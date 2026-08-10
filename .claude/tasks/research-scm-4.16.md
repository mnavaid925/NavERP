# Research — Sub-module 4.16: Customer Portal (Module 4 — Supply Chain Management, `scm`)

**NavERP.md §4.16 bullets (the scope this catalog is written against):** Order Tracking · Account Management ·
Document Retrieval · Support Ticketing · Catalog Browsing. (`NavERP.md:838-843`)

**The one-line thesis:** 4.16 is a **read-mostly projection of sub-modules 4.3/4.5/4.6/4.10 + `accounting` + `crm`
onto a customer-facing surface, plus the small amount of state that only a portal has** — who is allowed to see
what, which documents were shared and downloaded, and what the customer said about a specific order. Every leader
surveyed that sits on an ERP (Sana, Epicor, NetSuite, Unleashed) is exactly that: the portal stores almost nothing
and renders the ERP live. NetSuite's SuiteCommerce **MyAccount** is the sharpest precedent — a login-only portal
that deliberately ships **no cart, no checkout and no new-order entry**, only purchases/billing/support/settings.
That is the shape 4.16 should copy, because cart/checkout/pricing engine belong to Module 9.

---

## Repo state checked first

### LIVE_LINKS built so far in module 4 (`apps/core/navigation.py`, read at run time)
`"4.1" … "4.14"` are present (`navigation.py:770,783,793,803,815,827,839,849,869,885,914,934,978,1022`).
**`"4.15"` and `"4.16"` are absent.** Note: `.claude/tasks/research-scm-4.15.md` exists (committed `4c2b7557`)
but **4.15 Cold Chain was never built** — `apps/scm/models/__init__.py` ends at 4.14 Labor Management and there is
no `ColdChain*` model anywhere (`grep -ri coldchain apps/scm` hits only `Carriers.py` / an old migration, as a
*mode/handling* word). **4.16 must not FK to any cold-chain model — none exist.**

### Spine verified to EXIST (grep evidence — L28 "verify the spine exists", never trust the ERD)

| Entity | Where | Why 4.16 cares |
|---|---|---|
| `core.Party`, `core.PartyRole` | `apps/core/models/Party.py:5`, `PartyRole.py:5` (role `customer`) | the customer master — never duplicated |
| `core.Address` | `apps/core/models/Address.py:5` — fields are **`kind`/`line1`/`city`/`country` only, NO postal code** | ship-to book; the missing postcode is already documented at 4.10 |
| `core.ContactMethod` | `apps/core/models/ContactMethod.py:5` (`kind` email/phone/mobile, `value`) | portal contacts |
| `core.Document` | `apps/core/models/Document.py:5` — GenericFK + `FileField` + `classification` (public/internal/confidential) | the generic attachment 4.16 shares |
| `core.AuditLog` | `apps/core/models/AuditLog.py:5` — `ACTION_CHOICES = create/update/delete` only | **cannot** express "viewed order"/"downloaded POD" → see PortalActivity |
| `accounting.Invoice` | `apps/accounting/models/AccountsReceivable/Invoices.py:6` — `party` FK, `status`, `total`, `amount_paid()`, `balance_due()` | the AR document the portal lists. L29: no second ledger |
| `accounting.Payment`, `PaymentTerm`, `Currency` | `AccountsPayable/Payments.py:6`, `AccountsPayable/PaymentTerms.py:6`, `GeneralLedger/Currencies.py:6` | payment history / terms display |
| `accounting.CustomerProfile` | `AccountsReceivable/CustomerProfiles.py:5` — `credit_limit`, `credit_on_hold`, `payment_terms`, `currency` | "account balance / credit limit / terms" widget |
| `scm.SalesOrder` / `SalesOrderLine` | `models/OrderManagement/SalesOrders.py:20,185` — status incl. `partially_fulfilled`, `promised_date`, `invoice` FK, `confirmation_sent_at`/`shipped_notification_at`/`delivered_notification_at` | **4.5 owns the order. 4.16 READS it.** |
| `scm.SalesOrderAllocation` | `models/OrderManagement/SalesOrderAllocations.py:15`; line-level `quantity_allocated()` / `quantity_backordered()` derived (`SalesOrders.py:231-242`) | backorder + ATP figures, both derived |
| `scm.Shipment` / `TrackingEvent` | `models/TransportationManagement/Shipments.py:18,148` — `status`, `current_status_text`, `last_known_location`, `eta`, `is_delayed`, **`pod_received` / `pod_received_at`** (`:73-74`), 11 event types incl. `pod_signed` | **4.6 owns tracking + POD. 4.16 READS it.** |
| `scm.Load` / `LoadStop` | `models/TransportationManagement/Loads.py` | multi-stop/leg context |
| `scm.Item` / `ItemCategory` / `UOM` / `Location` | `models/InventoryManagement/Items.py:17,34,56`, `Locations.py` — **`Item.on_hand(location=None)` is a live `SUM` over `StockMove`, `Items.py:116-125`; there is deliberately no stored on-hand column** | catalog + stock levels (L37) |
| `scm.ReorderRule` | `models/InventoryManagement/ReorderRules.py:61` `lead_time_days` | honest "expected back in stock" hint (a *supply* lead time, not a promise) |
| `scm.ReturnAuthorization` / `ReturnLine` | `models/ReturnsManagement/ReturnAuthorizations.py:51` (`RMA-`, `public_token`, `source="portal"`) | **4.10 already built the customer return request** |
| `scm.TradeDocument` | `models/ContractCompliance/TradeDocuments.py:73` (`TD-`) | BoL / commercial invoice / packing list |
| `scm.QualityInspection` / `InspectionResult` | `models/QualityManagement/QualityInspections.py:65` + the existing `scm:coa_report` | CoA download (4.9 explicitly deferred the customer-facing CoA to 4.16) |
| `crm.CustomerPortalAccess` | `apps/crm/models/CustomerService/CustomerPortalAccess.py:5` — `customer_party` FK, **`portal_user` = `OneToOneField(User)`**, `can_submit_cases`, `is_active` | **THE customer login binding. One user ⇒ one party. Do not build a second one.** |
| `crm.Case` / `CaseComment` | `apps/crm/models/CustomerService/Cases.py:5,120` — `origin="portal"`, SLA (`first_response_due`/`resolution_due`), CSAT (`satisfaction_rating`), `public_token`, `CaseComment.is_public` | the helpdesk engine 4.16 reuses |
| `crm.SlaPolicy`, `crm.KnowledgeArticle` + `kb_public` | `CustomerService/SlaPolicies.py`, `KnowledgeBase.py:5` | SLA targets + KB deflection, already public |
| `crm.ContractDocument` | `apps/crm/models/DocumentContract/Contracts.py:5` (`CTR-`, `account` FK `core.Party`) | **the CUSTOMER-side contract.** `scm.SupplierContract` is supplier-side — never show it to a customer |

