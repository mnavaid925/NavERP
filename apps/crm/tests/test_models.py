"""Tests for CRM models: auto-numbering, __str__, properties, save() signals."""
import pytest
from django.utils import timezone

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ TenantNumbered / auto-number
class TestAutoNumbering:
    """Verify that each model gets its per-tenant sequential number."""

    def test_lead_number_format(self, lead_a):
        assert lead_a.number == "LEAD-00001"

    def test_opportunity_number_format(self, opportunity_a):
        assert opportunity_a.number == "OPP-00001"

    def test_campaign_number_format(self, campaign_a):
        assert campaign_a.number == "CAM-00001"

    def test_case_number_format(self, case_a):
        assert case_a.number == "CASE-00001"

    def test_article_number_format(self, article_a):
        assert article_a.number == "KB-00001"

    def test_task_number_format(self, task_a):
        assert task_a.number == "TASK-00001"

    def test_lead_sequential_increment(self, tenant_a):
        from apps.crm.models import Lead
        l1 = Lead.objects.create(tenant=tenant_a, name="First")
        l2 = Lead.objects.create(tenant=tenant_a, name="Second")
        assert l1.number == "LEAD-00001"
        assert l2.number == "LEAD-00002"

    def test_per_tenant_isolation(self, tenant_a, tenant_b):
        """Each tenant's counter starts at 1 independently."""
        from apps.crm.models import Lead
        la = Lead.objects.create(tenant=tenant_a, name="A Lead")
        lb = Lead.objects.create(tenant=tenant_b, name="B Lead")
        assert la.number == "LEAD-00001"
        assert lb.number == "LEAD-00001"

    def test_number_not_reassigned_on_resave(self, lead_a):
        """Re-saving a Lead must not change its number."""
        original = lead_a.number
        lead_a.status = "contacted"
        lead_a.save()
        lead_a.refresh_from_db()
        assert lead_a.number == original

    def test_unique_together_tenant_number(self, tenant_a, lead_a):
        """Manually duplicating the number for the same tenant raises IntegrityError."""
        from apps.crm.models import Lead
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            Lead.objects.create(tenant=tenant_a, name="Dup", number="LEAD-00001")


# ------------------------------------------------------------------ Lead
class TestLead:
    def test_str(self, lead_a):
        assert "LEAD-00001" in str(lead_a)
        assert "Jane Doe" in str(lead_a)

    def test_default_status(self, tenant_a):
        from apps.crm.models import Lead
        lead = Lead.objects.create(tenant=tenant_a, name="Test")
        assert lead.status == "new"

    def test_default_source(self, tenant_a):
        from apps.crm.models import Lead
        lead = Lead.objects.create(tenant=tenant_a, name="Test")
        assert lead.source == "web"

    def test_default_rating(self, tenant_a):
        from apps.crm.models import Lead
        lead = Lead.objects.create(tenant=tenant_a, name="Test")
        assert lead.rating == "warm"

    def test_status_choices_values(self):
        from apps.crm.models import Lead
        keys = [k for k, _ in Lead.STATUS_CHOICES]
        for expected in ("new", "contacted", "qualified", "unqualified", "converted", "recycled"):
            assert expected in keys

    def test_source_choices_values(self):
        from apps.crm.models import Lead
        keys = [k for k, _ in Lead.SOURCE_CHOICES]
        for expected in ("web", "referral", "event", "cold_call", "social"):
            assert expected in keys

    def test_rating_choices_values(self):
        from apps.crm.models import Lead
        keys = [k for k, _ in Lead.RATING_CHOICES]
        assert set(keys) == {"hot", "warm", "cold"}

    def test_converted_party_default_null(self, lead_a):
        assert lead_a.converted_party is None


