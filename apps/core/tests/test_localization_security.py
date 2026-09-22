"""Security tests for the 0.15 localization views.

The security review found no Critical and no Important here, so these tests are **regression locks** rather
than fixes: they pin the posture that was verified — every mutating verb is tenant-scoped and admin-gated,
the two GLOBAL registries are deliberately readable by any authenticated user, and 7.7's 405-not-403 ruling
holds on the one POST-only verb.
"""
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db

#: Every 0.15 route, with the args its name needs. `DELETE_ARGS` marks the POST-only verb.
ALL_ROUTES = [
    "localization_overview", "localization_board", "language_list", "timezone_list",
    "locale_profile_edit", "user_locale_edit", "statutory_rule_list", "statutory_rule_create",
    "statutory_rule_detail", "statutory_rule_edit", "statutory_rule_delete",
]
ARG_ROUTES = {"statutory_rule_detail", "statutory_rule_edit", "statutory_rule_delete"}

#: The views a plain member must be refused.
ADMIN_ONLY = ["localization_overview", "localization_board", "locale_profile_edit",
              "statutory_rule_list", "statutory_rule_create"]

#: The views a plain member is deliberately allowed to reach.
MEMBER_ALLOWED = ["language_list", "timezone_list", "user_locale_edit"]


def _localization_url(name, pk=1):
    return reverse("core:" + name, args=[pk] if name in ARG_ROUTES else [])


class TestLocalizationAnonymousAccess:
    def test_localization_anonymous_is_redirected_everywhere(self, client):
        """Every route except the POST-only delete verb, which answers 405 before authentication runs.

        `@require_POST` is the OUTERMOST decorator on `statutory_rule_delete` (7.7's ruling), so an
        anonymous GET is refused on method grounds and never reaches `@login_required`. That is correct
        and is asserted separately below — it is why this loop excludes that one name.
        """
        for name in ALL_ROUTES:
            if name == "statutory_rule_delete":
                continue
            resp = client.get(_localization_url(name))
            assert resp.status_code == 302, name
            assert "/login" in resp["Location"], name

    def test_localization_anonymous_get_on_delete_is_405(self, client):
        resp = client.get(reverse("core:statutory_rule_delete", args=[1]))
        assert resp.status_code == 405


class TestLocalizationMemberAccess:
    def test_localization_member_is_refused_the_admin_views(self, member_client, localization_rules):
        rule = localization_rules["a"][0]
        for name in ADMIN_ONLY:
            resp = member_client.get(_localization_url(name, pk=rule.pk))
            assert resp.status_code == 403, name

    def test_localization_member_is_refused_the_rule_verbs(self, member_client, localization_rules):
        rule = localization_rules["a"][0]
        for name in ("statutory_rule_detail", "statutory_rule_edit"):
            resp = member_client.get(reverse("core:" + name, args=[rule.pk]))
            assert resp.status_code == 403, name

    def test_localization_member_may_read_the_global_registries(self, member_client,
                                                                localization_languages,
                                                                localization_zones):
        """Deliberate: ISO language codes and IANA zone names are public facts, not tenant data."""
        for name in ("language_list", "timezone_list"):
            resp = member_client.get(reverse("core:" + name))
            assert resp.status_code == 200, name

    def test_localization_member_may_edit_their_own_preferences(self, member_client):
        assert member_client.get(reverse("core:user_locale_edit")).status_code == 200


class TestLocalizationMethodAndRoleGates:
    def test_localization_delete_get_is_405_not_403(self, member_client, localization_rules):
        """7.7's ruling: decorators apply bottom-up, so `@require_POST` sits ABOVE the role gate and a
        wrong method is answered 405 regardless of role."""
        rule = localization_rules["a"][0]
        resp = member_client.get(reverse("core:statutory_rule_delete", args=[rule.pk]))
        assert resp.status_code == 405

    def test_localization_delete_get_is_405_for_an_admin_too(self, client_a, localization_rules):
        rule = localization_rules["a"][0]
        resp = client_a.get(reverse("core:statutory_rule_delete", args=[rule.pk]))
        assert resp.status_code == 405

    def test_localization_delete_post_removes_the_row(self, client_a, localization_rules):
        from apps.core.models import StatutoryRule
        rule = localization_rules["a"][1]
        pk = rule.pk
        resp = client_a.post(reverse("core:statutory_rule_delete", args=[pk]))
        assert resp.status_code == 302
        assert not StatutoryRule.objects.filter(pk=pk).exists()


class TestLocalizationTenantIsolation:
    def test_localization_list_hides_another_tenants_rules(self, client_a, localization_rules):
        resp = client_a.get(reverse("core:statutory_rule_list"))
        pks = [r.pk for r in resp.context["object_list"]]
        assert localization_rules["a"][0].pk in pks
        assert localization_rules["b"].pk not in pks

    def test_localization_detail_cross_tenant_is_404(self, client_a, localization_rules):
        foreign = localization_rules["b"]
        resp = client_a.get(reverse("core:statutory_rule_detail", args=[foreign.pk]))
        assert resp.status_code == 404

    def test_localization_edit_cross_tenant_is_404_and_does_not_mutate(self, client_a,
                                                                       localization_rules):
        foreign = localization_rules["b"]
        original = (foreign.name, foreign.jurisdiction)
        resp = client_a.post(reverse("core:statutory_rule_edit", args=[foreign.pk]), {
            "name": "Hijacked", "jurisdiction": "Hijacked", "tax_code": "",
            "e_invoicing_scheme": "none", "effective_from": "2026-01-01", "is_active": "on",
        })
        assert resp.status_code == 404
        foreign.refresh_from_db()
        assert (foreign.name, foreign.jurisdiction) == original

    def test_localization_delete_cross_tenant_is_404_and_does_not_mutate(self, client_a,
                                                                        localization_rules):
        from apps.core.models import StatutoryRule
        foreign = localization_rules["b"]
        resp = client_a.post(reverse("core:statutory_rule_delete", args=[foreign.pk]))
        assert resp.status_code == 404
        assert StatutoryRule.objects.filter(pk=foreign.pk).exists()

    def test_localization_member_preference_cannot_touch_an_admins_row(
        self, member_client, member_user, admin_user
    ):
        """The member's save must create/update only their own row."""
        from apps.core.models import UserLocalePreference
        assert not UserLocalePreference.objects.filter(user=admin_user).exists()
        member_client.post(reverse("core:user_locale_edit"), {"date_format": "yyyy-MM-dd"})
        assert not UserLocalePreference.objects.filter(user=admin_user).exists()
        assert UserLocalePreference.objects.filter(user=member_user).exists()