### Spine verified NOT to exist (do not plan against it)
- **No customer price list / price book on the SCM side.** `Item` carries `standard_cost` / `average_cost` (COST),
  `SupplierCatalogItem` is purchase-side, and `crm.PriceBook`/`crm.Product` are a *different* product table with
  no mapping to `scm.Item` (`SalesOrders.py:196-200` says so explicitly). ⇒ portal price display can only be
  **"your last ordered price"** derived from `SalesOrderLine`, or hidden. A real price engine is **9.3**.
- **No image field on `scm.Item`** (`Items.py:56-102`) — catalog thumbnails need `core.Document` or nothing.
- **No `public_token` on `Shipment`** — an anonymous branded tracking link would need an additive column in 4.6.
- **No stored payment instrument anywhere** (the only gateway in the repo is the tenants-app Stripe subscription
  webhook) — "manage payment methods" is integration/later, not a table to invent.
- **No cold-chain models** (4.15 unbuilt, see above).

### The precedent that decides 4.16's architecture — SCM already has portal surfaces
`apps/scm/views/ReturnsManagement/Reports.py:1-43` (4.10) documents three deliberately-different surfaces and
4.16 must extend that pattern rather than reinvent it:
1. `portal_return_create` — `@login_required`, resolves the customer through **`crm.CustomerPortalAccess`**
   (`Reports.py:349-361`, a verbatim re-use of `crm.views…CustomerPortal._customer_portal_access`, with a local
   import because "SCM does not import CRM at module scope").
2. `returnauthorization_public` / `…_label` — **no decorator**; the unguessable `public_token` is the bearer
   credential; tenant is taken **off the object** (`request.tenant` is `None` for anonymous), the state guard
   lives in the lookup, and `obj.tenant.is_active` is re-checked.
3. `return_portal` — the **staff** console the sidebar bullet points at (**L32**).

**Consequences for 4.16, stated up front:**
- **No second login model.** `crm.CustomerPortalAccess.portal_user` is a `OneToOneField` on the user; a second
  SCM binding could disagree about *which party this user is* — an authorisation bug by construction. 4.16's new
  account row keys on the **customer Party**, not on the user.
- **All five sidebar bullets must point at STAFF pages** (L32; already applied at 4.1 "Vendor Portal" and 4.10
  "Return Portal"). The gated customer pages are secondary extras.

---

## Leaders surveyed (with source links)

1. **Sana Commerce Cloud** — ERP-native B2B web store / self-service portal (Dynamics + SAP); everything rendered
   live from the ERP — <https://www.sana-commerce.com/products/sana-commerce-cloud/customer-experience/> and the
   stock-presentation docs <https://support.sana-commerce.com/Content/Sana-User-Guide/Inventory/Stock-Presentation.htm>
2. **NetSuite SuiteCommerce MyAccount (SCMA)** — login-only customer portal: purchases, billing, quotes,
   subscriptions, support cases, settings; explicitly **no cart/checkout/new orders** —
   <https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/chapter_159786656208.html> ·
   <https://www.netsuite.com/portal/resource/articles/ecommerce/suitecommerce-myaccounts-online-self-service-portal-delivers-convenience-improved-customer-experience.shtml>
3. **OroCommerce** — B2B platform whose *schema* is corporate accounts, buyer roles, spending limits, approval
   workflows and RFQ — <https://oroinc.com/b2b-ecommerce/blog/10-essential-features-for-b2b-ecommerce-solutions/> ·
   <https://oroinc.com/b2b-ecommerce/blog/the-complete-guide-to-b2b-dealer-portals/>
4. **Epicor Commerce Connect / Prophet 21 customer portal** — distributor self-service: order status, invoice
   history, multiple ship-tos, live stock, customer SKUs/lists, contacts management —
   <https://www.epicor.com/en-us/products/digital-commerce/commerce-connect/> · <https://www.b2sell.com/blog/p21-customer-portal>
5. **Shopify B2B (Plus)** — company profiles with multiple locations, per-buyer permission levels, payment terms,
   customer-specific catalogs/price lists, sales-rep scoped access —
   <https://www.shopify.com/plus/solutions/b2b-ecommerce>
