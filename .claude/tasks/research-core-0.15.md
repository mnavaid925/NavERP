# Research — Sub-module 0.15: Localization & Regional Settings (Module 0, `core`)

Domain surveyed: **localization / regional configuration** as a *platform* concern rather than a domain
feature — language and RTL, per-tenant and per-user regional formats, time-zone handling, and the
statutory/e-invoicing layer that sits on top of tax. The commercial question every product answers is
"what does a tenant in a different country need before the app is usable for them?" — and the answer is
always a small number of **registries plus one profile row**, never a second engine.

---

## Repo state checked first

**`LIVE_LINKS` built so far in Module 0** (`apps/core/navigation.py`, read at run time):
`0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9 0.10 0.11 0.12 0.13 0.14` — 14 keys. **`0.15` is absent**, as are
`0.16`–`0.21`. 0.15 is the next unbuilt sub-module and may FK anything from 0.1–0.14.

**`config/settings.py` (read, not assumed):** `LANGUAGE_CODE = "en-us"`, `TIME_ZONE = "UTC"`,
`USE_I18N = True`, `USE_TZ = True`. **There is no `LANGUAGES`, no `LOCALE_PATHS`, and no `locale/`
directory.** So the app is i18n-*enabled* by Django defaults but has no language packs of its own — an
important honesty constraint (see the ownership call below).

---

## Spine entities VERIFIED to exist

`grep -rn "^class \w+" apps/core/models/ apps/accounting/models/ apps/tenants/models/`

| Entity | Where | What 0.15 gets from it — and must NOT re-declare |
|---|---|---|
| `accounting.Currency` | `apps/accounting/models/GeneralLedger/Currencies.py:6` | **The currency master already exists.** Verified fields: `code` (max_length=3, **unique**), `name`, `symbol`, `is_active`. It is **GLOBAL — no `tenant` FK**, with an explicit docstring saying so ("shared across all tenants … exactly as the intended ERD treats currencies as a shared reference master"). 0.15 must therefore not create a second currency table, and must not "fix" it by adding a tenant FK. |
| `accounting.ExchangeRate` | `.../GeneralLedger/ExchangeRates.py:5` | **The FX rate register already exists.** Verified fields: `tenant` (via `TenantOwned`), `currency` → `accounting.Currency`, `rate_date`, `rate` (18,8), `source` ∈ {`manual`, `feed`}, `unique_together = ("tenant","currency","rate_date")`, index `acc_fx_tenant_date_idx`. Bullet 2's "transaction currencies and rate updates" is therefore **already built**; what is missing is only the tenant's *base* currency and any *schedule* concept. |
| `accounting.TaxCode` | `.../Tax/TaxCodes.py:6` | **The tax master already exists.** Verified fields: `tenant`, `name`, `jurisdiction`, `tax_type` ∈ {`sales`,`vat`,`gst`,`use`}, `rate_pct` (6,3), `payable_account` → `accounting.GLAccount`, `is_active`. Bullet 4's "region-specific tax rules" is **already built**; only e-invoicing and the statutory-report registry are missing. |
| `core.BusinessCalendar.timezone_name` | `apps/core/models/Calendar.py:17` | 0.10 already stores an **IANA name as free text** for the *working-day* calendar (`help_text="IANA name, e.g. 'Europe/London'."`). This is the **business calendar's** zone, not the tenant's display zone. 0.15 must not re-declare it; the relationship is "two different zones, both legitimate". |
| `core.SettingDefinition` / `SettingValue` | `apps/core/models/Setting.py:16,52` | 0.10's generic key/value settings engine, whose own docstring already names "currency display" as an example. 0.15 must **not** turn this sub-module into a pile of setting definitions: a language is not a string, it is a row with an RTL flag; a time zone is not a string, it is a row with an offset and a DST flag. Registry ≠ setting. |
| `core.Holiday.region` | `apps/core/models/Calendar.py:51` | A free-text `region` already exists on holidays — evidence the repo already thinks in regions, and the reason `StatutoryRule.jurisdiction` should be free text too (a closed country list would be wrong for a global product). |
| `core.SyncSchedule` | `apps/core/models/Integration.py:219` | 0.13 already ships a **recorded sync intention** registry with `FREQUENCY_CHOICES` ∈ {manual, hourly, daily, weekly} and `transport` ∈ {api, sftp, file, edi, webhook}, docstring: "**Nothing runs it** — the repo has no scheduler." Bullet 2's "scheduled rate updates" must **reuse this** rather than grow a second schedule table — and must say plainly that it is a record, not a job. |
| `accounting.GLAccount`, `core.Tenant`, `core.AuditLog`, `accounts.User` | — | Standard FKs. `accounts.User` was checked for a `timezone`/`locale` field: **there is none** (fields are `tenant, party, role, email, username, first_name, last_name, is_tenant_admin, status, is_active, is_staff, date_joined`). |

