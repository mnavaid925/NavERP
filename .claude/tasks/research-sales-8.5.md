# Research — Sub-module 8.5: Quote & Proposal Management (CPQ) (Module 8 — Sales Management System, `sales`)

> Phase 1 output. Target pre-resolved: **8.5 Quote & Proposal Management (CPQ)**. Do not re-detect.
> NavERP.md 8.5 = lines 1334–1340 (five feature bullets).

---

## 1. Repo state checked first

### LIVE_LINKS actually present in `apps/core/navigation.py`
- `"8.1"` (line 2193), `"8.2"` (line 2205), `"8.3"` (line 2214), `"8.4"` (line 2229) are built and mapped.
- **No `"8.5"` entry exists in `LIVE_LINKS`** — 8.5 is the next unbuilt sub-module of Module 8. Confirmed by direct file inspection, not assumed.

### Spine entities VERIFIED to exist (recursive inspection over `apps/*/models/`)

| Class | File | Status & Role for 8.5 CPQ |
|---|---|---|
| `crm.Quote` | `apps/crm/models/SalesForceAutomation/Quotes.py:5` | **EXISTS** (`QUO-`). Canonical CRM quote header (`name`, `opportunity`, `account`, `price_book`, `status`, `subtotal`, `tax_total`, `total`, `discount_pct`, `terms`, `owner`). Flat, single-version, no bundle hierarchy, no approval workflow. |
| `crm.QuoteLine` | `apps/crm/models/SalesForceAutomation/Quotes.py:82` | **EXISTS**. Flat line item (`quote`, `product`→`crm.Product`, `description`, `quantity`, `unit_price`, `discount_pct`, `tax_pct`). No parent-line bundle nesting, no cost/margin tracking, not mapped to `scm.Item`. |
| `crm.Opportunity` | `apps/crm/models/SalesForceAutomation/Opportunities.py:5` | **EXISTS** (`OPP-`). Deal master with `amount`, `currency`, `probability`, `stage`, `owner`, `territory`, `forecast_category`. 8.5 quotes FK here. |
| `crm.Product` | `apps/crm/models/SalesForceAutomation/Products.py:5` | **EXISTS** (`PRD-`). Sales catalog product (`name`, `sku`, `product_type`, `unit_price`, `cost`, `tax_pct`, `is_active`, `margin_pct`). 8.5 bundles group these. |
| `crm.PriceBook` | `apps/crm/models/SalesForceAutomation/PriceBooks.py:5` | **EXISTS** (`PB-`). Price list with `price_adjustment_pct`, `currency_code`, `is_default`, `is_active`. |
| `crm.DocTemplate` | `apps/crm/models/DocumentContract/DocTemplates.py:6` | **EXISTS** (`TPL-`). HTML merge-template (`template_type` incl. `proposal`, `quote`, `contract`; `body` with Django merge variables). Reusable for 8.5 proposal templating. |
| `crm.ContractDocument` / `SignerRecord` | `apps/crm/models/DocumentContract/Contracts.py:5, 46` | **EXISTS** (`CTR-`). E-signature execution spine with URL-safe `token`, `viewed_at`, `signed_at`, `declined_at`, `ip_address`. Reference pattern for quote acceptance. |
| `core.Party` | `apps/core/models/Party.py:5` | **EXISTS**. Account / customer entity (`name`, `tax_id`, `kind`). |
| `scm.SalesOrder` | `apps/scm/models/OrderManagement/SalesOrders.py:20` | **EXISTS** (`SO-`). SCM 4.5 canonical sales order master. Already carries `source_quote = ForeignKey("crm.Quote")`. Destination of 8.5 Quote-to-Order ERP handoff. |
| `scm.SalesOrderLine` | `apps/scm/models/OrderManagement/SalesOrders.py:185` | **EXISTS**. Ordered item line (`sales_order`, `item`→`scm.Item`, `quantity_ordered`, `unit_price`, `discount_pct`, `tax_pct`). Note: docstring explicitly warns that `crm.QuoteLine.product` has no mapping to `scm.Item`, causing draft orders to require manual item picking. 8.5 CPQ lines resolve this by mapping both! |
| `scm.SalesOrderAllocation` | `apps/scm/models/OrderManagement/SalesOrderAllocations.py:15` | **EXISTS**. Soft inventory reservation (`sales_order_line`, `location`, `quantity`, `status` reserved/released/cancelled). Used for 8.5 automated inventory reservation. |
| `scm.Item` / `scm.UOM` | `apps/scm/models/InventoryManagement/Items.py:73, 51` | **EXISTS**. ERP stock item master (`sku`, `name`, `item_type`, `standard_cost`, `average_cost`). |
| `accounting.Currency` | `apps/accounting/models/GeneralLedger/Currencies.py:6` | **EXISTS**. Global currency master (`code`, `name`, `is_active`). |
| `accounting.TaxCode` | `apps/accounting/models/Tax/TaxCodes.py:6` | **EXISTS**. Tax code rate master (`code`, `rate_pct`). |
| `accounting.PaymentTerm` | `apps/accounting/models/AccountsPayable/PaymentTerms.py:6` | **EXISTS**. Commercial payment terms master. |

