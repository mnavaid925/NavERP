# Review — inventory 5.15 Quality Control (QC) & Inspection

Date: 2026-08-25 · Base: dce1270c · Reviewers: code+security, frontend, qa/performance (parallel wave)

Scope: `apps/inventory/{models,forms,views,urls}/QualityControl/`, `templates/inventory/qc/**`,
migration 0023(+0025), `_seed_quality_control`, `LIVE_LINKS["5.15"]`.

## Summary table

| Lane | Verdict | Findings |
|---|---|---|
| Code + security | PASS (post-fix) | I1 I2 I3 M1 M2 M3 |
| Frontend | PASS (post-fix) | F1 F2 F3 F4 F5 F6 |
| QA / performance | PASS | P1(keep) P2(no-op) P3(fixed) P4(note) P5(note) P6(ok) |

## Findings & dispositions

| ID | Sev | Finding | Disposition |
|---|---|---|---|
| I1/F1 | Imp | Quarantine delete button rendered to members whose delete view 403s (list+detail) | [x] fixed — delete gated on `is_admin`; `is_admin` added to list context |
| F2 | Imp | Defect report delete button same mismatch | [x] fixed — gated on existing `is_admin` |
| I2 | Imp | Edit status-guard TOCTOU: unlocked check → crud_edit unlocked save could rewrite beneath posted legs | [x] fixed — guard + save now hold `select_for_update` row lock across the whole request (same lock the verbs take) |
| I3/F4 | Imp | N+1 `checklist_items.count` per checklist list row | [x] fixed — `.annotate(n_items=Count(...))` in `_scoped`, template renders it |
| M1 | Min | `QuarantineOrder.status` not `editable=False` while DefectReport's is | [x] fixed — editable=False + AlterField migration 0025 |
| M2 | Min | `_run_action`/`_ACTION_MESSAGES` duplicated across the two verb modules | [~] skipped — matches the app's module-local verb-runner precedent (CrossDockOrder keeps its own copy); hoisting would touch shared `_common.py` mid-parallel-session for zero behavior change |
| M3 | Min | Fragile `QcChecklistItem.__str__` (`self.checklist_id and self.checklist.name`) forces FK fetch per render | [x] fixed — plain `{self.checklist}` interpolation |
| F3 | Min | Formset-level (`non_form_errors`) never rendered on checklist form | [x] fixed |
| F5 | Min | `date|default_if_none:"—"` never shows the dash (date returns '' for None) | [x] fixed → `default:"—"` (quarantine detail) |
| F6 | Min | Preview renders dangling "SKU →" when no verdict matches | [x] fixed — else-badge + "Another rule wins" indicator |
| P3 | Perf | Preview used `rules=[obj]` (skipped engine's is_active filter; contradicted its own claim) | [x] fixed — preview runs the FULL engine; inactive rules honestly show as not firing |
| P1 | Perf | `preview_items` fetched every rule-detail request | [~] skipped — reviewer verdict: keep (indexed LIMIT-50 picker must render before ?item= exists); autocomplete deferred |
| P2/P4/P5/P6 | Perf | ledger_moves slicing correct; unbounded FK dropdowns noted as production-scaling risk; LIKE %notes% bounded by per_page; seeder aggregates fine | [~] skipped — documented, no action at demo scale |

## Verified-clean highlights

Every view tenant-scoped; all FK vectors rejected in form AND model clean(); transfer pairs
sum zero; scrap/cancel/writeoff shortfall-checked lot-scoped under row+item locks with uniform
lock order (no ABBA); audit rows inside transactions; all destructive verbs admin-gated +
POST-only; resolver deterministic (tier→vendor→priority→id) and tenancy re-filters caller
lists; index prefixes collision-free and match migration; pagination after filters; all 31
template url names resolve; context keys match views throughout.

## Follow-ups for the test wave

See QA lane Part B (test_qc_{models,forms,views,security}.py). Top priorities:
double-click quarantine, cancel-from-held reversal, zone-shortfall refusal, lot-scoped
shortfall, member 403 matrix.
