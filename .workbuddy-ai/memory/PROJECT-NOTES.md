# NavERP — PROJECT NOTES (full detail)

> Companion to `MEMORY.md`, which is the always-injected digest. This file is NOT injected —
> read it when you need the detail behind a digest line. Consolidated 2026-09-23 from the
> 11.4 KB MEMORY.md that was being **truncated on injection** (content was silently lost at
> session start, which is worse than having less of it).

---

## Where the rules live — `.claude/` is canonical, never fork a parallel convention

`CLAUDE.md` (conventions) · `PROMPT.md` (brief) · `skills/<name>/SKILL.md` (per-module, plus
`next-module`, `sqa-review`, `manual-test`, `dump-module`) · `agents/` (reviewer/tester/fixer
personas) · `tasks/` = working memory: `todo.md` (newest plan prepended at TOP), `lessons.md`
(L-rules), `build-state.json` (gitignored + stale), and the `research-*` / `review-*` /
`contract-*` / `test-contract-*` / `plan-remaining-*` artifacts.

## Stack

Django 5.1, **function-based views only**, Tailwind CDN + HTMX, MySQL/MariaDB (`nav_erp`) via
XAMPP. Python only via `venv\Scripts\python.exe`. `models/ forms/ views/ urls/` are packages —
one folder per sub-module, one file per entity. Templates at
`templates/<slug>/<submodule>/<entity>/<page>.html`. **One file per commit** on `main`;
**never `git push`** — the user pushes.

**Foundation-app FLAT layout.** `core` / `tenants` keep entity files at the package root
(`models/Backup.py`) and templates at `templates/core/<entity>/<page>.html`; `urls.py` is flat.

## Build state — trust the code, not the catalog

`apps/core/navigation.py` `LIVE_LINKS` is the truth for "built". `NavERP.md` / `README.md`
status tables go stale — read `LIVE_LINKS` + `git log`.

A `LIVE_LINKS` entry + committed backend can still be non-functional (7.10: 21/22 templates
missing, migration `0014` unapplied, no seeder rows, Live sidebar 500s). Three things
`check` / `makemigrations --check` **cannot** see:

1. `showmigrations <app>` — is the last migration *applied*?
2. `reverse()` every route name in the new url module.
3. Template-reference count.

`/next-module` builds exactly ONE `N.M`, does **not** cover Module 0, and bare runs serialise —
check `git log` before assuming what "next" means.

## Close-out workflow (Phases 4–7)

1. **Review** — six reviewers strictly serially, each appending its own section to
   `review-<slug>-<N.M>.md`, then a deduped `# CONSOLIDATED FINDINGS` block with `C#/I#/M#` ids
   plus explicit no-action entries. Commit each lane.
2. Verify every load-bearing Critical yourself with a scratch probe before filing.
3. **Fix** — one `code-fixer` pass; re-verify each Critical with an independent probe.
4. **Tests** — `test-contract-<slug>-<N.M>.md` pinning fixtures + figures FIRST, then the
   conftest block (**append-only**, L43), then `test_<subslug>_{models,forms,views,security}.py`
   one file per commit. Final gate = full **unfiltered** app suite.
5. **Docs** — update the module's EXISTING `.claude/skills/<slug>/SKILL.md` (`## N.M` + Routes /
   Templates / Seeder / Tests / Sidebar + As-built), the `README.md` roadmap counter, and
   `### <Module> N.M — <Title> (close-out YYYY-MM-DD)` in `todo.md`. Each committed alone.

### Review method (proven on 7.10 — 53 findings / 5 Critical; reused on 0.16 — 30 / 7)

