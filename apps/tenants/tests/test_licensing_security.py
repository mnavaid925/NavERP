"""0.19 License & Subscription Administration — SECURITY lane.

Distinct from the pre-existing 0.1 `test_security.py` (CSRF/IDOR for 0.1's own views). This lane
covers 0.19's posture: multi-tenant isolation across all 24 routes, the role gate, the method gate,
and the one-writer verbs.

A fact this lane pins deliberately: the two verbs carry `@require_POST` ABOVE
`@tenant_admin_required`, so a wrong METHOD is 405 **regardless of role** — the opposite order from a
role-check-first view, and the reason a non-admin GET gets 405 rather than 403.
"""
import pytest
from django.test import Client
from django.urls import reverse

from apps.tenants.models import UsageQuota

pytestmark = pytest.mark.django_db

_LICENSING_READ_ROUTES = [
    "entitlementfeature_list", "entitlementfeature_create",
    "planentitlement_list", "planentitlement_create",
    "usagequota_list", "usagequota_create",
    "licenseassignment_list", "licenseassignment_create",
    "quota_board", "renewal_board",
]

_LICENSING_PK_ROUTES = [
    "entitlementfeature_detail", "entitlementfeature_edit", "entitlementfeature_delete",
    "planentitlement_detail", "planentitlement_edit", "planentitlement_delete",
    "usagequota_detail", "usagequota_edit", "usagequota_delete", "usagequota_mark_breached",
    "licenseassignment_detail", "licenseassignment_edit", "licenseassignment_delete",
    "licenseassignment_reclaim",
]


# --------------------------------------------------------------- cross-tenant IDOR
class TestCrossTenantIsolation:
    """The #1 risk in this repo. Lists are the caller's OWN (empty) data, never 404 and never another
    workspace's rows; a foreign row addressed by pk is a 404 on GET *and* on POST, with the row
    provably unmutated — a 404 that still wrote would be worse than no gate at all."""

    @pytest.mark.parametrize("name", _LICENSING_READ_ROUTES)
    def test_licensing_another_workspaces_list_is_its_own_empty_data(self, client_b, name):
        response = client_b.get(reverse(f"tenants:{name}"))
        assert response.status_code == 200
        if response.context is not None and "object_list" in response.context:
            assert list(response.context["object_list"]) == []

    @pytest.mark.parametrize("name", _LICENSING_PK_ROUTES)
    def test_licensing_a_foreign_row_is_404_on_get_or_405_on_a_post_only_url(self, client_b, name,
                                                                             lic019_quota_a,
                                                                             lic019_seat_a,
                                                                             lic019_feature_a,
                                                                             lic019_plan_grant_a):
        """GET reaches the view body, so a foreign row is a 404.

        The four delete routes and the two verbs carry `@require_POST` as the OUTERMOST decorator, so
        the method check fires before the tenant filter ever runs and a GET is a 405 — correctly, and
        without leaking whether the row exists. The POST is where those six must prove isolation, and
        that is asserted separately below.
        """
        rows = {"entitlementfeature": lic019_feature_a, "planentitlement": lic019_plan_grant_a,
                "usagequota": lic019_quota_a, "licenseassignment": lic019_seat_a}
        post_only = {"entitlementfeature_delete", "planentitlement_delete", "usagequota_delete",
                     "licenseassignment_delete", "usagequota_mark_breached",
                     "licenseassignment_reclaim"}
        for prefix, row in rows.items():
            if name.startswith(prefix):
                url = reverse(f"tenants:{name}", args=[row.pk])
                response = client_b.get(url)
                assert response.status_code == (405 if name in post_only else 404), \
                    f"{name} answered {response.status_code} for a foreign {prefix} row"

    @pytest.mark.parametrize("name", ["entitlementfeature_delete", "planentitlement_delete",
                                      "usagequota_delete", "licenseassignment_delete",
                                      "usagequota_mark_breached", "licenseassignment_reclaim"])
    def test_licensing_a_foreign_post_is_refused_and_mutates_nothing(self, client_b, name,
                                                                     lic019_feature_a,
                                                                     lic019_plan_grant_a,
                                                                     lic019_quota_a, lic019_seat_a):
        rows = [lic019_feature_a, lic019_plan_grant_a, lic019_quota_a, lic019_seat_a]
        counts = [row.__class__.objects.count() for row in rows]
        stamps = (lic019_quota_a.breached_at, lic019_seat_a.status, lic019_seat_a.reclaimed_on)
        for row in rows:
            response = client_b.post(reverse(f"tenants:{name}", args=[row.pk]), {"reason": "forged"})
            assert response.status_code in (404, 405), f"{name} answered {response.status_code}"
        assert [row.__class__.objects.count() for row in rows] == counts, "a refused POST still wrote"
        assert (lic019_quota_a.breached_at, lic019_seat_a.status,
                lic019_seat_a.reclaimed_on) == stamps, "a refused POST forged evidence"

    def test_licensing_a_seat_for_another_workspaces_user_is_unreachable(self, client_b, lic019_seat_a):
        assert client_b.get(reverse("tenants:licenseassignment_detail", args=[lic019_seat_a.pk])).status_code == 404
        response = client_b.get(reverse("tenants:licenseassignment_list"))
        assert lic019_seat_a not in list(response.context["object_list"])


