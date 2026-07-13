from flask import Flask

from .db import close_db, init_db
from .routes import bp


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        DATABASE="security_camera.sqlite3",
        UPLOAD_FOLDER="instance/uploads",
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,
    )

    app.teardown_appcontext(close_db)
    app.register_blueprint(bp)

    with app.app_context():
        init_db()

    return app
