"""Asset Classification & Categorization (Sub-module 11.3) — SECURITY Test Suite.

Comprehensive security, multi-tenancy, authorization, status-guard, and tamper-protection tests:
1. Cross-Tenant IDOR:
   - For all 4 models (AssetCategory, AssetModel, AssetCriticalityAssessment, AssetSpecificationTemplate):
     - Detail view with tenant B's PK as tenant A user -> asserts 404.
     - Edit view (GET and POST) with tenant B's PK as tenant A user -> asserts 404.
     - Delete view (POST) with tenant B's PK as tenant A admin -> asserts 404.
     - Criticality approve view (POST) with tenant B's PK as tenant A admin -> asserts 404.
     - Reverse IDOR: Tenant B user accessing Tenant A records returns 404 across detail, edit, delete, approve.
     - List views for tenant A must not contain any records belonging to tenant B.

2. Tenant Boundary Isolation on Form Inputs (Cross-Tenant FK Injection):
   - Attempting to create an AssetCategory with a parent belonging to tenant B -> rejected.
   - Attempting to create an AssetModel with category or manufacturer belonging to tenant B -> rejected.
   - Attempting to create an AssetCriticalityAssessment with asset or assessor belonging to tenant B -> rejected.
   - Attempting to create an AssetSpecificationTemplate with category or model belonging to tenant B -> rejected.

3. Authentication & Authorization Enforcement:
   - Unauthenticated requests across all 21 endpoints redirect to login.
   - Non-admin user (standard member) attempting delete actions -> returns 403 Forbidden.
   - Non-admin user attempting approve action -> returns 403 Forbidden.
   - State-changing actions (delete, approve) enforce @require_POST (GET returns 405 Method Not Allowed).

4. Mass-Assignment & Tamper Resistance:
   - Attempting to inject tenant, number, composite_score, abc_rating, assessment_status, approved_by,
     approved_at via POST data in asset_criticality_assessment_create or edit -> ignored / rejected,
     view-controlled values used.
   - Injected tenant on category, model, and spec template create/edit -> ignored, tenant isolation preserved.

5. Status Guard Compliance:
   - Direct POST to asset_criticality_assessment_edit on approved or superseded assessment is blocked with redirect.
   - Direct POST to asset_criticality_assessment_delete on approved or superseded assessment is blocked with redirect.
   - Direct POST to asset_criticality_assessment_approve on already approved or superseded assessment is blocked with redirect.

6. Audit Log Generation:
   - Verify AuditLog records are created for create, update, delete, and approve operations with tenant=request.tenant.
"""
from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
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

User = get_user_model()
pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (strictly prefixed with _assetclassification_)
# ==============================================================================


def _assetclassification_get_flash_messages(response):
    """Extract list of flash message strings from response."""
    return [str(m) for m in get_messages(response.wsgi_request)]


def _assetclassification_category_payload(**overrides):
    """Generate valid base form payload for AssetCategoryForm."""
    payload = {
        "code": "HVAC-SEC",
        "name": "Security HVAC Equipment",
        "parent": "",
        "category_type": "facility",
        "unspsc_code": "40101701",
        "unspsc_title": "Air handlers",
        "default_depreciation_method": "straight_line",
        "default_useful_life_months": 96,
        "default_maintenance_strategy": "preventive_calendar",
        "default_criticality": "medium",
        "description": "Classification category for security testing.",
        "display_order": 1,
        "is_active": True,
    }
    payload.update(overrides)
    return payload


def _assetclassification_model_payload(category, **overrides):
    """Generate valid base form payload for AssetModelForm."""
    cat_id = category.pk if hasattr(category, "pk") else category
    payload = {
        "model_number": "SEC-MDL-2026",
        "name": "Security Certified Model",
        "category": cat_id,
        "manufacturer": "",
        "manufacturer_name_fallback": "Security Corp",
        "description": "Equipment model for security testing.",
        "standard_warranty_months": 24,
        "warranty_coverage_type": "full_parts_labor",
        "expected_useful_life_months": 120,
        "default_meter_name": "Operating Hours",
        "default_meter_unit": "h",
        "estimated_replacement_cost": "75000.00",
        "model_status": "active",
        "technical_specifications": "Voltage: 480V; Amperage: 50A",
        "is_active": True,
    }
    payload.update(overrides)
    return payload


def _assetclassification_criticality_payload(asset, assessor, **overrides):
    """Generate valid base form payload for AssetCriticalityAssessmentForm."""
    asset_id = asset.pk if hasattr(asset, "pk") else asset
    assessor_id = assessor.pk if hasattr(assessor, "pk") else assessor
    payload = {
        "title": "Security Criticality Assessment",
        "asset": asset_id,
        "assessor": assessor_id,
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
        "findings_and_mitigation": "Security test assessment findings.",
    }
    payload.update(overrides)
    return payload


def _assetclassification_spec_template_payload(**overrides):
    """Generate valid base form payload for AssetSpecificationTemplateForm."""
    payload = {
        "attribute_key": "sec_operating_voltage",
        "display_name": "Security Operating Voltage",
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
        "help_text": "Security test help text.",
    }
    payload.update(overrides)
    return payload


