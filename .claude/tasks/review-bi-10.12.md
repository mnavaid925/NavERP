# 6-Lane Review Findings & Action Register — Sub-module 10.12: OLAP & Multidimensional Analysis (apps/bi)

Changeset under review: `b277eb8d6d606d2854f63b4e5265445b99c70922...HEAD`

---

## Executive Summary & Action Register

All six review lanes (`code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`) were executed serially. Findings have been deduplicated, categorized by severity (Critical → Important → Minor), and assigned deterministic action IDs.

### Critical Priority
- [x] **C1**: Fixed in `37b307ad`, `afff7f1d`, `4076846e`, `020dfa20` — Inverted `write_audit_log` call signature corrected across 14 callsites in `apps/bi/views/OlapAnalysis/{OlapCubes,PivotViews,WhatIfScenarios,WritebackCells}.py` to `write_audit_log(request.user, <instance>, "<action>", changes={...}, tenant=request.tenant)`.
- [x] **C2**: Fixed in `31b39380`, `f7f9d233`, `41142dbe`, `5ba0acef` — Guarded nullable user FK filter arguments (`created_by`, `committed_by`) in detail templates (`templates/bi/olap_analysis/{olap_cube,pivot_view,what_if_scenario,writeback_cell}/detail.html`) with explicit `{% if ... %}` conditions preventing Lesson L10 500 errors.

### Important Priority
- [x] **I1**: Fixed in `998403d6`, `38f5563b`, `656b73b0`, `f57ec3ca`, `52f3e56e`, `10afdea6` — Mutation and deletion guards on committed scenarios and writeback cells enforced across views, forms, and templates (`WhatIfScenarios.py`, `WritebackCells.py`, `detail.html`, `simulate.html`). Committed scenarios excluded from dropdown in `ScenarioWritebackCellForm.__init__`. Mutating UI action buttons hidden and replaced with locked indicators when committed.
- [x] **I2**: Fixed in `624c5f5b`, `c9f9f0c9`, `696c9abd`, `a9c943ae` — Applied `@tenant_admin_required` decorator to financial commit (`what_if_scenario_commit`) and all four delete views (`olap_cube_delete`, `pivot_view_delete`, `what_if_scenario_delete`, `writeback_cell_delete`) in `apps/bi/views/OlapAnalysis/`.
- [x] **I3**: Fixed in `5fc9d1f2`, `aed910e6`, `688a0929`, `84b49304`, `3b076d83`, `df0ec867` — Replaced invalid CSS class `badge-purple` with `badge-info` / `badge-slate` across 7 template occurrences in `templates/bi/olap_analysis/`.
- [x] **I4**: Fixed in `ec84c0b1`, `4cf1a8a5` — Validated `drill_through_target` in `PivotAnalysisViewForm.clean_drill_through_target()` with `reverse(val)` and added template safety guard `{% if view.drill_through_enabled and view.drill_through_target %}` in `matrix.html` preventing `NoReverseMatch` 500s.
- [x] **I5**: Fixed in `99cc5a61` — Added `"matrix_rows": row_headers` to view context in `apps/bi/views/OlapAnalysis/PivotViews.py:pivot_view_matrix` satisfying contract specification.
- [x] **I6**: Fixed in `09be6573` — Protected lifecycle status integrity in `WhatIfScenarioForm`: excluded `"committed"` choice in `__init__` and validated in `clean_status()` that `"committed"` cannot be manually selected to enforce formal commit workflow.
- [x] **I7**: Fixed in `d90a380b`, `515dc3a8` — Exposed `conditional_formatting_raw` JSON textarea in `PivotAnalysisViewForm` and rendered in `templates/bi/olap_analysis/pivot_view/form.html`.
- [x] **I8**: Fixed in `7b1d5eee`, `ecc28c76`, `edd11d09` — Handled blank slug uniqueness pre-computation in forms' `clean()` (`OlapCubes.py`, `PivotViews.py`, `WhatIfScenarios.py`) preventing unhandled `IntegrityError` when submitting forms with empty slugs.
- [x] **I9**: Fixed in `8409dd13` — Simplified `ScenarioWritebackCell.__str__` in `apps/bi/models/OlapAnalysis/WritebackCells.py` to `f"{self.number}"` avoiding cross-table relations during `write_audit_log`.
- [x] **I10**: Fixed in `c7665a2f` — Optimized simulation workbench in `apps/bi/views/OlapAnalysis/WhatIfScenarios.py:what_if_scenario_simulate`: evaluated `writeback_cells = list(...)` eliminating redundant SQL hits, and guarded recalculations with `if scenario.status != 'committed':`.

### Minor Priority
- [x] **M1**: Fixed in `45bc5cb5`, `38e1b5b1`, `1cb659ca` — Updated status badge fallback in `olap_cube/list.html`, `pivot_view/list.html`, `what_if_scenario/list.html` from hardcoded `Archived` to `{{ obj.get_status_display }}`.
- [x] **M2**: Fixed in `c8da9cf8`, `b3e0e525` — Added composite index `models.Index(fields=["tenant", "cube"], name="idx_bwif_ten_cube")` to `WhatIfScenario.Meta.indexes`, generated migration `0028_whatifscenario_idx_bwif_ten_cube.py`, and applied to database.
- [x] **M3**: Fixed in `c812abcf`, `192cc866` — Bounded writeback cells queryset on scenario detail view (`what_if_scenario_detail`) to recent 50 (`[:50]`), computed total count, and added register link to `writeback_cell_list?scenario={{ scenario.pk }}`.
- [x] **M4**: Fixed in `6eb002ea`, `ff567395` — Passed explicit unsliced counts `pivot_views_count` and `scenarios_count` in `olap_cube_detail` context and rendered in card headers.
- [x] **M5**: Fixed in `6f069089`, `a66ce635` — Added `.only("id", "name")` to filter dropdown querysets in `pivot_view_list` and `writeback_cell_list`.
- [x] **M6**: Fixed in `fd6ce8de`, `19f1f4f3`, `d575c3af`, `0ee3d76c` — Added `aria-label="Search ..."` attributes to filter search `<input name="q">` elements across list templates.

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