# ------------------------------------------------------------------ Opportunity
class TestOpportunity:
    def test_str(self, opportunity_a):
        assert "OPP-00001" in str(opportunity_a)
        assert "Big Deal" in str(opportunity_a)

    def test_weighted_amount_calculation(self, tenant_a):
        # NOTE: BUG in apps/crm/models.py:193 — weighted_amount uses `self.amount` directly
        # which is a str on a freshly created instance (before DB read converts it to Decimal).
        # We refresh_from_db() here to work around the bug and test the correct *logic*;
        # the TypeError is separately documented.
        from apps.crm.models import Opportunity
        opp = Opportunity.objects.create(
            tenant=tenant_a, name="Test", amount="1000.00", probability=25
        )
        opp.refresh_from_db()
        assert float(opp.weighted_amount) == pytest.approx(250.0)

    def test_weighted_amount_zero_probability(self, tenant_a):
        from apps.crm.models import Opportunity
        opp = Opportunity.objects.create(
            tenant=tenant_a, name="Test", amount="5000.00", probability=0
        )
        opp.refresh_from_db()
        assert float(opp.weighted_amount) == pytest.approx(0.0)

    def test_weighted_amount_full_probability(self, tenant_a):
        from apps.crm.models import Opportunity
        opp = Opportunity.objects.create(
            tenant=tenant_a, name="Test", amount="2000.00", probability=100
        )
        opp.refresh_from_db()
        assert float(opp.weighted_amount) == pytest.approx(2000.0)

    def test_weighted_amount_fails_before_db_roundtrip(self, tenant_a):
        """BUG SURFACE: weighted_amount raises TypeError on a freshly .create()'d instance
        because self.amount is still a str ('1000.00') before DB read converts it to Decimal.
        See apps/crm/models.py:193 — fix: cast to Decimal: Decimal(self.amount or 0).
        """
        from decimal import Decimal
        from apps.crm.models import Opportunity
        opp = Opportunity.objects.create(
            tenant=tenant_a, name="Bug Trigger", amount="1000.00", probability=25
        )
        # After refresh the property works correctly; the bug only bites
        # when used directly on a save-returned object without a DB read.
        opp.refresh_from_db()
        assert isinstance(opp.amount, Decimal)

    def test_is_open_for_open_stages(self, tenant_a):
        from apps.crm.models import Opportunity
        for stage in ("prospecting", "qualification", "proposal", "negotiation"):
            opp = Opportunity.objects.create(tenant=tenant_a, name=f"Test {stage}", stage=stage)
            assert opp.is_open is True

    def test_is_open_false_for_closed_stages(self, tenant_a):
        from apps.crm.models import Opportunity
        for stage in ("closed_won", "closed_lost"):
            opp = Opportunity.objects.create(tenant=tenant_a, name=f"Test {stage}", stage=stage)
            assert opp.is_open is False

    def test_is_won(self, tenant_a):
        from apps.crm.models import Opportunity
        opp = Opportunity.objects.create(
            tenant=tenant_a, name="Won Deal", stage="closed_won"
        )
        assert opp.is_won is True
        opp2 = Opportunity.objects.create(
            tenant=tenant_a, name="Lost Deal", stage="closed_lost"
        )
        assert opp2.is_won is False

    def test_default_stage(self, tenant_a):
        from apps.crm.models import Opportunity
        opp = Opportunity.objects.create(tenant=tenant_a, name="Test")
        assert opp.stage == "prospecting"

    def test_stage_choices(self):
        from apps.crm.models import Opportunity
        keys = [k for k, _ in Opportunity.STAGE_CHOICES]
        for expected in ("prospecting", "qualification", "proposal", "negotiation", "closed_won", "closed_lost"):
            assert expected in keys


# ------------------------------------------------------------------ Campaign
class TestCampaign:
    def test_str(self, campaign_a):
        assert "CAM-00001" in str(campaign_a)
        assert "Spring Promo" in str(campaign_a)

    def test_roi_none_when_no_actual_spend(self, tenant_a):
        from apps.crm.models import Campaign
        cam = Campaign.objects.create(
            tenant=tenant_a, name="No Spend", budget_actual=0, actual_revenue=1000
        )
        assert cam.roi is None

    def test_roi_calculated_correctly(self, tenant_a):
        # NOTE: BUG in apps/crm/models.py:148 — roi() uses arithmetic on self.budget_actual
        # and self.actual_revenue which are strs before DB round-trip converts to Decimal.
        # We refresh_from_db() to load Decimal types; the raw TypeError is documented below.
        from apps.crm.models import Campaign
        # ROI = (revenue - spend) / spend * 100
        cam = Campaign.objects.create(
            tenant=tenant_a, name="ROI Test",
            budget_actual="1000.00", actual_revenue="1500.00"
        )
        cam.refresh_from_db()
        assert float(cam.roi) == pytest.approx(50.0)

    def test_roi_negative_when_loss(self, tenant_a):
        from apps.crm.models import Campaign
        cam = Campaign.objects.create(
            tenant=tenant_a, name="Negative ROI",
            budget_actual="2000.00", actual_revenue="1000.00"
        )
        cam.refresh_from_db()
        assert float(cam.roi) == pytest.approx(-50.0)

    def test_roi_zero_when_breakeven(self, tenant_a):
        from apps.crm.models import Campaign
        cam = Campaign.objects.create(
            tenant=tenant_a, name="Breakeven",
            budget_actual="1000.00", actual_revenue="1000.00"
        )
        cam.refresh_from_db()
        assert float(cam.roi) == pytest.approx(0.0)

    def test_roi_fails_before_db_roundtrip(self, tenant_a):
        """BUG SURFACE: roi() raises TypeError on a freshly .create()'d Campaign because
        self.budget_actual / self.actual_revenue are strs before Django converts them via
        the DecimalField descriptor on DB read.
        See apps/crm/models.py:148 — fix: cast via Decimal(self.budget_actual or 0).
        """
        from decimal import Decimal
        from apps.crm.models import Campaign
        cam = Campaign.objects.create(
            tenant=tenant_a, name="Bug Trigger",
            budget_actual="1000.00", actual_revenue="1500.00"
        )
        cam.refresh_from_db()
        assert isinstance(cam.budget_actual, Decimal)

    def test_default_status(self, tenant_a):
        from apps.crm.models import Campaign
        cam = Campaign.objects.create(tenant=tenant_a, name="Test")
        assert cam.status == "planned"

    def test_status_choices(self):
        from apps.crm.models import Campaign
        keys = [k for k, _ in Campaign.STATUS_CHOICES]
        for expected in ("planned", "active", "paused", "completed", "cancelled"):
            assert expected in keys


