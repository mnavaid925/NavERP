# Research — Module 3.4: Employee Offboarding (hrm / offboarding)

## Products Surveyed

1. **SAP SuccessFactors Offboarding 2.0** — enterprise HCM, configurable event-driven offboarding
   programs; covers task assignment, exit interview (MDF custom objects), clearance workflow, DocuSign
   integration — https://community.sap.com/t5/human-capital-management-blogs-by-sap/offboarding-2-0/ba-p/13450241
2. **Workday HCM** — unified HR + Finance platform; termination types drive automatic offboarding
   workflows, exit surveys, final payment automation, identity de-provisioning
   — https://www.suretysystems.com/insights/tips-and-strategies-for-effective-workday-offboarding-processes/
3. **BambooHR** — SMB HRIS; offboarding checklists with task-category/assignee, resignation/termination
   document collection, exit interview scheduling, EOR-embedded offboarding
   — https://www.bamboohr.com/blog/how-to-crack-offboarding
4. **Zoho People** — mid-market HRMS; resignation/termination/deceased separation types; custom exit
   interview forms; IT/HR/Admin clearance forms; experience + relieving letter generation via mail-merge
   — https://help.zoho.com/portal/en/kb/people/administrator-guide/offboarding/articles/offboarding-in-zoho-people
5. **Darwinbox** — Indian enterprise HRMS; fully digital resignation → multi-dept clearance → FnF
   workflow; reduced FnF cycle from 62 days to 13.5 days via unified data; exit interviews integrated
   — https://darwinbox.com/blog/add-process-to-parting-exit-management
6. **Keka HR** — Indian SMB/mid-market; resignation/termination settings + exit reason categories;
   notice period as Day 1 of resignation; FnF includes leave encashment, notice buyout, gratuity,
   one-time payments; service certificate issued post-FnF
   — https://www.keka.com/full-and-final-settlement-policy
7. **greytHR** — Indian payroll-first HRMS; three-stage exit (Pre Clearance → Clearance → Post
   Clearance); notice period shortfall auto-calculated; FnF wizard (salary + leave + notice + deductions);
   relieving letter emailed on last working day; multi-level approval (1–3 levels); voluntary vs.
   involuntary paths
   — https://admin-help.greythr.com/admin/answers/123003054/
8. **Rippling** — US-focused unified HR/IT/Payroll; scheduled access revocation across all apps;
   resignation/layoff/termination/retirement types; final pay (PTO payout, prorated salary, COBRA);
   customizable exit survey; asset return tracking; device lock/wipe
   — https://www.rippling.com/blog/employee-exit-checklist
9. **Freshteam (Freshworks HRMS)** — SMB HRIS; resignation approval sequence (manager → HR Partner);
   standard notice period configuration with auto-termination on exit date; task/checklist assignment
   per department; automatic reminders for overdue offboarding tasks
   — https://support.freshteam.com/support/solutions/articles/19000104762-understanding-offboarding-in-freshteam/
10. **Gusto** — US SMB payroll + HR; dismissal payroll (termination-specific pay run); COBRA auto-
    notification; custom offboarding checklists (Plus/Premium); state-mandated separation notices;
    prorated final pay for salaried employees
    — https://support.gusto.com/article/230905104813447/View-and-complete-offboarding-checklists-for-admins

---

## Feature Catalog by Sub-Module

### 3.4.1 Resignation Management

- **Separation type taxonomy** — Distinguishes resignation (voluntary), termination (involuntary),
  layoff, retirement, contract-end, deceased. Seen in: Zoho People, Keka, greytHR, Rippling, Gusto.
  Priority: MUST. Spine: new field `separation_type` on `SeparationCase`. Buildable now.

- **Exit reason / reason code** — Configurable reason codes (better opportunity, compensation, work-life
  balance, relocation, personal, etc.) that feed attrition analytics. Seen in: Keka, Darwinbox,
  greytHR, SAP SuccessFactors. Priority: MUST. Spine: choices field on `SeparationCase`. Buildable now.

- **Resignation submission by employee** — Employee self-service: submits resignation with date,
  reason, and optional attachment (resignation letter file). Seen in: all 10 products.
  Priority: MUST. Spine: `SeparationCase` with `submitted_by` FK to `EmployeeProfile`, `submitted_at`,
  `resignation_letter` FileField. Buildable now.

