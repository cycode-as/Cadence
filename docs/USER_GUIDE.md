# CADENCE Database User Guide (Member 3)

This guide explains how to set up, migrate, seed, inspect, and integrate the CADENCE PostgreSQL database on Windows (PowerShell / VS Code).

---

## 1. Install Dependencies

Create and activate a virtual environment, then install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

> Tested on **Python 3.14.6** and **PostgreSQL 19** with `SQLAlchemy 2.0.51`, `alembic 1.20.1`, `psycopg[binary] 3.3.9`, `python-dotenv 1.2.4`, `pydantic-settings 2.16.3`, and `tzdata 2026.6` (required on Windows for `ZoneInfo("Asia/Kolkata")`).

---

## 2. Create the Local PostgreSQL Database

Open **SQL Shell (psql)** or PowerShell with `psql` on your `PATH`, connect as the `postgres` superuser, and run:

```sql
CREATE USER cadence_user WITH PASSWORD 'your_strong_local_password';
CREATE DATABASE cadence_db OWNER cadence_user;
GRANT ALL PRIVILEGES ON DATABASE cadence_db TO cadence_user;
```

If using PostgreSQL 15+, also ensure schema privileges inside `cadence_db`:

```sql
\c cadence_db
GRANT ALL ON SCHEMA public TO cadence_user;
```

---

## 3. Configure `DATABASE_URL`

1. Copy `.env.example` to `.env`:

```powershell
Copy-Item .env.example .env
```

2. Edit `.env` and fill in your local PostgreSQL credentials (never commit `.env`):

```env
DATABASE_URL=postgresql+psycopg://cadence_user:your_strong_local_password@localhost:5432/cadence_db
CADENCE_SEED_PASSWORD=your_local_demo_password
APP_ENV=development
```

> **Note:** Both `postgresql+psycopg://...` and `postgresql://...` work. `database/config.py` automatically normalizes `postgres://` and `postgresql://` to `postgresql+psycopg://` when Psycopg 3 is installed.
>
> **Special characters in passwords:** If your PostgreSQL password contains `@`, `#`, `:`, `/`, `?`, or `%`, URL-encode them in `DATABASE_URL` (for example, `@` → `%40`).

---

## 4. Run Alembic Migrations

Apply all migrations to create enums, tables, keys, indexes, and constraints:

```powershell
alembic upgrade head
```

Useful Alembic commands:

```powershell
# Check current revision
alembic current

# View migration history
alembic history

# Create a new migration after model edits
alembic revision --autogenerate -m "describe_change"

# Roll back one migration (local dev only)
alembic downgrade -1
```

---

## 5. Seed Demo Data

Run the idempotent seed script:

```powershell
python -m database.seed
```

This creates:
- **1 Battalion (`unit`)**: `1st CADENCE NCC Battalion` (`BN-01`)
- **2 Contingents (`contingent`)**: `Alpha Contingent`, `Bravo Contingent`
- **4 Companies & 8 Squads**
- **60 Cadets (`cadet_profile`)** with separate `rank` and `role`
- **5 Role Logins (`user`)**:
  - `cadet@cadence.test` (`Role.CADET`)
  - `leader@cadence.test` (`Role.CADET_LEADER`)
  - `juo@cadence.test` (`Role.JUO`)
  - `ano@cadence.test` (`Role.ANO`)
  - `co@cadence.test` (`Role.CO`)

Running `python -m database.seed` multiple times will **not** create duplicate records.

---

## 6. Connect with pgAdmin or DBeaver

- **Host:** `localhost`
- **Port:** `5432`
- **Database:** `cadence_db`
- **Username:** `cadence_user`
- **Password:** *(your `.env` password)*

To inspect tables quickly with `psql`:

```powershell
psql -h localhost -U cadence_user -d cadence_db -c "\dt"
```

---

## 7. How Member 1 Imports and Uses `get_db()`

```python
from fastapi import Depends
from sqlalchemy.orm import Session

from database.session import get_db
from database.models import User, RefreshToken, OtpCode, Role, Rank

def example_route(db: Session = Depends(get_db)):
    ...
```

`get_db()` yields a synchronous SQLAlchemy `Session` and reliably closes it in a `finally` block. See [MEMBER1_INTEGRATION.md](MEMBER1_INTEGRATION.md) for the full backend integration contract.

---

## 8. Run Database Tests

Run the automated database layer test suite (`unittest`):

```powershell
python -m unittest discover -s tests -v
```

---

## 9. Schema Overview (20 Tables)

### Organization
- `unit` — Top-level battalion
- `contingent` — Belongs to `unit`
- `company` — Belongs to `contingent`
- `squad` — Belongs to `company`

