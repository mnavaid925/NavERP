"""Tenants app test fixtures."""
import pytest
from django.utils import timezone


@pytest.fixture
def subscription_a(db, tenant_a):
    from apps.tenants.models import Subscription
    return Subscription.objects.create(
        tenant=tenant_a,
        plan="starter",
        status="trialing",
        billing_cycle="monthly",
        amount="29.99",
        seats=5,
        renews_on=timezone.localdate() + timezone.timedelta(days=14),
    )


@pytest.fixture
def subscription_b(db, tenant_b):
    from apps.tenants.models import Subscription
    return Subscription.objects.create(
        tenant=tenant_b,
        plan="pro",
        status="active",
        billing_cycle="yearly",
        amount="99.99",
        seats=10,
    )


@pytest.fixture
def invoice_a(db, tenant_a, subscription_a):
    from apps.tenants.models import SubscriptionInvoice
    return SubscriptionInvoice.objects.create(
        tenant=tenant_a,
        subscription=subscription_a,
        status="open",
        amount="29.99",
    )


@pytest.fixture
def encryption_key_a(db, tenant_a):
    from apps.tenants.models import EncryptionKey
    key = EncryptionKey(tenant=tenant_a, name="Primary Key", status="active")
    plaintext = EncryptionKey.generate_plaintext()
    key.set_secret(plaintext)
    key.save()
    return key, plaintext


# =====================================================================================
# 0.19 License & Subscription Administration.
#
# APPEND-ONLY (L43): this file is shared with 0.1's four lanes. Every fixture below is named with
# a `lic019_` prefix so it cannot shadow a 0.1 fixture, and nothing above this line was touched.
#
# `tenant_a` / `tenant_b` are the two workspaces the top of this file defines, which is exactly what
# the cross-tenant guards need. `lic019_subscription_a` is deliberately SEPARATE from the 0.1
# `subscription_a`: that one leaves `auto_renew` unset, which is the I10 three-state case this
# sub-module must not break.
# =====================================================================================


@pytest.fixture
def lic019_feature_a(db, tenant_a):
    """One boolean-privilege catalog feature for tenant A."""
    from apps.tenants.models import EntitlementFeature
    return EntitlementFeature.objects.create(
        tenant=tenant_a, code="sso", name="Single Sign-On", privilege_type="boolean",
        status="active", description="Federated sign-in.",
    )


@pytest.fixture
def lic019_feature_select_a(db, tenant_a):
    """A SELECT-privilege feature, so the `select_options` rule has something to bite on."""
    from apps.tenants.models import EntitlementFeature
    return EntitlementFeature.objects.create(
        tenant=tenant_a, code="sso_provider", name="SSO Provider", privilege_type="select",
        status="active", is_add_on=True, select_options="entra_id,okta,onelogin",
    )


@pytest.fixture
def lic019_subscription_a(db, tenant_a):
    """Tenant A's subscription, with an EXPRESSED auto_renew so the tri-state is unambiguous."""
    from apps.tenants.models import Subscription
    return Subscription.objects.create(
        tenant=tenant_a, plan="pro", status="active", billing_cycle="monthly",
        amount="149.00", seats=10, auto_renew=True,
    )


@pytest.fixture
def lic019_subscription_b(db, tenant_b):
    """Tenant B's subscription — the row a tenant-A record must never be able to point at."""
    from apps.tenants.models import Subscription
    return Subscription.objects.create(
        tenant=tenant_b, plan="enterprise", status="active", billing_cycle="yearly",
        amount="499.00", seats=100,
    )


@pytest.fixture
def lic019_plan_grant_a(db, tenant_a, lic019_feature_a):
    """A PLAN-level grant (`subscription=None`) — the catalog row an override outranks."""
    from apps.tenants.models import PlanEntitlement
    return PlanEntitlement.objects.create(
        tenant=tenant_a, plan="pro", feature=lic019_feature_a,
        privilege_value="true", is_enabled=True,
    )


@pytest.fixture
def lic019_override_a(db, tenant_a, lic019_feature_a, lic019_subscription_a):
    """A SUBSCRIPTION-level override of the same feature — the Chargebee-precedence case."""
    from apps.tenants.models import PlanEntitlement
    return PlanEntitlement.objects.create(
        tenant=tenant_a, plan="pro", feature=lic019_feature_a,
        subscription=lic019_subscription_a, privilege_value="false", is_enabled=True,
        notes="Negotiated off for this subscription.",
    )


@pytest.fixture
def lic019_quota_a(db, tenant_a, lic019_subscription_a):
    """A metered ceiling with a non-zero limit."""
    from apps.tenants.models import UsageQuota
    return UsageQuota.objects.create(
        tenant=tenant_a, subscription=lic019_subscription_a, metric="api_calls",
        quota_limit="500000.00", warn_at_pct=80, action_on_breach="alert", period="monthly",
    )


@pytest.fixture
def lic019_quota_unmetered_a(db, tenant_a, lic019_subscription_a):
    """A `quota_limit == 0` ceiling — the UNMETERED third state (0 is not "zero allowed")."""
    from apps.tenants.models import UsageQuota
    return UsageQuota.objects.create(
        tenant=tenant_a, subscription=lic019_subscription_a, metric="transactions",
        quota_limit="0.00", warn_at_pct=80, action_on_breach="alert", period="monthly",
    )


@pytest.fixture
def lic019_user_a(db, tenant_a):
    """A seat holder whose `tenant` is tenant A.

    Built through `create_user` so the password goes through Django's hasher and the account is a real
    `accounts.User` with `tenant` set — the nullable-`User.tenant` path every seat count narrows on.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(
        username="lic019_ops", email="lic019_ops@acme.test", password="pw-lic019",
        tenant=tenant_a,
    )


@pytest.fixture
def lic019_user_b(db, tenant_b):
    """A tenant-B user, for the cross-tenant seat and picker cases."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(
        username="lic019_other", email="lic019_other@globex.test", password="pw-lic019",
        tenant=tenant_b,
    )


@pytest.fixture
def lic019_seat_a(db, tenant_a, lic019_user_a, lic019_subscription_a):
    """One active tenant-wide seat (blank `module_slug` is the tenant-wide value, never NULL)."""
    from apps.tenants.models import LicenseAssignment
    return LicenseAssignment.objects.create(
        tenant=tenant_a, user=lic019_user_a, module_slug="",
        status="active", assignment_source="direct", subscription=lic019_subscription_a,
    )


@pytest.fixture
def lic019_seat_expired_a(db, tenant_a, lic019_user_a, lic019_subscription_a):
    """A seat whose `expires_on` is past — the DERIVED expired state, not a stored status."""
    from datetime import timedelta

    from django.utils import timezone

    from apps.tenants.models import LicenseAssignment
    return LicenseAssignment.objects.create(
        tenant=tenant_a, user=lic019_user_a, module_slug="crm",
        status="active", assignment_source="direct", subscription=lic019_subscription_a,
        expires_on=timezone.localdate() - timedelta(days=3),
    )
