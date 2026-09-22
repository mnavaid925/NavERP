# Review — Module 0 sub-module **0.15 Localization & Regional Settings** (`core`)

**BASE:** `35cde520` · **Changeset:** 22 files, ~1800 insertions · **Opened:** 2026-09-22
**Contract:** `.claude/tasks/contract-core-0.15.md` · **Research:** `.claude/tasks/research-core-0.15.md`

Six reviewers run **strictly serially**. Each lane's section is appended verbatim as it reports, followed by
an **Orchestrator verification** block recording whether I reproduced its load-bearing claims. Lane-local ids
(`L1-C1`) are canonicalised to `C#/I#/M#` only in the consolidated block at the foot of this file.

**Reviewer order:** `code-reviewer` → `explorer` → `frontend-reviewer` → `performance-reviewer` →
`qa-smoke-tester` → `security-reviewer`.

**Sanity-checks given to every lane** (already found and fixed before review — a lane reporting one as *new*
is reporting a stale claim, not a defect): the board's `base_currency` context key; `@require_POST` above
`@tenant_admin_required` on `statutory_rule_delete`; per-entity seeder guards; `_seed_localization_globals()`
called once outside the tenant loop.

---

## Lane 1 — `code-reviewer`

## Verdict
Safe to commit after fixing the one Important finding — the member-facing save flow lands on a 403. No Critical, no cross-tenant, no schema gap. All four "already fixed" sanity checks are genuinely fixed.

## Critical
None. I specifically probed and cleared: no cross-tenant read/write (`crud_*` and both hand-written singletons all filter `tenant=request.tenant`); `Language`/`TimeZone` are correctly global per the `accounting.Currency` precedent (`apps/core/models/Localization.py:58,87`); `StatutoryRule.tax_code` is tenant-scoped by `TenantModelForm` because `TaxCode` carries a `tenant` field (`apps/core/forms/_common.py:52-55`, verified against `accounting/models/Tax/TaxCodes.py:6`); migration `0012` exists and `makemigrations core --check --dry-run` reports "No changes detected in app 'core'".

## Important
1. `apps/core/views/Localization.py:148` — `user_locale_edit` is `@login_required` (a plain member is a supported actor, per the contract), but a successful save redirects to `core:localization_overview`, which is `@tenant_admin_required` → the member who just saved their own preferences is POST-redirected straight to a **403**. The sibling member-facing page in the same app does the opposite: 0.12's `my_preferences` redirects to itself (`apps/core/views/Notification.py:240`) precisely so a member stays on a page they can reach. Fix: redirect to `core:user_locale_edit` (or `dashboard:home`). *I'm unsure only between Important and Critical — it is a broken mainline path for a supported role, not a crash or a bypass, so I graded it Important.*

## Minor
1. `templates/core/userlocale/form.html:7,10,32` — same root cause as above, on the template side: the breadcrumb "Localization" link, the "Overview" action and the "Cancel" button all target the admin-gated `core:localization_overview`. For a member, "Cancel" is a dead end that 403s. Fix: point them at a member-reachable page (the page itself, or `dashboard:home`).
2. `templates/core/language/list.html:10-11` (clone at `templates/core/timezone/list.html:10-11`) — these two lists are `@login_required` (member-reachable by design), yet both page-action buttons ("Board" → `core:localization_board`, "Regional settings" → `core:locale_profile_edit`) are `@tenant_admin_required`, so every affordance on the page 403s for a member. This breaks the house pattern: member-reachable pages elsewhere offer only member-reachable actions (e.g. `party_list` → `party_create` is member-allowed, asserted by `apps/core/tests/test_security.py:71-78`). Clone-family grep: `grep -rn "page-actions" -A 3 templates/core/*.html | grep "localization_board\|localization_overview\|locale_profile_edit"` finds exactly these three templates.

## Done well
The four sanity checks hold up under probe, not just on paper: `base_currency` is genuinely in the board context (`views/Localization.py:217`) and used (`localizationboard.html:19`); `@require_POST` really is the outermost decorator on `statutory_rule_delete` (`views/Localization.py:191-193`) so a member's GET is 405; `_seed_localization` uses two independent per-entity guards (`seed_core.py:743,767`) rather than a tenant-wide guard; and `_seed_localization_globals()` is called exactly once, before the tenant loop (`seed_core.py:89`). The seeder's decision to match the tax code by `tax_type` instead of `.first()` (`seed_core.py:773-774`) is a real correctness improvement over the contract's literal wording — an arbitrary `.first()` would have attached the EU e-invoicing rule to a US sales-tax code.

## Suggested tests
- `apps/core/tests/test_views.py` — `user_locale_edit` POST as a **non-admin member** must redirect somewhere that returns 200 for that member (this is the regression test for the Important finding); and the same for the `language_list`/`timezone_list` page-action targets.
- `apps/core/tests/test_views.py` — `statutory_rule_detail` / `_edit` / `_delete` cross-tenant → 404, mirroring the existing `TestMultiTenantIDOR` class; plus `statutory_rule_create` sets `tenant` from the session, not from POST.
- `apps/core/tests/test_security.py` — `statutory_rule_delete` GET as a member → **405** (not 403), locking in 7.7's decorator-order ruling.
- `apps/core/tests/test_models.py` — `StatutoryRule.clean()` rejects `effective_to < effective_from` and rejects `e_invoicing_required=True` with `e_invoicing_scheme="none"`; `LocaleProfile.clean()` rejects a format pattern containing a disallowed character.
- `apps/core/tests/test_views.py` — `language_list` and `timezone_list` return 200 for a tenant-less superuser (`request.tenant is None`), and are **not** tenant-filtered (a row created with no tenant is still visible).
- Seeder idempotency: `seed_core` twice creates no second `Language`/`TimeZone`/`LocaleProfile`/`StatutoryRule` row.
- Note: the diff ships **zero** tests, and `grep -rl "LocaleProfile\|StatutoryRule" apps/core/tests/` returns nothing — the existing suite is generic and does not cover 0.15's five models, eleven routes or the two global lists.

## Routing
- performance-reviewer: `_fx_rows` (`views/Localization.py:56-58`) materialises **every** `ExchangeRate` row for the tenant into Python to dedupe to the newest-per-currency — fine for seed data, unbounded once a tenant has years of daily rates; and `localization_overview` fetches the same `LocaleProfile` row twice (`.first()` at line 251 and `.exists()` at line 252) where `bool(profile)` would do.
- frontend-reviewer: the member-reachable pages' action affordances (Minor 1 and 2 above) — whether the house rule is "hide what 403s" or "route members to a member page".
- security-reviewer: none — I found no cross-tenant read/write, no missing tenant FK, no unscoped form queryset and no secret surfaced through a form or `messages`.

