# Research — Sub-module 11.16: Document & Knowledge Management (Module 11 — Asset Management System, `assets`)

**Date:** 2026-11-12
**Target NavERP.md section:** `### 11.16 Document & Knowledge Management` (Module 11 — Asset Management System, lines 1834–1839)
**App target:** `apps/assets` (`apps/assets/models/AssetDocumentKnowledge/`, `templates/assets/...`, `app_name = "assets"`)

---

## Repo state checked first

- **Navigation (`apps/core/navigation.py`):** `LIVE_LINKS` has Module 11 built for `11.1` through `11.15`; `11.16`–`11.19` are unbuilt (`11.16` has no `LIVE_LINKS` entry yet). Neither Module 12 (`quality`) nor Module 13 (`documents`) exists in `LIVE_LINKS`.
- **Installed apps (`apps/`):** `accounting`, `accounts`, `assets`, `bi`, `core`, `crm`, `dashboard`, `ecommerce`, `hrm`, `inventory`, `procurement`, `projects`, `sales`, `scm`, `tenants` (`apps/documents` and `apps/quality` do not exist).
- **Migrations (`apps/assets/migrations/`):** Latest migration is `0021_assetexecutivescorecard_idx_akpi_ten_org_and_more.py` (all `11.1`–`11.15` models migrated; next migration is `0022_*`).
- **Existing `apps/assets` packaging convention:** Sub-modules `11.1`–`11.15` each own a PascalCase sub-package under `apps/assets/models/`, `forms/`, `views/`, and `urls/`, with **4 `TenantNumbered` models** per sub-module (60 existing `Asset*` / `CapitalizationPolicy` models across `11.1`–`11.15`). Base classes in `apps/assets/models/_base.py` provide `TenantOwned` (`tenant`, `created_at`, `updated_at`) and `TenantNumbered` (`NUMBER_PREFIX`, `number`, auto-generated via `next_number` in `save()`).
- **Upload security baseline (`apps/core/forms/_common.py`):** `ALLOWED_DOC_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".zip"}` (explicitly excluding `.svg` to prevent inline stored XSS under `/media/`) and `MAX_UPLOAD_BYTES = 20 * 1024 * 1024` (20 MB).
- **Verified spine & sibling models (available to FK by string — never duplicate):**
  - `core`: `core.Tenant`, `core.Party` (`kind` person/organization; `core.PartyRole`), `core.OrgUnit`, `core.Employment`, `core.Document` (`GenericForeignKey`, `classification` [`public`/`internal`/`confidential`], `version`, `uploaded_at`), `core.Activity`, `core.AuditLog`.
  - `accounts`: `accounts.User` (`settings.AUTH_USER_MODEL`; links `tenant`, `party`, `role`, `is_tenant_admin`).
  - `scm`: `scm.Asset` [`AST-`] (`code`, `name`, `asset_type`, `status`, `criticality`, `category`, `manufacturer`, `model_number`, `serial_number`, `tag_code`, `specifications`, `parent`, `location`, `work_center`, `org_unit`, `custodian`, `supplier`, `service_vendor`, `fixed_asset`), `scm.Location`, `scm.MaintenancePlan`, `scm.MaintenanceWorkOrder`.
  - `accounting`: `accounting.FixedAsset` [`FA-`].
  - `hrm`: `hrm.EmployeeProfile`, `hrm.TrainingCourse` [`TRC-`], `hrm.TrainingCertificate` [`CERT-`] (`expires_on`, `verification_code`, `status`), `hrm.EmployeeDocument` [`EDOC-`], `hrm.KnowledgeArticle` [`KBA-`].
  - `assets`: `AssetCategory` [`ACAT-`], `AssetModel` [`AMOD-`], `AssetSpecificationTemplate` [`ASPC-`], `AssetCriticalityAssessment` [`ACRT-`], `AssetWarranty` [`AWAR-`], `AssetMaintenanceSchedule` [`AMSC-`], `AssetMaintenanceRequest` [`AMRQ-`], `AssetMaintenanceLog` [`AMLG-`], `AssetFailureMode` [`AFMA-`], `AssetConditionAssessment` [`ACAS-`], `AssetCalibrationRecord` [`ACAL-`] (already uses `certificate_document = FK("core.Document")` and expiry status badges), `AssetIncidentReport` [`AINC-`], `AssetComplianceFramework` [`ACF-`], `AssetComplianceAudit` [`ACA-`], `AssetPermitLicense` [`APL-`], `AssetComplianceIncident` [`ACI-`], `AssetRiskRegister` [`ARK-`], `AssetBusinessContinuityPlan` [`ABC-`], `AssetCyberSecurityProfile` [`ACS-`], `AssetExecutiveScorecard` [`AKPI-`].
- **Sibling DMS/KB reference patterns in NavERP:**
  - `apps/projects/models/DocumentKnowledgeManagement/`: `ProjectDocument` [`PDM-`], `ProjectDocumentRevision`, `KnowledgeEntry` [`KNE-`].
  - `apps/procurement/models/DocumentKnowledgeManagement/`: `ProcurementDocument` [`PDOC-`], `ProcurementDocumentRevision`, `KnowledgeResource` [`PKR-`].
  - `apps/crm/models/DocumentContract/DocumentVersions.py`: `DocumentVersion`.
  - Precedent note: `core.Document` uses a `GenericForeignKey` without revision workflow, checkout locking, equipment/model/category linkage, expiry tracking, or direct `.filter(tenant=...)` joins; therefore, domain modules maintain a dedicated controlled document model while optionally bridging to `core.Document`.
- **Prefix & class collision check:** Scanned all 602 `NUMBER_PREFIX` constants across `apps/**/models/**/*.py` and all 60 classes under `apps/assets/models/`. Candidate prefixes `ADOC`, `ASOP`, `AOCT`, and `AKBA` are all unused (`FREE`), and proposed class names (`AssetDocument`, `AssetOperatingProcedure`, `AssetOperatorCertification`, `AssetKnowledgeArticle`) have zero collisions.

