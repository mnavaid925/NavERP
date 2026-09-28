# Review — sub-module 0.21 "Compliance, Governance & Risk" (`core`)

> **Base:** `5ab1c305` · **Scope:** the 35 commits in `5ab1c305..HEAD` whose subject contains `0.21`
> (36 files). 0.20 commits from a concurrent session interleave in that range and are **out of scope**.
> **Contract:** `.claude/tasks/contract-core-0.21.md` (`7d96c406`).
> **Findings are hand-verified by the main session** — each was reproduced against the real files or the
> real seeded database before being written down. Reviewer claims that did not reproduce are recorded as
> retracted, not silently dropped.

## Pass 1 — `code-reviewer`

**Verified clean (checked, not assumed):**

- `makemigrations core --check --dry-run` → **"No changes detected"**; migration `0018` provably matches
  the six models and depends on the correct leaf `0017`.
- All 6 models' fields, `max_length`s, CHOICES, `related_name`s, `Meta.ordering`, `unique_together` and
  all 12 index names (≤ 30 chars) match contract §1 exactly.
- All 28 views + 2 actions filter on `tenant=request.tenant`; **no `.all()` anywhere** — no tenant leak.
- URL ordering correct: literal `compliance/` board → `crud()` groups → child literals → the 2 actions.
  No `<int:pk>` route can shadow a later literal.
- Seeder idempotency: per-entity `if not …exists()` guards, `get_or_create` on the real unique keys.
  **Proven**: re-running `seed_core` creates nothing, and rows-per-`(tenant, code)` is exactly 1 in both
  tenants (3 codes × 2 tenants = 6 rows) — not a duplicate bug.
- Seed honesty: all 3 seeded `ControlFramework` rows carry `adopted_on=None` with notes disclaiming
  certification. No row asserts compliance.
- Context-key audit, run mechanically against contract §3: **every pinned `extra_context` key is present**
  in the corresponding view. Reverse audit (template vars absent from any view) surfaced only loop
  variables, `{% for %}` choice pairs and `q` — which `crud.py:181` supplies. **No L7/L8 drift.**
- `available_controls` branching in `controlframeworkmapping/form.html` verified correct: an undefined key
  falls to the generic branch, an empty queryset to the picker.

### C1 — Critical: the seeder never computes `inherent_score`, so every seeded risk displays `0`

**`apps/core/management/commands/seed_core.py:1596-1628`**

`RiskRegister.inherent_score` is written in exactly one place — `clean()` (model line 647). `Model.save()`
does **not** call `full_clean()`, there is no `post_save` signal in `core`, and the seeder uses
`objects.create(...)`. So `clean()` never runs and all three seeded risks keep the field default `0`.

**Reproduced against the seeded database:**

```
GRC-00001 code=RSK-01 L=possible  I=major    -> inherent_score=0  band=low
GRC-00002 code=RSK-02 L=unlikely I=moderate -> inherent_score=0  band=low
GRC-00003 code=RSK-03 L=likely   I=severe   -> inherent_score=0  band=low
constructed, NOT saved: inherent_score = 0
after explicit clean():  inherent_score = 20  band = critical
does save() call full_clean? -> False
```

Consequences on a freshly seeded demo DB: `riskregister/list.html` shows `0`/"Low" for all three rows,
`Meta.ordering = ["-inherent_score", "code"]` sorts three identical zeros (inert), and the board's
`critical_risks` computes 0. The seeder's own stdout claims "all three score bands" and its comment asserts
the model recomputes the field — both false. This is the one defect that makes a shipped page state
something untrue on a register whose whole purpose is that the number is true.

Intended spread: RSK-01 3×4=12 (high), RSK-02 2×3=6 (medium), RSK-03 4×5=20 (critical).

**Fix** — call `clean()` before `save()` (not `full_clean()`: `tenant`/`number` are not valid at
construction, and this matches how the model tests exercise the guards).

```python
risk = RiskRegister(
    tenant=tenant, code=code, title=title, risk_statement=statement,
    category=category, likelihood=likelihood, impact=impact,
    treatment=treatment, treatment_plan=plan, status=status, owner=admin_user,
    reviewed_on=today - 30 * day, next_review_on=today + 335 * day,
    notes="Seeded as an EXAMPLE risk. `inherent_score` is computed by the model from "
          "likelihood x impact; this seeder never asserts a number of its own.",
)
risk.clean()      # recomputes inherent_score from the two ordinal scales
risk.save()
```

### I1 — Important: `unacknowledged_count` counts acknowledgements, the opposite of its name

**`apps/core/views/Compliance.py:266-268`**

```python
"unacknowledged_count": PolicyAcknowledgement.objects.filter(
    tenant=request.tenant, policy__status="published",
    policy__requires_acknowledgement=True).count(),
```

This counts **acknowledgement rows that exist**. An unacknowledged person has no row, so they are
invisible to this query — the count rises as people comply. The name, the contract key and
`corporatepolicy/list.html:23` ("N acknowledgements recorded against published policies") describe three
different quantities. Note the template's *prose* is actually the honest one; the key name is the liar.

**Fix** — rename the key to what is counted, `acknowledgement_count`, in the view, the template and the
contract row. Computing "who has not acknowledged" needs the eligible-user population, which is
`_acknowledgeable_users(tenant)` minus distinct acknowledged users; that is a different, larger change and
is **not** taken here.
### I2 — Important: the back-fill form silently discards the note the user typed

