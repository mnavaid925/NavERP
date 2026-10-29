# Review Findings — Sub-module 9.6: Customer Account & Profile (Module 9 eCommerce, `ecommerce`)

- **Sub-module:** 9.6 Customer Account & Profile
- **App:** `apps/ecommerce`
- **Reviewed Commit Range:** `60854f643a9e30252b99563f1012a5bb46cf59c1...HEAD`
- **Phase:** 4 Review (strictly serial)

---

## Pass 1: Code Reviewer (`code-reviewer`)

### Critical
- [ ] **[C1] Broken `write_audit_log` Call Signatures Across All 4 View Files**
  - **Files:**
    - `apps/ecommerce/views/CustomerProfile/CustomerAccountProfiles.py:124, 158, 193`
    - `apps/ecommerce/views/CustomerProfile/CustomerAddressPreferences.py:88, 124, 161`
    - `apps/ecommerce/views/CustomerProfile/CustomerWishlists.py:93, 127, 163`
    - `apps/ecommerce/views/CustomerProfile/CustomerPrivacyRequests.py:98, 132, 167, 233, 276`
  - **Description:** Views call `write_audit_log(tenant=..., user=..., action=..., model_name=..., object_id=..., object_repr=...)`. Canonical signature is `write_audit_log(user, obj, action, changes=None, tenant=None)`. Calling with unsupported kwargs raises immediate `TypeError` on all create/edit/delete/export/anonymize write operations.
  - **Suggested Fix:** Change all calls to `write_audit_log(request.user, obj, "create", changes={"number": obj.number}, tenant=request.tenant)` (or `"update"`, `"delete"`).

- [ ] **[C2] Crash in GDPR Data Export on Missing `Address.postal_code` Attribute**
  - **File:** `apps/ecommerce/views/CustomerProfile/CustomerPrivacyRequests.py:207`
  - **Description:** `customerprivacyrequest_generate_export` accesses `pref.address.postal_code`. `core.Address` only defines `line1`, `city`, `country`. Raises `AttributeError: 'Address' object has no attribute 'postal_code'` (500 crash).
  - **Suggested Fix:** Use `getattr(pref.address, "postal_code", "") if pref.address else ""`.

- [ ] **[C3] Missing `UniqueConstraint(fields=["tenant", "number"])` on All 4 Models**
  - **Files:**
    - `apps/ecommerce/models/CustomerProfile/CustomerAccountProfiles.py:84`
    - `apps/ecommerce/models/CustomerProfile/CustomerAddressPreferences.py:42`
    - `apps/ecommerce/models/CustomerProfile/CustomerWishlists.py:34`
    - `apps/ecommerce/models/CustomerProfile/CustomerPrivacyRequests.py:49`
  - **Description:** All 4 models inherit from `TenantNumbered` which relies on `IntegrityError` to retry number allocation under concurrency. Without `UniqueConstraint(fields=["tenant", "number"])`, duplicate document numbers can be silently minted.
  - **Suggested Fix:** Add `models.UniqueConstraint(fields=["tenant", "number"], name="ecommerce_<model>_tenant_num_uniq")` to `class Meta.constraints` on all 4 models and generate migration `0007`.

### Important
- [ ] **[I1] Unhandled `ValueError` / 500 in `customerwishlist_item_add` on Malformed POST Input**
  - **File:** `apps/ecommerce/views/CustomerProfile/CustomerWishlists.py:179, 181`
  - **Description:** `desired_qty = int(request.POST.get("desired_quantity", 1))` raises `ValueError` if non-numeric or empty string.
  - **Suggested Fix:** Wrap in `try/except (ValueError, TypeError)` and default to 1.

- [ ] **[I2] Missing `transaction.atomic()` on Multi-Model GDPR Anonymization**
  - **File:** `apps/ecommerce/views/CustomerProfile/CustomerPrivacyRequests.py:248-286`
  - **Description:** `customerprivacyrequest_anonymize` updates profile, addresses, privacy request, and logs across separate statements without a transaction wrapper.
  - **Suggested Fix:** Wrap in `with transaction.atomic():`.

- [ ] **[I3] Inconsistent Authorization on Wishlist Item Actions**
  - **File:** `apps/ecommerce/views/CustomerProfile/CustomerWishlists.py:175, 213`
  - **Description:** `customerwishlist_item_add` and `customerwishlist_item_delete` lack `@tenant_admin_required`, while create/edit/delete require it.
  - **Suggested Fix:** Add `@tenant_admin_required` to `customerwishlist_item_add` and `customerwishlist_item_delete`.

