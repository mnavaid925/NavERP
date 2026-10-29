# Contract — Sub-module 9.6: Customer Account & Profile (Module 9: eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.6 Customer Account & Profile · **Module:** 9 eCommerce Management System · **App:** `apps/ecommerce`
- **Date:** 2026-10-29 · **Status:** FROZEN PRE-BUILD CONTRACT · **Phase:** 3.1 Spec
- **App Status:** Extending existing `apps/ecommerce/`. Next incremental migration: `0006_...`
- **Package Layout:** `CustomerProfile/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/ecommerce/customerprofile/`.

---

## 1. Models & CHOICES Contract

All top-level models inherit from `apps.ecommerce.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).
Child model `CustomerWishlistItem` inherits from `apps.ecommerce.models._base.TenantOwned` (`tenant`, `created_at`, `updated_at`).

### 1.1 `CustomerAccountProfile` (`apps/ecommerce/models/CustomerProfile/CustomerAccountProfiles.py`)
- **Table:** `ecommerce_customer_account_profile`
- **Number Prefix:** `ECAP` (`ECAP-00001`)
- **CHOICES:**
  - `TIER_CHOICES = [('bronze', 'Bronze'), ('silver', 'Silver'), ('gold', 'Gold'), ('platinum', 'Platinum'), ('vip', 'VIP')]`
  - `STATUS_CHOICES = [('active', 'Active'), ('pending_verification', 'Pending Verification'), ('suspended', 'Suspended'), ('locked', 'Locked'), ('anonymized', 'Anonymized / GDPR Erased')]`
  - `AUTH_MODE_CHOICES = [('password', 'Email / Password'), ('passwordless_email', 'Passwordless Email Magic Link'), ('phone_otp', 'Phone SMS OTP'), ('sso_oauth', 'Single Sign-On (SSO / OAuth)')]`
  - `FREQUENCY_CHOICES = [('all', 'All Communications'), ('weekly_digest', 'Weekly Digest'), ('promotions_only', 'Promotions & Offers Only')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `customer`: `ForeignKey('core.Party', on_delete=PROTECT, related_name='ecommerce_profiles')`
  - `user`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=SET_NULL, related_name='ecommerce_customer_profiles')`
  - `tier`: `CharField(max_length=20, choices=TIER_CHOICES, default='bronze')`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default='active')`
  - `auth_mode`: `CharField(max_length=25, choices=AUTH_MODE_CHOICES, default='password')`
  - `phone_number`: `CharField(max_length=32, blank=True)`
  - `phone_verified`: `BooleanField(default=False)`
  - `preferred_currency`: `ForeignKey('accounting.Currency', null=True, blank=True, on_delete=SET_NULL, related_name='ecommerce_customer_profiles')`
  - `preferred_language`: `CharField(max_length=10, default='en')`
  - `email_marketing_opt_in`: `BooleanField(default=False)`
  - `sms_marketing_opt_in`: `BooleanField(default=False)`
  - `notification_frequency`: `CharField(max_length=20, choices=FREQUENCY_CHOICES, default='all')`
  - `marketing_consent_at`: `DateTimeField(null=True, blank=True)`
  - `unsubscribe_token`: `CharField(max_length=64, blank=True, default='')`
  - `total_spent`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `order_count`: `PositiveIntegerField(default=0)`
  - `last_order_at`: `DateTimeField(null=True, blank=True)`
  - `internal_notes`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Indexes:**
  - `models.Index(fields=['tenant', 'tier'], name='idx_ecap_ten_tier')`
  - `models.Index(fields=['tenant', 'status'], name='idx_ecap_ten_stat')`
  - `models.Index(fields=['tenant', 'customer'], name='idx_ecap_ten_cust')`

---

