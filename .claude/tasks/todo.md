---
# HRM 3.10 Leave Management — completion pass (Leave Policy engine + Encashment)  (2026-07-03)

**Context.** 3.10 was previously built (LeaveType / LeaveAllocation / LeaveRequest / PublicHoliday, full CRUD +
approve workflow, `LIVE_LINKS["3.10"]`). Of NavERP.md's 5 bullets, **"Leave Policy" (accrual / carry-forward /
encashment) is the only one not built as a distinct feature** — the rules exist as config on `LeaveType`, but there
is no engine that runs accrual/carry-forward and no standalone encashment workflow (`compute_leave_encashment` is
offboarding-only). This pass completes 3.10 with a policy **engine** + an **encashment** workflow. Extending
`apps/hrm` — NOT a new app.

## New model (1) + 1 field

### `LeaveEncashment` (ENC-…) — the encashment request workflow
- `number` ENC-#### (TenantNumbered), `employee` → EmployeeProfile, `leave_type` → LeaveType (must be encashable)
- `year`, `days`, `rate_per_day`, `amount` (editable=False, = days × rate_per_day in save())
- status `draft → pending → approved → paid` (+ `rejected`, `cancelled`); `OPEN_STATUSES=(draft,pending)`
- `approver`(User SET_NULL), `approved_at`, `paid_on`, `payment_reference`, `decision_note`
- `clean()`: days > 0; leave_type must be `encashable`; days ≤ available balance for (employee, leave_type, year)
- workflow views: submit (owner) / approve+reject+mark_paid (`@tenant_admin_required`) / cancel (owner)
- **on approve** (atomic): reduce the matching `LeaveAllocation.allocated_days` by `days` (encashment consumes leave)

### `LeaveAllocation.carried_forward` (Decimal, editable=False, default 0)
- records days rolled in from the prior year (part of allocated_days) → makes carry-forward idempotent + auditable

## Policy engine (no model — standalone page + admin run actions)
- `leave_policy` (GET): lists LeaveTypes + their accrual/carry-forward/encashment config + a year selector and the
  two run actions; shows a current-year allocation summary.
- `leave_accrual_run` (POST, `@tenant_admin_required`): per active employee × accruing LeaveType, set
  `allocated_days = accrued(year) + carried_forward` (annual→accrual_days; monthly→accrual_days×months_elapsed),
  capped at `max_balance`. Idempotent per run.
- `leave_carryforward_run` (POST, `@tenant_admin_required`): source year → year+1, `carry = min(max(balance,0),
  max_carry_forward)`; set `dst.allocated_days = (dst.allocated_days − dst.carried_forward) + carry`,
  `dst.carried_forward = carry`. Idempotent.

## Build checklist
- [ ] models: `LeaveEncashment` + `LeaveAllocation.carried_forward`
- [ ] forms: `LeaveEncashmentForm` (workflow fields excluded)
- [ ] views: encashment CRUD + submit/approve/reject/mark_paid/cancel; `leave_policy` + accrual/carry-forward runs
- [ ] urls: `leave-encashments/…` (+ workflow) ; `leave-policy/` + `…/accrual-run/` + `…/carry-forward-run/`
- [ ] admin: register `LeaveEncashment`
- [ ] navigation: `LIVE_LINKS["3.10"]` += Leave Policy (`leave_policy`) + Leave Encashment (extra)
- [ ] templates: `leave/encashment/{list,detail,form}.html`, `leave/policy.html` (standalone); show carried_forward on allocation detail
- [ ] seeder: seed 1–2 encashment requests; carried_forward defaults 0
- [ ] migrate + seed (x2 idempotent) + `manage.py check`
- [ ] verify: smoke script — new urls 200/302, accrual/carry-forward runs mutate allocations idempotently, encashment approve reduces allocated_days, cross-tenant 404
- [ ] review agents: code-reviewer → explorer → frontend-reviewer → performance-reviewer → qa-smoke-tester → security-reviewer → test-writer
- [ ] update `.claude/skills/hrm/SKILL.md` 3.10 section

## Review — delivered 2026-07-03

