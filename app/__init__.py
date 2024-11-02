from flask import Flask
from .config import Config
from .extensions import db
from .main.routes import main
from .controllers.auth_controller import auth_bp
from .controllers.device_controller import device_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.db = db
    app.register_blueprint(main)
    app.register_blueprint(auth_bp)
    app.register_blueprint(device_bp)
    return app
