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



