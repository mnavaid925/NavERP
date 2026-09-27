# Review — Sub-module 0.19: License & Subscription Administration (`apps/tenants`)

Range under review: `44c7de31...HEAD` (40 files, +5577/-5, 46 commits).
Reviewers run **one at a time**; each section below is that agent's verdict, appended on report. The
working tree was clean at review time (four untracked tool dirs are not part of the change), so
`git diff HEAD` is empty and every reviewer was pointed at the base commit.

---

## Pass 1 — `code-reviewer`

**Verdict: commit after fixing the Important band.** Tenant scoping, one-writer discipline,
decorator order and the L10 nullable-FK discipline are all correct, but the seeder ships a broken
context key, the numbering-reconciliation wiring the contract made mandatory was never done, three
board context keys are dead, and the seeder's per-entity guards collapsed to one.

### Important

- **I1 · `apps/tenants/views/UsageQuota.py:68` — the `consumption` context key is provably always
  `{}`.** `_consumption_by_subscription` keys its result by the **tuple** `(subscription_id, metric)`
  (`Boards.py:52-55`), so the bare-`subscription_id` lookup at line 68 can never match. Contract
  §3.4 pinned a `{metric: Decimal}` map for *this* subscription. The template documents the mismatch
  instead of fixing it, and a key nothing reads is a defect in its own right.
  **Fix:** `{m: t for (sid, m), t in _consumption_by_subscription(tenant).items() if sid == obj.subscription_id}`.
  **Verified by the reviewer and independently re-confirmed by the main session.**

- **I2 · `apps/core/settings_engine.py:159` — `LITERAL_PREFIX_MODELS` never gained the four new
  prefixes.** It still holds only `{"SINV": [...]}`. The contract made this "part of 0.19's
  wire-up, **not optional**", and all four model docstrings (`EntitlementFeature.py:66-67`,
  `PlanEntitlement.py:50`, `UsageQuota.py:70`, `LicenseAssignment.py:55`) cite that dict as the
  reason their prefix is discoverable. As shipped, `prefix_usage()` reports all four as
  `model_only` and never names the models — **the docstrings point at wiring that does not exist.**
  **Confirmed by the main session** (`settings_engine.py:159-161`). Flagged by the build agent and
  missed by the main session as single writer — an omission, not a defect in the build.
  **Fix:** append `"ENT"`, `"PE"`, `"UQ"`, `"SEAT"` entries.

- **I3 · `apps/tenants/views/Boards.py:156-157, 209` — three dead context keys.** `metric_choices`
  and `action_choices` (quota board) and `plan_choices` (renewal board) are passed but read by **no**
  template; neither board has a filter bar. That is the both-directions violation the same
  sub-module names as a defect. **Fix:** drop the three keys, or add the filter bar.

- **I4 · `apps/tenants/management/commands/seed_tenants.py:160` — one guard for all four entities,
  not four independent per-entity guards.** Contract §6.6 pinned four so "a partially-seeded tenant
  self-heals instead of being skipped wholesale". A tenant with features but no quotas/seats never
  self-heals, and the `grace_ends_on` backfill at `:163` is unreachable for it. The docstring at
### Minor

- **M1** — the `PlanEntitlement` docstring overstates enforcement: it says the duplicate guard fires
  "at the only place a user can create one", but `PlanEntitlementForm.clean()` (which reads
  `self.tenant`) is the real UI-path guard and the model's `clean()` short-circuits on the form path.
  The rule *is* enforced — the sentence is what overclaims. **Clone sweep:** same shape in
  `forms/EntitlementFeature.py:31`, `forms/UsageQuota.py:28`, `forms/LicenseAssignment.py:38`.

- **M2** — `seed_tenants.py:63` still ends at "tenants seed complete." with no tenant-admin login
  instructions and no "the superuser has no tenant" warning. Pre-existing from 0.1 and out of scope
  as a bug, flagged only because 0.19 added two more seeded surfaces and did not extend it.

### Done well

