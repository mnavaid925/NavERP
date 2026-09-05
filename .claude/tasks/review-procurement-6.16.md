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

### 1/6 — `code-reviewer` (verified against the running code and the live DB)

**Verdict:** commit after fixing the four Important findings. No cross-tenant leak, no authorization
bypass, no missing migration.

#### R1 — Important — the two boards publish DIFFERENT composites under the same key

```
performance.py:725  (trend)      composite = _composite(lines)      # 6.16 KPI-line weighted mean
performance.py:839  (benchmark)  composite = card.overall_score     # SCM 4-dimension blend
```

Same key, same supplier, same period, materially different numbers. Reproduced on seeded data at
`2026-08-09`: *Bidder Two BV* ranks **34.62 (grade F, "Underperforming")** on the benchmark board and
**69.87** on the trend board. Rank, percentile and the quadrant segment all ride the wrong figure.

The trend row already carries both (`"composite": composite, "overall": card.overall_score`, line
730), so the distinction was understood — the benchmark board then publishes the other one under the
shared name. `performance.py:5-7` states the module premise is that the boards "can never hold two
answers".

**Fix:** fetch the cohort lines in one `scorecard_id__in` query and use `_composite()`; or rename the
benchmark key to `overall` and change the column header and segment legend to match.

#### R2 — Important — `manual_override = True` fires on an empty run

`performance.py:674` sets it unconditionally, including when `applicable_kpis()` returned `[]` and
`written == 0`. A tenant with no KPI library who presses Generate on a draft scorecard **permanently
hands it to 6.16 with zero evidence written** — and `evaluation/detail.html:284` actively invites that
press from the empty state. Recoverable only via the SCM scorecard form
(`scm/forms/.../SupplierScorecards.py:16`), which is why this is Important rather than Critical.

**Fix:** return the refusal shape when `kpis` is empty, or guard `manual_override = True` on `if written:`.

#### R3 / R4 — Important — two admin-gated controls are offered to non-admins

- `evaluation/detail.html:89` — the Generate button renders for every tenant member, but
  `supplierevaluation_generate` is `@tenant_admin_required`. `can_generate`
  (`views/.../ScorecardKpiScores.py:220`) is computed from status + tenant only. A non-admin gets a
  bare 403 with no warning.
- `improvementplan/detail.html:205` — same shape for Close (`can_close`,
  `views/.../SupplierImprovementPlans.py:192`). The copy at line 223 even says "Closing is
  admin-only" while still offering the control.

**Fix:** add `request.user.is_superuser or request.user.is_tenant_admin` to both flags — the app own
idiom in 18 other procurement templates (e.g. `goodsreceiptinspection/rtv/list.html:130`).

#### R5–R11 — Minor

- **R5** `PerformanceBoards.py:216` — `?category=` unvalidated while `?tier=` two lines above is
  checked and reset on junk; `?category=zzz` silently empties the board. Same shape as S1.
- **R6** `performance.py:690` — the alert `link_url` is a hand-built literal path, not
  `reverse("procurement:supplierevaluation_detail", ...)`; re-spelling the route breaks every alert card.
- **R7** `seed_procurement.py:2598` — dating the 6.16 window one day BEFORE the SCM one makes
  `period_choices(tenant)[0]` always the SCM period, so the benchmark board **default view** lands on
  2 suppliers with `line_count=0` while the 5 generated scorecards sit one period back. Reproduced.
- **R8** `SupplierImprovementPlans.py:344` — the eight status verbs do unlocked check-then-act, unlike
  `vsu_approve` (`VendorManagement/VendorSuspensions.py:163`) which wraps `select_for_update()` + the
  re-check + the save in `transaction.atomic()`. Matters most for `acknowledge:310`, whose "first
  acknowledgement is the date that counts" guard is racy.
- **R9** `kpi/detail.html:113` — `row_cap` is 50 but two of the three lists it describes are capped at
  `_RELATED_CAP` (20). Third instance of PB6.
- **R10** `PerformanceBoards.py:232` — `quadrant_choices` passed but never iterated;
  `benchmark_board.html:170-174` and `:203-206` hard-code the four labels twice.
