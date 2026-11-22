"""Page shells. Sign-in is required before a dashboard is shown."""

from flask import Blueprint, redirect, render_template, url_for

from app.auth.session import current_user, role_required

bp = Blueprint("ui", __name__)


@bp.get("/")
def home():
    return redirect(_destination())


@bp.get("/login")
def login_page():
    user = current_user()
    if user is not None:
        return redirect(_destination(user))
    return render_template("auth/login.html")


@bp.get("/student")
@role_required("student")
def student_dashboard():
    return render_template("student/dashboard.html")


@bp.get("/staff")
@role_required("staff")
def staff_dashboard():
    return render_template("staff/dashboard.html")


@bp.get("/verify/<token>")
def verify_slip_page(token: str):
    return render_template("public/verify.html", token=token)


def _destination(user=None) -> str:
    account = user if user is not None else current_user()
    if account is None:
        return url_for("ui.login_page")
    if account["role"] == "staff":
        return url_for("ui.staff_dashboard")
    return url_for("ui.student_dashboard")
