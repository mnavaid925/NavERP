# Research — Sub-module 9.4: Shopping Cart & Checkout (Module 9 — eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.4 Shopping Cart & Checkout
- **Module:** 9 eCommerce Management System
- **Target app:** `apps/ecommerce` (extending the app created in 9.1 and extended in 9.2, 9.3)
- **Research date:** 2026-10-29
- **Phase:** 1 Research only
- **Output boundary:** `.claude/tasks/research-ecommerce-9.4.md` only

---

## 1. Executive Summary & Domain Architecture

Sub-module 9.4 delivers the **Shopping Cart & Checkout Engine** for NavERP eCommerce. It is the primary conversion funnel of the entire digital store, bridging product discovery (9.1 PIM, 9.7 Search), inventory availability (9.2 Stock & Allocation), and pricing promotions (9.3 Dynamic Pricing & Coupons) with the eventual downstream Order Management System (9.5 OMS) and Accounting Financial Ledger (Module 2).

In modern commerce architectures (Shopify Plus, BigCommerce, Adobe Commerce / Magento, commercetools MACH, Stripe Checkout, Bolt, EasyPost, and TaxJar), the shopping cart and checkout pipeline is divided into three distinct operational domains:

1. **Cart Lifecycle Management (State & Persistence):**
   - Support for anonymous guest sessions (cookie/token-based) and authenticated customer carts (`core.Party`).
   - Cross-device cart persistence (seamless merging of guest cart contents when a user authenticates).
   - Real-time line-item price calculation incorporating 9.3 promotions and volume discounts.
   - Proactive cart abandonment detection, abandonment state tagging, and secure email recovery tokens.

2. **Checkout Flow Orchestration (Conversion Pipeline):**
   - Configurable checkout experience supporting both modern Single-Page Checkout (Shopify/Bolt style) and structured Multi-Step Checkout (Contact -> Shipping Address -> Shipping Method -> Payment -> Confirmation).
   - Visual progress indicators and required customer field validations.
   - Address collection and validation with separate shipping and billing identities.

3. **Transaction Calculations & Gateway Orchestration:**
   - **Shipping Rate Engine:** Support for flat-rate shipping, tiered order-weight tables, free-shipping subtotal thresholds (e.g. Free shipping on orders over $75), local store pickup, and carrier API integration abstraction.
   - **Tax Nexus & Compliance Engine:** Destination-based tax calculation, nexus state tracking, VAT/GST compliance, and B2B tax exemption certificate capture, referencing the existing `accounting.TaxCode` master.
   - **Payment Orchestration Layer:** Pluggable gateway configurations (Credit Cards via Stripe, Digital Wallets via PayPal/Apple Pay, Buy Now Pay Later via Klarna, Bank Wire Transfers, and Cash on Delivery) with PCI-DSS compliance isolation (storing only provider payment intents, status, and transaction tokens—never raw PAN/CVV).

### Architectural Boundary Rulings (L28, L29, L36, L37):
1. **Catalog & SKU Anchor**: Line items in `CartItem` reference `ecommerce.CatalogProduct` (`EPRD-`) and `ecommerce.ProductVariant` (`PVR-`).
2. **Customer / Identity Anchor**: Carts and checkout sessions optionally link to `core.Party` (`customer` role) or remain guest-accessible via UUID session tokens.
3. **Promotion Application (9.3 Reuse)**: Coupon codes submitted in cart/checkout validate against `ecommerce.CouponPromotion` (`ECPN-`) and dynamic discounts calculated via `DynamicPriceRule`.
4. **Inventory Reservation (9.2 Reuse)**: Carts display live available-to-promise inventory. Hard inventory reservation occurs when a checkout session moves to payment processing/order creation via `ecommerce.InventoryAllocation` (`EAL-`).
5. **Accounting & Tax Ledger Ownership (L29, Module 2)**: All financial taxes refer to `accounting.TaxCode` (`apps/accounting/models/Tax/TaxCodes.py`). All payments and journal entries are generated downstream in 9.5 (OMS) / Module 2; 9.4 orchestrates the checkout intent and payment method configuration.

---

