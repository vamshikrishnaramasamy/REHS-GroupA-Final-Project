import os
import numpy as np
from deepface import DeepFace

from app import create_app
from app.db import get_db, insert_embedding, clear_embeddings

MODEL_NAME = "Facenet512"
DETECTOR_BACKEND = "retinaface"
EMBEDDING_DIR = os.path.join(os.path.dirname(__file__), "instance", "embeddings")


def rebuild():
    app = create_app()
    with app.app_context():
        db = get_db()
        clear_embeddings(db)
        os.makedirs(EMBEDDING_DIR, exist_ok=True)

        people = db.execute("SELECT id, name FROM people").fetchall()

        for person in people:
            person_id, name = person["id"], person["name"]
            images = db.execute(
                "SELECT path FROM face_images WHERE person_id = ?", (person_id,)
            ).fetchall()

            embeddings = []
            for row in images:
                try:
                    result = DeepFace.represent(
                        img_path=row["path"],
                        model_name=MODEL_NAME,
                        detector_backend=DETECTOR_BACKEND,
                        enforce_detection=False,
                    )
                    embeddings.append(result[0]["embedding"])
                except Exception as e:
                    print(f"skip {row['path']}: {e}")

            if not embeddings:
                print(f"no usable images for {name}, skipping")
                continue

            avg_embedding = np.mean(np.array(embeddings), axis=0)
            embedding_path = os.path.join(EMBEDDING_DIR, f"{person_id}.npy")
            np.save(embedding_path, avg_embedding)

            insert_embedding(db, person_id, MODEL_NAME, DETECTOR_BACKEND, embedding_path)
            print(f"rebuilt embedding for {name} ({len(embeddings)} images)")

    print("Rebuild complete.")


if __name__ == "__main__":
    rebuild()