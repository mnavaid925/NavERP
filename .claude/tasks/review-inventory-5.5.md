# Review wave — inventory 5.5 Warehousing & Bin Management

Date: 2026-08-22 · Lanes run: code-reviewer · explorer · frontend-reviewer · performance-reviewer · qa-smoke-tester · security-reviewer (all returned; security re-run once after a truncated first return).
Scope: `apps/inventory/{models,forms,views,urls}/WarehousingBinManagement/`, migration 0006, `templates/inventory/warehouse/**`, overview card, admin rows, `_seed_warehousing`, `LIVE_LINKS["5.5"]`.
QA lane result up front: **42/42 smoke checks PASS** (routes, content, filters vs ORM, lifecycle POSTs with balanced ledger legs, validation, cross-tenant 404s, superuser isolation).

## Burn-down (fix in this order; mark each row when done)

| ID | Sev | Lane ids | Finding (one line) | Fix |
|----|-----|----------|--------------------|-----|
| C1 | Critical | F1 ≡ E1 ≡ E2 | `{% widthratio … as pct %}` yields a STRING in Django 5.1, so `pct >= 100` is always False → over-limit red badge never fires and bar width unclamped (`width:250%`) in `bincapacity/list.html` AND `warehouse/map.html`; the module's headline honesty signal is dead | [x] fixed (`utilisation_pct` Decimal property + per-row `pct` drive both pages; bar clamps at 100%, red badge fires on the true >100 figure) |
| C2 | Critical | P1 | N+1 ledger aggregates: bincapacity list resolves `obj.on_hand` twice per row (cell + widthratio) → ~30 SUM queries per page over each bin's full move history | [x] fixed (`on_hand_qty` Subquery moved onto `_scoped()` — one annotation per row, cells read it directly) |
| I1 | Important | R1 ≡ S1 | `crossdockorder_edit` has NO status guard server-side — crafted POST edits a received/shipped order (quantity/item/dock) beneath already-posted StockMove legs | [x] fixed (edit view re-fetches tenant-scoped and flashes + redirects non-editable orders before delegating to `crud_edit`) |
| I2 | Important | R2 ≡ S2 | delete TOCTOU: `is_editable` checked on an unlocked snapshot, then `crud_delete` re-fetches WITHOUT lock or re-check → concurrent receive() can be deleted after posting legs, orphaning ledger provenance | [x] fixed (delete hand-rolled like MaintenanceWorkOrders: `select_for_update` inside `atomic`, guard re-tested under the lock, audit written in-tx) |
| I3 | Important | S3 | ship()/cancel() shortfall check is lock-free vs concurrent outbounds sharing one dock (two orders of different items excepted) — racing POSTs can both pass and drive the dock negative; serialize by locking the Item row inside the action's transaction before the balance read | [x] fixed (`_stock_lock()` locks the Item FOR UPDATE in receive/ship/cancel before any balance read or cost roll) |
| I4 | Important | P2 ≡ R5 | `_over_capacity_count` runs per render, walking every profile with 2 property queries each ("one pass" docstring is false) | [x] fixed (single annotated COUNT with the raw `F()` comparison — one query, no Python walk) |
| I5 | Important | R3 | seeder `--flush` deletes CrossDockOrder rows but their StockMove legs persist; `next_number` restarts at XD-00001 so reseeded orders join the PREVIOUS generation's legs via reference match, and DOCK-1 on-hand accumulates across generations | [x] fixed (XD base = max across CrossDockOrder numbers AND surviving `XD-` StockMove references; explicit numbers passed to save) |
| I6 | Important | F2 | crossdockorder/detail.html has no Delete button even for drafts (delete only reachable from list row); sibling convention is Back/Edit/Delete | [x] fixed (draft-only Delete POST form with confirm + trash icon added to detail page actions) |
| M1 | Minor | R4 | chip uses rounded `utilisation >= 100`, filter/map use raw `on_hand >= max_quantity` → boundary rows disagree (99.96% quantizes to 100.0) | [x] fixed (chip is the same raw SQL comparison as filter/map — boundary rows agree everywhere) |
| M2 | Minor | R6 | forms `_lot_queryset`: `raw.isdecimal()` then `int(raw)` without range cap → over-range value raises OverflowError at query time (the L11 class); use `apps.core.crud.as_db_int` | [x] fixed (`as_db_int` replaces the isdecimal/int pair) |
| M3 | Minor | R7 | WarehouseMap edge cases: a warehouse whose parent is another warehouse renders twice (section header + child row); a cycle island among non-warehouse locations appears nowhere despite the "nothing silently dropped" comment | [x] fixed (warehouse children skipped in `_walk`; one `emitted` set across sections+orphans; residual pass appends cycle islands to orphan rows) |
| M4 | Minor | S4 | model `clean()` checks dock_location/lot_serial tenancy but not `item` (admin path bypasses form `_reject_foreign`) | [x] fixed (clean() checks `item` tenancy beside dock_location/lot_serial) |
| M5 | Minor | S5 | `recent_moves` / `BinCapacity.on_hand` rely on transitive tenant scoping via location FK; make the tenant filter explicit like `ledger_moves()` does | [x] fixed (`on_hand` aggregates via `location.stock_moves.filter(tenant_id=...)`; `recent_moves` filters `tenant=request.tenant`) |
| M6 | Minor | P3 | CrossDockOrder default ORDER BY `-scheduled_date,-id` has no supporting index (only `(tenant,status)` exists) → filesort per list render | [x] fixed (migration 0009 adds `inv_xd_tnt_sched_idx` on tenant+scheduled_date+id) |
| M7 | Minor | F3 | limits rendered as raw str(Decimal) while adjacent figures use floatformat — apply `-2` (weight/qty) / `-3` (volume) consistently | [x] fixed (list/detail/map limits use floatformat -2/-3/-2 with None-safe em-dash branches — floatformat eats non-numeric input) |
| M8 | Minor | F4 | XD detail omits `notes` entirely when blank; sibling shows a muted "No notes…" placeholder | [x] fixed (muted "No notes recorded." placeholder) |
| M9 | Minor | F5 | XD quantities displayed `floatformat:"-2"` but the field is 4-dp for lot-tracked goods (0.0001 renders as "0") — use `-4` | [x] fixed (floatformat -4 on XD list Qty, detail Quantity and both ledger/recent-move qty columns) |
| M10 | Minor | E4 | seeder get_or_create defaults `parent=zone` for WH-MAIN-A1 can never apply (seed_scm created A1 under main first) — comment claims zone holds two bins; align defaults/comment with reality instead of re-parenting another module's seeded row | [x] fixed (A1 defaults `parent=main` matching seed_scm; comment corrected — no re-parenting) |
| M11 | Minor | E5 | `--flush` deletes BinCapacity + CrossDockOrder but excludes both from the `deleted` tally it prints | [x] fixed (tally += BinCapacity + CrossDockOrder counts, deletes kept) |
| M12 | Minor | E8 | WarehouseMap docstring says "two queries"; it runs three (locations, group-by, profiles) | [x] fixed (docstring now says three queries and describes the residual pass) |
| M13 | Minor | E6 | urls/__init__ docstring has a malformed empty-segment token where `""` was meant | [x] fixed (docstring token replaced with `""`) |
| M14 | Minor | QA(a) | custom "different item" clean() message unreachable via normal POSTs (form narrowing intercepts with generic invalid-choice wording) — refusal correct, wording differs | [~] skipped — refusal is correct server-side (model clean() still enforces it); generic invalid-choice wording is standard Django UX |
| M15 | Minor | QA(b) | seeded over-limit demo self-destructs if a smoke cancels the seeded received order (compensating move nets DOCK-1 back under cap) — mitigation belongs in temp scripts / future fixture, not app code | [~] skipped — demo-data lifecycle note; mitigation lives in temp/ smoke scripts, not shipped code |
| M16 | Minor | E7 | no test_warehousing_* quartet yet — addressed by Phase 6 test wave, not the fixer | [~] skipped — owned by the Phase 6 test wave |

