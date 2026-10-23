# NavERP — long-term project notes

> **Full detail lives in `PROJECT-NOTES.md`** (same folder) — read it when you need the reasoning
> behind a line here. This file is the always-injected digest and MUST stay short: at 11 KB it was
> being **truncated on injection**, so its tail was silently lost every session. Keep it under ~3 KB.

## Where the rules live — `.claude/` is canonical, never fork a convention
`CLAUDE.md` · `PROMPT.md` · `skills/<name>/SKILL.md` · `agents/` (reviewer/tester/fixer personas) ·
`tasks/` = working memory (`todo.md`, newest plan at TOP; `lessons.md` L-rules;
`research-*`/`review-*`/`contract-*`/`test-contract-*`/`plan-remaining-*`).

## Stack
Django 5.1, **function-based views only**, Tailwind CDN + HTMX, MySQL/MariaDB (`nav_erp`) via XAMPP.
Python only via `venv\Scripts\python.exe`. `models/ forms/ views/ urls/` are packages, one file per
entity; templates `templates/<slug>/<submodule>/<entity>/<page>.html`. Foundation apps (`core`,
`tenants`) use a FLAT layout. **One file per commit** on `main`; **never `git push`**.

## Build state — trust code, not the catalog
`apps/core/navigation.py` `LIVE_LINKS` is the truth for "built"; `NavERP.md`/`README.md` go stale. A
`LIVE_LINKS` entry + committed backend can still be dead. `check`/`makemigrations --check` cannot
see: `showmigrations <app>` (is the last migration **applied**?), `reverse()` per route name,
template-reference count.

## Close-out (Phases 4–7)
**4 Review** (six lanes strictly serial → one `review-<slug>-<N.M>.md` + deduped
`# CONSOLIDATED FINDINGS` with `C#/I#/M#`) → **5 Fix** (one `code-fixer`; re-verify every Critical
with an **independent** probe) → **6 Tests** (`test-contract-*` pinning fixtures FIRST, then
`test_<subslug>_{models,forms,views,security}.py`, one file per commit) → **7 Docs**
(`skills/<slug>/SKILL.md`, README counter, `todo.md`). Final gate = full suite **without**
`--nomigrations`.

## Highest-value traps
- **The test DB is SQLite, not MariaDB.** `pytest.ini` → `config.settings_test` → `sqlite3 :memory:`.
  Never assert a server-specific *mechanism* in a test; assert the outcome. (SQLite also sorts NULLs
  last under `DESC`, so ordering defects still reproduce.)
- Iterate with `--nomigrations` (84–186× faster); keep ONE final run without it.
- **A long run looks like a dead run** — `pytest | tail` buffers all output. Check the process, not
  the silence. Read counts from `--junitxml=` via `xml.etree`.
- **A `ModelForm` refusal is not a database one.** `DataArchive.location` is `blank=False` but the
  column accepts `""` and the seeder writes it. Fixture helpers take a `_validate=` escape hatch for
  the deliberately-invalid states, or they cannot build the row under test.
- **`created_at` is `auto_now_add`** — a past-expiry or aged row can only be built by creating it and
  then `.update()`-ing the timestamp.
- **A dirty tree at session start is NOT yours (L45)** — never commit it.
- **`unique_together` containing `tenant` is NEVER validated by a `ModelForm`** → IntegrityError 500
  on create *and* edit. Guard with `clean_<field>` scoped to `self.tenant`.
- **Never parallel-`Edit` the same file** — edits race and lose updates.
- A rate-limited agent may have **already committed** work — re-read `git log` before re-running it.
- Probe the EMPTY state and junk params, not just the happy path.
- **Your own probe can be wrong** — verify its inputs before believing a failure. A count computed
  by subtraction double-counts rows satisfying two OR'd conditions.
- `manage.py shell < file.py` cannot run indented blocks — run `temp/` scripts as plain files.
- `response.context` is `None` in a bare script without `setup_test_environment()`.
- `User.objects.create_user()` here **requires `email`**.

## Security shapes
- **405 for a wrong method regardless of role** (7.7's ruling): put `require_POST` ABOVE the role
  gate (decorators apply bottom-up).
- No `.alert-*` classes exist in `theme.css`. Notices are `<p class="text-muted">` (`.text-warn`,
  `.text-ok`, `.text-danger`, `.text-brand`); badges are colour-named only.
- `AuditLog.action` is `varchar(10)` and `.create()` never validates `choices` — put the verb in
  `changes`. 25 sites still violate this.
- Use `|escapejs` for user text in an `onsubmit` handler (L42). Never fork the upload allow-list —
  import and extend `core.forms.ALLOWED_DOC_EXTENSIONS`.
- **A green badge is an ACTIVE REASSURANCE and must be earned** — pass `None` when the denominator
  is zero and name it "not applicable". 0.8: *"Reporting 0 here would be a false all-clear."*
- **`TenantModelForm` scoping is a shared seam (619 subclasses) and a KNOWN, OPEN issue.** The base
  class deliberately leaves a queryset unnarrowed when `tenant=None`, so `_reject_foreign` can return
  its precise "belongs to another workspace" message. Changing that broke 15 tests in three modules and
  was reverted — **do not re-try it without the owner's decision.** Measured exposure: 859
  tenant-scoped fields across 618 forms. **A form reachable WITHOUT a tenant must narrow explicitly**
  (`queryset.none()`), because a view-level guard fails silently when a view forgets it.
- **MariaDB sorts NULLs LAST under `DESC`** (opposite of PostgreSQL), so ordering on a nullable
  column can hide the newest work. `-id` is free and NULL-immune.
- No delete path erases bytes — Django never unlinks a `FileField` on row delete.

## Module ledger
- **Module 7 (projects)** — 7.1–7.17 closed; **7.18 in flight** by a concurrent session. Do not
  disturb its tree.
- **Module 0** (`core`, `accounts`, `tenants`, `dashboard`) — 0.1–0.15 built; **0.16 closed
  2026-09-25** (26 fixes + 266 tests + docs); **0.17–0.21 unbuilt**. Recurring shape: *registry +
  platform config + computed monitoring over the real tables*, never a second engine. **L36:** never
  re-declare a sibling's spine — point at it with an FK.

## Open plans
- Plans 2/3/4 + INDEX — **COMPLETE** (re-verified 2026-09-22).
- `plan-remaining-5-housekeeping.md` — Item A landed/green; **Item B** (two gitignored `.log` files)
  needs the user's explicit OK before deletion; **Item C** (14 BOM files) is a decision only.
- `plan-remaining-1-module0-submodules.md` — **0.16 in close-out; 0.17–0.21 remain.**
