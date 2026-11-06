# Review Findings: Module 10.9 — Standard & Operational Reporting

**Base SHA:** `c17d2e0e632e3147e25610d88a12ebb011aeea51`
**Head SHA:** `c1da14b8df66166fcc296dca454bdd219f936256`
**Target Sub-module:** BI 10.9 (Standard & Operational Reporting)
**Entities Covered:**
- `ReportDefinition` (`BRPT-`)
- `ReportParameter` (`BPAR-`)
- `ReportExecution` (`BRUN-`)
- `ReportDrillPath` (`BDRP-`)

---

## Pass 1: Code Reviewer (`code-reviewer`)

### Critical
*None.* Multi-tenancy isolation (`tenant=request.tenant`), model tenant keys, view-level `@tenant_admin_required` decorators, `@require_POST` delete guards, and migration coverage are strictly enforced.

### Important
1. `templates/bi/operational_reporting/report_definition/viewer.html:161` & `templates/bi/operational_reporting/report_definition/print.html:117` — **Invalid use of `dictsort` template filter on dictionary renders report data columns and parameter prompt values silently blank.**
   Django's `dictsort` filter sorts a list of dicts by key; when applied to a single `dict` (`row` or `applied_params`), it returns `""`.
   - In `viewer.html:161` and `print.html:117`, `{{ row|dictsort:col.field }}` evaluates to `""`, causing standard columns like `"description"` ("Account Title & Category") to render completely empty `<td></td>` cells.
   - In `viewer.html:56, 61, 65`, `applied_params|dictsort:param.parameter_name` also returns `""`, which prevents submitted parameter values from persisting in prompt inputs and breaks dropdown pre-selection.
2. `apps/bi/views/OperationalReporting/ReportParameters.py:34-36, 77-80` (and `ReportExecutions.py:52-54`, `ReportDrillPaths.py:37-39, 79-82`) — **Unvalidated integer FK GET parameter crashes with `ValueError` (500) on hand-crafted or non-numeric queries (L11).**
   `report_id = request.GET.get("report", "").strip()` is queried directly against the database (`qs.filter(report_id=report_id)` or `get_object_or_404(..., pk=report_id)`) without checking `.isdigit()`. Submitting `?report=abc` or `?report=test` causes a 500 `ValueError: Field 'id' expected a number but got 'abc'`.
3. `apps/bi/views/OperationalReporting/ReportDefinitions.py:203-225` — **`report_definition_clone` crashes with unhandled `IntegrityError` (500) when cloning with an existing slug.**
   `ReportCloneForm` does not check slug uniqueness per tenant. If a user clones a report twice with the default name/slug (`f"{source_report.slug}-copy"`), `ReportDefinition.objects.create()` raises an unhandled database `IntegrityError` on the `bi_brpt_tenant_slug_uniq` constraint.

### Minor
1. `apps/bi/models/OperationalReporting/ReportParameters.py:112-113`, `ReportExecutions.py:133`, `ReportDrillPaths.py:83` — **Unsupported `badge-purple` CSS class renders badges unstyled (L33).**
   `theme.css` only provides `.badge-green`, `.badge-red`, `.badge-amber`, `.badge-info`, `.badge-muted`, `.badge-slate`. `choice_single`, `choice_multi`, `drill_through`, and `operational_report` map to `badge-purple`, rendering without design-system badge background and text colors. Map to valid color-named classes (`badge-info`, `badge-slate`, or `badge-green`).
2. `apps/bi/views/OperationalReporting/ReportDefinitions.py:121` — **Missing `form.save_m2m()` call after `form.save(commit=False)` in `report_definition_create`.**
   Omitting `form.save_m2m()` is a convention defect that can cause silent data loss if M2M fields are added later.
3. `templates/bi/operational_reporting/report_definition/list.html:223, 226` — **Pagination links drop `is_prebuilt` filter parameter.**
   The pagination links preserve `q`, `category`, `report_type`, and `status`, but omit `is_prebuilt`.

---

## Pass 2: Codebase Explorer (`explorer`)

### Critical
*None.* All 24 URL routes, 24 views, 5 forms, and 15 templates resolve cleanly. System check reports 0 issues.

### Important
1. `templates/bi/operational_reporting/report_definition/viewer.html:56, 61, 65, 161` & `print.html:117` — **Duplicate/Confirmed: `dictsort` filter used on dictionary instances returns empty string.**
   - Confirmed `{{ row|dictsort:col.field }}` in fallback column branch causes `description` and non-standard fields to render as blank `<td></td>`.
   - Confirmed `{{ applied_params|dictsort:param.parameter_name }}` fails to restore user prompt values.

