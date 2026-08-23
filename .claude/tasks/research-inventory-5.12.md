# Research — Inventory 5.12 Multi-Location Management

Research-only catalog feeding a ONE-model (+ optional computed page) build in `apps/inventory`.
Sources: Oracle NetSuite OneWorld docs (Multi-Location Inventory, Global Inventory Relationship,
cross-subsidiary fulfillment), Odoo 18/19 inventory docs (warehouses/locations/transit/resupply),
SAP S/4HANA Learning (enterprise structure, MMBE/MB52/MB5T, plant-to-plant transfers),
Microsoft Learn (D365 On-hand list, Inventory Visibility app, reservation hierarchies),
Manhattan Active OMS/SCP (Dynamic Inventory Management, Omnichannel Allocation), Kinaxis
(MEIO), Fishbowl (Location Groups, Transfer Orders, reorder-level scope toggle), Zoho Inventory
(Branches), Cin7 Core/Omni · Brightpearl · Linnworks (2026 comparisons).

## 0. What the products actually ship (deduplicated patterns)

| Pattern | Who ships it | Shape |
|---|---|---|
| Org tier ABOVE warehouses | NetSuite (subsidiary; every location belongs to exactly ONE subsidiary), SAP (client → company code → plant → storage location, strict assignment chain), D365 (site → warehouse → location storage dimensions), Zoho (**Branch** above warehouses, branch-wise reports) | A separate org entity that warehouses ATTACH to — not extra depth on the bin tree |
| Reporting-only parent grouping | NetSuite parent locations ("East Coast" → New York → Atlanta Warehouse) — explicitly "does not affect operations, helps roll-up analytics" | Optional parent pointer purely for aggregation |
| Warehouse-as-group | Fishbowl (**Location Group** = warehouse containing locations; unlimited groups/sub-groups) | Group entity above stock locations |
| Single aggregated view w/ drilldown | D365 On-hand list (pick display dimensions: one row per site ↔ expand to warehouse ↔ location); Odoo Inventory Report filterable by warehouse; Fishbowl "view your inventory across all locations in a single window"; SAP MMBE/MB52 | Aggregate first, drill to node |
| In-transit included | Manhattan ("beyond on-hand … include in-transit, on-order, third-party"), SAP MB5T stock-in-transit report, Odoo dedicated **Transit Location** ("Inter-warehouse transit" under a virtual Physical Locations node), Fishbowl "In Transit" location type | Either a virtual location holding the stock, or a report over open transfer docs |
| Network ATP | D365 Inventory Visibility (ATP queries over configurable on-hand index hierarchies), Manhattan availability attributes (on-hand/expected/pre-order/past-due) | Computed, usually an add-on service |
| Cross-entity trading pairs | NetSuite **Global Inventory Relationship** (originating subsidiary × inventory subsidiary × allowed fulfillment/return locations) | Named-pair policy records |
| Inter-site resupply policy | Odoo "**Resupply From**" checkbox on destination warehouse auto-creates an inter-warehouse route; per-warehouse min/max reorder rules with route = Buy or Resupply-from-Central | Lane/group policies, not per-SKU-pair matrices |
| Per-node safety stock | NetSuite (reorder point + preferred stock level **per location** on the item), Fishbowl (reorder levels "Company Wide" vs "By Location Group" toggle), Odoo (reorder rules keyed product×location), Kinaxis MEIO (targets per echelon) | Per (item × node) parameters — **already ours**: `scm.ReorderRule` |
| Per-location pricing | Weak/absent as a *stocking-location* concept everywhere surveyed: Zoho/Cin7/Linnworks price by channel/customer segment; NetSuite prices flow from subsidiary (legal-entity) config; retail chains do regional pricing via price books, not warehouse masters | ⚠ see contradiction #1 |
| Source-location selection | Manhattan Omnichannel Allocation, NetSuite fulfillment optimization ("automatically select the locations items should ship from"), Zoho "closest warehouse" pick on SO | Out of scope here (4.5 owns SO allocation) |

