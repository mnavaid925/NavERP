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

## Consolidated Actionable Review Register

### Critical (Must Fix Before Commit)
- [x] **C1** — `apps/quality/views/NonConformance/MrbDispositions.py:103`: `write_audit_log(..., "disposition", ...)` passes an 11-char verb into `AuditLog.action` (`max_length=10`), triggering MySQL `DataError: (1406, "Data too long for column 'action'")` 500 crash on MRB disposition creation. Fix: Change action verb to `"create"`. — fixed in `e7574d47`
- [x] **C2** — `templates/quality/nonconformance/processdeviation/detail.html:84`: Lesson L10 None-safe crash on unapproved Process Deviation detail: `{{ process_deviation.approved_by.get_full_name|default:process_deviation.approved_by.username|default:"Pending Approval" }}` raises `VariableDoesNotExist` and 500s when `approved_by` is None. Fix: Guard with `{% if process_deviation.approved_by %}{{ process_deviation.approved_by.get_full_name|default:process_deviation.approved_by.username }}{% else %}Pending Approval{% endif %}`. — fixed in `e92d7dd9`
- [x] **C3** — `templates/quality/nonconformance/nonconformancereport/detail.html:126`: Lesson L10 None-safe crash on closed NCR without `closed_by`: `{{ non_conformance_report.closed_by.get_full_name|default:non_conformance_report.closed_by.username }}` inside `closure_notes` check raises `VariableDoesNotExist` and 500s when `closed_by` is None. Fix: Guard with `{% if non_conformance_report.closed_by %}{{ non_conformance_report.closed_by.get_full_name|default:non_conformance_report.closed_by.username }}{% else %}Quality Assurance{% endif %}`. — fixed in `dc320582`
- [x] **C4** — `apps/quality/views/NonConformance/NonConformanceReports.py:91-108` & `templates/quality/nonconformance/nonconformancereport/detail.html:223`: N+1 query on `d.mrb_chair` and invalidated prefetch cache in NCR detail view. Calling chained `.order_by(...)` in the view drops the prefetched cache and re-queries without `select_related("mrb_chair")`. Fix: Use `Prefetch("mrb_dispositions", queryset=MrbDisposition.objects.select_related("mrb_chair"))` and call `.all()`. — fixed in `26d3e3d8`
- [x] **C5** — `apps/quality/views/NonConformance/NonConformanceReports.py:164-171`: Missing lifecycle status guard on NCR deletion allows permanent destruction of closed/voided audit compliance records or deletion while active quarantine holds exist. Fix: Reject deletion if `ncr.is_closed` or `ncr.containment_records.filter(status='active').exists()`. — fixed in `0c3c6ec3`

