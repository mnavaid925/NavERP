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

---

## Lane 5 — `qa-smoke-tester`

**Verdict: NOT CLEAN — 1 critical defect class (user-reachable HTTP 500), 1 behavioural inconsistency.** Everything else I exercised — the full CRUD write path, both singletons, both model `clean()` rule sets, cross-tenant IDOR on every write verb, the tenant-less superuser, the empty tenant, and pagination boundaries — is clean. The dev database was left **byte-for-byte unaltered** (verified counts below).

Harnesses (gitignored throwaways): `temp/qa15_writes.py`, `temp/qa15_writes2b.py`, `temp/_repro_dup.py`, `temp/_rootcause.py`. I did not re-run `temp/smoke_15.py` as the deliverable; its coverage was read and deliberately exceeded.

---

## Critical

### L5-C1 — Duplicate `(tenant, name)` on `statutory_rule_create` → **HTTP 500** (IntegrityError), not a form error

* `apps/core/forms/Localization.py:37-48` (`StatutoryRuleForm`) — no duplicate guard
* `apps/core/models/Localization.py:237` — `unique_together = ("tenant", "name")`
* `apps/core/crud.py:198` — `obj.save()` is where it dies

**Exact request** (as `admin_acme`, seeded rule `pk=7` name `"EU VAT e-invoicing"`):
```
POST /core/localization/statutory/add/
name=EU VAT e-invoicing&jurisdiction=L5&tax_code=&e_invoicing_scheme=none
&effective_from=2026-01-01&is_active=on
```
**Exact observed response:** `HTTP 500`, body contains `IntegrityError` / `Duplicate entry '1-EU VAT e-invoicing' for key 'core_statutoryrule_tenant_id_name_c6784f7c_uniq'`. No `already exists` form error. Traceback: `apps/core/views/Localization.py:170` → `apps/core/crud.py:198 obj.save()` → `django.db.utils.IntegrityError (1062)`.

**Root cause, verified directly** (`temp/_rootcause.py`):
```
form.is_valid() = True
form.errors     = {}
"tenant" in form._get_validation_exclusions() = True
instance.validate_unique(exclude=['tenant']) -> no error (constraint SKIPPED)
```
`tenant` is not a `Meta.fields` member, so Django excludes it from validation; `Model._get_unique_checks()` drops **any** `unique_together` containing an excluded field — so the `(tenant, name)` constraint is never validated by the form. The form validates, `crud_create` saves, and MySQL rejects the INSERT.

**No data corruption:** the row is never inserted (count 3 → 3). The user just gets a 500 with no feedback.

**This is a missed house pattern, not an unknown:** CRM already blocks exactly this at the form level —
`apps/crm/forms/CustomerSuccess/HealthScores.py:15-23` ("…returns a friendly error instead of an IntegrityError 500") and `apps/crm/forms/SalesForceAutomation/SalesQuotas.py:16-29`. `StatutoryRuleForm` omits the equivalent.

### L5-C2 — Same defect on the **edit** verb: renaming a rule to a sibling's name → **HTTP 500**

* `apps/core/crud.py:217` — `obj = form.save()`
* `apps/core/views/Localization.py:182-185`

**Exact request** (as `admin_acme`; rename `pk=7` `"EU VAT e-invoicing"` to the sibling `pk=9` name `"India GST e-invoice"`):
```
POST /core/localization/statutory/7/edit/
name=India GST e-invoice&jurisdiction=L5&tax_code=&e_invoicing_scheme=none
&effective_from=2026-01-01&is_active=on
```
**Exact observed response:** `HTTP 500`, `IntegrityError (1062) Duplicate entry '1-India GST e-invoice'`. Rule count unchanged at 3. Same root cause as L5-C1.

---

## Important

### L5-I1 — Tenant-less superuser: the `statutory_rule_*` family does **not** take the documented redirect branch

`apps/core/views/Localization.py:156-165` — `statutory_rule_list` has **no** `request.tenant is None` guard (unlike `localization_board:202`, `localization_overview:241`, `locale_profile_edit:106`, `user_locale_edit:132`). It calls `crud_list(request, StatutoryRule.objects.filter(tenant=request.tenant), …)`, i.e. literally `filter(tenant=None)`.

**Exact requests as `admin` (`is_superuser=True`, `tenant=None`) — all 11 routes:**

| route | status | Location | note |
|---|---|---|---|
| `localization_overview` | 302 | `/` | ✅ documented branch |
| `localization_board` | 302 | `/` | ✅ documented branch |
| `language_list` | **200** | — | ✅ global by design, real content |
| `timezone_list` | **200** | — | ✅ global by design, real content |
| `locale_profile_edit` | 302 | `/` | ✅ (via `messages.error`, not `info`) |
| `user_locale_edit` | 302 | `/` | ✅ documented branch |
| `statutory_rule_list` | **200** | — | ❌ renders the tenant-scoped register, empty |
| `statutory_rule_create` | 302 | `/` | ✅ via `crud_create` (`crud.py:189-191`), `messages.error` not `info` |
| `statutory_rule_detail` | **404** | — | ❌ not the documented branch |
| `statutory_rule_edit` | **404** | — | ❌ not the documented branch |
| `statutory_rule_delete` | **405** | — | ✅ correct (`@require_POST` outermost) |

No 500 anywhere. `statutory_rule_list` was verified to render a genuine empty state (`"Statutory Rules"` heading + empty-state markup), not a silently-blank context.

**Scope note for the fixer:** the contract pins the `tenant is None` branch only for the two **computed** views — `.claude/tasks/contract-core-0.15.md:212-213` ("both computed views … Never `filter(tenant=None)`") and `:224-225` for `user_locale_edit`. It does **not** pin it for the `crud_*`-backed statutory views. So this is a genuine inconsistency with the sibling views and with the prompt's stated expectation, but it is *not* a contract violation as written, and it leaks nothing. Decide whether to extend the guard to the four `statutory_rule_*` views or leave it. Flagging as Important only because the prompt listed it as expected behaviour.

---

## Minor

### L5-M1 — Pre-existing dev-DB pollution (not created by this lane; affects later lanes/tests)

Present in the dev DB before I ran anything and still present after:
* tenant `423` `lane5-empty` ("Lane5 Empty") + users `admin_lane5-empty` / `ops_lane5-empty` / `sales_lane5-empty`
* tenant `424` `smoke-empty` ("Smoke Empty") + `admin_smoke-empty` / `ops_smoke-empty` / `sales_smoke-empty`
* tenant `70` with **`slug=''`**, name `SMOKETEST Acme`, and users `admin_` / `ops_` / `sales_` with malformed emails (`admin@.example`, `ops@.example`)