## 1. Feature catalog vs NavERP.md 5.12 bullets

### Bullet 1 — Location Hierarchy Setup (companies → regional DCs → stores)
- [GAP] Org-network tiers ABOVE the warehouse. `scm.Location`'s self-FK tree models PHYSICAL
  structure (warehouse > zone > bin > staging > transit — Locations.py:17-23); nothing groups
  warehouses into companies/regions/store portfolios. Every surveyed enterprise product carries
  this tier as a separate org entity (NetSuite subsidiary, SAP company code/plant, D365 site,
  Zoho branch, Fishbowl location-group).
- [GAP] Leaf sites attaching real warehouses to network nodes (Fishbowl group membership,
  NetSuite location.subsidiary assignment).
- [BUILT via scm.Location] Physical internals under each site (zones/bins/docks) — stays 4.3.
- [GAP-minor] Node lifecycle metadata (is_active, notes) on the org tier.

### Bullet 2 — Global Stock Visibility (aggregate across the enterprise)
- [BUILT partially via scm.StockMove + scm:on_hand_by_location] Per-location on-hand grid exists,
  grouped by location CODE — but flat, unfiltered by any network grouping, no tree roll-up.
- [BUILT via inventory:stocklevels] Per item×spot availability (on-hand/allocated/held/on-order) —
  again per-spot, not per network node.
- [GAP] Roll-up UP an org tree: one row per network node = Σ on-hand of all warehouses in its
  subtree (D365 dimension-aggregation UX; NetSuite consolidated visibility).
- [GAP] In-transit surfaced per node (Manhattan/SAP MB5T/Odoo pattern): units on OPEN
  `scm.StockTransfer`s mapped to source/destination nodes. Cheap — one grouped query; the ledger
  itself cannot show it because legs post atomically at completion.
- [GAP-honesty] Nodes without data answering "—" not 0 (house None-vs-zero discipline).
- [OUT OF SCOPE] Network-wide ATP computation (D365 Inventory Visibility service territory);
  per-spot available already exists on `inventory:stocklevels`.

### Bullet 3 — Location-Specific Rules (pricing / transfer rules / safety stock per location)
- [BUILT via scm.ReorderRule, 4.3] Safety stock + reorder point per (item × location) — the
  strongest per-location grain we own; 4.7 even computes it. Nothing to build.
- [BUILT via inventory.TransferRoute, 5.7] Transfer lanes between named endpoint pairs/groups
  (open ends = group-level service), transit windows, governed approvals. Matches Odoo
  resupply-lane / NetSuite GIR lane patterns at our scale.
