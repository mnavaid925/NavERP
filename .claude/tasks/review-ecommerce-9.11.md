# Review Findings — Sub-module 9.11: Marketplace & Multi-Vendor (`apps/ecommerce`)

- **Sub-module:** 9.11 Marketplace & Multi-Vendor • **Module:** 9 eCommerce Management System • **App:** `apps/ecommerce`
- **Changeset:** `f373366542e10cdb8e6b08f6aa8ce4f758c5ad69...HEAD`
- **Review Date:** 2026-10-31
- **Status:** All Findings Resolved [x] (Phase 5 Complete)

---

## Critical Findings

- [x] **C1**: Cross-vendor payout settlement leakage in `VendorSubOrder` and `VendorSubOrderForm` — fixed in `cefb8bbc`, `2442d3a0`
  - **Files**: `apps/ecommerce/models/Marketplace/VendorSubOrders.py:222-229`, `apps/ecommerce/forms/Marketplace/VendorSubOrderForms.py:14-23`
  - **Description**: `VendorSubOrder.clean()` does not validate `self.payout.vendor_id == self.vendor_id`. Also, `VendorSubOrderForm` exposes `payout` and `payout_status` without restricting to matching vendor or excluding them from manual edit, risking payout hijacking.
  - **Fix**: In `VendorSubOrder.clean()`, validate `if self.payout_id and self.vendor_id and self.payout.vendor_id != self.vendor_id: raise ValidationError(...)`. In `VendorSubOrderForm.Meta.exclude`, exclude `payout` and `payout_status`.

- [x] **C2**: Mismatched product variant association in `VendorProductListing` — fixed in `4444e59b`, `9c1e424a`
  - **Files**: `apps/ecommerce/models/Marketplace/VendorProductListings.py:186-193`, `apps/ecommerce/forms/Marketplace/VendorProductListingForms.py:44-50`
  - **Description**: `VendorProductListing.clean()` and form clean do not validate `self.variant.product_id == self.product_id`, allowing variants from unrelated products to be linked.
  - **Fix**: Validate that `variant.product_id == self.product_id` in `VendorProductListing.clean()` and `VendorProductListingForm.clean()`.

- [x] **C3**: Non-atomic multi-step financial & settlement mutations — fixed in `48f663c1`, `d421e3c7`
  - **Files**: `apps/ecommerce/views/Marketplace/VendorPayoutViews.py:155-176, 200-220`, `apps/ecommerce/views/Marketplace/VendorSubOrderViews.py:243-270`
  - **Description**: `vendorpayout_execute`, `vendorpayout_delete`, and `vendorsuborder_dispute` perform multiple mutations across payouts, sub-orders, and audit logs without `@transaction.atomic`.
  - **Fix**: Decorate `vendorpayout_execute`, `vendorpayout_delete`, and `vendorsuborder_dispute` with `@transaction.atomic`.

- [x] **C4**: Cascading N+1 query storm from chained `__str__` in `VendorSubOrderForm` — fixed in `2442d3a0`
  - **Files**: `apps/ecommerce/forms/Marketplace/VendorSubOrderForms.py:48-55`, `apps/ecommerce/models/Marketplace/VendorPayouts.py:166-168`
  - **Description**: Form `<select>` choices trigger N+1 queries when evaluating `str(order)` and `str(payout)` because querysets in form lack `select_related("customer")` and `select_related("vendor")`.
  - **Fix**: Add `select_related("customer")` on `order` queryset and `select_related("vendor")` on `payout` queryset in `VendorSubOrderForm.__init__`.

- [x] **C5**: Vendor commission type disregarded in financial calculations — fixed in `cefb8bbc`
  - **Files**: `apps/ecommerce/models/Marketplace/VendorSubOrders.py:230-237`
  - **Description**: `calculate_financials()` unconditionally adds fixed fee and percentage fee without checking `vendor.commission_type` ("percentage", "fixed", "combined").
  - **Fix**: In `calculate_financials()`, inspect `vendor.commission_type` and calculate fees conditionally according to the choice.

