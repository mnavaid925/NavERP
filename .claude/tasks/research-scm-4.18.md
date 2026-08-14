# Research — Sub-module 4.18: Finance & Accounting Integration (Module 4 — Supply Chain Management, `scm`)

Target resolved from `NavERP.md` lines 852–857. `apps/core/navigation.py` carries `LIVE_LINKS` keys `"4.1"`
(line 770) … `"4.17"` (line 1113) and **no `"4.18"`**, so 4.18 is the next unbuilt sub-module in Module 4.

**4.18 is an INTEGRATION sub-module, and that is the whole shape of this catalog.** Four of its five bullets
already have a home: `apps/accounting` (Module 2, fully built) owns the ledger, and SCM 4.1 / 4.5 / 4.6 / 4.10 /
4.16 / 4.17 already hand documents to it. The one bullet with **no home anywhere in the codebase** is
**Landed Cost Calculation** — `grep -rn "landed" apps/` returns zero model, field or view. Landed cost is
therefore the centrepiece of this pass; the other four bullets are survey + report surfaces over entities that
already exist.

---

## Repo state checked first

### LIVE_LINKS built so far in module 4
`4.1 … 4.17` (verified `apps/core/navigation.py:770–1113`). No `"4.18"` / `"4.19"` key exists.

### Accounting spine — VERIFIED to exist (do NOT re-declare any of these)
Read from `apps/accounting/models/__init__.py` (the authoritative re-export block) and the entity files:

| Entity | File · line | Fields 4.18 will actually touch |
|---|---|---|
| `accounting.Currency` | `GeneralLedger/Currencies.py:5` | **GLOBAL — no tenant FK.** Forms must scope by `is_active`, not by tenant (the 4.17 trap, `research-scm-4.17.md:24`). |
| `accounting.ExchangeRate` | `GeneralLedger/ExchangeRates.py:5` | Exists — FX for multi-currency landed cost is available, not a stand-in. |
| `accounting.GLAccount` | `GeneralLedger/GLAccounts.py:17` | Chart of accounts; balance is DERIVED. The accrual/expense/variance accounts a landed-cost charge points at. |
| `accounting.FiscalPeriod` | `GeneralLedger/FiscalPeriods.py:20` | Period the cost lands in; `Budget.fiscal_period` FKs it. |
| `accounting.JournalEntry` / `JournalLine` | `GeneralLedger/JournalEntries.py:23` | **Append-only, immutable once posted.** SCM posts NOTHING here (L29) — see "Hand-off, not posting" below. |
| `accounting.Bill` / `BillLine` | `AccountsPayable/Bills.py:6, 78` | `party→core.Party PROTECT`, `bill_date`, `due_date`, `status` (draft…void), `currency`, `journal_entry`, `subtotal`/`tax_total`/`total` **all `editable=False`**, `document→core.Document`. `BillLine(description, quantity, unit_price, **tax_rate_pct**, line_total editable=False, gl_account)`. **`BillLine` has NO `tax_code` FK** — a bill line carries a decimal rate, not a `TaxCode`. |
| `accounting.Payment` / `PaymentAllocation` | `AccountsPayable/Payments.py:39`, `AccountsReceivable/PaymentAllocations.py:54` | `Bill.amount_paid()` / `balance_due()` / `recompute_payment_status()` already exist — AP aging is accounting's. |
| `accounting.Invoice` / `InvoiceLine` | `AccountsReceivable/Invoices.py:47` | `kind` (`invoice`\|`credit_note`), `party`, `status`, `journal_entry`, derived totals. AR side. |
| `accounting.PaymentTerm` | `AccountsPayable/PaymentTerms.py:29` | Already FK'd from `scm.PurchaseOrder:45`, `scm.SalesOrder:70`, `scm.SupplierContract:77`, `scm.LogisticsClient:149`. |
| `accounting.TaxCode` | `Tax/TaxCodes.py:6` | `name`, `jurisdiction`, `tax_type` ∈ **`sales`/`vat`/`gst`/`use`** (line 9 — **no customs/duty/excise member**), `rate_pct` (6,3), `payable_account→GLAccount`, `is_active`. |
| `accounting.TaxReturn` | `Tax/TaxReturns.py:104` | Filing/period entity — accounting's, not ours. |
| `accounting.Budget` / `BudgetLine` | `Budgeting/Budgets.py:6`, `BudgetLines.py:5` | `Budget(name, fiscal_period, version original/revised/forecast, status draft/approved/archived)` + `.total()`. `BudgetLine(budget, **gl_account PROTECT**, **org_unit→core.OrgUnit**, amount)`. **The supply-chain-department dimension already exists — it is `BudgetLine.org_unit`.** |
| `accounting.CostAllocation` | `CostManagement/CostAllocations.py:6` | GL-account → GL-account/cost-centre distribution that posts Dr target / Cr source. **This is NOT landed cost** — it has no item, no receipt, no per-unit uplift. No duplication risk, but worth naming so nobody proposes reusing it. |
| `accounting.BankAccount` / `BankTransaction` / `ReconciliationMatch` / `FixedAsset` / `PayrollRun` / `Project` / `JobCostEntry` / `IntercompanyTransaction` / `InternalControl` / `IntegrationConfig` / `RecurringInvoice` / `VendorProfile` / `CustomerProfile` / `ScheduledReport` | `apps/accounting/models/**` | All exist. None are 4.18's to touch. |

### SCM entities that ALREADY hand off to finance (4.18 extends these — it must not re-invent them)

