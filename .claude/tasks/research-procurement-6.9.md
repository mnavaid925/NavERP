# Research — Procurement 6.9 Catalog Management (build-scope brief)

Spec: `NavERP.md` L1047–1052. Five bullets: (1) Catalog Item Creation, (2) Pricing & Tier
Management, (3) Catalog Approval Workflow, (4) Punch-out Catalog Integration,
(5) Supplier Catalog Hosting.

## 1. Verdict

Build **4 models** in one sub-module pass, in a new `CatalogManagement` package:
`CatalogItem` (the governed buy-side catalog line — internal or supplier sourced, with an
item-level approval machine), `CatalogPriceTier` (volume/contract/effective-dated price rows
with their own propose→approve lifecycle so price changes route through bullet 3 without a
second engine), `PunchOutEndpoint` (per-supplier cXML/OCI connection config — config only,
live handshake deferred), and `CatalogUploadBatch` (supplier-hosted file upload with a
validation/error-log lifecycle that feeds item creation). Hard-FK the VERIFIED masters
(`scm.Item`, `scm.UOM`, `core.Party`, `accounting.Currency`, `scm.SupplierContract`);
keep supplier-product text free-text. Do NOT re-declare SCM 4.2's `SupplierCatalog` /
`SupplierCatalogItem` [CAT-] — they already exist as 4.2's simple dated price lists; 6.9 is the
buyer-side governed layer above them. Punch-out real sessions (cXML/OCI outbound HTTP) defer;
CRM's webhook/SSRF-guard precedent is the follow-up path.

## 2. Feature catalog (researched capability → NavERP bullet → recommendation)

| # | Capability | Source products | Bullet | Build? |
|---|---|---|---|---|
| 1 | Internal/hosted catalog items w/ description, price, UOM | SAP Ariba, Coupa, Oracle iProcurement, GEP SMART, Zycus, Ivalua, Jaggaer One, Proactis | 1 | **Build now** — `CatalogItem` |
| 2 | Dual sourcing: link internal stock item OR free-text supplier product | Ariba (local vs punch-out), GEP (price book vs supplier catalog vs material master) | 1 | **Build now** — `source_type` choice + nullable `item` FK |
| 3 | Volume/quantity price breaks with effective date ranges | Oracle (price breaks by qty + effective dates), GEP (tiered/bulk discounts), Coupa | 2 | **Build now** — `CatalogPriceTier` |
| 4 | Contract pricing linkage on catalog lines | Ariba ("apply contract pricing proactively"), Coupa, GEP ("flip from contract") | 2 | **Build now** — FK `scm.SupplierContract` (4.2, verified); contract number surfaced on item |
| 5 | Catalog approval workflow: new-item path AND price-change path, revision compare | Oracle (Difference Summary, buyer approval hierarchy), GEP (version control + approval), Jaggaer (submit→approve→active), Zycus (custom approvals before go-live) | 3 | **Build now** — status machines on both models; new tier row = proposed price change |
| 6 | Preferred / blocked item flags, approved-supplier-only search | Ariba, Zycus (preferred items), GEP (guided buying) | 1,3 | **Build now** — cheap boolean columns on `CatalogItem` |
| 7 | Punch-out to external supplier sites (Amazon Business, Grainger) via cXML/OCI session handshake | Amazon Business punch-out docs, SAP OCI, cXML (Ariba/Coupa/Jaggaer/Oracle), GEP (OCI + API cart, real-time Amazon) | 4 | **Config table now** (`PunchOutEndpoint`: protocol cxml/oci/manual_link, URL, credentials write-only, enabled); live SetupRequest→PunchOutOrderMessage handshake **defer** — needs signed-secret storage + SSRF-guarded outbound HTTP; manual-link fallback works day one |
| 8 | Supplier self-service hosted catalog upload (CIF/cXML/XLSX/CSV) with technical validation + error log + versioning/compare | Ariba (CIF/cXML/BMEcat/XLSX validation by line no.), GEP myBuy hosted catalogs (template, error log, comparison report), Jaggaer Supplier Network (submit/syndicate), Zycus Supplier Network, Oracle (Agreement Loader) | 5 | **Build now** — `CatalogUploadBatch` (file upload, rows parsed/accepted/rejected counters, error log textfield, received→validated→approved/published→rejected lifecycle); full CIF/cXML parsers **defer** — CSV/Excel-row import only |
| 9 | Cross-catalog search/browse/faceting, UNSPSC mapping, content enrichment queues | Ariba (cross-catalog search, cleanse/enrich), Zycus (AI search, UNSPSC), GEP (UNSPSC codes) | 1 | **Computed page later** — list-page search + category filter now; enrichment queue defer |
| 10 | UOM conversion + per-UOM pricing, multi-currency catalogs | GEP (pricing per supported UOM), Oracle, Zycus | 1,2 | **Reuse** — FK `scm.UOM`; per-tier currency via `accounting.Currency`; conversion math stays with inventory 5.x UomConversions — do not duplicate |
| 11 | Price variance guards / tolerance on PO vs catalog price | Oracle (Price Change Tolerance %), Coupa invoice-vs-contract validation | 2 | **Defer** — belongs to 6.10 PO Management / receiving match, note it |
| 12 | Punch-out cart → requisition line transfer | Amazon/Ariba/Coupa flows (PunchOutOrderMessage → requisition) | 4 | **Defer** — when built it writes `scm.PurchaseRequisitionLine`, never a second requisition |

