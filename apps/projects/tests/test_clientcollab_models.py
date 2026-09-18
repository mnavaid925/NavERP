"""Projects 7.14 Client & External Collaboration — MODEL tests.
"""
import datetime
from decimal import Decimal
import re

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

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


# ==============================================================================================
# Numbering & Prefixes
# ==============================================================================================

def test_clientcollab_each_model_mints_its_own_prefix(
    tenant_a,
    clientcollab_project_a,
    clientcollab_client_org_a,
    clientcollab_vendor_org_a,
    clientcollab_contact_person_a,
):
    portal = _clientcollab_portal_access(tenant_a, clientcollab_project_a, clientcollab_contact_person_a)
    approval = _clientcollab_approval_request(tenant_a, clientcollab_project_a)
    sow = _clientcollab_sow(tenant_a, clientcollab_project_a, clientcollab_client_org_a)
    amendment = _clientcollab_amendment(tenant_a, sow)
    handoff = _clientcollab_vendor_handoff(tenant_a, clientcollab_project_a, clientcollab_vendor_org_a)
    invoice = _clientcollab_client_invoice(tenant_a, clientcollab_project_a)

    assert re.fullmatch(r"CPA-\d{5}", portal.number)
    assert re.fullmatch(r"CFB-\d{5}", approval.number)
    assert re.fullmatch(r"SOW-\d{5}", sow.number)
    assert re.fullmatch(r"SWA-\d{5}", amendment.number)
    assert re.fullmatch(r"VHD-\d{5}", handoff.number)
    assert re.fullmatch(r"PCI-\d{5}", invoice.number)


def test_clientcollab_numbers_advance_per_tenant(
    tenant_a,
    clientcollab_project_a,
    clientcollab_client_org_a,
):
    sow1 = _clientcollab_sow(tenant_a, clientcollab_project_a, clientcollab_client_org_a, title="SOW 1")
    sow2 = _clientcollab_sow(tenant_a, clientcollab_project_a, clientcollab_client_org_a, title="SOW 2")

    n1 = int(sow1.number.split("-")[1])
    n2 = int(sow2.number.split("-")[1])
    assert n2 == n1 + 1


# ==============================================================================================
# String representations (__str__)
# ==============================================================================================

def test_clientcollab_str_representations(
    tenant_a,
    clientcollab_project_a,
    clientcollab_client_org_a,
    clientcollab_vendor_org_a,
    clientcollab_contact_person_a,
):
    portal = _clientcollab_portal_access(tenant_a, clientcollab_project_a, clientcollab_contact_person_a)
    assert str(portal) == f"{portal.number} — {clientcollab_contact_person_a.name} ({clientcollab_project_a.name})"

    approval = _clientcollab_approval_request(
        tenant_a, clientcollab_project_a, deliverable_name="UAT Approval", status="draft"
    )
    assert str(approval) == f"{approval.number} — UAT Approval (Draft)"

    sow = _clientcollab_sow(tenant_a, clientcollab_project_a, clientcollab_client_org_a, title="Main Services")
    assert str(sow) == f"{sow.number} — Main Services ({clientcollab_project_a.name})"

    amendment = _clientcollab_amendment(tenant_a, sow, amendment_number=2, title="Additional Server")
    assert str(amendment) == f"{amendment.number} — {sow.number} #2: Additional Server"

    handoff = _clientcollab_vendor_handoff(
        tenant_a, clientcollab_project_a, clientcollab_vendor_org_a, title="Design Specs"
    )
    assert str(handoff) == f"{handoff.number} — Design Specs ({clientcollab_vendor_org_a.name})"

    invoice = _clientcollab_client_invoice(
        tenant_a, clientcollab_project_a, amount=Decimal("10000.00"), tax_amount=Decimal("1500.00")
    )
    assert str(invoice) == f"{invoice.number} — {clientcollab_project_a.name} (11500.00)"


# ==============================================================================================
# Computed properties & logic
# ==============================================================================================

def test_statement_of_work_amendment_calculations(
    tenant_a,
    clientcollab_project_a,
    clientcollab_client_org_a,
):
    sow = _clientcollab_sow(
        tenant_a,
        clientcollab_project_a,
        clientcollab_client_org_a,
        contract_value=Decimal("100000.00"),
    )
    assert sow.total_amendments == 0
    assert sow.effective_value == Decimal("100000.00")

    # Draft amendment does not affect total_amendments or effective_value
    _clientcollab_amendment(
        tenant_a,
        sow,
        amendment_number=1,
        value_change=Decimal("25000.00"),
        status="draft",
    )
    sow.refresh_from_db()
    assert sow.total_amendments == 0
    assert sow.effective_value == Decimal("100000.00")

    # Approved amendment affects both
    _clientcollab_amendment(
        tenant_a,
        sow,
        amendment_number=2,
        value_change=Decimal("30000.00"),
        status="approved",
    )
    sow.refresh_from_db()
    assert sow.total_amendments == 1
    assert sow.effective_value == Decimal("130000.00")

    # Negative approved amendment
    _clientcollab_amendment(
        tenant_a,
        sow,
        amendment_number=3,
        value_change=Decimal("-10000.00"),
        status="approved",
    )
    sow.refresh_from_db()
    assert sow.total_amendments == 2
    assert sow.effective_value == Decimal("120000.00")