- Give each lane the **already-fixed** defects as SANITY-CHECKS, not findings.
- Lane-local ids (`L1-C1`) → canonical `C#/I#/M#` only in the consolidated block.
- Have each lane **return its section as text** and append it yourself.
- Add an "Orchestrator verification" block per lane (corrected 2 of lane 1's claims on 7.10).
- A coverage claim is not evidence — probe it.
- A lane can be right on mechanism and **wrong on severity** — re-set severity on evidence.
- **Your own probe can be wrong** — verify its inputs.
- Name cross-module items **carried**, not folded in.

## Traps that cost real time

- **Always iterate with `--nomigrations`** (~84–186×: four lanes 2,349 s → 28 s; one test
  2,702 s → 14.5 s, all passing — the cost is purely migration application). Keep ONE final run
  *without* it as the phase gate; the flag cannot catch an unapplied migration
  (`temp/audit_integrity.py` check 2 can).
- **A long run looks like a dead run.** `pytest | tail -N` buffers all stdout until exit, so a
  45-min run shows nothing for 45 min. Do not diagnose death from silence: check for a live
  process or the `--junitxml` file, or re-run with `--nomigrations`. Read counts from
  `--junitxml=` via `xml.etree`; `pytest -q | tail` can drop the summary line.
- A concurrent session's failing tests appear in your "unfiltered" run. Prove *your* files
  green, then report foreign failures with provenance instead of "fixing" another session's
  drift (L45).
- Never enumerate routes with a bare resolver walk — scope to
  `get_resolver().namespace_dict['<app>']`.
- A derived property calling `.filter()` bypasses the prefetch cache (only `.all()` reads it) —
  compute in the VIEW off the prefetched list (7.8 `tsk_detail`: 31 → 13 queries).
  `Prefetch("a__b")` = 2 queries; `Prefetch("a", queryset=A.objects.select_related("b"))` = 1.
- **Probe the EMPTY state.** A context key derived from a project-scoped var 500'd
  (`UnboundLocalError`) with no `?project=`. Always test no-param and junk-param requests.
- **A `unique_together` including `tenant` is NEVER validated by a `ModelForm`** (0.15 C1).
  `tenant` is never in `Meta.fields`, so `Model._get_unique_checks()` drops the whole tuple; the
  form validates, `crud_create` saves, MySQL raises `IntegrityError` — an unhandled 500 on
  create *and* edit for typing an existing name. Repo-wide shape: any
  `unique_together = (tenant, <field>)` with a form excluding `tenant`. Guard with
  `clean_<field>` scoped to `self.tenant`, excluding `self.instance.pk`; reference
  `apps/crm/forms/CustomerSuccess/HealthScores.py`.
- **pytest fixtures are LAZY** — an exact count pinned from a probe that requested a fixture the
  lane never asks for is a fixture-graph accident, not a measurement. Name the fixture in the
  test signature.
- **Never parallel-`Edit` the same file** — edits race and silently lose updates.
- **A rate-limited agent may have already done work.** A `code-fixer` returning 429 had
  committed 13 fixes first. Re-read `git log` before re-running a failed agent.
- A template comment describing a regex-scanned pattern MATCHES the scan — write such comments
  without the literal.
- **`manage.py shell < script.py` cannot execute an indented block** — the interactive console
  runs stdin line-by-line → `IndentationError` everywhere. A `temp/` sweep needs
  `sys.path.insert(0, <project root>)` + `python temp/x.py` as a plain script.
- **`response.context` is `None` in a plain script** without
  `django.test.utils.setup_test_environment()`. A `TestCase` calls it for you; a bare script
  does not. Every `temp/_*_probe.py` should call it explicitly.
- **This project's `User.objects.create_user()` requires `email`** — omitting it raises
  `TypeError` and silently skips whatever block it was in.
- **Computing a count by subtraction (`total - complement`) double-counts a row satisfying two
  OR'd conditions.** Prefer a row-wise `sum()` in Python. (0.16 C4's probe made exactly this
  mistake and reported a defect the view did not have.)