### Important (Should Fix Before Commit)
- [x] **I1** — `templates/quality/nonconformance/nonconformancereport/list.html:35-75`: NCR list filter form omits Category `<select>` dropdown even though the view accepts `?category=` and passes `category_choices`. Fix: Add Category `<select name="category">` dropdown to filter bar. — fixed in `5ad93d9e`
- [x] **I2** — `templates/quality/nonconformance/processdeviation/list.html:32-64, 153, 165`: Process Deviation list filter form omits Risk Level `<select>` dropdown and pagination links drop `&risk_level={{ selected_risk_level }}`. Fix: Add `<select name="risk_level">` and preserve query param in pagination links. — fixed in `85ef043c`
- [x] **I3** — `apps/quality/views/NonConformance/NcrAnalytics.py:19-44`: Analytics dashboard executes 23 queries via Python loops and unaggregated counts. Fix: Replace with single `aggregate()` calls and SQL `GROUP BY` `.values(...).annotate(count=Count('id'))`, reducing queries from 23 to 7. — fixed in `a73ce0d9`
- [x] **I4** — `apps/quality/models/NonConformance/ProcessDeviations.py:173-178`: Missing composite database indexes on `ProcessDeviation` for `(tenant, ncr)` (`idx_qdev_ten_ncr`) and `(tenant, risk_impact_level)` (`idx_qdev_ten_risk_lvl`). Fix: Add to `Meta.indexes`. — fixed in `96261811` and migration `8fba15ee`
- [x] **I5** — `apps/quality/views/NonConformance/QuarantineContainments.py:133-146`, `apps/quality/views/NonConformance/MrbDispositions.py:139-146`, `apps/quality/views/NonConformance/ProcessDeviations.py:138-147`: Missing status guards on deleting active quarantine holds (`status="active"`), approved MRB dispositions (`status in ("approved", "executed")`), and active/closed process deviations (`status in ("approved", "active", "closed")`), plus delete redirects unconditionally to parent NCR instead of honoring list/next URL. Fix: Add status guards and support `request.POST.get("next")` fallback to list. — fixed in `5523d6e4`, `95e466c3`, `a3c08544`
- [x] **I6** — `apps/quality/forms/NonConformance/MrbDispositions.py:30, 53` & `apps/quality/models/NonConformance/MrbDispositions.py:185-188`: Mass assignment of derived financial field `total_cost_impact`. Fix: Remove `total_cost_impact` from form `Meta.fields` and recalculate automatically on `save()`. — fixed in `3f2a581d`, `4f46ef9a`, `d9cc6c93`
- [x] **I7** — `apps/quality/forms/NonConformance/MrbDispositions.py:31-35`: Tripartite board approvals validation: `MrbDispositionForm.clean()` allows marking `status="approved"` without all 3 sign-offs (quality, engineering, operations). Fix: Validate all 3 approvers are selected when status is "approved". — fixed in `2a9d2127`
- [x] **I8** — `templates/quality/nonconformance/ncr_analytics_dashboard.html:34-89`: Analytics dashboard uses ad-hoc KPI cards instead of design system `.stat-grid` / `.stat-card` / `.stat-value` / `.stat-label`. Fix: Update KPI markup to standard stat card classes. — fixed in `8c89ea80`
- [x] **I9** — `templates/quality/nonconformance/nonconformancereport/detail.html:173, 226, 279` & `ncr_analytics_dashboard.html:182`: Icon-only action links lack accessible names (`title` and `aria-label`). Fix: Add accessible labels. — fixed in `02173477`, `79339a90`
- [x] **I10** — `apps/quality/views/NonConformance/NonConformanceReports.py:141-152`: Closed NCR records can be modified via edit form without tenant admin gate. Fix: Restrict modifying closed NCRs to tenant admin / superuser. — fixed in `289f5a71`

### Minor (Fix When Convenient)
- [x] **M1** — `apps/quality/views/NonConformance/NonConformanceReports.py:116-120`: Creating an NCR directly with `status="closed"` does not populate `closed_at` and `closed_by`. Fix: Auto-populate if closed on create. — fixed in `77be2957`
- [x] **M2** — `apps/quality/forms/NonConformance/NonConformanceReports.py`, `QuarantineContainments.py`, `MrbDispositions.py`: Form numeric boundary validations: add non-negative checks and `quantity_nonconforming <= quantity_inspected`, `released_quantity <= quantity_on_hold`. — fixed in `154a2bbd`, `3fae09ab`, `14c7b985`
- [x] **M3** — All 4 list views: Duplicate `SELECT COUNT(*)` due to `qs.count()` followed by `paginator.count`. Fix: Reuse `paginator.count`. — fixed in `a9c64f20`, `5b54b5b2`, `d65f983f`, `d6076869`
- [x] **M4** — `NonConformanceReports.py:32-34`: Unused foreign keys in `non_conformance_report_list` `select_related`. Fix: Keep only `owner`. — fixed in `a183f05b`
- [x] **M5** — `templates/quality/nonconformance/nonconformancereport/detail.html:38-43`: Hide Delete NCR button when closed/voided (`{% if not non_conformance_report.is_closed %}`). — fixed in `4a9e03ad`
- [x] **M6** — `templates/quality/nonconformance/nonconformancereport/list.html:123`, `detail.html:100`, `processdeviation/detail.html:183`: Replace physical margin `ml-1` with logical `ms-1` (RTL readiness). — fixed in `ec646db4`, `33830cec`, `d59bdf80`
- [x] **M7** — List filter clear buttons lack `aria-label="Clear filters"`. Fix: Add `aria-label`. — fixed in `aa31f479`, `77c0895f`, `c24daf4a`, `68381ef6`
- [x] **M8** — List delete buttons bypass `.btn-icon.danger`. Fix: Add `.danger` modifier class. — fixed in `9d15d79a`, `6acc1394`, `9b741a57`, `31f58992`
- [x] **M9** — `ncr_analytics_dashboard.html:118, 133`: Category and Source breakdowns omit badge styling. Fix: Wrap with `<span class="badge {{ item.css }}">`. — fixed in `bdfb0d4b`
- [x] **M10** — `QuarantineContainments.py:97`: Audit log verb `"contain"` should be standardized to canonical `"create"`. — fixed in `f1466c94`

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

