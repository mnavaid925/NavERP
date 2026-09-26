# Review — Sub-module 8.4 Sales Forecasting (Module 8, sales) — code-reviewer pass
BASE 6edc6178 .. HEAD (4fe48513)

Scope reviewed: `apps/sales/models/SalesForecasting/*`, `apps/sales/forms/SalesForecasting/*`,
`apps/sales/views/SalesForecasting/*`, `apps/sales/forecast_services.py`, `apps/sales/urls/*`,
`apps/sales/admin.py`, `apps/sales/management/commands/seed_sales.py`, `apps/core/navigation.py`,
all 16 files under `templates/sales/salesforecasting/**`, against
`.claude/tasks/contract-sales-8.4.md` §0–§8.

---

## Critical

- [x] fixed — C1.  `apps/sales/views/SalesForecasting/ForecastPeriods.py:326` — the stale-instance bug a
  previous pass reported is **still present**. `forecast_period_edit` builds
  `ForecastPeriodForm(request.POST, instance=obj)`, so `form.instance is obj`; `form.is_valid()`
  runs `_post_clean()` → `Model.full_clean()` → `ForecastPeriod.clean()`
  (`models/.../ForecastPeriods.py:181-183`), which **writes the freshly derived `start_date` /
  `end_date` onto `form.instance`**. Line 326 then does `form.instance = locked` — a *separately
  loaded* row from `ForecastPeriod.objects.select_for_update().get(pk=obj.pk, …)`, whose
  `start_date`/`end_date` are the **old stored** values. Lines 327-334 copy only
  `form._meta.fields`; `start_date` and `end_date` are `editable=False` (model lines 72-73) so
  they are structurally absent from `form.fields` and are **never copied**. Line 335
  `form.save(commit=False)` returns `locked`, and `locked.save()` reaches
  `ForecastPeriod.save()` (model lines 187-192), whose guard is
  `if self.start_date is None or self.end_date is None: recompute` — the freshly loaded row is
  non-`None`, so the recompute is **skipped**. Net effect: a period edited from Q1 2025 to Q3 2025
  saves `period_type='quarter', period_year=2025, period_number=3` with the **Q1 window**. The row
  now contradicts its own type/year/number and no exception is raised.
  Corruption trace:
  - `period_elapsed_pct` (`models/.../ForecastPeriods.py:132-149`) reads the stale window → wrong
    denominator → wrong elapsed % on the list and detail pages.
  - `ForecastSubmission.pace_pct` (`models/.../ForecastSubmissions.py:215-219`) is
    `self.period.period_elapsed_pct` → `ForecastBoards._band()`
    (`views/.../ForecastBoards.py:378-383`) bands every rep on it, so reps flip Ahead/Behind on
    `forecast_attainment` with no underlying change, and `row["pace_pct"]` (line 373) is the same
    wrong figure.
  - `is_current` (`models/.../ForecastPeriods.py:127-129`) → the "Current" badge
    (`forecastperiod/list.html:15`) and the `stats.current` aggregate
    (`views/.../ForecastPeriods.py:118`) both misfire.
  - `_period_window()` (`forecast_services.py:71-80`) returns the stale pair and
    `_open_opportunities()` (`forecast_services.py:117-119`) filters
    `close_date__gte=window[0], close_date__lte=window[1]` on it → `weighted_amount` is snapshotted
    from the wrong set of deals on the next `forecast_submission_submit`
    (`views/.../ForecastSubmissions.py:409-412`).
  - The same window feeds `won.filter(closed_at__date__range=window)`
    (`forecast_services.py:183-192`) → `actual_amount`, which in turn feeds `variance_amount`,
    `attainment_pct`, the board's `variance_amount` and the whole accuracy page.
  - `_periods(tenant, only_past=True)` (`views/.../ForecastBoards.py:95-97`) filters
    `end_date__lt=today` on the stale column → a period edited forward silently disappears from
    `forecast_accuracy`.

