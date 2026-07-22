import os

import click
from flask import Flask

from .db import close_db, init_db
from .detection_sampler import start_camera_sampler
from .routes import bp


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        DATABASE="security_camera.sqlite3",
        UPLOAD_FOLDER="instance/uploads",
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,
        SECRET_KEY=os.environ["SECRET_KEY"],
    )

    app.teardown_appcontext(close_db)
    app.register_blueprint(bp)

    with app.app_context():
        init_db()

    # Skip the reloader's watcher process (WERKZEUG_RUN_MAIN unset there) so
    # debug mode doesn't start two copies of the sampler thread.
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        start_camera_sampler(app)

    @app.cli.command("cleanup-clips")
    @click.option("--days", type=float, default=None, help="Retention period override, in days (default: CLIP_RETENTION_DAYS env or 30).")
    def cleanup_clips_command(days):
        from .clips import cleanup_old_clips

        removed = cleanup_old_clips(retention_days=days)
        click.echo(f"Removed {removed} clip file(s) past retention.")

    return app
