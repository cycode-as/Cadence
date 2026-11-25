"""Integration tests for Reports and CSV Export."""

from datetime import datetime, timezone

from core.models import AttendanceRecord, AttendanceStatus, ParadeSession, PresenceStatus
from tests.conftest import auth_headers_for


def test_attendance_and_leave_reports(client, seed_data, db_session):
    ano_headers = auth_headers_for(seed_data["ano"])
    cadet1 = seed_data["cadet1"]

    # Seed an attendance record
    parade = ParadeSession(
        unit_id=seed_data["unit"].id,
        squad_id=seed_data["squad1"].id,
        title="Battalion Drill",
        date=datetime.now(timezone.utc),
        status=AttendanceStatus.ANO_APPROVED,
        created_by_id=seed_data["ano"].id,
    )
    db_session.add(parade)
    db_session.flush()

    record = AttendanceRecord(
        session_id=parade.id,
        cadet_id=cadet1.id,
        status=PresenceStatus.PRESENT,
        recorded_by_id=seed_data["ano"].id,
    )
    db_session.add(record)
    db_session.flush()

    # 1. Fetch attendance report
    att_res = client.get("/reports/attendance", headers=ano_headers)
    assert att_res.status_code == 200
    att_data = att_res.json()
    assert att_data["total_records"] >= 1
    assert att_data["present_count"] >= 1
    assert "squad_summaries" in att_data

    # 2. Fetch leave report
    leave_res = client.get("/reports/leave", headers=ano_headers)
    assert leave_res.status_code == 200
    leave_data = leave_res.json()
    assert "total_requests" in leave_data
    assert "approved_count" in leave_data

    # 3. Fetch participation report
    part_res = client.get("/reports/participation", headers=ano_headers)
    assert part_res.status_code == 200
    part_data = part_res.json()
    assert part_data["total_cadets"] >= 1
    assert len(part_data["cadets"]) >= 1


def test_attendance_csv_export(client, seed_data, db_session):
    ano_headers = auth_headers_for(seed_data["ano"])
    cadet1 = seed_data["cadet1"]

    # Ensure attendance record exists
    parade = ParadeSession(
        unit_id=seed_data["unit"].id,
        squad_id=seed_data["squad1"].id,
        title="Morning Drill for CSV",
        date=datetime.now(timezone.utc),
        status=AttendanceStatus.ANO_APPROVED,
        created_by_id=seed_data["ano"].id,
    )
    db_session.add(parade)
    db_session.flush()

    record = AttendanceRecord(
        session_id=parade.id,
        cadet_id=cadet1.id,
        status=PresenceStatus.PRESENT,
        remarks="Full kit inspected",
        recorded_by_id=seed_data["ano"].id,
    )
    db_session.add(record)
    db_session.flush()

    csv_res = client.get("/reports/attendance/export", headers=ano_headers)
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers["content-type"]
    assert "attachment; filename=" in csv_res.headers["content-disposition"]

    csv_text = csv_res.text
    header = "Parade Title,Date,Cadet Regt Number,Cadet Name,Squad,Attendance Status,Remarks"
    assert header in csv_text
    assert "Morning Drill for CSV" in csv_text
    assert cadet1.full_name in csv_text
    assert "Full kit inspected" in csv_text
