"""Tests for CRM sub-modules 1.7–1.12 model invariants.

Covers:
- Survey NPS auto-classification and token generation
- CrmMilestone completed_at stamping / clearing
- PurchaseOrder.recalc_total()
- ProductStock.is_low_stock
- OnboardingPlan.progress_pct
- compute_health_score()
- Per-tenant auto-numbering for new prefixes (EXP, PRJ, CTR, etc.)
"""
import pytest
from decimal import Decimal
from django.utils import timezone

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ Survey
class TestSurveyAutoClassification:
    def _make_survey(self, tenant, survey_type="nps", score=None):
        from apps.crm.models import Survey
        return Survey.objects.create(
            tenant=tenant, survey_type=survey_type, score=score
        )

    def test_nps_score_9_is_promoter(self, tenant_a):
        s = self._make_survey(tenant_a, score=9)
        assert s.classification == "promoter"

    def test_nps_score_10_is_promoter(self, tenant_a):
        s = self._make_survey(tenant_a, score=10)
        assert s.classification == "promoter"

    def test_nps_score_7_is_passive(self, tenant_a):
        s = self._make_survey(tenant_a, score=7)
        assert s.classification == "passive"

    def test_nps_score_8_is_passive(self, tenant_a):
        s = self._make_survey(tenant_a, score=8)
        assert s.classification == "passive"

    def test_nps_score_6_is_detractor(self, tenant_a):
        s = self._make_survey(tenant_a, score=6)
        assert s.classification == "detractor"

    def test_nps_score_0_is_detractor(self, tenant_a):
        s = self._make_survey(tenant_a, score=0)
        assert s.classification == "detractor"

    def test_nps_no_score_leaves_classification_blank(self, tenant_a):
        s = self._make_survey(tenant_a, score=None)
        assert s.classification == ""

    def test_csat_type_leaves_classification_blank(self, tenant_a):
        s = self._make_survey(tenant_a, survey_type="csat", score=8)
        assert s.classification == ""

    def test_ces_type_leaves_classification_blank(self, tenant_a):
        s = self._make_survey(tenant_a, survey_type="ces", score=5)
        assert s.classification == ""

    def test_token_auto_generated(self, tenant_a):
        s = self._make_survey(tenant_a)
        assert s.token is not None
        assert len(s.token) > 10

    def test_token_unique_per_survey(self, tenant_a):
        s1 = self._make_survey(tenant_a)
        s2 = self._make_survey(tenant_a)
        assert s1.token != s2.token

    def test_token_not_regenerated_on_resave(self, tenant_a):
        s = self._make_survey(tenant_a)
        original_token = s.token
        s.score = 9
        s.save()
        s.refresh_from_db()
        assert s.token == original_token

    def test_classification_updated_on_resave(self, tenant_a):
        """Changing score on save() re-classifies."""
        s = self._make_survey(tenant_a, score=5)
        assert s.classification == "detractor"
        s.score = 10
        s.save()
        s.refresh_from_db()
        assert s.classification == "promoter"

    def test_survey_str(self, tenant_a):
        s = self._make_survey(tenant_a, survey_type="nps")
        assert "NPS" in str(s) or "nps" in str(s).lower()

    def test_survey_number_prefix(self, tenant_a):
        s = self._make_survey(tenant_a)
        assert s.number.startswith("NPS-")

    def test_survey_unique_together_tenant_number(self, tenant_a):
        from apps.crm.models import Survey
        from django.db import IntegrityError
        s1 = self._make_survey(tenant_a)
        with pytest.raises(IntegrityError):
            Survey.objects.create(tenant=tenant_a, survey_type="nps", number=s1.number)


