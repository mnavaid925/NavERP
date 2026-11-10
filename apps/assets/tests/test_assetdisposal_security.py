"""Security, multi-tenant isolation, IDOR, and authorization tests for Sub-module 11.9: Asset Disposal & Retirement."""
from decimal import Decimal
import pytest
from django.urls import reverse

from apps.assets.models import (
    AssetDisposalRequest,
    AssetResaleListing,
    AssetTradeIn,
    AssetScrapSalvage,
)


# ==============================================================================
# 1. Multi-Tenant Isolation & IDOR Protection Tests
# ==============================================================================

@pytest.mark.django_db
def test_assetdisposal_idor_detail_and_edit_blocked(client_a, disposal_request_b, resale_listing_b, trade_in_b, scrap_salvage_b):
    # Acme user accessing Globex records -> must 404
    routes = [
        ("assets:asset_disposal_request_detail", disposal_request_b.pk),
        ("assets:asset_disposal_request_edit", disposal_request_b.pk),
        ("assets:asset_resale_listing_detail", resale_listing_b.pk),
        ("assets:asset_resale_listing_edit", resale_listing_b.pk),
        ("assets:asset_trade_in_detail", trade_in_b.pk),
        ("assets:asset_trade_in_edit", trade_in_b.pk),
        ("assets:asset_scrap_salvage_detail", scrap_salvage_b.pk),
        ("assets:asset_scrap_salvage_edit", scrap_salvage_b.pk),
    ]
    for url_name, pk in routes:
        resp = client_a.get(reverse(url_name, kwargs={"pk": pk}))
        assert resp.status_code == 404, f"IDOR vulnerability on {url_name} for pk={pk}"


@pytest.mark.django_db
def test_assetdisposal_idor_actions_blocked(client_a, disposal_request_b, resale_listing_b, trade_in_b, scrap_salvage_b):
    # Acme user triggering action on Globex records -> must 404
    actions = [
        ("assets:asset_disposal_request_submit", disposal_request_b.pk),
        ("assets:asset_disposal_request_appraise", disposal_request_b.pk),
        ("assets:asset_disposal_request_approve", disposal_request_b.pk),
        ("assets:asset_disposal_request_reject", disposal_request_b.pk),
        ("assets:asset_disposal_request_complete", disposal_request_b.pk),
        ("assets:asset_disposal_request_delete", disposal_request_b.pk),
        ("assets:asset_resale_listing_record_bid", resale_listing_b.pk),
        ("assets:asset_resale_listing_accept_sale", resale_listing_b.pk),
        ("assets:asset_resale_listing_mark_paid", resale_listing_b.pk),
        ("assets:asset_resale_listing_mark_delivered", resale_listing_b.pk),
        ("assets:asset_resale_listing_delete", resale_listing_b.pk),
        ("assets:asset_trade_in_surrender", trade_in_b.pk),
        ("assets:asset_trade_in_settle", trade_in_b.pk),
        ("assets:asset_trade_in_delete", trade_in_b.pk),
        ("assets:asset_scrap_salvage_certify_abatement", scrap_salvage_b.pk),
        ("assets:asset_scrap_salvage_record_cod", scrap_salvage_b.pk),
        ("assets:asset_scrap_salvage_settle", scrap_salvage_b.pk),
        ("assets:asset_scrap_salvage_delete", scrap_salvage_b.pk),
    ]
    for url_name, pk in actions:
        resp = client_a.post(reverse(url_name, kwargs={"pk": pk}))
        assert resp.status_code == 404, f"IDOR action vulnerability on {url_name} for pk={pk}"


@pytest.mark.django_db
def test_assetdisposal_list_views_tenant_isolation(client_a, client_b, disposal_request_a, disposal_request_b, resale_listing_a, resale_listing_b, trade_in_a, trade_in_b, scrap_salvage_a, scrap_salvage_b):
    # Verify Acme sees only A
    resp_a = client_a.get(reverse("assets:asset_disposal_request_list"))
    assert disposal_request_a in resp_a.context["disposal_requests"]
    assert disposal_request_b not in resp_a.context["disposal_requests"]

    resp_resale_a = client_a.get(reverse("assets:asset_resale_listing_list"))
    assert resale_listing_a in resp_resale_a.context["resale_listings"]
    assert resale_listing_b not in resp_resale_a.context["resale_listings"]

    resp_trade_a = client_a.get(reverse("assets:asset_trade_in_list"))
    assert trade_in_a in resp_trade_a.context["trade_ins"]
    assert trade_in_b not in resp_trade_a.context["trade_ins"]

    resp_scrap_a = client_a.get(reverse("assets:asset_scrap_salvage_list"))
    assert scrap_salvage_a in resp_scrap_a.context["scrap_salvages"]
    assert scrap_salvage_b not in resp_scrap_a.context["scrap_salvages"]

    # Verify Globex sees only B
    resp_b = client_b.get(reverse("assets:asset_disposal_request_list"))
    assert disposal_request_b in resp_b.context["disposal_requests"]
    assert disposal_request_a not in resp_b.context["disposal_requests"]