### 1.2 `CustomerAddressPreference` (`apps/ecommerce/models/CustomerProfile/CustomerAddressPreferences.py`)
- **Table:** `ecommerce_customer_address_preference`
- **Number Prefix:** `ECAD` (`ECAD-00001`)
- **CHOICES:**
  - `WINDOW_CHOICES = [('anytime', 'Anytime (Standard)'), ('morning', 'Morning (8 AM - 12 PM)'), ('afternoon', 'Afternoon (12 PM - 5 PM)'), ('evening', 'Evening (5 PM - 9 PM)'), ('weekend', 'Weekend Only')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `customer`: `ForeignKey('core.Party', on_delete=PROTECT, related_name='ecommerce_address_preferences')`
  - `address`: `ForeignKey('core.Address', on_delete=CASCADE, related_name='ecommerce_preferences')`
  - `label`: `CharField(max_length=50, default='Home')`
  - `is_default_shipping`: `BooleanField(default=False)`
  - `is_default_billing`: `BooleanField(default=False)`
  - `recipient_name`: `CharField(max_length=150, blank=True)`
  - `contact_phone`: `CharField(max_length=32, blank=True)`
  - `delivery_instructions`: `TextField(blank=True)`
  - `preferred_delivery_window`: `CharField(max_length=20, choices=WINDOW_CHOICES, default='anytime')`
  - `requires_signature`: `BooleanField(default=False)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Indexes:**
  - `models.Index(fields=['tenant', 'customer'], name='idx_ecad_ten_cust')`
  - `models.Index(fields=['tenant', 'is_default_shipping'], name='idx_ecad_ten_def_shp')`
  - `models.Index(fields=['tenant', 'is_default_billing'], name='idx_ecad_ten_def_bil')`

---

### 1.3 `CustomerWishlist` & `CustomerWishlistItem` (`apps/ecommerce/models/CustomerProfile/CustomerWishlists.py`)
- **Table:** `ecommerce_customer_wishlist` & `ecommerce_customer_wishlist_item`
- **Number Prefix:** `EWSL` (`EWSL-00001`)
- **CHOICES:**
  - `VISIBILITY_CHOICES = [('private', 'Private (Only Me)'), ('shared', 'Shared (Link Access)'), ('public', 'Public (Searchable)')]`
  - `PRIORITY_CHOICES = [('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('highest', 'Must Have')]`
