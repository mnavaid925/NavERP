---
name: inventory
description: Work on the Inventory Management System module (Module 5 â€” 5.1 Product & Catalog, 5.2 Vendor/Supplier Management, 5.3 Purchase Order Management, 5.5 Warehousing & Bins, 5.6 Inventory Tracking & Control, 5.7 Stock Movement & Transfers, 5.8 Lot & Serial Number Tracking, 5.11 Stocktaking & Cycle Counting; 5.4 Receiving and 5.10 Returns landed in a shared checkout). Extends apps/inventory around the SCM 4.3 item/location/StockMove spines (L36 â€” never re-declares them). Use when the user asks to add/change/debug anything under apps/inventory or templates/inventory, extend the seed_inventory seeder, touch inventory sidebar wiring (LIVE_LINKS 5.x), or invokes /inventory.
---

# Inventory Management System (Module 5)

App: `apps/inventory` (registered as `apps.inventory`; url prefix `/inventory/`, `app_name = "inventory"`).
Backend AND templates follow the package layout: one `<SubModule>/` folder per NavERP sub-module
(`models/forms/views/urls` line up one-to-one), templates under `templates/inventory/<short-slug>/â€¦`.

## Ownership spine (L36/L29/L37 â€” read before ANY new model)

The item/stock masters belong to **SCM 4.3** (`apps/scm`): `scm.Item` (sku, costing_method
weighted_avg/fifo/lifo, cached `average_cost`, `on_hand()` ledger aggregate, `apply_receipt()`),
`scm.ItemCategory`, `scm.UOM`, `scm.Location` (warehouse/zone/bin self-FK tree + bin attributes),
`scm.LotSerial`, and the **append-only `scm.StockMove` ledger** (signed quantity; on-hand is ALWAYS
its aggregate â€” no editable quantity anywhere). POs are `scm.PurchaseOrder(Line)` (lines are the L28
free-text `item_description`/`sku_hint` stand-in, NOT an item FK). SO allocations are
`scm.SalesOrderAllocation` (active statuses reserved/released; lot-blind; its ATP check lives in the
FORM, never model.clean()). This app only adds the catalog/vendor/po-approval/warehousing/tracking
layers AROUND that spine, FK'ing by string (`"scm.Item"`, â€¦) with PROTECT on item/location.

## Sub-modules as built

| N.M | Package folder | Models (this app) | Notes |
|-----|----------------|-------------------|-------|
| 5.1 | `Catalog/` | ItemAttribute, ItemPrice, ProductFile | sidebar bullets "SKU Management"/"Product Categorization" point at `scm:item_list` / `scm:category_list` |
| 5.2 | `VendorSupplierManagement/` | VendorCommunication [VC-] | directory/scorecard/contract bullets point at 4.2 SRM pages |
| 5.3 | `PurchaseOrderManagement/` | PurchaseOrderApprovalRule, PurchaseOrderApproval, PurchaseOrderDispatch + `reorderdraft` computed page | creation/tracking point at spine PO pages |
| 5.4 | `ReceivingPutaway/` | PutawayRule (+ module-level `resolve_putaway_suggestion` resolver) + `putaway_suggestions` computed page | GRN/Three-Way-Matching/QC bullets point at `scm:goodsreceipt_list` ×2 + `scm:qualityinspection_list`; ZERO writes into SCM |
| 5.5 | `WarehousingBinManagement/` | BinCapacity, CrossDockOrder [XD-] (+ warehousemap computed page) | XD receive/ship/cancel posts real StockMove legs |
| 5.6 | `InventoryTrackingControl/` | StockStatus, InventoryReservation [RSV-] (+ stocklevels computed page) | valuation bullet points at `scm:valuation_report` |
| 5.7 | `StockMovementTransfers/` | TransferRoute, TransferApprovalRule, TransferApproval [TA-] (+ transfer_board / transfer_queue / transfer_panel pages) | movement documents stay `scm.StockTransfer`; spine grew pending_approval/approved statuses + nullable route FK (scm migration 0035) |
| 5.8 | `LotSerialTracking/` | LotNumberRule, ShelfLifePolicy (+ `fefo_board` / `traceability` computed pages) | lot/serial ROWS stay `scm.LotSerial` (Serial Number Tracking bullet points at the spine master); classify_lot is THE shared expiry verdict |
| 5.9 | `FulfillmentOrchestration/` | FulfillmentWave [WAV-], FulfillmentWaveOrder (+ `wave_board` computed page) | order/pick/ship/shipping bullets point at `scm:salesorder_list` / `scm:picktask_list` / `scm:carrier_list`; zero writes into SCM |
| 5.11 | `StocktakingCycleCounting/` | CountProgram [CTP-], PhysicalInventory [PHY-] (+ variance_report computed page) | count EXECUTION stays `scm.CycleCountTask`; Blind Counts bullet points at the spine master; reconcile() refuses while spawned sheets are open |
| 5.10 | `ReturnsManagement/` | ReturnInspection [RMI-], ReturnInspectionChecklist, DispositionRoutingRule (+ `returns_workbench` computed board) | Primary RMA documents and ledger postings stay in SCM 4.10 (L36/L29); 5.10 adds warehouse physical inspection grading checklists and automated disposition routing engine |