## 2. Repo State Checked First

### 2.1 Navigation & App Tree State
- **`apps/core/navigation.py`:**
  - `"9.1"` is live: Product Information Management, Category Hierarchy, Product Variants, Bulk Import/Export, Product Relationships.
  - `"9.2"` is live: Real-Time Stock Tracking, Warehouse & Fulfillment Center Management, Stock Transfers & Adjustments, Backorder & Pre-Order Management, Multi-Channel Inventory Sync.
  - `"9.3"` is live: Dynamic Pricing Rules, Discount & Coupon Management, Flash Sales & Limited-Time Offers, Loyalty & Rewards Pricing, Price Matching & Competitive Monitoring.
  - Sub-module `"9.4"` has no `LIVE_LINKS` entry yet.
- **`apps/ecommerce/` structure:**
  - `models/ProductCatalog/`, `models/InventoryStock/`, `models/PricingPromotion/`
  - `forms/ProductCatalog/`, `forms/InventoryStock/`, `forms/PricingPromotion/`
  - `views/ProductCatalog/`, `views/InventoryStock/`, `views/PricingPromotion/`
  - `urls/ProductCatalog/`, `urls/InventoryStock/`, `urls/PricingPromotion/`
  - `templates/ecommerce/productcatalog/`, `templates/ecommerce/inventorystock/`, `templates/ecommerce/pricingpromotion/`
  - Sub-module 9.4 will add package subdirectories: `CartCheckout/` across `models/`, `forms/`, `views/`, `urls/`, and `templates/ecommerce/cartcheckout/`.

### 2.2 As-Built Core Spine Entities (Grep Verified)
| Entity | Location | Status | 9.4 Usage |
|---|---|---|---|
| `core.Tenant` | `apps/core/models/Tenant.py:17` | **Present** | Strict multi-tenant isolation |
| `core.Party` | `apps/core/models/Party.py:12` | **Present** | Authenticated customer identity |
| `accounting.Currency` | `apps/accounting/models/GeneralLedger/Currencies.py:6` | **Present** | Cart currency ISO code |
| `accounting.TaxCode` | `apps/accounting/models/Tax/TaxCodes.py:6` | **Present** | Tax rates, VAT/GST rules, nexus compliance |
| `ecommerce.CatalogProduct` | `apps/ecommerce/models/ProductCatalog/CatalogProducts.py:8` | **Present** | Target product for cart items (`EPRD-`) |
| `ecommerce.ProductVariant` | `apps/ecommerce/models/ProductCatalog/ProductVariants.py:10` | **Present** | Specific SKU option (`PVR-`) |
| `ecommerce.CouponPromotion` | `apps/ecommerce/models/PricingPromotion/CouponPromotions.py:12` | **Present** | Coupon validation on cart (`ECPN-`) |
| `ecommerce.DynamicPriceRule` | `apps/ecommerce/models/PricingPromotion/DynamicPriceRules.py:12` | **Present** | Price adjustments (`EDPR-`) |

### 2.3 Prefix Collision Verification
The following unique auto-number prefixes have been verified against the entire repository:
- `ECRT` — `Cart` (Unused, clean)
- `ECKS` — `CheckoutSession` (Unused, clean)
- `ESHP` — `ShippingMethodConfig` (Unused, clean)
- `EPMC` — `PaymentMethodConfig` (Unused, clean)

---

## 3. Leaders Surveyed (With Source Links & Capabilities)

### 1. Shopify Plus / Shop Pay Checkout
- **Positioning:** Global benchmark for eCommerce checkout speed, one-page checkout, and checkout extensibility.
- **Reference:** https://www.shopify.com/checkout
- **Key Features Surveyed:**
  - One-page modular checkout with live subtotal/tax/shipping recalculation.
  - Persistent cart sessions across desktop and mobile, with guest cart token recovery links.
  - Shipping profiles (flat rate, order value thresholds, carrier integration).
  - Multi-gateway payment orchestration supporting Shop Pay, Wallets, Credit Cards, and BNPL.

