"""Projects 7.14 Client & External Collaboration — FORM tests.
"""
import datetime
from decimal import Decimal

import pytest

from apps.projects.forms.ClientExternalCollaboration.ClientFeedbacks import ClientApprovalRequestForm
from apps.projects.forms.ClientExternalCollaboration.ClientInvoices import ProjectClientInvoiceForm
from apps.projects.forms.ClientExternalCollaboration.ClientPortals import ClientPortalAccessForm
from apps.projects.forms.ClientExternalCollaboration.StatementOfWorks import (
    SOWAmendmentForm,
    StatementOfWorkForm,
)
from apps.projects.forms.ClientExternalCollaboration.VendorHandoffs import VendorHandoffForm
from apps.projects.tests.conftest import (
    _clientcollab_sow,
    _clientcollab_today,
)


# ==============================================================================================
# ClientPortalAccessForm
# ==============================================================================================

def test_client_portal_access_form_valid(
    tenant_a,
    clientcollab_project_a,
    clientcollab_contact_person_a,
):
    form = ClientPortalAccessForm(
        data={
            "project": clientcollab_project_a.pk,
            "client_contact": clientcollab_contact_person_a.pk,
            "can_view_progress": True,
            "can_view_milestones": True,
            "can_view_deliverables": True,
            "can_view_financials": False,
            "can_submit_feedback": True,
            "is_active": True,
            "notes": "Portal access granted.",
        },
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors


def test_client_portal_access_form_rejects_foreign_fks(
    tenant_a,
    tenant_b,
    clientcollab_project_a,
    clientcollab_project_b,
    clientcollab_contact_person_a,
    clientcollab_contact_person_b,
):
    # Foreign project
    form = ClientPortalAccessForm(
        data={
            "project": clientcollab_project_b.pk,
            "client_contact": clientcollab_contact_person_a.pk,
            "is_active": True,
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "project" in form.errors

    # Foreign contact
    form = ClientPortalAccessForm(
        data={
            "project": clientcollab_project_a.pk,
            "client_contact": clientcollab_contact_person_b.pk,
            "is_active": True,
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "client_contact" in form.errors


# ==============================================================================================
# ClientApprovalRequestForm
# ==============================================================================================

def test_client_approval_request_form_valid(
    tenant_a,
    clientcollab_project_a,
    clientcollab_contact_person_a,
):
    form = ClientApprovalRequestForm(
        data={
            "project": clientcollab_project_a.pk,
            "deliverable_name": "API Spec Sign-off",
            "assigned_contact": clientcollab_contact_person_a.pk,
            "status": "draft",
            "due_date": _clientcollab_today() + datetime.timedelta(days=7),
            "review_notes": "Please check section 3.",
        },
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors


def test_client_approval_request_form_rejects_foreign_fks(
    tenant_a,
    tenant_b,
    clientcollab_project_a,
    clientcollab_project_b,
    clientcollab_contact_person_a,
    clientcollab_contact_person_b,
):
    form = ClientApprovalRequestForm(
        data={
            "project": clientcollab_project_b.pk,
            "deliverable_name": "Invalid Spec",
            "assigned_contact": clientcollab_contact_person_a.pk,
            "status": "draft",
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "project" in form.errors

    form = ClientApprovalRequestForm(
        data={
            "project": clientcollab_project_a.pk,
            "deliverable_name": "Invalid Contact",
            "assigned_contact": clientcollab_contact_person_b.pk,
            "status": "draft",
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "assigned_contact" in form.errors


# ==============================================================================================
# StatementOfWorkForm & SOWAmendmentForm
# ==============================================================================================

def test_statement_of_work_form_valid(
    tenant_a,
    clientcollab_project_a,
    clientcollab_client_org_a,
):
    form = StatementOfWorkForm(
        data={
            "project": clientcollab_project_a.pk,
            "client": clientcollab_client_org_a.pk,
            "title": "Core System Build SOW",
            "sow_code": "SOW-2026-001",
            "billing_type": "fixed_fee",
            "contract_value": "45000.00",
            "start_date": _clientcollab_today(),
            "end_date": _clientcollab_today() + datetime.timedelta(days=60),
            "status": "draft",
            "scope_summary": "Core deliverables only.",
            "terms_and_conditions": "Net 30 terms.",
        },
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors


def test_statement_of_work_form_date_validation(
    tenant_a,
    clientcollab_project_a,
    clientcollab_client_org_a,
):
    form = StatementOfWorkForm(
        data={
            "project": clientcollab_project_a.pk,
            "client": clientcollab_client_org_a.pk,
            "title": "Invalid Dates SOW",
            "billing_type": "fixed_fee",
            "contract_value": "10000.00",
            "start_date": _clientcollab_today() + datetime.timedelta(days=30),
            "end_date": _clientcollab_today(),  # end before start
            "status": "draft",
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "end_date" in form.errors


def test_statement_of_work_form_rejects_foreign_fks(
    tenant_a,
    tenant_b,
    clientcollab_project_a,
    clientcollab_project_b,
    clientcollab_client_org_a,
    clientcollab_client_org_b,
):
    form = StatementOfWorkForm(
        data={
            "project": clientcollab_project_b.pk,
            "client": clientcollab_client_org_a.pk,
            "title": "Foreign Project SOW",
            "start_date": _clientcollab_today(),
            "end_date": _clientcollab_today() + datetime.timedelta(days=10),
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "project" in form.errors

    form = StatementOfWorkForm(
        data={
            "project": clientcollab_project_a.pk,
            "client": clientcollab_client_org_b.pk,
            "title": "Foreign Client SOW",
            "start_date": _clientcollab_today(),
            "end_date": _clientcollab_today() + datetime.timedelta(days=10),
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "client" in form.errors


def test_sow_amendment_form_valid(
    tenant_a,
    clientcollab_project_a,
    clientcollab_client_org_a,
):
    sow = _clientcollab_sow(tenant_a, clientcollab_project_a, clientcollab_client_org_a)
    form = SOWAmendmentForm(
        data={
            "sow": sow.pk,
            "amendment_number": 1,
            "title": "Additional Scope Amendment",
            "effective_date": _clientcollab_today(),
            "value_change": "5000.00",
            "revised_scope": "Included reporting dashboard.",
            "justification": "Requested by client sponsor.",
            "status": "draft",
        },
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors


def test_sow_amendment_form_rejects_foreign_sow(
    tenant_a,
    tenant_b,
    clientcollab_project_a,
    clientcollab_project_b,
    clientcollab_client_org_a,
    clientcollab_client_org_b,
):
    foreign_sow = _clientcollab_sow(tenant_b, clientcollab_project_b, clientcollab_client_org_b)
    form = SOWAmendmentForm(
        data={
            "sow": foreign_sow.pk,
            "amendment_number": 1,
            "title": "Cross Tenant Amendment",
            "effective_date": _clientcollab_today(),
            "value_change": "1000.00",
            "status": "draft",
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "sow" in form.errors


# ==============================================================================================
# VendorHandoffForm
# ==============================================================================================

def test_vendor_handoff_form_valid(
    tenant_a,
    clientcollab_project_a,
    clientcollab_vendor_org_a,
):
    form = VendorHandoffForm(
        data={
            "project": clientcollab_project_a.pk,
            "vendor": clientcollab_vendor_org_a.pk,
            "title": "Mobile Mockups Delivery",
            "description": "Figma files handover.",
            "handoff_date": _clientcollab_today(),
            "due_date": _clientcollab_today() + datetime.timedelta(days=14),
            "status": "assigned",
            "deliverable_link": "https://figma.com/file/123",
            "scorecard_rating": 4,
            "performance_notes": "High quality deliverables.",
        },
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors


def test_vendor_handoff_form_date_validation(
    tenant_a,
    clientcollab_project_a,
    clientcollab_vendor_org_a,
):
    form = VendorHandoffForm(
        data={
            "project": clientcollab_project_a.pk,
            "vendor": clientcollab_vendor_org_a.pk,
            "title": "Invalid Dates Handoff",
            "handoff_date": _clientcollab_today() + datetime.timedelta(days=5),
            "due_date": _clientcollab_today(),  # due before handoff
            "status": "assigned",
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "due_date" in form.errors


def test_vendor_handoff_form_rejects_foreign_fks(
    tenant_a,
    tenant_b,
    clientcollab_project_a,
    clientcollab_project_b,
    clientcollab_vendor_org_a,
    clientcollab_vendor_org_b,
):
    form = VendorHandoffForm(
        data={
            "project": clientcollab_project_b.pk,
            "vendor": clientcollab_vendor_org_a.pk,
            "title": "Foreign Project Handoff",
            "handoff_date": _clientcollab_today(),
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "project" in form.errors

    form = VendorHandoffForm(
        data={
            "project": clientcollab_project_a.pk,
            "vendor": clientcollab_vendor_org_b.pk,
            "title": "Foreign Vendor Handoff",
            "handoff_date": _clientcollab_today(),
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "vendor" in form.errors


# ==============================================================================================
# ProjectClientInvoiceForm
# ==============================================================================================

def test_project_client_invoice_form_valid(
    tenant_a,
    clientcollab_project_a,
    clientcollab_client_org_a,
):
    sow = _clientcollab_sow(tenant_a, clientcollab_project_a, clientcollab_client_org_a)
    form = ProjectClientInvoiceForm(
        data={
            "project": clientcollab_project_a.pk,
            "sow": sow.pk,
            "billing_type": "milestone",
            "billing_date": _clientcollab_today(),
            "due_date": _clientcollab_today() + datetime.timedelta(days=30),
            "amount": "15000.00",
            "tax_amount": "1500.00",
            "status": "draft",
            "notes": "Milestone 1 invoice.",
        },
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors


def test_project_client_invoice_form_date_validation(
    tenant_a,
    clientcollab_project_a,
):
    form = ProjectClientInvoiceForm(
        data={
            "project": clientcollab_project_a.pk,
            "billing_type": "fixed_fee",
            "billing_date": _clientcollab_today() + datetime.timedelta(days=10),
            "due_date": _clientcollab_today(),  # due before billing date
            "amount": "5000.00",
            "tax_amount": "0.00",
            "status": "draft",
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "due_date" in form.errors


def test_project_client_invoice_form_rejects_foreign_fks(
    tenant_a,
    tenant_b,
    clientcollab_project_a,
    clientcollab_project_b,
    clientcollab_client_org_b,
):
    foreign_sow = _clientcollab_sow(tenant_b, clientcollab_project_b, clientcollab_client_org_b)

    form = ProjectClientInvoiceForm(
        data={
            "project": clientcollab_project_b.pk,
            "billing_type": "milestone",
            "billing_date": _clientcollab_today(),
            "amount": "1000.00",
            "tax_amount": "0.00",
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "project" in form.errors

    form = ProjectClientInvoiceForm(
        data={
            "project": clientcollab_project_a.pk,
            "sow": foreign_sow.pk,
            "billing_type": "milestone",
            "billing_date": _clientcollab_today(),
            "amount": "1000.00",
            "tax_amount": "0.00",
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "sow" in form.errors
