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

## Final Deduplicated & Prioritized Findings Register

### Critical Findings

- [x] **[C1] Unhandled HTTP 500 on duplicate slug during report cloning** (Fixed: added `tenant` parameter and `clean_new_slug` / `clean` uniqueness checks in `ReportCloneForm`, passed `tenant=request.tenant` in `report_definition_clone` view)
  - **Locations**: `apps/bi/forms/OperationalReporting/ReportDefinitions.py:123-140`, `apps/bi/views/OperationalReporting/ReportDefinitions.py:192-264`
  - **Issue**: `ReportCloneForm` does not validate tenant uniqueness of `new_slug`. When `ReportDefinition.objects.create(tenant=request.tenant, slug=new_slug, ...)` runs with a duplicate slug, an `IntegrityError` is thrown on `bi_brpt_tenant_slug_uniq`. `TenantNumbered.save()` catches this in a 5-attempt retry loop assuming a number sequence collision, then raises `IntegrityError: Could not allocate a unique BRPT number...`, crashing with HTTP 500.
  - **Fix**: Accept `tenant` in `ReportCloneForm`, add `clean_new_slug` to validate `ReportDefinition.objects.filter(tenant=self.tenant, slug=slug).exists()`, and return clean form validation error.

- [x] **[C2] Misuse of `dictsort` template filter on dictionary renders report data columns and parameter prompt values silently blank** (Fixed: populated parameter objects with `.runtime_value` in views, bound inputs/selects to `param.runtime_value`, and replaced `dictsort` in `viewer.html` and `print.html` with explicit column field branches)
  - **Locations**: `templates/bi/operational_reporting/report_definition/viewer.html:56, 61, 65, 161`, `templates/bi/operational_reporting/report_definition/print.html:117`, `apps/bi/views/OperationalReporting/ReportDefinitions.py:270-335`
  - **Issue**: Django's built-in `dictsort` filter sorts lists of dicts by key; when applied to a single dictionary (`row` or `applied_params`), it returns `""`. In `viewer.html` and `print.html`, `{{ row|dictsort:col.field }}` in fallback column branches evaluates to `""`, causing `"description"` and custom columns to render completely empty `<td></td>` cells. In `viewer.html:56, 61, 65`, `applied_params|dictsort:param.parameter_name` evaluates to `""`, losing user-entered prompt inputs and failing dropdown pre-selection.
  - **Fix**: In `report_definition_viewer` and `print`, populate parameter objects with `.runtime_value`, render `param.runtime_value` in inputs/selects, and in `viewer.html`/`print.html` add explicit handling for `description` and row cell dictionary lookups without `dictsort`.

- [x] **[C3] Stored Cross-Site Scripting (XSS) via `styling_css|safe` in Print View** (Fixed: added `clean_styling_css` in `ReportDefinitionForm` to block `</style>`, `<script>`, `<iframe`, and `javascript:` schemes, and sanitized closing style tags in `print.html`)
  - **Locations**: `templates/bi/operational_reporting/report_definition/print.html:31`, `apps/bi/forms/OperationalReporting/ReportDefinitions.py:31, 51`
  - **Issue**: `{{ report.styling_css|safe }}` is rendered inside `<style>` blocks in `print.html` without sanitizing closing HTML tags. An attacker or rogue tenant user can configure a report with CSS containing `</style><script>...` to break out of the style tag and execute arbitrary JavaScript.
  - **Fix**: Add `clean_styling_css` in `ReportDefinitionForm` to block `</style>`, `<script>`, `<iframe`, and `javascript:` URLs, and escape closing tags.

---

### Important Findings

- [x] **[I1] Unvalidated integer FK GET parameter crashes with `ValueError` (500) on non-numeric queries (L11)** (Fixed: guarded all `report` GET parameters with `report_id.isdigit()` across parameters, executions, and drill paths views)
  - **Locations**: `apps/bi/views/OperationalReporting/ReportParameters.py:34-36, 77-80`, `ReportExecutions.py:52-54`, `ReportDrillPaths.py:37-39, 79-82`
  - **Issue**: `report_id = request.GET.get("report", "").strip()` is queried directly against `report_id=report_id` or `get_object_or_404(..., pk=report_id)` without checking `.isdigit()`. Submitting `?report=abc` crashes with `ValueError: Field 'id' expected a number`.
  - **Fix**: Guard with `if report_id and report_id.isdigit():` before applying the filter or `get_object_or_404`.

