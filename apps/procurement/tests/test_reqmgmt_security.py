"""Procurement 6.2 - security posture of the Requisition Management surfaces.

The headline contracts pinned here: every read AND mutating verb 404s across the tenant
line, crafted-POST FK smuggling (a foreign ``target_line``, ``org_unit`` or ``gl_account``)
lands as a rendered validation error with nothing written, deciding amendments is
tenant-admin-only while GET never mutates, terminal requisition statuses cannot be amended,
an already-decided amendment can never be applied twice, template names are HTML-escaped,
and the duplicate-check engine answers strictly inside its own workspace.
"""
import datetime

import pytest
from django.test import Client
from django.urls import reverse

from apps.procurement.models import (
    RequisitionAmendment,
    RequisitionAmendmentLine,
    RequisitionTemplate,
    RequisitionTemplateLine,
)
from apps.procurement.views._helpers import find_duplicate_requisitions
from apps.scm.models import PurchaseRequisition

pytestmark = pytest.mark.django_db


def mgmt(total, initial=0):
    """The four hidden ``lines-*`` keys both 6.2 inline line formsets POST."""
    return {
        "lines-TOTAL_FORMS": str(total),
        "lines-INITIAL_FORMS": str(initial),
        "lines-MIN_NUM_FORMS": "0",
        "lines-MAX_NUM_FORMS": "1000",
    }


def _spine_pr(tenant, requester, title, status="draft"):
    """A raw scm-spine requisition for whichever workspace the test needs."""
    return PurchaseRequisition.objects.create(
        tenant=tenant, title=title, requester=requester, status=status,
        required_by=datetime.date.today() + datetime.timedelta(days=5),
        justification="Security fixture.")


# ------------------------------------------------------------------ cross-tenant IDOR


class TestCrossTenantIDOR:
    def test_reqmgmt_idor_detail_reads_are_404(self, client_b, requisition_approved_a,
                                               template_with_lines_a, amendment_pending_a):
        assert client_b.get(reverse(
            "procurement:req_detail",
            args=[requisition_approved_a.pk])).status_code == 404
        assert client_b.get(reverse(
            "procurement:template_detail",
            args=[template_with_lines_a.pk])).status_code == 404
        assert client_b.get(reverse(
            "procurement:template_edit",
            args=[template_with_lines_a.pk])).status_code == 404
        assert client_b.get(reverse(
            "procurement:amendment_detail",
            args=[amendment_pending_a.pk])).status_code == 404

    def test_reqmgmt_idor_amendment_form_get_and_post_are_404(
            self, client_b, tenant_a, requisition_approved_a):
        url = reverse("procurement:req_amendment_create",
                      args=[requisition_approved_a.pk])
        assert client_b.get(url).status_code == 404
        assert client_b.post(url, {"amendment_type": "cancel",
                                   "reason": "Foreign hijack"}).status_code == 404
        assert not RequisitionAmendment.objects.filter(tenant=tenant_a).exists()

    def test_reqmgmt_idor_mutating_posts_are_404_and_change_nothing(
            self, client_b, requisition_approved_a, template_with_lines_a,
            amendment_pending_a):
        before = PurchaseRequisition.objects.count()
        assert client_b.post(reverse(
            "procurement:template_apply",
            args=[template_with_lines_a.pk])).status_code == 404
        assert PurchaseRequisition.objects.count() == before      # drafted nowhere
        assert client_b.post(reverse(
            "procurement:amendment_approve",
            args=[amendment_pending_a.pk])).status_code == 404
        assert client_b.post(reverse(
            "procurement:amendment_reject",
            args=[amendment_pending_a.pk])).status_code == 404
        assert client_b.post(reverse(
            "procurement:template_delete",
            args=[template_with_lines_a.pk])).status_code == 404
        amendment_pending_a.refresh_from_db()
        assert amendment_pending_a.status == "pending"
        assert RequisitionTemplate.objects.filter(
            pk=template_with_lines_a.pk).exists()


# ------------------------------------------------------------------ crafted-POST FK smuggling