**Scope built.** Completed HRM 3.10 by adding the missing "Leave Policy" bullet as a working engine + an encashment
workflow. New `LeaveEncashment` (`ENC-`, draft→pending→approved→paid/rejected/cancelled; approve consumes balance)
+ `LeaveAllocation.carried_forward`/`encashed_days` fields. **Leave Policy engine** (`leave_policy` page, no model):
admin `leave_accrual_run` (annual grant / monthly rate×elapsed-months, capped at max_balance) and
`leave_carryforward_run` (min(balance, max_carry_forward) → next year), both idempotent + atomic + audit-logged.
Wired into `LIVE_LINKS["3.10"]` (all 5 bullets live + Encashment extra), admin, seeder (2 encashments/tenant),
2 migrations (0020 model+carried_forward, 0021 encashed_days).

**Key correctness insight (encashed_days).** Encashment approve records days in a **separate `encashed_days`** field,
not by shrinking `allocated_days` — because the accrual engine recomputes `allocated_days`, and reducing it directly
would let a routine accrual re-run silently restore cashed-out days (double-spend). `balance = allocated − used −
encashed`; carry-forward and offboarding both net out encashed days.

**Review-agent sequence (all applied + committed):**
- code-reviewer → 4: AuditLog.action truncation (10-char field → verb moved to `changes`); carry-forward dest-year
  `max_balance` cap; `LeaveAllocationForm` resets `carried_forward` on manual edit; `_accrual_target` 0 months for a
  future year.
- explorer → **double-spend bug** (accrual re-run restored encashed days) fixed via the `encashed_days` field; carry-
  forward + `compute_leave_encashment` net encashed days; allocation↔encashment cross-link; pending-encashments KPI.
- frontend-reviewer → 1 (always-render the allocation-detail Encashments card with an empty-state); else clean.
- performance-reviewer → clean (no N+1s; engine `get_or_create`-in-loop is O(employees×types), demo-acceptable —
  deferred the bulk_create/bulk_update rewrite as a scaling note).
- qa-smoke-tester → clean (independent migrate+seed+engine/workflow sweep, double-spend regression confirmed).
- security-reviewer → 1 applied (bound `_policy_year` to 2000–2100 vs oversized-year DB 500); 1 **rejected** (adding
  `tenant=` to `LeaveEncashment.clean()` would filter tenant=None pre-validation on create and break it — not
  exploitable, employee_id is already tenant-bound).
- test-writer → **102 tests** in `test_leave_encashment_and_policy.py`; HRM suite **1,775** green, project-wide **4,422**.

**Skill/README** updated (table 45→46, LeaveEncashment + LeaveAllocation fields, routes/engine actions, template
folders, LIVE_LINKS 3.10, seeder, Deferred pruned + scaling/offboarding notes; test counts refreshed).

**Deferred (future 3.10 passes):** engine bulk-write rewrite (prefetch-dict + bulk_create/bulk_update, pre-assigning
LA- numbers) or background task before ~hundreds of employees; auto-cancel/net open (draft/pending) encashments on
separation so final settlement can't double-pay (spawned as a background task); per-employee↔user ownership scoping
on request/encashment creation (app-wide convention).

**Next unbuilt sub-module:** 3.11 Time Tracking.

---
# HRM 3.11 Time Tracking — build plan from research-hrm-time-tracking.md (2026-07-03)

**Context.** Extends the existing `apps/hrm` app — **NOT a new app.** Skip `apps.py`/`INSTALLED_APPS`/
`config/urls.py` wire-up entirely (hrm is already installed and included). The only wire-up is one
`LIVE_LINKS["3.11"]` entry in `apps/core/navigation.py`. Mirrors the `LeaveRequest`/`LeaveEncashment`/
`AttendanceRegularization` status-machine + `TenantNumbered`/`TenantOwned` conventions exactly (see
`apps/hrm/models.py`). Source: `.claude/tasks/research-hrm-time-tracking.md`.

NavERP.md 3.11 bullets (exact text for `LIVE_LINKS`): **Timesheet** — Daily/weekly timesheet submission.
**Project Time Tracking** — Time logged against projects/tasks. **Billable Hours** — Client billing,
utilization reports. **Overtime Tracking** — OT calculation, approval, payment. **Timesheet Approval** —
Manager approval workflow.

## Models (from research — 3 models)

