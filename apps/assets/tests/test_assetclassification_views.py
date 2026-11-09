"""Asset Classification & Categorization (11.3) — VIEWS Integration Test Suite.

Covers all 19 views across the 4 entities:
1. AssetCategory:
   - asset_category_list (GET, context keys, filters by q/type/parent, junk params, pagination)
   - asset_category_create (GET, POST valid -> 302, POST invalid -> 200)
   - asset_category_detail (GET, context contract, cross-tenant 404)
   - asset_category_edit (GET, POST valid -> 302, POST invalid -> 200)
   - asset_category_delete (require_POST, tenant_admin_required, child/model guard, valid delete)

2. AssetModel:
   - asset_model_list (GET, context keys, filters by q/status/category, junk params)
   - asset_model_create (GET, POST valid -> 302, POST invalid -> 200)
   - asset_model_detail (GET, context contract, deployed assets, cross-tenant 404)
   - asset_model_edit (GET, POST valid -> 302, POST invalid -> 200)
   - asset_model_delete (require_POST, tenant_admin_required, deployed assets guard, valid delete)

3. AssetCriticalityAssessment:
   - asset_criticality_assessment_list (GET, context keys, filters by q/abc/status/asset, junk params)
   - asset_criticality_assessment_create (GET, POST valid -> 302 with auto score, POST invalid -> 200)
   - asset_criticality_assessment_detail (GET, context contract, dimension impact fields, cross-tenant 404)
   - asset_criticality_assessment_edit (GET, POST valid for draft, approved/superseded status guard)
   - asset_criticality_assessment_delete (require_POST, tenant_admin_required, approved/superseded status guard, draft delete)
   - asset_criticality_assessment_approve (require_POST, tenant_admin_required, status transition, scm.Asset sync, supersede prior, re-approve guard)

4. AssetSpecificationTemplate:
   - asset_specification_template_list (GET, context keys, filters by q/type/category, junk params)
   - asset_specification_template_create (GET, POST valid -> 302, POST invalid -> 200)
   - asset_specification_template_detail (GET, context contract, cross-tenant 404)
   - asset_specification_template_edit (GET, POST valid -> 302, POST invalid -> 200)
   - asset_specification_template_delete (require_POST, tenant_admin_required, valid delete)

5. Security:
   - Unauthenticated redirects for all entities
"""
from decimal import Decimal
import pytest
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from apps.assets.models import (
    AssetCategory,
    AssetCriticalityAssessment,
    AssetModel,
    AssetSpecificationTemplate,
)
from apps.core.models import AuditLog
from apps.scm.models import Asset


# ==============================================================================
# Helper Functions (strictly prefixed with _assetclassification_)
# ==============================================================================


def _assetclassification_get_flash_messages(response):
    """Extract list of flash message strings from response."""
    return [str(m) for m in get_messages(response.wsgi_request)]


def _assetclassification_category_payload(code="HVAC-AIR", name="Air Handling Units", **kwargs):
    """Generate valid base form payload for AssetCategoryForm."""
    payload = {
        "code": code,
        "name": name,
        "parent": "",
        "category_type": "facility",
        "unspsc_code": "40101701",
        "unspsc_title": "Air handlers",
        "default_depreciation_method": "straight_line",
        "default_useful_life_months": 96,
        "default_maintenance_strategy": "preventive_calendar",
        "default_criticality": "medium",
        "description": "Standard facility air handling units and ventilation systems.",
        "display_order": 20,
        "is_active": True,
    }
    payload.update(kwargs)
    return payload


def _assetclassification_model_payload(category, model_number="TRANE-CVHE-500", name="Trane CenTraVac Chiller", **kwargs):
    """Generate valid base form payload for AssetModelForm."""
    payload = {
        "model_number": model_number,
        "name": name,
        "category": category.pk if hasattr(category, "pk") else category,
        "manufacturer": "",
        "manufacturer_name_fallback": "Trane Commercial",
        "description": "Direct-drive centrifugal liquid chiller with adaptive controls.",
        "standard_warranty_months": 24,
        "warranty_coverage_type": "full_parts_labor",
        "expected_useful_life_months": 180,
        "default_meter_name": "Operating Hours",
        "default_meter_unit": "h",
        "estimated_replacement_cost": "250000.00",
        "model_status": "active",
        "technical_specifications": "Capacity: 500 Tons; Refrigerant: R-1233zd(E); Voltage: 480V 3Ph 60Hz",
        "is_active": True,
    }
    payload.update(kwargs)
    return payload


def _assetclassification_criticality_payload(asset, assessor, title="Annual Criticality Review", **kwargs):
    """Generate valid base form payload for AssetCriticalityAssessmentForm."""
    payload = {
        "title": title,
        "asset": asset.pk if hasattr(asset, "pk") else asset,
        "assessor": assessor.pk if hasattr(assessor, "pk") else assessor,
        "assessment_date": str(timezone.now().date()),
        "safety_impact": 4,
        "environmental_impact": 3,
        "operational_downtime_impact": 5,
        "financial_impact": 4,
        "regulatory_compliance_impact": 3,
        "is_single_point_of_failure": True,
        "recommended_strategy": "rcm_predictive",
        "review_cycle_months": 12,
        "next_assessment_due": str(timezone.now().date() + timezone.timedelta(days=365)),
        "findings_and_mitigation": "Primary line bottleneck asset. Vibration analysis recommended.",
    }
    payload.update(kwargs)
    return payload


def _assetclassification_spec_template_payload(**kwargs):
    """Generate valid base form payload for AssetSpecificationTemplateForm."""
    payload = {
        "attribute_key": "rated_operating_voltage",
        "display_name": "Rated Operating Voltage",
        "category": "",
        "model": "",
        "data_type": "number",
        "unit_of_measure": "V",
        "default_value": "480",
        "dropdown_options": "",
        "min_numeric_value": "380.000",
        "max_numeric_value": "480.000",
        "validation_regex": r"^[0-9]{3}$",
        "is_required": True,
        "is_filterable": True,
        "display_order": 10,
        "help_text": "Rated operating terminal voltage in volts RMS.",
    }
    payload.update(kwargs)
    return payload


# ==============================================================================
# 1. AssetCategory Views
# ==============================================================================


