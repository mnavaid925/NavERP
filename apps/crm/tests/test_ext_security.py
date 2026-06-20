"""Security regression tests for CRM sub-modules 1.7–1.12.

Covers:
- Mass-assignment: POSTing status=approved / approved_by to expense_create must yield draft expense
- ContractDocumentForm ignores POSTed status/current_version
- ProductStockForm ignores POSTed on_hand_qty
- File upload allowlist (rejects .html/.svg) + oversized file
- Non-admin member blocked from expense_approve, approvalrequest_approve,
  crm_po_receive, health_config_edit (all @tenant_admin_required)
- expense_submit allowed for any member (owner submits own draft)
- IDOR: tenant-A accessing tenant-B objects → 404
- Delete POST-only (GET does not delete)
"""
import datetime
import io
import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ Mass-assignment
class TestExpenseMassAssignment:
    def test_posted_status_approved_yields_draft(self, member_client, tenant_a, member_user):
        """A member POSTing status=approved must receive a draft expense, not approved."""
        from apps.crm.models import Expense
        resp = member_client.post(reverse("crm:expense_create"), {
            "category": "travel",
            "amount": "99.00",
            "expense_date": str(datetime.date.today()),
            "currency_code": "USD",
            "status": "approved",        # mass-assignment attempt
        })
        exp = Expense.objects.filter(tenant=tenant_a).first()
        assert exp is not None
        assert exp.status == "draft"   # never "approved"

    def test_posted_approved_by_not_set(self, member_client, tenant_a, admin_user):
        """POSTing approved_by=<admin pk> must not be accepted by ExpenseForm."""
        from apps.crm.models import Expense
        member_client.post(reverse("crm:expense_create"), {
            "category": "meals",
            "amount": "25.00",
            "expense_date": str(datetime.date.today()),
            "currency_code": "USD",
            "approved_by": str(admin_user.pk),  # mass-assignment attempt
        })
        exp = Expense.objects.filter(tenant=tenant_a).first()
        assert exp is not None
        assert exp.approved_by is None

    def test_submitted_by_is_set_to_current_user(self, member_client, tenant_a, member_user):
        """submitted_by must be the request user, not whatever was POSTed."""
        from apps.crm.models import Expense
        member_client.post(reverse("crm:expense_create"), {
            "category": "travel",
            "amount": "50.00",
            "expense_date": str(datetime.date.today()),
            "currency_code": "USD",
        })
        exp = Expense.objects.filter(tenant=tenant_a).first()
        assert exp is not None
        assert exp.submitted_by == member_user


class TestContractDocumentFormMassAssignment:
    def test_posted_status_ignored(self, client_a, tenant_a):
        """POSTing status=signed to contractdocument_create must not create a signed contract."""
        from apps.crm.models import ContractDocument
        resp = client_a.post(reverse("crm:contractdocument_create"), {
            "name": "Test NDA",
            "body_snapshot": "",
            "status": "signed",          # ignored by form
            "current_version": "99",     # ignored by form
        })
        ctr = ContractDocument.objects.filter(tenant=tenant_a).first()
        if ctr is not None:
            assert ctr.status == "draft"
            assert ctr.current_version == 1  # default, not 99

    def test_current_version_not_in_form_fields(self, tenant_a):
        """ContractDocumentForm must NOT include current_version."""
        from apps.crm.forms import ContractDocumentForm
        form = ContractDocumentForm(tenant=tenant_a)
        assert "current_version" not in form.fields

    def test_status_not_in_contract_form_fields(self, tenant_a):
        """ContractDocumentForm must NOT include status."""
        from apps.crm.forms import ContractDocumentForm
        form = ContractDocumentForm(tenant=tenant_a)
        assert "status" not in form.fields


