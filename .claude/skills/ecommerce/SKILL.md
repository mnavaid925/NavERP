---
name: ecommerce
description: Work on the eCommerce module (Module 9 — 9.1 Product Catalog, 9.2 Inventory & Stock, 9.3 Pricing & Promotion Engine, 9.4 Shopping Cart & Checkout, 9.5 Order Management System (OMS), 9.6 Customer Account & Profile: categories, products, variants, fulfillment centers, stock allocations, ATP, backorders, dynamic pricing, coupons, flash sales, competitor monitoring, carts, checkout funnels, orders, order lines, fulfillment routing rules, carrier dispatch tracking, return merchandise authorizations, customer account profiles, address preferences, wishlists, and GDPR privacy requests). Use when the user asks to add/change/debug anything under apps/ecommerce or templates/ecommerce, extend the eCommerce seeder, touch eCommerce sidebar wiring (LIVE_LINKS 9.1, 9.2, 9.3, 9.4, 9.5, or 9.6), or invokes /ecommerce.
---

# eCommerce Module (Module 9: 9.1 Catalog, 9.2 Inventory & Stock, 9.3 Pricing & Promotion, 9.4 Shopping Cart & Checkout, 9.5 Order Management System, 9.6 Customer Account & Profile)

The eCommerce Management System handles online store merchandising, product catalog management, SKU variants, product relationships, multi-node fulfillment center routing, real-time stock allocations, available-to-promise (ATP) calculation, backorder/pre-order waitlists, multi-channel inventory synchronization feeds, dynamic rule-based pricing engines, coupon code promotions, lightning flash sales, competitive repricing intelligence, persistent and guest shopping carts, 1-click cart abandonment recovery, multi-step and one-page checkout conversion funnels, flexible shipping calculation matrices, payment gateway orchestration, an enterprise omnichannel Order Management System (OMS) with intelligent order fulfillment routing, carrier dispatch tracking, and return merchandise authorization (RMA) workflows, as well as an enterprise Customer Account & Profile subsystem with tiered loyalty status, multi-mode authentication, address book delivery preferences, multi-wishlist curation with priority ranking, and statutory GDPR/CCPA privacy request management with automated JSON data portability exports and right-to-erasure account anonymization workflows. It integrates seamlessly with the NavERP core spine and physical supply chain:
- **Tenant Isolation**: Every model inherits `TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`). All queries and lookups are strictly tenant-scoped (`tenant=request.tenant`).
- **Physical Inventory Boundary**: Products, variants, and fulfillment centers link to `scm.Item` and `scm.Location` via string foreign keys. Module 9 does not duplicate inventory ledger balances or physical bin movements; physical warehouse stock and valuation remain anchored in `apps/scm` and `apps/inventory`, while eCommerce manages digital storefront availability, reservations, buffers, and channel broadcasting.
- **App Path**: `apps/ecommerce/`
- **Templates**: `templates/ecommerce/`
- **URL Prefix**: `/ecommerce/` (`app_name="ecommerce"`)
- **Mounted in**: `config/urls.py` as `path("ecommerce/", include("apps.ecommerce.urls", namespace="ecommerce"))`
- **Installed App**: `apps.ecommerce` in `config/settings.py`

---

## 1. App Layout & Package Architecture

All four layers (`models`, `forms`, `views`, `urls`) are organized as packages partitioned by sub-module:

