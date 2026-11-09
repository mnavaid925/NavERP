# Review Findings — Module 11.3: Asset Classification & Categorization

**Review Target Range:** `2806da08558e720535beb100b7bc06390d117b6f...10550949dbf972e187d73124cecc3babf165b58b`
**Date:** 2026-11-09
**Status:** Completed by Phase 5 `code-fixer`

---

## Consolidated Action Items (Deduplicated & Prioritized)

### Critical
*None.*

---

### Important

- [x] **I1** — `apps/assets/views/AssetClassification/AssetCriticalityAssessments.py:126`: Missing status guard on `asset_criticality_assessment_edit`. Allows modifying consequence scores, failure assessments, and SPOF flags on approved/superseded assessments.
  *Fix:* [x] fixed — `fix(assets): guard criticality assessment edit against approved or superseded status` (b40aa442)

- [x] **I2** — `apps/assets/views/AssetClassification/AssetCriticalityAssessments.py:154`: Missing status guard on `asset_criticality_assessment_delete`. Permits deletion of active approved or historic superseded risk assessments.
  *Fix:* [x] fixed — `security(assets): guard criticality assessment delete against approved or superseded status` (706dabd2)

- [x] **I3** — `apps/assets/models/AssetClassification/AssetSpecificationTemplates.py:27`: `DATA_TYPE_CSS["select"] = "badge-purple"` references a nonexistent CSS class (Lesson L33; theme.css only defines `badge-green/red/amber/info/muted/slate`).
  *Fix:* [x] fixed — `fix(assets): replace non-existent badge-purple with valid badge-info in DATA_TYPE_CSS` (65155908)

- [x] **I4** — `templates/assets/asset_classification/` (5 templates): Non-existent `text-green` theme class used in:
  - `asset_category/detail.html:269`
  - `asset_criticality_assessment/list.html:165`
  - `asset_model/detail.html:207`
  - `asset_specification_template/detail.html:158`
  - `asset_specification_template/list.html:155`
  *Fix:* [x] fixed — `fix(assets): use valid text-ok utility class across all 5 templates` (1defb885, 3d275605, e2198a31, 53fc652f, c0097c90)

- [x] **I5** — `apps/assets/views/AssetClassification/AssetCriticalityAssessments.py:19-21`: Chained N+1 query on `asmt.asset.location` in `asset_criticality_assessment_list`. In `list.html:129`, each row accesses `asmt.asset.location.name`.
  *Fix:* [x] fixed — `perf(assets): eliminate N+1 on asset location in criticality assessment list` (09e261a9)

- [x] **I6** — `templates/assets/asset_classification/`: Delete and approve actions in list and detail templates lack `{% if request.user.is_superuser or request.user.is_tenant_admin %}` access control checks (Lesson L27), offering privileged actions to non-admin users.
  *Fix:* [x] fixed — `security(assets): restrict category, model, assessment, and spec template delete/approve actions to tenant admin` (f34a9687, 524d80a8, 554315ec, 65e26f0f, 4351313f, e8740831, d58fb9cf, 5b80fdf4)

- [x] **I7** — `templates/assets/asset_classification/asset_specification_template/detail.html:101, 107`: Numerical `0` evaluates as falsy in `{{ template.min_numeric_value|default:"No limit" }}` and `max_numeric_value`, rendering "No limit" instead of "0".
  *Fix:* [x] fixed — `fix(assets): use default_if_none for numeric bounds to avoid masking zero values` (feaa3457)

---

### Minor

- [x] **M1** — `apps/assets/views/AssetClassification/AssetCriticalityAssessments.py:166`: `asset_criticality_assessment_approve` does not check if an assessment is already `superseded`.
  *Fix:* [x] fixed — `fix(assets): guard criticality assessment approval against approved and superseded states` (edfec8b2)

- [x] **M2** — `apps/assets/views/AssetClassification/AssetCriticalityAssessments.py:194-195`: In `asset_criticality_assessment_approve`, use tenant-scoped update for defense-in-depth:
  *Fix:* [x] fixed — `security(assets): use tenant-scoped update for asset criticality synchronization` (0951dfc2)

- [x] **M3** — `apps/assets/forms/AssetClassification/AssetCriticalityAssessments.py:126`: Unhandled `ValueError` in `AssetCriticalityAssessmentForm.clean` when executing `int(val)` on non-numeric input.
  *Fix:* [x] fixed — `fix(assets): handle non-numeric consequence score values in form clean` (f891ad41)

- [x] **M4** — `apps/assets/models/AssetClassification/AssetSpecificationTemplates.py:88`: Unchecked regex compilation in `clean()`.
  *Fix:* [x] fixed — `fix(assets): validate regex compilation syntax in AssetSpecificationTemplate.clean` (caf62984)

- [x] **M5** — `apps/assets/models/AssetClassification/AssetModels.py:91`: `AssetModel.estimated_replacement_cost` lacks non-negative validator at the model layer.
  *Fix:* [x] fixed — `fix(assets): add MinValueValidator to AssetModel.estimated_replacement_cost` (47645727) & migration 0007 (d58cb389)

- [x] **M6** — `apps/assets/models/AssetClassification/AssetCategories.py:144-153`: Add model-level tenant isolation check in `AssetCategory.clean()` hierarchy traversal loop.
  *Fix:* [x] fixed — `security(assets): validate tenant boundary in AssetCategory.clean hierarchy traversal` (29bde330)

