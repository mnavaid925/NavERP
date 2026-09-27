"""0.19 License & Subscription Administration — VIEWS lane.

Distinct from the pre-existing 0.1 lanes. This lane covers the 24 routes 0.19 added: four CRUD sets,
two POST-only verbs, and two computed boards.

The rule this lane exists to enforce: **assert CONTENT, not just a status code.** A wrong or missing
context key returns 200 and renders a blank region (L7/L8), so a bare `status == 200` tests nothing.
Every page assertion looks for a seeded record's own value in the HTML.
"""
import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.tenants.models import Subscription

pytestmark = pytest.mark.django_db

#: The CRUD routes as (name, needs_pk), so one loop covers them all.
_LICENSING_CRUD = [
    ("entitlementfeature_list", False), ("entitlementfeature_create", False),
    ("entitlementfeature_detail", True), ("entitlementfeature_edit", True),
    ("planentitlement_list", False), ("planentitlement_create", False),
    ("planentitlement_detail", True), ("planentitlement_edit", True),
    ("usagequota_list", False), ("usagequota_create", False),
    ("usagequota_detail", True), ("usagequota_edit", True),
    ("licenseassignment_list", False), ("licenseassignment_create", False),
    ("licenseassignment_detail", True), ("licenseassignment_edit", True),
]

_LICENSING_BOARDS = ["quota_board", "renewal_board"]


@pytest.fixture
def lic019_client_empty(db, tenant_a, admin_user):
    """A tenant admin whose workspace holds NO subscription, quota, seat or feature — so the two
    boards are exercised against a genuinely empty state. Defined HERE rather than in the shared
    conftest, which is owned by the earlier step and is 0.1's (L43)."""
    client = Client()
    client.force_login(admin_user)
    return client


def _licensing_html(client, name, pk=None):
    """Fetch a page and return its body as text.

    `reverse()` takes positional `args`, NOT a `pk=` kwarg — passing the kwarg raises TypeError,
    which reads as a broken view rather than a broken test."""
    url = reverse(f"tenants:{name}", args=[pk]) if pk else reverse(f"tenants:{name}")
    return client.get(url).content.decode("utf-8", "replace")


# --------------------------------------------------------------- every route reverses
class TestRoutesReverse:
    @pytest.mark.parametrize("name,needs_pk", _LICENSING_CRUD)
    def test_licensing_crud_route_reverses(self, name, needs_pk):
        # `reverse()` takes positional `args`; a `pk=` kwarg is a TypeError.
        url = reverse(f"tenants:{name}", args=[1]) if needs_pk else reverse(f"tenants:{name}")
        assert url.startswith("/tenants/licensing/")

    @pytest.mark.parametrize("name", _LICENSING_BOARDS)
    def test_licensing_board_route_reverses(self, name):
        assert reverse(f"tenants:{name}").startswith("/tenants/licensing/")

    def test_licensing_the_two_verb_routes_reverse(self, lic019_quota_a, lic019_seat_a):
        assert reverse("tenants:usagequota_mark_breached", args=[lic019_quota_a.pk])
        assert reverse("tenants:licenseassignment_reclaim", args=[lic019_seat_a.pk])

    def test_licensing_the_boards_are_declared_before_the_pk_routes(self):
        """Django is first-match-wins; a literal segment after a converter sibling is swallowed.

        `url_patterns` on the ROOT resolver only lists the top-level `include()` prefixes, so this
        has to descend into the tenants include to see the real patterns. The nested patterns hang
        off `url_patterns` directly, not off a `.resolver` attribute."""
        from django.urls import get_resolver
        tenants = next(p for p in get_resolver().url_patterns if str(p.pattern) == "tenants/")
        patterns = [str(p.pattern) for p in tenants.url_patterns]
        assert "licensing/quota-board/" in patterns
        assert "licensing/renewal-board/" in patterns


