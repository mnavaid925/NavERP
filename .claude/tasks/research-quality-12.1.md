# Research — Sub-module 12.1: Document Control & Management (Module 12 — Quality Management System, `quality`)

## Repo state checked first

- **`LIVE_LINKS` built in Module 12 so far:** None (`quality` is a brand new app).
  - Modules 0 through 11 are 100% built (`0.1`–`0.21`, `1.1`–`1.12`, `2.1`–`2.15`, `3.1`–`3.41`, `4.1`–`4.19`, `5.1`–`5.20`, `6.1`–`6.19`, `7.1`–`7.19`, `8.1`–`8.19`, `9.1`–`9.20`, `10.1`–`10.19`, `11.1`–`11.19` — verified via `apps/core/navigation.py`).
  - **`12.1` is the very first sub-module of Module 12.**
- **Sibling models and existing quality assets in other modules:**
  - `apps/scm/models/QualityManagement/`: `CapaActions.py` (`CAPA`), `InspectionPlans.py`, `NonConformances.py` (`NCR`), `QualityAudits.py` (`QA`), `QualityInspections.py` (`QC`) — SCM 4.9 supply-chain quality.
  - `apps/inventory/models/QualityControl/`: `DefectReports.py`, `QcChecklists.py`, `QcRoutingRules.py`, `QuarantineOrders.py` (`QRD`) — Inventory 5.12 QC.
  - `apps/projects/models/QualityManagement/`: `DeliverableInspections.py` (`QCI`), `QualityDefects.py` (`QDF`), `QualityPlans.py` (`QPL`), `QualityReviews.py` (`QRV`) — Projects 7.15 quality.
  - *Distinction:* None of these touch regulated **Quality Document Control & Management** (SOPs, Work Instructions, Policies, DCOs, 21 CFR Part 11 electronic signatures, read-and-acknowledge tracking, or automatic supersession). Sub-module 12.1 builds this foundational QMS document spine.

### Spine entities verified to EXIST (grep evidence)

| Claim | Evidence | Note |
|---|---|---|
| `core.Tenant` exists | `apps/core/models/Tenant.py:17` → `class Tenant(models.Model)` | Multi-tenant isolation foundation. |
| `core.OrgUnit` exists | `apps/core/models/OrgUnit.py:5` → `class OrgUnit(models.Model)` | Target department / plant / quality unit ownership. |
| `core.Party` & `PartyRole` exist | `apps/core/models/Party.py:5`, `PartyRole.py:5` | Unified party spine. |
| `core.Document` exists | `apps/core/models/Document.py:5` → `class Document(models.Model)` with `file = FileField(...)`, `classification`, `version` | Generic file attachment spine with GenericForeignKey. Controlled quality documents can attach physical files directly or link to `core.Document`. |
| `core.AuditLog` exists | `apps/core/models/AuditLog.py:5` + `apps/core/utils.py` `write_audit_log` helper | General tenant audit trail. |
| `core.NumberingScheme` exists | `apps/core/models/NumberingScheme.py:15` → `prefix` + `unique_together ("tenant", "prefix")` | Autonumbering schema registry. |
| `accounts.User` exists | `apps/accounts/models.py:52` → `class User(AbstractBaseUser, PermissionsMixin)` | Auth user model for authors, reviewers, approvers, signers, and trainees. |
| `hrm.EmployeeProfile` exists | `apps/hrm/models/EmployeeManagement/EmployeeProfiles.py:8` → `class EmployeeProfile(TenantNumbered)` | Links read-and-acknowledge sign-offs to formal personnel records. |

### Spine entities verified NOT to exist

- **No QMS Document Control tables anywhere:** Grep across all apps confirms zero existing models for controlled documents, document change orders, or GxP signature manifests.
- **No Document Management System (DMS) app yet:** Module 13 DMS is roadmap. Note the strict boundary: Module 13 DMS is general enterprise collaboration (unstructured files, shared drives, office templates), whereas Module 12.1 is strictly **Regulated Quality Document Control** (SOPs, policies, 21 CFR Part 11, ISO 9001/ISO 13485 compliance).

