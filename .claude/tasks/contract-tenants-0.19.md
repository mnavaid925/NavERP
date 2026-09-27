# Build Contract — 0.19 License & Subscription Administration (Module 0, `tenants`)

**Date:** 2026-09-27 · **Phase:** 3, step 1 (spec — read-only) · **Target app:** `apps/tenants` (flat, backend rule 9)
**BASE sha:** `44c7de31` (Phase 4 reviews `44c7de31...HEAD`)
**Migration:** `tenants.0005_*` — `apps/tenants/migrations/` was re-listed at contract time and holds
`0001_initial.py`, `0002_alter_brandingsetting_options.py`,
`0003_alter_subscription_stripe_subscription_id_and_more.py`, `0004_usagerecord.py`.
**Re-list the directory immediately before generating (L43).** If a peer session has added a `tenants`
model and generated its own `0005`, concede the lower number and generate last. Never `--merge`, never
renumber, never delete a peer's migration.
**Inputs:** `.claude/tasks/research-tenants-0.19.md` (committed `44c7de31`) and the
`# Build Plan — Module 0 0.19` block at the top of `.claude/tasks/todo.md` (lines 9-210). This contract
**restates** the plan; the points marked **[RULING]** are the only places this document resolves
something the plan left open or got wrong.

**Dirty tree at session start is NOT mine (L45).** Do not stage, edit or commit anything outside
`apps/tenants/`, `templates/tenants/`, `apps/core/navigation.py` and this task directory. The
untracked `temp/` scratch files, `.commandcode/`, `.gemini/`, `.workbuddy-ai/`, `.zcode/` belong to
other sessions. This spec session wrote exactly one file: `.claude/tasks/contract-tenants-0.19.md`. No
application code was touched, no migration was generated, nothing was pushed.

**Totals: 50 new columns (4 new models × 12/12/12/12 = 48, plus 2 on the existing `Subscription`) ·
24 view functions · 24 route names · 14 template files · 2 computed boards · 2 verbs.**

> Counting rule, so it is reproducible rather than a number nobody can check:
> `len([f for f in M._meta.concrete_fields if not f.primary_key])` per model, plus the 2 columns added
> to `Subscription`. See §0 for the miscounts this corrects.

---

## 0. Verification of the Phase 2 plan against the as-built code (L28)

Every name below was grep-verified in the real source, not read off the plan.

| Plan name / assumption | Verdict |
|---|---|
| `core.Tenant.PLAN_CHOICES` @ `apps/core/models/Tenant.py:20-25` — 4 values, longest `enterprise` (10 chars) | **exists** |
| `accounts.User` @ `apps/accounts/models.py:52`; `tenant` FK is **nullable** (`null=True`) | **exists** |
| `tenants.Subscription` @ `models/Subscription.py:5`; `days_left()` at `:35` | **exists** |
| `tenants.SubscriptionInvoice` @ `models/SubscriptionInvoice.py:5`; the `next_number(..., "SINV")` + retry-on-`IntegrityError` `save()` at `:33-44` | **exists** |
| `tenants.UsageRecord.METRIC_CHOICES` @ `models/UsageRecord.py:31-36`; `_usage_summary()` @ `views/UsageRecord.py:15-47` | **exists** |
| `core.ModuleAccessScope.module_slug` = `CharField(max_length=40)` @ `models/ModuleAccessScope.py:30` | **exists** |
| `write_audit_log(user, obj, action, changes=None, tenant=None)` @ `apps/core/utils.py:6` | **exists** |
| `crud_list(request, qs, template, *, search_fields, filters, extra_context, per_page, …)` @ `apps/core/crud.py:115` | **exists**, signature as assumed |
| `crud_create` / `crud_edit` / `crud_detail` / `crud_delete` @ `crud.py:186 / 215 / 239 / 249` | **exist** — but see **[RULING] 9** on the `tenant=` kwarg |
| `AuditLog.action` = `CharField(max_length=10, choices=[create, update, delete])` @ `models/AuditLog.py:16` | **exists** (L41) |
| FK `tenants.* → accounts.User` is legal | **legal** — `accounts` precedes `tenants` in `INSTALLED_APPS` (`config/settings.py:47-48`), and `inventory.InventoryAlert` already FKs `"accounts.User"` (`apps/inventory/models/AlertsNotifications/InventoryAlerts.py:75`) |
| Migration number `tenants.0005_*` | **free** — directory re-listed, last is `0004_usagerecord.py` |

### [RULING] 1 — the `LIC-` prefix is ALREADY TAKEN. `LicenseAssignment` must mint `SEAT-`.

The plan pins `LicenseAssignment` to prefix `LIC-`. **`scm.TradeLicense` (SCM 4.12 Contract &
Compliance) already declares `NUMBER_PREFIX = "LIC"`** at
`apps/scm/models/ContractCompliance/TradeLicenses.py:55`, and its docstring and `__str__` both narrate
it ("the internal LIC- ``number``", `f"{self.number or 'LIC'} · {self.title}"`). Three concrete
consequences, none hypothetical:

1. **Two registers would mint `LIC-00001` in the same tenant.** `next_number()` is per-**model**
   (`utils.py:58` filters `model.objects.filter(tenant=tenant, number__startswith=...)`), so neither
   would overwrite the other — but an operator reading two unrelated registers sees the same
   customer-facing number, which is precisely the failure `core.NumberingScheme`'s docstring says the
   reconciliation board exists to catch.
2. **`core.NumberingScheme` has `unique_together = ("tenant", "prefix")`** (`models/NumberingScheme.py:36`).
   A tenant cannot configure a numbering scheme for both registers.
3. **`settings_engine.prefix_usage()` keys `model_prefixes` by prefix** (`settings_engine.py:189`), so
   `model_prefixes["LIC"]` would list two models and the 0.10 numbering board would read as one prefix
   serving two unrelated document kinds.

**Ruling: `LicenseAssignment.NUMBER_PREFIX = "SEAT"`**, minting `SEAT-00001`. `SEAT` is free — the
repo-wide `NUMBER_PREFIX` scan (258 distinct prefixes) contains no `SEAT`, no `ENT`, no `PE`, no `UQ`.
Record the reason in the model docstring in one line: *SEAT, not LIC — `LIC` is `scm.TradeLicense`'s
internal number and two registers must not mint the same customer-facing number in one tenant.*
**Do not** "fix" this by editing `TradeLicense` — it is a shipped sub-module with committed tests.

### [RULING] 2 — the `unique_together` does NOT enforce what the plan says, and the test suite cannot catch that.

The plan writes: `unique_together = (tenant, plan, feature, subscription)` *"so a plan-level grant and
an override coexist instead of colliding."* The coexistence half is true — but only because
**`subscription` is NULLABLE and MySQL treats NULLs as distinct inside a unique index**. The identical
semantics hold on SQLite (NULLs are distinct) and therefore on the in-memory test database, so no
test written against this project would ever surface it. The consequence: the constraint **silently
fails to prevent what the plan reads it as preventing** — two plan-level grants for the same
`(tenant, plan, feature)` with `subscription = NULL` are **both accepted**, every time. The register
would hold two conflicting values for one privilege and the board would render both.

**Ruling:** keep the `unique_together` — it is correct and load-bearing for the override case (two
identical overrides *should* collide). **And** add a `clean()` to `PlanEntitlement` raising
`ValidationError` on a duplicate **plan-level** grant (`subscription_id is None`) for an existing
`(tenant, plan, feature)`, so the invariant is enforced at the only place a user can create one. The
database is not asked to do what it cannot do. See [RULING] 8 for the same discipline on the three
non-nullable unique tuples.

### [RULING] 3 — `is_override` must be a `@property`, not a column, because `subscription` is `SET_NULL`.

The plan lists `subscription` (nullable FK, `SET_NULL`) **and** `is_override` as fields. A stored
boolean plus a nullable FK that nulls on delete is a permanently-lying pair: delete the
`Subscription` and `subscription_id` becomes `None` while `is_override` stays `True`, so the register
reports an override that no longer exists and the Chargebee precedence rule is applied to nothing.

**Ruling:** `is_override` is a `@property` returning `self.subscription_id is not None`, and is
**not** a column. The precedence rule ("a subscription-level override PRECEDES the plan grant") is
honoured by the **read order** in `planentitlement_detail` — override row first, plan grant second —
and stated in prose on the page. It is **not** enforced anywhere, because entitlement enforcement is
one of the ten declines (§5.4).

### [RULING] 4 — "seat counts … stay `@property`" is not implementable. Split it.

A count is a queryset aggregate, not a per-instance attribute. A per-row `@property` calling `.count()`
is the exact defect `_usage_summary()`'s docstring names: *"a derived property calling `.filter()`
bypasses any prefetch cache and re-queries per render."*

**Ruling:** `is_reclaimable` **is** a `@property` (a per-row fact, so it is safe). The seat **count**
is computed in the **view**, off one grouped query, and passed as a context key — the
`_usage_summary()` precedent exactly. Never a model property.

### [RULING] 5 — the plan's "sole writer of `status`" contradicts its own exclusion list.

The plan makes `licenseassignment_reclaim` "the only writer of `status`/`reclaimed_on`/
`reclaim_reason`", then excludes only `reclaimed_on` and `reclaim_reason` from the form. A
`LicenseAssignmentForm` that still carries `status` would let a member `POST status=active` and
silently re-activate a revoked or reclaimed seat — undoing the one-writer discipline (L22) the plan
is trying to establish.

**Ruling:** `status` is **excluded** from `LicenseAssignmentForm.Meta.fields` and joins the two
reclaim-owned columns in the exclusion list. A seat is created `active` (the model default) and its
status thereafter changes **only** through the verb. "Expired" is a *displayed* state derived from
`expires_on` on the board, never a stored status the form can write.

### [RULING] 6 — `crud_list` cannot serve a `?flag=yes|no` boolean lens. Use literal `True`/`False`.

`crud_list`'s boolean handling is one dict: `mapped = {"True": True, "False": False}.get(val, val)`
(`crud.py:162`). A dropdown offering `("yes", "Yes")` sends `?flag=yes`, which is not in the map, so it
reaches `.filter(flag="yes")`, raises `ValueError` inside the filter, and is **silently skipped** by
the `except (ValueError, ValidationError)` at `:176` — the dropdown would render, appear selected, and
do nothing. (`usagerecord_list` avoids this by hand-rolling a `?billed=yes|no` lens at
`views/UsageRecord.py:59-61`; do not copy that shape here, because it puts filter logic in the view
that `crud_list` already owns.)

**Ruling:** every boolean lens in 0.19 uses literal option values, and a boolean `*_choices` key is
`[("True", "…"), ("False", "…")]` with the filter declared as `("field", "field", False)`. The
template compares `{% if request.GET.field == "True" %}`.

### [RULING] 7 — there is no `metric` queryset. `UsageQuota.metric` is an enum, not an FK.

The template bullet says the view passes *"the `metric` queryset"*. `UsageQuota.metric` is a
`CharField(choices=UsageRecord.METRIC_CHOICES)` — there is no queryset, and building one would be a
fifth metric list, the exact duplication the research rejects.

**Ruling:** the key is `metric_choices`, assigned the `UsageRecord.METRIC_CHOICES` object **by
identity** (`is`, not a copy — see §1.3), and the dropdown is an enum filter
`("metric", "metric", False)`.

### [RULING] 8 — three models carry a non-nullable `unique_together` with no duplicate guard. That is an HTTP 500, not a form error.

`EntitlementFeature` `(tenant, code)`, `UsageQuota` `(tenant, subscription, metric, period)` and
`LicenseAssignment` `(tenant, user, module_slug)` are all **fully non-nullable**, so the database
*does* enforce them — and a duplicate create/edit POST then raises `IntegrityError` out of
`crud_create`/`crud_edit` (`crud.py:200` / `:224`) as a **500**. That is precisely the defect that
shipped as `review-core-0.15` L5-C1 (create) and L5-C2 (edit). The plan specifies no guard.

**Ruling:** each of those three forms gets a `clean()` that raises a field error on a duplicate of its
own unique tuple, on **both** create and edit. `PlanEntitlement`'s form gets the `clean()` from
[RULING] 2. All four forms therefore turn a duplicate into a re-rendered form, never a 500.

### [RULING] 9 — every form MUST subclass `TenantModelForm`; a plain `ModelForm` raises `TypeError`.