- **Notice period tracking** — Configurable notice period (days) per employee/designation; system
  calculates expected Last Working Day (LWD) from resignation date + notice days; tracks served days
  vs. required; flags shortfall. Seen in: Keka (resignation date = Day 1), greytHR (shortfall auto-calc),
  Freshteam, Darwinbox, Zoho People. Priority: MUST. Spine: `notice_period_days`, `notice_start_date`,
  `expected_lwd`, `actual_lwd`, `notice_served_days` on `SeparationCase`. Buildable now.

- **Approval workflow (manager → HR)** — Multi-step approval: manager accepts/rejects resignation,
  then HR Partner confirms; optional withdrawal before approval; involuntary separations skip employee
  approval step. Seen in: greytHR (1–3 levels), Zoho People, Keka, Freshteam, SAP SuccessFactors.
  Priority: MUST. Spine: `status` state machine on `SeparationCase` (draft → pending_manager →
  pending_hr → approved → in_progress → completed); `manager_approved_by`, `hr_approved_by` FKs to
  User. Buildable now.

- **Resignation withdrawal** — Employee can retract before HR approval; HR can revoke acceptance post-
  approval. Seen in: greytHR, Keka. Priority: SHOULD. Spine: status transition + `withdrawal_reason`
  field. Buildable now.

- **Early exit / notice buyout** — Employee or employer can pay in lieu of notice (notice buyout
  amount = (basic/26) × unserved days); surfaces in FnF as a deduction or addition.
  Seen in: Keka, greytHR, Darwinbox. Priority: SHOULD. Spine: `notice_buyout_type` (pay_in_lieu /
  recover / none) on `SeparationCase`; buyout amount computed in `FinalSettlement`. Buildable now.

- **Knowledge transfer flag** — Boolean on the case triggering a KT task in the clearance checklist;
  owner set to manager. Seen in: SAP SuccessFactors, Workday, BambooHR. Priority: SHOULD. Spine:
  `requires_kt` boolean on `SeparationCase`. Buildable now.

---

### 3.4.2 Exit Interview

- **Exit interview record linked to separation case** — One exit interview per case; captures the
  interview date, interviewer (HR user), mode (in-person / virtual / self-service survey), and overall
  status. Seen in: SAP SuccessFactors (MDF object), Zoho People, Darwinbox, Keka, greytHR.
  Priority: MUST. Spine: new model `ExitInterview` FK to `SeparationCase`. Buildable now.

- **Structured questionnaire sections** — Questions organized into thematic areas: reason for leaving,
  manager & leadership satisfaction, team & culture, compensation & benefits, career growth, work
  environment, tools & processes, overall recommendation. Seen in: Zoho People (custom form builder),
  Workday (exit surveys), Rippling (customizable survey), SAP SuccessFactors.
  Priority: MUST. Spine: `ExitInterview` JSON field `responses` (keyed by section + question) or
  a flat `ExitInterviewResponse` line model. Buildable now (flat approach is simpler for v1).

- **Likert / rating scale responses** — Key questions rated 1–5 or 1–10 (e.g. manager effectiveness,
  overall satisfaction, would-recommend); free-text answers for open-ended questions.
  Seen in: Workday, Rippling, Personio, greytHR. Priority: MUST. Spine: integer rating fields +
  text fields on `ExitInterview` or response lines. Buildable now.

- **Primary reason for leaving (coded)** — Dropdown from a controlled list: better opportunity,
  compensation, career growth, relocation, health, retirement, personal, termination. Used for
  attrition analytics. Seen in: all 10 products. Priority: MUST. Spine: `primary_reason` choices
  field on `ExitInterview`. Buildable now.

- **Scheduling / interview date** — Date + time of scheduled interview; interviewer FK to User.
  Seen in: SAP SuccessFactors, Darwinbox, Zoho People. Priority: MUST. Spine: `scheduled_at`
  DateTimeField, `interviewer` FK to User on `ExitInterview`. Buildable now.

- **Feedback analytics / attrition trend** — Aggregate exit interview responses to surface top
  reasons for leaving; trends by department/period. Seen in: Darwinbox, Workday, Zoho Analytics.
  Priority: COULD (read-only list view with grouping is enough for v1). Spine: derived from
  `ExitInterview.primary_reason`. Buildable now (simple aggregation).

---

### 3.4.3 Clearance Process

- **Multi-department clearance checklist** — One `ClearanceItem` row per department/task; each row
  has an owner (HR, IT, Finance, Admin, Manager, or a named user), a status, and a due date.
  Standard departments: IT, HR, Finance, Admin, Manager (knowledge transfer). Custom departments
  possible. Seen in: Zoho People (IT/HR/Admin), greytHR, Darwinbox, SAP SuccessFactors, BambooHR,
  Keka. Priority: MUST. Spine: new model `ClearanceItem` FK to `SeparationCase`. Buildable now.