# ==============================================================================
# 2. Authorization & RBAC Tests
# ==============================================================================

@pytest.mark.django_db
def test_assetdisposal_login_required(client, disposal_request_a, resale_listing_a, trade_in_a, scrap_salvage_a):
    # Anonymous client accessing routes -> redirected to login (302)
    urls = [
        reverse("assets:asset_disposal_request_list"),
        reverse("assets:asset_disposal_request_create"),
        reverse("assets:asset_disposal_request_detail", kwargs={"pk": disposal_request_a.pk}),
        reverse("assets:asset_resale_listing_list"),
        reverse("assets:asset_resale_listing_create"),
        reverse("assets:asset_trade_in_list"),
        reverse("assets:asset_scrap_salvage_list"),
    ]
    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 302
        assert "/accounts/login" in resp.url or "login" in resp.url


@pytest.mark.django_db
def test_assetdisposal_delete_requires_tenant_admin(member_client, disposal_request_a, resale_listing_a, trade_in_a, scrap_salvage_a):
    # Non-admin member attempts delete -> 403 Forbidden
    deletes = [
        reverse("assets:asset_disposal_request_delete", kwargs={"pk": disposal_request_a.pk}),
        reverse("assets:asset_resale_listing_delete", kwargs={"pk": resale_listing_a.pk}),
        reverse("assets:asset_trade_in_delete", kwargs={"pk": trade_in_a.pk}),
        reverse("assets:asset_scrap_salvage_delete", kwargs={"pk": scrap_salvage_a.pk}),
    ]
    for url in deletes:
        resp = member_client.post(url)
        assert resp.status_code == 403, f"Expected 403 on non-admin delete for {url}"


