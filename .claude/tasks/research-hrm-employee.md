# Research — Module 3.1: Employee Management (HRM) — Completion Pass
## Focus: Document Management + Employee Lifecycle + EmployeeProfile gaps

---

## Products surveyed

1. **Workday HCM** — enterprise HCM; industry reference for effective-dated job-change events (Change Job process) and worker document categories with expiry tracking. Sources: Workday community, Oregon State Workday worker-document PDF, LinkedIn Mastering Effective Dating article.
2. **SAP SuccessFactors Employee Central** — flagship enterprise HRIS; canonical source for `jobInfo` HRIS element event types (H=Hire, Data Change, etc.), event-reason codes (Promotion, Demotion, Lateral/Transfer, Location Change), and digital personnel-file concept. Sources: SAP Help Portal, SAP Community 2H 2025 release notes.
3. **BambooHR** — SMB-focused HRIS; uses named historical tables (`jobInfo`, `compensation`, `employmentStatus`) each with effective date + reason/comment; HR document folder hierarchy (4-level subfolders), grid/list views, drag-drop upload, multi-select. Sources: BambooHR product updates, API docs table-name-fields reference.
4. **Zoho People** — mid-market HRIS; document vault with validity dates, custom access controls, confidentiality, e-signature (Zoho Sign / DocuSign / Adobe Sign), acknowledgment tracking, automated document lifecycle workflows. Sources: Zoho People document management page.
5. **Keka HRMS** — India/GCC-focused HRIS; explicit 3-bucket verification workflow (Pending Verification / Pending on Employee / Verified), expiry date on every document, automated expiry alerts (60 / 30 / 7 days for GCC Iqama/visa), access-control of confidential documents feature. Sources: Keka employee document management page, help center articles.
6. **greytHR** — India-focused HRIS; passport + visa tracking (passport no., type, issue date, expiry "Valid Till", issue place, country, family-member passports); position history (designation, department, grade, location with effective-from/to dates); employee profile carries blood group, marital status, father's name, nationality, marriage date, confirmation date, notice period, present/permanent/contact addresses, government IDs (Aadhaar, PAN, PRAN, Election Card, Passport, Driving License). Sources: greytHR admin help, passport/visa article, position history article.
7. **Personio** — European SMB/mid-market HRIS; digital employee file with system document categories (Application Documents, Payroll, Performance, Time-off Certificates, Work Contracts); expiry tracking for contract renewals; document adds include name, category, optional date, optional comment. Sources: Personio digital employee file page, support articles on document categories.
8. **Darwinbox** — Asia-Pacific enterprise HRIS; centralized document management with predefined types (PAN, Aadhaar, Passport), e-document storage, OCR for document extraction, WhatsApp/mobile-first expiry alerts. Sources: Darwinbox employee documents product page.
9. **HiBob (Bob)** — modern HCM; employee data structured in categories with historical tables: Work, Employment, Lifecycle, Salary, Variable Pay, Address; Lifecycle table auto-updated by status changes; Work and Employment tables track historical effective-dated changes; profile has marital status, national ID, work location, notice period, address. Sources: HiBob API docs (explore-employee-data).
10. **Rippling** — workforce platform; custom employee profile fields configurable per work location (country-localized ID fields, e.g. SSN for US, UANumber for India); work location, employment type, department are required fields; supports custom fields for certifications, work permits, citizenship; configurable profile tabs. Sources: Rippling blog employee profiles template, developer API worker reference.

---

## Feature catalog by NavERP 3.1 sub-area

