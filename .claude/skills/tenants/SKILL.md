---
name: tenants
description: Work on the Tenants & Licensing module (tenant registry, subscription/billing, and 0.19 License & Subscription Administration - entitlement features, plan grants, usage quotas, seat assignments). Use when the user asks to add/change/debug anything under apps/tenants or templates/tenants, or invokes /tenants.
---

# Tenants & Licensing (`apps/tenants`)

**A Module 0 FOUNDATION app.** It has **no NavERP sub-module level** — models, forms, views and
templates are all FLAT at the app root (`apps/tenants/models/Subscription.py`,
`templates/tenants/subscription/list.html`). This is rule 4 of the template-structure rules: Module 0
owns no `N.M`, so there is no `<SubModule>/` folder to nest under. Do **not** "graduate" this app to
the two-level shape.

## Sub-modules built here

| # | Name | State |
|---|------|-------|
| 0.1 | Tenant, subscription, billing, usage | built |
| 0.19 | License & Subscription Administration | built |

## Models

**`tenants` (0.1)** — `Subscription`, `SubscriptionInvoice`, `UsageRecord` (and `Tenant` itself lives
in `apps/core`).

**0.19 — four flat models, all in `apps/tenants/models/`:**

| Model | File | Number | Notes |
|---|---|---|---|
| `EntitlementFeature` | `EntitlementFeature.py` | `ENT-` | the vocabulary. `code` is lowercase-underscored, unique per tenant |
| `PlanEntitlement` | `PlanEntitlement.py` | `PE-` | a grant. `subscription=NULL` → plan-level; set → per-subscription OVERRIDE |
| `UsageQuota` | `UsageQuota.py` | `UQ-` | the commercial ceiling. `quota_limit` is a **CharField**; `"0"` means UNMETERED |
| `LicenseAssignment` | `LicenseAssignment.py` | `SEAT-` | a seat. **never `LIC-`** — `scm.TradeLicense` already owns that prefix |

**`SEAT-` is not a typo.** `NumberingScheme` is unique per `(tenant, prefix)`, so two registers
minting the same customer-facing number is a real collision. `LIC-` is taken by SCM. All four
prefixes are registered in `LITERAL_PREFIX_MODELS`.

### The three derived facts (properties, never columns)

- `PlanEntitlement.is_override` — `subscription_id is not None`. A property, not a boolean column:
  `subscription` is `SET_NULL`, so a stored flag would outlive the row it describes.
- `LicenseAssignment.is_reclaimable` — `status == "active"`.
- `LicenseAssignment.is_expired` — derived from `expires_on`. **Nothing ever writes `status="expired"`.**

### The two columns 0.19 added to `Subscription`

- `auto_renew` — **three-state** (`True` / `False` / `None`). `None` means *nobody has expressed an
  intent*; it shipped as `BooleanField(default=True)` once and was wrong, because it stamped every
  pre-existing subscription with a decision nobody made. Migration `0006`.
- `grace_ends_on` — a date, the end of the grace window.

## Vocabularies are shared BY REFERENCE

`UsageQuota.METRIC_CHOICES is UsageRecord.METRIC_CHOICES` and
`PlanEntitlement.PLAN_CHOICES is Tenant.PLAN_CHOICES`. Assert `is`, not `==` — two equal lists are
still two lists, and a pasted copy is the exact duplication 0.19 exists to prevent.

## URLs (`apps/tenants/urls.py`, `app_name = "tenants"`)

0.1: `subscription_list|create|detail|edit|delete`, `subscription_mark_paid`,
`subscription_webhook`, `invoice_*`, `usage_*`.

**0.19 — 24 routes under `/tenants/licensing/`:**
`entitlementfeature_list|create|detail|edit|delete`, the same five for `planentitlement`,
`usagequota` and `licenseassignment`, plus two boards — `quota_board`, `renewal_board` — and two
POST-only verbs, `usagequota_mark_breached` and `licenseassignment_reclaim`.

**Order is behaviour.** Django is first-match-wins: the two literal board segments are declared
BEFORE the `<int:pk>` siblings or they are swallowed.

**`crud_detail` does not exist.** The four `_detail` views call `render()` directly after ONE
`get_object_or_404` (contract [RULING] 10). `views/_common.py` does not export `crud_detail`;
calling it was the Phase 3.5 500. `crud_create` / `crud_edit` / `crud_delete` **are** exported.