Dedup notes: F1/E1/E2 are one defect in two templates (frontend found it independently of explorer). R1≡S1 and R2≡S2 were found by both the code and security lanes. P2≡R5 same finding.

---

## Per-lane findings (verbatim)

### explorer
| ID | Severity | File:line | Finding | Suggested fix |
|---|---|---|---|---|
| E1 | Important | templates/inventory/warehouse/bincapacity/list.html:56-58 | `{% widthratio … as pct %}` stores a string; `"125" >= 100` swallowed TypeError → False; red badge branch dead, bar unclamped | compare a real number (render `obj.quantity_utilisation`) |
| E2 | Important | templates/inventory/warehouse/map.html:74-77 | same defect in map's Qty Utilisation column | use `row.profile.quantity_utilisation` |
| E3 | Minor | models/WarehousingBinManagement/BinCapacities.py:66-69 | docstring promises template turns >100 red — only true after E1/E2 | fixed by C1 |
| E4 | Minor | seed_inventory.py:321-328 | A1 zone-parent default never applies (seed_scm owns the row) | align defaults/comment |
| E5 | Minor | seed_inventory.py:104-118 | new models absent from --flush tally | add counts |
| E6 | Minor | urls/__init__.py:8-10 | malformed empty-segment token in docstring | replace with "" |
| E7 | Minor | apps/inventory/tests/ | no test_warehousing_* quartet | test wave |
| E8 | Minor | views/WarehousingBinManagement/WarehouseMap.py:9-15 | docstring "two queries" ≠ three | reword |