- **R11 — CONTRACT defect** `performance.py:694` — `skipped` counts KPIs with no measured value, but
  every applicable KPI still gets a line, so `written` already includes each `skipped` one. Contract
  section 6 says "applicable KPIs that produced **no line**". Amend the contract; code and message agree.

#### Clean — coverage statement

- **Multi-tenancy: clean.** All 33 views, five `_*_qs` helpers, four forms, 14 resolvers and six public
  `performance.py` functions filter by tenant; **zero `.objects.all()`**; all four forms call
  `_reject_foreign` on every FK they expose; the two tenant-less scm line models are correctly scoped
  through their tenant-bearing parents.
- **The 14 `DERIVED_RESOLVERS`: clean.** Every join executed against the live DB with no `FieldError`,
  including the three counter-intuitive ones. **No phantom zeros** — `_pct`/`_mean` return `None` on an
  empty denominator, `defect_rate` guards `total <= ZERO`, `suspension_incidents` gates its real zero
  behind `_has_activity`.
- **Freezing: clean.** All seven frozen/denormalised columns written once per `update_or_create`, all
  `editable=False`, all excluded from the two-field edit form.
- **Structure/migration: clean.** 4 models + 4 forms + 33 views re-exported and in `__all__`, 33/33 url
  names reverse, `makemigrations --check` reports no changes.
- **Templates: clean.** 22/22 POST forms carry `{% csrf_token %}`, zero `{# #}`, zero non-existent badge
  classes (the five `badge-success` hits sit inside `{% comment %}` warnings), every FK filter uses
  `|stringformat:"d"`, every `{% url %}` resolves.

#### Done well

`generate_scorecard_lines` snapshots the pre-run bands into `previous` **before** writing anything
(`performance.py:601-603`), so "a NEW critical crossing" survives repeated presses — two presses
refresh the figures and raise zero duplicate alerts. Correct shape for an idempotent action with a
side effect.

---

### 2/6 - `explorer` (structural & integration coverage)

#### X5 - Important - **this is the ROOT of R3/R4**: 6.16 has no `_is_admin` helper at all

A grep for `_is_admin` / `is_tenant_admin` / `is_superuser` across
`apps/procurement/views/SupplierPerformanceEvaluation/` returns **nothing**; the same grep over
`templates/procurement/performance/` returns nothing. Twelve-plus sibling view modules define
`_is_admin(request)` - 6.3 `ApprovalWorkflowEngine/*`, 6.12
`GoodsReceiptInspection/{ReceiptBoards:129,ReceiptTolerances:45,ReturnsToVendor:54}`, 6.13
`InvoiceVoucherManagement/{InvoiceDisputes:81,MatchVariances:60,SupplierInvoices:101}` - three of them
carrying the literal docstring *"Mirrors @tenant_admin_required exactly, so a hidden button and a
refused POST agree."*

R3/R4 are the **symptom** (two buttons); this is the **cause** (the sub-module has no notion of admin).
**Fix R3/R4 by adding `_is_admin(request)` once and folding it into `can_generate` / `can_close`** -
patching two templates is not the house-consistent fix.

#### X1 - Important - the three boards are a closed triangle; no entity page links to any of them

The board templates are the only files referencing `supplier_benchmark_board` / `supplier_trend_board` /
`supplier_perception_gap`. Boards link **out** to the entities; `evaluation/detail.html` (which knows
the supplier *and* the period), `kpi/detail.html`, `feedback/list.html` and `improvementplan/detail.html`
link back to **no board**. From a supplier scorecard you cannot reach that supplier's trend; from the
360 register you cannot reach the perception gap those rows feed. Both boards already accept a
`?supplier=` deep link - exactly the link the entity pages should emit.

Diverges from siblings: 6.14's `spend_dashboard` is linked from three templates, 6.15's
`commitment_register` from two. 6.16 is the only recent sub-module whose computed pages are one-way.

#### X2 - Important - the one-way door is invisible from the SCM side

