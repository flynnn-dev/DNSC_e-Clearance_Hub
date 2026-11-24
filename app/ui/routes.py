"""Page shells. Sign-in is required before a dashboard is shown."""

import re

from flask import Blueprint, abort, redirect, render_template, url_for

from app.auth.session import current_user, role_required

_OFFICE = re.compile(r"[a-z0-9_-]{1,40}")

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


@bp.get("/student/clearance")
@role_required("student")
def student_clearance():
    return render_template("student/clearance.html")


@bp.get("/student/clearance/<office>")
@role_required("student")
def student_office(office: str):
    if _OFFICE.fullmatch(office) is None:
        abort(404)
    return render_template("student/office.html", office=office)


@bp.get("/student/documents")
@role_required("student")
def student_documents():
    return render_template("student/documents.html")


@bp.get("/student/announcements")
@role_required("student")
def student_announcements():
    return render_template("student/announcements.html")


@bp.get("/student/help")
@role_required("student")
def student_help():
    return render_template("student/help.html")


@bp.get("/staff")
@role_required("staff")
def staff_dashboard():
    return render_template("staff/dashboard.html")


@bp.get("/staff/students")
@role_required("staff")
def staff_students():
    return render_template("staff/students.html")


@bp.get("/staff/students/<status>")
@role_required("staff")
def staff_students_status(status: str):
    key = status.lower()
    if key not in {"hold", "pending", "cleared"}:
        abort(404)
    return redirect(url_for("ui.staff_students", status=key.upper()))


@bp.get("/staff/documents")
@role_required("staff")
def staff_documents():
    return render_template("staff/documents.html")


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