---

## Leaders surveyed (with source links)

1. **IBM Maximo Application Suite (Maximo Manage)** — [ibm.com (Doclinks)](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE0BaJeHhWadoKYfykBYI4YxkNJneDx3DN7skqG2tkWnJ4I4b7M7XhI2B9quabxoqSg_7XEqUoK15Ss6C8sKjE18-D_IBCkh0oUXNF__1w3voWZOuFpN4l5SPLd5XOR6FvCjS843decEwty99JaO3RXNLu3HBQtZmzQA5tTLk10tD5ANsR0wLAosXLaR8qVT2MlB6Z-kPzIusZcD-UvmdAXVw6frkX6i_7HqwhNEJk=), [ibm.com (Revision Control)](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGx_58d0-DyF6SjVgcp6V7BCCpry8VhfUTBTXG7XyShOxFRHzwyGdzCx4ID96j1MQH7Sm5MNXsqOzYAowZ8Kr4NHOiRw5gr3Uln919TzXgD4QnvwF9OMgwXuoI4afCgxnOmZmC3FGhGrkwocxUDGRIjaLAFw-2SSzkjrU-vQhqHf4GxRw97KZKYKg9-iaf5), [naviam.io (Failure Codes)](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHZkHnfJ372iEss0T2xXhUxvuiHvaX7uCDnTyiXJ80sgiHk_tLXamvXbhonTY07H8mZgDTmjGvAtN5_ejq8b1lglhAQ_YrSx06UPW88tNYyWfeDjSf705Sg_zZwKHAgsYbnZ5XdFMQJ_0GeYXwuEYMqXMxLFsG70K87haAtCn_B2c6oF6kMsGXd0xiFJw9glGJXN71-iCUk7M3Thw==)
   - Centralized Document Library Folders (`DOCLINKS`) bound to Assets/Work Orders, controlled record revision workflows locking pending revisions against ad-hoc attachment edits, Labor/Craft Qualifications & Certifications required for high-risk Job Plans/Safety Plans, and structured Failure Reporting (`Failure Class -> Problem -> Cause -> Remedy`).
2. **SAP EAM (SAP DMS / Engineering Change Management & WCM / APM)** — [sap.com (ECM)](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQESZcHybRM0qSHtSeR2rpUOFZiFWtLkbBIdRvciapLL8Xs7CHOQne2_LergbVOFF32fcgLah3kMZ7A2OQNERnGRjHCAXTaQ0-VOOoJN5Rgmn-EmgYLaq6R_SugewApEXy1Nt1-LQgdB3C5hti5Floi2ZtOCPqsASgKxQ7SDuC_cU2yxYu4pvVxnPNZteG5Yoj3Lo6xA-4c_MLA3_8VCKb-tLnSnFA0no71wNZq9R1HYxStEoFDSdmlgaWKuYafCbG7T3rgTN_M3kqQJNz-DpW8=), [sap.com (APM/FMEA)](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGSFB7a7rFk-dnG3PrjnevJxpdTXWLxVAw8GkwIPpgeC23YgjvAZFfE8rrt3LgXYf6_PcniClGKtU2vVJO653Ssu9WV_FXBfckbCwuUO7z2-Xp77tZZt4eW1fHzQqQK5UgxJTUDrtdhf2wR7DugQtmC-f56XD03H743SYwwtsgD_IC5loJQSiiuyhMFdrueX8d3m21NsSgTXTUAJZl0JA==)
   - Document Info Records (DIRs) governed by Change Records / Engineering Change Management (ECM) binding BOM, routing, and spec revisions to technical objects; Work Clearance Management (WCM) for LOTO safety isolation steps and danger tags; and APM Failure Catalogs mapping damage codes, causes, and mechanisms.
3. **Accruent Meridian (EAM EDMS)** — [accruent.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFe5IoTrqazJALYLhq69qvlq-rzIgA23OAo2KDNLbX4S3dYN25o-U_KIH0-HpBwMRyUGkxsVxKfGppUG2Nh1dUz1A5PZzSHikKmshZML0c2WC64bZwlaZr0PGJMFWXGoMo=), [meridian360.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE8Zx0Q7hBZ_h5jA85-TNg5S4CQIqdXoQDkUYwlGKkatZea6VW71_ex7xw9-OCDpB-3gUoDPQRSdpSljX3Y0L77FnnzAhOJg2LGTimvLtlkw1dodX65kX1hwz3bmpRfW1aCxsQtJbW8hXWeMCJGEeChsmPpiFvS7mPP6DJGmf8qeaY6t4sRFsmKw9Q2kyt5tbYdYug7FzfWdmlGhFeQCYqp)
   - Separates Approved "As-Built" master vault from Work-in-Progress (WIP) engineering workspace; tag-based asset-to-drawing sync; field markup/redlining feedback loops; and Management of Change (MOC) parallel approval workflows locking affected drawings until release.
4. **OpenText Extended ECM for Engineering** — [opentext.com (xECM Engineering)](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH_OSqzB5_twYan1Z9mY8Wo5U7HvIoJaaq0Er7q5Lk16CL6hr_xHCqRFyNvrUXonxJzgKPfyQjXplIMgLh0zr1CksgRYxobK0BTZ5mGI9fzqhYXOsXpRnj9WzLJ6-Biw9NHzzsP2rF3EsVOuA905iNYYFcxViD9q8MbC2A1s5e2jnaOh6CpDnXFIHzY-hnh5Je4dYHUcysb36M=), [opentext.com (Document Training)](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHxWkvFb7qDxAZmbeQB54cbfo0Iu4XktFF09oUzJ769jSraSqWRns9bU8lfyHp9Zq9EZ4MytHStgD5WR6Lp34jG6S1hp5zbv8KRiJOcMZf0SQ6dXpCnZCRFE3uglN5FTqSMtDan88t8-3MnFE1Vhg==)
   - Authoritative lifecycle workspaces for CAD drawings, P&IDs, and vendor manuals; transmittals and redlining review; MOC risk/safety gating; automated SOP sign-off tied to Document Training/certification compliance; and archival of RCA reports alongside resulting engineering modifications.