**`apps/core/views/Compliance.py:389-410` (`policyacknowledgement_create`)**

`PolicyAcknowledgementForm` has exactly one field, `notes` (`forms/Compliance.py:106`). The form is bound
and validated, then the row is written by:

```python
acknowledgement, created = PolicyAcknowledgement.objects.get_or_create(
    tenant=request.tenant, policy=policy, user=person,
    policy_version=policy.version,
)
```

`form.cleaned_data["notes"]` is never passed. The optional note is accepted, echoed back in the form, and
thrown away — silent data loss with no error and no warning. This is the back-fill path whose entire
purpose is to capture evidence about somebody who was not at a keyboard, so the note is the payload.

**Fix** — pass it through as `defaults={"notes": form.cleaned_data.get("notes") or ""}`. Using `defaults=`
keeps `get_or_create` idempotent on a double submit (an existing row is not mutated) and avoids a
`TypeError` on the "already acknowledged" branch.

### M1 — Minor: `corporatepolicy_list` runs a second COUNT over a queryset it is about to paginate

**`apps/core/views/Compliance.py:265`** — `qs.filter(status="published").count()` is one avoidable query
per list render. Correct, and the other 0.21 lists take the same shape, so this is a note for a future
pass rather than a defect to fix now.

### M2 — Minor: the contract table lists a `controlframeworkmapping_edit` view that does not exist

**`.claude/tasks/contract-core-0.21.md` §3** — there is no such `def` in `apps/core/views/Compliance.py`,
and `controlframeworkmapping/form.html` is create-only. This is **intentional and correct** (a mapping is
a pure join row with nothing to edit; its list page is delete-only for the same reason), but the contract
should not carry a row for a view that does not exist. The contract is corrected; no view is invented.

## Retracted claims

Recorded so they are not re-raised, and so the next reviewer does not re-derive them as if they were new.

- **"The seeder creates duplicate risks."** Retracted — rows-per-`(tenant, code)` is exactly 1 in each of
  the two tenants (3 codes x 2 tenants = 6 rows). The apparent duplication was two tenants each holding
  their own `RSK-01`; numbering restarts per tenant by design.
- **"`inherent_score` is user-overridable through the form."** Retracted — the field is genuinely absent
  from `RiskRegisterForm.Meta.fields` and `clean()` overwrites whatever arrives, so a crafted
  `inherent_score=1` cannot land. The *model* is correct; only the *seeder* bypassed `clean()` (C1).
- **"Templates read context keys no view supplies."** Retracted — a mechanical audit of all 15 templates
  against all 30 view contexts found no drift. The apparent misses were `{% for %}` loop variables, the
  `(value, label)` pairs from `*_CHOICES` iteration, and `q`, which `crud.py:181` supplies to every list.

## Fix order for Phase 5

1. **C1** — seeded scores are `0` on every fresh demo DB. One file, ~6 lines, and it makes a shipped page
   state something false.
2. **I2** — silent loss of user-entered data.
3. **I1** — a key whose name says the opposite of its value; rename in three places (view, template,
   contract) or compute the real thing.
4. **M2** — contract row for a nonexistent view.
5. **M1** — deferred, no change.

## Pass 2 — `explorer`

Scored across 5 areas. **Areas 2 (dropped wiring) and 5 (core-spine reuse) came back CLEAN**; those
results are recorded because a clean area is a result, not a silence.

**Wiring — verified mechanically, 0 gaps:** 6/6 models in `admin.py`; 11/11 CHOICES/VALUES constants
re-exported from `models/__init__.py` (runtime `hasattr` check, not grep); 6/6 forms in `forms/__init__.py`;
30/30 view functions in `views/__init__.py`; all 29 URL names `reverse()`; `LITERAL_PREFIX_MODELS`
registration consistent with how `CFW`/`CTL`/`CPOL`/`GRC` are actually minted; the seeder registers all four
`NumberingScheme` rows; `conftest.py` is genuinely append-only (the 0.21 block sits above the pre-existing
`import pytest` / `from django.test import Client` and redeclares nothing — all 11 new fixtures are
`cml021_`-prefixed, the 3 originals untouched); every helper in `test_compliance_models.py` is
`_cml021_`-prefixed and every test is `test_compliance_*`, so the next sub-module cannot shadow them.

**Core-spine reuse — CLEAN and the strongest part of the changeset.** Verified against the actual files:
no duplicated framework table (`ControlFramework` = certification programme, 0.8 `RegulatoryFramework` =
the law, with `dsar_window_days` + `data_residency_region`; different facts, different lifecycles, and the
boundary is stated in the model docstring, `models/__init__.py`, `navigation.py` and
`corporatepolicy/list.html:16-18`). `CorporatePolicy` is distinct from both 0.8 `RetentionPolicy` and
`hrm.HrPolicy`. `PolicyAcknowledgement` is distinct from `core.AuditLog` (`AuditLog.user` is
system-written; an acknowledgement is a human act). All three `owner` fields are actor FKs with
`SET_NULL`/`related_name="+"`, matching `Backup.py:202` / `Security.py:665` / `Monitoring.py:470`; every
place free text *is* used carries a one-line justification for why a closed set would be wrong.