class TestProductStockFormMassAssignment:
    def test_on_hand_qty_not_in_form_fields(self, tenant_a):
        """ProductStockForm must NOT include on_hand_qty (system-managed via PO receive)."""
        from apps.crm.forms import ProductStockForm
        form = ProductStockForm(tenant=tenant_a)
        assert "on_hand_qty" not in form.fields

    def test_posted_on_hand_qty_ignored(self, client_a, tenant_a):
        """POSTing on_hand_qty to productstock_create must not set the inventory count."""
        from apps.crm.models import ProductStock
        client_a.post(reverse("crm:productstock_create"), {
            "name": "Widget",
            "sku": "W-001",
            "reorder_level": "5",
            "unit_cost": "2.00",
            "is_active": "on",
            "on_hand_qty": "9999",   # mass-assignment attempt
        })
        stock = ProductStock.objects.filter(tenant=tenant_a).first()
        if stock is not None:
            assert stock.on_hand_qty != 9999
            assert stock.on_hand_qty == 0  # default


# ------------------------------------------------------------------ File upload security
class TestExpenseFileUpload:
    def _post_expense(self, client, file_name, content, content_type):
        upload = io.BytesIO(content)
        upload.name = file_name
        return client.post(reverse("crm:expense_create"), {
            "category": "travel",
            "amount": "30.00",
            "expense_date": str(datetime.date.today()),
            "currency_code": "USD",
            "receipt": upload,
        }, format="multipart")

    def test_html_receipt_rejected(self, client_a, tenant_a):
        """An .html receipt must be rejected by ExpenseForm.clean_receipt()."""
        from apps.crm.models import Expense
        self._post_expense(
            client_a,
            "malicious.html",
            b"<script>alert(1)</script>",
            "text/html",
        )
        # No expense should be saved because the form is invalid
        exp = Expense.objects.filter(tenant=tenant_a).first()
        if exp is not None:
            # If it was created, there should be no receipt (HTML rejected)
            assert not str(exp.receipt).endswith(".html")
        # Alternatively the form simply fails validation

    def test_svg_receipt_rejected(self, client_a, tenant_a):
        """An .svg file (potential stored XSS same-origin) must be rejected."""
        from apps.crm.models import Expense
        self._post_expense(
            client_a,
            "payload.svg",
            b"<svg><script>alert(1)</script></svg>",
            "image/svg+xml",
        )
        exp = Expense.objects.filter(tenant=tenant_a).first()
        if exp is not None:
            assert not str(exp.receipt).endswith(".svg")

    def test_valid_pdf_accepted(self, client_a, tenant_a):
        """A .pdf receipt should pass validation."""
        from apps.crm.models import Expense
        upload = io.BytesIO(b"%PDF-1.4 fake pdf content")
        upload.name = "receipt.pdf"
        upload.size = len(b"%PDF-1.4 fake pdf content")
        client_a.post(reverse("crm:expense_create"), {
            "category": "travel",
            "amount": "30.00",
            "expense_date": str(datetime.date.today()),
            "currency_code": "USD",
            "receipt": upload,
        })
        # Expense should be created (receipt is valid)
        assert Expense.objects.filter(tenant=tenant_a).count() >= 1

    def test_oversized_file_rejected(self, client_a, tenant_a):
        """A file > 20 MB must be rejected."""
        from apps.crm.forms import MAX_UPLOAD_BYTES
        from apps.crm.models import Expense

        # Build a fake file object with oversized .size attribute
        class FakeFile(io.BytesIO):
            def __init__(self, *args, **kwargs):
                super().__init__(b"x" * 100)
                self.name = "big_receipt.pdf"
                self.size = MAX_UPLOAD_BYTES + 1

        # Use the form directly to test validation
        from apps.crm.forms import ExpenseForm
        data = {
            "category": "travel",
            "amount": "30.00",
            "expense_date": str(datetime.date.today()),
            "currency_code": "USD",
        }
        form = ExpenseForm(data, files={"receipt": FakeFile()}, tenant=tenant_a)
        assert not form.is_valid()
        assert "receipt" in form.errors


