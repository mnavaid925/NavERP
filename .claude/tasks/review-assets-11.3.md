# Review Findings — Module 11.3: Asset Classification & Categorization

**Review Target Range:** `2806da08558e720535beb100b7bc06390d117b6f...10550949dbf972e187d73124cecc3babf165b58b`
**Date:** 2026-11-09
**Status:** Ready for Phase 5 `code-fixer`

---

## Consolidated Action Items (Deduplicated & Prioritized)

### Critical
*None.*

---

### Important

- [ ] **I1** — `apps/assets/views/AssetClassification/AssetCriticalityAssessments.py:126`: Missing status guard on `asset_criticality_assessment_edit`. Allows modifying consequence scores, failure assessments, and SPOF flags on approved/superseded assessments.
  *Fix:* Add status guard to `asset_criticality_assessment_edit`:
  ```python
  if assessment.assessment_status in ("approved", "superseded"):
      messages.error(
          request,
          f"Assessment {assessment.number} is {assessment.get_assessment_status_display()} and cannot be edited."
      )
      return redirect("assets:asset_criticality_assessment_detail", pk=assessment.pk)
  ```

- [ ] **I2** — `apps/assets/views/AssetClassification/AssetCriticalityAssessments.py:154`: Missing status guard on `asset_criticality_assessment_delete`. Permits deletion of active approved or historic superseded risk assessments.
  *Fix:* Add status guard to `asset_criticality_assessment_delete`:
  ```python
  if assessment.assessment_status in ("approved", "superseded"):
      messages.error(
          request,
          f"Assessment {assessment.number} cannot be deleted because it is {assessment.get_assessment_status_display()}."
      )
      return redirect("assets:asset_criticality_assessment_detail", pk=assessment.pk)
  ```

- [ ] **I3** — `apps/assets/models/AssetClassification/AssetSpecificationTemplates.py:27`: `DATA_TYPE_CSS["select"] = "badge-purple"` references a nonexistent CSS class (Lesson L33; theme.css only defines `badge-green/red/amber/info/muted/slate`).
  *Fix:* Change `"select": "badge-purple"` to `"select": "badge-info"`.

- [ ] **I4** — `templates/assets/asset_classification/` (5 templates): Non-existent `text-green` theme class used in:
  - `asset_category/detail.html:269`
  - `asset_criticality_assessment/list.html:165`
  - `asset_model/detail.html:207`
  - `asset_specification_template/detail.html:158`
  - `asset_specification_template/list.html:155`
  *Fix:* Replace `text-green` with `text-ok` (the valid theme.css utility class for success green text).

- [ ] **I5** — `apps/assets/views/AssetClassification/AssetCriticalityAssessments.py:19-21`: Chained N+1 query on `asmt.asset.location` in `asset_criticality_assessment_list`. In `list.html:129`, each row accesses `asmt.asset.location.name`.
  *Fix:* Add `"asset__location"` to `select_related`:
  ```python
  qs = AssetCriticalityAssessment.objects.filter(tenant=request.tenant).select_related(
      "asset__location", "assessor", "approved_by"
  )
  ```

- [ ] **I6** — `templates/assets/asset_classification/`: Delete and approve actions in list and detail templates lack `{% if request.user.is_superuser or request.user.is_tenant_admin %}` access control checks (Lesson L27), offering privileged actions to non-admin users.
  *Fix:* Wrap privileged action forms/buttons in `asset_category/detail.html:28`, `asset_category/list.html:165`, `asset_model/detail.html:25`, `asset_model/list.html:150`, `asset_criticality_assessment/detail.html:27, 37`, `asset_criticality_assessment/list.html:163, 170`, `asset_specification_template/detail.html:27`, `asset_specification_template/list.html:167` with `{% if request.user.is_superuser or request.user.is_tenant_admin %}`.

- [ ] **I7** — `templates/assets/asset_classification/asset_specification_template/detail.html:101, 107`: Numerical `0` evaluates as falsy in `{{ template.min_numeric_value|default:"No limit" }}` and `max_numeric_value`, rendering "No limit" instead of "0".
  *Fix:* Change `|default:"No limit"` to `|default_if_none:"No limit"`.

