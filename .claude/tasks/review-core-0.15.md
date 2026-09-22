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