5. **IFS Cloud EAM & Document Management (EDM)** — [ifs.com (Object Connections)](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHjqdyGOKHh_rzFwylDINQ1q11jApztsCyES8qHrEWoAyfT0vdTf5l9s_AE5-AoavN2nUUIPbeotBG_E8KZW4uqw-pGP1bEiNHIrBSK51BxI1xioHINdMaeo3Bnrtvk1ElCy0zObR0A9TMHed8J3rUQ0pEPrEBiTIJ_y5riCpsYMoqwS3FKAaEJDvldEZyq6rylh4HEih1KKbPzqQ==), [ifs.com (Compliance)](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFPchKuHvCdhHV0YL5SP_xaKg7ew8YGvmSIhVughqMAmCm6cu89xCgqjz0PSwTYjnq8yiHGtVs9sXv8UTqjNU7_K48P3g55WilIvnC3I1dgUduDdSidhVFwBPI7w_KiOJrmPkgauI1TWa232MTbZSrR1k8L8VbJxRihCo9YzwVibgu1-LZFTv3oYMlCmdGo8qJleF-0_chzgU7aulF2HqHQ3oAjmLCarbE=)
   - Document Classes driving numbering and metadata, Object Connections attaching manuals/blueprints directly to Equipment and Standard Jobs, four-stage revision lifecycle (`Draft -> Approval -> Released -> Obsolete` supersession), and technician qualification matrices for high-risk dispatching.
6. **Hexagon HxGN EAM & HxGN SDx** — [swainsmith.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH3keLZroSo3bxuYZfB8tufh7pTYwAqZ0NdOah-Mt_Ul4r15UOuyg3TdoE3fbHPRXzXoO76Z9L45otDBPkfxxd7sA54HavKYxza0Qkv0OethZ82PuFV-jpnCM7pKvSnBmZud1CUAK-1xEve-3li3cj5imE=), [21tech.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFu6NIDOp8Biyjn1qCD4a8x4h_MGLmcHDWSFQ0Xhnqb0s5zuCrdAAS7qx3Pn2RKgiGwHyVOjkhSPE4cp0UCauuyZXfGc-TBqH7x4LLPkmg7RxC9WmiZFs7PjkaPX7WGw0GYy7QpM7f6y1nI8iwC)
   - Tag-based P&ID/manual delivery at the point of maintenance work, safety permits with LOTO energy isolation points and precautions gating task sign-off, craft/certification expiry enforcement, and non-conformity logs paired with problem-cause-remedy failure analysis.
7. **MaintainX** — [getmaintainx.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEAaB_G9olR_DJdIeGZMaLNTk_3yG_t6VV5hngLPcJSb4PpiGeFOjfM9oNQ38jnJ-yISOUR11FgxxawMoV-AiPSEVfazkp_NBuJ_MrS_krQyeUbFByCDPk2qfpT6X1bP_h9InvUTgRWUXL7w_LLRA==), [getmaintainx.com (Procedures)](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFN59jlelxe38jSCZCeckNPQTZF4sNUKHdJo-RwShAfWIBwmKtjrGSwjyKwzlsDrSCHifkN-kOvfU6rPlBONUjcr_ZRAfhi-P9AQyUYdxaNYsvpUaLbc5LBOATYRcK2MWxtBQ-VfQ8WGnUVwb8=)
   - Frontline step-by-step Procedure Builder with conditional checks and mandatory sign-offs, embedded LOTO hazard warnings and sign-off gates before completion, searchable procedure/work-order troubleshooting knowledge base, and recurring anomaly RCA reviews.
8. **Fiix (Rockwell Automation)** — [morsa.ai](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG-PP6eoe5LioU2lkGEozKwzmL-z3bxP34kiOd4IiKcikNiJNj2OoY4KgUS8nOdx3z8BfjliI9cKVhj28eu4ZpJcH092a7U169HXz4wX43YVNJ94SMR_AmyqBie6ZRnq0CDup0l1gKa2id0hdSjAa5iBaMI), [fabrico.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGDoU2H_L-VYLGQhzO2PheEkzgS7orPqLNFe-8aUqTn3OHeiRpib11kIYr_x8qCi7Iz6wfS8Ga7f_Q0mtt_f3cR4LjymobvYgIAr5dTuXfWB9DFWAqreNjbB7gn16JfOWkbC4CsEcwFokIn4adb_rv4oME0iTtg)
   - Enterprise PM SOP attachment and LOTO verification cross-referenced to asset IDs, technician skill/certification mapping restricting uncertified sign-off on high-risk tasks, and structured failure-code hierarchies driving reliability analytics.
9. **Limble CMMS & UpKeep** — [morsa.ai](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG-PP6eoe5LioU2lkGEozKwzmL-z3bxP34kiOd4IiKcikNiJNj2OoY4KgUS8nOdx3z8BfjliI9cKVhj28eu4ZpJcH092a7U169HXz4wX43YVNJ94SMR_AmyqBie6ZRnq0CDup0l1gKa2id0hdSjAa5iBaMI), [fabrico.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGDoU2H_L-VYLGQhzO2PheEkzgS7orPqLNFe-8aUqTn3OHeiRpib11kIYr_x8qCi7Iz6wfS8Ga7f_Q0mtt_f3cR4LjymobvYgIAr5dTuXfWB9DFWAqreNjbB7gn16JfOWkbC4CsEcwFokIn4adb_rv4oME0iTtg)
   - Clean equipment-card document libraries (manuals, schematics, parts lists), drag-and-drop SOP checklists with mandatory LOTO sign-off steps, asset-to-labor qualification mapping, and accessible MTBF/MTTR failure tracking feeding RCA.
