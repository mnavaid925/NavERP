# 6-Lane Review Findings & Action Register — Sub-module 10.12: OLAP & Multidimensional Analysis (apps/bi)

Changeset under review: `b277eb8d6d606d2854f63b4e5265445b99c70922...HEAD`

---

## Executive Summary & Action Register

All six review lanes (`code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`) were executed serially. Findings have been deduplicated, categorized by severity (Critical → Important → Minor), and assigned deterministic action IDs.

### Critical Priority
- [ ] **C1**: Fix inverted `write_audit_log` call signature across 14 callsites in `apps/bi/views/OlapAnalysis/{OlapCubes,PivotViews,WhatIfScenarios,WritebackCells}.py`. Swap arguments 2 and 3 to `write_audit_log(request.user, <instance>, "<action>", changes={...}, tenant=request.tenant)`.
- [ ] **C2**: Guard nullable user FK filter arguments (`created_by`, `committed_by`) in detail templates (`templates/bi/olap_analysis/{olap_cube,pivot_view,what_if_scenario,writeback_cell}/detail.html`). Replace filter evaluations with explicit `{% if obj.created_by %}{{ obj.created_by.get_full_name|default:obj.created_by.username }}{% else %}System{% endif %}` and `{% if scenario.committed_by %}{{ scenario.committed_by.get_full_name|default:scenario.committed_by.username }}{% else %}—{% endif %}` to prevent Lesson L10 500 errors.

### Important Priority
- [ ] **I1**: Enforce mutation and deletion guards on committed scenarios and writeback cells across views, forms, and templates (`WhatIfScenarios.py`, `WritebackCells.py`, `detail.html`, `simulate.html`). Guard `what_if_scenario_edit`, `what_if_scenario_delete`, `writeback_cell_create`, `writeback_cell_edit`, `writeback_cell_delete`. Exclude committed scenarios in `ScenarioWritebackCellForm.__init__`. Hide mutating UI action buttons when committed.
- [ ] **I2**: Apply `@tenant_admin_required` decorator to financial commit (`what_if_scenario_commit`) and all four delete views (`olap_cube_delete`, `pivot_view_delete`, `what_if_scenario_delete`, `writeback_cell_delete`) in `apps/bi/views/OlapAnalysis/`.
- [ ] **I3**: Replace non-existent CSS class `badge-purple` in theme design system (Lesson L33) with `badge-info` (or `badge-slate`) across 7 template occurrences (`olap_cube/list.html`, `olap_cube/detail.html`, `pivot_view/list.html`, `what_if_scenario/list.html`, `what_if_scenario/detail.html`, `what_if_scenario/simulate.html`).
- [ ] **I4**: Validate `drill_through_target` in `PivotAnalysisViewForm.clean_drill_through_target()` with `reverse(target)` and add template safety guard `{% if view.drill_through_enabled and view.drill_through_target %}` in `matrix.html` to prevent `NoReverseMatch` 500s.
- [ ] **I5**: Add `"matrix_rows": row_headers` to view context in `apps/bi/views/OlapAnalysis/PivotViews.py:pivot_view_matrix` to satisfy contract specification.
- [ ] **I6**: Protect lifecycle status integrity in `WhatIfScenarioForm`: exclude `"status"` from `Meta.fields` (or validate in `clean_status()` that `"committed"` cannot be manually selected) to enforce the formal commit workflow.
- [ ] **I7**: Expose `conditional_formatting_raw` JSON textarea in `PivotAnalysisViewForm` so users can configure conditional formatting rules.
- [ ] **I8**: Handle blank slug uniqueness pre-computation in forms (`OlapCubes.py`, `PivotViews.py`, `WhatIfScenarios.py`) to prevent unhandled `IntegrityError` when submitting forms with empty slugs.
- [ ] **I9**: Simplify `ScenarioWritebackCell.__str__` in `apps/bi/models/OlapAnalysis/WritebackCells.py` to `f"{self.number}"` avoiding cross-table queries during `str(obj)` calls in `write_audit_log`.
- [ ] **I10**: Optimize simulation workbench in `apps/bi/views/OlapAnalysis/WhatIfScenarios.py:what_if_scenario_simulate`: evaluate `writeback_cells = list(writeback_cells)` to eliminate redundant SQL hits, and guard recalculations with `if scenario.status != 'committed':`.

### Minor Priority
- [ ] **M1**: Update status badge fallback in `olap_cube/list.html`, `pivot_view/list.html`, `what_if_scenario/list.html` from hardcoded `Archived` to `{{ obj.get_status_display }}`.
- [ ] **M2**: Add composite index `models.Index(fields=["tenant", "cube"], name="idx_bwif_ten_cube")` to `WhatIfScenario.Meta.indexes`.
- [ ] **M3**: Bound writeback cells queryset on scenario detail view (`what_if_scenario_detail`) to recent 50 (`[:50]`) and link to `writeback_cell_list?scenario={{ scenario.pk }}`.
- [ ] **M4**: Pass explicit unsliced counts `pivot_views_count` and `scenarios_count` in `olap_cube_detail` context for accurate card header metrics.
- [ ] **M5**: Add `.only("id", "name")` to filter dropdown querysets in `pivot_view_list` and `writeback_cell_list`.
- [ ] **M6**: Add `aria-label="Search ..."` attributes to filter search `<input name="q">` elements across list templates.