I used `423` **read-only** for the empty-state test rather than creating a new tenant, so I added nothing. Flagging because a later lane or the test suite may be sensitive to these rows. `Tenant.slug` is `unique=True` but not `blank=False`-guarded at the DB level, so `slug=''` is storable.

### L5-M2 — Message level inconsistency for the tenant-less branch

`crud.py:190` and `Localization.py:107` use `messages.error`; `Localization.py:135,203,242` use `messages.info`. Cosmetic; fold into L5-I1 if that is fixed.

---

## Exercised and clean

**1. StatutoryRule full CRUD round-trip** (as `admin_acme`, all in a rolled-back `atomic()`):
GET create `200`; POST valid rule → `302` to `core:statutory_rule_list`; row created; **tenant taken from the session, not POST** — posted `tenant=<globex pk 2>` and the stored `tenant_id` was `1`; `AuditLog` `create` row written; GET edit `200` containing the rule name; POST edit `302`, change persisted; **no duplicate row** (count for that name stayed 1); `AuditLog` `update` row written; POST delete `302`, row gone; `AuditLog` `delete` row written. Rollback restored acme rules `3→3` and `AuditLog` `6748→6748`.

**2. `locale_profile_edit` singleton** (as `admin_lane5-empty`, tenant with no profile): first POST **created** (count `0→1`); second POST **updated the same row** (count stayed 1, `date_format` `dd/MM/yyyy`→`yyyy-MM-dd`) — the OneToOne holds. Validation, as `admin_acme` against the existing row: `date_format="dd/MM/yyyy<script>"` → `200` + *"A format pattern may contain…"*, stored value unchanged; `time_format="HH:mm{0}"` rejected; `number_format="#,##0.00;DROP"` rejected; `first_day_of_week="0"` and `"99"` → `200` + *"Select a valid choice"*, stored value unchanged. All rejected by `LocaleProfile.clean()` (`models/Localization.py:155-161`), not merely the form.

**3. `user_locale_edit` singleton**: admin POST created own row with `tenant = session tenant`; second POST updated the same row (no duplicate); bad `date_format` rejected; **POST as a member (`leaver@acme.example`, non-admin) wrote the member's row** (`date_format=MM/dd/yyyy`) and the admin's row was untouched.

**4. `StatutoryRule.clean()` cross-field rules**: `e_invoicing_required=True` + `e_invoicing_scheme="none"` → `200` + *"Choose the scheme this jurisdiction uses."*, **not saved**; `effective_to=2026-01-01` < `effective_from=2026-06-01` → `200` + *"The end date cannot precede the start date."*, **not saved**.

**5. Cross-tenant IDOR on every write verb**: POST `statutory_rule_edit` with a globex pk → `404`; POST `statutory_rule_delete` with a globex pk → `404`; the globex row was then **byte-identical** on `(name, jurisdiction, notes, is_active, e_invoicing_scheme, updated_at)` and the globex count was still 3 — the 404 does not mutate.

**6. Empty-state boundary** (tenant `423`: 0 profiles, 0 rules, 0 exchange rates): `localization_board` `200` showing *"No exchange rates recorded"* + *"Not set"*; `localization_overview` `200` showing *"No statutory rules yet"* + *"Not configured"*; `statutory_rule_list` `200`. No crash, sensible zeroes.

**7. Pagination boundary** (20 extra rules → 23 total, rolled back): 2 pages; page 1 = 15 rows, page 2 = 8 rows; `?page=999` and `?page=3` both clamp to page 2; `?page=0`, `?page=-1`, `?page=abc`, `?page=99999999999999999999999999` all `200`. Rollback restored the count to 3.

**8. Additional form boundaries** (not in the existing harness): cross-tenant `TaxCode` pk rejected by the tenant-scoped queryset (*"Select a valid choice"*, not saved); own `TaxCode` accepted and persisted; missing required `effective_from` → required-field error; over-range `tax_code=99999999999999999999` → `200`, **not** a 500; bogus `e_invoicing_scheme="zzz"` → invalid-choice error; edit preserves `tenant_id`.

**9. Global registry filters** (global-by-design, correct for both tenant admin and tenant-less superuser): `language_list?rtl=True` → RTL only (Arabic, Hebrew; no French); `?rtl=False` → LTR only; `?q=ar` search works; `timezone_list?dst=True` → DST zones only (Europe/London present, Asia/Kolkata absent); `?dst=False` → `200`.

**10. Tenant-less superuser content (not just status)**: `language_list` `200` containing *Languages* / *Arabic* / *Right-to-left*; `timezone_list` `200` containing *Europe/London* / *Observes DST*.

**11. Data-safety verification.** Counts before → after my entire session: tenants `5→5`; languages `8→8`; timezones `10→10`; `LocaleProfile` `2→2`; `UserLocalePreference` `1→1`; `StatutoryRule` `6→6` (ids `[7,8,9,10,11,12]`); `AuditLog` `6748→6748`; `ExchangeRate` `6→6`; rows matching `L5-QA-*` = `0`. Every write was inside `transaction.atomic()` + `set_rollback(True)`. `git status` shows no change attributable to this lane (all my scripts live under gitignored `temp/`); I created, edited and committed **no** tracked file.

**False alarm I ruled out (not a defect):** my first pagination assertion expected the newest-created rule on page 1; the list orders by `Meta.ordering = ["jurisdiction", "name"]` (`models/Localization.py:236`), so that rule legitimately lands on page 2. Row counts per page are correct (15 / 8).

### Orchestrator verification — lane 5

**L5-C1 / L5-C2 — CONFIRMED, and this is the review's one true Critical.** I re-derived it from scratch with
`temp/probe_15_dup.py` rather than accepting the diagnosis, and reproduced **both the mechanism and the
symptom**:

```
tenant rules before: 3
existing rule: 'EU VAT e-invoicing' pk 7

--- 1. the raw Django claim: is the unique_together validated? ---
  is_valid() = True
  errors     = {} (none!)
  'tenant' excluded from validation = True
  instance.validate_unique(exclude=['tenant']) -> NO ERROR RAISED

--- 2. CREATE with a duplicate name ---
  status: 500

--- 3. EDIT renaming onto a sibling's name ---
  renaming 'EU VAT e-invoicing' -> 'India GST e-invoice' : status 500

--- 4. did anything mutate? ---
  rules before/after: 3 / 3 -> UNCHANGED
```

Both verbs 500 on a **plain, everyday** user action — typing a name that already exists, or renaming a rule
onto a sibling's name. Nothing exotic is required. Lane 5 is also right that this is a *missed house
pattern* rather than an unknown: `apps/crm/forms/CustomerSuccess/HealthScores.py:15-23` already solves it,
so the fix is to copy a shape that exists in the repo. Severity **Critical, upheld** — an unhandled 500 on
a mainline path is on the Critical rubric's closed list, and unlike lanes 1/3's dead-end this one is a
crash. **The fix belongs in `StatutoryRuleForm` (a `clean_name`/`clean` duplicate guard scoped to
`self.tenant`), not in `crud_create`** — `crud_create` is shared by every module and must not grow a
per-model rule.

