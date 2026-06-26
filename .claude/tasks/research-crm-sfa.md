# Research — Module 1.2: Sales Force Automation (CRM SFA) (crm-sfa)

## Leaders surveyed (with source links)

1. **Salesforce Sales Cloud / CPQ** — market leader in enterprise SFA; deep pipeline inspection, opportunity splits, CPQ discount schedules, and territory-based forecasting — https://www.salesforce.com/ap/products/sales-cloud/features/opportunity-pipeline-management/
2. **HubSpot Sales Hub** — mid-market SFA with native CPQ, deal pipeline with stage approvals, AI forecast ranges, and deal credit splits — https://www.hubspot.com/products/sales/deal-pipeline
3. **Microsoft Dynamics 365 Sales** — enterprise SFA with rich product catalog entities (product families/bundles/price levels/discount lists), opportunity-to-quote conversion, and territory-driven price list auto-selection — https://learn.microsoft.com/en-us/dynamics365/sales/developer/product-catalog-entities
4. **Zoho CRM** — mid-market SFA with territory management, 5-category forecasting (Pipeline/Best Case/Committed/Closed/Omitted), quota targets by role/territory hierarchy — https://www.zoho.com/crm/sales-force-automation/forecasting.html
5. **Pipedrive** — SMB-focused deal pipeline with weighted expected-value forecasting, customizable stages, and goal/quota tracking — https://www.pipedrive.com/en/products/sales/deal-management
6. **SugarCRM (Sugar Sell)** — mid-market with quote lifecycle (8 stages), product catalog, product groups on quotes, revenue line items, percentage/fixed discounts per line, PDF generation — https://support.sugarai.com/documentation/sugar_versions/14.0/ent/application_guide/opportunity_management/
7. **Freshsales** — mid-market with multiple pipelines, native CPQ, Freddy AI deal scoring and revenue forecasting, built-in e-signature on quotes — https://community.freshworks.com/deals-and-pipeline-management-11391
8. **Close CRM** — SMB/inside-sales focused; pipeline view with expected value (amount × confidence %), drag-and-drop Kanban, multi-pipeline support, annualized/monthly value toggle — https://help.close.com/docs/opportunity-pipeline-view
9. **DealHub CPQ** — specialist CPQ overlay for CRMs; multi-dimensional pricing (tiered/usage/fixed), discount guardrails, conditional approval routing, quote room, product bundling — https://dealhub.io/platform/cpq/
10. **PandaDoc CPQ** — quote-focused CPQ; advanced pricing tables, conditional approval workflows (triggered by discount level/margin), product line items, e-signature integration — https://www.pandadoc.com/cpq-software/
11. **Clari** — specialist revenue forecasting; forecast categories (Commit/Best Case/Pipeline), AI deal inspection, quota vs. actual tracking, territory/rep/team roll-ups — https://www.clari.com/products/forecast/

---

## Feature catalog by sub-module

### 1.2.1 Opportunity Management (Deals)

- **Kanban pipeline board** — drag-and-drop column view with deals as cards organized by stage; cards show deal name, account, amount, close date, and probability at a glance. Seen in: Salesforce, HubSpot, Pipedrive, Close, Freshsales, Zoho. Priority: **table-stakes**. Spine: reuses existing `crm.Opportunity`; new view only (no new table). Buildable now.

- **Deal detail fields: competitor, loss reason** — capture the primary competitor tracked during the deal and, on loss, the reason for loss (Price, Competition, Timeline, No Decision, Other). Seen in: Salesforce, Dynamics 365, Zoho, SugarCRM. Priority: **table-stakes**. Spine: enhance existing `crm.Opportunity` (+`competitor` CharField, +`loss_reason` CharField w/ choices, +`lost_at` DateTimeField). Buildable now.

- **Forecast category on opportunity** — independent of stage, reps assign each deal a forecast bucket (Pipeline / Best Case / Commit / Omitted / Closed) that drives the forecast rollup. Salesforce calls these "Forecast Categories"; Zoho uses the same 5; HubSpot maps stages to categories automatically. Seen in: Salesforce, Zoho, HubSpot, Dynamics 365, SugarCRM, Clari. Priority: **table-stakes**. Spine: enhance `crm.Opportunity` (+`forecast_category` CharField with choices). Buildable now.

- **Territory assignment on opportunity** — each deal belongs to a named sales territory (region, product line, vertical); used to scope pipeline views, assign default reps, and roll forecasts up by territory. Seen in: Salesforce, Zoho, Dynamics 365, SugarCRM. Priority: **common**. Spine: new `crm.Territory` table; Opportunity gets FK `territory`. Buildable now.

