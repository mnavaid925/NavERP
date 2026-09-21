# Plan 2 — Land the already-fixed defects (3 modified files, uncommitted)

**Created:** 2026-09-19 · **HEAD at authoring:** `0ba7f760` · **Status:** ✅ **COMPLETE — verified 2026-09-21**
**Scope:** 3 modified files · **Effort:** small — verify, then 3 single-file commits

> **CLOSED 2026-09-21.** All three fixes are landed and verified in the files; the four "Done when"
> gates pass (see the checkboxes at the foot). Re-verified from scratch rather than taken on trust:
> the nav leaf reverses to `/projects/dependencies/`, the SOW fixture builds with `start_date`, and the
> conftest carries the new field names. Commits: `c7a9eef4` (nav), `81e7a99d` (conftest), `9248505f`
> (unused import — the `test_financialbilling_forms.py` change itself was committed by a concurrent
> session first, as `ad6f6dc7`).
>
> **One real defect found in the audit itself while closing this out** — see "Check 6 was wrong" below.

---

## Check 6 was wrong, and is now fixed

Closing this plan required `temp/audit_integrity.py` to pass all 6 checks, and check 6 was **failing**.
It was not the seeders: **the check was wrong.**

It read ONLY `apps/<app>/management/commands/seed_<app>.py` and reported any model whose name did not
appear there as unseeded. But `core.SensitiveFieldMask` is seeded from **`seed_accounts.py`** — legitimately,
because its `exempt_roles` M2M needs an `accounts.Role` to exist first. The check reported a
**false positive** on a model that IS seeded.

**Fixed:** the check now scans every `seed_*.py` in the project and, when a model is not in its own
app's seeder, reports *which* seeder does reference it. It also distinguishes "unseeded and unexplained"
from "exempt, with a reason" — and every exemption now prints its reason:

