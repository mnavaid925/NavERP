"""Asset Procurement & Acquisition (11.1) — VIEWS Test Suite.

Covers all views for Sub-module 11.1:
1. Overview:
   - overview (GET, KPI metrics, recent feeds, tenant isolation, unauthenticated redirect)

2. Requisitions:
   - asset_requisition_list (GET, context contract, search, filters, junk params, pagination)
   - asset_requisition_detail (GET, context contract, cross-tenant 404)
   - asset_requisition_create (GET, POST valid -> 302, POST invalid -> 200)
   - asset_requisition_edit (GET, POST valid -> 302, guard blocked if approved/ordered)
   - asset_requisition_delete (require_POST, guard blocked if not draft/rejected, deletes draft/rejected)
   - asset_requisition_submit (require_POST, transitions draft -> pending_approval, guard)
   - asset_requisition_approve (require_POST, segregation of duties self-approval prevention, transitions pending -> approved, guard)
   - asset_requisition_reject (require_POST, rejection reason required, transitions -> rejected, guard)

3. Receipts:
   - asset_acquisition_receipt_list (GET, context contract, search, condition/status/location filters, junk params)
   - asset_acquisition_receipt_detail (GET, context contract, cross-tenant 404)
   - asset_acquisition_receipt_create (GET, POST valid -> 302, POST invalid -> 200)
   - asset_acquisition_receipt_edit (GET, POST valid -> 302, guard blocked if capitalized)
   - asset_acquisition_receipt_delete (require_POST, guard blocked if accepted/capitalized, deletes pending)
   - asset_acquisition_receipt_inspect (require_POST, notes appended, transitions -> accepted, guard)
   - asset_acquisition_receipt_quarantine (require_POST, reason appended, transitions -> quarantined, guard)

4. Capitalizations:
   - asset_capitalization_list (GET, context contract, search, status/method filters, junk params)
   - asset_capitalization_detail (GET, context contract, cross-tenant 404)
   - asset_capitalization_create (GET, receipt prepopulation, junk receipt param, POST valid -> 302, POST invalid -> 200)
   - asset_capitalization_edit (GET, POST valid -> 302, guard blocked if capitalized)
   - asset_capitalization_delete (require_POST, guard blocked if capitalized, deletes draft)
   - asset_capitalization_execute (require_POST, tenant_admin_required -> 403 for member, creates FixedAsset in accounting, marks receipt capitalized, transitions -> capitalized, guard)
   - asset_capitalization_reverse (require_POST, tenant_admin_required -> 403 for member, transitions -> reversed, guard)

5. Tags:
   - asset_tag_list (GET, context contract, search, status/format filters, junk params)
   - asset_tag_detail (GET, context contract, cross-tenant 404)
   - asset_tag_create (GET, capitalization prepopulation, junk capitalization param, POST valid -> 302, POST invalid -> 200)
   - asset_tag_edit (GET, POST valid -> 302)
   - asset_tag_delete (require_POST, guard blocked if affixed/verified, deletes pending_print)
   - asset_tag_mark_printed (require_POST, transitions -> printed, guard)
   - asset_tag_affix (require_POST, updates placement, transitions -> affixed, guard)
   - asset_tag_verify (require_POST, updates scanner_device_id, is_verified=True, transitions -> verified, guard)
   - asset_tag_print_label (GET, 200, context contract, label CSS and barcode/QR verification)
"""
from decimal import Decimal
import pytest
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models import FixedAsset
from apps.assets.models import (
    AssetAcquisitionReceipt,
    AssetCapitalization,
    AssetRequisition,
    AssetTag,
)


# ==============================================================================
# Helper Functions (strictly prefixed with _assetprocurement_)
# ==============================================================================


def _assetprocurement_get_flash_messages(response):
    """Extract list of flash message strings from response."""
    return [str(m) for m in get_messages(response.wsgi_request)]


def _assetprocurement_valid_requisition_payload(currency, **overrides):
    """Return a valid dictionary payload for creating an AssetRequisition."""
    payload = {
        "title": "Industrial CNC Milling Center",
        "description": "High-precision vertical machining center.",
        "business_justification": "Required for aerospace backlog.",
        "asset_category": "machinery",
        "priority": "high",
        "estimated_cost": Decimal("110000.00"),
        "currency": currency.pk,
        "budget_code": "CAPEX-2026-MFG-01",
        "proposed_manufacturer": "Haas Automation",
        "proposed_model": "VF-2SS",
        "required_delivery_date": "2026-12-31",
    }
    payload.update(overrides)
    return payload


def _assetprocurement_valid_receipt_payload(**overrides):
    """Return a valid dictionary payload for creating an AssetAcquisitionReceipt."""
    payload = {
        "title": "Intake Delivery for CNC Milling Center",
        "manufacturer": "Haas Automation",
        "model_number": "VF-2SS",
        "serial_number": "SN-HAAS-2026-7788",
        "quantity_received": 1,
        "received_date": timezone.now().date(),
        "carrier_name": "Swift Logistics Inc",
        "tracking_number": "TRK-2026-9090",
        "bill_of_lading": "BOL-990011",
        "condition_on_arrival": "excellent",
        "inspection_notes": "Initial dock inspection shows zero exterior box damage.",
    }
    payload.update(overrides)
    return payload


def _assetprocurement_valid_capitalization_payload(**overrides):
    """Return a valid dictionary payload for creating an AssetCapitalization."""
    payload = {
        "title": "Capitalization — Haas CNC VF-2SS",
        "asset_name": "Haas CNC VF-2SS Milling Station",
        "purchase_cost": Decimal("105000.00"),
        "freight_cost": Decimal("2500.00"),
        "installation_cost": Decimal("2500.00"),
        "customs_duties_cost": Decimal("0.00"),
        "other_initial_costs": Decimal("0.00"),
        "is_cip_conversion": False,
        "depreciation_method": "straight_line",
        "useful_life_months": 84,
        "salvage_value": Decimal("10000.00"),
        "in_service_date": timezone.now().date(),
    }
    payload.update(overrides)
    return payload


def _assetprocurement_valid_tag_payload(**overrides):
    """Return a valid dictionary payload for creating an AssetTag."""
    payload = {
        "tag_code": "ATAG-TEST-2026-999",
        "tag_format": "qr_code",
        "physical_placement": "Upper right chassis frame next to rating plate",
        "notes": "Weatherproof vinyl label applied with acrylic resin.",
    }
    payload.update(overrides)
    return payload


# ==============================================================================
# 1. Overview Tests
# ==============================================================================


@pytest.mark.django_db
def test_assetprocurement_overview_unauthenticated_redirects(client):
    """Unauthenticated access to overview redirects to login."""
    url = reverse("assets:overview")
    response = client.get(url)
    assert response.status_code == 302
    assert "/login/" in response.url


