# Contract — Sub-module 9.11: Marketplace & Multi-Vendor (Module 9: eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.11 Marketplace & Multi-Vendor • **Module:** 9 eCommerce Management System • **App:** `apps/ecommerce`
- **Date:** 2026-10-31 • **Status:** FROZEN PRE-BUILD CONTRACT • **Phase:** 3.1 Spec
- **App Status:** Extending existing `apps/ecommerce/`. Next incremental migration: `0012_...`
- **Package Layout:** `Marketplace/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/ecommerce/marketplace/`.

---

## 1. Models & CHOICES Contract

All top-level models inherit from `apps.ecommerce.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `MarketplaceVendor` (`apps/ecommerce/models/Marketplace/MarketplaceVendors.py`)
- **Table:** `ecommerce_marketplace_vendor`
- **Number Prefix:** `EMKV` (`EMKV-00001`)
- **CHOICES:**
  - `STATUS_CHOICES = [("draft", "Draft Application"), ("submitted", "Application Submitted"), ("under_review", "Compliance Review"), ("approved", "Approved"), ("active", "Active Seller"), ("suspended", "Suspended (Policy/SLA Breach)"), ("terminated", "Terminated")]`
  - `KYC_STATUS_CHOICES = [("unsubmitted", "Unsubmitted"), ("pending", "Under Verification"), ("verified", "Identity Verified"), ("rejected", "Verification Rejected")]`
  - `COMMISSION_TYPE_CHOICES = [("percentage", "Percentage Only"), ("fixed", "Flat Fee Only"), ("combined", "Percentage + Flat Fee")]`
  - `PAYOUT_METHOD_CHOICES = [("stripe_connect", "Stripe Connect"), ("bank_transfer", "Direct Bank Transfer / ACH"), ("paypal", "PayPal Payouts"), ("manual_check", "Manual Check / Wire")]`
  - `TAX_FORM_CHOICES = [("not_required", "Not Required"), ("w9_pending", "W-9 Pending"), ("w9_received", "W-9 Received"), ("w8ben_received", "W-8BEN Received"), ("1099_eligible", "1099-K Eligible")]`
- **Fields:**
  - `tenant`: `ForeignKey("core.Tenant", on_delete=CASCADE, related_name="marketplace_vendors", db_index=True)`
  - `number`: `CharField(max_length=20, editable=False)`
  - `party`: `ForeignKey("core.Party", on_delete=PROTECT, related_name="marketplace_vendors", help_text="Unified legal party")`
  - `owner_user`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name="owned_marketplace_vendors")`
  - `store_name`: `CharField(max_length=150)`
  - `slug`: `SlugField(max_length=160)`
  - `headline`: `CharField(max_length=255, blank=True)`
  - `description`: `TextField(blank=True)`
  - `logo_url`: `URLField(blank=True)`
  - `banner_url`: `URLField(blank=True)`
  - `support_email`: `EmailField(blank=True)`
  - `support_phone`: `CharField(max_length=50, blank=True)`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `kyc_status`: `CharField(max_length=25, choices=KYC_STATUS_CHOICES, default="unsubmitted", db_index=True)`
  - `kyc_document_type`: `CharField(max_length=100, blank=True)`
  - `kyc_notes`: `TextField(blank=True)`
  - `kyc_verified_at`: `DateTimeField(null=True, blank=True)`
  - `commission_type`: `CharField(max_length=20, choices=COMMISSION_TYPE_CHOICES, default="percentage")`
  - `commission_rate`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal("15.00"))`
  - `fixed_fee_per_order`: `DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))`
  - `payout_method`: `CharField(max_length=25, choices=PAYOUT_METHOD_CHOICES, default="bank_transfer")`
  - `payout_account_identifier`: `CharField(max_length=120, blank=True)`
  - `min_payout_amount`: `DecimalField(max_digits=10, decimal_places=2, default=Decimal("50.00"))`
  - `tax_id`: `CharField(max_length=64, blank=True)`
  - `tax_form_status`: `CharField(max_length=25, choices=TAX_FORM_CHOICES, default="not_required")`
  - `shipping_lead_time_days`: `PositiveIntegerField(default=2)`
  - `return_policy`: `TextField(blank=True)`
  - `rating_average`: `DecimalField(max_digits=3, decimal_places=2, default=Decimal("0.00"))`
  - `rating_count`: `PositiveIntegerField(default=0)`
  - `is_featured`: `BooleanField(default=False)`
  - `suspension_reason`: `TextField(blank=True)`
  - `suspended_at`: `DateTimeField(null=True, blank=True)`
  - `suspended_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name="suspended_vendors")`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=["tenant", "number"], name="ecommerce_emkv_tenant_num_uniq")`
  - `UniqueConstraint(fields=["tenant", "slug"], name="ecommerce_emkv_tenant_slug_uniq")`
  - `Index(fields=["tenant", "status"], name="idx_emkv_ten_status")`
  - `Index(fields=["tenant", "kyc_status"], name="idx_emkv_ten_kyc")`

