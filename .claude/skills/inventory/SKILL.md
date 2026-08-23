---
name: inventory
description: Work on the Inventory Management System module (Module 5 â€” 5.1 Product & Catalog, 5.2 Vendor/Supplier Management, 5.3 Purchase Order Management, 5.5 Warehousing & Bins, 5.6 Inventory Tracking & Control, 5.7 Stock Movement & Transfers, 5.8 Lot & Serial Number Tracking; 5.4 Receiving & Putaway in progress). Extends apps/inventory around the SCM 4.3 item/location/StockMove spines (L36 â€” never re-declares them). Use when the user asks to add/change/debug anything under apps/inventory or templates/inventory, extend the seed_inventory seeder, touch inventory sidebar wiring (LIVE_LINKS 5.x), or invokes /inventory.
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


### 5.8 Lot & Serial Number Tracking - the traceability slice

- **Lot/Batch Generation** -> LotNumberRule: pattern rules (prefix upper-cased on save,
  optional YYMMDD date component, zero-padded 1-9 digit sequence; per-item or tenant default,
  unique (tenant, name)). esolve(tenant, item) is most-specific-wins (item rule beats the
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

`LIVE_LINKS["5.1"â€¦"5.8"]` in `apps/core/navigation.py` map NavERP.md bullet names â†’ live routes,
pointing master-data bullets at owning scm pages. Overview card groups per sub-module.

## Common tasks

- **Add a field**: edit `models/<Sub>/<Entity>.py` + form Meta.fields + template column â†’ makemigrations.
- **Add an entity**: create the 4 layer files under the SAME `<SubModule>/` folder, add re-export
  blocks to each package `__init__.py`, register admin, extend seeder, add templates triple.
- **Add a filter**: parse GET in the view BEFORE crud_list/paginate; pass choices/querysets via
  extra_context; guard ints with `as_db_int`.
