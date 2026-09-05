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

## THE FIX LIST - deduped, sorted, IDs assigned (all six reviewers in)

**This is what the `code-fixer` works from.** Every item below is a distinct defect; the per-reviewer
sections beneath carry the evidence. Fix in ID order: C -> H -> I -> M. Mark each `[x] fixed` or
`[~] skipped - reason`.

### REFUTED - do NOT "fix" these. Touching them breaks working code.

- **X10** (never-rendered plan verbs) - **REFUTED as a code defect.** A draft and an un-acknowledged
  plan were created and both verbs driven end to end; all four "never rendered" badge states resolve to
  real theme classes. It is a **seeder-coverage note only** (folded into I13).
- **X11** (8 unexercised derived resolvers) - **REFUTED outright.** All eight were created, generated
  and rendered: zero raises, zero nonsense units, zero raw dicts. Unexercised, not broken.
- **R8 on seven of eight plan verbs** - not a security finding (racing buys nothing; `acknowledge` can
  only write a later timestamp). Only **generate** is worth locking - see C4.
- **R3/R4 are NOT an authorization bypass** - the server-side gate holds and the 403 leaks nothing.
  They are a UX-of-authorization item, fixed via I2's single helper.
- **`SupplierFeedback.score_value()` called twice** in a template - a pure dict lookup, no DB. Leave it.
- **`stat-icon red`, the NOT-YET-WIRED import comments, and the `*Form` suffix family** are app-wide
  convention, not drift.

### CRITICAL

- [x] **C1 - `?year=0` (and `>=10000`) is an uncaught 500.** `views/.../ScorecardKpiScores.py:153`.
  `crud.py`'s zero-skip is gated on `_is_pk_lookup()`, false for `period_end__year`; `as_db_int`
  range-checks against `MAX_DB_INT`, not 1-9999. Reproduced. **`DEBUG` defaults to `True`
  (`settings.py:16`)**, so a deployment without a `.env` renders a full technical 500 from a typed URL.
  Clamp `year` to 1-9999 in the view; the general guard belongs in `apps/core/crud.py`. *(N1, SEC-confirmed)*
  - **Status:** [x] fixed - 6ef3f76a `fix(procurement): C1 - clamp the 6.16 evaluation register year filter to 1-9999`. Re-verified this run: ?year=0 / =10000 / =99999 all 200, ?year=2025 still filters.
- [x] **C2 - Generate on an empty KPI library sets `manual_override` and destroys a derivable score.**
  `performance.py:674`. A scorecard that would grade **A / 93.70** becomes permanently unscoreable by
  either engine, and the operator sees a **green success message**. Two reachable paths need no empty
  library: a supplier with no `scm.SupplierProfile` while KPIs are tier-scoped, and a library mid-retune.
  Guard on `if written:` or return the refusal shape when `kpis` is empty. *(R2, upgraded by reviewer 5)*
  - **Status:** [x] fixed - 8297484c `fix(procurement): C2 - generate refuses an empty run instead of setting manual_override`. Re-verified on BOTH reachable paths (every KPI deactivated; tier-scoped KPIs plus a supplier with no scm.SupplierProfile): refused, 0 lines written, manual_override stays False; the control run still writes 8.
- [x] **C3 - `SupplierKpiScore` has no index covering its `Meta.ordering`.** `ScorecardKpiScores.py:119-128`.
  Measured: **130 ms -> 1,484 ms at 60,041 rows**, query count flat - a filesort over the tenant
  partition. Add `Index(["tenant","kpi_category","kpi_name","id"], name="prc_sks_tnt_cat_name_idx")`.
  **Needs a migration** - coordinate the number with the peer sessions. *(P1)*
  - **Status:** [x] fixed - c468781e `perf(procurement): C3 - index SupplierKpiScore on its Meta.ordering`. MIGRATION STILL PENDING - see Notes.
- [x] **C4 - over-long `rating` POST is an uncaught 500.** `views/.../SupplierFeedback.py:302` -
  `isdecimal()` passes on 5,000 digits, then `int()` raises. Reproduced. The only unguarded `int()` on
  request input in the repo. Use `as_db_int`. *(SEC1)*
  - **Status:** [x] fixed - 931bf0d2 `security(procurement): C4 - guard the feedback rating POST with as_db_int`. Re-verified: a 5,000-digit rating returns 302 with 'That is not one of the ratings on the 1-5 scale.' and no mutation; rating=4 still submits.

### IMPORTANT

- [x] **I1 - the two boards publish DIFFERENT composites under the same key.** `performance.py:725` vs
  `:839`. **All five suppliers differ**; Bidder Two BV reads 34.62 (grade F) on one board and 69.87 on
  the other, and rank/percentile/quadrant all ride the wrong figure. *(R1)*
  - **Status:** [x] fixed - aac75bf1 `fix(procurement): I1 - rank the benchmark board on the KPI-line composite, not overall_score`. Option A of the two the finding offered (compute the cohort composite from its lines, aggregated in SQL via _composite_from_sums) rather than renaming the key: renaming would have left two different numbers shipping under two names, and the trend row already carried both. Re-verified: all five suppliers now agree across the boards - Bidder Two BV reads 69.87 on both, with SCM's 34.62 carried beside it as `overall`.