10. **Fracttal One** — [fracttal.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGbhHHwhkQW-4gWFWbQ_SDMMAjseYkdlXFA17nXMT-WXedy6ZFVWRAf2SnY9i9Evj008e4UalJQjBzQJeJwcZ4ez4FQXSiVo-0XHxUvfHVez6uwXOlzD_d4If6tJH7dmPJW2BjnTvifENYRYagZFhHn-DI5GsvP2OulWhHtvK19b4cD9_dwQgv2tyUs26h0LaNWuMDS)
    - Field access to verified equipment manuals and P&IDs during work execution, LOTO safety cross-references, and structured capture of failure codes, downtime hours, and sensor anomalies into post-incident RCA records.

---

## Feature catalog (this sub-module only)

### 1. Asset Documentation Repository
*(Manuals, schematics, warranties, and certificates centralized storage)*

| Feature | Seen in | Priority | Spine reuse | Status |
|---|---|---|---|---|
| Centralized controlled document register typed by Document Class (OEM manual, P&ID/electrical schematic, datasheet, warranty certificate, calibration/inspection certificate, vendor transmittal, as-built record) | IBM Maximo, IFS Cloud, Accruent Meridian, OpenText xECM | Must | `scm.Asset`, `accounting.FixedAsset`, `assets.AssetModel`, `assets.AssetCategory`, `assets.AssetWarranty`, `assets.AssetComplianceFramework`, `core.Party`, `core.OrgUnit`, optional `core.Document` | Buildable now |
| Safe file upload + integrity metadata (`FileField`, SHA-256 checksum, byte size, original filename, MIME/extension allowlist via `ALLOWED_DOC_EXTENSIONS` excluding `.svg`, 20 MB cap) | OpenText xECM, Accruent Meridian, NavERP `7.10`/`6.19` pattern | Must | `apps/core/forms/_common.py` | Buildable now |
| Equipment tag & vendor reference indexing (`tag_code`, `manufacturer_ref`, `document_language`, `storage_location_ref`) plus search/filter by class, status, asset, category, model, site | Accruent Meridian, HxGN EAM, Limble, UpKeep | Must | `scm.Asset`, `core.OrgUnit` | Buildable now |
| Validity window, certificate expiration tracking (`effective_date`, `expiry_date`, `retention_years`), and expiring-soon indicator | IFS Cloud, OpenText xECM, NavERP `AssetCalibrationRecord` | Should | — | Buildable now |
| Access classification (`public_floor`, `internal_tech`, `restricted_engineering`, `confidential_vendor`) and printable document control sheet | OpenText xECM, IFS Cloud | Should | `core.Document` classification pattern | Buildable now |
| Optical character recognition (OCR) full-text PDF indexing & AI manual chat | OpenText xECM, MaintainX | Defer | — | Integration/later (`Module 13` / `11.19`) |

### 2. Version Control & Change Management
*(Drawing revisions, specification updates, and approval workflows)*

| Feature | Seen in | Priority | Spine reuse | Status |
|---|---|---|---|---|
| Immutable revision chain (`revision_label`, `revision_sequence`, `supersedes` self-FK, `is_current_revision` flag) separating WIP drafts from released As-Built masters and obsolete copies | Accruent Meridian, IFS Cloud, SAP DMS | Must | Self-FK on `AssetDocument` | Buildable now |
| Engineering Change / MOC linkage (`change_request_ref`, `change_type`: new issue / drawing redline / spec update / vendor bulletin / regulatory update / as-built reconcile) | Accruent Meridian, SAP ECM, OpenText xECM | Must | `assets.AssetSpecificationTemplate` | Buildable now |
| Field redlining & specification delta capture (`redline_summary`, `spec_delta_notes`) so field markups and tolerance/spec edits are audited prior to release | Accruent Meridian, OpenText xECM | Must | `assets.AssetSpecificationTemplate` | Buildable now |
| Structured review & release approval workflow (`draft -> in_review -> approved -> superseded -> archived`) with `reviewer`, `approved_by`, `approved_at`, `review_notes`, revision lock on released records, and atomic supersession on release | IBM Maximo, IFS Cloud, Accruent Meridian | Must | `accounts.User` (`settings.AUTH_USER_MODEL`), `core.AuditLog` pattern | Buildable now |
| Cooperative advisory check-out / check-in lock (`checked_out_by`, `checked_out_at`) preventing concurrent overwrite during WIP edits | Accruent Meridian, OpenText xECM | Should | `accounts.User` | Buildable now |
| One-click "Create New Revision" workflow cloning metadata into a new draft revision linked via `supersedes` | IFS Cloud, Accruent Meridian | Should | Self-FK on `AssetDocument` | Buildable now |
| In-browser CAD/DWG redline canvas annotation & geometric layer diffing | Accruent Meridian, HxGN SDx | Defer | — | Sibling `11.17 Spatial & CAD Integration` |

### 3. SOP & Procedure Management
*(Standard operating procedures, maintenance protocols, and safety instructions)*

