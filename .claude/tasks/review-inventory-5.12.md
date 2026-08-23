# Review — inventory 5.12 Multi-Location Management

Changeset: working-tree 5.12 files (MultiLocationManagement layers ×4, multilocation templates,
migration 0018 [shared node with sibling 5.14 tables], wiring hunks in app-root __init__s,
admin.py, seed_inventory.py `_seed_location_network`, navigation LIVE_LINKS["5.12"]).

## Lane coverage

| Lane | Result |
|---|---|
| code-reviewer | C1–C4 + C6 (agent lane died on provider network errors ×2; its checklist executed inline in main session) |
| frontend-reviewer | FE-1..FE-5 |
| qa-smoke-tester | 18/18 probes PASS incl. duplicate-code, same-warehouse-twice, cycle guards, ORM-recomputed rollup numbers; DB restored |
| security-reviewer | SEC-1 Low; isolation/gating/XSS/junk-params verified clean |
| performance-reviewer | PF-1 Low, PF-2 Info; four-query claim verified real |

No lane without result — the failed lane's scope was covered inline (C1–C3, M6 below).

## Findings (fix in ID order)

### Important

- [ ] **C1** — views/MultiLocationManagement/LocationNetworks.py — `global_stock` lives inside
      LocationNetworks.py but the frozen contract names a separate `GlobalStock.py` entity module
      (WarehouseMap precedent). **Fix:** split view + IN_FLIGHT_STATUSES into
      `views/MultiLocationManagement/GlobalStock.py`; keep package __init__ re-export resolving
      (`from .GlobalStock import global_stock`); urls import keeps resolving. New file gets its
      own commit.
- [ ] **C2** — seed_inventory `_seed_location_network` deviates from the frozen tree: contract
      pins HOLD-CO → REG-NORTH → DC-MAIN(dc)+WH-MAIN and HOLD-CO → DIV-RETAIL → ST-DT+WH-STORE
      with `sites_unassigned == 0`; code builds HQ/R-EAST/R-WEST/ST-01, never demos the `dc`
      badge, attaches only warehouses[0], and its docstring claims get_or_create it doesn't do.
      **Fix:** rebuild per contract codes/tiers (company/region/dc/store all demoed), attach BOTH
      seeded warehouses (sites_unassigned 0), drop the deliberate-unassigned gimmick, fix the
      docstring (plain create, honest about what exists). Keep guard-first idempotency.
- [ ] **C3** — global_stock measured 5 queries not the frozen 4: depth-≥2 nodes escape
      select_related and re-fetch ancestors in `path()`. **Fix:** build `by_pk` node map once and
      resolve `path_label` iteratively over the map (no `.parent` DB hits), restoring flat-4 at
      any depth. Verify with CaptureQueriesContext.

### Minor

- [ ] **M1** — urls/__init__: rename alias to contract-pinned `_mlm_locationnetworks` IS current;
      move concat entry directly under `*_fo_waves` per todo placement note (cosmetic, first-match
      unaffected).
- [ ] **M2** — `?is_active=` uses active/inactive while todo pinned true/false — ACCEPT the
      implemented vocabulary and annotate the todo line accordingly (self-consistent template+view).
- [ ] **M3** — global_stock.html gates empty-state Add Node on undefined `is_admin` (never renders);
      view passes only {rows,stats,q}. **Fix:** pass `is_admin` in global_stock context.
- [ ] **M4** — detail.html dead manual-breadcrumb else-block (path_label always present) — delete.
- [ ] **M5** — global_stock.html `{% if row.stock_value or row.stock_value == 0 %}` always true —
      simplify to unconditional floatformat rendering.
- [ ] **M6** — unassigned pseudo-row appended even when `q` matches nothing, hiding the honest
      no-match empty state. **Fix:** append pseudo-row only when `not q`.
- [ ] **M7** — whitespace-only `code` accepted ("   "). **Fix:** strip in form clean (and reject
      empty after strip with field error).
- [ ] **M8** — detail children queryset missing select_related("warehouse") though template derefs
      warehouse per child row. **Fix:** add select_related.
- [ ] **M9** — seeder `admin` lookup is staff-only; tenant without staff user passes None into
      release(). Broaden fallback to any tenant user (sibling line ~769 pattern).

### Accepted-as-is

- Migration 0018 bundles sibling 5.14 barcode tables (shared checkout node, disclosed).
- `is_active` active/inactive vocabulary (implemented) vs todo's true/false pin — accepted, todo annotated (M2).
- StockMove grouped SUM range-scans the ledger per render — inherent to ledger-derived rollups today (PF-2).

## Verification bar for the fixer

After each code finding `manage.py check` clean; final gates: `temp/smoke_multiloc_5_12.py` ALL PASS
(update it if the seeder shape changes assertions), QA probes from the lane script re-run clean,
global_stock CaptureQueriesContext == 4 view queries reported. Commits one file per commit; docs
commit closes the checkboxes.
