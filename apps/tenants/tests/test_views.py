"""Tests for tenants views: subscription CRUD, mark_paid, webhook, IDOR, encryption keys."""
import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ Subscription views
class TestSubscriptionViews:
    def test_list_admin_200(self, client_a):
        resp = client_a.get(reverse("tenants:subscription_list"))
        assert resp.status_code == 200

    def test_list_member_403(self, member_client):
        resp = member_client.get(reverse("tenants:subscription_list"))
        assert resp.status_code == 403

    def test_list_anon_redirects(self, client):
        resp = client.get(reverse("tenants:subscription_list"))
        assert resp.status_code == 302

    def test_create_get_200(self, client_a):
        resp = client_a.get(reverse("tenants:subscription_create"))
        assert resp.status_code == 200

    def test_create_post_saves_with_tenant(self, client_a, tenant_a):
        from apps.tenants.models import Subscription
        resp = client_a.post(reverse("tenants:subscription_create"), {
            "plan": "starter",
            "status": "trialing",
            "billing_cycle": "monthly",
            "amount": "29.99",
            "seats": 5,
            "started_on": "",
            "renews_on": "",
        })
        assert resp.status_code == 302
        assert Subscription.objects.filter(tenant=tenant_a, plan="starter").exists()

    def test_detail_200(self, client_a, subscription_a):
        resp = client_a.get(reverse("tenants:subscription_detail", args=[subscription_a.pk]))
        assert resp.status_code == 200

    def test_detail_cross_tenant_404(self, client_a, subscription_b):
        resp = client_a.get(reverse("tenants:subscription_detail", args=[subscription_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_200(self, client_a, subscription_a):
        resp = client_a.get(reverse("tenants:subscription_edit", args=[subscription_a.pk]))
        assert resp.status_code == 200

    def test_edit_cross_tenant_404(self, client_a, subscription_b):
        resp = client_a.get(reverse("tenants:subscription_edit", args=[subscription_b.pk]))
        assert resp.status_code == 404

    def test_delete_post_removes(self, client_a, subscription_a):
        from apps.tenants.models import Subscription
        pk = subscription_a.pk
        resp = client_a.post(reverse("tenants:subscription_delete", args=[pk]))
        assert resp.status_code == 302
        assert not Subscription.objects.filter(pk=pk).exists()

    def test_delete_cross_tenant_404(self, client_a, subscription_b):
        resp = client_a.post(reverse("tenants:subscription_delete", args=[subscription_b.pk]))
        assert resp.status_code == 404

    def test_list_only_shows_own_tenant(self, client_a, subscription_a, subscription_b):
        resp = client_a.get(reverse("tenants:subscription_list"))
        pks = [s.pk for s in resp.context["object_list"]]
        assert subscription_a.pk in pks
        assert subscription_b.pk not in pks


# ------------------------------------------------------------------ subscription_mark_paid
class TestSubscriptionMarkPaid:
    def test_mark_paid_sets_status_active(self, client_a, subscription_a):
        resp = client_a.post(
            reverse("tenants:subscription_mark_paid", args=[subscription_a.pk])
        )
        assert resp.status_code == 302
        subscription_a.refresh_from_db()
        assert subscription_a.status == "active"

    def test_mark_paid_creates_invoice(self, client_a, subscription_a, tenant_a):
        from apps.tenants.models import SubscriptionInvoice
        client_a.post(reverse("tenants:subscription_mark_paid", args=[subscription_a.pk]))
        assert SubscriptionInvoice.objects.filter(
            tenant=tenant_a, subscription=subscription_a, status="paid"
        ).exists()

    def test_mark_paid_invoice_has_paid_at(self, client_a, subscription_a, tenant_a):
        from apps.tenants.models import SubscriptionInvoice
        client_a.post(reverse("tenants:subscription_mark_paid", args=[subscription_a.pk]))
        inv = SubscriptionInvoice.objects.get(tenant=tenant_a, subscription=subscription_a)
        assert inv.paid_at is not None

    def test_mark_paid_sets_started_on_if_unset(self, client_a, subscription_a):
        subscription_a.started_on = None
        subscription_a.save()
        client_a.post(reverse("tenants:subscription_mark_paid", args=[subscription_a.pk]))
        subscription_a.refresh_from_db()
        assert subscription_a.started_on is not None

    def test_mark_paid_sets_renews_on_30_days(self, client_a, subscription_a):
        client_a.post(reverse("tenants:subscription_mark_paid", args=[subscription_a.pk]))
        subscription_a.refresh_from_db()
        expected = timezone.localdate() + timezone.timedelta(days=30)
        assert subscription_a.renews_on == expected

    def test_mark_paid_cross_tenant_404(self, client_a, subscription_b):
        resp = client_a.post(
            reverse("tenants:subscription_mark_paid", args=[subscription_b.pk])
        )
        assert resp.status_code == 404

    def test_mark_paid_creates_audit_log(self, client_a, subscription_a, tenant_a):
        from apps.core.models import AuditLog
        client_a.post(reverse("tenants:subscription_mark_paid", args=[subscription_a.pk]))
        assert AuditLog.objects.filter(tenant=tenant_a, action="update").exists()

    def test_mark_paid_is_atomic(self, client_a, subscription_a, tenant_a, monkeypatch):
        """If invoice creation fails, subscription status must roll back."""
        from apps.tenants import views as tenant_views
        from apps.tenants.models import SubscriptionInvoice

        original_create = SubscriptionInvoice.objects.create

        def failing_create(**kwargs):
            raise Exception("DB error")

        monkeypatch.setattr(SubscriptionInvoice.objects, "create", failing_create)

        with pytest.raises(Exception, match="DB error"):
            client_a.post(
                reverse("tenants:subscription_mark_paid", args=[subscription_a.pk])
            )

        subscription_a.refresh_from_db()
        # Status should still be trialing (rolled back)
        assert subscription_a.status == "trialing"


# ------------------------------------------------------------------ Stripe webhook
class TestStripeWebhook:
    """Webhook returns 400 when Stripe is disabled (settings_test has STRIPE_ENABLED=False)."""

    def test_webhook_returns_400_when_stripe_disabled(self, client):
        resp = client.post(
            reverse("tenants:stripe_webhook"),
            data=b'{}',
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_webhook_no_signature_returns_400(self, client):
        resp = client.post(
            reverse("tenants:stripe_webhook"),
            data=b'{"type": "invoice.paid"}',
            content_type="application/json",
        )
        assert resp.status_code == 400


# ------------------------------------------------------------------ Encryption key views
class TestEncryptionKeyViews:
    def test_list_admin_200(self, client_a):
        resp = client_a.get(reverse("tenants:encryptionkey_list"))
        assert resp.status_code == 200

    def test_list_member_403(self, member_client):
        resp = member_client.get(reverse("tenants:encryptionkey_list"))
        assert resp.status_code == 403

    def test_create_post_generates_key(self, client_a, tenant_a):
        from apps.tenants.models import EncryptionKey
        resp = client_a.post(reverse("tenants:encryptionkey_create"), {"name": "API Key"})
        assert resp.status_code == 302
        key = EncryptionKey.objects.filter(tenant=tenant_a, name="API Key").first()
        assert key is not None
        assert key.prefix  # prefix set
        assert key.key_hash  # hash set

    def test_detail_cross_tenant_404(self, client_a, encryption_key_a, tenant_b):
        from apps.tenants.models import EncryptionKey
        key_b = EncryptionKey(tenant=tenant_b, name="B Key")
        pt = EncryptionKey.generate_plaintext()
        key_b.set_secret(pt)
        key_b.save()
        resp = client_a.get(reverse("tenants:encryptionkey_detail", args=[key_b.pk]))
        assert resp.status_code == 404

    def test_rotate_key(self, client_a, encryption_key_a):
        key, old_pt = encryption_key_a
        old_hash = key.key_hash
        resp = client_a.post(reverse("tenants:encryptionkey_rotate", args=[key.pk]))
        assert resp.status_code == 302
        key.refresh_from_db()
        # Hash must have changed
        assert key.key_hash != old_hash

    def test_plaintext_shown_once_in_session(self, client_a, tenant_a):
        from apps.tenants.models import EncryptionKey
        resp = client_a.post(reverse("tenants:encryptionkey_create"), {"name": "Session Key"})
        assert resp.status_code == 302
        key = EncryptionKey.objects.get(tenant=tenant_a, name="Session Key")
        # Detail view should pop the session key and expose plaintext_once
        detail_resp = client_a.get(reverse("tenants:encryptionkey_detail", args=[key.pk]))
        assert detail_resp.status_code == 200
        assert detail_resp.context["plaintext_once"] is not None
        # Second visit: plaintext_once must be None (popped from session)
        detail_resp2 = client_a.get(reverse("tenants:encryptionkey_detail", args=[key.pk]))
        assert detail_resp2.context["plaintext_once"] is None


# ------------------------------------------------------------------ SubscriptionInvoice views
class TestSubscriptionInvoiceViews:
    def test_list_admin_200(self, client_a):
        resp = client_a.get(reverse("tenants:subscriptioninvoice_list"))
        assert resp.status_code == 200

    def test_list_cross_tenant_isolation(self, client_a, invoice_a, tenant_b, subscription_b):
        from apps.tenants.models import SubscriptionInvoice
        inv_b = SubscriptionInvoice.objects.create(
            tenant=tenant_b, subscription=subscription_b, status="paid", amount=99
        )
        resp = client_a.get(reverse("tenants:subscriptioninvoice_list"))
        pks = [i.pk for i in resp.context["object_list"]]
        assert invoice_a.pk in pks
        assert inv_b.pk not in pks

    def test_detail_cross_tenant_404(self, client_a, tenant_b, subscription_b):
        from apps.tenants.models import SubscriptionInvoice
        inv_b = SubscriptionInvoice.objects.create(
            tenant=tenant_b, subscription=subscription_b, status="open", amount=50
        )
        resp = client_a.get(reverse("tenants:subscriptioninvoice_detail", args=[inv_b.pk]))
        assert resp.status_code == 404


# ------------------------------------------------------------------ Branding views
class TestBrandingViews:
    def test_list_admin_200(self, client_a):
        resp = client_a.get(reverse("tenants:brandingsetting_list"))
        assert resp.status_code == 200

    def test_create_get_200(self, client_a):
        resp = client_a.get(reverse("tenants:brandingsetting_create"))
        assert resp.status_code == 200

    def test_create_post_saves(self, client_a, tenant_a):
        from apps.tenants.models import BrandingSetting
        resp = client_a.post(reverse("tenants:brandingsetting_create"), {
            "primary_color": "#2563eb",
            "accent_color": "#1d4ed8",
            "email_from_name": "NavERP",
            "email_footer": "",
        })
        assert resp.status_code == 302
        assert BrandingSetting.objects.filter(tenant=tenant_a).exists()

    def test_create_redirects_to_edit_if_exists(self, client_a, tenant_a):
        from apps.tenants.models import BrandingSetting
        b = BrandingSetting.objects.create(tenant=tenant_a)
        resp = client_a.get(reverse("tenants:brandingsetting_create"))
        assert resp.status_code == 302
        assert f"/{b.pk}/" in resp["Location"] or "edit" in resp["Location"]

    def test_member_blocked(self, member_client):
        resp = member_client.get(reverse("tenants:brandingsetting_list"))
        assert resp.status_code == 403


# ------------------------------------------------------------------ Onboarding
class TestOnboarding:
    def test_onboarding_get_200(self, client_a):
        resp = client_a.get(reverse("tenants:onboarding"))
        assert resp.status_code == 200

    def test_onboarding_post_creates_subscription(self, client_a, tenant_a):
        from apps.tenants.models import Subscription
        resp = client_a.post(reverse("tenants:onboarding"), {
            "plan": "starter",
            "seats": 5,
            "primary_color": "#2563eb",
            "accent_color": "#1d4ed8",
        })
        assert resp.status_code == 302
        assert Subscription.objects.filter(tenant=tenant_a).exists()
