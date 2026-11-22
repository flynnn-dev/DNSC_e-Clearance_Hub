"""Read environment settings when the application starts."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    """Load settings from the environment. Secrets stay out of source code."""

    @staticmethod
    def apply(app) -> None:
        load_dotenv(BASE_DIR / ".env")
        secret_key = os.environ.get("SECRET_KEY", "").strip()
        if not secret_key:
            raise RuntimeError(
                "SECRET_KEY is missing. Copy .env.example to .env and set SECRET_KEY."
            )
        app.config["SECRET_KEY"] = secret_key
        app.config["DATABASE_URL"] = os.environ.get("DATABASE_URL", "").strip()
        app.config["REGISTRAR_BASE_URL"] = os.environ.get("REGISTRAR_BASE_URL", "").strip()
        app.config["REGISTRAR_API_KEY"] = os.environ.get("REGISTRAR_API_KEY", "").strip()
        app.config["HMAC_SECRET"] = os.environ.get("HMAC_SECRET", "").strip()
        app.config["SLIP_SIGNING_KEY"] = os.environ.get("SLIP_SIGNING_KEY", "").strip()
        app.config["CLEARANCE_ANCHOR_DATE"] = os.environ.get("CLEARANCE_ANCHOR_DATE", "").strip()
        app.config["CLEARANCE_WORKING_DAYS"] = os.environ.get("CLEARANCE_WORKING_DAYS", "").strip()
        app.config["SESSION_COOKIE_HTTPONLY"] = True
        app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
        secure = os.environ.get("SESSION_COOKIE_SECURE", "").strip().lower()
        app.config["SESSION_COOKIE_SECURE"] = secure in {"1", "true", "yes"}
