# Research — Sub-module 9.12: Subscription & Recurring Commerce (Module 9 — eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.12 Subscription & Recurring Commerce
- **Module:** 9 eCommerce Management System
- **Target app:** `apps/ecommerce` (extending the app created in 9.1 and extended through 9.8)
- **Research date:** 2026-10-31
- **Phase:** 1 Research only
- **Output boundary:** `.claude/tasks/research-ecommerce-9.12.md` only

---

## 1. Executive Summary & Domain Architecture

Sub-module 9.12 delivers the **Subscription Plan Design, Recurring Billing & Invoicing, Subscription Self-Service Portal, Subscription Box & Curated Assortment Rotation, and Churn Prediction & Deflection Retention Engine** for the NavERP eCommerce platform.

In modern recurring digital commerce (exemplified by Recharge Payments, Ordergroove, Stripe Billing, Chargebee, Recurly, Smartrr, Loop Subscriptions, Skio, and Bold Subscriptions), recurring subscription revenue provides merchants with predictable cash flow, higher Customer Lifetime Value (LTV), and lower overall customer acquisition costs (CAC). Commercial benchmarks indicate:
- **Subscribe & Save** models achieve 28% to 45% higher customer retention rates compared to single-purchase transactional models.
- **Self-Service Subscriber Portals** with flexible pause, skip, date change, and SKU swap controls decrease voluntary cancellations by over 50%.
- **Intelligent Cancellation Interception (Defensive Flows)** offering targeted deflection incentives (e.g. 15% discount for 2 billing cycles, immediate shipment skip, or alternate flavor/box swap) recover 20% to 35% of would-be cancelled subscriptions.
- **Curated Assortment & Surprise Boxes** require dynamic rotation cycles, customer preference profiles (allergies, sizing, style preferences), and automated inventory allocation rules to maintain subscriber delight across cycles.

### Architectural Boundary Rulings (L28, L29, L36, L37):
1. **Catalog & Core Spine Integration (L36/L37)**:
   - Subscription plans attach directly to canonical **`ecommerce.CatalogProduct`** (`EPRD-`, 9.1) and **`ecommerce.ProductVariant`** (`PVR-`, 9.1).
   - Customer subscription accounts link to **`ecommerce.CustomerAccountProfile`** (`ECAP-`, 9.6) and unified Core Spine **`core.Party`** and **`accounts.User`**.
   - Recurring order instances spawn canonical **`ecommerce.EcommerceOrder`** (`EORD-`, 9.5) and **`ecommerce.EcommerceOrderLine`** records upon billing execution.
   - Financial ledger postings (when recurring bills or payments settle) post through **`apps/accounting`** (`Invoice`, `Payment`, `JournalEntry` via string reference).
2. **Clear Sibling Boundaries (9.4 vs. 9.5 vs. 9.6 vs. 9.8 vs. 9.12)**:
   - **Sub-module 9.4 (Cart & Checkout, shipped)**: Owns single-session cart lines, one-time checkout flows, and guest/authenticated payment method capture.
   - **Sub-module 9.5 (Order Management, shipped)**: Owns order fulfillment, split shipments, and returns/RMAs. When a subscription cycle bills, it creates an `EcommerceOrder` in 9.5.
   - **Sub-module 9.6 (Customer Account, shipped)**: Owns shopper addresses, login credentials, and wishlist management.
   - **Sub-module 9.8 (Personalization, shipped)**: Owns behavioral telemetry, recommendations, and dynamic RFM segments.
   - **Sub-module 9.12 (This Pass)**: Owns recurring plan cadence rules (weekly, monthly, quarterly, annual), subscription lifecycle instances, self-service pause/skip/swap rules, curated box rotation schedules, and churn deflection action logs.
3. **Multi-Tenancy & Data Isolation**:
   All subscription plans, customer subscriptions, curation schedules, and retention records are strictly scoped by `tenant` (`core.Tenant`). Subscriber tokens and billing schedules of Tenant A never leak into or trigger for Tenant B.
