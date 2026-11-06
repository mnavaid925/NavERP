# Review Findings: Sub-module 10.11 — KPI & Performance Scorecards

**Base SHA**: `b277eb8d6d606d2854f63b4e5265445b99c70922`
**Review Passes**:
1. `code-reviewer`
2. `explorer`
3. `frontend-reviewer`
4. `performance-reviewer`
5. `qa-smoke-tester`
6. `security-reviewer`

---

## Findings Summary

| ID | Severity | File(s) | Description | Status |
|---|---|---|---|:---:|
| **C1** | Critical | `apps/bi/views/PerformanceScorecards/*.py` | `write_audit_log` signature mismatch raising `TypeError: unexpected keyword argument 'model_name'` on all POST mutations | [x] fixed — aligned write_audit_log signature across all 4 views |
| **C2** | Critical | `apps/bi/forms/PerformanceScorecards/*.py` | `owner` field not scoped to `tenant=self.tenant` and missing from `reject_foreign` across 3 forms | [x] fixed — scoped owner queryset to tenant and added to reject_foreign |
| **C3** | Critical | `apps/bi/views/PerformanceScorecards/*.py` | Missing `@tenant_admin_required` gate on metric updates and recalculation endpoints | [x] fixed — added tenant_admin_required to kpi refresh, scorecard recalculate, and record actual endpoints |
| **C4** | Critical | `apps/bi/views/PerformanceScorecards/KpiDefinitions.py`, `templates/bi/kpi_performance_scorecards/kpi_definition/detail.html` | Broken prefetch in `kpi_definition_detail` triggers $2N+3$ query storm | [x] fixed — sorted assignments in Python and used length filter in template |
| **C5** | Critical | `apps/bi/views/PerformanceScorecards/PerformanceScorecards.py`, `apps/bi/models/PerformanceScorecards/PerformanceScorecards.py` | Redundant duplicate queries (5 queries vs 2) in scorecard detail | [x] fixed — passed evaluated assignments to get_perspective_summary and removed prefetch from bi_object |
| **I1** | Important | `apps/bi/views/PerformanceScorecards/StrategicObjectives.py`, `templates/bi/kpi_performance_scorecards/strategic_objective/detail.html` | Discarded prefetches & triple redundant `SELECT COUNT(*)` queries in objective detail | [x] fixed — evaluated querysets to list in view and used length filter in template |
| **I2** | Important | `apps/bi/views/PerformanceScorecards/KpiDefinitions.py` | Full-table scan and model object instantiation in Python for `on_target_count` in list view | [x] fixed — computed on_target via Count filter inside SQL aggregate |
| **I3** | Important | `apps/bi/views/PerformanceScorecards/PerformanceScorecards.py` | Context variable mismatch: `perspective_scores` missing from `performance_scorecard_detail` view context | [x] fixed — added perspective_scores to view context |
| **I4** | Important | `apps/bi/management/commands/seed_bi.py` | `seed_bi --flush` omits 10.11 entities from flush transaction | [x] fixed — added scorecard and kpi entities to seed_bi flush block |
| **I5** | Important | `templates/bi/kpi_performance_scorecards/kpi_definition/list.html` | Filter bar omission & dropped `status` filter on pagination in `kpi_definition_list` | [x] fixed — added status dropdown and preserved in pagination links |
| **I6** | Important | `templates/bi/kpi_performance_scorecards/performance_scorecard/list.html` | Filter bar omission & dropped `status` filter on pagination in `performance_scorecard_list` | [x] fixed — added status dropdown and preserved in pagination links |
| **I7** | Important | `templates/bi/kpi_performance_scorecards/**/*.html` | Design system palette violation: `badge-purple` is invalid in `theme.css` (L33) | [x] fixed — replaced badge-purple with valid badge-slate across all templates |
| **I8** | Important | `apps/bi/views/PerformanceScorecards/PerformanceScorecards.py` | Unused heavy prefetches (`child_objectives`, `scorecard_kpis__kpi`) in strategy map | [x] fixed — removed unused child_objectives and scorecard_kpis prefetches |
| **I9** | Important | `apps/bi/models/PerformanceScorecards/*.py` | Missing compound tenant indexes (`idx_bscr_ten_rag`, `idx_bsci_ten_trend`, `idx_bobj_ten_rag`) and simplify FK crossing in `ordering` | [x] fixed — added compound tenant indexes, simplified assignment ordering, applied migration 0029 |
| **I10** | Important | `apps/bi/models/PerformanceScorecards/PerformanceScorecards.py` | `PerformanceScorecard.save()` default reset should execute in `transaction.atomic()` after `super().save()` | [x] fixed — wrapped default scorecard reset in transaction.atomic after super save |
| **M1** | Minor | `apps/bi/views/PerformanceScorecards/*.py` | Non-numeric query parameters in list views (`department`, `fiscal_year`, `org_unit`, `scorecard`) need `.isdigit()` validation | [x] fixed — added isdigit check on all numeric FK and year query params |
| **M2** | Minor | `apps/bi/views/PerformanceScorecards/*.py` | Non-atomic multi-row mutations in scorecards, targets, and objectives should use `transaction.atomic()` | [x] fixed — wrapped mutations and recalculations in transaction.atomic |
| **M3** | Minor | `apps/bi/models/PerformanceScorecards/ScorecardKpiAssignments.py` | Chained FK traversal in `ScorecardKpiAssignment.__str__` | [x] fixed — made str resilient using fields_cache and id fallbacks |
| **M4** | Minor | `apps/bi/models/PerformanceScorecards/PerformanceScorecards.py` | Redundant `select_related("kpi")` in scorecard recalculation and summary methods | [ ] open |
| **M5** | Minor | `templates/bi/kpi_performance_scorecards/**/*.html` | Undefined utility class `text-primary` used instead of `text-brand` (L13) | [ ] open |
| **M6** | Minor | `templates/bi/kpi_performance_scorecards/**/*.html` | Filter form labels and quick refresh labels missing `for` / `id` association | [ ] open |
| **M7** | Minor | `templates/bi/kpi_performance_scorecards/**/*.html` | Inline JavaScript confirm handlers interpolating unescaped dynamic model names with single-quote breakages | [ ] open |
| **M8** | Minor | `apps/bi/views/PerformanceScorecards/ScorecardKpiAssignments.py` | `scorecard_id` in `scorecard_kpi_assignment_create` needs `.isdigit()` validation | [ ] open |