---

### 1.2 `VendorProductListing` (`apps/ecommerce/models/Marketplace/VendorProductListings.py`)
- **Table:** `ecommerce_vendor_product_listing`
- **Number Prefix:** `EVPL` (`EVPL-00001`)
- **CHOICES:**
  - `CONDITION_CHOICES = [("new", "Brand New"), ("refurbished", "Certified Refurbished"), ("used_like_new", "Used - Like New"), ("used_good", "Used - Good"), ("used_fair", "Used - Fair")]`
  - `MODERATION_STATUS_CHOICES = [("draft", "Draft"), ("pending_review", "Pending Moderation Review"), ("approved", "Approved & Live"), ("rejected", "Rejected"), ("changes_requested", "Changes Requested")]`
  - `COMPLIANCE_STATUS_CHOICES = [("pending", "Compliance Pending"), ("compliant", "Policy Compliant"), ("flagged_prohibited", "Prohibited Item Flag"), ("counterfeit_suspect", "Counterfeit Suspect"), ("ip_infringement", "Trademark / IP Violation")]`
- **Fields:**
  - `tenant`: `ForeignKey("core.Tenant", on_delete=CASCADE, related_name="vendor_listings", db_index=True)`
  - `number`: `CharField(max_length=20, editable=False)`
  - `vendor`: `ForeignKey("ecommerce.MarketplaceVendor", on_delete=CASCADE, related_name="product_listings")`
  - `product`: `ForeignKey("ecommerce.CatalogProduct", on_delete=CASCADE, related_name="vendor_listings")`
  - `variant`: `ForeignKey("ecommerce.ProductVariant", on_delete=SET_NULL, null=True, blank=True, related_name="vendor_listings")`
  - `seller_sku`: `CharField(max_length=80)`
  - `barcode`: `CharField(max_length=60, blank=True)`
  - `condition`: `CharField(max_length=20, choices=CONDITION_CHOICES, default="new")`
  - `condition_notes`: `CharField(max_length=255, blank=True)`
  - `asking_price`: `DecimalField(max_digits=12, decimal_places=2)`
  - `compare_at_price`: `DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)`
  - `cost_price`: `DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)`
  - `available_quantity`: `PositiveIntegerField(default=0)`
  - `low_stock_threshold`: `PositiveIntegerField(default=5)`
  - `lead_time_days`: `PositiveIntegerField(default=2)`
  - `moderation_status`: `CharField(max_length=25, choices=MODERATION_STATUS_CHOICES, default="pending_review", db_index=True)`
  - `compliance_status`: `CharField(max_length=25, choices=COMPLIANCE_STATUS_CHOICES, default="pending", db_index=True)`
  - `moderator_notes`: `TextField(blank=True)`
  - `rejection_reason`: `CharField(max_length=255, blank=True)`
  - `reviewed_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name="reviewed_listings")`
  - `submitted_at`: `DateTimeField(null=True, blank=True)`
  - `reviewed_at`: `DateTimeField(null=True, blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=["tenant", "number"], name="ecommerce_evpl_tenant_num_uniq")`
  - `UniqueConstraint(fields=["tenant", "vendor", "seller_sku"], name="ecommerce_evpl_ven_sku_uniq")`
  - `Index(fields=["tenant", "moderation_status", "is_active"], name="idx_evpl_ten_mod_act")`
  - `Index(fields=["tenant", "product", "asking_price"], name="idx_evpl_ten_prd_price")`

