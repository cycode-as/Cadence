"""FastAPI Router for Notices."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from core.dependencies import get_current_user, require_roles
from core.models import Role, User
from database.session import get_db
from modules.notices.schemas import (
    NoticeCreateRequest,
    NoticeResponse,
    NoticeUpdateRequest,
)
from modules.notices.service import (
    create_notice,
    delete_notice,
    get_notice,
    list_notices,
    update_notice,
)

router = APIRouter(prefix="/notices", tags=["Notices"])


@router.post("", response_model=NoticeResponse, status_code=status.HTTP_201_CREATED)
def create_new_notice(
    payload: NoticeCreateRequest,
    current_user: User = Depends(require_roles(Role.CO, Role.ANO, Role.JUO)),
    db: Session = Depends(get_db),
) -> NoticeResponse:
    """Publish a new notice to unit or specific squad (CO, ANO, JUO)."""
    return create_notice(db, current_user, payload)


@router.get("", response_model=list[NoticeResponse])
def get_all_notices(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[NoticeResponse]:
    """Retrieve all notices visible to the user's scope."""
    return list_notices(db, current_user)


@router.get("/{id}", response_model=NoticeResponse)
def get_notice_by_id(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NoticeResponse:
    """Retrieve detailed notice content within scope."""
    return get_notice(db, current_user, id)


@router.patch("/{id}", response_model=NoticeResponse)
def update_existing_notice(
    id: int,
    payload: NoticeUpdateRequest,
    current_user: User = Depends(require_roles(Role.CO, Role.ANO, Role.JUO)),
    db: Session = Depends(get_db),
) -> NoticeResponse:
    """Update notice content, target squad, or publish status."""
    return update_notice(db, current_user, id, payload)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_notice(
    id: int,
    current_user: User = Depends(require_roles(Role.CO, Role.ANO)),
    db: Session = Depends(get_db),
) -> None:
    """Delete a notice (CO, ANO)."""
    delete_notice(db, current_user, id)
