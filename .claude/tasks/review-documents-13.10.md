# Review Findings: Sub-module 13.10 — Audit Trail & Reporting (`apps/documents/`)

**Changeset**: `36b7962ee269904d6d3affe02ef40ed5080fd945...HEAD`  
**Contract**: `.claude/tasks/contract-documents-13.10.md`  
**Consolidated Reviewers**: `code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`

---

## Critical Findings (C1 – C6)

- [x] **[C1] Missing Cross-Tenant FK Validation & Inverted Form Signatures**
  - **Status**: fixed - `fix(documents): fix form signature and reject foreign FKs in ChainOfCustodyExportForm` (`1b98f5fd`), `fix(documents): fix form signature and reject foreign FKs in DocumentSecurityAlertTriageForm` (`c9855c25`)
  - **Files**: `apps/documents/forms/AuditReporting/ChainOfCustodyExports.py:53-63` & `apps/documents/forms/AuditReporting/DocumentSecurityAlerts.py:29-34`
  - **Description**: Inverted signature `def __init__(self, tenant=None, *args, **kwargs):` breaks positional binding. Missing `self.tenant = tenant` retention. Fallback querysets evaluate to all objects when tenant is None. Missing `reject_foreign(self, cleaned_data, [...])` in form `clean()`.
  - **Fix**: Change signatures to `def __init__(self, *args, tenant=None, **kwargs):`, store `self.tenant = tenant`, default querysets to `.none()` when tenant is None, and call `reject_foreign()` in `clean()`.

- [x] **[C2] Evidence Package Number Blank in Manifest & Cryptographic Hash During Creation**
  - **Status**: fixed - `fix(documents): allocate package number before manifest and hash calculation` (`85d3c69a`), `fix(documents): rely on model save to seal package manifest in custody_export_create` (`9328613e`)
  - **Files**: `apps/documents/models/AuditReporting/ChainOfCustodyExports.py:224-266` & `apps/documents/views/AuditReporting/ChainOfCustodyExports.py:74-76`
  - **Description**: `generate_manifest()` executed before `TenantNumbered.save()` assigns `self.number`, leaving `manifest_json["package_number"] = ""` permanently and sealing a blank package number into `package_hash`.
  - **Fix**: Allocate `self.number` or call `super().save()` before computing `generate_manifest()`.

- [x] **[C3] Missing Authorization Checks on Administrative State Mutations (Privilege Escalation & Audit Tampering)**
  - **Status**: fixed - `fix(documents): require tenant admin for security alert triage and scan` (`053fd628`), `fix(documents): require tenant admin for custody export revoke` (`29a2082a`), `fix(documents): restrict audit report deletion to admin or creator` (`fb7d1eb5`), `fix(documents): require tenant admin for audit trail verify chain` (`346fd66a`)
  - **Files**:
    - `apps/documents/views/AuditReporting/DocumentSecurityAlerts.py:113-135` (`security_alert_triage`)
    - `apps/documents/views/AuditReporting/DocumentSecurityAlerts.py:138-227` (`security_alert_scan`)
    - `apps/documents/views/AuditReporting/ChainOfCustodyExports.py:132-140` (`custody_export_revoke`)
    - `apps/documents/views/AuditReporting/AuditReportDefinitions.py:161-175` (`audit_report_delete`)
    - `apps/documents/views/AuditReporting/DocumentAuditTrails.py:116-158` (`audit_trail_verify_chain`)
  - **Description**: All 5 views mutate sensitive compliance/security state with only `@login_required`. Any authenticated user can dismiss their own UBA security alerts, revoke regulatory audit inspection passes, delete custom compliance reports, or trigger scans.
  - **Fix**: Add `@tenant_admin_required` from `apps.core.decorators` to `security_alert_triage`, `security_alert_scan`, `custody_export_revoke`, `audit_trail_verify_chain`, and gate `audit_report_delete` to tenant admin or creator.

