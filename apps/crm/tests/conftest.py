"""CRM app test fixtures.

Reuses the shared root conftest (tenant_a, tenant_b, admin_user, admin_b,
client_a, client_b, member_user, member_client) and adds CRM-specific records.
"""
import pytest


# ------------------------------------------------------------------ Party helpers
@pytest.fixture
def account_a(db, tenant_a):
    """An organization Party belonging to tenant_a."""
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_a, kind="organization", name="Acme Ltd")


@pytest.fixture
def account_b(db, tenant_b):
    """An organization Party belonging to tenant_b."""
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_b, kind="organization", name="Globex Ltd")


@pytest.fixture
def contact_a(db, tenant_a):
    """A person Party belonging to tenant_a."""
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_a, kind="person", name="Alice Smith")


@pytest.fixture
def contact_b(db, tenant_b):
    """A person Party belonging to tenant_b."""
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_b, kind="person", name="Bob Jones")


# ------------------------------------------------------------------ CRM model fixtures
@pytest.fixture
def lead_a(db, tenant_a):
    from apps.crm.models import Lead
    return Lead.objects.create(
        tenant=tenant_a,
        name="Jane Doe",
        company="Acme Corp",
        email="jane@acme.com",
        status="new",
        source="web",
        rating="warm",
        est_value="1000.00",
    )


@pytest.fixture
def lead_b(db, tenant_b):
    from apps.crm.models import Lead
    return Lead.objects.create(
        tenant=tenant_b,
        name="Bob Smith",
        company="Globex Inc",
        status="new",
    )


@pytest.fixture
def opportunity_a(db, tenant_a, account_a):
    from apps.crm.models import Opportunity
    return Opportunity.objects.create(
        tenant=tenant_a,
        name="Big Deal",
        account=account_a,
        stage="prospecting",
        amount="5000.00",
        probability=20,
    )


@pytest.fixture
def opportunity_b(db, tenant_b, account_b):
    from apps.crm.models import Opportunity
    return Opportunity.objects.create(
        tenant=tenant_b,
        name="Other Deal",
        account=account_b,
        stage="qualification",
        amount="3000.00",
        probability=50,
    )


@pytest.fixture
def campaign_a(db, tenant_a):
    from apps.crm.models import Campaign
    return Campaign.objects.create(
        tenant=tenant_a,
        name="Spring Promo",
        type="email",
        status="planned",
        budget_planned="2000.00",
        budget_actual="0.00",
        actual_revenue="0.00",
    )


@pytest.fixture
def campaign_b(db, tenant_b):
    from apps.crm.models import Campaign
    return Campaign.objects.create(
        tenant=tenant_b,
        name="Other Promo",
        type="social",
        status="active",
    )


@pytest.fixture
def case_a(db, tenant_a):
    from apps.crm.models import Case
    return Case.objects.create(
        tenant=tenant_a,
        subject="Widget broken",
        priority="medium",
        status="new",
    )


@pytest.fixture
def case_b(db, tenant_b):
    from apps.crm.models import Case
    return Case.objects.create(
        tenant=tenant_b,
        subject="Globex issue",
        status="new",
    )


@pytest.fixture
def article_a(db, tenant_a):
    from apps.crm.models import KnowledgeArticle
    return KnowledgeArticle.objects.create(
        tenant=tenant_a,
        title="How to reset password",
        status="draft",
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
def task_a(db, tenant_a):
    from apps.crm.models import CrmTask
    return CrmTask.objects.create(
        tenant=tenant_a,
        subject="Follow up with Jane",
        type="call",
        priority="high",
        status="open",
    )


@pytest.fixture
def task_b(db, tenant_b):
    from apps.crm.models import CrmTask
    return CrmTask.objects.create(
        tenant=tenant_b,
        subject="Globex task",
        status="open",
    )
