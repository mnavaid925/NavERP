# Research — Module 3.5: Job Requisition (hrm)

## Leaders surveyed

1. **Workday Recruiting** — enterprise HCM-integrated ATS; requisitions are auto-generated from headcount plans — https://systemratings.com/review/workday-recruiting-deep-dive-2025
2. **SAP SuccessFactors Recruiting** — enterprise recruiting suite with configurable route-map approvals and three system status tiers — https://help.sap.com/docs/successfactors-recruiting/setting-up-and-maintaining-sap-successfactors-recruiting/requisition-state-and-status
3. **Oracle Taleo / Recruiting Cloud** — legacy-enterprise ATS with Dynamic Approval Routing (DAR) and rich status lifecycle — https://docs.oracle.com/en/cloud/saas/taleo-enterprise/20b/otfru/requisitions.html
4. **Greenhouse** — mid-market structured-hiring ATS with configurable requisition approval chains and JD AI-bias checking — https://bestrecruitingtools.com/blog/greenhouse-ats-review-2026
5. **Lever** — modern ATS; requisitions hold headcount, backfill flag, compensation band; approval conditions tied to headcount/comp — https://help.lever.co/hc/en-us/articles/20087293597981
6. **iCIMS** — enterprise talent-platform; sequential multi-approver requisition workflow, minimum two approvers required — https://bestrecruitingtools.com/blog/icims-ats-review-enterprise-2026
7. **SmartRecruiters** — talent-acquisition platform with sequential, parallel, and per-job approval chains for both reqs and offers — https://community.sap.com/t5/human-capital-management-blog-posts-by-members/job-approval-in-smartrecruiters-overview-features-and-configuration-guide/ba-p/14349246
8. **Workable Hiring Plan** — SMB-to-mid-market ATS; most thoroughly documented req fields and status lifecycle (pending → approved → open → reserved → on hold → filled → cancelled) — https://help.workable.com/hc/en-us/articles/9470641768343
9. **BambooHR ATS** — HRIS-first platform; integrated req/approval as part of HRIS lifecycle with customizable workflow and fields — https://bestaihrsource.com/talent-acquisition/bamboohr-overview-features
10. **Zoho Recruit** — SMB ATS; requisition + approval route map, budget/timeline tracking, highly customizable fields — https://www.zoho.com/recruit/corporate-hr-software.html
11. **Ashby** — high-growth tech ATS; unlimited custom fields, conditional-logic approval workflows, formula fields — https://bestrecruitingtools.com/blog/ashby-ats-review-2026

---

## Feature catalog by sub-module 3.5

### 3.5.A — Job Posting (the requisition object itself)

- **Core requisition identity fields** — job title, requisition number (auto), department (FK to OrgUnit), work location (city/country/remote), employment type (full-time/part-time/contract/intern), headcount (number of openings), reason for hire (new headcount / backfill / replacement / contractor-to-perm) — seen in: Workable, Lever, Breezy HR, Oracle Taleo, Zoho Recruit, iCIMS — **priority: P0 (table-stakes)** · spine: department reuses `core.OrgUnit`; other fields are new columns on `JobRequisition` · buildable now

- **Hiring team fields** — hiring manager (FK to employee), recruiter assigned (FK to employee), secondary approvers/collaborators — seen in: Workable, Oracle Taleo, iCIMS, Greenhouse, SAP SuccessFactors — **priority: P0** · spine: reuses `hrm.EmployeeProfile` (never `core.Party` directly, per HRM pattern) · buildable now

- **Position context fields** — target start date, replacement for (nullable free-text or FK to departing employee), priority (high/medium/low/urgent) — seen in: Lever, Oracle Taleo, Workable, Breezy HR, SAP SuccessFactors — **priority: P1** · new columns on `JobRequisition` · buildable now

- **Designation and grade linkage** — link requisition to a `Designation` (which already carries min/mid/max salary band, requirements text, description) — this is the key NavERP differentiator: the `Designation` model already owns the job definition, so the requisition FK's in rather than duplicating — seen as: Workday "position-based requisition", SAP SuccessFactors "position management integration" — **priority: P0** · spine: reuses `hrm.Designation` + `hrm.JobGrade` · buildable now