- **Asset return clearance linked to AssetAllocation** — Each issued asset (`hrm.AssetAllocation`)
  generates (or links to) a clearance line; marking the clearance item as cleared triggers
  `AssetAllocation.status → returned`. Do NOT create a separate asset table — reuse the existing
  `hrm.AssetAllocation` (which already has status=returned + return_due_date + returned_at).
  Seen in: SAP SuccessFactors, Darwinbox, Keka, greytHR, BambooHR, Rippling.
  Priority: MUST. Spine: optional `asset_allocation` FK on `ClearanceItem` pointing to
  `hrm.AssetAllocation`. Buildable now.

- **Clearance department choices** — Standard set: IT, Finance, HR, Admin, Manager, Library, Legal,
  Security, Custom. Configurable. Seen in: Zoho People, Keka, Darwinbox. Priority: MUST. Spine:
  `department` choices field on `ClearanceItem`. Buildable now.

- **Per-item approval** — Each clearance item approved (or flagged as not applicable) by its assigned
  owner; HR can see overall progress; FnF is gated on all mandatory items being cleared.
  Seen in: SAP SuccessFactors (clearance gates experience letter), Darwinbox, greytHR.
  Priority: MUST. Spine: `status` (pending/cleared/na/rejected) + `cleared_by` FK + `cleared_at`
  on `ClearanceItem`. Buildable now.

- **FnF release gated on clearance** — System blocks FnF settlement initiation until all mandatory
  clearance items are in a terminal state (cleared or na). Seen in: Darwinbox, greytHR, HROne.
  Priority: SHOULD. Spine: property `all_mandatory_cleared` on `SeparationCase`. Buildable now.

- **No-dues certificate generation** — Once all clearance items are cleared, system can produce a
  no-dues certificate. Seen in: greytHR, Darwinbox, Keka. Priority: COULD. Spine: action/print view
  on `SeparationCase`. Buildable now (template render, no new model needed).

---

### 3.4.4 F&F Settlement

- **Settlement record per separation case** — One `FinalSettlement` record per `SeparationCase`;
  captures all computed components, a status (draft/computed/approved/paid), and a payment date.
  Seen in: Keka, greytHR, Darwinbox, Zoho Payroll, HROne. Priority: MUST. Spine: new model
  `FinalSettlement` FK to `SeparationCase`. Buildable now.

- **Pro-rata salary component** — Salary earned for partial final month: (gross_salary / 26) ×
  days_worked. Stored as a decimal line item. Seen in: greytHR, Keka, Gusto, Darwinbox.
  Priority: MUST. Spine: `prorata_salary` DecimalField on `FinalSettlement`. Buildable now.

- **Leave encashment component** — Unused earned leave days × (basic salary / 30); sourced from
  `hrm.LeaveAllocation` balance (reuse the existing model; do not duplicate leave data).
  Seen in: Keka, greytHR, Darwinbox, Zoho Payroll. Priority: MUST. Spine: `leave_encashment_days`
  (pulled from LeaveAllocation) + `leave_encashment_amount` on `FinalSettlement`. Buildable now.

- **Notice period recovery / buyout** — If employee did not serve full notice: deduct shortfall
  days × (basic / 26); if employer waives notice: pay notice buyout amount. Toggle controlled by
  `SeparationCase.notice_buyout_type`. Seen in: Keka (notice buyout toggle), greytHR (shortfall
  auto-deduction). Priority: MUST. Spine: `notice_recovery_amount` (positive = deduction, negative
  = payout) on `FinalSettlement`. Buildable now.

- **Gratuity component** — Eligible when service >= 5 years: Last Drawn Salary × 15 × years / 26;
  stored as a component; displayed as zero with an "ineligible" note if < 5 years.
  Seen in: Keka, greytHR, Darwinbox, Zoho Payroll, HROne. Priority: MUST (India-primary ERP).
  Spine: `gratuity_amount`, `gratuity_eligible` on `FinalSettlement`. Buildable now.

- **Deduction items** — Outstanding loan recovery, damaged/unreturned asset cost, advance recovery,
  professional tax, TDS (income tax withholding). Seen in: Keka, greytHR, Zoho Payroll.
  Priority: MUST. Spine: `loan_recovery`, `asset_deduction`, `advance_recovery`, `tax_deduction`
  on `FinalSettlement`. Buildable now (flat approach for v1; itemized lines are COULD).

