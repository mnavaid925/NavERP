# Review Record — Sub-module 8.13: Marketing Alignment & Attribution

**Module**: Module 8 — Sales Management System (`apps/sales/`)
**Sub-module**: 8.13 Marketing Alignment & Attribution
**Review window**: `386a2b27a38fb2589f69ddb287976cc2302ea332` (BASE) → `HEAD`
**Changeset**: 48 new files + 10 edited shared files, ~9.3k insertions
**Contract under review**: `.claude/tasks/contract-sales-8.13.md`
**Plan**: `.claude/tasks/todo.md` · **Research**: `.claude/tasks/research-sales-8.13.md`
**Gap register**: `.agents/tasks/gaps-sales-8.13.md`

> ### ⚠️ Review scope is BY PATH, not by commit range
>
> A **concurrent session** is working in this same checkout on the same `main` branch (it is
> building 8.12 and writing the 8.10/8.11 test files). Three of its commits
> (`c7871819`, `04884feb`, `ab5a19a8`) landed inside the `386a2b2...HEAD` range, so the raw
> commit range is **not** a valid review scope — it contains another session's work.
>
> **Review ONLY these paths:**
>
> | Path | What is in scope |
> |---|---|
> | `apps/sales/models/MarketingAlignment/` | 5 entity files, 6 model classes |
> | `apps/sales/forms/MarketingAlignment/` | 5 form modules |
> | `apps/sales/views/MarketingAlignment/` | 5 entity view modules + the console view |
> | `apps/sales/urls/MarketingAlignment/` | 6 url modules |
> | `apps/sales/models/__init__.py` | the 8.13 re-export block only |
> | `apps/sales/forms/__init__.py` | the 8.13 re-export block only |
> | `apps/sales/views/__init__.py` | the 8.13 re-export block only |
> | `apps/sales/urls/__init__.py` | the 8.13 mount only |
> | `apps/sales/admin.py` | the 8.13 admin registrations only |
> | `apps/sales/management/commands/seed_sales.py` | `_seed_marketing_alignment` + the 8.13 call/imports/output only |
> | `apps/sales/migrations/0023_attributiontouchpoint_campaignattribution_and_more.py` | the whole file |
> | `apps/core/navigation.py` | the `LIVE_LINKS["8.13"]` entry only |
> | `templates/sales/marketingalignment/` | all 18 templates |
>
> **Out of scope — do not review, do not comment on, do not fix:** anything under
> `apps/sales/tests/` (owned by the concurrent session), and the 8.10 / 8.11 / 8.12 work.
> A finding that is really about another session's file is not a finding against 8.13.

---

## Review sequence (CLAUDE.md Phase 4 — six reviewers, ONE AT A TIME)

Each reviewer is read-only: it never edits code and never commits. Findings are appended below as
each one reports. When all six have reported, the file is deduped, sorted
**Critical → Important → Minor**, and each finding is given an ID (`C1`, `I3`, `M7`).

| # | Reviewer | Scope | Status | Findings |
|---|---|---|---|---|
| 0 | `qa-smoke-tester` (Phase 3 gate) | rendered pages, filters, pagination, IDOR, content | **done** | 4 (I1, I2, M1, M2) — all fixed in the main session |
| 1 | `code-reviewer` | correctness, contract drift, Django idioms | pending | — |
| 2 | `explorer` | code/structure mapping, duplication, dead paths | pending | — |
| 3 | `frontend-reviewer` | templates, design system, filters, accessibility | pending | — |
| 4 | `performance-reviewer` | queries, N+1, indexes, aggregation | pending | — |
| 5 | `qa-smoke-tester` | rendered pages, filters, pagination, IDOR | pending | — |
| 6 | `security-reviewer` | tenant isolation, IDOR, injection, data exposure | pending | — |

---

## Phase 3 smoke gate — `qa-smoke-tester` pass (2026-10-19)

The Phase 3 gate ran an independent read-only verification against the contract (23 URLs, content
assertions, leak markers, junk params, page 2, cross-tenant IDOR, FK-select scoping,
cross-tenant POST rejection, the console model selector, and `check` / migration drift).

**Result: all 9 functional checks PASSED** — every page renders 200 with the right content, no
`{#` / `{% comment` leak markers, no 500 on hostile query strings, page 2 renders and preserves
active filters, 12/12 cross-tenant URLs return **404**, 19 FK selects across the 6 create forms
offer **0** foreign-tenant pks, a cross-tenant FK POST creates **0** rows, and the console rollup
genuinely changes with the model (`first_touch` $19,800 / `last_touch` $13,200 / `linear` $13,000
on the leading campaign).