### Architectural Boundary: CRM Quoting (1.2) vs. Sales CPQ (8.5)
- **CRM 1.2 `Quote`** was built for high-velocity, simple sales: flat line items, single revision, manual discount %, no approval rules, no bundle options.
- **Sales 8.5 CPQ** provides enterprise Configure, Price, Quote capabilities:
  1. **Configure**: Product bundling, option groups, default/required components, and compatibility dependency rules (`requires`, `excludes`, `recommends`).
  2. **Price**: Margin waterfall, cost-plus/margin calculations, volume discounts, and automated multi-tier approval rules (`QuoteApprovalRule`).
  3. **Quote & Propose**: Multi-version revision management (`CPQQuote.revision_of`, `revision_number`), primary quote designation (`is_primary`), side-by-side diff comparison, and branded web proposal generation with e-signature tokens.
  4. **Convert**: Seamless automated order generation into `scm.SalesOrder`, linking directly to `scm.Item` and automatically triggering soft inventory reservations (`scm.SalesOrderAllocation`).
- **Spine Compatibility**: To maintain integrity across the ERP, `CPQQuote` links to `crm.Opportunity`, `core.Party`, `accounting.Currency`, and optionally stamps a canonical `crm.Quote` reference or creates the `scm.SalesOrder` directly with `source_quote` linkage.

### Number prefixes checked (Zero collisions)
- Used in `apps/sales/`: `ACPL`, `CMP`, `FAD`, `FCP`, `FCS`, `FSC`, `LNE`, `OTM`, `OUT`, `PIPE`, `WLR`.
- Used in `apps/crm/`: `ACC`, `CON`, `CTR`, `LEA`, `OPP`, `PB`, `PRD`, `QTA`, `QUO`, `TPL`, etc.
- Used in `apps/scm/`: `SO`, `PO`, `QT` (RFQ Supplier Quote), `PR`, `RFQ`, `BOM`, `WO`, `AST`, etc.
- **Assigned for 8.5**:
  - `CPQ` → `CPQQuote` (Enterprise CPQ Quote & Proposal) — **FREE, VERIFIED**
  - `BND` → `ProductBundleOption` (Product Bundle & Compatibility Option) — **FREE, VERIFIED**
  - `QAR` → `QuoteApprovalRule` (Quote Pricing & Discount Approval Rule) — **FREE, VERIFIED**

---

## 2. Leaders surveyed (with source links)

Domain: **CPQ (Configure, Price, Quote) & Proposal Management Software** — 9 market leaders surveyed across enterprise CPQ, mid-market CPQ, and proposal automation.

1. **Salesforce CPQ / Revenue Cloud** — Industry standard for product bundling, product rules (validation, alert, selection), pricing waterfall, and primary quote syncing.
   - Primary sources:
     - Product Bundling & Options: https://developer.salesforce.com/docs/atlas.en-us.cpq_dev_spec.meta/cpq_dev_spec/cpq_product_bundles.htm
     - Product Rules & Compatibility: https://help.salesforce.com/s/articleView?id=sf.cpq_product_rules.htm
     - Pricing Waterfall: https://help.salesforce.com/s/articleView?id=sf.cpq_pricing_flow.htm
