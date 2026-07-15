from dataclasses import dataclass
from pathlib import Path

import numpy as np
from deepface import DeepFace

from flask import current_app

from app.db import get_db

MIN_CONFIDENCE = 80.0
MODEL_NAME = "Facenet512"
DETECTOR_BACKEND = "retinaface"


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


def _cosine_confidence(a, b) -> float:
    a, b = np.array(a), np.array(b)
    cosine_sim = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    return float(cosine_sim) * 100.0


def recognize_snapshot(snapshot_path: str) -> RecognitionResult | None:
    """DeepFace.find integration: compares snapshot against stored embeddings
    and only returns a result when confidence clears MIN_CONFIDENCE (80%).
    """
    db = get_db()
    known = db.execute("""
        SELECT e.embedding_path, p.name
        FROM embeddings e JOIN people p ON e.person_id = p.id
    """).fetchall()

    if not known:
        return None

    try:
        rep = DeepFace.represent(
            img_path=snapshot_path,
            model_name=MODEL_NAME,
            detector_backend=DETECTOR_BACKEND,
            enforce_detection=False,
        )
    except Exception:
        return None

    if not rep:
        return None

    query_embedding = rep[0]["embedding"]

    best_name, best_confidence = None, 0.0
    for row in known:
        stored = np.load(row["embedding_path"])
        confidence = _cosine_confidence(query_embedding, stored)
        if confidence > best_confidence:
            best_name, best_confidence = row["name"], confidence

    if best_name is None or best_confidence < MIN_CONFIDENCE:
        return None

    return RecognitionResult(
        person_name=best_name,
        confidence=best_confidence,
        snapshot_path=snapshot_path,
    )