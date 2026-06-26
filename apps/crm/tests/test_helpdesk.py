"""Tests for CRM §1.4 Customer Service & Support (Help Desk) sub-module.

Covers: SlaPolicy, Case (enhanced), CaseComment, KnowledgeArticle, KbCategory,
CustomerPortalAccess — models, forms, views, public/portal endpoints, and
multi-tenant IDOR isolation.
"""
import pytest
from datetime import timedelta
from decimal import Decimal
from django.urls import reverse
from django.test import Client
from django.utils import timezone

pytestmark = pytest.mark.django_db


# =================================================================== Fixtures

@pytest.fixture
def party_a(db, tenant_a):
    """An organization Party for tenant_a (used as the case account)."""
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_a, kind="organization", name="Acme Client")


@pytest.fixture
def party_b(db, tenant_b):
    """An organization Party for tenant_b."""
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_b, kind="organization", name="Globex Client")


@pytest.fixture
def sla_a(db, tenant_a):
    """An SlaPolicy for tenant_a with known per-priority targets."""
    from apps.crm.models import SlaPolicy
    return SlaPolicy.objects.create(
        tenant=tenant_a,
        name="Standard SLA",
        is_active=True,
        is_default=True,
        response_low=48,
        response_medium=24,
        response_high=8,
        response_critical=2,
        resolution_low=240,
        resolution_medium=120,
        resolution_high=48,
        resolution_critical=8,
    )


@pytest.fixture
def sla_b(db, tenant_b):
    """An SlaPolicy for tenant_b."""
    from apps.crm.models import SlaPolicy
    return SlaPolicy.objects.create(
        tenant=tenant_b,
        name="Globex SLA",
        is_active=True,
    )


@pytest.fixture
def case_a(db, tenant_a, party_a):
    """A basic Case for tenant_a."""
    from apps.crm.models import Case
    return Case.objects.create(
        tenant=tenant_a,
        subject="Widget broken",
        priority="medium",
        status="new",
        account=party_a,
    )


@pytest.fixture
def case_b(db, tenant_b, party_b):
    """A Case for tenant_b."""
    from apps.crm.models import Case
    return Case.objects.create(
        tenant=tenant_b,
        subject="Globex issue",
        status="new",
        account=party_b,
    )


@pytest.fixture
def kb_cat_a(db, tenant_a):
    """A KbCategory for tenant_a."""
    from apps.crm.models import KbCategory
    return KbCategory.objects.create(
        tenant=tenant_a,
        name="FAQs",
        is_active=True,
    )


@pytest.fixture
def kb_cat_b(db, tenant_b):
    from apps.crm.models import KbCategory
    return KbCategory.objects.create(
        tenant=tenant_b,
        name="Globex FAQs",
        is_active=True,
    )


@pytest.fixture
def article_a(db, tenant_a, kb_cat_a):
    """A published + external KB article for tenant_a (is_public=True)."""
    from apps.crm.models import KnowledgeArticle
    return KnowledgeArticle.objects.create(
        tenant=tenant_a,
        title="How to reset password",
        status="published",
        visibility="external",
        kb_category=kb_cat_a,
    )


@pytest.fixture
def article_draft(db, tenant_a):
    """A draft KB article for tenant_a."""
    from apps.crm.models import KnowledgeArticle
    return KnowledgeArticle.objects.create(
        tenant=tenant_a,
        title="Draft article",
        status="draft",
        visibility="external",
    )


@pytest.fixture
def article_internal(db, tenant_a):
    """A published but internal KB article — not publicly accessible."""
    from apps.crm.models import KnowledgeArticle
    return KnowledgeArticle.objects.create(
        tenant=tenant_a,
        title="Internal guide",
        status="published",
        visibility="internal",
    )


@pytest.fixture
def article_b(db, tenant_b):
    from apps.crm.models import KnowledgeArticle
    return KnowledgeArticle.objects.create(
        tenant=tenant_b,
        title="Globex FAQ",
        status="published",
        visibility="external",
    )


@pytest.fixture
def portal_user_a(db, tenant_a):
    """A User that will be the portal_user for tenant_a's CustomerPortalAccess."""
    from apps.accounts.models import User
    return User.objects.create_user(
        email="portal@acme.com",
        username="portal_acme",
        password="TestPass123!",
        tenant=tenant_a,
        is_tenant_admin=False,
    )


@pytest.fixture
def portal_access_a(db, tenant_a, party_a, portal_user_a):
    """A CustomerPortalAccess linking portal_user_a → party_a."""
    from apps.crm.models import CustomerPortalAccess
    return CustomerPortalAccess.objects.create(
        tenant=tenant_a,
        customer_party=party_a,
        portal_user=portal_user_a,
        can_submit_cases=True,
        is_active=True,
    )


@pytest.fixture
def portal_client_a(db, portal_user_a):
    """A test Client logged in as the portal user (not the admin)."""
    c = Client()
    c.force_login(portal_user_a)
    return c


# =================================================================== MODEL INVARIANTS

class TestSlaPolicyModel:
    def test_number_format(self, tenant_a):
        from apps.crm.models import SlaPolicy
        s = SlaPolicy.objects.create(tenant=tenant_a, name="Basic")
        assert s.number == "SLA-00001"

    def test_sequential_per_tenant(self, tenant_a):
        from apps.crm.models import SlaPolicy
        s1 = SlaPolicy.objects.create(tenant=tenant_a, name="Basic")
        s2 = SlaPolicy.objects.create(tenant=tenant_a, name="Premium")
        assert s1.number == "SLA-00001"
        assert s2.number == "SLA-00002"

    def test_per_tenant_isolation(self, tenant_a, tenant_b):
        from apps.crm.models import SlaPolicy
        a = SlaPolicy.objects.create(tenant=tenant_a, name="A")
        b = SlaPolicy.objects.create(tenant=tenant_b, name="B")
        assert a.number == "SLA-00001"
        assert b.number == "SLA-00001"

    def test_str_format(self, sla_a):
        s = str(sla_a)
        assert "SLA-00001" in s
        assert "Standard SLA" in s

    def test_targets_for_low(self, sla_a):
        resp_h, res_h = sla_a.targets_for("low")
        assert resp_h == 48
        assert res_h == 240

    def test_targets_for_medium(self, sla_a):
        resp_h, res_h = sla_a.targets_for("medium")
        assert resp_h == 24
        assert res_h == 120

    def test_targets_for_high(self, sla_a):
        resp_h, res_h = sla_a.targets_for("high")
        assert resp_h == 8
        assert res_h == 48

    def test_targets_for_critical(self, sla_a):
        resp_h, res_h = sla_a.targets_for("critical")
        assert resp_h == 2
        assert res_h == 8

    def test_targets_for_unknown_priority_returns_none(self, sla_a):
        resp_h, res_h = sla_a.targets_for("bogus")
        assert resp_h is None
        assert res_h is None

    def test_unique_together_tenant_number(self, tenant_a):
        from apps.crm.models import SlaPolicy
        from django.db import IntegrityError
        SlaPolicy.objects.create(tenant=tenant_a, name="First")
        with pytest.raises(IntegrityError):
            SlaPolicy.objects.create(tenant=tenant_a, name="Dup", number="SLA-00001")

    def test_is_active_default(self, tenant_a):
        from apps.crm.models import SlaPolicy
        s = SlaPolicy.objects.create(tenant=tenant_a, name="X")
        assert s.is_active is True