**Convention — no drift found.** `models.Model` used directly rather than `TenantConsistentMixin`, which
matches the closest siblings (`Privacy.py:17,72`, `Change.py:90,179`); `Security.py` uses the mixin, so
both patterns exist in this app and 0.21 picked the right neighbour. `@require_POST` above
`@tenant_admin_required` on all 7 mutating routes is correct (decorators apply bottom-up, so the role gate
runs first) and is documented at `views/Compliance.py:21`. Message audit: every success says "recorded";
grepping `enforced|granted|reminded|verified|compliant` across all 11 messages returns nothing, matching the
module's honesty rule. The two entities with no detail page have no `detail.html` on disk, no detail route,
and — the part that matters — no dead `{% url %}` to either. The `{% if x is not None %}` branch in
`controlframeworkmapping/form.html` correctly falls to the generic form when `available_controls` is
undefined and to the picker when it is an empty queryset.

### I3 — Important: `grc_overview` builds two querysets its template never reads

**`apps/core/views/Compliance.py:506,509`** — `"controls": controls.order_by("code")[:8]` and
`"policies": policies.order_by("code")[:8]`. `templates/core/grcoverview.html` renders the frameworks
panel (`{% for fw in frameworks %}`, line 71) and the risks panel (`{% for risk in risks %}`, line 97), and
reports `published_policies` / `open_risks` as scalar counts. It never iterates `controls` or `policies`.
Two wasted queries per board render, on the page an auditor opens first.

**Fix** — drop both keys. `controls` and `policies` stay in the view as local variables; they are still
used for the `critical_risks` / `overdue_reviews` / `published_policies` counts.

### I4 — Minor: `controlframeworkmapping_list` passes a `controls` queryset it never uses

**`apps/core/views/Compliance.py:176`** — the list template filters on `coverage` and `framework`
(line 31 and 37) but has no control filter, so `ComplianceControl.objects.filter(tenant=...)` is one
wasted query per render. Either drop the key or add the missing control filter dropdown; dropping is the
smaller honest change.

### M3 — Minor: form-page context keys leak non-context values into the audit

`policyacknowledgement_create` passes `is_edit` / `on_behalf_of` / `recorded_by` / `people` /
`policies`; `people` and `policies` are genuinely used (form.html:40, 48) and the rest are read by
`partials/form_field.html`. Recorded as **no defect** — noted only so the next reviewer does not re-derive
it as one.

## Fix order update (Phase 5)

1. **C1** — seeded `inherent_score = 0` on every fresh demo DB (seeder).
2. **I2** — back-fill form silently drops the typed note (`views/Compliance.py`).
3. **I1** — rename `unacknowledged_count` to what it counts (view + template + contract).
4. **I3** — drop two unused querysets from `grc_overview`.
5. **I4** — drop the unused `controls` queryset from `controlframeworkmapping_list`.
6. **M2** — remove the contract row for the nonexistent `controlframeworkmapping_edit` view.
7. **M1** — deferred, no change.

## Pass 3 — `frontend-reviewer`

**No Critical findings.** Nothing 500s, no dead route, no blank region, no unescaped user data.
**Areas 4 (XSS), 5 (markup/colspan/empty states) and 6 (structure) came back CLEAN.**

**Verified clean, and worth stating because these are the checks that usually fail:**

- **CRUD completeness**: the 4 full-CRUD entities each carry the complete Actions column — View (eye),
  Edit (pencil), Delete (POST form + `{% csrf_token %}` + `confirm`) — plus Edit/Delete in the detail
  header. The 2 delete-only entities explain that decision *in-file*.
- **XSS**: no `|safe`, no `{% autoescape off %}`, no unescaped `request.GET`. The only `request.GET` echo
  is `value="{{ q }}"`, autoescaped and supplied by `crud.py:181`. `|linebreaksbr` is used correctly on 3
  sites (it escapes before converting). All 12 `confirm()` strings are fixed literals with no apostrophe
  or backslash — honouring the L42 rule in `partials/confirm_button.html:20-29` — and none is built from a
  row value, so "deleted with no confirmation" cannot occur.
- **Table markup**: every `colspan` matches its real header count (8/8, 7/7, 7/7, 8/8, 6/6, 6/6);
  `<thead>`/`<tbody>` well-formed on all 12 tables; every panel has a real empty state.
- **Better than the siblings**: all 15 filter controls carry `aria-label`, where `retentionpolicy/list.html:22,28`
  has bare selects with none. No `<th scope="col">` anywhere — but no core sibling uses it either, so that
  is consistency, not a deviation.

### I5 — Important: `badge-blue` does not exist, so 3 badges render with no colour at all

**`riskregister/list.html:64`, `riskregister/list.html:74`, `grcoverview.html:102`**

**Verified:** `static/css/theme.css:284` defines `.badge` with **only** shape/typography — `padding`,
`border-radius`, `font-size`, `font-weight` — and **no** `background`/`color`. The palette defines exactly
six: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
`badge-blue` appears **nowhere** in `static/css/`, and these 3 lines are its only uses in the whole
`templates/` tree.

The pill still renders, so nothing looks broken — it renders *colourless*. The "Medium" band and **all
four open risk statuses** (`identified`, `assessing`, `treating`, `monitoring`) lose their fill, so on the
register whose leading column *is* the score band, "Medium" is indistinguishable from "Low", and the
board's "N in the critical band" caption has no coloured counterpart. Invisible to any template-only check.