---

## Detailed Findings

### Critical

#### [C1] `write_audit_log` Signature Mismatch on Mutation Endpoints
- **Locations**:
  - `apps/bi/views/PerformanceScorecards/KpiDefinitions.py:125, 155, 185, 211`
  - `apps/bi/views/PerformanceScorecards/PerformanceScorecards.py:137, 168, 198, 216`
  - `apps/bi/views/PerformanceScorecards/ScorecardKpiAssignments.py:119, 151, 183, 205`
  - `apps/bi/views/PerformanceScorecards/StrategicObjectives.py:113, 145, 176`
- **Symptom**: All create, edit, delete, and custom POST actions call `write_audit_log(tenant=..., user=..., action=..., model_name=..., object_id=..., object_repr=..., change_summary=...)`. The actual signature in `apps/core/utils.py:10` is `write_audit_log(user, obj, action, changes=None, tenant=None)`. Calling it with unsupported kwargs causes a `TypeError` and crashes all successful form submissions with HTTP 500.
- **Fix**: Update all call-sites to standard signature:
  ```python
  write_audit_log(request.user, obj, "create", tenant=request.tenant)
  write_audit_log(request.user, obj, "update", tenant=request.tenant)
  write_audit_log(request.user, obj, "delete", tenant=request.tenant)
  ```

#### [C2] Foreign User Assignment & Cross-Tenant Leak via `owner` Field
- **Locations**:
  - `apps/bi/forms/PerformanceScorecards/KpiDefinitions.py:81-83, 95`
  - `apps/bi/forms/PerformanceScorecards/PerformanceScorecards.py:59-61, 73`
  - `apps/bi/forms/PerformanceScorecards/StrategicObjectives.py:51, 63`
- **Symptom**: `self.fields["owner"].queryset` queries `User.objects.filter(is_active=True)` without scoping to `tenant=self.tenant`, and `reject_foreign` fails to guard `"owner"`. This exposes foreign tenant usernames and allows cross-tenant assignment via forged POSTs.
- **Fix**: In `__init__`, set:
  ```python
  self.fields["owner"].queryset = User.objects.filter(tenant=self.tenant, is_active=True).order_by("username")
  ```
  And add `"owner"` to `reject_foreign(self, cleaned, [..., "owner"])`.

#### [C3] Missing Administrative Authorization Gates on Metric Update & Recalculate Endpoints
- **Locations**:
  - `apps/bi/views/PerformanceScorecards/KpiDefinitions.py:198-200` (`kpi_definition_refresh`)
  - `apps/bi/views/PerformanceScorecards/PerformanceScorecards.py:211-213` (`performance_scorecard_recalculate`)
  - `apps/bi/views/PerformanceScorecards/ScorecardKpiAssignments.py:196-197` (`scorecard_kpi_assignment_record_actual`)
- **Symptom**: State-changing endpoints for recording actual metric measurements, refreshing KPI definition current values, and recalculating scorecard roll-up indices only have `@login_required`, allowing non-admin members to overwrite metrics.
- **Fix**: Add `@tenant_admin_required` decorator to all three views.