`templates/scm/srm/scorecard/detail.html:20` renders `Manual Override: Yes` and `:62` hides "Recompute
from signals" behind `{% if not obj.manual_override %}` - with **no link to 6.16 and no mention of it**.
`HANDOVER_NOTE` prints three times on the procurement side and zero times on the side that loses the
button. The SCM user sees the effect and not the cause. A one-line "generated by Procurement 6.16 -
view KPI lines" link closes it. (Cross-app edit - flagged as the integration gap, not asking 6.16 to
own `apps/scm`.)

#### X3 - Important - the critical-crossing alert is raised unassigned, and `SupplierKpi.owner` drives nothing

`performance.py:681-691` creates `ProcurementAlert(kind="task", severity="critical", ...)` with **no
`assigned_to` and no `due_at`**. `DashboardPortal/Overview.py:75,108` builds the personal queue as
`open_alerts.filter(assigned_to=me)` - so a `kind="task"` row with a null assignee **never reaches
anyone's task widget**. Every other producer routes it (`Escalations.py:171` uses
`assigned_to=policy.escalate_to`; the seeder's own alert block sets an assignee).

Meanwhile `SupplierKpi.owner` is documented as *"The person answerable for this number"*
(`SupplierKpis.py:194-197`) and is consumed **only** as a filter dropdown and a display field - a grep
for `owner` in `performance.py` returns nothing. The obvious assignee exists on the model and is unused.

#### X10 - Important - the seeder never produces a `draft` or `cancelled` plan

The four `plan_specs` (`seed_procurement.py:2881-2952`) are active / monitoring / closed-successful /
closed-escalated, and **all four set `acknowledge=`**. Consequences against
`SupplierImprovementPlans.py:189-191`:

- `can_activate` is False on all four -> the **Activate button has never rendered**
- `can_acknowledge` is False on all four -> the **Acknowledge button has never rendered**
- `STATUS_CSS["draft"]`/`["cancelled"]`, `OUTCOME_CSS["extended"]`/`["failed"]` have never rendered
- `?status=draft`, `?status=cancelled`, `?outcome=extended`, `?outcome=failed` all return empty pages

**Two of five verbs and four of nine badge states are pages nobody has seen.** One `draft` spec (no
`acknowledge=`), one `cancelled` spec, and moving one closure to `outcome="failed"` covers all of it.

#### Minor - X4, X6-X9, X11-X15

- **X4** `performance.py:688-689` - the alert's security comment cites `ProcurementAlert.clean()`, but
  `objects.create()` never calls `full_clean()` and `TenantOwned` adds no `save()` override. Nothing
  exploitable (hardcoded f-string), but the stated defence is not in force. Pairs with R6.
- **X6** `_supplier_parties` is duplicated four times **with two different signatures** -
  `PerformanceBoards.py:113` takes `tenant`, the other three take `request`. Four copies is house style;
  the split signature inside one sub-module is not, and invites an `AttributeError` on the first copy-paste.
- **X7** `_feedback_stats` omits `expired` while double-counting `requested` (its `overdue` card is a
  strict subset). `_score_stats` and `_evaluation_stats` are exhaustive by comparison.
- **X8** `SupplierFeedback.py:224` - one of nine `write_audit_log` calls omits `tenant=`; harmless
  (resolved downstream) but inconsistent with its eight neighbours.
- **X9** presentation drift: two detail templates link the supplier to `core:party_detail`, two render
  plain text; four empty-state headings end "yet", `kpiscore/list.html:183` does not.
- **X11** **8 of the 14 derived resolvers are never seeded** - `otif`, `ncr_rate`, `rtv_rate`,
  `invoice_accuracy`, `dispute_days`, `promise_adherence`, `backorder_rate`, `po_change_rate`. Their
  output and `breakdown` shape have never rendered on any page.
- **X12** `SupplierImprovementPlan.evidence` (FileField) never seeded (only `evidence_url`), so the
  upload branch has never rendered; `applies_to_tier` only ever `strategic`; `unit` never `ppm`/`money`/
  `ratio`; `review_frequency` never `monthly`/`semiannual`.
- **X13** the entire manual-score path hangs off **one** strategic-tier profile. If `seed_scm`'s tiering
  changes, `made_manual` silently becomes 0 and `supplierkpiscore_edit` / `kpiscore/form.html` /
  `can_edit` become unreachable on seeded data **with no warning printed**. Worth a `self.style.WARNING`
  when `made_manual == 0`.