# --------------------------------------------------------------- the role gate
class TestRoleGate:
    @pytest.mark.parametrize("name", _LICENSING_READ_ROUTES)
    def test_licensing_a_plain_member_is_refused_every_list_and_board(self, member_client, name):
        assert member_client.get(reverse(f"tenants:{name}")).status_code == 403

    @pytest.mark.parametrize("name", ["entitlementfeature_detail", "usagequota_detail",
                                      "licenseassignment_detail", "quota_board"])
    def test_licensing_a_plain_member_is_refused_the_paged_forms(self, member_client, name,
                                                                  lic019_quota_a, lic019_seat_a,
                                                                  lic019_feature_a):
        pks = {"entitlementfeature_detail": lic019_feature_a.pk, "usagequota_detail": lic019_quota_a.pk,
               "licenseassignment_detail": lic019_seat_a.pk, "quota_board": None}
        pk = pks[name]
        url = reverse(f"tenants:{name}", args=[pk]) if pk else reverse(f"tenants:{name}")
        assert member_client.get(url).status_code == 403

    def test_licensing_a_plain_member_cannot_create_a_quota(self, member_client, lic019_subscription_a):
        response = member_client.post(reverse("tenants:usagequota_create"), {
            "subscription": lic019_subscription_a.pk, "metric": "api_calls", "period": "monthly",
            "quota_limit": "1", "warn_at_pct": 80, "action_on_breach": "alert"})
        assert response.status_code == 403
        assert not UsageQuota.objects.filter(metric="api_calls").exists()

    def test_licensing_a_plain_member_cannot_run_the_breach_verb(self, member_client, lic019_quota_a):
        response = member_client.post(reverse("tenants:usagequota_mark_breached", args=[lic019_quota_a.pk]))
        assert response.status_code == 403
        lic019_quota_a.refresh_from_db()
        assert lic019_quota_a.breached_at is None, "a refused verb still stamped evidence"

    def test_licensing_a_plain_member_cannot_run_the_reclaim_verb(self, member_client, lic019_seat_a):
        response = member_client.post(reverse("tenants:licenseassignment_reclaim", args=[lic019_seat_a.pk]),
                                      {"reason": "forged"})
        assert response.status_code == 403
        lic019_seat_a.refresh_from_db()
        assert lic019_seat_a.status == "active"
        assert lic019_seat_a.reclaimed_on is None

    def test_licensing_a_plain_member_cannot_delete_by_posting(self, member_client, lic019_seat_a):
        from apps.tenants.models import LicenseAssignment
        before = LicenseAssignment.objects.count()
        response = member_client.post(reverse("tenants:licenseassignment_delete", args=[lic019_seat_a.pk]))
        assert response.status_code == 403
        assert LicenseAssignment.objects.count() == before

    def test_licensing_an_anonymous_caller_never_reaches_a_page(self, db):
        client = Client()
        assert client.get(reverse("tenants:entitlementfeature_list")).status_code in (302, 403)