`crud_create` does `form_class(request.POST, request.FILES, tenant=request.tenant, **form_kwargs)`
(`crud.py:195`, `:209`) and `crud_edit` the same at `:222` / `:233`. The `tenant=` kwarg is passed
**unconditionally** — `form_kwargs.pop("tenant", None)` strips it from *your* dict, not from the call.
A plain `forms.ModelForm` therefore dies with
`TypeError: __init__() got an unexpected keyword argument 'tenant'`. The plan already says
`TenantModelForm`; this is a verification, recorded so the build agent does not substitute a plain
`ModelForm`.

**What `TenantModelForm` gives 0.19 for free** (`apps/core/forms/_common.py:25-55`): widget classes per
field type, and **automatic tenant scoping of every `ModelChoiceField`** — but only
`if "tenant" in [f.name for f in model._meta.fields]`. Consequences: the `feature`, `subscription` and
`user` querysets are auto-narrowed on the form; `user`'s is narrowed to `filter(tenant=…)`, which
**automatically excludes the null-tenant superuser**. The **boards and the seat count are not forms**,
so they must filter `user__tenant=request.tenant` themselves (§3.5).

### [RULING] 10 — the plan says "nine declines" and then lists **ten**.

Counting the plan's own list at `todo.md:38-44`: entitlement enforcement · quota
enforcement/throttling · seat auto-deprovisioning · metered event ingestion · proration · prepaid
credit grants · rate cards / tiered / multi-currency pricing · plan versioning & grandfathering ·
automatic renewal execution · expiry email delivery = **10**. The research's "Not built" line is also
10. The word "nine" is a miscount that has already propagated into the research, the plan, and the
`LIVE_LINKS` comment the plan asks for.

**Ruling:** say **"ten declines"** in the nav comment, the module docstring and every page. Carrying
"nine" into shipped prose is the exact confident-prose failure L52 exists to stop. All ten are pinned
verbatim in §5.4 so the pages cannot drift apart.

### [RULING] 11 — §1.4 is WRONG about `LicenseAssignment.notes`; the MODEL gains the column.

Found by the build agent, which reported it rather than building around it (the right call). This
contract contradicts **itself**: §1.4's field table gives `LicenseAssignment` **no `notes` column**,
while §2.4 pins `Meta.fields = [..., "subscription", "notes"]` and §3.5 pins
`search_fields=["module_slug", "notes"]`. That is not cosmetic — a `ModelForm` naming an undeclared
field raises `FieldError: Unknown field(s) (notes)` at **class-definition time**, so every
licenseassignment page would fail at import, and `apply_search` would raise on the list.

**Ruling: the MODEL was the thing that was wrong; the column is added.** Three independent reasons:

1. Both upstream documents list it — `research-tenants-0.19.md:114` and `todo.md:85` both name `notes`
   for `LicenseAssignment`. §1.4 dropped it to keep a tidy **"4 × 12 = 48 columns"** total, and a
   column count is not a schema reason.
2. The other three 0.19 models **all** carry `notes`. A seat register is the row an operator most needs
   to annotate ("this seat is shared with the Acme pilot"), and it would be the only one without it.
3. The alternative — stripping `notes` from the form and the search — makes §2.4 and §3.5 wrong instead,
   and silently drops a field two upstream documents asked for.

**Consequence:** `LicenseAssignment` is **13 declared fields (14 concrete, with `id`)**, not 12, and the
"4 × 12 = 48" total becomes **49 declared columns + 4 implicit `id`s**. The `status` / `reclaimed_on` /
`reclaim_reason` exclusions are unaffected — those are separate columns with separate reasons. **This
ruling is binding on the migration, the tests and the review.**

### Checked and CLEARED (do not re-litigate)

- **`max_length` vs the longest CHOICES value** — the `fields.E009` class of bug that blocked 0.18's
  build. Longest value per field vs the pinned `max_length`: `privilege_type` 7/12 ·
  `EntitlementFeature.status` 8/10 · `plan` 10/20 · `action_on_breach` 6/10 · `period` 7/10 (values
  `monthly`=7) · `metric` 12/20 · `LicenseAssignment.status` 9/12 · `assignment_source` 6/10.
  **Every field is wider than its longest choice.** `manage.py check` re-runs the E009 check and passes.
- **MySQL 30-char index-name limit** — every index name pinned in §1 is ≤ 27 chars
  (`entfeat_tenant_status_idx` 25, `entfeat_tenant_code_idx` 24, `planent_tenant_plan_idx` 23,
  `planent_tenant_feature_idx` 26, `uquota_tenant_sub_idx` 21, `uquota_sub_metric_idx` 21,
  `licassign_tenant_status_idx` 27, `licassign_user_idx` 18, `licassign_sub_idx` 17) and every one is
  unique **app-wide** (the `tenants` app currently owns only `usage_tenant_metric_idx`,
  `usage_tenant_billed_idx`, `subinv_tenant_status_idx`, `subinv_stripe_inv_idx`, and the
  `HealthMetric` index). Django's own check catches an over-long name at `makemigrations` time.
- **`UsageQuota.metric` reuse is by IDENTITY, not a rebuilt copy.** `METRIC_CHOICES = UsageRecord.METRIC_CHOICES`
  is a module-level alias and the class re-exposes it, exactly as `AlertRule` re-exposes
  `SEVERITY_CHOICES` (the 0.18 pattern). A pasted copy is the defect; the tests assert `is`.
- **`LicenseAssignment`'s unique tuple excludes the nullable FK.** The natural instinct is
  `(tenant, user, module_slug, subscription)`. `subscription` is `SET_NULL`, so [RULING] 2 applies and
  the constraint would not bite. The seat's business rule is *"this user holds this module's seat in
  this workspace, once"*; `subscription` is the **billing** link, not part of seat identity. The pinned
  tuple is `(tenant, user, module_slug)` — all non-null, genuinely enforced.

---

## 1. Model contract — four new flat files under `apps/tenants/models/`

**File layout (backend rule 9 — `tenants` is a foundation app with no NavERP sub-modules, so the
entity files sit FLAT at the package root, never a `<SubModule>/` folder):**
`models/EntitlementFeature.py` · `models/PlanEntitlement.py` · `models/UsageQuota.py` ·
`models/LicenseAssignment.py`. Each does `from apps.tenants.models._base import *  # noqa: F401,F403`
(the verified foundation pattern) and declares its own `*_CHOICES` at module level.

**Module docstring (binding, and it is the honesty anchor for the whole sub-module).** Each file's
docstring states the posture in the house voice — *a row here is a commercial term somebody wrote
down, not a control that ran.* It must record: **ten** capabilities that are DECLINED (§5.4); the
three ownership rulings — 0.19 owns the **commercial** limit, `core.IpAccessRule` (0.18) owns the
**abuse** bound, `core.AlertRule` (0.17) owns operational thresholds, so `UsageQuota` must never be
presented as an anti-abuse control; and that `EntitlementFeature` is **deliberately NOT** FK'd to
`core.FeatureFlag` (that is a runtime on/off switch with `applies_to_plan`/`exempt_roles`; this is the
commercial catalog a plan grants — reusing it would merge two different facts).

**Import order inside each file is binding** where a new model FKs another new model:
`EntitlementFeature` → `PlanEntitlement` (FK `feature`) → `UsageQuota` → `LicenseAssignment`.
Django resolves FKs by string, so the order is a readability contract, not a load-order constraint —
but `models/__init__.py` must import them in that order too so the re-export block reads the same way.

**The `number` minting pattern (identical for all four, on the `SubscriptionInvoice` precedent at
`models/SubscriptionInvoice.py:33-44`, which is the only non-`TenantNumbered` model in the repo that
mints its own number):**

```python
def save(self, *args, **kwargs):
    if self.number:
        return super().save(*args, **kwargs)
    for _ in range(5):
        self.number = next_number(<ModelClass>, self.tenant, "<PREFIX>")
        try:
            with transaction.atomic():
                return super().save(*args, **kwargs)
        except IntegrityError:
            self.number = ""
    return super().save(*args, **kwargs)
```

`next_number` arrives free through `from apps.tenants.models._base import *` (`_base.py:16` imports it,
alongside `models`, `transaction`, `IntegrityError`, `timezone`, `secrets`, `hashlib`, `Tenant`).
**Prefixes are pinned and collision-checked against all 258 `NUMBER_PREFIX` values in the repo:**
`ENT-` (EntitlementFeature) · `PE-` (PlanEntitlement) · `UQ-` (UsageQuota) · **`SEAT-`**
(LicenseAssignment — see [RULING] 1; **not** `LIC-`).

Because these four mint a prefix through their **own `save()` with a hardcoded literal** rather than
declaring `NUMBER_PREFIX` on a `TenantNumbered` subclass, they are **invisible** to
`settings_engine.prefix_usage()`'s `NUMBER_PREFIX` scan. That scan has exactly one such blind spot and
it is a named constant — `settings_engine.LITERAL_PREFIX_MODELS` (`settings_engine.py:159-161`),
currently `{"SINV": ["tenants.SubscriptionInvoice"]}`. **Adding the four new entries is part of 0.19's
wire-up, not optional**: without it the 0.10 numbering board reports every new prefix as
`model_only` ("minted with no scheme behind it") and never lists which models mint it. The edit is
**append-only into that dict** and the file is shared with 0.10/0.13 — re-read immediately before
editing (L43).

### 1.1 `EntitlementFeature` — *the commercial feature catalog a plan can grant* — **12 fields**

| # | Field | Definition |
|---|---|---|
| 1 | `tenant` | `FK("core.Tenant", CASCADE, related_name="entitlement_features", db_index=True)` |
| 2 | `number` | `CharField(max_length=20, editable=False)` — `ENT-#####`, minted in `save()` |
| 3 | `code` | `CharField(max_length=60, db_index=True)` — the stable key a grant references |
| 4 | `name` | `CharField(max_length=150)` |
| 5 | `description` | `TextField(blank=True)` |
| 6 | `privilege_type` | `CharField(max_length=12, choices=PRIVILEGE_TYPE_CHOICES, default="boolean")` — **typed privileges** (Lago `value_type`, OpenMeter Metered/Static/Boolean): the survey's most reusable idea |
| 7 | `select_options` | `TextField(blank=True)` — a newline- or comma-separated option list, meaningful **only** when `privilege_type == "select"`; a `clean()` requires it non-blank in that case |
| 8 | `status` | `CharField(max_length=10, choices=STATUS_CHOICES, default="draft")` — **archival, not deletion**, so retiring a feature cannot rewrite what past subscriptions were entitled to |
| 9 | `is_add_on` | `BooleanField(default=False)` — *add-ons* (Lago fixed charges, Chargebee addons) |
| 10 | `is_active` | `BooleanField(default=True)` |
| 11 | `notes` | `TextField(blank=True)` |
| 12 | `created_at` | `DateTimeField(auto_now_add=True)` |

**CHOICES (exact literals).** `PRIVILEGE_TYPE_CHOICES = [("boolean", "Boolean"), ("integer", "Integer"),
("select", "Select")]`. `STATUS_CHOICES = [("draft", "Draft"), ("active", "Active"), ("archived",
"Archived")]`.

**Meta (exact).**
```python
class Meta:
    ordering = ["code"]
    unique_together = (("tenant", "code"),)
    indexes = [
        models.Index(fields=["tenant", "status"], name="entfeat_tenant_status_idx"),
        models.Index(fields=["tenant", "code"], name="entfeat_tenant_code_idx"),
    ]
```

**`__str__`** returns `f"{self.code} · {self.name}"` — the code is what a grant references, so a
stray `ENT-00001 · …` in an audit row is useless and this is not.

**`clean()` (two rules, both cheap and both real):** (a) `select_options` required iff
`privilege_type == "select"`; (b) a `code` must be lowercase-and-underscored
(`^[a-z][a-z0-9_]{1,58}$`) — a code is referenced by grants and by a future config, and
`"SSO"` vs `"sso"` becoming two features is the duplication 0.19 exists to prevent. **Do not** make
this a DB constraint or a custom manager; `clean()` is where this repo puts that class of rule
(`ModuleAccessScope.clean`, `UsageRecord.clean`).