2. **DealHub CPQ** — Leader in guided selling playbooks, dynamic questionnaires, DealRooms (interactive customer portals), and automated margin/discount approval matrices.
   - Primary sources:
     - Guided Selling & Bundles: https://dealhub.io/cpq/guided-selling/
     - DealRoom & Proposal Generation: https://dealhub.io/dealroom/
     - Approval Workflows: https://dealhub.io/cpq/approval-workflows/
3. **Oracle CPQ (formerly BigMachines)** — Enterprise industrial CPQ with multi-level configurable bundles, advanced pricing rules, multi-tier approvals, and native quote-to-order handoff.
   - Primary sources:
     - Oracle CPQ Overview: https://www.oracle.com/cx/sales/cpq/
     - Configuration Rules & Pricing: https://docs.oracle.com/en/cloud/saas/cpq/
4. **Conga CPQ (formerly Apttus)** — Complex constraint-based product configuration, dynamic discount schedules, margin guardrails, and document generation via Conga Composer.
   - Primary sources:
     - Conga CPQ Platform: https://conga.com/products/configure-price-quote-cpq
5. **Experlogix CPQ** — Premier manufacturing and B2B CPQ; visual rules engine, component dependencies, real-time BOM generation, and deep ERP integration.
   - Primary sources:
     - Experlogix CPQ Features: https://www.experlogix.com/cpq/
6. **PandaDoc** — Market leader in document & proposal generation, dynamic merge variables, conditional smart content blocks, revision history, and embedded e-signatures.
   - Primary sources:
     - PandaDoc Proposals & CPQ: https://www.pandadoc.com/proposals/
     - Smart Content & Variables: https://support.pandadoc.com/
7. **Proposify** — Proposal templating, dynamic pricing tables, client engagement tracking, and legally binding e-signatures.
   - Primary sources:
     - Proposal Automation: https://www.proposify.com/features
8. **Qwilr** — Web-first interactive quotes, selectable quote add-ons/tiers, instant e-signing, and prospect engagement analytics.
   - Primary sources:
     - Interactive Quoting: https://qwilr.com/features/quotes/
9. **HubSpot CPQ & Quotes (Commerce Hub)** — Native CRM quoting, product libraries, tiered pricing schedules, rules-based approval gates, and customer payment integration.
   - Primary sources:
     - HubSpot Quotes & CPQ: https://www.hubspot.com/products/sales/quotes

---

## 3. Feature catalog (this sub-module only)

### Bullet 1 — Quote Configuration (CPQ) (Product bundling, configurable options, compatibility rules, guided selling)
- **Hierarchical Product Bundling** — Group related products, software licenses, hardware, and services under a parent lead product. Supports static packages (fixed components), configurable bundles (customer/rep selects options), and nested options. · seen in: Salesforce CPQ, Oracle CPQ, DealHub, Experlogix · priority: **table-stakes**
  · spine: `ProductBundleOption` maps bundle parent `crm.Product` to child components with option groups; `CPQQuoteLine.parent_line` provides relational tree hierarchy on the quote.
- **Configurable Options & Option Groups** — Options categorized into structured groups (e.g. "Base Compute", "Storage Upgrades", "Warranty & SLA", "Implementation Services"). Each option specifies min/max quantity, default quantity, and whether it is required or optional. · seen in: Salesforce CPQ (Product Options), Conga CPQ · priority: **table-stakes**
  · spine: `ProductBundleOption.option_group`, `is_required`, `is_default`, `min_quantity`, `max_quantity`.
- **Compatibility & Dependency Rules** — Enforce business logic during configuration:
  - `Requires`: Selecting Option A mandates Option B (e.g. Enterprise Server requires 3-Year Support).
  - `Excludes / Incompatible`: Option A cannot be selected with Option C (e.g. 110V Power Supply excludes 230V Cord).
  - `Recommends`: Suggests complementary add-ons (cross-sell/upsell). · seen in: Experlogix, Salesforce CPQ (Product Rules), Oracle CPQ · priority: **table-stakes**
  · spine: `ProductBundleOption.compatibility_rule` (`none|requires|excludes|recommends`) + `depends_on_product` (`crm.Product`).
