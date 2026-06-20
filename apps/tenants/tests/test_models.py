"""Tests for tenants models: Subscription, SubscriptionInvoice, BrandingSetting, EncryptionKey."""
import hashlib
import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ Subscription
class TestSubscription:
    def test_str(self, subscription_a):
        assert "Acme Corp" in str(subscription_a)
        assert "Starter" in str(subscription_a)

    def test_default_plan(self, tenant_a):
        from apps.tenants.models import Subscription
        sub = Subscription.objects.create(tenant=tenant_a)
        assert sub.plan == "starter"

    def test_default_status(self, tenant_a):
        from apps.tenants.models import Subscription
        sub = Subscription.objects.create(tenant=tenant_a)
        assert sub.status == "trialing"

    def test_days_left_with_renews_on(self, subscription_a):
        days = subscription_a.days_left()
        assert days is not None
        assert days == 14

    def test_days_left_without_renews_on(self, tenant_a):
        from apps.tenants.models import Subscription
        sub = Subscription.objects.create(tenant=tenant_a)
        assert sub.days_left() is None

    def test_days_left_negative_when_past_due(self, tenant_a):
        from apps.tenants.models import Subscription
        sub = Subscription.objects.create(
            tenant=tenant_a,
            renews_on=timezone.localdate() - timezone.timedelta(days=5),
        )
        assert sub.days_left() < 0

    def test_status_choices(self):
        from apps.tenants.models import Subscription
        statuses = [c[0] for c in Subscription.STATUS_CHOICES]
        assert "trialing" in statuses
        assert "active" in statuses
        assert "past_due" in statuses
        assert "canceled" in statuses
        assert "incomplete" in statuses

    def test_billing_choices(self):
        from apps.tenants.models import Subscription
        cycles = [c[0] for c in Subscription.BILLING_CHOICES]
        assert "monthly" in cycles
        assert "yearly" in cycles


# ------------------------------------------------------------------ SubscriptionInvoice
class TestSubscriptionInvoice:
    def test_auto_number_assigned(self, invoice_a):
        assert invoice_a.number == "SINV-00001"

    def test_str_is_number(self, invoice_a):
        assert str(invoice_a) == "SINV-00001"

    def test_sequential_numbers(self, tenant_a, subscription_a):
        from apps.tenants.models import SubscriptionInvoice
        inv1 = SubscriptionInvoice.objects.create(
            tenant=tenant_a, subscription=subscription_a, status="open", amount=10
        )
        inv2 = SubscriptionInvoice.objects.create(
            tenant=tenant_a, subscription=subscription_a, status="open", amount=20
        )
        assert inv1.number == "SINV-00001"
        assert inv2.number == "SINV-00002"

    def test_per_tenant_numbering(self, tenant_a, tenant_b, subscription_a, subscription_b):
        from apps.tenants.models import SubscriptionInvoice
        inv_a = SubscriptionInvoice.objects.create(
            tenant=tenant_a, subscription=subscription_a, status="open", amount=10
        )
        inv_b = SubscriptionInvoice.objects.create(
            tenant=tenant_b, subscription=subscription_b, status="open", amount=20
        )
        assert inv_a.number == "SINV-00001"
        assert inv_b.number == "SINV-00001"

    def test_status_choices(self):
        from apps.tenants.models import SubscriptionInvoice
        statuses = [c[0] for c in SubscriptionInvoice.STATUS_CHOICES]
        assert "draft" in statuses
        assert "open" in statuses
        assert "paid" in statuses
        assert "void" in statuses
        assert "uncollectible" in statuses

    def test_unique_together_tenant_number(self, tenant_a, subscription_a, invoice_a):
        """Creating a second invoice with the same number for the same tenant raises IntegrityError."""
        from apps.tenants.models import SubscriptionInvoice
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            SubscriptionInvoice.objects.create(
                tenant=tenant_a,
                subscription=subscription_a,
                number="SINV-00001",  # manually set to force collision
                status="open",
                amount=50,
            )

    def test_number_not_reassigned_on_resave(self, invoice_a):
        """Re-saving an invoice must not change its number."""
        original_number = invoice_a.number
        invoice_a.status = "paid"
        invoice_a.save()
        invoice_a.refresh_from_db()
        assert invoice_a.number == original_number


