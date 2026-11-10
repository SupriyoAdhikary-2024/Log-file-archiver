"""Unit tests for log parser."""

import parser


def test_parse_valid_severities():
    line_err = "2026-11-10 10:01:00 ERROR Database connection failed"
    rec, status = parser.parse_line(line_err, 2)
    assert status == "ARCHIVED"
    assert rec == {
        "occurred_at": "2026-11-10 10:01:00",
        "severity": "ERROR",
        "message": "Database connection failed",
        "line_number": 2,
    }

    line_warn = "2026-11-10 10:02:00 WARNING High CPU usage"
    rec, status = parser.parse_line(line_warn, 3)
    assert status == "ARCHIVED"
    assert rec["severity"] == "WARNING"
    assert rec["message"] == "High CPU usage"

    line_crit = "2026-11-10 10:03:00 CRITICAL Server crashed"
    rec, status = parser.parse_line(line_crit, 4)
    assert status == "ARCHIVED"
    assert rec["severity"] == "CRITICAL"
    assert rec["message"] == "Server crashed"


def test_parse_ignored_severities():
    line_info = "2026-11-10 10:00:00 INFO Server started"
    rec, status = parser.parse_line(line_info, 1)
    assert status == "IGNORED"
    assert rec is None


def test_parse_blank_and_malformed_lines():
    rec, status = parser.parse_line("   ", 1)
    assert status == "BLANK"
    assert rec is None

    rec, status = parser.parse_line("Just a random traceback line without timestamp", 2)
    assert status == "MALFORMED"
    assert rec is None


def test_sample_file_contract():
    sample_lines = [
        "2026-11-10 10:00:00 INFO Server started",
        "2026-11-10 10:01:00 ERROR Database connection failed",
        "2026-11-10 10:02:00 WARNING High CPU usage",
        "2026-11-10 10:03:00 CRITICAL Server crashed",
        "2026-11-10 10:04:00 INFO Server restarted",
        "2026-11-10 10:05:00 ERROR Login failed",
    ]

    result = parser.parse_file(sample_lines)

    assert result["total_lines"] == 6
    assert result["archived_count"] == 4
    assert result["ignored_count"] == 2
    assert result["malformed_count"] == 0
    assert result["blank_count"] == 0

    severities = [r["severity"] for r in result["archived_records"]]
    assert severities == ["ERROR", "WARNING", "CRITICAL", "ERROR"]

    line_numbers = [r["line_number"] for r in result["archived_records"]]
    assert line_numbers == [2, 3, 4, 6]


def test_empty_file():
    result = parser.parse_file([])
    assert result["total_lines"] == 0
    assert result["archived_count"] == 0
    assert result["archived_records"] == []
