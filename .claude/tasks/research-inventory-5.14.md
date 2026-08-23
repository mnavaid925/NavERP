# Research — Inventory 5.14 Barcode & RFID Integration

Phase-1 output for the 5.14 build. Products surveyed: **Zebra Technologies (ZebraDesigner Pro 3 + ZT411 RFID printer)**,
**BarTender (Seagull Scientific)**, **Odoo Inventory Barcode**, **NetSuite WMS (+ RF-SMART)**, **SAP EWM (HU/SSCC label handling)**,
**Manhattan Associates WMS**, **Fishbowl Inventory**, **Sortly**, **inFlow Inventory**, and the **RAIN-RFIID/EPC solution layer**
(Impinj-class UHF Gen2 practice: commissioning → bulk reads → last-seen reconciliation).

## 0. Codebase facts verified this session

- The item/location spine is SCM's (L29/L36): `scm.Item` (`sku`, unique `(tenant, sku)`, CharField(64); tracking
  none/lot/serial), `scm.Location` (`code`, unique `(tenant, code)`, self-FK warehouse tree + `path()`),
  `scm.LotSerial` (`number`, unique `(tenant, item, number)`, status available/quarantine/expired/consumed).
  **`scm.Item` has NO barcode/GTIN column** — resolution must run on `sku` / `Location.code` / `LotSerial.number`
  (+ EPC for tags). Adding an additive column to the spine is possible but out of scope here.
- **No Pallet/LicensePlate/HU master exists anywhere in `apps/`** (SAP's Handling Unit and NetSuite License Plating have
  no analog). L28 stand-in decision: labels and tags carry a **free-text `pallet_ref`**; migrate to a real FK the day a
  pallet master lands.
- House bases confirmed (`apps/inventory/models/_base.py`): `TenantOwned` and `TenantNumbered` (`NUMBER_PREFIX`,
  retry-on-collision `save()`). Prefixes already taken in this app: RSV, RMI, WAV, XD, SLP, VC, PD, PHY, PA, CTP, TA —
  **LBL / SSN / TAG are all free**.
- Views house style (`apps/inventory/views/_common.py` + `apps/core/crud.py`): `crud_list/create/detail/edit/delete`
  (with `search_fields`, `filters`, `paginate(request, qs, per_page=15)` inside), `as_db_int(value)`,
  `write_audit_log(user, obj, action, changes)` from `apps/core/utils`. Reference shape:
  `views/StocktakingCycleCounting/CountPrograms.py` (CRUD + one bespoke POST verb).
- URL package concatenates per-entity `urlpatterns`; first-match-wins; **no greedy `<str:…>` converter anywhere** — new
  literal segments (`labels/`, `scan/`, `rfid-tags/`) are distinct whole components.
- Sidebar wiring = one `LIVE_LINKS["5.14"]` dict entry in `apps/core/navigation.py` (pattern at lines 1258-1286).
- `python-barcode==0.16.1` + `qrcode==8.2` are installed in the venv; **both render SVG without Pillow**
  (`barcode.get('code128', value, writer=SVGWriter())`, `qrcode.image.svg.SvgPathImage`) — Pillow is present anyway
  (requirements.txt line 7) so PNG is available later if ever needed. `requirements.txt` must gain exactly two lines.
- Latest inventory migration is past 0014 (5.11 landed); claim the next free number in Phase 0 per CLAUDE.md.

---

## 1. Product survey — what the leaders actually do