- **Bonus / incentive component** — Pending performance bonus or ex-gratia payable on exit.
  Seen in: greytHR, Keka, Darwinbox. Priority: SHOULD. Spine: `bonus_amount` on `FinalSettlement`.
  Buildable now.

- **Net payable computation** — net = prorata_salary + leave_encashment + gratuity + bonus
  + reimbursements − notice_recovery − loan_recovery − asset_deduction − advance_recovery
  − tax_deduction. Derived property (not stored), recomputed on save.
  Priority: MUST. Spine: `@property` / Python method on `FinalSettlement`. Buildable now.

- **FnF approval workflow** — Draft → Computed → HR Approved → Finance Approved → Paid; mirrors
  payroll approval chains. Seen in: Keka, Darwinbox, HROne. Priority: SHOULD. Spine: `status`
  choices on `FinalSettlement`. Buildable now.

- **Payroll/GL integration hook** — FnF settlement should eventually post to `accounting.PayrollRun`
  / `JournalEntry`. Do NOT duplicate GL logic in v1. Add a nullable `payroll_run_id` stub FK (to
  `accounting.PayrollRun` once that model exists) and a `gl_posted` BooleanField for future use.
  Seen in: HROne (auto-credits to payroll), Darwinbox, greytHR. Priority: COULD (stub only).
  Spine: deferred FK. Integration/later for live GL posting.

---

### 3.4.5 Experience Letter

- **Auto-generate relieving letter** — Printed/downloadable letter stating employee name, employment
  dates, designation, department, and confirmation that the employee has been relieved of duties.
  Generated as a Django HTML → PDF view from `SeparationCase` fields. Seen in: Zoho People (mail-merge),
  greytHR (emailed on last working day), Keka (service certificate), Darwinbox.
  Priority: MUST. Spine: action view on `SeparationCase`; no new model needed.
  Buildable now (HTML template + browser-print / wkhtmltopdf stub).

- **Auto-generate experience letter** — Similar to relieving but includes a positive-tenor description
  of the employee's role and contribution. Template-driven with variables from `EmployeeProfile` /
  `core.Employment`. Seen in: Zoho People, greytHR, Darwinbox, Keka.
  Priority: MUST. Spine: same action view, separate template. Buildable now.

- **Letter gated on clearance + FnF completion** — Experience letter generation is blocked until
  clearance is complete and FnF status is at least "approved". Seen in: SAP SuccessFactors
  (clearance gates letter), Darwinbox, greytHR. Priority: SHOULD. Spine: guard condition in
  the action view. Buildable now.

- **Letter tracking** — Record when relieving/experience letter was generated and by whom.
  Seen in: Zoho People (download + email log), greytHR. Priority: SHOULD. Spine: `letter_generated_at`,
  `letter_generated_by` fields on `SeparationCase`. Buildable now.

- **Custom letter templates** — HR configures organization letterhead, tone, and variables. Only
  possible with a full template engine; out of scope for v1 (admin can edit the Django template file).
  Seen in: Zoho People (Zoho Writer templates), Darwinbox. Priority: COULD. Integration/later.

---

## Recommended Build Scope — v1 (3–4 models, this sub-module pass only)

### Model 1: `SeparationCase` [SEP-]

The master offboarding record, one per departure event. Anchors all other 3.4 models.

**Key fields:**
```
employee          FK → hrm.EmployeeProfile  (not Party directly)
separation_type   choices: resignation | termination | layoff | retirement | contract_end | deceased
exit_reason       choices: better_opportunity | compensation | career_growth | relocation |
                            health | personal | retirement | performance | policy_violation | other
submitted_at      DateTimeField (nullable — filled on employee submission)
resignation_letter FileField (upload_to hrm/offboarding/letters/)
notice_period_days PositiveIntegerField (default from designation/company policy)
notice_start_date DateField (nullable)
expected_lwd      DateField (nullable — computed: notice_start_date + notice_period_days)
actual_lwd        DateField (nullable — HR-confirmed last working day)
notice_buyout_type choices: none | pay_in_lieu | recover
requires_kt       BooleanField default=True
status            choices: draft | pending_manager | pending_hr | approved | in_progress | completed | cancelled | withdrawn
manager_approved_by  FK → settings.AUTH_USER_MODEL (nullable)
manager_approved_at  DateTimeField (nullable)
hr_approved_by       FK → settings.AUTH_USER_MODEL (nullable)
hr_approved_at       DateTimeField (nullable)
withdrawal_reason    TextField (blank)
letter_generated_at  DateTimeField (nullable, editable=False)
letter_generated_by  FK → settings.AUTH_USER_MODEL (nullable, editable=False)
notes             TextField (blank)
```