```
apps/ecommerce/
├── models/
│   ├── _base.py                     # TenantNumbered abstract base model
│   ├── ProductCatalog/
│   │   ├── StoreCategories.py       # StoreCategory model (ECAT-)
│   │   ├── CatalogProducts.py       # CatalogProduct model (EPRD-)
│   │   ├── ProductVariants.py       # ProductVariant model (PVR-)
│   │   └── ProductRelationships.py  # ProductRelationship model (PRL-)
│   ├── InventoryStock/
│   │   ├── FulfillmentCenters.py    # FulfillmentCenter model (EFC-)
│   │   ├── InventoryAllocations.py  # InventoryAllocation model (EAL-)
│   │   ├── BackorderPolicies.py     # BackorderPolicy model (EBK-)
│   │   └── ChannelInventorySyncs.py # ChannelInventorySync model (ESYN-)
│   ├── PricingPromotion/
│   │   ├── DynamicPriceRules.py     # DynamicPriceRule model (EDPR-)
│   │   ├── CouponPromotions.py      # CouponPromotion model (ECPN-)
│   │   ├── FlashSales.py            # FlashSale model (EFLS-)
│   │   └── CompetitorPriceMonitors.py # CompetitorPriceMonitor model (ECPM-)
│   ├── CartCheckout/
│   │   ├── Carts.py                 # Cart (ECRT-) & CartItem models
│   │   ├── CheckoutSessions.py      # CheckoutSession model (ECKS-)
│   │   ├── ShippingMethods.py       # ShippingMethodConfig model (ESHP-)
│   │   └── PaymentMethods.py        # PaymentMethodConfig model (EPMC-)
│   ├── OrderManagement/
│   │   ├── EcommerceOrders.py       # EcommerceOrder (EORD-) & EcommerceOrderLine models
│   │   ├── OrderRoutingRules.py     # OrderRoutingRule model (EORT-)
│   │   ├── OrderFulfillments.py     # OrderFulfillment model (EFUL-)
│   │   └── ReturnMerchandiseAuthorizations.py # ReturnMerchandiseAuthorization model (ERMA-)
│   ├── CustomerProfile/
│   │   ├── CustomerAccountProfiles.py # CustomerAccountProfile model (ECAP-)
│   │   ├── CustomerAddressPreferences.py # CustomerAddressPreference model (ECAD-)
│   │   ├── CustomerWishlists.py     # CustomerWishlist (EWSL-) & CustomerWishlistItem models
│   │   └── CustomerPrivacyRequests.py # CustomerPrivacyRequest model (ECPR-)
│   └── __init__.py                  # Surgical re-exports of all models
├── forms/
│   ├── _common.py                   # TenantModelForm, TenantUniqueMixin, reject_foreign
│   ├── ProductCatalog/
│   │   ├── StoreCategories.py       # StoreCategoryForm
│   │   ├── CatalogProducts.py       # CatalogProductForm
│   │   ├── ProductVariants.py       # ProductVariantForm
│   │   ├── ProductRelationships.py  # ProductRelationshipForm
│   │   └── BulkOperations.py        # ProductImportForm
│   ├── InventoryStock/
│   │   ├── FulfillmentCenters.py    # FulfillmentCenterForm
│   │   ├── InventoryAllocations.py  # InventoryAllocationForm, StockAdjustmentActionForm
│   │   ├── BackorderPolicies.py     # BackorderPolicyForm
│   │   └── ChannelInventorySyncs.py # ChannelInventorySyncForm
│   ├── PricingPromotion/
│   │   ├── DynamicPriceRules.py     # DynamicPriceRuleForm
│   │   ├── CouponPromotions.py      # CouponPromotionForm
│   │   ├── FlashSales.py            # FlashSaleForm
│   │   └── CompetitorPriceMonitors.py # CompetitorPriceMonitorForm
│   ├── CartCheckout/
│   │   ├── Carts.py                 # CartForm, CartItemForm
│   │   ├── CheckoutSessions.py      # CheckoutSessionForm, CheckoutStepAdvanceForm
│   │   ├── ShippingMethods.py       # ShippingMethodConfigForm
│   │   └── PaymentMethods.py        # PaymentMethodConfigForm
│   ├── OrderManagement/
│   │   ├── EcommerceOrders.py       # EcommerceOrderForm, EcommerceOrderLineForm
│   │   ├── OrderRoutingRules.py     # OrderRoutingRuleForm
│   │   ├── OrderFulfillments.py     # OrderFulfillmentForm
│   │   └── ReturnMerchandiseAuthorizations.py # ReturnMerchandiseAuthorizationForm
│   ├── CustomerProfile/
│   │   ├── CustomerAccountProfiles.py # CustomerAccountProfileForm
│   │   ├── CustomerAddressPreferences.py # CustomerAddressPreferenceForm
│   │   ├── CustomerWishlists.py     # CustomerWishlistForm, CustomerWishlistItemForm
│   │   └── CustomerPrivacyRequests.py # CustomerPrivacyRequestForm
│   └── __init__.py                  # Re-exports of all forms
├── views/
│   ├── _common.py                   # ecommerce_scope, ecommerce_object, csv_safe, write_audit_log
│   ├── ProductCatalog/
│   │   ├── Overview.py              # catalog_overview dashboard
│   │   ├── StoreCategories.py       # storecategory CRUD
│   │   ├── CatalogProducts.py       # catalogproduct CRUD + publish action
│   │   ├── ProductVariants.py       # productvariant CRUD
│   │   ├── ProductRelationships.py  # productrelationship CRUD
│   │   └── BulkOperations.py        # product_import_csv, product_export_csv
│   ├── InventoryStock/
│   │   ├── Operations.py            # inventory_operations console dashboard
│   │   ├── FulfillmentCenters.py    # fulfillmentcenter CRUD
│   │   ├── InventoryAllocations.py  # inventoryallocation CRUD + stock adjust
│   │   ├── BackorderPolicies.py     # backorderpolicy CRUD
│   │   └── ChannelInventorySyncs.py # channelinventorysync CRUD + broadcast trigger
│   ├── PricingPromotion/
│   │   ├── DynamicPriceRules.py     # dynamicpricerule CRUD
│   │   ├── CouponPromotions.py      # couponpromotion CRUD
│   │   ├── FlashSales.py            # flashsale CRUD
│   │   └── CompetitorPriceMonitors.py # competitorpricemonitor CRUD + sync action
│   ├── CartCheckout/
│   │   ├── Carts.py                 # cart CRUD + recover action
│   │   ├── CheckoutSessions.py      # checkoutsession CRUD + advance action
│   │   ├── ShippingMethods.py       # shippingmethodconfig CRUD + toggle action
│   │   └── PaymentMethods.py        # paymentmethodconfig CRUD + toggle action
│   ├── OrderManagement/
│   │   ├── EcommerceOrders.py       # ecommerceorder CRUD + cancel action
│   │   ├── OrderRoutingRules.py     # orderroutingrule CRUD
│   │   ├── OrderFulfillments.py     # orderfulfillment CRUD + ship action
│   │   └── ReturnMerchandiseAuthorizations.py # returnmerchandiseauthorization CRUD + complete action
│   ├── CustomerProfile/
│   │   ├── CustomerAccountProfiles.py # customeraccountprofile CRUD
│   │   ├── CustomerAddressPreferences.py # customeraddresspreference CRUD
│   │   ├── CustomerWishlists.py     # customerwishlist CRUD + item_add, item_delete
│   │   └── CustomerPrivacyRequests.py # customerprivacyrequest CRUD + generate_export, anonymize
│   └── __init__.py                  # Re-exports of all views
├── urls/
│   ├── ProductCatalog/
│   │   ├── Overview.py              # overview & dashboard paths
│   │   ├── StoreCategories.py       # categories/ paths
│   │   ├── CatalogProducts.py       # products/ paths
│   │   ├── ProductVariants.py       # variants/ paths
│   │   ├── ProductRelationships.py  # relationships/ paths
│   │   └── BulkOperations.py        # import/ and export/ paths
│   ├── InventoryStock/
│   │   ├── Operations.py            # inventory/ console path
│   │   ├── FulfillmentCenters.py    # inventory/centers/ paths
│   │   ├── InventoryAllocations.py  # inventory/allocations/ paths
│   │   ├── BackorderPolicies.py     # inventory/backorders/ paths
│   │   └── ChannelInventorySyncs.py # inventory/sync/ paths
│   ├── PricingPromotion/
│   │   ├── DynamicPriceRules.py     # pricing/rules/ paths
│   │   ├── CouponPromotions.py      # pricing/coupons/ paths
│   │   ├── FlashSales.py            # pricing/flash-sales/ paths
│   │   └── CompetitorPriceMonitors.py # pricing/competitors/ paths
│   ├── CartCheckout/
│   │   ├── Carts.py                 # cart-checkout/carts/ paths
│   │   ├── CheckoutSessions.py      # cart-checkout/sessions/ paths
│   │   ├── ShippingMethods.py       # cart-checkout/shipping-methods/ paths
│   │   └── PaymentMethods.py        # cart-checkout/payment-methods/ paths
│   ├── OrderManagement/
│   │   ├── EcommerceOrders.py       # orders/ paths
│   │   ├── OrderRoutingRules.py     # routing-rules/ paths
│   │   ├── OrderFulfillments.py     # fulfillments/ paths
│   │   └── ReturnMerchandiseAuthorizations.py # returns/ paths
│   ├── CustomerProfile/
│   │   ├── CustomerAccountProfiles.py # customer-profiles/ paths
│   │   ├── CustomerAddressPreferences.py # address-preferences/ paths
│   │   ├── CustomerWishlists.py     # wishlists/ paths
│   │   └── CustomerPrivacyRequests.py # privacy-requests/ paths
│   └── __init__.py                  # Concatenates all urlpatterns with app_name="ecommerce"
├── admin.py                         # Django admin registrations
├── apps.py                          # EcommerceConfig
└── management/commands/
    └── seed_ecommerce.py            # Idempotent demo data seeder
```

---

## 2. Models & Entities

### Sub-module 9.1: Product Catalog Management
| Model | Prefix | Key Fields | Core / External FKs | Key Methods / Properties |
|---|---|---|---|---|
| `StoreCategory` | `ECAT-` | `name`, `slug`, `parent`, `display_order`, `is_active`, `include_in_menu` | `self` (hierarchical) | `full_path`, `get_breadcrumbs()` (cycle-safe) |
| `CatalogProduct` | `EPRD-` | `name`, `slug`, `status` (draft/active/archived), `visibility` (storefront/hidden/search_only), `brand`, `pim_completeness` | `primary_category`, `categories` (M2M), `scm.Item` | `calculate_pim_completeness()`, `price_range_display`, `active_variants` |
| `ProductVariant` | `PVR-` | `sku`, `name`, `option_values` (JSON), `price`, `compare_at_price`, `cost_price`, `is_active`, `weight_kg` | `product`, `scm.Item` | `is_on_sale`, `options_summary`, `margin_pct` |
| `ProductRelationship`| `PRL-` | `relationship_type` (cross_sell, up_sell, accessory, bundle_kit, bought_together), `discount_pct`, `is_active` | `source_product`, `target_product` | Unique per `(tenant, source, target, type)` |

