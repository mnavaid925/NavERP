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