**`reverse()` takes positional `args`**, never a `pk=` kwarg — `reverse("tenants:x", pk=1)` is a
TypeError.

## Templates — `templates/tenants/`

`subscription/`, `invoice/`, `usage/`, and for 0.19: `entitlementfeature/`, `planentitlement/`,
`usagequota/`, `licenseassignment/` (each with `list` / `detail` / `form.html`), plus two
app-root board pages: `quota_board.html`, `renewal_board.html`.

### Every confirm button comes from one partial

`templates/partials/confirm_button.html` owns the POST form, the `confirm()` dialog, the CSRF token
and the icon button. **Never hand-roll that form** — 0.19 had six copies and they drifted. A test
fails if any 0.19 page contains `method="post"` or `onsubmit=`.

```django
{% url 'tenants:usagequota_delete' obj.pk as delete_url %}
{% include "partials/confirm_button.html" with
    action=delete_url
    confirm_message="Delete this quota? The recorded ceiling is removed; the usage already consumed is not."
    label="Delete" icon="trash-2" variant="danger" %}
```

**The apostrophe trap (L42) — the partial cannot save you.** The message lands inside a JavaScript
single-quoted string. Django escapes a literal `'` to `&#39;`, the browser DECODES IT BACK to a bare
quote, the string ends early, and the dialog silently stops guarding anything. There is no way to
escape this from inside a Django template, so the message must be a **fixed literal with no ASCII
apostrophe and no backslash** — use the typographic `’`. A test enforces this; do not rely on review.

**Icon-only controls need `aria-label`, not just `title`.** `btn-icon` renders only a lucide `<i>`,
so `title` is the accessible name at best. `confirm_button.html` emits both.

## Seeder — `manage.py seed_tenants`

Idempotent and **independently self-healing per entity**: a tenant with features but no quotas still
gets its quotas, rather than the whole 0.19 block being skipped. A second run prints
`0.19 licensing already complete - nothing created` for every tenant. It finishes by printing the
tenant-admin logins and the reminder that the `admin` superuser has no tenant.

## Conventions & gotchas

1. **Every view filters `tenant=request.tenant`.** `request.tenant is None` (the `admin` superuser)
   returns empty by design.
2. **The form is where `tenant` lives, not the instance.** `TenantModelForm.__init__` stores
   `self.tenant`; it never sets `instance.tenant`. `ModelForm._post_clean()` runs
   `instance.full_clean()` during `is_valid()` — **before** the view assigns `obj.tenant` — so
   `self.tenant_id` is still `None` and any `Model.clean()` guard keyed on `self.tenant_id`
   **short-circuits on the form path**. The form's own `clean()` is the only line of defence there.
3. **Consequence of (2):** anything a form must compare against a stored value has to be normalised
   in the FORM too, not only in `Model.save()`. `LicenseAssignmentForm.clean()` lower-cases
   `module_slug` for exactly this reason — omitting it made a duplicate POST of `"ACCOUNTING"` pass
   validation, normalise on save, and raise `IntegrityError` → HTTP 500.
4. **A `ValidationError` keyed on a field the form does not have is a 500**, not a form error —
   Django raises `ValueError` binding it. Always key on a field the form declares.
5. **One-writer fields (L22)** are `editable=False` on the model **and** absent from the form:
   `UsageQuota.breached_at`, and `LicenseAssignment.status` / `reclaimed_on` / `reclaim_reason`.
   The verbs are the sole writers. A status-dependent Edit is additionally blocked **in the view** —
   a hidden button stops nobody.
6. **The six POST-only routes carry `@require_POST` ABOVE `@tenant_admin_required`.** Decorators
   apply bottom-up, so the method check runs first and a wrong method is **405 regardless of role**.
   That is deliberate: the house standard is 405 for a wrong method, not 403.
7. **A foreign row is 404 on GET but 405 on those six POST-only URLs** — the method check fires
   before the tenant filter, which is correct and leaks nothing.

## The ten declined capabilities (say these, never imply them)

0.19 **records** licensing terms; it does not **enforce** them. The pages state this in prose. Do not
write a feature that implies otherwise without doing the work.

