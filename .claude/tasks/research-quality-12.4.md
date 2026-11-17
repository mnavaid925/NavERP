# Research — Sub-module 12.4: Corrective & Preventive Action (CAPA) (Module 12 — Quality Management System, `quality`)

## Repo state checked first

- **`LIVE_LINKS` built in Module 12 so far (`apps/core/navigation.py`):**
  - `"12.1"` (Document Control & Management):
    - `"Document Creation & Authoring": "quality:controlled_document_list"`
    - `"Review & Approval Workflows": "quality:electronic_signature_list"`
    - `"Document Distribution & Obsolescence": "quality:document_acknowledgment_list"`
    - `"Change Request & Revision Control": "quality:document_change_order_list"`
    - `"Archive & Retrieval": "quality:document_archive_vault"`
  - `"12.2"` (Design Controls & Development):
    - `"Design Planning & Inputs": "quality:design_project_list"`
    - `"Design Reviews & Verification": "quality:design_review_list"`
    - `"Design Validation & Transfer": "quality:design_verification_list"`
    - `"Design History File (DHF)": "quality:traceability_matrix"`
    - `"Design Changes & Configuration Management": "quality:design_input_list"`
  - `"12.3"` (Risk Management / ISO 14971):
    - `"Hazard Identification & Analysis": "quality:risk_assessment_list"`
    - `"Risk Evaluation & Scoring": "quality:fmea_matrix"`
    - `"Risk Control & Mitigation": "quality:risk_control_measure_list"`
    - `"Residual Risk Assessment": "quality:risk_traceability_matrix"`
    - `"Risk Management File & Reporting": "quality:risk_management_plan_list"`
  - **`12.4` is the fourth sub-module of Module 12.**

- **Sibling models available to FK in `apps/quality/models/`:**
  - `ControlledDocument` (`apps/quality/models/DocumentControl/ControlledDocuments.py`, prefix `QDOC`): Standard operating procedures, work instructions, and inspection specifications updated as part of CAPA corrective actions.
  - `DocumentChangeOrder` (`apps/quality/models/DocumentControl/DocumentChangeOrders.py`, prefix `QDCR`): Formal engineering/process change control requests initiated from CAPA action plans.
  - `ElectronicSignatureRecord` (`apps/quality/models/DocumentControl/ElectronicSignatures.py`, prefix `QSIG`): 21 CFR Part 11 compliant digital signatures for CAPA approval, effectiveness sign-off, and formal closure.
  - `DocumentAcknowledgment` (`apps/quality/models/DocumentControl/DocumentAcknowledgments.py`, prefix `QACK`): Employee read-and-understand sign-offs for modified procedures.
  - `DesignProject` (`apps/quality/models/DesignControls/DesignProjects.py`, prefix `QDPL`): Master medical device/system design project.
  - `DesignInput` (`apps/quality/models/DesignControls/DesignInputs.py`, prefix `QINP`): Design requirements updated if CAPA uncovers design flaws.
  - `DesignVerification` (`apps/quality/models/DesignControls/DesignVerifications.py`, prefix `QVER`): Verification protocols proving remediation effectiveness.
  - `RiskManagementPlan` (`apps/quality/models/RiskManagement/RiskManagementPlans.py`, prefix `QRMP`): Product risk plan updated when new failure modes/hazards are identified.
  - `RiskAssessment` (`apps/quality/models/RiskManagement/RiskAssessments.py`, prefix `QRSK`): Specific hazard/FMEA failure mode linked to CAPA as originating root cause or post-mitigation review.
  - `RiskControlMeasure` (`apps/quality/models/RiskManagement/RiskControlMeasures.py`, prefix `QRCM`): Mitigations evaluated or implemented through CAPA actions.

- **Base classes in `apps/quality/models/_base.py`:**
  - `TenantOwned`: Multi-tenant isolation (`tenant`, `created_at`, `updated_at`).
  - `TenantNumbered`: Autonumbering base class with `next_number(type(self), self.tenant, self.NUMBER_PREFIX)` and atomic collision retry loop.