**The gate FAILED on contract conformance** with 4 findings. All 4 are fixed below.

### Findings

| ID | Severity | Finding | Status |
|---|---|---|---|
| `I1` | Important | **Touchpoint list had no `lead` filter control.** The view delivered the contract-pinned `leads` context key and honoured `?lead=<pk>` server-side, but the template never rendered a `<select name="lead">` — so the journey-identity dimension was unreachable from the UI. The template's own clear-filters guard and pagination links already referenced `active_filters.lead`, proving it was a dropped control, not a scope decision. | **[x] fixed** |
| `I2` | Important | **Content-engagement list had no `campaign` filter control.** Same shape as I1: the view delivered the contract-pinned `campaigns` context key and honoured `?campaign=<pk>`, but no `<select name="campaign">` was rendered — "which campaign drove this engagement" had no UI path, and the clear-filters guard and pagination links already referenced `active_filters.campaign`. | **[x] fixed** |
| `M1` | Minor | **Touchpoint detail view omitted the contract-pinned `attributions` context key.** Contract §4.2 pins `{"obj", "touchpoint", "attributions"}`; the view passed only `{"obj", "touchpoint"}`. The template did not consume the key either — it showed only the aggregate model property `obj.attributed_revenue`, so the per-model credit breakdown was invisible. No blank region, contract drift only. | **[x] fixed** |
| `M2` | Minor | **Contract named the migration `0022_marketingalignment`; the applied file is `0023_attributiontouchpoint_campaignattribution_and_more.py`** (0022 was taken by `0022_customersuccess_indexes`). Documentation drift only — `makemigrations --check` was clean and `showmigrations` reported every sales migration `[X]`. | **[x] fixed** |

### Fixes applied (main session — Phase 3 drift, not Phase 4 review findings)

- **I1** — `templates/sales/marketingalignment/attributiontouchpoint/list.html`: added the
  `lead` select (options from the `leads` context key, `|stringformat:"d"` pk comparison, and
  `active_filters.lead` reflected as `selected`); filter grid re-laid out to `lg:grid-cols-4`
  for the now-seven controls.
- **I2** — `templates/sales/marketingalignment/contentengagement/list.html`: added the
  `campaign` select on the same pattern; filter grid re-laid out to `lg:grid-cols-4`.
