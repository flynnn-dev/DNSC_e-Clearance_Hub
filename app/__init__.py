"""DNSC e-Clearance Hub application factory."""

from flask import Flask, jsonify

from app.api.clearance import bp as clearance_api_bp
from app.api.reports import bp as reports_api_bp
from app.api.slips import bp as slips_api_bp
from app.auth.routes import bp as auth_bp
from app.auth.session import current_user
from app.config import Config
from app.security.csrf import csrf_token
from app.ui.routes import bp as ui_bp


def create_app() -> Flask:
    app = Flask(__name__)
    Config.apply(app)
    app.register_blueprint(ui_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(clearance_api_bp)
    app.register_blueprint(slips_api_bp)
    app.register_blueprint(reports_api_bp)

    @app.context_processor
    def inject_account():
        return {"current_user": current_user(), "csrf_token": csrf_token()}

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    return app