- [ ] **[I4] Contract Drift in Wishlist Detail Template (`p.sku` and `p.base_price` on `CatalogProduct`)**
  - **File:** `templates/ecommerce/customerprofile/customerwishlist/detail.html:82, 136`
  - **Description:** Template attempts to render `{{ item.product.sku }}` and `{{ p.sku }}` / `{{ p.base_price }}`. `CatalogProduct` defines `number` and `price_range_display`, not `sku` / `base_price`.
  - **Suggested Fix:** Update to `{{ item.product.number }}` and `{{ p.name }} ({{ p.number }}) - {{ p.price_range_display }}`.

### Minor
- [ ] **[M1] Undefined `badge-purple` Theme Class**
  - **Files:**
    - `templates/ecommerce/customerprofile/customeraccountprofile/list.html:118`
    - `templates/ecommerce/customerprofile/customeraccountprofile/detail.html:20`
  - **Description:** `badge-purple` is not in `static/css/theme.css` (only `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate` exist, L33).
  - **Suggested Fix:** Replace `badge-purple` with `badge-info` or `badge-slate`.

- [ ] **[M2] AuditLog Verb Exceeding Maximum Length**
  - **File:** `apps/ecommerce/views/CustomerProfile/CustomerPrivacyRequests.py:236, 280`
  - **Description:** `action="dsar_export"` (11 chars) and `action="gdpr_erasure"` (12 chars) exceed `AuditLog.action` (`max_length=10`).
  - **Suggested Fix:** Use verbs `"export"` and `"anonymize"`.

- [ ] **[M3] Missing Variant-to-Product Consistency Check in `CustomerWishlistItemForm`**
  - **File:** `apps/ecommerce/forms/CustomerProfile/CustomerWishlists.py:42-74`
  - **Description:** `clean()` does not verify `variant.product == product`.
  - **Suggested Fix:** Add validation error if `variant and variant.product != product`.

---

## Pass 2: Explorer (`explorer`)

### Critical
- [ ] *(Corroborated [C2]) Spine Integration: Missing `core.Address.postal_code` in GDPR Export* (`CustomerPrivacyRequests.py:207`)
- [ ] *(Corroborated [C3]) Core Tenancy: Missing `UniqueConstraint(fields=["tenant", "number"])` across all 4 models*

### Important
- [ ] **[I5] Cross-Party Address Assignment in `CustomerAddressPreferenceForm`**
  - **File:** `apps/ecommerce/forms/CustomerProfile/CustomerAddressPreferences.py:42-49`
  - **Description:** `clean()` confirms tenant isolation but does not verify `address.party == customer`. An operator could assign another party's address to a customer.
  - **Suggested Fix:** Add check `if customer and address and address.party_id != customer.pk: self.add_error("address", "The selected address does not belong to this customer.")`.

- [ ] **[I6] Seeder Defect: Unfiltered Party Lookup in `seed_ecommerce.py` Leads to Cross-Party Linking**
  - **File:** `apps/ecommerce/management/commands/seed_ecommerce.py:1404-1414`
  - **Description:** `Address.objects.filter(tenant=tenant).first()` returns any address in the tenant, which might belong to a non-customer party.
  - **Suggested Fix:** Change to `Address.objects.filter(tenant=tenant, party=cust_party).first()`.

- [ ] **[I7] Template Address Attribute Drift on `core.Address`**
  - **Files:**
    - `templates/ecommerce/customerprofile/customeraddresspreference/list.html:106`
    - `templates/ecommerce/customerprofile/customeraddresspreference/detail.html:69, 75`
    - `templates/ecommerce/customerprofile/customeraccountprofile/detail.html:239`
  - **Description:** Templates expect `line2`, `state`, `postal_code` which do not exist on `core.Address`.
  - **Suggested Fix:** Render `{{ pref.address.line1 }}{% if pref.address.city %}, {{ pref.address.city }}{% endif %}{% if pref.address.country %}, {{ pref.address.country }}{% endif %}`.

### Minor
- [ ] *(Corroborated [M1]) Undefined `badge-purple` theme class in customeraccountprofile templates*

