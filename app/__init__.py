"""DNSC e-Clearance Hub application factory."""

from flask import Flask, jsonify, render_template

from app.config import Config


def create_app() -> Flask:
    app = Flask(__name__)
    Config.apply(app)

    @app.get("/")
    def home():
        return render_template("home.html")

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    return app
