# Research — Sub-module 9.3: Pricing & Promotion Engine (Module 9 — eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.3 Pricing & Promotion Engine
- **Module:** 9 eCommerce Management System
- **Target app:** `apps/ecommerce` (extending the app created in 9.1 and extended in 9.2)
- **Research date:** 2026-10-29
- **Phase:** 1 Research only
- **Output boundary:** `.claude/tasks/research-ecommerce-9.3.md` only

---

## 1. Executive Summary & Domain Architecture

Sub-module 9.3 represents the **Pricing, Discount, Promotional Campaign, Flash Sale, and Competitive Intelligence engine** of the NavERP eCommerce platform.

In modern enterprise commerce (exemplified by commercetools, Talon.One, Shopify Plus, BigCommerce, Adobe Commerce, and Salesforce B2C Commerce), pricing is not a single static decimal field on a catalog product; it is a **dynamic, multi-dimensional, context-aware rule engine**. A customer sees prices and promotions modulated by:
1. **Who they are:** Customer segmentation, loyalty reward tiers, B2B wholesale contract groups.
2. **Where they are:** Geo-pricing, regional currency rates, country-specific market tiers.
3. **When they buy:** Time-limited promotions, schedule windows, flash sales with live countdowns.
4. **How much they buy:** Tiered volume break pricing (e.g. 1-9 units @ \$100, 10-49 @ \$85, 50+ @ \$70).
5. **What vouchers/coupons they hold:** Single-use or multi-use coupon codes with validation rules, usage limits, minimum cart spend, and stackability policies.
6. **Market competition:** Competitive intelligence scraped from third-party storefronts, automated price-matching algorithms, and margin protection floors.

### Architectural Boundary Rulings (L28, L29, L36, L37):
1. **Catalog Base Anchor**: Reuses `ecommerce.CatalogProduct` (`EPRD-`) and `ecommerce.ProductVariant` (`PVR-`) as the target catalog entities. Base selling prices (`price`), strike-through list prices (`compare_at_price`), and unit cost prices (`cost_price`) live on `ProductVariant`. 9.3 applies dynamic rules and promotional discounts on top of these base prices.
2. **Customer / Segment Anchor**: Reuses `core.Party` and `core.PartyRole` (`PartyRole.ROLE_CUSTOMER`) for customer identification and tier tagging.
3. **Cart & Checkout Separation (9.4)**: Sub-module 9.3 defines the **pricing rules, discount codes, flash sales, and competitor monitoring records**. The actual runtime cart evaluation, cart item recalculation, shipping fee computation, and checkout line-item coupon application belong to Sub-module 9.4 (Shopping Cart & Checkout).
4. **Physical Stock & Accounting Ledger Isolation**: Sub-module 9.3 never writes directly to `accounting.JournalEntry` or `scm.StockMove`. Revenue recognition occurs upon order placement and invoice generation in 9.5 (OMS) / Module 2 (Accounting). Flash sale inventory caps represent digital promotion limits, leaving physical inventory reservation to 9.2 (`InventoryAllocation`).

---

## 2. Repo State Checked First

### 2.1 Navigation & App Tree State
- **`apps/core/navigation.py`:** 
  - `"9.1"` is live: Product Information Management, Category Hierarchy, Product Variants, Bulk Import/Export, Product Relationships.
  - `"9.2"` is live: Real-Time Stock Tracking, Warehouse & Fulfillment Center Management, Stock Transfers & Adjustments, Backorder & Pre-Order Management, Multi-Channel Inventory Sync.
  - Sub-module `"9.3"` has no `LIVE_LINKS` entry yet.
- **`apps/ecommerce/` structure:**
  - `models/ProductCatalog/`, `models/InventoryStock/`
  - `forms/ProductCatalog/`, `forms/InventoryStock/`
  - `views/ProductCatalog/`, `views/InventoryStock/`
  - `urls/ProductCatalog/`, `urls/InventoryStock/`
  - `templates/ecommerce/productcatalog/`, `templates/ecommerce/inventorystock/`
  - Sub-module 9.3 will add package subdirectories: `PricingPromotion/` across `models/`, `forms/`, `views/`, `urls/`, and `templates/ecommerce/pricingpromotion/`.

