# Research — Module 3: HRM, Sub-module 3.25 Personal Information (Self-Service) (hrm)

Scope note: 3.25 is the **Employee Self-Service (ESS) personal-information layer**, not a re-model of
`hrm.EmployeeProfile`. `EmployeeProfile` already carries flat columns for bank details
(`bank_name/bank_account/bank_routing` + masked accessors), two hardcoded emergency-contact slots
(`emergency_contact_name/phone/relation` + `_2_`), addresses (`current_address`/`permanent_address`),
contact info (`personal_email`/`work_email`/`mobile`), and personal-file fields (`date_of_birth`,
`marital_status`, `father_name`, `spouse_name`, `national_id`, `passport_number`, `photo`). This pass
does **not** duplicate those columns. What every researched ESS product adds on top of a flat HR-record
is: (1) the **employee-facing self-view/self-edit surface** over that record, (2) **proper child
entities** the 2-slot/1-slot flat columns cannot model — unlimited emergency contacts, multiple bank
accounts with one designated salary account, and family/dependent members, and (3) a **maker-checker
change-request workflow** that gates sensitive fields (bank, legal name, national ID, DOB) behind HR
review while letting low-risk fields (address, personal email, mobile) save directly.

**"My profile" resolution (integration note, not a spine change):** the logged-in `accounts.User` has a
nullable `party` FK to `core.Party` (`apps/accounts/models.py`), and `hrm.EmployeeProfile` has a 1:1
`party` FK back to the same `core.Party`. The natural resolution is
`request.user.party.employee_profile` (guarding for `party_id is None` or no linked profile — e.g. an
HR admin user with no employee record). This is a view-layer lookup for the `todo`/build pass to wire
up; it needs no new spine field.

## Leaders surveyed (with source links)