### Spine entities verified to EXIST (grep evidence)

| Claim | Evidence | Note |
|---|---|---|
| `core.Tenant` exists | `apps/core/models/Tenant.py:17` -> `class Tenant(models.Model)` | Multi-tenant isolation foundation. |
| `core.OrgUnit` exists | `apps/core/models/OrgUnit.py:5` -> `class OrgUnit(models.Model)` | Department, plant, quality unit, or manufacturing cell ownership. |
| `core.Party` & `PartyRole` exist | `apps/core/models/Party.py:5`, `PartyRole.py:5` | Unified party spine for owners, investigators, verifiers, and approvers. |
| `core.AuditLog` exists | `apps/core/models/AuditLog.py:5` + `write_audit_log` helper | Immutable tenant audit logging for CAPA lifecycle state transitions. |
| `core.NumberingScheme` exists | `apps/core/models/NumberingScheme.py:15` | Scheme prefix allocation registry. |
| `accounts.User` exists | `apps/accounts/models.py:52` -> `class User(AbstractBaseUser, PermissionsMixin)` | System users for authentication, assignment, and e-signatures. |
| `quality.ControlledDocument` exists | `apps/quality/models/DocumentControl/ControlledDocuments.py:8` | Linked to corrective actions requiring SOP / WI updates. |
| `quality.DocumentChangeOrder` exists | `apps/quality/models/DocumentControl/DocumentChangeOrders.py:8` | Linked to CAPA actions requiring formal engineering change orders. |
| `quality.ElectronicSignatureRecord` exists | `apps/quality/models/DocumentControl/ElectronicSignatures.py:10` | Formal 21 CFR Part 11 sign-off for CAPA plan and closure. |
| `quality.RiskAssessment` exists | `apps/quality/models/RiskManagement/RiskAssessments.py:8` | Linked to originating risk assessments and post-market safety feedback. |
| `quality.DesignProject` exists | `apps/quality/models/DesignControls/DesignProjects.py:8` | Linked to design-related CAPAs requiring DHF / Design Input remediation. |

### Spine entities verified NOT to exist (or unbuilt in Module 12)

- **Module 12 later feeder sub-modules (not built yet):**
  - Sub-module 12.5 Non-Conformance & Deviation Management (`apps/quality` has no NCR/Deviation models yet).
  - Sub-module 12.6 Supplier Quality Management (`apps/quality` has no SCAR models yet).
  - Sub-module 12.11 Quality Audits (`apps/quality` has no audit models yet).
  - Sub-module 12.13 Customer Complaints (`apps/quality` has no complaint models yet).
  - *Architecture Note:* While SCM 4.9 has `apps/scm/models/QualityManagement/CapaActions.py` (prefix `CAPA`), that is an operational supply chain / supplier floor action record. Sub-module 12.4 builds the regulatory, enterprise-wide Quality System CAPA spine governed by ISO 13485:2016 §8.5.2/8.5.3, 21 CFR 820.100 (QMSR), and ISO 9001:2015 §10.2. To avoid premature coupling to unbuilt 12.5/12.11/12.13 sub-modules, 12.4 uses a flexible polymorphic/tagged issue source model (`source_type`, `source_reference`, `source_description`) with optional FK hooks to existing records (`apps.scm.NonConformance`, `apps.scm.QualityAudit`, `quality.RiskAssessment`, `quality.DesignProject`).
- **Module 5 unbuilt masters:** `Item`, `LotSerial`, `UOM` are not built yet. CAPA records use free-text product/part identifiers (`affected_item_code`, `affected_item_name`, `affected_lot_numbers`) with future migration path to Module 5.

### Candidate prefix collision check (repo-wide automated verification)