@pytest.mark.django_db
def test_assetdisposal_approve_requires_tenant_admin(member_client, tenant_a, fixed_asset_a, category_root_a, admin_user):
    req = AssetDisposalRequest.objects.create(
        tenant=tenant_a,
        title="Admin-only Approval Check",
        fixed_asset=fixed_asset_a,
        category=category_root_a,
        requested_by=admin_user,
        disposal_method="resale",
        retirement_reason="technological_obsolescence",
        status="appraised",
    )
    url = reverse("assets:asset_disposal_request_approve", kwargs={"pk": req.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403


# ==============================================================================
# 3. HTTP Verb Safety Tests
# ==============================================================================

@pytest.mark.django_db
def test_assetdisposal_actions_require_post(client_a, disposal_request_a, resale_listing_a, trade_in_a, scrap_salvage_a):
    # GET on POST-only endpoints must return 405 Method Not Allowed
    post_only_urls = [
        reverse("assets:asset_disposal_request_submit", kwargs={"pk": disposal_request_a.pk}),
        reverse("assets:asset_disposal_request_appraise", kwargs={"pk": disposal_request_a.pk}),
        reverse("assets:asset_disposal_request_approve", kwargs={"pk": disposal_request_a.pk}),
        reverse("assets:asset_disposal_request_reject", kwargs={"pk": disposal_request_a.pk}),
        reverse("assets:asset_disposal_request_complete", kwargs={"pk": disposal_request_a.pk}),
        reverse("assets:asset_disposal_request_delete", kwargs={"pk": disposal_request_a.pk}),
        reverse("assets:asset_resale_listing_record_bid", kwargs={"pk": resale_listing_a.pk}),
        reverse("assets:asset_resale_listing_accept_sale", kwargs={"pk": resale_listing_a.pk}),
        reverse("assets:asset_resale_listing_mark_paid", kwargs={"pk": resale_listing_a.pk}),
        reverse("assets:asset_resale_listing_mark_delivered", kwargs={"pk": resale_listing_a.pk}),
        reverse("assets:asset_resale_listing_delete", kwargs={"pk": resale_listing_a.pk}),
        reverse("assets:asset_trade_in_surrender", kwargs={"pk": trade_in_a.pk}),
        reverse("assets:asset_trade_in_settle", kwargs={"pk": trade_in_a.pk}),
        reverse("assets:asset_trade_in_delete", kwargs={"pk": trade_in_a.pk}),
        reverse("assets:asset_scrap_salvage_certify_abatement", kwargs={"pk": scrap_salvage_a.pk}),
        reverse("assets:asset_scrap_salvage_record_cod", kwargs={"pk": scrap_salvage_a.pk}),
        reverse("assets:asset_scrap_salvage_settle", kwargs={"pk": scrap_salvage_a.pk}),
        reverse("assets:asset_scrap_salvage_delete", kwargs={"pk": scrap_salvage_a.pk}),
    ]
    for url in post_only_urls:
        resp = client_a.get(url)
        assert resp.status_code == 405, f"Expected 405 on GET for {url}"


# ==============================================================================
# 4. State Precondition & Mass Assignment Hardening Tests
# ==============================================================================

@pytest.mark.django_db
def test_assetdisposal_cannot_approve_unappraised_request(client_a, tenant_a, fixed_asset_a, category_root_a, admin_user):
    req = AssetDisposalRequest.objects.create(
        tenant=tenant_a,
        title="Unappraised Request",
        fixed_asset=fixed_asset_a,
        category=category_root_a,
        requested_by=admin_user,
        disposal_method="resale",
        retirement_reason="technological_obsolescence",
        status="draft",
    )
    url_approve = reverse("assets:asset_disposal_request_approve", kwargs={"pk": req.pk})
    resp = client_a.post(url_approve)
    assert resp.status_code == 302
    req.refresh_from_db()
    assert req.status == "draft"  # Must remain in draft, not approve


@pytest.mark.django_db
def test_assetdisposal_mass_assignment_status_ignored_in_form(client_a, tenant_a, fixed_asset_a, category_root_a, admin_user):
    req = AssetDisposalRequest.objects.create(
        tenant=tenant_a,
        title="Status Tamper Attempt",
        fixed_asset=fixed_asset_a,
        category=category_root_a,
        requested_by=admin_user,
        disposal_method="resale",
        retirement_reason="technological_obsolescence",
        status="draft",
    )
    url_edit = reverse("assets:asset_disposal_request_edit", kwargs={"pk": req.pk})
    # Attempt to inject status="completed"
    resp = client_a.post(url_edit, {
        "title": "Status Tamper Attempt - Modified",
        "fixed_asset": fixed_asset_a.pk,
        "category": category_root_a.pk,
        "requested_by": admin_user.pk,
        "disposal_method": "resale",
        "retirement_reason": "technological_obsolescence",
        "justification_notes": "Security test attempt to mass-assign status.",
        "status": "completed",
    })
    assert resp.status_code == 302
    req.refresh_from_db()
    assert req.status == "draft"  # View-level or Form-level exclusion prevents mass assignment


# ==============================================================================
# 5. Financial Settlement Anti-Inflation / Idempotency Hardening Tests
# ==============================================================================

@pytest.mark.django_db
def test_assetdisposal_financial_idempotency_hardened(client_a, resale_listing_a, trade_in_a, scrap_salvage_a, disposal_request_a):
    disposal_request_a.actual_gross_proceeds = Decimal("1000.00")
    disposal_request_a.actual_removal_cost = Decimal("200.00")
    disposal_request_a.save()

    # 1. Resale mark paid twice
    url_paid = reverse("assets:asset_resale_listing_mark_paid", kwargs={"pk": resale_listing_a.pk})
    client_a.post(url_paid)
    disposal_request_a.refresh_from_db()
    first_gross = disposal_request_a.actual_gross_proceeds

    # Second execution must not alter amounts
    client_a.post(url_paid)
    disposal_request_a.refresh_from_db()
    assert disposal_request_a.actual_gross_proceeds == first_gross

    # 2. Trade-in settle twice
    trade_in_a.status = "accepted"
    trade_in_a.save()
    url_trade_settle = reverse("assets:asset_trade_in_settle", kwargs={"pk": trade_in_a.pk})
    client_a.post(url_trade_settle)
    disposal_request_a.refresh_from_db()
    second_gross = disposal_request_a.actual_gross_proceeds

    # Second execution must not alter amounts
    client_a.post(url_trade_settle)
    disposal_request_a.refresh_from_db()
    assert disposal_request_a.actual_gross_proceeds == second_gross