| Feature | Seen in | Priority | Spine reuse | Status |
|---|---|---|---|---|
| Controlled SOP & maintenance protocol register (`procedure_type`: SOP operation, PM protocol, LOTO isolation, emergency shutdown, commissioning, calibration protocol, inspection checklist) | MaintainX, Limble, IFS Cloud, Fiix | Must | `scm.Asset`, `assets.AssetCategory`, `assets.AssetModel`, `assets.AssetMaintenanceSchedule`, `assets.AssetComplianceFramework`, `core.OrgUnit` | Buildable now |
| Ordered step-by-step execution instructions (`procedure_steps` JSON list: step number, title, instruction, expected reading/tolerance, mandatory sign-off flag) | MaintainX, Limble, IFS Cloud | Must | — | Buildable now |
| LOTO (Lockout/Tagout) & hazardous energy control block (`safety_level`, `loto_required`, `loto_isolation_points` JSON list of energy source / tag / isolation point / lock device / zero-energy verification step, `hazard_warnings`, `required_ppe`) | SAP WCM, HxGN EAM, MaintainX, Fiix | Must | `assets.AssetComplianceFramework` | Buildable now |
| Required qualification/competency tag (`required_qualification_code`) and estimated duration (`estimated_duration_minutes`) plus linked master drawing/manual (`primary_document`) | IBM Maximo, IFS Cloud, HxGN EAM | Should | `AssetDocument` | Buildable now |
| SOP revision & periodic safety review lifecycle (`draft -> under_review -> active -> superseded -> retired`, `revision_label`, `supersedes`, `effective_date`, `review_cycle_months`, `next_review_date`) | MaintainX, OpenText xECM, IFS Cloud | Must | `accounts.User` | Buildable now |
| Printable shop-floor SOP & LOTO sheet for physical posting at point of work | MaintainX, Limble, HxGN EAM | Should | — | Buildable now |

### 4. Training & Certification Records
*(Operator certifications, maintenance qualifications, and renewal alerts)*

| Feature | Seen in | Priority | Spine reuse | Status |
|---|---|---|---|---|
| Equipment- and hazard-specific operator/technician qualification register (`qualification_type`: equipment operator, maintenance tech, LOTO authorized, high-voltage electrical, confined space, crane/rigging, pressure vessel welding, calibration specialist, OEM certified; `proficiency_level`) | IBM Maximo, IFS Cloud, HxGN EAM, Fiix | Must | `core.Party` (`person`), `accounts.User`, optional `hrm.EmployeeProfile` & `hrm.TrainingCertificate` | Buildable now |
| Scope binding to specific asset, asset category, asset model, and/or controlled SOP (`operational_asset`, `asset_category`, `asset_model`, `operating_procedure`, `compliance_framework`) | IFS Cloud, Fiix, Limble, HxGN EAM | Must | `scm.Asset`, `assets.AssetCategory`, `assets.AssetModel`, `AssetOperatingProcedure`, `assets.AssetComplianceFramework` | Buildable now |
| Credential traceability & evidence (`issuing_authority`, `issuing_party`, `certificate_reference`, `certificate_file` upload, `training_hours`, `assessment_score`) and SOP read-and-acknowledge stamp (`sop_acknowledged`, `sop_acknowledged_at`) | OpenText Document Training, UpKeep, IBM Maximo | Must | `core.Party` (`organization`), `accounts.User` | Buildable now |
| Expiry & renewal alerting (`issued_date`, `expires_on`, `renewal_lead_days`, computed `days_until_expiry`, `is_expired`, `is_renewal_due`, automated/on-demand `expiring_soon` / `expired` status sync + `renew` & `revoke` POST actions) | HxGN EAM, IFS Cloud, NavERP `AssetCalibrationRecord` | Must | — | Buildable now |
| Reusable qualification-check helper (`is_operator_certified(...)`) for future work-order dispatch gating | IBM Maximo, HxGN EAM, SAP EAM | Should | `AssetOperatorCertification` | Buildable now (integration hook exposed; `11.5`/`11.13` hard block deferred) |
| Corporate LMS course catalog, quiz engines, and seat enrollment | OpenText, NavERP HRM `3.22`–`3.24` | Parked | `hrm.TrainingCourse`, `hrm.TrainingCertificate` | Sibling HRM `3.22`–`3.24` |

### 5. Lessons Learned & Failure Analysis
*(Post-incident reviews, root cause analysis, and knowledge base articles)*

| Feature | Seen in | Priority | Spine reuse | Status |
|---|---|---|---|---|
| Post-incident RCA & reliability knowledge base (`article_type`: RCA post-incident, lessons learned, troubleshooting guide, failure bulletin, OEM service advisory, PM optimization note; `severity`) | Fracttal, MaintainX, HxGN EAM, IBM Maximo | Must | `scm.Asset`, `accounting.FixedAsset`, `assets.AssetCategory`, `assets.AssetModel`, `core.OrgUnit` | Buildable now |
| Structured Problem-Cause-Remedy + 5-Why & Fishbone (6M) capture (`symptom_problem`, `root_cause_summary`, `five_whys` JSON, `contributing_factors` JSON for machine/method/material/manpower/measurement/environment, `remedy_corrective_action`, `preventive_lessons`) | IBM Maximo, SAP APM, Fracttal, HxGN EAM | Must | `assets.AssetFailureMode` (`AFMA-`), `assets.AssetMaintenanceRequest`, `assets.AssetMaintenanceLog`, `assets.AssetIncidentReport`, `assets.AssetComplianceIncident` | Buildable now |
| Recurrence & impact context (`downtime_hours_impacted`, `recurrence_count`), cross-links to affected drawing (`related_document`) and updated SOP (`recommended_procedure`) | Accruent Meridian, OpenText xECM, Limble, Fiix | Must | `AssetDocument`, `AssetOperatingProcedure` | Buildable now |
| Searchable troubleshooting tags (`tags`), `helpful_votes` / `view_count` feedback counters, and peer-review publishing workflow (`draft -> peer_review -> published -> retired`) | MaintainX, Limble, IFS Cloud | Should | `accounts.User` | Buildable now |

### Beyond the bullets (differentiators across leaders)
- **Single-pane cross-linking between Documents, SOPs, Certifications, and RCAs:** On any document/SOP/article detail view, technicians can see linked revisions, applicable SOPs/LOTO steps, certified operators, and prior RCA lessons learned for the same equipment/model.
- **CSV register export & KPI filter chips on list pages:** Matches `apps/assets` `11.14` / `11.11` polish (overdue reviews, expiring documents/certifications, pending ECN approvals, published KB lessons) with sanitized CSV formula neutralization.