### People
- `user` — Auth account (`email`, `password_hash`, `role`, MFA fields, `must_change_password`)
- `cadet_profile` — 1:1 with `user` (`user_id` unique), unique `cadet_no`, `rank`, org placement (`company_id`, `squad_id`)
- `role_assignment` — Scoped role assignment (`role`, `scope_type`, `scope_id`)
- `rank_history` — Immutable rank change history per `cadet_profile`

### Attendance
- `parade` — Scheduled parade event
- `attendance_sheet` — Unique `(parade_id, squad_id)`, state machine (`SheetStatus`), optimistic `version >= 1`
- `attendance_record` — Unique `(sheet_id, cadet_id)`, `AttendanceStatus`, protected by `ON DELETE RESTRICT`

### Leave
- `leave_request` — Cadet leave request (`to_date >= from_date`), `LeaveStatus`, `version >= 1`
- `approval_step` — Leave approval/forward/escalate/cancel timeline entries

### Communication
- `notice` — Scoped or public announcement (`target_scope_type`, `target_scope_id`, `is_public`)
- `notice_receipt` — Unique `(notice_id, user_id)` read tracking

### Other
- `exam_resource` — Study links grouped by `ExamLevel` (`A`, `B`, `C`)
- `audit_log` — Append-only audit trail (`action`, `entity_type`, `entity_id`, `before_data`, `after_data`, `reason`)

### Auth & MFA (Requested by Member 1)
- `refresh_token` — Hashed rotating refresh tokens (`token_hash` unique, `family_id`, `expires_at`, `revoked_at`, `replaced_by_token_id`)
- `otp_code` — Hashed one-time email OTPs (`code_hash`, `purpose`, `expires_at`, `consumed_at`, `attempt_count >= 0`)

### Tasks (Provisional Member 1 Integration)
- `task` — Scoped work item. PostgreSQL UUID columns are represented as UUID strings in Python.

| Field | Type / nullability | Description |
|---|---|---|
| `id` | UUID, required | Generated primary key |
| `unit_id` | UUID, required | Owning unit |
| `contingent_id` | UUID, nullable | Contingent scope; null for unit-wide tasks |
| `squad_id` | UUID, nullable | Squad scope; null for broader-scope tasks |
| `created_by_id` | UUID, required | User who created the task |
| `assignee_id` | UUID, nullable | Assigned user; null while unassigned |
| `title` | String(255), required | Short task title |
| `description` | Text, nullable | Additional task details |
| `status` | String(32), required | Checked status value; defaults to `TODO` |
| `priority` | String(16), required | Checked priority value; defaults to `MEDIUM` |
| `due_date` | Date, nullable | Optional due date |
| `created_at` | Timestamp with time zone, required | Creation time in UTC |
| `updated_at` | Timestamp with time zone, required | Last update time in UTC |

- Provisional status values: `TODO`, `IN_PROGRESS`, `DONE`, `CANCELLED`.
- Provisional priority values: `LOW`, `MEDIUM`, `HIGH`, `URGENT`.
- `Task.creator` and `Task.assignee` are distinct `User` relationships. Unit, contingent, squad, and creator deletion is restricted; deleting an assignee sets `assignee_id` to `NULL`.
- The current backend Task schema is not present in the repository. Field names and status/priority sets above are explicit integration assumptions and must be confirmed by Member 1 before API integration.

The Task table is introduced by an additive Alembic revision. Review the new revision and apply it with `alembic upgrade head`; it does not replace the initial migration or modify existing tables.

Example:

```python
from database.models import Task

task = Task(
    unit_id=unit.id,
    contingent_id=contingent.id,
    squad_id=squad.id,
    created_by_id=creator.id,
    assignee_id=assignee.id,
    title="Prepare parade checklist",
    status="TODO",
    priority="MEDIUM",
)
db.add(task)
db.commit()
```

---

## 10. Common Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `DATABASE_URL environment variable is not set` | Missing `.env` or shell variable | Copy `.env.example` to `.env` and set `DATABASE_URL` |
| `failed to resolve host` in `DATABASE_URL` | Unencoded `@` inside password | URL-encode special characters in password (e.g. `@` → `%40`) |
| `connection to server at "localhost", port 5432 failed` | PostgreSQL service stopped | Start PostgreSQL service in Windows Services (`postgresql-x64-19`) |
| `password authentication failed for user` | Wrong username or password in `.env` | Verify `.env` matches your PostgreSQL user (`postgres` or `cadence_user`) and password |
| `database "cadence_db" does not exist` | DB not created yet | Run `CREATE DATABASE cadence_db;` in `psql` |
| `No module named 'psycopg2'` | Old URL missing `+psycopg` or custom engine bypassing `database.config` | Always use `database.config` / `database.session`, or prefix URL with `postgresql+psycopg://` |
