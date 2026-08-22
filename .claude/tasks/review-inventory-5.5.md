# Review wave — inventory 5.5 Warehousing & Bin Management

Date: 2026-08-22 · Lanes run: code-reviewer · explorer · frontend-reviewer · performance-reviewer · qa-smoke-tester · security-reviewer (all returned; security re-run once after a truncated first return).
Scope: `apps/inventory/{models,forms,views,urls}/WarehousingBinManagement/`, migration 0006, `templates/inventory/warehouse/**`, overview card, admin rows, `_seed_warehousing`, `LIVE_LINKS["5.5"]`.
QA lane result up front: **42/42 smoke checks PASS** (routes, content, filters vs ORM, lifecycle POSTs with balanced ledger legs, validation, cross-tenant 404s, superuser isolation).

## Burn-down (fix in this order; mark each row when done)

| ID | Sev | Lane ids | Finding (one line) | Fix |
|----|-----|----------|--------------------|-----|
| C1 | Critical | F1 ≡ E1 ≡ E2 | `{% widthratio … as pct %}` yields a STRING in Django 5.1, so `pct >= 100` is always False → over-limit red badge never fires and bar width unclamped (`width:250%`) in `bincapacity/list.html` AND `warehouse/map.html`; the module's headline honesty signal is dead | [ ] open |
| C2 | Critical | P1 | N+1 ledger aggregates: bincapacity list resolves `obj.on_hand` twice per row (cell + widthratio) → ~30 SUM queries per page over each bin's full move history | [ ] open |
| I1 | Important | R1 ≡ S1 | `crossdockorder_edit` has NO status guard server-side — crafted POST edits a received/shipped order (quantity/item/dock) beneath already-posted StockMove legs | [ ] open |
| I2 | Important | R2 ≡ S2 | delete TOCTOU: `is_editable` checked on an unlocked snapshot, then `crud_delete` re-fetches WITHOUT lock or re-check → concurrent receive() can be deleted after posting legs, orphaning ledger provenance | [ ] open |
| I3 | Important | S3 | ship()/cancel() shortfall check is lock-free vs concurrent outbounds sharing one dock (two orders of different items excepted) — racing POSTs can both pass and drive the dock negative; serialize by locking the Item row inside the action's transaction before the balance read | [ ] open |
| I4 | Important | P2 ≡ R5 | `_over_capacity_count` runs per render, walking every profile with 2 property queries each ("one pass" docstring is false) | [ ] open |
| I5 | Important | R3 | seeder `--flush` deletes CrossDockOrder rows but their StockMove legs persist; `next_number` restarts at XD-00001 so reseeded orders join the PREVIOUS generation's legs via reference match, and DOCK-1 on-hand accumulates across generations | [ ] open |
| I6 | Important | F2 | crossdockorder/detail.html has no Delete button even for drafts (delete only reachable from list row); sibling convention is Back/Edit/Delete | [ ] open |
| M1 | Minor | R4 | chip uses rounded `utilisation >= 100`, filter/map use raw `on_hand >= max_quantity` → boundary rows disagree (99.96% quantizes to 100.0) | [ ] open |
| M2 | Minor | R6 | forms `_lot_queryset`: `raw.isdecimal()` then `int(raw)` without range cap → over-range value raises OverflowError at query time (the L11 class); use `apps.core.crud.as_db_int` | [ ] open |
| M3 | Minor | R7 | WarehouseMap edge cases: a warehouse whose parent is another warehouse renders twice (section header + child row); a cycle island among non-warehouse locations appears nowhere despite the "nothing silently dropped" comment | [ ] open |
| M4 | Minor | S4 | model `clean()` checks dock_location/lot_serial tenancy but not `item` (admin path bypasses form `_reject_foreign`) | [ ] open |
| M5 | Minor | S5 | `recent_moves` / `BinCapacity.on_hand` rely on transitive tenant scoping via location FK; make the tenant filter explicit like `ledger_moves()` does | [ ] open |
| M6 | Minor | P3 | CrossDockOrder default ORDER BY `-scheduled_date,-id` has no supporting index (only `(tenant,status)` exists) → filesort per list render | [ ] open |
| M7 | Minor | F3 | limits rendered as raw str(Decimal) while adjacent figures use floatformat — apply `-2` (weight/qty) / `-3` (volume) consistently | [ ] open |
| M8 | Minor | F4 | XD detail omits `notes` entirely when blank; sibling shows a muted "No notes…" placeholder | [ ] open |
| M9 | Minor | F5 | XD quantities displayed `floatformat:"-2"` but the field is 4-dp for lot-tracked goods (0.0001 renders as "0") — use `-4` | [ ] open |
| M10 | Minor | E4 | seeder get_or_create defaults `parent=zone` for WH-MAIN-A1 can never apply (seed_scm created A1 under main first) — comment claims zone holds two bins; align defaults/comment with reality instead of re-parenting another module's seeded row | [ ] open |
| M11 | Minor | E5 | `--flush` deletes BinCapacity + CrossDockOrder but excludes both from the `deleted` tally it prints | [ ] open |
| M12 | Minor | E8 | WarehouseMap docstring says "two queries"; it runs three (locations, group-by, profiles) | [ ] open |
| M13 | Minor | E6 | urls/__init__ docstring has a malformed empty-segment token where `""` was meant | [ ] open |
| M14 | Minor | QA(a) | custom "different item" clean() message unreachable via normal POSTs (form narrowing intercepts with generic invalid-choice wording) — refusal correct, wording differs | [ ] open |
| M15 | Minor | QA(b) | seeded over-limit demo self-destructs if a smoke cancels the seeded received order (compensating move nets DOCK-1 back under cap) — mitigation belongs in temp scripts / future fixture, not app code | [ ] open |
| M16 | Minor | E7 | no test_warehousing_* quartet yet — addressed by Phase 6 test wave, not the fixer | [ ] open |

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