### Candidate prefix collision check (repo-wide automated verification)

Automated script scanned all `NUMBER_PREFIX` declarations across the codebase:
- `QDOC` (Quality Controlled Document) → **0 collisions** (Completely free)
- `QDCR` (Quality Document Change Request / Order) → **0 collisions** (Completely free)
- `QSIG` (Quality Electronic Signature Record) → **0 collisions** (Completely free)
- `QACK` (Quality Read & Acknowledgment) → **0 collisions** (Completely free)
*(Note: `CR` collided with SCM Contract Compliance, `ECN` collided with Sales Enablement, `ADOC` in Assets, `EDOC` in HRM, `PDOC` in Procurement. The chosen prefixes `QDOC`, `QDCR`, `QSIG`, `QACK` have zero collisions).*

---

## Leaders surveyed (with source links)

1. **MasterControl (Document Control)** — The recognized market gold standard in life sciences and regulated manufacturing QMS. Automates the end-to-end controlled document lifecycle (Draft → In Review → Pending Approval → Effective → Superseded → Obsolete). Provides 21 CFR Part 11 compliant electronic signatures with manifest details (printed name, timestamp, meaning of signature), dual-authentication re-entry, dynamic lifecycle watermarking, automatic supersession of prior revisions, periodic review scheduling, and automated training triggers on release.
   - *Source:* https://www.mastercontrol.com/document-control/ · https://www.mastercontrol.com/gxp-lifeline/21-cfr-part-11-compliance/
2. **Veeva Vault QMS / QualityDocs** — Enterprise cloud life sciences leader. Features formal document lifecycles with strict state-based security (restricting read access to superseded/obsolete documents to prevent operational misuse), Multi-Document Change Control (DCC) and Document Change Requests (DCR) linking multiple affected documents to a single change record with justification and impact analysis, automated Periodic Review scheduling jobs and workflow envelopes, and audit-ready version trees.
   - *Source:* https://www.veeva.com/products/vault-qualitydocs/ · https://veevavault.help/en/lr/48102/
3. **Qualio (eQMS Document Management)** — Modern agile eQMS built for medical device and biotech startups/scaleups. Streamlines collaborative authoring, multi-tier approvals, and electronic signatures. Its signature capability is the instant automated "Read-and-Acknowledge" training trigger upon document effective date, complete with real-time completion dashboards, overdue tracking, and audit trail generation for FDA/ISO inspections.
   - *Source:* https://www.qualio.com/product/document-management
4. **Greenlight Guru (Medical Device Document Management)** — Purpose-built QMS for medical devices (FDA 21 CFR 820, ISO 13485). Provides structured Document Change Order (DCO) workspaces with end-to-end traceability, change summaries (what changed, why, who requested it), multi-tier approval routing across engineering, quality, and manufacturing, 21 CFR Part 11 e-signatures, automated obsolescence of superseded revisions, and downstream training triggers.
   - *Source:* https://www.greenlight.guru/document-management-software
5. **ETQ Reliance (Document Control)** — Enterprise quality management platform (part of Hexagon). Emphasizes lifecycle watermarking (dynamically stamping "DRAFT", "IN REVIEW", "EFFECTIVE", "OBSOLETE" based on status) and strict print control to combat "shadow paper systems" (tracking authorized printed copies, serial copy numbers, and marking printouts as "CONTROLLED COPY" vs "UNCONTROLLED COPY IF PRINTED").
   - *Source:* https://www.etq.com/document-control/
6. **TrackWise Digital / Sparta Systems (Quality Document Management)** — Cloud EQMS on Salesforce (Honeywell). Integrates closed-loop Document Management with Change Control: change requests initiate document revision workflows with impact assessments, parallel electronic reviews, automated distribution of effective procedures, and mandatory training record assignments.
   - *Source:* https://www.spartasystems.com/trackwise-digital/document-management/
