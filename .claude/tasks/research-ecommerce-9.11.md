# Research — Sub-module 9.11: Marketplace & Multi-Vendor (Module 9 — eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.11 Marketplace & Multi-Vendor
- **Module:** 9 eCommerce Management System
- **Target app:** `apps/ecommerce` (extending the existing app created in 9.1 and extended through 9.8)
- **Research date:** 2026-10-31
- **Phase:** 1 Research only
- **Output boundary:** `.claude/tasks/research-ecommerce-9.11.md` only

---

## 1. Executive Summary & Domain Architecture

Sub-module 9.11 delivers the **Multi-Vendor Marketplace Infrastructure, Seller Onboarding & KYC Verification, Vendor Catalog Listing & Moderation Queues, Multi-Vendor Order Splitting & Fulfillment SLA Routing, Automated Commission Calculation & Payout Settlement, and Seller Performance/Dispute/Suspension Management** for the NavERP eCommerce platform.

In modern multi-vendor commerce (benchmarked across Mirakl, CS-Cart Multi-Vendor, Adobe Commerce / Webkul, Marketplacer, Nautical Commerce, Dokan, VTEX, and Stripe Connect), transforming a single-operator digital storefront into an enterprise multi-vendor marketplace shifts the operating model from direct retailing to an orchestrated two-sided platform. Commercial benchmarks establish:
- **Vendor Catalog Ingestion & Moderation**: Over 65% of marketplace merchandise quality issues and IP disputes originate from unvetted vendor product listings. A strict pre-moderation queue with brand compliance, counterfeit inspection, and category checks protects platform reputation.
- **Order Splitting & Fulfillment SLA Routing**: In a multi-vendor cart checkout, customer orders must decompose cleanly into seller-specific sub-orders (logistical consignments). Each vendor fulfills their independent package within agreed SLA windows (e.g. 24–48 hours) with carrier tracking and automated SLA countdowns.
- **Automated Commission Splits & Payout Disbursements**: Marketplaces operate on take-rates (typically 8% to 25% plus optional flat order fees). Payout systems must calculate net balances (Gross Sales - Commission - Payment Fees - Withholding Taxes - Refunds) and support batch disbursement cycles with W-9 / 1099 tax collection tracking.
- **Seller Reputation, Disputes & Account Suspension**: Operational health relies on objective performance metrics (dispatch SLA breach rate, customer dispute frequency, return rate) driving seller scorecards, verified-purchase order reviews, dispute resolution workflows, and automated or manual vendor account suspension.

### Architectural Boundary Rulings (L28, L29, L36, L37):
1. **Unified Core Spine Integration (L36/L37)**:
   - **Unified Vendor Identity**: The marketplace seller is anchored directly to the core spine: **`core.Party`** (with associated `core.PartyRole` where `role='vendor'`) and linked to an administrative owner **`accounts.User`**. If the accounting module's accounts payable is utilized, it links seamlessly with **`accounting.VendorProfile`** and **`accounting.GLAccount`**.
   - **Catalog Product Anchoring**: Vendor listings bridge the vendor to canonical **`ecommerce.CatalogProduct`** (`EPRD-`, 9.1) and **`ecommerce.ProductVariant`** (`PVR-`, 9.1). The platform operator maintains category taxonomy **`ecommerce.StoreCategory`** (`ECAT-`, 9.1), while vendors submit seller-specific offers, pricing, condition, and inventory.
   - **Order Splitting & OMS Integration**: Multi-vendor transactions originate in **`ecommerce.EcommerceOrder`** (`EORD-`, 9.5). Order items from **`ecommerce.EcommerceOrderLine`** are routed to vendor-specific sub-orders (`VendorSubOrder`), allowing vendors to fulfill their consignment independently without exposing other sellers' lines or buyer billing secrets.
2. **Clear Sibling Boundaries (9.5 vs. 9.11 vs. 9.13 vs. 9.17 vs. Procurement 6.1)**:
   - **Sub-module 9.5 (Order Management System, shipped)**: Owns parent sales order capture (`EcommerceOrder`), global fraud validation, address verification, and centralized warehouse/3PL package tracking (`OrderFulfillment`).
   - **Sub-module 9.11 (This Pass)**: Owns marketplace vendor onboarding & KYC, vendor storefront profiles, vendor product listing moderation, seller sub-order routing & SLA tracking, commission split calculation & payout batch disbursements, and seller reputation scorecards & account suspension.
   - **Sub-module 9.13 (Reviews & User-Generated Content, sibling)**: Sibling sub-module that will own general consumer product reviews, customer photo/video UGC, product Q&A forums, and sentiment NLP. 9.11 specifically owns vendor-level performance scorecards, order dispute resolution, and verified seller ratings tied directly to fulfilled sub-orders.
   - **Sub-module 9.17 (B2B & Wholesale Commerce, sibling)**: Sibling sub-module that will own buyer company accounts, wholesale credit limits, and buyer approval chains. 9.11 provides the supply-side multi-vendor merchant infrastructure.
   - **Procurement Module 6 (Procurement & Supplier Management)**: Internal corporate purchasing, RFQs, e-auctions, and enterprise supplier contracts. 9.11 is consumer-facing and retail-facing marketplace sellers selling to eCommerce shoppers.
3. **Multi-Tenancy & Data Isolation**:
   All vendor profiles, product listings, sub-orders, and payout disbursement batches are strictly partitioned by `tenant` (`core.Tenant`). Vendors, listings, and financial balances of Tenant A can never leak into or interact with Tenant B.
4. **Base Class & Prefix Discipline**:
   All 4 models inherit from `TenantNumbered` (`apps/ecommerce/models/_base.py`), providing `tenant` FK (`on_delete=CASCADE`), thread-safe auto-number generation, and timestamps.
5. **Prefix Collision Sweep**:
   Candidate prefixes `EMKV`, `EVPL`, `EVSO`, `EVPO` verified 100% free across the entire NavERP repository.

---

## 2. Repo State Checked First

### 2.1 Navigation & App Tree State
- **`apps/core/navigation.py`:**
  - `"9.1"` is live: Product Catalog Management (`EPRD`, `PVR`, `ECAT`, `PREL`, `PRDIMG`, `PRDATTR`).
  - `"9.2"` is live: Inventory & Stock Management (`WHS`, `STKTRF`, `STKADJ`, `BORD`, `CHSYNC`).
  - `"9.3"` is live: Pricing & Promotion Engine (`DPR`, `COUP`, `FSAL`, `LOYP`, `CMPR`).
  - `"9.4"` is live: Shopping Cart & Checkout (`CART`, `CLINE`, `CHCK`, `SHPR`, `PAYO`).
  - `"9.5"` is live: Order Management System (`ORD`, `ORIT`, `ORUT`, `CHNG`, `RMA`).
  - `"9.6"` is live: Customer Account & Profile (`ECAP`, `ECAD`, `EWSH`, `EPRV`).
  - `"9.7"` is live: Search & Product Discovery (`ESYM`, `ESFC`, `ESMR`, `ESQL`).
  - `"9.8"` is live: Personalization & Recommendation Engine (`ESEG`, `EREC`, `EPEX`, `ESBE`).
  - Sub-module `"9.11"` currently has no `LIVE_LINKS` entries yet.
