# Research — Inventory 5.9 Order Management & Fulfillment (warehouse-ops slice)

Phase-1 output for the 5.9 build. Products surveyed: **SAP EWM**, **D365 SCM**, **Manhattan Active WM**, **NetSuite WMS**, **Blue Yonder WMS**, **Oracle WMS**, **Odoo 17 Inventory**, **ShipStation/ShipEngine/EasyPost** (rate-shop reality check).

## 0. Codebase facts verified this session

- `scm.PickTask.wave_ref` is **free text** (`CharField(40)`), indexed `(tenant, wave_ref)` (`scm_pik_tnt_wave_idx`, scm migration 0006). There is **no `Wave` master anywhere** in `apps/`. "Wave" exists only as a `strategy` enum value (`single/wave/batch/zone`) plus that text ref.
- `scm.PickTask` has **NO FK to SalesOrder** — confirmed independently by `apps/scm/forms/ReturnsManagement/ReturnAuthorizations.py:21`. `scm.Shipment.sales_order` (SET_NULL) links order→shipment, but **order→pick does not exist**. Any "progress from linked picks" can only ride a `wave_ref == <wave code>` text convention (read-only).
- `scm.SalesOrder` statuses: `draft, submitted, on_hold, allocated, partially_fulfilled, fulfilled, invoiced, cancelled, closed`; channels `manual/web/marketplace/edi/api/phone`; credit/fraud hold system-set; allocations live in separate `SalesOrderAllocation` rows.
- `scm.Carrier` [CAR-] is party-backed (required PROTECT `core.Party`) with `primary_mode`, `service_level` (`economy/standard/expedited`), `is_preferred`, status. `CarrierRateCard` = negotiated lane tariffs (audit baseline). **No label generation, no rate-shopping engine** — confirmed.
- `apps/inventory/migrations/`: latest = **0013_shelflifepolicy_lotnumberrule** → **0014 is next free number** (SKILL.md's "0011 taken" note is stale).
- 5.4 reference shape (`PutawayRule`): plain config table, cross-tenant `clean()` keyed on `<name>_id`, ZERO writes into SCM, computed queue page reads spine with preloaded kwargs.

---

## 1. Feature catalog

### Bullet 1 — Sales Order Processing

| Feature | Source product | Status |
|---|---|---|
| Manual order entry (customer, dates, terms) | every OMS | **[BUILT]** `scm:salesorder_*` |
| Channel attribution (web/marketplace/EDI/API/phone) | ShipHero-class e-com OMS | **[BUILT]** `SOURCE_CHANNEL_CHOICES` |
| Quote→order conversion | NetSuite, D365 | **[BUILT]** `create_from_quote` (crm.Quote hand-off) |
| Credit/fraud screening before release | Manhattan, D365 | **[BUILT]** `submit` hold engine |
| Soft allocation / ATP promise | D365 reserve-before-release | **[BUILT]** `SalesOrderAllocation` + form-side ATP |
| Backorder handling | everyone | **[BUILT]** derived `quantity_backordered()` |
| CSV/API channel import | e-com platforms | **[GAP — out of scope]** integration work, not a 5.9 table |

### Bullet 2 — Pick, Pack, Ship workflow

| Feature | Source | Status |
|---|---|---|
| Guided pick lists in bin walk-order | Odoo Barcode, Manhattan | **[BUILT]** `PickTaskLine` ordering by `pick_sequence` + `scm:picktask_*` |
| Single/wave/batch/zone strategies | everyone | **[BUILT as labels]** `strategy` choice; only single-order is truly orchestrated end-to-end |
| Short-pick handling | SAP re-release, Odoo backorder popup, BY short-allocation | **[BUILT]** `shortfall` / `is_short()` |
| Packing capture: package count / weight / tracking ref | everyone | **[BUILT]** recorded-not-generated fields |
| Dispatch, tracking events, POD | Manhattan/D365 | **[BUILT]** 4.6 `Shipment` + append-only `TrackingEvent` + POD |
| Pack-station scan verification (scan each line vs order, discrepancy prompt, carton close) | Odoo Barcode, Deposco | **[GAP — deliberately deferred]** pure UI over existing data; loses to the wave for the one-model slot |

### Bullet 3 — Wave Planning ← THE GAP

| Feature | Source | Status |
|---|---|---|
| **Wave master entity with lifecycle** | SAP `/SCWM/WAVE`, D365 All-waves page, NetSuite wave *transaction*, Odoo wave transfer | **[GAP]** only free-text `wave_ref` exists |
| Lifecycle planned→released→completed/cancelled | D365 `Created→Held→Released→Completed`; NetSuite `Pending Release→Released→auto-Completed`; SAP repeatable release | **[GAP]** |
| Grouping criteria: carrier cutoff, ship method, route/zone, priority, ship date | SAP (activity area/route/completion time), D365 (query filters + wave attributes + thresholds), Oracle WMS "wave search", BY criteria planning | **[GAP]** |
| Templates vs manual creation; scheduled auto-release | SAP wave templates (Automatic/Immediate/Manual), D365 template sequence, NetSuite release schedules (max/min order limits, up to 500 waves/run) | **[GAP — templates out of scope]** one manual master covers tenant need |
| Release creates floor pick work | everyone | **[N/A by ownership]** picks are scm's; release stays governance-only |
| Short-wave handling (partial stock → re-release until complete) | SAP retry interval + repeatable release; BY "no grouping" releases allocated lines immediately | **[GAP]** representable as wave staying `released` until closed; document, don't automate |
| Wave progress % rolling up from pick updates | NetSuite pick-task rollup, D365 wave status board | **[GAP]** derivable READ-ONLY via `wave_ref` match + member-order statuses |
| Thresholds trigger processing (weight/lines/shipments) | D365 wave thresholds | **[GAP — out of scope]** record as criteria text |
| Replenishment triggered by wave | D365 replenish method | **[GAP — out of scope]** reorder lives in 4.3/5.3 |
| Lock/unlock, merge waves, simulate release | SAP, D365 | **[GAP — out of scope]** keep lifecycle minimal |

Odoo nuance worth copying conceptually: its *batch* groups whole pickings; its *wave* splits lines first, accepts only same-operation-type, Ready-state documents, forbids removal once added, and offers backorder creation on shortfall validation. Our analog: membership locked once released (editability window = `planned` only).

### Bullet 4 — Shipping Integration

| Feature | Source | Status |
|---|---|---|
| Carrier master (party-backed, mode/service/compliance) | everyone | **[BUILT]** `scm.Carrier` → `scm:carrier_list` |
| Rate cards per lane/mode | enterprise TMS | **[BUILT]** `CarrierRateCard` |
| Loads/shipments/freight audit → AP bill | D365 load building, Manhattan | **[BUILT]** 4.6 `Load`/`FreightInvoice` |
| Live rate shopping (cheapest/fastest/best-value strategies) | ShipStation Rate Shopper, EasyPost | **[IMPOSSIBLE offline]** research confirms rates→buy-label→tracking-webhook loop is gateway-mediated (carrier accounts + credentials); house posture stays "recorded, not generated" exactly as `PickTask.tracking_ref` already declares |
| Label generation | everyone | **[IMPOSSIBLE offline — same reason]**; a dispatch/label LOG would duplicate PickTask packing fields — do not build a second log |
| On-time scorecard | Manhattan | **[BUILT]** `Carrier.recompute_scorecard()` |

**Conclusion:** bullets 1/2/4 need zero new tables — LIVE_LINKS pointers only. All genuinely-missing substance is bullet 3.

## 2. Recommended build scope — ONE entity: `FulfillmentWave`

### Why this gap (and not a pack station, label log, or import tool)

- Every surveyed system treats the wave as a **first-class document**, not a text tag; here it is a text tag — the weakest possible representation of the one bullet nothing covers.
- A pack-station page adds UX, not data, and would sit beside scm's own pick/pack actions (ownership smell). A label log duplicates `tracking_ref`/packing fields (anti-dedup). Channel import is an integration project. The wave is the only *structural* hole.

### Shape decision: header + child (one concept, one migration)

- **RECOMMENDED — `FulfillmentWave` [WAV-] + `FulfillmentWaveOrder` child** (the house `PickTask`+`PickTaskLine` pattern). The child is what makes the spec'd semantics expressible: PROTECT on the order FK (an order committed to a wave must not vanish silently) and hard `unique (wave, sales_order)`. An implicit M2M can do neither (auto-through rows vanish on either side's delete; no tenant column — repeats the documented `StockTransferLine` filtering gotcha from 5.7).
- Fallback under a literal one-table constraint: implicit `ManyToManyField("scm.SalesOrder")`. Loses PROTECT + per-row tenant. Documented as strictly worse.