# ------------------------------------------------------------------ BrandingSetting
class TestBrandingSetting:
    def test_str(self, tenant_a):
        from apps.tenants.models import BrandingSetting
        b = BrandingSetting.objects.create(tenant=tenant_a)
        assert "Acme Corp" in str(b)

    def test_default_colors(self, tenant_a):
        from apps.tenants.models import BrandingSetting
        b = BrandingSetting.objects.create(tenant=tenant_a)
        assert b.primary_color == "#2563eb"
        assert b.accent_color == "#1d4ed8"

    def test_valid_hex_color_saves(self, tenant_a):
        from apps.tenants.models import BrandingSetting
        b = BrandingSetting.objects.create(
            tenant=tenant_a, primary_color="#ff0000", accent_color="#00ff00"
        )
        assert b.primary_color == "#ff0000"

    def test_invalid_hex_color_raises_on_full_clean(self, tenant_a):
        """BrandingSetting with an invalid color should raise ValidationError on full_clean."""
        from apps.tenants.models import BrandingSetting
        b = BrandingSetting(tenant=tenant_a, primary_color="red;}INJECTION")
        with pytest.raises(ValidationError):
            b.full_clean()

    def test_invalid_hex_raises_on_save(self, tenant_a):
        """The save() method enforces the hex validator as a defense-in-depth."""
        from apps.tenants.models import BrandingSetting
        from django.core.exceptions import ValidationError as DjangoValidationError
        b = BrandingSetting(tenant=tenant_a, primary_color="red;}INJECTION")
        with pytest.raises((ValidationError, DjangoValidationError, Exception)):
            b.save()

    def test_three_char_hex_valid(self, tenant_a):
        from apps.tenants.models import BrandingSetting
        b = BrandingSetting.objects.create(
            tenant=tenant_a, primary_color="#fff", accent_color="#000"
        )
        assert b.primary_color == "#fff"


# ------------------------------------------------------------------ EncryptionKey
class TestEncryptionKey:
    def test_generate_plaintext_format(self):
        from apps.tenants.models import EncryptionKey
        pt = EncryptionKey.generate_plaintext()
        assert pt.startswith("nk_")
        assert len(pt) > 10

    def test_generate_plaintext_unique(self):
        from apps.tenants.models import EncryptionKey
        pt1 = EncryptionKey.generate_plaintext()
        pt2 = EncryptionKey.generate_plaintext()
        assert pt1 != pt2

    def test_set_secret_stores_prefix(self, tenant_a):
        from apps.tenants.models import EncryptionKey
        key = EncryptionKey(tenant=tenant_a, name="Test Key")
        plaintext = EncryptionKey.generate_plaintext()
        key.set_secret(plaintext)
        assert key.prefix == plaintext[:10]

    def test_set_secret_stores_sha256_hash(self, tenant_a):
        from apps.tenants.models import EncryptionKey
        key = EncryptionKey(tenant=tenant_a, name="Test Key")
        plaintext = EncryptionKey.generate_plaintext()
        key.set_secret(plaintext)
        expected_hash = hashlib.sha256(plaintext.encode()).hexdigest()
        assert key.key_hash == expected_hash

    def test_plaintext_not_stored(self, encryption_key_a):
        """The plaintext must never appear in the database record."""
        key, plaintext = encryption_key_a
        key.refresh_from_db()
        # Check that neither the plaintext nor the raw token body is stored
        assert key.key_hash != plaintext
        assert key.prefix != plaintext
        # Verify the prefix is only the first 10 chars
        assert len(key.prefix) == 10

    def test_str(self, encryption_key_a):
        key, _ = encryption_key_a
        assert "Primary Key" in str(key)
        assert "…" in str(key)

    def test_status_choices(self):
        from apps.tenants.models import EncryptionKey
        statuses = [c[0] for c in EncryptionKey.STATUS_CHOICES]
        assert "active" in statuses
        assert "rotated" in statuses
        assert "revoked" in statuses

    def test_default_status(self, encryption_key_a):
        key, _ = encryption_key_a
        assert key.status == "active"


# ------------------------------------------------------------------ HealthMetric
class TestHealthMetric:
    def test_str(self, tenant_a):
        from apps.tenants.models import HealthMetric
        m = HealthMetric.objects.create(tenant=tenant_a, metric="users", value=42)
        assert "Active Users" in str(m)
        assert "42" in str(m)

    def test_default_status(self, tenant_a):
        from apps.tenants.models import HealthMetric
        m = HealthMetric.objects.create(tenant=tenant_a, metric="users", value=1)
        assert m.status == "ok"

    def test_metric_choices(self):
        from apps.tenants.models import HealthMetric
        metrics = [c[0] for c in HealthMetric.METRIC_CHOICES]
        assert "users" in metrics
        assert "storage_mb" in metrics
        assert "api_calls" in metrics