### 2. BigCommerce Optimized One-Page Checkout
- **Positioning:** Enterprise Open SaaS eCommerce leader with native single-page checkout and abandoned cart saver.
- **Reference:** https://www.bigcommerce.com/features/checkout/
- **Key Features Surveyed:**
  - Single-page checkout reducing drop-offs with responsive inline validation.
  - Configurable guest checkout vs mandatory customer account registration.
  - Abandoned cart recovery campaigns with automated email triggers and discount recovery incentives.
  - Granular shipping zone definitions with dimensional weight support and live carrier rates.

### 3. commercetools (Composable Commerce MACH Cart Microservice)
- **Positioning:** Pioneer in headless, API-first commerce microservices for global enterprises.
- **Reference:** https://docs.commercetools.com/api/projects/carts
- **Key Features Surveyed:**
  - Modular Cart microservice decoupling cart creation, line-item updates, and discount calculations.
  - Separation between active shopping Cart and Checkout / Order state transitions.
  - Tax calculation strategies (Platform tax rules vs External tax provider webhook).
  - Shipping method selection based on shipping address country and order amount limits.

### 4. Adobe Commerce (Magento 2 Quote & Checkout Architecture)
- **Positioning:** Standard enterprise monolith/PWA framework with Quote service contracts.
- **Reference:** https://experienceleague.adobe.com/en/docs/commerce-operations/configuration-guide/sales/checkout/checkout-options
- **Key Features Surveyed:**
  - `Magento\Quote` persistent cart mechanism with customer-to-guest merging.
  - Totals Collector architecture: modular collectors calculating Subtotal, Discount, Shipping, Tax, and Grand Total.
  - Table-rate shipping rules (Destination vs Weight vs Price).
  - Payment method orchestration supporting offline methods (Check/MO, COD, Bank Transfer) and online payment gateways.

### 5. Stripe Checkout & Stripe Tax
- **Positioning:** Industry standard hosted checkout and automated global tax compliance engine.
- **Reference:** https://stripe.com/checkout & https://stripe.com/tax
- **Key Features Surveyed:**
  - Dynamic payment method sorting based on customer locale, currency, and device.
  - Nexus-aware real-time sales tax calculation without custom tax table maintenance.
  - Session expiration management (default 24 hours) and cancellation URLs.
  - PCI SAQ-A compliant tokenization with zero cardholder data on merchant servers.

### 6. Bolt One-Click Checkout
- **Positioning:** Checkout optimization network focusing on friction reduction and passwordless guest checkout.
- **Reference:** https://www.bolt.com/checkout
- **Key Features Surveyed:**
  - Network-wide passwordless identity detection via email/phone OTP.
  - Real-time address autocomplete and delivery rate evaluation.
  - Integrated checkout session fraud risk scoring.

### 7. EasyPost Multi-Carrier Shipping API
- **Positioning:** Leading logistics and carrier rate shopping platform.
- **Reference:** https://www.easypost.com/shipping-api
- **Key Features Surveyed:**
  - Carrier rate calculation across USPS, FedEx, UPS, and DHL.
  - Dimensional weight calculation (Length x Width x Height / DimDivisor).
  - Free shipping threshold rules based on pre-tax subtotal.

---

## 4. Feature Catalog (Sub-Module 9.4 Only)

### 4.1 Persistent & Guest Cart (NavERP.md Bullet 1)
- **Guest Session Cart** — Cookie/token-based cart identifier allowing shoppers to add products without logging in · seen in: Shopify, BigCommerce, WooCommerce · priority: table-stakes · spine: new table `Cart` (`ECRT-`) · buildable now.
- **Customer Cart Persistence** — Cart tied to `core.Party` (`customer` role), persisting across devices and browser sessions · seen in: Adobe Commerce, commercetools · priority: table-stakes · spine: `Cart.customer` FK to `core.Party` · buildable now.
- **Guest-to-Customer Cart Merging** — When an anonymous guest signs in, their session cart automatically merges into their customer cart · seen in: BigCommerce, Shopify · priority: common · spine: service logic in `CartService` · buildable now.
- **Cart Abandonment Tracking** — Automatic tagging of inactive carts (`abandoned` status after configurable inactivity window) with abandonment timestamp · seen in: BigCommerce Abandoned Cart Saver, Klaviyo · priority: table-stakes · spine: `Cart.status`, `Cart.abandoned_at` · buildable now.
- **Abandonment Recovery Token & URL** — Secure unguessable token and recovery URL to restore the exact cart state in 1 click · seen in: Shopify, BigCommerce · priority: common · spine: `Cart.recovery_token` · buildable now.
- **Line Item Notes & Options** — Storing variant configurations, personalized engraving/notes, or gift options · seen in: Shopify Line Item Properties, Etsy · priority: common · spine: `CartItem.custom_attributes` (JSONField) · buildable now.