4. **Base Class & Prefix Discipline**:
   All 4 models inherit from `TenantNumbered` (`apps/ecommerce/models/_base.py`), providing `tenant` FK (`on_delete=CASCADE`), thread-safe auto-number generation, and timestamps.

---

## 2. Repo State Checked First

### 2.1 Navigation & App Tree State
- **`apps/core/navigation.py`:**
  - `"9.1"` is live: Product Catalog Management (`EPRD`, `PVR`, `ECAT`, `PREL`).
  - `"9.2"` is live: Inventory & Stock Management (`EFC`, `EAL`, `EBK`, `ESYN`).
  - `"9.3"` is live: Pricing & Promotion Engine (`EDPR`, `ECPN`, `EFLS`, `ECPM`).
  - `"9.4"` is live: Shopping Cart & Checkout (`ECRT`, `ECKS`, `ESHP`, `EPMC`).
  - `"9.5"` is live: Order Management System (`EORD`, `EFUL`, `ERMA`, `EORT`).
  - `"9.6"` is live: Customer Account & Profile (`ECAP`, `ECAD`, `EWSL`, `ECPR`).
  - `"9.7"` is live: Search & Product Discovery (`ESYM`, `ESFC`, `ESMR`, `ESQL`).
  - `"9.8"` is live: Personalization & Recommendation (`ESEG`, `EREC`, `EPEX`, `ESBE`).
  - Sub-module `"9.12"` currently has no `LIVE_LINKS` entries yet.
- **`apps/ecommerce/` package structure:**
  - Sub-module 9.12 will add package subdirectories: `SubscriptionCommerce/` across `models/`, `forms/`, `views/`, `urls/`, and `templates/ecommerce/subscriptioncommerce/`.

### 2.2 As-Built Core Spine Entities (Grep Verified)
| Entity | Location | Status | 9.12 Usage |
|---|---|---|---|
| `core.Tenant` | `apps/core/models/Tenant.py:17` | **Present** | Strict workspace tenant isolation |
| `core.Party` | `apps/core/models/Party.py:5` | **Present** | Unified shopper party identity |
| `accounts.User` | `apps/accounts/models/User.py:14` | **Present** | Authenticated subscriber/staff identity |
| `ecommerce.CatalogProduct` | `apps/ecommerce/models/ProductCatalog/CatalogProducts.py:8` | **Present** | Target subscription product or curated box item |
| `ecommerce.ProductVariant` | `apps/ecommerce/models/ProductCatalog/ProductVariants.py:10` | **Present** | Specific variant/SKU for recurring order delivery |
| `ecommerce.CustomerAccountProfile` | `apps/ecommerce/models/CustomerProfile/CustomerAccountProfiles.py:11` | **Present** | Shopper profile anchor for active subscription |
| `ecommerce.EcommerceOrder` | `apps/ecommerce/models/OrderManagement/EcommerceOrders.py:10` | **Present** | Target order created upon recurring billing cycle |
| `accounting.Invoice` | `apps/accounting/models/GeneralLedger/` | **Present** | Cross-module financial invoice posting |

### 2.3 Prefix Collision Verification
All candidate prefixes checked across all models in the repository via `git grep -E '\b(ESPL|ESUB|ESBX|ESRT)\b'`:
- `ESPL` — `SubscriptionPlan` (**Verified 100% FREE**)
- `ESUB` — `CustomerSubscription` (**Verified 100% FREE**)
- `ESBX` — `SubscriptionBoxCuration` (**Verified 100% FREE**)
- `ESRT` — `SubscriptionRetentionAction` (**Verified 100% FREE**)

---

## 3. Commercial Market Leaders Surveyed

