# Cadence – Backend Functional Specification

**Document:** SPEC.md
**Project:** Cadence – NCC Operations Management Platform
**Version:** 0.1
**Status:** Initial Draft – Subject to Team Review

## 1. Project Overview

Cadence is an NCC operations management platform designed to digitize and streamline unit-level administrative and operational activities.

The backend will provide:
- Secure authentication and role-based access control.
- Cadet profile and squad management.
- Digital attendance and attendance approvals.
- Leave requests and approval escalation.
- Notices and task management.
- Scheduling and operational coordination.
- Real-time notifications and updates.
- Reports, analytics and audit logs.

## 2. Scope

Initial deployment: One NCC unit.

The platform will organize information through the following hierarchy:

Unit → Squads → Cadets → Activities / Parades / Tasks

All access must be enforced on the backend using role, assigned scope and requested action.

Users must not be able to access records outside their authorized scope by changing request parameters.

## 3. User Roles

The working five-role model is:

| Role | Description |
|---|---|
| CO | Commanding Officer; overall unit authority |
| ANO | Associate NCC Officer; administrative and approval authority |
| JUO | Junior Under Officer; reviews and supervises delegated operations |
| Leader | Squad-level leadership and operational responsibilities |
| Cadet | Individual cadet and platform user |

Final role names and hierarchy must be confirmed with the team.

## 4. Permission Matrix

| Function | CO | ANO | JUO | Leader | Cadet |
|---|---|---|---|---|---|
| Manage unit | Yes | Delegated | No | No | No |
| Manage cadets | Yes | Yes | Scoped | Scoped | Own profile |
| View attendance | Unit | Unit | Scoped | Squad | Own |
| Submit attendance | Yes | Yes | Yes | Yes | No |
| Review attendance | Yes | Yes | Yes | Scoped | No |
| Approve attendance | Yes | Yes | Review only | No | No |
| Submit leave | Yes | Yes | Yes | Yes | Own |
| Review leave | Yes | Yes | Yes | Delegated | No |
| Final leave approval | Yes | Yes | No | No | No |
| Manage notices | Yes | Yes | Delegated | No | No |
| View reports | Unit | Unit | Scoped | Scoped | Own |
| View audit logs | Yes | Authorized | No | No | No |

**Important:** This matrix is an initial proposal. Exact approval authority, especially for Leader and JUO, must be confirmed before implementation.

## 5. Authentication and Security

The backend must implement:

- Argon2 password hashing.
- JWT access and refresh tokens.
- HTTP-only secure cookies.
- CSRF protection.
- Refresh-token rotation.
- Login rate limiting.
- Forced password change when required.
- ANO-initiated password reset.
- TOTP-based MFA.
- Email OTP fallback.
- Mandatory MFA for ANO and CO.
- Role and scope-based authorization.
- Audit logging for sensitive operations.

All protected routes must include server-side permission checks.

## 6. Attendance Management

### Attendance states

`DRAFT → SUBMITTED → JUO_REVIEWED → ANO_APPROVED → LOCKED`

### Requirements

1. Authorized users can create a parade or attendance session.
2. Squad leaders submit attendance for their assigned cadets.
3. Duplicate attendance entries must be rejected.
4. JUO reviews submitted attendance.
5. ANO approves attendance.
6. Approved attendance is locked.
7. Editing locked attendance requires an authorized user and a mandatory reason.
8. Every state transition must generate an audit record.
9. State changes and audit records must be committed in the same database transaction.
10. Successful changes publish real-time events after transaction commit.

## 7. Leave Management

### Requirements

- Cadets can submit leave requests.
- Requests must include the reason and requested dates.
- Authorized leaders review requests.
- Requests escalate through JUO and ANO according to the configured approval policy.
- CO handles escalated requests where required.
- Approved leave must automatically update the applicable attendance/presence records.
- Rejected requests must retain their rejection reason.
- All decisions must be recorded in audit history.

The exact escalation and delegation rules must be finalized with the team.

## 8. Notices and Tasks

### Notices

- Authorized officers can create and publish notices.
- Notices can be targeted to the whole unit or selected squads.
- Cadets can view notices within their scope.
- Notice creation and updates generate events.

### Tasks

Tasks must support:

`ASSIGNED → IN_PROGRESS → SUBMITTED → UNDER_REVIEW → APPROVED / REJECTED / COMPLETED`