- [x] **I2 - add `_is_admin(request)` once and fold it into `can_generate` and `can_close`.** 6.16 has
  no notion of admin anywhere; twelve sibling modules define this helper. Fixes R3+R4 at the root, and
  extend `refusal_reason` so the page still says *why*. *(X5, R3, R4, SEC7)*
  - **Status:** [x] fixed - 952cecaf + e54bcbfa + c3231816 + db83bd59. Re-verified against the real non-admin ops_acme: neither the Generate form nor the Close form renders, and the refusal names the ROLE ('...is a workspace-admin action - ask an admin of this workspace') rather than claiming the period is closed.
- [x] **I3 - score lines are deletable off a PUBLISHED scorecard by any member** while writing them is
  admin-only and draft-only. Gate the delete on `scorecard.status == "draft"` and hide the bin icon.
  *(SEC2)*
  - **Status:** [x] fixed - 80bcf6be + c21315ff + f132d7ce + 9119ad28. Re-verified: POSTing a delete for a score line on a published scorecard leaves the row in place and returns the reason; the register hides the bin icon for that line.
- [x] **I4 - closed+signed plans and submitted responses stay editable/deletable by any member.**
  Gate `improvementplan_edit`/`_delete` on `OPEN_STATUSES` (already defined) and
  `supplierfeedback_edit` on `status == "requested"`, per `Milestones.py:102,139`. *(SEC3)*
  - **Status:** [x] fixed - bc2428d8 / d1a82552 / 96e1b05e / 24a19b45 / 7f840fc6 / 2f0dc37e (6 commits, previous run).
- [x] **I5 - `evidence` served as a raw unauthenticated `MEDIA_URL` link.** Route through an
  authenticated view per `Revisions.py:226`. **Do NOT sweep the five sibling clones** - carry that up
  as an app-wide item. *(SEC4)*
  - **Status:** [x] fixed - be6d00af / 77f8bfb1 / 7413bc2c / 023147b0 (4 commits, previous run).
- [x] **I6 - both `<select>`s submit their first option.** Feedback submit files **rating 1 "Poor"**;
  plan close files **"Successful"** irreversibly, stamping `verified_by`. Add a neutral
  `<option value="" selected>` + `required` to each; both views already refuse blank. *(F1, F2)*
  - **Status:** [x] fixed - 4bff3981 (rating select) + bf014074 (outcome select), previous run.
- [x] **I7 - benchmark cohort statistics are computed POST-cap.** Filter tier/category in the queryset
  **before** the slice. Measured: a 13-supplier cohort averaging 55.14 (best 95.00) displayed as
  6 suppliers averaging 10.00 with a best of 10.00. *(PB5, P11)*
  - **Status:** [x] fixed - 7db61277 `fix(procurement): I7 - apply the benchmark tier/category filter before the row cap`.
- [x] **I8 - `supplierevaluation_list` paginates an unordered queryset.** `annotate()`'s GROUP BY drops
  `Meta.ordering`; `UnorderedObjectListWarning` on every request. Append
  `.order_by("-period_end","-id")`. The app documents this fix twice already. *(S2, P3 - one fix)*
  - **Status:** [x] fixed - 6af9687f `fix(procurement): I8 - order the evaluation register explicitly after the annotate`.
- [x] **I9 - `generate_scorecard_lines` writes row-by-row: 4 round-trips per line** (54 q at 9 KPIs ->
  195 at 29; 39 of the first 54 are write plumbing). It already builds an `existing` dict before the
  loop - use `bulk_update` + `bulk_create`. **`bulk_update` does not fire `auto_now`**, so set
  `updated_at` explicitly. Same shape for the alert `create()` in a loop. *(P5)*
  - **Status:** [x] fixed - 0c5c404d `perf(procurement): I9 - bulk_update + bulk_create the generate run instead of 4 round-trips per line`. Measured 54 -> 21 queries on the first press and 20 on a re-press; line values byte-identical, pks stable across three presses, zero duplicate alerts. updated_at is stamped by hand and listed in the new _LINE_FIELDS because bulk_update does not fire auto_now.
- [x] **I10 - the seeder is not atomic and its guard preserves a crash.** Wrap `_seed_supplier_performance`
  steps 1-6 in `transaction.atomic()`. *(P6)*
  - **Status:** [x] fixed - 8b9a2f65 `fix(procurement): I10 - wrap the 6.16 seeder steps 1-6 in one transaction`. Exercised end to end against a rolled-back copy of acme; the summary line stays outside the atomic so it reports what actually committed.