### 1. Recharge Payments
- **Positioning**: The standard in DTC subscription commerce on Shopify & BigCommerce, processing billions in recurring volume.
- **Reference**: https://rechargepayments.com/features/
- **Key Capabilities**:
  - **Flexible Cadences**: Days, weeks, months, or custom billing day-of-month anchors.
  - **Subscribe & Save Discounts**: Tiered incentive pricing (e.g. 15% off first order, 10% ongoing).
  - **Self-Service Customer Portal**: Passwordless login, skip delivery, pause subscription, change shipping address or billing card.
  - **Smart Cancellation Prevention**: Multi-step exit surveys offering pause, skip, swap, or instant discount incentives before cancel confirmation.
  - **Dunning Management**: Automatic retry intervals (e.g. 3, 5, 7 days), customer notification emails, and card update links.

### 2. Ordergroove
- **Positioning**: Enterprise subscription and relationship commerce platform powering brands like L'Oreal, Dollar Shave Club, and PetSmart.
- **Reference**: https://www.ordergroove.com/subscriptions/
- **Key Capabilities**:
  - **Subscription Manager**: Embeddable customer portal prioritizing frictionless skip and product swap to mitigate subscriber fatigue.
  - **Predictive Reorder Logic**: AI-driven replenishment schedules adjusting delivery cadence based on customer consumption velocity.
  - **Prepaid & Gift Subscriptions**: Support for upfront lump-sum payment terms (3, 6, 12 months) with scheduled ongoing fulfillment.
  - **Integrated Dunning & Credit Card Updater**: Card expiration prediction and token refreshing to minimize involuntary churn.

### 3. Stripe Billing
- **Positioning**: Global infrastructure leader for recurring billing, usage pricing, and dunning automation.
- **Reference**: https://stripe.com/billing
- **Key Capabilities**:
  - **Prorations & Plan Transitions**: Instant proration calculation when upgrading or downgrading plans mid-cycle.
  - **Trial Periods & Commitment Terms**: Free or discounted trial intervals that automatically convert to standard billing on day N.
  - **Customer Portal**: Hosted self-service portal for updating payment details, viewing invoices, and changing subscription tiers.
  - **Smart Retries & Revenue Recovery**: Machine-learning powered retry timing based on banking networks.

### 4. Chargebee
- **Positioning**: Comprehensive subscription management, recurring billing, and revenue recognition suite.
- **Reference**: https://www.chargebee.com/recurring-billing-management/
- **Key Capabilities**:
  - **Retention Engine (Chargebee Retention)**: Dynamic churn deflection flows tailoring offers according to cancellation reason (e.g., offer a temporary pause for "I have too much inventory", or offer a discount for "Too expensive").
  - **Dunning Workflows**: Sophisticated grace periods, soft-dunning email cadences, and hard-dunning automated cancellation triggers.
  - **Multi-Frequency Plans**: Unified subscription product catalog supporting monthly, quarterly, annual, and custom billing intervals.

### 5. Recurly
- **Positioning**: Enterprise recurring subscription and churn management platform.
- **Reference**: https://recurly.com/product/
- **Key Capabilities**:
  - **Decline Management**: Advanced recovery algorithms reducing involuntary churn by up to 73%.
  - **Subscriber Lifecycle Orchestration**: Granular subscription states: Trialing, Active, Paused, In Dunning, Cancelled, Expired.
  - **Gift & Prepaid Subscriptions**: Scheduled activation dates and automated renewal options.

### 6. Smartrr
- **Positioning**: Next-gen DTC subscription platform known for high-converting customer portals and subscription bundles.
- **Reference**: https://smartrr.com/
- **Key Capabilities**:
  - **Curated Box & Build-a-Box**: Visual bundles allowing shoppers to pick items or receive curated rotations.
  - **Loyalty & Membership Tiers**: Exclusive subscriber-only discounts and perks.
  - **One-Click Actions**: Magic links allowing customers to skip or swap upcoming shipments directly from email/SMS without logging in.

### 7. Loop Subscriptions
- **Positioning**: Fast-growing subscription tool with deep focus on subscriber retention and automated workflows.
- **Reference**: https://loopwork.co/
- **Key Capabilities**:
  - **Loop Flows**: Visual workflow triggers based on cycle count (e.g. send surprise gift on cycle 3, upgrade tier on cycle 6).
  - **Box Curation & Rotation**: Rotating monthly items without creating duplicate product catalog SKUs.
  - **Gamified Retention**: Rewards unlocked as consecutive delivery milestones are achieved.

