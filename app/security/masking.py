"""Mask a student number before it leaves the Hub on a public page."""

import re

_STUDENT_NUMBER = re.compile(r"^\d{4}-\d{5}$")


def mask_student_number(student_number: str) -> str:
    """Keep the year and the last two digits. 2023-24935 becomes 2023-***35."""
    if not isinstance(student_number, str) or not _STUDENT_NUMBER.fullmatch(student_number):
        return "****-*****"
    year, sequence = student_number.split("-")
    return f"{year}-***{sequence[-2:]}"
