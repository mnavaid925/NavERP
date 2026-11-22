# Review Findings: Module 12.20 Data Integrity & Electronic Records

**Base Commit**: `0a93a42d6c28678b9dd1e5c18eac3ca09e22c3eb`
**Head Commit**: `HEAD`
**Target App**: `apps/quality/` (Sub-module 12.20: Data Integrity & Electronic Records)

---

## Review Passes
1. `code-reviewer`
2. `explorer`
3. `frontend-reviewer`
4. `performance-reviewer`
5. `qa-smoke-tester`
6. `security-reviewer`

---

## Raw Review Logs

### Pass 1: `code-reviewer`
- **Critical**: None.
- **Important**:
  - `I1`: Missing `system` filter dropdown in `data_integrity_assessment/list.html`
  - `I2`: Missing `gxp_impact` and `status` filter dropdowns in `system_change_control/list.html`
  - `I3`: Missing `status` filter dropdown in `audit_trail_review/list.html`
  - `I4`: Missing `part11` filter dropdown in `electronic_record_policy/list.html`
  - `I5`: Active filter query parameters dropped during pagination across list templates
  - `I6`: Missing date range order validation in `AuditTrailReviewForm` (`period_start <= period_end`)
- **Minor**:
  - `M1`: Pagination footer references `total_count` instead of `paginator.count`
  - `M2`: Lack of server-side minimum validation for `retention_period_years >= 1`
  - `M3`: Validation consistency between `anomalies_detected_count > 0` and `disposition="approved_clean"`

### Pass 2: `explorer`
- **Critical**: None.
- **Important**:
  - Corroborates `I1`, `I2`, `I3`, `I4`, `I5`, `I6`.
  - `I7`: `SystemChangeControlForm` allows closing without requiring `closure_summary`.
  - `I8`: `DataIntegrityAssessmentForm` allows approval when ALCOA+ ratings are `non_compliant` without requiring `remediation_plan` or `linked_capa`.
- **Minor**:
  - Corroborates `M1`, `M2`, `M3`.
  - `M4`: Detail templates render `system` and `governing_sop` as plain text instead of clickable links to `quality:computer_system_validation_detail` and `quality:controlled_document_detail`.
  - `M5`: Add index on `SystemChangeControl.target_date` for overdue/deadline queries.

### Pass 3: `frontend-reviewer`
- **Critical**: None.
- **Important**: None.
- **Minor**:
  - `M6`: Undefined CSS utility `text-green` in `audit_trail_review/list.html` and `detail.html` (use `text-ok` or `badge-green`).
  - Corroborates `I5` (secondary filter query parameter preservation during pagination).
  - Corroborates `M4` (hyperlinks to Computer System Validation and Controlled Document details).
  - `M7`: Redundant `has_previous` condition in `electronic_record_policy/list.html:201`.

### Pass 4: `performance-reviewer`
- **Critical**: None.
- **Important**:
  - `I9`: Missing `db_index=True` on `SystemChangeControl.change_type`.
  - `I10`: Pagination page size alignment with 20 items/page standard across list views.
- **Minor**:
  - Corroborates `I1` / `M8`: `systems` query in assessment list unused until UI filter added.
  - `M9`: Absence of composite ordering indexes on `(tenant, -created_at)` / `(tenant, -review_date)`.
  - `M10`: Composite `["tenant", "status"]` index consideration for high-volume multi-tenant status filtering.

### Pass 5: `qa-smoke-tester`
- **Critical**: None (123 automated assertions passed; 16/16 IDOR attack vectors blocked with 404).
- **Important**:
  - Corroborates `I5`: Active filter query parameters dropped during pagination.
  - Corroborates `I6`: Missing inverted date range validation in `AuditTrailReviewForm`.
  - Corroborates `I1`–`I4`: Missing filter dropdowns in list templates.
- **Minor**:
  - Corroborates `M2`: Lack of minimum value validation (`retention_period_years >= 1`).
  - Corroborates `M4`: Plaintext references instead of hyperlinks for CSV computer system and SOP.
  - Corroborates `M6`: Undefined CSS utility `text-green` in audit trail review templates.
  - `M11`: `data_integrity_dashboard.html:42` uses `stat-icon red`; standardize to `stat-icon orange` per L33 standard.