- **Job description body on the req** — full JD text stored on the requisition (either hand-typed or auto-populated from a `JobDescriptionTemplate`); separate from `Designation.description` (which is the evergreen definition), this is the hiring-event-specific customized copy — seen in: Oracle Taleo, Greenhouse, SmartRecruiters, iCIMS — **priority: P1** · new `TextField` on `JobRequisition`; optionally seeded from a `JobDescriptionTemplate` · buildable now

- **Internal/external posting toggle** — flag whether the requisition is for an internal-only posting (career mobility), external-only, or both — seen in: Oracle Taleo, SAP SuccessFactors, SmartRecruiters — **priority: P1** · new `CharField` with choices on `JobRequisition` · buildable now

- **Evergreen/pipeline requisition type** — special type for continuous-intake roles (e.g. sales, support) that don't close when filled; headcount is "unlimited" — seen in: Workday, Oracle Taleo, Reach ATS — **priority: P2** · choice value on requisition `req_type` field · buildable now (just a choice)

- **Status lifecycle** — statuses: draft → submitted → pending_approval → approved → posted → on_hold → filled → cancelled; also `rejected` (back from approval) — synthesized from Workable (draft/pending/approved/open/reserved/on_hold/filled/cancelled), SAP SuccessFactors (pre-approved/approved/closed), Oracle Taleo (draft/to_be_approved/approved/posted/on_hold/filled/cancelled) — **priority: P0** · new `status` field on `JobRequisition` · buildable now

---

### 3.5.B — Approval Workflow

- **Sequential multi-level approval chain** — requisition must pass through multiple approver levels in order before it can be posted; each step must be completed before the next is notified — seen in: all 10 products; mandatory in Workable (no bypass), required minimum 2 approvers in iCIMS — **priority: P0** · new `RequisitionApproval` model (one row per approval step per requisition) · buildable now

- **Approval step fields** — step order, approver (FK to User), role label (hiring manager / HR / finance / executive), status per step (pending/approved/rejected/delegated), decision at timestamp, comments/reason — seen in: Oracle Taleo DAR, SmartRecruiters, Workable, Greenhouse — **priority: P0** · `RequisitionApproval` model fields · buildable now

- **Approve / reject / return-for-revision actions** — approver can approve (advances to next step), reject (terminates workflow, req goes to `rejected`), or return with comments (req goes back to `draft` for editing and resubmission) — seen in: SmartRecruiters (approve/reject/return), Workable (approve/reject), Oracle Taleo (approve/reject/terminate) — **priority: P0** · view-level POST actions on `RequisitionApproval` · buildable now

- **Approval audit trail** — immutable log of who decided what and when; `decided_at`, `decided_by`, `comments` on each `RequisitionApproval` row; combined with the status history pattern already used in HRM (SeparationCase, FinalSettlement) — seen in: Oracle Taleo (History tab), SmartRecruiters, Workable — **priority: P0** · captured naturally on `RequisitionApproval` rows (never deleted) · buildable now

- **Approval delegation** — approver can delegate to a colleague for absence coverage — seen in: SmartRecruiters, Workday — **priority: P2** · `delegated_to` nullable FK on `RequisitionApproval` · deferred (adds complexity, low MVP value)

- **Condition-based approval routing** — different approval chains triggered by headcount > N, salary > threshold, new headcount vs. backfill, department/location — seen in: Lever, Workable (custom per dept/location), Ashby (conditional logic), SmartRecruiters — **priority: P2** · configuration-table approach; deferred to a later workflow engine pass · integration/later

---

### 3.5.C — Budget Management

- **Salary range on the requisition** — min and max salary stored directly on the req (may differ from the `Designation` band — this is the specific-opening budget); currency field for multi-currency tenants — seen in: Lever (compensation band), Workable, Breezy HR, Zoho Recruit, SAP SuccessFactors — **priority: P0** · `salary_min` / `salary_max` / `salary_currency` on `JobRequisition` · buildable now

- **Annualized / loaded cost estimate** — total first-year cost including benefits loading (e.g. salary × 1.25); a single computed or manually entered figure used by finance in the approval — seen in: GoodTime/Teravexa examples ("annualized loaded cost: $312,000"), Deel guide — **priority: P1** · `estimated_annual_cost` DecimalField on `JobRequisition`; can be derived from salary_max × a loading factor but is better manually entered by the requester for accuracy · buildable now

