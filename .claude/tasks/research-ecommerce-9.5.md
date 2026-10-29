# Research — Sub-module 9.5: Order Management System (OMS) (Module 9 — eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.5 Order Management System (OMS)
- **Module:** 9 eCommerce Management System
- **Target app:** `apps/ecommerce` (extending the app created in 9.1 and extended in 9.2 and 9.3)
- **Research date:** 2026-10-29
- **Phase:** 1 Research only
- **Output boundary:** `.claude/tasks/research-ecommerce-9.5.md` only

---

## 1. Executive Summary & Domain Architecture

Sub-module 9.5 represents the **Order Management System (OMS), Multi-Location Order Routing, Fulfillment Tracking, Post-Purchase Modification, and Reverse Logistics (RMA) engine** of the NavERP eCommerce platform.

In modern enterprise commerce (exemplified by Manhattan Active® Omni, Fluent Commerce, IBM Sterling Order Management, commercetools, Shopify Plus, Narvar, and Loop Returns), an OMS serves as the central nervous system bridging digital storefront sales with physical supply chains. It orchestrates orders from initial capture and fraud validation through intelligent routing, split shipments across multiple fulfillment centers, carrier tracking, and post-purchase customer modifications or return authorizations.

Key capabilities required by enterprise commerce leaders:
1. **Order Capture & Automated Validation:** Pre-order fraud risk scoring (0-100), address verification validation, inventory reservation checks, and payment authorization status verification.
2. **Intelligent Order Routing & Splitting:** Distributed Order Management (DOM) routing policies that determine the optimal fulfillment location (nearest fulfillment center, least package splits, available stock depth, or drop-ship vendor).
3. **Fulfillment Tracking & Real-Time Status:** Support for split order packages, multi-carrier shipment tracking integration (FedEx, UPS, DHL, USPS, local couriers), delivery date estimation, and customer transit notifications.
4. **Order Modifications & Cancellations:** Post-purchase modification workflows, partial line item cancellation before fulfillment, address corrections, and cancellation audit reasons.
5. **Reverse Logistics & Returns (RMA):** Return Merchandise Authorization lifecycle (requested, authorized, label generated, received, inspected, restocked), return type routing (refund, exchange, store credit), restocking disposition, and fee calculations.

### Architectural Boundary Rulings (L28, L29, L36, L37):
1. **Customers & Accounts**: **REUSE `core.Party` (Core Spine)**. Customers and buyers are `core.Party` instances with role `customer`. 9.5 attaches eCommerce orders, return requests, and customer contact data directly to `core.Party`. Declaring a duplicate customer or company table violates L36/L37.
2. **Catalog Products & Variants**: **REUSE `ecommerce.CatalogProduct` (`EPRD-`) and `ecommerce.ProductVariant` (`PVR-`)**. Line items snapshot SKU, product title, and unit prices from catalog variants while retaining immutable historical snapshots on the order line.
3. **Fulfillment Centers & Inventory**: **REUSE `ecommerce.FulfillmentCenter` (`EFC-`, 9.2)** as the destination and origin fulfillment nodes for order routing and RMA restocking. Physical inventory reservation integrates with `ecommerce.InventoryAllocation` (`EALC-`, 9.2).
4. **Discounts & Promotions**: **REUSE `ecommerce.CouponPromotion` (`ECPN-`, 9.3)** for tracking promotional coupon codes applied to orders.
5. **Multi-Currency & Financial Ledger**: **REUSE `accounting.Currency` (Accounting 2.2)** for multi-currency order valuation. Financial invoice posting and payment recording will reference `accounting.Invoice` (`INV-`) and `accounting.Payment` (`PMT-`) via string FKs without duplicating ledgers.

---

## 2. Repo State Checked First

