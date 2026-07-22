import ipaddress
import re
import shutil
import sqlite3
import cv2
from pathlib import Path
# Added 'jsonify' to the imports
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for, Response, jsonify, send_from_directory
from werkzeug.utils import secure_filename

from augmentation_utils import generate_variants

from .clips import CLIPS_DIR, capture_detection_clip
from .db import get_db
from .notifications import send_detection_alert
from .recognition import record_detection, save_enrollment_image
from datetime import datetime

bp = Blueprint("main", __name__)

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
DEFAULT_ANDROID_WEBCAM_PORT = 8080


def is_allowed_image(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS
    )


def validate_face_images(uploaded_files):
    """Secure filenames and validate extensions for face-image uploads.

    Returns (images, error_message). On error, images is [].
    """
    images = []
    for image in uploaded_files:
        if not image.filename:
            continue
        if not is_allowed_image(image.filename):
            return [], f"Error: {image.filename} is an invalid file type. Only PNG, JPG, JPEG, WEBP allowed."
        image.filename = secure_filename(image.filename)
        images.append(image)
    return images, None


def slugify_username(name):
    """Turn a person's name into the bare alphanumeric stem used in filenames."""
    return re.sub(r"[^a-zA-Z0-9]", "", name).lower() or "person"

# --- HELPERS FOR STREAMING ---

def gen_frames(stream_url):
    """Continuously captures frames from the RTSP stream and yields them as MJPEG."""
    camera = cv2.VideoCapture(stream_url)
    camera.set(cv2.CAP_PROP_BUFFERSIZE, 2)  # Low latency buffer
    
    while True:
        success, frame = camera.read()
        if not success:
            # Fallback if connection drops mid-stream
            break
        else:
            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                   
    camera.release()

def is_camera_online(stream_url):
    """Briefly checks if the stream is reachable (timeout 1s)."""
    cap = cv2.VideoCapture(stream_url)
    if not cap.isOpened():
        return False
    # Read one quick frame to confirm
    ret, _ = cap.read()
    cap.release()
    return ret


# --- ROUTES ---

@bp.route("/")
def dashboard():
    # --- TEMPORARY DIAGNOSTIC PRINT ---
    import os
    from flask import current_app
    db_path = os.path.join(current_app.instance_path, current_app.config["DATABASE"])
    print("\n" + "="*50)
    print(f"YOUR ACTIVE DATABASE IS AT:\n{os.path.abspath(db_path)}")
    print("="*50 + "\n")
    # ----------------------------------
    db = get_db()

    # 1. Capture filter values from the URL query parameters
    person_filter = request.args.get("person", "").strip()
    camera_filter = request.args.get("camera", "").strip()
    min_conf = request.args.get("min_confidence", type=float)

    # 2. Build dynamic SQL query
    query = "SELECT * FROM detections WHERE 1=1"
    params = []

    if person_filter:
        query += " AND person_name LIKE ?"
        params.append(f"%{person_filter}%")
    if camera_filter:
        query += " AND camera_name LIKE ?"
        params.append(f"%{camera_filter}%")
    if min_conf is not None:
        query += " AND confidence >= ?"
        params.append(min_conf)

    query += " ORDER BY occurred_at DESC LIMIT 50"

    # 3. Execute filtered query
    detections = db.execute(query, params).fetchall()

    # Stats and secondary queries
    stats = {
        "people": db.execute("SELECT COUNT(*) FROM people").fetchone()[0],
        "cameras": db.execute("SELECT COUNT(*) FROM cameras").fetchone()[0],
        "detections": db.execute("SELECT COUNT(*) FROM detections").fetchone()[0],
        "augmented_images": db.execute("SELECT COUNT(*) FROM augmented_images").fetchone()[0],
    }
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
    augmented_sources = db.execute(
        """
        SELECT source_filename, COUNT(*) AS augmented_count
        FROM augmented_images
        GROUP BY source_filename
        ORDER BY source_filename
        """
    ).fetchall()

    return render_template(
        "dashboard.html",
        stats=stats,
        detections=detections,
        cameras=cameras,
        people=people,
        augmented_sources=augmented_sources,
        # Pass filters back so input fields stay populated after submitting
        filters={"person": person_filter, "camera": camera_filter, "min_conf": min_conf},
    )