Automated ripgrep scan across all `NUMBER_PREFIX` declarations in `apps/`:
- `QCAP` (Quality CAPA Investigation / Plan) -> **0 collisions** (Completely free)
- `QRCA` (Quality Root Cause Analysis) -> **0 collisions** (Completely free)
- `QACT` (Quality CAPA Action Item) -> **0 collisions** (Completely free)
- `QEFF` (Quality CAPA Effectiveness Review) -> **0 collisions** (Completely free)

---

## Leaders surveyed (with source links)

1. **MasterControl (CAPA / Quality Excellence)** — Enterprise life sciences eQMS market leader for 21 CFR Part 820.100 and ISO 13485 compliance. Provides an automated, closed-loop CAPA lifecycle: direct intake from complaints/deviations/audits, risk-based triage, guided root cause investigation workspaces, integrated corrective/preventive action execution with cross-module change control triggers, and enforced time-delayed effectiveness checks that prevent premature closure.
   - *Source:* https://www.mastercontrol.com/capa/ · https://www.mastercontrol.com/gxp-lifeline/21-cfr-part-820-capa-requirements/
2. **Greenlight Guru (Medical Device CAPA Software)** — Premier medical device quality platform purpose-built for FDA 21 CFR 820 / QMSR and ISO 13485:2016. Connects CAPA directly into a living digital thread: links originating quality events (nonconformances, customer complaints, audits) to design controls (DHF), risk management files (ISO 14971), and document revisions. Enforces strict containment steps, systematic 5 Whys / Fishbone RCA, multi-task action assignment, and evidence-backed verification of effectiveness before closure.
   - *Source:* https://www.greenlight.guru/capa-software · https://www.greenlight.guru/blog/capa-medical-devices
3. **Veeva Vault Quality / QMS (CAPA & Quality Events)** — Cloud-native enterprise pharma and MedTech platform. Features integrated Quality Event intake, dedicated interactive 5 Whys cause-and-effect tree modeling, automated Root Cause record creation, cross-functional CAPA action assignment with automated escalation workflows, and automated Effectiveness Check scheduling with objective metric validation before formal regulatory closure.
   - *Source:* https://www.veeva.com/products/vault-qms/ · https://veevavault.help/en/lr/132104/
4. **Sparta Systems TrackWise / TrackWise Digital (CAPA Management)** — Industrial-grade enterprise QMS leader (now part of Honeywell). Delivers end-to-end CAPA tracking with business rules engines, drill-down root cause taxonomy codes, multi-owner corrective/preventive action planning, change control / training integration, automated management review escalations, and mandatory effectiveness verification loops with automated re-opening if recurrence is detected.
   - *Source:* https://www.spartasystems.com/trackwise-digital/capa/
5. **ETQ Reliance (CAPA Software System)** — Top-tier enterprise QMS platform supporting ISO 9001, ISO 13485, and IATF 16949. Unifies issue logging from nonconformances, audits, and customer feedback. Embeds root cause toolkits (5 Whys, Ishikawa 6M Fishbone, Fault Tree Analysis), tracks multi-department action plans with overdue escalation timers, and schedules future-dated effectiveness verification gates (30/60/90 days) requiring statistical proof of recurrence elimination.
   - *Source:* https://www.etq.com/capa-software/ · https://www.qualitymag.com/articles/94276-etq-reliance-capa
6. **Qualio (Life Science eQMS CAPA)** — Modern cloud quality platform for biotech and medical device scale-ups. Streamlines event triage, risk-based CAPA escalation, immediate containment holds, guided 5-Why investigation steps, action item task assignment, and scheduled verification waiting periods to validate that corrective actions sustained defect eradication.
   - *Source:* https://www.qualio.com/product/capa-software · https://www.qualio.com/product/non-conformance-management
7. **Dot Compliance (eQMS CAPA Management)** — Ready-to-use life sciences eQMS built on Salesforce. Emphasizes root cause categorization beyond "human error", structured 8D and 5 Whys investigation templates, automated action tracking, and strict effectiveness check gates that prevent CAPA sign-off until objective performance metrics confirm non-recurrence.
   - *Source:* https://www.dotcompliance.com/solutions/capa-software/