# --------------------------------------------------------------- the method gate
class TestMethodGateAndCSRF:
    """A `GET` on a destructive URL must be 405 AND must not have deleted anything. A hidden button
    is not a guard; the method check is."""

    @pytest.mark.parametrize("name,row_attr", [
        ("entitlementfeature_delete", "lic019_feature_a"),
        ("planentitlement_delete", "lic019_plan_grant_a"),
        ("usagequota_delete", "lic019_quota_a"),
        ("licenseassignment_delete", "lic019_seat_a"),
        ("usagequota_mark_breached", "lic019_quota_a"),
        ("licenseassignment_reclaim", "lic019_seat_a"),
    ])
    def test_licensing_a_get_on_a_destructive_url_is_405_and_changes_nothing(self, client_a, name,
                                                                             row_attr, request):
        row = request.getfixturevalue(row_attr)
        before = row.__class__.objects.count()
        # `breached_at` / `reclaimed_on` exist only on the two models the verbs write, so read them
        # defensively — a `hasattr` on the CLASS would be True via the field descriptor even for a
        # model whose instance has no such attribute.
        def _licensing_evidence():
            return tuple(getattr(row, field, None) for field in ("breached_at", "status", "reclaimed_on"))

        stamps = _licensing_evidence()
        response = client_a.get(reverse(f"tenants:{name}", args=[row.pk]))
        assert response.status_code == 405
        assert row.__class__.objects.count() == before, "a GET mutated the table"
        row.refresh_from_db()
        assert _licensing_evidence() == stamps, "a GET wrote evidence"

    @pytest.mark.parametrize("name,row_attr", [("usagequota_mark_breached", "lic019_quota_a"),
                                               ("licenseassignment_reclaim", "lic019_seat_a")])
    def test_licensing_the_verbs_enforce_csrf(self, name, row_attr, request, admin_user):
        row = request.getfixturevalue(row_attr)
        client = Client(enforce_csrf_checks=True)
        client.force_login(admin_user)
        response = client.post(reverse(f"tenants:{name}", args=[row.pk]))
        assert response.status_code == 403
        row.refresh_from_db()
        if hasattr(row, "breached_at"):
            assert row.breached_at is None
        else:
            assert row.reclaimed_on is None

    def test_licensing_a_non_admin_get_is_405_not_403_because_the_method_check_runs_first(self,
                                                                                          member_client,
                                                                                          lic019_quota_a):
        """The decorator order, made observable: `@require_POST` is OUTERMOST, so the method check
        precedes the role check and a non-admin GET gets 405 rather than 403."""
        assert member_client.get(reverse("tenants:usagequota_mark_breached", args=[lic019_quota_a.pk])).status_code == 405


