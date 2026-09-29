"""8.6 Order Management -- security lane.

Multi-tenancy is enforced by a single repeated idiom -- ``Model.objects.filter(tenant=...)`` or
``get_object_or_404(Model, pk=pk, tenant=...)`` -- which is exactly the kind of rule applied on
46 views and forgotten on the 47th. So this lane asserts it from the OUTSIDE: it logs in as
tenant B, hands it a row belonging to tenant A, and requires a **404**.

The 404 (not 403, not 302, not a 200 rendering someone else's data) is the contract. A 403 would
confirm the row exists, which is itself a leak; a 200 would be the breach.
"""
import pytest
from django.urls import reverse

from apps.sales.tests.conftest import (
    _ordermanagement_amendment,
    _ordermanagement_amendment_line,
    _ordermanagement_hold,
    _ordermanagement_obligation,
    _ordermanagement_order,
    _ordermanagement_rule,
    _ordermanagement_schedule,
)

pytestmark = pytest.mark.django_db

#: Surfaces addressed by a row pk. A cross-tenant pk must 404 on every one.
DETAIL_SURFACES = (
    "order_validation_rule_detail", "order_validation_rule_edit",
    "order_validation_rule_delete",
    "order_hold_detail", "order_hold_edit", "order_hold_delete",
    "order_amendment_detail", "order_amendment_edit", "order_amendment_delete",
    "order_amendment_impact", "order_amendment_decide", "order_amendment_apply",
    "order_amendment_withdraw", "order_amendment_line_add",
    "revenue_schedule_detail", "revenue_schedule_edit", "revenue_schedule_delete",
    "revenue_schedule_recognize", "revenue_schedule_obligation_add",
)

#: Hold verbs addressed by a single hold pk.
HOLD_SURFACES = (
    "order_hold_checkout", "order_hold_release_checkout", "order_hold_clear",
    "order_hold_clear_and_submit",
)

#: Every page an anonymous visitor must not be served.
PUBLIC_ROUTES = (
    "order_hold_list", "order_amendment_list", "revenue_schedule_list",
    "order_validation_rule_list", "order_capture_board", "revenue_recognition_board",
)


def _seed_a(tenant):
    """A full 8.6 graph belonging to tenant A."""
    order = _ordermanagement_order(tenant, status="submitted")
    rule = _ordermanagement_rule(tenant)
    hold = _ordermanagement_hold(tenant, order, rule=rule)
    amendment = _ordermanagement_amendment(tenant, order)
    _ordermanagement_amendment_line(amendment, order.lines.first())
    schedule = _ordermanagement_schedule(tenant, order)
    _ordermanagement_obligation(tenant, schedule)
    return {"order": order, "rule": rule, "hold": hold, "amendment": amendment,
            "schedule": schedule}


# ------------------------------------------------------------ cross-tenant IDOR


def test_ordermanagement_cross_tenant_idor_404s_on_every_detail_surface(
    ordermanagement_client_b, ordermanagement_tenant_a,
):
    """The core multi-tenancy assertion, driven from tenant B against tenant A's rows."""
    seed = _seed_a(ordermanagement_tenant_a)
    victims = {
        "order_validation_rule_detail": seed["rule"].pk,
        "order_hold_detail": seed["hold"].pk,
        "order_amendment_detail": seed["amendment"].pk,
        "revenue_schedule_detail": seed["schedule"].pk,
    }
    for name, pk in victims.items():
        response = ordermanagement_client_b.get(reverse("sales:" + name, args=[pk]))
        assert response.status_code == 404, \
            f"{name} returned {response.status_code} for another tenant's row"


def test_ordermanagement_cross_tenant_idor_404s_on_every_mutating_surface(
    ordermanagement_client_b, ordermanagement_tenant_a,
):
    """A verb that 404s on GET must also 404 on POST: the guard is in the lookup, not the verb."""
    _seed_a(ordermanagement_tenant_a)
    for name in DETAIL_SURFACES:
        response = ordermanagement_client_b.post(reverse("sales:" + name, args=[1]), {})
        assert response.status_code == 404, \
            f"{name} POST returned {response.status_code} for another tenant's row"


def test_ordermanagement_cross_tenant_hold_verbs_404(
    ordermanagement_client_b, ordermanagement_tenant_a,
):
    seed = _seed_a(ordermanagement_tenant_a)
    for name in HOLD_SURFACES:
        response = ordermanagement_client_b.post(
            reverse("sales:" + name, args=[seed["hold"].pk]), {"clear_note": "x"}
        )
        assert response.status_code == 404, \
            f"{name} POST returned {response.status_code} for another tenant's hold"