6. **Salesforce Experience Cloud + Service Cloud portal** — self-service hub over the same case/KB data agents
   use; sharing rules/permission sets expose Cases, Orders, Accounts, Contacts; 2026 adds Agentforce self-service
   agents — <https://smartbridge.com/salesforce-experience-cloud-customer-portals/> ·
   <https://noltic.com/stories/what-is-salesforce-experience-cloud>
7. **Zendesk help-center customer portal** — "My activities": requested tickets, **organization requests** (see
   your whole company's tickets), CC'd tickets, and a **customer-facing status vocabulary distinct from the agent
   one** — <https://support.zendesk.com/hc/en-us/articles/4408825864858-What-are-the-customer-portal-ticket-statuses> ·
   <https://support.zendesk.com/hc/en-us/articles/4780805182234-How-do-my-customers-see-their-tickets-if-they-re-in-multiple-organizations>
8. **project44 Movement** — real-time multimodal visibility: shipments stitched to **orders at SKU level**,
   milestone/ETA engine that fills carrier gaps, exception management, and granting visibility to *customers and
   partners* — <https://www.project44.com/platform/visibility/> · <https://www.project44.com/platform/>
9. **Unleashed B2B Portal** — wholesale portal add-on: browse, **real-time stock availability**, customer-specific
   pricing, favourites, reorder from order history, order-status monitoring —
   <https://www.unleashedsoftware.com/b2b-ecommerce-platform/> ·
   <https://support.unleashedsoftware.com/hc/en-us/articles/4405412640921-B2B-Portal-Introduction>
10. **Narvar (Track / Notify / Care)** — branded tracking page, 50+ proactive notification events (out-for-delivery,
    delivered/POD, missed delivery) across email/SMS/WhatsApp, explicitly sold as **WISMO deflection** —
    <https://corp.narvar.com/track> · <https://corp.narvar.com/notify> · <https://corp.narvar.com/solutions/customer-care>

*Context stat used below:* WISMO ("where is my order") is the single largest inbound support category,
**~25–40 % of ticket volume** (50–60 % at peak) — <https://wismolabs.com/what-is-wismo/> ·
<https://www.salesforce.com/commerce/wismo/>. That is why bullet 1 (Order Tracking) and bullet 4 (Support
Ticketing) are one design problem, not two.

---

## Feature catalog (4.16 only)

### Bullet 1 — Order Tracking ("real-time visibility of order status and location")

- **Order → shipment → milestone timeline on one page** — one screen showing the order header, its lines, the
  shipments that fulfil it and the event log · seen in: Sana, Epicor/P21, project44, Salesforce, Narvar ·
  priority: **table-stakes** · spine: **reads `scm.SalesOrder` + `scm.Shipment` (`sales_order` FK,
  `Shipments.py:43`) + `TrackingEvent`** — no new table · buildable now.
- **Line-level fulfilment / backorder visibility (SKU granularity)** — per line: ordered, allocated, backordered ·
  seen in: project44 (SKU-level order stitching), Sana order history, Oro · priority: **table-stakes** ·
  spine: derived via `SalesOrderLine.quantity_allocated()` / `quantity_backordered()` — **never stored** ·
  buildable now.
- **ETA / promised date + "delayed" flag** — the date the customer is told, and whether it has slipped · seen in:
  project44 (ETA engine that fills missing carrier milestones), Narvar (EDD), Sana · priority: **table-stakes** ·
  spine: `SalesOrder.promised_date` (stamped once at full allocation), `Shipment.eta` /
  `planned_delivery_date` / `is_delayed` · buildable now.
- **Exception surfacing (delay, customs hold, missed delivery)** — a customer-readable reason, not a raw code ·
  seen in: project44 exception management, Narvar missed-delivery flows · priority: **common** · spine:
  `Shipment.status="exception"` + `TrackingEvent.event_type in (exception, delayed, customs_hold)` ·
  buildable now (needs a customer-facing wording map — see Zendesk precedent below).
- **Customer-facing status vocabulary distinct from the internal one** — end users see a simplified status set ·
  seen in: Zendesk (documented portal statuses ≠ agent statuses), Narvar · priority: **common** · spine: a
  presentation mapping in the view/template over the existing `STATUS_CHOICES` — **no new column** · buildable now.
- **Company-wide vs own-records visibility** — a buyer sees their whole organisation's orders/tickets · seen in:
  Zendesk (organization requests), Salesforce sharing rules, Oro corporate accounts · priority: **common** ·
  spine: a policy field on the new PortalAccount. **Honest note:** `SalesOrder` has no "raised by portal user"
  column, so company-wide is the only faithful v1; per-user narrowing is deferred.
- **Multi-leg / multi-warehouse stitching** — several shipments and stops per order · seen in: project44
  (multimodal), Sana (multi-location) · priority: **common** · spine: reads `Load` / `LoadStop` · buildable now.
- **Proactive notifications (order confirmed / shipped / out-for-delivery / delivered)** — the actual WISMO
  killer · seen in: Narvar Notify (50+ events, email/SMS/WhatsApp), Sana, Salesforce · priority: **table-stakes
  in market** · spine: the hooks **already exist unfired** on `SalesOrder`
  (`confirmation_sent_at` / `shipped_notification_at` / `delivered_notification_at`, `SalesOrders.py:81-83`) ·
  **integration/later** — 4.16 may render "notified on <date>" and let staff stamp it; it must not invent a mailer.