- **M1** — `apps/sales/views/MarketingAlignment/AttributionTouchpoints.py`: the detail view now
  passes `attributions` (the touch's credit rows under every model, `select_related("computed_by")`).
  `templates/sales/marketingalignment/attributiontouchpoint/detail.html` gained a **"Credit by
  Attribution Model"** table that consumes it, so the key is live rather than decorative.
- **M2** — `.claude/tasks/contract-sales-8.13.md`: the migration reference corrected to
  `0023_attributiontouchpoint_campaignattribution_and_more.py`, with the reason recorded.

### Environment note (not a 8.13 defect)

A **concurrent session** is building sub-module **8.12** in this same checkout on the same
`main` branch. It owns `apps/sales/tests/conftest.py` and
`apps/sales/tests/test_customersuccess_models.py`, and it landed three commits inside the
`386a2b2...HEAD` range. 8.13 never touched `apps/sales/tests/` — which is also why Phase 6's
test-writing phase was skipped rather than contended (see `GAP-sales-8.13-09`).

---

## Phase 4 review passes

### `code-reviewer` — **C1: oversized pk in a filter parameter → 500 (Critical)**

Found while running the 8.12 session's own probe output against 8.13's identical pattern.

**Where:** all **10** pk-valued filter parameters across the five 8.13 list views —
`AttributionTouchpoints.py` (`campaign`, `lead`), `CampaignAttributions.py` (`campaign`),
`MqlHandoffs.py` (`campaign`, `owner`), `ContentEngagements.py` (`content`, `account`,
`campaign`), `MarketingEvents.py` (`owner`, `campaign`).

**What was wrong.** Each guard read:

```python
campaign_id = request.GET.get("campaign", "").strip()
if campaign_id and campaign_id.isdigit():
    qs = qs.filter(campaign_id=int(campaign_id))
```

`.isdigit()` is **not** a safety check. `?campaign=999999999999999999999` (21 digits) passes the
digit test, `int()` converts it, and the DB driver then raises
`OverflowError: Python int too large to convert to SQLite INTEGER` → an uncaught **500**.

**Why it matters.** The value is **harmless on MariaDB** — the production database returns
"no rows" and the page renders. It is **not** harmless on SQLite, and the entire NavERP test
suite runs on SQLite in-memory. So the bug is invisible in the running app and becomes a hard
500 under the test database, and in any future deployment on SQLite. The Phase 3 smoke gate
missed it because its hostile-input check used *non-numeric* junk (`?campaign=abc`), which the
old guard already handled — the oversized-numeric case was only reachable by running the same
views against SQLite.

**Fix applied** (new shared helper `apps/sales/views/MarketingAlignment/_common.py`):

```python
MAX_PK = 2**63 - 1
MIN_PK = -(2**63)

def pk_from_param(value):
    """Return an int pk for a GET parameter, or None when it cannot possibly be one."""
```

`None` means "do not filter by this parameter" — an empty value, a non-numeric value, or a value
outside the int64 range — so the filter falls back to the unfiltered list, which is the same
outcome as an unknown id and is never an error. All 10 call sites now use it; the contract pins
it as **§4.0 The pk-filter guard — `pk_from_param` (MANDATORY)**.

**Verification.** Reproduced on SQLite before the fix — **10/10 filters raised `OverflowError`**.
After the fix — **10/10 return 200**. `manage.py check` clean, `makemigrations --check` clean,
the full 8.13 page sweep still passes on MariaDB, and the oversized-pk sweep passes on both
databases.

### `code-reviewer` — **12 findings: 1 Critical, 5 Important, 7 Minor** (VERDICT: FAIL)

The reviewer read the contract, every backend and template file, and executed runtime probes
(seeder idempotency on a real tenant, `save()` re-stamp behaviour, the currency rejection,
form validity). Its full report is summarised below; every finding is to be fixed by the
`code-fixer` agent in ID order.

#### C1 — CRITICAL — the `currency` FK is unusable on every 8.13 form and admin

`accounting.Currency` is a **GLOBAL** master with **no tenant FK**
(`apps/accounting/models/GeneralLedger/Currencies.py:6-9` — *"ISO 4217 currency master.
**Global** — shared across all tenants (no tenant FK)"*; verified by introspection: fields are
`['id','code','name','symbol','is_active']`). So `getattr(currency, "tenant_id", None)` is `None`,
and `None != request.tenant.id` is always true — **every currency selection is rejected**.

The project's own idiom says the opposite: `ForecastPeriods.py:13` — *"`reporting_currency` is
deliberately never tenant-checked (L29)"*; `QuotaPlans.py:21-22` — *"`accounting.Currency` is a
GLOBAL master with no `tenant` FK, so it is never tenant-checked (L29)"*; `LeadQualifications.py:69`
— `budget_currency` carries no tenant guard.

- **Evidence (executed by the reviewer):**
  `AttributionTouchpointForm(tenant=<Acme>, data={..., "currency": <USD pk>})` →
  `FORM VALID: False`, `{'currency': [ValidationError(['That record belongs to another workspace.'])]}`.
  Model path: `AttributionTouchpoint(..., currency=usd).full_clean()` → `ValidationError` on `currency`.
- **Sites:** `apps/sales/forms/_common.py:34` (the shared `_reject_foreign` test),
  `AttributionTouchpoints.py:66`, `ContentEngagements.py:71`, `MqlHandoffs.py:93`,
  `MarketingEvents.py:73`; and the model `clean()` guards at `AttributionTouchpoints.py:192`,
  `ContentEngagements.py:160`, `MqlHandoffs.py:221`, `MarketingEvents.py:226`.
- **Consequence:** the `currency` field cannot be set on any 8.13 record through the UI or the
  admin — the dropdown offers currencies and then rejects every one. Worse, the seeder writes a
  currency anyway (`seed_sales.py:2926, 3036, 3070, 3126`), so **16 of the 19 seeded 8.13 rows per
  tenant** hold a value their own model forbids; re-opening any of them in the edit form
  re-submits the currency and hits the same error — **the seeded rows are un-editable**.
- **Fix:** remove `"currency"` from the four `_reject_foreign(...)` lists and from the four
  `clean()` guard loops; keep it in `Meta.fields` and in the admin (it is a valid global
  reference). Optionally narrow the widget to `Currency.objects.filter(is_active=True)`.

#### I1 — IMPORTANT — the seeder writes an `MqlHandoff` that violates the model's own SLA invariant

`seed_sales.py:3001` (`"sla_in_hours": -2`) and `:3030` (`sla_due_at = handoff_at + timedelta(hours=...)`)
put the SLA deadline **two hours before the handoff was raised**. `objects.create()` never calls
`full_clean()`, so the row is written anyway. The intent (an overdue pending handoff) is
expressible correctly: `handoff_at` in the past with `sla_due_at = handoff_at + 24h` is already
in the past, because `handoff_at = now - timedelta(days=3 + idx)`. **Fix:** make `sla_in_hours`
positive and let `handoff_at` place the deadline in the past.

#### I2 — IMPORTANT — SLA-breach counting contradicts the model's own `is_sla_breached`

The model property treats *any* unanswered, overdue handoff as breached. Both aggregates
(`MqlHandoffs.py:70-71`, `AttributionConsole.py:166-167`) use
`Q(responded_at__isnull=False, responded_at__gt=F("sla_due_at")) | Q(status="pending", sla_due_at__lt=now)`,
so a handoff in status `expired` that was never answered is excluded — exactly the case the
`expired` status exists to record. **Consequence:** the list stat and the console's SLA
compliance over-report compliance, and the same row reads as breached through
`obj.is_sla_breached` and compliant in the totals. **Fix:** align both aggregates with the
property — ideally by exposing one shared `Q` on the model so they cannot drift.

#### I3 — IMPORTANT — admin FK querysets are not narrowed to the requesting tenant

`admin.py:902-911` (`MarketingEventAdmin` — no `formfield_for_foreignkey` at all, so `owner`
and `campaign` are unnarrowed); `:894-899` (`ContentEngagementAdmin` narrows `content`/`lead`/
`campaign` but **not** `account`); `:875-882` (`MqlHandoffAdmin` narrows `lead`/`campaign`/
`opportunity`/`owner`/`assigned_to` but **not** `account`); `:857-861` (`CampaignAttributionAdmin`
narrows `touchpoint` but **not** `computed_by`). **Consequence:** the admin dropdowns list other
tenants' campaign names, party names and user emails, and the model guard then rejects the
cross-tenant pick — a confusing dead end rather than a filtered list. `accounts.User.tenant` is
nullable for the platform superuser, so `computed_by` is additionally un-selectable for `admin`.
**Fix:** add the missing names to each override, or introduce a shared base admin that narrows
every FK to `request.tenant`.

#### I4 — IMPORTANT — the seeder fabricates attribution credits against touchpoints it did not create

`seed_sales.py:2938-2939` — `all_touches = list(AttributionTouchpoint.objects.filter(tenant=tenant).order_by("pk"))`
is the **whole tenant**, not the six rows just inserted; `:2946-2975` then writes
`first_touch`/`last_touch`/`linear` credits for each. The block's own idempotency key is
`(tenant, touchpoint, attribution_model)`, so any operator-entered touchpoint with no credits
gets three fabricated credit rows on the next `seed_sales` run. **Consequence:** running a demo
command silently mutates operator-entered data. **Fix:** restrict `all_touches` to the rows this
block created, or to an explicit allow-list.

#### I5 — IMPORTANT — console content/event title lookups are not tenant-filtered

`AttributionConsole.py:215` (`EnablementContent.objects.filter(pk__in=content_ids)`) and `:240`
(`MarketingEvent.objects.filter(pk__in=event_ids)`); same pattern in
`MarketingEvents.py`'s `_event_annotations` (`EventRegistration.objects.filter(event=OuterRef("pk"))`).
Every other queryset in the console is tenant-scoped. **Consequence:** one cross-tenant link
(which `Model.clean()` does not prevent on `save()`) makes the console render another tenant's
content title or event name. **Fix:** add `tenant=tenant` to both filters and to the registration
subquery.

#### M1 — MINOR — blended `avg_cost_per_lead` double-counts leads spanning multiple campaigns

`AttributionConsole.py:93,115` (`total_leads += lead_count`, a per-campaign
`Count("lead_id", distinct=True)`) and `:264` (`total_spend / total_leads`). A lead touching two
campaigns contributes 2, so the headline cost-per-lead is understated. The contract pins the
per-campaign formula but not the blended headline. **Fix:** compute it from one
`Count("lead_id", distinct=True)` over the tenant's touchpoints and pin the formula in the contract.

#### M2 — MINOR — 7 of the 11 contract-pinned `stats` keys are passed but never rendered

`AttributionConsole.py:270-276` passes `avg_cost_per_lead`, `mql_total`, `mql_accepted`,
`mql_acceptance_rate_pct`, `sla_compliance_pct`, `content_engagements`, `events`; the template
renders only `total_touchpoints`, `total_spend`, `total_attributed_revenue`, `blended_roi_pct`
(the MQL numbers come from `mql_funnel` instead). `:275-276` issue two extra `COUNT(*)` queries
per load for values nothing displays, and `avg_cost_per_lead` — the one pinned headline stat with
no other home — is never shown although the page sub-heading advertises "cost per lead".
**Fix:** render the pinned stats, or drop the unused keys and the two counts.

#### M3 — MINOR — `attributed_cost` is aggregated and never read

`AttributionConsole.py:79` — `attributed_cost=Sum("attributed_cost")` in the per-campaign
aggregate; the key is read nowhere and is not in the contract's `campaign_rows` shape.
**Fix:** drop the annotation, or pin and render it.

#### M4 — MINOR — `MqlHandoff.save()` clears `responded_at` for every non-responded status

`MqlHandoffs.py:197` clears the stamp whenever the status is not in the responded set, which
includes `expired`. The contract clears only on the move back to `pending`. An already-answered
handoff later re-labelled `expired` loses its response time, and with it `is_responded`,
`response_hours` and its late-response breach classification — it silently drops out of
`avg_response_hours` and flips from "answered late" to "unanswered" in the SLA metric. The status
is editable from the form, so the transition is reachable by an ordinary edit.
**Fix:** clear only on the move back to `pending`.

#### M5 — MINOR — `save(update_fields=...)` silently discards the timestamp stamp

`MqlHandoffs.py:197` and `MarketingEvents.py:338` mutate `responded_at`/`attended_at` and then
delegate to `super().save(*args, **kwargs)`. If a caller passes `update_fields` that excludes
the stamped field, the stamp is not persisted while the in-memory instance still reports it. No
current 8.13 caller uses `update_fields`, so this is latent. **Fix:** add the stamped field to
`update_fields` when supplied, or refuse the call.

#### M6 — MINOR — templates hardcode `$` although the module carries a `currency` FK

e.g. `attributiontouchpoint/list.html:43,54,188,191`; `attribution_console.html:82,91,134,137,150,156,201,207,316,372`.
A touchpoint denominated in EUR renders as `$120.00`, and the console's Spend / Attributed Revenue
totals add figures whose currencies may differ. **Fix:** render `{{ obj.currency.symbol }}` /
`{{ obj.currency.code }}`.

#### M7 — MINOR — `MqlHandoffForm.clean()` does not implement the `sla_due_at >= handoff_at` rule the contract pins to the form

`MqlHandoffs.py:83-93` enforces only the rejection-reason rule; the SLA ordering rule lives
solely in the model's `clean()`. Observable behaviour is nearly identical (Django's
`ModelForm._post_clean` → `full_clean()` → `Model.clean()`), except that when either field
already carries a form-level error Django excludes it from model validation and the ordering rule
is silently skipped. **Fix:** add the comparison to the form's `clean()`.