The nullable-FK discipline is exact, not approximate: every read of `PlanEntitlement.subscription` and
`LicenseAssignment.subscription` sits inside an `{% if %}` branch rather than a `|default:` filter
argument, and the reason is written at each site — exactly the L10 trap that shipped in 0.18, avoided
here. The one-writer discipline holds end to end: `breached_at`, `status`, `reclaimed_on` and
`reclaim_reason` are off every form, written only by their verb with an explicit `update_fields`,
and `readonly` in admin, with the verb name in `changes=` rather than the varchar(10) `action` (L41).

### Routing

- **performance-reviewer:** `UsageQuota.py:68` runs a whole-tenant grouped aggregate to produce a
  value that is always `{}`; `Boards.py:180-200` loads every tenant subscription unpaginated and
  loops in Python; `_seat_summary` runs three queries where the contract says one;
  `PlanEntitlement.Meta.ordering` includes `feature__code`, forcing a join on every ordered query.
- **security-reviewer:** nothing outstanding — all 24 views filter `tenant=request.tenant`, all four
  forms inherit `TenantModelForm` and its FK scoping covers `feature`/`subscription`/`user`, and the
  nullable-`User.tenant` paths are narrowed in the list filter, the board and the seeder. One item for
## Pass 2 — `explorer`

**Headline: the honesty band is CLEAN and stronger than the contract asked.** All 14 templates were
grepped for `automatic|renews|charge|blocks|throttl|email|notify|versioning|grandfather|enforce|
consult`; **every hit is a negation or a correctly-derived state.** No template claims a declined
capability. All ten declines land in visible prose exactly where contract §5.4 put them.

**Bullet coverage: 4 of 5, not 5 of 5.** Bullets 1/2/3/5 each get a 0.19-built page. **Bullet 4 is
served entirely by 0.1's tables** (`SubscriptionInvoice` + `stripe_webhook`) with **proration declined**
— the only decline among the five.

### Findings

- **E3 · `apps/tenants/models/Subscription.py:30` — `auto_renew = BooleanField(default=True)` is a
  data-honesty defect, and the most important finding from this pass.** Every pre-existing
  subscription is silently stamped "auto-renews" by the migration, an intent it never expressed. The
  renewal board then renders a decision nobody made. This is the L52 failure class (a confident state
  that was fabricated) arriving through a column default.
  **Fix:** default `False`, or `null=True` + backfill, so absence stays absence.

- **E1 · `LicenseAssignment.module_slug` is unvalidated free text.** `EntitlementFeature.code` has a
  `CODE_VALIDATOR` pinning its case; `module_slug` has nothing, so `"Accounting"` and `"accounting"`
  are two different values for one module, and the register quietly stops matching
  `core.ModuleAccessScope.module_slug` — the consistency `models/LicenseAssignment.py:62-63` claims.
  **Fix:** normalise in `clean()` and offer a `<select>` of the real slugs on the form.

- **E2 · `templates/tenants/subscription/form.html` is missing the proration decline.** 0.19 added
  `auto_renew`/`grace_ends_on` to that very form, so it is 0.19's own page to be honest on, and the
  one-line decline is absent.

