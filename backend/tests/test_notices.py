"""Integration tests for Notices publication and scope isolation."""


from core.models import AuditLog
from tests.conftest import auth_headers_for


def test_notice_creation_and_visibility(client, seed_data, db_session):
    ano = seed_data["ano"]
    cadet1 = seed_data["cadet1"]
    ano_headers = auth_headers_for(ano)
    cadet_headers = auth_headers_for(cadet1)

    # 1. ANO creates unit-wide notice
    res = client.post(
        "/notices",
        json={
            "title": "Annual Training Camp 2026 Announcement",
            "content": "All cadets must submit camp willingness forms by Friday.",
            "is_published": True,
        },
        headers=ano_headers,
    )
    assert res.status_code == 201
    notice_id = res.json()["id"]

    # 2. Cadet can view the unit-wide notice
    list_res = client.get("/notices", headers=cadet_headers)
    assert list_res.status_code == 200
    ids = [n["id"] for n in list_res.json()]
    assert notice_id in ids

    # 3. Verify audit log entry created
    audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.resource_type == "Notice", AuditLog.resource_id == str(notice_id))
        .first()
    )
    assert audit is not None
    assert audit.action == "NOTICE_CREATED"


def test_cadet_cannot_create_or_delete_notice(client, seed_data):
    cadet1 = seed_data["cadet1"]
    ano = seed_data["ano"]
    cadet_headers = auth_headers_for(cadet1)
    ano_headers = auth_headers_for(ano)

    # Cadet creation attempt rejected
    create_res = client.post(
        "/notices",
        json={"title": "Cadet Notice", "content": "Unauthorized content"},
        headers=cadet_headers,
    )
    assert create_res.status_code == 403

    # ANO creates notice
    notice = client.post(
        "/notices",
        json={"title": "Official Notice", "content": "Authorized content"},
        headers=ano_headers,
    ).json()

    # Cadet deletion attempt rejected
    delete_res = client.delete(f"/notices/{notice['id']}", headers=cadet_headers)
    assert delete_res.status_code == 403


def test_squad_targeted_notice_isolation(client, seed_data):
    ano_headers = auth_headers_for(seed_data["ano"])
    cadet1_headers = auth_headers_for(seed_data["cadet1"])  # Squad 1
    cadet2_headers = auth_headers_for(seed_data["cadet2"])  # Squad 2

    # Notice targeted exclusively to Squad 1
    notice = client.post(
        "/notices",
        json={
            "title": "Alpha Squad Rifle Range Practice",
            "content": "Alpha Squad members report to range at 0600 hrs.",
            "target_squad_id": seed_data["squad1"].id,
        },
        headers=ano_headers,
    ).json()

    # Cadet 1 (Squad 1) can view the notice
    c1_res = client.get(f"/notices/{notice['id']}", headers=cadet1_headers)
    assert c1_res.status_code == 200

    # Cadet 2 (Squad 2) is forbidden from viewing the notice
    c2_res = client.get(f"/notices/{notice['id']}", headers=cadet2_headers)
    assert c2_res.status_code == 403