#### Verified as correct by the code-reviewer

Seeder idempotency (ran twice on one tenant — identical counts, no duplicate masters created);
`Currency` confirmed global (the basis for C1); `MqlHandoff.save()` does not re-stamp on a same-
status re-save and re-stamps on a re-accept; `EventRegistration.save()` stamps on entering
`attended` and clears on `no_show`; all 18 templates present at the contract paths, no
`badge-success/-warning/-danger`, stat icons limited to the six legal colours, csrf on every POST
form, all pk comparisons via `|stringformat:"d"` with zero `|slugify`; **every contract-pinned
filter has a working GET control** (touchpoint 6/6, attribution 4/4, engagement 6/6, event 5/5,
handoff 5/5); the console consumes every one of its context keys; `?model=` is whitelist-validated
with a `first_touch` fallback; **no `JournalEntry` anywhere in 8.13** (L29); no duplicate master
declared (L36/L37); every list/detail queryset tenant-scoped and every form FK queryset
tenant-scoped; CRUD completeness across 5 entity sets with POST-only tenant-admin deletes; the
package re-export blocks and `LIVE_LINKS["8.13"]` match the contract.

#### Not verified by the code-reviewer

The seeded-row edit round-trip (its own probe harness had two fixture bugs — `core.PartyRole`
needs an explicit `tenant=`, and `crm.Campaign`'s field is `budget_planned`, not `budget`); the
console aggregates against hand-computed values; any page render, junk-param list, page-2
pagination or cross-tenant IDOR request; `manage.py check` and the migration's forward/backward
behaviour; and the `Sum("registered_total")` aggregate over an ordered queryset — Django's
`get_aggregation()` can add ordering fields to the GROUP BY, so that one deserves a numeric check
before sign-off.

### `explorer` — **7 findings: 2 Important, 5 Minor** (+ a structure map)

A static code/structure pass (grep + file reads only — no renders, no DB, no file modified). It
read the code-reviewer's section first, so nothing below duplicates it. Findings are prefixed `E`
to keep the IDs unique across the six passes.

#### E1 — IMPORTANT — 11 enum filters accept junk values, so a hostile filter empties the register

`AttributionTouchpoints.py:47,51,55` (`channel`, `touch_type`, `touch_position`) ·
`CampaignAttributions.py:48,52` (`attribution_model`, `status`) ·
`ContentEngagements.py:44,48` (`engagement_type`, `engagement_channel`) ·
`MarketingEvents.py:73,77` (`event_type`, `status`) · `MqlHandoffs.py:42,46` (`status`,
`source_kind`).

Each site applies the raw GET string without checking it against the model's `CHOICES`:

```python
status = request.GET.get("status", "").strip()
if status:
    qs = qs.filter(status=status)
```

**Consequence.** `?status=bogus` narrows to a value no row can hold → the register renders
**empty with all-zero stat cards** (the stats are computed on the *filtered* queryset), instead
of falling back to the unfiltered list. This is a **contract breach**: contract §9 requires
"junk params fall back to the unfiltered list", and the Phase 3 smoke gate only asserted
"no 500", which is why it slipped through. The console in the same sub-module already does the
right thing (`AttributionConsole.py:57-59` whitelist + `first_touch` fallback) — so 8.13 ships
11 copies of the un-guarded shape and 1 copy of the guarded shape.

**Fix:** a shared `enum_filter(qs, request, param, field, choices)` in
`apps/sales/views/MarketingAlignment/_common.py`, applied at all 11 sites.

#### E2 — IMPORTANT — the average-response-hours computation is copy-pasted across two files

`MqlHandoffs.py:82-92` and `AttributionConsole.py:187-199` — the same eleven lines twice. Two
independent copies of one metric that must agree, or the MQL list card and the console's funnel
disagree — exactly the drift risk `apps/sales/views/_helpers.py`'s own docstring warns about
("*four copies of a role check, each free to drift*"). The two copies already differ in their
queryset (filtered vs whole-tenant), which is legitimate; the *algorithm* is duplicated.
**Fix:** one `avg_response_hours(queryset)` helper in `views/MarketingAlignment/_common.py`, called
from both. This also gives the code-reviewer's I2 (the triplicated SLA-breach `Q`) a natural home.

#### E3 — MINOR — 14 dead context/stats keys across six views, and 2 of them are contract drift

Every key below is passed by a view and read by no template. **Five detail templates use `obj.`
exclusively** (40 `obj.` hits, 0 `event.` hits in `marketingevent/detail.html`).

| View | Dead key(s) |
|---|---|
| `attribution_touchpoint_detail` | `"touchpoint": obj` |
| `campaign_attribution_detail` | `"attribution": obj` |
| `mql_handoff_detail` | `"handoff": obj` |
| `content_engagement_detail` | `"engagement": obj` |
| `marketing_event_detail` | `"event": obj`; `"registration_status_choices"`, `"followup_status_choices"` (these belong to `registrations.html`, which gets them from the registrations view) |
| `marketing_event_registrations` | `"obj": obj` (the template uses `event.`) |
| `campaign_attribution_list` | `stats["total_credit_pct"]` |
| `mql_handoff_list` | `stats["pending_count"]`, `["expired_count"]`, `["converted_count"]` |
| `marketing_event_list` | `stats["upcoming_count"]` |
| `content_engagement_list` | `stats["engaged_account_count"]` |
| console | `channel_rows[i]["channel"]` (the template reads `row.label`) |

**Contract drift.** The contract **pins** six of these (§4.2 `touchpoint`, §4.4 `total_credit_pct`,
§4.5 `attribution`, §4.7 the five MQL counters, §4.8 `handoff`, §4.13 `upcoming_count`, §4.14 `event`)
and does **not** pin the two extra choice keys `marketing_event_detail` actually passes; conversely
§4.16 under-specifies `marketing_event_registrations`, whose as-built context also needs
`registration_status_choices`, `followup_status_choices` and `active_filters`. **No runtime
impact** — the pages render correctly — but the contract is the authoritative spec, and a later
pass (or the Phase 6 test-writer) pins context names from it.

#### E4 — MINOR — the seeder's `touchpoints` accumulator is dead code, and it is exactly where the code-reviewer's I4 fix belongs

`seed_sales.py:2895` (`touchpoints = []`) and `:2910` (`touchpoints.append(...)`) — built and
appended to but never read; the credit loop iterates the tenant's whole touchpoint set instead.
The accumulator is the fossil of the intended design, and fixing I4 (credit only the rows this
block created) makes it live and removes the dead code in one step. **Do not simply delete it
while I4 is outstanding** — that would cement the defect.

#### E5 — MINOR — four model properties nothing references

`AttributionTouchpoint.is_first_touch` / `.is_last_touch` (duplicate the `touch_position` field,
and the list stats re-express the same fact as `Q(touch_position="first")`),
`MqlHandoff.is_responded` (duplicates the `responded_at__isnull=False` test used in two views),
`ContentEngagement.is_download` (duplicates `Q(engagement_type="download")`). Two expressions of
one fact, free to drift. **Fix:** use them where the same condition is currently re-expressed in
SQL, or delete them.

#### E6 — MINOR — `EventRegistration` has no edit or delete path, so the attendance transition is unreachable from the UI

`urls/MarketingAlignment/MarketingEvents.py:12-13` registers only the registrations list and the
registration create. The model's `attended_at` help-text says *"Stamped automatically the first
time the registration is marked attended"*, and `EventRegistration.save()` implements that — but
a registration created as `registered` can never later be marked `attended` through the app.
This is a **contract scope decision** (§4.16/§4.17 list only list + create), not a wiring bug, and
the code-reviewer verified CRUD completeness across 5 entity sets. **Consequence:** the attendance
model — the point of the registration child — is write-once. **Fix:** add an edit (+ delete)
route under the event's registrations page, or amend the help-text and record the missing
transition as a gap.

#### E7 — MINOR — two top-level 8.13 sidebar bullets resolve to the same URL

`apps/core/navigation.py:2522` "Campaign Influence & Attribution" → `sales:marketing_attribution_console`
and `:2524` "Campaign Performance Integration" → the same URL. **Important context:** a duplicate
target is an **established convention** in that file — 13 duplicated URLs, 12 of them the same
shape (a NavERP bullet + a short alias leaf). What differs in 8.13 is that the duplicate is
between **two top-level NavERP feature bullets**, so the sidebar shows one page twice under two
bullet names, and "Campaign Influence & Attribution" has no landing page of its own — its two
entity lists are demoted to "extra live leaves". **Fix:** point "Campaign Influence &
Attribution" at `sales:attribution_touchpoint_list`, or drop one bullet label.

#### Structure map (the explorer's distinctive deliverable)

- **Models** (`apps/sales/models/MarketingAlignment/`, 5 entity files + `__init__.py`, all on
  `apps/sales/models/_base.py`'s `TenantNumbered`/`TenantOwned`):
  `AttributionTouchpoints.py` → `AttributionTouchpoint` (`ATB-`) → `crm.Campaign`, `crm.Lead`,
  `crm.Opportunity`, `accounting.Currency`; `CampaignAttributions.py` → `CampaignAttribution`
  (`ATR-`), the child of `AttributionTouchpoint` (`related_name="attributions"`) → `accounts.User`;
  `MqlHandoffs.py` → `MqlHandoff` (`MQL-`) → `crm.Lead`, `crm.Campaign`, `core.Party`,
  `accounts.User` (owner + assigned_to), `crm.Opportunity`, `accounting.Currency`;
  `ContentEngagements.py` → `ContentEngagement` (`CNG-`) → `sales.EnablementContent`, `core.Party`,
  `crm.Lead`, `crm.Campaign`, `accounting.Currency`; `MarketingEvents.py` → `MarketingEvent` (`EVT-`)
  → `accounts.User`, `crm.Campaign`, `accounting.Currency`, **plus** its unnumbered child
  `EventRegistration` (`TenantOwned`) → `MarketingEvent` (`related_name="registrations"`),
  `crm.Lead`, `core.Party`, `crm.Campaign`, `crm.Opportunity`. A sixth, *derived* surface —
  `views/MarketingAlignment/AttributionConsole.py` → `marketing_attribution_console` — stores nothing
  and rolls up `CampaignAttribution` + `AttributionTouchpoint` + `crm.Campaign` on the fly.
- **Forms** (`apps/sales/forms/MarketingAlignment/`): one `ModelForm` per entity —
  `AttributionTouchpointForm`, `CampaignAttributionForm`, `MqlHandoffForm`, `ContentEngagementForm`,
  `MarketingEventForm`, `EventRegistrationForm`; all six derive from `TenantModelForm`, the five
  numbered ones also from `TenantUniqueMixin`, each narrowing its FK querysets to `request.tenant`.
- **Views** (`apps/sales/views/MarketingAlignment/`): 5 entity modules × {list, create, detail, edit,
  delete} = 25, plus `marketing_event_registrations`, `marketing_event_registration_create` and
  `marketing_attribution_console` = **28 functions**; deletes are `@require_POST` +
  `@tenant_admin_required`; `_common.py` holds the one shared helper, the int64-safe `pk_from_param`.
- **URLs** (`apps/sales/urls/MarketingAlignment/`): 6 modules, all under `marketing-alignment/`,
  **28 patterns** (5+5+5+5+7+1) — `touchpoints/`, `attributions/`, `mql-handoffs/`,
  `content-engagements/`, `events/` (+ `events/<pk>/registrations/`), `console/` — mounted in
  `apps/sales/urls/__init__.py` as `_marketing_alignment` under `app_name = "sales"`.
- **Templates** (`templates/sales/marketingalignment/`): 5 entity folders × {list, detail, form} +
  `marketingevent/{registrations,registration_form}` + the standalone `attribution_console.html` at
  the sub-module root = **18**.
- **Cross-cutting**: the 8.13 blocks in `apps/sales/{models,forms,views,urls}/__init__.py`; all 6
  models registered in `apps/sales/admin.py:831-928`; the seeder block `_seed_marketing_alignment`
  (`seed_sales.py:2842-3169`, called from `handle()` at `:161`); `LIVE_LINKS["8.13"]`
  (`apps/core/navigation.py:2515-2530`); migration `0023_attributiontouchpoint_campaignattribution_and_more.py`.

#### Verified as correct by the explorer

- **Migration ↔ models is a faithful field-by-field match** — every field name, type, `choices`
  list (all 15 choice-bearing fields carry their full vocabulary), `db_index`, `default`,
  `max_length`, `validators`, `help_text`, `null`/`blank`, `on_delete`, `related_name` (all 32 FK
  `related_name`s match, including the two child relations `attributions` and `registrations`), plus
  every `Meta` element — `ordering`, 20 indexes, 5 unique constraints.
- **The re-export blocks are complete and typo-free** — `models/…/__init__.py` (20 names),
  `forms/…` (6), `views/…` (28), `urls/…` (6 modules); every name in every `__all__` exists and
  every definition is exported; the `views/__init__.py` prefix filter picks up all 28 functions.
- **No wiring gaps in the URL/template graph** — 28 view functions ↔ 28 URL patterns ↔ 18
  templates: no view without a URL, no URL without a view, no orphan template, no path typo.
- **Template ↔ view filter wiring is exact** — every `<select name="…">` matches a
  `request.GET.get("…")` one-for-one (touchpoint 6, attribution 4, engagement 6, event 5,
  handoff 5); every `*_choices` key a template needs is rendered; and the pagination links on all
  five list templates **and** the registrations page preserve every active filter.
- **Convention compliance** — no relative imports anywhere under the 8.13 packages (grep `^from \.`
  → 0 hits); one file per entity, PascalCase; package `__init__.py` re-exports complete, the same
  shape as the 8.11 `CustomerSuccess` sibling; template folders match the sibling convention and
  the standalone console sits at the sub-module root per the folder rule's clause 6.
- **Seeder shape** — all six declared idempotency keys match the keys the code actually checks;
  every choice value it writes is a member of the model's `CHOICES`; every field it writes exists
  on the model; no variable used before definition; the block tolerates absent masters.
- **`pk_from_param` is genuinely new** — `apps/sales/views/_common.py` has no pk-parsing helper,
  and all 10 pk filter sites use it.
- **Scope consistency** — the 8.13 views scope by `tenant=request.tenant` without `sales_scope`;
  that matches every sales sub-module except 8.2, and `apps/core/scoping.py` documents the
  mechanism as opt-in per module.
- **`LIVE_LINKS["8.13"]` targets all resolve** (7 links, 6 distinct URLs).

#### Not verified by the explorer

No runtime verification (by instruction): no page rendered, no query string issued, no
`manage.py check`, no test run, no DB connection. `makemigrations --check` was not re-run (the
concurrent 8.12 session has in-flight models in the same app, so its output would be ambiguous) —
the explorer substituted the static field-by-field comparison above. The console aggregates'
numeric correctness (including whether `qs.aggregate(Sum("registered_total"))` over an ordered
queryset emits a `GROUP BY` that changes the result) remains a runtime question. The filter
dropdown querysets' completeness, and the sidebar rendering of E7, were reasoned from source
rather than observed.

### `frontend-reviewer` — pending
### `performance-reviewer` — pending
### `qa-smoke-tester` (Phase 4 pass) — pending
### `security-reviewer` — pending

---

