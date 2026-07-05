---
name: hrm
description: Work on the HRM module (Module 3 — 3.1 employees, 3.2 designations/org structure, 3.3 employee onboarding, 3.4 employee offboarding, 3.5 job requisition, 3.6 candidate management (ATS: candidates/applications/talent-pool tags/recruiting email templates + a public career portal), 3.7 interview process (interview scheduling/panel/RSVP + structured feedback scorecards + candidate invites/reminders), 3.8 offer management (offer letter generation + multi-step approval + tracking + background verification + pre-boarding over the JobApplication spine), 3.9 attendance/shifts (check-in/out, shifts + assignments, geofencing GPS zones, attendance regularization approval workflow), 3.10 leave management (types + policy engine [accrual/carry-forward runs], balance/allocations, applications, encashment payout workflow), 3.11 time tracking (weekly timesheets with inline entries + derived hours, project time against accounting.Project, billable/utilization + project-time reports, overtime requests, approval workflow), 3.12 holidays (calendar + floating-holiday elections + location/eligibility policies), 3.13 salary structure (pay-component catalog [earnings/statutory/reimbursement/variable], grade-wise CTC structure templates with an inline breakdown, effective-dated employee salary assignments — definition layer only; payroll run/posting stays in accounting.PayrollRun), 3.14 payroll processing (operational payroll run: computes per-employee payslips from the 3.13 salary structures, a draft->pending->approved/rejected->locked approval workflow, salary holds, arrears/bonus, and on lock hands the rolled-up totals to accounting.PayrollRun for GL posting — HRM builds no JournalEntry), 3.15 statutory compliance (Indian PF/ESI/PT/TDS/LWF compliance layer over payroll: a StatutoryConfig tenant settings singleton [employer codes/wage ceilings/rates/TAN/PAN], state-wise StatutoryStateRule PT slabs + LWF rules, per-employee EmployeeStatutoryIdentifier [UAN/PF/ESI, masked in the UI], and a StatutoryReturn [SCR-] per-scheme/period register aggregated from PayslipLine with a pending->filed->paid/late filing workflow + compliance calendar — touches no GL), 3.16 tax & investment (India income-tax declaration + computation engine: TaxRegimeConfig+TaxSlabBand old/new slabs, InvestmentDeclaration [ITD-] with 80C/80D/HRA section lines + InvestmentProof uploads/verification, and a TaxComputation [TXC-] recompute() engine [progressive slabs + 87A rebate + cess + HRA exemption + section caps + TDS-YTD from PayslipLine + monthly spread] with old-vs-new regime comparison and a Form 16 Part B report reusing StatutoryReturn(tds_form16) — posts no GL), 3.17 payout & reports (salary disbursement + reconciliation over 3.14: a PayoutBatch [POB-] generated from a locked PayrollCycle with per-payslip PayoutPayment [masked-bank snapshot, paid/failed/returned + retry-supersede lifecycle, UTR], PayslipDistribution [1:1 send/view/download tracking], BankReconciliation [BRC-] matching payments to the statement by UTR, plus payment-register + exceptions reports — posts no GL), 3.18 goal setting (OKR/goal mechanics, the first Performance-Management sub-module: a GoalPeriod quarterly/annual cycle catalog, Objective [OBJ-] with a parent self-FK cascade + core.OrgUnit dept scope + weight + derived weighted progress/pace-based health, KeyResult [KR-] with 5 metric types + weight, and an append-only GoalCheckIn [GCI-] history log that advances KeyResult.current_value, plus an alignment tree + ?mine direct-reports view — no ratings/reviews/PIP, those stay 3.19-3.21), 3.19 performance review (formal appraisal cycles, the 2nd Performance-Management sub-module: a ReviewCycle catalog with a 6-phase machine [draft->self_assessment->manager_review->calibration->released->closed] + optional GoalPeriod link, ReviewTemplate [RVT-] per review_type [self/manager/peer/upward/skip_level], PerformanceReview [RVW-] with a derived weighted overall_rating [None until rated] + stored manager/calibrated/potential ratings + effective_rating [calibrated overrides overall] + private_notes, ReviewRating [RVR-] weighted competency lines; submit->share->acknowledge workflow, a calibration board, and CONFIDENTIALITY gating [reviews visible only to subject/reviewer/admin, content edit-locked once non-draft] — continuous feedback/PIP stay 3.20-3.21)). Use when the user asks to add/change/debug anything under apps/hrm or templates/hrm, extend the seed_hrm seeder, touch HRM sidebar wiring (LIVE_LINKS 3.1/3.2/3.3/3.4/3.5/3.6/3.7/3.8/3.9/3.10/3.11/3.12/3.13/3.14/3.15/3.16/3.17/3.18/3.19), or invokes /hrm.
---

# HRM — Human Resource Management (Module 3)

NavERP Module 3. App path: `apps/hrm/`, templates: `templates/hrm/`, URL prefix `/hrm/`
(`app_name = "hrm"`). Built sub-modules: **3.1 Employee Management, 3.2 Organizational Structure,
3.3 Employee Onboarding, 3.4 Employee Offboarding, 3.5 Job Requisition, 3.6 Candidate Management,
3.7 Interview Process, 3.8 Offer Management, 3.9 Attendance Management, 3.10 Leave Management,
3.11 Time Tracking, 3.12 Holiday Management, 3.13 Salary Structure, 3.14 Payroll Processing,
3.15 Statutory Compliance, 3.16 Tax & Investment, 3.17 Payout & Reports, 3.18 Goal Setting,
3.19 Performance Review.** Reuses the
unified core spine — an **employee is a `core.Party` (person) + `core.Employment`**; departments reuse
`core.OrgUnit`. Payroll GL posting stays with **`accounting.PayrollRun`** (HRM does not duplicate it).

## Overview
Tenant-scoped employee directory + leave + attendance for the demo tenants. Everything filters by
`request.tenant`. Derived figures (leave balance, leave days, attendance hours) are computed, never stored
editable. Recruiting/payroll/performance are deferred to later passes (see "Deferred").