### Sub-module 9.2: Inventory & Stock Management
| Model | Prefix | Key Fields | Core / External FKs | Key Methods / Properties |
|---|---|---|---|---|
| `FulfillmentCenter` | `EFC-` | `name`, `code`, `center_type`, `priority`, `is_active`, `supports_pick_pack_ship`, `supports_customer_pickup`, `daily_cutoff_time`, address fields | `scm.Location` | Unique per `(tenant, code)`. Priority routing order. |
| `InventoryAllocation` | `EAL-` | `quantity_on_hand`, `quantity_allocated`, `safety_stock_buffer`, `low_stock_threshold`, `zone_bin`, `last_counted_at` | `product`, `variant`, `fulfillment_center` | `available_to_promise` (`max(0, on_hand - allocated - safety_buffer)`), `is_low_stock_alert` |
| `BackorderPolicy` | `EBK-` | `policy_type` (deny_when_empty, allow_backorder_with_notice, pre_order_only), `storefront_message`, `expected_availability_date`, `max_backorder_quantity`, `current_backorder_count`, `auto_notify_waitlist` | `variant` (OneToOne) | Unique per `(tenant, variant)` |
| `ChannelInventorySync`| `ESYN-`| `channel_type`, `channel_name`, `sync_mode`, `allocation_buffer_pct`, `last_synced_quantity`, `sync_status`, `last_synced_at` | `variant`, `fulfillment_center` (optional) | `calculate_sync_quantity()` (applies buffer percentage to ATP) |

### Sub-module 9.3: Pricing & Promotion Engine
| Model | Prefix | Key Fields | Core / External FKs | Key Methods / Properties |
|---|---|---|---|---|
| `DynamicPriceRule` | `EDPR-` | `name`, `rule_type`, `adjustment_value`, `scope`, `customer_segment`, `loyalty_tier`, `min_quantity`, `priority`, `is_active` | `category`, `product`, `variant` | `calculate_price(base_price)`, `is_currently_valid` |
| `CouponPromotion` | `ECPN-` | `code`, `name`, `discount_type`, `discount_value`, `min_spend`, `max_discount_amount`, `usage_limit_total`, `is_active` | `customer` (`core.Party`) | `calculate_discount(cart_subtotal)`, `is_currently_valid`, `remaining_redemptions` |
| `FlashSale` | `EFLS-` | `title`, `status`, `discount_percentage`, `flash_price`, `inventory_cap`, `units_sold`, `max_units_per_order`, `start_time`, `end_time` | `product`, `variant`, `category` | `calculate_effective_price(original_price)`, `is_live`, `remaining_units`, `sold_percentage` |
| `CompetitorPriceMonitor` | `ECPM-` | `competitor_name`, `competitor_url`, `competitor_price`, `match_strategy`, `beat_by_value`, `min_margin_pct`, `floor_price`, `status` | `product`, `variant` | `margin_floor_price`, `suggested_price`, `is_margin_risk` |

### Sub-module 9.4: Shopping Cart & Checkout
| Model | Prefix | Key Fields | Core / External FKs | Key Methods / Properties |
|---|---|---|---|---|
| `Cart` | `ECRT-` | `customer`, `session_key`, `email`, `status`, `currency`, `subtotal`, `discount_total`, `tax_total`, `shipping_total`, `grand_total`, `coupon_code`, `recovery_token` | `core.Party` (`customer`) | `recalculate_totals()`, `generate_recovery_token()`, `mark_abandoned()`, `item_count` |
| `CartItem` | — | `cart`, `product`, `variant`, `quantity`, `unit_price`, `total_price`, `custom_attributes` | `ecommerce.CatalogProduct`, `ecommerce.ProductVariant` | Auto calculates `total_price = unit_price * quantity` |
| `CheckoutSession` | `ECKS-` | `cart`, `customer`, `email`, `phone`, `flow_type`, `current_step`, `status`, shipping fields, billing fields, financial totals, `payment_status`, `expires_at`, `completed_at` | `Cart`, `core.Party`, `ShippingMethodConfig`, `PaymentMethodConfig`, `accounting.TaxCode` | `advance_step()` (funnel progression), auto fills billing address |
| `ShippingMethodConfig` | `ESHP-` | `name`, `code`, `carrier`, `calculation_type`, `base_rate`, `cost_per_kg`, `free_shipping_threshold`, `destination_countries`, `is_active`, `sort_order` | — | `calculate_rate(subtotal, total_weight_kg)` (flat, weight tiered, free threshold, pickup) |
| `PaymentMethodConfig` | `EPMC-` | `name`, `provider`, `method_category`, `environment`, `is_active`, `display_order`, `fee_type`, `fee_amount`, `min_order_amount`, `max_order_amount`, `supported_currencies` | — | `calculate_surcharge(subtotal)`, `is_eligible_for_amount(subtotal)` |

### Sub-module 9.5: Order Management System (OMS)
| Model | Prefix | Key Fields | Core / External FKs | Key Methods / Properties |
|---|---|---|---|---|
| `EcommerceOrder` | `EORD-` | `customer`, `guest_email`, `currency`, `status`, `payment_status`, `fulfillment_status`, `fraud_risk_level`, `fraud_score`, `subtotal_amount`, `discount_amount`, `shipping_amount`, `tax_amount`, `total_amount`, `applied_coupon`, shipping/billing addresses | `core.Party` (`customer`), `accounting.Currency`, `CouponPromotion`, `core.Address` | `recalculate_totals()`, `can_cancel()`, `cancel_order(reason)` |
| `EcommerceOrderLine` | — | `order`, `product`, `variant`, `sku`, `product_name`, `quantity`, `fulfilled_quantity`, `returned_quantity`, `unit_price`, `unit_discount`, `line_total`, `status` | `ecommerce.CatalogProduct`, `ecommerce.ProductVariant` | Computes `line_total = (quantity * unit_price) - (quantity * unit_discount)` |
| `OrderRoutingRule` | `EORT-` | `name`, `strategy` (closest_location, fewest_splits, highest_inventory, drop_ship_preferred, manual), `priority`, `destination_country`, `destination_region`, `preferred_fulfillment_center`, `allow_split_shipment`, `enable_dropship`, `is_active` | `ecommerce.FulfillmentCenter` | Evaluates closest fulfillment nodes and split shipment allowance |
| `OrderFulfillment` | `EFUL-` | `order`, `fulfillment_center`, `carrier_name`, `tracking_number`, `tracking_url`, `status`, `shipping_cost`, `shipped_at`, `estimated_delivery_date`, `actual_delivery_date`, `shipping_label_url`, `notification_sent` | `ecommerce.FulfillmentCenter` | `mark_shipped()`, `mark_delivered()`, auto-syncs parent order fulfillment status |
| `ReturnMerchandiseAuthorization` | `ERMA-` | `order`, `customer`, `return_type` (refund, exchange, store_credit), `status`, `reason`, `restocking_fee`, `refund_amount`, `refund_status`, `restocking_status`, `restocking_center` | `core.Party` (`customer`), `ecommerce.FulfillmentCenter` | `authorize()`, `complete_settlement()`, validates restocking fee <= refund amount |

