"""Security, multi-tenant isolation, authorization, IDOR defense, adversarial chaos,
and state tampering test suite for Sub-module 11.8: Warranty & Insurance Management.

Covers all 34 views across the 4 entities:
1. Multi-Tenant IDOR Protection (assert 404 on Foreign Tenant Records across detail, edit, delete, and actions)
2. Reverse IDOR (Tenant B client accessing Tenant A records returns 404)
3. List Isolation (assert zero cross-tenant contamination in list views)
4. Cross-Tenant Foreign Key Injection Defenses (reject_foreign across all foreign keys in forms)
5. Authorization & Role-Based Access Control:
   - Unauthenticated 302 login redirects for all 34 endpoints
   - Tenant Admin Gates (@tenant_admin_required vs non-admin member 403 on deletes and privileged actions)
   - Operational Member Permissions (standard users can perform operational workflow transitions)
6. Adversarial Numeric Input Hardening (Lesson L35: NaN, Infinity, -Infinity, negative values, and astronomical precision)
7. State Tampering & Workflow Guard Defenses:
   - Tampering with settled/finalized claims (settled_closed, settled_paid, rejected, denied)
   - Resurrecting voided warranty or cancelled policy via renewal action
   - Mass Assignment Prevention (tenant, number, status overrides in create/edit POST payloads are strictly ignored)
8. Audit Log Generation (assert immutable AuditLog rows on CRUD and workflow transitions)
9. HTTP Method Guards (require_POST on state-mutating actions rejects GET with 405)
"""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models import FixedAsset
from apps.assets.models import (
    AssetCategory,
    AssetInsuranceClaim,
    AssetInsurancePolicy,
    AssetWarranty,
    AssetWarrantyClaim,
)
from apps.core.models import AuditLog, Party, PartyRole
from apps.scm.models import Asset as OperationalAsset

User = get_user_model()
pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Payload Factories (prefixed with _assetwarrantyinsurance_)
# ==============================================================================

def _assetwarrantyinsurance_ensure_vendor_role(party):
    """Ensure party has an active vendor role to satisfy vendor-filtered FK dropdowns."""
    PartyRole.objects.get_or_create(
        tenant=party.tenant,
        party=party,
        role="vendor",
        defaults={"status": "active"},
    )
    return party


def _assetwarrantyinsurance_warranty_payload(currency, warrantor, fixed_asset=None, operational_asset=None, category=None, **overrides):
    """Build a valid POST payload for AssetWarrantyForm."""
    _assetwarrantyinsurance_ensure_vendor_role(warrantor)
    today = timezone.now().date()
    payload = {
        "title": "Industrial Centrifugal Compressor Factory Warranty",
        "warranty_certificate_number": "CERT-SEC-WARR-2026-001",
        "fixed_asset": str(fixed_asset.pk) if fixed_asset else "",
        "operational_asset": str(operational_asset.pk) if operational_asset else "",
        "asset_category": str(category.pk) if category else "",
        "warrantor_party": str(warrantor.pk),
        "currency": str(currency.pk),
        "warranty_type": "oem_standard",
        "coverage_scope": "comprehensive",
        "start_date": today.strftime("%Y-%m-%d"),
        "end_date": (today + timedelta(days=365)).strftime("%Y-%m-%d"),
        "meter_type": "hours",
        "meter_limit": "5000",
        "parts_coverage_percent": "100",
        "labor_coverage_percent": "100",
        "travel_dispatch_covered": True,
        "deductible_amount": "250.00",
        "contract_purchase_price": "1500.00",
        "terms_and_conditions": "Full parts and labor for manufacturing defects under normal operation.",
    }
    payload.update(overrides)
    return payload


def _assetwarrantyinsurance_warranty_claim_payload(currency, warranty, fixed_asset=None, operational_asset=None, **overrides):
    """Build a valid POST payload for AssetWarrantyClaimForm."""
    today = timezone.now().date()
    payload = {
        "title": "Impeller Shaft Fatigue Fracture Claim",
        "warranty": str(warranty.pk),
        "fixed_asset": str(fixed_asset.pk) if fixed_asset else "",
        "operational_asset": str(operational_asset.pk) if operational_asset else "",
        "incident_date": today.strftime("%Y-%m-%d"),
        "operating_meter_at_failure": "1420",
        "defect_description": "Fatigue crack detected on stage 2 impeller shaft assembly.",
        "warrantor_claim_reference": "OEM-RMA-84912",
        "currency": str(currency.pk),
        "claimed_amount": "3200.00",
        "deductible_applied": "250.00",
        "resolution_type": "cash_reimbursement",
        "part_return_status": "return_required_pending",
        "rma_tracking_number": "1Z9999999999999999",
        "settlement_notes": "Shipped to OEM regional service depot for non-destructive inspection.",
    }
    payload.update(overrides)
    return payload


def _assetwarrantyinsurance_insurance_policy_payload(currency, underwriter, broker=None, fixed_asset=None, operational_asset=None, category=None, **overrides):
    """Build a valid POST payload for AssetInsurancePolicyForm."""
    _assetwarrantyinsurance_ensure_vendor_role(underwriter)
    if broker:
        _assetwarrantyinsurance_ensure_vendor_role(broker)
    today = timezone.now().date()
    payload = {
        "policy_number": "POL-SEC-2026-MACH-01",
        "title": "Machinery Breakdown & Boiler Explosion Policy",
        "policy_type": "machinery_breakdown",
        "valuation_basis": "replacement_cost_value",
        "underwriter_party": str(underwriter.pk),
        "broker_party": str(broker.pk) if broker else "",
        "fixed_asset": str(fixed_asset.pk) if fixed_asset else "",
        "operational_asset": str(operational_asset.pk) if operational_asset else "",
        "asset_category": str(category.pk) if category else "",
        "currency": str(currency.pk),
        "effective_date": today.strftime("%Y-%m-%d"),
        "expiration_date": (today + timedelta(days=365)).strftime("%Y-%m-%d"),
        "total_insured_value": "350000.00",
        "deductible_retention": "5000.00",
        "coinsurance_percentage": "100",
        "annual_premium": "12500.00",
        "premium_frequency": "annual",
        "coverage_terms": "Sudden and accidental electrical and mechanical breakdown schedule.",
    }
    payload.update(overrides)
    return payload


def _assetwarrantyinsurance_insurance_claim_payload(currency, policy, fixed_asset=None, operational_asset=None, adjuster=None, **overrides):
    """Build a valid POST payload for AssetInsuranceClaimForm."""
    if adjuster:
        _assetwarrantyinsurance_ensure_vendor_role(adjuster)
    today = timezone.now().date()
    payload = {
        "title": "Main Transformer Stator Flashover Claim",
        "policy": str(policy.pk),
        "fixed_asset": str(fixed_asset.pk) if fixed_asset else "",
        "operational_asset": str(operational_asset.pk) if operational_asset else "",
        "adjuster_party": str(adjuster.pk) if adjuster else "",
        "incident_date": today.strftime("%Y-%m-%d"),
        "peril_type": "electrical_arcing_surge",
        "incident_description": "Severe utility voltage transient punctured winding insulation causing arcing.",
        "incident_location": "Building A - Switchgear Vault",
        "carrier_claim_number": "CLM-TRV-2026-00491",
        "adjuster_name": "Sarah Jenkins (Crawford & Co)",
        "currency": str(currency.pk),
        "claimed_loss_amount": "28000.00",
        "deductible_applied": "5000.00",
        "salvage_recovery_amount": "1200.00",
        "settlement_method": "direct_indemnity_check",
        "settlement_notes": "Forensic electrical engineer inspection concluded utility grid transient surge.",
    }
    payload.update(overrides)
    return payload


# ==============================================================================
# 1. Multi-Tenant IDOR Protection (404 on Foreign Tenant Records)
# ==============================================================================

def test_assetwarrantyinsurance_idor_warranty_detail_returns_404(client_a, warranty_b):
    """Tenant A client requesting Tenant B warranty detail returns 404."""
    url = reverse("assets:asset_warranty_detail", args=[warranty_b.pk])
    assert client_a.get(url).status_code == 404


def test_assetwarrantyinsurance_idor_warranty_edit_returns_404(client_a, warranty_b):
    """Tenant A client requesting Tenant B warranty edit returns 404 on GET and POST."""
    url = reverse("assets:asset_warranty_edit", args=[warranty_b.pk])
    assert client_a.get(url).status_code == 404
    assert client_a.post(url, data={"title": "Hacked Title"}).status_code == 404


def test_assetwarrantyinsurance_idor_warranty_delete_returns_404(client_a, warranty_b):
    """Tenant A admin client attempting to delete Tenant B warranty returns 404."""
    url = reverse("assets:asset_warranty_delete", args=[warranty_b.pk])
    response = client_a.post(url)
    assert response.status_code == 404
    assert AssetWarranty.objects.filter(pk=warranty_b.pk).exists()