- **E5 · the seat count is recorded THREE ways with no page stating how they relate** —
  `Subscription.seats` (10, `seed_tenants.py:69`, shown in the renewal board's Seats column), the
## Pass 3 — `frontend-reviewer`

**Clean bands (verified by grepping `theme.css`, not by eye): L33 badges, L2 comment leaks, L10
nullable-FK reads, filter bars on all four lists, and no invented theme classes.** Zero `{#` occurrences
in all 14 files. All six badge modifiers used exist; no semantic `-success/-warning/-danger` anywhere.
All three pk filters use `|stringformat:"d"`, none uses `|slugify`. Every `{% empty %}` colspan matches
its real column count.

### Critical

- **C1 · UTF-8 mojibake renders as visible garbage on 3 of the 14 pages, corrupting pinned honesty
  prose.** `licenseassignment/detail.html:19,122,130` · `quota_board.html:123,169` ·
  `renewal_board.html:142,181`. The byte sequence `E2 80 94` (em dash) was decoded as cp1252 and
  re-encoded, producing `â€"`.
  **Confirmed by the main session at the byte level** — `quota_board.html` begins with a UTF-8 BOM
  (`EF BB BF`) and the string `â€"` is present, so line 169 renders as
  *"<strong>L36 â€" which rows are 0.1's.</strong>"*. That is **the L36 honesty note itself**, garbled
  in a browser. Two more sites sit inside JS `confirm()` strings and two inside `title=` tooltips.
  The BOM does not 500 today (it becomes a leading TextNode `{% extends %}` never renders) — a latent
  trap, not a live bug — but it is the fingerprint of the same bad write.
  **Fix:** use entities, which the surrounding prose in the same files already does and which is
  encoding-proof: `â€"` → `&mdash;`, `anyoneâ€™s` → `anyone&rsquo;s`, `Â·` → `&middot;`; strip the BOM
  from all three files. 6 more instances sit inside `{% comment %}` blocks — invisible today, but a
  reader grepping the file for `—` finds nothing. No other file in the 40-file changeset has a
  non-ASCII byte.

### Important

- **I1 (the routed decision) · DROP the three dead context keys. Do NOT build the filter bars.**
  Both boards already document the decision in their own `{% comment %}` headers
  (`quota_board.html:24-25`, `renewal_board.html:22-23`): *"No filter bar, deliberately: this is a
  whole-tenant roll-up, and a filter that silently changes what '3 breached' means is worse than no
  filter at all."* The author made the call and wrote it down; the view simply did not follow through.
  A filter would be **actively wrong** here, not merely absent: all headline numbers are computed over
  the **unfiltered** set, so `?metric=api` would still print "2 marked as breached" above a table
  containing zero breached rows — and the board's value is that the number and the row are the same
  fact. Doing it honestly is a rewrite, not a template change.
  **Fix:** delete the three keys in `Boards.py:156-157, 209`.

- **I2 · four duplicated hand-rolled Delete blocks across the detail/board templates** should use the
## Pass 4 — `performance-reviewer`

**All four routed items verified real.** Bands: Critical 1 · Important 6 · Minor 4.

### Critical

- **C1 · `apps/tenants/views/PlanEntitlement.py:58-60` — N+1 on the grant detail page.** The
  `overrides` queryset has no `select_related`, while `planentitlement/detail.html:130` reads
  `grant.subscription.pk` and `.get_plan_display` **once per row**. The queryset filters
  `subscription__isnull=False`, so every row is *guaranteed* to have a subscription and *guaranteed*
  to fire a query — this is an N+1 on any page with ≥1 override, not a possible one. At the page's own
  50-row cap that is **51 queries where 3 suffice**, so the worst case is the designed case.
  **Fix:** add `.select_related("subscription")` (a LEFT OUTER JOIN on a nullable FK, free here).
  The same view already does this correctly twice — `obj` is `select_related("feature","subscription")`
  (`:51`) and `entitlementfeature_detail:54` selects `subscription` on its grants — which is what makes
  this a defect rather than a style choice. `plan_grants` needs nothing: its row loop touches only local
  columns. **Regression guard:** `django_assert_max_num_queries(3)` on `planentitlement_detail`.

### Important

- **I1 · `Boards.py:180-200` — the renewal board is unpaginated and its headline counts derive from the
  rows it loads.** Query count is a clean 1 (not an N+1), but the row count is unbounded and
  `Subscription` only ever grows. **The correction to the obvious fix is the valuable part:** capping at
  `[:200]` and leaving the counts as Python `len()` would be *worse* — the tiles would silently start
  reporting the cap instead of the workspace, which is the exact "confident lie" pass 3 ruled out for
  filter bars. The counts must move off the row list (aggregates), and the cap must be stated on the page.
- **I2 / I7 · `licenseassignment_detail` runs 6 queries where 2 suffice**; two aggregates are
  recomputed per page that the board helper already computes.
- **I6 · `usagequota_detail` runs 3 where 1 suffices** (two avoidable).
- Remaining Important items cover the seeder's per-tenant cost and the dropdown querysets.

### Minor

M1 (the seat list is over-selected — harmless), M3 (the one drop-in seeder query win), M4 (two unbounded
*dropdown* querysets), plus two more the reviewer enumerated.

### Verified clean — the N+1 sweep, with evidence

**All four list views are correct.** Each row loop was compared against its `select_related`:

| View | Row loop reads | Verdict |
## Pass 5 — `qa-smoke-tester` (runtime; report-only, no fixes applied)

**Verdict: 348 checks across 8 probe passes, 0 failures. No Critical, no Important.** 0.19 holds up
under runtime exercise; the one-writer discipline is real and the empty-state boards do not crash.
Probes ran against the **MySQL** dev DB through the in-process test client with a
`got_request_exception` signal attached, so **zero** page 500'd silently behind a 200.

| Pass | Scope | Checks | Fail |
|---|---|---|---|
| A1–A4 | four entities' full create→detail→edit→verb→delete lifecycle | 91 | 0 |
| B | the two POST-only verbs + one-writer discipline | 35 | 0 |
| C | form POST **cannot** forge the one-writer fields | 16 | 0 |
| D | the three duplicate guards, create **and** edit | 25 | 0 |
| E | junk params, page 2, both boards, empty workspace | 57 | 0 |
| F | cross-tenant IDOR on all 24 routes, GET **and** POST | 69 | 0 |
| G/H | subscription form columns, the dead `consumption` key, seeder, nav | 72 | 0 |

**Every lifecycle step asserted the DATABASE, not the status code** — a full concrete-field snapshot
before and after plus a set-diff, so an edit that changed *more* than intended would have failed. Edits
changed exactly the intended fields and `number` never moved. `GET` on a delete URL was confirmed
**not** to have deleted.

**One-writer discipline proven by forged POSTs against the real endpoints** (the part that matters —
a guard that 500s or silently no-ops would look identical on a naive check):
- `POST breached_at=2020-01-01` to `usagequota_edit` → **302, other fields saved** (`quota_limit`
  100→999, `action_on_breach`→`block`), `breached_at` still `NULL`.
- `POST status=revoked` at an **active** seat → still `active`; stamps still `NULL`/`''`.
- The reverse attack the form docstring names: `POST status=active` at a **reclaimed** seat → still
  `reclaimed`, and the seeded evidence stamps survived intact.
- The four fields are **absent from every rendered form** — asserted on the HTML, not inferred from
  `Meta.fields`.

**Verb gates all hold, in the right order.** GET → 405; non-admin POST → 403; **non-admin GET → 405,
not 403** — that is the decorator order working, `@require_POST` outermost so the method check precedes
the role check; cross-tenant → 404.

### Minor

- **M8/M9 · the seeder cannot self-heal a row it already created** (the pass-1 I4 guard, now with
  runtime evidence): delete a tenant's `UsageQuota` and re-run, and the seeder creates nothing
  because it still sees features. This is the exact self-heal property contract §6.6 asked for.
- One new minor observation on the seeder's output and the acme row restored by hand.

## Consolidated finding list (deduped, Critical → Important → Minor)

> ### ✅ FIXER REPORT — every finding closed
>
> **1 Critical, 16 Important, 6 Minor — 3 fixed, 3 deliberately skipped with the reason recorded.**
> 34 commits, one file each. The three skips are M3 (the four duplicated Delete links follow the
> house pattern and are recorded in code), M4 (icon-only buttons inherit the house pattern; worth an
> app-wide sweep) and M6 (the seeder's ~94 queries are inherent to the app-wide `next_number`-inside-
> `save()` design, not a 0.19 per-request path). "Skipped" means declined **on the record with a
> reason**, not overlooked — so this reads as 3 fixed / 3 justified, NOT "all resolved".
> Gates after the last fix: `manage.py check` clean · `makemigrations --check` "No changes detected" ·
> `audit_integrity.py` **6/6** (still `module 0: 2 catalogued but NOT built -> 0.20, 0.21`) ·
> `seed_tenants` idempotent · **post-fixer regression: 16/16 pages 200 with content, cross-tenant IDOR
> 404, zero comment leaks, all three re-encoded files free of BOM and mojibake, and the `auto_renew`
> tri-state round-tripping `true→True`, `false→False`, `unknown→None`.**
>
> Three notes a reader needs, because the fix differs from what a first reading would assume:
>
> 1. **I10 was NOT fixed with `default=False`.** The fixer rejected that as the wrong fix rather than a
>    cheaper one: it stamps every pre-existing row with the *opposite* unexpressed decision, and since
>    nothing in NavERP reads the value (no scheduler), `True` and `False` are equally arbitrary — only
>    `NULL` ("nobody has said") is a true statement. It became a **three-state** field with a
>    `NullBooleanSelect` subclass, plus **migration `0006`**. A checkbox would have been two-state and
>    silently converted every unanswered question into a declined one.
> 2. **I3 was a DELETION**, decided by the frontend pass, not a build: both boards deliberately have no
>    filter bar and say so, and a filter would have split the stat cards from the rows beneath them.
> 3. **The `code-fixer` agent ran out mid-I10 and left the tree broken** (`TypeError:
>    NullBooleanSelect.__init__() got an unexpected keyword argument 'choices'` — its `choices` are a
>    class attribute). The main session finished I10–I16, M1–M2 and the three doc findings.
>
> Marked per finding below as `[x] fixed` / `[~] skipped — reason`.

IDs assigned for the `code-fixer`. Cross-references kept so a fix can be checked against the pass
that raised it. **No security Critical/High/Medium exists; the only Critical is the encoding one.**

### Critical

- **C1** `[x] fixed` (pass 3, confirmed byte-level by the main session; pass 6 S2 agrees) — **UTF-8
  mojibake + BOM in 3 of 14 templates**, corrupting 7 visible sites including the L36 honesty note on
  both boards and two JS `confirm()` strings: `licenseassignment/detail.html`, `quota_board.html`,
  `renewal_board.html`. Re-encoded with HTML entities and the BOM stripped; verified by a
  post-fixer regression asserting `BOM=False, mojibake=False` on all three files at the byte level.
  **6 visible + 6 in-comment sites cleared.**

### Important

- **I1** `[x] fixed` (pass 1; **confirmed at runtime by pass 5**) — `views/UsageQuota.py:68`: `consumption`
  was **always `{}`** because `_consumption_by_subscription` keys by the tuple `(subscription_id,
  metric)`. The detail page now builds the per-metric map the contract pinned and renders it, replacing
  the template comment that had documented the mismatch.
- **I2** `[x] fixed` (pass 1; pass 5 confirmed it unwired) — `apps/core/settings_engine.py:159`:
  `LITERAL_PREFIX_MODELS` gained `ENT`, `PE`, `UQ` and `SEAT`, so `prefix_usage()` names the four models
  instead of reporting the prefixes `model_only` — which is what the four model docstrings claimed.
  **Flagged by the build agent and missed by the main session as single writer.**
- **I3** `[x] fixed` (decision from pass 3; pass 5 confirmed dead) — **DROPPED** `metric_choices`,
  `action_choices` and `plan_choices` from `Boards.py`, and the quota board's `{% comment %}` header now
  records the dropped keys and why. No filter bar was built: a filter would have split the stat cards
  from the rows beneath them, and both boards already document that decision.
- **I4** `[x] fixed` (pass 1; **pass 5 gave it runtime evidence**) — `seed_tenants.py`: **four independent
  per-entity guards**, so a tenant with features but no quotas/seats self-heals instead of being
  skipped wholesale. Confirmed by the second run printing "0.19 licensing already complete".
- **I5** `[x] fixed` (pass 1; pass 6 noted the admin as the reachable path) — `Boards.py`: `user__tenant`
  now narrows **all five** seat numbers off a single grouped query, so the numbers rendered side by side
  cannot disagree for a null-tenant user.
- **I6** `[x] fixed` (pass 1; pass 5 verified at runtime) — `views/LicenseAssignment.py`:
  `licenseassignment_edit` now refuses a non-active seat **in the view**, not merely hiding the button.
- **I7** `[x] fixed` (pass 4, raised as its Critical) — `views/PlanEntitlement.py`: `overrides` gained
  `select_related("subscription")`, killing an N+1 that the `subscription__isnull=False` filter made
  *guaranteed* rather than possible. 51 queries where 3 suffice → 3.
- **I8** `[x] fixed` (pass 4) — `Boards.py`: the renewal board's headline counts became **aggregates over
  the whole workspace** and the row list is capped at 200, with the cap **stated on the page**.
  Deliberately NOT "cap the queryset and leave `len()`", which would have made the cards report the cap.
- **I9** `[x] fixed` (pass 4) — `licenseassignment_detail` now `select_related`s both FKs the template
  walks (6 → 2 queries) and `usagequota_detail` `select_related`s the non-nullable `subscription` (3 → 1).
- **I10** `[x] fixed` (pass 2) — `auto_renew` became a **three-state** `BooleanField(default=None,
  null=True)` plus a `NullBooleanSelect` subclass on the form, and **migration `0006`**. `default=False`
  was rejected as the wrong fix, not a cheaper one (see the fixer report). The renewal board forwards the
  value **raw** — the old `getattr(..., False)` coerced "nobody has said" into a decline. Verified:
  `true→True`, `false→False`, `unknown→None`.
- **I11** `[x] fixed` (pass 2) — `module_slug` is normalised in **both** `clean()` and `save()`. `clean()`
  runs first and validates against the *stored* string, so without it a form posting `Accounting` would
  pass the duplicate guard and then fail the database `unique_together` — a 500 instead of a field error.
  Verified: `"  Accounting  "` stores as `"accounting"`, and the uppercase duplicate is a keyed form error.
- **I12** `[x] fixed` (pass 2) — `templates/tenants/subscription/form.html` now states the proration
  decline and that `auto_renew` records an intent no scheduler acts on. Verified on the rendered page.
- **I13** `[x] fixed` (pass 2) — `NavERP.md`'s per-bullet L36 record now names 0.19 as **4 of 5** and
  states that bullet 4 is served by 0.1's `SubscriptionInvoice` + webhook with proration declined.
- **I14** `[x] fixed` (pass 2) — `NavERP-ERD.md`'s as-built foundation schema now carries all four 0.19
  models and both `Subscription` columns, with the L36 reconciliation, the `SEAT-` prefix, the inert
  `unique_together`, the UNMETERED rule and the three-state `auto_renew`.
- **I15** `[x] fixed` (pass 6, S1) — a `clean()` on all three models refuses a subscription from another
  workspace, **and** `TenantScopedSubscriptionMixin` scopes the picker in the three licensing admins
  (a superuser, `tenant=None`, now gets an empty picker). Two independent defences; the error is keyed on
  `subscription`, a field the forms have. Verified: all three models refuse the cross-tenant pair, and a
  same-tenant pair still validates.
- **I16** `[x] fixed` (pass 2) — the seat register now carries a "Three seat numbers, deliberately not
  reconciled" panel naming the register total, the `seats` entitlement and `Subscription.seats`, and
  stating that a 75-seat override over a 50-seat plan is a legitimate record rather than a conflict.

### Minor

- **M1** `[x] fixed` (pass 1) — the `PlanEntitlement` docstring no longer claims the duplicate guard fires
  "at the only place a user can create one". It now states that **both** `clean()` and the FORM enforce it,
  and that the model's branch short-circuits on the form path. The rule was always enforced; the sentence
  claiming otherwise was the defect.
- **M2** `[x] fixed` (pass 1) — `seed_tenants` now prints the tenant-admin logins and the
  "the superuser `admin` has **no tenant**, so every module page is empty for it by design" warning.
  Verified on a real run.
- **M3** `[~] skipped — deliberately, with the reason recorded in code.** The four duplicated Delete
  blocks stay hand-rolled: the house `partials/pagination.html` shows there is **no** shared
  delete-confirm partial to reuse, so extracting one would mean authoring a new shared partial for four
  call sites — a wider change than the review asked for, in a file shared with every other module.
- **M4** `[~] skipped — deferred as cosmetic polish.** The icon-only buttons inherit the house pattern's
  missing `aria-label`; **0.19's filter bars are already better than that pattern** (every `<select>`
  and search input carries a descriptive label — the frontend pass singled this out as the one thing it
  most wants kept). Adding labels only to 0.19's detail pages would make 0.19 *diverge* from every
  sibling detail page. Worth doing as an app-wide sweep, not inside this sub-module.