### 5.9 Order Management & Fulfillment — the wave-planning slice

- **One header + membership rows, zero SCM writes**: `FulfillmentWave` [WAV-#####] groups
  EXISTING `scm.SalesOrder`s for the floor — status planned→released→closed|cancelled is
  verb-driven (`release()` refuses zero-member waves; `close()`/`cancel()` stamp `closed_at`,
  cancel preserves `released_at` history), every verb a `select_for_update` + in-txn audit
  (CrossDockOrder pattern). `FulfillmentWaveOrder` (unique wave+SO, PROTECT) locks once the
  wave leaves planned.
- **None-honest progress**: `orders_fulfilled_count` counts only `FULFILLED_STATUSES`
  ("partially_fulfilled"/"fulfilled"/"invoiced"/"closed" — cancelled is never progress);
  `pick_progress_pct` rides the L28 TEXT CONVENTION `PickTask.wave_ref == wave.number`
  (indexed `scm_pik_tnt_wave_idx`; SCM's operator types the ref) and answers **None** when no
  picks reference the wave or all matched picks are cancelled.
- **Board first** (`inventory:wave_board`, `/inventory/waves-board/`): paginate-then-THREE
  grouped queries per page (members/fulfilled/pick stats merged in Python — flat ~20 queries
  total); stats trio `{open_waves, released_today, unassigned_orders}` where unassigned =
  fulfillable SOs absent from every wave via one NOT-IN subquery. List page mirrors the
  discipline: `member_count` annotation + shared `_pick_stats_by_ref()` merge (the review's
  N+1 finding).
- **Gating**: create/edit/delete/verbs/membership ALL `@tenant_admin_required` (C2 fix);
  duplicate membership is refused at the FORM with an `"__all__"` error because
  `validate_unique` skips the non-form `wave` field (C1 fix). Membership locks at model clean,
  form clean AND view pre-check.
- Tests: `test_fulfillment_{models,forms,views,security}.py` (82) + conftest fixtures
  `fulfillment_{loc_wave,carrier,so_open,so_second,wave_planned,wave_released,member,foreign_wave}_*`.

### 5.10 Returns Management (RMA) — the reverse-flow floor operations slice

- **Ownership & Core Integration (L36/L29)**: SCM 4.10 owns the primary customer RMA document (`scm.ReturnAuthorization` `[RMA-]`), return lines, receiving disposition ledger postings (`scm.ReturnDisposition`), return policies, and the accounting refund queue (`scm:refund_queue`). Module 5 extends this by adding the warehouse floor receiving inspection and automated disposition routing logic.
- **Physical Inspection (`ReturnInspection` [RMI-] & `ReturnInspectionChecklist`)**: Comprehensive warehouse inspection record capturing packaging integrity (intact/opened/damaged/missing), component completeness, functional testing verdict (pass/partial/fail/untested), cosmetic condition (new/minor_wear/heavy_wear/broken), assigned condition grade (A/B/C/D), serial number verification against authorization ticket, restock eligibility flag, recommended restocking fee percentage, and checklist checkpoints.
- **Disposition Routing Engine (`DispositionRoutingRule` & `resolve_disposition_routing`)**: Configurable rule engine mapping item SKU/category + condition grade to recommended disposition actions (restock, refurbish, scrap, donate, recycle, liquidate, return to vendor, quarantine) and suggested warehouse destination bins. Deterministic hierarchy: Specific Item (Tier 3) > Category (Tier 2) > Catch-all (Tier 1) → Grade Specificity → Priority ASC → ID ASC.
- **Warehouse Returns Workbench (`inventory:returns_workbench`)**: Real-time computed operational dashboard providing visibility over open RMAs, bench inventory, and automated disposition recommendations with one-click inspection creation.
- **Sidebar Wiring**: `LIVE_LINKS["5.10"]` maps RMA Ticket & Credit/Refund Processing to SCM 4.10 (`scm:returnauthorization_list` and `scm:refund_queue`), and Return Inspection & Disposition Routing to Inventory 5.10 (`inventory:returninspection_list` and `inventory:dispositionrule_list`).
- **Completion fixes (resume session)**: RMA-line prefill reads `ReturnLine.quantity_approved`
  (no `quantity_authorized` on the spine); inspection create drops the stray
  `formset.save_m2m()` (unsaved inline formset has none, no m2m anyway); audit rows use the
  `write_audit_log(user, obj, action, changes)` signature; templates carry only existing theme
  classes (`badge-slate` not the nonexistent `badge-purple`, `btn-sm` not `btn-xs`).
- Tests: `test_returns_{models,forms,views,security}.py` (17) + conftest fixtures
  `return_reason_{a,b}`, `rma_{a,b}`, `rma_line_{a,b}`, `disposition_rule_{a,b}`, `inspection_{a,b}`.
  Gotcha of record: `scm.ReturnLine` is TENANT-LESS with `quantity_requested`/`quantity_approved`
  and a REQUIRED `reason` FK; `scm.ReturnAuthorization` requires `requested_on` — fixtures must
  scope lines via `return_authorization__tenant`, never pass `tenant=`/`quantity_authorized=`.

### 5.4 Receiving & Putaway — the directed-putaway slice

- **One config table + one pure engine**: `PutawayRule` is a standing instruction (nullable
  `item` / `category` / `source_location` FKs onto the spine, required `destination`,
  `priority`, `is_active`, `notes`). Overlapping rules are LEGAL — no unique_together — because
  the deterministic resolver decides: specificity tier DESC (item=3 > category=2 > catch-all=1)
  → priority ASC → id ASC. A dual-pinned rule fires as item-tier ONLY; it never falls through
  to its category leg.
- **`resolve_putaway_suggestion(task, *, rules=None, by_pk=None, on_hand=None)`** returns
  `(suggestion|None, reason, candidates)` — `candidates[0]` IS the suggestion when non-empty;
  every refusal starts `"No Suggestion Found"` and never guesses a bin. Tier ladder after
  rules: consolidation on bins already holding the SKU → storage-condition match against the
  bin's own-or-inherited condition → walk-order fallback under the receipt's warehouse.
  Shared disqualifiers in every tier: inactive location, full bin (declared `capacity` only —
  blank = unlimited), owner_client conflict (4.17 semantics), candidate == staging location,
  and a top guard refusing tasks whose own item is foreign (M11).
- **The queue page** (`inventory:putaway_suggestions`) is a COMPUTED board over OPEN
  `scm.PutawayTask`s — zero writes into SCM; overrides happen via `scm:putawaytask_edit`.
  The view batch-preloads rules/locations/on-hand ONCE per request and passes them as kwargs
  (~7 app queries flat regardless of backlog; bare resolver calls stay self-loading for tests).
  Stats trio `{open_tasks, covered_by_rule, uncovered}` covers the FULL filtered set; rows carry
  `{task, receipt, item, staging, candidates, suggestion, suggestion_reason}`.
- **Writes are admin-gated** (`@tenant_admin_required` on create/edit/delete like 5.3's rules);
  list/detail stay member-readable with `is_admin` hiding affordances. Rule forms reject all
  four FK vectors cross-tenant via `_reject_foreign`; model `clean()` keys off `<name>_id` so an
  unset required FK renders "required" instead of 500ing (review finding C1).
- Tests: `test_receiving_{models,forms,views,security}.py` (78) + conftest fixtures
  `receiving_loc_*`, `receiving_rule_*`, `receiving_task_a`.

### 5.7 Stock Movement & Transfers â€” the governance slice

- **The spine grew, additively**: `scm.StockTransfer.STATUS_CHOICES` gained
  `pending_approval`/`approved` and a nullable `route â†’ inventory.TransferRoute` FK
  (SET_NULL, related_name="transfers"); `scm.stocktransfer_complete` accepts "approved"
  alongside "draft" â€” an ungoverned transfer still needs no sign-off, a governed one
  cannot be executed around its chain. max_length is 16 ("pending_approval" is 16 chars).
- **Board** (`inventory:transfer_board`, hand-rolled around `apps.core.crud.paginate`
  because rows carry COMPUTED context): classifies every movement LIVE into
  inter/intra by walking each location to its topmost ancestor (`_warehouse_roots`,
  one dict for the whole tree, cycle-guarded) â€” there is NO scope column anywhere.
  `?scope=inter|intra` pre-filters by pk set; unit totals + decision chains are ONE
  grouped query per page (`_units_map`, `_chain_map`). NOTE: `StockTransferLine` has NO
  tenant column â€” filter via `transfer__tenant`.
- **Submit** (`transfer_submit`, POST, login-gated â€” requesting is everyone's job,
  authorizing is not): draft â†’ pending_approval; optional `route` validated with
  `as_db_int` + `route.covers(from,to)`; refuses lineless drafts.
- **Queue** (`inventory:transfer_queue`) mirrors the 5.3 PO queue: rule resolved live per
  movement (`TransferApprovalRule.resolve_from(rules, total_units, scope)`, half-open
  bands, scope-specific beats all-transfers, None = ONE default tier), chain replayed via
  `TransferApproval.cleared_tier_count()` (rejection resets, history survives), decisions
  under `select_for_update` on the SPINE row; final tier flips the spine to `approved`,
  reject returns it to draft. Verbs are `@tenant_admin_required` (403 for members).
- **TransferRoute**: routing catalog (direct/shuttle/milk_run/freight); endpoints optional
  â€” blank = open end; `covers()` matches set ends exactly. Deleting a route SET_NULLs
  movements (never rewrites history).
- Tests: `test_stockmovementtransfers_{models,views}.py` (23). Sandbox caveat of record:
  pytest-django DB-backed runs were killed by the build session's shell (plain pytest +
  collect-only worked); they must run green in a normal dev shell.



### 5.11 Stocktaking & Cycle Counting - the scheduling/freeze slice

- **Cycle Count Scheduling** -> CountProgram [CTP-]: cadence (daily / weekday / day-of-month
  1-28) over a zone-or-bin location + optional ABC class; is_due(today) honours last_run_date;
  generate_tasks(user) runs inside transaction.atomic with the program row re-read
  select_for_update, mints today's marked CycleCountTask (provenance marker, same-day REUSE via a
  notes__startswith probe so the name-suffixed stamp matches), stamps last_run, audits run/rerun.
  Run verb: POST-only; refuses inactive programs at the view (flash) AND the mint honours is_active.
- **Full Physical Inventory** -> PhysicalInventory [PHY-] over a warehouse: start() freezes
  (is_frozen marker; advisory to ops, surfaced on the board) and bulk-creates ONE full-method sheet
  per bin/zone under the warehouse (numbers pre-assigned in one pass - no per-bin max+1 round trips
  inside the lock); provenance goes through the ONE canonical task_marker() builder,
  "Physical inventory {number} #{pk}" - pk-stamped so a --flush re-seed that reissues PHY numbers
  can never adopt the previous generation's sheets. reconcile() REFUSES while any spawned sheet is
  outside reconciled/cancelled - naming the first three - then lifts the freeze; cancel() lifts from
  draft/counting. All verbs select_for_update, status editable=False; spawned_tasks bounds its notes
  scan with the spine's indexed (tenant, scheduled_date) window. Delete guarded to unfrozen drafts
  without spawned sheets. Migration 0016 adds the (tenant, -scheduled_date) list index.
- **Variance Analysis & Adjustments** -> inventory:variance_report (computed page): per counted
  sheet - lines counted/total, disagreeing count (amber badge, zero = green "clean"), net variance,
  posted adjustment link. Filters q/status before pagination; rows ranked by absolute variance
  within the page; location+adjustment select_related up front (zero N+1).
- **Blind Counts** -> scm:cyclecounttask_list pointer (the spine owns server-side expected
  snapshots and single-adjustment reconciliation).
- Templates: templates/inventory/stocktake/ - countprogram/physicalinventory triples plus
  page-only variance.html. Badges colour-named only; confirm() strings carry NO interpolated
  location fields (L42). Seeder _seed_stocktaking: Zone A weekly program + one event walked
  through REAL start/cancel and one left live frozen with sheets awaiting counters (the
  refused reconcile IS the demo).
- Tests: test_stocktake_{models,forms,views,security}.py (96) + conftest fixtures
  stocktake_{warehouse,zone,bin}_{a,b}, stocktake_program_{a,b}, stocktake_event_a,
  stocktake_event_counting_a, _stocktake_sheet/_stocktake_line helpers. GOTCHA of record:
  stocktake_event_counting_a runs REAL start() at fixture setup - always request
  stocktake_zone_a/stocktake_bin_a BEFORE it in a test signature, or start() finds a bin-less
  tree and spawns zero sheets. Verb methods return the FOR-UPDATE re-read row - capture the
  return value, the caller's instance is not refreshed in place.

### 5.8 Lot & Serial Number Tracking - the traceability slice

- **Lot/Batch Generation** -> LotNumberRule: pattern rules (prefix upper-cased on save,
  optional YYMMDD date component, zero-padded 1-9 digit sequence; per-item or tenant default,
  unique (tenant, name)). 
esolve(tenant, item) is most-specific-wins (item rule beats the
  default, inactive rules skipped, None when nothing governs); generate(user, item, *,
  expiry_date=None, notes="") mints the next scm.LotSerial under a collision-retried
  sequence, refuses None/untracked(	racking='none')/foreign/mismatched-kind items via
  ValidationError, stamps an already past-dated expiry straight to status "expired", and posts
  NO StockMove (minting a number claims no stock). One-click surface: inventory:lot_generate
  (GET form + active-rule samples; POST redirects to scm:lotserial_detail). Double-clicking
  the mint creates two DISTINCT valid numbers by design (append-only master; documented).
- **Shelf-Life & Expiry** -> ShelfLifePolicy (OneToOne per tracked SKU): shelf_life_days
  (informational), min_remaining_days (red do-not-ship gate), warning_days (amber window),
  fefo_enforced. clean() forbids warning_days < min_remaining_days AND foreign items.
- **classify_lot(lot, policy, today=None)** (models package re-export) is THE shared verdict:
  codes none/expired/blocked/warning/ok with badge-muted/red/red/amber/green. Board, policy
  detail and trace page all read it - they cannot drift.
- **FEFO board** -> inventory:fefo_board (computed page, NO table;
  iews/LotSerialTracking/FefoBoard.py): ONE grouped StockMove query per lot (positive totals
  only - depleted lots are not pickable), merged with lots + policies in Python. Pick order
  honours policy: enforced regimes sort true FEFO (earliest expiry first, no-expiry last);
  ADVISORY regimes (fefo_enforced=False) keep plain sku/number order so the badge tells the
  truth. Filters q/item/flag applied BEFORE pagination (dict rows through crud.paginate).
- **Traceability & Genealogy** -> inventory:traceability?lot=<pk> (computed page): backward =
  inbound legs, forward = outbound legs (recall scope), genealogy = other lots'
  consumption/production moves sharing THIS lot's transformation references (tenant-scoped
  before the string join; unlotted legs excluded rather than invented; abs_qty annotate for
  magnitude chips). No ?lot= renders a picker (tracked lots, stocked first, capped at 25).
