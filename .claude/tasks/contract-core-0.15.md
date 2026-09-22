# Contract — Module 0 sub-module **0.15 Localization & Regional Settings** (`core`)

**BASE:** `35cde520` · **Migration:** `core.0012` · **Test subslug:** `localization`
**App:** `core` — foundation app, entity files **FLAT at the package root** (`apps/core/models/Localization.py`),
`apps/core/urls.py` is a **flat file**. This mirrors 0.10–0.14 exactly.

> **Read this before writing a line of code.** Every name below is pinned because a name left unpinned is a
> silently blank region (L7) or a `NoReverseMatch` (L8). If the build needs a name that is not here, add it
> here first, then build it.

---

## 0. The L36 ownership call — what 0.15 must NOT re-declare

| exists already | where | 0.15's relationship |
|---|---|---|
| `accounting.Currency` — `code` (3, unique), `name`, `symbol`, `is_active`; **GLOBAL, no tenant FK** | `apps/accounting/models/GeneralLedger/Currencies.py:6` | FK'd **by string** as the base currency. Never re-declared, never given a tenant FK. |
| `accounting.ExchangeRate` — `tenant`, `currency`, `rate_date`, `rate`, `source` ∈ {manual, feed}, `unique_together ("tenant","currency","rate_date")` | `.../GeneralLedger/ExchangeRates.py:5` | **Read only.** The board reads it; 0.15 writes no rate. |
| `accounting.TaxCode` — `tenant`, `name`, `jurisdiction`, `tax_type`, `rate_pct`, `payable_account`, `is_active` | `.../Tax/TaxCodes.py:6` | FK'd by string from `StatutoryRule.tax_code`. Never re-declared. |
| `core.BusinessCalendar.timezone_name` — free-text IANA, the **working-day** zone | `apps/core/models/Calendar.py:17` | **Untouched.** A different zone from the tenant's display zone; both are legitimate. |
| `core.SettingDefinition` / `SettingValue` — the 0.10 generic settings engine | `apps/core/models/Setting.py:16,52` | **Untouched.** A language is a row with an RTL flag, not a key/value pair. |
| `core.SyncSchedule` — 0.13's recorded sync intention | `apps/core/models/Integration.py:219` | **Reused, not duplicated.** "Scheduled rate updates" is a `SyncSchedule` row with `entity_label="accounting.ExchangeRate"`. |

**Verified absent from the whole repo** (grep, no matches): `Language`, `TimeZone`, `Locale`,
`LocaleProfile`, `RegionalSetting`, `LocalizationProfile`, `StatutoryRule`, `EInvoicingConfig`.
`config/settings.py` has `USE_I18N=True` but **no `LANGUAGES`, no `LOCALE_PATHS`, no `locale/` directory**.

---

## 1. Models — `apps/core/models/Localization.py`

Imports: `from apps.core.models._base import *` (pulls `models`, `settings`, `timezone`, `ContentType`).

### 1.1 `Language` — **GLOBAL, no `tenant` FK**

Precedent for a global master: `accounting.Currency`, whose docstring says so explicitly. A language is a
fact about the world, not about a workspace.

| field | type | notes |
|---|---|---|
| `code` | `CharField(max_length=8, unique=True)` | ISO 639-1, e.g. `en`, `fr`, `ar`. |
| `name` | `CharField(max_length=60)` | e.g. `Arabic`. |
| `native_name` | `CharField(max_length=60, blank=True)` | e.g. `العربية`. |
| `is_rtl` | `BooleanField(default=False)` | Bullet 1's RTL support. |
| `is_default` | `BooleanField(default=False)` | The platform fallback language. |
| `is_active` | `BooleanField(default=True)` | |

`Meta.ordering = ["name"]` · `__str__` → `self.name`.

### 1.2 `TimeZone` — **GLOBAL, no `tenant` FK**

| field | type | notes |
|---|---|---|
| `name` | `CharField(max_length=64, unique=True)` | IANA, e.g. `Europe/London`. |
| `label` | `CharField(max_length=100)` | e.g. `London (GMT/BST)`. |
| `utc_offset_minutes` | `IntegerField(default=0)` | **Display only** — see the note below. |
| `observes_dst` | `BooleanField(default=False)` | |
| `is_active` | `BooleanField(default=True)` | |

`Meta.ordering = ["utc_offset_minutes", "name"]` · `__str__` → `self.label`.