- **Opportunity team / commission-credit splits** — multiple reps can share credit for a deal; revenue splits must total 100%; overlay splits may exceed 100% (for SE, SDR, or channel credit). Seen in: Salesforce (revenue + overlay splits), HubSpot Sales Hub Enterprise (deal credit splits). Priority: **common**. Spine: new `crm.OpportunitySplit` table (opportunity FK, user FK, split_type, percentage). Buildable now.

- **Pipeline stage history / stage age** — record how long a deal has been in the current stage so managers can identify stalled deals. Seen in: Salesforce Pipeline Inspection, HubSpot, Clari. Priority: **common**. Spine: add `stage_changed_at` DateTimeField on `crm.Opportunity`; a stage-age property derives days. Buildable now.

- **Contact role classification** — assign opportunity-specific roles to related contacts (Primary Decision Maker, Champion, Technical Evaluator, Economic Buyer, etc.) to clarify stakeholder influence. Seen in: Salesforce, SugarCRM, Dynamics 365. Priority: **common**. Spine: new `crm.OpportunityContact` junction (opportunity FK, party FK, role CharField). Buildable now.

- **Opportunity amount: best/likely/worst** — three amount fields let reps express deal uncertainty range (Worst, Likely, Best case amounts), used for conservative vs. optimistic forecasting. Seen in: SugarCRM, Dynamics 365. Priority: **differentiator** (many simpler tools use only one amount field). Spine: optional enhancement to `crm.Opportunity` (+`amount_best`, `amount_worst`). Buildable now (use existing `amount` as "likely").

- **Inline pipeline editing** — edit deal fields (amount, stage, close date) directly on the pipeline/list view without opening the detail page. Seen in: Salesforce Pipeline Inspection, Pipedrive, HubSpot. Priority: **common**. Spine: no new table; HTMX patch endpoint. Buildable now.

- **Deal velocity / bottleneck metrics** — track average time per stage across all closed-won deals; surface stages where deals stall most. Seen in: Salesforce, Pipedrive, HubSpot, Clari. Priority: **differentiator**. Spine: computed from `stage_changed_at` and existing data; report view only. Buildable now as a simple aggregate report; advanced AI scoring is deferred.

- **AI predictive deal scoring** — ML model assigns a win probability score independent of the rep-entered probability, based on activity signals. Seen in: Salesforce Einstein, HubSpot, Freshsales Freddy AI, Clari. Priority: **differentiator**. Buildable: integration/later (requires ML inference service).

- **Multiple sales pipelines** — different pipeline definitions per product line, geography, or sales motion (e.g., New Business vs. Renewal). Seen in: Freshsales, Close, Pipedrive, HubSpot. Priority: **common**. Spine: new `crm.Pipeline` table with its own ordered stage definitions; Opportunity gets FK to Pipeline. Deferred for this pass (single default pipeline sufficient; multi-pipeline is a later enhancement).

---

### 1.2.2 Product Catalog (Quoting)

- **Sales product catalog** — a tenant-scoped list of products/services with SKU, name, description, unit of measure, cost, and list price. Separate from the not-yet-built `core.Item` (Module 5). Seen in: all 10 leaders. Priority: **table-stakes**. Spine: new `crm.Product` table (CRM-owned, analogous to existing `crm.ProductStock`; distinct because it holds sales-facing attributes like list price, category, and active flag). Buildable now.

- **Price books (regional/tier pricing)** — named price lists allowing different unit prices for the same product by region, customer tier, or contract type. Dynamics 365 uses `PriceLevel`; Salesforce CPQ uses Price Books; SugarCRM and Zoho use similar constructs. Seen in: Salesforce, Dynamics 365, SugarCRM, Zoho, DealHub. Priority: **table-stakes**. Spine: new `crm.PriceBook` (name, currency_code, is_default) + `crm.PriceBookEntry` (pricebook FK, product FK, unit_price, min_qty). Buildable now.

- **Quote header** — a formal quote document linked to an opportunity with quote number (QT-), status lifecycle (Draft → Sent → Accepted → Rejected → Expired → Closed), expiry date, currency, selected price book, billing/shipping addresses, and terms. Seen in: Salesforce, Dynamics 365, SugarCRM, HubSpot, Freshsales, Zoho. Priority: **table-stakes**. Spine: new `crm.Quote` (TenantNumbered QT-, FK to Opportunity, FK to PriceBook). Buildable now.

