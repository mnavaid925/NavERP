# Research — Sub-module 9.6: Customer Account & Profile (Module 9 — eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.6 Customer Account & Profile
- **Module:** 9 eCommerce Management System
- **Target app:** `apps/ecommerce` (extending the app created in 9.1 and extended in 9.2, 9.3, 9.4, and 9.5)
- **Research date:** 2026-10-29
- **Phase:** 1 Research only
- **Output boundary:** `.claude/tasks/research-ecommerce-9.6.md` only

---

## 1. Executive Summary & Domain Architecture

Sub-module 9.6 represents the **Customer Account & Profile, Self-Service Portal, Address Book Preferences, Wishlist Management, Communication Consent Center, and Customer Privacy / GDPR Engine** of the NavERP eCommerce platform.

In modern enterprise and B2C digital commerce (exemplified by Shopify Plus, Adobe Commerce / Magento, BigCommerce, Salesforce B2C Commerce, commercetools, Klaviyo, Yotpo, and OneTrust), the customer account experience has evolved from a passive account page into an omnichannel self-service hub. It empowers customers to track historical purchases, reorder with one click, manage multiple delivery destinations with carrier instructions, organize saved wishlists with shareable links, control granular email/SMS communication opt-ins, and exercise statutory data privacy rights (GDPR/CCPA Data Subject Access Requests, data portability exports, and account erasure).

### Architectural Boundary Rulings (L28, L29, L36, L37):
1. **Core Spine Identity — Customers as `core.Party`**: Customers and shoppers are **`core.Party`** records with role `customer` (`core.PartyRole`). `apps/accounts.User` provides authentication credentials where `User.party` points to the `core.Party`. Sub-module 9.6 attaches eCommerce profile attributes, loyalty tiers, lifetime spend aggregates, and preference data directly to `core.Party`. Creating a duplicate customer table violates L36/L37.
2. **Address Spine — Augmenting `core.Address`**: Physical address locations belong to **`core.Address`** (`apps/core/models/Address.py`). 9.6 creates `CustomerAddressPreference` as an eCommerce overlay linking `core.Party` and `core.Address` to store delivery instructions, courier gate codes, delivery time windows, recipient contact info, and default shipping/billing flags without duplicating address lines.
3. **Purchase History & Reorder Shortcuts — Reusing 9.4 `Cart` & 9.5 `EcommerceOrder`**: Order history is queried dynamically from **`ecommerce.EcommerceOrder`** (`EORD-`, 9.5). Reorder shortcuts clone historical line items from `ecommerce.EcommerceOrderLine` (`EOLN-`, 9.5) directly into an active **`ecommerce.Cart`** (`ECRT-`, 9.4).
4. **Product Wishlists — Referencing 9.1 `CatalogProduct` & `ProductVariant`**: Wishlists and saved items link directly to **`ecommerce.CatalogProduct`** (`EPRD-`) and optional **`ecommerce.ProductVariant`** (`PVR-`) from Sub-module 9.1.
5. **Security & Identity — Reusing `apps/accounts`**: Core user password policies (`accounts.PasswordPolicy`), session tracking (`accounts.UserSession`), and multi-factor authentication (`accounts.MfaDevice`) are owned by `apps/accounts`. 9.6 integrates with them for customer-facing authentication modes rather than duplicating security models.
6. **Data Privacy & GDPR — Reconciling Statutory Retention vs. Erasure**: Under GDPR Article 17 ("Right to be Forgotten") vs. Commercial Tax Law (statutory retention for financial accounting), an eCommerce platform cannot delete completed orders (`EcommerceOrder`) and financial invoices (`accounting.Invoice`). The domain solution (validated in Adobe Commerce and OneTrust) anonymizes the customer profile (scrubbing PII, recipient names, phone numbers, delivery notes) and severs the login credentials, while retaining anonymized order transactions for regulatory accounting.

---

## 2. Repo State Checked First

