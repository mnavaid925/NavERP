"""Functional view and action workflow tests for Sub-module 11.9: Asset Disposal & Retirement."""
from decimal import Decimal
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.assets.models import (
    AssetDisposalRequest,
    AssetResaleListing,
    AssetTradeIn,
    AssetScrapSalvage,
)


# ==============================================================================
# 1. AssetDisposalRequest View Tests
# ==============================================================================

@pytest.mark.django_db
def test_assetdisposal_request_list_view(client_a, disposal_request_a):
    url = reverse("assets:asset_disposal_request_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "disposal_requests" in resp.context
    assert disposal_request_a in resp.context["disposal_requests"]
    assert "total_requests" in resp.context
    assert "reason_choices" in resp.context


@pytest.mark.django_db
def test_assetdisposal_request_list_view_filtering(client_a, disposal_request_a):
    url = reverse("assets:asset_disposal_request_list")
    # Filter by matching status
    resp = client_a.get(f"{url}?status=approved")
    assert resp.status_code == 200
    assert disposal_request_a in resp.context["disposal_requests"]

    # Filter by non-matching status
    resp_empty = client_a.get(f"{url}?status=draft")
    assert resp_empty.status_code == 200
    assert disposal_request_a not in resp_empty.context["disposal_requests"]


@pytest.mark.django_db
def test_assetdisposal_request_detail_view(client_a, disposal_request_a, resale_listing_a):
    url = reverse("assets:asset_disposal_request_detail", kwargs={"pk": disposal_request_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["disposal_request"] == disposal_request_a
    assert "resale_listings" in resp.context
    assert "trade_ins" in resp.context
    assert "scrap_salvages" in resp.context


@pytest.mark.django_db
def test_assetdisposal_request_create_view(client_a, fixed_asset_a, operational_asset_a, category_root_a):
    url = reverse("assets:asset_disposal_request_create")
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200

    data = {
        "title": "CNC Machining Center Retirement Plan",
        "fixed_asset": fixed_asset_a.pk,
        "operational_asset": operational_asset_a.pk,
        "category": category_root_a.pk,
        "disposal_method": "resale",
        "retirement_reason": "technological_obsolescence",
        "justification_notes": "Equipment to be replaced by high-speed milling cell.",
        "acquisition_cost": "75000.00",
        "accumulated_depreciation": "45000.00",
        "net_book_value": "30000.00",
        "estimated_residual_value": "35000.00",
        "estimated_removal_cost": "2000.00",
    }
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302
    created = AssetDisposalRequest.objects.get(title="CNC Machining Center Retirement Plan")
    assert created.status == "draft"
    assert created.net_book_value == Decimal("30000.00")


@pytest.mark.django_db
def test_assetdisposal_request_edit_view(client_a, tenant_a, fixed_asset_a, category_root_a, admin_user):
    req = AssetDisposalRequest.objects.create(
        tenant=tenant_a,
        title="Draft Press Retirement",
        fixed_asset=fixed_asset_a,
        category=category_root_a,
        requested_by=admin_user,
        disposal_method="scrap_salvage",
        retirement_reason="end_of_life",
        acquisition_cost=Decimal("40000.00"),
        net_book_value=Decimal("10000.00"),
        status="draft",
    )
    url = reverse("assets:asset_disposal_request_edit", kwargs={"pk": req.pk})
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200

    edit_data = {
        "title": "Draft Press Retirement - Updated Title",
        "fixed_asset": fixed_asset_a.pk,
        "category": category_root_a.pk,
        "disposal_method": "scrap_salvage",
        "retirement_reason": "end_of_life",
        "justification_notes": "Updated notes on scrap feasibility.",
        "acquisition_cost": "42000.00",
        "accumulated_depreciation": "30000.00",
        "net_book_value": "12000.00",
        "estimated_residual_value": "4000.00",
        "estimated_removal_cost": "800.00",
    }
    resp_post = client_a.post(url, edit_data)
    assert resp_post.status_code == 302
    req.refresh_from_db()
    assert req.title == "Draft Press Retirement - Updated Title"
    assert req.net_book_value == Decimal("12000.00")


@pytest.mark.django_db
def test_assetdisposal_request_edit_post_approval_blocked(client_a, disposal_request_a):
    # disposal_request_a is 'approved'
    url = reverse("assets:asset_disposal_request_edit", kwargs={"pk": disposal_request_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_disposal_request_detail", kwargs={"pk": disposal_request_a.pk})


@pytest.mark.django_db
def test_assetdisposal_request_delete_view(client_a, tenant_a, fixed_asset_a, category_root_a, admin_user):
    req = AssetDisposalRequest.objects.create(
        tenant=tenant_a,
        title="Temporary Request to Delete",
        fixed_asset=fixed_asset_a,
        category=category_root_a,
        requested_by=admin_user,
        disposal_method="resale",
        retirement_reason="redundant_surplus",
        status="draft",
    )
    url = reverse("assets:asset_disposal_request_delete", kwargs={"pk": req.pk})
    # GET is rejected with 405
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # POST deletes
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert not AssetDisposalRequest.objects.filter(pk=req.pk).exists()


@pytest.mark.django_db
def test_assetdisposal_request_workflow_actions(client_a, tenant_a, fixed_asset_a, category_root_a, admin_user):
    req = AssetDisposalRequest.objects.create(
        tenant=tenant_a,
        title="Full Lifecycle Test Request",
        fixed_asset=fixed_asset_a,
        category=category_root_a,
        requested_by=admin_user,
        disposal_method="resale",
        retirement_reason="technological_obsolescence",
        acquisition_cost=Decimal("60000.00"),
        net_book_value=Decimal("20000.00"),
        status="draft",
    )

    # 1. Submit
    url_submit = reverse("assets:asset_disposal_request_submit", kwargs={"pk": req.pk})
    resp = client_a.post(url_submit)
    assert resp.status_code == 302
    req.refresh_from_db()
    assert req.status == "submitted"

    # 2. Appraise
    url_appraise = reverse("assets:asset_disposal_request_appraise", kwargs={"pk": req.pk})
    appraisal_data = {
        "appraised_by": admin_user.pk,
        "estimated_residual_value": "24000.00",
        "estimated_removal_cost": "1800.00",
        "appraisal_notes": "Formal valuation confirmed.",
    }
    resp = client_a.post(url_appraise, appraisal_data)
    assert resp.status_code == 302
    req.refresh_from_db()
    assert req.status == "appraised"
    assert req.estimated_residual_value == Decimal("24000.00")

    # 3. Approve
    url_approve = reverse("assets:asset_disposal_request_approve", kwargs={"pk": req.pk})
    resp = client_a.post(url_approve)
    assert resp.status_code == 302
    req.refresh_from_db()
    assert req.status == "approved"
    assert req.approved_by == admin_user

    # 4. Complete
    req.actual_gross_proceeds = Decimal("26000.00")
    req.actual_removal_cost = Decimal("1500.00")
    req.save()

    url_complete = reverse("assets:asset_disposal_request_complete", kwargs={"pk": req.pk})
    resp = client_a.post(url_complete)
    assert resp.status_code == 302
    req.refresh_from_db()
    assert req.status == "completed"
    assert req.realized_gain_loss == Decimal("4500.00")
    fixed_asset_a.refresh_from_db()
    assert fixed_asset_a.status == "disposed"


# ==============================================================================
# 2. AssetResaleListing View & Action Tests
# ==============================================================================

@pytest.mark.django_db
def test_assetdisposal_resale_listing_list_view(client_a, resale_listing_a):
    url = reverse("assets:asset_resale_listing_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "resale_listings" in resp.context
    assert resale_listing_a in resp.context["resale_listings"]
    assert "total_listings" in resp.context
    assert "payment_status_choices" in resp.context


@pytest.mark.django_db
def test_assetdisposal_resale_listing_detail_view(client_a, resale_listing_a):
    url = reverse("assets:asset_resale_listing_detail", kwargs={"pk": resale_listing_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["resale_listing"] == resale_listing_a


@pytest.mark.django_db
def test_assetdisposal_resale_listing_create_view(client_a, disposal_request_a, fixed_asset_a):
    today = timezone.now().date()
    url = reverse("assets:asset_resale_listing_create")
    data = {
        "disposal_request": disposal_request_a.pk,
        "fixed_asset": fixed_asset_a.pk,
        "listing_channel": "public_auction",
        "listing_reference": "LOT-AUC-2026-09",
        "listing_date": today.isoformat(),
        "reserve_price": "28000.00",
        "asking_price": "35000.00",
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 302
    listing = AssetResaleListing.objects.get(listing_reference="LOT-AUC-2026-09")
    assert listing.status == "listed"


@pytest.mark.django_db
def test_assetdisposal_resale_listing_actions_and_idempotency(client_a, resale_listing_a, disposal_request_a):
    resale_listing_a.status = "listed"
    resale_listing_a.save()

    # 1. Record Bid
    url_bid = reverse("assets:asset_resale_listing_record_bid", kwargs={"pk": resale_listing_a.pk})
    bid_data = {
        "bid_amount": "38000.00",
        "bidder_name": "Titan Heavy Industries",
        "bidder_email": "titan@example.com",
    }
    resp = client_a.post(url_bid, bid_data)
    assert resp.status_code == 302
    resale_listing_a.refresh_from_db()
    assert resale_listing_a.highest_bid_amount == Decimal("38000.00")

    # 2. Accept Sale
    url_accept = reverse("assets:asset_resale_listing_accept_sale", kwargs={"pk": resale_listing_a.pk})
    sale_data = {
        "final_sale_amount": "38000.00",
        "commission_rate_percent": "5.00",
        "buyer_contact_name": "Titan Heavy Industries",
    }
    resp = client_a.post(url_accept, sale_data)
    assert resp.status_code == 302
    resale_listing_a.refresh_from_db()
    assert resale_listing_a.status == "sold"
    assert resale_listing_a.commission_amount == Decimal("1900.00")

    # 3. Mark Paid (Idempotent Test)
    disposal_request_a.refresh_from_db()
    initial_proceeds = disposal_request_a.actual_gross_proceeds or Decimal("0.00")

    url_paid = reverse("assets:asset_resale_listing_mark_paid", kwargs={"pk": resale_listing_a.pk})
    resp1 = client_a.post(url_paid)
    assert resp1.status_code == 302
    resale_listing_a.refresh_from_db()
    assert resale_listing_a.payment_status == "paid"

    disposal_request_a.refresh_from_db()
    assert disposal_request_a.actual_gross_proceeds == initial_proceeds + Decimal("38000.00")

    # Repeat Mark Paid - must NOT increment parent proceeds again
    resp2 = client_a.post(url_paid)
    assert resp2.status_code == 302
    disposal_request_a.refresh_from_db()
    assert disposal_request_a.actual_gross_proceeds == initial_proceeds + Decimal("38000.00")


# ==============================================================================
# 3. AssetTradeIn View & Action Tests
# ==============================================================================

@pytest.mark.django_db
def test_assetdisposal_trade_in_list_view(client_a, trade_in_a):
    url = reverse("assets:asset_trade_in_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "trade_ins" in resp.context
    assert trade_in_a in resp.context["trade_ins"]
    assert "total_trade_ins" in resp.context


@pytest.mark.django_db
def test_assetdisposal_trade_in_detail_view(client_a, trade_in_a):
    url = reverse("assets:asset_trade_in_detail", kwargs={"pk": trade_in_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["trade_in"] == trade_in_a


@pytest.mark.django_db
def test_assetdisposal_trade_in_create_view(client_a, disposal_request_a, fixed_asset_a, vendor_party_a):
    today = timezone.now().date()
    url = reverse("assets:asset_trade_in_create")
    data = {
        "disposal_request": disposal_request_a.pk,
        "retired_fixed_asset": fixed_asset_a.pk,
        "vendor": vendor_party_a.pk,
        "agreement_number": "AGR-TRD-VIEW-01",
        "agreement_date": today.isoformat(),
        "handover_due_date": (today + timezone.timedelta(days=10)).isoformat(),
        "dealer_appraised_value": "16000.00",
        "trade_in_allowance": "14000.00",
        "over_allowance_amount": "0.00",
        "replacement_asset_cost": "75000.00",
        "gain_loss_deferred": "0.00",
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 302
    trade_in = AssetTradeIn.objects.get(agreement_number="AGR-TRD-VIEW-01")
    assert trade_in.status == "proposed"


@pytest.mark.django_db
def test_assetdisposal_trade_in_actions_and_idempotency(client_a, trade_in_a, disposal_request_a):
    # 1. Surrender
    url_surrender = reverse("assets:asset_trade_in_surrender", kwargs={"pk": trade_in_a.pk})
    resp = client_a.post(url_surrender)
    assert resp.status_code == 302
    trade_in_a.refresh_from_db()
    assert trade_in_a.status == "equipment_surrendered"

    # 2. Settle (Idempotent Test)
    disposal_request_a.refresh_from_db()
    initial_proceeds = disposal_request_a.actual_gross_proceeds or Decimal("0.00")

    url_settle = reverse("assets:asset_trade_in_settle", kwargs={"pk": trade_in_a.pk})
    resp1 = client_a.post(url_settle)
    assert resp1.status_code == 302
    trade_in_a.refresh_from_db()
    assert trade_in_a.status == "credit_settled"

    disposal_request_a.refresh_from_db()
    assert disposal_request_a.actual_gross_proceeds == initial_proceeds + trade_in_a.trade_in_allowance

    # Repeat Settle - must NOT duplicate allowance onto parent disposal request
    resp2 = client_a.post(url_settle)
    assert resp2.status_code == 302
    disposal_request_a.refresh_from_db()
    assert disposal_request_a.actual_gross_proceeds == initial_proceeds + trade_in_a.trade_in_allowance


# ==============================================================================
# 4. AssetScrapSalvage View & Action Tests
# ==============================================================================

@pytest.mark.django_db
def test_assetdisposal_scrap_salvage_list_view(client_a, scrap_salvage_a):
    url = reverse("assets:asset_scrap_salvage_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "scrap_salvages" in resp.context
    assert scrap_salvage_a in resp.context["scrap_salvages"]
    assert "total_scraps" in resp.context
    assert "recycler_list" in resp.context


@pytest.mark.django_db
def test_assetdisposal_scrap_salvage_detail_view(client_a, scrap_salvage_a):
    url = reverse("assets:asset_scrap_salvage_detail", kwargs={"pk": scrap_salvage_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["scrap_salvage"] == scrap_salvage_a


@pytest.mark.django_db
def test_assetdisposal_scrap_salvage_create_view(client_a, disposal_request_a, fixed_asset_a, vendor_party_a, admin_user):
    today = timezone.now().date()
    url = reverse("assets:asset_scrap_salvage_create")
    data = {
        "disposal_request": disposal_request_a.pk,
        "fixed_asset": fixed_asset_a.pk,
        "recycler_partner": vendor_party_a.pk,
        "supervisor": admin_user.pk,
        "scrap_method": "shredding_recycling",
        "decommissioning_date": today.isoformat(),
        "total_scrap_weight_kg": "750.00",
        "ferrous_weight_kg": "700.00",
        "non_ferrous_weight_kg": "50.00",
        "e_waste_weight_kg": "0.00",
        "salvage_proceeds": "1200.00",
        "dismantling_cost": "250.00",
        "sanitization_method": "none",
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 302
    job = AssetScrapSalvage.objects.get(fixed_asset=fixed_asset_a, scrap_method="shredding_recycling")
    assert job.status == "dismantling"


@pytest.mark.django_db
def test_assetdisposal_scrap_salvage_actions_and_idempotency(client_a, scrap_salvage_a, disposal_request_a):
    today = timezone.now().date()

    # 1. Certify Abatement
    url_abatement = reverse("assets:asset_scrap_salvage_certify_abatement", kwargs={"pk": scrap_salvage_a.pk})
    resp = client_a.post(url_abatement, {
        "epa_manifest_number": "EPA-DOC-VIEW-99",
        "abatement_notes": "Decontamination completed.",
    })
    assert resp.status_code == 302
    scrap_salvage_a.refresh_from_db()
    assert scrap_salvage_a.status == "scrap_transferred"

    # 2. Record CoD
    scrap_salvage_a.cod_number = ""
    scrap_salvage_a.save()
    url_cod = reverse("assets:asset_scrap_salvage_record_cod", kwargs={"pk": scrap_salvage_a.pk})
    resp = client_a.post(url_cod, {
        "cod_number": "COD-CERT-VIEW-88",
        "cod_issue_date": today.isoformat(),
        "cod_issuing_agency": "Environmental Waste Authority",
    })
    assert resp.status_code == 302
    scrap_salvage_a.refresh_from_db()
    assert scrap_salvage_a.status == "certified_destroyed"

    # 3. Settle (Idempotent Test)
    disposal_request_a.refresh_from_db()
    initial_proceeds = disposal_request_a.actual_gross_proceeds or Decimal("0.00")
    initial_removal_cost = disposal_request_a.actual_removal_cost or Decimal("0.00")

    url_settle = reverse("assets:asset_scrap_salvage_settle", kwargs={"pk": scrap_salvage_a.pk})
    resp1 = client_a.post(url_settle)
    assert resp1.status_code == 302
    scrap_salvage_a.refresh_from_db()
    assert scrap_salvage_a.status == "settled"

    disposal_request_a.refresh_from_db()
    assert disposal_request_a.actual_gross_proceeds == initial_proceeds + scrap_salvage_a.salvage_proceeds
    assert disposal_request_a.actual_removal_cost == initial_removal_cost + scrap_salvage_a.dismantling_cost

    # Repeat Settle - must NOT duplicate proceeds or expenses on parent disposal request
    resp2 = client_a.post(url_settle)
    assert resp2.status_code == 302
    disposal_request_a.refresh_from_db()
    assert disposal_request_a.actual_gross_proceeds == initial_proceeds + scrap_salvage_a.salvage_proceeds
    assert disposal_request_a.actual_removal_cost == initial_removal_cost + scrap_salvage_a.dismantling_cost
