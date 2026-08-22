"""Procurement 6.2 - Requisition Management view flows (requisitions/templates/amendments).

Every surface is exercised through the rendered BYTES and real redirects. The load-bearing
contracts here: templates APPLY into scm's requisition spine as drafts under the signed-in
user (never a choosable requester), amendments are filed by any member but decided only by a
tenant admin (and ONLY approval mutates the spine), one open amendment per requisition, and
the duplicate check explains itself ("same title") instead of scoring silently.
"""
import datetime
from decimal import Decimal

import pytest

from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.procurement.models import (
    RequisitionAmendment,
    RequisitionTemplate,
    RequisitionTemplateLine,
)
from apps.procurement.views._helpers import find_duplicate_requisitions
from apps.scm.models import PurchaseRequisition

pytestmark = pytest.mark.django_db


def mgmt(total, initial=0):
    """The four hidden ``lines-*`` keys both 6.2 inline line formsets POST (prefix "lines":
    each child FK declares related_name="lines", which IS the inline formset default prefix)."""
    return {
        "lines-TOTAL_FORMS": str(total),
        "lines-INITIAL_FORMS": str(initial),
        "lines-MIN_NUM_FORMS": "0",
        "lines-MAX_NUM_FORMS": "1000",
    }


def amendment_cancel_payload():
    data = {"amendment_type": "cancel", "reason": "No longer needed"}
    data.update(mgmt(0))
    return data


def _pr_count(tenant):
    return PurchaseRequisition.objects.filter(tenant=tenant).count()


# ------------------------------------------------------------------ pages render


def test_reqmgmt_req_list_shows_number_and_status_badge(client_a, requisition_approved_a):
    resp = client_a.get(reverse("procurement:req_list"))
    assert resp.status_code == 200
    body = resp.content.decode()
    assert requisition_approved_a.number in body
    assert 'badge-green">Approved</span>' in body


def test_reqmgmt_req_list_dupes_filter_returns_200(client_a, requisition_pending_a):
    resp = client_a.get(reverse("procurement:req_list"), {"dupes": "1"})
    assert resp.status_code == 200
    assert "Duplicate watch" in resp.content.decode()


def test_reqmgmt_template_list_shows_annotated_line_count_and_total(
        client_a, template_with_lines_a):
    resp = client_a.get(reverse("procurement:template_list"))
    assert resp.status_code == 200
    body = resp.content.decode()
    assert template_with_lines_a.number in body
    assert "Monthly office supplies" in body
    assert "<td>2</td>" in body      # n_lines annotation
    assert "102.60" in body          # est_total annotation (4*22.50 + 3*4.20)


def test_reqmgmt_template_create_and_edit_render_line_formset_management_form(
        client_a, template_with_lines_a):
    create = client_a.get(reverse("procurement:template_create"))
    assert create.status_code == 200
    assert b'name="lines-TOTAL_FORMS"' in create.content
    edit = client_a.get(reverse("procurement:template_edit",
                                args=[template_with_lines_a.pk]))
    assert edit.status_code == 200
    assert b'name="lines-TOTAL_FORMS"' in edit.content
    assert "A4 printer paper" in edit.content.decode()


def test_reqmgmt_template_create_post_stamps_created_by_and_saves_lines(
        client_a, tenant_a, admin_user, org_unit_a, gl_expense_a, usd):
    data = {
        "name": "Weekly toner restock",
        "description": "",
        "org_unit": str(org_unit_a.pk),
        "currency": str(usd.pk),
        "default_lead_days": "5",
        "justification": "Printers eat toner.",
        "is_active": "on",
        "lines-0-item_description": "Toner cartridge black",
        "lines-0-sku_hint": "",
        "lines-0-uom_hint": "",
        "lines-0-quantity": "2",
        "lines-0-estimated_unit_price": "55.00",
        "lines-0-gl_account": str(gl_expense_a.pk),
    }
    data.update(mgmt(1))
    resp = client_a.post(reverse("procurement:template_create"), data)
    assert resp.status_code == 302
    template = RequisitionTemplate.objects.get(tenant=tenant_a, name="Weekly toner restock")
    assert resp.url == reverse("procurement:template_detail", args=[template.pk])
    assert template.created_by == admin_user
    assert template.is_active is True
    assert template.lines.count() == 1
    line = template.lines.get()
    assert (line.item_description, line.quantity, line.estimated_unit_price) == \
        ("Toner cartridge black", Decimal("2"), Decimal("55.00"))
    assert line.gl_account == gl_expense_a


