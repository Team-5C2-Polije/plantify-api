from flask import Flask
from .config import Config
from .extensions import db
from .main.routes import main
from .controllers.user_controller import user_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.db = db
    app.register_blueprint(main)
    app.register_blueprint(user_bp)
    return app