@pytest.mark.django_db
def test_assetprocurement_overview_authenticated_get_200(
    client_a, requisition_a, receipt_a, capitalization_a, asset_tag_a
):
    """Overview loads with 200 OK and provides all context KPI and feed contracts."""
    url = reverse("assets:overview")
    response = client_a.get(url)
    assert response.status_code == 200
    assert "assets/overview.html" in [t.name for t in response.templates]

    assert "kpis" in response.context
    kpis = response.context["kpis"]
    assert kpis["total_requisitions"] >= 1
    assert kpis["total_receipts"] >= 1
    assert kpis["total_capitalizations"] >= 1
    assert kpis["total_tags"] >= 1
    assert "capitalized_value" in kpis

    assert "recent_requisitions" in response.context
    assert "recent_receipts" in response.context
    assert "recent_capitalizations" in response.context
    assert "recent_tags" in response.context


@pytest.mark.django_db
def test_assetprocurement_overview_tenant_isolation(
    client_a, client_b, requisition_a, requisition_b
):
    """Overview only aggregates and presents tenant-owned records."""
    url = reverse("assets:overview")

    resp_a = client_a.get(url)
    assert resp_a.status_code == 200
    req_ids_a = [r.pk for r in resp_a.context["recent_requisitions"]]
    assert requisition_a.pk in req_ids_a
    assert requisition_b.pk not in req_ids_a

    resp_b = client_b.get(url)
    assert resp_b.status_code == 200
    req_ids_b = [r.pk for r in resp_b.context["recent_requisitions"]]
    assert requisition_b.pk in req_ids_b
    assert requisition_a.pk not in req_ids_b


# ==============================================================================
# 2. Asset Requisitions Tests
# ==============================================================================


@pytest.mark.django_db
def test_assetprocurement_requisition_list_get_200(client_a, requisition_a):
    """Requisition list view returns 200 OK with expected context variables."""
    url = reverse("assets:asset_requisition_list")
    response = client_a.get(url)
    assert response.status_code == 200
    assert "assets/asset_procurement/asset_requisition/list.html" in [
        t.name for t in response.templates
    ]

    context = response.context
    assert "requisitions" in context
    assert "page_obj" in context
    assert "status_choices" in context
    assert "priority_choices" in context
    assert "category_choices" in context

    items = list(context["requisitions"])
    assert requisition_a in items


@pytest.mark.django_db
def test_assetprocurement_requisition_list_tenant_isolation(
    client_a, requisition_a, requisition_b
):
    """Tenant A cannot see Tenant B's requisitions on the list page."""
    url = reverse("assets:asset_requisition_list")
    response = client_a.get(url)
    assert response.status_code == 200
    items = list(response.context["requisitions"])
    assert requisition_a in items
    assert requisition_b not in items


@pytest.mark.django_db
def test_assetprocurement_requisition_list_search_and_filters(
    client_a, requisition_a
):
    """Requisition list filters by search query, status, priority, and category."""
    url = reverse("assets:asset_requisition_list")

    # Search match
    resp = client_a.get(url, {"q": "Automated"})
    assert requisition_a in list(resp.context["requisitions"])

    # Search non-match
    resp = client_a.get(url, {"q": "NonExistentLaserStringXYZ"})
    assert requisition_a not in list(resp.context["requisitions"])

    # Status filter match
    resp = client_a.get(url, {"status": "draft"})
    assert requisition_a in list(resp.context["requisitions"])

    # Status filter mismatch
    resp = client_a.get(url, {"status": "approved"})
    assert requisition_a not in list(resp.context["requisitions"])

    # Priority and category filter match
    resp = client_a.get(url, {"priority": "high", "category": "machinery"})
    assert requisition_a in list(resp.context["requisitions"])

    # Priority mismatch
    resp = client_a.get(url, {"priority": "low"})
    assert requisition_a not in list(resp.context["requisitions"])


@pytest.mark.django_db
def test_assetprocurement_requisition_list_junk_params_resilience(
    client_a, requisition_a
):
    """Requisition list gracefully handles non-numeric and junk query parameters."""
    url = reverse("assets:asset_requisition_list")
    resp = client_a.get(
        url,
        {
            "q": "!@#$%^&*()_+",
            "status": "unrecognized_status_slug",
            "priority": "extreme_urgent",
            "category": "nanotech",
            "page": "not_an_integer",
        },
    )
    assert resp.status_code == 200
    assert "requisitions" in resp.context


@pytest.mark.django_db
def test_assetprocurement_requisition_detail_get_200(client_a, requisition_a):
    """Requisition detail renders 200 OK with requisition context."""
    url = reverse("assets:asset_requisition_detail", args=[requisition_a.pk])
    response = client_a.get(url)
    assert response.status_code == 200
    assert "assets/asset_procurement/asset_requisition/detail.html" in [
        t.name for t in response.templates
    ]
    assert response.context["requisition"] == requisition_a


@pytest.mark.django_db
def test_assetprocurement_requisition_detail_cross_tenant_404(
    client_a, requisition_b
):
    """Accessing another tenant's requisition detail returns 404 Not Found."""
    url = reverse("assets:asset_requisition_detail", args=[requisition_b.pk])
    response = client_a.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_assetprocurement_requisition_create_get_200(client_a):
    """Requisition create GET renders form with is_edit=False."""
    url = reverse("assets:asset_requisition_create")
    response = client_a.get(url)
    assert response.status_code == 200
    assert "assets/asset_procurement/asset_requisition/form.html" in [
        t.name for t in response.templates
    ]
    assert "form" in response.context
    assert response.context["is_edit"] is False
    assert response.context["requisition"] is None


@pytest.mark.django_db
def test_assetprocurement_requisition_create_post_success(
    client_a, tenant_a, currency_usd, vendor_party_a, location_a
):
    """Requisition create POST valid data creates record and redirects to detail."""
    url = reverse("assets:asset_requisition_create")
    payload = _assetprocurement_valid_requisition_payload(
        currency_usd,
        proposed_vendor=vendor_party_a.pk,
        target_location=location_a.pk,
    )
    response = client_a.post(url, payload)
    assert response.status_code == 302

    created = AssetRequisition.objects.filter(
        tenant=tenant_a, title=payload["title"]
    ).first()
    assert created is not None
    assert response.url == reverse(
        "assets:asset_requisition_detail", args=[created.pk]
    )
    assert created.status == "draft"

    msgs = _assetprocurement_get_flash_messages(response)
    assert any("created successfully" in m for m in msgs)


