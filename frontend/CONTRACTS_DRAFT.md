# CADENCE API & UI Contracts (Draft)

> Note: `docs/CONTRACTS.md` was not present on `origin/main` at project bootstrap.
> This draft captures the agreed contracts for Member 1 (Backend), Member 2 (Frontend), and Member 3 (Database).

## 1. Conventions
- **IDs**: UUID strings for all entities except `cadet_no` (e.g. `NCC-2026-0142`).
- **Timestamps**: ISO 8601 UTC on the wire; formatted to IST (`Asia/Kolkata`) in the UI.
- **Response formats**:
  - Page routes return `text/html`.
  - `/api/...` routes return `application/json`.
  - `/fragments/...` routes return `text/html` partials for HTMX.
- **Errors**:
  ```json
  {"error": {"code": "FORBIDDEN", "message": "...", "details": {}}}
  ```
  Error codes: `UNAUTHENTICATED` (401), `FORBIDDEN` (403), `NOT_FOUND` (404), `VALIDATION` (422), `CONFLICT` (409), `RATE_LIMITED` (429).
- **Auth**: `httpOnly` cookies (`access_token`, `refresh_token`).
- **CSRF**:
  - Every `POST`/`PUT`/`PATCH`/`DELETE` HTML form includes hidden input `csrf_token`.
  - All HTMX requests attach header `X-CSRF-Token` via `htmx:configRequest`.
- **Pagination**: `?cursor=<opaque>&limit=25` -> `{"items": [], "next_cursor": null}`.

## 2. Enums (Exact Values)
- `Role`: `CADET`, `CADET_LEADER`, `JUO`, `ANO`, `CO`
- `Rank`: `CADET`, `LCPL`, `CPL`, `SGT`, `CQMS`, `CSM`, `JUO`, `SUO`, `OFFICER`
- `ScopeType`: `SELF`, `SQUAD`, `COMPANY`, `CONTINGENT`, `BATTALION`
- `AttendanceStatus`: `PRESENT`, `ABSENT`, `LEAVE`, `LATE`
- `SheetStatus`: `DRAFT`, `SUBMITTED`, `JUO_REVIEWED`, `ANO_APPROVED`, `LOCKED`
- `LeaveStatus`: `PENDING_LEADER`, `PENDING_JUO`, `PENDING_ANO`, `PENDING_CO`, `APPROVED`, `REJECTED`, `CANCELLED`
- `ExamLevel`: `A`, `B`, `C`

## 3. Page Routes & Context Contracts
Every authenticated page receives:
- `user`: `{id, full_name, role, rank, scope_type, scope_name}`
- `nav_items`: `[]`
- `csrf_token`: `string`
- `bell`: `{unread_notices, pending_actions}`

Routes:
- `GET /dashboard` -> redirect by role
- `GET /dashboard/cadet` -> `dashboards/cadet.html`: `attendance_pct`, `next_parade`, `unread_notices`, `leave_summary`, `charts.attendance_trend`
- `GET /dashboard/leader` -> `dashboards/cadet_leader.html`: `squad`, `pending_sheets`, `pending_leave`, `absentees_today`, `charts.squad_attendance`
- `GET /dashboard/juo` -> `dashboards/juo.html`: `company`, `sheets_to_review`, `leave_queue`, `charts.company_by_squad`
- `GET /dashboard/ano` -> `dashboards/ano.html`: `contingent`, `approvals_pending`, `roster_counts`, `charts.contingent_trend`, `charts.leave_stats`
- `GET /dashboard/co` -> `dashboards/co.html`: `battalion`, `contingent_comparison`, `escalations`, `charts.battalion_by_contingent`
- `GET /attendance/sheet/{id}` -> `marking_sheet.html` (leader) or `approval.html` (JUO/ANO): `sheet`
- `GET /attendance/review` -> `review_list.html`: `items[]`, `filters`
- `GET /attendance/history` -> `history.html`: `percentage`, `items[]`
- `GET /leave/apply`, `/leave`, `/leave/{id}` -> `leave/apply.html`, `queue.html`, `detail.html`: `items[]`, `leave` (with `timeline[]` and `allowed_actions[]`)
- `GET /notices`, `/notices/new` -> `inbox.html`, `create.html`: `items[]`, `unread_count`; `scope_options[]`
- `GET /exam-resources` -> `list.html`: `items[]`, `levels[]`, `can_manage`
- `GET /reports` -> `reports/index.html`: `filters`, `level_options[]`, `download_links`
- `GET /admin/roster`, `/admin/import`, `/admin/squads` -> `roster.html`, `csv_upload.html`, `squad_board.html`: `cadets[]`, `import_result`, `org_tree`
- `GET /admin/audit` -> `audit_log.html`: `items[]`, `filters`, `next_cursor`
- `GET /` -> `guest/home.html`: `public_notices[]`, `exam_resources[]`
- Error handlers -> `errors/403|404|500.html`: `message`