class TestCraftedPostSmuggling:
    def test_reqmgmt_smuggled_amendment_target_line_rejected(
            self, client_a, tenant_a, requisition_pending_a, requisition_approved_a):
        """A hand-posted ``target_line`` from ANOTHER requisition must be refused outright."""
        foreign_line = requisition_approved_a.lines.first()
        data = {"amendment_type": "amend", "reason": "Crafted target"}
        data.update(mgmt(1))
        data.update({
            "lines-0-action": "update",
            "lines-0-target_line": str(foreign_line.pk),
            "lines-0-item_description": "",
            "lines-0-sku_hint": "",
            "lines-0-uom_hint": "",
            "lines-0-quantity": "99",
            "lines-0-estimated_unit_price": "",
            "lines-0-needed_by": "",
        })
        resp = client_a.post(reverse("procurement:req_amendment_create",
                                     args=[requisition_pending_a.pk]), data)
        assert resp.status_code == 200                       # re-rendered with errors
        formset = resp.context["formset"]
        assert not formset.is_valid()
        assert "target_line" in formset.errors[0]
        body = resp.content.decode()
        assert "different requisition" in body or \
            "not one of the available choices" in body
        assert not RequisitionAmendment.objects.filter(tenant=tenant_a).exists()
        assert RequisitionAmendmentLine.objects.count() == 0

    def test_reqmgmt_smuggled_template_org_unit_rejected(
            self, client_a, tenant_a, org_unit_b):
        data = {"name": "Foreign department probe", "description": "",
                "org_unit": str(org_unit_b.pk), "currency": "",
                "default_lead_days": "", "justification": ""}
        data.update(mgmt(0))
        resp = client_a.post(reverse("procurement:template_create"), data)
        assert resp.status_code == 200
        assert "org_unit" in resp.context["form"].errors
        body = resp.content.decode()
        assert "another workspace" in body or "not one of the available choices" in body
        assert not RequisitionTemplate.objects.filter(tenant=tenant_a).exists()

    def test_reqmgmt_smuggled_template_gl_account_row_rejected(
            self, client_a, tenant_a, gl_expense_b):
        """The line formset re-checks each row's GL account even though the header is valid."""
        data = {"name": "Charged elsewhere", "description": "", "org_unit": "",
                "currency": "", "default_lead_days": "", "justification": ""}
        data.update(mgmt(1))
        data.update({
            "lines-0-item_description": "Mystery item",
            "lines-0-sku_hint": "",
            "lines-0-uom_hint": "",
            "lines-0-quantity": "1",
            "lines-0-estimated_unit_price": "10.00",
            "lines-0-gl_account": str(gl_expense_b.pk),
        })
        resp = client_a.post(reverse("procurement:template_create"), data)
        assert resp.status_code == 200
        formset = resp.context["formset"]
        assert not formset.is_valid()
        assert "gl_account" in formset.errors[0]
        assert not RequisitionTemplate.objects.filter(tenant=tenant_a).exists()
        assert RequisitionTemplateLine.objects.count() == 0


# ------------------------------------------------------------------ privilege gates / authn