- **Guided Selling Wizard / Playbook** — Interactive questionnaire filtering the catalog by customer requirements (e.g., number of users, company size, deployment preference) to recommend the optimal bundle configuration. · seen in: DealHub Playbooks, Salesforce CPQ Guided Selling, Experlogix · priority: **differentiator**
  · spine: Guided selling view filtering `crm.Product` / `ProductBundleOption` records dynamically via HTMX modal/wizard.

### Bullet 2 — Pricing & Discount Approval (List price, volume discounts, tiered pricing, automated approval workflows)
- **Pricing Waterfall Engine** — Deterministic calculation sequence: List Price → Price Book Adjustment → Volume/Tier Discount → Discretionary Rep Discount → Net Unit Price → Line Subtotal. Computes line and total gross margins against unit cost. · seen in: Salesforce CPQ (Pricing Waterfall), Oracle CPQ · priority: **table-stakes**
  · spine: `CPQQuoteLine` fields (`list_price`, `unit_cost`, `discount_pct`, `discount_amount`, `unit_price`, `line_subtotal`, `margin_pct`) + `CPQQuote.recalc_totals()`.
- **Volume & Tiered Pricing Schedules** — Automated discount schedules based on line quantity breaks (e.g., 1–9 units = 0%, 10–49 units = 10%, 50+ units = 20%). · seen in: HubSpot CPQ, Oracle CPQ, Conga CPQ · priority: **common**
  · spine: Tier calculation logic in `QuoteProposal/pricing.py` evaluated during line entry/update.
- **Margin Protection & Cost Visibility** — Live margin computation at both line and quote header levels (`(Total Price - Total Cost) / Total Price * 100`). Alerts reps when deal margin drops below profitability floor. · seen in: Experlogix, DealHub, Conga · priority: **common**
  · spine: `CPQQuote.total_cost`, `CPQQuote.margin_pct`, `CPQQuoteLine.unit_cost`.
- **Automated Approval Workflows (Discount & Margin Gates)** — Rules-based approval routing:
  - If discount > threshold (e.g., >10% requires Manager, >25% requires Director, >40% requires VP/CFO).
  - If margin < floor (e.g., <20% triggers mandatory Finance approval).
  - If total deal amount > ceiling.
  - Locks quote from being presented or converted until approved. Supports approve/reject actions with audit comments. · seen in: DealHub, Salesforce Advanced Approvals, Oracle CPQ, HubSpot · priority: **table-stakes**
  · spine: `QuoteApprovalRule` model + `CPQQuote.approval_status` (`not_required|pending|approved|rejected`) + `approved_by`, `approved_at`, `approval_comments`.

### Bullet 3 — Proposal Generation & Templating (Branded proposal templates, dynamic content insertion, e-signature integration)
- **Branded Proposal Document Templating** — Clean, executive-ready HTML/PDF proposal generation including tenant branding/logo, company details, customer address, executive summary, itemized pricing tables, and legal terms. · seen in: PandaDoc, Proposify, Qwilr, Conga Composer · priority: **table-stakes**
  · spine: Reuses `crm.DocTemplate` (with `template_type='proposal'`) + `CPQQuote.proposal_template`, rendered into `CPQQuote.proposal_content`.
- **Dynamic Content & Line Item Grouping** — Proposal rendering automatically groups items by bundle header and option category, clearly distinguishing included package items from optional add-ons, with subtotal breakdowns. · seen in: PandaDoc Smart Content, DealHub DealRoom · priority: **common**
  · spine: View generator parses `CPQQuoteLine.parent_line` and `line_type` to render structured proposal tables.
- **E-Signature Capture & Audit Trail** — Built-in electronic signing with URL-safe token, capturing signer name, timestamp, and IP address. Locks document upon signature. · seen in: PandaDoc, Proposify, Qwilr, HubSpot, CRM 1.9 `SignerRecord` · priority: **table-stakes**
  · spine: `CPQQuote.signing_token`, `signed_at`, `signer_name`, `signer_ip`. Follows the proven pattern from `crm.ContractDocument`.