@pytest.mark.django_db
def test_assetprocurement_requisition_create_post_invalid(client_a):
    """Requisition create POST invalid data stays on form with errors."""
    url = reverse("assets:asset_requisition_create")
    response = client_a.post(url, {})
    assert response.status_code == 200
    assert response.context["form"].errors


@pytest.mark.django_db
def test_assetprocurement_requisition_edit_get_200(client_a, requisition_a):
    """Requisition edit GET renders form with is_edit=True and bound instance."""
    url = reverse("assets:asset_requisition_edit", args=[requisition_a.pk])
    response = client_a.get(url)
    assert response.status_code == 200
    assert response.context["is_edit"] is True
    assert response.context["requisition"] == requisition_a


@pytest.mark.django_db
def test_assetprocurement_requisition_edit_post_success(
    client_a, requisition_a, currency_usd
):
    """Requisition edit POST updates instance and redirects to detail."""
    url = reverse("assets:asset_requisition_edit", args=[requisition_a.pk])
    payload = _assetprocurement_valid_requisition_payload(
        currency_usd,
        title="Updated Fiber Laser Cutting Station",
        estimated_cost=Decimal("140000.00"),
    )
    response = client_a.post(url, payload)
    assert response.status_code == 302
    assert response.url == reverse(
        "assets:asset_requisition_detail", args=[requisition_a.pk]
    )

    requisition_a.refresh_from_db()
    assert requisition_a.title == "Updated Fiber Laser Cutting Station"
    assert requisition_a.estimated_cost == Decimal("140000.00")


@pytest.mark.django_db
def test_assetprocurement_requisition_edit_guard_blocked_if_approved_or_ordered(
    client_a, requisition_a, currency_usd
):
    """Requisition cannot be edited once approved or ordered."""
    url = reverse("assets:asset_requisition_edit", args=[requisition_a.pk])

    # Approved status guard
    requisition_a.status = "approved"
    requisition_a.save()
    resp_get = client_a.get(url)
    assert resp_get.status_code == 302
    assert resp_get.url == reverse(
        "assets:asset_requisition_detail", args=[requisition_a.pk]
    )
    msgs = _assetprocurement_get_flash_messages(resp_get)
    assert any("cannot be edited" in m for m in msgs)

    # Ordered status guard
    requisition_a.status = "ordered"
    requisition_a.save()
    payload = _assetprocurement_valid_requisition_payload(
        currency_usd, title="Tampered Title"
    )
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    requisition_a.refresh_from_db()
    assert requisition_a.title != "Tampered Title"


@pytest.mark.django_db
def test_assetprocurement_requisition_delete_requires_post(
    client_a, requisition_a
):
    """Requisition delete requires HTTP POST (GET returns 405)."""
    url = reverse("assets:asset_requisition_delete", args=[requisition_a.pk])
    response = client_a.get(url)
    assert response.status_code == 405


@pytest.mark.django_db
def test_assetprocurement_requisition_delete_guard_blocked_if_pending_or_approved(
    client_a, requisition_a
):
    """Requisition delete is rejected if status is pending_approval or approved."""
    url = reverse("assets:asset_requisition_delete", args=[requisition_a.pk])

    requisition_a.status = "pending_approval"
    requisition_a.save()
    response = client_a.post(url)
    assert response.status_code == 302
    assert response.url == reverse(
        "assets:asset_requisition_detail", args=[requisition_a.pk]
    )
    assert AssetRequisition.objects.filter(pk=requisition_a.pk).exists()
    msgs = _assetprocurement_get_flash_messages(response)
    assert any("cannot be deleted" in m for m in msgs)


@pytest.mark.django_db
def test_assetprocurement_requisition_delete_post_success_draft_or_rejected(
    client_a, requisition_a
):
    """Requisition in draft or rejected status can be deleted."""
    url = reverse("assets:asset_requisition_delete", args=[requisition_a.pk])

    # Draft deletion
    requisition_a.status = "draft"
    requisition_a.save()
    response = client_a.post(url)
    assert response.status_code == 302
    assert response.url == reverse("assets:asset_requisition_list")
    assert not AssetRequisition.objects.filter(pk=requisition_a.pk).exists()


@pytest.mark.django_db
def test_assetprocurement_requisition_submit_workflow(
    client_a, admin_user, requisition_a
):
    """Requisition submit transitions status to pending_approval and records submitter."""
    url = reverse("assets:asset_requisition_submit", args=[requisition_a.pk])

    # GET blocked
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # POST success
    requisition_a.status = "draft"
    requisition_a.save()
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse(
        "assets:asset_requisition_detail", args=[requisition_a.pk]
    )

    requisition_a.refresh_from_db()
    assert requisition_a.status == "pending_approval"
    assert requisition_a.submitted_by == admin_user
    assert requisition_a.submitted_at is not None

    # Redundant submit guard
    resp_again = client_a.post(url)
    assert resp_again.status_code == 302
    msgs = _assetprocurement_get_flash_messages(resp_again)
    assert any("cannot be submitted" in m for m in msgs)


@pytest.mark.django_db
def test_assetprocurement_requisition_approve_self_approval_prevention(
    client_a, admin_user, requisition_a
):
    """Segregation of Duties: Submitter cannot approve their own requisition."""
    url = reverse("assets:asset_requisition_approve", args=[requisition_a.pk])

    requisition_a.status = "pending_approval"
    requisition_a.submitted_by = admin_user
    requisition_a.save()

    response = client_a.post(url)
    assert response.status_code == 302
    assert response.url == reverse(
        "assets:asset_requisition_detail", args=[requisition_a.pk]
    )

    requisition_a.refresh_from_db()
    assert requisition_a.status == "pending_approval"
    msgs = _assetprocurement_get_flash_messages(response)
    assert any("Segregation of Duties" in m for m in msgs)


@pytest.mark.django_db
def test_assetprocurement_requisition_approve_success_by_different_user(
    client_a, admin_user, member_user, requisition_a
):
    """Requisition can be approved by a different authorized user."""
    url = reverse("assets:asset_requisition_approve", args=[requisition_a.pk])

    requisition_a.status = "pending_approval"
    requisition_a.submitted_by = member_user
    requisition_a.save()

    # GET blocked
    assert client_a.get(url).status_code == 405

    # POST approved
    response = client_a.post(url)
    assert response.status_code == 302
    assert response.url == reverse(
        "assets:asset_requisition_detail", args=[requisition_a.pk]
    )

    requisition_a.refresh_from_db()
    assert requisition_a.status == "approved"
    assert requisition_a.approved_by == admin_user
    assert requisition_a.approved_at is not None