7. **Arena QMS & PLM (PTC)** — High-tech, electronics, and medtech PLM/QMS leader. Establishes the clear architectural distinction between Document Change Orders (DCO) for procedural/quality documentation (SOPs, policies, work instructions, test protocols) versus Engineering Change Orders (ECO) for physical parts/BOMs. Enforces Change Control Board (CCB) review, side-by-side revision redlining, version promotion, and instant obsolescence.
   - *Source:* https://www.arenasolutions.com/products/qms/document-management/
8. **Dot Compliance (Ready-to-use eQMS on Salesforce)** — Life sciences eQMS offering out-of-the-box pre-configured document lifecycles, 21 CFR Part 11 / EU Annex 11 electronic signatures with intent selection, tamper-evident audit trails with mandatory reason-for-change logging, and seamless pairing of document release with employee training sign-offs.
   - *Source:* https://www.dotcompliance.com/solutions/document-management/

---

## Feature catalog (this sub-module only)

### Bullet 1 — Document Creation & Authoring (Template libraries, controlled formats, version stamping)

- **Controlled Document Classification & Types** — Categorizes documents into standardized quality tiers: SOP (Standard Operating Procedure), WI (Work Instruction), POL (Policy), QM (Quality Manual), SPEC (Specification), FORM (Form/Template), REC (Quality Record), PROTOCOL (Validation Protocol/Plan). · seen in: MasterControl, Veeva Vault, Greenlight Guru · priority: **table-stakes** · spine: new model `ControlledDocument` choice field · **buildable now**
- **Controlled Document Numbering & Revision Stamping** — Major/minor semantic versioning (e.g. Rev 1.0, 1.1, 2.0 or Rev A, B, C) decoupled from the immutable system sequence number (`QDOC-#####`). · seen in: All leaders · priority: **table-stakes** · spine: new model `ControlledDocument` (`number` + `revision` + `is_latest_revision`) · **buildable now**
- **Pre-Approved Quality Template Library** — Ability to flag a controlled document as a reusable template/form (`document_type="FORM"` or `"TEMPLATE"`) that authors instantiate when creating new procedures or records. · seen in: MasterControl, Dot Compliance · priority: **common** · spine: `ControlledDocument` (`is_template` boolean flag) · **buildable now**
- **Department & Ownership Scoping** — Assigns document ownership to a specific author (`accounts.User`) and organizational department (`core.OrgUnit`). · seen in: Veeva Vault, ETQ Reliance · priority: **table-stakes** · spine: FK `accounts.User` + FK `core.OrgUnit` · **buildable now**
- **Document Confidentiality & Security Tiering** — Explicit data classification (Public, Internal, Confidential, Restricted/Restricted GxP). · seen in: Dot Compliance, MasterControl · priority: **common** · spine: `ControlledDocument.classification` choice field · **buildable now**
- **Controlled File Repository / Attachment** — Secure file upload for the controlled document payload (PDF, DOCX) with file checksum/size verification. · seen in: All leaders · priority: **table-stakes** · spine: `models.FileField` on `ControlledDocument` · **buildable now**

### Bullet 2 — Review & Approval Workflows (Multi-tier routing, electronic signatures 21 CFR Part 11, approval audit trails)