### 4.2 One-Page & Multi-Step Checkout (NavERP.md Bullet 2)
- **Configurable Checkout Flow** — Support for One-Page Checkout (all sections visible) and Multi-Step Checkout (Contact -> Shipping -> Payment -> Review) with persistent session · seen in: Shopify, Adobe Commerce, BigCommerce · priority: table-stakes · spine: new table `CheckoutSession` (`ECKS-`) with `flow_type` · buildable now.
- **Step Progress & State Tracking** — Clear step indicators (`contact`, `shipping_address`, `shipping_method`, `payment`, `review`, `completed`) preventing invalid state transitions · seen in: Shopify, Bolt · priority: table-stakes · spine: `CheckoutSession.current_step` · buildable now.
- **Address Book Integration & Guest Capture** — Automatically loading saved addresses for authenticated customers from `core.Address` while allowing guest entry of shipping/billing info · seen in: Adobe Commerce, BigCommerce · priority: table-stakes · spine: `CheckoutSession` address snapshot fields · buildable now.
- **Billing Same as Shipping Toggle** — Instant 1-click duplication of shipping address to billing address, reducing checkout friction · seen in: Shopify, Stripe · priority: table-stakes · spine: `CheckoutSession.billing_same_as_shipping` · buildable now.
- **Session Expiration & Abandonment** — Checkout sessions expire after 24 hours to release soft locks and refresh dynamic pricing · seen in: Stripe Checkout, commercetools · priority: common · spine: `CheckoutSession.expires_at`, `CheckoutSession.status` · buildable now.

### 4.3 Shipping Rate Calculation (NavERP.md Bullet 3)
- **Configurable Shipping Methods** — Tenant-configurable delivery options (Standard Ground, Express 2-Day, Next Day, Free Delivery, Local Store Pickup) · seen in: Shopify, BigCommerce · priority: table-stakes · spine: new table `ShippingMethodConfig` (`ESHP-`) · buildable now.
- **Free Shipping Threshold Engine** — Automatic qualification for free shipping when pre-tax order subtotal exceeds a configurable threshold (e.g. Free shipping on $75+) · seen in: Shopify, WooCommerce, Amazon · priority: table-stakes · spine: `ShippingMethodConfig.min_order_subtotal` · buildable now.
- **Weight-Based & Dimensional Calculation** — Tiered pricing based on total cart weight (base rate + per-kg surcharge) · seen in: EasyPost, Magento Table Rates · priority: common · spine: `ShippingMethodConfig.cost_per_kg`, `calculation_type` · buildable now.
- **Geographic Destination Zones** — Restricting or pricing shipping methods based on destination country/region ISO codes · seen in: BigCommerce Shipping Zones, WooCommerce · priority: table-stakes · spine: `ShippingMethodConfig.destination_countries` · buildable now.
- **Carrier API Gateway Integration** — Real-time rate shopping from FedEx/UPS/USPS APIs · seen in: EasyPost, Shippo · priority: differentiator · spine: carrier type enumeration, simulation buildable now, real carrier HTTP APIs integration/later.