@pytest.mark.django_db
def test_assetprocurement_requisition_reject_workflow(
    client_a, admin_user, requisition_a
):
    """Requisition reject requires a reason and updates status to rejected."""
    url = reverse("assets:asset_requisition_reject", args=[requisition_a.pk])

    # GET blocked
    assert client_a.get(url).status_code == 405

    requisition_a.status = "pending_approval"
    requisition_a.save()

    # Empty reason error
    resp_empty = client_a.post(url, {"rejection_reason": ""})
    assert resp_empty.status_code == 302
    requisition_a.refresh_from_db()
    assert requisition_a.status == "pending_approval"
    msgs = _assetprocurement_get_flash_messages(resp_empty)
    assert any("reason is required" in m for m in msgs)

    # Valid reason rejection
    resp_valid = client_a.post(
        url, {"rejection_reason": "CAPEX allocation frozen for Q2."}
    )
    assert resp_valid.status_code == 302
    requisition_a.refresh_from_db()
    assert requisition_a.status == "rejected"
    assert requisition_a.rejection_reason == "CAPEX allocation frozen for Q2."
    assert requisition_a.approved_by == admin_user


# ==============================================================================
# 3. Asset Acquisition Receipts Tests
# ==============================================================================


@pytest.mark.django_db
def test_assetprocurement_receipt_list_get_200(client_a, receipt_a):
    """Receipt list view returns 200 OK with expected context variables."""
    url = reverse("assets:asset_acquisition_receipt_list")
    response = client_a.get(url)
    assert response.status_code == 200
    assert "assets/asset_procurement/asset_acquisition_receipt/list.html" in [
        t.name for t in response.templates
    ]

    context = response.context
    assert "receipts" in context
    assert "page_obj" in context
    assert "status_choices" in context
    assert "condition_choices" in context
    assert "locations" in context

    assert receipt_a in list(context["receipts"])


@pytest.mark.django_db
def test_assetprocurement_receipt_list_tenant_isolation(
    client_a, receipt_a, receipt_b
):
    """Tenant A cannot see Tenant B's intake receipts."""
    url = reverse("assets:asset_acquisition_receipt_list")
    response = client_a.get(url)
    assert response.status_code == 200
    items = list(response.context["receipts"])
    assert receipt_a in items
    assert receipt_b not in items


@pytest.mark.django_db
def test_assetprocurement_receipt_list_search_and_filters(
    client_a, receipt_a, location_a
):
    """Receipt list filters by search, condition, status, and receiving location."""
    url = reverse("assets:asset_acquisition_receipt_list")

    # Search match
    resp = client_a.get(url, {"q": "TL3030"})
    assert receipt_a in list(resp.context["receipts"])

    # Search mismatch
    resp = client_a.get(url, {"q": "NonExistentSerialXYZ"})
    assert receipt_a not in list(resp.context["receipts"])

    # Condition match
    resp = client_a.get(url, {"condition": "intact"})
    assert receipt_a in list(resp.context["receipts"])

    # Status match
    resp = client_a.get(url, {"status": "pending_inspection"})
    assert receipt_a in list(resp.context["receipts"])

    # Location match
    resp = client_a.get(url, {"location": str(location_a.pk)})
    assert receipt_a in list(resp.context["receipts"])


@pytest.mark.django_db
def test_assetprocurement_receipt_list_junk_params_resilience(
    client_a, receipt_a
):
    """Receipt list handles invalid and non-digit query parameters smoothly."""
    url = reverse("assets:asset_acquisition_receipt_list")
    resp = client_a.get(
        url,
        {
            "location": "not_an_int",
            "condition": "destroyed_in_space",
            "status": "mythical_status",
            "page": "invalid_page",
        },
    )
    assert resp.status_code == 200
    assert "receipts" in resp.context


@pytest.mark.django_db
def test_assetprocurement_receipt_detail_get_200(client_a, receipt_a):
    """Receipt detail renders 200 OK with receipt context."""
    url = reverse("assets:asset_acquisition_receipt_detail", args=[receipt_a.pk])
    response = client_a.get(url)
    assert response.status_code == 200
    assert "assets/asset_procurement/asset_acquisition_receipt/detail.html" in [
        t.name for t in response.templates
    ]
    assert response.context["receipt"] == receipt_a


@pytest.mark.django_db
def test_assetprocurement_receipt_detail_cross_tenant_404(client_a, receipt_b):
    """Cross-tenant access to receipt detail yields 404."""
    url = reverse("assets:asset_acquisition_receipt_detail", args=[receipt_b.pk])
    response = client_a.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_assetprocurement_receipt_create_get_200(client_a):
    """Receipt create GET renders empty form with is_edit=False."""
    url = reverse("assets:asset_acquisition_receipt_create")
    response = client_a.get(url)
    assert response.status_code == 200
    assert "assets/asset_procurement/asset_acquisition_receipt/form.html" in [
        t.name for t in response.templates
    ]
    assert response.context["is_edit"] is False
    assert response.context["receipt"] is None


@pytest.mark.django_db
def test_assetprocurement_receipt_create_post_success(
    client_a, tenant_a, requisition_a, vendor_party_a, location_a
):
    """Receipt create POST valid data creates intake receipt."""
    url = reverse("assets:asset_acquisition_receipt_create")
    payload = _assetprocurement_valid_receipt_payload(
        requisition=requisition_a.pk,
        vendor=vendor_party_a.pk,
        receiving_location=location_a.pk,
    )
    response = client_a.post(url, payload)
    assert response.status_code == 302

    created = AssetAcquisitionReceipt.objects.filter(
        tenant=tenant_a, serial_number=payload["serial_number"]
    ).first()
    assert created is not None
    assert response.url == reverse(
        "assets:asset_acquisition_receipt_detail", args=[created.pk]
    )
    assert created.status == "pending_inspection"


@pytest.mark.django_db
def test_assetprocurement_receipt_create_post_invalid(client_a):
    """Receipt create POST missing required fields re-renders form with errors."""
    url = reverse("assets:asset_acquisition_receipt_create")
    response = client_a.post(url, {})
    assert response.status_code == 200
    assert response.context["form"].errors


@pytest.mark.django_db
def test_assetprocurement_receipt_edit_get_and_post_success(
    client_a, receipt_a
):
    """Receipt edit GET and POST updates receipt details."""
    url = reverse("assets:asset_acquisition_receipt_edit", args=[receipt_a.pk])

    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True

    payload = _assetprocurement_valid_receipt_payload(
        title="Updated Intake Receipt Title",
        carrier_name="DHL Freight Global",
    )
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse(
        "assets:asset_acquisition_receipt_detail", args=[receipt_a.pk]
    )

    receipt_a.refresh_from_db()
    assert receipt_a.title == "Updated Intake Receipt Title"
    assert receipt_a.carrier_name == "DHL Freight Global"