8. **QT9 QMS (CAPA Management Module)** — Comprehensive ISO and FDA compliance suite. Features centralized CAPA logging with cross-module linkages, integrated 5 Whys and 8D problem-solving tools, customizable action item matrices, automated due-date escalation alerts, and formal effectiveness re-verification with automated re-opening to "investigating" if recurrence occurs.
   - *Source:* https://www.qt9software.com/capa-software.aspx

---

## Feature catalog (this sub-module only)

### Bullet 1 — Issue Detection & Logging (NCR, customer complaints, audit findings, deviation capture)

- **Universal Multi-Source CAPA Initiation** — Ingests quality issues originating from diverse feeder streams: Non-Conformance Reports (NCR), Customer Complaints, Internal/External Quality Audits, Process/Lab Deviations, Risk Management / FMEA triggers, Regulatory Inspection Findings (e.g. FDA Form 483 / Warning Letters), Supplier Quality issues, and Management Review observations. · seen in: All leaders · priority: **table-stakes** · spine: `CapaInvestigation.source_type` choices + flexible reference fields · **buildable now**
- **Direct & Standalone CAPA Intake** — Supports standalone initiation of proactive preventive actions or systemic continuous improvement initiatives without requiring a pre-existing defect record. · seen in: MasterControl, Greenlight Guru, TrackWise · priority: **table-stakes** · spine: `CapaInvestigation` standalone creation · **buildable now**
- **Action Type Classification (Corrective vs. Preventive)** — Clear differentiation per ISO 9001 §10.2 / ISO 13485 §8.5.2 & §8.5.3: Corrective Action (eliminate the root cause of an existing non-conformity to prevent recurrence) vs. Preventive Action (eliminate the potential cause of a potential non-conformity to prevent occurrence) vs. Immediate Correction / Containment. · seen in: All leaders · priority: **table-stakes** · spine: `CapaInvestigation.action_type` choices · **buildable now**
- **Immediate Containment & Quarantine Actions** — Captures immediate containment and stop-gap measures taken upon discovery (e.g., inventory quarantine hold, stop-shipment order, line stoppage, customer safety alert) before root cause analysis commences. · seen in: Greenlight Guru, Qualio, MasterControl, ETQ · priority: **table-stakes** · spine: `CapaInvestigation.containment_action`, `containment_date`, `containment_verified_by` · **buildable now**
- **Risk-Based Triage & Severity Scoring** — Evaluates initial issue risk (Severity: Critical, Major, Minor; Risk Priority Level: Low, Medium, High, Extreme) to determine whether a full formal CAPA investigation is legally required vs. manageable via standard deviation or local correction. · seen in: MasterControl, Veeva Vault, Greenlight Guru · priority: **table-stakes** · spine: `CapaInvestigation.severity`, `risk_level` · **buildable now**
- **Product & Lot Traceability Capture** — Identifies affected part numbers, item codes, lot/batch numbers, serial numbers, and equipment/production lines impacted by the quality issue. · seen in: Greenlight Guru, QT9, TrackWise · priority: **table-stakes** · spine: `CapaInvestigation` text fields (`affected_item_code`, `affected_item_name`, `affected_lots`, `affected_equipment`) · **buildable now**

### Bullet 2 — Root Cause Analysis (RCA) (5 Whys, fishbone diagrams, fault tree analysis, statistical methods)

