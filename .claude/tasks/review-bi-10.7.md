# Consolidated Review Findings: Sub-module 10.7 Data Catalog, Lineage & Governance

**Commit Range:** `7d343a2af8e7ae61ab20168cfdec164cec1e4ed0...HEAD`  
**Review Passes Completed (6/6):**
1. Code Reviewer
2. Explorer (Architecture & Contract)
3. Frontend Reviewer
4. Performance Reviewer
5. QA Smoke Tester
6. Security Reviewer

---

## Findings Checklist for Phase 5 (`code-fixer`)

### Critical
- [x] **C1**: `apps/bi/forms/DataCatalog/CatalogTrustEndorsements.py:43` & `apps/bi/views/DataCatalog/CatalogTrustEndorsements.py:94-98`: Attestation Identity Spoofing / Mass Assignment in `CatalogTrustEndorsementForm` & View. Exclude `attested_by` from form `Meta.fields`, and in `catalog_trust_endorsement_create`, set `endorsement.attested_by = request.user`. Fixed: excluded from form Meta.fields, bound request.user in view, rendered readonly in template.
- [x] **C2**: `apps/bi/views/DataCatalog/CatalogAssets.py:211-233, 235-256` & `templates/bi/data_catalog/catalog_asset/detail.html:351-397`: Missing Authorization Checks on Sensitive Certification and Deprecation Transitions. Restrict `catalog_asset_certify` and `catalog_asset_deprecate` to `request.user == asset.data_steward or getattr(request.user, "is_tenant_admin", False) or request.user.is_superuser`, raising `PermissionDenied`. In template, guard steward action forms with the same condition. Fixed: enforced steward/tenant-admin authorization in views and guarded action cards in template.