### 2.1 Navigation & App Tree State
- **`apps/core/navigation.py`:** 
  - `"9.1"` is live: Product Information Management, Category Hierarchy, Product Variants, Bulk Import/Export, Product Relationships.
  - `"9.2"` is live: Real-Time Stock Tracking, Warehouse & Fulfillment Center Management, Stock Transfers & Adjustments, Backorder & Pre-Order Management, Multi-Channel Inventory Sync.
  - `"9.3"` is live: Dynamic Price Rules, Coupon & Promotional Codes, Flash Sales, Competitor Price Monitoring.
  - Sub-module `"9.5"` has no `LIVE_LINKS` entry yet.
- **`apps/ecommerce/` structure:**
  - `models/ProductCatalog/`, `models/InventoryStock/`, `models/PricingPromotion/`
  - `forms/ProductCatalog/`, `forms/InventoryStock/`, `forms/PricingPromotion/`
  - `views/ProductCatalog/`, `views/InventoryStock/`, `views/PricingPromotion/`
  - `urls/ProductCatalog/`, `urls/InventoryStock/`, `urls/PricingPromotion/`
  - `templates/ecommerce/productcatalog/`, `templates/ecommerce/inventorystock/`, `templates/ecommerce/pricingpromotion/`
  - Sub-module 9.5 will add package subdirectories: `OrderManagement/` across `models/`, `forms/`, `views/`, `urls/`, and `templates/ecommerce/ordermanagement/`.

### 2.2 As-Built Core Spine Entities (Grep Verified)
| Entity | Location | Status | 9.5 Usage |
|---|---|---|---|
| `core.Tenant` | `apps/core/models/Tenant.py:17` | **Present** | Strict multi-tenant isolation |
| `core.Party` | `apps/core/models/Party.py:12` | **Present** | Customer account identity (`customer` role) |
| `core.Address` | `apps/core/models/Address.py:5` | **Present** | Customer billing and shipping addresses |
| `accounting.Currency` | `apps/accounting/models/GeneralLedger/Currencies.py:14` | **Present** | ISO-4217 order currency |
| `ecommerce.CatalogProduct` | `apps/ecommerce/models/ProductCatalog/CatalogProducts.py:8` | **Present** | Product reference on order lines |
| `ecommerce.ProductVariant` | `apps/ecommerce/models/ProductCatalog/ProductVariants.py:10` | **Present** | Specific SKU variant on order lines |
| `ecommerce.FulfillmentCenter` | `apps/ecommerce/models/InventoryStock/FulfillmentCenters.py:9` | **Present** | Sourcing origin for routing and RMA restock destination |
| `ecommerce.CouponPromotion` | `apps/ecommerce/models/PricingPromotion/CouponPromotions.py:9` | **Present** | Applied coupon discount reference |

### 2.3 Prefix Collision Verification
The following unique auto-number prefixes have been verified across all models in the repository:
- `EORD` — `EcommerceOrder` (**Verified FREE**)
- `EOLN` — `EcommerceOrderLine` (**Verified FREE**)
- `EORT` — `OrderRoutingRule` (**Verified FREE**)
- `EFUL` — `OrderFulfillment` (**Verified FREE**)
- `ERMA` — `ReturnMerchandiseAuthorization` (**Verified FREE**)

---

## 3. Commercial Market Leaders Surveyed

### 1. Manhattan Active® Omni (Manhattan Associates)
- **Positioning**: Cloud-native tier-1 enterprise Distributed Order Management (DOM) and omnichannel fulfillment orchestration platform.
- **Reference**: https://www.manh.com/products/manhattan-active-omni
- **Key OMS Capabilities**:
  - Unified customer order view across all physical and digital channels.
  - Multi-attribute order routing optimization (least freight cost, fewest splits, fulfillment center distance, SLA commitment).
  - Dynamic inventory reservation with safety stock dampening.
  - Granular post-order lifecycle: order holds, address corrections, partial shipment releases, and RMA receipt inspection.

### 2. Fluent Order Management (Fluent Commerce)
- **Positioning**: Headless, cloud-native Distributed Order Management system built for high-agility order routing and global inventory optimization.
- **Reference**: https://fluentcommerce.com/products/order-management-system/
- **Key OMS Capabilities**:
  - Configurable state-machine workflows for order validation, payment capture, and fraud screening.
  - Distributed sourcing engine selecting optimal nodes based on order splitting rules and geographic priority.
  - Split order fulfillments with independent carrier tracking numbers and status lifecycles.
  - Comprehensive customer return portal integration with disposition rules (return to warehouse, restock, liquidator, scrap).

