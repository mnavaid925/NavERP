---
name: hrm
description: Work on the HRM module (Module 3 — 3.1 employees, 3.2 designations/org structure, 3.3 employee onboarding, 3.4 employee offboarding, 3.9 attendance/shifts, 3.10 leave management, 3.12 holidays). Use when the user asks to add/change/debug anything under apps/hrm or templates/hrm, extend the seed_hrm seeder, touch HRM sidebar wiring (LIVE_LINKS 3.1/3.2/3.3/3.4/3.9/3.10/3.12), or invokes /hrm.
---

# HRM — Human Resource Management (Module 3)

NavERP Module 3. App path: `apps/hrm/`, templates: `templates/hrm/`, URL prefix `/hrm/`
(`app_name = "hrm"`). Built sub-modules: **3.1 Employee Management, 3.2 Organizational Structure,
3.3 Employee Onboarding, 3.4 Employee Offboarding, 3.9 Attendance Management, 3.10 Leave Management,
3.12 Holiday Management.** Reuses the
unified core spine — an **employee is a `core.Party` (person) + `core.Employment`**; departments reuse
`core.OrgUnit`. Payroll GL posting stays with **`accounting.PayrollRun`** (HRM does not duplicate it).

## Overview
Tenant-scoped employee directory + leave + attendance for the demo tenants. Everything filters by
`request.tenant`. Derived figures (leave balance, leave days, attendance hours) are computed, never stored
editable. Recruiting/payroll/performance are deferred to later passes (see "Deferred").

## Models (`apps/hrm/models.py`) — 20 tables (9 core HRM + 7 onboarding + 4 offboarding)
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

## URLs / routes (`apps/hrm/urls.py`, `app_name="hrm"`)
- Landing: `hrm:hrm_overview` (`/hrm/`).
- Per model `<entity>` in {`designation`, `employee`, `leavetype`, `leaveallocation`, `leaverequest`,
  `publicholiday`, `shift`, `shiftassignment`, `attendancerecord`, **`onboardingtemplate`,
  `onboardingtemplatetask`, `onboardingprogram`, `onboardingtask`, `onboardingdocument`, `assetallocation`,
  `orientationsession`**, **`separationcase`, `exitinterview`, `clearanceitem`, `finalsettlement`**}:
  `<entity>_list/_create/_detail/_edit/_delete`.
- Leave workflow extras: `hrm:leaverequest_submit/_approve/_reject/_cancel` (all POST-only).
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

## Templates (`templates/hrm/<submodule>/<entity>/<page>.html`)
63 files, **one folder per sub-module, then one folder per entity, with a bare `list/detail/form.html` page
filename** (CLAUDE.md "Template Folder Structure"): `employee/` (3.1 — single-entity, so `employee/list.html` etc.),
`designation/` (3.2 — `designation/list.html`), `onboarding/` (3.3 — entity folders `template/ templatetask/
program/` [the rich multi-section hub] `task/ document/` [`document/form.html` is multipart] `assetallocation/
orientationsession/`), **`offboarding/` (3.4 — entity folders `separationcase/` [the hub], `exitinterview/
clearanceitem/ finalsettlement/`, plus the standalone pages `offboarding/letters.html` [the letters landing list]
and the two print pages `offboarding/relieving_letter.html` / `offboarding/experience_letter.html` [which stay at
the sub-module level and do NOT extend base.html])**,
`attendance/` (3.9 — `shift/ shiftassignment/ record/`), `leave/` (3.10 — `type/ allocation/ request/`),
`holiday/` (3.12 — `publicholiday/`). The landing `hrm_overview.html` stays at the `templates/hrm/` root. A view
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

## Seeder (`apps/hrm/management/commands/seed_hrm.py`)
`venv\Scripts\python.exe manage.py seed_hrm` (`--flush` to wipe+reseed). Idempotent (skips a tenant that already
has `EmployeeProfile` rows). Per tenant: 3 designations, up to 5 employees **reusing existing `core.Party`
persons** (tops up with unique names if too few), 4 leave types + allocations, 2 leave requests (1 approved/1
pending), 5 holidays, 2 shifts + assignments, 5 attendance rows/employee. **Onboarding** is seeded by a separate
`_seed_onboarding(tenant)` (guarded by its own `OnboardingTemplate.exists()` check, so an already-HRM-seeded tenant
still gets it): 2 templates (12 task lines), 2 programs (1 active/1 completed) with generated tasks, 6 documents,
6 assets, 2 orientation sessions per tenant. **Offboarding** is seeded by `_seed_offboarding(tenant)` (guarded by
its own `SeparationCase.exists()` check; the offboarding models are also in the `--flush` delete list): 2 separation
cases per tenant (1 completed + fully-cleared + paid settlement + completed exit interview; 1 in-clearance with the
HR line cleared), 12 clearance items, 1 exit interview, 1 settlement. Login as `admin_acme` / `admin_globex`
(password `password`); superuser `admin` has no tenant and sees nothing.

## Sidebar wiring (`apps/core/navigation.py` `LIVE_LINKS`)
- 3.1: Employee Directory/Profile/Employment Details → `hrm:employee_list`; + HRM Overview → `hrm:hrm_overview`.
- 3.2: Designation/Job Titles → `hrm:designation_list`; Department Management → `core:orgunit_list`.
- 3.3: Onboarding Tasks + Welcome Kit → `hrm:onboardingprogram_list`; Document Collection →
  `hrm:onboardingdocument_list`; Asset Allocation → `hrm:assetallocation_list`; Orientation Schedule →
  `hrm:orientationsession_list`; + extras Onboarding Templates → `hrm:onboardingtemplate_list`, Template Tasks →
  `hrm:onboardingtemplatetask_list`.
- 3.4: Resignation Management → `hrm:separationcase_list`; Exit Interview → `hrm:exitinterview_list`; Clearance
  Process → `hrm:clearanceitem_list`; F&F Settlement → `hrm:finalsettlement_list`; Experience Letter →
  `hrm:offboarding_letters` (the letters landing page).
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
Salary structure + payroll/payslip (FK into `accounting.PayrollRun`, do NOT duplicate GL), recruiting/ATS
(3.5–3.8), performance/goals (3.18/3.19), timesheets (3.11, coordinate with `accounting.Project`),
statutory/tax (3.13–3.17), attendance regularization & geofencing, optional-holiday selection, leave
carry-forward/encashment batch, employee self-service portal, and a per-employee↔user link for ownership-scoped
leave actions (currently any tenant member can submit/cancel; approve/reject are admin-only).
**3.3 onboarding deferrals:** live e-sign API (DocuSign/HelloSign — `external_ref` is the stub), preboarding
before an `EmployeeProfile` exists (needs ATS 3.5–3.8), automated task reminders / calendar invites, IT
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