- **Sidebar 5.8**: generation -> inventory:lotrule_list, Serial Number Tracking ->
  scm:lotserial_list (spine master pointer), Shelf-Life -> inventory:fefo_board
  (+ policies CRUD linked from its header), Genealogy -> inventory:traceability.
- Templates: 	emplates/inventory/lottrack/ - lotrule/{list,detail,form}.html,
  shelflifepolicy/{list,detail,form}.html, page-only generate.html, efo.html,
  	race.html. Seeder _seed_lot_tracking: default + MON-27 item rule, WS-16/MON-27
  policies, four expiry-dated demo lots minted through the REAL generate path (notes marker
  guards idempotence) with genuine opening receipts (pply_receipt + receipt moves,
  reference OPENING-LOT). Tests: 	est_lot_{models,forms,views,security}.py (46).
### 5.6 Inventory Tracking & Control â€” the newest slice

- **Real-Time Stock Levels** â†’ `inventory:stocklevels` (computed page, NO table;
  `views/InventoryTrackingControl/StockLevels.py`). One grouped query per source merged into dict
  rows `{item, location, on_hand, allocated, held, available, on_order}`:
  on-hand = Î£ StockMove per (item, location); allocated = active SO allocations + active
  reservations; held = non-sellable StockStatus claims; on-order from open PO lines matched
  EXACTLY by `sku_hint` (ordered vs received split into TWO grouped queries â€” a single annotate
  over both relations fan-outs on partial receipts). Availability deliberately NOT clamped.
  Filters q/item/location/view=shortage applied BEFORE pagination (dict rows paginate through
  `apps.core.crud.paginate`, which accepts plain lists).