- [BUILT via inventory.ItemPrice, 5.1 — with caveat] Sell-side pricing exists as typed,
  breakable, dated rows; it simply has NO location/node dimension. Research verdict: keep it
  that way (contradiction #1) — declare the "unique pricing per location" clause satisfied by
  the EXISTING pricing master, not extended.
- [OUT OF SCOPE] Source-location/allocation selection (which DC ships the order) — Manhattan/
  NetSuite optimization territory; 4.5's SalesOrderAllocation owns reservation logic.

## 2. Recommended build scope — ONE model + ONE computed page

**Shape chosen: a tenant-scoped `LocationNetwork` node table (the missing org tier) + a computed
"Global Stock Visibility" page rolling the ledger up the tree.** This follows the Fishbowl /
Zoho / NetSuite-parent-location school (grouping entity ABOVE warehouses), NOT the Odoo move of
deepening the location tree itself — `scm.Location.location_type` means warehouse/zone/bin;
overloading it with company/region tiers would fork the meaning of every existing query
(`location_type="warehouse"` filters, warehouse-root walks in 5.7's board, putaway candidate
walks). Zero writes into scm; the only scm touch is reading.

Package: `apps/inventory/models/MultiLocationManagement/LocationNetworks.py` (+ forms/views/urls
siblings), templates `templates/inventory/multilocation/locationnetwork/{list,detail,form}.html`
+ page-only `multilocation/global_stock.html`.

### Model — `LocationNetwork` [LNW-]

```python
class LocationNetwork(TenantOwned):
    """One node of the org network above the warehouses — company, region, DC or store."""

    NODE_TYPE_CHOICES = [
        ("company", "Company"),
        ("region", "Region"),
        ("dc", "Distribution Center"),
        ("store", "Store / Site"),
    ]

    code = models.CharField(max_length=32)
    name = models.CharField(max_length=255)
    node_type = models.CharField(max_length=10, choices=NODE_TYPE_CHOICES, default="store")
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="children")
    warehouse = models.ForeignKey("scm.Location", on_delete=models.PROTECT, null=True, blank=True,
                                  related_name="network_nodes",
                                  help_text="The stocked site this leaf maps to; "
                                            "blank = pure grouping node")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]
        unique_together = (("tenant", "code"), ("tenant", "warehouse"))
        indexes = [models.Index(fields=["tenant", "node_type"], name="inv_lnw_tnt_type_idx")]
```

Design decisions (each traceable to research):
- **`parent` SET_NULL** — matches the spine precedent (`scm.Location.parent`); deleting a region
  leaves its children as visible roots instead of destroying an org chart. PROTECT was rejected:
  house delete views are thin (`obj.delete()`), and ProtectedError would 500.
- **`warehouse` PROTECT** — never silently detach a live stocked site from its network; contrast
  with parent deliberately documented in the docstring.
- **`unique_together (tenant, warehouse)`** — a warehouse may attach AT MOST ONCE across the whole
  tree, or subtree sums would double-count it. (NULLs excluded by SQL semantics, so grouping
  nodes coexist freely.) This answers "unique-per-node?" — unique per TENANT, which is the
  stronger and correct form.
- **`clean()`**: `_reject_foreign`-equivalent for parent + warehouse (crafted POSTs AND admin/
  seeder paths, TransferRoute.clean precedent); refuse `parent == self`; refuse a warehouse whose
  `location_type != "warehouse"` (a bin is not a store); **cycle guard** walking the parent chain
  with a seen-set — `Location.path()` precedent (Locations.py:95-103).
- **`path()`** mirroring `Location.path()` for display ("Holdings › North › Main DC").
- No status machine, no numbered mixin: an org node is master data, not a document (BinCapacity /
  PutawayRule precedent).

### Computed page — `inventory:global_stock` (no writes anywhere)

Route `path("network/global-stock/", views.global_stock, name="global_stock")` in
`urls/MultiLocationManagement/LocationNetworks.py`; view `views/MultiLocationManagement/GlobalStock.py`
(`StockLevels.py` style — computed page, dict rows through `crud.paginate`).

Query budget (~5 flat, the 5.6 discipline):
1. All tenant `LocationNetwork` rows once → build `{pk: row}` + `{parent_id: [children]}` maps.
2. Subtree warehouse-id sets per node in Python (iterative walk, cycle-guarded — never recursive
   per row).
3. ONE grouped `StockMove` query over ALL attached warehouse ids, `values("location_id")`,
   `Sum("quantity")` (+ value via `Sum(F*F)` like `on_hand_by_location`), **tenant predicate
   included** so `scm_move_tnt_item_loc_idx` applies → rolled up in Python.
4. ONE grouped open-`StockTransfer` query (`transfer__tenant=request.tenant`,
   `status__in=("in_transit",)` primary; optionally `("approved",)` flagged separately) summed
   per from/to warehouse → per-node outbound/inbound columns.
5. Items for the filter dropdown.

Rows: `{node, type_badge, path, warehouse_count, on_hand, on_hand_value, in_transit_out,
in_transit_in}` sorted by on_hand_value desc. Filters `?q=` (code/name) and `?item=<pk>`
(one-SKU lens: every node's total for that SKU — the MMBE-style material-across-the-network view)
applied BEFORE pagination.

Honesty rules:
- Node with no attached warehouses AND no descendants → aggregates answer **None**, rendered "—"
  ("no data"), never 0. Zero appears only when moves genuinely net to zero.
- **In-transit is informational and NEVER subtracted from on-hand**: `_post_transfer` posts both
  legs atomically at completion (StockTransfers.py docstring), so in-transit units are still
  truthfully counted at the source node. Subtracting would double-subtract.
- Drill-down links per row: warehouse → `inventory:stocklevels` (per-spot availability), node
  transfers → `inventory:transfer_board`, raw ledger → `scm:stock_ledger`.
- Page states plainly it is operational visibility, NOT valuation-owned (valuation stays
  `scm:valuation_report`) and NOT ATP.

CRUD for LocationNetwork: standard list/detail/create/edit/delete triple, create/edit/delete
`@tenant_admin_required` (rule-master gating precedent 5.3/5.4), list/detail member-readable.

## 3. LIVE_LINKS["5.12"] proposal (verbatim bullet titles)

```python
# 5.12 Multi-Location Management. The PHYSICAL tree is 4.3's scm.Location (L36 — never
# re-declare it) and per-location RULE grains already exist: safety stock on scm.ReorderRule,
# transfer lanes on inventory.TransferRoute (5.7), pricing rows on inventory.ItemPrice (5.1).
# What nothing provides is the ORG tier above the warehouses (company/region/DC/store) and
# the roll-up of the append-only ledger along it.
"5.12": {
    "Location Hierarchy Setup": "inventory:locationnetwork_list",  # NEW - org-tier node table [LNW-]
    "Global Stock Visibility":  "inventory:global_stock",          # NEW - computed roll-up page
    "Location-Specific Rules":  "scm:reorderrule_list",            # safety stock per item×location (4.3)
},
```

Bullet 3 bundles three rule families that live on three different masters; it points at
`scm:reorderrule_list` because safety stock is the one with TRUE per-location grain today
(TransferRoute endpoints are optional/open-ended; ItemPrice has no location column by design).
Both new templates cross-link the other two homes in their headers ("Transfer lanes →
inventory:transferroute_list · Pricing → inventory:itemprice_list") so the bundled bullet is
fully navigable without inventing a fourth model.

## 4. Seeder sketch (`_seed_multi_location` inside seed_inventory)

Reuses what seed_scm already created — verified: `WH-MAIN` Main Warehouse + `WH-STORE` Retail
Store (both `location_type="warehouse"`, seed_scm.py:364-367) holding opening receipts and a
COMPLETED main→store monitor transfer (TRF), plus `WH-MAIN-A1` bin and `DOCK-1` staging from the
4.4 seed. Guard marker-based on THIS module's table:

```python
def _seed_multi_location(self, tenant):
    if LocationNetwork.objects.filter(tenant=tenant).exists():
        return                                   # idempotent, --flush resets like siblings
    main = Location.objects.filter(tenant=tenant, code="WH-MAIN").first()
    store = Location.objects.filter(tenant=tenant, code="WH-STORE").first()

    corp   = LocationNetwork.objects.create(tenant=tenant, code="HOLD-CO", name="Holding Company",
                                            node_type="company")
    north  = LocationNetwork.objects.create(tenant=tenant, code="REG-NORTH", name="Northern Region",
                                            node_type="region", parent=corp)
    retail = LocationNetwork.objects.create(tenant=tenant, code="DIV-RETAIL", name="Retail Division",
                                            node_type="region", parent=corp)
    LocationNetwork.objects.create(tenant=tenant, code="DC-MAIN", name="Main Distribution Center",
                                   node_type="dc", parent=north, warehouse=main)
    LocationNetwork.objects.create(tenant=tenant, code="ST-DT", name="Downtown Store",
                                   node_type="store", parent=retail, warehouse=store)
```

Because WH-MAIN/WH-STORE already carry genuine StockMoves (OPENING receipts + completed TRF
legs), `inventory:global_stock` renders real numbers on first paint: Holding Company rolls up
everything; Northern Region shows main-stock minus shipped monitors; Retail Division shows the
received five; the completed transfer contributes zero in-transit (correctly). Optionally extend
the 5.7 block's governed transfers so one sits at `in_transit` status to light the in-transit
columns (guard-compatible: those seeds already skip when present).

## 5. Risks / gotchas

1. **Cycle-guarded walks twice** — parent-chain validation in `clean()` AND the subtree roll-up
   in the view must both use seen-set iteration (`Location.path()` precedent, Locations.py:95);
   a malformed self-parent row must never hang the page.
2. **Tenant scoping on every FK and aggregate** — `_reject_foreign` on parent + warehouse; the
   StockMove roll-up MUST carry `tenant=request.tenant` to hit `scm_move_tnt_item_loc_idx`;
   `StockTransferLine` has NO tenant column — always filter via `transfer__tenant` (5.7 gotcha
   of record).
3. **Migration number: claim 0017** — latest is `0016_physicalinventory_inv_phy_tnt_sched_idx`
   (5.11). Check `apps/inventory/migrations/` immediately before generating; a sibling session
   may take the number (shared-checkout etiquette, L43).
4. **Shared files are single-writer surgical edits** — `navigation.py` (one LIVE_LINKS entry),
   seeder (append one `_seed_*` + call), package `__init__.py` re-exports, `urls/__init__.py`
   concatenation. Never rewrite these files wholesale.
5. **Zero writes into scm** — string FK `"scm.Location"` with PROTECT; the computed page reads
   only. Any temptation to add columns to `scm.Location` for org tiers is exactly the fork the
   skill forbids (bin/cold-chain/3PL precedents added CLASSIFICATIONS, not new tree semantics).
6. **In-transit double-subtraction trap** — legs post atomically at completion, so on-hand at
   source already tells the truth; in-transit columns are additive information only.
7. **None-vs-zero** — `Sum()` over an empty set returns None: render "—" for data-less nodes;
   reserve 0 for genuinely netting-to-zero subtrees.
8. **`(tenant, warehouse)` uniqueness relies on NULL exclusion** — SQLite (tests) and MariaDB
   (prod) both allow multiple NULLs; verify the form surfaces the IntegrityError path anyway
   (TenantUniqueMixin pattern).
9. **ItemPrice location dimension: do NOT add it this build** — see contradiction #1; if a real
   requirement ever lands, a nullable `network_node` FK is additive and can ride a later
   migration.

## Contradictions found

1. **NavERP.md implies per-location pricing is a 5.12 deliverable; the market disagrees.**
   No surveyed product keys sell-side prices on the STOCKING site — pricing keys on customer
   segment/channel (Zoho, Cin7, Linnworks), legal subsidiary (NetSuite), or regional price books
   maintained outside the warehouse master. Our `ItemPrice` (typed, breakable, dated) matches the
   industry shape; bolting a location dimension on would be building a feature the leaders don't
   ship. Declared satisfied-by-existing, out of build scope.
2. **Prompt asked "hierarchy on the warehouse master or a separate network entity?" — the
   research says separate entity, but two schools disagree on WHERE.** NetSuite offers BOTH
   (subsidiary assignment AND optional parent-locations on the location record, the latter
   "reporting only"); Odoo deepens the location tree itself with VIEW-type pseudo-nodes. We side
   with the separate-entity school because `scm.Location.location_type` already enumerates
   physical kinds and 5.7's board walks warehouse ROOTS — mixing org nodes into that tree would
   corrupt an existing invariant.
3. **In-transit modeling contradicts between vendors:** Odoo/Fishbowl park stock in a dedicated
   transit LOCATION (stock visibly "somewhere"); SAP uses stock-in-transit segments; our ledger
   has NO in-transit bucket (atomic paired posting at completion). The global page therefore
   SYNTHESIZES in-transit from open `StockTransfer` documents — honest, but a divergence from
   the Odoo mental model worth stating on the page itself.
4. **"Aggregate stock levels" could read as ATP.** Manhattan/D365 bundle availability promises
   into network views; our per-spot available figure exists on `inventory:stocklevels`, and
   computing network ATP (promising against in-flight supply) is a planning feature, not
   visibility. Scope line drawn: roll-ups + in-transit yes, ATP no.