| What | Where | Already does |
|---|---|---|
| **Three-way match (PO ↔ GRN ↔ Bill)** | `models/ProcurementManagement/GoodsReceiptNotes.py:15` | `bill→accounting.Bill` (`:50`), `match_status` ∈ `not_matched/matched/price_variance/quantity_variance/over_received` (`:27`), `PRICE_TOLERANCE_PCT = 2%` (`:35`), `received_value()` (`:73`, ex-tax at PO price), `billed_value()` (`:87`, `bill.subtotal`), `recompute_match()` (`:98`). |
| **Freight audit → draft AP Bill** | `models/TransportationManagement/FreightInvoices.py:16` | `bill→accounting.Bill` nullable `editable=False` (`:63`), `CHARGE_TYPE_CHOICES` = linehaul/fuel_surcharge/accessorial/detention/demurrage/tolls/other (`:140`), billed-vs-contract variance + tolerance + duplicate detection (`run_audit`, `:91`). View action `views/TransportationManagement/FreightInvoices.py:183` — "**the AP hand-off (L29)**". |
| **3PL client billing → draft AR Invoice** | `models/ThirdPartyLogistics/ClientBillingRuns.py:174, 691` | `invoice→accounting.Invoice`, `draft_invoice()` — "**the AR hand-off (L29)**". |
| **Returns → draft credit note** | `models/ReturnsManagement/ReturnAuthorizations.py:194` | `credit_note→accounting.Invoice(kind="credit_note", status="draft")`. Docstring `:15`: "**SCM posts NO JournalEntry**". |
| **Sales order → invoice** | `models/OrderManagement/SalesOrders.py:86` | `invoice→accounting.Invoice`. |
| **Budget check at requisition time** | `models/ProcurementManagement/PurchaseRequisitions.py:50, 94` | `budget→accounting.Budget`, `org_unit→core.OrgUnit` (`:47`, help_text literally "the budget dimension"), `budget_check()` returns `{budgeted, committed, requested, remaining, over_budget}` from `accounting.BudgetLine`. Line-level `gl_account` (`:164`). **Deliberately a view-time check, not a stored encumbrance** (docstring `:97`). |
| **Customer-facing invoice access** | `models/CustomerPortal/PortalDocumentShares.py:174`, `PortalOrderInquiries.py:178` | Both FK `accounting.Invoice`. |
| **Maintenance external cost** | `models/AssetManagement/MaintenanceWorkOrders.py:60` | `external_cost` is a plain column, explicitly *not* a posted charge. |

### The inventory valuation engine 4.18 must plug into (NOT replace)

- `scm.StockMove` — `models/InventoryManagement/StockMoves.py:13`. **Append-only, signed quantity, never edited or
  deleted** (docstring `:5`: "no form, no admin write, no delete view"). `unit_cost` (14,4) at `:44` **IS the
  FIFO/LIFO/WAC cost layer** (docstring `:7`: "no separate cost-layer table is needed"). `MOVE_TYPES` at `:16`
  includes `adjustment` whose comment already names "revaluation".
- `scm.Item` — `models/InventoryManagement/Items.py:63`. `costing_method` ∈ `weighted_avg`/`fifo`/`lifo` (`:90`),
  `standard_cost` (`:91`), `average_cost` **`editable=False`, cached** (`:95`), `apply_receipt(quantity, unit_cost)`
  (`:179`) rolls the WAC forward against the *pre-receipt* on-hand.
- The posting service — `views/_helpers.py:133` `_post_stock_move(...)`, which calls `item.apply_receipt` at `:148`
  **before** writing the move. Every stock movement in the module goes through it.
- The authoritative valuation — `views/InventoryManagement/Reports.py:15` `_item_valuation(item, moves)` and `:49`
  `valuation_report`: WAC = on-hand × cached `average_cost`; FIFO/LIFO = walk the inbound layers, consume by total
  outbound, value what remains. **Transfers are excluded from the layer walk on purpose.**

### Spine facts verified NOT to exist (grep evidence)

- **No landed cost anywhere.** `grep -rni "landed|landed_cost|LandedCost" apps/` returns only prose ("a fix has to be
  found and **landed** three times") and the sibling research files parking it here. No model, no field, no view.
- **No customs-duty rate table.** `accounting.TaxCode.TAX_TYPE_CHOICES` (`Tax/TaxCodes.py:9`) is
  `sales`/`vat`/`gst`/`use` — **customs duty is not expressible**, and `TaxCode` has no HS code and no
  country-of-origin pair, which is the key a duty rate is looked up by.
- **No `weight`, `volume` or `hs_code` column on `scm.Item`** (whole model read, `Items.py:63–142`). This matters:
  allocate-by-weight and allocate-by-volume — table stakes in every product surveyed — have **no basis column to
  read** today.
- **`hs_code` / `country_of_origin` exist only as frozen snapshots on `scm.TradeDocumentLine`**
  (`ContractCompliance/TradeDocuments.py:367, 369`), and 4.12's docstring (`:30`) states the deliberate reason it
  added **no** `hs_code` to `Item`: "a mutable master plus a filed document would be two sources of truth… the
  'helpful' default that syncs them is the bug." **4.18 must respect that decision** — a duty rate belongs in a
  rate master keyed by HS code, not on the item master.
- `scm.TradeDocument.declared_value` (`:190`) and `.incoterm` (`:201`, Incoterms-2020 validated) exist and are the
  natural customs-value / cost-responsibility inputs.
- No SCM-side AP/AR register, aging view, or accrual model.

### Free auto-number prefixes
Taken in `apps/scm` (`grep -rn "NUMBER_PREFIX = " apps/scm/models/`): `PR RFQ QT PO GRN SCR SRA SC CAT TRF ADJ PUT
PIK CC YRD SO SHP LD CAR FRT SEA DF DS FA WC BOM WO PRD QC QA NCR CAPA RMA WTY ALR KPI LIC CR TD ESG AST PM MWO LAB
LST LSN LPL CCM EXC PAC PIQ PDS 3PL TAR CBR SLA`. **Free and proposed: `LC`, `DTY`.**

### Sibling research files — this sub-module's starting backlog
Four earlier files parked work here explicitly:
- `research-scm.md:229–231, 359–360` — "AP/AR, landed cost calculation (freight+customs+insurance rolled into item
  cost), budgeting, tax/VAT/customs… **the only new piece is landed-cost allocation, which needs 4.3's valuation
  first**." 4.3 is built; the prerequisite is met.
- `research-scm-4.3.md:262–265, 397–399, 422–425` — "Landed cost (freight/duty/insurance rolled into unit cost)…
  would need cost-component fields on the receiving transaction (GRN, 4.1) feeding into `StockMove.unit_cost`" and
  "GL posting of inventory value changes → 4.18, reuses `accounting.JournalEntry`."
- `research-scm-4.2.md:308` — "Landed-cost allocation, tax/VAT/customs on supplier goods → 4.18."
- `research-scm-4.12.md:360–362, 617–619` — "Duty/tariff & landed-cost calculation… **PARK → 4.18**.
  `TradeDocument.declared_value` is the input."
- `research-scm-4.4.md:404–406` — "`PutawayTask.unit_cost` this pass is just the PO/GRN unit price, no landed-cost
  allocation."

---

## Leaders surveyed (with source links)

Domain surveyed: **supply-chain-to-finance integration — landed cost, procure-to-pay finance, duty/customs
costing, receipt accounting**. Not "best SCM software".

1. **Oracle NetSuite — Landed Cost** — the SMB/mid-market reference implementation; landed-cost categories entered
   on an item receipt or vendor bill and allocated to inventory value —
   `docs.oracle.com/.../section_N2418831.html`