### Minor
1. `apps/bi/views/OperationalReporting/ReportParameters.py:112`, `ReportDrillPaths.py:108` — **Redirect target variance for parameter and drill path deletions:**
   - Both redirect to `bi:report_definition_detail` (parent report) instead of entity list. (Good UX, but slight variance from contract).
2. `apps/bi/views/OperationalReporting/ReportDefinitions.py:195` — **Context key alias in `clone.html`:**
   - View passes `source_report`; contract listed `report`.
3. `apps/bi/views/OperationalReporting/ReportExecutions.py:165` — **`report_execution_export` serves `xlsx` format with CSV MIME and contents.**
   - Export logic outputs delimited text regardless of whether CSV or XLSX was chosen.

---

## Pass 3: Frontend Reviewer (`frontend-reviewer`)

### Critical
1. `templates/bi/operational_reporting/report_definition/viewer.html:56, 61, 65, 161` & `print.html:117` — **[C1] Misuse of `dictsort` filter for dictionary key lookup in `viewer.html` and `print.html`.**
   - In `viewer.html:161` & `print.html:117`, `{{ row|dictsort:col.field }}` in the `{% else %}` branch evaluates to `""`, rendering standard mock columns like `"description"` and custom columns completely blank.
   - In `viewer.html:56, 65`, `value="{{ applied_params|dictsort:param.parameter_name|default:param.default_value }}"` evaluates `dictsort` to `""`, losing user-submitted prompt inputs.
   - In `viewer.html:61`, `{% if applied_params|dictsort:param.parameter_name == choice.value %}selected{% endif %}` compares `"" == choice.value`, failing to re-select submitted choices.

### Important
1. `apps/bi/models/OperationalReporting/ReportDrillPaths.py:80`, `ReportExecutions.py:126`, `ReportParameters.py:104` — **[I1] Non-existent theme class `badge-purple` returned by model properties (L33).**
   - `theme.css` has no `.badge-purple`.
   - `ReportDrillPath.badge_target_type` maps `"operational_report": "badge-purple"`.
   - `ReportExecution.badge_mode` maps `"drill_through": "badge-purple"`.
   - `ReportParameter.badge_type` maps `"choice_single"` and `"choice_multi"` to `"badge-purple"`.
   - Fix: Map to valid color-named classes (`badge-info`, `badge-slate`, or `badge-green`).
2. `templates/bi/operational_reporting/*/*/detail.html` — **[I2] Missing "Back to Reports" / "Back to List" action button in detail header page-actions.**
   - Detail page-actions omit standard "Back to List" action button alongside Edit/Delete.

### Minor
1. `templates/bi/operational_reporting/report_definition/print.html:104-123` — **[M1] Missing `{% empty %}` fallback row in print view.**
   - If report returns 0 rows matching prompt criteria, print table renders an empty tbody without an explanatory empty row.
2. `templates/bi/operational_reporting/*/*.html` — **[M2] Raw Tailwind color utilities lack paired `dark:` variants in certain headings/subheadings.**

---

## Pass 4: Performance Reviewer (`performance-reviewer`)

### Critical
*None.*

### Important
1. `apps/bi/views/OperationalReporting/ReportDefinitions.py:95-97` & `templates/.../detail.html:142, 146, 150` — **Redundant COUNT queries and sliced QuerySet count drift in `report_definition_detail`.**
   - `parameters.count` and `drill_paths.count` run separate `SELECT COUNT(*)` queries before loops iterate the same objects.
   - Slicing `executions[:10]` and calling `executions.count` produces a subquery count bounded at 10.
   - Fix: Evaluate `list(report.parameters...)`, `list(report.source_drill_paths...)`, and `total_executions_count = report.executions.count()` in view.
2. `apps/bi/views/OperationalReporting/ReportParameters.py:42`, `ReportExecutions.py:60`, `ReportDrillPaths.py:45` — **Unused heavy JSON & Text fields loaded in list filter dropdowns.**
   - Filter querysets pull large JSON/text columns (`columns_config_json`, `bands_config_json`, `raw_query`, `styling_css`).
   - Fix: Use `.only("id", "name", "number")` for filter dropdown querysets.
3. `apps/bi/models/OperationalReporting/ReportExecutions.py:102-107` — **Missing composite indexes on high-velocity `ReportExecution` table.**
   - Add `Index(fields=["tenant", "report", "-started_at"], name="idx_brun_ten_rpt_start")`
   - Add `Index(fields=["tenant", "output_format"], name="idx_brun_ten_format")`
   - Add `Index(fields=["tenant", "execution_mode"], name="idx_brun_ten_mode")`

### Minor
1. `apps/bi/views/OperationalReporting/ReportExecutions.py:150-158` — **Unselected foreign key lookup in `report_execution_delete`.**
   - `bi_object(request, ReportExecution, pk)` lacks `select_related=("report",)`, causing extra query when reading `execution.report.number` for audit log.

---