### 3.1.A — Employee Directory
- **Employee list with search + filter** — paginated list, search by name/number/department, filter by status/type/department/designation. Seen in: all 10 products. Priority: **table-stakes** · spine: reuses `EmployeeProfile` · **DONE (exists)**
- **Org chart view** — visual reporting-structure tree. Seen in: BambooHR, Workday, HiBob. Priority: **common** · spine: reuses `Employment.manager` + `OrgUnit` · buildable now (deferred to 3.2 Org Structure pass)
- **Employee photo + profile card** — avatar, number, name, department, designation thumbnail in directory. Seen in: BambooHR, Darwinbox, HiBob, Keka. Priority: **table-stakes** · spine: `EmployeeProfile.photo` already exists · **DONE (exists)**

### 3.1.B — Employee Profile (Personal Info, Contact, Emergency Contact)
- **Core personal information** — name (from `core.Party`), date of birth, gender, blood group, nationality. Seen in: all products. Priority: **table-stakes** · spine: `EmployeeProfile` · **DONE (exists)**
- **Marital status** — single/married/divorced/widowed/other; needed for benefits, tax, and dependents. Seen in: Workday, SAP SuccessFactors, greytHR, Zoho People, HiBob. Priority: **MUST** (gap) · spine: add to `EmployeeProfile` · buildable now
- **Current / permanent / contact address** — two distinct address records (present residence + permanent/hometown) + optional emergency/contact address. Seen in: greytHR (present + permanent + contact), Workday (home + mailing), Zoho People, Gusto. Priority: **MUST** (gap) · spine: add `EmployeeAddress` (separate table) OR add fields to `EmployeeProfile` — separate table preferred (supports multiple) · buildable now
- **Father's name / spouse name** — statutory/payroll compliance field (required for PF, ESI, gratuity in South Asia, GCC). Seen in: greytHR, Darwinbox, Keka. Priority: **SHOULD** (region-specific but common in target markets) · spine: add to `EmployeeProfile` · buildable now
- **Work email** — professional email distinct from `personal_email` (already on `EmployeeProfile`). Seen in: Workday, HiBob, Rippling, BambooHR. Priority: **MUST** (gap) · spine: add to `EmployeeProfile` · buildable now
- **Work location** — the office/site/remote location the employee reports to (distinct from org unit department). Seen in: HiBob, Workday, Rippling, greytHR, Keka. Priority: **MUST** (gap) · spine: add `work_location` CharField or FK to `core.OrgUnit(kind=branch)` · buildable now
- **Notice period** — contractual notice period in days/weeks, used in SeparationCase (already has `notice_period_days` there but not on the base profile for the contract default). Seen in: greytHR, HiBob, Personio. Priority: **SHOULD** (gap) · spine: add `notice_period_days` to `EmployeeProfile` as the contract-default · buildable now
- **Languages** — spoken/written languages for role-fit and global workforce planning. Seen in: Rippling, Workday. Priority: **COULD** · buildable now (simple CharField) · deferred
- **Emergency contacts** — already implemented (single contact: name/phone/relation). Seen in: all products. Improvement: support a second contact. Priority: **SHOULD** (gap) · add `emergency_contact_2_*` fields · buildable now
- **National ID / Tax ID** — national identifier (e.g., SSN/NRIC/Aadhaar/NID); stored separately from the personnel-file document vault for searchability. Seen in: Workday (Government IDs table), greytHR (Aadhaar/PAN/PRAN), HiBob (Identification category), Zoho People. Priority: **MUST** (gap) · add `national_id` + `national_id_type` to `EmployeeProfile` · buildable now

### 3.1.C — Employment Details (Job Title, Department, Reporting Manager, Employment Type)
- **Employment type** — already stored as `EmployeeProfile.employee_type` (full-time/part-time/contract/intern/consultant). Priority: **table-stakes** · **DONE (exists)**
- **Job title / department / manager** — stored in `core.Employment` (job_title / org_unit / manager), displayed on detail page. Priority: **table-stakes** · **DONE (exists)**
- **Designation / grade / salary band** — `hrm.Designation` with grade + min/max salary. Priority: **table-stakes** · **DONE (exists)**
- **Hired on / probation end / confirmed on** — all on `EmployeeProfile`. Priority: **table-stakes** · **DONE (exists)**
- **Employment status (active/on_leave/terminated)** — on `core.Employment.status`. Priority: **table-stakes** · **DONE (exists)**

