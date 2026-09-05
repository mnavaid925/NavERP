# Review findings — Procurement 6.16 Supplier Performance & Evaluation

Findings are collected here, never carried only in the transcript (CLAUDE.md Phase 4).
Sorted Critical → Important → Minor, IDs assigned once all six reviewers have reported.

**Review scope — path globs, NOT `BASE...HEAD`.** Four sessions (6.16/6.17/6.18/6.19) commit to
`main` in this one working tree, so a commit range from this session's start sha returns three other
sub-modules' files. Reviewers handed a range would file findings against the wrong sub-module, and
the fixer would then "fix" a peer's code against a contract it never read. Scope every reviewer to:

```
apps/procurement/{models,forms,views,urls}/SupplierPerformanceEvaluation/**
apps/procurement/performance.py
templates/procurement/performance/**
```

Note the `**`, not `*`: a single `*` matches only the five entity DIRECTORIES under
`templates/procurement/performance/` and none of the 14 `.html` files — a reviewer given that glob
reads nothing and reports clean, which is the answer you were hoping for. And note
`performance.py` listed separately: no sub-package glob reaches a flat module at the app root.

---

## Pre-review findings (found during the build, before the six reviewers run)

These were surfaced by the build agents themselves or by a peer session. They are recorded now so
they cannot be lost, and must be carried into the deduped list rather than re-discovered.

### PB1 — `supplierkpiscore_detail` fetches the joined row twice (performance)

`apps/procurement/views/SupplierPerformanceEvaluation/ScorecardKpiScores.py`

```python
obj = get_object_or_404(_score_qs(request), pk=pk)   # full row, select_related(*_SCORE_RELATIONS)
...
return crud_detail(request, model=SupplierKpiScore, pk=pk, ...,
                   select_related=(*_SCORE_RELATIONS, "computed_by"))   # fetches it AGAIN
```

The first fetch exists only to read `obj.breakdown` and `obj.source_at_time`; `crud_detail` then
repeats the same tenant-scoped, same-`select_related` query. Two joined fetches where one would do.

Not the cheap case: the sibling views deliberately avoid this by pre-fetching narrow —
`supplierfeedback_detail` and `improvementplan_detail` both use `.only(...)` for their pre-check, so
they pay a trivial second query rather than a duplicated join.

**Fix options:** either narrow the pre-fetch to `.only("pk", "tenant_id", "source_at_time",
"breakdown")` to match the siblings, or hand-roll `render()` the way `supplierevaluation_detail`
already does (its docstring gives the cross-app-import reason; the precedent for the pure
performance case is `contract_detail` in `ContractsManagement/Contracts.py:78`). Hand-rolling is one
query and sets exactly the same context keys `crud_detail` would.

Independently flagged twice: by the Entity 3 build agent, and by the concurrent 6.18 session.

### PB2 — confirm-dialog idiom is inconsistent inside 6.16 (minor / consistency)

Contract §8 pins `onclick="return confirm(...)"` on the button. Entity 1's
`templates/procurement/performance/kpi/list.html` and `kpi/detail.html` instead use `onsubmit` on
the form; Entities 2, 3 and 4 follow the contract. Both work — this is drift, not a bug — but 6.16
should not ship two idioms for the same gesture. Normalise Entity 1's two templates onto `onclick`.

### PB3 — `SupplierFeedback.__str__` renders `SFB · None` on an unsaved instance (minor)

Contract §1.3 pins `f"{self.number or 'SFB'} · {self.supplier_id and self.supplier.name}"`. When
`supplier_id` is unset the conjunction evaluates to `None` and the f-string renders the literal
string `"None"`. Only reachable on an unsaved instance (admin add form, a `repr()` in a traceback),
so it is cosmetic. The Entity 3 agent followed the frozen contract verbatim rather than silently
improving it — correct process; recording it here is the right place to fix it.

### PB4 — `supplierkpi_delete` diverges from contract §3.1, deliberately (accepted, do not "fix")

§3.1 specifies only `@login_required + @require_POST`, but §1.2 pins `SupplierKpiScore.kpi` as
`on_delete=PROTECT`, so a bare `crud_delete` on any KPI with measured history raises an uncaught
`ProtectedError` (500). The Entity 1 agent added the app's existing guard — `get_object_or_404` →
`transaction.atomic()` → `except ProtectedError` → `messages.error` naming the blockers → redirect —
following `apps/core/views/Party.py:47-72` and
`apps/accounting/views/GeneralLedger/Currencies.py:64-72`.

**This is a contract defect, not a code defect.** Recorded so a reviewer reads it as intent and does
not file it as an unauthorised deviation, and so the contract can be amended rather than the code
reverted.

### PB5 — `benchmark_rows()` slices before it filters (correctness at scale)

`apps/procurement/performance.py`

The `ROW_CAP` (500) slice is applied **before** the Python-side tier/category filter. Under 500
scorecards in a period the result is exact. Above that, a tier or category filter sees only the
first 500 rows by `party__name` — so a filtered cohort silently ranks a truncated population, and
the supplier ranked "top of tier" may simply be the best of the first 500 alphabetically.