---

## Recommended build scope (this pass — 4 models)

Mirroring `apps/assets` `11.1`–`11.15` (four `TenantNumbered` models per sub-module, strictly within the 1–4 model scope), place all four models in `apps/assets/models/AssetDocumentKnowledge/`:

### 1. `AssetDocument` (`NUMBER_PREFIX = "ADOC"`, `AssetDocuments.py`)
- **Purpose:** Centralized controlled asset document repository AND engineering revision / MOC approval lifecycle (covers NavERP bullets 1 & 2).
- **Key fields & choices:**
  - `title` (`CharField(200)`), `document_class` (`manual`, `schematic_pid`, `electrical_diagram`, `datasheet`, `warranty_cert`, `calibration_cert`, `compliance_cert`, `inspection_dossier`, `vendor_transmittal`, `as_built_drawing`), `tag_code` (`CharField(80)`), `manufacturer_ref` (`CharField(120)`), `document_language` (`CharField(32)`, default `"en"`), `access_classification` (`public_floor`, `internal_tech`, `restricted_eng`, `confidential`).
  - File & integrity: `file` (`FileField`, validated via `ALLOWED_DOC_EXTENSIONS` excluding `.svg` & `MAX_UPLOAD_BYTES` 20 MB), `original_filename`, `file_size_bytes`, `file_checksum` (SHA-256).
  - Revision & Change Management: `revision_label` (`CharField(24)`, default `"Rev A"`), `revision_sequence` (`PositiveIntegerField(default=1)`), `supersedes` (`ForeignKey("self", SET_NULL, null=True, blank=True, related_name="superseded_by_revisions")`), `is_current_revision` (`BooleanField(default=True)`), `change_request_ref` (`CharField(64)`, ECN/ECR/MOC ID), `change_type` (`new_issue`, `drawing_redline`, `spec_update`, `vendor_bulletin`, `regulatory_update`, `as_built_reconcile`), `redline_summary` (`TextField`), `spec_delta_notes` (`TextField`).
  - Cooperative lock & lifecycle: `checked_out_by` (`AUTH_USER_MODEL`, null/blank), `checked_out_at` (`DateTimeField`, null/blank), `effective_date` (`DateField`), `expiry_date` (`DateField`, null/blank), `retention_years` (`PositiveSmallIntegerField`, null/blank), `status` (`draft`, `in_review`, `approved`, `superseded`, `archived`), `owner` (`AUTH_USER_MODEL`), `reviewer` (`AUTH_USER_MODEL`), `approved_by` (`AUTH_USER_MODEL`), `approved_at` (`DateTimeField`), `review_notes` (`TextField`), `description` (`TextField`).
- **Verified FKs (all tenant-validated in `clean()`):** `core.Tenant`, `core.OrgUnit`, `scm.Asset`, `accounting.FixedAsset`, `assets.AssetModel`, `assets.AssetCategory`, `assets.AssetSpecificationTemplate`, `assets.AssetWarranty`, `assets.AssetComplianceFramework`, `core.Party` (`vendor_party`), `core.Document` (`core_document`), `accounts.User` (`owner`, `checked_out_by`, `reviewer`, `approved_by`), `self` (`supersedes`).
- **Constraints/Indexes (all `<= 30` chars):** `assets_adoc_ten_num_uniq`, `idx_adoc_ten_stat`, `idx_adoc_ten_cls`, `idx_adoc_ten_ast`, `idx_adoc_ten_exp`, `idx_adoc_ten_cur`.
- **Actions (POST):** `submit_review`, `approve_release` (atomically marks superseded predecessor `status="superseded"` and `is_current_revision=False`), `return_to_draft`, `checkout_lock`, `checkin_release`, `create_revision` (clones metadata into next `revision_sequence` draft linked via `supersedes`), `archive`.
- **Badge CSS (`STATUS_CSS`):** `draft -> badge-slate`, `in_review -> badge-amber`, `approved -> badge-green`, `superseded -> badge-muted`, `archived -> badge-muted`.

### 2. `AssetOperatingProcedure` (`NUMBER_PREFIX = "ASOP"`, `AssetOperatingProcedures.py`)
- **Purpose:** Controlled standard operating procedures, preventive maintenance protocols, and LOTO energy-isolation safety instructions (covers NavERP bullet 3).
- **Key fields & choices:**
  - `title` (`CharField(200)`), `procedure_type` (`sop_operation`, `pm_protocol`, `loto_isolation`, `emergency_shutdown`, `commissioning`, `calibration_protocol`, `inspection_checklist`), `safety_level` (`standard`, `caution`, `high_hazard_loto`, `permit_required`), `revision_label` (`CharField(24)`, default `"Rev 1.0"`), `supersedes` (`ForeignKey("self", ...)`).
  - Safety & step structure: `purpose_scope` (`TextField`), `hazard_warnings` (`TextField`), `required_ppe` (`CharField(255)`), `loto_required` (`BooleanField(default=False)`), `loto_isolation_points` (`JSONField(default=list)` — validated list of `{energy_source, tag_id, isolation_point, lock_device, verification_step}`), `procedure_steps` (`JSONField(default=list)` — validated list of `{step_no, title, instruction, expected_reading, is_mandatory_signoff}`), `required_qualification_code` (`CharField(64)`), `estimated_duration_minutes` (`PositiveIntegerField(default=30)`), `attachment` (`FileField`, safe upload validation).
  - Review & lifecycle: `effective_date` (`DateField`), `review_cycle_months` (`PositiveIntegerField(default=12)`), `next_review_date` (`DateField`, null/blank), `status` (`draft`, `under_review`, `active`, `superseded`, `retired`), `author` / `safety_reviewer` / `approved_by` (`AUTH_USER_MODEL`), `approved_at` (`DateTimeField`), `review_notes` (`TextField`).
