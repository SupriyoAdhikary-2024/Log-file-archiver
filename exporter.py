"""CSV export module for Log File Error Archiver.

Safely exports archived error records to CSV with CSV injection prevention.
"""

from __future__ import annotations

import csv
import io
from typing import Any, Dict, List, Sequence

# Characters that trigger spreadsheet formula execution when at the start of a cell
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_cell(value: Any) -> Any:
    """Sanitize string cells to prevent CSV formula injection (CSV Injection / CWE-1236).

    If the text starts with dangerous formula prefixes (=, +, -, @, tab, CR),
    prepend a single quote (') so spreadsheet applications treat it as raw text.
    """
    if isinstance(value, str):
        if value.startswith(FORMULA_PREFIXES):
            return f"'{value}"
    return value


def export_errors_to_csv(records: Sequence[Dict[str, Any]]) -> str:
    """Convert error records to safe CSV text.

    Args:
        records: Sequence of error record dictionaries.

    Returns:
        CSV-formatted string.
    """
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")

    # CSV Header
    headers = [
        "Record ID",
        "Occurred At",
        "Severity",
        "Message",
        "Line Number",
        "Source File",
        "Uploaded At",
    ]
    writer.writerow(headers)

    for rec in records:
        row = [
            rec.get("id", ""),
            sanitize_cell(rec.get("occurred_at", "")),
            sanitize_cell(rec.get("severity", "")),
            sanitize_cell(rec.get("message", "")),
            rec.get("line_number", ""),
            sanitize_cell(rec.get("source_file", "")),
            sanitize_cell(rec.get("uploaded_at", "")),
        ]
        writer.writerow(row)

    return output.getvalue()
