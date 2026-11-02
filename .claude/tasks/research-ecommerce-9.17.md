# Research — Sub-module 9.17: B2B & Wholesale Commerce (Module 9 — eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.17 B2B & Wholesale Commerce
- **Module:** 9 eCommerce Management System
- **Target app:** `apps/ecommerce` (extending the existing app created in 9.1 and extended through 9.16)
- **Research date:** 2026-11-02
- **Phase:** 1 Research only
- **Output file:** `.claude/tasks/research-ecommerce-9.17.md`

---

## 1. Executive Summary & Domain Architecture

Sub-module 9.17 delivers enterprise **B2B & Wholesale Commerce** capabilities for NavERP eCommerce, establishing first-class governance for business-to-business purchasing relationships that diverge significantly from standard direct-to-consumer (B2C) shopping experiences.

In enterprise wholesale, buyers are corporate entities purchasing high volumes under pre-negotiated contracts, multi-user hierarchies, trade credit terms, and custom procurement integrations. Market-leading B2B commerce platforms (such as Adobe Commerce B2B / Magento B2B, Shopify Plus B2B, BigCommerce B2B Edition, OroCommerce, and SAP Commerce Cloud) solve these specialized challenges through five fundamental capability pillars:

1. **Company Account Management & Role Hierarchies**:
   - Unlike single-shopper B2C profiles, B2B represents an organization (`core.Party`) with multiple associated buyers, purchasing managers, and approvers.
   - Companies maintain multi-tier user hierarchies, assigned departments, corporate credit limits, and custom purchasing approval rules (e.g. any order exceeding $5,000 or a buyer's individual spend threshold triggers a mandatory supervisor approval workflow).
2. **Quote Request & Negotiation (RFQ Workflows)**:
   - Wholesale transactions frequently require price negotiations for bulk volumes or specialized terms.
   - Buyers compile quote carts, request official RFQs with target pricing/dates, and merchants respond with counter-offers, volume discounts, or custom shipping rates. Once accepted, negotiated quotes seamlessly convert into locked e-commerce orders without manual re-entry.
3. **Punch-Out Catalog Integration (cXML / OCI)**:
   - Large institutional and enterprise buyers procure goods through internal ERP systems (SAP Ariba, Coupa, Jaggaer).
   - Punchout enables enterprise buyers to seamlessly jump from their procurement platform into the supplier's NavERP store with contract pricing, build a cart, and "punch back" the cart data as a procurement requisition for internal purchase order dispatch.
4. **Credit Terms & Net Payment (Trade Credit Management)**:
   - Wholesale transactions predominantly operate on trade terms (Net 15, Net 30, Net 60, Net 90) rather than immediate credit card settlement.
   - The platform manages credit lines, tracks available balances against open invoices, enforces mandatory PO numbers, and integrates with NavERP's authoritative General Ledger (`accounting`).
5. **Bulk Ordering, Quick Order & Requisition Lists**:
   - Professional buyers reorder hundreds of known SKUs repetitively.
   - Quick order matrix forms, bulk CSV/spreadsheet upload ordering, and saved reusable requisition lists (e.g., standard recurring supply kits) streamline purchasing from hours down to seconds.

### Architectural Boundary Rulings (L28, L29, L36, L37):
1. **Multi-Tenancy & Data Isolation (L28, L36)**:
   - All B2B commerce models inherit from `TenantNumbered` (`apps/ecommerce/models/_base.py`) with strict `tenant` (`core.Tenant`) isolation.
   - Company accounts, users, quotes, and quick order lists are partitioned per tenant.
2. **Financial Ledger & Payment Ownership (L29)**:
   - Module 9 `ecommerce` handles B2B payment terms and quote negotiation pricing.
   - Module 2 `accounting` remains the sole authoritative financial general ledger (`Invoice`, `Payment`, `JournalEntry`). B2B credit orders record formal accounting invoices without duplicating financial ledger tables in `ecommerce`.
3. **Party & User Spine Integration (L28)**:
   - `B2bCompanyAccount` links to `core.Party` (representing the corporate client entity).
   - `B2bCompanyUser` links to `settings.AUTH_USER_MODEL` and `core.Party` (representing individual buyers within the company).
4. **Product Catalog & Order Integration**:
   - B2B quote items and quick order templates link to verified catalog entities: `CatalogProduct` (9.1) and `ProductVariant` (9.1).
   - Approved quotes convert directly into `EcommerceOrder` (9.5) with order type flag / source metadata.

---

## 2. Repo State Checked First

### 2.1 Navigation & App Tree State
- **`apps/core/navigation.py` status:**
  - `"9.1"` is live: Product Catalog Management (`EPRD`, `PVR`, `ECAT`, `PRL`)
  - `"9.2"` is live: Inventory & Stock Management (`EFC`, `EAL`, `EBK`, `ESYN`)
  - `"9.3"` is live: Pricing & Promotion Engine (`EDPR`, `ECPN`, `EFLS`, `ECPM`)
  - `"9.4"` is live: Shopping Cart & Checkout (`ECRT`, `ECKS`, `ESHP`, `EPMC`)
  - `"9.5"` is live: Order Management System (`EORD`, `EFUL`, `ERMA`, `EORT`)
  - `"9.6"` is live: Customer Account & Profile (`ECAP`, `ECAD`, `EWSL`, `ECPR`)
  - `"9.7"` is live: Search & Product Discovery (`ESYM`, `ESFC`, `ESMR`, `ESQL`)
  - `"9.8"` is live: Personalization & Recommendation Engine (`EREC`, `EUSR`, `EACF`, `ECST`)
  - `"9.9"` is live: Content Management System (`ECMP`, `EBLP`, `EBNR`, `ENAV`)
  - `"9.10"` is live: Marketing & Campaign Management (`EMCP`, `ECPN`, `EABT`, `EADF`)
  - `"9.11"` is live: Marketplace & Multi-Vendor (`EVND`, `EVPL`, `EVST`, `EVCO`)
  - `"9.12"` is live: Subscription & Recurring Commerce (`ESBP`, `ECSB`, `ESBO`, `ESBD`)
  - `"9.13"` is live: Reviews & User-Generated Content (`EPRV`, `EQNA`, `EUGC`, `ERVR`)
  - `"9.14"` is live: Customer Service & Support (`ECST`, `ELCS`, `ESKB`, `ESLA`)
  - `"9.15"` is live: Analytics & Business Intelligence (`EATT`, `ECMT`, `EPMM`, `ECKM`)
  - `"9.16"` is live: Mobile Commerce (`EMAC`, `EMDR`, `EMPC`, `EMLR`)
  - `"9.17"`: Target sub-module (B2B & Wholesale Commerce) — to be built now.

### 2.2 Spine Entities Verified to Exist (Grep Evidence)
- `apps/core/models/`:
  - `Tenant`: verified (`apps/core/models/Tenant.py`)
  - `Party`: verified (`apps/core/models/Party.py`)
  - `User`: verified via `django.conf.settings.AUTH_USER_MODEL`
  - `Address`: verified (`apps/core/models/Address.py`)
- `apps/accounting/models/`:
  - `Currency`: verified (`apps/accounting/models/GeneralLedger/Currencies.py`)
  - `Invoice`: verified (`apps/accounting/models/AccountsReceivable/Invoices.py`)
  - `Payment`: verified (`apps/accounting/models/CashBank/Payments.py`)
- `apps/ecommerce/models/`:
  - `CatalogProduct`: verified (`apps/ecommerce/models/ProductCatalog/CatalogProducts.py`)
  - `ProductVariant`: verified (`apps/ecommerce/models/ProductCatalog/ProductVariants.py`)
  - `CustomerAccountProfile`: verified (`apps/ecommerce/models/CustomerProfile/CustomerAccountProfiles.py`)
  - `EcommerceOrder`: verified (`apps/ecommerce/models/OrderManagement/EcommerceOrders.py`)

---

## 3. Leaders Surveyed (with Source Links)

1. **Adobe Commerce (Magento B2B)**
   - *Enterprise standard for wholesale e-commerce and complex corporate accounts.*
   - Sources: [Adobe Commerce B2B Features](https://business.adobe.com/products/magento/b2b-commerce.html), Magento B2B User Guide.
   - Key capabilities: Company account hierarchies with custom buyer permissions, quote requests with live negotiation/counter-offers, requisition lists, company credit lines, quick order by SKU/CSV.

2. **Shopify Plus B2B**
   - *Leading modern DTC + B2B blended commerce platform.*
   - Sources: [Shopify Plus B2B Overview](https://www.shopify.com/plus/solutions/b2b), Shopify Help Center B2B.
   - Key capabilities: Company profiles with buyer locations, buyer roles (Admin, Ordering), wholesale price lists, Net 15/30/60 payment terms, draft order conversion for RFQs, PO number validation at checkout.

3. **BigCommerce B2B Edition**
   - *Turnkey mid-market and enterprise B2B suite with advanced buyer portals.*
   - Sources: [BigCommerce B2B Edition](https://www.bigcommerce.com/solutions/b2b/), BigCommerce Knowledge Base.
   - Key capabilities: Corporate account trees, order approval chains with spend thresholds, sales rep quoting portal, buyer invoice management, quick order SKU matrix, TradeCentric PunchOut gateway.

4. **OroCommerce**
   - *Purpose-built open source enterprise B2B commerce platform.*
   - Sources: [OroCommerce Features](https://oroinc.com/b2b-ecommerce/), OroCommerce Technical Documentation.
   - Key capabilities: Multi-organization and buyer hierarchy, configurable multi-step approval rules, quote negotiation lifecycle with margin calculation, corporate credit limits and AR balance tracking, native cXML/OCI punchout connectors.

5. **Salesforce B2B Commerce (CloudCraze / Commerce Cloud)**
   - *Enterprise CRM-integrated B2B commerce engine.*
   - Sources: [Salesforce B2B Commerce](https://www.salesforce.com/products/commerce-cloud/b2b-commerce/), Salesforce Help.
   - Key capabilities: Account hierarchies and contact roles, buyer group entitlements, contract pricing books, split shipments per line, quote requests connected to CPQ, credit terms.

6. **SAP Commerce Cloud B2B (Hybris)**
   - *Global enterprise manufacturing and distribution commerce platform.*
   - Sources: [SAP Commerce Cloud](https://www.sap.com/products/crm/e-commerce-platforms.html), SAP Help Portal.
   - Key capabilities: B2B organizational units, cost center budget limits, multi-tiered order approval workflows, quote negotiation, native SAP Ariba OCI/cXML PunchOut, bulk ordering matrix.

7. **Sana Commerce**
   - *Direct ERP-integrated B2B e-commerce platform for SAP and Microsoft Dynamics.*
   - Sources: [Sana Commerce Product Tour](https://www.sana-commerce.com/), Sana Documentation.
   - Key capabilities: Real-time ERP credit check and open invoice visibility, multi-tier pricing, customer self-service quote requests, recurring order templates, CSV shopping list import.

8. **TradeCentric (formerly PunchOut2Go)**
   - *Leading e-procurement integration gateway for B2B e-commerce.*
   - Sources: [TradeCentric Solutions](https://www.tradecentric.com/), PunchOut2Go Knowledge Base.
   - Key capabilities: cXML and OCI protocol translation, PunchOut setup requests, transfer shopping carts back to ERPs (Coupa, Ariba, Jaggaer), electronic PO dispatch.

---

## 4. Feature Catalog (This Sub-Module Only)

### 4.1 Company Account Management & Role Hierarchies
- **Corporate Company Accounts** — Centralized business account profile linking corporate identity (`core.Party`), tax/VAT ID, industry, and billing preferences.
  - *Seen in:* Adobe Commerce, BigCommerce B2B, Shopify Plus, OroCommerce.
  - *Priority:* `table-stakes`.
  - *Spine:* `TenantNumbered` entity `B2bCompanyAccount` pointing to `core.Party`.
  - *Buildable now:* Full Django CRUD with tenant isolation.
- **Multi-User Buyer Hierarchies & Roles** — Assign company employees distinct roles (Admin, Procurement Manager, Buyer, Approver, Auditor) with specific permissions.
  - *Seen in:* Adobe Commerce, BigCommerce B2B, OroCommerce, SAP Commerce.
  - *Priority:* `table-stakes`.
  - *Spine:* `B2bCompanyUser` linking `B2bCompanyAccount`, `settings.AUTH_USER_MODEL`, and `core.Party`.
  - *Buildable now:* Full Django CRUD with permission gates.
- **Purchase Approval Chains & Spending Limits** — Set per-buyer order spending limits and company-wide approval thresholds. Orders exceeding thresholds require designated approver review.
  - *Seen in:* BigCommerce B2B, OroCommerce, SAP Commerce.
  - *Priority:* `common`.
  - *Spine:* Fields on `B2bCompanyAccount` and `B2bCompanyUser` (`order_spend_limit`, `approval_threshold_amount`, `reports_to_approver`).
  - *Buildable now:* Fully modeled with status progression.

### 4.2 Quote Request & Negotiation (RFQ Workflows)
- **Request for Quote (RFQ) Submission** — Wholesale buyers submit quote requests with desired quantities, target pricing, delivery dates, and project notes.
  - *Seen in:* Adobe Commerce, BigCommerce B2B, OroCommerce, Sana Commerce.
  - *Priority:* `table-stakes`.
  - *Spine:* `B2bQuoteRequest` linking `B2bCompanyAccount`, `requested_by`, and `accounting.Currency`.
  - *Buildable now:* Full Django CRUD with line items payload and status workflow.
- **Quote Negotiation & Counter-Offers** — Sales reps review RFQs, calculate discounts/margins, apply custom shipping/tax, and return formal quote proposals with validity dates.
  - *Seen in:* Adobe Commerce, OroCommerce, Salesforce B2B.
  - *Priority:* `table-stakes`.
  - *Spine:* Status transitions (`submitted` -> `under_review` -> `quoted` -> `accepted` / `rejected`).
  - *Buildable now:* Form actions for quote revision and acceptance.
- **One-Click Order Conversion** — Upon customer acceptance, convert the locked quote into an official `EcommerceOrder` without re-entering products or pricing.
  - *Seen in:* Adobe Commerce, BigCommerce B2B, Shopify Plus.
  - *Priority:* `table-stakes`.
  - *Spine:* Foreign key `converted_order` on `B2bQuoteRequest` pointing to `ecommerce.EcommerceOrder`.
  - *Buildable now:* Transactional conversion action generating an order.

### 4.3 Punch-Out Catalog Integration (cXML / OCI)
- **Punchout Gateway Configuration** — Tenant-level and company-level punchout setup storing identity, shared secrets, return URLs, and protocol selection (`cxml` or `oci`).
  - *Seen in:* TradeCentric, OroCommerce, SAP Commerce, Adobe Commerce.
  - *Priority:* `common`.
  - *Spine:* Punchout configuration fields on `B2bCompanyAccount`.
  - *Buildable now:* Modeled fields, credential management, and test endpoint.
- **Punchout Session & Cart Return Handler** — Receive procurement setup requests, authenticate the buyer session, restrict catalog to contract pricing, and format the punchback cart XML/HTML.
  - *Seen in:* TradeCentric, OroCommerce.
  - *Priority:* `differentiator`.
  - *Spine:* View handler returning cXML/OCI payload structure.
  - *Buildable now:* Simulation endpoint and payload generator.

### 4.4 Credit Terms & Net Payment (Trade Credit Management)
- **Credit Limit & Available Balance Tracking** — Maintain credit lines for wholesale clients, validating open orders and open invoices against remaining credit.
  - *Seen in:* Adobe Commerce, OroCommerce, Sana Commerce, Shopify Plus.
  - *Priority:* `table-stakes`.
  - *Spine:* `credit_limit`, `available_credit`, `credit_status` on `B2bCompanyAccount`.
  - *Buildable now:* Field validation, status tracking, and balance deduction logic.
- **Payment Terms & Mandatory PO Number** — Assign specific payment terms (Prepaid, Due on Receipt, Net 15, Net 30, Net 45, Net 60, Net 90) and enforce customer purchase order numbers at checkout.
  - *Seen in:* Shopify Plus, BigCommerce B2B, Adobe Commerce, OroCommerce.
  - *Priority:* `table-stakes`.
  - *Spine:* `payment_terms`, `requires_po_number` on `B2bCompanyAccount`.
  - *Buildable now:* Field choices and checkout validation helpers.

### 4.5 Bulk Ordering & Quick Order
- **Saved Requisition Lists & Order Templates** — Buyers create recurring order templates (e.g. weekly replenishment, store opening kit) to reorder in bulk with 1 click.
  - *Seen in:* Adobe Commerce, OroCommerce, SAP Commerce, Sana Commerce.
  - *Priority:* `table-stakes`.
  - *Spine:* `B2bQuickOrderTemplate` linking `B2bCompanyAccount` and `created_by`.
  - *Buildable now:* Full Django CRUD with line items management.
- **Quick Order SKU Grid & CSV Import** — Fast order matrix allowing buyers to paste/type multiple SKUs with quantities or upload a CSV file directly to cart.
  - *Seen in:* Adobe Commerce, BigCommerce B2B, OroCommerce.
  - *Priority:* `table-stakes`.
  - *Spine:* Bulk order form and view action parsing CSV rows into catalog items.
  - *Buildable now:* Dedicated quick order view with CSV upload parser and catalog lookup.

---

## 5. Recommended Build Scope (This Pass — 4 Models)

To achieve complete coverage of the 5 NavERP.md bullets while complying with the strict 1–4 model limit per sub-module (L31), the following four tenant-scoped models are recommended:

1. **`B2bCompanyAccount` [Prefix: `EBCA`]**
   - *Domain:* Corporate business account, credit terms, approval rules, and punchout configuration.
   - *Key fields:*
     - Number: `EBCA-#####` via `TenantNumbered`.
     - Spine links: `tenant` (`core.Tenant`), `company_party` (`core.Party`), `primary_contact` (`settings.AUTH_USER_MODEL`), `currency` (`accounting.Currency`).
     - Business info: `company_name`, `company_tax_id`, `business_registration_number`, `website`, `industry`.
     - Credit terms: `credit_limit` (Decimal), `available_credit` (Decimal), `payment_terms` (choices: `prepaid`, `due_on_receipt`, `net_15`, `net_30`, `net_45`, `net_60`, `net_90`), `credit_status` (choices: `good_standing`, `warning`, `exceeded_limit`, `suspended`, `revoked`), `requires_po_number` (Boolean).
     - Approvals: `requires_order_approval` (Boolean), `approval_threshold_amount` (Decimal), `default_approver` (`settings.AUTH_USER_MODEL`, null/blank).
     - Punchout: `punchout_enabled` (Boolean), `punchout_protocol` (choices: `none`, `cxml`, `oci`), `punchout_identity` (CharField), `punchout_shared_secret` (CharField), `punchout_return_url` (URLField, blank).
     - Commercial: `wholesale_discount_percent` (Decimal), `status` (choices: `pending_review`, `active`, `on_hold`, `suspended`, `closed`).
   - *Justified by:* Company Account Management, Credit Terms & Net Payment, Punchout Integration.

2. **`B2bCompanyUser` [Prefix: `EBCU`]**
   - *Domain:* Corporate buyer membership, role permissions, spend limits, and approver hierarchy.
   - *Key fields:*
     - Number: `EBCU-#####` via `TenantNumbered`.
     - Spine links: `tenant` (`core.Tenant`), `company` (`B2bCompanyAccount`), `user` (`settings.AUTH_USER_MODEL`), `party` (`core.Party`, null/blank).
     - Role: `role` (choices: `company_admin`, `procurement_manager`, `buyer`, `approver`, `finance_auditor`), `job_title`, `department`.
     - Limits: `order_spend_limit` (Decimal), `monthly_spend_limit` (Decimal), `monthly_spend_current` (Decimal).
     - Permissions: `can_place_orders` (Boolean), `can_request_quotes` (Boolean), `can_view_invoices` (Boolean), `can_manage_users` (Boolean), `can_approve_orders` (Boolean).
     - Hierarchy: `reports_to_approver` (`self`, null/blank).
     - Status: `status` (choices: `active`, `invited`, `suspended`, `inactive`).
   - *Justified by:* Multi-user business accounts, role hierarchies, purchase approval chains.

3. **`B2bQuoteRequest` [Prefix: `EBQR`]**
   - *Domain:* Negotiable quote / RFQ lifecycle, pricing counter-offers, and order conversion.
   - *Key fields:*
     - Number: `EBQR-#####` via `TenantNumbered`.
     - Spine links: `tenant` (`core.Tenant`), `company` (`B2bCompanyAccount`), `requested_by` (`settings.AUTH_USER_MODEL`), `assigned_sales_rep` (`settings.AUTH_USER_MODEL`, null/blank), `currency` (`accounting.Currency`), `converted_order` (`ecommerce.EcommerceOrder`, null/blank).
     - Status: `status` (choices: `draft`, `submitted`, `under_review`, `quoted`, `buyer_review`, `accepted`, `rejected`, `expired`, `converted_to_order`).
     - Pricing: `target_budget` (Decimal, null/blank), `original_subtotal` (Decimal), `quoted_discount_percent` (Decimal), `quoted_total` (Decimal), `tax_amount` (Decimal), `shipping_estimate` (Decimal).
     - Timing: `target_delivery_date` (DateField, null/blank), `valid_until` (DateTimeField, null/blank), `submitted_at`, `quoted_at`, `accepted_at`.
     - Data: `line_items_data` (JSONField: items list with SKU, name, qty, requested price, quoted price, notes), `buyer_notes` (TextField), `merchant_notes` (TextField), `rejection_reason` (TextField, blank).
   - *Justified by:* Quote Request & Negotiation, volume pricing, order conversion.

4. **`B2bQuickOrderTemplate` [Prefix: `EBQT`]**
   - *Domain:* Reorder templates, saved requisition lists, repeating kits, and bulk SKU orders.
   - *Key fields:*
     - Number: `EBQT-#####` via `TenantNumbered`.
     - Spine links: `tenant` (`core.Tenant`), `company` (`B2bCompanyAccount`), `created_by` (`settings.AUTH_USER_MODEL`).
     - Metadata: `name` (CharField), `description` (TextField, blank), `scope` (choices: `private`, `company_shared`), `cadence` (choices: `ad_hoc`, `weekly`, `bi_weekly`, `monthly`, `quarterly`).
     - Items: `items_data` (JSONField: list of SKUs, names, default quantities, UOM, notes).
     - Activity: `total_items_count` (PositiveIntegerField), `times_ordered` (PositiveIntegerField), `last_ordered_at` (DateTimeField, null/blank), `is_active` (BooleanField).
   - *Justified by:* Bulk Ordering & Quick Order, CSV upload ordering, reorder templates, saved shopping lists.

---

## 6. Belongs to Sibling Sub-Modules (Parked, Not Scoped Here)

- **9.1 Product Catalog Management**: Base product catalog, SKU definitions, and standard consumer prices.
- **9.3 Pricing & Promotion Engine**: Consumer promotion rules, coupon codes, and flash sales.
- **9.5 Order Management System**: Core order placement, fulfillment pipelines, and return authorizations.
- **9.6 Customer Account & Profile**: Individual consumer profiles, consumer addresses, and consumer wishlists.
- **9.18 Fraud & Risk Management**: High-risk order velocity checks and chargeback disputes.
- **Module 4 (SCM 4.1 Procurement)**: Supplier purchase requisitions and supplier RFQs (where NavERP buys from vendors).

---

## 7. Deferred (Later Passes / Integrations)

- **Live EDI (ANSI X12 850 / EDIFACT ORDERS)**: Direct EDI transmission to large enterprise VAN networks.
- **Automated External Trade Credit Bureau Scoring**: Real-time Dun & Bradstreet / Experian business credit pull API.
- **Native Live cXML PunchOut HTTPS Listener**: Active cXML SetupRequest SSL listener daemon (simulated via structured endpoint in this pass).