Both are **zero writes into scm** (5.4 posture): release/cancel/close flip only the wave's own status; linking picks happens on scm's side by typing `wave_ref = <WAV code>` via `scm:picktask_edit`, or by the seeder walking the real path.

### Field proposal — `FulfillmentWave(TenantNumbered)` [WAV-#####]

```python
NUMBER_PREFIX = "WAV"
STATUS_CHOICES = [("planned", "Planned"), ("released", "Released"),
                  ("closed", "Closed"), ("cancelled", "Cancelled")]
EDITABLE_STATUSES = ("planned",)          # membership/fields locked after release
ACTIVE_STATUSES = ("planned", "released")

status          = CharField(12, choices=STATUS_CHOICES, default="planned", editable=False)
description     = CharField(255, blank=True)
location        = FK("scm.Location", SET_NULL, null=True, blank=True,
                     related_name="fulfillment_waves")            # warehouse root scope
carrier         = FK("scm.Carrier", SET_NULL, null=True, blank=True,
                     related_name="fulfillment_waves")            # optional grouping knob
ship_method     = CharField(12, blank=True, choices=SERVICE_LEVEL_CHOICES)  # import from scm Carriers (one-way dep, Loads.py precedent)
planned_ship_date = DateField(null=True, blank=True)
cutoff_at       = DateTimeField(null=True, blank=True, help_text="Carrier cutoff the release must beat")
priority        = PositiveIntegerField(default=100)             # lower = sooner (PutawayRule precedent)
criteria_text   = TextField(blank=True, help_text="Grouping criteria narrative — no engine claims")
released_at     = DateTimeField(null=True, blank=True, editable=False)
closed_at       = DateTimeField(null=True, blank=True, editable=False)
notes           = TextField(blank=True)

Meta: ordering ["planned_ship_date", "priority", "id"]; unique_together ("tenant", "number")
indexes: ("tenant","status") inv_wav_tnt_status_idx ; ("tenant","planned_ship_date") inv_wav_tnt_date_idx
```

