"""Tests for the 0.15 localization forms.

The load-bearing test in this file is `test_localization_statutory_form_rejects_a_duplicate_name`. Before
the review's C1 fix, `StatutoryRuleForm` did not validate the model's `unique_together = ("tenant", "name")`
— because `tenant` is not a `Meta.fields` member, Django's `Model._get_unique_checks()` drops any
`unique_together` containing an excluded field — so a duplicate name reached the database and returned an
`IntegrityError` **500**. These tests are what would have caught that.
"""
import datetime

import pytest

pytestmark = pytest.mark.django_db


class TestLocalizationStatutoryRuleForm:
    def _payload(self, name):
        return {
            "name": name, "jurisdiction": "Test", "tax_code": "", "e_invoicing_scheme": "none",
            "statutory_report": "", "effective_from": "2026-01-01", "effective_to": "",
            "is_active": "on", "notes": "",
        }

    def test_localization_statutory_form_rejects_a_duplicate_name(self, localization_rules, tenant_a):
        """C1 regression: an existing name must be a FORM ERROR, never a 500."""
        from apps.core.forms import StatutoryRuleForm
        form = StatutoryRuleForm(self._payload("EU VAT e-invoicing"), tenant=tenant_a)
        assert form.is_valid() is False
        assert "name" in form.errors
        assert "already exists" in form.errors["name"][0]

    def test_localization_statutory_form_allows_the_same_name_in_another_tenant(
        self, localization_rules, tenant_b
    ):
        from apps.core.forms import StatutoryRuleForm
        form = StatutoryRuleForm(self._payload("EU VAT e-invoicing"), tenant=tenant_b)
        assert form.is_valid() is True

    def test_localization_statutory_form_allows_an_edit_that_keeps_its_own_name(
        self, localization_rules, tenant_a
    ):
        """The guard must exclude `self.instance.pk`, or every no-op edit would be rejected."""
        from apps.core.forms import StatutoryRuleForm
        rule = localization_rules["a"][0]
        form = StatutoryRuleForm(self._payload(rule.name), instance=rule, tenant=tenant_a)
        assert form.is_valid() is True

    def test_localization_statutory_form_accepts_a_new_name(self, localization_rules, tenant_a):
        from apps.core.forms import StatutoryRuleForm
        form = StatutoryRuleForm(self._payload("Brand New Rule"), tenant=tenant_a)
        assert form.is_valid() is True

    def test_localization_statutory_form_excludes_tenant(self):
        from apps.core.forms import StatutoryRuleForm
        assert "tenant" not in StatutoryRuleForm().fields

    def test_localization_statutory_form_rejects_einvoicing_without_a_scheme(self, tenant_a):
        from apps.core.forms import StatutoryRuleForm
        payload = self._payload("Needs a scheme")
        payload["e_invoicing_required"] = "on"
        payload["e_invoicing_scheme"] = "none"
        form = StatutoryRuleForm(payload, tenant=tenant_a)
        assert form.is_valid() is False
        assert "e_invoicing_scheme" in form.errors

    def test_localization_statutory_form_rejects_inverted_dates(self, tenant_a):
        from apps.core.forms import StatutoryRuleForm
        payload = self._payload("Inverted")
        payload["effective_from"] = "2026-06-01"
        payload["effective_to"] = "2026-01-01"
        form = StatutoryRuleForm(payload, tenant=tenant_a)
        assert form.is_valid() is False
        assert "effective_to" in form.errors

    def test_localization_statutory_form_scopes_tax_code_to_the_tenant(self, tenant_a, tenant_b):
        from apps.accounting.models import TaxCode
        from apps.core.forms import StatutoryRuleForm
        mine = TaxCode.objects.create(tenant=tenant_a, name="Acme VAT", tax_type="vat", rate_pct=20)
        theirs = TaxCode.objects.create(tenant=tenant_b, name="Globex VAT", tax_type="vat",
                                        rate_pct=20)
        form = StatutoryRuleForm(tenant=tenant_a)
        pks = set(form.fields["tax_code"].queryset.values_list("pk", flat=True))
        assert mine.pk in pks
        assert theirs.pk not in pks

    def test_localization_statutory_form_refuses_a_cross_tenant_tax_code(self, tenant_a, tenant_b):
        from apps.accounting.models import TaxCode
        from apps.core.forms import StatutoryRuleForm
        theirs = TaxCode.objects.create(tenant=tenant_b, name="Globex VAT", tax_type="vat",
                                        rate_pct=20)
        payload = self._payload("Cross-tenant code")
        payload["tax_code"] = str(theirs.pk)
        form = StatutoryRuleForm(payload, tenant=tenant_a)
        assert form.is_valid() is False
        assert "tax_code" in form.errors


class TestLocalizationSingletonForms:
    def test_localization_locale_profile_form_excludes_tenant_and_timestamp(self):
        from apps.core.forms import LocaleProfileForm
        fields = LocaleProfileForm().fields
        assert "tenant" not in fields
        assert "updated_at" not in fields

    def test_localization_user_locale_form_excludes_tenant_and_user(self):
        from apps.core.forms import UserLocalePreferenceForm
        fields = UserLocalePreferenceForm().fields
        assert "tenant" not in fields
        assert "user" not in fields

    def test_localization_user_locale_date_format_is_optional(self):
        """Blank means "inherit the workspace's pattern" — so it must not be required."""
        from apps.core.forms import UserLocalePreferenceForm
        assert UserLocalePreferenceForm().fields["date_format"].required is False

    def test_localization_locale_profile_form_scopes_globals_unfiltered(self, tenant_a):
        """`language` / `time_zone` / `base_currency` are GLOBAL — they must NOT be tenant-filtered."""
        from apps.core.models import Language, TimeZone
        from apps.core.forms import LocaleProfileForm
        Language.objects.create(code="fr", name="French")
        TimeZone.objects.create(name="Europe/Paris", label="Paris", utc_offset_minutes=60)
        form = LocaleProfileForm(tenant=tenant_a)
        assert form.fields["language"].queryset.filter(code="fr").exists()
        assert form.fields["time_zone"].queryset.filter(name="Europe/Paris").exists()

    def test_localization_locale_profile_form_rejects_a_bad_format(self, tenant_a):
        from apps.core.forms import LocaleProfileForm
        form = LocaleProfileForm({"date_format": "dd/MM/yyyy<script>", "time_format": "HH:mm",
                                  "number_format": "#,##0.00", "first_day_of_week": "1"}, tenant=tenant_a)
        assert form.is_valid() is False
        assert "date_format" in form.errors
