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

---

## Reviewer findings

*(appended as each of the six reviewers reports: code-reviewer → explorer → frontend-reviewer →
performance-reviewer → qa-smoke-tester → security-reviewer)*