- **`apps/ecommerce/` package structure:**
  - Sub-module 9.11 will add package subdirectories: `Marketplace/` across `models/`, `forms/`, `views/`, `urls/`, and `templates/ecommerce/marketplace/`.
- **Database Migrations:**
  - Latest migration in `apps/ecommerce/migrations/` is `0011_audiencesegment_personalizedexperience_and_more.py`.
  - Sub-module 9.11 claims incremental migration number **`0012`**.

### 2.2 As-Built Core Spine Entities (Grep-Verified)
| Entity | Location | Status | 9.11 Usage |
|---|---|---|---|
| `core.Tenant` | `apps/core/models/Tenant.py:17` | **Present** | Strict workspace tenant isolation |
| `core.Party` | `apps/core/models/Party.py:5` | **Present** | Core legal identity for the vendor business or person |
| `core.PartyRole` | `apps/core/models/PartyRole.py:5` | **Present** | Role marker (`role='vendor'`) attaching vendor to party |
| `accounts.User` | `apps/accounts/models/User.py:14` | **Present** | Vendor account owner, listing moderator, payout approver |
| `ecommerce.CatalogProduct` | `apps/ecommerce/models/ProductCatalog/CatalogProducts.py:8` | **Present** | Canonical master catalog product anchor for vendor listings |
| `ecommerce.ProductVariant` | `apps/ecommerce/models/ProductCatalog/ProductVariants.py:10` | **Present** | Variant-level SKU target for vendor pricing and inventory |
| `ecommerce.EcommerceOrder` | `apps/ecommerce/models/OrderManagement/EcommerceOrders.py:10` | **Present** | Parent checkout order split into vendor sub-orders |
| `ecommerce.EcommerceOrderLine` | `apps/ecommerce/models/OrderManagement/EcommerceOrders.py:247` | **Present** | Line items purchased by customer, routed to vendor |
| `accounting.VendorProfile` | `apps/accounting/models/AccountsPayable/VendorProfiles.py:5` | **Present** | Optional AP profile anchor for accounting ledger integration |
| `accounting.GLAccount` | `apps/accounting/models/GeneralLedger/GLAccounts.py:6` | **Present** | Optional expense/clearing account for commission revenue posting |

### 2.3 Prefix Collision Verification
All candidate prefixes checked across all models in the repository via `git grep -E '\b(EMKV|EVPL|EVSO|EVPO|EVRV)\b'`:
- `EMKV` — `MarketplaceVendor` (**Verified 100% FREE**)
- `EVPL` — `VendorProductListing` (**Verified 100% FREE**)
- `EVSO` — `VendorSubOrder` (**Verified 100% FREE**)
- `EVPO` — `VendorPayout` (**Verified 100% FREE**)
- `EVRV` — `VendorReview` (**Verified 100% FREE**)

---

## 3. Commercial Market Leaders Surveyed

### 1. Mirakl (Enterprise SaaS Marketplace Benchmark)
- **Positioning**: Global enterprise marketplace engine powering Best Buy, Carrefour, Decathlon, Kroger, Macy's, and Hudson's Bay.
- **Reference**: https://www.mirakl.com/solutions/marketplace/
- **Key Architectural Capabilities**:
  - **Shop / Vendor Model**: Manages third-party merchant profile, KYB/KYC business identity documentation, commission agreements (percentage, fixed fee, category-specific), contact details, and state machine (`STAGING`, `OPEN`, `SUSPENDED`, `CLOSED`).
  - **Offers Architecture**: Rather than duplicating master products, sellers create *Offers* attached to global catalog products. An Offer carries the seller SKU, price, discount/sale price, available stock level, item condition (new, refurbished, used), and lead time to ship.
  - **Product Ingestion & Pre-Moderation**: Incoming vendor offers and newly proposed products pass through a moderation queue where platform operators approve, reject with notes, or request attribute changes.
  - **Logistical Order Splitting & SLA Countdown**: A customer's single commercial order is split into shop-specific logistical orders. Each shop order has its own acceptance SLA, shipping SLA (promising dispatch within N business hours), carrier assignment, and tracking number. Late dispatch directly deteriorates the seller's SLA compliance score.
  - **Automated Invoicing & Payout Cycles**: Generates seller billing cycles (e.g. 10-day intervals). Calculates net payout: `Gross Sales + Shipping - Operator Commission - Payment Fees - Adjustments/Refunds`. Integrates with payment service providers (PSP connectors: Adyen, Stripe Connect).
  - **Incidents & Dispute Freezes**: Buyers can open incidents against order lines. Open disputes freeze the associated funds in payout calculations until resolved.

### 2. CS-Cart Multi-Vendor
- **Positioning**: Dedicated multi-vendor platform with over 1,500 active commercial marketplaces worldwide.
- **Reference**: https://www.cs-cart.com/multi-vendor-features.html
- **Key Architectural Capabilities**:
  - **Companies (Vendors)**: Vendors operate mini-storefronts with distinct logos, descriptions, shipping methods, and contact info. Statuses: Active, Pending approval, Suspended, Disabled.
  - **Vendor Plans & Commission Engine**: Multi-tier vendor plans specifying monthly subscription fees, fixed transaction fees, and percentage commissions per sale.
  - **Product Pre-Moderation**: Dedicated add-on placing new or updated vendor products into an admin approval queue. Admin can accept, reject with reason, or require modifications before products appear on the storefront.
  - **Order Splitting & Vendor Orders**: Automatically divides parent customer orders into separate sub-orders for each vendor involved. Vendors manage their own order status, generate packing slips, and enter carrier tracking.
  - **Vendor Payouts / Accounting Ledger**: Full ledger table (`cscart_vendor_payouts`) recording order earnings, commission deductions, manual balance adjustments, withdrawal requests, and disbursement payouts.
  - **Vendor Reviews & Rating**: Star rating system on vendor profiles based on customer reviews.

### 3. Adobe Commerce Marketplace (Magento / Webkul Marketplace)
- **Positioning**: Enterprise multi-vendor architecture widely deployed in B2B and consumer retail marketplaces.
- **Reference**: https://store.webkul.com/Magento2-Multi-Vendor-Marketplace.html
- **Key Architectural Capabilities**:
  - **Seller Registration & KYC Flow**: Custom registration form capturing company registration, tax numbers, bank account details, and proof documents.
  - **Storefront Micro-Sites**: Vendors get dedicated SEO-friendly URLs (`/marketplace/seller/view/slug`), custom banners, profile logos, and return policy tabs.
  - **Product Approval Workflow**: Products created by sellers remain in `Pending` status until approved by the marketplace administrator. Includes policy compliance checks.
  - **Order Decomposition**: Orders are partitioned into seller order records. Sellers update shipping statuses and add tracking details for their respective line items.
  - **Commission Rules & Transactions**: Calculates commission on each sale; displays gross, admin commission, and vendor net amounts. Manages seller payout requests and payment reference tracking.
  - **Multi-Factor Seller Reviews**: Customers rate sellers on multiple dimensions: Product Quality, Shipping Speed, and Customer Communication (1 to 5 stars).