- [x] **C6**: Payout execution and deletion overwrites withheld and refunded sub-orders — fixed in `48f663c1`
  - **Files**: `apps/ecommerce/views/Marketplace/VendorPayoutViews.py:164, 209`
  - **Description**: `vendorpayout_execute` unconditionally sets all sub-orders to `paid` even if disputed (`withheld_dispute`) or `refunded`. `vendorpayout_delete` resets disputed sub-orders to `accrued`.
  - **Fix**: Exclude `withheld_dispute` and `refunded` sub-orders from batch status updates.

---

## Important Findings

- [x] **I1**: Contract drift and broken attribute lookups in `vendorsuborder/detail.html` — fixed in `d421e3c7`, `a66977db`
  - **Files**: `templates/ecommerce/marketplace/vendorsuborder/detail.html:237, 241`, `apps/ecommerce/views/Marketplace/VendorSubOrderViews.py:90`
  - **Description**: Template uses `sub_order.order.customer_party.name` (field is `customer.name`) and `sub_order.order.grand_total` (field is `total_amount`), resulting in fallback "Shopper" and blank "$". Also omits rendering the passed `order_lines` context.
  - **Fix**: Update template to `customer.name` and `total_amount`, add `order__customer` to `select_related` in view, and render the `order_lines` table.

- [x] **I2**: Broken attribute lookups on `listing.product` in Listing Detail Template — fixed in `c66f3d22`
  - **Files**: `templates/ecommerce/marketplace/vendorproductlisting/detail.html:207, 211`
  - **Description**: Line 207 uses `{{ listing.product.category.name }}` (`CatalogProduct` FK is `primary_category`), rendering "Uncategorized". Line 211 uses `listing.product.is_active` (`CatalogProduct` has `status` with choices draft/active/archived, no `is_active` boolean), rendering "Inactive".
  - **Fix**: Use `listing.product.primary_category.name` and `listing.product.status == "active"`.

- [x] **I3**: Missing `reject_foreign` validation across all marketplace forms — fixed in `d2c64293`, `9c1e424a`, `2442d3a0`, `9790ba08`
  - **Files**: `apps/ecommerce/forms/Marketplace/*.py`
  - **Description**: None of the four marketplace `TenantModelForm` classes implement a `clean()` method calling `reject_foreign(...)`.
  - **Fix**: Implement `clean()` with `reject_foreign` across `MarketplaceVendorForm`, `VendorProductListingForm`, `VendorSubOrderForm`, and `VendorPayoutForm`.

- [x] **I4**: AuditLog action string length exceeds `varchar(10)` limit — fixed in `d421e3c7`, `48f663c1`
  - **Files**: `apps/ecommerce/views/Marketplace/VendorSubOrderViews.py:262`, `apps/ecommerce/views/Marketplace/VendorPayoutViews.py:214`
  - **Description**: Action strings `"dispute_update"` (14 chars) and `"execute_disbursement"` (20 chars) exceed varchar(10) column limit, causing warnings and truncation (`dispute_up`, `execute_di`).
  - **Fix**: Pass `"dispute"` and `"execute"` (or `"disburse"`), storing full action details in changes payload.

- [x] **I5**: AuditLog called after `instance.delete()`, nullifying `object_id` — fixed in `9d5f3646`, `55bc069c`, `d421e3c7`, `48f663c1`
  - **Files**: `apps/ecommerce/views/Marketplace/MarketplaceVendorViews.py:172`, `apps/ecommerce/views/Marketplace/VendorProductListingViews.py:169`, `apps/ecommerce/views/Marketplace/VendorSubOrderViews.py:198`, `apps/ecommerce/views/Marketplace/VendorPayoutViews.py:165`
  - **Description**: `write_audit_log` invoked after `delete()`, when `pk` has been cleared to None.
  - **Fix**: Invoke `write_audit_log` before `instance.delete()` across all four deletion views.

- [x] **I6**: Workflow state mass assignment in `VendorPayoutForm` & `VendorProductListingForm` — fixed in `9790ba08`, `9c1e424a`
  - **Files**: `apps/ecommerce/forms/Marketplace/VendorPayoutForms.py:12-20`, `apps/ecommerce/forms/Marketplace/VendorProductListingForms.py:14-21`
  - **Description**: `payout_status` is not excluded in `VendorPayoutForm.Meta.exclude` (can bypass approval/disbursement). `moderation_status`, `compliance_status`, and `rejection_reason` are exposed in `VendorProductListingForm` (bypassing moderation flow).
  - **Fix**: Exclude these workflow fields from standard CRUD ModelForms.