- [x] **I11 - `supplierevaluation_detail` caps `lines` but not `plans`/`feedback_rows`** - 109 ms ->
  924 ms, 427 KB -> 2.28 MB HTML. Cap both and OR into `truncated`. *(P8)*
  - **Status:** [x] fixed - db68279c (view) + 16793a13 (template). Deviates from the finding on one point: the cut is published as a separate related_truncated / related_cap pair instead of being OR-ed into `truncated`, because the existing truncated message says the composite was computed over a cut list - which is false when only the plans table was cut. Two flags, two honest sentences.
- [x] **I12 - the seeder window sits one day before SCM's, with THREE symptoms:** the default board
  lands on SCM's period showing a perfect cohort with **no 6.16 evidence**; both goods receipts fall
  outside the window so **16 of 30 derived lines are unmeasured** (Delivery and Quality read "No data"
  on every seeded scorecard); and both risk assessments fall outside it, so the quadrant column has
  **never held a value** on the correct period. Move the window to match SCM's. *(R7, N3)*
  - **Status:** [x] fixed - 070182ef `fix(procurement): I12 - close the 6.16 seed window one day AFTER SCM's, not one day before`. All three symptoms measured fixed on a rolled-back re-seed: default board 2 rows with line_count 0 -> 5 rows with 9,8,8,8,8; unmeasured lines 16 -> 14 (On-time delivery and Defect rate each 5 -> 4); quadrants 0 of 5 placed -> 2 of 5. The anchor now also excludes the block's own cards, so a re-seed after --flush re-finds the period instead of walking a day further out each time. The second goods receipt stays outside the window because seed_inventory ran 14 days after seed_scm in this dev DB; on a workspace seeded in one pass both land on the run date.
- [x] **I13 - seeder coverage gaps** (one edit, several holes): no `draft` or `cancelled` plan, all four
  always acknowledged, `evidence` FileField never populated, `applies_to_tier` only ever `strategic`,
  and the whole manual-score path hangs off **one** strategic profile with no warning if it becomes 0.
  *(X10 downgraded, X12, X13)*
  - **Status:** [x] fixed - ecf4e42c `fix(procurement): I13 - seed the plan states, the evidence upload and the manual-path warning`. 4 -> 8 plans; all five statuses and all four outcomes now have a row; 7 of 8 acknowledged so Activate and Acknowledge finally render; one plan carries a real evidence file (written behind was_created so a re-run leaves no storage-renamed duplicate); made_manual == 0 now prints a WARNING naming the KPI and the tier. acknowledged_by is now written only with acknowledged_at. One sub-item deliberately left - see Notes.
- [x] **I14 - `?source=` and `?category=` pass unvalidated into a filter and silently empty the page.**
  Validate both in their views. *(S1, R5)*
  - **Status:** [x] fixed - 125c6d2d (?source= on the score register, which closes M19 with it) + f9e617bf (?category= on the benchmark board). Both junk values now fall back to the full list exactly as ?band= and ?tier= already did, and both real values still narrow (source: 15/10/1 rows; category: 5 -> 2, with tier 5 -> 1).
- [x] **I15 - two `_ROW_RELATIONS` miss `scorecard__party`** while both detail templates hop it.
  Measured +1 query each; becomes 1+N the day a list template prints it. *(P4)*
  - **Status:** [x] fixed - f1e66f3b (360 responses) + e3ac0085 (improvement plans). Measured 10 -> 9 queries on each detail page, bare core_party selects 1 -> 0, and a row without a scorecard now costs the same as one with.
- [~] **I16 - `manual_override` is invisible from the SCM side.** The scm scorecard page shows the
  effect and hides the cause. **Cross-app edit - confirm before touching `apps/scm`.** *(X2)*
  - **Status:** [~] skipped - cross-app edit on apps/scm, explicitly out of bounds for this session. The scm scorecard page does show manual_override and hide 'Recompute from signals' with no mention of 6.16, so the integration gap is real - but apps/scm and its templates belong to a live peer session and the ownership call is the user's. Carried up as a cross-app item.
- [x] **I17 - the critical-crossing alert is raised unassigned**, and the dashboard's personal queue
  filters on `assigned_to` - so it reaches nobody. `SupplierKpi.owner` is the obvious assignee and is
  never read. *(X3)*
  - **Status:** [x] fixed - 5ebb6794 `fix(procurement): I17 - assign the critical-crossing alert to the KPI's owner`. Verified on a rolled-back generate run: both alerts come out assigned_to=admin_acme and land in that user's personal open-alert queue, where all four seeded ones previously reached nobody. A KPI with no owner still raises the alert unassigned - that is the team queue.
- [x] **I18 - a zero-response survey line contradicts itself** - branch on `source_at_time`, not on
  `respondent_count`'s truthiness. *(F3)*
  - **Status:** [x] fixed - 25ee8f58 `fix(procurement): I18 - branch the responses row on the source, not on the count being truthy`. Verified on all four shapes; a zero-response survey line now reads '0 / asked, and nobody answered inside the period window' instead of contradicting the Source row six lines above.