- **Quote line items** — individual product/service rows on a quote; each line has product (FK or write-in), quantity, unit_price (from price book or overridden), line_discount (% or fixed amount), line_tax_pct, and derived line_total. Seen in: all 10 leaders. Priority: **table-stakes**. Spine: new `crm.QuoteLine` (FK to Quote, FK to Product nullable, item_name, qty, unit_price, discount_pct, discount_amount, tax_pct, sort_order). Buildable now.

- **Quote-level discount and tax** — additional percentage or fixed discount applied to the entire quote subtotal (beyond per-line discounts); separate tax rate applied to the taxable subtotal. Seen in: SugarCRM, Dynamics 365, Salesforce CPQ, DealHub. Priority: **table-stakes**. Spine: fields on `crm.Quote` (discount_pct, discount_amount, tax_pct, shipping). Buildable now.

- **Quote total computation** — derived fields: subtotal (sum of line totals), discount subtotal, taxable subtotal, tax amount, grand total. No stored aggregate needed; computed on save or as properties. Seen in: all leaders. Priority: **table-stakes**. Spine: `subtotal`, `tax_amount`, `total_amount` stored on Quote (recalculated from lines, like existing `PurchaseOrder.recalc_total()`). Buildable now.

- **Printable quote (HTML print view)** — a formatted, browser-printable or "Print to PDF" HTML page showing the quote with all line items, totals, company logo, terms, and validity date. No WeasyPrint/ReportLab dependency. Seen in: SugarCRM (PDF Manager), Dynamics 365, Zoho, Freshsales. Priority: **table-stakes** (PDF library is deferred; HTML print-view is sufficient for this pass). Spine: no new table; a dedicated `quote_print` view renders a print-optimized template. Buildable now.

- **Quote → Opportunity sync** — when a quote is accepted, update the linked opportunity's amount to match the quote total and optionally advance the stage to "Proposal" or "Negotiation". Seen in: Salesforce, Dynamics 365, SugarCRM. Priority: **common**. Spine: logic in `quote_accept` view; no new table. Buildable now (quote→sales-order sync to Module 8 is deferred).

- **Product bundling** — group related products into a bundle sold as a single line item (e.g., "Starter Pack = Software + Support"). Seen in: Dynamics 365, Salesforce CPQ, DealHub. Priority: **differentiator**. Spine: self-FK on `crm.Product` or separate bundle table. Deferred for this pass (adds complexity without blocking core quoting).

- **Volume / tiered discount schedules** — automatically apply different discount percentages based on quantity ranges (Range type: all units at same rate; Slab type: units in each band at different rates). Seen in: Salesforce CPQ, DealHub. Priority: **differentiator**. Spine: new `DiscountSchedule` + `DiscountTier` tables. Deferred (manual per-line discount covers the initial need).

- **Approval workflow on quote discount** — when a rep applies a discount beyond a threshold, the quote is locked until a manager approves. Seen in: PandaDoc CPQ, DealHub, Salesforce CPQ. Priority: **differentiator** (already handled generically by existing `crm.ApprovalRequest`). Buildable via existing `WorkflowRule` + `ApprovalRequest` infrastructure; no new model needed. Deferred as a wiring task (not a new model).

- **E-signature on quote** — send a quote to the customer for electronic signing; existing `crm.ContractDocument` + `crm.SignerRecord` already models this. Seen in: HubSpot, Freshsales, PandaDoc. Priority: **common**. Spine: reuse existing `crm.ContractDocument`; link Quote to ContractDocument via nullable FK. Buildable as link field; real e-sign delivery is integration/later.

- **Write-in products (non-catalog items)** — allow adding a free-text product line to a quote without requiring a product catalog entry. Seen in: Dynamics 365, SugarCRM, Salesforce. Priority: **table-stakes**. Spine: `QuoteLine.product` is nullable; `item_name` CharField acts as fallback. Buildable now.

- **Currency on quote** — store the quote currency as a CharField (currency_code); amounts stored in that currency. No FX conversion for now. Seen in: SugarCRM, Dynamics 365, Zoho. Priority: **common**. Spine: `Quote.currency_code` CharField (default "USD"), matching existing CRM pattern. Buildable now.

---

### 1.2.3 Forecasting