def test_assetwarrantyinsurance_idor_warranty_actions_return_404(client_a, warranty_b):
    """Tenant A client calling action endpoints on Tenant B warranty returns 404."""
    actions = [
        "assets:asset_warranty_activate",
        "assets:asset_warranty_renew",
        "assets:asset_warranty_void",
    ]
    for action_name in actions:
        url = reverse(action_name, args=[warranty_b.pk])
        resp = client_a.post(url)
        assert resp.status_code == 404, f"Action {action_name} failed to return 404 for cross-tenant IDOR"


def test_assetwarrantyinsurance_idor_warranty_claim_detail_returns_404(client_a, warranty_claim_b):
    """Tenant A client requesting Tenant B warranty claim detail returns 404."""
    url = reverse("assets:asset_warranty_claim_detail", args=[warranty_claim_b.pk])
    assert client_a.get(url).status_code == 404


def test_assetwarrantyinsurance_idor_warranty_claim_edit_returns_404(client_a, warranty_claim_b):
    """Tenant A client requesting Tenant B warranty claim edit returns 404 on GET and POST."""
    url = reverse("assets:asset_warranty_claim_edit", args=[warranty_claim_b.pk])
    assert client_a.get(url).status_code == 404
    assert client_a.post(url, data={"title": "Hacked Claim Title"}).status_code == 404


def test_assetwarrantyinsurance_idor_warranty_claim_delete_returns_404(client_a, warranty_claim_b):
    """Tenant A admin client attempting to delete Tenant B warranty claim returns 404."""
    url = reverse("assets:asset_warranty_claim_delete", args=[warranty_claim_b.pk])
    response = client_a.post(url)
    assert response.status_code == 404
    assert AssetWarrantyClaim.objects.filter(pk=warranty_claim_b.pk).exists()


def test_assetwarrantyinsurance_idor_warranty_claim_actions_return_404(client_a, warranty_claim_b):
    """Tenant A client calling action endpoints on Tenant B warranty claim returns 404."""
    actions = [
        "assets:asset_warranty_claim_submit",
        "assets:asset_warranty_claim_review",
        "assets:asset_warranty_claim_settle",
        "assets:asset_warranty_claim_reject",
    ]
    for action_name in actions:
        url = reverse(action_name, args=[warranty_claim_b.pk])
        resp = client_a.post(url)
        assert resp.status_code == 404, f"Action {action_name} failed to return 404 for cross-tenant IDOR"


def test_assetwarrantyinsurance_idor_insurance_policy_detail_returns_404(client_a, insurance_policy_b):
    """Tenant A client requesting Tenant B insurance policy detail returns 404."""
    url = reverse("assets:asset_insurance_policy_detail", args=[insurance_policy_b.pk])
    assert client_a.get(url).status_code == 404


def test_assetwarrantyinsurance_idor_insurance_policy_edit_returns_404(client_a, insurance_policy_b):
    """Tenant A client requesting Tenant B insurance policy edit returns 404 on GET and POST."""
    url = reverse("assets:asset_insurance_policy_edit", args=[insurance_policy_b.pk])
    assert client_a.get(url).status_code == 404
    assert client_a.post(url, data={"title": "Hacked Policy Title"}).status_code == 404


def test_assetwarrantyinsurance_idor_insurance_policy_delete_returns_404(client_a, insurance_policy_b):
    """Tenant A admin client attempting to delete Tenant B insurance policy returns 404."""
    url = reverse("assets:asset_insurance_policy_delete", args=[insurance_policy_b.pk])
    response = client_a.post(url)
    assert response.status_code == 404
    assert AssetInsurancePolicy.objects.filter(pk=insurance_policy_b.pk).exists()


def test_assetwarrantyinsurance_idor_insurance_policy_actions_return_404(client_a, insurance_policy_b):
    """Tenant A client calling action endpoints on Tenant B insurance policy returns 404."""
    actions = [
        "assets:asset_insurance_policy_activate",
        "assets:asset_insurance_policy_renew",
        "assets:asset_insurance_policy_cancel",
    ]
    for action_name in actions:
        url = reverse(action_name, args=[insurance_policy_b.pk])
        resp = client_a.post(url)
        assert resp.status_code == 404, f"Action {action_name} failed to return 404 for cross-tenant IDOR"


def test_assetwarrantyinsurance_idor_insurance_claim_detail_returns_404(client_a, insurance_claim_b):
    """Tenant A client requesting Tenant B insurance claim detail returns 404."""
    url = reverse("assets:asset_insurance_claim_detail", args=[insurance_claim_b.pk])
    assert client_a.get(url).status_code == 404


def test_assetwarrantyinsurance_idor_insurance_claim_edit_returns_404(client_a, insurance_claim_b):
    """Tenant A client requesting Tenant B insurance claim edit returns 404 on GET and POST."""
    url = reverse("assets:asset_insurance_claim_edit", args=[insurance_claim_b.pk])
    assert client_a.get(url).status_code == 404
    assert client_a.post(url, data={"title": "Hacked Insurance Claim Title"}).status_code == 404


def test_assetwarrantyinsurance_idor_insurance_claim_delete_returns_404(client_a, insurance_claim_b):
    """Tenant A admin client attempting to delete Tenant B insurance claim returns 404."""
    url = reverse("assets:asset_insurance_claim_delete", args=[insurance_claim_b.pk])
    response = client_a.post(url)
    assert response.status_code == 404
    assert AssetInsuranceClaim.objects.filter(pk=insurance_claim_b.pk).exists()


def test_assetwarrantyinsurance_idor_insurance_claim_actions_return_404(client_a, insurance_claim_b):
    """Tenant A client calling action endpoints on Tenant B insurance claim returns 404."""
    actions = [
        "assets:asset_insurance_claim_assign_adjuster",
        "assets:asset_insurance_claim_file_proof",
        "assets:asset_insurance_claim_settle",
        "assets:asset_insurance_claim_deny",
    ]
    for action_name in actions:
        url = reverse(action_name, args=[insurance_claim_b.pk])
        resp = client_a.post(url)
        assert resp.status_code == 404, f"Action {action_name} failed to return 404 for cross-tenant IDOR"