- [x] **I19 - no entity page links to any board**, though both boards accept `?supplier=`. *(X1)*
  - **Status:** [x] fixed - 25d8e92b (evaluation detail: trend + benchmark + perception gap) / b10bcc2d (plan detail: supplier trend) / b32ab899 (360 register: perception gap) / 4290b4aa (KPI detail: trend pre-filtered to that KPI). Every href was fetched, not just rendered: all 200 and all land pre-filtered - naming the supplier or pre-selecting the KPI rather than showing the picker prompt.
- [x] **I20 - `SupplierFeedback` missing ordering index** - 113 ms -> 822 ms at 50,028 rows. Same
  migration as C3. *(P2)*
  - **Status:** [x] fixed - 10fbffd4 `perf(procurement): I20 - index SupplierFeedback on its Meta.ordering`. MIGRATION NOT GENERATED - see Notes. The second index P2 suggested, (tenant, supplier, status, period_end), was deliberately not added: one covering index per table matches the twelve sibling ledger-like models, and a second write-cost index wants its own measurement.
- [x] **I21 - uncapped scorecard/KPI `<select>` pickers pulling whole rows** - +197 KB of `<option>` in
  one select at 2,007 scorecards. Slice and `.only(...)`. *(P7, P12)*
  - **Status:** [x] fixed - d0460b36 (score register) + 7ba2d199 (360 register). NOT applied to the create/edit forms P7 also named, and that is deliberate: slicing a ModelChoiceField.queryset breaks to_python()'s .get() ('Cannot filter a query once a slice has been taken'), and that .get() IS the _reject_foreign tenant boundary; .only() there would push label_from_instance's str(obj) into a deferred load per option. The form pickers want a limited widget, not this fix.

### MINOR

- [ ] **M1** `supplierkpiscore_detail` double-fetches the joined row (2 of 9 queries). *(PB1, P10)*
- [ ] **M2** normalise the confirm idiom to `onclick` in Entity 1's two KPI templates. *(PB2)*
- [ ] **M3** `SupplierFeedback.__str__` renders literal `"None"` on an unsaved instance. *(PB3)*
- [ ] **M4** five templates print the English word "None" where siblings use an em dash. *(S3)*
- [ ] **M5** `breakdown['window']` renders as a **Python list literal** under a column headed *Value*.
  Join as `"2026-05-11 to 2026-08-09"` in the flattener. *(N2)*
- [ ] **M6** the alert's `link_url` is hand-built rather than `reverse()`d. *(R6, X4)*
- [ ] **M7** `row_cap` carries two different caps across boards/details (three instances). *(PB6, R9)*
- [ ] **M8** `quadrant_choices` passed but never iterated; labels hard-coded twice. *(R10)*
- [ ] **M9** `_supplier_parties` duplicated four times with **two different signatures**. *(X6)*
- [ ] **M10** `_feedback_stats` omits `expired` while double-counting `requested`. *(X7)*
- [ ] **M11** one of nine `write_audit_log` calls omits `tenant=` (harmless, inconsistent). *(X8)*
- [ ] **M12** supplier linked to `core:party_detail` on two detail pages, plain text on two; empty-state
  heading wording drift. *(X9)*
- [ ] **M13** breakdown key `rows` means the denominator for `otd` and the numerator for three others.
  *(N4)*
- [ ] **M14** unbounded `closure_note` from POST -> `DataError` or silent truncation. Cap at 4000.
  *(SEC5)*
- [ ] **M15** generate's draft check reads a row fetched outside the transaction; use
  `select_for_update()`. *(SEC6, R8-generate-only)*
- [ ] **M16** `SupplierImprovementPlan` ordering index missing (low-volume table). *(P13)*
- [ ] **M17** seeder step 5 does per-row `.save()` where `bulk_update` fits (5 rows). *(P14)*
- [ ] **M18** `benchmark_rows` streams 2,402 risk rows to keep 302; fold into a `Subquery`. *(M1/P9)*
- [ ] **M19** the `?source=` docstring still asserts the safety S1 disproved. Must change with I14.
  *(X15)*
- [ ] **M20** `--flush` leaves scm scorecards flagged `manual_override` with their justifying lines
  gone. *(X14)*
- [ ] **M21** one `.stat-grid` nested in a `.card` needing an inline padding override. *(F5)*
- [ ] **M22** seven badge chains hand-rolled where the model already exposes `*_css` (all agree today).
  *(F4)*

### CONTRACT DEFECTS - amend `.claude/tasks/contract-procurement-6.16.md`, not the code

- [ ] **CD1** §3.1 specifies `supplierkpi_delete` with no `ProtectedError` guard, which would 500 on any
  KPI with measured history. The code's guard is correct; **the contract is wrong.** *(PB4)*
- [ ] **CD2** §6 describes `skipped` as "applicable KPIs that produced no line", but every applicable
  KPI gets a line. Code and message agree; the contract does not. *(R11)*

### NOTES - out of scope for this fixer