**PINNED RULE:** the stored offset is a convenience for sorting and display. Any *actual* conversion must
call `zoneinfo.ZoneInfo(self.name)`. Doing offset arithmetic against `utc_offset_minutes` is how DST bugs
ship, and the model docstring must say so.

### 1.3 `LocaleProfile` — **tenant singleton**

`tenant = models.OneToOneField("core.Tenant", on_delete=models.CASCADE, related_name="locale_profile", db_index=True)`

| field | type | notes |
|---|---|---|
| `language` | `FK("core.Language", on_delete=SET_NULL, null=True, blank=True, related_name="+")` | |
| `base_currency` | `FK("accounting.Currency", on_delete=SET_NULL, null=True, blank=True, related_name="+")` | Bullet 2's base currency. |
| `time_zone` | `FK("core.TimeZone", on_delete=SET_NULL, null=True, blank=True, related_name="+")` | Bullet 5's tenant half. |
| `date_format` | `CharField(max_length=40, default="dd/MM/yyyy")` | |
| `time_format` | `CharField(max_length=40, default="HH:mm")` | |
| `number_format` | `CharField(max_length=40, default="#,##0.00")` | |
| `address_format` | `TextField(blank=True)` | Free text, multi-line. |
| `first_day_of_week` | `PositiveSmallIntegerField(default=1)` | 1 = Monday … 7 = Sunday (ISO). |
| `notes` | `TextField(blank=True)` | |
| `updated_at` | `DateTimeField(auto_now=True)` | |

`Meta.ordering = ["tenant__name"]` · `__str__` → `"Locale · %s" % self.tenant`.

**PINNED:** no `created_at` — a singleton that is `get_or_create`d does not need one, and 0.10's
`BusinessCalendar` (the same singleton shape) has only `updated_at`.

### 1.4 `UserLocalePreference` — **per-user singleton**

| field | type | notes |
|---|---|---|
| `tenant` | `FK("core.Tenant", on_delete=CASCADE, related_name="user_locale_preferences", db_index=True)` | Present so the row is tenant-scoped like every other model. |
| `user` | `OneToOneField(settings.AUTH_USER_MODEL, on_delete=CASCADE, related_name="locale_preference")` | |
| `language` | `FK("core.Language", SET_NULL, null=True, blank=True, related_name="+")` | |
| `time_zone` | `FK("core.TimeZone", SET_NULL, null=True, blank=True, related_name="+")` | |
| `date_format` | `CharField(max_length=40, blank=True)` | **Blank = inherit the tenant's.** |
| `updated_at` | `DateTimeField(auto_now=True)` | |

`Meta.ordering = ["user__email"]` · `__str__` → `"Locale pref · %s" % self.user`.

### 1.5 `StatutoryRule` — **tenant**

| field | type | notes |
|---|---|---|
| `tenant` | `FK("core.Tenant", CASCADE, related_name="statutory_rules", db_index=True)` | |
| `name` | `CharField(max_length=150)` | |
| `jurisdiction` | `CharField(max_length=120, blank=True)` | **Free text** — matches `core.Holiday.region`; a closed country list would be wrong for a global product. |
| `tax_code` | `FK("accounting.TaxCode", SET_NULL, null=True, blank=True, related_name="statutory_rules")` | The rate this rule attaches to. |
| `e_invoicing_required` | `BooleanField(default=False)` | |
| `e_invoicing_scheme` | `CharField(max_length=12, choices=E_INVOICING_CHOICES, default="none")` | |
| `statutory_report` | `CharField(max_length=150, blank=True)` | e.g. `VAT Return (MTD)`. |
| `effective_from` | `DateField()` | |
| `effective_to` | `DateField(null=True, blank=True)` | |
| `is_active` | `BooleanField(default=True)` | |
| `notes` | `TextField(blank=True)` | |
| `created_at` / `updated_at` | `DateTimeField(auto_now_add=True)` / `(auto_now=True)` | |

**`E_INVOICING_CHOICES` (exact values):**
`[("none", "Not required"), ("peppol", "PEPPOL / EU"), ("sdi", "Italy SDI"), ("cfdi", "Mexico CFDI"), ("gst_irn", "India GST IRN"), ("other", "Other")]`

`Meta.ordering = ["jurisdiction", "name"]`
`unique_together = ("tenant", "name")`
`indexes = [models.Index(fields=["tenant", "is_active"], name="statrule_tenant_active_idx")]`
`__str__` → `self.name`

`clean()`: raise `ValidationError` when `effective_to` is set and `< effective_from`.
**No auto-number** — none of the five entities is a document anyone quotes in conversation, and this
avoids the prefix-collision surface entirely.

