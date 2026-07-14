from flask import Flask

from .db import close_db, init_db
from .routes import bp

from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')
app.config['DATABASE'] = 'app.db'

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'mp4', 'avi'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

app.allowed_file = allowed_file


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


from . import db
from . import routes
app.register_blueprint(routes.bp)

with app.app_context():
    # This checks if the db file exists, and if not, runs your scheme installer script
    db.init_db()