Verified clean by explorer: package layout/re-exports/absolute imports; zero spine re-declaration; all url names reverse; sidebar bullets match NavERP.md §5.5 verbatim; theme.css classes exist; STATUS_CSS comment accurate; `_post_move`/`_shortfall` mirror scm's posting service; migrations clean.

### performance-reviewer
| ID | Severity | File:line | Finding (growth curve) | Suggested fix |
|---|---|---|---|---|
| P1 | Critical | bincapacity/list.html:53,56 + BinCapacities.py:57 | 2 aggregate queries × 15 rows per render, each scanning that bin's whole ledger | annotate Subquery Sum once on _scoped() |
| P2 | Important | BinCapacities.py:108-112 | chip walks all profiles × 2 property queries per render | single annotated COUNT |
| P3 | Minor | CrossDockOrders.py Meta | ORDER BY -scheduled_date,-id unindexed | Index (tenant, scheduled_date, id) |

Clean: utilisation=over subquery index-supported; _dock_choices one DISTINCT; ledger_moves sliced on index; filters pre-pagination; WarehouseMap truly 3 queries total.

### qa-smoke-tester
42/42 PASS across routes/content/filters/lifecycle/validation/cross-tenant/superuser. Notables: Q3.1 `?utilisation=over` matches direct ORM computation exactly (DOCK-1 sole row); Q4.2–Q4.4 receive→ship posts [+q, −q] netting zero and shipped refuses cancel; Q6.x cross-tenant GET/POST → 404/no-op. Findings: QA(a) wording unreachable via form; QA(b) demo fragility. Script left at temp/qa_smoke_55.py.

### code-reviewer
R1 edit route ungated (StockTransfers precedent cited) · R2 delete TOCTOU (MaintenanceWorkOrders precedent cites the exact crud_delete shape) · R3 seeder reference-collision on reseed · R4 chip/filter boundary · R5 ≡ P2 · R6 int(raw) overflow (L11 family) · R7 map double-render/cycle-island. Verified clean: state machine locking/guards/audit-inside-transaction; ValidationError→flash conversion; quantity_utilisation divisors; makemigrations --check clean; seeder edge cases.

### security-reviewer
S1 ≡ R1 (A04/A01) · S2 ≡ R2 (A04 TOCTOU) · S3 lock-free balance under concurrency · S4 item tenant check missing in clean() · S5 transitive scoping in recent_moves/on_hand · S6–S10 CLEAN (mass assignment, IDOR surface, CSRF/POST discipline, injection via ?q=, seeder). Overall risk: low-to-moderate, all fixable without schema change beyond M6's optional index.

### frontend-reviewer
F1 ≡ C1 (verified empirically on Django 5.1.15) · F2 missing draft Delete on detail · F3 limit formatting · F4 notes placeholder · F5 qty precision. Verified clean: badge classes colour-named only; lucide names have precedent; filter reflection/stringformat:"d"; pagination include; colspans; form loops; aria-labels.