### 3.1.D — Document Management (PRIORITY GAP)

#### D.1 Document vault / personnel file (what the best products do)
- **Personnel-file document vault** — a per-employee repository of identity, compliance, and contract documents (separate from onboarding-collected documents). Seen in: Workday (worker document categories), BambooHR (Documents tab with folder hierarchy), greytHR (Employee Documents + Passport & Visa sub-pages), Keka (Employee Documents tab), Personio (digital employee file), HiBob, Darwinbox, Zoho People. Priority: **table-stakes** · new table `EmployeeDocument` FK → `EmployeeProfile` · buildable now
- **Document type classification** — named categories covering the full lifecycle of employee documents:
  - Identity/KYC: national ID proof, passport, driving license, address proof
  - Work-authorization: visa, work permit, residency permit
  - Educational: degree certificate, professional certification, diploma
  - Employment: appointment letter, offer letter, employment contract, NDA, non-compete
  - Financial/tax: tax form (W-4/Form 16), bank proof, PF nomination
  - Medical: medical fitness certificate, vaccination record
  - Other / custom
  Seen in: Workday (Background Check, Certification, Education, Government ID, Immigration), greytHR, Keka (PAN/Aadhaar/Passport/Driving License + custom), Darwinbox, BambooHR. Priority: **table-stakes** · `document_type` choice field on `EmployeeDocument` · buildable now
- **Document number** — the alphanumeric ID printed on the document (passport number, PAN number, license number, visa number). Seen in: greytHR (Passport No., Visa No.), Darwinbox (predefined), Keka (in request templates). Priority: **MUST** · field on `EmployeeDocument` · buildable now
- **Issue date + expiry date** — validity window; expiry date drives reminders. Seen in: greytHR (issue date + Valid Till for passport/visa), Workday (Issued Date + Expiration Date for visas/IDs), Keka (expiry date field), Zoho People (document validity dates). Priority: **MUST** · `issued_on` + `expires_on` DateFields on `EmployeeDocument` · buildable now
- **Issuing authority / country** — who issued the document (e.g., "Passport Office, Mumbai", "DHA Dubai", "IRS"). Seen in: greytHR (Issue Place + Country), Workday (for immigration). Priority: **SHOULD** · `issuing_authority` CharField on `EmployeeDocument` · buildable now
- **Verification / validation status** — HR-side workflow: Pending / Verified / Rejected / Expired. Seen in: Keka (3-bucket: Pending Verification → Verified/Rejected), BambooHR, Darwinbox. Priority: **MUST** · `verification_status` choice field on `EmployeeDocument` · buildable now
- **File upload** — attach the actual scanned/PDF copy. Seen in: all products. Priority: **table-stakes** · `file` FileField on `EmployeeDocument` · buildable now
- **Confidentiality flag** — HR-only vs. employee-visible; some document types (medical, legal) visible only to HR. Seen in: Workday (separate document categories with role-based access), BambooHR (padlock icon on folders), Keka (confidential document access control feature). Priority: **SHOULD** · `is_confidential` BooleanField on `EmployeeDocument` · buildable now
- **Expiry reminders / alerts** — notification (email/in-app) to HR at N days before expiry. Seen in: Workday (automated 6-month/3-month alerts for work authorization), Keka (60/30/7-day for Iqama/visa), greytHR (expiry status display), Darwinbox (WhatsApp alerts). Priority: **SHOULD** · can be driven by a management command or periodic task checking `expires_on < today + 90`; flag `expiry_notified_at` to avoid repeat sends · integration/later for actual email delivery, but `expires_on` queryable now

