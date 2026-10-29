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

---

## Pass 3: Frontend Reviewer (`frontend-reviewer`)

### Critical
*(None)*

### Important
- [ ] *(Corroborated [M1 / FE-I1]) Invalid theme badge class `.badge-purple` in customeraccountprofile list and detail templates (Lesson L33)*
- [ ] *(Corroborated [I7 / FE-I2]) Non-existent fields accessed on `core.Address` (`line2`, `state`, `postal_code`) across address and profile templates*

### Minor
- [ ] **[M4] Ad-hoc Stat Card Styling in `customeraccountprofile/detail.html`**
  - **File:** `templates/ecommerce/customerprofile/customeraccountprofile/detail.html:66, 77, 96, 113`
  - **Description:** Inline flex wrappers with raw Tailwind colors used instead of theme.css `.stat-card` / `.stat-icon` components.
  - **Suggested Fix:** Align stat cards with `theme.css` `.stat-card` / `.stat-icon` classes.

- [ ] **[M5] Missing `aria-label` on Icon-Only Action Buttons**
  - **Files:** All 4 list templates (`customeraccountprofile/list.html`, `customeraddresspreference/list.html`, `customerwishlist/list.html`, `customerprivacyrequest/list.html`)
  - **Description:** Action buttons (view, edit, delete, reset filter) provide `title="..."` but omit `aria-label="..."`.
  - **Suggested Fix:** Add `aria-label` matching `title` on icon-only buttons for accessibility.

---

## Pass 4: Performance Reviewer (`performance-reviewer`)

### Critical
- [ ] **[PERF-C1] N+1 Queries in `customerwishlist_list` Due to `w.items.count` in Template Loop**
  - **Files:** `templates/ecommerce/customerprofile/customerwishlist/list.html:111`, `apps/ecommerce/views/CustomerProfile/CustomerWishlists.py:18-22`
  - **Description:** `w.items.count` triggers a direct `COUNT(*)` query for each row in the 25-item page, bypassing prefetch.
  - **Suggested Fix:** Annotate `items_count=Count("items")` in the view queryset and use `w.items_count` in template.

### Important
- [ ] **[PERF-I1] N+1 Query in `customeraccountprofile_detail` Due to `w.items.count`**
  - **Files:** `templates/ecommerce/customerprofile/customeraccountprofile/detail.html:304`, `apps/ecommerce/views/CustomerProfile/CustomerAccountProfiles.py:91-94`
  - **Description:** `{{ w.items.count }}` issues a direct count query per wishlist.
  - **Suggested Fix:** Annotate `items_count=Count("items")` on wishlists query in `customeraccountprofile_detail`.

- [ ] **[PERF-I2] Missing `select_related` in `customerprivacyrequest_generate_export`**
  - **File:** `apps/ecommerce/views/CustomerProfile/CustomerPrivacyRequests.py:188-216`
  - **Description:** Missing `select_related("address")` on address preferences, `select_related("preferred_currency")` on profile, and `w.items.count` in loop.
  - **Suggested Fix:** Add `select_related` on address preferences and currency, and annotate items_count on wishlists in export.

- [ ] **[PERF-I3] Redundant Queries in `customerwishlist_detail` View**
  - **File:** `apps/ecommerce/views/CustomerProfile/CustomerWishlists.py:61-68`
  - **Description:** Prefetched `items__product` and `items__variant` are discarded when `wishlist.items.all().select_related("product", "variant")` creates a new queryset.
  - **Suggested Fix:** Change to `items = wishlist.items.all()`.

- [ ] **[PERF-I4] Missing Database Indexes on Filtered Columns**
  - **Files:** `apps/ecommerce/models/CustomerProfile/CustomerAccountProfiles.py`, `CustomerAddressPreferences.py`, `CustomerWishlists.py`
  - **Description:** Missing composite indexes on `(tenant, auth_mode)`, `(tenant, preferred_delivery_window)`, `(tenant, visibility)`, and `(tenant, customer, is_default)`.
  - **Suggested Fix:** Add `models.Index` on these composite fields and create migration.

### Minor
- [ ] **[PERF-M1] Missing `list_select_related` on Admin Changelists**
  - **File:** `apps/ecommerce/admin.py:210-255`
  - **Description:** Admin classes do not set `list_select_related` for related FKs.
  - **Suggested Fix:** Add `list_select_related` on the 5 admin classes.



