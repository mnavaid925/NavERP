# Review Findings — Sub-module 9.4: Shopping Cart & Checkout (`ecommerce`)

- **Sub-module:** 9.4 Shopping Cart & Checkout
- **Module:** 9 eCommerce Management System (`ecommerce`)
- **Review Range:** `BASE` (25bdbc0a95fd190736b7b27f883f1c316244fb0a) ... `HEAD` (8be5d265c52e859a43b1e0de8008bcc8976d957f)
- **Review Date:** 2026-10-29
- **Reviewers:** `code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer` (run serially)

---

## Executive Summary

The six review passes evaluated the newly built Sub-module 9.4 (Shopping Cart & Checkout), covering 4 tenant-scoped models (`Cart` + `CartItem`, `CheckoutSession`, `ShippingMethodConfig`, `PaymentMethodConfig`), their forms, views, URLs, 12 templates, seeder extensions, and navigation wiring.

Overall quality is high:
- Strict multi-tenancy is enforced on all model tables (`tenant_id`), querysets (`ecommerce_scope`), and forms (`TenantModelForm`).
- Function-based views with `@login_required` and `@require_POST` on mutation actions are universally used.
- All 12 templates adhere strictly to theme.css color-named badge standards (`badge-green`, `badge-amber`, `badge-red`, `badge-info`, `badge-slate`), with zero invalid semantic `-success` or `-danger` badge classes.
- Pagination controls are properly guarded with `has_previous`/`has_next` (L9).
- IDOR checks returned 404 on cross-tenant entity access across all models.

The six passes identified **6 actionable findings** (0 Critical, 3 Important, 3 Minor), detailed below.

---

## Prioritized Findings Register

| ID | Severity | Category | Target | Description | Status |
|---|---|---|---|---|---|
| **I1** | Important | Performance | `views/CartCheckout/Carts.py` | `cart_list` incurs an N+1 query in the template loop via `cart.item_count` (`items.all()`). Annotate `total_items` in view queryset using `Sum('items__quantity')`. | [ ] open |
| **I2** | Important | UX / Forms | `forms/CartCheckout/CheckoutSessions.py` | `expires_at` `datetime-local` widget renders blank on edit mode because Django DateTimeField default format includes seconds and tzoffset. Add `format='%Y-%m-%dT%H:%M'` to widget. | [ ] open |
| **I3** | Important | Data Integrity | `forms/CartCheckout/ShippingMethods.py` & `PaymentMethods.py` | `destination_countries` and `supported_currencies` accept unnormalized mixed-case string inputs. Add `clean_*` methods to uppercase and strip whitespace. | [ ] open |
| **M1** | Minor | Robustness | `models/CartCheckout/Carts.py` | In `CartItem.save()`, `if self.variant and not self.unit_price:` treats explicit zero price (`0.00`) as falsy and overwrites it. Use `if self.variant and self.unit_price is None:`. | [ ] open |
| **M2** | Minor | Code Quality | `views/CartCheckout/CheckoutSessions.py` | `checkoutsession_detail` loads `TaxCode.objects.filter(tenant=request.tenant)` and shipping/payment configs. Order these querysets explicitly with `.order_by('name')` or `.order_by('sort_order')`. | [ ] open |
| **M3** | Minor | Consistency | `templates/ecommerce/cartcheckout/cart/list.html` | Empty state button icon uses `<i data-lucide="plus"></i>`. Ensure icon initialization runs cleanly without duplicate SVG rendering. | [ ] open |

---

## Detailed Review Pass Reports

### Pass 1: `code-reviewer`
- **Multi-tenant Safety:** Verified. All 4 models inherit `TenantNumbered` which enforces `tenant` FK. All queries use `ecommerce_scope` or `ecommerce_object` filtering by `request.tenant`.
- **Core Spine Reuse:** Reuses `core.Tenant`, `core.Party`, `accounting.TaxCode`, `ecommerce.CatalogProduct`, `ecommerce.ProductVariant`. No duplicate customer or tax masters declared.
- **Backend Packages:** Packaging structure strictly adheres to `apps/ecommerce/{models,forms,views,urls}/CartCheckout/<Entity>.py`. Package `__init__.py` files re-export all symbols with absolute imports.
- **Finding M1:** In `CartItem.save()`, guard against falsy `Decimal("0.00")` overwrite.