**Verified NOT to exist** (grep returns nothing anywhere in `apps/`):
`Language`, `TimeZone`, `Locale`, `LocaleProfile`, `RegionalSetting`, `LocalizationProfile`,
`StatutoryRule`, `EInvoicingConfig`, `DateFormat`, `NumberFormat`. **There is no language registry, no
time-zone registry and no regional-format model in the repo.**

---

## What the market actually ships (the 6–10 products surveyed)

| Product | How it does localization / regional settings | What 0.15 should take from it |
|---|---|---|
| **SAP S/4HANA** | Country templates + "localization" as a *delivered content* layer per country; currency is a global ISO table; the **company code** carries currency, fiscal year variant, and a country key; date/number formats come from the **user master**. | The **three-scope split**: global registry (currency/language/tz) → tenant profile → user override. 0.15 is exactly this shape. |
| **Oracle Fusion Cloud ERP** | `General Ledger` owns currencies + daily rates; **legal entity / primary ledger** carries the base currency; tax is a separate `Tax` module with **regimes, jurisdictions and rates**; e-invoicing is a country-specific add-on. | Base currency belongs on a **tenant profile row**, not on each transaction. `TaxCode.jurisdiction` (already built) *is* Oracle's "jurisdiction". |
| **NetSuite OneWorld** | Multi-subsidiary + multi-currency; a **base currency** per subsidiary; **currency exchange rates** entered per (currency, date); per-user **locale + time zone + date/number format** preferences. | The clearest confirmation that the **per-user** preference half is a real product requirement, not padding — NetSuite puts locale/tz/format on the *user*, with the subsidiary supplying the default. |
| **Microsoft Dynamics 365 F&O** | "Localization" is a **country context** (`ISOCode`, `CountryRegionCodes`) plus per-country feature layers; number sequences and **date/time/number formats** are per-user with a legal-entity default. | Country/region is an attribute, not a model. Formats are **format strings**, not an enum of formats. |
| **Workday** | Localization is country-based payroll/statutory content; each worker has a **locale** and a **time zone**; statutory reporting is country-specific. | Statutory content is a **registry you point at**, and per-worker (≈ per-user) locale is first-class. |
| **Salesforce** | **Translation Workbench** for UI labels + **Advanced Currency Management** (dated exchange rates) + per-user **Locale, Language, Time Zone** on the User record. | The per-user triple is literally `Locale`, `Language`, `Time Zone`. 0.15's user row is the same triple. |
| **ServiceNow** | Per-user **language + time zone + date/time format**; translations are delivered as **language packs** (plugin records), and RTL is a per-language flag. | "Language pack" as a **row with an RTL flag** — this is where `Language.is_rtl` comes from. |
| **Stripe / Avalara (tax + e-invoicing)** | Tax is jurisdiction × rate; **e-invoicing is a per-country compliance mode** (e.g. Italy SDI, India GST/IRN) attached to the *entity*, not to the rate. | `StatutoryRule` = jurisdiction + a compliance mode + a report name — separate from `TaxCode`, which is only a rate. This is the bullet-4 gap. |
| **Shopify Markets / Lokalise / Phrase / Crowdin (TMS)** | Markets = per-region currency + language + domain; TMS products treat translation as a **content pipeline** (source strings → locale files → publish), not as DB rows. | **The decisive one.** Nobody stores UI strings in the operational DB — translations are **locale files**. So 0.15 must register languages and say plainly that the strings themselves are Django's `gettext`/`.po` layer, *not* a table. |
| **Unicode CLDR / ICU (the standard underneath all of the above)** | The canonical source of date, time, number, currency and address formats per locale. | Formats should be **pattern strings** (e.g. `dd/MM/yyyy`) and the DST truth should come from the **stdlib `zoneinfo`**, not from a hand-maintained offset table. |

