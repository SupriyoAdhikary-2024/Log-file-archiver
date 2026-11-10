"""Flask application for Log File Error Archiver.

Provides web dashboard and REST API for log uploading, error filtering,
severity analytics, and CSV exporting.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from flask import (
    Flask,
    Response,
    jsonify,
    render_template,
    request,
)
from werkzeug.exceptions import RequestEntityTooLarge

import database
import exporter
import parser

MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB
ALLOWED_EXTENSIONS = {".log", ".txt"}


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE
    app.config["DB_PATH"] = os.environ.get("DB_PATH", "archiver.db")

    if test_config:
        app.config.update(test_config)

    # Ensure DB is initialized
    database.init_db(app.config["DB_PATH"])

    @app.errorhandler(RequestEntityTooLarge)
    def handle_file_too_large(error: Any) -> tuple[Response, int]:
        return jsonify({"error": "File size exceeds the 2 MB limit."}), 413

    @app.errorhandler(400)
    def handle_bad_request(error: Any) -> tuple[Response, int]:
        return jsonify({"error": "Bad request."}), 400

    @app.errorhandler(404)
    def handle_not_found(error: Any) -> tuple[Response, int]:
        return jsonify({"error": "Resource not found."}), 404

    @app.errorhandler(500)
    def handle_server_error(error: Any) -> tuple[Response, int]:
        return jsonify({"error": "An internal server error occurred."}), 500

    @app.route("/")
    def index() -> str:
        return render_template("index.html")

    @app.route("/api/uploads", methods=["POST"])
    def upload_file() -> tuple[Response, int]:
        if "file" not in request.files:
            return jsonify({"error": "No file field in request."}), 400

        file_storage = request.files["file"]
        if not file_storage or not file_storage.filename:
            return jsonify({"error": "No file selected."}), 400

        # Validate extension
        raw_filename = file_storage.filename
        file_ext = Path(raw_filename).suffix.lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            return (
                jsonify(
                    {
                        "error": f"Invalid file extension '{file_ext}'. Only .log and .txt are supported."
                    }
                ),
                400,
            )

        # Read content
        file_bytes = file_storage.read()

        # Check file size
        if len(file_bytes) > MAX_FILE_SIZE:
            return jsonify({"error": "File size exceeds the 2 MB limit."}), 413

        if len(file_bytes) == 0:
            return jsonify({"error": "Uploaded file is empty."}), 400

        # Validate UTF-8 encoding
        try:
            content_str = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return (
                jsonify(
                    {"error": "File encoding invalid. The file must be valid UTF-8 text."}
                ),
                400,
            )

        # Compute SHA-256 for deduplication
        file_hash = hashlib.sha256(file_bytes).hexdigest()

        # Parse log content
        lines = content_str.splitlines()
        parsed_result = parser.parse_file(lines)

        # Sanitize display filename (prevent path traversal / overly long filenames)
        display_name = Path(raw_filename).name[:255]

        # Save to database
        db_path = app.config["DB_PATH"]
        try:
            upload_id = database.save_upload(
                db_path=db_path,
                filename=display_name,
                file_hash=file_hash,
                total_lines=parsed_result["total_lines"],
                archived_records=parsed_result["archived_records"],
            )
        except database.DuplicateUploadError:
            return (
                jsonify(
                    {
                        "error": "This file has already been uploaded and archived.",
                        "file_hash": file_hash,
                    }
                ),
                409,
            )

        return (
            jsonify(
                {
                    "upload_id": upload_id,
                    "filename": display_name,
                    "total_lines": parsed_result["total_lines"],
                    "archived_count": parsed_result["archived_count"],
                    "ignored_count": parsed_result["ignored_count"],
                    "malformed_count": parsed_result["malformed_count"],
                }
            ),
            201,
        )

    @app.route("/api/errors", methods=["GET"])
    def list_errors() -> Response:
        severity = request.args.get("severity", type=str)
        q = request.args.get("q", type=str)
        page = request.args.get("page", default=1, type=int)
        page_size = request.args.get("page_size", default=15, type=int)

        db_path = app.config["DB_PATH"]
        data = database.get_errors(
            db_path=db_path,
            severity=severity,
            q=q,
            page=page,
            page_size=page_size,
        )
        return jsonify(data)

    @app.route("/api/stats", methods=["GET"])
    def get_stats() -> Response:
        db_path = app.config["DB_PATH"]
        stats = database.get_stats(db_path=db_path)
        return jsonify(stats)

    @app.route("/api/export", methods=["GET"])
    def export_csv() -> Response:
        severity = request.args.get("severity", type=str)
        q = request.args.get("q", type=str)

        db_path = app.config["DB_PATH"]
        records = database.get_all_filtered_errors_for_export(
            db_path=db_path, severity=severity, q=q
        )
        csv_content = exporter.export_errors_to_csv(records)

        return Response(
            csv_content,
            mimetype="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="error_archive_export.csv"',
                "Content-Type": "text/csv; charset=utf-8",
            },
        )

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
