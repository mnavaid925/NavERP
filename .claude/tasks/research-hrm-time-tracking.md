# Research — Module 3: Human Resource Management, Sub-module 3.11 Time Tracking (hrm)

## Scope grounding
- **NavERP.md 3.11** bullets researched against: Timesheet (daily/weekly submission), Project Time Tracking
  (time logged against projects/tasks), Billable Hours (client billing, utilization reports), Overtime Tracking
  (OT calculation, approval, payment), Timesheet Approval (manager approval workflow).
- **Existing app:** `apps/hrm` (Django 5.1, function-based views, MySQL, multi-tenant). No time-tracking model
  exists yet in `apps/hrm/models.py` (confirmed via grep — this is a clean, additive build).
- **Anchor:** `hrm.EmployeeProfile` — every new model FKs it (never `core.Party` directly), matching
  `LeaveRequest`, `AttendanceRegularization`, `LeaveEncashment`.
- **Sibling pattern to mirror** (read from `apps/hrm/models.py`):
  - `TenantNumbered` abstract base (`apps/core/models.py`) auto-assigns `number` via `next_number()` with a
    retry-on-collision guard — timesheet/OT models should subclass it (`TS-`, `OT-` prefixes).
  - `LeaveRequest` / `LeaveEncashment` / `AttendanceRegularization` all use
    `STATUS_CHOICES = draft/pending/approved/rejected/(+cancelled/paid variants)`,
    `OPEN_STATUSES = ("draft", "pending")`, an `approver` FK to `settings.AUTH_USER_MODEL`, `approved_at`,
    and a derived numeric field recomputed in `save()` (never hand-edited on the form) — e.g. `LeaveRequest.days`,
    `LeaveEncashment.amount`, `AttendanceRecord.hours_worked`.
  - `AttendanceRecord` (3.9) already derives `hours_worked` from `check_in`/`check_out` per day — Time Tracking is
    a **different axis** (hours *allocated to project/task for billing/utilization*, submitted weekly and
    approved), not a duplicate of daily attendance. The two can optionally cross-reference by date/employee but
    are not merged.
  - `accounting.Project` (`apps/accounting/models_advanced.py`, 2.9 Project/Job Costing) already exists:
    `NUMBER_PREFIX = "PRJ"`, `billing_method` (`fixed`/`time_materials`/`milestone`), `client` (FK `core.Party`),
    `budget_amount`, `status`. `JobCostEntry` posts labor/other costs against a project as a JE. Module 7 (Project
    Management, task/WBS-level entities) is **not built yet** — so "tasks" in 3.11 must be **free text** for now,
    while the **project** link should be an optional FK to `accounting.Project` (nullable — timesheets can log
    against no project, e.g. general/admin time).

