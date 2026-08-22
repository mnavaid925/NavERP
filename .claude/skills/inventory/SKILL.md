# Inventory Management System (Module 5)

Work on the Inventory Management System module (Module 5 — `apps/inventory`). Use when the user
asks to add/change/debug anything under `apps/inventory` or `templates/inventory`, extend the
`seed_inventory` seeder, touch IMS sidebar wiring (`LIVE_LINKS` 5.x), build the next IMS
sub-module, or invokes `/inventory`.

## THE OWNERSHIP RULING (read before building anything here)

**This app does NOT own an item master and must never grow one.** SCM 4.3 shipped the inventory
spine first and OWNS it (L29/L36): `scm.Item`, `scm.ItemCategory` (hierarchical via self-FK),
`scm.UOM`, `scm.Location`, `scm.LotSerial`, the append-only `scm.StockMove` ledger (+ derived
on-hand/valuation), `scm.StockTransfer`/`StockAdjustment`/`ReorderRule`. NavERP.md's Module 5
table nominally assigns Item/UOM to this app — reconciled to "extend by FK" in
`NavERP-ERD.md` line ~467 and in `apps/scm/models/InventoryManagement/Items.py`'s docstring.
Every model here FKs `'scm.Item'` **by string**. The sidebar bullets for spine features point AT
the owning module's routes (`scm:item_list`, `scm:category_list`, …), never at duplicates.

The cost side of pricing lives ON `scm.Item` too: `standard_cost` (typed) plus `average_cost`
(derived cache written by receipt/landed-cost writers). This app stores **no cost column** — a
second cost figure would be two sources of truth for money.

## As-built sub-modules

### 5.1 Product & Catalog Management (COMPLETE)
Three tenant-scoped children on the item spine (`apps/inventory/models/Catalog/`):
- **`ItemAttribute`** — name/value/unit spec-sheet rows; `(tenant, item, name)` unique (a SKU
  cannot carry "Color" twice); `sequence` lays out the spec sheet; `display_value` joins unit.
- **`ItemPrice`** — SELL-side rows only: type retail/wholesale/promotional/clearance × price-break
  `min_quantity` × dated window (`valid_from`/`valid_until`, open end stays open); optional
  `accounting.Currency`; `margin_pct`/`markup_pct` computed against the item's CURRENT standard
  cost at render time and both return **None** without a saved item or a non-zero basis
  (`standard_cost=0` means "not costed yet" — never render it as a perfect margin).