### 2.1 Navigation & App Tree State
- **`apps/core/navigation.py`:**
  - `"9.1"` is live: Product Information Management, Category Hierarchy, Product Variants, Bulk Import/Export, Product Relationships, Catalog Overview.
  - `"9.2"` is live: Real-Time Stock Tracking, Warehouse & Fulfillment Center Management, Stock Transfers & Adjustments, Backorder & Pre-Order Management, Multi-Channel Inventory Sync, Inventory Operations Console.
  - `"9.3"` is live: Dynamic Price Rules, Discount & Coupon Management, Flash Sales, Loyalty & Rewards Pricing, Competitor Price Monitoring.
  - `"9.4"` is live: Persistent & Guest Cart, One-Page & Multi-Step Checkout, Shipping Rate Calculation, Tax Calculation, Payment Method Orchestration.
  - `"9.5"` is live: Order Capture & Validation, Order Routing & Splitting, Order Status & Tracking, Order Modifications & Cancellations, Returns & Exchanges (RMA).
  - Sub-module `"9.6"` has no `LIVE_LINKS` entry yet.
- **`apps/ecommerce/` package structure:**
  - Sub-module 9.6 will add package subdirectories: `CustomerAccount/` across `models/`, `forms/`, `views/`, `urls/`, and `templates/ecommerce/customeraccount/`.

### 2.2 As-Built Core Spine Entities (Grep Verified)
| Entity | Location | Status | 9.6 Usage |
|---|---|---|---|
| `core.Tenant` | `apps/core/models/Tenant.py:17` | **Present** | Multi-tenant isolation |
| `core.Party` | `apps/core/models/Party.py:5` | **Present** | Customer identity spine record (role `customer`) |
| `core.Address` | `apps/core/models/Address.py:5` | **Present** | Physical shipping and billing address records |
| `core.ContactMethod` | `apps/core/models/ContactMethod.py:5` | **Present** | Customer phone, email, and social contact handles |
| `accounts.User` | `apps/accounts/models/User.py:14` | **Present** | Django authentication user, links to `core.Party` via `User.party` |
| `accounts.MfaDevice` | `apps/accounts/models/IdentityAccess/MfaDevices.py` | **Present** | Multi-factor authentication device verification |
| `accounts.PasswordPolicy`| `apps/accounts/models/IdentityAccess/PasswordPolicies.py` | **Present** | Password complexity and expiration enforcement |
| `accounting.Currency` | `apps/accounting/models/GeneralLedger/Currencies.py:14` | **Present** | ISO-4217 customer preferred currency |
| `ecommerce.CatalogProduct` | `apps/ecommerce/models/ProductCatalog/CatalogProducts.py:8` | **Present** | Product reference in customer wishlists |
| `ecommerce.ProductVariant` | `apps/ecommerce/models/ProductCatalog/ProductVariants.py:10` | **Present** | Specific SKU variant in customer wishlists |
| `ecommerce.Cart` | `apps/ecommerce/models/CartCheckout/Carts.py:10` | **Present** | Reorder target destination for 1-click cart replenishment |
| `ecommerce.EcommerceOrder` | `apps/ecommerce/models/OrderManagement/EcommerceOrders.py:10` | **Present** | Order purchase timeline and invoice history |
| `ecommerce.EcommerceOrderLine` | `apps/ecommerce/models/OrderManagement/EcommerceOrders.py:270`| **Present** | Order lines inspected and cloned for reorder shortcuts |

### 2.3 Prefix Collision Verification
All candidate prefixes checked across all models in the repository:
- `ECAP` — `CustomerAccountProfile` (**Verified FREE**)
- `ECAD` — `CustomerAddressPreference` (**Verified FREE**)
- `EWSL` — `CustomerWishlist` (**Verified FREE**)
- `ECPR` — `CustomerPrivacyRequest` (**Verified FREE**)

---

## 3. Commercial Market Leaders Surveyed

### 1. Shopify Plus (Customer Accounts & Customer Privacy API)
- **Positioning**: Global commerce leader offering modern "New Customer Accounts" with passwordless verification, self-serve order management, and headless Customer Privacy APIs.
- **Reference**: https://help.shopify.com/en/manual/customers/customer-accounts, https://shopify.dev/docs/api/customer-privacy
- **Key Capabilities**:
  - **Passwordless Authentication**: 6-digit one-time email/SMS codes and Shop sign-in, removing password reset friction.
  - **Centralized Order Hub**: Order history timeline with live fulfillment tracking and self-service return initiation.
  - **Self-Serve Address Book**: Stored shipping and billing addresses pre-populating checkout.
  - **Customer Privacy API**: Explicit opt-in tracking for marketing vs. analytics cookies, GDPR compliance endpoints.
  - **Buy Again / Reorder**: Instant 1-click reorder button cloning previous order items into active checkout.

