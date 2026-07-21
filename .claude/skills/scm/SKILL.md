---
name: scm
description: Work on the SCM module (Module 4 — Supply Chain Management). As-built = 4.1 Procurement Management (requisitions, RFQs + quote comparison, purchase orders, goods receipts + three-way match) 4.2 Supplier Relationship Management (onboarding, signal-derived scorecards, contracts, catalogs, risk), 4.3 Inventory Management (the append-only StockMove ledger with derived on-hand, items/locations/lots, transfers, adjustments, reorder automation, FIFO/LIFO/WAC valuation), 4.4 Warehouse Management (putaway, wave/batch/zone picking + packing, cycle counting, yard), 4.5 Order Management (sales orders, credit/fraud validation, soft allocation, backorders, quote-to-order), and 4.6 Transportation Management (carrier master + rate cards + derived on-time scorecard, loads + route stops + cube utilization, shipments + append-only tracking events + POD, freight audit → draft accounting.Bill). Use when the user asks to add/change/debug anything under apps/scm or templates/scm, extend the seed_scm seeder, touch SCM sidebar wiring (LIVE_LINKS 4.x), build the next SCM sub-module (4.7+), or invokes /scm.
---

# SCM — Supply Chain Management (Module 4)

App path: `apps/scm`. Templates: `templates/scm/`. URL prefix: `/scm/`, `app_name = "scm"`.
Mirrors `NavERP.md` "## 4. Supply Chain Management (SCM)" (19 sub-modules, 4.1–4.19).

**As-built: 4.1 Procurement + 4.2 SRM + 4.3 Inventory + 4.4 Warehouse Management + 4.5 Order Management +
4.6 Transportation Management.** 4.7–4.19 are roadmap. Build the next one with `/next-module` (it takes the lowest
`4.M` without a `LIVE_LINKS["4.M"]` entry — **4.7 Demand Planning & Forecasting** is next) — see the reference apps
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
- **Verify**: `venv/Scripts/python.exe -m pytest apps/scm/tests -q` (1,343 tests). Ad-hoc smoke scripts live in `temp/`.

## Sidebar wiring  (`apps/core/navigation.py`)

`LIVE_LINKS["4.1"]` maps 4.1's NavERP.md bullets → live pages:
Purchase Requisition→`scm:requisition_list`, Request for Quotation→`scm:rfq_list`,
Purchase Order Management→`scm:purchaseorder_list`, Vendor Portal→`scm:purchaseorder_list?status=sent`
(staff-side, no vendor login — L32), Invoice Reconciliation→`scm:goodsreceipt_list`.
`LIVE_LINKS["4.2"]`–`["4.6"]` map each of those sub-modules' bullets the same way; **`LIVE_LINKS["4.6"]`** →
Route Planning + Load Optimization both `scm:load_list` (two facets of the load, they co-highlight),
Freight Audit & Payment `scm:freightinvoice_list`, Carrier Management `scm:carrier_list`,
Shipment Tracking `scm:shipment_list`.
`MODULE_ICONS[4]` = `"truck"` (already set). A new sub-module adds ONE `LIVE_LINKS["4.M"]` entry — don't touch others.