- **Cost center assignment** — which cost center absorbs the headcount cost; FK to `core.OrgUnit(kind="cost_center")` (same spine used by `hrm.CostCenterProfile`) — seen in: Breezy HR ("cost center code"), Workday (finance integration), Deel guide, Oracle Taleo — **priority: P0** · FK to `core.OrgUnit` (limit_choices_to kind=cost_center) on `JobRequisition` · buildable now

- **Hiring budget vs. salary budget distinction** — some products track the one-time cost-to-hire (agency fees, job board spend, relocation) separately from the ongoing salary cost — seen in: Breezy HR ("budgetary impact summary covering salary, benefits, and tools"), Deel guide — **priority: P2** · `hiring_cost_budget` DecimalField on `JobRequisition` (optional field) · buildable now as an optional field

- **Re-approval on salary change** — if the salary range is edited after approval, the approval workflow restarts — seen in: Workable (explicit "requires re-approval" field-level config) — **priority: P2** · enforcement logic in save()/view; deferred to later hardening pass

---

### 3.5.D — Job Templates

- **Reusable job description templates** — a library of named templates keyed by designation/role, containing pre-filled JD body, responsibilities, requirements, and qualifications text; applying a template pre-populates the requisition's JD fields — seen in: Greenhouse, Workable, Reach ATS, SmartRecruiters, JazzHR — **priority: P1** · new `JobDescriptionTemplate` model · buildable now

- **Template-to-designation linkage** — a template is optionally associated with a `Designation` so the system auto-suggests the right template when a requisition is raised for that designation — seen in: Greenhouse (templates for recurring role types), Workday (position-based auto-population) — **priority: P1** · FK `designation` (nullable) on `JobDescriptionTemplate` · buildable now; mirrors the `OnboardingTemplate.designation` pattern already in the codebase

- **Template fields** — name, designation FK (optional), JD body (summary / responsibilities / requirements / qualifications / nice-to-haves as rich text fields or structured text), employment type default, is_active — seen in: Breezy HR field breakdown, Greenhouse — **priority: P1** · `JobDescriptionTemplate` model · buildable now

- **AI JD generation / bias checking** — AI generates or de-biases job description text — seen in: Greenhouse, BambooHR — **priority: P2** · integration/later (external AI API)

---

### 3.5.E — Requisition Tracking

- **Status history / timeline** — an immutable log of every status change on a requisition (who changed it, from what status, to what status, at what time, with a note) — seen in: Oracle Taleo (History tab), SAP SuccessFactors, Workable — **priority: P1** · can be captured via the existing `core.AuditLog` (generic) OR as a lightweight `requisition_status_log` field-set on `RequisitionApproval` rows; the latter is already implied by the approval step model; a separate status-history model is P2 · buildable now via approval rows + AuditLog

- **Requisition dashboard / list filters** — filter by status, department, hiring manager, priority, date range; search by title/number — seen in: all products — **priority: P0** · view-level filter logic (no new model needed) · buildable now

- **Target fill date / SLA tracking** — flag requisitions that are overdue against their target start date — seen in: Workable (overdue status with red indicator), Oracle Taleo — **priority: P1** · derived from `target_start_date` vs. `today` in a template property; no new field needed · buildable now

- **Headcount tracking** — the requisition tracks "openings count" vs. "hires made" so a req for 3 seats auto-closes when 3 candidates are hired (wired by 3.6 Candidate Management) — seen in: Workable (headcount field), Lever — **priority: P1** · `headcount` (int) field on `JobRequisition`; `hires_made` is a counter-field updated by 3.6; for this pass just store headcount · buildable now (hire linkage deferred to 3.6)

- **Requisition cloning / duplicate** — copy an existing approved/closed req to create a new one (reuses same JD, department, salary, etc.) — seen in: Oracle Taleo ("Duplicate" action), Workable — **priority: P2** · view-level POST action; no new model · buildable now as a view action

---

## Unified-core mapping

### What exists in `apps/hrm/models.py` today (verified)

| Existing model | Relevant fields for 3.5 |
|---|---|
| `hrm.EmployeeProfile` | `party`, `designation`, `employee_type`; used as hiring manager / recruiter FK target |
| `hrm.Designation` | `name`, `job_grade`, `department`, `description`, `requirements`, `min_salary`, `mid_salary`, `max_salary`, `budgeted_headcount`; the template for a role — requisition FKs here to inherit the role definition |
| `hrm.JobGrade` | `name`, `level_order`; linked to Designation; identifies seniority level on the req |
| `hrm.DepartmentProfile` | `org_unit`, `head`, `cost_center`; DepartmentProfile.head is the department head who may appear in an approval chain |
| `hrm.CostCenterProfile` | `org_unit`, `owner`, `budget_annual`; cost center that absorbs headcount cost |
| `TenantNumbered` abstract | `NUMBER_PREFIX`, `number`, retry-on-collision `save()` — reused by `JobRequisition` with prefix `JR` |