- **Structured Lifecycle State Machine** — Explicit quality document lifecycle states: `draft` → `in_review` → `pending_approval` → `approved` → `effective` → `superseded` → `obsolete` → `archived`. · seen in: Veeva Vault, MasterControl, Arena QMS · priority: **table-stakes** · spine: `ControlledDocument.lifecycle_state` choices · **buildable now**
- **Multi-Tier Routing (Author, Reviewer, Approver)** — Configurable review and approval chain with separate stages for technical review, quality assurance review, and department head approval. · seen in: Greenlight Guru, TrackWise Digital · priority: **table-stakes** · spine: `ControlledDocument` / `DocumentChangeOrder` reviewer/approver assignment fields · **buildable now**
- **21 CFR Part 11 Electronic Signature Manifest (§ 11.50)** — Immutable signature record capturing: (1) printed legal name of signer, (2) exact date/time, (3) meaning of signature (`authored`, `reviewed`, `technical_approval`, `quality_approval`, `management_approval`, `acknowledgment`), and (4) cryptographic SHA-256 digest linking the signature inextricably to the document version and signer. · seen in: MasterControl, Veeva Vault, Qualio, Greenlight Guru, Dot Compliance · priority: **table-stakes (regulated requirement)** · spine: **new model `ElectronicSignatureRecord`** · **buildable now**
- **Dual-Credential Password Re-Authentication (§ 11.200)** — Prompts user to re-enter their login password upon executing an electronic signature action to satisfy non-repudiation. · seen in: MasterControl, Greenlight Guru, Dot Compliance · priority: **table-stakes** · spine: Django view auth check (`user.check_password(password)`) · **buildable now**
- **Review Decision & Comment Log** — Structured capture of review outcomes (`approved`, `rejected`, `changes_requested`) with mandatory rationale. · seen in: All leaders · priority: **table-stakes** · spine: `ElectronicSignatureRecord.comments` / `DocumentChangeOrder.closure_notes` + `core.AuditLog` · **buildable now**

### Bullet 3 — Document Distribution & Obsolescence (Controlled issuance, read-and-acknowledge tracking, automatic supersession)

- **Effective Date Scheduling & Enactment** — Documents do not become active immediately upon approval; they go live on a specified `effective_date` to allow for employee training and operational transition. · seen in: MasterControl, Veeva Vault, Qualio · priority: **table-stakes** · spine: `ControlledDocument.effective_date` + status transition logic · **buildable now**
- **Automatic Supersession & Obsolescence** — When Revision B becomes `effective`, Revision A is automatically transitioned to `superseded`, its `is_latest_revision` flag set to False, and forward/backward pointers linked (`supersedes` / `superseded_by`). Old versions are quarantined from active operational views. · seen in: Veeva Vault, Greenlight Guru, Arena QMS · priority: **table-stakes** · spine: `ControlledDocument.superseded_by` FK to `self` + `ControlledDocument.supersedes` FK to `self` · **buildable now**
- **Read-and-Acknowledge Training Tracking** — Automatic generation of acknowledgment tasks for affected employees when a new or revised SOP becomes effective, requiring them to confirm comprehension ("I have read, understood, and agree to adhere to this procedure"). · seen in: Qualio, MasterControl, Greenlight Guru, Dot Compliance · priority: **table-stakes** · spine: **new model `DocumentAcknowledgment`** FK to `ControlledDocument` and `accounts.User` / `hrm.EmployeeProfile` · **buildable now**
- **Acknowledgment Compliance & Overdue Monitoring** — Dashboard view tracking percentage of employees who have acknowledged effective SOPs, highlighting overdue pending sign-offs. · seen in: Qualio, Dot Compliance · priority: **common** · spine: `DocumentAcknowledgment.status` (`pending`, `acknowledged`, `overdue`, `waived`) with due date comparison · **buildable now**
- **Dynamic Lifecycle Watermarking & Controlled Stamp** — Dynamically indicates document status ("DRAFT", "IN REVIEW", "EFFECTIVE - CONTROLLED COPY", "OBSOLETE - DO NOT USE", "UNCONTROLLED IF PRINTED") based on its current lifecycle state. · seen in: ETQ Reliance, MasterControl · priority: **common** · spine: `ControlledDocument.watermark_text` property / view badge · **buildable now**

### Bullet 4 — Change Request & Revision Control (DCO / ECN, impact assessment, controlled re-release)