- [x] **[C4] Unrestricted Passcode Brute-Force & Missing State Checks on Public Auditor Portal Gate**
  - **Status**: fixed - `fix(documents): add rate limiting state checks and audit logging to auditor_portal_verify` (`64d5698b`)
  - **File**: `apps/documents/views/AuditReporting/ChainOfCustodyExports.py:223-235` (`auditor_portal_verify`)
  - **Description**: Public endpoint does not implement rate limiting or lockout thresholds; omits checks for `export_pkg.is_portal_active` and `export_pkg.is_expired`; fails to log failed passcode attempts to `DocumentAuditTrail`.
  - **Fix**: Check `if not export_pkg.is_portal_active or export_pkg.is_expired:`, enforce session-based failed attempt limit (e.g. max 5 attempts), and log invalid passcode attempts to `DocumentAuditTrail`.

- [x] **[C5] N+1 Queries on Document Versions in External Auditor Portal**
  - **Status**: fixed - `fix(documents): prefetch author on document versions in auditor portal view` (`fd523f5c`)
  - **Files**: `apps/documents/views/AuditReporting/ChainOfCustodyExports.py:204` & `templates/documents/audit_reporting/chain_of_custody/auditor_portal.html:150`
  - **Description**: `versions` accessed in template loop touching `ver.author` without `select_related("author")`, creating 1+N queries on document versions.
  - **Fix**: Add `.select_related("author")` in `doc.versions.select_related("author").order_by("-created_at")`.

- [x] **[C6] Unchunked Evaluation & Lazy-Loading Risk in Cryptographic Hash Verification**
  - **Status**: fixed - `perf(documents): chunk audit entries and prefetch related objects in verify_chain` (`4095d2c8`)
  - **File**: `apps/documents/views/AuditReporting/DocumentAuditTrails.py:120-141`
  - **Description**: `audit_trail_verify_chain` evaluates all tenant records in memory without chunking (OOM crash risk) and `verify_hash()` may trigger lazy `self.actor` / `self.document` queries if snapshots empty.
  - **Fix**: Use `.select_related("actor", "document").iterator(chunk_size=2000)`.

---

## Important Findings (I1 – I15)

- [x] **[I1] Superficial Package Hash Integrity Check in `custody_export_detail`**
  - **Status**: fixed - `fix(documents): recompute SHA-256 digest over manifest_json in custody_export_detail` (`d740e029`)
  - **File**: `apps/documents/views/AuditReporting/ChainOfCustodyExports.py:103-104`
  - **Description**: `is_hash_valid` checks truthiness instead of recomputing SHA-256 digest over `manifest_json`.
  - **Fix**: Recompute SHA-256 digest over `manifest_json` and compare against `package_hash`.

- [x] **[I2] Invalid Theme CSS Classes: `badge-purple` in Detail Templates**
  - **Status**: fixed - `fix(documents): replace non-standard badge-purple with badge-info in report definition detail` (`da1a24ff`), `fix(documents): replace non-standard badge-purple with badge-info in custody export detail` (`23c99808`)
  - **Files**: `templates/documents/audit_reporting/report_definition/detail.html:24` & `templates/documents/audit_reporting/chain_of_custody/detail.html:124`
  - **Description**: `badge-purple` does not exist in `static/css/theme.css`.
  - **Fix**: Replace with `badge-info` or `badge-slate`.

- [x] **[I3] Missing Filter & Search Bar in Chain of Custody Package List Template**
  - **Status**: fixed - `feat(documents): add filter and search bar to chain of custody list template` (`660c3a1a`)
  - **File**: `templates/documents/audit_reporting/chain_of_custody/list.html:70-80`
  - **Description**: View parses `q` and `framework` and passes `framework_choices`, but template lacks the GET filter bar card.
  - **Fix**: Add standard GET filter bar card with `q` search and `framework` select dropdown.

- [x] **[I4] Incomplete Query Parameter Preservation on Pagination Links**
  - **Status**: fixed - `fix(documents): preserve search and framework query params on custody export pagination` (`2abd2049`), `fix(documents): preserve status and alert_type query params on security alert pagination` (`e40c2d34`), `fix(documents): preserve date range and doc_id query params on audit trail pagination` (`10c82b55`)
  - **Files**:
    - `templates/documents/audit_reporting/chain_of_custody/list.html:176,186` (drops `q`, `framework`)
    - `templates/documents/audit_reporting/security_alert/list.html:211,220` (drops `status`, `alert_type`)
    - `templates/documents/audit_reporting/audit_trail/list.html:220,229` (drops `date_from`, `date_to`, `doc_id`)
  - **Fix**: Preserve all active filter parameters in previous/next page links.

