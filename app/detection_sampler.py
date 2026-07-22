import os
import threading
import time
from datetime import datetime

import cv2

from .db import get_db
from .recognition import record_detection

SAMPLE_INTERVAL_SECONDS = float(os.environ.get("DETECTION_SAMPLE_INTERVAL_SECONDS", "30"))

_started = False
_lock = threading.Lock()


def start_camera_sampler(app):
    """Start a background thread that periodically grabs a frame from every
    active camera's stream and runs it through the same detection pipeline
    as /api/detect (the iPhone TrueDepth app's flow) — just triggered by the
    backend instead of an external capture device.
    """
    global _started
    with _lock:
        if _started:
            return
        _started = True

    thread = threading.Thread(target=_sample_loop, args=(app,), daemon=True)
    thread.start()


def _sample_loop(app):
    while True:
        time.sleep(SAMPLE_INTERVAL_SECONDS)
        with app.app_context():
            try:
                _sample_all_cameras()
            except Exception:
                app.logger.exception("Camera detection sampling failed")


def _sample_all_cameras():
    db = get_db()
    cameras = db.execute(
        "SELECT id, name, stream_url FROM cameras WHERE is_active = 1"
    ).fetchall()

    for camera in cameras:
        frame = _grab_frame(camera["stream_url"])
        if frame is None:
            continue

        ok, buffer = cv2.imencode(".jpg", frame)
        if not ok:
            continue

        filename = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_camera{camera['id']}.jpg"
        record_detection(buffer.tobytes(), filename, camera["name"])


def _grab_frame(stream_url):
    capture = cv2.VideoCapture(stream_url)
    if not capture.isOpened():
        capture.release()
        return None
    success, frame = capture.read()
    capture.release()
    return frame if success else None