- **Stock Status Management** â†’ `StockStatus`: soft claim classifying a quantity at one spot
  (item Ã— location Ã— optional lot) active/damaged/expired/on_hold; posts NO StockMove. Ceiling
  check lives in `StockStatusForm.clean()` (Î£ other same-pool claims + qty â‰¤ spot ledger on-hand);
  model.clean() does tenant checks only (item/location/lot trio).
- **Inventory Reservations** â†’ `InventoryReservation` [RSV-]: general soft lock vs purpose
  sales_order/job/project/other + free-text reference. Lifecycle via locked verbs:
  reserved â†’ released â†’ consumed | cancelled (`release/consume/cancel(user)` raise ValidationError
  outside ACTIONABLE_STATUSES and on same-state moves; resolved_at stamps terminal states).
  ACTIVE_STATUSES = (reserved, released) count toward allocated; consumed stops counting because
  the issuing document already moved the goods. ATP in form: on-hand âˆ’ other active reservations âˆ’
  active SO allocations âˆ’ non-sellable classifications, all with conservative lot union
  (`Q(lot_serial=lot) | Q(lot_serial__isnull=True)` when a lot is named â€” unlotted claims may
  consume any lot). Edit/delete gated to EDITABLE_STATUSES ("reserved"); delete guard+delete share
  one atomic select_for_update block.

