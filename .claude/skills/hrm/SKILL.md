---
name: hrm
description: Work on the HRM module (Module 3 — 3.1 employees, 3.2 designations/org structure, 3.9 attendance/shifts, 3.10 leave management, 3.12 holidays). Use when the user asks to add/change/debug anything under apps/hrm or templates/hrm, extend the seed_hrm seeder, touch HRM sidebar wiring (LIVE_LINKS 3.1/3.2/3.9/3.10/3.12), or invokes /hrm.
---

# HRM — Human Resource Management (Module 3)

First pass of NavERP Module 3. App path: `apps/hrm/`, templates: `templates/hrm/`, URL prefix `/hrm/`
(`app_name = "hrm"`). Built sub-modules: **3.1 Employee Management, 3.2 Organizational Structure,
3.9 Attendance Management, 3.10 Leave Management, 3.12 Holiday Management.** Reuses the unified core spine —
an **employee is a `core.Party` (person) + `core.Employment`**; departments reuse `core.OrgUnit`. Payroll GL
posting stays with **`accounting.PayrollRun`** (HRM does not duplicate it).

## Overview
Tenant-scoped employee directory + leave + attendance for the demo tenants. Everything filters by
`request.tenant`. Derived figures (leave balance, leave days, attendance hours) are computed, never stored
editable. Recruiting/payroll/performance are deferred to later passes (see "Deferred").