**Fix** — `badge-blue` → `badge-info` at all three lines. Swap the template rather than adding a
`.badge-blue` alias to the shared stylesheet: 0.21 is the only consumer, and the theme already owns the
palette.

### I6 — Important: the coverage badge's `{% else %}` hardcodes "Not started" instead of `get_coverage_display`

**`controlframework/detail.html:68`, `compliancecontrol/detail.html:67`, `controlframeworkmapping/list.html:60`**

```html
{% else %}<span class="badge badge-slate">Not started</span>{% endif %}
```

The three explicit branches are exact `COVERAGE_CHOICES` members, so nothing is blank **today**. But the
terminal branch must be `{{ mapping.get_coverage_display }}` (Filter rule 5 and `contract-core-0.21.md:451-452`).
As written, any future fifth coverage value renders as **"Not started"** — a false statement, on the one
axis (`coverage`, the recorded-vs-enforced distinction) this module exists to keep honest. The correct
pattern sits 20 lines away in the same directory: `compliancecontrol/list.html:55` ends
`{% else %}<span class="badge badge-slate">{{ obj.get_status_display }}</span>{% endif %}`.

**Fix (×3)** — `{% else %}<span class="badge badge-slate">{{ mapping.get_coverage_display }}</span>{% endif %}`
(`obj.` rather than `mapping.` in the two detail templates).

### M4 — Minor: no `<th scope="col">` in any of the 15 templates

Consistent with every other core list page, so **not** fixed here. Recorded so a future accessibility pass
does not re-derive it as a 0.21 regression.

## Fix order update (Phase 5)

1. **C1** — seeded `inherent_score = 0` on every fresh demo DB (seeder).
2. **I2** — back-fill form silently drops the typed note (`views/Compliance.py`).
3. **I5** — `badge-blue` → `badge-info` at 3 sites (2 templates).
4. **I6** — coverage badge `{% else %}` → `get_coverage_display` at 3 sites (3 templates).
5. **I1** — rename `unacknowledged_count` to what it counts (view + template + contract).
6. **I3** — drop two unused querysets from `grc_overview`.
7. **I4** — drop the unused `controls` queryset from `controlframeworkmapping_list`.
8. **M2** — remove the contract row for the nonexistent `controlframeworkmapping_edit` view.
9. **M1**, **M4** — deferred, no change.

## Pass 4 — `performance-reviewer`

This pass found the **worst defect in the whole review**, and it is a shipped-broken page rather than a
blemish. Measurement was claimed live; the two claims that matter were **re-verified by the main session
against the live dev database** (see C2 below).

### C2 — Critical: `annotate()` collides with a same-named `@property` and 500s two list pages

**`apps/core/views/Compliance.py:201-202` and `256-257`**

```python
qs = ComplianceControl.objects.filter(tenant=request.tenant).annotate(framework_count=Count("mappings"))
qs = CorporatePolicy.objects.filter(tenant=request.tenant).annotate(acknowledged_count=Count("acknowledgements"))
```

`ComplianceControl.framework_count` (`models/Compliance.py:337-339`) and
`CorporatePolicy.acknowledged_count` (`models/Compliance.py:491-493`) are `@property`. A `property` is a
**data descriptor**, so Django's `ModelIterable` cannot `setattr` the annotation onto the instance and the
query raises on evaluation.

**Verified by the main session against the live dev DB — both list pages are dead:**

```
SQL  compliancecontrol_list: SELECT `core_compliancecontrol`.`id`, ... GROUP BY ...
     -> AttributeError: can't set attribute 'framework_count'
SQL  corporatepolicy_list:    SELECT `core_corporatepolicy`.`id`, ... GROUP BY ...
     -> AttributeError: can't set attribute 'acknowledged_count'
```

So `/core/compliance/controls/` and `/core/compliance/policies/` return **HTTP 500** for any tenant that
actually has rows. This is why the earlier content smoke passed and this is not: that smoke ran as a tenant
with **0 controls and 0 policies**, and iterating an empty queryset never reaches the `setattr`. The smoke
was structurally incapable of catching it — worth keeping (L8: a 200 with rows present is the only real
assertion).

**Two further harms from the same annotation**, both visible in the generated SQL above:

1. **It destroys `Meta.ordering`.** Django suppresses `Meta.ordering` when the query has a `GROUP BY`, so
   both pages lose `ordering = ["code"]` and raise
### I7 — Important: owner N+1 on three list pages

**`apps/core/views/Compliance.py:66, 200, 255, 437`** — only `riskregister_list` (line 468) has
`select_related("owner")`. The other three lists render `obj.owner`, so a 20-row page issues 1 + 20
`accounts_user` queries. **Verified**: `select_related` appears at lines 94, 155, 167, 231, 286, 353 and
**only** 468 — the risk list.

**Fix** — add `select_related("owner")` to `controlframework_list`, `compliancecontrol_list` and
`corporatepolicy_list`, matching line 468.

### I8 — Important: `grc_overview` computes aggregates in Python over full querysets

**`apps/core/views/Compliance.py:500-516`** — `framework_count`, `critical_risks` (a Python
`sum(1 for r in risks if r.score_label == "critical")` over the **entire** register) and `overdue_reviews`
(a Python sum over **all** controls and **all** risks) each fetch or scan rows the template never displays.
Only the `[:8]` slices reach the page. As the register grows this is O(all rows) per board load, and
`critical_risks` cannot use `grc_tenant_score_idx` because the banding happens in Python.