#### [C4] N+1 Query Storm in `kpi_definition_detail` Caused by Discarded Prefetch
- **Locations**:
  - `apps/bi/views/PerformanceScorecards/KpiDefinitions.py:101-103`
  - `templates/bi/kpi_performance_scorecards/kpi_definition/detail.html:308, 327-368`
- **Symptom**: Calling `.order_by("scorecard__name")` on `kpi.scorecard_assignments.all()` spawns a new query and discards prefetch cache. In template loops, accessing `a.scorecard.name` and `a.objective.name` triggers $2N+3$ queries.
- **Fix**: Sort the prefetched list in Python:
  ```python
  assignments = sorted(
      kpi.scorecard_assignments.all(),
      key=lambda a: (a.scorecard.name if a.scorecard else ""),
  )
  ```
  In template line 308, change `{{ assignments.count }}` to `{{ assignments|length }}`.

#### [C5] Multiple Redundant Queries and Wasted Prefetches in `performance_scorecard_detail`
- **Locations**:
  - `apps/bi/views/PerformanceScorecards/PerformanceScorecards.py:103-112`
  - `apps/bi/models/PerformanceScorecards/PerformanceScorecards.py:176`
- **Symptom**: Executes 5 database queries fetching the same assignments table (unused prefetches in `bi_object`, explicit query for `all_kpis`, and another query in `get_perspective_summary()`).
- **Fix**: Remove `prefetch_related` from `bi_object`, evaluate `all_kpis` into a list once, and pass it to `scorecard.get_perspective_summary(assignments=all_kpis)`.

---

### Important

#### [I1] Discarded Prefetches & Triple Duplicate COUNT Queries in `strategic_objective_detail`
- **Locations**:
  - `apps/bi/views/PerformanceScorecards/StrategicObjectives.py:87-90`
  - `templates/bi/kpi_performance_scorecards/strategic_objective/detail.html:65, 87, 99, 214`
- **Symptom**: Prefetches discarded by `.order_by(...)`, and template evaluates `.count` 4 times, triggering 11 queries instead of 2.
- **Fix**: Remove `prefetch_related` from `bi_object`, evaluate `child_objectives` and `assigned_kpis` into lists in the view, and use `|length` in the template.

#### [I2] Full-Table Scan & Heavy Object Allocation for `on_target_count` in `kpi_definition_list`
- **Locations**: `apps/bi/views/PerformanceScorecards/KpiDefinitions.py:24-38`
- **Symptom**: `on_target_count = sum(1 for k in qs if k.calculate_rag_status() == "green")` instantiates all model objects for tenant in memory before filters/pagination.
- **Fix**: Compute `on_target` via `Count("id", filter=...)` inside the existing SQL `qs.aggregate()` call.

#### [I3] Context Variable Mismatch: `perspective_scores` Missing in `performance_scorecard_detail`
- **Locations**: `apps/bi/views/PerformanceScorecards/PerformanceScorecards.py:114-122`
- **Symptom**: Contract pins `perspective_scores`, but view only passes `perspective_summary`.
- **Fix**: Add `"perspective_scores": perspective_summary` to view context.

#### [I4] `seed_bi --flush` Omits 10.11 Entities from Flush Transaction
- **Locations**: `apps/bi/management/commands/seed_bi.py:75-116`
- **Symptom**: `python manage.py seed_bi --flush` leaves 10.11 records in DB, breaking clean re-seeding.
- **Fix**: Add `ScorecardKpiAssignment`, `PerformanceScorecard`, `StrategicObjective`, `KpiDefinition` deletions in atomic flush block.

#### [I5] Filter Bar Omission & Dropped `status` Filter on Pagination in `kpi_definition_list`
- **Locations**: `templates/bi/kpi_performance_scorecards/kpi_definition/list.html:79-130, 248, 264`
- **Symptom**: Filter form omits `<select name="status">`, and pagination links drop `status` param.
- **Fix**: Add status select dropdown and preserve `&status={{ request.GET.status }}` in pagination links.

#### [I6] Filter Bar Omission & Dropped `status` Filter on Pagination in `performance_scorecard_list`
- **Locations**: `templates/bi/kpi_performance_scorecards/performance_scorecard/list.html:88-140, 248, 264`
- **Symptom**: Filter form omits `<select name="status">`, and pagination links drop `status` param.
- **Fix**: Add status select dropdown and preserve `&status={{ request.GET.status }}` in pagination links.

#### [I7] Design System Palette Violation: `badge-purple` is Invalid in `theme.css` (L33)
- **Locations**:
  - `templates/bi/kpi_performance_scorecards/kpi_definition/list.html:176`
  - `templates/bi/kpi_performance_scorecards/kpi_definition/detail.html:133, 336`
  - `templates/bi/kpi_performance_scorecards/performance_scorecard/strategy_map.html:160`
  - `templates/bi/kpi_performance_scorecards/scorecard_kpi_assignment/list.html:172`
  - `templates/bi/kpi_performance_scorecards/scorecard_kpi_assignment/detail.html:136`
  - `templates/bi/kpi_performance_scorecards/strategic_objective/list.html:171`
  - `templates/bi/kpi_performance_scorecards/strategic_objective/detail.html:19, 139, 243`