1. no entitlement **enforcement** at request time
2. `action_on_breach` is a recorded policy — **nothing acts on it**
3. reclaiming a seat does **not** disable the login
4. no **charging** from 0.19 (Stripe + `SubscriptionInvoice` is the 0.1 billing integration)
5. no identity-provider sync
6. no proration
7. no email delivery
8. no scheduler here — the renewal **run** is **0.20**
9. `module_slug` is a free-text label, not checked against the navigation registry
10. quota percentages are **display only**

`UsageRecord` remains the consumption store and 0.19 adds the **commercial ceiling**; it does not
replace it. `quota_limit == 0` means UNMETERED (mirroring `UsageRecord.included_allowance`, which
calls `None` unmetered and "deliberately distinct from `0`").

## Tests

`apps/tenants/tests/` — 0.1's own lanes plus four 0.19 lanes (`test_licensing_models|forms|views|
security.py`). Every 0.19 test is `test_licensing_*` and every helper `lic019_*`, so the next
sub-module appending nearby cannot shadow them.

**Run with `--no-migrations` while iterating** — the suite drops from minutes to seconds.

**A migration-backed run is affordable now, which it never was.** `pytest.ini` has always carried
`--reuse-db`, and for a long time it was a **silent no-op**: on SQLite Django reads only
`DATABASES["default"]["TEST"]["NAME"]` for the *test* database and ignores `NAME`, so with nothing set
it fell back to shared in-memory — discarded at exit, meaning **every run re-applied all ~270
migrations** (20+ minutes here, long enough that people start killing runs and leaving a partial DB
behind).

```powershell
# fast iteration
pytest apps/tenants/tests -q --no-migrations

# the real thing, paid once and then cached
$env:NAVERP_TEST_DB = "nav_erp_test.sqlite3"
pytest apps/tenants/tests          # slow ONCE
pytest apps/tenants/tests          # seconds from then on
Remove-Item nav_erp_test.sqlite3   # start over
```

Two traps: the knob is **`TEST["NAME"]`**, not `NAME`; and it must be a **bare filename**, not a path,
because Django uses the value verbatim. `root/conftest.py` additionally turns off SQLite durability for
the test DB (`synchronous=OFF`, `journal_mode=MEMORY`), guarded on the engine so it can never reach a
real database.

Always run the **full unfiltered** `apps/tenants/tests` before declaring done (L47 — never `-k`), and
**never kill a run part-way** — that discards the migration work.

The query-count guards assert that the count does not **grow with row count**, not a magic number: a
hard-coded count encodes whatever the page cost on the day it was written, while a per-row query
would still pass a constant-N check on a two-row fixture.

## Sidebar wiring

`LIVE_LINKS["0.1"]` and `LIVE_LINKS["0.19"]` in `apps/core/navigation.py`.

## Common tasks

**Add a field to a 0.19 model** — field + `clean()` guard if it is a rule → form `Meta.fields` (or an
explicit exclusion, with the reason) → `makemigrations` / `migrate` → contract line → the model lane.

**Add a 0.19-style model + CRUD** — model at `apps/tenants/models/<Name>.py` → **add it to the
package `__init__.py` re-export block** (omitting this is an `ImportError` at runtime) → form
inheriting `TenantModelForm` → `crud_list` / `crud_create` / `crud_edit` / `crud_delete` + a direct
`render()` detail → `templates/tenants/<name>/{list,detail,form}.html` → `admin.py` → seeder row →
tests. **Do not** mint a `LIC-` number: check `LITERAL_PREFIX_MODELS` in the numbering registry.

**Extend the seeder** — keep it per-entity self-healing and idempotent; a second run must print
"nothing created".

## Where to look before changing anything

- `apps/tenants/tests/test_licensing_*.py` — the executable spec, including the honesty band that
  asserts on the template FILES (no undefined badge class, no `|safe`, no `{# #}`, no BOM, no
  mojibake). Those regressions are cheap to reintroduce and invisible in review.
- `.claude/tasks/contract-tenants-0.19.md` — the frozen contract; check drift against it.
- `.claude/tasks/review-tenants-0.19.md` — the six review passes, including the three findings that
  were **skipped with a recorded reason** (M3, M4, M6) rather than fixed.