**Fix** — `critical_risks` becomes
`RiskRegister.objects.filter(tenant=tenant, inherent_score__gt=16).count()` (uses `grc_tenant_score_idx`);
`overdue_reviews` becomes two `.filter(next_review_on__lt=today).exclude(next_review_on=None).count()`;
`framework_count` stays a `.count()`. Keep the `[:8]` display querysets as they are.

### I9 — Minor: `corporatepolicy_detail` issues two identical COUNTs on `policy_id`

`acknowledgements.count()` for the header, then the same count again inside `acknowledgement_rate`. One is
reclaimable by passing the value through the context.

### Corrections to already-recorded findings (measured precision, not new defects)

- **I3** (`grc_overview` unused `controls`/`policies`) — costs **1** query, not two: the board issues no
  `SELECT … FROM core_corporatepolicy` at all, so `policies[:8]` is never evaluated. Only `controls[:8]`'s
  base queryset is touched, by the `overdue_reviews` sum. The real board waste is the five separate COUNTs
  and the three full fetches (now I8).
- **I4** (`controlframeworkmapping_list` unused `controls`) — costs **zero** queries. An unevaluated
  queryset in a template context is never fetched. It is **dead context, not a wasted round-trip**; still
  worth dropping, but as tidiness rather than performance.

**Areas verified CLEAN:** `riskregister_detail` measures 1 app query with `select_related`;
`policyacknowledgement_list` 4 queries, no N+1; `controlframeworkmapping_list` 3 queries; all 12 index names
≤ 30 chars; `makemigrations --check` clean; every list view filters `tenant=request.tenant`;
`score_label` / `is_open` / `is_overdue_review` are pure-Python and DB-free (**verified** — they compare
fields and call `timezone.localdate()` only); seeder idempotency intact, `get_or_create` on real unique keys.

## Consolidated fix order (Phase 5)

| # | Finding | File(s) | Why |
|---|---|---|---|
| 1 | **C2** — annotate/property collision, two 500s | `views/Compliance.py` + 2 templates | Only defect that breaks a page |
| 2 | **C1** — seeded `inherent_score = 0` | `seed_core.py` | Shipped page states something false |
| 3 | **I2** — back-fill drops the typed note | `views/Compliance.py` | Silent loss of user data |
| 4 | **I5** — `badge-blue` undefined (3 sites) | 2 templates | Wrong on every render, but invisible |
| 5 | **I6** — hardcoded "Not started" (3 sites) | 3 templates | False statement on the honesty axis |
| 6 | **I7** — owner N+1 on 3 lists | `views/Compliance.py` | Linear query growth |
| 7 | **I8** — Python aggregates over full querysets | `views/Compliance.py` | O(all rows) per board load |
| 8 | **I1** — rename `unacknowledged_count` | view + template + contract | Name says the opposite |
| 9 | **I3** / **I4** — dead context keys | `views/Compliance.py` | Tidiness |
| 10 | **I9** — duplicate COUNT on policy detail | `views/Compliance.py` | Minor |
| 11 | **M2** — contract row for a nonexistent view | `contract-core-0.21.md` | Docs |
| — | M1, M4 | — | Deferred, no change |

   `UnorderedObjectListWarning: Pagination may yield inconsistent results with an unordered object_list`
   (`crud.py:23`). That is non-deterministic `LIMIT/OFFSET` pagination **and** it forfeits the
   `(tenant_id, code)` unique index as the sort source. The SQL has `GROUP BY` with **no `ORDER BY`**.
2. **It forces a temp table + filesort** where the plain query was an index-ordered scan.

Net: an optimisation intended to replace N per-row `COUNT`s delivers **zero** benefit here while adding a
`LEFT JOIN` + `GROUP BY` to the paginator's own COUNT and destroying the sort index on the module's two
most-read registers.

**Fix (one rule, applied consistently).** An annotation alias must never equal a model `@property` name.
Either drop the two colliding properties, or rename the aliases and update the two templates. **Chosen fix:
keep the properties (the detail views legitimately use them), rename the annotations to `mapping_total` /
`acknowledgement_total`, and add explicit `.order_by("code")` to restore deterministic pagination.** Then
re-measure.

## Pass 5 — `qa-smoke-tester` (report-only; fix behaviour overridden)

**301 recorded checks, 3 runs, ~50s each.** The critical methodological point: this pass built its **own
tenants with 18 rows in each of the 6 models** (so the 15-per-page paginator has a real page 2 and a junk
filter has something to wrongly empty), plus a second tenant for the IDOR lane, and asserted row codes as
**literal strings in the HTML** — not just status codes. That is precisely what the original smoke could not
do, and it is why this pass found what the others missed.

### C2 is upgraded — `corporatepolicy_list` is a MASKED 500, which is worse than the 500 recorded above

**Verified by the main session (ORM mechanism), with the end-to-end HTTP behaviour observed by the agent:**

| Request (4 policies in the tenant) | Expected | Actual |
|---|---|---|
| `GET /core/compliance/policies/` | 200 | **500** |
| `GET /core/compliance/policies/?q=PONLYONE` (1 row) | 200 | **500** |
| `GET /core/compliance/policies/?q=zzzznotarealvalue` (0 rows) | — | **200 + "No policies recorded"** |