- **A "no choice label is truthy" assertion trips on Django's `'---------'` blank label.**
  Assert the actual security claim instead (no other tenant's value appears among the labels).

## Writing tests here — what costs a round each (learned on 0.16, 266 tests)

- **The test DB is SQLite, not MariaDB.** `pytest.ini` sets `DJANGO_SETTINGS_MODULE =
  config.settings_test`, whose `ENGINE` is `django.db.backends.sqlite3` with `NAME = ":memory:"`. The dev
  DB is MariaDB. So **never assert a server-specific mechanism** — C5's finding is MariaDB's NULL-last
  ordering, and SQLite happens to agree (verified: `ORDER BY x DESC` → `2, 1, NULL`), so the defect
  reproduces and the test is meaningful, but the assertion must be on the **outcome**.
- **A `ModelForm` refusal is not a database one.** `DataArchive.location` is `blank=False`, so
  `full_clean()` refuses `location=""` — but the column accepts it and the seeder plants exactly that row
  (the unrestorable archive the board counts). Fixture helpers therefore take a `_validate=True` flag and
  the deliberately-invalid states opt out; the form lane covers the refusal separately.
- **`created_at` is `auto_now_add`**, so the age a board computes cannot be set at insert time. A row
  "past its window" is built by creating it and then `.update(created_at=…)`. Without that the premise
  test passes while proving nothing.
- **`EnvironmentInstance` refuses `expires_at < created_at`**, so an environment *already past its
  reaping date* is unbuildable through `full_clean()` — yet it is the un-reaped sandbox the board lists.
  Same escape hatch.
- **A `OneToOneField` singleton forbids two fixtures.** `RecoveryPosture.tenant` is unique, so a both-set
  and a half-set posture cannot share a workspace; the second uses another tenant, and property tests
  build **unsaved** instances.
- **`form.initial` carries the related PK (an int) for a FK**, not the instance — `value.pk` raises
  `AttributeError`. Use `str(value)` when it has no `.pk`.
- **Check whether a field is a form field at all before posting it.** `LegalHoldForm` has no `issued_at`
  (a hold is issued when it is recorded), so a posted value is silently ignored and the model default
  applies — which is *why* C3's incoherent state is reachable only on the **edit** path.
- **A test that asserts a rule must be able to run the rule.** Using a past-expiry fixture in a cycle
  test fails on `expires_at` and reports a cycle failure that is really a fixture artefact.
- **Model constraints bite fixtures too**: `RestoreRecord` refuses a restore with no source;
  `ConsentRecord.purpose` is a FK to `ConsentPurpose`, not a string.
- **Enumerate, don't spot-check, when the blast radius is shared.** C7's probe walks all 619
  `TenantModelForm` subclasses — that is what found a live leak in a different app.
- **Compare JUnit XML failure SETS, not counts.** `--junitxml` + `xml.etree` gives the exact
  before/after/fixed/new partition; a console `| tail` had already cut the list off at 12 of 19.
- **`git worktree add temp/_baseline <sha>` is the cheap way to prove "pre-existing"** — run the failing
  tests at the pre-session commit rather than asserting they are someone else's. Remove with
  `git worktree remove --force`.

## Security shapes (from 7.10 + 0.16)

- **Decorator order decides 405 vs 403.** Decorators apply bottom-up, so the OUTERMOST runs
  first; the house standard is **405 for a wrong method regardless of role** (7.7's ruling) —
  put `require_POST` ABOVE the role gate (`@login_required` above it is fine, it is not a role
  gate). The `tenants` app's older verbs (`encryptionkey_rotate`, `subscription_mark_paid`)
  still carry the pre-7.7 order — not yet swept.
- **`.alert` / `.alert-info` / `.alert-warning` / `.alert-danger` do NOT exist in
  `static/css/theme.css`.** The house inline-notice pattern is `<p class="text-muted">`
  (variants `.text-warn`, `.text-ok`, `.text-danger`, `.text-brand`). Badges are colour-named
  only (`badge-green/amber/red/info/muted/slate`).
- **A tenant-wide seeder guard silently strands every entity added later.** Give each entity its
  own `if Model.objects.filter(tenant=tenant).exists(): return`.
- **An upload allow-list forked from the house list drifts into danger**: 7.10 added `.svg` (the
  one scriptable extension `core.forms.ALLOWED_DOC_EXTENSIONS` omits) and `MEDIA_ROOT` is served
  unauthenticated with `Content-Disposition: inline`. **Import and extend the house list; never
  re-declare it.**
- `AuditLog.action` is `varchar(10)` and `.create()` never validates `choices` — a longer action
  truncates silently on non-strict MySQL or raises `DataError` (500) under
  `STRICT_TRANS_TABLES`. The verb goes in `changes`. **25 sites across `apps/` still violate
  this** (0.16 adds zero).
- Never interpolate user text into a single-quoted JS literal in `onsubmit` — HTML escaping does
  not protect an inline-handler attribute. Use `|escapejs`. **L42**, third recurrence.
- No delete path here erases bytes: Django never unlinks a `FileField` on row delete and
  `--flush` touches no files, so "delete" is a UI claim. Any "delete"/"reset" claim needs a
  reference-counted unlink (watch `pdv_restore`, which deliberately shares a path).
- **A green badge is an ACTIVE REASSURANCE and must be earned.** Never render one when the
  denominator is zero — pass `None` and name it ("not applicable", the idiom at
  `backupboard.html:23`). 0.8's rule: *"Reporting 0 here would be a false all-clear."* Django's
  `{% if x is None %}` works in the if-tag.
- **`TenantModelForm` scoping is a shared Module-0 seam (`forms/_common.py`) — and a KNOWN, OPEN
  issue, not a rule to "fix".** The base class deliberately leaves a queryset unnarrowed when
  `tenant=None`. Reason: the affected modules (`projects`, `procurement`, `scm`, `inventory`) run a
  two-layer guard — layer 1 is a view-level `request.tenant is None` redirect, layer 2 is
  `_reject_foreign(...)` in `clean()`, which returns the precise *"That record belongs to another
  workspace."* message. **Layer 2 requires the queryset NOT to be pre-narrowed**, because Django
  validates `ModelChoiceField` in `Field.clean` (before `Form.clean`), so an emptied queryset
  short-circuits at field level and the operator gets Django's generic *"Select a valid choice…"*.

  On 2026-09-23 a 0.16 fix emptied the queryset for `tenant=None`. Measured on the same 4,866-test
  corpus: **19 failures with it, 4 without, 0 introduced by the revert** — it broke 15 tests across
  inventory (3), procurement (6) and projects (6). Reverted (`68ebb8eb`), escalated, not fixed.
  `test_initiation_forms.py` pins it with the docstring *"CURRENT, DOCUMENTED behaviour, pinned so a
  regression is visible either way."*

  Measured latent exposure: **859 tenant-scoped fields across 618 forms** expose rows from more than one
  tenant when `tenant=None`. The proposed plan (needs an owner decision) is an opt-out flag defaulting
  to safe, set on the ~7 forms that rely on layer 2.

  **The practical rule until then: a form reachable WITHOUT a tenant must narrow explicitly**
  (`queryset.none()`), and must not rely on the base class or on a view guard. A view-level guard fails
  *silently* when a view forgets it — which is exactly what happened to
  `ProjectIntegrationConnectorForm` (28 users across 6 tenants, emails, reachable by a superuser through
  an `@login_required`-only view; fixed `2cf76bd4`).
- **Ordering is part of correctness on a monitoring board.** MariaDB sorts NULLs **LAST** under
  `DESC` (opposite of PostgreSQL), so `Meta.ordering = ["-started_at", ...]` hides rows whose
  `started_at` is NULL (e.g. a queued backup). `-id` is free (PK) and NULL-immune;
  `nulls_first=True` over-corrects by floating *every* never-started row above *every* started
  one.

## Taking over a stalled concurrent session

A concurrent session can advance HEAD mid-audit (2026-09-19: `5122585d` → `0ba7f760` in one
session). Re-read `git log` + `git status` *before reporting state*; check whether a phase was
**skipped** rather than queued (7.15's tests were committed, then 7.16 started, silently
skipping 7.15's Phase-7 docs). Judge the uncommitted diff for coherence and **adopt it, never
`git checkout` it away** (back up to `temp/` first). To measure before/after: back up,
`git checkout`, measure, restore, verify the restore.

**Signature of a mid-write death:** a template carrying cp1252 bytes (`0x85`/`0x97`) in
otherwise-UTF-8 output (`get_template()` raises `UnicodeDecodeError`; byte-scan before assuming
truncation), or a directory named after an unexpanded shell variable (literally `$t/`). Damage
is asymmetric — backend + `LIVE_LINKS` commit, then it dies at the first template, so `git log`
looks finished: check the tree against the spec, not the log. Finishing a stalled build is a
review pass, not clerical work (7.10's missing templates exposed 4 real backend defects,
including a url module imported but never concatenated into `urlpatterns`).

## Module ledger

- **Module 7 (projects)** — 7.1–7.17 built/closed; **7.18 in flight** by a concurrent session
  (uncommitted `apps/projects/` + `templates/projects/reporting/`,
  `review-projects-7.18.md`); 7.19 roadmap. Do not disturb its tree.
- **Module 0 (System Admin & Security)** — spans `core`, `accounts`, `tenants`, `dashboard`.
  **0.1–0.15 built; 0.16 Backup/Recovery/Data-Lifecycle built and in close-out (2026-09-23);
  0.17–0.21 unbuilt.** `.claude/skills/core/SKILL.md` exists (added 2026-09-22).
  - Step-0 reconcile COMPLETE (`.claude/tasks/plan-1-module0-reconcile.md`): nothing was
    built-but-unsurfaced; every unmapped bullet was genuinely absent or partial.
    `NavERP.md:90-96`'s "substantially realized" is a claim, not a finding.
  - **Map bullets using the EXACT `NavERP.md` text** (0.2's bullet 5 is
    `Privileged Access Management (PAM)`; without the `(PAM)` suffix it reads as unmapped).
    **Leaving a bullet unmapped is correct when the feature is NOT built** — it renders as the
    roadmap pill it is.
  - Recurring shape: the honest move is almost always *registry + platform config + computed
    monitoring over the real tables*, never a second engine (71 approval models and per-module
    webhooks/templates already exist).
  - **L36 ownership rule:** never re-declare a sibling's spine — point at it with an FK. 0.16's
    bullet 4 collided with `LIVE_LINKS["0.8"]` and was narrowed to legal holds + the archive
    catalogue rather than duplicated.

## `crud()` factory contract (`apps/core/crud.py`)

- Generates 5 standard routes per model.
- `crud_list` context keys are **exactly** `object_list`, `page_obj`, `q` — it does **NOT**
  derive `*_choices` (contract §5.1 wrongly claimed it does; every view passes them via
  `extra_context`).
- `crud_edit` → `{form, obj, is_edit}`; `crud_detail` → `{obj}`.
- **`crud_edit` calls `redirect(success_url)` with no args** — so a pk-taking `_detail` route
  passed as a bare string raises `NoReverseMatch` *after* the row is committed. House convention
  is `success_url=reverse("..._detail", args=[pk])`.
- `crud_create` refuses a tenant-less actor and redirects; both `crud_create` and `crud_edit`
  always pass `tenant=request.tenant`.

## Open plans (`.claude/tasks/`)

- Plans 2/3/4 (+ `plan-remaining-INDEX.md`) — **COMPLETE, re-verified 2026-09-22**: commits
  `c7a9eef4`, `81e7a99d`, `9248505f`, `3db5a589`, `4b088965`, `1962ae89`; README roadmap table
  intact (24 rows 0–23, module 6 a valid row).
- `plan-remaining-5-housekeeping.md` — Item A (`apps/dashboard/tests/`) **landed and green**
  (`32913e28`, `3fc46276`, `33447c3a`, `5c841a3e`; 15 tests, 0 failures). **Item B: the plan was
  WRONG about it** — the two `.log` files are **gitignored/untracked** (`.gitignore:59 *.log`),
  so `git rm` fails and deleting them is NOT recoverable; only `enum-guard-pass.md` is tracked.
  Read-verdict 2026-09-22: `enum-guard-pass.md` is **redundant** (its guard landed in `crud.py`
  as `_enum_values()` + both procurement junk-enum tests corrected + rule in `lessons.md`) and
  the two logs' 20 named failures are **all resolved** (808 tests / 0 failures on the six named
  files) — all three are safe to drop, but the two logs need the user's explicit OK.
  **Item C open**: 14 files still carry a UTF-8 BOM; decision only. Plan + INDEX files corrected
  and committed (`81f971da`, `f45aa614`).
- `plan-remaining-1-module0-submodules.md` — the 6 remaining Module 0 sub-modules (0.16–0.21);
  the biggest item. **0.16 in close-out; 0.17–0.21 remain.**

## Open housekeeping flagged to the user (not actioned)

- Three stray probe tenants on the dev DB — `lane5-empty`, `smoke-empty`, and a nameless
  `SMOKETEST Acme`. **Not deleted** — they are not mine and deletion is destructive.