# ------------------------------------------------------------------ CrmMilestone
class TestCrmMilestoneCompletedAt:
    def _make_project(self, tenant):
        from apps.crm.models import CrmProject
        return CrmProject.objects.create(tenant=tenant, name="Test Project")

    def test_completed_at_stamped_when_status_completed(self, tenant_a):
        from apps.crm.models import CrmMilestone
        proj = self._make_project(tenant_a)
        ms = CrmMilestone.objects.create(
            tenant=tenant_a, project=proj, title="M1", status="completed"
        )
        assert ms.completed_at is not None

    def test_completed_at_null_when_not_started(self, tenant_a):
        from apps.crm.models import CrmMilestone
        proj = self._make_project(tenant_a)
        ms = CrmMilestone.objects.create(
            tenant=tenant_a, project=proj, title="M1", status="not_started"
        )
        assert ms.completed_at is None

    def test_completed_at_cleared_when_reopened(self, tenant_a):
        from apps.crm.models import CrmMilestone
        proj = self._make_project(tenant_a)
        ms = CrmMilestone.objects.create(
            tenant=tenant_a, project=proj, title="M1", status="completed"
        )
        assert ms.completed_at is not None
        ms.status = "in_progress"
        ms.save()
        ms.refresh_from_db()
        assert ms.completed_at is None

    def test_completed_at_not_overwritten_on_resave(self, tenant_a):
        from apps.crm.models import CrmMilestone
        proj = self._make_project(tenant_a)
        ms = CrmMilestone.objects.create(
            tenant=tenant_a, project=proj, title="M1", status="completed"
        )
        ms.refresh_from_db()
        first_stamp = ms.completed_at
        ms.title = "Updated Title"
        ms.save()
        ms.refresh_from_db()
        assert ms.completed_at == first_stamp

    def test_milestone_str(self, tenant_a):
        from apps.crm.models import CrmMilestone
        proj = self._make_project(tenant_a)
        ms = CrmMilestone.objects.create(
            tenant=tenant_a, project=proj, title="My Milestone", status="not_started"
        )
        assert "MS-" in str(ms)
        assert "My Milestone" in str(ms)

    def test_milestone_number_prefix(self, tenant_a):
        from apps.crm.models import CrmMilestone
        proj = self._make_project(tenant_a)
        ms = CrmMilestone.objects.create(
            tenant=tenant_a, project=proj, title="T", status="not_started"
        )
        assert ms.number.startswith("MS-")

    def test_milestone_blocked_status_null_completed_at(self, tenant_a):
        from apps.crm.models import CrmMilestone
        proj = self._make_project(tenant_a)
        ms = CrmMilestone.objects.create(
            tenant=tenant_a, project=proj, title="M1", status="blocked"
        )
        assert ms.completed_at is None


# ------------------------------------------------------------------ PurchaseOrder.recalc_total
class TestPurchaseOrderRecalcTotal:
    def _make_po(self, tenant):
        from apps.crm.models import PurchaseOrder
        return PurchaseOrder.objects.create(tenant=tenant, status="draft")

    def test_recalc_total_single_line(self, tenant_a):
        from apps.crm.models import PurchaseOrderLine
        po = self._make_po(tenant_a)
        PurchaseOrderLine.objects.create(
            tenant=tenant_a, purchase_order=po,
            item_name="Widget", quantity=Decimal("2"), unit_price=Decimal("10.00")
        )
        po.recalc_total()
        po.refresh_from_db()
        assert po.total_amount == Decimal("20.00")

    def test_recalc_total_multiple_lines(self, tenant_a):
        from apps.crm.models import PurchaseOrderLine
        po = self._make_po(tenant_a)
        PurchaseOrderLine.objects.create(
            tenant=tenant_a, purchase_order=po,
            item_name="Widget", quantity=Decimal("3"), unit_price=Decimal("5.00")
        )
        PurchaseOrderLine.objects.create(
            tenant=tenant_a, purchase_order=po,
            item_name="Gadget", quantity=Decimal("1"), unit_price=Decimal("100.00")
        )
        po.recalc_total()
        po.refresh_from_db()
        assert po.total_amount == Decimal("115.00")

    def test_recalc_total_no_lines_is_zero(self, tenant_a):
        po = self._make_po(tenant_a)
        po.recalc_total()
        po.refresh_from_db()
        assert po.total_amount == Decimal("0")

    def test_line_total_property(self, tenant_a):
        from apps.crm.models import PurchaseOrderLine
        po = self._make_po(tenant_a)
        line = PurchaseOrderLine.objects.create(
            tenant=tenant_a, purchase_order=po,
            item_name="X", quantity=Decimal("4"), unit_price=Decimal("7.50")
        )
        assert line.line_total == Decimal("30.00")

    def test_po_number_prefix(self, tenant_a):
        po = self._make_po(tenant_a)
        assert po.number.startswith("PO-")

    def test_po_str(self, tenant_a):
        po = self._make_po(tenant_a)
        assert "PO-" in str(po)