1. **Workday HCM** — enterprise HCM; the reference implementation for **effective-dated** personal-info
   changes with HR-approval routing and supporting-document requirements on sensitive fields —
   [Managing Your Personal and Work Information](https://employeehelp.workday.uw.edu/using-workday/managing-your-personal-and-work-information/), [Update_Employee_Personal_Info API](https://community.workday.com/sites/default/files/file-hosting/productionapi/Human_Resources/v20/Update_Employee_Personal_Info.html)
2. **SAP SuccessFactors Employee Central** — enterprise HCM core; effective-dated objects, "guardrails"
   approval workflows that can gate even fields the employee otherwise has edit permission on —
   [Employee Self-Service (ESS)](https://help.sap.com/docs/successfactors-employee-central/implementing-employee-central-core/employee-self-service-ess), [Unique Features of Workflow in SuccessFactors EC](https://www.yash.com/blog/workflow-in-successfactors-employee-central/)
3. **BambooHR** — SMB/mid-market HRIS; the clearest "unlimited emergency contacts, approval optional
   per field" ESS reference — [Update My Emergency Contacts](https://help.bamboohr.com/hc/en-us/articles/227351107-Update-my-Emergency-Contacts), [Employee Self-Service Help Manual](https://help.bamboohr.com/hc/en-us/articles/227321928-Employee-Self-Service-Help-Manual)
4. **Gusto** — SMB payroll/HRIS; the multi-bank-account + percentage/dollar **split-deposit**
   specialist (up to 5 accounts, Plaid verification) — [Edit bank and personal information](https://support.gusto.com/article/137880230100000/edit-bank-and-personal-information-for-us-employees-and-contractors)
5. **ADP Workforce Now** — enterprise payroll/HRIS; dependents tied to benefits life-events, and
   **beneficiary** designation with primary/secondary percentage allocation — [Employee Self-Service Payroll and HR Software](https://www.adp.com/resources/articles-and-insights/articles/e/employee-self-service.aspx)
6. **Zoho People** — SMB/mid-market HRMS; profile self-edit gated by admin-configured field
   permissions, audit-logged changes — [Zoho People Employee Self-Service](https://help.zoho.com/portal/en/kb/people/zoho-people-4-0/employee-handbook-zoho-people-4-0/employee-self-service/articles/zoho-people-employee-self-service), [Employee Self-Service Portal](https://www.zoho.com/people/employee-self-service.html)
7. **Keka HR** — India/APAC-focused HRMS; the clearest **per-field approval-permission matrix**
   reference (admin sets, per field: mandatory / who can view / who can edit / whether it needs
   approval) — [Employee Self-Service Portal](https://www.keka.com/employee-self-service-portal), [Managing Employee Profiles on Keka HR](https://help.keka.com/hc/en-us/articles/39946786383889-Managing-Employee-Profiles-on-Keka-HR)
8. **Darwinbox** — APAC enterprise HCM; ESS lets employees change contact/address/bank details
   without submitting paperwork to HR, with select fields still requiring HR authorization —
   [Everything You Need to Know About Self-Service HR Software](https://blog.darwinbox.com/self-service-hr-software)
9. **Rippling** — unified HR/IT/Finance platform; personal-dashboard self-service for viewing/updating
   personal information alongside pay stubs and benefits (least ESS-specific documentation of the ten,
   included for market-breadth confirmation) — [HR Workflow Automation — Employee Contact Info](https://www.rippling.com/recipes/employee-contact-info)
10. **greytHR** — India-focused HRMS; the most concrete **Family Details + Nomination** reference —
    family member roster (name/relationship/DOB, minor/mental-illness + guardian fields) feeding a
    separate nomination screen (select a family member as EPF/EPS/ESI/Gratuity nominee with a
    Nomination % that must sum to 100% for multi-nominee schemes) and a dedicated bank-details update
    flow — [Add/edit employee's nomination details](https://admin-help.greythr.com/admin/answers/121942238/), [How can I update an employee's bank account details?](https://support.greythr.com/hc/en-us/articles/4402841594893-How-can-I-update-an-employee-s-bank-account-details-), [View employee profile](https://ess-help.greythr.com/employee-portal/answers/57690611/)

## Feature catalog by sub-module

### 3.25 Profile Management — Update personal details

- **Self-view/self-edit of core personal fields** (gender, DOB, marital status, blood group,
  nationality, etc.) · seen in: Workday, SAP SuccessFactors EC, Zoho People, Keka, Darwinbox ·
  priority: table-stakes · spine: reuse `hrm.EmployeeProfile` (already has every one of these fields)
  · buildable now (a scoped "my profile" view/edit over the existing model)
- **Field-level self-edit permission** — which fields an employee can edit directly vs. which are
  read-only vs. which route to HR approval · seen in: Keka (admin-configurable Manage Field
  Permissions: mandatory / viewable / editable / approval-required, per field), SAP SuccessFactors EC
  (role-based self-service permissions, "guardrails" workflow even on employee-editable fields) ·
  priority: differentiator for a full configurable matrix; table-stakes for the underlying concept
  ("some fields need approval, some don't") · spine: this pass hardcodes a small sensitive-field list
  (bank, national ID, passport, DOB, legal name) as approval-gated via the new change-request model,
  everything else direct-edit · buildable now (hardcoded list); full per-tenant configurable
  permission matrix deferred
- **Profile photo self-upload** · seen in: Zoho People, BambooHR, Workday · priority: table-stakes ·
  spine: reuse `EmployeeProfile.photo` · buildable now
- **Read-only display of employment data** (job title, department, manager, hire date) alongside the
  editable personal section · seen in: Zoho People (Profile page shows designation/department/
  manager/reportees as read-only context) · priority: table-stakes · spine: reuse
  `EmployeeProfile.department`/`.manager` properties + `core.Employment` · buildable now
- **Legal name change requires supporting document + HR approval**, distinct from lower-risk fields ·
  seen in: Workday (name changes routed for approval, proof required for DOB/gender/citizenship),
  SAP SuccessFactors EC (guardrails workflow) · priority: common · spine: routes through the new
  change-request model against `party.name`; document attach reuses `core.Document`
  (GenericForeignKey) · buildable now (approval flow + optional document); a distinct
  "preferred/display name vs. legal name" pair of fields is integration/later

### 3.25 Contact Update — Address, phone, email changes

- **Self-service edit of address, personal email, mobile** · seen in: Workday, BambooHR, Zoho People,
  Darwinbox, SAP SuccessFactors EC, ADP · priority: table-stakes · spine: reuse
  `EmployeeProfile.current_address`/`.personal_email`/`.mobile` · buildable now
- **Multiple address slots (current/permanent)** · already built as 2 flat fields on
  `EmployeeProfile`; full multi-type address history is what Workday/SAP SuccessFactors EC model with
  unlimited effective-dated rows · priority: common (2-slot is already table-stakes-covered);
  unlimited-history is differentiator · spine: reuse the existing 2 fields — do **not** add
  `core.Address` rows this pass (would duplicate the flat columns for no new capability) · buildable
  now (edit only)
- **Effective-dated changes** — a change is recorded with an intended effective date and the prior
  value is preserved for history, rather than being overwritten silently · seen in: Workday
  ("effective-dated transactions" is the platform's core HR-data concept), SAP SuccessFactors EC
  (effective-dated objects, captures history) · priority: differentiator · spine: the new change-request
  model's `effective_date` + `old_value`/`new_value` fields capture the *intent* and *audit* of a
  dated change; a full slowly-changing-dimension replay of `EmployeeProfile` itself is integration/later
- **Work email is HR/IT-managed, not self-editable** — distinct from personal email · seen in: SAP
  SuccessFactors EC (separate Home vs. Work contact information, work info typically
  system/IT-provisioned) · priority: common · spine: reuse `EmployeeProfile.work_email`, excluded
  from the ESS edit form (admin/HR-only) · buildable now (view-layer scoping, no schema change)
- **Change audit trail** — who changed what, when, before → after · seen in: Zoho People (audit logs),
  Keka, SAP SuccessFactors EC · priority: table-stakes · spine: reuse `core.AuditLog` (already logs
  create/update on every tenant model via the existing CRUD helper) + the new change-request record
  gives field-level before/after specifically for approval-gated fields · buildable now

### 3.25 Emergency Contacts — Add/edit emergency contacts

- **Multiple emergency contacts, not capped at a fixed number** · seen in: BambooHR ("Add Contact",
  unlimited), Workday, Zoho People, greytHR · priority: table-stakes · spine: **new table**
  `EmergencyContact` — `EmployeeProfile`'s 2 hardcoded slots are a known scale limit this table lifts
  · buildable now
- **Primary/priority ordering** — which contact to call first · seen in: BambooHR, Workday · priority:
  common · spine: `EmergencyContact.is_primary` (bool, one true per employee) + `priority_order` (int)
  · buildable now
- **Relationship + phone/alt-phone/email/address per contact** · seen in: BambooHR, Zoho People,
  Darwinbox · priority: table-stakes · spine: `EmergencyContact` fields
  `name`/`relationship`/`phone`/`alt_phone`/`email`/`address` · buildable now
- **Changes may require approval before appearing on file** (tenant-configurable in the leaders) ·
  seen in: BambooHR ("updates may require approval before they display"), Keka (per-field permission
  config) · priority: common (as a *capability*); this pass treats emergency contacts as a lower-risk
  field group and lets employees **direct-edit** them (matching the majority of the ten leaders, which
  default emergency-contact edits to immediate) · spine: no approval gate on `EmergencyContact` this
  pass — flagged explicitly as a deliberate scope choice, not an oversight · buildable now

### 3.25 Bank Details — Update salary account

- **Multiple bank accounts on file** · seen in: Gusto (up to 5 accounts) · priority: differentiator
  (most other leaders model a single primary account; Gusto is the standout) · spine: **new table**
  `EmployeeBankAccount` — replaces the flat `bank_name`/`bank_account`/`bank_routing` trio on
  `EmployeeProfile` with unlimited rows per employee · buildable now
- **Exactly one account designated "salary account" / primary pay route** · seen in: greytHR (single
  active Bank Account card), ADP, Gusto (default account) · priority: table-stakes · spine:
  `EmployeeBankAccount.is_salary_account` (bool) with a save()-time single-`True`-per-employee
  constraint · buildable now
- **Split/percentage deposit across multiple accounts** · seen in: Gusto (percentage or fixed-dollar
  split, up to 5 accounts) · priority: differentiator · spine: `EmployeeBankAccount.split_percentage`
  (decimal, optional) · buildable now (stores the intended split; the actual payroll-run disbursement
  math is 3.14/3.17 Payroll territory — deferred)
- **Verification status** (e.g. instant bank verification via Plaid, or manual/pending review) · seen
  in: Gusto (Plaid verification, alerts on bank issues), implied by every payroll-linked ESS ·
  priority: common · spine: `EmployeeBankAccount.verification_status`
  (`unverified`/`pending`/`verified`) · buildable now as an admin/HR-set status; live bank-verification
  API integration is integration/later
- **Bank-detail changes are always HR/payroll-approval-gated** — the single highest-fraud-risk field
  group across every researched product · seen in: Workday, SAP SuccessFactors EC (guardrails
  workflow), Keka (payroll-linked fields are the canonical example of an approval-required field) ·
  priority: table-stakes · spine: `EmployeeBankAccount` create/edit routes through the new
  change-request model — no direct self-save on this table · buildable now
- **Masked display of the account number, never rendered in full after entry** · seen in: universal
  fintech UX across all ten, and the EXISTING NavERP precedent
  (`EmployeeProfile.masked_bank_account()`) · priority: table-stakes · spine: port the identical
  `_mask_last4` helper already on `EmployeeProfile` to `EmployeeBankAccount` · buildable now

### 3.25 Family Details — Dependent information for benefits

- **Family member roster: name, relationship, date of birth** · seen in: greytHR (Family Details:
  Name/Relationship/DOB, "+Add another member"), Zoho People, Darwinbox · priority: table-stakes ·
  spine: **new table** `FamilyMember` · buildable now
- **Dependent flag for benefits/insurance eligibility** · seen in: ADP Workforce Now (Manage
  Dependents page tied to benefits coverage, add/remove on a life event), greytHR (Family Details
  feeds statutory nomination) · priority: table-stakes · spine: `FamilyMember.is_dependent` (bool) ·
  buildable now
- **Minor / incapacitated flag + guardian details** · seen in: greytHR (Minor/Mental Illness checkbox
  + guardian name/relationship/address, required when checked) · priority: common · spine:
  `FamilyMember.is_minor` (bool) + `guardian_name`/`guardian_relationship` · buildable now
- **Nominee designation with percentage allocation** for statutory/benefit schemes · seen in: greytHR
  (select a family member as EPF/EPS/ESI/Gratuity nominee, Nomination % per nominee — EPF and Gratuity
  allow multiple nominees summing to 100%, EPS and ESI allow only one), ADP (Voluntary Life beneficiary
  primary/secondary with percentage) · priority: differentiator · spine: `FamilyMember.is_nominee`
  (bool) + `nominee_percentage` (decimal) — a single simplified percentage field this pass, not a
  per-scheme nomination sub-table · buildable now (simplified); full per-scheme (EPF/EPS/ESI/Gratuity)
  nomination bookkeeping with scheme-specific single-vs-multi rules is integration/later (depends on
  3.15 Statutory Compliance existing first)
- **Life-event-triggered dependent changes** (birth, marriage, divorce) that feed benefits
  re-enrollment · seen in: ADP Workforce Now ("report a life-changing event") · priority:
  differentiator · integration/later — needs 3.37 Compensation & Benefits as the consumer of the event
- **Family member changes require HR approval** — same sensitivity tier as bank/legal-name in the
  leaders that support configurable gating · seen in: Keka (field permission config), SAP
  SuccessFactors EC (guardrails workflow) · priority: common · spine: routes through the new
  change-request model · buildable now

### 3.25 Change-Request / Approval Workflow (cross-cutting — the connective tissue across all 5 bullets)

- **Maker-checker workflow**: the employee submits a proposed change to a sensitive field/record; HR
  reviews and approves/rejects before it takes effect, rather than the employee silently overwriting
  the field · seen in: BambooHR, Workday, SAP SuccessFactors EC, Darwinbox, Keka — universal across
  every leader surveyed for at least the sensitive fields (bank, legal name, national ID, DOB) ·
  priority: table-stakes · spine: **new table** `EmployeeInfoChangeRequest`, using a generic
  `content_type`/`object_id` pointer — mirrors the GenericForeignKey pattern already used by
  `core.AuditLog`/`core.Activity`/`core.Document` in this codebase, so the same request model can gate
  a field on `EmployeeProfile` itself or a new/changed `EmployeeBankAccount`/`FamilyMember` row ·
  buildable now
- **Configurable per-field "requires approval" matrix** (admin decides which fields are direct-edit vs.
  approval-gated) · seen in: Keka (Manage Field Permissions: mandatory / viewable / editable / approval
  needed, per field) · priority: differentiator · integration/later for a full per-tenant configuration
  UI — this pass hardcodes the sensitive set (bank account number, `is_salary_account`, `national_id`,
  `passport_number`, `date_of_birth`, legal name/`party.name`) as always-approval-gated, and address /
  personal email / mobile / emergency contacts / family-member add as direct-edit
- **Supporting document attachment on a change request** (e.g. proof of DOB/marriage/legal-name change)
  · seen in: Workday (proof required for DOB/gender/citizenship-status changes) · priority: common ·
  spine: reuse `core.Document` (GenericForeignKey to the `EmployeeInfoChangeRequest`) — no new
  file-handling model needed · buildable now
- **Notification to HR when a request is pending, and to the employee when it's decided** · seen in:
  all ten researched products · priority: table-stakes · spine: this pass ships an in-app "pending
  requests" list view for HR/admin; actual email/push delivery is Module 0.12 infrastructure ·
  integration/later for the notification channel, buildable now for the in-app queue
- **Full before/after audit trail** · seen in: Zoho People (audit logs, GDPR-compliant), enterprise
  IAM practice generally · priority: table-stakes · spine: reuse `core.AuditLog` (already captures
  create/update on every tenant model) + `EmployeeInfoChangeRequest.old_value`/`.new_value` gives
  field-level before/after specifically for the approval-gated set · buildable now

## Recommended build scope (this pass — 4 models)

Five NavERP.md bullets, four models — Profile Management and Contact Update are covered by an ESS
view/edit surface over the **existing** `EmployeeProfile` (no new table) routed through the shared
change-request model for its sensitive fields; Emergency Contacts, Bank Details, and Family Details
each get the proper child table their flat/2-slot columns cannot model; the change-request model is
the connective workflow all five bullets share.

- **`EmergencyContact`** [`TenantOwned`] — fields: `employee` (FK `EmployeeProfile`, CASCADE), `name`,
  `relationship`, `phone`, `alt_phone` (blank), `email` (blank), `address` (text, blank), `is_primary`
  (bool, one `True` per employee enforced in `clean()`/`save()`), `priority_order` (int), `notes`.
  Direct self-edit (no approval gate this pass — see the 3.25 Emergency Contacts catalog note on that
  deliberate scope choice). Justified by: unlimited multi-contact roster (BambooHR, Workday, Zoho
  People, greytHR), primary/priority ordering (BambooHR, Workday), relationship+phone+email fields
  (BambooHR, Zoho People, Darwinbox). Reuses `EmployeeProfile` as the parent FK; the flat
  `emergency_contact_*`/`emergency_contact_2_*` fields on `EmployeeProfile` stay as-is (legacy
  quick-reference; not migrated away this pass).

- **`EmployeeBankAccount`** [`TenantOwned`] — fields: `employee` (FK `EmployeeProfile`, CASCADE),
  `bank_name`, `account_holder_name`, `account_number` (WARNING: plaintext for demo, mirror the
  `EmployeeProfile.bank_account` note — mask with a ported `_mask_last4()`/`masked_account_number()`),
  `routing_number` (blank — IFSC/ABA/sort-code equivalent), `account_type`
  (`checking`/`savings`/`other`), `is_salary_account` (bool, one `True` per employee enforced in
  `clean()`/`save()`), `split_percentage` (decimal, optional — Gusto-style split deposit, stored not
  yet wired to payroll disbursement), `verification_status`
  (`unverified`/`pending`/`verified`), `status` (`active`/`inactive`). **All create/edit/delete on this
  model routes through `EmployeeInfoChangeRequest`** — no direct employee self-save (highest-risk
  field group; every leader gates it). Justified by: multiple accounts + split deposit (Gusto), single
  designated salary account (greytHR, ADP), verification status (Gusto/Plaid), always-approval-gated
  changes (Workday, SAP SuccessFactors EC, Keka), masked display (existing `EmployeeProfile` precedent
  + universal fintech UX). Reuses `EmployeeProfile` as parent, the exact `_mask_last4` masking pattern,
  and `_SENSITIVE_AUDIT_FIELDS` redaction convention already established for `bank_account`/
  `bank_routing`.

- **`FamilyMember`** [`TenantOwned`] — fields: `employee` (FK `EmployeeProfile`, CASCADE), `name`,
  `relationship` (`spouse`/`child`/`parent`/`sibling`/`other`), `date_of_birth`, `gender` (blank,
  reuse `EmployeeProfile.GENDER_CHOICES`), `is_dependent` (bool — benefits/insurance eligibility),
  `is_minor` (bool), `guardian_name` (blank), `guardian_relationship` (blank), `is_nominee` (bool),
  `nominee_percentage` (decimal, optional — simplified single percentage, not per-scheme), `notes`.
  Create/edit routes through `EmployeeInfoChangeRequest` (same sensitivity tier as bank/legal-name).
  Justified by: family roster with name/relationship/DOB (greytHR, Zoho People, Darwinbox), dependent
  flag for benefits (ADP, greytHR), minor+guardian fields (greytHR), nominee+percentage (greytHR,
  ADP beneficiary %). Reuses `EmployeeProfile` as parent and its `GENDER_CHOICES`.

- **`EmployeeInfoChangeRequest`** [`ICR-`, `TenantNumbered`] — fields: `employee` (FK
  `EmployeeProfile`, CASCADE — whose record is being changed), `content_type`/`object_id` (Generic FK
  — the target record: `EmployeeProfile` itself for legal-name/DOB/national-ID/passport changes, or a
  `EmergencyContact`/`EmployeeBankAccount`/`FamilyMember` row for those), `change_type`
  (`update`/`create`/`delete`), `field_name` (blank when the whole related record is being
  created/deleted rather than one field updated), `old_value` (text, blank), `new_value` (text),
  `reason` (text — employee's justification), `status`
  (`pending`/`approved`/`rejected`/`cancelled`), `requested_by` (FK `settings.AUTH_USER_MODEL`),
  `reviewed_by` (FK `settings.AUTH_USER_MODEL`, null), `reviewed_at`, `review_note`, `effective_date`
  (nullable date — the Workday/SAP SuccessFactors EC "effective-dated" intent, stored as a field
  rather than a full temporal replay). Justified by: maker-checker gating (BambooHR, Workday, SAP
  SuccessFactors EC, Darwinbox, Keka), per-field approval matrix (Keka — hardcoded sensitive-list this
  pass), supporting-document attach (Workday — via reused `core.Document`), full audit trail (Zoho
  People — via reused `core.AuditLog` + this model's own before/after). Reuses the GenericForeignKey
  pattern already established by `core.AuditLog`/`core.Activity`/`core.Document` rather than inventing
  a new polymorphic-reference shape.

## Deferred (later passes / integrations)

- **Full per-tenant configurable field-permission matrix** (Keka-style: admin sets per-field
  mandatory/viewable/editable/approval-required) — this pass hardcodes a fixed sensitive-field list;
  a true configuration UI is a distinct, reusable capability (could also serve other self-service
  sub-modules) and belongs with Module 0's form-builder/custom-fields infrastructure (0.10).
- **True effective-dated / slowly-changing-dimension replay of `EmployeeProfile`** (Workday, SAP
  SuccessFactors EC) — this pass stores `effective_date` as an *intent* field on the change request,
  not a full temporal history of every profile field with point-in-time queries.
- **Multiple address types with full address history** (mailing/billing beyond current/permanent) —
  the existing 2 flat fields on `EmployeeProfile` are reused as-is; adding `core.Address` rows would
  duplicate without adding capability this pass.
- **Per-scheme statutory nomination (EPF/EPS/ESI/Gratuity)** matching greytHR's exact business rules
  (single-nominee-only for EPS/ESI, multi-nominee summing to 100% for EPF/Gratuity) — deferred until
  3.15 Statutory Compliance exists as the consumer; this pass ships one simplified
  `nominee_percentage` field on `FamilyMember`.
- **Life-event-triggered benefits re-enrollment** (ADP: birth/marriage/divorce auto-prompts a benefits
  change) — deferred to 3.37 Compensation & Benefits, which doesn't exist yet.
- **Live bank-account verification** (Plaid/Open Banking instant verification) — `verification_status`
  is a manually/admin-set field this pass; the API integration is Module 0.13-territory.
- **Split-deposit disbursement math actually wired into a payroll run** — `EmployeeBankAccount.
  split_percentage` is stored this pass; consuming it during a payroll run is 3.14/3.17 territory.
- **Notification delivery** (email/push to HR on a pending request, to the employee on a decision) —
  this pass ships an in-app pending-requests queue; actual delivery channels are Module 0.12
  infrastructure.
- **Preferred/display name distinct from legal name**, with per-field-type document requirements
  enforced in code (Workday requires proof specifically for DOB/gender/citizenship) — this pass allows
  attaching a `core.Document` to any change request but doesn't hard-require one per field type.