| Product | Label design | Scan console | RFID | Integration surface |
|---|---|---|---|---|
| **Zebra ZebraDesigner Pro 3 + ZT411 RFID** | Office-style template designer; pre-built templates; GS1-128 wizard with Application Identifiers + check-digit modes; symbology catalog spans Code39/Code128(A/B/C), EAN13(+addons), UPC-A/E, QR/MicroQR, DataMatrix (ECC levels), PDF417 | n/a (design tool) | Print-and-encode on the printer: UHF EPC Gen2 v2.1, adaptive encoding, min 16 mm tag pitch; RF-tag dialog picks tag type/blocks | Printer-driver/ZPL centric; data from Excel/ODBC |
| **BarTender (Seagull)** | Intelligent Templates, 100+ symbologies, data-driven variations from one template | n/a | RFID objects on templates encode smart labels as easily as barcodes; smart cards too | 20+ ERP/WMS connectors, REST; **role-based permissions + print LOGGING/tracking for compliance** |
| **Odoo Inventory Barcode** | Barcode field on product/packaging/**location**; label wizard prints N copies (qty-driven); multi-label sheets | Scan console drives receipts/pickings/transfers/counts; **barcode nomenclature rules** parse GS1 AIs; unknown product → "does not exist" + Create button; internal codes (INT000001) recommended when vendor codes absent | None native | Keyboard wedge + mobile app; Enterprise-only |
| **NetSuite WMS (+RF-SMART)** | Mobile printing generates **GS1 DataMatrix only** with a fixed AI whitelist (item, GTIN, qty, UoM, lot, expiry, serial); standard label/template library | RF handheld flows: receiving (**force-scan** best practice), putaway, single/multi-order picking, pack station, Smart Count; **continuous scanning of lot/serialized items**; tally scanning across item types; HIBC supported for returns receiving | **License Plating**: ~5,000 pallets created via LP in one cited deployment; LP travels receiving→storage→outbound | RF devices over Wi-Fi posting real-time to ERP; third-party layers buffer/batch idempotently |
| **SAP EWM** | HU (Handling Unit) labels carry SSCC-18; VL74 output; PPF action profile `/SCWM/HU` auto-prints HU labels on packing; print-determination procedure assigned per packaging material type | RF/MFS guided tasks everywhere | HU = pallet/carton master WITH unique number — traceability across inbound/outbound/internal | Output management + external form systems (StreamServe) |
| **Manhattan Associates WMS** | Mature print/label management through integration layer; enterprise DC scale | RF task interleaving, putaway/pick/count validation scans | Full RFID support in Active WM | Deep integration surface |
| **Fishbowl Inventory** | Barcode/label generation from item records; Fishbowl Go mobile scanning | Scan-based cycle counts, receiving, picking across the warehouse | Barcoding(RFID) listed as common feature tier | QuickBooks/accounting-centric integrations |
| **Sortly** | QR/barcode label generation incl. custom labels + label templates; printable QR sheets | Mobile camera/scanner app check-in/out; scan-to-view item | Barcoding/RFID feature flags | Cloud/mobile-first |
| **inFlow Inventory** | "Generate barcodes and labels" from the product; symbology choice at print time | Scan to pick/receive/transfer/ship on any device | Listed capability only | API add-on |
| **RAIN RFID / EPC practice (Impinj-class)** | Tag commissioning = assign unique EPC then attach | Handheld bulk reads: 500+ tags < 3 s; fixed dock-door portals read pallets without unpacking; ASN vs read discrepancy flagged instantly | **EPC unique per object; passive (UHF 860–960 MHz, EPCglobal Class1 Gen2/ISO 18000-6C) vs active (battery beacons)**; lifecycle unassigned→commissioned→retired; reads update last-seen location; software reconciles reads against inventory records | Reader→middleware→ERP/WMS sync |

### Recurring patterns (deduplicated)

1. **Label register**: every serious system treats a printed label as a *record*, not just pixels — symbology chosen
   per purpose (linear Code39/Code128/EAN13 for product & bin; QR/DataMatrix when payload grows), payload assembled from
   master data but reviewable before print, copies count, and a **who-printed-what-when log** (explicit BarTender
   compliance feature; SAP keeps output records).
2. **Resolve-on-scan console**: a session context (device/user) receives raw strings; each is matched tenant-scoped
   against masters (item sku / location code / lot number / EPC); unknowns are *surfaced, not silently dropped*
   (Odoo's create-or-warn; NetSuite force-scan refuses unvalidated advance); batch/paste-many mode exists for rapid
   receiving and counting; every scan lands in an event trail.
3. **RFID registry**: uniqueness of the EPC is THE constraint (it is a license plate); passive-vs-active is a
   classification; tags have an assign/commission → retire lifecycle plus a lost state; bulk reads update last-seen
   time+location snapshots and feed discrepancy detection.
4. **Integration reality**: the web-app pattern is keyboard-wedge/console (scanner types into a browser field) or an
   HTTP endpoint for bulk reads. Server-side printer drivers, ZPL spooling, and reader SDKs belong to desktop/integration
   middleware, not to an ERP web module.

---

## 2. Feature catalog → NavERP 5.14 bullets

Bullet texts: *Label Generation · Mobile/Handheld Scanner Integration · RFID Tag Management · Batch Scanning.*

### Bullet 1 — Label Generation ← BarcodeLabel [LBL-]

| Feature | Source | Status / disposition |
|---|---|---|
| Symbology choice incl. Code39, Code128, EAN13, QR | Zebra catalog, Odoo, BarTender | **[BUILD]** `symbology` choices; python-barcode covers code39/code128/ean13, qrcode covers qr — both SVG, no rasterizer needed |
| Payload auto-built from target master data, editable before print | BarTender data-driven, SAP output determination | **[BUILD]** default payload per target type (item→sku, location→full path code, lot→item-sku·number); editable field, re-rendered live by the render endpoint |
| Target kinds: product / bin / pallet / generic | everyone (bin labels are Odoo standard; pallet=SSCC/HU/LP in SAP/NetSuite) | **[BUILD]** `target_type(item/location/lot/free)` + nullable FKs + free-text ref; `label_kind(product/bin/pallet/generic)` is the print-purpose tag; **pallet rides the L28 `pallet_ref` stand-in** |
| Copies per print | Odoo qty-driven wizard, everyone | **[BUILD]** `copies` PositiveSmallIntegerField (cap 500) |
| Print log: who printed what when | BarTender compliance logging, SAP output records | **[BUILD]** status draft→printed→void with `print()` verb stamping `printed_at`/`printed_by`; void allowed while draft/printed; audit-log hook as usual |
| Rendered label image served by the server | all (their engines render; ours renders SVG) | **[BUILD]** `labels/<pk>/render.svg` view returning `image/svg+xml`; print page lays out `copies` frames of the same SVG for browser printing |
| Free-form designer canvas (drag/drop, fonts, logos) | ZebraDesigner, BarTender | **[NOT BUILT]** a designer is a product; our register prints a clean standard frame |
| GS1-128 Application-Identifier parser/nomenclature engine | Odoo nomenclature rules, NetSuite AI whitelist | **[DEFERRED]** plain-text payloads only; parsing scanned GS1 strings into structured lots/expiry is a future sub-module |
| Additive `barcode` column on `scm.Item` (vendor GTIN) | Odoo/Netsuite store it on the item | **[DEFERRED]** spine edit; resolve-on-scan uses `sku` today — note as the natural 5.x follow-up |

### Bullet 2 — Mobile/Handheld Scanner Integration ← ScanSession [SSN-] + ScanEvent

| Feature | Source | Status / disposition |
|---|---|---|
| Session context: device + user + open/close | RF handheld logins (NetSuite/SAP RF sessions) | **[BUILD]** `device_label` free text ("Zebra TC22 #3"), `status(open/closed)`, `started_at`/`ended_at` |
| Resolve raw scan against item/bin/lot masters, tenant-scoped | every WMS console | **[BUILD]** match order: `Item.sku` → `Location.code` → `LotSerial.number` → `RfidTag.epc`; exact match after trim; case-insensitive fallback documented |
| Unknown-code surfacing | Odoo "does not exist" + create prompt; NetSuite force-scan refusal | **[BUILD]** event rows with `resolved_kind='unknown'`, `ok=False`; console highlights them; no silent drop, no inline master creation (keeps the console read-mostly) |
| Batch/paste-many mode | NetSuite continuous/tally scanning; Odoo batch | **[BUILD]** (bullet 4) `mode(single/batch)`; textarea accepts newline-separated codes, split server-side, capped per POST |
| Event trail of every scan | implied everywhere; explicit in middleware layers | **[BUILD]** `ScanEvent(session FK, raw_code, resolved_kind(item/location/lot/rfid/unknown), resolved_id, ok, scanned_at)` — append-only, no edit/delete routes |
| Offline queue / buffering / idempotent replay | Cleverence-style offline engines | **[NOT BUILT]** online-only console; paste-many absorbs flaky-WiFi gaps well enough for a web module |
| Force-scan workflow enforcement per operation type | NetSuite force-scan, RF-SMART validation | **[NOT BUILT]** 5.14 observes and registers; driving receipts/picks by scan belongs to scm's documents (L36) |

### Bullets 3+4 — RFID Tag Management & Batch Scanning ← RfidTag [TAG-]

| Feature | Source | Status / disposition |
|---|---|---|
| Unique EPC per tenant | EPC license-plate principle; patent literature on serialization discipline | **[BUILD]** `unique_together (tenant, epc)`, normalized upper/trim on save |
| Passive vs active kind | Wasp/AssetVue/RAIN taxonomy | **[BUILD]** `kind(passive/active)` |
| Tagged-target linkage (what the tag is ON) | commissioning step in every RFID stack | **[BUILD]** nullable item/location/lot_serial FKs + free-text `ref` + `pallet_ref` stand-in (L28) |
| Lifecycle: unassigned→active→retired (+lost) | Wasp commissioning/retire; EPC reuse-after-retirement debate | **[BUILD]** `status(unassigned/active/retired/lost)` + verb methods `assign()/activate()/retire()/mark_lost()` under `transaction.atomic()` guards refusing illegal transitions (retired is terminal; lost reachable only from active) |
| Bulk-read ingestion updating last-seen | dock-door/handheld reads → middleware → ERP | **[BUILD]** POST list-of-EPCs endpoint: normalize, match registered tags, stamp `last_seen_at` + optional `last_seen_location` FK snapshot; report known/unknown counts; unknowns optionally recorded as ScanEvents(kind=rfid, ok=False) when posted from a session |
| Discrepancy detection reads-vs-records | InvenTrack/BarcodeIndia validate ASN vs reads | **[READ-ONLY]** detail pages show tag vs target; full reconciliation joins 5.11 counting — defer |
| Read-write tag memory / encoding at print | Zebra adaptive encoding, BarTender RFID objects | **[NOT BUILT]** hardware-side concern; registry stores the identity only |
| Fixed-reader portal streaming APIs | Impinj/zebra IoT stacks | **[NOT BUILT]** paste/POST ingestion only |

---

## 3. Recommended build scope — THREE entities, one migration

Sub-module package name: `apps/inventory/models/BarcodeRfidIntegration/{BarcodeLabels,ScanSessions,RfidTags}.py`
(mirrored in forms/views/urls). Template root slug: `templates/inventory/autoid/…` (matches short-slug siblings
`lottrack`, `stocktake`). All three extend `TenantNumbered` except ScanEvent (child of a numbered parent).

### 3.1 `BarcodeLabel(TenantNumbered)` [LBL-#####]

```python
NUMBER_PREFIX = "LBL"
TARGET_TYPES = [("item", "Item"), ("location", "Location"),
                ("lot", "Lot / Serial"), ("free", "Free text")]
SYMBologies  = [("code39", "Code 39"), ("code128", "Code 128"),
                ("ean13", "EAN-13"), ("qr", "QR Code")]
LABEL_KINDS  = [("product", "Product"), ("bin", "Bin"),
                ("pallet", "Pallet"), ("generic", "Generic")]
STATUSES     = [("draft", "Draft"), ("printed", "Printed"), ("void", "Void")]

label_kind    CharField(10, choices=LABEL_KINDS, default="product")
target_type   CharField(10, choices=TARGET_TYPES)
item          FK("scm.Item", SET_NULL, null=True, blank=True, related_name="barcode_labels")
location      FK("scm.Location", SET_NULL, null=True, blank=True, related_name="barcode_labels")
lot_serial    FK("scm.LotSerial", SET_NULL, null=True, blank=True, related_name="barcode_labels")
target_ref    CharField(64, blank=True)     # free-text target when target_type='free' or FK-less
pallet_ref    CharField(64, blank=True)     # L28 stand-in until a pallet master exists
symbology     CharField(10, choices=SYMBOLOGIES, default="code128")
payload       CharField(255)                # auto-defaulted per target on clean(); editable before print
copies        PositiveSmallIntegerField(default=1, validators=[MaxValueValidator(500)])
status        CharField(10, choices=STATUSES, default="draft", editable=False)
printed_at    DateTimeField(null=True, blank=True, editable=False)
printed_by    FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, editable=False,
                 related_name="+")
notes         TextField(blank=True)

def default_payload(self): …                 # item→sku; location→path() head code; lot→f"{sku}·{number}"; free→target_ref
def print(self, user): …                     # refuse void; stamp status/printed_at/by; write_audit_log("print")
def render_svg(self) -> str: …               # python-barcode SVGWriter / qrcode SvgPathImage; ean13 validates 12 digits

Meta: ordering ["-created_at"]; unique_together ("tenant", "number")
indexes: ("tenant","status") inv_lbl_tnt_status_idx ; ("tenant","label_kind") inv_lbl_tnt_kind_idx
```

### 3.2 `ScanSession(TenantNumbered)` [SSN-#####] + `ScanEvent`

```python
NUMBER_PREFIX = "SSN"
MODES    = [("single", "Single scan"), ("batch", "Batch / paste-many")]
STATUSES = [("open", "Open"), ("closed", "Closed")]

device_label CharField(60)                  # "TC22-03", "Dock laptop 2" — free text, no device master
mode         CharField(8, choices=MODES, default="single")
status       CharField(8, choices=STATUSES, default="open", editable=False)
started_at   DateTimeField(auto_now_add=True, editable=False)
ended_at     DateTimeField(null=True, blank=True, editable=False)
notes        CharField(255, blank=True)

def close(self, user): …                    # refuse double-close; stamp ended_at/status; audit log

class ScanEvent(TenantOwned):               # child; append-only — NO edit/delete views, ever
    RESOLVED_KINDS = [("item","Item"),("location","Location"),("lot","Lot / Serial"),
                      ("rfid","RFID tag"),("unknown","Unknown")]
    session     FK(ScanSession, CASCADE, related_name="events")
    raw_code    CharField(120)              # length-capped; echoed ONLY through escaped templates
    resolved_kind CharField(10, choices=RESOLVED_KINDS, default="unknown")
    resolved_id IntegerField(null=True, blank=True)   # pk of the matched row, if any
    ok          BooleanField(default=False)
    scanned_at  DateTimeField(auto_now_add=True, editable=False)

Meta(event): ordering ["scanned_at"]; index ("tenant","session") inv_sce_tnt_session_idx
```

Resolution helper lives on the model manager/module: `resolve_code(tenant, raw) -> (kind, obj_or_None)` trying
`Item.sku`, `Location.code`, `LotSerial.number`, `RfidTag.epc` in order — one place, unit-testable.

### 3.3 `RfidTag(TenantNumbered)` [TAG-#####]

```python
NUMBER_PREFIX = "TAG"
KINDS    = [("passive", "Passive (UHF)"), ("active", "Active (battery)")]
STATUSES = [("unassigned", "Unassigned"), ("active", "Active"),
            ("retired", "Retired"), ("lost", "Lost")]
ACTIVE_STATUSES = ("unassigned", "active")

epc            CharField(32)                # normalized .strip().upper() in save(); hex charset validator
kind           CharField(8, choices=KINDS, default="passive")
item           FK("scm.Item", SET_NULL, null=True, blank=True, related_name="rfid_tags")
location       FK("scm.Location", SET_NULL, null=True, blank=True, related_name="rfid_tags")
lot_serial     FK("scm.LotSerial", SET_NULL, null=True, blank=True, related_name="rfid_tags")
target_ref     CharField(64, blank=True)
pallet_ref     CharField(64, blank=True)    # L28 stand-in, same rationale as BarcodeLabel
status         CharField(12, choices=STATUSES, default="unassigned", editable=False)
last_seen_at   DateTimeField(null=True, blank=True, editable=False)
last_seen_location FK("scm.Location", SET_NULL, null=True, blank=True,
                      related_name="rfid_last_seen_tags")

VERBS (each @classmethod-safe instance method wrapped in transaction.atomic(), refusing illegal moves):
assign(target…) -> sets FKs, status stays/returns active; activate() unassigned→active;
retire() any non-retired→retired (terminal; clears nothing history-wise);
mark_lost() active→lost; record_read(location=None) stamps last_seen_at(+location snapshot)

Meta: ordering ["epc"]; unique_together ("tenant", "epc"); index ("tenant","status") inv_tag_tnt_status_idx
```

### 3.4 URLs (`urls/BarcodeRfidIntegration/…`, concatenated in `urls/__init__.py`)

```
labels/                          inventory:label_list        crud_list (search: payload/target_ref/pallet_ref/item__sku; filters: status, kind)
labels/add/                      inventory:label_create
labels/<int:pk>/                 inventory:label_detail      (preview SVG + print sheet link)
labels/<int:pk>/edit/            inventory:label_edit        (draft only)
labels/<int:pk>/delete/          inventory:label_delete      POST
labels/<int:pk>/print/           inventory:label_print       POST verb
labels/<int:pk>/render.svg       inventory:label_render      GET → HttpResponse(svg, content_type="image/svg+xml")
scan/                            inventory:scan_list         sessions list
scan/add/                        inventory:scan_create
scan/<int:pk>/                   inventory:scan_detail       + close verb
scan/<int:pk>/close/             inventory:scan_close        POST
scan/<int:pk>/delete/            inventory:scan_delete       POST
scan/console/                    inventory:scan_console      THE page: textarea + live resolve table
scan/console/resolve/            inventory:scan_resolve      POST {codes, session} → JSON rows + persists events
rfid-tags/                       inventory:tag_list
rfid-tags/add/                   inventory:tag_create
rfid-tags/<int:pk>/              inventory:tag_detail
rfid-tags/<int:pk>/edit/         inventory:tag_edit          (fields only; verbs below)
rfid-tags/<int:pk>/delete/       inventory:tag_delete        POST
rfid-tags/<int:pk>/<verb>/       inventory:tag_activate/tag_retire/tag_lost   POST verbs
rfid-tags/bulk-read/             inventory:tag_bulkread      page + POST ingest (list of EPCs, optional location)
```

Templates: `autoid/{label,scansession,rfidtag}/{list,detail,form}.html`, `autoid/label/print.html`
(N copies of the same SVG frame), `autoid/scansession/console.html`, `autoid/rfidtag/bulkread.html`.
Seeder: 6-10 labels across targets, one open + one closed session with mixed events (incl. an unknown),
tags covering passive/active × unassigned/active/retired/lost. LIVE_LINKS `"5.14"` maps the four bullets to
`inventory:label_list` (Label Generation), `inventory:scan_console` (Scanner Integration), `inventory:tag_list`
(RFID Management), `inventory:tag_bulkread` (Batch Scanning). requirements.txt gains
`python-barcode==0.16.1` + `qrcode==8.2`.

---

## 4. Risks & guardrails (write these into the build)

- **SVG content-type response**: return `HttpResponse(svg_bytes, content_type="image/svg+xml")` with the tenant check
  INSIDE the view (`get_object_or_404(BarcodeLabel, pk=pk, tenant=request.tenant)` — IDOR otherwise). Never wrap user
  text into `<text>` without escaping; build SVG via the libraries' writers and inject human-readable lines with
  `django.utils.html.escape`. `ean13` raises on non-12-digit input — convert to `ValidationError` in `clean()`, not a 500
  at render time.
- **XSS via raw_code echo**: scanner input is attacker-controlled text. Cap `raw_code` at 120 chars, strip control
  characters before save, and echo ONLY through Django template autoescaping — never `|safe`, never a JSON blob injected
  via innerHTML client-side. The resolve endpoint returns data consumed by templates that escape.
- **EPC normalization**: `.strip().upper()` on save (LotNumberRule.prefix precedent) BEFORE uniqueness is enforced;
  reject empty and non-hex (`^[0-9A-F]{8,32}$`) so `epc-001` junk never enters the registry. Bulk-read normalizes the
  same way so a lowercase paste still matches.
- **Batch caps**: split paste-many on newlines, hard cap events per POST (e.g. 300) with a flash message when truncated —
  a 50k-line paste must not become a 50k-row INSERT storm.
- **Zero stock writes (L37)**: 5.14 records observations and prints identifiers. It posts NO StockMove, touches no
  on-hand aggregate, writes nothing outside `apps/inventory` + its own tables.
- **No greedy route risk**: all new segments are literal prefixes (`labels/`, `scan/`, `rfid-tags/`) distinct from every
  existing first segment; keep `render.svg` AFTER `<int:pk>` literals as shown.

## 5. What NOT to build

- **No printer-driver / ZPL / ESC-POS integration, no hardware SDKs** — the browser print sheet over SVG IS the output;
  thermal printers accept browser/system print paths like any web app.
- **No device master, no reader/portal streaming APIs** — `device_label` free text; bulk ingestion is paste/POST.
- **No Pallet/Handling-Unit/License-Plate master** — L28 stand-in `pallet_ref` free text on both label and tag; revisit
  when a pallet model exists anywhere.
- **No GS1/AI nomenclature parser, no DataMatrix/PDF417 rendering** — plain-text payloads; python-barcode/qrcode cover
  the four chosen symbologies.
- **No camera-based in-browser scanning** and no offline queue engine — keyboard-wedge/console pattern only.
- **No scan-driven document enforcement** (force-scan receiving etc.) — scm owns those documents (L36).