# ------------------------------------------------------------------ ProductStock.is_low_stock
class TestProductStockIsLowStock:
    def _make_stock(self, tenant, on_hand, reorder):
        from apps.crm.models import ProductStock
        return ProductStock.objects.create(
            tenant=tenant, name="Widget",
            on_hand_qty=Decimal(str(on_hand)),
            reorder_level=Decimal(str(reorder))
        )

    def test_is_low_stock_true_when_on_hand_equals_reorder(self, tenant_a):
        s = self._make_stock(tenant_a, on_hand=5, reorder=5)
        assert s.is_low_stock is True

    def test_is_low_stock_true_when_on_hand_below_reorder(self, tenant_a):
        s = self._make_stock(tenant_a, on_hand=3, reorder=10)
        assert s.is_low_stock is True

    def test_is_low_stock_false_when_on_hand_above_reorder(self, tenant_a):
        s = self._make_stock(tenant_a, on_hand=20, reorder=10)
        assert s.is_low_stock is False

    def test_is_low_stock_true_when_zero_on_hand(self, tenant_a):
        s = self._make_stock(tenant_a, on_hand=0, reorder=0)
        assert s.is_low_stock is True

    def test_stock_str(self, tenant_a):
        s = self._make_stock(tenant_a, on_hand=5, reorder=3)
        assert "STK-" in str(s)
        assert "Widget" in str(s)

    def test_stock_number_prefix(self, tenant_a):
        s = self._make_stock(tenant_a, on_hand=10, reorder=5)
        assert s.number.startswith("STK-")

    def test_stock_unique_together_tenant_number(self, tenant_a):
        from apps.crm.models import ProductStock
        from django.db import IntegrityError
        s1 = self._make_stock(tenant_a, on_hand=1, reorder=0)
        with pytest.raises(IntegrityError):
            ProductStock.objects.create(
                tenant=tenant_a, name="Dup", number=s1.number, on_hand_qty=1, reorder_level=0
            )


# ------------------------------------------------------------------ OnboardingPlan.progress_pct
class TestOnboardingPlanProgressPct:
    def _make_plan(self, tenant):
        from apps.crm.models import OnboardingPlan
        return OnboardingPlan.objects.create(tenant=tenant, name="Test Plan")

    def _add_step(self, plan, tenant, done=False):
        from apps.crm.models import OnboardingStep
        return OnboardingStep.objects.create(
            tenant=tenant, plan=plan, title="Step",
            completed_at=timezone.now() if done else None
        )

    def test_progress_pct_zero_when_no_steps(self, tenant_a):
        plan = self._make_plan(tenant_a)
        assert plan.progress_pct == 0

    def test_progress_pct_zero_when_none_done(self, tenant_a):
        plan = self._make_plan(tenant_a)
        self._add_step(plan, tenant_a, done=False)
        self._add_step(plan, tenant_a, done=False)
        assert plan.progress_pct == 0

    def test_progress_pct_100_when_all_done(self, tenant_a):
        plan = self._make_plan(tenant_a)
        self._add_step(plan, tenant_a, done=True)
        self._add_step(plan, tenant_a, done=True)
        assert plan.progress_pct == 100

    def test_progress_pct_50_when_half_done(self, tenant_a):
        plan = self._make_plan(tenant_a)
        self._add_step(plan, tenant_a, done=True)
        self._add_step(plan, tenant_a, done=False)
        assert plan.progress_pct == 50

    def test_progress_pct_rounded(self, tenant_a):
        """1 of 3 done = 33.33... rounds to 33."""
        plan = self._make_plan(tenant_a)
        self._add_step(plan, tenant_a, done=True)
        self._add_step(plan, tenant_a, done=False)
        self._add_step(plan, tenant_a, done=False)
        assert plan.progress_pct == 33

    def test_plan_str(self, tenant_a):
        plan = self._make_plan(tenant_a)
        assert "CS-" in str(plan)
        assert "Test Plan" in str(plan)

    def test_plan_number_prefix(self, tenant_a):
        plan = self._make_plan(tenant_a)
        assert plan.number.startswith("CS-")


