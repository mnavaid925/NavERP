"""Tests for the 0.15 localization views.

Two behaviours here are easy to get wrong and silent when wrong: the singleton edit pages must not create
a row merely because somebody opened the page, and the two GLOBAL registries must render for a tenant-less
superuser (they are not tenant data, so the `tenant is None` branch must not catch them).
"""
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


class TestLocalizationGlobalLists:
    def test_localization_language_list_renders(self, client_a, localization_languages):
        resp = client_a.get(reverse("core:language_list"))
        assert resp.status_code == 200
        assert "core/language/list.html" in [t.name for t in resp.templates]
        assert "Arabic" in resp.content.decode()

    def test_localization_timezone_list_renders_a_formatted_offset(self, client_a,
                                                                  localization_zones):
        """The column must read `UTC+05:30`, never `UTC+330` (which reads as hours)."""
        resp = client_a.get(reverse("core:timezone_list"))
        body = resp.content.decode()
        assert resp.status_code == 200
        assert "UTC+05:30" in body
        assert "UTC+330" not in body

    def test_localization_language_list_filters_by_rtl(self, client_a, localization_languages):
        resp = client_a.get(reverse("core:language_list"), {"rtl": "True"})
        body = resp.content.decode()
        assert resp.status_code == 200
        assert "Arabic" in body
        assert "English" not in body

    def test_localization_language_list_survives_junk_params(self, client_a,
                                                             localization_languages):
        resp = client_a.get(reverse("core:language_list"),
                            {"rtl": "abc", "active": "maybe", "page": "999"})
        assert resp.status_code == 200

    def test_localization_timezone_list_survives_junk_params(self, client_a, localization_zones):
        resp = client_a.get(reverse("core:timezone_list"), {"dst": "nope", "page": "-1"})
        assert resp.status_code == 200


class TestLocalizationSingletonEdits:
    def test_localization_profile_get_does_not_create_a_row(self, client_a, tenant_a):
        """Opening the page must not write. A row appears only when somebody saves one."""
        from apps.core.models import LocaleProfile
        assert LocaleProfile.objects.filter(tenant=tenant_a).count() == 0
        resp = client_a.get(reverse("core:locale_profile_edit"))
        assert resp.status_code == 200
        assert LocaleProfile.objects.filter(tenant=tenant_a).count() == 0

    def test_localization_profile_post_creates_then_updates_one_row(self, client_a, tenant_a,
                                                                    localization_languages,
                                                                    localization_zones):
        from apps.core.models import LocaleProfile
        url = reverse("core:locale_profile_edit")
        payload = {
            "language": str(localization_languages[0].pk),
            "base_currency": "", "time_zone": str(localization_zones[0].pk),
            "date_format": "dd/MM/yyyy", "time_format": "HH:mm", "number_format": "#,##0.00",
            "address_format": "", "first_day_of_week": "1", "notes": "",
        }
        assert client_a.post(url, payload).status_code == 302
        assert LocaleProfile.objects.filter(tenant=tenant_a).count() == 1

        payload["date_format"] = "yyyy-MM-dd"
        assert client_a.post(url, payload).status_code == 302
        assert LocaleProfile.objects.filter(tenant=tenant_a).count() == 1
        assert LocaleProfile.objects.get(tenant=tenant_a).date_format == "yyyy-MM-dd"

    def test_localization_profile_post_rejects_a_bad_format(self, client_a, tenant_a):
        from apps.core.models import LocaleProfile
        payload = {"date_format": "dd/MM/yyyy<script>", "time_format": "HH:mm",
                   "number_format": "#,##0.00", "first_day_of_week": "1"}
        resp = client_a.post(reverse("core:locale_profile_edit"), payload)
        assert resp.status_code == 200
        assert LocaleProfile.objects.filter(tenant=tenant_a).count() == 0

    def test_localization_user_locale_post_writes_the_actors_row(self, member_client, member_user,
                                                                 localization_languages,
                                                                 localization_zones):
        """A member's own save must land on the MEMBER's row, in the member's tenant."""
        from apps.core.models import UserLocalePreference
        payload = {"language": str(localization_languages[0].pk),
                   "time_zone": str(localization_zones[0].pk), "date_format": "yyyy-MM-dd"}
        assert member_client.post(reverse("core:user_locale_edit"), payload).status_code == 302

        pref = UserLocalePreference.objects.get(user=member_user)
        assert pref.tenant_id == member_user.tenant_id
        assert pref.date_format == "yyyy-MM-dd"