### Important
- [x] **I1**: `apps/bi/views/DataCatalog/CatalogAssets.py:199-206`, `apps/bi/views/DataCatalog/CatalogLineageEdges.py:162-169`, `apps/bi/views/DataCatalog/DataGovernancePolicies.py:144-151`, `apps/bi/views/DataCatalog/CatalogTrustEndorsements.py:163-170`: Audit Trail Erasure: `obj.delete()` Invoked Before `write_audit_log`. Call `write_audit_log(...)` BEFORE calling `obj.delete()` across all four delete views so `obj.pk` is not None and `AuditLog.object_id` is recorded properly. Fixed: relocated write_audit_log before delete across all four views.
- [x] **I2**: `apps/bi/forms/DataCatalog/CatalogAssets.py:68` & `apps/bi/forms/DataCatalog/DataGovernancePolicies.py:47`: Form `code` Auto-Slug Blocked by Default Required Validation. Set `self.fields["code"].required = False` in `__init__` on both forms. Fixed: set code required=False in __init__ for both forms.
- [x] **I3**: `apps/bi/views/DataCatalog/CatalogTrustEndorsements.py:93-118, 132-155, 158-172`: Rating Sync & Transaction Atomicity on Endorsement Create, Edit, Delete. Extract `_recalculate_asset_rating(asset)` and call it atomically in `create`, `edit`, and `delete`. Fixed: extracted _recalculate_asset_rating and wrapped in atomic transactions on create, edit, delete.
- [ ] **I4**: `apps/bi/views/DataCatalog/CatalogAssets.py:194`, `apps/bi/views/DataCatalog/CatalogLineageEdges.py:157`, `apps/bi/views/DataCatalog/DataGovernancePolicies.py:140`, `apps/bi/views/DataCatalog/CatalogTrustEndorsements.py:132-170`: Missing Administrative / Author Access Controls on Delete and Endorsement Edit. Decorate delete views with `@tenant_admin_required` (or author/steward check), and restrict `catalog_trust_endorsement_edit` to `endorsement.attested_by == request.user` or tenant admin.
- [ ] **I5**: `apps/bi/forms/DataCatalog/CatalogAssets.py:35, 54, 86-89` & `templates/bi/data_catalog/catalog_asset/form.html:86-89`: Mass Assignment of Workflow-Controlled `certification_status` in `CatalogAssetForm`. Exclude `certification_status` from `CatalogAssetForm.Meta.fields`.
- [ ] **I6**: `templates/bi/data_catalog/catalog_asset/detail.html:326`: Core Spine Attribute Mismatch on `DataQualityScorecard`. Update `{{ asset.quality_scorecard.overall_health_score }}%` to `{{ asset.quality_scorecard.overall_quality_score }}%`.
- [ ] **I7**: `templates/bi/data_catalog/catalog_lineage_edge/detail.html:191`: Core Spine Attribute Mismatch on `TransformationStep`. Update `{{ edge.transformation_step.step_order }}` to `{{ edge.transformation_step.sequence }}`.
- [ ] **I8**: `templates/bi/data_catalog/catalog_asset/detail.html:36`, `templates/bi/data_catalog/catalog_lineage_edge/detail.html:30`, `templates/bi/data_catalog/catalog_trust_endorsement/detail.html:39`, `templates/bi/data_catalog/data_governance_policy/detail.html:29`: Missing POST Delete Form Buttons on Detail Templates. Add standard POST delete form buttons with confirm dialogs in `.page-actions`.
- [ ] **I9**: `templates/bi/data_catalog/catalog_asset/list.html:85-137` & `templates/bi/data_catalog/data_governance_policy/list.html:81-115`: Missing Filter Form Dropdowns in List Templates. Add `<select name="status">` to asset list and `<select name="enforcement">` to policy list filter forms.
- [ ] **I10**: `apps/bi/views/DataCatalog/CatalogTrustEndorsements.py:57-66` & `templates/bi/data_catalog/catalog_trust_endorsement/list.html:63-71`: Contract Drift on Endorsement List Context Variable `average_rating_overall`. Calculate `average_rating_overall` in view, pass to context, and render in `list.html`.
- [ ] **I11**: `apps/bi/views/DataCatalog/CatalogAssets.py:112-113`: Redundant `refresh_from_db` Query on `catalog_asset_detail` Load. Drop `refresh_from_db` and update in-memory instance attribute directly (`asset.view_count = (asset.view_count or 0) + 1`).
- [ ] **I12**: `apps/bi/models/DataCatalog/CatalogLineageEdges.py:103-110` & `apps/bi/models/DataCatalog/CatalogTrustEndorsements.py:87-88`: Chained FK Traversal in `__str__` without `fields_cache` Guard (Lesson L18). Guard relations in `__str__` using `self._state.fields_cache` fallback, and pass `select_related` to `bi_object` in edit/delete views.

### Minor
- [ ] **M1**: `apps/bi/views/DataCatalog/Overview.py:72-81, 97` & `templates/bi/data_catalog/catalog_overview.html:275-294`: Unused View Context Variable `sensitivity_distribution`. Render sensitivity distribution card in `catalog_overview.html`.
- [ ] **M2**: `templates/bi/data_catalog/catalog_lineage_edge/list.html:237-252` & `templates/bi/data_catalog/catalog_trust_endorsement/list.html:214-230`: Asset Filter Parameter Dropped in Pagination Links. Append `{% if request.GET.asset %}&asset={{ request.GET.asset }}{% endif %}` to pagination links.
- [ ] **M3**: `apps/bi/views/DataCatalog/Overview.py:72-81` & `templates/bi/data_catalog/catalog_overview.html:287`: Raw Item Count Used as Percentage Width in Overview Hub. Compute percentage `d.pct` in Python in `Overview.py` and render `style="width: {{ d.pct }}%;"`.
- [ ] **M4**: `apps/bi/forms/DataCatalog/CatalogAssets.py:84, 157`: Heavy JSON Column Loading in Form Dropdown Queryset. Apply `.only("id", "number", "name")` to `replacement_qs`.
- [ ] **M5**: `apps/bi/models/DataCatalog/{CatalogAssets,CatalogLineageEdges,CatalogTrustEndorsements,DataGovernancePolicies}.py`: Composite Tenant Ordering Indexes on 10.7 Models. Add composite ordering indexes `(tenant, -created_at)` and `(tenant, -attested_at)`.
