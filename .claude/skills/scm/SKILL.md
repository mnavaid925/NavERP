---
name: scm
description: Work on the SCM module (Module 4 — Supply Chain Management). As-built = 4.1 Procurement Management (requisitions, RFQs + quote comparison, purchase orders, goods receipts + three-way match) 4.2 Supplier Relationship Management (onboarding, signal-derived scorecards, contracts, catalogs, risk), 4.3 Inventory Management (the append-only StockMove ledger with derived on-hand, items/locations/lots, transfers, adjustments, reorder automation, FIFO/LIFO/WAC valuation), 4.4 Warehouse Management (putaway, wave/batch/zone picking + packing, cycle counting, yard), 4.5 Order Management (sales orders, credit/fraud validation, soft allocation, backorders, quote-to-order), 4.6 Transportation Management (carrier master + rate cards + derived on-time scorecard, loads + route stops + cube utilization, shipments + append-only tracking events + POD, freight audit → draft accounting.Bill), and 4.7 Demand Planning & Forecasting (statistical forecasts over DERIVED sales history with a decomposition waterfall, seasonality/promotion index curves, demand-sensing signals with a working order-surge detector, consensus adjustments, and a compute-then-apply safety-stock calculator on 4.3's ReorderRule), 4.8 Manufacturing / Production (versioned multi-level bills of materials with a cycle-guarded explosion, work centres with derived capacity/OEE, the work-order lifecycle posting component consumption and finished-goods production through 4.3's append-only ledger under new consumption/production move types, ledger-derived WIP costing, an MRP netting report and an infinite-capacity schedule board), and 4.9 Quality Management System (reusable inspection plans, inspections at the receipt/in-process/shipment trigger points with snapshotted results and a usage decision held separate from pass/fail, non-conformance reports with MRB dispositions where only a scrap moves stock, CAPA with effectiveness verification, audits whose findings ARE non-conformances, and generated certificates of analysis that are refused rather than issued off-spec), and 4.10 Returns Management (RMAs with an eligibility verdict snapshotted at approval, a receiving bench where only the disposition decision touches stock - a restock posts a positive receipt at a grade-written-down cost while intake posts nothing - credit notes drafted into accounting and stopped there, warranty claims against suppliers with typed partial-approval cost lines, and a customer return portal across a staff console, a logged-in request page and a token-gated public status page and return slip). and 4.11 Supply Chain Analytics (a closed 36-metric registry in apps/scm/analytics.py behind five computed report pages - inventory turnover/dead stock/FIFO aging, the spend cube with negotiated-savings and supplier leaderboards, OTD/OTIF/freight-per-unit/utilization with a carrier scorecard, operational margin and cost-to-serve that says on the page it is NOT the statutory P&L, and a deterministic explainable disruption composite that never claims to be AI - plus KpiTarget for human intent, KpiSnapshot freezing history that cannot be re-derived, and a SupplyChainAlert inbox ranked by value at risk with a de-duplicating detector). and 4.12 Contract & Compliance Management (a standing-obligation register whose CLM obligations point back at 4.2's contracts rather than duplicating them, import/export licences that decrement as documents are issued under them, trade paperwork hung off 4.6's shipments with HS codes snapshotted at issue, supplier ESG scorecards, and a GLEC/ISO-14083 freight-emissions estimate that reports its coverage gaps instead of a confident zero). and 4.13 Asset Management (scm.Asset as the operational asset spine with a cycle-guarded hierarchy and derived MTBF/MTTR/availability that answer None rather than a flattering zero, four-trigger preventive-maintenance plans whose schedule has exactly one writer, the MWO- maintenance work order - a SEPARATE document from 4.8's WO- production work order - carrying downtime, Maximo failure codes and the sub-module's one ledger write under a new maintenance StockMove type, an append-only MeterReading log with no edit and no delete route, and three computed report pages: a PM forecast board, an MRO storeroom over 4.3's Item/StockMove/ReorderRule with no SparePart table, and a repair-vs-replace page that READS accounting.FixedAsset). and 4.14 Labor Management (engineered multi-determinant labour standards with a most-specific-wins resolver that answers None rather than a zero standard, warehouse shift sessions on core.Party whose twelve productivity figures are all derived and all answer None on a zero denominator, booked direct/indirect activity intervals that SNAPSHOT the standard at file time so re-timing it cannot rewrite last month, volume-driven labour plans on 4.7's generate-then-review shape, and three computed pages - a task-assignment board writing only 4.4's EXISTING assigned_to column, an admin-only productivity scorecard, and a read-only payroll CSV hand-off that narrows to your own rows unless you are an admin; declares no attendance table because HRM owns attendance, no task table because 4.4 owns tasks, and writes no StockMove, no JournalEntry and nothing at all into hrm.*). and 4.15 Cold Chain Management (three of its five NavERP bullets are COMPUTED pages rather than tables: a ColdChainMonitor watching exactly one of a Location, an Asset or a Shipment through three typed PROTECT FKs and never a GenericForeignKey, an append-only TemperatureReading interval log with no edit and no delete route, and a TemperatureExcursion whose every measured column is editable=False and written solely by coldchain.detect_excursions() under a lock on the MONITOR row - because MariaDB cannot express the partial unique constraint that rule would otherwise be - with the breached limits SNAPSHOTTED onto the episode, mean kinetic temperature returning None rather than 0 on frozen ranges per USP <1079.2>, no temperature ever passing through q4() or carrying MinValueValidator(ZERO) since -18 C is the normal operating point, Cold Storage Inventory computed over 4.3 and Maintenance of Reefers computed over 4.13 so 4.15 declares zero maintenance entities and a reefer is derived as an asset with an active monitor). Use when the user asks to add/change/debug anything under apps/scm or templates/scm, extend the seed_scm seeder, touch SCM sidebar wiring (LIVE_LINKS 4.x), build the next SCM sub-module, or invokes /scm.
---

# SCM — Supply Chain Management (Module 4)

App path: `apps/scm`. Templates: `templates/scm/`. URL prefix: `/scm/`, `app_name = "scm"`.
Mirrors `NavERP.md` "## 4. Supply Chain Management (SCM)" (19 sub-modules, 4.1–4.19).

**As-built: 4.1 Procurement + 4.2 SRM + 4.3 Inventory + 4.4 Warehouse Management + 4.5 Order Management +
4.6 Transportation Management + 4.7 Demand Planning & Forecasting + 4.8 Manufacturing / Production + 4.9 Quality Management + 4.10 Returns Management + 4.11 Supply Chain Analytics + 4.12 Contract & Compliance Management + 4.13 Asset Management + 4.14 Labor Management + 4.15 Cold Chain Management + 4.16 Customer Portal + 4.17 Third-Party Logistics (3PL) + 4.18 Finance & Accounting Integration — 18 of 19.**
Only **4.19** is roadmap. Build the next one with `/next-module` (it takes the lowest `4.M` without a `LIVE_LINKS["4.M"]` entry) — see the reference apps
`apps/crm`/`apps/accounting` for the package layout and the mandatory
[Module Creation Sequence](../../CLAUDE.md).

## Overview

4.1 realizes the procure-to-pay chain from `NavERP.md` 4.1's five bullets:
`PurchaseRequisition → RFQ → RFQQuote (award) → PurchaseOrder → GoodsReceiptNote → three-way match vs accounting.Bill`.
It **owns** these procurement transaction tables — the ERD originally assigned them to Module 6 (Procurement), but
SCM ships first, so per lesson **L29** it owns them and Module 6 will EXTEND them by FK (strategic sourcing / e-auction
/ contract authoring / scorecards), never re-declare them. See lesson **L36**.

## Models  (`apps/scm/models/ProcurementManagement/<Entity>.py`)

Shared bases in `models/_base.py`: `TenantOwned` (tenant FK + timestamps, `related_name="+"`) and `TenantNumbered`
(adds a per-tenant `number` assigned once in `save()` via `apps.core.utils.next_number` with a retry loop). `ZERO` too.

**Core-spine reuse (all FK by string):** suppliers are `core.Party` + `core.PartyRole` (role `supplier` OR `vendor` —
both accepted, see `_supplier_parties`); departments are `core.OrgUnit`; money masters are in **`apps.accounting`**,
NOT core — `accounting.Currency` (GLOBAL, no tenant FK), `accounting.GLAccount`, `accounting.PaymentTerm`,
`accounting.Budget`/`BudgetLine`, `accounting.Bill`. **Line items are FREE-TEXT** (`item_description`/`sku_hint`/
`uom_hint`) because `core.Item` does not exist yet (Module 5) — lesson **L28**; the future migration is noted in each
line model's docstring.

- **`PurchaseRequisitions.py`** — `PurchaseRequisition` [`PR-`] + `PurchaseRequisitionLine`.
  Status: draft/pending_approval/approved/rejected/converted/cancelled. `estimated_total` derived (never hand-set).
  `approval_tier()` → the sign-off tier from `APPROVAL_TIERS` (standard ≤1000, manager ≤10000, executive above).
  `budget_check(lines=None)` compares the requisition against matching `accounting.BudgetLine` amounts at VIEW TIME
  (not a stored encumbrance) — `budgeted`/`committed`/`requested`/`remaining` all restricted to the SAME GL accounts
  the requisition's lines charge (L36-adjacent regression: committed is summed at line level per account, not other
  requisitions' whole totals). `.is_editable` = draft/pending.
- **`Rfqs.py`** — `RFQ` [`RFQ-`] + `RFQLine` + `RFQVendor` (invite list, own tenant FK) + `RFQQuote` [`QT-`] +
  `RFQQuoteLine`. RFQ status: draft/sent/closed/awarded/cancelled. Quote status: received/shortlisted/awarded/rejected.
  Quote `total` derived. `RFQVendor.has_responded` is a per-row `.exists()` — **N+1 in a loop**; the detail view sets
  `.responded` on each invite instead (never call the property in a template).
- **`PurchaseOrders.py`** — `PurchaseOrder` [`PO-`] + `PurchaseOrderLine`. **The canonical PO** (distinct from the
  lightweight `crm.PurchaseOrder` 1.12 quick-order — different app_label, coexists on purpose, do NOT dedupe).
  Nine-state lifecycle: draft/pending_approval/approved/sent/acknowledged/partially_received/received/cancelled/closed.
  `version` + `amendment_reason` = the amendment trail; `acknowledged_*`/`promised_ship_date` = staff-recorded vendor
  ack (no vendor login — L32); `cancelled_*`. Money totals derived. Received quantity is DERIVED:
  `PurchaseOrderLine.received_quantity()` (memoized, excludes cancelled receipts) and
  `PurchaseOrder.received_by_line()` = `{po_line_id: qty}` in ONE query (use this in loops, not the per-line call —
  perf, L-perf). `recompute_receipt_status(received_map=None)` and `rematch_receipts()` (re-matches EVERY receipt on
  the order — verdicts depend on the cross-receipt aggregate).
- **`GoodsReceiptNotes.py`** — `GoodsReceiptNote` [`GRN-`] + `GoodsReceiptLine`. Status: draft/received/cancelled.
  `recompute_match(received_map=None)` sets `match_status` ∈ not_matched/matched/price_variance/quantity_variance/
  over_received. **Over-receipt wins over a price gap** (accepting un-ordered goods is the more serious finding). The
  match compares **NET of tax**: `received_value()` (ex-tax) vs `billed_value()` (= `bill.subtotal`, ex-tax) within a
  2% tolerance — comparing against `bill.total` would flag every taxed bill as a price variance (real bug, locked by
  `test_taxed_bill_still_matches_on_net_value`).

## URLs / routes  (`apps/scm/urls/ProcurementManagement/`, `app_name="scm"`)

- **overview** — `scm:overview` (`/scm/`).
- **requisition** — `_list/_create/_detail/_edit/_delete` + `_submit` `_approve` `_reject` (POST).
- **rfq** — `_list/_create/_detail/_edit/_delete` + `_send` `_close` (POST) + `_compare` (the quote matrix, GET).
- **quote** — `_create` (takes `rfq_pk`) `_edit` `_delete` `_award` (POST; award drafts a PO).
- **purchaseorder** — `_list/_create/_detail/_edit/_delete` + `_amend` (GET form) + `_submit` `_approve` `_send`
  `_acknowledge` `_cancel` `_close` (POST).
- **goodsreceipt** — `_list/_create/_detail/_edit/_delete` + `_receive` `_cancel` `_rematch` (POST).

**Authorization** — `@tenant_admin_required` (spend/commitment gates): `requisition_approve`, `requisition_reject`,
`quote_award`, `purchaseorder_approve`, `purchaseorder_cancel`, `purchaseorder_amend`, `goodsreceipt_cancel`.
Everything else is `@login_required`. When a view is admin-gated, the template button MUST be wrapped in
`{% if request.user.is_superuser or request.user.is_tenant_admin %}` or it 403s (L32-adjacent).

## Templates  (`templates/scm/<submodule>/<entity>/<page>.html`)

Landing `templates/scm/overview.html`. Entities under `templates/scm/procurement/`:
`requisition/`, `rfq/` (+ `compare.html`), `quote/` (form only — a child of RFQ), `purchaseorder/`, `goodsreceipt/`,
each with `list/detail/form.html`. Extend `base.html`; design-system classes from `static/css/theme.css`.
**Badges are COLOUR-named** (`badge-green/amber/red/muted/info/slate`) — NEVER `badge-success/danger/warning` (L33);
always end a badge chain with `{% else %}{{ obj.get_<field>_display }}{% endif %}`. State callouts use
`<div class="card" style="border-inline-start:3px solid var(--x); background:var(--x-bg);">` + a `.text-danger`/
`.text-warn`/`.text-ok` utility (NOT inline colours, NOT physical `border-left`). Multi-line notes use
`{% comment %}…{% endcomment %}`, never `{# … #}`.

## Seeder  (`apps/scm/management/commands/seed_scm.py`)

`python manage.py seed_scm` (`--flush` to re-seed). Per tenant, walks the whole chain: an approved budget-checked
requisition + a pending one (so the approval queue isn't empty), an RFQ sent to two suppliers with quotes that differ
PER LINE (so `compare` has a real winner per row), the award + resulting PO, and a GRN three-way-matched against a
real `accounting.Bill` — deliberately short-shipping one line so the match lands on Quantity Variance. Idempotent via
a per-tenant `PurchaseRequisition` guard; reuses spine rows (suppliers matched by name, existing OrgUnit/Budget/
GLAccount). `--flush` deletes the linked `accounting.Bill` rows too (they're otherwise orphaned). Login as a tenant
admin (`admin_acme` / `password`) — the superuser has `tenant=None` and sees nothing.

## 4.2 Supplier Relationship Management  (`apps/scm/*/SupplierRelationshipManagement/`, templates `templates/scm/srm/`)

SRM on the `core.Party` supplier spine. Five models, all reusing `_supplier_parties` (supplier OR vendor role):

- **`SupplierProfiles.py`** — `SupplierProfile` (OneToOne on `core.Party`; SRM extension, distinct from the AP-only
  `accounting.VendorProfile` — a supplier can carry both). Onboarding lifecycle draft→qualification→due_diligence→
  approved (+rejected/suspended); a five-`dd_*`-boolean due-diligence checklist with `due_diligence_progress()`;
  `is_active`/`is_editable`. Actions: submit, approve (tenant-admin, **requires `onboarding_status=='due_diligence'`
  AND `due_diligence_complete`**), reject (tenant-admin, blocks approved), reopen (tenant-admin, rejected→draft),
  suspend/reinstate (tenant-admin).
- **`SupplierScorecards.py`** — `SupplierScorecard` [`SCR-`]. delivery/quality/price/responsiveness each 0-100
  (MaxValueValidator(100)), a re-weighted `overall_score` + A-F `grade`. `recompute_from_signals()` DERIVES the four
  from real 4.1 history in the period: on-time `GoodsReceiptNote`s, `GoodsReceiptLine` reject rate, best `RFQQuote`
  price, quote turnaround — prefetched + aggregated (one query each, not per-row). `manual_override` freezes it;
  `recompute_overall()` skips its save when unchanged. Actions: recompute (blocked when archived/override), publish.
- **`SupplierContracts.py`** — `SupplierContract` [`SC-`]. `days_to_expiry()`/`is_expiring_soon()`/`refresh_status()`
  (date-driven active↔expiring↔expired; terminated/renewed are terminal). List rolls statuses via
  `_roll_contract_statuses` (one bulk_update, not save-per-row). Actions: activate, renew (drafts a successor),
  terminate (tenant-admin + reason). `contract_edit` blocks terminated/expired/renewed.
- **`SupplierCatalogs.py`** — `SupplierCatalog` [`CAT-`] + `SupplierCatalogItem` (free-text, L28). Item formset
  prefix `items-`. Actions: activate (blocks empty).
- **`SupplierRiskAssessments.py`** — `SupplierRiskAssessment` [`SRA-`]. Four 1-5 factor scores →
  `recompute_risk_level()` derives `risk_level`/`risk_index` (**a single 5 forces at least High**). Actions:
  submit, review (tenant-admin).

**URLs** (`app_name="scm"`): `supplierprofile_*` (/suppliers/) + submit/approve/reject/reopen/suspend;
`scorecard_*` (/scorecards/) + recompute/publish; `contract_*` (/contracts/) + activate/renew/terminate;
`catalog_*` (/catalogs/) + activate; `riskassessment_*` (/risk-assessments/) + submit/review.
**Templates** under `templates/scm/srm/{supplierprofile,scorecard,contract,catalog,riskassessment}/`. Overview page
has a "Supplier Management" nav card. **LIVE_LINKS["4.2"]** maps the five bullets. **Seeder**: `_seed_srm_tenant`
(guarded independently of 4.1) seeds a profile/scorecard/contract/catalog/risk per supplier, scorecards derived from
real 4.1 signals; `--flush` clears the SRM tables.

## 4.3 Inventory Management  (`apps/scm/*/InventoryManagement/`, templates `templates/scm/inventory/`)

**SCM owns the INVENTORY SPINE** (ships-first, L29/L36/L37) — Module 5 extends it by FK, never re-declares it.

**Spine models.** `Items.py` = `ItemCategory` + `UOM` (code/name/factor) + `Item` (sku unique per tenant,
item_type stock/consumable/service, tracking none/lot/serial, costing_method weighted_avg/fifo/lifo,
`average_cost` = a CACHED display figure from `apply_receipt()`, **not** the quantity source of truth).
`Locations.py` = `Location` (warehouse/zone/bin/staging/transit, self-parent hierarchy, cycle-guarded `path()`).
`LotSerials.py` = `LotSerial` (lot/serial, expiry, available/quarantine/expired/consumed).
`StockMoves.py` = **`StockMove` — the append-only ledger**: signed `quantity` (+into/−out of a location),
`unit_cost` (IS the FIFO/LIFO/WAC cost layer), move_type receipt/issue/transfer/adjustment, `reference`
(source doc number). **No form, no edit/delete view, admin write disabled.** Corrections are compensating moves.

**THE RULE: on-hand and valuation are ALWAYS derived** — `Item.on_hand(location=None)`, `Item.total_value()`,
`Location.on_hand_value()`, `LotSerial.on_hand()`, `_item_valuation()`. There is no stored quantity anywhere.
Never add one.

**Domain models.** `StockTransfers.py` = `StockTransfer` [`TRF-`] + line (draft/in_transit/completed/cancelled;
completing posts a PAIRED −/+ move per line). `StockAdjustments.py` = `StockAdjustment` [`ADJ-`] + line
(draft/posted/cancelled; reason cycle_count/write_off/damage/found/revaluation/other; signed `quantity_delta`;
`value_impact()`). `ReorderRules.py` = `ReorderRule` (unique per tenant+item+location; `current_on_hand()`,
`is_below_point()`, `suggested_quantity()`).

**The posting service** lives in `apps/scm/views/_helpers.py` and is the ONLY way stock moves:
`_post_stock_move` (rolls `apply_receipt` BEFORE writing an inbound move so the average weights correctly),
`_insufficient_stock` (reads the LIVE aggregate so it sees earlier lines in the same transaction),
`_post_transfer`, `_post_adjustment`. Callers wrap them in `transaction.atomic()` and catch `ValidationError`
→ a friendly message; a shortfall rolls the whole post back. This is also the documented future hook for 4.1's
`GoodsReceiptNote.mark_received`.

**URLs**: `item_*` (/items/), `category_*` (/categories/), `uom_*` (/uoms/), `location_*` (/locations/),
`lotserial_*` (/lot-serials/), `stocktransfer_*` (/transfers/) + `_complete`/`_cancel`, `stockadjustment_*`
(/adjustments/) + `_post`/`_cancel`, `reorderrule_*` (/reorder-rules/); reports `valuation_report` (/valuation/),
`reorder_alerts`, `stock_ledger`, `on_hand_by_location`. **Tenant-admin gated**: transfer complete/cancel and
adjustment post/cancel (they move real stock). **Templates** under `templates/scm/inventory/<entity>/` with the
four report pages at that root; the stock ledger deliberately has NO actions column.
**Seeder**: `_seed_inventory_tenant` (guarded on Item) creates UOMs/categories/3 items across costing methods, two
locations, opening-balance receipt moves, a completed transfer, a posted cycle-count adjustment, and two reorder
rules (one below on-hand so an alert fires).

## 4.4 Warehouse Management  (`apps/scm/*/WarehouseManagement/`, templates `templates/scm/warehouse/`)

Layered ON the 4.3 spine, never beside it. **Bins ARE `Location`s** — 4.4 added `capacity`, `pick_sequence`,
`abc_class` and `is_pickable` to the existing model rather than forking a Bin table (which would split the
StockMove FK and the on-hand aggregate in two). `GoodsReceiptNote` gained a staging `location` FK.

- **`PutawayTasks.py`** — `PutawayTask` [`PUT-`]: receipt → staging → bin, strategies directed/fixed/random/
  cross_dock. Completing (tenant-admin, locked) posts the staging→bin pair via `_post_putaway`.
- **`PickTasks.py`** — `PickTask` [`PIK-`] + line: single/wave/batch/zone. Lines order by the bin's
  `pick_sequence`. A line may be SHORT picked, never over-picked. Confirming (tenant-admin, locked) issues only
  `quantity_picked` via `_post_pick`. Packing records label DATA only — carriers/rendering are 4.6 TMS.
  Stands alone: no `SalesOrder` FK because Module 8 isn't built.
- **`CycleCountTasks.py`** — `CycleCountTask` [`CC-`] + line: scheduled → in_progress → counted → reconciled.
  **`expected_quantity` is snapshotted server-side on START** (not a form field, read-only in admin) — never
  re-derived at reconcile, or mid-count movement would silently absorb the discrepancy. `counted_quantity` is
  nullable so uncounted ≠ counted-zero. Reconciling makes **exactly one** `StockAdjustment(reason='cycle_count')`
  and posts it through the EXISTING adjustment path; a no-variance count reconciles without an empty document.
  **Past `scheduled` the sheet's COMPOSITION is frozen** (`BaseCycleCountTaskLineFormSet(lock_sheet=True)`:
  `extra=0`, `item`/`lot_serial`/`DELETE` `disabled`, plus a `clean()` re-check because a hand-rolled POST can
  inflate `TOTAL_FORMS`). Without it a row added after start carried `expected=0`, so reconcile posted the whole
  counted quantity as a found-stock variance — a fabricated adjustment against a never-snapshotted item. Freezing
  is what makes the snapshot mean anything; `counted_quantity`/`notes` stay writable, since that IS the job.
  `start` takes `select_for_update()` (snapshot-exactly-once) and writes via one `bulk_update`.
- **`YardVisits.py`** — `YardVisit` [`YRD-`]: scheduled/arrived/at_dock/departed with derived `dwell_minutes()`.
  Posts NO StockMove. `carrier_name` is free text until 4.6.

- **`picktask_start`** (released → picking) is plain `@login_required` — it moves no stock, it only marks who
  took the task. Added because `picking` was otherwise a status nothing could reach.

**The GRN→StockMove wire-up lives here too** (`_post_grn_receipt`/`_reverse_grn_receipt` in `views/_helpers.py`):
booking a goods receipt posts an inbound move per received line at the PO line's `unit_price`; cancelling posts
COMPENSATING moves (never deletes) and is **GUARDED** — if putaway has already moved the stock on, cancelling is
REFUSED rather than driving staging negative while the bin keeps the un-reversed quantity (`receive → putaway →
cancel` is an ordinary sequence, not an edge case). A workspace with NO location does **not** block booking —
4.1 stands alone without the 4.3 spine — it just reports a distinct `blocked` reason (L38). `goodsreceipt_receive` is now tenant-admin gated because it moves stock. Item
resolution is best-effort via `sku_hint`→`Item.sku` (4.1 lines are free text) and RETURNS unmatched lines so the
view warns rather than silently posting nothing.

**URLs**: `putawaytask_*` (/putaway/) + `_start`/`_complete`/`_cancel`; `picktask_*` (/picks/) + `_release`/
`_start`/`_confirm`/`_pack`/`_cancel`; `cyclecounttask_*` (/cycle-counts/) + `_start`/`_complete`/`_reconcile`/`_cancel`;
`yardvisit_*` (/yard/) + `_arrive`/`_dock`/`_depart`/`_cancel`. **Seeder**: `_seed_warehouse_tenant` runs AFTER
`_seed_inventory_tenant` — a real dependency, since every row references its items/locations.

## 4.5 Order Management System  (`apps/scm/*/OrderManagement/`, templates `templates/scm/orders/`)

**apps/scm OWNS `SalesOrder`/`SalesOrderLine`** (ships-first, L28/L29/L36/L37). The ERD nominally
assigns them to Modules 1/8/9, but CRM is fully built across all twelve of its sub-modules and
deliberately stopped at `Lead → Opportunity → Quote`; Modules 8/9 don't exist. Module 8.6 "Order
Management" is a DIFFERENT, later feature set (amend/cancel with impact analysis, revenue
recognition) that FKs INTO this order — it does not re-declare it. Unlike `crm.PurchaseOrder` vs
`scm.PurchaseOrder` there is no order-shaped model in CRM to collide with.

- **`SalesOrders.py`** — `SalesOrder` [`SO-`] + `SalesOrderLine`. Nine states: draft → submitted /
  on_hold → allocated / partially_fulfilled → fulfilled → invoiced → closed (+ cancelled).
  `EDITABLE_STATUSES = ("draft",)` — no amend flow, that is 8.6's job.
  `recompute_allocation_status()` derives submitted/partially_fulfilled/allocated in ONE grouped
  annotate and refuses to touch any other status (mirrors `PurchaseOrder.recompute_receipt_status`).
  `partially_fulfilled` means *part-reserved, remainder backordered* — NOT partially shipped; this
  sub-module never tracks physical shipment. `promised_date` is stamped once, on first reaching
  `allocated`, and never moved. `recalc_totals()` sums in **Python**, not `F()` — an `F()/100`
  expression integer-divides on SQLite and silently drops per-line discount/tax.
  **`SalesOrderLine.item` is nullable ONLY for quote conversion** (see below); `salesorder_submit`
  refuses while any line is unmapped, so it is a visible draft to-do and never something that ships.
- **`SalesOrderAllocations.py`** — `SalesOrderAllocation`: a **soft reservation that posts NO
  StockMove**. On-hand does not move when stock is allocated; what moves is availability-to-promise.
  Stock physically leaves only via 4.4's `PickTask` confirm — the append-only ledger stays the sole
  physical truth (L37). `reserved`/`released` both count as allocated (released = sent to the floor);
  `cancelled` frees the claim. `clean()` guards Σ ≤ line.quantity_ordered.

**Two guards, deliberately separate questions** (`views/OrderManagement/SalesOrderAllocations.py`):
`clean()` asks *is this more than was ordered?*; `_available_to_promise()` asks *is the stock
actually there?* = `on_hand(location) − other active allocations there`. An order for 10 with 3 on
hand fails the second, not the first. Raw on-hand would promise the same unit to two customers.
Incoming POs are NOT counted (supply-aware ATP is deferred). The create/edit paths take a
**`select_for_update` row lock on the Item** (`_lock_item`) so the check and the write are one
decision — the item, not the line, because availability is per item+location ACROSS orders.

**Credit/fraud** live in the VIEW (`_evaluate_hold`), not the model — scm models never cross-import a
peer app, and this reads `accounting.CustomerProfile`/`Invoice`. It reuses the `over_limit` pattern
from `accounting.views…invoice_detail`. The order's own total counts toward exposure. A held order's
`confirmation_sent_at` stays None — it was never confirmed to anyone. `release_hold` APPENDS its
reason so the original justification survives the override.

**Quote-to-order** (`salesorder_create_from_quote`, the first scm→crm model import): closes the dead
end where `crm.Quote.quote_accept()` created nothing downstream. **Item mapping is never guessed** —
`crm.QuoteLine.product` is a CRM `Product` with no mapping to `scm.Item`, so lines arrive with the
quote's `description` and `item=None` and staff map them before submit. Idempotent: a second attempt
redirects to the existing order.

**URLs — the prefix is `sales-orders/`, NOT `orders/`** (already `PurchaseOrder`'s; same `app_name`,
one concatenated list, first-match-wins would shadow it permanently). Allocations live at
`allocations/`, created via `sales-order-lines/<line_pk>/allocations/add/`.
**Gotcha:** `SalesOrderLine` has **no tenant column** — always scope it through
`sales_order__tenant=request.tenant`. **Seeder**: `_seed_oms_tenant` runs after
`_seed_inventory_tenant`; its three demo orders reach their status by *derivation*, not hand-setting.

## 4.6 Transportation Management System (TMS)  (`apps/scm/*/TransportationManagement/`, templates `templates/scm/transportation/`)

The carrier/freight layer 4.4 and 4.5 deferred to it — it's where `YardVisit.carrier_name`/`PickTask.tracking_ref`
free-text placeholders finally get a real `Carrier` master. Four entities (8 tables). Shared MODE/EQUIPMENT/
SERVICE_LEVEL choice vocabularies live at the top of `Carriers.py` and are imported by the sibling entity modules
(one-way, acyclic).

- **`Carriers.py`** — `Carrier` [`CAR-`] + `CarrierRateCard` (tenant-less child). **A carrier is a spine-backed
  profile on `core.Party`**, NOT a standalone company table — `party` is a REQUIRED FK (PROTECT), scoped by a new
  `_carrier_parties` helper (`supplier`/`vendor`/`partner` roles) in `forms/_common.py`; `Carrier.name` is a property
  reading `party.name`. This mirrors 4.2 `SupplierProfile` and keeps the freight→Bill hand-off clean (Bill.party is
  required). `carrier_type`/`primary_mode`/`service_level`/SCAC/MC/DOT/insurance-expiry + `is_preferred`/status.
  **`on_time_delivery_pct` is DERIVED** by `recompute_scorecard()` from delivered-shipment history (on-time =
  `actual_delivery_at.date() <= planned_delivery_date`), editable=False, and — like `SupplierScorecard` — refuses to
  wipe a real score with a phantom zero when there's no signal. `CarrierRateCard`: lane/mode/equipment/rate_basis +
  base_rate + `fuel_surcharge_pct` (0–100) + `min_charge` + `rate_with_fuel` property + `currency`→`accounting.Currency`.
- **`Loads.py`** — `Load` [`LD-`] + `LoadStop` (tenant-less child). The route/trip consolidation unit.
  status planning→tendered→booked→in_transit→delivered (+cancelled), `EDITABLE_STATUSES = ("planning","tendered")`.
  **Cube utilization is DERIVED, never stored**: `weight/volume_utilization_pct(planned)` = assigned-shipment total ÷
  equipment capacity, returns **None** when capacity is 0/None (no division-by-zero). The detail view aggregates BOTH
  dimensions in ONE `.aggregate(w=Sum, v=Sum)` and passes each precomputed total in so the property never re-queries
  (never call the no-arg path per row). `LoadStop`: sequence/stop_type/address(+free-text)/status.
- **`Shipments.py`** — `Shipment` [`SHP-`] + `TrackingEvent` (**append-only**, tenant-less child — no edit/delete
  views, mirrors the StockMove ledger). Links `sales_order`/`purchase_order` (nullable, outbound/inbound), optional
  `load` consolidation + `carrier`. status planned→booked→in_transit→exception/delivered (+cancelled),
  `EDITABLE_STATUSES = ("planned","booked")`. **`apply_tracking_event(event)` projects the latest event onto the
  summary fields** (`status`/`current_status_text`/`last_known_location`/`actual_pickup_at`/`actual_delivery_at`/POD)
  — a `pickup` event → in_transit + stamps pickup once; `delivered`/`pod_signed` → delivered (+POD); exception/delayed/
  customs_hold → exception; a terminal (delivered/cancelled) shipment records the event but is NEVER walked back.
  Cube inputs (`weight_kg`/`volume_cbm`/`package_count`) live here (Item has no dimensions yet, L28). `is_delayed`
  property. When a delivery closes a shipment the view calls `carrier.recompute_scorecard()`.
- **`FreightInvoices.py`** — `FreightInvoice` [`FRT-`] + `FreightInvoiceLine` (tenant-less child). The freight audit.
  `carrier` PROTECT; `load`/`shipment` nullable (form `clean()` cross-checks their carrier == the billed carrier — a
  data-integrity guard, not cross-tenant). **All amounts DERIVED from lines**: `recalc_amounts()` sums billed/contract/
  variance in **Python** (not `F()` — SQLite int-division trap). `run_audit()` sets `match_status` ∈ not_matched/
  matched/price_variance/duplicate/disputed (mirrors `GoodsReceiptNote.MATCH_STATUS_CHOICES`): within
  `match_tolerance_pct` → matched, outside → price_variance, a same-carrier + same non-blank `carrier_invoice_number`
  → duplicate, and an already-`disputed` invoice is left disputed. **The hand-off (`freightinvoice_handoff`) drafts an
  `accounting.Bill`** (status=`draft`, `party=carrier.party`, one BillLine for the freight total) and links it by
  nullable FK — **it NEVER posts a JE (L29)**; AP approves/pays the Bill in accounting. `is_editable` = pending &
  no bill.

**URLs** (`app_name="scm"`, prefixes all unique vs `orders/`/`sales-orders/`):
- **carrier** — `carrier_*` (/carriers/) + `carrier_recompute_scorecard` (POST).
- **load** — `load_*` (/loads/) + `load_tender`/`load_book` (POST, `@login_required`, require a carrier) +
  `load_dispatch`/`load_deliver`/`load_cancel` (POST, `@tenant_admin_required`).
- **shipment** — `shipment_*` (/shipments/) + `shipment_book` + `shipment_add_event` (appends a TrackingEvent,
  `recorded_by` = `request.user`) + `shipment_cancel` (all POST, `@login_required`).
- **freightinvoice** — `freightinvoice_*` (/freight-invoices/) + `freightinvoice_run_audit`/`_dispute` (POST,
  `@login_required`) + `freightinvoice_approve`/`_reject`/`_handoff` (POST, `@tenant_admin_required`).
  **approve/reject are pending-only guarded** (a crafted POST can't reject an approved or approve a rejected invoice);
  **run_audit is is_editable-guarded** (frozen once approved/handed-off).

**Templates** under `templates/scm/transportation/{carrier,load,shipment,freightinvoice}/{list,detail,form}.html`.
Carrier/load/freightinvoice forms carry an inline formset (rate cards / route stops / charge lines); shipment tracking
events are appended from the detail page's `TrackingEventForm`, not a formset. Load detail renders cube utilization as
`.progress`/`.progress-bar` bars (guarded `is not None`, "set a capacity to compute" fallback). Colour-named badges only.
**Seeder**: `_seed_tms_tenant` runs LAST (after `_seed_oms_tenant`/procurement) so shipments can link the seeded
SalesOrder/PurchaseOrder; carriers reuse `self._supplier(...)` parties; events go through the real `apply_tracking_event`
and the invoice through the real `run_audit` (derived state, not hand-set). Idempotent via a `Carrier` guard; `_flush`
deletes freight-linked draft bills → FreightInvoice → Shipment → Load → Carrier (FreightInvoice.carrier is PROTECT).

## 4.7 Demand Planning & Forecasting  (`apps/scm/*/DemandPlanning/`, templates `templates/scm/demandplanning/`)

Realizes 4.7's five bullets. The organising rule: **demand history is DERIVED, never stored.**
`models/DemandPlanning/_history.py::demand_series()` aggregates 4.5's `SalesOrderLine` (bucketed by
`sales_order__order_date`, excluding `draft`/`cancelled`) or 4.3's `StockMove` `issue` rows (negated — issues are
signed negative), returning a **dense, zero-filled** `[(period_start, qty)]`. A fourth copy of sales history would
drift from the orders it was copied from, so there is no history table — the same rule as `Item.on_hand()`.
`demand_series_map()` is the batched many-item form; `period_count()` measures a span **arithmetically** (never
`len(period_range(...))` — that builds the list the cap exists to prevent).