## Models (`apps/hrm/models.py`) — 71 tables (18 core HRM + 7 onboarding + 4 offboarding + 2 employee-records + 3 job-requisition + 6 candidate-management + 4 interview-process + 5 offer-management + 4 statutory-compliance + 6 tax-investment + 4 payout-reports + 4 goal-setting + 4 performance-review)
All inherit local abstract bases (mirror crm/accounting; peer apps don't import each other):
- `TenantOwned` — `tenant` FK (`related_name="+"`) + `created_at`/`updated_at`.
- `TenantNumbered(TenantOwned)` — adds auto per-tenant `number` via `core.utils.next_number` with a 5-retry
  collision guard. Set `NUMBER_PREFIX` on the subclass.

| Model | Number | Key fields | Reuses core / notes |
|-------|--------|-----------|---------------------|
| `JobGrade` (3.2) | — | name, level_order(int, 1=most junior), description, is_active | Orderable grade catalog (G1/G2/M1…); `__str__`="name (Ln)"; `unique_together=(tenant,name)`. Designations FK here. |
| `Designation` (3.2) | — | name, **job_grade→`JobGrade`**, grade(free-text fallback), department→`core.OrgUnit`, **description, requirements**, min/**mid**/max_salary, **budgeted_headcount**, is_active | `clean()`: min≤max and min≤mid≤max. `__str__` prefers `job_grade.name` over free-text `grade`. `unique_together=(tenant,name)`; indexes (tenant,is_active)/(tenant,department)/(tenant,job_grade) |
| `DepartmentProfile` (3.2) | — | **org_unit→`core.OrgUnit`(1:1, kind=department)**, code, description, head→`EmployeeProfile`, cost_center→`core.OrgUnit`(kind=cost_center), is_active | HRM companion to a department OrgUnit (adds head/code/CC core can't hold; name/parent stay on OrgUnit). `clean()` rejects non-department org_unit + non-cc cost_center. `unique_together=(tenant,org_unit)`; indexes (tenant,is_active)/(tenant,head)/(tenant,cost_center) |
| `CostCenterProfile` (3.2) | — | **org_unit→`core.OrgUnit`(1:1, kind=cost_center)**, code, description, owner→`EmployeeProfile`, budget_annual, budget_year, is_active | HRM companion to a cost-center OrgUnit (budget/owner). `clean()` rejects non-cc org_unit. `unique_together=(tenant,org_unit)`. Budget-vs-actuals reporting deferred to Accounting. |
| `EmployeeProfile` | `EMP-` | party→`core.Party`(1:1), employment→`core.Employment`(1:1), designation→`Designation`, employee_type, gender, dob, blood_group, marital_status, nationality, personal_email, work_email, mobile, work_location, notice_period_days, father_name, spouse_name, national_id(+_type), passport_number/_expiry, current/permanent_address, bank_*, probation_end_date, confirmed_on, emergency_*(×2), photo, notes | **The anchor — every other HRM model FKs here, not to core.Party.** Props: `department`/`manager` (via employment), `name` (party.name). **Masked PII accessors — always use in templates, never the raw field:** `masked_bank_account()`/`masked_bank_routing()`/`masked_national_id()`/`masked_passport_number()` (last-4 via `_mask_last4`). `national_id`/`passport_number` (+ bank_*) redacted from AuditLog via `core.crud._SENSITIVE_AUDIT_FIELDS`; plaintext at rest (WARNING — encrypt later). |
| `LeaveType` | — | name, code, is_paid, accrual_rule(none/monthly/annual), accrual_days, max_balance, max_carry_forward, encashable, is_active | `clean()`: accrual_days>0 when accruing. `unique_together=(tenant,code)` |
| `LeaveAllocation` | `LA-` | employee, leave_type, year, allocated_days, **carried_forward**(editable=False, engine-set), **encashed_days**(editable=False, workflow-set), note, status(draft/active/expired) | `used_days` derived (sum of approved requests); **`balance` = allocated_days − used_days − encashed_days**; `carried_forward` = days rolled in by the carry-forward run (kept separate for idempotency); `encashed_days` = APPROVED encashment payouts (kept separate so accrual can't restore cashed-out days); `unique_together` also (tenant,employee,leave_type,year). `LeaveAllocationForm.save()` zeroes carried_forward on a manual allocated_days edit |
| `LeaveRequest` | `LR-` | employee, leave_type, start_date, end_date, **days**(editable=False), reason, status(draft/pending/approved/rejected/cancelled), approver, approved_at, rejected_reason, cancelled_reason | `save()` recomputes `days` from range minus non-optional holidays; `clean()`: end ≥ start. `OPEN_STATUSES=(draft,pending)` |
| `LeaveEncashment` (3.10) | `ENC-` | employee, leave_type(encashable), year, days, rate_per_day, **amount**(editable=False), status(draft/pending/approved/paid/rejected/cancelled), approver, approved_at, paid_on, payment_reference, decision_note | Encash unused leave → payout. `save()` sets `amount = days × rate_per_day`; `clean()`: days>0 + leave_type.encashable + days ≤ balance (tenant-less query — employee is already tenant-bound, tenant unset pre-validation on create). `OPEN_STATUSES=(draft,pending)`. **On approve** (view, `@tenant_admin_required`, atomic, re-checks balance) increments the linked allocation's `encashed_days` (NOT allocated_days). Indexes (tenant,employee,status)/(tenant,status)/(tenant,leave_type,year) |
| `Timesheet` (3.11) | `TS-` | employee, period_start, period_end, **total_hours**/**billable_hours**(editable=False), status(draft/pending/approved/rejected/cancelled), approver, approved_at, decision_note, rejected_reason | Weekly header. `total_hours`/`billable_hours` **derived** — recomputed by `refresh_totals()` (one `entries.aggregate(Sum, Sum filter=is_billable)`) after every entry add/edit/delete + on approve; never hand-typed. `clean()`: end≥start + (on edit) the period must still cover every existing entry. `OPEN_STATUSES=(draft,pending)`; unique (tenant,employee,period_start); indexes (tenant,employee,status)/(tenant,status)/(tenant,period_start) |
| `TimesheetEntry` (3.11) | — | timesheet→`Timesheet`(CASCADE, related_name=entries), date, **project→`accounting.Project`**(SET_NULL, optional), task_description(free text), hours, is_billable, billable_rate, notes | Inline child line managed on the timesheet hub (POST `timesheetentry_add/_edit/_delete`), **locked once the timesheet is approved** (view guard). `clean()`: hours>0 + date within parent period. Derived `billable_value` (hours×rate when billable). Reuses the 2.9 job-costing `accounting.Project` (task FK deferred to Module 7). Indexes (tenant,timesheet)/(tenant,project)/(tenant,date) |
| `OvertimeRequest` (3.11) | `OT-` | employee, timesheet→`Timesheet`(SET_NULL, optional), date, hours_claimed, multiplier(default 1.50), payout_method(pay/comp_leave), reason, status(draft/pending/approved/rejected/cancelled), approver, approved_at, decision_note | OT claim; derived `overtime_pay_equivalent_hours` (hours×multiplier) — no stored currency amount (no pay-rate source until 3.13). `clean()`: hours_claimed>0 + linked timesheet must be the same employee. `OPEN_STATUSES=(draft,pending)`; indexes (tenant,employee,status)/(tenant,status)/(tenant,date) |
| `PublicHoliday` (3.12) | — | date, name, is_optional, **category**(national/regional/company/observance) | non-optional holidays excluded from leave `days`; optional (floating) holidays are elected via `FloatingHolidayElection`, not auto-off; `unique_together=(tenant,date,name)`; index (tenant,date) |
| `HolidayPolicy` (3.12) | — | name, location(free-text, contains-match vs `EmployeeProfile.work_location`), org_unit→`core.OrgUnit`, employee_type(reuses `EmployeeProfile.EMPLOYEE_TYPE_CHOICES`), designation→`Designation`, is_default, floating_holiday_quota, **holidays**(M2M→`PublicHoliday`), is_active, description | Location/eligibility-scoped policy. Classmethod **`for_employee(employee)`** resolves the governing policy: each SET scope field must match the employee (blank=wildcard), most matched fields wins, `is_default` breaks ties → falls back to the default → else `None`. `unique_together=(tenant,name)`; index (tenant,is_default) |
| `FloatingHolidayElection` (3.12) | — | employee, holiday(must be `is_optional=True`), policy→`HolidayPolicy`(auto-resolved), status(pending/approved/rejected), requested_on, **approved_by**(editable=False), approved_at(editable=False), note | Employee elects an optional holiday. `clean()`: only optional holidays are electable; quota check counts the employee's pending+approved elections in the holiday's year vs the resolved policy's `floating_holiday_quota` (tenant derived from the employee — instance tenant is unset pre-validation on create). `save()` auto-resolves `policy` when blank (`clean()` stores it so `save()` doesn't re-scan). Approve/reject workflow (`@tenant_admin_required` + `@require_POST`); edit/delete locked once decided (status≠pending). `unique_together=(tenant,employee,holiday)`; indexes (tenant,employee,status)/(tenant,status) |
| `PayComponent` (3.13) | — | name, code, component_type(earning/statutory_deduction/voluntary_deduction/reimbursement/variable), variable_subtype, calculation_type(fixed_amount/pct_of_basic/pct_of_ctc/pct_of_gross), default_amount, default_percentage, frequency(monthly/annual/one_time), is_taxable, include_in_ctc, contribution_side(employee/employer/both), annual_cap_amount, requires_bill, is_active, display_order, description | Unified pay-component catalog covering 4 of the 5 NavERP.md 3.13 bullets (Pay/Tax/Reimbursement/Variable) via `component_type`. `clean()`: fixed→no default %, pct→no default amount. `unique_together=(tenant,name)`; index (tenant,component_type) |
| `SalaryStructureTemplate` (3.13) | `SST-` | name, job_grade→`JobGrade`, annual_ctc_amount, currency(CharField, no `accounting.Currency` FK this pass), is_active, description | Grade-wise CTC container. **`computed_ctc_total`** = derived property (sum of line `resolved_amount()`; NOT stored — `salarystructuretemplate_detail` computes `ctc_total` once from the fetched lines to avoid the property re-querying). `unique_together=(tenant,number)`; index (tenant,job_grade) |
| `SalaryStructureLine` (3.13) | — | template→`SalaryStructureTemplate`(CASCADE, related_name=lines), pay_component→`PayComponent`(**PROTECT**), calculation_type(override; blank=defer to component), amount, percentage, sequence | The CTC breakdown row, managed **inline** on the template detail (add/edit/delete mirror 3.11 `TimesheetEntry`; the add view presets `instance(tenant,template)` before validation). **`resolved_amount()`**: fixed→line amount else component default else 0; pct→(line % else component %) × `template.annual_ctc_amount` (v1: all pct types resolve off CTC — true multi-base deferred). Form `clean()` rejects a duplicate component (form excludes `template`, so `validate_unique` skips it → manual check, else IntegrityError 500). `unique_together=(tenant,template,pay_component)`; index (tenant,template) |
| `EmployeeSalaryStructure` (3.13) | `ESS-` | employee→`EmployeeProfile`(related_name=salary_structures), template→`SalaryStructureTemplate`, annual_ctc_amount, effective_from, effective_to, status(active/superseded), notes | Effective-dated assignment of a CTC to an employee (may override the template's). `clean()`: effective_to≥from + **at most one `active` per employee** (tenant derived from the employee, unset pre-validation on create). A **superseded** assignment is read-only — `edit`/`delete` reject it server-side (redirect to detail, buttons hidden); supersede = edit the active row to superseded + create a new active one. `unique_together=(tenant,number)`; indexes (tenant,employee,effective_from)/(tenant,status) |
| `PayrollCycle` (3.14) | `PRC-` | period_start/end, pay_date, cycle_type(regular/off_cycle/bonus), status(draft/pending_approval/approved/rejected/locked), submitted_by/at, approved_by/at, rejection_reason, notes, **accounting_payroll_run→`accounting.PayrollRun`**(set on lock) | Operational payroll run header. Derived `headcount`/`total_gross`/`total_deductions`/`total_net` (single cached aggregate); `is_locked`. Workflow: generate→submit→approve/reject→lock. **On lock** it rolls up payslip totals and creates a draft `accounting.PayrollRun` (L29 — HRM never builds a JournalEntry; accounting's `payroll_run_post` posts the GL). off_cycle/bonus submit→approved directly. `unique_together=(tenant,number)`; index (tenant,status) |
| `Payslip` (3.14) | `PSL-` | cycle→`PayrollCycle`(CASCADE), employee→`EmployeeProfile`(**PROTECT**), salary_structure→`EmployeeSalaryStructure`(SET_NULL), days_in_period, days_worked, lop_days, lop_amount, gross_pay, total_deductions, net_pay (all editable=False/derived), arrears_amount, bonus_amount, on_hold, hold_reason, released_at | One per (tenant,cycle,employee). **`recompute()`** = the calc engine: monthly = structure line `resolved_amount(employee CTC)`/12; earnings pro-rated by days_worked/days_in_period; LOP; + arrears/bonus; **employer-side statutory EXCLUDED from net** (company cost, snapshotted); rebuilds the PayslipLines; guarded against a locked cycle. `clean()`: days_worked≤days_in_period, non-negative arrears/bonus/lop. "locked" derives from `cycle.is_locked`. `unique_together=(tenant,cycle,employee)` |
| `PayslipLine` (3.14) | — | payslip→`Payslip`(CASCADE, related_name=lines), component_name(snapshot string), component_type(`PayComponent`'s + arrears/bonus/lop), amount(positive magnitude), contribution_side(snapshot — drives the lock employee/employer-tax roll-up), sequence | Per-component SNAPSHOT copied at generation so a later PayComponent/structure edit never rewrites historical payslips (immutable-results convention). index (tenant,payslip) |
| `Shift` | — | name, start_time, end_time, grace_minutes, is_default, is_active | overnight shifts allowed (end < start) |
| `ShiftAssignment` | — | employee, shift, effective_from, effective_to(null=ongoing) | `clean()`: effective_to ≥ effective_from; `unique_together=(tenant,employee,effective_from)` |
| `AttendanceRecord` | `ATT-` | employee, date, check_in, check_out, **hours_worked**(editable=False), shift, status(present/absent/half_day/on_leave/holiday/regularized), source(web/mobile/biometric/manual), **latitude, longitude, geofence→`GeoFence`(SET_NULL)** (3.9 geofencing), notes | `save()` recomputes `hours_worked` (handles overnight); `is_late()` (minutes-of-day vs shift start+grace); **`has_geo()`**, **`geo_status()`** → `verified`/`outside`/`""` (DERIVED, checks the zone's live radius regardless of `is_active`); `clean()`: lat/long are a pair (both or neither), a geofence needs coords; `unique_together` also (tenant,employee,date); index (tenant,geofence) |
| `GeoFence` (3.9) | — | name, address, latitude, longitude (Decimal 9,6 + range validators), radius_m(PositiveInt, MinValue 1), is_active | GPS zone for field attendance. **Real haversine** `distance_to(lat,lng)`→metres + `contains(lat,lng)` (≤ radius; guards None); `EARTH_RADIUS_M=6_371_000`; `unique_together=(tenant,name)`; index (tenant,is_active). Delete guarded when punches reference it (deactivate instead). |
| `AttendanceRegularization` (3.9) | `REG-` | employee, **attendance_record→`AttendanceRecord`(SET_NULL, optional)**, date, reason_type(missed_punch/forgot_checkin/forgot_checkout/wrong_time/on_duty/work_from_home/system_error/other), requested_check_in, requested_check_out, reason, status(draft/pending/approved/rejected/cancelled), approver, approved_at, decision_note | Punch-correction request; `OPEN_STATUSES=(draft,pending)`; `clean()`: linked record must be same employee + at least one requested time. **On approve** (view, `@tenant_admin_required`, atomic) the requested times are written onto the linked punch (→ `regularized`, hours recompute); if none is linked it finds the (employee,date) row or materialises a fresh `ATT-` punch and links it back. `unique_together=(tenant,number)`; indexes (tenant,employee,status)/(tenant,status)/(tenant,date) |

### 3.3 Employee Onboarding (7 tables) — reusable template → per-hire program → tasks/docs/assets/sessions

| Model | Number | Key fields | Reuses core / notes |
|-------|--------|-----------|---------------------|
| `OnboardingTemplate` | `ONBT-` | name, description, designation→`Designation`(nullable), is_active | Reusable checklist; `unique_together=(tenant,name)`. Auto-suggested per role via designation. |
| `OnboardingTemplateTask` | — | template→`OnboardingTemplate`, title, description, task_category(hr_admin/it_setup/manager_action/buddy_action/new_hire_action/document_sign/equipment_request/training/meet_greet/custom), assignee_role(hr/it/manager/buddy/new_hire), due_offset_days(int, ±), phase(preboarding/week_1/month_1/month_2/month_3/ongoing), order, is_mandatory | Choice sets are **module-level constants** `TASK_CATEGORY_CHOICES`/`ASSIGNEE_ROLE_CHOICES`/`PHASE_CHOICES` (shared with `OnboardingTask`). `unique_together=(tenant,template,title)` |
| `OnboardingProgram` | `ONB-` | employee→`EmployeeProfile`, template→`OnboardingTemplate`(nullable), start_date, status(draft/active/completed/cancelled), buddy→`EmployeeProfile`(nullable), welcome_message, welcome_video_url, first_day_notes, completed_at(editable=False), notes | **Welcome Kit = the welcome_*/first_day_notes fields** (no separate table). `progress` is a **derived** %-of-tasks property (memoised; list views use `tasks_total`/`tasks_done` annotations). One-program-per-employee enforced in `OnboardingProgramForm.clean()` (tenant is form-set, not on the instance at model-clean time). |
| `OnboardingTask` | — | program→`OnboardingProgram`, title, description, task_category, assignee_role, assignee→`User`(nullable), due_date, phase, status(pending/in_progress/completed/skipped), is_mandatory, completed_at/completed_by(editable=False), order, notes | Generated from the template by `services.generate_tasks_from_template` (`due_date = start_date + due_offset_days`). `is_overdue()` helper. |
| `OnboardingDocument` | — | program→`OnboardingProgram`, document_type(employment_contract/nda/offer_letter/id_proof/tax_form/bank_details/policy_acknowledgment/background_check/custom), title, description, file(upload, allowlisted), esign_required, **esign_status**(not_required/pending/sent/viewed/signed/declined), due_date, signed_at(editable=False), external_ref(stub) | **`esign_status` is workflow-owned**: `save()` derives it from `esign_required` (not_required↔pending), preserves terminal signed/declined; advanced to `signed` only by the mark-signed action. NOT a form field. |
| `AssetAllocation` | `AST-` | program→`OnboardingProgram`(nullable), employee→`EmployeeProfile`, asset_name, asset_category(laptop/desktop/phone/id_card/access_card/uniform/vehicle/sim/other), serial_number, asset_tag, status(pending/issued/returned/lost/damaged), issued_at, issued_by→`User`, returned_at(editable=False), return_due_date, notes | issued_at/issued_by stamped by the Issue action (excluded from the form); returned_at by Return. A nullable FK to the future `assets.Asset` (Module 11) is reserved (commented). |
| `OrientationSession` | — | program→`OnboardingProgram`(nullable), employee→`EmployeeProfile`, title, session_type(orientation/training/meet_greet/policy_review/system_demo/department_intro/social/custom), facilitator→`User`(nullable), facilitator_name(free text), scheduled_at, duration_minutes, location, meeting_url, **attendance_status**(scheduled/attended/missed/rescheduled/cancelled), notes | `clean()` blocks scheduling before `program.start_date` (fetches only that field). `attendance_status` is workflow-owned (NOT a form field) — set by mark-attended/mark-missed only. |

**Onboarding flow:** create `OnboardingTemplate` + `OnboardingTemplateTask`s → create an `OnboardingProgram` for a new hire (status `draft`) → **Activate** (draft→active, generates `OnboardingTask`s from the template) → tick tasks complete/reopen/skip, collect `OnboardingDocument`s (mark-signed), issue/return `AssetAllocation`s, schedule `OrientationSession`s (mark attended/missed) → **Complete** (admin). `services.generate_tasks_from_template` is a request-free, idempotent (title-keyed `bulk_create`) helper shared by the activate/generate-tasks views and the seeder.

**Derived-not-stored:** never set `LeaveRequest.days`, `AttendanceRecord.hours_worked`, or
`LeaveAllocation.used_days/balance` from a form — they're computed in `save()`/properties. For list views, use
the `used_days_db`/`balance_db` annotations from `views._used_days_subquery()` (avoids per-row N+1), not the model
properties.

### 3.4 Employee Offboarding (4 tables) — case → exit-interview / clearance / final-settlement → letters

| Model | Number | Key fields | Reuses core / notes |
|-------|--------|-----------|---------------------|
| `SeparationCase` | `SEP-` | employee→`EmployeeProfile`, separation_type(resignation/termination/layoff/retirement/contract_end/deceased), exit_reason(coded), resignation_letter(upload), notice_period_days, notice_start_date, **expected_last_working_day**(editable=False, computed), actual_last_working_day, notice_buyout_type(none/pay_in_lieu/recover), requires_kt, **status**(draft→pending_approval→in_clearance→cleared→settled→completed +rejected/withdrawn), approver/approved_at, rejection_reason, withdrawal_reason, relieving/experience_letter_generated_at/_by, submitted_at | **The offboarding hub** — every other 3.4 model FKs here. `save()` derives `expected_last_working_day = notice_start_date + notice_period_days` (added to `update_fields` when missing so workflow saves persist it). `all_mandatory_cleared` property (gates Mark-Cleared + letters). No standalone "approved" state — approve goes straight to `in_clearance`. `LETTER_READY_STATUSES = (cleared, settled, completed)`. |
| `ExitInterview` | `EI-` | case→`SeparationCase`, interviewer→`User`, scheduled_at, conducted_at(editable=False), mode(in_person/video/phone/form), **status**(scheduled/completed/skipped/no_show, editable=False), 8×`rating_*` SmallIntegerField(1–5, `_RATING_VALIDATORS`), primary_reason(coded), would_recommend, would_rejoin, what_went_well/what_to_improve/additional_comments | One per case (form-guarded, not DB). `RATING_FIELDS` class list drives the form fieldset + detail table. `average_rating` property. |
| `ClearanceItem` | — | case→`SeparationCase`, department(it/finance/hr/admin/manager/legal/security/library/custom), department_label, description, is_mandatory, assigned_to→`User`, due_date, **status**(pending/in_progress/cleared/not_applicable/rejected, editable=False), cleared_by/cleared_at(editable=False), **asset_allocation→`AssetAllocation`(SET_NULL)** | Child clearance lines (no number). `RESOLVED_STATUSES = (cleared, not_applicable)`. `department_display` property (custom label fallback). Marking a line cleared **returns its linked issued asset** (same txn, employee-ownership-guarded). |
| `FinalSettlement` | `FNF-` | case→`SeparationCase`, settlement_date, 6 earnings DecimalFields (prorata_salary, leave_encashment_days+amount, gratuity_eligible+amount, bonus_amount, reimbursement_amount, other_income), 7 deduction DecimalFields (notice_recovery_amount, loan_recovery, asset_deduction, advance_recovery, tax_deduction, professional_tax, other_deduction), **status**(draft→computed→hr_approved→finance_approved→paid +cancelled, editable=False), hr/finance_approved_by/_at(editable=False), paid_at(editable=False), gl_posted(stub) | One per case (`unique_together(tenant,case)`). `net_payable`/`total_earnings`/`total_deductions` are **derived properties** (never stored). `gl_posted` always False — GL posting deferred to `accounting.PayrollRun`. |

**Offboarding flow:** create `SeparationCase` (draft) → **Submit** (draft→pending_approval, stamps submitted_at) → **Approve** (admin; →in_clearance, `generate_clearance_checklist` auto-creates the 6 department lines) → clear/NA/reject each `ClearanceItem` (admin; cleared returns the linked asset) → **Mark Cleared** (admin; gated on `all_mandatory_cleared`) → create `FinalSettlement` → **Compute** (admin; `compute_leave_encashment` fills leave encashment + gratuity-if-≥5yrs) → **HR Approve** (requires `computed`) → **Finance Approve** → **Mark Paid** (case→settled) → **Complete** (admin) → **Generate Relieving/Experience Letter** (print view, stamps generated_at). An `ExitInterview` is scheduled off the case and marked completed/skipped (admin). **Workflow-owned fields are excluded from every form** (status/approver/timestamps/letter stamps) — set only by the audited POST actions.

**Offboarding services (`apps/hrm/services.py`):** `generate_clearance_checklist(case)` — idempotent ((department,description)-keyed `bulk_create`) 6-line department checklist, links one issued `AssetAllocation` to the IT line, respects `requires_kt` for the manager line. `compute_leave_encashment(employee)` — sums encashable active `LeaveAllocation` balances via a **single correlated subquery** (no N+1), values them at `designation.min_salary / 30` per day; returns `(days, amount)`.

### 3.1 Employee records (2 tables) — personnel-file vault + job-history timeline (children of `EmployeeProfile`)

| Model | Number | Key fields | Reuses core / notes |
|-------|--------|-----------|---------------------|
| `EmployeeDocument` | `EDOC-` | employee→`EmployeeProfile`, document_type(19 choices: national_id/passport/visa/work_permit/degree_certificate/employment_contract/nda/…), title, document_number, issuing_authority/_country, issued_on, expires_on, is_confidential, file(upload, allowlist pdf/doc/docx/jpg/png + 10 MB), **verification_status**(pending/verified/rejected, editable=False), verified_by/verified_at(editable=False), notes | Personnel-file vault — distinct from `OnboardingDocument` (program e-sign) and `core.Document` (generic). `is_expired`/`is_expiring_soon` (≤30 days) **derived props**. **`is_confidential` is enforced** — confidential docs are admin-only on detail/edit/delete and excluded from the non-admin list/hub. Verify/reject are workflow-owned (`@tenant_admin_required`). |
| `EmployeeLifecycleEvent` | `ELC-` | employee→`EmployeeProfile`, event_type(`LIFECYCLE_EVENT_TYPE_CHOICES`: hire/confirmation/transfer/promotion/demotion/salary_revision/separation/…, module-level), effective_date, reason, from/to pairs (designation→`Designation`, department→`core.OrgUnit`, location, job_title, salary, manager→`EmployeeProfile`, employee_type — all `related_name="+"`), notes, initiated_by→`User`(editable=False) | Append-only job-history timeline. v1 records events only — does NOT auto-mutate `core.Employment`/`EmployeeProfile` (deferred). Ordering `-effective_date`. **Create/edit/delete are `@tenant_admin_required`** (authoritative HR records carrying salary); list/detail are view-only for members. `initiated_by` stamped from `request.user`. |

**Employee-records views (`apps/hrm/views.py`, the `3.1 … (completion)` section):** full CRUD for both via `crud_*`; `_employee_child_create` (the `?employee=<pk>` pre-fill helper, validates the pk → `cancel_employee`); `employee_document_mark_verified`/`_reject` (`@tenant_admin_required`); `_is_hr_admin(user)` helper (superuser or `is_tenant_admin`) gates confidential docs. `employee_detail` is the hub — adds **Documents** + **Employment Lifecycle** section cards (confidential docs filtered for non-admins). The employee form renders the new personnel-file fields via its generic `{% for field in form %}` loop (no template edit needed). Seeded by `_seed_employee_records` (see Seeder).

### 3.5 Job Requisition (3 tables) — authorization-to-hire hub + JD template library + approval chain

| Model | Number | Key fields | Reuses core / notes |
|-------|--------|-----------|---------------------|
| `JobDescriptionTemplate` (3.5) | `JDTMPL-` | name, designation→`Designation`(SET_NULL), employment_type, jd_summary/responsibilities/requirements/nice_to_have, is_active | Reusable JD library; `unique_together=(tenant,name)`. **Copy-on-apply** — `apply_template_to_requisition` copies the 4 `jd_*` onto a requisition (NOT a live link), so editing a template never mutates open reqs. Mirrors `OnboardingTemplate.designation`. |
| `JobRequisition` (3.5) | `JR-` | title, designation→`Designation`, job_grade→`JobGrade`, template→`JobDescriptionTemplate`, department/cost_center→`core.OrgUnit`(limit_choices_to kind), location, headcount, req_type, employment_type, reason_for_hire, is_replacement_for(free-text stub), posting_type, **hiring_manager/recruiter→`EmployeeProfile`** (never `core.Party`), target_start_date, priority, salary_min/max/currency, estimated_annual_cost, hiring_cost_budget, jd_*(opening-specific copy), notes, **+ workflow-owned (editable=False): status / submitted_at / approved_at / posted_at / filled_at** | The hub — 3.6/3.7/3.8 will FK *in*; it FKs only what exists today. `JR_STATUS_CHOICES`: draft→pending_approval→approved→posted→on_hold→filled (+cancelled/rejected). `clean()`: salary_min≤max, headcount≥1. **Derived props** `is_overdue` / `approval_progress` (approved,total) / `current_approval_step` (lowest pending) — the last two fire a SELECT, so the detail view computes them from an already-fetched list. Indexes (tenant,status)/(tenant,designation)/(tenant,department)/(tenant,hiring_manager)/(tenant,priority,status). |
| `RequisitionApproval` (3.5) | — | requisition→`JobRequisition`(CASCADE), step_order, approver→`User`(SET_NULL, nullable), approver_role, **status**(pending/approved/rejected/returned/skipped, editable=False), decided_at/decided_by(editable=False), comments | Child of the requisition — both the sequential approval chain (current step = lowest `step_order` still `pending`) and the immutable audit trail (rows are UPDATEd by the actions, never form-edited). `unique_together=(requisition,step_order)`; `clean()` step_order≥1. Mirrors `ClearanceItem`. |

**Requisition flow:** create a `JobRequisition` (draft) → optionally add `RequisitionApproval` steps (admin) or let **Submit** auto-build the default HR→Executive chain (`generate_approval_chain`) → **Submit** (draft/rejected→pending_approval) → **Approve Step** each pending step in order (last one flips the req to `approved`) / **Reject** (→rejected, re-submittable) / **Return** (→draft, resets the chain) → **Post** (approved→posted) → **Hold** (→on_hold) → **Mark Filled** (posted/on_hold→filled) / **Cancel**. **Apply Template** (draft/rejected) copies a JD template's body; **Clone** duplicates a req as a fresh draft (no workflow stamps). **All writes are `@tenant_admin_required`** (authoritative HR records carrying salary/headcount — same precedent as `EmployeeLifecycleEvent`); list/detail reads are `@login_required`. Workflow-owned fields are excluded from every form.

**Requisition services (`apps/hrm/services.py`):** `generate_approval_chain(requisition)` — idempotent (returns existing rows if any) default 2-step (HR, Executive) `bulk_create`. `apply_template_to_requisition(requisition, template)` — copies the 4 `jd_*` fields + sets `template`, deliberately leaves `employment_type`; request-free.

### 3.6 Candidate Management (6 tables) — ATS candidate DB + application pipeline + recruiting email/comms + public career portal

A **candidate is a `core.Party`(person) + `PartyRole(role="candidate")`** (the `"candidate"` role was added to `core.PartyRole.ROLE_CHOICES`, migration `core/0004`) + a thin `CandidateProfile` extension — exactly mirroring how `EmployeeProfile` extends `Party`. `JobApplication` FKs the candidate to the **already-built `JobRequisition` (3.5)**. Migrations: `hrm/0011` (the 6 models + `JobRequisition.public_token`), `hrm/0012` (token → unique+null), `hrm/0013` (two ordering indexes).

| Model | Number | Key fields | Reuses core / notes |
|-------|--------|-----------|---------------------|
| `CandidateTag` (3.6) | — | name, color(hex, `HEX_COLOR_VALIDATOR`), description | Talent-pool label, M2M'd onto `CandidateProfile.tags`. CRUD = list/create/edit/delete (**no detail page** — too few fields). `unique_together=(tenant,name)`. |
| `CandidateProfile` (3.6) | `CAND-` | **party→`core.Party`(1:1)**, first_name, last_name, **email(unique per tenant)**, phone, linkedin_url, current_job_title/employer, city, country, years_of_experience, highest_qualification, skill_set(free-text), resume_file, resume_text(keyword search), photo, gender, **status(editable=False)**, source, do_not_contact, gdpr_consent, **gdpr_consent_date(editable=False)**, gdpr_consent_expires, notes, sourced_by→`User`, expected_salary, notice_period_days, **tags→M2M `CandidateTag`** | Mirrors `EmployeeProfile`. `@property name`="First Last". `UniqueConstraint(tenant,email)` = dedup anchor (`clean_email` surfaces a friendly form error). Indexes (tenant,status)/(tenant,source)/(tenant,do_not_contact)/(tenant,created_at). `status` workflow-owned (mark-hired/blacklist/restore actions). |
| `CandidateSkill` (3.6) | — | candidate→`CandidateProfile`(CASCADE), skill_name, proficiency, source(parsed/manual/self_reported) | **Inline child** of the candidate hub (added/removed via POST actions, no own templates — mirrors `RequisitionApproval`/`ClearanceItem`). Powers `skills__skill_name__icontains` filter. `unique_together=(candidate,skill_name)`. |
| `JobApplication` (3.6) | `APP-` | candidate→`CandidateProfile`(CASCADE), **requisition→`JobRequisition`(CASCADE)**, **stage(editable=False)**, source, referred_by→`EmployeeProfile`(SET_NULL), cover_letter_text/file, screening_answers(JSON), rating(1–5), rejection_reason/notes, applied_at, **stage_changed_at/hired_on(editable=False)**, notes | The pipeline record. `APPLICATION_STAGE_CHOICES` (10): applied→screening→phone_screen→assessment→interview→offer→hired (+rejected/withdrawn/on_hold). `APPLICATION_TERMINAL_STAGES=(hired,rejected,withdrawn)`. `UniqueConstraint(candidate,requisition)` (no double-apply). `clean()` rating 1–5. Indexes (tenant,stage)/(tenant,source)/(tenant,requisition)/(tenant,candidate)/(tenant,applied_at). |
| `CandidateEmailTemplate` (3.6) | `CETMPL-` | name, template_type(10 types), subject, body_html(merge fields), is_active, is_auto_send | HRM-owned (does NOT reuse `crm.EmailTemplate`). An `is_auto_send` template whose `template_type` matches a stage transition fires automatically. Merge fields: `{{candidate_name}}/{{job_title}}/{{company_name}}/{{recruiter_name}}/{{application_number}}`. Index (tenant,template_type,is_active). |
| `CandidateCommunication` (3.6) | `CC-` | candidate→`CandidateProfile`(CASCADE), application→`JobApplication`(SET_NULL), template→`CandidateEmailTemplate`(SET_NULL), channel(email/sms/whatsapp), direction, subject, body, sent_by→`User`(null=system auto-send), sent_at, delivery_status | **Append-only** typed email log (created only via the send-email action / `_send_candidate_email`; admin blocks add+change). Indexes (tenant,candidate)/(tenant,application)/(tenant,delivery_status). |

**Application flow:** create a `JobApplication` (stage=applied) — internally via `application_create` (pre-selects `?candidate=`/`?requisition=`, lands on the new detail) or via the **public career portal**. On the application hub: **Move Stage** (`application_advance_stage`, blocked once terminal) — moving to `hired` also stamps `hired_on` + flips `candidate.status="hired"`; **Reject** (reason + notes), **Withdraw**, **Hold** — all guard against terminal stages. Stage-into-a-type with a matching `is_auto_send` template (or an explicit **Send Email**) renders merge fields and logs a `CandidateCommunication`. `_send_candidate_email(application, …)` (in `views.py`): honors `do_not_contact` (sends/logs nothing), resolves a template by instance or active type, renders merge fields, `send_mail` (console backend in dev) wrapped so a transport failure logs `delivery_status="failed"` instead of 500ing.

**Public career portal (UNAUTHENTICATED, `apps/hrm/views.py`):** `careers_list` (per-tenant job board — `?tenant=<slug>` for anon, auto-resolves `request.tenant` for staff; only posted reqs with a token) + `careers_apply(token)` (resolves a `status="posted"` req by its unguessable `public_token`, minted in `jobrequisition_post`). POST creates `Party`+`PartyRole(candidate)`+`CandidateProfile`+`JobApplication(source="careers_page")` under **`req.tenant`** in `transaction.atomic()`, dedups the candidate by email + the application by `get_or_create` (no double-apply), stamps `gdpr_consent_date`, fires the `application_received` auto-template, PRG-redirects `?submitted=1`. `# WARNING:` rate-limiting deferred (django-ratelimit) — flagged in code.

### 3.7 Interview Process (4 tables) — scheduling + panel + structured scorecards over the 3.6 application

Interviews hang off the **already-built 3.6 `JobApplication`** (candidate + requisition are reached through it — `Interview.candidate`/`requisition` are convenience props that traverse `application`, so list views must `select_related("application__candidate","application__requisition")`). Candidate **invites/reminders REUSE the 3.6 pipeline** — `_send_interview_email` composes a body and calls `_send_candidate_email`, honoring `do_not_contact` and logging a `CandidateCommunication` (no new email model); `EMAIL_TEMPLATE_TYPE_CHOICES` gained `interview_reminder` (alongside the existing `interview_invite`). Migrations: `hrm/0014` (the 4 models + the choice add), `hrm/0015` (the `(interview,panelist)` unique_together).

| Model | Number | Key fields | Reuses core / notes |
|-------|--------|-----------|---------------------|
| `Interview` (3.7) | `INTV-` | **application→`JobApplication`(CASCADE)**, title, round_number, mode(in_person/phone/video/one_way_video), **status(editable=False)**, scheduled_at, duration_minutes, location, video_provider(zoom/teams/google_meet/other), meeting_url, interviewer_instructions, notes, scheduled_by→`User`(SET_NULL, set in view), **reminder_sent_at/feedback_reminder_sent_at(editable=False)** | The scheduled round. `INTERVIEW_STATUS_CHOICES` (7): scheduled→confirmed→in_progress→completed (+cancelled/no_show/rescheduled). `INTERVIEW_TERMINAL_STATUSES=(completed,cancelled,no_show)` (reschedule reopens). `@property candidate`/`requisition`/`is_closed`. Indexes (tenant,status)/(tenant,mode)/(tenant,application)/(tenant,scheduled_at). |
| `InterviewPanelist` (3.7) | — | interview→`Interview`(CASCADE), interviewer→`User`(CASCADE), role(lead/interviewer/shadow/observer), rsvp_status(pending/accepted/declined), briefing_notes, notified_at(editable=False) | **Inline child** of the interview hub (add/remove/rsvp POST actions, no own templates — mirrors `CandidateSkill`/`RequisitionApproval`). `unique_together=(interview,interviewer)`. Index (tenant,interview). |
| `InterviewFeedback` (3.7) | `IFB-` | interview→`Interview`(CASCADE), panelist→`InterviewPanelist`(SET_NULL, `related_name="+"`), submitted_by→`User`(SET_NULL), overall_recommendation(strong_no/no/maybe/yes/strong_yes), summary, **is_submitted/submitted_at(editable=False)** | Structured scorecard, one per panelist per interview. `unique_together=[(tenant,number),(interview,panelist)]` — the (interview,panelist) UNIQUE allows multiple panelist=NULL cards (MariaDB/SQLite treat NULLs distinct) but rejects a duplicate non-null panelist. **`is_submitted` is workflow-owned** (the `interviewfeedback_submit` action stamps it + submitted_by/at; NOT a form field, so an edit can't un-submit). Indexes (tenant,interview)/(tenant,overall_recommendation)/(tenant,is_submitted). |
| `FeedbackCriterion` (3.7) | — | feedback→`InterviewFeedback`(CASCADE), criterion_name, rating(1–5), notes | **Inline child** of the scorecard hub (add/remove POST actions, no own templates). `clean()` rejects rating outside 1–5 (also enforced in the form). Index (tenant,feedback). Averages are annotated/aggregated in the views (`Avg("criteria__rating")`), never a query-in-property. |

**Interview flow:** create an `Interview` against an application (status=scheduled; `interview_create` honors `?application=`, stamps `scheduled_by`, lands on the detail hub) → on the hub: **Confirm / Start / Complete / Cancel / No-show** (status machine, blocked once terminal) and **Reschedule** (sets a new `scheduled_at` and reopens a closed round to `rescheduled`); add/remove **panelists** + inline **RSVP**; **Send Invite / Send Reminder** to the candidate (reuse `_send_candidate_email`; reminder stamps `reminder_sent_at`; do_not_contact suppresses) and **Request Feedback** (emails panelist Users best-effort, stamps `feedback_reminder_sent_at`). Scorecards: create an `InterviewFeedback` (draft; `?interview=` pre-select) → add/remove `FeedbackCriterion` rating lines on its hub → **Submit** (stamps is_submitted/submitted_at/submitted_by). **Workflow fields are excluded from every form** — status/scheduled_by/reminder stamps, rsvp/notified_at, is_submitted/submitted_by/submitted_at — set only by the audited POST actions. **Deletes are `@tenant_admin_required`** (auditable records); the rest is `@login_required` (scheduling/feedback are normal recruiter actions). `meeting_url` is rendered through the `core` `|safe_external_url` filter so only http/https schemes become a clickable link (defense-in-depth vs a `javascript:` href).

### 3.8 Offer Management (5 tables) — offer letter + multi-step approval + tracking + background check + pre-boarding over the 3.6 application

| Model | Prefix | Key fields | Notes |
|---|---|---|---|
| `OfferLetterTemplate` (3.8) | `OLTMPL-` | name, is_active, body_html (merge tokens `{{candidate_name}}/{{job_title}}/{{base_salary}}/{{currency}}/{{start_date}}/{{company_name}}/{{hiring_manager_name}}`) | Reusable printable letter body (mirrors `CandidateEmailTemplate`). `unique_together=(tenant,name)`. Index (tenant,is_active). The `offer_letter_print` view merges its tokens via `_apply_merge`. |
| `Offer` (3.8) | `OFR-` | **application→`JobApplication`(CASCADE)**, offer_letter_template→`OfferLetterTemplate`(SET_NULL), base_salary, currency (defaults from requisition), bonus_amount/bonus_terms, signing_bonus, equity_terms, relocation_assistance, benefits_summary, start_date, expires_on, **status(editable=False)**, decline_reason/decline_notes, signed_document(FileField), signature_status, **+ workflow stamps (editable=False): extended_by/extended_at/accepted_at/declined_at/rescinded_at/created_by** | The offer hub. `OFFER_STATUS_CHOICES`: draft→pending_approval→approved→extended→accepted/declined/rescinded/expired. `OFFER_TERMINAL_STATUSES=(accepted,declined,rescinded,expired)`. **Derived props** `is_overdue` (expires_on past + non-terminal), `is_closed`, `total_compensation` (base+bonus+signing — drives the approval threshold), `approval_progress`/`current_approval_step` (fire a SELECT — the detail view computes from the fetched list). `@property candidate`/`requisition` via application. `clean()` rejects negative amounts. Indexes (tenant,status)/(tenant,application)/(tenant,created_at). |
| `OfferApproval` (3.8) | — | offer→`Offer`(CASCADE), step_order, approver→`User`(SET_NULL), approver_role(reuses `APPROVER_ROLE_CHOICES`), **status(editable=False, reuses `APPROVAL_STEP_STATUS_CHOICES`)**, decided_at/decided_by(editable=False), comments | **Inline child** of the offer hub (add/delete POST actions, draft-only + admin — mirrors `RequisitionApproval`). `unique_together=(offer,step_order)`. `clean()` step_order≥1. Indexes (offer,status)/(approver,status). |
| `BackgroundVerification` (3.8) | `BGV-` | offer→`Offer`(CASCADE), vendor(checkr/hireright/sterling/other), check_type(criminal/employment/education/professional_license/identity/credit), **status(editable=False)**, result(clear/consider/not_applicable), consent_given/consent_date(editable=False), report_file(FileField), initiated_at/completed_at/initiated_by(editable=False), notes | `BGV_STATUS_CHOICES`: not_started/consent_pending→initiated→in_progress/action_needed/ready_for_review→completed (Checkr/Sterling lifecycle). `result` is set only by `backgroundverification_complete`, NOT the form. `BGV_MANUAL_TRANSITION_STATUSES=(in_progress,action_needed,ready_for_review)` shared by the mark-status guard + the detail dropdown. Indexes (tenant,status)/(tenant,offer)/(tenant,check_type)/(tenant,created_at). |
| `PreboardingItem` (3.8) | — | offer→`Offer`(CASCADE), document_type(id_proof/address_proof/tax_form/bank_details/nda/education_certificate/background_check_consent/other), is_required, **status(editable=False)** (pending/submitted/verified/rejected), uploaded_file(FileField), submitted_at/verified_by/verified_at/reminder_sent_at(editable=False), notes | **Inline child** of the offer hub (add/delete/submit/verify/reject/send-invite POST actions, no own templates — distinct from post-start 3.3 `OnboardingDocument`). Indexes (tenant,offer)/(tenant,status). |

**Offer flow:** create an `Offer` against an application (status=draft; `offer_create` honors `?application=`, stamps `created_by`, defaults `currency` from the requisition, lands on the detail hub) → optionally add/remove **approval steps** (draft + admin only) → **Submit** (builds the default chain via `generate_offer_approval_chain` if none, resets the whole chain to pending so a reject→resubmit re-approves from the top) → **Approve Step** ×N (last step clears → status=approved) or **Reject Step** (reopens to draft) → **Extend** (gated on all steps approved; stamps extended_by/at, sends the offer email via `_send_candidate_email` template_type="offer", sets signature_status=sent) → **Accept** (status=accepted, drives `JobApplication.stage`→hired + hired_on, raises the pre-boarding checklist via `generate_preboarding_checklist`) / **Decline** (requires a valid decline_reason) / **Rescind** (admin) / **Expire** (only when extended + overdue). **Background checks** are ordered from the hub (`?offer=`): consent → **Initiate** (admin; blocked without consent) → **Update Status** (admin) → **Complete** with a result (admin). **Pre-boarding**: auto-raised on accept; per-item **Mark Submitted** (candidate/HR; clears stale verify stamps), **Send Invite** (reuses `_send_candidate_email`, stamps reminder_sent_at, do_not_contact suppresses), **Verify/Reject/Delete** (admin). **Workflow fields are excluded from every form** — status + all `*_at`/`*_by` stamps, BGV `result` — set only by the audited POST actions. **Privileged actions are `@tenant_admin_required`** (submit/approve/reject/extend/rescind/expire/delete, approval add/delete, preboarding verify/reject/delete, BGV initiate/mark-status/complete, letter-template delete); accept/decline/send-email + preboarding add/submit/send-invite are `@login_required`. File uploads (signed_document/report_file/uploaded_file) are extension+size validated via `_validate_upload`. The printable offer letter is a standalone page (`offer_letter.html`, not a base.html child; mirrors `relieving_letter.html`). **Deferred:** live e-sign / background-check vendor APIs, adverse-action dispute flow, parallel/rule-engine approval routing, acceptance-rate analytics, scheduled pre-boarding dispatch.

### 3.15 Statutory Compliance (4 tables) — Indian PF/ESI/PT/TDS/LWF config + state rules + per-employee IDs + returns register over the 3.14 payroll spine

| Model | Prefix | Key fields | Notes |
|---|---|---|---|
| `StatutoryConfig` (3.15) | — | **tenant `OneToOneField` (overrides the abstract FK — one row per tenant)**, PF (pf_establishment_code, pf_wage_ceiling=15000, pf_employee_rate/pf_employer_rate=12/12), ESI (esi_employer_code, esi_wage_ceiling=21000, esi_employee_rate/esi_employer_rate=0.75/3.25), PT (pt_default_state), TDS (tan_number, tds_circle_address, pan_of_deductor), LWF (is_lwf_applicable) | Tenant settings **singleton** (like Zoho's Statutory Components screen). `StatutoryConfig.for_tenant(tenant)` get-or-creates the one row. Rates/ceilings are documented here; actual per-payslip computation stays in `PayComponent`/`Payslip.recompute()`. **No list/create/delete — detail + edit only**; edit is `@tenant_admin_required`. |
| `StatutoryStateRule` (3.15) | — | state(`INDIAN_STATE_CHOICES`), scheme(pt/lwf), PT: income_from/income_to/pt_monthly_amount/pt_deduction_month, LWF: lwf_employee_contribution/lwf_employer_contribution/lwf_periodicity(monthly/half_yearly/annual)/lwf_due_month_1/lwf_due_month_2, registration_number, is_active, effective_from | State-wise PT slabs + LWF rules (one shared table). `clean()` enforces scheme-required fields + one **active** LWF row per (tenant,state) (supersede-not-edit). `unique_together(tenant,state,scheme,income_from)` — LWF income_from=None. The active-LWF-per-state guard also fires on **CREATE** via `StatutoryStateRuleForm.clean()` (model.clean can't see tenant pre-save). Indexes (tenant,scheme)/(tenant,state). |
| `EmployeeStatutoryIdentifier` (3.15) | — | **employee `OneToOneField`→`EmployeeProfile`**, uan_number, pf_number, esi_number, pt_state(`INDIAN_STATE_CHOICES`), is_pf_applicable, is_esi_applicable | 1:1 companion for government IDs that don't fit `EmployeeProfile.national_id` (PAN). `masked_uan_number()/masked_pf_number()/masked_esi_number()` (last-4, mirror `EmployeeProfile._mask_last4`) — **masked in list+detail; raw only in the edit form input**. uan/pf/esi added to `_SENSITIVE_AUDIT_FIELDS`. Create form narrows to employees without an identifier. Index (tenant,employee). |
| `StatutoryReturn` (3.15) | `SCR-` | scheme(pf/esi/pt/tds_24q/tds_form16/lwf), period_type(monthly/quarterly/half_yearly/annual), period_start/period_end, cycle→`PayrollCycle`(SET_NULL, monthly single-cycle), employee→`EmployeeProfile`(SET_NULL, only for tds_form16), **employee_contribution_total/employer_contribution_total/headcount (editable=False, derived)**, due_date, status(pending/filed/paid/late), filed_on/paid_on(editable=False), payment_reference, registration_number_used(editable=False, snapshot), notes | Per-scheme/period challan/return register. `recompute()` aggregates `PayslipLine` (statutory_deduction, scheme keyword-matched via `SCHEME_KEYWORDS` on component_name — **v1, no per-line scheme tag**) by contribution_side: employer=`contribution_side="employer"`, employee=everything else (mirrors 3.14 `payrollcycle_lock`, no double-count of "both"). `is_locked`=status≠pending; `is_overdue`=pending+past due. `unique_together(tenant,scheme,period_start,employee)` + `StatutoryReturnForm.clean()` closes the org-level (employee=None) NULL-distinct duplicate hole. Indexes (tenant,status)/(tenant,due_date)/(tenant,scheme). |

**Statutory flow:** configure once via `StatutoryConfig` (tenant-admin) → optionally add `StatutoryStateRule` PT slabs / LWF rows per state → set each employee's `EmployeeStatutoryIdentifier` (UAN/PF/ESI) → create a `StatutoryReturn` (scheme + period, optional cycle) → **Generate** (`@tenant_admin_required`; `recompute()` rolls up the period's `PayslipLine` totals — the seeded PF return shows employer ≈ Σ employer-PF lines) → **Mark Filed** (pending→filed) → **Mark Paid** (filed/pending→paid; **paying after due_date auto-flags `late`**). The **compliance calendar** (`statutory_compliance_calendar`) is a read-only cross-scheme view grouping returns into Overdue/Pending/Filed/Settled. Edit/delete/generate are **pending-only** (`is_locked` guard). Reuses `EmployeeProfile`/`PayrollCycle`/`PayslipLine`/`PayComponent`; **touches no `accounting.PayrollRun`/`JournalEntry`** (no GL path). **Deferred:** ECR/ESIC file-format + portal upload, TRACES/challan matching, Form 16/24Q PDF rendering, AI pre-filing error detection, rate-change alerting, and a per-`PayslipLine` scheme tag (to replace the v1 component_name-substring match).

### 3.16 Tax & Investment (6 tables) — India income-tax declaration + computation engine over 3.13/3.14/3.15; Form 16 reuses `StatutoryReturn(tds_form16)` (no new Form 16 table)

| Model | Prefix | Key fields | Notes |
|---|---|---|---|
| `TaxRegimeConfig` (3.16) | — | financial_year, regime(old/new), standard_deduction(75k new/50k old), cess_rate(4), rebate_income_threshold + rebate_max_tax (Section 87A), is_default_regime, tax_law_reference | Per-(tenant, FY, regime) rate master. `unique_together(tenant, financial_year, regime)`. Its `slab_bands` are the bracket table the engine walks. |
| `TaxSlabBand` (3.16) | — | config FK, income_from, income_to(null=top band), rate_percent, sequence | Child of `TaxRegimeConfig` — the progressive slab table. `clean()` income_to≥income_from. Managed **inline** on the config detail (like `SalaryStructureLine`). |
| `InvestmentDeclaration` (3.16) | `ITD-` | employee FK(PROTECT), financial_year, regime_elected(old/new, default new), status(draft/submitted/locked), declaration_window_open/close, proof_window_open/close, previous_employer_income/tds, submitted_at(editable=False) | Per-employee-per-FY declaration header. `is_editable`=status draft. `unique_together(tenant, employee, financial_year)`. Submit(→submitted)/Lock(→locked, tenant-admin) freezes the lines. |
| `InvestmentDeclarationLine` (3.16) | — | declaration FK, section_code(80c/80d/80d_parents/hra/24b_home_loan_interest/80ccd_1b_nps/lta/80e_education_loan/other_chapter_via), declared_amount, verified_amount(editable=False), HRA sub-fields(monthly_rent_amount/is_metro_city/landlord_pan), lender_name(24b) | Section-wise declared vs verified breakdown. `effective_amount`=verified-else-declared. `recompute_verified()` sums the line's `verified` proofs. `unique_together(tenant, declaration, section_code)`. Managed **inline** on the declaration detail (draft-only). |
| `InvestmentProof` (3.16) | — | declaration_line FK, file(FileField, `_validate_upload` guard), title, amount, verification_status(pending/verified/rejected/on_hold, editable=False), verified_by/verified_at(editable=False), rejection_reason | Uploaded proof + 4-state verify workflow (mirrors `EmployeeDocument`). Verify/reject/on_hold `@tenant_admin_required`, only from pending/on_hold (terminal-state guard); rolls up the line's `verified_amount`. |
| `TaxComputation` (3.16) | `TXC-` | employee FK(PROTECT), declaration FK(PROTECT), financial_year, computation_type(provisional/final), manual_override_amount/override_reason, remaining_pay_periods, **tax_payable/tax_paid_ytd/monthly_tds_amount (editable=False, derived)**, statutory_return FK→`StatutoryReturn`(SET_NULL, editable=False), computed_at | The **engine**. `save()` derives financial_year from the declaration (form excludes it). `recompute()`: `_progressive_tax` slab-walk → 87A rebate → 4% cess; HRA 3-way min; `_chapter_via` regime-filtered (new keeps only `NEW_REGIME_ALLOWED_SECTIONS`={80ccd_1b_nps}) + `SECTION_CAPS`(80c 1.5L/NPS 50k/24b 2L, surfaced via `capped_sections`); `tax_paid_ytd` aggregates TDS `PayslipLine`s over the FY (reuses 3.15 `SCHEME_KEYWORDS["tds_24q"]`); `monthly_tds_amount`=(payable−paid)/periods or override. Derived props (`gross_annual_income`/`hra_exemption`/`taxable_income_old/_new`/`tax_old_regime/_new`/`cheaper_regime`) are memoized via a per-instance `_engine_cache` (~9 queries/detail, not 60). `final` requires proof_window_close passed. `link_form16()` update_or_creates the `StatutoryReturn(tds_form16)` row per (tenant,employee,FY-start). `unique_together(tenant, employee, financial_year)`, recomputed in place. |

**Tax flow:** set up `TaxRegimeConfig` (old + new) with `TaxSlabBand`s per FY → create an `InvestmentDeclaration` for an employee/FY, add 80C/80D/HRA/… `InvestmentDeclarationLine`s (draft) → **Submit** → **Lock** (tenant-admin; lines immutable) → employees upload `InvestmentProof`s (gated on the **proof window**, not is_editable) → tenant-admin **Verify/Reject/On-Hold** (rolls up `verified_amount`) → create a `TaxComputation` (employee+declaration; FY auto-derived), **Generate** (`recompute()`; the seeded demo shows **52520 old vs 0 new** via 87A) → **Link Form 16** (`link_form16()` → the `tds_form16` `StatutoryReturn`) → view **Form 16 Part B** (`form16_partb` report) + the **regime comparison** (`tax_regime_comparison`, old-vs-new + savings). `TaxComputationForm.clean()` guards employee/declaration mismatch + the (tenant,employee,FY) duplicate; `investmentdeclarationline_create` wraps save in a `transaction.atomic()` savepoint (friendly duplicate-section redirect). Reuses `EmployeeProfile`/`EmployeeSalaryStructure`/`PayslipLine`/`StatutoryConfig`/`StatutoryReturn`; **posts no GL**. **Deferred:** Form 16/16A PDF+merge+email, TRACES, bulk declaration import, AI anomaly detection, auto regime-lock, instrument-level 80C sub-ledger, a per-`PayslipLine` scheme tag, and a slab-band gap/overlap validation.

### 3.17 Payout & Reports (4 tables) — salary disbursement + reconciliation over 3.14; reuses `Payslip.net_pay` + `EmployeeProfile` MASKED bank; posts no GL

| Model | Prefix | Key fields | Notes |
|---|---|---|---|
| `PayoutBatch` (3.17) | `POB-` | cycle FK→`PayrollCycle`(PROTECT), status(draft/approved/disbursed/partially_disbursed/reconciled), bank_file_format(neft/nach/ach/manual/other), source_bank_name, source_account_last4(RegexValidator masked-only), generated_by/at + approved_by/at + disbursed_at(editable=False), notes | Disbursement header from **one locked cycle** (`clean()` requires `cycle.is_locked`). `unique_together(tenant, cycle)` (+ `PayoutBatchForm.clean()` closes the create-time dup 500; dropdown lists only locked, un-batched cycles). `_current_payments()`=`payments.filter(retries__isnull=True)` (excludes superseded originals); cached `_totals()` derives headcount/total_amount/paid_count/paid_amount/failed_count/on_hold_count. `is_editable`=draft. **List view annotates** list_headcount/list_total/list_paid (O(1), not per-row `_totals()`). |
| `PayoutPayment` (3.17) | — | batch FK(CASCADE), payslip FK→`Payslip`(PROTECT), employee FK→`EmployeeProfile`(PROTECT), net_amount(snapshot of net_pay, editable=False), **bank_name_snapshot/bank_account_last4_snapshot/bank_routing_snapshot (MASKED copies via masked_bank_account()/masked_bank_routing() — never raw, editable=False)**, payment_method, status(pending/processing/paid/failed/returned/on_hold), transaction_reference(UTR), initiated_at/paid_on(editable=False), failure_reason, retry_of self-FK(SET_NULL) | Per-employee disbursement row. **No `unique_together`** — a retry is a NEW row (`retry_of`→original), so retries coexist; the generate action (draft-only delete+recreate) guarantees one original per payslip; no user-facing create form. Snapshots are pre-masked so need no `_SENSITIVE_AUDIT_FIELDS` redaction. |
| `PayslipDistribution` (3.17) | — | payslip `OneToOneField`(CASCADE), delivery_channel(email/portal/print), status(pending/sent/viewed/downloaded/failed), sent_to_email(snapshot, editable=False), sent_at/viewed_at/downloaded_at(editable=False), sent_by | Payslip send→view→download tracking (PDF+SMTP deferred). `for_payslip()` lazy get-or-create. `send`/`send_cycle` `@tenant_admin_required`; `mark_viewed`/`mark_downloaded` `@login_required` (no user↔employee link yet — SECURITY NOTE, scope to owner later). |
| `BankReconciliation` (3.17) | `BRC-` | batch FK→`PayoutBatch`(PROTECT), statement_date, status(pending/in_progress/reconciled/discrepancy), matched_count/matched_amount/unmatched_count/unmatched_amount(editable=False, derived), statement_reference, reconciled_by/at(editable=False), notes | `recompute()` matches the batch's current payments by UTR+status: paid + non-blank transaction_reference = matched, everything else unmatched; status reconciled iff unmatched==0 else discrepancy. **No `BankStatementLine` table** — matches directly against `PayoutPayment`. |

**Payout flow:** create a `PayoutBatch` from a **locked** `PayrollCycle` → **Generate** (`@tenant_admin_required`; one `PayoutPayment` per payslip, snapshots net_pay + masked bank; on-hold payslips → `on_hold` rows) → **Approve** (draft→approved) → **Disburse** (approved→disbursed; pending→processing; bank-file export deferred) → per payment **Mark Paid**(+UTR)/**Mark Failed**(+reason)/**Retry** (a failed row → a new pending `retry_of` row; `_recompute_batch_status` — the one derivation point — re-derives partially_disbursed/disbursed over current payments). Payslips: **Send** (single) / **Send a cycle** (bulk) → viewed/downloaded signals. **Reconcile** a `BankReconciliation` (matches by UTR → reconciled/discrepancy; a full match flips the batch to reconciled). Reports (no model): **payment_register** (bank-advice, by-status/by-method, masked accounts) + **payout_exceptions** (failed/returned un-retried, with Retry). Reuses `PayrollCycle`/`Payslip`/`EmployeeProfile`; **posts no GL** (L29). **Deferred:** bank-file-format writers, live bank API, prenote verification, payslip PDF render, live statement feed, `BankStatementLine`, period-over-period anomaly detection, WPS/non-India formats, auto-retry scheduling, and a user↔employee link for owner-scoped view/download.

### 3.18 Goal Setting (4 tables) — first Performance-Management sub-module; OKR mechanics over `EmployeeProfile` + `core.OrgUnit`; **no new core-spine entity**, posts no GL
| Model | № | Key fields | Notes |
|---|---|---|---|
| `GoalPeriod` (3.18) | — (`TenantOwned`, name-identified like `JobGrade`) | name, period_type(quarterly/half_yearly/annual/custom), start_date, end_date, status(draft/active/closed/archived), description | Quarterly/annual OKR cycle catalog (Goal Timeline). `unique_together(tenant, name)`. `clean()` rejects end_date<=start_date. Derived props `objective_count` (list view uses O(1) `.annotate(num_objectives=Count)`) + `avg_progress_pct` (simple mean of objective progress; detail view prefetches `objectives__key_results`). "Current" = `status="active"` (no second is_current flag). |
| `Objective` (3.18) | `OBJ-` | title, description, **owner FK→`EmployeeProfile`(PROTECT)**, **goal_period FK→`GoalPeriod`(PROTECT)**, **parent_objective self-FK(SET_NULL, related_name="child_objectives")**, **department FK→`core.OrgUnit`(SET_NULL)**, scope(company/department/team/individual), target_type(aspirational/committed), weight, status(draft/active/at_risk/completed/cancelled), start_date, due_date | The "O". `parent_objective` = the vertical alignment/cascade link (Goal Alignment); `clean()` blocks self-parenting + multi-hop cycles. **Derived, never stored:** `progress_pct` (KR-weighted rollup via cached `_krs()`, simple-mean fallback when all weights 0, ZERO for 0 KRs), `health_status`+`health_status_display` (pace: progress vs time-elapsed-in-period, falls back to the period window when own start/due null), `key_result_count`. Indexes on (tenant, status/period/owner/parent/department). |
| `KeyResult` (3.18) | `KR-` | objective FK(CASCADE), title, metric_type(numeric/percentage/currency/boolean/milestone), start_value/target_value/current_value(nullable Decimal), is_milestone_event, unit, weight, status(not_started/in_progress/completed/cancelled) | The "KR". `metric_type` folds the Viva Goals/Perdoo KR-type split into one CharField (no 5th model). `clean()` requires target_value for numeric/percentage/currency. **Derived:** `progress_pct` (start→current→target interp clamped [0,100], denom-zero guard; boolean→0/100; milestone→completed?100:0) + `health_status`+`health_status_display`. `current_value` also directly editable on the KR form. |
| `GoalCheckIn` (3.18) | `GCI-` | key_result FK(CASCADE), checkin_date(default localdate), value_at_checkin(nullable), confidence(on_track/at_risk/off_track), is_milestone_event, comment, **created_by FK→`EmployeeProfile`(SET_NULL, editable=False)** | Append-only progress-update history log (Goal Tracking) — **no edit view** (delete+recreate to correct). `save()` advances `key_result.current_value` **only on create + when value present**. `created_by` resolved server-side from `request.user.party.employee_profile` (never form-set). |

**Goal flow:** define a `GoalPeriod` → **Activate**/**Close** it (`@tenant_admin_required`; status is workflow-owned, NOT on the form) → create `Objective`s scoped to the period, optionally aligned up a `parent_objective` cascade + tagged to a `core.OrgUnit` department → add `KeyResult`s (nested create under the objective, weight defaults to an equal split `100/(siblings+1)`) → log `GoalCheckIn`s per KR (nested create; advances `current_value`, records confidence + comment). **Objective progress** = weighted average of its KRs' progress×weight (derived); **health** = on_track/at_risk/off_track by realized progress vs time elapsed in the period. Views: **objective_tree** (3-level company→dept→individual cascade, prefetched, `tree_max_depth=3`) serves Goal Alignment; **objective_list?mine=1** filters to the logged-in user's own objectives + their direct reports' (via the derived `EmployeeProfile.manager`/`employment.manager` reporting line — no new FK); **goalcheckin_list** is the org-wide check-in history. Reuses `EmployeeProfile` (owner/created_by) + `core.OrgUnit` (department, exactly like `Designation.department`); **no new core-spine entity, posts no GL**. **Deferred to 3.19-3.21 + later:** always-on KPI catalog, horizontal/M2M alignment, objective-to-cascade weighting, AI-drafted OKRs/summaries, external progress sync (Jira/Azure/Salesforce), drift-alert notifications, step-weighted milestone sub-tracking, and all review-cycles/ratings/360/kudos/1:1/PIP (3.19 Performance Review, 3.20 Continuous Feedback, 3.21 Performance Improvement).

### 3.19 Performance Review (4 tables) — 2nd Performance-Management sub-module; formal appraisal cycles over `EmployeeProfile`; references the 3.18 `GoalPeriod`/`Objective`; **CONFIDENTIAL** (not company-open); no new spine, posts no GL
| Model | № | Key fields | Notes |
|---|---|---|---|
| `ReviewCycle` (3.19) | — (`TenantOwned`, name-identified like `GoalPeriod`) | name, cycle_type(annual/half_yearly/quarterly/custom), status(draft/self_assessment/manager_review/calibration/released/closed — the **phase machine**, `PHASE_ORDER` tuple), self_review_start/end, manager_review_start/end, calibration_date, results_release_date, goal_period FK→`GoalPeriod`(SET_NULL), description | Named appraisal cycle. `unique_together(tenant, name)`. `clean()` rejects self/manager window end<=start + manager_start<self_end. `review_count` prop. Advanced one phase at a time via `reviewcycle_advance_phase` (`@tenant_admin_required`) — status is **workflow-owned, NOT on the form** (the 3.18 GoalPeriodForm lesson). |
| `ReviewTemplate` (3.19) | `RVT-` | name, review_type(self/manager/peer/upward/skip_level), rating_scale_max(2..10, default 5), include_goals, is_anonymous(peer/360 default), description, is_active | The review-form definition per participant type (a cycle can attach several — the peer form ≠ manager form). `usage_count` prop. FK from PerformanceReview is SET_NULL (retire without blocking). |
| `PerformanceReview` (3.19) | `RVW-` | cycle FK(PROTECT), template FK(SET_NULL), **subject FK→`EmployeeProfile`(PROTECT)**, **reviewer FK→`EmployeeProfile`(PROTECT)**, review_type, status(draft/submitted/shared/acknowledged), manager_rating/calibrated_rating/potential_rating(nullable), strengths/improvements/**private_notes**(manager-only)/calibration_notes, is_anonymous, submitted_at/shared_at/acknowledged_at/acknowledged_by(editable=False) | The per-instance review row (self=subject==reviewer; peer/upward=multiple rows). **Derived, never stored:** `overall_rating` (weighted mean of ratings via cached `_ratings()`, **`None`** when unrated — not 0), `rating_count`, `effective_rating` (**calibrated overrides overall**, Workday two-field pattern), `reviewer_anonymized` (is_anonymous & peer/upward), `goal_period` passthrough. `clean()`: self-review reviewer==subject; non-self reviewer!=subject; manager_rating only on manager reviews. |
| `ReviewRating` (3.19) | `RVR-` | review FK(CASCADE), criterion_label, criterion_category(competency/goal/value/custom), rating_value, weight, comment | Per-competency line. `weight` mirrors `KeyResult.weight` so `overall_rating` derives (weighted mean). `clean()`: rating_value within `review.template.rating_scale_max`; weight non-negative. |

**Review flow:** define a `ReviewCycle` (optionally linked to the 3.18 active `GoalPeriod`) → **Advance Phase** (`@tenant_admin_required`, one PHASE_ORDER step at a time) → create `PerformanceReview`s (self/manager/peer/upward) with a `ReviewTemplate` → add `ReviewRating` competency lines (nested create, equal-split weight default) → **Submit** (reviewer-or-admin; snapshots `manager_rating` on a manager review) → **Share** (`@tenant_admin_required`) → **Acknowledge** (subject-only). **Calibrate** a manager review (`@tenant_admin_required`, writes `calibrated_rating`/`potential_rating` via the narrow `CalibrationForm` — the ONLY calibrated_rating write path); the **calibration_board** (`?cycle=`) ranks a cycle's manager reviews by `effective_rating` (Stack-Ranker style). A review's **goal-review section** (when `template.include_goals`) reads the subject's `Objective`s for `cycle.goal_period`. **CONFIDENTIALITY (key design point — unlike 3.18 OKRs):** performance data is visible ONLY to the subject, the reviewer, or a tenant admin — `_can_view_review` gates `performancereview_detail`/`reviewrating_detail` (403 otherwise) and `_visible_reviews_q` filters `performancereview_list` + the `reviewcycle_detail` roster to the viewer's own reviews; `private_notes` is additionally hidden from the subject (`show_private = admin or reviewer`); content is **edit-locked once non-draft** (`_can_edit_review` = draft-only + reviewer/admin, protecting the submit→share→acknowledge audit trail). Reuses `EmployeeProfile` + the 3.18 `GoalPeriod`/`Objective`; **no new core-spine entity, posts no GL**. **Deferred to 3.20-3.21 + later:** continuous feedback/kudos/1:1s (3.20), PIP/coaching (3.21), a dedicated `ReviewCriterion` competency catalog, a `CalibrationSession` grouping table, bell-curve/9-box visualizations (reports over `calibrated_rating`/`potential_rating`), multi-level calibration roll-up, external/non-employee reviewers, AI features.

## URLs / routes (`apps/hrm/urls.py`, `app_name="hrm"`)
- Landing: `hrm:hrm_overview` (`/hrm/`).
- Per model `<entity>` in {`designation`, **`jobgrade`, `department`, `costcenter`** (3.2), `employee`, `leavetype`,
  `leaveallocation`, `leaverequest`, **`leaveencashment`** (3.10), **`timesheet`, `overtimerequest`** (3.11), `publicholiday`, `shift`, `shiftassignment`, `attendancerecord`,
  **`geofence`, `attendanceregularization`** (3.9),
  **`onboardingtemplate`, `onboardingtemplatetask`, `onboardingprogram`, `onboardingtask`, `onboardingdocument`,
  `assetallocation`, `orientationsession`**, **`separationcase`, `exitinterview`, `clearanceitem`,
  `finalsettlement`**}: `<entity>_list/_create/_detail/_edit/_delete`.
- **Employee records (3.1):** `employee_document_list/_create/_detail/_edit/_delete` (`/hrm/employee-documents/`) +
  POST `employee_document_mark_verified`/`employee_document_reject` (`@tenant_admin_required`);
  `employee_lifecycle_list/_create/_detail/_edit/_delete` (`/hrm/lifecycle-events/`; create/edit/delete are
  `@tenant_admin_required`). Both create pages honor `?employee=<pk>` to pre-fill + redirect to the employee hub.
- **Org-structure derived pages (3.2, no model):** `hrm:org_chart` (`/hrm/org-chart/`, `?view=reporting|department`
  toggle — reporting-line tree from `core.Employment.manager` / by-department grouping; excludes terminated
  employees; capped at 500) and `hrm:company_setup` (`/hrm/company-setup/`, read-only — company `OrgUnit` +
  `tenants.BrandingSetting`, links out to `core:orgunit_list` and `tenants:brandingsetting_list`).
- `department`/`costcenter` are **HRM companion profiles** over `core.OrgUnit` nodes — the OrgUnit nodes themselves
  are created/managed in `core:orgunit_list`; the HRM pages enrich them (head/owner/budget/code). Delete removes
  only the companion row, never the OrgUnit.
- Leave workflow extras: `hrm:leaverequest_submit/_approve/_reject/_cancel` (all POST-only).
- **Holiday Management (3.12):** floating-holiday election workflow `hrm:floatingholidayelection_approve/_reject`
  (POST-only, `@tenant_admin_required`; reject reads a `note` from POST); `_edit`/`_delete` are locked once the
  election is decided (status≠pending → redirect to detail). Public holidays + holiday policies are plain CRUD.
- **Salary Structure (3.13):** `SalaryStructureLine` is managed **inline** on the salary-structure detail —
  `hrm:salarystructureline_add` (POST-only; presets `instance(tenant, template)` before validation so the form
  `clean()` duplicate-check + save see the template), `_edit` (GET+POST, own `line_form.html`), `_delete` (POST);
  mirrors the 3.11 timesheet-entry hub. `hrm:paycomponent_delete` is guarded against in-use lines (PROTECT → friendly
  message, not a 500). `EmployeeSalaryStructure` `_edit`/`_delete` reject a `superseded` record (read-only history →
  redirect to detail). Pay components + salary templates + employee assignments are otherwise plain CRUD.
- **Payroll Processing (3.14):** the `PayrollCycle` workflow is `hrm:payrollcycle_generate` (POST, draft-only —
  builds a `Payslip` per active `EmployeeSalaryStructure` + `recompute()`; **preserves** manual arrears/bonus/hold
  across a re-generate; effective-date-windowed) → `_submit` (`@login_required`; off_cycle/bonus go straight to
  approved) → `_approve`/`_reject` (`@tenant_admin_required`) → `_lock` (`@tenant_admin_required`; rolls up totals,
  creates a draft `accounting.PayrollRun`, links it — **HRM builds no JournalEntry**, accounting's `payroll_run_post`
  posts the GL). A locked cycle is immutable (edit/delete/generate/payslip-edit/hold all rejected). Salary holds:
  `hrm:payslip_hold`/`_release` (`@tenant_admin_required`, pre-lock only). `payslip_edit` (draft-only) recomputes.
  **The privileged buttons (approve/reject/lock/hold/release) are gated in the template behind
  `is_superuser or is_tenant_admin`** (app-wide convention — non-admins see an awaiting-admin notice).
- **Statutory Compliance (3.15):** `StatutoryConfig` is a singleton — `hrm:statutoryconfig_detail` + `_edit`
  only (no list/create/delete; `_edit` is `@tenant_admin_required`). `hrm:statutorystaterule_*` and
  `hrm:employeestatutoryidentifier_*` are standard `@login_required` CRUD. `hrm:statutoryreturn_*` CRUD +
  workflow: `_generate`/`_mark_filed`/`_mark_paid` (POST, `@tenant_admin_required`) — generate re-aggregates the
  period's `PayslipLine` totals via `StatutoryReturn.recompute()`, mark_paid after due_date auto-sets `late`;
  edit/delete/generate are pending-only (`is_locked`). `hrm:statutory_compliance_calendar` is a read-only grouped
  overview. Return list scheme deep-links: `?scheme=pf|esi|pt|tds_24q|lwf`.
- **Tax & Investment (3.16):** `hrm:taxregimeconfig_*` CRUD + inline slab bands (`taxslabband_create/edit/delete`,
  config-scoped, like 3.13's `salarystructureline_*`) + `tax_regime_comparison` (read). `hrm:investmentdeclaration_*`
  CRUD + `_submit` (draft→submitted) / `_lock` (`@tenant_admin_required`, →locked) + inline
  `investmentdeclarationline_*` (declaration-scoped, gated by `is_editable`; `_create` wraps save in an atomic
  savepoint for the friendly duplicate-section redirect). `hrm:investmentproof_upload` (line-scoped, gated on the
  **proof window** not is_editable) + `_verify`/`_reject`/`_on_hold` (POST, `@tenant_admin_required`, pending/on_hold
  only, roll up the line's `verified_amount`). `hrm:taxcomputation_*` CRUD + `_generate` (recompute) / `_link_form16`
  (both `@tenant_admin_required`) + `form16_partb` (read report). All privileged buttons are `is_superuser or
  is_tenant_admin`-gated in the templates.
- **Payout & Reports (3.17):** `hrm:payoutbatch_*` CRUD (edit/delete draft-only; delete pre-checks reconciliations)
  + `_generate` (from a locked cycle, snapshots masked bank) / `_approve` / `_disburse` (all
  `@tenant_admin_required`) + `payment_register` (read). Per-payment `hrm:payoutpayment_mark_paid` (POST
  transaction_reference) / `_mark_failed` (POST failure_reason) / `_retry` (new retry_of row) — all
  `@tenant_admin_required`, pending/processing-only (retry failed/returned-only), each recomputes the batch status via
  the shared `_recompute_batch_status`. `payout_exceptions` (read, failed/returned un-retried + inline Retry).
  `hrm:payslipdistribution_list/_detail` + `_send` / `_send_cycle` (POST a `cycle` field, `@tenant_admin_required`) +
  `_mark_viewed`/`_mark_downloaded` (`@login_required`, forward-only, no ownership link yet). `hrm:bankreconciliation_*`
  CRUD (edit/delete pending/in_progress-only) + `_reconcile` (`@tenant_admin_required`; `recompute()` + batch flip).
- **Goal Setting (3.18):** `hrm:goalperiod_*` CRUD (delete pre-checks objectives — goal_period is PROTECT) + `_activate`/`_close`
  (POST, `@tenant_admin_required`; the only status-change path — `status` is off the form). `hrm:objective_*` CRUD +
  `objective_tree` (cascade view) + `objective_list?mine=1` (own + direct-reports). `hrm:keyresult_create` is nested
  (`/hrm/objectives/<objective_pk>/key-results/add/`, sets objective + equal-split weight) then `_detail/_edit/_delete`
  (all redirect back to the parent objective_detail). `hrm:goalcheckin_create` is nested
  (`/hrm/key-results/<keyresult_pk>/check-ins/add/`, sets key_result + created_by, advances current_value) + `_list`
  (org-wide) / `_detail` / `_delete` — **no `_edit`** (append-only history log).
- **Performance Review (3.19):** `hrm:reviewcycle_*` CRUD (delete pre-checks reviews — cycle is PROTECT) +
  `_advance_phase` (POST, `@tenant_admin_required`; one PHASE_ORDER step; status is off the form). `hrm:reviewtemplate_*`
  CRUD. `hrm:performancereview_*` CRUD (`_edit`/`_delete` gated by `_can_edit_review` = draft + reviewer/admin;
  `_detail` gated by `_can_view_review` = subject/reviewer/admin, 403 else; `_list` + roster filtered by
  `_visible_reviews_q`; `?mine=1`) + `_submit` (reviewer-or-admin) / `_share` (`@tenant_admin_required`) /
  `_acknowledge` (subject-only) / `_calibrate` (`@tenant_admin_required`, GET+POST, the only `calibrated_rating`
  writer). `hrm:reviewrating_create` is nested (`/hrm/reviews/<review_pk>/ratings/add/`, equal-split weight; all
  reviewrating mutation gated by `_can_edit_review`) + `_detail`/`_edit`/`_delete`. `hrm:calibration_board`
  (`/hrm/calibration/?cycle=`, `@tenant_admin_required`, report — manager reviews ranked by effective_rating).
- **Time Tracking (3.11):** `hrm:timesheet_submit/_approve/_reject/_cancel` (POST; approve `@tenant_admin_required`,
  recomputes + locks); inline entries `hrm:timesheetentry_add` (`/hrm/timesheets/<ts_pk>/entries/add/`, POST),
  `hrm:timesheetentry_edit` (`/hrm/timesheet-entries/<pk>/edit/`, GET+POST), `_delete` (POST) — all blocked once the
  timesheet is approved; `hrm:overtimerequest_submit/_approve/_reject/_cancel` (POST); report pages
  `hrm:timesheet_utilization_report` (`/hrm/reports/utilization/`) + `hrm:project_time_report`
  (`/hrm/reports/project-time/`), both GET with optional `?date_from`/`?date_to`.
- **Leave encashment workflow (3.10, all POST-only):** `hrm:leaveencashment_submit` (owner), `_approve`/`_reject`/
  `_mark_paid` (`@tenant_admin_required`; approve increments the allocation's `encashed_days`), `_cancel` (owner).
- **Leave Policy engine (3.10, no model):** `hrm:leave_policy` (`/hrm/leave-policy/`, GET — leave-type config +
  per-year allocation summary; `?year=` bounded 2000–2100) + POST `hrm:leave_accrual_run` / `hrm:leave_carryforward_run`
  (both `@tenant_admin_required`, atomic, idempotent; accrual sets allocated_days = accrued + carried_forward capped
  at max_balance, carry-forward rolls min(balance, max_carry_forward) into next year via the `carried_forward` field).
- **Attendance-regularization workflow extras (3.9, all POST-only):** `hrm:attendanceregularization_submit`
  (owner, draft→pending), `_approve`/`_reject` (`@tenant_admin_required`; approve rewrites the linked/created
  punch), `_cancel` (draft/pending→cancelled). Geofence delete is guarded when attendance rows reference it.
- **Onboarding workflow extras (all POST-only):** `onboardingprogram_activate/_generate_tasks/_complete/_cancel`
  (complete + cancel are `@tenant_admin_required`), `onboardingtask_complete/_reopen/_skip`,
  `onboardingdocument_mark_signed`, `assetallocation_issue/_return`,
  `orientationsession_mark_attended/_mark_missed`.
- **Offboarding (3.4) workflow extras (all POST-only):** `separationcase_submit` (`@login_required`),
  `separationcase_approve/_reject/_mark_cleared/_complete` (`@tenant_admin_required`), `separationcase_withdraw`
  (`@login_required`), `separationcase_relieving_letter/_experience_letter` (`@login_required`, render a print
  view + stamp generated_at); `exitinterview_complete/_skip` (`@tenant_admin_required`); `clearanceitem_mark_cleared/
  _mark_na/_reject` (all `@tenant_admin_required`); `finalsettlement_compute/_hr_approve/_finance_approve/_mark_paid`
  (all `@tenant_admin_required`). The two letter names are `hrm:separationcase_relieving_letter` /
  `hrm:separationcase_experience_letter`. Create pages honor `?case=<pk>` to pre-fill the parent case.
- **Offboarding letters landing page:** `hrm:offboarding_letters` (`/hrm/letters/`, `@login_required`,
  `offboarding_letters` view) — a standalone list of cases in `LETTER_READY_STATUSES` (cleared/settled/completed)
  with per-row relieving/experience letter buttons + a "generated on" indicator. This is what the **"Experience
  Letter" sidebar bullet** points at (the letters themselves are per-case print views, not records).
- **Job Requisition (3.5):** `jobrequisition_list/_create/_detail/_edit/_delete` (`/hrm/requisitions/`) and
  `jobdescriptiontemplate_list/_create/_detail/_edit/_delete` (`/hrm/job-templates/`). **Workflow extras (all
  POST-only, `@tenant_admin_required`):** `jobrequisition_submit/_approve_step/_reject/_return/_post/_hold/
  _mark_filled/_cancel`, `jobrequisition_apply_template`, `jobrequisition_clone`, and the inline approval-step
  actions `approval_add` (`/requisitions/<jr_pk>/approval/add/`) / `approval_delete`
  (`/requisition-approvals/<pk>/delete/`). **All JobRequisition + JobDescriptionTemplate writes (CRUD + workflow)
  are `@tenant_admin_required`** — list/detail reads are `@login_required`.
- **Candidate Management (3.6):** `candidate_list/_create/_detail/_edit/_delete` (`/hrm/candidates/`),
  `application_list/_create/_detail/_edit/_delete` (`/hrm/applications/`), `candidatetag_list/_create/_edit/_delete`
  (`/hrm/candidate-tags/`, **no detail**), `emailtemplate_list/_create/_detail/_edit/_delete`
  (`/hrm/candidate-email-templates/`), `communication_list/_detail` (`/hrm/candidate-communications/`, **read-only
  list+detail**, no create/edit/delete). **Candidate hub inline + status actions (POST):** `candidate_mark_hired`
  (`@login_required`), `candidate_blacklist`/`candidate_restore`/`candidate_delete` (**`@tenant_admin_required`**),
  `candidate_skill_add`/`candidate_skill_delete`, `candidate_tag_add`/`candidate_tag_remove`. **Application pipeline
  actions (POST, `@login_required`):** `application_advance_stage`/`application_reject`/`application_withdraw`/
  `application_hold`/`application_send_email`. **Email-template authoring is `@tenant_admin_required`**
  (`emailtemplate_create/_edit/_delete` — shared auto-firing templates). **Public portal (NO login):**
  `careers_list` (`/hrm/careers/`) + `careers_apply` (`/hrm/careers/<token>/apply/`). `application_create` honors
  `?candidate=`/`?requisition=` pre-select; the requisition hub links to `application_list?requisition=<pk>` and
  `application_create?requisition=<pk>`.
- **Interview Process (3.7):** `interview_list/_create/_detail/_edit/_delete` (`/hrm/interviews/`) and
  `interviewfeedback_list/_create/_detail/_edit/_delete` (`/hrm/interview-feedback/`). **Interview workflow extras
  (POST-only, `@login_required`):** `interview_confirm/_start/_complete/_cancel/_no_show/_reschedule`;
  `interview_panelist_add` + `interview_panelist_remove`/`interview_panelist_rsvp` (`/interviews/<pk>/panelists/
  <panelist_pk>/...`); `interview_send_invite`/`interview_send_reminder`/`interview_request_feedback`. **Scorecard
  extras:** `interviewfeedback_submit` (POST), `feedbackcriterion_add` + `feedbackcriterion_delete`
  (`/interview-feedback/<pk>/criteria/<criterion_pk>/delete/`). **`interview_delete` + `interviewfeedback_delete` are
  `@tenant_admin_required`** (security-review #2); all reads + scheduling/feedback writes are `@login_required`.
  `interview_create` honors `?application=<pk>`; `interviewfeedback_create` honors `?interview=<pk>` (the interview
  hub's "Add Scorecard" passes it). Edits redirect to the detail hub.
- **Offer Management (3.8):** `offer_list/_create/_detail/_edit/_delete` (`/hrm/offers/`),
  `backgroundverification_list/_create/_detail/_edit/_delete` (`/hrm/background-checks/`),
  `offerlettertemplate_list/_create/_detail/_edit/_delete` (`/hrm/offer-letter-templates/`). **Offer workflow extras
  (POST-only):** `offer_submit/_approve_step/_reject_step/_extend/_rescind/_expire` (`@tenant_admin_required`),
  `offer_accept/_decline/_send_email` (`@login_required`), `offer_letter_print` (`/hrm/offers/<pk>/letter/`, GET,
  standalone print page); inline approval steps `offerapproval_add` (`/offers/<pk>/approvals/add/`) /
  `offerapproval_delete` (`/offer-approvals/<pk>/delete/`) (both `@tenant_admin_required`). **Pre-boarding items
  (POST, inline on the offer hub):** `preboardingitem_add`/`_mark_submitted`/`_send_invite` (`@login_required`),
  `preboardingitem_verify`/`_reject`/`_delete` (`@tenant_admin_required`) at `/offers/<pk>/preboarding/add/` +
  `/preboarding-items/<pk>/...`. **Background-check lifecycle (POST):** `backgroundverification_initiate/_mark_status/
  _complete` (all `@tenant_admin_required`); `backgroundverification_edit` is blocked once completed;
  `backgroundverification_delete` + `offerlettertemplate_delete` are `@tenant_admin_required`. `offer_create` honors
  `?application=<pk>`; `backgroundverification_create` honors `?offer=<pk>`. Edits redirect to the detail hub.

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
  Onboarding adds: in-use template (has programs), issued asset, and active/completed program all block deletion.
- Attendance date-range filter parses GET dates with `_parse_iso_date` (malformed input ignored, no 500).
- **Onboarding (3.3):** `onboardingprogram_detail` is the hub — groups tasks by phase + embeds documents/assets/
  sessions with inline POST actions; computes `progress` from the already-fetched task list (no extra query).
  `onboardingprogram_list` annotates `tasks_total`/`tasks_done` (`Count(distinct=True)`) for the progress column.
  Workflow actions mirror the leave pattern (status guards + audit log); mark-signed rejects `not_required`,
  attendance actions reject `cancelled`. Task generation lives in **`apps/hrm/services.py`** (not views) so the
  seeder/tests can import it without the view layer.
- **Offboarding (3.4):** `separationcase_detail` is the hub — embeds the clearance checklist (progress bar +
  inline mark-cleared/na/reject), the exit-interview summary, and the F&F settlement summary, with conditional
  workflow buttons by status; `all_mandatory_cleared` + clearance progress are computed from the already-fetched
  clearance list (no extra query). The four create views go through `_offboarding_create` (a `crud_create` variant
  that pre-fills `?case=` and redirects to the parent case hub with the new pk). The two letter views
  (`_generate_letter`) gate on `LETTER_READY_STATUSES`, stamp generated_at/by once, then `render()` a standalone
  print template with `Content-Disposition: inline`. Delete/edit guards: only a `draft` case is deletable
  (else withdraw), only `draft`/`pending_approval` editable; clearance line editable/deletable only while
  `pending`/`in_progress`; settlement editable in `draft`/`computed`, deletable only in `draft`.
- **Job Requisition (3.5):** `jobrequisition_detail` is the hub — info/team/org/timeline+budget/JD cards + the
  inline **approval chain** (progress bar, per-row approve/remove, add-step form, a separate reject/return decision
  card), with conditional workflow buttons by status (`can_submit/_approve/_post/_hold/_fill/_cancel/_edit` context
  flags) and an `is_hr_admin` flag that gates **all** action UI (non-admins get a read-only hub). `approved_count`/
  `total_count`/`approval_progress`/`current_step` are computed from the already-fetched `approvals` list (the
  model's `approval_progress`/`current_approval_step` props would each re-query). `jobrequisition_create` is a
  custom view (not `crud_create`) so the "Save & Apply Template" button can copy the JD in one request. Edit guard:
  only `draft`/`rejected` editable; delete guard: only `draft`. `jobrequisition_submit` accepts `draft` **or**
  `rejected` (resets the prior chain on re-submit). `jobrequisition_approve_step` advances the lowest pending step
  and flips the req to `approved` when the last clears. `jobrequisition_clone` copies non-workflow fields via
  `_JR_CLONE_FK_FIELDS`/`_JR_CLONE_PLAIN_FIELDS` (status→draft, all `*_at` null).
- **Interview Process (3.7):** `interview_detail` is the hub — workflow action bar (status buttons + reschedule +
  send invite/reminder/request-feedback, all do_not_contact/terminal guarded), details, the inline **panel** table
  (add/remove/RSVP) and the **scorecards** table; lists carry `select_related("application__candidate",
  "application__requisition")` + a `Count("panelists")` annotation (explicit `.order_by()` after `.annotate()` —
  L9/UnorderedObjectListWarning). `_transition_interview(request, pk, new_status, msg)` is the shared status helper
  (terminal-guarded); `_interview_or_404` is the tenant-scoped fetch used by every action; `_send_interview_email`
  /`_interview_detail_lines` compose the candidate email; `_form_changes(form)` is the local audit-diff helper for
  the two custom edits. `interviewfeedback_detail` is the scorecard hub (inline criteria add/remove + submit);
  `interviewfeedback_list` annotates `Avg("criteria__rating")` + `Count("criteria")`. `interviewfeedback_submit`
  stamps is_submitted/submitted_at/submitted_by; create/edit never set them (is_submitted is off the form).
- **Offer Management (3.8):** `offer_detail` is the hub — a workflow action bar (submit/approve-step/reject-step/
  extend/accept/decline/rescind/expire/send-email, gated by status + admin), a compensation card, the inline
  **approval chain** (add-step form draft+admin, per-row remove), the **background-checks** list (+ Order Check),
  and the **pre-boarding** checklist (per-row submit/verify/reject/send-invite/delete + add-item form). `approved`/
  `all_approved`/`approval_progress` are computed from the already-fetched `approvals` list (the model props
  re-query). Status helpers mirror 3.5/3.7: `_offer_or_404` (select_related incl. `requisition__hiring_manager__party`
  for the letter merge), `_bgv_or_404`, `_preboarding_or_404`. `offer_submit` calls `generate_offer_approval_chain`
  then **resets the whole chain to pending** so a reject→resubmit re-approves from the top (the fix for the
  explorer's stuck-rejected-step bug). `offer_accept` drives `JobApplication.stage`→hired inside `transaction.atomic()`.
  `offer_letter_print` merges `OfferLetterTemplate.body_html` via `_apply_merge` (or a generated fallback body) and
  renders the standalone print page. `backgroundverification_detail` passes `transition_status_choices` (the
  `BGV_MANUAL_TRANSITION_STATUSES` subset) so the Update-Status dropdown never drifts from the view guard.

## Templates (`templates/hrm/<submodule>/<entity>/<page>.html`)
123 files, **one folder per sub-module, then one folder per entity, with a bare `list/detail/form.html` page
filename** (CLAUDE.md "Template Folder Structure"): `employee/` (3.1 — the main employee is single-entity so
`employee/list.html` etc.; its child entities get their own folders `employee/document/{list,detail,form}.html` and
`employee/lifecycle/{list,detail,form}.html` — the `budget/line/` child-entity precedent),
**`organization/` (3.2 — multi-entity: entity folders `designation/ jobgrade/ department/ costcenter/` each with
`list/detail/form.html`, plus the standalone derived pages `organization/org_chart.html` and
`organization/company_setup.html`)** — note 3.2 moved from the old flat `designation/` folder to `organization/`
when it became multi-entity, `onboarding/` (3.3 — entity folders `template/ templatetask/
program/` [the rich multi-section hub] `task/ document/` [`document/form.html` is multipart] `assetallocation/
orientationsession/`), **`offboarding/` (3.4 — entity folders `separationcase/` [the hub], `exitinterview/
clearanceitem/ finalsettlement/`, plus the standalone pages `offboarding/letters.html` [the letters landing list]
and the two print pages `offboarding/relieving_letter.html` / `offboarding/experience_letter.html` [which stay at
the sub-module level and do NOT extend base.html])**,
**`recruitment/` (3.5 — entity folders `jobrequisition/` [the hub] and `jobdescriptiontemplate/`, each with
`list/detail/form.html`; `RequisitionApproval` rows render inline on the requisition hub, no own templates)**,
**`candidates/` (3.6 — entity folders `candidate/` [the hub: inline skills/tags/applications/communications],
`application/` [the hub: pipeline actions + send-email], `tag/` [list+form, no detail], `emailtemplate/`,
`communication/` [list+detail only]; the reusable `candidates/_stage_badge.html` partial; the public standalone
pages `candidates/careers_list.html` + `candidates/careers_apply.html` which extend `base_auth.html` (not
`base.html`); `CandidateSkill` renders inline on the candidate hub, no own templates)**,
**`interview/` (3.7 — entity folders `interview/` [the hub: inline panel add/remove/RSVP + scorecards table + the
status/reschedule/invite-reminder action bar] and `interviewfeedback/` [the scorecard hub: inline criteria + submit],
each with `list/detail/form.html`; the reusable `interview/_status_badge.html` + `interview/_reco_badge.html`
partials; `InterviewPanelist` + `FeedbackCriterion` render inline on their parent hubs, no own templates. The detail
hub does `{% load safe_url %}` to render `meeting_url` through `|safe_external_url`)**,
**`offer/` (3.8 — entity folders `offer/` [the workflow hub: status action bar + inline approval chain +
background-checks list + pre-boarding checklist], `backgroundverification/` [list/detail with the initiate/
update-status/complete lifecycle], `offerlettertemplate/` [list/detail/form; the detail uses `{% verbatim %}` for
the merge-token reference], each with `list/detail/form.html`; the reusable `offer/_status_badge.html` partial; the
standalone printable `offer/offer_letter.html` [does NOT extend base.html; mirrors `relieving_letter.html`];
`OfferApproval` + `PreboardingItem` render inline on the offer hub, no own templates)**,
`attendance/` (3.9 — `shift/ shiftassignment/ record/ geofence/ regularization/`), `leave/` (3.10 — `type/ allocation/ request/ encashment/` + the standalone engine page `leave/policy.html`), `timetracking/` (3.11 — `timesheet/ timesheetentry/ overtimerequest/` + standalone `utilization_report.html`/`project_time_report.html`),
`holiday/` (3.12 — `publicholiday/ holidaypolicy/ floatingholidayelection/`),
`salary/` (3.13 — `paycomponent/ salarystructuretemplate/ [+ inline line managed on its detail + a standalone line_form.html] employeesalarystructure/`),
`payroll/` (3.14 — `payrollcycle/ payslip/`; the cycle detail is the workflow hub, the payslip detail shows the breakdown + hold/release),
`statutory/` (3.15 — `statutoryconfig/ statutorystaterule/ employeestatutoryidentifier/ statutoryreturn/` + the standalone `compliance_calendar.html` at the `statutory/` root; the return detail is the generate/file/pay workflow hub; the identifier list+detail render **masked** UAN/PF/ESI),
`tax/` (3.16 — `taxregimeconfig/` [+ inline slab bands, `band_form.html`], `investmentdeclaration/` [+ inline lines, `line_form.html`; detail = submit/lock hub + section-lines + proofs tables], `investmentproof/` [detail = verify/reject/on_hold hub; `form.html` = multipart upload], `taxcomputation/` [detail = old-vs-new breakdown + generate/link-form16 actions] + the standalone `regime_comparison.html` and `form16_partb.html` at the `tax/` root; form16_partb renders the PAN **masked**),
`payout/` (3.17 — `payoutbatch/` [detail = generate/approve/disburse hub + payments table with per-row mark-paid/failed/retry inline forms + reconciliations list], `payslipdistribution/` [list = bulk send-a-cycle form; detail = send/view/download], `bankreconciliation/` [detail = reconcile hub + exception rows] + the standalone `payment_register.html` and `exceptions.html` at the `payout/` root; only **masked** bank last-4 rendered anywhere). `performance/` (3.18 — `goalperiod/` {list/detail [activate/close workflow + objectives table]/form}, `objective/` {list [All/My-team `{% querystring %}` toggle + 6 filters]/detail [KR table + inline add + child-objectives + recent check-ins]/form/`tree.html`+`_tree_node.html` [recursive alignment cascade]}, `keyresult/` {detail [check-in history + inline log form]/form}, `goalcheckin/` {list/detail/form — no edit}; progress via `.progress-bar` width, health via `badge-green/amber/red` + `health_status_display` label, `.tree-node`/`.tree-children` classes in theme.css). The **same `performance/` folder** also holds 3.19 (Performance Review): `reviewcycle/` {list/detail [phase-progress stat cards + advance-phase workflow + reviews roster]/form}, `reviewtemplate/` {list/detail/form}, `performancereview/` {list [About/By-Me toggle + 5 filters; Edit gated per-row]/detail [ratings table + inline add + role-based submit/share/acknowledge/calibrate workflow + private-notes block gated on `show_private` + goal-review section]/form/`calibrate.html`}, `reviewrating/` {detail/form} + the standalone `calibration_board.html` at the `performance/` root (cycle selector + effective-rating-ranked manager reviews). The landing `hrm_overview.html` stays at the `templates/hrm/` root (gained Active Objectives + Open Reviews stat cards). A view
renders e.g. `"hrm/onboarding/document/list.html"`, `"hrm/leave/request/list.html"`,
`"hrm/attendance/record/list.html"`. Extend `base.html`, use the design-system classes
(`page-header/card/table/badge/form-*/empty-state`), `partials/pagination.html`. Conventions: search `q` + filter
selects pre-filled from `request.GET`; FK filters compare `obj.pk|stringformat:"d"`; boolean filters use
`"True"/"False"`; badges use exact model choice values with `{{ obj.get_<field>_display }}` fallback; every list
has an Actions column (view/edit/delete-POST+csrf+confirm). **Never render raw `bank_account` — use
`masked_bank_account`.** `employee/form.html` (photo) and `offboarding/separationcase/form.html` (resignation
letter) are `multipart/form-data`. Right-align numeric cells with the `.text-right` utility.

## Forms (`apps/hrm/forms.py`)
`TenantModelForm` subclasses (auto tenant-scope FK querysets, theme widgets). Exclude `tenant`, auto `number`, and
computed fields. **SECURITY: `LeaveRequestForm` excludes `status` and `approver`** (set only by workflow actions —
prevents self-approval via crafted POST). `EmployeeProfileForm` scopes `party` to person Parties and validates the
photo (`clean_photo`: jpg/jpeg/png/webp/gif allowlist + 5 MB cap). **Onboarding form security:**
`OnboardingDocumentForm` excludes `esign_status`/`signed_at` (workflow-derived); `clean_file` allowlists
pdf/doc/docx/jpg/png + 10 MB. `OrientationSessionForm` excludes `attendance_status`. `AssetAllocationForm` excludes
`issued_at`/`issued_by`/`returned_at`. `OnboardingProgramForm.clean()` blocks a 2nd program per employee + a
self-buddy. (All "advance the state" fields are owned by the audited workflow actions, never form-set.)
**Offboarding form security (3.4):** `SeparationCaseForm` excludes status/submitted_at/approver/approved_at/
rejection_reason/withdrawal_reason/expected_last_working_day/both letter stamps; `clean_resignation_letter`
allowlists pdf/doc/docx/jpg/png + 10 MB. `ExitInterviewForm` excludes status/conducted_at + 1:1-per-case guard.
`ClearanceItemForm` excludes status/cleared_by/cleared_at and scopes `asset_allocation` to `status="issued"`.
`FinalSettlementForm` excludes status/hr+finance approval stamps/paid_at/gl_posted + 1:1-per-case guard
(also DB `unique_together`).
**Employee-records form security (3.1):** `EmployeeProfileForm` now carries the 15 personnel-file fields
(marital_status/work_email/work_location/notice_period_days/national_id(+type)/passport_number(+expiry)/father+
spouse_name/current+permanent_address/emergency_contact_2_*) + `confirmed_on`. `EmployeeDocumentForm` excludes
`verification_status`/`verified_by`/`verified_at` (workflow-owned) and `clean_file` allowlists pdf/doc/docx/jpg/png
+ 10 MB. `EmployeeLifecycleEventForm` excludes `initiated_by` and scopes all FK querysets (employee/managers/
designations/departments) to the tenant.
**Job-requisition form security (3.5):** `JobRequisitionForm` excludes `status`/`submitted_at`/`approved_at`/
`posted_at`/`filled_at` (workflow-owned) + scopes designation/job_grade/template/department/cost_center/
hiring_manager/recruiter querysets to the tenant; `clean()` validates salary_min≤max and headcount≥1.
`RequisitionApprovalForm` excludes `status`/`decided_at`/`decided_by` and scopes `approver` to **tenant users**
(`get_user_model().filter(tenant=…)`). `JobDescriptionTemplateForm` scopes `designation` to active tenant rows.
**Candidate-management form security (3.6):** `CandidateProfileForm` excludes `party`/`status`/`gdpr_consent_date`/
`tags` (set in the view / managed via inline actions), `clean_email` enforces (tenant,email) uniqueness as a
friendly error, `clean_resume_file` (pdf/doc/docx + 10 MB via the shared `_validate_resume`), `clean_photo` (img + 5
MB). `JobApplicationForm` excludes `stage`/`stage_changed_at`/`hired_on`/`rejection_*`/`screening_answers`
(workflow-owned) + explicitly scopes candidate/requisition/referred_by querysets to the tenant; `clean_rating` 1–5.
`CandidateTagForm.clean_color` enforces strict hex (`#RRGGBB`) — defense-in-depth since the value is interpolated
into a CSS `style=` attribute. `CandidateEmailTemplateForm` = name/template_type/subject/body_html/is_active/
is_auto_send. `PublicApplicationForm` is a plain `forms.Form` (no model binding — no mass-assignment surface),
resume required, `gdpr_consent` required, `clean_resume_file` allowlist.
**Interview-process form security (3.7):** `InterviewForm` excludes `status`/`scheduled_by`/`reminder_sent_at`/
`feedback_reminder_sent_at` (workflow-owned) and scopes the `application` dropdown to the tenant (select_related
candidate+requisition to kill the `__str__` N+1); `scheduled_at` gets the round-tripping `datetime-local` widget.
`InterviewPanelistForm` excludes `interview`/`rsvp_status`/`notified_at` and scopes `interviewer` to active tenant
users. `InterviewFeedbackForm` excludes `is_submitted`/`submitted_by`/`submitted_at` (submission is the action-only
workflow — a form checkbox could un-submit), scopes `panelist` to the selected interview's panel (edit instance, or
the `?interview=` initial / bound data on create, isdigit-guarded), and `clean()` rejects a panelist that is not on
the selected interview (the DB `(interview,panelist)` unique is the backstop). `FeedbackCriterionForm` = criterion_
name/rating/notes with a `NumberInput(min=1,max=5)` widget + `clean_rating` 1–5.
**Offer-management form security (3.8):** `OfferForm` excludes `status` + all workflow stamps (extended_by/at,
accepted_at, declined_at, rescinded_at, created_by) + `number`; makes `currency` optional so the view defaults it
from the requisition; `clean()` rejects negative amounts; `clean_signed_document` allowlists pdf/doc/docx + 10 MB
via the shared `_validate_upload`. `OfferApprovalForm` excludes `status`/`decided_at`/`decided_by` and scopes
`approver` to tenant users (mirrors `RequisitionApprovalForm`). **`BackgroundVerificationForm` excludes `result`**
(set only by `backgroundverification_complete` — a form-editable verdict would bypass the consent→initiate→complete
gate) + `status`/lifecycle stamps; `clean_report_file` allowlists pdf/doc/docx + 10 MB. `PreboardingItemForm`
excludes the workflow stamps; `clean_uploaded_file` allowlists pdf/doc/docx/jpg/jpeg/png + 10 MB (ID-proof photos).
`OfferLetterTemplateForm` = name/is_active/body_html. The shared `_validate_upload(f, *, allowed_ext, max_bytes,
label)` helper backs all four upload guards (and `_validate_resume`).

## Seeder (`apps/hrm/management/commands/seed_hrm.py`)
`venv\Scripts\python.exe manage.py seed_hrm` (`--flush` to wipe+reseed). Idempotent (skips a tenant that already
has `EmployeeProfile` rows). Per tenant: 3 designations, up to 5 employees **reusing existing `core.Party`
persons** (tops up with unique names if too few), 4 leave types + allocations, 2 leave requests (1 approved/1
pending), **2 leave encashments** (1 pending / 1 draft on the encashable Annual type, rate = designation
min_salary/30), 6 holidays (2 optional/floating) + **2 holiday policies** (Company Default quota-2 + Full-Time Staff quota-1, each with an optional-holiday pool) + **2 floating-holiday elections** (1 approved w/ actor, 1 pending), 2 shifts + assignments, 5 attendance rows/employee (present punches tagged to the HQ
geofence — one outside/rest verified), **2 geofences** (HQ + client site) and **2 attendance regularizations**
(1 pending / 1 draft on the absent punches) per tenant. **Org structure (3.2)** is seeded by a
separate `_seed_org_structure(tenant)` (guarded by its own `JobGrade.exists()` check): 5 job grades (G1–M2), links
the seeded designations to grades + fills mid-salary/budgeted-headcount, creates 2 **cost-center `core.OrgUnit`
nodes** (core seeds none) with `CostCenterProfile`s (budget + owner), and a `DepartmentProfile` (code + head) over
each seeded department OrgUnit. **Onboarding** is seeded by a separate
`_seed_onboarding(tenant)` (guarded by its own `OnboardingTemplate.exists()` check, so an already-HRM-seeded tenant
still gets it): 2 templates (12 task lines), 2 programs (1 active/1 completed) with generated tasks, 6 documents,
6 assets, 2 orientation sessions per tenant. **Offboarding** is seeded by `_seed_offboarding(tenant)` (guarded by
its own `SeparationCase.exists()` check; the offboarding models are also in the `--flush` delete list): 2 separation
cases per tenant (1 completed + fully-cleared + paid settlement + completed exit interview; 1 in-clearance with the
HR line cleared), 12 clearance items, 1 exit interview, 1 settlement. **Employee records (3.1)** are seeded by
`_seed_employee_records(tenant)` (guarded by its own `EmployeeDocument.exists()` check; both models in the `--flush`
list): for the first 3 employees — 3 `EmployeeDocument`s each (national_id [verified], passport [pending, expires in
~180 days = expiring-soon], appointment_letter [verified]) + a `hire` (and `confirmation` if confirmed)
`EmployeeLifecycleEvent`. **Job requisitions (3.5)** are seeded by `_seed_job_requisition(tenant)` (guarded by its
own `JobRequisition.exists()` check; the 3 models self-flush): 2 `JobDescriptionTemplate`s + 3 `JobRequisition`s
across the lifecycle (1 posted, 1 draft, 1 approved with a fully-approved 2-step `RequisitionApproval` chain),
reusing the seeded designations/employees/department + cost-center OrgUnits. **Candidate Management (3.6)** is seeded
by `_seed_candidates(tenant)` (guarded by its own `CandidateProfile.exists()` check; the 3.6 models are in its own
`--flush` block — candidate Parties are deleted by id): mints `public_token` on posted requisitions (the seeder sets
`status="posted"` directly, bypassing the post action), then 3 talent-pool tags, 2 recruiting email templates (1
auto-send `application_received`, 1 manual `rejection`), 6 candidates (each a fresh `core.Party`+`PartyRole(role=
"candidate")`) with 2 skills each + tags on the first two, 8 `JobApplication`s spread across stages against the
seeded requisitions (`get_or_create` on (candidate,requisition)), and 2 `CandidateCommunication`s on the first app.
**Interview Process (3.7)** is seeded by `_seed_interviews(tenant)` (guarded by its own `Interview.exists()` check;
`--flush` cascades from `Interview`): adds 2 recruiting templates (`interview_invite` + `interview_reminder`), then 2
interviews on existing `JobApplication`s (a completed video round + an upcoming in-person round), 1–2 `InterviewPanelist`s
each from the tenant Users, and a submitted `InterviewFeedback` scorecard with 3 `FeedbackCriterion` lines on the
completed round; skipped (with a notice) if the tenant has no applications yet.
**Offer Management (3.8)** is seeded by `_seed_offers(tenant)` (guarded by its own `Offer.exists()` check; `--flush`
cascades from `Offer`): 1 `OfferLetterTemplate` ("Standard Offer Letter" with merge tokens), then 2 offers on
existing `JobApplication`s — one **accepted** end-to-end (2-step chain both approved via
`generate_offer_approval_chain`, a completed clear `BackgroundVerification`, and a `generate_preboarding_checklist`
with a mix of verified/submitted/pending items; drives its application → hired), and one **pending_approval** (first
step approved, second pending). Reuses the seeded applications/Users; skipped (with a notice) if the tenant has no
applications yet.
**Time Tracking (3.11)** is seeded by `_seed_timetracking(tenant)` (guarded by its own `Timesheet.exists()` check;
`--flush` cascades from `Timesheet`): per up-to-3 employees, 2 timesheets (last week **approved**, this week
**pending**) × 4 `TimesheetEntry` lines against a seeded `accounting.Project` where one exists (billable rows carry
the project + a 75.00 rate; non-billable rows have no project), totals via `refresh_totals()`; plus 1 **pending**
`OvertimeRequest` linked to an approved sheet. Skipped (with a notice) if the tenant has no employees.
**Salary Structure (3.13)** is seeded by `_seed_salary(tenant)` (own `PayComponent.exists()` guard; `--flush` deletes
children-first: EmployeeSalaryStructure → SalaryStructureLine → SalaryStructureTemplate → PayComponent, because
line→component is PROTECT): **8 pay components** (Basic/HRA/Special Allowance earnings, PF employee+employer + PT
statutory, LTA reimbursement w/ cap+requires_bill, Performance Bonus variable), **1** `SalaryStructureTemplate`
("Standard Staff — CTC", tied to the first JobGrade) with a **5-line fixed-amount breakdown** (derived
`computed_ctc_total` = 118,700 vs. a 120,000 target), and **1 active** `EmployeeSalaryStructure` for the first
employee. Reuses seeded JobGrade + EmployeeProfile; runs after `_seed_org_structure` (grades) + `_seed_tenant`
(employees) in `handle()`.
**Payroll Processing (3.14)** is seeded by `_seed_payroll(tenant)` (own `PayrollCycle.exists()` guard; children-first
flush PayslipLine→Payslip→PayrollCycle — AND these three are ALSO in the central `_seed_tenant` flush list before
`EmployeeProfile` because `Payslip.employee` is PROTECT): ensures the first **3 employees** have an active
`EmployeeSalaryStructure`, creates **1 regular** `PayrollCycle` for the current month (draft), **generates + recomputes
their payslips** (gross 9,291.67 each — employer PF excluded from net), and puts **1 payslip on hold**. Runs after
`_seed_salary` (needs the 3.13 structures).
**Statutory Compliance (3.15)** is seeded by `_seed_statutory(tenant)` (own `StatutoryConfig.exists()` guard;
children-first flush StatutoryReturn→EmployeeStatutoryIdentifier→StatutoryStateRule→StatutoryConfig — also in the
central `_seed_tenant` flush before `EmployeeProfile`): creates **1 `StatutoryConfig`**, **3 Maharashtra
`StatutoryStateRule`s** (2 PT slabs + 1 half-yearly LWF), an `EmployeeStatutoryIdentifier` **per employee**, and
**generates 1 PF `StatutoryReturn`** (`SCR-00001`) over the 3.14 cycle (employer ≈ 1,800 across 3 heads). Runs
**after** `_seed_payroll` (needs its PayslipLine rows).
**Tax & Investment (3.16)** is seeded by `_seed_tax(tenant)` (own `TaxRegimeConfig.exists()` guard; children-first
flush TaxComputation→InvestmentProof→InvestmentDeclarationLine→InvestmentDeclaration→TaxSlabBand→TaxRegimeConfig —
also in the central `_seed_tenant` flush before `EmployeeProfile`): creates **2 FY-2025-26 `TaxRegimeConfig`s**
(new + old, **11 `TaxSlabBand`s**), an old-regime **`InvestmentDeclaration`** (mid-year joiner, previous_employer_income
800k) + **80C/HRA lines** + a **verified `InvestmentProof`**, and a generated + Form-16-linked **`TaxComputation`**
(`TXC-00001`, hand-verified **52520 old / 0 new** via 87A). Runs **after** `_seed_statutory` (Form 16 links its
`StatutoryReturn(tds_form16)`; TDS-YTD needs PayslipLine rows).
**Payout & Reports (3.17)** is seeded by `_seed_payout(tenant)` (own `PayoutBatch.exists()` guard; children-first
flush BankReconciliation→PayoutPayment→PayoutBatch→PayslipDistribution — also in the central `_seed_tenant` flush
before `Payslip`/`PayrollCycle`): **locks the seeded `PayrollCycle`** (a batch needs a locked cycle; a real lock also
creates the accounting.PayrollRun — the seeder just flips status), generates a **`PayoutBatch`** (`POB-00001`) with
**3 payments (1 paid / 1 failed / 1 on-hold → partially_disbursed)**, a **`PayslipDistribution` per payslip** (the
paid one sent), and a **`BankReconciliation`** (`BRC-00001` → discrepancy, 1 matched / 2 unmatched). Runs **after**
`_seed_tax`.
**Goal Setting (3.18)** is seeded by `_seed_goals(tenant)` (own `GoalPeriod.exists()` guard; children-first flush
GoalCheckIn→KeyResult→Objective→GoalPeriod — **also in the central `_seed_tenant` flush before `EmployeeProfile`**,
since `Objective.owner` is PROTECT): an **active + a closed `GoalPeriod`**, a **3-level Objective cascade**
(1 company → 2 department → 2 individual, reusing seeded `EmployeeProfile` owners + a `core.OrgUnit` department),
**10 `KeyResult`s** with mixed metric_types/weights tuned to a **spread of health states** (on_track/at_risk/off_track),
and **19 staggered `GoalCheckIn`s** (the latest per KR reports the KR's intended `current_value` so `save()` stays
consistent). Runs **after** `_seed_payout`.
**Performance Review (3.19)** is seeded by `_seed_reviews(tenant)` (own `ReviewCycle.exists()` guard; children-first
flush ReviewRating→PerformanceReview→ReviewCycle→ReviewTemplate — **also in the central `_seed_tenant` flush before
`EmployeeProfile`**, since PerformanceReview.subject/reviewer are PROTECT): 1 mid-phase `ReviewCycle` linked to the
3.18 active `GoalPeriod`, 3 `ReviewTemplate`s (self/manager/peer), and **4 `PerformanceReview`s** across
self(submitted)/manager(shared, manager_rating snapshot)/manager(acknowledged + `calibrated_rating` ≠ overall)/peer
(anonymous submitted) — resolving the manager via the derived `.manager` — with **12 `ReviewRating` lines** (spread
values so the derived `overall_rating` + the calibrated-override case both show). Runs **after** `_seed_goals`.
Login as `admin_acme` / `admin_globex` (password `password`); superuser `admin` has no
tenant and sees nothing.

## Sidebar wiring (`apps/core/navigation.py` `LIVE_LINKS`)
- 3.1 (all 5 bullets live): Employee Directory/Profile/Employment Details → `hrm:employee_list`; Document Management
  → `hrm:employee_document_list`; Employee Lifecycle → `hrm:employee_lifecycle_list`; + HRM Overview →
  `hrm:hrm_overview`.
- 3.2 (all 5 bullets live): Company Setup → `hrm:company_setup`; Department Management → `hrm:department_list`;
  Designation/Job Titles → `hrm:designation_list`; Organization Chart → `hrm:org_chart`; Cost Centers →
  `hrm:costcenter_list`; + extra Job Grades → `hrm:jobgrade_list`.
- 3.3: Onboarding Tasks + Welcome Kit → `hrm:onboardingprogram_list`; Document Collection →
  `hrm:onboardingdocument_list`; Asset Allocation → `hrm:assetallocation_list`; Orientation Schedule →
  `hrm:orientationsession_list`; + extras Onboarding Templates → `hrm:onboardingtemplate_list`, Template Tasks →
  `hrm:onboardingtemplatetask_list`.
- 3.4: Resignation Management → `hrm:separationcase_list`; Exit Interview → `hrm:exitinterview_list`; Clearance
  Process → `hrm:clearanceitem_list`; F&F Settlement → `hrm:finalsettlement_list`; Experience Letter →
  `hrm:offboarding_letters` (the letters landing page).
- 3.5 (all 5 bullets live): Job Posting / Budget Management / Requisition Tracking → `hrm:jobrequisition_list`;
  Approval Workflow → `hrm:jobrequisition_list?status=pending_approval` (filtered to the pending queue, suffix
  handled by `_safe_reverse`); Job Templates → `hrm:jobdescriptiontemplate_list`.
- 3.6 (all 5 bullets live): Application Portal → `hrm:application_list`; Resume Parser / Candidate Database /
  Resume Search → `hrm:candidate_list` (the one candidate DB — its filter bar covers name/skill/resume-text search,
  NLP parsing deferred — so the three co-highlight there); Candidate Communication → `hrm:communication_list`; +
  extras Email Templates → `hrm:emailtemplate_list`, Talent Pool Tags → `hrm:candidatetag_list`, Public Careers
  Page → `hrm:careers_list`. The HRM overview adds 3 clickable recruiting stat cards (open reqs / active
  applications / new candidates); a posted requisition's detail hub shows its applications + the shareable apply URL.
- 3.7 (all 5 bullets live): Interview Scheduling / Interview Panel / Interview Reminders → `hrm:interview_list`
  (panel is managed on the interview detail; reminders are detail-page actions — these co-highlight there);
  Interview Feedback → `hrm:interviewfeedback_list` (the scorecards list); Video Interview →
  `hrm:interview_list?mode=video` (the video-mode filtered slice — most-specific match highlights it distinctly,
  suffix handled by `_safe_reverse`).
- 3.8 (all 5 bullets live): Offer Letter Generation → `hrm:offerlettertemplate_list` (the letter-template library);
  Offer Approval → `hrm:offer_list?status=pending_approval` (the pending-approval queue, suffix handled by
  `_safe_reverse`); Offer Tracking → `hrm:offer_list` (the all-status offer list); Background Verification →
  `hrm:backgroundverification_list`; Pre-boarding → `hrm:offer_list?status=accepted` (accepted offers = active
  pre-boarding, managed on the offer detail hub).
- 3.9: Check-in/Check-out + Attendance Calendar → `hrm:attendancerecord_list`; Attendance Regularization →
  `hrm:attendanceregularization_list`; Shift Management → `hrm:shift_list`; Geofencing → `hrm:geofence_list`;
  + Shift Assignments → `hrm:shiftassignment_list` (extra). All 5 NavERP.md 3.9 bullets are now live.
- 3.10: Leave Types → `hrm:leavetype_list`; Leave Policy → `hrm:leave_policy` (accrual/carry-forward engine);
  Leave Balance → `hrm:leaveallocation_list`; Leave Application + Leave Calendar → `hrm:leaverequest_list`;
  + Leave Encashment → `hrm:leaveencashment_list` (extra). All 5 NavERP.md 3.10 bullets are now live.
- 3.11: Timesheet + Project Time Tracking → `hrm:timesheet_list`; Billable Hours → `hrm:timesheet_utilization_report`;
  Overtime Tracking → `hrm:overtimerequest_list`; Timesheet Approval → `hrm:timesheet_list?status=pending`;
  + Project Time Report → `hrm:project_time_report` (extra). All 5 NavERP.md 3.11 bullets are now live.
- 3.12: Holiday Calendar → `hrm:publicholiday_list`; Floating Holidays → `hrm:floatingholidayelection_list`;
  Holiday Policies → `hrm:holidaypolicy_list`. All 3 NavERP.md 3.12 bullets are now live.
- 3.13: Pay Components → `hrm:paycomponent_list`; Salary Structure Templates → `hrm:salarystructuretemplate_list`;
  Variable Pay / Tax Components / Reimbursements → `hrm:paycomponent_list?component_type=variable|statutory_deduction|reimbursement`
  (one `PayComponent` catalog, `?query` deep-links so each bullet highlights on its filtered slice); + Employee Salary
  Structures → `hrm:employeesalarystructure_list` (extra). All 5 NavERP.md 3.13 bullets are now live.
- 3.14: Payroll Run → `hrm:payrollcycle_list`; Payroll Approval → `hrm:payrollcycle_list?status=pending_approval`;
  Salary Holds → `hrm:payslip_list?on_hold=True`; Arrears Calculation → `hrm:payslip_list` (arrears entered per
  payslip); Bonus Processing → `hrm:payrollcycle_list?cycle_type=bonus`. All 5 NavERP.md 3.14 bullets are now live.
- 3.15: PF/ESI/TDS Management → `hrm:statutoryreturn_list?scheme=pf|esi|tds_24q` (the challan/return register);
  PT/LWF Management → `hrm:statutorystaterule_list?scheme=pt|lwf` (the state-wise rule table IS their config
  surface); + Statutory Configuration → `hrm:statutoryconfig_detail`, Statutory Identifiers →
  `hrm:employeestatutoryidentifier_list`, Compliance Calendar → `hrm:statutory_compliance_calendar` (extras). All
  5 NavERP.md 3.15 bullets are now live.
- 3.16: Tax Regime → `hrm:taxregimeconfig_list`; Investment Declaration → `hrm:investmentdeclaration_list`;
  Investment Proof → `hrm:investmentproof_list?verification_status=pending`; Tax Computation + Form 16 Generation →
  `hrm:taxcomputation_list` (Form 16 has no standalone model — the computation detail links to the `form16_partb`
  report); + Regime Comparison → `hrm:tax_regime_comparison` (extra). All 5 NavERP.md 3.16 bullets are now live.
- 3.17: Bank Integration → `hrm:payoutbatch_list`; Payslip Generation → `hrm:payslipdistribution_list`; Payment
  Register → `hrm:payout_exceptions` (the batch detail links the per-batch `payment_register`); Reconciliation →
  `hrm:bankreconciliation_list`. All 4 NavERP.md 3.17 bullets are now live.
- 3.18: OKR/KPI Management → `hrm:objective_list`; Goal Alignment → `hrm:objective_tree`; Weight Assignment →
  `hrm:objective_list` (per-KR weight on objective_detail); Goal Timeline → `hrm:goalperiod_list`; Goal Tracking →
  `hrm:goalcheckin_list`. All 5 NavERP.md 3.18 bullets are now live.
- 3.19: Review Cycles → `hrm:reviewcycle_list`; Self-Assessment → `hrm:performancereview_list?review_type=self`;
  Manager Review → `hrm:performancereview_list?review_type=manager`; 360° Feedback → `hrm:performancereview_list`;
  Calibration → `hrm:calibration_board`. All 5 NavERP.md 3.19 bullets are now live.

## Conventions & gotchas
- An employee is `core.Party(kind=person)` + `core.Employment` + `hrm.EmployeeProfile` (1:1:1). Create the Party
  first; `EmployeeProfile.party` is required.
- `EmployeeProfile.department`/`manager` are read-only properties off the linked Employment — set them on the
  Employment, not the profile.
- `core.Employment` has a `(tenant, status)` index (added for `employee_list` status filtering).
- **3.2 companion-profile pattern:** `DepartmentProfile`/`CostCenterProfile` are 1:1 companions on `core.OrgUnit`
  (kind department/cost_center) — like `EmployeeProfile` extends `core.Party`. The OrgUnit owns name/parent/
  hierarchy; the profile adds HR fields HRM can't put on core (head/owner/budget/code). Create the OrgUnit in
  `core:orgunit_list` first, then enrich it here. The model `clean()` validates `org_unit.kind` and (defense-in-depth)
  tenant; the **real cross-tenant guard is the form FK queryset scoping** (tenant is set in the view after
  `form.is_valid()`, so the model's tenant check is skipped during form-create). The seeder must create the
  cost-center OrgUnit nodes itself — the core seeder makes only company + department units.
- **3.2 org chart is derived** (no model) from `core.Employment.manager` (single-parent reporting chain, cycle-
  guarded iterative DFS) + `core.OrgUnit.parent`; capped at 500 employees with a banner. Terminated employees are
  excluded. A matrix/multi-manager structure would need a join table (deferred).
- Sensitive fields (`bank_account`, `bank_routing`) are redacted from `AuditLog.changes` via
  `core.crud._SENSITIVE_AUDIT_FIELDS`; still plaintext at rest (documented WARNING — encrypt in a later pass).

## Common tasks
- **Add a field to a model:** edit `models.py` → add to the relevant `forms.py` `fields` (unless computed) → render
  in the entity's `detail.html`/`form.html` → `makemigrations hrm` + `migrate` → extend `seed_hrm` if useful → add a test.
- **Add a new model + CRUD:** model (inherit `TenantOwned`/`TenantNumbered`) → form → 5 views via `crud_*` helpers
  → 5 url names → admin → 3 templates → `LIVE_LINKS` entry → seeder → tests.
- **Add a workflow/status action** (mirror onboarding's activate/complete or leave submit/approve): write a
  `@login_required`/`@tenant_admin_required` + `@require_POST` view that fetches `get_object_or_404(Model, pk=pk,
  tenant=request.tenant)`, guards the source status, mutates with `save(update_fields=[...])`, calls
  `write_audit_log(request.user, obj, "update", {"action": "..."})`, redirects to the detail; add a POST-only url
  name; render a `{% csrf_token %}` form (conditional on status) in the detail/list; **exclude the
  workflow-advanced field from the ModelForm** so it's only settable via the action.
- **Add a filter:** pass the choice/queryset in the view's `extra_context`, add `(param, lookup, is_int)` to the
  `crud_list` `filters`, render the `<select>` pre-filled from `request.GET` (FK → `|stringformat:"d"`).
- **Extend the seeder:** add a block guarded by the existing `EmployeeProfile.exists()` check, `get_or_create` on a
  natural key; keep it idempotent and reuse core Parties.

## Deferred (later HRM passes — see `.claude/tasks/todo.md`)
**3.11 Time Tracking deferrals:** live/running start-stop timer; a real `Task`/WBS FK replacing free-text
`task_description` (blocked on Module 7 Project Management); auto-invoicing billable time (Accounting AR); feeding
approved hours into `accounting.JobCostEntry` as labor cost (needs a stable pay-rate from 3.13 Salary Structure);
full rate-card matrix (client×project×role — the entry-level `billable_rate` snapshot is the buildable-now slice);
profitability/margin reporting; OT payroll payout / comp-leave auto-credit to `LeaveAllocation` (`payout_method`
captures intent only); multi-jurisdiction OT compliance thresholds; `OvertimeRequestForm.timesheet` dropdown
dynamic-scoping to the selected employee (the model `clean()` catches a mismatch server-side today).
**3.12 Holiday Management deferrals:** bulk/country holiday import (CSV / "duplicate previous year"); weekend-observance
auto-shift; auto-reprocessing of overlapping `LeaveRequest`s when a holiday changes; holiday reminder emails;
iCal/Outlook/Google calendar sync + subscribable feeds; public/private visibility toggle + "Who's Out" widget;
SAP-style temporary/travel calendar override (the most-specific-match `HolidayPolicy.for_employee` resolution already
covers location differences without a per-trip object); controlled reason/occasion-code taxonomy for elections
(free-text `note` this pass); hard election-deadline/cutoff scheduler.
**3.13 Salary Structure deferrals:** the payroll RUN / calculation engine + payslip generation + GL posting (owned by
`accounting.PayrollRun` / 3.14 Payroll Processing per L29 — 3.13 only DEFINES the structures a run consumes); statutory
filing (PF ECR / ESI / Form 16/24Q); a full arbitrary formula engine referencing any component (v1 does fixed /
%-of-CTC, and `resolved_amount()` resolves ALL pct types off `annual_ctc_amount` since no separate stored basic/gross
subtotal exists yet — a true multi-base resolver is deferred); compensation-review / multi-level approval workflow
(v1 `EmployeeSalaryStructure.status` is just active/superseded); reimbursement claims/attachment tracking against
`annual_cap_amount` (captured as a `requires_bill`/cap flag only); per-run statutory threshold enforcement;
multi-currency (`currency` is a plain CharField — no `accounting.Currency` FK this pass); pay-group / `core.OrgUnit`-
scoped structures; and gating sensitive comp writes behind `@tenant_admin_required` (an app-wide authorization-policy
pass, not forked into 3.13 — see the security-reviewer note).
**3.14 Payroll Processing deferrals:** the **statutory compliance layer** (PF/ESI/PT/TDS/LWF config, state rules,
challans/returns) is now **built as 3.15 Statutory Compliance** (a separate sub-module — see its section above); 3.14
only computes generic `statutory_deduction`/employer-contribution lines from the components, which 3.15 aggregates.
Also: bank-file/NEFT disbursement generation;
payslip PDF/email + employee self-service download; a tax-slab TDS engine; off-cycle multi-country/multi-currency
payroll; YTD tax-projection reports; a configurable N-level approval-criteria engine (v1 is a fixed
submit→approve/reject two-step); automatic arrears diffing from salary-structure history (v1 takes a manual
`arrears_amount`); per-employee rollback inside a locked cycle (v1 = a new off_cycle cycle for corrections);
attendance/leave-linked LOP auto-wiring to 3.10; deduction-proration on attendance (v1 deductions resolve off the
component, not double-pro-rated); and an accounting-side "post directly from HRM" helper (posting stays in accounting).
**3.15 Statutory Compliance deferrals:** ECR (EPFO) / ESIC challan file-format generation + government-portal upload
(v1 stores the aggregated totals a later exporter needs); TRACES integration / unconsumed-challan matching; Form 16 /
Form 24Q PDF/XML rendering + email delivery; AI/rules pre-filing error detection (PAN/late-deduction flags); automatic
rate-change alerting (v1 supports supersede-not-edit via `is_active`/`effective_from` but has no notify engine); a
richer calendar-grid UI; multi-country/non-India schemes; Gratuity/Bonus Act compliance; and — the key one — a
**per-`PayslipLine` scheme tag** to replace the v1 `SCHEME_KEYWORDS` `component_name`-substring match in
`StatutoryReturn.recompute()` (a proper scheme FK/choice on `PayslipLine` would require a 3.14 model change, deferred
to avoid touching an already-shipped/tested model).
**3.16 Tax & Investment deferrals:** Form 16 / 16A / Part-A+B PDF rendering + merge + email (v1 `form16_partb.html`
is a data/report view only); TRACES portal integration (the government-issued Part A file/zip); Form 16A
(non-salary/vendor TDS — belongs to AP, not HRM); bulk Excel import of declarations (v1 is manual per-employee, incl.
HR-on-behalf); AI anomaly detection on declarations; automatic regime-lock tied to the first payroll run (v1 gates via
`InvestmentDeclaration.status`); a full instrument-level 80C sub-ledger (v1 collapses to one number per section);
non-India / multi-country tax regimes; exact Income Tax Act 2025 section-renumbering adoption (modeled defensively via
descriptive `section_code` + `TaxRegimeConfig.tax_law_reference`); a **`TaxSlabBand` gap/overlap validation** (v1
`clean()` only checks a single band's income_to≥income_from, not table contiguity — awkward with incremental inline
adds); and the shared `PayslipLine` scheme tag noted above (reused by `TaxComputation._tds_paid_ytd`'s TDS keyword match).
**3.17 Payout & Reports deferrals:** bank-specific file-format writers (the exact NEFT/NACH/ACH/WPS-SIF layouts — v1
stores the batch + payment rows a later exporter needs); live bank-API payment initiation (RazorpayX/Keka direct
integration — v1 status transitions are manual admin actions); bank-account prenote / multi-day verification; payslip
PDF rendering + secure/password-protected delivery (v1 `PayslipDistribution` tracks the send/view/download SIGNAL,
not the document); live bank-statement feed / auto-reconciliation (v1 matches manually against
`PayoutPayment.transaction_reference`); a dedicated `BankStatementLine` persistence model; period-over-period
payroll-cost anomaly detection; WPS/non-India mandatory formats; automatic retry scheduling (v1 is a manual
`retry_of`); and — the key one — a **`User`↔`EmployeeProfile` link** so `payslipdistribution_mark_viewed`/
`_mark_downloaded` can be scoped to the payslip's own employee (v1 is `@login_required`, documented SECURITY NOTE).
**3.1 employee-records deferrals:** lifecycle event → `core.Employment`/`EmployeeProfile` auto-sync (v1 records the
timeline only), document expiry email/push reminders (needs Celery/SMTP), normalized `EmployeeAddress` table (v1 is
free-text), OCR/AI document extraction + e-signature on personnel docs, `work_location` FK→`core.OrgUnit(branch)`.
**Two security items are deferred as project-wide patterns** (not 3.1-specific): (a) the employee **edit form** still
shows raw `national_id`/`passport_number`/`bank_*` to any `@login_required` member (same as the pre-existing
`bank_account` treatment — masking only protects the read-only detail render; gating the whole employee CRUD or
splitting a sensitive-fields sub-form behind `@tenant_admin_required` is a Module-0 decision); (b) uploaded
`EmployeeDocument` files are served via the dev `/media/` helper with no auth gate (same as onboarding docs/photos/
resignation letters — keep `MEDIA_ROOT` outside the web root in production, or add a protected `X-Accel-Redirect`
serve view project-wide).
**3.6 candidate-management deferrals:** resume NLP/AI field extraction (`resume_text` is captured now, parsing
deferred — needs Celery/SMTP), structured `CandidateEducation`/`CandidateExperience` child tables (v1 uses free-text
`skill_set` + inline `CandidateSkill`), a candidate self-service status portal (signed token link), CAPTCHA/honeypot
+ **per-IP rate-limiting on the public `careers_apply`/`careers_list`** (WARNING in code — django-ratelimit before
prod), GDPR auto-anonymization scheduled task (`gdpr_consent_expires` captured now), bulk SMS/WhatsApp send
(`CandidateCommunication.channel` supports it; only email actually sends), bulk-email-to-segment, a formal
`post_save` signal for auto-send templates (v1 fires inline in the stage-move actions), talent-rediscovery/AI
matching, side-by-side candidate comparison, and DEI/diversity analytics (`gender` captured now). Uploaded resumes/
cover-letters are served via the dev `/media/` helper with no `Content-Disposition: attachment` (project-wide
WARNING — extension-allowlist only, no content sniffing; harden before prod).
**3.7 interview-process deferrals:** live calendar (Google/Outlook) OAuth sync + ICS invites (`scheduled_at` is set
manually now), automatic Zoom/Teams/Meet meeting-link generation (`meeting_url` is pasted manually), a candidate
self-scheduling portal (EasyBook/Calendly-style slot picking), SMS/WhatsApp reminders (only candidate email + a
best-effort panel email actually send), one-way async video interview capture/playback (`mode="one_way_video"` is a
label only), AI scorecard summarization + AI video scoring, interviewer load-balancing/auto-assignment, a reusable
interview-kit / question-bank template catalog, strict queryset-level feedback **blinding** (the `is_submitted` flag
models the anti-anchoring intent but feedback isn't hidden from other panelists pre-submission), an admin-gated
scorecard edit window, and the **Celery beat task for timed reminder dispatch** (reminders/invites are manual
actions; `reminder_sent_at`/`feedback_reminder_sent_at` record the last manual send).
**3.8 offer-management deferrals:** live e-signature vendor wiring (DocuSign/Adobe Sign/Zoho Sign — `signed_document`
/`signature_status` are fields only, no send-for-signature/webhook/auto-attach), live background-check vendor APIs
(Checkr/HireRight/Sterling order + webhook status push-back — `BackgroundVerification` is a manually-advanced record;
the fields a webhook would write already exist), the formal **adverse-action / dispute compliance flow** for a
"Consider" result (pre-adverse notice → response window → final notice), **parallel** (all-at-once) approval routing
(the chain is sequential-by-`step_order`), a configurable **conditional-routing rule engine** (only a single
hardcoded `OFFER_APPROVAL_EXEC_THRESHOLD` constant adds the executive step today), a configurable
approval-notification field-picker, companion-document bundling (NDA/authorization sent alongside the offer),
offer **acceptance-rate / decline-reason analytics** (the `status`/`decline_reason` fields ship now; the dashboard
is a later analytics pass), template-usage scoping rules, and **scheduled/automated pre-boarding invite dispatch**
(Celery — invites/reminders are manual actions stamping `reminder_sent_at`). The pre-boarding→3.3 onboarding
hand-off on the join date is a TODO comment at the `offer_accept` trigger point (no forced `OnboardingProgram`
creation this pass). The three new uploads (`signed_document`/`report_file`/`uploaded_file`) are extension+size
validated but served via the dev `/media/` helper — keep `MEDIA_ROOT` outside the web root + `Content-Disposition:
attachment` in production (project-wide WARNING).
Salary structure + payroll/payslip (FK into `accounting.PayrollRun`, do NOT duplicate GL), plus
`JobRequisition` follow-ons (condition-based approval routing, approval delegation, re-approval on salary change,
external job-board posting, AI JD generation, internal career portal, `is_replacement_for`→`EmployeeProfile` FK
upgrade, evergreen auto-reopen), continuous feedback/PIP (3.20–3.21; 3.18 Goal Setting + 3.19 Performance Review are **built**),
timesheets (3.11, coordinate with `accounting.Project`),
statutory/tax (3.13–3.17), employee self-service portal, and a per-employee↔user link
for ownership-scoped leave actions (currently any tenant member can submit/cancel; approve/reject are admin-only).
**3.10 Leave Policy deferrals:** the accrual/carry-forward run engine is O(employees × leave-types) `get_or_create`
+ per-row `save()` (fine at demo scale, atomic + idempotent) — move to a prefetch-dict + `bulk_create`/`bulk_update`
(pre-assigning `LA-` numbers) or a background task before a tenant reaches ~hundreds of employees; auto-cancel/net
open (draft/pending) `LeaveEncashment` rows on separation so final settlement can't double-pay a still-open request.
**3.3 onboarding deferrals:** live e-sign API (DocuSign/HelloSign — `external_ref` is the stub), preboarding
before an `EmployeeProfile` exists (needs ATS 3.6–3.8), automated task reminders / calendar invites, IT
provisioning automation, AI 30-60-90-day plan generation, a new-hire self-service portal, and a real FK to the
Module 11 `assets.Asset` register (reserved on `AssetAllocation`). Onboarding session reschedule/cancel actions
aren't built — `OrientationSession.attendance_status` reschedule/cancel are reachable only via Django admin.
**3.4 offboarding deferrals:** live GL posting (`FinalSettlement.gl_posted` is a stub — defer to
`accounting.PayrollRun`), PDF/email letter delivery (v1 is an HTML browser-print view), a dynamic exit-interview
questionnaire builder (the 8 Likert fields are fixed), per-asset clearance auto-generation via signal (the IT line
links one issued asset), itemized FnF lines + statutory PF/ESI components, attrition analytics over
`ExitInterview.primary_reason`, a no-dues certificate, a `rehire_eligible` pool from `would_rejoin`, multi-level
approval chains, and per-department clearance roles (clearance resolution is currently `@tenant_admin_required`).
Private uploads (`resignation_letter`, onboarding docs, photos) are served via the dev `/media/` helper — keep
`MEDIA_ROOT` outside the web root in production (project-wide WARNING).