### 3. IBM Sterling Order Management
- **Positioning**: Enterprise-grade OMS powerhouse known for global scale, complex multi-warehouse routing, and intricate hybrid B2B/B2C fulfillment.
- **Reference**: https://www.ibm.com/products/order-management
- **Key OMS Capabilities**:
  - Intelligent order promising and real-time inventory allocation.
  - Sourcing rule prioritization based on carrier cut-off times, node capacity, and shipping zones.
  - Sophisticated post-purchase modification support (adding/removing lines, shipping method upgrades, customer-requested cancel).
  - Reverse logistics pipeline supporting cross-channel returns, RMA generation, restocking inspection, and automated refund triggers.

### 4. Shopify Plus Order Management & Order Routing Engine
- **Positioning**: Merchant-friendly enterprise order management with native multi-location fulfillment routing and reverse logistics.
- **Reference**: https://www.shopify.com/enterprise/order-management-system
- **Key OMS Capabilities**:
  - Location-based order routing with ranked rule priorities (minimize split shipments, ship from closest location, rank location priorities).
  - Fulfillment orders model where an order is broken down into fulfillment units assigned to specific locations.
  - Built-in fraud risk analysis (Low, Medium, High) with indicator reasons.
  - Self-serve and administrative return workflows with restocking fee deductions, reason tracking, and return labels.

### 5. commercetools Order Management
- **Positioning**: MACH-certified API-first headless commerce platform with flexible order state machines and transaction orchestration.
- **Reference**: https://docs.commercetools.com/api/projects/orders
- **Key OMS Capabilities**:
  - Clean separation between Order State, Payment State, and Shipment State.
  - Line item level tracking (ordered, allocated, fulfilled, cancelled, returned).
  - Post-purchase edits with price re-calculations and credit memos.
  - Native return item records tracking return authorization, shipment state, and payment refund state.

### 6. Loop Returns & Narvar (Post-Purchase & Reverse Logistics Specialists)
- **Positioning**: Best-in-class eCommerce returns, exchanges, tracking, and customer experience orchestration platforms.
- **Reference**: https://www.loopreturns.com/ and https://corp.narvar.com/
- **Key Capabilities**:
  - Return Merchandise Authorization (RMA) tracking with self-service customer initiation.
  - Automated return label generation and tracking numbers.
  - Return outcome resolution: refund to original payment, exchange for variant, or store credit.
  - Item disposition and warehouse restocking condition assessment (restock to inventory, quarantine, scrap).

---

## 4. Feature Catalog (This Sub-Module Only)

### 4.1 Order Capture & Validation
- **Omnichannel Order Capture** — Captures digital orders with customer account linkage, currency, order totals, and address snapshots · seen in: Manhattan, Fluent, Shopify Plus · priority: `table-stakes` · spine: reuses `core.Party`, `accounting.Currency`, snapshots `core.Address` · buildable now.
- **Pre-Fulfillment Fraud Screening** — Multi-factor risk level scoring (`low`, `medium`, `high`, `flagged`) with fraud score and indicator flags to prevent chargebacks · seen in: Shopify Plus, IBM Sterling · priority: `table-stakes` · spine: new fields on `EcommerceOrder` · buildable now.
- **Address Verification Validation** — Flags address verification status (`unverified`, `passed`, `failed`, `corrected`) before releasing orders to fulfillment · seen in: Manhattan, Fluent · priority: `common` · spine: new field on `EcommerceOrder` · buildable now.
- **Inventory Reservation & Allocation** — Soft-reserves variant stock upon order validation and tracks allocation status (`none`, `reserved`, `allocated`, `released`) · seen in: IBM Sterling, Fluent · priority: `table-stakes` · spine: links to `ecommerce.InventoryAllocation` · buildable now.
- **Payment Authorization State Synchronization** — Tracks payment states (`pending`, `authorized`, `captured`, `partially_refunded`, `refunded`, `failed`) decoupled from shipment state · seen in: commercetools, Shopify · priority: `table-stakes` · spine: fields on `EcommerceOrder` · buildable now.