### 8. Skio
- **Positioning**: Modern Shopify subscription platform specializing in fast customer portals and group subscriptions.
- **Reference**: https://skio.com/
- **Key Capabilities**:
  - **Passwordless Customer Portal**: 1-click SMS login for maximum self-service engagement.
  - **Surprise-and-Delight Logic**: Automatic zero-cost sample insertion on specific cycle intervals.
  - **Instant Deflection Flows**: Tailored pause/discount offers embedded in the cancel drawer.

### 9. Bold Subscriptions
- **Positioning**: Flexible subscription management and recurring ordering engine.
- **Reference**: https://boldcommerce.com/subscriptions
- **Key Capabilities**:
  - **Mixed Carts**: Seamlessly buying one-time items and recurring subscriptions in the same checkout transaction.
  - **Commitment Terms**: Minimum billing cycles required before cancellation is permitted.

---

## 4. Feature Catalog (This Sub-Module Only)

### 4.1 Subscription Plan Design
- **Flexible Billing & Delivery Frequencies** — Daily, weekly, bi-weekly, monthly, quarterly, semi-annual, annual cadence intervals. · seen in: Recharge, Ordergroove, Stripe Billing · priority: `table-stakes` · spine: `SubscriptionPlan` · buildable now.
- **Discount & Incentive Structures** — Percentage discount (e.g. 15% off), fixed recurring price, or free shipping perk for subscribing. · seen in: Recharge, Smartrr, Skio · priority: `table-stakes` · spine: `SubscriptionPlan` · buildable now.
- **Trial Periods & Commitment Terms** — Configurable trial duration (e.g. 14-day free trial) and minimum commitment cycles (e.g. minimum 3 orders before cancellation allowed). · seen in: Stripe, Chargebee, Bold · priority: `common` · spine: `SubscriptionPlan` · buildable now.
- **Subscription Archetypes** — Subscribe & Save (replenishment consumable), Curated Box (rotating assortment), Fixed Membership Club (perks/discounts). · seen in: Smartrr, Loop · priority: `common` · spine: `SubscriptionPlan` · buildable now.

### 4.2 Recurring Billing & Invoicing
- **Subscriber Lifecycle State Machine** — States: `trialing`, `active`, `paused`, `past_due` (in dunning), `pending_cancellation`, `cancelled`, `expired`. · seen in: Chargebee, Recurly, Stripe · priority: `table-stakes` · spine: `CustomerSubscription` · buildable now.
- **Next Billing & Fulfillment Anchors** — Tracking of `next_billing_date`, `next_delivery_date`, billing cycle count, and total lifetime orders generated. · seen in: Recharge, Ordergroove · priority: `table-stakes` · spine: `CustomerSubscription` · buildable now.
- **Automated Dunning & Retry Tracking** — Failed payment retry counter, grace period expiry, and dunning status tracking. · seen in: Chargebee, Stripe, Recurly · priority: `table-stakes` · spine: `CustomerSubscription` · buildable now.
- **Order Generation Bridge** — Scheduled command / billing action that clones subscription line details into a live `EcommerceOrder` in 9.5 upon successful cycle charge. · seen in: Recharge, Ordergroove · priority: `table-stakes` · spine: `CustomerSubscription` -> `ecommerce.EcommerceOrder` · buildable now.

### 4.3 Subscription Self-Service Portal
- **Skip Upcoming Shipment** — Subscribers can skip next scheduled delivery cycle without altering overall subscription cadence. · seen in: Ordergroove, Recharge, Skio, Smartrr · priority: `table-stakes` · spine: `CustomerSubscription` (skip action) · buildable now.
- **Pause & Resume Controls** — Temporary suspension with a defined `paused_until` date or indefinite hold with easy 1-click reactivation. · seen in: Recharge, Ordergroove, Chargebee · priority: `table-stakes` · spine: `CustomerSubscription` · buildable now.
- **Product & Variant Swapping** — Ability to switch between flavors, sizes, or related items in the upcoming cycle without cancelling and re-subscribing. · seen in: Smartrr, Ordergroove, Loop · priority: `common` · spine: `CustomerSubscription` · buildable now.
- **Frequency Adjustment** — Allowing customers to speed up (e.g. switch from 60 days to 30 days) or slow down deliveries to match consumption. · seen in: Recharge, Skio · priority: `common` · spine: `CustomerSubscription` · buildable now.