- **X14** `--flush` deletes the four 6.16 tables but deliberately leaves `scm.SupplierScorecard` - so
  after a flush the `manual_override` flag, the four dimension columns and `overall_score` remain while
  the justifying score lines are gone. `recompute_from_signals()` still skips them and the numbers stand
  on nothing. Either reset those columns for the cards this block opened, or say so in the comment.
- **X15** `ScorecardKpiScores.py:315-319` docstring asserts *"That is safe - junk matches nothing"*,
  which S1 disproved. Must change with the S1 fix or it licenses re-introducing the same filter tuple.

#### Clean - coverage statement (verified programmatically, not by reading)

- **Sidebar: CLEAN.** All five `LIVE_LINKS["6.16"]` keys match the NavERP.md bullets **character-exactly**;
  all five routes reverse; zero bullets unmapped, zero extra leaves.
- **Orphan url names: NONE.** All 33 are `{% url %}`-referenced from at least one template. Resolver walk:
  33/33 register, literals correctly ahead of `<int:pk>`, **zero duplicates across all 412 procurement routes**.
- **Spine reuse: CLEAN.** No second supplier table, no second blocking flag, no second alert mechanism,
  no scorecard create route (links out to `scm:scorecard_create`). `TIER_CHOICES` is a documented local
  mirror with the reason stated.
- **Dead ends: CLEAN** (AST-extracted context keys diffed against every template, both directions). No key
  set-and-unread except the already-filed `quadrant_choices` (R10); no template variable read that its
  view never sets; every model field appears in at least one template;
  `DERIVED_METRIC_CHOICES` and `DERIVED_RESOLVERS` agree **14/14 both ways** - the closed-registry promise holds.
- **Package integration: CLEAN.** All four sub-package and app-level blocks present, all names in `__all__`,
  all four models registered in admin, form `Meta.fields` correctly exclude every stamp.
- **Verified as app-wide convention - do NOT "fix":** the NOT-YET-WIRED import comments (60 files across
  6.13-6.19); the `*Form` suffix family; `stat-icon red` **does** exist (`theme.css:265`, 31 uses); and
  cross-module inbound links are absent for 6.13/6.14/6.15 too, so 6.16 being unlinked from the procurement
  overview is house style - **X1 is about intra-6.16 asymmetry only.**

---

### 3/6 - `frontend-reviewer` (all 17 templates read in full)

**Critical: none.** Three Important, two Minor. The first two are the same bug with opposite bias, and
both were reproduced against the model definitions.

#### F1 - Important - the feedback submit form pre-selects "1 - Poor", the WORST rating

`templates/procurement/performance/feedback/detail.html:143-149`

On the ordinary flow (`requested`, `rating is None`) no `{% if obj.rating == N %}selected{% endif %}`
fires, so the browser selects the first `<option>`. An operator who clicks **Submit response** without
touching the select files that supplier at **rating 1 (Poor)** - and `supplierfeedback_submit` accepts
it as a deliberate choice (`posted` is truthy, `1 in _RATING_VALUES`,
`views/.../SupplierFeedback.py:300-305`). The confirm at line 152 says "with the rating selected above"
**without naming it**, so nothing catches it. That rating then feeds the survey aggregate and the
perception-gap board.

**Fix:** a neutral first option - `<option value="" selected>Choose a rating...</option>` - plus
`required`. Safe: the view already refuses an empty post with `messages.error` + redirect
(`:306-309`), which is exactly what the help text at line 150 promises.

#### F2 - Important - the close form pre-selects "Successful", and closing is irreversible

`templates/procurement/performance/improvementplan/detail.html:210-214`. Verified:

```
OUTCOME_CHOICES = [("successful", "Successful"), ("extended", "Extended"), ...]   # first = default
<option value="{{ val }}">{{ label }}</option>                                    # nothing selected
```

Same shape as F1, opposite bias, and worse: closing is **admin-only**, stamps `verified_by` /
`verified_at`, writes `closure_note` once, and **cannot be edited afterwards** (the page says so at
line 220). It is the ending the supplier is shown. An admin who presses **Close plan** without opening
the select signs the plan *Successful*. The confirm at line 222 again only says "with the outcome
selected above".