2. **Microsoft Dynamics 365 Supply Chain Management — Landed Cost module** — the deepest import-costing model:
   voyage → shipping container → folio, auto-cost rules, multi-basis apportionment —
   `learn.microsoft.com/.../supply-chain/landed-cost/auto-cost-setup`
3. **Oracle Fusion Cloud SCM — Landed Cost Management + Receipt Accounting** — "trade operations", charge names,
   estimated→actual with variance, allocation down to PO schedules and receipts —
   `docs.oracle.com/.../landed-cost-management.html`
4. **SAP S/4HANA — MM planned vs. unplanned delivery costs** — condition types on the PO, separate freight/customs
   clearing GL accounts, a *different vendor per cost type*, GR/IR clearing — `community.sap.com` (linked below)
5. **Acumatica Cloud ERP — landed cost on purchase receipts** — landed-cost bills entered directly in AP and
   associated to received items; custom allocation methods; variance account —
   `acumatica.com/cloud-erp-software/distribution-management/purchase-order-management/`
6. **Odoo — Landed Costs** — the closest architectural analogue to NavERP's append-only ledger: an *additional*
   valuation layer linked to the original receipt, five split methods, AVCO/FIFO only —
   `odoo.com/documentation/18.0/.../landed_costs.html`
7. **VISCO Software** — importer-specialist ERP; the richest single description of the estimated→accrue→reconcile
   workflow and per-charge allocation bases — `viscosoftware.com/landed-cost-software-for-importers/`
8. **Magaya Supply Chain / Magaya Customs Compliance** — freight-forwarder landed cost + ACE-certified customs
   filing — `magaya.com/landed-cost/`
9. **Avalara AvaTax Cross-Border** — real-time duty/import-tax calculation, AI HS/HTS/TARIC classification, DDP —
   `avalara.com/us/en/products/global-commerce-offerings/avatax-cross-border.html`
10. **Descartes CustomsInfo** — global trade content: HTS codes, duty rates and rulings for 190+ countries feeding
    landed-cost calculation — `customsinfo.com`
11. **Coupa — AP Automation / Invoice Management** — procure-to-pay AP side: multi-level invoice validation,
    accruals at close, budget control — `coupa.com/products/ap-automation/invoicing/`
12. **Infor CloudSuite (Industrial / LN)** — landed-cost inventory-adjustment account, vouchered-vs-estimated
    variance entries, periodic inventory revaluation — `erpresearch.com/en-us/infor-cloudsuite-inventory-management`

---

## Feature catalog (this sub-module only)

### Bullet 3 — Landed Cost Calculation → **NEW MODELS. The centrepiece.**

