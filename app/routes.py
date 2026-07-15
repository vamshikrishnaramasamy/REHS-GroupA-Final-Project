import cv2
from pathlib import Path
# Added 'jsonify' to the imports
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for, Response, jsonify
from .db import get_db
from .recognition import save_enrollment_image
from datetime import datetime

bp = Blueprint("main", __name__)

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
    db = get_db()
    
    # 1. Fetch raw cameras from the SQLite database
    raw_cameras = db.execute("SELECT * FROM cameras ORDER BY name").fetchall()
    
    processed_cameras = []
    online_count = 0
    offline_count = 0

    # 2. Convert SQLite Row objects to mutable dicts, check status, and update DB
    for row in raw_cameras:
        camera_dict = dict(row)
        
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
        offline_count=offline_count
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
        "last_frame": last_frame_time
    })


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
    db.execute(
        """
        INSERT INTO detections (person_name, camera_name, confidence, snapshot_path)
        VALUES (?, ?, ?, ?)
        """,
        (
            request.form.get("person_name", "Unknown"),
            request.form.get("camera_name", "Demo Camera"),
            float(request.form.get("confidence", 82)),
            "",
        ),
    )
    db.commit()
    flash("Demo detection logged.")
    return redirect(url_for("main.dashboard"))