### 2. Adobe Commerce / Magento 2
- **Positioning**: Enterprise digital commerce platform renowned for deeply configurable customer accounts, multi-address shipping, and native B2C/B2B customer attributes.
- **Reference**: https://experienceleague.adobe.com/en/docs/commerce-admin/customers/customer-accounts/customer-dashboard
- **Key Capabilities**:
  - **Comprehensive Account Dashboard**: Left-navigation hub showing default billing/shipping address, recent orders, newsletter subscriptions, and store credits.
  - **Address Book Management**: Multiple shipping and billing addresses with distinct default flags and delivery comments.
  - **My Wish List**: Saving items for later, multiple named wishlists, public shareable links, and "Add All to Cart".
  - **GDPR & Privacy Compliance**: Data Subject Access Request (DSAR) export, profile anonymization, and customer erasure workflows that preserve statutory tax/order records.

### 3. BigCommerce (Customer Accounts & Wishlists)
- **Positioning**: Leading open-SaaS enterprise platform offering rich customer grouping, address management, and developer-friendly customer APIs.
- **Reference**: https://support.bigcommerce.com/s/article/Managing-Customers, https://developer.bigcommerce.com/docs/rest-management/wishlists
- **Key Capabilities**:
  - **Customer Segmentation Groups**: Customer groups granting tailored pricing, wholesale catalog visibility, and tax exemption flags.
  - **Customer Wishlists**: Multiple named wishlists, public/private sharing tokens, and REST API endpoints (`/v3/wishlists`).
  - **Stored Addresses API**: Programmatic address CRUD with default shipping/billing markers and commercial address flags.
  - **Single Sign-On (SSO)**: JWT-based customer login integration for seamless storefront portal authentication.

### 4. Salesforce B2C Commerce (Salesforce Commerce Cloud)
- **Positioning**: Tier-1 enterprise cloud platform powering high-volume global retail storefronts with sophisticated customer profiles and headless APIs.
- **Reference**: https://developer.salesforce.com/docs/commerce/commerce-api/references/shopper-customers, https://salesforcecommercecloud.github.io/b2c-dev-doc/
- **Key Capabilities**:
  - **Customer Profile (`dw.customer.Customer`)**: Central shopper record managing credentials, lifecycle stage, lifetime value metrics, and loyalty tiers.
  - **Address Book (`dw.customer.AddressBook`)**: Collection of customer addresses with preferred delivery instructions and address labels (Home, Work, Vacation).
  - **Product Lists (`dw.customer.ProductList`)**: Unified abstraction for wishlists, gift registries, and shopping lists supporting priority levels and item notes.
  - **Shopper Consents API**: Fine-grained customer consent tracking for marketing channels, behavioral tracking, and privacy opt-ins.

### 5. commercetools (Composable Commerce)
- **Positioning**: Industry-defining headless commerce platform utilizing MACH architecture (Microservices, API-first, Cloud-native, Headless).
- **Reference**: https://docs.commercetools.com/api/projects/customers, https://docs.commercetools.com/api/projects/shoppingLists
- **Key Capabilities**:
  - **Customer & Address Arrays**: Customer resource managing addresses with explicit `defaultShippingAddressId` and `defaultBillingAddressId`.
  - **`EXTERNAL_AUTH` Mode**: Support for passwordless and external IdP authentication (Auth0, Okta, Firebase) without storing passwords in the commerce database.
  - **Shopping Lists API (`/me/shopping-lists`)**: Customer and anonymous shopping lists with line item counts, desired quantities, and variant references.
  - **Customer Groups**: Assignment to customer groups for promotional targeting and business rules.

### 6. Klaviyo (Customer Consent & Preference Center)
- **Positioning**: Premier eCommerce marketing automation and customer data platform specializing in compliance, double opt-in, and communication preference centers.
- **Reference**: https://help.klaviyo.com/hc/en-us/articles/115005251108-Understanding-Consent-in-Profiles, https://help.klaviyo.com/hc/en-us/articles/115005255808
- **Key Capabilities**:
  - **Granular Multi-Channel Consent**: Independent tracking of Email, SMS, and Push notification consent with opt-in method and timestamp.
  - **Double Opt-In (DOI)**: Verification emails/SMS confirmation before activating marketing subscriptions.
  - **Unified Preference Center**: Self-service portal where customers choose message frequency (weekly vs. monthly) and content categories instead of blanket unsubscriptions.
  - **1-Click Cryptographic Unsubscribe**: Unsubscribe tokens in message headers allowing seamless, authenticated preference updates without login friction.

