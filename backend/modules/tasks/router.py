"""FastAPI Router for Task Operations."""


from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from core.dependencies import get_current_user, require_roles
from core.models import Role, TaskStatus, User
from database.session import get_db
from modules.tasks.schemas import (
    TaskCreateRequest,
    TaskResponse,
    TaskReviewRequest,
    TaskSubmitRequest,
    TaskUpdateRequest,
)
from modules.tasks.service import (
    create_task,
    get_task,
    list_tasks,
    review_task_submission,
    submit_task_work,
    update_task_progress,
)

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_new_task(
    payload: TaskCreateRequest,
    current_user: User = Depends(require_roles(Role.CO, Role.ANO, Role.JUO, Role.LEADER)),
    db: Session = Depends(get_db),
) -> TaskResponse:
    """Assign a new task to a cadet or squad (Leader, JUO, ANO, CO)."""
    return create_task(db, current_user, payload)


@router.get("", response_model=list[TaskResponse])
def get_all_tasks(
    status_filter: TaskStatus | None = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TaskResponse]:
    """List tasks visible to user scope."""
    return list_tasks(db, current_user, status_filter=status_filter)


@router.get("/{id}", response_model=TaskResponse)
def get_task_by_id(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskResponse:
    """Retrieve detailed task information."""
    return get_task(db, current_user, id)


@router.patch("/{id}", response_model=TaskResponse)
def update_task(
    id: int,
    payload: TaskUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskResponse:
    """Update task progress (Assignee) or metadata (Leader/Officers)."""
    return update_task_progress(db, current_user, id, payload)


@router.post("/{id}/submit", response_model=TaskResponse)
def submit_task(
    id: int,
    payload: TaskSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskResponse:
    """Submit completed work for review (Assignee cadet)."""
    return submit_task_work(db, current_user, id, payload)


@router.post("/{id}/review", response_model=TaskResponse)
def review_task(
    id: int,
    payload: TaskReviewRequest,
    current_user: User = Depends(require_roles(Role.CO, Role.ANO, Role.JUO, Role.LEADER)),
    db: Session = Depends(get_db),
) -> TaskResponse:
    """Review and complete or reject task submission with feedback."""
    return review_task_submission(db, current_user, id, payload)
