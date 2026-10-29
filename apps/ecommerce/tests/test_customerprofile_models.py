"""Unit and invariant tests for eCommerce 9.6 Customer Account & Profile models.

Covers:
- CustomerAccountProfile
- CustomerAddressPreference
- CustomerWishlist
- CustomerWishlistItem
- CustomerPrivacyRequest

Naming conventions enforced:
- Test functions: test_customerprofile_*
- Module-level helpers: _customerprofile_*
"""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.models import Address, Party
from apps.ecommerce.models import (
    CustomerAccountProfile,
    CustomerAddressPreference,
    CustomerWishlist,
    CustomerWishlistItem,
    CustomerPrivacyRequest,
    CatalogProduct,
)
from apps.ecommerce.tests.conftest import (
    CUSTOMERPROFILE_MODEL_FIELDS,
    CUSTOMERPROFILE_CHOICES,
    _customerprofile_account,
    _customerprofile_address,
    _customerprofile_address_preference,
    _customerprofile_wishlist,
    _customerprofile_wishlist_item,
    _customerprofile_privacy_request,
    _productcatalog_product,
    _productcatalog_variant,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (_customerprofile_*)
# ==============================================================================

def _customerprofile_create_customer(tenant, name="Profile Customer"):
    return Party.objects.create(tenant=tenant, name=name, kind="person")


# ==============================================================================
# Contract Verification Tests
# ==============================================================================

def test_customerprofile_model_fields_contract():
    model_classes = {
        "CustomerAccountProfile": CustomerAccountProfile,
        "CustomerAddressPreference": CustomerAddressPreference,
        "CustomerWishlist": CustomerWishlist,
        "CustomerWishlistItem": CustomerWishlistItem,
        "CustomerPrivacyRequest": CustomerPrivacyRequest,
    }
    for model_name, expected_fields in CUSTOMERPROFILE_MODEL_FIELDS.items():
        cls = model_classes[model_name]
        actual_fields = {f.name for f in cls._meta.get_fields()}
        for field in expected_fields:
            assert field in actual_fields, f"Field '{field}' missing on {model_name}"


def test_customerprofile_choices_contract():
    assert tuple(CustomerAccountProfile.TIER_CHOICES) == CUSTOMERPROFILE_CHOICES["CustomerAccountProfile"]["tier"]
    assert tuple(CustomerAccountProfile.STATUS_CHOICES) == CUSTOMERPROFILE_CHOICES["CustomerAccountProfile"]["status"]
    assert tuple(CustomerAccountProfile.AUTH_MODE_CHOICES) == CUSTOMERPROFILE_CHOICES["CustomerAccountProfile"]["auth_mode"]
    assert tuple(CustomerAccountProfile.FREQUENCY_CHOICES) == CUSTOMERPROFILE_CHOICES["CustomerAccountProfile"]["notification_frequency"]

    assert tuple(CustomerAddressPreference.WINDOW_CHOICES) == CUSTOMERPROFILE_CHOICES["CustomerAddressPreference"]["preferred_delivery_window"]
    assert tuple(CustomerWishlist.VISIBILITY_CHOICES) == CUSTOMERPROFILE_CHOICES["CustomerWishlist"]["visibility"]
    assert tuple(CustomerWishlistItem.PRIORITY_CHOICES) == CUSTOMERPROFILE_CHOICES["CustomerWishlistItem"]["priority"]
    assert tuple(CustomerPrivacyRequest.REQUEST_TYPE_CHOICES) == CUSTOMERPROFILE_CHOICES["CustomerPrivacyRequest"]["request_type"]
    assert tuple(CustomerPrivacyRequest.STATUS_CHOICES) == CUSTOMERPROFILE_CHOICES["CustomerPrivacyRequest"]["status"]


# ==============================================================================
# CustomerAccountProfile Tests
# ==============================================================================

def test_customerprofile_account_creation_and_auto_number(tenant_a, ecom_customer_a):
    profile = _customerprofile_account(
        tenant_a,
        ecom_customer_a,
        tier="silver",
        auth_mode="passwordless_email",
        phone_number="+15551234567",
    )
    assert profile.pk is not None
    assert profile.number.startswith("ECAP-")
    assert profile.tier == "silver"
    assert profile.status == "active"
    assert profile.auth_mode == "passwordless_email"
    assert profile.unsubscribe_token != ""
    assert profile.number in str(profile)
    assert ecom_customer_a.name in str(profile)


def test_customerprofile_account_marketing_consent_timestamp(tenant_a):
    customer = _customerprofile_create_customer(tenant_a, name="Consent Customer")
    profile = CustomerAccountProfile(
        tenant=tenant_a,
        customer=customer,
        email_marketing_opt_in=True,
    )
    assert profile.marketing_consent_at is None
    profile.save()
    assert profile.marketing_consent_at is not None
    assert (timezone.now() - profile.marketing_consent_at).total_seconds() < 5


def test_customerprofile_account_unique_customer_per_tenant(tenant_a, ecom_customer_a):
    _customerprofile_account(tenant_a, ecom_customer_a)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CustomerAccountProfile.objects.create(
                tenant=tenant_a,
                customer=ecom_customer_a,
            )


def test_customerprofile_account_unique_number_per_tenant(tenant_a, ecom_customer_a):
    prof1 = _customerprofile_account(tenant_a, ecom_customer_a)
    cust2 = _customerprofile_create_customer(tenant_a, name="Second Customer")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CustomerAccountProfile.objects.create(
                tenant=tenant_a,
                number=prof1.number,
                customer=cust2,
            )


# ==============================================================================
# CustomerAddressPreference Tests
# ==============================================================================

def test_customerprofile_address_preference_creation_and_str(tenant_a, ecom_customer_a, ecom_address_a):
    pref = _customerprofile_address_preference(
        tenant_a,
        ecom_customer_a,
        ecom_address_a,
        label="Warehouse Dock",
        preferred_delivery_window="morning",
        requires_signature=True,
    )
    assert pref.pk is not None
    assert pref.number.startswith("ECAD-")
    assert pref.label == "Warehouse Dock"
    assert pref.preferred_delivery_window == "morning"
    assert pref.requires_signature is True
    assert pref.number in str(pref)
    assert "Warehouse Dock" in str(pref)


def test_customerprofile_address_preference_single_default_shipping(tenant_a, ecom_customer_a):
    addr1 = _customerprofile_address(tenant_a, ecom_customer_a, line1="10 First St")
    addr2 = _customerprofile_address(tenant_a, ecom_customer_a, line1="20 Second St")

    pref1 = _customerprofile_address_preference(
        tenant_a,
        ecom_customer_a,
        addr1,
        label="First",
        is_default_shipping=True,
        is_default_billing=False,
    )
    assert pref1.is_default_shipping is True

    pref2 = _customerprofile_address_preference(
        tenant_a,
        ecom_customer_a,
        addr2,
        label="Second",
        is_default_shipping=True,
        is_default_billing=False,
    )
    assert pref2.is_default_shipping is True

    pref1.refresh_from_db()
    assert pref1.is_default_shipping is False


def test_customerprofile_address_preference_single_default_billing(tenant_a, ecom_customer_a):
    addr1 = _customerprofile_address(tenant_a, ecom_customer_a, line1="30 Third St")
    addr2 = _customerprofile_address(tenant_a, ecom_customer_a, line1="40 Fourth St")

    pref1 = _customerprofile_address_preference(
        tenant_a,
        ecom_customer_a,
        addr1,
        label="Billing 1",
        is_default_shipping=False,
        is_default_billing=True,
    )
    assert pref1.is_default_billing is True

    pref2 = _customerprofile_address_preference(
        tenant_a,
        ecom_customer_a,
        addr2,
        label="Billing 2",
        is_default_shipping=False,
        is_default_billing=True,
    )
    assert pref2.is_default_billing is True

    pref1.refresh_from_db()
    assert pref1.is_default_billing is False


def test_customerprofile_address_preference_unique_number(tenant_a, ecom_customer_a, ecom_address_a):
    pref1 = _customerprofile_address_preference(tenant_a, ecom_customer_a, ecom_address_a)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CustomerAddressPreference.objects.create(
                tenant=tenant_a,
                number=pref1.number,
                customer=ecom_customer_a,
                address=ecom_address_a,
            )


# ==============================================================================
# CustomerWishlist & CustomerWishlistItem Tests
# ==============================================================================

def test_customerprofile_wishlist_creation_and_auto_slug(tenant_a, ecom_customer_a):
    wishlist = _customerprofile_wishlist(
        tenant_a,
        ecom_customer_a,
        name="Holiday Gift Ideas 2026",
        visibility="shared",
    )
    assert wishlist.pk is not None
    assert wishlist.number.startswith("EWSL-")
    assert wishlist.slug == "holiday-gift-ideas-2026"
    assert wishlist.share_token != ""
    assert wishlist.visibility == "shared"
    assert wishlist.number in str(wishlist)


def test_customerprofile_wishlist_single_default_unsets_previous(tenant_a, ecom_customer_a):
    w1 = _customerprofile_wishlist(tenant_a, ecom_customer_a, name="Wishlist 1", is_default=True)
    assert w1.is_default is True

    w2 = _customerprofile_wishlist(tenant_a, ecom_customer_a, name="Wishlist 2", is_default=True)
    assert w2.is_default is True

    w1.refresh_from_db()
    assert w1.is_default is False


def test_customerprofile_wishlist_item_creation_and_str(tenant_a, ecom_wishlist_a, ecom_product_a, ecom_variant_a):
    item = _customerprofile_wishlist_item(
        tenant_a,
        ecom_wishlist_a,
        ecom_product_a,
        variant=ecom_variant_a,
        desired_quantity=3,
        priority="highest",
        comment="Must have for launch",
    )
    assert item.pk is not None
    assert item.desired_quantity == 3
    assert item.priority == "highest"
    assert item.comment == "Must have for launch"
    assert ecom_wishlist_a.name in str(item)
    assert ecom_product_a.name in str(item)
    assert "x3" in str(item)


def test_customerprofile_wishlist_unique_number(tenant_a, ecom_customer_a):
    w1 = _customerprofile_wishlist(tenant_a, ecom_customer_a, name="W1")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CustomerWishlist.objects.create(
                tenant=tenant_a,
                number=w1.number,
                customer=ecom_customer_a,
                name="W_Dup",
            )


# ==============================================================================
# CustomerPrivacyRequest Tests
# ==============================================================================

def test_customerprofile_privacy_request_creation_and_deadline(tenant_a, ecom_customer_a):
    req = _customerprofile_privacy_request(
        tenant_a,
        ecom_customer_a,
        request_type="erasure_anonymize",
    )
    assert req.pk is not None
    assert req.number.startswith("ECPR-")
    assert req.status == "received"
    assert req.statutory_deadline is not None
    assert req.statutory_deadline >= (timezone.now() + timedelta(days=28)).date()
    assert req.completed_at is None
    assert req.number in str(req)


def test_customerprofile_privacy_request_completed_at_auto_set(tenant_a, ecom_customer_a):
    req = _customerprofile_privacy_request(
        tenant_a,
        ecom_customer_a,
        request_type="access_export",
        status="received",
    )
    assert req.completed_at is None

    req.status = "completed"
    req.save()
    assert req.completed_at is not None
    assert (timezone.now() - req.completed_at).total_seconds() < 5


def test_customerprofile_privacy_request_unique_number(tenant_a, ecom_customer_a):
    req1 = _customerprofile_privacy_request(tenant_a, ecom_customer_a)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CustomerPrivacyRequest.objects.create(
                tenant=tenant_a,
                number=req1.number,
                customer=ecom_customer_a,
            )
