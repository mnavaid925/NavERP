---
name: scm
description: Work on the SCM module (Module 4 — Supply Chain Management). As-built = 4.1 Procurement Management (requisitions, RFQs + quote comparison, purchase orders, goods receipts + three-way match) 4.2 Supplier Relationship Management (onboarding, signal-derived scorecards, contracts, catalogs, risk), 4.3 Inventory Management (the append-only StockMove ledger with derived on-hand, items/locations/lots, transfers, adjustments, reorder automation, FIFO/LIFO/WAC valuation), and 4.4 Warehouse Management (putaway, wave/batch/zone picking + packing, cycle counting, yard). Use when the user asks to add/change/debug anything under apps/scm or templates/scm, extend the seed_scm seeder, touch SCM sidebar wiring (LIVE_LINKS 4.x), build the next SCM sub-module (4.5+), or invokes /scm.
---

# SCM — Supply Chain Management (Module 4)

App path: `apps/scm`. Templates: `templates/scm/`. URL prefix: `/scm/`, `app_name = "scm"`.
Mirrors `NavERP.md` "## 4. Supply Chain Management (SCM)" (19 sub-modules, 4.1–4.19).

**As-built: 4.1 Procurement + 4.2 SRM + 4.3 Inventory + 4.4 Warehouse Management.** 4.5–4.19 are roadmap.
Build the next one with `/next-module` (it takes the lowest `4.M` without a `LIVE_LINKS["4.M"]` entry) — see the
reference apps `apps/crm`/`apps/accounting` for the package layout and the mandatory
[Module Creation Sequence](../../CLAUDE.md). **4.5 OMS is next**; note `SalesOrder` (Module 8) does not exist, so
it will need the same ships-first stand-in decision 4.1/4.3 made (L28/L29/L36/L37).

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
- **Verify**: `venv/Scripts/python.exe -m pytest apps/scm -q` (167 tests). Ad-hoc smoke scripts live in `temp/`.

## Sidebar wiring  (`apps/core/navigation.py`)

`LIVE_LINKS["4.1"]` maps 4.1's NavERP.md bullets → live pages:
Purchase Requisition→`scm:requisition_list`, Request for Quotation→`scm:rfq_list`,
Purchase Order Management→`scm:purchaseorder_list`, Vendor Portal→`scm:purchaseorder_list?status=sent`
(staff-side, no vendor login — L32), Invoice Reconciliation→`scm:goodsreceipt_list`.
`MODULE_ICONS[4]` = `"truck"` (already set). A new sub-module adds ONE `LIVE_LINKS["4.M"]` entry — don't touch others.
