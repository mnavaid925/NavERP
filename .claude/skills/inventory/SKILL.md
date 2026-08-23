---
name: inventory
description: Work on the Inventory Management System module (Module 5 — 5.1 Product & Catalog, 5.2 Vendor/Supplier Management, 5.3 Purchase Order Management, 5.5 Warehousing & Bins, 5.6 Inventory Tracking & Control; 5.4 Receiving & Putaway in progress). Extends apps/inventory around the SCM 4.3 item/location/StockMove spines (L36 — never re-declares them). Use when the user asks to add/change/debug anything under apps/inventory or templates/inventory, extend the seed_inventory seeder, touch inventory sidebar wiring (LIVE_LINKS 5.x), or invokes /inventory.
---

# Inventory Management System (Module 5)

App: `apps/inventory` (registered as `apps.inventory`; url prefix `/inventory/`, `app_name = "inventory"`).
Backend AND templates follow the package layout: one `<SubModule>/` folder per NavERP sub-module
(`models/forms/views/urls` line up one-to-one), templates under `templates/inventory/<short-slug>/…`.

## Ownership spine (L36/L29/L37 — read before ANY new model)

The item/stock masters belong to **SCM 4.3** (`apps/scm`): `scm.Item` (sku, costing_method
weighted_avg/fifo/lifo, cached `average_cost`, `on_hand()` ledger aggregate, `apply_receipt()`),
`scm.ItemCategory`, `scm.UOM`, `scm.Location` (warehouse/zone/bin self-FK tree + bin attributes),
`scm.LotSerial`, and the **append-only `scm.StockMove` ledger** (signed quantity; on-hand is ALWAYS
its aggregate — no editable quantity anywhere). POs are `scm.PurchaseOrder(Line)` (lines are the L28
free-text `item_description`/`sku_hint` stand-in, NOT an item FK). SO allocations are
`scm.SalesOrderAllocation` (active statuses reserved/released; lot-blind; its ATP check lives in the
FORM, never model.clean()). This app only adds the catalog/vendor/po-approval/warehousing/tracking
layers AROUND that spine, FK'ing by string (`"scm.Item"`, …) with PROTECT on item/location.

## Sub-modules as built

| N.M | Package folder | Models (this app) | Notes |
|-----|----------------|-------------------|-------|
| 5.1 | `Catalog/` | ItemAttribute, ItemPrice, ProductFile | sidebar bullets "SKU Management"/"Product Categorization" point at `scm:item_list` / `scm:category_list` |
| 5.2 | `VendorSupplierManagement/` | VendorCommunication [VC-] | directory/scorecard/contract bullets point at 4.2 SRM pages |
| 5.3 | `PurchaseOrderManagement/` | PurchaseOrderApprovalRule, PurchaseOrderApproval, PurchaseOrderDispatch + `reorderdraft` computed page | creation/tracking point at spine PO pages |
| 5.5 | `WarehousingBinManagement/` | BinCapacity, CrossDockOrder [XD-] (+ warehousemap computed page) | XD receive/ship/cancel posts real StockMove legs |
| 5.6 | `InventoryTrackingControl/` | StockStatus, InventoryReservation [RSV-] (+ stocklevels computed page) | valuation bullet points at `scm:valuation_report` |

### 5.6 Inventory Tracking & Control — the newest slice

- **Real-Time Stock Levels** → `inventory:stocklevels` (computed page, NO table;
  `views/InventoryTrackingControl/StockLevels.py`). One grouped query per source merged into dict
  rows `{item, location, on_hand, allocated, held, available, on_order}`:
  on-hand = Σ StockMove per (item, location); allocated = active SO allocations + active
  reservations; held = non-sellable StockStatus claims; on-order from open PO lines matched
  EXACTLY by `sku_hint` (ordered vs received split into TWO grouped queries — a single annotate
  over both relations fan-outs on partial receipts). Availability deliberately NOT clamped.
  Filters q/item/location/view=shortage applied BEFORE pagination (dict rows paginate through
  `apps.core.crud.paginate`, which accepts plain lists).
- **Stock Status Management** → `StockStatus`: soft claim classifying a quantity at one spot
  (item × location × optional lot) active/damaged/expired/on_hold; posts NO StockMove. Ceiling
  check lives in `StockStatusForm.clean()` (Σ other same-pool claims + qty ≤ spot ledger on-hand);
  model.clean() does tenant checks only (item/location/lot trio).