- [x] fixed — C2.  `templates/sales/salesforecasting/forecastadjustment/detail.html:24` — an entire
  fragment sits **after `{% endblock %}` (line 22)** and is therefore **silently discarded** by
  `{% extends "base.html" %}` (line 1). The dead line is
  `</dl>{% if obj.note %}<p …><strong>Note:</strong> {{ obj.note|linebreaksbr }}</p>{% endif %}<p …>The system value is a snapshot …</p></div></div>`
  — the manager's **override note never renders at all**, and the only two closing tags that
  balance the first card die with it. The damage compounds:
  - line 7 opens `<div class="card">` + `<div class="card-body">` + `<dl class="detail-grid">` and
    closes none of them inside the block;
  - line 9 opens the "What it targets" card **inside that still-open `<dl>`**, so the second card
    renders as a child of the first card's definition list;
  - the `</div>` on **line 12** and the `</div>` on **line 21** are both **unmatched closes**
    (verified with `html.parser`: the open stack at both points is `['div','div','div','dl']` from
    line 7);
  - `<div class="grid lg:grid-cols-3 gap-4">` (line 5) and
    `<div class="lg:col-span-2 space-y-4">` (line 6) are **never closed**, so the whole
    Actions / State / Reset sidebar (`<div class="space-y-4">`, line 13) collapses into the left
    column and the 3-column grid never closes.
  All of this returns **HTTP 200** — the page renders, the note is just gone and the layout is
  wrong.
  **Fix** — move line 24's content up to immediately after line 8 (closing the `<dl>`, the
  `card-body` and the `card`), give the "What it targets" card its own `</dl></div></div>`, and
  make lines 12/20/21 close `lg:col-span-2` and `grid` exactly once each. Re-run the
  `html.parser` balance check (`LEFTOVER OPEN == []`, no unmatched closes) as part of the fix;
  `templates/sales/salesforecasting/forecastperiod/detail.html:14-23` is the correct reference.

- [x] fixed — C3.  `templates/sales/salesforecasting/forecastscenario/detail.html:7` — the first card's
  `<div class="card">` / `<div class="card-body">` are **never closed**; line 9 closes only the
  `<dl>`. Consequence: the "Projection from the live forecast" card (line 10) and every card after
  it — "The real forecast is untouched" (line 22), "Current plan" (line 23), "Apply the period"
  (line 26), "Rollup axis" (line 30) — all render **as children of the "The scenario" card body**
  instead of as siblings. `<div class="grid lg:grid-cols-3 gap-4">` (line 5) is also never closed
  (verified: `LEFTOVER OPEN == [('div', 5)]`). The page returns 200 with a visibly wrong card
  nesting and an unterminated grid container.
  **Fix** — close the first card after its `<dl>` content on line 9
  (`</dl>…</p></div></div>`), and add the missing `</div>` for the grid container before
  `{% endblock %}` on line 31. `forecastperiod/detail.html:14-23` is the correct reference.

- [x] fixed — C4.  `apps/sales/forecast_services.py:117-119` — `_open_opportunities()` filters
  `close_date__gte=window[0], close_date__lte=window[1]`, but `crm.Opportunity.close_date` is
  `models.DateField(null=True, blank=True)`
  (`apps/crm/models/SalesForceAutomation/Opportunities.py:36`). A NULL `close_date` fails both
  bounds and is therefore **silently excluded**. In practice most open deals carry no close date,
  so `_rollup_by_currency()` returns an empty dict and

---

## Important

- [x] fixed — I1. `apps/sales/views/SalesForecasting/ForecastBoards.py:454` and `:503` — `bias_values`
  is a single list fed by **two different populations**. Line 454 appends `bias_pct`, a
  *period-level* tenant-wide bias; line 503 appends `mean_bias`, a *rep-level* mean. Line 527
  then computes `mean_bias_pct = sum(bias_values) / Decimal(len(bias_values))` and the stat card
  "Mean bias" (`accuracy.html:5`) prints it. With 5 periods and 10 reps the headline number is a
  15-way average that double-counts the same underlying submissions and weights reps against
  periods arbitrarily. **Fix** — keep two lists: compute `mean_bias_pct` from the period-level
  values only (and expose a separate `mean_owner_bias_pct` from the owner values), or report
  `mean_bias_pct` as the unweighted mean of `bias_rows` alone.

