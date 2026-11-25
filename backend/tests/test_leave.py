"""Integration tests for Leave Management and attendance synchronization."""

from datetime import datetime, timedelta, timezone

from core.models import (
    AttendanceRecord,
    AttendanceStatus,
    LeaveStatus,
    ParadeSession,
    PresenceStatus,
)
from tests.conftest import auth_headers_for


def test_leave_submission_and_approval_flow(client, seed_data, db_session):
    cadet1 = seed_data["cadet1"]
    leader = seed_data["leader"]
    ano = seed_data["ano"]
    cadet_headers = auth_headers_for(cadet1)
    leader_headers = auth_headers_for(leader)
    ano_headers = auth_headers_for(ano)

    now = datetime.now(timezone.utc)
    start_date = now + timedelta(days=2)
    end_date = now + timedelta(days=5)

    # 1. Cadet submits leave request -> PENDING
    submit_res = client.post(
        "/leave",
        json={
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "reason": "Attending university semester examinations",
        },
        headers=cadet_headers,
    )
    assert submit_res.status_code == 201
    leave_id = submit_res.json()["id"]
    assert submit_res.json()["status"] == LeaveStatus.PENDING.value
    assert submit_res.json()["cadet_id"] == cadet1.id

    # 2. Leader reviews leave -> REVIEWED
    review_res = client.post(
        f"/leave/{leave_id}/review",
        json={"notes": "Exam datesheet verified by squad leader"},
        headers=leader_headers,
    )
    assert review_res.status_code == 200
    assert review_res.json()["status"] == LeaveStatus.REVIEWED.value
    assert review_res.json()["reviewed_by_id"] == leader.id

    # 3. Cadet cannot approve leave
    cadet_approve_res = client.post(
        f"/leave/{leave_id}/approve",
        headers=cadet_headers,
    )
    assert cadet_approve_res.status_code == 403

    # 4. ANO approves leave -> APPROVED
    approve_res = client.post(
        f"/leave/{leave_id}/approve",
        json={"notes": "Sanctioned official duty leave"},
        headers=ano_headers,
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == LeaveStatus.APPROVED.value
    assert approve_res.json()["approved_by_id"] == ano.id


def test_leave_attendance_synchronization(client, seed_data, db_session):
    cadet1 = seed_data["cadet1"]
    ano = seed_data["ano"]
    cadet_headers = auth_headers_for(cadet1)
    ano_headers = auth_headers_for(ano)

    now = datetime.now(timezone.utc)
    leave_start = now + timedelta(days=1)
    leave_end = now + timedelta(days=3)
    parade_date = now + timedelta(days=2)  # Falls within leave window

    # Pre-existing parade session scheduled during the leave window
    parade = ParadeSession(
        unit_id=cadet1.unit_id,
        squad_id=cadet1.squad_id,
        title="Scheduled Battalion Parade",
        date=parade_date,
        status=AttendanceStatus.DRAFT,
        created_by_id=ano.id,
    )
    db_session.add(parade)
    db_session.flush()

    # Cadet submits leave
    submit_res = client.post(
        "/leave",
        json={
            "start_date": leave_start.isoformat(),
            "end_date": leave_end.isoformat(),
            "reason": "Family medical emergency",
        },
        headers=cadet_headers,
    )
    leave_id = submit_res.json()["id"]

    # ANO approves leave directly
    approve_res = client.post(f"/leave/{leave_id}/approve", headers=ano_headers)
    assert approve_res.status_code == 200

    # Verify attendance record automatically synchronized to ON_LEAVE
    synced_record = (
        db_session.query(AttendanceRecord)
        .filter(
            AttendanceRecord.session_id == parade.id,
            AttendanceRecord.cadet_id == cadet1.id,
        )
        .first()
    )
    assert synced_record is not None
    assert synced_record.status == PresenceStatus.ON_LEAVE
    assert synced_record.remarks == "Approved Leave"


def test_leave_rejection_flow(client, seed_data):
    cadet1 = seed_data["cadet1"]
    leader = seed_data["leader"]
    cadet_headers = auth_headers_for(cadet1)
    leader_headers = auth_headers_for(leader)

    now = datetime.now(timezone.utc)
    submit_res = client.post(
        "/leave",
        json={
            "start_date": (now + timedelta(days=1)).isoformat(),
            "end_date": (now + timedelta(days=2)).isoformat(),
            "reason": "Personal errands",
        },
        headers=cadet_headers,
    )
    leave_id = submit_res.json()["id"]

    # Reject with mandatory reason
    reject_res = client.post(
        f"/leave/{leave_id}/reject",
        json={"rejection_reason": "Insufficient justification for missing camp preparation"},
        headers=leader_headers,
    )
    assert reject_res.status_code == 200
    assert reject_res.json()["status"] == LeaveStatus.REJECTED.value
    assert "Insufficient justification" in reject_res.json()["rejection_reason"]


def test_leave_scope_isolation(client, seed_data):
    cadet1 = seed_data["cadet1"]
    cadet2 = seed_data["cadet2"]  # Cadet2 is in Squad 2
    leader1 = seed_data["leader"]  # Leader is in Squad 1
    cadet1_headers = auth_headers_for(cadet1)
    cadet2_headers = auth_headers_for(cadet2)
    leader1_headers = auth_headers_for(leader1)

    now = datetime.now(timezone.utc)
    # Cadet2 submits leave
    submit_res = client.post(
        "/leave",
        json={
            "start_date": (now + timedelta(days=1)).isoformat(),
            "end_date": (now + timedelta(days=2)).isoformat(),
            "reason": "Medical appointment",
        },
        headers=cadet2_headers,
    )
    leave2_id = submit_res.json()["id"]

    # Cadet1 cannot view Cadet2's leave request
    get_res = client.get(f"/leave/{leave2_id}", headers=cadet1_headers)
    assert get_res.status_code == 403

    # Leader of Squad 1 cannot review leave for Cadet in Squad 2
    review_res = client.post(
        f"/leave/{leave2_id}/review",
        json={"notes": "Attempted cross-squad review"},
        headers=leader1_headers,
    )
    assert review_res.status_code == 403
