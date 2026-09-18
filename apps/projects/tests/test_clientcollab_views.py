"""Projects 7.14 Client & External Collaboration — VIEW tests.
"""
import datetime
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.accounting.models import Invoice
from apps.projects.models import (
    ClientApprovalRequest,
    ClientPortalAccess,
    ProjectClientInvoice,
    SOWAmendment,
    StatementOfWork,
    VendorHandoff,
)
from apps.projects.tests.conftest import (
    _clientcollab_amendment,
    _clientcollab_approval_request,
    _clientcollab_client_invoice,
    _clientcollab_portal_access,
    _clientcollab_sow,
    _clientcollab_today,
    _clientcollab_vendor_handoff,
)


_ALL_ROUTES = [
    ("cpa_list", False),
    ("cpa_create", False),
    ("cpa_detail", True),
    ("cpa_edit", True),
    ("cpa_delete", True),
    ("cfb_list", False),
    ("cfb_create", False),
    ("cfb_detail", True),
    ("cfb_edit", True),
    ("cfb_delete", True),
    ("cfb_approve", True),
    ("cfb_reject", True),
    ("sow_list", False),
    ("sow_create", False),
    ("sow_detail", True),
    ("sow_edit", True),
    ("sow_delete", True),
    ("sow_activate", True),
    ("sow_amendment_create", True),
    ("vhd_list", False),
    ("vhd_create", False),
    ("vhd_detail", True),
    ("vhd_edit", True),
    ("vhd_delete", True),
    ("vhd_accept", True),
    ("vhd_reject", True),
    ("pci_list", False),
    ("pci_create", False),
    ("pci_detail", True),
    ("pci_edit", True),
    ("pci_delete", True),
    ("pci_generate_invoice", True),
]


def test_clientcollab_all_routes_resolve():
    for route_name, needs_pk in _ALL_ROUTES:
        if needs_pk:
            url = reverse(f"projects:{route_name}", args=[1])
        else:
            url = reverse(f"projects:{route_name}")
        assert url.startswith("/projects/"), f"{route_name} did not resolve as expected"


# ==============================================================================================
# GET Lists & Details
# ==============================================================================================

def test_clientcollab_list_and_detail_views(
    client_a,
    tenant_a,
    clientcollab_project_a,
    clientcollab_client_org_a,
    clientcollab_vendor_org_a,
    clientcollab_contact_person_a,
):
    portal = _clientcollab_portal_access(tenant_a, clientcollab_project_a, clientcollab_contact_person_a)
    approval = _clientcollab_approval_request(tenant_a, clientcollab_project_a)
    sow = _clientcollab_sow(tenant_a, clientcollab_project_a, clientcollab_client_org_a)
    handoff = _clientcollab_vendor_handoff(tenant_a, clientcollab_project_a, clientcollab_vendor_org_a)
    invoice = _clientcollab_client_invoice(tenant_a, clientcollab_project_a)

    # Lists
    assert client_a.get(reverse("projects:cpa_list")).status_code == 200
    assert client_a.get(reverse("projects:cfb_list")).status_code == 200
    assert client_a.get(reverse("projects:sow_list")).status_code == 200
    assert client_a.get(reverse("projects:vhd_list")).status_code == 200
    assert client_a.get(reverse("projects:pci_list")).status_code == 200

    # Details
    resp = client_a.get(reverse("projects:cpa_detail", args=[portal.pk]))
    assert resp.status_code == 200
    assert portal.number.encode() in resp.content

    resp = client_a.get(reverse("projects:cfb_detail", args=[approval.pk]))
    assert resp.status_code == 200
    assert approval.number.encode() in resp.content

    resp = client_a.get(reverse("projects:sow_detail", args=[sow.pk]))
    assert resp.status_code == 200
    assert sow.number.encode() in resp.content

    resp = client_a.get(reverse("projects:vhd_detail", args=[handoff.pk]))
    assert resp.status_code == 200
    assert handoff.number.encode() in resp.content

    resp = client_a.get(reverse("projects:pci_detail", args=[invoice.pk]))
    assert resp.status_code == 200
    assert invoice.number.encode() in resp.content


