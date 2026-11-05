# Code Review Findings: Sub-module 10.7 Data Catalog, Lineage & Governance

**Commit Range:** `7d343a2af8e7ae61ab20168cfdec164cec1e4ed0...HEAD`

---

## 1. Code Reviewer Pass

### Verdict
Commit after fixing Important findings. The sub-module has excellent multi-tenant scoping and 4-layer backend package alignment, but requires fixes for auto-slug validation errors, POST-trusted attestation fields, rating sync/atomic transactions, status transition authorization, and missing detail delete/list filter controls.

### Findings
- **[Important]** `apps/bi/forms/DataCatalog/CatalogAssets.py:68` & `apps/bi/forms/DataCatalog/DataGovernancePolicies.py:47`: The `code` field is required by default on `CatalogAssetForm` and `DataGovernancePolicyForm` because `code` has `blank=False` on the models. When users leave `code` blank expecting it to auto-slugify from `name`, Django's field validation fails with `"This field is required."` before `clean()` can run. Fix: In `__init__`, set `self.fields["code"].required = False` on both forms.
- **[Important]** `apps/bi/forms/DataCatalog/CatalogTrustEndorsements.py:38` & `apps/bi/views/DataCatalog/CatalogTrustEndorsements.py:94`: `attested_by` is exposed as an editable dropdown in `CatalogTrustEndorsementForm` and trusted directly from POST in `catalog_trust_endorsement_create`, allowing users to submit endorsements or ratings impersonating other stewards. Fix: Exclude `attested_by` from `CatalogTrustEndorsementForm.Meta.fields`, and in `catalog_trust_endorsement_create`, set `endorsement.attested_by = request.user`.
- **[Important]** `apps/bi/views/DataCatalog/CatalogTrustEndorsements.py:93-110, 132-155, 158-172`: In `catalog_trust_endorsement_create`, creating the endorsement and updating `asset.average_rating` is not wrapped in `transaction.atomic()`. Furthermore, editing or deleting an endorsement (`catalog_trust_endorsement_edit`, `catalog_trust_endorsement_delete`) does not recalculate `asset.average_rating`, leading to stale and corrupted average ratings. Fix: Extract an atomic helper `_recalculate_asset_rating(asset)` and invoke it on endorsement create, edit, and delete.
- **[Important]** `apps/bi/views/DataCatalog/CatalogAssets.py:211-256`: `catalog_asset_certify` and `catalog_asset_deprecate` execute sensitive governance state changes (`certification_status` and `deprecation_replacement`) but only verify `@login_required` without checking whether `request.user` is the asset's data steward or a tenant administrator. Fix: Add an authorization check verifying `request.user == asset.data_steward or getattr(request.user, "is_tenant_admin", False) or request.user.is_superuser`, returning a 403 or error message if unauthorized.
- **[Important]** `templates/bi/data_catalog/catalog_asset/detail.html:36-54`, `templates/bi/data_catalog/catalog_lineage_edge/detail.html:30-39`, `templates/bi/data_catalog/data_governance_policy/detail.html:29-38`, `templates/bi/data_catalog/catalog_trust_endorsement/detail.html:39-48`: None of the four detail templates include the standard POST-only Delete form with `{% csrf_token %}` and confirm dialog in the page actions/sidebar, violating CRUD completeness contract. Fix: Add POST-only Delete button forms pointing to `bi:catalog_asset_delete`, `bi:catalog_lineage_edge_delete`, `bi:data_governance_policy_delete`, and `bi:catalog_trust_endorsement_delete`.
- **[Important]** `templates/bi/data_catalog/catalog_asset/list.html:85-137` & `templates/bi/data_catalog/data_governance_policy/list.html:81-115`: Filter dropdown omissions in list templates: `catalog_asset/list.html` omits the `certification_status` dropdown even though the view parses `status` and passes `certification_status_choices`; `data_governance_policy/list.html` omits the `enforcement` dropdown even though the view parses `enforcement` and passes `enforcement_choices`. Fix: Add the missing `<select>` filters to both template filter bars.
- **[Minor]** `apps/bi/views/DataCatalog/Overview.py:72-81, 97` & `templates/bi/data_catalog/catalog_overview.html:275-294`: `catalog_overview` computes `sensitivity_distribution` and passes it into context, but `templates/bi/data_catalog/catalog_overview.html` only renders `domain_distribution` and ignores `sensitivity_distribution`. Fix: Add a sensitivity distribution visual breakdown to `catalog_overview.html` or remove the unused calculation.
- **[Minor]** `templates/bi/data_catalog/catalog_lineage_edge/list.html:237-252` & `templates/bi/data_catalog/catalog_trust_endorsement/list.html:214-230`: Both list views support filtering by `?asset=...`, but pagination links in their templates omit `&asset={{ request.GET.asset }}` when navigating between pages. Fix: Add `{% if request.GET.asset %}&asset={{ request.GET.asset }}{% endif %}` to pagination links.

---

