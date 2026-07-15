import os
import sqlite3
from pathlib import Path

import cv2
import albumentations as A

REPO_ROOT = Path(__file__).resolve().parent
INPUT_DIR = REPO_ROOT / "untamperedImages"
OUTPUT_DIR = REPO_ROOT / "augmentedImages"
DB_PATH = REPO_ROOT / "instance" / "security_camera.sqlite3"
NUM_AUGMENTATIONS = 6


augmentation_pipeline = A.Compose([
    A.HorizontalFlip(p=0.5),
    A.VerticalFlip(p=0.5),
    A.Rotate(limit=15, p=0.8),
    A.RandomBrightnessContrast(brightness_limit=0.2, contrast_limit=0.2, p=0.8),
    A.GaussNoise(std_range=(0.02, 0.05), p=0.3),  # Adds noise for robustness
])


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS augmented_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_filename TEXT NOT NULL,
            output_filename TEXT NOT NULL,
            output_path TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    return conn


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_connection()

    supported_extensions = (".jpg", ".jpeg", ".png")
    generated_count = 0

    for filename in sorted(os.listdir(INPUT_DIR)):
        if not filename.lower().endswith(supported_extensions):
            continue

        image_path = INPUT_DIR / filename
        image = cv2.imread(str(image_path))
        if image is None:
            print(f"Skipping unreadable image: {filename}")
            continue

        base_name, ext = os.path.splitext(filename)

        for i in range(NUM_AUGMENTATIONS):
            augmented = augmentation_pipeline(image=image)
            augmented_image = augmented["image"]

            output_filename = f"{base_name}_aug_{i}{ext}"
            output_path = OUTPUT_DIR / output_filename
            cv2.imwrite(str(output_path), augmented_image)

            conn.execute(
                """
                INSERT INTO augmented_images (source_filename, output_filename, output_path)
                VALUES (?, ?, ?)
                """,
                (filename, output_filename, str(output_path)),
            )
            generated_count += 1

    conn.commit()
    conn.close()

    print(f"Augmentation complete! Generated {generated_count} images in '{OUTPUT_DIR}'.")


if __name__ == "__main__":
    main()
