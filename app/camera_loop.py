import time
from pathlib import Path

import cv2

from app.db import get_db
from app.recognition import recognize_snapshot

CHECK_INTERVAL_SEC = 2
SNAPSHOT_DIR = Path("instance/snapshots")


def run_camera_loop(app, camera_name: str, stream_url: str):
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(stream_url)

    if not cap.isOpened():
        print(f"Could not open stream for {camera_name}: {stream_url}")
        return

    last_check = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.5)
                continue

            now = time.time()
            if now - last_check < CHECK_INTERVAL_SEC:
                continue
            last_check = now

            snapshot_path = str(SNAPSHOT_DIR / f"{camera_name}_{int(now)}.jpg")
            cv2.imwrite(snapshot_path, frame)

            with app.app_context():
                result = recognize_snapshot(snapshot_path)
                if result is not None:
                    db = get_db()
                    db.execute("""
                        INSERT INTO detections
                            (person_name, camera_name, confidence, snapshot_path)
                        VALUES (?, ?, ?, ?)
                    """, (result.person_name, camera_name, result.confidence, snapshot_path))
                    db.commit()
                    print(f"Detected {result.person_name} ({result.confidence:.1f}%) on {camera_name}")
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()