### 4.2 Order Routing & Splitting
- **Configurable Sourcing Rules** — Priority-ranked routing strategies (`closest_location`, `fewest_splits`, `highest_inventory`, `drop_ship_preferred`, `manual`) · seen in: Shopify Plus, Fluent Commerce, Manhattan · priority: `table-stakes` · spine: new `OrderRoutingRule` table referencing `ecommerce.FulfillmentCenter` · buildable now.
- **Split Shipment Orchestration** — Partitions an order across multiple fulfillment centers when single-node stock is insufficient · seen in: Manhattan, Fluent, IBM Sterling · priority: `table-stakes` · spine: modeled via `OrderFulfillment` packages · buildable now.
- **Regional Zone & Geographic Filtering** — Constrains routing rules by destination country or region · seen in: Shopify Plus, IBM Sterling · priority: `common` · spine: fields on `OrderRoutingRule` · buildable now.
- **Drop-Ship Sourcing Flag** — Allows designated product lines or fulfillment centers to route directly to third-party supplier dispatch · seen in: Manhattan, IBM Sterling · priority: `common` · spine: boolean on `OrderRoutingRule` · buildable now.

### 4.3 Order Status & Tracking
- **Decoupled Fulfillment Lifecycle** — Tracks package status independently per package (`draft`, `allocated`, `picking`, `packing`, `shipped`, `in_transit`, `out_for_delivery`, `delivered`, `failed_delivery`) · seen in: Fluent, Narvar · priority: `table-stakes` · spine: modeled via `OrderFulfillment` · buildable now.
- **Multi-Carrier Shipment Tracking Integration** — Stores carrier name (FedEx, UPS, DHL, USPS, Local Courier), tracking number, tracking URL, and estimated delivery date · seen in: Narvar, Shopify Plus · priority: `table-stakes` · spine: fields on `OrderFulfillment` · buildable now.
- **Customer Notification Status** — Tracks whether dispatch and tracking notifications have been transmitted to the customer · seen in: Narvar, Shopify · priority: `common` · spine: boolean and timestamp on `OrderFulfillment` · buildable now.

### 4.4 Order Modifications & Cancellations
- **Post-Purchase Order Cancellation** — Enables administrative or customer cancellation prior to fulfillment, recording cancellation reason and timestamp · seen in: Shopify, commercetools · priority: `table-stakes` · spine: fields and methods on `EcommerceOrder` · buildable now.
- **Partial Line Cancellation** — Allows individual order lines to be cancelled while preserving remaining lines for fulfillment · seen in: IBM Sterling, commercetools · priority: `table-stakes` · spine: line-level status and quantity cancelled on `EcommerceOrderLine` · buildable now.
- **Shipping Address Correction** — Enables customer or support agent to update delivery address prior to fulfillment package release · seen in: Manhattan, Fluent · priority: `common` · spine: snapshot fields on `EcommerceOrder` · buildable now.

### 4.5 Returns & Exchanges (RMA)
- **RMA Lifecycle State Machine** — Tracks complete return journey: `requested`, `authorized`, `label_generated`, `in_transit`, `received`, `inspected`, `approved`, `rejected`, `completed` · seen in: Loop Returns, Narvar, Manhattan · priority: `table-stakes` · spine: `ReturnMerchandiseAuthorization` table · buildable now.
- **Return Resolution Type** — Directs outcome to `refund`, `exchange`, or `store_credit` · seen in: Loop Returns, commercetools · priority: `table-stakes` · spine: choices on `ReturnMerchandiseAuthorization` · buildable now.
- **Return Shipping Label & Tracking** — Generates return tracking number and label documentation URL for customer reverse logistics · seen in: Loop Returns, Narvar · priority: `table-stakes` · spine: fields on `ReturnMerchandiseAuthorization` · buildable now.
- **Warehouse Restocking & Disposition Logic** — Assigns returned items to a target `FulfillmentCenter` with disposition assessment (`restocked`, `scrapped`, `quarantined`) and restocking fee deductions · seen in: Manhattan, Fluent, Loop Returns · priority: `table-stakes` · spine: fields on `ReturnMerchandiseAuthorization` · buildable now.