### 4. Performance Reviewer
- **Summary**: 1 Critical, 2 Important, 2 Minor.
- **Critical**:
  - `apps/quality/views/NonConformance/NonConformanceReports.py:91-108` and `templates/quality/nonconformance/nonconformancereport/detail.html:223`: [C1] N+1 query on `d.mrb_chair` and invalidated prefetch cache in NCR detail view. Calling `.order_by(...)` discards prefetched queries, and MRB table renders `d.mrb_chair` without `select_related`. Fix: use `Prefetch("mrb_dispositions", queryset=MrbDisposition.objects.select_related("mrb_chair"))` and call `.all()` without chained ordering since `Meta.ordering` already defines `["-created_at"]`.
- **Important**:
  - `apps/quality/views/NonConformance/NcrAnalytics.py:19-44`: [I1] Analytics dashboard executes 23 queries via Python loops over choices and separate counts. Fix: replace with single `aggregate()` calls and SQL `GROUP BY` `.values(...).annotate(count=Count('id'))`, reducing queries from 23 to 7.
  - `apps/quality/models/NonConformance/ProcessDeviations.py:173-178`: [I2] Missing composite indexes on `ProcessDeviation` for `(tenant, ncr)` (`idx_qdev_ten_ncr`) and `(tenant, risk_impact_level)` (`idx_qdev_ten_risk_lvl`).
- **Minor**:
  - All 4 list views: [M1] Duplicate `SELECT COUNT(*)` on list views due to `qs.count()` followed by `paginator.count`. Fix: use `paginator.count`.
  - `NonConformanceReports.py:32-34`: [M2] Unused foreign keys in `non_conformance_report_list` `select_related`. Fix: select only `owner`.

### 5. QA Smoke Tester (Runtime Verification)
- **Summary**: 41 checks executed (39 PASS, 2 FAIL).
- **IDOR**: 100% PASS across all 4 entities (NCR, Quarantine, MRB, Process Deviation) detail and edit views returning 404 for cross-tenant access.
- **Critical**:
  - `templates/quality/nonconformance/processdeviation/detail.html:84`: [C1] 500 crash (`VariableDoesNotExist`) when viewing process deviation with `approved_by=None`.
  - `templates/quality/nonconformance/nonconformancereport/detail.html:126`: [C2] 500 crash (`VariableDoesNotExist`) when viewing closed NCR with `closed_by=None` and `closure_notes` populated.
  - `apps/quality/views/NonConformance/MrbDispositions.py:103`: [C3] `AuditLog.action` length overflow (`"disposition"` is 11 chars, column capacity is 10 chars).
- **Important**:
  - `templates/quality/nonconformance/nonconformancereport/list.html:35-75`: [I1] Missing Category `<select>` dropdown.
  - `templates/quality/nonconformance/processdeviation/list.html:32-64, 153, 165`: [I2] Missing Risk Level `<select>` dropdown and dropped query param in pagination.

### 6. Security Reviewer
- **Summary**: 2 Critical, 4 High, 3 Medium, 2 Low.
- **IDOR & AuthN/CSRF**: 100% PASS across all views and forms.
- **Critical**:
  - `MrbDispositions.py:103`: AuditLog action length column overflow causes 500 crash on MySQL strict mode.
  - `NonConformanceReports.py:164-171`: Missing lifecycle status guard on NCR deletion allows permanent destruction of regulated records.
- **High**:
  - `forms/NonConformance/MrbDispositions.py:30, 53`: Mass assignment of derived financial field `total_cost_impact`.
  - Deletion views: Missing status guards on deleting active quarantine holds, approved MRB dispositions, and active/closed process deviations.
  - `MrbDispositionForm.clean()`: Tripartite board approvals validation missing when status="approved".
  - `NonConformanceReports.py:141-152`: Closed NCR records can be modified via edit form without tenant admin gate.
- **Medium / Low**:
  - Non-negative boundary validation in forms.
  - Inconsistent closure attribution on direct closed creation.
  - Template L10 crashes on `approved_by` and `closed_by`.
  - Canonical verb `"contain"` -> `"create"`.