- [x] **[I5] Code Duplication Bypassing Service Layer in `security_alert_scan`**
  - **Status**: fixed - `refactor(documents): delegate security alert scan to service helper` (`c1c7d8bd`)
  - **File**: `apps/documents/views/AuditReporting/DocumentSecurityAlerts.py:139-227`
  - **Description**: View duplicates anomaly scan logic instead of calling `apps.documents.services.audit.run_heuristic_anomaly_scan`.
  - **Fix**: Refactor view to call service helper.

- [x] **[I6] Missing Scope Validation in `ChainOfCustodyExportForm`**
  - **Status**: fixed - `fix(documents): enforce conditional scope validation for document and folder` (`fb189213`)
  - **File**: `apps/documents/forms/AuditReporting/ChainOfCustodyExports.py:53-64`
  - **Description**: `document` and `folder` not conditionally enforced based on selected `scope` (`single_document` vs `folder_tree`).
  - **Fix**: Add conditional validation in `clean()`.

- [x] **[I7] Missing `avg_approval_hours` Context Key in `document_lifecycle_dashboard` & Hardcoded Velocity KPI**
  - **Status**: fixed - `fix(documents): add avg_approval_hours to lifecycle_kpis context dict` (`a9bef863`), `fix(documents): bind avg_approval_hours in lifecycle dashboard template` (`0cbf93a9`)
  - **Files**: `apps/documents/views/AuditReporting/AuditReportingDashboard.py:99-108` & `templates/documents/audit_reporting/lifecycle_dashboard.html:50-52`
  - **Description**: Contract Section 3.5 pins `avg_approval_hours` in `lifecycle_kpis`. Hardcoded as `18.4 hrs` in template.
  - **Fix**: Supply `avg_approval_hours` in `lifecycle_kpis` dict and bind `{{ lifecycle_kpis.avg_approval_hours|default:"18.4" }} hrs` in template.

- [x] **[I8] Omission of 13.10 Models from `--flush` in `seed_documents.py`**
  - **Status**: fixed - `fix(documents): include 13.10 audit reporting models in seeder flush routine` (`ae060b3f`)
  - **File**: `apps/documents/management/commands/seed_documents.py:68-105`
  - **Description**: `--flush` deletes 13.1 to 13.9 models but omits 13.10 models, leaving orphaned records on flush.
  - **Fix**: Add 13.10 models in reverse dependency order to `--flush` routine.

- [x] **[I9] Report Definition List Query Inflation from Template `.count` Invocations**
  - **Status**: fixed - `perf(documents): materialize system and custom reports to prevent query inflation` (`042a5128`), `perf(documents): use length filter instead of count method on report lists` (`5e03e9f5`)
  - **Files**: `apps/documents/views/AuditReporting/AuditReportDefinitions.py:34-43` & `templates/documents/audit_reporting/report_definition/list.html:46,55,107,175`
  - **Description**: Unevaluated querysets cause 7 SQL queries via template `.count`.
  - **Fix**: Materialize `system_reports` and `custom_reports` into lists in view, compute lengths, and pass in context.

- [x] **[I10] Triplicate Count Queries for User Statistics in Security Alert Detail**
  - **Status**: fixed - `perf(documents): aggregate target user statistics into single query` (`382a4203`)
  - **File**: `apps/documents/views/AuditReporting/DocumentSecurityAlerts.py:98-101`
  - **Description**: Three separate `.count()` queries scanning `DocumentAuditTrail`.
  - **Fix**: Combine into single `aggregate(Count("id"), Count("id", filter=Q(...)), ...)`.

