"""Asset Procurement & Acquisition (Sub-module 11.1) — SECURITY Test Suite.

Comprehensive security, multi-tenancy, authorization, and tamper-protection tests:
1. IDOR Protection (assert 404):
   - Tenant A client accessing Tenant B records: detail, edit (GET/POST), delete (POST),
     and all workflow action endpoints for Requisition, Receipt, Capitalization, and Tag.
   - Reverse IDOR: Tenant B client accessing Tenant A records returns 404 across all endpoints.
   - List queries and overview KPIs strictly isolate by tenant with zero data leakage.

2. Authentication Enforcement (assert 302 to login):
   - Anonymous client accessing overview, list, detail, create, edit, delete, and all workflow actions.

3. Privilege & Role-Based Access Control:
   - Non-admin member (member_client) calling @tenant_admin_required views
     (asset_capitalization_execute, asset_capitalization_reverse) returns 403 Forbidden.
   - Tenant admin is authorized to perform privileged operations.

4. HTTP Method Restrictions (assert 405 Method Not Allowed):
   - Sending GET requests to all @require_POST endpoints (all 4 delete views and 10 workflow action views).

5. Mass Assignment Prevention:
   - Attempting to inject status, number, tenant, is_verified, scanner_device_id, or rejection_reason
     via POST to create/edit endpoints does not alter or overwrite model attributes.

6. Segregation of Duties:
   - Requisition submitter attempting to approve their own requisition is blocked with an error message
     and redirect; approval by an independent authorized user succeeds.

7. Cross-Tenant Foreign Key Injection Defense:
   - Submitting foreign tenant foreign keys (vendor, location, PO, receipt, asset) on create/edit
     is rejected by form and view-level scoping.
"""
from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models import Currency, GLAccount
from apps.assets.models import (
    AssetAcquisitionReceipt,
    AssetCapitalization,
    AssetRequisition,
    AssetTag,
)
from apps.core.models import OrgUnit, Party, PartyRole
from apps.scm.models import Asset, Location, PurchaseOrder

User = get_user_model()
pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (strictly prefixed with _assetprocurement_)
# ==============================================================================


def _assetprocurement_get_flash_messages(response):
    """Extract list of flash message strings from response."""
    return [str(m) for m in get_messages(response.wsgi_request)]


def _assetprocurement_valid_requisition_payload(currency, **overrides):
    """Return a valid dictionary payload for creating an AssetRequisition."""
    payload = {
        "title": "Industrial CNC Laser Station",
        "description": "High-precision fiber laser cutting machine.",
        "business_justification": "Required for sheet metal expansion.",
        "asset_category": "machinery",
        "priority": "high",
        "estimated_cost": Decimal("115000.00"),
        "currency": currency.pk,
        "budget_code": "CAPEX-2026-SEC-01",
        "proposed_manufacturer": "Trumpf Laser",
        "proposed_model": "TruLaser 1030",
        "required_delivery_date": "2026-12-31",
    }
    payload.update(overrides)
    return payload


def _assetprocurement_valid_receipt_payload(**overrides):
    """Return a valid dictionary payload for creating an AssetAcquisitionReceipt."""
    payload = {
        "title": "Intake Delivery for CNC Laser Station",
        "manufacturer": "Trumpf Laser",
        "model_number": "TruLaser 1030",
        "serial_number": "SN-TRUMPF-2026-SEC1",
        "quantity_received": 1,
        "received_date": timezone.now().date(),
        "carrier_name": "Swift Heavy Freight",
        "tracking_number": "TRK-SEC-2026-001",
        "bill_of_lading": "BOL-SEC-99001",
        "condition_on_arrival": "excellent",
        "inspection_notes": "Initial dock intake inspection complete.",
    }
    payload.update(overrides)
    return payload


def _assetprocurement_valid_capitalization_payload(**overrides):
    """Return a valid dictionary payload for creating an AssetCapitalization."""
    payload = {
        "title": "Capitalization — CNC Laser Station",
        "asset_name": "Trumpf TruLaser 1030 Workstation",
        "purchase_cost": Decimal("110000.00"),
        "freight_cost": Decimal("3000.00"),
        "installation_cost": Decimal("2000.00"),
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
        "tag_code": "ATAG-SEC-2026-001",
        "tag_format": "qr_code",
        "physical_placement": "Upper right chassis plate near main power switch",
        "notes": "Industrial barcode security label.",
    }
    payload.update(overrides)
    return payload


# ==============================================================================
# 1. IDOR Protection Tests (Cross-Tenant Object Access Asserts 404)
# ==============================================================================


def test_assetprocurement_idor_requisition_detail_returns_404(client_a, requisition_b):
    """Tenant A admin client accessing Tenant B requisition detail returns 404."""
    url = reverse("assets:asset_requisition_detail", args=[requisition_b.pk])
    response = client_a.get(url)
    assert response.status_code == 404


