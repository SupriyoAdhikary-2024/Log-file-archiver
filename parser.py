"""Log parser module for Log File Error Archiver.

Parses timestamped log files formatted as:
YYYY-MM-DD HH:MM:SS LEVEL message
Extracts WARNING, ERROR, and CRITICAL severity entries.
"""

from __future__ import annotations

import re
from typing import IO, Any, Dict, List, Optional, Tuple

LOG_LINE_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+([A-Z]+)\s*(.*)$"
)

ARCHIVE_SEVERITIES = {"WARNING", "ERROR", "CRITICAL"}
KNOWN_IGNORED_SEVERITIES = {"INFO", "DEBUG", "TRACE", "NOTICE"}


def parse_line(line: str, line_number: int) -> Tuple[Optional[Dict[str, Any]], str]:
    """Parse a single log line.

    Args:
        line: Raw line string from file.
        line_number: 1-indexed line number.

    Returns:
        A tuple of (record, status):
          - record: Dict containing occurred_at, severity, message, line_number
                    if archive-worthy, or None.
          - status: One of 'ARCHIVED', 'IGNORED', 'BLANK', 'MALFORMED'.
    """
    stripped = line.strip()
    if not stripped:
        return None, "BLANK"

    match = LOG_LINE_PATTERN.match(stripped)
    if not match:
        return None, "MALFORMED"

    timestamp, severity, message = match.groups()

    if severity in ARCHIVE_SEVERITIES:
        return {
            "occurred_at": timestamp,
            "severity": severity,
            "message": message,
            "line_number": line_number,
        }, "ARCHIVED"

    return None, "IGNORED"


def parse_file(file_stream: IO[str] | list[str]) -> Dict[str, Any]:
    """Parse a file stream or iterable of strings.

    Args:
        file_stream: Iterable stream of strings.

    Returns:
        Dict with total_lines, archived_records, archived_count,
        ignored_count, malformed_count, blank_count.
    """
    archived_records: List[Dict[str, Any]] = []
    total_lines = 0
    ignored_count = 0
    malformed_count = 0
    blank_count = 0

    for line_number, raw_line in enumerate(file_stream, start=1):
        total_lines += 1
        record, status = parse_line(raw_line, line_number)

        if status == "ARCHIVED" and record is not None:
            archived_records.append(record)
        elif status == "IGNORED":
            ignored_count += 1
        elif status == "BLANK":
            blank_count += 1
        elif status == "MALFORMED":
            malformed_count += 1

    return {
        "total_lines": total_lines,
        "archived_records": archived_records,
        "archived_count": len(archived_records),
        "ignored_count": ignored_count,
        "malformed_count": malformed_count,
        "blank_count": blank_count,
    }