- **Document Change Order (DCO / DCR)** — First-class change authorization object governing all additions, revisions, and retirements of controlled documents. · seen in: Arena QMS (DCO), Greenlight Guru (DCO), Veeva Vault (DCC) · priority: **table-stakes** · spine: **new model `DocumentChangeOrder`** (`NUMBER_PREFIX = "QDCR"`) · **buildable now**
- **Mandatory Reason for Change & Description** — Captures regulatory justification for the proposed modification. · seen in: All leaders · priority: **table-stakes** · spine: `DocumentChangeOrder.reason_for_change` + `change_description` · **buildable now**
- **Multidimensional Impact Assessment** — Structured risk and scope evaluation covering regulatory impact (triggers FDA/ISO filing?), training impact (requires employee retraining?), equipment/process impact, and customer impact. · seen in: MasterControl, Greenlight Guru, TrackWise Digital · priority: **table-stakes** · spine: `DocumentChangeOrder` fields (`regulatory_impact`, `training_required`, `impact_assessment`) · **buildable now**
- **Change Control Board (CCB) Approval Routing** — Formal submission, CCB review, decision capture (`pending`, `approved`, `rejected`), and closure sign-off before a revision can be released. · seen in: Arena QMS, Greenlight Guru · priority: **common** · spine: `DocumentChangeOrder.ccb_decision` + `ccb_decision_date` · **buildable now**
- **Change Types & Emergency Bypass** — Categorizes changes into `new_document`, `major_revision`, `minor_revision`, `obsoletion`, and `emergency_change` (with mandatory post-change full review gate). · seen in: MasterControl, TrackWise Digital · priority: **common** · spine: `DocumentChangeOrder.change_type` choices · **buildable now**

### Bullet 5 — Archive & Retrieval (Long-term retention, secure vaulting, rapid search with metadata)

- **Retention Policy & Archival Timers** — Enforces regulatory retention periods (e.g. 5, 10, 25 years or "life of device + 2 years" per 21 CFR 820) before disposal. · seen in: MasterControl, Veeva Vault · priority: **table-stakes** · spine: `ControlledDocument.retention_years` + `archived_at` · **buildable now**
- **Secure Obsolete Vaulting** — Filters obsolete and superseded documents out of daily operational search results, keeping them accessible only to Quality Assurance / Document Control roles in a dedicated Archive Vault. · seen in: Veeva Vault, ETQ Reliance · priority: **table-stakes** · spine: QuerySet filter on `lifecycle_state__in=["superseded", "obsolete", "archived"]` · **buildable now**
- **Multi-Attribute Filter & Full Metadata Indexing** — Fast search by document number, title, document type, department, lifecycle state, owner, revision, and effective date range. · seen in: All leaders · priority: **table-stakes** · spine: Standard NavERP list view filters + Q search · **buildable now**
- **Inspection-Ready Audit Trail History Dossier** — Assembles all historical revisions, change orders, electronic signatures, and acknowledgment records into a single consolidated audit view for external regulatory inspectors. · seen in: MasterControl, Dot Compliance, Qualio · priority: **differentiator** · spine: Detail view aggregating `ControlledDocument` + `DocumentChangeOrder` + `ElectronicSignatureRecord` + `DocumentAcknowledgment` · **buildable now**

---

## Recommended build scope (this pass — 1–4 models)

Following NavERP's strict Module Creation Sequence guidelines, Sub-module 12.1 is built using **4 tenant-scoped models** that form the complete, end-to-end quality document control spine:

### 1. `ControlledDocument` [NUMBER_PREFIX = "QDOC"]
- **Role:** Master record for any controlled quality procedure, policy, instruction, or specification, tracking its version lifecycle, effective status, periodic review, and supersession hierarchy.
- **Fields:**
  - `tenant` (FK `core.Tenant`, on_delete=CASCADE)
  - `number` (CharField, max_length=20, auto-numbered e.g. `QDOC-00001`)
  - `title` (CharField, max_length=255)
  - `document_type` (CharField, choices: `sop`="SOP", `wi`="Work Instruction", `policy`="Policy", `manual`="Quality Manual", `spec`="Specification", `form`="Form/Template", `protocol`="Protocol/Plan", `record`="Quality Record")
  - `department` (FK `core.OrgUnit`, on_delete=SET_NULL, null=True, blank=True)
  - `owner` (FK `accounts.User`, on_delete=PROTECT, related_name="owned_quality_documents")
  - `revision` (CharField, max_length=20, default="1.0" — e.g. "1.0", "2.0", "A", "B")
  - `is_latest_revision` (BooleanField, default=True, db_index=True)
  - `lifecycle_state` (CharField, max_length=25, choices: `draft`="Draft", `in_review`="In Review", `pending_approval`="Pending Approval", `approved`="Approved", `effective`="Effective", `superseded`="Superseded", `obsolete`="Obsolete", `archived`="Archived", default="draft", db_index=True)
  - `classification` (CharField, max_length=20, choices: `public`="Public", `internal`="Internal", `confidential`="Confidential", `restricted`="Restricted GxP", default="internal")
  - `file` (FileField, upload_to="quality/documents/%Y/%m/", blank=True, null=True)
  - `description` (TextField, blank=True)
  - `change_summary` (TextField, blank=True, help_text="Summary of changes in this revision")
  - `effective_date` (DateField, null=True, blank=True)
  - `review_interval_months` (PositiveIntegerField, default=12, help_text="Periodic review interval in months")
  - `next_review_date` (DateField, null=True, blank=True)
  - `retention_years` (PositiveIntegerField, default=10, help_text="Archival retention period in years")
  - `supersedes` (ForeignKey to self, on_delete=SET_NULL, null=True, blank=True, related_name="superseded_by_set")
  - `superseded_by` (ForeignKey to self, on_delete=SET_NULL, null=True, blank=True, related_name="supersedes_set")
  - `is_template` (BooleanField, default=False, help_text="Whether this document acts as an approved master template/form")
  - `archived_at` (DateTimeField, null=True, blank=True)
  - `created_at`, `updated_at` (from `TenantNumbered`)
- **Key Methods / Properties:**
  - `watermark`: Dynamic status string ("DRAFT", "EFFECTIVE - CONTROLLED COPY", "SUPERSEDED", "OBSOLETE").
  - `is_effective`: Returns True if state is `effective` and `effective_date` <= today.
  - `is_overdue_review`: Returns True if `next_review_date` is past.

### 2. `DocumentChangeOrder` [NUMBER_PREFIX = "QDCR"]
- **Role:** Formal Change Request / Change Order (DCO/ECN) authorizing the creation, revision, or obsolescence of controlled documents, with justification, impact analysis, and CCB approval gates.
- **Fields:**
  - `tenant` (FK `core.Tenant`, on_delete=CASCADE)
  - `number` (CharField, max_length=20, auto-numbered e.g. `QDCR-00001`)
  - `title` (CharField, max_length=255)
  - `target_document` (FK `ControlledDocument`, on_delete=CASCADE, related_name="change_orders")
  - `change_type` (CharField, max_length=25, choices: `new_document`="New Document", `major_revision`="Major Revision", `minor_revision`="Minor Revision", `obsoletion`="Obsoletion / Retirement", `emergency_change`="Emergency Change", default="major_revision")
  - `status` (CharField, max_length=25, choices: `draft`="Draft", `submitted`="Submitted for Review", `in_review`="In Review", `ccb_review`="CCB Review", `approved`="Approved", `rejected`="Rejected", `implemented`="Implemented", `closed`="Closed", `cancelled`="Cancelled", default="draft", db_index=True)
  - `reason_for_change` (TextField, help_text="21 CFR Part 11 / ISO justification for change")
  - `change_description` (TextField, help_text="Detailed description of proposed edits")
  - `impact_assessment` (TextField, blank=True, help_text="Analysis of impact on product quality, safety, validation, and regulatory filings")
  - `regulatory_impact` (BooleanField, default=False, help_text="Requires regulatory notification or license amendment")
  - `training_required` (BooleanField, default=True, help_text="Requires employee read-and-acknowledge training before/upon effective date")
  - `requested_by` (FK `accounts.User`, on_delete=PROTECT, related_name="requested_change_orders")
  - `proposed_effective_date` (DateField, null=True, blank=True)
  - `ccb_decision` (CharField, max_length=20, choices: `pending`="Pending Decision", `approved`="Approved", `rejected`="Rejected", `more_info`="More Info Requested", default="pending")
  - `ccb_decision_date` (DateTimeField, null=True, blank=True)
  - `ccb_approver` (FK `accounts.User`, on_delete=SET_NULL, null=True, blank=True, related_name="ccb_approved_orders")
  - `closure_notes` (TextField, blank=True)
  - `closed_at` (DateTimeField, null=True, blank=True)
  - `created_at`, `updated_at` (from `TenantNumbered`)