### 7. Yotpo (Loyalty & SMS Compliance)
- **Positioning**: Leading eCommerce retention platform specializing in SMS marketing compliance (TCPA/CTIA), customer loyalty points, and VIP tiers.
- **Reference**: https://support.yotpo.com/en/article/sms-compliance-faqs, https://www.yotpo.com/platform/loyalty/
- **Key Capabilities**:
  - **TCPA / CTIA Consent Logging**: Capturing explicit opt-in text, IP address, and timestamp for SMS marketing compliance.
  - **Customer VIP Tiers**: Tier-based customer progression (Bronze, Silver, Gold, VIP) based on rolling annual spend or order frequency.
  - **Points Balance & History**: Real-time display of accumulated loyalty points, redemption thresholds, and expiration dates on the customer dashboard.

### 8. OneTrust (eCommerce Privacy & DSAR Automation)
- **Positioning**: Market-leading enterprise privacy management and regulatory compliance platform for GDPR, CCPA/CPRA, and global data rights.
- **Reference**: https://www.onetrust.com/products/datasubject-access-requests/, https://www.onetrust.com/solutions/ecommerce/
- **Key Capabilities**:
  - **Self-Service DSAR Intake**: Branded customer web form to submit requests for Data Access, Portability, and Account Deletion.
  - **Automated Data Portability**: Aggregating customer profile, order history, and addresses into a machine-readable JSON/CSV package.
  - **Right to Erasure with Financial Exception Handling**: Automated pseudonymization/anonymization workflows that scrub customer PII while retaining financial and invoice records required by statutory tax laws.
  - **SLA & Audit Tracking**: 30-day statutory countdown tracking and full compliance audit trails for regulatory reporting.

---

## 4. Feature Catalog (Sub-module 9.6 only)

### 4.1 Registration & Authentication
- **Customer Account Identity Spine Mapping** — Customer profiles link directly to `core.Party` (with role `customer`) and optional `accounts.User` for login credentials.
  - *Seen in:* Shopify Plus, commercetools, Adobe Commerce, Salesforce B2C
  - *Priority:* `table-stakes`
  - *Spine:* Reuses `core.Party` + `accounts.User`
  - *Status:* Buildable now
- **Authentication Mode & Provider Tracking** — Track customer auth method (`password`, `passwordless_email`, `phone_otp`, `sso_oauth`, `external_idp`) and external identity provider ID.
  - *Seen in:* commercetools (`EXTERNAL_AUTH`), Shopify Plus, BigCommerce
  - *Priority:* `common`
  - *Spine:* New field in `CustomerAccountProfile`
  - *Status:* Buildable now (external IdP OAuth integrations flagged for integration)
- **Phone Number Verification State** — Track customer mobile phone, verification status (`unverified`, `pending_code`, `verified`), and verification timestamp for SMS delivery and order alerts.
  - *Seen in:* Shopify Plus (Shop), Klaviyo, Yotpo
  - *Priority:* `common`
  - *Spine:* New fields in `CustomerAccountProfile` (uses `core.ContactMethod` for raw value)
  - *Status:* Buildable now
- **Customer Lifecycle Status** — Account lifecycle state machine: `pending_verification`, `active`, `suspended`, `locked`, `anonymized`.
  - *Seen in:* Adobe Commerce, BigCommerce, Salesforce B2C
  - *Priority:* `table-stakes`
  - *Spine:* New field in `CustomerAccountProfile`
  - *Status:* Buildable now

### 4.2 Account Dashboard & Order History
- **Unified Customer Dashboard Overview** — Consolidated metrics card displaying total lifetime orders, total spend amount, loyalty tier/points, default shipping address, and active orders.
  - *Seen in:* Adobe Commerce, Shopify Plus, BigCommerce
  - *Priority:* `table-stakes`
  - *Spine:* Aggregated view context over `CustomerAccountProfile`, `EcommerceOrder`, and `CustomerAddressPreference`
  - *Status:* Buildable now
- **Chronological Order Purchase Timeline** — Detailed order list with date, order number (`EORD-`), items thumbnail summary, fulfillment status, and tracking link.
  - *Seen in:* Shopify Plus, Adobe Commerce, Salesforce B2C
  - *Priority:* `table-stakes`
  - *Spine:* Reuses `ecommerce.EcommerceOrder` (`apps/ecommerce/models/OrderManagement/EcommerceOrders.py`)
  - *Status:* Buildable now