# ==============================================================================
# 1. Cross-Tenant IDOR Protection Tests (Strict 404 & List Query Isolation)
# ==============================================================================


def test_assetclassification_security_idor_category_detail_returns_404(client_a, category_root_b):
    """Tenant A admin client accessing Tenant B category detail returns 404."""
    url = reverse("assets:asset_category_detail", args=[category_root_b.pk])
    response = client_a.get(url)
    assert response.status_code == 404


def test_assetclassification_security_idor_category_edit_get_and_post_returns_404(client_a, category_root_b):
    """Tenant A admin client attempting to view or submit edit to Tenant B category returns 404."""
    url = reverse("assets:asset_category_edit", args=[category_root_b.pk])
    assert client_a.get(url).status_code == 404

    payload = _assetclassification_category_payload(name="Tampered Name")
    assert client_a.post(url, data=payload).status_code == 404


def test_assetclassification_security_idor_category_delete_post_returns_404(client_a, category_root_b):
    """Tenant A admin client attempting to delete Tenant B category returns 404."""
    url = reverse("assets:asset_category_delete", args=[category_root_b.pk])
    response = client_a.post(url)
    assert response.status_code == 404
    assert AssetCategory.objects.filter(pk=category_root_b.pk).exists()


def test_assetclassification_security_idor_model_detail_returns_404(client_a, asset_model_b):
    """Tenant A admin client accessing Tenant B model detail returns 404."""
    url = reverse("assets:asset_model_detail", args=[asset_model_b.pk])
    response = client_a.get(url)
    assert response.status_code == 404


def test_assetclassification_security_idor_model_edit_get_and_post_returns_404(client_a, asset_model_b, category_root_a):
    """Tenant A admin client attempting to view or submit edit to Tenant B model returns 404."""
    url = reverse("assets:asset_model_edit", args=[asset_model_b.pk])
    assert client_a.get(url).status_code == 404

    payload = _assetclassification_model_payload(category=category_root_a, name="Tampered Model Name")
    assert client_a.post(url, data=payload).status_code == 404


def test_assetclassification_security_idor_model_delete_post_returns_404(client_a, asset_model_b):
    """Tenant A admin client attempting to delete Tenant B model returns 404."""
    url = reverse("assets:asset_model_delete", args=[asset_model_b.pk])
    response = client_a.post(url)
    assert response.status_code == 404
    assert AssetModel.objects.filter(pk=asset_model_b.pk).exists()


def test_assetclassification_security_idor_criticality_detail_returns_404(client_a, criticality_assessment_b):
    """Tenant A admin client accessing Tenant B criticality assessment detail returns 404."""
    url = reverse("assets:asset_criticality_assessment_detail", args=[criticality_assessment_b.pk])
    response = client_a.get(url)
    assert response.status_code == 404


def test_assetclassification_security_idor_criticality_edit_get_and_post_returns_404(
    client_a, criticality_assessment_b, operational_asset_a, vendor_party_a
):
    """Tenant A admin client attempting to view or submit edit to Tenant B criticality assessment returns 404."""
    url = reverse("assets:asset_criticality_assessment_edit", args=[criticality_assessment_b.pk])
    assert client_a.get(url).status_code == 404

    payload = _assetclassification_criticality_payload(
        asset=operational_asset_a, assessor=vendor_party_a, title="Tampered Criticality Title"
    )
    assert client_a.post(url, data=payload).status_code == 404


def test_assetclassification_security_idor_criticality_delete_post_returns_404(client_a, criticality_assessment_b):
    """Tenant A admin client attempting to delete Tenant B criticality assessment returns 404."""
    url = reverse("assets:asset_criticality_assessment_delete", args=[criticality_assessment_b.pk])
    response = client_a.post(url)
    assert response.status_code == 404
    assert AssetCriticalityAssessment.objects.filter(pk=criticality_assessment_b.pk).exists()


def test_assetclassification_security_idor_criticality_approve_post_returns_404(client_a, criticality_assessment_b):
    """Tenant A admin client attempting to approve Tenant B criticality assessment returns 404."""
    url = reverse("assets:asset_criticality_assessment_approve", args=[criticality_assessment_b.pk])
    response = client_a.post(url)
    assert response.status_code == 404
    criticality_assessment_b.refresh_from_db()
    assert criticality_assessment_b.assessment_status == "draft"
    assert criticality_assessment_b.approved_by is None


def test_assetclassification_security_idor_spec_template_detail_returns_404(client_a, spec_template_b):
    """Tenant A admin client accessing Tenant B specification template detail returns 404."""
    url = reverse("assets:asset_specification_template_detail", args=[spec_template_b.pk])
    response = client_a.get(url)
    assert response.status_code == 404