- [x] fixed — I2. `apps/sales/views/SalesForecasting/ForecastBoards.py:426-433` — `forecast_accuracy`
  parses and validates `?period=` into `selected_period_id`, hands it to the template (line 536)
  … and then **never uses it**: the report always aggregates every past period.
  `templates/sales/salesforecasting/forecastboard/accuracy.html` has no `<form method="get">` and
  no period dropdown at all, so the pinned `period_choices` key is dead too. Net effect: a
  bookmarked `?period=7` silently returns the tenant-wide report while the URL claims otherwise,
  and two contract-pinned context keys are never rendered. **Fix** — either render the period
  dropdown on `accuracy.html` and honour `selected_period_id` by narrowing `periods` to it
  (falling back to all past periods when absent), or drop the parameter and the two keys and
  record the deviation from contract §5.4 (contract line 562).

- [x] fixed — I3. `apps/sales/views/SalesForecasting/ForecastBoards.py:125-151` — `_submissions()`,
  `_adjustments()` and `_scenarios()` are **unbounded**; none applies `MAX_ROWS`, directly
  contradicting the module docstring at lines 59-62 ("the lists are bounded so a huge workspace
  cannot pull an unbounded set into memory"). `forecast_call` (line 557) then materialises every
  submission *and* every adjustment of a period into per-row dicts. **Fix** — add `[:MAX_ROWS]` to
  all three helpers and surface the truncation in `caveats` (the pattern the 0.17 firing board
  already uses: "this list is capped at N").

- [x] fixed — I4. `apps/sales/views/SalesForecasting/ForecastBoards.py:441-455` — the accuracy loop
  runs `_submissions(tenant, period)` **and** `_adjustments(tenant, period, …)` per period, over
  `periods[:MAX_PERIODS]` = up to **200** periods: up to 400 queries plus 200 round trips for one

- [x] fixed — I6. `apps/sales/views/SalesForecasting/ForecastPeriods.py:201-218` — `submissions` is
  sliced to `[:200]` (line 204) and that **capped list** is what `_period_rollups()` sums, so
  `category_totals`, `currency_rollups` and `total_forecast_amount` silently exclude every
  submission past the 200th — while `submissions_count` (line 206) is the *true* count, so the two
  numbers on the same page disagree with no explanation. **Fix** — compute the rollups from
  `values(...).annotate(Sum(...))` over the untruncated queryset, and add a caveat when
  `submissions_count > len(submissions)`.

- [x] fixed — I7. `apps/sales/views/SalesForecasting/ForecastBoards.py:97` — `only_past` uses
  `end_date__lt=today`, which **excludes a period on its own final day**. That is an off-by-one
  against the model, which treats the same day as `today >= end_date` → `period_elapsed_pct == 100`
  (`models/.../ForecastPeriods.py:147`) and `is_current == True` (line 129). A period whose actuals
  have landed is missing from the accuracy report on its last day and only appears the day after.
  **Fix** — use `end_date__lte=today` (or `Q(end_date__lt=today) | Q(end_date=today,
  start_date__lte=today)`), matching the `period_elapsed_pct` definition.

- [x] fixed — I8. `apps/sales/views/SalesForecasting/ForecastBoards.py:487-496` — the "Manager
  overrides by rep" table sums `adjustment.net_delta` (a **money** amount,
  `adjusted_value - original_value`) per rep with **no currency label and no caveat**.
  `ForecastAdjustment` carries no currency field, so on a tenant whose calls sit in several
  currencies this is a cross-currency sum presented as one figure — a direct L29 violation, and
  the only report on the page that does it (the board at least emits a currency caveat, lines
  253-258). It is also a contract break: contract §5.4 (contract line 562) pins `sandbagging_rows`
  as `{"owner", "early_vs_final_pct", "adjustment_count"}` — a *percentage* — and the build
  substituted `net_delta`, an absolute amount, then changed `accuracy.html:12` to match.
  **Fix** — compute the pinned `early_vs_final_pct` (mean signed % move per rep, `None`-guarded);
  if the absolute figure is also wanted, bucket it by the period's `reporting_currency` and add a
  `currency_code` key plus a caveat exactly as the board does.