### Sheet & Timeline Schema
- `sheet`: `{id, parade{}, squad{id,name}, status, version, records[{cadet_user_id, full_name, cadet_no, rank, status, remark}], timeline[{step, label, actor, at|null, state: done|current|pending}], allowed_actions[]}`
- Attendance state machine: `DRAFT` -> `SUBMITTED` -> `JUO_REVIEWED` -> `ANO_APPROVED` -> `LOCKED` (returns go back to `DRAFT`; locked edits require ANO + reason).
- Leave chain: `Cadet` -> `Cadet Leader` -> `JUO` -> `ANO` (`CO` for escalations).

## 4. Backend APIs Consumed
- **Auth (M1)**:
  - `POST /auth/login` `{email, password}`
  - `POST /auth/logout`
  - `POST /auth/refresh`
  - `POST /auth/change-password` `{current_password, new_password}`
  - `GET /auth/mfa/setup` (QR) & `POST /auth/mfa/setup/confirm` `{code}`
  - `POST /auth/mfa/verify` `{code}` or `{method: "email"}`
  - `POST /auth/mfa/email-otp`
  - MFA is mandatory for `ANO` and `CO`.
- **Attendance (M1)**:
  - `POST /api/parades`, `GET /api/parades`
  - `GET /api/attendance/sheets/{id}`
  - `PUT /api/attendance/sheets/{id}/records` `{records: [{cadet_user_id, status, remark}]}` (returns 409 on stale `version`)
  - `POST /api/attendance/sheets/{id}/submit`
  - `POST /api/attendance/sheets/{id}/review` `{decision: "FORWARD"|"RETURN", comment}`
  - `POST /api/attendance/sheets/{id}/approve` `{decision: "APPROVE"|"RETURN", comment}`
  - `POST /api/attendance/sheets/{id}/edit-locked` `{cadet_user_id, status, reason}`
  - `GET /api/attendance/me` -> `{percentage, present, total, items[]}`
- **Leave (M1)**:
  - `POST /api/leave` `{from_date, to_date, reason}`
  - `GET /api/leave`, `GET /api/leave/{id}`
  - `POST /api/leave/{id}/forward`, `.../decide` `{decision: "APPROVE"|"REJECT", comment}`, `.../escalate` `{reason}`, `.../cancel`
- **Notices (M1)**:
  - `POST /api/notices` `{title, body, target_scope_type, target_scope_id, is_public}`
  - `GET /api/notices` -> `{items[{id, title, body, published_by, published_at, read}], next_cursor, unread_count}`
  - `POST /api/notices/{id}/read`
  - `GET /api/public/notices` (no auth)
  - `GET /api/me/bell`
- **Reports & Audit (M1)**:
  - `GET /api/reports/attendance?level&scope_id&from&to&format=json|csv`
  - `GET /api/reports/absentees?parade_id`
  - `GET /api/reports/leave-stats`
  - `GET /api/audit?actor&action&entity_type&from&to&cursor`
- **Roster / Org / Exam Resources (M3)**:
  - `GET /api/org/tree`
  - `GET /api/cadets`
  - `POST /api/cadets/{user_id}/move` `{to_squad_id}`
  - `POST /api/cadets/import` (multipart CSV) -> `{imported, failed, errors[{row, field, message}]}`
  - `GET /api/cadets/import/template`
  - `GET/POST/PATCH/DELETE /api/exam-resources` (ANO, CO manage)
  - CSV columns: `full_name,email,phone,cadet_no,rank,division,company,squad,enrollment_date,guardian_name,guardian_phone`

## 5. HTMX Fragments
- `/fragments/dashboard/cards` -> `#stat-cards` (`dashboard.refresh`)
- `/fragments/attendance/sheet/{id}/body` -> `#sheet-{id}` (`attendance.updated`)
- `/fragments/attendance/sheet/{id}/timeline` -> `#timeline-{id}` (`attendance.updated`)
- `/fragments/leave/queue` -> `#leave-queue` (`leave.updated`)
- `/fragments/leave/{id}/timeline` -> `#timeline-{id}` (`leave.updated`)
- `/fragments/notices/list` -> `#notice-list` (`notice.created`)
- `/fragments/bell` -> `#bell` (any event)
- `/fragments/presence/{entity}/{id}` -> `#presence-{id}` (`presence.updated`)

## 6. WebSocket (`/ws`)
- Server -> client event:
  ```json
  {"event":"attendance.updated","scope_type":"SQUAD","scope_id":"uuid","entity":"attendance_sheet","entity_id":"uuid","actor_id":"uuid","at":"2026-11-25T06:00:00Z"}
  ```
- Events: `attendance.updated`, `leave.updated`, `notice.created`, `dashboard.refresh`, `presence.updated`.
- Client -> server: `{"type":"presence.join","entity":"attendance_sheet","entity_id":"..."}` and `presence.leave`.
- Reconnect with exponential backoff; close code `4401` redirects to `/login`.

## 7. Analytics Endpoints (Owned by Frontend)
- `GET /api/analytics/attendance?level&scope_id&from&to`
- `GET /api/analytics/leave?level&scope_id&from&to`
- `GET /api/analytics/drill-table?level&scope_id&from&to&cursor` (HTML table fragment)
- Chart JSON shape:
  ```json
  {"labels":["Alpha Coy","Bravo Coy"],"datasets":[{"label":"Attendance %","data":[91.2,84.5]}],"drill":{"level":"company","next_level":"squad","ids":["uuid1","uuid2"]}}
  ```