@bp.route("/cameras")
def cameras():
    db = get_db()
    
    # 1. Fetch raw cameras from the SQLite database
    raw_cameras = db.execute("SELECT * FROM cameras ORDER BY name").fetchall()
    
    processed_cameras = []
    online_count = 0
    offline_count = 0
    disabled_count = 0

    # 2. Convert SQLite Row objects to mutable dicts, check status, and update DB
    for row in raw_cameras:
        camera_dict = dict(row)

        if not camera_dict["is_active"]:
            # Disabled cameras are skipped entirely, no network ping wasted on them.
            camera_dict["online"] = False
            disabled_count += 1
            processed_cameras.append(camera_dict)
            continue

        # Check if the RTSP stream is currently alive
        is_online = is_camera_online(camera_dict["stream_url"])
        camera_dict["online"] = is_online

        if is_online:
            online_count += 1
            # Update the last_frame value to the current time on page load
            camera_dict["last_frame"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            db.execute(
                "UPDATE cameras SET last_frame = ? WHERE id = ?",
                (camera_dict["last_frame"], camera_dict["id"])
            )
        else:
            offline_count += 1

        processed_cameras.append(camera_dict)

    db.commit()

    return render_template(
        "camera.html",
        cameras=processed_cameras,
        online_count=online_count,
        offline_count=offline_count,
        disabled_count=disabled_count,
    )


@bp.route("/video_feed/<int:camera_id>")
def video_feed(camera_id):
    db = get_db()
    # Query database for the stream URL matching this camera ID
    camera = db.execute("SELECT * FROM cameras WHERE id = ?", (camera_id,)).fetchone()
    if not camera:
        return "Camera not found", 404
        
    return Response(
        gen_frames(camera["stream_url"]),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


# --- DYNAMIC CAMERA STATUS & TIMELINE API ---

@bp.route("/api/camera_status/<int:camera_id>")
def camera_status(camera_id):
    db = get_db()
    camera = db.execute("SELECT * FROM cameras WHERE id = ?", (camera_id,)).fetchone()
    if not camera:
        return jsonify({"online": False, "last_frame": "Never"}), 404

    if not camera["is_active"]:
        return jsonify({"online": False, "disabled": True, "last_frame": camera["last_frame"] or "Never"})

    is_online = is_camera_online(camera["stream_url"])
    last_frame_time = camera["last_frame"] or "Never"
    
    # ONLY update the database timestamp if the camera is online
    if is_online:
        last_frame_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            "UPDATE cameras SET last_frame = ? WHERE id = ?", 
            (last_frame_time, camera_id)
        )
        db.commit()
        
    return jsonify({
        "online": is_online,
        "disabled": False,
        "last_frame": last_frame_time
    })


@bp.post("/api/detect")
def detect_face():
    """Accept a single frame from an external detector (e.g. the iPhone TrueDepth
    app), run it through the face recognition pipeline, and log the result.
    """
    image = request.files.get("image")
    if image is None or not image.filename:
        return jsonify({"error": "No image file provided under form field 'image'."}), 400
    if not is_allowed_image(image.filename):
        return jsonify({"error": f"'{image.filename}' is an invalid file type. Only PNG, JPG, JPEG, WEBP allowed."}), 400

    camera_name = request.form.get("camera_name", "").strip() or "iPhone TrueDepth"
    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{secure_filename(image.filename)}"

    result = record_detection(image.read(), filename, camera_name)
    return jsonify(result)


# --- POST ENDPOINTS ---

@bp.post("/cameras/delete/<int:camera_id>")
def delete_camera(camera_id):
    db = get_db()
    
    # Fetch camera name first to display in the flash message
    camera = db.execute("SELECT name FROM cameras WHERE id = ?", (camera_id,)).fetchone()
    camera_name = camera["name"] if camera else "Unknown Camera"
    
    # Delete the camera record from the database
    db.execute("DELETE FROM cameras WHERE id = ?", (camera_id,))
    db.commit()
    
    flash(f"Removed camera: {camera_name}")

    return redirect(url_for("main.cameras"))


@bp.post("/cameras/<int:camera_id>/toggle")
def toggle_camera(camera_id):
    db = get_db()
    camera = db.execute("SELECT name, is_active FROM cameras WHERE id = ?", (camera_id,)).fetchone()
    if not camera:
        flash("Camera not found.")
        return redirect(url_for("main.cameras"))

    new_state = 0 if camera["is_active"] else 1
    db.execute("UPDATE cameras SET is_active = ? WHERE id = ?", (new_state, camera_id))
    db.commit()

    flash(f"{camera['name']} {'enabled' if new_state else 'disabled'}.")
    return redirect(url_for("main.cameras"))


@bp.post("/detections/mark_false_positive/<int:det_id>")
def mark_false_positive(det_id):
    db = get_db()
    db.execute("UPDATE detections SET is_false_positive = 1 WHERE id = ?", (det_id,))
    db.commit()
    flash("Detection marked as false positive.")
    return redirect(url_for("main.dashboard", **request.args)) # Keeps filters active


@bp.post("/people")
def create_person():
    name = request.form.get("name", "").strip()
    notes = request.form.get("notes", "").strip()

    images, error = validate_face_images(request.files.getlist("images"))
    if error:
        flash(error)
        return redirect(url_for("main.dashboard"))

    if not name:
        flash("Name is required.")
        return redirect(url_for("main.dashboard"))
    if len(images) < 1:
        flash("Upload at least one face image.")
        return redirect(url_for("main.dashboard"))

    db = get_db()
    existing = db.execute(
        "SELECT id FROM people WHERE lower(name) = lower(?)", (name,)
    ).fetchone()
    if existing:
        flash(f"A person named '{name}' already exists.")
        return redirect(url_for("main.dashboard"))

    try:
        cursor = db.execute("INSERT INTO people (name, notes) VALUES (?, ?)", (name, notes))
    except sqlite3.IntegrityError:
        flash(f"A person named '{name}' already exists.")
        return redirect(url_for("main.dashboard"))
    person_id = cursor.lastrowid
    username = slugify_username(name)
    upload_dir = Path(current_app.config["UPLOAD_FOLDER"]) / "people" / str(person_id)

    for idx, image in enumerate(images, start=1):
        ext = Path(image.filename).suffix.lower()
        image.filename = f"{username}{idx}{ext}"
        save_enrollment_image(image, upload_dir)
        db.execute(
            "INSERT INTO face_images (person_id, path) VALUES (?, ?)",
            (person_id, f"people/{person_id}/{image.filename}"),
        )
    db.commit()
    flash(f"Added {name}.")
    return redirect(url_for("main.dashboard"))


@bp.route("/people/<int:person_id>")
def person_detail(person_id):
    db = get_db()
    person = db.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
    if not person:
        flash("Person not found.")
        return redirect(url_for("main.dashboard"))

    images = db.execute(
        "SELECT * FROM face_images WHERE person_id = ? ORDER BY created_at DESC",
        (person_id,),
    ).fetchall()
    detections = db.execute(
        "SELECT * FROM detections WHERE person_name = ? ORDER BY occurred_at DESC",
        (person["name"],),
    ).fetchall()

    return render_template(
        "person_detail.html",
        person=person,
        images=images,
        detections=detections,
    )


@bp.post("/people/<int:person_id>/images")
def add_person_images(person_id):
    db = get_db()
    person = db.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
    if not person:
        flash("Person not found.")
        return redirect(url_for("main.dashboard"))

    images, error = validate_face_images(request.files.getlist("images"))
    if error:
        flash(error)
        return redirect(url_for("main.person_detail", person_id=person_id))
    if len(images) < 1:
        flash("Upload at least one face image.")
        return redirect(url_for("main.person_detail", person_id=person_id))

    username = slugify_username(person["name"])
    existing_count = db.execute(
        "SELECT COUNT(*) FROM face_images WHERE person_id = ? AND is_augmented = 0",
        (person_id,),
    ).fetchone()[0]

    upload_dir = Path(current_app.config["UPLOAD_FOLDER"]) / "people" / str(person_id)
    for offset, image in enumerate(images, start=1):
        idx = existing_count + offset
        ext = Path(image.filename).suffix.lower()
        image.filename = f"{username}{idx}{ext}"
        save_enrollment_image(image, upload_dir)
        db.execute(
            "INSERT INTO face_images (person_id, path) VALUES (?, ?)",
            (person_id, f"people/{person_id}/{image.filename}"),
        )
    db.commit()
    flash(f"Added {len(images)} image(s).")
    return redirect(url_for("main.person_detail", person_id=person_id))


@bp.post("/people/<int:person_id>/augment")
def augment_person_images(person_id):
    db = get_db()
    person = db.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
    if not person:
        flash("Person not found.")
        return redirect(url_for("main.dashboard"))

    source_images = db.execute(
        "SELECT * FROM face_images WHERE person_id = ? AND is_augmented = 0",
        (person_id,),
    ).fetchall()
    if not source_images:
        flash("No source images available to augment.")
        return redirect(url_for("main.person_detail", person_id=person_id))

    username = slugify_username(person["name"])
    upload_root = Path(current_app.config["UPLOAD_FOLDER"])
    upload_dir = upload_root / "people" / str(person_id)
    generated_count = 0

    for source in source_images:
        source_name = Path(source["path"]).name
        image = cv2.imread(str(upload_root / source["path"]))
        if image is None:
            continue

        stem = Path(source_name).stem
        ext = Path(source_name).suffix
        match = re.match(rf"^{re.escape(username)}(\d+)$", stem)
        source_index = match.group(1) if match else stem
        for i, augmented_image in enumerate(generate_variants(image), start=1):
            output_filename = f"{username}{source_index}_{i}{ext}"
            output_path = upload_dir / output_filename
            cv2.imwrite(str(output_path), augmented_image)

            db.execute(
                "INSERT INTO face_images (person_id, path, is_augmented) VALUES (?, ?, 1)",
                (person_id, f"people/{person_id}/{output_filename}"),
            )
            db.execute(
                """
                INSERT INTO augmented_images (person_id, source_filename, output_filename, output_path)
                VALUES (?, ?, ?, ?)
                """,
                (person_id, source_name, output_filename, str(output_path)),
            )
            generated_count += 1

    db.commit()
    flash(f"Generated {generated_count} augmented image(s) from {len(source_images)} source image(s).")
    return redirect(url_for("main.person_detail", person_id=person_id))


@bp.post("/people/<int:person_id>/images/<int:image_id>/delete")
def delete_person_image(person_id, image_id):
    db = get_db()
    image = db.execute(
        "SELECT * FROM face_images WHERE id = ? AND person_id = ?",
        (image_id, person_id),
    ).fetchone()
    if not image:
        flash("Image not found.")
        return redirect(url_for("main.person_detail", person_id=person_id))

    file_path = Path(current_app.config["UPLOAD_FOLDER"]) / image["path"]
    file_path.unlink(missing_ok=True)

    db.execute("DELETE FROM face_images WHERE id = ?", (image_id,))
    if image["is_augmented"]:
        db.execute(
            "DELETE FROM augmented_images WHERE person_id = ? AND output_filename = ?",
            (person_id, Path(image["path"]).name),
        )
    db.commit()
    flash("Image removed.")
    return redirect(url_for("main.person_detail", person_id=person_id))


def _delete_person_record(db, person_id):
    """Remove a person's uploaded files and DB row.

    face_images and augmented_images rows cascade-delete via their FKs;
    only the on-disk files need explicit cleanup.
    """
    upload_dir = Path(current_app.config["UPLOAD_FOLDER"]) / "people" / str(person_id)
    shutil.rmtree(upload_dir, ignore_errors=True)
    db.execute("DELETE FROM people WHERE id = ?", (person_id,))


@bp.post("/people/<int:person_id>/delete")
def delete_person(person_id):
    db = get_db()
    person = db.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
    if not person:
        flash("Person not found.")
        return redirect(url_for("main.dashboard"))

    _delete_person_record(db, person_id)
    db.commit()
    flash(f"Removed {person['name']}.")
    return redirect(url_for("main.dashboard"))


@bp.post("/people/bulk_delete")
def bulk_delete_people():
    person_ids = request.form.getlist("person_ids", type=int)
    if not person_ids:
        flash("No people selected.")
        return redirect(url_for("main.dashboard"))

    db = get_db()
    placeholders = ",".join("?" * len(person_ids))
    rows = db.execute(
        f"SELECT id, name FROM people WHERE id IN ({placeholders})", person_ids
    ).fetchall()

    for row in rows:
        _delete_person_record(db, row["id"])
    db.commit()
    flash(f"Removed {len(rows)} people.")
    return redirect(url_for("main.dashboard"))


@bp.post("/detections/clear")
def clear_detections():
    db = get_db()
    rows = db.execute("SELECT clip_path FROM detections WHERE clip_path != ''").fetchall()
    for row in rows:
        (CLIPS_DIR / Path(row["clip_path"]).name).unlink(missing_ok=True)

    count = db.execute("SELECT COUNT(*) FROM detections").fetchone()[0]
    db.execute("DELETE FROM detections")
    db.commit()
    flash(f"Cleared {count} detection log(s).")
    return redirect(url_for("main.dashboard"))


@bp.route("/uploads/<path:filename>")
def uploaded_file(filename):
    upload_root = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    return send_from_directory(upload_root, filename)


@bp.post("/cameras")
def create_camera():
    name = request.form.get("name", "").strip()
    location = request.form.get("location", "").strip()
    source_type = request.form.get("source_type", "manual").strip()

    if not name:
        flash("Camera name is required.")
        return redirect(url_for("main.dashboard"))

    if source_type == "iphone_wifi":
        # TODO(teammate): wire up iPhone webcam support (e.g. an RTSP/HTTP
        # stream from an app like "NDI HX Camera" or "EpocCam") the same way
        # android_wifi below builds a stream_url from user input.
        flash("iPhone webcam support isn't wired up yet.")
        return redirect(url_for("main.dashboard"))

    if source_type == "android_wifi":
        ip_address = request.form.get("android_ip", "").strip()
        port = request.form.get("android_port", "").strip() or str(DEFAULT_ANDROID_WEBCAM_PORT)

        if not ip_address:
            flash("The phone's IP address is required for an Android webcam.")
            return redirect(url_for("main.dashboard"))
        try:
            ipaddress.ip_address(ip_address)
        except ValueError:
            flash(f"'{ip_address}' is not a valid IP address.")
            return redirect(url_for("main.dashboard"))
        if not port.isdigit():
            flash("Port must be a number.")
            return redirect(url_for("main.dashboard"))

        stream_url = f"http://{ip_address}:{port}/video"
    else:
        source_type = "manual"
        stream_url = request.form.get("stream_url", "").strip()
        if not stream_url:
            flash("Stream URL is required.")
            return redirect(url_for("main.dashboard"))

    db = get_db()
    db.execute(
        "INSERT INTO cameras (name, stream_url, location, source_type) VALUES (?, ?, ?, ?)",
        (name, stream_url, location, source_type),
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
    detection_id = cursor.lastrowid
    row = db.execute(
        "SELECT occurred_at FROM detections WHERE id = ?", (detection_id,)
    ).fetchone()

    try:
        send_detection_alert(person_name, camera_name, confidence, row["occurred_at"])
    except Exception as exc:  # noqa: BLE001 - alerting must never break detection logging
        current_app.logger.warning("Detection alert email failed: %s", exc)

    try:
        camera_row = db.execute(
            "SELECT stream_url FROM cameras WHERE name = ?", (camera_name,)
        ).fetchone()
        if camera_row and camera_row["stream_url"]:
            clip_path = capture_detection_clip(camera_row["stream_url"], detection_id)
            if clip_path:
                db.execute(
                    "UPDATE detections SET clip_path = ? WHERE id = ?",
                    (clip_path, detection_id),
                )
                db.commit()
    except Exception as exc:  # noqa: BLE001 - clip capture must never break detection logging
        current_app.logger.warning("Detection clip capture failed: %s", exc)

    flash("Demo detection logged.")
    return redirect(url_for("main.dashboard"))