- **Symptom**: `badge-purple` does not exist in `static/css/theme.css` and renders unstyled.
- **Fix**: Replace `badge-purple` with `badge-info` or `badge-slate` for `learning_growth`.

#### [I8] Unused Heavy Prefetches in `performance_scorecard_strategy_map`
- **Locations**: `apps/bi/views/PerformanceScorecards/PerformanceScorecards.py:233-235`
- **Symptom**: Prefetches `child_objectives` and `scorecard_kpis__kpi`, which are never rendered.
- **Fix**: Remove unused prefetches from `objectives` query.

#### [I9] Missing Compound Tenant Indexes and Simplify FK Crossing in `ordering`
- **Locations**:
  - `apps/bi/models/PerformanceScorecards/PerformanceScorecards.py`
  - `apps/bi/models/PerformanceScorecards/ScorecardKpiAssignments.py`
  - `apps/bi/models/PerformanceScorecards/StrategicObjectives.py`
- **Symptom**: Frequent filtering on `(tenant, overall_rag_status)`, `(tenant, trend_direction)`, `(tenant, rag_status)` lack indexes. `ScorecardKpiAssignment.Meta.ordering` references `kpi__name` which forces automatic INNER JOIN.
- **Fix**: Add compound indexes and simplify ordering to `["scorecard", "perspective", "sort_order", "id"]`.

#### [I10] Non-Atomic Default Reset in `PerformanceScorecard.save()`
- **Locations**: `apps/bi/models/PerformanceScorecards/PerformanceScorecards.py:101-105`
- **Symptom**: If `is_default=True`, resetting other default scorecards is done without `transaction.atomic()`.
- **Fix**: Wrap in `transaction.atomic()` after `super().save()`.

---

## Minor Findings

#### [M1] Missing `.isdigit()` Validation on Filter GET Parameters in List Views
- **Locations**:
  - `apps/bi/views/PerformanceScorecards/KpiDefinitions.py:67-69`
  - `apps/bi/views/PerformanceScorecards/PerformanceScorecards.py:64-70`
  - `apps/bi/views/PerformanceScorecards/ScorecardKpiAssignments.py:48-50`
  - `apps/bi/views/PerformanceScorecards/StrategicObjectives.py:54-56`
- **Fix**: Add `.isdigit()` checks before filtering by `department`, `fiscal_year`, `org_unit`, or `scorecard`.

#### [M2] Non-Atomic Multi-Row Mutations in Scorecards, Targets, and Objectives
- **Locations**:
  - `apps/bi/views/PerformanceScorecards/ScorecardKpiAssignments.py:116-204`
  - `apps/bi/views/PerformanceScorecards/StrategicObjectives.py:110-144`
- **Fix**: Wrap save + recalculate calls in `transaction.atomic()`.

#### [M3] Chained FK Traversal in `ScorecardKpiAssignment.__str__`
- **Locations**: `apps/bi/models/PerformanceScorecards/ScorecardKpiAssignments.py:95-96`
- **Fix**: Make `__str__` resilient using `self.scorecard_id` and `self.kpi_id`.

#### [M4] Redundant `select_related("kpi")` in Recalculation Methods
- **Locations**: `apps/bi/models/PerformanceScorecards/PerformanceScorecards.py:116, 176`
- **Fix**: Remove `.select_related("kpi")` from `self.kpi_assignments.all()` in both methods.

#### [M5] Undefined Utility Class `text-primary` Used Instead of `text-brand` (L13)
- **Locations**: Templates across `kpi_definition`, `performance_scorecard`, `scorecard_kpi_assignment`, `strategic_objective`.
- **Fix**: Replace `text-primary` with `text-brand` (or `text-blue-600`).

#### [M6] Filter Form Labels and Quick Refresh Labels Missing `for` / `id` Association
- **Locations**: List views filter bars and `kpi_definition/detail.html`.
- **Fix**: Add matching `for` and `id` attributes.

#### [M7] Inline JavaScript Confirm Handlers Interpolating Unescaped Model Names
- **Locations**: List view delete buttons across models.
- **Fix**: Use static confirmation message e.g. `onsubmit="return confirm('Are you sure you want to delete this record?');"`.

#### [M8] `scorecard_id` in `scorecard_kpi_assignment_create` Needs `.isdigit()` Validation
- **Locations**: `apps/bi/views/PerformanceScorecards/ScorecardKpiAssignments.py:101-104`
- **Fix**: Add `.isdigit()` validation before querying `PerformanceScorecard`.
