# Review Findings — Sub-module 9.6: Customer Account & Profile (Module 9 eCommerce, `ecommerce`)

- **Sub-module:** 9.6 Customer Account & Profile
- **App:** `apps/ecommerce`
- **Reviewed Commit Range:** `60854f643a9e30252b99563f1012a5bb46cf59c1...HEAD`
- **Review Passes Completed:** 6/6 (`code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`)
- **Status:** Deduplicated & Prioritized for Phase 5 `code-fixer`

---

## Critical Findings

- [x] **[C1] Broken `write_audit_log` Call Signatures Across All 4 View Files** — fixed: `fix(ecommerce): correct write_audit_log signatures across CustomerProfile views`
  - **Files:**
    - `apps/ecommerce/views/CustomerProfile/CustomerAccountProfiles.py:124, 158, 193`
    - `apps/ecommerce/views/CustomerProfile/CustomerAddressPreferences.py:88, 124, 161`
    - `apps/ecommerce/views/CustomerProfile/CustomerWishlists.py:93, 127, 163`
    - `apps/ecommerce/views/CustomerProfile/CustomerPrivacyRequests.py:98, 132, 167, 233, 276`
  - **Description:** Views call `write_audit_log(tenant=..., user=..., action=..., model_name=..., object_id=..., object_repr=...)`. Canonical signature in `apps/core/utils.py:10` is `write_audit_log(user, obj, action, changes=None, tenant=None)`. Calling with unsupported kwargs raises immediate `TypeError` on all 13 create, edit, delete, export, and anonymize write operations, evading audit logging and crashing with HTTP 500.
  - **Fix:** Update all 14 call sites to match canonical signature: `write_audit_log(request.user, obj, "create", changes={"number": obj.number}, tenant=request.tenant)` (or `"update"`, `"delete"`, `"export"`, `"anonymize"`).

- [x] **[C2] Crash in GDPR Data Export on Missing `Address.postal_code` Attribute** — fixed: `fix(ecommerce): safely access Address attributes in GDPR data export`
  - **File:** `apps/ecommerce/views/CustomerProfile/CustomerPrivacyRequests.py:207`
  - **Description:** In `customerprivacyrequest_generate_export`, the export serializer accesses `pref.address.postal_code`. `core.Address` only defines `party`, `kind`, `line1`, `city`, and `country`. Attempting to generate a data portability export raises `AttributeError: 'Address' object has no attribute 'postal_code'` and produces an unhandled HTTP 500.
  - **Fix:** Safely access postal code: `getattr(pref.address, "postal_code", "") if pref.address else ""`.

- [x] **[C3] Missing Database-Level Unique Constraints (`tenant`, `number`) Across All 4 Models** — fixed: `feat(ecommerce): add unique constraints across all 4 customer profile models and migration 0007`
  - **Files:**
    - `apps/ecommerce/models/CustomerProfile/CustomerAccountProfiles.py:84`
    - `apps/ecommerce/models/CustomerProfile/CustomerAddressPreferences.py:42`
    - `apps/ecommerce/models/CustomerProfile/CustomerWishlists.py:34`
    - `apps/ecommerce/models/CustomerProfile/CustomerPrivacyRequests.py:49`
  - **Description:** All 4 models inherit from `TenantNumbered` which relies on `IntegrityError` to retry number allocation up to 5 times when sequence races occur. Without a database unique constraint on `("tenant", "number")`, concurrent writers will not raise `IntegrityError` and will silently write duplicate document numbers (`ECAP-`, `ECAD-`, `EWSL-`, `ECPR-`). In addition, `CustomerAccountProfile` lacks `UniqueConstraint(fields=["tenant", "customer"])`.
  - **Fix:** Add `models.UniqueConstraint(fields=["tenant", "number"], name="ecommerce_<model>_tenant_num_uniq")` to `class Meta.constraints` on all 4 models, and `models.UniqueConstraint(fields=["tenant", "customer"], name="ecommerce_ecap_tenant_cust_uniq")` on `CustomerAccountProfile`. Generate incremental migration.

