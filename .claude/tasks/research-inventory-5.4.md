# Research — Inventory 5.4 Receiving & Putaway

Phase-1 feature catalog for the 5.4 build (one new tenant-scoped model + one computed page in
`apps/inventory`). Research-only output; feeds the `todo` agent.

## Method & products surveyed

Receiving-and-putaway specifically (not generic WMS), across ~10 products:

| Product | What was examined |
|---|---|
| **SAP EWM** (+ classic WM) | putaway rules per storage type (empty bin / addition to existing stock / general storage area / consolidation group); storage-type search sequence; strategies: fixed bin, near-picking-bin, open storage, bulk, pallets; putaway control indicator on the product master; capacity check modes; max-bins-per-product; split-during-putaway; sort-field ordering of the empty-bin search |
| **Microsoft Dynamics 365 SCM** (advanced warehousing) | work templates + location directives with directive codes; query-ordered candidate locations; location-profile max qty/volume/weight enforced at put ("if putaway can't find a location, check whether locations are simply considered full"); item default putaway location per warehouse |
| **Odoo Inventory** | the closest open-model analog: the **Putaway Rule** model (product/product-category → "Store To" destination, triggered "when product arrives in" a location) plus **Storage Categories** (capacity by weight/product/package + Allow-New-Product policy if-empty/if-same/mixed) |
| **Manhattan Associates WMS / Active WM** | directed-putaway algorithms, velocity zone logic, hazmat segregation, FIFO/FEFO rotation, ASN/blind receiving, cross-dock |
| **Blue Yonder Advanced Slotting** | AI/ML continuous slotting optimization (directory-level detail) |
| **Körber K.Motion / HighJump**, Made4net | rule-engine putaway, dynamic velocity slotting (directory-level) |
| **Fishbowl Inventory** | default receiving location per location-group unless the part has its own default location; mobile scan displays designated section/aisle/shelf/bin (suggestion UX) |
| **Finale Inventory (Descartes)** | two-step receive-to-dock then transfer-to-bins workflow |
| **EasyEcom** | GRN-triggered PutAway queue; QC-status-aware zone mapping (QC Pass → normal bins, Damaged/Quarantine → "Bad Zone" bins); **"No Suggestion Found"** honesty when no mapped bin exists |

Plus one practitioner source articulating the generic directed-putaway algorithm every vendor
implements: **Step 1 SKU profile lookup → Step 2 slot availability check (open, correctly sized,
not at capacity, storage-compliant) → Step 3 business rules** (ABC zone assignment, FIFO/FEFO,
family grouping, hazmat segregation). Same source names the cost of *not* doing this:
undirected putaway produces "ghost inventory".

---

## 1. Feature catalog, deduplicated, mapped to NavERP.md's four 5.4 bullets

### Bullet 1 — Goods Receipt Note (GRN): recording received items against a specific PO

| Feature | Status |
|---|---|
| Receive items against a purchase order | **[BUILT via `scm:goodsreceipt_create` / `scm:goodsreceipt_receive`]** — `scm.GoodsReceiptNote` [GRN-] + lines |
| Goods land in a staging/dock location on receipt | **[BUILT]** — staging/receiving location on the GRN header; posting goes through the 4.3 service |
| Put-away queue appears after GRN completion (EasyEcom pattern) | **[BUILT]** — open `PutawayTask`s are exactly that queue; the computed page below reads it |
| ASN-driven receiving (pre-advice vs blind count) | **[OUT OF SCOPE]** — no ASN master exists anywhere; scm owns procurement documents. PO receipt is the trigger here |
| Damage capture at receipt | **[BUILT-lite]** — notes fields + 4.9 QMS inspections; not this build's gap |

### Bullet 2 — Three-Way Matching: matching PO, GRN, Vendor Invoice