- **Verified FKs (all tenant-validated in `clean()`):** `core.Tenant`, `core.OrgUnit`, `scm.Asset`, `assets.AssetCategory`, `assets.AssetModel`, `assets.AssetMaintenanceSchedule`, `assets.AssetComplianceFramework`, `assets.AssetDocument` (`primary_document`), `self` (`supersedes`), `accounts.User` (`author`, `safety_reviewer`, `approved_by`).
- **Constraints/Indexes (`<= 30` chars):** `assets_asop_ten_num_uniq`, `idx_asop_ten_stat`, `idx_asop_ten_type`, `idx_asop_ten_haz`, `idx_asop_ten_rev`.
- **Actions (POST):** `submit_review`, `activate` (validates `loto_required` has isolation points or hazard warnings; atomically supersedes predecessor if set), `clone_revision`, `retire`, plus printable shop-floor SOP view.
- **Badge CSS (`STATUS_CSS`):** `draft -> badge-slate`, `under_review -> badge-amber`, `active -> badge-green`, `superseded -> badge-muted`, `retired -> badge-muted`; `SAFETY_CSS`: `standard -> badge-slate`, `caution -> badge-info`, `high_hazard_loto -> badge-red`, `permit_required -> badge-amber`.

### 3. `AssetOperatorCertification` (`NUMBER_PREFIX = "AOCT"`, `AssetOperatorCertifications.py`)
- **Purpose:** Equipment- and hazard-specific operator & maintenance technician qualifications, SOP acknowledgments, and expiry/renewal alerts (covers NavERP bullet 4).
- **Key fields & choices:**
  - `title` (`CharField(200)`), `qualification_code` (`CharField(64)`), `qualification_type` (`equipment_operator`, `maintenance_technician`, `loto_authorized`, `electrical_hv`, `confined_space`, `crane_rigging`, `pressure_welding`, `calibration_specialist`, `oem_certified`), `proficiency_level` (`trainee_supervised`, `qualified_operator`, `senior_technician`, `lead_inspector`, `trainer_assessor`).
  - Personnel & authority: `operator_party` (`core.Party`), `operator_user` (`AUTH_USER_MODEL`), `employee_profile` (`hrm.EmployeeProfile`, optional), `hrm_certificate` (`hrm.TrainingCertificate`, optional), `issuing_authority` (`CharField(150)`), `issuing_party` (`core.Party`, optional), `certificate_reference` (`CharField(80)`), `certificate_file` (`FileField`, safe upload validation).
  - Validity & alerts: `issued_date` (`DateField`), `expires_on` (`DateField`, null/blank), `renewal_lead_days` (`PositiveSmallIntegerField(default=30)`), `last_assessed_date` (`DateField`, null/blank), `assessor` (`AUTH_USER_MODEL`), `training_hours` (`DecimalField(6, 2)`, >= 0), `assessment_score` (`DecimalField(5, 2)`, 0–100 optional), `sop_acknowledged` (`BooleanField(default=False)`), `sop_acknowledged_at` (`DateTimeField`, null/blank), `notes` (`TextField`), `status` (`pending`, `active`, `expiring_soon`, `expired`, `revoked`).
- **Verified FKs (all tenant-validated in `clean()`):** `core.Tenant`, `core.OrgUnit`, `core.Party` (`operator_party`, `issuing_party`), `accounts.User` (`operator_user`, `assessor`), `hrm.EmployeeProfile`, `hrm.TrainingCertificate`, `scm.Asset`, `assets.AssetCategory`, `assets.AssetModel`, `assets.AssetOperatingProcedure`, `assets.AssetComplianceFramework`.
- **Clean rules & helpers:** `clean()` requires at least one person reference (`operator_party`, `operator_user`, or `employee_profile`), `expires_on >= issued_date` when set, `assessment_score` in `0..100`, and tenant consistency across all FKs. Properties `days_until_expiry`, `is_expired`, `is_renewal_due`, method `sync_expiry_status()`, and helper `is_operator_certified(...)`.
- **Constraints/Indexes (`<= 30` chars):** `assets_aoct_ten_num_uniq`, `idx_aoct_ten_stat`, `idx_aoct_ten_type`, `idx_aoct_ten_exp`, `idx_aoct_ten_usr`, `idx_aoct_ten_pty`.
- **Actions (POST):** `verify_activate`, `acknowledge_sop`, `renew_certification`, `revoke`, `refresh_expiry_alerts`.
- **Badge CSS (`STATUS_CSS`):** `pending -> badge-slate`, `active -> badge-green`, `expiring_soon -> badge-amber`, `expired -> badge-red`, `revoked -> badge-muted`.

### 4. `AssetKnowledgeArticle` (`NUMBER_PREFIX = "AKBA"`, `AssetKnowledgeArticles.py`)
- **Purpose:** Post-incident reviews, structured Root Cause Analysis (Problem-Cause-Remedy, 5-Why, Fishbone 6M), and equipment troubleshooting knowledge base (covers NavERP bullet 5).
- **Key fields & choices:**
  - `title` (`CharField(200)`), `article_type` (`rca_post_incident`, `lessons_learned`, `troubleshooting_guide`, `failure_bulletin`, `oem_service_advisory`, `pm_optimization_note`), `rca_methodology` (`five_whys`, `fishbone_ishikawa`, `problem_cause_remedy`, `fmea_feedback`, `fault_tree`, `general_kb`), `severity` (`low`, `medium`, `high`, `critical`).
  - Failure & RCA analysis: `symptom_problem` (`TextField`), `root_cause_summary` (`TextField`), `five_whys` (`JSONField(default=list)` — validated list of `{why_level, question, answer}`), `contributing_factors` (`JSONField(default=dict)` — validated Fishbone 6M keys `machine`, `method`, `material`, `manpower`, `measurement`, `environment`), `remedy_corrective_action` (`TextField`), `preventive_lessons` (`TextField`), `downtime_hours_impacted` (`DecimalField(8, 2)`, >= 0), `recurrence_count` (`PositiveIntegerField(default=1)`), `tags` (`CharField(255)`), `helpful_votes` (`PositiveIntegerField(default=0)`), `view_count` (`PositiveIntegerField(default=0)`), `attachment` (`FileField`, safe upload validation).
  - Lifecycle: `incident_occurred_on` (`DateField`, null/blank), `status` (`draft`, `peer_review`, `published`, `retired`), `author` (`AUTH_USER_MODEL`), `reviewed_by` (`AUTH_USER_MODEL`), `published_at` (`DateTimeField`, null/blank).