Mechanism, confirmed by the main session: Django only trips when it `setattr`s the annotation **onto an
instance** (`query.py:133`). `corporatepolicy_list` never instantiates on the empty path — it only calls
`.count()` — so a filter matching nothing renders **200 with the empty state on a workspace holding four
policies**. That asserts something false about the register, and a status-only smoke scores it *passing*.
This is the worst behaviour in the changeset and it is strictly worse than the plain 500 recorded in pass 4.

### C3 — Critical: `compliancecontrol_list` 500s unconditionally, and no empty-state smoke can ever see it work

**`apps/core/views/Compliance.py:201-202` and `:210`**

Beyond the same alias collision, the view iterates the annotated queryset **at context-build time**:

```python
"overdue_count": sum(1 for c in qs if c.is_overdue_review),
```

`qs` is the **unfiltered** annotated queryset, so it instantiates controls even when the page's own result
set is empty. **Verified**: `sum(1 for c in qs if c.is_overdue_review)` raises
`AttributeError: can't set attribute 'framework_count'` against the live DB. The page is therefore dead at
3 rows, at 1 row **and at 0 rows** — a "no rows" smoke cannot make this page pass under any circumstances.

Folded into the C2 fix: rename the aliases and replace the Python `sum` with a DB-side count (I8).

### I10 — Important (design, not a bug): the acknowledgement register can only ever contain admins

Every 0.21 page — **including the policy detail page where the Acknowledge button lives** — is
`@tenant_admin_required`, and so is `policy_acknowledge`. **Proven**: a non-admin member POSTing
acknowledge gets **403** and writes nothing.

But `policyacknowledgement/list.html` describes itself as "One row per person, per policy, per version",
and `CorporatePolicy.acknowledgement_rate` divides acknowledgements by the *active user count* — i.e. the
register and the rate are both written as if the whole workforce acknowledges. In practice only tenant
admins ever can. On a real workspace `acknowledgement_rate` will read near-0% and imply non-compliance
where the real cause is that members cannot click the button at all.

This is a **scope** finding, not a defect in what was built — but it must not ship as a silent lie. Fix:
either drop `@tenant_admin_required` from the acknowledge action and the policy detail page (a signed-in
member may acknowledge; the *back-fill* stays admin-only), **or** keep the gate and reword the register and
the rate's denominator so neither claims to cover people who were never able to act. **Chosen: keep the
admin gate** (it is the safer default and the 0.16 evidence-stamp convention supports it) and reword —
changing an authorization boundary mid-review is the riskier edit, and the wording change is honest either
way. Recorded so the decision is explicit rather than accidental.

### I11 — Important: `framework_count` means three different things in one module

It is a `@property` on `ComplianceControl`, an `annotate` alias on that same model, **and** the board's
`ControlFramework` count (`grcoverview.html:30`). This is what made C2 easy to introduce and hard to see.
**Fix** — distinct names: `n_mappings` (annotation), `mapping_total` (property), and leave the board's
`framework_count` alone since it is a different model.

**C2 fix, revised in light of the above:** rename the annotations to `mapping_total` / `acknowledgement_total`
(no model property shares those names), update the two templates that read them, add explicit
`.order_by("code")` to restore deterministic pagination, and replace `compliancecontrol_list`'s
`sum(1 for c in qs ...)` with a `.filter(...).count()`.

### Verified passing all seven checks (state this — it is most of the surface)

- **List pages** — frameworks, risks, mappings, acknowledgements: all 7 (status, content, junk params,
  page 2, IDOR, permissions, POST-only).
- **Detail pages** — framework, control, policy, risk: all 7.
- **Form pages** — 6 create + 4 edit: fields present and correctly pre-filled on edit.
- **GRC board** `/core/compliance/`: all 7.
- **Delete POSTs** — all 6: GET 405 with no mutation, POST 302 and the row is gone.
- **`policy_acknowledge`** — GET 405; POST on a published policy writes +1 with the correct actor and the
  version **snapshotted**; **draft and retired both refused with a message and +0 rows**; idempotent on a
  double press; re-versioning opens a new round and the superseded badge renders. The evidence-stamp
  design works.
- **`controlframeworkmapping_add`** — picker excludes an already-mapped control **from the `<select>`**
  (it still appears under "Already mapped"); POST 302 +1 at `not_started`; idempotent; cross-tenant
  `control_id` → 404; junk `control_id` → no 500.
- **Junk params** — `?type/is_active/status/policy_type/treatment/likelihood/coverage=bogus`,
  `?framework=notanint`, `?policy=notanint`: all 200 showing the **full unfiltered 15-row page 1**.
- **Pagination** — `?page=2/0/999/-1/abc`: all 200 clean; page 2 is a genuinely different row set.
- **`?q=` no-match** — 200 + empty state, **no row text leaked**; `?q=<real>` still finds its row.
- **Cross-tenant IDOR** — 9 GETs + 7 POSTs: all **404**, no tenant-B text in any body, and every foreign
  row was still alive afterwards.
- **Permissions** — 22 pages, 6 delete POSTs, mapping-add POST: non-admin member 403 throughout; anonymous
  302. `policy_acknowledge` GET is **405, not 403** — method is checked before the role, which is the
  documented and correct decorator order.