class TestCaseSave:
    """Case.save() SLA, closed_at, resolved_at, and public_token logic."""

    def test_public_token_generated_on_create(self, case_a):
        assert case_a.public_token is not None
        assert len(case_a.public_token) > 10

    def test_public_token_generated_once(self, case_a):
        """Editing a case must NOT regenerate the public_token."""
        original_token = case_a.public_token
        case_a.subject = "Updated subject"
        case_a.save()
        case_a.refresh_from_db()
        assert case_a.public_token == original_token

    def test_public_token_unique(self, tenant_a):
        """Two cases must have distinct tokens."""
        from apps.crm.models import Case
        c1 = Case.objects.create(tenant=tenant_a, subject="C1")
        c2 = Case.objects.create(tenant=tenant_a, subject="C2")
        assert c1.public_token != c2.public_token

    def test_sla_due_times_computed_on_create(self, tenant_a, sla_a):
        """When an sla_policy is set, first_response_due + resolution_due are auto-computed."""
        from apps.crm.models import Case
        before = timezone.now()
        c = Case.objects.create(
            tenant=tenant_a, subject="SLA test",
            priority="medium", status="new", sla_policy=sla_a)
        c.refresh_from_db()
        # medium: response=24h, resolution=120h
        assert c.first_response_due is not None
        assert c.resolution_due is not None
        # Both due times should be roughly 24h and 120h after creation (± 5 seconds)
        expected_resp = before + timedelta(hours=24)
        expected_res = before + timedelta(hours=120)
        assert abs((c.first_response_due - expected_resp).total_seconds()) < 5
        assert abs((c.resolution_due - expected_res).total_seconds()) < 5

    def test_sla_due_times_anchored_at_created_at(self, tenant_a, sla_a):
        """first_response_due and resolution_due use created_at as the anchor."""
        from apps.crm.models import Case
        c = Case.objects.create(
            tenant=tenant_a, subject="Anchored SLA",
            priority="high", status="new", sla_policy=sla_a)
        c.refresh_from_db()
        # high: response=8h, resolution=48h
        expected_resp = c.created_at + timedelta(hours=8)
        expected_res = c.created_at + timedelta(hours=48)
        assert abs((c.first_response_due - expected_resp).total_seconds()) < 2
        assert abs((c.resolution_due - expected_res).total_seconds()) < 2

    def test_sla_due_computed_once_not_recomputed_on_edit(self, tenant_a, sla_a):
        """Editing a case (changing priority) must NOT recompute already-set due times."""
        from apps.crm.models import Case
        c = Case.objects.create(
            tenant=tenant_a, subject="SLA once",
            priority="low", status="new", sla_policy=sla_a)
        c.refresh_from_db()
        original_resp_due = c.first_response_due
        original_res_due = c.resolution_due
        # Change priority — should not recompute since both dues already set
        c.priority = "critical"
        c.save()
        c.refresh_from_db()
        assert c.first_response_due == original_resp_due
        assert c.resolution_due == original_res_due

    def test_sla_not_computed_without_policy(self, tenant_a):
        """Without an sla_policy, due times remain null."""
        from apps.crm.models import Case
        c = Case.objects.create(tenant=tenant_a, subject="No SLA", status="new")
        assert c.first_response_due is None
        assert c.resolution_due is None

    def test_closed_at_stamped_when_closed(self, case_a):
        case_a.status = "closed"
        case_a.save()
        case_a.refresh_from_db()
        assert case_a.closed_at is not None

    def test_closed_at_stamped_once(self, case_a):
        """closed_at must NOT be overwritten on re-save when already closed."""
        case_a.status = "closed"
        case_a.save()
        case_a.refresh_from_db()
        first_closed = case_a.closed_at
        case_a.description = "still closed"
        case_a.save()
        case_a.refresh_from_db()
        assert case_a.closed_at == first_closed

    def test_closed_at_cleared_when_reopened(self, case_a):
        """Re-opening a closed case must clear closed_at."""
        case_a.status = "closed"
        case_a.save()
        case_a.refresh_from_db()
        assert case_a.closed_at is not None
        # Reopen
        case_a = type(case_a).objects.get(pk=case_a.pk)
        case_a.status = "open"
        case_a.save()
        case_a.refresh_from_db()
        assert case_a.closed_at is None

    def test_resolved_at_stamped_on_resolved(self, case_a):
        case_a.status = "resolved"
        case_a.save()
        case_a.refresh_from_db()
        assert case_a.resolved_at is not None

    def test_resolved_at_stamped_on_closed(self, case_a):
        case_a.status = "closed"
        case_a.save()
        case_a.refresh_from_db()
        assert case_a.resolved_at is not None

    def test_resolved_at_cleared_when_reopened(self, case_a):
        case_a.status = "resolved"
        case_a.save()
        case_a.refresh_from_db()
        assert case_a.resolved_at is not None
        case_a = type(case_a).objects.get(pk=case_a.pk)
        case_a.status = "in_progress"
        case_a.save()
        case_a.refresh_from_db()
        assert case_a.resolved_at is None

    def test_number_format(self, tenant_a):
        from apps.crm.models import Case
        c = Case.objects.create(tenant=tenant_a, subject="First case")
        assert c.number == "CASE-00001"

    def test_sequential_per_tenant(self, tenant_a):
        from apps.crm.models import Case
        c1 = Case.objects.create(tenant=tenant_a, subject="A")
        c2 = Case.objects.create(tenant=tenant_a, subject="B")
        assert c1.number == "CASE-00001"
        assert c2.number == "CASE-00002"

    def test_per_tenant_isolation(self, tenant_a, tenant_b):
        from apps.crm.models import Case
        a = Case.objects.create(tenant=tenant_a, subject="A")
        b = Case.objects.create(tenant=tenant_b, subject="B")
        assert a.number == "CASE-00001"
        assert b.number == "CASE-00001"

    def test_str_format(self, case_a):
        s = str(case_a)
        assert "CASE-00001" in s
        assert "Widget broken" in s

    def test_unique_together_tenant_number(self, tenant_a):
        from apps.crm.models import Case
        from django.db import IntegrityError
        Case.objects.create(tenant=tenant_a, subject="First")
        with pytest.raises(IntegrityError):
            Case.objects.create(tenant=tenant_a, subject="Dup", number="CASE-00001")


