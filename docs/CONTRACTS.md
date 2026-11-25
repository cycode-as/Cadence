# CADENCE Contracts (Short Form)

Shared contract for Member 1 (Backend), Member 2 (Frontend) and Member 3 (Database). Save as `docs/CONTRACTS.md`. Changes go through a PR that tags the other two members.

## 0. Shared rules

| Item | Rule |
|---|---|
| IDs / time | UUID strings (`cadet_no` like `NCC-2026-0142`); ISO 8601 UTC, shown in IST |
| Scope columns | Every table has `unit_id` and `contingent_id` |
| Errors | `{"error":{"code","message","details"}}`: `401 UNAUTHENTICATED`, `403 FORBIDDEN`, `404 NOT_FOUND`, `409 CONFLICT`, `422 VALIDATION`, `429 RATE_LIMITED` |
| Auth | httpOnly cookies `access_token` (15 min), `refresh_token` (7 days, rotating) |
| CSRF | `csrf_token` form field or `X-CSRF-Token` header on every POST, PUT, PATCH and DELETE |
| URL types | Pages return HTML, `/api/...` returns JSON, `/fragments/...` returns HTML partials |
| Pagination | `?cursor&limit=25` returns `{items, next_cursor}` |

### Enums

Defined once in `database/models/enums.py`.

| Enum | Values |
|---|---|
| Role | `CADET`, `CADET_LEADER`, `JUO`, `ANO`, `CO` |
| Rank | `CADET`, `LCPL`, `CPL`, `SGT`, `CQMS`, `CSM`, `JUO`, `SUO`, `OFFICER` |
| ScopeType | `SELF`, `SQUAD`, `COMPANY`, `CONTINGENT`, `BATTALION` |
| AttendanceStatus | `PRESENT`, `ABSENT`, `LEAVE`, `LATE` |
| SheetStatus | `DRAFT`, `SUBMITTED`, `JUO_REVIEWED`, `ANO_APPROVED`, `LOCKED` |
| LeaveStatus | `PENDING_LEADER`, `PENDING_JUO`, `PENDING_ANO`, `PENDING_CO`, `APPROVED`, `REJECTED`, `CANCELLED` |
| ExamLevel | `A`, `B`, `C` |

Role to default scope:

| Role | Default scope |
|---|---|
| Cadet | `SELF` |
| Cadet Leader | `SQUAD` |
| JUO | `COMPANY` |
| ANO | `CONTINGENT` |
| CO | `BATTALION` |

Rank and role are stored separately.

### WebSocket event format

Only format on `/ws`:

```json
{"event","scope_type","scope_id","entity","entity_id","actor_id","at"}
```

Events:

- `attendance.updated`
- `leave.updated`
- `notice.created`
- `dashboard.refresh`
- `presence.updated`

The payload carries no record data, so the browser re-fetches the fragment and the server re-checks permissions.

## 1. Member 3 (Database): provides

Every table has `id`, `unit_id`, `contingent_id`, `created_at`, `updated_at`.

| Group | Tables |
|---|---|
| Org | `unit`, `contingent`, `company`, `squad` |
| People | `user`, `cadet_profile`, `role_assignment`, `rank_history` |
| Attendance | `parade`, `attendance_sheet` (unique parade + squad), `attendance_record` (unique sheet + cadet) |
| Leave | `leave_request`, `approval_step` |
| Comms | `notice`, `notice_receipt` |
| Other | `exam_resource`, `audit_log` (append-only) |
| Added for M1 | `refresh_token`, `otp_code` |

Code interfaces:

| Item | Detail |
|---|---|
| `get_db()` | Sync session dependency |
| `python -m database.seed` | 1 battalion, 2 contingents, about 60 cadets, one login per role |
| Seed logins | `cadet@`, `leader@`, `juo@`, `ano@`, `co@cadence.test` |

### APIs

| Endpoint | Roles | Notes |
|---|---|---|
| `GET /api/org/tree` | ANO, CO | Contingents, companies, squads |
| `POST /api/org/{contingents,companies,squads}` | ANO (CO for contingents) | `{name, parent_id}` |
| `GET /api/cadets` | JUO and above | Filters `squad_id`, `company_id`, `rank`, `q` |
| `GET /api/cadets/{id}` | Self or by scope | |
| `POST /api/cadets` | ANO | Sets `must_change_password` |
| `PATCH /api/cadets/{id}/rank` | ANO | Writes rank history and audit |
| `PATCH /api/cadets/{id}/role` | ANO | |
| `POST /api/cadets/{id}/move` | ANO | `{to_squad_id}`, used by drag-drop |
| `POST /api/cadets/import` | ANO | CSV, returns `{imported, failed, errors[{row, field, message}]}` |
| `GET /api/cadets/import/template` | ANO | CSV download |
| `/api/exam-resources` (`GET`, `POST`, `PATCH`, `DELETE`) | GET: any and Guest; write: ANO, CO | Links only |