class TestPrivilegeGates:
    def test_reqmgmt_member_cannot_decide_amendments(
            self, member_client, requisition_approved_a, amendment_pending_a):
        before_date = requisition_approved_a.required_by
        approve = reverse("procurement:amendment_approve", args=[amendment_pending_a.pk])
        reject = reverse("procurement:amendment_reject", args=[amendment_pending_a.pk])
        assert member_client.post(approve, {"decision_note": "wave it through"}).status_code \
            == 403
        assert member_client.post(reject, {"decision_note": "veto"}).status_code == 403
        amendment_pending_a.refresh_from_db()
        assert amendment_pending_a.status == "pending"
        assert amendment_pending_a.decided_at is None
        assert amendment_pending_a.applied_at is None
        requisition_approved_a.refresh_from_db()
        assert requisition_approved_a.required_by == before_date     # spine untouched

    def test_reqmgmt_member_template_surface_as_built(
            self, member_client, tenant_a, member_user, template_with_lines_a):
        """As-built privilege surface around templates: APPLY is open to any member BY DESIGN
        (the draft is always raised under the SIGNED-IN user); DELETE currently carries no
        admin gate - pinned here so any change to that posture updates this test."""
        before = PurchaseRequisition.objects.filter(tenant=tenant_a).count()
        resp = member_client.post(reverse("procurement:template_apply",
                                          args=[template_with_lines_a.pk]))
        assert resp.status_code == 302
        pr = PurchaseRequisition.objects.filter(tenant=tenant_a).latest("id")
        assert PurchaseRequisition.objects.filter(tenant=tenant_a).count() == before + 1
        assert pr.requester_id == member_user.pk          # session user, never choosable
        assert pr.status == "draft"

        del_resp = member_client.post(reverse("procurement:template_delete",
                                              args=[template_with_lines_a.pk]))
        assert del_resp.status_code == 302
        assert not RequisitionTemplate.objects.filter(
            pk=template_with_lines_a.pk).exists()

    def test_reqmgmt_anonymous_get_redirects_to_login_on_every_reqmgmt_url(
            self, db, requisition_pending_a, template_with_lines_a, amendment_pending_a):
        paths = [
            reverse("procurement:req_list"),
            reverse("procurement:req_detail", args=[requisition_pending_a.pk]),
            reverse("procurement:req_amendment_create", args=[requisition_pending_a.pk]),
            reverse("procurement:template_list"),
            reverse("procurement:template_create"),
            reverse("procurement:template_detail", args=[template_with_lines_a.pk]),
            reverse("procurement:template_edit", args=[template_with_lines_a.pk]),
            reverse("procurement:template_delete", args=[template_with_lines_a.pk]),
            reverse("procurement:template_apply", args=[template_with_lines_a.pk]),
            reverse("procurement:amendment_list"),
            reverse("procurement:amendment_detail", args=[amendment_pending_a.pk]),
            reverse("procurement:amendment_approve", args=[amendment_pending_a.pk]),
            reverse("procurement:amendment_reject", args=[amendment_pending_a.pk]),
        ]
        anon = Client()
        for path in paths:
            resp = anon.get(path)
            assert resp.status_code == 302, path
            assert "/login/" in resp["Location"], path


# ------------------------------------------------------------------ method discipline


class TestMethodDiscipline:
    def test_reqmgmt_state_changing_verbs_reject_get_with_405(
            self, client_a, template_with_lines_a, amendment_pending_a):
        verbs = [
            ("procurement:template_delete", template_with_lines_a.pk),
            ("procurement:template_apply", template_with_lines_a.pk),
            ("procurement:amendment_approve", amendment_pending_a.pk),
            ("procurement:amendment_reject", amendment_pending_a.pk),
        ]
        for name, pk in verbs:
            resp = client_a.get(reverse(name, args=[pk]))
            assert resp.status_code == 405, name
        assert RequisitionTemplate.objects.filter(
            pk=template_with_lines_a.pk).exists()
        amendment_pending_a.refresh_from_db()
        assert amendment_pending_a.status == "pending"


# ------------------------------------------------------------------ status-machine abuse