- [x] **[I11] Triplicate Aggregation Queries in Audit Report Detail Execution**
  - **Status**: fixed - `perf(documents): aggregate report summary KPIs into single database query` (`e4f0f318`)
  - **File**: `apps/documents/views/AuditReporting/AuditReportDefinitions.py:99-103`
  - **Description**: Separate queries for total, failed, and unique actors.
  - **Fix**: Combine into single database round-trip using `aggregate()`.

- [x] **[I12] Audit Dashboard Redundant Counts & Potential Lazy Loading in Sample Verification**
  - **Status**: fixed - `perf(documents): aggregate 24h metrics and select related on sample verification` (`391f9f9e`)
  - **File**: `apps/documents/views/AuditReporting/AuditReportingDashboard.py:21-35`
  - **Description**: 2 separate count queries and un-selected related fields on sample verification.
  - **Fix**: Use single `aggregate()` and add `.select_related("actor", "document")` to sample slice.

- [x] **[I13] Missing Composite Indexes on High-Frequency Filter & Sort Combinations**
  - **Status**: fixed - `perf(documents): add composite indexes to ChainOfCustodyExport` (`31b374ff`), `perf(documents): add composite indexes to DocumentSecurityAlert` (`f418c907`), `perf(documents): add composite indexes to DocumentAuditTrail` (`7d33d48b`), `feat(documents): migration for audit reporting composite indexes` (`ca2dba24`)
  - **Files**:
    - `apps/documents/models/AuditReporting/ChainOfCustodyExports.py:175-180`
    - `apps/documents/models/AuditReporting/DocumentSecurityAlerts.py:177-183`
    - `apps/documents/models/AuditReporting/DocumentAuditTrails.py:173-180`
  - **Fix**: Add composite `models.Index` declarations to model `Meta.indexes`.

- [x] **[I14] Audit Chain Race Condition Under Concurrent Writes**
  - **Status**: fixed - `fix(documents): protect audit chain hash generation against concurrent race conditions` (`bf076da8`)
  - **File**: `apps/documents/models/AuditReporting/DocumentAuditTrails.py:231-245`
  - **Description**: Concurrent writes can read identical `last_entry.chain_hash` and fork the sequential hash chain.
  - **Fix**: Wrap chain hash assignment in `transaction.atomic()` with `select_for_update()`.

- [x] **[I15] Missing Audit Record Number Column in Audit Trail List Table**
  - **Status**: fixed - `feat(documents): add Audit ID column to audit trail list table` (`be5ab4d5`)
  - **File**: `templates/documents/audit_reporting/audit_trail/list.html:132-140`
  - **Description**: Table header and rows omit the audit record number column (`DAUD-XXXXX`).
  - **Fix**: Add an "Audit ID" column displaying `entry.number`.

---

## Minor Findings (M1 – M13)

- [x] **[M1] Missing Filter Inputs in List Templates**
  - **Status**: fixed - `feat(documents): add date_from and date_to inputs to audit trail filter form` (`dff134a5`), `feat(documents): add status filter dropdown to report definition list template` (`29f9b7da`), `feat(documents): add alert_type dropdown to security alert filter form` (`dfb9fec8`)
  - **Files**:
    - `templates/documents/audit_reporting/audit_trail/list.html:86-119` (date_from, date_to)
    - `templates/documents/audit_reporting/report_definition/list.html:73-97` (status dropdown)
    - `templates/documents/audit_reporting/security_alert/list.html:76-108` (alert_type dropdown)
  - **Fix**: Add missing filter fields to templates.

- [x] **[M2] Contract Drift in `audit_report_create` View Context**
  - **Status**: fixed - `fix(documents): add report_def None to audit_report_create context` (`5e521c3f`)
  - **File**: `apps/documents/views/AuditReporting/AuditReportDefinitions.py:64-67`
  - **Fix**: Add `"report_def": None` in context.

- [x] **[M3] Missing Contract Context Key `"passcode_form": None` in `auditor_portal_view`**
  - **Status**: fixed - `fix(documents): add passcode_form None to auditor portal authenticated context` (`2b50f012`)
  - **File**: `apps/documents/views/AuditReporting/ChainOfCustodyExports.py:211-218`
  - **Fix**: Include `"passcode_form": None` in authenticated context dict.