## 3. Spine verification (grep `^class` over all five model packages — code is truth)

Verified EXISTS today:

| Class | App | Path |
|---|---|---|
| `Tenant` / `Party` / `PartyRole` / `OrgUnit` | core | apps/core/models/{Tenant,Party,PartyRole}.py |
| `Item` (sku, name, uom FK, standard_cost; TenantOwned) | scm 4.3/5.x spine | apps/scm/models/InventoryManagement/Items.py:73 |
| `UOM`, `ItemCategory` | scm | apps/scm/models/InventoryManagement/Items.py:51,34 |
| `StockMove`, `Location`, `LotSerial` | scm | apps/scm/models/InventoryManagement/{StockMoves,Locations,LotSerials}.py |
| `PurchaseRequisition`(+Line), `RFQ`(+lines), `PurchaseOrder`(+Line), `GoodsReceiptNote` | scm 4.1 | apps/scm/models/ProcurementManagement/*.py |
| `SupplierProfile`, `SupplierContract`, `SupplierScorecard`, **`SupplierCatalog`[CAT-]**, **`SupplierCatalogItem`** | scm 4.2 | apps/scm/models/SupplierRelationshipManagement/*.py (catalogs at SupplierCatalogs.py:11,46) |
| `Product`, `PriceBook`, `Quote` | crm 1.2 (SELL-side quoting) | apps/crm/models/SalesForceAutomation/*.py |
| `ItemPrice` (SELL-side retail breaks), `ProductFile`, `ItemAttribute` | inventory 5.1 | apps/inventory/models/Catalog/*.py |
| `Currency`, `TaxCode`, `PaymentTerm` | accounting | apps/accounting/models/{GeneralLedger/Tax/AccountsPayable}/*.py |

NOT BUILT / DO NOT FK:
- No procurement-side catalog, tier-pricing, punch-out, or upload-batch entity anywhere (6.9 greenfield).
- `crm.Product`/`PriceBook` and `inventory.ItemPrice` are SELL-side — wrong domain; reuse rejected.
- Parallel-session WIP (UNTRACKED — read-only convention reference, never an FK target):
  `apps/procurement/{models,forms,views,urls}/{VendorManagement,EAuctionManagement,ContractsManagement}/`
  and migrations 0007/0010 uncommitted. 6.8 contracts are WIP → use COMMITTED `scm.SupplierContract`
  (4.2) for contract pricing instead.
- Stand-in rule (L28/L29): supplier-product identity stays free-text (`supplier_part_no`,
  `description`) because no supplier-product master exists beyond 4.2's free-text
  `SupplierCatalogItem`; internal items hard-FK verified `scm.Item`.

Conventions read from committed pair: `apps/procurement/models/_base.py` +
`models/RfxManagement/{Events,Responses}.py`, `views/RfxManagement/Events.py`,
`management/commands/seed_procurement.py`, `apps/core/navigation.py` (LIVE_LINKS "6.1"…"6.7"
wired; "6.8"/"6.9" absent).

## 4. Recommended model sketch (new package `apps/procurement/models/CatalogManagement/`)

All inherit `_base.TenantNumbered` / `TenantOwned`; money via `q2()` clamp; derived figures are
`@property` never stored; actions return `bool` and stamp timestamps.

### `CatalogItem(TenantNumbered)` — prefix `PCI` — bullets 1+3 (+6)
- `source_type` choices: `internal` / `supplier_product`.
- `item` FK `"scm.Item"` SET_NULL null blank (required-when-internal, validated in `clean()`
  incl. same-tenant check like `inventory.ItemPrice.clean()`).
- `supplier` FK `"core.Party"` SET_NULL null blank related_name="procurement_catalog_items".
- `contract` FK `"scm.SupplierContract"` SET_NULL null blank (bullet 4 contract pricing).
- Free-text stand-ins: `supplier_part_no` CharField(64), `name` CharField(255),
  `description` TextField, `manufacturer` CharField(120) blank.
- `uom` FK `"scm.UOM"` SET_NULL null blank; `currency` FK `"accounting.Currency"` SET_NULL
  null blank; `base_price` Decimal(14,2) ≥ 0.
- STATUS_CHOICES: `draft` → `pending_approval` → `approved` / `rejected` → `blocked` /
  `archived`. EDITABLE_STATUSES = draft/rejected (RfxEvent pattern). Fields: `submitted_by/at`,
  `approved_by/at`, `rejection_reason`, `created_by` FK AUTH_USER_MODEL.
- Flags: `is_preferred`, `is_active`. Search helpers: `category_text` CharField(120) blank
  (UNSPSC-lite).
- Unique: `("tenant","number")`. Indexes `(tenant,status)`, `(tenant,item)`.
- Properties/actions: `is_purchasable` (approved + active), `approve()/reject()/block()`.

### `CatalogPriceTier(TenantOwned)` — no number (child rows) — bullets 2+3
- `catalog_item` FK `"procurement.CatalogItem"` CASCADE related_name="price_tiers".
- `min_quantity` Decimal(14,2) default 1; `unit_price` Decimal(14,2) ≥ 0 (blank when
  discount_pct used); `discount_pct` Decimal(5,2) null blank.
- `valid_from`/`valid_until` DateFields null blank (open end allowed; `clean()` window check);
  `contract` FK `"scm.SupplierContract"` SET_NULL null blank.
- STATUS_CHOICES: `draft` (proposed change) → `active` → `superseded` / `cancelled`.
  `approved_by/at`, `submitted_by` FKs.
- Unique: `("tenant","catalog_item","min_quantity","valid_from")` — one break per threshold.
- Ordering `["catalog_item_id","min_quantity"]`. Property: `effective_price(base)`.

### `PunchOutEndpoint(TenantOwned)` — prefix `POE` — bullet 4
- `party` FK `"core.Party"` CASCADE related_name="punchout_endpoints";
  `name` CharField(120).
- PROTOCOL_CHOICES: `cxml` / `oci` / `manual_link`. `punchout_url` URLField;
  `username` CharField(120) blank; `shared_secret` CharField(255) blank
  (**write-only**: form excludes on edit, never re-rendered — CRM Webhook signing-secret style).
- `enabled` Boolean default True; `last_session_at` DateTime editable=False null;
  `notes` TextField. Index `(tenant, enabled)`.
- Live handshake DEFERRED: no outbound HTTP this pass; `manual_link` renders a button today.

### `CatalogUploadBatch(TenantNumbered)` — prefix `CUB` — bullets 5+1 feed
- `party` FK `"core.Party"` SET_NULL null blank; `file` FileField upload_to
  `procurement/catalog_uploads/%Y/%m/` with curated extension allowlist in `clean()`
  (.csv/.xls/.xlsx/.xml — ProductFile precedent).
- STATUS_CHOICES: `received` → `validated` → `published` / `rejected`; `validated_by/at`.
- Validation stats (editable=False, written by the parse action): `rows_parsed`,
  `rows_accepted`, `rows_rejected` PositiveIntegers default 0; `error_log` TextField blank
  (line-numbered errors — GEP/Ariba pattern). `notes` TextField.
- Action: `validate_and_stage()` parses CSV rows into draft `CatalogItem`s (free-text supplier
  products or SKU-match to `scm.Item`), leaving them `pending_approval` — bullet 3 gates go-live.

REUSE (FK by string, zero re-declaration): `scm.Item`, `scm.UOM`, `scm.ItemCategory` (via
`scm.Item.category` reads), `core.Party`, `accounting.Currency`, `scm.SupplierContract`,
`accounting.PaymentTerm` if needed on tiers. Explicitly NOT reused: `scm.SupplierCatalog*`
(4.2 owns simple price lists; a future provenance FK from CatalogItem to
`"scm.SupplierCatalogItem"` is a documented optional enhancement for scm owners, mirroring
their own L28 docstring), `inventory.ItemPrice`, `crm.PriceBook/Product`.

## 5. Sidebar mapping proposal — future LIVE_LINKS["6.9"] in apps/core/navigation.py

| 6.9 bullet | url name |
|---|---|
| Catalog Item Creation | `procurement:catalog_item_list` |
| Pricing & Tier Management | `procurement:catalog_tier_list` |
| Catalog Approval Workflow | `procurement:catalog_item_list?status=pending_approval` (+ `catalog_tier_list?status=draft` linked from its page) |
| Punch-out Catalog Integration | `procurement:punchout_endpoint_list` |
| Supplier Catalog Hosting | `procurement:catalog_upload_list` |

Detail/form routes follow `<entity>_detail`, `<entity>_create`, `<entity>_update`;
actions POST to `<entity>_action` style urls like rfx issue/close.

## 6. Conventions checklist (captured from committed code)

- Base: `from apps.procurement.models._base import *`; `TenantNumbered` adds
  `NUMBER_PREFIX` + retry-on-collision `save()` via `apps.core.utils.next_number`
  (renders e.g. `PCI-00001`); `unique_together = ("tenant", "number")`.
- Money: `DecimalField(max_digits=14, decimal_places=2)` clamped through `q2()`/MAX_Q2;
  non-negative via `MinValueValidator(ZERO)`.
- Choices as module-level tuple lists (`STATUS_CHOICES`), plus `EDITABLE_STATUSES` /
  LIVE-status tuples; lifecycle methods return False when illegal, stamp `*_at` fields,
  `save(update_fields=[...])`.
- Meta: registers `ordering = ["-created_at", "-id"]`, children domain-ordered; explicit
  prefixed index names (`prc_cat_tnt_status_idx` style); tenant FK uses
  `related_name="+"` in the abstract base — own FKs get explicit namespaced reverse names
  (`rfx_events` → use `procurement_catalog_items` etc.).
- Package layout: `models/CatalogManagement/{__init__,CatalogItems,Tiers,PunchOutEndpoints,UploadBatches}.py`
  re-exported in package `__init__`; siblings `forms/`, `views/`, `urls/` mirror it;
  views import `crud_list`/`paginate` from `apps.core.crud`, filter
  `tenant=request.tenant`, annotate then `.order_by(...)` explicitly.
- Templates: `templates/procurement/catalogmanagement/<entity>/{list,detail,form}.html`
  (lowercase-concatenated submodule dir, cf. `rfxmanagement/events/`).
- Seeder: append `_seed_catalog(self, tenant)` blocks to
  `apps/procurement/management/commands/seed_procurement.py`, each guarded by
  `if Model.objects.filter(tenant=tenant).exists(): skip` (per-entity idempotency);
  guard against missing prerequisites with a friendly skip message ("run seed_scm first").
- Admin registration per model in `apps/procurement/admin.py` (follow RfxEvent pattern).
- Coordination warning: `apps/procurement/urls/__init__.py` is MODIFIED-untracked by the
  parallel 6.7/6.8 session — rebase/merge carefully before wiring urls + LIVE_LINKS["6.9"];
  migrations must be numbered after whatever lands first (0010 exists untracked).

## 7. Surprises affecting scope

1. **SCM 4.2 already shipped a catalog** (`SupplierCatalog`[CAT-]/`SupplierCatalogItem`) —
   biggest duplication trap. 6.9 must be framed as the governed buy-side layer above it, not a
   replacement; document the optional provenance FK rather than editing scm files.
2. **`scm.Item` exists**, so unlike older free-text stand-ins 6.9 can hard-FK the internal item
   master; only supplier-product identity stays free-text.
3. Sell-side look-alikes exist under three names (`inventory.ItemPrice`,
   `crm.PriceBook`, `crm.Product`) — naming collision hazard; keep 6.9 names
   Catalog*/Tier/PunchOut/Upload distinct.