- **`ProductFile`** — photo/safety_sheet/manual/datasheet/certificate/other; file-upload OR
  external `url` (model `clean()` demands at least one, error keyed on `file` so it renders);
  curated extension allowlist (subset of core's — no archives); 20 MB cap enforced at the form
  boundary from core's `MAX_UPLOAD_BYTES`; `is_primary` auto-demotes siblings in `save()`; row
  delete keeps the artifact on disk.
Plus `/inventory/` overview: computed catalog stats + completeness bars (priced % / photographed %
— gaps read as progress, not alerts).

Routes (16, prefix under `/inventory/`): `` overview; `attributes|prices|files/` each with
`_list/_add/_detail/_edit/_delete` (literal before `<int:pk>`, deletes POST-only).
Templates: `templates/inventory/catalog/<entity>/{list,detail,form}.html`.
Seeder: `seed_inventory` — idempotent per tenant per entity; reuses seeded `scm.Item`s (skips a
tenant with none); price ladder off real standard costs; files seed as RFC 2606 links, never
uploads.

### 5.2 Vendor / Supplier Management (COMPLETE)
The extend-don't-redeclare rule applied to the buy side: three of the four NavERP bullets ARE the
4.2 SRM pages (the supplier spine is owned by SCM per L36 — the sidebar bullets point at
`scm:supplierprofile_list` / `scm:scorecard_list` / `scm:contract_list`; payment terms live on
`SupplierContract`, per-line lead times + MOQs on `SupplierCatalogItem`). The one genuine gap was
the conversation itself, so 5.2's only new table is (`apps/inventory/models/VendorSupplierManagement/`):
- **`VendorCommunication`** [VC-#####] — one logged interaction with a vendor: `channel`
  (email/call/meeting/site_visit/note; `CHANNEL_CSS` badge map, colour-named only), `direction`
  (inbound/outbound/blank), `subject`+`body`, `occurred_at` (when it actually happened), optional
  `follow_up_on` driving due/overdue list chips and the `is_follow_up_overdue` property
  (`timezone.localdate()`, never `date.today()`); **PROTECT** FK to the vendor `core.Party`
  (deleting a party cannot destroy interaction history) with a cross-tenant guard in `clean()`.
  "Logged by" is deliberately NOT a column — every write lands in `core.AuditLog` via the CRUD
  helpers. This pass gave the app its own `TenantNumbered` base in `models/_base.py`
  (local copy of scm's, backed by `apps.core.utils.next_number`).

Routes (+5, prefix `vendor-communications/`): `vendorcommunication_{list,detail,create,edit,delete}`.
Templates: `templates/inventory/vendor/vendorcommunication/{list,detail,form}.html`; the overview
gained a "Vendor Pages" card linking the log + the three SRM pages. Detail page shows the same
vendor's other interactions (scoped + self-excluded from the view, no select_related — the panel
never dereferences party) and cross-links the three SRM pages.
Seeder: `_seed_vendor_communications` in `seed_inventory` — six scripted interactions per tenant
(one overdue follow-up, one future) over existing supplier/vendor-role parties via
`forms/_common._vendor_parties()` (roles supplier|vendor, `.distinct()`); skips a tenant with none;
follow-up dates derive from `timezone.localdate()`.
Tests: `test_vendor_{models,forms,views,security}.py` (39 tests) + conftest fixtures
`vendor_party_a/b`, `communication_a/b`. Full inventory suite green (104 as of 5.2).

### 5.5 Warehousing & Bin Management (COMPLETE)
The location spine is SCM's (L36): "Warehouse Structure" points at `scm:location_list` — the
tree already nests warehouse → zone → aisle → rack → bin through its self-FK, so no second
location master exists here. What nothing else records (`apps/inventory/models/WarehousingBinManagement/`):
- **`BinCapacity`** — ONE capacity envelope per location (`unique_together tenant+location`,
  PROTECT FK `scm.Location`, rn `bin_capacity`): `max_weight_kg` / `max_volume_m3` /
  `max_quantity` (each nullable, ≥0; a form-level rule demands AT LEAST ONE limit), notes.
  Quantity utilisation is DERIVED from the StockMove aggregate (`on_hand`,
  `quantity_utilisation` → None when no limit declared — never a flattering 0%, the 4.15
  honesty rule); weight/volume limits are stored but NOT turned into percentages because
  `scm.Item` has no structured unit-weight — pages say so instead of inventing figures.
- **`CrossDockOrder`** [XD-#####] — dock-to-dock bypass: `item`(PROTECT)/`lot_serial`(SET_NULL,
  must belong to the item)/`dock_location`(PROTECT)/`quantity`(>0)/`unit_cost`(inbound layer)/
  `scheduled_date`/`inbound_reference`/`outbound_reference`/`status`
  draft→received→shipped|cancelled. `receive()` posts a REAL receipt leg into scm.StockMove
  (rolling `Item.average_cost` exactly like scm's posting service), `ship()` posts a guarded
  issue leg at average cost, cancel-from-received posts a GUARDED compensating −receipt —
  the ledger is never deleted. Every action re-reads its row FOR UPDATE inside atomic and
  writes its audit row INSIDE the transaction; received/shipped documents refuse deletion.
- **Warehouse Mapping** is a COMPUTED page (no table): all locations in one fetch + ONE
  group-by for per-bin on-hand AND value, cycle-guarded Python walk (_MAX_DEPTH 8), orphan
  roots surfaced not hidden, over-capacity count from data already in hand.

Routes (+14): `bin-capacity/` quintet; `cross-dock/` CRUD with the receive/ship/cancel verbs as
literal segments BEFORE `<int:pk>`; `warehouse-map/`. Templates:
`templates/inventory/warehouse/{bincapacity,crossdockorder}/{list,detail,form}.html` +
`warehouse/map.html`. Seeder: `_seed_warehousing` in `seed_inventory` — extends seed_scm's
WH-MAIN tree (zone WH-MAIN-ZA, bins A2/B1, dock DOCK-2 via get_or_create), four capacity
profiles (DOCK-1 capped at 8 so the received cross-dock of 10 shows genuinely over-limit), and
four XD orders walked through the REAL actions (draft/received/shipped/cancelled-with-reversal).
Sidebar: `LIVE_LINKS["5.5"]` — Warehouse Structure → `scm:location_list`; Bin Capacity →
`inventory:bincapacity_list`; Warehouse Mapping → `inventory:warehousemap`; Cross-Docking →
`inventory:crossdockorder_list`.

### Not built yet (NavERP.md order): 5.4, 5.6–5.20
receiving/putaway (5.4 → 4.1 GRN + 4.4 WMS), tracking & control (5.6), movements/transfers
(5.7 → 4.3), lot/serial (5.8 → 4.3), order mgmt (5.9 → 4.5), returns (5.10 → 4.10), stocktaking
(5.11 → 4.4 cycle counts), multi-location (5.12), forecasting (5.13 → 4.7), barcode/RFID (5.14 —
identifiers belong beside the spine columns, not in a parallel master), QC/inspection (5.15 → 4.9), alerts
(5.16 → 4.11 pattern), reporting (5.17), accounting integration (5.18 → accounting owns the
ledger), third-party APIs (5.19 → 4.19 pattern), UOM (5.20 → scm.UOM exists; conversions beyond
its factor column are what's actually missing).

## House rules inherited from the peer apps

- Backend package layout: `models/ forms/ views/ urls/` packages, one `<SubModule>/` folder per
  NavERP sub-module (here: `Catalog/`, `VendorSupplierManagement/`), one `<Entity>.py` per entity
  in each layer, re-export blocks in every touched `__init__.py`, absolute imports throughout.
  No flat files, no `*_advanced.py`.
- Views are thin FBVs over `apps/core/crud.py` (`crud_list/create/detail/edit/delete`) — tenant
  scoping, L11 int-filter guard, pagination and audit logging come from there. Deletes are
  `@require_POST`.
- Forms: local copies of `TenantUniqueMixin` + `_reject_foreign` live in
  `forms/_common.py` (peer apps don't import each other's internals). **The mixin has TWO
  jobs**: stamping `instance.tenant` for tenant-included unique validation AND feeding model
  `clean()` foreign-key checks during `full_clean()` on CREATE (`crud_create` stamps tenant only
  after `is_valid()`) — keep it on every form whose model's `clean()` compares tenants,
  constraint or not (this exact gap was SEC-1: without the stamp every ProductFile create was
  falsely rejected as cross-tenant).
- Detail pages pass **scoped, self-excluded sibling querysets from the view**
  (`obj.item.catalog_x.filter(tenant=request.tenant).exclude(pk=obj.pk)`) — never loop the raw
  reverse relation in the template.
- Tests: `apps/inventory/tests/test_catalog_{models,forms,views,security}.py` +
  shared-root fixtures (`tenant_a/b`, `client_a/b`, `admin_user`…). Run everything unfiltered:
  `venv\Scripts\python.exe -m pytest -q` (17,963 tests green as of 5.1).

## Sidebar wiring

`LIVE_LINKS["5.1"]` in `apps/core/navigation.py`: SKU Management → `scm:item_list`,
Product Categorization → `scm:category_list`, Product Attributes →
`inventory:itemattribute_list`, Pricing & Costing → `inventory:itemprice_list`,
Product Imagery & Documents → `inventory:productfile_list`.
`LIVE_LINKS["5.2"]`: Supplier Directory → `scm:supplierprofile_list`, Supplier Performance
Tracking → `scm:scorecard_list`, Contract & Terms Management → `scm:contract_list`
(all three reuse 4.2 SRM per L36), Vendor Communication Log →
`inventory:vendorcommunication_list`. Later 5.x sub-modules add ONE
`LIVE_LINKS["N.M"]` entry each; do not touch the parse_catalog machinery or other entries.