- **Anonymous branded tracking link (no login)** — share a tracking URL with a warehouse clerk who has no account ·
  seen in: Narvar Track, project44 (grant access to customers/partners) · priority: **differentiator** · spine:
  would need an additive `public_token` on **4.6's** `Shipment` (the 4.4-extends-4.3 / 4.13-extends-`Item`
  precedent) · **deferred** — v1 tracking is login-gated; note the 4.10 residual risk (tokens never expire).

### Bullet 2 — Account Management ("user profiles, addresses, and payment methods")

- **Company account with several named users** — many buyers under one customer · seen in: Shopify (company
  profiles, multiple buyers), Oro (corporate account hierarchy), Epicor (add/remove company contacts), Sana ·
  priority: **table-stakes** · spine: **one `crm.CustomerPortalAccess` row per user (already exists)** +
  **one new PortalAccount row per `core.Party`** · buildable now.
- **Per-buyer permissions (what this account may see/do)** — price visibility, invoice visibility, ticket
  raising, document access · seen in: Sana ("roles and access rights… every user sees only what they should"),
  Shopify ("unique permission levels"), Oro (role-based buyers), Salesforce (permission sets) · priority:
  **table-stakes** · spine: entitlement flags on the new PortalAccount (party-level v1) · buildable now.
- **Spending limits & multi-step order approval chains** — buyer → approver by amount/category · seen in: Oro,
  Shopify · priority: **common** · spine: needs a per-user grant + an approval doc · **deferred** (and ordering
  itself is parked to 9.4/9.17).