#### D.2 Distinction from existing tables
- **`OnboardingDocument`** (already built) — scoped to an `OnboardingProgram`; tracks e-sign status; collected during joining. NOT the personnel-file vault.
- **`core.Document`** (generic attachment in the spine) — content-type generic relation; not employee-specific; not suitable for typed/dated/verified personnel docs.
- **`EmployeeDocument`** (new) — employee-specific, typed, numbered, with issue/expiry dates and verification status; the permanent personnel-file vault; FK → `EmployeeProfile`.

### 3.1.E — Employee Lifecycle (PRIORITY GAP)

#### E.1 What the best products do
- **Effective-dated job-change event log** — every position change (hire, confirmation, transfer, promotion, demotion, salary revision, re-designation, suspension, reinstatement, separation) is stored as a dated row with from→to field-values + reason + notes. This is the "job history" or "position history" timeline. Seen in: Workday (Change Job process: event type + reason code, effective date, new position/department/location/title/salary grade), SAP SuccessFactors (jobInfo HRIS element: event="H" for hire, "Data Change" for all changes, plus event reasons: Promotion/Demotion/Lateral Transfer/Location Change), BambooHR (`jobInfo` historical table: date, location, department, division, jobTitle, reportsTo; `compensation` table: startDate, rate, type, reason), greytHR (Position History: designation + department + grade + location, effective-from/to), HiBob (historical Work / Employment / Lifecycle / Salary tables, each with effective date), Personio (Employee History: attribute, old value, new value, application date, editor, approver). Priority: **table-stakes** · new table `EmployeeLifecycleEvent` FK → `EmployeeProfile` · buildable now
- **Event types covering the full HRM lifecycle**:
  - `hire` — initial hiring record (links to hired_on date)
  - `confirmation` — probation end / confirmed (links to confirmed_on)
  - `transfer` — department or location change (from→to department / location)
  - `promotion` — designation/grade upgrade (from→to designation, possibly salary change)
  - `demotion` — designation/grade downgrade (from→to designation)
  - `salary_revision` — CTC/pay-rate change without title change (from→to salary amount)
  - `re_designation` — title change without salary or grade change (from→to job title)
  - `location_change` — work location change only
  - `reporting_change` — manager / reporting line change (from→to manager)
  - `suspension` — temporary suspension with return-to-work date
  - `reinstatement` — return from suspension
  - `contract_renewal` — contract extension with new end date
  - `separation` — records the final exit event (redundant with `SeparationCase` but useful as a single-row summary in the timeline)
  Seen in: Workday, SAP SuccessFactors, BambooHR, HiBob, greytHR, Personio. Priority: **MUST** (hire/confirmation/transfer/promotion/salary_revision) · **SHOULD** (demotion/re_designation/location_change/reporting_change) · **COULD** (suspension/reinstatement/contract_renewal) · buildable now for all event types
- **From→to field capture** — for any change event, record the old value and new value (e.g., from_designation → to_designation, from_department → to_department, from_salary → to_salary) so the history is self-contained and auditable without joining other tables. Seen in: Workday (new org/position), SAP SuccessFactors (new vs. old jobInfo row), Personio (old value / new value columns), HiBob (effective rows vs. prior rows). Priority: **MUST** · separate `from_*` + `to_*` fields on `EmployeeLifecycleEvent` · buildable now
- **Reason / change reason** — textual or coded reason for the event (e.g., "Merit increase", "Restructuring", "Performance", "Better opportunity"). Seen in: Workday (reason codes: Lateral Move / Promotion / Demotion / Location Change), SAP SuccessFactors (event reasons as configurable options), BambooHR (compensation `reason` field), Personio (approver / reason columns). Priority: **MUST** · `reason` TextField (free text for v1; coded picklist is an enhancement) on `EmployeeLifecycleEvent` · buildable now
- **Effective date** — the date the change takes effect (not the date it was entered). Seen in: all products (Workday: "Effective Date defaults to start of next pay period"; BambooHR: `date`; greytHR: `Effective From`; HiBob: each table row has an effective date). Priority: **table-stakes** · `effective_date` DateField on `EmployeeLifecycleEvent` · buildable now
- **Initiated by / approved by** — who raised the event and who authorized it (for audit). Seen in: Personio (editor + approver columns), Workday (initiating user + action chain). Priority: **SHOULD** · `initiated_by` + `approved_by` FK → `settings.AUTH_USER_MODEL` on `EmployeeLifecycleEvent` · buildable now
- **Profile timeline / audit view** — an employee-profile section showing the ordered history of events, most-recent-first. Seen in: BambooHR (click table → History), Personio (Employee History tab), Workday (History UI on Full Profile). Priority: **MUST** · rendered from `EmployeeLifecycleEvent` ordered by `effective_date DESC` on the employee detail page · buildable now (template only, no new table)

