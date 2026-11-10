# Research — Sub-module 11.11: Compliance & Regulatory Management (Module 11 — Asset Management System, `assets`)

- **Sub-module:** 11.11 Compliance & Regulatory Management
- **Module:** 11 Asset Management System
- **Target app:** `apps/assets` (package target: `apps/assets/models/AssetCompliance/`)
- **Research date:** 2026-11-10
- **Phase:** Phase 1 Research Catalog
- **Output file target:** `.claude/tasks/research-assets-11.11.md`

---

## 1. Executive Summary & Domain Architecture

Sub-module 11.11 delivers the **Compliance & Regulatory Management** governance and oversight engine for NavERP's **Asset Management System (`apps/assets`)**. Operating at the legal, environmental, and statutory boundary of physical asset operations, Sub-module 11.11 ensures enterprise equipment, facilities, vehicles, and plant infrastructure adhere strictly to mandatory regulatory frameworks (OSHA, EPA, DOT, ASME, NFPA), international management standards (ISO 55001, ISO 14001, ISO 45001), environmental operating licenses, and municipal permits.

Industrial and commercial enterprise assets operate under stringent statutory mandates. Failure to maintain active operating permits or comply with safety and environmental standards exposes organizations to catastrophic workplace casualties, severe environmental contamination, crippling regulatory fines (e.g. EPA civil penalties exceeding $50,000/day per violation; OSHA willful citation penalties exceeding $160,000 per violation), mandatory stop-work injunctions, and severe reputational damage.

Sub-module 11.11 unifies asset compliance operations across five foundational pillars:
1. **Regulatory Standards Mapping:**
   Catalogs regulatory bodies, statutory standards, code revisions, and specific clauses (ISO 55001 Asset Management, OSHA 1910 General Industry, EPA 40 CFR Environmental Protection, ASME Boiler & Pressure Vessel Code, NFPA 70E Electrical Safety). Maps frameworks directly to asset categories and specific operating assets, tracking overall organization readiness scores, applicability rules, and periodic review frequencies.
2. **Audit Preparation & Documentation:**
   Automates compliance audit cycles (internal oversight, ISO surveillance, regulatory inspections, customer quality audits). Provides digital compliance checklists, evidence collection (linking inspection logs, maintenance work orders, calibration records), non-conformance severity scoring (Compliant, Minor Non-Conformance, Major Non-Conformance, Critical Breach), and an audit summary dashboard ready for external regulatory review.
3. **Environmental & Safety Compliance:**
   Tracks environmental operating limits, continuous emission monitoring, hazardous material thresholds (Tier II EPCRA, RCRA hazardous wastes, refrigerant R-22/HFC phase-downs), and mandatory safety inspection protocols (lockout/tagout, pressure relief valve certifications, crane load tests).
4. **License & Permit Tracking:**
   Maintains a centralized register of operating permits, municipal licenses, emissions allowances, boiler operating certificates, and radioactive source licenses. Manages critical dates (issuance, effective, expiration), automated renewal lead alerts (e.g. 90/60/30-day windows), fee tracking, renewal prerequisites, and statutory issuing agency details.
5. **Penalty & Violation Management:**
   Logs formal notices of violation (NOV), citations, inspection deficiency notices, and non-compliance incidents. Tracks proposed vs assessed fines, payment settlements, root-cause investigations, and corrective/preventive action (CAPA) plans with verified closure verification.

---

### Architectural Data Flow & Spine Integration