Requirements:
- Task assignment to individuals or squads.
- Due dates and descriptions.
- Submission and review.
- Rejection with feedback.
- Task history and audit records.
- Real-time status updates.

## 9. WebSocket and Real-Time Events

Endpoint:

`/ws`

Requirements:
- Authenticate connections using the session cookie.
- Verify the user's identity and authorization.
- Restrict users to authorized rooms and scopes.
- Prevent unauthorized event subscriptions.
- Publish events after successful database commits.
- Disconnect or reject unauthorized connections.

### Initial event names

| Event | Purpose |
|---|---|
| `attendance.created` | New attendance session |
| `attendance.submitted` | Squad attendance submitted |
| `attendance.reviewed` | JUO review completed |
| `attendance.approved` | ANO approval completed |
| `attendance.locked` | Attendance locked |
| `leave.submitted` | Leave request submitted |
| `leave.reviewed` | Leave reviewed |
| `leave.approved` | Leave approved |
| `leave.rejected` | Leave rejected |
| `notice.created` | New notice |
| `task.assigned` | Task assigned |
| `task.updated` | Task status updated |

Event payloads must contain only the information authorized recipients need.

## 10. Audit Logging

The backend must maintain an audit trail for:

- Authentication and security-sensitive actions.
- Account and role changes.
- Attendance creation and modification.
- Attendance approval and locking.
- Leave submission and decisions.
- Task assignment and review.
- Notice publication.
- Administrative actions.

Each audit record should capture:

- Actor ID.
- Action.
- Resource type and ID.
- Previous state, where applicable.
- New state, where applicable.
- Timestamp.
- Reason, where required.

Audit history must not be editable through normal application APIs.

## 11. Reports and Scheduling

### Reports
- Attendance reports.
- Leave reports.
- Cadet participation reports.
- Squad-level summaries.
- CSV export.
- Weekly report emails.

### Scheduling
- Parade and activity scheduling.
- Conflict detection.
- Cadet, squad, instructor and venue availability checks.
- Prevention of overlapping bookings.

## 12. Preliminary API Route List

### Authentication
- `POST /auth/login`
- `POST /auth/logout`
- `POST /auth/refresh`
- `POST /auth/change-password`
- `POST /auth/reset-password`
- `POST /auth/mfa/setup`
- `POST /auth/mfa/verify`

### Attendance
- `POST /attendance/parades`
- `GET /attendance/parades`
- `GET /attendance/parades/{id}`
- `POST /attendance/{id}/submit`
- `POST /attendance/{id}/review`
- `POST /attendance/{id}/approve`
- `POST /attendance/{id}/lock`
- `PATCH /attendance/{id}/records/{record_id}`

### Leave
- `POST /leave`
- `GET /leave`
- `GET /leave/{id}`
- `POST /leave/{id}/review`
- `POST /leave/{id}/approve`
- `POST /leave/{id}/reject`

### Notices
- `POST /notices`
- `GET /notices`
- `GET /notices/{id}`
- `PATCH /notices/{id}`

### Reports
- `GET /reports/attendance`
- `GET /reports/leave`
- `GET /reports/participation`
- `GET /reports/attendance/export`

### Real-time
- `WS /ws`

These routes are preliminary and must be aligned with M2's frontend requirements and M3's database schema.

## 13. Testing Requirements

- Authentication and token tests.
- Password hashing tests.
- MFA verification tests.
- Permission matrix tests for all five roles.
- Scope isolation tests.
- Attendance state-transition tests.
- Duplicate attendance tests.
- Leave escalation tests.
- Audit transaction tests.
- WebSocket authentication and room isolation tests.
- API integration tests.
- CSV export tests.

## 14. Non-Functional Requirements

- Secure password storage.
- Backend-enforced authorization.
- Consistent error responses.
- Database transaction integrity.
- Reliable real-time event delivery.
- Maintainable modular architecture.
- Automated testing.
- No sensitive credentials committed to Git.

## 15. Team Integration

**Member 1 – Backend**
- Authentication, authorization, business logic, WebSockets, audit logging and reports.

**Member 2 – Frontend**
- Dashboard, user interfaces, API integration and real-time UI updates.

**Member 3 – Database**
- Database schema, relationships, migrations and data integrity.

### Integration checkpoints

1. Authentication routes and frontend login integration.
2. WebSocket connection and event integration.
3. Attendance and leave event integration.
4. Final permission and scope validation.

---

**End of Specification – Version 0.1**