**Fix:** `<option value="" selected>Choose how it ended...</option>` first, plus `required`.
`improvementplan_close` already refuses `""` with a message (`SupplierImprovementPlans.py:348-353`).

#### F3 - Important - a zero-response survey line claims it is not a survey line

`templates/procurement/performance/kpiscore/detail.html:132` -
`{% if obj.respondent_count %}` is a **truthiness** test on a `PositiveIntegerField(default=0)`, so `0`
falls through to `{% else %}None - not a survey measurement{% endif %}`.

That path is live: `performance.py:631` runs `update_or_create` for **every** applicable KPI, so a
survey KPI with no submitted responses in the window gets a real line with `source_at_time="survey"`,
`measured_value=None`, `respondent_count=0`. The card then reads "Source at the time: **360 survey**"
at `:125-126` and "Responses aggregated: **not a survey measurement**" seven lines later - two rows of
one card contradicting each other, and the honest fact ("asked, nobody answered") is lost.

**Fix:** branch on the source, not the count -
`{% if obj.source_at_time == "survey" %}{{ obj.respondent_count }}{% else %}...{% endif %}`.

#### Minor

- **F4** badge chains hand-rolled where the model already owns the mapping -
  `evaluation/detail.html:337-346, :401-403, :408-411` and `kpi/detail.html:145-148, :197-206, :262-264,
  :269-272`. All seven chains **agree with the model today**, so drift risk rather than a live defect -
  but the list templates for the same models already use `{{ obj.status_css }}`, and both files' header
  comments claim badges come "from the model's own committed mapping", which is only true of the lists.
- **F5** `benchmark_board.html:107` - the only `.stat-grid` in 6.16 nested inside a `.card` and needing
  an inline `style="padding:0 1rem;"` correction; the five list pages put it at top level with no
  override.

#### Clean - coverage statement

- **Comment leak (L2):** zero `{#` in all 17 files; every note uses `{% comment %}`.
- **L33 / theme classes:** only `badge-green/-red/-amber/-info/-muted/-slate` used; the 5
  `badge-success` hits are inside `{% comment %}` warnings. All `stat-icon` variants used exist. Every
  non-badge modifier resolves against `theme.css` - no invented class names.
- **Model-owned mappings:** `BAND_CSS`, both `STATUS_CSS`, `RATING_CSS`, `KIND_CSS`, `SEVERITY_CSS`,
  `OUTCOME_CSS` and `performance._delta_css()` all emit real theme classes, and `_delta_css`'s
  thresholds match the perception-gap legend **exactly** (>=20 red, >=10 amber, <=-10 info, else green,
  None slate).
- **Badge conditions vs CHOICES:** every literal chain tests a value the model can hold; no dead
  branches; all carry an `{% else %}` fallback.
- **Pagination (L9):** all five lists delegate to the shared partial, which guards `has_previous` /
  `has_next` and replays every GET param except `page` - filters survive paging.
- **Filters:** every list has `name="q"` plus exactly the selects its view declares, each reflecting
  `request.GET`; all pk comparisons use `|stringformat:"d"` and there is **no `|slugify` anywhere** (the
  seven grep hits are comments saying never to use it). `benchmark_board.html:67-69` even re-offers a
  hand-typed out-of-range `?period=` so the picker cannot disagree with the table it filters.
- **URLs:** all 38 distinct `{% url %}` names resolve, including cross-app `scm:scorecard_detail` /
  `scm:scorecard_create` and `procurement:vsu_detail`.
- **Destructive controls:** every delete is a POST form with `{% csrf_token %}`, and every confirm names
  the specific record (`{{ obj.number }}`) and its real consequence - no generic "Are you sure?". Only
  system-assigned numbers reach `confirm()`; no user-authored strings do.
- **Overflow:** all 17 tables sit inside `.table-wrap`, including both branches of the
  `{% if selected_kpi %}` split in `trend_board.html`.
- **Empty states:** copy is accurate - `perception_gap.html:160-164` correctly distinguishes "no
  responses at all" from "none in this window", and `evaluation/list.html:167` does not blame filters
  when the register is genuinely empty.