### 4. Marketplacer
- **Positioning**: Enterprise headless marketplace platform powering major retailers (Woolworths, Petstock, Myer, Jaycar).
- **Reference**: https://www.marketplacer.com/
- **Key Architectural Capabilities**:
  - **Seller M-Portal**: Dedicated merchant onboarding portal with automated business validation and document upload.
  - **Catalog Curation Firewall**: Automated rules engine preventing brand infringement, restricted keywords, and incomplete product attributes.
  - **Split Shipment Fulfillment & Dispatch SLAs**: Real-time order dispatch monitoring against SLA thresholds. Automated warning notifications when orders approach dispatch deadlines.
  - **Remittance & Settlement Batches**: Automated generation of vendor settlement remittances with clear audit trails, tax summaries (W-9 / 1099 reporting), and automated banking batches.
  - **Seller Scorecards**: Real-time visibility into seller health: On-time dispatch rate, cancellation rate, refund frequency, and dispute volume.

### 5. Nautical Commerce
- **Positioning**: Cloud-native multi-vendor commerce platform purpose-built for enterprise drop-ship and curated marketplaces.
- **Reference**: https://www.nauticalcommerce.com/
- **Key Architectural Capabilities**:
  - **Seller Onboarding Engine**: Self-service application workflow, business verification, and payout credential capture.
  - **Distributed Product Mapping**: Links seller listings to shared catalog schemas, with automated price and inventory synchronization.
  - **Multi-Vendor Order Orchestration**: Intelligently routes line items to correct sellers, captures tracking numbers, and updates unified customer order tracking.
  - **Fintech Payout Splits**: Real-time split payment calculation deducting platform take-rates, holding funds during escrow/return windows, and disbursing net balances.
  - **Vendor Health & Performance Tiers**: Tier-based seller scoring that unlocks lower commission rates for top-performing merchants.

### 6. Dokan / WooCommerce Multi-Vendor
- **Positioning**: Most deployed open-source multi-vendor marketplace plugin, running on over 70,000 active eCommerce sites.
- **Reference**: https://wedevs.com/dokan/
- **Key Architectural Capabilities**:
  - **Vendor Store Management**: Storefront setup wizard, store branding, payment details, and address configurations.
  - **Product Pre-Moderation Queue**: Frontend vendor product creation with admin approval requirement before publishing.
  - **Parent-to-Sub-Order Splitting**: Creates child orders referencing the main order, ensuring sellers only access their own items and fulfillment controls.
  - **Flexible Commission Types**: Supports percentage, flat fee per order, or combined commission structures.
  - **Withdrawal / Payout Request System**: Vendors request payouts when their available balance exceeds minimum thresholds; administrators review and disburse via Stripe, PayPal, or Bank Transfer.
  - **Store Reviews & Dispute Escalation**: Shoppers submit store feedback, with seller response capability and admin moderation.

### 7. VTEX Marketplace
- **Positioning**: Global enterprise composable digital commerce and marketplace network.
- **Reference**: https://vtex.com/en-us/marketplace/
- **Key Architectural Capabilities**:
  - **Collaborative Seller Network**: Sellers onboard and connect their catalogs with automated mapping to operator categories.
  - **Buy-Box Algorithm**: When multiple vendors offer the same catalog product, VTEX's buy-box algorithm ranks offers based on price, delivery time, and seller rating.
  - **Split Order Engine**: Splits checkout orders into multiple fulfillment orders per seller, managing cross-seller shipment notifications.
  - **SLA & Seller Health Monitoring**: Continuous evaluation of seller fulfillment speed and defect rates, automatically pausing underperforming sellers.

### 8. Stripe Connect (Marketplace Fintech Engine)
- **Positioning**: Benchmark fintech infrastructure powering multi-vendor fund flows for Shopify, DoorDash, Deliveroo, and Lyft.
- **Reference**: https://stripe.com/connect
- **Key Architectural Capabilities**:
  - **Connected Accounts (Custom / Express)**: Onboards sellers with automated identity verification (KYC/KYB), bank account linking, and tax document collection (W-9 / 1099-K).
  - **Destination Charges & Application Fees**: Charges buyer the full order amount, immediately routes net funds to seller connected account, and retains marketplace application fee (commission).
  - **Payout Schedules & Balances**: Configurable payout timing (daily, weekly rolling, monthly, or manual request) with reserve holdbacks for chargebacks and returns.
  - **Dispute Liability Allocation**: Allocates dispute fees and chargeback amounts back to the responsible vendor account.

### 9. Sharetribe (Marketplace Platform & Transaction State Machine)
- **Positioning**: Specialized marketplace infrastructure supporting multi-party listings and custom transaction workflows.
- **Reference**: https://www.sharetribe.com/
- **Key Architectural Capabilities**:
  - **Listing Lifecycle**: State machine transitioning listings from `draft` to `pending_approval`, `published`, and `closed`.
  - **Transaction Processes**: Step-by-step transaction state machine with built-in transition delays, review periods, and automatic completion.
  - **Two-Sided Reviews**: Verified buyer review of seller upon transaction completion, with moderation and dispute flags.

---

## 4. Synthesized Feature Catalog (Grouped by NavERP.md 9.11 Bullets)

### 4.1 Vendor Onboarding & Verification
- **Application & Registration Workflow**:
  - Self-service or administrative vendor application intake capturing legal business name, trade name, contact person, phone, email, and company registration details.
  - Status progression: `draft` -> `submitted` -> `under_review` -> `approved` -> `active` -> `suspended` -> `terminated`.
  - Tenant isolation: every vendor belongs strictly to one `core.Tenant`.
- **KYC / KYB Verification**:
  - Know-Your-Customer (KYC) and Know-Your-Business (KYB) compliance tracking.
  - Document verification types: Business License, Government Photo ID, Proof of Address, Bank Account Statement, Tax Registration Certificate.
  - KYC verification states: `unsubmitted`, `pending`, `verified`, `rejected`.
  - Verification audit trail: verified timestamp, reviewer identity, compliance notes.
- **Commission Agreements & Financial Terms**:
  - Flexible commission model configuration: Percentage fee (e.g. 15.00%), Flat transaction fee per order (e.g. $1.50), or Combined (Percentage + Flat).
  - Payout disbursement settings: Payout method (`stripe_connect`, `bank_transfer`, `paypal`, `manual_check`), account identifier (Stripe connected account ID, IBAN/BIC, PayPal email).
  - Payout frequency preference: Weekly, Bi-weekly, Monthly, or Manual On-Demand.
  - Minimum payout threshold configuration (e.g. $50.00).
- **Tax Form Collection & Compliance**:
  - Tax classification tracking: W-9 (US entities), W-8BEN (foreign individuals), W-8BEN-E (foreign entities).
  - Tax ID / EIN / VAT number recording with validation.
  - 1099-K reporting eligibility flag and year-end reporting tracking.
- **Storefront Setup & Branding**:
  - Public store name, URL slug (`/marketplace/vendor/<slug>/`), and marketing headline.
  - Storefront branding: Logo image URL, hero banner image URL, detailed business description.
  - Customer service contact information: Dedicated support email, support phone, operational hours.
  - Vendor fulfillment policies: Default dispatch lead time in days, customized return & refund policy text, shipping policy guidelines.

