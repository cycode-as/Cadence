# Member 1 Backend Integration Reference (Database Layer)

This document summarizes how the backend (`backend` branch) integrates with the CADENCE database layer (`database/`).

## 1. Standard Imports

```python
from fastapi import Depends
from sqlalchemy.orm import Session

from database.session import get_db, SessionLocal, engine
from database.base import Base
from database.models import (
    # Frozen Enums
    Role,
    Rank,
    ScopeType,
    AttendanceStatus,
    SheetStatus,
    LeaveStatus,
    ExamLevel,
    # Auth & People Models
    User,
    CadetProfile,
    RoleAssignment,
    RankHistory,
    RefreshToken,
    OtpCode,
    # Org & Operations Models
    Unit,
    Contingent,
    Company,
    Squad,
    Parade,
    AttendanceSheet,
    AttendanceRecord,
    LeaveRequest,
    ApprovalStep,
    Notice,
    NoticeReceipt,
    ExamResource,
    AuditLog,
)
```

## 2. `get_db()` Usage

```python
@router.get("/api/example")
def example_endpoint(db: Session = Depends(get_db)):
    ...
```

- **Signature:** `get_db() -> Generator[Session, None, None]`
- **Behavior:** Ensures the SQLAlchemy `Engine` is initialized from `DATABASE_URL`, opens `SessionLocal()`, yields the synchronous `Session`, and guarantees `db.close()` in `finally:`.
- **Timezone support (Windows + UTC storage):** All `created_at`, `updated_at`, `expires_at`, `revoked_at`, `consumed_at`, `read_at`, and `*_at` columns use `DateTime(timezone=True)` storing UTC (`datetime.now(timezone.utc)`). `tzdata==2026.6` is pinned in `requirements.txt` so `zoneinfo.ZoneInfo("Asia/Kolkata")` works reliably on Windows for IST display conversion.
- **UUID convention:** All primary keys and entity/scope foreign keys use `Uuid(as_uuid=False)` — stored as native PostgreSQL `UUID` and returned as standard UUID strings (`str`) in Python.

## 3. Key Model Fields for Auth & MFA

### `User` (`user`)
- `id` (UUID string PK), `unit_id`, `contingent_id` *(nullable for CO)*
- `email` (unique), `full_name`, `phone`
- `password_hash`, `role` (`Role` enum)
- `is_active`, `must_change_password`, `totp_secret`, `mfa_enabled`
- `created_at`, `updated_at`

### `RefreshToken` (`refresh_token`)
- `id` (UUID string PK), `unit_id`, `contingent_id` *(nullable)*
- `user_id` (FK -> `user.id`, `ON DELETE CASCADE`, indexed)
- `token_hash` (unique, indexed — store SHA-256/HMAC hash only, never raw tokens)
- `family_id` (UUID string, indexed — groups a rotation chain for reuse detection)
- `expires_at` (indexed UTC timestamp — 7 days per contract), `revoked_at` (nullable UTC timestamp)
- `replaced_by_token_id` (self-FK -> `refresh_token.id`, `ON DELETE SET NULL`, nullable)
- `created_at`, `updated_at`
- **Relationships:** `RefreshToken.user` (`User.refresh_tokens`), `RefreshToken.replaced_by`
- **Rotation support:** On refresh, create a new `RefreshToken` sharing `family_id`, set `old.revoked_at = utc_now()`, and link `old.replaced_by_token_id = new.id`. If an already-revoked token is presented, revoke all active tokens matching `family_id`.

### `OtpCode` (`otp_code`)
- `id` (UUID string PK), `unit_id`, `contingent_id` *(nullable)*
- `user_id` (FK -> `user.id`, `ON DELETE CASCADE`, indexed)
- `code_hash` (`String(128)` — store hashed OTP only, never plaintext)
- `purpose` (`String(32)`, default `"mfa_email"`)
- `expires_at` (indexed UTC timestamp — 10 minutes per contract), `consumed_at` (nullable UTC timestamp)
- `attempt_count` (`Integer`, default `0`, `CHECK (attempt_count >= 0)`)
- `created_at`, `updated_at`
- **Composite index:** `(user_id, purpose, expires_at)`
- **Relationships:** `OtpCode.user` (`User.otp_codes`)
- **Consumption & rate-limiting:** Increment `attempt_count` on failed verification; set `consumed_at = utc_now()` on single-use success; reject if `consumed_at is not None` or `expires_at <= utc_now()`.

## 4. Documented Contract Assumptions
1. **Scope nullability:** `unit` allows nullable `unit_id` and `contingent_id`; `contingent` allows nullable `contingent_id`; battalion-level rows (`CO` `user`, battalion `notice`, `exam_resource`, `audit_log`, `refresh_token`, `otp_code`) allow nullable `contingent_id`.
2. **`cadet_id` FK target:** `rank_history.cadet_id`, `attendance_record.cadet_id`, and `leave_request.cadet_id` reference `cadet_profile.id`.
3. **Audit JSON columns:** `AuditLog` uses `before_data` and `after_data` (`JSONB` on PostgreSQL, `JSON` on SQLite) to avoid SQL `BEFORE`/`AFTER` keyword collisions.
4. **Password hashing in `database/seed.py`:** Uses PBKDF2-HMAC-SHA256 (`$pbkdf2-sha256$600000$<salt_b64>$<hash_b64>`). Coordinate `verify_password()` in backend auth accordingly or align hashing helper before PR integration.

## 5. Migration & Connection Setup
- Configure `DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/cadence_db` in `.env`.
- Run `alembic upgrade head` before starting the backend server.
- Run `python -m database.seed` to populate demo logins (`cadet@`, `leader@`, `juo@`, `ano@`, `co@cadence.test`).