- **Honest numbers:** every nullable read traced - `composite`, `overall`, `measured_value`, `score`,
  `delta`, `percentile`, `risk_index`, `quadrant`, `grade` all render as an em dash, "Not scored", "No
  data" or "Unplaced", never `0`. **F3 is the single exception.**
- **Accessibility:** matches house level exactly; the bare `q` input with `aria-label` and no
  `<label for>` is the same pattern as `budgetcost/` and `spendanalytics/`, so not filed against 6.16.
  Every icon-only button has `title` **and** `aria-label`; every field uses `for="{{ field.id_for_label }}"`.
- **Not a finding after checking:** the second `.card-header` mid-card after a table is an established
  house pattern (seven sibling templates do it).

#### Praise

The `*_css` model properties are the best thing in this sub-module: by putting the colour mapping on
the model and having templates emit `<span class="badge {{ obj.band_css }}">`, **L33 - the bug that has
shipped three times on this project - is made structurally unable to recur on those rows**, because the
template never names a colour at all. Combined with `evaluation/detail.html:84-93`, where the one-way
handover is stated as a standing warning, again inside the `confirm()` at the moment of the click, and
a third time in past tense once set - and where `can_generate=False` *replaces* the button with
`refusal_reason` rather than greying it out. F4 is only asking that the same idea be finished across
the seven embedded tables.

---

### 4/6 - `performance-reviewer` (measured against live seeded MySQL; scale tests in rolled-back transactions)

**Headline: there is no N+1 anywhere in this sub-module.** All 15 pages measured **flat** across 6x
cohort, 6x period, 9x score-line, 7x feedback, 16x plan and 4x KPI-catalogue growth. The real problems
are missing indexes and unbounded row volume - a different, and in one case worse, failure mode.

| Page | seeded | grown | delta |
|---|---|---|---|
| all five registers | 11-13 | 11-13 | **0** |
| all five details | 9-11 | 9-11 | **0** |
| benchmark board | 12 | 12 (also 12 at **302 suppliers**) | **0** |
| trend board | 12 | 12 (2 -> 12 periods) | **0** |
| perception gap | 11 | 11 (28 -> 208 rows) | **0** |

Compute layer: `benchmark_rows()` **3 queries** at both 5 and 302 suppliers; `trend_series()` **2** at
both 2 and 12 periods; `perception_gap_rows()` **1** at both 28 and 208 rows; the 14 resolvers **21
queries total, 1-2 each, none looping**.

#### P1 - CRITICAL - `SupplierKpiScore` has no index covering its `Meta.ordering`

`ScorecardKpiScores.py:119-128` - `ordering = ["kpi_category", "kpi_name", "id"]`, but the three
declared indexes are `(tenant, scorecard)`, `(tenant, band)`, `(tenant, kpi)`. Nothing covers the sort.

**Measured at 60,041 score lines for one tenant** (200 scorecards x 300 KPIs, rolled back):

```
score register page 1   130 ms -> 1,484 ms   (11x)
page 2000               1,571 ms
?band=ok                1,291 ms
query count             FLAT at 12          <- not an N+1, a missing index
isolated ORDER BY ... LIMIT 15    277 ms  (0.5 ms when index-backed)
EXPLAIN: type=ref rows=28697 Extra=Using where; Using filesort
```

**Fix:** `models.Index(fields=["tenant", "kpi_category", "kpi_name", "id"], name="prc_sks_tnt_cat_name_idx")`.

**This is the app-wide pattern, not a fork:** 12 of the 72 procurement models index their register's
default sort, and they are exactly the ledger-like ones - `SupplierInvoice (tenant, -invoice_date)`,
`InvoiceMatchVariance (tenant, -detected_at)`, `PolicyAttestation`, `FraudAlert`, `MaverickSpendFinding`,
`ComplianceScreening`, `MaterialIssue`, `CostForecast`, `ReplenishmentRun`. `SupplierKpiScore` is the
fastest-growing table in 6.16 (suppliers x periods x catalogue size) and is the one left out.

#### P2 - Important - `SupplierFeedback` has the same missing ordering index

