---
name: scm
description: Work on the SCM module (Module 4 — Supply Chain Management). As-built = 4.1 Procurement Management (requisitions, RFQs + quote comparison, purchase orders, goods receipts + three-way match) 4.2 Supplier Relationship Management (onboarding, signal-derived scorecards, contracts, catalogs, risk), 4.3 Inventory Management (the append-only StockMove ledger with derived on-hand, items/locations/lots, transfers, adjustments, reorder automation, FIFO/LIFO/WAC valuation), 4.4 Warehouse Management (putaway, wave/batch/zone picking + packing, cycle counting, yard), 4.5 Order Management (sales orders, credit/fraud validation, soft allocation, backorders, quote-to-order), 4.6 Transportation Management (carrier master + rate cards + derived on-time scorecard, loads + route stops + cube utilization, shipments + append-only tracking events + POD, freight audit → draft accounting.Bill), and 4.7 Demand Planning & Forecasting (statistical forecasts over DERIVED sales history with a decomposition waterfall, seasonality/promotion index curves, demand-sensing signals with a working order-surge detector, consensus adjustments, and a compute-then-apply safety-stock calculator on 4.3's ReorderRule), 4.8 Manufacturing / Production (versioned multi-level bills of materials with a cycle-guarded explosion, work centres with derived capacity/OEE, the work-order lifecycle posting component consumption and finished-goods production through 4.3's append-only ledger under new consumption/production move types, ledger-derived WIP costing, an MRP netting report and an infinite-capacity schedule board), and 4.9 Quality Management System (reusable inspection plans, inspections at the receipt/in-process/shipment trigger points with snapshotted results and a usage decision held separate from pass/fail, non-conformance reports with MRB dispositions where only a scrap moves stock, CAPA with effectiveness verification, audits whose findings ARE non-conformances, and generated certificates of analysis that are refused rather than issued off-spec). Use when the user asks to add/change/debug anything under apps/scm or templates/scm, extend the seed_scm seeder, touch SCM sidebar wiring (LIVE_LINKS 4.x), build the next SCM sub-module (4.10+), or invokes /scm.
---

# SCM — Supply Chain Management (Module 4)

App path: `apps/scm`. Templates: `templates/scm/`. URL prefix: `/scm/`, `app_name = "scm"`.
Mirrors `NavERP.md` "## 4. Supply Chain Management (SCM)" (19 sub-modules, 4.1–4.19).

**As-built: 4.1 Procurement + 4.2 SRM + 4.3 Inventory + 4.4 Warehouse Management + 4.5 Order Management +
4.6 Transportation Management + 4.7 Demand Planning & Forecasting + 4.8 Manufacturing / Production + 4.9 Quality Management.** 4.10–4.19 are
roadmap. Build the next one with `/next-module` (it takes the lowest `4.M` without a `LIVE_LINKS["4.M"]` entry —
**4.10 Returns Management (Reverse Logistics)** is next) — see the reference apps
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
`MODULE_ICONS[4]` = `"truck"` (already set). A new sub-module adds ONE `LIVE_LINKS["4.M"]` entry — don't touch others.
