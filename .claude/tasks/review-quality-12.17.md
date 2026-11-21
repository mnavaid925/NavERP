# Review Findings: Submodule 12.17 (Regulatory Compliance & Submissions)

**Module:** Quality Management (12)  
**Submodule:** 12.17 Regulatory Compliance & Submissions (`apps/quality/`)  
**Base Commit:** `9448e93f0d2646888e2e79a8faafd9f648805e20`  
**Review Passes:** 6 serial passes (`code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`)  
**Status:** Findings Consolidated — Ready for Code Fixer  

---

## Findings Summary

| Severity | Count | Open | Fixed | Skipped |
| :--- | :---: | :---: | :---: | :---: |
| **Critical** | 2 | 0 | 2 | 0 |
| **Important** | 9 | 5 | 4 | 0 |
| **Minor** | 14 | 14 | 0 | 0 |
| **Total** | 25 | 19 | 6 | 0 |

---

## Critical Findings

- [x] **C1: Unbounded In-Memory QuerySet Evaluation and Missing `.iterator()` in All 4 CSV Exports**
  - **Files**:
    - `apps/quality/views/RegulatorySubmissions/RegulatorySubmissions.py:198`
    - `apps/quality/views/RegulatorySubmissions/ProductRegistrations.py:216`
    - `apps/quality/views/RegulatorySubmissions/RegulatoryCommitments.py:212`
    - `apps/quality/views/RegulatorySubmissions/PostMarketSurveillanceReports.py:198`
  - **Issue**: CSV export loops iterate over unchunked querysets (`for item in qs:`) which caches all objects in memory at once. Furthermore, massive `TextField` columns (`technical_sections_summary`, `notes`, `intended_purpose`, `commitment_description`, etc.) are queried across the wire but never written to the CSV.
  - **Fix**: Stream via `.iterator(chunk_size=1000)` and use `.defer(...)` or `.only(...)` to exclude large unused text fields.

- [x] **C2: Redundant Unused Table JOINs in CSV Exports and Dashboard**
  - **Files**:
    - `apps/quality/views/RegulatorySubmissions/RegulatorySubmissions.py:172` (`org_unit`)
    - `apps/quality/views/RegulatorySubmissions/ProductRegistrations.py:188` (`authorized_representative`)
    - `apps/quality/views/RegulatorySubmissions/PostMarketSurveillanceReports.py:171` (`product_registration`, `prepared_by`)
    - `apps/quality/views/RegulatorySubmissions/RegulatoryDashboard.py:42` (`product_registration` in `recent_pms_reports`)
  - **Issue**: Views join foreign tables that are never rendered or accessed in the CSV output row or dashboard table, adding unnecessary SQL overhead.
  - **Fix**: Remove unreferenced foreign keys from `select_related`.

---

## Important Findings

- [x] **I1: Missing Filter Query Parameter Retention in Pagination Links across All 4 List Views**
  - **Files**:
    - `templates/quality/regulatory_submissions/regulatory_submission/list.html:211, 219`
    - `templates/quality/regulatory_submissions/product_registration/list.html:215, 223`
    - `templates/quality/regulatory_submissions/regulatory_commitment/list.html:209, 217`
    - `templates/quality/regulatory_submissions/post_market_surveillance_report/list.html:198, 206`
  - **Issue**: Pagination links only preserve `q`, `status`, and primary type; navigating to page 2 strips authority, agency, device class, and benefit-risk filters.
  - **Fix**: Append all active GET filter parameters to previous/next pagination links.

- [x] **I2: Core Spine Attribute Mismatch: `ControlledDocument.revision_number` Does Not Exist**
  - **File**: `templates/quality/regulatory_submissions/regulatory_submission/detail.html:112`
  - **Issue**: Template references `technical_dossier.revision_number`, but the attribute on `ControlledDocument` is `revision`. Resolves silently to empty string `(Rev )`.
  - **Fix**: Update template expression to `{{ regulatory_submission.technical_dossier.revision }}`.

