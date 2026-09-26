# Plan 5 — Housekeeping: the untested dashboard app, transient artifacts, BOM files

**Created:** 2026-09-19 · **HEAD at authoring:** `0ba7b760` · **Status:** ✅ **COMPLETE — all three items closed 2026-09-26**
**Scope:** `apps/dashboard/`, `.claude/tasks/*.log`, 14 BOM files · **Effort:** small–medium
**Priority:** lowest of the five — do this last, or skip C entirely

> **Status re-verified 2026-09-22.** The original header said "not started"; that was stale.
> - **Item A — ✅ DONE.** `apps/dashboard/tests/` exists with both lanes and is green.
> - **Item B — open, and this plan's own recipe for it is WRONG.** Two of the three files are
>   gitignored and untracked, so `git rm` fails on them (details in Item B).
> - **Item C — open, no decision recorded.** All 14 files still carry the BOM.

> ## ✅ CLOSED 2026-09-26 — this plan is finished. Nothing here is outstanding.
>
> | Item | Outcome |
> |---|---|
> | **A** — dashboard tests | ✅ Done earlier (`32913e28`, `3fc46276`, `33447c3a`, `5c841a3e`) |
> | **B** — 2026-09-01 artifacts | ✅ **CLOSED.** `enum-guard-pass.md` **deleted** as `2500eec1`; the two `.log` files **deliberately kept on disk** (user's call, 2026-09-26) — they are gitignored, so keeping them costs nothing and a delete is unrecoverable |
> | **C** — 14 BOM files | ✅ **DECIDED: leave them.** Re-verified all 14 still begin `ef bb bf`; not a defect |
>
> **Re-verification done before acting on B** (not taken on the plan's 2026-09-22 word): the central
> enum guard really is live at `apps/core/crud.py:84` (`_enum_values`) and `:171-172` (the
> `continue` in `crud_list`'s non-int branch), and both tests the note demanded are corrected —
> `apps/procurement/tests/test_receipt_views.py:649` and `:1163` now assert
> `_receipt_pks(r) == [<the row>]`, not `== []`, each with a docstring naming the old behaviour.
> The note's content survives in the code, the two tests and `lessons.md`, so deleting it loses
> nothing — and it *was* tracked, which is the only reason that `git rm` was safe.
>
> **Item B's final state — one deleted, two deliberately kept (decided 2026-09-26).** The tracked
> `enum-guard-pass.md` was removed as `2500eec1`. The two `.log` files were **kept on disk by explicit
> user decision**: they are gitignored, so they never reach a commit and keeping them costs nothing,
> while deleting them is the one unrecoverable action in this whole plan. **Item B is closed — do not
> re-open it and do not try to `git rm` the logs; that command will fail and the intent was settled.**
>
> The evidence that made the decision safe to defer is recorded above, and was **re-verified
> independently on 2026-09-26** rather than taken from the 2026-09-22 run:
>
> ```
> apps/procurement/tests/test_invoice_{forms,views,security}.py
> apps/procurement/tests/test_spend_{forms,views,security}.py
> -> 808 tests, 0 failures, 0 errors, 1 skipped, 343.6 s
>    (temp/junit_plan5_itemB_recheck.xml, read via xml.etree)
> ```
>
> So all 20 failures the logs name are genuinely resolved and **nothing needs filing in `todo.md`**.
>
> **Item C's decision — "leave", taken deliberately, not by omission.** Python strips a UTF-8 BOM per
> PEP 263, so every one of the 14 files imports fine and `manage.py check` is clean. The only cost is
> that plain-utf-8 AST tooling chokes on them, which is a tooling wart, not a defect. Stripping would
> rewrite the first bytes of 14 files and land 14 commits of pure noise in a repo where every commit
> is expected to carry meaning. **If you are already editing one of these files for another reason,
> strip the BOM in that same commit.**

---

## Item A — `apps/dashboard/` has zero tests — ✅ **DONE (verified 2026-09-22)**

> **COMPLETE — do not rebuild this.** `apps/dashboard/tests/` now holds `__init__.py`, `conftest.py`,
> `test_dashboard_views.py` and `test_dashboard_security.py`, committed as `32913e28` (tests package),
> `3fc46276` (conftest fixtures), `33447c3a` (views lane) and `5c841a3e` (security lane).
> Re-run 2026-09-22 with `--nomigrations`: **15 tests, 0 failures, 0 errors, 65 s**
> (`temp/junit_dashboard_check.xml`, read via `xml.etree`). Exactly the **two lanes** specified — the app
> has no models and no forms, so no `_models`/`_forms` files were written.
>
> The steps and checklist below are kept as the record of what was asked for; the work is in the tree.

**The only app in the repo with no test lane.**

| app | test files |
|---|---|
| core | 8 |
| accounts | 6 |
| tenants | 6 |
| crm | 20 |
| accounting | 12 |
| hrm | 74 |
| scm | 27 |
| inventory | 77 |
| procurement | 71 |
| projects | 62 |
| **dashboard** | **0** |

The app is tiny — `apps.py`, `urls.py`, `views.py`, `migrations/__init__.py` (**no models of its own**) —
which is exactly why it has been skipped. But `views.home` is the **root landing page** every
authenticated user hits, and it contains real logic that a regression would break silently:

- **`tenant = request.tenant` with an explicit `if tenant is not None:` guard** — the no-tenant path must
  render 200 with zeroed stats, not raise.
- **A latest-value-per-metric subquery** — `HealthMetric.objects.filter(...).values("metric").annotate(latest_id=Max("id"))`.
  This is the kind of query that silently returns the *wrong row* (not an error) if edited.
- **Cross-app aggregation** over `core.Party`, `core.PartyRole`, `core.Activity`, `core.AuditLog`,
  `tenants.Subscription`, `tenants.SubscriptionInvoice` — six tables from two other apps.
- **Chart label resolution** — `dict(PartyRole.ROLE_CHOICES)` / `dict(Activity.STATUS_CHOICES)` mapping
  raw values to display labels, with a `.get(raw, raw)` fallback.
- `@login_required`, and `recent_audit` capped at 8 with `select_related("user")`.

### Steps

1. **Write the contract first** — `.claude/tasks/test-contract-dashboard-0.0.md`, pinning fixtures and the
   exact expected figures (per the house Phase-6 rule: contract before conftest before tests).
2. **Append the conftest block** for dashboard (append-only — never rewrite an existing block, L43).
3. **Write two lanes, not four** — the app has no models and no forms, so `_models`/`_forms` lanes would
   be empty files:
   - `apps/dashboard/tests/test_dashboard_views.py` — 200 for an authenticated tenant user; the six
     aggregates equal the seeded figures; `latest` health row per metric is the **highest-id** row (build
     two rows for one metric and assert the newer one wins — this is the subquery's whole point);
     `recent_audit` capped at 8; chart label lists match their data lists in length and map values
     correctly; `stats["subscription"]` is the newest subscription.
   - `apps/dashboard/tests/test_dashboard_security.py` — anonymous → redirect to login (not 200);
     **tenant isolation**: tenant A's dashboard never counts tenant B's parties/users/audit rows;
     the no-tenant path returns 200 with zeroed stats.
4. **Commit each file separately**, `conftest.py` last so the lanes can be run as they land.

### Verify

```bash
venv\Scripts\python.exe -m pytest apps/dashboard/tests --junitxml=temp/junit_dashboard.xml
```
Then confirm the full suite still passes, and re-run `venv\Scripts\python.exe temp\audit_integrity.py`
(all 6 checks — a new test lane must not disturb them).

---

## Item B — Transient run artifacts left in `.claude/tasks/`

`.claude/tasks/` is the project's **working memory** — the home of `todo.md`, `lessons.md`,
`build-state.json` and the per-run `research-`/`review-`/`contract-`/`test-contract-` files. Three files
there are not working memory; they are one-off debug output from 2026-09-01:

| file | size | date | what it is |
|---|---|---|---|
| `invoice-test-failures.log` | 28,480 B | 2026-09-01 20:04 | raw pytest failure dump |
| `spend-test-failures.log` | 9,748 B | 2026-09-01 06:21 | raw pytest failure dump |
| `enum-guard-pass.md` | 3,825 B | 2026-09-01 08:35 | a one-off pass note |

**Before deleting anything, read them** — the two logs may still name unresolved failures. If they are
resolved (both are from 2026-09-01, and the modules involved have since been reviewed and closed out),
they are dead weight. `enum-guard-pass.md` may belong in `lessons.md` if it records a rule.

### ⚠ The plan's own `git rm` recipe is WRONG — corrected 2026-09-22

The paragraph above (and step 3 below) assume all three files are **tracked**. They are not. Verified:

```bash
git ls-files .claude/tasks/{invoice,spend}-test-failures.log .claude/tasks/enum-guard-pass.md
#  -> .claude/tasks/enum-guard-pass.md          (only this one)
git check-ignore -v .claude/tasks/invoice-test-failures.log
#  -> .gitignore:59:*.log   .claude/tasks/invoice-test-failures.log
```

| file | tracked? | `git rm` works? | deletion recoverable? |
|---|---|---|---|
| `invoice-test-failures.log` | **no — gitignored** (`.gitignore:59 *.log`) | **no** | **no** |
| `spend-test-failures.log` | **no — gitignored** | **no** | **no** |
| `enum-guard-pass.md` | yes | yes | yes (via history) |

So the plan's stated justification — *"a `git rm` on tracked files is reversible via history, which is why
it is acceptable here"* — **does not hold for the two logs**. Deleting them is a plain filesystem delete
with no undo. **They require the user's explicit confirmation, and there is no `git rm` to run.** This is
the one place where the plan would have led a session into an unrecoverable action.

### Read verdict (2026-09-22)

All three were read before any decision, as the plan requires:

- **`enum-guard-pass.md` — the work it describes has LANDED; the note is now redundant.** The central
  guard exists in `apps/core/crud.py` as `_enum_values()` (line ~100), called from `crud_list`'s
  non-int branch at line 171: `choices = _enum_values(qs.model, lookup)` / `if choices is not None and
  mapped not in choices: continue` — with the deliberate narrowness the note specifies (`__` in lookup,
  unknown field, no `choices`, non-string choice values all skip the guard). Both test corrections it
  demanded were made: `test_receipt_discrepancy_list_junk_enum_params_never_500` and
  `test_receipt_rtv_list_junk_enum_params_never_500` now assert `_receipt_pks(r) == [<the row>]` instead of
  `== []`, with docstrings naming the old behaviour. The rule is also captured in `lessons.md`.
  **Verdict: safe to delete** (tracked, reversible) — its content survives in the code comment, the two
  corrected tests and the lesson.
- **The two `.log` files — every failure they name is now RESOLVED; they are dead weight.** They are raw
  pytest dumps naming **15 failures in `test_invoice_*`** and **5 in `test_spend_*`** (e.g.
  `_invoice_header_post() got multiple values for argument 'vendor'`, `assert None == 'date'` on the
  `document_date` widget, `assert 'Pending Approval' == 'Pending approval'`). Re-ran the six named files on
  2026-09-22 with `--nomigrations`:

  ```
  apps/procurement/tests/test_invoice_{forms,views,security}.py
  apps/procurement/tests/test_spend_{forms,views,security}.py
  -> 808 tests, 0 failures, 0 errors, 1 skipped   (temp/junit_plan5_itemB.xml)
  ```

  So the plan's expectation holds — the modules were reviewed and closed out since 2026-09-01. **Nothing
  needs filing in `todo.md`; the logs are safe to drop.** (Counts read from the `--junitxml` file via
  `xml.etree`, because `pytest -q | tail -N` dropped the summary line — as documented.)

### Steps (corrected)

1. ~~`git rm` all three~~ → **`git rm` only `enum-guard-pass.md`**; the two logs need a plain delete after
   the user confirms.
2. If the re-run still names a failure, file it in `todo.md` first, then delete the log.
3. Confirm with the user before removing the two logs — **this is not recoverable**.

```bash
# the tracked one — reversible via history
git rm .claude/tasks/enum-guard-pass.md
git commit -m "chore(tasks): drop the enum-guard pass note (landed in crud_list + both tests)"

# the two logs — only after explicit confirmation, and NOT via git rm
rm .claude/tasks/invoice-test-failures.log
rm .claude/tasks/spend-test-failures.log
```

**One file per commit**, so a mistaken deletion is trivially revertible.

---

## Item C — 14 Python files carry a UTF-8 BOM (cosmetic — optional)

> **Re-verified 2026-09-22: all 14 still carry the BOM** (`head -c 3 | od -An -tx1` → `ef bb bf` on every
> one). No decision has been recorded, so this item is genuinely open — but the recommendation is
> unchanged: **leave them.** Note the plan's own framing is correct — Python strips the BOM per PEP 263,
> `manage.py check` is clean, and this is a tooling wart, not a defect.

`ast.parse` on a plain-utf-8 decode raises `SyntaxError: invalid non-printable character U+FEFF`, which
makes these files invisible to AST-based tooling. **Python itself imports them fine** (it strips the BOM
per PEP 263), the app loads, and `manage.py check` is clean — so this is **not a defect**. It is a
tooling wart.

| app | files |
|---|---|
| inventory | `forms/BarcodeRfidIntegration/__init__.py`, `management/commands/seed_inventory.py`, `models/BarcodeRfidIntegration/__init__.py`, `urls/BarcodeRfidIntegration/__init__.py`, `views/BarcodeRfidIntegration/__init__.py`, `views/ReportingAnalytics/ReportSnapshots.py` |
| procurement | `forms/RequisitionManagement/Amendments.py`, `forms/RequisitionManagement/Templates.py`, `views/_helpers.py`, `views/ContractsManagement/Clauses.py`, `tests/test_reqmgmt_views.py`, `tests/test_sourcing_forms.py`, `tests/test_sourcing_security.py`, `tests/test_sourcing_views.py` |

**Recommendation: leave them.** Stripping a BOM rewrites the first bytes of 14 files for zero functional
gain, and would produce 14 commits of pure noise in a repo where every commit is expected to carry
meaning. **Only do it if** you are already editing one of these files for another reason — in which case
strip the BOM in that same commit.

---

## Done when

- [x] `apps/dashboard/tests/` exists with a views lane and a security lane, both green — **verified
      2026-09-22: 15 tests, 0 failures, 0 errors** (`temp/junit_dashboard_check.xml`). Landed by
      `32913e28` / `3fc46276` / `33447c3a` / `5c841a3e`.
- [x] The three 2026-09-01 artifacts are resolved — **`enum-guard-pass.md` deleted** as `2500eec1`
      (its content already lived in `apps/core/crud.py` and two corrected tests); **the two `.log`
      files deliberately kept on disk** by user decision, since they are gitignored and a delete is
      unrecoverable. Re-verified 2026-09-26 that all 20 failures they name are resolved:
      **808 tests, 0 failures, 0 errors, 1 skipped** (`temp/junit_plan5_itemB_recheck.xml`).
- [x] Item C: explicitly decided — **LEAVE the 14 BOM files.** All 14 re-confirmed to begin
      `ef bb bf` on 2026-09-26. Not a defect (PEP 263); strip opportunistically if already editing one.
- [x] Each change committed separately. **Never `git push`.**

## Note

This was the lowest-value plan of the five, and **all five are now complete** (re-verified
2026-09-26 — see `plan-remaining-INDEX.md`). **Nothing in the `plan-remaining-*` set is outstanding
except Plan 1 (Module 0, 0.17–0.21)** — the real remaining work.