- **`scm.SupplierScorecard` has no `(tenant, period_end)` index** and 6.16 makes that a hot filter.
  **Do not fork an index onto SCM's model from 6.16.** *(M7/perf)*
- **The `.file.url` / `.evidence.url` family** - five more unauthenticated media links in procurement.
  App-wide item. *(SEC4)*
- **Dev-DB hygiene:** a third tenant `id=70, slug='', name='SMOKETEST Acme'` is a peer's un-rolled-back
  throwaway. An **empty slug** risks tenant-resolution edge cases. Tell the other sessions; do not
  delete another session's rows. *(N5)*

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

### 5/6 - `qa-smoke-tester` (empirical confirmation pass - NOT a repeat sweep)

The first smoke gate could only test what seeded data reaches. This pass **built the missing states**
(all writes in rolled-back transactions) to confirm or refute what reviewers 1-4 predicted. **Two
refutations, one severity upgrade, one new Critical.**

| # | Finding | Verdict | Severity change |
|---|---|---|---|
| R2 | `manual_override` on an empty run | **CONFIRMED** | **-> CRITICAL** |
| F1/F2 | selects default to first option | **CONFIRMED** | as filed |
| X10 | never-rendered verbs/badges | **REFUTED as a code defect** | **-> Minor (seed note)** |
| F3 | zero-response survey line | **CONFIRMED** | as filed |
| X11 | 8 unexercised resolvers | **REFUTED - all 8 clean** | **-> note only** |
| PB5/P11 | post-cap cohort statistics | **CONFIRMED** | **-> Important+** |
| S1 | junk filter empties register | **CONFIRMED + 1 NEW 500** | new = Critical |
| P4 | missing `scorecard__party` | **CONFIRMED** | as filed |

#### N1 - NEW - CRITICAL - `supplierevaluation_list?year=0` is an uncaught 500

Reproduced independently by the main session:

```
?year=0      -> 500        ?year=2026   -> 200
?year=10000  -> 500        ?year=9999   -> 200
?year=99999  -> 500        ?year=abc    -> 200
ValueError: year 0 is out of range
  django/db/backends/base/operations.py:615  first = datetime.date(value, 1, 1)
```

Reachable range: `0` and `[10000, MAX_DB_INT]`. **Mechanism:** `crud.py`'s zero-skip is gated on
`_is_pk_lookup()`, which returns `False` for `period_end__year` - and its own comment states the
assumption that is false here (*"`year` ... 0 is a perfectly good value"*). `as_db_int` range-checks
against `MAX_DB_INT`, not the date-year range 1-9999. `ScorecardKpiScores.py:153` is the **only
`__year` int filter in the app**, so 6.16 is the first place the shape appears - and the view's
docstring claiming a hand-edited query string "cannot 500 the page (L11)" is provably false.

**Fix:** clamp `year` to 1-9999 in the view before it reaches `filters=`; the general guard belongs in
`apps/core/crud.py`.

#### R2 - CONFIRMED, and understated. Raise to CRITICAL.

Control vs victim, same supplier, same window:

```
CONTROL (never generated) -> recompute_from_signals fills it:
        d=100.00 q=100.00 p=100.00 r=58.00  overall=93.70  grade='A'
VICTIM  (Generate pressed, 0 KPIs) -> lines=0, manual_override=True
        recompute_from_signals: all None, overall=None, grade=''
```

**A scorecard that would have graded A / 93.70 is now permanently unscoreable by either engine** - and
the operator is told it worked, in a green success message: *"Generated 0 KPI line(s) ... This
scorecard is now owned by Procurement."* On the SCM side the "Recompute from signals" button is gone.

**Two reachable paths needing no empty library at all**, both measured: a brand-new supplier with no
`scm.SupplierProfile` while KPIs are tier-scoped (`applicable_kpis() == []`), and a library mid-retune
with every KPI deactivated. Recovery exists (untick `manual_override` on the SCM form) but **nothing
anywhere tells the user recovery is needed.**

#### F1 / F2 - CONFIRMED, with the distinction cleanly established

Parsed the real rendered HTML and applied the UA rule (no `selected` => first non-disabled option):

```
F1  select has NO `required`, all five options selected=False
    browser submits rating='1' -> STORED rating=1 (Poor), score_value()=Decimal('0')
    CONTROL (no rating field at all) -> view refuses, stays 'requested'
F2  select has NO `required`, all four selected=False
    browser submits outcome='successful' -> STORED closed/successful, verified_by stamped
    CONTROL (no outcome field) -> view refuses, stays 'monitoring'
```

So it is unambiguously **"the form submits the first option"**, not "the view rejects empty". The
view's blank-refusal is real but sits on a path a browser never takes.

#### PB5 / P11 - CONFIRMED and worse than filed

`ROW_CAP` monkeypatched to 8, 12 extra scorecards (6 named `AAA...` scoring 10, 6 named `ZZZ...`
scoring 95; `benchmark_rows` slices by `party__name`):

```
              TRUTH     SHOWN
count         13        6        WRONG
average       55.14     10.00    WRONG
best          95.00     10.00    WRONG
```