### Sub-module 9.6: Customer Account & Profile
| Model | Prefix | Key Fields | Core / External FKs | Key Methods / Properties |
|---|---|---|---|---|
| `CustomerAccountProfile` | `ECAP-` | `customer`, `user`, `tier`, `status`, `auth_mode`, `phone_number`, `phone_verified`, `preferred_currency`, `preferred_language`, `email_marketing_opt_in`, `sms_marketing_opt_in`, `notification_frequency`, `marketing_consent_at`, `unsubscribe_token`, `total_spent`, `order_count`, `last_order_at`, `internal_notes` | `core.Party` (`customer`), `settings.AUTH_USER_MODEL`, `accounting.Currency` | Unique per `(tenant, customer)`, auto-generates `unsubscribe_token` and captures consent timestamp |
| `CustomerAddressPreference` | `ECAD-` | `customer`, `address`, `label`, `is_default_shipping`, `is_default_billing`, `recipient_name`, `contact_phone`, `delivery_instructions`, `preferred_delivery_window`, `requires_signature` | `core.Party` (`customer`), `core.Address` | Manages single default shipping & billing address across customer preferences on save |
| `CustomerWishlist` | `EWSL-` | `customer`, `name`, `slug`, `visibility` (private/shared/public), `is_default`, `share_token`, `notes` | `core.Party` (`customer`) | Auto slug generation, token generation, single default wishlist flag management on save |
| `CustomerWishlistItem` | — | `wishlist`, `product`, `variant`, `desired_quantity`, `priority` (low/medium/high/highest), `comment` | `CustomerWishlist`, `ecommerce.CatalogProduct`, `ecommerce.ProductVariant` | TenantOwned, priority ranking, variant-product relationship validation |
| `CustomerPrivacyRequest` | `ECPR-` | `customer`, `request_type` (access_export, rectification, erasure_anonymize, restriction, opt_out_sale), `status`, `statutory_deadline`, `completed_at`, `requested_by_email`, `verification_method`, `data_export_payload`, `resolution_notes` | `core.Party` (`customer`) | Defaults 30-day statutory deadline, auto-stamps `completed_at`, triggers automated JSON export & account anonymization |



---

## 3. URLs & Routes

All routes live under `/ecommerce/` with namespace `ecommerce`:

### 9.1 Catalog Routes
| URL Pattern | View Function | URL Name | Description |
|---|---|---|---|
| `overview/` | `catalog_overview` | `catalog_overview` | Merchandising & catalog KPI dashboard |
| `""` | `catalog_overview` | `dashboard` | Alias to overview |
| `categories/` | `storecategory_list` | `storecategory_list` | Category tree list & search |
| `categories/create/` | `storecategory_create` | `storecategory_create` | Create category |
| `categories/<int:pk>/` | `storecategory_detail` | `storecategory_detail` | Category detail with subcategories & products |
| `categories/<int:pk>/edit/`| `storecategory_edit` | `storecategory_edit` | Edit category |
| `categories/<int:pk>/delete/`| `storecategory_delete` | `storecategory_delete` | Delete category (POST only, tenant admin required) |
| `products/` | `catalogproduct_list` | `catalogproduct_list` | Product catalog grid/list with filters |
| `products/create/` | `catalogproduct_create` | `catalogproduct_create` | Create catalog product |
| `products/import/` | `product_import_csv` | `product_import_csv` | Bulk CSV product/variant import |
| `products/export/` | `product_export_csv` | `product_export_csv` | Bulk CSV export |
| `products/<int:pk>/` | `catalogproduct_detail` | `catalogproduct_detail` | Product detail with variants & relationships |
| `products/<int:pk>/edit/` | `catalogproduct_edit` | `catalogproduct_edit` | Edit catalog product |
| `products/<int:pk>/delete/`| `catalogproduct_delete` | `catalogproduct_delete` | Delete product (POST only, tenant admin required) |
| `products/<int:pk>/publish/`| `catalogproduct_publish` | `catalogproduct_publish` | Quick toggle draft/active status (POST only) |
| `variants/` | `productvariant_list` | `productvariant_list` | SKU variants list & filter |
| `variants/create/` | `productvariant_create` | `productvariant_create` | Create variant (supports `?product=<id>`) |
| `variants/<int:pk>/` | `productvariant_detail` | `productvariant_detail` | Variant detail view |
| `variants/<int:pk>/edit/` | `productvariant_edit` | `productvariant_edit` | Edit variant |
| `variants/<int:pk>/delete/`| `productvariant_delete` | `productvariant_delete` | Delete variant (POST only, tenant admin required) |
| `relationships/` | `productrelationship_list` | `productrelationship_list` | Merchandising relationships list |
| `relationships/create/` | `productrelationship_create` | `productrelationship_create` | Create relationship (supports `?source=<id>`) |
| `relationships/<int:pk>/`| `productrelationship_detail`| `productrelationship_detail`| Relationship detail view |
| `relationships/<int:pk>/edit/`| `productrelationship_edit`| `productrelationship_edit`| Edit relationship |
| `relationships/<int:pk>/delete/`| `productrelationship_delete`| `productrelationship_delete`| Delete relationship (POST only, tenant admin required) |

### 9.2 Inventory & Stock Routes
| URL Pattern | View Function | URL Name | Description |
|---|---|---|---|
| `inventory/` | `inventory_operations` | `inventory_operations` | Operations console & stock KPI overview |
| `inventory/centers/` | `fulfillmentcenter_list` | `fulfillmentcenter_list` | Centers list with type & status filters |
| `inventory/centers/create/` | `fulfillmentcenter_create` | `fulfillmentcenter_create` | Add new fulfillment center / 3PL node |
| `inventory/centers/<int:pk>/` | `fulfillmentcenter_detail` | `fulfillmentcenter_detail` | Center detail with stocked SKUs and sync feeds |
| `inventory/centers/<int:pk>/edit/` | `fulfillmentcenter_edit` | `fulfillmentcenter_edit` | Edit fulfillment center |
| `inventory/centers/<int:pk>/delete/`| `fulfillmentcenter_delete` | `fulfillmentcenter_delete` | Delete fulfillment center (POST, tenant admin) |
| `inventory/allocations/` | `inventoryallocation_list` | `inventoryallocation_list` | Stock allocation table with ATP & low stock filters |
| `inventory/allocations/create/` | `inventoryallocation_create` | `inventoryallocation_create` | Create allocation (supports `?center=` & `?variant=`) |
| `inventory/allocations/<int:pk>/` | `inventoryallocation_detail` | `inventoryallocation_detail` | Allocation detail with ATP equation & audit log |
| `inventory/allocations/<int:pk>/edit/` | `inventoryallocation_edit` | `inventoryallocation_edit` | Edit allocation parameters & safety buffers |
| `inventory/allocations/<int:pk>/adjust/` | `inventoryallocation_adjust` | `inventoryallocation_adjust` | Stock adjustment workflow (cycle count, damage, etc.) |
| `inventory/allocations/<int:pk>/delete/`| `inventoryallocation_delete` | `inventoryallocation_delete` | Delete allocation (POST, tenant admin) |
| `inventory/backorders/` | `backorderpolicy_list` | `backorderpolicy_list` | Backorder & pre-order policy list |
| `inventory/backorders/create/` | `backorderpolicy_create` | `backorderpolicy_create` | Configure backorder/pre-order policy |
| `inventory/backorders/<int:pk>/` | `backorderpolicy_detail` | `backorderpolicy_detail` | Policy detail with waitlist commitments |
| `inventory/backorders/<int:pk>/edit/` | `backorderpolicy_edit` | `backorderpolicy_edit` | Edit policy message, caps, and dates |
| `inventory/backorders/<int:pk>/delete/`| `backorderpolicy_delete` | `backorderpolicy_delete` | Delete policy (POST, tenant admin) |
| `inventory/sync/` | `channelinventorysync_list` | `channelinventorysync_list` | Multi-channel sync feeds list |
| `inventory/sync/create/` | `channelinventorysync_create` | `channelinventorysync_create` | Connect new channel inventory feed |
| `inventory/sync/<int:pk>/` | `channelinventorysync_detail` | `channelinventorysync_detail` | Feed detail with broadcast calculations & diagnostics |
| `inventory/sync/<int:pk>/edit/` | `channelinventorysync_edit` | `channelinventorysync_edit` | Edit sync mode, buffers, or status |
| `inventory/sync/<int:pk>/delete/` | `channelinventorysync_delete` | `channelinventorysync_delete` | Delete channel feed (POST, tenant admin) |
| `inventory/sync/<int:pk>/trigger/` | `channelinventorysync_trigger` | `channelinventorysync_trigger` | On-demand instant stock broadcast push (POST) |

