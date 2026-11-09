"""CSV export safety, shared by every export (Client_Export_Hardening_refactor.md F1).

A cell that starts with = + - @, tab or CR is run as a formula when a CSV is opened in a
spreadsheet (CSV injection, OWASP). Data cells get a leading apostrophe so they display as text.
Section markers and headers the app writes itself are not passed through this (RA1).
Pure: no imports from the app, unit-testable anywhere.
"""
from __future__ import annotations

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value) -> str:
    if value is None:
        return ""
    text = str(value)
    return "'" + text if text.startswith(_FORMULA_PREFIXES) else text


def safe_row(values) -> list:
    return [csv_safe(v) for v in values]
