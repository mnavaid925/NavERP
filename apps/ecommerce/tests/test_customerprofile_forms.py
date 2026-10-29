"""Form validation, exclusion, and tenant isolation tests for eCommerce 9.6 Customer Profile.

Covers:
- CustomerAccountProfileForm
- CustomerAddressPreferenceForm
- CustomerWishlistForm
- CustomerWishlistItemForm
- CustomerPrivacyRequestForm

Naming conventions enforced:
- Test functions: test_customerprofile_*
- Module-level helpers: _customerprofile_*
"""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.utils import timezone

from apps.accounting.models.GeneralLedger.Currencies import Currency
from apps.core.models import Address, Party
from apps.ecommerce.forms.CustomerProfile.CustomerAccountProfiles import CustomerAccountProfileForm
from apps.ecommerce.forms.CustomerProfile.CustomerAddressPreferences import CustomerAddressPreferenceForm
from apps.ecommerce.forms.CustomerProfile.CustomerWishlists import (
    CustomerWishlistForm,
    CustomerWishlistItemForm,
)
from apps.ecommerce.forms.CustomerProfile.CustomerPrivacyRequests import CustomerPrivacyRequestForm
from apps.ecommerce.models import (
    CustomerAccountProfile,
    CustomerAddressPreference,
    CustomerWishlist,
    CustomerWishlistItem,
    CustomerPrivacyRequest,
)
from apps.ecommerce.tests.conftest import (
    CUSTOMERPROFILE_FORM_FIELDS,
    _customerprofile_account,
    _customerprofile_address,
    _customerprofile_wishlist,
    _productcatalog_product,
    _productcatalog_variant,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (_customerprofile_*)
# ==============================================================================

def _customerprofile_create_customer(tenant, name="Form Customer"):
    return Party.objects.create(tenant=tenant, name=name, kind="person")


# ==============================================================================
# Form Contract & Exclusion Tests
# ==============================================================================

def test_customerprofile_form_fields_contract():
    form_classes = {
        "CustomerAccountProfileForm": CustomerAccountProfileForm,
        "CustomerAddressPreferenceForm": CustomerAddressPreferenceForm,
        "CustomerWishlistForm": CustomerWishlistForm,
        "CustomerWishlistItemForm": CustomerWishlistItemForm,
        "CustomerPrivacyRequestForm": CustomerPrivacyRequestForm,
    }
    for form_name, expected_fields in CUSTOMERPROFILE_FORM_FIELDS.items():
        cls = form_classes[form_name]
        actual_fields = tuple(cls.Meta.fields)
        assert actual_fields == expected_fields, f"Field mismatch on {form_name}"


def test_customerprofile_form_exclusions_prevent_mass_assignment():
    # CustomerAccountProfileForm
    acc_fields = CustomerAccountProfileForm.Meta.fields
    for forbidden in ("tenant", "number", "total_spent", "order_count", "last_order_at", "marketing_consent_at", "unsubscribe_token"):
        assert forbidden not in acc_fields, f"{forbidden} must be excluded from CustomerAccountProfileForm"

    # CustomerAddressPreferenceForm
    pref_fields = CustomerAddressPreferenceForm.Meta.fields
    for forbidden in ("tenant", "number"):
        assert forbidden not in pref_fields, f"{forbidden} must be excluded from CustomerAddressPreferenceForm"

    # CustomerWishlistForm
    wsh_fields = CustomerWishlistForm.Meta.fields
    for forbidden in ("tenant", "number", "share_token"):
        assert forbidden not in wsh_fields, f"{forbidden} must be excluded from CustomerWishlistForm"

    # CustomerWishlistItemForm
    item_fields = CustomerWishlistItemForm.Meta.fields
    assert "tenant" not in item_fields, "tenant must be excluded from CustomerWishlistItemForm"

    # CustomerPrivacyRequestForm (status removed per Finding I11)
    req_fields = CustomerPrivacyRequestForm.Meta.fields
    for forbidden in ("tenant", "number", "completed_at", "data_export_payload", "status"):
        assert forbidden not in req_fields, f"{forbidden} must be excluded from CustomerPrivacyRequestForm"


# ==============================================================================
# CustomerAccountProfileForm Tests
# ==============================================================================

def test_customerprofile_account_form_valid(tenant_a, ecom_customer_a):
    form_data = {
        "customer": ecom_customer_a.pk,
        "tier": "gold",
        "status": "active",
        "auth_mode": "phone_otp",
        "phone_number": "+1234567890",
        "phone_verified": True,
        "preferred_language": "en",
        "email_marketing_opt_in": True,
        "sms_marketing_opt_in": False,
        "notification_frequency": "weekly_digest",
        "internal_notes": "Valued VIP shopper",
    }
    form = CustomerAccountProfileForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()
    assert instance.pk is not None
    assert instance.tier == "gold"
    assert instance.auth_mode == "phone_otp"


def test_customerprofile_account_form_tenant_scoped_customers(tenant_a, tenant_b, ecom_customer_b):
    # Foreign customer from tenant_b submitted in tenant_a form
    form_data = {
        "customer": ecom_customer_b.pk,
        "tier": "bronze",
        "status": "active",
        "auth_mode": "password",
        "phone_number": "",
        "notification_frequency": "all",
    }
    form = CustomerAccountProfileForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "customer" in form.errors


# ==============================================================================
# CustomerAddressPreferenceForm Tests
# ==============================================================================

def test_customerprofile_address_preference_form_valid(tenant_a, ecom_customer_a, ecom_address_a):
    form_data = {
        "customer": ecom_customer_a.pk,
        "address": ecom_address_a.pk,
        "label": "Main Office",
        "is_default_shipping": True,
        "is_default_billing": False,
        "recipient_name": "Acme Purchasing",
        "contact_phone": "+15559876543",
        "delivery_instructions": "Leave at front desk",
        "preferred_delivery_window": "afternoon",
        "requires_signature": True,
    }
    form = CustomerAddressPreferenceForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()
    assert instance.pk is not None
    assert instance.preferred_delivery_window == "afternoon"
    assert instance.requires_signature is True


def test_customerprofile_address_preference_form_cross_party_address_rejected(tenant_a, ecom_customer_a):
    other_customer = _customerprofile_create_customer(tenant_a, name="Other Cust")
    other_address = _customerprofile_address(tenant_a, other_customer, line1="777 Alien Way")

    form_data = {
        "customer": ecom_customer_a.pk,
        "address": other_address.pk,
        "label": "Wrong Address",
        "is_default_shipping": False,
        "is_default_billing": False,
        "preferred_delivery_window": "anytime",
    }
    form = CustomerAddressPreferenceForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "address" in form.errors
    assert "belong to this customer" in str(form.errors["address"]).lower()


# ==============================================================================
# CustomerWishlistForm & ItemForm Tests
# ==============================================================================

def test_customerprofile_wishlist_form_valid(tenant_a, ecom_customer_a):
    form_data = {
        "customer": ecom_customer_a.pk,
        "name": "Summer Wishlist",
        "slug": "summer-wishlist",
        "visibility": "shared",
        "is_default": False,
        "notes": "Items to purchase in July",
    }
    form = CustomerWishlistForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()
    assert instance.pk is not None
    assert instance.name == "Summer Wishlist"
    assert instance.visibility == "shared"


def test_customerprofile_wishlist_item_form_valid(tenant_a, ecom_wishlist_a, ecom_product_a, ecom_variant_a):
    form_data = {
        "wishlist": ecom_wishlist_a.pk,
        "product": ecom_product_a.pk,
        "variant": ecom_variant_a.pk,
        "desired_quantity": 2,
        "priority": "high",
        "comment": "Birthday gift idea",
    }
    form = CustomerWishlistItemForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()
    assert instance.pk is not None
    assert instance.priority == "high"
    assert instance.desired_quantity == 2


def test_customerprofile_wishlist_item_form_mismatched_variant_rejected(tenant_a, ecom_wishlist_a, ecom_product_a):
    prod2 = _productcatalog_product(tenant_a, name="Unrelated Product")
    var2 = _productcatalog_variant(tenant_a, prod2, name="Other Variant", price=Decimal("15.00"))

    # Pass product_a with variant from product 2
    form_data = {
        "wishlist": ecom_wishlist_a.pk,
        "product": ecom_product_a.pk,
        "variant": var2.pk,
        "desired_quantity": 1,
        "priority": "medium",
    }
    form = CustomerWishlistItemForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "variant" in form.errors
    assert "does not belong" in str(form.errors["variant"]).lower() or "belongs to" in str(form.errors["variant"]).lower()


def test_customerprofile_wishlist_item_form_negative_quantity_rejected(tenant_a, ecom_wishlist_a, ecom_product_a):
    form_data = {
        "wishlist": ecom_wishlist_a.pk,
        "product": ecom_product_a.pk,
        "desired_quantity": -5,
        "priority": "medium",
    }
    form = CustomerWishlistItemForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "desired_quantity" in form.errors


# ==============================================================================
# CustomerPrivacyRequestForm Tests
# ==============================================================================

def test_customerprofile_privacy_request_form_valid(tenant_a, ecom_customer_a):
    deadline = (timezone.now() + timedelta(days=25)).date()
    form_data = {
        "customer": ecom_customer_a.pk,
        "request_type": "access_export",
        "requested_by_email": "dpo-agent@example.com",
        "verification_method": "account_login",
        "statutory_deadline": deadline.isoformat(),
        "resolution_notes": "Identity confirmed via 2FA login",
    }
    form = CustomerPrivacyRequestForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()
    assert instance.pk is not None
    assert instance.requested_by_email == "dpo-agent@example.com"
    assert instance.status == "received"
