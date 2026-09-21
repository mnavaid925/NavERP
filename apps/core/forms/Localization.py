"""core — 0.15 forms (localization & regional settings).

**Three forms, and deliberately no more.**

* There is **no `LanguageForm` and no `TimeZoneForm`.** Those two registries are GLOBAL (no `tenant`
  FK) and their pages are read-only, because a write to them would need a platform-admin gate this repo
  does not have. A form no view calls is dead code.
* The format-pattern and date-range rules live in the **models'** `clean()`, not here. A `ModelForm`
  runs `instance.full_clean()` in `_post_clean`, so a model-level rule is already enforced on every
  form — re-stating it as a `clean_<field>` would be a second copy that can never fire on its own.
  One rule, one place, and the seeder and the admin get it too.

These classes exist to carry `Meta.fields` (the pinned field list) and to inherit `TenantModelForm`,
which applies the design-system widget classes and scopes any tenant-owned FK queryset.
"""
from apps.core.forms._common import *  # noqa: F401,F403
from apps.core.models import LocaleProfile, StatutoryRule, UserLocalePreference


class LocaleProfileForm(TenantModelForm):
    """The workspace's localization profile. A singleton — edited, never created or deleted."""

    class Meta:
        model = LocaleProfile
        fields = ["language", "base_currency", "time_zone", "date_format", "time_format",
                  "number_format", "address_format", "first_day_of_week", "notes"]


class UserLocalePreferenceForm(TenantModelForm):
    """One person's regional overrides. `date_format` blank means "inherit the workspace's"."""

    class Meta:
        model = UserLocalePreference
        fields = ["language", "time_zone", "date_format"]


class StatutoryRuleForm(TenantModelForm):
    """A jurisdiction's statutory/e-invoicing obligation.

    `tax_code` is scoped to the tenant automatically by `TenantModelForm`, because
    `accounting.TaxCode` carries a `tenant` field. `language`, `time_zone` and `base_currency` do not,
    so those querysets stay global — which is the point of a registry.
    """

    class Meta:
        model = StatutoryRule
        fields = ["name", "jurisdiction", "tax_code", "e_invoicing_required", "e_invoicing_scheme",
                  "statutory_report", "effective_from", "effective_to", "is_active", "notes"]