---

## Recommended build scope for this pass (2 new models + profile field additions)

### Model 1: `EmployeeDocument` (PREFIX: EDOC-)
Personnel-file document vault — one row per document per employee. FK → `EmployeeProfile` (the anchor).

**Fields:**
- `employee` FK → `hrm.EmployeeProfile` (CASCADE)
- `document_type` CharField choices:
  - `national_id` National ID / Aadhaar / NRIC
  - `passport` Passport
  - `driving_license` Driving License
  - `address_proof` Address Proof
  - `visa` Visa
  - `work_permit` Work Permit
  - `degree_certificate` Degree / Diploma Certificate
  - `professional_cert` Professional Certification
  - `appointment_letter` Appointment Letter
  - `employment_contract` Employment Contract
  - `nda` Non-Disclosure Agreement
  - `non_compete` Non-Compete Agreement
  - `tax_form` Tax Form (W-4 / Form 16 / TDS)
  - `bank_proof` Bank Account Proof
  - `pf_nomination` PF / Pension Nomination
  - `medical_cert` Medical / Fitness Certificate
  - `background_check` Background Check Report
  - `experience_certificate` Previous Employment / Experience Letter
  - `other` Other
- `title` CharField(255) — human label (e.g., "Passport — MRZ2019")
- `document_number` CharField(100, blank) — the number on the document itself
- `issuing_authority` CharField(255, blank) — issuing body (e.g., "Passport Office, Delhi")
- `issuing_country` CharField(100, blank) — country code / name
- `issued_on` DateField(null, blank) — issue date
- `expires_on` DateField(null, blank) — expiry date (null = no expiry)
- `verification_status` CharField choices: `pending` / `verified` / `rejected` / `expired`
  - default `pending`; `expired` is auto-set or set by a management command when `expires_on < today`
- `is_confidential` BooleanField(default=False) — HR-only; hides from self-service
- `file` FileField(upload_to="hrm/employee_docs/%Y/%m/", null, blank)
- `notes` TextField(blank)
- `verified_by` FK → `AUTH_USER_MODEL` (null, blank, editable=False)
- `verified_at` DateTimeField(null, blank, editable=False)
- (from `TenantNumbered`) `number`, `tenant`, `created_at`, `updated_at`

**Indexes:** (tenant, employee), (tenant, document_type), (tenant, verification_status), (tenant, expires_on)
**Unique together:** (tenant, number)
**Derived from research:** BambooHR folder/upload model, greytHR passport/visa fields, Keka verification workflow, Workday worker document categories, Zoho People validity dates, Keka expiry alerts.

---

### Model 2: `EmployeeLifecycleEvent` (PREFIX: ELC-)
Immutable, auditable log of every job-change event. Each row represents one dated event in an employee's job history. FK → `EmployeeProfile`.

