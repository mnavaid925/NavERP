# Review Findings: Sub-module 12.5 Non-Conformance & Deviation Management

- **Module**: Quality Management (`apps/quality`)
- **Sub-module**: 12.5 Non-Conformance & Deviation Management
- **BASE Commit**: `585db911e9d93d64932a42f765dae39dbb5756a1`
- **Scope**:
  - `apps/quality/models/NonConformance/*`
  - `apps/quality/forms/NonConformance/*`
  - `apps/quality/views/NonConformance/*`
  - `apps/quality/urls/NonConformance/*`
  - `templates/quality/nonconformance/*`
  - Migration `0009` & integration wireup in `apps/quality/` and `apps/core/navigation.py`

---

## Raw Review Logs

### 1. Code Reviewer
- **Verdict**: Commit after fixing Critical + Important findings.
- **Critical**:
  - `apps/quality/views/NonConformance/MrbDispositions.py:103`: `write_audit_log(request.user, obj, "disposition", tenant=request.tenant)` passes 11-char verb `"disposition"` into `AuditLog.action` (`max_length=10`), triggering MySQL `DataError: (1406, "Data too long for column 'action'")` on creation. Fix: Change `"disposition"` to `"create"`.
- **Important**:
  - `templates/quality/nonconformance/processdeviation/detail.html:84`: Nullable FK `process_deviation.approved_by` traversed in filter argument without guard: `{{ process_deviation.approved_by.get_full_name|default:process_deviation.approved_by.username|default:"Pending Approval" }}` (Lesson L10). Fix: `{% if process_deviation.approved_by %}{{ process_deviation.approved_by.get_full_name|default:process_deviation.approved_by.username }}{% else %}Pending Approval{% endif %}`.
  - `templates/quality/nonconformance/nonconformancereport/detail.html:126`: Nullable FK `non_conformance_report.closed_by` in `{{ non_conformance_report.closed_by.get_full_name|default:non_conformance_report.closed_by.username }}` inside `closure_notes` check (Lesson L10). Fix: `{% if non_conformance_report.closed_by %}{{ non_conformance_report.closed_by.get_full_name|default:non_conformance_report.closed_by.username }}{% else %}Quality Assurance{% endif %}`.
  - `templates/quality/nonconformance/nonconformancereport/list.html:35-75`: View parses `selected_category` and provides `category_choices`, but filter form omits Category filter dropdown. Fix: Add category `<select>` dropdown.
  - `templates/quality/nonconformance/processdeviation/list.html:32-64, 153, 165`: View parses `selected_risk_level` and provides `risk_level_choices`, but filter form omits Risk Impact dropdown and pagination links drop it. Fix: Add dropdown and preserve param in pagination.
  - `apps/quality/views/NonConformance/QuarantineContainments.py:140`, `apps/quality/views/NonConformance/MrbDispositions.py:146`, `apps/quality/views/NonConformance/ProcessDeviations.py:145-147`: Deleting from list view unconditionally redirects to NCR detail instead of list. Fix: Support `next_url` fallback to list.
  - `apps/quality/views/NonConformance/NonConformanceReports.py:163-171`: Guard against deleting closed NCR records (`if ncr.status == 'closed': messages.error(...); return redirect(...)`).
- **Minor**:
  - `apps/quality/views/NonConformance/NonConformanceReports.py:116-120`: In `non_conformance_report_create`, creating with `status="closed"` does not populate `closed_at`/`closed_by`. Fix: auto-populate on creation.
  - `apps/quality/models/NonConformance/MrbDispositions.py:186-187`: `MrbDisposition.save()` only auto-sums when `total_cost_impact` is 0. Fix: recalculate in `save()`.
  - `templates/quality/nonconformance/nonconformancereport/detail.html:38-43`: Hide Delete NCR button when closed/voided (`{% if not non_conformance_report.is_closed %}`).
- **Done Well**: Solid multi-tenancy (`TenantNumbered`, `quality_scope`, `reject_foreign`), clean spine reuse (`core.Party`, `core.OrgUnit`, `quality.CapaInvestigation`), strict `theme.css` badges.


