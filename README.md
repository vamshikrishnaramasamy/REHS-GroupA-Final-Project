# REHS Group A Final Project

Basic Flask implementation for an AI security camera dashboard.

## Current scope

- Enroll people with face images.
- Register camera stream URLs.
- Store people, images, cameras, and detections in SQLite.
- View dashboard stats and detection logs.
- Log demo detections while the DeepFace pipeline is being built.

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

## Planned work

See `.github/ISSUES.md` for teammate-sized issues.