```mermaid
flowchart TD
    subgraph SPINE["Core, SCM & Foundation Spine"]
        AST["scm.Asset [AST-]<br/>(Operational Plant & Facilities Equipment)"]
        ACAT["assets.AssetCategory [ACAT-]<br/>(Taxonomy & Criticality Node)"]
        PARTY["core.Party<br/>(Regulatory Bodies, Auditors & Permitting Authorities)"]
        DOC["core.Document<br/>(Permits, Evidence Files & Audit Packets)"]
        USER["settings.AUTH_USER_MODEL<br/>(Compliance Officers, Auditors & Inspectors)"]
    end

    subgraph SUB_11_11["11.11 Compliance & Regulatory Management (THIS SUB-MODULE)"]
        ACF["AssetComplianceFramework [ACF-]<br/>• Regulatory body & standard code mapping<br/>• ISO 55001 / OSHA / EPA / ASME clauses<br/>• Asset category applicability & readiness scoring<br/>• Mandatory review cycles & audit schedules"]

        ACA["AssetComplianceAudit [ACA-]<br/>• Scheduled & ad-hoc compliance audit cycles<br/>• Internal, third-party & regulatory scopes<br/>• Checklists, evidence links & findings scoring<br/>• Non-conformance ratings (Minor, Major, Critical)"]

        APL["AssetPermitLicense [APL-]<br/>• Operating permits, licenses & safety certificates<br/>• Issuing authority, license #, conditions & limits<br/>• Expiration dates, renewal lead alerts & fee tracking<br/>• Renewal approval & compliance status lifecycle"]

        ACI["AssetComplianceIncident [ACI-]<br/>• Notice of Violation (NOV), citations & infractions<br/>• Environmental exceedances & safety failures<br/>• Penalty fine amounts, currencies & payment tracking<br/>• Root cause analysis & CAPA remediation workflows"]
    end

    %% Model Relationships
    PARTY -->|Regulatory Authority / Agency| ACF
    ACAT -->|Applicable Category| ACF
    ACF -->|Framework Audited| ACA
    AST -->|Subject Asset| ACA
    USER -->|Lead Auditor / Assigned Officer| ACA
    DOC -->|Audit Evidence Packet| ACA

    AST -->|Permitted Asset| APL
    PARTY -->|Issuing Agency| APL
    DOC -->|Permit Certificate Document| APL

    AST -->|Non-Compliant Asset| ACI
    APL -->|Violated Permit (Optional)| ACI
    PARTY -->|Issuing Enforcement Agency| ACI
    ACA -->|Source Audit (Optional)| ACI
    USER -->|Investigator / Remediation Lead| ACI
```

---

## 2. Leading Commercial Products in this Domain

To build a competitive, enterprise-grade solution, we surveyed the eight leading commercial software products in enterprise asset compliance, environmental health & safety (EHS), and regulatory governance:

1. **IBM Maximo (Maximo Health, Safety & Environment - HSE):**
   - *Overview:* The enterprise gold standard in EAM. Its HSE add-on is deeply rooted in ISO 55001 principles.
   - *Key Capabilities:* Directly links regulatory compliance records to asset hierarchies; tracks operating permits with expiration alert matrices; enforces Lockout/Tagout (LOTO) safety prerequisites; logs regulatory citations with root-cause investigation trees; generates regulatory audit documentation packs directly from work order histories.
2. **Enablon (Wolters Kluwer):**
   - *Overview:* Leading enterprise EHS & Operational Risk Management (ORM) platform for energy, chemicals, and manufacturing.
   - *Key Capabilities:* Regulatory compliance registers mapped to global environmental statutes (EPA Clean Air Act, Clean Water Act, Title V, RCRA); management of change (MOC) compliance reviews; automated compliance audit checklists with mobile execution; citation and penalty register with legal liability reserves.
3. **Cority:**
   - *Overview:* Enterprise EHS and sustainability software suite with robust industrial hygiene and environmental modules.
   - *Key Capabilities:* Comprehensive regulatory standard mapping with automated regulatory updates; environmental permit limit monitoring (mass balance, discharge thresholds); corrective and preventive action (CAPA) tracking with effectiveness verifications; audit finding registers with automated escalation.
4. **Intelex (EHSQ):**
   - *Overview:* Global EHS and Quality management system renowned for ISO 14001, ISO 45001, and ISO 55000 frameworks.
   - *Key Capabilities:* Pre-configured audit checklist templates for regulatory inspections; permit condition tracking with recurring compliance task assignments; non-conformance and notice of violation incident reporting; root cause analysis (5 Whys / Fishbone) tied to corrective actions.