- [x] **I7**: `TypeError` on `None` comparison in model `clean()` methods — fixed in `bda9062c`, `4444e59b`, `cefb8bbc`, `84d9efb4`
  - **Files**: `apps/ecommerce/models/Marketplace/MarketplaceVendors.py:244-249`, `apps/ecommerce/models/Marketplace/VendorProductListings.py:179`, `apps/ecommerce/models/Marketplace/VendorSubOrders.py:215, 217`
  - **Description**: Direct `< Decimal("0.00")` comparisons without guarding for `None` raise unhandled `TypeError` if fields are unpopulated before validation.
  - **Fix**: Add `if self.<field> is not None and self.<field> < Decimal("0.00"):` guards.

- [x] **I8**: Missing `payout_status` filter dropdown in Sub-Orders List template — fixed in `a714ef1d`
  - **Files**: `templates/ecommerce/marketplace/vendorsuborder/list.html:34-90, 238, 246`
  - **Description**: View parses `payout_status` and passes `payout_status_choices` and `payout_filter`, but filter form lacks `<select name="payout_status">` and pagination links drop the parameter.
  - **Fix**: Add `<select name="payout_status">` with `payout_status_choices` to the filter form and append to pagination query.

- [x] **I9**: Vendor customer rating calculation uses Python loops and is never synchronized on rating edits — fixed in `bda9062c`, `cefb8bbc`
  - **Files**: `apps/ecommerce/models/Marketplace/MarketplaceVendors.py:255-267`, `apps/ecommerce/models/Marketplace/VendorSubOrders.py:257-260`
  - **Description**: `update_rating` fetches all ratings into Python and calculates average with Python `sum`/`len`. SubOrder saves with ratings do not trigger `self.vendor.update_rating()`.
  - **Fix**: Refactor `update_rating()` to use SQL `.aggregate(total=Count("customer_rating"), avg=Avg("customer_rating"))` and invoke `self.vendor.update_rating()` when a sub-order is saved with a rating.

- [x] **I10**: Form labels missing `for` attributes and table buttons missing `aria-label` — fixed in `f2b8ebf1`, `93942eee`, `b9f03ef8`, `35c99795`, `c545d560`, `2318c5aa`, `a714ef1d`, `22ff8afe`, `31262747`, `c66f3d22`, `a66977db`, `efc5aa02`
  - **Files**: `templates/ecommerce/marketplace/**/*.html`
  - **Description**: Form labels lack `for="{{ form.<field>.id_for_label }}"`, and list table icon buttons lack `aria-label`, violating WCAG standards.
  - **Fix**: Add `for` attributes to form labels and `aria-label` to icon buttons.

- [x] **I11**: Hardcoded `bg-white` and `border-slate-200` overrides on `.card` bypassing dark mode — fixed in `f5fbd166`
  - **Files**: All 13 templates across `templates/ecommerce/marketplace/`
  - **Description**: Hardcoded utility classes `bg-white border border-slate-200` override `.card` CSS custom properties, breaking dark mode rendering.
  - **Fix**: Remove redundant `bg-white border border-slate-200` utilities where `.card` is present.

- [x] **I12**: Missing multi-tenant composite indexes for filtered fields — fixed in `4444e59b`, `cefb8bbc`, `84d9efb4`, `37cae024`
  - **Files**: `apps/ecommerce/models/Marketplace/VendorSubOrders.py:194-211`, `apps/ecommerce/models/Marketplace/VendorPayouts.py:130-140`, `apps/ecommerce/models/Marketplace/VendorProductListings.py:166-175`
  - **Description**: Missing composite indexes for hot multi-tenant filter combinations: `("tenant", "fulfillment_status")`, `("tenant", "sla_status")`, `("tenant", "payout_status")`, and `("tenant", "compliance_status")`.
  - **Fix**: Add these composite indexes to `Meta.indexes`.

---

## Minor Findings