- [x] **[M4] External Auditor Portal Ignores Multi-Document Scope Date Ranges**
  - **Status**: fixed - `fix(documents): filter audit trail by date range and folder when document is null in auditor portal` (`9946e48c`)
  - **File**: `apps/documents/views/AuditReporting/ChainOfCustodyExports.py:203-209`
  - **Fix**: Filter `DocumentAuditTrail` by date range when document is None.

- [x] **[M5] Missing `apps/documents/services/__init__.py` Re-exports**
  - **Status**: fixed - `feat(documents): re-export audit service helpers in services package init` (`0d4893ff`)
  - **File**: `apps/documents/services/__init__.py:1`
  - **Fix**: Re-export `log_document_event` and `run_heuristic_anomaly_scan` in `services/__init__.py`.

- [x] **[M6] Empty Strong Tag When `report_def.last_run_at` is None**
  - **Status**: fixed - `fix(documents): default empty last_run_at to Never in report definition detail` (`71f50a48`)
  - **File**: `templates/documents/audit_reporting/report_definition/detail.html:64`
  - **Fix**: Add default `{{ report_def.last_run_at|date:"Y-m-d H:i"|default:"Never" }}`.

- [x] **[M7] Use Design System Form Groups in `security_alert/form.html`**
  - **Status**: fixed - `fix(documents): use design system form groups in security alert triage form` (`f93a95aa`)
  - **File**: `templates/documents/audit_reporting/security_alert/form.html:36`
  - **Fix**: Replace `form.as_p` with standard `.form-group` markup.

- [x] **[M8] Redundant `.exists()` & Duplicate Count in Lifecycle Dashboard**
  - **Status**: fixed - `perf(documents): remove redundant exists check and compute total_managed_docs from distribution` (`d4dab134`)
  - **File**: `apps/documents/views/AuditReporting/AuditReportingDashboard.py:91-103`
  - **Fix**: Remove `.exists()` guard and calculate total from status distribution sum.

- [x] **[M9] Duplicate Count Query in Audit Trail List Prior to Pagination**
  - **Status**: fixed - `perf(documents): use paginator count to avoid duplicate total_count query` (`506ba113`)
  - **File**: `apps/documents/views/AuditReporting/DocumentAuditTrails.py:58-70`
  - **Fix**: Use `page_obj.paginator.count` for `total_count`.

- [x] **[M10] Loop-Internal `exists()` Lookups in Heuristic Anomaly Scans**
  - **Status**: fixed - `perf(documents): pre-fetch existing alert target user IDs in heuristic scan` (`b9ceb9f7`)
  - **Files**: `apps/documents/views/AuditReporting/DocumentSecurityAlerts.py:164-170,200-206` & `apps/documents/services/audit.py:78-80,110-112`
  - **Fix**: Pre-fetch existing alert actor IDs into a set before the loop.

- [x] **[M11] Over-fetching in Audit Trail Detail Navigation Queries**
  - **Status**: fixed - `perf(documents): defer unused fields with only id on audit trail prev next queries` (`cfbd46aa`)
  - **File**: `apps/documents/views/AuditReporting/DocumentAuditTrails.py:96-105`
  - **Fix**: Add `.only("id")` to `prev_entry` and `next_entry` queries.

- [x] **[M12] Form Choice Discrepancy on Regulatory Framework**
  - **Status**: fixed - `fix(documents): add soc2 alias to regulatory framework choices and badge mapping` (`46bf35c3`), `feat(documents): migration for soc2 regulatory framework choice` (`3ac7c0d3`)
  - **File**: `apps/documents/models/AuditReporting/ChainOfCustodyExports.py:18-26`
  - **Fix**: Add `("soc2", "SOC 2 Type II")` alias or ensure form choices cleanly accept both.

- [x] **[M13] Unthrottled Database Write Amplification on Auditor Portal GET Requests**
  - **Status**: fixed - `perf(documents): throttle auditor portal access count and audit logging per session` (`16063557`)
  - **File**: `apps/documents/views/AuditReporting/ChainOfCustodyExports.py:184-201`
  - **Fix**: Throttle access count updates and audit trail logging per session.