`SupplierFeedback.py:154-161` - `ordering = ["-period_end", "-id"]`, no covering index. **Measured at
50,028 rows:** register 113 ms -> **822 ms**, perception-gap board 91 ms -> **384 ms**, counts flat.
`EXPLAIN`: `Using where; Using filesort`. Fix: `Index(["tenant", "-period_end"])`; a second
`(tenant, supplier, status, period_end)` would also cover `survey_aggregate()`,
`perception_gap_rows()` and `_feedback_windows()`, which all filter that exact tuple.

#### P3 - Important - **duplicate of S2**, with the app's own fix precedent located

Same unordered-`annotate` pagination defect already filed as S2. Adds: `UnorderedObjectListWarning`
fires on *every* request, and **the app already has the documented fix twice** -
`OrderFulfillment/AdvancedShipmentNotice.py:57-62` and `EAuctionManagement/Auctions.py:54-56`, both with
the reasoning spelled out. 6.16 forked from it. Also confirms the annotate's *cost* is fine (119 -> 152
ms at 4,007 scorecards), so S2 is correctness-only. **Do not double-count; fix once.**

#### P4 - Important - chained `scorecard__party` missing on two detail views (L18)

`SupplierFeedback.py:65` and `SupplierImprovementPlans.py:71` stop their `_ROW_RELATIONS` at
`scorecard`, but both detail templates hop `{{ obj.scorecard.party.name }}`. **Measured: 10 queries
when the row has a scorecard vs 9 when it does not**, the extra being a bare `SELECT FROM core_party`.

One query today - but the module's own `_SCORE_RELATIONS = ("kpi", "scorecard", "scorecard__party")`
exists to prevent exactly this, and that tuple is reused by paginated registers, so the day a list
template prints the supplier off the scorecard it becomes 1+N for a 15-row page.

#### P5 - Important - `generate_scorecard_lines` writes row-by-row: 4 round-trips per line

`performance.py:631-649`. **Measured: 54 queries at 9 KPIs -> 195 at 29 KPIs = 7.05 queries per extra
KPI**, of which only 1-2 are the resolver. At 9 KPIs, **39 of the 54 queries are write plumbing** (10
SAVEPOINT + 10 SELECT + 9 UPDATE + 10 RELEASE).

The function already holds the answer: `:601-602` builds `existing = {row.kpi_id: row ...}` before the
loop, so it knows which lines exist. Build objects in the loop, then one `bulk_update()` + one
`bulk_create()` - **4N -> 2**. At 29 KPIs that is 195 -> ~85; in the seeder it removes ~150 of 675.
*Caveat for the fixer:* `bulk_update` does not fire `auto_now`, so `updated_at` must be set explicitly
and listed in `fields`. Same shape at `:680-692` where `ProcurementAlert.objects.create()` is called in
a loop.

#### P6 - Important - `_seed_supplier_performance` is not wrapped in `transaction.atomic()`

`seed_procurement.py:2530`, guard at `:2569`. **Measured: 675 queries, 602 ms per tenant.** The
re-entry guard is `if SupplierKpi.objects.filter(tenant=tenant).exists(): return` - so a crash after
step 1 leaves the tenant holding KPIs and no scorecards, feedback or plans, and **that guard then
preserves the broken state forever**. This is the exact failure `_seed_templates` documents and wraps
against at `seed_procurement.py:408`. Fix: `with transaction.atomic():` around steps 1-6.

#### P7 - Important - the scorecard `<select>` pickers are uncapped and pull whole rows

`ScorecardKpiScores.py:333-335`, `SupplierFeedback.py:114-118`, plus both create/edit forms.
**Measured with 2,007 scorecards:** score register 107 -> **349 ms**, HTML **425 KB -> 623 KB** (+197 KB
of `<option>` in one `<select>`); feedback register the same. Counts flat - pure row volume.

The module already has the convention everywhere else (`ROW_CAP=500`, `PERIOD_CAP=24`,
`_CATEGORY_CAP=200`). Fix: slice `[:ROW_CAP]` and `.only("id","number","period_end","party__name")` -
the dropdown prints four values and currently fetches all 18 scorecard columns plus the whole party row.

#### P8 - Important - `supplierevaluation_detail` caps `lines` but not `plans` / `feedback_rows`