Derived (never stored — the honesty rules):

```python
def member_orders(self):        # via FulfillmentWaveOrder rows
def linked_picks(self):         # scm.PickTask.objects.filter(tenant=..., wave_ref=self.number)
                                # documented convention; rides scm_pik_tnt_wave_idx
def pick_progress(self):        # None when no linked picks (None-vs-zero honesty);
                                # else picked-or-packed picks / picks matched
def member_progress(self):      # None when no members; else share of members in
                                # (partially_fulfilled, fulfilled, invoiced, closed)
def progress_label(self):       # blends both signals for list/board display; "—" when both None
```

### Field proposal — `FulfillmentWaveOrder` child

```python
tenant       = FK("core.Tenant", CASCADE, related_name="fulfillment_wave_orders")  # explicit! lesson from StockTransferLine
wave         = FK("inventory.FulfillmentWave", CASCADE, related_name="orders")
sales_order  = FK("scm.SalesOrder", PROTECT, related_name="inventory_wave_orders")
notes        = CharField(255, blank=True)

unique_together ("wave", "sales_order"); index ("tenant", "sales_order") inv_wvo_tnt_so_idx
```

Verbs on the header (admin-gated writes like 5.3/5.4 rules; members readable):

- `release` — planned→released, stamps `released_at`; refuses zero-member waves; writes NOTHING into scm (the operator's cue to set `wave_ref` on picks).
- `cancel` — active→cancelled (stamps `closed_at`); allowed from planned/released; never touches orders or picks.
- `close` — released→closed once done (manual verdict; SAP/D365 auto-complete needs the order→pick link we deliberately don't own).
- Membership add/remove only while `status == "planned"` (Odoo's lock-after-add lesson, softened).

### Optional computed page — `inventory:wave_board`

One board over the tenant's own waves + read-only pick signal (5.4/5.6 style, dict rows through `apps.core.crud.paginate`):

- Planned/released waves sorted by `planned_ship_date`, `priority`; per-row progress chips from `pick_progress()`/`member_progress()`; overdue flag when `planned_ship_date < today` while still active.
- **Orphan-picks audit** (cheap, genuinely useful): `PickTask`s whose non-blank `wave_ref` matches no `FulfillmentWave.number` — catches typos in the one convention this design depends on.
- Filters `?status=` / `?due=` parsed before pagination. Skip if session budget tight — the wave CRUD triple alone satisfies 5.9.

---

## 3. LIVE_LINKS["5.9"] proposal

```python
# 5.9 Order Management & Fulfillment. Orders/picks/dispatch are SCM documents
# (4.5 SalesOrder, 4.4 PickTask, 4.6 Carrier) - point at them, never re-declare.
# What nothing else provides is the WAVE: a master grouping released-to-floor
# orders, with criteria, cutoffs and derived progress over members + linked picks.
"5.9": {
    "Sales Order Processing":   "scm:salesorder_list",   # bullet (4.5's SO spine owns entry/allocation/backorders)
    "Pick, Pack, Ship":         "scm:picktask_list",     # bullet (4.4 guided picks + packing capture)
    "Wave Planning":            "inventory:wave_list",   # bullet (NEW WAV- master + release verbs; board linked from header)
    "Shipping Integration":     "scm:carrier_list",      # bullet (4.6 carrier master/rate cards; labels stay recorded-not-generated)
},
```

---

## 4. Seeder sketch (`_seed_fulfillment(tenant)` in seed_inventory)

Guard: `FulfillmentWave.objects.filter(tenant=tenant).exists()` → skip (marker-based like every entity).

Reuses seed_scm demo data (parties/SOs already exist there):

1. **WAV demo A — released with partial progress**: 2–3 `submitted`/`allocated` SOs as members; create ONE `scm.PickTask` through the real path (`strategy="wave"`, two lines off stocked items, `wave_ref="WAV-00001"`), walk it to `picking` with one line short-picked → exercises `pick_progress()`, shortfall display, and the `wave_ref` linkage convention end-to-end.
2. **WAV demo B — planned**: members only (one `submitted` SO + one `draft` SO to show mixed states), `criteria_text` narrative, `carrier` = seeded preferred CAR party, `cutoff_at` tomorrow 12:00 → exercises member-only progress and editability window.
3. **WAV demo C — cancelled**, one member → lifecycle coverage for badges/filters.
4. Leave at least one existing PIK task's `wave_ref` untouched/unlinked so the orphan audit has something honest to show only if a *typo* row is added deliberately (skip if noisy).

---

## 5. Risks & gotchas

1. **No order→pick FK exists** — progress via `wave_ref == number` is a TEXT CONVENTION. Case-sensitive equality; document on the detail page; the board's orphan audit is the safety net. Do not invent an scm-side FK in this build (that would be a scm migration).
2. **Zero-writes discipline** — release/cancel/close touch only inventory rows. Tempting shortcut "release creates PickTasks" violates 5.4 posture; refuse it.
3. **Cross-tenant guards** — form `_reject_foreign` on `location`/`carrier`/`sales_order` keyed on `<name>_id` (review finding C1 pattern) so unset required FKs render "required", not 500. Views filter `tenant=request.tenant`; `request.tenant_id` DOES NOT EXIST (shipped once here already).
4. **PROTECT side-effect** — deleting an SO that sits in any wave raises ProtectedError. Acceptable (it's the point); make sure delete confirmations on scm pages aren't blamed — surface a friendly message if any view wraps it.
5. **TenantUniqueMixin / two jobs** — coordinate the **0014** migration claim across concurrent sessions (check `apps/inventory/migrations/` immediately before `makemigrations`). Child table needs its own explicit `tenant` column + tenant predicate in every aggregate (`StockTransferLine` lesson).
6. **None-vs-zero honesty** — both progress helpers return `None` when their signal set is empty (mirrors `Carrier.recompute_scorecard` refusing phantom zeros). Templates must render "—"/muted chip, never `0%`.
7. **Status off the form** — status flips ONLY via locked verbs (RSV precedent); forms exclude it; list/detail badges driven by `STATUS_CSS` colour names only.
8. **Editability window** — membership mutations blocked once released; enforce in form+view+model.clean (three layers, house style).
9. **Odoo lesson encoded** — same-operation-type rule ≈ our single operation domain already; "cannot remove from wave" → our planned-only window; backorder-on-shortfall stays scm's job (SO allocations), do not duplicate.

## Facts contradicting the given context

- None material. Two precision fixes: (a) SKILL.md says "0011 taken; check before generating" — actual next number is **0014** as the task claimed, confirmed by listing `apps/inventory/migrations/`. (b) The task's "derived progress from linked PickTasks if any exist" needs the caveat above: linkage is conventional (`wave_ref` text), not structural — no order→pick FK exists anywhere in scm. Also noted: `PickTasks.py` docstring still claims SalesOrder "belongs to Module 8 and is not built" — stale comment since 4.5 shipped; harmless but worth knowing when reading that file.