# ------------------------------------------------------------------ Authz: non-admin blocked
class TestNonAdminBlocked:
    def _make_expense(self, tenant, submitted_by):
        from apps.crm.models import Expense
        return Expense.objects.create(
            tenant=tenant, category="travel", amount="50.00",
            expense_date=datetime.date.today(), status="submitted",
            submitted_by=submitted_by,
        )

    def _make_po(self, tenant):
        from apps.crm.models import PurchaseOrder
        return PurchaseOrder.objects.create(tenant=tenant, status="sent")

    def _make_approval(self, tenant):
        from apps.crm.models import ApprovalRequest
        return ApprovalRequest.objects.create(tenant=tenant, subject="Approve me")

    def test_member_cannot_approve_expense(self, member_client, tenant_a, member_user):
        """Non-admin member → @tenant_admin_required redirects (not 200/approve)."""
        exp = self._make_expense(tenant_a, member_user)
        resp = member_client.post(reverse("crm:expense_approve", args=[exp.pk]))
        # Should redirect (302) — either to login or dashboard, not actually approve
        assert resp.status_code in (302, 403)
        exp.refresh_from_db()
        assert exp.status == "submitted"  # unchanged

    def test_member_cannot_reject_expense(self, member_client, tenant_a, member_user):
        exp = self._make_expense(tenant_a, member_user)
        resp = member_client.post(reverse("crm:expense_reject", args=[exp.pk]))
        assert resp.status_code in (302, 403)
        exp.refresh_from_db()
        assert exp.status == "submitted"  # unchanged

    def test_admin_can_approve_expense(self, client_a, tenant_a, member_user):
        """Tenant admin should be able to approve."""
        exp = self._make_expense(tenant_a, member_user)
        resp = client_a.post(reverse("crm:expense_approve", args=[exp.pk]))
        assert resp.status_code == 302
        exp.refresh_from_db()
        assert exp.status == "approved"

    def test_member_cannot_receive_po(self, member_client, tenant_a):
        """Non-admin member → @tenant_admin_required on crm_po_receive."""
        po = self._make_po(tenant_a)
        resp = member_client.post(reverse("crm:crm_po_receive", args=[po.pk]))
        assert resp.status_code in (302, 403)
        po.refresh_from_db()
        assert po.status == "sent"  # unchanged

    def test_admin_can_receive_po(self, client_a, tenant_a):
        po = self._make_po(tenant_a)
        resp = client_a.post(reverse("crm:crm_po_receive", args=[po.pk]))
        assert resp.status_code == 302
        po.refresh_from_db()
        assert po.status == "received"

    def test_member_cannot_approve_approvalrequest(self, member_client, tenant_a):
        apr = self._make_approval(tenant_a)
        resp = member_client.post(reverse("crm:approvalrequest_approve", args=[apr.pk]))
        assert resp.status_code in (302, 403)
        apr.refresh_from_db()
        assert apr.status == "pending"  # unchanged

    def test_member_cannot_edit_health_config(self, member_client, tenant_a):
        resp = member_client.post(reverse("crm:health_config_edit"), {
            "weight_tickets": "10",
            "weight_nps": "10",
            "weight_tasks": "10",
            "weight_engagement": "10",
            "red_threshold": "40",
            "yellow_threshold": "70",
        })
        assert resp.status_code in (302, 403)

    def test_admin_can_edit_health_config(self, client_a, tenant_a):
        resp = client_a.post(reverse("crm:health_config_edit"), {
            "weight_tickets": "30",
            "weight_nps": "30",
            "weight_tasks": "20",
            "weight_engagement": "20",
            "red_threshold": "35",
            "yellow_threshold": "65",
        })
        assert resp.status_code == 302
        from apps.crm.models import HealthScoreConfig
        config = HealthScoreConfig.objects.get(tenant=tenant_a)
        assert int(config.red_threshold) == 35


class TestExpenseSubmitMemberOk:
    def test_member_can_submit_own_draft(self, member_client, tenant_a, member_user):
        """expense_submit is NOT @tenant_admin_required — member can submit their own draft."""
        from apps.crm.models import Expense
        exp = Expense.objects.create(
            tenant=tenant_a, category="travel", amount="50.00",
            expense_date=datetime.date.today(), status="draft",
            submitted_by=member_user,
        )
        resp = member_client.post(reverse("crm:expense_submit", args=[exp.pk]))
        assert resp.status_code == 302
        exp.refresh_from_db()
        assert exp.status == "submitted"