- [x] fixed — I9. `templates/sales/salesforecasting/forecastboard/call.html:4` — the "New call" CTA is
  gated on `{% if can_review and period %}`, and `can_review` is `_is_tenant_admin(request.user)`
  (`views/.../ForecastBoards.py:612`). A rep — the one person who is supposed to *make* the
  forecast call — never sees the button on the page whose entire purpose is the forecast call,
  while `forecast_submission_create` is `@login_required` and would happily serve them. This is an
  inverted role check, not just a missing button. **Fix** — drop the `can_review` condition (keep
  `{% if period %}` so the link has a period to forecast into), or gate on "this user may create a
  call", which is the actual precondition.


---

## Minor

- [x] fixed — M1. `_is_tenant_admin()` is copy-pasted into four sibling modules —
  `views/SalesForecasting/ForecastPeriods.py:68`, `…/ForecastSubmissions.py:64`,
  `…/ForecastAdjustments.py:48`, `…/ForecastScenarios.py:62` — and `ForecastBoards.py:31` then
  imports the private copy from `ForecastPeriods`. Four copies of a role check is four things to
  drift, and the import makes the boards module depend on a sibling's private name. **Fix** — move
  it to `apps/sales/views/_helpers.py` (or `_common.py`) and import it everywhere.

- [x] fixed — M2. `templates/sales/salesforecasting/forecastboard/call.html:9` — the badge ladder
  tests `row.status == 'reverted'`, which is **not** in `ForecastSubmission.STATUS_CHOICES`
  (`models/.../ForecastSubmissions.py:67-73`: draft/submitted/approved/rejected/locked). The branch
  is unreachable; a reverted call falls to the `{% else %}` muted badge. **Fix** — delete the
  `'reverted'` branch (reverting is an *adjustment* state, not a submission state;
  `mark_reverted()` sends the call back to `draft`).

- [x] fixed — M3. `templates/sales/salesforecasting/forecastboard/attainment.html:6` — the third stat
  card reads `{{ stats.on_pace }}` under the label **"No quota"**, while `stats["on_pace"]` and
  `stats["no_quota"]` are the *same* count (`views/.../ForecastBoards.py:413` and `:415` both count
  `attainment_pct is None`) and `stats.no_quota` is passed but never read. **Fix** — read
  `stats.no_quota` under that label and drop the duplicate `on_pace` key (or keep `on_pace` and
  rename its card).

- [x] fixed — M4. `templates/sales/salesforecasting/forecastboard/attainment.html:6` — `stats.total`
  is labelled **"Reps"** but `views/.../ForecastBoards.py:411` sets it to `len(rows)`, and rows
  are grouped by `submission.owner_id` (line 350) — the `None` (unassigned) key forms its own row,
  so the count is "distinct owner buckets including unassigned", not "reps". **Fix** — label it
  "Owners", or break the `None` bucket out into an explicit "Unassigned" card.

- [x] fixed — M5. `apps/sales/views/SalesForecasting/ForecastPeriods.py:226,228,231` — the period
  detail context passes `submissions_count`, `status_choices` and `category_choices`, and
  `templates/sales/salesforecasting/forecastperiod/detail.html` reads **none** of them (status
  badges are hard-coded per value at line 15, category labels per value at line 14). Harmless, but
  dead context hides drift. **Fix** — either consume the keys in the template (cleaner) or drop
  them from the view.

- [x] fixed — M6. `apps/sales/forms/SalesForecasting/ForecastSubmissions.py:174` + `:176-179` — on a
  rejected submission with an empty note, `ForecastReviewForm` emits **two** errors for the same
  thing: Django's `"This field is required."` (from `required = not approved`) and the custom
  `"A rejection must say why."` from `clean()`. **Fix** — keep the declarative
  `required = not approved` and drop the `clean()` re-check, or leave the field optional and keep

