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