def test_project_client_invoice_amounts_and_tax(
    tenant_a,
    clientcollab_project_a,
):
    inv = _clientcollab_client_invoice(
        tenant_a,
        clientcollab_project_a,
        amount=Decimal("5000.00"),
        tax_amount=Decimal("500.00"),
    )
    assert inv.total_amount == Decimal("5500.00")

    inv.amount = Decimal("8000.00")
    inv.tax_amount = Decimal("800.00")
    inv.save()
    assert inv.total_amount == Decimal("8800.00")


def test_client_portal_access_is_expired(
    tenant_a,
    clientcollab_project_a,
    clientcollab_contact_person_a,
):
    portal_active = _clientcollab_portal_access(
        tenant_a,
        clientcollab_project_a,
        clientcollab_contact_person_a,
        expires_at=None,
    )
    assert portal_active.is_expired is False

    past = timezone.now() - datetime.timedelta(days=2)
    portal_active.expires_at = past
    portal_active.save()
    assert portal_active.is_expired is True

    future = timezone.now() + datetime.timedelta(days=10)
    portal_active.expires_at = future
    portal_active.save()
    assert portal_active.is_expired is False


# ==============================================================================================
# Choices and defaults
# ==============================================================================================

def test_clientcollab_choices_and_defaults(
    tenant_a,
    clientcollab_project_a,
    clientcollab_client_org_a,
    clientcollab_contact_person_a,
):
    portal = ClientPortalAccess(
        tenant=tenant_a,
        project=clientcollab_project_a,
        client_contact=clientcollab_contact_person_a,
    )
    assert portal.can_view_progress is True
    assert portal.can_view_milestones is True
    assert portal.can_view_deliverables is True
    assert portal.can_view_financials is False
    assert portal.can_submit_feedback is True
    assert portal.is_active is True

    approval = ClientApprovalRequest(
        tenant=tenant_a,
        project=clientcollab_project_a,
        deliverable_name="Test Deliverable",
    )
    assert approval.status == "draft"

    sow = StatementOfWork(
        tenant=tenant_a,
        project=clientcollab_project_a,
        client=clientcollab_client_org_a,
        title="Test SOW",
        start_date=_clientcollab_today(),
        end_date=_clientcollab_today() + datetime.timedelta(days=30),
    )
    assert sow.billing_type == "fixed_fee"
    assert sow.status == "draft"
    assert sow.contract_value == Decimal("0.00")

    invoice = ProjectClientInvoice(
        tenant=tenant_a,
        project=clientcollab_project_a,
    )
    assert invoice.billing_type == "milestone"
    assert invoice.status == "draft"
    assert invoice.amount == Decimal("0.00")
    assert invoice.tax_amount == Decimal("0.00")


# ==============================================================================================
# Model Constraints
# ==============================================================================================

def test_client_portal_access_unique_per_contact_project(
    tenant_a,
    clientcollab_project_a,
    clientcollab_contact_person_a,
):
    _clientcollab_portal_access(tenant_a, clientcollab_project_a, clientcollab_contact_person_a)
    with pytest.raises((ValidationError, IntegrityError)):
        _clientcollab_portal_access(tenant_a, clientcollab_project_a, clientcollab_contact_person_a)


def test_statement_of_work_dates_required(
    tenant_a,
    clientcollab_project_a,
    clientcollab_client_org_a,
):
    sow = StatementOfWork(
        tenant=tenant_a,
        project=clientcollab_project_a,
        client=clientcollab_client_org_a,
        title="No dates SOW",
        start_date=None,
        end_date=None,
    )
    with pytest.raises(ValidationError) as exc:
        sow.full_clean()
    assert "start_date" in exc.value.message_dict
    assert "end_date" in exc.value.message_dict


def test_vendor_handoff_scorecard_rating_range(
    tenant_a,
    clientcollab_project_a,
    clientcollab_vendor_org_a,
):
    handoff = VendorHandoff(
        tenant=tenant_a,
        project=clientcollab_project_a,
        vendor=clientcollab_vendor_org_a,
        title="Score Test",
        scorecard_rating=6,  # Valid range is 1-5
    )
    with pytest.raises(ValidationError) as exc:
        handoff.full_clean()
    assert "scorecard_rating" in exc.value.message_dict