### 9.3 Pricing & Promotion Routes
| URL Pattern | View Function | URL Name | Description |
|---|---|---|---|
| `pricing/rules/` | `dynamicpricerule_list` | `dynamicpricerule_list` | Rules list with type, scope, and segment filters |
| `pricing/rules/create/` | `dynamicpricerule_create` | `dynamicpricerule_create` | Create dynamic pricing rule |
| `pricing/rules/<int:pk>/` | `dynamicpricerule_detail` | `dynamicpricerule_detail` | Rule detail view with targeting scope and priority |
| `pricing/rules/<int:pk>/edit/` | `dynamicpricerule_edit` | `dynamicpricerule_edit` | Edit pricing rule parameters |
| `pricing/rules/<int:pk>/delete/` | `dynamicpricerule_delete` | `dynamicpricerule_delete` | Delete rule (POST, tenant admin) |
| `pricing/coupons/` | `couponpromotion_list` | `couponpromotion_list` | Coupons list with type and status filters |
| `pricing/coupons/create/` | `couponpromotion_create` | `couponpromotion_create` | Create coupon voucher code |
| `pricing/coupons/<int:pk>/` | `couponpromotion_detail` | `couponpromotion_detail` | Coupon detail with redemption stats |
| `pricing/coupons/<int:pk>/edit/` | `couponpromotion_edit` | `couponpromotion_edit` | Edit coupon limits, spend threshold, and dates |
| `pricing/coupons/<int:pk>/delete/` | `couponpromotion_delete` | `couponpromotion_delete` | Delete coupon (POST, tenant admin) |
| `pricing/flash-sales/` | `flashsale_list` | `flashsale_list` | Flash sales list with live status indicators |
| `pricing/flash-sales/create/` | `flashsale_create` | `flashsale_create` | Schedule new lightning flash sale |
| `pricing/flash-sales/<int:pk>/` | `flashsale_detail` | `flashsale_detail` | Flash sale detail with live progress bar and countdown |
| `pricing/flash-sales/<int:pk>/edit/` | `flashsale_edit` | `flashsale_edit` | Edit flash sale pricing, cap, or timing |
| `pricing/flash-sales/<int:pk>/delete/` | `flashsale_delete` | `flashsale_delete` | Delete flash sale (POST, tenant admin) |
| `pricing/competitors/` | `competitorpricemonitor_list` | `competitorpricemonitor_list` | Competitor price tracking table with margin flags |
| `pricing/competitors/create/` | `competitorpricemonitor_create` | `competitorpricemonitor_create` | Add competitor listing to monitor |
| `pricing/competitors/<int:pk>/` | `competitorpricemonitor_detail` | `competitorpricemonitor_detail` | Monitor detail with suggested repricing and margin floor |
| `pricing/competitors/<int:pk>/edit/` | `competitorpricemonitor_edit` | `competitorpricemonitor_edit` | Edit match strategy, undercut margins, and floor |
| `pricing/competitors/<int:pk>/delete/` | `competitorpricemonitor_delete` | `competitorpricemonitor_delete` | Delete monitor (POST, tenant admin) |
| `pricing/competitors/<int:pk>/sync/` | `competitorpricemonitor_sync` | `competitorpricemonitor_sync` | Trigger instant competitor price scrape check (POST) |

### 9.4 Shopping Cart & Checkout Routes
| URL Pattern | View Function | URL Name | Description |
|---|---|---|---|
| `cart-checkout/carts/` | `cart_list` | `cart_list` | Shopping carts table with search and status filters |
| `cart-checkout/carts/create/` | `cart_create` | `cart_create` | Manually initiate cart for customer or guest |
| `cart-checkout/carts/<int:pk>/` | `cart_detail` | `cart_detail` | Cart detail with items, customer, totals, and abandonment recovery |
| `cart-checkout/carts/<int:pk>/edit/` | `cart_edit` | `cart_edit` | Edit cart attributes, coupon code, status, and notes |
| `cart-checkout/carts/<int:pk>/delete/` | `cart_delete` | `cart_delete` | Delete cart (POST only, tenant admin) |
| `cart-checkout/carts/<int:pk>/recover/` | `cart_recover` | `cart_recover` | Generate recovery token & trigger recovery email (POST) |
| `cart-checkout/sessions/` | `checkoutsession_list` | `checkoutsession_list` | Checkout sessions table with flow & status filters |
| `cart-checkout/sessions/create/` | `checkoutsession_create` | `checkoutsession_create` | Launch checkout session from existing active cart |
| `cart-checkout/sessions/<int:pk>/` | `checkoutsession_detail` | `checkoutsession_detail` | Checkout session detail: shipping/billing address, tax breakdown, totals |
| `cart-checkout/sessions/<int:pk>/edit/` | `checkoutsession_edit` | `checkoutsession_edit` | Edit checkout session information |
| `cart-checkout/sessions/<int:pk>/delete/` | `checkoutsession_delete` | `checkoutsession_delete` | Delete checkout session (POST only, tenant admin) |
| `cart-checkout/sessions/<int:pk>/advance/` | `checkoutsession_advance` | `checkoutsession_advance` | Advance session to next conversion funnel step (POST) |
| `cart-checkout/shipping-methods/` | `shippingmethodconfig_list` | `shippingmethodconfig_list` | Shipping methods configuration table |
| `cart-checkout/shipping-methods/create/` | `shippingmethodconfig_create` | `shippingmethodconfig_create` | Add shipping method & carrier rate calculation rule |
| `cart-checkout/shipping-methods/<int:pk>/` | `shippingmethodconfig_detail` | `shippingmethodconfig_detail` | Shipping method detail & tier matrix breakdown |
| `cart-checkout/shipping-methods/<int:pk>/edit/` | `shippingmethodconfig_edit` | `shippingmethodconfig_edit` | Edit shipping method rates and destination rules |
| `cart-checkout/shipping-methods/<int:pk>/delete/` | `shippingmethodconfig_delete` | `shippingmethodconfig_delete` | Delete shipping method (POST only, tenant admin) |
| `cart-checkout/shipping-methods/<int:pk>/toggle/` | `shippingmethodconfig_toggle` | `shippingmethodconfig_toggle` | Quick toggle shipping method active status (POST) |
| `cart-checkout/payment-methods/` | `paymentmethodconfig_list` | `paymentmethodconfig_list` | Payment methods & gateway configuration table |
| `cart-checkout/payment-methods/create/` | `paymentmethodconfig_create` | `paymentmethodconfig_create` | Connect payment gateway / payment method rule |
| `cart-checkout/payment-methods/<int:pk>/` | `paymentmethodconfig_detail` | `paymentmethodconfig_detail` | Payment method detail & fee / threshold settings |
| `cart-checkout/payment-methods/<int:pk>/edit/` | `paymentmethodconfig_edit` | `paymentmethodconfig_edit` | Edit payment provider, fee type, or currency settings |
| `cart-checkout/payment-methods/<int:pk>/delete/` | `paymentmethodconfig_delete` | `paymentmethodconfig_delete` | Delete payment method (POST only, tenant admin) |
| `cart-checkout/payment-methods/<int:pk>/toggle/` | `paymentmethodconfig_toggle` | `paymentmethodconfig_toggle` | Quick toggle payment gateway active status (POST) |