- **Verified FKs (all tenant-validated in `clean()`):** `core.Tenant`, `core.OrgUnit`, `scm.Asset`, `accounting.FixedAsset`, `assets.AssetCategory`, `assets.AssetModel`, `assets.AssetFailureMode`, `assets.AssetMaintenanceRequest`, `assets.AssetMaintenanceLog`, `assets.AssetIncidentReport`, `assets.AssetComplianceIncident`, `assets.AssetDocument` (`related_document`), `assets.AssetOperatingProcedure` (`recommended_procedure`), `accounts.User` (`author`, `reviewed_by`).
- **Constraints/Indexes (`<= 30` chars):** `assets_akba_ten_num_uniq`, `idx_akba_ten_stat`, `idx_akba_ten_type`, `idx_akba_ten_sev`, `idx_akba_ten_rca`, `idx_akba_ten_ast`.
- **Actions (POST):** `submit_review`, `publish`, `mark_helpful` (atomic `F("helpful_votes") + 1`), `retire`.
- **Badge CSS (`STATUS_CSS`):** `draft -> badge-slate`, `peer_review -> badge-amber`, `published -> badge-green`, `retired -> badge-muted`; `SEVERITY_CSS`: `low -> badge-slate`, `medium -> badge-info`, `high -> badge-amber`, `critical -> badge-red`.

### Recommended `LIVE_LINKS["11.16"]` mapping (exact NavERP.md bullets)
- `"Asset Documentation Repository"` -> `("assets:asset_document_list", ())`
- `"Version Control & Change Management"` -> `("assets:asset_document_change_list", ())` (dedicated MOC / revision-review queue view filtered to drafts/in-review/superseded chains, ensuring 1-to-1 distinct sidebar highlighting via `_route_score` in `apps/core/navigation.py`)
- `"SOP & Procedure Management"` -> `("assets:asset_operating_procedure_list", ())`
- `"Training & Certification Records"` -> `("assets:asset_operator_certification_list", ())`
- `"Lessons Learned & Failure Analysis"` -> `("assets:asset_knowledge_article_list", ())`

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **11.17 Spatial & CAD Integration:** Interactive 2D/3D CAD/BIM drawing viewer, AutoCAD/Revit layer toggling, floor-plan spatial pins, and canvas geometric redlining.
- **11.18 Sustainability & ESG:** Carbon/ESG audit dossiers and environmental emissions disclosures.
- **11.19 AI & Predictive Intelligence:** LLM/RAG chat over OEM manuals, automated predictive anomaly detection, and AI failure prediction.
- **11.3 Asset Classification & Taxonomy / 11.5 Maintenance / 11.7 Reliability / 11.8 Warranties / 11.11 Compliance:** Defining attribute templates (`AssetSpecificationTemplate`), executing PM/CM work orders (`AssetMaintenanceRequest`), calculating FMEA RPN (`AssetFailureMode`), processing financial warranty claims (`AssetWarrantyClaim`), and managing statutory permits (`AssetPermitLicense`); `11.16` connects to those records via nullable FKs rather than absorbing their workflows.
- **Module 3 HRM (`3.22`–`3.24` Training Management / LMS / Training Admin, `3.36` Helpdesk, `3.39` Policy):** Employee LMS courses, course-completion tracking, general HR FAQs, and corporate HR policies; `11.16` links optionally to `hrm.EmployeeProfile` and `hrm.TrainingCertificate` while owning equipment/hazard qualifications.
- **Module 12 Quality Management (`12.1` Document Control, `12.4` CAPA, `12.12` Quality Training) & Module 13 Document Management (`13.1`–`13.19` Enterprise DMS, OCR, DRM/Watermarking, Enterprise Wikis, Retention Purging):** Neither app exists yet; cross-enterprise non-asset document control, DRM, OCR pipelines, and automated legal hold/purging stay parked for Modules 12 and 13.

---

## Deferred (later passes / integrations)

- **Hard work-order dispatch enforcement (`11.5` / `11.13`):** Blocking `AssetMaintenanceRequest` or `FieldWorkOrder` assignment unless the technician holds an active `AssetOperatorCertification`; `11.16` ships the reusable `is_operator_certified(...)` check without altering existing `11.5`/`11.13` views.
- **Scheduled expiry notifications & automated review reminders:** Asynchronous email/in-app dispatch (Celery/cron) for upcoming `AssetOperatorCertification` expirations, `AssetDocument` expirations, and `AssetOperatingProcedure` periodic safety reviews; in-app renewal alerts and on-demand status sync ship in this pass.
- **External EDMS bi-directional connectors & OCR indexing:** Webhook/API sync with Accruent Meridian / SharePoint / OpenText or OCR full-text extraction of scanned PDFs (`11.15` connector extension / `Module 13`).
- **21 CFR Part 11 cryptographic e-signatures & PDF watermarking:** Multi-factor signature challenge and watermark overlay on controlled downloads (`Module 12` / `Module 13`).