def test_assetprocurement_idor_requisition_edit_get_and_post_returns_404(
    client_a, requisition_b, currency_usd
):
    """Tenant A admin client attempting to view or submit edit to Tenant B requisition returns 404."""
    url = reverse("assets:asset_requisition_edit", args=[requisition_b.pk])
    assert client_a.get(url).status_code == 404

    payload = _assetprocurement_valid_requisition_payload(
        currency_usd, title="Tampered Title"
    )
    assert client_a.post(url, data=payload).status_code == 404


def test_assetprocurement_idor_requisition_delete_post_returns_404(
    client_a, requisition_b
):
    """Tenant A admin client attempting to delete Tenant B requisition returns 404."""
    url = reverse("assets:asset_requisition_delete", args=[requisition_b.pk])
    response = client_a.post(url)
    assert response.status_code == 404
    assert AssetRequisition.objects.filter(pk=requisition_b.pk).exists()


def test_assetprocurement_idor_requisition_workflow_actions_return_404(
    client_a, requisition_b
):
    """Tenant A admin client calling submit/approve/reject on Tenant B requisition returns 404."""
    submit_url = reverse("assets:asset_requisition_submit", args=[requisition_b.pk])
    assert client_a.post(submit_url).status_code == 404

    approve_url = reverse("assets:asset_requisition_approve", args=[requisition_b.pk])
    assert client_a.post(approve_url).status_code == 404

    reject_url = reverse("assets:asset_requisition_reject", args=[requisition_b.pk])
    assert client_a.post(reject_url, data={"rejection_reason": "Rogue reason"}).status_code == 404


def test_assetprocurement_idor_receipt_detail_returns_404(client_a, receipt_b):
    """Tenant A admin client accessing Tenant B dock receipt detail returns 404."""
    url = reverse("assets:asset_acquisition_receipt_detail", args=[receipt_b.pk])
    response = client_a.get(url)
    assert response.status_code == 404


def test_assetprocurement_idor_receipt_edit_get_and_post_returns_404(
    client_a, receipt_b
):
    """Tenant A admin client attempting to edit Tenant B dock receipt returns 404."""
    url = reverse("assets:asset_acquisition_receipt_edit", args=[receipt_b.pk])
    assert client_a.get(url).status_code == 404

    payload = _assetprocurement_valid_receipt_payload(title="Tampered Receipt")
    assert client_a.post(url, data=payload).status_code == 404


def test_assetprocurement_idor_receipt_delete_post_returns_404(client_a, receipt_b):
    """Tenant A admin client attempting to delete Tenant B dock receipt returns 404."""
    url = reverse("assets:asset_acquisition_receipt_delete", args=[receipt_b.pk])
    response = client_a.post(url)
    assert response.status_code == 404
    assert AssetAcquisitionReceipt.objects.filter(pk=receipt_b.pk).exists()


def test_assetprocurement_idor_receipt_workflow_actions_return_404(
    client_a, receipt_b
):
    """Tenant A admin client calling inspect or quarantine on Tenant B receipt returns 404."""
    inspect_url = reverse("assets:asset_acquisition_receipt_inspect", args=[receipt_b.pk])
    assert client_a.post(inspect_url, data={"inspection_notes": "Cross tenant"}).status_code == 404

    quarantine_url = reverse("assets:asset_acquisition_receipt_quarantine", args=[receipt_b.pk])
    assert client_a.post(quarantine_url, data={"quarantine_reason": "Cross tenant"}).status_code == 404


def test_assetprocurement_idor_capitalization_detail_returns_404(
    client_a, capitalization_b
):
    """Tenant A admin client accessing Tenant B capitalization detail returns 404."""
    url = reverse("assets:asset_capitalization_detail", args=[capitalization_b.pk])
    response = client_a.get(url)
    assert response.status_code == 404


def test_assetprocurement_idor_capitalization_edit_get_and_post_returns_404(
    client_a, capitalization_b
):
    """Tenant A admin client attempting to edit Tenant B capitalization returns 404."""
    url = reverse("assets:asset_capitalization_edit", args=[capitalization_b.pk])
    assert client_a.get(url).status_code == 404

    payload = _assetprocurement_valid_capitalization_payload(title="Tampered Cap")
    assert client_a.post(url, data=payload).status_code == 404


def test_assetprocurement_idor_capitalization_delete_post_returns_404(
    client_a, capitalization_b
):
    """Tenant A admin client attempting to delete Tenant B capitalization returns 404."""
    url = reverse("assets:asset_capitalization_delete", args=[capitalization_b.pk])
    response = client_a.post(url)
    assert response.status_code == 404
    assert AssetCapitalization.objects.filter(pk=capitalization_b.pk).exists()


def test_assetprocurement_idor_capitalization_workflow_actions_return_404(
    client_a, capitalization_b
):
    """Tenant A admin client calling execute or reverse on Tenant B capitalization returns 404."""
    exec_url = reverse("assets:asset_capitalization_execute", args=[capitalization_b.pk])
    assert client_a.post(exec_url).status_code == 404

    rev_url = reverse("assets:asset_capitalization_reverse", args=[capitalization_b.pk])
    assert client_a.post(rev_url).status_code == 404


