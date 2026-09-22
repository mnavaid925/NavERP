"""Tests for the 0.15 localization models.

The two interesting things here are the two GLOBAL registries (which must never grow a `tenant` FK) and
the two `clean()` rule sets, which are the only place the format-pattern and cross-field rules live —
`ModelForm._post_clean` runs them, so testing them at the model layer covers the forms too.
"""
import datetime

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

pytestmark = pytest.mark.django_db


class TestLocalizationGlobalRegistries:
    def test_localization_language_code_is_unique(self, localization_languages):
        from apps.core.models import Language
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Language.objects.create(code="en", name="Duplicate English")

    def test_localization_language_has_no_tenant_field(self):
        """Pinned so a later "fix" cannot give the registry a tenant FK.

        A language is a fact about the world, not about a workspace — the same posture
        `accounting.Currency` takes. Adding a tenant FK here would mean every workspace re-typing "French".
        """
        from apps.core.models import Language
        assert "tenant" not in [f.name for f in Language._meta.fields]

    def test_localization_timezone_has_no_tenant_field(self):
        from apps.core.models import TimeZone
        assert "tenant" not in [f.name for f in TimeZone._meta.fields]

    def test_localization_timezone_name_is_unique(self, localization_zones):
        from apps.core.models import TimeZone
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                TimeZone.objects.create(name="UTC", label="Duplicate UTC")

    @pytest.mark.parametrize("minutes,expected", [
        (0, "UTC+00:00"),
        (330, "UTC+05:30"),
        (-480, "UTC-08:00"),
        (-30, "UTC-00:30"),
        (60, "UTC+01:00"),
        (540, "UTC+09:00"),
    ])
    def test_localization_timezone_offset_display(self, minutes, expected):
        """`utc_offset_minutes` is minutes; the column must not print `UTC+330` (which reads as hours)."""
        from apps.core.models import TimeZone
        assert TimeZone(utc_offset_minutes=minutes).offset_display == expected


class TestLocalizationLocaleProfile:
    def test_localization_locale_profile_is_a_tenant_singleton(self, localization_profile, tenant_a):
        from apps.core.models import LocaleProfile
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                LocaleProfile.objects.create(tenant=tenant_a)

    def test_localization_locale_profile_rejects_a_bad_format(self, tenant_a):
        from apps.core.models import LocaleProfile
        profile = LocaleProfile(tenant=tenant_a, date_format="dd/MM/yyyy<script>")
        with pytest.raises(ValidationError) as exc:
            profile.full_clean()
        assert "date_format" in exc.value.message_dict

    def test_localization_locale_profile_rejects_a_percent_token(self, tenant_a):
        """`%` is excluded by FORMAT_TOKEN_RE, so no `strftime`-injection shape can be stored."""
        from apps.core.models import LocaleProfile
        profile = LocaleProfile(tenant=tenant_a, number_format="%Y-%m-%d")
        with pytest.raises(ValidationError):
            profile.full_clean()

    def test_localization_locale_profile_accepts_a_good_format(self, tenant_a):
        from apps.core.models import LocaleProfile
        profile = LocaleProfile(tenant=tenant_a, date_format="dd/MM/yyyy",
                                number_format="#,##0.00", time_format="HH:mm")
        profile.full_clean()   # must not raise

    def test_localization_locale_profile_first_day_is_a_choice(self, tenant_a):
        from apps.core.models import LocaleProfile
        profile = LocaleProfile(tenant=tenant_a, first_day_of_week=9)
        with pytest.raises(ValidationError) as exc:
            profile.full_clean()
        assert "first_day_of_week" in exc.value.message_dict


class TestLocalizationStatutoryRule:
    def test_localization_statutory_rule_rejects_inverted_dates(self, tenant_a):
        from apps.core.models import StatutoryRule
        rule = StatutoryRule(
            tenant=tenant_a, name="Inverted", effective_from=datetime.date(2026, 6, 1),
            effective_to=datetime.date(2026, 1, 1),
        )
        with pytest.raises(ValidationError) as exc:
            rule.full_clean()
        assert "effective_to" in exc.value.message_dict

    def test_localization_statutory_rule_rejects_einvoicing_without_a_scheme(self, tenant_a):
        from apps.core.models import StatutoryRule
        rule = StatutoryRule(
            tenant=tenant_a, name="No scheme", effective_from=datetime.date(2026, 1, 1),
            e_invoicing_required=True, e_invoicing_scheme="none",
        )
        with pytest.raises(ValidationError) as exc:
            rule.full_clean()
        assert "e_invoicing_scheme" in exc.value.message_dict

    def test_localization_statutory_rule_name_is_unique_per_tenant(self, localization_rules,
                                                                  tenant_a, tenant_b):
        """The same name is fine in another tenant — the constraint is `(tenant, name)`, not `name`."""
        from apps.core.models import StatutoryRule
        # Allowed in tenant_b, even though tenant_a already holds this name.
        StatutoryRule.objects.create(tenant=tenant_b, name="EU VAT e-invoicing",
                                     effective_from=datetime.date(2026, 1, 1))
        # Refused in tenant_a, where the fixture already created it.
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                StatutoryRule.objects.create(tenant=tenant_a, name="EU VAT e-invoicing",
                                             effective_from=datetime.date(2026, 1, 1))