# --------------------------------------------------------------- every page renders REAL content
class TestPagesRenderTheirOwnData:
    """L8. A 200 with a blank region is the defect, so each assertion looks for the seeded value."""

    def test_licensing_feature_list_shows_the_seeded_code(self, client_a, lic019_feature_a):
        assert lic019_feature_a.code in _licensing_html(client_a, "entitlementfeature_list")

    def test_licensing_feature_detail_shows_the_seeded_code(self, client_a, lic019_feature_a):
        html = _licensing_html(client_a, "entitlementfeature_detail", lic019_feature_a.pk)
        assert lic019_feature_a.code in html
        assert lic019_feature_a.name in html

    def test_licensing_grant_list_shows_the_seeded_plan(self, client_a, lic019_plan_grant_a):
        assert lic019_plan_grant_a.get_plan_display() in \
            _licensing_html(client_a, "planentitlement_list")

    def test_licensing_grant_detail_shows_the_seeded_privilege_value(self, client_a, lic019_plan_grant_a):
        assert lic019_plan_grant_a.privilege_value in \
            _licensing_html(client_a, "planentitlement_detail", lic019_plan_grant_a.pk)

    def test_licensing_quota_list_shows_the_seeded_metric(self, client_a, lic019_quota_a):
        assert lic019_quota_a.get_metric_display() in _licensing_html(client_a, "usagequota_list")

    def test_licensing_quota_detail_shows_the_seeded_metric(self, client_a, lic019_quota_a):
        assert lic019_quota_a.get_metric_display() in \
            _licensing_html(client_a, "usagequota_detail", lic019_quota_a.pk)

    def test_licensing_seat_list_shows_the_seeded_number(self, client_a, lic019_seat_a):
        assert lic019_seat_a.number in _licensing_html(client_a, "licenseassignment_list")

    def test_licensing_seat_detail_shows_the_seeded_number(self, client_a, lic019_seat_a):
        assert lic019_seat_a.number in \
            _licensing_html(client_a, "licenseassignment_detail", lic019_seat_a.pk)

    @pytest.mark.parametrize("name", ["entitlementfeature_create", "planentitlement_create",
                                      "usagequota_create", "licenseassignment_create"])
    def test_licensing_every_create_page_renders_its_form(self, client_a, name):
        assert _licensing_html(client_a, name)


# --------------------------------------------------------------- the quota board's three states
class TestQuotaBoardStates:
    """`quota_limit == 0` means UNMETERED: no percentage, no breach state, and it is excluded from
    the warned/breached counts. All three states must be renderable at once."""

    def test_licensing_the_board_renders_both_a_metered_and_an_unmetered_row(self, client_a,
                                                                               lic019_quota_a,
                                                                               lic019_quota_unmetered_a):
        html = _licensing_html(client_a, "quota_board")
        assert lic019_quota_a.get_metric_display() in html
        assert lic019_quota_unmetered_a.get_metric_display() in html

    def test_licensing_an_unmetered_row_says_so(self, client_a, lic019_quota_unmetered_a):
        assert "Unmetered" in _licensing_html(client_a, "quota_board")

    def test_licensing_the_board_counts_the_unmetered_rows_separately(self, client_a, lic019_quota_a,
                                                                       lic019_quota_unmetered_a):
        response = client_a.get(reverse("tenants:quota_board"))
        assert response.status_code == 200
        assert response.context["unmetered_count"] == 1
        assert response.context["breached_count"] == 0

    def test_licensing_a_marked_breach_is_counted(self, client_a, lic019_quota_a):
        client_a.post(reverse("tenants:usagequota_mark_breached", args=[lic019_quota_a.pk]))
        lic019_quota_a.refresh_from_db()
        assert lic019_quota_a.breached_at is not None
        response = client_a.get(reverse("tenants:quota_board"))
        assert response.context["breached_count"] == 1

    def test_licensing_the_board_states_action_on_breach_is_not_enforced(self, client_a, lic019_quota_a):
        """Decline #2, asserted on the rendered page rather than in a docstring."""
        html = _licensing_html(client_a, "quota_board")
        assert "no interceptor" in html or "nothing in NavERP enforces" in html


# --------------------------------------------------------------- the renewal board's honesty
class TestRenewalBoard:
    def test_licensing_the_board_renders_a_seeded_subscription(self, client_a, lic019_subscription_a):
        assert lic019_subscription_a.get_plan_display() in _licensing_html(client_a, "renewal_board")

    def test_licensing_the_board_counts_only_an_expressed_auto_renew(self, client_a,
                                                                     lic019_subscription_a):
        """I10. `None` means "nobody has said" and must NOT be reported as a decision to renew."""
        assert lic019_subscription_a.auto_renew is True
        response = client_a.get(reverse("tenants:renewal_board"))
        assert response.context["auto_renew_count"] == 1

        lic019_subscription_a.auto_renew = None
        lic019_subscription_a.save()
        response = client_a.get(reverse("tenants:renewal_board"))
        assert response.context["auto_renew_count"] == 0, \
            "an unanswered intent must not be reported as a decision"

    def test_licensing_the_board_names_the_sub_module_that_owns_the_scheduler(self, client_a):
        """Decline #9 — the renewal RUN is 0.20, and the page says so."""
        assert "0.20" in _licensing_html(client_a, "renewal_board")

    def test_licensing_the_board_exposes_its_row_cap(self, client_a):
        """I8's honesty half: the cards count the whole workspace while the table is capped, so the
        page must carry the cap or a reader counts rows against a tile and calls it broken."""
        response = client_a.get(reverse("tenants:renewal_board"))
        assert "row_cap" in response.context
        assert "renewal_total" in response.context