### What exists in `apps/core/models.py` today (verified)

| Core model | How 3.5 reuses it |
|---|---|
| `core.OrgUnit(kind="department")` | FK for `department` on `JobRequisition` |
| `core.OrgUnit(kind="cost_center")` | FK for `cost_center` on `JobRequisition` |
| `core.Employment` | Linked through `EmployeeProfile`; do NOT FK here directly |
| `core.AuditLog` | Generic audit trail (can capture req status changes) |
| `django.contrib.auth.User` | `approver` FK on `RequisitionApproval` steps |

### What 3.5 does NOT reuse / what is deferred

- **Candidate** (3.6), **Interview** (3.7), **Offer** (3.8) — these are separate later sub-modules. `JobRequisition` must be self-contained and FK only to models that exist today. The candidate-to-req link is added in 3.6 when the `Candidate` model arrives.
- **GL / JournalEntry** — no financial posting for a requisition; budget is informational only at this stage. The cost posts when payroll runs (Module 2 + HRM 3.13+).
- **`core.Item`** — not applicable to job requisitions.
- **`core.StockMove`** — not applicable.

---

## Recommended build scope for 3.5 (this pass — 3 models)

### Model 1: `JobRequisition` [JR-]

The hub record — the "authorization to hire" that all later stages (3.6 candidate, 3.7 interview, 3.8 offer) will FK into. Inherits `TenantNumbered` (NUMBER_PREFIX = "JR").

**Proposed fields (driven by P0/P1 features above):**

```python
# Identity
number              CharField(20, editable=False)           # JR-00001 — TenantNumbered
title               CharField(255)                          # specific job title for this opening
designation         FK(hrm.Designation, null=True)          # links to role definition / salary band
job_grade           FK(hrm.JobGrade, null=True)             # denormalized for quick filter

# Organization
department          FK(core.OrgUnit, kind=dept, null=True)  # inherits from Designation but overridable
cost_center         FK(core.OrgUnit, kind=cc, null=True)    # P&L owner
location            CharField(255, blank=True)              # office / city / remote

# Headcount & type
headcount           PositiveSmallIntegerField(default=1)    # number of openings
req_type            CharField choices: standard/backfill/replacement/evergreen
employment_type     CharField choices: full_time/part_time/contract/intern/consultant
reason_for_hire     CharField choices: new_headcount/backfill/replacement/project/contractor_to_perm
is_replacement_for  CharField(255, blank=True)              # name of departing employee (free text stub)

# Posting scope
posting_type        CharField choices: internal/external/both

# Hiring team
hiring_manager      FK(hrm.EmployeeProfile, null=True)      # reports-to for the new hire
recruiter           FK(hrm.EmployeeProfile, null=True)      # TA owner

# Timeline
target_start_date   DateField(null=True)
priority            CharField choices: low/medium/high/urgent

# Budget (P0/P1)
salary_min          DecimalField(14,2, null=True)
salary_max          DecimalField(14,2, null=True)
salary_currency     CharField(3, default="USD")
estimated_annual_cost  DecimalField(14,2, null=True)        # loaded annual cost (salary+benefits est.)
hiring_cost_budget  DecimalField(14,2, null=True)           # one-time recruitment cost (P2 optional)

# Job description (on this specific opening)
jd_summary          TextField(blank=True)                   # role overview / elevator pitch
jd_responsibilities TextField(blank=True)                   # bullet list of duties
jd_requirements     TextField(blank=True)                   # must-have qualifications
jd_nice_to_have     TextField(blank=True)                   # preferred qualifications
template            FK(JobDescriptionTemplate, null=True)   # which template was applied

# Workflow-owned status
status              CharField choices: draft/submitted/pending_approval/approved/posted/on_hold/filled/cancelled/rejected
submitted_at        DateTimeField(null=True, editable=False)
approved_at         DateTimeField(null=True, editable=False)
filled_at           DateTimeField(null=True, editable=False)
notes               TextField(blank=True)
```