---

## 5. Recommended Build Scope (This Pass — 4 Models)

We recommend exactly **4 tenant-scoped models** (plus 1 inline child model for lines) organized under `apps/ecommerce/models/OrderManagement/`:

### 1. `EcommerceOrder` [EORD-] (with child `EcommerceOrderLine`)
- **File**: `apps/ecommerce/models/OrderManagement/EcommerceOrders.py`
- **Class**: `class EcommerceOrder(TenantNumbered)`
- **Auto-number Prefix**: `EORD`
- **Fields**:
  - `tenant`: `ForeignKey('core.Tenant', on_delete=models.CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)` (`EORD-#####`)
  - `customer`: `ForeignKey('core.Party', on_delete=models.PROTECT, related_name='ecommerce_orders')`
  - `guest_email`: `EmailField(blank=True)`
  - `currency`: `ForeignKey('accounting.Currency', on_delete=models.PROTECT, related_name='ecommerce_orders')`
  - `status`: `CharField(max_length=25, choices=ORDER_STATUS_CHOICES, default='pending_validation')`
  - `payment_status`: `CharField(max_length=25, choices=PAYMENT_STATUS_CHOICES, default='pending')`
  - `fulfillment_status`: `CharField(max_length=25, choices=FULFILLMENT_STATUS_CHOICES, default='unfulfilled')`
  - `fraud_risk_level`: `CharField(max_length=15, choices=FRAUD_RISK_CHOICES, default='low')`
  - `fraud_score`: `PositiveSmallIntegerField(default=10, validators=[MinValueValidator(0), MaxValueValidator(100)])`
  - `address_verification_status`: `CharField(max_length=20, choices=AVS_STATUS_CHOICES, default='unverified')`
  - `inventory_reservation_status`: `CharField(max_length=20, choices=RESERVATION_STATUS_CHOICES, default='none')`
  - `subtotal_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `discount_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `shipping_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `tax_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `total_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `applied_coupon`: `ForeignKey('ecommerce.CouponPromotion', null=True, blank=True, on_delete=models.SET_NULL, related_name='orders')`
  - `shipping_name`: `CharField(max_length=150)`
  - `shipping_address_line1`: `CharField(max_length=255)`
  - `shipping_city`: `CharField(max_length=100)`
  - `shipping_state`: `CharField(max_length=100, blank=True)`
  - `shipping_postal_code`: `CharField(max_length=30)`
  - `shipping_country`: `CharField(max_length=100)`
  - `billing_name`: `CharField(max_length=150, blank=True)`
  - `billing_address_line1`: `CharField(max_length=255, blank=True)`
  - `billing_city`: `CharField(max_length=100, blank=True)`
  - `billing_state`: `CharField(max_length=100, blank=True)`
  - `billing_postal_code`: `CharField(max_length=30, blank=True)`
  - `billing_country`: `CharField(max_length=100, blank=True)`
  - `cancellation_reason`: `TextField(blank=True)`
  - `cancelled_at`: `DateTimeField(null=True, blank=True)`
  - `customer_notes`: `TextField(blank=True)`
  - `internal_notes`: `TextField(blank=True)`
- **Child Class**: `class EcommerceOrderLine(models.Model)`
  - `tenant`: `ForeignKey('core.Tenant', on_delete=models.CASCADE, related_name='+')`
  - `order`: `ForeignKey(EcommerceOrder, on_delete=models.CASCADE, related_name='lines')`
  - `product`: `ForeignKey('ecommerce.CatalogProduct', on_delete=models.PROTECT, related_name='order_lines')`
  - `variant`: `ForeignKey('ecommerce.ProductVariant', null=True, blank=True, on_delete=models.SET_NULL, related_name='order_lines')`
  - `sku`: `CharField(max_length=80)`
  - `product_name`: `CharField(max_length=200)`
  - `quantity`: `PositiveIntegerField(default=1)`
  - `fulfilled_quantity`: `PositiveIntegerField(default=0)`
  - `returned_quantity`: `PositiveIntegerField(default=0)`
  - `unit_price`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `unit_discount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `line_total`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `status`: `CharField(max_length=20, choices=LINE_STATUS_CHOICES, default='pending')`