| Feature | Status |
|---|---|
| PO vs GRN vs Invoice match with tolerance | **[BUILT]** — `match_status` machine (`not_matched/matched/price_variance/quantity_variance/over_received`) on the GRN, 2% price tolerance vs `accounting.Bill`, `recompute_match()` |
| Manual re-match action | **[BUILT via `scm:goodsreceipt_rematch`]**
| Tolerance policy as configurable data | **[GAP — defer]** — the 2% is a class constant; making tolerance tenant-editable is an accounting-side concern, not worth an inventory table |

D365's invoice-matching (two-way/three-way with tolerance groups) is the same concept already
shipped. Nothing in the research argues for re-opening bullet 2.

### Bullet 3 — Quality Inspection (Receiving): accept / reject / quarantine

| Feature | Status |
|---|---|
| Receipt-triggered inspection plans | **[BUILT via `scm:inspectionplan_list`]** (4.9 QMS) |
| Accept / reject / quarantine decisions on incoming goods | **[BUILT via `scm:qualityinspection_decide` / `_quarantine` / `_release_lot` / `_raise_ncr`]** |
| QC-status-aware putaway routing (failed stock only into quarantine-capable bins — EasyEcom's "Bad Zone" mapping) | **[GAP — out of scope for v1]** — the QMS release/quarantine flow owns that hand-off; a suggestion engine should simply never propose a destination while stock is held, which falls out naturally because quarantined goods have no open directed putaway task |

### Bullet 4 — Putaway Logic: system-guided suggestions for the optimal bin/location ← **THE GENUINE GAP**

`PutawayTask.strategy = "directed"` is commented *"system suggests the bin"* but grep confirms no
suggestion logic exists anywhere; `to_location` is hand-picked today, and there is not even a
create-task-from-receipt flow (`PutawayTask(` appears only in the seeder and tests).

Researched capabilities, deduplicated:

**a) Rules configuration object (how real products persist intent)**
- Odoo **Putaway Rule**: product *or* product-category → destination location, optionally
  triggered by arrival location; resolution priority is most-specific-wins
  (product > category > catch-all empty rule; the empty catch-all is documented best practice).
  Rules are ordinary CRUD rows.
- SAP EWM: putaway control indicator on the product + storage-type search sequence; per-area
  strategies (fixed bin / empty bin / addition-to-existing-stock / near-picking-bin).
- D365: **location directives** — ordered, named, query-based records with directive codes.
- EasyEcom: SKU/bin mappings consulted at put-away time.

→ **[GAP]** — this is the missing table.

**b) Slotting inputs feeding suggestions — most ALREADY EXIST as spine columns**
- Bin ABC velocity class (`Location.abc_class`) — data exists, engine doesn't use it.
- Walk order (`Location.pick_sequence`) — data exists.
- Capacity limit (`Location.capacity`, blank = unlimited) + derived on-hand per location from the
  StockMove ledger — data exists; D365's lesson: a "no location found" is usually just full bins.
- Storage-condition pair: `scm.Item.storage_condition` (requirement) vs
  `scm.Location.storage_condition` (provision) — both columns shipped (4.15 precedent);
  matching them needs zero schema change.
- Consolidation preference ("addition to existing stock", SAP's second putaway rule): prefer a bin
  already holding the item — derivable from derived on-hand.
- Dedicated-space respect: `owner_client` on Location/Item (4.17) — don't suggest another client's
  aisle.

→ enforcement of all of these at suggestion time is **[GAP]**.

**c) Suggestion UX**
- Proposed destination shown to the operator with override (Odoo suggests on the move line; D365
  mobile directs the put; Fishbowl shows aisle/shelf/bin on scan). → **[GAP]**
- Reason codes explaining the choice ("fixed bin", "zone affinity", "first available"). → **[GAP]**
- Honest refusal when nothing matches — EasyEcom literally prints **"No Suggestion Found"** rather
  than inventing a bin. → **[GAP — adopt as principle]**
