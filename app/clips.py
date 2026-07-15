import os
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2

from .db import get_db

CLIPS_DIR = Path(__file__).resolve().parent / "static" / "clips"

PRE_SECONDS = float(os.environ.get("CLIP_PRE_SECONDS", "3"))
POST_SECONDS = float(os.environ.get("CLIP_POST_SECONDS", "3"))
DEFAULT_FPS = float(os.environ.get("CLIP_FALLBACK_FPS", "15"))
RETENTION_DAYS = float(os.environ.get("CLIP_RETENTION_DAYS", "30"))


def capture_detection_clip(stream_url: str, detection_id: int) -> str | None:
    """Record a short clip for a detection event and return its path relative to static/.

    There is no continuously-running frame buffer feeding this yet, so it can only
    capture frames from the moment it's called onward — PRE_SECONDS + POST_SECONDS
    of video starting at the trigger, not true pre-roll. See CLIPS.md.
    """
    if not stream_url:
        return None

    camera = cv2.VideoCapture(stream_url)
    if not camera.isOpened():
        camera.release()
        return None

    fps = camera.get(cv2.CAP_PROP_FPS) or 0
    if fps <= 1:
        fps = DEFAULT_FPS

    success, frame = camera.read()
    if not success:
        camera.release()
        return None

    height, width = frame.shape[:2]
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"detection_{detection_id}_{timestamp}.mp4"
    clip_path = CLIPS_DIR / filename

    writer = cv2.VideoWriter(str(clip_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    total_frames = max(1, int(fps * (PRE_SECONDS + POST_SECONDS)))
    deadline = time.monotonic() + PRE_SECONDS + POST_SECONDS + 2
    frames_written = 0

    writer.write(frame)
    frames_written += 1
    while frames_written < total_frames and time.monotonic() < deadline:
        success, frame = camera.read()
        if not success:
            break
        writer.write(frame)
        frames_written += 1

    writer.release()
    camera.release()

    if frames_written < max(1, int(fps * 0.5)):
        clip_path.unlink(missing_ok=True)
        return None

    return f"clips/{filename}"


def cleanup_old_clips(retention_days: float | None = None) -> int:
    """Delete clip files older than the retention period and clear clip_path for those rows.

    Returns the number of files removed.
    """
    days = RETENTION_DAYS if retention_days is None else retention_days
    cutoff = time.time() - days * 86400
    removed = 0

    if CLIPS_DIR.exists():
        for clip_file in CLIPS_DIR.iterdir():
            if clip_file.is_file() and clip_file.stat().st_mtime < cutoff:
                clip_file.unlink()
                removed += 1

    db = get_db()
    rows = db.execute("SELECT id, clip_path FROM detections WHERE clip_path != ''").fetchall()
    for row in rows:
        clip_file = CLIPS_DIR / Path(row["clip_path"]).name
        if not clip_file.exists():
            db.execute("UPDATE detections SET clip_path = '' WHERE id = ?", (row["id"],))
    db.commit()

    return removed