### 4.4 Tax Calculation & Compliance (NavERP.md Bullet 4)
- **Nexus-Aware Destination Tax Calculation** — Applying tax rates based on shipping destination state/country and tenant nexus presence · seen in: TaxJar, Avalara, Stripe Tax · priority: table-stakes · spine: reuse `accounting.TaxCode` (`apps/accounting/models/Tax/TaxCodes.py`) + `CheckoutSession.tax_jurisdiction` · buildable now.
- **VAT / GST Inclusive & Exclusive Handling** — Support for both North American sales tax (exclusive, added at checkout) and European/Global VAT (inclusive in display price or jurisdiction-calculated) · seen in: commercetools, Shopify Tax · priority: table-stakes · spine: `accounting.TaxCode.is_inclusive` · buildable now.
- **B2B Tax Exemption Certificate Capture** — Collecting tax exemption certificate numbers and rationale for wholesale/non-profit buyers, waiving tax at checkout · seen in: BigCommerce B2B, Avalara CertCapture · priority: common · spine: `CheckoutSession.tax_exempt`, `CheckoutSession.exemption_number` · buildable now.
- **Line-Item Tax Breakdown Snapshot** — Freezing exact tax rates and amounts at checkout submission for audit compliance · seen in: Stripe Tax, TaxJar · priority: table-stakes · spine: `CheckoutSession.tax_amount`, `CheckoutSession.tax_breakdown` (JSONField) · buildable now.

### 4.5 Payment Method Orchestration (NavERP.md Bullet 5)
- **Configurable Payment Gateways** — Tenant-level enablement of payment methods: Credit Cards (Stripe), Digital Wallets (PayPal Express), Buy Now Pay Later (Klarna), Bank Wire Transfers, and Cash on Delivery (COD) · seen in: Shopify Payments, BigCommerce, Adobe Commerce · priority: table-stakes · spine: new table `PaymentMethodConfig` (`EPMC-`) · buildable now.
- **Payment Fee & Surcharge Rules** — Optional payment method processing fee or discount (e.g. 2% fee on credit cards or 3% discount on direct bank transfer) · seen in: Magento, WooCommerce Payment Fees · priority: common · spine: `PaymentMethodConfig.fee_type`, `PaymentMethodConfig.fee_amount` · buildable now.
- **Cart Amount Eligibility Thresholds** — Enforcing minimum and maximum cart totals for specific methods (e.g. Klarna BNPL only between $35 and $1,500; COD capped at $500) · seen in: Klarna, PayPal Pay in 4 · priority: common · spine: `PaymentMethodConfig.min_cart_amount`, `max_cart_amount` · buildable now.
- **PCI-DSS Compliance Tokenization** — Tokenized payment representation (storing gateway `payment_intent_id` and client tokens, never raw credit card numbers or CVV) · seen in: Stripe Elements, Braintree Drop-in · priority: table-stakes · spine: `CheckoutSession.payment_token`, `CheckoutSession.payment_status` · buildable now.
- **Environment Toggle & Sandbox Testing** — Safe toggle between test/sandbox mode and production environment per payment method · seen in: Stripe, PayPal Developer · priority: table-stakes · spine: `PaymentMethodConfig.environment` · buildable now.

---

## 5. Recommended Build Scope (This Pass — Exactly 4 Models)

To achieve complete CRUD, tenant isolation, seeder coverage, and full alignment with the 5 feature bullets of Sub-module 9.4, we recommend **exactly 4 tenant-scoped models** (plus 1 child line-item model within the `Carts.py` file):

### 1. `Cart` (`ECRT-`) & `CartItem` — `Carts.py`
- **Serves:** Bullet 1 (Persistent & Guest Cart, cross-device persistence, and abandonment recovery).
- **Auto-number Prefix:** `ECRT` (`NUMBER_PREFIX = "ECRT"`)
- **Key Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=models.CASCADE, related_name='ecommerce_carts')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `customer`: `ForeignKey('core.Party', on_delete=models.SET_NULL, null=True, blank=True, related_name='ecommerce_carts')`
  - `session_key`: `CharField(max_length=64, blank=True, db_index=True)` (for guest sessions)
  - `email`: `EmailField(blank=True)` (captured during shopping or checkout for recovery)
  - `status`: `CharField(max_length=20, choices=[('active', 'Active'), ('locked', 'Locked (In Checkout)'), ('abandoned', 'Abandoned'), ('converted', 'Converted to Order'), ('expired', 'Expired')], default='active', db_index=True)`
  - `currency`: `CharField(max_length=3, default='USD')`
  - `subtotal`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `discount_total`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `tax_total`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `shipping_total`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `grand_total`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `coupon_code`: `CharField(max_length=50, blank=True)`
  - `last_activity_at`: `DateTimeField(default=timezone.now)`
  - `abandoned_at`: `DateTimeField(null=True, blank=True)`
  - `recovery_token`: `CharField(max_length=64, blank=True, unique=True, null=True)`
  - `recovery_sent_at`: `DateTimeField(null=True, blank=True)`
  - `notes`: `TextField(blank=True)`