---

### 1.3 `VendorSubOrder` (`apps/ecommerce/models/Marketplace/VendorSubOrders.py`)
- **Table:** `ecommerce_vendor_sub_order`
- **Number Prefix:** `EVSO` (`EVSO-00001`)
- **CHOICES:**
  - `FULFILLMENT_STATUS_CHOICES = [("unfulfilled", "Unfulfilled"), ("allocated", "Stock Allocated"), ("picking", "Picking Items"), ("packed", "Package Packed"), ("shipped", "Shipped with Carrier"), ("delivered", "Delivered to Customer"), ("cancelled", "Cancelled")]`
  - `SLA_STATUS_CHOICES = [("on_time", "On Time (Within SLA)"), ("near_breach", "Approaching SLA Deadline"), ("breached", "SLA Breached (Late Dispatch)")]`
  - `PAYOUT_STATUS_CHOICES = [("accrued", "Accrued / Pending Settlement"), ("in_payout_batch", "Assigned to Payout Batch"), ("paid", "Disbursed to Vendor"), ("withheld_dispute", "Withheld (Open Dispute)"), ("refunded", "Refunded / Cancelled")]`
  - `DISPUTE_STATUS_CHOICES = [("none", "No Dispute"), ("disputed", "Customer Dispute Opened"), ("under_investigation", "Under Investigation"), ("resolved_merchant", "Resolved in Seller Favor"), ("resolved_customer", "Resolved in Buyer Favor (Refund Issued)"), ("escalated_to_admin", "Escalated to Operator Admin")]`
