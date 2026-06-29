---
name: hrm
description: Work on the HRM module (Module 3 — 3.1 employees, 3.2 designations/org structure, 3.3 employee onboarding, 3.4 employee offboarding, 3.5 job requisition, 3.6 candidate management (ATS: candidates/applications/talent-pool tags/recruiting email templates + a public career portal), 3.9 attendance/shifts, 3.10 leave management, 3.12 holidays). Use when the user asks to add/change/debug anything under apps/hrm or templates/hrm, extend the seed_hrm seeder, touch HRM sidebar wiring (LIVE_LINKS 3.1/3.2/3.3/3.4/3.5/3.6/3.9/3.10/3.12), or invokes /hrm.
---

# HRM — Human Resource Management (Module 3)

NavERP Module 3. App path: `apps/hrm/`, templates: `templates/hrm/`, URL prefix `/hrm/`
(`app_name = "hrm"`). Built sub-modules: **3.1 Employee Management, 3.2 Organizational Structure,
3.3 Employee Onboarding, 3.4 Employee Offboarding, 3.5 Job Requisition, 3.6 Candidate Management,
3.9 Attendance Management, 3.10 Leave Management, 3.12 Holiday Management.** Reuses the
unified core spine — an **employee is a `core.Party` (person) + `core.Employment`**; departments reuse
`core.OrgUnit`. Payroll GL posting stays with **`accounting.PayrollRun`** (HRM does not duplicate it).

## Overview
Tenant-scoped employee directory + leave + attendance for the demo tenants. Everything filters by
`request.tenant`. Derived figures (leave balance, leave days, attendance hours) are computed, never stored
editable. Recruiting/payroll/performance are deferred to later passes (see "Deferred").

## Models (`apps/hrm/models.py`) — 34 tables (12 core HRM + 7 onboarding + 4 offboarding + 2 employee-records + 3 job-requisition + 6 candidate-management)
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

## URLs / routes (`apps/hrm/urls.py`, `app_name="hrm"`)
- Landing: `hrm:hrm_overview` (`/hrm/`).
- Per model `<entity>` in {`designation`, **`jobgrade`, `department`, `costcenter`** (3.2), `employee`, `leavetype`,
  `leaveallocation`, `leaverequest`, `publicholiday`, `shift`, `shiftassignment`, `attendancerecord`,
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

## Templates (`templates/hrm/<submodule>/<entity>/<page>.html`)
104 files, **one folder per sub-module, then one folder per entity, with a bare `list/detail/form.html` page
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

## Seeder (`apps/hrm/management/commands/seed_hrm.py`)
`venv\Scripts\python.exe manage.py seed_hrm` (`--flush` to wipe+reseed). Idempotent (skips a tenant that already
has `EmployeeProfile` rows). Per tenant: 3 designations, up to 5 employees **reusing existing `core.Party`
persons** (tops up with unique names if too few), 4 leave types + allocations, 2 leave requests (1 approved/1
pending), 5 holidays, 2 shifts + assignments, 5 attendance rows/employee. **Org structure (3.2)** is seeded by a
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
Salary structure + payroll/payslip (FK into `accounting.PayrollRun`, do NOT duplicate GL), the rest of recruiting/
ATS — **3.7 Interview / 3.8 Offer (these FK into the built 3.5 `JobRequisition` / 3.6 `JobApplication`; the
`stage="interview"`/`"offer"` values are the 3.6→3.7/3.8 handoff)** — plus
`JobRequisition` follow-ons (condition-based approval routing, approval delegation, re-approval on salary change,
external job-board posting, AI JD generation, internal career portal, `is_replacement_for`→`EmployeeProfile` FK
upgrade, evergreen auto-reopen), performance/goals (3.18/3.19), timesheets (3.11, coordinate with `accounting.Project`),
statutory/tax (3.13–3.17), attendance regularization & geofencing, optional-holiday selection, leave
carry-forward/encashment batch, employee self-service portal, and a per-employee↔user link for ownership-scoped
leave actions (currently any tenant member can submit/cancel; approve/reject are admin-only).
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