- Rules execution trace / simulation without executing the task (documented SAP/WMS practice).
  → **[GAP — the computed page IS the trace]**

**d) Adjacent but explicitly NOT 5.4**
- Cross-dock bypass: `strategy="cross_dock"` exists as a manual choice on `PutawayTask`
  [BUILT]; *automated* cross-dock planning is NavERP.md **5.5's own bullet** ("Cross-Docking").
- Bin capacity limits as master data: likewise **5.5's bullet** ("Bin Capacity Management") —
  5.4 only READS `Location.capacity`.
- Weight/volume cube checks, hazmat matrices, family grouping, seasonal re-slotting, AI slotting:
  real products do these, but none can be expressed without new master data — record as future
  work, not build scope.

---

## 2. Recommended build scope — ONE new model + ONE computed page

### Chosen shape: `PutawayRule` table + computed suggestions page

**Why a table (and not the pure-computed alternative):** every researched product persists
putaway guidance as *configuration data* — Odoo has a literal `stock.putaway.rule` model, D365
location directives are records, SAP's search sequences are customizing rows, EasyEcom maps
SKUs to bins. None computes guidance purely from derived state, because the whole point is to
capture operator intent ("vaccines go to the cold room") that no derivation can invent. A
computed-only page would have nowhere to store that sentence, so the no-table option contradicts
the research and is rejected.

**Ownership fit:** rules FK the existing spine by string (`scm.Item`, `scm.ItemCategory`,
`scm.Location`) exactly like 5.1/5.2 models; they WRITE nothing — suggestions are read-only over
`scm.PutawayTask`, and overrides happen through the existing `scm:putawaytask_edit`.

### Model — `apps/inventory/models/ReceivingPutaway/PutawayRules.py`

```python
class PutawayRule(TenantOwned):
    """One system-guided putaway instruction: when goods X arrive at Y, store them in Z."""

    item            = FK("scm.Item", PROTECT, null=True, blank=True,
                         related_name="inventory_putaway_rules")
    category        = FK("scm.ItemCategory", PROTECT, null=True, blank=True,
                         related_name="inventory_putaway_rules")
    source_location = FK("scm.Location", SET_NULL, null=True, blank=True,
                         related_name="inventory_putaway_rules_from",
                         help_text="Applies when goods arrive in this staging/dock; blank = any arrival point")
    destination     = FK("scm.Location", PROTECT, related_name="inventory_putaway_rules_to",
                         help_text="Destination bin or zone")
    priority        = PositiveIntegerField(default=100)
    is_active       = BooleanField(default=True)
    notes           = TextField(blank=True)
```

- Plain `TenantOwned` (no `[PWR-` numbering] — configuration row, like `scm.ReorderRule`; reason
  strings cite codes, not numbers).