A user filtering to `?tier=strategic` sees a 6-supplier cohort averaging 10.00 whose **best** scores
10.00; the truth is 13 suppliers averaging 55.14 with a best of 95.00. All six top performers are
absent. Second shape: with `ROW_CAP=2` on seeded data, `?tier=strategic` returns **`rows=0, count=0,
truncated=True`** - a strategic supplier exists and the board says the cohort is empty.

#### REFUTED - do NOT let the fixer touch these

- **X11 REFUTED.** All 8 never-seeded resolvers were created, generated and rendered: **zero raises,
  zero nonsense units, zero raw dicts, zero leak markers**; six correctly report "No data in the
  period", two return a real `0.00` with a sensible breakdown. Reviewer 2 was right they were
  unexercised and wrong to imply risk.
- **X10 REFUTED as a code defect.** A `draft` and an un-acknowledged plan were created and both verbs
  driven end to end - Activate and Acknowledge render and work, re-acknowledge is correctly refused,
  and all four "never rendered" badge states resolve to real theme classes. It is a **seeder-coverage
  note**, not an Important finding.

#### More new findings

- **N2 - Important-ish:** `breakdown['window']` renders as a **Python list literal** on 40 of 41 seeded
  lines - under a column headed *Value* the user reads `['2026-05-11', '2026-08-09']`. The template
  promises values are `str()`-ified so nothing prints as a repr; it prints as text, but that text *is*
  a repr. One-line fix in the flattener: join lists as `"2026-05-11 to 2026-08-09"`.
- **N3 - R7 has THREE symptoms, not one; re-grade R7 Important.** The 6.16 window is one day before
  SCM's, which means: (1) *(filed)* the default board lands on SCM's period - 2 rows, both
  `line_count=0`, a perfect-looking cohort avg 86.03 **with no 6.16 evidence behind it**; (2) *(new)*
  both `GoodsReceiptNote`s fall outside the 6.16 window, so `otd` and `defect_rate` are unmeasured for
  **all five suppliers - 16 of 30 seeded derived lines**, i.e. the flagship Delivery and Quality KPIs
  read "No data" on every seeded scorecard; (3) *(new)* both `SupplierRiskAssessment` rows are dated
  outside it too, so the quadrant column renders **"Unplaced" six times** and the risk axis has never
  held a value on the correct period. Moving the window to match SCM's fixes all three.
- **N4 - Minor:** the breakdown key `rows` means the **denominator** for `otd` but the **numerator** for
  `ncr_rate` / `po_change_rate` / `backorder_rate` (e.g. `rows: 0` printed beside `po_lines: 3`) - same
  key, opposite meaning, on an audit trail whose job is being arguable.
- **N5 - dev-DB hygiene, NOT a 6.16 defect:** a third tenant sits in the shared MySQL - `id=70,
  **slug=''**, name='SMOKETEST Acme'` - a peer session's throwaway that was never rolled back. An empty
  slug means tenant-resolution edge cases. Left untouched; worth telling the other sessions.

#### Filter audit - every param on every page

Exactly **two** silent-empty holes and **one** 500:
- `supplierkpiscore_list?source=` **UNGUARDED** (S1 confirmed; `?source=0` also empties it)
- `supplier_benchmark_board?category=` **UNGUARDED** (R5 confirmed)
- `supplierevaluation_list?year=` **500** (N1)

Everything else guarded: all of `supplierkpi_list`'s five, `supplierfeedback_list`'s six,
`improvementplan_list`'s six, the boards' `period`/`tier`/`supplier`/`kpi`. **Explicitly not holes:**
`?is_active=0` filters correctly to inactive; the two boards render a "Pick a supplier" prompt rather
than a wiped register. `page` junk on all five registers is 200 - L9 clean.

#### Empirical confirmation of filed-but-unexercised findings

- **R1 is worse than filed - ALL FIVE suppliers differ**, not one: Northwind 86.88 vs 89.17, Cascade
  80.63 vs 81.37, Bidder One 75.00 vs 79.17, AeroParcel 40.38 vs 38.46, **Bidder Two 34.62 (grade F)
  vs 69.87**.
- **R3/R4** confirmed against the real non-admin `ops_acme`: both forms render, then `POST` gives a
  bare **unthemed Django 403 page**, with no mutation.
- **X3** confirmed: 4 of 4 critical task alerts have `assigned_to=None` and `due_at=None`.

#### What was touched

Every write went through `transaction.atomic()` + forced rollback. Post-run snapshot identical to
opening: `kpi=9 score=41 fb=28 plan=4 card=7`, plan/feedback status distributions unchanged,
5 `manual_override` scorecards, 4 critical alerts, zero residue, `ROW_CAP` restored to 500. No
`makemigrations`, no `--flush`, no code edit, no git. All 18 throwaway scripts deleted.

---

### 6/6 - `security-reviewer`

