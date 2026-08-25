# Review — Inventory 5.20 Units of Measure (UOM)

- **Changeset:** `b70f382de1f1d954a026df10a4765d9b2eae8f87..HEAD` (2026-08-25)
- **Lanes:** code+performance · security · frontend+QA smoke (three parallel read-only agents; live shell probes included)
- **Scope:** `UomConversion` model + BFS conversion engine, CRUD quintet, read-only calculator, 4 templates, LIVE_LINKS["5.20"], migration 0028, `_seed_uom_conversions`

## Summary table

| ID | Severity | Lane | File | Finding | Status |
|----|----------|------|------|---------|--------|
| F1 | Important | code+security | views/UomCalculator.py | `?qty=1e999` / `Infinity` / `NaN` / `1e999999`: legal-parse Decimals crash `quantize()` (`decimal.Overflow`/`InvalidOperation`) → 500; NaN silently renders | [x] fixed — finite-check refuses Infinity/NaN ("plain finite number"); compute block wrapped in `except ArithmeticError` (decimal exception root) → "too large to convert" honest card; 4 harness probes prove it |
| F2 | Minor | code+frontend | models/UomConversions.py:158 | `_active_edges` select_related missing `item` → per-hop N+1 on calculator route table | [x] fixed — `"item"` added |
| F3 | Minor | code | forms/UomConversions.py | from==to refusal duplicated form+model clean() → error rendered twice | [x] fixed — kept ONLY in model clean() (keyed field error) |
| F4 | Minor | code | models/UomConversions.py clean() | FK tenant loop keyed off attribute access; convention is `<name>_id` keying (PutawayRule C1 pattern) | [x] fixed — explicit per-FK `_id` guards |
| F5 | Minor | code | models/views | `resolve()` was dead code | [x] fixed — detail view now stamps a resolver-derived "Fires today?" verdict from it |
| F6 | Minor | code | models | Duplicate-probe race on NULL-item defaults (MariaDB cannot express the partial unique) | [~] skipped — accepted demo posture; deterministic tie-break in `_active_edges` keeps resolution sane; functional-index hardening deferred to a real-concurrency pass |
| F7 | Minor | code/perf | list+calculator views | three/separate COUNT queries | [x] fixed — ONE conditional `aggregate()` each |
| F8 | Minor | code | admin.py | changelist `__str__` + FK lookups with no select_related | [x] fixed — `list_select_related` added |
| G1 | Info | frontend | calculator.html | dead `{% if to_uom %}` guard in result label | [x] fixed — removed (result only set when both resolved) |
| G2 | Info | frontend | calculator.html breadcrumb | parent crumb said "Units of Measure", siblings say "UOM Conversions" | [x] fixed |
| G3 | Info | qa | temp/verify_uom_520.py | harness expected 302 on foreign delete (actual correct = 404 IDOR block) | [x] fixed (harness-only, gitignored) |

## Verified-clean highlights

- Engine math traced end-to-end: identity returns `[]`, unreachable returns `(None, None)` and callers SAY so; product quantized once; tier override is PER EDGE so chains mix tiers correctly (proven live: PLT→CASE default × CASE→EA item rule = 960); BFS depth cap exact at 5 hops; ties deterministic by id.
- Tenancy defense-in-depth held under live probing: cross-tenant `resolve()` → None; every object fetch tenant-pinned 404s; calculator `_pick` resolves only inside pre-scoped querysets; zero `|safe`; deletes POST-only; no raw SQL.
- Design system audit clean: colour-named badges only, sanctioned stat-icons, full component vocabulary matches sibling templates, valid Lucide names, admin-gated affordances.
- Smoke: 22 PASS incl. bogus-scope/junk-pk/bad-bool GET probes degrading gracefully; member create 403.

**Verdict:** approve after F1 (fixed). All Critical/Important findings closed; one Minor consciously skipped with reason (F6).