- [x] **[I2] Non-existent theme class `badge-purple` returned by model properties (L33)** (Fixed: remapped all `badge-purple` properties to valid theme classes `badge-slate` and `badge-info` across `ReportDrillPath`, `ReportExecution`, and `ReportParameter`)
  - **Locations**: `apps/bi/models/OperationalReporting/ReportDrillPaths.py:80`, `ReportExecutions.py:126`, `ReportParameters.py:104`
  - **Issue**: `theme.css` only provides `.badge-green`, `.badge-red`, `.badge-amber`, `.badge-info`, `.badge-muted`, `.badge-slate`. `choice_single`, `choice_multi`, `drill_through`, and `operational_report` map to `badge-purple`, rendering without CSS styles.
  - **Fix**: Map them to valid color-named classes (`badge-info`, `badge-slate`, or `badge-green`).

- [x] **[I3] CSV Formula Injection in Export Header Row** (Fixed: wrapped all CSV export column headers in `csv_safe(...)` in `report_execution_export`)
  - **Location**: `apps/bi/views/OperationalReporting/ReportExecutions.py:179`
  - **Issue**: In `report_execution_export`, row cells are sanitized with `csv_safe(...)`, but column titles in the header row are written without sanitization. If a column title begins with `=`, `+`, `-`, or `@`, spreadsheet software executes it as a formula.
  - **Fix**: Apply `csv_safe(...)` to every column title written to the CSV header row.

- [x] **[I4] Unauthenticated State Mutation & Audit Flooding via HTTP GET in Report Viewer** (Fixed: removed database execution creation from read-only GET `report_definition_viewer`, reserving runs for POST `report_execution_run`)
  - **Location**: `apps/bi/views/OperationalReporting/ReportDefinitions.py:312-326`
  - **Issue**: Loading `report_definition_viewer` with an HTTP GET request automatically creates a persistent `ReportExecution` database record. GET requests are not CSRF-protected and can be triggered by crawlers, prefetching, or image tags, flooding execution audit logs.
  - **Fix**: Remove automatic execution creation on read-only GET requests, reserving execution creation for explicit POST execution triggers (`report_execution_run`).

- [x] **[I5] Redundant COUNT queries and sliced QuerySet count drift in `report_definition_detail`** (Fixed: pre-evaluated `parameters_count`, `drill_paths_count`, and `total_executions_count` in view, rendering them in `detail.html`)
  - **Locations**: `apps/bi/views/OperationalReporting/ReportDefinitions.py:95-97`, `templates/bi/operational_reporting/report_definition/detail.html:142, 146, 150`
  - **Issue**: In `detail.html`, `parameters.count` and `drill_paths.count` run separate SQL `COUNT(*)` queries before loops iterate the same objects. Furthermore, slicing `executions[:10]` and calling `executions.count` produces a subquery count capped at 10.
  - **Fix**: Evaluate `list(report.parameters...)`, `list(report.source_drill_paths...)`, and `total_executions_count = report.executions.count()` in the view and pass `parameters_count`, `drill_paths_count`, `total_executions_count` in context.

- [x] **[I6] Unused heavy JSON & Text fields loaded in list filter dropdowns** (Fixed: applied `.only("id", "name", "number")` to report querysets across all 3 list views)
  - **Locations**: `apps/bi/views/OperationalReporting/ReportParameters.py:42`, `ReportExecutions.py:60`, `ReportDrillPaths.py:45`
  - **Issue**: Filter dropdown querysets load full `ReportDefinition` records including large text and JSON fields (`columns_config_json`, `bands_config_json`, `raw_query`, `styling_css`).
  - **Fix**: Add `.only("id", "name", "number")` to filter dropdown querysets in all three views.