### Orchestrator verification — lane 1

**Reproduced independently** with `temp/probe_15_member_flow.py` (scratch, run against the real DB), not by
re-reading lane 1's reasoning:

```
member = smoke_leaver | is_tenant_admin = False
  GET user_locale_edit     -> 200      <-- the page IS member-reachable
  GET language_list        -> 200
  GET timezone_list        -> 200
  POST user_locale_edit    -> 302  Location=/core/localization/
  GET  /core/localization/ -> 403      <-- CONFIRMED dead end
  GET  localization_board    -> 403
  GET  locale_profile_edit   -> 403
  GET  localization_overview -> 403
  POST my_preferences -> 302 Location=/core/notifications/my-preferences/
  GET  that location  -> 200           <-- 0.12's precedent: redirect to ITSELF
```

- **L1-I1 — CONFIRMED, severity upheld as Important.** The member's own preference save lands on a 403.
  Lane 1 flagged its own uncertainty between Important and Critical; I agree with **Important** and not
  Critical: it is a broken mainline path for a supported role, but it neither crashes, corrupts data, nor
  bypasses authorization (the member is correctly *denied*). It is a UX dead end, not a security hole.
  The 0.12 precedent lane 1 cited is real — `my_preferences` redirects to itself and returns 200.
- **L1-M1 — CONFIRMED**, same root cause, template side.
- **L1-M2 — CONFIRMED.** All three page-action targets (`localization_board`, `locale_profile_edit`,
  `localization_overview`) return 403 for a member while the hosting pages return 200.
- **Lane 1's "Done well" claims — independently confirmed.** My own smoke probe (`temp/smoke_15.py`) had
  already exercised `base_currency` (board renders the currency row), the decorator order (member GET →
  405, not 403), and the seeder (two runs, second creates nothing). Lane 1 and the smoke probe agree.
- **No Critical missed by me, and none filed.** Lane 1's cleared list matches my own read of the code.
- **Carried, not folded in:** the `_fx_rows` materialisation concern is genuinely a performance question,
  not a correctness one, and is routed to lane 4 rather than fixed here.

---

## Lane 2 — `explorer` (referential integrity)

**BASE** `35cde520` · **HEAD** `8df00fa2` · 23 files changed (20 code/config + 3 `.claude/tasks/*.md`)
Method: `django.setup()` introspection + `reverse()`/`get_template()` probes + static template-variable extraction + `manage.py check` + `makemigrations --check` + read-only ORM queries. No file written, no migration/seeder run.

### Verdict
The referential spine of 0.15 is **sound** — every re-export resolves to its claimed module, all 11 routes ↔ views ↔ templates form a closed triangle, every `{% url %}` in the 9 templates resolves under the right namespace, the template paths follow the foundation-app convention, `LIVE_LINKS["0.15"]` matches the NavERP.md bullets character-for-character, and there are **no orphans in either direction**. One **Important** cross-tree defect: the new seeder's peer-app FK resolution cannot be satisfied under the repo's own documented seed order, and its guard makes that permanent.

---

### Critical
None.

### Important

**L2-I1 — `seed_core`'s 0.15 FKs can never be populated on a fresh install; the per-entity guard freezes them NULL.**
`apps/core/management/commands/seed_core.py:749,753` reads `accounting.Currency` and `:765,769,770` reads `accounting.TaxCode` — but `seed_accounting` is the **sole creator** of both (`apps/accounting/management/commands/seed_accounting.py:94` for `Currency`, `:376,379` for `TaxCode`; no data migration creates either), and it cannot run first: `seed_accounting.py:96-98` bails with *"No tenants found — run `seed_core` first."* The documented order is therefore structurally `seed_core → seed_accounts → seed_tenants → … → seed_accounting` (`README.md:864-874`, restated at `seed_core.py:5` and `.claude/tasks/qa-smoke-tester.md:18`).

On a fresh DB that order makes every lookup `.first()` → `None`:
- `LocaleProfile.base_currency = None` (`seed_core.py:753`)
- all three `StatutoryRule.tax_code = None` (`seed_core.py:780`)

and the guards at `seed_core.py:748` / `:764` are `if not <Model>.objects.filter(tenant=tenant).exists()` — so re-running `seed_core` after `seed_accounting` **does not repair the links**, because the rows already exist. The 0.15 verification gate (`seed_core` ×2, `.claude/tasks/todo.md`) passes on the dev DB only because accounting data pre-existed there — my read-only query confirms the current DB is correctly linked (`LocaleProfile.base_currency_id=1`; rules `tax_code_id=21/22/23/24`), so this is **latent, not present**.

User-visible on a fresh install: `localizationoverview.html:20` and `localizationboard.html:19` render "Base currency: **Not set**"; `statutoryrule/list.html:50` renders "—" and `detail.html:25` renders "No rate attached — a pure reporting obligation" for the very rule the seeder deliberately matched by `tax_type` so that, in its own words (`seed_core.py:767-768`), *"the FK is only meaningful if it names the right rate."*

Fix direction (not applied): have `_seed_localization` backfill a NULL link on re-run rather than skip the whole entity, or move the two FK resolutions out of the guard, or drop the peer-app FK from the seeder. This is also the **first** time `seed_core` reaches into another app's rows (only two `django_apps.get_model` call sites, both added by 0.15), so the coupling is new.

### Minor

**L2-M1 — context keys supplied but never consumed (dead context, 3 sites).**
`views/Localization.py:216` passes `"profile"` to the board, but `localizationboard.html` never references `profile` (it uses the derived `base_currency`); `views/Localization.py:125` passes `obj` + `is_edit` to `localeprofile/form.html` and `:151` passes `obj` to `userlocale/form.html`, and neither template references either name. Harmless — the reverse direction (used-but-unsupplied) is what would render blank, and there is **no** instance of that.

**L2-M2 — pinned contract doc drifted from the code it pins.**
`.claude/tasks/contract-core-0.15.md:197` records `rtl_choices=[("True","RTL only"),("False","LTR only")]`; the code ships `[("True","Right-to-left"),("False","Left-to-right")]` (`views/Localization.py:82`). The doc has an `AS-BUILT CORRECTION` convention (§2 at line 147, §3.2 at line 217) but no entry for this one. Doc-only; no runtime effect.