## Leaders surveyed (with source links)
1. **Harvest** — time tracking tightly fused with invoicing for agencies/freelancers — [Features](https://www.getharvest.com/features)
2. **Toggl Track** — privacy-first, simple timer-based tracking with strong project budget/estimate reporting — [Features](https://toggl.com/track/features/)
3. **Clockify** — most generous free tier; timesheet + approval + billable-rate stack aimed at teams of any size — [Features](https://clockify.me/features/)
4. **QuickBooks Time (formerly TSheets)** — payroll-native time tracking with configurable overtime rules — [Approvals](https://quickbooks.intuit.com/learn-support/en-us/help-article/manage-timesheets/approve-unapprove-reject-timesheets-quickbooks/L3fq6c1oN_US_en_US), [Time tracking](https://quickbooks.intuit.com/time-tracking/manage-employee-time/)
5. **Deltek Replicon** — enterprise-grade project time/billing with deep multi-jurisdiction labor-law compliance — [Deltek Replicon](https://www.deltek.com/en/time-tracking/replicon)
6. **Hubstaff** — remote-team time tracking with configurable overtime policy (threshold + multiplier) and payroll gating on approval — [Overtime Policy](https://support.hubstaff.com/overtime/), [Timesheet Approvals](https://support.hubstaff.com/optimizing-payroll-with-timesheet-approvals/)
7. **TimeCamp** — billing/invoicing built in, per-user/per-project billable rates, approval locks timesheets — [All features](https://www.timecamp.com/all-features/), [Rapid Timesheet Approvals](https://www.timecamp.com/time-tracking/rapid-timesheet-approvals/)
8. **Deel** — global EOR/contractor time tracking with configurable overtime submission rules (daily/weekly thresholds, multipliers, comp-leave conversion) and compliance blocking on over-limit submissions — [Overtime Submission Methods](https://help.letsdeel.com/hc/en-gb/articles/21024788842257-How-to-create-and-manage-Overtime-Submission-Methods-for-your-employees), [Timesheet Policies](https://help.letsdeel.com/hc/en-gb/articles/29317050610449-How-to-Create-and-Manage-Time-Tracking-Policies-for-Timesheet-Submission)
9. **Rippling Time & Attendance** — workflow-based OT approval routing (manager + finance), auto-sync approved hours to payroll — [Time and Attendance](https://www.rippling.com/products/hr/time-and-attendance)
10. **Zoho Projects (+ Zoho Books timesheet billing)** — task-level billable/non-billable logging rolled into weekly timesheets, budget-vs-logged utilization reporting — [Timesheet Software](https://www.zoho.com/projects/timesheet-software.html), [Timesheet Billing](https://www.zoho.com/us/billing/features/timesheet-billing/)
11. **BambooHR Time Tracking** — automatic overtime calc against configurable thresholds, one-click approval workflow — [Time Tracking](https://www.bamboohr.com/platform/time-and-attendance/time-tracking)

## Feature catalog by NavERP.md bullet

### Timesheet — Daily/weekly timesheet submission
- **Weekly timesheet grid (day columns x row per project/task)** — a single header record aggregates a week of daily entries · seen in: Clockify, Zoho Projects, Deel · priority: P0 · spine: new table `Timesheet` (header) + `TimesheetEntry` (lines) FK `hrm.EmployeeProfile` · buildable now.
- **Draft -> submit -> approved/rejected workflow** — employee drafts, submits for review; locked once approved · seen in: Harvest, Clockify, TimeCamp, BambooHR · priority: P0 · spine: reuse the `draft/pending/approved/rejected/cancelled` status machine already used by `LeaveRequest`/`LeaveEncashment` · buildable now.
- **Manual time entry (start/day + hours) vs. live timer** — most products offer both; timer state (running/stopped) is a real-time UI feature · seen in: Toggl Track, Harvest, Zoho Projects · priority: P0 for manual entry, P2 for live timer · spine: `TimesheetEntry.hours` (manual) is buildable now; a running timer needs session/websocket state — defer.
- **Locked/immutable after approval** — approved entries cannot be edited, preserving payroll/billing integrity · seen in: Toggl Track, TimeCamp, QuickBooks Time · priority: P0 · spine: enforce in `clean()`/view guard once `status == 'approved'`, mirroring `LeaveRequest.OPEN_STATUSES` edit-lock pattern · buildable now.
- **Submission reminders / due-date nudges** — automated reminders when a timesheet is late or missing · seen in: Harvest, Clockify, BambooHR · priority: P2 · integration/later (notification/email infra, not core CRUD).
- **Timesheet templates (recurring project/task rows)** — pre-fill common rows for a recurring week · seen in: Clockify, Replicon · priority: P2 · deferred — nice-to-have UX layer once base CRUD exists.
- **Daily vs. weekly period granularity** — some tools default to daily submission for compliance jurisdictions, others weekly · seen in: Deel, Replicon, Clockify · priority: P1 · spine: `Timesheet.period_start`/`period_end` fields support either (default a Mon-Sun week per NavERP.md "daily/weekly") · buildable now.
- **Activity log / audit trail of entry edits** — who changed what, when, for compliance and payroll disputes · seen in: Harvest · priority: P1 · spine: reuse Module 0's audit/history cross-cutting mechanism if present, else defer — don't build a bespoke audit table for this one model.

### Project Time Tracking — Time logged against projects/tasks
- **Time entry tagged to a project** — every logged hour is attributable to a client/project for cost and billing rollups · seen in: Harvest, Toggl Track, Zoho Projects, Replicon, TimeCamp · priority: P0 · spine: `TimesheetEntry.project` = optional FK `accounting.Project` (nullable — non-project/admin time allowed) · buildable now.
- **Time entry tagged to a task** — finer-grained bucket under a project (feature/ticket/milestone) · seen in: Toggl Track, Zoho Projects, Replicon · priority: P1 · spine: **no task model exists yet** (Module 7 Project Management not built) — use `TimesheetEntry.task_description` (free text/`CharField`), not a FK. Note for future migration once Module 7 ships a `Task` model.
- **Budget-vs-actual / estimate tracking per project** — compare logged hours to a project's time/budget estimate to flag overruns · seen in: Toggl Track, Zoho Projects, Clockify · priority: P1 · spine: derive from `SUM(TimesheetEntry.hours) WHERE project=X` compared against `accounting.Project.budget_amount` — a report/aggregate, not a stored field · buildable now (read-only view/report).
- **Cross-project time distribution in one entry period** — a single day/week can span multiple projects for the same employee · seen in: all surveyed products · priority: P0 · spine: modeled naturally by `TimesheetEntry` being a line table (many rows per `Timesheet` header) · buildable now.
- **Feed project actuals into job costing** — logged hours convert into a labor cost posted to the project's ledger · seen in: Replicon, Zoho Projects (via Zoho Books) · priority: P1 (future) · integration/later — NavERP already has `accounting.JobCostEntry` (posts a balanced JE); wiring approved timesheet hours -> `JobCostEntry` (labor cost @ employee's cost rate) is a natural Module 2/3 integration point but is **out of scope for this pass** (would require a payroll/cost-rate field and cross-app posting logic). Flag as the clear next integration once both sides are stable.

### Billable Hours — Client billing, utilization reports
- **Billable vs. non-billable flag per entry** — mark whether logged time is chargeable to the client · seen in: Harvest, Toggl Track, Clockify, TimeCamp, Zoho Projects · priority: P0 · spine: `TimesheetEntry.is_billable` (Boolean) · buildable now.
- **Billable rate per employee/project/task** — hourly rate used to compute billable value · seen in: Toggl Track ("billable rates by workspace/member/project"), TimeCamp, Zoho Books · priority: P1 · spine: reuse the project's existing cost/rate concept where possible; simplest buildable slice is a `TimesheetEntry.billable_rate` snapshot (decimal) captured at entry time (rate can vary later without rewriting history) rather than a new rate-card table · buildable now (entry-level rate; a full rate-card matrix is deferred).
- **Utilization report (billable hours / total capacity)** — per-employee percentage showing how much of their time is billable vs. idle/overhead, used for capacity planning · seen in: Harvest ("capacity reporting"), Toggl Track (profitability reporting), Zoho Projects (budget vs. logged) · priority: P0 · spine: **derived** report — `SUM(billable hours) / SUM(all approved hours)` per employee per period, computed from `TimesheetEntry` rows, never stored · buildable now (a report view, no new model).
- **Automatic invoice generation from tracked time** — turn approved billable hours directly into a client invoice · seen in: Harvest, TimeCamp, Zoho Books · priority: P2 · integration/later — NavERP's Accounting module (2.x Receivables/AR) owns invoicing; wiring approved billable `TimesheetEntry` rows to an AR invoice line is a cross-module integration for a later pass, not this one.
- **Rate-card matrix (per client/project/role)** — a fuller billing-rate system where the applicable rate depends on client, project, and employee role together · seen in: Toggl Track, Zoho Books · priority: P2 · deferred — the entry-level `billable_rate` snapshot above covers the buildable-now need; a full rate-card table is scope creep for this pass.
- **Profitability / margin reporting (revenue vs. cost of billed hours)** — ties billable value against the employee's cost to show project margin · seen in: Toggl Track, Replicon · priority: P2 · deferred — needs a stable employee cost-rate figure (payroll, 3.13 Salary Structure) not yet built; revisit once Salary Structure lands.

### Overtime Tracking — OT calculation, approval, payment
- **Configurable OT threshold + multiplier** — define daily/weekly hour thresholds beyond which a multiplier (e.g., 1.5x) applies · seen in: Hubstaff ("policy name, threshold, multiplier"), Deel ("daily and weekly thresholds, multipliers"), QuickBooks Time · priority: P0 · spine: `OvertimeRequest` fields `ot_hours`, `multiplier` (decimal, default e.g. 1.5), threshold logic can be a simple tenant-level constant/setting for this pass (a full configurable-policy table is P2/deferred) · buildable now (simple version).
- **Automatic OT calculation from hours over threshold** — system computes OT hours rather than manual entry · seen in: QuickBooks Time, BambooHR, Deel · priority: P0 · spine: **derive** `ot_hours` from `SUM(TimesheetEntry.hours)` for the period minus the standard threshold (e.g., 40/week) — computed in `save()`/a method, not hand-typed, mirroring `LeaveRequest.days` and `AttendanceRecord.hours_worked` · buildable now.
- **OT approval workflow (separate from timesheet approval)** — a manager/finance-routed approval specifically for overtime, sometimes a second approval tier · seen in: Rippling ("routed to both managers and Finance"), Hubstaff, Deel · priority: P0 · spine: new `OvertimeRequest` (TenantNumbered, `OT-` prefix) with the same `draft/pending/approved/rejected/cancelled` machine + `@tenant_admin_required` approve/reject, mirroring `LeaveRequest`/`LeaveEncashment` · buildable now.
- **OT converted to pay or comp-leave** — approved OT either becomes a payroll payout or is banked as compensatory time off · seen in: Deel ("paid out or converted to compensatory leave") · priority: P1 · spine: `OvertimeRequest.payout_method` choice (`pay`/`comp_leave`) captures *intent*; actual payroll payout is **integration/later** (3.13 Salary Structure / payroll not built), and comp-leave crediting to `LeaveAllocation` is a nice follow-on but out of scope for this pass — record the choice now so the field exists for that wiring later.
- **Overtime alerts/notifications before threshold is hit** — proactive warning to avoid unplanned OT cost · seen in: Rippling, Hubstaff · priority: P2 · integration/later (notification infra).
- **Multi-jurisdiction OT compliance rules (state/country-specific)** — different legal thresholds and multipliers by location · seen in: Replicon (145+ jurisdictions), BambooHR (all 50 US states), Deel (public-holiday/non-working-day rules) · priority: P2 · deferred — NavERP is not yet modeling jurisdiction-specific labor law; a single tenant-configurable threshold/multiplier is the realistic buildable-now slice.
- **Overtime tied to payroll run / lock on approval** — approved OT flows straight into the next pay cycle and can't be edited after · seen in: Hubstaff ("payroll won't be processed unless timesheet approved"), Rippling · priority: P1 · spine: enforce the same status-lock pattern as timesheets; actual payroll run integration deferred (no payroll module yet).

### Timesheet Approval — Manager approval workflow
- **Submit -> pending -> approve/reject with approver identity + timestamp** — the core workflow, always present · seen in: all 10 products · priority: P0 · spine: reuse `LeaveRequest`-style fields verbatim: `status`, `approver` FK `settings.AUTH_USER_MODEL`, `approved_at`, `rejected_reason`/`decision_note` · buildable now.
- **Manager-scoped approval queue** — approver only sees timesheets for their direct reports · seen in: Rippling, QuickBooks Time, BambooHR · priority: P1 · spine: derive from `core.Employment.manager` (already exists) filtered against `EmployeeProfile` — a queryset filter in the approve view, not a new field · buildable now.
- **Bulk approve multiple timesheets** — approve several team members' timesheets in one action · seen in: QuickBooks Time ("manage multiple timesheets and approve when ready"), BambooHR ("one-click approval") · priority: P2 · deferred — a UX/bulk-action layer on top of the single-record approve view; add once the base CRUD is stable.
- **Approval locks the record (no further edits)** — approved timesheets become read-only · seen in: Toggl Track, TimeCamp, QuickBooks Time · priority: P0 · spine: enforce via `OPEN_STATUSES` check in edit/delete views, exactly like `LeaveRequest`/`AttendanceRegularization` · buildable now.
- **Rejection with comment, resubmission** — rejected timesheet returns to employee with a reason, can be edited and resubmitted · seen in: Zoho Projects, Clockify, TimeCamp · priority: P0 · spine: `rejected_reason`/`decision_note` field + status returns to `draft` on reject, matching `LeaveRequest` · buildable now.
- **Second-tier / dual approval (e.g., manager then finance)** — used for overtime or high-value billable time · seen in: Rippling · priority: P2 · deferred — single-approver workflow is the realistic scope for this pass; multi-tier approval chains are a cross-cutting workflow-engine concern (Module 0/1.10 Automation territory), not specific to 3.11.
- **Approval-progress visibility for the submitter** — employee can see where their timesheet is in the approval chain · seen in: Zoho Projects · priority: P2 · deferred — covered adequately by the status field + detail page for this pass.

## Recommended build scope (this pass — 3 models)

- **`Timesheet`** [TS-] (`TenantNumbered`, mirrors `LeaveRequest`) — weekly header record.
  - `employee` FK `hrm.EmployeeProfile` (anchor, cascade)
  - `period_start`, `period_end` (`DateField`) — the Mon–Sun (or tenant-configured) week the sheet covers
  - `status` (`draft/pending/approved/rejected/cancelled`), `OPEN_STATUSES = ("draft", "pending")`
  - `approver` FK `settings.AUTH_USER_MODEL` (SET_NULL), `approved_at`, `decision_note`/`rejected_reason`
  - `total_hours`, `billable_hours` — **derived/`editable=False`**, recomputed in `save()`/a `refresh_totals()`
    helper from the child `TimesheetEntry` rows (never hand-typed), mirroring `LeaveRequest.days`
  - Justified by: Timesheet weekly grid + draft/submit/approve workflow (Clockify, Zoho Projects, Harvest, Deel);
    lock-on-approval (Toggl Track, TimeCamp, QuickBooks Time).
  - `unique_together = ("tenant", "employee", "period_start")` — one timesheet per employee per week.

- **`TimesheetEntry`** (plain `TenantOwned`, child of `Timesheet`, no own numbering — line item like `LeaveAllocation`).
  - `timesheet` FK `hrm.Timesheet` (cascade, `related_name="entries"`)
  - `date` (`DateField`, must fall within parent's `period_start`/`period_end`)
  - `project` — **optional** FK `accounting.Project` (`SET_NULL`, null/blank) — reuse the existing job-costing
    spine rather than a new project table; nullable so admin/non-project time is loggable
  - `task_description` (`CharField`, blank) — free-text task/ticket reference; **Module 7 migration note:** once
    Project Management ships a `Task`/WBS entity, this becomes an optional FK alongside (or replacing) the
    free-text field
  - `hours` (`DecimalField`) — manually entered (live timer UI deferred)
  - `is_billable` (`BooleanField`, default True)
  - `billable_rate` (`DecimalField`, default 0) — snapshot rate captured at entry time for billable-value
    calculation (`hours * billable_rate` derived, not stored)
  - `notes` (`TextField`, blank)
  - Justified by: project/task time logging (Harvest, Toggl Track, Zoho Projects, Replicon, TimeCamp); billable
    vs. non-billable flag (Harvest, Clockify, TimeCamp, Zoho Projects); per-entry billable rate (Toggl Track,
    TimeCamp); cross-project distribution within one period (all 10).
  - Utilization and budget-vs-actual are **reports**, computed by aggregating `TimesheetEntry` — no extra field.

- **`OvertimeRequest`** [OT-] (`TenantNumbered`, mirrors `LeaveEncashment`) — overtime claim tied to a timesheet.
  - `employee` FK `hrm.EmployeeProfile`
  - `timesheet` FK `hrm.Timesheet` (`SET_NULL`, null/blank) — the week the OT was worked in, optional so a claim
    can be raised before the timesheet is fully approved
  - `date` (`DateField`) — the day the OT occurred (finer than the week, since OT is often daily-threshold based)
  - `hours_claimed` (`DecimalField`) — hours claimed as overtime by the employee
  - `multiplier` (`DecimalField`, default `1.50`) — the pay multiplier applied (tenant-configurable constant for
    now, not a full jurisdiction rule engine)
  - `payout_method` (`pay`/`comp_leave` choice) — captures intent; actual payroll payout or leave-balance credit
    is integration/later
  - `reason` (`TextField`)
  - `status` (`draft/pending/approved/rejected/cancelled`), `OPEN_STATUSES = ("draft", "pending")`
  - `approver` FK `settings.AUTH_USER_MODEL` (SET_NULL), `approved_at`, `decision_note`
  - Justified by: configurable threshold + multiplier (Hubstaff, Deel, QuickBooks Time); separate OT approval
    workflow (Rippling, Hubstaff, Deel); pay-vs-comp-leave choice (Deel); lock-on-approval tying into payroll
    (Hubstaff, Rippling).
  - `amount` is **not** stored here (no stable employee pay-rate source exists yet — 3.13 Salary Structure isn't
    built) — only `hours_claimed x multiplier` = "OT-equivalent hours" is derivable; a currency `amount` field
    is deferred until payroll exists.

**Numbering/status pattern:** both `Timesheet` and `OvertimeRequest` subclass `TenantNumbered` (prefixes `TS`,
`OT`) and reuse the exact `draft -> pending -> approved/rejected(+cancelled)` machine, `@tenant_admin_required`
approve/reject views, and edit/delete lock via `OPEN_STATUSES` already proven by `LeaveRequest`,
`AttendanceRegularization`, and `LeaveEncashment` — no new workflow pattern needs inventing.

**Derived/report views (no new tables):**
- Utilization report: billable hours / total approved hours per employee per period.
- Project actuals report: `SUM(TimesheetEntry.hours)` per `accounting.Project` vs. `Project.budget_amount`.
- OT summary: total approved OT hours/equivalent per employee per pay period.

## Deferred (later passes / integrations)
- **Live/running timer (start-stop UI, active-timer state)** — Toggl Track/Harvest core UX; needs session or
  websocket state beyond a single Django CRUD pass. Manual hour entry covers the P0 need now.
- **Task-level FK (replacing free-text `task_description`)** — blocked on Module 7 (Project Management) shipping
  a `Task`/WBS model. Revisit `TimesheetEntry.project`/`task_description` once that exists.
- **Automatic invoice generation from billable time** — Harvest/TimeCamp/Zoho Books pattern; belongs to
  Accounting's AR/Receivables sub-module as a cross-module integration, not 3.11 itself.
- **Feeding approved hours into `accounting.JobCostEntry` as a labor cost** — natural next step once an
  employee cost/pay-rate figure exists (3.13 Salary Structure); flagged in the catalog above as the clear future
  integration.
- **Full rate-card matrix (client x project x role)** — the entry-level `billable_rate` snapshot is the
  buildable-now equivalent; a normalized rate-card table is scope creep for this pass.
- **Profitability/margin reporting (billed value vs. employee cost)** — needs a stable payroll cost rate; revisit
  after 3.13 Salary Structure.
- **OT payout to payroll / comp-leave auto-credit to `LeaveAllocation`** — `payout_method` captures intent now;
  actual money movement or leave-balance crediting needs the payroll module.
- **Multi-jurisdiction OT compliance rules (state/country-specific thresholds)** — Replicon/BambooHR/Deel-grade
  labor-law engine; NavERP uses one tenant-level threshold/multiplier constant for now.
- **Timesheet templates for recurring rows, submission reminders/nudges, bulk-approve, second-tier
  manager+finance approval, approval-progress visibility for submitters** — UX/workflow-engine layers to add
  once the base three models are stable and adopted.
- **GPS/geofencing on time entries** — already exists on `AttendanceRecord` (3.9); not duplicated here since
  3.11 tracks project/billing allocation, not physical punch location.
- **Audit trail of timesheet entry edits** — defer to Module 0's cross-cutting audit mechanism if/when available,
  rather than a bespoke history table for this one model.