### 5.3 Purchase Order (PO) Management â€” the workflow slice

- **Approval routing**: `PurchaseOrderApprovalRule` value bands are HALF-OPEN (`min <= total < max`)
  so adjacent rules never both match; `resolve()`/batched `resolve_from()` pick most-specific-wins
  (org-scoped beats unscoped, then narrowest band; `None` = ONE default tier, never zero).
  Rule writes are `@tenant_admin_required` â€” a rule IS the money gate.
- **Tier decisions**: `PurchaseOrderApproval` [PA-] rows replay via `cleared_tier_count()`
  (rejection resets to zero, history from BOTH runs survives). **Deliberately NO (tenant, po, tier)
  uniqueness** â€” it bricked every rejected-then-resubmitted chain with an IntegrityError (review
  C1); sequential integrity = `_decide` holds `select_for_update()` on the ORDER row inside one
  atomic block. Final tier performs the spine's own approve transition; reject returns to draft.
  EVERY decision is audited (`tier_approve`/`tier_reject`), not just the flip.
- **Dispatch log**: `PurchaseOrderDispatch` [PD-] has NO edit route by design (proof of
  transmission is not rewritable); model clean() demands recipients for email/edi only;
  FIRST dispatch of an approved order flips it to Sent transactionally with the log row.