**L2-M3 — one premise in the sweep brief is misattributed (record correction).**
The brief states `localeprofile/form.html` links to `accounting:tax_code_list`. In the tree that link is at `templates/core/statutoryrule/list.html:10`; `localeprofile/form.html` links only to `core:localization_board`, `core:localization_overview`, `dashboard:home`. Both `accounting:tax_code_list` → `/accounting/tax-codes/` and `accounting:exchange_rate_list` → `/accounting/exchange-rates/` resolve. No defect — flagging so the consolidated record isn't wrong.

---

### Checked and clean

**1. Re-export completeness — clean.** Imported `apps.core.{models,forms,views}` and introspected: all 5 models, 3 forms and 11 views are present, and each object's `__module__` is exactly `apps.core.{models,forms,views}.Localization` (`models/__init__.py:104-110`, `forms/__init__.py:81-85`, `views/__init__.py:238-250`). Nothing in those blocks is a stale name; nothing declared in `Localization.py` is missing from the block (`FORMAT_TOKEN_RE` is internal and unreferenced elsewhere, correctly not re-exported). No name collision with the `_base` star-import.

**2. URL ↔ view ↔ template triangle — clean.** All 11 routes reverse (`core:localization_overview` `/core/localization/`, `…/board/`, `…/languages/`, `…/time-zones/`, `…/profile/`, `…/my-settings/`, `…/statutory/`, `…/statutory/add/`, `…/statutory/<pk>/`, `…/<pk>/edit/`, `…/<pk>/delete/`); literal segments precede `<int:pk>` in every case (`urls.py:187-202`). All 9 view-rendered template paths exist **at the exact path** via `get_template()` (`core/language/list.html`, `core/timezone/list.html`, `core/localeprofile/form.html`, `core/userlocale/form.html`, `core/statutoryrule/{list,form,detail}.html`, `core/localizationboard.html`, `core/localizationoverview.html`).

**3. Template ↔ context contract — clean.** Extracted every `{{ }}` and every `{% if/elif/for %}` name from all 9 templates and matched against each view's dict / `crud_list`'s pinned contract. Every name is supplied: the two global lists take `object_list`/`page_obj`/`q` from `crud_list` plus their `*_choices` from `extra_context` (`views/Localization.py:82-83,97-98,163-164`); `statutoryrule/*` take `obj`/`form`/`is_edit` from `crud_detail`/`crud_create`/`crud_edit`; the two computed pages match §3.3/§3.4 of the contract key-for-key, including `base_currency`, `rate_rows[].{currency,rate,rate_date,source,age_days}`, `stale_after_days`, `exchange_rate_url`, `tax_code_url`, `has_profile`, `my_pref`, `recent_rules`, `user_pref_count`. `request.GET.*` comes from the enabled `django.template.context_processors.request` (`config/settings.py:81`). No used-but-unsupplied variable anywhere.

**4. `{% url %}` name existence — clean.** Every url tag in the 9 templates reverses under the right namespace, including the three the brief called out: `language/list.html:10` + `timezone/list.html:10` → `core:localization_board`; `language/list.html:11` + `timezone/list.html:11` → `core:locale_profile_edit`; `statutoryrule/list.html:10` → `accounting:tax_code_list`. A tree-wide grep for `core:language_list|core:timezone_list|core:localization*|core:locale_profile_edit|core:user_locale_edit|core:statutory_rule*` finds **only** these 9 templates plus `navigation.py:215-221` and the redirects/success_urls in `views/Localization.py:121,148,172,185,195` — no other file in `templates/` or `apps/` references a 0.15 route, so there is no dangling pre-existing reference.

**5. Template path convention — clean.** Foundation-app shape honoured: 7 files at `templates/core/<entity>/<page>.html` (`language/`, `timezone/`, `localeprofile/`, `userlocale/`, `statutoryrule/`) and 2 computed pages at the app root (`localizationboard.html`, `localizationoverview.html`), matching the existing `privacyoverview.html` / `configoverview.html` / `workflowoverview.html`. **No banned flat `<entity>_<page>.html` was created** — the `templates/core/` listing contains only directories and the established `*overview.html`/`*board.html` root pages.

**6. Sidebar wiring — clean.** `LIVE_LINKS["0.15"]` exists (`navigation.py:214-222`). Its 7 targets all reverse. The 5 bullet keys are **byte-identical** to the NavERP.md bullets at lines 223-227 — verified by parsing `NavERP.md` with the real `parse_catalog()`: `bullets with NO live link: []`, and the only non-bullet keys are `Localization Overview` + `My Regional Settings`, the same "# extra" convention every other built sub-module uses (0.1, 0.4, 0.8, 0.10-0.14, …). This matters because `resolve_nav` (`navigation.py:2198-2208`) silently drops an unmatched key and silently appends an unknown one — a typo would have produced a missing link with no error.

**7. Orphan sweep — clean, both directions.** Every new symbol has a consumer: all 3 forms are called by views; all 11 views are named in `urls.py`; all 5 models are used by views + admin + seeder; `STALE_RATE_DAYS` and `_fx_rows` are used in the board; `FORMAT_TOKEN_RE` is used by both `clean()` methods. Nothing referenced-but-undefined: `apps/core/admin.py` imports all 5 models (and admin autodiscovery runs inside `django.setup()`, so a missing name would have raised) — `admin.site._registry` confirms all 5 registered; `seed_core.py` imports `Language, LocaleProfile, StatutoryRule, TimeZone` and `django_apps` and uses each. No duplicate `class Language/TimeZone/LocaleProfile/StatutoryRule/UserLocalePreference` anywhere in `apps/`.

**Also verified clean (beyond the brief):**
- `manage.py check` → **0 issues**, which validates every `list_display` / `list_filter` / `search_fields` / `readonly_fields` entry on the 5 new `ModelAdmin`s against the real models.
- `makemigrations --check --dry-run` → **"No changes detected"**; `core.0012`'s `dependencies` name `accounting.0005_invoice_recurring_invoice`, which is accounting's latest migration and postdates the `Currency`/`TaxCode` `CreateModel` in 0001/0002 — the FK targets exist before 0012 runs.
- Every `search_fields` / filter lookup the views pass exists on its model (`Language`: `code,name,native_name` / `is_rtl,is_active`; `TimeZone`: `name,label` / `observes_dst,is_active`; `StatutoryRule`: `name,jurisdiction,statutory_report,notes` / `e_invoicing_scheme,is_active`) — a bad name here would 500 on search, not blank.
- Every `crud_list` filter param name matches the `<select name="…">` in its template (`rtl`/`active`, `dst`/`active`, `scheme`/`active`).
- `Currency.name` exists (`accounting` `Currency` fields include `code, name, symbol, is_active`), so `localizationboard.html:43` renders; `ExchangeRate.get_source_display()` is valid (`source` choices `manual|feed`); `TaxCode.tax_type` choices are `sales|vat|gst|use`, so the seeder's `"vat"`/`"sales"` filters are real values.
- `statrule_tenant_active_idx` is unique across the tree (25 chars, under the 30-char cross-backend limit); no duplicate index name.
- `partials/pagination.html` needs only `page_obj` + `request.GET` — both supplied; the list templates' `<div>` nesting matches the house pattern exactly (`party/list.html` tail is structurally identical).
- All icons used are standard lucide names served from the full CDN bundle (`base.html:29` `lucide@latest`), so the lone `data-lucide="languages"` (`language/list.html:56`) resolves.
- `core` still ships **no 0.15 tests** — `grep -rl "LocaleProfile\|StatutoryRule\|localization\|0\.15" apps/core/tests/` returns nothing (lane 1 already filed this; recorded here as a cross-check, not a new finding).