- **Form Exclusions**: `tenant`, `number`, `subtotal_amount`, `total_amount`, `cancelled_at`.

### 2. `OrderRoutingRule` [EORT-]
- **File**: `apps/ecommerce/models/OrderManagement/OrderRoutingRules.py`
- **Class**: `class OrderRoutingRule(TenantNumbered)`
- **Auto-number Prefix**: `EORT`
- **Fields**:
  - `tenant`: `ForeignKey('core.Tenant', on_delete=models.CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)` (`EORT-#####`)
  - `name`: `CharField(max_length=150)`
  - `strategy`: `CharField(max_length=30, choices=ROUTING_STRATEGY_CHOICES, default='closest_location')`
  - `priority`: `PositiveIntegerField(default=10)`
  - `destination_country`: `CharField(max_length=100, blank=True)`
  - `destination_region`: `CharField(max_length=100, blank=True)`
  - `preferred_fulfillment_center`: `ForeignKey('ecommerce.FulfillmentCenter', null=True, blank=True, on_delete=models.SET_NULL, related_name='routing_rules')`
  - `allow_split_shipment`: `BooleanField(default=True)`
  - `enable_dropship`: `BooleanField(default=False)`
  - `is_active`: `BooleanField(default=True)`
  - `description`: `TextField(blank=True)`
- **Form Exclusions**: `tenant`, `number`.

### 3. `OrderFulfillment` [EFUL-]
- **File**: `apps/ecommerce/models/OrderManagement/OrderFulfillments.py`
- **Class**: `class OrderFulfillment(TenantNumbered)`
- **Auto-number Prefix**: `EFUL`
- **Fields**:
  - `tenant`: `ForeignKey('core.Tenant', on_delete=models.CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)` (`EFUL-#####`)
  - `order`: `ForeignKey('ecommerce.EcommerceOrder', on_delete=models.CASCADE, related_name='fulfillments')`
  - `fulfillment_center`: `ForeignKey('ecommerce.FulfillmentCenter', null=True, blank=True, on_delete=models.SET_NULL, related_name='fulfillments')`
  - `carrier_name`: `CharField(max_length=80)`
  - `tracking_number`: `CharField(max_length=100, blank=True)`
  - `tracking_url`: `URLField(blank=True)`
  - `status`: `CharField(max_length=25, choices=FULFILLMENT_PACKAGE_STATUS_CHOICES, default='allocated')`
  - `shipping_cost`: `DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))`
  - `shipped_at`: `DateTimeField(null=True, blank=True)`
  - `estimated_delivery_date`: `DateField(null=True, blank=True)`
  - `actual_delivery_date`: `DateField(null=True, blank=True)`
  - `shipping_label_url`: `URLField(blank=True)`
  - `notification_sent`: `BooleanField(default=False)`
  - `notes`: `TextField(blank=True)`
- **Form Exclusions**: `tenant`, `number`, `shipped_at`, `actual_delivery_date`.