**NUMBER_PREFIX:** `SEP`
**Status machine:** draft (employee self-service) → pending_manager (submitted) → pending_hr
(manager approved) → approved (HR approved) → in_progress (active separation, clearance running)
→ completed (FnF paid + letters issued) / cancelled (revoked before approved) / withdrawn.

---

### Model 2: `ExitInterview` [EI-]

One interview per `SeparationCase`. Captures scheduling, structured questionnaire responses, and
primary reason analytics.

**Key fields:**
```
case              FK → hrm.SeparationCase (related_name="exit_interviews")
interviewer       FK → settings.AUTH_USER_MODEL (nullable — HR user conducting interview)
scheduled_at      DateTimeField (nullable)
conducted_at      DateTimeField (nullable — set on completion)
mode              choices: in_person | virtual | self_service
status            choices: scheduled | completed | skipped
primary_reason    choices: better_opportunity | compensation | career_growth | relocation |
                            health | personal | retirement | performance | policy_violation | other
# Structured rating questions (1–5 Likert; null if skipped)
rating_role_clarity        SmallIntegerField (1–5, nullable)
rating_manager             SmallIntegerField (1–5, nullable)
rating_team                SmallIntegerField (1–5, nullable)
rating_compensation        SmallIntegerField (1–5, nullable)
rating_growth              SmallIntegerField (1–5, nullable)
rating_work_environment    SmallIntegerField (1–5, nullable)
rating_tools               SmallIntegerField (1–5, nullable)
rating_overall             SmallIntegerField (1–5, nullable)
would_rejoin               BooleanField (nullable)
would_recommend            BooleanField (nullable)
# Open-text sections
feedback_role       TextField (blank)
feedback_manager    TextField (blank)
feedback_company    TextField (blank)
suggestions         TextField (blank)
```

**Rationale:** Flat model (no dynamic question table) for v1 simplicity. The fixed sections match
the industry-standard categories found in Zoho People, Workday, and Rippling exit surveys.

---

### Model 3: `ClearanceItem`

One row per department/task for a separation case. Asset clearance lines link optionally to
`hrm.AssetAllocation` instead of duplicating asset data.

**Key fields:**
```
case              FK → hrm.SeparationCase (related_name="clearance_items")
department        choices: it | finance | hr | admin | manager | legal | security | library | custom
department_label  CharField (max_length=100, blank — used when department="custom")
description       CharField (max_length=255 — task description, e.g. "Return company laptop")
is_mandatory      BooleanField default=True
assigned_to       FK → settings.AUTH_USER_MODEL (nullable — the clearance owner)
due_date          DateField (nullable)
status            choices: pending | cleared | not_applicable | rejected
cleared_by        FK → settings.AUTH_USER_MODEL (nullable, editable=False)
cleared_at        DateTimeField (nullable, editable=False)
notes             TextField (blank)
asset_allocation  FK → hrm.AssetAllocation (nullable — for asset-return clearance lines;
                       on_delete=SET_NULL; reuses existing model, no duplication)
```

**Side-effect on mark-clear:** when `asset_allocation` is set and `status` transitions to `cleared`,
update `AssetAllocation.status → returned` and set `returned_at = now()` in the same transaction.
This reuses the existing `hrm.AssetAllocation` model rather than duplicating asset tracking.

---

### Model 4: `FinalSettlement` [FNF-]

One F&F settlement record per `SeparationCase`. All monetary components are stored as Decimal
fields; `net_payable` is a `@property` (derived, not stored). Leave encashment days are read from
`hrm.LeaveAllocation`; do NOT duplicate leave balance storage.

