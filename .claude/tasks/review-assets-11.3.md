# Review Findings — Module 11.3: Asset Classification & Categorization

**Review Target Range:** `2806da08558e720535beb100b7bc06390d117b6f...10550949dbf972e187d73124cecc3babf165b58b`
**Date:** 2026-11-09

---

## 1. Code Reviewer Pass

### Verdict
Commit after fixing Important findings.

### Critical
None.

### Important
1. `apps/assets/views/AssetClassification/AssetCriticalityAssessments.py:126` — View lacks status guard on `asset_criticality_assessment_edit`, allowing direct GET/POST requests to modify consequence scoring on approved or superseded assessments. Fix: Guard view with `if assessment.assessment_status in ("approved", "superseded"): messages.error(request, f"Assessment {assessment.number} is {assessment.get_assessment_status_display()} and cannot be edited."); return redirect("assets:asset_criticality_assessment_detail", pk=assessment.pk)`.
2. `apps/assets/views/AssetClassification/AssetCriticalityAssessments.py:154` — View lacks status guard on `asset_criticality_assessment_delete`, permitting deletion of active approved or superseded audit records. Fix: Guard view with `if assessment.assessment_status in ("approved", "superseded"): messages.error(request, f"Assessment {assessment.number} cannot be deleted because it is {assessment.get_assessment_status_display()}."); return redirect("assets:asset_criticality_assessment_detail", pk=assessment.pk)`.
3. `apps/assets/models/AssetClassification/AssetSpecificationTemplates.py:27` — Choice mapping `"select": "badge-purple"` references a nonexistent CSS class because `static/css/theme.css` only declares `badge-green/red/amber/info/muted/slate`. Fix: Change `"select": "badge-purple"` to `"select": "badge-info"`.
4. `templates/assets/asset_classification/asset_specification_template/detail.html:101` — `{{ template.min_numeric_value|default:"No limit" }}` incorrectly evaluates numerical `0` as falsy and outputs "No limit" instead of "0". Fix: Change `|default:"No limit"` to `|default_if_none:"No limit"`.

### Minor
1. `apps/assets/views/AssetClassification/AssetCriticalityAssessments.py:166` — `asset_criticality_assessment_approve` does not check if an assessment is already superseded, allowing re-approval of obsolete audits. Fix: Change status check to `if assessment.assessment_status in ("approved", "superseded"): messages.warning(request, f"Assessment {assessment.number} cannot be approved because it is {assessment.get_assessment_status_display()}."); return redirect("assets:asset_criticality_assessment_detail", pk=assessment.pk)`.
2. `apps/assets/views/AssetClassification/AssetCategories.py:64` — All 4 list views pass `"q": q` whereas the pre-build contract pinned `"search_query"` as the context key. Fix: Pass both `"q": q, "search_query": q` in the context dictionaries of `asset_category_list`, `asset_model_list`, `asset_criticality_assessment_list`, and `asset_specification_template_list`.
3. `apps/assets/views/AssetClassification/AssetCriticalityAssessments.py:43` — Filter parameter `asset_id` is processed in `asset_criticality_assessment_list`, but omitted from context and pagination links. Fix: Add `"selected_asset": asset_id` to context and preserve `{% if selected_asset %}&asset={{ selected_asset }}{% endif %}` in pagination URLs.
4. `apps/assets/forms/AssetClassification/AssetCriticalityAssessments.py:126` — `int(val)` in `AssetCriticalityAssessmentForm.clean` raises an unhandled `ValueError` if a non-numeric string is submitted. Fix: Wrap `int(val)` with `try/except (ValueError, TypeError): self.add_error(fld, "Consequence score must be an integer between 1 and 5.")`.
5. `apps/assets/models/AssetClassification/AssetSpecificationTemplates.py:88` — `AssetSpecificationTemplate.clean` does not validate `validation_regex`, risking `re.error` 500 exceptions if an invalid regex string is stored. Fix: Add `if self.validation_regex: try: re.compile(self.validation_regex) except re.error as e: raise ValidationError({"validation_regex": f"Invalid regex pattern: {e}"})` in `clean()`.
6. `apps/assets/models/AssetClassification/AssetModels.py:91` — `AssetModel.estimated_replacement_cost` lacks a non-negative validator at the model layer. Fix: Add `validators=[MinValueValidator(Decimal("0.00"))]` to `estimated_replacement_cost`.
7. `templates/assets/asset_classification/asset_category/detail.html:93` — Useful life field displays redundant text `{{ category.default_useful_life_months }} Months ({{ category.default_useful_life_months|floatformat:0 }} mos)`. Fix: Simplify to `{{ category.default_useful_life_months }} Months`.
8. `templates/assets/asset_classification/asset_category/detail.html:223` — Template manually resolves manufacturer fallback instead of reusing `mod.display_manufacturer`. Fix: Replace `{{ mod.manufacturer.name|default:mod.manufacturer_name_fallback|default:"—" }}` with `{{ mod.display_manufacturer }}`.