- **Tenant-B isolation** on the 4 working lists and the board: no tenant-A text; tenant-B sees its own rows.

### False alarms run down (each was a defect in the test, not the app — do not re-report)

- *"CREATE policy/risk returns 200 with no row"* — incomplete payloads; the forms correctly required
  `policy_type`/`version` and `likelihood`/`impact`/`treatment`/`status`. With complete payloads: 302 + row,
  and `inherent_score` = 20 (likely x severe) — **the create path computes the score correctly**, which
  independently corroborates that C1 is confined to the seeder.
- *"DELETE mapping/acknowledgement already gone"* — both are `CASCADE` children and the parents had been
  deleted first. With parents intact: 405 on GET, 302 + gone on POST. The cascade is correct.
- *"`policy_acknowledge` writes 0 rows"* — an acknowledgement had been pre-created for every policy, so the
  POST hit the `unique_together` guard. Against a policy with no row: 302, +1, actor and version correct.
- *"An already-mapped control is offered again"* — parsing the `<select name="control_id">` shows it is not
  an option; it is only in the "Already mapped" context list. The picker is correct.
- *"Empty state has 2 rows"* — the counter matched `<tr>` inside `<thead><tr>`; a regex on `<tr>\s*\n` gives
  exact counts.

### Environment finding worth keeping

`--reuse-db` was unusable for this pass: `nav_erp_test.sqlite3` was **locked by the concurrent session**
(`database is locked` on `DROP INDEX prc_asl_tnt_sealed_idx`), and a file copy was a mid-migration snapshot.
`--no-migrations` was used instead — tables built straight from the models, seconds not 20 minutes, fully
isolated. **Worth adding to the notes in `config/settings_test.py`.**

### Housekeeping

`nav_erp_smoke.sqlite3` (18 MB) was left in the project root as an untracked, disposable scratch copy of the
shared test DB, held by a process this agent could not safely identify. Delete once that process exits.

## Pass 6 — `security-reviewer`

**No Critical.** **No tenant-isolation break, no IDOR, no CSRF hole, no injection.** The earlier passes'
conclusion that the scoping and method gates hold up under edge-case and related-hop analysis.

**Areas verified CLEAN (with the reason, so it need not be re-derived):**

- **Related-hop tenant isolation** — every `framework.mappings` / `control.mappings` hop starts from an
  object fetched with `tenant=request.tenant`, so the hop cannot cross. All 6 `get_object_or_404` calls in
  the two actions are tenant-scoped, as are the `int()`-coerced POST reads.
- **Mass assignment** — `inherent_score` and `residual_score` are confirmed off `RiskRegisterForm`;
  `user` and `policy_version` off `PolicyAcknowledgementForm`; `tenant` supplied by `TenantModelForm` and
  never a form field. No derived or evidence field is reachable through a bound form.
- **CSRF / method safety** — every state-changing 0.21 route is POST-only, and every POST form carries
  `{% csrf_token %}`. No GET mutates.
- **Injection** — `q` reaches `Q(**{f"{field}__icontains": q})` (`crud.py:37-43`): pure ORM, fully
  parameterised, and the field names are developer literals, never user input. int-FK filters are declared
  `is_int=True` and already go through `as_db_int`. A repo-wide grep for `.raw(`, `.extra(`, `eval(`,
  `exec(`, `mark_safe`, `|safe`, `autoescape off` and request-driven dynamic `getattr` returned **no hits**
  in 0.21.
- **Information disclosure** — cross-tenant and nonexistent pks both answer 404 with an identical body, so
  there is no 404-vs-403 enumeration oracle. All four `GRC_NOTES` strings *remove* a misconception; none
  discloses a host, path, key or another tenant's data.
- **`acknowledged_at` is `DateTimeField(auto_now_add=True, editable=False)`** — verified. It cannot be
  backdated through any form, and `editable=False` keeps it off every ModelForm.
- **Seeder safety** — every seeded framework carries `adopted_on=None` with an explicit "registered, not
  adopted" note; the one `effective` control has a real `last_reviewed_on`; the acknowledgement block picks
  a `published` policy, not a draft; `owner` is left `None` rather than inventing an identity.

### I12 — Important: `int()` on an `isdigit()`-guarded POST pk is a reachable uncaught 500

**`apps/core/views/Compliance.py:133,139` and `:393,397,400`**

`str.isdigit()` and `int()` accept **different character sets**. **Verified on this machine:**

```
'²'  (U+00B2)  isdigit=True  int() -> ValueError: invalid literal for int() with base 10
'³'  (U+00B3)  isdigit=True  int() -> ValueError
'9'*100        isdigit=True  int() -> 99999999999999999999  -> OverflowError in the SQLite driver
```

So `POST /core/compliance/frameworks/1/add-controls/` with `control_id=%C2%B2` — or 100 nines — is an
unhandled 500. Neither `ValueError` nor `OverflowError` is caught anywhere in the path.

**The repo has already diagnosed this exact class.** `crud.py:59-63` defines `as_db_int`, whose docstring
names the correct predicate and cites **L11**: *"`?vendor=abc` and `?vendor=²` are refused by `isdecimal()`"*.
**Verified behaviour:**

