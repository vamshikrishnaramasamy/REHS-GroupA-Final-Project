# REHS Group A Final Project

Basic Flask implementation for an AI security camera dashboard.

## Current scope

- Enroll people with face images.
- Register camera stream URLs.
- Store people, images, cameras, and detections in SQLite.
- View dashboard stats and detection logs.
- Log demo detections while the DeepFace pipeline is being built.

## Tech stack

- Facial recognition: DeepFace
- Web server: Flask
- Database: SQLite
- Face enrollment plan: collect 5 starting images, augment each image 6 times, then add high-confidence production detections back into the dataset.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
flask --app run run --debug
```

Open http://127.0.0.1:5000.

Install `requirements-ai.txt` when working on DeepFace recognition tasks.

## Project layout

- `app/routes.py`: Flask page and form routes.
- `app/db.py`: SQLite schema and connection helpers.
- `app/recognition.py`: DeepFace integration point.
- `app/templates/dashboard.html`: Dashboard UI.
- `app/static/styles.css`: Dashboard styles.
- `imagevariation.py`: Existing image augmentation script from the project history.

## Implementation goals

- Dashboard with person enrollment.
- Live camera feed views.
- Detection log with date, time, name, confidence, camera, and snapshot path.
- BLE/RFID identity proof of concept, with image recognition fallback.
- Notification path, ideally app-based, with text or email fallback.
- P2P redundancy research if time allows.

## Planned work

See `.github/ISSUES.md` and the GitHub issue tracker for teammate-sized issues.