### 2.2 As-Built Core Spine Entities (Grep Verified)
| Entity | Location | Status | 9.3 Usage |
|---|---|---|---|
| `core.Tenant` | `apps/core/models/Tenant.py:17` | **Present** | Strict multi-tenant isolation |
| `core.Party` | `apps/core/models/Party.py:12` | **Present** | Customer account identity |
| `ecommerce.CatalogProduct` | `apps/ecommerce/models/ProductCatalog/CatalogProducts.py:8` | **Present** | Target product for promotion rules (`EPRD-`) |
| `ecommerce.ProductVariant` | `apps/ecommerce/models/ProductCatalog/ProductVariants.py:10` | **Present** | Specific purchasable SKU option (`PVR-`) with `price`, `compare_at_price`, and `cost_price` |
| `ecommerce.StoreCategory` | `apps/ecommerce/models/ProductCatalog/StoreCategories.py:9` | **Present** | Category-wide discount rules (`ECAT-`) |
| `crm.PriceBook` | `apps/crm/models/SalesForceAutomation/PriceBooks.py:5` | **Present** | Reference for B2B CRM price list patterns |

### 2.3 Prefix Collision Verification
The following unique auto-number prefixes have been verified against the entire repository:
- `EDPR` — `DynamicPriceRule` (Unused, clean)
- `ECPN` — `CouponPromotion` (Unused, clean)
- `EFLS` — `FlashSale` (Unused, clean)
- `ECPM` — `CompetitorPriceMonitor` (Unused, clean)

---

## 3. Commercial Market Leaders Surveyed