---

## Detailed Lane Reports

### Pass 1: Code Reviewer (`code-reviewer`)
- **Critical**:
  1. `apps/bi/views/OlapAnalysis/WhatIfScenarios.py` & `WritebackCells.py` — Missing view-level status guard on committed scenarios and writeback cells allows updating or deleting already-committed financial simulations and cells.
  2. `templates/bi/olap_analysis/{olap_cube,pivot_view,what_if_scenario,writeback_cell}/detail.html` — Template evaluates filter argument `created_by.username` when `created_by` is None, raising `VariableDoesNotExist` and 500ing on detail pages (Lesson L10).
- **Important**:
  1. `apps/bi/views/OlapAnalysis/WhatIfScenarios.py` & `apps/bi/views/OlapAnalysis/{OlapCubes,PivotViews,WhatIfScenarios,WritebackCells}.py` — Missing `@tenant_admin_required` decorator on commit and destructive deletion endpoints.
  2. `apps/bi/forms/OlapAnalysis/PivotViews.py` & `templates/bi/olap_analysis/pivot_view/matrix.html` — Unvalidated `drill_through_target` input in `PivotAnalysisViewForm` crashes `matrix.html` with `NoReverseMatch`.
  3. `apps/bi/forms/OlapAnalysis/{OlapCubes,PivotViews,WhatIfScenarios}.py` — When `slug` is left empty in create forms, unique constraints check runs on empty string before `save()` generates slug, causing duplicate name collisions to crash with `IntegrityError`.
- **Minor**:
  1. List templates hardcode `Archived` in status badge fallback.
  2. `what_if_scenario_commit` sets `is_committed=True` on writeback cells but does not link `ScenarioWritebackCell.committed_budget_line`.

### Pass 2: Architecture & Contract Explorer (`explorer`)
- **Important**:
  1. `apps/bi/views/OlapAnalysis/PivotViews.py:198` — Discrepancy in `pivot_view_matrix` context: contract specifies `matrix_rows`.
  2. `apps/bi/forms/OlapAnalysis/PivotViews.py:38-51` — Model Field `conditional_formatting` missing from `PivotAnalysisViewForm`.
  3. `templates/bi/olap_analysis/pivot_view/matrix.html` & `PivotViews.py` — Dynamic `drill_through_target` lacks resolution validation.
- **Minor**:
  1. Non-standard CSS badge class `badge-purple` used across templates.
  2. Writeback cell mutation not guarded against committed scenarios.

### Pass 3: Frontend Reviewer (`frontend-reviewer`)
- **Critical**:
  1. Nullable user FK filter arguments cause 500 error on detail pages (Lesson L10).
- **Important**:
  1. Non-existent CSS class `badge-purple` in Theme Design System across 7 template occurrences (Lesson L33).
  2. Mutating action controls displayed on committed scenarios and committed cells in detail/simulate templates.
- **Minor**:
  1. Status badge fallback hardcodes `Archived`.
  2. Dynamic reverse `{% url view.drill_through_target %}` in `matrix.html` lacks existence check.
  3. Search filter inputs lack `aria-label`.

### Pass 4: Performance Reviewer (`performance-reviewer`)
- **Important**:
  1. `ScenarioWritebackCell.__str__` traverses ForeignKey without caching or select_related, triggering extra SQL queries during `write_audit_log`.
  2. Redundant database hits for writeback cells in simulation workbench (`what_if_scenario_simulate`).
  3. Missing composite index on `WhatIfScenario (tenant, cube)`.
  4. Unbounded writeback cells queryset on scenario detail view.
- **Minor**:
  1. `pivot_views.count` and `scenarios.count` on sliced querysets cap at slice limit.
  2. Filter dropdown querysets load heavy unused JSON/text fields.

### Pass 5: QA Smoke Tester (`qa-smoke-tester`)
- **Critical**:
  1. Inverted `write_audit_log` call signature across 14 callsites in all 4 view files crashes 100% of mutations with HTTP 500 (`AttributeError: type object 'str' has no attribute '_meta'`).
  2. Nullable `created_by` / `committed_by` filter argument crashes detail pages with HTTP 500.
- **Important**:
  1. Committed scenarios and writeback cells lack view-level mutation guards.
  2. Non-existent `badge-purple` CSS class in Theme Design System.
- **Minor**:
  1. Hardcoded status badge fallback text in list templates.

### Pass 6: Security Reviewer (`security-reviewer`)
- **Critical**:
  1. Absence of mutation and deletion guards on committed scenarios and writeback cells compromises ledger audit integrity.
  2. Inverted `write_audit_log` call signature breaks security audit logging and crashes all mutations.
- **Important**:
  1. Missing `@tenant_admin_required` authorization on financial commit and destructive deletions.
  2. Direct exposure of lifecycle `status` in `WhatIfScenarioForm` allows bypassing formal commit workflow.
  3. Simulation workbench performs database state mutation during standard HTTP GET request without CSRF protection.
  4. Unvalidated dynamic reverse target in `drill_through_target` risks unhandled `NoReverseMatch` 500s.
- **Minor**:
  1. Template traversal of nullable user FKs in default filter arguments.
  2. Unbounded queryset on scenario detail view.