5. **Benchmark Gensuite:**
   - *Overview:* Cloud compliance platform specializing in operational risk and environmental permit compliance.
   - *Key Capabilities:* "Compliance Calendar" engine for statutory permit renewal deadlines and regulatory reporting filings; hazardous materials inventory tracking (Tier II EPCRA); audit readiness dashboards showing real-time compliance posture by site and asset category.
6. **SAP EAM & SAP EHS (Environment, Health, and Safety):**
   - *Overview:* Market-leading ERP asset maintenance and compliance suite.
   - *Key Capabilities:* Direct integration between plant maintenance work orders and permit-to-work systems; statutory inspection interval tracking; environmental emissions limits monitored via asset measurement points; penalty cost tracking linked to financial general ledger accounts.
7. **SoftExpert Excellence Suite (SoftExpert EAM / GRC / EHS):**
   - *Overview:* Unified Governance, Risk, and Compliance (GRC) and EAM solution.
   - *Key Capabilities:* Regulatory requirements repository linked to assets, policies, and process controls; multi-standard audit management (planning, fieldwork, observation, reporting, action plan); license and certification expiration matrix with automated workflow notifications.
8. **ComplianceQuest:**
   - *Overview:* Cloud-native Quality and EHS management system built on Salesforce.
   - *Key Capabilities:* Integrated permit management lifecycle; automated supplier and internal asset audit workflows; regulatory inspection management with inspector note logging; penalty fine accounting and legal remediation tracking.

---

## 3. Competitive Feature Matrix & Deep-Dive

Mapping researched industry capabilities directly against the five **NavERP.md** feature bullets for Sub-module 11.11:

### Feature Bullet 1: Regulatory Standards Mapping
*NavERP.md: "Regulatory Standards Mapping — ISO 55000, OSHA, EPA, and industry-specific compliance frameworks."*

| Feature Capability | Commercial Benchmark | Priority | NavERP Implementation Plan |
|---|---|---|---|
| **Multi-Framework Standards Catalog** | IBM Maximo, Enablon, SoftExpert | Table-Stakes | Standard code register: ISO 55001 (Asset Mgmt), ISO 14001 (Environmental), ISO 45001 (Health & Safety), OSHA 1910 (General Industry), EPA 40 CFR, ASME BPVC, NFPA 70E. |
| **Regulatory Body / Authority Linking** | Intelex, Benchmark Gensuite | Table-Stakes | FK to `core.Party` representing enforcement agency (e.g. EPA, OSHA, State Dept of Environmental Protection). |
| **Asset Category & Scope Mapping** | IBM Maximo, SAP EAM | Table-Stakes | Linking frameworks to `assets.AssetCategory` (e.g., pressure vessels require ASME; combustion equipment requires EPA Title V). |
| **Compliance Readiness Scoring** | SoftExpert, ComplianceQuest | Common | Calculated compliance readiness metric (0–100%) indicating the percentage of required audits and permits satisfied. |
| **Mandatory Review & Audit Cycle** | Cority, Intelex | Common | Mandatory review frequency (e.g. annual, biennial, triennial) with next scheduled compliance review tracking. |

### Feature Bullet 2: Audit Preparation & Documentation
*NavERP.md: "Audit Preparation & Documentation — Evidence collection, compliance checklists, and auditor access portals."*