- **Multi-Methodology RCA Framework** — Accommodates industry-standard problem-solving disciplines within a single CAPA: 5 Whys iterative questioning, Fishbone (Ishikawa 6M), 8D (Eight Disciplines), Fault Tree Analysis (FTA), Is/Is Not Comparative Analysis (Kepner-Tregoe), and Barrier Analysis. · seen in: ETQ Reliance, QT9, Veeva Vault, Dot Compliance · priority: **table-stakes** · spine: `RootCauseAnalysis.method` choices · **buildable now**
- **Structured 5 Whys Investigation Engine** — Dedicated interactive problem decomposition capturing the initial problem statement, 5 sequential levels of "Why?" inquiries, and the resulting root cause finding. · seen in: Veeva Vault, Qualio, ETQ Reliance, QT9 · priority: **table-stakes** · spine: `RootCauseAnalysis` fields (`why_1`, `why_2`, `why_3`, `why_4`, `why_5`) · **buildable now**
- **Ishikawa 6M Fishbone Factor Structuring** — Categorizes potential contributing failure factors across the classic manufacturing 6M dimensions: Manpower / Personnel (training, human error, ergonomics), Machine / Equipment (maintenance, tooling, wear), Methods / Procedures (unclear SOP, incorrect revision), Materials (supplier variance, raw material defect), Measurement (calibration, gauge error), and Milieu / Environment (temperature, humidity, ESD). · seen in: MasterControl, ETQ Reliance, Dot Compliance · priority: **common** · spine: `RootCauseAnalysis` structured text/JSON fields for 6M categories · **buildable now**
- **Standardized Root Cause Taxonomy / Categorization** — Mandates categorization of finalized root causes into controlled regulatory taxonomy (e.g., Procedure/SOP Defect, Training Deficiency, Equipment/Tooling Malfunction, Material/Component Defect, Software Bug, Design Inadequacy, Environmental Factor, Human Factors/Usability) to facilitate cross-enterprise Pareto trending. · seen in: TrackWise, MasterControl, Dot Compliance, Qualio · priority: **table-stakes** · spine: `RootCauseAnalysis.root_cause_category` choices · **buildable now**
- **Escape Point & Detection Gap Analysis** — Investigates not just why the failure happened, but why the existing quality inspection barriers and controls failed to detect the defect before release (the "escape point"). · seen in: ETQ Reliance, 8D standard, MasterControl · priority: **common** · spine: `RootCauseAnalysis.escape_point_analysis` · **buildable now**
- **Root Cause Conclusion & Evidence Documentation** — Formal, defensible synthesis of the true root cause with attached investigation notes, testing logs, and laboratory findings. · seen in: All leaders · priority: **table-stakes** · spine: `RootCauseAnalysis.root_cause_summary`, `investigation_details` · **buildable now**

### Bullet 3 — Action Plan Development (Corrective actions, preventive actions, containment steps, effectiveness checks)

- **Granular Multi-Action Item Decomposition** — Decomposes the overarching CAPA plan into distinct, assignable action items (`CapaAction`), each with clear scope, owner, target completion date, and implementation deliverables. · seen in: All leaders · priority: **table-stakes** · spine: `CapaAction` model linked to `CapaInvestigation` · **buildable now**
- **Action Strategy Classification** — Classifies individual actions by strategic objective: Corrective (eliminate root cause), Preventive (prevent similar failures across other product lines/processes), Containment / Remediation (rework, quarantine, product hold), or Systemic Improvement. · seen in: Greenlight Guru, MasterControl, ETQ · priority: **table-stakes** · spine: `CapaAction.action_type` choices · **buildable now**
- **Cross-Subsystem Change Hooks (Document, Training, Design)** — Flags and links the specific quality subsystems requiring updates: SOP / Document Revision (FK `quality.ControlledDocument`, `quality.DocumentChangeOrder`), Design Control / DHF update (FK `quality.DesignProject`), Employee Retraining, Process Engineering change, or Supplier Corrective Action (SCAR). · seen in: MasterControl, Greenlight Guru, TrackWise, Veeva Vault · priority: **table-stakes** · spine: `CapaAction.action_category` + FKs to `quality.ControlledDocument`, `quality.DocumentChangeOrder`, `quality.DesignProject` · **buildable now**
- **Implementation Verification & Objective Evidence** — Requires an independent quality review of each completed action item to confirm physical implementation before the action item can be closed (e.g., verifying that the revised SOP was released and training records completed). · seen in: MasterControl, QT9, ETQ Reliance · priority: **table-stakes** · spine: `CapaAction.verified_by`, `verified_on`, `verification_evidence` · **buildable now**

