"""Tests for tenants forms: secret/derived fields excluded, validators."""
import pytest

pytestmark = pytest.mark.django_db


class TestEncryptionKeyForm:
    def test_only_name_field(self, tenant_a):
        from apps.tenants.forms import EncryptionKeyForm
        form = EncryptionKeyForm(tenant=tenant_a)
        assert list(form.fields.keys()) == ["name"]

    def test_prefix_not_in_form(self, tenant_a):
        from apps.tenants.forms import EncryptionKeyForm
        form = EncryptionKeyForm(tenant=tenant_a)
        assert "prefix" not in form.fields

    def test_key_hash_not_in_form(self, tenant_a):
        from apps.tenants.forms import EncryptionKeyForm
        form = EncryptionKeyForm(tenant=tenant_a)
        assert "key_hash" not in form.fields

    def test_last_rotated_at_not_in_form(self, tenant_a):
        from apps.tenants.forms import EncryptionKeyForm
        form = EncryptionKeyForm(tenant=tenant_a)
        assert "last_rotated_at" not in form.fields

    def test_valid_form(self, tenant_a):
        from apps.tenants.forms import EncryptionKeyForm
        form = EncryptionKeyForm({"name": "My Key"}, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_name_required(self, tenant_a):
        from apps.tenants.forms import EncryptionKeyForm
        form = EncryptionKeyForm({"name": ""}, tenant=tenant_a)
        assert not form.is_valid()
        assert "name" in form.errors

    def test_tenant_not_in_form(self, tenant_a):
        from apps.tenants.forms import EncryptionKeyForm
        form = EncryptionKeyForm(tenant=tenant_a)
        assert "tenant" not in form.fields


class TestSubscriptionInvoiceForm:
    def test_number_not_a_form_field(self, tenant_a):
        from apps.tenants.forms import SubscriptionInvoiceForm
        form = SubscriptionInvoiceForm(tenant=tenant_a)
        assert "number" not in form.fields

    def test_paid_at_not_a_form_field(self, tenant_a):
        from apps.tenants.forms import SubscriptionInvoiceForm
        form = SubscriptionInvoiceForm(tenant=tenant_a)
        assert "paid_at" not in form.fields

    def test_stripe_invoice_id_not_a_form_field(self, tenant_a):
        from apps.tenants.forms import SubscriptionInvoiceForm
        form = SubscriptionInvoiceForm(tenant=tenant_a)
        assert "stripe_invoice_id" not in form.fields

    def test_tenant_not_a_form_field(self, tenant_a):
        from apps.tenants.forms import SubscriptionInvoiceForm
        form = SubscriptionInvoiceForm(tenant=tenant_a)
        assert "tenant" not in form.fields

    def test_valid_form_with_subscription(self, tenant_a, subscription_a):
        from apps.tenants.forms import SubscriptionInvoiceForm
        import datetime
        form = SubscriptionInvoiceForm({
            "subscription": subscription_a.pk,
            "status": "open",
            "amount": "29.99",
            "issued_on": "2024-01-01",
            "due_on": "2024-01-31",
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors


class TestSubscriptionForm:
    def test_stripe_fields_not_in_form(self, tenant_a):
        from apps.tenants.forms import SubscriptionForm
        form = SubscriptionForm(tenant=tenant_a)
        assert "stripe_customer_id" not in form.fields
        assert "stripe_subscription_id" not in form.fields

    def test_tenant_not_a_form_field(self, tenant_a):
        from apps.tenants.forms import SubscriptionForm
        form = SubscriptionForm(tenant=tenant_a)
        assert "tenant" not in form.fields

    def test_valid_form(self, tenant_a):
        from apps.tenants.forms import SubscriptionForm
        form = SubscriptionForm({
            "plan": "starter",
            "status": "trialing",
            "billing_cycle": "monthly",
            "amount": "29.99",
            "seats": 5,
            "started_on": "",
            "renews_on": "",
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors


class TestBrandingSettingForm:
    def test_logo_optional(self, tenant_a):
        from apps.tenants.forms import BrandingSettingForm
        form = BrandingSettingForm({
            "primary_color": "#2563eb",
            "accent_color": "#1d4ed8",
            "email_from_name": "",
            "email_footer": "",
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_invalid_hex_color_fails(self, tenant_a):
        from apps.tenants.forms import BrandingSettingForm
        form = BrandingSettingForm({
            "primary_color": "red;}INJECTION",
            "accent_color": "#1d4ed8",
            "email_from_name": "",
            "email_footer": "",
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert "primary_color" in form.errors

    def test_tenant_not_a_form_field(self, tenant_a):
        from apps.tenants.forms import BrandingSettingForm
        form = BrandingSettingForm(tenant=tenant_a)
        assert "tenant" not in form.fields