- **Sales quota definition** — per-rep or per-territory revenue or unit target for a period (month/quarter/year). Seen in: Salesforce, Zoho, Clari, SugarCRM, HubSpot Sales Hub Enterprise. Priority: **table-stakes**. Spine: new `crm.SalesQuota` (tenant FK, user FK nullable, territory FK nullable, period_type month/quarter, period_start DateField, target_amount Decimal). Buildable now.

- **Weighted pipeline forecast** — sum of (amount × probability/100) across all open opportunities in a period; the primary forecast metric. Seen in: all leaders. Priority: **table-stakes**. Spine: derived from existing `Opportunity.weighted_amount` property; aggregate in a forecast dashboard view. No new table needed. Buildable now.

- **Forecast category rollup** — aggregate pipeline by forecast category (Pipeline / Best Case / Commit / Closed) for a given period and rep/territory, enabling quota gap analysis. Seen in: Salesforce, Zoho, HubSpot, Clari, SugarCRM. Priority: **table-stakes**. Spine: derived from `Opportunity.forecast_category` + `close_date` in a forecast dashboard view. No new table needed. Buildable now.

- **Quota vs. actual comparison** — show each rep's quota target alongside closed-won revenue for the period, and the gap remaining. Seen in: all major leaders. Priority: **table-stakes**. Spine: join `SalesQuota` with aggregate of `Opportunity` where `stage='closed_won'`. View/template logic only. Buildable now.

- **Monthly vs. quarterly forecast periods** — allow setting quotas and viewing forecasts in either monthly or quarterly buckets. Seen in: Zoho, Salesforce, Clari, SugarCRM. Priority: **table-stakes**. Spine: `SalesQuota.period_type` choices ('monthly', 'quarterly'). Buildable now.

- **Territory-based forecast rollup** — aggregate quota and pipeline for a territory and all its sub-territories (parent-child hierarchy). Seen in: Salesforce, Zoho, SugarCRM, Dynamics 365. Priority: **common**. Spine: `crm.Territory` with self-FK `parent`; forecast dashboard rolls up by territory tree. Buildable now.

- **Forecast by product line / category** — filter or break down the forecast by product category or product type. Seen in: Salesforce CPQ, Zoho, Clari. Priority: **common** (requires Product catalog to be in place first). Spine: aggregate `QuoteLine.product.category` across accepted quotes. Buildable now once Quote/Product models exist.

- **Top-down and bottom-up forecasting** — managers push down targets (top-down); reps submit their own projections which roll up (bottom-up). Seen in: Zoho, Clari, SugarCRM. Priority: **common**. Spine: `SalesQuota` supports both; a manager-submitted and rep-submitted amount could be represented by two quota rows or a `submitted_amount` field. Buildable now (simple model-level field).

- **Best/Worst/Likely amount ranges** — optional three-value amount on Opportunity supports conservative, expected, and optimistic forecasting modes. Seen in: SugarCRM (Best/Likely/Worst fields), Dynamics 365. Priority: **differentiator**. Spine: optional fields on `crm.Opportunity`. Buildable now.

- **AI/ML forecast accuracy** — machine-learning model predicts close probability independently of rep's stated probability; compares forecast to actuals historically to score accuracy. Seen in: Clari (98% accuracy claim), Salesforce Einstein, Zoho Zia. Priority: **differentiator**. Integration/later — requires external ML inference.

- **Pipeline coverage ratio** — displays total pipeline value ÷ quota target (benchmark: 3:1 for healthy pipeline). Seen in: HubSpot, Clari, Salesforce. Priority: **differentiator**. Spine: derived metric in forecast dashboard view. Buildable now as a computed value.

---

## Recommended build scope (this pass — 8 models / 3 views)

### Models

1. **Opportunity (enhance existing)** — add fields justified by competitive research:
   - `competitor` CharField(100, blank) — deal detail feature (Salesforce, Dynamics, Zoho)
   - `loss_reason` CharField(20, choices: price/competition/timeline/no_decision/other, blank) — set on Closed Lost (Salesforce, Zoho, SugarCRM)
   - `lost_at` DateTimeField(null, blank) — system-set when stage → closed_lost
   - `forecast_category` CharField(10, choices: pipeline/best_case/commit/omitted/closed, default: pipeline) — forecast rollup (Salesforce, Zoho, HubSpot, Clari)
   - `territory` FK to `crm.Territory` (null, blank) — territory-based forecasting (Salesforce, Zoho)
   - `stage_changed_at` DateTimeField(null, blank) — stage-age / stalled-deal detection (Salesforce Pipeline Inspection, Clari)
   - `amount_best` DecimalField(null, blank) — optimistic scenario (SugarCRM, Dynamics)
   - `amount_worst` DecimalField(null, blank) — conservative scenario (SugarCRM, Dynamics)
   Reuses: existing `crm.Opportunity` (enhances it in-place)

