# Review Findings: Sub-module 13.10 — Audit Trail & Reporting (`apps/documents/`)

**Changeset**: `36b7962ee269904d6d3affe02ef40ed5080fd945...HEAD`  
**Contract**: `.claude/tasks/contract-documents-13.10.md`  

---

## 1. Code Reviewer Pass

- [ ] **[C1] Missing Cross-Tenant FK Validation & Inverted Form Signatures**
  - **File**: `apps/documents/forms/AuditReporting/ChainOfCustodyExports.py:53-63` & `apps/documents/forms/AuditReporting/DocumentSecurityAlerts.py:29-34`
  - Inverted `__init__` signature `(self, tenant=None, *args, **kwargs)` breaks positional binding, missing `self.tenant = tenant`, and missing `reject_foreign` validation in form `clean()`.
  - Fix: Change signatures to `def __init__(self, *args, tenant=None, **kwargs):`, store `self.tenant = tenant`, and call `reject_foreign(...)` in `clean()`.

- [ ] **[C2] Evidence Package Number Blank in Manifest & Cryptographic Hash**
  - **File**: `apps/documents/models/AuditReporting/ChainOfCustodyExports.py:224-266`
  - `generate_manifest()` executed before `TenantNumbered.save()` assigns `self.number`, leaving `manifest_json["package_number"] = ""` permanently.
  - Fix: Allocate `self.number` before `generate_manifest()` if not already set.

- [ ] **[I1] Invalid Theme CSS Classes: `badge-purple` in Detail Templates**
  - **Files**: `templates/documents/audit_reporting/report_definition/detail.html:24` & `templates/documents/audit_reporting/chain_of_custody/detail.html:124`
  - `badge-purple` does not exist in `static/css/theme.css`.
  - Fix: Replace with `badge-info` or `badge-slate`.

- [ ] **[I2] Missing Filter & Search Bar in Chain of Custody Package List Template**
  - **File**: `templates/documents/audit_reporting/chain_of_custody/list.html:70-80`
  - Template omits filter card for `q`, `framework`, and `status`.
  - Fix: Add standard `<form method="get">` filter bar.

- [ ] **[I3] Superficial Package Hash Verification in `custody_export_detail`**
  - **File**: `apps/documents/views/AuditReporting/ChainOfCustodyExports.py:103-104`
  - `is_hash_valid` checks truthiness instead of recomputing SHA-256 digest over `manifest_json`.
  - Fix: Recompute SHA-256 and compare against `package_hash`.

- [ ] **[I4] Code Duplication Bypassing Service Layer in `security_alert_scan`**
  - **File**: `apps/documents/views/AuditReporting/DocumentSecurityAlerts.py:139-227`
  - View duplicates logic instead of calling `apps/documents/services/audit.py:run_heuristic_anomaly_scan`.
  - Fix: Refactor view to call service helper.

- [ ] **[I5] Missing Scope Validation in `ChainOfCustodyExportForm`**
  - **File**: `apps/documents/forms/AuditReporting/ChainOfCustodyExports.py:53-64`
  - `document` and `folder` not conditionally enforced based on selected `scope`.
  - Fix: Add conditional validation in `clean()`.

- [ ] **[M1] Missing Filter Inputs and Pagination Query Parameter Preservation**
  - **Files**: `templates/documents/audit_reporting/audit_trail/list.html`, `security_alert/list.html`, `report_definition/list.html`, `chain_of_custody/list.html`
  - Filter forms lack certain date/type inputs; pagination links drop active GET query parameters.
  - Fix: Add missing filter fields and ensure pagination links preserve all GET parameters.

- [ ] **[M2] Contract Drift in `audit_report_create` View Context**
  - **File**: `apps/documents/views/AuditReporting/AuditReportDefinitions.py:64-67`
  - View omits `"report_def": None` from context.
  - Fix: Add `"report_def": None` in context.

- [ ] **[M3] External Auditor Portal Ignores Multi-Document Scope Date Ranges**
  - **File**: `apps/documents/views/AuditReporting/ChainOfCustodyExports.py:203-209`
  - When `document` is None, `audit_trail` is defaulted to empty list even if `start_date` and `end_date` are set.
  - Fix: Filter `DocumentAuditTrail` by date range when document is None.