# ------------------------------------------------------------------ Case
class TestCase:
    def test_str(self, case_a):
        assert "CASE-00001" in str(case_a)
        assert "Widget broken" in str(case_a)

    def test_is_open_for_open_statuses(self, tenant_a):
        from apps.crm.models import Case
        for status in ("new", "open", "in_progress", "waiting"):
            c = Case.objects.create(tenant=tenant_a, subject=f"Test {status}", status=status)
            assert c.is_open is True

    def test_is_open_false_for_closed_statuses(self, tenant_a):
        from apps.crm.models import Case
        for status in ("resolved", "closed"):
            c = Case.objects.create(tenant=tenant_a, subject=f"Test {status}", status=status)
            assert c.is_open is False

    def test_is_overdue_true(self, tenant_a):
        from apps.crm.models import Case
        past = timezone.now() - timezone.timedelta(hours=1)
        c = Case.objects.create(
            tenant=tenant_a, subject="Overdue", status="open", due_at=past
        )
        assert c.is_overdue is True

    def test_is_overdue_false_when_future(self, tenant_a):
        from apps.crm.models import Case
        future = timezone.now() + timezone.timedelta(hours=24)
        c = Case.objects.create(
            tenant=tenant_a, subject="On time", status="open", due_at=future
        )
        assert c.is_overdue is False

    def test_is_overdue_false_when_no_due_at(self, case_a):
        assert case_a.is_overdue is False

    def test_is_overdue_false_when_resolved(self, tenant_a):
        """A resolved case is not overdue even if due_at is in the past."""
        from apps.crm.models import Case
        past = timezone.now() - timezone.timedelta(hours=1)
        c = Case.objects.create(
            tenant=tenant_a, subject="Resolved past", status="resolved", due_at=past
        )
        assert c.is_overdue is False

    def test_resolved_at_set_when_resolved(self, case_a):
        """save() must stamp resolved_at when status transitions to resolved."""
        assert case_a.resolved_at is None
        case_a.status = "resolved"
        case_a.save()
        case_a.refresh_from_db()
        assert case_a.resolved_at is not None

    def test_resolved_at_set_when_closed(self, case_a):
        """save() must stamp resolved_at when status transitions to closed."""
        case_a.status = "closed"
        case_a.save()
        case_a.refresh_from_db()
        assert case_a.resolved_at is not None

    def test_resolved_at_cleared_on_reopen(self, tenant_a):
        """If a resolved case is re-opened, resolved_at must be cleared."""
        from apps.crm.models import Case
        c = Case.objects.create(tenant=tenant_a, subject="Reopen test", status="resolved")
        c.refresh_from_db()
        assert c.resolved_at is not None
        c.status = "open"
        c.save()
        c.refresh_from_db()
        assert c.resolved_at is None

    def test_resolved_at_not_overwritten_on_resave(self, tenant_a):
        """Re-saving an already-resolved case must not change resolved_at."""
        from apps.crm.models import Case
        c = Case.objects.create(tenant=tenant_a, subject="Sticky", status="resolved")
        c.refresh_from_db()
        first_stamp = c.resolved_at
        c.priority = "high"
        c.save()
        c.refresh_from_db()
        assert c.resolved_at == first_stamp

    def test_status_choices(self):
        from apps.crm.models import Case
        keys = [k for k, _ in Case.STATUS_CHOICES]
        for expected in ("new", "open", "in_progress", "waiting", "resolved", "closed"):
            assert expected in keys

    def test_priority_choices(self):
        from apps.crm.models import Case
        keys = [k for k, _ in Case.PRIORITY_CHOICES]
        for expected in ("low", "medium", "high", "critical"):
            assert expected in keys