**Deliberately NOT FK'd to `core.FeatureFlag`.** `FeatureFlag` (`key`, `label`, `is_enabled`,
`applies_to_plan`, `exempt_roles`) is a *runtime on/off switch*; this is the *commercial catalog a plan
grants*. Two different facts, two tables, and the nav comment says so.

### 1.2 `PlanEntitlement` — *a privilege granted at a plan, or overridden at one subscription* — **12 fields**

| # | Field | Definition |
|---|---|---|
| 1 | `tenant` | `FK("core.Tenant", CASCADE, related_name="plan_entitlements", db_index=True)` |
| 2 | `number` | `CharField(max_length=20, editable=False)` — `PE-#####`, minted in `save()` |
| 3 | `plan` | `CharField(max_length=20, choices=PLAN_CHOICES, default="starter")` |
| 4 | `feature` | `FK("tenants.EntitlementFeature", CASCADE, related_name="plan_entitlements")` |
| 5 | `privilege_value` | `CharField(max_length=120, blank=True)` — holds `true` / `10` / `okta`; a **char**, not typed columns, because one column must serve all three privilege types |
| 6 | `is_add_on` | `BooleanField(default=False)` |
| 7 | `subscription` | `FK("tenants.Subscription", SET_NULL, null=True, blank=True, related_name="entitlement_overrides")` — **nullable**: `NULL` = the plan-level grant; set = the subscription-level **override** |
| 8 | `effective_from` | `DateField(null=True, blank=True)` |
| 9 | `effective_to` | `DateField(null=True, blank=True)` — Chargebee's *Forever* vs *Until &lt;date&gt;* |
| 10 | `is_enabled` | `BooleanField(default=True)` |
| 11 | `notes` | `TextField(blank=True)` |
| 12 | `created_at` | `DateTimeField(auto_now_add=True)` |

**CHOICES.** `PLAN_CHOICES = Tenant.PLAN_CHOICES` — **by reference** (L36: assign the object, never
rebuild the tuple), reaching `Tenant` through `_base`'s existing `from apps.core.models import Tenant`
(`models/_base.py:15`). The class re-exposes it exactly as `Subscription` does
(`PLAN_CHOICES = Tenant.PLAN_CHOICES`, `Subscription.py:6`). **No `PlanTier` table** — Zuora-scale and
out of scope; the four-value vocabulary already exists.

**`is_override` is NOT a column** — it is `@property: return self.subscription_id is not None`, per
[RULING] 3.

**Meta (exact).**
```python
class Meta:
    ordering = ["plan", "feature__code", "-id"]
    unique_together = (("tenant", "plan", "feature", "subscription"),)
    indexes = [
        models.Index(fields=["tenant", "plan"], name="planent_tenant_plan_idx"),
        models.Index(fields=["tenant", "feature"], name="planent_tenant_feature_idx"),
    ]
```

**`clean()` — three rules.** (a) The [RULING] 2 duplicate-plan-grant guard: if `subscription_id is
None` and another `PlanEntitlement` exists for the same `(tenant, plan, feature)`, raise on
`subscription`. (b) `effective_to < effective_from` raises on `effective_to` (the `UsageRecord.clean`
precedent). (c) `privilege_value` must parse against the feature's `privilege_type` when set —
`boolean` ⇒ in `{"true", "false"}`; `integer` ⇒ `int()`-parseable; `select` ⇒ the value is one of
`feature.select_options`. Rule (c) is what makes a *typed* privilege typed; without it `privilege_type`
is a label and the board's "granted: `banana` for an integer privilege" is shippable.

**`__str__`** returns `f"{self.plan}: {self.feature.code} = {self.privilege_value or '—'}"`.

### 1.3 `UsageQuota` — *the commercial ceiling somebody wrote down* — **12 fields**

| # | Field | Definition |
|---|---|---|
| 1 | `tenant` | `FK("core.Tenant", CASCADE, related_name="usage_quotas", db_index=True)` |
| 2 | `number` | `CharField(max_length=20, editable=False)` — `UQ-#####`, minted in `save()` |
| 3 | `subscription` | `FK("tenants.Subscription", CASCADE, related_name="usage_quotas")` — **not** nullable: a ceiling with no subscription has nothing to bound, and unlike `UsageRecord.subscription` (nullable so a row can pre-date a subscription) a quota is authored *for* one |
| 4 | `metric` | `CharField(max_length=20, choices=METRIC_CHOICES)` — **the same object** as `UsageRecord.METRIC_CHOICES` |
| 5 | `quota_limit` | `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))])` — **`0` means unmetered, NOT zero allowed**: see the note below |
| 6 | `warn_at_pct` | `PositiveIntegerField(default=80, validators=[MinValueValidator(1), MaxValueValidator(100)])` |
| 7 | `action_on_breach` | `CharField(max_length=10, choices=ACTION_CHOICES, default="alert")` — **a recorded policy with no interceptor** |
| 8 | `is_fair_use` | `BooleanField(default=False)` — *fair-use limits* |
| 9 | `period` | `CharField(max_length=10, choices=PERIOD_CHOICES, default="monthly")` |
| 10 | `breached_at` | `DateTimeField(null=True, blank=True, editable=False)` — **evidence stamp, sole writer is the `usagequota_mark_breached` verb** (the `UsageRecord.is_billed`/`billed_at` precedent, L22) |
| 11 | `notes` | `TextField(blank=True)` |
| 12 | `created_at` | `DateTimeField(auto_now_add=True)` |

**CHOICES (exact literals).**
`METRIC_CHOICES = UsageRecord.METRIC_CHOICES` — a **module-level alias assigned by reference**, and
the class re-exposes it (`METRIC_CHOICES = METRIC_CHOICES`), the 0.18 `SEVERITY_CHOICES` pattern
exactly. A pasted copy is the defect; the tests assert `UsageQuota.METRIC_CHOICES is
UsageRecord.METRIC_CHOICES`.
`ACTION_CHOICES = [("alert", "Alert"), ("charge", "Charge"), ("block", "Block")]`.
`PERIOD_CHOICES = [("monthly", "Monthly"), ("yearly", "Yearly")]` — the same two values as
`Subscription.BILLING_CHOICES`, pinned as a local literal rather than an alias because a quota's reset
window need not equal the subscription's billing cycle, and aliasing them would make that
unexpressible.

**`quota_limit = 0` means UNMETERED, not "zero permitted".** This is the one place a build agent will
get it wrong. `UsageRecord.included_allowance` (`models/UsageRecord.py:72-82`) returns `None` for an
unmetered plan and its docstring says so explicitly: *"`None` means UNMETERED … deliberately distinct
from `0`, which would make every unit an overage."* The quota board applies the identical
distinction: a `UsageQuota` with `quota_limit == 0` renders **"Unmetered"** with no percentage and no
breach state, and is **excluded from the `warned`/`breached` counts**. Write that rule in the model
docstring, in the board helper's docstring, and on the board page.

**Meta (exact).**
```python
class Meta:
    ordering = ["subscription", "metric", "period"]
    unique_together = (("tenant", "subscription", "metric", "period"),)
    indexes = [
        models.Index(fields=["tenant", "subscription"], name="uquota_tenant_sub_idx"),
        models.Index(fields=["subscription", "metric"], name="uquota_sub_metric_idx"),
    ]
```

**`clean()` — one rule:** the [RULING] 8 duplicate guard on
`(tenant, subscription, metric, period)`. No cross-field rule: `quota_limit` and `warn_at_pct` are
independent.

**`__str__`** returns `f"{self.get_metric_display()} quota for {self.subscription}"`.

**Board join (binding):** the quota board joins on the **same `subscription`** as
`UsageRecord.subscription`, because `UsageRecord` is the consumption half and `UsageQuota` is the
ceiling half. If the two ever join on anything else the pages disagree, and a "98% of quota" that is
98% of *last year's* subscription is exactly the L52 lie.

### 1.4 `LicenseAssignment` — *one seat, held by one person, for one module* — **12 fields**

| # | Field | Definition |
|---|---|---|
| 1 | `tenant` | `FK("core.Tenant", CASCADE, related_name="license_assignments", db_index=True)` |
| 2 | `number` | `CharField(max_length=20, editable=False)` — **`SEAT-#####`**, minted in `save()` ([RULING] 1) |
| 3 | `user` | `FK("accounts.User", CASCADE, related_name="license_assignments")` — **not** nullable: a seat with no holder is not a seat |
| 4 | `module_slug` | `CharField(max_length=40, blank=True)` — **a char, not an FK**: no module master exists in this repo. `max_length=40` matches the verified `core.ModuleAccessScope.module_slug` **exactly**, so the two registries read consistently; blank = tenant-wide |
| 5 | `status` | `CharField(max_length=12, choices=STATUS_CHOICES, default="active")` — **off the form** ([RULING] 5); sole writer is the `licenseassignment_reclaim` verb |
| 6 | `assignment_source` | `CharField(max_length=10, choices=SOURCE_CHOICES, default="direct")` |
| 7 | `assigned_from` | `DateField(null=True, blank=True)` |
| 8 | `expires_on` | `DateField(null=True, blank=True)` — drives the **displayed** expired state, never a stored status |
| 9 | `reclaimed_on` | `DateTimeField(null=True, blank=True, editable=False)` — **evidence stamp**, sole writer is the verb (L22) |
| 10 | `reclaim_reason` | `CharField(max_length=200, blank=True, editable=False)` — *reclamation*, and the verb's audit trail |
| 11 | `subscription` | `FK("tenants.Subscription", SET_NULL, null=True, blank=True, related_name="license_assignments")` — the **billing** link; `SET_NULL` so deleting a subscription does not delete a person's seat history |
| 12 | `created_at` | `DateTimeField(auto_now_add=True)` |

**CHOICES (exact literals).** `STATUS_CHOICES = [("active", "Active"), ("reclaimed", "Reclaimed"),
("revoked", "Revoked"), ("expired", "Expired")]`.
`SOURCE_CHOICES = [("direct", "Direct"), ("group", "Group"), ("rule", "Rule")]`. The docstring says
**plainly that nothing in NavERP chooses `assignment_source` automatically** — there is no directory
sync, no group engine, no rule evaluator — so `"direct"` is the only value a view or the seeder may
ever write, and `group`/`rule` are vocabulary somebody can record by hand. This is the
`IpAccessRule.source` 0.18 precedent: a source field nobody sets is fine, a source field silently set
by nothing is a lie about provenance.

**`user` and the null-tenant superuser (binding).** `accounts.User.tenant` is **nullable** — the
superuser `admin` has `tenant=None` by design. Three consequences, each one a place the count would
otherwise be a lie:
* `TenantModelForm` auto-scopes the `user` field's queryset to `filter(tenant=…)`, so the **form**
  cannot offer the superuser ([RULING] 9).
* The **seat count** on the board is `LicenseAssignment.objects.filter(tenant=…, status="active",
  user__tenant=request.tenant).count()` — the extra `user__tenant` clause is **required**, because
  the board reads the model, not the form.
* If a row ever lands with a null-tenant user, the count and the register total disagree by one and
  the page is self-contradicting. The seeder must only ever seat users whose `tenant` is the seeded
  tenant.

**`is_reclaimable` — `@property` only** ([RULING] 4): `return self.status == "active"`. It is a
per-row fact, so a property is correct and cheap. **The seat COUNT is not a property**; it is computed
in the view (§3.7).

**`is_expired` — `@property`:** `return bool(self.expires_on and self.expires_on <
timezone.localdate())`. A **displayed** state, per [RULING] 5 — nothing ever writes `status="expired"`.

**Meta (exact).**
```python
class Meta:
    ordering = ["-assigned_from", "-id"]
    unique_together = (("tenant", "user", "module_slug"),)
    indexes = [
        models.Index(fields=["tenant", "status"], name="licassign_tenant_status_idx"),
        models.Index(fields=["tenant", "user"], name="licassign_user_idx"),
        models.Index(fields=["tenant", "subscription"], name="licassign_sub_idx"),
    ]
```

Note the unique tuple has **three** members, not four — see [RULING] 2 and the "Checked and CLEARED"
list: `subscription` is nullable, so including it would make the constraint inert, and it is the
billing link rather than part of seat identity.

**`clean()` — one rule:** the [RULING] 8 duplicate guard on `(tenant, user, module_slug)`. Note the
seeder and the form both pass `module_slug=""` for a tenant-wide seat, and `""` is a *value* here
(never `NULL`), so two tenant-wide seats for one user do collide correctly.