- [x] **M7** — `apps/assets/views/AssetClassification/`: All 4 list views (`AssetCategories.py:64`, `AssetModels.py:63`, `AssetCriticalityAssessments.py:68`, `AssetSpecificationTemplates.py:61`) pass only `"q": q` instead of the pinned `"search_query"`.
  *Fix:* [x] fixed — `fix(assets): pass search_query in all 4 classification list view contexts` (0ace4acb, a0cfa2a6, 29b4ec25, 45e520b2)

- [x] **M8** — `apps/assets/views/AssetClassification/AssetCriticalityAssessments.py:42-44`: Filter parameter `asset_id` parsed in `asset_criticality_assessment_list`, but omitted from context and pagination links.
  *Fix:* [x] fixed — `fix(assets): pass selected_asset in context and preserve in pagination links` (422708f9, 29010ee7)

- [x] **M9** — `apps/assets/views/AssetClassification/AssetCategories.py:78`: Enhance `select_related` in `asset_category_detail` to `select_related=["parent__parent"]` for deep taxonomies.
  *Fix:* [x] fixed — `perf(assets): preload parent taxonomy levels in category detail view` (9e34f0d5)

- [x] **M10** — `templates/assets/asset_classification/asset_category/detail.html:93`: Simplify redundant text `{{ category.default_useful_life_months }} Months ({{ category.default_useful_life_months|floatformat:0 }} mos)` to `{{ category.default_useful_life_months }} Months`.
  *Fix:* [x] fixed — `fix(assets): simplify useful life label in category detail template` (c30df700)

- [x] **M11** — `templates/assets/asset_classification/asset_category/detail.html:223`: Replace `{{ mod.manufacturer.name|default:mod.manufacturer_name_fallback|default:"—" }}` with `{{ mod.display_manufacturer }}`.
  *Fix:* [x] fixed — `refactor(assets): reuse display_manufacturer model property in category detail template` (52882568)

- [x] **M12** — `templates/assets/asset_classification/asset_category/list.html:193` & sibling list templates: Add `p-4 border-t border-slate-100` to `.card-footer` pagination containers.
  *Fix:* [x] fixed — `style(assets): add padding and border to card footer pagination containers across all 4 list templates` (b70eab52, ba247683, 4f6fdd43, e864fa4e)

- [x] **M13** — All 12 templates: Replace `mr-1` with `me-1` on button icon spacing for RTL compatibility.
  *Fix:* [x] fixed — `style(assets): use me-1 instead of mr-1 for RTL compatibility across all 12 classification templates` (698f2e9a, af066766, a91e8575, abe9abf7, 1d51067f, 041727c7, 2fd1eea3, 33754301, edfdd333, 8ef90218, 9c944c1f, 6e9ab32d)

---

## Individual Pass Logs

### 1. Code Reviewer Pass
- **Verdict**: Commit after fixing Important findings.
- **Critical**: None.
- **Important**: Missing status guards on edit/delete for approved/superseded assessments; `badge-purple` non-existent class; `|default` vs `|default_if_none`.
- **Minor**: Re-approval guard, `search_query` context key, `asset_id` filter propagation, `int(val)` ValueError handling, regex check, replacement cost validator, category detail text display.

### 2. Explorer Pass
- **Verdict**: Commit after fixing Important findings.
- **Critical**: None.
- **Package structure & Re-exports**: 100% compliant.
- **Spine integration**: Fully aligned with `scm.Asset`, `core.Party`, `accounting.FixedAsset`.
- **Contract compliance**: All 4 models, 19 URL routes, 10 `LIVE_LINKS["11.3"]` entries match contract.

### 3. Frontend Reviewer Pass
- **Verdict**: Pass with minor findings.
- **Critical**: None.
- **Important**: Non-existent `text-green` theme class across 5 templates (fix: `text-ok`); non-existent `badge-purple` in `DATA_TYPE_CSS`.
- **Minor**: `.card-footer` styling, `display_manufacturer` reuse, `mr-1` vs `me-1` RTL spacing.
- **Done well**: Zero comment leaks (L2), robust pagination guards (L9), strict PK comparison with `|stringformat:"d"`.

### 4. Performance Reviewer Pass
- **Verdict**: Commit after fixing Important findings.
- **Critical**: None.
- **Important**: Chained N+1 query on `asmt.asset.location` in `asset_criticality_assessment_list`. Fix: add `"asset__location"` to `select_related`.
- **Minor**: Shallow hierarchy breadcrumb select_related; SCM index recommendation.
- **Done well**: Single-query KPI aggregates via `.aggregate()`, robust tenant-composite indexes on all 4 models, pre-paginator filtering.

### 5. QA Smoke Tester Pass
- **Verdict**: PASS — 47/47 checks passed (0 errors, 0 IDOR leaks).
- **All 19 sub-module URLs**: 200/302/404/405 verified against real data with `admin_acme`.
- **IDOR**: 13 cross-tenant checks returned 404 cleanly.
- **Resilience**: Handled junk parameters (`?category=abc&status=invalid`) and boundary pagination without 500s.

### 6. Security Reviewer Pass
- **Verdict**: Commit after fixing Important findings.
- **Critical**: None.
- **Important**: View status guards on edit/delete for approved/superseded assessments; template UI access control checks for privileged delete and approve actions (Lesson L27).
- **Minor**: Check superseded in approval, defense-in-depth tenant update on `scm.Asset`, form `int()` ValueError handling, regex syntax validation, replacement cost validator, model-level hierarchy tenant check.
- **Done well**: Strict multi-tenant isolation, comprehensive `reject_foreign`, mass-assignment exclusion of workflow/system fields, 100% CSRF and `@login_required` / `@tenant_admin_required` coverage.