- **1-Click Reorder Shortcut ("Buy Again")** — Action button on past orders that copies valid line items into the customer's active shopping cart with current catalog prices.
  - *Seen in:* Shopify Plus, Adobe Commerce, BigCommerce
  - *Priority:* `common`
  - *Spine:* Action view bridging `ecommerce.EcommerceOrderLine` into `ecommerce.Cart`
  - *Status:* Buildable now
- **Invoice & Receipt Download Summary** — Downloadable printable invoice/receipt for completed orders.
  - *Seen in:* Adobe Commerce, BigCommerce, Shopify Plus
  - *Priority:* `table-stakes`
  - *Spine:* View rendering printable HTML/PDF summary from `EcommerceOrder`
  - *Status:* Buildable now
- **Multiple Named Customer Wishlists** — Support for creating multiple named wishlists (e.g. "Favorites", "Holiday 2026") with public/private visibility and shareable link tokens.
  - *Seen in:* BigCommerce, Adobe Commerce, commercetools, Salesforce B2C
  - *Priority:* `common`
  - *Spine:* New table `CustomerWishlist` (`EWSL-`)
  - *Status:* Buildable now
- **Wishlist Saved Items & Priority** — Saved catalog products and variants in wishlists with desired quantity, added price, priority (`low`, `medium`, `high`), and notes.
  - *Seen in:* Adobe Commerce, BigCommerce, Salesforce B2C (`ProductList`)
  - *Priority:* `common`
  - *Spine:* New child table `CustomerWishlistItem` (`EWSI-`), FK to `ecommerce.CatalogProduct` & `ProductVariant`
  - *Status:* Buildable now

### 4.3 Address Book & Preferences
- **Multi-Address Customer Book** — Customer can manage multiple saved shipping and billing addresses associated with their profile.
  - *Seen in:* Shopify Plus, Adobe Commerce, BigCommerce, commercetools, Salesforce B2C
  - *Priority:* `table-stakes`
  - *Spine:* Reuses `core.Address` overlayed by `CustomerAddressPreference`
  - *Status:* Buildable now
- **Default Shipping & Billing Preferences** — Explicit flags identifying the default shipping destination and default billing address for streamlined 1-click checkout prefill.
  - *Seen in:* commercetools, Adobe Commerce, Shopify Plus, BigCommerce
  - *Priority:* `table-stakes`
  - *Spine:* Flags in `CustomerAddressPreference`
  - *Status:* Buildable now
- **Address Labels & Recipient Details** — User-friendly address tags ("Home", "Office", "Warehouse", "Parent's House") plus courier recipient name and phone number.
  - *Seen in:* Salesforce B2C, Adobe Commerce, BigCommerce
  - *Priority:* `common`
  - *Spine:* Fields in `CustomerAddressPreference`
  - *Status:* Buildable now
- **Delivery Instructions & Courier Notes** — Structured delivery guidance for couriers (e.g., gate code, leave at back porch, concierge drop-off, call upon arrival).
  - *Seen in:* Shopify Plus, Amazon, BigCommerce
  - *Priority:* `common`
  - *Spine:* Fields in `CustomerAddressPreference`
  - *Status:* Buildable now
- **Delivery Time Window Preference** — Preferred delivery schedule (`anytime`, `morning`, `afternoon`, `evening`, `weekend_only`).
  - *Seen in:* Manhattan Active Omni, commercetools
  - *Priority:* `differentiator`
  - *Spine:* Choice field in `CustomerAddressPreference`
  - *Status:* Buildable now

### 4.4 Communication Preferences
- **Granular Multi-Channel Marketing Opt-In** — Independent opt-in toggles for marketing emails, marketing SMS, and push notifications with timestamp and consent source.
  - *Seen in:* Klaviyo, Yotpo, Salesforce B2C, Shopify Plus
  - *Priority:* `table-stakes`
  - *Spine:* Fields in `CustomerAccountProfile`
  - *Status:* Buildable now
- **Transactional Notifications Preference** — Opt-in preferences for operational notifications (order confirmations, shipping tracking updates, out-for-delivery SMS).
  - *Seen in:* Shopify Plus, Klaviyo
  - *Priority:* `common`
  - *Spine:* Fields in `CustomerAccountProfile`
  - *Status:* Buildable now
- **Double Opt-In (DOI) Verification Lifecycle** — Tracking confirmation timestamp when a customer verifies their email or SMS subscription link.
  - *Seen in:* Klaviyo, Mailchimp
  - *Priority:* `common`
  - *Spine:* Timestamp in `CustomerAccountProfile`
  - *Status:* Buildable now