**`__str__`** returns
`f"{self.user} · {self.module_slug or 'all modules'} ({self.get_status_display()})"`.

### 1.5 The column pair on the EXISTING `Subscription` — **+2 columns, surgical**

`models/Subscription.py` is **shared with 0.1 and is an append-only target** (L43: re-read the file
immediately before editing; never full-rewrite it; a peer session may be in it). **No new model** — a
renewal commitment is a property of the subscription, and a table for two fields is over-modelling.

| # | Field | Definition |
|---|---|---|
| +1 | `auto_renew` | `BooleanField(default=True)` — the **recorded** intent, with no scheduler behind it |
| +2 | `grace_ends_on` | `DateField(null=True, blank=True)` — the grace window, **recorded**; the renewal board computes from it |

**Placement:** both go immediately after `renews_on` (line 23) and **before** the Stripe linkage
block, so the commercial dates stay together and the webhook-owned block stays last. That placement is
what makes the diff reviewable as "0.19 added two columns" rather than "0.1's model moved".

**Both are editable and BOTH are on `SubscriptionForm`** (§2.5) — unlike 0.1's
`stripe_customer_id` / `stripe_subscription_id`, which are the webhook's and stay off every form.
`auto_renew` is a *commercial term an operator negotiates*, and the honest way to record "we will not
auto-renew" is for an operator to be able to say so. The page states that **nothing in NavERP reads
this flag**: no scheduler exists (0.20 owns it), no renewal is executed, no card is charged.

**Existing field NOT touched:** `Subscription` has no `number` field and none is added. It is not a
`TenantNumbered` and does not become one in 0.19 — 0.1 keyed it on `(tenant, plan, status)`, and
retro-fitting a number would rewrite existing rows' identity for no gain.

---

## 2. Form contract — four new forms + one surgical edit

**Base class (binding):** every form is a `TenantModelForm` from `apps/tenants/forms/_common.py`
(re-exported from `apps.core.forms`), per [RULING] 9. A plain `ModelForm` raises `TypeError` inside
`crud_create`/`crud_edit`. Each form file does
`from apps.tenants.forms._common import *  # noqa: F401,F403` then
`from apps.tenants.models import (…Model,)` — absolute imports, never a relative `from .models import`
(rule 4: a relative import resolves to the wrong package one level deeper).

**No `tenant` field on any `Meta.fields`.** `crud_create` sets `obj.tenant = request.tenant` itself
(`crud.py:198-199`) and `TenantModelForm` scopes the FK querysets, so listing `tenant` would be a
user-editable tenant switch — the one field that must never be form-writable.

**No `number` on any `Meta.fields`.** `number` is `editable=False` on all four models, which keeps it
off every `ModelForm` **structurally** rather than through a field list somebody has to remember
(the `TenantNumbered.number` rationale, `apps/sales/models/_base.py:26`). The exclusion is therefore
belt-and-braces; say so in each docstring rather than implying a list is load-bearing.

### 2.1 `EntitlementFeatureForm`
`Meta.fields = ["code", "name", "description", "privilege_type", "select_options", "status",
"is_add_on", "is_active", "notes"]`

**Excluded:** `number` (`editable=False`, minted in `save()`); `tenant` (set by the view).
**`clean()`:** the [RULING] 8 duplicate-`code` guard on `(tenant, code)`, excluding self on edit.
**Do not** re-implement the model's `select_options` / code-format rules here — `ModelForm._post_clean()`
already calls `instance.full_clean()`, and a second copy would drift.

### 2.2 `PlanEntitlementForm`
`Meta.fields = ["plan", "feature", "privilege_value", "is_add_on", "subscription", "effective_from",
"effective_to", "is_enabled", "notes"]`

**Excluded:** `number` (`editable=False`); `tenant` (set by the view).
**`subscription` STAYS on the form** — the whole point of the model is that an operator records an
override, and a form that could not set it would make `is_override` permanently `False`. It is
nullable, so the form's "no override" case is the empty choice.
**`clean()`:** the [RULING] 2 duplicate-plan-grant guard. Note the model's privilege-value type check
(§1.2c) is enforced automatically by `full_clean()`; do not duplicate it.

### 2.3 `UsageQuotaForm`
`Meta.fields = ["subscription", "metric", "quota_limit", "warn_at_pct", "action_on_breach",
"is_fair_use", "period", "notes"]`

**Excluded — and this is the plan's own point, stated as evidence:** `breached_at` is an **evidence
stamp**, `editable=False`, whose **sole writer is the `usagequota_mark_breached` verb**. The
`UsageRecordForm` docstring (`forms/UsageRecord.py:9-12`) states the consequence in the house voice and
it is reproduced here in spirit: *a form that could set it would let a member declare their own quota
breached without a single unit being consumed.* The breach is what an operator later reads as
evidence; it must be stamped by the act, not typed by hand.
**Also excluded:** `number` (`editable=False`); `tenant` (set by the view).
**`clean()`:** the [RULING] 8 duplicate guard on `(tenant, subscription, metric, period)`.

### 2.4 `LicenseAssignmentForm`
`Meta.fields = ["user", "module_slug", "assignment_source", "assigned_from", "expires_on",
"subscription", "notes"]`

**Excluded, with the reason for each:**

| Excluded | Why |
|---|---|
| `status` | **Sole writer is the `licenseassignment_reclaim` verb** ([RULING] 5). A form carrying it would let a member `POST status=active` and silently re-activate a revoked seat. |
| `reclaimed_on` | Evidence stamp, `editable=False`, written only by the verb (L22 — no system stamp is user-editable). |
| `reclaim_reason` | Same: the reason belongs to the act of reclamation, which is the verb. A free-text reason typed into a form is a claim, not a record. |
| `number` | `editable=False`, minted in `save()`. |
| `tenant` | Set by the view. |

**`clean()`:** the [RULING] 8 duplicate guard on `(tenant, user, module_slug)` — and it is reachable
by an ordinary user, because `module_slug` and `user` are both on this form.

### 2.5 `SubscriptionForm` — **surgical edit, append two names to `Meta.fields`**
`forms/Subscription.py:11` becomes
`fields = ["plan", "status", "billing_cycle", "amount", "seats", "started_on", "renews_on", "auto_renew", "grace_ends_on"]`

`auto_renew` and `grace_ends_on` are **not** evidence stamps — they are negotiated commercial terms an
operator sets by hand — so unlike `UsageQuota.breached_at` they belong on the form. This file is
shared with 0.1: **re-read immediately before editing and change nothing else** (L43).

---

## 3. View contract — 24 functions, 5 flat files, every context key pinned

**Files:** `views/EntitlementFeature.py` · `views/PlanEntitlement.py` · `views/UsageQuota.py` ·
`views/LicenseAssignment.py` · `views/Boards.py` (the two computed boards; one file because they are
two functions and neither has a model — the 0.17/0.18 board precedent). Each starts with
`from apps.tenants.views._common import *  # noqa: F401,F403`, which already brings in `crud_list`,
`crud_create`, `crud_edit`, `crud_detail`, `crud_delete`, `get_object_or_404`, `redirect`, `render`,
`messages`, `timezone`, `Decimal`, `transaction`, `reverse`, `require_POST`, `tenant_admin_required`
and `write_audit_log` (`views/_common.py:10-25`). **Never re-import those from `apps.core` in an entity
module** — a second import path is how a decorator order drifts.

**Decorator rule, absolute:** every one of the 24 functions is `@tenant_admin_required`. The **two
destructive verbs** and the **four delete views** carry `@require_POST` **ABOVE** the role gate:

```python
@require_POST          # outermost — runs first
@tenant_admin_required # inner
def licenseassignment_reclaim(request, pk):
```