### Done well
- Thorough multi-tenant protection with `TenantNumbered`, `assets_object`, `reject_foreign`, and tenant-scoped querysets across all views, models, and forms.
- Full exclusion of view-owned workflow fields (`composite_score`, `abc_rating`, `assessment_status`, `approved_by`, `approved_at`) in `AssetCriticalityAssessmentForm` preventing POST spoofing.
- Robust taxonomy hierarchy design with recursive loop prevention in `AssetCategory.clean()`.
- Safe atomic synchronization in `asset_criticality_assessment_approve`, superseding older approved assessments and updating `scm.Asset.criticality` inside a `transaction.atomic()` block.
- Standardized package architecture across `models/`, `forms/`, `views/`, `urls/`, and `templates/`, with all URL names and parameters matching template links without reverse errors.

---

## 2. Explorer Reviewer Pass

### Verdict
Commit after fixing Important findings in Phase 5.

### Critical
None.

### Important
1. `apps/assets/views/AssetClassification/AssetCriticalityAssessments.py:126` — Missing status guard on `asset_criticality_assessment_edit`: Allows direct editing of assessments that are already `approved` or `superseded`, violating ERP audit and compliance freeze rules. Fix: Guard view with `if assessment.assessment_status in ("approved", "superseded"): messages.error(request, f"Assessment {assessment.number} is {assessment.get_assessment_status_display()} and cannot be edited."); return redirect("assets:asset_criticality_assessment_detail", pk=assessment.pk)`.
2. `apps/assets/views/AssetClassification/AssetCriticalityAssessments.py:154` — Missing status guard on `asset_criticality_assessment_delete`: Permits deletion of `approved` or `superseded` risk assessment records. Fix: Guard view with `if assessment.assessment_status in ("approved", "superseded"): messages.error(request, f"Assessment {assessment.number} cannot be deleted because it is {assessment.get_assessment_status_display()}."); return redirect("assets:asset_criticality_assessment_detail", pk=assessment.pk)`.
3. `apps/assets/models/AssetClassification/AssetSpecificationTemplates.py:27` — `DATA_TYPE_CSS["select"] = "badge-purple"` references a nonexistent CSS class. In `static/css/theme.css` and rule L33, badges only support `badge-green/red/amber/info/muted/slate`. Fix: Change `"select": "badge-purple"` to `"select": "badge-info"`.
4. `templates/assets/asset_classification/asset_specification_template/detail.html:101, 107` — `{{ template.min_numeric_value|default:"No limit" }}` and `{{ template.max_numeric_value|default:"No limit" }}` evaluate numerical `0` as falsy and display "No limit" instead of "0". Fix: Change `|default:"No limit"` to `|default_if_none:"No limit"`.

### Minor
1. `apps/assets/views/AssetClassification/AssetCategories.py:64`, `AssetModels.py:63`, `AssetCriticalityAssessments.py:68`, `AssetSpecificationTemplates.py:61` — View Context Key Contract Drift: Contract Section 4 pinned `search_query: request.GET.get('q', '')` for all 4 list views. The views currently pass only `"q": q`. Fix: Provide both `"search_query": q, "q": q` in context dictionaries.
2. `apps/assets/views/AssetClassification/AssetCriticalityAssessments.py:42-44` — Incomplete query filter propagation: Parameter `asset_id` is parsed and filtered on the queryset in `asset_criticality_assessment_list`, but `"selected_asset"` is omitted from the context dictionary and from pagination link query strings (`&asset={{ selected_asset }}`). Fix: Pass `"selected_asset": asset_id` in context and preserve in pagination links.
3. `apps/assets/views/AssetClassification/AssetCriticalityAssessments.py:166` — Re-approval of superseded assessments: `asset_criticality_assessment_approve` checks `if assessment.assessment_status == "approved"`, but does not guard against approving an assessment that was previously `superseded`. Fix: Guard with `if assessment.assessment_status in ("approved", "superseded"): messages.warning(request, f"Assessment {assessment.number} cannot be approved because it is {assessment.get_assessment_status_display()}."); return redirect(...)`.
4. `apps/assets/forms/AssetClassification/AssetCriticalityAssessments.py:126` — Unhandled `ValueError` in form clean: `int(val)` raises an unhandled exception if malformed data is submitted. Fix: Wrap in `try/except (ValueError, TypeError): self.add_error(fld, "Consequence score must be an integer between 1 and 5.")`.
5. `apps/assets/models/AssetClassification/AssetSpecificationTemplates.py:88` — Unchecked regex compilation in `clean()`: If an invalid regex pattern is saved in `validation_regex`, subsequent evaluation raises `re.error`. Fix: Add `if self.validation_regex: try: re.compile(self.validation_regex) except re.error as e: raise ValidationError({"validation_regex": f"Invalid regex pattern: {e}"})`.
6. `apps/assets/models/AssetClassification/AssetModels.py:91` — Model-level validation on replacement cost: `estimated_replacement_cost` lacks a `MinValueValidator(Decimal("0.00"))` on the model field itself.
7. `templates/assets/asset_classification/asset_category/detail.html:93` — Redundant text formatting: displays `{{ category.default_useful_life_months }} Months ({{ category.default_useful_life_months|floatformat:0 }} mos)`. Fix: Simplify to `{{ category.default_useful_life_months }} Months`.
8. `templates/assets/asset_classification/asset_category/detail.html:223` — Template reimplements manufacturer fallback instead of property helper: Uses `{{ mod.manufacturer.name|default:mod.manufacturer_name_fallback|default:"—" }}` instead of `{{ mod.display_manufacturer }}`.

