"""Staff office reports. The signed-in office is the only office in the file."""

from flask import Blueprint, Response, jsonify

from app.auth.session import current_user, role_required
from app.db.users import connect
from app.services.clearance_service import ClearanceError
from app.services.report_service import office_report, office_report_csv

bp = Blueprint("reports_api", __name__)


@bp.get("/api/office/reports.json")
@role_required("staff")
def report_json():
    try:
        report = _report()
    except ClearanceError as exc:
        return jsonify(error=str(exc)), exc.status
    return jsonify(report)


@bp.get("/api/office/reports.csv")
@role_required("staff")
def report_csv():
    try:
        report = _report()
    except ClearanceError as exc:
        return jsonify(error=str(exc)), exc.status
    body = office_report_csv(report)
    filename = f"{report['office']}-clearance.csv"
    return Response(
        body,
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _report() -> dict:
    user = current_user()
    with connect() as connection:
        return office_report(connection, user["office"])