**Models**
- **`SeasonalityProfile`** [`SEA-`] + tenant-less child **`SeasonalityIndex`** — ONE table for a recurring seasonal
  curve, a windowed `promotion`/`event` (uplift + cannibalization) AND a `period_from_launch` lifecycle ramp; they are
  the same object at different `profile_type`s. `apply_to()` splits the effect into `(seasonal_index, event_uplift)`
  so the two land in SEPARATE waterfall columns. `seasonalityprofile_derive` fills the factors from history
  (period mean ÷ overall mean) over **whole, closed buckets** — a mid-bucket window biases the two end periods down.
- **`DemandForecast`** [`DF-`] + tenant-less child **`DemandForecastPeriod`** — item × optional location × optional
  customer over a bucketed horizon. `_forecasting.py` holds the engines (naive, seasonal_naive, moving/weighted MA,
  exponential smoothing, Holt linear, Holt-Winters, like-item, manual, `best_fit` on an out-of-sample hold-out) as
  **pure Decimal, zero ORM, no numpy/pandas**. **The decomposition IS the feature**: `historical → baseline ×
  seasonal_index + event_uplift + signal_adjustment + consensus = final`, each its own column.
  `generate_periods()` rebuilds the grid (skips `is_locked` rows; **writes no quantities for `method="manual"`**),
  `recompute_consensus()` re-resolves every accepted adjustment against the LIVE base, and
  `accuracy_metrics()` returns MAPE/WMAPE/bias/tracking-signal/**FVA** over ELAPSED periods only.
- **`DemandSignal`** [`DS-`] — short-horizon sensing log, `new → under_review → applied|dismissed|expired`. Most
  types await an external feed, but **`detect_order_surge()` works today with zero integration** (live sales-order
  run rate vs. the approved forecast, de-duped on `source_reference = "<DF number>:<period sequence>"`);
  `expire_stale_signals()` retires past-window rows on the same button.
- **`ForecastAdjustment`** [`FA-`] — consensus input by `contributor_function` with a mandatory reason code +
  rationale. `absolute`/`delta`/`percent` all reduce to ONE signed delta via `delta_against(base)`; only `accepted`
  ones roll up.
- **`ReorderRule` EXTENDED IN PLACE** (4.3's model, no second policy table) — `safety_stock_method`
  (fixed/service_level/periodic_review/avg_max/forecast_error), service level, lead time + variability, review
  period, seasonality/forecast links, plus seven `editable=False` computed columns.

**The compute-then-apply contract (do not break it):** `ReorderRule.calculate()` writes ONLY `computed_*` /
`avg_daily_demand` / `demand_std_dev` / `abc_class` / `xyz_class` / `last_calculated_at`. `apply_computed()` — reached
only from the **tenant-admin-gated** `scm:safety_stock_apply` — is the sole promoter into the live
`safety_stock`/`reorder_point` that 4.3's `reorder_alerts` and 4.1's suggested quantities buy against. For the same
reason `ReorderRuleForm` **disables those two fields for a non-admin** (`ADMIN_ONLY_FIELDS`), or the gate would be
one click away on the 4.3 edit page.

**URLs**: `forecasts/` (+ `generate/ submit-review/ approve/ archive/ revise/`), `seasonality/` (+ `derive/`),
`demand-signals/` (+ the literal `detect/` **above** the pk route, `review/ apply/ dismiss/`),
`forecast-adjustments/` (+ `accept/ reject/`), and the two reports `safety-stock/` (+ `recalculate/`,
`<pk>/apply/`) + `forecast-accuracy/`.

**Authorization**: `@tenant_admin_required` on `demandforecast_approve`, `demandforecast_archive`,
`demandforecast_revise` (it archives the original) and `safety_stock_apply`. An archived/draft forecast is closed to
signals and adjustments (`ADJUSTABLE_STATUSES`, enforced on BOTH the form queryset and in `_review`). A signal that
names an item may only be applied to THAT item's forecast. Reviewed adjustments and applied/dismissed signals cannot
be deleted — the roll-up would keep their number with no source row.

**Guards worth knowing**:
- `MAX_HORIZON_PERIODS = 520` + a year-1900 floor. Test a span with **`period_count()`** (arithmetic), never
  `len(period_range(...))` — building the range to measure it IS the runaway the cap prevents.
- **`q2`/`q4` in `models/_base.py` clamp as well as quantize.** Every writer of a quantity column uses them; an
  unclamped sibling can still `DataError` a whole `bulk_update` and fail the batch instead of the one bad row.
- **A `DemandForecastPeriod` has exactly three typed fields: `baseline_quantity`, `unit_price`, `is_locked`.**
  Everything else is a computed waterfall step and is `editable=False`, so no form and no admin inline can offer
  it. On a `manual` forecast you type `baseline_quantity`; the grid save calls `recompute_consensus()` so `final`
  updates immediately (generate and accept/reject are not the only things that must derive it).
- **A LOCKED period is excluded from BOTH roll-ups** — `recompute_consensus` and `apply_to_forecast`. Giving a
  locked row a share and then declining to move its `final_quantity` silently swallows that share.
- **Moving an APPROVED plan is admin-only, whichever door you use.** `approve`/`archive`/`revise` are
  `@tenant_admin_required`; accepting an adjustment and applying a signal touch the same numbers, so they go
  through `_guard_plan_of_record()` (gated on the TARGET's status, so draft/in-review work stays open to every
  planner). Gating the new path is not gating the column — see also `ReorderRuleForm.ADMIN_ONLY_FIELDS`.

**Seeder**: `_seed_demand_planning_tenant` runs LAST. It back-dates 24 months of closed `SalesOrder`s per item
(4.5 only seeds today's, and without history every 4.7 page would correctly compute zero), then drives the REAL code
paths — `generate_periods()`, `detect_order_surge()`, `apply_to_forecast()`, `recompute_consensus()`, `calculate()`.
The approved forecast's horizon opens **three months ago** so accuracy scores real elapsed periods and the detector
has a live period. Reorder rules are calculated but deliberately **NOT applied**, so the report has a real variance.
`_flush` deletes the 4.7 tree FIRST (`DemandForecast.item` is `PROTECT`).

---

## 4.8 Manufacturing / Production  (`apps/scm/*/Manufacturing/`, templates `templates/scm/manufacturing/`)

The **make** side. Realizes 4.8's five bullets, built on one rule: nothing it computes is also stored.

**Models** (`models/Manufacturing/`, load order WorkCenters → BillsOfMaterials → WorkOrders → ProductionTimeLogs
— the FK chain runs backwards along it):

- **`WorkCenter`** [`WC-`] (`WorkCenters.py`) — machine/assembly/manual/inspection/outsourced station.
  `capacity_hours_per_day`, `efficiency_pct`, `setup_minutes`, split `machine_cost_per_hour`/`labor_cost_per_hour`
  (both **capped** at `MAX_HOURLY_RATE`; see gotchas). Points at an existing **`scm.Location`** — there is
  deliberately **no `wip` location_type**. `org_unit`→`core.OrgUnit`, `supervisor`→`core.Party`.
  Derived, never stored: `cost_per_hour`, `effective_capacity_hours()`, `scheduled_hours()` (window **overlap**,
  not containment), the batched `scheduled_hours_map()`, `actual_hours()`, `utilization_pct(actual=…)`,
  `oee_chip()` (also returns `booked_hours` so the detail page needs ONE aggregate, not three).
- **`BillOfMaterials`** [`BOM-`] + **`BOMLine`** (`BillsOfMaterials.py`) — versioned recipe with
  `effective_from/to`, `bom_type` (manufacture/kit/phantom), `output_quantity` (components scale by
  `order_qty / output_quantity`), `lead_time_days` (**in-house production** time — *not* `ReorderRule.lead_time_days`,
  which is purchasing), `default_work_center` (the documented stand-in for a deferred routing master).
  Lines carry `quantity_per`, `scrap_pct` (→ derived `effective_quantity_per`) and `issue_method`
  (manual/backflush). `status` **IS** a form field here (master-data curation, not a stock-gating workflow) —
  unlike `WorkOrder.status`.
- **`WorkOrder`** [`WO-`] + **`WorkOrderComponent`** (`WorkOrders.py`) — seven-state run
  (draft/planned/released/in_progress/completed/closed/cancelled), `order_policy` MTS/MTO with a `sales_order` peg,
  `component_location`/`output_location` (both **PROTECT**), `output_lot_serial`.
- **`ProductionTimeLog`** [`PRD-`] (`ProductionTimeLogs.py`) — setup/labour/machine/**downtime** in ONE table
  (splitting downtime out would fork every utilization query). `duration_minutes` derived in `save()`.

**Routes** (`urls/Manufacturing/`): `work-centers/`, `boms/`, `work-orders/`, `time-logs/` (five CRUD names each),
plus report pages `mrp/` → `scm:mrp_report` and `production-schedule/` → `scm:production_schedule`.
Work-order verbs, all under `<int:pk>/`: `plan/ release/ schedule/ issue/ report/ close/ cancel/`.

**The two postings** (`views/Manufacturing/WorkOrders.py`) — `@tenant_admin_required @require_POST`, inside
`transaction.atomic()` behind `select_for_update()` with the status **re-read inside the transaction**
(a double-click otherwise posts twice). Both route through 4.3's `_post_stock_move` and `_shared_items`.

**Seeder**: `_seed_manufacturing_tenant` runs LAST (it consumes 4.3's on-hand). Creates 2 work centres, a `WS-KIT`
finished good with an active default BOM over the existing items, and `WO-00001` driven through the real
`_issue_components` + backflush + posting path — the demo state is what the app would have written.

### Non-negotiables for 4.8 (each one is a bug that was found and fixed — the tests lock them)

1. **Component draws post `move_type="consumption"`, output posts `"production"` — NEVER `issue`/`receipt`.**
   4.7's `demand_series(source="stock_issues")` reads `move_type="issue"` as **customer** demand, so booking a
   raw-material draw as an issue silently inflates every forecast built on that source. `_item_valuation`'s
   `!= "transfer"` layer walk includes both new types correctly.
2. **Make-vs-buy is DERIVED, not a flag.** An item is manufactured iff an active effective BOM exists —
   `BillOfMaterials.manufactured_item_ids()` / `explosion_index()` answer it for a whole tenant in one query.
   There is **no `Item.is_manufactured`** column, so nothing can drift or need a data migration.
3. **`computed_unit_cost` divides the UNABSORBED pool by THIS layer's good quantity.** Dividing the whole pool by
   the cumulative quantity re-charges cost an earlier layer already carried — on a 3-then-2 split of a run costing
   C that posts `C` then `0.4C`, banking **140%** of real cost and driving `wip_value` negative. The ledger is
   append-only: an over-valued layer can never be corrected in place.
4. **Components are a SNAPSHOT.** `explode_components()` writes `WorkOrderComponent` rows once and is a no-op if
   any exist, so a re-explode never overwrites a hand-edited set and a later BOM edit cannot rewrite history.
5. **`explode()` is bounded on THREE axes** — a branch-scoped visited set (cycles), `MAX_EXPLODE_DEPTH`, and
   `MAX_EXPLODE_ROWS` (the output is the *product* of branch factors; five chained 50-line recipes are 6.25M rows,
   an authenticated OOM). A would-be-cyclic component is emitted as a **leaf**, never dropped.
6. **Single writers.** `quantity_produced`/`quantity_scrapped`/`produced_unit_cost`/`status`/`released_by` belong to
   the posting and lifecycle actions; `WorkOrderComponent.quantity_issued` to the issue action;
   `ProductionTimeLog.duration_minutes` to `save()`. All `editable=False`, absent from `Meta.fields`, and in the
   admin's `readonly_fields`. `ProductionTimeLog.quantity_completed` is **advisory** and does NOT roll up.
   `produced_unit_cost` holds the **last reported layer's** cost, not a run average — the page labels it so.
7. **No WIP location, no WIP column, no journal entry.** `wip_value` is computed on the detail page. A `wip`
   `location_type` would migrate a model 4.3/4.4/4.5 share, and `is_pickable=True` would leak WIP into 4.5's
   available-to-promise. SCM posts no JE (L29).
8. **MRP suggests, never acts** — it nets **net** (not gross) parent demand, excludes `fulfilled`/`invoiced`
   orders, filters the horizon on `requested_date` (NULL included), and openly excludes open POs because 4.1's
   `PurchaseOrderLine` has no `item` FK. A human converts each row.
9. **Batched, not per-row.** `explosion_index()` (2 queries) is shared across an MRP run; `scheduled_hours_map()`
   does the load board in one; `workcenter_list` uses `Exists()` not `Count()` (two Counts over two reverse
   relations LEFT JOIN into a cartesian product). Query budgets are asserted in `test_views.py`, including
   **scale-invariance** locks on `mrp_report` and `production_schedule`.
10. **New PROTECT FKs need delete guards.** 4.8 added three onto `Item` (extended `item_delete`) and two onto
    `Location` — `location_delete` now catches `ProtectedError` inside `atomic()` rather than enumerating guards
    that go stale. `workcenter_delete` guards its own two. Forgetting this is a 500, not a message (cf. `405ee0ea`).

---

## 4.9 Quality Management System (QMS)  (`apps/scm/*/QualityManagement/`, templates `templates/scm/quality/`)

The **conformance** layer over everything 4.1/4.6/4.8 already move. **SCM owns these tables** — Module 12 (unbuilt,
20 sub-modules) will EXTEND them by FK rather than re-declare them, the same L36 call procurement made in 4.1.

**Models** (`models/QualityManagement/`, load order InspectionPlans → QualityInspections → QualityAudits →
NonConformances → CapaActions; an audit *finding* is an NCR, and a CAPA hangs off an NCR, so the chain runs that way):

- **`InspectionPlan`** + **`InspectionCharacteristic`** (`InspectionPlans.py`) — the reusable spec. Keyed to a
  trigger (`incoming_receipt / in_process / outgoing_shipment / periodic_stock / audit_checklist`) and scoped by
  item, category or supplier; `all_100 / percentage / fixed_count / aql` sampling; versioned with
  `effective_from`. **No `NUMBER_PREFIX`** — `("tenant", "code", "version")` is the key, which keeps a prefix free.
  Characteristics carry `target_value` + `lower_limit`/`upper_limit`, `uom`, `test_method`, `is_critical`,
  `is_mandatory` and **`include_on_coa`** — the one boolean that makes a certificate generatable.
  `for_trigger()` resolves item → category → supplier → unscoped in ONE query.
- **`QualityInspection`** [`QC-`] + **`InspectionResult`** (`QualityInspections.py`) — hangs off whichever of
  4.1's `GoodsReceiptNote`, 4.8's `WorkOrder` or 4.6's `Shipment` triggered it (all nullable). `status`
  (`draft/in_progress/passed/failed/on_hold/cancelled`) is **separate from** `usage_decision`
  (`pending/accept/accept_with_deviation/reject`) — an out-of-spec lot can still be accepted with deviation, and
  that decision is what an auditor cares about. Carries the CoA stamp trio (`coa_number`, `coa_issued_on`,
  `coa_issued_to`).
- **`QualityAudit`** [`QA-`] (`QualityAudits.py`) — `internal/supplier/customer/certification`, reusing an
  `InspectionPlan` as its checklist. Findings are `NonConformance(source="audit")` rows via `related_name="findings"`.
- **`NonConformance`** [`NCR-`] (`NonConformances.py`) — one register for every source, with the full MRB
  disposition set (`use_as_is/rework/repair/scrap/return_to_vendor/regrade`), containment, `cost_of_quality`,
  owner/due tracking.
- **`CapaAction`** [`CAPA-`] + **`CapaTask`** (`CapaActions.py`) — corrective and preventive as one attribute
  (ISO 9001 §10.2), standalone or linked to an NCR or audit finding, named RCA method, effectiveness verification.

**Routes** (`urls/QualityManagement/`): `inspection-plans/`, `inspections/`, `nonconformances/`, `capa/`,
`quality-audits/` (five CRUD names each) plus `coa/` → `scm:coa_report`, `scm:coa_issue`, `scm:coa_print`.
Verb routes all sit under `<int:pk>/`. **`@tenant_admin_required`** (so their buttons need the role check too):
`qualityinspection_decide`, `qualityinspection_quarantine`, `qualityinspection_release_lot`,
`nonconformance_quarantine`, `nonconformance_release_lot`, `nonconformance_disposition`, `capaaction_verify`,
`coa_issue`. Everything else is `@login_required`; every action and delete is `@require_POST`.

**Seeder**: `_seed_quality_tenant` runs LAST, guarded on **`InspectionPlan`** (the first thing it writes — guarding
on the inspection left an aborted run to `IntegrityError` on the plans' unique key). It flips two 4.3 items to
`tracking="lot"` and opens two lots, because without lot-tracked stock a certificate has no batch, quarantine has
nothing to flip and the scrap has nothing to draw against.

### Non-negotiables for 4.9

1. **A quality scrap posts `move_type="adjustment"`** with `reference="NCR-…"`. There is deliberately **no new
   move type** — 4.8 earned `consumption`/`production` because 4.7 reads `issue` as *customer demand*, and that
   justification does not transfer to a write-off.
2. **Quarantine flips `LotSerial.status` and posts NOTHING.** A hold is not a movement. Release is only reachable
   from a lot that was quarantined, so restoring `available` is correct rather than a guess.
3. **GRN-rejected units never entered stock**, so their NCR posts nothing — expressed as the executable
   `posts_stock` property, which also requires an `item` (an audit finding legitimately has none, and the scrap
   path would otherwise hand `None` to `_insufficient_stock`).
4. **Results are SNAPSHOTTED** from the plan's characteristics, so editing a plan cannot rewrite a certificate
   already issued. `_evaluate()` is the sole writer of `result`.
5. **A certificate is refused, not just discouraged.** `coa_blockers()` enumerates every reason; `coa_issue`
   refuses when any is present, and once issued the usage decision is frozen — otherwise reversing to `reject`
   would leave a live certificate that `coa_blockers()` says should never have existed.
6. **`coa_number` is allocated LATE**, out of id order. `apps/core/utils.next_number` therefore orders by the
   number **field**, not by `-id` — the `-id` form re-minted certificate numbers already in use, and MySQL cannot
   carry a partial unique index on a mostly-blank column to catch it. The issue site re-checks the issued set too.
7. **An audit cannot close over an open finding**, and stays editable while `in_progress` so its conclusion can
   actually be written (locking at `start` made its own happy path unreachable).
8. **Never name an annotation after a model `@property`.** Django cannot set it when instantiating rows and the
   whole list page 500s with `AttributeError: can't set attribute` — hence `characteristic_count_agg`,
   `major_count_agg`, `minor_count_agg`. Two of the five list views shipped broken on exactly this.
9. **`formset.instance = form.instance` before `formset.is_valid()`** on every formset whose `clean()` reads a
   parent field — on create the parent is an empty instance and the guard silently no-ops (a live 4.8 bug).
10. **New PROTECT FKs need delete guards — use the GENERIC shape.** `Item`, `Location` and `LotSerial` all now
    catch `ProtectedError` inside `atomic()` and name the blocking relations. The `.exists()` enumeration
    `item_delete` used to carry had grown a guard per sub-module and still missed six FKs; an item on a *draft*
    adjustment line has no stock moves, so it cleared every guard and 500'd. Enumeration goes stale with every
    sub-module that adds an FK — don't start a new one.
11. **The result snapshot is immutable in SHAPE, not just in content.** `InspectionResultFormSet` is
    `can_delete=False` with an injection guard in `clean()`. `extra=0` does **not** prevent injection —
    `initial_form_count()` on a bound formset comes from the POSTed management form. Deletion is permanent
    (`generate_results()` short-circuits on `results.exists()`), so removing the one failing characteristic
    silently turns a failed inspection into a certifiable one.
12. **A gate lives in TWO places.** Guarding the view and forgetting the button is the recurring failure mode in
    this module — it shipped four times across 4.8/4.9 (audit Delete, Raise-CAPA, the usage-decision panel, a
    filter wired with no control). Every action button must be gated on the same condition its view enforces,
    *and* the SQL of a state filter must agree with the per-row verdict the page then renders (`?coa_state=ready`
    listed rows the page badged "Blocked" because it encoded four of seven rules).
13. **Prefetch + `_result_rows()` together.** Chaining `.select_related()` off a related manager CLEARS a
    prefetch and re-queries, so a `Prefetch` alone provably changes nothing — `_result_rows()` is prefetch-aware
    and `generate_results()` invalidates both caches. `coa_report` is asserted scale-invariant in the tests.

---

## 4.10 Returns Management (Reverse Logistics)  (`apps/scm/*/ReturnsManagement/`, templates `templates/scm/returns/`)

The **backwards** flow. **SCM owns these tables** — the unbuilt `5.10 Returns Management (RMA)` and
`9.5 OMS → Returns & Exchanges` extend them by FK rather than build a second RMA (L36, declared in the
`ReturnAuthorization` and `ReturnDisposition` docstrings; the `scm_return_*` / `scm_warranty_*` reverse-accessor
namespace is reserved so a later module cannot collide).

**Models** (`models/ReturnsManagement/`):

- **`ReturnReason`** — master, **no prefix** (`("tenant","code")` is the key). A reason is **policy, not a
  label**: `fault_party` (customer/merchant/carrier/supplier/unknown) decides who pays return freight;
  `blocks_restock` decides whether the unit may re-enter sellable stock; four `allows_*` booleans rather than an
  M2M so the offer set stays filterable and migration-free. Also `requires_photo`, `raises_nonconformance`,
  `suggested_disposition` (pre-selects only).
- **`ReturnPolicy`** — master, **no prefix**. The published promise: `window_basis`
  (delivery/fulfilment/order_date) + `window_days` + `fallback_days`, `refund_basis`, `restocking_fee_type`,
  `return_shipping_paid_by`, `auto_approve` (**pre-fills the approve form only, never auto-acts**). It earns its
  table on two things nothing else can hold: **`grade_a..d_cost_pct`** (defaults 100/75/40/0 — without them
  `condition_grade` is decorative) and **`return_to_address`**, because `scm.Location` has NO address field and
  the return slip must print one.
- **`ReturnAuthorization`** [`RMA-`] + **`ReturnLine`** — a deliberately **NON-POSTING** document: it authorises
  and owns neither stock nor money. A portal submission is this record at `status="requested"` — a status is not
  a document, so there is no separate intake table. `policy_snapshot` freezes the eligibility verdict **at
  approval** (the 4.9 `InspectionResult` precedent). `public_token` is minted once in `save()` with
  `secrets.token_urlsafe(32)`. Lines hold `unit_price` (what they paid) **separately from** `unit_cost` (what it
  cost us), plus a `tax_pct` snapshot.
- **`ReturnDisposition`** — **no prefix** (the `SalesOrderAllocation` precedent). One row per
  *(line, decision, quantity)*. Receiving and deciding are **two separately stamped acts on the same row**.
  `condition_grade` is the INPUT, `disposition` the OUTPUT — never collapsed. `stock_posted` is the idempotency
  latch; `posts_stock` is an executable property.
- **`WarrantyClaim`** [`WTY-`] + **`WarrantyClaimCost`** — supplier recovery, with typed cost children
  (part/labour/freight/external_service/admin) because the normal real outcome is a **partial** approval that
  accepts the part and refuses the labour, which a flat `claim_value` cannot express.

**Routes** (`urls/ReturnsManagement/`): `returns/`, `return-reasons/`, `return-policies/`,
`return-dispositions/` (deliberately not the generic `dispositions/`, which Module 5 will want),
`warranty-claims/`, plus `refund-queue/`, `returns-bench/`, `return-portal/` and **`return-tracking/<str:token>/`**
— the two public pages sit on their own first segment rather than under `returns/`, which removes the
greedy-converter ordering hazard entirely.

**`@tenant_admin_required`** (ten, so their buttons need the role check too): `returnauthorization_approve`,
`_reject`, `_draft_credit_note`, `_draft_replacement`; `returndisposition_decide`, `_post`, `_split`;
`warrantyclaim_submit`, `_record_response`, `_record_credit`. The two public views have **no decorator at all**.

**Seeder**: `_seed_returns_tenant` runs LAST. Four RMAs by design — one settled with a real restock plus an
off-ledger scrap, one **credit-only** (it never gets a disposition row and would otherwise be silently dropped
by every received-keyed queue), one on the bench, and one at `awaiting_receipt` **because `LABEL_STATUSES`
excludes every other seeded state** and the return slip would otherwise 404 for all demo data.

### Non-negotiables for 4.10

1. **`ReturnDisposition` is the ONLY ledger writer.** Everything else in 4.10 posts nothing, ever.
2. **Intake posts NOTHING.** Keeping the returns bench off-ledger IS the blocked-stock stand-in: `Location` has
   no blocked type and `Item.on_hand()` sums every location, so an intake row would inflate on-hand, valuation
   and 4.7's reorder inputs tenant-wide and indistinguishably from sellable stock. The honest cost (bench goods
   absent from inventory value) is surfaced by `scm:returns_awaiting_disposition`, not papered over.
3. **A restock is a POSITIVE `receipt` at `restock_unit_cost`, never a transfer pair.** `_post_transfer` passes
   `item.average_cost` *specifically* so a transfer is value-neutral, and `_item_valuation` excludes
   `"transfer"` from the FIFO/LIFO walk — so a transfer could never carry a grade write-down. No new move_type:
   checked against all five `move_type` consumers.
4. **`unit_price` must never reach a StockMove.** It is the SALE price; restocking at it would roll
   `average_cost` toward the selling price via `apply_receipt()`. Hence the separate `unit_cost` snapshot and
   `restock_unit_cost`.
5. **FIFO/LIFO divergence is EXPECTED after a written-down restock.** `_item_valuation` walks layers and ignores
   `average_cost`, while `Item.total_value()` multiplies `on_hand × average_cost`. Pre-existing dual-figure
   design; 4.10 is the first module to make it diverge routinely. Documented and test-pinned — do not "fix" it.
6. **The credit note drafts and STOPS.** `accounting.Invoice(kind="credit_note", status="draft")`, mirroring the
   4.6 freight hand-off. SCM posts no JournalEntry (L29) and creates no `accounting.Payment` — an outbound
   payment posts against the AP liability account, which is wrong for a customer refund. **Refuse to draft when
   `credit_total <= 0`**: `invoice_post` requires a positive total, so a credit whose fees meet its value would
   be permanently unpostable.
7. **The credited quantity comes from the DISPOSITION rows**, never from `quantity_approved` — and
   `quantity_received` includes `received_pending`, or anything on the bench silently disappears from the queues.
8. **A `credit_only` RMA never gets a disposition row.** Every received-keyed queue must branch on
   `return_type` or it drops perfectly valid work as abandoned.
9. **`accounting.Currency` is GLOBAL** — no tenant FK, no `is_base`. There is no "tenant default currency" to
   fall back to; a portal return inherits from the customer's order history, and a null currency is a **loud
   refusal at settlement**, not a guess on a money document.
10. **The public token surface** resolves its tenant **off the object**, never `request.tenant` (None for an
    anonymous visitor), refuses an inactive tenant, puts the state guard in the queryset so a draft/cancelled
    RMA 404s rather than leaks, writes through a **conditional UPDATE** (TOCTOU-safe), and leaks no price, cost
    or supplier data. The token never expires and cannot be revoked — a stated residual risk; no token in this
    repo can.
11. **No `customer_return` on `NonConformance.SOURCE_CHOICES`.** `source` is `max_length=14` and the value is 15
    characters, so it is a column widen against a 4.9 model plus a reversal of 4.9's documented reasoning. 4.10
    links via `ReturnDisposition.nonconformance` instead.

## 4.11 Supply Chain Analytics  (`apps/scm/*/SupplyChainAnalytics/` + `apps/scm/analytics.py`, templates `templates/scm/analytics/`)

**The measuring layer. 4.11 is READ-ONLY over 4.1–4.10: it posts no `StockMove` and no `JournalEntry`.**
A survey of thirteen control-tower / spend-analytics products (SAP IBP, Blue Yonder, Kinaxis, o9, Oracle SCM
Analytics, Sievo, Coupa, GEP, project44, FourKites, Netstock, Anaplan, Resilinc) found the same shape in every
one: an analytics module is overwhelmingly **computed pages**, and the only things worth storing are metric
targets, point-in-time snapshots and alert instances carrying human state. So **all five NavERP bullets are
computed pages** and the three models are cross-cutting machinery, not one table per bullet.

### `apps/scm/analytics.py` — the compute layer (flat at the app root, CLAUDE.md backend rule 8)

**Every 4.11 number comes through `compute_metric()`.** No view, template or export does arithmetic. That is what
makes it impossible for a tile to read green while the alert behind it fires red, or for a CSV to disagree with
the page it was exported from.

- `SCM_METRICS` — 36 resolvers, built by attaching one to every key in `METRIC_META`, with a module-level
  assertion that none is missing so the catalog and the compute layer cannot drift.
- `compute_metric(tenant, metric, start, end, scope=None, target=None)` — the single entry point. Result contract:
  `{"value": Decimal|None, "display": str, "breakdown": {...}, "rows": [...]}`, everything inside `breakdown`/`rows`
  JSON-serializable because `KpiSnapshot.breakdown` stores it verbatim.
- `band_for(target, value)` → `ok|warning|critical|unknown`, honouring each metric's `direction`. **Both**
  `KpiSnapshot.status_band` and the alert detector call this one function.
- `range_bounds` / `period_windows` / `period_count` — `period_count` is computed **arithmetically** (L40: a guard
  written as `len(build_the_whole_thing())` *is* the payload).
- `capture_snapshots(tenant, targets, period_end, user)` and `detect_alerts(tenant, user)` — the two services. The
  seeder and the POST actions both call these, so nothing hand-sets a plausible-looking number.
- `supplier_delivery_stats` / `supplier_quality_stats` — deliberately **duplicate** the arithmetic of 4.2's
  `SupplierScorecard.recompute_from_signals` rather than refactoring a shipped, tested sub-module (L38). A parity
  test in `test_analytics.py` is what keeps the two honest.

**A not-computed figure returns `None` with a stated reason (`_unavailable`), never `0`.** Zero is a fact ("no
dead stock"); absence is not one ("no stock to measure"), and rendering them the same way is how a page reports
good news it never computed.

### Models (`models/SupplyChainAnalytics/`) — and why each is STORED rather than derived

- **`_choices.py`** — the closed metric catalog (`METRIC_META`, 36 entries × group/unit/direction/scopes/
  parameters) plus every shared vocabulary. **This file exists to break an import cycle**: `analytics.py` imports
  models to aggregate over 4.1–4.10, so `KpiTarget.metric` cannot take its `choices` from `analytics`. Same split
  `apps/crm` already proved (`models/AnalyticsReporting/_choices.py` vs `crm/analytics.py`). Edge runs one way:
  `analytics → models → _choices`.
- **`KpiTarget`** [`KPI-`] — target + warning/critical bands + the knobs a metric declares (`parameter_days`,
  `parameter_pct`), `is_alerting`, `min_impact_value`, `owner`, `is_pinned`. **Stored because a target is human
  intent** — nothing in 4.1–4.10 records "we want six turns". Scope is **four typed nullable FKs**
  (`scope_category`/`scope_location`/`scope_carrier`/`scope_vendor`), never a generic `scope_ref` int: a bare int
  carries neither tenant nor type (L40). `clean()` is registry-driven off `METRIC_META`, not a per-metric
  if-chain, and rejects the empty conjunction `is_alerting` with no thresholds.
- **`KpiSnapshot`** — the frozen fact row, with the component arithmetic in a `breakdown` JSON. **Stored for three
  independent reasons**: history *drifts* (`Item.average_cost` is recomputed on every receipt and back-dated
  `StockMove`/GRN rows are legal, so re-deriving last quarter silently rewrites the past); a twelve-point trend
  would otherwise be twelve full FIFO ledger walks per page load; and every surveyed product ships it.
  `unique_together (tenant, kpi_target, period_start, dimension_key)` makes a re-run idempotent, and `computed_at`
  is `default=timezone.now` **not** `auto_now_add` precisely so the re-run re-stamps it.
- **`SupplyChainAlert`** [`ALR-`] — twelve exception types, ranked by `impact_value` rather than by count, with
  acknowledge/assign/snooze/resolve/dismiss as no-op-safe model methods each returning its own audit diff.
  **Stored because acknowledgement is human state no aggregate reproduces** — a purely computed exception list
  forgets that somebody already looked.

### Non-negotiables for 4.11 (each is a defect that was found and fixed — the tests lock them)

1. **De-dupe is enforced in `detect_alerts` under `transaction.atomic()` + `select_for_update()`, NOT by a DB
   constraint.** A `unique_together` including `status` would let a *resolved* row block the next genuine breach,
   and a `UniqueConstraint(condition=...)` is **silently dropped by Django on MariaDB**, which has no partial
   indexes — so it would protect nothing here. The lock is load-bearing: `atomic()` bounds the write but grants no
   mutual exclusion, and without it two concurrent runs both read an empty open set and both create.
2. **`_impact_of` returns `None`, not `ZERO`, when a metric has no money behind it.** Most of the catalog emits no
   `IMPACT_KEYS` figure, so collapsing "unmeasurable" into "zero" made `impact < min_impact_value` true forever —
   any operator setting a floor on `otd_pct` silently stopped receiving its alerts. **An unmeasurable impact fails
   OPEN.**
3. **One resolver, one row shape.** `_r_supplier_disruption_score` used to emit `components` as `dict[str, dict]`
   normally and `dict[str, str]` on the nothing-scored path; the view called `.get()` on each value, so a tenant
   with no history got a 500 on the **first-run path**. Its league rows also carry **uniform keys** — a missing key
   never reaches a template's `|default:"0"` (Django substitutes `string_if_invalid` and *drops* the filters), so
   ragged rows render blank.
4. **Report templates must read the resolver's real row keys.** Eight tables shipped naming keys that did not
   exist; every cell rendered an em-dash behind a 200 with no error. `temp/smoke_411.py` has a row-key contract
   check for exactly this.
5. **Int FK filters guard with `.isdecimal()`, never `.isdigit()`.** `'²'.isdigit()` is `True` but `int('²')`
   raises, and it 500'd six pages. `apps/core/crud.as_db_int()` is the shared guard — it also refuses over-range
   values (`?vendor=999999999999999999999` converts fine then dies in the driver).
6. **Deleting a `KpiTarget` is `@tenant_admin_required`** — it cascades `KpiSnapshot`, and *writing* that history
   is admin-gated, so leaving the destructive path open inverted the gate. `kpitarget_edit` stays open to members
   deliberately: tuning a threshold is the target owner's daily work.
7. **Honest framing, enforced by a test.** `disruption_risk` renders a methodology card stating the scores are
   deterministic weighted composites over real rows, and **the page never says "AI"** (the sidebar legitimately
   does for Module 10's own bullets, so the assertion is scoped to the content region). Genuine ML is 10.13.
8. **`margin_analytics` prints the L29 disclaimer on the page**, not in a comment: SCM posts no `JournalEntry`,
   `apps.accounting` owns the ledger, this is an operational estimate and explicitly not the statutory P&L.
9. **CSV cells go through `_csv_safe`** — a value starting `= + - @` executes as a formula when the export is
   opened, and SKUs/supplier names are user-controlled. Numbers are left alone so `-3.5` stays numeric.
10. **Chart payloads use `json_script`, never `|safe`** — series labels are SKUs and supplier names.

### URLs / routes  (`urls/SupplyChainAnalytics/`)

`kpi-targets/` · `kpi-snapshots/` · `alerts/` · `inventory-analytics/` · `spend-analytics/` · `logistics-kpis/` ·
`margin-analytics/` · `disruption-risk/`. Two near-misses, both checked and both free — **`alerts/` vs 4.3's
`reorder-alerts/`** and **`disruption-risk/` vs 4.2's `risk-assessments/`**: Django matches whole path components
and never splits at a hyphen. *Do not "tidy" either one to match the other.* CSV exports are literal `export/`
sub-routes, so they add no new first segment. 4.11 introduces no greedy converter.

Names: `kpitarget_list/_create/_detail/_edit/_delete/_snapshot` · `kpisnapshot_list/_detail/_delete/_capture/
_export` · `supplychainalert_list/_create/_detail/_edit/_delete/_acknowledge/_assign/_snooze/_resolve/_dismiss/
_detect` · `inventory_analytics`/`spend_analytics`/`logistics_kpis`/`margin_analytics`/`disruption_risk` (+`_export`).

### Templates  (`templates/scm/analytics/`)

Entity folders `kpitarget/{list,detail,form}`, `kpisnapshot/{list,detail}`, `supplychainalert/{list,detail,form}`;
the five report pages sit at the **sub-module root** as standalone pages (the `safety_stock_report.html`
precedent). **`kpisnapshot` has no `form.html` on purpose** and both its templates say so on the page.

### Seeder

`_seed_analytics_tenant(tenant)` runs **last** in `handle()` — it measures every sub-module above it. It types the
ten KPI targets (intent), then produces every number by calling the **real** `capture_snapshots` / `detect_alerts`,
so the demo is reproducible by pressing the button on the page. Three alerts are moved through
acknowledge/assign/resolve via the model methods. It **refuses rather than half-seeds** when there is no stock
ledger or purchase history. Periods come from `analytics.period_windows("month", 3)` — 30-day deltas are not month
arithmetic and collapsed three periods into two.

### Query budget (measured)

Report pages **28–36 queries each and scale-invariant** (verified by multiplying alerts/snapshots 10× and
re-measuring — identical). List pages 9–12. `capture_snapshots` is ~8.5 queries/target and linear **by nature**
(each target names a different metric over different tables); bounded by `MAX_SNAPSHOT_TARGETS = 200` and by being
an explicit tenant-admin POST. Deliberately **not** memoised on `(metric, scope, period)`: `compute_metric` reads
the target's own parameters and bands, so two targets sharing a metric can legitimately differ.

## 4.12 Contract & Compliance Management  (`apps/scm/*/ContractCompliance/`, templates `templates/scm/compliance/`)

**Built by SUBTRACTION as much as addition.** 4.2's `SupplierContract` already WAS the contract repository
(party, NDAs/SLAs/master agreements, dates, value, terms, renewal window, a `core.Document` FK), 4.9 already
owned audit -> finding -> CAPA, and Module 13 owns folders/versioning/retention. So the **Contract Repository
bullet points at the EXISTING `scm:contract_list`** - the same call 4.4 made pointing its Bin/Location bullet
at 4.3's `scm:location_list` - and 4.12 builds only what had no home.

**The 4.2 extension (additive, nullable, behaviour-neutral).** `SupplierContract` gains exactly three things:
`parent_contract` (self-FK, **SET_NULL** - an amendment is a separately-signed instrument, so deleting the
master must orphan it, never destroy it), `owner`, and a `logistics` entry in `TYPE_CHOICES`. `clean()` refuses
a self-parent, a cross-tenant parent and a **cycle** (10-hop cap + a seen-set) - the detail page walks that
chain to render ancestry, and a cycle there is a hung worker, not a caught error. It also gained `STATUS_CSS` +
`status_css`, which replaced three hand-written colour ladders.

**Models** (`models/ContractCompliance/`; choices + the emission-factor table live in `_choices.py`):

* **`ComplianceRequirement`** [`CR-`] + child **`ComplianceCheck`** (`ComplianceRequirements.py`) - the
  standing-obligation register (Intelex shape: source, framework, jurisdiction, applicability, owner,
  recurrence, next due, workflow status). **A CLM contract obligation is `source="contract"` with an FK to
  4.2's contract, not a second obligation table** - the same call 4.9 made when an audit finding became a
  `NonConformance`. Scope is **five TYPED nullable FKs** (`org_unit`/`party`/`location`/`item`, or none for
  tenant-wide), never one untyped int: a bare id carries neither a tenant nor a type. `record_check()` is the
  only writer of `compliant`/`non_compliant` and of `last_checked_on`, and advances `next_due_date` by
  `frequency` **anchored on the check's `due_date`**, so a late proof does not drag the schedule forward.
  `compliance_rate` returns **`None`, not 0**, with no checks. `ComplianceCheck` is **tenant-less** - reached
  only via `requirement__tenant` - has no list/detail page (it is a timeline on the parent), and stamps
  `performed_by` from `request.user`.
* **`TradeDocument`** [`TD-`] + child **`TradeDocumentLine`** (`TradeDocuments.py`) - import/export paperwork
  FK'd to **4.6's `Shipment`**, never a second consignment. Lines **snapshot `hs_code`/`country_of_origin` at
  issue**: a filed declaration records what was declared, not whatever the master says later. `license` is
  **`PROTECT`**. `CHARGING_STATUSES = ("issued", "submitted", "accepted")`.
* **`TradeLicense`** [`LIC-`] (`TradeLicenses.py`) - the category's signature feature, **real-time
  decrementing**: issuing a document charges `used_value`/`used_quantity`, voiding refunds them.
  `recompute_usage()` runs **TWO single-grain aggregates on purpose** - summing `declared_value` and
  `lines__quantity` together would fan the document row out per line and charge a two-line invoice twice its
  face value. `status` is `editable=False` (draft -> applied -> active -> revoked).
* **`SustainabilityAssessment`** [`ESG-`] (`SustainabilityAssessments.py`) - EcoVadis four-theme scorecard on
  `core.Party` with a **derived** `overall_score`/`rating` (`editable=False`, so the headline cannot disagree
  with its components), Assent-style declaration flags, and supplier-declared Scope 1/2/3.

**The computed report - `scm:carbon_footprint_report` (+ `_export`), NO table.** GLEC v3.2 / ISO 14083 tonne-km
= `(weight_kg / 1000) x Load.distance_km x EMISSION_FACTORS[mode]`; 4.6 stored `distance_km`/`weight_kg`
expressly for this. The factor table lives **once**, in `_choices.py`, and is a **CLOSED set**: a shipment with
no load, no distance, no weight, or a mode with no factor is **counted as EXCLUDED and reported**, never scored
as zero - a green zero meaning "we had no data" is the 4.11 `projected_stockout_count` defect, and worse here
because it looks like an environmental result. Totals are `None`, not 0, when nothing is measurable. The page
renders its own arithmetic, its factor provenance and its limitations, and never says "AI"; statutory CSRD
disclosure is `apps/accounting`'s (L29). The date window is applied in **SQL**, not just in the Python loop.

**Routes** - `compliance-requirements/` (+ `<pk>/checks/add/`), `compliance-checks/<pk>/edit|delete/`,
`trade-licenses/` (+ `submit`/`approve`/`revoke`/`recompute`), `trade-documents/` (+ `issue`/`submit`/
`accept`/`void`/`print`), `sustainability-assessments/`, `carbon-footprint/` (+ `export/`). Verbs are POST-only
(405 on GET) and take the lock-apply-audit shape; an empty diff is `messages.info` and **no audit row**.
`tradelicense_delete` catches `ProtectedError` because of the PROTECT FK above.

**Security posture worth keeping** (each was a real finding; each is now regression-locked in the suite):

* `get_object_or_404` runs **before** any guard that can return - a reasonless `revoke`/`void` POST to a
  foreign pk must 404, not 302. An invariant with a precondition is not one.
* `ComplianceRequirementForm.status` choices are narrowed to `applicable`/`in_progress`/`not_applicable`/
  `retired` (+ the stored value). Narrowing `.choices` is **enforcement** - `ChoiceField.validate` refuses a
  crafted POST - and without it any member could mark an overdue obligation compliant with zero evidence.
* `TradeLicenseForm(may_edit_controls=False)` **pops** `authorized_value`/`authorized_quantity`/`expiry_date`
  once a licence is in force (popped => absent from `cleaned_data`, so a crafted POST cannot set them either).
  Approving is admin-gated, so widening the ceiling must be too.
* The CSV export routes **every** cell through 4.11's `_csv_safe` - carrier labels are `Party.name`, free text.
* `?date_to=0001-01-01` is clamped (the `-365 days` default would `OverflowError`) and `?carrier=` goes through
  `as_db_int`, not `isdecimal()`.

**Seeder** - `_seed_compliance_tenant()`: 2 licences (one active at ~5% drawn, one 21 days from expiry against
a 60-day notice window so it lands on *Expiring Soon*), 2 trade documents + 4 HS-coded lines, 6 requirements
across every `source` and 5 scopes (one overdue, one due-soon, one not-applicable-with-reason), 3 checks, 2 ESG
assessments, plus `owner` back-filled and one amendment on 4.2's contracts. **Statuses are never typed** -
licences walk the real ladder and requirements move only through `record_check()`. Its deletes go at the TOP of
`_flush()`, licences LAST (the PROTECT FK). Carbon coverage seeds at 50% on purpose: `SHP-00002` has a weight
but no load, a genuine gap the page is supposed to report.

**Deliberately out of scope** (recorded in the model docstrings): the `scm.Item` trade-classification columns
(`hs_code`/`country_of_origin`/hazmat) - the line already snapshots them, and a master would be a second source
of truth whose first "helpful" default would silently rewrite a filed declaration; denied-party/sanctions
screening; licence and document determination; AES/EDI/TRACES filing; per-form PDF layouts; clause library;
supplier e-sign; AI extraction; a frozen carbon ledger; multi-tier mapping; SDS/GHS library. Parked to named
siblings: landed cost -> 4.18, compliance dashboards -> 4.11, ESG *risk* -> 4.2, audits/CAPA -> 4.9, EDI ->
4.19, GDPR engine -> Module 13, statutory CSRD -> `apps/accounting`.

## 4.13 Asset Management  (`apps/scm/*/AssetManagement/`, templates `templates/scm/assets/`)

The **maintenance** side of the plant. **`scm.Asset` IS the operational asset spine** (L29/L36) — grep confirmed
no `Asset` row existed anywhere in the project, so Module 11 (Asset Management System, unbuilt) EXTENDS this table
by string FK (11.2 tracking, 11.7 condition monitoring, 11.19 fleet) rather than standing up a second one. The
organising rule, restated from 4.3 and 4.8: **nothing 4.13 computes is also stored.**

**Two additive changes to shipped 4.3 models, both all-default and behaviour-neutral** (the 4.4-added-bin-columns
precedent): `Item.is_spare_part` — a one-column MRO marker, **not** a `SparePart` table, because UoM, category,
costing method, average cost, reorder point and the derived on-hand already live on `Item` — and
`("maintenance", "Maintenance")` on `StockMove.MOVE_TYPES`, the outbound type the issue-parts verb posts.

### Models  (`models/AssetManagement/`, load order `_choices` → `Assets` → `MaintenancePlans` → `MaintenanceWorkOrders` → `MeterReadings`)

`_choices.py` is **pure data — no queries, no model imports, not even `_base`** (the `ContractCompliance/_choices.py`
precedent, and `__all__` is explicit because `models/__init__.py` star-imports it first). It holds the seven
vocabularies read from two or more directions: `CRITICALITY_CHOICES` (critical/high/medium/low),
`PRIORITY_CHOICES` (urgent/high/medium/low), `WORK_TYPE_CHOICES` (preventive/corrective/breakdown/inspection/
calibration/predictive/safety), **Maximo's failure hierarchy** flattened to `PROBLEM_CODE_CHOICES` /
`CAUSE_CODE_CHOICES` / `REMEDY_CODE_CHOICES` (all CLOSED, all carrying `other` as the honest escape hatch — a closed
vocabulary is what makes "which cause costs us the most downtime?" a `GROUP BY` rather than a text-mining project),
and `METER_SOURCE_CHOICES` (manual/work_order/sensor — `sensor` is the 11.7 seam, written by nothing today). Plus
`MAX_LABOUR_RATE`, and `CRITICALITY_CSS` / `PRIORITY_CSS` / `WORK_TYPE_CSS` — colour is decided in exactly ONE
place per vocabulary (the `KpiSnapshot.BAND_CSS` precedent) so a badge cannot be styled one way on the list page
and another on the detail page. Single-model vocabularies stay on their model with their own maps
(`Asset.ASSET_TYPE_CHOICES` / `STATUS_CHOICES` + `STATUS_CSS`, `MaintenancePlan.TRIGGER_CHOICES` /
`SCHEDULE_BASIS_CHOICES` / `CONDITION_OPERATOR_CHOICES` + `DUE_STATUS_LABELS` / `DUE_STATUS_CSS` / `TRIGGER_CSS`,
`MaintenanceWorkOrder.SOURCE_CHOICES` / `STATUS_CHOICES` + `STATUS_CSS`). **Colour-named classes only**
(`badge-green/red/amber/info/muted/slate`) — `badge-success`/`-warning`/`-danger` render unstyled (L33).

- **`Assets.py`** — **`Asset`** [`AST-`] + **`AssetSparePart`**. Identity (`code` unique per tenant, `name`,
  `asset_type`, `status`, `criticality`, free-text `category` sized to match `accounting.FixedAsset.category`,
  `tag_code` = the QR/barcode value), placement (`parent` self-FK, `location`→`scm.Location`, `org_unit`,
  **`work_center`→`scm.WorkCenter`** — the SCM differentiator, because taking a machine down is a *capacity* fact
  4.8's board wants to read), three `core.Party` roles (`custodian`/`supplier`/`service_vendor`), commercial
  (`purchase_date`/`commissioned_on`/`warranty_expires_on`/`purchase_cost`, plus `fixed_asset`→`accounting.FixedAsset`
  as a **pointer and nothing more**), and the meter DEFINITION (`meter_name`/`meter_unit` — the values live in
  `MeterReading`). `clean()` is table-driven off `TENANT_SCOPED_FKS` (eight pointers), enforces `tag_code`
  uniqueness **in Python** (MariaDB stores a blank as `""`, so `unique_together` would allow exactly ONE untagged
  asset per workspace) and walks the parent chain under `MAX_HIERARCHY_DEPTH = 20` to reject self-parents and
  cycles — the cap bounds the walk even when the DATA is already looped, so the edit form that repairs a loop can
  still validate. **Everything reliability-shaped is DERIVED and has no column**: `open_jobs()`/`open_job_count()`/
  `is_down_now()`, `downtime_minutes()`, `failure_count()`, `mtbf_hours()`, `mttr_hours()`, `availability_pct()`,
  `maintenance_cost_to_date()`, `next_pm_due()`, `latest_reading()`, `days_to_warranty_expiry()`/`warranty_chip()`.
  `CLOSED_JOB_STATUSES` is stated as the TERMINAL set so an unknown status counts as OPEN; `FAILURE_WORK_TYPES` is
  `("breakdown",)` only — planned corrective work is repair, not failure, and counting it would depress MTBF for
  doing maintenance properly. `AssetSparePart` is **tenant-less** (reached via `asset__tenant`), `unique_together
  ("asset","item")`, `item` PROTECT, and is the ASSOCIATION only — which item, `quantity_per_service`, `is_critical`.
- **`MaintenancePlans.py`** — **`MaintenancePlan`** [`PM-`] + **`MaintenancePlanTask`**. `trigger_type` is
  **Oracle's four forecast methods verbatim** — `calendar` / `meter` / `combined` / `condition` — never a boolean
  `is_meter_based`, which would have covered two of the four; `combined` means *whichever axis arrives first*, and
  `due_status()` is the one place that is decided. `schedule_basis` is `floating` (measure from the last
  completion — right for wear-driven work) vs `fixed` (measure from the published calendar — right for a statutory
  inspection); the difference is not guessable from the data, so it is stored. `next_due_on` / `next_due_reading`
  are COLUMNS because they are *the schedule*, not a derivation — everything genuinely derived from them
  (`days_until_due`, `meter_gap`, `is_due`, `due_status`) recomputes on read. `last_completed_on` /
  `last_generated_on` are `editable=False` (L22). `asset` is **CASCADE** — deliberately unlike
  `MaintenanceWorkOrder.asset`, which is PROTECT: a plan is a standing instruction, a completed job is history.
  Every day-count column is capped (`interval_days` ≤ 3650, `lead_time_days` ≤ 365) because a bare
  `PositiveIntegerField` fed to `timedelta(days=…)` is an uncaught `OverflowError`. `MaintenancePlanTask` is
  tenant-less (`plan__tenant`), ordered on `sequence` in tens, with `is_mandatory` and `is_safety_step` — safety
  rides as a **flag, not a permit table** until 11.11 exists.
- **`MaintenanceWorkOrders.py`** — **`MaintenanceWorkOrder`** [`MWO-`] + **`MaintenanceWorkOrderPart`** +
  **`MaintenanceWorkOrderTask`**. **ONE table covering requests, PM occurrences and breakdowns** — a maintenance
  *request* is `status="requested"` plus `reported_by`, and approving it is a status verb, not a conversion between
  two tables (the same call 4.9 made for audit findings vs NCRs; a split forks every MTTR/MTBF/downtime/PM-compliance
  query into a UNION over two grains). Eight states: requested/approved/scheduled/in_progress/on_hold/completed/
  closed/cancelled, with `OPEN_STATUSES` and `CLOSED_STATUSES` declared once on the model because three readers
  outside the file depend on them. `status`, `started_at`, `completed_at` and `downtime_minutes` are all
  `editable=False` and absent from `Meta.fields`; `downtime_start`/`downtime_end` ARE editable on purpose (the
  window is routinely discovered after the fact) and `save()` derives `downtime_minutes` from the pair, **clamped**
  to `MAX_DOWNTIME_MINUTES` (a year) — two `DateTimeField`s can be 9999 years apart, which is ~5.3e9 minutes and an
  `OverflowError` on a column no validator ever sees. Also `is_unplanned_downtime`, the three failure codes,
  `labour_hours`/`labour_rate` (capped by `MAX_LABOUR_RATE`, refused on the way in rather than clamped on the way
  out) / `external_cost`, `meter_reading_at_work` (a **capture field nothing reads** — the complete verb turns it
  into a `MeterReading`), and a nullable `non_conformance` link OUT to 4.9. Derived, never stored: `parts_cost`,
  `labour_cost`, `total_cost`, `duration_hours`, `is_on_time`, `open_task_count`. `MaintenanceWorkOrderPart` is
  tenant-less, `item` PROTECT, with `unit_cost`/`is_issued`/`issued_at` all `editable=False` — planned and issued
  are separate facts, and `unit_cost` is stamped from `item.average_cost` AT ISSUE TIME and never re-read.
  `MaintenanceWorkOrderTask` is a **SNAPSHOT of the plan's checklist with deliberately NO FK back to it** (the 4.9
  `InspectionResult` / 4.8 `WorkOrderComponent` precedent): `sequence`/`description`/`expected_result`/
  `is_mandatory`/`is_safety_step` are plain column copies, and `is_done`/`actual_result`/`completed_at`
  (`editable=False`) are what actually happened.
- **`MeterReadings.py`** — **`MeterReading`**, `TenantOwned` and **no `NUMBER_PREFIX`** (the `StockMove`
  precedent — a reading is a data point in a series, not something anyone quotes by number). `asset`,
  `recorded_by`→`core.Party`, `meter_name` (free text, NOT validated against `Asset.meter_name` — an asset commonly
  has several meters), `unit`, `reading`, `read_at`, `source`, `reference`, `notes`. `reading` is **bounded by a
  validator and never clamped** — it is an assertion about the world, not a computed figure, and quietly clamping
  an odometer would corrupt every meter-based due date while looking like a successful save. `clean()` carries the
  cross-tenant guard and **refuses a future `read_at`**: a post-dated row sorts to the top of an append-only log
  and becomes "the current value" for a machine that has not reached it.

### Forms  (`forms/AssetManagement/`)

All four `Meta.fields` are **WHITELISTS, never `Meta.exclude`**. `AssetForm` (TenantUniqueMixin) scopes `parent`
(excluding self), `location`/`work_center`/`org_unit`, the three party dropdowns by ROLE (`_employee_parties` for
`custodian`, `_supplier_parties` for `supplier`/`service_vendor`) and `fixed_asset` — deliberately **not** narrowed
by `FixedAsset.status`, since an operational asset legitimately points at a `cip` or `disposed` book record.
`AssetSparePartForm` has four fields and **no parent pointer** — `asset` comes from the ROUTE, never POST.
`MaintenancePlanForm` + `MaintenancePlanTaskFormSet` (`inlineformset_factory`, `extra=3`, **prefix `tasks-`**);
`MaintenanceWorkOrderForm` + `MaintenanceWorkOrderPartFormSet` (**prefix `parts-`**, with
`BaseMaintenanceWorkOrderPartFormSet` refusing to remove an ISSUED line). `MeterReadingForm.Meta.fields` is
`["asset","meter_name","unit","reading","read_at","notes"]` — `source` and `reference` are **provenance and are not
form fields at all** (see gotcha 5).

### URLs / routes  (`urls/AssetManagement/`, `app_name="scm"`) — 36 names

- **asset** (`assets/`) — `asset_list` `asset_create` (`assets/add/`) `asset_detail` `asset_edit` `asset_delete`
  (`@tenant_admin_required @require_POST`), plus the one parent-nested child route
  `assets/<int:pk>/spare-parts/add/` → `asset_add_spare_part`.
- **assetsparepart** — `assetsparepart_edit` / `assetsparepart_delete` at
  `asset-spare-parts/<int:pk>/{edit,delete}/`, on the CHILD's own pk (a child pk already identifies its parent;
  nesting would invite pairing a real line with somebody else's asset id — the `compliance-checks/` rationale).
  **No list and no detail route** — a parts list is a panel on its asset, and the workspace-wide view is the
  spare-parts REPORT.
- **maintenanceplan** (`maintenance-plans/`) — `_list/_create/_detail/_edit/_delete` +
  `maintenance-plans/<int:pk>/generate/` → `maintenanceplan_generate` (`@tenant_admin_required @require_POST`).
- **maintenanceworkorder** (`maintenance-work-orders/`) — `_list/_create/_detail/_edit/_delete`, plus **ten verbs**
  all under `<int:pk>/` and all `@require_POST`: paths `approve/` `schedule/` `start/` `hold/` `resume/`
  `complete/` `close/` `cancel/` `issue-parts/` `record-reading/` → names `maintenanceworkorder_approve`
  `_schedule` `_start` `_hold` `_resume` `_complete` `_close` `_cancel` `_issue_parts` `_record_reading` (note the
  two hyphenated paths map to underscored names). **`@tenant_admin_required` on four**: `_delete`, `_approve`,
  `_cancel`, `_issue_parts` (the last because it writes the ledger) — so those four buttons need
  `{% if request.user.is_superuser or request.user.is_tenant_admin %}`.
- **the checklist child** — `maintenance-work-order-tasks/<int:pk>/toggle/` → `maintenanceworkordertask_toggle`, on
  its OWN pk, resolved through `work_order__tenant` (that join IS the authorization check). **No create and no
  delete route**: the checklist is a snapshot, and ticking a step is the only change it accepts.
- **meterreading** (`meter-readings/`) — `meterreading_list` `meterreading_create` (takes an optional
  `?asset=<pk>` pre-fill) `meterreading_detail`. **No edit route, no delete route** — see gotcha 5.
- **the three computed reports** — `pm-forecast/` → `scm:pm_forecast` (`?days=`, capped at
  `MAX_FORECAST_DAYS = 365`), `spare-parts/` → `scm:sparepart_list`, `asset-depreciation/` →
  `scm:asset_depreciation_report`. No `<int:pk>` anywhere in that module; every option is a query string.

**Collision check, already done and recorded in the url module docstrings**: nothing anywhere in `scm` starts with
`asset`, `maintenance`, `meter`, `pm` or `spare`. `assets/`, `asset-spare-parts/`, `asset-depreciation/`,
`maintenance-plans/`, `maintenance-work-orders/`, `maintenance-work-order-tasks/` and `spare-parts/` are all
DISTINCT whole path components — Django matches whole components and never splits one at a hyphen. 4.13 adds no
greedy `<str:…>` converter; 4.10's `return-tracking/<str:token>/` remains the app's only one.

### Templates  (`templates/scm/assets/`)

Entity folders `asset/{list,detail,form}.html`, `assetsparepart/form.html` (form only — a child of the asset),
`maintenanceplan/{list,detail,form}.html`, `maintenanceworkorder/{list,detail,form}.html`,
`meterreading/{list,detail,form}.html` (**`form.html` is the CREATE page only — there is no edit form, and its
provenance card says on the page why `source`/`reference` are not inputs**), and the three
report pages at the sub-module root as standalone pages (the `safety_stock_report.html` precedent):
`pm_forecast.html`, `spare_parts.html`, `asset_depreciation.html`. Badge classes come from the model
(`obj.status_css` / `criticality_css` / `priority_css` / `work_type_css` / `due_status_css` / `trigger_css`) —
Django templates cannot subscript a dict by a variable, so every colour decision is resolved in Python.

### Seeder  (`_seed_asset_tenant`, runs LAST in `handle()`)

Guarded on an `Asset` existence check, and it **REFUSES rather than half-seeds** when 4.3 is absent (no `WH-MAIN`
location, no `DOCK-C`/`MON-27` items) — its assets sit at 4.3 locations and its jobs draw parts out of 4.3's
ledger. Creates: four assets with a real `parent`→`children` hierarchy (`LINE-01` > `LINE-01-DRV`, plus `FL-002`
and `CNV-03`, the conveyor tied to 4.8's `WC-ASM` when manufacturing ran) of which **two link an
`accounting.FixedAsset` and two do not**, so the depreciation report's coverage figure is genuinely measured; two
4.3 items flipped to `is_spare_part`; the machines' parts lists; **eight meter readings** forming a real rising
trend (six forklift running-hours rows ending at 1218.5 h, two conveyor bearing-temp rows ending at 77.2 °C);
**three plans on three DIFFERENT triggers** (a floating calendar plan, a meter plan whose 1200 h target is already
passed so `meter_gap()` is negative and `due_status()` answers `overdue` off the usage axis with no date involved,
and a condition plan at 75 °C that fires against the 77.2 °C reading); and three jobs at three points of the
lifecycle — a completed PM (generated, walked down the real ladder, parts issued, completed), an **open breakdown
that is down RIGHT NOW** (`downtime_start` set, `downtime_end` NULL, so `is_down_now()` is true and `mttr_hours()`
hits its zero-denominator guard and answers `None`), and an unapproved request. **Nothing hand-sets a status or a
system stamp** — every job walks the verbs' own ladder, the schedule is rolled by `MaintenancePlan.advance()`, and
every row is `full_clean()`ed (excluding `number`) so the seed PROVES the trigger contract and the cross-tenant
guards. The one ledger write goes through the real `_shared_items` / `_insufficient_stock` / `_post_stock_move`
path and is guarded on `(move_type="maintenance", reference=<MWO number>)` — **the same filter `_flush()` deletes
on**, so guard and teardown describe the same rows. `_flush()` puts 4.13 FIRST: readings → work orders → plans →
assets → the `maintenance` moves, forced by the single PROTECT edge `MaintenanceWorkOrder.asset`.

### Common tasks (4.13)

- **Add a field to an entity**: edit `models/AssetManagement/<Entity>.py`, add it to that form's `Meta.fields`
  whitelist **unless it is derived, verb-written or a system stamp** (those get `editable=False` and stay off the
  form), surface it in `detail.html`/`form.html`, `makemigrations scm && migrate`.
- **Add a work-order verb**: add a `*_STATUSES` tuple beside the others at the top of
  `views/AssetManagement/MaintenanceWorkOrders.py`, call `_transition(...)` (passing a `precheck` if the guard
  reads any table other than the work order's own row), add the route **under `<int:pk>/`** in
  `urls/AssetManagement/MaintenanceWorkOrders.py`, re-export the view, then add BOTH the `can_<verb>` context flag
  and the button gated on it — a gate lives in two places.
- **Add a filter**: pass the choice list / queryset from the view (`crud_list(extra_context=…)`) and add the
  `(param, lookup, is_int)` tuple to `filters=`; pk filters compare with `|stringformat:"d"`, never `|slugify`.
- **Add a meter source**: extend `METER_SOURCE_CHOICES` in `_choices.py` — the column is `max_length=12` against a
  10-char longest value, so there is headroom. Do **not** add an edit route to correct a reading.
- **Extend the seeder**: add rows inside `_seed_asset_tenant`'s `Asset` guard, reusing the existing `_asset` /
  `_plan` / `_job` / `_reading` existence-checked helpers; anything that writes the ledger needs its own
  `(move_type, reference)` guard and a matching line in `_flush()`.

### Non-negotiables for 4.13

1. **`MaintenanceWorkOrder` [MWO-] is NOT 4.8's `WorkOrder` [WO-].** Separate documents, separate prefixes,
   separate url prefixes (`maintenance-work-orders/` vs `work-orders/`), separate templates. 4.8's work order MAKES
   product — it explodes a BOM, carries `item`/`quantity_planned`/`quantity_produced`/`component_location`/
   `output_location` and posts `consumption`/`production` moves; this one REPAIRS a machine and has none of those.
   The tempting merge (one table with a `work_type` discriminator) breaks three shipped features at once: **MRP
   netting** reads open work orders as supply for their `item` and a repair has none; **the load board** would
   schedule repairs against work-centre capacity that is already unavailable *because* the machine is down, double
   counting the outage; and **OEE** divides good output by planned production time, so rows with no output quantity
   drive the numerator to zero on the very shifts maintenance was working. The one place they touch is
   `Asset.work_center` — a fact 4.8's board *reads*. **Never "tidy" one to look like the other.**
2. **`maintenance` is in `OUTBOUND_MOVE_TYPES` but NOT in `COGS_MOVE_TYPES`** (`apps/scm/analytics.py`), and the two
   constants must stay separate. It is out of COGS because a spare fitted to your own machine is maintenance
   **opex**, not the cost of any good that was sold — folding it in inflates COGS and understates gross margin on
   every product it never touched. It is not `issue` because 4.7's `demand_series(source="stock_issues")` reads
   `issue` as **customer demand**. But it IS outbound, because *"has anybody touched this in 90 days?"* is a
   **recency** question, not a valuation one. Sharing one tuple was a live bug: a spare drawn every week posts only
   `maintenance` moves, so it never entered the dead-stock resolver's "moved" set and **every actively-consumed
   spare was classified as dead stock** — and that does not stop at a dashboard, `_detect_dead_stock` persisted
   `SupplyChainAlert` rows reading "<SKU> has not moved for 90 days" about a part issued last week. Reproducible
   with the shipped seeder.
3. **The plan schedule has exactly ONE writer: `maintenanceworkorder_complete`.** `maintenanceplan_generate`
   deliberately does NOT roll it, and that is not an omission. `advance()` anchors a `fixed` plan on its own
   published `next_due_on`, so a second call compounds the first and advanced the plan **two cycles per
   occurrence** (measured on a quarterly plan: Jan 1 → generate Apr 1 → complete Jun 30, and the April inspection
   silently never came due; identical compounding on `next_due_reading`, 1000 → 1250 → 1500). Beyond that bug,
   `floating` is *defined* as measured from the last completion — rolling at generate time anchors it on the
   generate date — and a generated job later CANCELLED must not consume a cycle nobody performed. So the plan stays
   visibly due until the work is actually done (generate already refuses while an open job exists, so it cannot
   double-generate meanwhile), and the page says so out loud. **`MaintenancePlan.advance()` rolls exactly ONE cycle
   even when several were missed** (the `ComplianceRequirement.record_check` posture), **returns the list of field
   names it wrote and does not save by default** (`save=False`) — both callers fold that list into their own
   `update_fields` alongside their own stamp, so the roll and the stamp are one round trip.
4. **The completion meter capture must be filed BEFORE the plan roll reads it.** `advance()` on a **floating meter**
   plan takes its base from `plan.latest_reading()`, so a capture filed afterwards is invisible to the very roll it
   should drive. Measured: a forklift last read at 1218.5 h, completed with a 1250 h capture on a 250 h interval,
   published **1468.5 instead of 1500** — the next service 31.5 h early, every cycle, compounding. The complete
   verb therefore does the three steps in a fixed order inside ONE lock: stamp → file the reading → roll the plan.
   (An asset that names no meter cannot have a capture filed; that is said out loud in a warning message rather
   than saved under an invented name.)
5. **`MeterReading` has no edit route and no delete route, by design** — the `StockMove` append-only precedent,
   verbatim, down to `admin.py` registering it read-only. A wrong reading is corrected by posting a LATER, CORRECT
   one: `Asset.latest_reading()` answers with the newest row so the fix takes effect immediately, the mistaken row
   stays visible (which is the *point* of an append-only log), and a meter plan or condition trigger compares
   readings against a target — so silently rewriting one rewrites every due date derived from it, retroactively,
   with no audit row saying which figure the schedule was built on. **If a later pass is tempted to add an edit
   route, the answer is a second reading, not a mutable first one.** Relatedly, `source` and `reference` are
   **provenance**: they are stamped by whichever verb actually files the reading (`work_order` + the MWO number),
   never form fields. Leaving them on the form let any logged-in member post a hand-typed figure claiming to have
   been captured on somebody else's job, on a log with no edit route to take it back.
6. **The `None` contract.** `mtbf_hours()` / `mttr_hours()` / `availability_pct()` return **`None`, never `0`**, on
   a zero denominator (no failures, no finished-and-timed breakdown, no establishable observation window) — an MTBF
   of 0 h reads as "fails constantly", the exact opposite of an asset that has never failed. Same for
   `MaintenancePlan.meter_gap()`, `MaintenanceWorkOrder.duration_hours` / `is_on_time`, and every report figure
   with no data behind it. **`maintenance_cost_to_date()` is NOT None-able** — it returns `q2(...)`
   unconditionally, so a `0.00` there is a REAL zero (nothing has been spent yet). Templates must render `—` for
   the first three, and the idiom is an explicit `{% if x is not None %}`: **`{{ x|default:"—" }}` is wrong**
   (it swallows a real `0`, which is falsy) and **`{{ x|default_if_none:"—"|floatformat:2 }}` is also wrong**
   (`floatformat` cannot parse an em dash and returns an empty string, so the blank silently disappears).
7. **Query shapes that must not regress.** `asset_list` annotates `open_jobs_count` with a **correlated scalar
   `Subquery`**, NOT a joined `Count`: the joined form makes the whole asset query an aggregate query and forces a
   `GROUP BY scm_asset.id`, which `.count()` cannot collapse — Django wraps it in a derived table and keeps the
   `down_now` EXISTS in the inner select, so the PAGINATOR's count alone became one correlated EXISTS probe per
   asset in the workspace plus a full LEFT OUTER JOIN plus `Using temporary; Using filesort`, every page load
   (`.order_by()` on the subquery is load-bearing too, or `MaintenanceWorkOrder.Meta.ordering` drags a column into
   the GROUP BY). `down_now` is an `Exists()`, not a `Count` — a correlated EXISTS stops at the first row.
   `Asset._reliability_agg` is ONE memoised aggregate serving all six header figures (it was eleven round trips),
   and the **parts `Sum` deliberately stays a separate query**: `MaintenanceWorkOrderPart` is a different GRAIN, and
   folding it in fans the job rows out and multiplies labour and external cost by each job's part count — a
   three-part repair charged three times its labour, silently, forever. `_reliability_agg` also reads `now` ONCE,
   so an open downtime window cannot print 412 min in one tile while another has already divided by 413. **Any
   query touching `MeterReading` must state `tenant` explicitly** even when the related manager makes it redundant:
   `tenant_id` is the LEADING column of `scm_mtr_tnt_asset_idx` `(tenant, asset, read_at)`, so without it MariaDB
   falls back to the plain FK index and filesorts the asset's whole meter history to find one row (measured — a
   reader adding a third caller owes the same line). And **templates read the annotations, never the per-row
   methods** — `row.down_now`, `row.open_jobs_count`, `part.on_hand`, `derived_on_hand`; `Asset.is_down_now()`,
   `Asset.open_job_count()`, `Item.on_hand()` and `MaintenancePlan.latest_reading()` are all correct and all cost a
   query EACH, per row, per reference.
8. **A guard that protects the ledger must be evaluated INSIDE the row lock.** `select_for_update()` protects the
   work order's own columns, but a guard reading a CHILD table (a part line's `is_issued`) is a plain snapshot
   read: run before the lock it answers about the state the request started in, and the write then waits for the
   lock and lands the moment the competing transaction commits. Not a narrow window either — `_issue_parts` holds
   the row locked for its whole per-line loop, so firing issue-parts and cancel back to back wins it reliably.
   `_transition` therefore takes a **`precheck` callable** evaluated inside the lock, and the shared refusal
   sentence lives in one helper (`_issued_parts_refusal`) so cancel and delete cannot drift.
   **`maintenanceworkorder_delete` is hand-rolled rather than delegating to `crud_delete`** for exactly this
   reason: `crud_delete` re-fetches by pk with no lock and re-checks neither guard, because it cannot know about
   guards it was never told about — and `MaintenanceWorkOrderPart` is CASCADE, so the loss was irreversible (the
   record of WHAT was drawn and at what cost destroyed, while the negative `maintenance` StockMoves survived
   pointing at a document that no longer existed).
9. **`Asset.status` is user-editable and NO verb writes it.** Raising, starting, completing or closing a job leaves
   it alone; "down now" is DERIVED from open downtime windows (an open job with `downtime_start` set and
   `downtime_end` still null), stated once in `_open_downtime_jobs()` so the header chip and the rows under it
   cannot disagree. The alternative — a verb that flips the asset to `under_maintenance` and back — needs a rule
   for every path out of a job (cancelled, held, superseded by a second job on the same machine), and the first
   path anyone forgets leaves an asset permanently reading "under maintenance" while it is happily running. One
   writer per column. Note the vocabulary is deliberately DIFFERENT from `accounting.FixedAsset.status`
   (cip/active/disposed): an asset can be `standby` operationally while perfectly `active` financially.
10. **Spare Parts Inventory is a COMPUTED page over 4.3, and there is no `SparePart` table.** A spare is an
    `scm.Item` flagged `is_spare_part`; its on-hand is the live SUM of the append-only `StockMove` ledger (one
    grouped aggregate inside a scalar subquery — **not** `annotate(Sum("stock_moves__quantity"))`, whose join form
    pushes filters into `HAVING` and raises `Unknown column … in 'having clause'` the moment the same filter is
    counted for a header chip on MariaDB); its min/max come from the `ReorderRule` the buyer already maintains.
    Likewise **Asset Depreciation READS `accounting.FixedAsset`** — acquisition cost, accumulated depreciation and
    book value. SCM stores none of them, recomputes none of them and posts **no `JournalEntry`** (L29); the page
    prints that note on itself. Rows with no link, a **cross-workspace** link (defence in depth — treated as
    unlinked rather than quietly printing another tenant's book value) or a **nil book value** are COUNTED and
    reported as excluded, never folded in as zero and never rendered as infinity. Both reports render 200 on an
    empty tenant with an honest zero-coverage line; neither may 500 on a first run.

## 4.14 Labor Management  (`apps/scm/*/LaborManagement/`, templates `templates/scm/labor/`)

The **people** side of the warehouse, and the sub-module most defined by what it deliberately does **not** own.
Two whole features here are computed pages over somebody else's tables, and a third is a read-only hand-off.

**THE THREE THINGS 4.14 DOES NOT DECLARE — read this before adding anything.**

1. **No attendance table. HRM owns daily attendance.** `hrm.AttendanceRecord` is unique per
   `(tenant, employee, date)` with `check_in`/`check_out` TimeFields, derived `hours_worked`, geofence and a
   biometric `source`, alongside `Shift`, `ShiftAssignment`, `AttendanceRegularization`, `Timesheet` and
   `OvertimeRequest`. A `LaborSession` is the layer *beneath* that: a shift **at a warehouse** whose minutes are
   split into booked activity intervals, which is what an LMS measures and what a one-row-per-day attendance
   record structurally cannot hold. `LaborSession.work_date` is deliberately the **same grain** as
   `AttendanceRecord.date` so the two reconcile **in a report, without a FK**.
2. **No task table, and no second assignee column.** 4.4's `PickTask` / `PutawayTask` / `CycleCountTask` already
   carry `assigned_to`, a status and lifecycle stamps. `scm:labor_board` is a **computed console** that reads
   those three queues live and writes **only** their existing `assigned_to`. Migration `0024` contains **no
   `AddField` at all** — that is the evidence, not the claim. (Same precedent as 4.13's Spare Parts computing over
   4.3 and 4.4's bin bullet pointing at `scm:location_list`.)
3. **No payroll posting.** `scm:labor_payroll_export` writes **nothing**, anywhere. `accounting.PayrollRun` is a
   whole-company period **accrual** with no employee lines and no hours columns, so "drafting" one from warehouse
   labour would be *wrong*, not merely redundant. Contrast 4.6's freight audit, which *does* draft an
   `accounting.Bill` — because a Bill has lines and a payee.

**`apps/scm` contains ZERO `hrm.*` references** (no `from apps.hrm`, no `"hrm.X"` FK string) and 4.14 did not add
the first. There is an architectural test asserting it. 4.14 also writes **no `StockMove` and no `JournalEntry`**.

### Models  (`apps/scm/models/LaborManagement/`)

`_choices.py` first — it imports no sibling model, so the edge runs one way. It owns `ACTIVITY_CHOICES` and the
`DIRECT_ACTIVITIES` / `INDIRECT_ACTIVITIES` **frozensets** (the single source of truth for "is this row
productive" — every aggregate branches on these, never a hand-typed tuple), `INDIRECT_REASON_CHOICES`, the
`*_CSS` dicts, and every bound. Re-exported **by name**, not `import *`: 4.13's `AssetManagement/_choices` is
star-imported and exports `MAX_LABOUR_RATE`, so 4.14's rate ceiling is the distinct token `MAX_STANDARD_RATE`.

- **`LaborStandard` [`LST-`]** — the engineered standard, and the keystone: without it 4.14 is a timeclock.
  Multi-determinant (`setup_minutes` + `travel_minutes` + `minutes_per_unit` + PF&D `allowance_pct`), scoped by
  `location` and/or `item_category` (both nullable = network-wide), dated with `effective_from`/`effective_to`,
  and `source` ∈ engineered/observed/benchmark/learned. `minutes_for(qty)` =
  `(setup + travel + qty × rate) × (1 + allowance/100)` — **the whole earned-minutes definition, in one place**.
  `status` is `editable=False` (activate/archive verbs); `EDITABLE_STATUSES = ("draft", "active")` because an
  active standard stays editable **precisely because every activity snapshots it**.
  Module-level **`select_standard(tenant, activity, location, item_category, on_date)`** — most-specific-wins
  (location+category → category → location → network), ties by latest `effective_from`, active rows only, and
  **returns `None` when nothing matches**. Every caller must handle that: an unmeasured job must not read as a
  failing one.
- **`LaborSession` [`LSN-`]** — the warehouse shift. `worker` → **`core.Party`** on `PROTECT` (the worker is the
  *subject* of the row — contrast `MeterReading.recorded_by`, `SET_NULL` because the observation outlives the
  observer). **Never `hrm.EmployeeProfile`.** Status ladder `open → closed → approved` (+ `cancelled`);
  `approved` **is** the export lock. Provenance (`source`, `recorded_by`, `login`, the three stamps) is all
  `editable=False` and stamped by whichever verb files the record. **No `exported_at` column** — a decision: a GET
  must not write. Twelve derived figures, none stored, each accepting a pre-fetched `activities=None` list so one
  render is one scan.
- **`LaborActivity` [`LAB-`]** — the booked interval, shaped on 4.8's `ProductionTimeLog`. `duration_minutes`
  derived in `save()` **with the `update_fields` ride-along**. Nullable pointers to the three 4.4 tasks (at most
  one, and it must match the activity type). **The four `*_snapshot` columns are the correctness feature**:
  resolution happens **once**, in the create view, and `save()` never re-resolves.
- **`LaborPlan` [`LPL-`] + `LaborPlanLine`** — 4.7's generate-then-review shape. `LaborPlanLine` is
  **tenant-less** — scope it via `plan__tenant`, always. `planned_headcount` is the **only** editable column on a
  line.

### URLs  (`apps/scm/urls/LaborManagement/`, `app_name="scm"`)

`labor-standards/` · `labor-sessions/` · `labor-activities/` · `labor-plans/` · `labor-plan-lines/` ·
`labor-board/` · `labor-payroll-export/` · `labor-scorecard/` — **eight distinct whole path components**; nothing
else in scm starts with `labor`. Names: `laborstandard_{list,create,detail,edit,delete,activate,archive}` ·
`laborsession_{list,create,detail,edit,delete,clock_in,clock_out,close,approve,reopen,cancel}` ·
`laboractivity_{list,detail,edit,delete}` + `laborsession_add_activity` ·
`laborplan_{list,create,detail,edit,delete,generate,approve,archive}` · `laborplanline_edit` ·
`labor_board` / `labor_board_assign` / `labor_board_unassign` · `labor_payroll_export` · `labor_scorecard`.

`laborsession_add_activity` **nests** under its session (the parent supplies the child's session, which must
never come from POST); `laborplanline_edit` hangs off its **own** pk (a child pk already identifies it, and
nesting invites pairing a real child with someone else's parent).

### Gating — 4.14 renders NAMED PEOPLE, so this is not the usual list

House policy, checked against `apps/hrm`: a **workspace-wide roll-up over named people** is
`@tenant_admin_required` (hrm's cost, leave-liability, executive, benchmarking reports); a **per-record** people
page is `@login_required` (hrm's attendance record list). Therefore:

- `laborsession_list` / `laboractivity_list` and the detail pages — `@login_required`. Correct: per-record.
- **`labor_scorecard` — `@tenant_admin_required`.** It *ranks* colleagues with a coaching band; there is no
  version scoped to one person that is still a ranking. Its four header chips are wrapped in the house gate.
- **`labor_payroll_export` — `@login_required`, but the ROWS narrow.** It is a sidebar bullet and `resolve_nav`
  has no per-link permission concept, so gating it would hand every member a bullet that 403s (L32). An admin
  sees the workspace; everybody else sees **only themselves**, the page says so, and a member with **no linked
  Party** gets a sentinel worker id — **not `None`**, which `_worker_aggregate` reads as "no filter" and would
  hand them the whole floor. The worker **dropdown** is scoped too: narrowing the table while listing every
  colleague in a `<select>` leaks the roster the narrowing exists to protect.
- Tenant-admin verbs: the five deletes, `laborsession_approve`/`_reopen`/`_cancel`,
  `laborstandard_activate`/`_archive`, `laborplan_generate`/`_approve`, and **both board verbs** (they write
  another sub-module's table).

### Templates  (`templates/scm/labor/`)

`laborstandard/` `laborsession/` `laboractivity/` `laborplan/` `laborplanline/` (entity folders, bare
`list/detail/form.html`) + three standalone report pages at the sub-module root: `labor_board.html`,
`labor_payroll_export.html`, `labor_scorecard.html`. **Note the deliberate asymmetry**: the backend package is
`LaborManagement/` (PascalCase NavERP title) while the template folder is `labor/` (short slug) — exactly what
4.13 does as `models/AssetManagement/` ↔ `templates/scm/assets/`. Do not "fix" either into matching the other.

### Seeder

`_seed_labor_tenant(tenant)` runs after `_seed_asset_tenant`. Six standards (five active — one at a location, one
by item category, three network-wide — plus one **draft**, so `select_standard()` demonstrably skips drafts),
three sessions on three different workers (one **approved** and fully booked, one **closed** with a real
**45-minute gap**, one **open** with `clock_out=None` so every "None while open" guard is exercised), ten
activities (three indirect with reasons, two carrying `error_quantity`, one linked to a real `PickTask`, one to a
real `CycleCountTask`, one deliberately unmeasured), and one 14-day plan generated to `planned` with 56 lines,
one short and one over. It creates **no Party** and writes **no StockMove**.

**It also required a change to 4.4's seeder**: `_seed_warehouse_tenant` walked all three of its tasks to terminal
states *and* assigned them, so every "what needs doing" surface — 4.4's own lists and 4.14's board — rendered
empty. It now also creates **one OPEN unassigned task of each kind**; 4.14 claims two of them and leaves the
put-away unassigned, so both halves of the board populate from one set of rows.

### Tests (`apps/scm/tests/`, ~505 for 4.14)

Appended to the shared suite, never a new module: `conftest.py` (fixtures), `test_models.py` (16
classes), `test_forms.py` (5), `test_views.py` (6), `test_security.py` (6). **`grep` any helper name
before defining one** — `test_suite_hygiene.py` fails the suite on a duplicate module-level name, and
`test_views.py` already owns `_messages` / `_message_blob` / `_returns_query_count`. The 4.14 date
helpers (`_labor_moment` / `_labor_workday` / `_labor_date`) are plain functions in `conftest.py`, not
fixtures, so they are **imported**, not injected.

The classes worth knowing, because each pins a defect that shipped and was fixed:
`TestRunningActivityIsCountedWhenItLands` · `TestSnapshotClamping` · `TestSnapshotImmutability` ·
`TestIndirectWorkIsNeverMeasured` · `TestSelectStandardPrecedence` · `TestGapFilterReturnsTheRightRows`
· `TestLaborPayrollExportPrivacy`.

**What this suite CANNOT prove**, because it runs on SQLite (`config.settings_test`) while production
is MariaDB — verified separately against the real database and worth re-checking by hand after any
change in these areas:
* the `HAVING`/`GROUP BY` shape behind `?gap=` (SQLite permits the non-aggregate MariaDB refuses);
* every `select_for_update` guard (SQLite has no row-level locking, so a concurrency test is vacuous);
* **column bounds — blind on BOTH engines.** This project's MariaDB runs without
  `STRICT_TRANS_TABLES` (`manage.py check` says so as `mysql.W002`), so an over-range decimal is
  **silently truncated**, not rejected. Verified: `100000000.9999` in, `99999999.9999` out, no
  warning. That is why `MAX_SNAPSHOT_MINUTES` clamps in Python — it is the only layer that holds.

### Non-negotiables for 4.14

1. **Every productivity figure answers `None`, never `0`, on a zero denominator.** An unmeasured job printed as
   0% is a claim about a named person that the data does not support. Templates use `|default_if_none:"—"` for
   numerics (`|default:` would swallow a genuine `0.00`).
2. **A still-running activity contributes to NEITHER side of a ratio.** `clean()` permits `ended_at=None` with a
   quantity, so its earned minutes are known while its duration is still 0 — counting it added to the numerator
   and nothing to the denominator, and performance *climbed when work started and fell when it finished*. The
   model (`_measured`, `_unit_totals`) and the scorecard's `GROUP BY` (`duration_minutes__gt=0` on all four
   filters) must always agree; there is a test asserting they return the same number for the same data.
3. **Snapshots are never rewritten.** Editing a `LaborStandard` cannot change a figure already filed. An
   **indirect** activity is never measured *whatever it carries* — `has_standard` gates on
   `INDIRECT_ACTIVITIES` at the model, so a direct row edited to `break` stops printing a performance %.
4. **Bounds are constants and none is computed from the thing it bounds** (L40): `MAX_SESSION_MINUTES`,
   `MAX_ACTIVITY_MINUTES` (explicitly *not* "the session's remaining minutes"), `MAX_ACTIVITIES_PER_SESSION`
   (nothing in the model bounds this — overlaps are legal), `MAX_HORIZON_PERIODS` (integer arithmetic on the two
   dates, **never** `len(range)`), `MAX_PLAN_LINES` (one `COUNT(*)` *before* any allocation), `MAX_BULK_ASSIGN`
   (measured on `request.POST.getlist` before any query), `MAX_SNAPSHOT_MINUTES` (**`q4()` is not this bound** —
   it clamps to (14,4) while the column is (12,4)).
5. **The bulk-assign path is bulk on purpose.** `write_audit_log` stores `str(obj)`, and `PutawayTask.__str__`
   walks two FKs while `CycleCountTask.__str__` walks one — per-row it measured 3–5 queries **per row** inside a
   held `FOR UPDATE`. It now does one lock-free `select_related` fetch for the display strings, one
   `bulk_update` and one `bulk_create`. **Do not add `select_related` to the locking query** — on MariaDB
   `FOR UPDATE` with joins locks the joined `Item`/`Location` rows too. And `bulk_update` does **not** fire
   `auto_now`, so `updated_at` is stamped explicitly.
6. **`?gap=` taught the filter rule (L44).** Annotating a `Sum` adds a `GROUP BY`; comparing a **non-aggregate**
   against it pushes the column into `HAVING`, which MariaDB rejects (MySQL 8 would not). `_ATTENDED_SPAN` is
   wrapped in `Max` for that reason. Test **every valid value** of a closed vocabulary, not just junk — a
   negative-input sweep proves the guard and says nothing about the feature.

### Common tasks (4.14)

- **Add a field to a standard** → model, `Meta.fields` whitelist (never `exclude`), the form's field groups AND
  the count in `laborstandard/form.html`'s note, then `makemigrations scm`.
- **Add a derived figure to a shift** → a method on `LaborSession` taking `activities=None`, passed the
  pre-fetched list by `laborsession_detail`; add the SQL twin to `_worker_aggregate` **and** a test that the two
  agree.
- **Add an activity type** → `_DIRECT_ACTIVITY_CHOICES` or `_INDIRECT_ACTIVITY_CHOICES` in `_choices.py` only;
  `ACTIVITY_CHOICES`, both frozensets and `ACTIVITY_CSS` are all derived from those two lists, so the partition
  stays total by construction.
- **Add a volume source to the plan** → `VOLUME_SOURCE_CHOICES`, a branch in `_daily_series`, and decide whether
  it is flow-constant (`_FLOW_CONSTANT_METHODS`) before caching it — `same_period_last_year` is per-bucket and
  caching it would flatten a seasonal plan.

## 4.15 Cold Chain Management  (`apps/scm/*/ColdChainManagement/` + `apps/scm/coldchain.py`, templates `templates/scm/coldchain/`)

**Three of the five NavERP.md bullets are COMPUTED PAGES, not tables.** That is the headline fact. 4.15 adds
three models and two additive fields, and reuses 4.3 / 4.13 for everything else.

**Models** (`apps/scm/models/ColdChainManagement/`)
- **`ColdChainMonitor`** (`CCM-`, `ColdChainMonitors.py`) — one device watching exactly ONE subject.
  `SUBJECT_FIELDS = ("location","asset","shipment")`, three typed **PROTECT** FKs, never a `GenericForeignKey`
  (a GenericFK carries neither a constraint nor a type, so it can point at a deleted or cross-tenant row).
  `clean()` enforces exactly-one AND **freezes the subject once readings exist** — re-pointing would silently
  re-attribute history the probe never measured. Carries limits (**a one-sided band is legal**), warning margin,
  `excursion_grace_minutes`, `logging_interval_minutes`, setpoint, and the three calibration columns.
  `status` is **user-editable here** — deliberately unlike the excursion's, which is verb-driven.
- **`TemperatureReading`** (no prefix, `TemperatureReadings.py`) — **append-only** interval SUMMARY rows (not raw
  samples), `interval_minutes` snapshotted per row, `unique_together (monitor, reading_at)` so a replayed import
  is a DB error rather than a doubled history. `source`/`recorded_by` are `editable=False`. **No edit view, no
  delete view, read-only admin** (the `StockMove`/`MeterReading` posture) — a wrong reading is corrected by
  filing a later one.
- **`TemperatureExcursion`** (`EXC-`, `TemperatureExcursions.py`) — split in half, and the split IS the design.
  The **measured half is detector-written and every column is `editable=False`**: `started_at` / `ended_at` /
  `duration_minutes` / `breach_direction` / `extreme_temperature` / `limit_min` / `limit_max` / `reading_count` /
  `mkt` / `last_detected_at`, plus `status`. **`limit_min`/`limit_max` are SNAPSHOTTED** so editing a monitor
  cannot rewrite what past episodes were breaches OF. Only severity / assessment / cause / corrective_action /
  notes and the three links out (`non_conformance`, `maintenance_work_order`, `lot_serial`) are writable.
- **Additive**: `storage_condition` on **`scm.Item`** and **`scm.Location`**, sourced from the package-ROOT
  `apps/scm/models/_choices.py` (root because 4.3 reads it too — a cross-sub-module vocabulary must not live in
  one sub-module's private folder). Both are on `ItemForm`/`LocationForm`; **without that they are unreachable
  and the whole Cold Storage bullet is inert** (this shipped broken once — see below).

**Service** (`apps/scm/coldchain.py`, flat at the app root like `analytics.py`)
- `detect_excursions(tenant, *, monitor=None, user=None, after=None)` is the **ONLY writer of every measured
  column**. It takes `select_for_update()` on the **MONITOR row** before reading anything — that lock **IS** the
  "one open episode per monitor" guard, because **MariaDB cannot express `UniqueConstraint(condition=…)`**.
  Locking the monitor (always present) rather than the episode matters: an episode lock is a no-op on exactly
  the path that would create a second one. `after=` is the sweep cursor past `MAX_MONITORS_PER_SWEEP`.
- `mean_kinetic_temperature(rows, *, frozen=False)` — USP <1079.2>, exact `Decimal`, interval-weighted (a hot
  hour weighs an hour, not "one row"). **Returns `None`, never 0, for frozen ranges** — MKT models Arrhenius
  degradation above freezing, so a number there is arithmetic without meaning.
- Also `walk_episodes`, `episode_stats`, `profile(monitor, *, date_from, date_to)`, `window_stats`,
  `time_in_range`, `severity_for`, `clamp_window`, `raise_work_order(excursion, user=None)` (hands off to 4.13).

**URLs** — alias **`_ccm_`** (`_cc_` is 4.12's, `_cp_` is 4.16's). `coldchainmonitor_*` (incl. `_profile`,
`_add_reading`, `_import_readings`, `_detect`), `temperaturereading_list/_detail` (**no edit/delete route
exists** — that absence is the append-only rule), `temperatureexcursion_*` + POST-only verbs
`acknowledge`/`assess`/`close`/`dismiss`/`raise_work_order`, and `cold_storage_report` /
`cold_chain_compliance_report` / `reefer_board`.

**Templates** (`templates/scm/coldchain/`) — entity folders `coldchainmonitor/` (incl. `profile.html`),
`temperaturereading/` (incl. `import.html`), `temperatureexcursion/`; the three derived pages sit at the
sub-module root. `profile.html` draws a **band strip, not a line chart**: the project ships no charting library
and no filter can offset a SIGNED temperature into a pixel height — half of 4.15 runs at −18 °C, so a naive
height-as-percent bar renders every frozen reading flat against the floor.

**Seeder** — `_seed_coldchain_tenant` in `seed_scm.py`. 4 monitors across all three subject kinds, 204 readings,
3 cold zones (one deliberately UNMONITORED so the gap report has a subject), a reefer asset + condition-trigger
`MaintenancePlan`, 3 lots (one already expired and still on hand). **It calls `detect_excursions()` and lets the
detector write every excursion** — a hand-written one would be a lie in the table an auditor reads. Its
`_flush()` block **must stay ahead of 4.13's asset teardown** (`ColdChainMonitor.asset` is `PROTECT`).

**Gotchas specific to 4.15 — all three shipped as real defects and were caught in review:**
1. **Never `MinValueValidator(ZERO)` on a temperature** and **never pass one through `q2()`/`q4()`**.
   `Decimal(value or ZERO)` turns a missing reading into a plausible **0 °C**, which in a freezer log either
   reads as a catastrophic excursion or masks a real one. The importer **skips and counts** an unreadable cell.
   Bounds are `MIN_TEMPERATURE_C = Decimal("-200")`.
2. **`Decimal("nan")` parses cleanly** and only raises `InvalidOperation` at the first ordering comparison — one
   `nan` CSV cell 500'd the whole import. `_parse_decimal` guards with `is_finite()`. `Infinity` was always safe.
3. **A decision column on a ModelForm whose real writer is a gated verb is a privilege escalation.**
   `assessment` was on `TemperatureExcursionForm` while `temperatureexcursion_edit` is `@login_required` and
   `assess` is `@tenant_admin_required` — any member could mark product released with no signature. It is off
   the whitelist; **do not put it back**. (`apps/scm/forms/ReturnsManagement/ReturnDispositions.py` has the same
   shape with `disposition` and is not yet fixed.)
4. Reefer maintenance declares **ZERO** entities — a reefer is DERIVED as *an `Asset` with an active monitor*, so
   `Asset.ASSET_TYPE_CHOICES` gains no `reefer` value that would go stale the day a unit is repurposed.
   `MaintenancePlan.condition_threshold` carries `MinValueValidator(ZERO)`, so a **sub-zero condition trigger is
   not expressible today** — the seeded plan uses a positive "too warm" threshold.
5. The compliance report states an explicit **NON-CLAIM**: it is an audit trail, not a validated 21 CFR Part 11 /
   EU Annex 11 system. Do not add conformance language.
6. `LotSerial.status` (quarantine) is **4.9's column to write**; 4.15 only reads it.

---

## 4.16 Customer Portal  (`apps/scm/*/CustomerPortal/`, templates `templates/scm/portal/`)

**The self-service layer, and mostly an exercise in NOT re-declaring things.** Two of its five NavERP bullets are
COMPUTED PAGES with no table. 4.16 owns no order (4.5), no shipment or POD (4.6), no item or catalogue (4.3), no
invoice (`accounting`) and no helpdesk (CRM).

### Models — 4, all new, nothing re-declared
| Model | Prefix | Notes |
|---|---|---|
| `PortalAccount` | `PAC-` | One row per customer `core.Party`. **NOT a login** — users bind via the shipped `crm.CustomerPortalAccess`. Entitlement booleans, `stock_display` (hidden/availability_text/band/exact_quantity), `catalog_scope` + `catalog_categories` M2M, `price_basis`, `default_ship_to`, notification prefs (**stored only, 4.16 dispatches nothing**). `unique_together` on `(tenant, customer)`. |
| `PortalOrderInquiry` | `PIQ-` | **WRAPS `crm.Case`** — thread/SLA/CSAT/ownership all reused. Adds supply-chain context + `outcome`. `case`, `outcome`, `resolved_at`, `return_authorization`, `source`, `raised_by` are `editable=False`. |
| `PortalDocumentShare` | `PDS-` | Six typed pointers, **exactly one** set. Expiring, revocable, download-audited `public_token`. |
| `PortalActivity` | — | Append-only customer **read** log. `TenantOwned`, every field `editable=False`, **list+detail only**. |

### The rules that bit during the build — read before changing anything
1. **`PortalAccount` create/edit are `@tenant_admin_required`** (like `_delete`, and like CRM's
   `customerportalaccess_create`). This row publishes AR balance, credit limit, invoice history and per-warehouse
   stock to an outsider — that is an IAM decision, not ordinary CRUD.
2. **`expires_at` and `revoked_at` are HALVES OF ONE CONTROL.** `portaldocumentshare_edit` is admin-gated to match
   `_revoke`; `expires_at` is **required on create**, optional on edit, so a member cannot mint a permanent link
   only an admin can kill.
3. **`CUSTOMER_VISIBLE_INVOICE_KIND` / `_STATUSES` live in `models/CustomerPortal/_choices.py`**, read by the
   profile page, the share form AND the download view. They were local to `Portal.py`, so only the page obeyed
   them and every seeded share pointed at a **draft credit note** the token happily served.
4. **`core.Document.classification == "confidential"` is refused** in the form queryset, `clean()` and
   `_target_still_owned`. Nothing in `apps/scm` read that column before.
5. **Same tenant ≠ same customer.** `PortalOrderInquiry.clean()` checks the counterparty on `sales_order` /
   `shipment` / `invoice`, not just the tenant. (Repo-wide: ~40 scm models tenant-check their FKs; 3 check a
   counterparty, all here.)
6. **`clean()` re-homes errors keyed on `editable=False` columns to `NON_FIELD_ERRORS`** — `add_error` on a field
   the form does not declare raises `ValueError`, i.e. a **500**. That is why `PortalInquiryCustomerForm` also
   drops `invoice_dispute` from its choices: it has no `invoice` picker by design.
7. **`portal_document_download` is the app's 2nd unauthenticated route.** Tenant off the **object**
   (`request.tenant` is `None` for an anonymous visitor), `tenant.is_active` + `portal_account.is_active` +
   `can_view_documents` re-checked, revoke/expiry enforced **inside the lookup**, ownership re-proved, streamed
   via `FileResponse` (never a `MEDIA_URL` redirect — `config/urls.py` serves it directly under `DEBUG`).
   `@require_GET`. Evidence is recorded **only for a real navigation** (`Sec-Fetch-Dest`), so a forced `<img>`
   load cannot forge a download row. **Needs per-IP rate limiting before it faces the internet.**
8. **`can_request_returns` is enforced in 4.10's `portal_return_create`**, not just hidden. A customer with **no**
   `PortalAccount` is still allowed there — that route predates 4.16 and must not regress.
9. **`ModelChoiceField.queryset` is also the VALIDATOR** — never slice it (`to_python` calls `.get()`, and Django
   refuses to filter a sliced query). That is why the inquiry pickers are uncapped.
10. `select_related` must follow the hop the target's `__str__` actually walks — `SalesOrderLine` → `item`,
    `SalesOrder` → `customer`, `Shipment` → nothing, `QualityInspection` → `item`. A **wrong** one raises
    `FieldError` when the widget iterates; a merely **useless** one is silent and costs a query per `<option>`.

### Routes (31) · alias `_cp_`
`portalaccount_*`, `portalorderinquiry_*` (+ `_resolve` / `_reopen` / `_raise_return`), `portaldocumentshare_*`
(+ `_revoke`), `portalactivity_list|_detail`, `portal_order_tracking`, `portal_catalog_preview`, and the gated
`portal_home` / `portal_order_list` / `portal_order_detail` / `portal_documents` / `portal_catalog` /
`portal_profile` / `portal_inquiry_create` / `portal_document_download`.
**4.10 already owns `return_portal` and `portal_return_create`** — the `scm:` namespace is flat.

### Templates — `templates/scm/portal/`
Entity folders `portalaccount/ portalorderinquiry/ portaldocumentshare/ portalactivity/`; staff standalone
`order_tracking.html`, `catalog_preview.html`; the nine gated pages are `customer_*.html` so the split is obvious.
**`public_token` is rendered nowhere** except inside a download `href` on `customer_documents.html`.

### Seeder — `_seed_portal_tenant`
Three accounts: fully-enabled, restricted, and **`PAC-00003` deliberately EMPTY** (zero orders/documents/inquiries,
never logged in). That is not filler — a new portal customer's empty state is the **modal first session**, and no
smoke sweep in this repo had ever rendered an `{% empty %}` branch. Inquiries go through `open_for()`, the revoked
share through `revoke()`, activity through `record()`, so every run exercises the shipped path.

### Shared resolver
`_portal_account(request)` in `apps/scm/views/_helpers.py` → `(portal, refusal)`, exactly one non-None. Refuses at
each of three steps; **never falls through to an unscoped queryset**. 4.10's `_customer_portal_access` was promoted
into the same file.

## 4.17 Third-Party Logistics (3PL)  (`apps/scm/*/ThirdPartyLogistics/`, templates `templates/scm/3pl/`)

**Warehouse-as-a-service: billing the client for space and handling.** Two of its five NavERP bullets are
COMPUTED PAGES with no table, because segregation and rental are *questions about existing stock*, not new stock.
4.17 owns no item or ledger (4.3), no receipt (4.1), no pick (4.4), no shipment (4.6) and **no invoice**
(`accounting`) — it derives from all of them and stops at a DRAFT invoice.

### Models — 4 tenant-scoped + 2 tenant-less children
| Model | Prefix | Notes |
|---|---|---|
| `LogisticsClient` | `3PL-` | Commercial configuration on a customer `core.Party` — **never a second company table** (the `Carrier`/`SupplierProfile` posture). `billing_cycle`, `minimum_monthly_charge`, `space_model` (shared/dedicated/hybrid) + committed sqft/pallet positions, `storage_billing_method` (calendar / anniversary / split_month / average_daily / snapshot), self-FK `parent_client` for divisions. Integration block is **non-secret identifiers only** (`integration_mode`, `client_system`, `edi_partner_id`, `edi_qualifier`); `last_synced_at` is written by NOTHING here — it exists so 4.19 can. |
| `ClientRateCard` + `ClientRateCardLine` | `TAR-` | Versioned tariff, effective-range guarded, `activate`/`supersede` verbs. Line = `charge_category` × **14-value `charge_basis`**, free allowance, per-occurrence minimum, tier band, optional per-location/per-category rate, revenue `gl_account`. `rate` is `Decimal(14,4)`. |
| `ClientBillingRun` + `ClientBillingRunLine` | `CBR-` | Reviewable **worksheet** (Infoplus/CartonCloud posture), not an invoice. `calculate()` derives quantities from `StockMove`/`PutawayTask`/`PickTaskLine`/`SalesOrder`/`Shipment`, keeps manual lines, re-runs idempotently. `draft_invoice()` writes `accounting.Invoice(status="draft")` and **posts no JournalEntry** (L29). |
| `ClientSLA` | `SLA-` | Per-client metric target measured from operational rows by `recompute()`. Warning band, `breach_count`, graduated + **capped** service credits — **suggested only, nothing is auto-credited**. |

Plus additive nullable `owner_client` (SET_NULL) on **`Item`** and **`Location`**, indexed `(tenant, owner_client)`
in migration **0030** (`scm_item_tnt_owner_idx` / `scm_loc_tnt_owner_idx`).

### The rules that bit during the build — read before changing anything
1. **NEVER write `quantity`/`unit_price` into the drafted invoice.** `accounting.InvoiceLine.unit_price` is
   `Decimal(14,**2**)` and `save()` recomputes `line_total = quantity * unit_price`, while a rate is
   `Decimal(14,**4**)`. A `0.0450`/pallet-day storage rate silently becomes `0.05` — an ~11% over-bill. So
   `draft_invoice()` writes `quantity=1, unit_price=q2(line.amount)` and carries the real qty × rate in the
   **description**. Do not "improve" this back into the natural pair.
2. **No `owner_client` column on `StockMove`.** Client attribution derives through `item.owner_client`; an owner
   column on an append-only ledger is a second source of truth (L37).
3. **`GoodsReceiptLine` has NO `item` FK** — `PurchaseOrderLine` carries free-text `item_description`/`sku_hint`
   (the pre-catalogue L28 stand-in). Receipt→client attribution runs ONLY through
   `Q(putaway_tasks__item__owner_client=c) | Q(location__owner_client=c)`. Do not "restore" a `po_line`→`item` path.
4. **MANUAL_ONLY_BASES** (`per_sqft`, `per_cbm`, `per_kg`, `per_hour`, `per_carton`, `pct_of_value`) are priceable
   but **not measurable today** — `Item` has no weight or dimensions, `Location` has no area. Those lines get
   `quantity=0`, `needs_manual_quantity=True` and a description naming the missing measurement. **Never guess a
   conversion factor.** `per_pallet_position` bills stock units 1:1 and the line **says so** — a stated
   approximation, never a hidden one.
5. **Deleting a billing run is gated on `VOIDABLE_STATUSES`, not on `!= "invoiced"`.** An `approved` run carries a
   `@tenant_admin_required` `approved_by`/`approved_at` signature; letting a member delete it destroys the
   approval the model's own `void()` refuses to touch. The list template's Delete button uses the same gate — both
   places, or the button bounces.
6. **`recompute()` distinguishes `no_data` from meeting.** An empty window writes `status="no_data"` and leaves
   `last_measured_value` NULL (never `0`), so an unmeasurable period never reads as success.
7. **NO secret of any kind (L20)** — no API key, token, endpoint URL or EDI password. Credentials, transport and
   webhooks are **4.19's**.
8. **`_choices.py` is owned by `LogisticsClients.py`** and imported BY NAME in `models/__init__.py` — never
   `import *` (three sibling `_choices` modules are already star-imported; a fourth would shadow by import order).
9. **`ClientRateCard.status` IS on the header form** (deliberately — `clientratecard_edit` refuses any card outside
   `EDITABLE_RATE_CARD_STATUSES` and `clean()` re-runs the overlap guard). Only `ClientBillingRun.status` and
   `ClientSLA.status` are off their forms.

### Routes (36)
`logisticsclient_*`, `clientratecard_*` (+ `_activate` / `_supersede`) and `clientratecardline_*`,
`clientbillingrun_*` (+ `_calculate` / `_approve` / `_void` / `_draft_invoice`) and `clientbillingrunline_*`,
`clientsla_*` (+ `_recompute` / `_recompute_all`), plus the two COMPUTED reports `client_inventory_report` and
`client_space_report`.

### Templates — `templates/scm/3pl/`
Entity folders `logisticsclient/ clientratecard/ clientbillingrun/ clientsla/`, the two nested line forms
(`clientratecardline/form.html`, `clientbillingrunline/form.html`), and two standalone reports at the sub-module
root: `client_inventory_report.html`, `client_space_report.html`. The space report prints committed sqft/pallet
positions **beside** the summed `Location.capacity` of the client's dedicated bins, labelled "in each bin's own
units" — **no conversion between the two is invented**.

### Seeder — `_seed_3pl_tenant`
Guarded by `LogisticsClient.exists()`. Three clients — **dedicated**, **shared**, and one mid-**onboarding** — an
active + a draft + a shared rate card, an invoiced run, an open run and a shared run, and SLAs across metrics.
`--flush` deletes the drafted AR invoices before the runs and the runs before the PROTECTed rate cards.

## 4.18 Finance & Accounting Integration  (`apps/scm/*/FinanceIntegration/`, templates `templates/scm/finance/`)

**What we owe, what we are owed, and what a receipt actually cost to land.** THREE of its five NavERP bullets —
Accounts Payable, Accounts Receivable, Budgeting — are **READ-ONLY COMPUTED registers**, not tables: what we owe and
what we are owed already exist as POINTERS into `apps/accounting` from six shipped models (4.1 `GoodsReceiptNote.bill`,
4.6 `FreightInvoice.bill`, 4.18 `LandedCostVoucher.bill`; 4.5 `SalesOrder.invoice`, 4.17 `ClientBillingRun.invoice`,
4.10 `RMA.credit_note`), so an AP/AR/Budget table here would be a second copy of the same money that drifts the first
time Accounting voids something (L29). **SCM posts NO `JournalEntry`.** The sub-module's one and only accounting write
is `LandedCostVoucher.draft_bill()`, which creates a DRAFT `accounting.Bill` and **stops** — Accounting posts the
entry. Landed cost itself is an **ADDITIVE allocation layer over the append-only `StockMove` ledger** (4.3): it never
edits a move, it rolls `Item.average_cost` via `apply_landed_cost()` and records the uplift as its own rows.

### Models — 2 tenant-scoped + 2 children (`models/FinanceIntegration/`)
| Model | Prefix | Notes |
|---|---|---|
| `DutyTariff` | `DTY-` | The **customs duty master** — one effective-dated rate per `(tenant, hs_code, country_of_origin, effective_from)`. **`effective_from` is NEVER nullable** (a NULL member silently disables the unique key in MySQL — every NULL compares unequal). **Blank `country_of_origin` = "any origin"** catch-all, not "unknown". `rate_for(tenant, hs_code, origin, on_date)` resolves: active-only → window contains date (the `effective_to__isnull` leg carried explicitly) → **named origin beats the any-origin row** → newest `effective_from` first; returns `None`, never raises (it DEFAULTS a form field). `is_current` is a **computed property**, never a column. Exists because **`accounting.TaxCode` structurally cannot be a customs master** (no customs `tax_type`, no `hs_code`, no origin pair) — do NOT re-declare a sales-tax rate here; `tax_code` FK is the *recoverable import-VAT counterpart* only. `clean()` upper-cases/strips `hs_code` BEFORE `validate_unique`. |
| `LandedCostVoucher` | `LC-` | One receipt's landed cost. `goods_receipt` (**`scm.GoodsReceiptNote`**, **PROTECT** — the evidence), `party` (**`core.Party`**, **PROTECT, required** — the payee, because `accounting.Bill.party` is non-null PROTECT), `shipment`/`trade_document` (SET_NULL, 4.6/4.12), `currency` (**`accounting.Currency`** — a GLOBAL model with no tenant column, so `TenantModelForm` cannot scope it and `_active_currencies()` narrows it by hand instead), `bill` (**`accounting.Bill`**, SET_NULL, **`editable=False`** — `draft_bill()` is its only writer). **Typed, not derived:** required `cost_date` (the date the charges were incurred), the `allocation_basis` below, and free-text `notes` — the form carries **no money at all**. Status ladder **draft → allocated → accrued → reconciled** (+ `cancelled`); `EDITABLE_STATUSES=("draft",)` and only while `bill is None`. `allocation_basis`: value / quantity / weight / volume / equal (**no `manual`** — deferred, not half-shipped). All derived money (`estimated_total`/`actual_total`/`variance_amount`/`variance_pct`/`allocated_total`) is `editable=False` and `recalc_totals()` is their only writer; `accrued_at` is also `editable=False` but is stamped by `accrue()` and cleared by `allocate()`. Verb ladder `allocate() → accrue() → draft_bill()` + `cancel()`; **`allocate()` is idempotent** — it reverses its prior average-cost roll first (ruling 5) and clears `accrued_at` when re-allocation demotes an accrued voucher. Allocation base = `receipt_moves()` (inbound `StockMove` `quantity > 0`, which excludes the compensating negatives a cancelled GRN leaves in the append-only ledger). |
| `LandedCostCharge` | — | **Tenant-LESS child** (reached via `voucher.tenant`, the `FreightInvoiceLine`/`BillLine` convention). One cost line: `charge_type` (**11 values** — freight/duty/brokerage/insurance/handling/drayage/port_fees/fuel_surcharge/inspection/storage/other), `description`, `estimated_amount`/`actual_amount`, `allocation_basis` (blank INHERITS the voucher's via `effective_basis`), `gl_account` (**`accounting.GLAccount`**, SET_NULL — the expense account `draft_bill()` copies onto the vendor bill line), `tax_code` (**`accounting.TaxCode`**, SET_NULL — the recoverable import-VAT counterpart, never a customs rate), `is_recoverable` (recoverable tax NEVER capitalises), `capitalise_to_inventory`. **Two POINTER columns, both on the form whitelist and therefore user-facing:** `party` (**`core.Party`**, SET_NULL) is the vendor for THIS line when it differs from the voucher's payee (the broker's fee on a forwarder's voucher) — and it is **load-bearing**, not decoration: `split_charges()` returns `(billable, excluded)` and **EXCLUDES every charge naming a party other than the voucher's payee** from the drafted bill, and `draft_bill()` **REFUSES OUTRIGHT** when that leaves nothing billable ("every charge names a different vendor"). Multi-vendor auto-split is deferred and named, so it refuses rather than quietly invoicing the forwarder for the broker's fee — **that refusal is the first thing to check when `draft_bill()` throws.** `freight_invoice` (**`scm.FreightInvoice`**, SET_NULL) is the 4.6 audited carrier invoice this charge came from — **the carrier-bill↔landed-cost link already exists here**; do not add a second one (4.6's `FreightInvoice.bill` is the separate *AP* pointer). **Snapshots** `hs_code`/`country_of_origin`/`duty_rate_pct` from `DutyTariff` at entry — never a live join, so a re-rated tariff can't restate a costed shipment. `clean()` refuses a duty rate on a non-`duty` charge. `allocatable_amount` = actual if > 0 else estimate; `capitalises` = capitalise AND not recoverable. |
| `LandedCostAllocation` | — | One charge's share of one receipt move. **Carries its OWN `tenant`** — the deliberate exception to the tenant-less-child rule, because the 4.3 valuation report and the 4.18 variance report query these rows DIRECTLY grouped by `stock_move`/`item` (the three `(tenant, …)` indexes serve exactly those queries). Every **DERIVED** column (`quantity`/`basis_value`/`basis_used`/`allocated_amount`/`unit_cost_uplift`) is `editable=False`; the four FKs `voucher`/`charge`/`stock_move`/`item` and the inherited `tenant`/timestamps are ordinary fields, and what actually keeps them unwritten is that **no form points at the model** — there is deliberately no form, view, list or url. **`allocate()` is the only writer.** Rendered inside the voucher detail page and the variance report; admin is READ-ONLY. `stock_move`/`item` are PROTECT; `item` is denormalised off the move so the reports never join through the ledger. |

Migration **0031**. **Deferred index (review M3):** a `(tenant, party)` index on `LandedCostVoucher` was skipped —
0031 was the number claimed in a shared checkout, and 4.17 deferred its own index finding the same way, so both belong
in a later **app-wide index-sweep migration**, not a one-off 0032.

### The rules that bit during the build — read before changing anything
1. **Backend package `FinanceIntegration/` ↔ template folder `templates/scm/finance/` — the asymmetry IS the house
   rule.** Every shipped scm template folder uses a short slug while the Python package uses the NavERP.md
   sub-module title in PascalCase (`ThirdPartyLogistics/` ↔ `3pl/`, `CustomerPortal/` ↔ `portal/`). **Do NOT "fix"
   `finance/` into `financeintegration/`.** State the rule without a count — a hard-coded number of template folders
   goes stale the moment the next sub-module ships one.
2. **`draft_bill()` is a DRAFT and the only accounting write.** SET_NULL on `bill` so voiding the bill in accounting
   can't cascade a voucher — and the inventory value it justifies — out of existence. Never make 4.18 post a
   `JournalEntry`.
3. **`DutyTariff.rate_for()` DEFAULTS, it does not restate.** The number is snapshotted onto `LandedCostCharge`;
   correcting a tariff tomorrow must never rewrite what a receipt was costed at today. `LandedCostChargeForm.clean()`
   calls `rate_for()` only for a **customs charge that carries an `hs_code`**, and never overwrites a rate the user
   typed.
4. **A blank `country_of_origin` is the any-origin fallback, not a wildcard alternative** — `rate_for` tries the named
   origin first (`__iexact`) and the blank row only on a miss. Both can legitimately coexist for one HS code on one day.
5. **The charge route split is a security decision.** `landed-cost-vouchers/<int:pk>/charges/add/` nests the create
   under the PARENT (the voucher comes from the ROUTE, never a POST-body pk — the graft-onto-another-workspace vector);
   `edit`/`delete` take the CHARGE's own pk. All scoped through `voucher__tenant=request.tenant` regardless.
6. **The FULL gating map — SEVEN POST-only routes, and only four of them are admin-gated.** A GET on any of the
   seven is a **405**, not a silent state change, which is exactly what `test_finance_security.py` asserts.
   * the four **money-committing verbs** `landedcostvoucher_allocate` / `_accrue` / `_draft_bill` / `_cancel` —
     `@tenant_admin_required @require_POST`;
   * the three **deletes** `landedcostvoucher_delete`, `landedcostcharge_delete`, `dutytariff_delete` —
     `@login_required @require_POST`: POST-only but **MEMBER-PERMITTED, with no admin gate**. That is a deliberate
     divergence from the sibling precedent where 4.13's `asset_delete` IS `@tenant_admin_required`;
   * every list / detail / create / edit page — voucher, charge (`landedcostcharge_create`/`_edit`) and tariff — is
     plain `@login_required`; a GET renders the form;
   * the four report pages are `@login_required` STAFF pages, read-only, no `@require_POST`.

   So in the templates: the **four verb buttons** need `{% if request.user.is_superuser or request.user.is_tenant_admin %}`,
   and the **three Delete buttons must NOT** — gating them hides an action ordinary members legitimately have, and
   their un-gated state is a documented decision rather than a security defect to file.
7. **A purely-recoverable or purely-expensed voucher must still reach AP** — `draft_bill()`/the ladder must not assume
   every voucher capitalises; the "Draft the bill" button shows even on a voucher that can never be allocated.

### Routes  (`urls/FinanceIntegration/`, `app_name="scm"`)
`landedcostvoucher_*` (list/create/detail/edit/delete) **+ the verb ladder** `_allocate` / `_accrue` / `_draft_bill` /
`_cancel`; `landedcostcharge_create` (nested under the voucher) + `landedcostcharge_edit` / `_delete` (own pk);
`dutytariff_*` (plain CRUD, no verbs — a master, not a document); and **four COMPUTED reports**
`finance_payables` / `finance_receivables` / `finance_budget_variance` / `landed_cost_variance`. No greedy
`<str:…>` route (4.10's `return-tracking/<str:token>/` and 4.16's `portal-documents/<str:token>/` remain the app's
only two). `LandedCostAllocation` has **no url** — it renders inside the voucher detail and the variance report.

### Templates — `templates/scm/finance/`
Entity folders `dutytariff/` (list/detail/form) and `landedcostvoucher/` (list/detail/form), the nested line form
`landedcostcharge/form.html`, and **four standalone report pages** at the sub-module root: `payables.html`,
`receivables.html`, `budget_variance.html`, `landed_cost_variance.html`. The voucher detail page hosts the charge grid
and the derived allocation grid; an unallocatable per-unit uplift renders as `None`, not `0`.

### Seeder — `_seed_finance_tenant`  (runs LAST in `handle()`, after 4.17)
Guarded by `LandedCostVoucher.exists()`. **Invents no master data** — every party, item, GL account, tax code,
currency, shipment, freight invoice and customs document is found among rows earlier passes seeded; an optional link
whose subject is absent is left null. **It does, however, WRITE THE STOCK LEDGER, and that is the pass's biggest side
effect:** when the chosen `received` GRN has no `receipt` `StockMove`s, it posts them through the **real
`_post_grn_receipt` helper** — the same function `goodsreceipt_receive` calls from the UI — inside
`transaction.atomic()`, so the inbound cost layers and the weighted-average roll follow the app's own path rather
than a seeder's copy of it. That deliberately closes **4.1's documented gap**: 4.1 books its GRN `received` without
posting stock because it runs *before* `_seed_inventory_tenant` (no item master, no location to post against), while
this pass runs LAST and the PO lines' `sku_hint`s are the exact SKUs 4.3 seeds. It is guarded by the same
`exists()` check the flush filter describes, so a second run posts nothing. **It also returns early and seeds ZERO
vouchers in four cases**, each with its own WARNING: no `received` GRN at all; the receipt post came back *blocked*;
the post matched *no item*; or there is **no supplier/vendor/partner party** (the drafted bill's `party` is PROTECT
and required, and this pass creates no party). Sets `weight_kg`/`volume_cbm` on three SKUs (`WS-16`, `MON-27`, `DOCK-C`) **only
where NULL** so allocate-by-weight/volume don't silently fall back to quantity. Two `DutyTariff` rows (an any-origin
fallback **and** an origin-specific row — the pair IS the `rate_for` demo). Two `LandedCostVoucher`s: one run all the
way through the REAL `allocate()` → `draft_bill()` path (so the rounding remainder, `_unallocate()` and the `BillLine`
precision rules are exercised on every seed), the second **left in DRAFT on purpose** — the ordinary first state, which
is what makes the estimate-only path and the "Allocate" button visible in the demo. `--flush` deletes the whole
allocation → charge → voucher tree BEFORE 4.1's `GoodsReceiptNote` (PROTECT) and any party cleanup; there is no
`JournalEntry` to unwind.

## Conventions & gotchas

- **Every view filters `tenant=request.tenant`**; `crud_*` helpers in `apps/core/crud.py` do this for you.
- **Child dropdown scoping**: `PurchaseOrderLine`/`RFQLine` have NO tenant field, so `TenantModelForm` can't scope
  them — they're hand-scoped to the parent via `_scope_to_parent` (forms) / a formset that threads the parent through
  `get_form_kwargs`. Never point a dropdown at an unscoped child queryset.
- **Formset prefix is `lines-`** (and `vendors-` on the RFQ view), NOT `form-` — the line children declare
  `related_name="lines"`, so `BaseInlineFormSet.get_default_prefix()` returns `lines`.
- **Formset delete guards**: removing a `PurchaseOrderLine` with a receipt, or an `RFQLine` a supplier priced, raises
  a formset `ValidationError` (not a 500) — see `BasePurchaseOrderLineFormSet`/`BaseRFQLineFormSet`.
- **Audit**: hand-rolled form views bypass `crud_edit`, so they pass `_changed(form)` (imported explicitly from
  `apps.scm.views._common` — `import *` skips underscore names) to `write_audit_log` to keep the field diff.
- **Status/number/version/totals/match_status are never form fields** — advanced only by their actions.
- **Match on NET value** (bill subtotal), and **admin-gate any action that commits/breaks money** (see Authorization).

## Common tasks

- **Add a field to an entity**: edit its `models/ProcurementManagement/<Entity>.py`, add to the form's `Meta.fields`
  (unless derived/system-set), surface in `detail.html`/`form.html`, `makemigrations scm && migrate`.
- **Add a new model + CRUD**: new `<Entity>.py` in each of models/forms/views/urls under `ProcurementManagement/`,
  re-export from **every** package `__init__.py`, templates under `templates/scm/procurement/<entity>/`, register in
  `admin.py`, extend `seed_scm`. (A whole new sub-module 4.M gets its own `<SubModule>/` folder — use `/next-module`.)
- **Add a list filter**: pass the choice/queryset in the view's `crud_list(extra_context=...)` and add a
  `(param, lookup, is_int)` tuple to `filters=`; in the template reflect `request.GET` (pk filters use
  `|stringformat:"d"`).
- **Extend the seeder**: add rows inside the per-tenant guard in `seed_scm.py`, reusing existing Party/OrgUnit rows.
- **Verify**: `venv/Scripts/python.exe -m pytest apps/scm/tests -q` (2,761 tests). Ad-hoc smoke scripts live in `temp/`.

## Sidebar wiring  (`apps/core/navigation.py`)

`LIVE_LINKS["4.1"]` maps 4.1's NavERP.md bullets → live pages:
Purchase Requisition→`scm:requisition_list`, Request for Quotation→`scm:rfq_list`,
Purchase Order Management→`scm:purchaseorder_list`, Vendor Portal→`scm:purchaseorder_list?status=sent`
(staff-side, no vendor login — L32), Invoice Reconciliation→`scm:goodsreceipt_list`.
`LIVE_LINKS["4.2"]`–`["4.7"]` map each of those sub-modules' bullets the same way; **`LIVE_LINKS["4.6"]`** →
Route Planning + Load Optimization both `scm:load_list` (two facets of the load, they co-highlight),
Freight Audit & Payment `scm:freightinvoice_list`, Carrier Management `scm:carrier_list`,
Shipment Tracking `scm:shipment_list`. **`LIVE_LINKS["4.7"]`** → Sales Forecasting
`scm:demandforecast_list`, Seasonality Analysis `scm:seasonalityprofile_list`, Demand Sensing
`scm:demandsignal_list`, Collaborative Planning `scm:forecastadjustment_list` (the FULL list, not
`?status=proposed` — the queue is a chip on that page and filtering the nav entry would hide the
accepted/rejected history), Safety Stock Calculation **`scm:safety_stock_report`** (a computed REPORT,
the `scm:reorder_alerts`/`scm:valuation_report` precedent that a bullet need not be a CRUD list).
**`LIVE_LINKS["4.8"]`** → Bill of Materials (BOM) `scm:billofmaterials_list`, Production Scheduling
`scm:production_schedule`, Work Order Management `scm:workorder_list`, Material Resource Planning (MRP)
`scm:mrp_report`, Shop Floor Control **`scm:productiontimelog_list`** (the time-log list, NOT the work-centre
master — the bullet is about *tracking* machine time, labour time and progress, which is what the log records;
centres are reachable from it and from the schedule board).
**`LIVE_LINKS["4.15"]`** → Temperature Monitoring `scm:coldchainmonitor_list` (the MONITOR register, **not**
the reading ledger — an append-only log takes no bullet of its own, the `MeterReading` precedent),
Excursion Management `scm:temperatureexcursion_list`, and **three COMPUTED pages**: Cold Storage Inventory
`scm:cold_storage_report` (4.3 filtered — on-hand from the `StockMove` ledger, mismatch from the two
`storage_condition` columns disagreeing, expiry/quarantine from `LotSerial`), Compliance Reporting
`scm:cold_chain_compliance_report`, Maintenance of Reefers `scm:reefer_board` (a board over **4.13**;
4.15 declares zero maintenance entities). `resolve_nav()` renders exactly five leaves under 4.15 — a sixth
would mean a key drifted from its NavERP.md bullet, which is the cheapest check that the mapping is honest.

**`LIVE_LINKS["4.11"]`** → all five bullets are COMPUTED pages, the `safety_stock_report` precedent taken to
its conclusion: Inventory Dashboards `scm:inventory_analytics`, Procurement Analytics `scm:spend_analytics`,
Logistics KPIs `scm:logistics_kpis`, Financial Reporting `scm:margin_analytics` (operational, NOT the ledger),
Predictive Analytics `scm:disruption_risk`. **None of 4.11's three models takes a sidebar key** — `KpiTarget`
and `KpiSnapshot` are masters reached from the analytics pages (the `InspectionPlan`/`WorkCenter`/`ReorderRule`/
`ReturnReason` precedent) and the alert inbox is reached from the open-count chip every report page carries.
**`LIVE_LINKS["4.12"]`** -> Contract Repository **`scm:contract_list`** (4.2's EXISTING list, extended - the
4.4->4.3 `scm:location_list` precedent, NOT a second contract table), Compliance Tracking
`scm:compliancerequirement_list`, Trade Documentation `scm:tradedocument_list`, License Management
`scm:tradelicense_list`, Sustainability Tracking `scm:sustainabilityassessment_list`. The **carbon report is
NOT a sixth key** - 4.12 has five NavERP.md bullets and the sidebar mirrors that file exactly, so
`scm:carbon_footprint_report` is reached from a chip in the Sustainability list header.
**`LIVE_LINKS["4.13"]`** → Asset Registry `scm:asset_list`, Preventive Maintenance
`scm:maintenanceplan_list`, Breakdown Maintenance **`scm:maintenanceworkorder_list`** (4.13's MWO list,
NOT 4.8's `scm:workorder_list` — see non-negotiable 1), Spare Parts Inventory **`scm:sparepart_list`**
(a COMPUTED page over 4.3 — no `SparePart` table; the 4.4→4.3 `scm:location_list` and 4.12→4.2
`scm:contract_list` precedent), Asset Depreciation **`scm:asset_depreciation_report`** (COMPUTED over
`accounting.FixedAsset`). **No sidebar key for `MeterReading`, `AssetSparePart`,
`MaintenanceWorkOrderPart` or `MaintenanceWorkOrderTask`** — 4.13 has five NavERP.md bullets and the
sidebar mirrors that file exactly; the reading log is reached from the asset's meter panel and from
`scm:meterreading_list`, and the three children are panels on their parent's detail page (the
`WorkCenter`/`ReorderRule`/`ReturnReason`/`InspectionPlan` precedent). The PM forecast board
(`scm:pm_forecast`) is likewise a chip in the Preventive Maintenance list header, not a sixth key.
**`LIVE_LINKS["4.14"]`** → Labor Planning `scm:laborplan_list`, Time & Attendance
**`scm:laborsession_list`** (the warehouse SHIFT, *not* an attendance table — HRM owns
`hrm.AttendanceRecord` and `apps/scm` holds zero `hrm.*` references), Task Assignment
**`scm:labor_board`** (a COMPUTED console over 4.4's EXISTING `assigned_to` — 4.14 declares no task
table and adds no assignee column; migration `0024` has no `AddField` at all), Performance Tracking
**`scm:laborstandard_list`** (the standards library, because units-per-hour with nothing to compare
against is trivia — the scorecard hangs off a header chip, the `pm_forecast` precedent), Payroll
Integration **`scm:labor_payroll_export`** (a read-only CSV hand-off that writes nothing;
`accounting.PayrollRun` is a whole-company accrual with no employee lines, so drafting one would be
*wrong* rather than redundant). **No sidebar key for `LaborActivity` or `LaborPlanLine`** — five
NavERP.md bullets, five keys. Note `scm:labor_scorecard` is `@tenant_admin_required` while the
payroll export is NOT: the export is a sidebar destination and `resolve_nav` has no per-link
permission concept, so it stays reachable and narrows its rows to the acting worker instead (L32).

**4.16** — `Order Tracking` → `scm:portal_order_tracking` (COMPUTED join of 4.5 + 4.6, no table),
`Account Management` → `scm:portalaccount_list`, `Document Retrieval` → `scm:portaldocumentshare_list`,
`Support Ticketing` → `scm:portalorderinquiry_list`, `Catalog Browsing` → `scm:portal_catalog_preview` (staff
render-as preview). **All five are STAFF pages (L32)** — the sidebar IS the staff application, and a staff user has
no `crm.CustomerPortalAccess`, so a bullet pointing at a gated customer page would refuse the person clicking it.
The gated surface is reached by CUSTOMERS at `/scm/portal/`. **No key for `PortalActivity`** — five NavERP.md
bullets, five keys; the log is a panel on the account detail page.

**`LIVE_LINKS["4.17"]`** → Client Billing `scm:clientbillingrun_list` (the ledger-derived worksheet that stops at
a DRAFT `accounting.Invoice`), Client Inventory Segregation **`scm:client_inventory_report`** (COMPUTED over
`Item.owner_client` + `StockMove` — no table), SLA Management `scm:clientsla_list` (`recompute()` derives the
achievement, it is never typed), Client Integration **`scm:logisticsclient_list`** (the EDI/API field block lives
ON the client master — there is no sync console to point at, and inventing a dead link is worse than pointing at
the real thing, L32), Warehouse Rental Management **`scm:client_space_report`** (COMPUTED — committed space beside
the client's reserved bins). **No key for `ClientRateCard`** or either line child — five NavERP.md bullets, five
keys; the rate card is the pricing a billing run is calculated against and is reached from the client detail page,
the billing-run list and the client list.

**`LIVE_LINKS["4.18"]`** → Accounts Payable **`scm:finance_payables`**, Accounts Receivable
**`scm:finance_receivables`**, Landed Cost Calculation `scm:landedcostvoucher_list`, Budgeting
**`scm:finance_budget_variance`**, Tax Management `scm:dutytariff_list`. **THREE of the five are READ-ONLY COMPUTED
registers over pointers, not tables** — payables reads 4.1 `GoodsReceiptNote.bill` + 4.6 `FreightInvoice.bill` +
4.18 `LandedCostVoucher.bill`; receivables reads 4.5 `SalesOrder.invoice` + 4.17 `ClientBillingRun.invoice` +
4.10 `ReturnAuthorization.credit_note`; budgeting is computed over `accounting.BudgetLine.org_unit` against PR/PO
commitments and freight + landed actuals. An AP, AR or Budget table here would be a second copy of the same money
that drifts the first time Accounting voids something (L29). Landed Cost Calculation is the one genuinely new
capability, and Tax Management is the **customs** master (HS code × origin) — sales/VAT/GST stays
`accounting.TaxCode`, FK'd from the charge line. **No key for `LandedCostCharge`, `LandedCostAllocation` or the
landed-cost variance report `scm:landed_cost_variance`** — five NavERP.md bullets, five keys; the charges and the
derived allocations are panels on the voucher detail page and the variance report is reached from there (the
`ClientRateCardLine` / `ReorderRule` / `ReturnReason` / `MeterReading` rule).

`MODULE_ICONS[4]` = `"truck"` (already set). A new sub-module adds ONE `LIVE_LINKS["4.M"]` entry — don't touch others.