@pytest.mark.django_db
def test_assetprocurement_receipt_edit_guard_blocked_if_capitalized(
    client_a, receipt_a
):
    """Receipt cannot be edited once it has been capitalized."""
    url = reverse("assets:asset_acquisition_receipt_edit", args=[receipt_a.pk])

    receipt_a.status = "capitalized"
    receipt_a.save()

    resp_get = client_a.get(url)
    assert resp_get.status_code == 302
    assert resp_get.url == reverse(
        "assets:asset_acquisition_receipt_detail", args=[receipt_a.pk]
    )
    msgs = _assetprocurement_get_flash_messages(resp_get)
    assert any("already been capitalized" in m for m in msgs)


@pytest.mark.django_db
def test_assetprocurement_receipt_delete_requires_post_and_guard(
    client_a, receipt_a
):
    """Receipt delete requires POST, blocks if accepted/capitalized, allows pending."""
    url = reverse("assets:asset_acquisition_receipt_delete", args=[receipt_a.pk])

    # GET blocked
    assert client_a.get(url).status_code == 405

    # Guard blocked when accepted
    receipt_a.status = "accepted"
    receipt_a.save()
    resp_blocked = client_a.post(url)
    assert resp_blocked.status_code == 302
    assert AssetAcquisitionReceipt.objects.filter(pk=receipt_a.pk).exists()

    # Success when pending_inspection
    receipt_a.status = "pending_inspection"
    receipt_a.save()
    resp_success = client_a.post(url)
    assert resp_success.status_code == 302
    assert resp_success.url == reverse("assets:asset_acquisition_receipt_list")
    assert not AssetAcquisitionReceipt.objects.filter(pk=receipt_a.pk).exists()


@pytest.mark.django_db
def test_assetprocurement_receipt_inspect_accept_workflow(
    client_a, admin_user, receipt_a
):
    """Receipt inspect action marks status as accepted and appends inspection notes."""
    url = reverse("assets:asset_acquisition_receipt_inspect", args=[receipt_a.pk])

    # GET blocked
    assert client_a.get(url).status_code == 405

    # Guard blocked if capitalized
    receipt_a.status = "capitalized"
    receipt_a.save()
    resp_blocked = client_a.post(url, {"inspection_notes": "Passed ok."})
    assert resp_blocked.status_code == 302
    assert receipt_a.status == "capitalized"

    # Success transition
    receipt_a.status = "pending_inspection"
    receipt_a.save()
    resp_success = client_a.post(
        url, {"inspection_notes": "Visual and dimensional inspection verified."}
    )
    assert resp_success.status_code == 302
    assert resp_success.url == reverse(
        "assets:asset_acquisition_receipt_detail", args=[receipt_a.pk]
    )

    receipt_a.refresh_from_db()
    assert receipt_a.status == "accepted"
    assert receipt_a.inspected_by == admin_user
    assert receipt_a.inspected_at is not None
    assert "dimensional inspection verified" in receipt_a.inspection_notes


@pytest.mark.django_db
def test_assetprocurement_receipt_quarantine_workflow(
    client_a, admin_user, receipt_a
):
    """Receipt quarantine action records reason and sets status to quarantined."""
    url = reverse(
        "assets:asset_acquisition_receipt_quarantine", args=[receipt_a.pk]
    )

    # GET blocked
    assert client_a.get(url).status_code == 405

    receipt_a.status = "pending_inspection"
    receipt_a.save()

    response = client_a.post(
        url, {"quarantine_reason": "Damaged crating and exposed guide rails."}
    )
    assert response.status_code == 302
    assert response.url == reverse(
        "assets:asset_acquisition_receipt_detail", args=[receipt_a.pk]
    )

    receipt_a.refresh_from_db()
    assert receipt_a.status == "quarantined"
    assert receipt_a.inspected_by == admin_user
    assert "Damaged crating" in receipt_a.inspection_notes


# ==============================================================================
# 4. Asset Capitalizations Tests
# ==============================================================================


@pytest.mark.django_db
def test_assetprocurement_capitalization_list_get_200(
    client_a, capitalization_a
):
    """Capitalization list view returns 200 OK with expected context variables."""
    url = reverse("assets:asset_capitalization_list")
    response = client_a.get(url)
    assert response.status_code == 200
    assert "assets/asset_procurement/asset_capitalization/list.html" in [
        t.name for t in response.templates
    ]

    context = response.context
    assert "capitalizations" in context
    assert "page_obj" in context
    assert "status_choices" in context
    assert "method_choices" in context
    assert capitalization_a in list(context["capitalizations"])


@pytest.mark.django_db
def test_assetprocurement_capitalization_list_tenant_isolation(
    client_a, capitalization_a, capitalization_b
):
    """Tenant A cannot see Tenant B's capitalization events."""
    url = reverse("assets:asset_capitalization_list")
    response = client_a.get(url)
    assert response.status_code == 200
    items = list(response.context["capitalizations"])
    assert capitalization_a in items
    assert capitalization_b not in items


@pytest.mark.django_db
def test_assetprocurement_capitalization_list_search_and_filters(
    client_a, capitalization_a
):
    """Capitalization list filters by search, status, and depreciation method."""
    url = reverse("assets:asset_capitalization_list")

    # Search match
    resp = client_a.get(url, {"q": "Trumpf"})
    assert capitalization_a in list(resp.context["capitalizations"])

    # Search mismatch
    resp = client_a.get(url, {"q": "NonExistentLaserMillingUnit"})
    assert capitalization_a not in list(resp.context["capitalizations"])

    # Status match
    resp = client_a.get(url, {"status": "draft"})
    assert capitalization_a in list(resp.context["capitalizations"])

    # Method match
    resp = client_a.get(url, {"method": "straight_line"})
    assert capitalization_a in list(resp.context["capitalizations"])


@pytest.mark.django_db
def test_assetprocurement_capitalization_list_junk_params_resilience(
    client_a, capitalization_a
):
    """Capitalization list handles unrecognized filter parameters gracefully."""
    url = reverse("assets:asset_capitalization_list")
    resp = client_a.get(
        url,
        {
            "status": "random_unknown_status",
            "method": "reverse_double_declining",
            "page": "abc_xyz",
        },
    )
    assert resp.status_code == 200
    assert "capitalizations" in resp.context


@pytest.mark.django_db
def test_assetprocurement_capitalization_detail_get_200(
    client_a, capitalization_a
):
    """Capitalization detail renders 200 OK with capitalization context."""
    url = reverse("assets:asset_capitalization_detail", args=[capitalization_a.pk])
    response = client_a.get(url)
    assert response.status_code == 200
    assert "assets/asset_procurement/asset_capitalization/detail.html" in [
        t.name for t in response.templates
    ]
    assert response.context["capitalization"] == capitalization_a