class TestCaseProperties:
    def test_is_open_true_for_open_statuses(self, tenant_a):
        from apps.crm.models import Case
        for st in ["new", "open", "in_progress", "waiting"]:
            c = Case(tenant=tenant_a, subject="x", status=st)
            assert c.is_open is True, f"Expected is_open for status={st}"

    def test_is_open_false_for_resolved_and_closed(self, tenant_a):
        from apps.crm.models import Case
        for st in ["resolved", "closed"]:
            c = Case(tenant=tenant_a, subject="x", status=st)
            assert c.is_open is False, f"Expected not is_open for status={st}"

    def test_is_response_overdue_when_past_due_and_not_responded(self, tenant_a, sla_a):
        """Past first_response_due + no first_responded_at + open → overdue."""
        from apps.crm.models import Case
        past = timezone.now() - timedelta(hours=1)
        c = Case(
            tenant=tenant_a, subject="x", status="open",
            first_response_due=past, first_responded_at=None,
        )
        assert c.is_response_overdue is True

    def test_is_response_overdue_false_when_responded(self, tenant_a):
        """Already responded → not overdue."""
        from apps.crm.models import Case
        past = timezone.now() - timedelta(hours=1)
        c = Case(
            tenant=tenant_a, subject="x", status="open",
            first_response_due=past,
            first_responded_at=timezone.now() - timedelta(minutes=30),
        )
        assert c.is_response_overdue is False

    def test_is_response_overdue_false_when_future_due(self, tenant_a):
        from apps.crm.models import Case
        future = timezone.now() + timedelta(hours=10)
        c = Case(tenant=tenant_a, subject="x", status="open", first_response_due=future)
        assert c.is_response_overdue is False

    def test_is_response_overdue_false_when_closed(self, tenant_a):
        from apps.crm.models import Case
        past = timezone.now() - timedelta(hours=1)
        c = Case(tenant=tenant_a, subject="x", status="closed", first_response_due=past)
        assert c.is_response_overdue is False

    def test_is_resolution_overdue_when_past_due_and_open(self, tenant_a):
        from apps.crm.models import Case
        past = timezone.now() - timedelta(hours=1)
        c = Case(tenant=tenant_a, subject="x", status="open", resolution_due=past)
        assert c.is_resolution_overdue is True

    def test_is_resolution_overdue_false_when_future(self, tenant_a):
        from apps.crm.models import Case
        future = timezone.now() + timedelta(hours=10)
        c = Case(tenant=tenant_a, subject="x", status="open", resolution_due=future)
        assert c.is_resolution_overdue is False

    def test_is_resolution_overdue_false_when_closed(self, tenant_a):
        from apps.crm.models import Case
        past = timezone.now() - timedelta(hours=1)
        c = Case(tenant=tenant_a, subject="x", status="closed", resolution_due=past)
        assert c.is_resolution_overdue is False

    def test_is_overdue_uses_resolution_due(self, tenant_a):
        from apps.crm.models import Case
        past = timezone.now() - timedelta(hours=1)
        c = Case(tenant=tenant_a, subject="x", status="open", resolution_due=past)
        assert c.is_overdue is True

    def test_is_overdue_falls_back_to_due_at(self, tenant_a):
        from apps.crm.models import Case
        past = timezone.now() - timedelta(hours=1)
        c = Case(tenant=tenant_a, subject="x", status="open", due_at=past, resolution_due=None)
        assert c.is_overdue is True

    def test_is_overdue_false_when_future_due_at(self, tenant_a):
        from apps.crm.models import Case
        future = timezone.now() + timedelta(hours=5)
        c = Case(tenant=tenant_a, subject="x", status="open", due_at=future)
        assert c.is_overdue is False

    def test_is_overdue_false_when_no_deadline(self, case_a):
        assert case_a.is_overdue is False


class TestKnowledgeArticleModel:
    def test_number_format(self, tenant_a):
        from apps.crm.models import KnowledgeArticle
        a = KnowledgeArticle.objects.create(tenant=tenant_a, title="First")
        assert a.number == "KB-00001"

    def test_sequential_per_tenant(self, tenant_a):
        from apps.crm.models import KnowledgeArticle
        a1 = KnowledgeArticle.objects.create(tenant=tenant_a, title="A")
        a2 = KnowledgeArticle.objects.create(tenant=tenant_a, title="B")
        assert a1.number == "KB-00001"
        assert a2.number == "KB-00002"

    def test_per_tenant_isolation(self, tenant_a, tenant_b):
        from apps.crm.models import KnowledgeArticle
        a = KnowledgeArticle.objects.create(tenant=tenant_a, title="A")
        b = KnowledgeArticle.objects.create(tenant=tenant_b, title="B")
        assert a.number == "KB-00001"
        assert b.number == "KB-00001"

    def test_str_format(self, article_a):
        s = str(article_a)
        assert "KB-00001" in s
        assert "How to reset password" in s

    def test_public_token_generated_on_create(self, article_a):
        assert article_a.public_token is not None
        assert len(article_a.public_token) > 10

    def test_public_token_generated_once(self, article_a):
        """Re-saving must not regenerate the public token."""
        original_token = article_a.public_token
        article_a.title = "Updated"
        article_a.save()
        article_a.refresh_from_db()
        assert article_a.public_token == original_token

    def test_is_public_true_when_published_external(self, article_a):
        assert article_a.is_public is True

    def test_is_public_false_when_draft(self, article_draft):
        assert article_draft.is_public is False

    def test_is_public_false_when_internal(self, article_internal):
        assert article_internal.is_public is False

    def test_is_public_false_when_archived(self, tenant_a):
        from apps.crm.models import KnowledgeArticle
        a = KnowledgeArticle.objects.create(
            tenant=tenant_a, title="Archived",
            status="archived", visibility="external")
        assert a.is_public is False

    def test_unique_together_tenant_number(self, tenant_a):
        from apps.crm.models import KnowledgeArticle
        from django.db import IntegrityError
        KnowledgeArticle.objects.create(tenant=tenant_a, title="First")
        with pytest.raises(IntegrityError):
            KnowledgeArticle.objects.create(tenant=tenant_a, title="Dup", number="KB-00001")

    def test_status_choices(self):
        from apps.crm.models import KnowledgeArticle
        keys = [k for k, _ in KnowledgeArticle.STATUS_CHOICES]
        assert set(keys) == {"draft", "published", "archived"}

    def test_visibility_choices(self):
        from apps.crm.models import KnowledgeArticle
        keys = [k for k, _ in KnowledgeArticle.VISIBILITY_CHOICES]
        assert set(keys) == {"internal", "external"}


class TestKbCategoryModel:
    def test_number_format(self, tenant_a):
        from apps.crm.models import KbCategory
        c = KbCategory.objects.create(tenant=tenant_a, name="General")
        assert c.number == "KBC-00001"

    def test_sequential_per_tenant(self, tenant_a):
        from apps.crm.models import KbCategory
        c1 = KbCategory.objects.create(tenant=tenant_a, name="A")
        c2 = KbCategory.objects.create(tenant=tenant_a, name="B")
        assert c1.number == "KBC-00001"
        assert c2.number == "KBC-00002"

    def test_per_tenant_isolation(self, tenant_a, tenant_b):
        from apps.crm.models import KbCategory
        a = KbCategory.objects.create(tenant=tenant_a, name="A")
        b = KbCategory.objects.create(tenant=tenant_b, name="B")
        assert a.number == "KBC-00001"
        assert b.number == "KBC-00001"

    def test_str_format(self, kb_cat_a):
        s = str(kb_cat_a)
        assert "KBC-00001" in s
        assert "FAQs" in s

    def test_is_active_default(self, tenant_a):
        from apps.crm.models import KbCategory
        c = KbCategory.objects.create(tenant=tenant_a, name="X")
        assert c.is_active is True

    def test_parent_relationship(self, tenant_a, kb_cat_a):
        """Child category can reference a parent."""
        from apps.crm.models import KbCategory
        child = KbCategory.objects.create(
            tenant=tenant_a, name="Sub-FAQ", parent=kb_cat_a)
        assert child.parent_id == kb_cat_a.pk

    def test_unique_together_tenant_number(self, tenant_a):
        from apps.crm.models import KbCategory
        from django.db import IntegrityError
        KbCategory.objects.create(tenant=tenant_a, name="First")
        with pytest.raises(IntegrityError):
            KbCategory.objects.create(tenant=tenant_a, name="Dup", number="KBC-00001")