### Bullet 4 — CAPA Tracking & Escalation (Due-date monitoring, overdue alerts, management review escalation)

- **Target Phase Timelines & Lifecycle SLA Enforcement** — Configurable target completion windows for each CAPA phase (Investigation Due Date, Implementation Due Date, Effectiveness Due Date). · seen in: All leaders · priority: **table-stakes** · spine: `CapaInvestigation` milestone date fields + derived SLA properties · **buildable now**
- **Overdue Status Detection & Visual Aging Badges** — Automatic identification of overdue investigations, pending action items, and delayed effectiveness checks with color-coded aging tiers (Active, Approaching Due, Overdue, Critical Aging). · seen in: All leaders · priority: **table-stakes** · spine: `CapaInvestigation.is_overdue`, `days_open` properties · **buildable now**
- **Formal Management Review Escalation** — Escalation flag and logging for CAPAs exceeding regulatory closure thresholds (e.g., open > 60/90 days) or involving high-severity patient safety risks, feeding directly into executive ISO 13485 / ISO 9001 Management Review meetings. · seen in: MasterControl, TrackWise, Greenlight Guru, QT9 · priority: **table-stakes** · spine: `CapaInvestigation.is_escalated`, `escalation_reason`, `escalated_at`, `management_review_date` · **buildable now**
- **Structured 7-Stage State Machine** — Governed lifecycle ladder: `Draft` -> `Investigation / RCA` -> `Action Planning` -> `In Implementation` -> `Pending Effectiveness` -> `Closed` -> `Reopened` (plus `Cancelled/Void`). Prevents skipping mandatory phases. · seen in: Veeva Vault, MasterControl, Greenlight Guru · priority: **table-stakes** · spine: `CapaInvestigation.status` choices & transition validation · **buildable now**

### Bullet 5 — Effectiveness Verification & Closure (Metrics-based validation, recurrence monitoring, formal closure approval)

- **Independent Effectiveness Verification Protocol** — Mandatory verification phase independent of action implementation, mandated by 21 CFR 820.100(a)(4) and ISO 13485 §8.5.2(e). Defines explicit criteria, verification methodology, and scheduled evaluation date. · seen in: All leaders · priority: **table-stakes** · spine: `CapaEffectivenessReview` model linked to `CapaInvestigation` · **buildable now**
- **Scheduled Delayed Evaluation Gate** — Enforces a time-delayed verification period (e.g., 30, 60, 90, or 180 days post-implementation, or after N production lots) to ensure sufficient operational run-time before assessing whether the root cause was truly eliminated. · seen in: MasterControl, ETQ Reliance, Qualio, Greenlight Guru · priority: **table-stakes** · spine: `CapaEffectivenessReview.scheduled_date` · **buildable now**
- **Quantitative & Qualitative Verification Methods** — Configurable effectiveness criteria: Statistical Sampling / Inspection (zero defects in N samples per AQL), Trend Analysis (defect rate reduced by X%), Quality Audit Recheck (follow-up audit clean), Process Capability (Cpk/Ppk improvement), or Zero Recurrence Over Time Window. · seen in: ETQ Reliance, MasterControl, Dot Compliance, QT9 · priority: **table-stakes** · spine: `CapaEffectivenessReview.verification_method`, `acceptance_criteria` · **buildable now**
- **Recurrence Monitoring & Re-Investigation Loop** — Explicit determination of whether the nonconformity recurred (`recurrence_detected: Yes / No`). If the effectiveness check fails, the system prevents closure and automatically triggers re-opening of the investigation (`status='reopened'` / `'investigating'`). · seen in: QT9, Veeva Vault, ETQ Reliance, MasterControl · priority: **table-stakes** · spine: `CapaEffectivenessReview.outcome` (`effective`, `partially_effective`, `not_effective`), re-open logic · **buildable now**
- **Formal Multi-Role Closure Sign-off** — Gated final closure requiring review by Quality Management, confirming all actions are implemented and verified effective. Compatible with 21 CFR Part 11 e-signatures (`quality.ElectronicSignatureRecord`). · seen in: All leaders · priority: **table-stakes** · spine: `CapaInvestigation.closed_by`, `closed_at`, `closure_summary` · **buildable now**

