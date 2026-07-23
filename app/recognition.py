import threading
from dataclasses import dataclass
from pathlib import Path

from flask import current_app

from .db import get_db


MIN_CONFIDENCE = 80.0

# DeepFace.find() is CPU-heavy and not safe to run concurrently: overlapping
# calls (e.g. the background sampler firing while a manual /api/detect
# request is in flight) make TensorFlow's per-call thread pools fight each
# other for cores, which can turn a ~1s lookup into a many-minute stall.
_recognition_lock = threading.Lock()


def record_detection(image_bytes: bytes, filename: str, camera_name: str) -> dict:
    """Save a captured frame, run it through recognition, and log a detection row.

    Shared by /api/detect (external capture devices, e.g. the iPhone TrueDepth
    app) and the background camera sampler, so both paths behave identically.
    """
    upload_dir = Path(current_app.config["UPLOAD_FOLDER"]) / "detections"
    upload_dir.mkdir(parents=True, exist_ok=True)
    full_path = upload_dir / filename
    full_path.write_bytes(image_bytes)

    result = recognize_snapshot(str(full_path))
    person_name = result.person_name if result else "Unknown"
    confidence = result.confidence if result else 0.0

    db = get_db()
    db.execute(
        """
        INSERT INTO detections (person_name, camera_name, confidence, snapshot_path)
        VALUES (?, ?, ?, ?)
        """,
        (person_name, camera_name, confidence, f"detections/{filename}"),
    )
    db.commit()

    return {
        "match": result is not None,
        "person_name": person_name,
        "confidence": confidence,
    }


@dataclass(frozen=True)
class RecognitionResult:
    person_name: str
    confidence: float
    snapshot_path: str


def save_enrollment_image(upload, destination_dir: Path) -> str:
    destination_dir.mkdir(parents=True, exist_ok=True)
    filename = Path(upload.filename).name
    target = destination_dir / filename
    upload.save(target)
    return str(target)


def recognize_snapshot(snapshot_path: str) -> RecognitionResult | None:
    """Match a captured frame against enrolled people via DeepFace.find()."""
    from deepface import DeepFace

    people_dir = Path(current_app.config["UPLOAD_FOLDER"]) / "people"
    ref_images = [
        p for p in people_dir.rglob("*.*")
        if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
    ]
    if not ref_images:
        return None

    current_app.logger.info(
        "Starting DeepFace.find for %s against %d reference image(s)",
        snapshot_path, len(ref_images),
    )

    try:
        with _recognition_lock:
            matches = DeepFace.find(
                img_path=snapshot_path,
                db_path=str(people_dir),
                detector_backend="mtcnn",
                enforce_detection=False,
                silent=True,
            )
    except ValueError:
        return None

    if not matches or matches[0].empty:
        return None

    best = matches[0].iloc[0]
    confidence = float(best["confidence"])
    if confidence < MIN_CONFIDENCE:
        return None

    person_id = Path(best["identity"]).parent.name
    row = get_db().execute("SELECT name FROM people WHERE id = ?", (person_id,)).fetchone()
    if row is None:
        return None

    return RecognitionResult(person_name=row["name"], confidence=confidence, snapshot_path=snapshot_path)