### 1. Talon.One (Enterprise Promotion & Loyalty Cloud)
- **Architecture**: Headless API-first rule engine with rule builder ("Effects", "Conditions").
- **Dynamic Pricing**: Contextual price rules evaluating customer loyalty tier, cart spend, location geofence, and temporal validity.
- **Coupons**: Mass unique code generation, referral codes, single-use validations, and budget limit guards.
- **Source**: [talon.one / product / promotions](https://www.talon.one/)

### 2. Voucherify (API-First Promotional Platform)
- **Architecture**: Composable coupon, gift card, referral, discount, and loyalty management platform.
- **Discount Rules**: Percentage off, fixed amount, unit discounts, and free shipping triggers.
- **Redemption Limits**: Per-customer redemption caps, global budget constraints, and time-window validity.
- **Stacking Logic**: Clear precedence hierarchies (exclusive, stackable, priority-ranked).
- **Source**: [voucherify.io / features / promotions](https://www.voucherify.io/)

### 3. commercetools (MACH-Certified Composable Commerce)
- **Architecture**: Microservices-based Product Discounts and Cart Discounts with predicate query engines.
- **Product Discounts**: Applied directly to catalog listings before cart addition (e.g. Category X is 15% off for Gold members).
- **Tiered Pricing**: Volume price breaks stored on variant prices (`price_tiers` with minimum quantity thresholds).
- **Source**: [docs.commercetools.com / api / projects / productDiscounts](https://docs.commercetools.com/)

### 4. Shopify Plus (Discounts API & Shopify Functions)
- **Architecture**: Automatic discounts, coupon codes, and serverless discount functions.
- **Flash Sales**: Scheduled launches with countdown assets, queueing integration, and inventory reservation.
- **Combinations**: Explicit discount combination rules (Order discounts can combine with Product discounts, but not other Order discounts).
- **Customer Segmentation**: Automatic discount triggers based on customer tags and dynamic customer segments.
- **Source**: [help.shopify.com / manual / discounts](https://help.shopify.com/)

### 5. BigCommerce Enterprise (Price Lists & Promotions Engine)
- **Architecture**: Separation between permanent/scheduled Price Lists (customer group pricing, currency pricing) and Promotions (cart/checkout dynamic discounts).
- **Geo & Currency Pricing**: Assigning distinct price lists to specific international channels or geographic storefronts.
- **Tier Pricing**: Quantity breaks with discount type (fixed amount off, percentage off, or exact price override).
- **Source**: [support.bigcommerce.com / s / article / Price-Lists](https://support.bigcommerce.com/)

### 6. Adobe Commerce / Magento Enterprise
- **Architecture**: Dual rule system: Catalog Price Rules (applied at browse time) vs. Cart Price Rules (applied at checkout).
- **Customer Groups**: General, Wholesale, Retail, VIP groups with custom discount multipliers.
- **Flash Sales**: Scheduled updates with automatic activation and deactivation timestamps.
- **Source**: [experienceleague.adobe.com / docs / commerce-admin / marketing / promotions](https://experienceleague.adobe.com/)

### 7. Salesforce B2C Commerce (Demandware)
- **Architecture**: Campaigns, Qualifiers, Conditions, and Promotions framework.
- **Qualifiers**: Customer groups, coupons, source tracking codes, and schedule windows.
- **Promotion Types**: Product promotions, Order promotions, and Shipping promotions.
- **Source**: [developer.salesforce.com / docs / commerce / b2c-commerce](https://developer.salesforce.com/)

### 8. Prisync & Competera (Competitive Price Intelligence & Dynamic Repricing)
- **Architecture**: Automated competitive price tracking, competitor URL scraping, price matching rules, and margin safety floors.
- **Rule Engine**: "Match lowest competitor price", "Beat competitor by $1 / 5%", while enforcing `min_price = cost_price * (1 + min_margin_pct)`.
- **Alerting**: Real-time notifications when a competitor changes price or runs out of stock.
- **Source**: [prisync.com / competitor-price-monitoring](https://prisync.com/)

---

## 4. Deduplicated Feature Catalog (Mapped to 9.3 Bullets)

### Bullet 1: Dynamic Pricing Rules
- **Rule Type & Adjustments**: Percentage discount, fixed discount amount, or direct price override.
- **Targeting Hierarchy**: Apply to specific ProductVariant, CatalogProduct, StoreCategory, or storewide catalog.
- **Customer Segment & Loyalty Tier**: Restrict rules to customer segments (`retail`, `wholesale`, `vip`, `gold_member`, `b2b`).
- **Volume Tiers (Quantity Breaks)**: Minimum quantity trigger (e.g. Buy 5+, get 10% off; Buy 20+, get 20% off).
- **Time-Based Scheduling**: Start datetime and end datetime with active status flag.
- **Geo & Regional Pricing**: Target specific country codes, currency codes, or sales channels.
- **Priority & Precedence**: Priority integer (1–100) and evaluation order handling.
- *Priority*: `table-stakes`. *Model*: `DynamicPriceRule` (`EDPR-`).

### Bullet 2: Discount & Coupon Management
- **Coupon Code Generation**: Alphanumeric uppercase coupon code (e.g. `SUMMER20`, `WELCOME10`).
- **Discount Calculations**: Percentage discount, fixed cart discount, fixed item discount, or free shipping voucher.
- **Minimum Spend & Quantity**: Minimum order subtotal required to unlock discount.
- **Usage Limits**: Maximum global redemptions (`usage_limit_total`) and maximum redemptions per customer (`usage_limit_per_customer`).
- **Usage Tracking**: Current redemptions counter (`used_count`) and lifetime discount amount redeemed.
- **Stackability Policies**: Stackable flag (`is_stackable`) allowing or forbidding combination with other promotions or dynamic pricing rules.
- **Customer Eligibility**: Specific customer link (single-customer voucher) or open to all.
- *Priority*: `table-stakes`. *Model*: `CouponPromotion` (`ECPN-`).

### Bullet 3: Flash Sales & Limited-Time Offers
- **High-Impact Event Schedule**: Dedicated start and end timestamps with second-level precision for live countdown timers.
- **Discount Scheme**: Flash sale discount percentage or dedicated promotional price override.
- **Inventory-Gated Quota**: Maximum promotional units allocated to the flash sale (`inventory_cap`), with live tracking of units claimed (`units_sold`).
- **Purchase Rationing**: Per-customer purchase limit (e.g. Max 2 units per customer) to prevent scalping and hoarders.
- **Storefront Display Assets**: Flash sale headline, promotional badge label ("FLASH SALE", "LIGHTNING DEAL"), and banner highlight color.
- **Lifecycle Status**: Auto-transition between `draft`, `scheduled`, `active`, `paused`, and `ended`.
- *Priority*: `table-stakes`. *Model*: `FlashSale` (`EFLS-`).

### Bullet 4: Loyalty & Rewards Pricing
- **Tier-Based Discount Unlocks**: Embedded directly in `DynamicPriceRule` and `CouponPromotion` via `loyalty_tier` requirement (`bronze`, `silver`, `gold`, `platinum`, `vip`).
- **Points-to-Currency Value**: Configurable point redemption valuation on promotional vouchers.
- **Member-Exclusive Pricing**: Flags on price rules ensuring unauthenticated visitors see standard retail MSRP while signed-in loyalty members see preferential pricing.
- *Priority*: `table-stakes`. *Implementation*: First-class fields across `DynamicPriceRule` and `CouponPromotion`.

### Bullet 5: Price Matching & Competitive Monitoring
- **Competitor Tracking Node**: Competitor name (e.g. Amazon, BestBuy, Walmart, Competitor X), competitor store URL, and product listing URL.
- **Monitored Product**: Direct FK link to `ProductVariant` / `CatalogProduct`.
- **Competitor Price Scrape Record**: Latest scraped price, currency, stock availability status, and last checked timestamp.
- **Automated Price Match Strategy**: Strategy choice: `manual_review`, `auto_match_exact`, `beat_by_amount`, `beat_by_percent`.
- **Margin Protection Floor**: Critical safety guard; rule will never lower price below `(ProductVariant.cost_price * (1 + min_margin_pct))` or a configured `floor_price`.
- **Match Status**: `tracking`, `matched`, `suppressed_margin_risk`, `out_of_stock`.
- *Priority*: `differentiator`. *Model*: `CompetitorPriceMonitor` (`ECPM-`).

---

## 5. Recommended Build Scope (4 Models for 9.3)

To ensure high architectural rigor, zero clutter, and complete coverage of all 5 NavERP bullets, Sub-module 9.3 will deliver **exactly 4 models** under `apps/ecommerce/models/PricingPromotion/`:

### Model 1: `DynamicPriceRule`
- **File**: `apps/ecommerce/models/PricingPromotion/DynamicPriceRules.py`
- **Prefix**: `NUMBER_PREFIX = "EDPR"`
- **Key Fields**:
  - `number`: Auto-generated identifier (`EDPR-00001`).
  - `name`: Human-readable rule title (e.g. "Wholesale Tier 1 15% Off", "Summer Footwear Clearance").
  - `rule_type`: Choice (`percentage_discount`, `fixed_discount`, `fixed_price_override`).
  - `adjustment_value`: Decimal amount (e.g. 15.0000 for 15% or 20.0000 for $20 off).
  - `scope`: Choice (`storewide`, `category`, `product`, `variant`).
  - `category`: FK `ecommerce.StoreCategory` (nullable).
  - `product`: FK `ecommerce.CatalogProduct` (nullable).
  - `variant`: FK `ecommerce.ProductVariant` (nullable).
  - `customer_segment`: Choice (`all`, `retail`, `wholesale`, `vip`, `b2b`).
  - `loyalty_tier`: Choice (`none`, `bronze`, `silver`, `gold`, `platinum`).
  - `min_quantity`: PositiveIntegerField default 1 (for volume tiered pricing).
  - `country_code`: CharField(max_length=2, blank=True) for geo-pricing (ISO 3166-1 alpha-2).
  - `currency_code`: CharField(max_length=3, default="USD").
  - `valid_from`: DateTimeField.
  - `valid_to`: DateTimeField (nullable).
  - `priority`: PositiveIntegerField default 10 (higher number wins).
  - `is_active`: BooleanField default True.
  - `description`: TextField blank True.

### Model 2: `CouponPromotion`
- **File**: `apps/ecommerce/models/PricingPromotion/CouponPromotions.py`
- **Prefix**: `NUMBER_PREFIX = "ECPN"`
- **Key Fields**:
  - `number`: Auto-generated identifier (`ECPN-00001`).
  - `code`: CharField unique per tenant (e.g. `WELCOME10`, `VIPGOLD2026`).
  - `name`: Promotional campaign title.
  - `discount_type`: Choice (`percentage`, `fixed_cart`, `fixed_item`, `free_shipping`).
  - `discount_value`: DecimalField (e.g. 10.0000 for 10% or 15.0000 for $15 off).
  - `min_spend`: DecimalField default 0.0000.
  - `max_discount_amount`: DecimalField nullable (discount cap for percentage vouchers).
  - `usage_limit_total`: PositiveIntegerField nullable (total global redemptions allowed).
  - `usage_limit_per_customer`: PositiveIntegerField default 1.
  - `used_count`: PositiveIntegerField default 0.
  - `is_stackable`: BooleanField default False.
  - `loyalty_tier_required`: Choice (`none`, `bronze`, `silver`, `gold`, `platinum`).
  - `customer`: FK `core.Party` nullable (for personalized single-customer coupons).
  - `valid_from`: DateTimeField.
  - `valid_to`: DateTimeField nullable.
  - `is_active`: BooleanField default True.

### Model 3: `FlashSale`
- **File**: `apps/ecommerce/models/PricingPromotion/FlashSales.py`
- **Prefix**: `NUMBER_PREFIX = "EFLS"`
- **Key Fields**:
  - `number`: Auto-generated identifier (`EFLS-00001`).
  - `title`: Flash sale headline (e.g. "Midnight Madness - 50% Off Outerwear").
  - `status`: Choice (`draft`, `scheduled`, `active`, `paused`, `ended`).
  - `product`: FK `ecommerce.CatalogProduct` nullable.
  - `variant`: FK `ecommerce.ProductVariant` nullable.
  - `category`: FK `ecommerce.StoreCategory` nullable.
  - `discount_percentage`: DecimalField(max_digits=5, decimal_places=2).
  - `flash_price`: DecimalField nullable (specific override price if not percentage).
  - `inventory_cap`: PositiveIntegerField (promotional units allocated).
  - `units_sold`: PositiveIntegerField default 0.
  - `max_units_per_order`: PositiveIntegerField default 1 (anti-scalping purchase cap).
  - `start_time`: DateTimeField.
  - `end_time`: DateTimeField.
  - `badge_label`: CharField default "FLASH DEAL".
  - `banner_bg_color`: CharField default "#ef4444" (tailwind red-500).
  - `terms_and_conditions`: TextField blank True.

### Model 4: `CompetitorPriceMonitor`
- **File**: `apps/ecommerce/models/PricingPromotion/CompetitorPriceMonitors.py`
- **Prefix**: `NUMBER_PREFIX = "ECPM"`
- **Key Fields**:
  - `number`: Auto-generated identifier (`ECPM-00001`).
  - `competitor_name`: CharField (e.g. "Amazon", "Walmart", "BestBuy").
  - `product`: FK `ecommerce.CatalogProduct` nullable.
  - `variant`: FK `ecommerce.ProductVariant` on_delete=CASCADE (primary monitored SKU).
  - `competitor_url`: URLField.
  - `competitor_price`: DecimalField(max_digits=14, decimal_places=4).
  - `competitor_currency`: CharField(max_length=3, default="USD").
  - `is_in_stock`: BooleanField default True.
  - `last_scraped_at`: DateTimeField nullable.
  - `match_strategy`: Choice (`manual`, `match_exact`, `beat_by_fixed`, `beat_by_percent`).
  - `beat_by_value`: DecimalField default 0.0000.
  - `min_margin_pct`: DecimalField default 10.00 (margin protection floor, e.g. 10% above cost).
  - `floor_price`: DecimalField nullable (hard floor price below which price cannot drop).
  - `status`: Choice (`active`, `paused`, `margin_suppressed`, `out_of_stock`).
  - `notes`: TextField blank True.

---

## 6. Sibling Sub-Module Boundaries & Deferred Scope

### Belongs to Sibling Sub-Modules
- **Cart Discount Evaluation & Stacking Math** -> **Sub-module 9.4 (Shopping Cart & Checkout)**: Sub-module 9.3 stores and configures the rules and coupons; 9.4 calculates line item totals, tax, and order grand totals in the checkout pipeline.
- **Order Line Coupon Attribution** -> **Sub-module 9.5 (OMS)**: Capturing the applied promotion code on the placed `SalesOrderLine`.
- **Customer Loyalty Points Ledger** -> **Sub-module 9.6 / 19.4**: Full point accumulation and debit transactions. 9.3 consumes loyalty tiers for pricing unlocks.
- **Personalized AI Recommendation Prompts** -> **Sub-module 9.8 / Module 23 (AI)**.

### Deferred Integrations
- **Live Competitor Web Scraping Daemon**: Headless browser (Puppeteer/Playwright) worker daemons belong in background task queues (Celery/cron), while 9.3 provides the complete data model, manual override, simulation, and trigger endpoints.
- **SMS/Push Coupon Broadcasting**: Twilio / SendGrid blast messaging belongs in 9.10 (Marketing Campaigns).

---

## 7. URL & Route Map Specification

All routes registered under `apps/ecommerce/urls/PricingPromotion/`:
```
/ecommerce/pricing/rules/                       -> dynamicpricerule_list
/ecommerce/pricing/rules/create/                -> dynamicpricerule_create
/ecommerce/pricing/rules/<int:pk>/              -> dynamicpricerule_detail
/ecommerce/pricing/rules/<int:pk>/edit/         -> dynamicpricerule_edit
/ecommerce/pricing/rules/<int:pk>/delete/       -> dynamicpricerule_delete

/ecommerce/pricing/coupons/                     -> couponpromotion_list
/ecommerce/pricing/coupons/create/              -> couponpromotion_create
/ecommerce/pricing/coupons/<int:pk>/            -> couponpromotion_detail
/ecommerce/pricing/coupons/<int:pk>/edit/       -> couponpromotion_edit
/ecommerce/pricing/coupons/<int:pk>/delete/     -> couponpromotion_delete

/ecommerce/pricing/flash-sales/                 -> flashsale_list
/ecommerce/pricing/flash-sales/create/          -> flashsale_create
/ecommerce/pricing/flash-sales/<int:pk>/        -> flashsale_detail
/ecommerce/pricing/flash-sales/<int:pk>/edit/   -> flashsale_edit
/ecommerce/pricing/flash-sales/<int:pk>/delete/ -> flashsale_delete

/ecommerce/pricing/competitors/                 -> competitorpricemonitor_list
/ecommerce/pricing/competitors/create/          -> competitorpricemonitor_create
/ecommerce/pricing/competitors/<int:pk>/        -> competitorpricemonitor_detail
/ecommerce/pricing/competitors/<int:pk>/edit/   -> competitorpricemonitor_edit
/ecommerce/pricing/competitors/<int:pk>/delete/ -> competitorpricemonitor_delete
/ecommerce/pricing/competitors/<int:pk>/sync/   -> competitorpricemonitor_sync
```

---

## 8. Summary for `todo` Agent

Sub-module 9.3 delivers an enterprise-grade Pricing & Promotion Engine for eCommerce across **4 models**:
1. `DynamicPriceRule` (`EDPR-`): Volume break tiers, customer segments, geo-pricing, temporal schedules.
2. `CouponPromotion` (`ECPN-`): Voucher codes, usage limits, percentage/fixed cuts, stackable rules.
3. `FlashSale` (`EFLS-`): Countdown timers, inventory-gated caps, max units per order, visual styling.
4. `CompetitorPriceMonitor` (`ECPM-`): Competitor price tracking, match strategies, and margin protection floors.

All models are tenant-isolated via `TenantNumbered`, adhere to strict CRUD conventions, and integrate directly with catalog variants (`ProductVariant`), categories (`StoreCategory`), and customer roles (`core.Party`).