- **Inventory Reservations** → `InventoryReservation` [RSV-]: general soft lock vs purpose
  sales_order/job/project/other + free-text reference. Lifecycle via locked verbs:
  reserved → released → consumed | cancelled (`release/consume/cancel(user)` raise ValidationError
  outside ACTIONABLE_STATUSES and on same-state moves; resolved_at stamps terminal states).
  ACTIVE_STATUSES = (reserved, released) count toward allocated; consumed stops counting because
  the issuing document already moved the goods. ATP in form: on-hand − other active reservations −
  active SO allocations − non-sellable classifications, all with conservative lot union
  (`Q(lot_serial=lot) | Q(lot_serial__isnull=True)` when a lot is named — unlotted claims may
  consume any lot). Edit/delete gated to EDITABLE_STATUSES ("reserved"); delete guard+delete share
  one atomic select_for_update block.

### 5.3 Purchase Order (PO) Management — the workflow slice

- **Approval routing**: `PurchaseOrderApprovalRule` value bands are HALF-OPEN (`min <= total < max`)
  so adjacent rules never both match; `resolve()`/batched `resolve_from()` pick most-specific-wins
  (org-scoped beats unscoped, then narrowest band; `None` = ONE default tier, never zero).
  Rule writes are `@tenant_admin_required` — a rule IS the money gate.
- **Tier decisions**: `PurchaseOrderApproval` [PA-] rows replay via `cleared_tier_count()`
  (rejection resets to zero, history from BOTH runs survives). **Deliberately NO (tenant, po, tier)
  uniqueness** — it bricked every rejected-then-resubmitted chain with an IntegrityError (review
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
pages (`overview`, `reorderdraft`, `approval_queue`, `warehousemap`, `stocklevels`). Literal routes
always precede `<int:pk>` ones; no greedy `<str:…>` converters exist in this app.

## Templates

`templates/inventory/catalog|vendor|po|warehouse|tracking/…` — entity triples `list/detail/form.html`
plus page-only files (`map.html`, `reorderdraft.html`, `approvals.html`, `tracking/stocklevels.html`).
Badges: colour-named ONLY (`badge-green/red/amber/info/muted/slate`; STATUS_CSS dicts decide per
status). Filter forms reflect request.GET; pk selects compare with `|stringformat:"d"`; every list has
Actions column (eye/pencil/trash-2), pagination partial, `.empty-state`.

## Seeder

`python manage.py seed_inventory` (idempotent per-entity guards; `--flush` deletes all app rows).
Per tenant it reuses seed_scm's items/parties/location tree: attribute sets, price ladder, file links
(RFC 2606 placeholders), vendor communications, approval rules + dispatch + a pending_approval PO,
bin capacities + four cross-docks walked through REAL actions, then 5.6: status classifications on
actually-stocked spots (small slices) and three RSV rows walked through release/cancel.

## Conventions & gotchas

- Every view filters `tenant=request.tenant`; `request.tenant_id` DOES NOT EXIST (middleware sets
  only `request.tenant`) — that exact bug shipped once here and was caught by strict xfails.
- Forms take `tenant=` kwarg (TenantModelForm); use `_reject_foreign` + TenantUniqueMixin patterns
  from `apps/inventory/forms/_common.py`.
- Spot-ledger aggregates must carry the tenant predicate so `scm_move_tnt_item_loc_idx` applies.
- Migrations are sequential app-wide: 0011 is taken (5.3 dispatch recipient state); check
  `apps/inventory/migrations/` before generating — concurrent sessions may take numbers.

## Sidebar wiring

`LIVE_LINKS["5.1"…"5.6"]` in `apps/core/navigation.py` map NavERP.md bullet names → live routes,
pointing master-data bullets at owning scm pages. Overview card groups per sub-module.

## Common tasks

- **Add a field**: edit `models/<Sub>/<Entity>.py` + form Meta.fields + template column → makemigrations.
- **Add an entity**: create the 4 layer files under the SAME `<SubModule>/` folder, add re-export
  blocks to each package `__init__.py`, register admin, extend seeder, add templates triple.
- **Add a filter**: parse GET in the view BEFORE crud_list/paginate; pass choices/querysets via
  extra_context; guard ints with `as_db_int`.