Decorators apply bottom-up, so the outermost runs first. With the role gate outermost, a non-admin
member's `GET` would be answered **403 by the role check before the method check ever ran**; the house
standard (7.7's ruling) is **405 for a wrong method regardless of role**. The `usagerecord_delete`
docstring (`views/UsageRecord.py:109-115`) states this and names the trap explicitly: *the older
tenants verbs (`encryptionkey_rotate`, `subscription_mark_paid`) still carry the pre-7.7 order — this
one does not copy it.* **0.19 copies neither.** Do not "fix" the two old 0.1 verbs in passing; they are
0.1's and outside this sub-module's diff.

**Every queryset is `filter(tenant=request.tenant)`.** No exceptions, and never
`Model.objects.all()`.

**The `crud_list` junk-param gate is already satisfied — do not re-implement it** (0.18 [RULING] 4).
`crud.py:134-179` skips a junk enum via `_enum_values`, a non-pk or over-range int via `as_db_int`,
`?pk=0` via `_is_pk_lookup`, and a `ValidationError` raised inside `.filter()`. So `?status=nope` and
`?metric=not_a_metric` are already ignored. The gate asserts the **unfiltered row count**, not merely
a 200. The views must **not** add their own parsing.

### 3.1 The context-var contract (pinned, L7/L8)

| View kind | Keys the helper supplies | Keys the view adds |
|---|---|---|
| `*_list` | `object_list`, `page_obj`, `q` (`crud.py:181`) | the entity's `*_choices` / FK querysets / board rows, per §3.2-§3.5 |
| `*_create` | `form`, `is_edit=False` (`crud.py:210`) | nothing needed |
| `*_detail` | `obj` (`crud.py:244`) | the entity's related rows, per §3.2-§3.5 |
| `*_edit` | `form`, `obj`, `is_edit=True` (`crud.py:234`) | nothing needed |
| boards | *(no helper — `render()` directly)* | the full pinned key list, per §3.7 |

`object_list` (not the plural model name) and `obj` (not `entitlementfeature_obj`) are **the repo-wide
convention** and every existing `tenants` template already depends on it. A name left unpinned is a
silently blank region (L8) or a `NoReverseMatch` on `{% url … obj.pk %}` (L7).

### 3.2 `views/EntitlementFeature.py` — 5 functions

```python
@tenant_admin_required
def entitlementfeature_list(request):
    qs = EntitlementFeature.objects.filter(tenant=request.tenant)
    return crud_list(
        request, qs, "tenants/entitlementfeature/list.html",
        search_fields=["code", "name", "description"],
        filters=[("status", "status", False),
                 ("privilege_type", "privilege_type", False),
                 ("addon", "is_add_on", False)],
        extra_context={
            "status_choices": EntitlementFeature.STATUS_CHOICES,
            "privilege_type_choices": EntitlementFeature.PRIVILEGE_TYPE_CHOICES,
            "addon_choices": [("True", "Add-on"), ("False", "Included")],
        },
    )
```

**Every `extra_context` key backs a real dropdown** — the 0.18 [RULING] 3 discipline, in both
directions: no key with no dropdown behind it, and no dropdown with no key. The boolean `addon_choices`
is literal `True`/`False` per [RULING] 6, and the template tests
`{% if request.GET.addon == "True" %}`.

`entitlementfeature_create` → `crud_create(request, form_class=EntitlementFeatureForm,
template="tenants/entitlementfeature/form.html", success_url="tenants:entitlementfeature_list")`.

`entitlementfeature_detail(request, pk)` → `crud_detail(request, model=EntitlementFeature, pk=pk,
template="tenants/entitlementfeature/detail.html", extra_context={"entitlements": …})` where
`entitlements` is `obj.plan_entitlements.select_related("subscription").order_by("plan", "feature__code")[:50]`
— **capped at 50**, the `subscription_detail` embedded-list precedent (`views/Subscription.py:37`,
*"cap embedded list"*). Without the cap a feature granted on every plan across many subscriptions
renders an unbounded page.

`entitlementfeature_edit` → `crud_edit(request, model=EntitlementFeature, pk=pk,
form_class=EntitlementFeatureForm, template="tenants/entitlementfeature/form.html",
success_url="tenants:entitlementfeature_list")`.

`entitlementfeature_delete` → `@require_POST` above `@tenant_admin_required`, then
`crud_delete(request, model=EntitlementFeature, pk=pk, success_url="tenants:entitlementfeature_list")`.
**No guard beyond the helper.** The `usagerecord_delete` billed-row guard is deliberately *not*
copied: an `EntitlementFeature` is a catalog row whose grants cascade, and freezing it would mean a
mistyped code could never be corrected. `status="archived"` is the retirement path, and the list
template's delete button must say so.

### 3.3 `views/PlanEntitlement.py` — 5 functions

```python
@tenant_admin_required
def planentitlement_list(request):
    qs = (PlanEntitlement.objects.filter(tenant=request.tenant)
          .select_related("feature", "subscription"))
    return crud_list(
        request, qs, "tenants/planentitlement/list.html",
        search_fields=["privilege_value", "notes"],
        filters=[("plan", "plan", False),
                 ("feature", "feature_id", True),
                 ("enabled", "is_enabled", False),
                 ("addon", "is_add_on", False)],
        extra_context={
            "plan_choices": PlanEntitlement.PLAN_CHOICES,
            "feature_choices": EntitlementFeature.objects
                                   .filter(tenant=request.tenant).order_by("code"),
            "enabled_choices": [("True", "Enabled"), ("False", "Disabled")],
            "addon_choices": [("True", "Add-on"), ("False", "Included")],
        },
    )
```

**`feature_choices` is a QUERYSET, and the template's pk comparison must use
`{% if request.GET.feature == f.pk|stringformat:"d" %}selected{% endif %}` — NEVER `|slugify`** (the
workspace's Filter Implementation Rules; a pk is not a slug, and the rule exists because it has
already broken once). The filter is declared `("feature", "feature_id", True)` — `is_int=True` routes
it through `as_db_int`, so `?feature=abc` and `?feature=0` are both skipped rather than silently
emptying the register (L11). Note `_is_pk_lookup("feature_id")` is `True` (it ends with `_id`), so the
`?feature=0` zero-guard applies.

`planentitlement_create` → `crud_create(…, form_class=PlanEntitlementForm, template=
"tenants/planentitlement/form.html", success_url="tenants:planentitlement_list")`.

`planentitlement_detail(request, pk)` → `crud_detail(…, extra_context={…})` with:
`"plan_grants"` = the same-feature plan-level rows (`subscription__isnull=True`, `.order_by("plan")[:50]`),
`"overrides"` = the same-feature subscription-level rows (`.order_by("subscription_id")[:50]`), and
`"overridden_features"` = a **single** dict of `feature_id → plan-grant value` built in the view. All
three capped at 50.

**`overridden_features` is a real derived value, not a tautology, and it is what makes [RULING] 3's
read-order rule visible.** It is a dict comprehension over the already-fetched `plan_grants` list —
never a per-row `.filter()`, which re-queries per render (the `_usage_summary` docstring, verbatim).
The template renders it as a table: *Feature · Plan grants · This subscription's override*. **The page
must say in prose that the override is shown first because it takes precedence in how a human reads
this page — and that nothing in NavERP enforces that precedence at request time**, because entitlement
enforcement is decline #1.

`planentitlement_edit` → `crud_edit(…)`; `planentitlement_delete` → `@require_POST` + `crud_delete(…)`.
Both success URLs are the list.

### 3.4 `views/UsageQuota.py` — 6 functions (5 CRUD + 1 verb)

```python
@tenant_admin_required
def usagequota_list(request):
    qs = UsageQuota.objects.filter(tenant=request.tenant).select_related("subscription")
    # `breached_at` is a DateTimeField, not a boolean — see the note below. Applied here, not in the
    # `filters` spec, exactly as usagerecord_list does for `?billed=yes|no`.
    breached = request.GET.get("breached", "").strip()
    if breached in ("True", "False"):
        qs = qs.filter(breached_at__isnull=(breached == "False"))
    return crud_list(
        request, qs, "tenants/usagequota/list.html",
        search_fields=["notes"],
        filters=[("metric", "metric", False),
                 ("subscription", "subscription_id", True),
                 ("action", "action_on_breach", False),
                 ("period", "period", False)],
        extra_context={
            "metric_choices": UsageQuota.METRIC_CHOICES,
            "action_choices": UsageQuota.ACTION_CHOICES,
            "period_choices": UsageQuota.PERIOD_CHOICES,
            "subscription_choices": Subscription.objects
                                          .filter(tenant=request.tenant).order_by("-created_at"),
            "breached_choices": [("True", "Breached"), ("False", "Not breached")],
        },
    )
```

`metric_choices` is `UsageQuota.METRIC_CHOICES` — the same object as `UsageRecord.METRIC_CHOICES`
([RULING] 7).

**`breached` is NOT in the `filters` spec, and this is a real correction to the naive wiring.**
`breached_at` is a `DateTimeField(null=True)`, not a boolean, so `?breached=True` in a filter spec
would reach `.filter(breached_at="True")`, raise `ValueError` inside the filter, and be **silently
skipped** by `crud.py:176` — the dropdown would render, appear selected, and do nothing. The lens is
therefore applied in the view, on the `usagerecord_list` precedent (`views/UsageRecord.py:57-61`,
which does exactly this for `?billed=yes|no` and explains why in a comment). The template compares
`{% if request.GET.breached == "True" %}selected{% endif %}`. This is the **one** place a 0.19 view
filters outside `crud_list`; the comment must say why, so the next reader does not "simplify" it back
into the filter spec and silently break the dropdown.

`usagequota_create` / `usagequota_edit` → `crud_create` / `crud_edit` on `UsageQuotaForm`, template
`tenants/usagequota/form.html`, success `tenants:usagequota_list`.
`usagequota_detail` → `crud_detail(…, extra_context={"consumption": …})` where `consumption` is the
`{metric: Decimal}` map for **this** subscription, taken from `_quota_board` (§3.7) — reuse the helper,
do not re-query. **Do not** add a `quota_board_url` key unless the template renders it; a key nothing
reads is a defect (0.18 [RULING] 3).

### 3.5 `views/LicenseAssignment.py` — 6 functions (5 CRUD + 1 verb)

```python
@tenant_admin_required
def licenseassignment_list(request):
    qs = (LicenseAssignment.objects.filter(tenant=request.tenant)
          .select_related("user", "subscription"))
    return crud_list(
        request, qs, "tenants/licenseassignment/list.html",
        search_fields=["module_slug", "notes"],
        filters=[("status", "status", False),
                 ("source", "assignment_source", False),
                 ("user", "user_id", True),
                 ("module", "module_slug", False)],
        extra_context={
            "status_choices": LicenseAssignment.STATUS_CHOICES,
            "source_choices": LicenseAssignment.SOURCE_CHOICES,
            "user_choices": accounts_user_queryset(request),
            "module_choices": LicenseAssignment.objects
                                   .filter(tenant=request.tenant)
                                   .exclude(module_slug="")
                                   .values_list("module_slug", flat=True)
                                   .distinct().order_by("module_slug"),
        },
    )
```

**`user_choices` MUST be a module-level helper, and it MUST filter the null-tenant superuser:**

```python
def accounts_user_queryset(request):
    """Seat candidates: this tenant's users only.

    `accounts.User.tenant` is NULLABLE (the superuser `admin` has tenant=None by design), so an
    unfiltered queryset would offer the superuser as a seat holder — and every count on the board
    would then disagree with the register. `TenantModelForm` does this scoping for the *form*; the
    list filter and the board read the model, so they do it themselves.
    """
    return get_user_model().objects.filter(tenant=request.tenant).order_by("email")
```

`get_user_model` is **not** currently exported by `views/_common.py` — the entity module imports it
from `django.contrib.auth` explicitly. **It is needed only here**, so the import goes in
`views/LicenseAssignment.py`. Do not add it to `_common.py` on a guess; that file is shared with
0.1/0.6/0.7 and every addition is a re-read (L43).

**`module_choices` is a `ValuesListQuerySet`, not a list of objects** — `module_slug` is a plain
`CharField`, so there is no object to render; `{% for slug in module_choices %}<option value="{{ slug }}">`
is the shape, and the comparison is `{% if request.GET.module == slug %}`. Distinct + ordered, and it
is **derived from the rows that exist** rather than from `core.ModuleAccessScope`, so the dropdown can
never offer a module nobody holds a seat in. (Pointing it at `ModuleAccessScope` would be the longer
list, but that couples a seat filter to a table owned by 0.6, and the research explicitly declines a
second per-module switch — keep it derived and say why in the comment.)

`licenseassignment_create` / `licenseassignment_edit` → `crud_create` / `crud_edit` on
`LicenseAssignmentForm`, template `tenants/licenseassignment/form.html`, success
`tenants:licenseassignment_list`. `licenseassignment_detail` → `crud_detail(…, extra_context={"seat_summary": …})`
where `seat_summary` is the board's `{active, reclaimed, revoked, expired, total}` dict for **this
tenant** (§3.7) — a real roll-up, not a tautological total.

### 3.6 The two verbs (both honest, both POST-only, both audited)

**`licenseassignment_reclaim(request, pk)`** — route `seats/<int:pk>/reclaim/`, name
`licenseassignment_reclaim`.

**Sole writer of `status`, `reclaimed_on`, `reclaim_reason`.** All three are off the form
([RULING] 5), and this is the only code in the repository permitted to write them.

**Guard order, exactly:**
1. `@require_POST` — outermost, so a `GET` is **405** before the role check (§3 header).
2. `@tenant_admin_required` — 403/redirect for a non-admin.
3. `get_object_or_404(LicenseAssignment, pk=pk, tenant=request.tenant)` — **404 for a cross-tenant
   pk**, and the tenant filter is inside `get_object_or_404` so it cannot be forgotten.
4. **Idempotence guard:** `if obj.status != "active":` → `messages.info(request, "That seat is not
   active.")` → `redirect("tenants:licenseassignment_detail", pk=obj.pk)`. This is the
   `usagerecord_mark_billed` shape (`views/UsageRecord.py:133-135`) and it stops a double-click
   stamping two `reclaimed_on` values.
5. **The write:** `obj.status = "reclaimed"`, `obj.reclaimed_on = timezone.now()`,
   `obj.reclaim_reason = <the posted reason, truncated to 200>`, then
   `obj.save(update_fields=["status", "reclaimed_on", "reclaim_reason"])`. **`update_fields` is
   mandatory** — it makes the verb's write surface auditable by reading the code.
6. **The audit (L41 — read this twice):** `AuditLog.action` is
   `CharField(max_length=10, choices=[create, update, delete])` (`apps/core/models/AuditLog.py:16`),
   so the verb name **cannot** go in `action`. The call is:

```python
write_audit_log(request.user, obj, "update", changes={
    "verb": "licenseassignment_reclaim",
    "status": "reclaimed",
    "reclaim_reason": obj.reclaim_reason,
})
```

This is the `usagerecord_mark_billed` call shape in kind (`changes={"verb": …}`,
`views/UsageRecord.py:144`). **Never** pass a 24-character verb as `action`.
7. `messages.success(...)` → **`redirect("tenants:licenseassignment_detail", pk=obj.pk)`** — the
   detail page, not the list, so the operator sees the stamped evidence they just created.

**`usagequota_mark_breached(request, pk)`** — route `quotas/<int:pk>/mark-breached/`, name
`usagequota_mark_breached`.

**Sole writer of `breached_at`** (`editable=False`, off the form, §2.3). **Guard order 1-4 identical**,
with the idempotence guard `if obj.breached_at is not None:` → `messages.info("That quota is already
marked as breached.")` → detail redirect. Step 5 is
`obj.breached_at = timezone.now(); obj.save(update_fields=["breached_at"])`. Step 6 is
`write_audit_log(request.user, obj, "update", changes={"verb": "usagequota_mark_breached"})` —
**the same `changes={"verb": …}` shape, `action="update"`**. Step 7 redirects to
`tenants:usagequota_detail`.

**Neither verb requires consumption to exist, and neither one enforces `action_on_breach`.** The
`action_on_breach` value (`alert` / `charge` / `block`) is a **recorded policy with no interceptor**:
marking a quota breached writes a timestamp and an audit row, and **nothing else happens** — no alert
is raised, no charge is computed, no request is blocked. Both pages say so in those words.

### 3.7 The two computed boards — `views/Boards.py`, 2 functions, no model

Both follow `_usage_summary()` (`views/UsageRecord.py:15-47`) exactly: **one grouped query in the
view**, the allowance table read once, **no per-row `.filter()`**, and a **module-level helper** so
`usagequota_detail` can reuse the same numbers rather than re-querying (L41 §1 — the row-dict
contract is a second contract: *read the producer of the rows, not the view that forwards them*).

**`quota_board(request)`** — route `quotas/board/`, name `quota_board`.

```python
def _quota_board(tenant):
    """Quota vs. consumption, one grouped query, following `_usage_summary()`.

    Consumption is UNBILLED usage for the CURRENT period only — the same `is_billed=False` lens the
    0.1 usage list uses — so "consumed" and "overage" mean the same thing on both pages. The join is
    on the SAME `subscription` as `UsageRecord.subscription`; joining on anything else would let a
    quota be measured against a different subscription's consumption.
    """
```

The grouped query: `UsageRecord.objects.filter(tenant=tenant, is_billed=False).values("subscription_id",
"metric").annotate(total=Sum("quantity")).order_by("subscription_id", "metric")`, then
`UsageQuota.objects.filter(tenant=tenant).select_related("subscription")` fetched **once** into a
`{(subscription_id, metric): quota}` dict. Every row is then built in Python from those two
structures — **one query per model, constant regardless of how many metrics or quotas exist.**

**Each row dict has EXACTLY these keys** (the template may not read any other):

| Key | Type | Note |
|---|---|---|
| `quota` | `UsageQuota` | the object, for `{% url 'tenants:usagequota_detail' row.quota.pk %}` |
| `subscription` | `Subscription` | denormalised onto the row so the template never walks `quota.subscription` |
| `metric` | str | the choice value |
| `metric_label` | str | `labels.get(metric, metric)` — never empty |
| `limit` | Decimal | `quota.quota_limit` |
| `consumed` | Decimal | `Decimal("0.00")` when the metric has no usage rows this period — **never `None`**, or the template's arithmetic prints blank |
| `pct_used` | int | `0` when unmetered; else `min(int(consumed / limit * 100), 999)` — capped so a `limit` of `0.01` cannot render a 4000% cell |
| `overage` | Decimal | `max(0, consumed - limit)`; **`Decimal("0.00")` when unmetered** |
| `warn_at_pct` | int | copied from the quota, so the template does no arithmetic to find the threshold |
| `is_warned` | bool | unmetered ⇒ `False` |
| `is_breached` | bool | `quota.breached_at is not None` — **the recorded stamp, not a recomputation**, so a manual mark-breach shows here immediately |
| `breached_at` | datetime or `None` | **read inside an `{% if %}` branch in the template, never through a filter argument** (L10) |
| `action_on_breach` | str | the raw value; the label is `dict(ACTION_CHOICES)[…]` **in the view**, so the template never builds a dict |
| `is_fair_use` | bool | |

**`pct_used` is `0` and the row renders "Unmetered" whenever `limit == 0`** — the §1.3 rule, applied
here. Unmetered rows are excluded from the `warned`/`breached` counts below.

**`quota_board` context (EXACTLY six keys):**

| Key | Value |
|---|---|
| `quota_rows` | the list of row dicts above, ordered by `-pct_used` then `metric_label` |
| `warned_count` | `len([r for r in rows if r["is_warned"]])` — a real roll-up, not a tautology (0.52's zero-rule) |
| `breached_count` | `len([r for r in rows if r["is_breached"]])` |
| `unmetered_count` | `len([r for r in rows if r["limit"] == 0])` |
| `metric_choices` | `UsageQuota.METRIC_CHOICES` (the same object) |
| `action_choices` | `UsageQuota.ACTION_CHOICES` |

**`renewal_board(request)`** — route `renewals/board/`, name `renewal_board`.

One query: `Subscription.objects.filter(tenant=request.tenant).order_by("renews_on", "id")` —
**never a per-row `days_left()` loop is forbidden**; `days_left()` (`models/Subscription.py:35-37`) is
a pure method on an already-loaded row, so calling it per row is fine and is **preferred over
re-deriving the arithmetic in the view**. It returns `None` when `renews_on` is unset, and the
template must handle that (`{% if renewal.days_left is not None %}`) — a bare
`{{ renewal.days_left }}` would print `None` on screen.

**Each row dict has EXACTLY these keys:**

| Key | Type | Note |
|---|---|---|
| `subscription` | `Subscription` | for `{% url 'tenants:subscription_detail' renewal.subscription.pk %}` |
| `plan` | str | the raw choice value |
| `plan_label` | str | the display value, computed in the view |
| `status` | str | the raw value; label in the view |
| `days_left` | int or `None` | `subscription.days_left()` — `None` when `renews_on` is unset |
| `auto_renew` | bool | **the recorded intent; nothing reads it** |
| `grace_ends_on` | date or `None` | read inside `{% if %}` in the template (L10) |
| `in_grace` | bool | `grace_ends_on is not None and today <= grace_ends_on` |
| `is_expired` | bool | `renews_on is not None and renews_on < today` — a **computed** state, never a stored status |
| `seats` | int | copied so the template does no FK walk |

**`renewal_board` context (EXACTLY six keys):** `renewal_rows`, `expiring_count`
(`len([r for r in rows if r["days_left"] is not None and 0 <= r["days_left"] <= 30])`),
`in_grace_count`, `expired_count`, `auto_renew_count`, `plan_choices` (`Tenant.PLAN_CHOICES`).

**The seat roll-up reused by `licenseassignment_detail`** is a **separate** module-level helper
`_seat_summary(tenant)` in `views/Boards.py`, returning
`{"active": …, "reclaimed": …, "revoked": …, "expired": …, "total": …}` from **one** query using
`.values("status").annotate(n=Count("id"))`, with the `user__tenant=tenant` clause on the active count
(§1.4). `expired` is the count of rows whose `expires_on` is past **and** whose `status == "active"` —
the displayed state, never a stored one.

---

## 4. URL contract — `apps/tenants/urls.py`, +24 named routes

`tenants/urls.py` is a deliberately **flat** module (backend rule 10: it is a hand-written list, and
`tenants` has no sub-module level), `app_name = "tenants"`, `urlpatterns` is a plain list, and Django
resolves **first-match-wins — so order is behaviour.** Every `add/` and every literal board route goes
**before** its `<int:pk>` siblings, exactly as the 0.1 usage block does (`urls.py:43-49`, whose
comment reads *"Literal routes BEFORE the `<int:pk>` routes."*).

**Append the whole 0.19 block after the existing `path("isolation/", …)` line, with a section
comment.** Appending at the end is safe **only because no new path is a prefix of an existing one** —
verified below. Do not renumber or reorder any existing line; `urls.py` is shared with 0.1/0.6/0.7
(L43).

```python
    # Licensing & subscription administration (0.19). Literal routes BEFORE the <int:pk> routes.
    # --- Entitlement feature catalog (bullet 2, the catalog half)
    path("entitlements/", views.entitlementfeature_list, name="entitlementfeature_list"),
    path("entitlements/add/", views.entitlementfeature_create, name="entitlementfeature_create"),
    path("entitlements/<int:pk>/", views.entitlementfeature_detail, name="entitlementfeature_detail"),
    path("entitlements/<int:pk>/edit/", views.entitlementfeature_edit, name="entitlementfeature_edit"),
    path("entitlements/<int:pk>/delete/", views.entitlementfeature_delete, name="entitlementfeature_delete"),
    # --- Plan grants + subscription-level overrides (bullet 2, the grant half)
    path("entitlements/grants/", views.planentitlement_list, name="planentitlement_list"),
    path("entitlements/grants/add/", views.planentitlement_create, name="planentitlement_create"),
    path("entitlements/grants/<int:pk>/", views.planentitlement_detail, name="planentitlement_detail"),
    path("entitlements/grants/<int:pk>/edit/", views.planentitlement_edit, name="planentitlement_edit"),
    path("entitlements/grants/<int:pk>/delete/", views.planentitlement_delete, name="planentitlement_delete"),
    # --- Usage quotas + the quota board (bullet 3)
    path("quotas/", views.usagequota_list, name="usagequota_list"),
    path("quotas/board/", views.quota_board, name="quota_board"),
    path("quotas/add/", views.usagequota_create, name="usagequota_create"),
    path("quotas/<int:pk>/", views.usagequota_detail, name="usagequota_detail"),
    path("quotas/<int:pk>/edit/", views.usagequota_edit, name="usagequota_edit"),
    path("quotas/<int:pk>/delete/", views.usagequota_delete, name="usagequota_delete"),
    path("quotas/<int:pk>/mark-breached/", views.usagequota_mark_breached, name="usagequota_mark_breached"),
    # --- Seat register (bullet 1)
    path("seats/", views.licenseassignment_list, name="licenseassignment_list"),
    path("seats/add/", views.licenseassignment_create, name="licenseassignment_create"),
    path("seats/<int:pk>/", views.licenseassignment_detail, name="licenseassignment_detail"),
    path("seats/<int:pk>/edit/", views.licenseassignment_edit, name="licenseassignment_edit"),
    path("seats/<int:pk>/delete/", views.licenseassignment_delete, name="licenseassignment_delete"),
    path("seats/<int:pk>/reclaim/", views.licenseassignment_reclaim, name="licenseassignment_reclaim"),
    # --- Renewal & expiry board (bullet 5)
    path("renewals/board/", views.renewal_board, name="renewal_board"),
```

**Ordering proof (this is why appending is safe, and it is checked, not assumed):**
* `quotas/board/` precedes `quotas/<int:pk>/` — and it must, because `board` is a `str`, so
  `<int:pk>` would **not** match it anyway; the ordering is defensive, not load-bearing. Written
  first so a future `path("quotas/<str:token>/", …)` cannot swallow it.
* `entitlements/` precedes `entitlements/grants/`. Both are exact literals with no converter, so
  Django matches on the **full** remaining path, not a prefix — `entitlements/` does **not** shadow
  `entitlements/grants/`. (This is the one place a reader will worry; the comment in the file should
  say so, or the next agent will "fix" it into a prefix route and break the grants list.)
* **No new path is a prefix of an existing one and vice versa.** The pre-existing first segments are
  `subscriptions`, `subscription-invoices`, `branding`, `encryption-keys`, `health`, `usage`,
  `onboarding`, `isolation`, `stripe`. The new ones are `entitlements`, `quotas`, `seats`,
  `renewals`. **No overlap.**
* **`usage/` vs `quotas/`:** distinct, so 0.1's usage register and 0.19's quota register never
  collide. This is the L36 boundary made concrete in the URLconf.

**All 24 names must reverse.** Assert programmatically before the sub-module is considered wired:
`for name in [...]: reverse(f"tenants:{name}")`. Every one of the 24 appears in the
`views/__init__.py` re-export block (§6.2) — a route whose view was not re-exported is an
`AttributeError` at import time, which `manage.py check` catches.

---

## 5. Template contract — 14 files under `templates/tenants/`

**Folder shape (rule 4 — `tenants` is a foundation app and is FLAT: no sub-module level).** The
entity folder sits at the app root: `templates/tenants/<entity>/{list,detail,form}.html`, exactly the
existing `templates/tenants/usagerecord/` shape. The two boards are **standalone computed pages with
no model**, so they sit at the **app root** beside `isolation.html` and `onboarding_wizard.html` —
not inside an entity folder (rule 6).

| # | File | Backing view |
|---|---|---|
| 1-3 | `entitlementfeature/{list,detail,form}.html` | 0.19 |
| 4-6 | `planentitlement/{list,detail,form}.html` | 0.19 |
| 7-9 | `usagequota/{list,detail,form}.html` | 0.19 |
| 10-12 | `licenseassignment/{list,detail,form}.html` | 0.19 |
| 13 | `quota_board.html` | `quota_board` |
| 14 | `renewal_board.html` | `renewal_board` |

All 14 `{% extends "base.html" %}`. The **0.1 `usagerecord/list.html` is the style reference** — read
it before writing the first one and copy its filter bar, Actions column, pagination block and
empty-state rather than inventing a new shape.

### 5.1 The four list templates — six mandatory elements each

1. **Filter bar reflecting `request.GET`.** One `<select>` per key in that view's `extra_context`,
   and **one key per dropdown** (0.18 [RULING] 3, both directions). Select-when comparisons:
   * enum / char field: `{% if request.GET.status == "draft" %}selected{% endif %}`
   * FK queryset: `{% if request.GET.feature == f.pk|stringformat:"d" %}selected{% endif %}` —
     **never `|slugify`**
   * `ValuesListQuerySet` (`module_choices`): `{% if request.GET.module == slug %}selected{% endif %}`
   * boolean: `{% if request.GET.addon == "True" %}selected{% endif %}` ([RULING] 6)
2. **Actions column** on every row: view (eye) → `{% url 'tenants:<entity>_detail' obj.pk %}`;
   edit (pencil) → `{% url 'tenants:<entity>_edit' obj.pk %}`; delete (bin) → a **POST form** with
   `{% csrf_token %}` and `onclick="return confirm('…')"`. For the two verbs, a third button:
   **Reclaim** (bin, POST) on `licenseassignment` rows and **Mark breached** (alert, POST) on
   `usagequota` rows — both POST forms with csrf + confirm.
3. **Pagination (L9) — the guards are mandatory, not optional:**
   `{% if page_obj.has_previous %}…page={{ page_obj.previous_page_number }}{% else %}…page=1{% endif %}`
   and the `has_next` / `paginator.num_pages` equivalent. `Page.previous_page_number()` **raises
   `EmptyPage` on page 1**, so an unguarded `{{ page_obj.previous_page_number }}` 500s as soon as a
   list exceeds 15 rows — invisible with small seed data, which is why it ships. The windowed
   `page_obj.window` list (with `None` marking an ellipsis gap, `crud.py:32-33`) is available for a
   numbered pager.
4. **Empty state** naming what would appear here.
5. **Honesty prose** — §5.4.
6. **Status badges: colour-named classes ONLY** — `badge-green`, `badge-red`, `badge-amber`,
   `badge-info`, `badge-muted`, `badge-slate`. The semantic `badge-success` / `badge-warning` /
   `badge-danger` names **do not exist in this stylesheet and render unstyled** (L33, shipped three
   times). Every badge condition uses the **exact** model choice value (`"reclaimed"`, not
   `"reclaim"`; `"past_due"`, not `"pastdue"`), and every badge has an `{% else %}` fallback of
   `{{ obj.get_status_display }}`.

### 5.2 The four detail templates
Actions **sidebar** (not a row): Edit → `{% url …_edit obj.pk %}` (conditional where the model says
so — for `licenseassignment`, hide Edit when `obj.status != "active"`, since a reclaimed seat's
identity fields are what the operator may still correct but its *status* they may not), Delete (POST +
confirm + csrf), and **Back to <Model> list**. Plus the related rows from §3.2-§3.5 — and **every
nullable FK is read inside an `{% if %}` branch, never through a `|default:` filter argument** (L10).

### 5.3 The two board templates
Tables over `quota_rows` / `renewal_rows`, one `<tr>` per row, **one empty-state row when the list is
empty** (an empty `<tbody>` renders as a page with no table at all, which reads as a bug). The
percentage cell prints `pct_used` and appends `%` only when the row is not unmetered. Board pages get
no filter bar — they are whole-tenant roll-ups, and a filter that silently changes what "3 breached"
means is worse than no filter.

### 5.4 The honesty contract — the ten declines, per page, in prose (binding)

**Every one of the 14 templates carries a short, visible note** — not a tooltip, not a docstring, a
sentence or two a member actually reads. Which declines apply where:

* **All 14 pages** carry the umbrella: *"NavERP records commercial terms somebody wrote down. It does
  not enforce them."*
* **`entitlementfeature/*`, `planentitlement/*`:** entitlement enforcement is declined — nothing
  consults a `PlanEntitlement` at request time; a grant is a **record**, not a gate.
* **`usagequota/*`, `quota_board.html`:** quota enforcement and throttling are declined —
  `action_on_breach` is a **recorded policy with no interceptor**; marking a quota breached writes a
  timestamp and an audit row and **nothing else happens**.
* **`licenseassignment/*`:** seat auto-deprovisioning is declined — there is no identity sync, so
  reclaiming a seat **does not disable the login**. Say this on the reclaim button and on the list.
* **`quota_board.html`:** metered event ingestion is declined — `UsageRecord` rows are entered by
  hand or by 0.1's flow; there is no event pipeline feeding this board.
* **`renewal_board.html`:** automatic renewal execution is declined — `auto_renew` is a **recorded
  intent with no scheduler**; nothing renews anything. And expiry **email delivery** is declined —
  there is no sender in `tenants` (0.20/0.21 own it), so **no email is sent when a subscription
  expires.**
* **Declared on `SubscriptionForm` / `subscription/form.html` (0.1's page, one line added):** proration
  is declined — no money arithmetic is performed anywhere in 0.19 (L29).
* **Prepaid credit grants** and **rate cards / tiered / multi-currency pricing** are declined
  app-wide; the statement belongs on the two board pages and the nav comment, not on all 14.

**The L36 note, required on `quota_board.html` and `renewal_board.html`:** bullets 3 and 4 of 0.19
point at these **new** boards, but **the underlying rows are 0.1's** — `UsageRecord` and
`Subscription` / `SubscriptionInvoice` were built by sub-module 0.1 and are **extended by FK and by two
columns here, never re-declared**. The page says which rows are 0.1's, in those words. A reader who
believes 0.19 built a second usage table will file a duplicate-billing bug against the wrong
sub-module.

---

## 6. Wire-up — the shared files, one writer, one file per commit

### 6.1 `apps/tenants/models/__init__.py` — add the four models to the re-export block
**Append** four `from .<Entity> import (<Model>,)` blocks after the existing `UsageRecord` block,
matching the file's existing grouping style. **Adding a model without the re-export is a bug** (L7: a
silent `ImportError`/`AttributeError` at runtime, and the seeder, the admin and every test import from
`apps.tenants.models`). Shared with 0.1 — re-read before editing (L43), change nothing else.

### 6.2 `apps/tenants/views/__init__.py` — re-export all 24 new view functions
Six blocks: `from .EntitlementFeature import (…)` (5 names), `from .PlanEntitlement import (…)` (5),
`from .UsageQuota import (…)` (6), `from .LicenseAssignment import (…)` (6), `from .Boards import
(quota_board, renewal_board)` (2). **24 names total.** A route whose view was not re-exported is an
`AttributeError` at import — which `manage.py check` catches, so this is verifiable, not hopeful.

### 6.3 `apps/tenants/forms/__init__.py` — re-export the four new form classes
Four blocks, same pattern, after the existing `UsageRecordForm` block.

### 6.4 `apps/tenants/admin.py` — register the four models
Four `@admin.register` classes, each with a real `list_display` / `list_filter` and `readonly_fields`
carrying the evidence stamps — `["number", "breached_at", "created_at"]` for `UsageQuota`,
`["number", "reclaimed_on", "created_at"]` for `LicenseAssignment`, `["number", "created_at"]` for the
other two. `number` is `editable=False` so it is off the admin form structurally, but listing it in
`list_display` is what makes the register navigable. **Append only.**

### 6.5 `apps/core/settings_engine.py` — extend `LITERAL_PREFIX_MODELS`
```python
LITERAL_PREFIX_MODELS = {
    "SINV": ["tenants.SubscriptionInvoice"],
    "ENT":  ["tenants.EntitlementFeature"],
    "PE":   ["tenants.PlanEntitlement"],
    "UQ":   ["tenants.UsageQuota"],
    "SEAT": ["tenants.LicenseAssignment"],
}
```
Without this the 0.10 numbering board reports four prefixes as `model_only` and never names the models
minting them (§1). Shared with 0.10/0.13 — re-read before editing (L43).

### 6.6 `apps/tenants/management/commands/seed_tenants.py` — add `_seed_licensing(tenant)`
**Idempotence: a PER-ENTITY guard, never a tenant-wide one** (the 0.18 ruling). `_seed_licensing` gets
**four** independent guards — `if EntitlementFeature.objects.filter(tenant=tenant).exists(): … skip` —
so a second run adds nothing, and a partially-seeded tenant self-heals instead of being skipped
wholesale. `get_or_create` on each unique tuple; never `.create()` on a numbered model, or the second
run mints a second number.

**No `Subscription` is created here** (0.1 owns those) — extend the existing subscription's two new
fields instead: `sub.auto_renew = True`, `sub.grace_ends_on = <today + 10 days>`,
`sub.save(update_fields=[…])`, guarded so a second run changes nothing.

**Seeder rule that is not optional:** each model name must appear **literally** in the seeder file's
bytes, because `temp/audit_integrity.py:277` greps `re.search(r"\b" + m.__name__ + r"\b", blob)` to
decide whether a model is seeded — a helper indirection would make all four models read as "unseeded
and unexplained" and fail the audit. Print the tenant-admin login instructions, and warn that the
superuser has no tenant.

### 6.7 `apps/core/navigation.py` — the `LIVE_LINKS["0.19"]` block

**One block, inserted immediately after `LIVE_LINKS["0.18"]`'s closing `},` (currently line 294) and
before the `# ===== Module 1 — Customer Relationship Management` comment at line 295.** Surgical edit
adjacent to 0.18; **re-read the file immediately before editing** — another session may be working
nearby (L43), and those line numbers are from contract time.

```python
    # 0.19 License & Subscription Administration. The five bullet keys below are copied
    # BYTE-IDENTICALLY from `NavERP.md` lines 251-255; `parse_catalog()` matches them by exact
    # string, so a one-character drift renders a fully built page as a "soon" roadmap pill with no
    # error anywhere. Verify with the repo's own `parse_catalog()`, never by eye.
    #
    # Every label points at a DISTINCT page: `resolve_nav` renders every label in the dict, so two
    # labels over one page light the active-link highlight twice. Asserted before this block counts
    # as wired.
    #
    # **Bullets 3 and 4 point at 0.19's NEW boards; the underlying rows are 0.1's.** `UsageRecord`,
    # `Subscription` and `SubscriptionInvoice` were built by sub-module 0.1 and are EXTENDED here
    # (a quota to read the meter against, two columns on the subscription) — never re-declared. The
    # boards are new; the rows are 0.1's.
    #
    # **TEN capabilities are DECLINED, not partially faked**, and every page says so in its own
    # prose: entitlement enforcement (no interceptor consults `PlanEntitlement` at request time) ·
    # quota enforcement/throttling (`action_on_breach` is a recorded policy with no interceptor) ·
    # seat auto-deprovisioning (no identity sync — reclaiming a seat does not disable a login) ·
    # metered event ingestion (no event pipeline) · proration (no money arithmetic; L29) · prepaid
    # credit grants (a second money store; L29) · rate cards / tiered / multi-currency pricing (a
    # monetization engine, not a sub-module) · plan versioning & grandfathering · automatic renewal
    # execution (no scheduler — 0.20) · expiry email delivery (no sender in `tenants` — 0.20/0.21).
    "0.19": {
        "License Allocation & Seats": "tenants:licenseassignment_list",   # bullet 1 (the seat register)
        "Plan & Entitlement Management": "tenants:planentitlement_list", # bullet 2 (plan grants + overrides)
        "Usage Metering & Quotas": "tenants:quota_board",                 # bullet 3 (the NEW board; rows are 0.1's)
        "Billing & Invoicing Integration": "tenants:renewal_board",       # bullet 4 (renewal/grace record; 0.1's Subscription + invoices)
        "Renewal & Expiry Management": "tenants:subscription_list",       # bullet 5 (auto_renew / grace_ends_on columns)
        # Extra built pages that are NOT NavERP.md bullets. `resolve_nav` appends these AFTER the
        # bullets, so they read as operational leaves rather than as more promised features.
        "Entitlement Feature Catalog": "tenants:entitlementfeature_list", # extra (bullet 2's catalog half)
        "Usage Quota Register": "tenants:usagequota_list",                # extra (bullet 3's register)
    },
```

**The five keys are byte-identical to `NavERP.md` lines 251-255** — `License Allocation & Seats`,
`Plan & Entitlement Management`, `Usage Metering & Quotas`, `Billing & Invoicing Integration`,
`Renewal & Expiry Management`. Verified by reading `NavERP.md:251-255` directly at contract time.

**The five targets are DISTINCT** — `licenseassignment_list`, `planentitlement_list`, `quota_board`,
`renewal_board`, `subscription_list` — and the two extras are distinct from all five. **7 labels over
7 distinct targets.** Note bullet 2's two halves get two pages (the catalog and the grants) and
**neither** is a duplicate of the other; `entitlementfeature_list` is an *extra* precisely because
`planentitlement_list` is already bullet 2's target.

**Bullet 4's target needs one sentence of justification and it belongs in the comment above:**
`Billing & Invoicing Integration` names *subscription billing, proration, and payment-gateway sync*.
Proration is declined and gateway sync is **0.1's** (`stripe_webhook`, signature-verified at
`views/Subscription.py:103-158`). So the only part of bullet 4 that 0.19 *adds* is the recorded
renewal/grace state on the subscription — and the renewal board is where an operator reads the billing
period's commercial terms. Pointing bullet 4 at `tenants:subscriptioninvoice_list` instead would
**duplicate 0.1's extra leaf "Subscription Invoices"** onto a second sub-module's bullet, which is
exactly the L36-ownership confusion the plan's own boundary note warns against.

### 6.8 The migration
Generate as the **last backend step**, after all four model files exist and are re-exported, so Django
auto-depends on anything a peer landed in the meantime. `venv\Scripts\python.exe manage.py
makemigrations tenants` → `migrate` → `seed_tenants` **twice** → `manage.py check`, then
`makemigrations --check --dry-run` → **"No changes detected"**. Name: **`tenants.0005_*`**
(`0005_entitlementfeature_planentitlement_usagequota_licenseassignment_and_more.py` in practice —
Django generates it, do not hand-write it).

---

## 7. Verification checklist (the gate — in order, all of it)

Run as `admin_acme` / `password` with a throwaway `temp/` script, `Client(raise_request_exception=False)`
so one pass collects **all** failures instead of aborting on the first (L8).

1. **Every one of the 24 routes returns 200 (GET pages) or 302 (POST redirects)** as `admin_acme`.
2. **Content assertions, not status codes (L8 — a 200 proves nothing about a blank region).** For each
   of the 14 pages assert the **rendered HTML** contains:
   * list pages — a seeded row's own `number` (e.g. `ENT-00001`, `SEAT-00001`) **and** the page title;
   * detail pages — the row's `number` **and** one field value, so a wrong context var is caught;
   * both boards — a seeded `metric_label` and a seeded `plan_label`;
   * **no `{#` and no `{% comment` in any output** (L3 — a half-written template block leaks as
     literal text and still returns 200).
3. **Junk-param gate.** `?status=nope`, `?privilege_type=nope`, `?metric=nope`, `?action=nope`,
   `?period=nope`, `?source=nope`, `?feature=abc`, `?user=0`, `?subscription=abc`, `?page=9999`,
   `?addon=yes` — each list returns 200 **and the unfiltered row count is unchanged** (not merely a
   200). `?page=9999` resolves to the last page, and the prev/next guards hold.
4. **Page 2.** Seed enough rows to exceed 15 on at least one list, request `?page=2`, assert 200 and
   that the pagination block rendered — this is the only way the L9 `EmptyPage` 500 ever shows up.
5. **Cross-tenant IDOR → 404.** As the second tenant's admin, request every detail / edit / delete and
   both verb URLs for a row owned by the first tenant. All **404**; both verbs refuse as well.
6. **Method check.** `GET` on all four delete URLs and both verb URLs returns **405** (`@require_POST` is
   above the role gate), and an unauthenticated request redirects to login. A non-admin member is
   refused (**403**) on all 24 routes.
7. **Cross-tenant FK binding.** A POST naming another tenant's `feature` / `user` / `subscription` id
   re-renders the form with an error, never saves.
8. **Duplicate guard.** A POST repeating an existing `(tenant, code)` / `(tenant, subscription, metric,
   period)` / `(tenant, user, module_slug)` / duplicate plan-level grant returns **200 with a form
   error**, not a 500 ([RULING] 8) and not a second row ([RULING] 2).

9. **Audit-log assertions.** POST both verbs, then assert an `AuditLog` row exists with
   `action="update"` and `changes["verb"]` equal to the verb name — and that **`action` is one of
   `create`/`update`/`delete`**, never a verb string (L41).
10. **One-writer assertions.** After a reclaim POST, `status`, `reclaimed_on` and `reclaim_reason` are
    set; after a mark-breached POST, `breached_at` is set. And **`LicenseAssignmentForm` has no
    `status`, `reclaimed_on` or `reclaim_reason` field; `UsageQuotaForm` has no `breached_at` field**
    ([RULING] 5, L22).
11. **Nav distinctness gate.** `len(set(LIVE_LINKS["0.19"].values())) == len(LIVE_LINKS["0.19"]) == 7`,
    **all seven reverse**, and the five bullet keys diff **byte-identical** against `parse_catalog()`.
    Both `apps/core/tests/test_navigation_active.py` and `temp/audit_integrity.py` walk `LIVE_LINKS`,
    so the active-link logic must light **exactly one** label per page.
12. **Sidebar shows 0.19 Live**, not a "soon" roadmap pill.
13. **`venv\Scripts\python.exe temp\audit_integrity.py` passes**, and independently reports
    `module 0: 2 catalogued but NOT built -> 0.20, 0.21`. **Any new model left unseeded and
    unexplained is a failure** — an unexplained exemption is indistinguishable from an oversight (L52).
    The four new models must therefore appear literally in `seed_tenants.py` (§6.6).
14. **`makemigrations --check --dry-run` → "No changes detected"** after the migration lands, and
    `manage.py check` clean (which re-runs the E009 max_length/choices check cleared in §0).
15. **Idempotence.** `seed_tenants` run twice seeds nothing the second time; the four per-entity guards
    hold, and the numbered models did not mint a second `ENT-`/`PE-`/`UQ-`/`SEAT-` number.
16. **Null-tenant sweep (L10).** Every nullable FK (`PlanEntitlement.subscription`,
    `LicenseAssignment.subscription`, `User.tenant`, `UsageQuota.breached_at`,
    `Subscription.grace_ends_on`, `LicenseAssignment.reclaim_reason`) renders with **no**
    `VariableDoesNotExist` and no literal `None` in the HTML, on a tenant seeded with no overrides and
    no grace date. Also assert the **seat count** equals the register's active rows — a null-tenant
    seat would make them disagree by one.
17. **Honest-claim sweep.** Read all 14 templates against the one question that matters most — *does
    any page imply that NavERP enforced, blocked, throttled, sent, scheduled, de-provisioned or
    integrated anything?* A heading reading "Enforced limits" when nothing enforces is the 0.16 lie;
    "Recorded policy — no enforcing layer" is the same fact told honestly. Do this **before Phase 4**,
    so the six reviewers spend their passes on quality rather than on a page that lies.
18. **Query-count sanity.** Both boards run a **constant** number of queries (one grouped `UsageRecord`
    query + one `UsageQuota`/`Subscription` query + one labels lookup), not one per row. Check with
    `CaptureQueriesContext` on a tenant with several quotas and several subscriptions.

**Commit discipline for the whole build:** one file per commit, explicit paths,
`git add '<path>'; git commit -m '<specific message about that one file>'` — PowerShell `;` separators,
never `&&`. **Never `git push`, at any step.** Never stage `temp/` or the untracked `.commandcode/`,
`.gemini/`, `.workbuddy-ai/`, `.zcode/` directories — they belong to other sessions (L45). If a build
step appears to need one of them, stop and re-plan rather than staging it.

---

## 8. The build order (one thing at a time — never interleave)

1. **`apps/tenants/models/EntitlementFeature.py`**, then `PlanEntitlement.py`, then `UsageQuota.py`,
   then `LicenseAssignment.py` — one file, one commit each, in that order (the FK order). Then
   **`models/Subscription.py`** — the two-column surgical edit, **re-read first** (L43).
2. **`apps/tenants/forms/`** — four new files + the `Subscription.py` surgical edit. One commit each.
3. **`apps/tenants/views/`** — `EntitlementFeature.py`, `PlanEntitlement.py`, `UsageQuota.py`,
   `LicenseAssignment.py`, `Boards.py`. One commit each. **Decorator order is checked here** (§3).
4. **The 14 templates**, entity by entity, then the two boards. One commit each.
5. **Integrate** — verify every expected file actually landed *before* wiring anything, then §6.1-§6.8
   in order, one file per commit, then `makemigrations` → `migrate` → `seed_tenants` **twice** →
   `manage.py check`.
6. **Smoke** against §7, then Phase 4.

**Not in this contract's scope and not touched by the build:** `config/settings.py` (no new app, no
new setting, no new middleware), `apps/core/middleware.py` (**no entitlement interceptor** — decline #1;
adding one would change runtime behaviour across every module and is a separate pass with its own
review), `NavERP.md` / `NavERP-ERD.md` / `README.md` (Phase 7), `apps/tenants/tests/*` (Phase 6,
append-only), `.claude/skills/tenants/SKILL.md` (Phase 7 — **update** the existing skill; `tenants`
is not a brand-new app). For Phase 7, L36 §2 requires reconciling **both** sides of the 0.1/0.19
boundary in one sweep, or the doc contradicts the code.