## Models (`apps/hrm/models.py`) — 9 tables
All inherit local abstract bases (mirror crm/accounting; peer apps don't import each other):
- `TenantOwned` — `tenant` FK (`related_name="+"`) + `created_at`/`updated_at`.
- `TenantNumbered(TenantOwned)` — adds auto per-tenant `number` via `core.utils.next_number` with a 5-retry
  collision guard. Set `NUMBER_PREFIX` on the subclass.

| Model | Number | Key fields | Reuses core / notes |
|-------|--------|-----------|---------------------|
| `Designation` | — | name, grade, department→`core.OrgUnit`, min/max_salary, is_active | `clean()`: min_salary ≤ max_salary. `unique_together=(tenant,name)` |
| `EmployeeProfile` | `EMP-` | party→`core.Party`(1:1), employment→`core.Employment`(1:1), designation→`Designation`, employee_type, gender, dob, blood_group, nationality, personal_email, mobile, bank_*, probation_end_date, confirmed_on, emergency_*, photo, notes | **The anchor — every other HRM model FKs here, not to core.Party.** Props: `department`/`manager` (via employment), `name` (party.name), `masked_bank_account()` |
| `LeaveType` | — | name, code, is_paid, accrual_rule(none/monthly/annual), accrual_days, max_balance, max_carry_forward, encashable, is_active | `clean()`: accrual_days>0 when accruing. `unique_together=(tenant,code)` |
| `LeaveAllocation` | `LA-` | employee, leave_type, year, allocated_days, note, status(draft/active/expired) | `used_days`/`balance` are **derived properties** (sum of approved requests); `unique_together` also on (tenant,employee,leave_type,year) |
| `LeaveRequest` | `LR-` | employee, leave_type, start_date, end_date, **days**(editable=False), reason, status(draft/pending/approved/rejected/cancelled), approver, approved_at, rejected_reason, cancelled_reason | `save()` recomputes `days` from range minus non-optional holidays; `clean()`: end ≥ start. `OPEN_STATUSES=(draft,pending)` |
| `PublicHoliday` | — | date, name, is_optional | non-optional holidays excluded from leave `days`; `unique_together=(tenant,date,name)` |
| `Shift` | — | name, start_time, end_time, grace_minutes, is_default, is_active | overnight shifts allowed (end < start) |
| `ShiftAssignment` | — | employee, shift, effective_from, effective_to(null=ongoing) | `clean()`: effective_to ≥ effective_from; `unique_together=(tenant,employee,effective_from)` |
| `AttendanceRecord` | `ATT-` | employee, date, check_in, check_out, **hours_worked**(editable=False), shift, status(present/absent/half_day/on_leave/holiday/regularized), source(web/mobile/biometric/manual), notes | `save()` recomputes `hours_worked` (handles overnight); `is_late()` (minutes-of-day vs shift start+grace); `unique_together` also (tenant,employee,date) |

**Derived-not-stored:** never set `LeaveRequest.days`, `AttendanceRecord.hours_worked`, or
`LeaveAllocation.used_days/balance` from a form — they're computed in `save()`/properties. For list views, use
the `used_days_db`/`balance_db` annotations from `views._used_days_subquery()` (avoids per-row N+1), not the model
properties.

## URLs / routes (`apps/hrm/urls.py`, `app_name="hrm"`)
- Landing: `hrm:hrm_overview` (`/hrm/`).
- Per model `<entity>` in {`designation`, `employee`, `leavetype`, `leaveallocation`, `leaverequest`,
  `publicholiday`, `shift`, `shiftassignment`, `attendancerecord`}: `<entity>_list/_create/_detail/_edit/_delete`.
- Leave workflow extras: `hrm:leaverequest_submit/_approve/_reject/_cancel` (all POST-only).

## Views (`apps/hrm/views.py`)
Function-based, `@login_required`, tenant-scoped, built on `apps.core.crud` helpers
(`crud_list/_create/_edit/_delete`). Notes:
- `hrm_overview` — headcount / new-this-month / on-leave-today / present/absent-today stat cards + pending leave +
  upcoming holidays.
- `employee_detail` — personal/employment cards, masked bank, current-year leave balances (annotated), recent
  attendance, current shift, recent leave requests.
- Leave workflow: `submit`(draft→pending), `approve`(→approved, sets approver/approved_at, flips attendance in
  window to on_leave), `reject`(→rejected+reason), `cancel`(→cancelled, reverts on_leave attendance to present).
  **`approve`/`reject` are `@tenant_admin_required`; `submit`/`cancel` are `@login_required`.**
- Delete guards: active employee, in-use leave type, in-use shift, in-use designation all block deletion.
- Attendance date-range filter parses GET dates with `_parse_iso_date` (malformed input ignored, no 500).

## Templates (`templates/hrm/`)
28 files: `hrm_overview.html` + list/detail/form per model. Extend `base.html`, use the design-system classes
(`page-header/card/table/badge/form-*/empty-state`), `partials/pagination.html`. Conventions: search `q` + filter
selects pre-filled from `request.GET`; FK filters compare `obj.pk|stringformat:"d"`; boolean filters use
`"True"/"False"`; badges use exact model choice values with `{{ obj.get_<field>_display }}` fallback; every list
has an Actions column (view/edit/delete-POST+csrf+confirm). **Never render raw `bank_account` — use
`masked_bank_account`.** `employee_form.html` is `multipart/form-data` (photo).

## Forms (`apps/hrm/forms.py`)
`TenantModelForm` subclasses (auto tenant-scope FK querysets, theme widgets). Exclude `tenant`, auto `number`, and
computed fields. **SECURITY: `LeaveRequestForm` excludes `status` and `approver`** (set only by workflow actions —
prevents self-approval via crafted POST). `EmployeeProfileForm` scopes `party` to person Parties and validates the
photo (`clean_photo`: jpg/jpeg/png/webp/gif allowlist + 5 MB cap).

## Seeder (`apps/hrm/management/commands/seed_hrm.py`)
`venv\Scripts\python.exe manage.py seed_hrm` (`--flush` to wipe+reseed). Idempotent (skips a tenant that already
has `EmployeeProfile` rows). Per tenant: 3 designations, up to 5 employees **reusing existing `core.Party`
persons** (tops up with unique names if too few), 4 leave types + allocations, 2 leave requests (1 approved/1
pending), 5 holidays, 2 shifts + assignments, 5 attendance rows/employee. Login as `admin_acme` / `admin_globex`
(password `password123`); superuser `admin` has no tenant and sees nothing.

## Sidebar wiring (`apps/core/navigation.py` `LIVE_LINKS`)
- 3.1: Employee Directory/Profile/Employment Details → `hrm:employee_list`; + HRM Overview → `hrm:hrm_overview`.
- 3.2: Designation/Job Titles → `hrm:designation_list`; Department Management → `core:orgunit_list`.
- 3.9: Check-in/Check-out + Attendance Calendar → `hrm:attendancerecord_list`; Shift Management → `hrm:shift_list`;
  + Shift Assignments → `hrm:shiftassignment_list`.
- 3.10: Leave Types → `hrm:leavetype_list`; Leave Balance → `hrm:leaveallocation_list`; Leave Application + Leave
  Calendar → `hrm:leaverequest_list`.
- 3.12: Holiday Calendar → `hrm:publicholiday_list`.

## Conventions & gotchas
- An employee is `core.Party(kind=person)` + `core.Employment` + `hrm.EmployeeProfile` (1:1:1). Create the Party
  first; `EmployeeProfile.party` is required.
- `EmployeeProfile.department`/`manager` are read-only properties off the linked Employment — set them on the
  Employment, not the profile.
- `core.Employment` has a `(tenant, status)` index (added for `employee_list` status filtering).
- Sensitive fields (`bank_account`, `bank_routing`) are redacted from `AuditLog.changes` via
  `core.crud._SENSITIVE_AUDIT_FIELDS`; still plaintext at rest (documented WARNING — encrypt in a later pass).

## Common tasks
- **Add a field to a model:** edit `models.py` → add to the relevant `forms.py` `fields` (unless computed) → render
  in `_detail.html`/`_form.html` → `makemigrations hrm` + `migrate` → extend `seed_hrm` if useful → add a test.
- **Add a new model + CRUD:** model (inherit `TenantOwned`/`TenantNumbered`) → form → 5 views via `crud_*` helpers
  → 5 url names → admin → 3 templates → `LIVE_LINKS` entry → seeder → tests.
- **Add a filter:** pass the choice/queryset in the view's `extra_context`, add `(param, lookup, is_int)` to the
  `crud_list` `filters`, render the `<select>` pre-filled from `request.GET` (FK → `|stringformat:"d"`).
- **Extend the seeder:** add a block guarded by the existing `EmployeeProfile.exists()` check, `get_or_create` on a
  natural key; keep it idempotent and reuse core Parties.

## Deferred (later HRM passes — see `.claude/tasks/todo.md`)
Salary structure + payroll/payslip (FK into `accounting.PayrollRun`, do NOT duplicate GL), recruiting/ATS
(3.5–3.8), onboarding/offboarding (3.3/3.4), performance/goals (3.18/3.19), timesheets (3.11, coordinate with
`accounting.Project`), statutory/tax (3.13–3.17), attendance regularization & geofencing, optional-holiday
selection, leave carry-forward/encashment batch, employee self-service portal, and a per-employee↔user link for
ownership-scoped leave actions (currently any tenant member can submit/cancel; approve/reject are admin-only).