**Verdict: one High, three Medium, three Low. No cross-tenant leak, no authorization bypass, no
injection.** The High and two Mediums are new; the rest sharpen or refute earlier passes.

#### SEC1 - HIGH - `supplierfeedback_submit`: an over-long `rating` is an uncaught 500 (NEW)

`views/.../SupplierFeedback.py:302`. Reproduced independently by the main session:

```python
if not posted.isdecimal() or int(posted) not in _RATING_VALUES:   # <- int() on the right of `or`
```
```
isdecimal('1'*5000) -> True        # so the short-circuit FALLS THROUGH to int()
int('1'*5000)       -> ValueError: Exceeds the limit (4300) for integer string conversion
```

Any authenticated tenant member with one open response's pk can 500 the page at will. **This is the
only unguarded `int()` on request input in the whole repo** - every sibling wraps it (crm Surveys,
accounting CashForecast, hrm Celebrations/Budget), and `apps/core/crud.py:53-56` documents this exact
trap by name, which is why the GET filters here are safe and this POST verb is not. The smoke gate's
junk-param sweep is GET-only by construction and could not have found it.

**Fix:** use `as_db_int(posted)`, which length-checks before `int()`.

#### SEC2 - MEDIUM - score lines can be deleted off a PUBLISHED scorecard by any member (NEW)

`views/.../ScorecardKpiScores.py:391-408`. Writing a score line requires `@tenant_admin_required` **and**
a draft scorecard; **deleting one requires only `@login_required`**. So any ordinary member can POST away
the measured evidence behind a published or archived scorecard, from the register's own bin icon
(offered unconditionally). The four scm dimension columns and `overall_score` are left standing, so the
published grade survives with nothing behind it - the view's own docstring concedes it, and
`generate_scorecard_lines` refuses to touch a published card precisely because "a closed period is
closed". **The delete route is the hole in that invariant.**

#### SEC3 - MEDIUM - closed+signed plans and submitted responses stay editable by any member (NEW)

`SupplierImprovementPlans.py:214-233, 396-410`; `SupplierFeedback.py:245-260`. Neither edit nor delete
carries a status gate. After an admin closes a plan - stamping `verified_by`/`verified_at` and the
outcome the supplier is shown - **any member can rewrite `finding`, `root_cause`,
`corrective_actions`, the dates and the supplier, leaving the signature beside altered content**, or
delete the closed plan outright. Same on feedback: `rating` is in `Meta.fields`, so a **submitted**
response's rating can be overwritten through the ordinary edit form, bypassing the submit verb's guard
and silently moving the survey aggregate and the perception-gap board.