# ------------------------------------------------------------------ IDOR: ext model cross-tenant 404
class TestExtIDOR:
    def _make_expense(self, tenant, submitted_by):
        from apps.crm.models import Expense
        return Expense.objects.create(
            tenant=tenant, category="travel", amount="50.00",
            expense_date=datetime.date.today(), status="draft",
            submitted_by=submitted_by,
        )

    def _make_project(self, tenant):
        from apps.crm.models import CrmProject
        return CrmProject.objects.create(tenant=tenant, name="Project")

    def _make_po(self, tenant):
        from apps.crm.models import PurchaseOrder
        return PurchaseOrder.objects.create(tenant=tenant, status="draft")

    def _make_survey(self, tenant):
        from apps.crm.models import Survey
        return Survey.objects.create(tenant=tenant, survey_type="nps")

    def test_expense_detail_cross_tenant_404(self, client_a, tenant_b, admin_b):
        exp_b = self._make_expense(tenant_b, admin_b)
        resp = client_a.get(reverse("crm:expense_detail", args=[exp_b.pk]))
        assert resp.status_code == 404

    def test_expense_edit_cross_tenant_404(self, client_a, tenant_b, admin_b):
        exp_b = self._make_expense(tenant_b, admin_b)
        resp = client_a.get(reverse("crm:expense_edit", args=[exp_b.pk]))
        assert resp.status_code == 404

    def test_expense_delete_cross_tenant_404(self, client_a, tenant_b, admin_b):
        from apps.crm.models import Expense
        exp_b = self._make_expense(tenant_b, admin_b)
        client_a.post(reverse("crm:expense_delete", args=[exp_b.pk]))
        assert Expense.objects.filter(pk=exp_b.pk).exists()  # not deleted

    def test_project_detail_cross_tenant_404(self, client_a, tenant_b):
        proj_b = self._make_project(tenant_b)
        resp = client_a.get(reverse("crm:crmproject_detail", args=[proj_b.pk]))
        assert resp.status_code == 404

    def test_po_detail_cross_tenant_404(self, client_a, tenant_b):
        po_b = self._make_po(tenant_b)
        resp = client_a.get(reverse("crm:crm_po_detail", args=[po_b.pk]))
        assert resp.status_code == 404

    def test_po_receive_cross_tenant_404(self, client_a, tenant_b):
        po_b = self._make_po(tenant_b)
        resp = client_a.post(reverse("crm:crm_po_receive", args=[po_b.pk]))
        assert resp.status_code == 404

    def test_survey_detail_cross_tenant_404(self, client_a, tenant_b):
        survey_b = self._make_survey(tenant_b)
        resp = client_a.get(reverse("crm:survey_detail", args=[survey_b.pk]))
        assert resp.status_code == 404

    def test_expense_submit_cross_tenant_404(self, client_a, tenant_b, admin_b):
        exp_b = self._make_expense(tenant_b, admin_b)
        resp = client_a.post(reverse("crm:expense_submit", args=[exp_b.pk]))
        assert resp.status_code == 404

    def test_expense_approve_cross_tenant_404(self, client_a, tenant_b, admin_b):
        exp_b = self._make_expense(tenant_b, admin_b)
        resp = client_a.post(reverse("crm:expense_approve", args=[exp_b.pk]))
        assert resp.status_code == 404

    def test_onboarding_plan_detail_cross_tenant_404(self, client_a, tenant_b):
        from apps.crm.models import OnboardingPlan
        plan_b = OnboardingPlan.objects.create(tenant=tenant_b, name="B Plan")
        resp = client_a.get(reverse("crm:onboardingplan_detail", args=[plan_b.pk]))
        assert resp.status_code == 404

    def test_contract_detail_cross_tenant_404(self, client_a, tenant_b):
        from apps.crm.models import ContractDocument
        ctr_b = ContractDocument.objects.create(tenant=tenant_b, name="B NDA")
        resp = client_a.get(reverse("crm:contractdocument_detail", args=[ctr_b.pk]))
        assert resp.status_code == 404