- [x] **[I7] Missing composite indexes on high-velocity `ReportExecution` table** (Fixed: added composite indexes `idx_brun_ten_rpt_start`, `idx_brun_ten_format`, and `idx_brun_ten_mode` to `ReportExecution.Meta.indexes`, generated and applied migration `0023`)
  - **Location**: `apps/bi/models/OperationalReporting/ReportExecutions.py:102-107`
  - **Issue**: `ReportExecution` records grow rapidly. History queries filtering by `(tenant, report)` ordered by `-started_at` perform filesorts without a composite index. Filtering on `output_format` and `execution_mode` also lacks tenant composite indexes.
  - **Fix**: Add composite indexes in `ReportExecution.Meta.indexes`:
    - `Index(fields=["tenant", "report", "-started_at"], name="idx_brun_ten_rpt_start")`
    - `Index(fields=["tenant", "output_format"], name="idx_brun_ten_format")`
    - `Index(fields=["tenant", "execution_mode"], name="idx_brun_ten_mode")`
    Generate and apply database migration.

- [x] **[I8] Missing "Back to Reports" / "Back to List" action button in detail header page-actions** (Fixed: added back-to-list navigation action buttons across all four detail templates)
  - **Locations**: `templates/bi/operational_reporting/report_definition/detail.html:25-51`, `report_parameter/detail.html:33-51`, `report_execution/detail.html:25-47`, `report_drill_path/detail.html:28-46`
  - **Issue**: Detail page header `.page-actions` omit standard "Back to List" navigation button.
  - **Fix**: Add `<a href="..." class="btn btn-outline"><i data-lucide="arrow-left"></i><span>Back</span></a>` in `.page-actions`.

---

### Minor Findings

- [x] **[M1] Missing `form.save_m2m()` call after `form.save(commit=False)` in `report_definition_create`** (Fixed: added `form.save_m2m()` immediately after `report.save()`)
  - **Location**: `apps/bi/views/OperationalReporting/ReportDefinitions.py:121`
  - **Issue**: `form.save_m2m()` is omitted after `form.save(commit=False)`.
  - **Fix**: Add `form.save_m2m()` immediately after `report.save()`.

- [x] **[M2] Pagination links drop `is_prebuilt` filter parameter** (Fixed: appended `is_prebuilt` filter parameter to pagination links in `report_definition/list.html`)
  - **Location**: `templates/bi/operational_reporting/report_definition/list.html:223, 226`
  - **Issue**: Pagination links in report definition list preserve `q`, `category`, `report_type`, and `status`, but omit `is_prebuilt`.
  - **Fix**: Append `{% if is_prebuilt %}&is_prebuilt={{ is_prebuilt }}{% endif %}` to previous/next page link URLs.

- [ ] **[M3] Missing `{% empty %}` fallback row in print view**
  - **Location**: `templates/bi/operational_reporting/report_definition/print.html:104-123`
  - **Issue**: When a printed report returns 0 rows, the table body is empty without an explanatory note.
  - **Fix**: Add `{% empty %}` row: `<td colspan="10" class="text-center py-6 text-slate-500 italic">No records found matching prompt criteria.</td>`.

- [ ] **[M4] Unselected foreign key lookup in `report_execution_delete`**
  - **Location**: `apps/bi/views/OperationalReporting/ReportExecutions.py:150-158`
  - **Issue**: `bi_object(request, ReportExecution, pk)` lacks `select_related=("report",)`, causing an avoidable query when recording audit log changes.
  - **Fix**: Add `select_related=("report",)` to `bi_object(...)`.

- [ ] **[M5] Privileged tenant-admin action buttons exposed to non-admins in list tables**
  - **Locations**: `templates/bi/operational_reporting/*/*/list.html`
  - **Issue**: Edit/delete/clone buttons for `@tenant_admin_required` views are shown to staff members who lack admin privileges.
  - **Fix**: Wrap action buttons in `{% if request.user.is_superuser or request.is_tenant_admin %}`.