2. **Territory** [TER-] — named sales territory for assigning deals and scoping forecasts
   - `name` CharField(120)
   - `parent` FK self (null, blank) — sub-territory hierarchy (Salesforce, Zoho)
   - `description` TextField(blank)
   - `owner` FK AUTH_USER (null) — territory manager
   New table: `crm.Territory`

3. **OpportunitySplit** — credit distribution among reps for team selling
   - `opportunity` FK Opportunity CASCADE
   - `user` FK AUTH_USER SET_NULL
   - `split_type` CharField choices: revenue / overlay
   - `percentage` DecimalField(5,2) — revenue splits must total 100%; overlay can exceed
   - `notes` CharField(blank)
   New table: `crm.OpportunitySplit`. Justified by: Salesforce team selling, HubSpot deal splits.

4. **Product** [PRD-] — CRM-owned sales catalog item (distinct from `crm.ProductStock` which tracks stock; this is the outbound sales catalog)
   - `name` CharField(255)
   - `sku` CharField(64, blank)
   - `category` CharField(40, blank) — for product-line forecast grouping
   - `description` TextField(blank)
   - `unit_of_measure` CharField(20, default "Each")
   - `cost` DecimalField(12,2, default 0) — internal cost
   - `list_price` DecimalField(12,2, default 0) — default unit price
   - `is_active` BooleanField(default True)
   New table: `crm.Product`. Justified by: all 10 leaders have a product catalog; separate from `ProductStock` (which is inventory-tracking).

5. **PriceBook** [PBK-] — named price list for regional/tier pricing
   - `name` CharField(255)
   - `currency_code` CharField(3, default "USD")
   - `is_default` BooleanField(default False)
   - `description` TextField(blank)
   New table: `crm.PriceBook`. Justified by: Salesforce, Dynamics 365, SugarCRM, Zoho.

6. **PriceBookEntry** — product-to-price-book pricing override
   - `pricebook` FK PriceBook CASCADE
   - `product` FK Product CASCADE
   - `unit_price` DecimalField(12,2)
   - `min_quantity` DecimalField(5,2, default 1) — minimum qty for this price to apply
   - `is_active` BooleanField(default True)
   unique_together: (tenant, pricebook, product). New table: `crm.PriceBookEntry`. Justified by: Dynamics 365 PriceLevel/ProductPriceLevel, Salesforce price book items.

7. **Quote** [QT-] — formal sales quote linked to an Opportunity
   - `opportunity` FK Opportunity SET_NULL (null, blank) — link to deal
   - `account` FK core.Party SET_NULL — billing party (denormalized for standalone quotes)
   - `pricebook` FK PriceBook SET_NULL (null, blank)
   - `status` CharField choices: draft / sent / accepted / rejected / expired / closed
   - `valid_until` DateField(null, blank) — expiry date
   - `currency_code` CharField(3, default "USD")
   - `payment_terms` CharField(60, blank)
   - `notes` TextField(blank)
   - `subtotal` DecimalField(14,2, default 0) — recomputed from lines
   - `discount_pct` DecimalField(5,2, default 0) — quote-level % discount
   - `discount_amount` DecimalField(12,2, default 0) — quote-level fixed discount
   - `tax_pct` DecimalField(5,2, default 0) — quote-level tax rate
   - `tax_amount` DecimalField(12,2, default 0) — recomputed
   - `shipping` DecimalField(12,2, default 0)
   - `total_amount` DecimalField(14,2, default 0) — grand total (recomputed)
   - `owner` FK AUTH_USER
   - `contract` FK ContractDocument SET_NULL (null, blank) — link to e-sign envelope
   New table: `crm.Quote`. Justified by: all 10 leaders.

8. **QuoteLine** — a line item on a Quote
   - `quote` FK Quote CASCADE
   - `product` FK Product SET_NULL (null, blank) — nullable for write-in lines
   - `item_name` CharField(255) — snapshot or write-in
   - `description` TextField(blank)
   - `quantity` DecimalField(10,2, default 1)
   - `unit_price` DecimalField(12,2, default 0)
   - `discount_pct` DecimalField(5,2, default 0)
   - `discount_amount` DecimalField(12,2, default 0)
   - `tax_pct` DecimalField(5,2, default 0)
   - `sort_order` PositiveSmallIntegerField(default 0)
   - derived property `line_total` = quantity × unit_price × (1 - discount_pct/100) - discount_amount
   New table: `crm.QuoteLine`. Justified by: all 10 leaders (line-item quoting is universal).