# ==============================================================================================
# GET Create & Edit Forms
# ==============================================================================================

def test_clientcollab_create_and_edit_get(
    client_a,
    tenant_a,
    clientcollab_project_a,
    clientcollab_client_org_a,
    clientcollab_vendor_org_a,
    clientcollab_contact_person_a,
):
    portal = _clientcollab_portal_access(tenant_a, clientcollab_project_a, clientcollab_contact_person_a)
    approval = _clientcollab_approval_request(tenant_a, clientcollab_project_a)
    sow = _clientcollab_sow(tenant_a, clientcollab_project_a, clientcollab_client_org_a)
    handoff = _clientcollab_vendor_handoff(tenant_a, clientcollab_project_a, clientcollab_vendor_org_a)
    invoice = _clientcollab_client_invoice(tenant_a, clientcollab_project_a)

    # Create GET
    assert client_a.get(reverse("projects:cpa_create")).status_code == 200
    assert client_a.get(reverse("projects:cfb_create")).status_code == 200
    assert client_a.get(reverse("projects:sow_create")).status_code == 200
    assert client_a.get(reverse("projects:sow_amendment_create", args=[sow.pk])).status_code == 200
    assert client_a.get(reverse("projects:vhd_create")).status_code == 200
    assert client_a.get(reverse("projects:pci_create")).status_code == 200

    # Edit GET
    assert client_a.get(reverse("projects:cpa_edit", args=[portal.pk])).status_code == 200
    assert client_a.get(reverse("projects:cfb_edit", args=[approval.pk])).status_code == 200
    assert client_a.get(reverse("projects:sow_edit", args=[sow.pk])).status_code == 200
    assert client_a.get(reverse("projects:vhd_edit", args=[handoff.pk])).status_code == 200
    assert client_a.get(reverse("projects:pci_edit", args=[invoice.pk])).status_code == 200


# ==============================================================================================
# POST Lifecycle Verbs
# ==============================================================================================

def test_client_feedback_approve_and_reject(
    client_a,
    tenant_a,
    clientcollab_project_a,
):
    approval1 = _clientcollab_approval_request(tenant_a, clientcollab_project_a, status="pending_review")
    resp = client_a.post(
        reverse("projects:cfb_approve", args=[approval1.pk]),
        {"signed_by_name": "VP Technology"},
    )
    assert resp.status_code == 302
    approval1.refresh_from_db()
    assert approval1.status == "approved"
    assert approval1.signed_by_name == "VP Technology"
    assert approval1.signed_at is not None

    approval2 = _clientcollab_approval_request(tenant_a, clientcollab_project_a, status="pending_review")
    resp = client_a.post(
        reverse("projects:cfb_reject", args=[approval2.pk]),
        {"rejection_reason": "Missing security assessment."},
    )
    assert resp.status_code == 302
    approval2.refresh_from_db()
    assert approval2.status == "rejected"
    assert approval2.rejection_reason == "Missing security assessment."


def test_statement_of_work_activate_and_amend(
    client_a,
    tenant_a,
    clientcollab_project_a,
    clientcollab_client_org_a,
):
    sow = _clientcollab_sow(tenant_a, clientcollab_project_a, clientcollab_client_org_a, status="draft")
    resp = client_a.post(reverse("projects:sow_activate", args=[sow.pk]))
    assert resp.status_code == 302
    sow.refresh_from_db()
    assert sow.status == "active"
    assert sow.activated_at is not None

    # Post amendment
    resp = client_a.post(
        reverse("projects:sow_amendment_create", args=[sow.pk]),
        {
            "sow": sow.pk,
            "amendment_number": 1,
            "title": "Extended Maintenance Period",
            "effective_date": _clientcollab_today(),
            "value_change": "12000.00",
            "revised_scope": "12 months additional SLA support.",
            "justification": "Customer request.",
            "status": "approved",
        },
    )
    assert resp.status_code == 302
    assert sow.amendments.filter(title="Extended Maintenance Period").exists()
    sow.refresh_from_db()
    assert sow.total_amendments == 1
    assert sow.effective_value == Decimal("62000.00")