---

## 2. Forms — `apps/core/forms/Localization.py`

Imports: `from apps.core.forms._common import *` (gives `forms`, `TenantModelForm`).

**Only three forms.** There is deliberately **no `LanguageForm` and no `TimeZoneForm`**: their pages are
read-only (see §3.1), and shipping a form no view calls is dead code a reviewer will correctly flag.

| form | `Meta.model` | `Meta.fields` (exact order) |
|---|---|---|
| `LocaleProfileForm` | `LocaleProfile` | `["language", "base_currency", "time_zone", "date_format", "time_format", "number_format", ` `"address_format", "first_day_of_week", "notes"]` |
| `UserLocalePreferenceForm` | `UserLocalePreference` | `["language", "time_zone", "date_format"]` |
| `StatutoryRuleForm` | `StatutoryRule` | `["name", "jurisdiction", "tax_code", "e_invoicing_required", ` `"e_invoicing_scheme", "statutory_report", "effective_from", "effective_to", "is_active", "notes"]` |

**Excluded everywhere:** `tenant`, `updated_at`, `created_at`, `user`.

> **AS-BUILT CORRECTION (§2).** The first draft of this contract specified `clean_first_day_of_week`,
> `clean_date_format` / `clean_time_format` / `clean_number_format` and `StatutoryRuleForm.clean()`.
> All four are **dead code as form methods**, and none were built:
> * `first_day_of_week` carries `choices=`, so the form field is a `TypedChoiceField` and an
>   out-of-range day is already rejected — the check could never fire.
> * The format-pattern rule and both `StatutoryRule` cross-field rules were moved into the **models'**
>   `clean()`. `ModelForm._post_clean()` calls `instance.full_clean()`, so a model-level rule is
>   enforced on every form anyway — a `clean_<field>` copy is a second copy that cannot fire on its own.
>   One rule, one place, and the seeder and the admin are covered by the same rule.
>
> So the built forms are **`Meta`-only**, and the validation lives in `LocaleProfile.clean()` /
> `UserLocalePreference.clean()` / `StatutoryRule.clean()` (see §1). `FORMAT_TOKEN_RE` is exported from
> `apps.core.models.Localization` and imported by nothing else — the model is its only consumer.

---

## 3. Views — `apps/core/views/Localization.py`

### 3.0 Import trap (this file will 500 without it)

`apps/core/views/_common.py` star-exports **only**: `get_user_model`, `login_required`, `JsonResponse`,
`get_object_or_404`, `render`, `require_POST`, `crud_create`, `crud_delete`, `crud_detail`, `crud_edit`,
`crud_list`, `run_search`, `tenant_admin_required`, `Party`, `User`.

It does **NOT** export `messages`, `redirect`, `timezone`, `Count`, `Max`, `Q` or `Sum`. This file must
import them explicitly:
```python
from django.contrib import messages
from django.db.models import Max
from django.shortcuts import redirect
from django.utils import timezone
```
(Skipping this is the documented cause of a `NameError: name 'Q' is not defined` on every non-empty `?q=`.)

### 3.1 The GLOBAL-registry rule (pinned)

`language_list` and `timezone_list` are the only two views in this sub-module that are **not**
tenant-scoped, because `Language` and `TimeZone` have no `tenant` FK:

- decorated `@login_required` (NOT `@tenant_admin_required` — that decorator reads `request.tenant`),
- **no** `filter(tenant=...)`, and
- **no create / edit / delete routes at all.** A write would need a platform-admin gate this repo does
  not have; inventing one is out of scope. The registry is populated by the seeder and the page says so.

They must also work for a tenant-less superuser (`request.tenant is None`) — they are global.

### 3.2 View list, decorators and context keys (PINNED)