def test_assetclassification_security_idor_spec_template_edit_get_and_post_returns_404(client_a, spec_template_b, category_root_a):
    """Tenant A admin client attempting to view or submit edit to Tenant B specification template returns 404."""
    url = reverse("assets:asset_specification_template_edit", args=[spec_template_b.pk])
    assert client_a.get(url).status_code == 404

    payload = _assetclassification_spec_template_payload(category=category_root_a.pk, display_name="Tampered Spec")
    assert client_a.post(url, data=payload).status_code == 404


def test_assetclassification_security_idor_spec_template_delete_post_returns_404(client_a, spec_template_b):
    """Tenant A admin client attempting to delete Tenant B specification template returns 404."""
    url = reverse("assets:asset_specification_template_delete", args=[spec_template_b.pk])
    response = client_a.post(url)
    assert response.status_code == 404
    assert AssetSpecificationTemplate.objects.filter(pk=spec_template_b.pk).exists()


def test_assetclassification_security_idor_reverse_tenant_b_accessing_tenant_a_returns_404(
    client_b, category_root_a, asset_model_a, criticality_assessment_a, spec_template_a
):
    """Tenant B admin client accessing Tenant A records returns 404 across detail, edit, delete, and approve."""
    # Category
    assert client_b.get(reverse("assets:asset_category_detail", args=[category_root_a.pk])).status_code == 404
    assert client_b.get(reverse("assets:asset_category_edit", args=[category_root_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_category_delete", args=[category_root_a.pk])).status_code == 404

    # Model
    assert client_b.get(reverse("assets:asset_model_detail", args=[asset_model_a.pk])).status_code == 404
    assert client_b.get(reverse("assets:asset_model_edit", args=[asset_model_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_model_delete", args=[asset_model_a.pk])).status_code == 404

    # Criticality Assessment
    assert client_b.get(reverse("assets:asset_criticality_assessment_detail", args=[criticality_assessment_a.pk])).status_code == 404
    assert client_b.get(reverse("assets:asset_criticality_assessment_edit", args=[criticality_assessment_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_criticality_assessment_delete", args=[criticality_assessment_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_criticality_assessment_approve", args=[criticality_assessment_a.pk])).status_code == 404

    # Specification Template
    assert client_b.get(reverse("assets:asset_specification_template_detail", args=[spec_template_a.pk])).status_code == 404
    assert client_b.get(reverse("assets:asset_specification_template_edit", args=[spec_template_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_specification_template_delete", args=[spec_template_a.pk])).status_code == 404


def test_assetclassification_security_tenant_isolation_list_views(
    client_a,
    category_root_a,
    category_root_b,
    asset_model_a,
    asset_model_b,
    criticality_assessment_a,
    criticality_assessment_b,
    spec_template_a,
    spec_template_b,
):
    """List views for Tenant A contain only Tenant A records and never leak Tenant B records."""
    # Category list
    resp_cat = client_a.get(reverse("assets:asset_category_list"))
    assert resp_cat.status_code == 200
    cat_ids = [c.pk for c in resp_cat.context["categories"]]
    assert category_root_a.pk in cat_ids
    assert category_root_b.pk not in cat_ids
    content_cat = resp_cat.content.decode()
    assert category_root_a.code in content_cat
    assert category_root_b.code not in content_cat

    # Model list
    resp_mod = client_a.get(reverse("assets:asset_model_list"))
    assert resp_mod.status_code == 200
    mod_ids = [m.pk for m in resp_mod.context["models"]]
    assert asset_model_a.pk in mod_ids
    assert asset_model_b.pk not in mod_ids
    content_mod = resp_mod.content.decode()
    assert asset_model_a.model_number in content_mod
    assert asset_model_b.model_number not in content_mod

    # Criticality list
    resp_crit = client_a.get(reverse("assets:asset_criticality_assessment_list"))
    assert resp_crit.status_code == 200
    crit_ids = [a.pk for a in resp_crit.context["assessments"]]
    assert criticality_assessment_a.pk in crit_ids
    assert criticality_assessment_b.pk not in crit_ids
    content_crit = resp_crit.content.decode()
    assert criticality_assessment_a.title in content_crit
    assert criticality_assessment_b.title not in content_crit

    # Spec Template list
    resp_spec = client_a.get(reverse("assets:asset_specification_template_list"))
    assert resp_spec.status_code == 200
    spec_ids = [s.pk for s in resp_spec.context["templates"]]
    assert spec_template_a.pk in spec_ids
    assert spec_template_b.pk not in spec_ids
    content_spec = resp_spec.content.decode()
    assert spec_template_a.attribute_key in content_spec
    assert spec_template_b.attribute_key not in content_spec


# ==============================================================================
# 2. Tenant Boundary Isolation on Form Inputs (Cross-Tenant FK Injection)
# ==============================================================================


def test_assetclassification_security_fk_injection_category_parent(client_a, category_root_b):
    """Submitting foreign parent category on AssetCategoryForm is rejected."""
    url = reverse("assets:asset_category_create")
    payload = _assetclassification_category_payload(code="CAT-REJECT-PARENT", parent=category_root_b.pk)
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert not resp.context["form"].is_valid()
    assert "parent" in resp.context["form"].errors


def test_assetclassification_security_fk_injection_model_category(client_a, category_root_b):
    """Submitting foreign category on AssetModelForm is rejected."""
    url = reverse("assets:asset_model_create")
    payload = _assetclassification_model_payload(category=category_root_b.pk, model_number="REJ-CAT-01")
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert not resp.context["form"].is_valid()
    assert "category" in resp.context["form"].errors


def test_assetclassification_security_fk_injection_model_manufacturer(client_a, category_root_a, vendor_party_b):
    """Submitting foreign manufacturer party on AssetModelForm is rejected."""
    url = reverse("assets:asset_model_create")
    payload = _assetclassification_model_payload(
        category=category_root_a, model_number="REJ-MFR-01", manufacturer=vendor_party_b.pk
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert not resp.context["form"].is_valid()
    assert "manufacturer" in resp.context["form"].errors


def test_assetclassification_security_fk_injection_criticality_asset(client_a, operational_asset_b, vendor_party_a):
    """Submitting foreign physical asset on AssetCriticalityAssessmentForm is rejected."""
    url = reverse("assets:asset_criticality_assessment_create")
    payload = _assetclassification_criticality_payload(
        asset=operational_asset_b.pk, assessor=vendor_party_a.pk
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert not resp.context["form"].is_valid()
    assert "asset" in resp.context["form"].errors


def test_assetclassification_security_fk_injection_criticality_assessor(client_a, operational_asset_a, vendor_party_b):
    """Submitting foreign assessor party on AssetCriticalityAssessmentForm is rejected."""
    url = reverse("assets:asset_criticality_assessment_create")
    payload = _assetclassification_criticality_payload(
        asset=operational_asset_a.pk, assessor=vendor_party_b.pk
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert not resp.context["form"].is_valid()
    assert "assessor" in resp.context["form"].errors


def test_assetclassification_security_fk_injection_spec_template_category(client_a, category_root_b):
    """Submitting foreign category on AssetSpecificationTemplateForm is rejected."""
    url = reverse("assets:asset_specification_template_create")
    payload = _assetclassification_spec_template_payload(
        attribute_key="rej_sec_cat_attr", category=category_root_b.pk
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert not resp.context["form"].is_valid()
    assert "category" in resp.context["form"].errors


def test_assetclassification_security_fk_injection_spec_template_model(client_a, asset_model_b):
    """Submitting foreign equipment model on AssetSpecificationTemplateForm is rejected."""
    url = reverse("assets:asset_specification_template_create")
    payload = _assetclassification_spec_template_payload(
        attribute_key="rej_sec_mod_attr", model=asset_model_b.pk
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert not resp.context["form"].is_valid()
    assert "model" in resp.context["form"].errors


# ==============================================================================
# 3. Authentication & Authorization Enforcement
# ==============================================================================


def test_assetclassification_security_unauthenticated_requests_redirect(
    client, category_root_a, asset_model_a, criticality_assessment_a, spec_template_a
):
    """Anonymous client accessing any of the 21 classification endpoints is redirected to login."""
    endpoints = [
        # AssetCategory (5)
        ("GET", reverse("assets:asset_category_list")),
        ("GET", reverse("assets:asset_category_create")),
        ("POST", reverse("assets:asset_category_create")),
        ("GET", reverse("assets:asset_category_detail", args=[category_root_a.pk])),
        ("GET", reverse("assets:asset_category_edit", args=[category_root_a.pk])),
        ("POST", reverse("assets:asset_category_edit", args=[category_root_a.pk])),
        ("POST", reverse("assets:asset_category_delete", args=[category_root_a.pk])),
        # AssetModel (5)
        ("GET", reverse("assets:asset_model_list")),
        ("GET", reverse("assets:asset_model_create")),
        ("POST", reverse("assets:asset_model_create")),
        ("GET", reverse("assets:asset_model_detail", args=[asset_model_a.pk])),
        ("GET", reverse("assets:asset_model_edit", args=[asset_model_a.pk])),
        ("POST", reverse("assets:asset_model_edit", args=[asset_model_a.pk])),
        ("POST", reverse("assets:asset_model_delete", args=[asset_model_a.pk])),
        # AssetCriticalityAssessment (6)
        ("GET", reverse("assets:asset_criticality_assessment_list")),
        ("GET", reverse("assets:asset_criticality_assessment_create")),
        ("POST", reverse("assets:asset_criticality_assessment_create")),
        ("GET", reverse("assets:asset_criticality_assessment_detail", args=[criticality_assessment_a.pk])),
        ("GET", reverse("assets:asset_criticality_assessment_edit", args=[criticality_assessment_a.pk])),
        ("POST", reverse("assets:asset_criticality_assessment_edit", args=[criticality_assessment_a.pk])),
        ("POST", reverse("assets:asset_criticality_assessment_delete", args=[criticality_assessment_a.pk])),
        ("POST", reverse("assets:asset_criticality_assessment_approve", args=[criticality_assessment_a.pk])),
        # AssetSpecificationTemplate (5)
        ("GET", reverse("assets:asset_specification_template_list")),
        ("GET", reverse("assets:asset_specification_template_create")),
        ("POST", reverse("assets:asset_specification_template_create")),
        ("GET", reverse("assets:asset_specification_template_detail", args=[spec_template_a.pk])),
        ("GET", reverse("assets:asset_specification_template_edit", args=[spec_template_a.pk])),
        ("POST", reverse("assets:asset_specification_template_edit", args=[spec_template_a.pk])),
        ("POST", reverse("assets:asset_specification_template_delete", args=[spec_template_a.pk])),
    ]

    for method, target_url in endpoints:
        if method == "GET":
            resp = client.get(target_url)
        else:
            resp = client.post(target_url)
        assert resp.status_code == 302, f"Expected 302 redirect for {method} {target_url}, got {resp.status_code}"
        assert "login" in resp.url or "/accounts/login" in resp.url


def test_assetclassification_security_rbac_non_admin_member_blocked_from_delete(
    member_client, category_root_a, asset_model_a, criticality_assessment_a, spec_template_a
):
    """Non-tenant-admin member receives 403 Forbidden on all 4 delete operations."""
    delete_endpoints = [
        reverse("assets:asset_category_delete", args=[category_root_a.pk]),
        reverse("assets:asset_model_delete", args=[asset_model_a.pk]),
        reverse("assets:asset_criticality_assessment_delete", args=[criticality_assessment_a.pk]),
        reverse("assets:asset_specification_template_delete", args=[spec_template_a.pk]),
    ]
    for url in delete_endpoints:
        resp = member_client.post(url)
        assert resp.status_code == 403, f"Expected 403 for non-admin on {url}, got {resp.status_code}"


def test_assetclassification_security_rbac_non_admin_member_blocked_from_approve(
    member_client, criticality_assessment_a
):
    """Non-tenant-admin member receives 403 Forbidden on criticality approval."""
    url = reverse("assets:asset_criticality_assessment_approve", args=[criticality_assessment_a.pk])
    resp = member_client.post(url)
    assert resp.status_code == 403
    criticality_assessment_a.refresh_from_db()
    assert criticality_assessment_a.assessment_status == "draft"


def test_assetclassification_security_http_methods_get_on_require_post_endpoints_returns_405(
    client_a, category_root_a, asset_model_a, criticality_assessment_a, spec_template_a
):
    """Sending GET to state-changing endpoints protected by @require_POST returns 405 Method Not Allowed."""
    endpoints = [
        reverse("assets:asset_category_delete", args=[category_root_a.pk]),
        reverse("assets:asset_model_delete", args=[asset_model_a.pk]),
        reverse("assets:asset_criticality_assessment_delete", args=[criticality_assessment_a.pk]),
        reverse("assets:asset_criticality_assessment_approve", args=[criticality_assessment_a.pk]),
        reverse("assets:asset_specification_template_delete", args=[spec_template_a.pk]),
    ]
    for url in endpoints:
        resp = client_a.get(url)
        assert resp.status_code == 405, f"Expected 405 for GET on {url}, got {resp.status_code}"


# ==============================================================================
# 4. Mass-Assignment & Tamper Resistance
# ==============================================================================


def test_assetclassification_security_mass_assignment_criticality_create(
    client_a, tenant_a, tenant_b, operational_asset_a, vendor_party_a, admin_user
):
    """Injected tenant, number, score, tier, status, approver fields are ignored on criticality create."""
    url = reverse("assets:asset_criticality_assessment_create")
    malicious_payload = _assetclassification_criticality_payload(
        asset=operational_asset_a,
        assessor=vendor_party_a,
        title="Tamper Assessment Create",
        safety_impact=1,
        environmental_impact=1,
        operational_downtime_impact=1,
        financial_impact=1,
        regulatory_compliance_impact=1,
        is_single_point_of_failure=False,
        # Injected view/system controlled fields
        tenant=tenant_b.pk,
        number="CRIT-HACKED-999",
        composite_score=999,
        abc_rating="A",
        assessment_status="approved",
        approved_by=admin_user.pk,
        approved_at="2026-01-01T00:00:00Z",
    )
    resp = client_a.post(url, data=malicious_payload)
    assert resp.status_code == 302

    created = AssetCriticalityAssessment.objects.filter(
        tenant=tenant_a, title="Tamper Assessment Create"
    ).first()
    assert created is not None
    assert created.tenant == tenant_a  # Injected tenant_b ignored
    assert created.number != "CRIT-HACKED-999"  # Injected number ignored
    assert created.number.startswith("ACRT-")
    assert created.composite_score == 5  # Server computed 1+1+1+1+1=5
    assert created.abc_rating == "C"  # Score 5 is Tier C, not injected 'A'
    assert created.assessment_status == "draft"  # Injected 'approved' ignored
    assert created.approved_by is None
    assert created.approved_at is None


def test_assetclassification_security_mass_assignment_criticality_edit(
    client_a, tenant_a, tenant_b, criticality_assessment_a, admin_user
):
    """Injected tenant, number, score, tier, status, approver fields are ignored on criticality edit."""
    url = reverse("assets:asset_criticality_assessment_edit", args=[criticality_assessment_a.pk])
    original_number = criticality_assessment_a.number

    malicious_payload = _assetclassification_criticality_payload(
        asset=criticality_assessment_a.asset,
        assessor=criticality_assessment_a.assessor,
        title="Legit Updated Title",
        safety_impact=2,
        environmental_impact=2,
        operational_downtime_impact=2,
        financial_impact=2,
        regulatory_compliance_impact=2,
        is_single_point_of_failure=False,
        # Injected overrides
        tenant=tenant_b.pk,
        number="CRIT-OVERWRITE-777",
        composite_score=500,
        abc_rating="A",
        assessment_status="approved",
        approved_by=admin_user.pk,
        approved_at="2026-01-01T00:00:00Z",
    )
    resp = client_a.post(url, data=malicious_payload)
    assert resp.status_code == 302

    criticality_assessment_a.refresh_from_db()
    assert criticality_assessment_a.title == "Legit Updated Title"
    assert criticality_assessment_a.tenant == tenant_a
    assert criticality_assessment_a.number == original_number
    assert criticality_assessment_a.composite_score == 10  # Server calculated 2*5 = 10
    assert criticality_assessment_a.abc_rating == "C"  # Score 10 is Tier C
    assert criticality_assessment_a.assessment_status == "draft"
    assert criticality_assessment_a.approved_by is None
    assert criticality_assessment_a.approved_at is None


def test_assetclassification_security_mass_assignment_category_create_and_edit(
    client_a, tenant_a, tenant_b, category_root_a
):
    """Injected tenant or number fields on category create and edit are ignored."""
    # Create
    create_url = reverse("assets:asset_category_create")
    create_payload = _assetclassification_category_payload(
        code="CAT-MASS-01",
        tenant=tenant_b.pk,
        number="NUM-HACKED-01",
    )
    resp_create = client_a.post(create_url, data=create_payload)
    assert resp_create.status_code == 302
    created_cat = AssetCategory.objects.filter(tenant=tenant_a, code="CAT-MASS-01").first()
    assert created_cat is not None
    assert created_cat.tenant == tenant_a

    # Edit
    edit_url = reverse("assets:asset_category_edit", args=[category_root_a.pk])
    edit_payload = _assetclassification_category_payload(
        code=category_root_a.code,
        name="Category Updated Legit",
        tenant=tenant_b.pk,
    )
    resp_edit = client_a.post(edit_url, data=edit_payload)
    assert resp_edit.status_code == 302
    category_root_a.refresh_from_db()
    assert category_root_a.tenant == tenant_a
    assert category_root_a.name == "Category Updated Legit"


def test_assetclassification_security_mass_assignment_model_create_and_edit(
    client_a, tenant_a, tenant_b, category_root_a, asset_model_a
):
    """Injected tenant or number fields on model create and edit are ignored."""
    # Create
    create_url = reverse("assets:asset_model_create")
    create_payload = _assetclassification_model_payload(
        category=category_root_a,
        model_number="MOD-MASS-01",
        tenant=tenant_b.pk,
        number="NUM-MOD-HACK",
    )
    resp_create = client_a.post(create_url, data=create_payload)
    assert resp_create.status_code == 302
    created_mod = AssetModel.objects.filter(tenant=tenant_a, model_number="MOD-MASS-01").first()
    assert created_mod is not None
    assert created_mod.tenant == tenant_a

    # Edit
    edit_url = reverse("assets:asset_model_edit", args=[asset_model_a.pk])
    edit_payload = _assetclassification_model_payload(
        category=category_root_a,
        model_number=asset_model_a.model_number,
        name="Model Legit Updated",
        tenant=tenant_b.pk,
    )
    resp_edit = client_a.post(edit_url, data=edit_payload)
    assert resp_edit.status_code == 302
    asset_model_a.refresh_from_db()
    assert asset_model_a.tenant == tenant_a
    assert asset_model_a.name == "Model Legit Updated"


def test_assetclassification_security_mass_assignment_spec_template_create_and_edit(
    client_a, tenant_a, tenant_b, category_root_a, spec_template_a
):
    """Injected tenant or number fields on specification template create and edit are ignored."""
    # Create
    create_url = reverse("assets:asset_specification_template_create")
    create_payload = _assetclassification_spec_template_payload(
        attribute_key="spec_mass_01",
        category=category_root_a.pk,
        tenant=tenant_b.pk,
        number="NUM-SPEC-HACK",
    )
    resp_create = client_a.post(create_url, data=create_payload)
    assert resp_create.status_code == 302
    created_spec = AssetSpecificationTemplate.objects.filter(tenant=tenant_a, attribute_key="spec_mass_01").first()
    assert created_spec is not None
    assert created_spec.tenant == tenant_a

    # Edit
    edit_url = reverse("assets:asset_specification_template_edit", args=[spec_template_a.pk])
    edit_payload = _assetclassification_spec_template_payload(
        attribute_key=spec_template_a.attribute_key,
        category=category_root_a.pk,
        display_name="Spec Legit Updated",
        tenant=tenant_b.pk,
    )
    resp_edit = client_a.post(edit_url, data=edit_payload)
    assert resp_edit.status_code == 302
    spec_template_a.refresh_from_db()
    assert spec_template_a.tenant == tenant_a
    assert spec_template_a.display_name == "Spec Legit Updated"


# ==============================================================================
# 5. Status Guard Compliance
# ==============================================================================


def test_assetclassification_security_status_guard_edit_approved_blocked(
    client_a, criticality_assessment_a, operational_asset_a, vendor_party_a
):
    """Direct POST to edit an approved criticality assessment is blocked with an error redirect."""
    criticality_assessment_a.assessment_status = "approved"
    criticality_assessment_a.save()

    url = reverse("assets:asset_criticality_assessment_edit", args=[criticality_assessment_a.pk])
    payload = _assetclassification_criticality_payload(
        asset=operational_asset_a, assessor=vendor_party_a, title="Tampered Approved Title"
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_criticality_assessment_detail", args=[criticality_assessment_a.pk])

    msgs = _assetclassification_get_flash_messages(resp)
    assert any("cannot be edited" in m for m in msgs)

    criticality_assessment_a.refresh_from_db()
    assert criticality_assessment_a.title != "Tampered Approved Title"


def test_assetclassification_security_status_guard_edit_superseded_blocked(
    client_a, criticality_assessment_a, operational_asset_a, vendor_party_a
):
    """Direct POST to edit a superseded criticality assessment is blocked with an error redirect."""
    criticality_assessment_a.assessment_status = "superseded"
    criticality_assessment_a.save()

    url = reverse("assets:asset_criticality_assessment_edit", args=[criticality_assessment_a.pk])
    payload = _assetclassification_criticality_payload(
        asset=operational_asset_a, assessor=vendor_party_a, title="Tampered Superseded Title"
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_criticality_assessment_detail", args=[criticality_assessment_a.pk])

    msgs = _assetclassification_get_flash_messages(resp)
    assert any("cannot be edited" in m for m in msgs)


def test_assetclassification_security_status_guard_delete_approved_blocked(client_a, criticality_assessment_a):
    """Direct POST to delete an approved assessment is blocked with an error redirect."""
    criticality_assessment_a.assessment_status = "approved"
    criticality_assessment_a.save()

    url = reverse("assets:asset_criticality_assessment_delete", args=[criticality_assessment_a.pk])
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_criticality_assessment_detail", args=[criticality_assessment_a.pk])

    msgs = _assetclassification_get_flash_messages(resp)
    assert any("cannot be deleted" in m for m in msgs)
    assert AssetCriticalityAssessment.objects.filter(pk=criticality_assessment_a.pk).exists()


def test_assetclassification_security_status_guard_delete_superseded_blocked(client_a, criticality_assessment_a):
    """Direct POST to delete a superseded assessment is blocked with an error redirect."""
    criticality_assessment_a.assessment_status = "superseded"
    criticality_assessment_a.save()

    url = reverse("assets:asset_criticality_assessment_delete", args=[criticality_assessment_a.pk])
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_criticality_assessment_detail", args=[criticality_assessment_a.pk])

    msgs = _assetclassification_get_flash_messages(resp)
    assert any("cannot be deleted" in m for m in msgs)
    assert AssetCriticalityAssessment.objects.filter(pk=criticality_assessment_a.pk).exists()


def test_assetclassification_security_status_guard_approve_already_approved_blocked(client_a, criticality_assessment_a):
    """Direct POST to approve an already approved assessment returns a warning redirect."""
    criticality_assessment_a.assessment_status = "approved"
    criticality_assessment_a.save()

    url = reverse("assets:asset_criticality_assessment_approve", args=[criticality_assessment_a.pk])
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_criticality_assessment_detail", args=[criticality_assessment_a.pk])

    msgs = _assetclassification_get_flash_messages(resp)
    assert any("cannot be approved" in m for m in msgs)


def test_assetclassification_security_status_guard_approve_superseded_blocked(client_a, criticality_assessment_a):
    """Direct POST to approve a superseded assessment returns a warning redirect."""
    criticality_assessment_a.assessment_status = "superseded"
    criticality_assessment_a.save()

    url = reverse("assets:asset_criticality_assessment_approve", args=[criticality_assessment_a.pk])
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_criticality_assessment_detail", args=[criticality_assessment_a.pk])

    msgs = _assetclassification_get_flash_messages(resp)
    assert any("cannot be approved" in m for m in msgs)


# ==============================================================================
# 6. Audit Log Generation
# ==============================================================================


def test_assetclassification_security_audit_log_category_create_update_delete(client_a, tenant_a, admin_user):
    """AuditLog rows are generated for category create, update, and delete with tenant=request.tenant."""
    # 1. Create
    create_url = reverse("assets:asset_category_create")
    payload = _assetclassification_category_payload(code="AUD-CAT-01", name="Audit Category Test")
    resp_create = client_a.post(create_url, data=payload)
    assert resp_create.status_code == 302
    cat = AssetCategory.objects.get(tenant=tenant_a, code="AUD-CAT-01")

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=str(cat.pk),
    ).exists()

    # 2. Update
    edit_url = reverse("assets:asset_category_edit", args=[cat.pk])
    payload["name"] = "Audit Category Updated"
    resp_edit = client_a.post(edit_url, data=payload)
    assert resp_edit.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=str(cat.pk),
    ).exists()

    # 3. Delete
    delete_url = reverse("assets:asset_category_delete", args=[cat.pk])
    resp_delete = client_a.post(delete_url)
    assert resp_delete.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
        object_id=str(cat.pk),
    ).exists()


def test_assetclassification_security_audit_log_model_create_update_delete(
    client_a, tenant_a, admin_user, category_root_a
):
    """AuditLog rows are generated for model create, update, and delete with tenant=request.tenant."""
    # 1. Create
    create_url = reverse("assets:asset_model_create")
    payload = _assetclassification_model_payload(
        category=category_root_a, model_number="AUD-MOD-01", name="Audit Model Test"
    )
    resp_create = client_a.post(create_url, data=payload)
    assert resp_create.status_code == 302
    model = AssetModel.objects.get(tenant=tenant_a, model_number="AUD-MOD-01")

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=str(model.pk),
    ).exists()

    # 2. Update
    edit_url = reverse("assets:asset_model_edit", args=[model.pk])
    payload["name"] = "Audit Model Updated"
    resp_edit = client_a.post(edit_url, data=payload)
    assert resp_edit.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=str(model.pk),
    ).exists()

    # 3. Delete
    delete_url = reverse("assets:asset_model_delete", args=[model.pk])
    resp_delete = client_a.post(delete_url)
    assert resp_delete.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
        object_id=str(model.pk),
    ).exists()


def test_assetclassification_security_audit_log_criticality_create_update_delete_and_approve(
    client_a, tenant_a, admin_user, operational_asset_a, vendor_party_a
):
    """AuditLog rows are generated for criticality create, update, approve, and delete operations."""
    # 1. Create
    create_url = reverse("assets:asset_criticality_assessment_create")
    payload = _assetclassification_criticality_payload(
        asset=operational_asset_a, assessor=vendor_party_a, title="Audit Criticality Test"
    )
    resp_create = client_a.post(create_url, data=payload)
    assert resp_create.status_code == 302
    crit = AssetCriticalityAssessment.objects.get(tenant=tenant_a, title="Audit Criticality Test")

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=str(crit.pk),
    ).exists()

    # 2. Update
    edit_url = reverse("assets:asset_criticality_assessment_edit", args=[crit.pk])
    payload["title"] = "Audit Criticality Updated"
    resp_edit = client_a.post(edit_url, data=payload)
    assert resp_edit.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=str(crit.pk),
    ).exists()

    # 3. Approve
    approve_url = reverse("assets:asset_criticality_assessment_approve", args=[crit.pk])
    resp_approve = client_a.post(approve_url)
    assert resp_approve.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="approve",
        object_id=str(crit.pk),
    ).exists()

    # 4. For delete, create another draft assessment
    payload_delete = _assetclassification_criticality_payload(
        asset=operational_asset_a, assessor=vendor_party_a, title="Audit Criticality For Delete"
    )
    client_a.post(create_url, data=payload_delete)
    crit_to_delete = AssetCriticalityAssessment.objects.get(tenant=tenant_a, title="Audit Criticality For Delete")

    delete_url = reverse("assets:asset_criticality_assessment_delete", args=[crit_to_delete.pk])
    resp_delete = client_a.post(delete_url)
    assert resp_delete.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
        object_id=str(crit_to_delete.pk),
    ).exists()


def test_assetclassification_security_audit_log_spec_template_create_update_delete(
    client_a, tenant_a, admin_user, category_root_a
):
    """AuditLog rows are generated for specification template create, update, and delete."""
    # 1. Create
    create_url = reverse("assets:asset_specification_template_create")
    payload = _assetclassification_spec_template_payload(
        attribute_key="aud_spec_01",
        category=category_root_a.pk,
        display_name="Audit Spec Test",
    )
    resp_create = client_a.post(create_url, data=payload)
    assert resp_create.status_code == 302
    spec = AssetSpecificationTemplate.objects.get(tenant=tenant_a, attribute_key="aud_spec_01")

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=str(spec.pk),
    ).exists()

    # 2. Update
    edit_url = reverse("assets:asset_specification_template_edit", args=[spec.pk])
    payload["display_name"] = "Audit Spec Updated"
    resp_edit = client_a.post(edit_url, data=payload)
    assert resp_edit.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=str(spec.pk),
    ).exists()

    # 3. Delete
    delete_url = reverse("assets:asset_specification_template_delete", args=[spec.pk])
    resp_delete = client_a.post(delete_url)
    assert resp_delete.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
        object_id=str(spec.pk),
    ).exists()