### Orchestrator verification — lane 2

**L2-I1 — CONFIRMED, and it is the sharpest finding of the two lanes so far.** I reproduced the premise
independently rather than accepting the reasoning:

```
$ grep -n "No tenants found" apps/accounting/management/commands/seed_accounting.py
97:        tenants = list(Tenant.objects.all())
99:            self.stdout.write(self.style.WARNING("No tenants found — run `seed_core` first."))

$ grep -rn "Currency.objects.*create\|TaxCode.objects.*create" apps/*/management/commands/*.py
apps/accounting/.../seed_accounting.py:94   Currency.objects.get_or_create(...)
apps/accounting/.../seed_accounting.py:376  TaxCode.objects.create(...)
apps/accounting/.../seed_accounting.py:379  TaxCode.objects.create(...)
apps/crm/.../seed_crm.py:404                Currency.objects.get_or_create(...)
```

So `seed_accounting` (a) is the only creator of both peer-app masters, and (b) explicitly requires
`seed_core` to have run first. The dependency is therefore **circular in the documented order**, and lane 2
is right that the per-entity guard makes the resulting NULLs permanent. I also confirm lane 2's own scoping
check: the current dev DB *is* correctly linked, so this is latent, not live — which is exactly why the
`seed_core` ×2 gate in `todo.md` passed. **Severity upheld as Important**, not Critical: no crash, no
cross-tenant exposure, no data loss — a fresh install simply renders a configuration page that says
"Not set" for the two things the sub-module exists to show. The fix belongs in `_seed_localization`
(backfill a NULL link on re-run), not in the schema.

- **L2-M1 — CONFIRMED** (dead context keys; harmless direction).
- **L2-M2 — CONFIRMED**, doc-only drift in the contract I wrote. Fix the contract.
- **L2-M3 — CONFIRMED, and the error was MINE, in the brief I handed lane 2**, not in the code. I wrote that
  `localeprofile/form.html` links to `accounting:tax_code_list`; the link is actually in
  `statutoryrule/list.html:10`. Lane 2 corrected the record instead of filing a phantom finding — the
  behaviour I want from a lane. **Recorded as an orchestrator error, no code action.**
- **Lane 2's seven "checked and clean" sections are the most valuable part of this lane** and are the reason
  the explorer runs second: the re-export blocks, the 11-route triangle, the byte-identical `LIVE_LINKS` keys
  and the orphan sweep in both directions are exactly the classes of defect a per-file diff read cannot see.
  I spot-checked two of them myself (the `LIVE_LINKS` keys via `parse_catalog()`, and `get_template()` on all
  nine paths) and they hold.

---

## Lane 3 — `frontend-reviewer`

**Verdict: REQUEST CHANGES.** Design-system compliance is genuinely clean (every modifier class resolves; the L33 badge/stat-icon regression has *not* recurred), the comment-leak guard is clean, pagination/CSRF/None-safety are clean, and all 9 pages render 200 as admin. Two real problems: a member-facing navigation dead-end on `userlocale/form.html`, and the timezone offset column printing raw minutes. Plus a detail page that is the only one of 18 missing its Back-to-list link.

I rendered every page (admin **and** member) with the smoke harness plus an inline member probe.

---

### Critical

**L3-C1 — `templates/core/userlocale/form.html:7,10,15,32` — every affordance on a member's own settings page 403s, including "Cancel".**
`user_locale_edit` is `@login_required` (`apps/core/views/Localization.py:129`), so a plain member can reach this page. Verified with a real member login (`member: leaver@acme.example`): the page renders 200, and *every* in-page link targets an `@tenant_admin_required` view:
- `:7` breadcrumb `<a … core:localization_overview>Localization</a>` → 403
- `:10` page-action "Overview" → `core:localization_overview` → 403
- `:15` body link "Regional Settings" → `core:locale_profile_edit` → 403
- `:32` **"Cancel"** → `core:localization_overview` → 403

A Cancel control that returns 403 is unambiguously wrong: the member's only in-page exit is the browser Back button.
**Fix (house pattern — see the rule below):** `:7` make the crumb a plain `<span>Localization</span>`; `:10` empty the `.page-actions` (exactly `templates/core/my_preferences.html:9-10`); `:15` make "the workspace's regional settings" plain text; `:32` point Cancel at `{% url 'dashboard:home' %}` or drop it (`my_preferences.html:45-47` ships Save only).

---

### Important

**L3-I1 / L3-I2 — `templates/core/language/list.html:10-11` and `templates/core/timezone/list.html:10-11` — both page-action buttons 403 for a member.**
These two registries are `@login_required` **by design** (they must work for the tenant-less superuser) and are the only 0.15 pages a member can open. Verified on the member render: the page contains `<a href="/core/localization/board/">Board</a>` and `<a href="/core/localization/profile/">Regional settings</a>`, and `core:localization_board` / `core:locale_profile_edit` both return **403** for that member. **Fix:** drop "Board" (there is no member-reachable board) and re-point "Regional settings" at `{% url 'core:user_locale_edit' %}` — which *is* `@login_required` and is the member's own equivalent — or empty the `.page-actions` like `my_preferences.html`.

**L3-I3 — `templates/core/timezone/list.html:44` (header) / `:50` (value) — the offset column prints raw minutes under a header with no unit.**
Rendered values: `Europe/London → UTC+0`, `Asia/Kolkata → UTC+330`, `Asia/Tokyo → UTC+540`, `America/Los_Angeles → UTC-480`. `utc_offset_minutes` is a **minutes** integer, so "UTC+330" reads as 330 hours — the opposite of the clarity the model docstring (`apps/core/models/Localization.py:91-94`) asks for. A template cannot format this cleanly; add a `TimeZone.offset_display` property (e.g. `UTC+05:30` / `UTC-08:00`) and render that. (Route the model change to the code lane.)