def test_assetprocurement_idor_tag_detail_and_print_label_returns_404(
    client_a, asset_tag_b
):
    """Tenant A admin client accessing Tenant B tag detail or print label returns 404."""
    detail_url = reverse("assets:asset_tag_detail", args=[asset_tag_b.pk])
    assert client_a.get(detail_url).status_code == 404

    print_url = reverse("assets:asset_tag_print_label", args=[asset_tag_b.pk])
    assert client_a.get(print_url).status_code == 404


def test_assetprocurement_idor_tag_edit_get_and_post_returns_404(
    client_a, asset_tag_b
):
    """Tenant A admin client attempting to edit Tenant B tag returns 404."""
    url = reverse("assets:asset_tag_edit", args=[asset_tag_b.pk])
    assert client_a.get(url).status_code == 404

    payload = _assetprocurement_valid_tag_payload(physical_placement="Cross Placement")
    assert client_a.post(url, data=payload).status_code == 404


def test_assetprocurement_idor_tag_delete_post_returns_404(client_a, asset_tag_b):
    """Tenant A admin client attempting to delete Tenant B tag returns 404."""
    url = reverse("assets:asset_tag_delete", args=[asset_tag_b.pk])
    response = client_a.post(url)
    assert response.status_code == 404
    assert AssetTag.objects.filter(pk=asset_tag_b.pk).exists()


def test_assetprocurement_idor_tag_workflow_actions_return_404(
    client_a, asset_tag_b
):
    """Tenant A admin client calling mark-printed, affix, or verify on Tenant B tag returns 404."""
    print_url = reverse("assets:asset_tag_mark_printed", args=[asset_tag_b.pk])
    assert client_a.post(print_url).status_code == 404

    affix_url = reverse("assets:asset_tag_affix", args=[asset_tag_b.pk])
    assert client_a.post(affix_url, data={"physical_placement": "Chassis"}).status_code == 404

    verify_url = reverse("assets:asset_tag_verify", args=[asset_tag_b.pk])
    assert client_a.post(verify_url, data={"scanner_device_id": "SCANNER-99"}).status_code == 404