| Feature Capability | Commercial Benchmark | Priority | NavERP Implementation Plan |
|---|---|---|---|
| **Audit Cycle Scheduling & Scope** | Intelex, SoftExpert, Enablon | Table-Stakes | Formal audit scheduling (`ACA-#####`) with defined scope (Internal, External Regulatory, ISO Certification, Customer). |
| **Lead Auditor & Team Assignment** | SoftExpert, ComplianceQuest | Table-Stakes | Dedicated fields for Lead Auditor (User / external `Party`) and Auditee Asset Owner. |
| **Checklist & Findings Management** | Intelex, Cority, IBM Maximo | Common | Checklist items count, passed items, minor non-conformances, major non-conformances, and critical breaches. |
| **Compliance Rating & Outcomes** | IBM Maximo, Intelex | Table-Stakes | Standardized rating: Fully Compliant, Minor Deficiency, Major Non-Conformance, Unsatisfactory / Critical Breach. |
| **Evidence Documentation Repository** | Benchmark Gensuite, Enablon | Common | Direct attachment integration (`core.Document`) for inspection certificates, test logs, and audit summary reports. |

### Feature Bullet 3: Environmental & Safety Compliance
*NavERP.md: "Environmental & Safety Compliance — Emissions tracking, hazardous material registers, and safety inspection logs."*

| Feature Capability | Commercial Benchmark | Priority | NavERP Implementation Plan |
|---|---|---|---|
| **Operating Conditions & Thresholds** | Enablon, Cority, SAP EHS | Table-Stakes | Capturing operating conditions, emissions thresholds (PPM, tons/yr), hazardous material inventory types, and safety limits. |
| **Inspection Log & Certification Linking** | IBM Maximo, UpKeep | Table-Stakes | Direct cross-referencing between equipment compliance records and periodic inspection/calibration certificates. |
| **Environmental Hazard Classification** | Cority, Benchmark Gensuite | Common | Categorizing compliance requirements into Air Emissions, Hazardous Waste (RCRA), Wastewater Discharge, Toxic Chemical, or Physical Safety. |
| **Regulatory Notification Protocol** | Enablon, Intelex | Differentiator | Enforcing statutory incident notification timelines (e.g. 24-hr EPA reportable release, OSHA 8-hr fatality / 24-hr hospitalization reporting). |

### Feature Bullet 4: License & Permit Tracking
*NavERP.md: "License & Permit Tracking — Operating licenses, certifications, and renewal deadline management."*

| Feature Capability | Commercial Benchmark | Priority | NavERP Implementation Plan |
|---|---|---|---|
| **Centralized Permit & License Register** | Benchmark Gensuite, SoftExpert | Table-Stakes | Dedicated entity (`APL-#####`) capturing license number, permit type, issuing authority (`core.Party`), and permitted asset (`scm.Asset`). |
| **Effective, Expiration & Renewal Dates** | ExpiryEdge, Intelex, Zluri | Table-Stakes | Structured date lifecycle: Issue Date, Effective Date, Expiration Date, and Next Renewal Due Date. |
| **Renewal Lead Alert Windows** | Benchmark Gensuite, IBM Maximo | Table-Stakes | Configurable lead warning days (e.g. 90, 60, 30 days) with visual badge indicators (`Active`, `Renewal Pending`, `Expired`, `Suspended`). |
| **Permit Fees & Renewal Costs** | SoftExpert, SAP EAM | Common | Tracking initial license fees, annual renewal fees, and statutory filing costs. |
| **Operating Conditions & Constraints** | Enablon, Cority | Common | Documenting specific permit terms, capacity caps (e.g. MMBtu/hr burner rating, max gallons/day discharge), and reporting frequencies. |

### Feature Bullet 5: Penalty & Violation Management
*NavERP.md: "Penalty & Violation Management — Non-compliance incident logging, corrective actions, and fine tracking."*

| Feature Capability | Commercial Benchmark | Priority | NavERP Implementation Plan |
|---|---|---|---|
| **Notice of Violation (NOV) & Citation Log** | Enablon, Intelex, Cority | Table-Stakes | Dedicated incident entity (`ACI-#####`) recording citation/ticket number, violation date, violation category, and citing agency. |
| **Severity & Citation Classification** | OSHA/EPA standards | Table-Stakes | Severity tiers: De Minimis, Other-Than-Serious, Serious, Repeat, Willful, Imminent Danger. |
| **Financial Exposure & Fine Tracking** | SAP EHS, Enablon | Table-Stakes | Proposed/assessed penalty fine amount, negotiated settlement amount, paid amount, payment date, and receipt verification. |
| **Root Cause Analysis (RCA)** | ComplianceQuest, Intelex | Common | Structured RCA method and investigation narrative (Equipment Failure, Inadequate Training, Procedural Drift, Design Flaw). |
| **CAPA & Remediation Action Tracking** | Intelex, SoftExpert, IBM Maximo | Table-Stakes | Detailed corrective action plan, responsible remediation officer, target completion date, actual completion date, and verified closure status. |