### 3. `ElectronicSignatureRecord` [NUMBER_PREFIX = "QSIG"]
- **Role:** 21 CFR Part 11 compliant electronic signature manifest inextricably linking the authenticated signer, their legal identity, role/meaning, timestamp, and cryptographic hash to a controlled document or change order.
- **Fields:**
  - `tenant` (FK `core.Tenant`, on_delete=CASCADE)
  - `number` (CharField, max_length=20, auto-numbered e.g. `QSIG-00001`)
  - `document` (FK `ControlledDocument`, on_delete=CASCADE, null=True, blank=True, related_name="signatures")
  - `change_order` (FK `DocumentChangeOrder`, on_delete=CASCADE, null=True, blank=True, related_name="signatures")
  - `signer` (FK `accounts.User`, on_delete=PROTECT, related_name="quality_signatures")
  - `signer_name` (CharField, max_length=150, help_text="Printed legal name of the signer at signing time")
  - `signer_title` (CharField, max_length=100, blank=True, help_text="Job title or role of signer")
  - `meaning_of_signature` (CharField, max_length=30, choices: `authored`="Author / Originator", `reviewed`="Technical Review", `quality_approval`="Quality Assurance Approval", `management_approval`="Management Approval", `ccb_approval`="Change Control Board Approval", `acknowledgment`="Read & Understood Acknowledgment")
  - `signature_timestamp` (DateTimeField, auto_now_add=True, editable=False)
  - `ip_address` (GenericIPAddressField, null=True, blank=True)
  - `user_agent` (CharField, max_length=255, blank=True)
  - `signature_hash` (CharField, max_length=64, editable=False, help_text="SHA-256 cryptographic digest binding signer, timestamp, meaning, and record")
  - `comments` (TextField, blank=True)
- **Key Method:**
  - Generates immutable SHA-256 digest on `save()` combining `tenant_id`, `signer_id`, `meaning_of_signature`, `signature_timestamp`, and target record PK.

### 4. `DocumentAcknowledgment` [NUMBER_PREFIX = "QACK"]
- **Role:** Read-and-Acknowledge distribution tracking ensuring employees review, understand, and formally sign off on newly released or revised procedures prior to or upon their effective date.
- **Fields:**
  - `tenant` (FK `core.Tenant`, on_delete=CASCADE)
  - `number` (CharField, max_length=20, auto-numbered e.g. `QACK-00001`)
  - `document` (FK `ControlledDocument`, on_delete=CASCADE, related_name="acknowledgments")
  - `user` (FK `accounts.User`, on_delete=PROTECT, related_name="quality_acknowledgments")
  - `employee_profile` (FK `hrm.EmployeeProfile`, on_delete=SET_NULL, null=True, blank=True, related_name="document_acknowledgments")
  - `status` (CharField, max_length=20, choices: `pending`="Pending Read & Sign", `acknowledged`="Acknowledged & Understood", `overdue`="Overdue", `waived`="Waived", default="pending", db_index=True)
  - `assigned_date` (DateField, auto_now_add=True)
  - `due_date` (DateField)
  - `acknowledged_at` (DateTimeField, null=True, blank=True)
  - `comprehension_confirmed` (BooleanField, default=False, help_text="Affirmation: I have read, understood, and agree to follow this procedure")
  - `comments` (TextField, blank=True)
  - `created_at`, `updated_at` (from `TenantNumbered`)