def test_vendor_handoff_accept_and_reject(
    client_a,
    tenant_a,
    clientcollab_project_a,
    clientcollab_vendor_org_a,
):
    handoff1 = _clientcollab_vendor_handoff(
        tenant_a, clientcollab_project_a, clientcollab_vendor_org_a, status="delivered"
    )
    resp = client_a.post(
        reverse("projects:vhd_accept", args=[handoff1.pk]),
        {"scorecard_rating": "5", "performance_notes": "Delivered ahead of schedule."},
    )
    assert resp.status_code == 302
    handoff1.refresh_from_db()
    assert handoff1.status == "accepted"
    assert handoff1.scorecard_rating == 5
    assert handoff1.performance_notes == "Delivered ahead of schedule."
    assert handoff1.accepted_at is not None

    handoff2 = _clientcollab_vendor_handoff(
        tenant_a, clientcollab_project_a, clientcollab_vendor_org_a, status="delivered"
    )
    resp = client_a.post(
        reverse("projects:vhd_reject", args=[handoff2.pk]),
        {"deficiency_notes": "Designs did not follow brand palette."},
    )
    assert resp.status_code == 302
    handoff2.refresh_from_db()
    assert handoff2.status == "rejected"
    assert handoff2.deficiency_notes == "Designs did not follow brand palette."


def test_project_client_invoice_generate_invoice(
    client_a,
    tenant_a,
    clientcollab_project_a,
    clientcollab_client_org_a,
):
    clientcollab_project_a.client = clientcollab_client_org_a
    clientcollab_project_a.save()

    invoice = _clientcollab_client_invoice(
        tenant_a,
        clientcollab_project_a,
        amount=Decimal("15000.00"),
        tax_amount=Decimal("1500.00"),
        status="draft",
    )
    resp = client_a.post(reverse("projects:pci_generate_invoice", args=[invoice.pk]))
    assert resp.status_code == 302
    invoice.refresh_from_db()
    assert invoice.status == "invoiced"
    assert invoice.invoiced_at is not None
    assert invoice.accounting_invoice.kind == "invoice"
    assert invoice.accounting_invoice.party == clientcollab_client_org_a


# ==============================================================================================
# Delete Views
# ==============================================================================================

def test_clientcollab_delete_views(
    client_a,
    tenant_a,
    clientcollab_project_a,
    clientcollab_client_org_a,
    clientcollab_vendor_org_a,
    clientcollab_contact_person_a,
):
    portal = _clientcollab_portal_access(tenant_a, clientcollab_project_a, clientcollab_contact_person_a)
    approval = _clientcollab_approval_request(tenant_a, clientcollab_project_a)
    sow = _clientcollab_sow(tenant_a, clientcollab_project_a, clientcollab_client_org_a)
    handoff = _clientcollab_vendor_handoff(tenant_a, clientcollab_project_a, clientcollab_vendor_org_a)
    invoice = _clientcollab_client_invoice(tenant_a, clientcollab_project_a)

    assert client_a.post(reverse("projects:cpa_delete", args=[portal.pk])).status_code == 302
    assert not ClientPortalAccess.objects.filter(pk=portal.pk).exists()

    assert client_a.post(reverse("projects:cfb_delete", args=[approval.pk])).status_code == 302
    assert not ClientApprovalRequest.objects.filter(pk=approval.pk).exists()

    assert client_a.post(reverse("projects:sow_delete", args=[sow.pk])).status_code == 302
    assert not StatementOfWork.objects.filter(pk=sow.pk).exists()

    assert client_a.post(reverse("projects:vhd_delete", args=[handoff.pk])).status_code == 302
    assert not VendorHandoff.objects.filter(pk=handoff.pk).exists()

    assert client_a.post(reverse("projects:pci_delete", args=[invoice.pk])).status_code == 302
    assert not ProjectClientInvoice.objects.filter(pk=invoice.pk).exists()
