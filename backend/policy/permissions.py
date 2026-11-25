"""Role-Based and Scope-Based Access Control policies for Cadence."""


from fastapi import HTTPException, status

from core.models import Role, User


class AuthorizationError(HTTPException):
    """Exception raised when an action is unauthorized."""

    def __init__(self, detail: str = "Permission denied"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def check_scope(
    user: User,
    target_unit_id: int | None = None,
    target_squad_id: int | None = None,
    target_cadet_id: int | None = None,
) -> bool:
    """Validate whether the user's role and assignment grant access to the specified target.

    Rules:
    - CO and ANO have unit-wide access for their assigned unit.
    - JUO has unit-wide supervisory access or scoped squad access.
    - Leader has access strictly confined to their assigned squad and unit-level events.
    - Cadet has access within their unit/squad, and strictly own cadet records.
    """
    # System administrators or CO: Unit-wide authority
    if user.role == Role.CO:
        if target_unit_id is not None and user.unit_id is not None:
            return user.unit_id == target_unit_id
        return True

    # ANO: Unit-wide administrative authority
    if user.role == Role.ANO:
        if target_unit_id is not None and user.unit_id is not None:
            return user.unit_id == target_unit_id
        return True

    # JUO: Operational supervisor within their unit
    if user.role == Role.JUO:
        if target_unit_id is not None and user.unit_id != target_unit_id:
            return False
        if target_squad_id is not None and user.squad_id is not None:
            return user.squad_id == target_squad_id
        return True

    # Leader: Squad-level access
    if user.role == Role.LEADER:
        if target_unit_id is not None and user.unit_id != target_unit_id:
            return False
        if target_squad_id is not None and user.squad_id != target_squad_id:
            return False
        return True

    # Cadet: strictly own records
    if user.role == Role.CADET:
        if target_cadet_id is not None:
            return user.id == target_cadet_id
        return False

    return False


def enforce_scope(
    user: User,
    target_unit_id: int | None = None,
    target_squad_id: int | None = None,
    target_cadet_id: int | None = None,
) -> None:
    """Enforce scope validation, raising HTTP 403 Forbidden on violation."""
    if not check_scope(
        user,
        target_unit_id=target_unit_id,
        target_squad_id=target_squad_id,
        target_cadet_id=target_cadet_id,
    ):
        raise AuthorizationError(
            detail="Forbidden: Access outside assigned scope denied."
        )