Disclosed rather than silent: `truncated` is returned and the board prints a warning. But the
warning says *the list was cut*, not *your filter was applied to a cut list*, which is the part that
changes the meaning of the ranking.

**Fix:** apply the tier/category filter in the queryset before the slice, so the cap truncates the
filtered cohort rather than the filter narrowing a truncated one.

Found by the boards build agent while measuring, and flagged as out of its scope (the function was
already committed by the Entity 2 agent).

### PB6 — `trend_series()` truncates at 24 but the shared cap constant says 500 (minor)

The boards re-export `ROW_CAP` (500) per the contract's §5 convention, but `trend_series()` actually
truncates at `PERIOD_CAP` (24). The trend board therefore passes `PERIOD_CAP` as its `row_cap` so
the page cannot print "more than 500 scorecards" when the cut happened at 24. Correct behaviour,
but the two caps sharing one context key name across three boards is a trap for the next editor —
worth either renaming the key per board or documenting why trend's differs.

---

## RESUME POINT — where 6.16 stands (session ended here)

**Build: COMPLETE.** Four entities + three boards, all committed. `manage.py check` clean.

**Integrate: DONE except the seeder.** Verified on disk this session:

| Step | State |
|---|---|
| four `SupplierPerformanceEvaluation/__init__.py` re-export blocks | done (33/22/24/51 lines) |
| `models/` `forms/` `views/` `urls/` app-level `__init__.py` | done |
| `admin.py` — four models registered | done (`07f0b03c`) |
| `apps/core/navigation.py` — `LIVE_LINKS["6.16"]` | done (`d33ac440`) |
| `urls/__init__.py` — appended last | done (`851c486c`) |
| **`seed_procurement.py` — `_seed_supplier_performance`** | **NOT STARTED — the only code left** |
| `makemigrations` + `migrate` | **DONE** — `0026` (`a0f4095d`), applied, single leaf, all four tables live |
| seed / smoke / reviewers / fixer / tests / SKILL+README | **NOT RUN** |

Verified by resolver walk (not grep — grep cannot see factory-generated names):
**33 of 33 routes register, zero duplicate url names app-wide, procurement total 385.**

### The seeder is the only code left. Two traps it must handle

1. **`seed_scm` leaves its scorecards `published`** (`apps/scm/management/commands/seed_scm.py` ~288:
   creates `draft`, recomputes, then flips to `published`). `generate_scorecard_lines` **refuses on
   anything but draft**, so the seeder must create its OWN draft `scm.SupplierScorecard` per demo
   supplier for a prior period and generate onto those. Seeding against the scm scorecards produces
   a page that is correct, empty, and looks broken.
2. Dispatch line goes **immediately after `self._seed_budget_cost(tenant)`**; 6.17/6.18/6.19 append
   theirs after. Idempotent (`.exists()` guard, `get_or_create`), reuse seeded `core.Party`
   suppliers, never `--flush`.

### MIGRATION: RESOLVED AND APPLIED — `0026` (`a0f4095d`)

**Superseded the hold below.** The `ProcurementPolicy` ownership settled and was verified on disk:
6.17's `PolicyAttestation.policy` FKs `"procurement.ProcurementPolicy"` by string at 6.19's table
(`RiskComplianceManagement/Policies.py:265`), and exactly one `ProcurementPolicy` exists app-wide.
6.19 consented to their models landing in a migration authored here. Generated, committed, applied:

```
procurement leaves: ['0026_procurementdocument_knowledgeresource_and_more']  count: 1  (linear)
migrate -> OK ; check -> no issues
procurement_supplierkpi / _supplierkpiscore / _supplierfeedback / _supplierimprovementplan : all live
```

`0026` carries **eight** tables — 6.16's four and 6.19's four — because `makemigrations` reads the app
model registry and has no per-model or per-path flag. 6.17's and 6.18's are absent only because
theirs were not re-exported at that moment. **The next generator takes `0027`.**

The reasoning that led to holding is kept below because it is the reusable part.

### Why generating was held until ownership settled

`makemigrations procurement` **cannot be scoped to one session's models.** It reads the app model
registry, and a `--dry-run` this session showed it would emit ONE migration containing 6.19's four
models alongside 6.16's four:

```
0026_procurementdocument_knowledgeresource_and_more.py
    + ProcurementDocument · KnowledgeResource · ProcurementDocumentRevision · ProcurementPolicy   (6.19)
    + SupplierKpi · SupplierImprovementPlan · SupplierFeedback · SupplierKpiScore                 (6.16)
```

A shared migration is functionally fine. **The blocker is `ProcurementPolicy`** — still disputed
between 6.17 and 6.19 as of this session's end. Generating would bake `procurement_procurementpolicy`
into the graph under a 6.16 migration and settle by accident a question 6.16 is not party to,
converting a class rename into a cross-session migration-graph edit.

**Before generating, confirm with the 6.17 and 6.19 sessions that ownership is settled.** Then
announce immediately before running (only *simultaneous* generation splits the graph), and verify a
single leaf afterwards:

```python
MigrationLoader(None, ignore_no_migrations=True).graph.leaf_nodes()   # filter app == 'procurement'
```

Leaf at session end: `0025_remove_budgetmapping_prc_bmap_tnt_active_idx_and_more`.

**Registration is the lever** (found by the 6.18 session): a model enters the registry only when
`models/__init__.py` re-exports it. 6.16's block has landed, so 6.16's models are now exposed to
capture by whoever generates next — including a peer. That is accepted, not a problem: the four
models are settled and verified.

### Remaining phases after the seeder

migrate → `seed_procurement` **twice** → `manage.py check` → smoke as `admin_acme`/`password`
(assert content, not status) → the six reviewers **scoped to path globs, NOT `BASE...HEAD`** (see the
top of this file) → `code-fixer` on findings PB1–PB6 → tests → SKILL.md + README.

---

## Smoke gate — 123 assertions, 2 Important + 1 Minor (all reproduced independently)

Run as `admin_acme` against MySQL with `0026` applied. All 33 routes exercised (20 GET + 13 POST).
Empty branch exercised on all five registers with every `{% empty %}` href resolved AND fetched;
cross-tenant IDOR run in full (9/9 GET + 13/13 POST -> 404, zero mutation proven by snapshot).

### S1 — Important — `supplierkpiscore_list`: `?source=<junk>` silently empties the register

```
(no params)   -> 41 rows | empty-state False
?source=zzz   -> 0  rows | empty-state True    <-- register wiped
?band=zzz     -> 41 rows | empty-state False   <-- correct fallback, SAME PAGE
```

A tenant with 41 generated lines is told it has none. The two dropdowns on one register disagree.

**Root cause, verified:** `crud_list`'s L11 enum guard (`apps/core/crud.py::_enum_values`) disables
itself for a field with no `choices` — and `SupplierKpiScore.source_at_time` is
`CharField(max_length=8, blank=True, editable=False)` with **no choices**
(`ScorecardKpiScores.py:99`), while the filter tuple `("source", "source_at_time", False)`
(`views/.../ScorecardKpiScores.py:325`) passes the raw GET value into `.filter()`.

Contract §5.7 anticipated this and accepted it — "the template's `source_choices` dropdown is the
ONLY thing keeping the values legal". That holds only for a user who never edits the URL, which is
precisely the L11 case. **Not drift against the contract; drift against L11.**

**Fix (zero-migration preferred):** validate `source` in the view against `SupplierKpi.SOURCE_CHOICES`
and drop it from `filters=` when unrecognised. Adding `choices=` to the model field would engage the
existing guard but costs an `AlterField` migration.

### S2 — Important — `supplierevaluation_list` paginates an UNORDERED queryset

Django raises `UnorderedObjectListWarning` from `apps/core/crud.py:23` on **every** request.
Reproduced directly:

```
with    annotate(): qs.ordered = False   ORDER BY present in SQL: False
without annotate(): qs.ordered = True
```

`_evaluation_qs()` (`views/.../ScorecardKpiScores.py:104-108`) adds
`.annotate(line_count=Count("procurement_kpi_scores"))`, whose GROUP BY makes Django drop
`SupplierScorecard.Meta.ordering = ["-period_end","-id"]`. The view docstring still claims "newest
period first"; the register actually renders in pk order. **On MySQL, LIMIT/OFFSET over an unordered
GROUP BY is undefined**, so page 2 may repeat or drop rows once a tenant exceeds 15 periods. Only
this one of the five registers is affected — the other four report `ordered=True`.

Invisible to a status-only check: 7 seeded scorecards fit on one page, so page 2 was unreachable.

**Fix:** append `.order_by("-period_end", "-id")` to `_evaluation_qs()`. One line, no migration.

### S3 — Minor — the literal word "None" as human copy where `&mdash;` is used elsewhere

Five `{% else %}` branches print the English word "None". Verified in source to be template
literals, **not** leaked Python `None` — so not defects — but indistinguishable from a leak to a
reader or a reviewer, and the first is a bare unstyled token:

| File | Line |
|---|---|
| `performance/evaluation/detail.html` | 158 (bare, no `text-muted`) |
| `performance/improvementplan/detail.html` | 134, 154 |
| `performance/feedback/detail.html` | 68 |
| `performance/kpiscore/detail.html` | 131 |

### Confirmed working (not exhaustive — see the run for the full 123)

Generate is idempotent (9 -> 9 -> 9 over two presses) and **refuses on a published scorecard** with
the reason rendered on the page, not just logged. All 13 POST verbs 405 on GET. `improvementplan_close`
403s a non-admin with no mutation. Boards carry real rows at the demo period: benchmark ranks 5 with
cohort avg 63.50, trend plots 2 periods x 9 KPI series, perception-gap shows 2 rows with both sides.
Zero leak markers, zero raw-Python repr, zero non-existent badge classes, reflected `q` escaped.
Every contract §5 context key present in the real render context on all 18 pages.

---

## Reviewer findings

*(appended as each of the six reviewers reports: code-reviewer → explorer → frontend-reviewer →
performance-reviewer → qa-smoke-tester → security-reviewer)*
