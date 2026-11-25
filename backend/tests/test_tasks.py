"""Integration tests for Task lifecycle, review, and scope enforcement."""

from datetime import datetime, timedelta, timezone

from core.models import AuditLog, TaskStatus
from tests.conftest import auth_headers_for


def test_task_full_lifecycle(client, seed_data, db_session):
    leader = seed_data["leader"]
    cadet1 = seed_data["cadet1"]
    leader_headers = auth_headers_for(leader)
    cadet_headers = auth_headers_for(cadet1)

    now = datetime.now(timezone.utc)
    due_date = now + timedelta(days=3)

    # 1. Leader creates and assigns task to Cadet1 -> ASSIGNED
    create_res = client.post(
        "/tasks",
        json={
            "title": "Prepare Drill Ground Inspection Report",
            "description": "Inspect ground flags and drill markers for battalion parade.",
            "due_date": due_date.isoformat(),
            "squad_id": seed_data["squad1"].id,
            "assignee_id": cadet1.id,
        },
        headers=leader_headers,
    )
    assert create_res.status_code == 201
    task_id = create_res.json()["id"]
    assert create_res.json()["status"] == TaskStatus.ASSIGNED.value

    # 2. Cadet marks task IN_PROGRESS
    prog_res = client.patch(
        f"/tasks/{task_id}",
        json={"status": TaskStatus.IN_PROGRESS.value},
        headers=cadet_headers,
    )
    assert prog_res.status_code == 200
    assert prog_res.json()["status"] == TaskStatus.IN_PROGRESS.value

    # 3. Cadet submits completed work -> SUBMITTED
    submit_res = client.post(
        f"/tasks/{task_id}/submit",
        json={"submission_text": "Ground markers painted and inspection report attached."},
        headers=cadet_headers,
    )
    expected_sub = "Ground markers painted and inspection report attached."
    assert submit_res.status_code == 200
    assert submit_res.json()["status"] == TaskStatus.SUBMITTED.value
    assert submit_res.json()["submission_text"] == expected_sub

    # 4. Cadet cannot review own task
    cadet_review = client.post(
        f"/tasks/{task_id}/review",
        json={"status": TaskStatus.COMPLETED.value, "feedback": "Self-approved"},
        headers=cadet_headers,
    )
    assert cadet_review.status_code == 403

    # 5. Leader reviews and approves work -> COMPLETED
    review_res = client.post(
        f"/tasks/{task_id}/review",
        json={
            "status": TaskStatus.COMPLETED.value,
            "feedback": "Inspection completed to standard.",
        },
        headers=leader_headers,
    )
    assert review_res.status_code == 200
    assert review_res.json()["status"] == TaskStatus.COMPLETED.value
    assert review_res.json()["feedback"] == "Inspection completed to standard."

    # 6. Verify audit logs recorded the lifecycle
    audits = (
        db_session.query(AuditLog)
        .filter(AuditLog.resource_type == "Task", AuditLog.resource_id == str(task_id))
        .all()
    )
    actions = [a.action for a in audits]
    assert "TASK_CREATED" in actions
    assert "TASK_UPDATED" in actions
    assert "TASK_SUBMITTED" in actions
    assert "TASK_REVIEWED" in actions


def test_task_rejection_with_feedback(client, seed_data):
    leader_headers = auth_headers_for(seed_data["leader"])
    cadet_headers = auth_headers_for(seed_data["cadet1"])

    now = datetime.now(timezone.utc)
    task = client.post(
        "/tasks",
        json={
            "title": "Equipment Inventory",
            "description": "Count and verify webbing sets.",
            "due_date": (now + timedelta(days=2)).isoformat(),
            "assignee_id": seed_data["cadet1"].id,
        },
        headers=leader_headers,
    ).json()

    # Submit task
    client.post(
        f"/tasks/{task['id']}/submit",
        json={"submission_text": "Incomplete counts."},
        headers=cadet_headers,
    )

    # Leader reviews with rejection
    review_res = client.post(
        f"/tasks/{task['id']}/review",
        json={
            "status": TaskStatus.REJECTED.value,
            "feedback": "Recount webbing buckles and re-submit.",
        },
        headers=leader_headers,
    )
    assert review_res.status_code == 200
    assert review_res.json()["status"] == TaskStatus.REJECTED.value
    assert "Recount webbing" in review_res.json()["feedback"]


def test_leader_cannot_assign_task_to_other_squad_cadet(client, seed_data):
    leader = seed_data["leader"]  # Squad 1
    cadet2 = seed_data["cadet2"]  # Squad 2
    leader_headers = auth_headers_for(leader)

    now = datetime.now(timezone.utc)
    res = client.post(
        "/tasks",
        json={
            "title": "Cross-squad task",
            "description": "Unauthorized assignment",
            "due_date": (now + timedelta(days=1)).isoformat(),
            "assignee_id": cadet2.id,
        },
        headers=leader_headers,
    )
    assert res.status_code == 403
