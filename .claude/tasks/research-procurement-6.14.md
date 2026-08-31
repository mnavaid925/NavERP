# Research — Sub-module 6.14: Spend Analytics & Reporting (Module 6 — Procurement Management System, `procurement`)

> **Read this first.** 6.14 is an **analytics** sub-module. Its job is to *read* spend that already exists in the
> tree, not to re-declare it. The failure mode for this pass is **over-modelling**: four of the five NavERP.md
> bullets are best delivered as **computed pages with no new table**, and only three things in this domain are
> genuinely *stored facts* — a classification rule, a maverick finding, and a saved report definition (+ its
> snapshot). That is the recommended scope, and nothing more.

---

## Repo state checked first

### LIVE_LINKS built so far in Module 6 (`apps/core/navigation.py`)
`6.1 · 6.2 · 6.3 · 6.4 · 6.5 · 6.6 · 6.7 · 6.8 · 6.9 · 6.10 · 6.11 · 6.12 · 6.13` — **6.14 is the next unbuilt
key** (`navigation.py:1600` is the last `"6.13"` block; there is no `"6.14"`).

### Spine entities VERIFIED to exist (grep evidence, L28 — the ERD is intent, the grep is truth)

| Entity | Verified at | What 6.14 uses it for |
|---|---|---|
| `procurement.SupplierInvoice` [SIV-] | `apps/procurement/models/InvoiceVoucherManagement/SupplierInvoices.py:123` | **the primary spend fact** — `vendor`, `invoice_date`, `total`, `status`, `invoice_type`, `currency`, `purchase_order`, `payment_term` |
| `procurement.SupplierInvoiceLine` | `.../SupplierInvoiceLines.py:56` | **line-grain spend** — `line_total` (SIGNED), `quantity`, `unit_price`, `gl_account`, `item`, `po_line`, `sku_hint`, `description` |
| `scm.PurchaseOrder` [PO-] + `PurchaseOrderLine` | `apps/scm/models/ProcurementManagement/PurchaseOrders.py:15, :172` | **committed** spend basis; `requisition`, `ship_to`, `vendor`, `order_date`, `total` |
| `scm.PurchaseRequisition` [PR-] | `apps/scm/models/ProcurementManagement/PurchaseRequisitions.py:14` | the **department axis** — `org_unit` → `core.OrgUnit`; `APPROVAL_TIERS` thresholds for split-purchase detection |
| `scm.SupplierContract` [SC-] | `apps/scm/models/SupplierRelationshipManagement/SupplierContracts.py:13` | **the contract spine for maverick detection** — `party`, `status`, `start_date`, `end_date`, `contract_value` |
| `scm.ItemCategory` | `apps/scm/models/InventoryManagement/Items.py:34` | **the taxonomy** — already hierarchical (`parent`/`children`), tenant-scoped, `is_active`, and already has CRUD at `scm:category_list/_create/_edit/_delete` |
| `scm.Item` | `apps/scm/models/InventoryManagement/Items.py:73` | `category` FK — the free category axis wherever `SupplierInvoiceLine.item` is set |
| `procurement.CatalogItem` [PCI-] | `apps/procurement/models/CatalogManagement/CatalogItems.py:17` | off-catalog / non-preferred detection — `is_preferred`, `base_price`, `supplier`, `item`, `supplier_part_no`, `status`, **`contract` → `scm.SupplierContract`** |
| `procurement.CatalogPriceTier` | `.../CatalogManagement/Tiers.py:13` | contracted price benchmark — `min_quantity`, `unit_price`, `discount_pct`, `effective_price(base)`, `valid_from/until`, **`contract` FK** |
| `procurement.VendorSuspension` [VSU-] | `apps/procurement/models/VendorManagement/VendorSuspensions.py:27` | blocked-supplier maverick reason — `supplier`, `starts_on`, `ends_on`, `status` |
| `core.Party` / `core.OrgUnit` | `apps/core/models/OrgUnit.py:5` | supplier + department dimensions (never re-declare a vendor — it is a `PartyRole`) |
| `accounting.GLAccount` / `Currency` / `Bill` / `JournalEntry` | `apps/accounting/models/…` (used live by `SupplierInvoices.py:24`) | GL-account axis, currency split. **6.14 reads; it never posts** (L29) |
| `crm.AnalyticsReport` + `ReportSnapshot` | `apps/crm/models/AnalyticsReporting/Reports.py:6`, `Snapshots.py:5` | **the proven analytics shape to mirror** |
| `apps/crm/analytics.py` | file exists | the compute-layer pattern (widget/report result contracts, `range_bounds`, `_money`/`_pct`) |
| `accounting.ScheduledReport` | `apps/accounting/models/Reporting/ScheduledReports.py:6` | the scheduled-delivery pattern — **its own docstring says the delivery worker is deferred** |
| `apps/scm/analytics.py` | file exists, 2500+ lines | **the closest prior art and the biggest de-duplication risk — see below** |

### Spine entities VERIFIED NOT to exist (corrects two assumptions in the brief)

1. **There is no `Contract` model in `apps/procurement/models/ContractsManagement/`.** That folder holds
   `ContractClauseLink`, `ContractSigner` (`Contracts.py:22, :60`), `ContractClause`, `ContractMilestone` [CMI-],
   `ContractAmendment` [CAM-] — all of which hang off **`scm.SupplierContract`**. 6.8 deliberately extended the
   SCM contract rather than declaring a second one. **Maverick detection therefore FKs `scm.SupplierContract`.**
2. **There is no commodity-category model in `CatalogManagement/`.** `CatalogItem.category_text` is a **free-text
   CharField(120)** (`CatalogItems.py:81`). The only real, hierarchical, tenant-scoped taxonomy in the tree is
   **`scm.ItemCategory`** — reuse it; do not declare a `SpendCategory`.
3. **No FX-rate table exists anywhere.** Totals must be summed per currency with a `mixed_currency` flag, exactly
   as `scm/analytics.py:1396 _currency_split` already does. Do not invent a rate.
4. **No `CostCenter` model** — the only hit is `hrm.CostCenterProfile`, an HR entity. The cost-centre/department
   dimension is **`core.OrgUnit`**, reached through `PurchaseRequisition.org_unit` and `PurchaseOrder.ship_to`.

### ⚠️ The single biggest de-duplication risk: SCM 4.11 already ships a spend cube

`LIVE_LINKS["4.11"]` (`navigation.py:914-920`) maps **"Procurement Analytics" → `scm:spend_analytics`**, computed in
`apps/scm/analytics.py` §8 (`:1369-1866`). It already delivers, over **`PurchaseOrder` only**:

- `_r_spend_total` (`:1408`) — cube by **currency × supplier × GL account × `ship_to` OrgUnit**
- `_r_spend_off_contract_pct` (`:1448`) — one-query `Exists()` against `SupplierContract` covering `order_date`,
  plus the `requisition IS NULL` unrequisitioned proxy
- `_r_spend_top_supplier_share_pct` (`:1496`) — top-5 share + sole-source `sku_hint` count
- `_r_spend_tail_share_pct` (`:1533`), `_r_savings_negotiated` (`:1577`),
  `_r_savings_price_variance_opportunity` (`:1633`), cycle/lead time
- Reusable constants: `SPEND_PO_STATUSES = ("approved","sent","acknowledged","partially_received","received","closed")`
  (`:200`), `COVERING_CONTRACT_STATUSES = ("active","expiring")` (`:204`), `MAX_DETAIL_ROWS = 25` (`:154`).

**4.11 also wrote down exactly what it could NOT do**, and every one of those is 6.14's mandate
(`research-scm-4.11.md:519-547`): the drag-and-drop report builder, BI/Excel export, spend **classification into a
taxonomy**, and **contract-line-level compliance** were all explicitly deferred here, and the stated blockers were
"4.1 PO lines carry `sku_hint` free text, not an `Item` FK" and "4.2 built no contract↔item linkage".