`ScorecardKpiScores.py:236-241`. `lines` is correctly `[:ROW_CAP + 1]` with a `truncated` flag, and the
sibling `supplierkpi_detail` caps all three of its lists. **Measured with 1,500 feedback rows and 500
plans on one scorecard: 109 ms -> 924 ms, HTML 427 KB -> 2.28 MB**, counts flat. A supplier with a real
360 programme reaches that without anything unusual happening.

#### Minor - P9-P14

- **P9** `benchmark_rows()` streams every risk assessment to keep one per party (reviewer 1's referral,
  quantified): **2,402 rows pulled to keep 302** - an 8x over-fetch, one query, so memory not N+1. Fix
  with a `Subquery(...values("risk_index")[:1])` annotation, which folds it into an existing query.
- **P10 - PB1 quantified:** 2 of the 9 queries on `supplierkpiscore_detail` are the same row, fetched
  once through `_score_qs` (3 joins) and again by `crud_detail` (4 joins). Both sibling detail views
  already use the cheap-probe idiom; this one needs only `.only("pk","tenant_id","source_at_time","breakdown")`.
- **P11 - PB5 quantified:** demonstrated with `ROW_CAP` monkeypatched to 10 - `?tier=strategic` returned
  **1 row with `truncated=True` and `cohort.count=1`**. The damage is not query count: `cohort.average`,
  `best`, `worst` and every rank/percentile are computed over the **post-cap survivors**, so a filtered
  board reports statistics for a cohort that is not the cohort.
- **P12** `.only("id","code","name")` on the two KPI pickers - they currently pull `description` and
  `notes` (both `TextField`) for every `<option>`.
- **P13** `SupplierImprovementPlan` ordering index missing (`EXPLAIN`: `type=ALL key=None ... filesort`),
  but the table is low-volume by nature. `SupplierKpi` has the same gap on a 10-100-row catalogue -
  deliberately not worth an index.
- **P14** seeder step 5 does per-row `.save()` where `bulk_update` would be one call (5 rows today).

#### M7 - cross-app NOTE, explicitly NOT a 6.16 fix

`scm.SupplierScorecard` has no `(tenant, period_end)` index, and 6.16 is what turns `period_end` into a
hot filter. Measured cost is currently small (1.9 ms). **Do not fork an index onto SCM's model from
6.16** - this is a note for whoever owns SCM 4.x.

#### Measured and found acceptable - coverage statement

- **No N+1 anywhere**, across every growth axis tested.
- `kpiscore/list.html` renders `{{ obj.scorecard.party.name }}` and `_SCORE_RELATIONS` **correctly chains
  `scorecard__party`** - the highest-volume register does not fire per-row `Party` queries.
- `SupplierKpiScore.__str__` reads the **frozen** `kpi_name`, never `self.kpi.name` - the L18 trap is
  deliberately closed on the model that would suffer most.
- **Every `stats` dict is ONE conditional `aggregate()`.** `_evaluation_stats` correctly carries
  `distinct=True` on every count (dropping it on any one would silently report "number of score lines"),
  and `_plan_stats` computes `overdue` through `Coalesce` in SQL so the stat card and the row badge
  cannot disagree.
- No `len(qs)` where `count()` belongs, no `if qs:` where `exists()` belongs. The `fetch cap+1 then
  len()` idiom is correct - it answers "was it truncated?" from the same query.
- All 17 templates grepped for `.all` / `.count` / `.exists` / `.first` inside `{% for %}` - **zero**
  related-manager calls.
- **`SupplierFeedback.score_value()` called twice (reviewer 1's referral) is NOT a performance finding** -
  it is a pure dict lookup with no DB access. Leave it alone.

#### Suggested query-count tests (hand to the test-writer)

Seven `django_assert_max_num_queries` tests that lock in **flatness** rather than the fix - notably
`test_616_feedback_detail_joins_the_scorecard_party` and `..._plan_detail_...` (a row *with* a scorecard
must cost the same as one without; **fails until P4 is fixed**, which is the point) and
`test_616_evaluation_register_queryset_is_ordered` (fails until S2/P3 is fixed).

---

*(remaining reviewers append below: qa-smoke-tester → security-reviewer)*