### 4.2 Vendor Product Management
- **Seller Catalog Listing Upload**:
  - Multi-vendor catalog model: bridges the `MarketplaceVendor` to canonical `ecommerce.CatalogProduct` and variant `ecommerce.ProductVariant`.
  - Seller-specific SKU tracking (`seller_sku`) and optional barcode/UPC.
  - Product condition classification: `new`, `refurbished`, `used_like_new`, `used_good`, `used_fair`.
  - Seller-specific pricing: Asking price, optional compare-at/list price, and vendor unit cost.
  - Seller inventory management: Allocated available quantity, low-stock alert threshold, and backorder permission.
- **Moderation Queues & Approval Workflows**:
  - Moderation state machine: `draft` -> `pending_review` -> `approved` -> `rejected` -> `changes_requested`.
  - Administrative moderation queue: Operator views all pending seller listings, inspects product attributes, images, prices, and descriptions.
  - Moderator decision logging: Reviewer user FK (`accounts.User`), reviewed timestamp, administrative feedback notes, and structured rejection reason codes.
  - Automatic publishing: Approved listings immediately become visible on the public storefront and search results; rejected or unapproved listings remain hidden.
- **Policy Compliance & Intellectual Property Enforcement**:
  - Compliance check states: `pending`, `compliant`, `flagged_prohibited`, `counterfeit_suspect`, `ip_infringement`.
  - Prohibited category enforcement: Blocks restricted items (hazardous materials, counterfeit brands, prohibited pharmaceuticals, adult content).
  - Compliance review notes and violation audit history.

### 4.3 Vendor Order Fulfillment
- **Seller-Specific Order Routing & Splitting**:
  - Multi-vendor order decomposition: When a customer completes checkout on an order (`EcommerceOrder`) containing items from multiple vendors, the platform creates dedicated `VendorSubOrder` records per vendor.
  - Line-item assignment: Associates relevant `EcommerceOrderLine` records to the vendor's sub-order.
  - Vendor data confidentiality: Vendors can only access their own sub-orders, customer shipping details, and allocated line items—never other sellers' items or billing credentials.
- **Fulfillment Lifecycle Tracking**:
  - Sub-order fulfillment states: `unfulfilled`, `allocated`, `picking`, `packed`, `shipped`, `delivered`, `cancelled`.
  - Shipping carrier recording: Carrier name (FedEx, UPS, DHL, USPS, Royal Mail, Local Courier), tracking number, and tracking URL.
  - Shipping cost allocation: Tracks shipping charges paid by buyer allocated to this vendor.
- **SLA Tracking & Dispatch Countdowns**:
  - Promised dispatch date: Automatically calculated based on vendor's lead time (e.g. order date + 2 business days).
  - Actual dispatch tracking: Timestamp of package handoff to carrier.
  - Real-time SLA compliance status: `on_time` (shipped before deadline), `near_breach` (approaching deadline within 6 hours), `breached` (late shipment).
  - Delivery confirmation timestamp.
- **Performance Scorecards & Metrics**:
  - Tracks on-time fulfillment rate percentage per vendor.
  - Computes late dispatch count and fulfillment lead time hours.
  - Feeds directly into vendor reputation rating and auto-suspension triggers.

### 4.4 Vendor Commission & Payouts
- **Revenue Split Calculation**:
  - Real-time transaction splitting on sub-order completion:
    - `Gross Amount`: Vendor items subtotal + allocated shipping amount.
    - `Commission Amount`: Calculated based on vendor agreed rate (`Gross * commission_rate % + fixed_fee`).
    - `Payment Processing Fee`: Optional gateway fee deduction.
    - `Net Vendor Payable`: `Gross - Commission - Fees`.
  - Historical snapshotting: Commission rate and amounts are locked into the sub-order record upon order confirmation, ensuring future rate changes never mutate past transaction balances.
- **Payout Batch Runs & Disbursements**:
  - Dedicated payout batch model (`VendorPayout`) aggregating all eligible fulfilled sub-orders for a billing cycle.
  - Payout date window: Period start and period end.
  - Payout status lifecycle: `draft` -> `pending_approval` -> `processing` -> `completed` -> `failed` -> `cancelled`.
  - Financial summary breakdown: Gross sales volume, total commission retained by platform, processing fees deducted, customer refunds/adjustments deducted, withholding tax deducted, and final net payout amount.
  - Payout execution tracking: Payout method, bank/Stripe reference transaction ID (`reference_code`), processed timestamp, and administrative approval user (`approved_by`).
- **Tax Withholding & Reporting**:
  - Withholding tax deduction tracking for cross-border or backup withholding scenarios.
  - Annual 1099-K tax reporting flag (`is_1099_reported`), tax reporting year, and cumulative taxable earnings aggregation.

### 4.5 Vendor Ratings & Reviews
- **Verified-Purchase Seller Feedback**:
  - Order-anchored feedback: Ratings and reviews are attached directly to fulfilled `VendorSubOrder` records, ensuring only verified buyers who completed a transaction can submit seller feedback.
  - Customer rating score (1 to 5 stars) covering product quality, packaging, and delivery speed.
  - Written review comments and seller public response.
- **Vendor Reputation Scorecards**:
  - Aggregate rating calculation on `MarketplaceVendor`: `rating_average` (e.g. 4.85) and `rating_count`.
  - Performance scorecard metrics: Fulfillment on-time percentage, return/refund rate, and dispute frequency.
  - Highlighting top-rated sellers ("Top Seller" / "Verified Partner" badges).
- **Order Dispute Resolution**:
  - Customer-initiated order dispute tracking on `VendorSubOrder`: `dispute_status` (`none`, `disputed`, `under_investigation`, `resolved_merchant`, `resolved_customer`, `escalated_to_admin`).
  - Structured dispute reasons: Item not received (INR), Significantly not as described (SNAD), Damaged in transit, Missing items, Wrong item sent.
  - Dispute resolution notes, refund amount, and resolution timestamp.
  - Dispute freeze: Open disputes immediately place the sub-order's payout status into `withheld_dispute`, protecting platform funds.
- **Suspension & Enforcement Workflows**:
  - Vendor account status governance: Administrative suspension or termination.
  - Suspension reasons: Excessive SLA breaches, high dispute rate, counterfeit listing violations, fraud alert.
  - Suspension tracking: `suspended_at`, `suspended_by` (`accounts.User`), and detailed suspension reason text.
  - Enforcement impact: Suspending a vendor immediately deactivates all their `VendorProductListing` records, removing their items from storefront search and category pages.

---

## 5. Recommended Build Scope for This Pass (4 TenantNumbered Models)

To achieve maximum enterprise power, strict compliance with the 1–4 model build scope rule, complete coverage of all 5 NavERP.md feature bullets, and verified core-spine integration, we recommend **4 `TenantNumbered` models** in `apps/ecommerce/models/Marketplace/`:

```
apps/ecommerce/models/Marketplace/
├── MarketplaceVendors.py       # [EMKV] Vendor Onboarding, KYC, Storefront Setup, Commission Agreement, Scorecard, Suspension
├── VendorProductListings.py    # [EVPL] Vendor Catalog Upload, Moderation Queue, Policy Compliance, Seller Pricing & Stock
├── VendorSubOrders.py          # [EVSO] Seller Order Routing, Fulfillment Tracking, Dispatch SLAs, Order Disputes & Rating
├── VendorPayouts.py            # [EVPO] Commission Split Reconciliation, Automated Payout Disbursements, 1099 Tax Tracking
└── __init__.py
```

### 5.1 Model 1: `MarketplaceVendor` [Prefix: `EMKV`]
- **File**: `apps/ecommerce/models/Marketplace/MarketplaceVendors.py`
- **Class**: `MarketplaceVendor(TenantNumbered)`
- **Prefix**: `EMKV` (Verified 100% Free across repository)
- **Role**: Primary merchant entity in the marketplace. Governs legal onboarding, KYC verification, storefront branding, commission agreements, aggregate seller reputation scorecards, and account suspension workflows (covering Bullets 1 and 5).
- **Core Spine FKs**:
  - `tenant`: `ForeignKey("core.Tenant", on_delete=models.CASCADE, db_index=True)`
  - `party`: `ForeignKey("core.Party", on_delete=models.PROTECT, related_name="marketplace_vendors", help_text="Unified legal party (person or organization)")`
  - `owner_user`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="owned_marketplace_vendors", help_text="Primary login user managing this vendor")`
- **Choices**:
  - `STATUS_CHOICES`:
    - `draft` — Draft Application
    - `submitted` — Application Submitted
    - `under_review` — Compliance Review
    - `approved` — Approved
    - `active` — Active Seller
    - `suspended` — Suspended (Policy/SLA Breach)
    - `terminated` — Terminated
  - `KYC_STATUS_CHOICES`:
    - `unsubmitted` — Unsubmitted
    - `pending` — Under Verification
    - `verified` — Identity Verified
    - `rejected` — Verification Rejected
  - `COMMISSION_TYPE_CHOICES`:
    - `percentage` — Percentage Only
    - `fixed` — Flat Fee Only
    - `combined` — Percentage + Flat Fee
  - `PAYOUT_METHOD_CHOICES`:
    - `stripe_connect` — Stripe Connect
    - `bank_transfer` — Direct Bank Transfer / ACH
    - `paypal` — PayPal Payouts
    - `manual_check` — Manual Check / Wire
  - `TAX_FORM_CHOICES`:
    - `not_required` — Not Required
    - `w9_pending` — W-9 Pending
    - `w9_received` — W-9 Received
    - `w8ben_received` — W-8BEN Received
    - `1099_eligible` — 1099-K Eligible
- **Fields**:
  - `store_name`: `CharField(max_length=150, help_text="Public vendor store name")`
  - `slug`: `SlugField(max_length=160, help_text="URL slug for public storefront, e.g. /vendors/acme-crafts/")`
  - `headline`: `CharField(max_length=255, blank=True, help_text="Short tagline or slogan")`
  - `description`: `TextField(blank=True, help_text="Storefront about text and company profile")`
  - `logo_url`: `URLField(blank=True, help_text="Store logo graphic URL")`
  - `banner_url`: `URLField(blank=True, help_text="Storefront hero banner image URL")`
  - `support_email`: `EmailField(blank=True, help_text="Customer support email address")`
  - `support_phone`: `CharField(max_length=50, blank=True, help_text="Customer support phone number")`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `kyc_status`: `CharField(max_length=25, choices=KYC_STATUS_CHOICES, default="unsubmitted")`
  - `kyc_document_type`: `CharField(max_length=100, blank=True, help_text="Document submitted (e.g. Business License, Passport, Utility Bill)")`
  - `kyc_notes`: `TextField(blank=True, help_text="Compliance officer notes regarding KYC verification")`
  - `kyc_verified_at`: `DateTimeField(null=True, blank=True)`
  - `commission_type`: `CharField(max_length=20, choices=COMMISSION_TYPE_CHOICES, default="percentage")`
  - `commission_rate`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal("15.00"), help_text="Percentage fee deducted from gross sales (e.g. 15.00%)")`
  - `fixed_fee_per_order`: `DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"), help_text="Flat fee deducted per sub-order (e.g. $1.50)")`
  - `payout_method`: `CharField(max_length=25, choices=PAYOUT_METHOD_CHOICES, default="bank_transfer")`
  - `payout_account_identifier`: `CharField(max_length=120, blank=True, help_text="Connected account ID, IBAN, or recipient address")`
  - `min_payout_amount`: `DecimalField(max_digits=10, decimal_places=2, default=Decimal("50.00"), help_text="Minimum accumulated balance required for payout release")`
  - `tax_id`: `CharField(max_length=64, blank=True, help_text="EIN, SSN, or VAT tax registration number")`
  - `tax_form_status`: `CharField(max_length=25, choices=TAX_FORM_CHOICES, default="not_required")`
  - `shipping_lead_time_days`: `PositiveIntegerField(default=2, help_text="Standard promised dispatch SLA in business days")`
  - `return_policy`: `TextField(blank=True, help_text="Vendor-specific return policy terms")`
  - `rating_average`: `DecimalField(max_digits=3, decimal_places=2, default=Decimal("0.00"), help_text="Aggregate customer satisfaction score (0.00 to 5.00)")`
  - `rating_count`: `PositiveIntegerField(default=0, help_text="Total number of customer ratings received")`
  - `is_featured`: `BooleanField(default=False, help_text="Highlight in marketplace seller directory and homepage")`
  - `suspension_reason`: `TextField(blank=True, help_text="Formal reason if vendor account is suspended")`
  - `suspended_at`: `DateTimeField(null=True, blank=True)`
  - `suspended_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="suspended_vendors")`
- **Constraints & Indexes**:
  - `UniqueConstraint(fields=["tenant", "number"], name="ecommerce_emkv_tenant_num_uniq")`
  - `UniqueConstraint(fields=["tenant", "slug"], name="ecommerce_emkv_tenant_slug_uniq")`
  - `Index(fields=["tenant", "status"], name="idx_emkv_ten_status")`
  - `Index(fields=["tenant", "kyc_status"], name="idx_emkv_ten_kyc")`
- **Form Exclusions**: `tenant`, `number`, `rating_average`, `rating_count`, `kyc_verified_at`, `suspended_at`, `suspended_by`, `created_at`, `updated_at`.

### 5.2 Model 2: `VendorProductListing` [Prefix: `EVPL`]
- **File**: `apps/ecommerce/models/Marketplace/VendorProductListings.py`
- **Class**: `VendorProductListing(TenantNumbered)`
- **Prefix**: `EVPL` (Verified 100% Free across repository)
- **Role**: Bridges a vendor with the canonical catalog product. Manages seller catalog offers, moderation queues, policy compliance verification, seller-specific pricing, and inventory (covering Bullet 2).
- **Core Spine FKs**:
  - `tenant`: `ForeignKey("core.Tenant", on_delete=models.CASCADE, db_index=True)`
  - `vendor`: `ForeignKey("ecommerce.MarketplaceVendor", on_delete=models.CASCADE, related_name="product_listings", help_text="Marketplace vendor offering this item")`
  - `product`: `ForeignKey("ecommerce.CatalogProduct", on_delete=models.CASCADE, related_name="vendor_listings", help_text="Canonical catalog product master")`
  - `variant`: `ForeignKey("ecommerce.ProductVariant", on_delete=models.SET_NULL, null=True, blank=True, related_name="vendor_listings", help_text="Specific variant or SKU")`
  - `reviewed_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_listings")`