**Key fields:**
```
case                  FK → hrm.SeparationCase (related_name="final_settlements", unique=True)
settlement_date       DateField (nullable — target payment date)
# Payable components (all DecimalField max_digits=14, decimal_places=2, default=0)
prorata_salary        — earned salary for partial final month
leave_encashment_days DecimalField(5,2, default=0) — sourced from LeaveAllocation
leave_encashment_amount
gratuity_eligible     BooleanField (default=False — True if service >= 5 yrs)
gratuity_amount
bonus_amount          — pending performance bonus / ex-gratia
reimbursement_amount  — pending reimbursement claims
other_income          — any other taxable addition
# Deduction components
notice_recovery_amount — positive = deducted (unserved notice); negative = paid (buyout)
loan_recovery         — outstanding salary advances / loans
asset_deduction       — cost of unreturned/damaged assets
advance_recovery      — other advance recoveries
tax_deduction         — TDS / income tax withholding
professional_tax      — statutory professional tax
other_deduction
# Metadata
status            choices: draft | computed | hr_approved | finance_approved | paid | cancelled
hr_approved_by    FK → settings.AUTH_USER_MODEL (nullable)
hr_approved_at    DateTimeField (nullable)
paid_at           DateField (nullable)
notes             TextField (blank)
# GL integration stub (do NOT post to JournalEntry in v1 — deferred to accounting.PayrollRun)
gl_posted         BooleanField default=False
```

**`@property net_payable`:**
```
prorata_salary + leave_encashment_amount + gratuity_amount + bonus_amount
+ reimbursement_amount + other_income
- notice_recovery_amount - loan_recovery - asset_deduction
- advance_recovery - tax_deduction - professional_tax - other_deduction
```

**NUMBER_PREFIX:** `FNF`

---

## Experience Letter / Relieving Letter — Action View, No New Model

Both letters are rendered from an HTML template using data already on `SeparationCase` +
`EmployeeProfile` + `core.Employment`. No new model is needed. The view:
1. Guards: `case.status == 'completed'` and all mandatory clearance items cleared.
2. Renders `templates/hrm/offboarding/relieving_letter.html` or `experience_letter.html`.
3. Sets `Content-Disposition: inline` (browser-print) — wkhtmltopdf/WeasyPrint PDF generation
   is deferred.
4. On first render, stamps `case.letter_generated_at = now()` and `case.letter_generated_by`.

---

## Mapping to the Unified Core Spine

| Offboarding entity       | Spine relationship                                              |
|--------------------------|----------------------------------------------------------------|
| `SeparationCase.employee`| FK → `hrm.EmployeeProfile` (1:1 over `core.Party` + `core.Employment`) |
| Notice period LWD        | `core.Employment.status` set to `terminated` on `actual_lwd`  |
| Leave encashment days    | Read from `hrm.LeaveAllocation` (existing model, no duplication)|
| Asset return clearance   | `ClearanceItem.asset_allocation` → `hrm.AssetAllocation` (existing model) |
| FnF GL posting           | Stub only — future FK to `accounting.PayrollRun` / `JournalEntry` |
| Letters                  | Data from `EmployeeProfile` + `core.Employment` (party.name, designation, department, hired_on) |

---

## Deferred (later passes / integrations)

- **Live GL journal posting** — FnF amounts posted as `JournalEntry`/`JournalLine` debit/credit;
  deferred until `accounting.PayrollRun` model is built. Stub (`gl_posted` flag) is in v1.
- **Dynamic questionnaire builder** — Admin-configurable exit interview questions (vs. fixed fields);
  requires a `Question`/`QuestionResponse` normalized model; too complex for a single sub-module pass.
- **Automated clearance generation from AssetAllocation** — On case creation, auto-create one
  `ClearanceItem` per `issued` AssetAllocation for that employee; deferred to a post-save signal.
- **PDF generation (wkhtmltopdf / WeasyPrint)** — Proper PDF binary for letters; v1 ships HTML
  print view; PDF library dependency deferred.
- **Custom letter templates** — Admin-editable letterhead/variable templates (like Zoho Writer);
  deferred until a template-engine admin exists.
- **Email dispatch of letters** — Auto-email relieving/experience letter to employee's personal
  email on case completion; deferred (requires email integration).
- **FnF itemized settlement lines** — Normalized `FnFLine` child model for granular line-by-line
  audit; v1 uses flat fields which cover the 80% case.
- **Statutory compliance line items** — EPF/PF withdrawal initiation, ESI settlement, ESOP vesting;
  require statutory integrations — deferred.
- **Attrition analytics dashboard** — Aggregated exit interview primary_reason trends by dept/period;
  deferred to Module 10 BI.
- **IT system de-provisioning integration** — Revoke AD/SSO/Google Workspace access automatically;
  Rippling/HROne-style; requires Module 13 integration hook.
- **Knowledge transfer task list** — Dedicated KT task sub-model (milestones, documents, successor);
  v1 only flags `requires_kt` on `SeparationCase` as a plain `ClearanceItem` line.
