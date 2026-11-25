"""Tasks management service with lifecycle management and audit trails."""


from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from core.models import AuditLog, Role, Task, TaskStatus, User
from modules.tasks.schemas import (
    TaskCreateRequest,
    TaskResponse,
    TaskReviewRequest,
    TaskSubmitRequest,
    TaskUpdateRequest,
)
from policy.permissions import check_scope, enforce_scope


def map_task_response(task: Task) -> TaskResponse:
    """Format Task entity into TaskResponse schema."""
    return TaskResponse(
        id=task.id,
        unit_id=task.unit_id,
        squad_id=task.squad_id,
        assignee_id=task.assignee_id,
        assignee_name=task.assignee.full_name if task.assignee else None,
        title=task.title,
        description=task.description,
        due_date=task.due_date,
        status=task.status,
        submission_text=task.submission_text,
        feedback=task.feedback,
        created_by_id=task.created_by_id,
        creator_name=task.creator.full_name if task.creator else None,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def create_task(
    db: Session,
    user: User,
    data: TaskCreateRequest,
) -> TaskResponse:
    """Create and assign a task to a squad or cadet (Leader, JUO, ANO, CO)."""
    enforce_scope(user, target_unit_id=user.unit_id, target_squad_id=data.squad_id)

    # If assigning to specific cadet, verify cadet scope
    if data.assignee_id:
        cadet = db.query(User).filter(User.id == data.assignee_id).first()
        if not cadet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Assignee cadet ID {data.assignee_id} not found",
            )
        if user.role == Role.LEADER and cadet.squad_id != user.squad_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Leaders may only assign tasks to cadets in their own squad",
            )

    task = Task(
        unit_id=user.unit_id or 1,
        squad_id=data.squad_id,
        assignee_id=data.assignee_id,
        title=data.title,
        description=data.description,
        due_date=data.due_date,
        status=TaskStatus.ASSIGNED,
        created_by_id=user.id,
    )
    db.add(task)
    db.flush()

    audit = AuditLog(
        actor_id=user.id,
        action="TASK_CREATED",
        resource_type="Task",
        resource_id=str(task.id),
        new_state=TaskStatus.ASSIGNED.value,
        reason=f"Task '{task.title}' assigned to squad {task.squad_id} / cadet {task.assignee_id}",
    )
    db.add(audit)
    db.flush()

    return map_task_response(task)


def list_tasks(
    db: Session,
    user: User,
    status_filter: TaskStatus | None = None,
) -> list[TaskResponse]:
    """Retrieve tasks accessible to the user based on role and assignment."""
    query = db.query(Task).filter(Task.unit_id == user.unit_id)

    if user.role == Role.CADET:
        query = query.filter(
            (Task.assignee_id == user.id)
            | ((Task.squad_id == user.squad_id) & (Task.assignee_id.is_(None)))
        )
    elif user.role == Role.LEADER:
        query = query.filter(
            (Task.squad_id == user.squad_id)
            | (Task.created_by_id == user.id)
        )

    if status_filter:
        query = query.filter(Task.status == status_filter)

    tasks = query.order_by(Task.due_date.asc()).all()
    return [map_task_response(t) for t in tasks]


def get_task(
    db: Session,
    user: User,
    task_id: int,
) -> TaskResponse:
    """Retrieve details of a specific task within scope."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    # Unit boundary
    if user.unit_id and task.unit_id != user.unit_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Task belongs to another unit",
        )

    # Cadet scope
    if user.role == Role.CADET:
        is_assigned_individually = task.assignee_id == user.id
        is_assigned_to_squad = task.squad_id == user.squad_id and task.assignee_id is None
        if not (is_assigned_individually or is_assigned_to_squad):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You are not assigned to this task",
            )

    return map_task_response(task)


def update_task_progress(
    db: Session,
    user: User,
    task_id: int,
    data: TaskUpdateRequest,
) -> TaskResponse:
    """Update task metadata (Leaders/Officers) or progress status (Assignee)."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    prev_state = task.status.value

    # Cadet can only transition task from ASSIGNED to IN_PROGRESS
    if user.role == Role.CADET:
        if task.assignee_id != user.id and task.squad_id != user.squad_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Cannot update task you are not assigned to",
            )
        if data.status and data.status == TaskStatus.IN_PROGRESS:
            task.status = TaskStatus.IN_PROGRESS
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cadets may only update status to IN_PROGRESS",
            )
    else:
        # Leader or Officer editing task
        if not check_scope(user, target_unit_id=task.unit_id, target_squad_id=task.squad_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Outside your authorized scope",
            )
        if data.title:
            task.title = data.title
        if data.description:
            task.description = data.description
        if data.due_date:
            task.due_date = data.due_date
        if data.status:
            task.status = data.status

    db.add(task)

    audit = AuditLog(
        actor_id=user.id,
        action="TASK_UPDATED",
        resource_type="Task",
        resource_id=str(task.id),
        previous_state=prev_state,
        new_state=task.status.value,
        reason=f"Task updated by {user.full_name}",
    )
    db.add(audit)
    db.flush()

    return map_task_response(task)


def submit_task_work(
    db: Session,
    user: User,
    task_id: int,
    data: TaskSubmitRequest,
) -> TaskResponse:
    """Assignee submits completed task work: (ASSIGNED/IN_PROGRESS -> SUBMITTED)."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    # Only assigned cadet or squad member can submit
    if user.role == Role.CADET:
        if task.assignee_id != user.id and task.squad_id != user.squad_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Only assigned cadet may submit task work",
            )

    if task.status not in (TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot submit task work when status is {task.status.value}",
        )

    prev_state = task.status.value
    task.submission_text = data.submission_text
    task.status = TaskStatus.SUBMITTED
    db.add(task)

    audit = AuditLog(
        actor_id=user.id,
        action="TASK_SUBMITTED",
        resource_type="Task",
        resource_id=str(task.id),
        previous_state=prev_state,
        new_state=TaskStatus.SUBMITTED.value,
        reason="Task work submitted for review",
    )
    db.add(audit)
    db.flush()

    return map_task_response(task)


def review_task_submission(
    db: Session,
    user: User,
    task_id: int,
    data: TaskReviewRequest,
) -> TaskResponse:
    """Authorized reviewer reviews task submission: (SUBMITTED -> COMPLETED / REJECTED)."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    if task.status != TaskStatus.SUBMITTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task status must be SUBMITTED to review, got {task.status.value}",
        )

    if data.status not in (TaskStatus.COMPLETED, TaskStatus.APPROVED, TaskStatus.REJECTED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Review status must be COMPLETED or REJECTED",
        )

    # Leader scope check
    if user.role == Role.LEADER and task.squad_id and task.squad_id != user.squad_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Leaders may only review tasks in their squad",
        )

    prev_state = task.status.value
    task.status = data.status
    task.feedback = data.feedback
    db.add(task)

    audit = AuditLog(
        actor_id=user.id,
        action="TASK_REVIEWED",
        resource_type="Task",
        resource_id=str(task.id),
        previous_state=prev_state,
        new_state=data.status.value,
        reason=f"Reviewed: {data.feedback or 'No feedback provided'}",
    )
    db.add(audit)
    db.flush()

    return map_task_response(task)