- [x] **I3: Missing `@tenant_admin_required` on Destructive Deletion Views**
  - **Files**:
    - `apps/quality/views/RegulatorySubmissions/RegulatorySubmissions.py:160`
    - `apps/quality/views/RegulatorySubmissions/ProductRegistrations.py:176`
    - `apps/quality/views/RegulatorySubmissions/RegulatoryCommitments.py:177`
    - `apps/quality/views/RegulatorySubmissions/PostMarketSurveillanceReports.py:159`
  - **Issue**: All 4 delete views allow any authenticated user in the tenant to permanently delete regulatory submissions and certificates. In accordance with QMS governance, deletion must be restricted to tenant admins.
  - **Fix**: Import `tenant_admin_required` from `apps.core.decorators` and apply to all 4 deletion views.

- [x] **I4: KPI Stat Cards Computed on Filtered Queryset Instead of Tenant Base Queryset**
  - **Files**:
    - `apps/quality/views/RegulatorySubmissions/RegulatorySubmissions.py:54-58`
    - `apps/quality/views/RegulatorySubmissions/ProductRegistrations.py:54-62`
    - `apps/quality/views/RegulatorySubmissions/RegulatoryCommitments.py:54-59`
    - `apps/quality/views/RegulatorySubmissions/PostMarketSurveillanceReports.py:52-53`
  - **Issue**: Filtering by status (e.g. `status=draft`) resets the summary cards (e.g. "Approved" shows 0 even if approved items exist).
  - **Fix**: Compute top-level summary metrics from `base_qs` before applying filter expressions.

- [ ] **I5: Redundant Standalone B-Tree Indexes on Fields Covered by Composite Indexes**
  - **Files**:
    - `apps/quality/models/RegulatorySubmissions/RegulatorySubmissions.py:60, 77, 85`
    - `apps/quality/models/RegulatorySubmissions/ProductRegistrations.py:42, 45, 70, 74`
    - `apps/quality/models/RegulatorySubmissions/RegulatoryCommitments.py:43, 85, 88`
    - `apps/quality/models/RegulatorySubmissions/PostMarketSurveillanceReports.py:49, 62, 72, 78`
  - **Issue**: Fields have `db_index=True` despite already being covered as the secondary column in `Meta.indexes` composite indexes.
  - **Fix**: Remove redundant `db_index=True` where composite indexes provide coverage.

- [ ] **I6: Missing High-Value Composite Indexes for Default Ordering and Filter Patterns**
  - **Files**:
    - `apps/quality/models/RegulatorySubmissions/RegulatorySubmissions.py:120`
    - `apps/quality/models/RegulatorySubmissions/ProductRegistrations.py:100`
    - `apps/quality/models/RegulatorySubmissions/RegulatoryCommitments.py:103`
  - **Issue**: `(tenant, -created_at)`, `(tenant, status, expiration_date)`, and `(tenant, status, due_date)` are frequently sorted/filtered together without composite index coverage.
  - **Fix**: Add composite indexes <= 30 chars: `idx_qsub_ten_created`, `idx_qreg_ten_stat_exp`, `idx_qcom_ten_stat_due`.

- [ ] **I7: Redundant Duplicate SQL Roundtrips via `{{ queryset.count }}` in Detail Templates**
  - **Files**:
    - `templates/quality/regulatory_submissions/regulatory_submission/detail.html:140, 183`
    - `templates/quality/regulatory_submissions/product_registration/detail.html:150, 193`
  - **Issue**: Calling `.count` on related querysets fires an extra `SELECT COUNT(*)` query immediately before the `{% for %}` loop runs `SELECT ...`.
  - **Fix**: Use `{{ linked_commitments|length }}` or evaluate related querysets to lists in the views.

- [ ] **I8: Multiple Sequential Individual `.count()` Queries on List Views Instead of Conditional Aggregation**
  - **Files**:
    - `apps/quality/views/RegulatorySubmissions/RegulatorySubmissions.py:54-58`
    - `apps/quality/views/RegulatorySubmissions/ProductRegistrations.py:54-63`
    - `apps/quality/views/RegulatorySubmissions/RegulatoryCommitments.py:54-60`
  - **Issue**: 2–3 separate `COUNT(*)` queries are executed per list view request.
  - **Fix**: Combine into a single `base_qs.aggregate(...)` with conditional `Count("id", filter=Q(...))`.