9. **SalesQuota** — per-rep or per-territory revenue target for a period
   - `user` FK AUTH_USER SET_NULL (null, blank) — rep quota (null = territory quota)
   - `territory` FK Territory SET_NULL (null, blank) — territory quota
   - `period_type` CharField choices: monthly / quarterly
   - `period_start` DateField — first day of the period (month or quarter)
   - `target_amount` DecimalField(14,2, default 0) — quota target
   - `submitted_amount` DecimalField(14,2, default 0) — rep's own bottom-up projection
   New table: `crm.SalesQuota`. Justified by: Salesforce, Zoho, Clari, SugarCRM, HubSpot.

### Views (no new tables)

- **Pipeline Kanban view** (`crm/sales/pipeline/kanban.html`) — HTMX-powered Kanban grouping existing `Opportunity` rows by `stage`, showing amount/probability/account/close_date on each card; drag-and-drop stage change via HTMX PATCH; owner filter + territory filter. Justified by: all 10 leaders; Pipedrive's visual pipeline is a primary differentiator.

- **Forecast dashboard** (`crm/sales/forecast/dashboard.html`) — shows weighted pipeline by forecast_category vs. SalesQuota for the selected period; quota vs. closed-won; pipeline coverage ratio; territory/rep breakdown. Justified by: Salesforce, Zoho, Clari, HubSpot.

- **Quote print view** (`crm/sales/quote/print.html`) — print-optimized HTML template for the quote with all line items, totals, logo, and terms. Justified by: SugarCRM PDF, Dynamics 365 PDF Manager, Zoho. No PDF library — browser "Print to PDF" is sufficient.

---

## Deferred (later passes / integrations)

- **Multiple sales pipelines** — distinct pipeline definitions per product line / team; one default pipeline covers 90% of SMB use cases. Later enhancement when multi-pipeline is needed.
- **Product bundling / kits** — grouping products into a bundle sold as one unit; adds schema complexity (self-FK or bundle_line table). Later.
- **Volume / tiered discount schedules** — automated quantity-break discount application; manual per-line discount covers initial need. Later (requires `DiscountSchedule` + `DiscountTier` tables).
- **PDF library rendering** — WeasyPrint/wkhtmltopdf for true PDF output; browser "Print to PDF" covers the initial requirement. Integration/later.
- **E-signature delivery on quotes** — sending the quote PDF to a customer for signing via DocuSign/HelloSign; existing `ContractDocument`/`SignerRecord` models the tracking, but delivery requires an e-sign provider. Integration/later.
- **Quote → Sales Order sync** — pushing an accepted quote into Module 8 `SalesOrder`; blocked until Module 8 (Sales) is built. Deferred.
- **Quote → Invoice sync** — pushing accepted quote into Module 2 Accounting AR invoice; blocked until Module 2 is built. Deferred.
- **AI / ML predictive deal scoring** — win probability score derived from activity signals independent of rep's stated probability (Salesforce Einstein, Clari, Freshsales Freddy). Requires external ML inference service. Integration/later.
- **AI forecast accuracy / range prediction** — HubSpot / Clari style best/worst/most-likely AI forecast. Integration/later.
- **Commission payout calculation** — computing actual commission dollar amounts from `OpportunitySplit` percentages; payroll integration required. Deferred to Module 3 (HRM/Payroll) or a dedicated commission module.
- **Contact role junction (OpportunityContact)** — stakeholder roles on opportunities (Decision Maker, Champion, etc.). Useful but not blocking; can be added in a follow-up sub-module pass alongside Activity enhancements.
- **Real-time FX conversion** — multi-currency with live exchange rates; `currency_code` CharField is sufficient for now. Deferred to Module 2 (Accounting).
- **Inline pipeline editing (HTMX)** — editing amount/stage/close_date inline on the list/Kanban without a full page reload; lower priority than the Kanban board itself. Secondary pass.
- **Deal velocity / stage-age reporting** — average days per stage computed from `stage_changed_at` history; useful analytics but secondary to quota vs. actual reporting. Secondary pass.
- **Approval workflow wiring for over-discount quotes** — connect existing `WorkflowRule` + `ApprovalRequest` to quotes exceeding a discount threshold; no new model needed but requires wiring work. Secondary pass.
