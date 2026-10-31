# Review Findings — Sub-module 9.11: Marketplace & Multi-Vendor (`apps/ecommerce`)

- **Sub-module:** 9.11 Marketplace & Multi-Vendor • **Module:** 9 eCommerce Management System • **App:** `apps/ecommerce`
- **Changeset:** `f373366542e10cdb8e6b08f6aa8ce4f758c5ad69...HEAD`
- **Review Date:** 2026-10-31
- **Status:** Review In Progress (Pass 1 & Pass 2 complete)

---

## Pass 1: Code Review (`code-reviewer`)

### Critical
- [ ] **C1**: Cross-vendor payout settlement leakage in `VendorSubOrder` and `VendorSubOrderForm`
  - `apps/ecommerce/models/Marketplace/VendorSubOrders.py:222-229`
  - `apps/ecommerce/forms/Marketplace/VendorSubOrderForms.py:53`
  - Description: `VendorSubOrder.clean()` does not validate `self.payout.vendor_id == self.vendor_id`. Also `VendorSubOrderForm` does not filter `payout` queryset to the selected vendor.
  - Fix: Validate vendor alignment in `clean()` and filter payout queryset to matching vendor in form.
- [ ] **C2**: Mismatched product variant association in `VendorProductListing`
  - `apps/ecommerce/models/Marketplace/VendorProductListings.py:186-193`
  - Description: `VendorProductListing.clean()` does not validate `self.variant.product_id == self.product_id`, allowing variants from unrelated products to be linked.
  - Fix: Add check `if self.variant_id and self.product_id and self.variant.product_id != self.product_id:` in `clean()`.
- [ ] **C3**: Vendor commission type disregarded in financial calculations
  - `apps/ecommerce/models/Marketplace/VendorSubOrders.py:230-237`
  - Description: `calculate_financials()` unconditionally adds fixed fee and percentage fee without checking `vendor.commission_type` ("percentage", "fixed", "combined").
  - Fix: Check `commission_type` and apply rate / fixed fee conditionally based on choice.
- [ ] **C4**: Payout execution and deletion overwrites withheld and refunded sub-orders
  - `apps/ecommerce/views/Marketplace/VendorPayoutViews.py:164, 209`
  - Description: `vendorpayout_execute` unconditionally sets all sub-orders to `paid` even if disputed (`withheld_dispute`) or `refunded`. `vendorpayout_delete` resets disputed sub-orders to `accrued`.
  - Fix: Exclude `withheld_dispute` and `refunded` sub-orders from batch updates.

### Important
- [ ] **I1**: Contract drift and broken fields in `vendorsuborder/detail.html`
  - `templates/ecommerce/marketplace/vendorsuborder/detail.html:237, 241`
  - Description: Template uses `sub_order.order.customer_party.name` (field is `customer.name`) and `sub_order.order.grand_total` (field is `total_amount`), and omits `order_lines` table.
  - Fix: Fix variable names to `customer.name` and `total_amount`, and add consignment order lines table.
- [ ] **I2**: AuditLog action string length clamped by `varchar(10)` limit
  - `apps/ecommerce/views/Marketplace/VendorSubOrderViews.py:262`
  - `apps/ecommerce/views/Marketplace/VendorPayoutViews.py:214`
  - Description: Action strings `"dispute_update"` and `"execute_disbursement"` exceed 10 characters.
  - Fix: Pass `"dispute"` and `"execute"`, recording details in changes payload.
- [ ] **I3**: AuditLog called after `instance.delete()`, saving `object_id = None`
  - `apps/ecommerce/views/Marketplace/MarketplaceVendorViews.py:172`
  - `apps/ecommerce/views/Marketplace/VendorProductListingViews.py:169`
  - `apps/ecommerce/views/Marketplace/VendorSubOrderViews.py:198`
  - `apps/ecommerce/views/Marketplace/VendorPayoutViews.py:165`
  - Description: `write_audit_log` invoked after `delete()`, when `pk` has been cleared.
  - Fix: Invoke `write_audit_log` before `instance.delete()`.
- [ ] **I4**: Missing `reject_foreign` validation in marketplace forms
  - `apps/ecommerce/forms/Marketplace/*.py`
  - Description: Marketplace model forms lack `reject_foreign` defense-in-depth checks on foreign keys.
  - Fix: Implement `clean()` with `reject_foreign` in all four forms.
- [ ] **I5**: Vendor customer rating aggregate never synchronized on rating edits
  - `apps/ecommerce/models/Marketplace/MarketplaceVendors.py:255`
  - Description: `MarketplaceVendor.update_rating()` is never triggered when sub-order ratings are created or edited.
  - Fix: Trigger `self.vendor.update_rating()` upon rating changes.