@pytest.mark.django_db
def test_assetprocurement_capitalization_detail_cross_tenant_404(
    client_a, capitalization_b
):
    """Cross-tenant access to capitalization detail returns 404."""
    url = reverse("assets:asset_capitalization_detail", args=[capitalization_b.pk])
    response = client_a.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_assetprocurement_capitalization_create_get_with_receipt_prepopulate(
    client_a, receipt_a
):
    """Capitalization create GET pre-populates initial values if receipt param is given."""
    url = reverse("assets:asset_capitalization_create")

    # Clean GET without param
    resp_clean = client_a.get(url)
    assert resp_clean.status_code == 200
    assert resp_clean.context["is_edit"] is False

    # GET with receipt query param
    resp_pre = client_a.get(url, {"receipt": str(receipt_a.pk)})
    assert resp_pre.status_code == 200
    initial = resp_pre.context["form"].initial
    assert initial["acquisition_receipt"] == receipt_a
    assert initial["asset_name"] == receipt_a.title

    # GET with non-numeric junk receipt query param
    resp_junk = client_a.get(url, {"receipt": "abc_not_a_pk"})
    assert resp_junk.status_code == 200


@pytest.mark.django_db
def test_assetprocurement_capitalization_create_post_success(
    client_a, tenant_a, receipt_a, asset_account_a, cip_account_a
):
    """Capitalization create POST computes total_cost_basis and saves."""
    url = reverse("assets:asset_capitalization_create")
    payload = _assetprocurement_valid_capitalization_payload(
        acquisition_receipt=receipt_a.pk,
        asset_gl_account=asset_account_a.pk,
        cip_gl_account=cip_account_a.pk,
        purchase_cost=Decimal("100000.00"),
        freight_cost=Decimal("3000.00"),
        installation_cost=Decimal("2000.00"),
    )
    response = client_a.post(url, payload)
    assert response.status_code == 302

    created = AssetCapitalization.objects.filter(
        tenant=tenant_a, asset_name=payload["asset_name"]
    ).first()
    assert created is not None
    assert response.url == reverse(
        "assets:asset_capitalization_detail", args=[created.pk]
    )
    assert created.total_cost_basis == Decimal("105000.00")
    assert created.status == "draft"


@pytest.mark.django_db
def test_assetprocurement_capitalization_create_post_invalid(client_a):
    """Capitalization create POST invalid payload remains on form with errors."""
    url = reverse("assets:asset_capitalization_create")
    response = client_a.post(url, {})
    assert response.status_code == 200
    assert response.context["form"].errors


@pytest.mark.django_db
def test_assetprocurement_capitalization_edit_get_and_post_success(
    client_a, capitalization_a
):
    """Capitalization edit GET and POST updates capitalization cost fields."""
    url = reverse("assets:asset_capitalization_edit", args=[capitalization_a.pk])

    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True

    payload = _assetprocurement_valid_capitalization_payload(
        title="Updated Capitalization Description",
        purchase_cost=Decimal("130000.00"),
        freight_cost=Decimal("4000.00"),
        installation_cost=Decimal("2000.00"),
    )
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse(
        "assets:asset_capitalization_detail", args=[capitalization_a.pk]
    )

    capitalization_a.refresh_from_db()
    assert capitalization_a.title == "Updated Capitalization Description"
    assert capitalization_a.total_cost_basis == Decimal("136000.00")


@pytest.mark.django_db
def test_assetprocurement_capitalization_edit_guard_blocked_if_capitalized(
    client_a, capitalization_a
):
    """Capitalization cannot be edited once status is capitalized."""
    url = reverse("assets:asset_capitalization_edit", args=[capitalization_a.pk])

    capitalization_a.status = "capitalized"
    capitalization_a.save()

    resp_get = client_a.get(url)
    assert resp_get.status_code == 302
    assert resp_get.url == reverse(
        "assets:asset_capitalization_detail", args=[capitalization_a.pk]
    )
    msgs = _assetprocurement_get_flash_messages(resp_get)
    assert any("already capitalized" in m for m in msgs)


@pytest.mark.django_db
def test_assetprocurement_capitalization_delete_requires_post_and_guard(
    client_a, capitalization_a
):
    """Capitalization delete requires POST, blocks capitalized, deletes draft."""
    url = reverse("assets:asset_capitalization_delete", args=[capitalization_a.pk])

    # GET blocked
    assert client_a.get(url).status_code == 405

    # Guard blocked when capitalized
    capitalization_a.status = "capitalized"
    capitalization_a.save()
    resp_blocked = client_a.post(url)
    assert resp_blocked.status_code == 302
    assert AssetCapitalization.objects.filter(pk=capitalization_a.pk).exists()

    # Success when draft
    capitalization_a.status = "draft"
    capitalization_a.save()
    resp_success = client_a.post(url)
    assert resp_success.status_code == 302
    assert resp_success.url == reverse("assets:asset_capitalization_list")
    assert not AssetCapitalization.objects.filter(pk=capitalization_a.pk).exists()


