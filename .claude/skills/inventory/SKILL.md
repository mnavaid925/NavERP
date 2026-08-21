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

### Not built yet (NavERP.md order): 5.2–5.20
Vendor/supplier management (5.2 — likely maps onto `core.Party` roles + 4.2 SRM rather than new
tables), PO management (5.3 → scm owns), receiving/putaway (5.4 → 4.1 GRN + 4.4 WMS),
warehousing/bins (5.5 → 4.3/4.4), tracking & control (5.6), movements/transfers (5.7 → 4.3),
lot/serial (5.8 → 4.3), order mgmt (5.9 → 4.5), returns (5.10 → 4.10), stocktaking (5.11 → 4.4
cycle counts), multi-location (5.12), forecasting (5.13 → 4.7), barcode/RFID (5.14 — identifiers
belong beside the spine columns, not in a parallel master), QC/inspection (5.15 → 4.9), alerts
(5.16 → 4.11 pattern), reporting (5.17), accounting integration (5.18 → accounting owns the
ledger), third-party APIs (5.19 → 4.19 pattern), UOM (5.20 → scm.UOM exists; conversions beyond
its factor column are what's actually missing).

## House rules inherited from the peer apps

- Backend package layout: `models/ forms/ views/ urls/` packages, one `<SubModule>/` folder per
  NavERP sub-module (here: `Catalog/`), one `<Entity>.py` per entity in each layer, re-export
  blocks in every touched `__init__.py`, absolute imports throughout. No flat files, no
  `*_advanced.py`.
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
Product Imagery & Documents → `inventory:productfile_list`. Later 5.x sub-modules add ONE
`LIVE_LINKS["N.M"]` entry each; do not touch the parse_catalog machinery or other entries.