CSV columns: `full_name`, `email`, `phone`, `cadet_no`, `rank`, `division`, `company`, `squad`, `enrollment_date`, `guardian_name`, `guardian_phone`.

M3 consumes: `can()` and `publish()` from M1.

## 2. Member 1 (Backend): provides

Interfaces:

| Item | Signature |
|---|---|
| Permission check | `can(user, action, resource) -> bool`, and `require(action)` as a dependency |
| Realtime | `publish(event, scope_type, scope_id, entity, entity_id, actor_id)` |
| Audit | `write_audit(db, actor, action, entity_type, entity_id, before, after, reason)`, written in the same transaction |

Actions: `attendance.mark`, `attendance.review`, `attendance.approve`, `attendance.edit_locked`, `leave.apply`, `leave.forward`, `leave.decide`, `notice.publish`, `roster.manage`, `rank.assign`, `report.export`, `audit.view`, `exam_resource.manage`.

### Auth and MFA

| Endpoint | Notes |
|---|---|
| `POST /auth/login` | Redirects to MFA or change-password when needed |
| `POST /auth/logout`, `/auth/refresh` | Refresh token rotates |
| `POST /auth/change-password` | `{current_password, new_password}` |
| `POST /auth/reset/{user_id}` | ANO only, emails a temporary password |
| `GET /auth/mfa/setup`, `POST /auth/mfa/setup/confirm` | TOTP with QR. Mandatory for ANO and CO |
| `POST /auth/mfa/verify`, `/auth/mfa/email-otp` | `{code}` or `{method:"email"}`; email OTP lasts 10 min |

### Attendance

| Endpoint | Role | Result |
|---|---|---|
| `POST /api/parades` | ANO | Creates draft sheets per squad |
| `GET /api/parades` | by scope | |
| `GET /api/attendance/sheets/{id}` | by scope | Sheet with `records[]`, `timeline[]`, `allowed_actions[]` |
| `PUT /api/attendance/sheets/{id}/records` | Leader | While in `DRAFT` |
| `POST /api/attendance/sheets/{id}/submit` | Leader | `409` if already submitted |
| `POST /api/attendance/sheets/{id}/review` | JUO | `FORWARD` or `RETURN` |
| `POST /api/attendance/sheets/{id}/approve` | ANO | `APPROVE` or `RETURN`, then auto-`LOCKED` |
| `POST /api/attendance/sheets/{id}/edit-locked` | ANO | Reason required, audited |
| `GET /api/attendance/me` | Cadet | Percentage and history |

State machine: `DRAFT` -> `SUBMITTED` -> `JUO_REVIEWED` -> `ANO_APPROVED` -> `LOCKED`. Returns go back to `DRAFT`. A stale version returns `409`.

### Leave

| Endpoint | Role |
|---|---|
| `POST /api/leave` | Cadet |
| `GET /api/leave`, `GET /api/leave/{id}` | by scope |
| `POST /api/leave/{id}/forward` | Leader, JUO |
| `POST /api/leave/{id}/decide` | ANO (CO when `PENDING_CO`); approval auto-marks `LEAVE` in attendance |
| `POST /api/leave/{id}/escalate` | ANO |
| `POST /api/leave/{id}/cancel` | Cadet, while pending |

### Notices, reports, audit

| Endpoint | Notes |
|---|---|
| `POST /api/notices` | `{title, body, target_scope_type, target_scope_id, is_public}` |
| `GET /api/notices`, `POST /api/notices/{id}/read` | Includes `unread_count` |
| `GET /api/public/notices` | No auth, for Guest |
| `GET /api/me/bell` | `{unread_notices, pending_actions}` |
| `GET /api/reports/attendance`, `/api/reports/absentees`, `/api/reports/leave-stats` | `format=json` |
| `GET /api/audit` | ANO (own contingent), CO (all) |

Jobs and email: weekly report every Monday 08:00 IST to ANO and CO. Email templates: `otp`, `verify`, `password_reset`, `leave_decision`, `weekly_report`.

WebSocket `/ws`: cookie auth, close code `4401` if invalid. Rooms are `user`, `squad`, `company`, `contingent`, `battalion`, and users join only rooms inside their scope. Client sends `presence.join` or `presence.leave` with `{entity, entity_id}`. Server broadcasts `presence.updated` with `viewers[{name, role}]`.

M1 consumes: schema and `get_db()` from M3, and template names from M2.

## 3. Member 2 (Frontend): provides

### Pages

Every page also gets `user`, `nav_items`, `csrf_token`, `bell`.