4. Real cXML/OCI punch-out needs signed secrets + SSRF-guarded outbound HTTP (the exact
   machinery CRM webhooks deferred behind) — config-first build keeps bullet 4 honest without
   shipping a fake handshake.

## 8. Build plan appendix (Phase-2 substitute — promoted to todo.md at build start)

Status: research DONE; build QUEUED behind the parallel session's 6.7/6.8 review-fix-test
waves. This appendix is the frozen build contract so any session (or a resumed one) can
execute without re-researching.

### 8.1 Models (package `apps/procurement/models/CatalogManagement/`)

1. **CatalogItem** [PCI-, `CatalogItems.py`] — governed buy-side catalog line.
   Fields: `number` (PCI-#####), `tenant`, `internal_item FK scm.Item NULL`
   (internal path) vs free-text `supplier_product_name/description/supplier_sku`
   (supplier path; L28 stand-in for supplier identity), `supplier FK
   scm.SupplierProfile NULL`, `uom FK scm.UOM NULL`, `currency FK
   accounting.Currency`, `tax_code FK accounting.TaxCode NULL`,
   `unit_price Decimal(14,2)`, `source` choices
   (`internal/supplier/punchout/upload`), `status` machine:
   `draft → pending_approval → approved / rejected → blocked / archived`
   (`approved` is the only punchable/buyable state), `provenance_catalog FK
   scm.SupplierCatalog NULL` (optional documented provenance), `rejected_reason
   Text NULL`, timestamps. Derived: none stored editable.
2. **CatalogPriceTier** [no number, `Tiers.py`] — effective-dated volume break.
   Fields: tenant, `catalog_item FK CatalogItem` (related
   `procurement_price_tiers`), `min_quantity Decimal(12,2)`, `tier_price
   Decimal(14,2)`, `valid_from Date`, `valid_to Date NULL`, `contract FK
   scm.SupplierContract NULL` (contract pricing), `status`
   `draft/approved/retired` (propose→approve so PRICE CHANGES route through the
   approval bullet), `approved_by/at`. Validation: valid_to > valid_from;
   overlapping active tiers warned in views (not hard-blocked).
3. **PunchOutEndpoint** [`PunchOutEndpoints.py`] — per-supplier connection config.
   Fields: tenant, `supplier FK scm.SupplierProfile`, `name`, `protocol`
   choices (`cxml/oci/manual_link`), `punchout_url URL`, `shared_secret` stored
   WRITE-ONLY (prefix+SHA-256 like tenants.EncryptionKey — never plaintext),
   `is_active Bool`, `last_tested_at DT NULL`, `test_status` choices
   (`untested/ok/failed`) — config-only; live handshake explicitly deferred
   (SSRF guard note per CRM webhooks precedent).
4. **CatalogUploadBatch** [CUB-, `UploadBatches.py`] — supplier-hosted file intake.
   Fields: number CUB-#####, tenant, `supplier FK scm.SupplierProfile`,
   `file` (extension allowlist csv/xml via core `_common` ALLOWED_DOC_EXTENSIONS
   pattern), `original_filename`, `status`: `uploaded/validated/failed/staged`,
   `row_count Int`, `error_log Text`, `staged_items_created Int` — validation is
   a parse pass that reports errors and stages DRAFT CatalogItems; it never
   auto-approves.

### 8.2 Routes / templates / wiring

- urls per entity: `<entity>_list/_detail/_create/_update/_delete` (+ POST action
  verbs: `catalog_item_submit/approve/reject/block`, `catalog_tier_approve/retire`,
  `punchout_endpoint_test`(stub marks tested), `catalog_upload_validate/stage`).
- Templates: `templates/procurement/catalogmanagement/{catalogitem,tier,punchoutendpoint,uploadbatch}/{list,detail,form}.html`.
- LIVE_LINKS["6.9"] mapping per §5 above. Admin registers all four models.
- Seeder `_seed_catalog(self, tenant)` in seed_procurement.py: guard per entity;
  needs seeded scm.Item + SupplierProfile rows (friendly skip if absent).

### 8.3 Integration & coordination protocol at build start

1. Confirm no `"6.9"` key and NO catalog commits from the other session (if seen:
   ABORT and report duplicate-build risk).
2. `git rev-parse HEAD` → BASE; claim migration number = highest existing
   procurement migration + 1 (0010 untracked exists → expect 0011+, verify live).
3. Register `build_state.py start --slug procurement --submodule 6.9 --title
   'Catalog Management' --base <BASE> --migration <claimed>`; mark phases as they
   complete (`0_claim 1_research 2_todo 3_build 4_review 5_fix 6_tests 7_docs`).
4. Shared-file edits (re-export blocks, urls/__init__, admin.py, seeder,
   navigation.py) happen ONLY in the solo Integrate phase, surgical Edits only.
5. Review wave `.claude/tasks/review-procurement-6.9.md`; fixer burns findings;
   test wave writes `test_catalogmgmt_{models,forms,views,security}.py`; skill +
   README last. One file per commit throughout; never push.