```
as_db_int('²')      = None      as_db_int('12')  = 12
as_db_int('9'*100)  = None      as_db_int('0x1') = None
as_db_int('')       = None      as_db_int('-3')  = None
### I13 — Important: acknowledgement evidence is hard-deletable, and a policy delete cascades it away

**`views/Compliance.py:427-431`, `:301-305`, `models/Compliance.py:534`**

Any tenant admin can delete an acknowledgement via the list page's delete action, and deleting a
`CorporatePolicy` cascades its acknowledgements away. Neither path writes an audit row. For a module whose
central claim is that its rows are trustworthy evidence, a plain delete with only a JS `confirm()` (which a
direct POST bypasses) is the wrong affordance.

**Secure fix** — refuse deletion of a `PolicyAcknowledgement` outright with an explanatory message, and
block deletion of a `CorporatePolicy` that still has acknowledgements unless an explicit override is posted.
Both are ordinary, authorised actions — which is exactly why the cross-tenant IDOR and permission passes
could not have caught this.

### I14 — Important: `acknowledgement_rate` counts attestations of *any* version

**`models/Compliance.py:491-509`** — the rate divides the acknowledgement count by the active-user count
without filtering on `policy_version`. So editing a policy's `version` retroactively "validates" every prior
acknowledgement of the earlier version. **Every individual row on the page is truthful; only the aggregate
lies** — the more subtle of the two evidence findings.

**Secure fix** — filter to the current version:
`self.acknowledgements.filter(policy_version=self.version).count()`, and say in the template when older
versions exist rather than silently counting them.

### M5 — Minor: the seeder attributes acknowledgements to real named users

**`seed_core.py:1584-1595`** — a seeded acknowledgement is indistinguishable from a genuine attestation
unless the reader already knows it is demo data. Acceptable for a demo seeder, but the row's own `notes`
should say so rather than relying on the seeder's stdout.

## Phase 4 summary — 3 Critical, 11 Important, 5 Minor, 6 retractions

| ID | Finding | Sev | File |
|---|---|---|---|
| **C1** | Seeder never calls `clean()`; every seeded risk shows `0`/"Low" | Critical | `seed_core.py` |
| **C2** | `annotate()` alias collides with a `@property`; policy list is a **masked** 500, control list 500s unconditionally | Critical | `views/Compliance.py` |
| **C3** | Control list instantiates the annotated `qs` in Python at context-build time | Critical | `views/Compliance.py` |
| **I1** | `unacknowledged_count` counts the opposite of its name | Important | view + template + contract |
| **I2** | Back-fill form silently drops the typed note | Important | `views/Compliance.py` |
| **I3** | `grc_overview` passes two querysets its template never reads | Important | `views/Compliance.py` |
| **I4** | `controlframeworkmapping_list` passes a dead `controls` queryset | Important | `views/Compliance.py` |
| **I5** | `badge-blue` is not a class in the theme; 3 badges render colourless | Important | 2 templates |
| **I6** | Coverage badge `{% else %}` hardcodes "Not started" | Important | 3 templates |
| **I7** | Owner N+1 on three list pages | Important | `views/Compliance.py` |
| **I8** | Board aggregates computed in Python over full querysets | Important | `views/Compliance.py` |
| **I9** | Policy detail issues two identical COUNTs | Important | `views/Compliance.py` |
| **I10** | Acknowledgement register can only ever contain admins | Important | design — reword |
| **I11** | `framework_count` means three different things | Important | naming |
| **I12** | `int()` on `isdigit()`-guarded POST pk → uncaught 500 + DEBUG traceback | Important | `views/Compliance.py` |
| **I13** | Acknowledgement evidence is hard-deletable; cascades on policy delete | Important | views + model |
| **I14** | `acknowledgement_rate` counts any version, so re-versioning validates the cohort | Important | `models/Compliance.py` |
| **M1** | Extra COUNT on the policy list | Minor | deferred |
| **M2** | Contract lists a `controlframeworkmapping_edit` view that does not exist | Minor | contract |
| **M3** | Form-page context keys — **no defect**, recorded to stop re-derivation | Minor | — |
| **M4** | No `<th scope="col">` — consistent with every core sibling | Minor | deferred |
| **M5** | Seeded acknowledgements attributed to real users | Minor | seeder |

**The three Criticals share one root cause worth naming: nothing asserted content on a page that had rows.**
The original smoke ran against a tenant with zero controls and policies and passed; the C2/C3 pages were dead
the entire time. Fixing the smoke's blind spot — rows present, code asserted as a literal in the HTML — is
what found the worst defect in the changeset.

```

And the view's own comment at `Compliance.py:136-138` asserts the **opposite** of the truth: *"`as_db_int`
is deliberately NOT used here: … the isdigit guard above already refuses the junk that reaches it."* It does
not. The helper is one import away in the same package.

Impact: authenticated tenant-admin availability loss, plus — because `DEBUG = _bool("DEBUG", "True")`
**defaults to True** in `config/settings.py:16` — a Django technical 500 page with a full traceback and
local variables, which here include the resolved `request.tenant` and the queryset. Not an isolation
break; a reachable crash plus a traceback.

**Secure fix** — use the existing helper in all three places and delete the incorrect comment:

```python
from apps.core.crud import as_db_int

number = as_db_int(control_id)
if number is None:
    messages.error(request, "Choose a control to add.")
    return redirect("core:controlframeworkmapping_add", pk=pk)
control = get_object_or_404(ComplianceControl, pk=number, tenant=request.tenant)
```