### Pass 2: `explorer` (Contract Alignment)
- **Contract vs As-Built:** Checked `contract-ecommerce-9.4.md` against disk files.
  - Model fields and choices match 100%.
  - Number prefixes `ECRT`, `ECKS`, `ESHP`, `EPMC` match 100%.
  - Route names (`cart_list`, `checkoutsession_list`, `shippingmethodconfig_list`, `paymentmethodconfig_list`, etc.) match 100%.
  - View context keys (`carts`, `page_obj`, `status_choices`, `sessions`, `methods`, etc.) verified present.
- **Navigation:** `apps/core/navigation.py` `LIVE_LINKS["9.4"]` maps all 5 exact NavERP.md feature bullets.

### Pass 3: `frontend-reviewer` (UI & Design System)
- **Badges:** All templates verified. Color-named classes (`badge-green`, `badge-amber`, `badge-red`, `badge-info`, `badge-slate`) used exclusively. No `-success`, `-danger`, or `-warning` classes exist.
- **Pagination:** All lists (`cart`, `checkoutsession`, `shippingmethodconfig`, `paymentmethodconfig`) include guards `{% if page_obj.has_previous %}` and `{% if page_obj.has_next %}` preventing L9 `EmptyPage` 500 exceptions.
- **Form Controls:** Tailwind `form-input`, `form-select`, `form-textarea`, `form-checkbox` classes properly attached via widgets.
- **Finding I2:** On `CheckoutSessionForm`, `expires_at` input needs `format='%Y-%m-%dT%H:%M'` to render correctly in browser `datetime-local` fields.

### Pass 4: `performance-reviewer` (Database & Query Efficiency)
- **Indexes:** All models declare compound indexes with names <= 30 characters (`ecom_cart_tnt_stat_idx`, `ecom_cks_tnt_stat_idx`, `ecom_shp_tnt_act_sort_idx`, `ecom_pmc_tnt_act_dsp_idx`).
- **Query Optimization:** Detail views use `select_related` and `prefetch_related` appropriately.
- **Finding I1:** In `cart_list`, `cart.item_count` accesses `cart.items.all()` in template loop. Annotating `total_items=Coalesce(Sum('items__quantity'), 0)` eliminates the N+1 query.

### Pass 5: `qa-smoke-tester` (Functionality & Edge Cases)
- **CRUD Completeness:** All 4 models have full working List, Detail, Create, Edit, Delete (POST-only + confirm) flows.
- **Actions:** `cart_recover`, `checkoutsession_advance`, `shippingmethodconfig_toggle`, `paymentmethodconfig_toggle` all require POST and redirect with messages.
- **Junk Parameter Sweep:** Tested non-numeric, special character, and SQL injection strings across search and filter parameters; all return clean 200 OK without 500 errors.
- **Finding M2:** Querysets passed to `checkoutsession_detail` should have explicit `.order_by()` clauses.

### Pass 6: `security-reviewer` (Auth, IDOR, Compliance)
- **Authentication & Authorization:** All views guarded with `@login_required`. State-modifying endpoints require `@require_POST` and CSRF validation.
- **IDOR Protection:** Cross-tenant accesses test-probed with Tenant B records against Tenant A admin; all return 404 Not Found.
- **PCI-DSS Compliance:** Confirmed zero storage of raw credit card PAN, CVV, or expiration data on `PaymentMethodConfig` or `CheckoutSession`. Only tokens and transaction IDs are stored.
- **Finding I3:** Normalize comma-separated country and currency inputs to prevent case mismatch bypasses in checkout validation.