**Fields:**
- `employee` FK → `hrm.EmployeeProfile` (CASCADE)
- `event_type` CharField choices:
  - `hire` Hire
  - `confirmation` Confirmation (probation end)
  - `transfer` Transfer (department / location change)
  - `promotion` Promotion
  - `demotion` Demotion
  - `salary_revision` Salary Revision
  - `re_designation` Re-designation (title change)
  - `location_change` Location Change
  - `reporting_change` Reporting Manager Change
  - `suspension` Suspension
  - `reinstatement` Reinstatement
  - `contract_renewal` Contract Renewal
  - `separation` Separation (exit summary)
  - `other` Other
- `effective_date` DateField — when the change takes effect
- `reason` TextField(blank) — free-text reason / change reason
- From/to capture (all null/blank so only relevant fields are populated per event type):
  - `from_designation` FK → `hrm.Designation` (null, blank, SET_NULL)
  - `to_designation` FK → `hrm.Designation` (null, blank, SET_NULL)
  - `from_department` FK → `core.OrgUnit` (null, blank, SET_NULL)
  - `to_department` FK → `core.OrgUnit` (null, blank, SET_NULL)
  - `from_location` CharField(255, blank) — work location before
  - `to_location` CharField(255, blank) — work location after
  - `from_job_title` CharField(255, blank) — free-text title before
  - `to_job_title` CharField(255, blank) — free-text title after
  - `from_salary` DecimalField(14,2, null, blank) — CTC/salary before
  - `to_salary` DecimalField(14,2, null, blank) — CTC/salary after
  - `from_manager` FK → `hrm.EmployeeProfile` (null, blank, SET_NULL, related_name="+")
  - `to_manager` FK → `hrm.EmployeeProfile` (null, blank, SET_NULL, related_name="+")
  - `from_employee_type` CharField(20, blank) — employment type before
  - `to_employee_type` CharField(20, blank) — employment type after
- `notes` TextField(blank) — additional notes / comments
- `initiated_by` FK → `AUTH_USER_MODEL` (null, blank, SET_NULL, editable=False)
- `approved_by` FK → `AUTH_USER_MODEL` (null, blank, SET_NULL, editable=False)
- `approved_at` DateTimeField(null, blank, editable=False)
- (from `TenantNumbered`) `number`, `tenant`, `created_at`, `updated_at`

**Indexes:** (tenant, employee, effective_date), (tenant, event_type), (tenant, employee, event_type), (tenant, effective_date)
**Unique together:** (tenant, number)
**Ordering:** `-effective_date`
**Derived from research:** Workday Change Job events, SAP SuccessFactors jobInfo event types + event reasons, BambooHR jobInfo/compensation historical tables, greytHR position history, HiBob Work/Employment/Lifecycle tables, Personio Employee History (old value / new value columns).

---

### EmployeeProfile field additions (not new models — additions to the existing model)

These fields are missing from the current `EmployeeProfile` based on the competitive analysis:

| Field | Type | Why / Seen In |
|---|---|---|
| `marital_status` | CharField choices: `single / married / divorced / widowed / other`, blank | Workday, SAP SF, greytHR, HiBob, Zoho People — statutory/benefits |
| `work_email` | EmailField(blank) | Workday, HiBob, Rippling, BambooHR — professional contact address |
| `work_location` | CharField(255, blank) | HiBob, greytHR, Keka, Rippling — office/site/remote assignment |
| `notice_period_days` | PositiveSmallIntegerField(null, blank) | greytHR, HiBob, Personio — contract default; also used by SeparationCase |
| `national_id` | CharField(100, blank) | Workday Gov IDs, greytHR Aadhaar/PAN, HiBob Identification, Zoho |
| `national_id_type` | CharField(50, blank) | pairs with national_id — e.g., "Aadhaar", "SSN", "NRIC", "NID" |
| `passport_number` | CharField(50, blank) | greytHR passport page, Workday immigration, Keka doc types |
| `passport_expiry` | DateField(null, blank) | greytHR "Valid Till", Workday expiration date |
| `father_name` | CharField(255, blank) | greytHR, Darwinbox, Keka — PF/ESI/gratuity statutory field |
| `spouse_name` | CharField(255, blank) | greytHR — address + family details section |
| `current_address` | TextField(blank) | greytHR "Present Address", HiBob address table, Gusto home address |
| `permanent_address` | TextField(blank) | greytHR "Permanent Address", Workday mailing address |
| `emergency_contact_2_name` | CharField(255, blank) | almost all products support ≥2 emergency contacts |
| `emergency_contact_2_phone` | CharField(30, blank) | second emergency contact phone |
| `emergency_contact_2_relation` | CharField(100, blank) | relationship to second contact |