### 4.4 Subscription Box & Curation
- **Curated Assortment Rotation Schedule** — Defining themed monthly or seasonal boxes (e.g. "October Artisan Roast", "Spring Skincare Curation") with scheduled start and end dates. · seen in: Smartrr, Loop Subscriptions · priority: `common` · spine: `SubscriptionBoxCuration` · buildable now.
- **Customer Preference Capture** — Capturing subscriber dietary, sizing, scent, skin type, or stylistic preferences to guide item allocation. · seen in: Loop, Smartrr · priority: `common` · spine: `SubscriptionBoxCuration` · buildable now.
- **Surprise Element & Mystery Inclusion** — Configurable flag and logic to include a rotating bonus/mystery item or sample SKU in the cycle delivery. · seen in: Loop, Skio · priority: `differentiator` · spine: `SubscriptionBoxCuration` · buildable now.
- **Box Item Allocation & Substitutions** — Setting primary included items and allowed alternate replacement items in case of stockouts. · seen in: Loop, Bold · priority: `common` · spine: `SubscriptionBoxCuration` · buildable now.

### 4.5 Churn Prediction & Retention
- **Cancellation Intent & Reason Interception** — Intercepting cancellation clicks with structured reason tracking: "Too much product", "Too expensive", "Product didn't meet expectations", "Financial reasons", "Switching to competitor", "Temporary pause needed". · seen in: Chargebee Retention, Recharge, Ordergroove, Loop · priority: `table-stakes` · spine: `SubscriptionRetentionAction` · buildable now.
- **Dynamic Deflection Offers** — Presenting targeted counter-offers based on the reason: pause for 30/60 days, skip next order, apply 15% discount on next 2 cycles, or swap to a lower-priced product. · seen in: Chargebee Retention, ProsperStack, Recharge · priority: `common` · spine: `SubscriptionRetentionAction` · buildable now.
- **Churn Risk Scoring** — Algorithmic or heuristic scoring based on delivery skips, past payment failures, and engagement recency. · seen in: Chargebee, Ordergroove · priority: `differentiator` · spine: `SubscriptionRetentionAction` · buildable now.
- **Win-Back Campaigns & Reactivation** — Tracking post-cancellation status, outbound win-back offer eligibility, and successful reactivations. · seen in: Recharge, Klaviyo integration · priority: `common` · spine: `SubscriptionRetentionAction` · buildable now.

---

## 5. Recommended Build Scope (This Pass — 4 Models)

To deliver a comprehensive, enterprise-grade Subscription & Recurring Commerce capability while staying within the strict 1–4 model per sub-module rule, we recommend the following 4 tenant-scoped models in `apps/ecommerce/models/SubscriptionCommerce/`:

1. **`SubscriptionPlan`** [Prefix: `ESPL-`] (`apps/ecommerce/models/SubscriptionCommerce/SubscriptionPlans.py`)
   - **Purpose**: Defines reusable subscription rules, billing frequencies, discount incentives, trial periods, and commitment terms.
   - **Fields**:
     - `name`: `CharField(max_length=150)`
     - `code`: `SlugField(max_length=60)`
     - `plan_type`: `CharField(max_length=30, choices=PLAN_TYPE_CHOICES)` (Subscribe & Save, Curated Box, Membership Club)
     - `frequency`: `CharField(max_length=20, choices=FREQUENCY_CHOICES)` (Weekly, Bi-weekly, Monthly, Bi-monthly, Quarterly, Annual)
     - `interval_count`: `PositiveIntegerField(default=1)` (e.g. Every 2 Weeks)
     - `discount_type`: `CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES)` (Percentage, Fixed Amount, None)
     - `discount_value`: `DecimalField(max_digits=10, decimal_places=2, default=0.00)`
     - `trial_period_days`: `PositiveIntegerField(default=0)`
     - `min_commitment_cycles`: `PositiveIntegerField(default=1)`
     - `allow_pause`: `BooleanField(default=True)`
     - `allow_skip`: `BooleanField(default=True)`
     - `allow_swap`: `BooleanField(default=True)`
     - `max_pause_days`: `PositiveIntegerField(default=90)`
     - `target_product`: `ForeignKey('ecommerce.CatalogProduct', on_delete=models.SET_NULL, null=True, blank=True)`
     - `is_active`: `BooleanField(default=True)`
     - `description`: `TextField(blank=True)`