- **Fields:**
  - `tenant`: `ForeignKey("core.Tenant", on_delete=CASCADE, related_name="vendor_sub_orders", db_index=True)`
  - `number`: `CharField(max_length=20, editable=False)`
  - `vendor`: `ForeignKey("ecommerce.MarketplaceVendor", on_delete=PROTECT, related_name="sub_orders")`
  - `order`: `ForeignKey("ecommerce.EcommerceOrder", on_delete=CASCADE, related_name="vendor_sub_orders")`
  - `payout`: `ForeignKey("ecommerce.VendorPayout", on_delete=SET_NULL, null=True, blank=True, related_name="sub_orders")`
  - `fulfillment_status`: `CharField(max_length=25, choices=FULFILLMENT_STATUS_CHOICES, default="unfulfilled", db_index=True)`
  - `sla_status`: `CharField(max_length=20, choices=SLA_STATUS_CHOICES, default="on_time")`
  - `payout_status`: `CharField(max_length=25, choices=PAYOUT_STATUS_CHOICES, default="accrued", db_index=True)`
  - `subtotal_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`
  - `shipping_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`
  - `commission_rate`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal("15.00"))`
  - `commission_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`
  - `net_vendor_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`
  - `carrier_name`: `CharField(max_length=80, blank=True)`
  - `tracking_number`: `CharField(max_length=100, blank=True)`
  - `tracking_url`: `URLField(blank=True)`
  - `promised_dispatch_date`: `DateField(null=True, blank=True)`
  - `dispatched_at`: `DateTimeField(null=True, blank=True)`
  - `delivered_at`: `DateTimeField(null=True, blank=True)`
  - `customer_rating`: `PositiveSmallIntegerField(null=True, blank=True)`
  - `customer_feedback`: `TextField(blank=True)`
  - `seller_response`: `TextField(blank=True)`
  - `rated_at`: `DateTimeField(null=True, blank=True)`
  - `dispute_status`: `CharField(max_length=25, choices=DISPUTE_STATUS_CHOICES, default="none", db_index=True)`
  - `dispute_reason`: `CharField(max_length=150, blank=True)`
  - `dispute_notes`: `TextField(blank=True)`
  - `dispute_resolved_at`: `DateTimeField(null=True, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=["tenant", "number"], name="ecommerce_evso_tenant_num_uniq")`
  - `Index(fields=["tenant", "vendor", "fulfillment_status"], name="idx_evso_ten_ven_ful")`
  - `Index(fields=["tenant", "order"], name="idx_evso_ten_order")`
  - `Index(fields=["tenant", "payout_status"], name="idx_evso_ten_payout")`
  - `Index(fields=["tenant", "dispute_status"], name="idx_evso_ten_dispute")`

---

### 1.4 `VendorPayout` (`apps/ecommerce/models/Marketplace/VendorPayouts.py`)
- **Table:** `ecommerce_vendor_payout`
- **Number Prefix:** `EVPO` (`EVPO-00001`)
- **CHOICES:**
  - `PAYOUT_STATUS_CHOICES = [("draft", "Draft Batch"), ("pending_approval", "Pending Finance Approval"), ("processing", "Processing with Bank / Gateway"), ("completed", "Completed & Disbursed"), ("failed", "Disbursement Failed"), ("cancelled", "Cancelled")]`
  - `PAYOUT_METHOD_CHOICES = [("stripe_connect", "Stripe Connect Transfer"), ("bank_transfer", "Bank Wire / ACH"), ("paypal", "PayPal Payout"), ("manual_check", "Manual Check / Voucher")]`
- **Fields:**
  - `tenant`: `ForeignKey("core.Tenant", on_delete=CASCADE, related_name="vendor_payouts", db_index=True)`
  - `number`: `CharField(max_length=20, editable=False)`
  - `vendor`: `ForeignKey("ecommerce.MarketplaceVendor", on_delete=PROTECT, related_name="payouts")`
  - `period_start`: `DateField()`
  - `period_end`: `DateField()`
  - `gross_sales_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`
  - `commission_deducted`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`
  - `fees_deducted`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`
  - `refunds_deducted`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`
  - `tax_withholding_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`
  - `net_payout_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`
  - `payout_method`: `CharField(max_length=25, choices=PAYOUT_METHOD_CHOICES, default="bank_transfer")`
  - `payout_status`: `CharField(max_length=25, choices=PAYOUT_STATUS_CHOICES, default="draft", db_index=True)`
  - `reference_code`: `CharField(max_length=100, blank=True)`
  - `tax_year`: `PositiveIntegerField(null=True, blank=True)`
  - `is_1099_reported`: `BooleanField(default=False)`
  - `notes`: `TextField(blank=True)`
  - `approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name="approved_payouts")`
  - `processed_at`: `DateTimeField(null=True, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=["tenant", "number"], name="ecommerce_evpo_tenant_num_uniq")`
  - `Index(fields=["tenant", "vendor", "payout_status"], name="idx_evpo_ten_ven_stat")`
  - `Index(fields=["tenant", "period_end"], name="idx_evpo_ten_period")`

---

## 2. Forms Contract

### 2.1 `MarketplaceVendorForm` (`apps/ecommerce/forms/Marketplace/MarketplaceVendorForms.py`)
- **Model:** `MarketplaceVendor`
- **Excludes:** `tenant`, `number`, `rating_average`, `rating_count`, `kyc_verified_at`, `suspended_at`, `suspended_by`, `created_at`, `updated_at`
- **Additional Forms:**
  - `VendorKycVerificationForm`: fields `kyc_status`, `kyc_document_type`, `kyc_notes`
  - `VendorSuspensionForm`: fields `suspension_reason`