### Bullet 4 — Quote Versioning & Comparison (Side-by-side quote versions, revision history, customer-facing quote portals)
- **Audit-Grade Quote Versioning & Revisioning** — Multiple revisions of a quote for a single deal (v1, v2, v3). Revising an existing quote creates an immutable clone linked via `revision_of` and increments `revision_number`. Superseded versions are preserved and locked. · seen in: Salesforce CPQ, Conga CPQ, PandaDoc Version History · priority: **table-stakes**
  · spine: `CPQQuote.quote_group_id` (UUID), `revision_number`, `revision_of` (`ForeignKey("self")`), `is_primary`.
- **Primary Quote Designation** — Exactly one quote revision per deal is marked as Primary (`is_primary=True`). The primary quote's total automatically syncs to `crm.Opportunity.amount` and drives forecasting pipeline values. · seen in: Salesforce CPQ (Primary Quote checkbox) · priority: **table-stakes**
  · spine: `CPQQuote.is_primary` with tenant/opportunity unicity constraint and Opportunity amount synchronization.
- **Side-by-Side Version Comparison (Diff View)** — Visual comparison tool between any two revisions of a quote (e.g. v1 vs v2): highlights added/removed lines, quantity deltas, discount changes, price variance, and overall margin swing. · seen in: DealHub, PandaDoc · priority: **differentiator**
  · spine: Diff calculation view `quote_compare_view` comparing `lines` of two `CPQQuote` instances.
- **Customer-Facing Interactive Quote Portal** — Web-based portal accessed via secure token link where the customer can:
  - Review the proposal interactively.
  - Toggle optional add-on lines (`is_optional=True`) with live HTMX price updates.
  - Electronically sign and accept the quote. · seen in: Qwilr, DealHub DealRoom, PandaDoc · priority: **differentiator**
  · spine: Public route `/sales/quotes/portal/<token>/`, updating `CPQQuoteLine.is_selected` and recording signature.

### Bullet 5 — Quote-to-Order Conversion (Automated order creation, inventory reservation, ERP handoff)
- **Automated Sales Order Creation** — 1-click conversion from accepted `CPQQuote` directly into `scm.SalesOrder` (`SO-`):
  - Copies customer (`core.Party`), currency (`accounting.Currency`), payment terms, and notes.
  - Transforms `CPQQuoteLine` items into `scm.SalesOrderLine` records.
  - Automatically links physical stock SKUs (`scm.Item`) configured on the CPQ lines. · seen in: Oracle CPQ, Salesforce CPQ Order Generation, Experlogix · priority: **table-stakes**
  · spine: Converts to `scm.SalesOrder` and sets `CPQQuote.converted_order`.
- **Automated Soft Inventory Reservation (ATP Claim)** — For each converted line associated with an `scm.Item`, automatically generates an `scm.SalesOrderAllocation` record in status `reserved`, reserving availability-to-promise at the default fulfillment warehouse. · seen in: SCM 4.5 `SalesOrderAllocation` · priority: **table-stakes**
  · spine: Creates `scm.SalesOrderAllocation(sales_order_line=so_line, location=loc, quantity=qty, status="reserved")`.
- **Deal Lifecycle Handoff & Closed-Won Sync** — Converting to order advances `crm.Opportunity.stage` to `closed_won`, records an append-only `sales.OpportunityOutcome` (result="won"), stamps `CPQQuote.status = 'converted'`, and records a `core.AuditLog` entry. · seen in: Salesforce, HubSpot · priority: **table-stakes**
  · spine: Seamless orchestration across `sales.CPQQuote` → `scm.SalesOrder` → `crm.Opportunity` → `sales.OpportunityOutcome`.

---

## 4. Recommended build scope (this pass — 4 models)

All four models live in **`apps/sales/models/QuoteProposal/`**, using `TenantOwned` and `TenantNumbered` from `apps/sales/models/_base.py`. Re-export every model in `apps/sales/models/__init__.py`. Templates under `templates/sales/quotes/`.