- [ ] **[M6] Missing regular expression validation in `ReportParameterForm`**
  - **Location**: `apps/bi/forms/OperationalReporting/ReportParameters.py:22`
  - **Issue**: Malformed regular expression strings in `validation_regex` cause unhandled `re.error` at runtime.
  - **Fix**: Add `clean_validation_regex` to verify `re.compile(pattern)` succeeds.

- [ ] **[M7] Discrepant `report` field in `ReportExecutionRunForm`**
  - **Location**: `apps/bi/forms/OperationalReporting/ReportExecutions.py:11-16`
  - **Issue**: `ReportExecutionRunForm` includes a `report` dropdown even though the report is already fixed by URL kwarg `report_pk`.
  - **Fix**: Exclude `report` from `ReportExecutionRunForm.Meta.fields`.

---

## Detailed Pass Logs (Historical)

<details>
<summary>Pass 1: Code Reviewer (code-reviewer)</summary>

### Critical
*None.*

### Important
1. `templates/bi/operational_reporting/report_definition/viewer.html:161` & `print.html:117` — Invalid use of `dictsort` template filter on dictionary.
2. `apps/bi/views/OperationalReporting/ReportParameters.py:34-36` — Unvalidated integer FK GET parameter crashes with `ValueError` (L11).
3. `apps/bi/views/OperationalReporting/ReportDefinitions.py:203-225` — `report_definition_clone` crashes with unhandled `IntegrityError` (500) on duplicate slug.

### Minor
1. Unsupported `badge-purple` CSS class in model properties.
2. Missing `form.save_m2m()` call in `report_definition_create`.
3. Pagination links drop `is_prebuilt` filter parameter.

</details>

<details>
<summary>Pass 2: Codebase Explorer (explorer)</summary>

### Critical
*None.* All 24 routes, 24 views, 5 forms, 15 templates resolve cleanly. System check reports 0 issues.

### Important
1. Confirmed `dictsort` filter bug on dictionaries in `viewer.html` and `print.html`.

### Minor
1. Redirect target variance for parameter and drill path deletions.
2. Context key alias in `clone.html` (`source_report` vs `report`).
3. `report_execution_export` serves xlsx format as CSV text.

</details>

<details>
<summary>Pass 3: Frontend Reviewer (frontend-reviewer)</summary>

### Critical
1. `viewer.html` & `print.html` dictsort filter defect breaks data column and prompt input rendering.

### Important
1. Non-existent theme class `badge-purple` in model properties.
2. Missing "Back to List" action button in detail header page-actions.

### Minor
1. Missing `{% empty %}` fallback row in print view.
2. Raw Tailwind color utilities lack paired `dark:` variants.

</details>

<details>
<summary>Pass 4: Performance Reviewer (performance-reviewer)</summary>

### Critical
*None.*

### Important
1. Redundant COUNT queries and sliced QuerySet count drift in `report_definition_detail`.
2. Unused heavy JSON & Text fields loaded in list filter dropdowns.
3. Missing composite indexes on high-velocity `ReportExecution` table (`idx_brun_ten_rpt_start`, `idx_brun_ten_format`, `idx_brun_ten_mode`).

### Minor
1. Unselected foreign key lookup in `report_execution_delete`.

</details>

<details>
<summary>Pass 5: QA Smoke Tester (qa-smoke-tester)</summary>

### Critical
1. Unhandled HTTP 500 on duplicate slug during report cloning.

### Important
*None.* (56 passing test scenarios across all routes, exports, junk params, IDOR, permissions).

### Minor
*None.*

</details>

<details>
<summary>Pass 6: Security Reviewer (security-reviewer)</summary>

### Critical
1. Stored Cross-Site Scripting (XSS) via `styling_css|safe` in Print View.

### Important
1. CSV Formula Injection in Export Header Row.
2. Unauthenticated State Mutation & Audit Flooding via HTTP GET in Report Viewer.

### Minor
1. Unhandled `IntegrityError` (HTTP 500) on Report Clone Duplicate Slug.
2. Privileged Tenant-Admin Action Buttons Exposed to Non-Admins in List Templates.
3. Missing Regular Expression Validation in `ReportParameterForm`.
4. Form Parameter Discrepancy in `report_execution_run`.

</details>