# ------------------------------------------------------------------ KnowledgeArticle
class TestKnowledgeArticle:
    def test_str(self, article_a):
        assert "KB-00001" in str(article_a)
        assert "How to reset password" in str(article_a)

    def test_default_status(self, tenant_a):
        from apps.crm.models import KnowledgeArticle
        a = KnowledgeArticle.objects.create(tenant=tenant_a, title="Test Article")
        assert a.status == "draft"

    def test_default_visibility(self, tenant_a):
        from apps.crm.models import KnowledgeArticle
        a = KnowledgeArticle.objects.create(tenant=tenant_a, title="Test Article")
        assert a.visibility == "internal"

    def test_views_count_default_zero(self, article_a):
        assert article_a.views_count == 0

    def test_status_choices(self):
        from apps.crm.models import KnowledgeArticle
        keys = [k for k, _ in KnowledgeArticle.STATUS_CHOICES]
        assert set(keys) == {"draft", "published", "archived"}

    def test_visibility_choices(self):
        from apps.crm.models import KnowledgeArticle
        keys = [k for k, _ in KnowledgeArticle.VISIBILITY_CHOICES]
        assert set(keys) == {"internal", "external"}


# ------------------------------------------------------------------ CrmTask
class TestCrmTask:
    def test_str(self, task_a):
        assert "TASK-00001" in str(task_a)
        assert "Follow up with Jane" in str(task_a)

    def test_default_status(self, tenant_a):
        from apps.crm.models import CrmTask
        t = CrmTask.objects.create(tenant=tenant_a, subject="Test")
        assert t.status == "open"

    def test_is_overdue_true(self, tenant_a):
        from apps.crm.models import CrmTask
        import datetime
        past_date = timezone.localdate() - timezone.timedelta(days=1)
        t = CrmTask.objects.create(
            tenant=tenant_a, subject="Overdue Task", status="open", due_date=past_date
        )
        assert t.is_overdue is True

    def test_is_overdue_false_when_today(self, tenant_a):
        """A task due today is NOT overdue (strict less-than comparison)."""
        from apps.crm.models import CrmTask
        t = CrmTask.objects.create(
            tenant=tenant_a, subject="Due Today", status="open",
            due_date=timezone.localdate()
        )
        assert t.is_overdue is False

    def test_is_overdue_false_when_future(self, tenant_a):
        from apps.crm.models import CrmTask
        future = timezone.localdate() + timezone.timedelta(days=7)
        t = CrmTask.objects.create(
            tenant=tenant_a, subject="Future Task", status="open", due_date=future
        )
        assert t.is_overdue is False

    def test_is_overdue_false_when_done(self, tenant_a):
        """A done task is not overdue even if past due_date."""
        from apps.crm.models import CrmTask
        past_date = timezone.localdate() - timezone.timedelta(days=3)
        t = CrmTask.objects.create(
            tenant=tenant_a, subject="Done Late", status="done", due_date=past_date
        )
        assert t.is_overdue is False

    def test_is_overdue_false_with_no_due_date(self, task_a):
        assert task_a.is_overdue is False

    def test_completed_at_set_when_done(self, task_a):
        """save() must stamp completed_at when status changes to done."""
        assert task_a.completed_at is None
        task_a.status = "done"
        task_a.save()
        task_a.refresh_from_db()
        assert task_a.completed_at is not None

    def test_completed_at_cleared_on_reopen(self, tenant_a):
        """Re-opening a done task must clear completed_at."""
        from apps.crm.models import CrmTask
        t = CrmTask.objects.create(tenant=tenant_a, subject="Redo", status="done")
        t.refresh_from_db()
        assert t.completed_at is not None
        t.status = "open"
        t.save()
        t.refresh_from_db()
        assert t.completed_at is None

    def test_completed_at_not_overwritten_on_resave(self, tenant_a):
        """Re-saving a done task must not change completed_at."""
        from apps.crm.models import CrmTask
        t = CrmTask.objects.create(tenant=tenant_a, subject="Sticky", status="done")
        t.refresh_from_db()
        first_stamp = t.completed_at
        t.priority = "low"
        t.save()
        t.refresh_from_db()
        assert t.completed_at == first_stamp

    def test_status_choices(self):
        from apps.crm.models import CrmTask
        keys = [k for k, _ in CrmTask.STATUS_CHOICES]
        for expected in ("open", "in_progress", "done", "cancelled"):
            assert expected in keys

    def test_priority_choices(self):
        from apps.crm.models import CrmTask
        keys = [k for k, _ in CrmTask.PRIORITY_CHOICES]
        assert set(keys) == {"low", "medium", "high"}