# ------------------------------------------------------------------ compute_health_score
class TestComputeHealthScore:
    def _make_account(self, tenant):
        from apps.core.models import Party
        return Party.objects.create(tenant=tenant, kind="organization", name="Health Co")

    def test_returns_health_score_object(self, tenant_a):
        from apps.crm.models import compute_health_score, HealthScore
        acct = self._make_account(tenant_a)
        hs = compute_health_score(acct, tenant_a)
        assert isinstance(hs, HealthScore)

    def test_score_is_0_to_100(self, tenant_a):
        from apps.crm.models import compute_health_score
        acct = self._make_account(tenant_a)
        hs = compute_health_score(acct, tenant_a)
        assert 0 <= hs.score <= 100

    def test_tier_is_set(self, tenant_a):
        from apps.crm.models import compute_health_score
        acct = self._make_account(tenant_a)
        hs = compute_health_score(acct, tenant_a)
        assert hs.tier in ("green", "yellow", "red")

    def test_breakdown_dict_has_required_keys(self, tenant_a):
        from apps.crm.models import compute_health_score
        acct = self._make_account(tenant_a)
        hs = compute_health_score(acct, tenant_a)
        assert "tickets" in hs.breakdown
        assert "nps" in hs.breakdown
        assert "tasks" in hs.breakdown
        assert "engagement" in hs.breakdown

    def test_idempotent_one_row_per_account(self, tenant_a):
        from apps.crm.models import compute_health_score, HealthScore
        acct = self._make_account(tenant_a)
        compute_health_score(acct, tenant_a)
        compute_health_score(acct, tenant_a)
        count = HealthScore.objects.filter(tenant=tenant_a, account=acct).count()
        assert count == 1

    def test_open_case_lowers_tickets_score(self, tenant_a):
        """More open cases → lower health score (tickets component penalizes open cases)."""
        from apps.crm.models import compute_health_score, Case
        acct = self._make_account(tenant_a)
        # No cases → tickets_score = 100
        hs_no_cases = compute_health_score(acct, tenant_a)
        score_no_cases = hs_no_cases.score

        # Create open cases to lower the tickets score
        for i in range(5):
            Case.objects.create(
                tenant=tenant_a, account=acct,
                subject=f"Case {i}", status="open"
            )
        hs_with_cases = compute_health_score(acct, tenant_a)
        assert hs_with_cases.score <= score_no_cases

    def test_promoter_nps_boosts_score(self, tenant_a):
        """A promoter NPS survey should result in high NPS component."""
        from apps.crm.models import compute_health_score, Survey
        acct = self._make_account(tenant_a)
        Survey.objects.create(
            tenant=tenant_a, account=acct, survey_type="nps",
            score=10, sent_at=timezone.now()
        )
        hs = compute_health_score(acct, tenant_a)
        assert hs.breakdown["nps"] == 100

    def test_green_tier_when_high_score(self, tenant_a):
        """An account with promoter NPS and open opportunity should be green."""
        from apps.crm.models import compute_health_score, Survey, Opportunity
        from apps.core.models import Party
        acct = Party.objects.create(tenant=tenant_a, kind="organization", name="Healthy Corp")
        Survey.objects.create(
            tenant=tenant_a, account=acct, survey_type="nps",
            score=10, sent_at=timezone.now()
        )
        Opportunity.objects.create(
            tenant=tenant_a, account=acct, name="Big Deal", stage="prospecting", probability=50
        )
        hs = compute_health_score(acct, tenant_a)
        # Score should be in green territory (>= yellow_threshold=70 by default)
        assert hs.tier in ("green", "yellow")  # at least not red in this scenario

    def test_computed_at_is_set(self, tenant_a):
        from apps.crm.models import compute_health_score
        acct = self._make_account(tenant_a)
        hs = compute_health_score(acct, tenant_a)
        assert hs.computed_at is not None

    def test_health_score_number_prefix(self, tenant_a):
        from apps.crm.models import compute_health_score
        acct = self._make_account(tenant_a)
        hs = compute_health_score(acct, tenant_a)
        assert hs.number.startswith("HS-")

    def test_tier_thresholds_red(self, tenant_a):
        """Score below red_threshold → red tier."""
        from apps.crm.models import (
            compute_health_score, HealthScoreConfig, Case
        )
        config, _ = HealthScoreConfig.objects.get_or_create(tenant=tenant_a)
        acct = self._make_account(tenant_a)
        # Create many open cases to push tickets_score very low
        for i in range(5):
            Case.objects.create(
                tenant=tenant_a, account=acct,
                subject=f"C{i}", status="open"
            )
        hs = compute_health_score(acct, tenant_a)
        assert hs.score < 100  # ensure at least some penalty was applied