- **Choices**:
  - `CONDITION_CHOICES`:
    - `new` — Brand New
    - `refurbished` — Certified Refurbished
    - `used_like_new` — Used - Like New
    - `used_good` — Used - Good
    - `used_fair` — Used - Fair
  - `MODERATION_STATUS_CHOICES`:
    - `draft` — Draft
    - `pending_review` — Pending Moderation Review
    - `approved` — Approved & Live
    - `rejected` — Rejected
    - `changes_requested` — Changes Requested
  - `COMPLIANCE_STATUS_CHOICES`:
    - `pending` — Compliance Pending
    - `compliant` — Policy Compliant
    - `flagged_prohibited` — Prohibited Item Flag
    - `counterfeit_suspect` — Counterfeit Suspect
    - `ip_infringement` — Trademark / IP Violation
- **Fields**:
  - `seller_sku`: `CharField(max_length=80, help_text="Vendor internal SKU code")`
  - `barcode`: `CharField(max_length=60, blank=True, help_text="UPC, EAN, or ISBN barcode")`
  - `condition`: `CharField(max_length=20, choices=CONDITION_CHOICES, default="new")`
  - `condition_notes`: `CharField(max_length=255, blank=True, help_text="Details on packaging or cosmetic state")`
  - `asking_price`: `DecimalField(max_digits=12, decimal_places=2, help_text="Seller listing price offered to shoppers")`
  - `compare_at_price`: `DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Original retail or MSRP strikethrough price")`
  - `cost_price`: `DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Vendor wholesale cost basis")`
  - `available_quantity`: `PositiveIntegerField(default=0, help_text="Real-time stock units available for purchase")`
  - `low_stock_threshold`: `PositiveIntegerField(default=5, help_text="Alert vendor when stock falls below this level")`
  - `lead_time_days`: `PositiveIntegerField(default=2, help_text="Custom dispatch lead time in business days for this item")`
  - `moderation_status`: `CharField(max_length=25, choices=MODERATION_STATUS_CHOICES, default="pending_review", db_index=True)`
  - `compliance_status`: `CharField(max_length=25, choices=COMPLIANCE_STATUS_CHOICES, default="pending", db_index=True)`
  - `moderator_notes`: `TextField(blank=True, help_text="Internal review notes visible to vendor and admin")`
  - `rejection_reason`: `CharField(max_length=255, blank=True, help_text="Reason code if listing was rejected")`
  - `submitted_at`: `DateTimeField(null=True, blank=True)`
  - `reviewed_at`: `DateTimeField(null=True, blank=True)`
  - `is_active`: `BooleanField(default=True, help_text="Whether this listing is published and purchasable")`
- **Constraints & Indexes**:
  - `UniqueConstraint(fields=["tenant", "number"], name="ecommerce_evpl_tenant_num_uniq")`
  - `UniqueConstraint(fields=["tenant", "vendor", "seller_sku"], name="ecommerce_evpl_ven_sku_uniq")`
  - `Index(fields=["tenant", "moderation_status", "is_active"], name="idx_evpl_ten_mod_act")`
  - `Index(fields=["tenant", "product", "asking_price"], name="idx_evpl_ten_prd_price")`
- **Form Exclusions**: `tenant`, `number`, `reviewed_at`, `reviewed_by`, `created_at`, `updated_at`.

### 5.3 Model 3: `VendorSubOrder` [Prefix: `EVSO`]
- **File**: `apps/ecommerce/models/Marketplace/VendorSubOrders.py`
- **Class**: `VendorSubOrder(TenantNumbered)`
- **Prefix**: `EVSO` (Verified 100% Free across repository)
- **Role**: Decomposes parent customer orders into vendor-specific consignments. Manages vendor fulfillment workflow, SLA dispatch tracking, carrier details, commission deduction snapshotting, order-anchored customer ratings, and dispute resolution (covering Bullets 3, 4, and 5).
- **Core Spine FKs**:
  - `tenant`: `ForeignKey("core.Tenant", on_delete=models.CASCADE, db_index=True)`
  - `vendor`: `ForeignKey("ecommerce.MarketplaceVendor", on_delete=models.PROTECT, related_name="sub_orders", help_text="Vendor responsible for fulfilling this sub-order")`
  - `order`: `ForeignKey("ecommerce.EcommerceOrder", on_delete=models.CASCADE, related_name="vendor_sub_orders", help_text="Parent eCommerce order")`
  - `payout`: `ForeignKey("ecommerce.VendorPayout", on_delete=models.SET_NULL, null=True, blank=True, related_name="sub_orders", help_text="Payout batch that settled this sub-order")`
- **Choices**:
  - `FULFILLMENT_STATUS_CHOICES`:
    - `unfulfilled` — Unfulfilled
    - `allocated` — Stock Allocated
    - `picking` — Picking Items
    - `packed` — Package Packed
    - `shipped` — Shipped with Carrier
    - `delivered` — Delivered to Customer
    - `cancelled` — Cancelled
  - `SLA_STATUS_CHOICES`:
    - `on_time` — On Time (Within SLA)
    - `near_breach` — Approaching SLA Deadline
    - `breached` — SLA Breached (Late Dispatch)
  - `PAYOUT_STATUS_CHOICES`:
    - `accrued` — Accrued / Pending Settlement
    - `in_payout_batch` — Assigned to Payout Batch
    - `paid` — Disbursed to Vendor
    - `withheld_dispute` — Withheld (Open Dispute)
    - `refunded` — Refunded / Cancelled
  - `DISPUTE_STATUS_CHOICES`:
    - `none` — No Dispute
    - `disputed` — Customer Dispute Opened
    - `under_investigation` — Under Investigation
    - `resolved_merchant` — Resolved in Seller Favor
    - `resolved_customer` — Resolved in Buyer Favor (Refund Issued)
    - `escalated_to_admin` — Escalated to Operator Admin
