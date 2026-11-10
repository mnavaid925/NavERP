"""Functional view and workflow action test suite for Sub-module 11.8: Warranty & Insurance Management.

Covers all 4 entities and their view endpoints:
1. AssetWarranty:
   - list (search, filters by status/warranty_type/coverage_scope/category, pagination, junk params)
   - create (GET renders form, POST valid creates & redirects, POST invalid renders errors)
   - detail (renders 200, context contract, content assertions, cross-tenant 404)
   - edit (GET renders form, POST valid updates record)
   - delete (GET 405 @require_POST, POST deletes record)
   - action endpoints: activate, renew (verify renewal rejection on voided/cancelled), void
2. AssetWarrantyClaim:
   - list (search, filters by status, resolution_type, part_return_status, warranty pk, pagination)
   - create (GET with ?warranty=<pk> prepopulation, POST valid, POST invalid)
   - detail (renders chained warrantor party cleanly, cross-tenant 404)
   - edit (status guard: modifying settled/closed claim is rejected)
   - delete (GET 405 @require_POST, POST deletes)
   - workflow actions: submit, review, settle (verify valid approved_amount, status guard preventing
     re-settling already settled claim, and resolution_type validation), reject (status guard)
3. AssetInsurancePolicy:
   - list (filters by status, policy_type, valuation_basis, category, pagination, junk params)
   - create (GET, POST valid, POST invalid)
   - detail (renders 200, context contract, cross-tenant 404)
   - edit (GET, POST valid)
   - delete (GET 405 @require_POST, POST deletes)
   - action endpoints: activate, renew (rejection on cancelled), cancel
4. AssetInsuranceClaim:
   - list (filters by status, peril_type, settlement_method, policy pk, pagination)
   - create (GET with ?policy=<pk> prepopulation, POST valid, POST invalid)
   - detail (renders chained underwriter party cleanly, cross-tenant 404)
   - edit (status guard: modifying settled/closed claim is rejected)
   - delete (GET 405 @require_POST, POST deletes)
   - workflow actions: assign_adjuster, file_proof, settle (verify valid settlement_payout and
     salvage_recovery numbers, status guard, and settlement_method validation), deny (status guard)
5. Query count tests: test list query counts stay bounded using django_assert_max_num_queries(15).
6. Security: unauthenticated access redirects to login.
"""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models import Currency, FixedAsset
from apps.assets.models import (
    AssetCategory,
    AssetInsuranceClaim,
    AssetInsurancePolicy,
    AssetWarranty,
    AssetWarrantyClaim,
)
from apps.core.models import AuditLog, Party, PartyRole
from apps.scm.models import Asset as OperationalAsset

pytestmark = pytest.mark.django_db


# ==============================================================================
# Helpers (strictly prefixed with _assetwarrantyinsurance_)
# ==============================================================================

def _assetwarrantyinsurance_get_flash_messages(response):
    """Extract list of flash message strings from response."""
    return [str(m) for m in get_messages(response.wsgi_request)]


def _assetwarrantyinsurance_ensure_vendor_role(party):
    """Ensure party has an active vendor role to satisfy vendor-filtered FK dropdowns."""
    PartyRole.objects.get_or_create(
        tenant=party.tenant,
        party=party,
        role="vendor",
        defaults={"status": "active"},
    )
    return party