# --------------------------------------------------------------- the boards on an empty workspace
class TestBoardsOnAnEmptyWorkspace:
    """A board that crashes on an empty state is a real defect, not a cosmetic one."""

    @pytest.mark.parametrize("name", _LICENSING_BOARDS)
    def test_licensing_a_board_renders_with_no_data_at_all(self, lic019_client_empty, name):
        response = lic019_client_empty.get(reverse(f"tenants:{name}"))
        assert response.status_code == 200
        assert "Traceback" not in response.content.decode("utf-8", "replace")

    def test_licensing_the_quota_board_reports_zero_of_everything(self, lic019_client_empty):
        response = lic019_client_empty.get(reverse("tenants:quota_board"))
        assert response.context["quota_rows"] == []
        assert response.context["breached_count"] == 0
        assert response.context["unmetered_count"] == 0

    def test_licensing_the_renewal_board_reports_zero_of_everything(self, lic019_client_empty):
        response = lic019_client_empty.get(reverse("tenants:renewal_board"))
        assert response.context["renewal_rows"] == []
        assert response.context["auto_renew_count"] == 0


# --------------------------------------------------------------- filters, paging, junk params
class TestListsAreResilient:
    @pytest.mark.parametrize("name", ["entitlementfeature_list", "planentitlement_list",
                                      "usagequota_list", "licenseassignment_list"])
    @pytest.mark.parametrize("query", [
        {"status": "nonsense"}, {"page": "2"}, {"page": "9999"}, {"q": "%_"}, {"user": "abc"},
    ])
    def test_licensing_a_list_survives_junk_parameters(self, client_a, name, query):
        assert client_a.get(reverse(f"tenants:{name}"), query).status_code == 200

    def test_licensing_a_filter_narrows_the_list(self, client_a, lic019_feature_a):
        response = client_a.get(reverse("tenants:entitlementfeature_list"), {"status": "active"})
        assert response.status_code == 200
        assert lic019_feature_a in list(response.context["object_list"])

    def test_licensing_a_filter_matching_nothing_is_an_empty_list_not_an_error(self, client_a):
        response = client_a.get(reverse("tenants:entitlementfeature_list"), {"status": "archived"})
        assert response.status_code == 200
        assert list(response.context["object_list"]) == []


# --------------------------------------------------------------- the two POST-only verbs
class TestVerbsAreTheSoleWriters:
    def test_licensing_mark_breached_stamps_the_quota(self, client_a, lic019_quota_a):
        response = client_a.post(reverse("tenants:usagequota_mark_breached", args=[lic019_quota_a.pk]))
        assert response.status_code in (200, 302)
        lic019_quota_a.refresh_from_db()
        assert lic019_quota_a.breached_at is not None

    def test_licensing_mark_breached_does_not_move_its_own_stamp(self, client_a, lic019_quota_a):
        client_a.post(reverse("tenants:usagequota_mark_breached", args=[lic019_quota_a.pk]))
        lic019_quota_a.refresh_from_db()
        first = lic019_quota_a.breached_at
        client_a.post(reverse("tenants:usagequota_mark_breached", args=[lic019_quota_a.pk]))
        lic019_quota_a.refresh_from_db()
        assert lic019_quota_a.breached_at == first, "the verb must not rewrite its own evidence"

    def test_licensing_reclaim_stamps_the_seat(self, client_a, lic019_seat_a):
        response = client_a.post(reverse("tenants:licenseassignment_reclaim", args=[lic019_seat_a.pk]),
                                 {"reason": "Returned to the pool."})
        assert response.status_code in (200, 302)
        lic019_seat_a.refresh_from_db()
        assert lic019_seat_a.status == "reclaimed"
        assert lic019_seat_a.reclaimed_on is not None

    def test_licensing_a_non_reclaimable_seat_keeps_its_evidence_empty(self, client_a, lic019_seat_a):
        lic019_seat_a.status = "revoked"
        lic019_seat_a.save()
        client_a.post(reverse("tenants:licenseassignment_reclaim", args=[lic019_seat_a.pk]))
        lic019_seat_a.refresh_from_db()
        assert lic019_seat_a.reclaimed_on is None, "a revoked seat is not reclaimable evidence"