### 4. `ReturnMerchandiseAuthorization` [ERMA-]
- **File**: `apps/ecommerce/models/OrderManagement/ReturnMerchandiseAuthorizations.py`
- **Class**: `class ReturnMerchandiseAuthorization(TenantNumbered)`
- **Auto-number Prefix**: `ERMA`
- **Fields**:
  - `tenant`: `ForeignKey('core.Tenant', on_delete=models.CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)` (`ERMA-#####`)
  - `order`: `ForeignKey('ecommerce.EcommerceOrder', on_delete=models.CASCADE, related_name='returns')`
  - `customer`: `ForeignKey('core.Party', on_delete=models.CASCADE, related_name='ecommerce_returns')`
  - `return_type`: `CharField(max_length=20, choices=RETURN_TYPE_CHOICES, default='refund')`
  - `status`: `CharField(max_length=25, choices=RMA_STATUS_CHOICES, default='requested')`
  - `reason`: `CharField(max_length=30, choices=RETURN_REASON_CHOICES, default='changed_mind')`
  - `return_shipping_label_url`: `URLField(blank=True)`
  - `return_tracking_number`: `CharField(max_length=100, blank=True)`
  - `restocking_fee`: `DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))`
  - `refund_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `refund_status`: `CharField(max_length=20, choices=REFUND_STATUS_CHOICES, default='pending')`
  - `restocking_status`: `CharField(max_length=20, choices=RESTOCK_STATUS_CHOICES, default='pending')`
  - `restocking_center`: `ForeignKey('ecommerce.FulfillmentCenter', null=True, blank=True, on_delete=models.SET_NULL, related_name='rma_restocks')`
  - `customer_notes`: `TextField(blank=True)`
  - `inspection_notes`: `TextField(blank=True)`
  - `authorized_at`: `DateTimeField(null=True, blank=True)`
  - `completed_at`: `DateTimeField(null=True, blank=True)`
- **Form Exclusions**: `tenant`, `number`, `authorized_at`, `completed_at`.

---

## 6. Belongs to Sibling Sub-Modules (Parked, Not Scoped Here)

- **Shopping Cart & Checkout Sessions** (`Cart`, `CartItem`, guest checkout conversion) -> belongs to **9.4 Shopping Cart & Checkout**.
- **Customer Account Management & Address Book Portal** -> belongs to **9.6 Customer Account & Profile**.
- **Self-Serve Customer Support Tickets for Orders** -> belongs to **9.14 Customer Service & Support**.
- **Storefront Payment Gateway Integrations** (Stripe, PayPal, Adyen checkout SDKs) -> belongs to **9.4 Shopping Cart & Checkout**.
- **Enterprise Physical Warehouse Packing & Picking Slips** (WMS bin locations, barcode scanners) -> belongs to **Module 4 (SCM) / Module 5 (Inventory)**.
- **Financial General Ledger Posting** (`JournalEntry`, GL accounts) -> belongs to **Module 2 (Accounting)**.

---

## 7. Deferred (Later Passes / External Integrations)

- Direct carrier webhook listeners for real-time live FedEx/UPS tracking telemetry -> deferred to background webhook integration worker.
- Automated payment gateway refund API triggering (Stripe refund call) -> deferred to 9.19 Integration & API Ecosystem.
- Automated address validation API (Google Maps / USPS AVS integration) -> deferred to external API services.

---

## 8. Summary of Research

- **Sub-module:** 9.5 Order Management System (OMS)
- **Leaders surveyed:** Manhattan Active® Omni, Fluent Order Management, IBM Sterling Order Management, Shopify Plus, commercetools, Loop Returns, Narvar.
- **Recommended models (4 models + 1 child):**
  1. `EcommerceOrder` [`EORD-`] (+ `EcommerceOrderLine`) — Omnichannel order capture, validation, fraud scoring, payment state, address snapshots, and cancellation.
  2. `OrderRoutingRule` [`EORT-`] — Multi-location intelligent fulfillment sourcing, split shipment policy, and drop-ship preferences.
  3. `OrderFulfillment` [`EFUL-`] — Decoupled package fulfillment, multi-carrier shipment tracking, delivery dates, and transit status.
  4. `ReturnMerchandiseAuthorization` [`ERMA-`] — Reverse logistics RMA lifecycle, return resolutions (refund/exchange/store credit), inspection, and restocking logic.
- **Catalog written to:** `.claude/tasks/research-ecommerce-9.5.md`