## 2. Explorer (Architecture & Contract) Pass

### Verdict
Solid contract consistency across 23 URLs, forms, models, and admin. Identified two core spine field attribute mismatches (`overall_health_score` vs `overall_quality_score` and `step_order` vs `sequence`), corroborated filter dropdown and detail delete form omissions, and noted raw item count usage as percentage width in overview.

### Findings
- **[Important]** `templates/bi/data_catalog/catalog_asset/detail.html:326`: The detail template attempts to render `{{ asset.quality_scorecard.overall_health_score }}%` in the sidebar health scorecard badge. In `apps/bi/models/DataQuality/DataQualityScorecards.py:79`, the scorecard metric field is named `overall_quality_score`. Because the attribute does not exist on the model, Django's template engine silently renders empty text `(Overall Health: %)`. Fix: Update to `{{ asset.quality_scorecard.overall_quality_score }}%`.
- **[Important]** `templates/bi/data_catalog/catalog_lineage_edge/detail.html:191`: The lineage edge detail template references `{{ edge.transformation_step.name }} (Step #{{ edge.transformation_step.step_order }})`. In `apps/bi/models/EtlPipelines/TransformationSteps.py:37`, the field is named `sequence` (not `step_order`). Step order renders blank. Fix: Replace with `{{ edge.transformation_step.sequence }}`.
- **[Important]** `templates/bi/data_catalog/catalog_asset/list.html:85-137`: Form control missing for certification status filter. View parses `status` and passes `certification_status_choices`, but template has no `<select name="status">`. Fix: Add `<select name="status">` dropdown.
- **[Important]** `templates/bi/data_catalog/data_governance_policy/list.html:81-115`: Form control missing for enforcement filter. View parses `enforcement` and passes `enforcement_choices`, but template has no `<select name="enforcement">`. Fix: Add `<select name="enforcement">` dropdown.
- **[Important]** `templates/bi/data_catalog/catalog_asset/detail.html:36-54`, `templates/bi/data_catalog/catalog_lineage_edge/detail.html:30-39`, `templates/bi/data_catalog/data_governance_policy/detail.html:29-38`, `templates/bi/data_catalog/catalog_trust_endorsement/detail.html:39-48`: Missing POST delete button forms in detail views. Fix: Add standard POST delete form with confirmation dialog to all four detail templates.
- **[Minor]** `apps/bi/views/DataCatalog/Overview.py:72-81, 97` & `templates/bi/data_catalog/catalog_overview.html:275-294`: View calculates `sensitivity_distribution` and injects it into context, but `catalog_overview.html` only renders `domain_distribution`. Fix: Add visual card for sensitivity distribution in template or remove calculation.
- **[Minor]** `templates/bi/data_catalog/catalog_lineage_edge/list.html:237-252` & `templates/bi/data_catalog/catalog_trust_endorsement/list.html:214-230`: Pagination links drop `&asset={{ request.GET.asset }}`. Fix: Preserve query parameter in pagination links.
- **[Minor]** `templates/bi/data_catalog/catalog_overview.html:287`: In "Assets by Domain", the progress bar style uses raw item count `{{ d.count|floatformat:0 }}%` as percentage width. Fix: Compute percentage `d.pct` in Python in `Overview.py` and render `style="width: {{ d.pct }}%;"`.

---

## 3. Frontend Reviewer Pass

### Verdict
Exemplary structure and design-system fidelity across all 13 templates. Zero comment leaks, zero non-existent theme.css classes, zero unsafe None lookups, and zero NoReverseMatch risks. Identified missing detail POST delete buttons, two missing list filter selects, and pagination query preservation for asset filters.

### Findings
- **[Important]** `templates/bi/data_catalog/catalog_asset/detail.html:36`, `templates/bi/data_catalog/catalog_lineage_edge/detail.html:30`, `templates/bi/data_catalog/catalog_trust_endorsement/detail.html:39`, `templates/bi/data_catalog/data_governance_policy/detail.html:29`: Missing POST delete button with confirmation dialog on all 4 detail pages. Fix: Add standard POST delete form with confirmation dialog to `.page-actions`.
- **[Important]** `templates/bi/data_catalog/catalog_asset/list.html:85-137`: Missing `<select name="status">` in list filter form despite view passing `certification_status_choices` and handling `status` GET filter. Fix: Add certification status `<select>` dropdown.
- **[Important]** `templates/bi/data_catalog/data_governance_policy/list.html:81-115`: Missing `<select name="enforcement">` in list filter form despite view passing `enforcement_choices` and handling `enforcement` GET filter. Fix: Add enforcement level `<select>` dropdown.
- **[Minor]** `templates/bi/data_catalog/catalog_lineage_edge/list.html:239, 247` & `templates/bi/data_catalog/catalog_trust_endorsement/list.html:217, 225`: Pagination links omit `{% if request.GET.asset %}&asset={{ request.GET.asset }}{% endif %}` parameter preservation. Fix: Append asset query parameter to previous/next pagination links.

---
