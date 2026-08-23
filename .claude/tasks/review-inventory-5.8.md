# Review — inventory 5.8 Lot & Serial Number Tracking

Date: 2026-08-23 · Base: `295c788b6d8f2dd003bc9fdedcdd9db9e4f63513` · Two read-only reviewer lanes
(frontend+QA, backend+security) run in parallel over the sub-module changeset; findings merged,
deduped and fixed in the main session (no code-fixer agent available in this environment).

| Lane | Result |
|------|--------|
| frontend+QA | 0 Critical / 1 Important / 6 Minor |
| backend+security | 0 Critical / 2 Important / 6 Minor |

## Findings & dispositions

| ID | Sev | Where | Finding | Status |
|----|-----|-------|---------|--------|
| I-1f | Imp | shelflifepolicy/list.html | List page had no filter bar while the view implements q + fefo filters | [x] fixed — standard .filter-bar added |
| I-1b | Imp | FefoBoard._board_items | Dropdown fed LOT pks into an ITEM queryset | [x] fixed — item set derived via LotSerial→item_id DISTINCT walk |
| I-2b | Imp | ShelfLifePolicy.fefo_enforced / FefoBoard sort | Advisory flag had no functional effect on pick order | [x] fixed — advisory regimes sort by sku/number in their own tier; enforced keep true FEFO; test pins both orders |
| M-1b | Min | Traceability._render_trace | Reverse FK lacked explicit tenant predicate (defence-in-depth) | [x] fixed |
| M-2b | Min | _sibling_moves | Genealogy keys on free-text reference equality — writer discipline, not schema | [~] skipped — documented in docstring; schema link deferred until a posting-path column exists |
| M-3b | Min | LotNumberRule.generate | Past-dated expiry minted as status "available" | [x] fixed — derives expired/available from expiry_date |
| M-4b | Min | lot_generate view | Double-submit mints two distinct valid numbers | [~] skipped — intentional (append-only master); rationale documented on generate() |
| M-5b | Min | seed_inventory | Hardcoded/false success counts | [x] fixed — actual creations counted |
| M-6b | Min | seeder apply_receipt | Writes spine average_cost outside app tables without a note | [x] fixed — comment added (mirrors seed_scm posting shape) |
| M-1f | Min | shelflifepolicy/list.html | policy_count context unused | [x] fixed — rendered in header |
| M-2f | Min | trace picker | Silent 25-row cap with no hint | [x] fixed — hint line added |
| M-3f | Min | trace genealogy chips | Negative consumption quantities rendered raw | [x] fixed — Abs("quantity") annotate; chips show magnitude |
| M-4f | Min | generate.html | form wrapped whole card, off-pattern DOM | [x] fixed — form inside card body |
| M-5f | Min | lotrule/list.html | seq(05) implied a literal leading zero | [x] fixed — "seq(N digits)" |
| M-6f | Min | fefo.html icons | skull/octagon-alert/circle-dashed unproven lucide names | [x] fixed — swapped to calendar-x/ban/clock |

Also caught post-review by tests: `Abs` imported from wrong module (`django.db.models.functions`),
and the advisory-sort first implementation only re-tiered but still expiry-sorted within the
advisory group — both fixed and pinned by test.

## Verification

- `manage.py check` green; migration 0013 applied to nav_erp.
- Seeder ×2 idempotent (rules/policies skip; demo lots guarded by notes marker).
- HTTP smoke (temp/smoke_58.py): 32/32 — every page 200, FEFO verdicts render, trace sections,
  mint flow creates the spine row and redirects, untracked refusal, cross-tenant IDOR 404s.
- pytest: 46 new tests green (`test_lot_{models,forms,views,security}.py`).
- Full unfiltered app suite: only failures are files owned by other sessions
  (`test_receiving_forms.py` from a prior pass; `test_stockmovementtransfers_*` mid-flight in the
  concurrent 5.7 session) — left untouched per L45.