- **Cryptographic 1-Click Unsubscribe Token** — Secure URL token enabling 1-click unsubscribe links in emails without requiring customer password login.
  - *Seen in:* Klaviyo, OneTrust
  - *Priority:* `table-stakes`
  - *Spine:* Token field in `CustomerAccountProfile`
  - *Status:* Buildable now
- **Communication Frequency Preference** — Customer preference for marketing contact cadence (`daily`, `weekly_digest`, `monthly`, `promotions_only`).
  - *Seen in:* Klaviyo Preference Center
  - *Priority:* `differentiator`
  - *Spine:* Choice field in `CustomerAccountProfile`
  - *Status:* Buildable now

### 4.5 Account Security & Privacy (GDPR / CCPA)
- **Customer Self-Service Privacy Request Intake (DSAR)** — Customer portal for submitting data access, data portability export, or account erasure requests.
  - *Seen in:* OneTrust, Adobe Commerce, Shopify Plus
  - *Priority:* `table-stakes`
  - *Spine:* New table `CustomerPrivacyRequest` (`ECPR-`)
  - *Status:* Buildable now
- **Data Subject Request SLA & Lifecycle Tracking** — State machine (`submitted`, `identity_verified`, `processing`, `completed`, `rejected`), 30-day statutory GDPR due date, and verified timestamps.
  - *Seen in:* OneTrust, Didomi
  - *Priority:* `table-stakes`
  - *Spine:* State machine and date fields in `CustomerPrivacyRequest`
  - *Status:* Buildable now
- **Data Portability Machine-Readable Export** — Generation of customer personal data package (JSON format containing profile, order history, addresses, wishlists, and consent logs).
  - *Seen in:* OneTrust, Shopify Plus, Adobe Commerce
  - *Priority:* `table-stakes`
  - *Spine:* JSON export builder view in `CustomerPrivacyRequest`
  - *Status:* Buildable now
- **Account Erasure & Anonymization Engine** — GDPR Article 17 erasure workflow that sanitizes customer PII (names, emails, phones, delivery notes) and deactivates login credentials while preserving anonymized transactional records for statutory tax/accounting compliance.
  - *Seen in:* Adobe Commerce GDPR module, OneTrust, Shopify Plus
  - *Priority:* `table-stakes`
  - *Spine:* Method and execution action on `CustomerPrivacyRequest` and `CustomerAccountProfile`
  - *Status:* Buildable now
- **Two-Factor Authentication (2FA) & Password Policy Integration** — Customer account security status indicators showing MFA enablement and password update history.
  - *Seen in:* Shopify Plus, Adobe Commerce
  - *Priority:* `table-stakes`
  - *Spine:* Reuses `apps.accounts.MfaDevice` and `apps.accounts.PasswordPolicy`
  - *Status:* Buildable now

### 4.6 Beyond the Bullets (High-Value Market Additions)
- **Customer VIP Tier & Loyalty Points Stand-in** — Customer tier categorization (`bronze`, `silver`, `gold`, `platinum`, `vip`) with cached loyalty points balance, paving the way for Sub-module 9.3 loyalty discounts.
  - *Seen in:* Yotpo, BigCommerce, Adobe Commerce
  - *Priority:* `common`
  - *Spine:* Fields on `CustomerAccountProfile`
  - *Status:* Buildable now
- **Public Shareable Wishlist Token** — Unique secure token allowing customers to share their wishlist with friends or family via URL.
  - *Seen in:* BigCommerce, Adobe Commerce, Amazon
  - *Priority:* `common`
  - *Spine:* Field on `CustomerWishlist`
  - *Status:* Buildable now

---

## 5. Recommended Build Scope (This Pass — 4 Models)

To deliver a robust, cohesive customer portal for Sub-module 9.6 while adhering strictly to NavERP multi-tenancy and the core spine, we recommend **4 tenant-scoped models** organized under `apps/ecommerce/models/CustomerAccount/`:

### Model 1: `CustomerAccountProfile` [Prefix: `ECAP`]
- **Purpose**: The central eCommerce profile augmenting `core.Party` (role `customer`) and `accounts.User`. Stores customer tier, lifetime transaction aggregates, communication preferences, and authentication metadata.
- **Fields & Choices**:
  - `tenant` (FK `core.Tenant`, cascade)
  - `code` (auto-numbered, `ECAP-XXXXX`)
  - `customer` (OneToOne/FK `core.Party`, on_delete=PROTECT, related_name="ecommerce_profile")
  - `user` (OneToOne/FK `accounts.User`, on_delete=SET_NULL, null=True, blank=True, related_name="ecommerce_customer_profile")
  - `tier` (CharField, choices: `bronze`, `silver`, `gold`, `platinum`, `vip`, default `bronze`)
  - `status` (CharField, choices: `active`, `pending_verification`, `suspended`, `anonymized`, default `active`)
  - `auth_mode` (CharField, choices: `password`, `passwordless_email`, `phone_otp`, `sso_oauth`, default `password`)
  - `phone_number` (CharField, blank=True)
  - `is_phone_verified` (BooleanField, default False)
  - `phone_verified_at` (DateTimeField, null=True, blank=True)
  - `preferred_currency` (FK `accounting.Currency`, on_delete=PROTECT, null=True, blank=True)
  - `preferred_language` (CharField, default="en", max_length=10)
  - `marketing_email_opt_in` (BooleanField, default False)
  - `marketing_sms_opt_in` (BooleanField, default False)
  - `order_updates_sms_opt_in` (BooleanField, default True)
  - `communication_frequency` (CharField, choices: `all`, `weekly_digest`, `promotions_only`, default `all`)
  - `unsubscribe_token` (CharField, max_length=64, blank=True, db_index=True)
  - `double_opt_in_confirmed_at` (DateTimeField, null=True, blank=True)
  - `total_orders_count` (PositiveIntegerField, default=0)
  - `total_spend_amount` (DecimalField, max_digits=12, decimal_places=2, default=0.00)
  - `loyalty_points_balance` (PositiveIntegerField, default=0)
  - `notes` (TextField, blank=True)
- **Verified FKs**: `core.Tenant`, `core.Party`, `accounts.User`, `accounting.Currency`.

### Model 2: `CustomerAddressPreference` [Prefix: `ECAD`]
- **Purpose**: Logistics and delivery preference overlay connecting a customer `core.Party` with physical `core.Address` records. Holds carrier delivery instructions, courier notes, and default selection flags.
- **Fields & Choices**:
  - `tenant` (FK `core.Tenant`, cascade)
  - `code` (auto-numbered, `ECAD-XXXXX`)
  - `customer` (FK `core.Party`, on_delete=CASCADE, related_name="ecommerce_address_preferences")
  - `address` (FK `core.Address`, on_delete=CASCADE, related_name="ecommerce_preferences")
  - `label` (CharField, choices: `home`, `work`, `warehouse`, `other`, default `home`)
  - `is_default_shipping` (BooleanField, default False)
  - `is_default_billing` (BooleanField, default False)
  - `recipient_name` (CharField, max_length=255, blank=True)
  - `recipient_phone` (CharField, max_length=50, blank=True)
  - `delivery_instructions` (TextField, blank=True, help_text="Gate codes, porch drop-off, neighbor delivery notes")
  - `delivery_window` (CharField, choices: `anytime`, `morning`, `afternoon`, `evening`, default `anytime`)
  - `requires_signature` (BooleanField, default False)
- **Verified FKs**: `core.Tenant`, `core.Party`, `core.Address`.

### Model 3: `CustomerWishlist` [Prefix: `EWSL`] & `CustomerWishlistItem`
- **Purpose**: Saved product collections enabling customers to save items for future purchases, share lists via URL, and move items directly into the shopping cart.
- **Fields & Choices (`CustomerWishlist`)**:
  - `tenant` (FK `core.Tenant`, cascade)
  - `code` (auto-numbered, `EWSL-XXXXX`)
  - `customer` (FK `core.Party`, on_delete=CASCADE, related_name="ecommerce_wishlists")
  - `name` (CharField, max_length=255, default="My Wishlist")
  - `slug` (SlugField, blank=True)
  - `visibility` (CharField, choices: `private`, `shared`, `public`, default `private`)
  - `share_token` (CharField, max_length=64, blank=True, db_index=True)
  - `is_default` (BooleanField, default True)
  - `item_count` (PositiveIntegerField, default=0)
  - `notes` (TextField, blank=True)