The module docstrings state the wrong invariant ("status and outcome are not on the form, so editing
can never move a plan through its lifecycle") - true, and beside the point: **the payload is not the
status.** Forks from a direct analogue in the same app, `ContractsManagement/Milestones.py:102,139`,
which gates both verbs on the identical `OPEN_STATUSES` tuple. `SupplierImprovementPlan.OPEN_STATUSES`
already exists and is used by three other helpers - just not by edit or delete.

#### SEC4 - MEDIUM - `evidence` is served as a raw unauthenticated `MEDIA_URL` link

`improvementplan/detail.html:132` renders `{{ obj.evidence.url }}` -> `/media/procurement/
improvement_evidence/YYYY/MM/<original-filename>`, served with **no session check and no tenant check**.
An audit report or NCR pack is readable by anyone who can guess a plausible filename under the current
month's folder.

**The upload validation itself is correct** - `clean_evidence` applies `ALLOWED_DOC_EXTENSIONS` then
`MAX_UPLOAD_BYTES`, `.svg` is correctly absent, and Django handles traversal in `upload_to`. The gap is
purely *serving*. `evidence_url` is **clean**: `URLField` rejects `javascript:` and `data:` at validation.

**Fix precedent is in this same app**, added by the 6.19 session five days ago -
`DocumentKnowledgeManagement/Revisions.py:226` routes downloads through an authenticated view. Mirror it.

**Pattern-clone family (L28), NOT for this fixer to sweep:**
`grep -rn "\.file\.url\|\.evidence\.url\|\.attachment\.url" templates/` finds **five more** in
procurement alone (catalogmanagement, goodsreceiptinspection, rfxmanagement, invoicevouchermanagement x2).
Only 6.19 routes through an authenticated view. Filed against 6.16 as the new instance; **carry the
family up as an app-wide item, do not silently edit the peers' files.**

#### SEC5 - LOW - unbounded `closure_note` written straight from the POST body

`SupplierImprovementPlans.py:357`. `closure_note` is `editable=False`, so it never passes a form or
`full_clean()`, and is written with `save(update_fields=[...])`. A >64 KB POST hits MySQL `TEXT`'s
65,535-byte ceiling -> uncaught `DataError` (500), or silently truncates a signed closure narrative
under non-strict SQL mode. Admin-only, hence Low. CRM's sibling already caps at `[:4000]`.

#### SEC6 - LOW - generate's draft check reads a row fetched OUTSIDE the transaction (verdict on R8)

`ScorecardKpiScores.py:270-272` -> `performance.py:588`. The view fetches the scorecard unlocked;
`generate_scorecard_lines`'s `@transaction.atomic` then re-checks `status` against that **stale
in-memory instance** and never re-reads. A scorecard published concurrently can still be generated
onto - writing the dimension columns and `manual_override` onto a **closed period**, the exact
invariant the guard exists to protect. Fix with `select_for_update()` per
`VendorManagement/VendorSuspensions.py:104-112`.

**Explicit disagreement with R8 on the other seven verbs:** `activate`/`monitor`/`cancel`/`close` are
last-writer-wins races between two actors who each already hold the right to make that transition, so
racing buys nothing; `acknowledge`'s race can only write a *later* timestamp than the one it
overwrites. **Correctness/audit-fidelity, not an exploit. Generate is the one worth locking.**

#### SEC7 - LOW - verdict on R3/R4/X5: agreed, not a bypass

The server-side gate holds completely - `@require_POST` sits outside `@tenant_admin_required`, whose
inner `@login_required` runs first, so anonymous GET is 405, anonymous POST redirects to login, and a
non-admin POST raises `PermissionDenied` with zero mutation. **One correction to the earlier framing:
the 403 is NOT a stack-trace leak even with `DEBUG=True`** - Django routes `PermissionDenied` to the
`permission_denied` handler, which never renders the technical page. It is unthemed, not disclosive.
Agrees with X5 that the fix is one `_is_admin` helper, not two template patches.

#### Clean - coverage statement

- **`breakdown` JSONField: clean, no user-controlled value can reach it.** All four writers traced -
  the 14 resolvers build it from computed integers and `str()`-ified Decimals plus hard-coded notes;
  the unknown-key branch echoes a `choices`-validated field; the edit form writes only
  choice-constrained or numeric values. Rendered `{{ row.key }}`/`{{ row.value }}`, flattened and
  `str()`-ified by the view, **autoescaping intact, no `|safe`-adjacent filter**. No stored-XSS path.
- **XSS/CSS injection: clean, unusually so.** Zero `|safe`, zero `mark_safe`, zero
  `{% autoescape off %}`, zero `escapejs`, zero `json_script`, **zero `<script>` blocks** across all 17
  templates. The eleven `|linebreaksbr` uses are on plain `TextField`s never marked safe. Every
  `style="..."` is literal except one guarded computed `Decimal`.
- **Inline handlers: clean, all 18 `confirm()` sites checked.** Only system-assigned identifiers reach
  a handler - no `title`, `supplier.name`, `finding` or `kpi_name`. Independently reproduces reviewer 3.
- **Mass assignment: clean, enumerated field by field.** `manual_override` is on no 6.16 form. All
  seven frozen columns plus 12 others are `editable=False` so a ModelForm cannot bind them;
  `status`/`outcome`/`score`/`band`/`weight_applied` are kept out by explicit `Meta.fields` allowlists.
  **`SupplierKpiScoreEditForm` specifically: a crafted POST cannot edit a derived line** - the view
  refuses `source_at_time != "manual"` and redirects *before* `crud_edit`, on GET and POST alike.
- **Cross-tenant disclosure: clean, and `_reject_foreign` produces no oracle** - it is in practice
  unreachable because `ModelChoiceField.to_python()` queries the already-narrowed queryset first and
  fails with Django's generic message, so "another tenant's row" and "no such row" are observationally
  identical. No count, aggregate, `<select>` option or window picker escapes the tenant filter.
- **Audit trail: clean; no 6.16 field belongs on `_SENSITIVE_AUDIT_FIELDS`.** `closure_note` is
  deliberately absent from the close verb's `changes` dict - correct. X8 confirmed harmless.
- **N1 gains a disclosure dimension:** `crud.py`'s `is_int=True` branch has **no try/except at all**, so
  the `ValueError` surfaces during `Paginator` evaluation, outside `crud_list`. `DEBUG` **defaults to
  `True`** at `settings.py:16`, so a deployment shipping without a `.env` renders the full technical
  500 - traceback, locals, `META`/`COOKIES` - from a URL anyone can type.
- **S1/R5 carry no injection risk:** `?source=` is ORM-parameterised; `?category=` never reaches the
  database at all (Python-side comparison over a 120-char-truncated value). Silent-empty UX bugs only.
- **Also clean:** zero `.raw()`/`.extra()`/`cursor.execute`; 22/22 POST forms carry `{% csrf_token %}`
  (the GET filter forms are correctly tokenless); no `@csrf_exempt`; **no `?next=` or any user-supplied
  redirect**; all 33 views decorated with `require_POST` correctly outside the auth decorator so no
  ordering bypass exists; no raw `request.GET` echoed into markup (all 26 reflections are `{% if %}`
  comparisons); the tenant trust root is sound (`TenantMiddleware` reads `user.tenant` from the
  database, never a header); the alert's `link_url` is built from an integer pk and cannot become an
  open redirect.

---