---

## 4. Spine Entity Mapping & Verified As-Built Reuses

Per project rule (lessons L28/L29), we verified existing master tables in the codebase before defining foreign keys:

1. **`scm.Asset` (`apps/scm/models/AssetManagement/Assets.py` [AST-]):**
   - *Status:* Verified as-built.
   - *Role in 11.11:* The primary physical plant asset, facility machine, or mobile equipment subject to compliance frameworks, audits, permits, and non-compliance citations.
2. **`assets.AssetCategory` (`apps/assets/models/AssetClassification/AssetCategories.py` [ACAT-]):**
   - *Status:* Verified as-built.
   - *Role in 11.11:* The taxonomy node to which broad regulatory standards apply (e.g. Pressure Vessels, Heavy Mobile Equipment, Chemical Storage Tanks).
3. **`core.Party` (`apps/core/models/Party.py`):**
   - *Status:* Verified as-built.
   - *Role in 11.11:* Standardized representation of external entities:
     - Regulatory agencies (OSHA, EPA, State Environmental Agency, Department of Transportation).
     - External accredited audit firms (BSI, TÜV SÜD, Bureau Veritas, DNV).
     - Permitting and licensing authorities (Municipal Fire Marshals, County Health Departments).
4. **`core.Document` (`apps/core/models/Document.py`):**
   - *Status:* Verified as-built.
   - *Role in 11.11:* Digital storage for official permit certificates, stamped inspection reports, NOV formal notices, and auditor evidence packets.
5. **`settings.AUTH_USER_MODEL` (`apps/accounts/models/User.py`):**
   - *Status:* Verified as-built.
   - *Role in 11.11:* Internal compliance officers, lead internal auditors, asset owners, and corrective action assignees.

---

## 5. Recommended Build Scope: 4 Tenant-Scoped Models

To deliver complete, production-grade coverage for Sub-module 11.11 within the strict 1–4 model rule, we recommend the following four tenant-scoped entities under package `apps/assets/models/AssetCompliance/`:

### Model 1: `AssetComplianceFramework` (Prefix: `ACF-`)
- **Purpose:** Catalogs regulatory standards, compliance mandates, safety codes, and international frameworks governing physical enterprise assets.
- **Key Fields:**
  - `number`: Auto-generated identifier (`ACF-#####`).
  - `name`: Framework name (e.g., "OSHA 1910.119 Process Safety Management", "ISO 55001 Asset Management Framework", "EPA Title V Clean Air Act Operating Permit Standard", "ASME Boiler & Pressure Vessel Code Section VIII").
  - `code`: Short statutory code/identifier (e.g. `OSHA-1910-PSM`, `ISO-55001`, `EPA-TITLE-V`, `ASME-BPVC`).
  - `framework_type`: Choice (`regulatory`, `statutory`, `voluntary_standard`, `industry_code`, `corporate_policy`).
  - `regulatory_agency`: ForeignKey to `core.Party` (nullable) — enforcement authority (e.g. OSHA, EPA).
  - `applicable_category`: ForeignKey to `assets.AssetCategory` (nullable) — category of assets governed.
  - `effective_date`: Date the standard takes effect for the organization.
  - `revision`: Current standard edition/version (e.g., "2024 Edition", "Rev 4").
  - `mandatory_audit_cycle_months`: Integer audit frequency (e.g. 12 for annual, 36 for triennial).
  - `readiness_score`: Integer (0–100%) indicating current audit readiness.
  - `description`: Detailed scope, applicability guidelines, and compliance objectives.
  - `status`: Choice (`active`, `draft`, `under_review`, `deprecated`).