---

### Minor

- [ ] **M1** — `apps/assets/views/AssetClassification/AssetCriticalityAssessments.py:166`: `asset_criticality_assessment_approve` does not check if an assessment is already `superseded`.
  *Fix:* Change check to `if assessment.assessment_status in ("approved", "superseded"): messages.warning(request, f"Assessment {assessment.number} cannot be approved because it is {assessment.get_assessment_status_display()}."); return redirect("assets:asset_criticality_assessment_detail", pk=assessment.pk)`.

- [ ] **M2** — `apps/assets/views/AssetClassification/AssetCriticalityAssessments.py:194-195`: In `asset_criticality_assessment_approve`, use tenant-scoped update for defense-in-depth:
  *Fix:* Use `Asset.objects.filter(tenant=request.tenant, pk=assessment.asset_id).update(criticality=operational_criticality)`.

- [ ] **M3** — `apps/assets/forms/AssetClassification/AssetCriticalityAssessments.py:126`: Unhandled `ValueError` in `AssetCriticalityAssessmentForm.clean` when executing `int(val)` on non-numeric input.
  *Fix:* Wrap in `try/except (ValueError, TypeError): self.add_error(fld, "Consequence score must be an integer between 1 and 5.")`.

- [ ] **M4** — `apps/assets/models/AssetClassification/AssetSpecificationTemplates.py:88`: Unchecked regex compilation in `clean()`.
  *Fix:* Add `if self.validation_regex: try: re.compile(self.validation_regex) except re.error as e: raise ValidationError({"validation_regex": f"Invalid regular expression pattern: {e}"})`.

- [ ] **M5** — `apps/assets/models/AssetClassification/AssetModels.py:91`: `AssetModel.estimated_replacement_cost` lacks non-negative validator at the model layer.
  *Fix:* Add `validators=[MinValueValidator(Decimal("0.00"))]`.

- [ ] **M6** — `apps/assets/models/AssetClassification/AssetCategories.py:144-153`: Add model-level tenant isolation check in `AssetCategory.clean()` hierarchy traversal loop.
  *Fix:* Add `if curr.tenant_id != self.tenant_id: raise ValidationError({"parent": "Parent category belongs to another workspace."})`.

- [ ] **M7** — `apps/assets/views/AssetClassification/`: All 4 list views (`AssetCategories.py:64`, `AssetModels.py:63`, `AssetCriticalityAssessments.py:68`, `AssetSpecificationTemplates.py:61`) pass only `"q": q` instead of the pinned `"search_query"`.
  *Fix:* Pass both `"q": q, "search_query": q` in context dictionaries.

- [ ] **M8** — `apps/assets/views/AssetClassification/AssetCriticalityAssessments.py:42-44`: Filter parameter `asset_id` parsed in `asset_criticality_assessment_list`, but omitted from context and pagination links.
  *Fix:* Pass `"selected_asset": asset_id` in context and preserve in pagination links.

- [ ] **M9** — `apps/assets/views/AssetClassification/AssetCategories.py:78`: Enhance `select_related` in `asset_category_detail` to `select_related=["parent__parent"]` for deep taxonomies.

- [ ] **M10** — `templates/assets/asset_classification/asset_category/detail.html:93`: Simplify redundant text `{{ category.default_useful_life_months }} Months ({{ category.default_useful_life_months|floatformat:0 }} mos)` to `{{ category.default_useful_life_months }} Months`.

- [ ] **M11** — `templates/assets/asset_classification/asset_category/detail.html:223`: Replace `{{ mod.manufacturer.name|default:mod.manufacturer_name_fallback|default:"—" }}` with `{{ mod.display_manufacturer }}`.

- [ ] **M12** — `templates/assets/asset_classification/asset_category/list.html:193` & sibling list templates: Add `p-4 border-t border-slate-100` to `.card-footer` pagination containers.

- [ ] **M13** — All 12 templates: Replace `mr-1` with `me-1` on button icon spacing for RTL compatibility.

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