- [x] **[C4] Unchecked Request Type & Missing `transaction.atomic()` in GDPR Anonymization** — fixed: `fix(ecommerce): validate request type and wrap GDPR anonymization in transaction.atomic`
  - **File:** `apps/ecommerce/views/CustomerProfile/CustomerPrivacyRequests.py:248-286`
  - **Description:** `customerprivacyrequest_anonymize` does not verify `privacy_request.request_type == "erasure_anonymize"`, allowing data erasure to be triggered on export/rectification requests. Furthermore, multiple table updates occur without `transaction.atomic()`; an exception midway leaves customer PII in a corrupted, partially scrubbed state.
  - **Fix:** Validate `if privacy_request.request_type != "erasure_anonymize":` and wrap the entire anonymization routine inside `with transaction.atomic():`.

- [x] **[C5] Incomplete GDPR Right to Erasure Leaving Active Authentication Accounts Intact** — fixed: `fix(ecommerce): deactivate auth user and anonymize wishlists on GDPR erasure`
  - **File:** `apps/ecommerce/views/CustomerProfile/CustomerPrivacyRequests.py:253-270`
  - **Description:** `profile.user = None` unlinks the customer profile from the Django auth user, but does not deactivate the `accounts.User` record (`user.is_active` remains True, user email persists). The customer can still authenticate, violating GDPR Article 17. Additionally, linked `CustomerWishlist` records remain intact and publicly accessible via share tokens.
  - **Fix:** Deactivate linked `user` (`user.is_active = False`), anonymize email (`user.email = f"erased_{user.pk}@anonymized.local"`), and anonymize customer wishlists (`visibility="private"`, `name="Anonymized Wishlist"`).

---

## Important Findings

- [x] **[I1] Unhandled Numeric Input & Empty Product Crash in `customerwishlist_item_add`** — fixed: `fix(ecommerce): validate product id and sanitize desired quantity in customerwishlist_item_add`
  - **File:** `apps/ecommerce/views/CustomerProfile/CustomerWishlists.py:179-185`
  - **Description:** `desired_qty = int(request.POST.get("desired_quantity", 1))` hand-parses user input without `try/except (ValueError, TypeError)`. Non-numeric or negative inputs crash with 500 or decrement quantities below zero. Furthermore, empty `product` POST data raises `ValueError: Field 'id' expected a number but got ''`.
  - **Fix:** Guard `product_id` (check non-empty and digits), and wrap `desired_qty` with `max(1, min(int(request.POST.get("desired_quantity", 1) or 1), 9999))`.

- [x] **[I2] Inconsistent Authorization Gates on Wishlist Item Actions** — fixed: `security(ecommerce): add tenant_admin_required to wishlist item add and delete views`
  - **File:** `apps/ecommerce/views/CustomerProfile/CustomerWishlists.py:175, 213`
  - **Description:** `customerwishlist_item_add` and `customerwishlist_item_delete` lack `@tenant_admin_required`, while create/edit/delete require it. Any unprivileged authenticated user can add or delete items from any customer's wishlist in the tenant.
  - **Fix:** Add `@tenant_admin_required` to both view endpoints.

- [x] **[I3] N+1 Queries in `customerwishlist_list` and `customeraccountprofile_detail` Due to `w.items.count`** — fixed: `perf(ecommerce): annotate items_count to eliminate N+1 queries in wishlist list and profile detail`
  - **Files:**
    - `templates/ecommerce/customerprofile/customerwishlist/list.html:111`
    - `apps/ecommerce/views/CustomerProfile/CustomerWishlists.py:18-22`
    - `templates/ecommerce/customerprofile/customeraccountprofile/detail.html:304`
    - `apps/ecommerce/views/CustomerProfile/CustomerAccountProfiles.py:91-94`
  - **Description:** Calling `{{ w.items.count }}` in template loops triggers a direct SQL `SELECT COUNT(*)` for every row, bypassing Django's prefetch cache (27 queries on a 25-row page).
  - **Fix:** Annotate `items_count=Count("items")` in `customerwishlist_list` and `customeraccountprofile_detail` querysets, and update templates to use `w.items_count`.