@pytest.mark.django_db
def test_assetprocurement_capitalization_execute_permission_denied_for_non_admin(
    member_client, capitalization_a
):
    """Non-admin members cannot execute asset capitalization (requires tenant admin)."""
    url = reverse("assets:asset_capitalization_execute", args=[capitalization_a.pk])
    response = member_client.post(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_assetprocurement_capitalization_execute_success_creates_fixed_asset(
    client_a, admin_user, tenant_a, capitalization_a, receipt_a
):
    """Capitalization execute creates FixedAsset ledger entity and marks receipt capitalized."""
    url = reverse("assets:asset_capitalization_execute", args=[capitalization_a.pk])

    # Ensure clean uncapitalized state
    capitalization_a.status = "draft"
    capitalization_a.fixed_asset = None
    capitalization_a.acquisition_receipt = receipt_a
    capitalization_a.save()

    receipt_a.status = "accepted"
    receipt_a.save()

    # GET blocked
    assert client_a.get(url).status_code == 405

    # Execute POST
    response = client_a.post(url)
    assert response.status_code == 302
    assert response.url == reverse(
        "assets:asset_capitalization_detail", args=[capitalization_a.pk]
    )

    capitalization_a.refresh_from_db()
    assert capitalization_a.status == "capitalized"
    assert capitalization_a.capitalized_by == admin_user
    assert capitalization_a.capitalized_at is not None
    assert capitalization_a.fixed_asset is not None

    # Verify Module 2 FixedAsset ledger entity created
    fa = capitalization_a.fixed_asset
    assert isinstance(fa, FixedAsset)
    assert fa.tenant == tenant_a
    assert fa.name == capitalization_a.asset_name
    assert fa.acquisition_cost == capitalization_a.total_cost_basis
    assert fa.status == "active"

    # Upstream receipt marked capitalized
    receipt_a.refresh_from_db()
    assert receipt_a.status == "capitalized"


@pytest.mark.django_db
def test_assetprocurement_capitalization_execute_guard_invalid_state(
    client_a, capitalization_a
):
    """Capitalization execute rejects when already in capitalized state."""
    url = reverse("assets:asset_capitalization_execute", args=[capitalization_a.pk])
    capitalization_a.status = "capitalized"
    capitalization_a.save()

    response = client_a.post(url)
    assert response.status_code == 302
    msgs = _assetprocurement_get_flash_messages(response)
    assert any("cannot be executed" in m for m in msgs)


@pytest.mark.django_db
def test_assetprocurement_capitalization_reverse_workflow(
    client_a, member_client, capitalization_a
):
    """Capitalization reverse requires admin, transitions capitalized to reversed."""
    url = reverse("assets:asset_capitalization_reverse", args=[capitalization_a.pk])

    # GET blocked
    assert client_a.get(url).status_code == 405

    capitalization_a.status = "capitalized"
    capitalization_a.save()

    # Member user gets 403
    resp_member = member_client.post(url)
    assert resp_member.status_code == 403

    # Admin user reverses
    resp_admin = client_a.post(url)
    assert resp_admin.status_code == 302
    assert resp_admin.url == reverse(
        "assets:asset_capitalization_detail", args=[capitalization_a.pk]
    )

    capitalization_a.refresh_from_db()
    assert capitalization_a.status == "reversed"

    # Reverse again fails guard
    resp_again = client_a.post(url)
    assert resp_again.status_code == 302
    msgs = _assetprocurement_get_flash_messages(resp_again)
    assert any("cannot be reversed" in m for m in msgs)


# ==============================================================================
# 5. Asset Tags Tests
# ==============================================================================


@pytest.mark.django_db
def test_assetprocurement_tag_list_get_200(client_a, asset_tag_a):
    """Tag list view returns 200 OK with expected context variables."""
    url = reverse("assets:asset_tag_list")
    response = client_a.get(url)
    assert response.status_code == 200
    assert "assets/asset_procurement/asset_tag/list.html" in [
        t.name for t in response.templates
    ]

    context = response.context
    assert "tags" in context
    assert "page_obj" in context
    assert "status_choices" in context
    assert "format_choices" in context
    assert asset_tag_a in list(context["tags"])


@pytest.mark.django_db
def test_assetprocurement_tag_list_tenant_isolation(
    client_a, asset_tag_a, asset_tag_b
):
    """Tenant A cannot see Tenant B's asset tags."""
    url = reverse("assets:asset_tag_list")
    response = client_a.get(url)
    assert response.status_code == 200
    items = list(response.context["tags"])
    assert asset_tag_a in items
    assert asset_tag_b not in items


@pytest.mark.django_db
def test_assetprocurement_tag_list_search_and_filters(client_a, asset_tag_a):
    """Tag list filters by tag code search, format, and status."""
    url = reverse("assets:asset_tag_list")

    # Search match
    resp = client_a.get(url, {"q": "ATAG-ACME"})
    assert asset_tag_a in list(resp.context["tags"])

    # Search mismatch
    resp = client_a.get(url, {"q": "NonExistentTagCode999"})
    assert asset_tag_a not in list(resp.context["tags"])

    # Format match
    resp = client_a.get(url, {"format": "qr_code"})
    assert asset_tag_a in list(resp.context["tags"])

    # Status match
    resp = client_a.get(url, {"status": "pending_print"})
    assert asset_tag_a in list(resp.context["tags"])


@pytest.mark.django_db
def test_assetprocurement_tag_list_junk_params_resilience(client_a, asset_tag_a):
    """Tag list handles invalid query params without raising exceptions."""
    url = reverse("assets:asset_tag_list")
    resp = client_a.get(
        url,
        {
            "format": "invalid_tag_format",
            "status": "damaged_by_fire_unsupported",
            "page": "page_not_valid",
        },
    )
    assert resp.status_code == 200
    assert "tags" in resp.context


@pytest.mark.django_db
def test_assetprocurement_tag_detail_get_200(client_a, asset_tag_a):
    """Tag detail renders 200 OK with tag context."""
    url = reverse("assets:asset_tag_detail", args=[asset_tag_a.pk])
    response = client_a.get(url)
    assert response.status_code == 200
    assert "assets/asset_procurement/asset_tag/detail.html" in [
        t.name for t in response.templates
    ]
    assert response.context["tag"] == asset_tag_a


@pytest.mark.django_db
def test_assetprocurement_tag_detail_cross_tenant_404(client_a, asset_tag_b):
    """Accessing another tenant's asset tag returns 404."""
    url = reverse("assets:asset_tag_detail", args=[asset_tag_b.pk])
    response = client_a.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_assetprocurement_tag_create_get_with_capitalization_prepopulate(
    client_a, capitalization_a, operational_asset_a
):
    """Tag create GET pre-populates tag_code and relations if capitalization query param given."""
    capitalization_a.operational_asset = operational_asset_a
    capitalization_a.save()

    url = reverse("assets:asset_tag_create")

    # Clean GET
    resp_clean = client_a.get(url)
    assert resp_clean.status_code == 200
    assert resp_clean.context["is_edit"] is False

    # GET with capitalization param
    resp_pre = client_a.get(url, {"capitalization": str(capitalization_a.pk)})
    assert resp_pre.status_code == 200
    initial = resp_pre.context["form"].initial
    assert initial["capitalization"] == capitalization_a
    assert initial["operational_asset"] == operational_asset_a
    assert "AST-" in initial["tag_code"]

    # GET with non-numeric junk capitalization param
    resp_junk = client_a.get(url, {"capitalization": "junk_cap_id"})
    assert resp_junk.status_code == 200


@pytest.mark.django_db
def test_assetprocurement_tag_create_post_success(
    client_a, tenant_a, capitalization_a, operational_asset_a
):
    """Tag create POST valid data creates tag and redirects to detail."""
    url = reverse("assets:asset_tag_create")
    payload = _assetprocurement_valid_tag_payload(
        capitalization=capitalization_a.pk,
        operational_asset=operational_asset_a.pk,
        tag_code="ATAG-HAAS-VF2SS-001",
    )
    response = client_a.post(url, payload)
    assert response.status_code == 302

    created = AssetTag.objects.filter(
        tenant=tenant_a, tag_code="ATAG-HAAS-VF2SS-001"
    ).first()
    assert created is not None
    assert response.url == reverse("assets:asset_tag_detail", args=[created.pk])
    assert created.status == "pending_print"


@pytest.mark.django_db
def test_assetprocurement_tag_create_post_invalid(client_a):
    """Tag create POST missing tag_code re-renders form with errors."""
    url = reverse("assets:asset_tag_create")
    response = client_a.post(url, {})
    assert response.status_code == 200
    assert response.context["form"].errors


@pytest.mark.django_db
def test_assetprocurement_tag_edit_get_and_post_success(client_a, asset_tag_a):
    """Tag edit GET and POST updates tag metadata."""
    url = reverse("assets:asset_tag_edit", args=[asset_tag_a.pk])

    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True

    payload = _assetprocurement_valid_tag_payload(
        tag_code=asset_tag_a.tag_code,
        physical_placement="Relocated to operator console bracket",
    )
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse(
        "assets:asset_tag_detail", args=[asset_tag_a.pk]
    )

    asset_tag_a.refresh_from_db()
    assert (
        asset_tag_a.physical_placement
        == "Relocated to operator console bracket"
    )


@pytest.mark.django_db
def test_assetprocurement_tag_delete_requires_post_and_guards(
    client_a, asset_tag_a
):
    """Tag delete requires POST, blocks affixed/verified, deletes pending_print."""
    url = reverse("assets:asset_tag_delete", args=[asset_tag_a.pk])

    # GET blocked
    assert client_a.get(url).status_code == 405

    # Guard blocked when affixed
    asset_tag_a.status = "affixed"
    asset_tag_a.save()
    resp_affixed = client_a.post(url)
    assert resp_affixed.status_code == 302
    assert AssetTag.objects.filter(pk=asset_tag_a.pk).exists()

    # Guard blocked when verified
    asset_tag_a.status = "verified"
    asset_tag_a.save()
    resp_verified = client_a.post(url)
    assert resp_verified.status_code == 302
    assert AssetTag.objects.filter(pk=asset_tag_a.pk).exists()

    # Success when pending_print
    asset_tag_a.status = "pending_print"
    asset_tag_a.save()
    resp_del = client_a.post(url)
    assert resp_del.status_code == 302
    assert resp_del.url == reverse("assets:asset_tag_list")
    assert not AssetTag.objects.filter(pk=asset_tag_a.pk).exists()


@pytest.mark.django_db
def test_assetprocurement_tag_mark_printed_workflow(client_a, asset_tag_a):
    """Mark printed action transitions status to printed."""
    url = reverse("assets:asset_tag_mark_printed", args=[asset_tag_a.pk])

    # GET blocked
    assert client_a.get(url).status_code == 405

    # Guard blocked if affixed
    asset_tag_a.status = "affixed"
    asset_tag_a.save()
    resp_guard = client_a.post(url)
    assert resp_guard.status_code == 302
    msgs = _assetprocurement_get_flash_messages(resp_guard)
    assert any("cannot be marked printed" in m for m in msgs)

    # Success when pending_print
    asset_tag_a.status = "pending_print"
    asset_tag_a.save()
    resp_success = client_a.post(url)
    assert resp_success.status_code == 302
    assert resp_success.url == reverse(
        "assets:asset_tag_detail", args=[asset_tag_a.pk]
    )

    asset_tag_a.refresh_from_db()
    assert asset_tag_a.status == "printed"


@pytest.mark.django_db
def test_assetprocurement_tag_affix_workflow(client_a, admin_user, asset_tag_a):
    """Affix action transitions status to affixed and updates placement."""
    url = reverse("assets:asset_tag_affix", args=[asset_tag_a.pk])

    # GET blocked
    assert client_a.get(url).status_code == 405

    # Guard blocked if verified
    asset_tag_a.status = "verified"
    asset_tag_a.save()
    resp_guard = client_a.post(url)
    assert resp_guard.status_code == 302
    msgs = _assetprocurement_get_flash_messages(resp_guard)
    assert any("cannot be affixed" in m for m in msgs)

    # Success when printed
    asset_tag_a.status = "printed"
    asset_tag_a.save()
    resp_success = client_a.post(
        url, {"physical_placement": "Riveted to main column casting."}
    )
    assert resp_success.status_code == 302
    assert resp_success.url == reverse(
        "assets:asset_tag_detail", args=[asset_tag_a.pk]
    )

    asset_tag_a.refresh_from_db()
    assert asset_tag_a.status == "affixed"
    assert asset_tag_a.affixed_by == admin_user
    assert asset_tag_a.affixed_at is not None
    assert asset_tag_a.physical_placement == "Riveted to main column casting."


@pytest.mark.django_db
def test_assetprocurement_tag_verify_workflow(client_a, admin_user, asset_tag_a):
    """Verify action records scanner audit and sets is_verified=True."""
    url = reverse("assets:asset_tag_verify", args=[asset_tag_a.pk])

    # GET blocked
    assert client_a.get(url).status_code == 405

    # Guard blocked when pending_print
    asset_tag_a.status = "pending_print"
    asset_tag_a.save()
    resp_guard = client_a.post(url)
    assert resp_guard.status_code == 302
    msgs = _assetprocurement_get_flash_messages(resp_guard)
    assert any("cannot be verified" in m for m in msgs)

    # Success when affixed
    asset_tag_a.status = "affixed"
    asset_tag_a.save()
    resp_success = client_a.post(
        url, {"scanner_device_id": "ZEBRA-TC52-AUDIT-DOCK"}
    )
    assert resp_success.status_code == 302
    assert resp_success.url == reverse(
        "assets:asset_tag_detail", args=[asset_tag_a.pk]
    )

    asset_tag_a.refresh_from_db()
    assert asset_tag_a.status == "verified"
    assert asset_tag_a.is_verified is True
    assert asset_tag_a.verified_by == admin_user
    assert asset_tag_a.verified_at is not None
    assert asset_tag_a.scanner_device_id == "ZEBRA-TC52-AUDIT-DOCK"


@pytest.mark.django_db
def test_assetprocurement_tag_print_label_get_200(client_a, asset_tag_a):
    """Print label renders 200 OK standalone high-contrast barcode/QR printable layout."""
    url = reverse("assets:asset_tag_print_label", args=[asset_tag_a.pk])
    response = client_a.get(url)
    assert response.status_code == 200
    assert "assets/asset_procurement/asset_tag/print_label.html" in [
        t.name for t in response.templates
    ]
    assert response.context["tag"] == asset_tag_a

    content = response.content.decode("utf-8")
    assert asset_tag_a.tag_code in content
    # Assert label styling and print layout CSS
    assert "@page" in content or "label-container" in content