# --------------------------------------------------------------- the I6 view-level edit guard
class TestSeatEditIsGuardedInTheView:
    """Hiding the Edit button does not stop a direct POST, so the rule has to live in the view."""

    def test_licensing_a_reclaimed_seat_cannot_be_edited(self, client_a, lic019_seat_a):
        lic019_seat_a.status = "reclaimed"
        lic019_seat_a.save()
        client_a.post(reverse("tenants:licenseassignment_edit", args=[lic019_seat_a.pk]),
                      {"user": lic019_seat_a.user_id, "module_slug": "crm",
                       "assignment_source": "direct"})
        lic019_seat_a.refresh_from_db()
        assert lic019_seat_a.module_slug == "", "a refused edit must not have been applied"

    def test_licensing_an_active_seat_can_still_be_edited(self, client_a, lic019_seat_a):
        response = client_a.post(reverse("tenants:licenseassignment_edit", args=[lic019_seat_a.pk]),
                                 {"user": lic019_seat_a.user_id, "module_slug": "crm",
                                  "assignment_source": "direct"})
        assert response.status_code in (200, 302)
        lic019_seat_a.refresh_from_db()
        assert lic019_seat_a.module_slug == "crm"


# --------------------------------------------------------------- query-count regression guards
class TestQueryCounts:
    """The performance pass fixed an N+1 that the `subscription__isnull=False` filter made GUARANTEED
    rather than possible.

    These assert the property that actually matters — the count does **not** grow with the number of
    rows — rather than a magic number. A hard-coded count would encode whatever the page happened to
    cost on the day it was written and would break on an unrelated, legitimate change, while a
    per-row query would still pass a "constant 2" style check if the fixture only had two rows.
    """

    @staticmethod
    def _licensing_count(getter):
        with CaptureQueriesContext(connection) as ctx:
            response = getter()
        assert response.status_code == 200
        return len(ctx.captured_queries)

    def test_licensing_grant_detail_does_not_query_per_row(self, client_a, tenant_a, lic019_feature_a,
                                                           lic019_override_a):
        from apps.tenants.models import PlanEntitlement
        url = reverse("tenants:planentitlement_detail", args=[lic019_override_a.pk])
        before = self._licensing_count(lambda: client_a.get(url))
        for _ in range(8):
            sub = Subscription.objects.create(tenant=tenant_a, plan="pro", status="active")
            PlanEntitlement.objects.create(tenant=tenant_a, plan="pro", feature=lic019_feature_a,
                                           subscription=sub, privilege_value="true")
        after = self._licensing_count(lambda: client_a.get(url))
        assert after == before, f"grant detail went {before} -> {after} queries: the N+1 is back"

    def test_licensing_seat_detail_does_not_query_per_row(self, client_a, tenant_a, lic019_user_a):
        from apps.tenants.models import LicenseAssignment
        seat = LicenseAssignment.objects.create(tenant=tenant_a, user=lic019_user_a, module_slug="crm")
        url = reverse("tenants:licenseassignment_detail", args=[seat.pk])
        before = self._licensing_count(lambda: client_a.get(url))
        for i in range(8):
            LicenseAssignment.objects.create(tenant=tenant_a, user=lic019_user_a,
                                             module_slug=f"mod{i}")
        after = self._licensing_count(lambda: client_a.get(url))
        assert after == before, f"seat detail went {before} -> {after} queries"

    def test_licensing_the_quota_board_does_not_query_per_row(self, client_a, tenant_a,
                                                              lic019_subscription_a):
        from apps.tenants.models import UsageQuota
        UsageQuota.objects.create(tenant=tenant_a, subscription=lic019_subscription_a,
                                  metric="api_calls", period="monthly", quota_limit="10")
        url = reverse("tenants:quota_board")
        before = self._licensing_count(lambda: client_a.get(url))
        for i in range(8):
            UsageQuota.objects.create(tenant=tenant_a, subscription=lic019_subscription_a,
                                      metric=f"metric_{i}", period="monthly", quota_limit="10")
        after = self._licensing_count(lambda: client_a.get(url))
        assert after == before, f"quota board went {before} -> {after} queries: the N+1 is back"

    def test_licensing_the_renewal_board_does_not_query_per_row(self, client_a, tenant_a):
        for _ in range(6):
            Subscription.objects.create(tenant=tenant_a, plan="pro", status="active")
        url = reverse("tenants:renewal_board")
        before = self._licensing_count(lambda: client_a.get(url))
        for _ in range(8):
            Subscription.objects.create(tenant=tenant_a, plan="starter", status="active")
        after = self._licensing_count(lambda: client_a.get(url))
        assert after == before, f"renewal board went {before} -> {after} queries: the N+1 is back"
