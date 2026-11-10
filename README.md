# Log File Error Archiver

A production-ready web application built with Python (Flask), SQLite, and JavaScript (Chart.js) that allows developers, testers, and teams to upload `.log` and `.txt` files, automatically parse timestamped entries, extract archive-worthy alerts (`WARNING`, `ERROR`, and `CRITICAL`), and explore them through an interactive dashboard and filtered CSV export.

---

## Features

- **File Upload & Validation**: Accepts UTF-8 encoded `.log` and `.txt` files up to 2 MB. Validates file size, file extension, and UTF-8 encoding.
- **Deduplication**: Calculates SHA-256 hash on file upload to prevent duplicate processing (HTTP `409 Conflict`).
- **Precision Log Parsing**: Accurately extracts `YYYY-MM-DD HH:MM:SS LEVEL message` entries, capturing line numbers and severities (`WARNING`, `ERROR`, `CRITICAL`), while ignoring `INFO` and blank lines.
- **Persistent Local Database**: Uses SQLite with relational foreign keys and indices for high-performance sorting and retrieval.
- **Interactive Dashboard**:
  - Live severity distribution breakdown with Chart.js doughnut visualization.
  - Interactive stat counters that act as quick filters.
  - Full-text keyword search and severity dropdown filter.
  - Server-side pagination with newest-first ordering.
  - Drag-and-drop file upload zone with instant feedback.
- **Safe CSV Export**: Exports filtered search results to CSV with formula injection prevention (CWE-1236 mitigation).
- **Comprehensive Automated Test Suite**: Built-in unit and integration tests using `pytest`.

---

## Project Structure

```text
log-error-archiver/
├── app.py                  # Flask application & API routes
├── parser.py               # Log line and file parsing engine
├── database.py             # SQLite schema & database queries
├── exporter.py             # CSV export with formula injection sanitization
├── requirements.txt        # Python package dependencies
├── pytest.ini              # Pytest configuration
├── .gitignore              # Git ignore rules for virtual environments, db, logs
├── README.md               # Documentation & setup guide
├── sample_logs/
│   └── sample.log          # 6-line sample file for validation & demos
├── templates/
│   └── index.html          # Web dashboard markup
├── static/
│   ├── style.css           # Modern, responsive CSS styling
│   └── app.js              # Client logic, Chart.js & AJAX requests
└── tests/
    ├── test_parser.py      # Parser unit tests
    └── test_upload.py      # Endpoints, upload validation & CSV tests
```

---

## Quickstart & Local Setup

### 1. Prerequisites
- Python 3.11+
- Git

### 2. Clone and Setup Environment

```powershell
# In PowerShell:
git clone <repo-url>
cd log-error-archiver

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

*(On macOS/Linux, activate using `source .venv/bin/activate`)*

### 3. Run the Application

```powershell
python app.py
```

Open your browser and navigate to **[http://localhost:5000](http://localhost:5000)**.

### 4. Run the Test Suite

```powershell
pytest -v
```

All 14 tests verify parser contracts, upload validations, status codes, query filtering, and CSV safety.

---

## API Contract

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serves dashboard UI (`templates/index.html`) |
| `POST` | `/api/uploads` | Uploads log file (`multipart/form-data`, field `file`). Returns 201 on success, 400 on invalid format/encoding, 409 on duplicate file, 413 on file > 2 MB. |
| `GET` | `/api/errors` | Retrieves paginated errors (`severity`, `q`, `page`, `page_size`). |
| `GET` | `/api/stats` | Retrieves count totals and severity breakdown. |
| `GET` | `/api/export` | Downloads CSV export of errors matching current active filters. |

### Upload Response Example
```json
{
  "upload_id": 1,
  "filename": "sample.log",
  "total_lines": 6,
  "archived_count": 4,
  "ignored_count": 2,
  "malformed_count": 0
}
```

---

## Demo Script

1. Open the dashboard at `http://localhost:5000`.
2. Drag and drop `sample_logs/sample.log` into the upload drop-zone.
3. Observe:
   - Success notification shows: 6 lines processed, 4 archived, 2 ignored.
   - Severity counters update: 1 Critical, 2 Error, 1 Warning.
   - The doughnut chart updates visually.
   - The table renders the 4 archived entries with timestamp, severity badge, message, filename, and line numbers.
4. Try filtering by **CRITICAL** or typing a keyword like `Database` in the search box.
5. Click **Export CSV** to download the currently filtered view.
6. Attempt to re-upload the same file; notice the duplicate upload prevention (HTTP 409).
7. Restart the Flask app; notice all data persists seamlessly from SQLite.

---

## Deployment (Render)

1. Commit and push the repository to GitHub:
   ```bash
   git add .
   git commit -m "Initial complete release of Log File Error Archiver"
   git push origin main
   ```
2. In the [Render Dashboard](https://dashboard.render.com/):
   - Create a new **Web Service**.
   - Connect your GitHub repository.
   - Set **Runtime** to `Python 3`.
   - Set **Build Command** to: `pip install -r requirements.txt`
   - Set **Start Command** to: `gunicorn app:app`
3. *Note on SQLite Persistence:* SQLite files on ephemeral cloud filesystems reset upon redeployment. For production persistent cloud storage, mount a persistent disk or connect to managed PostgreSQL.

---

## Team Roles

- **Member 1 (Parser & Unit Tests)**: `parser.py`, `tests/test_parser.py`
- **Member 2 (Flask Routes & Validation)**: `app.py`, `tests/test_upload.py`
- **Member 3 (Database & Exporter)**: `database.py`, `exporter.py`
- **Member 4 (UI, Integration, & Deployment)**: `templates/`, `static/`, `README.md`, deployment config