- **M5** `[x] fixed` (pass 2, E4) — the four detail views' use of `render()` with a hand-set `obj` is now
  the documented, verified contract (they call `crud_detail`, which `views/_common.py` does **not**
  export — that was the Phase 3.5 500). Pinned for Phase 6.
- **M6** `[~] skipped — not actionable here.** The seeder's ~94 queries are inherent to the app-wide
  numbering design (`next_number` mints inside `save()`, which `bulk_create` bypasses); rewriting that is
  a numbering decision out of scope for 0.19. Recorded so it is not mistaken for a per-request hot path.

**Query-count regression guards requested by pass 4, for Phase 6:**
`planentitlement_detail` → 3 (I7) · `licenseassignment_detail` → 2 (I9) · `quota_board` → 2 and
`renewal_board` → 2 (I8), pinning the constant-query property.

### Confirms I2 and I3 stand (not fixed by anything)

`LITERAL_PREFIX_MODELS` is still unwired, so `prefix_usage()` still reports all four prefixes as
`model_only` — **I2 stands unverified at runtime** (it is a `core` settings surface, not a 0.19 route).
The three dead board context keys are **confirmed dead**: the rendered HTML contains **no `<select>`
element at all** on either board.

### What it could NOT verify (stated, so a clean report does not overstate itself)

MySQL only (no SQLite, so the NULL-distinct claim in `PlanEntitlement`'s docstring is taken on the
author's word — though the *consequence*, that the form guard is load-bearing, was confirmed); no live
socket; `DEBUG=False`; no concurrency (the `save()` retry loops were never triggered); no mail path;
**Django admin not exercised — and the admin is not tenant-scoped, so pass-1 I5's null-tenant-user
concern is reachable there**; no money surface by design; seeded content swept for acme plus one
purpose-built empty tenant, not all ten workspaces.

---

|---|---|---|
| `entitlementfeature_list:20` | local columns only — **no FK** | 2 queries, none needed |
| `planentitlement_list:22` | `obj.feature.*`, `obj.subscription.*` | covered |
| `usagequota_list:19` | `obj.subscription.*` | covered |
| `licenseassignment_list:33` | `obj.user` (local `email`), two local-field properties | covered (over-selected) |

- **Pagination:** all four lists go through `crud_list` at `per_page=15`; filters and search are applied
  **before** `paginate()` (`crud.py:132-180`); nothing is `list()`-ed to count or slice;
  `get_page()` handles an out-of-range `?page=`. **Page 2 is safe on all four.**
- **Decimal arithmetic — clean, no float coercion anywhere.** Both `quantity` and `quota_limit` are
  `DecimalField`; `Sum()` returns `Decimal`; `consumed / limit * 100` is Decimal÷Decimal and is
  `int()`-truncated and capped before reaching a template. **The quota board's arithmetic is the best
  code in the change.**
- **Derived-property discipline holds:** `is_expired`/`is_reclaimable` are cheap local-field facts, the
  seat *count* is correctly kept out of the model, and `overridden_features` is a dict comprehension
  over an already-fetched list rather than a per-row `.filter()`.
- **The seeder's ~94 queries are inherent to the app-wide numbering design** (`next_number` mints in
  `save()`, which `bulk_create` bypasses), not to 0.19. A re-run costs 2 queries/tenant because the
  guard short-circuits. Recorded so it is not mistaken for a per-request hot path.

---

  shared partial the house uses rather than four copies.

### Minor (M1–M5)

Polish: aria-labels on the icon-only action buttons (the house pattern has the same gap);
`usagequota/detail.html` header omits Back-to-list that the other three detail pages carry; and
further small consistency items the reviewer enumerated.

### Done well — and the standard to keep

The filter-bar accessibility work beats the house pattern **without being asked**: every `<select>` in
all four new list templates carries a descriptive `aria-label` (`"Metric"`, `"Action on breach"`,
`"Breach state"`, `"Privilege type"`, `"Holder"`, `"Module"`) and the search inputs carry
`aria-label="Search"`. The `usagerecord` reference has **zero** labelling on all five of its controls.
Four filter bars, nineteen controls, all named, done consistently — the standard the next sub-module
should be measured against.

---

  `seats` `EntitlementFeature` granted 3/10/50/500 per plan with a **75** subscription override, and
  the 5 active rows in the seat register. Nothing asserts they agree and nothing says they are
  unrelated; the seat register's `subscription` FK puts the two registers one click apart. A coverage
  gap rather than an overclaim — but a reader will assume they agree.

- **E6 · `NavERP-ERD.md:596-604` is now wrong about the model 0.19 edited** — omits the four new
  models and `Subscription`'s two new columns, on a section `NavERP.md:111-113` names as the schema
  authority. Pre-existing (0.1's `UsageRecord` is already missing), but 0.19 widened the gap.

- **E7 · `NavERP.md:100-106` has no 0.19 line.** That paragraph is the repo's L36 record of how many
  of 5 bullets each *built* sub-module maps. 0.19 has a `LIVE_LINKS` entry and is absent from it. Its
  real verdict is **4 of 5** (bullet 4 served by 0.1, proration declined) — `navigation.py:301-306`
  already says this in code; the document a reader opens does not.

- **E4 · the contract has no ruling recording that `views/_common.py` exports no `crud_detail`** and
  that the four 0.19 detail views therefore use `render()` with a hand-set `obj`. Phase 6 must pin
  the real context names, not the helper's.

**Phase 7 close-out is correctly outstanding** (`.claude/skills/tenants/SKILL.md` does not exist —
Module 0 has no per-app skill; `README.md:173-181` and `NavERP.md:61` still read *0.19–0.21 unbuilt*).
That is Phase 7's job, not a finding. Only **E6** and **E7** misstate something a reader would act on.

---

  its own eye: `LicenseAssignment.subscription` is a tenant-scoped form field but the model row is not
  tenant-consistent at the DB level, so a cross-tenant pairing is constructible through unscoped admin.
- **frontend-reviewer:** the two boards have no filter bar, which is what makes I3 either a delete or
  a build — the call is a UX one.

---

  `:145` and the module docstring at `:3` both claim "per-entity guards" — the prose overstates the
  code. **Fix:** guard each of the four blocks independently, or correct the prose.

- **I5 · `apps/tenants/views/Boards.py:79-85` — `_seat_summary` applies `user__tenant=tenant` to the
  `active` count only.** `expired`, `reclaimed`/`revoked` and `total` omit it, so the five numbers
  rendered side by side on the seat detail page stop agreeing when a row holds a null-tenant user
  (reachable via Django admin, which is not tenant-scoped). The helper's docstring calls the clause
  "REQUIRED, not defensive". **Fix:** carry the clause on all four numbers, or restate it.

- **I6 · `apps/tenants/views/LicenseAssignment.py:85-89` — `licenseassignment_edit` has no
  view-level guard** while the detail template hides the edit control for a non-active seat. Hiding
  a button does not stop a direct POST. **Fix:** enforce the same rule in the view.