def test_assetwarrantyinsurance_reverse_idor(client_b, warranty_a, warranty_claim_a, insurance_policy_a, insurance_claim_a):
    """Tenant B user accessing Tenant A records returns 404 across detail, edit, delete, and actions."""
    # 1. AssetWarranty
    assert client_b.get(reverse("assets:asset_warranty_detail", args=[warranty_a.pk])).status_code == 404
    assert client_b.get(reverse("assets:asset_warranty_edit", args=[warranty_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_warranty_delete", args=[warranty_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_warranty_activate", args=[warranty_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_warranty_renew", args=[warranty_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_warranty_void", args=[warranty_a.pk])).status_code == 404

    # 2. AssetWarrantyClaim
    assert client_b.get(reverse("assets:asset_warranty_claim_detail", args=[warranty_claim_a.pk])).status_code == 404
    assert client_b.get(reverse("assets:asset_warranty_claim_edit", args=[warranty_claim_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_warranty_claim_delete", args=[warranty_claim_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_warranty_claim_submit", args=[warranty_claim_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_warranty_claim_review", args=[warranty_claim_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_warranty_claim_settle", args=[warranty_claim_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_warranty_claim_reject", args=[warranty_claim_a.pk])).status_code == 404

    # 3. AssetInsurancePolicy
    assert client_b.get(reverse("assets:asset_insurance_policy_detail", args=[insurance_policy_a.pk])).status_code == 404
    assert client_b.get(reverse("assets:asset_insurance_policy_edit", args=[insurance_policy_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_insurance_policy_delete", args=[insurance_policy_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_insurance_policy_activate", args=[insurance_policy_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_insurance_policy_renew", args=[insurance_policy_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_insurance_policy_cancel", args=[insurance_policy_a.pk])).status_code == 404

    # 4. AssetInsuranceClaim
    assert client_b.get(reverse("assets:asset_insurance_claim_detail", args=[insurance_claim_a.pk])).status_code == 404
    assert client_b.get(reverse("assets:asset_insurance_claim_edit", args=[insurance_claim_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_insurance_claim_delete", args=[insurance_claim_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_insurance_claim_assign_adjuster", args=[insurance_claim_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_insurance_claim_file_proof", args=[insurance_claim_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_insurance_claim_settle", args=[insurance_claim_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_insurance_claim_deny", args=[insurance_claim_a.pk])).status_code == 404


def test_assetwarrantyinsurance_list_isolation_warranties(client_a, client_b, warranty_a, warranty_b):
    """asset_warranty_list strictly isolates warranties between tenants."""
    resp_a = client_a.get(reverse("assets:asset_warranty_list"))
    assert resp_a.status_code == 200
    items_a = list(resp_a.context["warranties"])
    assert warranty_a in items_a
    assert warranty_b not in items_a
    assert warranty_b.title not in resp_a.content.decode()

    resp_b = client_b.get(reverse("assets:asset_warranty_list"))
    assert resp_b.status_code == 200
    items_b = list(resp_b.context["warranties"])
    assert warranty_b in items_b
    assert warranty_a not in items_b
    assert warranty_a.title not in resp_b.content.decode()


def test_assetwarrantyinsurance_list_isolation_warranty_claims(client_a, client_b, warranty_claim_a, warranty_claim_b):
    """asset_warranty_claim_list strictly isolates warranty claims between tenants."""
    resp_a = client_a.get(reverse("assets:asset_warranty_claim_list"))
    assert resp_a.status_code == 200
    items_a = list(resp_a.context["warranty_claims"])
    assert warranty_claim_a in items_a
    assert warranty_claim_b not in items_a
    assert warranty_claim_b.title not in resp_a.content.decode()

    resp_b = client_b.get(reverse("assets:asset_warranty_claim_list"))
    assert resp_b.status_code == 200
    items_b = list(resp_b.context["warranty_claims"])
    assert warranty_claim_b in items_b
    assert warranty_claim_a not in items_b
    assert warranty_claim_a.title not in resp_b.content.decode()


def test_assetwarrantyinsurance_list_isolation_insurance_policies(client_a, client_b, insurance_policy_a, insurance_policy_b):
    """asset_insurance_policy_list strictly isolates insurance policies between tenants."""
    resp_a = client_a.get(reverse("assets:asset_insurance_policy_list"))
    assert resp_a.status_code == 200
    items_a = list(resp_a.context["policies"])
    assert insurance_policy_a in items_a
    assert insurance_policy_b not in items_a
    assert insurance_policy_b.title not in resp_a.content.decode()

    resp_b = client_b.get(reverse("assets:asset_insurance_policy_list"))
    assert resp_b.status_code == 200
    items_b = list(resp_b.context["policies"])
    assert insurance_policy_b in items_b
    assert insurance_policy_a not in items_b
    assert insurance_policy_a.title not in resp_b.content.decode()


def test_assetwarrantyinsurance_list_isolation_insurance_claims(client_a, client_b, insurance_claim_a, insurance_claim_b):
    """asset_insurance_claim_list strictly isolates insurance claims between tenants."""
    resp_a = client_a.get(reverse("assets:asset_insurance_claim_list"))
    assert resp_a.status_code == 200
    items_a = list(resp_a.context["insurance_claims"])
    assert insurance_claim_a in items_a
    assert insurance_claim_b not in items_a
    assert insurance_claim_b.title not in resp_a.content.decode()

    resp_b = client_b.get(reverse("assets:asset_insurance_claim_list"))
    assert resp_b.status_code == 200
    items_b = list(resp_b.context["insurance_claims"])
    assert insurance_claim_b in items_b
    assert insurance_claim_a not in items_b
    assert insurance_claim_a.title not in resp_b.content.decode()


# ==============================================================================
# 2. Form Cross-Tenant Injection Defenses (reject_foreign validation)
# ==============================================================================

def test_assetwarrantyinsurance_fk_injection_warranty_fixed_asset_rejected(client_a, currency_usd, vendor_party_a, fixed_asset_b):
    """Attempting to bind Tenant B's FixedAsset in Tenant A warranty fails form validation."""
    url = reverse("assets:asset_warranty_create")
    payload = _assetwarrantyinsurance_warranty_payload(currency_usd, vendor_party_a, fixed_asset=fixed_asset_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "fixed_asset" in response.context["form"].errors


def test_assetwarrantyinsurance_fk_injection_warranty_operational_asset_rejected(client_a, currency_usd, vendor_party_a, operational_asset_b):
    """Attempting to bind Tenant B's OperationalAsset in Tenant A warranty fails form validation."""
    url = reverse("assets:asset_warranty_create")
    payload = _assetwarrantyinsurance_warranty_payload(currency_usd, vendor_party_a, operational_asset=operational_asset_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "operational_asset" in response.context["form"].errors


def test_assetwarrantyinsurance_fk_injection_warranty_category_rejected(client_a, currency_usd, vendor_party_a, category_root_b):
    """Attempting to bind Tenant B's AssetCategory in Tenant A warranty fails form validation."""
    url = reverse("assets:asset_warranty_create")
    payload = _assetwarrantyinsurance_warranty_payload(currency_usd, vendor_party_a, category=category_root_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "asset_category" in response.context["form"].errors


def test_assetwarrantyinsurance_fk_injection_warranty_warrantor_rejected(client_a, currency_usd, vendor_party_b):
    """Attempting to bind Tenant B's Vendor as warrantor in Tenant A warranty fails form validation."""
    url = reverse("assets:asset_warranty_create")
    payload = _assetwarrantyinsurance_warranty_payload(currency_usd, vendor_party_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "warrantor_party" in response.context["form"].errors


def test_assetwarrantyinsurance_fk_injection_warranty_claim_warranty_rejected(client_a, currency_usd, warranty_b):
    """Attempting to bind Tenant B's Warranty in Tenant A warranty claim fails form validation."""
    url = reverse("assets:asset_warranty_claim_create")
    payload = _assetwarrantyinsurance_warranty_claim_payload(currency_usd, warranty=warranty_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "warranty" in response.context["form"].errors


def test_assetwarrantyinsurance_fk_injection_warranty_claim_fixed_asset_rejected(client_a, currency_usd, warranty_a, fixed_asset_b):
    """Attempting to bind Tenant B's FixedAsset in Tenant A warranty claim fails form validation."""
    url = reverse("assets:asset_warranty_claim_create")
    payload = _assetwarrantyinsurance_warranty_claim_payload(currency_usd, warranty_a, fixed_asset=fixed_asset_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "fixed_asset" in response.context["form"].errors


def test_assetwarrantyinsurance_fk_injection_warranty_claim_operational_asset_rejected(client_a, currency_usd, warranty_a, operational_asset_b):
    """Attempting to bind Tenant B's OperationalAsset in Tenant A warranty claim fails form validation."""
    url = reverse("assets:asset_warranty_claim_create")
    payload = _assetwarrantyinsurance_warranty_claim_payload(currency_usd, warranty_a, operational_asset=operational_asset_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "operational_asset" in response.context["form"].errors


def test_assetwarrantyinsurance_fk_injection_insurance_policy_underwriter_rejected(client_a, currency_usd, underwriter_party_b):
    """Attempting to bind Tenant B's Underwriter in Tenant A insurance policy fails form validation."""
    url = reverse("assets:asset_insurance_policy_create")
    payload = _assetwarrantyinsurance_insurance_policy_payload(currency_usd, underwriter=underwriter_party_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "underwriter_party" in response.context["form"].errors


def test_assetwarrantyinsurance_fk_injection_insurance_policy_broker_rejected(client_a, currency_usd, underwriter_party_a, broker_party_b):
    """Attempting to bind Tenant B's Broker in Tenant A insurance policy fails form validation."""
    url = reverse("assets:asset_insurance_policy_create")
    payload = _assetwarrantyinsurance_insurance_policy_payload(currency_usd, underwriter_party_a, broker=broker_party_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "broker_party" in response.context["form"].errors


def test_assetwarrantyinsurance_fk_injection_insurance_policy_fixed_asset_rejected(client_a, currency_usd, underwriter_party_a, fixed_asset_b):
    """Attempting to bind Tenant B's FixedAsset in Tenant A insurance policy fails form validation."""
    url = reverse("assets:asset_insurance_policy_create")
    payload = _assetwarrantyinsurance_insurance_policy_payload(currency_usd, underwriter_party_a, fixed_asset=fixed_asset_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "fixed_asset" in response.context["form"].errors


def test_assetwarrantyinsurance_fk_injection_insurance_policy_operational_asset_rejected(client_a, currency_usd, underwriter_party_a, operational_asset_b):
    """Attempting to bind Tenant B's OperationalAsset in Tenant A insurance policy fails form validation."""
    url = reverse("assets:asset_insurance_policy_create")
    payload = _assetwarrantyinsurance_insurance_policy_payload(currency_usd, underwriter_party_a, operational_asset=operational_asset_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "operational_asset" in response.context["form"].errors


def test_assetwarrantyinsurance_fk_injection_insurance_policy_category_rejected(client_a, currency_usd, underwriter_party_a, category_root_b):
    """Attempting to bind Tenant B's AssetCategory in Tenant A insurance policy fails form validation."""
    url = reverse("assets:asset_insurance_policy_create")
    payload = _assetwarrantyinsurance_insurance_policy_payload(currency_usd, underwriter_party_a, category=category_root_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "asset_category" in response.context["form"].errors


def test_assetwarrantyinsurance_fk_injection_insurance_claim_policy_rejected(client_a, currency_usd, insurance_policy_b):
    """Attempting to bind Tenant B's InsurancePolicy in Tenant A insurance claim fails form validation."""
    url = reverse("assets:asset_insurance_claim_create")
    payload = _assetwarrantyinsurance_insurance_claim_payload(currency_usd, policy=insurance_policy_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "policy" in response.context["form"].errors


def test_assetwarrantyinsurance_fk_injection_insurance_claim_fixed_asset_rejected(client_a, currency_usd, insurance_policy_a, fixed_asset_b):
    """Attempting to bind Tenant B's FixedAsset in Tenant A insurance claim fails form validation."""
    url = reverse("assets:asset_insurance_claim_create")
    payload = _assetwarrantyinsurance_insurance_claim_payload(currency_usd, insurance_policy_a, fixed_asset=fixed_asset_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "fixed_asset" in response.context["form"].errors


def test_assetwarrantyinsurance_fk_injection_insurance_claim_operational_asset_rejected(client_a, currency_usd, insurance_policy_a, operational_asset_b):
    """Attempting to bind Tenant B's OperationalAsset in Tenant A insurance claim fails form validation."""
    url = reverse("assets:asset_insurance_claim_create")
    payload = _assetwarrantyinsurance_insurance_claim_payload(currency_usd, insurance_policy_a, operational_asset=operational_asset_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "operational_asset" in response.context["form"].errors


def test_assetwarrantyinsurance_fk_injection_insurance_claim_adjuster_rejected(client_a, currency_usd, insurance_policy_a, adjuster_party_b):
    """Attempting to bind Tenant B's Adjuster in Tenant A insurance claim fails form validation."""
    url = reverse("assets:asset_insurance_claim_create")
    payload = _assetwarrantyinsurance_insurance_claim_payload(currency_usd, insurance_policy_a, adjuster=adjuster_party_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "adjuster_party" in response.context["form"].errors


# ==============================================================================
# 3. Authorization & Role-Based Access Control (RBAC)
# ==============================================================================

def test_assetwarrantyinsurance_unauthenticated_redirect_to_login(
    client, warranty_a, warranty_claim_a, insurance_policy_a, insurance_claim_a
):
    """Unauthenticated client is redirected to login for all 34 warranty and insurance endpoints."""
    endpoints = [
        # AssetWarranty (8 endpoints)
        reverse("assets:asset_warranty_list"),
        reverse("assets:asset_warranty_create"),
        reverse("assets:asset_warranty_detail", args=[warranty_a.pk]),
        reverse("assets:asset_warranty_edit", args=[warranty_a.pk]),
        reverse("assets:asset_warranty_delete", args=[warranty_a.pk]),
        reverse("assets:asset_warranty_activate", args=[warranty_a.pk]),
        reverse("assets:asset_warranty_renew", args=[warranty_a.pk]),
        reverse("assets:asset_warranty_void", args=[warranty_a.pk]),

        # AssetWarrantyClaim (9 endpoints)
        reverse("assets:asset_warranty_claim_list"),
        reverse("assets:asset_warranty_claim_create"),
        reverse("assets:asset_warranty_claim_detail", args=[warranty_claim_a.pk]),
        reverse("assets:asset_warranty_claim_edit", args=[warranty_claim_a.pk]),
        reverse("assets:asset_warranty_claim_delete", args=[warranty_claim_a.pk]),
        reverse("assets:asset_warranty_claim_submit", args=[warranty_claim_a.pk]),
        reverse("assets:asset_warranty_claim_review", args=[warranty_claim_a.pk]),
        reverse("assets:asset_warranty_claim_settle", args=[warranty_claim_a.pk]),
        reverse("assets:asset_warranty_claim_reject", args=[warranty_claim_a.pk]),

        # AssetInsurancePolicy (8 endpoints)
        reverse("assets:asset_insurance_policy_list"),
        reverse("assets:asset_insurance_policy_create"),
        reverse("assets:asset_insurance_policy_detail", args=[insurance_policy_a.pk]),
        reverse("assets:asset_insurance_policy_edit", args=[insurance_policy_a.pk]),
        reverse("assets:asset_insurance_policy_delete", args=[insurance_policy_a.pk]),
        reverse("assets:asset_insurance_policy_activate", args=[insurance_policy_a.pk]),
        reverse("assets:asset_insurance_policy_renew", args=[insurance_policy_a.pk]),
        reverse("assets:asset_insurance_policy_cancel", args=[insurance_policy_a.pk]),

        # AssetInsuranceClaim (9 endpoints)
        reverse("assets:asset_insurance_claim_list"),
        reverse("assets:asset_insurance_claim_create"),
        reverse("assets:asset_insurance_claim_detail", args=[insurance_claim_a.pk]),
        reverse("assets:asset_insurance_claim_edit", args=[insurance_claim_a.pk]),
        reverse("assets:asset_insurance_claim_delete", args=[insurance_claim_a.pk]),
        reverse("assets:asset_insurance_claim_assign_adjuster", args=[insurance_claim_a.pk]),
        reverse("assets:asset_insurance_claim_file_proof", args=[insurance_claim_a.pk]),
        reverse("assets:asset_insurance_claim_settle", args=[insurance_claim_a.pk]),
        reverse("assets:asset_insurance_claim_deny", args=[insurance_claim_a.pk]),
    ]
    assert len(endpoints) == 34, f"Expected exactly 34 endpoints tested, found {len(endpoints)}"

    for url in endpoints:
        resp_get = client.get(url)
        assert resp_get.status_code == 302, f"Expected 302 login redirect for GET {url}, got {resp_get.status_code}"
        assert "/accounts/login/" in resp_get.url or "login" in resp_get.url

        resp_post = client.post(url, data={})
        assert resp_post.status_code == 302, f"Expected 302 login redirect for POST {url}, got {resp_post.status_code}"


def test_assetwarrantyinsurance_rbac_warranty_delete_admin_only(member_client, client_a, warranty_a):
    """asset_warranty_delete requires tenant admin role; regular member receives 403."""
    url = reverse("assets:asset_warranty_delete", args=[warranty_a.pk])
    # Member attempt blocked
    resp_member = member_client.post(url)
    assert resp_member.status_code == 403
    assert AssetWarranty.objects.filter(pk=warranty_a.pk).exists()

    # Admin attempt succeeds
    resp_admin = client_a.post(url)
    assert resp_admin.status_code == 302
    assert not AssetWarranty.objects.filter(pk=warranty_a.pk).exists()


def test_assetwarrantyinsurance_rbac_warranty_void_admin_only(member_client, client_a, warranty_a):
    """asset_warranty_void requires tenant admin role; regular member receives 403."""
    url = reverse("assets:asset_warranty_void", args=[warranty_a.pk])
    # Member attempt blocked
    resp_member = member_client.post(url)
    assert resp_member.status_code == 403
    warranty_a.refresh_from_db()
    assert warranty_a.status != "voided"

    # Admin attempt succeeds
    resp_admin = client_a.post(url)
    assert resp_admin.status_code == 302
    warranty_a.refresh_from_db()
    assert warranty_a.status == "voided"


def test_assetwarrantyinsurance_rbac_warranty_claim_delete_admin_only(member_client, client_a, warranty_claim_a):
    """asset_warranty_claim_delete requires tenant admin role; regular member receives 403."""
    url = reverse("assets:asset_warranty_claim_delete", args=[warranty_claim_a.pk])
    # Member attempt blocked
    resp_member = member_client.post(url)
    assert resp_member.status_code == 403
    assert AssetWarrantyClaim.objects.filter(pk=warranty_claim_a.pk).exists()

    # Admin attempt succeeds
    resp_admin = client_a.post(url)
    assert resp_admin.status_code == 302
    assert not AssetWarrantyClaim.objects.filter(pk=warranty_claim_a.pk).exists()


def test_assetwarrantyinsurance_rbac_insurance_policy_delete_admin_only(member_client, client_a, insurance_policy_a):
    """asset_insurance_policy_delete requires tenant admin role; regular member receives 403."""
    url = reverse("assets:asset_insurance_policy_delete", args=[insurance_policy_a.pk])
    # Member attempt blocked
    resp_member = member_client.post(url)
    assert resp_member.status_code == 403
    assert AssetInsurancePolicy.objects.filter(pk=insurance_policy_a.pk).exists()

    # Admin attempt succeeds
    resp_admin = client_a.post(url)
    assert resp_admin.status_code == 302
    assert not AssetInsurancePolicy.objects.filter(pk=insurance_policy_a.pk).exists()


def test_assetwarrantyinsurance_rbac_insurance_policy_cancel_admin_only(member_client, client_a, insurance_policy_a):
    """asset_insurance_policy_cancel requires tenant admin role; regular member receives 403."""
    url = reverse("assets:asset_insurance_policy_cancel", args=[insurance_policy_a.pk])
    # Member attempt blocked
    resp_member = member_client.post(url)
    assert resp_member.status_code == 403
    insurance_policy_a.refresh_from_db()
    assert insurance_policy_a.status != "cancelled"

    # Admin attempt succeeds
    resp_admin = client_a.post(url)
    assert resp_admin.status_code == 302
    insurance_policy_a.refresh_from_db()
    assert insurance_policy_a.status == "cancelled"


def test_assetwarrantyinsurance_rbac_insurance_claim_delete_admin_only(member_client, client_a, insurance_claim_a):
    """asset_insurance_claim_delete requires tenant admin role; regular member receives 403."""
    url = reverse("assets:asset_insurance_claim_delete", args=[insurance_claim_a.pk])
    # Member attempt blocked
    resp_member = member_client.post(url)
    assert resp_member.status_code == 403
    assert AssetInsuranceClaim.objects.filter(pk=insurance_claim_a.pk).exists()

    # Admin attempt succeeds
    resp_admin = client_a.post(url)
    assert resp_admin.status_code == 302
    assert not AssetInsuranceClaim.objects.filter(pk=insurance_claim_a.pk).exists()


def test_assetwarrantyinsurance_rbac_member_permitted_warranty_actions(member_client, warranty_a):
    """Non-admin member is permitted to activate draft warranty and renew active warranty."""
    # 1. Activate draft warranty
    warranty_a.status = "draft"
    warranty_a.save(update_fields=["status"])
    url_activate = reverse("assets:asset_warranty_activate", args=[warranty_a.pk])
    resp_act = member_client.post(url_activate)
    assert resp_act.status_code == 302
    warranty_a.refresh_from_db()
    assert warranty_a.status == "active"

    # 2. Renew active warranty
    old_end = warranty_a.end_date
    url_renew = reverse("assets:asset_warranty_renew", args=[warranty_a.pk])
    resp_ren = member_client.post(url_renew)
    assert resp_ren.status_code == 302
    warranty_a.refresh_from_db()
    assert warranty_a.end_date > old_end


def test_assetwarrantyinsurance_rbac_member_permitted_warranty_claim_actions(member_client, warranty_claim_a):
    """Non-admin member is permitted to submit, review, and settle warranty claims."""
    # 1. Submit draft claim
    warranty_claim_a.claim_status = "draft"
    warranty_claim_a.save(update_fields=["claim_status"])
    url_sub = reverse("assets:asset_warranty_claim_submit", args=[warranty_claim_a.pk])
    resp_sub = member_client.post(url_sub)
    assert resp_sub.status_code == 302
    warranty_claim_a.refresh_from_db()
    assert warranty_claim_a.claim_status == "submitted"

    # 2. Review submitted claim
    url_rev = reverse("assets:asset_warranty_claim_review", args=[warranty_claim_a.pk])
    resp_rev = member_client.post(url_rev)
    assert resp_rev.status_code == 302
    warranty_claim_a.refresh_from_db()
    assert warranty_claim_a.claim_status == "under_review"

    # 3. Settle claim
    url_set = reverse("assets:asset_warranty_claim_settle", args=[warranty_claim_a.pk])
    resp_set = member_client.post(url_set, data={"approved_amount": "2500.00", "resolution_type": "cash_reimbursement"})
    assert resp_set.status_code == 302
    warranty_claim_a.refresh_from_db()
    assert warranty_claim_a.claim_status == "settled_closed"


def test_assetwarrantyinsurance_rbac_member_permitted_insurance_policy_actions(member_client, insurance_policy_a):
    """Non-admin member is permitted to activate draft policy and renew active policy."""
    # 1. Activate draft policy
    insurance_policy_a.status = "draft"
    insurance_policy_a.save(update_fields=["status"])
    url_act = reverse("assets:asset_insurance_policy_activate", args=[insurance_policy_a.pk])
    resp_act = member_client.post(url_act)
    assert resp_act.status_code == 302
    insurance_policy_a.refresh_from_db()
    assert insurance_policy_a.status == "active"

    # 2. Renew active policy
    old_exp = insurance_policy_a.expiration_date
    url_ren = reverse("assets:asset_insurance_policy_renew", args=[insurance_policy_a.pk])
    resp_ren = member_client.post(url_ren)
    assert resp_ren.status_code == 302
    insurance_policy_a.refresh_from_db()
    assert insurance_policy_a.expiration_date > old_exp


def test_assetwarrantyinsurance_rbac_member_permitted_insurance_claim_actions(member_client, insurance_claim_a):
    """Non-admin member is permitted to assign adjuster, file proof of loss, and settle claim."""
    # 1. Assign adjuster
    url_adj = reverse("assets:asset_insurance_claim_assign_adjuster", args=[insurance_claim_a.pk])
    resp_adj = member_client.post(url_adj, data={"adjuster_name": "Marcus Vance", "carrier_claim_number": "TRV-88192"})
    assert resp_adj.status_code == 302
    insurance_claim_a.refresh_from_db()
    assert insurance_claim_a.claim_status == "adjuster_assigned"

    # 2. File proof of loss
    url_prf = reverse("assets:asset_insurance_claim_file_proof", args=[insurance_claim_a.pk])
    resp_prf = member_client.post(url_prf)
    assert resp_prf.status_code == 302
    insurance_claim_a.refresh_from_db()
    assert insurance_claim_a.claim_status == "proof_of_loss_filed"

    # 3. Settle claim
    url_set = reverse("assets:asset_insurance_claim_settle", args=[insurance_claim_a.pk])
    resp_set = member_client.post(url_set, data={"settlement_payout_amount": "22000.00", "salvage_recovery_amount": "500.00"})
    assert resp_set.status_code == 302
    insurance_claim_a.refresh_from_db()
    assert insurance_claim_a.claim_status == "settled_paid"


# ==============================================================================
# 4. Adversarial Numeric Input Hardening (Lesson L35)
# ==============================================================================

def test_assetwarrantyinsurance_adversarial_numeric_warranty_claim_settle_nan(client_a, warranty_claim_a):
    """Submitting 'NaN' for approved_amount redirects safely without crash, preserving state."""
    url = reverse("assets:asset_warranty_claim_settle", args=[warranty_claim_a.pk])
    resp = client_a.post(url, data={"approved_amount": "NaN"})
    assert resp.status_code == 302
    warranty_claim_a.refresh_from_db()
    assert warranty_claim_a.claim_status == "submitted"
    assert warranty_claim_a.approved_amount == Decimal("0.00")


def test_assetwarrantyinsurance_adversarial_numeric_warranty_claim_settle_infinity(client_a, warranty_claim_a):
    """Submitting 'Infinity' for approved_amount redirects safely without crash, preserving state."""
    url = reverse("assets:asset_warranty_claim_settle", args=[warranty_claim_a.pk])
    resp = client_a.post(url, data={"approved_amount": "Infinity"})
    assert resp.status_code == 302
    warranty_claim_a.refresh_from_db()
    assert warranty_claim_a.claim_status == "submitted"


def test_assetwarrantyinsurance_adversarial_numeric_warranty_claim_settle_negative_infinity(client_a, warranty_claim_a):
    """Submitting '-Infinity' for approved_amount redirects safely without crash, preserving state."""
    url = reverse("assets:asset_warranty_claim_settle", args=[warranty_claim_a.pk])
    resp = client_a.post(url, data={"approved_amount": "-Infinity"})
    assert resp.status_code == 302
    warranty_claim_a.refresh_from_db()
    assert warranty_claim_a.claim_status == "submitted"


def test_assetwarrantyinsurance_adversarial_numeric_warranty_claim_settle_negative_value(client_a, warranty_claim_a):
    """Submitting negative approved_amount redirects safely without crash, preserving state."""
    url = reverse("assets:asset_warranty_claim_settle", args=[warranty_claim_a.pk])
    resp = client_a.post(url, data={"approved_amount": "-5000.00"})
    assert resp.status_code == 302
    warranty_claim_a.refresh_from_db()
    assert warranty_claim_a.claim_status == "submitted"


def test_assetwarrantyinsurance_adversarial_numeric_warranty_claim_settle_astronomical(client_a, warranty_claim_a):
    """Submitting out-of-range precision approved_amount redirects safely without crash."""
    url = reverse("assets:asset_warranty_claim_settle", args=[warranty_claim_a.pk])
    resp = client_a.post(url, data={"approved_amount": "999999999999999999999999.00"})
    assert resp.status_code == 302
    warranty_claim_a.refresh_from_db()
    assert warranty_claim_a.claim_status == "submitted"


def test_assetwarrantyinsurance_adversarial_numeric_warranty_claim_settle_malformed_string(client_a, warranty_claim_a):
    """Submitting malformed non-numeric text redirects safely without crash."""
    url = reverse("assets:asset_warranty_claim_settle", args=[warranty_claim_a.pk])
    resp = client_a.post(url, data={"approved_amount": "malicious_exploit!@#$%^&*()"})
    assert resp.status_code == 302
    warranty_claim_a.refresh_from_db()
    assert warranty_claim_a.claim_status == "submitted"


def test_assetwarrantyinsurance_adversarial_numeric_insurance_claim_settle_nan(client_a, insurance_claim_a):
    """Submitting 'NaN' for settlement_payout_amount redirects safely without crash."""
    url = reverse("assets:asset_insurance_claim_settle", args=[insurance_claim_a.pk])
    resp = client_a.post(url, data={"settlement_payout_amount": "NaN"})
    assert resp.status_code == 302
    insurance_claim_a.refresh_from_db()
    assert insurance_claim_a.claim_status == "proof_of_loss_filed"
    assert insurance_claim_a.settlement_payout_amount == Decimal("0.00")


def test_assetwarrantyinsurance_adversarial_numeric_insurance_claim_settle_infinity(client_a, insurance_claim_a):
    """Submitting 'Infinity' for settlement_payout_amount redirects safely without crash."""
    url = reverse("assets:asset_insurance_claim_settle", args=[insurance_claim_a.pk])
    resp = client_a.post(url, data={"settlement_payout_amount": "Infinity"})
    assert resp.status_code == 302
    insurance_claim_a.refresh_from_db()
    assert insurance_claim_a.claim_status == "proof_of_loss_filed"


def test_assetwarrantyinsurance_adversarial_numeric_insurance_claim_settle_negative_infinity(client_a, insurance_claim_a):
    """Submitting '-Infinity' for settlement_payout_amount redirects safely without crash."""
    url = reverse("assets:asset_insurance_claim_settle", args=[insurance_claim_a.pk])
    resp = client_a.post(url, data={"settlement_payout_amount": "-Infinity"})
    assert resp.status_code == 302
    insurance_claim_a.refresh_from_db()
    assert insurance_claim_a.claim_status == "proof_of_loss_filed"


def test_assetwarrantyinsurance_adversarial_numeric_insurance_claim_settle_negative_value(client_a, insurance_claim_a):
    """Submitting negative settlement_payout_amount redirects safely without crash."""
    url = reverse("assets:asset_insurance_claim_settle", args=[insurance_claim_a.pk])
    resp = client_a.post(url, data={"settlement_payout_amount": "-15000.00"})
    assert resp.status_code == 302
    insurance_claim_a.refresh_from_db()
    assert insurance_claim_a.claim_status == "proof_of_loss_filed"


def test_assetwarrantyinsurance_adversarial_numeric_insurance_claim_settle_astronomical(client_a, insurance_claim_a):
    """Submitting out-of-range precision settlement_payout_amount redirects safely without crash."""
    url = reverse("assets:asset_insurance_claim_settle", args=[insurance_claim_a.pk])
    resp = client_a.post(url, data={"settlement_payout_amount": "999999999999999999999999.00"})
    assert resp.status_code == 302
    insurance_claim_a.refresh_from_db()
    assert insurance_claim_a.claim_status == "proof_of_loss_filed"


def test_assetwarrantyinsurance_adversarial_numeric_insurance_claim_settle_salvage_nan(client_a, insurance_claim_a):
    """Submitting 'NaN' for salvage_recovery_amount redirects safely without crash."""
    url = reverse("assets:asset_insurance_claim_settle", args=[insurance_claim_a.pk])
    resp = client_a.post(url, data={"settlement_payout_amount": "20000.00", "salvage_recovery_amount": "NaN"})
    assert resp.status_code == 302
    insurance_claim_a.refresh_from_db()
    assert insurance_claim_a.claim_status == "proof_of_loss_filed"


def test_assetwarrantyinsurance_adversarial_numeric_insurance_claim_settle_salvage_negative(client_a, insurance_claim_a):
    """Submitting negative salvage_recovery_amount redirects safely without crash."""
    url = reverse("assets:asset_insurance_claim_settle", args=[insurance_claim_a.pk])
    resp = client_a.post(url, data={"settlement_payout_amount": "20000.00", "salvage_recovery_amount": "-500.00"})
    assert resp.status_code == 302
    insurance_claim_a.refresh_from_db()
    assert insurance_claim_a.claim_status == "proof_of_loss_filed"


def test_assetwarrantyinsurance_adversarial_numeric_insurance_claim_settle_salvage_astronomical(client_a, insurance_claim_a):
    """Submitting astronomical salvage_recovery_amount redirects safely without crash."""
    url = reverse("assets:asset_insurance_claim_settle", args=[insurance_claim_a.pk])
    resp = client_a.post(url, data={"settlement_payout_amount": "20000.00", "salvage_recovery_amount": "999999999999999999999999.00"})
    assert resp.status_code == 302
    insurance_claim_a.refresh_from_db()
    assert insurance_claim_a.claim_status == "proof_of_loss_filed"


# ==============================================================================
# 5. State Tampering & Workflow Guard Defenses
# ==============================================================================

def test_assetwarrantyinsurance_state_tampering_settled_warranty_claim_re_settle_blocked(client_a, warranty_claim_a):
    """Attempting to re-settle a settled warranty claim is rejected by view-level guard."""
    # First settle it
    warranty_claim_a.claim_status = "settled_closed"
    warranty_claim_a.approved_amount = Decimal("3000.00")
    warranty_claim_a.save()

    url = reverse("assets:asset_warranty_claim_settle", args=[warranty_claim_a.pk])
    resp = client_a.post(url, data={"approved_amount": "5000.00"})
    assert resp.status_code == 302

    warranty_claim_a.refresh_from_db()
    assert warranty_claim_a.approved_amount == Decimal("3000.00")


def test_assetwarrantyinsurance_state_tampering_settled_warranty_claim_reject_blocked(client_a, warranty_claim_a):
    """Attempting to reject an already settled warranty claim is blocked by status guard."""
    warranty_claim_a.claim_status = "settled_closed"
    warranty_claim_a.save()

    url = reverse("assets:asset_warranty_claim_reject", args=[warranty_claim_a.pk])
    resp = client_a.post(url)
    assert resp.status_code == 302

    warranty_claim_a.refresh_from_db()
    assert warranty_claim_a.claim_status == "settled_closed"


def test_assetwarrantyinsurance_state_tampering_settled_warranty_claim_submit_blocked(client_a, warranty_claim_a):
    """Attempting to re-submit an already settled warranty claim is blocked by status guard."""
    warranty_claim_a.claim_status = "settled_closed"
    warranty_claim_a.save()

    url = reverse("assets:asset_warranty_claim_submit", args=[warranty_claim_a.pk])
    resp = client_a.post(url)
    assert resp.status_code == 302

    warranty_claim_a.refresh_from_db()
    assert warranty_claim_a.claim_status == "settled_closed"


def test_assetwarrantyinsurance_state_tampering_settled_warranty_claim_edit_blocked(client_a, warranty_claim_a):
    """Editing settled_closed warranty claim is blocked on GET and POST."""
    warranty_claim_a.claim_status = "settled_closed"
    warranty_claim_a.save()

    url = reverse("assets:asset_warranty_claim_edit", args=[warranty_claim_a.pk])
    assert client_a.get(url).status_code == 302

    resp_post = client_a.post(url, data={"title": "Hacked Settlement"})
    assert resp_post.status_code == 302
    warranty_claim_a.refresh_from_db()
    assert warranty_claim_a.title != "Hacked Settlement"


def test_assetwarrantyinsurance_state_tampering_rejected_warranty_claim_edit_blocked(client_a, warranty_claim_a):
    """Editing rejected warranty claim is blocked on GET and POST."""
    warranty_claim_a.claim_status = "rejected"
    warranty_claim_a.save()

    url = reverse("assets:asset_warranty_claim_edit", args=[warranty_claim_a.pk])
    assert client_a.get(url).status_code == 302

    resp_post = client_a.post(url, data={"title": "Hacked Rejection"})
    assert resp_post.status_code == 302
    warranty_claim_a.refresh_from_db()
    assert warranty_claim_a.title != "Hacked Rejection"


def test_assetwarrantyinsurance_state_tampering_settled_insurance_claim_re_settle_blocked(client_a, insurance_claim_a):
    """Attempting to re-settle a settled insurance claim is rejected by status guard."""
    insurance_claim_a.claim_status = "settled_paid"
    insurance_claim_a.settlement_payout_amount = Decimal("25000.00")
    insurance_claim_a.save()

    url = reverse("assets:asset_insurance_claim_settle", args=[insurance_claim_a.pk])
    resp = client_a.post(url, data={"settlement_payout_amount": "99000.00"})
    assert resp.status_code == 302

    insurance_claim_a.refresh_from_db()
    assert insurance_claim_a.settlement_payout_amount == Decimal("25000.00")


def test_assetwarrantyinsurance_state_tampering_settled_insurance_claim_deny_blocked(client_a, insurance_claim_a):
    """Attempting to deny an already settled insurance claim is blocked by status guard."""
    insurance_claim_a.claim_status = "settled_paid"
    insurance_claim_a.save()

    url = reverse("assets:asset_insurance_claim_deny", args=[insurance_claim_a.pk])
    resp = client_a.post(url)
    assert resp.status_code == 302

    insurance_claim_a.refresh_from_db()
    assert insurance_claim_a.claim_status == "settled_paid"


def test_assetwarrantyinsurance_state_tampering_settled_insurance_claim_edit_blocked(client_a, insurance_claim_a):
    """Editing settled_paid insurance claim is blocked on GET and POST."""
    insurance_claim_a.claim_status = "settled_paid"
    insurance_claim_a.save()

    url = reverse("assets:asset_insurance_claim_edit", args=[insurance_claim_a.pk])
    assert client_a.get(url).status_code == 302

    resp_post = client_a.post(url, data={"title": "Hacked Settlement Title"})
    assert resp_post.status_code == 302
    insurance_claim_a.refresh_from_db()
    assert insurance_claim_a.title != "Hacked Settlement Title"


def test_assetwarrantyinsurance_state_tampering_denied_insurance_claim_edit_blocked(client_a, insurance_claim_a):
    """Editing denied_disputed insurance claim is blocked on GET and POST."""
    insurance_claim_a.claim_status = "denied_disputed"
    insurance_claim_a.save()

    url = reverse("assets:asset_insurance_claim_edit", args=[insurance_claim_a.pk])
    assert client_a.get(url).status_code == 302

    resp_post = client_a.post(url, data={"title": "Hacked Denial Title"})
    assert resp_post.status_code == 302
    insurance_claim_a.refresh_from_db()
    assert insurance_claim_a.title != "Hacked Denial Title"


def test_assetwarrantyinsurance_state_tampering_renew_voided_warranty_blocked(client_a, warranty_a):
    """Attempting to renew a voided warranty is rejected by status guard."""
    warranty_a.status = "voided"
    warranty_a.save()
    old_end = warranty_a.end_date

    url = reverse("assets:asset_warranty_renew", args=[warranty_a.pk])
    resp = client_a.post(url)
    assert resp.status_code == 302

    warranty_a.refresh_from_db()
    assert warranty_a.status == "voided"
    assert warranty_a.end_date == old_end


def test_assetwarrantyinsurance_state_tampering_renew_cancelled_insurance_policy_blocked(client_a, insurance_policy_a):
    """Attempting to renew a cancelled insurance policy is rejected by status guard."""
    insurance_policy_a.status = "cancelled"
    insurance_policy_a.save()
    old_exp = insurance_policy_a.expiration_date

    url = reverse("assets:asset_insurance_policy_renew", args=[insurance_policy_a.pk])
    resp = client_a.post(url)
    assert resp.status_code == 302

    insurance_policy_a.refresh_from_db()
    assert insurance_policy_a.status == "cancelled"
    assert insurance_policy_a.expiration_date == old_exp


def test_assetwarrantyinsurance_mass_assignment_warranty_create(client_a, tenant_a, tenant_b, currency_usd, vendor_party_a):
    """Injected tenant, number, and status in warranty create payload are ignored."""
    url = reverse("assets:asset_warranty_create")
    payload = _assetwarrantyinsurance_warranty_payload(
        currency_usd,
        vendor_party_a,
        title="Tamper Warranty Create",
        # Injected unauthorized fields
        tenant=tenant_b.pk,
        number="WARR-HACK-9999",
        status="claimed",
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    created = AssetWarranty.objects.filter(tenant=tenant_a, title="Tamper Warranty Create").first()
    assert created is not None
    assert created.tenant == tenant_a
    assert created.number != "WARR-HACK-9999"
    assert created.number.startswith("AWAR-")
    assert created.status == "active"  # Injected status ignored; default is active
    assert created.status != "claimed"


def test_assetwarrantyinsurance_mass_assignment_warranty_edit(client_a, tenant_a, tenant_b, warranty_a, currency_usd):
    """Injected tenant, number, and status in warranty edit payload are ignored."""
    url = reverse("assets:asset_warranty_edit", args=[warranty_a.pk])
    original_number = warranty_a.number

    payload = _assetwarrantyinsurance_warranty_payload(
        currency_usd,
        warranty_a.warrantor_party,
        title="Legitimate Warranty Update",
        # Injected overrides
        tenant=tenant_b.pk,
        number="WARR-FORGED-0001",
        status="voided",
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    warranty_a.refresh_from_db()
    assert warranty_a.title == "Legitimate Warranty Update"
    assert warranty_a.tenant == tenant_a
    assert warranty_a.number == original_number
    assert warranty_a.status == "active"  # Injected 'voided' ignored


def test_assetwarrantyinsurance_mass_assignment_warranty_claim_create(client_a, tenant_a, tenant_b, currency_usd, warranty_a):
    """Injected tenant, number, and claim_status in warranty claim create payload are ignored."""
    url = reverse("assets:asset_warranty_claim_create")
    payload = _assetwarrantyinsurance_warranty_claim_payload(
        currency_usd,
        warranty_a,
        title="Tamper Claim Create",
        # Injected overrides
        tenant=tenant_b.pk,
        number="WCLM-HACK-9999",
        claim_status="settled_closed",
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    created = AssetWarrantyClaim.objects.filter(tenant=tenant_a, title="Tamper Claim Create").first()
    assert created is not None
    assert created.tenant == tenant_a
    assert created.number != "WCLM-HACK-9999"
    assert created.number.startswith("AWCL-")
    assert created.claim_status == "draft"  # Default draft
    assert created.claim_status != "settled_closed"


def test_assetwarrantyinsurance_mass_assignment_warranty_claim_edit(client_a, tenant_a, tenant_b, warranty_claim_a, currency_usd):
    """Injected tenant, number, and claim_status in warranty claim edit payload are ignored."""
    url = reverse("assets:asset_warranty_claim_edit", args=[warranty_claim_a.pk])
    original_number = warranty_claim_a.number

    payload = _assetwarrantyinsurance_warranty_claim_payload(
        currency_usd,
        warranty_claim_a.warranty,
        title="Legitimate Claim Update",
        # Injected overrides
        tenant=tenant_b.pk,
        number="WCLM-OVERWRITE-888",
        claim_status="settled_closed",
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    warranty_claim_a.refresh_from_db()
    assert warranty_claim_a.title == "Legitimate Claim Update"
    assert warranty_claim_a.tenant == tenant_a
    assert warranty_claim_a.number == original_number
    assert warranty_claim_a.claim_status == "submitted"  # Injected settled_closed ignored


def test_assetwarrantyinsurance_mass_assignment_insurance_policy_create(client_a, tenant_a, tenant_b, currency_usd, underwriter_party_a):
    """Injected tenant, number, and status in insurance policy create payload are ignored."""
    url = reverse("assets:asset_insurance_policy_create")
    payload = _assetwarrantyinsurance_insurance_policy_payload(
        currency_usd,
        underwriter_party_a,
        title="Tamper Policy Create",
        # Injected overrides
        tenant=tenant_b.pk,
        number="POL-HACK-9999",
        status="cancelled",
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    created = AssetInsurancePolicy.objects.filter(tenant=tenant_a, title="Tamper Policy Create").first()
    assert created is not None
    assert created.tenant == tenant_a
    assert created.number != "POL-HACK-9999"
    assert created.number.startswith("AINS-")
    assert created.status == "active"  # Injected status ignored; default is active
    assert created.status != "cancelled"


def test_assetwarrantyinsurance_mass_assignment_insurance_policy_edit(client_a, tenant_a, tenant_b, insurance_policy_a, currency_usd):
    """Injected tenant, number, and status in insurance policy edit payload are ignored."""
    url = reverse("assets:asset_insurance_policy_edit", args=[insurance_policy_a.pk])
    original_number = insurance_policy_a.number

    payload = _assetwarrantyinsurance_insurance_policy_payload(
        currency_usd,
        insurance_policy_a.underwriter_party,
        title="Legitimate Policy Update",
        # Injected overrides
        tenant=tenant_b.pk,
        number="POL-FORGED-0001",
        status="cancelled",
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    insurance_policy_a.refresh_from_db()
    assert insurance_policy_a.title == "Legitimate Policy Update"
    assert insurance_policy_a.tenant == tenant_a
    assert insurance_policy_a.number == original_number
    assert insurance_policy_a.status == "active"  # Injected cancelled ignored


def test_assetwarrantyinsurance_mass_assignment_insurance_claim_create(client_a, tenant_a, tenant_b, currency_usd, insurance_policy_a):
    """Injected tenant, number, and claim_status in insurance claim create payload are ignored."""
    url = reverse("assets:asset_insurance_claim_create")
    payload = _assetwarrantyinsurance_insurance_claim_payload(
        currency_usd,
        insurance_policy_a,
        title="Tamper Ins Claim Create",
        # Injected overrides
        tenant=tenant_b.pk,
        number="ICLM-HACK-9999",
        claim_status="settled_paid",
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    created = AssetInsuranceClaim.objects.filter(tenant=tenant_a, title="Tamper Ins Claim Create").first()
    assert created is not None
    assert created.tenant == tenant_a
    assert created.number != "ICLM-HACK-9999"
    assert created.number.startswith("AICL-")
    assert created.claim_status == "incident_reported"  # Default incident_reported
    assert created.claim_status != "settled_paid"


def test_assetwarrantyinsurance_mass_assignment_insurance_claim_edit(client_a, tenant_a, tenant_b, insurance_claim_a, currency_usd):
    """Injected tenant, number, and claim_status in insurance claim edit payload are ignored."""
    url = reverse("assets:asset_insurance_claim_edit", args=[insurance_claim_a.pk])
    original_number = insurance_claim_a.number

    payload = _assetwarrantyinsurance_insurance_claim_payload(
        currency_usd,
        insurance_claim_a.policy,
        title="Legitimate Ins Claim Update",
        # Injected overrides
        tenant=tenant_b.pk,
        number="ICLM-OVERWRITE-777",
        claim_status="settled_paid",
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    insurance_claim_a.refresh_from_db()
    assert insurance_claim_a.title == "Legitimate Ins Claim Update"
    assert insurance_claim_a.tenant == tenant_a
    assert insurance_claim_a.number == original_number
    assert insurance_claim_a.claim_status == "proof_of_loss_filed"  # Injected settled_paid ignored


# ==============================================================================
# 6. Audit Log Generation
# ==============================================================================

def test_assetwarrantyinsurance_audit_log_warranty_lifecycle(client_a, tenant_a, admin_user, currency_usd, vendor_party_a):
    """AuditLog rows are generated for warranty create, update, and delete."""
    # 1. Create
    url_create = reverse("assets:asset_warranty_create")
    payload = _assetwarrantyinsurance_warranty_payload(currency_usd, vendor_party_a, title="Audit Warranty Lifecycle")
    resp_create = client_a.post(url_create, data=payload)
    assert resp_create.status_code == 302

    warranty = AssetWarranty.objects.get(tenant=tenant_a, title="Audit Warranty Lifecycle")
    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=warranty.pk,
    ).exists()

    # 2. Update
    url_edit = reverse("assets:asset_warranty_edit", args=[warranty.pk])
    payload["title"] = "Audit Warranty Updated"
    resp_edit = client_a.post(url_edit, data=payload)
    assert resp_edit.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=warranty.pk,
    ).exists()

    # 3. Delete
    url_delete = reverse("assets:asset_warranty_delete", args=[warranty.pk])
    resp_del = client_a.post(url_delete)
    assert resp_del.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
        object_id=warranty.pk,
    ).exists()


def test_assetwarrantyinsurance_audit_log_warranty_claim_lifecycle(client_a, tenant_a, admin_user, currency_usd, warranty_a):
    """AuditLog rows are generated for warranty claim create, update, and delete."""
    # 1. Create
    url_create = reverse("assets:asset_warranty_claim_create")
    payload = _assetwarrantyinsurance_warranty_claim_payload(currency_usd, warranty_a, title="Audit Claim Lifecycle")
    resp_create = client_a.post(url_create, data=payload)
    assert resp_create.status_code == 302

    claim = AssetWarrantyClaim.objects.get(tenant=tenant_a, title="Audit Claim Lifecycle")
    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=claim.pk,
    ).exists()

    # 2. Update
    url_edit = reverse("assets:asset_warranty_claim_edit", args=[claim.pk])
    payload["title"] = "Audit Claim Updated"
    resp_edit = client_a.post(url_edit, data=payload)
    assert resp_edit.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=claim.pk,
    ).exists()

    # 3. Delete
    url_delete = reverse("assets:asset_warranty_claim_delete", args=[claim.pk])
    resp_del = client_a.post(url_delete)
    assert resp_del.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
        object_id=claim.pk,
    ).exists()


def test_assetwarrantyinsurance_audit_log_insurance_policy_lifecycle(client_a, tenant_a, admin_user, currency_usd, underwriter_party_a):
    """AuditLog rows are generated for insurance policy create, update, and delete."""
    # 1. Create
    url_create = reverse("assets:asset_insurance_policy_create")
    payload = _assetwarrantyinsurance_insurance_policy_payload(currency_usd, underwriter_party_a, title="Audit Policy Lifecycle")
    resp_create = client_a.post(url_create, data=payload)
    assert resp_create.status_code == 302

    policy = AssetInsurancePolicy.objects.get(tenant=tenant_a, title="Audit Policy Lifecycle")
    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=policy.pk,
    ).exists()

    # 2. Update
    url_edit = reverse("assets:asset_insurance_policy_edit", args=[policy.pk])
    payload["title"] = "Audit Policy Updated"
    resp_edit = client_a.post(url_edit, data=payload)
    assert resp_edit.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=policy.pk,
    ).exists()

    # 3. Delete
    url_delete = reverse("assets:asset_insurance_policy_delete", args=[policy.pk])
    resp_del = client_a.post(url_delete)
    assert resp_del.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
        object_id=policy.pk,
    ).exists()


def test_assetwarrantyinsurance_audit_log_insurance_claim_lifecycle(client_a, tenant_a, admin_user, currency_usd, insurance_policy_a):
    """AuditLog rows are generated for insurance claim create, update, and delete."""
    # 1. Create
    url_create = reverse("assets:asset_insurance_claim_create")
    payload = _assetwarrantyinsurance_insurance_claim_payload(currency_usd, insurance_policy_a, title="Audit Ins Claim Lifecycle")
    resp_create = client_a.post(url_create, data=payload)
    assert resp_create.status_code == 302

    claim = AssetInsuranceClaim.objects.get(tenant=tenant_a, title="Audit Ins Claim Lifecycle")
    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=claim.pk,
    ).exists()

    # 2. Update
    url_edit = reverse("assets:asset_insurance_claim_edit", args=[claim.pk])
    payload["title"] = "Audit Ins Claim Updated"
    resp_edit = client_a.post(url_edit, data=payload)
    assert resp_edit.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=claim.pk,
    ).exists()

    # 3. Delete
    url_delete = reverse("assets:asset_insurance_claim_delete", args=[claim.pk])
    resp_del = client_a.post(url_delete)
    assert resp_del.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
        object_id=claim.pk,
    ).exists()


# ==============================================================================
# 7. HTTP Method Guards (require_POST rejects GET with 405)
# ==============================================================================

def test_assetwarrantyinsurance_http_method_guards_require_post(client_a, warranty_a, warranty_claim_a, insurance_policy_a, insurance_claim_a):
    """All 18 state-mutating action endpoints reject GET requests with 405 Method Not Allowed."""
    post_only_endpoints = [
        # Warranty actions (4)
        reverse("assets:asset_warranty_delete", args=[warranty_a.pk]),
        reverse("assets:asset_warranty_activate", args=[warranty_a.pk]),
        reverse("assets:asset_warranty_renew", args=[warranty_a.pk]),
        reverse("assets:asset_warranty_void", args=[warranty_a.pk]),

        # Warranty Claim actions (5)
        reverse("assets:asset_warranty_claim_delete", args=[warranty_claim_a.pk]),
        reverse("assets:asset_warranty_claim_submit", args=[warranty_claim_a.pk]),
        reverse("assets:asset_warranty_claim_review", args=[warranty_claim_a.pk]),
        reverse("assets:asset_warranty_claim_settle", args=[warranty_claim_a.pk]),
        reverse("assets:asset_warranty_claim_reject", args=[warranty_claim_a.pk]),

        # Insurance Policy actions (4)
        reverse("assets:asset_insurance_policy_delete", args=[insurance_policy_a.pk]),
        reverse("assets:asset_insurance_policy_activate", args=[insurance_policy_a.pk]),
        reverse("assets:asset_insurance_policy_renew", args=[insurance_policy_a.pk]),
        reverse("assets:asset_insurance_policy_cancel", args=[insurance_policy_a.pk]),

        # Insurance Claim actions (5)
        reverse("assets:asset_insurance_claim_delete", args=[insurance_claim_a.pk]),
        reverse("assets:asset_insurance_claim_assign_adjuster", args=[insurance_claim_a.pk]),
        reverse("assets:asset_insurance_claim_file_proof", args=[insurance_claim_a.pk]),
        reverse("assets:asset_insurance_claim_settle", args=[insurance_claim_a.pk]),
        reverse("assets:asset_insurance_claim_deny", args=[insurance_claim_a.pk]),
    ]
    assert len(post_only_endpoints) == 18, f"Expected 18 POST-only endpoints, got {len(post_only_endpoints)}"

    for url in post_only_endpoints:
        response = client_a.get(url)
        assert response.status_code == 405, f"Expected 405 for GET on {url}, got {response.status_code}"