**L3-I4 — `templates/core/statutoryrule/detail.html:39` — missing "Back to list"; the only core detail page without one.**
17 of 18 `templates/core/*/detail.html` carry `<a … class="btn btn-outline"><i data-lucide="arrow-left"></i> Back to list</a>` as a trailing element after the last card (e.g. `party/detail.html:27`, `mapping/detail.html:45`, `dsar/detail.html:76`). `statutoryrule/detail.html` has `grep -c Back = 0` and ends at `</div>` → `{% endblock %}`. The Edit + POST-Delete pair in `.page-actions:9-15` is correct and matches `party/detail.html:9-15`; only the trailing link is absent. **Fix:** append `<a href="{% url 'core:statutory_rule_list' %}" class="btn btn-outline"><i data-lucide="arrow-left"></i> Back to list</a>` after line 39.

---

### Minor

**L3-M1 — `templates/core/localeprofile/form.html:10`, `statutoryrule/form.html:10`, `userlocale/form.html:10` — the three new forms are the only core forms with a page-action.**
`grep arrow-left` across all 43 `templates/core/**/form.html` returns exactly these three files. The closest sibling, `ratelimit/form.html:9-10`, ships an **empty** `.page-actions`. A back affordance is harmless-to-helpful, so this is only a note that the house form norm is a bare header — but for `userlocale/form.html` it is the L3-C1 defect, not a style choice.

**L3-M2 — `templates/core/localizationoverview.html:98-101` — the closing "What this sub-module does NOT do" paragraph is a five-clause run-on, and it repeats `localizationboard.html:16` verbatim.**
The *content* is right and matches the 0.13 precedent (`integrationoverview.html:62-67`, `integrationboard.html:93-95`). But this block packs "does not translate / does not fetch / does not convert / does not transmit" into one 6-line sentence, and "Nothing on this page is stored — the counts are derived on read" is word-for-word the sentence on `localizationboard.html:16`, one click away. **Fix:** convert the block to a short `<ul>` (four bullets), and let the board keep the "nothing is stored" line while the overview drops it.

**L3-M3 — `templates/core/timezone/list.html:51`, `templates/core/language/list.html:51` — `badge-amber` used for a neutral registry fact.**
"Observes DST" and "Right-to-left" are facts, not warnings, yet amber is the attention colour (it is used for genuinely actionable things at `localizationboard.html:21,22,28`). Valid classes both — no styling bug — but `badge-slate` or `badge-info` would read as neutral. Low priority; the palette is officially colour-named only.

---

### The member-affordance house rule (the question routed to me)

**Rule: an affordance rendered to a member must resolve for a member. Route it to a member-reachable page where one exists; hide it where none does. Never ship a visible control whose only outcome is 403.** The house precedent supports exactly this, and does it both ways:

- **Hide** — `templates/core/my_preferences.html:9-10` ships a deliberately **empty** `.page-actions`, and `:7` breadcrumbs `NavERP › My Notification Preferences` with **no** link to the admin-gated `core:notification_overview`, even though 0.12 has one. The rationale is written down at `apps/core/navigation.py:93-94`: *"`My Preferences` is deliberately NOT admin-gated — a preference a member cannot set is an admin setting with a different label."* The author went out of their way to make the member page self-contained.
- **Route** — `templates/core/party/list.html:10` (member-reachable: `Party.py:17-18` `@login_required`) points "New Party" at `core:party_create`, which is *also* `@login_required` (`Party.py:28-29`). Same for `templates/core/activity/list.html:10` → `core:activity_create` (`Activity.py:35-36`). No affordance on either page points at an admin-gated view.
- **The one counter-example, and why it isn't a licence:** the sidebar. `apps/core/navigation.py` has no role filter (grep for `is_tenant_admin|is_superuser` returns comments only) and `templates/partials/sidebar.html` has none either, so the member render of `language_list` already contains 11 `/core/localization/` links — `localization/board/` ×2, `localization/profile/` ×2, `localization/statutory/` ×1 — several of which 403. That is a **pre-existing, app-wide** condition affecting every admin-gated sub-module, not a 0.15 defect, and I am not filing it here. But "the sidebar does it too" does not justify adding more dead controls to a page's own chrome, which is where the author has consistently followed the rule.

**So: three templates change.** `language/list.html:10-11` and `timezone/list.html:10-11` (re-point "Regional settings" → `core:user_locale_edit`, drop "Board"), and `userlocale/form.html:7,10,15,32` (plain-text crumb, empty actions, plain-text body reference, Cancel → `dashboard:home`). `localeprofile/form.html` is admin-gated, so its "Overview" action is legitimate and needs no change.

---

### Checked and clean