| model | why it carries no demo data |
|---|---|
| `core.SensitiveFieldMask` | seeded by `seed_accounts` (cross-app — needs a Role) |
| `core.DisposalRecord` | evidence of a real disposal; seeding one invents a disposal that never happened |
| `core.SettingValue` | an operator's override; ABSENCE means "take the definition default" |
| `core.CustomFieldValue` | a value belongs to a record that does not exist in the seed |
| `core.BusinessRuleLog` | an evaluation log records that something happened; seeding one fabricates an event |
| `projects.ProjectReportRun` | a report EXECUTION record; seeding one fabricates a run (7.16, another session's) |
| `core.AuditLog` / `crm.HealthScore` / `procurement.WidgetPreference` | as before |

An exemption without a stated reason is indistinguishable from an oversight — which is the thing this
check exists to catch, so a blanket `[expected: non-seeded by design]` was undermining it.

`temp/` is **gitignored** (0 tracked files), so this improvement lives locally by design and cannot be
committed. It will be in effect for every future audit run.

---

## Goal

Three defect fixes are sitting in the working tree, verified but uncommitted. Commit them **one file per
commit** so each is reviewable and revertible on its own. Nothing here needs new code — it needs
confirmation and landing.

## Current working tree

```
 M apps/core/navigation.py                             <-- MY fix (nav defect)
 M apps/projects/tests/conftest.py                     <-- ANOTHER SESSION's fix (adopt, don't discard)
 M apps/projects/tests/test_financialbilling_forms.py  <-- MY fix (test defect)
?? .claude/tasks/contract-projects-7.16.md             <-- ANOTHER SESSION's, mid-build — LEAVE ALONE
?? .commandcode/  .gemini/antigravity/  .workbuddy-ai/  .zcode/   <-- untracked tooling dirs — LEAVE ALONE
```

---

## Fix 1 — `apps/core/navigation.py` (1 line)

**The defect.** `LIVE_LINKS["7.8"]["Task Dependencies & Blocking"]` pointed at `projects:dependencies`,
a route that does not exist. The register is `projects:dep_list` (7.2's `TaskDependency` — exactly what
the surrounding comment in the file describes).

**Why it was silent.** `_safe_reverse()` catches `NoReverseMatch` and returns `None`; `_feature_node()`
then sets `live: False`; `templates/partials/sidebar.html` falls into its `{% else %}` branch and renders
`<a class="nav-roadmap">…<span class="pill-soon">soon</span>`. So a **fully built** register was
advertised as roadmap and unreachable from the sidebar — with no 500 to notice. Same class as 7.10's
`_cc_activityfeed`.

**Applied fix:** `"projects:dependencies"` → `"projects:dep_list"`.

**Verify before committing:**

```bash
venv\Scripts\python.exe temp\audit_integrity.py
```
Check 5 must read `581 distinct targets` and PASS. (Before the fix it was 582 targets with 1 broken —
the count drops because the regex no longer sees a distinct name.) Direct confirmation:

```bash
venv\Scripts\python.exe -c "import os,sys,django; sys.path.insert(0,os.getcwd()); os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings'); django.setup(); from apps.core.navigation import LIVE_LINKS,_safe_reverse; print(_safe_reverse(LIVE_LINKS['7.8']['Task Dependencies & Blocking']))"
```
Expected: `/projects/dependencies/`

**Commit:**
```bash
git add apps/core/navigation.py
git commit -m "fix(core): point 7.8 Task Dependencies sidebar leaf at projects:dep_list"
```

---

## Fix 2 — `apps/projects/tests/conftest.py` (25 insertions / 22 deletions)

**Not mine — adopt it, never `git checkout` it away** (house rule for a stalled concurrent session).
It aligns the 7.15 fixtures with the fields the committed models actually have:

| fixture | was | now |
|---|---|---|
| rate card | `rate_type`, `daily_rate` | `expense_markup_pct` |
| billing run | `date_from` / `date_to` | `run_date` / `cutoff_date` |
| revenue schedule | `client`, `currency`, `fiscal_period_name` | dropped; `recognition_date` added |
| payment record | `currency`, `amount_due`, `amount_paid` | mints a real `accounting.Invoice` via `accounting_invoice` |

The fixtures were committed at 13:04; the models they must match were committed earlier. The diff is
coherent and matches the models, so it is a genuine fix.

**Verify:** the three 7.15 test files that use these fixtures must be green — see Fix 3's run below.

**Commit:**
```bash
git add apps/projects/tests/conftest.py
git commit -m "test(projects): align 7.15 financial billing fixtures with model fields"
```

---

## Fix 3 — `apps/projects/tests/test_financialbilling_forms.py` (1 test + 1 import)

**The defect.** `test_financialbilling_billing_run_form_rejects_mismatched_project_and_sow` constructed
its fixture row with `StatementOfWork.objects.create(..., effective_date=...)`. `effective_date` belongs
to **`SOWAmendment`**, not `StatementOfWork` — which requires non-null `start_date` and `end_date`
(`apps/projects/models/ClientExternalCollaboration/StatementOfWorks.py:63-64`). Result:

```
TypeError: StatementOfWork() got unexpected keyword arguments: 'effective_date'
```

The test died in setup, so its assertion never ran.

**Applied fix:** `effective_date=…` → `start_date=…` + `end_date=… + timedelta(days=90)`, plus
`from datetime import timedelta`.

**This was the only such mismatch in the 7.15 lanes** — proven, not assumed. A static AST sweep over all
five 7.15 test files + conftest, checking every `<Model>.objects.create(...)` / `<Model>(...)` kwarg
against `model._meta` fields, reports `clean`. The sweep's sensitivity was verified by running it against
the pre-fix file from `git show HEAD:…`, where it correctly reported exactly
`StatementOfWork.objects.create -> unknown kwarg 'effective_date'`.
Script: `temp/sweep_715_fields.py`.

**Verify — this is the gate that matters:**

```bash
venv\Scripts\python.exe -m pytest apps/projects/tests/test_financialbilling_forms.py apps/projects/tests/test_financialbilling_models.py apps/projects/tests/test_financialbilling_views.py apps/projects/tests/test_financialbilling_security.py --nomigrations -p no:cacheprovider --junitxml=temp/junit_715_nm.xml
```

**Verified 2026-09-19: `28 passed, 0 failed in 28.07s`.** The pre-fix baseline, from the same four files
without `--nomigrations`: `tests=28 failures=1 errors=0 time=2349.06s` — the single failure being
`test_financialbilling_billing_run_form_rejects_mismatched_project_and_sow` with exactly the
`effective_date` TypeError described above (read from `temp/junit_715.xml` via `xml.etree`).

> **⚠ USE `--nomigrations` FOR EVERY ITERATION — this is an ~84× difference, not a nicety.** Measured on
> the four 7.15 lanes: **2,349 s (39 min)** with migrations vs **28 s** without. A *single test* is worse:
> **2,702 s (45 min)** with migrations vs **14.5 s** without — **~186×**. Both runs passed; nothing was
> broken, it was purely the cost of applying migrations.
>
> **A long run looks like a dead run.** Piping through `tail -N` buffers *all* stdout until the process
> exits, so a 45-minute run shows **zero output for 45 minutes** — no progress, no partial results, nothing
> to distinguish it from a hang. Do not conclude a run has died from silence; check for a live python
> process (`Get-Process python`) and whether the `--junitxml` file has appeared, or just re-run with
> `--nomigrations`.
>
> Read counts from the `--junitxml` file with `xml.etree`, never from grepping stdout.
>
> `--nomigrations` is an **iteration** aid: still do one final full run *without* it (and without `-k`)
> before closing the phase, because it skips migration application and therefore cannot catch an
> unapplied-migration defect — the 7.10 failure mode. `temp/audit_integrity.py` check 2 covers that.

**Commit:**
```bash
git add apps/projects/tests/test_financialbilling_forms.py
git commit -m "test(projects): use start_date/end_date when building the foreign SOW fixture"
```

---

## Done when

- [x] The 7.15 four-file suite is **28 passed / 0 failed** — re-verified 2026-09-21: `28 passed in 17.81s`
      with `--nomigrations` (`temp/junit_715_plan2.xml`).
- [x] `temp/audit_integrity.py` passes all 6 checks — re-verified 2026-09-21, after fixing check 6
      itself (see above). 3,649 route names reverse; 2,199 template references resolve; 655 sidebar
      targets resolve; every migration applied.
- [x] Three commits exist, one per file: `c7a9eef4`, `81e7a99d`, `9248505f`.
- [x] `git status` shows no file of mine. The tree's remaining modifications are **another session's**
      7.16/7.18 work in `apps/projects/` and `templates/projects/reporting/` — not this plan's, and not
      mine to touch (L45). The plan's original expectation named `contract-projects-7.16.md`; that
      session has since progressed past it, which is why the untracked set differs.

## Verified in the files (not just "the commit exists")

| fix | check | result |
|---|---|---|
| 1 nav leaf | `_safe_reverse(LIVE_LINKS['7.8']['Task Dependencies & Blocking'])` | `/projects/dependencies/` ✅ |
| 2 conftest | `grep -cE 'expense_markup_pct\|run_date\|cutoff_date\|recognition_date'` | 5 ✅ |
| 3 SOW fixture | `StatementOfWork.objects.create(...)` uses `start_date` | line 161 ✅ |

## Notes

- **Never `git push`** — the user pushes.
- **Do not commit** `.claude/tasks/contract-projects-7.16.md`: a concurrent session is mid-build on 7.16
  and that file is its in-flight contract (written 15:56). It will commit it itself.
- If Fix 3's run surfaces a *different* failure, check provenance before "fixing" it — a concurrent
  session's drift showing up in your run is expected (L45), and 7.16 is being built in `apps/projects/`
  right now.