- **Landed-cost charge categories (a closed cost-component taxonomy)** — freight, duty/tariff, customs &
  brokerage, insurance, handling, drayage/inland, port/terminal fees, fuel surcharge, inspection/fumigation,
  storage/demurrage, compliance labelling, other · seen in: NetSuite ("landed cost categories"), Oracle Fusion
  ("charge names — Freight, Insurance, Handling, Miscellaneous"), VISCO (the fullest list), Magaya, D365 ("cost
  types") · priority: **table-stakes** · spine: **new table** `LandedCostCharge.charge_type` choices; mirror the
  shape of the verified `FreightInvoiceLine.CHARGE_TYPE_CHOICES` (`FreightInvoices.py:140`) so the two vocabularies
  are recognisably siblings · **buildable now**
- **Multi-basis apportionment: by value, by quantity, by weight, by volume, equal, manual** · seen in: NetSuite
  (weight/quantity/value, **one method per transaction**), Odoo (equal/by quantity/by current cost/by weight/by
  volume), D365 (quantity, amount, value, weight, volume, measurement, user-defined volumetric), VISCO, Acumatica
  ("custom allocation methods") · priority: **table-stakes** · spine: **new table** — `allocation_basis` on both
  the voucher (default) and the charge line (override) · **buildable now**, with one caveat: **`scm.Item` has no
  `weight` or `volume` column** (verified above), so weight/volume bases need two additive nullable columns on the
  existing `Item` master — exactly the `is_spare_part` / `storage_condition` / `owner_client` precedent
  (`Items.py:107, 120, 138`), never a parallel table
- **Per-charge basis override in one document** ("freight by weight; insurance by value; broker minimum by
  quantity") · seen in: VISCO (explicit), D365 (auto costs are per cost type), Oracle Fusion · priority: **common**
  — and it is what NetSuite explicitly *cannot* do ("only one allocation method per transaction"), so it is a real
  differentiator to carry · spine: **new table** — `LandedCostCharge.allocation_basis` nullable, falls back to the
  voucher's · **buildable now**
- **Estimated → actual with a stored variance** · seen in: Oracle Fusion ("initially estimates… later updates with
  actuals… the difference shown as a variance"), VISCO (estimate at PO from freight benchmarks + duty rate by HTS,
  reconcile on invoice arrival), Infor (vouchered-vs-estimated variance entries), D365 (estimated landed cost of a
  voyage) · priority: **table-stakes** · spine: **new table** — `estimated_amount` + `actual_amount` per charge,
  derived `variance_amount` on the voucher · **buildable now**
- **Accrual at receipt, reconcile when the freight/broker invoice lands later** · seen in: VISCO (named "cost
  accrual workflow"), Coupa (accruals at month-end close), SAP (GR/IR clearing is precisely this) · priority:
  **table-stakes** · spine: **new table** — an `accrual_account→accounting.GLAccount` on the charge plus the
  voucher's `status` lifecycle; the reconciliation target is a **draft `accounting.Bill`** (never a JE from SCM) ·
  **buildable now**
- **Allocation down to the receipt line / individual unit, retrievable per shipment** · seen in: Oracle Fusion
  ("distributed and allocated to the respective PO schedules and further on to the receipts"), VISCO ("pull up any
  shipment and see every cost component, every allocation, every variance"), NetSuite (landed cost allocation per
  line) · priority: **table-stakes** · spine: **new table** `LandedCostAllocation`, FK'd to the verified
  `scm.GoodsReceiptLine` (`GoodsReceiptNotes.py:166`) and to the exact `scm.StockMove` it uplifts · **buildable now**
- **The uplift becomes inventory value (revaluation of the receipt's cost layer)** · seen in: every product
  surveyed; Odoo is the architectural model — it writes an *additional valuation layer linked to the original*
  rather than editing the original · priority: **table-stakes** · spine: **extends 4.3's existing engine, does not
  replace it.** `LandedCostAllocation` **is** the additive layer: `_item_valuation` (`Reports.py:15`) reads
  `StockMove.unit_cost + Σ uplift for that move`, and the cached WAC rolls forward via a new
  `Item.apply_landed_cost(total_amount)` that mirrors `apply_receipt` (`Items.py:179`) — **`StockMove` rows are
  never edited** (`StockMoves.py:5`) · **buildable now**
- **Costing-method eligibility guard** — landed cost only makes sense on AVCO/FIFO-style perpetual valuation ·
  seen in: Odoo (hard constraint: AVCO or FIFO only) · priority: **differentiator** · spine: a `clean()` guard
  against the verified `Item.costing_method` (`Items.py:90`); `standard_cost` items take a variance instead ·
  **buildable now**
- **A separate cost vendor per charge (freight forwarder ≠ goods supplier ≠ customs broker)** · seen in: SAP
  (three vendors on one PO via condition types), Acumatica (landed-cost bills entered directly in AP), VISCO ·
  priority: **table-stakes** · spine: **reuses `core.Party`** on the charge line — vendors are `PartyRole`s, never
  a new company table · **buildable now**
- **Cost rules that auto-populate charges (auto costs)** · seen in: D365 (`Landed cost > Costing setup > Auto
  costs`, rules per voyage/container/folio/PO/item), VISCO (freight benchmarks + historical fee data) · priority:
  **differentiator** · spine: would be a 5th table (`LandedCostRule`) · **DEFERRED** — over-scope for this pass
- **Voyage / container / folio grouping above the receipt** · seen in: D365 (voyage → shipping container → folio),
  Oracle Fusion (a trade operation over "a group of shipments") · priority: **common** · spine: NavERP's nearest
  verified grouping is `scm.Shipment` (`Shipments.py:18`, has `direction`, `weight_kg`, `volume_cbm`,
  `package_count`) and `scm.Load` — so the voucher carries an optional `shipment` FK rather than a new voyage
  table · **buildable now (as an FK, not a new entity)**
- **Multi-currency charges converted at the actual rate** · seen in: VISCO ("currency conversion at actual exchange
  rates"), Oracle, D365 · priority: **common** · spine: **reuses `accounting.Currency` + `accounting.ExchangeRate`**
  (both verified) — note `Currency` is GLOBAL, scope dropdowns by `is_active` · **buildable now**

### Bullet 5 — Tax Management → **EXTENDS `accounting.TaxCode` + one small NEW duty-rate master**

- **Customs duty computed from an HS/HTS code × country of origin × duty rate** · seen in: Avalara AvaTax
  Cross-Border (HS 6-digit / HTS & TARIC 10-digit / Schedule B, AI classification), Descartes CustomsInfo (duty
  rates + rulings for 190+ countries), VISCO ("maintain HTS codes by product, apply the correct duty rate
  automatically, flag when rates change, apply the correct rate by transaction date"), Magaya · priority:
  **table-stakes in this domain** · spine: **`accounting.TaxCode` cannot express it** — verified `tax_type` is
  `sales/vat/gst/use` only (`Tax/TaxCodes.py:9`) with no HS code and no origin-country pair. A small tenant-scoped
  **`DutyTariff`** master `(hs_code, country_of_origin, duty_rate_pct, effective_from/to)` is the genuinely-new
  domain table; the duty *charge line* still points at `accounting.TaxCode` for the recoverable VAT/GST portion ·
  **buildable now** (the *content feed* — live global tariff data — is integration/later)
- **Sales tax / VAT / GST on the landed-cost charge itself** · seen in: NetSuite ("Landed Cost and Taxation",
  Legacy Tax/SuiteTax), Avalara, Coupa (global tax & e-invoicing compliance) · priority: **table-stakes** · spine:
  **reuses `accounting.TaxCode`** by FK from `LandedCostCharge.tax_code` — never re-declare a rate table.
  ⚠ note for the todo agent: the drafted `accounting.BillLine` carries `tax_rate_pct` (a decimal), **not** a
  `TaxCode` FK (`Bills.py:83`) — the hand-off must copy `tax_code.rate_pct` into it, the same shape as
  `LogisticsClient`'s decimal tax field (`LogisticsClients.py:136`) · **buildable now**
- **Recoverable vs. non-recoverable tax** (recoverable VAT must NOT capitalise into inventory; duty must) · seen
  in: SAP (planned delivery costs valuate the material; VAT clears separately), Oracle, NetSuite · priority:
  **common** · spine: a boolean `is_recoverable` / `capitalise_to_inventory` on the charge line — this single flag
  is what stops the module overstating stock value · **buildable now**
- **Incoterms driving who bears which cost** · seen in: Magaya, VISCO, Descartes · priority: **common** · spine:
  **reuses the verified `scm.TradeDocument.incoterm`** (`TradeDocuments.py:201`, Incoterms-2020 validated) via the
  voucher's optional trade-document link — do not add a second incoterm field · **buildable now**
- **Duty drawback, FTZ, FTA rules-of-origin qualification** · seen in: e2open, ONESOURCE FTA, SAP GTS, Thomson
  Reuters (already catalogued at `research-scm-4.12.md:360`) · priority: **differentiator** · **DEFERRED** — a
  rules engine, not a data model
- **AI/automated HS classification** · seen in: Avalara (self-serve + managed), Descartes · priority:
  **differentiator** · **integration/later**

### Bullet 1 — Accounts Payable → **ALREADY COVERED; 4.18 adds a register view + the landed-cost Bill hand-off**

- **Three-way match PO ↔ receipt ↔ invoice with tolerance and an exception queue** · seen in: Coupa (multi-level
  automated invoice validation), SAP, Oracle, NetSuite · priority: table-stakes · spine: **ALREADY COVERED BY
  `apps/scm/models/ProcurementManagement/GoodsReceiptNotes.py`** (`match_status`, `PRICE_TOLERANCE_PCT`,
  `recompute_match()`) · nothing to build
- **Freight invoice audit → AP** · seen in: Coupa, Descartes, Oracle · priority: table-stakes · spine: **ALREADY
  COVERED BY `apps/scm/models/TransportationManagement/FreightInvoices.py`** + its `handoff` view
  (`views/TransportationManagement/FreightInvoices.py:183`) · nothing to build
- **A landed-cost/accessorial invoice booked straight into AP against received goods** · seen in: Acumatica
  ("enter landed cost bills directly in Accounts Payable and associate them with received items"), NetSuite
  (landed cost sourced from an existing vendor bill, incl. an "exclude tax" variant), SAP (unplanned delivery costs
  entered at invoice verification) · priority: **table-stakes** · spine: **NEW — the one genuinely new AP capability
  in 4.18**: `LandedCostVoucher.bill → accounting.Bill` nullable `editable=False`, set by a `draft_bill()` action
  that copies the exact `FreightInvoice.handoff` pattern · **buildable now**
- **One consolidated "SCM payables" register** — every SCM document that has drafted or matched an
  `accounting.Bill`, with its match/approval state and variance · seen in: Coupa (approval-queue visibility),
  Oracle Receipt Accounting · priority: **common** · spine: **a REPORT VIEW over verified existing FKs**
  (`GoodsReceiptNote.bill`, `FreightInvoice.bill`, `LandedCostVoucher.bill`) — **no new table** · **buildable now**
- **Payment execution, aging buckets, dunning, cash application, e-invoicing/PEPPOL** · seen in: Coupa,
  Tradeshift · priority: table-stakes *in AP products* · spine: **accounting owns all of it** (`Bill.amount_paid()`,
  `balance_due()`, `recompute_payment_status()`, `accounting.Payment`/`PaymentAllocation`) · **out of scope — L29**
- **OCR / AI invoice capture from PDF or email** · seen in: Coupa (Rossum AI), Tradeshift · priority:
  differentiator · **integration/later**

### Bullet 2 — Accounts Receivable → **ALREADY COVERED; 4.18 adds a register view only**

- **Order → invoice** · **ALREADY COVERED BY `apps/scm/models/OrderManagement/SalesOrders.py:86`**
- **Activity/storage-based client billing → draft invoice** · **ALREADY COVERED BY
  `apps/scm/models/ThirdPartyLogistics/ClientBillingRuns.py:691` (`draft_invoice()`)**
- **Return → credit note** · **ALREADY COVERED BY
  `apps/scm/models/ReturnsManagement/ReturnAuthorizations.py:194`**
- **Customer self-service invoice/POD retrieval** · **ALREADY COVERED BY
  `apps/scm/models/CustomerPortal/PortalDocumentShares.py:174` and `PortalOrderInquiries.py:178`**
- **Freight recovery / accessorial rebill to the customer** (charging the customer for what the carrier charged
  us) · seen in: Magaya, Descartes, 3PL billing suites · priority: **common** · spine: expressible today as a
  `ClientRateCard` charge (4.17) — **park as a 4.17 refinement**, not a 4.18 table
- **One consolidated "SCM receivables" register** — every SCM document holding an `accounting.Invoice` link with
  its status and balance · priority: **common** · spine: **a REPORT VIEW over verified existing FKs** — **no new
  table** · **buildable now**
- **AR aging, dunning, cash application, collections** · spine: **accounting owns it** · **out of scope — L29**

### Bullet 4 — Budgeting → **ALREADY COVERED BY `accounting.Budget`/`BudgetLine` + `PurchaseRequisition.budget_check()`; 4.18 adds a department view**

- **Budget checking at requisition/PO time with a committed-spend figure** · seen in: Coupa (budget control),
  Oracle, SAP · priority: table-stakes · spine: **ALREADY COVERED BY
  `apps/scm/models/ProcurementManagement/PurchaseRequisitions.py:94` (`budget_check()`)** — returns
  budgeted/committed/requested/remaining/over_budget from `accounting.BudgetLine` · nothing to build
- **Budget by supply-chain department / cost centre** · priority: table-stakes · spine: **the dimension already
  exists** — `accounting.BudgetLine.org_unit → core.OrgUnit` (`BudgetLines.py:10`) and
  `PurchaseRequisition.org_unit` (`:47`, "the budget dimension"). **A new SCM Budget table would be a second source
  of truth and is forbidden (L29).** · nothing to build
- **Budget vs. actual variance across the whole supply-chain spend, not just requisitions** — PR/PO commitments +
  freight invoices + landed-cost vouchers + maintenance external cost, grouped by `OrgUnit` · seen in: Coupa
  (spend visibility), Oracle, Infor · priority: **common** · spine: **a REPORT VIEW joining verified existing
  models** — `accounting.BudgetLine` (budget) vs. `PurchaseRequisitionLine`/`PurchaseOrderLine` (committed, both
  carry `gl_account`) vs. `FreightInvoice.billed_amount` + `LandedCostVoucher.actual_total` (incurred) —
  **no new table** · **buildable now**
- **Multi-version budgets (original / revised / forecast) and approval** · spine: **already on
  `accounting.Budget.version`/`status`** (`Budgets.py:11–12`) · nothing to build
- **Rolling re-forecast, budget workflow/approval routing, encumbrance accounting** · priority: differentiator ·
  **DEFERRED** — `budget_check()`'s docstring (`:97`) records the deliberate decision *not* to store an
  encumbrance; reversing it is an accounting-module decision, not 4.18's

### Beyond the bullets

- **Cost variance reporting: estimated vs. actual landed cost per shipment/item, with the margin impact** · seen
  in: Infor ("know where you're losing margin while a job is live, not at month-end"), Oracle, VISCO · priority:
  **common** · spine: **a REPORT VIEW** over `LandedCostAllocation` · **buildable now**
- **True unit cost / true gross margin per item including landed cost** · seen in: NetSuite, VISCO, Magaya,
  Zonos · priority: **common** · spine: extends the verified `valuation_report` (`Reports.py:49`) with the uplift
  column — and 4.11's `gross margin analysis` bullet is where the *analytics* version lives · **buildable now**
- **Landed-cost simulation / scenario modelling before committing a PO** · seen in: VISCO (estimate at PO
  creation), Zonos/Avalara (real-time quote at checkout), gitnux/wifitalents comparison criteria ("scenario
  modeling") · priority: **differentiator** · **DEFERRED**
- **Inventory-value GL posting (perpetual-inventory journal entries)** · seen in: every suite · priority:
  table-stakes *in an ERP* · spine: **`accounting.JournalEntry` — and SCM does not post it.** Every SCM sub-module
  to date stops at a draft `Bill`/`Invoice` (L29, and 6 separate docstrings say so verbatim). 4.18 keeps that line:
  **it drafts the Bill, accounting posts the entry.** · **out of scope by architecture, not by effort**

---

## Recommended build scope (this pass — 3 models + 1 optional)

Landed cost is the centrepiece; AP, AR and Budgeting are report surfaces over already-built FKs.

Backend package: `apps/scm/{models,forms,views,urls}/FinanceIntegration/`.
Templates: `templates/scm/finance/<entity>/{list,detail,form}.html` (+ standalone report pages at
`templates/scm/finance/`).

### 1. `LandedCostVoucher` [**LC-**] — `models/FinanceIntegration/LandedCostVouchers.py`
The document that gathers the extra costs of one inbound receipt and turns them into inventory value.
Justified by: charge categories, estimated→actual variance, accrual workflow, voyage/trade-operation grouping,
separate cost vendor, multi-currency, AP hand-off.

- `TenantNumbered`, `NUMBER_PREFIX = "LC"`, `unique_together = ("tenant", "number")`
- **Verified FKs:** `goods_receipt → "scm.GoodsReceiptNote"` PROTECT (`GoodsReceiptNotes.py:15`) — the receipt whose
  layers get uplifted; `shipment → "scm.Shipment"` SET_NULL null/blank (`Shipments.py:18`) — the D365
  voyage/Oracle trade-operation stand-in; `trade_document → "scm.TradeDocument"` SET_NULL null/blank
  (`TradeDocuments.py:73`) — customs value + incoterm source; `currency → "accounting.Currency"` SET_NULL
  (**GLOBAL — scope the form by `is_active`, not tenant**); `bill → "accounting.Bill"` SET_NULL null/blank
  **`editable=False`** — the AP hand-off, copying `FreightInvoices.py:63`
- `cost_date` (DateField), `notes`
- `STATUS_CHOICES = [("draft","Draft"), ("allocated","Allocated"), ("accrued","Accrued"),
  ("reconciled","Reconciled"), ("cancelled","Cancelled")]`, `EDITABLE_STATUSES = ("draft",)`
- `ALLOCATION_BASIS_CHOICES = [("value","By Value"), ("quantity","By Quantity"), ("weight","By Weight"),
  ("volume","By Volume"), ("equal","Equal"), ("manual","Manual")]` — the union of NetSuite / Odoo / D365 / VISCO
- `allocation_basis` (default `"value"`) — the voucher-level default a charge line may override
- Derived, `editable=False`: `estimated_total`, `actual_total`, `variance_amount`, `variance_pct`,
  `allocated_total`
- Methods: `recalc_totals()` (Python sum, never `F()` — the SQLite integer-division trap the rest of `scm` avoids,
  cf. `FreightInvoices.py:76`); `allocate()` (writes/rewrites `LandedCostAllocation` rows inside
  `transaction.atomic()`, rolls `Item.apply_landed_cost`); `draft_bill()` (idempotent — mirrors
  `FreightInvoice.handoff`, tenant-admin gated per L27 because it moves money); `is_editable` property
- Indexes: `(tenant, status)`, `(tenant, cost_date)`, `(tenant, goods_receipt)`

### 2. `LandedCostCharge` — same file, child of the voucher (tenant-less, reached via `voucher.tenant`)
One cost component. Justified by: the charge-name taxonomy, per-charge allocation basis, estimated vs. actual,
recoverable-vs-capitalised tax, a different vendor per charge, duty by HS code.

- `voucher` FK CASCADE `related_name="charges"`
- `CHARGE_TYPE_CHOICES = [("freight","Freight"), ("duty","Customs Duty"), ("brokerage","Customs & Brokerage"),
  ("insurance","Insurance"), ("handling","Handling"), ("drayage","Drayage / Inland"),
  ("port_fees","Port & Terminal Fees"), ("fuel_surcharge","Fuel Surcharge"), ("inspection","Inspection / Fumigation"),
  ("storage","Storage / Demurrage"), ("other","Other")]` — sibling vocabulary to the verified
  `FreightInvoiceLine.CHARGE_TYPE_CHOICES` (`FreightInvoices.py:140`)
- `description`, `party → "core.Party"` SET_NULL null/blank (the charge vendor — a `PartyRole`, never a new vendor
  table), `freight_invoice → "scm.FreightInvoice"` SET_NULL null/blank (link the 4.6 audited carrier bill as the
  actual — reuse, don't re-key)
- `estimated_amount`, `actual_amount` (both `Decimal(14,2)`, `MinValueValidator(ZERO)`); `variance_amount` **property**
- `allocation_basis` — same choices, **blank = inherit the voucher's** (VISCO's "freight by weight, insurance by
  value" in one document; the thing NetSuite cannot do)
- `gl_account → "accounting.GLAccount"` SET_NULL null/blank (expense/accrual account — maps 1:1 onto the verified
  `accounting.BillLine.gl_account`, so the drafted bill lands on the right account)
- `tax_code → "accounting.TaxCode"` SET_NULL null/blank — **extends accounting's tax master, never a second one**
- `is_recoverable` (BooleanField, default `False`) — recoverable VAT must not capitalise into inventory
- `capitalise_to_inventory` (BooleanField, default `True`) — a charge that is pure period expense still belongs on
  the voucher for the AP hand-off but must not touch stock value
- Duty slice (only meaningful when `charge_type="duty"`): `hs_code` (CharField 20, blank),
  `country_of_origin` (CharField 64, blank), `duty_rate_pct` (`Decimal(6,3)`, default 0) —
  **snapshot columns, matching 4.12's frozen-declaration precedent (`TradeDocuments.py:26–33`); they do NOT go on
  `Item`**

### 3. `LandedCostAllocation` — same file. **The additive valuation layer.**
The per-receipt-line uplift the valuation report reads. Justified by: allocation to receipt line / PO schedule /
unit, per-shipment cost retrieval, and Odoo's "extra valuation layer linked to the original" architecture — which
is the only shape compatible with NavERP's append-only `StockMove`.

- `voucher` FK CASCADE `related_name="allocations"`; `charge` FK CASCADE `related_name="allocations"`
- `goods_receipt_line → "scm.GoodsReceiptLine"` PROTECT (`GoodsReceiptNotes.py:166`)
- `item → "scm.Item"` PROTECT (`Items.py:63`)
- `stock_move → "scm.StockMove"` SET_NULL null/blank (`StockMoves.py:13`) — **the exact inbound cost layer this
  uplifts.** Nullable because a receipt booked before 4.18 shipped has no allocation, and because a landed-cost
  voucher may legitimately precede the physical posting
- All `editable=False` (written by `allocate()`, never hand-typed): `quantity` (`Decimal(14,4)` — the receipt
  quantity at allocation time), `basis_value` (`Decimal(16,4)` — the weight/volume/value/qty number the split
  actually used, stored so the arithmetic is auditable), `allocated_amount` (`Decimal(14,2)`),
  `unit_cost_uplift` (`Decimal(14,4)` = allocated ÷ quantity)
- Index: `(tenant, item)`, `(tenant, stock_move)` — the valuation report joins on both
- **Rounding rule to pin in the contract:** the last allocation row absorbs the rounding remainder so
  `Σ allocated_amount == charge.actual_amount` exactly — a cent lost here is a cent of inventory value that never
  reconciles

### 4. *(optional — cut this first if the session is tight)* `DutyTariff` [**DTY-**] — `models/FinanceIntegration/DutyTariffs.py`
A tenant-scoped duty-rate master `accounting.TaxCode` structurally cannot be.
Justified by: Avalara/Descartes/VISCO's HS-code × origin-country × effective-dated duty rate.

- `TenantOwned`; `hs_code` (CharField 20), `country_of_origin` (CharField 64, blank = any),
  `description`, `duty_rate_pct` (`Decimal(6,3)`), `effective_from` / `effective_to` (DateField, null/blank),
  `is_active`, optional `tax_code → "accounting.TaxCode"` SET_NULL (the recoverable import-VAT counterpart)
- `unique_together = ("tenant", "hs_code", "country_of_origin", "effective_from")`; index `(tenant, hs_code)`
- Read by the duty charge line to default `duty_rate_pct` **by transaction date** (VISCO's "apply the correct rate
  by transaction date"); the value stays snapshotted on the charge so a later rate change never rewrites history

### Extensions to already-built models (surgical, additive, all-default — the `is_spare_part` precedent)
Not new models, but the pass does not work without them:

- **`scm.Item`** (`Items.py:63`) — `weight_kg` (`Decimal(12,4)`, null/blank) and `volume_cbm` (`Decimal(12,4)`,
  null/blank). Without these, allocate-by-weight and allocate-by-volume have no basis to read. Additive and
  nullable, so no existing row changes meaning and nothing needs backfilling. **Do NOT add `hs_code` to `Item`** —
  4.12 ruled on that explicitly (`TradeDocuments.py:30`).
- **`scm.Item.apply_landed_cost(total_amount)`** — a new *method* (no new column) mirroring `apply_receipt`
  (`Items.py:179`): raise the cached `average_cost` by `total_amount ÷ current on-hand`. WAC revaluation is exactly
  that, and it keeps the cache consistent without touching `StockMove`.
- **`views/InventoryManagement/Reports.py::_item_valuation`** (`:15`) — add the per-move uplift so FIFO/LIFO layers
  value at `unit_cost + uplift`. This is the single edit that makes landed cost *real* rather than decorative.
  ⚠ Single-writer file shared with 4.3 — surgical `Edit` only, and the transfer-exclusion rule at `:30` must survive.

### Report/view surfaces (no models — the other four bullets)
- `scm/finance/payables.html` — SCM payables register: every `GoodsReceiptNote`/`FreightInvoice`/`LandedCostVoucher`
  carrying an `accounting.Bill`, with match/approval state and variance
- `scm/finance/receivables.html` — SCM receivables register: every `SalesOrder`/`ClientBillingRun`/
  `ReturnAuthorization` carrying an `accounting.Invoice`, with status and balance
- `scm/finance/budget_variance.html` — supply-chain budget vs. commitment vs. actual, grouped by `core.OrgUnit`
- `scm/finance/landed_cost_variance.html` — estimated vs. actual by charge type / shipment / item

### Suggested `LIVE_LINKS["4.18"]` shape
`Accounts Payable → scm:finance_payables` · `Accounts Receivable → scm:finance_receivables` ·
`Landed Cost Calculation → scm:landedcostvoucher_list` · `Budgeting → scm:finance_budget_variance` ·
`Tax Management → scm:dutytariff_list` (or the landed-cost variance report if model 4 is cut).

---

## Explicit verdict per NavERP.md bullet

| Bullet | Verdict | Where |
|---|---|---|
| **Accounts Payable** | **ALREADY COVERED** by `apps/scm/models/ProcurementManagement/GoodsReceiptNotes.py` (three-way match → `accounting.Bill`) + `apps/scm/models/TransportationManagement/FreightInvoices.py` (freight audit → `accounting.Bill`). **4.18 EXTENDS** with `LandedCostVoucher.draft_bill()` and a read-only payables register view. **No AP table.** |
| **Accounts Receivable** | **ALREADY COVERED** by `apps/scm/models/OrderManagement/SalesOrders.py:86`, `apps/scm/models/ThirdPartyLogistics/ClientBillingRuns.py:691`, `apps/scm/models/ReturnsManagement/ReturnAuthorizations.py:194`, `apps/scm/models/CustomerPortal/PortalDocumentShares.py:174`. **4.18 EXTENDS** with a read-only receivables register view. **No AR table.** |
| **Landed Cost Calculation** | **NEW MODELS** — `LandedCostVoucher` + `LandedCostCharge` + `LandedCostAllocation`. The only bullet with no existing home. **EXTENDS** `scm.Item` (`weight_kg`, `volume_cbm`, `apply_landed_cost()`) and `views/InventoryManagement/Reports.py::_item_valuation`. |
| **Budgeting** | **ALREADY COVERED** by `apps/accounting/models/Budgeting/Budgets.py` + `BudgetLines.py` (`org_unit` **is** the supply-chain-department dimension) and `apps/scm/models/ProcurementManagement/PurchaseRequisitions.py:94` (`budget_check()`). **4.18 EXTENDS** with a budget-variance report view across PR/PO/freight/landed-cost spend. **No Budget table — that would be L29's second source of truth.** |
| **Tax Management** | **EXTENDS** `apps/accounting/models/Tax/TaxCodes.py` by FK (`LandedCostCharge.tax_code`) + `is_recoverable` handling. **One small NEW model** `DutyTariff` for HS-code × origin duty rates, because `TaxCode.tax_type` is `sales/vat/gst/use` only and has no HS code. **Tax codes are NOT re-declared.** |

---

## Architecture decisions to hand the todo agent (get these wrong and the pass fails)

1. **SCM still posts NO `JournalEntry`.** Six existing docstrings say so verbatim
   (`ReturnAuthorizations.py:15`, `FreightInvoices.py:8`, `ClientBillingRuns.py:29`, `TemperatureExcursions.py:62`,
   `coldchain.py:71`, `admin.py:1334`). 4.18 is the sub-module most tempted to break it and must not: it drafts an
   `accounting.Bill`, and accounting posts the entry. L29.
2. **`StockMove` rows are never edited.** The uplift is an additive `LandedCostAllocation` row (Odoo's model), not
   a mutation of `StockMove.unit_cost`. The valuation *reader* adds them.
3. **Idempotency on both actions.** `allocate()` must be re-runnable (delete-and-rewrite this voucher's allocation
   rows inside `transaction.atomic()`, then re-roll the cached average); `draft_bill()` must be a no-op when
   `bill_id` is already set — the `FreightInvoice.handoff` precedent, which has a test at
   `tests/test_views.py:5132` asserting exactly that.
4. **`accounting.Currency` is GLOBAL (no tenant column).** `TenantModelForm`'s scoping pass cannot handle it —
   scope the dropdown by `is_active` (`forms/ThirdPartyLogistics/ClientRateCards.py:136` is the worked precedent).
5. **Precision mismatch on the hand-off.** `LandedCostCharge` amounts are `(14,2)` but `accounting.BillLine`
   recomputes `line_total = quantity × unit_price` in its own `save()` (`Bills.py:91`) — draft with
   `quantity=1, unit_price=<amount>` so nothing is re-derived and lost, and copy `tax_code.rate_pct` into
   `tax_rate_pct` (there is no `tax_code` FK on `BillLine`).
6. **Rounding remainder** goes to the last allocation row so the allocated total ties to the charge exactly.
7. **Tenant-admin gate** on `allocate()` and `draft_bill()` (L27) — both change money.

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **Gross-margin analysis / cost-breakdown dashboards / freight-cost-per-unit KPI** → **4.11 Supply Chain
  Analytics** (built; `_r_freight_cost_per_unit` already exists at `analytics.py:2130`, and 4.11's own bullet is
  "Financial Reporting — Gross margin analysis and supply chain cost breakdowns"). 4.18 supplies the *true* unit
  cost; 4.11 is where the trend charts live.
- **Freight recovery / accessorial rebill to a 3PL client** → **4.17** (`ClientRateCard` charge types).
- **Customs filing, licences, trade documents, FTA rules-of-origin, denied-party screening** → **4.12** (built).
  4.18 reads `TradeDocument.declared_value`/`incoterm`; it files nothing.
- **Carrier rate-card contract amounts and the freight audit itself** → **4.6** (built). 4.18 links the audited
  `FreightInvoice` as a landed-cost *actual*; it does not re-audit.
- **EDI / e-invoicing / PEPPOL / ERP connectors / tariff-content feeds** → **4.19 Integration & API Gateway**.
- **Payment execution, AP/AR aging, dunning, cash application, bank reconciliation, journal posting, tax returns**
  → **`apps/accounting` (Module 2)**. Already built. L29.
- **Item master enrichment beyond `weight_kg`/`volume_cbm`** (pricing tiers, price lists) → **Module 5**.

## Deferred (later passes / integrations)

- **Auto-cost rules** (`LandedCostRule`: cost templates per vendor/route/container/item that pre-populate charges) —
  D365's `Auto costs`, VISCO's freight benchmarks. A 5th table; over-scope for one pass.
- **Voyage/container/folio as first-class entities** — D365's three-level grouping. NavERP models it as a
  `Shipment` FK for now; promote only if a bullet demands it.
- **Landed-cost simulation / what-if before PO commitment** — needs the rule engine above first.
- **Live global tariff/duty content** (Descartes CustomsInfo, Avalara) and **AI HS classification** —
  integration/later; `DutyTariff` is the table they would populate.
- **Duty drawback, FTZ, FTA preference qualification** — rules engines, parked at `research-scm-4.12.md:360` and
  still parked.
- **Encumbrance / commitment accounting as stored balances** — `budget_check()`'s docstring records the deliberate
  decision to keep it a view-time computation; reversing it is an `apps/accounting` decision.
- **Standard-cost variance postings (PPV) and periodic inventory revaluation runs** — Infor/NetSuite standard
  costing. Needs `accounting` to own the posting; 4.18 only guards `costing_method` eligibility.
- **OCR/AI invoice capture, e-invoicing compliance** — Coupa/Tradeshift territory; 4.19 + accounting.

---

## Sources

- [NetSuite — Entering Landed Cost on a Transaction (Oracle Docs)](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_N2418831.html)
- [NetSuite landed cost allocation methods — CohnReznick](https://www.cohnreznick.com/insights/optimize-inventory-tracking-with-netsuite-landed-costs)
- [Microsoft Dynamics 365 SCM — Auto costs setup (Landed Cost)](https://learn.microsoft.com/en-us/dynamics365/supply-chain/landed-cost/auto-cost-setup)
- [Microsoft Dynamics 365 SCM — Landed cost vs. Transportation management](https://learn.microsoft.com/en-us/dynamics365/supply-chain/landed-cost/landed-cost-vs-tms)
- [Oracle Fusion Cloud SCM — Landed Cost Management](https://docs.oracle.com/en/cloud/saas/supply-chain-management/21d/fapma/landed-cost-management.html)
- [SAP S/4HANA Cloud — Planned Delivery Cost of Purchasing (SAP Community)](https://community.sap.com/t5/enterprise-resource-planning-blog-posts-by-sap/planned-delivery-cost-of-purchasing-in-s-4hana-cloud-public-edition/ba-p/13572608)
- [SAP S/4HANA Cloud — Unplanned Delivery Cost of Purchasing (SAP Community)](https://community.sap.com/t5/enterprise-resource-planning-blog-posts-by-sap/unplanned-delivery-cost-of-purchasing-in-s4hana-cloud-public-edition/ba-p/13661882)
- [Acumatica — Purchase Order Management (landed cost)](https://www.acumatica.com/cloud-erp-software/distribution-management/purchase-order-management/)
- [Odoo 18 — Landed costs](https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/inventory/product_management/inventory_valuation/landed_costs.html)
- [VISCO — Landed Cost Software for Importers](https://viscosoftware.com/landed-cost-software-for-importers/)
- [Magaya — What is landed cost in logistics?](https://www.magaya.com/landed-cost/)
- [Avalara — AvaTax Cross-Border](https://www.avalara.com/us/en/products/global-commerce-offerings/avatax-cross-border.html)
- [Descartes CustomsInfo — Global Trade Content, HS Codes and Rulings](https://www.customsinfo.com/)
- [Descartes — Duty and Tariff Data](https://www.descartes.com/solutions/global-trade-intelligence/duty-and-tariff-data)
- [Coupa — Invoice Management](https://www.coupa.com/products/ap-automation/invoicing/)
- [Coupa — AP Automation](https://www.coupa.com/products/ap-automation/)
- [Infor CloudSuite Inventory Management overview — ERP Research](https://www.erpresearch.com/en-us/infor-cloudsuite-inventory-management)
- [Infor — Landed Cost Inventory Adjustment account (Infor Docs)](https://docs.infor.com/csi/10.x/en-us/csbiolh/inventory_user_cl_sl/mergedprojects/sl_invprod/fields/l/landed_cost_inv_adj_acct.html)
- [Top Landed Cost Software 2026 comparison — Gitnux](https://gitnux.org/best/landed-cost-software/)