- [x] **M1**: N+1 query in Marketplace Console Dashboard KYC Queue — fixed in `4a7a8b75`
  - **Files**: `apps/ecommerce/views/Marketplace/MarketplaceConsoleViews.py:43`, `templates/ecommerce/marketplace/console/dashboard.html:122`
  - **Fix**: Add `.select_related("party")` to `pending_kyc_vendors`.

- [x] **M2**: Double query (`.count` followed by iteration) in Payout Detail — fixed in `efc5aa02`
  - **Files**: `templates/ecommerce/marketplace/vendorpayout/detail.html:163, 178`
  - **Fix**: Use `settled_suborders|length` instead of `settled_suborders.count`.

- [x] **M3**: Hidden foreign key fetch in `VendorSubOrder.save()` and audit logging — fixed in `d421e3c7`
  - **Files**: `apps/ecommerce/models/Marketplace/VendorSubOrders.py:232`, `apps/ecommerce/views/Marketplace/VendorSubOrderViews.py:214, 244`
  - **Fix**: Fetch sub_order with `select_related("vendor", "order")` in action handlers.

- [x] **M4**: Missing `select_related("product__primary_category")` in Listing Detail View — fixed in `55bc069c`
  - **Files**: `apps/ecommerce/views/Marketplace/VendorProductListingViews.py:80-86`
  - **Fix**: Add `product__primary_category` to `select_related`.

- [x] **M5**: Separate consecutive `COUNT(*)` queries in Dashboard Console — fixed in `4a7a8b75`
  - **Files**: `apps/ecommerce/views/Marketplace/MarketplaceConsoleViews.py:21-22`
  - **Fix**: Combine counts using conditional aggregation `aggregate(total=Count("id"), pending_kyc=Count("id", filter=Q(kyc_status="pending")))`.

- [x] **M6**: Unescaped string interpolation in inline JavaScript confirm handlers — fixed in `c545d560`, `2318c5aa`, `a714ef1d`, `22ff8afe`
  - **Files**: `templates/ecommerce/marketplace/marketplacevendor/list.html:174`, `templates/ecommerce/marketplace/vendorproductlisting/list.html:174`
  - **Fix**: Use `{{ v.store_name|escapejs }}` in `confirm(...)`.

- [x] **M7**: Unused disputes query in `marketplacevendor_detail` — fixed in `31262747`
  - **Files**: `apps/ecommerce/views/Marketplace/MarketplaceVendorViews.py:80, 96`
  - **Fix**: Render disputes table in vendor detail or remove unused queryset.

- [x] **M8**: Naive datetime vs local date in SLA calculation — fixed in `cefb8bbc`
  - **Files**: `apps/ecommerce/models/Marketplace/VendorSubOrders.py:242`
  - **Fix**: Use `timezone.localdate(self.dispatched_at)` instead of `self.dispatched_at.date()`.

- [x] **M9**: Duplicate `search_query` context key in MarketplaceVendor list view — fixed in `9d5f3646`
  - **Files**: `apps/ecommerce/views/Marketplace/MarketplaceVendorViews.py:56-57`
  - **Fix**: Remove redundant `"search_query"` key.

- [x] **M10**: Full model column fetches for dropdown filters in list views — fixed in `55bc069c`, `d421e3c7`, `48f663c1`
  - **Files**: `apps/ecommerce/views/Marketplace/VendorProductListingViews.py:57`, `apps/ecommerce/views/Marketplace/VendorSubOrderViews.py:61`, `apps/ecommerce/views/Marketplace/VendorPayoutViews.py:50`
  - **Fix**: Add `.only("id", "store_name")` to vendor dropdown querysets.

- [x] **M11**: Unregistered audit log verb warnings — fixed in `d421e3c7`, `48f663c1`
  - **Files**: `apps/ecommerce/views/Marketplace/*.py`
  - **Fix**: Use `"update"` verb with action recorded in changes dictionary for custom actions.

- [x] **M12**: Non-negative amount validations in `VendorPayout.clean` — fixed in `84d9efb4`
  - **Files**: `apps/ecommerce/models/Marketplace/VendorPayouts.py:141`
  - **Fix**: Add non-negative validations for monetary line fields.