- **Reorder auto-drafting** (`reorderdraft`): suggestions from below-point `scm.ReorderRule`s over
  `on_hand_map`; POST recomputes quantities from the ledger (never trusts the rendered page),
  groups by buyer-chosen vendor-role party, drafts DRAFT spine orders only.
- Tests: `test_po_{models,forms,views,security}.py` (85) + conftest fixtures `location_a`,
  `approval_rule_std_a/cap_a`, `po_pending_a/po_sent_a`, `tier_decision_a`, `po_dispatch_a`,
  `reorder_below_a`.

## URLs / routes

`app_name = "inventory"`; each entity module exposes `urlpatterns`, concatenated in
`urls/__init__.py`. Names: `<entity>_list/_detail/_create/_edit/_delete` plus lifecycle verbs
(`crossdockorder_receive/_ship/_cancel`, `reservation_release/_consume/_cancel`) and computed
pages (`overview`, `reorderdraft`, `approval_queue`, `warehousemap`, `stocklevels`,
`putaway_suggestions`). Literal routes
always precede `<int:pk>` ones; no greedy `<str:â€¦>` converters exist in this app.

## Templates

`templates/inventory/catalog|vendor|po|warehouse|receiving|tracking/â€¦` â€” entity triples `list/detail/form.html`
plus page-only files (`map.html`, `reorderdraft.html`, `approvals.html`, `tracking/stocklevels.html`,
`receiving/putaway_suggestions.html`).
Badges: colour-named ONLY (`badge-green/red/amber/info/muted/slate`; STATUS_CSS dicts decide per
status). Filter forms reflect request.GET; pk selects compare with `|stringformat:"d"`; every list has
Actions column (eye/pencil/trash-2), pagination partial, `.empty-state`.