- **Key Property:**
  - `is_overdue`: Returns True if `status == "pending"` and `due_date < timezone.now().date()`.

---

## Belongs to sibling sub-modules (parked, not scoped here)

The following capabilities belong to sibling sub-modules in Module 12 or related modules and are intentionally parked:

- **12.2 Design Controls & Development:** Design History File (DHF), design inputs/outputs, design verification & validation protocols, design transfer documentation.
- **12.3 Risk Management (ISO 14971 / FMEA):** Failure Mode and Effects Analysis (FMEA), hazard analysis, Risk Priority Numbers (RPN), risk mitigations.
- **12.4 Corrective & Preventive Action (CAPA):** CAPA issue detection, 5 Whys / Fishbone Root Cause Analysis (RCA), corrective action plans, effectiveness verification checks.
- **12.5 Non-Conformance & Deviation Management (NCR):** Material segregation, quarantine hold triggers, Material Review Board (MRB) disposition workflows (rework, scrap, return-to-vendor).
- **12.6 Supplier & Vendor Quality Management:** Approved Vendor List (AVL), supplier qualification audits, Supplier Corrective Action Requests (SCAR), supplier scorecards.
- **12.7–12.9 Inspection Controls (IQC, IPQC, FQC):** ANSI/ASQ Z1.4 sampling plans, Certificate of Analysis (CoA) verification, Statistical Process Control (SPC) inspection logs.
- **12.11 Audit Management:** Quality audit checklists, internal/external audit schedules, audit findings, and compliance reporting.
- **12.12 Training & Competency Management:** Full employee training matrix, job-role curricula, competency tests, LMS integration (Sub-module 12.1 only tracks the immediate procedure **Read-and-Acknowledge** sign-off).
- **Module 13 Document Management System (DMS):** General enterprise file storage, rich-text cloud document authoring, folder hierarchies, and marketing/sales asset storage.

---

## Deferred (later passes / integrations)

The following advanced integrations are identified in market leaders but deferred from this initial 12.1 pass to keep scope tight and reliable:

- **Real-Time Web Collaborative Redlining:** Live concurrent editing inside Microsoft Office 365 or Google Workspace iframes (leaders like Arena and TrackWise integrate this, but NavERP operates cleanly with controlled file uploads and structured revision summaries).
- **Hardware PKI / X.509 Cryptographic Token Integration:** Digital certificates stored on smart cards or USB crypto keys (satisfactorily fulfilled via FDA 21 CFR Part 11 compliant password re-authentication + SHA-256 signature manifests).
- **Automated In-Flight PDF Dynamic Watermarking Engine:** Server-side PDF binary manipulation inserting diagonal "CONTROLLED COPY" or "OBSOLETE" watermarks upon file download (deferred to an asynchronous PDF worker pass; current pass implements UI lifecycle badges and clear metadata watermarking).
- **Automated Periodic Review Email Escalation Celery Tasks:** Background cron jobs sending reminder emails 30 days prior to `next_review_date` (deferred until 0.20 Job Scheduler is wired; documented as an operator-driven review status).
- **Barcoding / QR Code Printing on Controlled Copies:** Stamping unique 2D barcodes on physical printouts for barcode-scanner shop floor reconciliation.