### Model 2: `AssetComplianceAudit` (Prefix: `ACA-`)
- **Purpose:** Manages compliance audit cycles, verification inspections, checklist execution, evidence gathering, and non-conformance severity tracking.
- **Key Fields:**
  - `number`: Auto-generated identifier (`ACA-#####`).
  - `title`: Descriptive title of audit (e.g., "Annual OSHA Machinery Guarding Audit - Plant 1", "ISO 55001 Stage 2 Surveillance Audit", "EPA Hazardous Waste Storage Inspection").
  - `framework`: ForeignKey to `AssetComplianceFramework` — governing standard.
  - `asset`: ForeignKey to `scm.Asset` (nullable) — specific asset audited (or null for plant/category-wide audit).
  - `audit_type`: Choice (`internal`, `external_regulatory`, `third_party_certification`, `customer_qualification`).
  - `lead_auditor_user`: ForeignKey to `settings.AUTH_USER_MODEL` (nullable) — internal lead auditor.
  - `auditor_party`: ForeignKey to `core.Party` (nullable) — external audit firm / inspector.
  - `audit_date`: Scheduled or completed audit date.
  - `scope_description`: Statement of audit scope, facility boundaries, and target equipment.
  - `total_checkpoints`: Integer count of evaluated checklist checkpoints.
  - `passed_checkpoints`: Integer count of compliant checkpoints.
  - `minor_findings_count`: Integer count of minor deficiencies.
  - `major_findings_count`: Integer count of major non-conformances.
  - `critical_findings_count`: Integer count of critical/immediate danger findings.
  - `compliance_rating`: Choice (`fully_compliant`, `minor_deficiencies`, `major_non_conformance`, `critical_breach`, `not_rated`).
  - `summary_findings`: Text summary of auditor observations and required actions.
  - `status`: Choice (`scheduled`, `in_progress`, `under_review`, `completed`, `cancelled`).

### Model 3: `AssetPermitLicense` (Prefix: `APL-`)
- **Purpose:** Tracks mandatory operating permits, municipal licenses, emissions registrations, safety certificates, and recurring renewal deadlines for enterprise assets.
- **Key Fields:**
  - `number`: Auto-generated identifier (`APL-#####`).
  - `permit_name`: Official title (e.g., "Stationary Source Air Emissions Operating Permit", "High-Pressure Steam Boiler Operating Certificate", "Flammable Liquids Storage Permit", "Overweight Heavy Hauler Highway Permit").
  - `permit_number`: Regulatory license number issued by the authority (e.g. `EPA-AIR-2026-9042`, `BOILER-CERT-7731`).
  - `permit_type`: Choice (`environmental_emissions`, `safety_operating`, `hazardous_material`, `water_discharge`, `pressure_vessel`, `radiation_device`, `municipal_zoning`, `transportation`).
  - `asset`: ForeignKey to `scm.Asset` — physical asset covered by this permit/license.
  - `issuing_authority`: ForeignKey to `core.Party` (nullable) — permitting body.
  - `issue_date`: Date issued by authority.
  - `effective_date`: Start date of permit validity.
  - `expiration_date`: Critical statutory expiration deadline.
  - `renewal_lead_days`: Days ahead of expiration to trigger renewal alert (e.g. 30, 60, 90).
  - `renewal_fee`: Decimal amount of renewal filing fee.
  - `operating_conditions`: Permitted limits, operating thresholds, hours, or emission caps.
  - `status`: Choice (`active`, `pending_renewal`, `under_review`, `expired`, `suspended`, `revoked`).