def test_assetprocurement_idor_reverse_tenant_b_cannot_access_tenant_a(
    client_b, requisition_a, receipt_a, capitalization_a, asset_tag_a
):
    """Tenant B admin client accessing Tenant A records returns 404 across all endpoints."""
    # Requisition
    assert client_b.get(reverse("assets:asset_requisition_detail", args=[requisition_a.pk])).status_code == 404
    assert client_b.get(reverse("assets:asset_requisition_edit", args=[requisition_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_requisition_delete", args=[requisition_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_requisition_submit", args=[requisition_a.pk])).status_code == 404

    # Receipt
    assert client_b.get(reverse("assets:asset_acquisition_receipt_detail", args=[receipt_a.pk])).status_code == 404
    assert client_b.get(reverse("assets:asset_acquisition_receipt_edit", args=[receipt_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_acquisition_receipt_delete", args=[receipt_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_acquisition_receipt_inspect", args=[receipt_a.pk])).status_code == 404

    # Capitalization
    assert client_b.get(reverse("assets:asset_capitalization_detail", args=[capitalization_a.pk])).status_code == 404
    assert client_b.get(reverse("assets:asset_capitalization_edit", args=[capitalization_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_capitalization_delete", args=[capitalization_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_capitalization_execute", args=[capitalization_a.pk])).status_code == 404

    # Tag
    assert client_b.get(reverse("assets:asset_tag_detail", args=[asset_tag_a.pk])).status_code == 404
    assert client_b.get(reverse("assets:asset_tag_print_label", args=[asset_tag_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_tag_delete", args=[asset_tag_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_tag_verify", args=[asset_tag_a.pk])).status_code == 404


# ==============================================================================
# 2. Multi-Tenant Query & KPI Isolation (Zero Data Leakage)
# ==============================================================================


def test_assetprocurement_tenant_isolation_overview_kpis(
    client_a,
    client_b,
    requisition_a,
    requisition_b,
    receipt_a,
    receipt_b,
    capitalization_a,
    capitalization_b,
    asset_tag_a,
    asset_tag_b,
):
    """Overview dashboard KPIs and recent activity feeds isolate strictly by tenant."""
    # Tenant A Overview
    resp_a = client_a.get(reverse("assets:overview"))
    assert resp_a.status_code == 200
    kpis_a = resp_a.context["kpis"]
    assert kpis_a["total_requisitions"] == 1
    assert kpis_a["total_receipts"] == 1
    assert kpis_a["total_capitalizations"] == 1
    assert kpis_a["total_tags"] == 1

    content_a = resp_a.content.decode()
    assert requisition_a.title in content_a
    assert requisition_b.title not in content_a
    assert receipt_a.title in content_a
    assert receipt_b.title not in content_a
    assert capitalization_a.asset_name in content_a
    assert capitalization_b.asset_name not in content_a
    assert asset_tag_a.tag_code in content_a
    assert asset_tag_b.tag_code not in content_a
    assert capitalization_a in resp_a.context["recent_capitalizations"]
    assert capitalization_b not in resp_a.context["recent_capitalizations"]

    # Tenant B Overview
    resp_b = client_b.get(reverse("assets:overview"))
    assert resp_b.status_code == 200
    kpis_b = resp_b.context["kpis"]
    assert kpis_b["total_requisitions"] == 1
    assert kpis_b["total_receipts"] == 1
    assert kpis_b["total_capitalizations"] == 1
    assert kpis_b["total_tags"] == 1

    content_b = resp_b.content.decode()
    assert requisition_b.title in content_b
    assert requisition_a.title not in content_b
    assert receipt_b.title in content_b
    assert receipt_a.title not in content_b
    assert capitalization_b.asset_name in content_b
    assert capitalization_a.asset_name not in content_b
    assert asset_tag_b.tag_code in content_b
    assert asset_tag_a.tag_code not in content_b
    assert capitalization_b in resp_b.context["recent_capitalizations"]
    assert capitalization_a not in resp_b.context["recent_capitalizations"]


def test_assetprocurement_tenant_isolation_requisition_list(
    client_a, requisition_a, requisition_b
):
    """Requisition list view strictly isolates records to current tenant."""
    url = reverse("assets:asset_requisition_list")
    response = client_a.get(url)
    assert response.status_code == 200
    req_ids = [r.pk for r in response.context["requisitions"]]
    assert requisition_a.pk in req_ids
    assert requisition_b.pk not in req_ids

    content = response.content.decode()
    assert requisition_a.title in content
    assert requisition_b.title not in content


def test_assetprocurement_tenant_isolation_receipt_list(
    client_a, receipt_a, receipt_b
):
    """Dock receipt list view strictly isolates records to current tenant."""
    url = reverse("assets:asset_acquisition_receipt_list")
    response = client_a.get(url)
    assert response.status_code == 200
    rcv_ids = [r.pk for r in response.context["receipts"]]
    assert receipt_a.pk in rcv_ids
    assert receipt_b.pk not in rcv_ids

    content = response.content.decode()
    assert receipt_a.serial_number in content
    assert receipt_b.serial_number not in content


def test_assetprocurement_tenant_isolation_capitalization_list(
    client_a, capitalization_a, capitalization_b
):
    """Capitalization list view strictly isolates records to current tenant."""
    url = reverse("assets:asset_capitalization_list")
    response = client_a.get(url)
    assert response.status_code == 200
    cap_ids = [c.pk for c in response.context["capitalizations"]]
    assert capitalization_a.pk in cap_ids
    assert capitalization_b.pk not in cap_ids

    content = response.content.decode()
    assert capitalization_a.asset_name in content
    assert capitalization_b.asset_name not in content


def test_assetprocurement_tenant_isolation_tag_list(
    client_a, asset_tag_a, asset_tag_b
):
    """Asset tag list view strictly isolates records to current tenant."""
    url = reverse("assets:asset_tag_list")
    response = client_a.get(url)
    assert response.status_code == 200
    tag_ids = [t.pk for t in response.context["tags"]]
    assert asset_tag_a.pk in tag_ids
    assert asset_tag_b.pk not in tag_ids

    content = response.content.decode()
    assert asset_tag_a.tag_code in content
    assert asset_tag_b.tag_code not in content


# ==============================================================================
# 3. Authentication Enforcement (Unauthenticated Requests Redirect to Login)
# ==============================================================================


def test_assetprocurement_unauthenticated_overview_redirects(client):
    """Anonymous access to overview redirects to login."""
    url = reverse("assets:overview")
    response = client.get(url)
    assert response.status_code == 302
    assert "login" in response.url


def test_assetprocurement_unauthenticated_requisition_views_redirect(
    client, requisition_a
):
    """Anonymous client accessing any requisition endpoint is redirected to login."""
    urls = [
        ("GET", reverse("assets:asset_requisition_list")),
        ("GET", reverse("assets:asset_requisition_create")),
        ("POST", reverse("assets:asset_requisition_create")),
        ("GET", reverse("assets:asset_requisition_detail", args=[requisition_a.pk])),
        ("GET", reverse("assets:asset_requisition_edit", args=[requisition_a.pk])),
        ("POST", reverse("assets:asset_requisition_edit", args=[requisition_a.pk])),
        ("POST", reverse("assets:asset_requisition_delete", args=[requisition_a.pk])),
        ("POST", reverse("assets:asset_requisition_submit", args=[requisition_a.pk])),
        ("POST", reverse("assets:asset_requisition_approve", args=[requisition_a.pk])),
        ("POST", reverse("assets:asset_requisition_reject", args=[requisition_a.pk])),
    ]
    for method, target_url in urls:
        if method == "GET":
            resp = client.get(target_url)
        else:
            resp = client.post(target_url)
        assert resp.status_code == 302, f"Failed for {method} {target_url}"
        assert "login" in resp.url


def test_assetprocurement_unauthenticated_receipt_views_redirect(client, receipt_a):
    """Anonymous client accessing any receipt endpoint is redirected to login."""
    urls = [
        ("GET", reverse("assets:asset_acquisition_receipt_list")),
        ("GET", reverse("assets:asset_acquisition_receipt_create")),
        ("POST", reverse("assets:asset_acquisition_receipt_create")),
        ("GET", reverse("assets:asset_acquisition_receipt_detail", args=[receipt_a.pk])),
        ("GET", reverse("assets:asset_acquisition_receipt_edit", args=[receipt_a.pk])),
        ("POST", reverse("assets:asset_acquisition_receipt_edit", args=[receipt_a.pk])),
        ("POST", reverse("assets:asset_acquisition_receipt_delete", args=[receipt_a.pk])),
        ("POST", reverse("assets:asset_acquisition_receipt_inspect", args=[receipt_a.pk])),
        ("POST", reverse("assets:asset_acquisition_receipt_quarantine", args=[receipt_a.pk])),
    ]
    for method, target_url in urls:
        if method == "GET":
            resp = client.get(target_url)
        else:
            resp = client.post(target_url)
        assert resp.status_code == 302, f"Failed for {method} {target_url}"
        assert "login" in resp.url


def test_assetprocurement_unauthenticated_capitalization_views_redirect(
    client, capitalization_a
):
    """Anonymous client accessing any capitalization endpoint is redirected to login."""
    urls = [
        ("GET", reverse("assets:asset_capitalization_list")),
        ("GET", reverse("assets:asset_capitalization_create")),
        ("POST", reverse("assets:asset_capitalization_create")),
        ("GET", reverse("assets:asset_capitalization_detail", args=[capitalization_a.pk])),
        ("GET", reverse("assets:asset_capitalization_edit", args=[capitalization_a.pk])),
        ("POST", reverse("assets:asset_capitalization_edit", args=[capitalization_a.pk])),
        ("POST", reverse("assets:asset_capitalization_delete", args=[capitalization_a.pk])),
        ("POST", reverse("assets:asset_capitalization_execute", args=[capitalization_a.pk])),
        ("POST", reverse("assets:asset_capitalization_reverse", args=[capitalization_a.pk])),
    ]
    for method, target_url in urls:
        if method == "GET":
            resp = client.get(target_url)
        else:
            resp = client.post(target_url)
        assert resp.status_code == 302, f"Failed for {method} {target_url}"
        assert "login" in resp.url


def test_assetprocurement_unauthenticated_tag_views_redirect(client, asset_tag_a):
    """Anonymous client accessing any asset tag endpoint is redirected to login."""
    urls = [
        ("GET", reverse("assets:asset_tag_list")),
        ("GET", reverse("assets:asset_tag_create")),
        ("POST", reverse("assets:asset_tag_create")),
        ("GET", reverse("assets:asset_tag_detail", args=[asset_tag_a.pk])),
        ("GET", reverse("assets:asset_tag_edit", args=[asset_tag_a.pk])),
        ("POST", reverse("assets:asset_tag_edit", args=[asset_tag_a.pk])),
        ("POST", reverse("assets:asset_tag_delete", args=[asset_tag_a.pk])),
        ("POST", reverse("assets:asset_tag_mark_printed", args=[asset_tag_a.pk])),
        ("POST", reverse("assets:asset_tag_affix", args=[asset_tag_a.pk])),
        ("POST", reverse("assets:asset_tag_verify", args=[asset_tag_a.pk])),
        ("GET", reverse("assets:asset_tag_print_label", args=[asset_tag_a.pk])),
    ]
    for method, target_url in urls:
        if method == "GET":
            resp = client.get(target_url)
        else:
            resp = client.post(target_url)
        assert resp.status_code == 302, f"Failed for {method} {target_url}"
        assert "login" in resp.url


# ==============================================================================
# 4. Privilege & Role-Based Access Control (RBAC)
# ==============================================================================


def test_assetprocurement_rbac_non_admin_member_capitalization_execute_forbidden(
    member_client, capitalization_a
):
    """Non-admin workspace member calling capitalization execute returns 403 Forbidden."""
    url = reverse("assets:asset_capitalization_execute", args=[capitalization_a.pk])
    response = member_client.post(url)
    assert response.status_code == 403


def test_assetprocurement_rbac_non_admin_member_capitalization_reverse_forbidden(
    member_client, capitalization_a
):
    """Non-admin workspace member calling capitalization reverse returns 403 Forbidden."""
    url = reverse("assets:asset_capitalization_reverse", args=[capitalization_a.pk])
    response = member_client.post(url)
    assert response.status_code == 403


def test_assetprocurement_rbac_admin_authorized_for_capitalization_operations(
    client_a, capitalization_a
):
    """Tenant admin client is authorized to execute and reverse capitalizations."""
    exec_url = reverse("assets:asset_capitalization_execute", args=[capitalization_a.pk])
    # Execute capitalization
    resp_exec = client_a.post(exec_url)
    assert resp_exec.status_code == 302
    capitalization_a.refresh_from_db()
    assert capitalization_a.status == "capitalized"

    # Reverse capitalization
    rev_url = reverse("assets:asset_capitalization_reverse", args=[capitalization_a.pk])
    resp_rev = client_a.post(rev_url)
    assert resp_rev.status_code == 302
    capitalization_a.refresh_from_db()
    assert capitalization_a.status == "reversed"


# ==============================================================================
# 5. HTTP Method Restrictions (@require_POST blocks GET with 405)
# ==============================================================================


def test_assetprocurement_http_methods_get_on_delete_endpoints_returns_405(
    client_a, requisition_a, receipt_a, capitalization_a, asset_tag_a
):
    """Sending GET to any delete endpoint returns 405 Method Not Allowed."""
    endpoints = [
        reverse("assets:asset_requisition_delete", args=[requisition_a.pk]),
        reverse("assets:asset_acquisition_receipt_delete", args=[receipt_a.pk]),
        reverse("assets:asset_capitalization_delete", args=[capitalization_a.pk]),
        reverse("assets:asset_tag_delete", args=[asset_tag_a.pk]),
    ]
    for url in endpoints:
        resp = client_a.get(url)
        assert resp.status_code == 405, f"Expected 405 for GET on {url}, got {resp.status_code}"


def test_assetprocurement_http_methods_get_on_workflow_endpoints_returns_405(
    client_a, requisition_a, receipt_a, capitalization_a, asset_tag_a
):
    """Sending GET to all workflow transition endpoints returns 405 Method Not Allowed."""
    endpoints = [
        reverse("assets:asset_requisition_submit", args=[requisition_a.pk]),
        reverse("assets:asset_requisition_approve", args=[requisition_a.pk]),
        reverse("assets:asset_requisition_reject", args=[requisition_a.pk]),
        reverse("assets:asset_acquisition_receipt_inspect", args=[receipt_a.pk]),
        reverse("assets:asset_acquisition_receipt_quarantine", args=[receipt_a.pk]),
        reverse("assets:asset_capitalization_execute", args=[capitalization_a.pk]),
        reverse("assets:asset_capitalization_reverse", args=[capitalization_a.pk]),
        reverse("assets:asset_tag_mark_printed", args=[asset_tag_a.pk]),
        reverse("assets:asset_tag_affix", args=[asset_tag_a.pk]),
        reverse("assets:asset_tag_verify", args=[asset_tag_a.pk]),
    ]
    for url in endpoints:
        resp = client_a.get(url)
        assert resp.status_code == 405, f"Expected 405 for GET on {url}, got {resp.status_code}"


# ==============================================================================
# 6. Mass Assignment Prevention Tests
# ==============================================================================


def test_assetprocurement_mass_assignment_requisition_create_fields_ignored(
    client_a, currency_usd, tenant_a, tenant_b
):
    """Injected status, number, tenant, and rejection_reason are ignored on requisition create."""
    url = reverse("assets:asset_requisition_create")
    malicious_payload = _assetprocurement_valid_requisition_payload(
        currency_usd,
        status="approved",
        number="REQ-INJECTED-999",
        tenant=tenant_b.pk,
        rejection_reason="Hacked rejection reason",
    )
    response = client_a.post(url, data=malicious_payload)
    assert response.status_code == 302

    created_req = AssetRequisition.objects.filter(
        tenant=tenant_a, title=malicious_payload["title"]
    ).first()
    assert created_req is not None
    assert created_req.status == "draft"  # status override was ignored
    assert created_req.number != "REQ-INJECTED-999"  # number override was ignored
    assert created_req.number.startswith("AREQ-")
    assert created_req.tenant == tenant_a  # tenant override was ignored
    assert created_req.rejection_reason == ""  # rejection_reason override was ignored


def test_assetprocurement_mass_assignment_requisition_edit_fields_ignored(
    client_a, requisition_a, currency_usd, tenant_a, tenant_b
):
    """Injected status, number, tenant, and rejection_reason are ignored on requisition edit."""
    url = reverse("assets:asset_requisition_edit", args=[requisition_a.pk])
    original_number = requisition_a.number

    malicious_payload = _assetprocurement_valid_requisition_payload(
        currency_usd,
        title="Updated Requisition Legitimate Title",
        status="ordered",
        number="REQ-MODIFIED-777",
        tenant=tenant_b.pk,
        rejection_reason="Injected reason",
    )
    response = client_a.post(url, data=malicious_payload)
    assert response.status_code == 302

    requisition_a.refresh_from_db()
    assert requisition_a.title == "Updated Requisition Legitimate Title"
    assert requisition_a.status == "draft"
    assert requisition_a.number == original_number
    assert requisition_a.tenant == tenant_a
    assert requisition_a.rejection_reason == ""


def test_assetprocurement_mass_assignment_receipt_create_fields_ignored(
    client_a, tenant_a, tenant_b
):
    """Injected status, number, and tenant are ignored on dock receipt create."""
    url = reverse("assets:asset_acquisition_receipt_create")
    malicious_payload = _assetprocurement_valid_receipt_payload(
        status="capitalized",
        number="RCV-INJECTED-999",
        tenant=tenant_b.pk,
    )
    response = client_a.post(url, data=malicious_payload)
    assert response.status_code == 302

    created_rcv = AssetAcquisitionReceipt.objects.filter(
        tenant=tenant_a, serial_number=malicious_payload["serial_number"]
    ).first()
    assert created_rcv is not None
    assert created_rcv.status == "pending_inspection"  # status override ignored
    assert created_rcv.number != "RCV-INJECTED-999"  # number override ignored
    assert created_rcv.number.startswith("ARCV-")
    assert created_rcv.tenant == tenant_a  # tenant override ignored


def test_assetprocurement_mass_assignment_receipt_edit_fields_ignored(
    client_a, receipt_a, tenant_a, tenant_b
):
    """Injected status, number, and tenant are ignored on dock receipt edit."""
    url = reverse("assets:asset_acquisition_receipt_edit", args=[receipt_a.pk])
    original_number = receipt_a.number

    malicious_payload = _assetprocurement_valid_receipt_payload(
        title="Updated Receipt Legitimate Title",
        status="capitalized",
        number="RCV-MODIFIED-888",
        tenant=tenant_b.pk,
    )
    response = client_a.post(url, data=malicious_payload)
    assert response.status_code == 302

    receipt_a.refresh_from_db()
    assert receipt_a.title == "Updated Receipt Legitimate Title"
    assert receipt_a.status == "pending_inspection"
    assert receipt_a.number == original_number
    assert receipt_a.tenant == tenant_a


def test_assetprocurement_mass_assignment_capitalization_create_fields_ignored(
    client_a, tenant_a, tenant_b
):
    """Injected status, number, and tenant are ignored on capitalization create."""
    url = reverse("assets:asset_capitalization_create")
    malicious_payload = _assetprocurement_valid_capitalization_payload(
        status="capitalized",
        number="CAP-INJECTED-999",
        tenant=tenant_b.pk,
    )
    response = client_a.post(url, data=malicious_payload)
    assert response.status_code == 302

    created_cap = AssetCapitalization.objects.filter(
        tenant=tenant_a, title=malicious_payload["title"]
    ).first()
    assert created_cap is not None
    assert created_cap.status == "draft"  # status override ignored
    assert created_cap.number != "CAP-INJECTED-999"  # number override ignored
    assert created_cap.number.startswith("ACAP-")
    assert created_cap.tenant == tenant_a  # tenant override ignored


def test_assetprocurement_mass_assignment_capitalization_edit_fields_ignored(
    client_a, capitalization_a, tenant_a, tenant_b
):
    """Injected status, number, and tenant are ignored on capitalization edit."""
    url = reverse("assets:asset_capitalization_edit", args=[capitalization_a.pk])
    original_number = capitalization_a.number

    malicious_payload = _assetprocurement_valid_capitalization_payload(
        title="Updated Cap Legitimate Title",
        status="capitalized",
        number="CAP-MODIFIED-999",
        tenant=tenant_b.pk,
    )
    response = client_a.post(url, data=malicious_payload)
    assert response.status_code == 302

    capitalization_a.refresh_from_db()
    assert capitalization_a.title == "Updated Cap Legitimate Title"
    assert capitalization_a.status == "draft"
    assert capitalization_a.number == original_number
    assert capitalization_a.tenant == tenant_a


def test_assetprocurement_mass_assignment_tag_create_fields_ignored(
    client_a, tenant_a, tenant_b
):
    """Injected status, is_verified, scanner_device_id, number, tenant are ignored on tag create."""
    url = reverse("assets:asset_tag_create")
    malicious_payload = _assetprocurement_valid_tag_payload(
        status="verified",
        is_verified=True,
        scanner_device_id="ROGUE-SCANNER-999",
        number="TAG-INJECTED-999",
        tenant=tenant_b.pk,
    )
    response = client_a.post(url, data=malicious_payload)
    assert response.status_code == 302

    created_tag = AssetTag.objects.filter(
        tenant=tenant_a, tag_code=malicious_payload["tag_code"]
    ).first()
    assert created_tag is not None
    assert created_tag.status == "pending_print"  # status override ignored
    assert created_tag.is_verified is False  # is_verified override ignored
    assert created_tag.scanner_device_id == ""  # scanner_device_id override ignored
    assert created_tag.number != "TAG-INJECTED-999"  # number override ignored
    assert created_tag.number.startswith("ATAG-")
    assert created_tag.tenant == tenant_a  # tenant override ignored


def test_assetprocurement_mass_assignment_tag_edit_fields_ignored(
    client_a, asset_tag_a, tenant_a, tenant_b
):
    """Injected status, is_verified, scanner_device_id, number, tenant are ignored on tag edit."""
    url = reverse("assets:asset_tag_edit", args=[asset_tag_a.pk])
    original_number = asset_tag_a.number

    malicious_payload = _assetprocurement_valid_tag_payload(
        tag_code=asset_tag_a.tag_code,
        physical_placement="Updated placement on machine",
        status="verified",
        is_verified=True,
        scanner_device_id="ROGUE-SCANNER-888",
        number="TAG-MODIFIED-888",
        tenant=tenant_b.pk,
    )
    response = client_a.post(url, data=malicious_payload)
    assert response.status_code == 302

    asset_tag_a.refresh_from_db()
    assert asset_tag_a.physical_placement == "Updated placement on machine"
    assert asset_tag_a.status == "pending_print"
    assert asset_tag_a.is_verified is False
    assert asset_tag_a.scanner_device_id == ""
    assert asset_tag_a.number == original_number
    assert asset_tag_a.tenant == tenant_a


# ==============================================================================
# 7. Segregation of Duties (SoD)
# ==============================================================================


def test_assetprocurement_sod_submitter_cannot_approve_own_requisition(
    client_a, admin_user, requisition_a
):
    """Requisition submitter attempting to approve their own requisition is blocked with an error."""
    requisition_a.submitted_by = admin_user
    requisition_a.status = "pending_approval"
    requisition_a.save()

    url = reverse("assets:asset_requisition_approve", args=[requisition_a.pk])
    response = client_a.post(url)
    assert response.status_code == 302

    messages = _assetprocurement_get_flash_messages(response)
    assert any("Segregation of Duties" in m for m in messages)

    requisition_a.refresh_from_db()
    assert requisition_a.status == "pending_approval"
    assert requisition_a.approved_by is None


def test_assetprocurement_sod_different_user_can_approve_requisition(
    client_a, admin_user, tenant_a, requisition_a
):
    """An independent authorized manager can approve a requisition submitted by another user."""
    other_submitter = User.objects.create_user(
        username="mfg_engineer",
        email="engineer@acme.com",
        password="TestPassword123!",
        tenant=tenant_a,
    )
    requisition_a.submitted_by = other_submitter
    requisition_a.status = "pending_approval"
    requisition_a.save()

    url = reverse("assets:asset_requisition_approve", args=[requisition_a.pk])
    response = client_a.post(url)
    assert response.status_code == 302

    requisition_a.refresh_from_db()
    assert requisition_a.status == "approved"
    assert requisition_a.approved_by == admin_user
    assert requisition_a.approved_at is not None


# ==============================================================================
# 8. Cross-Tenant Foreign Key Injection Defense
# ==============================================================================


def test_assetprocurement_cross_tenant_fk_injection_requisition(
    client_a, currency_usd, vendor_party_b, location_b, po_b
):
    """Submitting foreign vendor, location, or PO on requisition form is rejected."""
    url = reverse("assets:asset_requisition_create")

    # Injected foreign vendor
    payload_vendor = _assetprocurement_valid_requisition_payload(
        currency_usd, proposed_vendor=vendor_party_b.pk
    )
    resp = client_a.post(url, data=payload_vendor)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert not resp.context["form"].is_valid()

    # Injected foreign location
    payload_loc = _assetprocurement_valid_requisition_payload(
        currency_usd, target_location=location_b.pk
    )
    resp = client_a.post(url, data=payload_loc)
    assert resp.status_code == 200
    assert not resp.context["form"].is_valid()

    # Injected foreign PO
    payload_po = _assetprocurement_valid_requisition_payload(
        currency_usd, purchase_order=po_b.pk
    )
    resp = client_a.post(url, data=payload_po)
    assert resp.status_code == 200
    assert not resp.context["form"].is_valid()


def test_assetprocurement_cross_tenant_fk_injection_receipt(
    client_a, requisition_b, po_b, vendor_party_b, location_b
):
    """Submitting foreign requisition, PO, vendor, or location on receipt form is rejected."""
    url = reverse("assets:asset_acquisition_receipt_create")

    payload = _assetprocurement_valid_receipt_payload(
        requisition=requisition_b.pk,
        purchase_order=po_b.pk,
        vendor=vendor_party_b.pk,
        receiving_location=location_b.pk,
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert not resp.context["form"].is_valid()


def test_assetprocurement_cross_tenant_fk_injection_capitalization(
    client_a, receipt_b, requisition_b, operational_asset_b
):
    """Submitting foreign receipt, requisition, or operational asset on capitalization form is rejected."""
    url = reverse("assets:asset_capitalization_create")

    payload = _assetprocurement_valid_capitalization_payload(
        acquisition_receipt=receipt_b.pk,
        requisition=requisition_b.pk,
        operational_asset=operational_asset_b.pk,
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert not resp.context["form"].is_valid()


def test_assetprocurement_cross_tenant_fk_injection_tag(
    client_a, operational_asset_b, capitalization_b
):
    """Submitting foreign operational asset or capitalization on tag form is rejected."""
    url = reverse("assets:asset_tag_create")

    payload = _assetprocurement_valid_tag_payload(
        operational_asset=operational_asset_b.pk,
        capitalization=capitalization_b.pk,
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert not resp.context["form"].is_valid()