class TestCustomerPortalAccessModel:
    def test_number_format(self, tenant_a, portal_user_a):
        from apps.crm.models import CustomerPortalAccess
        c = CustomerPortalAccess.objects.create(tenant=tenant_a, portal_user=portal_user_a)
        assert c.number == "CSP-00001"

    def test_sequential_per_tenant(self, tenant_a, admin_user, portal_user_a):
        from apps.crm.models import CustomerPortalAccess
        # Need two separate users for two records (portal_user is OneToOne)
        c1 = CustomerPortalAccess.objects.create(tenant=tenant_a, portal_user=portal_user_a)
        c2 = CustomerPortalAccess.objects.create(tenant=tenant_a, portal_user=admin_user)
        assert c1.number == "CSP-00001"
        assert c2.number == "CSP-00002"

    def test_per_tenant_isolation(self, tenant_a, tenant_b, portal_user_a, admin_b):
        from apps.crm.models import CustomerPortalAccess
        a = CustomerPortalAccess.objects.create(tenant=tenant_a, portal_user=portal_user_a)
        b = CustomerPortalAccess.objects.create(tenant=tenant_b, portal_user=admin_b)
        assert a.number == "CSP-00001"
        assert b.number == "CSP-00001"

    def test_str_format(self, portal_access_a, party_a):
        s = str(portal_access_a)
        assert "CSP-00001" in s
        assert party_a.name in s

    def test_str_fallback_no_party(self, tenant_a, portal_user_a):
        from apps.crm.models import CustomerPortalAccess
        c = CustomerPortalAccess.objects.create(tenant=tenant_a, portal_user=portal_user_a)
        assert "Customer" in str(c)

    def test_is_active_default(self, tenant_a, portal_user_a):
        from apps.crm.models import CustomerPortalAccess
        c = CustomerPortalAccess.objects.create(tenant=tenant_a, portal_user=portal_user_a)
        assert c.is_active is True

    def test_can_submit_cases_default(self, tenant_a, portal_user_a):
        from apps.crm.models import CustomerPortalAccess
        c = CustomerPortalAccess.objects.create(tenant=tenant_a, portal_user=portal_user_a)
        assert c.can_submit_cases is True

    def test_unique_together_tenant_number(self, tenant_a, portal_user_a, admin_user):
        from apps.crm.models import CustomerPortalAccess
        from django.db import IntegrityError
        CustomerPortalAccess.objects.create(tenant=tenant_a, portal_user=portal_user_a)
        with pytest.raises(IntegrityError):
            CustomerPortalAccess.objects.create(
                tenant=tenant_a, portal_user=admin_user, number="CSP-00001")


class TestCaseCommentModel:
    def test_is_public_default_false(self, case_a, tenant_a, admin_user):
        from apps.crm.models import CaseComment
        c = CaseComment.objects.create(
            tenant=tenant_a, case=case_a, author=admin_user, body="Note")
        assert c.is_public is False

    def test_str_internal(self, case_a, tenant_a, admin_user):
        from apps.crm.models import CaseComment
        c = CaseComment.objects.create(
            tenant=tenant_a, case=case_a, author=admin_user, body="internal note")
        assert "internal" in str(c)

    def test_str_public(self, case_a, tenant_a, admin_user):
        from apps.crm.models import CaseComment
        c = CaseComment.objects.create(
            tenant=tenant_a, case=case_a, author=admin_user,
            body="public reply", is_public=True)
        assert "public" in str(c)

    def test_ordering_by_created_at(self, case_a, tenant_a, admin_user):
        """Comments must be returned in chronological order."""
        from apps.crm.models import CaseComment
        c1 = CaseComment.objects.create(
            tenant=tenant_a, case=case_a, author=admin_user, body="First")
        c2 = CaseComment.objects.create(
            tenant=tenant_a, case=case_a, author=admin_user, body="Second")
        pks = list(CaseComment.objects.filter(case=case_a).values_list("pk", flat=True))
        assert pks.index(c1.pk) < pks.index(c2.pk)


# =================================================================== FORM SECURITY

class TestCaseFormExclusions:
    """System-managed fields must be absent from CaseForm."""

    def test_first_response_due_excluded(self, tenant_a):
        from apps.crm.forms import CaseForm
        form = CaseForm(tenant=tenant_a)
        assert "first_response_due" not in form.fields

    def test_first_responded_at_excluded(self, tenant_a):
        from apps.crm.forms import CaseForm
        form = CaseForm(tenant=tenant_a)
        assert "first_responded_at" not in form.fields

    def test_resolution_due_excluded(self, tenant_a):
        from apps.crm.forms import CaseForm
        form = CaseForm(tenant=tenant_a)
        assert "resolution_due" not in form.fields

    def test_closed_at_excluded(self, tenant_a):
        from apps.crm.forms import CaseForm
        form = CaseForm(tenant=tenant_a)
        assert "closed_at" not in form.fields

    def test_public_token_excluded(self, tenant_a):
        from apps.crm.forms import CaseForm
        form = CaseForm(tenant=tenant_a)
        assert "public_token" not in form.fields

    def test_satisfaction_rating_excluded(self, tenant_a):
        from apps.crm.forms import CaseForm
        form = CaseForm(tenant=tenant_a)
        assert "satisfaction_rating" not in form.fields

    def test_satisfaction_comment_excluded(self, tenant_a):
        from apps.crm.forms import CaseForm
        form = CaseForm(tenant=tenant_a)
        assert "satisfaction_comment" not in form.fields

    def test_satisfaction_at_excluded(self, tenant_a):
        from apps.crm.forms import CaseForm
        form = CaseForm(tenant=tenant_a)
        assert "satisfaction_at" not in form.fields

    def test_resolved_at_excluded(self, tenant_a):
        from apps.crm.forms import CaseForm
        form = CaseForm(tenant=tenant_a)
        assert "resolved_at" not in form.fields

    def test_tenant_excluded(self, tenant_a):
        from apps.crm.forms import CaseForm
        form = CaseForm(tenant=tenant_a)
        assert "tenant" not in form.fields

    def test_number_excluded(self, tenant_a):
        from apps.crm.forms import CaseForm
        form = CaseForm(tenant=tenant_a)
        assert "number" not in form.fields

    def test_subject_is_required(self, tenant_a):
        from apps.crm.forms import CaseForm
        form = CaseForm(tenant=tenant_a, data={})
        assert not form.is_valid()
        assert "subject" in form.errors

    def test_cross_tenant_sla_policy_rejected(self, tenant_a, sla_b):
        """CaseForm must reject an sla_policy from another tenant."""
        from apps.crm.forms import CaseForm
        form = CaseForm(
            tenant=tenant_a,
            data={
                "subject": "Injected",
                "type": "question",
                "priority": "medium",
                "status": "new",
                "origin": "email",
                "sla_policy": str(sla_b.pk),  # cross-tenant FK
            }
        )
        assert not form.is_valid()
        assert "sla_policy" in form.errors