**Both blockers are now gone.** `SupplierInvoiceLine` has a real `item` FK *and* a `gl_account` FK, and
`CatalogItem.contract` / `CatalogPriceTier.contract` supply the item↔contract linkage. That is what makes 6.14 a
genuinely new capability rather than a second copy of `scm:spend_analytics`.

### DECISION — which spend does 6.14's cube read? **Invoiced (recognised) spend, with committed as a second basis.**

**Primary basis = `SupplierInvoiceLine` → `SupplierInvoice`,** filtered to
`status__in = ("approved", "scheduled", "paid")` (the statuses past `approve()`, i.e. a `Bill` + `JournalEntry`
exist), excluding `draft/parked/captured/blocked/disputed/pending_approval/void/reversed`. Four reasons, each
evidenced above and in the market survey:

1. **It is what the products actually do.** Basware's Spend Insights explicitly covers "not only PO-based spend but
   also **non-PO-based** spend"; Ivalua aggregates "**AP vouchers, invoices**, P-cards, travel". Invoiced spend is
   "recognised spend"; PO spend is "commitment". Building the cube on invoices is the mainstream choice.
2. **It sees the spend where maverick buying actually hides.** A `SupplierInvoice` with
   `purchase_order_id IS NULL` (`invoice_type="service"`) is structurally invisible to 4.11's PO cube — and that
   PO-less invoice *is* the canonical maverick transaction.
3. **The dimensions are materially better.** `SupplierInvoiceLine` carries `gl_account` **and** `item`
   (→ `scm.Item.category` → `scm.ItemCategory`) at line grain; `PurchaseOrderLine` carries only `gl_account` and
   free text. The category axis only becomes real on the invoice side.
4. **Credit memos net out for free.** `SupplierInvoiceLine.line_total` is SIGNED and a credit memo's lines are
   negative by construction (`SupplierInvoiceLines.py:195`, `SupplierInvoices.py:407-416`), so a plain
   `Sum("line_total")` yields **net** spend with no special-casing.

**Secondary basis = committed PO spend** offered as a `basis` toggle on the dashboard and on `SpendReport`, so a
buyer can compare commitment against recognition (the "committed vs invoiced" gap is itself an insight). When the
toggle is `committed`, reuse 4.11's `SPEND_PO_STATUSES` verbatim so the two pages can never disagree, and put a
link to `scm:spend_analytics` on the page rather than restating its savings/cycle-time figures.

### Dimensions actually reachable (and how honest each one is)

| Axis | ORM path from `SupplierInvoiceLine` | Quality |
|---|---|---|
| Supplier | `invoice__vendor` → `core.Party` | **Strong** — always set (`PROTECT`) |
| GL account | `gl_account__code/name` | **Strong** — line-level, mandatory on non-PO lines (`SupplierInvoiceLines.py:187`) |
| Time | `invoice__invoice_date` + `TruncMonth`/`TruncQuarter` | **Strong** |
| Currency | `invoice__currency__code` | **Strong**, but no FX — split, never sum across |
| Category | `item__category` **→ else a `SpendClassificationRule` match → else `(Unclassified)`** | **Medium** — `item` is nullable; this is exactly why the rule model exists |
| Department / cost centre | `Coalesce(invoice__purchase_order__requisition__org_unit, invoice__purchase_order__ship_to)` → `core.OrgUnit` | **WEAK — a 3-hop nullable chain, NULL for every PO-less invoice.** Must render an explicit `(unassigned)` bucket and state the caveat on the page, the way `scm/analytics.py` prints `GL_AXIS_CAVEAT`. Do not pretend otherwise. |
| Contract | `CatalogItem.contract` / `CatalogPriceTier.contract` → `scm.SupplierContract` | **New in 6.9** — enables item-level (not just vendor-level) contract compliance |

### What the CRM 1.6 prior art gives 6.14 for free

Read and mirrored: `apps/crm/models/AnalyticsReporting/Reports.py`, `Snapshots.py`, `_choices.py`,
`apps/crm/analytics.py`, `apps/accounting/models/Reporting/ScheduledReports.py`.

- **The three-layer shape is already proven here:** a saved *definition* row (`AnalyticsReport`, `TenantNumbered`,
  `NUMBER_PREFIX="RPT"`, with `report_type` / `date_range` / `group_by` / `is_favorite` / `owner` /
  `last_run_at` editable=False), **live compute on every render** (nothing stored), and an explicit
  **snapshot** row (`ReportSnapshot`: `summary` JSONField for KPI cards + `data` JSONField for
  `{columns, rows, chart_type, chart_labels, chart_data}`, created only by a POST action, never by a form).
  6.14 copies this verbatim rather than inventing a shape.
- **The compute-module contract is already written down** (`crm/analytics.py:13-21`): scalar → `{kind, value,
  display, max, pct}`; series → `{kind, labels, data}`; table → `{kind, columns, rows}`; report result must be
  **JSON-serialisable so the snapshot can store it verbatim and re-render without recomputing**. Reuse it.
- **Import direction is fixed:** `analytics.py` imports `models`; `models` never imports `analytics`. It lives
  **flat at the app root** (`apps/procurement/analytics.py`) per the backend-structure rule 8. There is no
  `apps/procurement/analytics.py` today — this pass creates it.
- **`range_bounds(key)`** and the `_money`/`_num`/`_pct` display helpers can be lifted in shape from
  `crm/analytics.py:35-97`.
- **Scheduled delivery is a solved-and-deferred question**: `accounting.ScheduledReport` already exists with
  `report_type`/`frequency`/`recipients`/`last_run`, and its docstring says the worker is deferred. 6.14 does
  **not** add a second one.
- **6.1 already ships the CSV precedent** (`apps/procurement/views/DashboardPortal/SelfServiceReports.py:81-112`)
  including `_csv_safe()` formula-injection neutralisation — and its docstring says verbatim: *"there is no
  tenant-wide export — that is 6.14 Spend Analytics' job"*. Reuse `_csv_safe`, do not re-invent it.
- **6.1 owns per-user widget visibility** (`WidgetPreference`, `DashboardPortal/WidgetPreferences.py:18`, with a
  `"spend": "Spend Summary"` key already in `WIDGETS`). **6.14 declares no widget-preference model.**

---

## Leaders surveyed (with source links)