### 9.5 Order Management System Routes
| URL Pattern | View Function | URL Name | Description |
|---|---|---|---|
| `orders/` | `ecommerceorder_list` | `ecommerceorder_list` | Omnichannel orders list with status, payment, fulfillment, and fraud filters |
| `orders/create/` | `ecommerceorder_create` | `ecommerceorder_create` | Create new customer order with line items |
| `orders/<int:pk>/` | `ecommerceorder_detail` | `ecommerceorder_detail` | Order detail with lines, fulfillments, return authorizations, and financial summary |
| `orders/<int:pk>/edit/` | `ecommerceorder_edit` | `ecommerceorder_edit` | Edit order details, shipping address, and notes |
| `orders/<int:pk>/delete/` | `ecommerceorder_delete` | `ecommerceorder_delete` | Delete order (POST only, tenant admin) |
| `orders/<int:pk>/cancel/` | `ecommerceorder_cancel` | `ecommerceorder_cancel` | Cancel order & release allocated inventory (POST) |
| `routing-rules/` | `orderroutingrule_list` | `orderroutingrule_list` | Order fulfillment routing rules with strategy filter |
| `routing-rules/create/` | `orderroutingrule_create` | `orderroutingrule_create` | Configure new fulfillment routing rule |
| `routing-rules/<int:pk>/` | `orderroutingrule_detail` | `orderroutingrule_detail` | Routing rule detail view with strategy parameters |
| `routing-rules/<int:pk>/edit/` | `orderroutingrule_edit` | `orderroutingrule_edit` | Edit routing rule priority, strategy, and nodes |
| `routing-rules/<int:pk>/delete/` | `orderroutingrule_delete` | `orderroutingrule_delete` | Delete routing rule (POST only, tenant admin) |
| `fulfillments/` | `orderfulfillment_list` | `orderfulfillment_list` | Order fulfillment packages with carrier and status filters |
| `fulfillments/create/` | `orderfulfillment_create` | `orderfulfillment_create` | Create fulfillment package for order |
| `fulfillments/<int:pk>/` | `orderfulfillment_detail` | `orderfulfillment_detail` | Fulfillment detail with tracking timeline and label links |
| `fulfillments/<int:pk>/edit/` | `orderfulfillment_edit` | `orderfulfillment_edit` | Edit fulfillment package tracking and delivery info |
| `fulfillments/<int:pk>/delete/` | `orderfulfillment_delete` | `orderfulfillment_delete` | Delete fulfillment package (POST only, tenant admin) |
| `fulfillments/<int:pk>/ship/` | `orderfulfillment_ship` | `orderfulfillment_ship` | Mark fulfillment package as shipped with carrier (POST) |
| `returns/` | `returnmerchandiseauthorization_list` | `returnmerchandiseauthorization_list` | Return merchandise authorizations (RMA) with status & type filters |
| `returns/create/` | `returnmerchandiseauthorization_create` | `returnmerchandiseauthorization_create` | Initiate customer return authorization |
| `returns/<int:pk>/` | `returnmerchandiseauthorization_detail` | `returnmerchandiseauthorization_detail` | RMA detail with inspection findings and settlement status |
| `returns/<int:pk>/edit/` | `returnmerchandiseauthorization_edit` | `returnmerchandiseauthorization_edit` | Edit return authorization parameters |
| `returns/<int:pk>/delete/` | `returnmerchandiseauthorization_delete` | `returnmerchandiseauthorization_delete` | Delete return authorization (POST only, tenant admin) |
| `returns/<int:pk>/complete/` | `returnmerchandiseauthorization_complete` | `returnmerchandiseauthorization_complete` | Finalize RMA refund settlement and restock (POST) |

