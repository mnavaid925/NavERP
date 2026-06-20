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
