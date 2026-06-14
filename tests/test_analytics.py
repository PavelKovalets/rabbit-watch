"""T2.9 — descriptive analytics aggregates and workbook (FR-6).

Aggregates take an explicit tz so assertions are deterministic regardless of the test
machine's local timezone (the CLI uses local time).
"""
from datetime import timezone

from src.brain.analytics import (
    build_workbook,
    dwell_stats,
    visits_by_hour,
    visits_per_day,
)


def rec(start_iso, dur):
    return {
        "start": start_iso, "end": start_iso, "duration_s": dur,
        "confidence": 0.9, "scene": "x", "snapshot": "a.jpg",
    }


RECORDS = [
    rec("2026-06-10T08:30:00+00:00", 60),
    rec("2026-06-10T08:45:00+00:00", 120),
    rec("2026-06-11T14:00:00+00:00", 30),
]


def test_visits_per_day():
    assert visits_per_day(RECORDS, tz=timezone.utc) == {"2026-06-10": 2, "2026-06-11": 1}


def test_visits_by_hour():
    h = visits_by_hour(RECORDS, tz=timezone.utc)
    assert h[8] == 2 and h[14] == 1 and h[0] == 0
    assert sum(h.values()) == 3


def test_dwell_stats():
    s = dwell_stats(RECORDS)
    assert s["count"] == 3
    assert s["mean"] == 70  # (60+120+30)/3
    assert s["median"] == 60
    assert s["max"] == 120


def test_dwell_stats_empty():
    assert dwell_stats([]) == {"count": 0, "mean": 0.0, "median": 0.0, "max": 0.0}


def test_handles_phase1_timestamp_field():
    # Old records used "timestamp" instead of "start"; aggregates still work.
    legacy = [{"timestamp": "2026-06-10T08:00:00+00:00", "confidence": 0.9}]
    assert visits_per_day(legacy, tz=timezone.utc) == {"2026-06-10": 1}


def test_build_workbook_sheets_and_save(tmp_path):
    wb = build_workbook(RECORDS, tz=timezone.utc)
    assert wb.sheetnames == ["Visits", "Per day", "By hour", "Summary"]
    assert wb["Visits"].max_row == 4  # header + 3 visits

    out = tmp_path / "report.xlsx"
    wb.save(out)
    assert out.exists() and out.stat().st_size > 0
