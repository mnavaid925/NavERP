"""Tests for HRM 3.26 Request Management (Self-Service) views: ``DocumentRequest``/``IdCardRequest``/
``AssetRequest`` CRUD (create is direct self-service — no admin gate — mirroring EmergencyContact;
edit/delete/submit/cancel stay ownership-gated via ``_can_manage_own_child``; approve/reject/fulfill/
issue are ``@tenant_admin_required``), the draft->pending->approved/rejected/cancelled(+fulfilled/
issued) lifecycle status-guard matrix, the self-approval guard (blocks an admin who is the requesting
employee on approve/reject — but not a different admin), the ``assetrequest_fulfill`` action's
one-linked-``AssetAllocation`` side effect (``program=None``, ``status='issued'``), and the
``my_requests`` self-service hub. Mirrors test_selfservice_views.py conventions; client_a is the
tenant admin."""
import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _client_for(party, tenant, *, email, username, is_admin=False):
    """Build a logged-in Client for a User linked to the given Party (mirrors the self-service
    trio's convention)."""
    from apps.accounts.models import User
    user = User.objects.create_user(
        email=email, username=username, password="TestPass123!",
        tenant=tenant, is_tenant_admin=is_admin,
    )
    user.party = party
    user.save(update_fields=["party"])
    c = Client()
    c.force_login(user)
    return c


def _admin_linked_to(party, tenant, *, email, username):
    """A tenant-admin User linked to a specific Party (for self-approval-guard tests)."""
    return _client_for(party, tenant, email=email, username=username, is_admin=True)


def _document_request_post_data(**overrides):
    data = {
        "document_type": "experience_letter", "purpose": "Needed for a home-loan application.",
        "addressed_to": "", "copies": "1", "delivery_method": "soft_copy", "needed_by": "",
    }
    data.update(overrides)
    return data


def _idcard_request_post_data(**overrides):
    data = {
        "request_type": "new", "reason_type": "first_issue",
        "reason": "First-time badge issuance.", "delivery_location": "",
    }
    data.update(overrides)
    return data


def _asset_request_post_data(**overrides):
    data = {
        "asset_category": "laptop", "asset_name": "Dell XPS 13",
        "justification": "Current laptop is out of warranty.", "priority": "normal", "needed_by": "",
    }
    data.update(overrides)
    return data


