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
### 2. Explorer (Contract & Spec)
- **Contract Adherence**: All 4 models, 4 forms, 17 URLs, and sidebar entries in `LIVE_LINKS["12.5"]` match `.claude/tasks/contract-quality-12.5.md` and `NavERP.md`.
- **Critical**:
  - `apps/quality/views/NonConformance/MrbDispositions.py:103`: AuditLog action `"disposition"` is 11 chars, exceeding DB `max_length=10`. Fix: change to `"create"`. Note: `.claude/tasks/contract-quality-12.5.md` Section 0 contained a self-contradiction listing `"disposition"` as <= 10 chars.
- **Important**:
  - `templates/quality/nonconformance/nonconformancereport/list.html:35-75`: Category filter `<select>` missing in list filter bar.
  - `templates/quality/nonconformance/processdeviation/list.html:32-64, 153, 165`: Risk Level filter `<select>` missing and pagination drops `selected_risk_level`.
  - `templates/quality/nonconformance/processdeviation/detail.html:84`: Nullable `approved_by` filter argument traversal without guard.
  - `templates/quality/nonconformance/nonconformancereport/detail.html:126`: Nullable `closed_by` traversal without guard.
  - `apps/quality/views/NonConformance/QuarantineContainments.py:140`, `apps/quality/views/NonConformance/MrbDispositions.py:146`: Delete redirects unconditionally to NCR detail instead of honoring list/next.
- **Minor**:
  - `apps/quality/views/NonConformance/NonConformanceReports.py:116-120`: Auto-populate `closed_at`/`closed_by` on create if status is closed.
  - `apps/quality/models/NonConformance/MrbDispositions.py:186-187`: Auto recalculate total cost in `save()`.

### 3. Frontend Reviewer
- **Praise**: Zero comment leaks, 100% adherence to color-named theme.css classes, full CRUD CSRF POST forms, flawless pagination guards.
- **Critical**:
  - `templates/quality/nonconformance/processdeviation/detail.html:84`: [C1] Lesson L10 None-safe crash on unapproved Process Deviation detail (`approved_by`). Fix: `{% if process_deviation.approved_by %}{{ process_deviation.approved_by.get_full_name|default:process_deviation.approved_by.username }}{% else %}Pending Approval{% endif %}`.
  - `templates/quality/nonconformance/nonconformancereport/detail.html:126`: [C2] Lesson L10 None-safe crash on NCR detail when `closed_by` is unset. Fix: `{% if non_conformance_report.closed_by %}{{ non_conformance_report.closed_by.get_full_name|default:non_conformance_report.closed_by.username }}{% else %}—{% endif %}`.
- **Important**:
  - `templates/quality/nonconformance/nonconformancereport/list.html:35-75`: [I1] NCR list filter form omits Category `<select>` dropdown. Fix: add Category dropdown.
  - `templates/quality/nonconformance/processdeviation/list.html:32-64, 153, 165`: [I2] Process Deviation list filter form & pagination omit Risk Level. Fix: add dropdown and preserve in pagination links.
  - `templates/quality/nonconformance/ncr_analytics_dashboard.html:34-89`: [I3] Analytics dashboard uses ad-hoc KPI cards instead of design system `.stat-grid` / `.stat-card` / `.stat-value` / `.stat-label`. Fix: update KPI markup to standard stat card classes.
  - `templates/quality/nonconformance/nonconformancereport/detail.html:173, 226, 279` & `ncr_analytics_dashboard.html:182`: [I4] Icon-only action links lack accessible `title` and `aria-label`. Fix: add accessible labels.
- **Minor**:
  - `templates/quality/nonconformance/nonconformancereport/list.html:123`, `detail.html:100`, `processdeviation/detail.html:183`: [M1] Physical margin `ml-1` instead of logical `ms-1` (RTL readiness).
  - Clear filter buttons lack `aria-label`: [M2] Add `aria-label="Clear filters"`.
  - Delete buttons bypass `.btn-icon.danger`: [M3] Add `.danger` modifier class.
  - `ncr_analytics_dashboard.html:118, 133`: [M4] Category and Source breakdowns omit badge markup. Fix: wrap with `<span class="badge {{ item.css }}">`.