# ------------------------------------------------------------------ Delete POST-only
class TestDeletePostOnly:
    def test_expense_delete_get_405(self, client_a, tenant_a, admin_user):
        from apps.crm.models import Expense
        exp = Expense.objects.create(
            tenant=tenant_a, category="travel", amount="30.00",
            expense_date=datetime.date.today(), submitted_by=admin_user
        )
        resp = client_a.get(reverse("crm:expense_delete", args=[exp.pk]))
        assert resp.status_code == 405
        assert Expense.objects.filter(pk=exp.pk).exists()

    def test_project_delete_get_405(self, client_a, tenant_a):
        from apps.crm.models import CrmProject
        proj = CrmProject.objects.create(tenant=tenant_a, name="P1")
        resp = client_a.get(reverse("crm:crmproject_delete", args=[proj.pk]))
        assert resp.status_code == 405
        assert CrmProject.objects.filter(pk=proj.pk).exists()

    def test_po_delete_get_405(self, client_a, tenant_a):
        from apps.crm.models import PurchaseOrder
        po = PurchaseOrder.objects.create(tenant=tenant_a, status="draft")
        resp = client_a.get(reverse("crm:crm_po_delete", args=[po.pk]))
        assert resp.status_code == 405
        assert PurchaseOrder.objects.filter(pk=po.pk).exists()

    def test_survey_delete_get_405(self, client_a, tenant_a):
        from apps.crm.models import Survey
        s = Survey.objects.create(tenant=tenant_a, survey_type="nps")
        resp = client_a.get(reverse("crm:survey_delete", args=[s.pk]))
        assert resp.status_code == 405
        assert Survey.objects.filter(pk=s.pk).exists()


# ------------------------------------------------------------------ CSRF enforcement for ext views
class TestCSRFExt:
    def test_expense_approve_enforces_csrf(self, admin_user, tenant_a):
        from apps.crm.models import Expense
        exp = Expense.objects.create(
            tenant=tenant_a, category="travel", amount="50.00",
            expense_date=datetime.date.today(), submitted_by=admin_user
        )
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("crm:expense_approve", args=[exp.pk]))
        assert resp.status_code == 403

    def test_crm_po_receive_enforces_csrf(self, admin_user, tenant_a):
        from apps.crm.models import PurchaseOrder
        po = PurchaseOrder.objects.create(tenant=tenant_a, status="sent")
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("crm:crm_po_receive", args=[po.pk]))
        assert resp.status_code == 403

    def test_expense_delete_enforces_csrf(self, admin_user, tenant_a):
        from apps.crm.models import Expense
        exp = Expense.objects.create(
            tenant=tenant_a, category="travel", amount="50.00",
            expense_date=datetime.date.today(), submitted_by=admin_user
        )
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("crm:expense_delete", args=[exp.pk]))
        assert resp.status_code == 403


# ------------------------------------------------------------------ ApprovalRequest approve/reject
class TestApprovalRequestActions:
    def _make_approval(self, tenant):
        from apps.crm.models import ApprovalRequest
        return ApprovalRequest.objects.create(
            tenant=tenant, subject="Approve Discount 50%", status="pending"
        )

    def test_admin_can_approve(self, client_a, tenant_a):
        apr = self._make_approval(tenant_a)
        resp = client_a.post(reverse("crm:approvalrequest_approve", args=[apr.pk]))
        assert resp.status_code == 302
        apr.refresh_from_db()
        assert apr.status == "approved"
        assert apr.approved_at is not None

    def test_admin_can_reject(self, client_a, tenant_a):
        apr = self._make_approval(tenant_a)
        resp = client_a.post(reverse("crm:approvalrequest_reject", args=[apr.pk]))
        assert resp.status_code == 302
        apr.refresh_from_db()
        assert apr.status == "rejected"
        assert apr.rejected_at is not None

    def test_member_cannot_approve(self, member_client, tenant_a):
        apr = self._make_approval(tenant_a)
        resp = member_client.post(reverse("crm:approvalrequest_approve", args=[apr.pk]))
        assert resp.status_code in (302, 403)
        apr.refresh_from_db()
        assert apr.status == "pending"

    def test_member_cannot_reject(self, member_client, tenant_a):
        apr = self._make_approval(tenant_a)
        resp = member_client.post(reverse("crm:approvalrequest_reject", args=[apr.pk]))
        assert resp.status_code in (302, 403)
        apr.refresh_from_db()
        assert apr.status == "pending"
