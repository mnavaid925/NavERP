# Review — Inventory 5.17 Reporting & Analytics (2026-08-25)

Five parallel read-only lanes over the 5.17 changeset (`apps/inventory/{models,forms,views,urls}/ReportingAnalytics/`,
`templates/inventory/reports/**`, migration 0022, seeder block, navigation entry).
BASE `dce1270c9bf997a898035edb974eb123c3cbf20e`. QA smoke executed live against `nav_erp`.

## Summary table

| Lane | Verdict | Findings |
|------|---------|----------|
| code-reviewer | 1 Critical, 2 Important, 6 Minor | C1, I1, I2, M1–M6 |
| performance-reviewer | Clean — O(1) queries, no N+1 | P1–P4 (all Minor), P5/P6 pass |
| frontend-reviewer | Solid; 2 Important, 3 cosmetic | F1–F5 |
| qa-smoke-tester | **12/12 PASS** live (render, generate→freeze, admin delete, IDOR 404, member 403, leak scan) | none |
| security-reviewer | Injection-free, CSRF-clean, IDOR-guarded | S1–S5 |

## Findings & dispositions

- [x] fixed — **C1/S1/S2 (Critical)** `ReportSnapshotForm(request.POST or None)` built without
      `tenant=request.tenant`: location dropdown listed ALL tenants' locations and `_reject_foreign`
      rejected even own-tenant locations (scoped snapshots unusable). Fixed by passing the kwarg +
      docstring noting why (views/ReportingAnalytics/ReportSnapshots.py).
- [x] fixed — **I1/F2** the four reports' "Freeze snapshot" buttons send `?type=` but the form never
      pre-selected it. GET now validates against REPORT_TYPES and seeds `initial`.
- [x] fixed — **I2** a SKU received-and-sold-through inside the window (both endpoints stockless,
      COGS > 0) was labelled velocity "dead". Engine now falls back to whichever endpoint value
      exists for the average, and a demand-with-no-resting-stock item reads "fast" (it is the fastest
      possible mover); documented in `_velocity`.
- [x] fixed — **F1** `.stat-icon.red` did not exist in theme.css (aging + snapshot detail KPI tiles
      rendered unstyled). Added `.stat-icon.red` (also repairs procurement overview's same bug).
- [x] fixed — **F3/M5b** snapshot-detail empty-state colspan now matches per-type column count.
- [x] fixed — **F4** deprecated lucide `bar-chart-3` → `chart-column` (abc page + overview card).
- [x] fixed — **S3** 4300+-digit `?days=` blew Python's int-str limit inside `int()`; clamp_window
      length-guards before parsing.
- [x] fixed — **M2** filter dropdowns were derived from already-filtered rows (self-narrowing);
      all four views now build pickers from the full row set (StockLevels rule).
- [x] fixed — **M3/S5/P2** seeder: docstring said two but seeded three; `username="admin"` fallback
      not tenant-scoped; one Ledger now threaded through all three freezes via `build_summary(ledger=)`.
- [x] fixed — **P1/P4** Decimal hoists (`days_dec`, module `_HALF`); Ledger fetch filters
      `item__item_type="stock"` at the DB.
- [x] fixed — **M1** dead context keys removed (`velocity_css`, `abc_css`, `health_css`,
      `bucket_labels`, `counts`, list/detail `type_css`) — house style is inline badge chains.
- [x] fixed — **M4** all five view modules carry the package-standard
      `from apps.inventory.views._common import *` header.
- [~] skipped — **M5** ABC rank column uses `forloop.counter` (ranks renumber per page): every
      sibling register does the same; a global rank needs window functions for zero UX gain.
- [~] skipped — **M6** aging bucket cells quantized independently can drift a rounding residue from
      On Hand; display-level only, sums stay correct at raw precision.
- [~] skipped — **F5** Actions-column idiom differs cosmetically from sibling lists; functionally
      identical flex layout.
- [~] skipped — **S4** snapshot generation unmetered for members: accepted threat model (own-tenant,
      audited write; reviewers flagged acceptable). Revisit if abuse appears.
- [~] skipped — **Info** `{{ object.number }}` inside onsubmit JS strings: server-minted IRS-
      numbers, autoescape intact; noted as pattern to avoid.

## Verified clean (both reviewers)
Engine math mirrors SCM's costing walk (transfers excluded from costing, included in physical
aging buckets; WAC at cached average_cost; division guards everywhere); every query path
tenant-scoped; dict-row filters run BEFORE pagination; migration 0022 field-for-field matches the
model; navigation labels byte-match NavERP.md bullets; audit rows on create/delete; no `.raw()`/
`|safe`; CSRF on all POST forms; pagination/window caps in place.

## Post-fix verification
`manage.py check` clean · smoke script 7/7 PASS (all pages + generate POST + IDOR 404) ·
QA lane 12/12 PASS with DB cleanup confirmed.

*Note:* this sub-module was built while a concurrent session shipped 5.15/5.16/5.18 in the same app;
migration numbering was de-conflicted (0022 scoped to this sub-module's model only) and shared-file
wiring landed through either session's commits.