---

## Design implications (what this research forces)

1. **Two GLOBAL registries, one tenant profile, one user override, one statutory registry — five models,
   and every one of them earns its place.** A "global registry" is not a shortcut: `accounting.Currency`
   set the precedent with an explicit docstring justifying the missing tenant FK, and languages and IANA
   time zones are facts about the world, not about a workspace. Giving them a `tenant` FK would mean every
   workspace re-typing "French".
2. **Bullets 2 and 4 are already half-built by `accounting`.** This is the L36 call the `todo` agent must
   make explicitly: 0.15 **points at** `accounting.Currency` / `accounting.ExchangeRate` /
   `accounting.TaxCode` and builds only the genuinely absent half — the tenant's base currency, the
   statutory/e-invoicing registry, and the formats.
3. **`TimeZone` is a registry *and* the DST answer is `zoneinfo`.** The registry gives a browsable list
   with an explicit `observes_dst` flag (so the UI can warn); the actual conversion must call
   `zoneinfo.ZoneInfo(name)` rather than doing offset arithmetic against the stored `utc_offset_minutes`.
   Storing an offset is a display convenience; treating it as the source of truth is how DST bugs ship.
4. **Never a translation table.** The TMS survey is unanimous and the repo agrees: `USE_I18N=True` with no
   `LOCALE_PATHS` means strings live in `.po` files. `Language` registers *which* languages the workspace
   offers and which are RTL; it must not pretend to store the strings.
5. **`accounting.ExchangeRate` has no schedule — and 0.13 already built one.** "Scheduled rate updates"
   is a `core.SyncSchedule` row (`entity_label="accounting.ExchangeRate"`), not a new model. Duplicating
   it would be the second-engine mistake L36 exists to prevent.
6. **Numbering: no auto-number for 0.15.** None of these five entities is a document a human quotes in
   conversation; a `StatutoryRule` is named, not numbered. This also avoids the prefix-collision surface
   entirely (`accounting` has already taken `FA`, `JE`, `SINV`, …; `core`'s taken set is large).

## Risks specific to this sub-module

- **Global rows and tenant-scoped views.** `Language` and `TimeZone` have no `tenant` FK, so their views
  cannot use `filter(tenant=request.tenant)` and cannot use `crud_edit`/`crud_delete` (both of which
  hard-filter on tenant). They are **read-only reference lists**; a write would need a platform-admin
  gate that this repo does not have. This must be stated in the contract, not discovered at review time.
- **`LocaleProfile` / `UserLocalePreference` are OneToOne singletons**, so the house "list + detail +
  create + edit + delete" CRUD rule does not literally apply — the correct shape is a single
  **edit** page per scope, exactly as `core.BusinessCalendar` (0.10) and 0.12's `my_preferences` do.
- **`request.tenant is None` (the superuser).** Every tenant-scoped view in 0.15 must take the 0.13
  branch (`messages.info` + redirect to `dashboard:home`) rather than 500 on `filter(tenant=None)`
  returning an empty set and then indexing it.
- **Format strings are free text and must be validated.** A pattern like `dd/MM/yyyy` is fine; an
  arbitrary string is a template-injection-ish foot-gun when later formatted. Validate with an
  allow-list of token characters.