---

## 9. Defects found in the plan — summary

Ten, recorded above as [RULING]s rather than worked around. In severity order:

| # | Defect | Consequence if built as planned |
|---|---|---|
| 1 | `LIC-` prefix already owned by `scm.TradeLicense` (`TradeLicenses.py:55`) | Two registers mint the same customer-facing number per tenant; `NumberingScheme` cannot configure both; the 0.10 numbering board reads one prefix as two document kinds. **Ruled: `SEAT-`.** |
| 2 | `unique_together(tenant, plan, feature, subscription)` on a **nullable** FK, relied on to stop duplicate plan grants | MySQL **and** SQLite treat NULLs as distinct, so the constraint **never fires** for plan-level grants and **no test on this project can catch it**. **Ruled: keep the tuple, add a `clean()`.** |
| 3 | `is_override` as a column beside a `SET_NULL` FK | Deleting a `Subscription` leaves `is_override=True` on a row that has no override — a permanently-lying register. **Ruled: `@property`.** |
| 4 | "seat counts … stay `@property`" | A per-row count re-queries per render; unimplementable as stated. **Ruled: count in the view, `is_reclaimable` stays a property.** |
| 5 | The verb is the "sole writer of `status`" but `status` is left on `LicenseAssignmentForm` | A member can `POST status=active` and silently re-activate a revoked seat, undoing L22. **Ruled: `status` excluded.** |
| 6 | Boolean lenses assumed to take `?flag=yes\|no` | `crud_list` maps only `"True"`/`"False"`; `"yes"` raises inside `.filter()` and is **silently skipped** — the dropdown renders and does nothing. **Ruled: literal `True`/`False`.** |
| 7 | The view is said to pass "the `metric` queryset" | `UsageQuota.metric` is a `CharField` with choices; there is no queryset, and inventing one is the duplication the research rejects. **Ruled: `metric_choices`, by identity.** |
| 8 | Three models carry a non-nullable `unique_together` with **no** duplicate guard | A duplicate create/edit POST is an **HTTP 500**, not a form error — exactly `review-core-0.15` L5-C1/L5-C2. **Ruled: `clean()` on all four forms.** |
| 9 | Forms assumed to accept "no user kwarg" | `crud_create`/`crud_edit` pass `tenant=` **unconditionally**; a plain `ModelForm` dies with `TypeError`. **Ruled: `TenantModelForm` everywhere (the plan says so; pinned so it is not "simplified").** |
| 10 | "**nine** declines" | The list has **ten** items, and the miscount has already propagated into the research, the plan, and the `LIVE_LINKS` comment the plan asks for. **Ruled: say ten.** |

**Also corrected in passing, not a plan defect but a build trap:** `?breached=True` against
`UsageQuota.breached_at` (a `DateTimeField`) is silently swallowed by `crud.py:176`, so the breached
lens is applied in the view on the `usagerecord_list` precedent, not in `crud_list`'s filter spec
(§3.4).

**Verified CLEAR, so the build does not re-litigate them:** every `max_length` exceeds its longest
CHOICES value (the `fields.E009` bug that blocked 0.18); every index name is ≤ 27 chars and unique
app-wide (MySQL's 30-char limit); `ENT-`/`PE-`/`UQ-`/`SEAT-` are collision-free across all 258
repo prefixes; a `tenants → accounts.User` FK is legal (`accounts` precedes `tenants` in
`INSTALLED_APPS`, and `inventory.InventoryAlert` already does it); `tenants.0005_*` is free; and every
assumed `crud_*` signature exists exactly as used.

---

*Contract frozen 2026-09-27. Sources: research `44c7de31`, the plan at the top of `todo.md`, BASE
`44c7de31`. Every pinned name verified against the as-built source with grep. The ten defects found in
the plan are recorded as [RULING]s above rather than papered over.*





