# ------------------------------------------------------------------ template apply


def test_reqmgmt_template_apply_drafts_requisition_on_spine(
        client_a, tenant_a, admin_user, template_with_lines_a):
    before = _pr_count(tenant_a)
    resp = client_a.post(reverse("procurement:template_apply",
                                 args=[template_with_lines_a.pk]))
    assert resp.status_code == 302
    req = PurchaseRequisition.objects.get(tenant=tenant_a,
                                          title="Monthly office supplies")
    assert resp.url == f"/procurement/requisitions/{req.pk}/"
    assert PurchaseRequisition.objects.filter(tenant=tenant_a).count() == before + 1
    assert req.requester == admin_user          # the SIGNED-IN user, never choosable
    assert req.status == "draft"
    assert req.estimated_total == Decimal("102.60")
    assert req.lines.count() == 2
    assert req.required_by == datetime.date.today() + datetime.timedelta(days=7)


def test_reqmgmt_template_apply_zero_line_template_refused(client_a, tenant_a):
    empty = RequisitionTemplate.objects.create(tenant=tenant_a, name="Empty blueprint")
    before = _pr_count(tenant_a)
    resp = client_a.post(reverse("procurement:template_apply", args=[empty.pk]), follow=True)
    assert resp.status_code == 200
    assert resp.redirect_chain[-1][0] == reverse("procurement:template_detail",
                                                 args=[empty.pk])
    assert "has no lines" in resp.content.decode()
    assert _pr_count(tenant_a) == before
    assert not PurchaseRequisition.objects.filter(title="Empty blueprint").exists()


def test_reqmgmt_template_apply_inactive_template_refused(
        client_a, tenant_a, template_with_lines_a):
    template_with_lines_a.is_active = False
    template_with_lines_a.save(update_fields=["is_active"])
    before = _pr_count(tenant_a)
    resp = client_a.post(reverse("procurement:template_apply",
                                 args=[template_with_lines_a.pk]), follow=True)
    assert resp.status_code == 200
    assert "inactive and cannot be applied" in resp.content.decode()
    assert _pr_count(tenant_a) == before
    assert not PurchaseRequisition.objects.filter(title="Monthly office supplies").exists()


# ------------------------------------------------------------------ amendment filing


def test_reqmgmt_amendment_create_files_pending_cancel(
        client_a, tenant_a, admin_user, requisition_pending_a):
    resp = client_a.post(reverse("procurement:req_amendment_create",
                                 args=[requisition_pending_a.pk]),
                         amendment_cancel_payload())
    assert resp.status_code == 302
    amendment = RequisitionAmendment.objects.get(tenant=tenant_a,
                                                 requisition=requisition_pending_a)
    assert resp.url == reverse("procurement:amendment_detail", args=[amendment.pk])
    assert amendment.status == "pending"
    assert amendment.amendment_type == "cancel"
    assert amendment.reason == "No longer needed"
    assert amendment.requested_by == admin_user
    assert amendment.decided_at is None and amendment.applied_at is None


def test_reqmgmt_amendment_create_one_open_rule_blocks_second_filing(
        client_a, tenant_a, requisition_pending_a):
    client_a.post(reverse("procurement:req_amendment_create",
                          args=[requisition_pending_a.pk]),
                  amendment_cancel_payload())
    resp = client_a.post(reverse("procurement:req_amendment_create",
                                 args=[requisition_pending_a.pk]),
                         amendment_cancel_payload(), follow=True)
    assert resp.status_code == 200
    assert resp.redirect_chain[-1][0] == reverse("procurement:req_detail",
                                                 args=[requisition_pending_a.pk])
    assert "already has a pending amendment" in resp.content.decode()
    assert RequisitionAmendment.objects.filter(
        tenant=tenant_a, requisition=requisition_pending_a).count() == 1


def test_reqmgmt_amendment_create_draft_requisition_refused(
        client_a, tenant_a, admin_user):
    draft = PurchaseRequisition.objects.create(tenant=tenant_a, title="Still a draft",
                                               requester=admin_user)
    resp = client_a.post(reverse("procurement:req_amendment_create", args=[draft.pk]),
                         amendment_cancel_payload(), follow=True)
    assert resp.status_code == 200
    assert resp.redirect_chain[-1][0] == reverse("procurement:req_detail", args=[draft.pk])
    assert "cannot be amended" in resp.content.decode()
    assert not RequisitionAmendment.objects.filter(tenant=tenant_a).exists()


