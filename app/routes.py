from pathlib import Path

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from .db import get_db
from .notifications import send_detection_alert
from .recognition import save_enrollment_image

bp = Blueprint("main", __name__)


@bp.route("/")
def dashboard():
    db = get_db()
    stats = {
        "people": db.execute("SELECT COUNT(*) FROM people").fetchone()[0],
        "cameras": db.execute("SELECT COUNT(*) FROM cameras").fetchone()[0],
        "detections": db.execute("SELECT COUNT(*) FROM detections").fetchone()[0],
    }
    detections = db.execute(
        "SELECT * FROM detections ORDER BY occurred_at DESC LIMIT 20"
    ).fetchall()
    cameras = db.execute("SELECT * FROM cameras ORDER BY name").fetchall()
    people = db.execute(
        """
        SELECT people.*, COUNT(face_images.id) AS image_count
        FROM people
        LEFT JOIN face_images ON face_images.person_id = people.id
        GROUP BY people.id
        ORDER BY people.name
        """
    ).fetchall()
    return render_template(
        "dashboard.html",
        stats=stats,
        detections=detections,
        cameras=cameras,
        people=people,
    )

@bp.route("/cameras")
def cameras():

    cameras = []

    return render_template(
        "camera.html",
        cameras=cameras,
        online_count=0,
        offline_count=0
    )

@bp.post("/people")
def create_person():
    name = request.form.get("name", "").strip()
    notes = request.form.get("notes", "").strip()
    images = [image for image in request.files.getlist("images") if image.filename]
    if not name:
        flash("Name is required.")
        return redirect(url_for("main.dashboard"))
    if len(images) < 1:
        flash("Upload at least one face image.")
        return redirect(url_for("main.dashboard"))

    db = get_db()
    cursor = db.execute("INSERT INTO people (name, notes) VALUES (?, ?)", (name, notes))
    person_id = cursor.lastrowid
    upload_dir = Path(current_app.config["UPLOAD_FOLDER"]) / "people" / str(person_id)
    for image in images:
        path = save_enrollment_image(image, upload_dir)
        db.execute(
            "INSERT INTO face_images (person_id, path) VALUES (?, ?)",
            (person_id, path),
        )
    db.commit()
    flash(f"Added {name}.")
    return redirect(url_for("main.dashboard"))


@bp.post("/cameras")
def create_camera():
    name = request.form.get("name", "").strip()
    stream_url = request.form.get("stream_url", "").strip()
    location = request.form.get("location", "").strip()
    if not name or not stream_url:
        flash("Camera name and stream URL are required.")
        return redirect(url_for("main.dashboard"))

    db = get_db()
    db.execute(
        "INSERT INTO cameras (name, stream_url, location) VALUES (?, ?, ?)",
        (name, stream_url, location),
    )
    db.commit()
    flash(f"Added camera {name}.")
    return redirect(url_for("main.dashboard"))


@bp.post("/detections/demo")
def create_demo_detection():
    db = get_db()
    person_name = request.form.get("person_name", "Unknown")
    camera_name = request.form.get("camera_name", "Demo Camera")
    confidence = float(request.form.get("confidence", 82))
    cursor = db.execute(
        """
        INSERT INTO detections (person_name, camera_name, confidence, snapshot_path)
        VALUES (?, ?, ?, ?)
        """,
        (person_name, camera_name, confidence, ""),
    )
    db.commit()
    row = db.execute(
        "SELECT occurred_at FROM detections WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()

    try:
        send_detection_alert(person_name, camera_name, confidence, row["occurred_at"])
    except Exception as exc:  # noqa: BLE001 - alerting must never break detection logging
        current_app.logger.warning("Detection alert email failed: %s", exc)

    flash("Demo detection logged.")
    return redirect(url_for("main.dashboard"))