class TestLocalizationStatutoryRuleViews:
    def test_localization_statutory_list_renders_and_filters(self, client_a, localization_rules):
        resp = client_a.get(reverse("core:statutory_rule_list"))
        assert resp.status_code == 200
        assert "EU VAT e-invoicing" in resp.content.decode()

        resp = client_a.get(reverse("core:statutory_rule_list"), {"scheme": "peppol"})
        body = resp.content.decode()
        assert resp.status_code == 200
        assert "EU VAT e-invoicing" in body
        assert "US sales tax filing" not in body

    def test_localization_statutory_list_survives_junk_params(self, client_a, localization_rules):
        resp = client_a.get(reverse("core:statutory_rule_list"),
                            {"scheme": "zzz", "active": "1", "page": "999999999999999999999"})
        assert resp.status_code == 200

    def test_localization_statutory_create_rejects_a_duplicate_with_200(self, client_a, tenant_a,
                                                                        localization_rules):
        """C1 regression at the view layer: a duplicate name is a form error, never a 500."""
        from apps.core.models import StatutoryRule
        before = StatutoryRule.objects.filter(tenant=tenant_a).count()
        resp = client_a.post(reverse("core:statutory_rule_create"), {
            "name": "EU VAT e-invoicing", "jurisdiction": "Test", "tax_code": "",
            "e_invoicing_scheme": "none", "effective_from": "2026-01-01", "is_active": "on",
        })
        assert resp.status_code == 200
        assert "name" in resp.context["form"].errors
        assert StatutoryRule.objects.filter(tenant=tenant_a).count() == before

    def test_localization_statutory_create_saves_with_the_session_tenant(
        self, client_a, tenant_a, tenant_b, localization_statutory_payload
    ):
        """A posted foreign `tenant` must be ignored — the tenant comes from the session."""
        from apps.core.models import StatutoryRule
        payload = dict(localization_statutory_payload, tenant=str(tenant_b.pk))
        resp = client_a.post(reverse("core:statutory_rule_create"), payload)
        assert resp.status_code == 302
        rule = StatutoryRule.objects.get(name="New Compliance Rule")
        assert rule.tenant_id == tenant_a.pk

    def test_localization_statutory_edit_updates(self, client_a, localization_rules):
        from apps.core.models import StatutoryRule
        rule = localization_rules["a"][1]
        resp = client_a.post(reverse("core:statutory_rule_edit", args=[rule.pk]), {
            "name": rule.name, "jurisdiction": "Edited Jurisdiction", "tax_code": "",
            "e_invoicing_scheme": "none", "effective_from": "2026-01-01", "is_active": "on",
        })
        assert resp.status_code == 302
        rule.refresh_from_db()
        assert rule.jurisdiction == "Edited Jurisdiction"

    def test_localization_statutory_edit_rejects_a_rename_onto_a_sibling(self, client_a,
                                                                         localization_rules):
        """C1 regression on the edit verb — the second half of the original 500."""
        from apps.core.models import StatutoryRule
        first, second = localization_rules["a"]
        resp = client_a.post(reverse("core:statutory_rule_edit", args=[first.pk]), {
            "name": second.name, "jurisdiction": "Test", "tax_code": "",
            "e_invoicing_scheme": "none", "effective_from": "2026-01-01", "is_active": "on",
        })
        assert resp.status_code == 200
        assert "name" in resp.context["form"].errors
        first.refresh_from_db()
        assert first.name == "EU VAT e-invoicing"

    def test_localization_statutory_detail_renders(self, client_a, localization_rules):
        rule = localization_rules["a"][0]
        resp = client_a.get(reverse("core:statutory_rule_detail", args=[rule.pk]))
        assert resp.status_code == 200
        assert rule.name in resp.content.decode()


class TestLocalizationComputedPages:
    def test_localization_board_renders(self, client_a, localization_profile):
        resp = client_a.get(reverse("core:localization_board"))
        assert resp.status_code == 200
        assert "core/localizationboard.html" in [t.name for t in resp.templates]
        assert resp.context["stale_after_days"] == 7
        assert isinstance(resp.context["rate_rows"], list)

    def test_localization_overview_renders(self, client_a, localization_profile):
        resp = client_a.get(reverse("core:localization_overview"))
        assert resp.status_code == 200
        assert resp.context["has_profile"] is True

    def test_localization_overview_without_a_profile(self, client_a, tenant_a):
        resp = client_a.get(reverse("core:localization_overview"))
        assert resp.status_code == 200
        assert resp.context["has_profile"] is False


class TestLocalizationTenantlessSuperuser:
    """The two GLOBAL registries must work for `tenant=None` — they are not tenant data."""

    @pytest.fixture
    def superuser_client(self, db):
        from django.contrib.auth import get_user_model
        from django.test import Client
        user = get_user_model().objects.create_superuser(
            email="rootless15@example.com", password="pw-rootless15")
        assert user.tenant is None
        client = Client()
        client.force_login(user)
        return client

    def test_localization_global_lists_render_for_a_tenantless_user(self, superuser_client,
                                                                    localization_languages,
                                                                    localization_zones):
        for name, marker in (("language_list", "Arabic"), ("timezone_list", "Europe/London")):
            resp = superuser_client.get(reverse("core:" + name))
            assert resp.status_code == 200, name
            assert marker in resp.content.decode(), name

    def test_localization_tenant_scoped_pages_redirect_for_a_tenantless_user(self, superuser_client):
        for name in ("localization_overview", "localization_board", "locale_profile_edit",
                     "user_locale_edit"):
            resp = superuser_client.get(reverse("core:" + name))
            assert resp.status_code == 302, name
            assert resp["Location"] == reverse("dashboard:home"), name