- `item` + `category` both null = catch-all (Odoo's documented best-practice fallback).
- `Meta`: `ordering = ["priority", "id"]`; index `(tenant, is_active)`; **no hard unique
  constraint** — overlapping rules are legal, the resolver order decides (Odoo behaves the same).
- `clean()`: cross-tenant guard on all four FKs (error keyed on each field so it renders);
  `destination != source_location` (mirrors `PutawayTask.clean`).

**Deterministic resolver contract (most-specific-wins):**
1. Candidate set: tenant-scoped, `is_active`, `(rule.item == item OR (rule.item IS NULL AND
   (rule.category == item.category OR rule.category IS NULL))) AND (rule.source_location IS NULL
   OR rule.source_location == arrival_location)`.
2. Order: specificity tier DESC (item=3 > category=2 > catch-all=1) → `priority` ASC → `id` ASC.
   First hit wins. Total order ⇒ identical output on every render.
3. No hit ⇒ suggestion is `None` — never a guessed bin (EasyEcom precedent).

### Computed page — `inventory:putaway_suggestions`

Standalone page at `templates/inventory/receiving/putaway_suggestions.html` (sub-module root per
the template rules). Rows = open `PutawayTask`s (`status in (pending, in_progress)`) — the GRN
link already exists (`goods_receipt` FK, `related_name="putaway_tasks"`), so this IS the
received-but-unputaway queue. Per row, ranked candidates:

| Rank | Heuristic | Reason string (examples) |
|---|---|---|
| 1 | Resolver rule hit | `"Rule: VAC-10 arriving DOCK-1 → CR-01"` |
| 2 | Consolidation — bin already holds the item (`on_hand > 0`), pick_sequence asc | `"Already holds MON-27"` |
| 3 | Storage-condition match — item requires chilled; candidate's own-or-ancestor condition equals it | `"Chilled requirement matched Cold Room 1"` |
| 4 | Walk-order fallback — first active pickable bin under the receipt's warehouse ancestor with free capacity | `"First pickable bin by walk order"` |

- Capacity honesty: `free = capacity − units-on-hand-at-bin` when capacity is set; blank capacity =
  unlimited and labelled as such. Never presented as weight/volume (that's 5.5's master data).
- Disqualifiers: condition mismatch; bin full; bin dedicated to a different 3PL client than the
  item's `owner_client`.
- Nothing qualifies ⇒ suggestion `None` + human-readable reason. Stats strip: open tasks,
  % covered by rules, uncovered count (the uncovered number is a finding, not an error).
- Zero writes: each row links `scm:putawaytask_edit` where the operator accepts/overrides.

CRUD for the rules themselves follows the standard house triple
(`putawayrule_{list,detail,create,edit,delete}` under `receiving/putaway-rules/`), reachable from
the suggestions page header.

---

## 3. Sidebar mapping proposal — `LIVE_LINKS["5.4"]`

Exact bullet titles from NavERP.md line 889:

```python
# 5.4 Receiving & Putaway. Bullets 1–3 are SCM-owned (L29/L36): the GRN document, its
# three-way match machine and 4.9's receiving inspections already exist — the sidebar points
# AT them. The genuine gap is bullet 4: "directed" putaway has a strategy label but no engine,
# so inventory adds the rule table + a computed suggestions page over open scm.PutawayTasks.
"5.4": {
    "Goods Receipt Note (GRN)":       "scm:goodsreceipt_list",          # bullet 1 (4.1 document)
    "Three-Way Matching":             "scm:goodsreceipt_list",          # bullet 2 (match_status badges live there)
    "Quality Inspection (Receiving)": "scm:qualityinspection_list",     # bullet 3 (4.9 QMS)
    "Putaway Logic":                  "inventory:putaway_suggestions",  # bullet 4 (new computed page; rules CRUD linked from its header)
},
```

Two bullets sharing a value route is fine (keys stay unique); precedent for pointing a bullet at
a computed page is `"Task Assignment": "scm:labor_board"` (4.14).

---

## 4. Seeder sketch — `_seed_putaway_rules` in `seed_inventory`

Guards (house pattern): skip the section if `PutawayRule.objects.filter(tenant=tenant).exists()`;
skip with a warning when seeded items are missing. Locations reuse seed_scm's rows via
`get_or_create` (mirroring how seed_scm itself guards WH-MAIN-A1 / DOCK-1):
`WH-MAIN` warehouse · `WH-MAIN-A1` bin (pick_sequence 10, abc_class "a", capacity 500) ·
`DOCK-1` staging (parent WH-MAIN, not pickable) · `CR-01` chilled zone · items `WS-16`,
`MON-27`, `DOCK-C` (category **IT Equipment**) and, only if present, `VAC-10`
(category **Temperature-controlled goods**, chilled requirement).

Four demo rows, chosen so every resolver tier and reason code shows up on one page:

1. `VAC-10` @ DOCK-1 → `CR-01`, priority 10 — item-specific cold-chain rule (chilled requirement
   matched by a chilled zone). Guarded: skipped gracefully if the cold-chain seed never ran.
2. `MON-27` @ DOCK-1 → `WH-MAIN-A1`, priority 20 — item-specific beats category (demonstrates tier order).
3. Category **IT Equipment** @ DOCK-1 → `WH-MAIN-A1`, priority 30.
4. Catch-all @ DOCK-1 → `WH-MAIN`, priority 900 — Odoo's empty-rule best practice.

With one open seeded putaway task for MON-27 off DOCK-1, the page renders rule-hit + consolidation +
fallback reasons without any new stock posting.

---

## 5. Risks / gotchas

1. **Cross-tenant guards need the mixin stamp (SEC-1).** `clean()` compares four FK tenants against
   `self.tenant_id`, but CRUD helpers assign the real tenant only after `is_valid()` — so the form
   MUST carry `TenantUniqueMixin` even though the model has no tenant-including `unique_together`;
   its second job (stamping `instance.tenant` during CREATE validation) is what keeps creates from
   being falsely rejected. Pair with `_reject_foreign(form, cleaned, [...])` for field-rendered errors.
2. **Reason-string determinism.** Compose reasons only from stable stored values (codes, SKUs, pk);
   never `__str__` drift, never timezone-dependent text. The resolver's total order (tier → priority
   → id) must hold everywhere it is used so two renders agree.