---

## 2. Explorer Reviewer Pass

- [ ] **[EXP-I1] Missing `avg_approval_hours` Context Key in `document_lifecycle_dashboard` & Hardcoded Velocity KPI**
  - **File**: `apps/documents/views/AuditReporting/AuditReportingDashboard.py:99-108` & `templates/documents/audit_reporting/lifecycle_dashboard.html:50-52`
  - Contract Section 3.5 explicitly pins `lifecycle_kpis` context keys as `(avg_approval_hours, bottleneck_stages, high_churn_docs, status_distribution)`. Omitted from view context and hardcoded as `18.4 hrs` in template.
  - Fix: Calculate or supply `avg_approval_hours` in `lifecycle_kpis` dict and bind `{{ lifecycle_kpis.avg_approval_hours|default:"18.4" }} hrs` in template.

- [ ] **[EXP-I2] Omission of 13.10 Models from `--flush` in `seed_documents.py`**
  - **File**: `apps/documents/management/commands/seed_documents.py:68-105`
  - The `--flush` command in seeder deletes 13.1 to 13.9 models but omits 13.10 models (`ChainOfCustodyExport`, `DocumentSecurityAlert`, `AuditReportDefinition`, `DocumentAuditTrail`), leading to orphaned records on flush.
  - Fix: Add 13.10 models in reverse dependency order to `--flush` routine.

- [ ] **[EXP-M1] Missing `apps/documents/services/__init__.py` Re-exports**
  - **File**: `apps/documents/services/__init__.py:1`
  - `apps/documents/services/audit.py` defines `log_document_event` and `run_heuristic_anomaly_scan`, but `__init__.py` does not re-export them.
  - Fix: Re-export `log_document_event` and `run_heuristic_anomaly_scan` in `services/__init__.py`.

- [ ] **[EXP-M2] Missing Contract Context Key `"passcode_form": None` in `auditor_portal_view`**
  - **File**: `apps/documents/views/AuditReporting/ChainOfCustodyExports.py:211-218`
  - Contract Section 3.4 pins `passcode_form` in context. When session is authenticated (`passcode_required=False`), `passcode_form` is missing from context dict.
  - Fix: Include `"passcode_form": None` in authenticated context dict.

---

## 3. Frontend Reviewer Pass

- [ ] **[FE-I1] Invalid CSS Badge Class `badge-purple` in Detail Templates**
  - **Files**: `templates/documents/audit_reporting/report_definition/detail.html:24` & `templates/documents/audit_reporting/chain_of_custody/detail.html:124`
  - `badge-purple` is non-existent in `static/css/theme.css`.
  - Fix: Replace with `badge-info` (or `badge-slate`).

- [ ] **[FE-I2] Missing Filter & Search Bar in `chain_of_custody/list.html`**
  - **File**: `templates/documents/audit_reporting/chain_of_custody/list.html:70`
  - View parses `q` and `framework` and passes `framework_choices`, but template lacks the GET filter bar card.
  - Fix: Add standard GET filter bar card with `q` search and `framework` select dropdown.

- [ ] **[FE-I3] Incomplete Query Parameter Preservation on Pagination Links**
  - **Files**:
    - `templates/documents/audit_reporting/chain_of_custody/list.html:176,186` (drops `q`, `framework`)
    - `templates/documents/audit_reporting/security_alert/list.html:211,220` (drops `status`, `alert_type`)
    - `templates/documents/audit_reporting/audit_trail/list.html:220,229` (drops `date_from`, `date_to`, `doc_id`)
  - Fix: Preserve all active filter parameters in previous/next page links.

- [ ] **[FE-M1] Missing Filter Form Fields in List Templates**
  - **Files**:
    - `templates/documents/audit_reporting/audit_trail/list.html:86-119` (omits `date_from`, `date_to` date inputs)
    - `templates/documents/audit_reporting/report_definition/list.html:73-97` (omits `status` dropdown)
    - `templates/documents/audit_reporting/security_alert/list.html:76-108` (omits `alert_type` dropdown)
  - Fix: Add the missing filter fields to each respective filter form layout.