- [ ] **I9: Non-Standard CSS Class `form-checkbox` on Boolean Input**
  - **Files**:
    - `apps/quality/forms/RegulatorySubmissions/PostMarketSurveillanceReports.py:49`
    - `templates/quality/regulatory_submissions/post_market_surveillance_report/form.html:119`
  - **Issue**: Uses `form-checkbox` instead of theme standard `.form-check`.
  - **Fix**: Replace `form-checkbox` with `form-check`.

---

## Minor Findings

- [ ] **M1: Ambiguous Countdown / Overdue Display for Waived Commitments**
  - **Files**:
    - `templates/quality/regulatory_submissions/regulatory_commitment/list.html:148-154`
    - `templates/quality/regulatory_submissions/regulatory_commitment/detail.html:197-203`
  - **Issue**: If commitment is `waived`, displays countdown `in X days` instead of "Waived".
  - **Fix**: Add explicit `{% elif item.status == "waived" %}` branch.

- [ ] **M2: Missing Cross-Module Hyperlink to Core Spine Entities in Detail Views**
  - **Files**:
    - `templates/quality/regulatory_submissions/regulatory_submission/detail.html:108-115` (`technical_dossier`)
    - `templates/quality/regulatory_submissions/regulatory_commitment/detail.html:167-171` (`linked_inspection`)
  - **Issue**: `technical_dossier` and `linked_inspection` are rendered as plain text instead of links to their detail pages.
  - **Fix**: Hyperlink to `quality:controlled_document_detail` and `quality:regulatory_inspection_host_detail`.

- [ ] **M3: Unused Imports in Views and Models**
  - **Files**:
    - `apps/quality/models/RegulatorySubmissions/ProductRegistrations.py:1`
    - `apps/quality/views/RegulatorySubmissions/RegulatorySubmissions.py:8, 9`
    - `apps/quality/views/RegulatorySubmissions/ProductRegistrations.py:9`
    - `apps/quality/views/RegulatorySubmissions/RegulatoryCommitments.py:8, 15`
    - `apps/quality/views/RegulatorySubmissions/PostMarketSurveillanceReports.py:8`
    - `apps/quality/views/RegulatorySubmissions/RegulatoryDashboard.py:1`
  - **Issue**: Unused imports (`get_object_or_404`, `timedelta`, `timezone`, `RegulatoryInspectionHost`).
  - **Fix**: Remove unused imports.

- [ ] **M4: Missing Audit Logging on Bulk CSV Data Export**
  - **Files**:
    - `apps/quality/views/RegulatorySubmissions/RegulatorySubmissions.py:171`
    - `apps/quality/views/RegulatorySubmissions/ProductRegistrations.py:187`
    - `apps/quality/views/RegulatorySubmissions/RegulatoryCommitments.py:188`
    - `apps/quality/views/RegulatorySubmissions/PostMarketSurveillanceReports.py:170`
  - **Issue**: Mass export of regulatory records lacks an audit trail entry.
  - **Fix**: Call `write_audit_log` with action `"export"`.

- [ ] **M5: Missing Pre-Population Parameter `?inspection=` on Commitment Creation**
  - **File**: `apps/quality/views/RegulatorySubmissions/RegulatoryCommitments.py:112-126`
  - **Issue**: Does not handle `?inspection=` GET parameter to pre-populate `linked_inspection`.
  - **Fix**: Inspect `request.GET.get("inspection")` and pre-populate `linked_inspection` and `regulatory_agency`.

- [ ] **M6: Visual Negative Sign Discrepancy on Expiration Days in Detail View**
  - **File**: `templates/quality/regulatory_submissions/product_registration/detail.html:297`
  - **Issue**: Renders `Expired (-5d)` instead of `Expired 5d ago`.
  - **Fix**: Strip negative sign using `|stringformat:"d"|slice:"1:"`.