- **Child Model `CartItem`:**
  - `cart`: `ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')`
  - `product`: `ForeignKey('ecommerce.CatalogProduct', on_delete=models.CASCADE, related_name='cart_items')`
  - `variant`: `ForeignKey('ecommerce.ProductVariant', on_delete=models.SET_NULL, null=True, blank=True, related_name='cart_items')`
  - `quantity`: `PositiveIntegerField(default=1)`
  - `unit_price`: `DecimalField(max_digits=12, decimal_places=2)`
  - `total_price`: `DecimalField(max_digits=12, decimal_places=2)`
  - `custom_attributes`: `JSONField(default=dict, blank=True)`

### 2. `CheckoutSession` (`ECKS-`) — `CheckoutSessions.py`
- **Serves:** Bullet 2 (One-Page & Multi-Step Checkout) & Bullet 4 (Tax Calculation & Compliance snapshot).
- **Auto-number Prefix:** `ECKS` (`NUMBER_PREFIX = "ECKS"`)
- **Key Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=models.CASCADE, related_name='ecommerce_checkout_sessions')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `cart`: `ForeignKey('ecommerce.Cart', on_delete=models.CASCADE, related_name='checkout_sessions')`
  - `customer`: `ForeignKey('core.Party', on_delete=models.SET_NULL, null=True, blank=True, related_name='ecommerce_checkout_sessions')`
  - `email`: `EmailField()`
  - `phone`: `CharField(max_length=30, blank=True)`
  - `flow_type`: `CharField(max_length=20, choices=[('one_page', 'One-Page Checkout'), ('multi_step', 'Multi-Step Checkout')], default='one_page')`
  - `current_step`: `CharField(max_length=20, choices=[('contact', 'Contact Details'), ('shipping_address', 'Shipping Address'), ('shipping_method', 'Shipping Method'), ('payment', 'Payment'), ('review', 'Review & Place Order'), ('completed', 'Completed')], default='contact')`
  - `status`: `CharField(max_length=20, choices=[('in_progress', 'In Progress'), ('processing', 'Processing Payment'), ('completed', 'Completed'), ('expired', 'Expired'), ('abandoned', 'Abandoned')], default='in_progress', db_index=True)`
  - **Shipping Address:** `shipping_name`, `shipping_address_line1`, `shipping_address_line2`, `shipping_city`, `shipping_state`, `shipping_postal_code`, `shipping_country`
  - **Billing Address:** `billing_same_as_shipping` (BooleanField, default=True), `billing_name`, `billing_address_line1`, `billing_city`, `billing_state`, `billing_postal_code`, `billing_country`
  - **Method References:**
    - `shipping_method`: `ForeignKey('ecommerce.ShippingMethodConfig', on_delete=models.SET_NULL, null=True, blank=True, related_name='checkout_sessions')`
    - `payment_method`: `ForeignKey('ecommerce.PaymentMethodConfig', on_delete=models.SET_NULL, null=True, blank=True, related_name='checkout_sessions')`
  - **Tax & Compliance (Bullet 4):**
    - `tax_code`: `ForeignKey('accounting.TaxCode', on_delete=models.SET_NULL, null=True, blank=True, related_name='ecommerce_checkouts')`
    - `tax_jurisdiction`: `CharField(max_length=100, blank=True)`
    - `tax_rate`: `DecimalField(max_digits=6, decimal_places=4, default=Decimal('0.0000'))`
    - `is_tax_exempt`: `BooleanField(default=False)`
    - `tax_exemption_number`: `CharField(max_length=50, blank=True)`
    - `tax_breakdown`: `JSONField(default=dict, blank=True)`
  - **Financial Totals Snapshot:**
    - `subtotal_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
    - `discount_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
    - `shipping_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
    - `tax_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
    - `total_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - **Payment State & Order Reference:**
    - `payment_status`: `CharField(max_length=20, choices=[('pending', 'Pending'), ('authorized', 'Authorized'), ('paid', 'Paid'), ('failed', 'Failed')], default='pending')`
    - `payment_transaction_id`: `CharField(max_length=100, blank=True)`
    - `order_reference`: `CharField(max_length=50, blank=True)` (ready to link to 9.5 OMS order)
    - `expires_at`: `DateTimeField()`
    - `completed_at`: `DateTimeField(null=True, blank=True)`

### 3. `ShippingMethodConfig` (`ESHP-`) — `ShippingMethods.py`
- **Serves:** Bullet 3 (Shipping Rate Calculation, dimensional weight, free-threshold rules, and local delivery).
- **Auto-number Prefix:** `ESHP` (`NUMBER_PREFIX = "ESHP"`)
- **Key Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=models.CASCADE, related_name='ecommerce_shipping_methods')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `name`: `CharField(max_length=100)` (e.g. "Standard Ground Delivery", "Express Air Shipping", "Free Shipping ($75+)", "Local Store Pickup")
  - `code`: `CharField(max_length=50)` (e.g. `GROUND`, `EXPRESS`, `FREE_75`, `LOCAL_PICKUP`)
  - `carrier`: `CharField(max_length=20, choices=[('custom', 'Custom / Internal Fleet'), ('fedex', 'FedEx'), ('ups', 'UPS'), ('usps', 'USPS'), ('dhl', 'DHL')], default='custom')`
  - `calculation_type`: `CharField(max_length=20, choices=[('flat_rate', 'Flat Rate'), ('weight_tiered', 'Weight-Based Tier'), ('free_threshold', 'Free Above Subtotal Threshold'), ('local_pickup', 'Local Store Pickup / Free')], default='flat_rate')`
  - `base_rate`: `DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))`
  - `cost_per_kg`: `DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))`
  - `free_shipping_threshold`: `DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)`
  - `estimated_days_min`: `PositiveSmallIntegerField(default=3)`
  - `estimated_days_max`: `PositiveSmallIntegerField(default=5)`
  - `destination_countries`: `CharField(max_length=255, default='US,CA', help_text="Comma-separated ISO country codes or 'ALL'")`
  - `is_active`: `BooleanField(default=True, db_index=True)`
  - `sort_order`: `PositiveSmallIntegerField(default=0)`
  - `description`: `TextField(blank=True)`

### 4. `PaymentMethodConfig` (`EPMC-`) — `PaymentMethods.py`
- **Serves:** Bullet 5 (Payment Method Orchestration, credit cards, digital wallets, BNPL, bank transfers, COD).
- **Auto-number Prefix:** `EPMC` (`NUMBER_PREFIX = "EPMC"`)
- **Key Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=models.CASCADE, related_name='ecommerce_payment_methods')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `name`: `CharField(max_length=100)` (e.g. "Credit / Debit Card (Stripe)", "PayPal Express Checkout", "Klarna Buy Now Pay Later", "Direct Bank Wire Transfer", "Cash on Delivery (COD)")
  - `provider`: `CharField(max_length=30, choices=[('stripe', 'Stripe Payments'), ('paypal', 'PayPal Express'), ('klarna', 'Klarna BNPL'), ('bank_transfer', 'Direct Bank Transfer / Wire'), ('cod', 'Cash on Delivery (COD)')], default='stripe')`
  - `method_category`: `CharField(max_length=20, choices=[('credit_card', 'Credit / Debit Card'), ('wallet', 'Digital Wallet'), ('bnpl', 'Buy Now Pay Later'), ('bank_transfer', 'Bank Transfer'), ('cash_on_delivery', 'Cash on Delivery')], default='credit_card')`
  - `environment`: `CharField(max_length=15, choices=[('sandbox', 'Sandbox / Test Mode'), ('production', 'Live / Production')], default='sandbox')`
  - `is_active`: `BooleanField(default=True, db_index=True)`
  - `display_order`: `PositiveSmallIntegerField(default=0)`
  - `fee_type`: `CharField(max_length=15, choices=[('none', 'No Surcharge'), ('percentage', 'Percentage Surcharge'), ('fixed', 'Fixed Fee Surcharge')], default='none')`
  - `fee_amount`: `DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))`
  - `min_order_amount`: `DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)`
  - `max_order_amount`: `DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)`
  - `supported_currencies`: `CharField(max_length=100, default='USD,EUR,GBP')`
  - `instructions`: `TextField(blank=True, help_text="Customer instructions displayed at checkout (e.g. bank account details or COD terms)")`
  - `supports_refunds`: `BooleanField(default=True)`

---

## 6. Belongs to Sibling Sub-Modules (Parked, Not Scoped Here)

- **Order Capture, Fulfillment Routing, & Split Shipments** -> Belongs to **9.5 Order Management System (OMS)**. Checkout completion creates a `CheckoutSession` marked `completed` and generates an OMS Order.
- **Customer Account Dashboard & Saved Address Book** -> Belongs to **9.6 Customer Account & Profile**. 9.4 consumes saved addresses from `core.Address` / `Party` read-only.
- **Catalog Navigation & Product Details** -> Belongs to **9.1 Product Catalog Management**.
- **Inventory Stock Reservation & Warehouse Picking** -> Belongs to **9.2 Inventory & Stock Management**.
- **Promotional Coupons & Dynamic Price Rules Engine** -> Belongs to **9.3 Pricing & Promotion Engine**. 9.4 evaluates coupon codes against 9.3's `CouponPromotion` model.
- **Post-purchase Order Tracking & RMA Returns** -> Belongs to **9.5 Order Management System (OMS)**.

---

## 7. Deferred (Later Passes / Integrations)

- **Live Carrier Webhook Tracking (FedEx/UPS/DHL Live API credentials)** — Tenant-level API keys and live XML/JSON carrier rate requests are modeled with fallback calculation types (`flat_rate`, `weight_tiered`, `free_threshold`). Production carrier API connectors deferred to 9.19 (Integration & API Ecosystem).
- **Automated Abandoned Cart Email Sequences (Klaviyo/SendGrid)** — 9.4 records the `abandoned_at` timestamp, `recovery_token`, and manual trigger view. Automated cron-based worker delivery is deferred to background automation.
- **Third-Party Real-Time Tax Cloud (TaxJar / Avalara AvaTax APIs)** — Local nexus rules and rates calculate dynamically via destination lookup and `accounting.TaxCode`. Third-party SaaS tax API synchronization deferred to 9.19.
- **Live Stripe Payment Element / Apple Pay JS SDK embedding** — 9.4 models the full orchestration layer, gateway configs, test credentials, and mock authorization tokens. Client-side JS SDK payment elements can be wired when front-end payment keys are provisioned.

---

## 8. Summary for Todo Agent & Phase 2

- **Sub-module:** 9.4 Shopping Cart & Checkout
- **App:** `apps/ecommerce` (Package: `CartCheckout/`)
- **Models Recommended:** Exactly 4 models:
  1. `Cart` (`ECRT-`) & `CartItem` (Session/guest & persistent carts, abandonment tracking, recovery tokens)
  2. `CheckoutSession` (`ECKS-`) (One-page/multi-step checkout orchestrator, address snapshot, tax & shipping totals)
  3. `ShippingMethodConfig` (`ESHP-`) (Shipping rates, weight tiers, free-shipping threshold rules, pickup)
  4. `PaymentMethodConfig` (`EPMC-`) (Gateway orchestration, fees, BNPL, credit cards, COD, sandbox toggle)
- **Verified Core Reused:** `core.Tenant`, `core.Party`, `accounting.TaxCode`, `accounting.Currency`, `ecommerce.CatalogProduct`, `ecommerce.ProductVariant`, `ecommerce.CouponPromotion`.
- **Output File:** `.claude/tasks/research-ecommerce-9.4.md`