---

## Recommended build scope (this pass — 4 models)

Following the standard NavERP sub-module build pattern (1–4 tenant-scoped models inheriting `TenantNumbered` / `TenantOwned`), the recommended scope for Sub-module 12.4 comprises **4 models** under package `apps/quality/models/Capa/`:

1. **`CapaInvestigation` [prefix `QCAP`]** — The master CAPA record and regulatory lifecycle controller.
   - *Justified by:* Multi-source issue intake, Corrective vs. Preventive classification, immediate containment hold, risk triage, phase tracking, milestone SLAs, overdue detection, management review escalation, and formal closure.
   - *Key fields:* `number`, `title`, `action_type` (`corrective`, `preventive`), `source_type` (`nonconformance`, `complaint`, `audit_finding`, `deviation`, `risk_assessment`, `supplier`, `inspection_trend`, `management_review`), `source_reference` (char 100), `source_description` (text), `severity` (`critical`, `major`, `minor`), `risk_level` (`low`, `medium`, `high`, `extreme`), `problem_statement`, `containment_action`, `containment_date`, `affected_item_code`, `affected_item_name`, `affected_lots`, `target_investigation_date`, `target_implementation_date`, `target_effectiveness_date`, `status` (`draft`, `investigating`, `action_planning`, `in_implementation`, `pending_effectiveness`, `closed`, `reopened`, `cancelled`), `is_escalated`, `escalation_reason`, `management_review_date`, `closed_at`, `closure_summary`.
   - *FKs:* `tenant` (`core.Tenant`), `lead_investigator` (`core.Party`), `quality_owner` (`core.Party`), `department` (`core.OrgUnit`), `closed_by` (`core.Party`), `risk_assessment` (`quality.RiskAssessment`, optional), `design_project` (`quality.DesignProject`, optional).

2. **`RootCauseAnalysis` [prefix `QRCA`]** — The structured problem-solving and root cause investigation record.
   - *Justified by:* 5 Whys iterative questioning, Ishikawa 6M factor breakdown, standardized root cause taxonomy, escape point detection gap analysis, and defensible conclusion documentation.
   - *Key fields:* `number`, `method` (`five_why`, `fishbone_6m`, `eight_d`, `fault_tree`, `is_is_not`, `barrier_analysis`, `other`), `problem_redefinition`, `why_1`, `why_2`, `why_3`, `why_4`, `why_5`, `fishbone_data` (JSON / structured 6M text: Man, Machine, Method, Material, Measurement, Environment), `root_cause_category` (`procedure_sop`, `training_competence`, `equipment_tooling`, `material_component`, `software_design`, `hardware_design`, `environmental`, `human_factors`, `other`), `root_cause_summary`, `escape_point_analysis`, `status` (`draft`, `in_progress`, `completed`, `verified`, `rejected`), `completed_date`, `verification_notes`.
   - *FKs:* `tenant` (`core.Tenant`), `capa` (`quality.CapaInvestigation`), `lead_investigator` (`core.Party`), `verified_by` (`core.Party`).

