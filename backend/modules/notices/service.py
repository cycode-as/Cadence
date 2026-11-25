"""Notices management service with scope isolation and audit logging."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from core.models import AuditLog, Notice, Role, User
from modules.notices.schemas import (
    NoticeCreateRequest,
    NoticeResponse,
    NoticeUpdateRequest,
)
from policy.permissions import check_scope, enforce_scope


def map_notice_response(notice: Notice) -> NoticeResponse:
    """Format Notice entity into NoticeResponse schema."""
    return NoticeResponse(
        id=notice.id,
        unit_id=notice.unit_id,
        target_squad_id=notice.target_squad_id,
        title=notice.title,
        content=notice.content,
        author_id=notice.author_id,
        author_name=notice.author.full_name if notice.author else None,
        is_published=notice.is_published,
        created_at=notice.created_at,
        updated_at=notice.updated_at,
    )


def create_notice(
    db: Session,
    user: User,
    data: NoticeCreateRequest,
) -> NoticeResponse:
    """Create a new notice targeted to unit or squad (CO, ANO, JUO)."""
    enforce_scope(user, target_unit_id=user.unit_id, target_squad_id=data.target_squad_id)

    notice = Notice(
        unit_id=user.unit_id or 1,
        target_squad_id=data.target_squad_id,
        title=data.title,
        content=data.content,
        author_id=user.id,
        is_published=data.is_published,
    )
    db.add(notice)
    db.flush()

    audit = AuditLog(
        actor_id=user.id,
        action="NOTICE_CREATED",
        resource_type="Notice",
        resource_id=str(notice.id),
        new_state=f"Published: {notice.is_published}",
        reason=f"Notice '{notice.title}' published by {user.full_name}",
    )
    db.add(audit)
    db.flush()

    return map_notice_response(notice)


def list_notices(
    db: Session,
    user: User,
) -> list[NoticeResponse]:
    """List notices visible to the user within their authorized scope."""
    query = db.query(Notice).filter(Notice.unit_id == user.unit_id)

    # For cadets/leaders: only published notices matching their squad or unit-wide
    if user.role in (Role.CADET, Role.LEADER):
        query = query.filter(Notice.is_published.is_(True))
        if user.squad_id:
            query = query.filter(
                (Notice.target_squad_id == user.squad_id)
                | (Notice.target_squad_id.is_(None))
            )
        else:
            query = query.filter(Notice.target_squad_id.is_(None))

    notices = query.order_by(Notice.created_at.desc()).all()
    return [map_notice_response(n) for n in notices]


def get_notice(
    db: Session,
    user: User,
    notice_id: int,
) -> NoticeResponse:
    """Retrieve details of a notice if visible to user scope."""
    notice = db.query(Notice).filter(Notice.id == notice_id).first()
    if not notice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notice not found",
        )

    # Unit isolation
    if user.unit_id and notice.unit_id != user.unit_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Notice belongs to another unit",
        )

    # Squad isolation for Cadets and Leaders
    if user.role in (Role.CADET, Role.LEADER):
        if not notice.is_published:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notice is not published",
            )
        if notice.target_squad_id and notice.target_squad_id != user.squad_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Notice is targeted to another squad",
            )

    return map_notice_response(notice)


def update_notice(
    db: Session,
    user: User,
    notice_id: int,
    data: NoticeUpdateRequest,
) -> NoticeResponse:
    """Update a notice (CO, ANO, JUO)."""
    notice = db.query(Notice).filter(Notice.id == notice_id).first()
    if not notice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notice not found",
        )

    if not check_scope(user, target_unit_id=notice.unit_id, target_squad_id=notice.target_squad_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Cannot edit notices outside your authorized scope",
        )

    prev_state = f"Title: {notice.title}, Published: {notice.is_published}"

    if data.title is not None:
        notice.title = data.title
    if data.content is not None:
        notice.content = data.content
    if data.target_squad_id is not None:
        notice.target_squad_id = data.target_squad_id
    if data.is_published is not None:
        notice.is_published = data.is_published

    db.add(notice)

    audit = AuditLog(
        actor_id=user.id,
        action="NOTICE_UPDATED",
        resource_type="Notice",
        resource_id=str(notice.id),
        previous_state=prev_state,
        new_state=f"Title: {notice.title}, Published: {notice.is_published}",
        reason=f"Notice '{notice.title}' updated by {user.full_name}",
    )
    db.add(audit)
    db.flush()

    return map_notice_response(notice)


def delete_notice(
    db: Session,
    user: User,
    notice_id: int,
) -> None:
    """Delete or archive a notice (CO, ANO)."""
    notice = db.query(Notice).filter(Notice.id == notice_id).first()
    if not notice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notice not found",
        )

    if not check_scope(user, target_unit_id=notice.unit_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Cannot delete notices outside your unit",
        )

    audit = AuditLog(
        actor_id=user.id,
        action="NOTICE_DELETED",
        resource_type="Notice",
        resource_id=str(notice.id),
        previous_state=f"Title: {notice.title}",
        reason=f"Notice deleted by {user.full_name}",
    )
    db.add(audit)
    db.delete(notice)
    db.flush()
