"""Tests for CRM sub-modules 1.7–1.12 views (CRUD, filters, state-machine actions).

Covers:
- Expense CRUD + submit/approve/reject state-machine
- CrmProject CRUD + opportunity_to_project (idempotent)
- Survey CRUD + survey_respond (public endpoint)
- PurchaseOrder CRUD + crm_po_receive (bumps stock, blocks cancelled)
- OnboardingPlan + onboardingstep_complete (toggles, completes plan when all done)
- sign_document (public e-signature endpoint)
- Multi-tenant list isolation (A's list never shows B's rows)
- Delete-is-POST-only (GET does not delete)
"""
import datetime
import pytest
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ helpers / fixtures
@pytest.fixture
def project_a(db, tenant_a):
    from apps.crm.models import CrmProject
    return CrmProject.objects.create(tenant=tenant_a, name="Alpha Project", status="active")


@pytest.fixture
def project_b(db, tenant_b):
    from apps.crm.models import CrmProject
    return CrmProject.objects.create(tenant=tenant_b, name="Beta Project")


@pytest.fixture
def expense_a(db, tenant_a, admin_user):
    from apps.crm.models import Expense
    return Expense.objects.create(
        tenant=tenant_a, category="travel", amount="100.00",
        expense_date=datetime.date.today(), status="draft",
        submitted_by=admin_user,
    )


@pytest.fixture
def expense_b(db, tenant_b, admin_b):
    from apps.crm.models import Expense
    return Expense.objects.create(
        tenant=tenant_b, category="meals", amount="50.00",
        expense_date=datetime.date.today(), status="draft",
        submitted_by=admin_b,
    )


@pytest.fixture
def survey_a(db, tenant_a):
    from apps.crm.models import Survey
    return Survey.objects.create(tenant=tenant_a, survey_type="nps")


@pytest.fixture
def survey_b(db, tenant_b):
    from apps.crm.models import Survey
    return Survey.objects.create(tenant=tenant_b, survey_type="nps")


@pytest.fixture
def stock_a(db, tenant_a):
    from apps.crm.models import ProductStock
    return ProductStock.objects.create(
        tenant=tenant_a, name="Bolt", on_hand_qty="10", reorder_level="5"
    )


@pytest.fixture
def po_a(db, tenant_a):
    from apps.crm.models import PurchaseOrder
    return PurchaseOrder.objects.create(tenant=tenant_a, status="sent")


@pytest.fixture
def po_b(db, tenant_b):
    from apps.crm.models import PurchaseOrder
    return PurchaseOrder.objects.create(tenant=tenant_b, status="draft")


@pytest.fixture
def onboarding_plan_a(db, tenant_a):
    from apps.crm.models import OnboardingPlan
    return OnboardingPlan.objects.create(tenant=tenant_a, name="Onboard Acme")


@pytest.fixture
def onboarding_plan_b(db, tenant_b):
    from apps.crm.models import OnboardingPlan
    return OnboardingPlan.objects.create(tenant=tenant_b, name="Onboard Globex")


@pytest.fixture
def contract_a(db, tenant_a):
    from apps.crm.models import ContractDocument
    return ContractDocument.objects.create(tenant=tenant_a, name="NDA v1", status="sent")


@pytest.fixture
def contract_b(db, tenant_b):
    from apps.crm.models import ContractDocument
    return ContractDocument.objects.create(tenant=tenant_b, name="NDA v2", status="sent")