### 1. `CPQQuote` `[CPQ-]` — Enterprise CPQ Quote Header & Lifecycle Master
`models/QuoteProposal/CPQQuotes.py`
- Inherits: `TenantNumbered`
- Auto-number: `NUMBER_PREFIX = "CPQ"` (e.g. `CPQ-00001`)
- Fields:
  - `name`: `CharField(max_length=255)` — descriptive quote title
  - `opportunity`: `ForeignKey("crm.Opportunity", on_delete=models.SET_NULL, null=True, blank=True, related_name="cpq_quotes")`
  - `account`: `ForeignKey("core.Party", on_delete=models.PROTECT, related_name="cpq_quotes")`
  - `contact`: `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="cpq_quotes_contact")`
  - `owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="cpq_quotes")`
  - `price_book`: `ForeignKey("crm.PriceBook", on_delete=models.SET_NULL, null=True, blank=True, related_name="cpq_quotes")`
  - `currency`: `ForeignKey("accounting.Currency", on_delete=models.PROTECT, related_name="cpq_quotes")`
  - `status`: `CharField(max_length=20, choices=[("draft","Draft"), ("in_review","In Review"), ("approved","Approved"), ("presented","Presented"), ("accepted","Accepted"), ("declined","Declined"), ("expired","Expired"), ("converted","Converted to Order")], default="draft")`
  - `valid_until`: `DateField(null=True, blank=True)`
  - **Versioning & Revision Control**:
    - `quote_group_id`: `UUIDField(default=uuid.uuid4, db_index=True)` — common thread across revisions
    - `revision_number`: `PositiveIntegerField(default=1)`
    - `revision_of`: `ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="revisions")`
    - `is_primary`: `BooleanField(default=True)` — drives Opportunity amount when True
    - `revision_notes`: `TextField(blank=True)`
  - **Financials & Waterfall Aggregates**:
    - `list_subtotal`: `DecimalField(max_digits=16, decimal_places=2, default=0)`
    - `discount_total`: `DecimalField(max_digits=16, decimal_places=2, default=0)`
    - `net_subtotal`: `DecimalField(max_digits=16, decimal_places=2, default=0)`
    - `tax_total`: `DecimalField(max_digits=16, decimal_places=2, default=0)`
    - `grand_total`: `DecimalField(max_digits=16, decimal_places=2, default=0)`
    - `total_cost`: `DecimalField(max_digits=16, decimal_places=2, default=0)`
    - `margin_pct`: `DecimalField(max_digits=6, decimal_places=2, default=0)`
  - **Approval Governance**:
    - `approval_status`: `CharField(max_length=20, choices=[("not_required","Not Required"), ("pending","Pending Approval"), ("approved","Approved"), ("rejected","Rejected")], default="not_required")`
    - `approval_rule`: `ForeignKey("sales.QuoteApprovalRule", on_delete=models.SET_NULL, null=True, blank=True, related_name="quotes")`
    - `approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="cpq_approved_quotes")`
    - `approved_at`: `DateTimeField(null=True, blank=True)`
    - `approval_comments`: `TextField(blank=True)`
  - **Proposal & E-Signature**:
    - `proposal_template`: `ForeignKey("crm.DocTemplate", on_delete=models.SET_NULL, null=True, blank=True, related_name="cpq_proposals")`
    - `proposal_content`: `TextField(blank=True)` — HTML merge snapshot
    - `signing_token`: `CharField(max_length=64, blank=True, unique=True, null=True)` — public portal token
    - `presented_at`: `DateTimeField(null=True, blank=True)`
    - `signed_at`: `DateTimeField(null=True, blank=True)`
    - `signer_name`: `CharField(max_length=255, blank=True)`
    - `signer_ip`: `GenericIPAddressField(null=True, blank=True)`
  - **ERP Integration Handoff**:
    - `converted_order`: `ForeignKey("scm.SalesOrder", on_delete=models.SET_NULL, null=True, blank=True, related_name="source_cpq_quotes")`
    - `converted_at`: `DateTimeField(null=True, blank=True)`
    - `crm_quote`: `ForeignKey("crm.Quote", on_delete=models.SET_NULL, null=True, blank=True, related_name="cpq_quotes")`
    - `terms`: `TextField(blank=True)`
- Key methods: `recalc_totals()`, `create_revision()`, `make_primary()`, `convert_to_sales_order()`.