**Key design decisions:**
- `designation` FK allows auto-populating `jd_*` fields + salary range from `Designation.description`/`requirements`/`min_salary`/`max_salary`. The requisition stores its own copy so hiring-event edits don't mutate the evergreen Designation.
- `status` is workflow-owned (set only by POST actions, not on the edit form — mirrors the SeparationCase pattern).
- `department` and `cost_center` are FKs to `core.OrgUnit` (same as `DepartmentProfile`/`CostCenterProfile`).
- `hiring_manager` and `recruiter` FK `hrm.EmployeeProfile` (never `core.Party` directly — per the HRM module's convention).
- No FK to Candidate/Interview/Offer — those models don't exist yet; 3.6 will add the back-FK.

---

### Model 2: `JobDescriptionTemplate` [JDTMPL-]

A reusable JD library entry keyed optionally by Designation. Inherits `TenantNumbered` (NUMBER_PREFIX = "JDTMPL").

**Proposed fields:**

```python
number          CharField(20, editable=False)       # JDTMPL-00001
name            CharField(255)                      # e.g. "Senior Software Engineer — Backend"
designation     FK(hrm.Designation, null=True)      # auto-suggest when req is for this designation
employment_type CharField choices (same as req, blank=True)
jd_summary      TextField(blank=True)
jd_responsibilities TextField(blank=True)
jd_requirements     TextField(blank=True)
jd_nice_to_have     TextField(blank=True)
is_active       BooleanField(default=True)
```

**Key design decisions:**
- Mirrors the `OnboardingTemplate.designation` FK pattern already in the codebase.
- Applying a template copies text into `JobRequisition.jd_*` fields (a copy-on-apply semantic, not a live link) so the req can be edited independently.
- No separate template-task lines needed — this is a text document, not a checklist.

---

### Model 3: `RequisitionApproval` [no prefix — child row]

One row per approval step per requisition. The collection of rows is the multi-level approval chain and the immutable audit trail.

**Proposed fields:**

```python
requisition     FK(JobRequisition, related_name="approvals")
step_order      PositiveSmallIntegerField              # 1, 2, 3 ... defines sequence
approver        FK(settings.AUTH_USER_MODEL)           # the designated approver
approver_role   CharField choices: hiring_manager/hr/finance/executive/custom  # label only
status          CharField choices: pending/approved/rejected/returned/skipped  # workflow-owned
decided_at      DateTimeField(null=True, editable=False)
decided_by      FK(User, null=True, editable=False)    # may differ from approver if delegated
comments        TextField(blank=True)                  # reason for rejection/return
```

**Key design decisions:**
- `step_order` enforces sequential flow; the view only notifies the approver whose step_order equals the current minimum pending step.
- `status` is workflow-owned (set only by the approve/reject/return POST actions).
- Never deleted — together the rows form the immutable approval audit trail.
- Three POST actions per step: **approve** (advances to next step or marks req `approved`), **reject** (terminates, req → `rejected`), **return** (req → `draft` for revision, all pending steps reset to `pending`).
- No separate status-history model needed in v1: the `RequisitionApproval` rows plus `core.AuditLog` cover the audit requirement.

---

## Deferred to later passes / integrations

| Feature | Reason deferred |
|---|---|
| Candidate linkage (3.6 FK) | Candidate model doesn't exist yet; 3.6 adds `candidate.requisition` FK |
| Interview/offer linkage (3.7/3.8) | Same — separate sub-modules |
| Auto-close when headcount filled | Requires 3.6 hire counter; stub `hires_made` field added but logic deferred |
| Condition-based approval routing (headcount/salary thresholds trigger different chains) | Needs a workflow-engine configuration model; P2 — defer to 0.11 workflow pass |
| Approval delegation (delegate-to colleague) | `delegated_to` FK can be added later; low MVP value |
| Re-approval on salary edit | View-level guard; deferred to hardening pass |
| External job board posting (LinkedIn, Indeed, etc.) | Third-party API integration; deferred to later |
| AI JD generation / bias detection | External AI API integration; deferred |
| Internal career portal (candidate-facing view) | Deferred to 3.6 Candidate Management |
| Requisition analytics / time-to-fill metrics | Deferred to 3.32 Analytics Dashboard / BI module |
| GL/budget integration | Informational only at this stage; salary cost posts in payroll (3.14/accounting) |
| Evergreen requisition headcount logic | `req_type=evergreen` choice is added, but auto-reopen logic deferred |
