# Test contract — `core` 0.15 Localization & Regional Settings

**Created:** 2026-09-22 · **Test subslug:** `localization` · **BASE:** `35cde520`
**Lanes:** four (`models`, `forms`, `views`, `security`) — the app has models and forms, so all four apply.
**Files:** `apps/core/tests/test_localization_{models,forms,views,security}.py`

Every test function is named `test_localization_*` and every module-level helper `_localization_*`, so the
next sub-module appending nearby cannot shadow them.

---

## Fixtures — appended to `apps/core/tests/conftest.py` (APPEND-ONLY, L43)

The root `conftest.py` already provides `tenant_a`, `tenant_b`, `admin_user`, `member_user`, `client_a`,
`client_b`, `member_client`, `client`. `apps/core/tests/conftest.py` currently adds only `party_a` /
`party_b`. Append **below** those, never rewriting them.

| fixture | creates | purpose |
|---|---|---|
| `localization_languages` | 3 global `Language`: `en` (default, LTR), `ar` (RTL), `he` (RTL) | RTL + default flags; global, so **no tenant** |
| `localization_zones` | 3 global `TimeZone`: `UTC` (+0, no DST), `Asia/Kolkata` (+330, no DST), `Europe/London` (+0, DST) | the `offset_display` and DST paths |
| `localization_profile` | 1 `LocaleProfile` on `tenant_a`, language=`en`, time_zone=`UTC`, defaults | the tenant singleton |
| `localization_rules` | 2 `StatutoryRule` on `tenant_a` (`EU VAT e-invoicing` / peppol / required; `US sales tax filing` / none) + 1 on `tenant_b` | the `(tenant, name)` constraint and tenant isolation |
| `localization_statutory_payload` | a dict of valid POST fields | shared by the create/edit view tests |

**Figures that matter:** `Language` and `TimeZone` are **global** — a fixture creating 3 of each makes the
global count 3 *plus whatever the dev DB holds*, so **every count assertion must be scoped** (`filter(code=…)`,
`filter(name=…)`) or computed relative to a baseline captured at test start. Never assert `Language.objects.count() == 3`.

---

## Lanes

### `test_localization_models.py`
| # | test | expectation |
|---|---|---|
| 1 | `Language.code` unique | a duplicate `code` raises `IntegrityError` |
| 2 | `Language` has no `tenant` field | `"tenant" not in [f.name for f in Language._meta.fields]` — the global-registry contract, pinned so a later "fix" cannot add one |
| 3 | `TimeZone.offset_display` formats minutes | `0 → "UTC+00:00"`, `330 → "UTC+05:30"`, `-480 → "UTC-08:00"`, `-30 → "UTC-00:30"` |
| 4 | `TimeZone.name` unique | duplicate raises `IntegrityError` |
| 5 | `LocaleProfile` is a tenant singleton | a second row for the same tenant raises `IntegrityError` |
| 6 | `LocaleProfile.clean` rejects a bad format | `date_format="dd/MM/yyyy<script>"` raises `ValidationError` on `full_clean()` |
| 7 | `LocaleProfile.clean` accepts a good format | `"#,##0.00"` passes `full_clean()` |
| 8 | `StatutoryRule.clean` rejects an inverted date range | `effective_to < effective_from` raises `ValidationError` keyed `effective_to` |
| 9 | `StatutoryRule.clean` rejects e-invoicing with no scheme | `e_invoicing_required=True, e_invoicing_scheme="none"` raises `ValidationError` keyed `e_invoicing_scheme` |
| 10 | `(tenant, name)` is unique per tenant | the same `name` in `tenant_b` is allowed while `tenant_a`'s duplicate raises |