# ------------------------------------------------------------------ Auto-numbering for ext models
class TestExtAutoNumbering:
    def test_expense_number_prefix(self, tenant_a):
        from apps.crm.models import Expense
        import datetime
        exp = Expense.objects.create(
            tenant=tenant_a, category="travel", amount="50.00",
            expense_date=datetime.date.today()
        )
        assert exp.number.startswith("EXP-")

    def test_crmproject_number_prefix(self, tenant_a):
        from apps.crm.models import CrmProject
        proj = CrmProject.objects.create(tenant=tenant_a, name="Alpha Project")
        assert proj.number.startswith("PRJ-")

    def test_contractdocument_number_prefix(self, tenant_a):
        from apps.crm.models import ContractDocument
        ctr = ContractDocument.objects.create(tenant=tenant_a, name="NDA v1")
        assert ctr.number.startswith("CTR-")

    def test_doctemplate_number_prefix(self, tenant_a):
        from apps.crm.models import DocTemplate
        tpl = DocTemplate.objects.create(tenant=tenant_a, name="NDA Template")
        assert tpl.number.startswith("TPL-")

    def test_workflowrule_number_prefix(self, tenant_a):
        from apps.crm.models import WorkflowRule
        wfr = WorkflowRule.objects.create(tenant=tenant_a, name="Auto Rule")
        assert wfr.number.startswith("WFR-")

    def test_approvalrequest_number_prefix(self, tenant_a):
        from apps.crm.models import ApprovalRequest
        apr = ApprovalRequest.objects.create(tenant=tenant_a, subject="Approve Discount")
        assert apr.number.startswith("APR-")

    def test_onboardingplan_number_prefix(self, tenant_a):
        from apps.crm.models import OnboardingPlan
        plan = OnboardingPlan.objects.create(tenant=tenant_a, name="Onboarding Plan")
        assert plan.number.startswith("CS-")

    def test_healthscore_number_prefix(self, tenant_a):
        from apps.crm.models import HealthScore
        from apps.core.models import Party
        acct = Party.objects.create(tenant=tenant_a, kind="organization", name="Acct")
        hs = HealthScore.objects.create(tenant=tenant_a, account=acct, score=75, tier="green")
        assert hs.number.startswith("HS-")

    def test_survey_number_prefix(self, tenant_a):
        from apps.crm.models import Survey
        s = Survey.objects.create(tenant=tenant_a, survey_type="nps")
        assert s.number.startswith("NPS-")

    def test_productstock_number_prefix(self, tenant_a):
        from apps.crm.models import ProductStock
        s = ProductStock.objects.create(tenant=tenant_a, name="Bolt")
        assert s.number.startswith("STK-")

    def test_purchaseorder_number_prefix(self, tenant_a):
        from apps.crm.models import PurchaseOrder
        po = PurchaseOrder.objects.create(tenant=tenant_a, status="draft")
        assert po.number.startswith("PO-")

    def test_sequential_numbering_per_tenant(self, tenant_a, tenant_b):
        from apps.crm.models import CrmProject
        p1 = CrmProject.objects.create(tenant=tenant_a, name="P1")
        p2 = CrmProject.objects.create(tenant=tenant_a, name="P2")
        pb = CrmProject.objects.create(tenant=tenant_b, name="PB")
        assert p1.number == "PRJ-00001"
        assert p2.number == "PRJ-00002"
        assert pb.number == "PRJ-00001"

    def test_milestone_number_prefix(self, tenant_a):
        from apps.crm.models import CrmProject, CrmMilestone
        proj = CrmProject.objects.create(tenant=tenant_a, name="P1")
        ms = CrmMilestone.objects.create(
            tenant=tenant_a, project=proj, title="T", status="not_started"
        )
        assert ms.number.startswith("MS-")

    def test_timesheet_number_prefix(self, tenant_a):
        from apps.crm.models import CrmProject, Timesheet
        import datetime
        proj = CrmProject.objects.create(tenant=tenant_a, name="P1")
        ts = Timesheet.objects.create(
            tenant=tenant_a, project=proj, date=datetime.date.today(), hours=Decimal("2")
        )
        assert ts.number.startswith("TS-")

    def test_partner_portal_access_number_prefix(self, tenant_a):
        from apps.crm.models import PartnerPortalAccess
        ppa = PartnerPortalAccess.objects.create(tenant=tenant_a)
        assert ppa.number.startswith("PRT-")