# --------------------------------------------------------------- the honesty band
class TestNoPageOverclaims:
    """L33 and the house honesty rule, asserted on the files rather than in a docstring. A page that
    implies enforcement, charging, sending or scheduling that the code cannot perform is a real
    defect, not a style nit."""

    _TEMPLATES = [
        "templates/tenants/entitlementfeature/list.html",
        "templates/tenants/entitlementfeature/detail.html",
        "templates/tenants/planentitlement/list.html",
        "templates/tenants/planentitlement/detail.html",
        "templates/tenants/usagequota/list.html",
        "templates/tenants/usagequota/detail.html",
        "templates/tenants/licenseassignment/list.html",
        "templates/tenants/licenseassignment/detail.html",
        "templates/tenants/quota_board.html",
        "templates/tenants/renewal_board.html",
    ]

    @pytest.mark.parametrize("template", _TEMPLATES)
    def test_licensing_no_template_uses_a_badge_class_that_does_not_exist(self, template):
        """L33. The semantic `-success` / `-warning` / `-danger` names are NOT in `theme.css`; they
        render unstyled, which is how a shipped page looks broken."""
        import re
        from pathlib import Path

        root = Path(__file__).resolve().parents[3]
        css = (root / "static" / "css" / "theme.css").read_text(encoding="utf-8")
        defined = set(re.findall(r"\.badge-([a-z]+)", css))
        used = set(re.findall(r"badge-([a-z]+)", (root / template).read_text(encoding="utf-8")))
        assert used, f"{template} should use at least one badge"
        assert used <= defined, f"{template} uses undefined badge classes: {used - defined}"

    @pytest.mark.parametrize("template", _TEMPLATES)
    def test_licensing_no_template_uses_safe_or_mark_safe(self, template):
        from pathlib import Path

        root = Path(__file__).resolve().parents[3]
        text = (root / template).read_text(encoding="utf-8")
        assert "|safe" not in text
        assert "mark_safe" not in text
        assert "{% autoescape off %}" not in text

    @pytest.mark.parametrize("template", _TEMPLATES)
    def test_licensing_no_template_leaks_a_single_line_comment(self, template):
        """L2. A multi-line `{# … #}` comment renders as visible text; only `{% comment %}` is safe.
        Asserted by checking no `{#` survives at all."""
        from pathlib import Path

        root = Path(__file__).resolve().parents[3]
        assert "{#" not in (root / template).read_text(encoding="utf-8")

    @pytest.mark.parametrize("template", _TEMPLATES)
    def test_licensing_no_template_is_double_encoded(self, template):
        """The C1 defect: three of these files shipped UTF-8-with-BOM and double-encoded, rendering
        `â€”` in the page — including the L36 honesty note itself."""
        from pathlib import Path

        root = Path(__file__).resolve().parents[3]
        raw = (root / template).read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), f"{template} has a UTF-8 BOM"
        text = raw.decode("utf-8", "replace")
        for bad in ("â€", "Â·", "â€™"):
            assert bad not in text, f"{template} contains mojibake {bad!r}"

    def test_licensing_the_seat_pages_state_that_reclaiming_disables_nobody(self, client_a, lic019_seat_a):
        """Decline #3, on the page the reader is most likely to trust."""
        html = client_a.get(reverse("tenants:licenseassignment_list")).content.decode("utf-8", "replace")
        assert "does not disable the login" in html or "disables nobody" in html

    def test_licensing_the_grant_pages_state_that_nothing_enforces_them(self, client_a, lic019_feature_a):
        """Decline #1, asserted on the page rather than in a module docstring."""
        html = client_a.get(reverse("tenants:entitlementfeature_list")).content.decode("utf-8", "replace")
        assert "enforce" in html.lower()

    # ------------------------------------------------------------------ M3 / M4 closed by a shared partial
    _LICENSING_019_PAGES = [
        "templates/tenants/entitlementfeature/list.html",
        "templates/tenants/planentitlement/list.html",
        "templates/tenants/usagequota/list.html",
        "templates/tenants/licenseassignment/list.html",
        "templates/tenants/quota_board.html",
        "templates/tenants/renewal_board.html",
    ]

    def _licensing_root(self):
        from pathlib import Path
        return Path(__file__).resolve().parents[3]

    @pytest.mark.parametrize("template", _LICENSING_019_PAGES)
    def test_licensing_every_icon_only_button_has_an_accessible_name(self, template):
        """M4. An icon-only control whose only label is `title` has a fallback accessible name at
        best; `aria-label` is the robust one. Asserted per file so a new icon button cannot be added
        without one."""
        text = (self._licensing_root() / template).read_text(encoding="utf-8")
        for line in text.splitlines():
            if 'class="btn-icon' in line:
                assert "aria-label" in line, f"{template} has an icon-only button with no accessible name"

    @pytest.mark.parametrize("template", _LICENSING_019_PAGES)
    def test_licensing_no_page_hand_rolls_its_own_confirm_form(self, template):
        """M3. The seven-line POST+confirm form was duplicated across six call sites, which is how
        the two copies drifted. They now all include the shared partial."""
        text = (self._licensing_root() / template).read_text(encoding="utf-8")
        assert 'method="post"' not in text, f"{template} hand-rolls a POST form; use partials/confirm_button.html"
        assert "onsubmit=" not in text, f"{template} hand-rolls a confirm dialog"

    def test_licensing_every_confirm_comes_from_the_shared_partial(self):
        """...and the partial really is where they come from, so the count is honest."""
        text = (self._licensing_root() / "templates/tenants/entitlementfeature/list.html").read_text(
            encoding="utf-8")
        assert 'partials/confirm_button.html' in text

    @pytest.mark.parametrize("template", _LICENSING_019_PAGES)
    def test_licensing_no_confirm_message_contains_a_raw_apostrophe(self, template):
        """L42. A literal `'` in a confirm message is HTML-escaped to `&#39;`, which the browser
        DECODES BACK to a bare quote before JavaScript parses the string — so the dialog stops
        guarding anything. `partials/confirm_button.html` cannot escape this from inside a template,
        so the rule is enforced here instead of being trusted to review."""
        import re
        root = self._licensing_root()
        for path in (root / template, root / "templates/partials/confirm_button.html"):
            for message in re.findall(r'confirm_message="([^"]*)"', path.read_text(encoding="utf-8")):
                assert "'" not in message, f"{path.name} confirm message contains a raw apostrophe (L42)"
                assert "\\" not in message, f"{path.name} confirm message contains a backslash (L42)"