### 9.6 Customer Account & Profile Routes
| URL Pattern | View Function | URL Name | Description |
|---|---|---|---|
| `customer-profiles/` | `customeraccountprofile_list` | `customeraccountprofile_list` | Customer account profiles table with tier, status, auth mode, and search filters |
| `customer-profiles/create/` | `customeraccountprofile_create` | `customeraccountprofile_create` | Create new customer account profile |
| `customer-profiles/<int:pk>/` | `customeraccountprofile_detail` | `customeraccountprofile_detail` | Profile detail with recent orders, address preferences, wishlists, and privacy requests |
| `customer-profiles/<int:pk>/edit/` | `customeraccountprofile_edit` | `customeraccountprofile_edit` | Edit customer account profile information |
| `customer-profiles/<int:pk>/delete/` | `customeraccountprofile_delete` | `customeraccountprofile_delete` | Delete customer account profile (POST only, tenant admin) |
| `address-preferences/` | `customeraddresspreference_list` | `customeraddresspreference_list` | Address preferences table with delivery window filter |
| `address-preferences/create/` | `customeraddresspreference_create` | `customeraddresspreference_create` | Create customer address preference linked to core.Address |
| `address-preferences/<int:pk>/` | `customeraddresspreference_detail` | `customeraddresspreference_detail` | Address preference detail with instructions and delivery window |
| `address-preferences/<int:pk>/edit/` | `customeraddresspreference_edit` | `customeraddresspreference_edit` | Edit address preference attributes |
| `address-preferences/<int:pk>/delete/` | `customeraddresspreference_delete` | `customeraddresspreference_delete` | Delete address preference (POST only, tenant admin) |
| `wishlists/` | `customerwishlist_list` | `customerwishlist_list` | Customer wishlists table with visibility filter |
| `wishlists/create/` | `customerwishlist_create` | `customerwishlist_create` | Create new customer wishlist |
| `wishlists/<int:pk>/` | `customerwishlist_detail` | `customerwishlist_detail` | Wishlist detail with items table, priority indicators, and item quick-add form |
| `wishlists/<int:pk>/edit/` | `customerwishlist_edit` | `customerwishlist_edit` | Edit wishlist name, visibility, and notes |
| `wishlists/<int:pk>/delete/` | `customerwishlist_delete` | `customerwishlist_delete` | Delete wishlist (POST only, tenant admin) |
| `wishlists/<int:pk>/items/add/` | `customerwishlist_item_add` | `customerwishlist_item_add` | Add product/variant item to wishlist (POST, tenant admin) |
| `wishlists/items/<int:item_pk>/delete/` | `customerwishlist_item_delete` | `customerwishlist_item_delete` | Remove item from wishlist (POST, tenant admin) |
| `privacy-requests/` | `customerprivacyrequest_list` | `customerprivacyrequest_list` | Statutory privacy requests table with type and status filters |
| `privacy-requests/create/` | `customerprivacyrequest_create` | `customerprivacyrequest_create` | Log incoming GDPR/CCPA privacy request |
| `privacy-requests/<int:pk>/` | `customerprivacyrequest_detail` | `customerprivacyrequest_detail` | Privacy request detail with timeline, payload viewer, and action buttons |
| `privacy-requests/<int:pk>/edit/` | `customerprivacyrequest_edit` | `customerprivacyrequest_edit` | Edit privacy request metadata |
| `privacy-requests/<int:pk>/delete/` | `customerprivacyrequest_delete` | `customerprivacyrequest_delete` | Delete privacy request (POST only, tenant admin) |
| `privacy-requests/<int:pk>/generate-export/` | `customerprivacyrequest_generate_export` | `customerprivacyrequest_generate_export` | Generate comprehensive JSON data portability export (POST, tenant admin) |
| `privacy-requests/<int:pk>/anonymize/` | `customerprivacyrequest_anonymize` | `customerprivacyrequest_anonymize` | Execute right-to-erasure GDPR anonymization workflow (POST, tenant admin) |

---

## 4. Templates & Design System

Templates are stored under `templates/ecommerce/`:
- `productcatalog/` — Catalog overview, bulk import, storecategory, catalogproduct, productvariant, productrelationship templates.
- `inventorystock/`
  - `overview.html` — Operations console: ATP KPIs, low stock alerts, active fulfillment centers, connected channel syncs, and backorder queue.
  - `fulfillmentcenter/` — `list.html`, `detail.html`, `form.html`.
  - `inventoryallocation/` — `list.html` (with ATP highlights), `detail.html` (with ATP equation breakdown), `form.html`, `adjust.html` (cycle count / damage write-off workflow).
  - `backorderpolicy/` — `list.html`, `detail.html`, `form.html`.
  - `channelinventorysync/` — `list.html`, `detail.html`, `form.html`.
- `pricingpromotion/`
  - `dynamicpricerule/` — `list.html`, `detail.html`, `form.html`.
  - `couponpromotion/` — `list.html`, `detail.html`, `form.html`.
  - `flashsale/` — `list.html` (with active live badges), `detail.html` (with inventory sell-through progress bar), `form.html`.
  - `competitorpricemonitor/` — `list.html` (with margin risk warnings and suggested repricing), `detail.html` (with margin floor breakdown and instant sync button), `form.html`.
- `cartcheckout/`
  - `cart/` — `list.html` (with cart status badges and items count), `detail.html` (with line items table, financial breakdown, recovery URL trigger), `form.html`.
  - `checkoutsession/` — `list.html` (with funnel step indicators, flow types, payment statuses), `detail.html` (with step progress stepper, shipping & billing address panels, tax breakdown, advance step button), `form.html`.
  - `shippingmethod/` — `list.html` (with carrier logos/badges, rate calculation badges, active toggle), `detail.html` (with delivery estimation windows, threshold info), `form.html`.
  - `paymentmethod/` — `list.html` (with payment provider badges, environment pills, active toggle), `detail.html` (with fee structures, currency support lists, instructions), `form.html`.
- `ordermanagement/`
  - `ecommerceorder/` — `list.html` (with order status, payment, fulfillment, and fraud badges), `detail.html` (with order overview, customer card, items table, fulfillments timeline, returns panel, cancellation modal), `form.html`.
  - `orderroutingrule/` — `list.html` (with routing strategy badges and priority pills), `detail.html` (with destination scope and preferred center), `form.html`.
  - `orderfulfillment/` — `list.html` (with carrier badges and tracking links), `detail.html` (with tracking progress, dispatch metadata, and carrier ship action), `form.html`.
  - `returnmerchandiseauthorization/` — `list.html` (with return type badges and refund statuses), `detail.html` (with inspection notes, fee deduction, restocking center, and complete settlement action), `form.html`.
- `customerprofile/`
  - `customeraccountprofile/` — `list.html` (with tier, status, and auth mode badges), `detail.html` (with customer header, loyalty stats, address preferences, wishlists, and privacy requests), `form.html`.
  - `customeraddresspreference/` — `list.html` (with default shipping/billing badges and delivery window pills), `detail.html` (with physical address details and delivery instructions), `form.html`.
  - `customerwishlist/` — `list.html` (with visibility badges and items count), `detail.html` (with items table, priority badges, and quick-add form), `form.html`.
  - `customerprivacyrequest/` — `list.html` (with request type and workflow status badges), `detail.html` (with request timeline, data export action, anonymization modal, and payload viewer), `form.html`.

**UI & Badge Rules:**
- Only use color-named badge classes from `static/css/theme.css`: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
- Stat icon classes: `stat-icon blue`, `stat-icon green`, `stat-icon orange`, `stat-icon purple`, `stat-icon slate`.
- Never use semantic `-success`, `-danger`, or `-warning` classes (which render unstyled).

---

## 5. Seeder & Demo Data

Run the idempotent demo seeder:
```powershell
venv\Scripts\python.exe manage.py seed_ecommerce
```