- **Design-system classes (L33 / L13) — clean.** Ran the required `grep -oE '\.(badge-[a-z]+|stat-icon(\.[a-z]+)?|text-[a-z]+)' static/css/theme.css | sort -u` → `badge-{green,red,amber,info,muted,slate,group}`, `stat-icon.{blue,green,orange,purple,red,slate}`, `text-{brand,danger,muted,ok,red,right,warn}`. Then extracted **every** `class="…"` token from all 9 new templates and diffed against every selector in `theme.css`: **40 tokens, 0 missing.** No `badge-success`/`badge-danger`, no `.alert*`, no invented utility. `text-warn` (board:30, overview:98) and `text-muted` are both real. The palette regression has not recurred.
- **Comment leak (L2) — clean.** No `{#` in any of the 9 templates; smoke leak-marker scan reports `clean` on all five checked pages.
- **Badge fallbacks — clean.** Every badge is a boolean test with an `{% else %}`: `language/list.html:51,52,53`; `timezone/list.html:51,52`; `statutoryrule/list.html:51,53`; `statutoryrule/detail.html:26,31`; `localizationboard.html:19,21,22,28,47`; `localizationoverview.html:18,24,87`. No badge tests a CHOICES value here (the only enum, `e_invoicing_scheme`, is shown via `get_…_display`), so there is no unguarded enum branch and no all-one-colour redundancy.
- **Pagination (L9) — clean.** All three lists delegate to `partials/pagination.html`, which guards `has_previous`/`has_next` and preserves all GET params. `?page=999` on `language_list` → 200.
- **CSRF — clean.** Every POST form carries `{% csrf_token %}`: `statutoryrule/list.html:59`, `detail.html:12`, `form.html:16`, `localeprofile/form.html:17`, `userlocale/form.html:17`.
- **Structure / div balance — clean.** Card nesting matches `ratelimit/list.html` exactly (the `.table-wrap` is a sibling of `.card-body` inside `.card`, closed by the final `</div>`); I balanced all 9 files. Delete is a POST form with `onsubmit="return confirm(…)"` in both list and detail.
- **Filter bars (L9/L11) — clean.** `q` + FK/status `<select>`s re-select from `request.GET`, `|stringformat:"d"` is not needed (no pk filters), and junk values are safe: `?rtl=abc`, `?dst=nope&active=maybe`, `?scheme=zzz` all → 200 (boolean map + enum guard in `crud.py:160-179`).
- **URLs — clean.** All 12 names used resolve; `accounting:tax_code_list` → `/accounting/tax-codes/` and `accounting:exchange_rate_list` → `/accounting/exchange-rates/` both reverse, and the board's `{{ exchange_rate_url }}` / `{{ tax_code_url }}` hrefs are correct.
- **None-safety (L10) — clean.** `obj.tax_code`, `obj.language`, `obj.time_zone`, `row.currency`, `profile` are all guarded by `{% if %}` before any attribute access; nullable FKs render `—`.
- **Accessibility / responsive — clean.** Search inputs carry `aria-label="Search"`; icon-only buttons carry `title` (matching `party/list.html:44-48`); tables wrapped in `.table-wrap`; inline `style="flex:1; min-width:200px;"` on the search group is copied verbatim from `ratelimit/list.html:18`.
- **Read-only communication (per your context) — clean.** `language/list.html:16` and `timezone/list.html:16` both state "global registry … the page is read-only and there is no 'add' button". The read-only state is communicated; I am not filing the absent CRUD as a defect.
- **Readability of the computed pages (your item 4).** The disclaimers read as **useful honesty, not noise** — they are in-house style (`integrationboard.html:28,91-97`, `integrationoverview.html:59-69`) and they pre-empt the two real misreadings ("this translates the UI", "rates refresh themselves"). The `dl.detail-grid` layouts are legible: `localizationboard.html:18-29` (10 items) and `localizationoverview.html:17-30` (12 items) sit in `repeat(auto-fit, minmax(240px,1fr))` with short uppercase `<dt>` labels. Only the two notes at L3-M2 apply.
- **Structure (flat foundation-app layout).** `templates/core/language/list.html`, `…/statutoryrule/detail.html`, and computed pages at the app root are the correct shape for a foundation app; no banned `<entity>_<page>.html` inside a module.
- **Dark mode / RTL.** No raw Tailwind colour utilities in the new templates (theme classes only), so no missing `dark:` variants; no hard-coded left/right. The Arabic `native_name` cell (`language/list.html:50`) is pure-RTL text so bidi renders correctly without `dir="auto"`.

**Praise:** the L33 fix landed properly — this is the fourth attempt at the badge/stat-icon family and the first changeset in the family to ship **zero** non-existent modifier classes, including resisting the obvious `badge-warning` for the e-invoicing column. The read-only registries also say out loud that they are read-only, which is the right instinct.

### Orchestrator verification — lane 3

**L3-I3 — CONFIRMED by independent render.** I pulled the offset column straight out of the rendered HTML
rather than trusting the description:

```
  America/Los_Angeles  Los Angeles (PST/PDT)  -> UTC-480
  America/Chicago      Chicago (CST/CDT)      -> UTC-360
  Europe/London        London (GMT/BST)       -> UTC+0
  Europe/Berlin        Berlin (CET/CEST)      -> UTC+60
  Asia/Kolkata         Kolkata (IST)          -> UTC+330
  Asia/Tokyo           Tokyo (JST)            -> UTC+540
```

`UTC+330` for IST is the bug in one line: the column is minutes and the header says nothing. Lane 3 is right
that this contradicts the model's own docstring, which goes out of its way to say the offset is a
display convenience. **Real, Important.**

**L3-I4 — CONFIRMED by count:** `grep -c "Back to list" templates/core/statutoryrule/detail.html` → **0**,
while `grep -l "Back to list" templates/core/*/detail.html | wc -l` → **17 of 18**. The outlier is real.

**L3-C1 vs L1-I1 — the same defect, two severities. I am consolidating them as ONE finding graded
Important, and overruling lane 3's Critical.** Both lanes found the same root cause (the member's own
settings page offers only admin-gated exits); lane 3 adds the four in-page symptoms, lane 1 the POST-redirect
symptom. On **evidence** the grade is Important, not Critical: the member's save actually **succeeds** (the
`UserLocalePreference` row is written — my probe followed the redirect and got 403 from the *landing page*,
not from the write), nothing crashes, no tenant boundary is crossed, and the member is correctly *denied*
admin pages rather than wrongly granted them. The Critical rubric is a closed list — cross-tenant
read/write, missing tenant FK, authorization bypass, secret exposure, data corruption/loss, an unhandled
crash on a mainline path, a schema change with no migration — and a dead-end landing page is none of those.
Lane 1 reached the same conclusion explicitly; lane 3 graded on UX severity, which is the right instinct but
the wrong column. **I2 (Important) carries all five symptoms; the fix is one pass over three templates.**