- **Child Model (`CustomerWishlistItem`)** (internal child entity in same file):
  - `wishlist` (FK `CustomerWishlist`, on_delete=CASCADE, related_name="items")
  - `product` (FK `ecommerce.CatalogProduct`, on_delete=CASCADE, related_name="wishlist_items")
  - `variant` (FK `ecommerce.ProductVariant`, on_delete=SET_NULL, null=True, blank=True)
  - `desired_quantity` (PositiveIntegerField, default=1)
  - `added_price` (DecimalField, max_digits=12, decimal_places=2, default=0.00)
  - `priority` (CharField, choices: `low`, `medium`, `high`, default `medium`)
  - `notes` (CharField, max_length=255, blank=True)
  - `added_at` (DateTimeField, auto_now_add=True)
- **Verified FKs**: `core.Tenant`, `core.Party`, `ecommerce.CatalogProduct`, `ecommerce.ProductVariant`.

### Model 4: `CustomerPrivacyRequest` [Prefix: `ECPR`]
- **Purpose**: Self-service GDPR and CCPA Data Subject Access Request (DSAR) engine handling data portability exports, consent withdrawal, and account erasure workflows.
- **Fields & Choices**:
  - `tenant` (FK `core.Tenant`, cascade)
  - `code` (auto-numbered, `ECPR-XXXXX`)
  - `customer` (FK `core.Party`, on_delete=PROTECT, related_name="ecommerce_privacy_requests")
  - `request_type` (CharField, choices: `data_export`, `account_erasure`, `consent_withdrawal`, `rectification`, default `data_export`)
  - `status` (CharField, choices: `submitted`, `identity_verified`, `processing`, `completed`, `rejected`, default `submitted`)
  - `verification_token` (CharField, max_length=64, blank=True)
  - `verification_expires_at` (DateTimeField, null=True, blank=True)
  - `verified_at` (DateTimeField, null=True, blank=True)
  - `due_date` (DateField, help_text="Statutory 30-day compliance deadline")
  - `completed_at` (DateTimeField, null=True, blank=True)
  - `rejected_at` (DateTimeField, null=True, blank=True)
  - `rejection_reason` (TextField, blank=True)
  - `anonymization_summary` (JSONField, default=dict, blank=True)
  - `export_payload` (JSONField, default=dict, blank=True, help_text="Generated machine-readable portability snapshot")
  - `request_ip` (GenericIPAddressField, null=True, blank=True)
  - `resolution_notes` (TextField, blank=True)
- **Verified FKs**: `core.Tenant`, `core.Party`.

---

## 6. Belongs to Sibling Sub-modules (Parked, Not Scoped Here)

- **9.1 Product Information Management (PIM)**: Product catalog attributes, variant matrices, category trees. *(Built)*
- **9.2 Inventory & Stock Management**: Fulfillment center allocations, stock counts, backorders. *(Built)*
- **9.3 Pricing & Promotion Engine**: Discount coupon codes, dynamic pricing tiers, flash sales. *(Built)*
- **9.4 Shopping Cart & Checkout**: Cart calculation, checkout steps, payment method configs. *(Built)*
- **9.5 Order Management System (OMS)**: Order routing, shipment fulfillments, RMA returns. *(Built)*
- **9.7 Search & Product Discovery**: Typo-tolerant search, faceted attribute filters, visual search. *(Sibling 9.7)*
- **9.8 Personalization & Recommendation Engine**: Clickstream telemetry, AI collaborative recommendations. *(Sibling 9.8)*
- **9.10 Marketing & Campaign Management**: Automated marketing email drips, SMS broadcast campaigns. *(Sibling 9.10)*
- **9.13 Reviews & User-Generated Content**: Post-purchase product reviews, verified buyer badges, star ratings. *(Sibling 9.13)*
- **9.14 Customer Service & Support**: Customer support helpdesk tickets, live chat widget. *(Sibling 9.14)*
- **9.17 B2B & Wholesale Commerce**: Multi-user company accounts, role hierarchies, purchase approval chains. *(Sibling 9.17)*

---

## 7. Deferred (Later Passes / External Integrations)

- **Third-Party SMS Gateway Dispatch (Twilio, Sinch, AWS SNS)**: Data model supports phone verification status and SMS opt-in tracking; real-time SMS OTP dispatch is flagged for gateway connector integration.
- **Social Login OAuth Providers (Google, Apple, Facebook)**: Relies on `django-allauth` or external IdP configuration; data model stores `auth_mode` and external provider identifiers.
- **Hardware WebAuthn / Passkeys**: Browser and IdP level biometric credentials registration.
- **Automated OneTrust Webhook Sync**: Outbound webhook syndication to external legal compliance software.