class TestKnowledgeArticleFormExclusions:
    def test_helpful_count_excluded(self, tenant_a):
        from apps.crm.forms import KnowledgeArticleForm
        form = KnowledgeArticleForm(tenant=tenant_a)
        assert "helpful_count" not in form.fields

    def test_not_helpful_count_excluded(self, tenant_a):
        from apps.crm.forms import KnowledgeArticleForm
        form = KnowledgeArticleForm(tenant=tenant_a)
        assert "not_helpful_count" not in form.fields

    def test_public_token_excluded(self, tenant_a):
        from apps.crm.forms import KnowledgeArticleForm
        form = KnowledgeArticleForm(tenant=tenant_a)
        assert "public_token" not in form.fields

    def test_views_count_excluded(self, tenant_a):
        from apps.crm.forms import KnowledgeArticleForm
        form = KnowledgeArticleForm(tenant=tenant_a)
        assert "views_count" not in form.fields

    def test_tenant_excluded(self, tenant_a):
        from apps.crm.forms import KnowledgeArticleForm
        form = KnowledgeArticleForm(tenant=tenant_a)
        assert "tenant" not in form.fields

    def test_number_excluded(self, tenant_a):
        from apps.crm.forms import KnowledgeArticleForm
        form = KnowledgeArticleForm(tenant=tenant_a)
        assert "number" not in form.fields


class TestKbCategoryFormSelfParentExclusion:
    """KbCategoryForm must exclude the category itself from the parent queryset on edit."""

    def test_self_excluded_from_parent_on_edit(self, kb_cat_a):
        from apps.crm.forms import KbCategoryForm
        form = KbCategoryForm(tenant=kb_cat_a.tenant, instance=kb_cat_a)
        parent_pks = list(form.fields["parent"].queryset.values_list("pk", flat=True))
        assert kb_cat_a.pk not in parent_pks

    def test_self_not_excluded_on_create(self, tenant_a, kb_cat_a):
        """On a new (unsaved) form, the full queryset is available."""
        from apps.crm.forms import KbCategoryForm
        form = KbCategoryForm(tenant=tenant_a)
        parent_pks = list(form.fields["parent"].queryset.values_list("pk", flat=True))
        # kb_cat_a should be in the queryset on a fresh form
        assert kb_cat_a.pk in parent_pks


class TestCustomerPortalAccessFormExclusions:
    def test_accepted_at_excluded(self, tenant_a):
        from apps.crm.forms import CustomerPortalAccessForm
        form = CustomerPortalAccessForm(tenant=tenant_a)
        assert "accepted_at" not in form.fields

    def test_tenant_excluded(self, tenant_a):
        from apps.crm.forms import CustomerPortalAccessForm
        form = CustomerPortalAccessForm(tenant=tenant_a)
        assert "tenant" not in form.fields

    def test_number_excluded(self, tenant_a):
        from apps.crm.forms import CustomerPortalAccessForm
        form = CustomerPortalAccessForm(tenant=tenant_a)
        assert "number" not in form.fields

    def test_cross_tenant_customer_party_rejected(self, tenant_a, party_b):
        """CustomerPortalAccessForm must reject a customer_party from another tenant."""
        from apps.crm.forms import CustomerPortalAccessForm
        form = CustomerPortalAccessForm(
            tenant=tenant_a,
            data={
                "customer_party": str(party_b.pk),  # cross-tenant FK injection
                "can_submit_cases": True,
                "is_active": True,
            }
        )
        assert not form.is_valid()
        assert "customer_party" in form.errors


# =================================================================== VIEWS / CRUD