3. **`CapaAction` [prefix `QACT`]** — Individual corrective, preventive, and containment action items.
   - *Justified by:* Action plan decomposition, strategic classification, cross-system links (SOP revision, training, design change, process engineering), due-date tracking, implementation verification, and evidence attachments.
   - *Key fields:* `number`, `action_type` (`corrective`, `preventive`, `containment`, `remediation`), `action_category` (`sop_revision`, `training`, `design_change`, `process_engineering`, `equipment_maintenance`, `supplier_action`, `other`), `title`, `description`, `target_date`, `completed_date`, `implementation_notes`, `status` (`pending`, `in_progress`, `completed`, `verified`, `cancelled`), `verified_on`, `verification_evidence`.
   - *FKs:* `tenant` (`core.Tenant`), `capa` (`quality.CapaInvestigation`), `root_cause` (`quality.RootCauseAnalysis`, optional), `assigned_to` (`core.Party`), `department` (`core.OrgUnit`), `verified_by` (`core.Party`), `document_change_order` (`quality.DocumentChangeOrder`, optional), `controlled_document` (`quality.ControlledDocument`, optional).

4. **`CapaEffectivenessReview` [prefix `QEFF`]** — The independent effectiveness verification and recurrence review record.
   - *Justified by:* 21 CFR 820.100(a)(4) and ISO 13485 §8.5.2(e) mandate, scheduled delayed evaluation gate, statistical/trend acceptance criteria, recurrence monitoring, and formal closure approval gate.
   - *Key fields:* `number`, `scheduled_date`, `review_date`, `verification_method` (`statistical_sample`, `trend_analysis`, `audit_recheck`, `process_capability`, `zero_recurrence_window`), `acceptance_criteria`, `evaluation_methodology`, `objective_evidence`, `metrics_observed`, `recurrence_detected` (bool), `outcome` (`pending`, `effective`, `partially_effective`, `not_effective`), `status` (`scheduled`, `under_review`, `completed`, `cancelled`), `review_notes`.
   - *FKs:* `tenant` (`core.Tenant`), `capa` (`quality.CapaInvestigation`), `reviewer` (`core.Party`), `approved_by` (`core.Party`).

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **Non-Conformance Reports (NCR) & Material Review Board (MRB)** -> Belongs to **12.5 Non-Conformance & Deviation Management**. Quarantine holds, suspect material tagging, disposition workflows (scrap, rework, return to vendor, use-as-is).
- **Supplier Corrective Action Requests (SCAR)** -> Belongs to **12.6 Supplier & Vendor Quality Management**. Supplier scorecards, supplier-issued CAPAs, AVL integration.
- **Equipment Maintenance & Calibration Work Orders** -> Belongs to **12.7 Calibration & Maintenance Management**. Out-of-tolerance investigations.
- **Receiving & In-Process Floor Inspections (IQC / IPQC / FQC)** -> Belongs to **12.8 Inspection & Quality Control**. AQL inspection plans.
- **Statistical Process Control (SPC) Charts** -> Belongs to **12.9 Statistical Process Control**. Control charts, X-bar R, Cp/Cpk process capability calculators.
- **Formal Audit Programs & Audit Findings** -> Belongs to **12.11 Quality Audits & Assessments**. ISO 19011 audit planning, checklists, observation scoring.
- **Customer Complaints, Vigilance & Medical Device Reporting (MDR)** -> Belongs to **12.13 Customer Complaints & Feedback Management**. 30-day FDA / EMA adverse event reporting.

---

## Deferred (later passes / integrations)

- **21 CFR Part 11 Electronic Signature Ceremony Integration:** While `quality.ElectronicSignatureRecord` exists in 12.1, full cryptographic signing modals for CAPA closure are wired as an enhancement after core CAPA CRUD and state transitions stabilize.
- **Automated Background Email/Push Escalation Alerts:** Background Celery/cron notification dispatch for overdue CAPAs is deferred; this pass provides the database fields, overdue properties, and UI visual indicators.
- **Interactive SVG / HTML5 Canvas Fishbone Diagram Builder:** Drag-and-drop graphical fishbone builder is deferred to frontend polish; this pass provides structured 6M forms and cleanly rendered summary cards.
- **Natural Language / AI Root Cause Clustering:** NLP similarity search across historical CAPAs (as seen in TrackWise Digital) is deferred to enterprise AI integration.