@pytest.mark.django_db
def test_assetclassification_views_category_list_renders_200_and_context(
    client_a, category_root_a, category_child_a
):
    """asset_category_list renders 200 with required context keys and aggregates."""
    url = reverse("assets:asset_category_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "categories" in resp.context
    assert "category_list" in resp.context
    assert "page_obj" in resp.context
    assert "paginator" in resp.context
    assert ("category_types" in resp.context or "category_type_choices" in resp.context)
    assert "parent_categories" in resp.context
    assert ("total_count" in resp.context or "status_counts" in resp.context)
    assert "q" in resp.context
    assert "search_query" in resp.context
    assert resp.context["total_count"] >= 2
    assert resp.context["root_count"] >= 1


@pytest.mark.django_db
def test_assetclassification_views_category_list_filter_search(
    client_a, category_root_a, category_child_a
):
    """asset_category_list filters by q search query."""
    url = reverse("assets:asset_category_list")

    # Match by child code
    resp_match = client_a.get(url, {"q": "HVAC-CHL"})
    assert resp_match.status_code == 200
    found_pks = [c.pk for c in resp_match.context["categories"]]
    assert category_child_a.pk in found_pks
    assert category_root_a.pk not in found_pks

    # Match by root name
    resp_root = client_a.get(url, {"q": "Plant Equipment"})
    assert resp_root.status_code == 200
    root_pks = [c.pk for c in resp_root.context["categories"]]
    assert category_root_a.pk in root_pks
    assert category_child_a.pk not in root_pks

    # No match
    resp_none = client_a.get(url, {"q": "NONEXISTENT_CATEGORY_XYZ"})
    assert resp_none.status_code == 200
    assert len(resp_none.context["categories"]) == 0


@pytest.mark.django_db
def test_assetclassification_views_category_list_filter_category_type(
    client_a, category_root_a, category_child_a
):
    """asset_category_list filters by category_type."""
    url = reverse("assets:asset_category_list")

    # Filter machinery -> category_root_a
    resp = client_a.get(url, {"type": "machinery"})
    assert resp.status_code == 200
    pks = [c.pk for c in resp.context["categories"]]
    assert category_root_a.pk in pks
    assert category_child_a.pk not in pks

    # Filter facility -> category_child_a
    resp_fac = client_a.get(url, {"type": "facility"})
    assert resp_fac.status_code == 200
    fac_pks = [c.pk for c in resp_fac.context["categories"]]
    assert category_child_a.pk in fac_pks
    assert category_root_a.pk not in fac_pks


@pytest.mark.django_db
def test_assetclassification_views_category_list_filter_parent(
    client_a, category_root_a, category_child_a
):
    """asset_category_list filters by parent category ID."""
    url = reverse("assets:asset_category_list")
    resp = client_a.get(url, {"parent": str(category_root_a.pk)})
    assert resp.status_code == 200
    pks = [c.pk for c in resp.context["categories"]]
    assert category_child_a.pk in pks
    assert category_root_a.pk not in pks


@pytest.mark.django_db
def test_assetclassification_views_category_list_junk_parameters_safe(
    client_a, category_root_a
):
    """asset_category_list handles malformed and junk query parameters gracefully."""
    url = reverse("assets:asset_category_list")
    resp = client_a.get(url, {
        "category": "not_an_int",
        "parent": "invalid_abc",
        "type": "invalid_type_slug",
        "page": "99999",
    })
    assert resp.status_code == 200
    # Safe fallback to empty or valid page without crashing 500


@pytest.mark.django_db
def test_assetclassification_views_category_detail_renders_200_and_context(
    client_a, category_root_a, category_child_a, asset_model_a, spec_template_a
):
    """asset_category_detail renders 200 with category, children, models, spec_templates."""
    url = reverse("assets:asset_category_detail", kwargs={"pk": category_root_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["category"] == category_root_a
    assert category_child_a in resp.context["children"]
    assert asset_model_a in resp.context["models"]
    assert spec_template_a in resp.context["spec_templates"]


@pytest.mark.django_db
def test_assetclassification_views_category_detail_cross_tenant_404(
    client_b, category_root_a
):
    """Tenant B client cannot view Tenant A category (IDOR isolation)."""
    url = reverse("assets:asset_category_detail", kwargs={"pk": category_root_a.pk})
    resp = client_b.get(url)
    assert resp.status_code == 404


@pytest.mark.django_db
def test_assetclassification_views_category_create_get_renders_form(client_a):
    """asset_category_create GET renders form page with is_edit=False."""
    url = reverse("assets:asset_category_create")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["category"] is None


@pytest.mark.django_db
def test_assetclassification_views_category_create_post_success(
    client_a, tenant_a, admin_user
):
    """asset_category_create POST valid data creates category with tenant=request.tenant."""
    url = reverse("assets:asset_category_create")
    payload = _assetclassification_category_payload(code="PUMP-CENT", name="Centrifugal Pumps")

    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    created = AssetCategory.objects.filter(tenant=tenant_a, code="PUMP-CENT").first()
    assert created is not None
    assert created.tenant == tenant_a
    assert created.name == "Centrifugal Pumps"
    assert resp.url == reverse("assets:asset_category_detail", kwargs={"pk": created.pk})

    # Verify audit log recorded
    assert AuditLog.objects.filter(tenant=tenant_a, action="create").exists()


@pytest.mark.django_db
def test_assetclassification_views_category_create_post_invalid(client_a):
    """asset_category_create POST invalid data re-renders form with 200 and errors."""
    url = reverse("assets:asset_category_create")
    payload = _assetclassification_category_payload(code="", name="")  # missing required

    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_assetclassification_views_category_edit_get_renders_form(
    client_a, category_root_a
):
    """asset_category_edit GET renders form page with is_edit=True."""
    url = reverse("assets:asset_category_edit", kwargs={"pk": category_root_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is True
    assert resp.context["category"] == category_root_a


@pytest.mark.django_db
def test_assetclassification_views_category_edit_post_success(
    client_a, tenant_a, category_root_a
):
    """asset_category_edit POST updates category fields and redirects to detail."""
    url = reverse("assets:asset_category_edit", kwargs={"pk": category_root_a.pk})
    payload = _assetclassification_category_payload(
        code=category_root_a.code,
        name="Heavy Plant Equipment Updated",
        category_type="machinery",
        default_useful_life_months=144,
    )

    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_category_detail", kwargs={"pk": category_root_a.pk})

    category_root_a.refresh_from_db()
    assert category_root_a.name == "Heavy Plant Equipment Updated"
    assert category_root_a.default_useful_life_months == 144


@pytest.mark.django_db
def test_assetclassification_views_category_edit_post_invalid(
    client_a, category_root_a
):
    """asset_category_edit POST invalid data re-renders form with 200 and errors."""
    url = reverse("assets:asset_category_edit", kwargs={"pk": category_root_a.pk})
    payload = _assetclassification_category_payload(code="", name="")

    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_assetclassification_views_category_delete_require_post(
    client_a, category_root_a
):
    """asset_category_delete blocks GET requests with 405 Method Not Allowed."""
    url = reverse("assets:asset_category_delete", kwargs={"pk": category_root_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


@pytest.mark.django_db
def test_assetclassification_views_category_delete_permission_guard(
    member_client, category_root_a
):
    """asset_category_delete blocks non-tenant-admin users with 403 Forbidden."""
    url = reverse("assets:asset_category_delete", kwargs={"pk": category_root_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_assetclassification_views_category_delete_guard_blocked_by_child(
    client_a, category_root_a, category_child_a
):
    """asset_category_delete redirects with error if category has active children."""
    url = reverse("assets:asset_category_delete", kwargs={"pk": category_root_a.pk})
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_category_detail", kwargs={"pk": category_root_a.pk})
    assert AssetCategory.objects.filter(pk=category_root_a.pk).exists()

    msgs = _assetclassification_get_flash_messages(resp)
    assert any("sub-categories" in m for m in msgs)


@pytest.mark.django_db
def test_assetclassification_views_category_delete_guard_blocked_by_model(
    client_a, tenant_a, asset_model_a
):
    """asset_category_delete redirects with error if category has equipment models."""
    category = asset_model_a.category
    url = reverse("assets:asset_category_delete", kwargs={"pk": category.pk})
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_category_detail", kwargs={"pk": category.pk})
    assert AssetCategory.objects.filter(pk=category.pk).exists()

    msgs = _assetclassification_get_flash_messages(resp)
    assert any("equipment models" in m for m in msgs)


@pytest.mark.django_db
def test_assetclassification_views_category_delete_success(client_a, tenant_a):
    """asset_category_delete deletes standalone category and redirects to list."""
    standalone = AssetCategory.objects.create(
        tenant=tenant_a,
        code="OFF-FURN",
        name="Office Furniture",
        category_type="furniture",
        is_active=True,
    )
    url = reverse("assets:asset_category_delete", kwargs={"pk": standalone.pk})
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_category_list")
    assert not AssetCategory.objects.filter(pk=standalone.pk).exists()


# ==============================================================================
# 2. AssetModel Views
# ==============================================================================


@pytest.mark.django_db
def test_assetclassification_views_model_list_renders_200_and_context(
    client_a, asset_model_a
):
    """asset_model_list renders 200 with required context keys and aggregates."""
    url = reverse("assets:asset_model_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "models" in resp.context
    assert "model_list" in resp.context
    assert "categories" in resp.context
    assert ("model_statuses" in resp.context or "status_choices" in resp.context)
    assert ("total_count" in resp.context or "status_counts" in resp.context)
    assert "q" in resp.context
    assert "search_query" in resp.context
    assert resp.context["total_count"] >= 1
    assert resp.context["active_count"] >= 1


@pytest.mark.django_db
def test_assetclassification_views_model_list_filter_search(
    client_a, asset_model_a
):
    """asset_model_list filters by q search query."""
    url = reverse("assets:asset_model_list")

    # Match by model_number
    resp_num = client_a.get(url, {"q": asset_model_a.model_number})
    assert resp_num.status_code == 200
    pks = [m.pk for m in resp_num.context["models"]]
    assert asset_model_a.pk in pks

    # Match by model name
    resp_name = client_a.get(url, {"q": "Excavator"})
    assert resp_name.status_code == 200
    name_pks = [m.pk for m in resp_name.context["models"]]
    assert asset_model_a.pk in name_pks

    # No match
    resp_none = client_a.get(url, {"q": "UNKNOWN_MODEL_STRING"})
    assert resp_none.status_code == 200
    assert len(resp_none.context["models"]) == 0


@pytest.mark.django_db
def test_assetclassification_views_model_list_filter_status(
    client_a, asset_model_a
):
    """asset_model_list filters by model_status."""
    url = reverse("assets:asset_model_list")

    resp_active = client_a.get(url, {"status": "active"})
    assert resp_active.status_code == 200
    pks = [m.pk for m in resp_active.context["models"]]
    assert asset_model_a.pk in pks

    resp_discontinued = client_a.get(url, {"status": "discontinued"})
    assert resp_discontinued.status_code == 200
    disc_pks = [m.pk for m in resp_discontinued.context["models"]]
    assert asset_model_a.pk not in disc_pks


@pytest.mark.django_db
def test_assetclassification_views_model_list_filter_category(
    client_a, asset_model_a, category_child_a
):
    """asset_model_list filters by category ID."""
    url = reverse("assets:asset_model_list")

    # Match model's category
    resp = client_a.get(url, {"category": str(asset_model_a.category_id)})
    assert resp.status_code == 200
    pks = [m.pk for m in resp.context["models"]]
    assert asset_model_a.pk in pks

    # Different category
    resp_other = client_a.get(url, {"category": str(category_child_a.pk)})
    assert resp_other.status_code == 200
    other_pks = [m.pk for m in resp_other.context["models"]]
    assert asset_model_a.pk not in other_pks


@pytest.mark.django_db
def test_assetclassification_views_model_list_junk_parameters_safe(
    client_a, asset_model_a
):
    """asset_model_list handles junk parameters without 500."""
    url = reverse("assets:asset_model_list")
    resp = client_a.get(url, {
        "category": "not_an_id",
        "status": "bogus_status",
        "page": "9999",
    })
    assert resp.status_code == 200


@pytest.mark.django_db
def test_assetclassification_views_model_detail_renders_200_and_context(
    client_a, asset_model_a, operational_asset_a
):
    """asset_model_detail renders 200 with model, spec_templates, deployed_assets, deployed_count."""
    # Wire operational asset model number to match asset_model_a
    operational_asset_a.model_number = asset_model_a.model_number
    operational_asset_a.save()

    url = reverse("assets:asset_model_detail", kwargs={"pk": asset_model_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["model"] == asset_model_a
    assert "spec_templates" in resp.context
    assert "deployed_assets" in resp.context
    assert resp.context["deployed_count"] >= 1
    assert operational_asset_a in resp.context["deployed_assets"]


@pytest.mark.django_db
def test_assetclassification_views_model_detail_cross_tenant_404(
    client_b, asset_model_a
):
    """Tenant B cannot access Tenant A asset model (IDOR protection)."""
    url = reverse("assets:asset_model_detail", kwargs={"pk": asset_model_a.pk})
    resp = client_b.get(url)
    assert resp.status_code == 404


@pytest.mark.django_db
def test_assetclassification_views_model_create_get_renders_form(client_a):
    """asset_model_create GET renders form page with is_edit=False."""
    url = reverse("assets:asset_model_create")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["model"] is None


@pytest.mark.django_db
def test_assetclassification_views_model_create_post_success(
    client_a, tenant_a, category_root_a
):
    """asset_model_create POST valid data creates model and redirects to detail."""
    url = reverse("assets:asset_model_create")
    payload = _assetclassification_model_payload(
        category=category_root_a,
        model_number="KOM-PC200-8",
        name="Komatsu Hydraulic Excavator",
    )

    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    created = AssetModel.objects.filter(tenant=tenant_a, model_number="KOM-PC200-8").first()
    assert created is not None
    assert created.tenant == tenant_a
    assert created.name == "Komatsu Hydraulic Excavator"
    assert resp.url == reverse("assets:asset_model_detail", kwargs={"pk": created.pk})


@pytest.mark.django_db
def test_assetclassification_views_model_create_post_invalid(client_a):
    """asset_model_create POST invalid data re-renders form with 200."""
    url = reverse("assets:asset_model_create")
    payload = _assetclassification_model_payload(category="", model_number="")

    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_assetclassification_views_model_edit_get_renders_form(
    client_a, asset_model_a
):
    """asset_model_edit GET renders form page with is_edit=True."""
    url = reverse("assets:asset_model_edit", kwargs={"pk": asset_model_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is True
    assert resp.context["model"] == asset_model_a


@pytest.mark.django_db
def test_assetclassification_views_model_edit_post_success(
    client_a, asset_model_a
):
    """asset_model_edit POST valid data updates model and redirects to detail."""
    url = reverse("assets:asset_model_edit", kwargs={"pk": asset_model_a.pk})
    payload = _assetclassification_model_payload(
        category=asset_model_a.category,
        model_number=asset_model_a.model_number,
        name="Hydraulic Excavator Series II",
        estimated_replacement_cost="185000.00",
    )

    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_model_detail", kwargs={"pk": asset_model_a.pk})

    asset_model_a.refresh_from_db()
    assert asset_model_a.name == "Hydraulic Excavator Series II"
    assert asset_model_a.estimated_replacement_cost == Decimal("185000.00")


@pytest.mark.django_db
def test_assetclassification_views_model_edit_post_invalid(
    client_a, asset_model_a
):
    """asset_model_edit POST invalid data re-renders form with 200 and errors."""
    url = reverse("assets:asset_model_edit", kwargs={"pk": asset_model_a.pk})
    payload = _assetclassification_model_payload(category=asset_model_a.category, name="")

    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_assetclassification_views_model_delete_require_post(
    client_a, asset_model_a
):
    """asset_model_delete blocks GET requests with 405 Method Not Allowed."""
    url = reverse("assets:asset_model_delete", kwargs={"pk": asset_model_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


@pytest.mark.django_db
def test_assetclassification_views_model_delete_permission_guard(
    member_client, asset_model_a
):
    """asset_model_delete blocks non-tenant-admin users with 403 Forbidden."""
    url = reverse("assets:asset_model_delete", kwargs={"pk": asset_model_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_assetclassification_views_model_delete_guard_blocked_by_deployed_assets(
    client_a, asset_model_a, operational_asset_a
):
    """asset_model_delete redirects with error if physical registered assets reference model number."""
    operational_asset_a.model_number = asset_model_a.model_number
    operational_asset_a.save()

    url = reverse("assets:asset_model_delete", kwargs={"pk": asset_model_a.pk})
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_model_detail", kwargs={"pk": asset_model_a.pk})
    assert AssetModel.objects.filter(pk=asset_model_a.pk).exists()

    msgs = _assetclassification_get_flash_messages(resp)
    assert any("registered assets" in m for m in msgs)


@pytest.mark.django_db
def test_assetclassification_views_model_delete_success(
    client_a, tenant_a, category_root_a
):
    """asset_model_delete deletes unreferenced model and redirects to list."""
    unreferenced = AssetModel.objects.create(
        tenant=tenant_a,
        model_number="UNREF-999",
        name="Unreferenced Model",
        category=category_root_a,
    )
    url = reverse("assets:asset_model_delete", kwargs={"pk": unreferenced.pk})
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_model_list")
    assert not AssetModel.objects.filter(pk=unreferenced.pk).exists()


# ==============================================================================
# 3. AssetCriticalityAssessment Views
# ==============================================================================


@pytest.mark.django_db
def test_assetclassification_views_criticality_list_renders_200_and_context(
    client_a, criticality_assessment_a
):
    """asset_criticality_assessment_list renders 200 with required context keys."""
    url = reverse("assets:asset_criticality_assessment_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "assessments" in resp.context
    assert "assessment_list" in resp.context
    assert "abc_choices" in resp.context
    assert "status_choices" in resp.context
    assert ("total_count" in resp.context or "status_counts" in resp.context)
    assert "class_a_count" in resp.context
    assert "q" in resp.context
    assert "search_query" in resp.context
    assert "selected_asset" in resp.context
    assert resp.context["total_count"] >= 1


@pytest.mark.django_db
def test_assetclassification_views_criticality_list_filter_search(
    client_a, criticality_assessment_a
):
    """asset_criticality_assessment_list filters by q search query."""
    url = reverse("assets:asset_criticality_assessment_list")

    # Match assessment title
    resp_title = client_a.get(url, {"q": "CNC Criticality Review"})
    assert resp_title.status_code == 200
    pks = [a.pk for a in resp_title.context["assessments"]]
    assert criticality_assessment_a.pk in pks

    # Match target asset number
    resp_asset = client_a.get(url, {"q": criticality_assessment_a.asset.number})
    assert resp_asset.status_code == 200
    asset_pks = [a.pk for a in resp_asset.context["assessments"]]
    assert criticality_assessment_a.pk in asset_pks

    # No match
    resp_none = client_a.get(url, {"q": "NONEXISTENT_REVIEW_TITLE"})
    assert resp_none.status_code == 200
    assert len(resp_none.context["assessments"]) == 0


@pytest.mark.django_db
def test_assetclassification_views_criticality_list_filter_abc_and_status(
    client_a, criticality_assessment_a
):
    """asset_criticality_assessment_list filters by abc_rating and assessment_status."""
    url = reverse("assets:asset_criticality_assessment_list")

    # Filter abc rating
    resp_abc = client_a.get(url, {"abc": criticality_assessment_a.abc_rating})
    assert resp_abc.status_code == 200
    pks = [a.pk for a in resp_abc.context["assessments"]]
    assert criticality_assessment_a.pk in pks

    # Filter status draft
    resp_status = client_a.get(url, {"status": "draft"})
    assert resp_status.status_code == 200
    status_pks = [a.pk for a in resp_status.context["assessments"]]
    assert criticality_assessment_a.pk in status_pks

    # Filter status approved -> 0
    resp_app = client_a.get(url, {"status": "approved"})
    assert resp_app.status_code == 200
    app_pks = [a.pk for a in resp_app.context["assessments"]]
    assert criticality_assessment_a.pk not in app_pks


@pytest.mark.django_db
def test_assetclassification_views_criticality_list_filter_asset(
    client_a, criticality_assessment_a, operational_asset_a
):
    """asset_criticality_assessment_list filters by target asset ID."""
    url = reverse("assets:asset_criticality_assessment_list")

    # Valid asset id
    resp = client_a.get(url, {"asset": str(operational_asset_a.pk)})
    assert resp.status_code == 200
    pks = [a.pk for a in resp.context["assessments"]]
    assert criticality_assessment_a.pk in pks

    # Nonexistent asset id
    resp_other = client_a.get(url, {"asset": "999999"})
    assert resp_other.status_code == 200
    assert len(resp_other.context["assessments"]) == 0

    # Junk asset id safe
    resp_junk = client_a.get(url, {"asset": "junk_text"})
    assert resp_junk.status_code == 200


@pytest.mark.django_db
def test_assetclassification_views_criticality_detail_renders_200_and_context(
    client_a, criticality_assessment_a
):
    """asset_criticality_assessment_detail renders 200 with assessment and consequence dimensions."""
    url = reverse(
        "assets:asset_criticality_assessment_detail",
        kwargs={"pk": criticality_assessment_a.pk},
    )
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "assessment" in resp.context
    assessment = resp.context["assessment"]
    assert assessment == criticality_assessment_a

    # Consequence dimensions present and assertable
    assert assessment.operational_downtime_impact == 5
    assert assessment.safety_impact == 4
    assert assessment.environmental_impact == 3
    assert assessment.regulatory_compliance_impact == 3
    assert assessment.financial_impact == 4
    assert assessment.is_single_point_of_failure is True
    assert assessment.composite_score >= 20
    assert assessment.abc_rating == "A"


@pytest.mark.django_db
def test_assetclassification_views_criticality_detail_cross_tenant_404(
    client_b, criticality_assessment_a
):
    """Tenant B cannot view Tenant A criticality assessment."""
    url = reverse(
        "assets:asset_criticality_assessment_detail",
        kwargs={"pk": criticality_assessment_a.pk},
    )
    resp = client_b.get(url)
    assert resp.status_code == 404


@pytest.mark.django_db
def test_assetclassification_views_criticality_create_get_renders_form(client_a):
    """asset_criticality_assessment_create GET renders form page with is_edit=False."""
    url = reverse("assets:asset_criticality_assessment_create")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["assessment"] is None


@pytest.mark.django_db
def test_assetclassification_views_criticality_create_post_success_auto_calculates(
    client_a, tenant_a, operational_asset_a, vendor_party_a
):
    """asset_criticality_assessment_create POST valid data creates assessment and auto-calculates score."""
    url = reverse("assets:asset_criticality_assessment_create")
    payload = _assetclassification_criticality_payload(
        asset=operational_asset_a,
        assessor=vendor_party_a,
        title="Centrifugal Chiller Criticality Assessment",
        safety_impact=4,
        environmental_impact=2,
        operational_downtime_impact=5,
        financial_impact=4,
        regulatory_compliance_impact=2,
        is_single_point_of_failure=True,
    )

    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    created = AssetCriticalityAssessment.objects.filter(
        tenant=tenant_a, title="Centrifugal Chiller Criticality Assessment"
    ).first()
    assert created is not None
    assert created.tenant == tenant_a
    assert created.assessment_status == "draft"
    # Base consequence sum = 4 + 2 + 5 + 4 + 2 = 17, plus SPOF bonus +5 = 22
    assert created.composite_score == 22
    assert created.abc_rating == "A"
    assert resp.url == reverse(
        "assets:asset_criticality_assessment_detail", kwargs={"pk": created.pk}
    )


@pytest.mark.django_db
def test_assetclassification_views_criticality_create_post_invalid(client_a):
    """asset_criticality_assessment_create POST invalid data returns 200 with form errors."""
    url = reverse("assets:asset_criticality_assessment_create")
    payload = _assetclassification_criticality_payload(asset="", assessor="", title="")

    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_assetclassification_views_criticality_edit_get_renders_form(
    client_a, criticality_assessment_a
):
    """asset_criticality_assessment_edit GET renders form page with is_edit=True for draft."""
    url = reverse(
        "assets:asset_criticality_assessment_edit",
        kwargs={"pk": criticality_assessment_a.pk},
    )
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is True
    assert resp.context["assessment"] == criticality_assessment_a


@pytest.mark.django_db
def test_assetclassification_views_criticality_edit_post_success(
    client_a, criticality_assessment_a
):
    """asset_criticality_assessment_edit POST updates assessment and recalculates composite score."""
    url = reverse(
        "assets:asset_criticality_assessment_edit",
        kwargs={"pk": criticality_assessment_a.pk},
    )
    payload = _assetclassification_criticality_payload(
        asset=criticality_assessment_a.asset,
        assessor=criticality_assessment_a.assessor,
        title="Updated CNC Criticality Review",
        safety_impact=1,
        environmental_impact=1,
        operational_downtime_impact=1,
        financial_impact=1,
        regulatory_compliance_impact=1,
        is_single_point_of_failure=False,
    )

    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse(
        "assets:asset_criticality_assessment_detail",
        kwargs={"pk": criticality_assessment_a.pk},
    )

    criticality_assessment_a.refresh_from_db()
    assert criticality_assessment_a.title == "Updated CNC Criticality Review"
    assert criticality_assessment_a.composite_score == 5
    assert criticality_assessment_a.abc_rating == "C"


@pytest.mark.django_db
def test_assetclassification_views_criticality_edit_guard_blocked_if_approved(
    client_a, criticality_assessment_a
):
    """asset_criticality_assessment_edit redirects to detail with error if assessment is approved."""
    criticality_assessment_a.assessment_status = "approved"
    criticality_assessment_a.save()

    url = reverse(
        "assets:asset_criticality_assessment_edit",
        kwargs={"pk": criticality_assessment_a.pk},
    )

    # GET blocked
    resp_get = client_a.get(url)
    assert resp_get.status_code == 302
    assert resp_get.url == reverse(
        "assets:asset_criticality_assessment_detail",
        kwargs={"pk": criticality_assessment_a.pk},
    )

    # POST blocked
    payload = _assetclassification_criticality_payload(
        asset=criticality_assessment_a.asset,
        assessor=criticality_assessment_a.assessor,
        title="Attempted Unauthorized Modification",
    )
    resp_post = client_a.post(url, data=payload)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse(
        "assets:asset_criticality_assessment_detail",
        kwargs={"pk": criticality_assessment_a.pk},
    )

    msgs = _assetclassification_get_flash_messages(resp_post)
    assert any("cannot be edited" in m for m in msgs)


@pytest.mark.django_db
def test_assetclassification_views_criticality_edit_guard_blocked_if_superseded(
    client_a, criticality_assessment_a
):
    """asset_criticality_assessment_edit redirects to detail with error if assessment is superseded."""
    criticality_assessment_a.assessment_status = "superseded"
    criticality_assessment_a.save()

    url = reverse(
        "assets:asset_criticality_assessment_edit",
        kwargs={"pk": criticality_assessment_a.pk},
    )
    resp = client_a.get(url)
    assert resp.status_code == 302
    assert resp.url == reverse(
        "assets:asset_criticality_assessment_detail",
        kwargs={"pk": criticality_assessment_a.pk},
    )

    msgs = _assetclassification_get_flash_messages(resp)
    assert any("cannot be edited" in m for m in msgs)


@pytest.mark.django_db
def test_assetclassification_views_criticality_delete_require_post(
    client_a, criticality_assessment_a
):
    """asset_criticality_assessment_delete blocks GET requests with 405 Method Not Allowed."""
    url = reverse(
        "assets:asset_criticality_assessment_delete",
        kwargs={"pk": criticality_assessment_a.pk},
    )
    resp = client_a.get(url)
    assert resp.status_code == 405


@pytest.mark.django_db
def test_assetclassification_views_criticality_delete_permission_guard(
    member_client, criticality_assessment_a
):
    """asset_criticality_assessment_delete blocks non-tenant-admin with 403 Forbidden."""
    url = reverse(
        "assets:asset_criticality_assessment_delete",
        kwargs={"pk": criticality_assessment_a.pk},
    )
    resp = member_client.post(url)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_assetclassification_views_criticality_delete_guard_blocked_if_approved(
    client_a, criticality_assessment_a
):
    """asset_criticality_assessment_delete redirects with error if assessment is approved."""
    criticality_assessment_a.assessment_status = "approved"
    criticality_assessment_a.save()

    url = reverse(
        "assets:asset_criticality_assessment_delete",
        kwargs={"pk": criticality_assessment_a.pk},
    )
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse(
        "assets:asset_criticality_assessment_detail",
        kwargs={"pk": criticality_assessment_a.pk},
    )
    assert AssetCriticalityAssessment.objects.filter(pk=criticality_assessment_a.pk).exists()

    msgs = _assetclassification_get_flash_messages(resp)
    assert any("cannot be deleted" in m for m in msgs)


@pytest.mark.django_db
def test_assetclassification_views_criticality_delete_guard_blocked_if_superseded(
    client_a, criticality_assessment_a
):
    """asset_criticality_assessment_delete redirects with error if assessment is superseded."""
    criticality_assessment_a.assessment_status = "superseded"
    criticality_assessment_a.save()

    url = reverse(
        "assets:asset_criticality_assessment_delete",
        kwargs={"pk": criticality_assessment_a.pk},
    )
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse(
        "assets:asset_criticality_assessment_detail",
        kwargs={"pk": criticality_assessment_a.pk},
    )
    assert AssetCriticalityAssessment.objects.filter(pk=criticality_assessment_a.pk).exists()


@pytest.mark.django_db
def test_assetclassification_views_criticality_delete_draft_success(
    client_a, criticality_assessment_a
):
    """asset_criticality_assessment_delete deletes draft assessment and redirects to list."""
    url = reverse(
        "assets:asset_criticality_assessment_delete",
        kwargs={"pk": criticality_assessment_a.pk},
    )
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_criticality_assessment_list")
    assert not AssetCriticalityAssessment.objects.filter(pk=criticality_assessment_a.pk).exists()


@pytest.mark.django_db
def test_assetclassification_views_criticality_approve_require_post(
    client_a, criticality_assessment_a
):
    """asset_criticality_assessment_approve blocks GET requests with 405 Method Not Allowed."""
    url = reverse(
        "assets:asset_criticality_assessment_approve",
        kwargs={"pk": criticality_assessment_a.pk},
    )
    resp = client_a.get(url)
    assert resp.status_code == 405


@pytest.mark.django_db
def test_assetclassification_views_criticality_approve_permission_guard(
    member_client, criticality_assessment_a
):
    """asset_criticality_assessment_approve blocks non-tenant-admin with 403 Forbidden."""
    url = reverse(
        "assets:asset_criticality_assessment_approve",
        kwargs={"pk": criticality_assessment_a.pk},
    )
    resp = member_client.post(url)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_assetclassification_views_criticality_approve_workflow_success_and_asset_sync(
    client_a, tenant_a, admin_user, criticality_assessment_a, operational_asset_a
):
    """asset_criticality_assessment_approve transitions to approved, syncs scm.Asset.criticality, and logs audit."""
    criticality_assessment_a.abc_rating = "A"
    criticality_assessment_a.save()

    url = reverse(
        "assets:asset_criticality_assessment_approve",
        kwargs={"pk": criticality_assessment_a.pk},
    )
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse(
        "assets:asset_criticality_assessment_detail",
        kwargs={"pk": criticality_assessment_a.pk},
    )

    criticality_assessment_a.refresh_from_db()
    assert criticality_assessment_a.assessment_status == "approved"
    assert criticality_assessment_a.approved_by == admin_user
    assert criticality_assessment_a.approved_at is not None

    # Assert scm.Asset.criticality synchronized to 'critical' for Class A
    operational_asset_a.refresh_from_db()
    assert operational_asset_a.criticality == "critical"

    # Verify audit log entry
    assert AuditLog.objects.filter(tenant=tenant_a, action="approve").exists()

    msgs = _assetclassification_get_flash_messages(resp)
    assert any("approved!" in m for m in msgs)


@pytest.mark.django_db
def test_assetclassification_views_criticality_approve_supersedes_prior_approved(
    client_a, tenant_a, admin_user, operational_asset_a, vendor_party_a
):
    """asset_criticality_assessment_approve automatically supersedes previous approved assessment for asset."""
    # 1. Seed prior approved assessment
    prior = AssetCriticalityAssessment(
        tenant=tenant_a,
        title="Prior Active Assessment",
        asset=operational_asset_a,
        assessor=vendor_party_a,
        safety_impact=2,
        environmental_impact=2,
        operational_downtime_impact=2,
        financial_impact=2,
        regulatory_compliance_impact=2,
        is_single_point_of_failure=False,
        assessment_status="approved",
        approved_by=admin_user,
        approved_at=timezone.now(),
    )
    prior.calculate_composite_score()
    prior.save()

    # 2. Seed new draft assessment
    new_assessment = AssetCriticalityAssessment(
        tenant=tenant_a,
        title="New Detailed Risk Re-Evaluation",
        asset=operational_asset_a,
        assessor=vendor_party_a,
        safety_impact=4,
        environmental_impact=3,
        operational_downtime_impact=5,
        financial_impact=4,
        regulatory_compliance_impact=3,
        is_single_point_of_failure=True,
        assessment_status="draft",
    )
    new_assessment.calculate_composite_score()
    new_assessment.save()

    url = reverse(
        "assets:asset_criticality_assessment_approve",
        kwargs={"pk": new_assessment.pk},
    )
    resp = client_a.post(url)
    assert resp.status_code == 302

    prior.refresh_from_db()
    new_assessment.refresh_from_db()

    assert prior.assessment_status == "superseded"
    assert new_assessment.assessment_status == "approved"


@pytest.mark.django_db
def test_assetclassification_views_criticality_approve_guard_already_approved_or_superseded(
    client_a, criticality_assessment_a
):
    """asset_criticality_assessment_approve redirects with warning if already approved or superseded."""
    criticality_assessment_a.assessment_status = "approved"
    criticality_assessment_a.save()

    url = reverse(
        "assets:asset_criticality_assessment_approve",
        kwargs={"pk": criticality_assessment_a.pk},
    )
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse(
        "assets:asset_criticality_assessment_detail",
        kwargs={"pk": criticality_assessment_a.pk},
    )

    msgs = _assetclassification_get_flash_messages(resp)
    assert any("cannot be approved" in m for m in msgs)


# ==============================================================================
# 4. AssetSpecificationTemplate Views
# ==============================================================================


@pytest.mark.django_db
def test_assetclassification_views_spec_template_list_renders_200_and_context(
    client_a, spec_template_a
):
    """asset_specification_template_list renders 200 with required context keys."""
    url = reverse("assets:asset_specification_template_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "templates" in resp.context
    assert "template_list" in resp.context
    assert ("data_types" in resp.context or "data_type_choices" in resp.context)
    assert "categories" in resp.context
    assert ("total_count" in resp.context or "status_counts" in resp.context)
    assert "numeric_count" in resp.context
    assert "q" in resp.context
    assert "search_query" in resp.context
    assert resp.context["total_count"] >= 1


@pytest.mark.django_db
def test_assetclassification_views_spec_template_list_filter_search(
    client_a, spec_template_a
):
    """asset_specification_template_list filters by q search query."""
    url = reverse("assets:asset_specification_template_list")

    # Match by attribute_key
    resp_key = client_a.get(url, {"q": spec_template_a.attribute_key})
    assert resp_key.status_code == 200
    pks = [t.pk for t in resp_key.context["templates"]]
    assert spec_template_a.pk in pks

    # Match by display_name
    resp_name = client_a.get(url, {"q": "Operating Voltage"})
    assert resp_name.status_code == 200
    name_pks = [t.pk for t in resp_name.context["templates"]]
    assert spec_template_a.pk in name_pks

    # No match
    resp_none = client_a.get(url, {"q": "NONEXISTENT_KEY_PARAM"})
    assert resp_none.status_code == 200
    assert len(resp_none.context["templates"]) == 0


@pytest.mark.django_db
def test_assetclassification_views_spec_template_list_filter_type_and_category(
    client_a, spec_template_a, category_child_a
):
    """asset_specification_template_list filters by data_type and category ID."""
    url = reverse("assets:asset_specification_template_list")

    # Filter type 'number' -> matches spec_template_a
    resp_num = client_a.get(url, {"type": "number"})
    assert resp_num.status_code == 200
    num_pks = [t.pk for t in resp_num.context["templates"]]
    assert spec_template_a.pk in num_pks

    # Filter type 'text' -> excludes spec_template_a
    resp_text = client_a.get(url, {"type": "text"})
    assert resp_text.status_code == 200
    text_pks = [t.pk for t in resp_text.context["templates"]]
    assert spec_template_a.pk not in text_pks

    # Filter category
    resp_cat = client_a.get(url, {"category": str(spec_template_a.category_id)})
    assert resp_cat.status_code == 200
    cat_pks = [t.pk for t in resp_cat.context["templates"]]
    assert spec_template_a.pk in cat_pks

    # Other category
    resp_other = client_a.get(url, {"category": str(category_child_a.pk)})
    assert resp_other.status_code == 200
    other_pks = [t.pk for t in resp_other.context["templates"]]
    assert spec_template_a.pk not in other_pks


@pytest.mark.django_db
def test_assetclassification_views_spec_template_list_junk_parameters_safe(
    client_a, spec_template_a
):
    """asset_specification_template_list handles junk parameters without 500."""
    url = reverse("assets:asset_specification_template_list")
    resp = client_a.get(url, {
        "category": "not_an_int",
        "type": "invalid_data_type",
        "page": "9999",
    })
    assert resp.status_code == 200


@pytest.mark.django_db
def test_assetclassification_views_spec_template_detail_renders_200_and_context(
    client_a, spec_template_a
):
    """asset_specification_template_detail renders 200 with template in context."""
    url = reverse(
        "assets:asset_specification_template_detail",
        kwargs={"pk": spec_template_a.pk},
    )
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["template"] == spec_template_a


@pytest.mark.django_db
def test_assetclassification_views_spec_template_detail_cross_tenant_404(
    client_b, spec_template_a
):
    """Tenant B cannot view Tenant A spec template (IDOR isolation)."""
    url = reverse(
        "assets:asset_specification_template_detail",
        kwargs={"pk": spec_template_a.pk},
    )
    resp = client_b.get(url)
    assert resp.status_code == 404


@pytest.mark.django_db
def test_assetclassification_views_spec_template_create_get_renders_form(client_a):
    """asset_specification_template_create GET renders form page with is_edit=False."""
    url = reverse("assets:asset_specification_template_create")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["template"] is None


@pytest.mark.django_db
def test_assetclassification_views_spec_template_create_post_success(
    client_a, tenant_a, category_root_a
):
    """asset_specification_template_create POST valid data creates template and redirects."""
    url = reverse("assets:asset_specification_template_create")
    payload = _assetclassification_spec_template_payload(
        category=category_root_a.pk,
        attribute_key="full_load_amperage",
        display_name="Full Load Amperage (FLA)",
        unit_of_measure="A",
        min_numeric_value="10.000",
        max_numeric_value="350.000",
        validation_regex="",
    )

    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    created = AssetSpecificationTemplate.objects.filter(
        tenant=tenant_a, attribute_key="full_load_amperage"
    ).first()
    assert created is not None
    assert created.tenant == tenant_a
    assert created.unit_of_measure == "A"
    assert resp.url == reverse(
        "assets:asset_specification_template_detail", kwargs={"pk": created.pk}
    )


@pytest.mark.django_db
def test_assetclassification_views_spec_template_create_post_invalid(client_a):
    """asset_specification_template_create POST invalid data re-renders form with 200."""
    url = reverse("assets:asset_specification_template_create")
    payload = _assetclassification_spec_template_payload(attribute_key="", display_name="")

    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_assetclassification_views_spec_template_edit_get_renders_form(
    client_a, spec_template_a
):
    """asset_specification_template_edit GET renders form page with is_edit=True."""
    url = reverse(
        "assets:asset_specification_template_edit",
        kwargs={"pk": spec_template_a.pk},
    )
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is True
    assert resp.context["template"] == spec_template_a


@pytest.mark.django_db
def test_assetclassification_views_spec_template_edit_post_success(
    client_a, spec_template_a
):
    """asset_specification_template_edit POST updates template and redirects to detail."""
    url = reverse(
        "assets:asset_specification_template_edit",
        kwargs={"pk": spec_template_a.pk},
    )
    payload = _assetclassification_spec_template_payload(
        category=spec_template_a.category.pk,
        attribute_key=spec_template_a.attribute_key,
        display_name="Rated Operating Voltage (RMS)",
        unit_of_measure="VAC",
        min_numeric_value="400.000",
        max_numeric_value="480.000",
        validation_regex="",
    )

    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse(
        "assets:asset_specification_template_detail",
        kwargs={"pk": spec_template_a.pk},
    )

    spec_template_a.refresh_from_db()
    assert spec_template_a.display_name == "Rated Operating Voltage (RMS)"
    assert spec_template_a.unit_of_measure == "VAC"
    assert spec_template_a.min_numeric_value == Decimal("400.000")


@pytest.mark.django_db
def test_assetclassification_views_spec_template_edit_post_invalid(
    client_a, spec_template_a
):
    """asset_specification_template_edit POST invalid min/max bounds returns 200 with errors."""
    url = reverse(
        "assets:asset_specification_template_edit",
        kwargs={"pk": spec_template_a.pk},
    )
    # min > max violation
    payload = _assetclassification_spec_template_payload(
        category=spec_template_a.category.pk,
        attribute_key=spec_template_a.attribute_key,
        min_numeric_value="500.000",
        max_numeric_value="200.000",
        validation_regex="",
    )

    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_assetclassification_views_spec_template_delete_require_post(
    client_a, spec_template_a
):
    """asset_specification_template_delete blocks GET requests with 405 Method Not Allowed."""
    url = reverse(
        "assets:asset_specification_template_delete",
        kwargs={"pk": spec_template_a.pk},
    )
    resp = client_a.get(url)
    assert resp.status_code == 405


@pytest.mark.django_db
def test_assetclassification_views_spec_template_delete_permission_guard(
    member_client, spec_template_a
):
    """asset_specification_template_delete blocks non-tenant-admin with 403 Forbidden."""
    url = reverse(
        "assets:asset_specification_template_delete",
        kwargs={"pk": spec_template_a.pk},
    )
    resp = member_client.post(url)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_assetclassification_views_spec_template_delete_success(
    client_a, spec_template_a
):
    """asset_specification_template_delete deletes template and redirects to list."""
    url = reverse(
        "assets:asset_specification_template_delete",
        kwargs={"pk": spec_template_a.pk},
    )
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_specification_template_list")
    assert not AssetSpecificationTemplate.objects.filter(pk=spec_template_a.pk).exists()


# ==============================================================================
# 5. Security & Authentication Checks
# ==============================================================================


@pytest.mark.django_db
def test_assetclassification_views_unauthenticated_redirects(
    client, category_root_a, asset_model_a, criticality_assessment_a, spec_template_a
):
    """Anonymous client accessing any classification view is redirected to login."""
    protected_urls = [
        reverse("assets:asset_category_list"),
        reverse("assets:asset_category_create"),
        reverse("assets:asset_category_detail", kwargs={"pk": category_root_a.pk}),
        reverse("assets:asset_category_edit", kwargs={"pk": category_root_a.pk}),
        reverse("assets:asset_model_list"),
        reverse("assets:asset_model_create"),
        reverse("assets:asset_model_detail", kwargs={"pk": asset_model_a.pk}),
        reverse("assets:asset_model_edit", kwargs={"pk": asset_model_a.pk}),
        reverse("assets:asset_criticality_assessment_list"),
        reverse("assets:asset_criticality_assessment_create"),
        reverse("assets:asset_criticality_assessment_detail", kwargs={"pk": criticality_assessment_a.pk}),
        reverse("assets:asset_criticality_assessment_edit", kwargs={"pk": criticality_assessment_a.pk}),
        reverse("assets:asset_specification_template_list"),
        reverse("assets:asset_specification_template_create"),
        reverse("assets:asset_specification_template_detail", kwargs={"pk": spec_template_a.pk}),
        reverse("assets:asset_specification_template_edit", kwargs={"pk": spec_template_a.pk}),
    ]

    for url in protected_urls:
        resp = client.get(url)
        assert resp.status_code == 302
        assert "/accounts/login/" in resp.url or "login" in resp.url