## Seeder

`python manage.py seed_inventory` (idempotent per-entity guards; `--flush` deletes all app rows).
Per tenant it reuses seed_scm's items/parties/location tree: attribute sets, price ladder, file links
(RFC 2606 placeholders), vendor communications, approval rules + dispatch + a pending_approval PO,
four tier-demo putaway rules + one open putaway task off DOCK-1 (5.4), then bin capacities + four cross-docks walked through REAL actions, then 5.6: status classifications on
actually-stocked spots (small slices), three RSV rows walked through release/cancel, then 5.7:
three TransferRoutes + two approval rules + four governed spine transfers walked through the REAL
transitions (pending mid-chain / approved / returned-to-draft / completed via scm's own
`_post_transfer` posting service so the legs are genuine StockMoves). Guards are marker-based on
THIS module's tables â€” seed_scm already creates one plain transfer per tenant.

## Conventions & gotchas

- Every view filters `tenant=request.tenant`; `request.tenant_id` DOES NOT EXIST (middleware sets
  only `request.tenant`) â€” that exact bug shipped once here and was caught by strict xfails.
- Forms take `tenant=` kwarg (TenantModelForm); use `_reject_foreign` + TenantUniqueMixin patterns
  from `apps/inventory/forms/_common.py`.
- Spot-ledger aggregates must carry the tenant predicate so `scm_move_tnt_item_loc_idx` applies.
- Migrations are sequential app-wide: 0011 is taken (5.3 dispatch recipient state); check
  `apps/inventory/migrations/` before generating â€” concurrent sessions may take numbers.

## Sidebar wiring

`LIVE_LINKS["5.1"…"5.11"]` in `apps/core/navigation.py` map NavERP.md bullet names â†’ live routes,
pointing master-data bullets at owning scm pages. Overview card groups per sub-module.

## Common tasks