| Route | Template | Context keys |
|---|---|---|
| `/dashboard/cadet` | `dashboards/cadet.html` | `attendance_pct`, `next_parade`, `unread_notices`, `leave_summary`, `charts` |
| `/dashboard/leader` | `cadet_leader.html` | `squad`, `pending_sheets`, `pending_leave`, `absentees_today`, `charts` |
| `/dashboard/juo` | `juo.html` | `company`, `sheets_to_review`, `leave_queue`, `charts` |
| `/dashboard/ano` | `ano.html` | `contingent`, `approvals_pending`, `roster_counts`, `charts` |
| `/dashboard/co` | `co.html` | `battalion`, `contingent_comparison`, `escalations`, `charts` |
| `/attendance/sheet/{id}` | `marking_sheet.html` or `approval.html` | `sheet` |
| `/attendance/review`, `/attendance/history` | `review_list.html`, `history.html` | `items`, `filters`; `percentage`, `items` |
| `/leave/apply`, `/leave`, `/leave/{id}` | `apply.html`, `queue.html`, `detail.html` | `items`, `leave` |
| `/notices`, `/notices/new` | `inbox.html`, `create.html` | `items`, `unread_count`; `scope_options` |
| `/exam-resources` | `list.html` | `items`, `levels`, `can_manage` |
| `/reports` | `reports/index.html` | `filters`, `level_options`, `download_links` |
| `/admin/roster`, `/admin/import`, `/admin/squads` | `roster`, `csv_upload`, `squad_board` | `cadets`, `import_result`, `org_tree` |
| `/admin/audit` | `audit_log.html` | `items`, `filters`, `next_cursor` |
| `/` | `guest/home.html` | `public_notices`, `exam_resources` |
| errors | `errors/403`, `404`, `500.html` | `message` |

### Fragments

| Route | Event | Element |
|---|---|---|
| `/fragments/dashboard/cards` | `dashboard.refresh` | `#stat-cards` |
| `/fragments/attendance/sheet/{id}/body` | `attendance.updated` | `#sheet-{id}` |
| `/fragments/attendance/sheet/{id}/timeline` | `attendance.updated` | `#timeline-{id}` |
| `/fragments/leave/queue` | `leave.updated` | `#leave-queue` |
| `/fragments/leave/{id}/timeline` | `leave.updated` | `#timeline-{id}` |
| `/fragments/notices/list` | `notice.created` | `#notice-list` |
| `/fragments/bell` | `any` | `#bell` |
| `/fragments/presence/{entity}/{id}` | `presence.updated` | `#presence-{id}` |

### Analytics

M2 owns these endpoints:

| Endpoint | Returns |
|---|---|
| `GET /api/analytics/attendance`, `/api/analytics/leave` | Chart JSON, with `level`, `scope_id`, `from`, `to` |
| `GET /api/analytics/drill-table` | HTML table fragment |

Chart JSON:

```json
{"labels":["..."],"datasets":[{"label":"...","data":[...] }],"drill":{"level":"...","next_level":"...","ids":["..."]}}
```

Clicking bar `i` loads the drill table with `level = next_level` and `scope_id = ids[i]`. Levels: `battalion`, `contingent`, `company`, `squad`, `cadet`.

### Static scripts

- `ws.js`: connects with backoff, maps event to element, `htmx.trigger`, toast, bell, presence.
- `charts.js`: `renderChart`, bar-click drill-down.
- `scroll-cache.js`: saves and restores scroll per URL in `sessionStorage`.
- `dnd.js`: SortableJS squad board calling `/move`, reverts on error; CSV drop zone.
- `toast.js`, `presence.js`: `showToast(type, msg)`, viewer badge.

UI rule: show buttons only for actions listed in `allowed_actions[]`, and never compute permissions in templates.

M2 consumes: all M1 and M3 APIs above, plus `timeline[]` and `allowed_actions[]`.

## 4. Dependencies and change rules

| Needed | From | To | Deadline |
|---|---|---|---|
| Enums, tables, `get_db()`, migration | M3 | M1, M2 | Day 1, 2h |
| `refresh_token` and `otp_code` tables | M1 asks | M3 | Day 0 |
| Seed logins | M3 | M1, M2 | Day 1, 4h |
| Auth routes and template names | M1 | M2 | Day 1, 4h |
| `can()` and `require()` | M1 | M2, M3 | Day 1, 6h |
| Import and move endpoint shapes | M3 | M2 | Day 1, 8h |
| `/ws` and `publish()` | M1 | M2, M3 | Day 1, 10h |

1. Contract changes go through a PR first, never in code first.
2. Adding a field is safe. Renaming or removing one needs both consumers' approval.
3. Enums and action names freeze after Day 1, 2h.
