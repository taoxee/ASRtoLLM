from flask import Flask
from flask_cors import CORS


def create_app():
    application = Flask(__name__, static_folder="../static")
    CORS(application)

    from app.routes import bp
    application.register_blueprint(bp)

    return application