**Lane 3's member-affordance rule is the most useful single output of the whole review so far.** It answers
the question lane 1 routed to it with the house precedent *quoted* (`navigation.py:93-94`'s "a preference a
member cannot set is an admin setting with a different label") rather than asserted, and it correctly
declines to file the app-wide sidebar condition as a 0.15 defect — that is exactly the "carried, not folded
in" discipline. I adopt the rule.

**One thing I checked that lane 3 could not:** its claim that `localeprofile/form.html` needs no change
because it is admin-gated is right, and the same reasoning means `statutoryrule/*` and the two computed
pages need no change either — so the fix surface really is just three templates, as it says.

---

## Lane 4 — `performance-reviewer`

**Base `35cde520` → HEAD.** Read-only. Measured against the seeded MariaDB dev DB (`nav_erp`) via `django.test.Client` + `CaptureQueriesContext`, as tenant-1 admin (`admin@acme.example`, pk 2). All destructive probes ran inside `transaction.atomic()` blocks that were force-rolled-back (verified net-zero row counts afterwards).

## Verdict

**No Critical findings. One Important (the routed `_fx_rows` concern is real and I confirm it — with a corrected rationale and a verified cheaper query). Two routed/incidental Minors.** Every one of the 11 views is **constant** in query count with respect to row count — there is **no N+1 anywhere** in this sub-module, and `statutory_rule_list` already does the `select_related` it needs. The index posture is correct and the "missing index on tiny global tables" question resolves to *correctly absent*.

Note for the orchestrator: every total below includes **6 shared queries** that no 0.15 view issues — session load, user load, tenant load, the `tenants_brandingsetting` context processor, and the `BEGIN`/`UPDATE django_session`/`COMMIT` written by the app-wide `SessionTimeoutMiddleware` on every request. I subtract those when attributing queries to a view.

---

## Important

### L4-I1 — `_fx_rows` materialises the tenant's entire rate history to emit one row per currency
`apps/core/views/Localization.py:46-69` (query at `:56-58`, dedupe loop `:58-61`)

**Confirmed, and it is the only genuine growth-shape defect in the module.** The query count is constant (1 — good), but the **rows transferred** scale as O(currencies × days) while the output is O(currencies). Measured:

| tenant 1 `ExchangeRate` rows | rows out of `_fx_rows` | queries | wall time |
|---|---|---|---|
| 3 (seeded) | 3 | 1 | <1 ms |
| **2,193** (3 currencies × 730 daily rates, rolled back) | **3** | **1** | **207 ms** |

The SQL is a full `INNER JOIN accounting_currency … WHERE tenant_id=1 ORDER BY currency.code ASC, rate_date DESC` with **no LIMIT** — every tenant row is fetched, joined and sorted, then discarded in Python. Extrapolating the measured 0.095 ms/row: a tenant with 10 currencies and 5 years of daily rates (≈18,250 rows) pays **≈1.7 s and ≈18k model instances per board render** — on a dashboard page. That is unbounded, so it is a real problem for this codebase, not a micro-optimization.

**The docstring's tie-break rationale does not apply to this model.** `apps/core/views/Localization.py:49-51` justifies the choice over a `Max("rate_date")` subquery because the latter "silently returns the wrong row when two rates share a date". But `ExchangeRate.Meta.unique_together = ("tenant", "currency", "rate_date")` (`apps/accounting/models/GeneralLedger/ExchangeRates.py:17`) makes two rows for the same tenant+currency+date **impossible**, so the max date is unique per currency and the feared ambiguity cannot occur. The constraint is also backed by a real unique index (`accounting_exchangerate_tenant_id_currency_id_ra_40b1546e_uniq` on `(tenant_id, currency_id, rate_date)`, per `SHOW INDEX`), which serves the aggregate below directly.

**Concrete cheaper query — 2 queries, O(currencies) rows, output verified identical:**

```python
from django.db.models import Max, Q

latest = (ExchangeRate.objects.filter(tenant=tenant)
          .values("currency_id").annotate(md=Max("rate_date")))
q = Q()
for r in latest:
    q |= Q(currency_id=r["currency_id"], rate_date=r["md"])
qs = (ExchangeRate.objects.filter(tenant=tenant).filter(q)
      .select_related("currency").order_by("currency__code"))
# then build the same row dicts from `qs`
```

I ran this against both the seeded data and a 2,190-row synthetic set: the `{(currency_id, rate, rate_date)}` sets are **equal** in both cases (`slow == fast -> True`), it issues **2** queries, and it preserves the `currency__code` display order. Correctness is preserved precisely *because* of the unique constraint above. A `django_assert_max_num_queries(2)` test on `localization_board` (hand to the test-writer) would lock this in.

---

## Minor

### L4-M1 — `localization_overview` fetches the same `LocaleProfile` row twice (routed: CONFIRMED)
`apps/core/views/Localization.py:251-252`

Confirmed by measurement. The page issues two queries for the one singleton row:
```
SELECT ... FROM core_localeprofile WHERE tenant_id = 1 LIMIT 1      <- .first()
SELECT 1 AS a FROM core_localeprofile WHERE tenant_id = 1 LIMIT 1   <- .exists()
```
Fix: fetch once and derive the flag — `profile = LocaleProfile.objects.filter(tenant=tenant).first()`, then `"profile": profile, "has_profile": profile is not None` (or the template's existing `{% if profile %}`). Saves exactly **one** query. **Honest grading:** this is a confirmed, trivially-correct fix, but it is a *constant* 1-query saving on a singleton — it does not grow with anything. I grade it Minor for impact while noting the fix is free.

### L4-M2 — one COUNT query per stat card instead of one aggregate per table
`apps/core/views/Localization.py:223-229` (board) and `:254-260` (overview)

Board issues **6** COUNTs (2× `core_timezone`, 2× `core_language`, 2× `core_statutoryrule`); overview issues the same 6 plus a 7th on `core_userlocalepreference`. Per the persona's rule 5, KPIs over one table should share an aggregate. Each pair collapses to one query with a conditional aggregate, e.g.:

```python
z = TimeZone.objects.aggregate(total=Count("id", filter=Q(is_active=True)),
                               dst=Count("id", filter=Q(is_active=True, observes_dst=True)))
```

Board 6→3 and overview 7→4. Graded Minor, not Important: these are `COUNT(*)` on tables bounded at 8/10 rows (global registries) and 6 rules, so the saving is constant and tiny — it is a query-count tidiness issue, not a scaling one. Do **not** let this distract from L4-I1.

### L4-M3 — the profile's FK targets are lazily loaded one query each
`apps/core/views/Localization.py:213` / `:251`; rendered at `templates/core/localizationoverview.html:19-21`, `templates/core/localizationboard.html:19`

The profile fetch does not `select_related` its FKs, so each rendered relation costs a query: board loads `accounting_currency` for `profile.base_currency` (1 extra), overview loads `core_language`, `accounting_currency` and `core_timezone` (3 extra) — all visible in the per-view SQL. Fix: add `.select_related("language", "base_currency", "time_zone")` to the profile queryset. Constant (one row), so Minor.

---

## Measured and clean

**Per-view query counts** (tenant-1 admin, seeded data; `total` then `module-owned = total − 6 shared`):

| View | total | module-owned | shape |
|---|---|---|---|
| `language_list` | 9 | 2 (COUNT + page SELECT) | constant |
| `timezone_list` | 9 | 2 | constant |
| `statutory_rule_list` | 9 | 2 (COUNT + page SELECT) | constant |
| `statutory_rule_create` | 8 | 1 (taxcode choices) | constant |
| `statutory_rule_detail` | 8 | 1 (rule, tax_code JOINed) | constant |
| `statutory_rule_edit` | 9 | 2 | constant |
| `locale_profile_edit` | 11 | 4 (profile + 3 form choice sets) | constant |
| `user_locale_edit` | 10 | 3 | constant |
| `localization_board` | 17 | 10 | constant |
| `localization_overview` | 21 | 14 | constant |

**No page's query count grows with rows.** Verified at scale inside rolled-back transactions: `statutory_rule_list` stays at **9** queries with 3 rows *and* with 303 rows, on pages 1/2/5 (pagination keeps it flat); `localization_board` stays at **17** and `localization_overview` at **21** with 300 extra rules. **No N+1 found in this sub-module.**

**`statutory_rule_list` `select_related` — present and sufficient.** `apps/core/views/Localization.py:159` applies `.select_related("tax_code")`, and the template touches `obj.tax_code.name` (`templates/core/statutoryrule/list.html:50`). The page emits **one** joined `core_statutoryrule` query and **zero** per-row `accounting_taxcode` queries. The list template does **not** touch `rate_pct`; the detail template does (`statutoryrule/detail.html:25`), and `crud_detail` is called with `select_related=("tax_code",)` (`Localization.py:178`) — also confirmed as a single joined query, no extra load.

**Template loops do no per-row work.** `language/list.html` and `timezone/list.html` touch only the row's own scalar fields. `localizationboard.html:41-51` iterates a pre-built Python list of dicts whose `currency` is already resolved by `_fx_rows`'s `select_related("currency")`, and whose `source` is pre-computed via `get_source_display()` — no query inside the loop. `localizationoverview.html:82-88` touches no FK. Clean.

**Indexes — correct, nothing missing, nothing redundant.**
- `statrule_tenant_active_idx (tenant_id, is_active)` is present (`models/Localization.py:238`, `SHOW INDEX` confirms) and exactly covers the predicates the board/overview counts run (`WHERE tenant_id=… AND is_active=1`); the e-invoicing count narrows further on the covered prefix. `unique_together (tenant, name)` also backs the list's tenant filter.
- `db_index=True` on `StatutoryRule.tenant` (`models/Localization.py:216-217`) does **not** create a redundant single-column index — `SHOW INDEX` on `core_statutoryrule` lists only PRIMARY, `(tenant_id, name)`, `tax_code_id`, and `statrule_tenant_active_idx`; `makemigrations --check core` reports *no drift*. So there is no redundant tenant-only index to trim.
- `Language` and `TimeZone` carry only their unique natural-key index (`code` / `name`). An index on `is_rtl` / `is_active` / `observes_dst` **would be pointless and I say so**: both are global registries bounded at ~8 and ~10 rows (a full IANA set is ~600), the flags are low-cardinality so a btree index buys nothing, and the `icontains` search (`crud_list` → `__icontains`) could not use one anyway. Correctly absent.
- `recent_rules` (`Localization.py:261`) orders by `created_at` with no index — considered and clean: `StatutoryRule` is a low-volume compliance register (dozens per tenant), so a `(tenant, created_at)` index is not warranted.

**`currencies_without_rates` — cheap and correct, no cross-tenant concern.** `Currency.objects.filter(is_active=True).count()` (`Localization.py:210, 221`) is a single `COUNT(*)` with O(1) growth. Filtering the **global** `accounting.Currency` master with no tenant predicate is *right*, not a leak: `Currency` is a global, non-sensitive reference master (`apps/accounting/models/GeneralLedger/Currencies.py:6-7`) shared by all tenants, so the number means "currencies the platform offers that this tenant has not rated" (measured: 4 − 3 = 1 for both tenants). The only edge is that a tenant holding a rate on a *now-inactive* currency would under-count the gap — a logic nuance, not a performance one; I flag it for the logic lane, not mine.

**Seeder cost — not worth flagging.** `_seed_localization_globals()` (`seed_core.py:704-709`, `:727-732`) is 8 language + 10 zone = **18 `get_or_create`** calls → 18 SELECTs on a re-run (36 statements on first run). `_seed_localization(tenant)` adds 2 guard SELECTs per tenant on a re-run (`:748`, `:764`). Against tables that hold 8 and 10 rows **forever**, run once, this is trivial, and `get_or_create` *is* the idempotency mechanism — a `bulk_create(ignore_conflicts=True)` would drop the created-count output and the natural-key guard for no measurable gain. The `if not X.objects.filter(tenant=…).exists()` per-entity guards are the deliberate anti-pattern-avoidance the docstring describes. Clean.

**Pagination** is in place for all three list views via `crud_list` (`apps/core/crud.py:115, 180`, default `per_page=15`), and all three list models have deterministic `Meta.ordering`, so pages are stable. No `list(qs)`-to-count or `len(qs)` misuse: the board's `len(rate_rows)` (`Localization.py:219`) operates on an already-materialised Python list, and every other existence check uses `.exists()` — except the one duplicate at L4-M1.

### Orchestrator verification — lane 4

**L4-I1 — CONFIRMED, and this lane corrected a mistake of MINE.** The load-bearing fact is the constraint,
which I re-read directly:

```
apps/accounting/models/GeneralLedger/ExchangeRates.py:17
        unique_together = ("tenant", "currency", "rate_date")
```

Two rows for the same tenant+currency+date are therefore **impossible**, so the `Max("rate_date")` tie I
wrote my own docstring to avoid *cannot occur*. My justification —

> "The alternative — a `Max("rate_date")` subquery joined back — is the shape that silently returns the
> wrong row when two rates share a date"

— is **false for this model**, and lane 4 proved it by measurement rather than argument (2,193 rows →
207 ms, then an A/B whose output sets are equal). This is the single most valuable finding of the review so
far: not because the code is wrong, but because **the stated reason for the code being right was wrong**,
and a future editor reading that docstring would have preserved a slow query to defend against a tie that
cannot happen. Severity upheld as **Important** — unbounded rows on a landing page, but no incorrectness.

**L4-M1 — CONFIRMED** (two queries for one singleton row; free fix).
**L4-M3 — CONFIRMED** (profile FKs lazily loaded; free fix).
**L4-M2 — CONFIRMED as a query-count tidy, and I agree with the lane's own downgrade to Minor.** 6 COUNTs
on tables of 8/10/6 rows is not a scaling problem. I will fold M1+M2+M3 into one "trim the computed pages'
queries" fix rather than three separate passes.
**L4's `currencies_without_rates` edge case — carried, not folded in.** A tenant holding a rate on a
now-inactive currency under-counts the gap. That is a *logic* nuance the lane explicitly declined to grade
(it is not its column) and I am recording it as a known, accepted edge rather than fixing it: the number
answers "currencies the platform offers that this tenant has not rated", and an inactive currency is not
offered. **No action, stated so the decision is visible.**
**L4's 6-shared-query accounting is exactly the discipline I want** — attributing queries to the view rather
than to the framework is what makes the per-view table above usable.