1. **Sievo** — best-of-breed spend analytics; the reference definition of the spend cube (Category / Cost Center /
   Supplier), AI classification at 98%+ coverage, supplier normalisation, ABC segmentation, tail spend, contract-
   compliance %, payment-terms analysis, price variance & benchmarking, savings tracking —
   [sievo.com/resources/spend-analysis-101](https://sievo.com/en/resources/spend-analysis-101)
2. **SpendHQ** — spend cube specialist; What / Who-supplier / Who-internal dimensions, sourcing-level taxonomy
   *distinct from* GL/UNSPSC codes, ML categorisation over heuristic rules, maverick spend, single-sourced spend,
   supplier fragmentation, contract renewal/expiry opportunity detection —
   [spendhq.com/spend-cube](https://www.spendhq.com/spend-cube/)
3. **JAGGAER Spend Analytics** — unified multi-source visibility; **Pareto views for the top suppliers driving 80%
   of spend**, duplicate-master detection, savings initiatives tracked to realised P&L, 65+ pre-built dashboards +
   custom reporting, IntelliClass NLP/ML classification at 95%+, **off-contract leakage + payment-term adherence
   monitoring**, cubes by plant/region/supplier/category/BU, tail-spend consolidation candidates —
   [jaggaer.com/solutions/spend-analytics](https://www.jaggaer.com/solutions/spend-analytics)
4. **Ivalua Spend Analysis** — aggregates ERP/AP/**invoices**/P-card/travel; **classification by business-managed
   rules with no code, fully viewable/editable/auditable in the UI**, on-demand (not batch) re-classification,
   custom multi-level taxonomies, Spend Workbench drill-down by supplier/category/entity/region/time, savings
   identification, **compliance monitoring that identifies maverick spending**, price-variance tracking,
   "opportunity canvas" —
   [ivalua.com/solutions/…/spend-analysis](https://www.ivalua.com/solutions/process/strategic-sourcing/spend-analysis/)
5. **Coupa Spend Analysis** — AI classification/standardisation/enrichment across spend + ERP systems,
   configurable dashboards without IT, **community benchmarking over anonymised peer data**, outlier/anomaly
   detection, savings-opportunity identification. Dashboards are described as highlighting *spend by category,
   supplier concentration, **maverick spend percentage**, and contract utilisation rates* —
   [coupa.com/products/procure-to-pay/spend-analysis](https://www.coupa.com/products/procure-to-pay/spend-analysis/) ·
   [coupa.com/blog/spend-analysis](https://www.coupa.com/blog/spend-analysis/)
6. **SAP Ariba Spend Analysis** (→ SAP Spend Control Tower) — visibility by supplier/buyer/category/part, **up to
   six levels of commodity classification** via ML + supplier intelligence + **custom mapping and rules engines**,
   peer/category/market benchmarking, configurable role-based dashboards, **pre-configured dashboards for maverick
   spend, supplier risk and contract compliance**, ad-hoc reporting to transaction-level detail —
   [sap.com/products/spend-management/spend-analytics-software](https://www.sap.com/products/spend-management/spend-analytics-software.html) ·
   [learning.sap.com/…/spend-analysis](https://learning.sap.com/products/intelligent-spend-management/ariba/spend-analysis)
7. **Zycus iAnalyze** (Merlin AutoClass) — **four classification levels**, ad-hoc spend reports organised by
   category / payment terms / supplier / diversity, personalised real-time dashboards, an **Automated Savings
   Opportunity Identifier**, role-based alerts, and — named explicitly — a **drag-and-drop dashboard builder** —
   [zycus.com/glossary/what-is-spend-cube-analysis](https://www.zycus.com/glossary/what-is-spend-cube-analysis) ·
   [procurementtactics.com/spend-analysis-software](https://procurementtactics.com/spend-analysis-software/)
8. **GEP SMART Spend Analysis** — taxonomy-agnostic classification engine, **opportunity-finder algorithms**,
   **real-time alerts when spend thresholds are exceeded**, forecast workbench for spend-trend projection —
   [gep.com/software/gep-smart/procurement-spend-analysis-software](https://www.gep.com/software/gep-smart/procurement-spend-analysis-software)
   (feature detail cross-read from the comparison below)
9. **Basware Analytics / Spend Insights** — the **invoice-data-first** spend analytics case: 100% spend visibility
   built from captured invoices, a single view of **PO *and* non-PO, direct and indirect** spend with recommended
   actions; standard dashboards, KPIs and ad-hoc reporting across P2P; role-based alerts for overspend and
   contract expiry; taxonomy-flexible auto-tagging; network-wide peer benchmarks —
   [blog.basware.com/…/100-spend-visibility](https://blog.basware.com/en/new-basware-analytics-dashboard-provides-revolutionary-100-spend-visibility) ·
   [thescxchange.com/…/basware-spend-insights-dashboard](https://www.thescxchange.com/articles/4147-basware-introduces-spend-insights-dashboard-to-provide-single-view-of-entire-spend-recommendations)
10. **Simfoni** (+ Vitesse tail spend) — interactive spend dashboard across multiple ERPs, category-level analysis,
    buying-pattern identification, **vendor consolidation aimed squarely at tail spend**, KPI reporting —
    [simfoni.com/spend-analytics](https://simfoni.com/spend-analytics/)

**Cross-checks used for priority calls:** a 10-product comparison
([procurementtactics.com/spend-analysis-software](https://procurementtactics.com/spend-analysis-software/), which
also covers Oracle Fusion Spend Analytics, IBM Emptoris and Corcentric), a 2026 buyer's guide
([ignite.no/blog/spend-analytics-software](https://www.ignite.no/blog/spend-analytics-software)), the spend-cube
definitions at [zycus.com/glossary/what-is-spend-cube](https://www.zycus.com/glossary/what-is-spend-cube) and
[ivalua.com/glossary/spend-cube](https://www.ivalua.com/glossary/spend-cube/), the taxonomy primer at
[suplari.com/blog/spend-taxonomy-in-procurement-explained](https://suplari.com/blog/spend-taxonomy-in-procurement-explained),
and — the single most useful source for bullet 4 — the **maverick spend rate playbook** at
[umbrex.com/…/maverick-spend-rate](https://umbrex.com/resources/company-analysis/supply-chain-logistics/maverick-spend-rate/),
which gives the formula, the five classification rules, the addressable-spend exclusion and the benchmark bands.

---

## Feature catalog (this sub-module only)

### Bullet 1 — **Spend Dashboards** ("total spend by category, supplier, or department")
> **Delivered as a COMPUTED page with NO new table.** The spend cube is a `values().annotate()`, not a model.

- **The spend cube itself — supplier × category × department × time, one measure re-sliced** — the defining
  artefact of the domain · seen in: Sievo, SpendHQ, Zycus, Ivalua, JAGGAER, SAP Ariba, Coupa (all ten) ·
  **table-stakes** · spine: reads `procurement.SupplierInvoiceLine` + `SupplierInvoice` (+ optional
  `scm.PurchaseOrder` basis); **no new table** · buildable now
- **KPI strip above the cube** — net spend, invoice count, distinct suppliers, average invoice value, % classified,
  maverick %, top-5 supplier share, PO-less share · seen in: Basware (standard dashboards + KPIs), Sievo (10 core
  KPIs incl. Spend Visibility, Spend Under Management, Contract Compliance), Coupa · **table-stakes** ·
  spine: computed · buildable now
- **Spend trend by month/quarter with period-over-period delta** · seen in: SpendHQ (trends & variance), Sievo,
  GEP (forecast workbench) · **table-stakes** · spine: `TruncMonth("invoice__invoice_date")` · buildable now
- **Drill-through from any cube cell to the transactions behind it** — the credibility feature; a number nobody can
  trace is a number nobody trusts · seen in: SAP Ariba ("ad-hoc reporting with transaction-level detail"), Ivalua
  (Spend Workbench drill-down), JAGGAER, Corcentric ("drill-through") · **table-stakes** · spine: existing
  `procurement:supplierinvoice_detail` from 6.13 — link, never re-render · buildable now
- **Committed vs invoiced (commitment vs recognition) basis toggle** — PO value vs invoiced value in the same
  window · seen in: Basware (PO *and* non-PO in one view), Ivalua (multi-source), JAGGAER · **common** and a real
  differentiator against 4.11's PO-only page · spine: `basis` GET param + `SPEND_PO_STATUSES` reused from
  `scm/analytics.py:200` · buildable now
- **Per-currency split with an explicit `mixed_currency` flag** — no FX table exists; summing face values across
  currencies silently lies · seen in: JAGGAER (multi-currency across BUs), Ivalua · **table-stakes for
  correctness** · spine: mirror `scm/analytics.py:1396` · buildable now
- **Spend-threshold alerts / overspend notifications** · seen in: GEP ("real-time alerts for spend threshold
  exceedances"), Basware (role-based alerts), Zycus · **common** · spine: `procurement.ProcurementAlert` (6.1)
  already exists — **defer**, and if wanted later it emits an alert row, not a new table
- **Community / peer benchmarking against anonymised external spend data** · seen in: Coupa ($10T community),
  SpendHQ ($8T data lake), SAP Ariba (market intelligence), Basware (network benchmarks) · **differentiator** ·
  **integration/later** — needs an external corpus; ship nothing

### Bullet 2 — **Custom Report Builder** ("drag-and-drop tool … bespoke reports")
> **The only bullet that genuinely needs a stored definition.** Mirror CRM 1.6 exactly.
> **NAMING HONESTY (the 6.13 "Invoice Capture (OCR)" → "Assisted Capture" precedent, applied here):** a
> drag-and-drop canvas is **not** what a server-rendered Django + Tailwind + HTMX page delivers. Only **Zycus**
> names drag-and-drop explicitly; the other nine describe *self-service / configurable / ad-hoc / custom*
> reporting. Ship it as **"Report Builder"** — a guided form where measure, up to two dimensions, grain, filters,
> Top-N and chart type are chosen from **dropdowns**, then rendered server-side. Put a one-line note on the page
> saying dimensions are selected, not dragged. **Do not use the words "drag and drop" anywhere in the code,
> templates, sidebar label or commit messages.**

- **Saved report definition (measure + dimensions + grain + filters), re-runnable and shareable** · seen in:
  Zycus ("ad hoc spend reports by category, payment terms, supplier, diversity"), SAP Ariba (ad-hoc reporting),
  Coupa ("configurable reports without relying on IT"), JAGGAER (custom reporting), Ivalua (custom KPIs), Basware
  (ad-hoc reporting) · **table-stakes** · spine: **new table `SpendReport`**, shaped on `crm.AnalyticsReport` ·
  buildable now
- **Favourites / pinning + owner** · seen in: Coupa, Ivalua (self-service dashboards), Zycus (personalised
  dashboards) · **common** · spine: `is_favorite` + `owner` fields on `SpendReport` (verbatim from
  `AnalyticsReport`) · buildable now
- **Point-in-time snapshot so a report can be compared period-over-period without re-querying history** · seen
  in: Sievo (monthly/quarterly refresh cadence), SpendHQ (refresh cycles), JAGGAER (savings tracked to realised
  P&L) · **common**, and the single most valuable non-obvious feature to copy from CRM 1.6 · spine: **new table
  `SpendReportSnapshot`**, shaped on `crm.ReportSnapshot` (`summary` + `data` JSONFields) · buildable now
- **Pre-built report library so the page is useful on day one** · seen in: JAGGAER ("65+ pre-built Tableau
  dashboards"), SAP Ariba (pre-configured), Ivalua ("value within weeks using pre-built reports"), Oracle ·
  **table-stakes** · spine: **no table** — the seeder creates ~6 `SpendReport` rows (spend by supplier, spend by
  category, spend by department, monthly trend, maverick by reason, unclassified spend) · buildable now
- **Role-based / shared vs private reports** · seen in: SAP Ariba (role-based dashboards), Zycus (role-based
  alerts) · **common** · spine: `owner` + an `is_shared` boolean is enough; full RBAC is **deferred**
- **Scheduled/subscribed delivery of a report by email** · seen in: Basware, JAGGAER, SAP Ariba, and the general
  BI pattern (Power BI subscriptions) · **common** · spine: `accounting.ScheduledReport` already models this and
  its worker is already deferred — **defer**; `SpendReport` + snapshot is the substrate it would point at

### Bullet 3 — **Category Spend Analysis** ("deep dive within specific commodity categories")
> **One new table (the classification rule) + one computed drill-down page.** The taxonomy itself is
> `scm.ItemCategory` — already hierarchical, already has CRUD. **Do not declare a `SpendCategory`.**

- **Spend classification into a category taxonomy, with an unclassified bucket** — the #1 defining capability of
  the category; every vendor leads with it · seen in: Sievo (98%+ coverage), SpendHQ (97% in weeks), JAGGAER
  (IntelliClass, 95%+), Coupa (AI classification), SAP Ariba (six levels), Zycus (four levels), Ivalua, Basware,
  GEP (taxonomy-agnostic) · **table-stakes** · spine: **new table `SpendClassificationRule`** mapping
  vendor / GL account / keyword → **existing `scm.ItemCategory`**; `item__category` passthrough where
  `SupplierInvoiceLine.item` is set; `(Unclassified)` otherwise · buildable now
- **Rules that a business user can read, edit and audit — no black box** — this is Ivalua's *explicit*
  differentiator ("view, manage and edit all classification rules via a simple UI", "complete traceability and
  explainable logic") and it is the honest thing a Django app can ship where the others ship ML · seen in:
  Ivalua, SAP Ariba ("custom mapping and rules engines"), GEP · **table-stakes here, differentiator in market** ·
  spine: `SpendClassificationRule` CRUD + a `preview()` action · buildable now
- **ML/NLP auto-classification and supplier normalisation/dedup** · seen in: all ten · **differentiator** ·
  **integration/later** — needs a classifier and a training corpus. Say so on the page; the rules engine is the
  shipped equivalent, not a claimed AI
- **"% of spend classified" as a headline KPI (spend visibility)** — how every product proves the classification
  is working · seen in: Sievo (Spend Visibility KPI), SpendHQ, JAGGAER · **table-stakes** · spine: computed ·
  buildable now
- **Classification workbench — unclassified spend ranked by value, with "create a rule from this row"** — turns
  the rule table from config into a workflow · seen in: Ivalua (business-managed rules, guided recommendations),
  SpendHQ · **common** · spine: computed page over unclassified lines + a pre-filled `SpendClassificationRule`
  form · buildable now
- **Category drill-down: suppliers in the category, share, trend, top items** · seen in: Ivalua (Spend Workbench),
  Sievo, Zycus, Simfoni, Oracle ("dashboards by category, region, business unit") · **table-stakes** · spine:
  computed · buildable now
- **Pareto / 80-20 supplier concentration within a category, with running cumulative %** — JAGGAER names it
  explicitly ("Pareto views identify the top suppliers driving 80% of spend") · seen in: JAGGAER, Sievo (ABC:
  A=70-80%, B=15-20%, C=5-10%), SpendHQ (fragmentation) · **table-stakes** · spine: computed over the supplier
  league table · buildable now
- **HHI concentration index (Σ share² × 10 000) beside the Pareto** — the standard single-number concentration
  measure; one extra pass over a league table already computed · **differentiator** (implied by every product's
  concentration/fragmentation view, named by none) · spine: computed · buildable now
- **Tail-spend view — the long tail of low-value suppliers as consolidation candidates** · seen in: Sievo, Simfoni
  (Vitesse), JAGGAER, GEP · **common** · spine: computed. ⚠️ 4.11 already ships `_r_spend_tail_share_pct` on the
  PO basis — 6.14's version is the **invoiced** twin; link across rather than duplicate the narrative
- **Sole-source / single-sourced category exposure** · seen in: SpendHQ ("single-sourced spend"), Sievo, Resilinc ·
  **common** · spine: computed — count of categories/items with exactly one supplier in the window · buildable now
- **Price variance for the same item across suppliers, with a quantified consolidation opportunity** —
  opportunity = Σ qty × (price paid − best price in window) · seen in: Sievo ("price differences among
  suppliers"), Ivalua ("measure price variance"), Zycus, GEP · **common** and **materially better here than in
  4.11**, because invoice lines have an `item` FK instead of a free-text `sku_hint` · spine: computed over
  `SupplierInvoiceLine` grouped by `item` (fall back to `sku_hint` when `item` is null, and say so) ·
  buildable now
- **ABC / A-B-C spend segmentation of categories** · seen in: Sievo (explicit tiers) · **common** ·
  spine: computed. Note `ReorderRule.abc_class` already exists in SCM for *inventory* ABC — this is a **spend**
  ABC over categories, a different thing; do not read the inventory one
- **External category price indices / should-cost / BOM roll-ups** · seen in: JAGGAER (should-cost, BOM),
  Sievo, GEP · **differentiator** · **integration/later**

### Bullet 4 — **Maverick Spend Tracking** ("purchases outside preferred contracts or suppliers")
> **One new table — the finding — plus one computed dashboard.** 4.11 already computes an off-contract *percentage*;
> what 6.14 adds is the **actionable worklist with a reason code and a disposition**, which is how every product
> actually surfaces non-compliance. The detection thresholds ship as **class constants**, not a policy table —
> the exact precedent set by `SupplierInvoice`'s tolerance bands (`SupplierInvoices.py:164-182`).

The [umbrex maverick-spend playbook](https://umbrex.com/resources/company-analysis/supply-chain-logistics/maverick-spend-rate/)
gives the formula and the rule set this bullet is built from:
**Maverick Spend Rate = maverick spend ÷ addressable spend**, where *addressable* excludes categories with no
approved channel (taxes, utilities, payroll, pre-approved exceptions); a **transaction-rate** twin
(maverick transactions ÷ total transactions) is reported beside it; benchmarks are **<5-10% best-in-class,
10-20% typical, >20-30% lagging**.

Its five classification rules map onto verified NavERP fields as follows — **this table is the
`REASON_CHOICES` list**:

| Reason code | Detection (all fields verified above) | Priority |
|---|---|---|
| `no_contract` | vendor has no `scm.SupplierContract` with `status in ("active","expiring")` whose `start_date`/`end_date` window covers the document date — the `Exists()` shape at `scm/analytics.py:1461-1467` | **table-stakes** (Sievo, Coupa, JAGGAER, Ivalua, SAP Ariba) |
| `po_less_invoice` | `SupplierInvoice.purchase_order_id IS NULL` and `invoice_type != "credit_memo"` — umbrex's "no-PO violation"; **invisible to 4.11 by construction** | **table-stakes** (umbrex; Basware's non-PO visibility) |
| `no_requisition` | `PurchaseOrder.requisition_id IS NULL` — the unrequisitioned buy, already used as a proxy at `scm/analytics.py:1474` | **table-stakes** |
| `off_catalog` | no approved `CatalogItem` (`status` approved, `is_active`) exists for that `item` / `supplier_part_no` at that supplier | **common** (umbrex "off-catalog", SpendHQ, Coupa contract utilisation) |
| `non_preferred_vendor` | an approved `CatalogItem` with `is_preferred=True` exists for the same `item`/`supplier_part_no` at a **different** supplier | **table-stakes** — this is literally the NavERP bullet's wording ("outside … preferred … suppliers") |
| `price_above_contract` | `unit_price` exceeds the applicable `CatalogPriceTier.effective_price(base)` (or `CatalogItem.base_price`) by more than the tolerance — umbrex's stated **>5%** | **common** (umbrex, Sievo price variance, Ivalua). **This is the item-level contract-leakage check 4.11 said it could not build** |
| `suspended_vendor` | an active `procurement.VendorSuspension` covers the supplier at the document date | **differentiator** — umbrex's "blocked suppliers" rule, and the data already exists |
| `split_purchase` | ≥N POs to one vendor inside W days, each below a `PurchaseRequisition.APPROVAL_TIERS` threshold, summing above it | **differentiator** — see the 6.17 boundary note below; ship only if the pass has room |

- **Maverick findings as a reviewable worklist with disposition (acknowledge / justify / remediate / dismiss)** ·
  seen in: Ivalua ("integrated workflow guides stakeholders through … compliance remediation"), JAGGAER
  (compliance & policy control monitoring), SAP Ariba (pre-configured maverick dashboards), Coupa · **table-stakes
  for this bullet** · spine: **new table `MaverickSpendFinding`** · buildable now
- **A false-positive escape hatch (`dismissed`) and an accepted-exception state (`justified`)** — without them the
  list is abandoned within a month; the same reasoning that made `duplicate_candidates()` a suspicion rather than
  an auto-reject in 6.13 (`SupplierInvoices.py:524-527`) · seen in: Ivalua, Coupa · **table-stakes** · buildable now
- **Idempotent re-scan** — re-running the detector must **update** an open finding, never mint a duplicate ·
  precedent in-repo: `SupplyChainAlert`'s `dedupe_key` + partial-open guard (`research-scm-4.11.md:490`) and
  `run_match()`'s delete-and-rebuild (`SupplierInvoices.py:604-605`) · **table-stakes for usability** ·
  spine: `dedupe_key` unique per tenant · buildable now
- **Addressable-spend denominator** — the rate is meaningless against total spend · seen in: umbrex (explicit),
  Sievo ("Spend Under Management") · **table-stakes** · spine: `is_addressable` boolean on the finding + an
  excluded-GL-account/category constant list; state the exclusion on the page · buildable now
- **Breakdown by department, supplier, requester, category and channel** · seen in: umbrex (six segmentation
  axes), Coupa (maverick % on the dashboard), SAP Ariba · **table-stakes** · spine: computed over the findings ·
  buildable now
- **Contract-utilisation / leakage value (what it cost vs what the contract said)** · seen in: Coupa ("contract
  utilisation rates"), JAGGAER ("off-contract leakage"), Sievo ("contract compliance rate") · **common** ·
  spine: `benchmark_amount` + derived `leakage_amount` on the finding, benchmarked against `CatalogPriceTier` ·
  buildable now
- **Contract-expiry / renewal opportunity flagged from spend** · seen in: SpendHQ (renewals, expirations, new
  vendor increases), Basware (contract-expiry alerts) · **common** · spine: `scm.SupplierContract.is_expiring_soon()`
  + `days_to_expiry()` already exist (`SupplierContracts.py:128-137`) — **read them**; 6.8/4.2 own the renewal
  workflow, 6.14 only surfaces the spend at risk
- **P-card / MCC misuse detection** · seen in: umbrex, Sievo (P-card sources) · **common** · **deferred** — no
  card-transaction source exists in the tree
- **Fraud pattern detection / anomaly outliers** · seen in: Coupa (AI fraud monitoring), Ivalua ("prevent fraud"),
  Oracle · **differentiator** · **belongs to 6.17** (see parked list) — except `split_purchase`, which is
  approval-policy avoidance and sits defensibly here; flag the boundary in the code comment either way

### Bullet 5 — **Data Export & Visualization** ("Excel/CSV, or integrating with BI tools like PowerBI")
> **Computed page + a download endpoint. No new table.**

- **CSV/Excel export of the current cube slice or a saved report's rows** · seen in: all ten (Power BI paginated
  export supports `.xlsx`/`.csv`; every suite ships an export button) · **table-stakes** · spine: **no table** —
  reuse `_csv_safe()` from `apps/procurement/views/DashboardPortal/SelfServiceReports.py:107`.
  ⚠️ **Security: every exported cell must pass through `_csv_safe`** — vendor names, descriptions and rule names
  are all user-authored, and Excel executes a leading `=`/`+`/`-`/`@` on open · buildable now
- **Export respects the active filters, not "everything"** — an export that ignores the filter set is the bug
  users report first · seen in: Power BI subscriptions (filters/bookmarks applied before delivery), Ivalua ·
  **table-stakes** · spine: same GET params drive the queryset and the CSV · buildable now
- **A row cap + an explicit "showing N of M" notice on export** · **common** · spine: mirror
  `MAX_DETAIL_ROWS`/`MAX_GROUP_ROWS` from `scm/analytics.py:146,154` · buildable now
- **Snapshot-as-export — download a frozen snapshot rather than re-running the query** · seen in: Sievo/SpendHQ
  refresh cadence, Power BI subscriptions · **common** · spine: `SpendReportSnapshot.data` renders straight to
  CSV with no recompute · buildable now
- **A live BI connector / read-only feed URL for PowerBI** · seen in: JAGGAER (REST/SFTP feeds, Tableau), Sievo
  ("BI integration"), Basware, Microsoft's Power BI procurement content packs · **differentiator** ·
  **integration/later** — a signed, tenant-scoped read-only endpoint is a security design of its own. State the
  honest position on the page: **CSV download today; a BI feed is not implemented.** Do not put "PowerBI" in a
  sidebar label that only downloads a CSV
- **PDF / print-friendly board pack** · seen in: SAP Ariba, Coupa (CFO-ready reporting) · **common** ·
  **deferred** — the print-letter precedent (`hrm/offboarding/relieving_letter.html`) exists if wanted later

### Beyond the bullets (strong features the five bullets do not mention)

- **Payment-terms & early-payment-discount analytics from the spend base** — unrealised discounts, late-payment
  exposure, terms distribution by supplier · seen in: **Sievo (explicit: "unrealized payment term discounts, late
  payment interests, or opportunities to negotiate better payment terms")**, JAGGAER ("payment-term adherence"),
  Basware (payment performance) · **common** · spine: `SupplierInvoice.payment_term`, `discount_date`,
  `discount_amount()`, `annualised_pct()` — **all already built and derived in 6.13**
  (`SupplierInvoices.py:490-517`) · buildable now, **but 6.13 already ships a discount dashboard**
  (`LIVE_LINKS["6.13"]` deep-links a `#discount` anchor) — 6.14 should show the *aggregate* trend and link across,
  not restate the working list
- **Savings-initiative pipeline (identified → approved → in sourcing → realised → validated)** · seen in: Sievo
  (initiative management), JAGGAER ("track initiatives from conception through realized value, reconciled against
  P&L"), Ivalua (opportunity canvas), GEP, SpendHQ (project pipeline with status/timeline/impact) ·
  **differentiator** · a genuinely storable workflow, and `research-scm-4.11.md:521-525` explicitly routed it to
  "6.5 / 6.14" · **DEFER** — it is a second sub-module's worth of lifecycle and would blow the 4-hour budget.
  Recommend it lands in **6.5 Sourcing Analytics** or a later 6.14 pass; note the hook, ship nothing
- **Supplier-master duplicate detection** ("Acme Corp" / "ACME Corporation") · seen in: JAGGAER ("spot duplicate
  master records"), Sievo (supplier normalisation), SpendHQ (NLP normalisation) · **common** ·
  spine: `core.Party` — **belongs to core/6.4 vendor management**, not to an analytics pass. Park it
- **ESG / diversity / carbon spend enrichment** · seen in: SpendHQ, Sievo, Ivalua, JAGGAER · **differentiator** ·
  **integration/later** (and `research-scm-4.6.md`/`4.11` already routed carbon to 4.12)

---

## Recommended build scope (this pass — 4 models in 3 entity files, + 5 computed pages)

Package path: `apps/procurement/{models,forms,views,urls}/SpendAnalytics/` (PascalCase sub-module folder per the
backend-structure rule), templates under `templates/procurement/spendanalytics/<entity>/{list,detail,form}.html`,
and a **new flat compute module `apps/procurement/analytics.py`** (rule 8 — `analytics.py` stays at the app root,
as in `apps/crm/analytics.py` and `apps/scm/analytics.py`). No `apps/procurement/analytics.py` exists today.

### 1. `SpendClassificationRule` — `models/SpendAnalytics/SpendClassificationRules.py`
**`TenantOwned`, no number** (config, not a document — the `ApprovalRoutingRule` / `ReceiptTolerancePolicy`
precedent, both `TenantOwned`).
Justified by: *spend classification into a taxonomy* (all 10 leaders), *business-managed auditable rules*
(Ivalua, SAP Ariba, GEP), *% of spend classified* KPI (Sievo, SpendHQ, JAGGAER).

- `name` CharField(120)
- `match_type` CharField choices
  `[("vendor","Supplier"), ("gl_account","GL Account"), ("keyword","Description / SKU keyword"), ("invoice_type","Invoice Type"), ("org_unit","Department / Cost Centre")]`
- `vendor` FK **`core.Party`** SET_NULL null/blank · `gl_account` FK **`accounting.GLAccount`** SET_NULL null/blank ·
  `org_unit` FK **`core.OrgUnit`** SET_NULL null/blank · `keyword` CharField(120) blank ·
  `invoice_type` CharField(20) blank (validated against `SupplierInvoice.INVOICE_TYPE_CHOICES`)
- `category` FK **`scm.ItemCategory`** PROTECT — **the taxonomy is reused, never re-declared**
- `priority` PositiveSmallIntegerField default 100 (**lower wins**; ties broken by `id` so the resolution is
  deterministic)
- `applies_to` CharField choices `[("both","Invoiced + Committed"), ("invoiced","Invoiced only"), ("committed","Committed (PO) only")]` default `both`
- `is_active` Boolean default True · `notes` TextField blank
- `match_count` PositiveIntegerField default 0 **editable=False** · `last_matched_at` DateTimeField null
  **editable=False** — both written only by the preview/apply action, never by the form
- `clean()`: the field required by `match_type` must be set (a `vendor` rule with no vendor matches everything);
  cross-tenant guard on `vendor` / `gl_account` / `org_unit` / `category`
- Methods: `matches(line)` (pure, unit-testable), `classmethod resolve(line)` → the winning category or `None`,
  `preview(start, end)` → count + value this rule would claim in a window
- Meta: `ordering = ["priority", "id"]`, indexes `(tenant, is_active)`, `(tenant, match_type)`
- FKs verified: `core.Party` ✓ · `accounting.GLAccount` ✓ · `core.OrgUnit` ✓ · `scm.ItemCategory` ✓

### 2. `MaverickSpendFinding` [**`MSF-`**] — `models/SpendAnalytics/MaverickFindings.py`
**`TenantNumbered`.** Prefix `MSF` verified free (existing procurement prefixes: CUB RQA POE CMI EBID VSU PCI EAUC
VPA CAM RXR VIS RFX PCO RQT RAM SEV DSC DSP BID RDS SIV ASN RTV BKO).
Justified by: the umbrex rule set + *maverick spend dashboards* (SAP Ariba, Coupa), *off-contract leakage*
(JAGGAER), *compliance monitoring & remediation workflow* (Ivalua), *maverick spend %* (Coupa dashboards).

- `reason` CharField choices — **the eight codes in the bullet-4 table above**:
  `[("no_contract","No active contract"), ("po_less_invoice","Invoice with no purchase order"), ("no_requisition","PO raised with no requisition"), ("off_catalog","Item not on an approved catalogue"), ("non_preferred_vendor","Bought from a non-preferred supplier"), ("price_above_contract","Price above the contracted/catalogue price"), ("suspended_vendor","Supplier was blocked or suspended"), ("split_purchase","Orders split below an approval threshold")]`
- `severity` CharField `[("low","Low"),("medium","Medium"),("high","High")]` with a class-constant
  `SEVERITY_BY_REASON` default map (constants, not a policy table — the `SupplierInvoice` tolerance precedent)
- `status` CharField `[("open","Open"),("acknowledged","Acknowledged"),("justified","Justified — accepted"),("remediated","Remediated"),("dismissed","Dismissed — false positive")]` default `open`, moved **only** by guarded verb methods that re-check their own guard and return a bool (the 6.13 discipline)
- Source pointers (nullable, `SET_NULL`, at least one required in `clean()`):
  `supplier_invoice` FK **`procurement.SupplierInvoice`** · `invoice_line` FK **`procurement.SupplierInvoiceLine`** ·
  `purchase_order` FK **`scm.PurchaseOrder`**
- Dimensions stamped at detection so the dashboard groups in one query without four joins:
  `vendor` FK **`core.Party`** PROTECT (always set) · `category` FK **`scm.ItemCategory`** SET_NULL ·
  `org_unit` FK **`core.OrgUnit`** SET_NULL · `contract` FK **`scm.SupplierContract`** SET_NULL
  ("the agreement this should have been on", when one exists) ·
  `catalog_item` FK **`procurement.CatalogItem`** SET_NULL (the preferred alternative, for `non_preferred_vendor`
  and `price_above_contract`)
- `document_date` DateField (the invoice/order date — what the window filters on, indexed) ·
  `amount` Decimal(18,2) editable=False (spend at risk) · `benchmark_amount` Decimal(18,2) null
  (what it should have cost) · `leakage_amount` Decimal(18,2) editable=False, derived
  `max(0, amount − benchmark_amount)` in `save()`
- `is_addressable` Boolean default True — the umbrex denominator exclusion
- Governance: `dedupe_key` CharField(120) **editable=False** with `unique_together ("tenant","dedupe_key")` so a
  re-scan **updates** rather than duplicates; `detail` TextField (the human-readable "why", built by the
  detector); `detected_at` DateTimeField auto; `resolution_note` TextField blank;
  `resolved_by` FK user SET_NULL editable=False; `resolved_at` DateTimeField null editable=False
- `classmethod scan(tenant, start, end, reasons=None, user=None)` → runs the enabled checks, upserts on
  `dedupe_key`, returns `{reason: count}`. **Re-runnable and idempotent.** Detection constants live on the class:
  `PRICE_TOLERANCE_PCT = Decimal("5.00")` (umbrex), `SPLIT_WINDOW_DAYS = 30`, `SPLIT_MIN_ORDERS = 3`,
  `COVERING_CONTRACT_STATUSES = ("active","expiring")` (matching `scm/analytics.py:204`),
  `NON_ADDRESSABLE_GL_CODES = (...)`
- `STATUS_CSS` / `SEVERITY_CSS` badge maps — **only** `badge-green|red|amber|info|muted|slate` exist in
  `theme.css` (L33); a `badge-danger` renders unstyled
- Meta indexes: `(tenant, status)`, `(tenant, reason)`, `(tenant, document_date)`, `(tenant, vendor)`
- FKs verified: every one of them, in the table at the top of this file

### 3. `SpendReport` [**`SPR-`**] + `SpendReportSnapshot` — `models/SpendAnalytics/SpendReports.py`
**`TenantNumbered` + a plain child** (one entity file owns the primary model plus its children — rule 2).
Shaped **field-for-field on `crm.AnalyticsReport` + `crm.ReportSnapshot`.** Prefix `SPR` verified free.
Justified by: saved/ad-hoc self-service reports (Zycus, SAP Ariba, Coupa, JAGGAER, Ivalua, Basware), pre-built
report libraries (JAGGAER, Ivalua, SAP Ariba), snapshots for period-over-period comparison (Sievo, SpendHQ).

`SpendReport`
- `name` CharField(120) · `description` TextField blank
- `basis` CharField `[("invoiced","Invoiced (recognised) spend"),("committed","Committed (PO) spend")]` default `invoiced`
- `measure` CharField `[("net_spend","Net spend"),("transaction_count","Transactions"),("avg_transaction","Average transaction value"),("supplier_count","Distinct suppliers"),("maverick_spend","Maverick spend"),("maverick_pct","Maverick spend %"),("classified_pct","Classified spend %"),("leakage","Contract leakage value")]` default `net_spend`
- `dimension_1` / `dimension_2` CharField `[("supplier","Supplier"),("category","Category"),("department","Department / cost centre"),("gl_account","GL account"),("currency","Currency"),("month","Month"),("quarter","Quarter"),("invoice_type","Invoice type"),("none","— none —")]` (`dimension_1` default `supplier`, `dimension_2` default `none`; `clean()` refuses `dimension_1 == dimension_2` unless both are `none`)
- `date_range` CharField `[("last_30","Last 30 days"),("last_90","Last 90 days"),("quarter","This quarter"),("year","This year"),("all","All time"),("custom","Custom range")]` default `last_90`, + `date_from` / `date_to` DateFields (required only when `custom`, checked in `clean()`)
- Filters: `vendor` FK `core.Party` null · `category` FK `scm.ItemCategory` null · `org_unit` FK `core.OrgUnit` null · `gl_account` FK `accounting.GLAccount` null · `min_amount` Decimal(18,2) null
- `chart_type` CharField `[("bar","Bar"),("line","Line"),("pie","Pie"),("table","Table only")]` default `bar` · `top_n` PositiveSmallIntegerField default 20 (validators 1-100)
- `is_favorite` Boolean · `is_shared` Boolean default True · `owner` FK user SET_NULL · `last_run_at` DateTimeField null **editable=False** (system-stamped on render/snapshot — verbatim from `AnalyticsReport`)
- Meta: `ordering = ["-is_favorite","name"]`, `unique_together ("tenant","number")`, indexes `(tenant, measure)`, `(tenant, is_favorite)`

`SpendReportSnapshot` (plain child, tenant FK for scoping — the `crm.ReportSnapshot` shape verbatim)
- `tenant` FK `core.Tenant` · `report` FK CASCADE `related_name="snapshots"` · `title` CharField(160) ·
  `generated_by` FK user SET_NULL · `generated_at` auto_now_add ·
  `summary` JSONField(default=list) — `[{label, value}]` KPI cards ·
  `data` JSONField(default=dict) — `{columns, rows, chart_type, chart_labels, chart_data}`, rendered as-is with
  **no recompute** · `row_count` PositiveIntegerField default 0
- Created **only** by a POST `report_snapshot` action, never by a user form

### Computed pages (NO new table) — with the exact aggregate each one runs

Base queryset for every invoiced figure (define **once** in `apps/procurement/analytics.py`):
```
RECOGNISED_INVOICE_STATUSES = ("approved", "scheduled", "paid")
SupplierInvoiceLine.objects.filter(
    invoice__tenant=tenant,
    invoice__status__in=RECOGNISED_INVOICE_STATUSES,
    invoice__invoice_date__gte=start, invoice__invoice_date__lt=end)
```

| Page (url name) | Bullet | The aggregates it runs |
|---|---|---|
| `spend_dashboard` | 1 | `.aggregate(Sum("line_total"))` for net spend; `.values("invoice__vendor_id","invoice__vendor__name").annotate(total=Sum("line_total"), invoices=Count("invoice_id", distinct=True)).order_by("-total")[:25]`; `.values("gl_account__code","gl_account__name").annotate(total=Sum("line_total"))`; `.values("item__category__name").annotate(total=Sum("line_total"))`; `.annotate(unit=Coalesce("invoice__purchase_order__requisition__org_unit__name","invoice__purchase_order__ship_to__name")).values("unit").annotate(total=Sum("line_total"))`; `.annotate(m=TruncMonth("invoice__invoice_date")).values("m").annotate(total=Sum("line_total")).order_by("m")`; `.values("invoice__currency__code").annotate(total=Sum("line_total"))` → `mixed_currency` flag |
| `category_spend` | 3 | Per `?category=<pk>`: supplier league + running cumulative % (**Pareto**) and **HHI** = `Σ (share²) × 10 000`; `TruncMonth` trend; per-item price spread `.values("item_id","item__name").annotate(qty=Sum("quantity"), spend=Sum("line_total"), lo=Min("unit_price"), hi=Max("unit_price"))` → consolidation opportunity `Σ qty × (avg − lo)`; sole-source count `.values("item_id").annotate(v=Count("invoice__vendor_id", distinct=True)).filter(v=1).count()`; tail share (bottom decile of suppliers by count) |
| `classification_workbench` | 3 | Unclassified lines (`item__category__isnull=True` **and** no `SpendClassificationRule` match) ranked by `Sum("line_total")` grouped by `invoice__vendor` / `gl_account` / `sku_hint`, each row linking to a pre-filled rule form; headline **`classified_pct` = classified spend ÷ total spend** |
| `maverick_dashboard` | 4 | `MaverickSpendFinding.objects.filter(tenant=…, document_date__range=…)`: `.values("reason").annotate(n=Count("id"), value=Sum("amount"))`; **rate = Σ amount (status ∈ open/acknowledged, `is_addressable=True`) ÷ addressable spend**; transaction-rate twin; `.values("org_unit__name" / "vendor__name" / "category__name").annotate(value=Sum("amount"))`; `TruncMonth("document_date")` trend; `Sum("leakage_amount")`; the umbrex benchmark bands printed on the page; a `Scan now` POST calling `MaverickSpendFinding.scan(...)` |
| `spend_export` | 5 | A page (not a bare download — a sidebar bullet must land on a page) offering CSV of the current cube slice or of any saved report / snapshot, filters carried through verbatim, every cell through `_csv_safe`, a `showing N of M` cap notice, and an honest note that a live BI/PowerBI feed is not implemented |

Plus standard CRUD for the three entities: `spendclassificationrule_*`, `maverickfinding_*` (list/detail + the
disposition verb POSTs; create/edit only where a human authors one), `spendreport_*` (+ `spendreport_run`,
`spendreport_snapshot`, `spendreport_export`).

### Proposed `LIVE_LINKS["6.14"]` (one key per NavERP.md bullet, all staff-reachable)
```
"Spend Dashboards":         "procurement:spend_dashboard"        # computed cube
"Custom Report Builder":    "procurement:spendreport_list"       # saved definitions (guided, NOT drag-and-drop)
"Category Spend Analysis":  "procurement:category_spend"         # computed drill-down + Pareto/HHI
"Maverick Spend Tracking":  "procurement:maverick_dashboard"     # findings worklist + rate vs addressable spend
"Data Export & Visualization": "procurement:spend_export"        # CSV page; BI feed stated as not implemented
```
`SpendClassificationRule` CRUD is a **master with no sidebar key**, reached from `category_spend` and
`classification_workbench` (the `ReceiptTolerancePolicy` / `KpiTarget` precedent).

### Seeder rows to add to `seed_procurement` (idempotent, all dates relative to NOW — L16)
~6 `SpendReport` rows forming the pre-built library (spend by supplier, by category, by department, monthly trend,
maverick by reason, unclassified spend) with 1-2 `SpendReportSnapshot` rows on one of them; ~8
`SpendClassificationRule` rows covering vendor / GL / keyword match types against existing `scm.ItemCategory` rows;
and `MaverickSpendFinding` rows generated by **calling `scan()`** against the 6.13/6.10 seeded invoices and orders
rather than hand-writing findings — that way the seeded data proves the detector works.

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **Budget vs actual, commitment accounting, variance analysis, spend forecasting** → **6.15 Budget & Cost
  Management** (its own bullets say exactly this). 6.14 must not restate `accounting.Budget`; link out (L29).
- **Supplier scorecards, OTD/defect KPIs, 360 feedback, PIPs, benchmarking supplier performance** →
  **6.16 Supplier Performance & Evaluation**. `scm.SupplierScorecard` already exists and 4.11 already trends it.
- **Fraud-pattern detection, restricted-party screening, conflict-of-interest, tamper-proof audit logging** →
  **6.17 Risk & Compliance Management**. Only `split_purchase` (approval-threshold avoidance) stays in 6.14, and
  the code comment must name the boundary.
- **Savings-initiative lifecycle (identified → approved → sourcing → realised → validated)** → **6.5 Sourcing
  Analytics** or a later 6.14 pass. Already routed to "6.5 / 6.14" by `research-scm-4.11.md:521-525`; it is a
  full workflow entity and does not fit this budget.
- **Early-payment-discount opportunity *worklist*** → already built in **6.13** (the `#discount` dashboard
  anchor). 6.14 shows only the aggregate/trend and deep-links across.
- **Contract renewal/expiry workflow and alerts** → **6.8** / **4.2**. 6.14 surfaces spend at risk on an expiring
  contract; it does not own the renewal.
- **Supplier master deduplication / normalisation** → **6.4 Vendor Management** / `core.Party`. An analytics pass
  must never edit the party master.
- **Catalogue price maintenance and preferred-supplier designation** → **6.9** (`CatalogItem.is_preferred`,
  `CatalogPriceTier` already exist). 6.14 *reads* them as the benchmark.
- **PO-based spend cube, negotiated-savings, cycle/lead time, tail share on the committed basis** → already
  **SCM 4.11** (`scm:spend_analytics`). 6.14's cube is the **invoiced** twin plus classification and findings;
  the dashboard must link to 4.11 rather than restate its savings and cycle-time figures.
- **Generic dashboard builder, formula-authored KPI library, OLAP cubes, NLQ, ML/AutoML, scheduled distribution
  and bursting** → **Module 10 (`bi`)**: 10.8 / 10.10 / 10.11 / 10.12 / 10.13 / 10.15 / 10.16. This is the most
  important boundary in the file — 6.14 is a *procurement* analytics page, not a BI platform.
- **Statutory P&L, journal-backed cost reporting** → **`apps.accounting`** (L29). 6.14 posts nothing.

---

## Deferred (later passes / integrations)

- **ML/NLP auto-classification and supplier normalisation** (all ten vendors) — needs a classifier and a training
  corpus. The `SpendClassificationRule` engine is the honest shipped equivalent; the page must say the rules are
  explicit, not learned. Never label it "AI".
- **Scheduled / subscribed report delivery by email** — `accounting.ScheduledReport` already models the config and
  already defers the worker; adding a second scheduler table here duplicates it. `SpendReport` + snapshot is the
  substrate a future worker points at.
- **Live BI / PowerBI connector, REST or SFTP feeds** (JAGGAER, Sievo, Basware) — a signed tenant-scoped read-only
  endpoint is its own security design. CSV/XLSX download ships; say so plainly on the page.
- **Community / peer benchmarking and external category price indices** (Coupa, SpendHQ, SAP Ariba, Sievo, GEP) —
  needs an external corpus. Nothing ships.
- **P-card / T&E / expense spend sources** (Ivalua, Sievo, umbrex's MCC rule) — no card-transaction model exists
  in this tree; the maverick reason list omits card misuse for exactly that reason.
- **Multi-currency normalisation** — there is still **no FX-rate table** in this repo (re-verified this pass).
  Every total is a face-value sum per currency with a `mixed_currency` flag, exactly as `scm/analytics.py:1396`
  does. Inventing a rate would be worse than the caveat.
- **UNSPSC codes on the taxonomy** — `scm.ItemCategory` has `name`/`parent`/`description` but no code column.
  Adding a nullable `unspsc_code` is the additive one-column precedent (`Item.is_spare_part`,
  `Item.storage_condition`), **but it is a cross-app SCM migration from a Procurement build** — out of scope for
  this pass. Category *names* carry the taxonomy for now; note the future migration.
- **`split_purchase` detection** — ship it only if the pass has room after the other seven reasons; it is the
  most expensive check (a self-join over a rolling window) and the closest to 6.17's territory.
- **PDF board pack / CFO-ready print export** — the print-template precedent exists; not this pass.
- **Should-cost modelling, BOM roll-ups, what-if scenario modelling** (JAGGAER, IBM Emptoris, GEP) — solver/
  modelling work, well outside a Django aggregate pass.