| view | decorator | template | context keys |
|---|---|---|---|
| `language_list` | `@login_required` | `core/language/list.html` | `object_list`, `page_obj`, `q` (via `crud_list` with `search_fields=["code","name","native_name"]`, `filters=[("rtl","is_rtl",False),("active","is_active",False)]`, `extra_context={"rtl_choices":[("True","Right-to-left"),("False","Left-to-right")], "active_choices":[("True","Active"),("False","Inactive")]}`) |
| `timezone_list` | `@login_required` | `core/timezone/list.html` | same three + `extra_context={"dst_choices":[("True","Observes DST"),("False","No DST")], "active_choices":[...]}` with `search_fields=["name","label"]`, `filters=[("dst","observes_dst",False),("active","is_active",False)]` |
| `locale_profile_edit` | `@tenant_admin_required` | `core/localeprofile/form.html` | `form`, `obj`, `is_edit=True` |
| `user_locale_edit` | `@login_required` | `core/userlocale/form.html` | `form`, `obj` |
| `statutory_rule_list` | `@tenant_admin_required` | `core/statutoryrule/list.html` | `object_list`, `page_obj`, `q`, `scheme_choices`, `active_choices` |
| `statutory_rule_create` | `@tenant_admin_required` | `core/statutoryrule/form.html` | `form`, `is_edit=False` |
| `statutory_rule_detail` | `@tenant_admin_required` | `core/statutoryrule/detail.html` | `obj` |
| `statutory_rule_edit` | `@tenant_admin_required` | `core/statutoryrule/form.html` | `form`, `obj`, `is_edit=True` |
| `statutory_rule_delete` | `@require_POST` **above** `@tenant_admin_required` | — | redirect to `core:statutory_rule_list` |
| `localization_board` | `@tenant_admin_required` | `core/localizationboard.html` | see §3.3 |
| `localization_overview` | `@tenant_admin_required` | `core/localizationoverview.html` | see §3.4 |

**Decorator order is pinned by 7.7's ruling:** `@require_POST` goes **above** `@tenant_admin_required`
so a member's GET gets **405**, not 403.

**`request.tenant is None` branch** (both computed views): `messages.info(request, "...")` then
`redirect("dashboard:home")` — exactly as 0.13's `integration_board` does. Never `filter(tenant=None)`.

`locale_profile_edit` / `user_locale_edit` are hand-written (not `crud_*`) because both are **singletons**.

> **AS-BUILT CORRECTION (§3.2).** This contract specified `get_or_create` on both. The build instead
> **reads** the row (`...objects.filter(...).first()`, possibly `None`) and creates only on a valid
> POST, because `get_or_create` on a GET inserts a row merely because somebody opened the page — a
> write with no user intent behind it.
> Because `tenant` (and, for the user row, `user`) is not a form field, both views use
> `form.save(commit=False)`, set the missing keys, then `save()`. A plain `form.save()` would attempt
> to insert a NULL tenant on the create path and raise `IntegrityError`.
> `user_locale_edit` additionally takes the `request.tenant is None` branch with an informational
> message: `UserLocalePreference.tenant` is NOT NULL, so a tenant-less superuser cannot own one.

### 3.3 `localization_board` context keys (COMPUTED — no table)

Reads the **real** `accounting.ExchangeRate` rows. One query, grouped in Python (ordered so the first row
per currency is the newest — no N+1, no subquery-tie bug).

```python
STALE_RATE_DAYS = 7   # module-level constant

rate_rows = []        # [{"currency": Currency, "rate": Decimal, "rate_date": date,
                      #   "source": str, "age_days": int}, ...]  newest-first per currency
```

| key | value |
|---|---|
| `profile` | `LocaleProfile` or `None` |
| `base_currency` | `Currency` or `None` |
| `rate_rows` | list as above, ordered by `currency.code` |
| `rate_count` | `len(rate_rows)` |
| `stale_rate_count` | rows with `age_days > STALE_RATE_DAYS` |
| `currencies_without_rates` | active `accounting.Currency` count − `rate_count` |
| `stale_after_days` | `STALE_RATE_DAYS` (so the template never hardcodes it) |
| `timezone_count` / `dst_zone_count` | active global zones / of those, `observes_dst=True` |
| `language_count` / `rtl_count` | active languages / of those, `is_rtl=True` |
| `statutory_count` | active `StatutoryRule` for the tenant |
| `e_invoicing_count` | active rules with `e_invoicing_required=True` |
| `exchange_rate_url` / `tax_code_url` | `reverse("accounting:exchange_rate_list")` / `reverse("accounting:tax_code_list")` |

### 3.4 `localization_overview` context keys (COMPUTED hub)

| key | value |
|---|---|
| `profile` | `LocaleProfile` or `None` |
| `has_profile` | `bool` |
| `my_pref` | the actor's `UserLocalePreference` or `None` |
| `language_count`, `rtl_count`, `timezone_count`, `dst_zone_count` | as §3.3 |
| `statutory_count`, `e_invoicing_count` | as §3.3 |
| `user_pref_count` | `UserLocalePreference.objects.filter(tenant=tenant).count()` |
| `recent_rules` | `StatutoryRule.objects.filter(tenant=tenant).order_by("-created_at")[:5]` |