### 2.2 `VendorProductListingForm` (`apps/ecommerce/forms/Marketplace/VendorProductListingForms.py`)
- **Model:** `VendorProductListing`
- **Excludes:** `tenant`, `number`, `reviewed_at`, `reviewed_by`, `created_at`, `updated_at`
- **Additional Form:**
  - `ListingModerationForm`: fields `moderation_status`, `compliance_status`, `moderator_notes`, `rejection_reason`

### 2.3 `VendorSubOrderForm` (`apps/ecommerce/forms/Marketplace/VendorSubOrderForms.py`)
- **Model:** `VendorSubOrder`
- **Excludes:** `tenant`, `number`, `commission_amount`, `net_vendor_amount`, `rated_at`, `dispute_resolved_at`, `created_at`, `updated_at`
- **Additional Forms:**
  - `SubOrderFulfillmentForm`: fields `fulfillment_status`, `carrier_name`, `tracking_number`, `tracking_url`
  - `SubOrderDisputeForm`: fields `dispute_status`, `dispute_reason`, `dispute_notes`
  - `SubOrderReviewForm`: fields `customer_rating`, `customer_feedback`, `seller_response`

### 2.4 `VendorPayoutForm` (`apps/ecommerce/forms/Marketplace/VendorPayoutForms.py`)
- **Model:** `VendorPayout`
- **Excludes:** `tenant`, `number`, `net_payout_amount`, `processed_at`, `approved_by`, `created_at`, `updated_at`
- **Additional Form:**
  - `PayoutApprovalForm`: fields `payout_status`, `reference_code`, `notes`

---

## 3. URLs and Context Contract

All URLs live under namespace `ecommerce:`.