class TestStatusMachineAbuse:
    def test_reqmgmt_no_amendment_against_draft_requisition(
            self, client_a, tenant_a, admin_user):
        draft = _spine_pr(tenant_a, admin_user, "Still a draft")
        data = {"amendment_type": "cancel", "reason": "Cancel me anyway"}
        data.update(mgmt(0))
        resp = client_a.post(reverse("procurement:req_amendment_create",
                                     args=[draft.pk]), data, follow=True)
        assert resp.status_code == 200
        assert resp.redirect_chain[-1][0] == reverse("procurement:req_detail",
                                                     args=[draft.pk])
        assert "cannot be amended" in resp.content.decode()
        assert not RequisitionAmendment.objects.filter(requisition=draft).exists()

    def test_reqmgmt_no_amendment_against_converted_requisition(
            self, client_a, tenant_a, admin_user):
        converted = _spine_pr(tenant_a, admin_user, "Already a PO", status="converted")
        data = {"amendment_type": "cancel", "reason": "Close me anyway"}
        data.update(mgmt(0))
        resp = client_a.post(reverse("procurement:req_amendment_create",
                                     args=[converted.pk]), data, follow=True)
        assert resp.status_code == 200
        assert resp.redirect_chain[-1][0] == reverse("procurement:req_detail",
                                                     args=[converted.pk])
        assert "cannot be amended" in resp.content.decode()
        assert not RequisitionAmendment.objects.filter(requisition=converted).exists()

    def test_reqmgmt_double_approve_does_not_reapply(
            self, client_a, requisition_approved_a, amendment_pending_a):
        url = reverse("procurement:amendment_approve", args=[amendment_pending_a.pk])
        first = client_a.post(url, {"decision_note": "Vendor confirmed"})
        assert first.status_code == 302
        amendment_pending_a.refresh_from_db()
        decided_once = amendment_pending_a.decided_at
        applied_once = amendment_pending_a.applied_at
        requisition_approved_a.refresh_from_db()
        date_after_first = requisition_approved_a.required_by

        second = client_a.post(url, {}, follow=True)
        assert second.status_code == 200
        assert second.redirect_chain[-1][0] == reverse("procurement:amendment_detail",
                                                       args=[amendment_pending_a.pk])
        assert "already been decided" in second.content.decode()
        amendment_pending_a.refresh_from_db()
        requisition_approved_a.refresh_from_db()
        assert amendment_pending_a.status == "approved"
        assert amendment_pending_a.decided_at == decided_once
        assert amendment_pending_a.applied_at == applied_once
        assert requisition_approved_a.required_by == date_after_first
        assert requisition_approved_a.lines.count() == 2


# ------------------------------------------------------------------ output escaping


class TestOutputEscaping:
    def test_reqmgmt_template_name_is_html_escaped_in_list(self, client_a, tenant_a):
        RequisitionTemplate.objects.create(tenant=tenant_a,
                                           name="<script>alert(1)</script>")
        resp = client_a.get(reverse("procurement:template_list"))
        assert resp.status_code == 200
        body = resp.content.decode()
        assert "&lt;script&gt;" in body
        assert "<script>alert" not in body


# ------------------------------------------------------------------ formset bound caps


class TestFormsetCaps:
    def test_reqmgmt_crafted_total_forms_never_explodes_rows(
            self, client_a, tenant_a):
        """A management form declaring 60 rows (> max_num=50) must neither crash nor
        materialise phantom rows: only genuinely-filled rows may ever land."""
        data = {"name": "Cap probe blueprint", "description": "", "org_unit": "",
                "currency": "", "default_lead_days": "", "justification": ""}
        data.update(mgmt(60))
        data.update({
            "lines-0-item_description": "The only real row",
            "lines-0-sku_hint": "",
            "lines-0-uom_hint": "",
            "lines-0-quantity": "2",
            "lines-0-estimated_unit_price": "3.50",
            "lines-0-gl_account": "",
        })
        resp = client_a.post(reverse("procurement:template_create"), data)
        assert resp.status_code in (200, 302)                # never a 500
        assert RequisitionTemplate.objects.filter(tenant=tenant_a).count() <= 1
        assert RequisitionTemplateLine.objects.filter(
            template__tenant=tenant_a).count() <= 1


# ------------------------------------------------------------------ duplicate engine isolation


class TestDuplicateEngineIsolation:
    def test_reqmgmt_duplicate_engine_never_leaks_foreign_tenant_rows(
            self, tenant_a, tenant_b, admin_user, admin_b, requisition_approved_a):
        twin_a = _spine_pr(tenant_a, admin_user, "Quarterly office supplies")
        twin_b = _spine_pr(tenant_b, admin_b, "Quarterly office supplies")

        found = find_duplicate_requisitions(requisition_approved_a)
        pks = [d["requisition"].pk for d in found]
        assert twin_a.pk in pks                              # engine demonstrably works...
        assert twin_b.pk not in pks                          # ...but stays in-workspace
        assert all(d["requisition"].tenant_id == tenant_a.pk for d in found)

        foreign_view = find_duplicate_requisitions(twin_b)
        assert [d["requisition"].pk for d in foreign_view] == [] or \
            all(d["requisition"].tenant_id == tenant_b.pk for d in foreign_view)