# ================================================================ DocumentRequest — list
class TestDocumentRequestListView:
    def test_list_200(self, client_a, document_request_a):
        resp = client_a.get(reverse("hrm:documentrequest_list"))
        assert resp.status_code == 200

    def test_list_shows_own_for_self_scoped_employee(self, tenant_a, employee_a, document_request_a):
        c = _client_for(employee_a.party, tenant_a, email="dr_list@acme.com", username="dr_list_acme")
        resp = c.get(reverse("hrm:documentrequest_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert document_request_a.pk in pks

    def test_list_filter_by_status(self, client_a, document_request_a):
        resp = client_a.get(reverse("hrm:documentrequest_list"), {"status": "draft"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert document_request_a.pk in pks

    def test_list_filter_by_document_type(self, client_a, document_request_a):
        resp = client_a.get(reverse("hrm:documentrequest_list"), {"document_type": "experience_letter"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert document_request_a.pk in pks

    def test_list_search_by_purpose(self, client_a, document_request_a):
        resp = client_a.get(reverse("hrm:documentrequest_list"), {"q": "home-loan"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert document_request_a.pk in pks

    def test_list_has_choices_context_for_admin(self, client_a, document_request_a):
        resp = client_a.get(reverse("hrm:documentrequest_list"))
        assert resp.context["is_admin"] is True
        assert "status_choices" in resp.context
        assert "document_type_choices" in resp.context
        assert "employees" in resp.context

    def test_bad_page_does_not_500(self, client_a, document_request_a):
        resp = client_a.get(reverse("hrm:documentrequest_list"), {"page": "999"})
        assert resp.status_code == 200

    def test_list_query_count_bounded(self, client_a, document_request_a, django_assert_max_num_queries):
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:documentrequest_list"))


# ================================================================ DocumentRequest — create (direct self-service)
class TestDocumentRequestCreateView:
    def test_get_200_for_self_scoped_employee(self, tenant_a, employee_a):
        c = _client_for(employee_a.party, tenant_a, email="dr_self@acme.com", username="dr_self_acme")
        resp = c.get(reverse("hrm:documentrequest_create"))
        assert resp.status_code == 200

    def test_post_creates_draft_for_self(self, tenant_a, employee_a):
        from apps.hrm.models import DocumentRequest
        c = _client_for(employee_a.party, tenant_a, email="dr_self2@acme.com", username="dr_self2_acme")
        resp = c.post(reverse("hrm:documentrequest_create"), _document_request_post_data())
        assert resp.status_code == 302
        dr = DocumentRequest.objects.filter(tenant=tenant_a, employee=employee_a).first()
        assert dr is not None
        assert dr.status == "draft"
        assert dr.tenant_id == tenant_a.pk

    def test_get_200_for_admin_with_employee_param(self, client_a, employee_a):
        resp = client_a.get(reverse("hrm:documentrequest_create") + f"?employee={employee_a.pk}")
        assert resp.status_code == 200

    def test_post_creates_for_admin_targeting_employee(self, client_a, tenant_a, employee_a):
        from apps.hrm.models import DocumentRequest
        resp = client_a.post(
            reverse("hrm:documentrequest_create"),
            _document_request_post_data(employee_pk=str(employee_a.pk)))
        assert resp.status_code == 302
        assert DocumentRequest.objects.filter(tenant=tenant_a, employee=employee_a).exists()

    def test_admin_without_employee_target_redirects_with_no_create(self, client_a, tenant_a):
        from apps.hrm.models import DocumentRequest
        resp = client_a.post(reverse("hrm:documentrequest_create"), _document_request_post_data())
        assert resp.status_code == 302
        assert not DocumentRequest.objects.filter(tenant=tenant_a).exists()

    def test_form_has_no_employee_tenant_status_number_fields(self, tenant_a, employee_a):
        c = _client_for(employee_a.party, tenant_a, email="dr_form@acme.com", username="dr_form_acme")
        resp = c.get(reverse("hrm:documentrequest_create"))
        fields = resp.context["form"].fields
        for excluded in ("employee", "tenant", "status", "number"):
            assert excluded not in fields


# ================================================================ DocumentRequest — detail/edit/delete
class TestDocumentRequestDetailEditDelete:
    def test_detail_200_for_owner(self, tenant_a, employee_a, document_request_a):
        c = _client_for(employee_a.party, tenant_a, email="dr_det@acme.com", username="dr_det_acme")
        resp = c.get(reverse("hrm:documentrequest_detail", args=[document_request_a.pk]))
        assert resp.status_code == 200

    def test_detail_200_for_admin(self, client_a, document_request_a):
        resp = client_a.get(reverse("hrm:documentrequest_detail", args=[document_request_a.pk]))
        assert resp.status_code == 200

    def test_edit_get_200_for_owner_when_open(self, tenant_a, employee_a, document_request_a):
        c = _client_for(employee_a.party, tenant_a, email="dr_edit@acme.com", username="dr_edit_acme")
        resp = c.get(reverse("hrm:documentrequest_edit", args=[document_request_a.pk]))
        assert resp.status_code == 200

    def test_edit_blocked_when_not_open(self, tenant_a, employee_a, document_request_a):
        document_request_a.status = "approved"
        document_request_a.save(update_fields=["status"])
        c = _client_for(employee_a.party, tenant_a, email="dr_edit2@acme.com", username="dr_edit2_acme")
        resp = c.get(reverse("hrm:documentrequest_edit", args=[document_request_a.pk]))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("hrm:documentrequest_detail", args=[document_request_a.pk])

    def test_edit_post_updates_when_open(self, tenant_a, employee_a, document_request_a):
        c = _client_for(employee_a.party, tenant_a, email="dr_edit3@acme.com", username="dr_edit3_acme")
        resp = c.post(
            reverse("hrm:documentrequest_edit", args=[document_request_a.pk]),
            _document_request_post_data(addressed_to="HR Manager"))
        assert resp.status_code == 302
        document_request_a.refresh_from_db()
        assert document_request_a.addressed_to == "HR Manager"

    def test_delete_post_removes_when_open(self, tenant_a, employee_a, document_request_a):
        from apps.hrm.models import DocumentRequest
        c = _client_for(employee_a.party, tenant_a, email="dr_del@acme.com", username="dr_del_acme")
        pk = document_request_a.pk
        resp = c.post(reverse("hrm:documentrequest_delete", args=[pk]))
        assert resp.status_code == 302
        assert not DocumentRequest.objects.filter(pk=pk).exists()

    def test_delete_blocked_when_not_open(self, tenant_a, employee_a, document_request_a):
        from apps.hrm.models import DocumentRequest
        document_request_a.status = "cancelled"
        document_request_a.save(update_fields=["status"])
        c = _client_for(employee_a.party, tenant_a, email="dr_del2@acme.com", username="dr_del2_acme")
        resp = c.post(reverse("hrm:documentrequest_delete", args=[document_request_a.pk]))
        assert resp.status_code == 302
        assert DocumentRequest.objects.filter(pk=document_request_a.pk).exists()

    def test_delete_get_not_allowed(self, client_a, document_request_a):
        resp = client_a.get(reverse("hrm:documentrequest_delete", args=[document_request_a.pk]))
        assert resp.status_code == 405


# ================================================================ DocumentRequest — workflow
class TestDocumentRequestWorkflow:
    def test_submit_draft_to_pending_by_owner(self, tenant_a, employee_a, document_request_a):
        c = _client_for(employee_a.party, tenant_a, email="dr_sub@acme.com", username="dr_sub_acme")
        resp = c.post(reverse("hrm:documentrequest_submit", args=[document_request_a.pk]))
        assert resp.status_code == 302
        document_request_a.refresh_from_db()
        assert document_request_a.status == "pending"

    def test_submit_blocked_when_not_draft(self, client_a, document_request_a):
        document_request_a.status = "pending"
        document_request_a.save(update_fields=["status"])
        client_a.post(reverse("hrm:documentrequest_submit", args=[document_request_a.pk]))
        document_request_a.refresh_from_db()
        assert document_request_a.status == "pending"  # unchanged, no error

    def test_submit_get_not_allowed(self, client_a, document_request_a):
        resp = client_a.get(reverse("hrm:documentrequest_submit", args=[document_request_a.pk]))
        assert resp.status_code == 405

    def test_cancel_by_owner_sets_cancelled(self, tenant_a, employee_a, document_request_a):
        c = _client_for(employee_a.party, tenant_a, email="dr_can@acme.com", username="dr_can_acme")
        resp = c.post(reverse("hrm:documentrequest_cancel", args=[document_request_a.pk]))
        assert resp.status_code == 302
        document_request_a.refresh_from_db()
        assert document_request_a.status == "cancelled"

    def test_cancel_blocked_when_not_open(self, client_a, document_request_a):
        document_request_a.status = "fulfilled"
        document_request_a.save(update_fields=["status"])
        client_a.post(reverse("hrm:documentrequest_cancel", args=[document_request_a.pk]))
        document_request_a.refresh_from_db()
        assert document_request_a.status == "fulfilled"  # unchanged

    def test_approve_by_admin_sets_approved(self, client_a, admin_user, document_request_a):
        document_request_a.status = "pending"
        document_request_a.save(update_fields=["status"])
        resp = client_a.post(reverse("hrm:documentrequest_approve", args=[document_request_a.pk]))
        assert resp.status_code == 302
        document_request_a.refresh_from_db()
        assert document_request_a.status == "approved"
        assert document_request_a.approver_id == admin_user.pk
        assert document_request_a.approved_at is not None

    def test_approve_403_for_non_admin(self, tenant_a, employee_a, document_request_a):
        document_request_a.status = "pending"
        document_request_a.save(update_fields=["status"])
        c = _client_for(employee_a.party, tenant_a, email="dr_appr_na@acme.com", username="dr_appr_na_acme")
        resp = c.post(reverse("hrm:documentrequest_approve", args=[document_request_a.pk]))
        assert resp.status_code == 403
        document_request_a.refresh_from_db()
        assert document_request_a.status == "pending"

    def test_approve_blocked_when_not_pending(self, client_a, document_request_a):
        client_a.post(reverse("hrm:documentrequest_approve", args=[document_request_a.pk]))  # still draft
        document_request_a.refresh_from_db()
        assert document_request_a.status == "draft"  # unchanged

    def test_approve_get_not_allowed(self, client_a, document_request_a):
        resp = client_a.get(reverse("hrm:documentrequest_approve", args=[document_request_a.pk]))
        assert resp.status_code == 405

    def test_reject_requires_non_blank_decision_note(self, client_a, document_request_a):
        document_request_a.status = "pending"
        document_request_a.save(update_fields=["status"])
        client_a.post(reverse("hrm:documentrequest_reject", args=[document_request_a.pk]), {"decision_note": ""})
        document_request_a.refresh_from_db()
        assert document_request_a.status == "pending"  # unchanged

    def test_reject_with_note_sets_rejected(self, client_a, document_request_a):
        document_request_a.status = "pending"
        document_request_a.save(update_fields=["status"])
        resp = client_a.post(
            reverse("hrm:documentrequest_reject", args=[document_request_a.pk]), {"decision_note": "Not eligible"})
        assert resp.status_code == 302
        document_request_a.refresh_from_db()
        assert document_request_a.status == "rejected"
        assert document_request_a.decision_note == "Not eligible"

    def test_reject_403_for_non_admin(self, tenant_a, employee_a, document_request_a):
        document_request_a.status = "pending"
        document_request_a.save(update_fields=["status"])
        c = _client_for(employee_a.party, tenant_a, email="dr_rej_na@acme.com", username="dr_rej_na_acme")
        resp = c.post(reverse("hrm:documentrequest_reject", args=[document_request_a.pk]), {"decision_note": "no"})
        assert resp.status_code == 403
        document_request_a.refresh_from_db()
        assert document_request_a.status == "pending"

    def test_reject_get_not_allowed(self, client_a, document_request_a):
        resp = client_a.get(reverse("hrm:documentrequest_reject", args=[document_request_a.pk]))
        assert resp.status_code == 405

    def test_fulfill_approved_to_fulfilled(self, client_a, document_request_a):
        document_request_a.status = "approved"
        document_request_a.save(update_fields=["status"])
        resp = client_a.post(reverse("hrm:documentrequest_fulfill", args=[document_request_a.pk]), {})
        assert resp.status_code == 302
        document_request_a.refresh_from_db()
        assert document_request_a.status == "fulfilled"
        assert document_request_a.fulfilled_at is not None

    def test_fulfill_blocked_when_not_approved(self, client_a, document_request_a):
        client_a.post(reverse("hrm:documentrequest_fulfill", args=[document_request_a.pk]), {})  # still draft
        document_request_a.refresh_from_db()
        assert document_request_a.status == "draft"  # unchanged

    def test_fulfill_403_for_non_admin(self, tenant_a, employee_a, document_request_a):
        document_request_a.status = "approved"
        document_request_a.save(update_fields=["status"])
        c = _client_for(employee_a.party, tenant_a, email="dr_ful_na@acme.com", username="dr_ful_na_acme")
        resp = c.post(reverse("hrm:documentrequest_fulfill", args=[document_request_a.pk]), {})
        assert resp.status_code == 403
        document_request_a.refresh_from_db()
        assert document_request_a.status == "approved"

    def test_fulfill_get_not_allowed(self, client_a, document_request_a):
        resp = client_a.get(reverse("hrm:documentrequest_fulfill", args=[document_request_a.pk]))
        assert resp.status_code == 405


class TestDocumentRequestSelfApprovalGuard:
    def test_approve_blocked_when_admin_is_subject_employee(self, tenant_a, employee_a, document_request_a):
        document_request_a.status = "pending"
        document_request_a.save(update_fields=["status"])
        c = _admin_linked_to(employee_a.party, tenant_a, email="dr_admin_emp@acme.com", username="dr_admin_emp_acme")
        resp = c.post(reverse("hrm:documentrequest_approve", args=[document_request_a.pk]))
        assert resp.status_code == 302
        document_request_a.refresh_from_db()
        assert document_request_a.status == "pending"

    def test_reject_blocked_when_admin_is_subject_employee(self, tenant_a, employee_a, document_request_a):
        document_request_a.status = "pending"
        document_request_a.save(update_fields=["status"])
        c = _admin_linked_to(employee_a.party, tenant_a, email="dr_admin_emp2@acme.com", username="dr_admin_emp2_acme")
        resp = c.post(reverse("hrm:documentrequest_reject", args=[document_request_a.pk]), {"decision_note": "no"})
        assert resp.status_code == 302
        document_request_a.refresh_from_db()
        assert document_request_a.status == "pending"

    def test_approve_allowed_by_a_different_admin(self, client_a, document_request_a):
        document_request_a.status = "pending"
        document_request_a.save(update_fields=["status"])
        resp = client_a.post(reverse("hrm:documentrequest_approve", args=[document_request_a.pk]))
        assert resp.status_code == 302
        document_request_a.refresh_from_db()
        assert document_request_a.status == "approved"


# ================================================================ IdCardRequest — list/create
class TestIdCardRequestListView:
    def test_list_200(self, client_a, idcard_request_a):
        resp = client_a.get(reverse("hrm:idcardrequest_list"))
        assert resp.status_code == 200

    def test_list_shows_own_for_self_scoped_employee(self, tenant_a, employee_a, idcard_request_a):
        c = _client_for(employee_a.party, tenant_a, email="ir_list@acme.com", username="ir_list_acme")
        resp = c.get(reverse("hrm:idcardrequest_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert idcard_request_a.pk in pks

    def test_list_filter_by_status(self, client_a, idcard_request_a):
        resp = client_a.get(reverse("hrm:idcardrequest_list"), {"status": "draft"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert idcard_request_a.pk in pks

    def test_list_filter_by_request_type(self, client_a, idcard_request_a):
        resp = client_a.get(reverse("hrm:idcardrequest_list"), {"request_type": "new"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert idcard_request_a.pk in pks

    def test_list_filter_by_reason_type(self, client_a, idcard_request_a):
        resp = client_a.get(reverse("hrm:idcardrequest_list"), {"reason_type": "first_issue"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert idcard_request_a.pk in pks

    def test_list_search_by_reason(self, client_a, idcard_request_a):
        resp = client_a.get(reverse("hrm:idcardrequest_list"), {"q": "badge"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert idcard_request_a.pk in pks

    def test_list_has_choices_context(self, client_a, idcard_request_a):
        resp = client_a.get(reverse("hrm:idcardrequest_list"))
        assert "status_choices" in resp.context
        assert "request_type_choices" in resp.context
        assert "reason_type_choices" in resp.context
        assert "employees" in resp.context

    def test_list_query_count_bounded(self, client_a, idcard_request_a, django_assert_max_num_queries):
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:idcardrequest_list"))


class TestIdCardRequestCreateView:
    def test_get_200_for_self_scoped_employee(self, tenant_a, employee_a):
        c = _client_for(employee_a.party, tenant_a, email="ir_self@acme.com", username="ir_self_acme")
        resp = c.get(reverse("hrm:idcardrequest_create"))
        assert resp.status_code == 200

    def test_post_creates_draft_for_self(self, tenant_a, employee_a):
        from apps.hrm.models import IdCardRequest
        c = _client_for(employee_a.party, tenant_a, email="ir_self2@acme.com", username="ir_self2_acme")
        resp = c.post(reverse("hrm:idcardrequest_create"), _idcard_request_post_data())
        assert resp.status_code == 302
        ir = IdCardRequest.objects.filter(tenant=tenant_a, employee=employee_a).first()
        assert ir is not None
        assert ir.status == "draft"

    def test_post_creates_for_admin_targeting_employee(self, client_a, tenant_a, employee_a):
        from apps.hrm.models import IdCardRequest
        resp = client_a.post(
            reverse("hrm:idcardrequest_create"),
            _idcard_request_post_data(employee_pk=str(employee_a.pk)))
        assert resp.status_code == 302
        assert IdCardRequest.objects.filter(tenant=tenant_a, employee=employee_a).exists()

    def test_form_has_no_employee_tenant_status_number_fields(self, tenant_a, employee_a):
        c = _client_for(employee_a.party, tenant_a, email="ir_form@acme.com", username="ir_form_acme")
        resp = c.get(reverse("hrm:idcardrequest_create"))
        fields = resp.context["form"].fields
        for excluded in ("employee", "tenant", "status", "number", "card_number"):
            assert excluded not in fields


# ================================================================ IdCardRequest — detail/edit/delete
class TestIdCardRequestDetailEditDelete:
    def test_detail_200_for_owner(self, tenant_a, employee_a, idcard_request_a):
        c = _client_for(employee_a.party, tenant_a, email="ir_det@acme.com", username="ir_det_acme")
        resp = c.get(reverse("hrm:idcardrequest_detail", args=[idcard_request_a.pk]))
        assert resp.status_code == 200

    def test_detail_200_for_admin(self, client_a, idcard_request_a):
        resp = client_a.get(reverse("hrm:idcardrequest_detail", args=[idcard_request_a.pk]))
        assert resp.status_code == 200

    def test_edit_blocked_when_not_open(self, tenant_a, employee_a, idcard_request_a):
        idcard_request_a.status = "issued"
        idcard_request_a.save(update_fields=["status"])
        c = _client_for(employee_a.party, tenant_a, email="ir_edit@acme.com", username="ir_edit_acme")
        resp = c.get(reverse("hrm:idcardrequest_edit", args=[idcard_request_a.pk]))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("hrm:idcardrequest_detail", args=[idcard_request_a.pk])

    def test_edit_post_updates_when_open(self, tenant_a, employee_a, idcard_request_a):
        c = _client_for(employee_a.party, tenant_a, email="ir_edit2@acme.com", username="ir_edit2_acme")
        resp = c.post(
            reverse("hrm:idcardrequest_edit", args=[idcard_request_a.pk]),
            _idcard_request_post_data(delivery_location="Front desk"))
        assert resp.status_code == 302
        idcard_request_a.refresh_from_db()
        assert idcard_request_a.delivery_location == "Front desk"

    def test_delete_post_removes_when_open(self, tenant_a, employee_a, idcard_request_a):
        from apps.hrm.models import IdCardRequest
        c = _client_for(employee_a.party, tenant_a, email="ir_del@acme.com", username="ir_del_acme")
        pk = idcard_request_a.pk
        resp = c.post(reverse("hrm:idcardrequest_delete", args=[pk]))
        assert resp.status_code == 302
        assert not IdCardRequest.objects.filter(pk=pk).exists()

    def test_delete_blocked_when_not_open(self, tenant_a, employee_a, idcard_request_a):
        from apps.hrm.models import IdCardRequest
        idcard_request_a.status = "rejected"
        idcard_request_a.save(update_fields=["status"])
        c = _client_for(employee_a.party, tenant_a, email="ir_del2@acme.com", username="ir_del2_acme")
        resp = c.post(reverse("hrm:idcardrequest_delete", args=[idcard_request_a.pk]))
        assert resp.status_code == 302
        assert IdCardRequest.objects.filter(pk=idcard_request_a.pk).exists()

    def test_delete_get_not_allowed(self, client_a, idcard_request_a):
        resp = client_a.get(reverse("hrm:idcardrequest_delete", args=[idcard_request_a.pk]))
        assert resp.status_code == 405


# ================================================================ IdCardRequest — workflow (+ issue)
class TestIdCardRequestWorkflow:
    def test_submit_draft_to_pending_by_owner(self, tenant_a, employee_a, idcard_request_a):
        c = _client_for(employee_a.party, tenant_a, email="ir_sub@acme.com", username="ir_sub_acme")
        resp = c.post(reverse("hrm:idcardrequest_submit", args=[idcard_request_a.pk]))
        assert resp.status_code == 302
        idcard_request_a.refresh_from_db()
        assert idcard_request_a.status == "pending"

    def test_cancel_by_owner_sets_cancelled(self, tenant_a, employee_a, idcard_request_a):
        c = _client_for(employee_a.party, tenant_a, email="ir_can@acme.com", username="ir_can_acme")
        resp = c.post(reverse("hrm:idcardrequest_cancel", args=[idcard_request_a.pk]))
        assert resp.status_code == 302
        idcard_request_a.refresh_from_db()
        assert idcard_request_a.status == "cancelled"

    def test_approve_by_admin_sets_approved(self, client_a, admin_user, idcard_request_a):
        idcard_request_a.status = "pending"
        idcard_request_a.save(update_fields=["status"])
        resp = client_a.post(reverse("hrm:idcardrequest_approve", args=[idcard_request_a.pk]))
        assert resp.status_code == 302
        idcard_request_a.refresh_from_db()
        assert idcard_request_a.status == "approved"
        assert idcard_request_a.approver_id == admin_user.pk

    def test_approve_403_for_non_admin(self, tenant_a, employee_a, idcard_request_a):
        idcard_request_a.status = "pending"
        idcard_request_a.save(update_fields=["status"])
        c = _client_for(employee_a.party, tenant_a, email="ir_appr_na@acme.com", username="ir_appr_na_acme")
        resp = c.post(reverse("hrm:idcardrequest_approve", args=[idcard_request_a.pk]))
        assert resp.status_code == 403
        idcard_request_a.refresh_from_db()
        assert idcard_request_a.status == "pending"

    def test_reject_requires_non_blank_decision_note(self, client_a, idcard_request_a):
        idcard_request_a.status = "pending"
        idcard_request_a.save(update_fields=["status"])
        client_a.post(reverse("hrm:idcardrequest_reject", args=[idcard_request_a.pk]), {"decision_note": ""})
        idcard_request_a.refresh_from_db()
        assert idcard_request_a.status == "pending"  # unchanged

    def test_reject_with_note_sets_rejected(self, client_a, idcard_request_a):
        idcard_request_a.status = "pending"
        idcard_request_a.save(update_fields=["status"])
        resp = client_a.post(
            reverse("hrm:idcardrequest_reject", args=[idcard_request_a.pk]), {"decision_note": "Not eligible"})
        assert resp.status_code == 302
        idcard_request_a.refresh_from_db()
        assert idcard_request_a.status == "rejected"

    def test_reject_403_for_non_admin(self, tenant_a, employee_a, idcard_request_a):
        idcard_request_a.status = "pending"
        idcard_request_a.save(update_fields=["status"])
        c = _client_for(employee_a.party, tenant_a, email="ir_rej_na@acme.com", username="ir_rej_na_acme")
        resp = c.post(reverse("hrm:idcardrequest_reject", args=[idcard_request_a.pk]), {"decision_note": "no"})
        assert resp.status_code == 403
        idcard_request_a.refresh_from_db()
        assert idcard_request_a.status == "pending"

    def test_issue_requires_card_number(self, client_a, idcard_request_a):
        idcard_request_a.status = "approved"
        idcard_request_a.save(update_fields=["status"])
        resp = client_a.post(reverse("hrm:idcardrequest_issue", args=[idcard_request_a.pk]), {"card_number": ""})
        assert resp.status_code == 302
        idcard_request_a.refresh_from_db()
        assert idcard_request_a.status == "approved"  # unchanged — no card number
        assert idcard_request_a.card_number == ""

    def test_issue_with_card_number_sets_issued_and_stamps(self, client_a, idcard_request_a):
        idcard_request_a.status = "approved"
        idcard_request_a.save(update_fields=["status"])
        resp = client_a.post(
            reverse("hrm:idcardrequest_issue", args=[idcard_request_a.pk]), {"card_number": "BADGE-4471"})
        assert resp.status_code == 302
        idcard_request_a.refresh_from_db()
        assert idcard_request_a.status == "issued"
        assert idcard_request_a.card_number == "BADGE-4471"
        assert idcard_request_a.issued_at is not None

    def test_issue_blocked_when_not_approved(self, client_a, idcard_request_a):
        client_a.post(reverse("hrm:idcardrequest_issue", args=[idcard_request_a.pk]), {"card_number": "X1"})
        idcard_request_a.refresh_from_db()
        assert idcard_request_a.status == "draft"  # unchanged
        assert idcard_request_a.card_number == ""

    def test_issue_403_for_non_admin(self, tenant_a, employee_a, idcard_request_a):
        idcard_request_a.status = "approved"
        idcard_request_a.save(update_fields=["status"])
        c = _client_for(employee_a.party, tenant_a, email="ir_iss_na@acme.com", username="ir_iss_na_acme")
        resp = c.post(reverse("hrm:idcardrequest_issue", args=[idcard_request_a.pk]), {"card_number": "X1"})
        assert resp.status_code == 403
        idcard_request_a.refresh_from_db()
        assert idcard_request_a.status == "approved"
        assert idcard_request_a.card_number == ""

    def test_issue_get_not_allowed(self, client_a, idcard_request_a):
        resp = client_a.get(reverse("hrm:idcardrequest_issue", args=[idcard_request_a.pk]))
        assert resp.status_code == 405


class TestIdCardRequestSelfApprovalGuard:
    def test_approve_blocked_when_admin_is_subject_employee(self, tenant_a, employee_a, idcard_request_a):
        idcard_request_a.status = "pending"
        idcard_request_a.save(update_fields=["status"])
        c = _admin_linked_to(employee_a.party, tenant_a, email="ir_admin_emp@acme.com", username="ir_admin_emp_acme")
        resp = c.post(reverse("hrm:idcardrequest_approve", args=[idcard_request_a.pk]))
        assert resp.status_code == 302
        idcard_request_a.refresh_from_db()
        assert idcard_request_a.status == "pending"

    def test_reject_blocked_when_admin_is_subject_employee(self, tenant_a, employee_a, idcard_request_a):
        idcard_request_a.status = "pending"
        idcard_request_a.save(update_fields=["status"])
        c = _admin_linked_to(employee_a.party, tenant_a, email="ir_admin_emp2@acme.com", username="ir_admin_emp2_acme")
        resp = c.post(reverse("hrm:idcardrequest_reject", args=[idcard_request_a.pk]), {"decision_note": "no"})
        assert resp.status_code == 302
        idcard_request_a.refresh_from_db()
        assert idcard_request_a.status == "pending"

    def test_approve_allowed_by_a_different_admin(self, client_a, idcard_request_a):
        idcard_request_a.status = "pending"
        idcard_request_a.save(update_fields=["status"])
        resp = client_a.post(reverse("hrm:idcardrequest_approve", args=[idcard_request_a.pk]))
        assert resp.status_code == 302
        idcard_request_a.refresh_from_db()
        assert idcard_request_a.status == "approved"


# ================================================================ AssetRequest — list/create
class TestAssetRequestListView:
    def test_list_200(self, client_a, asset_request_a):
        resp = client_a.get(reverse("hrm:assetrequest_list"))
        assert resp.status_code == 200

    def test_list_shows_own_for_self_scoped_employee(self, tenant_a, employee_a, asset_request_a):
        c = _client_for(employee_a.party, tenant_a, email="ar_list@acme.com", username="ar_list_acme")
        resp = c.get(reverse("hrm:assetrequest_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert asset_request_a.pk in pks

    def test_list_filter_by_status(self, client_a, asset_request_a):
        resp = client_a.get(reverse("hrm:assetrequest_list"), {"status": "draft"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert asset_request_a.pk in pks

    def test_list_filter_by_asset_category(self, client_a, asset_request_a):
        resp = client_a.get(reverse("hrm:assetrequest_list"), {"asset_category": "laptop"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert asset_request_a.pk in pks

    def test_list_filter_by_priority(self, client_a, asset_request_a):
        resp = client_a.get(reverse("hrm:assetrequest_list"), {"priority": "normal"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert asset_request_a.pk in pks

    def test_list_search_by_asset_name(self, client_a, asset_request_a):
        resp = client_a.get(reverse("hrm:assetrequest_list"), {"q": "Dell XPS"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert asset_request_a.pk in pks

    def test_list_has_choices_context(self, client_a, asset_request_a):
        resp = client_a.get(reverse("hrm:assetrequest_list"))
        assert "status_choices" in resp.context
        assert "asset_category_choices" in resp.context
        assert "priority_choices" in resp.context
        assert "employees" in resp.context

    def test_list_query_count_bounded(self, client_a, asset_request_a, django_assert_max_num_queries):
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:assetrequest_list"))


class TestAssetRequestCreateView:
    def test_get_200_for_self_scoped_employee(self, tenant_a, employee_a):
        c = _client_for(employee_a.party, tenant_a, email="ar_self@acme.com", username="ar_self_acme")
        resp = c.get(reverse("hrm:assetrequest_create"))
        assert resp.status_code == 200

    def test_post_creates_draft_for_self(self, tenant_a, employee_a):
        from apps.hrm.models import AssetRequest
        c = _client_for(employee_a.party, tenant_a, email="ar_self2@acme.com", username="ar_self2_acme")
        resp = c.post(reverse("hrm:assetrequest_create"), _asset_request_post_data())
        assert resp.status_code == 302
        ar = AssetRequest.objects.filter(tenant=tenant_a, employee=employee_a).first()
        assert ar is not None
        assert ar.status == "draft"

    def test_post_creates_for_admin_targeting_employee(self, client_a, tenant_a, employee_a):
        from apps.hrm.models import AssetRequest
        resp = client_a.post(
            reverse("hrm:assetrequest_create"),
            _asset_request_post_data(employee_pk=str(employee_a.pk)))
        assert resp.status_code == 302
        assert AssetRequest.objects.filter(tenant=tenant_a, employee=employee_a).exists()

    def test_form_has_no_employee_tenant_status_allocation_fields(self, tenant_a, employee_a):
        c = _client_for(employee_a.party, tenant_a, email="ar_form@acme.com", username="ar_form_acme")
        resp = c.get(reverse("hrm:assetrequest_create"))
        fields = resp.context["form"].fields
        for excluded in ("employee", "tenant", "status", "number", "allocation"):
            assert excluded not in fields


# ================================================================ AssetRequest — detail/edit/delete
class TestAssetRequestDetailEditDelete:
    def test_detail_200_for_owner(self, tenant_a, employee_a, asset_request_a):
        c = _client_for(employee_a.party, tenant_a, email="ar_det@acme.com", username="ar_det_acme")
        resp = c.get(reverse("hrm:assetrequest_detail", args=[asset_request_a.pk]))
        assert resp.status_code == 200

    def test_detail_200_for_admin(self, client_a, asset_request_a):
        resp = client_a.get(reverse("hrm:assetrequest_detail", args=[asset_request_a.pk]))
        assert resp.status_code == 200

    def test_edit_blocked_when_not_open(self, tenant_a, employee_a, asset_request_a):
        asset_request_a.status = "fulfilled"
        asset_request_a.save(update_fields=["status"])
        c = _client_for(employee_a.party, tenant_a, email="ar_edit@acme.com", username="ar_edit_acme")
        resp = c.get(reverse("hrm:assetrequest_edit", args=[asset_request_a.pk]))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("hrm:assetrequest_detail", args=[asset_request_a.pk])

    def test_edit_post_updates_when_open(self, tenant_a, employee_a, asset_request_a):
        c = _client_for(employee_a.party, tenant_a, email="ar_edit2@acme.com", username="ar_edit2_acme")
        resp = c.post(
            reverse("hrm:assetrequest_edit", args=[asset_request_a.pk]),
            _asset_request_post_data(asset_name="MacBook Pro"))
        assert resp.status_code == 302
        asset_request_a.refresh_from_db()
        assert asset_request_a.asset_name == "MacBook Pro"

    def test_delete_post_removes_when_open(self, tenant_a, employee_a, asset_request_a):
        from apps.hrm.models import AssetRequest
        c = _client_for(employee_a.party, tenant_a, email="ar_del@acme.com", username="ar_del_acme")
        pk = asset_request_a.pk
        resp = c.post(reverse("hrm:assetrequest_delete", args=[pk]))
        assert resp.status_code == 302
        assert not AssetRequest.objects.filter(pk=pk).exists()

    def test_delete_blocked_when_not_open(self, tenant_a, employee_a, asset_request_a):
        from apps.hrm.models import AssetRequest
        asset_request_a.status = "rejected"
        asset_request_a.save(update_fields=["status"])
        c = _client_for(employee_a.party, tenant_a, email="ar_del2@acme.com", username="ar_del2_acme")
        resp = c.post(reverse("hrm:assetrequest_delete", args=[asset_request_a.pk]))
        assert resp.status_code == 302
        assert AssetRequest.objects.filter(pk=asset_request_a.pk).exists()

    def test_delete_get_not_allowed(self, client_a, asset_request_a):
        resp = client_a.get(reverse("hrm:assetrequest_delete", args=[asset_request_a.pk]))
        assert resp.status_code == 405


# ================================================================ AssetRequest — workflow (+ fulfill/allocation)
class TestAssetRequestWorkflow:
    def test_submit_draft_to_pending_by_owner(self, tenant_a, employee_a, asset_request_a):
        c = _client_for(employee_a.party, tenant_a, email="ar_sub@acme.com", username="ar_sub_acme")
        resp = c.post(reverse("hrm:assetrequest_submit", args=[asset_request_a.pk]))
        assert resp.status_code == 302
        asset_request_a.refresh_from_db()
        assert asset_request_a.status == "pending"

    def test_cancel_by_owner_sets_cancelled(self, tenant_a, employee_a, asset_request_a):
        c = _client_for(employee_a.party, tenant_a, email="ar_can@acme.com", username="ar_can_acme")
        resp = c.post(reverse("hrm:assetrequest_cancel", args=[asset_request_a.pk]))
        assert resp.status_code == 302
        asset_request_a.refresh_from_db()
        assert asset_request_a.status == "cancelled"

    def test_approve_by_admin_sets_approved(self, client_a, admin_user, asset_request_a):
        asset_request_a.status = "pending"
        asset_request_a.save(update_fields=["status"])
        resp = client_a.post(reverse("hrm:assetrequest_approve", args=[asset_request_a.pk]))
        assert resp.status_code == 302
        asset_request_a.refresh_from_db()
        assert asset_request_a.status == "approved"
        assert asset_request_a.approver_id == admin_user.pk

    def test_approve_403_for_non_admin(self, tenant_a, employee_a, asset_request_a):
        asset_request_a.status = "pending"
        asset_request_a.save(update_fields=["status"])
        c = _client_for(employee_a.party, tenant_a, email="ar_appr_na@acme.com", username="ar_appr_na_acme")
        resp = c.post(reverse("hrm:assetrequest_approve", args=[asset_request_a.pk]))
        assert resp.status_code == 403
        asset_request_a.refresh_from_db()
        assert asset_request_a.status == "pending"

    def test_reject_requires_non_blank_decision_note(self, client_a, asset_request_a):
        asset_request_a.status = "pending"
        asset_request_a.save(update_fields=["status"])
        client_a.post(reverse("hrm:assetrequest_reject", args=[asset_request_a.pk]), {"decision_note": ""})
        asset_request_a.refresh_from_db()
        assert asset_request_a.status == "pending"  # unchanged

    def test_reject_with_note_sets_rejected(self, client_a, asset_request_a):
        asset_request_a.status = "pending"
        asset_request_a.save(update_fields=["status"])
        resp = client_a.post(
            reverse("hrm:assetrequest_reject", args=[asset_request_a.pk]), {"decision_note": "Budget freeze"})
        assert resp.status_code == 302
        asset_request_a.refresh_from_db()
        assert asset_request_a.status == "rejected"

    def test_reject_403_for_non_admin(self, tenant_a, employee_a, asset_request_a):
        asset_request_a.status = "pending"
        asset_request_a.save(update_fields=["status"])
        c = _client_for(employee_a.party, tenant_a, email="ar_rej_na@acme.com", username="ar_rej_na_acme")
        resp = c.post(reverse("hrm:assetrequest_reject", args=[asset_request_a.pk]), {"decision_note": "no"})
        assert resp.status_code == 403
        asset_request_a.refresh_from_db()
        assert asset_request_a.status == "pending"

    def test_fulfill_approved_to_fulfilled_creates_one_linked_asset_allocation(
        self, client_a, tenant_a, employee_a, asset_request_a
    ):
        from apps.hrm.models import AssetAllocation
        asset_request_a.status = "approved"
        asset_request_a.save(update_fields=["status"])
        before = AssetAllocation.objects.filter(tenant=tenant_a, employee=employee_a).count()
        resp = client_a.post(
            reverse("hrm:assetrequest_fulfill", args=[asset_request_a.pk]),
            {"serial_number": "SN-9001", "asset_tag": "TAG-42"})
        assert resp.status_code == 302
        asset_request_a.refresh_from_db()
        assert asset_request_a.status == "fulfilled"
        assert asset_request_a.allocation_id is not None
        after = AssetAllocation.objects.filter(tenant=tenant_a, employee=employee_a).count()
        assert after == before + 1
        allocation = asset_request_a.allocation
        assert allocation.pk == asset_request_a.allocation_id
        assert allocation.tenant_id == tenant_a.pk
        assert allocation.employee_id == employee_a.pk
        assert allocation.program_id is None
        assert allocation.status == "issued"
        assert allocation.asset_name == asset_request_a.asset_name
        assert allocation.asset_category == asset_request_a.asset_category
        assert allocation.serial_number == "SN-9001"
        assert allocation.asset_tag == "TAG-42"
        assert allocation.issued_at is not None
        assert allocation.issued_by_id is not None

    def test_fulfill_blocked_when_not_approved_creates_no_allocation(self, client_a, asset_request_a):
        from apps.hrm.models import AssetAllocation
        before = AssetAllocation.objects.count()
        client_a.post(reverse("hrm:assetrequest_fulfill", args=[asset_request_a.pk]), {})  # still draft
        asset_request_a.refresh_from_db()
        assert asset_request_a.status == "draft"  # unchanged
        assert asset_request_a.allocation_id is None
        assert AssetAllocation.objects.count() == before

    def test_fulfill_403_for_non_admin_creates_no_allocation(self, tenant_a, employee_a, asset_request_a):
        from apps.hrm.models import AssetAllocation
        asset_request_a.status = "approved"
        asset_request_a.save(update_fields=["status"])
        before = AssetAllocation.objects.count()
        c = _client_for(employee_a.party, tenant_a, email="ar_ful_na@acme.com", username="ar_ful_na_acme")
        resp = c.post(reverse("hrm:assetrequest_fulfill", args=[asset_request_a.pk]), {})
        assert resp.status_code == 403
        asset_request_a.refresh_from_db()
        assert asset_request_a.status == "approved"
        assert AssetAllocation.objects.count() == before

    def test_fulfill_get_not_allowed(self, client_a, asset_request_a):
        resp = client_a.get(reverse("hrm:assetrequest_fulfill", args=[asset_request_a.pk]))
        assert resp.status_code == 405


class TestAssetRequestSelfApprovalGuard:
    def test_approve_blocked_when_admin_is_subject_employee(self, tenant_a, employee_a, asset_request_a):
        asset_request_a.status = "pending"
        asset_request_a.save(update_fields=["status"])
        c = _admin_linked_to(employee_a.party, tenant_a, email="ar_admin_emp@acme.com", username="ar_admin_emp_acme")
        resp = c.post(reverse("hrm:assetrequest_approve", args=[asset_request_a.pk]))
        assert resp.status_code == 302
        asset_request_a.refresh_from_db()
        assert asset_request_a.status == "pending"

    def test_reject_blocked_when_admin_is_subject_employee(self, tenant_a, employee_a, asset_request_a):
        asset_request_a.status = "pending"
        asset_request_a.save(update_fields=["status"])
        c = _admin_linked_to(employee_a.party, tenant_a, email="ar_admin_emp2@acme.com", username="ar_admin_emp2_acme")
        resp = c.post(reverse("hrm:assetrequest_reject", args=[asset_request_a.pk]), {"decision_note": "no"})
        assert resp.status_code == 302
        asset_request_a.refresh_from_db()
        assert asset_request_a.status == "pending"

    def test_approve_allowed_by_a_different_admin(self, client_a, asset_request_a):
        asset_request_a.status = "pending"
        asset_request_a.save(update_fields=["status"])
        resp = client_a.post(reverse("hrm:assetrequest_approve", args=[asset_request_a.pk]))
        assert resp.status_code == 302
        asset_request_a.refresh_from_db()
        assert asset_request_a.status == "approved"


# ================================================================ My Requests hub
class TestMyRequestsHub:
    def test_200_for_linked_employee(self, tenant_a, employee_a):
        c = _client_for(employee_a.party, tenant_a, email="myreq@acme.com", username="myreq_acme")
        resp = c.get(reverse("hrm:my_requests"))
        assert resp.status_code == 200

    def test_redirect_for_user_without_linked_profile(self, client_a):
        resp = client_a.get(reverse("hrm:my_requests"))
        assert resp.status_code == 302

    def test_anonymous_redirected(self, client):
        resp = client.get(reverse("hrm:my_requests"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_context_has_tiles_and_profile(
        self, tenant_a, employee_a, document_request_a, idcard_request_a, asset_request_a
    ):
        c = _client_for(employee_a.party, tenant_a, email="myreq2@acme.com", username="myreq2_acme")
        resp = c.get(reverse("hrm:my_requests"))
        assert "tiles" in resp.context
        assert "profile" in resp.context
        labels = [t["label"] for t in resp.context["tiles"]]
        assert "Document Requests" in labels
        assert "ID Card Requests" in labels
        assert "Asset Requests" in labels
        assert "Leave Requests" in labels
        assert "Attendance Regularization" in labels

    def test_document_request_tile_counts_open_and_total_and_recent(
        self, tenant_a, employee_a, document_request_a
    ):
        c = _client_for(employee_a.party, tenant_a, email="myreq3@acme.com", username="myreq3_acme")
        resp = c.get(reverse("hrm:my_requests"))
        tile = next(t for t in resp.context["tiles"] if t["label"] == "Document Requests")
        assert tile["total_count"] == 1
        assert tile["open_count"] == 1  # draft is an OPEN status
        assert document_request_a in tile["recent"]

    def test_tile_excludes_other_employees_rows(self, tenant_a, employee_a, employee_a2, document_request_a):
        from apps.hrm.models import DocumentRequest
        DocumentRequest.objects.create(tenant=tenant_a, employee=employee_a2, purpose="Someone else's request")
        c = _client_for(employee_a.party, tenant_a, email="myreq4@acme.com", username="myreq4_acme")
        resp = c.get(reverse("hrm:my_requests"))
        tile = next(t for t in resp.context["tiles"] if t["label"] == "Document Requests")
        assert tile["total_count"] == 1

    def test_asset_request_tile_open_count_excludes_decided_rows(self, tenant_a, employee_a, asset_request_a):
        asset_request_a.status = "rejected"
        asset_request_a.save(update_fields=["status"])
        c = _client_for(employee_a.party, tenant_a, email="myreq5@acme.com", username="myreq5_acme")
        resp = c.get(reverse("hrm:my_requests"))
        tile = next(t for t in resp.context["tiles"] if t["label"] == "Asset Requests")
        assert tile["total_count"] == 1
        assert tile["open_count"] == 0
