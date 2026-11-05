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

## 4. Performance Reviewer Pass

### Verdict
Good baseline ORM hygiene with pre-filtering, aggregated counts, and consistent Paginator usage. Identified redundant `refresh_from_db` on asset detail, chained FK traversal in `__str__` without cached check (Lesson L18), heavy JSON column loading in form dropdowns, and missing composite ordering indexes matching the app-wide pattern.

### Findings
- **[Important]** `apps/bi/views/DataCatalog/CatalogAssets.py:112-113`: Redundant `refresh_from_db` query on every `catalog_asset_detail` load immediately after atomic `update()`. Fix: Update in-memory attribute directly `asset.view_count = (asset.view_count or 0) + 1` without executing a redundant SELECT.
- **[Important]** `apps/bi/models/DataCatalog/CatalogLineageEdges.py:103-110` & `apps/bi/models/DataCatalog/CatalogTrustEndorsements.py:87-88`: Chained FK traversal in `__str__` without checking `self._state.fields_cache` (Lesson L18). Triggers un-prefetched queries during edit/delete audit logging. Fix: Make `__str__` defensive using `fields_cache` check with fallback ID, and pass `select_related` to `bi_object` in edit/delete views.
- **[Minor]** `apps/bi/forms/DataCatalog/CatalogAssets.py:84, 157`: Heavy JSON columns (`schema_columns_json`, `search_tags_json`) loaded in `deprecation_replacement` dropdown querysets. Fix: Apply `.only("id", "number", "name")` to the replacement queryset.
- **[Minor]** `apps/bi/models/DataCatalog/{CatalogAssets,CatalogLineageEdges,CatalogTrustEndorsements,DataGovernancePolicies}.py`: Missing composite ordering indexes `(tenant, -created_at)` and `(tenant, -attested_at)`. Fix: Add composite ordering indexes matching sibling BI models.

---

## 5. QA Smoke Tester Pass

### Verdict
Passed 100% of route GETs (23/23), POST create/edit redirections (8/8), cross-tenant IDOR protection (18/18 -> 404), zero comment leaks, and clean pagination/junk-param handling. Uncovered two new runtime defects (AuditLog `object_id` recorded as NULL due to `obj.delete()` called before `write_audit_log`, and `average_rating_overall` missing from endorsement list context) while corroborating all previous findings.

### Findings
- **[Important]** `apps/bi/views/DataCatalog/CatalogAssets.py:199-206`, `apps/bi/views/DataCatalog/CatalogLineageEdges.py:162-169`, `apps/bi/views/DataCatalog/DataGovernancePolicies.py:144-151`, `apps/bi/views/DataCatalog/CatalogTrustEndorsements.py:163-170`: In all four delete views, `obj.delete()` is executed BEFORE `write_audit_log`. Because `delete()` clears `obj.pk` to `None`, `AuditLog.object_id` is permanently written as `NULL`. Fix: Call `write_audit_log(...)` BEFORE calling `obj.delete()`.
- **[Important]** `apps/bi/views/DataCatalog/CatalogTrustEndorsements.py:57-66` & `templates/bi/data_catalog/catalog_trust_endorsement/list.html:63-71`: Contract drift on context key. The view omits `average_rating_overall` (pinned in Contract Section 4.5), and `list.html` hardcodes `5-Star System`. Fix: Calculate `average_rating_overall` in view, pass to context, and render in `list.html`.
- **[Important]** `apps/bi/forms/DataCatalog/CatalogAssets.py:68` & `apps/bi/forms/DataCatalog/DataGovernancePolicies.py:47`: Blank `code` field blocked by Django form validation before `clean()` auto-slug. Fix: Set `self.fields["code"].required = False` on both forms.
- **[Important]** `apps/bi/forms/DataCatalog/CatalogTrustEndorsements.py:43` & `apps/bi/views/DataCatalog/CatalogTrustEndorsements.py:94-98`: `attested_by` trusted from POST in `CatalogTrustEndorsementForm`. Fix: Exclude `attested_by` from form and set `endorsement.attested_by = request.user` in view.
- **[Important]** `apps/bi/views/DataCatalog/CatalogTrustEndorsements.py:132-155, 158-172`: Endorsement edit and delete do not recalculate `asset.average_rating`. Fix: Extract atomic `_recalculate_asset_rating(asset)` and call on create, edit, delete.
- **[Important]** `apps/bi/views/DataCatalog/CatalogAssets.py:211-256`: Non-stewards / non-admins can alter certification and deprecation status. Fix: Add authorization check restricting to data steward, tenant admin, or superuser.
- **[Important]** `templates/bi/data_catalog/catalog_asset/detail.html:326`: `overall_health_score` does not exist on `DataQualityScorecard` (field is `overall_quality_score`). Fix: Update template reference.
- **[Important]** `templates/bi/data_catalog/catalog_lineage_edge/detail.html:191`: `step_order` does not exist on `TransformationStep` (field is `sequence`). Fix: Update template reference.
- **[Important]** `templates/bi/data_catalog/{catalog_asset,catalog_lineage_edge,data_governance_policy,catalog_trust_endorsement}/detail.html`: Missing POST delete form buttons in `page-actions`. Fix: Add POST delete form buttons with confirm dialogs.
- **[Important]** `templates/bi/data_catalog/catalog_asset/list.html` & `templates/bi/data_catalog/data_governance_policy/list.html`: Missing `<select name="status">` and `<select name="enforcement">` in filter forms. Fix: Add missing select controls.
- **[Minor]** `apps/bi/views/DataCatalog/Overview.py:72-81` & `templates/bi/data_catalog/catalog_overview.html:287`: Progress bar style uses raw item count as percentage width. Fix: Compute percentage `d.pct` in Python in `Overview.py`.

---