The command provisions:
- 5 Hierarchical Categories: Electronics, Computing, Laptops, Accessories, Audio.
- 5 Catalog Products: Pro Ultra Laptop, Mechanical Keyboard, Wireless Mouse, Noise-Cancelling Headphones, Thunderbolt Dock.
- 11 Product Variants across multiple SKUs, sizes, colors, and option configurations with pricing and compare-at discounts.
- 6 Merchandising Relationships: Cross-sells, Up-sells, Accessories, and Frequently Bought Together bundles.
- 3 Fulfillment Centers: Main Distribution Hub (`DC-MAIN-01`), West Coast 3PL Partner (`3PL-WEST-02`), Downtown Flagship Store (`RET-FLAG-01`).
- 10 Inventory Allocations with on-hand, allocated, safety stock, and bin locations.
- 3 Backorder & Pre-Order Policies with waitlist tracking and customer storefront messages.
- 4 Multi-Channel Sync Feeds covering Shopify, Amazon Prime, Walmart Marketplace, and In-Store POS with buffer percentages.
- 4 Dynamic Pricing Rules: Storewide 10% Welcome, VIP 15% Audio, Wholesale Volume Tier (Min 5 units, 20% off), Laptop Flash Deal override.
- 4 Coupon Codes: `WELCOME10` (10% off), `SAVE50` ($50 off $200 min spend), `VIPFREESHIP` (Free shipping), `BLACKFRIDAY` (25% off max $100 cap).
- 3 Flash Sales: Midnight Audio Lightning Deal, Weekend Computing Blitz, Flash Clearance.
- 4 Competitor Price Monitors: Amazon US, Walmart, Best Buy, and Newegg with beat-by-fixed, beat-by-percent, and margin floor protection.
- 4 Shopping Carts: Active authenticated cart, Abandoned guest cart with recovery token, Multi-item cart in checkout, and Converted historical cart.
- 6 Cart Items with automatic total price calculation and variant pricing inheritance.
- 4 Checkout Sessions: In-progress contact step session, Shipping method selection session, Ready-for-payment session, and Completed session with order reference.
- 4 Shipping Methods: Standard Ground (Flat Rate), Express Air (Weight Tiered), Free Shipping over $100, and Store Pickup.
- 4 Payment Methods: Stripe Credit Card, PayPal Express Wallet, Klarna BNPL, and Cash on Delivery with surcharge and order limit rules.
- 4 eCommerce Orders: Validated priority order, In-fulfillment partially shipped order, Delivered & completed order, and Cancelled customer order.
- 8 eCommerce Order Lines with line discounts, quantities, and line statuses.
- 3 Order Routing Rules: Domestic Express Routing (closest location), West Coast Drop-Ship Routing (drop-ship preferred), High Stock Allocation (highest inventory).
- 4 Order Fulfillments: Carrier-dispatched FedEx Ground package with live tracking, Shipped DHL Express package, Allocated draft package, and Delivered package.
- 3 Return Merchandise Authorizations (RMA): Damaged item refund with restock quarantine, Wrong item replacement return, and Size/fit customer return with restocking fee.
- 4 Customer Account Profiles across bronze, silver, gold, and platinum tiers with marketing consent and preferences.
- 5 Customer Address Preferences with default shipping, default billing, delivery instructions, and window selections.
- 4 Customer Wishlists with private, shared, and public visibilities.
- 6 Customer Wishlist Items with priority indicators and quantity targets.
- 4 Customer Privacy Requests covering access/export, rectification, erasure/anonymization, and CCPA opt-out.
- All demo data is scoped to tenant `acme`.

---

## 6. Conventions & Gotchas

1. **Multi-Tenancy & IDOR**:
   - Every view must filter queries using `tenant=request.tenant`.
   - Single object lookups must use `ecommerce_object(Model, pk, request.tenant)` or `get_object_or_404(Model, pk=pk, tenant=request.tenant)`.
   - ModelForms must use `TenantUniqueMixin` and filter all FK querysets in `__init__` to `self.tenant`.
   - Form `clean()` methods must invoke `reject_foreign(self, cleaned_data, [...])`.
2. **Context Variable Contract**:
   - List views pass `page_obj`, `is_paginated`, filter values, and choice constants.
   - Detail views pass the singular entity name along with preloaded related collections.
3. **Available-to-Promise (ATP)**:
   - Digital storefronts must show `ATP = max(0, quantity_on_hand - quantity_allocated - safety_stock_buffer)` rather than raw on-hand stock.
4. **Audit Logging Signature**:
   - `write_audit_log(request.user, obj, action, changes_dict)` — always pass `user` first, `obj` second, short action verb third, and changes dictionary fourth.
5. **Integer Query Param Guarding (Lesson L11)**:
   - Always validate foreign key filter parameters before passing to ORM: `if param and param.isdigit():`.
6. **Open Redirect Validation**:
   - Always validate `next` parameters with `url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()})`.
7. **Pricing Engine Precedence & Margin Protection**:
   - Flash sales take highest priority during active windows.
   - Competitive repricing suggestions must never breach the `margin_floor_price` calculated from variant unit cost (`cost_price * (1 + min_margin_pct/100)`). If competitor undercuts below margin floor, monitor flags `is_margin_risk` and clamps suggested price to floor.
8. **Checkout Billing Address Inheritance**:
   - When `billing_same_as_shipping` is True, `CheckoutSession.save()` automatically clones shipping address fields into the corresponding billing fields. In forms, `billing_country` is made non-required since it is populated server-side.
9. **Single Default Address & Wishlist Constraints**:
   - `CustomerAddressPreference` and `CustomerWishlist` models enforce single-default rules on save: when `is_default_shipping`, `is_default_billing`, or `is_default` is set to True, all sibling records for that customer are automatically unset.
10. **Statutory Privacy & Anonymization Guards**:
    - Right-to-erasure workflows de-identify personal customer profiles, revoke marketing consents, deactivate associated authentication users (`user.is_active = False`), and privatize public wishlists in atomic transactions.

---

## 7. Sidebar Navigation

Mounted in `apps/core/navigation.py`:
```python
LIVE_LINKS["9.1"] = ("ecommerce:catalog_overview", "9.1 Product Catalog", "ecommerce")
LIVE_LINKS["9.2"] = ("ecommerce:inventory_operations", "9.2 Inventory & Stock", "ecommerce")
LIVE_LINKS["9.3"] = {
    "Dynamic Pricing Rules": "ecommerce:dynamicpricerule_list",
    "Discount & Coupon Management": "ecommerce:couponpromotion_list",
    "Flash Sales & Limited-Time Offers": "ecommerce:flashsale_list",
    "Loyalty & Rewards Pricing": "ecommerce:couponpromotion_list",
    "Price Matching & Competitive Monitoring": "ecommerce:competitorpricemonitor_list",
}
LIVE_LINKS["9.4"] = {
    "Shopping Carts & Guest Sessions": "ecommerce:cart_list",
    "Abandoned Cart Recovery": "ecommerce:cart_list",
    "One-Page & Multi-Step Checkout": "ecommerce:checkoutsession_list",
    "Shipping Methods & Calculation": "ecommerce:shippingmethodconfig_list",
    "Payment Gateway Configuration": "ecommerce:paymentmethodconfig_list",
}
LIVE_LINKS["9.5"] = {
    "Order Lifecycle & Validation": "ecommerce:ecommerceorder_list",
    "Order Routing & Distributed Sourcing": "ecommerce:orderroutingrule_list",
    "Carrier Dispatch & Shipment Tracking": "ecommerce:orderfulfillment_list",
    "Returns & RMA Management": "ecommerce:returnmerchandiseauthorization_list",
    "Omnichannel Order Orchestration": "ecommerce:ecommerceorder_list",
}
LIVE_LINKS["9.6"] = {
    "Registration & Authentication": "ecommerce:customeraccountprofile_list",
    "Account Dashboard & Order History": "ecommerce:customeraccountprofile_list",
    "Address Book & Preferences": "ecommerce:customeraddresspreference_list",
    "Communication Preferences": "ecommerce:customeraccountprofile_list",
    "Account Security & Privacy": "ecommerce:customerprivacyrequest_list",
    "Customer Profiles": "ecommerce:customeraccountprofile_list",
    "Address Preferences": "ecommerce:customeraddresspreference_list",
    "Wishlists": "ecommerce:customerwishlist_list",
    "Privacy Requests": "ecommerce:customerprivacyrequest_list",
}
```
Appears under the eCommerce section of the primary navigation bar.