- **Fields (`CustomerWishlist`):**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `customer`: `ForeignKey('core.Party', on_delete=PROTECT, related_name='ecommerce_wishlists')`
  - `name`: `CharField(max_length=120, default='My Wishlist')`
  - `slug`: `SlugField(max_length=140, blank=True)`
  - `visibility`: `CharField(max_length=20, choices=VISIBILITY_CHOICES, default='private')`
  - `is_default`: `BooleanField(default=True)`
  - `share_token`: `CharField(max_length=64, blank=True, default='')`
  - `notes`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Fields (`CustomerWishlistItem`):**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `wishlist`: `ForeignKey('ecommerce.CustomerWishlist', on_delete=CASCADE, related_name='items')`
  - `product`: `ForeignKey('ecommerce.CatalogProduct', on_delete=CASCADE, related_name='wishlist_items')`
  - `variant`: `ForeignKey('ecommerce.ProductVariant', null=True, blank=True, on_delete=SET_NULL, related_name='wishlist_items')`
  - `desired_quantity`: `PositiveIntegerField(default=1)`
  - `priority`: `CharField(max_length=15, choices=PRIORITY_CHOICES, default='medium')`
  - `comment`: `CharField(max_length=255, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Indexes:**
  - `models.Index(fields=['tenant', 'customer'], name='idx_ewsl_ten_cust')`
  - `models.Index(fields=['tenant', 'share_token'], name='idx_ewsl_ten_token')`
  - `models.Index(fields=['tenant', 'wishlist'], name='idx_ewsi_ten_wish')`
  - `models.Index(fields=['tenant', 'product'], name='idx_ewsi_ten_prod')`

---

### 1.4 `CustomerPrivacyRequest` (`apps/ecommerce/models/CustomerProfile/CustomerPrivacyRequests.py`)
- **Table:** `ecommerce_customer_privacy_request`
- **Number Prefix:** `ECPR` (`ECPR-00001`)
- **CHOICES:**
  - `REQUEST_TYPE_CHOICES = [('access_export', 'Right of Access / Data Portability (JSON Export)'), ('rectification', 'Right to Rectification (Correct Data)'), ('erasure_anonymize', 'Right to Erasure (GDPR Account Anonymization)'), ('restriction', 'Right to Restriction of Processing'), ('opt_out_sale', 'Do Not Sell / Share My Data (CCPA)')]`
  - `STATUS_CHOICES = [('received', 'Received / Awaiting Identity Verification'), ('identity_verified', 'Identity Verified'), ('processing', 'Processing Data Query / Erasure'), ('completed', 'Completed & Delivered'), ('rejected', 'Rejected / Legally Exempt')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `customer`: `ForeignKey('core.Party', on_delete=PROTECT, related_name='ecommerce_privacy_requests')`
  - `request_type`: `CharField(max_length=25, choices=REQUEST_TYPE_CHOICES, default='access_export')`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default='received')`
  - `statutory_deadline`: `DateField(null=True, blank=True)`
  - `completed_at`: `DateTimeField(null=True, blank=True)`
  - `requested_by_email`: `EmailField(blank=True)`
  - `verification_method`: `CharField(max_length=50, blank=True, default='account_login')`
  - `data_export_payload`: `JSONField(null=True, blank=True)`
  - `resolution_notes`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Indexes:**
  - `models.Index(fields=['tenant', 'customer'], name='idx_ecpr_ten_cust')`
  - `models.Index(fields=['tenant', 'status'], name='idx_ecpr_ten_stat')`
  - `models.Index(fields=['tenant', 'request_type'], name='idx_ecpr_ten_type')`

---

## 2. Forms Contract (`apps/ecommerce/forms/CustomerProfile/`)

### 2.1 `CustomerAccountProfileForm`
- **File:** `apps/ecommerce/forms/CustomerProfile/CustomerAccountProfiles.py`
- **Model:** `CustomerAccountProfile`
- **Fields:** `['customer', 'user', 'tier', 'status', 'auth_mode', 'phone_number', 'phone_verified', 'preferred_currency', 'preferred_language', 'email_marketing_opt_in', 'sms_marketing_opt_in', 'notification_frequency', 'internal_notes']`
- **Excluded:** `tenant`, `number`, `total_spent`, `order_count`, `last_order_at`, `marketing_consent_at`, `unsubscribe_token`

### 2.2 `CustomerAddressPreferenceForm`
- **File:** `apps/ecommerce/forms/CustomerProfile/CustomerAddressPreferences.py`
- **Model:** `CustomerAddressPreference`
- **Fields:** `['customer', 'address', 'label', 'is_default_shipping', 'is_default_billing', 'recipient_name', 'contact_phone', 'delivery_instructions', 'preferred_delivery_window', 'requires_signature']`
- **Excluded:** `tenant`, `number`

### 2.3 `CustomerWishlistForm` & `CustomerWishlistItemForm`
- **File:** `apps/ecommerce/forms/CustomerProfile/CustomerWishlists.py`
- **Model:** `CustomerWishlist`
- **Fields:** `['customer', 'name', 'slug', 'visibility', 'is_default', 'notes']`
- **Excluded:** `tenant`, `number`, `share_token`
- **Item Form Model:** `CustomerWishlistItem`
- **Item Form Fields:** `['wishlist', 'product', 'variant', 'desired_quantity', 'priority', 'comment']`
- **Item Form Excluded:** `tenant`

### 2.4 `CustomerPrivacyRequestForm`
- **File:** `apps/ecommerce/forms/CustomerProfile/CustomerPrivacyRequests.py`
- **Model:** `CustomerPrivacyRequest`
- **Fields:** `['customer', 'request_type', 'status', 'requested_by_email', 'verification_method', 'statutory_deadline', 'resolution_notes']`
- **Excluded:** `tenant`, `number`, `completed_at`, `data_export_payload`

---

## 3. URLs & Views Contract (`apps/ecommerce/urls/CustomerProfile/`)

`app_name = 'ecommerce'`

| View Name | Route | HTTP Methods | View Function | Key Context Dict Entries |
|---|---|---|---|---|
| `customeraccountprofile_list` | `customer-profiles/` | GET | `customeraccountprofile_list` | `profiles`, `status_choices`, `tier_choices`, `auth_mode_choices`, `page_obj`, `is_paginated`, `q` |
| `customeraccountprofile_detail` | `customer-profiles/<int:pk>/` | GET | `customeraccountprofile_detail` | `profile`, `recent_orders`, `address_preferences`, `wishlists`, `privacy_requests` |
| `customeraccountprofile_create` | `customer-profiles/create/` | GET, POST | `customeraccountprofile_create` | `form`, `customers` |
| `customeraccountprofile_edit` | `customer-profiles/<int:pk>/edit/` | GET, POST | `customeraccountprofile_edit` | `form`, `profile`, `customers` |
| `customeraccountprofile_delete` | `customer-profiles/<int:pk>/delete/` | POST | `customeraccountprofile_delete` | `profile` |
| `customeraddresspreference_list` | `address-preferences/` | GET | `customeraddresspreference_list` | `preferences`, `window_choices`, `page_obj`, `is_paginated`, `q` |
| `customeraddresspreference_detail` | `address-preferences/<int:pk>/` | GET | `customeraddresspreference_detail` | `preference` |
| `customeraddresspreference_create` | `address-preferences/create/` | GET, POST | `customeraddresspreference_create` | `form`, `customers`, `addresses` |
| `customeraddresspreference_edit` | `address-preferences/<int:pk>/edit/` | GET, POST | `customeraddresspreference_edit` | `form`, `preference`, `customers`, `addresses` |
| `customeraddresspreference_delete` | `address-preferences/<int:pk>/delete/` | POST | `customeraddresspreference_delete` | `preference` |
| `customerwishlist_list` | `wishlists/` | GET | `customerwishlist_list` | `wishlists`, `visibility_choices`, `page_obj`, `is_paginated`, `q` |
| `customerwishlist_detail` | `wishlists/<int:pk>/` | GET | `customerwishlist_detail` | `wishlist`, `items`, `products`, `priority_choices` |
| `customerwishlist_create` | `wishlists/create/` | GET, POST | `customerwishlist_create` | `form`, `customers` |
| `customerwishlist_edit` | `wishlists/<int:pk>/edit/` | GET, POST | `customerwishlist_edit` | `form`, `wishlist`, `customers` |
| `customerwishlist_delete` | `wishlists/<int:pk>/delete/` | POST | `customerwishlist_delete` | `wishlist` |
| `customerwishlist_item_add` | `wishlists/<int:pk>/items/add/` | POST | `customerwishlist_item_add` | Redirect to `customerwishlist_detail` |
| `customerwishlist_item_delete` | `wishlists/items/<int:item_pk>/delete/` | POST | `customerwishlist_item_delete` | Redirect to `customerwishlist_detail` |
| `customerprivacyrequest_list` | `privacy-requests/` | GET | `customerprivacyrequest_list` | `requests`, `type_choices`, `status_choices`, `page_obj`, `is_paginated`, `q` |
| `customerprivacyrequest_detail` | `privacy-requests/<int:pk>/` | GET | `customerprivacyrequest_detail` | `privacy_request` |
| `customerprivacyrequest_create` | `privacy-requests/create/` | GET, POST | `customerprivacyrequest_create` | `form`, `customers` |
| `customerprivacyrequest_edit` | `privacy-requests/<int:pk>/edit/` | GET, POST | `customerprivacyrequest_edit` | `form`, `privacy_request`, `customers` |
| `customerprivacyrequest_delete` | `privacy-requests/<int:pk>/delete/` | POST | `customerprivacyrequest_delete` | `privacy_request` |
| `customerprivacyrequest_generate_export` | `privacy-requests/<int:pk>/generate-export/` | POST | `customerprivacyrequest_generate_export` | Redirect to `customerprivacyrequest_detail` |
| `customerprivacyrequest_anonymize` | `privacy-requests/<int:pk>/anonymize/` | POST | `customerprivacyrequest_anonymize` | Redirect to `customerprivacyrequest_detail` |

---

## 4. Templates Contract (`templates/ecommerce/customerprofile/`)

All templates extend `"base.html"` and use strictly color-named badge classes:
`.badge-green`, `.badge-red`, `.badge-amber`, `.badge-info`, `.badge-slate` (L33).

- `customeraccountprofile/list.html`
- `customeraccountprofile/detail.html`
- `customeraccountprofile/form.html`
- `customeraddresspreference/list.html`
- `customeraddresspreference/detail.html`
- `customeraddresspreference/form.html`
- `customerwishlist/list.html`
- `customerwishlist/detail.html`
- `customerwishlist/form.html`
- `customerprivacyrequest/list.html`
- `customerprivacyrequest/detail.html`
- `customerprivacyrequest/form.html`

---

## 5. Navigation Contract (`LIVE_LINKS["9.6"]`)

```python
LIVE_LINKS["9.6"] = {
    # NavERP.md 9.6 feature bullets
    "Registration & Authentication": "ecommerce:customeraccountprofile_list",
    "Account Dashboard & Order History": "ecommerce:customeraccountprofile_list",
    "Address Book & Preferences": "ecommerce:customeraddresspreference_list",
    "Communication Preferences": "ecommerce:customeraccountprofile_list",
    "Account Security & Privacy": "ecommerce:customerprivacyrequest_list",
    # Extra live leaves
    "Customer Profiles": "ecommerce:customeraccountprofile_list",
    "Address Preferences": "ecommerce:customeraddresspreference_list",
    "Wishlists": "ecommerce:customerwishlist_list",
    "Privacy Requests": "ecommerce:customerprivacyrequest_list",
}
```