---

## 4. URLs — appended to the flat `apps/core/urls.py`

Literals before `<int:pk>`. `app_name = "core"` (already set).

| path | view | name |
|---|---|---|
| `localization/` | `localization_overview` | `localization_overview` |
| `localization/board/` | `localization_board` | `localization_board` |
| `localization/languages/` | `language_list` | `language_list` |
| `localization/time-zones/` | `timezone_list` | `timezone_list` |
| `localization/profile/` | `locale_profile_edit` | `locale_profile_edit` |
| `localization/my-settings/` | `user_locale_edit` | `user_locale_edit` |
| `localization/statutory/` | `statutory_rule_list` | `statutory_rule_list` |
| `localization/statutory/add/` | `statutory_rule_create` | `statutory_rule_create` |
| `localization/statutory/<int:pk>/` | `statutory_rule_detail` | `statutory_rule_detail` |
| `localization/statutory/<int:pk>/edit/` | `statutory_rule_edit` | `statutory_rule_edit` |
| `localization/statutory/<int:pk>/delete/` | `statutory_rule_delete` | `statutory_rule_delete` |

---

## 5. Templates

| path | notes |
|---|---|
| `templates/core/language/list.html` | reference list; **no Actions column** (read-only) |
| `templates/core/timezone/list.html` | same |
| `templates/core/localeprofile/form.html` | singleton edit |
| `templates/core/userlocale/form.html` | singleton edit |
| `templates/core/statutoryrule/list.html` | full list: search + filters + pagination + Actions |
| `templates/core/statutoryrule/form.html` | shared create/edit |
| `templates/core/statutoryrule/detail.html` | detail |
| `templates/core/localizationboard.html` | computed board |
| `templates/core/localizationoverview.html` | computed hub |

All extend `base.html` and use **only** theme.css classes that exist. Before using any modifier, run:
`grep -oE '\.(badge-[a-z]+|stat-icon(\.[a-z]+)?|text-[a-z]+)' static/css/theme.css | sort -u`
`.alert*` does **not** exist — the inline-notice pattern is `<p class="text-muted">`.

---

## 6. `LIVE_LINKS["0.15"]` — exact NavERP.md bullet names

```python
"0.15": {
    "Multi-Language & Translation": "core:language_list",            # bullet 1
    "Multi-Currency & Exchange Rates": "core:localization_board",    # bullet 2 (points at accounting)
    "Regional Formats": "core:locale_profile_edit",                  # bullet 3
    "Tax & Statutory Configuration": "core:statutory_rule_list",     # bullet 4 (points at accounting)
    "Time Zone Management": "core:timezone_list",                    # bullet 5
    "Localization Overview": "core:localization_overview",           # extra
    "My Regional Settings": "core:user_locale_edit",                 # extra
},
```

---

## 7. Seeder — `apps/core/management/commands/seed_core.py`

- `_seed_localization_globals()` — **Language + TimeZone only**, called **once** in `handle()` *outside*
  the tenant loop (they are global). Guarded by `.exists()`, not per tenant. Seeds ~8 languages
  (`en` default, `ar` RTL, `he` RTL, `fr`, `de`, `es`, `pt`, `zh-hans`) and ~10 IANA zones spanning
  DST and non-DST.
- `_seed_localization(tenant)` — the tenant half. **Per-entity guards**, never a tenant-wide one
  (a tenant-wide guard is the documented defect that stranded every later entity):
  - `LocaleProfile.objects.get_or_create(tenant=tenant, defaults={...})`
  - `if not StatutoryRule.objects.filter(tenant=tenant).exists(): ...` → 2–3 rules, one with
    `e_invoicing_required=True` + `e_invoicing_scheme="peppol"`, one attached to a real
    `accounting.TaxCode` when one exists (`TaxCode.objects.filter(tenant=tenant).first()`).

Run twice; the second run must create nothing.

---

## 8. Out of scope — stated, not omitted

- **No translation table and no `.po` files.** Strings live in Django's `gettext` layer; `USE_I18N=True`
  with no `LOCALE_PATHS` is the as-built truth. `Language` registers *which* languages are offered.
- **No rate fetching, no scheduler.** `accounting.ExchangeRate.source` records `manual`/`feed`; nothing
  in this repo fetches a rate, and 0.13's `SyncSchedule` already records the intention.
- **No timezone conversion helper applied to existing views.** `TimeZone` is a registry; converting every
  date render across 20 apps is a separate, much larger change and is explicitly not attempted here.
