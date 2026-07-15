import os

if __name__ == "__main__":
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        with app.app_context():
            from app.db import get_db
            cameras = get_db().execute(
                "SELECT name, stream_url FROM cameras WHERE is_active = 1"
            ).fetchall()

        for cam in cameras:
            t = threading.Thread(target=run_camera_loop, args=(app, cam["name"], cam["stream_url"]), daemon=True)
            t.start()

    app.run(debug=True)