### `test_localization_forms.py`
| # | test | expectation |
|---|---|---|
| 1 | **`StatutoryRuleForm` rejects a duplicate name (the C1 regression test)** | a form bound with an existing `tenant_a` name is **invalid**, with the message on `name` — this is the test that would have caught the 500 |
| 2 | `StatutoryRuleForm` allows the same name in another tenant | same name, `tenant=tenant_b` → valid |
| 3 | `StatutoryRuleForm` allows an **edit that keeps its own name** | `instance=<existing rule>`, same name → **valid** (the guard must exclude `self.instance.pk`) |
| 4 | `StatutoryRuleForm` accepts a genuinely new name | valid |
| 5 | `StatutoryRuleForm` excludes `tenant` | `"tenant" not in form.fields` |
| 6 | `StatutoryRuleForm.tax_code` is tenant-scoped | the queryset contains only `tenant_a`'s tax codes |
| 7 | `LocaleProfileForm` excludes `tenant` and `updated_at` | neither is a form field |
| 8 | `UserLocalePreferenceForm` excludes `tenant` and `user` | neither is a form field |
| 9 | `UserLocalePreferenceForm.date_format` is optional | `required is False` — blank means inherit |

### `test_localization_views.py`
| # | test | expectation |
|---|---|---|
| 1 | `language_list` renders | `client_a` → 200, `core/language/list.html`, contains the seeded language name |
| 2 | `timezone_list` renders the formatted offset | 200, contains `UTC+05:30` and **not** `UTC+330` |
| 3 | `locale_profile_edit` GET does **not** create a row | count unchanged after GET — the deliberate "no write without intent" behaviour |
| 4 | `locale_profile_edit` POST creates then updates one row | two POSTs → count stays 1, value changed |
| 5 | `user_locale_edit` POST writes the **actor's** row | as a member, the row's `user` is the member and its `tenant` is the member's tenant |
| 6 | `statutory_rule_list` renders + filters | 200; `?scheme=peppol` narrows to the e-invoicing rule |
| 7 | `statutory_rule_create` **returns 200 + a form error on a duplicate name** | the C1 regression at the view layer — never 500 |
| 8 | `statutory_rule_create` saves a valid rule with the session tenant | 302, row exists, `tenant == tenant_a` even when a foreign `tenant` is posted |
| 9 | `statutory_rule_edit` updates | 302, change persisted |
| 10 | `statutory_rule_detail` renders | 200, contains the rule name |
| 11 | `localization_board` renders the FX rows | 200; the seeded rate appears; `stale_after_days` is in the context |
| 12 | `localization_overview` renders | 200; `has_profile` True for `tenant_a` |
| 13 | both global lists work for a tenant-less superuser | a `tenant=None` superuser gets **200 with content** on `language_list`/`timezone_list` |

### `test_localization_security.py`
| # | test | expectation |
|---|---|---|
| 1 | anonymous → login redirect | every one of the 11 routes → 302 with `/login` in `Location` |
| 2 | member → 403 on the admin-gated views | `statutory_rule_*`, `locale_profile_edit`, `localization_board`, `localization_overview` → 403 |
| 3 | member → 200 on the two global registries | `language_list`, `timezone_list` → 200 (global, read-only, by design) |
| 4 | member → 200 on their own preference page | `user_locale_edit` → 200 |
| 5 | **`statutory_rule_delete` GET → 405, not 403** | locks in 7.7's decorator-order ruling |
| 6 | cross-tenant IDOR on detail/edit/delete | `admin_acme` on a `tenant_b` pk → **404**, and the `tenant_b` row is **unchanged** afterwards |
| 7 | `statutory_rule_create` cannot be given a foreign tenant | POST with `tenant=<tenant_b pk>` → the saved row's tenant is `tenant_a` |
| 8 | tenant isolation of the list | `client_a`'s list contains no `tenant_b` rule |
| 9 | the member's preference POST cannot write the admin's row | the admin's `UserLocalePreference` is untouched |
| 10 | no 500 on junk params | `?scheme=zzz`, `?rtl=abc`, `?dst=nope`, `?page=999` → 200 |

---

## Gate

```bash
venv\Scripts\python.exe -m pytest apps/core/tests -k localization --nomigrations -p no:cacheprovider
```
then the **full unfiltered** `apps/core/tests` suite, then `temp/audit_integrity.py` (all 6 checks).

**Always iterate with `--nomigrations`** (~84–186× faster). The final phase gate is one run **without** it.

## Out of scope
- **Query-count assertions** — lane 4 already measured every view; pinning counts here would make an
  unrelated optimisation fail this lane. `localization_board`'s exact 2-query shape is asserted by lane 4's
  own probe, not here.
- **Template markup assertions beyond the template name** — cosmetic edits would break them.