- [x] **[I4] Missing `select_related` in `customerprivacyrequest_generate_export`** — fixed: `perf(ecommerce): add select_related and items_count annotation in generate_export`
  - **File:** `apps/ecommerce/views/CustomerProfile/CustomerPrivacyRequests.py:188-216`
  - **Description:** Missing `select_related("address")` on address preferences, `select_related("preferred_currency")` on profile, and calling `w.items.count` in loop causes N+1 queries during export generation.
  - **Fix:** Add `select_related("preferred_currency")` on profile, `select_related("address")` on preferences, and annotate `items_count=Count("items")` on wishlists.

- [x] **[I5] Redundant Queries in `customerwishlist_detail` View** — fixed: `perf(ecommerce): reuse prefetched items cache in customerwishlist_detail`
  - **File:** `apps/ecommerce/views/CustomerProfile/CustomerWishlists.py:61-68`
  - **Description:** Prefetched `items__product` and `items__variant` are discarded when line 68 executes `items = wishlist.items.all().select_related("product", "variant")`.
  - **Fix:** Change to `items = wishlist.items.all()` to reuse prefetched memory cache.

- [x] **[I6] Missing Database Indexes on Filtered Columns** — fixed: `feat(ecommerce): add composite indexes on CustomerProfile models in migration 0007`
  - **Files:** `apps/ecommerce/models/CustomerProfile/CustomerAccountProfiles.py`, `CustomerAddressPreferences.py`, `CustomerWishlists.py`
  - **Description:** Missing composite database indexes on `(tenant, auth_mode)`, `(tenant, preferred_delivery_window)`, `(tenant, visibility)`, and `(tenant, customer, is_default)`.
  - **Fix:** Add `models.Index` on these composite fields in model Meta and generate migration.

- [x] **[I7] Cross-Customer Physical Address Binding in `CustomerAddressPreferenceForm`** — fixed: `fix(ecommerce): validate physical address ownership against customer in CustomerAddressPreferenceForm`
  - **File:** `apps/ecommerce/forms/CustomerProfile/CustomerAddressPreferences.py:42-49`
  - **Description:** `clean()` confirms tenant isolation but does not verify that `address.party_id == customer.pk`. A staff member can accidentally bind Customer A's preference to Customer B's physical address.
  - **Fix:** In `CustomerAddressPreferenceForm.clean()`, add `if customer and address and getattr(address, "party_id", None) != customer.pk: self.add_error("address", "The selected physical address does not belong to this customer.")`.

- [x] **[I8] Contract Drift in Wishlist Detail Template (`p.sku` and `p.base_price` on `CatalogProduct`)** — fixed: `fix(ecommerce): update product attributes to number and price_range_display in wishlist detail`
  - **File:** `templates/ecommerce/customerprofile/customerwishlist/detail.html:82, 136`
  - **Description:** Line 82 references `{{ item.product.sku }}` and line 136 references `<option value="...">{{ p.name }} ({{ p.sku }}) - ${{ p.base_price }}</option>`. `CatalogProduct` defines `number` and `price_range_display`, but not `sku` or `base_price`. Renders blank labels `() - $`.
  - **Fix:** Update to `{{ item.product.number }}` and `{{ p.name }} ({{ p.number }}) - {{ p.price_range_display }}`.

- [x] **[I9] Non-Existent Fields Accessed on `core.Address` in Templates** — fixed: `fix(ecommerce): align address display with core.Address fields in templates`
  - **Files:**
    - `templates/ecommerce/customerprofile/customeraddresspreference/list.html:106`
    - `templates/ecommerce/customerprofile/customeraddresspreference/detail.html:69, 75`
    - `templates/ecommerce/customerprofile/customeraccountprofile/detail.html:239`
  - **Description:** Templates expect attributes (`line2`, `state`, `postal_code`) that do not exist on `core.Address`.
  - **Fix:** Update address display to standard core fields: `{{ pref.address.line1 }}{% if pref.address.city %}, {{ pref.address.city }}{% endif %}{% if pref.address.country %}, {{ pref.address.country }}{% endif %}`.

- [x] **[I10] Seeder Defect: Unfiltered Party Lookup in `seed_ecommerce.py`** — fixed: `fix(ecommerce): filter seed Address by customer party`
  - **File:** `apps/ecommerce/management/commands/seed_ecommerce.py:1404-1414`
  - **Description:** `Address.objects.filter(tenant=tenant).first()` returns any address in the tenant, which might belong to an organization or vendor party rather than `cust_party`.
  - **Fix:** Filter by customer party: `Address.objects.filter(tenant=tenant, party=cust_party).first()`.

