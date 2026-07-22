from dataclasses import dataclass
from pathlib import Path

from flask import current_app

from .db import get_db


MIN_CONFIDENCE = 80.0


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
    if not any(people_dir.rglob("*.*")):
        return None

    try:
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
