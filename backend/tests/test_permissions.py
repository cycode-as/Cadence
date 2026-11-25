"""Tests for Role-Based and Scope-Based authorization."""

import pytest

from policy.permissions import AuthorizationError, check_scope, enforce_scope


def test_co_and_ano_unit_scope(seed_data):
    co = seed_data["co"]
    ano = seed_data["ano"]
    unit = seed_data["unit"]

    # Allowed within their unit
    assert check_scope(co, target_unit_id=unit.id) is True
    assert check_scope(ano, target_unit_id=unit.id) is True

    # Denied outside their unit
    assert check_scope(co, target_unit_id=999) is False
    assert check_scope(ano, target_unit_id=999) is False


def test_juo_scope(seed_data):
    juo = seed_data["juo"]
    squad1 = seed_data["squad1"]
    squad2 = seed_data["squad2"]

    # JUO assigned to squad1
    assert check_scope(juo, target_unit_id=juo.unit_id, target_squad_id=squad1.id) is True
    assert check_scope(juo, target_unit_id=juo.unit_id, target_squad_id=squad2.id) is False
    assert check_scope(juo, target_unit_id=999) is False


def test_leader_squad_scope(seed_data):
    leader = seed_data["leader"]
    squad1 = seed_data["squad1"]
    squad2 = seed_data["squad2"]

    # Leader can only access squad1
    assert check_scope(leader, target_squad_id=squad1.id) is True
    assert check_scope(leader, target_squad_id=squad2.id) is False


def test_cadet_self_scope_only(seed_data):
    cadet1 = seed_data["cadet1"]
    cadet2 = seed_data["cadet2"]

    # Cadet can only access their own records
    assert check_scope(cadet1, target_cadet_id=cadet1.id) is True
    assert check_scope(cadet1, target_cadet_id=cadet2.id) is False
    assert check_scope(cadet1, target_squad_id=cadet1.squad_id) is False


def test_enforce_scope_exception(seed_data):
    cadet1 = seed_data["cadet1"]
    cadet2 = seed_data["cadet2"]

    # Passing check raises nothing
    enforce_scope(cadet1, target_cadet_id=cadet1.id)

    # Failing check raises AuthorizationError
    with pytest.raises(AuthorizationError):
        enforce_scope(cadet1, target_cadet_id=cadet2.id)