### Model 4: `AssetComplianceIncident` (Prefix: `ACI-`)
- **Purpose:** Logs non-compliance violations, statutory citations, notices of violation (NOV), penalty fines, and corrective/preventive action (CAPA) remediation.
- **Key Fields:**
  - `number`: Auto-generated identifier (`ACI-#####`).
  - `title`: Brief incident summary (e.g., "EPA Title V Exceedance - Boiler #2 NOX Emission Spike", "OSHA Citation 1910.212 - Missing Machine Guarding on Stamping Press").
  - `incident_date`: Date and time the violation or exceedance occurred.
  - `discovery_date`: Date the organization discovered or was cited for the event.
  - `incident_type`: Choice (`notice_of_violation`, `regulatory_citation`, `emissions_exceedance`, `unpermitted_discharge`, `safety_infraction`, `failed_inspection`, `internal_audit_breach`).
  - `severity`: Choice (`de_minimis`, `other_than_serious`, `serious`, `repeat`, `willful`, `imminent_danger`).
  - `asset`: ForeignKey to `scm.Asset` (nullable) — cited asset.
  - `permit`: ForeignKey to `AssetPermitLicense` (nullable) — violated permit/license.
  - `audit`: ForeignKey to `AssetComplianceAudit` (nullable) — source audit that uncovered the breach.
  - `enforcement_agency`: ForeignKey to `core.Party` (nullable) — citing agency.
  - `citation_reference`: Agency docket, ticket, or citation reference number.
  - `fine_assessed`: Decimal monetary fine or penalty assessed by regulator.
  - `fine_paid`: Decimal amount actually settled and paid.
  - `fine_payment_date`: Date fine was disbursed.
  - `root_cause`: Choice (`mechanical_failure`, `human_error`, `inadequate_procedure`, `lack_of_maintenance`, `measurement_error`, `external_factor`).
  - `root_cause_analysis`: Narrative of root cause investigation.
  - `corrective_action_plan`: Mandated or proposed CAPA remediation plan.
  - `assigned_investigator`: ForeignKey to `settings.AUTH_USER_MODEL` (nullable).
  - `target_resolution_date`: Date CAPA is scheduled for completion.
  - `actual_resolution_date`: Date CAPA was executed and verified.
  - `status`: Choice (`open`, `under_investigation`, `capa_in_progress`, `under_agency_review`, `appealed`, `resolved`, `closed`).

---

## 6. Deferred Features & Out-of-Scope Roadmap

The following advanced or specialized capabilities were analyzed during market research and are consciously deferred to subsequent sub-modules or future releases:

1. **Continuous IoT Emissions CEMS Telemetry Ingestion (Deferred to Module 10 BI & 23 AI):**
   Real-time millisecond-frequency automated IoT sensor ingestion for smokestack Continuous Emission Monitoring Systems (CEMS) will link into Module 10 telemetry streams and Module 11.7 `AssetTelemetryReading`.
2. **Automated EPA Central Data Exchange (CDX) / NetDMR Electronic Filings (Deferred to EDI/Integrations):**
   Direct XML/REST electronic filing integration into US EPA electronic reporting portals (TRI-MEweb, NetDMR) is an external regulatory gateway service.
3. **Legal Litigation & Regulatory Court Defense Case Management (Deferred to Legal/Governance):**
   Full multi-jurisdictional legal docket tracking and outside counsel billing for appealed environmental enforcement lawsuits belongs to enterprise corporate legal operations.
4. **Comprehensive Site-Wide ESG Carbon Accounting & Scope 1/2/3 Inventories (Belongs to Module 22 Sustainability & ESG):**
   Enterprise-wide corporate carbon footprint calculations and GHG Protocol disclosure packs belong to Module 22 `esg`, which will consume asset operating hours and emissions data from Sub-module 11.11.

---

## 7. Recommended Next Steps

1. Hand off this research catalog to the `todo` agent.
2. Generate checkable implementation task list in `.claude/tasks/todo.md`.
3. Freeze the pre-build contract in `.claude/tasks/contract-assets-11.11.md`.
4. Implement entity by entity under `apps/assets/` following NavERP package conventions.