3. **None-vs-zero honesty.** "No suggestion" is a legitimate answer, not an empty string or a
   fabricated bin (EasyEcom's "No Suggestion Found"); uncovered-count stays visible.
4. **Capacity units honesty.** `Location.capacity` is "in the bin's own units"; comparing it to
   unit-quantity on-hand is deliberately naive — label the column accordingly, never imply weight/
   volume (5.5 owns bin-capacity master data).
5. **Zero writes into SCM.** The page reads `PutawayTask`/`StockMove`; acceptance/override flows
   through `scm:putawaytask_edit`. No StockMove, no task mutation from inventory.
6. **PROTECT semantics.** Item/category PROTECT so deleting a master cannot silently downgrade a
   specific rule into a broader one (silent specificity loss = wrong-stock-placement risk).
7. **Ancestor walks** (storage-condition inheritance, warehouse ancestor of a bin) reuse the bounded
   cycle-guard pattern of `Location.path()`.
8. **ABC conflation trap.** `ReorderRule.abc_class` is a REVENUE rank (item side) and is explicitly
   NOT `Location.abc_class` (bin velocity). The fallback uses pick_sequence, not either ABC column,
   precisely to avoid mixing axes.
9. **No quantity auto-split** across multiple bins (Odoo's documented behaviour too) — one
   suggestion per task; the operator splits manually via additional tasks if ever needed.
10. **Migration numbering** — claim the next `apps/inventory` migration before generating (L43),
    and keep the seeder idempotent per tenant (guard-first, like every 5.x section).

---

## Facts found that adjust the given context (none contradict it)

- The context is accurate throughout: bullets 1–3 fully built on SCM routes; `strategy="directed"`
  has no engine; no create-from-receipt flow exists.
- **Enrichment A:** `scm.Item` carries its OWN `storage_condition` (requirement declaration) and
  `owner_client` — the provision/requirement pair with `Location.storage_condition` means
  condition-matching needs zero schema change.
- **Enrichment B:** `scm.Location` also carries `owner_client` (4.17 3PL reservation) — candidate
  filtering should respect it (don't route into a client's dedicated aisle).
- **Enrichment C:** `PutawayTask.goods_receipt` already exists (`related_name="putaway_tasks"`),
  so the received-but-unputaway queue is directly derivable from open tasks — no join gymnastics.
- **Enrichment D:** NavERP.md gives **5.5** the "Bin Capacity Management" and "Cross-Docking"
  bullets (lines 897–899) — reinforcing that 5.4 must only READ capacity and treat cross-dock as a
  manual strategy choice.