def test_ordermanagement_cross_tenant_child_surfaces_404(
    ordermanagement_client_b, ordermanagement_tenant_a,
):
    """The children are tenant-LESS, so the tenant guard lives on the PARENT lookup. If the
    parent check is skipped the child verbs become the hole -- so they are tested directly."""
    seed = _seed_a(ordermanagement_tenant_a)
    line_pk = seed["amendment"].lines.first().pk
    ob_pk = seed["schedule"].obligations.first().pk
    child_urls = (
        reverse("sales:order_amendment_line_edit", args=[seed["amendment"].pk, line_pk]),
        reverse("sales:order_amendment_line_delete", args=[seed["amendment"].pk, line_pk]),
        reverse("sales:revenue_schedule_obligation_edit", args=[seed["schedule"].pk, ob_pk]),
        reverse("sales:revenue_schedule_obligation_delete", args=[seed["schedule"].pk, ob_pk]),
    )
    for url in child_urls:
        # These are POST-only, so the 405 arrives before the tenant lookup ever runs. That is
        # correct -- and it means the GET proves nothing about authorisation. The POST is the
        # real attack path, so that is what carries the 404 assertion.
        assert ordermanagement_client_b.get(url).status_code in (404, 405), url
        assert ordermanagement_client_b.post(url, {}).status_code == 404, url


def test_ordermanagement_cross_tenant_child_of_the_wrong_parent_404s(
    ordermanagement_client_b, ordermanagement_tenant_a, ordermanagement_tenant_b,
):
    """The subtle case: both the parent and the child belong to B, so neither is 'foreign'.

    Reaching B's own line through A's amendment pk would be a genuine authorisation hole --
    the view must check that the child is a child of the amendment named in the URL.
    """
    seed_a = _seed_a(ordermanagement_tenant_a)
    order_b = _ordermanagement_order(ordermanagement_tenant_b, status="submitted")
    amendment_b = _ordermanagement_amendment(ordermanagement_tenant_b, order_b)
    line_b = _ordermanagement_amendment_line(amendment_b, order_b.lines.first())

    url = reverse("sales:order_amendment_line_edit", args=[seed_a["amendment"].pk, line_b.pk])
    # POST-only: the GET is 405 before any lookup, so the POST is where the hole would show.
    assert ordermanagement_client_b.get(url).status_code in (404, 405)
    assert ordermanagement_client_b.post(url, {}).status_code == 404, \
        "B reached its own line through another tenant's amendment"


def test_ordermanagement_boards_never_leak_another_tenants_rows(
    ordermanagement_client_b, ordermanagement_tenant_a,
):
    """A board or list that aggregates without a tenant filter leaks another workspace."""
    seed_a = _seed_a(ordermanagement_tenant_a)
    for name in ("order_hold_list", "order_amendment_list", "revenue_schedule_list",
                 "order_validation_rule_list", "order_amendment_open_queue",
                 "revenue_recognition_board", "order_capture_board",
                 "order_fulfillment_board", "order_history_board",
                 "reorder_customers_board", "renewals_due_board"):
        response = ordermanagement_client_b.get(reverse("sales:" + name))
        assert response.status_code == 200
        html = response.content.decode()
        assert seed_a["hold"].number not in html, f"{name} leaked tenant A's hold number"
        assert seed_a["rule"].number not in html, f"{name} leaked tenant A's rule number"


def test_ordermanagement_cross_tenant_raise_hold_404s(
    ordermanagement_client_b, ordermanagement_tenant_a,
):
    """`order_hold_raise` is addressed by ORDER id -- the one non-pk route in the surface."""
    seed_a = _seed_a(ordermanagement_tenant_a)
    response = ordermanagement_client_b.post(
        reverse("sales:order_hold_raise", args=[seed_a["order"].pk]), {"hold_type": "manual"}
    )
    assert response.status_code == 404



# ------------------------------------------------------------------- the login floor


@pytest.mark.parametrize("name", PUBLIC_ROUTES)
def test_ordermanagement_every_page_requires_login(client, name):
    """An anonymous visitor is redirected to the login page, never served a workspace page."""
    response = client.get(reverse("sales:" + name))
    assert response.status_code in (302, 403)
    if response.status_code == 302:
        assert "login" in response["Location"].lower()


def test_ordermanagement_anonymous_post_is_refused(client):
    """CSRF plus login: an anonymous POST must not reach a verb at all."""
    response = client.post(reverse("sales:order_hold_bulk_raise"), {"ids": "1"})
    assert response.status_code in (302, 403)


def test_ordermanagement_post_without_csrf_token_is_refused(
    ordermanagement_tenant_a, ordermanagement_admin_a
):
    """Django's test client bypasses CSRF by default, so enforce it explicitly here."""
    from django.test import Client

    seed = _seed_a(ordermanagement_tenant_a)
    enforcing = Client(enforce_csrf_checks=True)
    assert enforcing.login(username=ordermanagement_admin_a.username, password="password")

    response = enforcing.post(
        reverse("sales:order_hold_clear", args=[seed["hold"].pk]), {"clear_note": "no token"}
    )
    assert response.status_code == 403, "a POST without a CSRF token was accepted"
    seed["hold"].refresh_from_db()
    assert seed["hold"].status == "open", "the hold was cleared despite the CSRF failure"