class TestCaseViews:
    def test_list_200(self, client_a, case_a):
        resp = client_a.get(reverse("crm:case_list"))
        assert resp.status_code == 200

    def test_list_shows_own_case(self, client_a, case_a):
        resp = client_a.get(reverse("crm:case_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert case_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, case_a, case_b):
        resp = client_a.get(reverse("crm:case_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert case_b.pk not in pks

    def test_detail_200(self, client_a, case_a):
        resp = client_a.get(reverse("crm:case_detail", args=[case_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_obj(self, client_a, case_a):
        resp = client_a.get(reverse("crm:case_detail", args=[case_a.pk]))
        assert resp.context["obj"].pk == case_a.pk

    def test_create_get_200(self, client_a):
        resp = client_a.get(reverse("crm:case_create"))
        assert resp.status_code == 200

    def test_create_post_persists_with_tenant(self, client_a, tenant_a):
        from apps.crm.models import Case
        resp = client_a.post(reverse("crm:case_create"), {
            "subject": "New ticket",
            "type": "question",
            "priority": "low",
            "status": "new",
            "origin": "email",
        })
        assert resp.status_code == 302
        c = Case.objects.filter(tenant=tenant_a, subject="New ticket").first()
        assert c is not None
        assert c.number.startswith("CASE-")

    def test_edit_get_200(self, client_a, case_a):
        resp = client_a.get(reverse("crm:case_edit", args=[case_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates(self, client_a, case_a):
        resp = client_a.post(reverse("crm:case_edit", args=[case_a.pk]), {
            "subject": "Widget fixed",
            "type": "problem",
            "priority": "high",
            "status": "open",
            "origin": "email",
        })
        assert resp.status_code == 302
        case_a.refresh_from_db()
        assert case_a.subject == "Widget fixed"

    def test_delete_removes_record(self, client_a, case_a):
        from apps.crm.models import Case
        pk = case_a.pk
        resp = client_a.post(reverse("crm:case_delete", args=[pk]))
        assert resp.status_code == 302
        assert not Case.objects.filter(pk=pk).exists()

    def test_anon_redirected(self, client):
        resp = client.get(reverse("crm:case_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_detail_shows_comment_form(self, client_a, case_a):
        resp = client_a.get(reverse("crm:case_detail", args=[case_a.pk]))
        assert "comment_form" in resp.context


class TestCaseCommentAdd:
    """case_comment_add: first-response SLA clock behaviour."""

    def test_internal_comment_does_not_stamp_first_responded_at(self, client_a, case_a):
        from apps.crm.models import Case
        resp = client_a.post(
            reverse("crm:case_comment_add", args=[case_a.pk]),
            {"body": "Internal note", "is_public": ""},  # is_public unchecked
        )
        assert resp.status_code == 302
        case_a.refresh_from_db()
        assert case_a.first_responded_at is None

    def test_first_public_reply_stamps_first_responded_at(self, client_a, case_a):
        from apps.crm.models import Case
        assert case_a.first_responded_at is None
        client_a.post(
            reverse("crm:case_comment_add", args=[case_a.pk]),
            {"body": "Hi customer!", "is_public": "on"},
        )
        case_a.refresh_from_db()
        assert case_a.first_responded_at is not None

    def test_second_public_reply_does_not_overwrite_first_responded_at(self, client_a, case_a):
        """The atomic F()-style update only fires for null → value, never overwrites."""
        # First reply
        client_a.post(
            reverse("crm:case_comment_add", args=[case_a.pk]),
            {"body": "First reply", "is_public": "on"},
        )
        case_a.refresh_from_db()
        first_stamp = case_a.first_responded_at
        assert first_stamp is not None

        # Second reply
        client_a.post(
            reverse("crm:case_comment_add", args=[case_a.pk]),
            {"body": "Second reply", "is_public": "on"},
        )
        case_a.refresh_from_db()
        # Must NOT have changed
        assert case_a.first_responded_at == first_stamp

    def test_comment_creates_casecomment_record(self, client_a, case_a, tenant_a):
        from apps.crm.models import CaseComment
        client_a.post(
            reverse("crm:case_comment_add", args=[case_a.pk]),
            {"body": "A comment", "is_public": "on"},
        )
        assert CaseComment.objects.filter(case=case_a, tenant=tenant_a).exists()


class TestSlaPolicyViews:
    def test_list_200(self, client_a, sla_a):
        resp = client_a.get(reverse("crm:slapolicy_list"))
        assert resp.status_code == 200

    def test_list_shows_own_policy(self, client_a, sla_a):
        resp = client_a.get(reverse("crm:slapolicy_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert sla_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, sla_a, sla_b):
        resp = client_a.get(reverse("crm:slapolicy_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert sla_b.pk not in pks

    def test_detail_200(self, client_a, sla_a):
        resp = client_a.get(reverse("crm:slapolicy_detail", args=[sla_a.pk]))
        assert resp.status_code == 200

    def test_create_get_200_admin(self, client_a):
        resp = client_a.get(reverse("crm:slapolicy_create"))
        assert resp.status_code == 200

    def test_create_blocked_for_non_admin(self, member_client):
        """@tenant_admin_required — a non-admin gets 403."""
        resp = member_client.get(reverse("crm:slapolicy_create"))
        assert resp.status_code == 403

    def test_create_post_persists_with_tenant(self, client_a, tenant_a):
        from apps.crm.models import SlaPolicy
        resp = client_a.post(reverse("crm:slapolicy_create"), {
            "name": "Gold SLA",
            "is_active": "on",
            "is_default": "",
            "response_low": 48,
            "response_medium": 24,
            "response_high": 4,
            "response_critical": 1,
            "resolution_low": 200,
            "resolution_medium": 100,
            "resolution_high": 24,
            "resolution_critical": 4,
        })
        assert resp.status_code == 302
        s = SlaPolicy.objects.filter(tenant=tenant_a, name="Gold SLA").first()
        assert s is not None
        assert s.number.startswith("SLA-")

    def test_edit_blocked_for_non_admin(self, member_client, sla_a):
        resp = member_client.get(reverse("crm:slapolicy_edit", args=[sla_a.pk]))
        assert resp.status_code == 403

    def test_edit_get_200_admin(self, client_a, sla_a):
        resp = client_a.get(reverse("crm:slapolicy_edit", args=[sla_a.pk]))
        assert resp.status_code == 200

    def test_delete_blocked_for_non_admin(self, member_client, sla_a):
        resp = member_client.post(reverse("crm:slapolicy_delete", args=[sla_a.pk]))
        assert resp.status_code == 403

    def test_delete_succeeds_for_admin(self, client_a, sla_a):
        from apps.crm.models import SlaPolicy
        pk = sla_a.pk
        resp = client_a.post(reverse("crm:slapolicy_delete", args=[pk]))
        assert resp.status_code == 302
        assert not SlaPolicy.objects.filter(pk=pk).exists()

    def test_anon_redirected(self, client):
        resp = client.get(reverse("crm:slapolicy_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestKnowledgeArticleViews:
    def test_list_200(self, client_a, article_a):
        resp = client_a.get(reverse("crm:knowledgearticle_list"))
        assert resp.status_code == 200

    def test_list_shows_own_article(self, client_a, article_a):
        resp = client_a.get(reverse("crm:knowledgearticle_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert article_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, article_a, article_b):
        resp = client_a.get(reverse("crm:knowledgearticle_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert article_b.pk not in pks

    def test_detail_200(self, client_a, article_a):
        resp = client_a.get(reverse("crm:knowledgearticle_detail", args=[article_a.pk]))
        assert resp.status_code == 200

    def test_detail_increments_views_count(self, client_a, article_a):
        """knowledgearticle_detail must bump views_count."""
        before = article_a.views_count
        client_a.get(reverse("crm:knowledgearticle_detail", args=[article_a.pk]))
        article_a.refresh_from_db()
        assert article_a.views_count == before + 1

    def test_create_get_200(self, client_a):
        resp = client_a.get(reverse("crm:knowledgearticle_create"))
        assert resp.status_code == 200

    def test_create_post_persists_with_tenant(self, client_a, tenant_a):
        from apps.crm.models import KnowledgeArticle
        resp = client_a.post(reverse("crm:knowledgearticle_create"), {
            "title": "New Article",
            "visibility": "internal",
            "status": "draft",
        })
        assert resp.status_code == 302
        a = KnowledgeArticle.objects.filter(tenant=tenant_a, title="New Article").first()
        assert a is not None
        assert a.number.startswith("KB-")

    def test_edit_get_200(self, client_a, article_a):
        resp = client_a.get(reverse("crm:knowledgearticle_edit", args=[article_a.pk]))
        assert resp.status_code == 200

    def test_delete_removes_record(self, client_a, article_a):
        from apps.crm.models import KnowledgeArticle
        pk = article_a.pk
        resp = client_a.post(reverse("crm:knowledgearticle_delete", args=[pk]))
        assert resp.status_code == 302
        assert not KnowledgeArticle.objects.filter(pk=pk).exists()

    def test_anon_redirected(self, client):
        resp = client.get(reverse("crm:knowledgearticle_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestKbCategoryViews:
    def test_list_200(self, client_a, kb_cat_a):
        resp = client_a.get(reverse("crm:kbcategory_list"))
        assert resp.status_code == 200

    def test_list_shows_own_category(self, client_a, kb_cat_a):
        resp = client_a.get(reverse("crm:kbcategory_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert kb_cat_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, kb_cat_a, kb_cat_b):
        resp = client_a.get(reverse("crm:kbcategory_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert kb_cat_b.pk not in pks

    def test_detail_200(self, client_a, kb_cat_a):
        resp = client_a.get(reverse("crm:kbcategory_detail", args=[kb_cat_a.pk]))
        assert resp.status_code == 200

    def test_create_get_200(self, client_a):
        resp = client_a.get(reverse("crm:kbcategory_create"))
        assert resp.status_code == 200

    def test_create_post_persists_with_tenant(self, client_a, tenant_a):
        from apps.crm.models import KbCategory
        resp = client_a.post(reverse("crm:kbcategory_create"), {
            "name": "New Category",
            "is_active": "on",
            "order": "0",
        })
        assert resp.status_code == 302
        c = KbCategory.objects.filter(tenant=tenant_a, name="New Category").first()
        assert c is not None
        assert c.number.startswith("KBC-")

    def test_edit_get_200(self, client_a, kb_cat_a):
        resp = client_a.get(reverse("crm:kbcategory_edit", args=[kb_cat_a.pk]))
        assert resp.status_code == 200

    def test_delete_removes_record(self, client_a, kb_cat_a):
        from apps.crm.models import KbCategory
        pk = kb_cat_a.pk
        resp = client_a.post(reverse("crm:kbcategory_delete", args=[pk]))
        assert resp.status_code == 302
        assert not KbCategory.objects.filter(pk=pk).exists()

    def test_anon_redirected(self, client):
        resp = client.get(reverse("crm:kbcategory_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestCustomerPortalAccessViews:
    def test_list_200(self, client_a, portal_access_a):
        resp = client_a.get(reverse("crm:customerportalaccess_list"))
        assert resp.status_code == 200

    def test_list_shows_own_access(self, client_a, portal_access_a):
        resp = client_a.get(reverse("crm:customerportalaccess_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert portal_access_a.pk in pks

    def test_create_get_200_admin(self, client_a):
        resp = client_a.get(reverse("crm:customerportalaccess_create"))
        assert resp.status_code == 200

    def test_create_blocked_for_non_admin(self, member_client):
        """@tenant_admin_required gates creation of portal access."""
        resp = member_client.get(reverse("crm:customerportalaccess_create"))
        assert resp.status_code == 403

    def test_detail_200(self, client_a, portal_access_a):
        resp = client_a.get(reverse("crm:customerportalaccess_detail", args=[portal_access_a.pk]))
        assert resp.status_code == 200

    def test_edit_blocked_for_non_admin(self, member_client, portal_access_a):
        resp = member_client.get(reverse("crm:customerportalaccess_edit", args=[portal_access_a.pk]))
        assert resp.status_code == 403

    def test_edit_get_200_admin(self, client_a, portal_access_a):
        resp = client_a.get(reverse("crm:customerportalaccess_edit", args=[portal_access_a.pk]))
        assert resp.status_code == 200

    def test_delete_blocked_for_non_admin(self, member_client, portal_access_a):
        resp = member_client.post(reverse("crm:customerportalaccess_delete", args=[portal_access_a.pk]))
        assert resp.status_code == 403

    def test_delete_succeeds_for_admin(self, client_a, portal_access_a):
        from apps.crm.models import CustomerPortalAccess
        pk = portal_access_a.pk
        resp = client_a.post(reverse("crm:customerportalaccess_delete", args=[pk]))
        assert resp.status_code == 302
        assert not CustomerPortalAccess.objects.filter(pk=pk).exists()

    def test_anon_redirected(self, client):
        resp = client.get(reverse("crm:customerportalaccess_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# =================================================================== PUBLIC ENDPOINTS

class TestCasePublic:
    """case_public: no login required; bearer is the case's public_token."""

    def test_get_200(self, client, case_a):
        resp = client.get(reverse("crm:case_public", kwargs={"token": case_a.public_token}))
        assert resp.status_code == 200

    def test_bogus_token_404(self, client):
        resp = client.get(reverse("crm:case_public", kwargs={"token": "not-a-real-token-xyz"}))
        assert resp.status_code == 404

    def test_only_public_comments_shown(self, client, case_a, tenant_a, admin_user):
        """Internal (is_public=False) comments must not appear on the public page."""
        from apps.crm.models import CaseComment
        public_c = CaseComment.objects.create(
            tenant=tenant_a, case=case_a, author=admin_user,
            body="Customer can see this", is_public=True)
        private_c = CaseComment.objects.create(
            tenant=tenant_a, case=case_a, author=admin_user,
            body="Agent-only note", is_public=False)
        resp = client.get(reverse("crm:case_public", kwargs={"token": case_a.public_token}))
        comment_pks = [c.pk for c in resp.context["comments"]]
        assert public_c.pk in comment_pks
        assert private_c.pk not in comment_pks

    def test_post_comment_creates_public_casecomment(self, client, case_a, tenant_a):
        """A POST with action=comment on the public page creates an is_public=True comment."""
        from apps.crm.models import CaseComment
        url = reverse("crm:case_public", kwargs={"token": case_a.public_token})
        resp = client.post(url, {
            "action": "comment",
            "body": "Customer reply via public page",
        })
        assert resp.status_code == 302
        c = CaseComment.objects.filter(case=case_a, is_public=True).first()
        assert c is not None
        assert c.body == "Customer reply via public page"

    def test_post_satisfaction_records_rating(self, client, case_a):
        """A POST with action=satisfaction records the CSAT rating."""
        url = reverse("crm:case_public", kwargs={"token": case_a.public_token})
        resp = client.post(url, {
            "action": "satisfaction",
            "rating": "5",
            "comment": "Excellent support!",
        })
        assert resp.status_code == 302
        case_a.refresh_from_db()
        assert case_a.satisfaction_rating == 5
        assert case_a.satisfaction_comment == "Excellent support!"
        assert case_a.satisfaction_at is not None

    def test_post_satisfaction_atomic_guard_does_not_overwrite(self, client, case_a):
        """A second satisfaction POST must not overwrite the first rating (atomic guard)."""
        url = reverse("crm:case_public", kwargs={"token": case_a.public_token})
        # First submission
        client.post(url, {"action": "satisfaction", "rating": "5", "comment": "Great!"})
        case_a.refresh_from_db()
        assert case_a.satisfaction_rating == 5

        # Second submission (attempt to overwrite)
        client.post(url, {"action": "satisfaction", "rating": "1", "comment": "Bad!"})
        case_a.refresh_from_db()
        # Must remain 5 — the atomic UPDATE...WHERE satisfaction_rating IS NULL matched 0 rows
        assert case_a.satisfaction_rating == 5


class TestKbPublic:
    """kb_public: no login; only published+external articles are accessible."""

    def test_get_200_for_published_external(self, client, article_a):
        resp = client.get(reverse("crm:kb_public", kwargs={"token": article_a.public_token}))
        assert resp.status_code == 200

    def test_get_404_for_draft(self, client, article_draft):
        resp = client.get(reverse("crm:kb_public", kwargs={"token": article_draft.public_token}))
        assert resp.status_code == 404

    def test_get_404_for_internal(self, client, article_internal):
        resp = client.get(reverse("crm:kb_public", kwargs={"token": article_internal.public_token}))
        assert resp.status_code == 404

    def test_get_404_for_bogus_token(self, client):
        resp = client.get(reverse("crm:kb_public", kwargs={"token": "bogus-token-xyz"}))
        assert resp.status_code == 404

    def test_get_increments_views_count(self, client, article_a):
        before = article_a.views_count
        client.get(reverse("crm:kb_public", kwargs={"token": article_a.public_token}))
        article_a.refresh_from_db()
        assert article_a.views_count == before + 1


class TestKbHelpful:
    """kb_helpful: POST-only public vote endpoint."""

    def test_get_is_405(self, client, article_a):
        """GET must be rejected with 405 (require_POST)."""
        resp = client.get(reverse("crm:kb_helpful", kwargs={"token": article_a.public_token}))
        assert resp.status_code == 405

    def test_vote_yes_increments_helpful_count(self, client, article_a):
        before = article_a.helpful_count
        url = reverse("crm:kb_helpful", kwargs={"token": article_a.public_token})
        resp = client.post(url, {"vote": "yes"})
        assert resp.status_code == 302
        article_a.refresh_from_db()
        assert article_a.helpful_count == before + 1
        assert article_a.not_helpful_count == 0

    def test_vote_no_increments_not_helpful_count(self, client, article_a):
        before = article_a.not_helpful_count
        url = reverse("crm:kb_helpful", kwargs={"token": article_a.public_token})
        resp = client.post(url, {"vote": "no"})
        assert resp.status_code == 302
        article_a.refresh_from_db()
        assert article_a.not_helpful_count == before + 1
        assert article_a.helpful_count == 0

    def test_bogus_vote_changes_nothing(self, client, article_a):
        url = reverse("crm:kb_helpful", kwargs={"token": article_a.public_token})
        resp = client.post(url, {"vote": "maybe"})
        assert resp.status_code == 302
        article_a.refresh_from_db()
        assert article_a.helpful_count == 0
        assert article_a.not_helpful_count == 0

    def test_bogus_token_404(self, client):
        url = reverse("crm:kb_helpful", kwargs={"token": "no-such-token"})
        resp = client.post(url, {"vote": "yes"})
        assert resp.status_code == 404


# =================================================================== CUSTOMER PORTAL

class TestPortalCaseList:
    def test_no_access_redirected(self, member_client):
        """A logged-in user with no CustomerPortalAccess is redirected."""
        resp = member_client.get(reverse("crm:portal_case_list"))
        assert resp.status_code == 302

    def test_anon_redirected(self, client):
        resp = client.get(reverse("crm:portal_case_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_access_with_no_customer_party_redirected(self, tenant_a, db):
        """An access record with customer_party=None must redirect (no case leak)."""
        from apps.accounts.models import User
        from apps.crm.models import CustomerPortalAccess
        # Create a portal user with no party link
        orphan_user = User.objects.create_user(
            email="orphan@acme.com", username="orphan_acme",
            password="X", tenant=tenant_a, is_tenant_admin=False)
        CustomerPortalAccess.objects.create(
            tenant=tenant_a, portal_user=orphan_user,
            customer_party=None, is_active=True)
        c = Client()
        c.force_login(orphan_user)
        resp = c.get(reverse("crm:portal_case_list"))
        # Must redirect rather than show an empty or cross-tenant list
        assert resp.status_code == 302

    def test_portal_list_shows_only_own_party_cases(
            self, portal_client_a, case_a, tenant_a, party_a, party_b, portal_access_a):
        """The portal user sees only cases linked to their customer_party."""
        from apps.crm.models import Case
        # A case for another party in the same tenant
        other_party = party_b  # already in tenant_b — make one in tenant_a
        from apps.core.models import Party
        other_party_a = Party.objects.create(
            tenant=tenant_a, kind="organization", name="Other Company")
        other_case = Case.objects.create(
            tenant=tenant_a, subject="Other company case",
            status="new", account=other_party_a)

        resp = portal_client_a.get(reverse("crm:portal_case_list"))
        assert resp.status_code == 200
        pks = [o.pk for o in resp.context["object_list"]]
        # case_a is linked to party_a which is portal_access_a.customer_party
        assert case_a.pk in pks
        # other_case is linked to a different party — must NOT appear
        assert other_case.pk not in pks


class TestPortalCaseDetail:
    def test_own_case_200(self, portal_client_a, case_a, portal_access_a):
        resp = portal_client_a.get(reverse("crm:portal_case_detail", args=[case_a.pk]))
        assert resp.status_code == 200

    def test_other_customer_case_404(self, portal_client_a, portal_access_a, tenant_a):
        """Accessing another customer's case via the portal must return 404."""
        from apps.crm.models import Case
        from apps.core.models import Party
        other_party = Party.objects.create(
            tenant=tenant_a, kind="organization", name="Not My Company")
        other_case = Case.objects.create(
            tenant=tenant_a, subject="Not mine", status="new", account=other_party)
        resp = portal_client_a.get(
            reverse("crm:portal_case_detail", args=[other_case.pk]))
        assert resp.status_code == 404

    def test_no_access_redirected(self, member_client, case_a):
        """Non-portal user is redirected from portal case detail."""
        resp = member_client.get(reverse("crm:portal_case_detail", args=[case_a.pk]))
        assert resp.status_code == 302


class TestPortalCaseCreate:
    def test_get_200(self, portal_client_a, portal_access_a):
        resp = portal_client_a.get(reverse("crm:portal_case_create"))
        assert resp.status_code == 200

    def test_post_creates_case_with_portal_origin(
            self, portal_client_a, portal_access_a, party_a, tenant_a):
        """portal_case_create forces account=customer_party and origin=portal."""
        from apps.crm.models import Case
        resp = portal_client_a.post(reverse("crm:portal_case_create"), {
            "subject": "My support request",
            "priority": "low",
            "description": "Please help me.",
        })
        assert resp.status_code == 302
        c = Case.objects.filter(tenant=tenant_a, subject="My support request").first()
        assert c is not None
        assert c.origin == "portal"
        assert c.account == party_a  # forced to customer_party

    def test_no_access_redirected(self, member_client):
        resp = member_client.get(reverse("crm:portal_case_create"))
        assert resp.status_code == 302


# =================================================================== MULTI-TENANT IDOR

class TestCaseIDOR:
    """Tenant A user attempts to access Tenant B's Case objects → 404."""

    def test_detail_cross_tenant_404(self, client_a, case_b):
        resp = client_a.get(reverse("crm:case_detail", args=[case_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, case_b):
        resp = client_a.get(reverse("crm:case_edit", args=[case_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, case_b):
        resp = client_a.post(reverse("crm:case_edit", args=[case_b.pk]), {
            "subject": "Injected", "type": "question",
            "priority": "low", "status": "new", "origin": "email",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, case_b):
        resp = client_a.post(reverse("crm:case_delete", args=[case_b.pk]))
        assert resp.status_code == 404


class TestSlaPolicyIDOR:
    def test_detail_cross_tenant_404(self, client_a, sla_b):
        resp = client_a.get(reverse("crm:slapolicy_detail", args=[sla_b.pk]))
        assert resp.status_code == 404

    def test_edit_cross_tenant_404(self, client_a, sla_b):
        resp = client_a.get(reverse("crm:slapolicy_edit", args=[sla_b.pk]))
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, sla_b):
        resp = client_a.post(reverse("crm:slapolicy_delete", args=[sla_b.pk]))
        assert resp.status_code == 404


class TestKnowledgeArticleIDOR:
    def test_detail_cross_tenant_404(self, client_a, article_b):
        resp = client_a.get(reverse("crm:knowledgearticle_detail", args=[article_b.pk]))
        assert resp.status_code == 404

    def test_edit_cross_tenant_404(self, client_a, article_b):
        resp = client_a.get(reverse("crm:knowledgearticle_edit", args=[article_b.pk]))
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, article_b):
        resp = client_a.post(reverse("crm:knowledgearticle_delete", args=[article_b.pk]))
        assert resp.status_code == 404


class TestKbCategoryIDOR:
    def test_detail_cross_tenant_404(self, client_a, kb_cat_b):
        resp = client_a.get(reverse("crm:kbcategory_detail", args=[kb_cat_b.pk]))
        assert resp.status_code == 404

    def test_edit_cross_tenant_404(self, client_a, kb_cat_b):
        resp = client_a.get(reverse("crm:kbcategory_edit", args=[kb_cat_b.pk]))
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, kb_cat_b):
        resp = client_a.post(reverse("crm:kbcategory_delete", args=[kb_cat_b.pk]))
        assert resp.status_code == 404


class TestCustomerPortalAccessIDOR:
    def test_detail_cross_tenant_404(self, client_a, db, tenant_b, admin_b):
        """Tenant A can't view tenant B's CustomerPortalAccess records."""
        from apps.crm.models import CustomerPortalAccess
        access_b = CustomerPortalAccess.objects.create(
            tenant=tenant_b, portal_user=admin_b)
        resp = client_a.get(reverse("crm:customerportalaccess_detail", args=[access_b.pk]))
        assert resp.status_code == 404

    def test_edit_cross_tenant_404(self, client_a, db, tenant_b, admin_b):
        from apps.crm.models import CustomerPortalAccess
        access_b = CustomerPortalAccess.objects.create(
            tenant=tenant_b, portal_user=admin_b)
        resp = client_a.get(reverse("crm:customerportalaccess_edit", args=[access_b.pk]))
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, db, tenant_b, admin_b):
        from apps.crm.models import CustomerPortalAccess
        access_b = CustomerPortalAccess.objects.create(
            tenant=tenant_b, portal_user=admin_b)
        resp = client_a.post(reverse("crm:customerportalaccess_delete", args=[access_b.pk]))
        assert resp.status_code == 404