- [ ] **M7: Dashboard Expiring Registrations Can Crowd Out Upcoming Renewals**
  - **File**: `apps/quality/views/RegulatorySubmissions/RegulatoryDashboard.py:33-36`
  - **Issue**: Orders by `expiration_date` ascending without filtering `expiration_date__gte=today`, crowding out upcoming renewals if historic expired records exist.
  - **Fix**: Filter `expiration_date__gte=today` (or include active/pending renewal status).

- [ ] **M8: Plain Text Asterisks Instead of Design System `<span class="req">*</span>`**
  - **Files**:
    - `templates/quality/regulatory_submissions/regulatory_submission/form.html`
    - `templates/quality/regulatory_submissions/product_registration/form.html`
    - `templates/quality/regulatory_submissions/regulatory_commitment/form.html`
    - `templates/quality/regulatory_submissions/post_market_surveillance_report/form.html`
  - **Issue**: Form labels use literal raw string `*` instead of `<span class="req">*</span>`.
  - **Fix**: Replace `*` with `<span class="req">*</span>`.

- [ ] **M9: Inconsistent Breadcrumb Naming in Product Registration Form**
  - **File**: `templates/quality/regulatory_submissions/product_registration/form.html:13`
  - **Issue**: Parent breadcrumb reads `Registrations` instead of `Product Registrations`.
  - **Fix**: Update breadcrumb text to `Product Registrations`.

- [ ] **M10: Action Icon Buttons Lack Row-Specific `aria-label` Context**
  - **Files**:
    - `templates/quality/regulatory_submissions/regulatory_submission/list.html`
    - `templates/quality/regulatory_submissions/product_registration/list.html`
    - `templates/quality/regulatory_submissions/regulatory_commitment/list.html`
    - `templates/quality/regulatory_submissions/post_market_surveillance_report/list.html`
  - **Issue**: Icon action buttons only supply generic titles without record identifiers for screen readers.
  - **Fix**: Add `aria-label="View {{ item.number }}"`, `aria-label="Edit {{ item.number }}"`, `aria-label="Delete {{ item.number }}"`.

- [ ] **M11: Defense-in-Depth Tenant Scoping on Reverse Relations in Detail Views**
  - **Files**:
    - `apps/quality/views/RegulatorySubmissions/RegulatorySubmissions.py:93-94`
    - `apps/quality/views/RegulatorySubmissions/ProductRegistrations.py:96-97`
  - **Issue**: Reverse relation queries rely solely on relational integrity without `.filter(tenant=request.tenant)`.
  - **Fix**: Chain `.filter(tenant=request.tenant)` on reverse relation queries.

- [ ] **M12: List View Filter Dropdown Querysets Fetch Full Model Instances**
  - **Files**:
    - `apps/quality/views/RegulatorySubmissions/RegulatorySubmissions.py:64`
    - `apps/quality/views/RegulatorySubmissions/ProductRegistrations.py:68`
    - `apps/quality/views/RegulatorySubmissions/RegulatoryCommitments.py:65`
    - `apps/quality/views/RegulatorySubmissions/PostMarketSurveillanceReports.py:59`
  - **Issue**: Filter options load all fields instead of `.only("id", "name")`.
  - **Fix**: Add `.only("id", "name")` to filter dropdown querysets.

- [ ] **M13: Commitment Detail Overdue Days Display on Status Override**
  - **File**: `templates/quality/regulatory_submissions/regulatory_commitment/detail.html:198`
  - **Issue**: When `status == "overdue"` but `due_date >= today`, `slice:"1:"` strips the first digit of a positive number.
  - **Fix**: Only apply slice if `days_remaining < 0`.

- [ ] **M14: Unused Variable in Form Validation**
  - **File**: `apps/quality/forms/RegulatorySubmissions/RegulatorySubmissions.py:80`
  - **Issue**: `planned = cleaned_data.get("planned_submission_date")` is extracted but unused.
  - **Fix**: Remove unused variable extraction.
