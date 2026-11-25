"""Integration tests for Attendance lifecycle and scope rules."""

from datetime import datetime, timezone

from core.models import AttendanceStatus, AuditLog, PresenceStatus
from tests.conftest import auth_headers_for


def test_attendance_complete_lifecycle(client, seed_data, db_session):
    ano = seed_data["ano"]
    juo = seed_data["juo"]
    leader = seed_data["leader"]
    cadet1 = seed_data["cadet1"]
    ano_headers = auth_headers_for(ano)
    juo_headers = auth_headers_for(juo)
    leader_headers = auth_headers_for(leader)

    # 1. Create parade (ANO) -> DRAFT
    create_res = client.post(
        "/attendance/parades",
        json={
            "title": "Morning Drill Session",
            "date": datetime.now(timezone.utc).isoformat(),
            "squad_id": seed_data["squad1"].id,
        },
        headers=ano_headers,
    )
    assert create_res.status_code == 201
    parade_id = create_res.json()["id"]
    assert create_res.json()["status"] == AttendanceStatus.DRAFT.value

    # 2. Leader submits squad attendance -> SUBMITTED
    submit_res = client.post(
        f"/attendance/{parade_id}/submit",
        json={
            "squad_id": seed_data["squad1"].id,
            "records": [
                {
                    "cadet_id": cadet1.id,
                    "status": PresenceStatus.PRESENT.value,
                    "remarks": "On time in proper kit",
                }
            ],
        },
        headers=leader_headers,
    )
    assert submit_res.status_code == 200
    assert submit_res.json()["status"] == AttendanceStatus.SUBMITTED.value
    assert len(submit_res.json()["records"]) == 1

    # 3. JUO reviews attendance -> JUO_REVIEWED
    review_res = client.post(
        f"/attendance/{parade_id}/review",
        json={"notes": "Reviewed and verified uniform turnout"},
        headers=juo_headers,
    )
    assert review_res.status_code == 200
    assert review_res.json()["status"] == AttendanceStatus.JUO_REVIEWED.value

    # 4. ANO approves attendance -> ANO_APPROVED
    approve_res = client.post(
        f"/attendance/{parade_id}/approve",
        json={"notes": "Approved for battalion records"},
        headers=ano_headers,
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == AttendanceStatus.ANO_APPROVED.value

    # 5. Lock attendance -> LOCKED
    lock_res = client.post(
        f"/attendance/{parade_id}/lock",
        headers=ano_headers,
    )
    assert lock_res.status_code == 200
    assert lock_res.json()["status"] == AttendanceStatus.LOCKED.value

    # 6. Verify audit logs were created in the database for state transitions
    audits = (
        db_session.query(AuditLog)
        .filter(AuditLog.resource_id == str(parade_id))
        .all()
    )
    actions = [a.action for a in audits]
    assert "ATTENDANCE_SESSION_CREATED" in actions
    assert "ATTENDANCE_SUBMITTED" in actions
    assert "ATTENDANCE_REVIEWED" in actions
    assert "ATTENDANCE_APPROVED" in actions
    assert "ATTENDANCE_LOCKED" in actions


def test_cadet_cannot_create_parade(client, seed_data):
    cadet1 = seed_data["cadet1"]
    cadet_headers = auth_headers_for(cadet1)

    response = client.post(
        "/attendance/parades",
        json={
            "title": "Unauthorized Cadet Drill",
            "date": datetime.now(timezone.utc).isoformat(),
        },
        headers=cadet_headers,
    )
    assert response.status_code == 403


def test_leader_cannot_submit_other_squad_cadet(client, seed_data):
    leader = seed_data["leader"]  # Assigned to squad1
    cadet2 = seed_data["cadet2"]  # Belongs to squad2
    leader_headers = auth_headers_for(leader)
    ano_headers = auth_headers_for(seed_data["ano"])

    create_res = client.post(
        "/attendance/parades",
        json={
            "title": "Squad 1 Parade",
            "date": datetime.now(timezone.utc).isoformat(),
            "squad_id": seed_data["squad1"].id,
        },
        headers=ano_headers,
    )
    parade_id = create_res.json()["id"]

    submit_res = client.post(
        f"/attendance/{parade_id}/submit",
        json={
            "squad_id": seed_data["squad1"].id,
            "records": [
                {
                    "cadet_id": cadet2.id,
                    "status": PresenceStatus.PRESENT.value,
                }
            ],
        },
        headers=leader_headers,
    )
    assert submit_res.status_code == 403


def test_duplicate_cadet_attendance_rejected(client, seed_data):
    leader = seed_data["leader"]
    cadet1 = seed_data["cadet1"]
    leader_headers = auth_headers_for(leader)
    ano_headers = auth_headers_for(seed_data["ano"])

    create_res = client.post(
        "/attendance/parades",
        json={
            "title": "Morning Drill",
            "date": datetime.now(timezone.utc).isoformat(),
            "squad_id": seed_data["squad1"].id,
        },
        headers=ano_headers,
    )
    parade_id = create_res.json()["id"]

    # First submit
    client.post(
        f"/attendance/{parade_id}/submit",
        json={
            "squad_id": seed_data["squad1"].id,
            "records": [{"cadet_id": cadet1.id, "status": PresenceStatus.PRESENT.value}],
        },
        headers=leader_headers,
    )

    # Duplicate submit for same cadet in same parade
    dup_res = client.post(
        f"/attendance/{parade_id}/submit",
        json={
            "squad_id": seed_data["squad1"].id,
            "records": [{"cadet_id": cadet1.id, "status": PresenceStatus.ABSENT.value}],
        },
        headers=leader_headers,
    )
    assert dup_res.status_code == 400
    assert "Duplicate attendance record" in dup_res.json()["detail"]


def test_record_correction_with_mandatory_audit_reason(client, seed_data, db_session):
    ano = seed_data["ano"]
    leader = seed_data["leader"]
    cadet1 = seed_data["cadet1"]
    ano_headers = auth_headers_for(ano)
    leader_headers = auth_headers_for(leader)

    # Setup parade and submit
    parade = client.post(
        "/attendance/parades",
        json={"title": "Parade", "date": datetime.now(timezone.utc).isoformat()},
        headers=ano_headers,
    ).json()

    submit_res = client.post(
        f"/attendance/{parade['id']}/submit",
        json={
            "records": [{"cadet_id": cadet1.id, "status": PresenceStatus.ABSENT.value}],
        },
        headers=leader_headers,
    )
    record_id = submit_res.json()["records"][0]["id"]

    # Correct record to ON_LEAVE with mandatory reason
    correct_res = client.patch(
        f"/attendance/{parade['id']}/records/{record_id}",
        json={
            "status": PresenceStatus.ON_LEAVE.value,
            "reason": "Cadet had sanctioned medical leave with certificate",
            "remarks": "Medical certificate verified by ANO",
        },
        headers=ano_headers,
    )
    assert correct_res.status_code == 200
    assert correct_res.json()["status"] == PresenceStatus.ON_LEAVE.value

    # Verify audit trail captured the change
    audit = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.resource_type == "AttendanceRecord",
            AuditLog.resource_id == str(record_id),
        )
        .first()
    )
    assert audit is not None
    assert audit.action == "ATTENDANCE_RECORD_CORRECTED"
    assert audit.previous_state == PresenceStatus.ABSENT.value
    assert audit.new_state == PresenceStatus.ON_LEAVE.value
    assert "medical leave" in audit.reason


def test_cadet_sees_only_own_record(client, seed_data):
    ano_headers = auth_headers_for(seed_data["ano"])
    cadet1_headers = auth_headers_for(seed_data["cadet1"])

    parade = client.post(
        "/attendance/parades",
        json={"title": "Battalion Parade", "date": datetime.now(timezone.utc).isoformat()},
        headers=ano_headers,
    ).json()

    # Submit records for cadet1 and cadet2
    client.post(
        f"/attendance/{parade['id']}/submit",
        json={
            "records": [
                {"cadet_id": seed_data["cadet1"].id, "status": PresenceStatus.PRESENT.value},
                {"cadet_id": seed_data["cadet2"].id, "status": PresenceStatus.ABSENT.value},
            ],
        },
        headers=ano_headers,
    )

    # Cadet1 inspects parade detail
    detail = client.get(f"/attendance/parades/{parade['id']}", headers=cadet1_headers).json()
    assert len(detail["records"]) == 1
    assert detail["records"][0]["cadet_id"] == seed_data["cadet1"].id