---

## Verified clean

**Template structure** — all 16 files under `templates/sales/salesforecasting/**` exist at the
contract §7 paths with bare `list`/`detail`/`form` filenames; the four report pages are correctly
nested as `forecastboard/<action>.html`. `{% block content %}` opens on line 3 and `{% endblock %}`
closes on the last line of every file, with **zero** `{{ … }}`/`{% … %}` tokens outside a block in
the 15 files other than C2. `html.parser` tag-balance is clean on 14 of 16 (only C2 and C3 leak).
No `{# … #}` or `{% comment %}` leaks into any output. `{% include "partials/pagination.html" %}`
is present after the table on all four list pages, and all four build `page_obj` from
`apps.core.crud.paginate` (which sets `page_obj.window`), never a bare `Paginator`.

**Design system** — every badge in the changeset is colour-named
(`badge-green|red|amber|info|muted|slate`) and every stat icon is
`blue|green|orange|purple|slate`; a mechanical scan found no `badge-success` / `badge-danger` /
`badge-warning` and no invented `stat-icon` colour. All of them exist in `static/css/theme.css`.

**URLs** — `apps/sales/urls/__init__.py:38-42` places the four 8.4 groups after the 8.3 boards
and before the 8.2 pipelines; within every group the literal routes (`add/`, `export/`, `apply/`,
`submit/`, `approve/`, `reject/`, `lock/`, `unlock/`, `revert/`, `select/`) precede the
`<int:pk>` ones, and no sales route is a `<str:…>` catch-all, so nothing can be shadowed. Scenarios
correctly ship **no** export route, and the list template therefore renders no export button and
reads no `export_url`.

**Multi-tenancy** — every queryset in the five view modules filters `tenant=request.tenant`
(`ForecastPeriods.py:65`, `ForecastSubmissions.py:69`, `ForecastAdjustments.py:92`,
`ForecastScenarios.py:76`, `ForecastBoards.py:90,94,106,129,138,150`); every detail/edit/delete
route goes through `get_object_or_404(<tenant-scoped queryset>, pk=pk)`, so a cross-tenant pk is a
404. `request.tenant is None` degrades to an empty register in every path (`_filter_choices`
returns `[]`, `_periods`/`_submissions`/`_adjustments`/`_scenarios` return `[]`,
`forecast_ai_gate` returns "Select a tenant workspace") and the create views
(`ForecastSubmissions.py:306`, `ForecastAdjustments.py:346`, `ForecastScenarios.py:302`) redirect
with a message instead of raising. No `.all()` on a tenant model anywhere in the changeset.

**Django 5.1 / repo-specific hazards** — every `CheckConstraint` uses the keyword-only
`condition=` (`ForecastPeriods.py:103`, `ForecastSubmissions.py:170`, `ForecastScenarios.py:140,147`).
`accounting.Currency` is treated as the global master it is: never tenant-filtered, explicitly
documented at `ForecastPeriods.py:12-13` and applied at `ForecastPeriods.py:263` and
`forms/.../ForecastPeriods.py:32-40`. The `OrgUnit.parent` walk (`forecast_services.py:46-67`) is
iterative, depth-bounded at 12 and guarded by a `seen` set, so a legacy cycle truncates rather than
hangs. The `PROTECT` FKs (`ForecastSubmission.period`, `ForecastScenario.period`,
`ForecastAdjustment.submission`) are all caught — `ProtectedError` is imported and handled at
`ForecastPeriods.py:410` and `ForecastSubmissions.py:510` — and the two model-level `delete()`
guards refuse in `clean()` before any row goes. The nullable-FK `unique_together` trap is
explicitly avoided on `ForecastSubmission` (no DB-level `(tenant, period, owner)` unique; the rule
lives in `clean()` at `ForecastSubmissions.py:258-273,295-298` and again in the form at
`forms/.../ForecastSubmissions.py:149-158`), and `related_name` crowding is avoided with
`related_name="+"` on the two actor FKs. `manage.py check` is clean and
`makemigrations --check --dry-run` reports "No changes detected".