| URL Name | Pattern | View Function | Required Context Keys |
|---|---|---|---|
| `marketplace_console` | `marketplace/console/` | `marketplace_console` | `title`, `metrics`, `pending_kyc_vendors`, `pending_listings`, `sla_risk_suborders`, `active_disputes` |
| `marketplacevendor_list` | `marketplace/vendors/` | `marketplacevendor_list` | `vendors` (Page), `status_choices`, `kyc_status_choices`, `commission_type_choices`, `query`, `status_filter`, `kyc_filter`, `commission_filter` |
| `marketplacevendor_create` | `marketplace/vendors/create/` | `marketplacevendor_create` | `form`, `is_edit: False` |
| `marketplacevendor_detail` | `marketplace/vendors/<int:pk>/` | `marketplacevendor_detail` | `vendor`, `listings`, `sub_orders`, `payouts`, `disputes` |
| `marketplacevendor_edit` | `marketplace/vendors/<int:pk>/edit/` | `marketplacevendor_edit` | `vendor`, `form`, `is_edit: True` |
| `marketplacevendor_delete` | `marketplace/vendors/<int:pk>/delete/` | `marketplacevendor_delete` | POST-only |
| `marketplacevendor_verify_kyc` | `marketplace/vendors/<int:pk>/verify-kyc/` | `marketplacevendor_verify_kyc` | POST action |
| `marketplacevendor_suspend` | `marketplace/vendors/<int:pk>/suspend/` | `marketplacevendor_suspend` | POST action |
| `vendorproductlisting_list` | `marketplace/listings/` | `vendorproductlisting_list` | `listings` (Page), `moderation_status_choices`, `compliance_status_choices`, `condition_choices`, `vendors`, `query`, `status_filter`, `compliance_filter`, `vendor_filter` |
| `vendorproductlisting_create` | `marketplace/listings/create/` | `vendorproductlisting_create` | `form`, `is_edit: False` |
| `vendorproductlisting_detail` | `marketplace/listings/<int:pk>/` | `vendorproductlisting_detail` | `listing` |
| `vendorproductlisting_edit` | `marketplace/listings/<int:pk>/edit/` | `vendorproductlisting_edit` | `listing`, `form`, `is_edit: True` |
| `vendorproductlisting_delete` | `marketplace/listings/<int:pk>/delete/` | `vendorproductlisting_delete` | POST-only |
| `vendorproductlisting_moderate` | `marketplace/listings/<int:pk>/moderate/` | `vendorproductlisting_moderate` | POST action |
| `vendorsuborder_list` | `marketplace/sub-orders/` | `vendorsuborder_list` | `sub_orders` (Page), `fulfillment_status_choices`, `sla_status_choices`, `payout_status_choices`, `dispute_status_choices`, `vendors`, `query`, `fulfillment_filter`, `sla_filter`, `dispute_filter`, `vendor_filter` |
| `vendorsuborder_create` | `marketplace/sub-orders/create/` | `vendorsuborder_create` | `form`, `is_edit: False` |
| `vendorsuborder_detail` | `marketplace/sub-orders/<int:pk>/` | `vendorsuborder_detail` | `sub_order`, `order_lines` |
| `vendorsuborder_edit` | `marketplace/sub-orders/<int:pk>/edit/` | `vendorsuborder_edit` | `sub_order`, `form`, `is_edit: True` |
| `vendorsuborder_delete` | `marketplace/sub-orders/<int:pk>/delete/` | `vendorsuborder_delete` | POST-only |
| `vendorsuborder_fulfill` | `marketplace/sub-orders/<int:pk>/fulfill/` | `vendorsuborder_fulfill` | POST action |
| `vendorsuborder_dispute` | `marketplace/sub-orders/<int:pk>/dispute/` | `vendorsuborder_dispute` | POST action |
| `vendorpayout_list` | `marketplace/payouts/` | `vendorpayout_list` | `payouts` (Page), `payout_status_choices`, `payout_method_choices`, `vendors`, `query`, `status_filter`, `method_filter`, `vendor_filter` |
| `vendorpayout_create` | `marketplace/payouts/create/` | `vendorpayout_create` | `form`, `is_edit: False` |
| `vendorpayout_detail` | `marketplace/payouts/<int:pk>/` | `vendorpayout_detail` | `payout`, `settled_suborders` |
| `vendorpayout_edit` | `marketplace/payouts/<int:pk>/edit/` | `vendorpayout_edit` | `payout`, `form`, `is_edit: True` |
| `vendorpayout_delete` | `marketplace/payouts/<int:pk>/delete/` | `vendorpayout_delete` | POST-only |
| `vendorpayout_approve` | `marketplace/payouts/<int:pk>/approve/` | `vendorpayout_approve` | POST action |
| `vendorpayout_execute` | `marketplace/payouts/<int:pk>/execute/` | `vendorpayout_execute` | POST action |

---

## 4. Templates Contract

1. `templates/ecommerce/marketplace/console/dashboard.html`
2. `templates/ecommerce/marketplace/marketplacevendor/list.html`
3. `templates/ecommerce/marketplace/marketplacevendor/detail.html`
4. `templates/ecommerce/marketplace/marketplacevendor/form.html`
5. `templates/ecommerce/marketplace/vendorproductlisting/list.html`
6. `templates/ecommerce/marketplace/vendorproductlisting/detail.html`
7. `templates/ecommerce/marketplace/vendorproductlisting/form.html`
8. `templates/ecommerce/marketplace/vendorsuborder/list.html`
9. `templates/ecommerce/marketplace/vendorsuborder/detail.html`
10. `templates/ecommerce/marketplace/vendorsuborder/form.html`
11. `templates/ecommerce/marketplace/vendorpayout/list.html`
12. `templates/ecommerce/marketplace/vendorpayout/detail.html`
13. `templates/ecommerce/marketplace/vendorpayout/form.html`