### 2. `CPQQuoteLine` — Hierarchical Line Items, Options & Stock Mapping
`models/QuoteProposal/CPQQuoteLines.py`
- Inherits: `TenantOwned`
- Fields:
  - `quote`: `ForeignKey("sales.CPQQuote", on_delete=models.CASCADE, related_name="lines")`
  - `parent_line`: `ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="child_lines")` — enables bundle hierarchy
  - `line_type`: `CharField(max_length=20, choices=[("standard","Standard Item"), ("bundle_parent","Bundle Package"), ("bundle_component","Bundle Component"), ("optional_addon","Optional Add-on")], default="standard")`
  - `product`: `ForeignKey("crm.Product", on_delete=models.SET_NULL, null=True, blank=True, related_name="cpq_lines")`
  - `item`: `ForeignKey("scm.Item", on_delete=models.PROTECT, null=True, blank=True, related_name="cpq_lines")` — **resolves the SCM item mapping gap**
  - `description`: `CharField(max_length=255)`
  - `quantity`: `DecimalField(max_digits=14, decimal_places=4, default=1, validators=[MinValueValidator(Decimal("0.0001"))])`
  - `uom`: `ForeignKey("scm.UOM", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")`
  - `unit_cost`: `DecimalField(max_digits=14, decimal_places=2, default=0)`
  - `list_price`: `DecimalField(max_digits=14, decimal_places=2, default=0)`
  - `discount_pct`: `DecimalField(max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])`
  - `discount_amount`: `DecimalField(max_digits=14, decimal_places=2, default=0)`
  - `unit_price`: `DecimalField(max_digits=14, decimal_places=2, default=0)` — net unit price
  - `tax_pct`: `DecimalField(max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])`
  - `tax_code`: `ForeignKey("accounting.TaxCode", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")`
  - `line_subtotal`: `DecimalField(max_digits=14, decimal_places=2, default=0)`
  - `line_total`: `DecimalField(max_digits=14, decimal_places=2, default=0)`
  - `margin_pct`: `DecimalField(max_digits=6, decimal_places=2, default=0)`
  - `is_optional`: `BooleanField(default=False)` — customer toggle in portal
  - `is_selected`: `BooleanField(default=True)` — included in calculation
  - `sort_order`: `PositiveIntegerField(default=0)`
  - `configuration_notes`: `CharField(max_length=255, blank=True)`

### 3. `ProductBundleOption` `[BND-]` — Product Bundling & Compatibility Rules
`models/QuoteProposal/ProductBundles.py`
- Inherits: `TenantNumbered`
- Auto-number: `NUMBER_PREFIX = "BND"` (e.g. `BND-00001`)
- Fields:
  - `bundle_product`: `ForeignKey("crm.Product", on_delete=models.CASCADE, related_name="bundle_options")` — the parent package product
  - `component_product`: `ForeignKey("crm.Product", on_delete=models.CASCADE, related_name="bundled_as_option")` — the component or add-on product
  - `component_item`: `ForeignKey("scm.Item", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")` — default physical item mapping
  - `option_group`: `CharField(max_length=80, default="Components")` — e.g., "Hardware", "Software", "Support Tier", "Add-Ons"
  - `option_type`: `CharField(max_length=20, choices=[("component","Required Component"), ("accessory","Optional Accessory"), ("service","Related Service")], default="component")`
  - `min_quantity`: `DecimalField(max_digits=12, decimal_places=2, default=1)`
  - `max_quantity`: `DecimalField(max_digits=12, decimal_places=2, default=1)`
  - `default_quantity`: `DecimalField(max_digits=12, decimal_places=2, default=1)`
  - `is_required`: `BooleanField(default=False)`
  - `is_default`: `BooleanField(default=True)`
  - `unit_price_override`: `DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)` — special bundle pricing
  - `discount_pct`: `DecimalField(max_digits=5, decimal_places=2, default=0)`
  - `compatibility_rule`: `CharField(max_length=20, choices=[("none","None"), ("requires","Requires Dependent Product"), ("excludes","Incompatible With Dependent Product"), ("recommends","Recommends Dependent Product")], default="none")`
  - `depends_on_product`: `ForeignKey("crm.Product", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")`
  - `is_active`: `BooleanField(default=True)`
  - `notes`: `CharField(max_length=255, blank=True)`