**Audit** — every hand-rolled save path calls `write_audit_log` inside the same
`transaction.atomic()` as the write: submit (`ForecastSubmissions.py:416`), approve/reject (`:476`),
revert (`ForecastAdjustments.py:459`), lock/unlock (`ForecastPeriods.py:367`), period delete
(`:404`), scenario apply (`ForecastScenarios.py:549`), scenario select (`:428`), scenario delete
(`:591`), adjustment create/edit/delete. The four board views write nothing at all.

**Filters and pagination** — GET is parsed and applied *before* `paginate(...)` in all four list
views; enum params are validated against the model's own `CHOICES` and reset to `""` on junk
(`period_type`, `rollup_dimension`, `status`, `scenario_type`, `is_selected`, `kind`,
`reason_code`, `target_field`); integer FK params go through `as_db_int` so `?period_id=abc` and an
over-range id are skipped, not 500. Every FK dropdown the list templates render is backed by a
bounded context key (`periods`, `owners`, `org_units`, `territories`, `pipelines`, `submissions`,
`opportunities`, `period_choices`, `selected_choices`, `active_choices`, `locked_choices`,
`reverted_choices`). pk comparisons in filter dropdowns use `|stringformat:"d"`
(`forecastsubmission/list.html:9-13`, `forecastscenario/list.html:9-10`,
`forecastadjustment/list.html:11-12`) — never `slugify`.

**CRUD completeness** — list / detail / create / edit / delete exist for all four entities
(periods, submissions, adjustments, scenarios); all four deletes are `@require_POST` +
`@tenant_admin_required` with a `confirm()` and `{% csrf_token %}` in the template, and all four
have a url name. Each list template carries a View / Edit / Delete Actions column and each detail
template an Actions sidebar with Back-to-list.

**Contract conformance (sampled)** — the five NavERP.md 8.4 bullet strings in
`apps/core/navigation.py:2229-2239` match `NavERP.md:1328-1332` byte-for-byte, and every value
resolves to a distinct, staff-reachable page. The template folder is `salesforecasting/`
(mechanical lowercase) as §1 settled, not `forecasting/`. The number prefixes `FCP` / `FCS` /
`FAD` / `FSC` and the `crm.SalesQuota.PERIOD_CHOICES` / `crm.Opportunity.FORECAST_CATEGORY_CHOICES`
vocabularies are reused, never re-spelled, and no opportunity, quota, currency or order table is
re-declared. The isolation rule holds: applying or selecting a scenario writes only
`ForecastScenario` columns, and `ForecastScenario.period` is `PROTECT` with `owner` `SET_NULL`.

`_selected_period` (`ForecastBoards.py:105-122`) validates `?period=` against *this* tenant's
period list, so a foreign pk returns `None` rather than leaking the row.

**Derived values are not columns** — `total_forecast_amount`, `variance_amount`, `attainment_pct`,
`pace_pct`, `is_current`, `period_elapsed_pct` are all `@property`
(`ForecastSubmissions.py:188-219`, `ForecastPeriods.py:126-149`); `ForecastAdjustment.net_delta` is
a property (`:225-234`); `ForecastScenario.effective_*` are properties (`:187-200`) and
`projected_*` are explicitly labelled server-written `editable=False` snapshots, not live figures.
The per-row board/attainment/accuracy figures are computed in the view from the category columns,
never read off a stored total.

**Division safety** — every percentage is zero-guarded and returns `None` rather than
`Infinity`/`NaN`: `_safe_pct` (`ForecastBoards.py:78-87`, `denominator in (None, 0, ZERO)`),
`ForecastSubmission.attainment_pct` (`:209-211`, `quota <= 0`), `_variance_pct`
(`ForecastScenarios.py:489`, `Decimal(before) == 0`), the accuracy bias at `:452` and `:478`, and
`period_elapsed_pct`'s `total_days <= 0` guard. `Decimal` is used throughout — no `float` cast
anywhere in the derived maths. The templates guard each comparison with `is not None` first
(`board.html:11`, `attainment.html:9`, `accuracy.html:5,8,11,12`), so no `None` reaches a
comparison.