Note: `current_address` and `permanent_address` as TextFields (single-field freeform) are adequate for v1. A proper multi-field `EmployeeAddress` table (line1/city/state/postal/country) is a deferred enhancement — the TextField is buildable now and avoids an extra model.

---

## Deferred (later passes / integrations)

- **Expiry email/push notifications** — a background task (Celery / management command) that emails HR when `EmployeeDocument.expires_on < today + N days`. The data model (`expires_on`) is buildable now; the delivery mechanism (SMTP/provider) is an integration pass. `EmployeeDocument` should store `expiry_alert_sent_at` DateTimeField to prevent duplicate sends.
- **Multi-field address table** (`EmployeeAddress`) — a proper table with line1/line2/city/state/postal/country fields and address_type (current/permanent/contact/emergency). Deferred in favor of TextField addresses for v1.
- **Second emergency contact as a table** — if more than two contacts are needed, a separate `EmployeeEmergencyContact` table is cleaner. v1 uses flat `_2_*` fields.
- **Org chart visualization** — covered in 3.2 Organizational Structure pass.
- **Document OCR / AI extraction** — Darwinbox's AI OCR auto-populates `document_number`, `issued_on`, `expires_on` from scanned images. Requires an OCR API integration (Tesseract / AWS Textract / Google Vision). Out of scope for this Django pass.
- **E-signature on personnel documents** — Zoho People integrates Zoho Sign / DocuSign / Adobe Sign for documents requiring employee signature. The `OnboardingDocument` already handles e-sign for onboarding. Extending to personnel-vault documents requires an e-sign provider integration.
- **Document retention policy / auto-purge** — GDPR/DPDP-driven scheduled deletion of documents past their retention window. Data model note: add a `retention_until` DateField to `EmployeeDocument` when this ships.
- **Salary band history tracking** — Designation already has `min_salary`/`max_salary` but a salary-band-change history (separate from an individual employee's salary revision event) is a Compensation Management feature in 3.37 or the Accounting payroll pass.
- **Position freeze / headcount budget** — workforce planning feature (3.40); not part of 3.1.
- **Suspension workflow with approval** — the `suspension` event type in `EmployeeLifecycleEvent` records the fact, but a proper suspension workflow (approvals, return-to-work automation, disciplinary link) belongs in 3.39 Compliance & Legal.
- **Passport / visa as sub-types of EmployeeDocument** — in greytHR, passport and visa have dedicated sub-pages with family-member tracking. For v1, these are just `document_type="passport"` or `"visa"` rows in `EmployeeDocument`. A dedicated `EmployeePassport` / `EmployeeVisa` table (with family-member association and Muqeem/immigration system integration) is a later compliance pass.
- **Background check result storage** — Workday/BambooHR keep background check documents in a restricted category. The `document_type="background_check"` on `EmployeeDocument` with `is_confidential=True` covers v1; a full BGV workflow integration (vendor API calls, status webhooks) is a later pass.
- **Languages / skills inventory** — Rippling/Workday track spoken languages and skill levels. A `EmployeeSkill` or `EmployeeLanguage` table is a Talent Management (3.38) feature.
- **Custom document fields / picklist management** — Keka and Darwinbox allow admin-defined document types and custom metadata fields per type. This is a 0.10 Custom Fields feature, not a module-level model.