- [x] **[I11] Workflow State Mass Assignment in `CustomerPrivacyRequestForm`** — fixed: `security(ecommerce): remove status from CustomerPrivacyRequestForm fields`
  - **File:** `apps/ecommerce/forms/CustomerProfile/CustomerPrivacyRequests.py:14`
  - **Description:** `CustomerPrivacyRequestForm` exposes `"status"` in `Meta.fields`. Setting `status="completed"` directly via edit form bypasses export generation and data anonymization routines.
  - **Fix:** Remove `"status"` from `CustomerPrivacyRequestForm.Meta.fields` and transition status exclusively via verified fulfillment actions (`generate_export` and `anonymize`).

---

## Minor Findings

- [x] **[M1] Undefined Theme Badge Class `.badge-purple`** — fixed: `fix(ecommerce): replace non-standard badge-purple with badge-info in profile templates`
  - **Files:**
    - `templates/ecommerce/customerprofile/customeraccountprofile/list.html:118`
    - `templates/ecommerce/customerprofile/customeraccountprofile/detail.html:20`
  - **Description:** `badge-purple` is used for the VIP tier badge, but `static/css/theme.css` only defines `.badge-green`, `.badge-red`, `.badge-amber`, `.badge-info`, `.badge-muted`, `.badge-slate` (Lesson L33).
  - **Fix:** Replace `badge-purple` with `.badge-info` or `.badge-slate`.

- [x] **[M2] AuditLog Verb Exceeding Maximum Length** — fixed: `fix(ecommerce): clamp audit log action verbs to export and anonymize`
  - **File:** `apps/ecommerce/views/CustomerProfile/CustomerPrivacyRequests.py:236, 280`
  - **Description:** `action="dsar_export"` (11 chars) and `action="gdpr_erasure"` (12 chars) exceed `AuditLog.action` (`max_length=10`).
  - **Fix:** Use verbs `"export"` and `"anonymize"`, placing specific operations in `changes`.

- [x] **[M3] Missing Variant-to-Product Consistency Check in `CustomerWishlistItemForm`** — fixed: `fix(ecommerce): validate variant belongs to product in CustomerWishlistItemForm`
  - **File:** `apps/ecommerce/forms/CustomerProfile/CustomerWishlists.py:69-74`
  - **Description:** `clean()` does not verify `variant.product == product`.
  - **Fix:** In `CustomerWishlistItemForm.clean()`, add `if product and variant and variant.product_id != product.pk: self.add_error("variant", "Selected variant does not belong to the chosen product.")`.

- [x] **[M4] Ad-hoc Stat Card Styling in `customeraccountprofile/detail.html`** — fixed: `style(ecommerce): align stat cards with theme.css stat-card and stat-icon components`
  - **File:** `templates/ecommerce/customerprofile/customeraccountprofile/detail.html:66, 77, 96, 113`
  - **Description:** Inline flex wrappers with raw Tailwind colors used instead of theme.css `.stat-card` / `.stat-icon` components.
  - **Fix:** Align stat cards with `theme.css` `.stat-card` / `.stat-icon` classes.

- [x] **[M5] Missing `aria-label` on Icon-Only Action Buttons** — fixed: `accessibility(ecommerce): add aria-label to icon-only action buttons across all 4 list templates`
  - **Files:** All 4 list templates (`customeraccountprofile/list.html`, `customeraddresspreference/list.html`, `customerwishlist/list.html`, `customerprivacyrequest/list.html`)
  - **Description:** Action buttons (view, edit, delete, reset filter) provide `title="..."` but omit `aria-label="..."`.
  - **Fix:** Add `aria-label` matching `title` on icon-only buttons for accessibility.

- [x] **[M6] Missing `list_select_related` on Admin Changelists** — fixed: `perf(ecommerce): add list_select_related to CustomerProfile admin classes`
  - **File:** `apps/ecommerce/admin.py:210-255`
  - **Description:** Admin classes do not set `list_select_related` for related FKs.
  - **Fix:** Add `list_select_related` on the 5 admin classes.