### Minor
- [ ] **M1**: `payout_status` filter dropped in sub-order pagination links
  - `templates/ecommerce/marketplace/vendorsuborder/list.html:238, 246`
  - Fix: Append `&payout_status={{ payout_filter }}`.
- [ ] **M2**: N+1 query risks in console and detail views
  - `apps/ecommerce/views/Marketplace/MarketplaceConsoleViews.py:43`
  - `apps/ecommerce/views/Marketplace/VendorProductListingViews.py:84`
  - `apps/ecommerce/views/Marketplace/VendorSubOrderViews.py:90`
  - Fix: Add missing `select_related` keys (`party`, `product__primary_category`, `order__customer`).
- [ ] **M3**: Unused disputes query in `marketplacevendor_detail`
  - `apps/ecommerce/views/Marketplace/MarketplaceVendorViews.py:80`
  - Fix: Render disputes table in vendor detail or remove query.
- [ ] **M4**: Naive datetime vs local date in SLA calculation
  - `apps/ecommerce/models/Marketplace/VendorSubOrders.py:242`
  - Fix: Use `timezone.localdate(self.dispatched_at)` instead of `self.dispatched_at.date()`.
- [ ] **M5**: Missing non-negative amount validations in `VendorPayout.clean`
  - `apps/ecommerce/models/Marketplace/VendorPayouts.py:141`
  - Fix: Add non-negative validations for monetary line fields.

---

## Pass 2: Explorer Review (`explorer`)

### Important
- [ ] **EXP-I1**: Broken Attribute Lookups on `listing.product` in Listing Detail Template
  - `templates/ecommerce/marketplace/vendorproductlisting/detail.html:207, 211`
  - Description: Line 207 uses `{{ listing.product.category.name }}` (`CatalogProduct` FK is `primary_category`), rendering `"Uncategorized"`. Line 211 uses `listing.product.is_active` (`CatalogProduct` has `status` with choices draft/active/archived, no `is_active` boolean), rendering `"Inactive"`.
  - Fix: Use `listing.product.primary_category.name` and `listing.product.status == "active"`.
- [ ] **EXP-I2**: Broken Attribute Lookups on `sub_order.order` in Sub-Order Detail Template
  - `templates/ecommerce/marketplace/vendorsuborder/detail.html:237, 241`
  - Description: Line 237 references `sub_order.order.customer_party.name` (`EcommerceOrder` FK is `customer`), rendering fallback `"Shopper"`. Line 241 references `${{ sub_order.order.grand_total }}` (`EcommerceOrder` field is `total_amount`), rendering blank `$`.
  - Fix: Use `sub_order.order.customer.name` and `sub_order.order.total_amount`.
- [ ] **EXP-I3**: Missing `payout_status` Filter Dropdown in Sub-Orders List Template
  - `templates/ecommerce/marketplace/vendorsuborder/list.html:34-90`
  - Description: View parses `payout_status` and passes `payout_status_choices` and `payout_filter`, but filter form lacks the dropdown and pagination links drop the parameter.
  - Fix: Add `<select name="payout_status">` with `payout_status_choices` to the filter form and append to pagination query.
- [ ] **EXP-I4**: `TypeError` on `None` Comparison in Model `clean()` Methods
  - `apps/ecommerce/models/Marketplace/MarketplaceVendors.py:244-249`
  - `apps/ecommerce/models/Marketplace/VendorProductListings.py:179`
  - `apps/ecommerce/models/Marketplace/VendorSubOrders.py:215, 217`
  - Description: Direct `< Decimal("0.00")` comparisons without guarding for `None` raise unhandled `TypeError` if fields are unpopulated before validation.
  - Fix: Add `if self.<field> is not None and self.<field> < Decimal("0.00"):` guards.

### Minor
- [ ] **EXP-M1**: `VendorSubOrder.save()` Does Not Update Vendor Aggregate Rating
  - `apps/ecommerce/models/Marketplace/VendorSubOrders.py:257-260`
  - `apps/ecommerce/models/Marketplace/MarketplaceVendors.py:255-266`
  - Description: Vendor rating aggregates remain `0.00` because saving sub-orders with customer ratings never calls `vendor.update_rating()`.
  - Fix: Invoke `self.vendor.update_rating()` on sub-order save when rated.
- [ ] **EXP-M2**: Unrendered `order_lines` in Sub-Order Detail View
  - `templates/ecommerce/marketplace/vendorsuborder/detail.html:226-255`
  - Description: View provides `order_lines` context, but the template does not display an items table for ordered lines.
  - Fix: Render `order_lines` table in the parent order section.
