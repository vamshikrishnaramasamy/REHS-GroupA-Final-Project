from dataclasses import dataclass
from pathlib import Path


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
    """Placeholder for DeepFace.find integration.

    The app logs detections through one narrow function so the team can replace
    this stub with DeepFace without changing the Flask routes.
    """
    _ = snapshot_path
    return None