- **Add a field**: edit `models/<Sub>/<Entity>.py` + form Meta.fields + template column â†’ makemigrations.
- **Add an entity**: create the 4 layer files under the SAME `<SubModule>/` folder, add re-export
  blocks to each package `__init__.py`, register admin, extend seeder, add templates triple.
- **Add a filter**: parse GET in the view BEFORE crud_list/paginate; pass choices/querysets via
  extra_context; guard ints with `as_db_int`.

### 5.14 Barcode & RFID Integration - the device slice

- **The identified things are the spine's own codes**: resolve_code(tenant, raw) walks
  scm.Item.sku -> scm.Location.code -> scm.LotSerial.number -> inventory.RfidTag.epc,
  iexact + id-ordered, tenant-scoped; precedence decides when a code matches several masters.
  No parallel identity table anywhere; pallet_ref free-text is the L28 stand-in (no pallet/HU master).
- **BarcodeLabel [LBL-]** (TenantNumbered): target_type item/location/lot/free + nullable FKs +
  target_ref/pallet_ref; symbology code39/code128/ean13/qr; BLANK payload auto-derives from the
  target in save() (form field deliberately optional); copies 1..500; draft->printed via print()
  (re-print allowed, refreshes stamp), void refuses further prints; render endpoint serves
  image/svg+xml from python-barcode SVGWriter / qrcode SvgPathImage (both pillow-free; CSP header;
  invalid-payload symbologies get a STATIC error card - payload never echoed into it; Code39
  upper-cases before validating, KeyError kept in the except-tuple because checksum precedes alphabet
  validation); print page shows clamped preview frames (PRINT_PREVIEW_CAP) + confirm-run POST.
- **ScanSession [SSN-] + ScanEvent** (TenantNumbered/TenantOwned): handheld/wedge capture sessions
  (single|batch) closed via close(); events are append-only snapshots (raw_code, resolved_kind,
  resolved_label, ok) created ONLY through ScanEvent.record or the console - no event form exists.
  Scan Console (`inventory:scan_console`) resolves typed/pasted codes live (?mode=single|batch,
  ?session= preselects); POST caps at 300 BEFORE the loop inside one atomic block; batch path uses
  the grouped resolve_codes helper (4 __in queries, same precedence); unknowns recorded ok=False.
- **RfidTag [TAG-]** (TenantOwned, epc IS the identifier): hex regex ^[0-9A-F\\-]{8,64}$ normalised
  strip+upper in save()/clean(), unique (tenant, epc); unassigned->active->retired|lost verbs all
  guarded (activate REQUIRES an anchor: item/location/lot_serial/target_ref/pallet_ref);
  bulk_read(tenant, epcs, location) stamps last_seen_at/last_seen_location in ONE .update() and
  reports unmatched EPCs (cap 500).
- Writes admin-gated (@tenant_admin_required on label CRUD/print/void, tag CRUD/verbs/bulk-read);
  sessions + console member-open BY DESIGN ("everyone scans"); edit refused once a session closes.
- Sidebar 5.14: Label Generation -> barcodelabel_list; Scanner Integration -> scan_console;
  RFID Tag Management -> rfidtag_list; Batch Scanning -> scan_console (?mode=batch).
- Templates: templates/inventory/barcode/ - barcodelabel/{list,detail,form,print}.html,
  scansession/{list,detail,form}.html, rfidtag/{list,detail,form,bulkread}.html, page-only console.html.
- Seeder _seed_barcode_rfid -> independently-guarded _seed_barcode_labels_and_scans (labels over demo
  items/bins incl. one EAN-13, one session walked through the REAL resolver with a deliberate unknown,
  one open batch) + _seed_rfid_tags (five tags through real verbs, bulk_read stamps last-seen).
- Deps: python-barcode==0.16.1 + qrcode==8.2 pinned in requirements.txt (SVG factories need no Pillow).
- Tests: test_barcode_{models,forms,views,security}.py (30) + conftest fixtures barcode_label_{a,b},
  scan_session_open_a, scan_event_a, rfid_tag_active_a, rfid_tag_b.