- **Address book / multiple ship-to locations** — pick where this order goes · seen in: Epicor P21 ("manage
  multiple ship-to locations"), Shopify (locations), Sana · priority: **table-stakes** · spine: reads/writes
  **`core.Address`** (`kind="shipping"`, `party=` the customer) + a `default_ship_to` FK on PortalAccount ·
  buildable now · **flag for the todo agent:** `core.Address` has no postal-code field (already documented at
  4.10); do not design a form that implies one.
- **Contact details & who receives what** — emails/phones on file · seen in: Epicor, NetSuite (email
  preferences), Narvar (customer chooses email/SMS) · priority: **common** · spine: reads/writes
  **`core.ContactMethod`**; channel preference = small DATA-only fields on PortalAccount · buildable now
  (dispatch itself: integration/later).
- **Account balance / credit limit / payment terms widget** — financial transparency in the portal · seen in:
  Sana ("buyer widgets"), NetSuite (balances + statements), Epicor P21 (balances, credit limits, terms) ·
  priority: **common** · spine: **reads `accounting.CustomerProfile` (`credit_limit`, `credit_on_hold`,
  `payment_terms`) + `accounting.Invoice.balance_due()`** — L29, SCM computes no AR of its own · buildable now,
  gated by a PortalAccount flag.
- **Manage stored payment methods (vaulted card / ACH) & pay invoices online** — · seen in: NetSuite (pay full or
  partial by card), Shopify (vaulted cards, ACH), Sana (online + on-account + partial payments), Salesforce ·
  priority: **table-stakes in market** · spine: `accounting.Payment` exists but no instrument vault does ·
  **integration/later** — the bullet's "payment methods" is satisfied in v1 as *read-only terms + balance*; a real
  wallet needs a gateway and PCI scope this repo does not have.
- **Sales agent / CSR "view as this customer"** — staff see exactly what the buyer sees · seen in: Sana (agents
  log in on behalf of customers), Shopify (sales-rep scoped permissions) · priority: **differentiator** · spine:
  a **staff** page that renders the customer's projection server-side · buildable now · **security note for the
  todo agent:** render-as, never authenticate-as — no session swapping, no impersonation token.

### Bullet 3 — Document Retrieval ("invoices, POD, and contracts")

- **Invoice list + open/paid state + printable copy** — · seen in: every leader (NetSuite billing, Sana, Epicor
  "download invoice PDFs", Salesforce) · priority: **table-stakes** · spine: **reads `accounting.Invoice`
  filtered by `party`** (+ `balance_due()`); print = a print-friendly HTML page (the `hrm/…/relieving_letter.html`
  precedent) · buildable now.
- **Account statement / transaction history** — · seen in: NetSuite (printable statements), Epicor P21 ·
  priority: **common** · spine: a computed page over `accounting.Invoice` + `Payment` — **accounting already owns
  AR aging**; 4.16 links out rather than recomputing · buildable now (thin).
- **Proof of Delivery retrieval** — the signed delivery record · seen in: Narvar (delivery confirmation),
  Epicor (track shipments), every TMS · priority: **table-stakes** · spine: `Shipment.pod_received` /
  `pod_received_at` + the `pod_signed` `TrackingEvent` + any `core.Document` attached to the shipment ·
  buildable now.
- **Packing list / BoL / customs paperwork** — · seen in: Sana ("all documentation available in real time"),
  Epicor, distributor portals · priority: **common** · spine: reads **`scm.TradeDocument`** (4.12) · buildable now.
- **Contracts / agreements visible to the customer** — · seen in: Sana (quotes/contracts in one place), Oro
  dealer zones · priority: **common** · spine: reads **`crm.ContractDocument`** (`account` FK). **Never expose
  `scm.SupplierContract`** — that is supplier-side commercial data.
- **Certificates of Analysis / quality certificates per lot** — · seen in: distributor/manufacturer portals
  (documented in the dealer-portal literature; NavERP's own 4.9 research deferred "customer-facing CoA download"
  to 4.16) · priority: **differentiator** (decisive in chemicals/food/pharma) · spine: the existing
  `scm:coa_report` over `QualityInspection`/`InspectionResult`, surfaced as a share · buildable now.
- **Explicit, revocable, expiring share of a specific document + download audit** — who was given what, when it
  expires, how many times it was fetched · seen in: partner/dealer download zones (server-side packaged
  downloads, emailed links), Salesforce sharing model · priority: **differentiator** · spine: **NEW table** ·
  buildable now — and it is the one genuinely new thing this bullet needs.
- **Bulk/zip download of a selected document set** — · seen in: dealer portals (server-side ZIP, emailed link
  when large) · priority: **differentiator** · **deferred** (needs async/packaging).

### Bullet 4 — Support Ticketing ("complaints or queries regarding orders")

- **Raise a ticket *in the context of* an order / line / shipment / invoice** — the context is pre-filled, not
  retyped · seen in: NetSuite (support cases beside purchases), Salesforce (Cases exposed with Orders),
  Zendesk, Sana · priority: **table-stakes** · spine: **NEW link table wrapping `crm.Case`** — see build scope ·
  buildable now.
- **A supply-chain inquiry taxonomy** — WISMO, delivery exception, short shipment, damaged goods, wrong item,
  invoice dispute, return request, product question · seen in: WISMO literature (25–40 % of inbound volume;
  "my order arrived damaged" as a distinct claim initiation), Narvar Care, Zendesk · priority: **table-stakes** ·
  spine: `inquiry_type` choices on the new table · buildable now.
- **Threaded conversation the customer can read and reply to** — · seen in: Zendesk, Salesforce, NetSuite ·
  priority: **table-stakes** · spine: **reuses `crm.CaseComment` with `is_public=True`** — the CRM portal view
  already does exactly this (`crm/views/CustomerService/CustomerPortal.py:57-68`) · buildable now.
- **SLA targets + first-response clock** — · seen in: Zendesk, Salesforce, Freshdesk · priority: **common** ·
  spine: **reuses `crm.SlaPolicy` + `Case.first_response_due` / `resolution_due`** — already computed in
  `Case.save()` · buildable now, zero new code.
- **CSAT after resolution** — · seen in: Zendesk, Salesforce · priority: **common** · spine: reuses
  `Case.satisfaction_rating` / `satisfaction_at` · buildable now.
- **Organisation-wide ticket visibility (+ CC'd tickets)** — · seen in: Zendesk organization requests ·
  priority: **common** · spine: the PortalAccount visibility policy; **CC is deferred** (needs email).
- **Convert an inquiry into a return / claim** — the ticket becomes an RMA · seen in: NetSuite ("request
  returns" beside cases), Narvar Shield (claims → returns/exchanges), Salesforce · priority: **differentiator** ·
  spine: FK from the new inquiry to the **existing** `scm.ReturnAuthorization`, and re-use of 4.10's already-built
  `portal_return_create` · buildable now — **do not build a second RMA**.
- **Knowledge-base deflection before ticket creation** — · seen in: Zendesk, Salesforce · priority: **common** ·
  spine: `crm.KnowledgeArticle` + the already-public `kb_public` view · buildable now (a link, not a build).
- **AI agent / chatbot deflection** — · seen in: Salesforce Agentforce (2026), Narvar automated claims ·
  priority: **differentiator** · **integration/later**.

### Bullet 5 — Catalog Browsing ("available products and current stock levels")

- **Browse/search the item catalog by category** — · seen in: Unleashed (categories + catalogues), Sana, Epicor,
  Shopify · priority: **table-stakes** · spine: **reads `scm.Item` + `ItemCategory` + `UOM`** · buildable now ·
  note: `Item` has **no image field** — either attach `core.Document` or ship text-only (recommended).
- **Live stock availability, per warehouse** — · seen in: Unleashed ("accurate stock availability"), Sana
  (multi-location stock on the product page), Epicor P21 (live stock across warehouses) · priority:
  **table-stakes** · spine: **derived `Item.on_hand(location)` over the append-only `StockMove` ledger — never a
  stored column (L37)** · buildable now · **perf flag:** aggregate once per page with `annotate(Sum(...))`, not
  per row (the `recompute_allocation_status` docstring makes the same point).
- **Configurable stock *presentation*: hidden / text / colour band / exact quantity, with a low-stock
  threshold, varying by customer type** — · seen in: **Sana Stock Presentation** (exact amount, text, colour
  indicator, or hidden entirely; different rules for B2C, B2B and sales agents), Unleashed · priority:
  **common** and cheap · spine: `stock_display` + `low_stock_threshold` on the new PortalAccount · buildable now.
- **Available-to-promise (net of reservations)** — what the customer can actually have · seen in: Sana ("total
  available" vs "physical available"), project44 (in-transit inventory) · priority: **differentiator** · spine:
  derived `on_hand − Σ active SalesOrderAllocation.quantity` (the `exclude(status="cancelled")` rule at
  `SalesOrders.py:234`) · buildable now.
- **"Expected back in stock" for out-of-stock lines** — · seen in: Sana, Unleashed, distributor portals ·
  priority: **common** · spine: `ReorderRule.lead_time_days` — label it a *replenishment estimate*, not a promise ·
  buildable now.
- **Customer-specific catalog scoping** — this buyer only sees their assortment · seen in: Shopify
  (customer-specific catalogs), Oro (organization-aware catalogs), Unleashed (per-customer catalogues) ·
  priority: **table-stakes** · spine: `catalog_scope` (`all_active` / `previously_ordered` / `categories`) +
  an M2M to `ItemCategory` on the new PortalAccount · buildable now.
- **Customer-specific / negotiated pricing** — · seen in: Sana, Unleashed, Epicor P21, Oro, Shopify (price lists,
  volume breaks) · priority: **table-stakes in market** · spine: **GAP — no customer price master exists**
  (see "verified NOT to exist"). v1: `price_basis` = `hidden` | `last_ordered` (the customer's own most recent
  `SalesOrderLine.unit_price` for that item). A real price/promotion engine is **9.3** · buildable now in the
  reduced form only.
- **Favourites / saved lists / customer part numbers / quick-order pad / CSV upload** — · seen in: Unleashed
  (favourites), Epicor (customer SKUs + lists), Sana (quick order grid, file upload), Shopify (product lists) ·
  priority: **common** · spine: would be a 5th table · **deferred** (first candidate for the next 4.16 pass).
- **Reorder from order history / cart / checkout** — · seen in: everyone; **but NetSuite SCMA deliberately
  omits cart, checkout and new-order entry** · priority: **table-stakes in market**, out of scope here · spine:
  writing a `SalesOrder` from the portal belongs to 9.4/9.17/8.6. **Cheapest honest v1 inside 4.16:** a
  "request a reorder" that files a `PortalOrderInquiry(inquiry_type="reorder_request")` against the source
  order, which staff turn into a real order with the existing 4.5 create flow.

### Beyond the bullets (strong features NavERP.md doesn't name)

- **Portal enablement / adoption console for staff** — which customers have the portal switched on, which users
  are bound, who has never logged in · seen in: Sana (admin-created accounts), Oro, Salesforce · priority:
  **common** · spine: the new PortalAccount list + `crm.CustomerPortalAccess` counts · buildable now.
- **Portal activity audit (login, order viewed, document downloaded, inquiry raised)** — the evidence trail that
  makes "we told you on the 3rd" defensible, and the input to any deflection metric · seen in: Zendesk activity
  history, Narvar (tracking-page engagement / WISMO-reduction reporting), project44 (who was granted access),
  Salesforce · priority: **common** · spine: **NEW append-only table** — `core.AuditLog` cannot carry it
  (`ACTION_CHOICES` is create/update/delete only, `AuditLog.py:8`) · buildable now.
- **Per-account welcome/announcement message** — · seen in: Oro dealer zones, Sana · priority: **differentiator**
  · spine: a text field on PortalAccount · buildable now.
- **WISMO-deflection stat block** — inquiries per 100 tracked orders, downloads per share, self-service rate ·
  seen in: Narvar (sold on ~60 % WISMO deflection) · priority: **differentiator** · spine: computed over the new
  activity + inquiry tables · buildable now (thin, on the staff console).

---

## Recommended build scope (this pass — 4 tenant-scoped models)

All four are new tables. **Nothing in 4.5/4.6/4.3/4.10/`accounting`/`crm` is re-declared, extended or
re-numbered** — the rest of 4.16 is read-only pages and derived figures.

### 1. `PortalAccount` [`PAC-`] — *the account-level portal configuration and entitlement record*
Bullets: **Account Management** (primary), gates **Catalog Browsing** and **Document Retrieval**.
- One row per customer **`core.Party`** (`unique_together = ("tenant", "customer")`) — the "company account"
  every leader has (Shopify company profile, Oro corporate account, Zendesk organization). **It is not a login.**
  Users bind via the existing `crm.CustomerPortalAccess` (one-to-one on `User`); a portal page resolves
  `user → CustomerPortalAccess → customer_party → PortalAccount`, and **refuses when no PortalAccount row
  exists** (explicit per-customer opt-in, and it makes the staff console meaningful).
- Justified fields:
  - `customer` FK **`core.Party`** (PROTECT), `is_active`, `activated_on` — enablement console.
  - Entitlements (Sana roles/access rights, Shopify permission levels, Oro roles, Salesforce permission sets):
    `can_track_shipments`, `can_view_invoices`, `can_view_documents`, `can_raise_inquiries`,
    `can_request_returns` (routes to 4.10's existing `portal_return_create`), `show_credit_and_balance`.
  - Stock presentation (**Sana Stock Presentation**, Unleashed): `stock_display` ∈
    `hidden | availability_text | band | exact_quantity`, `low_stock_threshold`, `show_by_location`.
  - Catalog scope (Shopify catalogs, Oro organization-aware catalog, Unleashed catalogues):
    `catalog_scope` ∈ `all_active | previously_ordered | categories` + `catalog_categories` M2M
    **`scm.ItemCategory`**.
  - Pricing (the documented gap): `price_basis` ∈ `hidden | last_ordered`.
  - `default_ship_to` FK **`core.Address`** (SET_NULL) — Epicor P21 multi-ship-to.
  - Notification preference DATA hooks (Narvar channel choice, NetSuite email preferences):
    `notify_on_shipment`, `notify_on_delivery`, `notify_on_exception`, `preferred_channel` ∈ `email | sms | none`
    — **stamped/read only; 4.16 dispatches nothing** (the `SalesOrder.*_notification_at` posture).
  - `welcome_message` (Oro dealer zone), `support_email`, `notes`.
- Verified FKs: `core.Tenant`, `core.Party`, `core.Address`, `scm.ItemCategory`.

### 2. `PortalOrderInquiry` [`PIQ-`] — *a support ticket that is **about a specific order/shipment/invoice***
Bullet: **Support Ticketing** (primary); it is also the WISMO landing zone for **Order Tracking**.
- **Wraps `crm.Case` rather than forking the helpdesk.** `case` FK **`crm.Case`** (CASCADE) carries the thread
  (`CaseComment.is_public`), the SLA clocks, CSAT, ownership and the public status token — all already built and
  tested. SCM adds only the supply-chain context and outcome. *(SCM already FKs CRM: `SalesOrder.source_quote →
  crm.Quote`, `SalesOrders.py:60`.)*
  - **Rejected alternative:** adding `sales_order`/`shipment` columns to `crm.Case` — a cross-app schema edit in
    an SCM pass, and it would put SCM vocabulary in CRM's model. **Also rejected:** a second ticket table (L29's
    "one ledger" logic applied to the helpdesk).
- Justified fields:
  - Context: `sales_order` FK **`scm.SalesOrder`**, `sales_order_line` FK **`scm.SalesOrderLine`** (nullable),
    `shipment` FK **`scm.Shipment`** (nullable), `invoice` FK **`accounting.Invoice`** (nullable) — project44's
    order↔shipment↔SKU stitching, NetSuite's cases-beside-purchases.
  - `inquiry_type` ∈ `wismo | delivery_exception | short_shipment | damaged | wrong_item | quality |
    invoice_dispute | return_request | reorder_request | product_question | other` (WISMO literature + Narvar
    Care + the classic distribution claim set).
  - `requested_resolution` ∈ `information | redeliver | replace | credit | return | callback`.
  - `quantity_affected` (Decimal, nullable) — short-shipment/damage claims.
  - `outcome` ∈ `open | information_provided | credit_drafted | rma_raised | replacement_arranged | rejected |
    duplicate` + `resolved_at` (system-set).
  - `return_authorization` FK **`scm.ReturnAuthorization`** (SET_NULL) — the ticket→RMA conversion, pointing at
    4.10's existing document.
  - `source` ∈ `portal | staff`, `raised_by` FK `settings.AUTH_USER_MODEL` (editable=False).
- Verified FKs: `crm.Case`, `scm.SalesOrder`, `scm.SalesOrderLine`, `scm.Shipment`, `scm.ReturnAuthorization`,
  `accounting.Invoice`, `core.Tenant`.
- Behaviour to specify in the todo: creating a portal inquiry creates the `crm.Case` with
  `origin="portal"`, `account=<the portal party>` and the tenant's default `SlaPolicy` — exactly the shape of
  `crm.views…CustomerPortal.portal_case_create:92-98`, forced server-side.

### 3. `PortalDocumentShare` [`PDS-`] — *what this account may retrieve, and the proof it did*
Bullet: **Document Retrieval** (primary).
- Justified fields:
  - `portal_account` FK **`scm.PortalAccount`** (CASCADE) — the audience.
  - `doc_type` ∈ `invoice | pod | packing_list | trade_document | contract | coa | statement | other`.
  - Exactly one typed pointer (validated in `clean()`): `document` FK **`core.Document`**,
    `invoice` FK **`accounting.Invoice`**, `shipment` FK **`scm.Shipment`** (its POD),
    `trade_document` FK **`scm.TradeDocument`**, `contract` FK **`crm.ContractDocument`**.
  - `title` (customer-facing label — never leak an internal filename), `shared_by` (User, editable=False),
    `shared_at`.
  - `public_token` — `secrets.token_urlsafe(32)` minted once in `save()` (the `ReturnAuthorization.public_token`
    / `crm.Case.public_token` precedent; `secrets` is already re-exported from `scm/models/_base.py:17`).
  - **`expires_at`, `revoked_at`** — the improvement over 4.10's documented residual risk (its tokens never
    expire and cannot be revoked). Both enforced **in the lookup**, not after it.
  - `download_count`, `first_viewed_at`, `last_downloaded_at` (all editable=False) — the audit dealers' portals
    keep.
- Verified FKs: `core.Document`, `accounting.Invoice`, `scm.Shipment`, `scm.TradeDocument`,
  `crm.ContractDocument`, `core.Tenant`.
- **# WARNING for the todo agent (security):** a token only protects a file if the file is *served through the
  view*. `config/urls.py:19-20` serves `MEDIA_URL` directly **when `DEBUG`**, so in dev the underlying
  `/media/documents/...` path bypasses the token entirely. The download view must stream (`FileResponse`) and the
  build must not treat the token as protection for the media directory. Re-check `tenant.is_active` off the
  object (`request.tenant` is `None` for an anonymous visitor) — the `_public_rma` pattern,
  `ReturnsManagement/Reports.py:460-473`.

### 4. `PortalActivity` (append-only log — **no number prefix**, the `StockMove`/`TrackingEvent` posture)
Bullets: cross-cutting evidence for **Order Tracking**, **Document Retrieval**, **Support Ticketing**.
- `portal_account` FK, `user` FK (nullable — token visitors have none), `action` ∈
  `login | view_order | track_shipment | view_catalog | download_document | raise_inquiry | request_return |
  update_profile`, `at`, `object_label` (short human string), optional `sales_order` / `shipment` /
  `document_share` FKs, `ip_address`.
- **Why not `core.AuditLog`:** its `ACTION_CHOICES` are `create/update/delete` only (`AuditLog.py:8`) — it
  records *changes to records by staff*, not *reads by a customer*. Bending it would corrupt an existing
  audit surface.
- **List + detail only — no create/edit/delete views** (the append-only precedent). If scope must be cut, this is
  the model to cut first; the other three each carry a bullet.

### Read-only / derived pages that satisfy the bullets (no tables of their own)
*(the `scm:reorder_alerts` / `valuation_report` / `mrp_report` / `coa_report` precedent — a bullet may be a page)*

| Bullet | Staff page (sidebar target — **L32**) | Gated customer page (secondary extra) |
|---|---|---|
| Order Tracking | `scm:portal_order_tracking` — portal customers' open orders with shipment status, ETA, exception and POD state in one row (neither 4.5's order list nor 4.6's shipment list shows this join) | `scm:portal_order_list` / `scm:portal_order_detail` (timeline: lines + allocations/backorder + shipments + `TrackingEvent`s) |
| Account Management | `scm:portalaccount_list` (+ detail/form/delete) | `scm:portal_profile` — addresses (`core.Address`), contacts (`core.ContactMethod`), terms/credit read-only from `accounting.CustomerProfile` |
| Document Retrieval | `scm:portaldocumentshare_list` (+ share/revoke actions) | `scm:portal_documents` and the tokenised `scm:portal_document_download/<token>` |
| Support Ticketing | `scm:portalorderinquiry_list` — the triage queue (type, order, SLA state, outcome) | `scm:portal_inquiry_create` / `scm:portal_inquiry_detail` (thread over `crm.CaseComment`) |
| Catalog Browsing | `scm:portal_catalog_preview` — "as seen by customer X" (Sana's sales-agent view; render-as, never auth-as) | `scm:portal_catalog` — items in scope, availability per `stock_display`, ATP, last-ordered price |

**Portal home** (`scm:portal_home`) ties the gated pages together — the NetSuite MyAccount landing shape
(purchases · billing · documents · support · catalog), gated by `PortalAccount` entitlements.

---

## Belongs to sibling sub-modules (parked, not scoped here)

- Cart, checkout, order placement, promotions, price/discount engine, product search & discovery, storefront CMS,
  wishlists, reviews → **9.1 / 9.3 / 9.4 / 9.7 / 9.9 / 9.13 / 9.17**. (NetSuite SCMA ships a portal without a cart
  — that is the licence to park this.)
- Customer-specific **price lists / contract pricing / volume breaks** (Sana, Unleashed, Shopify, Oro) → **9.3**
  (+ 8.5 for quote pricing). 4.16 shows "your last ordered price" or nothing.
- Online invoice **payment** + stored payment instruments (NetSuite, Shopify, Sana) → **accounting 2.4 / 2.6** and
  a gateway integration; the AR document itself stays `accounting.Invoice` (L29).
- Order **amendment / cancellation with impact analysis**, revenue recognition → **8.6** (the 4.5 docstring
  already reserves this).
- Quote request / RFQ from the portal (Oro RFQ, NetSuite quotes) → **8.5 Quote & Proposal** / `crm.Quote`;
  supplier-side RFQ is **4.1**.
- Supplier/vendor self-service portal (login, acknowledge PO, submit invoice, upload certificates) → **4.1 /
  4.2** (both already parked it; L32 note at `navigation.py:774-777`).
- **3PL client** portal — client billing by volume/weight, SLA dashboards, client-ERP sync → **4.17**.
- Return **request** flow, RMA lifecycle, refunds, disposition → **4.10** (already built; 4.16 links to
  `portal_return_create`, adds nothing).
- Helpdesk engine — SLA policies, KB authoring, agent queues, CSAT surveys, public case token page → **CRM 1.4**
  (reused wholesale).
- Customer contract authoring/e-signature → **CRM 1.9** (`ContractDocument` / `SignerRecord`); supplier
  contracts → **4.2 / 4.12**.
- Carrier API / GPS / EDI ingestion of tracking events, webhooks to customer systems → **4.6** (event log) and
  **4.19 Integration & API Gateway**.
- Document folders, versioning, retention, watermarking, OCR → **Module 13 (DMS)**; `core.Document` stays the
  attachment.
- Cold-chain temperature evidence on a delivery → **4.15** (unbuilt — no FK available).

---

## Deferred (later passes / integrations)

- **Proactive customer notifications** (Narvar Notify's 50+ events; email/SMS/WhatsApp): 4.16 renders and stamps
  the existing `SalesOrder.*_notification_at` hooks and nothing more. Real dispatch needs 4.19 / a mail service.
- **Anonymous branded tracking link**: needs an additive `public_token` on 4.6's `Shipment`; v1 tracking is
  login-gated. Revisit with the L32/4.10 token-security checklist.
- **Per-user roles, spending limits, multi-step order approvals** (Oro, Shopify): needs a per-user grant row and
  an approval document; entitlements are party-level this pass.
- **Stored payment methods / pay-now** (NetSuite, Shopify, Sana): gateway + PCI scope; not inventable in-repo.
- **Favourites / saved lists / customer part numbers / quick-order pad / CSV order upload** (Unleashed, Epicor,
  Sana): the strongest candidate for a follow-up 4.16 pass — one small table.
- **Reorder that actually writes a `SalesOrder`**: parked to 9.4/9.17; the honest v1 is
  `inquiry_type="reorder_request"`.
- **Bulk/ZIP document packages** and emailed large-download links: needs async packaging.
- **AI self-service agent / chat deflection** (Salesforce Agentforce, Narvar automated claims): Module 10.
- **Catalog imagery**: `scm.Item` has no image field; either attach `core.Document` later or stay text-only.
- **Per-user "own records only" scoping**: `SalesOrder` records no portal originator, so company-wide visibility
  is the only faithful v1 (Zendesk's organization-requests default).
- **Portal-side multi-language / branding themes** (Sana, Narvar branded pages): presentation-layer work, no
  data-model impact.
