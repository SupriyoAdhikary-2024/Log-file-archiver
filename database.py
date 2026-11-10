"""Database repository layer for Log File Error Archiver.

Manages SQLite schema, upload tracking, error archiving, and querying.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class DuplicateUploadError(Exception):
    """Raised when an uploaded file hash already exists in the database."""


def get_connection(db_path: str) -> sqlite3.Connection:
    """Create a connection configured with row factory and foreign keys."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: str = "archiver.db") -> None:
    """Initialize SQLite database tables and indexes."""
    with get_connection(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                uploaded_at TEXT NOT NULL,
                file_hash TEXT NOT NULL UNIQUE,
                total_lines INTEGER NOT NULL,
                archived_count INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                upload_id INTEGER NOT NULL,
                occurred_at TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                line_number INTEGER NOT NULL,
                FOREIGN KEY (upload_id) REFERENCES uploads(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_errors_severity ON errors(severity);
            CREATE INDEX IF NOT EXISTS idx_errors_occurred_at ON errors(occurred_at DESC);
            CREATE INDEX IF NOT EXISTS idx_errors_upload_id ON errors(upload_id);
            """
        )


def save_upload(
    db_path: str,
    filename: str,
    file_hash: str,
    total_lines: int,
    archived_records: List[Dict[str, Any]],
) -> int:
    """Save an upload and all its archived records within a single transaction.

    Args:
        db_path: Path to SQLite DB.
        filename: Original display name of the uploaded file.
        file_hash: SHA-256 hash of the uploaded file.
        total_lines: Total lines processed.
        archived_records: List of parsed error record dictionaries.

    Returns:
        The newly created upload_id.

    Raises:
        DuplicateUploadError: If file_hash already exists in uploads table.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # Check for duplicate
        cursor.execute("SELECT id FROM uploads WHERE file_hash = ?", (file_hash,))
        if cursor.fetchone() is not None:
            raise DuplicateUploadError(
                f"An identical file has already been uploaded (hash: {file_hash})."
            )

        uploaded_at = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            """
            INSERT INTO uploads (filename, uploaded_at, file_hash, total_lines, archived_count)
            VALUES (?, ?, ?, ?, ?)
            """,
            (filename, uploaded_at, file_hash, total_lines, len(archived_records)),
        )
        upload_id = cursor.lastrowid
        assert upload_id is not None

        if archived_records:
            cursor.executemany(
                """
                INSERT INTO errors (upload_id, occurred_at, severity, message, line_number)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        upload_id,
                        rec["occurred_at"],
                        rec["severity"],
                        rec["message"],
                        rec["line_number"],
                    )
                    for rec in archived_records
                ],
            )

        return int(upload_id)


def _build_filter_clause(
    severity: Optional[str] = None, q: Optional[str] = None
) -> Tuple[str, List[Any]]:
    """Build WHERE clause and parameter list for queries."""
    conditions = []
    params: List[Any] = []

    if severity and severity.upper() in {"WARNING", "ERROR", "CRITICAL"}:
        conditions.append("e.severity = ?")
        params.append(severity.upper())

    if q and q.strip():
        search_pattern = f"%{q.strip()}%"
        conditions.append("(e.message LIKE ? OR u.filename LIKE ?)")
        params.extend([search_pattern, search_pattern])

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return where_clause, params


def get_errors(
    db_path: str,
    severity: Optional[str] = None,
    q: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """Retrieve paginated errors with optional severity and search filters."""
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    offset = (page - 1) * page_size

    where_clause, params = _build_filter_clause(severity, q)

    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        count_sql = f"""
            SELECT COUNT(*) AS total
            FROM errors e
            JOIN uploads u ON e.upload_id = u.id
            {where_clause}
        """
        cursor.execute(count_sql, params)
        total_records = cursor.fetchone()["total"]

        total_pages = (total_records + page_size - 1) // page_size if total_records > 0 else 1

        select_sql = f"""
            SELECT
                e.id,
                e.upload_id,
                e.occurred_at,
                e.severity,
                e.message,
                e.line_number,
                u.filename AS source_file,
                u.uploaded_at
            FROM errors e
            JOIN uploads u ON e.upload_id = u.id
            {where_clause}
            ORDER BY e.occurred_at DESC, e.id DESC
            LIMIT ? OFFSET ?
        """
        cursor.execute(select_sql, params + [page_size, offset])
        records = [dict(row) for row in cursor.fetchall()]

    return {
        "records": records,
        "page": page,
        "page_size": page_size,
        "total_records": total_records,
        "total_pages": total_pages,
    }


def get_all_filtered_errors_for_export(
    db_path: str,
    severity: Optional[str] = None,
    q: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Fetch all matching records (unpaginated) for CSV export."""
    where_clause, params = _build_filter_clause(severity, q)

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        select_sql = f"""
            SELECT
                e.id,
                e.occurred_at,
                e.severity,
                e.message,
                e.line_number,
                u.filename AS source_file,
                u.uploaded_at
            FROM errors e
            JOIN uploads u ON e.upload_id = u.id
            {where_clause}
            ORDER BY e.occurred_at DESC, e.id DESC
        """
        cursor.execute(select_sql, params)
        return [dict(row) for row in cursor.fetchall()]


def get_stats(db_path: str) -> Dict[str, Any]:
    """Get counts by severity and overall upload summary."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                severity,
                COUNT(*) as count
            FROM errors
            GROUP BY severity
            """
        )
        counts = {"WARNING": 0, "ERROR": 0, "CRITICAL": 0}
        total_errors = 0
        for row in cursor.fetchall():
            sev = row["severity"]
            cnt = row["count"]
            if sev in counts:
                counts[sev] = cnt
            total_errors += cnt

        cursor.execute("SELECT COUNT(*) AS total_uploads FROM uploads")
        total_uploads = cursor.fetchone()["total_uploads"]

        return {
            "by_severity": counts,
            "total_errors": total_errors,
            "total_uploads": total_uploads,
        }