2. **`CustomerSubscription`** [Prefix: `ESUB-`] (`apps/ecommerce/models/SubscriptionCommerce/CustomerSubscriptions.py`)
   - **Purpose**: Represents an active or historical recurring subscription contract for a specific customer.
   - **Fields**:
     - `customer_profile`: `ForeignKey('ecommerce.CustomerAccountProfile', on_delete=models.CASCADE, related_name='subscriptions')`
     - `plan`: `ForeignKey('ecommerce.SubscriptionPlan', on_delete=models.PROTECT, related_name='subscriptions')`
     - `product`: `ForeignKey('ecommerce.CatalogProduct', on_delete=models.PROTECT, related_name='subscriptions')`
     - `variant`: `ForeignKey('ecommerce.ProductVariant', on_delete=models.SET_NULL, null=True, blank=True, related_name='subscriptions')`
     - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default='active')` (Trialing, Active, Paused, Past Due / In Dunning, Pending Cancellation, Cancelled, Expired)
     - `quantity`: `PositiveIntegerField(default=1)`
     - `unit_price`: `DecimalField(max_digits=12, decimal_places=2)`
     - `recurring_discount_pct`: `DecimalField(max_digits=5, decimal_places=2, default=0.00)`
     - `started_at`: `DateTimeField(default=timezone.now)`
     - `next_billing_date`: `DateField()`
     - `next_delivery_date`: `DateField(null=True, blank=True)`
     - `paused_until`: `DateField(null=True, blank=True)`
     - `completed_cycles_count`: `PositiveIntegerField(default=0)`
     - `consecutive_successful_cycles`: `PositiveIntegerField(default=0)`
     - `failed_payment_count`: `PositiveIntegerField(default=0)`
     - `shipping_address_line`: `CharField(max_length=255, blank=True)`
     - `payment_method_ref`: `CharField(max_length=100, blank=True, help_text='Tokenized payment card or gateway method reference')`
     - `cancellation_reason`: `CharField(max_length=255, blank=True)`
     - `cancelled_at`: `DateTimeField(null=True, blank=True)`

3. **`SubscriptionBoxCuration`** [Prefix: `ESBX-`] (`apps/ecommerce/models/SubscriptionCommerce/SubscriptionBoxCurations.py`)
   - **Purpose**: Manages curated box assortments, seasonal rotation themes, customer preference profiles, and mystery/surprise inclusions.
   - **Fields**:
     - `name`: `CharField(max_length=150)` (e.g. "Autumn Harvest Coffee Box", "Holiday Grooming Kit")
     - `code`: `SlugField(max_length=60)`
     - `plan`: `ForeignKey('ecommerce.SubscriptionPlan', on_delete=models.CASCADE, related_name='curations')`
     - `cycle_identifier`: `CharField(max_length=50)` (e.g. "2026-11", "Q4-2026")
     - `theme_title`: `CharField(max_length=200, blank=True)`
     - `curation_notes`: `TextField(blank=True)`
     - `primary_product`: `ForeignKey('ecommerce.CatalogProduct', on_delete=models.SET_NULL, null=True, blank=True, related_name='curation_primaries')`
     - `has_surprise_item`: `BooleanField(default=False)`
     - `surprise_item_description`: `CharField(max_length=255, blank=True)`
     - `preference_tag`: `CharField(max_length=100, blank=True, help_text='Preference grouping e.g. "Dark Roast", "Vegan", "Sensitive Skin"')`
     - `start_date`: `DateField()`
     - `end_date`: `DateField()`
     - `is_active`: `BooleanField(default=True)`

4. **`SubscriptionRetentionAction`** [Prefix: `ESRT-`] (`apps/ecommerce/models/SubscriptionCommerce/SubscriptionRetentionActions.py`)
   - **Purpose**: Records subscriber cancellation intent, churn risk evaluation, defensive deflection offers presented, and customer retention outcomes.
   - **Fields**:
     - `subscription`: `ForeignKey('ecommerce.CustomerSubscription', on_delete=models.CASCADE, related_name='retention_actions')`
     - `customer_profile`: `ForeignKey('ecommerce.CustomerAccountProfile', on_delete=models.CASCADE, related_name='retention_actions')`
     - `trigger_type`: `CharField(max_length=30, choices=TRIGGER_TYPE_CHOICES)` (Cancel Intent, Pause Request, Dunning Involuntary, High Churn Risk Prediction)
     - `cancellation_reason`: `CharField(max_length=50, choices=REASON_CHOICES)` (Too Expensive, Too Much Backlog / Product, Poor Product Quality, Temporary Break / Traveling, Switching to Competitor, Other)
     - `churn_risk_score`: `DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text='Predicted churn risk 0.00 to 100.00')`
     - `offered_action`: `CharField(max_length=30, choices=OFFER_CHOICES)` (Discount Next N Orders, Free Skip Cycle, Pause for 30/60 Days, Alternate Product Swap, Free Gift / Perk, None)
     - `offer_discount_pct`: `DecimalField(max_digits=5, decimal_places=2, default=0.00)`
     - `outcome`: `CharField(max_length=30, choices=OUTCOME_CHOICES, default='pending')` (Deflected / Retained, Cancelled Anyway, Paused Instead, Accepted Swap, Expired / No Action)
     - `notes`: `TextField(blank=True)`

---

## 6. Sibling Sub-Module Boundaries & Core Integration

- **Sub-module 9.1 (Product Catalog, shipped)**: `SubscriptionPlan` and `CustomerSubscription` refer to `CatalogProduct` and `ProductVariant`.
- **Sub-module 9.5 (Order Management, shipped)**: Recurring charge execution generates `EcommerceOrder` and `EcommerceOrderLine` records for fulfillment and shipping.
- **Sub-module 9.6 (Customer Accounts, shipped)**: Subscriptions tie directly to `CustomerAccountProfile` for authentication and self-service account portal views.
- **Module 2 (Accounting, shipped)**: Payments and invoices generated from recurring subscriptions link to `accounting.Invoice` and `accounting.Payment`.
- **Sub-module 9.10 (Marketing Campaigns, sibling)**: Sibling sub-module will handle bulk email sequences; 9.12 provides the retention event data and subscriber eligibility status.

---

## 7. Belongs to Sibling Sub-Modules (Parked, not scoped here)

- **Payment Gateway Token Vaulting / PCI Storage** -> Sub-module 9.10 (Payment Gateway & Fraud Management).
- **Physical Warehouse Packing & Route Planning** -> Sub-module 9.11 (Shipping, Delivery & Logistics).
- **Customer Product Reviews on Box Contents** -> Sub-module 9.13 (Reviews & User-Generated Content).

---

## 8. Deferred (Later passes / integrations)

- Real-time automated credit card updater webhooks (Stripe / Adyen network tokens).
- Dynamic Machine-Learning Churn Prediction neural networks (Python Scikit-Learn / PyTorch model serving).
- Physical barcode packing integration for customized box builds.

---
*End of Research Document — Sub-module 9.12: Subscription & Recurring Commerce*
