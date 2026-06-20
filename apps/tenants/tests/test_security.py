"""Security tests for tenants app: CSRF, IDOR, Stripe webhook integrity."""
import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


class TestCSRFOnTenantViews:
    def test_mark_paid_enforces_csrf(self, admin_user, subscription_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("tenants:subscription_mark_paid", args=[subscription_a.pk]))
        assert resp.status_code == 403

    def test_subscription_delete_enforces_csrf(self, admin_user, subscription_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("tenants:subscription_delete", args=[subscription_a.pk]))
        assert resp.status_code == 403

    def test_encryptionkey_rotate_enforces_csrf(self, admin_user, encryption_key_a):
        key, _ = encryption_key_a
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("tenants:encryptionkey_rotate", args=[key.pk]))
        assert resp.status_code == 403


class TestMemberBlocked:
    """Non-admin members must receive 403 on all tenant admin views."""

    PROTECTED_URLS = [
        ("tenants:subscription_list", []),
        ("tenants:subscription_create", []),
        ("tenants:subscriptioninvoice_list", []),
        ("tenants:brandingsetting_list", []),
        ("tenants:encryptionkey_list", []),
        ("tenants:healthmetric_list", []),
    ]

    @pytest.mark.parametrize("url_name,args", [
        ("tenants:subscription_list", []),
        ("tenants:subscription_create", []),
        ("tenants:subscriptioninvoice_list", []),
        ("tenants:brandingsetting_list", []),
        ("tenants:encryptionkey_list", []),
        ("tenants:healthmetric_list", []),
    ])
    def test_member_blocked(self, member_client, url_name, args):
        resp = member_client.get(reverse(url_name, args=args))
        assert resp.status_code == 403


class TestAnonymousBlocked:
    @pytest.mark.parametrize("url_name,args", [
        ("tenants:subscription_list", []),
        ("tenants:encryptionkey_list", []),
        ("tenants:brandingsetting_list", []),
        ("tenants:healthmetric_list", []),
    ])
    def test_anon_redirected(self, client, url_name, args):
        resp = client.get(reverse(url_name, args=args))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestStripeWebhookSecurity:
    """Stripe webhook must reject unsigned/tampered payloads."""

    def test_no_payload_returns_400(self, client):
        resp = client.post(
            reverse("tenants:stripe_webhook"),
            content_type="application/json",
            data=b"",
        )
        assert resp.status_code == 400

    def test_get_method_not_allowed(self, client):
        resp = client.get(reverse("tenants:stripe_webhook"))
        assert resp.status_code == 405

    def test_invalid_json_returns_400(self, client):
        resp = client.post(
            reverse("tenants:stripe_webhook"),
            content_type="application/json",
            data=b"not-json",
        )
        assert resp.status_code == 400


class TestEncryptionKeySecurityInvariant:
    """Plaintext must never be retrievable from the database."""

    def test_key_hash_is_sha256(self, encryption_key_a):
        import hashlib
        key, plaintext = encryption_key_a
        expected = hashlib.sha256(plaintext.encode()).hexdigest()
        assert key.key_hash == expected

    def test_plaintext_not_in_database_fields(self, encryption_key_a):
        key, plaintext = encryption_key_a
        key.refresh_from_db()
        # The actual key body (after "nk_") must not appear in any stored field
        key_body = plaintext[3:]  # strip "nk_"
        assert key_body not in key.prefix
        assert key_body not in key.key_hash

    def test_edit_form_does_not_expose_secret(self, tenant_a, encryption_key_a):
        from apps.tenants.forms import EncryptionKeyForm
        key, _ = encryption_key_a
        form = EncryptionKeyForm(instance=key, tenant=tenant_a)
        assert "prefix" not in form.fields
        assert "key_hash" not in form.fields

    def test_generate_plaintext_has_min_entropy(self):
        from apps.tenants.models import EncryptionKey
        # Must be at least 32 chars beyond "nk_" prefix for adequate entropy
        pt = EncryptionKey.generate_plaintext()
        assert len(pt) >= 35  # "nk_" (3) + at least 32 chars of token