**L5-I1 — DOWNGRADED TO NO ACTION. The error was MINE, in the brief.** I told lane 5 to expect the
`tenant is None` redirect branch on "the tenant-scoped ones" including `statutory_rule_*`. That is not the
house norm, and I should have checked before writing it:

```
$ grep -A 6 "def party_list" apps/core/views/Party.py
18:def party_list(request):
19-    return crud_list(
20-        request, Party.objects.filter(tenant=request.tenant),   # <- no guard, by design
...
$ grep -rn "crud_list(" apps/*/views/*.py | wc -l                  -> 487
$ grep -rn -B3 "crud_list(" apps/core/views/*.py | grep -c "tenant is None"  -> 0
```

**Zero of 487** `crud_list` call sites guard the tenant-less case, and `party_list` — the reference view —
is structurally identical to `statutory_rule_list`. An empty register **is** the correct rendering for a
superuser who "sees no module data by design". Lane 5 flagged it as Important *only* because my prompt
asserted it; it even said so ("Flagging as Important only because the prompt listed it as expected
behaviour"). I am recording this as an orchestrator error alongside L2-M3, and **filing no code action**.
`statutory_rule_detail`/`_edit` → 404 and `_delete` → 405 are all correct.

**L5-M1 — out of scope for this sub-module, but worth escalating.** Three junk tenants (including one with
`slug=''`) predate 0.15 and were not created by this build. They are dev-DB residue from earlier smoke
runs. Not a 0.15 finding, and deliberately **not** fixed here — but recorded, because lane 5 is right that a
later test lane could trip over them.

**L5-M2 — CONFIRMED as cosmetic**, and with L5-I1 dropped there is nothing to fold it into. `messages.error`
vs `messages.info` across the five tenant-less branches is a one-word inconsistency with no functional
effect. **No action.**

**Lane 5's data-safety discipline is the best in the review:** every write inside a rolled-back
`transaction.atomic()`, with before/after counts published for nine tables, and an explicit note that the
one dev-DB oddity was pre-existing. It also refused to re-run the existing smoke harness as its deliverable
and instead covered the write paths that harness omits — which is precisely how the Critical was found.

---

## Lane 6 — `security-reviewer`

**Lane:** L6 (security) · **BASE** `35cde520` · **Scope:** `git diff 35cde520...HEAD` restricted to the `core` 0.15 surface · **Mode:** read-only

---

## Verdict

**Clean.** No Critical, no Important, no cross-tenant exposure, no missing gate, no mass-assignment hole, no CSRF gap, no IDOR. Two Minor items, both non-confidentiality (an authorization/UX link mismatch and an audit-fidelity gap). The tenant-isolation posture is correct on every path I could reach, and I confirmed the load-bearing claims at runtime with a non-mutating probe (built in `temp/`, then deleted).

---

## Critical

None.

## Important

None.

## Minor

### L6-M1 — Member-reachable 0.15 pages advertise admin-gated destinations (now-403 links)

`apps/core/views/Localization.py:103` (`locale_profile_edit`), `:199` (`localization_board`) and `:238` (`localization_overview`) are all `@tenant_admin_required`, but three **member-reachable** templates (`@login_required` views) link to them:

- `templates/core/language/list.html:7,10,11` → `localization_overview`, `localization_board`, `locale_profile_edit`
- `templates/core/timezone/list.html:7,10,11` → same three
- `templates/core/userlocale/form.html:7,10,15,32` → `localization_overview`, `locale_profile_edit`

**Attack path (no data exposure):** a member opens `/localization/languages/` (200, allowed by `@login_required`) and clicks *Board* / *Regional settings* → `PermissionDenied` → 403. The gate holds server-side; nothing leaks. This is the persona's named AuthN/AuthZ item ("when a view gains a gate, the template must stop offering the now-403 button"), and the house already has the idiom in **214** templates.

**Fix** (house-idiomatic), in `templates/core/language/list.html:10-11` and the two sibling files:

```django
{% if request.user.is_superuser or request.user.is_tenant_admin %}
  <a href="{% url 'core:localization_board' %}" class="btn btn-outline">Board</a>
  <a href="{% url 'core:locale_profile_edit' %}" class="btn btn-outline">Regional settings</a>
{% endif %}
```

Note the breadcrumb links (`:7`) hit the same 403 and need the same treatment or a neutral target.

**Pattern-clone grep** — `grep -rn "url 'core:locale_profile_edit'\|url 'core:localization_board'\|url 'core:localization_overview'" templates/` returns exactly the three member-reachable files above; the rest are on admin-gated pages and are fine. The sidebar (`apps/core/navigation.py:2116` `LIVE_LINKS["0.15"]`) shows these same admin destinations to members too, but `resolve_nav` (`navigation.py:2195`) is role-blind for **every** module, so that is pre-existing architecture, not a 0.15 regression — I am not filing it.

### L6-M2 — The two hand-rolled singleton saves write an audit row without the field diff

`apps/core/views/Localization.py:119` and `:146` pass a bare verb:

```python
write_audit_log(request.user, obj, "update", changes={"verb": "locale_profile_save"})
```

where the equivalent house path uses the diff: `apps/core/crud.py:219` → `changes=_changed(form)`. So the trail records *that* a tenant admin changed the workspace's regional profile, not *what* changed (old→new language / base currency / zone / format patterns).

**Security impact: negligible** — `LocaleProfile` and `UserLocalePreference` hold no secret, credential or personal data (the sub-module has no such field), so this is audit fidelity, not confidentiality. Filing it only because the persona names hand-rolled save paths explicitly.

**Fix:** mirror `crud.py` — `from apps.core.crud import _changed` and pass `changes=_changed(form)` (or an explicit `{"field": "old→new"}` dict). If the verb marker is wanted, merge it: `changes={"verb": "...", **_changed(form)}`.

---

## Answers to the 8 questions

**1. Are the two GLOBAL read-only lists an information disclosure? — No. Correct as built.**

Verdict: **not a disclosure.** The argument holds on three independent legs:

- **Precedent is exact and stricter in 0.15.** `apps/accounting/views/GeneralLedger/Currencies.py:15-20` — `currency_list` is `@login_required`, reads `Currency.objects.all()`, no tenant filter, and (unlike 0.15) *does* have write routes behind `@tenant_admin_required` (`:23`). `Language`/`TimeZone` take the same shape and add **no** CRUD routes at all, so 0.15 is the *more* restrictive of the two.
- **The exposed data is public by construction.** I read `templates/core/language/list.html:44-53` — the page renders `code`, `name`, `native_name`, `is_rtl`, `is_default`, `is_active`. Those are ISO 639-1 identifiers and their own endonyms; `timezone_list` renders IANA names + standard offset + DST flag (`models/Localization.py:97-103`). Both are published facts, identical for every tenant, and contain **no tenant identifier, no tenant count, and no per-tenant row**. A cross-tenant reader learns nothing about any workspace.
- **No tenant data is reachable through them.** The queryset is `Language.objects.all()` (`views/Localization.py:78`) / `TimeZone.objects.all()` (`:93`) with no join to any tenant-owned table, so there is no path from these pages to tenant rows.

What the pages *do* confirm is that a registry exists — which the sidebar already advertises to every user. Verdict: **by design, not a finding.**

**2. Can `UserLocalePreference.tenant` disagree with the user's tenant, and does any view cross the boundary? — They can disagree; no view crosses; the only consequence is an IntegrityError 500.**

`user_locale_edit` (`views/Localization.py:129-151`) reads `filter(tenant=request.tenant, user=request.user).first()` (`:138`) and on POST **overwrites both** server-owned keys from the session:

```python
obj.tenant = request.tenant   # :143
obj.user   = request.user     # :144
```

A crafted POST cannot move either: `UserLocalePreferenceForm.Meta.fields = ["language", "time_zone", "date_format"]` (`forms/Localization.py:34`), and my probe confirmed `tenant` and `user` are both **model fields absent from the form**, so Django discards them from POST entirely and both assignments are unconditional.

Disagreement is only reachable by moving a user's tenant out-of-band. I grepped for it: **no application code reassigns a `User` row's tenant** (`grep -rn "\.tenant = " apps/accounts/ apps/tenants/` returns nothing for the `User` model; `UserForm.Meta.fields`, `forms.py:108-109`, omits `tenant`). The only reachable path is the Django admin — `apps/accounts/admin.py:22` `UserAdmin.list_display` includes `tenant` and does not make it read-only — i.e. **platform superuser only**.

If it happens: GET finds no row (`obj=None`, blank form, reads nothing from the old tenant), and the next POST inserts a second row for the same `user` → the `OneToOneField` unique constraint fires → `IntegrityError` → 500. **No view then reads or writes across the boundary** — every read is `filter(tenant=..., user=...)` (`:138`, `:253`, `:260`). So: **no cross-tenant leak; an availability edge case requiring a superuser action.** Not filed as a finding (it is the same 500 class as Q6, with a narrower trigger).

**3. Can a tenant admin write a `LocaleProfile` for a different tenant? — No.**

`locale_profile_edit` (`views/Localization.py:104-125`) reads `filter(tenant=request.tenant).first()` (`:110`), and on save sets `obj.tenant = request.tenant` (`:117`) **after** `form.save(commit=False)`. `LocaleProfileForm.Meta.fields` (`forms/Localization.py:25-26`) excludes `tenant`, so a crafted `tenant=<other pk>` in the POST is dropped by Django; my probe confirmed `tenant` is a model field not on the form. The three FKs the form *does* expose — `language`, `base_currency`, `time_zone` — are the global registries, and my probe confirmed their querysets carry **no** tenant predicate (`core_language`, `accounting_currency`, `core_timezone`, unfiltered), which is correct: they have no `tenant` column to scope on. **No path writes another tenant's profile.**

**4. Is `StatutoryRule.tax_code` genuinely tenant-scoped, in the form and in the seeder? — Yes, both.**

**Form.** `accounting.TaxCode(TenantOwned)` — `apps/accounting/models/Tax/../TaxCodes.py:6` inherits `TenantOwned`, whose `tenant` FK is at `apps/accounting/models/_base.py:48`. `TenantModelForm.__init__` (`forms/_common.py:52-55`) filters any `ModelChoiceField` whose model has a `tenant` field. My probe, on a stub tenant `pk=4242`, produced:

```sql
SELECT ... FROM "accounting_taxcode" WHERE "accounting_taxcode"."tenant_id" = 4242 ORDER BY ...
```

So a crafted cross-tenant pk fails `ModelChoiceField` validation ("Select a valid choice") → form invalid → no write. The view side is closed twice over: `crud_create` re-sets `obj.tenant = request.tenant` (`crud.py:196-197`) and `crud_edit`/`crud_detail`/`crud_delete` all fetch `get_object_or_404(..., tenant=request.tenant)` (`crud.py:213, 230, 241`).

**Seeder.** `seed_core.py:769-770`:

```python
vat_code   = TaxCode.objects.filter(tenant=tenant, tax_type="vat").first()
sales_code = TaxCode.objects.filter(tenant=tenant, tax_type="sales").first()
```

Both are tenant-scoped, and the `Currency.objects.filter(code="USD")` lookup at `:753` is global by design (no tenant column). **The seeder never crosses tenants.**

**5. Write-verb authorization — confirmed, all of it.**

- **`@require_POST` is outermost on `statutory_rule_delete`** (`views/Localization.py:191-193`). Source order is `@require_POST` above `@tenant_admin_required`, so bottom-up application makes `require_POST` the outermost wrapper. Runtime-confirmed with a `RequestFactory` probe:

  | caller | method | result |
  |---|---|---|
  | anonymous | GET | **405** |
  | anonymous | POST | 302 → `/login/` |
  | member | GET | **405** |
  | member | POST | **403** `PermissionDenied` |

  The 405-not-403 ruling (7.7) holds exactly: the method check precedes the role gate. Note this means an anonymous `GET` gets 405 rather than a login redirect — that reveals only that the route exists, and it is the documented house standard, so not a finding.
- **Every mutating view is gated.** Probe over all 11 views: `language_list`/`timezone_list` `@login_required` (read-only, no write routes); `user_locale_edit` `@login_required` (own row only); `locale_profile_edit`, `statutory_rule_list/create/detail/edit/delete`, `localization_board`, `localization_overview` all `@tenant_admin_required`. No mutating view is login-only.
- **Member cannot create/edit/delete a `StatutoryRule`.** Probe: member `GET` on `statutory_rule_create` → `PermissionDenied: Tenant administrator access required.` (403), raised before the view body runs. `crud_delete` is additionally self-defending (`crud.py:240-242`).
- **Member *can* save their own `UserLocalePreference`** — `@login_required` at `:129`, writing only `tenant=request.tenant, user=request.user`.
- **Template/route consistency:** the edit/delete buttons in `templates/core/statutoryrule/list.html:57-61` and `detail.html:10-14` live on `@tenant_admin_required` pages, so a member never reaches them. (The *inverse* mismatch on the member-reachable pages is L6-M1.)

**6. Security impact of the duplicate-name HTTP 500 — none. Availability/UX bug only.**

Mechanism confirmed at source level (Django 5.1.15): `_get_validation_exclusions()` excludes any model field not on the form (`venv/.../django/forms/models.py:404`), and `_get_unique_checks()` skips a `unique_together` tuple if *any* of its fields is excluded (`venv/.../django/db/models/base.py:1413-1415` — `if not any(name in exclude for name in check)`). My probe showed `tenant` and `created_at`/`updated_at` are model fields absent from `StatutoryRuleForm`, with `unique_together = (('tenant','name'),)`. So `("tenant","name")` is never validated → `crud_create` inserts → `IntegrityError` → 500. QA's finding is real.

**Security judgement:**
- **Not a DoS.** One failed INSERT per request, an authenticated request, no unbounded resource, no lock retained past the statement, no persistent state change. The server stays up.
- **Not an information leak.** The 500 body is generic whenever `DEBUG=False`. And the oracle it would otherwise create is **intra-tenant only**: the constraint is `(tenant, name)`, so a same-named rule in *another* tenant does not collide — no cross-tenant existence oracle exists. The only actor who can trigger it is a tenant admin (`@tenant_admin_required`), and a tenant admin can already enumerate their own tenant's rule names via `statutory_rule_list`. **Information gain: zero.**
- **Verdict: purely availability/UX.** It is a deviation from the repo's "no unhandled 500 from user input" ethos, which is QA's lane — I am not re-filing it.

**7. CSRF, IDOR, mass assignment — all clean.**

- **CSRF:** every POST form carries `{% csrf_token %}` — `templates/core/localeprofile/form.html:17`, `userlocale/form.html:17`, `statutoryrule/form.html:16`, `statutoryrule/detail.html:12`, `statutoryrule/list.html:59`. No `@csrf_exempt` anywhere in the 0.15 views/forms/models/urls (grepped, zero hits). `CsrfViewMiddleware` is in `MIDDLEWARE` and no view opts out.
- **State-changing GET:** none. The only mutating route, `statutory_rule_delete`, is `@require_POST` *and* `crud_delete` re-checks `request.method` (`crud.py:242`). `crud_delete` still runs the tenant-scoped `get_object_or_404` on GET, but performs no mutation and redirects — no write.
- **IDOR on `statutory_rule_*`:** `statutory_rule_detail` (`crud.py:230-233`), `_edit` (`:213`) and `_delete` (`:241`) all resolve through `filter(tenant=request.tenant)` → another tenant's pk yields **404**, which is the correct non-oracle response. `statutory_rule_list` filters `tenant=request.tenant` at the call site (`views/Localization.py:159`). No `Model.objects.get(pk=...)` or `.all()` on a tenant-owned model anywhere in the file.
- **Mass assignment:** no view writes a POST-supplied `tenant` or `user`. All three forms exclude `tenant`; `UserLocalePreferenceForm` also excludes `user` (probe-confirmed). `statutory_rule_create` inherits `set_tenant=True` → `obj.tenant = request.tenant` (`crud.py:196-197`). The two singleton views assign both keys from the session after `commit=False` (`views/Localization.py:117`, `:143-144`). Status-like fields (`is_active`, `e_invoicing_required`) are legitimately user-editable domain data, not workflow-controlled. `created_at`/`updated_at` are `auto_now*` and off-form.

**8. Does `DEBUG` affect what these views expose? — Only the generic 500 page, and only via the pre-existing config default.**

`config/settings.py:16` → `DEBUG = _bool("DEBUG", "True")`. With `DEBUG=True` a traceback page renders SQL, table/column names, local paths and a filtered settings view — relevant to Q6's duplicate-name 500. With `DEBUG=False` (which `config/settings_test.py` sets, and which `.env` must set in production) it is Django's generic 500 with no detail. This is a **deployment-configuration** property affecting every 500 in the application, not a 0.15 defect, and the repo already documents the `SECRET_KEY`-fails-hard-when-not-DEBUG guard at `settings.py:23`. None of the 11 views read `settings.DEBUG`, and none render a conditional that widens on it. No 0.15-specific exposure.

---

## Assessed and clean

| Check | Result |
|---|---|
| Cross-tenant IDOR on `statutory_rule_{list,detail,edit,delete}` | Scoped via `filter(tenant=request.tenant)`; foreign pk → 404 |
| FK dropdown cross-tenant pk (`tax_code`) | `TenantModelForm` scopes to `tenant_id = <request.tenant>` — SQL-confirmed |
| Global FK dropdowns (`language`, `time_zone`, `base_currency`) | Correctly unfiltered — those models have no `tenant` column |
| Seeder cross-tenant `TaxCode` resolution | `filter(tenant=tenant, tax_type=...)` — scoped |
| Mass assignment of `tenant` / `user` | All three forms exclude both; views assign from the session |
| `@require_POST` outermost on delete (7.7 ruling) | Confirmed statically **and** at runtime (405 before 403) |
| Member → `StatutoryRule` write | 403 `PermissionDenied` (probe) |
| Member → own `UserLocalePreference` | Allowed (`@login_required`), own row only |
| CSRF on every POST form | `{% csrf_token %}` present in all 5; no `@csrf_exempt` |
| State-changing GET | None |
| XSS in the 9 templates | Auto-escaped throughout; no `\|safe`, `mark_safe`, `{% autoescape off %}`; `linebreaksbr` escapes first |
| CSS injection via `style="..."` | All 4 occurrences are static template literals, no user value interpolated |
| SQL injection | ORM only; no `.raw()` / `.extra()` / `cursor.execute()` in the sub-module |
| Secrets / credentials / hashes | **None exist in this sub-module** — no secret field, no reveal path, no `messages` secret |
| Format-pattern allow-list (`FORMAT_TOKEN_RE`, `models/Localization.py:55`) | `%` excluded, so no `strftime`-injection shape; and no production consumer exists today (grepped) — defence-in-depth, not a live control |
| Open redirect / `?next=` handling | None in 0.15 |
| `AuditLog` coverage | `crud_create`/`_edit`/`_delete` audit automatically; both singleton saves write a row (diff omitted — L6-M2) |
| Migration `core.0012` | Pure `CreateModel`/`AddIndex`; no `RunPython`, no `RunSQL`, no data backfill |
| `admin.py` registrations | All 5 use the admin site's own staff/superuser gate; `UserLocalePreferenceAdmin` exposes `user` + `tenant` read-only in `list_display`, consistent with the rest of `admin.py` |
| Tenant-less superuser (`tenant=None`) | `locale_profile_edit`/`user_locale_edit`/`localization_board`/`localization_overview` redirect with a message; `crud_create` redirects; lists return empty. No 500, no orphan write |
| Unvalidated numeric input (L35) | No hand-parsed numerics; `utc_offset_minutes`/`first_day_of_week` are `IntegerField`/`PositiveSmallIntegerField` with choices |
| Hand-parsed GET filters (L11) | All route through `crud_list`'s `as_db_int`/enum guards — no raw `int(request.GET[...])` |

**Probe note:** I built one throwaway script in `temp/` (gitignored) that did in-memory form/queryset inspection plus `RequestFactory` calls that raise before any DB access; it opened no connection, wrote no row, ran no migration, and I deleted it. The runtime confirmations above are its output. I edited nothing else, ran no migration and did not run the seeder.

**Hand-off:** nothing to escalate — no suspected exploit survived the check. The QA lane's duplicate-name 500 needs no security follow-up (Q6).

### Orchestrator verification — lane 6

**Clean, and I accept it.** Two things about this lane are worth recording:

- **L6-M2 is a genuinely NEW finding** — no other lane raised it. I confirmed it by reading my own code:
  `views/Localization.py:119` and `:146` pass `changes={"verb": "..."}` where `crud.py:219` passes
  `changes=_changed(form)`. So the two singleton saves record *that* the profile changed but not *what*
  changed — the audit trail for a config surface is thinner than for every CRUD surface beside it. Minor and
  non-confidential, exactly as graded, but real. **Fix note for the fixer:** `_changed` is module-private in
  `crud.py`; importing a `_`-prefixed name across modules is itself a smell, so prefer passing an explicit
  `{field: new_value}` diff from the view, or promote the helper — the fixer should pick one and say which.
- **L6-M1 duplicates lane 3's L3-I1/I2 and lane 1's L1-M1/M2** — the same three templates. That is
  **corroboration, not noise**: three independent lanes reached the same conclusion, and lane 6 supplies the
  house-idiomatic fix (`{% if request.user.is_superuser or request.user.is_tenant_admin %}`) plus the
  pattern-clone grep. It consolidates to **one** finding.
- **Lane 6's Q6 answer is the right call and I adopt it:** the duplicate-name 500 has **zero** security
  impact — not a DoS, and the `(tenant, name)` constraint is intra-tenant so it creates no cross-tenant
  existence oracle. It correctly declined to re-file QA's finding and left it in QA's lane. That is the
  "carried, not folded in" discipline again.
- **Lane 6's Q2 answer found a real edge case and correctly declined to file it**: a superuser changing a
  user's tenant via the Django admin can leave a stale `UserLocalePreference`, and the next save 500s on the
  OneToOne. Narrow, superuser-only, no cross-tenant read or write. **Recorded, no action.**
- **The `admin.site` `list_display`-based gating is the right final note:** all five new admins inherit the
  admin site's own staff/superuser gate, so no new exposure was introduced through the admin.

**All six lanes are in.** Consolidated findings below.

---

# CONSOLIDATED FINDINGS

**Six lanes:** `code-reviewer` · `explorer` · `frontend-reviewer` · `performance-reviewer` · `qa-smoke-tester` · `security-reviewer`.
**Raw findings:** 17 across the six lanes → **1 Critical, 4 Important, 7 Minor, 8 explicit no-action entries.**

Severity was re-set on evidence, not inherited. Where lanes disagreed, the resolution is recorded inline.
**Two lanes filed findings that were artifacts of MY briefs (N1, and lane 2's M3) — both are recorded as
orchestrator errors and neither produced a code change.**

## C — Critical

| id | finding | source lanes | verified by | status |
|---|---|---|---|---|
| **C1** | **A duplicate `(tenant, name)` 500s on both create and edit.** `StatutoryRuleForm` never validates the model's `unique_together`, because `tenant` is not a `Meta.fields` member and Django's `_get_unique_checks()` drops any `unique_together` containing an excluded field. Typing an existing rule name — or renaming a rule onto a sibling's name — is an everyday action that ends in an unhandled `IntegrityError`/500 instead of a form error. **Fix:** add the duplicate guard to `StatutoryRuleForm` (scoped to `self.tenant`), copying the shape that already exists in the repo at `apps/crm/forms/CustomerSuccess/HealthScores.py:15-23`. Do **not** touch `crud_create` — it is shared by every module. | L5-C1, L5-C2 | **Orchestrator: reproduced from scratch** (`temp/probe_15_dup.py`): `is_valid()=True`, `errors={}`, `tenant` excluded, `validate_unique(exclude=['tenant'])` silent, then HTTP 500 on both verbs, DB unmutated. **Critical upheld** — an unhandled 500 on a mainline path. | [x] fixed — `fix(core): validate StatutoryRule (tenant, name) uniqueness in the form (0.15 C1)` (c2dfe385) |

## I — Important

| id | finding | source lanes | verified by | status |
|---|---|---|---|---|
| **I1** | **Member-reachable pages offer only admin-gated exits.** Three templates: `userlocale/form.html` (breadcrumb, "Overview", body link, **and Cancel** all → `@tenant_admin_required` pages), `language/list.html` and `timezone/list.html` (both page-action buttons). A member who saves their own regional preference is POST-redirected to a 403, and their only in-page exit is the browser Back button. **Fix:** route to member-reachable pages where one exists (`core:user_locale_edit`, `dashboard:home`), hide where none does — lane 6's `{% if request.user.is_superuser or request.user.is_tenant_admin %}` idiom, or lane 3's "empty the `.page-actions`" precedent from `my_preferences.html`. | L1-I1, L1-M1, L1-M2, L3-C1, L3-I1/I2, L6-M1 | **Orchestrator: reproduced** (`temp/probe_15_member_flow.py`): member GET 200 → POST 302 to `/core/localization/` → **403**; and all three page-action targets 403. **Severity set to Important, overruling lane 3's Critical** — the save itself *succeeds*, nothing crashes, no boundary is crossed, and the member is correctly denied rather than wrongly granted. The Critical rubric is a closed list and a dead-end landing page is not on it. | [x] fixed — `fix(core): hide admin-gated exits on the member regional-settings page (0.15 I1)` (f19d1855), `…on the member language list` (aadf1164), `…on the member time-zone list` (830419fc), `…land the member locale save on its own page` (2a58b008), `…hide the admin-gated profile link from a member on the locale form` (26653443) |
| **I2** | **`_fx_rows` materialises the tenant's entire rate history to emit one row per currency.** O(currencies × days) rows fetched, joined and sorted, then discarded in Python. Measured 2,193 rows → 207 ms; extrapolates to ≈1.7 s on a landing page at 10 currencies × 5 years. **And the docstring's stated justification is false:** it claims a `Max("rate_date")` subquery can "return the wrong row when two rates share a date", but `ExchangeRate.Meta.unique_together = ("tenant","currency","rate_date")` makes that impossible. **Fix:** lane 4's 2-query replacement, A/B-verified to produce an identical output set. | L4-I1 | **Orchestrator: confirmed** the deciding constraint at `apps/accounting/models/GeneralLedger/ExchangeRates.py:17`. **This is the review's most valuable finding: the code is slow but not wrong — the *reason* I wrote for it was wrong, and a future editor would have defended a slow query against a tie that cannot occur.** | [x] fixed — `perf(core): rewrite _fx_rows to a 2-query grouped Max and drop its false tie-break rationale (0.15 I2)` (89e71349) |
| **I3** | **The timezone offset column prints raw minutes.** `templates/core/timezone/list.html:44,50` renders `utc_offset_minutes` as `UTC+330` for IST and `UTC-480` for Los Angeles — reading as hours, under a header with no unit, and contradicting the model's own docstring. **Fix:** add a `TimeZone.offset_display` property (`UTC+05:30` / `UTC-08:00`) and render that. | L3-I3 | **Orchestrator: reproduced by render** — pulled the column straight out of the live HTML. | [x] fixed — `feat(core): add TimeZone.offset_display property for UTC-offset rendering (0.15 I3)` (2b5df7a9), `…render the time-zone offset via offset_display, not raw minutes` (7c8b0c94) |
| **I4** | **The 0.15 seeder's peer-app FKs can never be populated on a fresh install.** `_seed_localization` reads `accounting.Currency` and `accounting.TaxCode`, but `seed_accounting` is their only creator and explicitly requires `seed_core` to run first ("No tenants found — run `seed_core` first"). On a fresh DB every lookup is `None`, and the per-entity guard then **freezes the NULLs permanently** — re-running `seed_core` after `seed_accounting` does not repair them. Latent on the dev DB only because accounting data pre-existed. **Fix:** backfill a NULL link on re-run inside `_seed_localization`, rather than skipping the whole entity. | L2-I1 | **Orchestrator: confirmed the premise** by grep — `seed_accounting.py:97-99` bails without tenants; it is the sole `Currency`/`TaxCode` creator. Dependency is circular in the documented order. | [x] fixed — `fix(core): backfill the localization seeder NULL peer-app FKs on re-run (0.15 I4)` (948f85de) |

## M — Minor

| id | finding | source | note | status |
|---|---|---|---|---|
| **M1** | `templates/core/statutoryrule/detail.html:39` — no "Back to list"; the only one of 18 core detail pages without it. | L3-I4 | Verified by count: 0 vs 17/18. | [x] fixed — `fix(core): add the missing Back-to-list link on the statutory rule detail (0.15 M1)` (61019a9c) |
| **M2** | `views/Localization.py:119,146` — the two singleton saves write an audit row with `{"verb": ...}` but no field diff, where `crud.py:219` passes `_changed(form)`. Audit fidelity only; no secret involved. | L6-M2 | **New in lane 6.** Fixer must choose: explicit diff dict, or promote `_changed` (importing a `_`-name across modules is itself a smell). | [x] fixed — **explicit diff dict** chosen: a local `_audit_changes()` twin in the view module, `crud._changed` left private. `fix(core): record the field diff on the two hand-rolled locale saves (0.15 M2)` (d84d0184), `…correct the _audit_changes call-site count from ~15 to ~75` (0e78ce8b) |
| **M3** | Trim the two computed pages' queries: `localization_overview` fetches `LocaleProfile` twice (`.first()` + `.exists()`); 6 COUNTs per page where 3 conditional aggregates would do; the profile's FKs are not `select_related`. | L4-M1/M2/M3 | Constant savings, not scaling. Fold into **one** pass. | [x] fixed — `perf(core): trim the two computed pages to one aggregate per table and one profile fetch (0.15 M3)` (36ffcd30) |
| **M4** | Dead context keys: `profile` is passed to the board and never used; `obj`/`is_edit` are passed to both form templates and never used. | L2-M1 | Harmless direction (the dangerous direction was checked and is absent). | [x] fixed — `chore(core): drop the dead context keys from the locale singleton and board renders (0.15 M4)` (5c3edeac) |
| **M5** | `contract-core-0.15.md:197` records `rtl_choices` labels that differ from the shipped ones. | L2-M2 | Doc-only. Fix the contract. | [x] fixed — `docs(core): correct the contract rtl_choices labels to the shipped ones (0.15 M5)` (5ab2f4a8) |
| **M6** | `badge-amber` used for neutral registry facts ("Observes DST", "Right-to-left") where `badge-slate`/`badge-info` would read as neutral. | L3-M3 | Valid classes; polish only. | [x] fixed — `style(core): read "Observes DST" as a neutral fact, not an amber warning (0.15 M6)` (e920ff8c), `…"Right-to-left"…` (e7b5d180) |
| **M7** | `localizationoverview.html:98-101` — a five-clause run-on that repeats `localizationboard.html:16` verbatim. Convert to a `<ul>`; let the board keep the "nothing is stored" line. | L3-M2 | Content is right; presentation only. | [x] fixed — `docs(core): turn the overview run-on into a four-bullet list and drop the board duplication (0.15 M7)` (11852be0) |

## No action — recorded so the decisions are visible

| # | item | why no action |
|---|---|---|
| **N1** | L5-I1: the `statutory_rule_*` views do not take the `tenant is None` redirect branch. | **Orchestrator error, not a defect.** I told lane 5 to expect it; the house norm is the opposite — **0 of 487** `crud_list` call sites guard it, and `party_list` (the reference view) is structurally identical. An empty register *is* the correct rendering for a superuser who sees no module data. Lane 5 said it filed it only because my brief asserted it. |
| **N2** | L5-M2: `messages.error` vs `messages.info` across the tenant-less branches. | Cosmetic, one word; nothing to fold it into once N1 is dropped. |
| **N3** | L4: `currencies_without_rates` under-counts if a rate exists on a now-inactive currency. | Accepted edge — the number answers "currencies the platform offers that this tenant has not rated", and an inactive currency is not offered. |
| **N4** | L5-M1: three junk dev-DB tenants (ids 423, 424, 70 — one with `slug=''`) predate this build. | Out of scope for 0.15; **escalated** rather than fixed, since a later test lane could trip on them. |
| **N5** | L6: a superuser changing a user's tenant via the Django admin can leave a stale `UserLocalePreference` whose next save 500s on the OneToOne. | Narrow, superuser-only, **no cross-tenant read or write** — every read is `filter(tenant=..., user=...)`. |
| **N6** | L3/L6: the sidebar shows admin destinations to members. | Pre-existing and app-wide — `resolve_nav` is role-blind for **every** module. Not a 0.15 regression. |
| **N7** | L6: `config/settings.py:16` defaults `DEBUG=True`. | Deployment configuration affecting every 500 in the app; no 0.15 view reads `settings.DEBUG`. |
| **N8** | L1/L2: the changeset ships zero tests. | That is **Phase 6**, which has not run yet — recorded as a plan item, not a defect. |

## Findings the review affirmatively cleared

Recorded because a clean verdict on a checked item is evidence, not silence:

- **No Critical in the security lane.** No cross-tenant read or write on any path; no missing tenant FK; no unscoped form queryset; no IDOR (`foreign pk → 404`, and the 404 does not mutate); no CSRF gap; no state-changing GET; no mass assignment of `tenant`/`user`; **no secret exists in this sub-module at all.**
- **`@require_POST` outermost on `statutory_rule_delete`** — 7.7's 405-not-403 ruling holds, confirmed statically *and* at runtime (anonymous GET → 405, member GET → 405, member POST → 403).
- **The two GLOBAL read-only registries are correct, not a disclosure** — the exposed data is ISO language codes and IANA zone names (public facts, identical for every tenant), there is no join to any tenant-owned table, and `accounting.currency_list` takes the same shape while being *less* restrictive. **By design, no finding.**
- **No N+1 anywhere**; every one of the 11 views is constant in query count with respect to row count (verified at 3 rows and at 303 rows).
- **Design-system compliance is fully clean** — 40 class tokens across the 9 templates, **0** missing from `theme.css`. The L33 badge/stat-icon regression has **not** recurred, on its fourth opportunity.
- **The referential spine is closed** — re-export blocks, the 11-route triangle, template paths, `{% url %}` names, `LIVE_LINKS` keys (byte-identical to the NavERP.md bullets) and the orphan sweep in both directions.
- **The seeder is idempotent** and the dev DB was left byte-identical by every lane that touched it.

## Fix order for the `code-fixer`

1. **C1** — the duplicate-name guard in `StatutoryRuleForm`. (Only Critical.)
2. **I1** — the three member-reachable templates, one pass.
3. **I3** — `TimeZone.offset_display` + the template.
4. **I4** — the seeder backfill.
5. **I2** — `_fx_rows`, using lane 4's A/B-verified 2-query form, and **rewrite the docstring** (the old rationale is false).
6. **M1–M7**, with **M3** as a single pass and **M5** a doc edit.

---

# FIXER'S NOTES — `code-fixer`

**All 12 findings are `[x] fixed`. None skipped.** Fixes landed one file per commit, in ID order,
Critical → Important → Minor.

## I1 — the pattern chosen, and why

**Hide**, using `{% if request.user.is_superuser or request.user.is_tenant_admin %}`.

The finding permitted either house pattern (route-where-a-member-page-exists, or hide). *Hide* was chosen because:

- it is the idiom the repo already uses in **313** template locations, and it is byte-for-byte the condition
  inside `apps/core/decorators.py:18` (`user.is_superuser or getattr(user, "is_tenant_admin", False)`) — so the
  member's view of the page and the gate that guards the destination can never disagree;
- it is the precedent set by the sibling member page `templates/core/my_preferences.html`, which ships a
  deliberately **empty** `.page-actions` and a breadcrumb that does **not** link the admin-gated
  `core:notification_overview` — the author made that page self-contained on purpose
  (`apps/core/navigation.py:93-94`).

The routing alternative was rejected on two grounds. Re-pointing "Regional settings" at
`core:user_locale_edit` makes the label and the destination disagree ("Regional settings" would open
"My Regional Settings"), and a "Cancel → `dashboard:home`" would send a member who opened the page from the
sidebar all the way home. Neither is needed: a member has no dead end once the dead controls are gone — the
sidebar and the browser Back both work, and the save now returns to the page itself (`core:user_locale_edit`),
not to the admin-gated overview.

Applied consistently across all three files: every admin-gated crumb renders as **plain text**
(`<span>Localization</span>`, never a link to an inaccessible page), and every admin-gated page action —
including `userlocale/form.html`'s **Cancel** and the body reference to Regional Settings — is hidden.
`localeprofile/form.html` is itself `@tenant_admin_required`, so its "Overview" action is legitimate and was
left alone.

## App-wide recommendation (clone family)

I1 is one instance of a condition that is **not** specific to 0.15: `resolve_nav` is role-blind, so *every*
admin-gated sub-module's page actions and breadcrumbs are rendered to members (see N6). This burn-down fixed
0.15's three pages only, deliberately, rather than forking one module out of step with the other ~12. A separate
app-wide pass over member-visible admin affordances is worth scheduling.

## Verification performed

Every probe writes inside `transaction.atomic()` and rolls back; before/after counts are printed.

| probe | finding | what it proves |
|---|---|---|
| `temp/probe_c1_dup.py` | C1 | create-duplicate **and** edit-duplicate both return **200 with the form error** (not 500) and leave the row unmutated; a legitimate new name and a legitimate rename both **302 and persist**; tenant-1 rule count 3 → 4 in-transaction → 3 after rollback |
| `temp/probe_i2_fx.py` | I2 | the old (fetch-all, dedupe in Python) and new (grouped `Max`, 2-query) `_fx_rows` produce **identical** output rows on the seeded tenant **and** on a synthetic 730-day history; the new shape issues exactly **2** queries |
| `temp/probe_i4_seed.py` | I4 | a forced NULL `base_currency` and two forced NULL `tax_code`s are **repaired** by a re-run, with **no row-count change** (no duplication); the India GST rule correctly stays without a `tax_code`; a second run is a no-op |
| `temp/probe_m2_audit.py` | M2 | both hand-rolled singleton saves now write a real `{field: new_value}` diff next to the `verb` marker |
| `temp/probe_15_render.py` | I1, I3, M6, M7 | all nine 0.15 pages return 200 with their expected content asserted for `admin_acme`; the three member-reachable pages contain **no admin-gated href** in their own chrome and body while the admin pages still return **403** to a member; the offset column shows `UTC+05:30` / `UTC-08:00` / `UTC+00:00` and no raw minutes |

**I3 is not a schema change.** `offset_display` is a `@property`, not a field:
`manage.py makemigrations --check --dry-run core` → *"No changes detected in app 'core'"*.

## Observed but NOT fixed (out of scope for this burn-down)

- **`contract-core-0.15.md` §3.3 and the two singleton rows of §3.2 are now stale.** §3.3 still describes
  `_fx_rows` as "One query, grouped in Python (… no subquery-tie bug)" and still lists a `profile` key on the
  board; §3.2 still lists `obj`/`is_edit` for `locale_profile_edit` and `obj` for `user_locale_edit`. I2 and M4
  changed all of that. Left alone because the contract is the *pre-build pinned spec* and its own convention is
  to record divergence in an **AS-BUILT CORRECTION** block, not to rewrite the pinned tables — and because only
  M5 (the `rtl_choices` label drift) was in the finding list. Worth a follow-up correction block.