- [ ] **`Timesheet`** [`TS-`] (`TenantNumbered`, mirrors `LeaveRequest`) — weekly header.
  - `employee` FK `hrm.EmployeeProfile` (CASCADE, anchor — never `core.Party` directly)
  - `period_start`, `period_end` (`DateField`) — the week the sheet covers (drivers: "Daily/weekly timesheet
    submission" — Clockify/Zoho Projects/Harvest/Deel; daily-vs-weekly granularity P1 — Deel/Replicon/Clockify)
  - `status` (`draft/pending/approved/rejected/cancelled`), `OPEN_STATUSES = ("draft", "pending")` (driver:
    "Draft → submit → approved/rejected workflow" P0 — Harvest/Clockify/TimeCamp/BambooHR)
  - `approver` FK `settings.AUTH_USER_MODEL` (SET_NULL, null/blank), `approved_at` (DateTimeField, null/blank)
  - `decision_note` (TextField, blank), `rejected_reason` (TextField, blank) — rejection-with-comment +
    resubmission (driver: Zoho Projects/Clockify/TimeCamp)
  - `total_hours`, `billable_hours` (`DecimalField(max_digits=6, decimal_places=2, default=0, editable=False)`)
    — **derived/never hand-typed**, recomputed in a `refresh_totals()` helper called from `save()`/the entry
    add-remove views, summed from child `TimesheetEntry.hours` (driver: weekly aggregation, all 10 products;
    mirrors `LeaveRequest.days`/`AttendanceRecord.hours_worked`)
  - `Meta`: `unique_together = [("tenant", "number"), ("tenant", "employee", "period_start")]` — one timesheet
    per employee per week; indexes `(tenant, employee, status)`, `(tenant, status)`, `(tenant, period_start)`
  - `clean()`: `period_end >= period_start`
  - Reuses `hrm.EmployeeProfile` (anchor); no core-spine table added.

- [ ] **`TimesheetEntry`** (plain `TenantOwned`, child line — no own numbering, mirrors `LeaveAllocation`/
  `ClearanceItem` pattern of an un-numbered child row).
  - `timesheet` FK `hrm.Timesheet` (CASCADE, `related_name="entries"`)
  - `date` (`DateField`) — `clean()` must fall within the parent's `period_start`/`period_end`
  - `project` FK `accounting.Project` (**SET_NULL, null=True, blank=True**) — optional so admin/non-project
    time is loggable (driver: "Time entry tagged to a project" P0 — Harvest/Toggl/Zoho Projects/Replicon/
    TimeCamp; reuses the existing 2.9 job-costing spine instead of a new project table)
  - `task_description` (`CharField(max_length=255, blank=True)`) — free text; **Module 7 migration note**:
    becomes an optional FK once Project Management ships a `Task`/WBS model (driver: "Time entry tagged to a
    task" P1 — Toggl/Zoho Projects/Replicon)
  - `hours` (`DecimalField(max_digits=5, decimal_places=2)`) — manually entered (driver: "Manual time entry"
    P0; live timer P2 deferred — Toggl/Harvest/Zoho Projects)
  - `is_billable` (`BooleanField(default=True)`) — (driver: "Billable vs. non-billable flag per entry" P0 —
    Harvest/Toggl/Clockify/TimeCamp/Zoho Projects)
  - `billable_rate` (`DecimalField(max_digits=10, decimal_places=2, default=0)`) — snapshot rate captured at
    entry time (driver: "Billable rate per employee/project/task" P1 — Toggl/TimeCamp/Zoho Books; entry-level
    snapshot, not a rate-card table)
  - `notes` (`TextField(blank=True)`)
  - `Meta`: indexes `(tenant, timesheet)`, `(tenant, project)`, `(tenant, date)`
  - `clean()`: `hours > 0`; `date` within parent timesheet's period; if `timesheet.status == "approved"` block
    add/edit (lock-on-approval, driver: Toggl/TimeCamp/QuickBooks Time — enforced in the view guard, mirroring
    `OPEN_STATUSES` edit-lock on `LeaveRequest`)
  - Reuses `accounting.Project` (2.9) — no new project table. Billable value (`hours * billable_rate`) and
    utilization/budget-vs-actual are **derived report aggregates**, never stored fields.

- [ ] **`OvertimeRequest`** [`OT-`] (`TenantNumbered`, mirrors `LeaveEncashment`) — overtime claim.
  - `employee` FK `hrm.EmployeeProfile` (CASCADE)
  - `timesheet` FK `hrm.Timesheet` (SET_NULL, null=True, blank=True) — the week the OT was worked in, optional
    (driver: a claim can be raised before the timesheet is fully approved)
  - `date` (`DateField`) — the day OT occurred (finer than the week; daily-threshold based)
  - `hours_claimed` (`DecimalField(max_digits=5, decimal_places=2)`) — driver: "Automatic OT calculation from
    hours over threshold" P0 (QuickBooks Time/BambooHR/Deel) — for this pass captured as a claim, with a
    `suggested_hours()` helper that computes `SUM(TimesheetEntry.hours for date) - daily/weekly threshold` as a
    **display hint** (not force-written) so the field stays user-correctable while still being
    threshold-informed
  - `multiplier` (`DecimalField(max_digits=4, decimal_places=2, default=Decimal("1.50"))`) — driver:
    "Configurable OT threshold + multiplier" P0 (Hubstaff/Deel/QuickBooks Time) — simple tenant-constant default,
    editable per request
  - `payout_method` (`CharField(max_length=20, choices=[("pay", "Pay"), ("comp_leave", "Compensatory Leave")],
    default="pay")` — driver: "OT converted to pay or comp-leave" P1 (Deel); captures intent only, actual
    payroll/comp-leave crediting deferred (no 3.13 Salary Structure yet)
  - `reason` (`TextField()`)
  - `status` (`draft/pending/approved/rejected/cancelled`), `OPEN_STATUSES = ("draft", "pending")` — driver:
    "OT approval workflow (separate from timesheet approval)" P0 (Rippling/Hubstaff/Deel)
  - `approver` FK `settings.AUTH_USER_MODEL` (SET_NULL, null/blank), `approved_at` (DateTimeField, null/blank),
    `decision_note` (TextField, blank)
  - `overtime_pay_equivalent_hours` property (`hours_claimed * multiplier`, **derived, not stored** — no
    currency `amount` field since no stable employee pay-rate source exists yet; note this explicitly in the
    docstring per research)
  - `Meta`: `unique_together = ("tenant", "number")`; indexes `(tenant, employee, status)`, `(tenant, status)`,
    `(tenant, date)`
  - `clean()`: `hours_claimed > 0`
  - Reuses `hrm.EmployeeProfile`, optionally `hrm.Timesheet`; no new core-spine table.

**Numbering/status pattern:** both `Timesheet` and `OvertimeRequest` subclass `TenantNumbered` (`TS-`, `OT-`)
and reuse the exact `draft → pending → approved/rejected(+cancelled)` machine, `@tenant_admin_required`
approve/reject views, and edit/delete lock via `OPEN_STATUSES` proven by `LeaveRequest`/`AttendanceRegularization`/
`LeaveEncashment` — no new workflow pattern to invent.

## Backend (apps/hrm/ — extension, not a new app)

- [ ] `models.py` — add `Timesheet`, `TimesheetEntry`, `OvertimeRequest` in a new `# 3.11 Time Tracking` section
  (after the 3.10 Leave Management block, before 3.12 Holiday or wherever fits chronologically); `Timesheet.
  refresh_totals()` helper (sums `entries.aggregate(Sum("hours"), Sum("hours", filter=Q(is_billable=True)))`,
  called after entry add/edit/delete and in `save()` when entries already exist)
- [ ] `forms.py` — `TimesheetForm` (fields: `employee, period_start, period_end`; excludes `status/approver/
  approved_at/decision_note/rejected_reason/total_hours/billable_hours` — workflow/derived, never on the form,
  mirrors `LeaveRequestForm`'s comment style), `TimesheetEntryForm` (fields: `date, project, task_description,
  hours, is_billable, billable_rate, notes`; excludes `timesheet` — set from URL/view context like
  `ClearanceItem`-style child forms; `project` queryset scoped to `request.tenant` via `__init__`),
  `OvertimeRequestForm` (fields: `employee, timesheet, date, hours_claimed, multiplier, payout_method, reason`;
  excludes `status/approver/approved_at/decision_note`)
- [ ] `views.py` — full CRUD for `Timesheet` (`crud_list/_create/_detail/_edit/_delete` via `apps.core.crud`) +
  workflow (`timesheet_submit` draft→pending owner/`@login_required`; `timesheet_approve`/`_reject`
  `@tenant_admin_required`, approve sets approver/approved_at + calls `refresh_totals()` one final time and
  locks entries; `_cancel` owner). `TimesheetEntry` managed **inline on the `timesheet_detail` hub** (POST
  `timesheetentry_add`/`_edit`/`_delete` scoped to `?timesheet=<pk>`, no standalone list/detail templates —
  mirrors `ClearanceItem`/`RequisitionApproval` inline-child pattern); every entry mutation blocked when
  `timesheet.status == "approved"` (lock-on-approval) and calls `timesheet.refresh_totals()` + `save()`
  afterward. Full CRUD for `OvertimeRequest` (`crud_list/_create/_detail/_edit/_delete`) + workflow
  (`overtimerequest_submit` owner; `_approve`/`_reject` `@tenant_admin_required`; `_cancel` owner). Report views
  (read-only, `@login_required`, no new model): `timesheet_utilization_report` (per-employee/period
  billable-hours ÷ total-approved-hours, aggregated from `TimesheetEntry` joined through approved `Timesheet`
  rows), `project_time_report` (per `accounting.Project`: `SUM(TimesheetEntry.hours)` vs
  `Project.budget_amount`, flags overrun). Every list view: search (`q` over employee name/number) + filters
  (`status`, `employee`, date-range) parsed from `request.GET` BEFORE pagination, passing `status_choices`/
  `employee` queryset to the template context (Filter Implementation Rules). Every delete view: tenant-scoped
  `get_object_or_404`, POST-only, blocks delete once `status` not in `OPEN_STATUSES`. `write_audit_log` called
  on create/edit/delete/workflow transitions, mirroring `leaverequest_*`.
- [ ] `urls.py` — `timesheet_list/_create/_detail/_edit/_delete` (`/hrm/timesheets/`); POST-only
  `timesheet_submit/_approve/_reject/_cancel`; inline POST `timesheetentry_add` (`/hrm/timesheets/<ts_pk>/
  entries/add/`), `timesheetentry_edit`/`_delete` (`/hrm/timesheet-entries/<pk>/edit|delete/`);
  `overtimerequest_list/_create/_detail/_edit/_delete` (`/hrm/overtime-requests/`); POST-only
  `overtimerequest_submit/_approve/_reject/_cancel`; GET report pages `timesheet_utilization_report`
  (`/hrm/reports/utilization/`) and `project_time_report` (`/hrm/reports/project-time/`)
- [ ] `admin.py` — register `Timesheet` (inline `TimesheetEntry` via `TabularInline`), `OvertimeRequest`;
  list_display includes `number, employee, status`; list_filter `status`
- [ ] migrations — one migration adding the 3 models (run `makemigrations hrm` after models.py lands)
- [ ] `management/commands/seed_hrm.py` — extend the existing idempotent seeder: `_seed_timesheets(tenant,
  employees)` creates 2–3 `Timesheet` rows per seeded employee (mixed draft/pending/approved) with 3–5
  `TimesheetEntry` rows each; reuse a seeded `accounting.Project` if `Project.objects.filter(tenant=tenant)
  .exists()` else leave `project=None` + populate `task_description` free text; seed 1–2 `OvertimeRequest` rows
  per tenant (mixed statuses) linked to a seeded timesheet where applicable. Check
  `Timesheet.objects.filter(tenant=tenant).exists()` before creating (skip-if-exists pattern); no bare
  `.create()` for the numbered models — use the existing `next_number`-safe `TenantNumbered.save()` path.
  `management/__init__.py` and `management/commands/__init__.py` already exist (hrm app) — no new ones needed.

## Wire-up

- [ ] `apps/core/navigation.py` — add **one** `LIVE_LINKS["3.11"]` entry mapping all 5 NavERP.md bullets:
  ```python
  # 3.11 Time Tracking
  "3.11": {
      "Timesheet": "hrm:timesheet_list",                              # bullet
      "Project Time Tracking": "hrm:timesheet_list",                  # bullet (entries logged on the timesheet hub)
      "Billable Hours": "hrm:timesheet_utilization_report",           # bullet (utilization/billable report)
      "Overtime Tracking": "hrm:overtimerequest_list",                # bullet
      "Timesheet Approval": "hrm:timesheet_list?status=pending",      # bullet (pending-approval queue)
  },
  ```
  (Confirm exact bullet text against `NavERP.md` 3.11 before committing — copy verbatim.)
- [ ] No `apps.py`/`INSTALLED_APPS`/`config/urls.py` changes — `apps.hrm` is already installed and included.

## Templates (templates/hrm/timetracking/<entity>/…)

- [ ] `templates/hrm/timetracking/timesheet/list.html` — filter bar (`status`, `employee`, date-range) reflecting
  `request.GET`; Actions column (view/edit/delete-POST+confirm+csrf, edit/delete conditional on
  `obj.status in OPEN_STATUSES`); pagination; empty-state
- [ ] `templates/hrm/timetracking/timesheet/detail.html` — the hub: header fields + `total_hours`/`billable_hours`
  cards, inline entries table with add/edit/delete forms (conditional on open status), Submit/Approve/Reject/
  Cancel action buttons (role/status-gated), Actions sidebar (Edit/Delete/Back to List)
- [ ] `templates/hrm/timetracking/timesheet/form.html` — create/edit (employee, period_start, period_end)
- [ ] `templates/hrm/timetracking/overtimerequest/list.html` — filter bar (`status`, `employee`, date-range),
  Actions column
- [ ] `templates/hrm/timetracking/overtimerequest/detail.html` — full fields + workflow actions + Actions sidebar
- [ ] `templates/hrm/timetracking/overtimerequest/form.html` — create/edit
- [ ] `templates/hrm/timetracking/utilization_report.html` — standalone report page (per-employee/period
  billable % table) at the sub-module root (not an entity folder — no CRUD)
- [ ] `templates/hrm/timetracking/project_time_report.html` — standalone report page (per-project logged-vs-
  budget table) at the sub-module root

## Verify

- [ ] `makemigrations hrm` + `migrate`
- [ ] `python manage.py seed_hrm` run twice — idempotent (no duplicate timesheets/OT requests on the 2nd run)
- [ ] `python manage.py check`
- [ ] `temp/` smoke sweep: every `hrm:timesheet_*` / `hrm:overtimerequest_*` / `hrm:timesheet_utilization_report`
  / `hrm:project_time_report` url returns 200/302 for a logged-in tenant user; no `{#`/`{% comment` leaks in
  rendered timetracking templates; cross-tenant IDOR — a tenant-B user requesting a tenant-A `Timesheet`/
  `OvertimeRequest` pk gets 404; entry-add on an approved timesheet is blocked (403/redirect+message, not a
  silent no-op); `total_hours`/`billable_hours` recompute correctly after an entry add/edit/delete
- [ ] sidebar shows **Timesheet, Project Time Tracking, Billable Hours, Overtime Tracking, Timesheet Approval**
  as Live under 3.11

## Close-out

- [ ] `code-reviewer` agent → apply findings → commit
- [ ] `explorer` agent → apply findings → commit
- [ ] `frontend-reviewer` agent → apply findings → commit
- [ ] `performance-reviewer` agent → apply findings → commit (watch for N+1 on `entries` aggregation in list
  views — use annotations, not per-row `refresh_totals()` calls)
- [ ] `qa-smoke-tester` agent → apply findings → commit
- [ ] `security-reviewer` agent → apply findings → commit
- [ ] `test-writer` agent → apply output → commit
- [ ] update `.claude/skills/hrm/SKILL.md` — add the 3.11 Time Tracking section (models table row, routes,
  template folders, `LIVE_LINKS["3.11"]`, seeder rows) following the existing 3.9/3.10 write-up style
- [ ] update root `README.md` (HRM test count, module count) if the project keeps that convention (check prior
  module commits, e.g. `c31b32b`)

## Review — delivered 2026-07-03

**Scope built.** New HRM sub-module 3.11 Time Tracking (extension of `apps/hrm`). 3 models mirroring the sibling
LeaveRequest workflow: `Timesheet` (`TS-`, weekly header, **derived** `total_hours`/`billable_hours` via
`refresh_totals()`, draft→pending→approved/rejected/cancelled), `TimesheetEntry` (inline child on the timesheet hub,
optional `accounting.Project` FK, date-in-period `clean()`, **locked once approved**), `OvertimeRequest` (`OT-`,
hours×multiplier, pay/comp_leave, derived pay-equiv hours). Two derived report pages (utilization %, project-time
vs budget). Wired into `LIVE_LINKS["3.11"]` (all 5 bullets live + Project Time Report extra), admin (Timesheet w/
TimesheetEntry inline), seeder (`_seed_timetracking`: 6 timesheets + 24 entries + 1 OT/tenant), migration 0022.

**Full Module Creation Sequence run (research → todo → build → 7 review agents → skill):**
- research → `research-hrm-time-tracking.md` (10 products → 3-model scope). todo → the build plan above.
- Build: the smoke test caught a real bug — `project_time_report` aliased `Sum('hours')` as `hours`, shadowing the
  field into a `FieldError`; fixed (aliased `logged`/`billable`) before committing.
- code-reviewer → Critical: the admin `TimesheetEntryInline` could drift `total_hours`/`billable_hours` (no refresh)
  — fixed via `TimesheetAdmin.save_formset()`; + `Timesheet.clean()` period-covers-entries guard, `OvertimeRequest.
  clean()` timesheet-employee-match guard, entry-add error re-render (preserve input), dead-helper cleanup.
- explorer → clean + 2 follow-ups (overview pending-timesheet/overtime KPIs, date-range filters on both reports).
- frontend-reviewer → clean (conditional-colspan entries table done right; no comment leaks).
- performance-reviewer → clean (no N+1s, reports are single-query aggregates, index coverage exact).
- qa-smoke-tester → clean (40 HTTP checks: derived totals, lock-on-approval, period guard, 403, IDOR all held).
- security-reviewer → no vulnerabilities (tenant isolation incl. inline-entry path, mass-assignment, IDOR clean).
- test-writer → **160 tests** in `test_time_tracking.py` (+ conftest fixtures); HRM suite **1,935** green, project-wide
  **4,582**.

**Skill/README** updated (table 46→49, 3 model rows, routes/workflow/report extras, `timetracking/` folders,
LIVE_LINKS 3.11, seeder note, Deferred; test counts refreshed).

**Next unbuilt sub-module:** 3.13 (the lowest `N.M` without a LIVE_LINKS entry — likely a Payroll/Compensation
sub-module; auto-detect at run time).

## Later passes / deferred (carried over from research)

- Live/running timer (start-stop UI, active-timer state) — needs session/websocket state beyond a CRUD pass.
- Task-level FK replacing free-text `task_description` — blocked on Module 7 (Project Management) shipping a
  `Task`/WBS model.
- Automatic invoice generation from billable time — belongs to Accounting's AR/Receivables as a cross-module
  integration.
- Feeding approved hours into `accounting.JobCostEntry` as a labor cost — needs a stable employee cost/pay-rate
  figure (3.13 Salary Structure) first; flagged as the clear next integration once both sides are stable.
- Full rate-card matrix (client × project × role) — the entry-level `billable_rate` snapshot is the
  buildable-now equivalent.
- Profitability/margin reporting (billed value vs. employee cost) — needs a stable payroll cost rate; revisit
  after 3.13 Salary Structure.
- OT payout to payroll / comp-leave auto-credit to `LeaveAllocation` — `payout_method` captures intent now;
  actual money movement needs the payroll module.
- Multi-jurisdiction OT compliance rules (state/country-specific thresholds) — single tenant-level
  threshold/multiplier constant is the realistic buildable-now slice.
- Timesheet templates for recurring rows, submission reminders/nudges, bulk-approve, second-tier manager+finance
  approval, approval-progress visibility for submitters — UX/workflow-engine layers for once the base 3 models
  are stable.
- GPS/geofencing on time entries — already exists on `AttendanceRecord` (3.9); not duplicated here.
- Audit trail of timesheet entry edits — defer to Module 0's cross-cutting audit mechanism if/when available.

## Review notes
(filled in at the end)