### Done well
- Architecture & Package Structure: Adheres 100% to CLAUDE.md backend package structure with one folder per sub-module (`AssetClassification/`) across `models/`, `forms/`, `views/`, `urls/`, and templates. Full surgical re-exports at both sub-module and app levels.
- Core Spine Integration: Seamless integration with `scm.Asset` (for equipment risk assessments and operational criticality synchronization), `core.Party` (for OEM vendors and reliability inspectors), and `accounting.FixedAsset` depreciation defaults.
- Contract Compliance: All 4 models match table names, number prefixes (`ACAT`, `AMOD`, `ACRT`, `ASPC`), fields, choices, indexes, and constraints. All 19 URL routes and all 10 `LIVE_LINKS["11.3"]` entries match the spec.
- Multi-Tenancy & Security: Complete tenant isolation across all models via `TenantNumbered`, views using `assets_object`, forms using `reject_foreign`, and write views writing audit logs.
- Seeder & Admin: Robust seeder in `seed_assets.py` with multi-tenant coverage, realistic demo taxonomy, and idempotency guards. Comprehensive Django admin registrations with filters and search.

---

## 3. Frontend Reviewer Pass

### Verdict
Pass with minor findings (0 Critical, 2 Important, 3 Minor).

### Critical
None.

### Important
1. `templates/assets/asset_classification/asset_category/detail.html:269`, `asset_criticality_assessment/list.html:165`, `asset_model/detail.html:207`, `asset_specification_template/detail.html:158`, `asset_specification_template/list.html:155` — Non-existent `text-green` theme class used across 5 templates (Lesson L13 & L33). In `theme.css`, success text is `.text-ok`. Fix: Replace `text-green` with `text-ok`.
2. `apps/assets/models/AssetClassification/AssetSpecificationTemplates.py:27` — Non-existent `badge-purple` returned by `DATA_TYPE_CSS["select"]`. Fix: Change `"select": "badge-purple"` to `"select": "badge-info"`.

### Minor
1. `templates/assets/asset_classification/asset_category/list.html:193`, `asset_model/list.html:178`, `asset_criticality_assessment/list.html:198`, `asset_specification_template/list.html:195` — Unstyled `.card-footer` container for pagination in list views lacks top border and padding. Fix: Add standard utility classes `p-4 border-t border-slate-100`.
2. `templates/assets/asset_classification/asset_category/detail.html:223` — Prefer model property `display_manufacturer` over chained filter defaults `{{ mod.manufacturer.name|default:mod.manufacturer_name_fallback|default:"—" }}`. Fix: Replace with `{{ mod.display_manufacturer }}`.
3. All 12 templates — RTL icon spacing: use `me-1` instead of `mr-1` for automated RTL mirror support.

### Done well
- Zero comment leaks: strict adherence to Lesson L2; zero multiline `{# ... #}` comment leaks.
- Robust pagination guards (L9): all 4 list templates correctly guard `has_previous` and `has_next` before accessing `previous_page_number` / `next_page_number`.
- Strict PK filter comparisons using `|stringformat:"d"`.
- Accessible & well-structured forms and table delete actions.
- Risk assessment consequence progress bar breakdown leveraging theme.css `.progress` and `.progress-bar`.

---

## 4. Performance Reviewer Pass

### Verdict
Commit after fixing Important findings in Phase 5 (0 Critical, 1 Important, 2 Minor).

### Critical
None.

### Important
1. `apps/assets/views/AssetClassification/AssetCriticalityAssessments.py:19-21` — Chained N+1 query on `asmt.asset.location` in `asset_criticality_assessment_list`. In `templates/.../list.html:129`, each row accesses `asmt.asset.location.name`. Fix: Add `"asset__location"` to `select_related` in `AssetCriticalityAssessments.py`:
   ```python
   qs = AssetCriticalityAssessment.objects.filter(tenant=request.tenant).select_related(
       "asset__location", "assessor", "approved_by"
   )
   ```

### Minor
1. `apps/assets/views/AssetClassification/AssetCategories.py:78` — Shallow `select_related` on hierarchy breadcrumb in `asset_category_detail`. Fix: Enhance `select_related` in `asset_category_detail` to `select_related=["parent__parent"]` to cover standard 3-tier taxonomies without additional queries.
2. `apps/assets/views/AssetClassification/AssetModels.py:81-85` — Cross-module unindexed filter on `scm.Asset.model_number`. (SCM app maintenance recommendation).

### Done well
- Single-query KPI aggregates via `.aggregate(Count("id", filter=Q(...)))` across all 4 list views.
- Robust tenant-composite indexes on all 4 models covering all search and filter combinations.
- Strict pre-paginator filtering and standard page size of 15.
- Zero N+1 queries in Django Admin thanks to explicit `list_select_related`.