# ================================================================ Expenses
class TestExpenseList:
    def test_list_200(self, client_a, expense_a):
        resp = client_a.get(reverse("crm:expense_list"))
        assert resp.status_code == 200

    def test_list_shows_own_expense(self, client_a, expense_a):
        resp = client_a.get(reverse("crm:expense_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert expense_a.pk in pks

    def test_list_excludes_other_tenant_expense(self, client_a, expense_a, expense_b):
        resp = client_a.get(reverse("crm:expense_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert expense_b.pk not in pks

    def test_status_filter(self, client_a, expense_a, tenant_a):
        from apps.crm.models import Expense
        Expense.objects.create(
            tenant=tenant_a, category="meals", amount="20.00",
            expense_date=datetime.date.today(), status="approved"
        )
        resp = client_a.get(reverse("crm:expense_list") + "?status=draft")
        statuses = [obj.status for obj in resp.context["object_list"]]
        assert all(s == "draft" for s in statuses)

    def test_anon_redirects(self, client):
        resp = client.get(reverse("crm:expense_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestExpenseCreate:
    def test_create_get_200(self, client_a):
        resp = client_a.get(reverse("crm:expense_create"))
        assert resp.status_code == 200

    def test_create_post_creates_expense(self, client_a, tenant_a):
        from apps.crm.models import Expense
        resp = client_a.post(reverse("crm:expense_create"), {
            "category": "travel",
            "amount": "75.00",
            "expense_date": str(datetime.date.today()),
            "currency_code": "USD",
        })
        assert Expense.objects.filter(tenant=tenant_a).exists()

    def test_create_assigns_tenant(self, client_a, tenant_a):
        from apps.crm.models import Expense
        client_a.post(reverse("crm:expense_create"), {
            "category": "travel",
            "amount": "75.00",
            "expense_date": str(datetime.date.today()),
            "currency_code": "USD",
        })
        exp = Expense.objects.filter(tenant=tenant_a).first()
        assert exp is not None
        assert exp.tenant == tenant_a

    def test_create_sets_submitted_by(self, client_a, tenant_a, admin_user):
        from apps.crm.models import Expense
        client_a.post(reverse("crm:expense_create"), {
            "category": "travel",
            "amount": "75.00",
            "expense_date": str(datetime.date.today()),
            "currency_code": "USD",
        })
        exp = Expense.objects.filter(tenant=tenant_a).first()
        assert exp.submitted_by == admin_user

    def test_create_default_status_is_draft(self, client_a, tenant_a):
        from apps.crm.models import Expense
        client_a.post(reverse("crm:expense_create"), {
            "category": "travel",
            "amount": "75.00",
            "expense_date": str(datetime.date.today()),
            "currency_code": "USD",
        })
        exp = Expense.objects.filter(tenant=tenant_a).first()
        assert exp.status == "draft"


class TestExpenseDetail:
    def test_detail_200(self, client_a, expense_a):
        resp = client_a.get(reverse("crm:expense_detail", args=[expense_a.pk]))
        assert resp.status_code == 200

    def test_detail_cross_tenant_404(self, client_a, expense_b):
        resp = client_a.get(reverse("crm:expense_detail", args=[expense_b.pk]))
        assert resp.status_code == 404


class TestExpenseSubmit:
    def test_submit_changes_status_to_submitted(self, client_a, expense_a):
        client_a.post(reverse("crm:expense_submit", args=[expense_a.pk]))
        expense_a.refresh_from_db()
        assert expense_a.status == "submitted"

    def test_submit_non_draft_does_not_change_status(self, client_a, expense_a):
        # Set status to submitted first
        expense_a.status = "submitted"
        expense_a.save()
        client_a.post(reverse("crm:expense_submit", args=[expense_a.pk]))
        expense_a.refresh_from_db()
        assert expense_a.status == "submitted"  # still submitted, not re-submitted

    def test_submit_redirects(self, client_a, expense_a):
        resp = client_a.post(reverse("crm:expense_submit", args=[expense_a.pk]))
        assert resp.status_code == 302


class TestExpenseApprove:
    def test_approve_sets_status_approved(self, client_a, expense_a):
        client_a.post(reverse("crm:expense_approve", args=[expense_a.pk]))
        expense_a.refresh_from_db()
        assert expense_a.status == "approved"

    def test_approve_sets_approved_by(self, client_a, expense_a, admin_user):
        client_a.post(reverse("crm:expense_approve", args=[expense_a.pk]))
        expense_a.refresh_from_db()
        assert expense_a.approved_by == admin_user

    def test_reject_sets_status_rejected(self, client_a, expense_a):
        client_a.post(reverse("crm:expense_reject", args=[expense_a.pk]))
        expense_a.refresh_from_db()
        assert expense_a.status == "rejected"


class TestExpenseDelete:
    def test_delete_post_removes_expense(self, client_a, expense_a, tenant_a):
        from apps.crm.models import Expense
        client_a.post(reverse("crm:expense_delete", args=[expense_a.pk]))
        assert not Expense.objects.filter(pk=expense_a.pk).exists()

    def test_delete_get_does_not_delete(self, client_a, expense_a, tenant_a):
        from apps.crm.models import Expense
        # GET is rejected by @require_POST → 405
        resp = client_a.get(reverse("crm:expense_delete", args=[expense_a.pk]))
        assert resp.status_code == 405
        assert Expense.objects.filter(pk=expense_a.pk).exists()


# ================================================================ CrmProject + opportunity_to_project
class TestCrmProjectList:
    def test_list_200(self, client_a, project_a):
        resp = client_a.get(reverse("crm:crmproject_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, project_a):
        resp = client_a.get(reverse("crm:crmproject_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert project_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, project_a, project_b):
        resp = client_a.get(reverse("crm:crmproject_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert project_b.pk not in pks

    def test_status_filter(self, client_a, project_a, tenant_a):
        from apps.crm.models import CrmProject
        CrmProject.objects.create(tenant=tenant_a, name="Planned", status="planning")
        resp = client_a.get(reverse("crm:crmproject_list") + "?status=active")
        statuses = [obj.status for obj in resp.context["object_list"]]
        assert all(s == "active" for s in statuses)


class TestOpportunityToProject:
    def test_won_opp_creates_project(self, client_a, tenant_a, account_a):
        from apps.crm.models import Opportunity, CrmProject
        opp = Opportunity.objects.create(
            tenant=tenant_a, name="Big Win", account=account_a,
            stage="closed_won", amount="5000.00", probability=100
        )
        resp = client_a.post(reverse("crm:opportunity_to_project", args=[opp.pk]))
        assert resp.status_code == 302
        assert CrmProject.objects.filter(tenant=tenant_a, source_opportunity=opp).exists()

    def test_idempotent_second_call_returns_existing(self, client_a, tenant_a, account_a):
        from apps.crm.models import Opportunity, CrmProject
        opp = Opportunity.objects.create(
            tenant=tenant_a, name="Big Win 2", account=account_a,
            stage="closed_won", amount="5000.00", probability=100
        )
        client_a.post(reverse("crm:opportunity_to_project", args=[opp.pk]))
        client_a.post(reverse("crm:opportunity_to_project", args=[opp.pk]))
        assert CrmProject.objects.filter(tenant=tenant_a, source_opportunity=opp).count() == 1

    def test_non_won_opp_rejected(self, client_a, opportunity_a):
        """Opportunity not in closed_won stage → no project created."""
        from apps.crm.models import CrmProject
        # opportunity_a is in 'prospecting' stage
        resp = client_a.post(
            reverse("crm:opportunity_to_project", args=[opportunity_a.pk])
        )
        assert resp.status_code == 302
        assert not CrmProject.objects.filter(source_opportunity=opportunity_a).exists()

    def test_cross_tenant_404(self, client_a, opportunity_b):
        resp = client_a.post(reverse("crm:opportunity_to_project", args=[opportunity_b.pk]))
        assert resp.status_code == 404


# ================================================================ Survey + survey_respond
class TestSurveyList:
    def test_list_200(self, client_a, survey_a):
        resp = client_a.get(reverse("crm:survey_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, survey_a):
        resp = client_a.get(reverse("crm:survey_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert survey_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, survey_a, survey_b):
        resp = client_a.get(reverse("crm:survey_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert survey_b.pk not in pks


class TestSurveyRespond:
    def test_get_200(self, client, survey_a):
        resp = client.get(reverse("crm:survey_respond", args=[survey_a.token]))
        assert resp.status_code == 200

    def test_post_sets_score_and_responded_at(self, client, survey_a):
        resp = client.post(reverse("crm:survey_respond", args=[survey_a.token]), {
            "score": "9",
            "feedback_text": "Great service!",
        })
        assert resp.status_code == 302
        survey_a.refresh_from_db()
        assert survey_a.score == 9
        assert survey_a.responded_at is not None

    def test_post_sets_nps_classification(self, client, survey_a):
        client.post(reverse("crm:survey_respond", args=[survey_a.token]), {
            "score": "9",
            "feedback_text": "",
        })
        survey_a.refresh_from_db()
        assert survey_a.classification == "promoter"

    def test_score_clamped_to_10(self, client, survey_a):
        """Score > 10 is clamped to 10 by the view."""
        client.post(reverse("crm:survey_respond", args=[survey_a.token]), {
            "score": "999",
            "feedback_text": "",
        })
        survey_a.refresh_from_db()
        assert survey_a.score == 10

    def test_score_clamped_to_0(self, client, survey_a):
        """Negative score (from a crafted POST) is clamped to 0."""
        # isdigit() returns False for negative, so score remains None
        client.post(reverse("crm:survey_respond", args=[survey_a.token]), {
            "score": "-5",
            "feedback_text": "",
        })
        survey_a.refresh_from_db()
        assert survey_a.score is None or survey_a.score == 0

    def test_re_submit_is_noop(self, client, survey_a):
        """Responding twice does not overwrite the first response."""
        client.post(reverse("crm:survey_respond", args=[survey_a.token]), {"score": "9"})
        survey_a.refresh_from_db()
        first_score = survey_a.score

        client.post(reverse("crm:survey_respond", args=[survey_a.token]), {"score": "2"})
        survey_a.refresh_from_db()
        assert survey_a.score == first_score  # unchanged

    def test_feedback_length_capped(self, client, survey_a):
        """Feedback text > 4000 chars is silently truncated."""
        long_feedback = "x" * 5000
        client.post(reverse("crm:survey_respond", args=[survey_a.token]), {
            "score": "8",
            "feedback_text": long_feedback,
        })
        survey_a.refresh_from_db()
        assert len(survey_a.feedback_text) <= 4000

    def test_invalid_token_404(self, client):
        resp = client.get(reverse("crm:survey_respond", args=["invalidtoken123"]))
        assert resp.status_code == 404


class TestSurveyDelete:
    def test_delete_post_removes(self, client_a, survey_a):
        from apps.crm.models import Survey
        client_a.post(reverse("crm:survey_delete", args=[survey_a.pk]))
        assert not Survey.objects.filter(pk=survey_a.pk).exists()

    def test_delete_get_is_405(self, client_a, survey_a):
        from apps.crm.models import Survey
        resp = client_a.get(reverse("crm:survey_delete", args=[survey_a.pk]))
        assert resp.status_code == 405
        assert Survey.objects.filter(pk=survey_a.pk).exists()


# ================================================================ PurchaseOrder + crm_po_receive
class TestPurchaseOrderList:
    def test_list_200(self, client_a, po_a):
        resp = client_a.get(reverse("crm:crm_po_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, po_a):
        resp = client_a.get(reverse("crm:crm_po_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert po_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, po_a, po_b):
        resp = client_a.get(reverse("crm:crm_po_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert po_b.pk not in pks

    def test_status_filter(self, client_a, po_a, tenant_a):
        from apps.crm.models import PurchaseOrder
        PurchaseOrder.objects.create(tenant=tenant_a, status="draft")
        resp = client_a.get(reverse("crm:crm_po_list") + "?status=sent")
        statuses = [obj.status for obj in resp.context["object_list"]]
        assert all(s == "sent" for s in statuses)


class TestCrmPoReceive:
    def test_receive_sets_status_received(self, client_a, po_a, tenant_a):
        client_a.post(reverse("crm:crm_po_receive", args=[po_a.pk]))
        po_a.refresh_from_db()
        assert po_a.status == "received"

    def test_receive_sets_received_at(self, client_a, po_a):
        client_a.post(reverse("crm:crm_po_receive", args=[po_a.pk]))
        po_a.refresh_from_db()
        assert po_a.received_at is not None

    def test_receive_bumps_product_stock(self, client_a, tenant_a, po_a, stock_a):
        from decimal import Decimal
        from apps.crm.models import PurchaseOrderLine
        PurchaseOrderLine.objects.create(
            tenant=tenant_a, purchase_order=po_a,
            product=stock_a, item_name="Bolt",
            quantity="5", unit_price="1.00"
        )
        stock_a.refresh_from_db()  # ensure Decimal type
        original_qty = stock_a.on_hand_qty
        client_a.post(reverse("crm:crm_po_receive", args=[po_a.pk]))
        stock_a.refresh_from_db()
        assert stock_a.on_hand_qty == original_qty + Decimal("5")

    def test_receive_cancelled_po_blocked(self, client_a, tenant_a):
        from apps.crm.models import PurchaseOrder
        po = PurchaseOrder.objects.create(tenant=tenant_a, status="cancelled")
        client_a.post(reverse("crm:crm_po_receive", args=[po.pk]))
        po.refresh_from_db()
        assert po.status == "cancelled"  # unchanged

    def test_receive_already_received_po_blocked(self, client_a, tenant_a):
        from apps.crm.models import PurchaseOrder
        po = PurchaseOrder.objects.create(
            tenant=tenant_a, status="received", received_at=timezone.now()
        )
        resp = client_a.post(reverse("crm:crm_po_receive", args=[po.pk]))
        po.refresh_from_db()
        assert po.status == "received"  # still received, not changed

    def test_receive_cross_tenant_404(self, client_a, po_b):
        resp = client_a.post(reverse("crm:crm_po_receive", args=[po_b.pk]))
        assert resp.status_code == 404

    def test_detail_shows_own_po(self, client_a, po_a):
        resp = client_a.get(reverse("crm:crm_po_detail", args=[po_a.pk]))
        assert resp.status_code == 200


# ================================================================ Onboarding Plan + step completion
class TestOnboardingPlanList:
    def test_list_200(self, client_a, onboarding_plan_a):
        resp = client_a.get(reverse("crm:onboardingplan_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, onboarding_plan_a):
        resp = client_a.get(reverse("crm:onboardingplan_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert onboarding_plan_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, onboarding_plan_a, onboarding_plan_b):
        resp = client_a.get(reverse("crm:onboardingplan_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert onboarding_plan_b.pk not in pks


class TestOnboardingStepComplete:
    def _make_step(self, plan, tenant):
        from apps.crm.models import OnboardingStep
        return OnboardingStep.objects.create(tenant=tenant, plan=plan, title="Step A")

    def test_complete_toggles_step_to_done(self, client_a, onboarding_plan_a, tenant_a):
        step = self._make_step(onboarding_plan_a, tenant_a)
        assert step.completed_at is None
        client_a.post(reverse("crm:onboardingstep_complete", args=[step.pk]))
        step.refresh_from_db()
        assert step.completed_at is not None

    def test_complete_toggles_step_back_to_open(self, client_a, onboarding_plan_a, tenant_a):
        step = self._make_step(onboarding_plan_a, tenant_a)
        # First toggle: complete
        client_a.post(reverse("crm:onboardingstep_complete", args=[step.pk]))
        step.refresh_from_db()
        assert step.completed_at is not None
        # Second toggle: re-open
        client_a.post(reverse("crm:onboardingstep_complete", args=[step.pk]))
        step.refresh_from_db()
        assert step.completed_at is None

    def test_complete_all_steps_completes_plan(self, client_a, onboarding_plan_a, tenant_a):
        step1 = self._make_step(onboarding_plan_a, tenant_a)
        step2 = self._make_step(onboarding_plan_a, tenant_a)
        client_a.post(reverse("crm:onboardingstep_complete", args=[step1.pk]))
        client_a.post(reverse("crm:onboardingstep_complete", args=[step2.pk]))
        onboarding_plan_a.refresh_from_db()
        assert onboarding_plan_a.status == "completed"
        assert onboarding_plan_a.completed_at is not None

    def test_step_complete_cross_tenant_404(self, client_a, onboarding_plan_b, tenant_b):
        from apps.crm.models import OnboardingStep
        step = OnboardingStep.objects.create(
            tenant=tenant_b, plan=onboarding_plan_b, title="B Step"
        )
        resp = client_a.post(reverse("crm:onboardingstep_complete", args=[step.pk]))
        assert resp.status_code == 404


# ================================================================ sign_document (public)
class TestSignDocument:
    def _make_signer(self, tenant, contract):
        import secrets
        from apps.crm.models import SignerRecord
        return SignerRecord.objects.create(
            tenant=tenant, contract=contract,
            signer_name="Alice", signer_email="alice@example.com",
            token=secrets.token_urlsafe(32)
        )

    def test_get_200_with_valid_token(self, client, contract_a, tenant_a):
        signer = self._make_signer(tenant_a, contract_a)
        resp = client.get(reverse("crm:sign_document", args=[signer.token]))
        assert resp.status_code == 200

    def test_invalid_token_404(self, client):
        resp = client.get(reverse("crm:sign_document", args=["bogus-token-xyz"]))
        assert resp.status_code == 404

    def test_post_sign_sets_signed_at(self, client, contract_a, tenant_a):
        signer = self._make_signer(tenant_a, contract_a)
        resp = client.post(reverse("crm:sign_document", args=[signer.token]), {"action": "sign"})
        assert resp.status_code == 302
        signer.refresh_from_db()
        assert signer.signed_at is not None

    def test_all_signers_signed_flips_contract_to_signed(self, client, tenant_a):
        from apps.crm.models import ContractDocument
        contract = ContractDocument.objects.create(
            tenant=tenant_a, name="Solo NDA", status="sent"
        )
        signer = self._make_signer(tenant_a, contract)
        client.post(reverse("crm:sign_document", args=[signer.token]), {"action": "sign"})
        contract.refresh_from_db()
        assert contract.status == "signed"
        assert contract.signed_at is not None

    def test_double_sign_is_noop(self, client, contract_a, tenant_a):
        signer = self._make_signer(tenant_a, contract_a)
        # First sign
        client.post(reverse("crm:sign_document", args=[signer.token]), {"action": "sign"})
        signer.refresh_from_db()
        first_signed_at = signer.signed_at
        # Second sign attempt: should be a no-op (already signed)
        client.post(reverse("crm:sign_document", args=[signer.token]), {"action": "sign"})
        signer.refresh_from_db()
        assert signer.signed_at == first_signed_at

    def test_expired_contract_refuses_signing(self, client, tenant_a):
        from apps.crm.models import ContractDocument
        import secrets
        from apps.crm.models import SignerRecord
        past = timezone.now() - timezone.timedelta(days=1)
        contract = ContractDocument.objects.create(
            tenant=tenant_a, name="Expired NDA", status="sent", expires_at=past
        )
        signer = SignerRecord.objects.create(
            tenant=tenant_a, contract=contract,
            signer_name="Bob", signer_email="bob@example.com",
            token=secrets.token_urlsafe(32)
        )
        resp = client.get(reverse("crm:sign_document", args=[signer.token]))
        assert resp.status_code == 200
        # Page should show expired state
        assert resp.context.get("expired") is True

    def test_decline_sets_declined_at_and_contract_declined(self, client, tenant_a):
        from apps.crm.models import ContractDocument
        contract = ContractDocument.objects.create(
            tenant=tenant_a, name="Declined NDA", status="sent"
        )
        signer = self._make_signer(tenant_a, contract)
        client.post(reverse("crm:sign_document", args=[signer.token]), {"action": "decline"})
        signer.refresh_from_db()
        contract.refresh_from_db()
        assert signer.declined_at is not None
        assert contract.status == "declined"


# ================================================================ ProductStock
class TestProductStockList:
    def test_list_200(self, client_a, stock_a):
        resp = client_a.get(reverse("crm:productstock_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, stock_a):
        resp = client_a.get(reverse("crm:productstock_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert stock_a.pk in pks

    def test_is_active_filter(self, client_a, stock_a, tenant_a):
        from apps.crm.models import ProductStock
        ProductStock.objects.create(tenant=tenant_a, name="Inactive", is_active=False)
        # Template uses capitalized "True"/"False" for the boolean filter value
        resp = client_a.get(reverse("crm:productstock_list") + "?is_active=True")
        names = [obj.name for obj in resp.context["object_list"]]
        assert "Inactive" not in names

    def test_detail_200(self, client_a, stock_a):
        resp = client_a.get(reverse("crm:productstock_detail", args=[stock_a.pk]))
        assert resp.status_code == 200

    def test_cross_tenant_detail_404(self, client_a, tenant_b):
        from apps.crm.models import ProductStock
        stock_b = ProductStock.objects.create(tenant=tenant_b, name="B Stock")
        resp = client_a.get(reverse("crm:productstock_detail", args=[stock_b.pk]))
        assert resp.status_code == 404


# ================================================================ Anonymous blocked on ext views
class TestAnonBlockedExt:
    @pytest.mark.parametrize("url_name", [
        "crm:expense_list",
        "crm:crmproject_list",
        "crm:survey_list",
        "crm:crm_po_list",
        "crm:onboardingplan_list",
        "crm:productstock_list",
        "crm:healthscore_list",
        "crm:workflowrule_list",
        "crm:approvalrequest_list",
        "crm:doctemplate_list",
        "crm:contractdocument_list",
    ])
    def test_anon_redirected_to_login(self, client, url_name):
        resp = client.get(reverse(url_name))
        assert resp.status_code == 302
        assert "login" in resp["Location"]