### 4. `QuoteApprovalRule` `[QAR-]` — Pricing & Discount Approval Gates
`models/QuoteProposal/QuoteApprovalRules.py`
- Inherits: `TenantNumbered`
- Auto-number: `NUMBER_PREFIX = "QAR"` (e.g. `QAR-00001`)
- Fields:
  - `name`: `CharField(max_length=255)` — e.g. "Director Discount Gate (>15%)", "Margin Floor Protection (<20%)"
  - `rule_type`: `CharField(max_length=24, choices=[("discount_threshold","Discount % Ceiling"), ("margin_floor","Margin % Floor"), ("amount_ceiling","High Value Deal Review"), ("composite","Combined Discount & Margin")], default="discount_threshold")`
  - `max_rep_discount_pct`: `DecimalField(max_digits=5, decimal_places=2, default=10)` — discounts exceeding this require approval
  - `min_margin_pct`: `DecimalField(max_digits=5, decimal_places=2, default=20)` — margins below this require approval
  - `min_quote_amount`: `DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)` — threshold for deal value
  - `required_role`: `CharField(max_length=24, choices=[("sales_manager","Sales Manager"), ("sales_director","Sales Director"), ("vp_sales","VP of Sales"), ("finance_director","Finance Director"), ("cfo","Chief Financial Officer")], default="sales_manager")`
  - `priority`: `PositiveIntegerField(default=10)`
  - `is_active`: `BooleanField(default=True)`
  - `description`: `TextField(blank=True)`
- Key methods: `evaluate(quote)` — returns `(requires_approval, rule_triggered_or_none)`.

---

## 5. Belongs to sibling sub-modules (parked)

- **8.6 Order Management**: Commercial change orders, amendments with downstream impact analysis, cancellations, and ASC 606 revenue recognition schedules. 8.5 strictly hands off the created order to 8.6 / SCM 4.5.
- **8.7 Territory & Quota Management**: Territory assignment algorithms, quota rebalancing, and quota modeling. 8.5 reads existing territories/owners read-only.
- **8.15 Contract & Subscription Management**: Full legal clause redlining, contract negotiation workflow, subscription recurring renewals, and mid-term co-terming. 8.5 handles proposal delivery and immediate e-signing.
- **8.18 Integration & API Hub**: Third-party external CPQ connectors (Salesforce/SAP/EDI quote sync).
- **8.19 Master Data & Configuration**: Enterprise catalog master administration and global price book restructuring.

---

## 6. Deferred (later passes / external integrations)

- **3D / Visual CAD Product Configuration**: Visual CAD/3D rendering during configuration (typical of heavy machinery / Epicor CPQ).
- **Payment Gateway Direct Charge from Portal**: Collecting credit card/ACH deposits directly on the web quote portal (e.g. Stripe checkout).
- **DocuSign / Adobe Sign External API Sync**: Sending via third-party proprietary e-sign webhooks rather than NavERP's built-in cryptographic portal signing.
- **Complex Stair-Step Billing Tiers**: Advanced multi-tier meter billing schedules (handled when 8.15 Contract & Subscription ships).

---

## 7. Verification Checklist for the Todo Agent

- [ ] Ensure `apps/sales/models/QuoteProposal/` folder is used with all 4 models.
- [ ] Export `CPQQuote`, `CPQQuoteLine`, `ProductBundleOption`, `QuoteApprovalRule` in `apps/sales/models/__init__.py`.
- [ ] Verify `CPQ`, `BND`, `QAR` prefixes in `apps/sales/models/_base.py` / `TenantNumbered`.
- [ ] Map all 5 NavERP.md §8.5 bullet labels in `apps/core/navigation.py`:
  1. `"Quote Configuration (CPQ)"`: `sales:cpq_quote_list` (with bundle configurator)
  2. `"Pricing & Discount Approval"`: `sales:quote_approval_rule_list` (and approval queue)
  3. `"Proposal Generation & Templating"`: `sales:proposal_template_list` (and document builder)
  4. `"Quote Versioning & Comparison"`: `sales:quote_version_list` (and side-by-side diff)
  5. `"Quote-to-Order Conversion"`: `sales:quote_conversion_board` (and order/ATP handoff)
- [ ] Confirm `CPQQuote.convert_to_sales_order()` seamlessly instantiates `scm.SalesOrder` and soft-reserves stock with `scm.SalesOrderAllocation`.