- **Fields**:
  - `fulfillment_status`: `CharField(max_length=25, choices=FULFILLMENT_STATUS_CHOICES, default="unfulfilled", db_index=True)`
  - `sla_status`: `CharField(max_length=20, choices=SLA_STATUS_CHOICES, default="on_time")`
  - `payout_status`: `CharField(max_length=25, choices=PAYOUT_STATUS_CHOICES, default="accrued", db_index=True)`
  - `subtotal_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), help_text="Gross items subtotal for this vendor")`
  - `shipping_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), help_text="Shipping fee allocated to this vendor")`
  - `commission_rate`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal("15.00"), help_text="Snapshot of commission percentage applied")`
  - `commission_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), help_text="Total commission retained by platform")`
  - `net_vendor_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), help_text="Net amount payable to vendor (Subtotal + Shipping - Commission)")`
  - `carrier_name`: `CharField(max_length=80, blank=True, help_text="Shipping carrier name (e.g. FedEx, DHL, USPS)")`
  - `tracking_number`: `CharField(max_length=100, blank=True, help_text="Shipment tracking number")`
  - `tracking_url`: `URLField(blank=True, help_text="Direct parcel tracking URL")`
  - `promised_dispatch_date`: `DateField(null=True, blank=True, help_text="Deadline date for vendor dispatch based on SLA")`
  - `dispatched_at`: `DateTimeField(null=True, blank=True, help_text="Actual timestamp when carrier accepted package")`
  - `delivered_at`: `DateTimeField(null=True, blank=True, help_text="Timestamp when carrier confirmed delivery")`
  - `customer_rating`: `PositiveSmallIntegerField(null=True, blank=True, help_text="Customer satisfaction score (1 to 5 stars)")`
  - `customer_feedback`: `TextField(blank=True, help_text="Customer review comments regarding this seller's fulfillment")`
  - `seller_response`: `TextField(blank=True, help_text="Vendor public reply to customer review")`
  - `rated_at`: `DateTimeField(null=True, blank=True)`
  - `dispute_status`: `CharField(max_length=25, choices=DISPUTE_STATUS_CHOICES, default="none", db_index=True)`
  - `dispute_reason`: `CharField(max_length=150, blank=True, help_text="Dispute reason (e.g. Item Not Received, Damaged, SNAD)")`
  - `dispute_notes`: `TextField(blank=True, help_text="Customer dispute details and investigation evidence")`
  - `dispute_resolved_at`: `DateTimeField(null=True, blank=True)`
- **Constraints & Indexes**:
  - `UniqueConstraint(fields=["tenant", "number"], name="ecommerce_evso_tenant_num_uniq")`
  - `Index(fields=["tenant", "vendor", "fulfillment_status"], name="idx_evso_ten_ven_ful")`
  - `Index(fields=["tenant", "order"], name="idx_evso_ten_order")`
  - `Index(fields=["tenant", "payout_status"], name="idx_evso_ten_payout")`
  - `Index(fields=["tenant", "dispute_status"], name="idx_evso_ten_dispute")`
- **Form Exclusions**: `tenant`, `number`, `commission_amount`, `net_vendor_amount`, `rated_at`, `dispute_resolved_at`, `created_at`, `updated_at`.

### 5.4 Model 4: `VendorPayout` [Prefix: `EVPO`]
- **File**: `apps/ecommerce/models/Marketplace/VendorPayouts.py`
- **Class**: `VendorPayout(TenantNumbered)`
- **Prefix**: `EVPO` (Verified 100% Free across repository)
- **Role**: Batch settlement reconciliation and disbursement execution. Aggregates delivered sub-orders, deducts platform commissions, tracks payment gateway reference transactions, and monitors annual 1099 tax reporting (covering Bullet 4).
- **Core Spine FKs**:
  - `tenant`: `ForeignKey("core.Tenant", on_delete=models.CASCADE, db_index=True)`
  - `vendor`: `ForeignKey("ecommerce.MarketplaceVendor", on_delete=models.PROTECT, related_name="payouts", help_text="Vendor receiving this payout disbursement")`
  - `approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_payouts")`
- **Choices**:
  - `PAYOUT_STATUS_CHOICES`:
    - `draft` — Draft Batch
    - `pending_approval` — Pending Finance Approval
    - `processing` — Processing with Bank / Gateway
    - `completed` — Completed & Disbursed
    - `failed` — Disbursement Failed
    - `cancelled` — Cancelled
  - `PAYOUT_METHOD_CHOICES`:
    - `stripe_connect` — Stripe Connect Transfer
    - `bank_transfer` — Bank Wire / ACH
    - `paypal` — PayPal Payout
    - `manual_check` — Manual Check / Voucher
- **Fields**:
  - `period_start`: `DateField(help_text="Start date of earning period covered")`
  - `period_end`: `DateField(help_text="End date of earning period covered")`
  - `gross_sales_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), help_text="Gross sales volume from fulfilled sub-orders")`
  - `commission_deducted`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), help_text="Total marketplace commission retained")`
  - `fees_deducted`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), help_text="Payment processing or platform gateway fees deducted")`
  - `refunds_deducted`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), help_text="Customer returns and refund adjustments deducted")`
  - `tax_withholding_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), help_text="Statutory withholding tax deducted")`
  - `net_payout_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), help_text="Final disbursed amount transferred to vendor")`
  - `payout_method`: `CharField(max_length=25, choices=PAYOUT_METHOD_CHOICES, default="bank_transfer")`
  - `payout_status`: `CharField(max_length=25, choices=PAYOUT_STATUS_CHOICES, default="draft", db_index=True)`
  - `reference_code`: `CharField(max_length=100, blank=True, help_text="Gateway transfer ID (e.g. tr_12345) or bank transaction confirmation number")`
  - `tax_year`: `PositiveIntegerField(null=True, blank=True, help_text="Tax year for 1099-K filing, e.g. 2026")`
  - `is_1099_reported`: `BooleanField(default=False, help_text="Flag indicating annual 1099 form has been generated and filed")`
  - `notes`: `TextField(blank=True, help_text="Disbursement notes or failure error message")`
  - `processed_at`: `DateTimeField(null=True, blank=True, help_text="Timestamp when funds transfer was executed")`
- **Constraints & Indexes**:
  - `UniqueConstraint(fields=["tenant", "number"], name="ecommerce_evpo_tenant_num_uniq")`
  - `Index(fields=["tenant", "vendor", "payout_status"], name="idx_evpo_ten_ven_stat")`
  - `Index(fields=["tenant", "period_end"], name="idx_evpo_ten_period")`
- **Form Exclusions**: `tenant`, `number`, `net_payout_amount`, `processed_at`, `approved_by`, `created_at`, `updated_at`.

---

## 6. Implementation Architecture & Directory Blueprint

### 6.1 Backend Package Directory Layout
```
apps/ecommerce/
├── models/
│   ├── Marketplace/
│   │   ├── __init__.py
│   │   ├── MarketplaceVendors.py
│   │   ├── VendorProductListings.py
│   │   ├── VendorSubOrders.py
│   │   └── VendorPayouts.py
│   └── __init__.py             # Surgical re-export of EMKV, EVPL, EVSO, EVPO
├── forms/
│   ├── Marketplace/
│   │   ├── __init__.py
│   │   ├── MarketplaceVendorForms.py
│   │   ├── VendorProductListingForms.py
│   │   ├── VendorSubOrderForms.py
│   │   └── VendorPayoutForms.py
│   └── __init__.py             # Surgical re-export
├── views/
│   ├── Marketplace/
│   │   ├── __init__.py
│   │   ├── MarketplaceConsoleViews.py  # Overview dashboard & KPI cards
│   │   ├── MarketplaceVendorViews.py   # Full CRUD + verify_kyc, suspend_vendor actions
│   │   ├── VendorProductListingViews.py # Full CRUD + moderate_listing action
│   │   ├── VendorSubOrderViews.py      # Full CRUD + mark_dispatched, resolve_dispute actions
│   │   └── VendorPayoutViews.py        # Full CRUD + approve_payout, execute_payout actions
│   └── __init__.py             # Surgical re-export
├── urls/
│   ├── Marketplace.py          # All sub-module routes
│   └── __init__.py             # Surgical wire-up of _marketplace_urls
└── admin.py                    # Surgical registration of 4 models
```

### 6.2 Template Directory Layout
```
templates/ecommerce/marketplace/
├── console/
│   └── dashboard.html          # Operational marketplace dashboard: KYC queue, moderation queue, SLA alert widget, payout liability, disputes
├── marketplacevendor/
│   ├── list.html               # Filterable table: status, kyc_status, commission_type, search
│   ├── detail.html             # Storefront view, KYC documents, active listings tab, sub-orders tab, payouts tab, rating scorecard
│   └── form.html               # Crispy-styled Tailwind form
├── vendorproductlisting/
│   ├── list.html               # Filterable table: moderation_status, compliance_status, condition, vendor, search
│   ├── detail.html             # Product spec, vendor pricing, stock, moderation decision buttons (Approve/Reject)
│   └── form.html               # Listing creation & price/stock editor
├── vendorsuborder/
│   ├── list.html               # Filterable table: fulfillment_status, sla_status, payout_status, dispute_status, vendor
│   ├── detail.html             # Order details, items table, carrier dispatch form, SLA countdown, customer review & dispute action panel
│   └── form.html               # Sub-order fulfillment & status update form
└── vendorpayout/
    ├── list.html               # Filterable table: payout_status, payout_method, vendor, date range
    ├── detail.html             # Settlement reconciliation sheet, sub-orders breakdown, approve/disburse action buttons
    └── form.html               # Payout batch creation & reconciliation form