**AI gate** — `forecast_ai_gate` (`forecast_services.py:201-219`) requires
`won >= 40 AND lost >= 40` from the append-only `OpportunityOutcome` and returns the count message
otherwise. Every prediction surface on all four report pages **and** the submission detail is
gated: `board.html:8,10,11`, `call.html:7`, `forecastsubmission/detail.html:15,17` all sit behind
`{% if ai_available %}` / `{% if not ai_available %}`, the views null the figures at
`ForecastBoards.py:275-282,302-306,577-578`, and the seeder deliberately never seeds 40/40
(`seed_sales.py:626-628`). No leaked prediction value with the gate shut.

  the message; not both.

- [x] fixed — M7. `templates/sales/salesforecasting/forecastboard/attainment.html:9` vs `:11-12` — the
  main table renders `{{ row.owner.get_full_name|default:row.owner.username|default:"Unassigned" }}`
  while the two "Ahead/Behind of pace" summary lists below render `{{ row.owner }}`, i.e. raw
  `User.__str__`. The same rep appears under two different labels on one page. **Fix** — add an
  `owner_label` to each row dict in the view and use it in all three places.

- [x] fixed — M8. Amended contract §8 with a dated deviation note naming the three functions that are in \orecast_services.py\ and the eight that are view functions, rather than moving working, otherwise-correct code. See \.claude/tasks/contract-sales-8.4.md:628\. Contract drift, structural: contract §8 (contract line 626) pins ten functions in
  `apps/sales/forecast_services.py` (`forecast_rollup_rows`, `forecast_attainment_rows`,
  `forecast_accuracy_rows`, `forecast_submit`, `forecast_review`, `forecast_revert`,
  `forecast_lock_period`, `forecast_apply_scenario` alongside the three that are there). Only the
  three were moved; the rest live in the view modules. The code is fine and the module docstring is
  honest about it, but the contract is the frozen spec. **Fix** — either move the eight, or amend
  the contract with a dated note recording the deviation.

- [x] fixed — M9. `apps/sales/views/SalesForecasting/ForecastBoards.py:275-282` —
  `ai_predicted_commit` and `ai_confidence_pct` are written into **every** row dict
  unconditionally (as `None` when the gate is shut), so the gate is enforced in two places
  (view + `board.html:10-11`). Not a leak — the template double-gates and the values are `None` —
  but the redundancy means a future template that forgets `{% if ai_available %}` would render
  `None` rather than nothing, hiding the mistake. **Fix** — omit the keys entirely when
  `not ai_available` and let the template's `{% if %}` guard on `ai_available` alone.

- [~] skipped — M10. The premise is not reproducible: the finding says \ForecastSubmissionForm\ sets \self.locked_fields = []\ and never populates it, but \ForecastSubmissions.py:101-104\ does populate it — \if self.instance.pk and self.instance.is_frozen: self.locked_fields = list(self.fields)\ — so the tamper-detection path IS live for exactly the frozen records it is meant to protect (is_frozen covers both FROZEN_STATES and a locked period). Deleting the helper and attribute as instructed would REMOVE a working guard rather than fix a gap. Left as-is; see the commit that moved \_is_tenant_admin\ out of these modules for the verified import state. `apps/sales/forms/SalesForecasting/ForecastSubmissions.py:119-125` —
  `_locked_value()` compares a `Decimal` field against the raw POST string, but
  `ForecastSubmissionForm` sets `self.locked_fields = []` (line 63) and never populates it, so the
  whole tamper-detection path is inert for this form. The frozen-record rule is still enforced by
  the `period.is_locked` / `FROZEN_STATES` checks at lines 139-145, so this is defence-in-depth
  that is switched off rather than a hole. **Fix** — populate `locked_fields` in `__init__` from
  the instance's frozen state, or delete the unused helper and attribute so the next reader does
  not assume a guard that is not there.