- [ ] **[FE-M2] Empty Strong Tag When `report_def.last_run_at` is None**
  - **File**: `templates/documents/audit_reporting/report_definition/detail.html:64`
  - When report has never run, `<strong>{{ report_def.last_run_at|date:"Y-m-d H:i" }}</strong>` renders empty tags.
  - Fix: Add default: `{{ report_def.last_run_at|date:"Y-m-d H:i"|default:"Never" }}`.

- [ ] **[FE-M3] Use Design System Form Groups in `security_alert/form.html`**
  - **File**: `templates/documents/audit_reporting/security_alert/form.html:36`
  - Renders raw `{{ form.as_p }}` rather than explicit `.form-group` markup.
  - Fix: Replace `form.as_p` with standard `.form-group` fields matching the other sub-module forms.

---

## 4. Performance Reviewer Pass

- [ ] **[PERF-C1] N+1 Queries on Document Versions in External Auditor Portal**
  - **File**: `apps/documents/views/AuditReporting/ChainOfCustodyExports.py:204` & `templates/documents/audit_reporting/chain_of_custody/auditor_portal.html:150`
  - `versions` accessed in template loop touching `ver.author` without `select_related("author")`.
  - Fix: Add `.select_related("author")` to `doc.versions.select_related("author").order_by("-created_at")`.

- [ ] **[PERF-C2] Unchunked Evaluation & Lazy-Loading Risk in Cryptographic Hash Verification**
  - **File**: `apps/documents/views/AuditReporting/DocumentAuditTrails.py:120-141`
  - `audit_trail_verify_chain` evaluates all tenant records in memory without chunking; `verify_hash()` may trigger lazy `self.actor` or `self.document` queries if snapshots empty.
  - Fix: Add `.select_related("actor", "document").iterator(chunk_size=2000)`.

- [ ] **[PERF-I1] Report Definition List Query Inflation from Template `.count` Invocations**
  - **File**: `apps/documents/views/AuditReporting/AuditReportDefinitions.py:34-43` & `templates/documents/audit_reporting/report_definition/list.html:46,55,107,175`
  - Unevaluated querysets cause 7 SQL queries via template `.count`.
  - Fix: Materialize `system_reports` and `custom_reports` into lists in view, compute lengths, and pass in context.

- [ ] **[PERF-I2] Triplicate Count Queries for User Statistics in Security Alert Detail**
  - **File**: `apps/documents/views/AuditReporting/DocumentSecurityAlerts.py:98-101`
  - Three separate `.count()` queries scanning `DocumentAuditTrail`.
  - Fix: Combine into single `aggregate(Count("id"), Count("id", filter=Q(...)), ...)`.

- [ ] **[PERF-I3] Triplicate Aggregation Queries in Audit Report Detail Execution**
  - **File**: `apps/documents/views/AuditReporting/AuditReportDefinitions.py:99-103`
  - Separate queries for total, failed, and unique actors.
  - Fix: Combine into single database round-trip using `aggregate()`.

- [ ] **[PERF-I4] Audit Dashboard Redundant Counts & Potential Lazy Loading in Sample Verification**
  - **File**: `apps/documents/views/AuditReporting/AuditReportingDashboard.py:21-35`
  - 2 separate count queries and un-selected related fields on sample verification.
  - Fix: Use single `aggregate()` and add `.select_related("actor", "document")` to sample slice.

- [ ] **[PERF-I5] Missing Composite Indexes on High-Frequency Filter & Sort Combinations**
  - **Files**:
    - `apps/documents/models/AuditReporting/ChainOfCustodyExports.py:175-180` (`["tenant", "is_portal_active", "expires_at"]`)
    - `apps/documents/models/AuditReporting/DocumentSecurityAlerts.py:177-183` (`["tenant", "status", "-detected_at"]`, `["tenant", "target_user", "alert_type", "detected_at"]`)
    - `apps/documents/models/AuditReporting/DocumentAuditTrails.py:173-180` (`["tenant", "document", "-event_timestamp"]`, `["tenant", "actor", "-event_timestamp"]`)
  - Fix: Add these composite `models.Index` declarations to model `Meta.indexes`.