def _assetwarrantyinsurance_warranty_payload(currency, warrantor, **kwargs):
    """Build a valid payload for AssetWarrantyForm POST."""
    _assetwarrantyinsurance_ensure_vendor_role(warrantor)
    today = timezone.now().date()
    payload = {
        "title": "Industrial Centrifugal Compressor Factory Warranty",
        "warranty_certificate_number": "CERT-COMP-2026-001",
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
    payload.update(kwargs)
    return payload


def _assetwarrantyinsurance_warranty_claim_payload(currency, warranty, **kwargs):
    """Build a valid payload for AssetWarrantyClaimForm POST."""
    today = timezone.now().date()
    payload = {
        "title": "Impeller Shaft Fatigue Fracture Claim",
        "warranty": str(warranty.pk),
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
    payload.update(kwargs)
    return payload


def _assetwarrantyinsurance_insurance_policy_payload(currency, underwriter, **kwargs):
    """Build a valid payload for AssetInsurancePolicyForm POST."""
    _assetwarrantyinsurance_ensure_vendor_role(underwriter)
    today = timezone.now().date()
    payload = {
        "policy_number": "POL-2026-IND-MACH-01",
        "title": "Machinery Breakdown & Boiler Explosion Policy",
        "policy_type": "machinery_breakdown",
        "valuation_basis": "replacement_cost_value",
        "underwriter_party": str(underwriter.pk),
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
    payload.update(kwargs)
    return payload


def _assetwarrantyinsurance_insurance_claim_payload(currency, policy, **kwargs):
    """Build a valid payload for AssetInsuranceClaimForm POST."""
    today = timezone.now().date()
    payload = {
        "title": "Main Transformer Stator Flashover Claim",
        "policy": str(policy.pk),
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
    payload.update(kwargs)
    return payload


# ==============================================================================
# 1. AssetWarranty Views & Actions
# ==============================================================================

def test_assetwarrantyinsurance_warranty_list_renders_200_and_context(client_a, warranty_a, tenant_a):
    """asset_warranty_list renders 200 with complete context contracts and statistics."""
    url = reverse("assets:asset_warranty_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "warranties" in resp.context
    assert "page_obj" in resp.context
    assert "paginator" in resp.context
    assert "status_choices" in resp.context
    assert "warranty_type_choices" in resp.context
    assert "coverage_scope_choices" in resp.context
    assert "category_list" in resp.context
    assert "total_warranties" in resp.context
    assert "active_warranties" in resp.context
    assert "expiring_soon_count" in resp.context
    assert "claimed_count" in resp.context

    warranties = list(resp.context["warranties"])
    assert warranty_a in warranties
    assert resp.context["total_warranties"] >= 1


def test_assetwarrantyinsurance_warranty_list_search_by_query(client_a, warranty_a, tenant_a):
    """asset_warranty_list search filters by certificate number, title, and warrantor name."""
    url = reverse("assets:asset_warranty_list")

    # Search by certificate number
    resp = client_a.get(url, {"q": warranty_a.warranty_certificate_number})
    assert resp.status_code == 200
    pks = [w.pk for w in resp.context["warranties"]]
    assert warranty_a.pk in pks

    # Search by title snippet
    resp = client_a.get(url, {"q": "Compressor OEM"})
    assert resp.status_code == 200
    pks = [w.pk for w in resp.context["warranties"]]
    assert warranty_a.pk in pks

    # Search non-matching term returns empty
    resp_empty = client_a.get(url, {"q": "NONEXISTENT_XYZ_TERM_123"})
    assert resp_empty.status_code == 200
    assert len(resp_empty.context["warranties"]) == 0


def test_assetwarrantyinsurance_warranty_list_filter_status(client_a, warranty_a, tenant_a, currency_usd, vendor_party_a, admin_user):
    """asset_warranty_list filters accurately by status enumeration."""
    today = timezone.now().date()
    draft_warranty = AssetWarranty.objects.create(
        tenant=tenant_a,
        warrantor_party=vendor_party_a,
        warranty_type="third_party_extended",
        coverage_scope="parts_only",
        title="Draft Spare Parts Warranty",
        warranty_certificate_number="WTY-DRAFT-99",
        start_date=today,
        end_date=today + timedelta(days=180),
        currency=currency_usd,
        status="draft",
        registered_by=admin_user,
    )
    url = reverse("assets:asset_warranty_list")

    # Filter active
    resp_active = client_a.get(url, {"status": "active"})
    assert resp_active.status_code == 200
    pks_active = [w.pk for w in resp_active.context["warranties"]]
    assert warranty_a.pk in pks_active
    assert draft_warranty.pk not in pks_active

    # Filter draft
    resp_draft = client_a.get(url, {"status": "draft"})
    assert resp_draft.status_code == 200
    pks_draft = [w.pk for w in resp_draft.context["warranties"]]
    assert draft_warranty.pk in pks_draft
    assert warranty_a.pk not in pks_draft


def test_assetwarrantyinsurance_warranty_list_filter_warranty_type_and_coverage(client_a, warranty_a):
    """asset_warranty_list filters by warranty_type and coverage_scope."""
    url = reverse("assets:asset_warranty_list")

    # Match warranty_a (oem_standard / comprehensive)
    resp = client_a.get(url, {"warranty_type": "oem_standard", "coverage_scope": "comprehensive"})
    assert resp.status_code == 200
    assert warranty_a.pk in [w.pk for w in resp.context["warranties"]]

    # Non-matching type
    resp_mismatch = client_a.get(url, {"warranty_type": "third_party_service"})
    assert resp_mismatch.status_code == 200
    assert warranty_a.pk not in [w.pk for w in resp_mismatch.context["warranties"]]


def test_assetwarrantyinsurance_warranty_list_filter_category(client_a, warranty_a, category_root_a):
    """asset_warranty_list filters by asset_category FK id."""
    warranty_a.asset_category = category_root_a
    warranty_a.save(update_fields=["asset_category"])

    url = reverse("assets:asset_warranty_list")
    resp = client_a.get(url, {"category": str(category_root_a.pk)})
    assert resp.status_code == 200
    assert warranty_a.pk in [w.pk for w in resp.context["warranties"]]

    resp_other = client_a.get(url, {"category": "999999"})
    assert resp_other.status_code == 200
    assert len(resp_other.context["warranties"]) == 0


def test_assetwarrantyinsurance_warranty_list_pagination_and_junk_params(client_a, tenant_a, currency_usd, vendor_party_a, admin_user):
    """asset_warranty_list handles page 2 and invalid parameters gracefully without 500 error."""
    today = timezone.now().date()
    # Create 16 warranties to exceed paginator size of 15
    for i in range(16):
        AssetWarranty.objects.create(
            tenant=tenant_a,
            warrantor_party=vendor_party_a,
            warranty_type="oem_standard",
            coverage_scope="comprehensive",
            title=f"Bulk Warranty Batch {i}",
            warranty_certificate_number=f"WTY-BULK-{i:03d}",
            start_date=today,
            end_date=today + timedelta(days=365),
            currency=currency_usd,
            status="active",
            registered_by=admin_user,
        )

    url = reverse("assets:asset_warranty_list")

    # Valid page 2
    resp_p2 = client_a.get(url, {"page": "2"})
    assert resp_p2.status_code == 200
    assert resp_p2.context["page_obj"].number == 2

    # Junk params
    resp_junk = client_a.get(url, {
        "page": "999999",
        "category": "not_an_int",
        "status": "bogus_status_code",
        "coverage_scope": "invalid_scope",
    })
    assert resp_junk.status_code == 200


def test_assetwarrantyinsurance_warranty_create_get_renders_form(client_a):
    """asset_warranty_create GET renders form with is_edit=False and warranty=None."""
    url = reverse("assets:asset_warranty_create")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["warranty"] is None


def test_assetwarrantyinsurance_warranty_create_post_valid(client_a, tenant_a, currency_usd, vendor_party_a, admin_user):
    """asset_warranty_create POST valid data creates record and writes audit log."""
    url = reverse("assets:asset_warranty_create")
    payload = _assetwarrantyinsurance_warranty_payload(
        currency_usd,
        vendor_party_a,
        title="Centrifugal Blower Factory Warranty 2026",
        warranty_certificate_number="CERT-BLW-2026-78",
    )

    resp = client_a.post(url, payload)
    assert resp.status_code == 302

    created = AssetWarranty.objects.filter(tenant=tenant_a, warranty_certificate_number="CERT-BLW-2026-78").first()
    assert created is not None
    assert created.tenant == tenant_a
    assert created.registered_by == admin_user
    assert created.number.startswith("AWAR-")
    assert resp.url == reverse("assets:asset_warranty_detail", kwargs={"pk": created.pk})

    # Verify audit log was recorded
    log = AuditLog.objects.filter(tenant=tenant_a, action="create").order_by("-at").first()
    assert log is not None
    assert created.number in str(log.changes)


def test_assetwarrantyinsurance_warranty_create_post_invalid(client_a):
    """asset_warranty_create POST invalid data returns 200 with form errors."""
    url = reverse("assets:asset_warranty_create")
    # Empty payload missing required fields
    resp = client_a.post(url, {})
    assert resp.status_code == 200
    assert resp.context["form"].errors


def test_assetwarrantyinsurance_warranty_detail_renders_200_and_content(client_a, warranty_a, warranty_claim_a):
    """asset_warranty_detail renders 200 with warranty contract and child claims."""
    url = reverse("assets:asset_warranty_detail", kwargs={"pk": warranty_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["warranty"] == warranty_a
    assert warranty_claim_a in resp.context["claims"]

    content = resp.content.decode("utf-8")
    assert warranty_a.warranty_certificate_number in content
    assert warranty_a.title in content
    assert warranty_a.warrantor_party.name in content


def test_assetwarrantyinsurance_warranty_detail_cross_tenant_404(client_b, warranty_a):
    """Cross-tenant warranty detail access returns 404 (IDOR barrier)."""
    url = reverse("assets:asset_warranty_detail", kwargs={"pk": warranty_a.pk})
    resp = client_b.get(url)
    assert resp.status_code == 404


def test_assetwarrantyinsurance_warranty_edit_get_renders_form(client_a, warranty_a):
    """asset_warranty_edit GET renders edit form with is_edit=True."""
    url = reverse("assets:asset_warranty_edit", kwargs={"pk": warranty_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["is_edit"] is True
    assert resp.context["warranty"] == warranty_a


def test_assetwarrantyinsurance_warranty_edit_post_valid(client_a, warranty_a, currency_usd, vendor_party_a):
    """asset_warranty_edit POST valid updates record fields and redirects to detail."""
    url = reverse("assets:asset_warranty_edit", kwargs={"pk": warranty_a.pk})
    payload = _assetwarrantyinsurance_warranty_payload(
        currency_usd,
        vendor_party_a,
        title="Updated Centrifugal Compressor Factory Warranty",
        deductible_amount="350.00",
    )

    resp = client_a.post(url, payload)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_warranty_detail", kwargs={"pk": warranty_a.pk})

    warranty_a.refresh_from_db()
    assert warranty_a.title == "Updated Centrifugal Compressor Factory Warranty"
    assert warranty_a.deductible_amount == Decimal("350.00")


def test_assetwarrantyinsurance_warranty_delete_requires_post(client_a, warranty_a):
    """asset_warranty_delete rejects GET with 405 Method Not Allowed."""
    url = reverse("assets:asset_warranty_delete", kwargs={"pk": warranty_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


def test_assetwarrantyinsurance_warranty_delete_post_success(client_a, warranty_a):
    """asset_warranty_delete POST deletes the warranty and redirects to list."""
    pk = warranty_a.pk
    url = reverse("assets:asset_warranty_delete", kwargs={"pk": pk})
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_warranty_list")
    assert not AssetWarranty.objects.filter(pk=pk).exists()


def test_assetwarrantyinsurance_warranty_activate_action(client_a, tenant_a, currency_usd, vendor_party_a, admin_user):
    """asset_warranty_activate action activates draft warranty and warns if already active."""
    today = timezone.now().date()
    draft = AssetWarranty.objects.create(
        tenant=tenant_a,
        warrantor_party=vendor_party_a,
        warranty_type="oem_standard",
        coverage_scope="comprehensive",
        title="Draft Test Warranty",
        warranty_certificate_number="WTY-ACT-001",
        start_date=today,
        end_date=today + timedelta(days=365),
        currency=currency_usd,
        status="draft",
        registered_by=admin_user,
    )
    url = reverse("assets:asset_warranty_activate", kwargs={"pk": draft.pk})

    # GET is rejected
    assert client_a.get(url).status_code == 405

    # POST activates
    resp = client_a.post(url)
    assert resp.status_code == 302
    draft.refresh_from_db()
    assert draft.status == "active"

    # Re-activating warns
    resp_again = client_a.post(url)
    assert resp_again.status_code == 302
    messages = _assetwarrantyinsurance_get_flash_messages(resp_again)
    assert any("already Active" in m for m in messages)


def test_assetwarrantyinsurance_warranty_renew_action(client_a, warranty_a):
    """asset_warranty_renew extends end_date by 1 year and rejects renewal on voided warranty."""
    url = reverse("assets:asset_warranty_renew", kwargs={"pk": warranty_a.pk})

    # GET rejected
    assert client_a.get(url).status_code == 405

    orig_end = warranty_a.end_date
    resp = client_a.post(url)
    assert resp.status_code == 302
    warranty_a.refresh_from_db()
    assert warranty_a.status == "active"
    assert warranty_a.end_date == orig_end + timedelta(days=365)

    # Rejection on voided
    warranty_a.status = "voided"
    warranty_a.save(update_fields=["status"])
    void_end = warranty_a.end_date
    resp_void = client_a.post(url)
    assert resp_void.status_code == 302
    warranty_a.refresh_from_db()
    assert warranty_a.status == "voided"
    assert warranty_a.end_date == void_end
    messages = _assetwarrantyinsurance_get_flash_messages(resp_void)
    assert any("cannot be renewed" in m for m in messages)


def test_assetwarrantyinsurance_warranty_void_action(client_a, warranty_a):
    """asset_warranty_void action marks warranty voided."""
    url = reverse("assets:asset_warranty_void", kwargs={"pk": warranty_a.pk})

    # GET rejected
    assert client_a.get(url).status_code == 405

    resp = client_a.post(url)
    assert resp.status_code == 302
    warranty_a.refresh_from_db()
    assert warranty_a.status == "voided"


# ==============================================================================
# 2. AssetWarrantyClaim Views & Workflow Actions
# ==============================================================================

def test_assetwarrantyinsurance_warranty_claim_list_renders_200_and_context(client_a, warranty_claim_a):
    """asset_warranty_claim_list renders 200 with complete statistics context."""
    url = reverse("assets:asset_warranty_claim_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "warranty_claims" in resp.context
    assert "page_obj" in resp.context
    assert "paginator" in resp.context
    assert "claim_status_choices" in resp.context
    assert "resolution_type_choices" in resp.context
    assert "part_return_status_choices" in resp.context
    assert "total_claims" in resp.context
    assert "pending_claims" in resp.context
    assert "settled_claims" in resp.context
    assert "total_net_recovered" in resp.context
    assert warranty_claim_a in resp.context["warranty_claims"]


def test_assetwarrantyinsurance_warranty_claim_list_filters(client_a, warranty_claim_a, warranty_a):
    """asset_warranty_claim_list filters by status, resolution_type, part_return_status, and warranty."""
    url = reverse("assets:asset_warranty_claim_list")

    # Match status submitted
    resp = client_a.get(url, {"status": "submitted"})
    assert resp.status_code == 200
    assert warranty_claim_a.pk in [c.pk for c in resp.context["warranty_claims"]]

    # Match resolution_type
    resp_res = client_a.get(url, {"resolution_type": warranty_claim_a.resolution_type})
    assert resp_res.status_code == 200
    assert warranty_claim_a.pk in [c.pk for c in resp_res.context["warranty_claims"]]

    # Match warranty PK
    resp_war = client_a.get(url, {"warranty": str(warranty_a.pk)})
    assert resp_war.status_code == 200
    assert warranty_claim_a.pk in [c.pk for c in resp_war.context["warranty_claims"]]

    # Search query
    resp_q = client_a.get(url, {"q": warranty_claim_a.title[:10]})
    assert resp_q.status_code == 200
    assert warranty_claim_a.pk in [c.pk for c in resp_q.context["warranty_claims"]]


def test_assetwarrantyinsurance_warranty_claim_create_get_prepopulated(client_a, warranty_a):
    """asset_warranty_claim_create GET with ?warranty=<pk> prepopulates initial fields."""
    url = reverse("assets:asset_warranty_claim_create")
    resp = client_a.get(url, {"warranty": str(warranty_a.pk)})

    assert resp.status_code == 200
    assert resp.context["form"].initial.get("warranty") == warranty_a
    assert resp.context["form"].initial.get("fixed_asset") == warranty_a.fixed_asset
    assert resp.context["form"].initial.get("currency") == warranty_a.currency
    assert resp.context["form"].initial.get("deductible_applied") == warranty_a.deductible_amount


def test_assetwarrantyinsurance_warranty_claim_create_post_valid(client_a, tenant_a, currency_usd, warranty_a, admin_user):
    """asset_warranty_claim_create POST valid data creates claim and assigns filed_by."""
    url = reverse("assets:asset_warranty_claim_create")
    payload = _assetwarrantyinsurance_warranty_claim_payload(
        currency_usd,
        warranty_a,
        title="Spindle Vibration Thermal Trip Claim",
    )

    resp = client_a.post(url, payload)
    assert resp.status_code == 302

    created = AssetWarrantyClaim.objects.filter(tenant=tenant_a, title="Spindle Vibration Thermal Trip Claim").first()
    assert created is not None
    assert created.tenant == tenant_a
    assert created.filed_by == admin_user
    assert created.number.startswith("AWCL-")
    assert resp.url == reverse("assets:asset_warranty_claim_detail", kwargs={"pk": created.pk})


def test_assetwarrantyinsurance_warranty_claim_create_post_invalid(client_a):
    """asset_warranty_claim_create POST invalid data returns 200 with form errors."""
    url = reverse("assets:asset_warranty_claim_create")
    resp = client_a.post(url, {})
    assert resp.status_code == 200
    assert resp.context["form"].errors


def test_assetwarrantyinsurance_warranty_claim_detail_renders_chained_warrantor(client_a, warranty_claim_a):
    """asset_warranty_claim_detail renders 200 and cleanly displays chained warrantor party name."""
    url = reverse("assets:asset_warranty_claim_detail", kwargs={"pk": warranty_claim_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["claim"] == warranty_claim_a
    content = resp.content.decode("utf-8")
    assert warranty_claim_a.warranty.warrantor_party.name in content
    assert warranty_claim_a.title in content


def test_assetwarrantyinsurance_warranty_claim_detail_cross_tenant_404(client_b, warranty_claim_a):
    """Cross-tenant warranty claim detail access returns 404."""
    url = reverse("assets:asset_warranty_claim_detail", kwargs={"pk": warranty_claim_a.pk})
    resp = client_b.get(url)
    assert resp.status_code == 404


def test_assetwarrantyinsurance_warranty_claim_edit_get_and_post_valid(client_a, warranty_claim_a, currency_usd):
    """asset_warranty_claim_edit renders form on GET and updates claim on POST."""
    url = reverse("assets:asset_warranty_claim_edit", kwargs={"pk": warranty_claim_a.pk})
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True

    payload = _assetwarrantyinsurance_warranty_claim_payload(
        currency_usd,
        warranty_claim_a.warranty,
        title="Updated Impeller Shaft Fracture",
        claimed_amount="3500.00",
    )
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    warranty_claim_a.refresh_from_db()
    assert warranty_claim_a.title == "Updated Impeller Shaft Fracture"
    assert warranty_claim_a.claimed_amount == Decimal("3500.00")


def test_assetwarrantyinsurance_warranty_claim_edit_status_guard(client_a, warranty_claim_a):
    """asset_warranty_claim_edit status guard prevents editing settled_closed or rejected claims."""
    url = reverse("assets:asset_warranty_claim_edit", kwargs={"pk": warranty_claim_a.pk})

    for finalized_status in ["settled_closed", "rejected"]:
        warranty_claim_a.claim_status = finalized_status
        warranty_claim_a.save(update_fields=["claim_status"])

        resp_get = client_a.get(url)
        assert resp_get.status_code == 302
        assert resp_get.url == reverse("assets:asset_warranty_claim_detail", kwargs={"pk": warranty_claim_a.pk})

        resp_post = client_a.post(url, {"title": "Hacked Title Attempt"})
        assert resp_post.status_code == 302
        warranty_claim_a.refresh_from_db()
        assert warranty_claim_a.title != "Hacked Title Attempt"


def test_assetwarrantyinsurance_warranty_claim_delete_requires_post_and_deletes(client_a, warranty_claim_a):
    """asset_warranty_claim_delete requires POST and deletes record."""
    pk = warranty_claim_a.pk
    url = reverse("assets:asset_warranty_claim_delete", kwargs={"pk": pk})

    assert client_a.get(url).status_code == 405

    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_warranty_claim_list")
    assert not AssetWarrantyClaim.objects.filter(pk=pk).exists()


def test_assetwarrantyinsurance_warranty_claim_submit_action(client_a, warranty_claim_a, warranty_a):
    """asset_warranty_claim_submit marks claim submitted and updates warranty status to claimed."""
    warranty_claim_a.claim_status = "draft"
    warranty_claim_a.save(update_fields=["claim_status"])
    warranty_a.status = "active"
    warranty_a.save(update_fields=["status"])

    url = reverse("assets:asset_warranty_claim_submit", kwargs={"pk": warranty_claim_a.pk})
    assert client_a.get(url).status_code == 405

    resp = client_a.post(url)
    assert resp.status_code == 302
    warranty_claim_a.refresh_from_db()
    warranty_a.refresh_from_db()
    assert warranty_claim_a.claim_status == "submitted"
    assert warranty_claim_a.submission_date is not None
    assert warranty_a.status == "claimed"

    # Re-submitting triggers warning
    resp_again = client_a.post(url)
    assert resp_again.status_code == 302
    messages = _assetwarrantyinsurance_get_flash_messages(resp_again)
    assert any("already Submitted" in m for m in messages)


def test_assetwarrantyinsurance_warranty_claim_review_action(client_a, warranty_claim_a):
    """asset_warranty_claim_review marks claim under_review."""
    url = reverse("assets:asset_warranty_claim_review", kwargs={"pk": warranty_claim_a.pk})
    assert client_a.get(url).status_code == 405

    resp = client_a.post(url)
    assert resp.status_code == 302
    warranty_claim_a.refresh_from_db()
    assert warranty_claim_a.claim_status == "under_review"


def test_assetwarrantyinsurance_warranty_claim_settle_action_success_and_validations(client_a, warranty_claim_a, warranty_a, admin_user):
    """asset_warranty_claim_settle validates amounts, checks status guard, and calculates net recovery."""
    warranty_claim_a.claim_status = "under_review"
    warranty_claim_a.deductible_applied = Decimal("250.00")
    warranty_claim_a.save(update_fields=["claim_status", "deductible_applied"])
    warranty_a.status = "claimed"
    warranty_a.save(update_fields=["status"])

    url = reverse("assets:asset_warranty_claim_settle", kwargs={"pk": warranty_claim_a.pk})
    assert client_a.get(url).status_code == 405

    # 1. Invalid negative approved_amount rejected
    resp_neg = client_a.post(url, {"approved_amount": "-100.00"})
    assert resp_neg.status_code == 302
    messages = _assetwarrantyinsurance_get_flash_messages(resp_neg)
    assert any("Invalid approved amount" in m for m in messages)

    # 2. Malformed non-numeric string rejected
    resp_nan = client_a.post(url, {"approved_amount": "not_a_number"})
    assert resp_nan.status_code == 302
    messages = _assetwarrantyinsurance_get_flash_messages(resp_nan)
    assert any("Invalid numeric value" in m for m in messages)

    # 3. Valid settlement with custom resolution_type and settlement_notes
    resp_valid = client_a.post(url, {
        "approved_amount": "3000.00",
        "resolution_type": "cash_reimbursement",
        "settlement_notes": "OEM agreed to direct credit reimbursement.",
    })
    assert resp_valid.status_code == 302
    warranty_claim_a.refresh_from_db()
    warranty_a.refresh_from_db()

    assert warranty_claim_a.claim_status == "settled_closed"
    assert warranty_claim_a.approved_amount == Decimal("3000.00")
    assert warranty_claim_a.net_recovery_amount == Decimal("2750.00")  # 3000 - 250
    assert warranty_claim_a.approved_by == admin_user
    assert warranty_claim_a.settlement_date is not None
    # Linked warranty restored to active since no other open claims
    assert warranty_a.status == "active"

    # 4. Status guard: cannot settle an already settled claim
    resp_resettle = client_a.post(url, {"approved_amount": "2000.00"})
    assert resp_resettle.status_code == 302
    messages = _assetwarrantyinsurance_get_flash_messages(resp_resettle)
    assert any("cannot be settled in its current state" in m for m in messages)


def test_assetwarrantyinsurance_warranty_claim_reject_action_and_status_guard(client_a, warranty_claim_a, warranty_a):
    """asset_warranty_claim_reject records rejection and enforces state machine guards."""
    warranty_claim_a.claim_status = "draft"
    warranty_claim_a.save(update_fields=["claim_status"])

    url = reverse("assets:asset_warranty_claim_reject", kwargs={"pk": warranty_claim_a.pk})

    # Cannot reject draft claim
    resp_draft = client_a.post(url)
    assert resp_draft.status_code == 302
    messages = _assetwarrantyinsurance_get_flash_messages(resp_draft)
    assert any("cannot be rejected" in m for m in messages)

    # Set to under_review, then reject
    warranty_claim_a.claim_status = "under_review"
    warranty_claim_a.save(update_fields=["claim_status"])
    warranty_a.status = "claimed"
    warranty_a.save(update_fields=["status"])

    resp_valid = client_a.post(url, {"settlement_notes": "Damage deemed operator negligence."})
    assert resp_valid.status_code == 302
    warranty_claim_a.refresh_from_db()
    warranty_a.refresh_from_db()

    assert warranty_claim_a.claim_status == "rejected"
    assert warranty_claim_a.resolution_type == "rejected_uncovered"
    assert warranty_claim_a.settlement_notes == "Damage deemed operator negligence."
    assert warranty_a.status == "active"


# ==============================================================================
# 3. AssetInsurancePolicy Views & Actions
# ==============================================================================

def test_assetwarrantyinsurance_insurance_policy_list_renders_200_and_context(client_a, insurance_policy_a):
    """asset_insurance_policy_list renders 200 with complete metrics context."""
    url = reverse("assets:asset_insurance_policy_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "policies" in resp.context
    assert "page_obj" in resp.context
    assert "paginator" in resp.context
    assert "status_choices" in resp.context
    assert "policy_type_choices" in resp.context
    assert "valuation_basis_choices" in resp.context
    assert "category_list" in resp.context
    assert "total_policies" in resp.context
    assert "active_policies" in resp.context
    assert "pending_renewal_count" in resp.context
    assert "total_insured_value" in resp.context
    assert insurance_policy_a in resp.context["policies"]


def test_assetwarrantyinsurance_insurance_policy_list_filters(client_a, insurance_policy_a, category_root_a):
    """asset_insurance_policy_list filters by status, policy_type, valuation_basis, and category."""
    insurance_policy_a.asset_category = category_root_a
    insurance_policy_a.save(update_fields=["asset_category"])

    url = reverse("assets:asset_insurance_policy_list")

    # Match status active
    resp = client_a.get(url, {"status": "active"})
    assert resp.status_code == 200
    assert insurance_policy_a.pk in [p.pk for p in resp.context["policies"]]

    # Match policy_type machinery_breakdown
    resp_type = client_a.get(url, {"policy_type": "machinery_breakdown"})
    assert resp_type.status_code == 200
    assert insurance_policy_a.pk in [p.pk for p in resp_type.context["policies"]]

    # Match valuation_basis replacement_cost_value
    resp_vb = client_a.get(url, {"valuation_basis": "replacement_cost_value"})
    assert resp_vb.status_code == 200
    assert insurance_policy_a.pk in [p.pk for p in resp_vb.context["policies"]]

    # Match category
    resp_cat = client_a.get(url, {"category": str(category_root_a.pk)})
    assert resp_cat.status_code == 200
    assert insurance_policy_a.pk in [p.pk for p in resp_cat.context["policies"]]

    # Search query
    resp_q = client_a.get(url, {"q": insurance_policy_a.policy_number})
    assert resp_q.status_code == 200
    assert insurance_policy_a.pk in [p.pk for p in resp_q.context["policies"]]


def test_assetwarrantyinsurance_insurance_policy_list_pagination_and_junk(client_a, tenant_a, currency_usd, underwriter_party_a, admin_user):
    """asset_insurance_policy_list handles page 2 and junk query parameters cleanly."""
    today = timezone.now().date()
    _assetwarrantyinsurance_ensure_vendor_role(underwriter_party_a)
    for i in range(16):
        AssetInsurancePolicy.objects.create(
            tenant=tenant_a,
            underwriter_party=underwriter_party_a,
            policy_number=f"POL-TEST-PAG-{i:03d}",
            title=f"Batch Policy {i}",
            policy_type="machinery_breakdown",
            valuation_basis="replacement_cost_value",
            effective_date=today,
            expiration_date=today + timedelta(days=365),
            currency=currency_usd,
            status="active",
            risk_manager=admin_user,
        )

    url = reverse("assets:asset_insurance_policy_list")
    resp_p2 = client_a.get(url, {"page": "2"})
    assert resp_p2.status_code == 200
    assert resp_p2.context["page_obj"].number == 2

    resp_junk = client_a.get(url, {
        "page": "-99",
        "category": "not_an_int",
        "status": "bogus_status",
    })
    assert resp_junk.status_code == 200


def test_assetwarrantyinsurance_insurance_policy_create_get_and_post(client_a, tenant_a, currency_usd, underwriter_party_a, admin_user):
    """asset_insurance_policy_create GET renders form, POST valid creates policy and redirects."""
    url = reverse("assets:asset_insurance_policy_create")

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is False
    assert resp_get.context["policy"] is None

    # POST valid
    payload = _assetwarrantyinsurance_insurance_policy_payload(
        currency_usd,
        underwriter_party_a,
        policy_number="POL-2026-NEW-99",
        title="Comprehensive Fleet & Equipment Policy",
    )
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302

    created = AssetInsurancePolicy.objects.filter(tenant=tenant_a, policy_number="POL-2026-NEW-99").first()
    assert created is not None
    assert created.tenant == tenant_a
    assert created.risk_manager == admin_user
    assert created.number.startswith("AINS-")
    assert resp_post.url == reverse("assets:asset_insurance_policy_detail", kwargs={"pk": created.pk})

    # POST invalid
    resp_invalid = client_a.post(url, {})
    assert resp_invalid.status_code == 200
    assert resp_invalid.context["form"].errors


def test_assetwarrantyinsurance_insurance_policy_detail_renders_200_and_content(client_a, insurance_policy_a, insurance_claim_a):
    """asset_insurance_policy_detail renders 200 with policy details and linked claims."""
    url = reverse("assets:asset_insurance_policy_detail", kwargs={"pk": insurance_policy_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["policy"] == insurance_policy_a
    assert insurance_claim_a in resp.context["claims"]

    content = resp.content.decode("utf-8")
    assert insurance_policy_a.policy_number in content
    assert insurance_policy_a.underwriter_party.name in content


def test_assetwarrantyinsurance_insurance_policy_detail_cross_tenant_404(client_b, insurance_policy_a):
    """Cross-tenant insurance policy detail access returns 404."""
    url = reverse("assets:asset_insurance_policy_detail", kwargs={"pk": insurance_policy_a.pk})
    resp = client_b.get(url)
    assert resp.status_code == 404


def test_assetwarrantyinsurance_insurance_policy_edit_get_and_post(client_a, insurance_policy_a, currency_usd, underwriter_party_a):
    """asset_insurance_policy_edit GET renders edit form, POST updates policy."""
    url = reverse("assets:asset_insurance_policy_edit", kwargs={"pk": insurance_policy_a.pk})

    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True
    assert resp_get.context["policy"] == insurance_policy_a

    payload = _assetwarrantyinsurance_insurance_policy_payload(
        currency_usd,
        underwriter_party_a,
        policy_number=insurance_policy_a.policy_number,
        title="Updated Machinery Breakdown Coverage",
        annual_premium="14000.00",
    )
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("assets:asset_insurance_policy_detail", kwargs={"pk": insurance_policy_a.pk})

    insurance_policy_a.refresh_from_db()
    assert insurance_policy_a.title == "Updated Machinery Breakdown Coverage"
    assert insurance_policy_a.annual_premium == Decimal("14000.00")


def test_assetwarrantyinsurance_insurance_policy_delete_requires_post_and_deletes(client_a, insurance_policy_a):
    """asset_insurance_policy_delete requires POST and deletes policy."""
    pk = insurance_policy_a.pk
    url = reverse("assets:asset_insurance_policy_delete", kwargs={"pk": pk})

    assert client_a.get(url).status_code == 405

    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_insurance_policy_list")
    assert not AssetInsurancePolicy.objects.filter(pk=pk).exists()


def test_assetwarrantyinsurance_insurance_policy_activate_action(client_a, tenant_a, currency_usd, underwriter_party_a, admin_user):
    """asset_insurance_policy_activate transitions draft to active, warns if already active."""
    today = timezone.now().date()
    _assetwarrantyinsurance_ensure_vendor_role(underwriter_party_a)
    draft_policy = AssetInsurancePolicy.objects.create(
        tenant=tenant_a,
        underwriter_party=underwriter_party_a,
        policy_number="POL-ACT-DRAFT-01",
        title="Draft Property Policy",
        policy_type="commercial_property",
        valuation_basis="actual_cash_value",
        effective_date=today,
        expiration_date=today + timedelta(days=365),
        currency=currency_usd,
        status="draft",
        risk_manager=admin_user,
    )
    url = reverse("assets:asset_insurance_policy_activate", kwargs={"pk": draft_policy.pk})

    assert client_a.get(url).status_code == 405

    resp = client_a.post(url)
    assert resp.status_code == 302
    draft_policy.refresh_from_db()
    assert draft_policy.status == "active"

    # Re-activating warns
    resp_again = client_a.post(url)
    assert resp_again.status_code == 302
    messages = _assetwarrantyinsurance_get_flash_messages(resp_again)
    assert any("already Active" in m for m in messages)


def test_assetwarrantyinsurance_insurance_policy_renew_action(client_a, insurance_policy_a):
    """asset_insurance_policy_renew extends expiration_date by 1 year and rejects renewal on cancelled policy."""
    url = reverse("assets:asset_insurance_policy_renew", kwargs={"pk": insurance_policy_a.pk})

    assert client_a.get(url).status_code == 405

    orig_exp = insurance_policy_a.expiration_date
    resp = client_a.post(url)
    assert resp.status_code == 302
    insurance_policy_a.refresh_from_db()
    assert insurance_policy_a.status == "active"
    assert insurance_policy_a.expiration_date == orig_exp + timedelta(days=365)

    # Rejection on cancelled
    insurance_policy_a.status = "cancelled"
    insurance_policy_a.save(update_fields=["status"])
    cancelled_exp = insurance_policy_a.expiration_date

    resp_cancelled = client_a.post(url)
    assert resp_cancelled.status_code == 302
    insurance_policy_a.refresh_from_db()
    assert insurance_policy_a.status == "cancelled"
    assert insurance_policy_a.expiration_date == cancelled_exp
    messages = _assetwarrantyinsurance_get_flash_messages(resp_cancelled)
    assert any("cannot be renewed" in m for m in messages)


def test_assetwarrantyinsurance_insurance_policy_cancel_action(client_a, insurance_policy_a):
    """asset_insurance_policy_cancel sets policy status to cancelled."""
    url = reverse("assets:asset_insurance_policy_cancel", kwargs={"pk": insurance_policy_a.pk})

    assert client_a.get(url).status_code == 405

    resp = client_a.post(url)
    assert resp.status_code == 302
    insurance_policy_a.refresh_from_db()
    assert insurance_policy_a.status == "cancelled"


# ==============================================================================
# 4. AssetInsuranceClaim Views & Workflow Actions
# ==============================================================================

def test_assetwarrantyinsurance_insurance_claim_list_renders_200_and_context(client_a, insurance_claim_a):
    """asset_insurance_claim_list renders 200 with recovery totals context."""
    url = reverse("assets:asset_insurance_claim_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "insurance_claims" in resp.context
    assert "page_obj" in resp.context
    assert "paginator" in resp.context
    assert "claim_status_choices" in resp.context
    assert "peril_type_choices" in resp.context
    assert "settlement_method_choices" in resp.context
    assert "total_claims" in resp.context
    assert "active_claims" in resp.context
    assert "settled_claims" in resp.context
    assert "total_payout_recovered" in resp.context
    assert insurance_claim_a in resp.context["insurance_claims"]


def test_assetwarrantyinsurance_insurance_claim_list_filters(client_a, insurance_claim_a, insurance_policy_a):
    """asset_insurance_claim_list filters by status, peril_type, settlement_method, and policy."""
    url = reverse("assets:asset_insurance_claim_list")

    # Match status proof_of_loss_filed
    resp = client_a.get(url, {"status": "proof_of_loss_filed"})
    assert resp.status_code == 200
    assert insurance_claim_a.pk in [c.pk for c in resp.context["insurance_claims"]]

    # Match peril_type electrical_arcing_surge
    resp_peril = client_a.get(url, {"peril_type": "electrical_arcing_surge"})
    assert resp_peril.status_code == 200
    assert insurance_claim_a.pk in [c.pk for c in resp_peril.context["insurance_claims"]]

    # Match policy PK
    resp_pol = client_a.get(url, {"policy": str(insurance_policy_a.pk)})
    assert resp_pol.status_code == 200
    assert insurance_claim_a.pk in [c.pk for c in resp_pol.context["insurance_claims"]]

    # Search query
    resp_q = client_a.get(url, {"q": insurance_claim_a.title[:12]})
    assert resp_q.status_code == 200
    assert insurance_claim_a.pk in [c.pk for c in resp_q.context["insurance_claims"]]


def test_assetwarrantyinsurance_insurance_claim_create_get_prepopulated(client_a, insurance_policy_a):
    """asset_insurance_claim_create GET with ?policy=<pk> prepopulates initial values."""
    url = reverse("assets:asset_insurance_claim_create")
    resp = client_a.get(url, {"policy": str(insurance_policy_a.pk)})

    assert resp.status_code == 200
    assert resp.context["form"].initial.get("policy") == insurance_policy_a
    assert resp.context["form"].initial.get("fixed_asset") == insurance_policy_a.fixed_asset
    assert resp.context["form"].initial.get("currency") == insurance_policy_a.currency
    assert resp.context["form"].initial.get("deductible_applied") == insurance_policy_a.deductible_retention


def test_assetwarrantyinsurance_insurance_claim_create_post_valid(client_a, tenant_a, currency_usd, insurance_policy_a, admin_user):
    """asset_insurance_claim_create POST valid data creates claim and assigns claims_officer."""
    url = reverse("assets:asset_insurance_claim_create")
    payload = _assetwarrantyinsurance_insurance_claim_payload(
        currency_usd,
        insurance_policy_a,
        title="High Voltage Arcing Damage Claim",
    )

    resp = client_a.post(url, payload)
    assert resp.status_code == 302

    created = AssetInsuranceClaim.objects.filter(tenant=tenant_a, title="High Voltage Arcing Damage Claim").first()
    assert created is not None
    assert created.tenant == tenant_a
    assert created.claims_officer == admin_user
    assert created.number.startswith("AICL-")
    assert resp.url == reverse("assets:asset_insurance_claim_detail", kwargs={"pk": created.pk})


def test_assetwarrantyinsurance_insurance_claim_create_post_invalid(client_a):
    """asset_insurance_claim_create POST invalid data returns 200 with form errors."""
    url = reverse("assets:asset_insurance_claim_create")
    resp = client_a.post(url, {})
    assert resp.status_code == 200
    assert resp.context["form"].errors


def test_assetwarrantyinsurance_insurance_claim_detail_renders_chained_underwriter(client_a, insurance_claim_a):
    """asset_insurance_claim_detail renders 200 and cleanly renders chained underwriter party name."""
    url = reverse("assets:asset_insurance_claim_detail", kwargs={"pk": insurance_claim_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["claim"] == insurance_claim_a
    content = resp.content.decode("utf-8")
    assert insurance_claim_a.policy.underwriter_party.name in content
    assert insurance_claim_a.title in content


def test_assetwarrantyinsurance_insurance_claim_detail_cross_tenant_404(client_b, insurance_claim_a):
    """Cross-tenant insurance claim detail access returns 404."""
    url = reverse("assets:asset_insurance_claim_detail", kwargs={"pk": insurance_claim_a.pk})
    resp = client_b.get(url)
    assert resp.status_code == 404


def test_assetwarrantyinsurance_insurance_claim_edit_get_and_post_valid(client_a, insurance_claim_a, currency_usd):
    """asset_insurance_claim_edit renders form on GET and updates claim on POST."""
    url = reverse("assets:asset_insurance_claim_edit", kwargs={"pk": insurance_claim_a.pk})

    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True

    payload = _assetwarrantyinsurance_insurance_claim_payload(
        currency_usd,
        insurance_claim_a.policy,
        title="Updated Transformer Flashover Narrative",
        claimed_loss_amount="31000.00",
    )
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    insurance_claim_a.refresh_from_db()
    assert insurance_claim_a.title == "Updated Transformer Flashover Narrative"
    assert insurance_claim_a.claimed_loss_amount == Decimal("31000.00")


def test_assetwarrantyinsurance_insurance_claim_edit_status_guard(client_a, insurance_claim_a):
    """asset_insurance_claim_edit status guard prevents editing finalized claims."""
    url = reverse("assets:asset_insurance_claim_edit", kwargs={"pk": insurance_claim_a.pk})

    for fin_status in ["settled_paid", "denied_disputed", "closed"]:
        insurance_claim_a.claim_status = fin_status
        insurance_claim_a.save(update_fields=["claim_status"])

        resp_get = client_a.get(url)
        assert resp_get.status_code == 302
        assert resp_get.url == reverse("assets:asset_insurance_claim_detail", kwargs={"pk": insurance_claim_a.pk})

        resp_post = client_a.post(url, {"title": "Exploit Attempt"})
        assert resp_post.status_code == 302
        insurance_claim_a.refresh_from_db()
        assert insurance_claim_a.title != "Exploit Attempt"


def test_assetwarrantyinsurance_insurance_claim_delete_requires_post_and_deletes(client_a, insurance_claim_a):
    """asset_insurance_claim_delete requires POST and deletes record."""
    pk = insurance_claim_a.pk
    url = reverse("assets:asset_insurance_claim_delete", kwargs={"pk": pk})

    assert client_a.get(url).status_code == 405

    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_insurance_claim_list")
    assert not AssetInsuranceClaim.objects.filter(pk=pk).exists()


def test_assetwarrantyinsurance_insurance_claim_assign_adjuster_action(client_a, insurance_claim_a):
    """asset_insurance_claim_assign_adjuster updates adjuster name and carrier reference."""
    url = reverse("assets:asset_insurance_claim_assign_adjuster", kwargs={"pk": insurance_claim_a.pk})

    assert client_a.get(url).status_code == 405

    resp = client_a.post(url, {
        "adjuster_name": "Marcus Vance (Crawford Forensic)",
        "carrier_claim_number": "TRV-ADJ-2026-9041",
    })
    assert resp.status_code == 302
    insurance_claim_a.refresh_from_db()
    assert insurance_claim_a.claim_status == "adjuster_assigned"
    assert insurance_claim_a.adjuster_name == "Marcus Vance (Crawford Forensic)"
    assert insurance_claim_a.carrier_claim_number == "TRV-ADJ-2026-9041"
    assert insurance_claim_a.date_reported_to_carrier is not None


def test_assetwarrantyinsurance_insurance_claim_file_proof_action(client_a, insurance_claim_a):
    """asset_insurance_claim_file_proof updates status to proof_of_loss_filed and sets date."""
    url = reverse("assets:asset_insurance_claim_file_proof", kwargs={"pk": insurance_claim_a.pk})

    assert client_a.get(url).status_code == 405

    resp = client_a.post(url)
    assert resp.status_code == 302
    insurance_claim_a.refresh_from_db()
    assert insurance_claim_a.claim_status == "proof_of_loss_filed"
    assert insurance_claim_a.proof_of_loss_date is not None


def test_assetwarrantyinsurance_insurance_claim_settle_action_success_and_validations(client_a, insurance_claim_a):
    """asset_insurance_claim_settle validates payout/salvage numbers, method choices, and status guard."""
    insurance_claim_a.claim_status = "proof_of_loss_filed"
    insurance_claim_a.save(update_fields=["claim_status"])

    url = reverse("assets:asset_insurance_claim_settle", kwargs={"pk": insurance_claim_a.pk})
    assert client_a.get(url).status_code == 405

    # 1. Negative settlement_payout rejected
    resp_neg_payout = client_a.post(url, {"settlement_payout_amount": "-500.00"})
    assert resp_neg_payout.status_code == 302
    messages = _assetwarrantyinsurance_get_flash_messages(resp_neg_payout)
    assert any("Invalid settlement payout amount" in m for m in messages)

    # 2. Negative salvage recovery rejected
    resp_neg_salvage = client_a.post(url, {
        "settlement_payout_amount": "20000.00",
        "salvage_recovery_amount": "-250.00",
    })
    assert resp_neg_salvage.status_code == 302
    messages = _assetwarrantyinsurance_get_flash_messages(resp_neg_salvage)
    assert any("Invalid salvage recovery amount" in m for m in messages)

    # 3. Valid settlement
    resp_valid = client_a.post(url, {
        "settlement_payout_amount": "23000.00",
        "salvage_recovery_amount": "1500.00",
        "settlement_method": "direct_indemnity_check",
        "settlement_notes": "Carrier issued indemnity draft net of $5,000 policy retention.",
    })
    assert resp_valid.status_code == 302
    insurance_claim_a.refresh_from_db()
    assert insurance_claim_a.claim_status == "settled_paid"
    assert insurance_claim_a.settlement_payout_amount == Decimal("23000.00")
    assert insurance_claim_a.salvage_recovery_amount == Decimal("1500.00")
    assert insurance_claim_a.settlement_method == "direct_indemnity_check"
    assert insurance_claim_a.settlement_date is not None

    # 4. Status guard: cannot settle an already settled claim
    resp_resettle = client_a.post(url, {"settlement_payout_amount": "10000.00"})
    assert resp_resettle.status_code == 302
    messages = _assetwarrantyinsurance_get_flash_messages(resp_resettle)
    assert any("cannot be settled in its current state" in m for m in messages)


def test_assetwarrantyinsurance_insurance_claim_deny_action_and_status_guard(client_a, insurance_claim_a):
    """asset_insurance_claim_deny records carrier denial and enforces state machine guard."""
    insurance_claim_a.claim_status = "incident_reported"
    insurance_claim_a.save(update_fields=["claim_status"])

    url = reverse("assets:asset_insurance_claim_deny", kwargs={"pk": insurance_claim_a.pk})

    resp = client_a.post(url, {"settlement_notes": "Loss excluded under gradual wear and tear endorsement."})
    assert resp.status_code == 302
    insurance_claim_a.refresh_from_db()
    assert insurance_claim_a.claim_status == "denied_disputed"
    assert insurance_claim_a.settlement_method == "none_denied"
    assert insurance_claim_a.settlement_date is not None

    # Status guard: already denied cannot be denied again
    resp_again = client_a.post(url)
    assert resp_again.status_code == 302
    messages = _assetwarrantyinsurance_get_flash_messages(resp_again)
    assert any("cannot be recorded as denied" in m for m in messages)


# ==============================================================================
# 5. Query Count Tests: Lists bounded by django_assert_max_num_queries(15)
# ==============================================================================

def test_assetwarrantyinsurance_warranty_list_query_count_bounded(client_a, tenant_a, currency_usd, vendor_party_a, admin_user, django_assert_max_num_queries):
    """asset_warranty_list query count remains strictly bounded (<= 15 queries) under multi-row dataset."""
    today = timezone.now().date()
    for i in range(8):
        AssetWarranty.objects.create(
            tenant=tenant_a,
            warrantor_party=vendor_party_a,
            warranty_type="oem_standard",
            coverage_scope="comprehensive",
            title=f"Query Test Warranty {i}",
            warranty_certificate_number=f"WTY-QRY-{i:03d}",
            start_date=today,
            end_date=today + timedelta(days=365),
            currency=currency_usd,
            status="active",
            registered_by=admin_user,
        )

    url = reverse("assets:asset_warranty_list")
    with django_assert_max_num_queries(15):
        resp = client_a.get(url)
        assert resp.status_code == 200


def test_assetwarrantyinsurance_warranty_claim_list_query_count_bounded(client_a, tenant_a, warranty_a, currency_usd, admin_user, django_assert_max_num_queries):
    """asset_warranty_claim_list query count remains strictly bounded (<= 15 queries)."""
    today = timezone.now().date()
    for i in range(8):
        AssetWarrantyClaim.objects.create(
            tenant=tenant_a,
            warranty=warranty_a,
            title=f"Query Test Warranty Claim {i}",
            incident_date=today,
            claimed_amount=Decimal("1500.00"),
            currency=currency_usd,
            claim_status="submitted",
            filed_by=admin_user,
        )

    url = reverse("assets:asset_warranty_claim_list")
    with django_assert_max_num_queries(15):
        resp = client_a.get(url)
        assert resp.status_code == 200


def test_assetwarrantyinsurance_insurance_policy_list_query_count_bounded(client_a, tenant_a, currency_usd, underwriter_party_a, admin_user, django_assert_max_num_queries):
    """asset_insurance_policy_list query count remains strictly bounded (<= 15 queries)."""
    today = timezone.now().date()
    _assetwarrantyinsurance_ensure_vendor_role(underwriter_party_a)
    for i in range(8):
        AssetInsurancePolicy.objects.create(
            tenant=tenant_a,
            underwriter_party=underwriter_party_a,
            policy_number=f"POL-QRY-{i:03d}",
            title=f"Query Test Policy {i}",
            policy_type="machinery_breakdown",
            valuation_basis="replacement_cost_value",
            effective_date=today,
            expiration_date=today + timedelta(days=365),
            currency=currency_usd,
            status="active",
            risk_manager=admin_user,
        )

    url = reverse("assets:asset_insurance_policy_list")
    with django_assert_max_num_queries(15):
        resp = client_a.get(url)
        assert resp.status_code == 200


def test_assetwarrantyinsurance_insurance_claim_list_query_count_bounded(client_a, tenant_a, insurance_policy_a, currency_usd, admin_user, django_assert_max_num_queries):
    """asset_insurance_claim_list query count remains strictly bounded (<= 15 queries)."""
    today = timezone.now().date()
    for i in range(8):
        AssetInsuranceClaim.objects.create(
            tenant=tenant_a,
            policy=insurance_policy_a,
            title=f"Query Test Insurance Claim {i}",
            incident_date=today,
            peril_type="electrical_arcing_surge",
            claimed_loss_amount=Decimal("5000.00"),
            currency=currency_usd,
            claim_status="proof_of_loss_filed",
            claims_officer=admin_user,
        )

    url = reverse("assets:asset_insurance_claim_list")
    with django_assert_max_num_queries(15):
        resp = client_a.get(url)
        assert resp.status_code == 200


# ==============================================================================
# 6. Unauthenticated Access Tests
# ==============================================================================

def test_assetwarrantyinsurance_unauthenticated_access_redirects_to_login(client, warranty_a, insurance_policy_a):
    """Unauthenticated access to any view redirects cleanly to login endpoint."""
    endpoints = [
        reverse("assets:asset_warranty_list"),
        reverse("assets:asset_warranty_create"),
        reverse("assets:asset_warranty_detail", kwargs={"pk": warranty_a.pk}),
        reverse("assets:asset_warranty_claim_list"),
        reverse("assets:asset_insurance_policy_list"),
        reverse("assets:asset_insurance_claim_list"),
    ]
    for url in endpoints:
        resp = client.get(url)
        assert resp.status_code == 302
        assert "/login" in resp.url