# ------------------------------------------------------------------ amendment decisions


def test_reqmgmt_amendment_approve_applies_change_to_requisition(
        client_a, requisition_approved_a, amendment_pending_a):
    resp = client_a.post(reverse("procurement:amendment_approve",
                                 args=[amendment_pending_a.pk]),
                         {"decision_note": "Vendor confirmed date"})
    assert resp.status_code == 302
    assert resp.url == reverse("procurement:req_detail",
                               args=[requisition_approved_a.pk])
    amendment_pending_a.refresh_from_db()
    requisition_approved_a.refresh_from_db()
    assert amendment_pending_a.status == "approved"
    assert amendment_pending_a.applied_at is not None
    assert amendment_pending_a.decision_note == "Vendor confirmed date"
    assert requisition_approved_a.required_by == amendment_pending_a.new_required_by


def test_reqmgmt_amendment_approve_member_forbidden(member_client, amendment_pending_a):
    resp = member_client.post(reverse("procurement:amendment_approve",
                                      args=[amendment_pending_a.pk]))
    assert resp.status_code == 403
    amendment_pending_a.refresh_from_db()
    assert amendment_pending_a.status == "pending"
    assert amendment_pending_a.applied_at is None


def test_reqmgmt_amendment_reject_without_reason_stays_pending(
        client_a, amendment_pending_a):
    resp = client_a.post(reverse("procurement:amendment_reject",
                                 args=[amendment_pending_a.pk]), {}, follow=True)
    assert resp.status_code == 200
    assert resp.redirect_chain[-1][0] == reverse("procurement:amendment_detail",
                                                 args=[amendment_pending_a.pk])
    assert "Give a reason when rejecting an amendment." in resp.content.decode()
    amendment_pending_a.refresh_from_db()
    assert amendment_pending_a.status == "pending"


def test_reqmgmt_amendment_reject_with_reason_decides(client_a, admin_user,
                                                      amendment_pending_a):
    resp = client_a.post(reverse("procurement:amendment_reject",
                                 args=[amendment_pending_a.pk]),
                         {"decision_note": "Duplicate of an existing request"})
    assert resp.status_code == 302
    assert resp.url == reverse("procurement:amendment_detail",
                               args=[amendment_pending_a.pk])
    amendment_pending_a.refresh_from_db()
    assert amendment_pending_a.status == "rejected"
    assert amendment_pending_a.decided_by == admin_user
    assert amendment_pending_a.decided_at is not None
    assert amendment_pending_a.applied_at is None


# ------------------------------------------------------------------ duplicate check


def test_reqmgmt_duplicate_panel_flags_same_title(client_a, tenant_a, admin_user):
    first = PurchaseRequisition.objects.create(tenant=tenant_a, title="Standing desk order",
                                               requester=admin_user)
    second = PurchaseRequisition.objects.create(tenant=tenant_a, title="Standing desk order",
                                                requester=admin_user)

    found = find_duplicate_requisitions(first)
    assert [d["requisition"].pk for d in found] == [second.pk]
    assert found[0]["reasons"] == ["same title"]

    resp = client_a.get(reverse("procurement:req_detail", args=[first.pk]))
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Potential duplicates" in body
    assert "same title" in body
    assert second.number in body


# ------------------------------------------------------------------ tenancy & tenant-less


def test_reqmgmt_cross_tenant_reads_are_404(client_b, requisition_approved_a,
                                            template_with_lines_a, amendment_pending_a):
    assert client_b.get(reverse("procurement:req_detail",
                                args=[requisition_approved_a.pk])).status_code == 404
    assert client_b.get(reverse("procurement:template_edit",
                                args=[template_with_lines_a.pk])).status_code == 404
    assert client_b.get(reverse("procurement:amendment_detail",
                                args=[amendment_pending_a.pk])).status_code == 404


def test_reqmgmt_tenantless_superuser_redirects_not_500(db):
    root = User.objects.create_user(email="root@naverp.io", username="root",
                                    password="TestPass123!", tenant=None,
                                    is_superuser=True)
    c = Client()
    c.force_login(root)
    resp = c.get(reverse("procurement:req_list"))
    assert resp.status_code == 302
    assert resp.url == reverse("dashboard:home")