- [x] fixed — I10. `apps/sales/forms/SalesForecasting/ForecastScenarios.py:190-194` — dead code after
  `return cleaned` in `ForecastScenarioApplyForm.clean`: a stray block that re-disables every field
  when the period is locked (and references `self.instance` / `self.fields`, which an action form
  does not reliably have). It parses — it sits inside the method body — but never executes, and it
  is a copy-paste of the block that belongs in `ForecastScenarioForm.__init__` (lines 100-105).
  **Fix** — delete lines 190-194; the locked-period refusal for the apply form is already enforced
  correctly at lines 181-182.

  page load. `select_related` inside the helpers is correct, so this is a query-count storm rather
  than a classic N+1, but the effect is the same. **Fix** — collapse the report into 2-3
  aggregates: one
  `ForecastSubmission.objects.filter(tenant=…, period__in=pks).values("period_id").annotate(...)`
  for submitted/actual/weighted, one
  `ForecastAdjustment.objects.filter(tenant=…, submission__period__in=pks, is_reverted=False)
  .values("submission__owner_id").annotate(...)` for the override table, then group in Python.

- [x] fixed — I5. `apps/sales/views/SalesForecasting/ForecastScenarios.py:529-548` and
  `apps/sales/models/SalesForecasting/ForecastScenarios.py:174-200` —
  `forecast_scenario_apply` iterates **every** scenario in the period under `select_for_update()`
  (no `[:N]`), and for each one calls `baseline_submission()` roughly seven times
  (`snapshot_projection()` → 3× `_project`, `_apply_target_amount()` → up to 3 more,
  `_baseline_target_amount()` → 1). That is ~7 **identical** `ForecastSubmission` queries per
  scenario inside one long transaction holding row locks — 350 queries for 50 scenarios.
  `forecast_scenario_detail` (lines 232-258) repeats it: `effective_*` (3) + `baseline_totals` (1)
  + the `baseline_submission` context key (1) = 5 identical queries for one page. **Fix** — hoist
  `submission = obj.baseline_submission()` above the apply loop and pass it down instead of
  re-fetching, and prefetch the baseline submissions for the whole scenario set (or cache per
  `(tenant, period)` for the request). Also cap the apply loop with a `[:N]` and report what it
  skipped.

  - `forecast_submission_snapshot()` (`forecast_services.py:170-175`) falls through to
    `weighted = Decimal("0")` and **writes `weighted_amount = 0.00`** as a stored snapshot on
    `forecast_submission_submit` (`views/.../ForecastSubmissions.py:410`);
  - the "Pipeline behind this call" panel
    (`templates/…/forecastsubmission/detail.html:26`) prints its empty state, *"No open
    opportunities match this call's owner, territory and pipeline inside the period window."* —
    an assertion the data does not support.
  A wrong stored number **and** a wrong user-facing statement, with no caveat anywhere.
  **Fix** — treat a missing close date as "lands in this period" rather than "does not exist",
  e.g. `queryset.filter(Q(close_date__isnull=True) | Q(close_date__range=window))`, and add a
  caveat when any matched opportunity had a NULL `close_date` so the panel stops claiming the
  pipeline is empty.

  - `forecast_period_export` (`views/.../ForecastPeriods.py:437-438`) emits the stale Start/End
    date columns.
  **Fix** — carry the derived window across the instance swap, one line before the field copy:
  `locked.start_date = form.instance.start_date; locked.end_date = form.instance.end_date` placed
  immediately above `form.instance = locked` at line 326 (with a comment explaining that clean()
  derived the window on `form.instance` and that `editable=False` keeps it out of the copy loop
  below). Equivalently, drop the `form.instance = locked` swap and re-check the lock against a
  re-read. Add a regression test asserting that editing `period_year`/`period_number` changes
  `start_date`/`end_date` on the saved row. `forecast_period_create` (lines 276-278) is **not**
  affected — there `form.instance` is the row that is saved.