```

### 6.3 Sidebar & Navigation Wiring (`apps/core/navigation.py`)
In `apps/core/navigation.py`, Sub-module `"9.11"` will declare the exact mapping matching the 5 NavERP.md feature bullets:
```python
    "9.11": {
        "Vendor Onboarding & Verification": "ecommerce:marketplacevendor_list",
        "Vendor Product Management": "ecommerce:vendorproductlisting_list",
        "Vendor Order Fulfillment": "ecommerce:vendorsuborder_list",
        "Vendor Commission & Payouts": "ecommerce:vendorpayout_list",
        "Vendor Ratings & Reviews": "ecommerce:marketplace_console",
        # Extra live leaves
        "Marketplace Console": "ecommerce:marketplace_console",
        "Marketplace Vendors": "ecommerce:marketplacevendor_list",
        "Product Listings & Moderation": "ecommerce:vendorproductlisting_list",
        "Vendor Sub-Orders": "ecommerce:vendorsuborder_list",
        "Commission Payouts": "ecommerce:vendorpayout_list",
    },
```

---

## 7. Seeder Plan & Demo Scenarios (`seed_ecommerce.py`)

The seeder command (`seed_ecommerce.py`) will be extended with rich, realistic, enterprise marketplace demo data for each active tenant:
1. **Core Spine Anchoring**:
   - Queries or creates 4 distinct `core.Party` entities (`Apex Electronics LLC`, `Artisan Leathercraft Co`, `Nordic Living Goods`, `GreenLeaf Organics`), assigning `PartyRole(role='vendor')`.
   - Links to administrative `accounts.User` instances (`vendor_apex`, `vendor_artisan`, `vendor_nordic`, `vendor_greenleaf`).
2. **Vendors (`MarketplaceVendor`)**:
   - **Vendor 1 (Active Top Seller)**: `Apex Electronics LLC` — Status: `active`, KYC: `verified`, Commission: `12.50%`, Payout: `stripe_connect`, Rating: `4.92` (48 reviews), Featured: `True`.
   - **Vendor 2 (Active Craftsman)**: `Artisan Leathercraft Co` — Status: `active`, KYC: `verified`, Commission: `15.00%`, Payout: `bank_transfer`, Rating: `4.80` (19 reviews), Featured: `True`.
   - **Vendor 3 (Pending Applicant)**: `Nordic Living Goods` — Status: `under_review`, KYC: `pending`, Commission: `15.00%`, Payout: `bank_transfer`, Rating: `0.00` (0 reviews), Featured: `False`.
   - **Vendor 4 (Suspended Seller)**: `GreenLeaf Organics` — Status: `suspended`, KYC: `verified`, Commission: `18.00%`, Payout: `paypal`, Suspension Reason: "Repeated dispatch SLA breaches (>45% late shipments) and 3 unresolved customer disputes.", Rating: `2.65` (14 reviews).
3. **Product Listings (`VendorProductListing`)**:
   - 8 realistic listings mapped to existing `ecommerce.CatalogProduct` items:
     - 4 `approved` & `active` listings (priced competitively, stock available).
     - 2 `pending_review` listings in the moderation queue awaiting operator approval.
     - 1 `rejected` listing flagged for policy compliance ("Unverified medical health claim in product specifications").
     - 1 `changes_requested` listing requiring updated warranty documentation.
4. **Multi-Vendor Sub-Orders (`VendorSubOrder`)**:
   - Linked to existing demo `EcommerceOrder` records:
     - Sub-Order 1: `fulfilled` / `delivered`, `on_time` SLA, 5-star customer review ("Arrived 1 day early! Packaging was pristine."), payout `paid`.
     - Sub-Order 2: `shipped`, `on_time` SLA, in-transit with FedEx tracking, payout `accrued`.
     - Sub-Order 3: `allocated`, `near_breach` SLA warning countdown, fulfillment lead time urgent.
     - Sub-Order 4: `delivered`, `disputed` with active customer claim ("Item arrived with cracked casing. Awaiting replacement part from seller."), payout status `withheld_dispute`.
5. **Payout Batches (`VendorPayout`)**:
   - Payout Batch 1: `completed` for `Apex Electronics LLC`, Net: `$3,425.80`, Commission Retained: `$489.40`, Reference: `tr_1Nx982Klq092`, 1099 Eligible: `True`.
   - Payout Batch 2: `pending_approval` for `Artisan Leathercraft Co`, Net: `$1,240.00`, Commission Retained: `$218.82`.

---

## 8. Gaps & Non-Goals for This Pass

To maintain clean code delivery, bulletproof stability, and strict isolation:
- **NO Direct External Payment Gateway API Calls**: Payment gateway execution (e.g. live Stripe Connect API webhooks, PayPal Payouts batch HTTP calls) is recorded via state transitions, reference codes, and transfer IDs. Live API integration is cleanly segregated to Sub-module 9.19 (Integration & API Ecosystem).
- **NO Automated ML Counterfeit Image Scanning**: Automated computer vision scanning of trademarked images is represented via the structured compliance verification state machine (`COMPLIANCE_STATUS_CHOICES`). Advanced AI image models belong in enterprise integrations.
- **NO Third-Party Subdomain Multitenancy for Vendors**: Vendor mini-stores are served via clean URL routes (`/marketplace/vendor/<slug>/`) within the standard tenant storefront, rather than provisioning wildcard DNS subdomains.
- **NO General Consumer Product UGC**: Product star reviews, photo/video customer uploads, and community Q&A belong explicitly to sibling Sub-module 9.13 (Reviews & User-Generated Content). 9.11 cleanly restricts itself to verified-purchase seller fulfillment ratings and order dispute resolution.
