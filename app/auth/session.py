"""The signed-in user comes from the session, then the database."""

from functools import wraps

from flask import g, jsonify, redirect, request, session, url_for

from app.db.users import connect, find_user_by_id

_ROLES = {"student", "staff"}


def current_user():
    if "current_user" in g:
        return g.current_user
    user_id = session.get("user_id")
    role = session.get("role")
    if not isinstance(user_id, int) or role not in _ROLES:
        g.current_user = None
        return None
    with connect() as connection:
        user = find_user_by_id(connection, user_id)
    if user is None or user["role"] != role:
        session.clear()
        g.current_user = None
        return None
    g.current_user = user
    return user


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            if request.path.startswith("/api/"):
                return jsonify(error="Sign in required."), 401
            return redirect(url_for("ui.login_page"))
        return view(*args, **kwargs)

    return wrapped


def role_required(role: str):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if user is None:
                if request.path.startswith("/api/"):
                    return jsonify(error="Sign in required."), 401
                return redirect(url_for("ui.login_page"))
            if user["role"] != role:
                if request.path.startswith("/api/"):
                    return jsonify(error="You cannot open this page."), 403
                return _forbidden()
            return view(*args, **kwargs)

        return wrapped

    return decorator


def _forbidden():
    from flask import render_template

    return render_template("errors/forbidden.html"), 403