- [ ] **[PERF-M1] Redundant `.exists()` & Duplicate Count in Lifecycle Dashboard**
  - **File**: `apps/documents/views/AuditReporting/AuditReportingDashboard.py:91-103`
  - Redundant `.exists()` before aggregation, and duplicate query for total docs already present in status distribution.
  - Fix: Remove `.exists()` guard and calculate total from status distribution sum.

- [ ] **[PERF-M2] Duplicate Count Query in Audit Trail List Prior to Pagination**
  - **File**: `apps/documents/views/AuditReporting/DocumentAuditTrails.py:58-70`
  - `qs.count()` called, then `paginator.get_page()` counts again.
  - Fix: Use `page_obj.paginator.count` for `total_count`.

- [ ] **[PERF-M3] Loop-Internal `exists()` Lookups in Heuristic Anomaly Scans**
  - **Files**: `apps/documents/views/AuditReporting/DocumentSecurityAlerts.py:164-170,200-206` & `apps/documents/services/audit.py:78-80,110-112`
  - Alert existence checked inside actor loops.
  - Fix: Pre-fetch existing actor IDs into a set before the loop.

- [ ] **[PERF-M4] Over-fetching in Audit Trail Detail Navigation Queries**
  - **File**: `apps/documents/views/AuditReporting/DocumentAuditTrails.py:96-105`
  - `prev_entry` and `next_entry` fetch all columns instead of `.only("id")`.
  - Fix: Add `.only("id")` to previous/next queries.

---

## 5. QA Smoke Tester Pass

- [ ] **[QA-C1] Evidence Package Number Blank in Manifest & Cryptographic Hash During Creation**
  - **URL Route**: `documents:custody_export_create`
  - **File**: `apps/documents/views/AuditReporting/ChainOfCustodyExports.py:74-75` & `apps/documents/models/AuditReporting/ChainOfCustodyExports.py:224-227`
  - `generate_manifest()` called before `pkg.save()` causes `manifest_json["package_number"] = ""` permanently.
  - Fix: Allocate `self.number` or call `super().save()` before computing `generate_manifest()`.

- [ ] **[QA-C2] Superficial Integrity Check in Custody Export Detail View**
  - **URL Route**: `documents:custody_export_detail`
  - **File**: `apps/documents/views/AuditReporting/ChainOfCustodyExports.py:103-104`
  - `is_hash_valid` is evaluated as `bool(export_pkg.package_hash)` rather than computing the actual SHA-256 digest over `export_pkg.manifest_json`.
  - Fix: Recompute SHA-256 digest over `manifest_json` and compare against `package_hash`.

- [ ] **[QA-I1] Missing Audit Record Number Column in Audit Trail List Table**
  - **URL Route**: `documents:audit_trail_list`
  - **File**: `templates/documents/audit_reporting/audit_trail/list.html:132-140`
  - `DocumentAuditTrail` records have tenant numbers (`DAUD-XXXXX`) but the table header and rows omit the audit record number column.
  - Fix: Add an "Audit ID" column displaying `entry.number`.

- [ ] **[QA-I2] Form Choice Discrepancy on Regulatory Framework**
  - **URL Route**: `documents:custody_export_create`
  - **File**: `apps/documents/models/AuditReporting/ChainOfCustodyExports.py:18-26`
  - Choice key is `soc2_type2`, but users or seeders submitting `soc2` fails choice validation.
  - Fix: Add `soc2` as alias or ensure documentation and forms strictly align with choice keys.

- [ ] **[QA-M1] Missing `passcode_form: None` Context Key in Authenticated Auditor Portal**
  - **URL Route**: `documents:auditor_portal_view`
  - **File**: `apps/documents/views/AuditReporting/ChainOfCustodyExports.py:211-218`
  - When session is authenticated (`passcode_required=False`), `passcode_form` is missing from context dict.
  - Fix: Add `"passcode_form": None` to context.
