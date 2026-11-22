"""Office clearance report. Student numbers are masked because the file leaves the screen."""

import csv
import io

from app.security.masking import mask_student_number
from app.services.clearance_service import staff_queue


def office_report(connection, office: str) -> dict:
    payload = staff_queue(connection, office)
    students = [
        {
            "student_number": mask_student_number(item["student_number"]),
            "display_name": item["display_name"],
            "status": item["status"],
            "reason": item["reason"] or "",
        }
        for item in payload["students"]
    ]
    return {"office": payload["office"], "counts": payload["counts"], "students": students}


def office_report_csv(report: dict) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=["student_number", "display_name", "status", "reason"],
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(report["students"])
    return buffer.getvalue()
