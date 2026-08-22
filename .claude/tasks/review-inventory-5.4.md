# Review — inventory 5.4 Receiving & Putaway

Review wave over changeset `35d1688b..HEAD` (16 files, +890): PutawayRule model + deterministic
resolver, form, views (CRUD quintet + computed suggestions queue), urls, four templates,
migration 0008, wiring hunks (package `__init__`s, admin, seeder, LIVE_LINKS).

## Lane coverage

| Lane | Result |
|---|---|
| code-reviewer | 3 findings (all Minor) |
| explorer | 7 findings (1 Important) |
| frontend-reviewer | 3 findings (2 Low, 1 polish) |
| performance-reviewer | 1 batch finding (Important; P2/P3 subsumed) |
| qa-smoke-tester | 1 Critical, 1 Important, 2 anomalies + DB restored |
| security-reviewer | 1 Important, 3 Minor |

No lane NO RESULT — no re-run needed.

## Findings (fix in ID order)

### Critical

- [x] fixed **C1** — `apps/inventory/models/ReceivingPutaway/PutawayRules.py:94` — `clean()` reads
      `getattr(self, name)` on the required `destination` FK; when a POST supplies a cross-tenant
      pk (removed from cleaned_data by the tenant-scoped queryset) or omits destination entirely,
      `construct_instance` leaves the FK unassigned and attribute access raises
      `RelatedObjectDoesNotExist` → **unhandled 500**, and the designed "That record belongs to
      another workspace." error can never render. Repro (qa lane): POST create with
      `destination=<globex pk>` as acme → 500; POST omitting destination → same 500.
      **Fix:** key the guard off `<name>_id` and skip unset FKs (`if getattr(self, f"{name}_id") is None: continue`),
      keeping the same field-keyed error dict. Verify BOTH repros then render form errors instead of 500.

### Important

- [x] fixed **I1** — `apps/inventory/views/ReceivingPutaway/PutawayRules.py:54-85` — rule
      create/edit/delete are `@login_required` only; sibling 5.x config CRUD is admin-gated
      (`ApprovalRules.py` uses `core.decorators.tenant_admin_required`). Any workspace member can
      rewrite routing config. **Fix:** add `@tenant_admin_required` to `_create/_edit/_delete`
      and hide Edit/Delete affordances for non-admins in list/detail templates (mirror 5.3's
      template gating pattern).
- [x] fixed **I2** — view:140-145 + models:156-178 — stats loop resolves the FULL filtered set at
      ~3 queries/task (rules + StockMove GROUP BY + tenant Location map each call; `by_pk` and
      ancestry chains rebuilt per task). Q ≈ 3N+4 vs measured sibling `labor_board` O(1)/request;
      multi-second at a few-hundred-task backlog. **Fix:** signature-compatible batch preloader —
      optional kwargs `resolve_putaway_suggestion(task, *, rules=None, by_pk=None, on_hand=None)`;
      view preloads once per request (rules select_related'd; locations map; StockMove aggregate
      grouped by item via `item_id__in=distinct items`); resolver falls back to self-loading when
      kwargs absent (keeps direct-call tests working). Target flat ≤~10 queries/request.
- [x] fixed **I3** — `apps/inventory/{models,forms,views,urls}/ReceivingPutaway/` lack `__init__.py`
      (implicit namespace packages). Every sibling sub-module ships docstring inits; models copy
      also re-exports. Works today by accident. **Fix:** add four `__init__.py` mirroring siblings
      (`models/__init__.py` gets `from .PutawayRules import PutawayRule, resolve_putaway_suggestion` + `__all__`).

### Minor

- [x] fixed **M1** — models:134-138 — consolidation tier sorts by `_walk_key` which prepends an
      `is_pickable` group flag; frozen contract says "pick_sequence ASC then code ASC".
      Deterministic but off-contract. **Fix:** tier-2 sort key `(pick_sequence or _UNSEQUENCED, code)`.
- [x] fixed **M2** — views:`_ancestry_contains` starts at `start_pk`'s parent, so a task staged AT the
      warehouse row itself vanishes from its own warehouse filter (qa-verified: seeded PUT-00002
      disappears). **Fix:** return True when `start_pk == ancestor_pk` before walking parents.
- [x] fixed **M3** — putaway_suggestions.html:67-68 — refusal rows read "No Suggestion Found" twice
      (hardcoded span + resolver reason already begins with that phrase). **Fix:** drop the
      hardcoded span; render only `row.suggestion_reason` as muted text.
- [x] fixed **M4** — putaway_suggestions.html:65 — suggestion reason rendered inside `badge-info`; full
      sentences wrap awkwardly in a pill. **Fix:** render reason as small muted text under the bin
      code (badges stay for short statuses only).
- [x] fixed **M5** — forms/views import models via direct entity-module path
      (`from apps.inventory.models.ReceivingPutaway.PutawayRules import ...`) while all 11 sibling
      modules use package-root spellings. **Fix:** switch to `from apps.inventory.models import ...`
      / `from apps.inventory.forms import ...`; delete the stale build-phase comments.
- [x] fixed **M6** — urls/__init__.py docstring lists `putaway-rules/`, `putaway-suggestions/` after
      `warehouse-map/` but the concat places them before vendor-communications. **Fix:** align the
      prose with actual route order.
- [x] fixed **M7** — seed_inventory.py --flush help text omits "putaway rules" though flush deletes them.
      **Fix:** add to the enumeration string.
- [x] fixed **M8** — seed_inventory.py success line always prints "(+1 open putaway task)" even when zero
      tasks were ensured. **Fix:** track whether a task was created and interpolate accordingly.
- [x] fixed **M9** — seed_inventory.py docstring claims "no items are invented here" while rule 1 may
      invent location CR-01. **Fix:** reword honestly ("creates CR-01 if missing").
- [x] fixed **M10** — models cost-note parenthetical says "~a 25-row page" but the view resolves the whole
      filtered queue for stats. **Fix:** reword to reflect full-set resolution (post-I2 wording:
      preloaded context, flat queries).
- [x] fixed **M11** — models:161,247 — resolver trusts `task.item`/`task.from_location` tenancy (unreachable
      today; future non-form write paths could poison reasons). **Fix:** cheap top-of-resolver guard:
      if `task.item.tenant_id != task.tenant_id` return the honest refusal triple.
- [x] fixed **M12** — suggestions page has no nudge when `stats.covered_by_rule == 0`. **Fix (template-only):**
      one-line hint under the stat strip pointing at Manage Rules.

### Accepted-as-is (no action)

- junk `?is_active=` renders unfiltered — deliberate L11 skip-filter posture, consistent with scm lists.
- `--flush` wipes across tenants — house-wide CLI pattern, queued for an app-wide sweep, not 5.4's.
- superuser add-page redirects with flash (guard-first crud behaviour) — matches foundation design.
- `?page=999` clamps to last page — identical to `/scm/putaway/`.

## Verification bar for the fixer

After every fix: `manage.py check` clean; re-run `temp/smoke_receiving_5_4.py` (must stay ALL PASS);
re-probe C1's two POST cases expecting rendered form errors; count queries on the suggestions page
(post-I2 target ≤ ~10); commits one file per commit.
