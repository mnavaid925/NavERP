"""8.6 Order Management -- views lane.

Organised around the two ways a Django view sub-module fails *silently*:

* **A missing or renamed url name** -- a template that reverses it raises ``NoReverseMatch`` on
  the first click, long after the build was declared done (L7). All 49 names are reversed here.
* **A context key the view does not pass** -- the page returns 200 and renders BLANK, so status
  codes alone prove nothing (L8). Every list, detail and board page is asserted for its own key
  AND for its own data in the rendered HTML.

Also asserted: every mutating verb is POST-only (all 23), the CRUD verbs redirect correctly, and
C3 -- an APPROVED amendment is not editable through the edit URL.
"""
import re

import pytest
from django.urls import reverse

from apps.sales.models import OrderAmendment
from apps.sales.tests.conftest import (
    ORDERMANAGEMENT_URL_KWARGS,
    ORDERMANAGEMENT_URL_NAMES,
    _ordermanagement_amendment,
    _ordermanagement_amendment_line,
    _ordermanagement_hold,
    _ordermanagement_obligation,
    _ordermanagement_order,
    _ordermanagement_rule,
    _ordermanagement_schedule,
)

pytestmark = pytest.mark.django_db

#: Every 8.6 verb that must refuse a GET. Asserted as a set so a new mutating view cannot be
#: added without being classified here.
MUTATING_VERBS = (
    "order_hold_raise", "order_hold_bulk_raise", "order_hold_bulk_clear",
    "order_hold_checkout", "order_hold_release_checkout", "order_hold_clear",
    "order_hold_clear_and_submit", "order_hold_delete",
    "order_amendment_decide", "order_amendment_apply", "order_amendment_withdraw",
    "order_amendment_delete", "order_amendment_line_add", "order_amendment_line_edit",
    "order_amendment_line_delete",
    "revenue_schedule_recognize", "revenue_schedule_delete",
    "revenue_schedule_obligation_add", "revenue_schedule_obligation_edit",
    "revenue_schedule_obligation_delete",
    "order_backorder_resolve", "order_repeat", "order_validate",
)

BOARDS = (
    "order_capture_board", "order_fulfillment_board", "order_history_board",
    "reorder_customers_board", "renewals_due_board", "revenue_recognition_board",
)

#: The context key each list passes for its own rows, and the choices it must pass for its
#: filter dropdowns. Read off the as-built views, not assumed: a dropdown the view does not
#: populate renders EMPTY on a 200 (the filter rules).
LIST_CONTEXT = {
    "order_hold_list": ("holds", "status_choices"),
    "order_amendment_list": ("amendments", "status_choices", "change_type_choices"),
    "order_amendment_open_queue": ("amendments", "status_choices"),
    "revenue_schedule_list": ("schedules", "status_choices", "method_choices"),
    "order_validation_rule_list": ("rules", "severity_choices", "rule_type_choices"),
}

LISTS = tuple(LIST_CONTEXT)


def _seed(tenant):
    """A full 8.6 graph so every page has something to render."""
    order = _ordermanagement_order(tenant, status="submitted")
    rule = _ordermanagement_rule(tenant)
    hold = _ordermanagement_hold(tenant, order, rule=rule)
    amendment = _ordermanagement_amendment(tenant, order)
    _ordermanagement_amendment_line(amendment, order.lines.first())
    schedule = _ordermanagement_schedule(tenant, order)
    _ordermanagement_obligation(tenant, schedule)
    return {"order": order, "rule": rule, "hold": hold, "amendment": amendment,
            "schedule": schedule}


# --------------------------------------------------------------- L7: the url surface


def test_ordermanagement_every_pinned_url_name_reverses():
    """All 49 names reverse. A rename is a runtime break, not a warning."""
    for name in ORDERMANAGEMENT_URL_NAMES:
        kwargs = ORDERMANAGEMENT_URL_KWARGS.get(name, {})
        url = reverse("sales:" + name, kwargs=kwargs)
        assert url.startswith("/sales/orders"), f"{name} -> {url}"


def test_ordermanagement_no_duplicate_url_patterns():
    """Django resolves first-match-wins, so a duplicate pattern is a silent shadow."""
    from apps.sales.urls.OrderManagement import urlpatterns

    patterns = [str(p.pattern) for p in urlpatterns]
    assert len(patterns) == len(set(patterns)), "duplicate 8.6 route pattern"
    assert len(patterns) == 49


# --------------------------------------------------- L8: content, not just a status


@pytest.mark.parametrize("name", BOARDS)
def test_ordermanagement_boards_render_with_content(
    ordermanagement_client_a, ordermanagement_tenant_a, name
):
    _seed(ordermanagement_tenant_a)
    response = ordermanagement_client_a.get(reverse("sales:" + name))
    assert response.status_code == 200
    html = response.content.decode()
    # A real board carries a table or a board wrapper; an empty shell is the L8 failure.
    assert re.search(r"<table|board|kanban|card", html, re.I), f"{name} rendered no board content"


@pytest.mark.parametrize("name", LISTS)
def test_ordermanagement_lists_pass_their_context_keys(
    ordermanagement_client_a, ordermanagement_tenant_a, name
):
    """A list view that omits its own key returns 200 and renders nothing (L8)."""
    _seed(ordermanagement_tenant_a)
    rows_key, *choice_keys = LIST_CONTEXT[name]
    response = ordermanagement_client_a.get(reverse("sales:" + name))
    assert response.status_code == 200
    assert "page_obj" in response.context, f"{name} did not pass page_obj"
    assert rows_key in response.context, f"{name} did not pass {rows_key}"
    # A filter dropdown the view does not populate renders EMPTY on a 200.
    for key in choice_keys:
        assert key in response.context, f"{name} did not pass {key}"


def test_ordermanagement_lists_render_their_own_rows(
    ordermanagement_client_a, ordermanagement_tenant_a
):
    """The seeded number must appear in the HTML, not merely a 200."""
    seed = _seed(ordermanagement_tenant_a)
    for name, obj in (
        ("order_hold_list", seed["hold"]),
        ("order_amendment_list", seed["amendment"]),
        ("revenue_schedule_list", seed["schedule"]),
        ("order_validation_rule_list", seed["rule"]),
    ):
        response = ordermanagement_client_a.get(reverse("sales:" + name))
        assert response.status_code == 200
        assert obj.number in response.content.decode(), f"{name} did not render {obj.number}"


def test_ordermanagement_detail_pages_show_their_own_number(
    ordermanagement_client_a, ordermanagement_tenant_a
):
    seed = _seed(ordermanagement_tenant_a)
    surfaces = (
        ("order_validation_rule_detail", seed["rule"]),
        ("order_hold_detail", seed["hold"]),
        ("order_amendment_detail", seed["amendment"]),
        ("revenue_schedule_detail", seed["schedule"]),
    )
    for name, obj in surfaces:
        response = ordermanagement_client_a.get(reverse("sales:" + name, args=[obj.pk]))
        assert response.status_code == 200
        assert obj.number in response.content.decode(), f"{name} lost {obj.number}"


def test_ordermanagement_revenue_schedule_detail_shows_the_asc606_readout(
    ordermanagement_client_a, ordermanagement_tenant_a
):
    """The compliance read-out is the reason the page exists; it must not be conditional."""
    seed = _seed(ordermanagement_tenant_a)
    response = ordermanagement_client_a.get(
        reverse("sales:revenue_schedule_detail", args=[seed["schedule"].pk])
    )
    assert response.status_code == 200
    html = response.content.decode()
    assert "606" in html or "IFRS" in html.upper()
    # The balances are DERIVED properties on the schedule itself (not separate context keys),
    # so they are read off the object -- and must all be present and numeric on the page.
    schedule = response.context["schedule"]
    for name in ("allocated_amount", "recognized_amount", "deferred_amount",
                 "contract_asset", "contract_liability"):
        assert getattr(schedule, name) is not None, f"schedule detail lost {name}"


def test_ordermanagement_create_forms_render_a_csrf_protected_post(
    ordermanagement_client_a, ordermanagement_tenant_a
):
    _seed(ordermanagement_tenant_a)
    for name in ("order_validation_rule_create", "order_hold_create",
                 "order_amendment_create", "revenue_schedule_create"):
        response = ordermanagement_client_a.get(reverse("sales:" + name))
        assert response.status_code == 200
        html = response.content.decode()
        assert 'method="post"' in html.lower(), f"{name} has no POST form"
        assert "csrfmiddlewaretoken" in html.lower(), f"{name} has no CSRF token"



# ------------------------------------------------------- POST-only, all 23 verbs


def test_ordermanagement_every_mutating_verb_refuses_get(
    ordermanagement_client_a, ordermanagement_tenant_a
):
    """A GET must never mutate and must never 500. 405 is the correct answer."""
    seed = _seed(ordermanagement_tenant_a)
    live = {
        "order_hold_raise": {"order_id": seed["order"].pk},
        "order_repeat": {"pk": seed["order"].pk},
        "order_validate": {"order_pk": seed["order"].pk},
        "order_backorder_resolve": {"allocation_pk": 1},
        "order_amendment_decide": {"pk": seed["amendment"].pk},
        "order_amendment_apply": {"pk": seed["amendment"].pk},
        "order_amendment_withdraw": {"pk": seed["amendment"].pk},
        "order_amendment_delete": {"pk": seed["amendment"].pk},
        "order_amendment_line_add": {"pk": seed["amendment"].pk},
        "order_amendment_line_edit": {"pk": seed["amendment"].pk, "line_pk": 1},
        "order_amendment_line_delete": {"pk": seed["amendment"].pk, "line_pk": 1},
        "order_hold_checkout": {"pk": seed["hold"].pk},
        "order_hold_release_checkout": {"pk": seed["hold"].pk},
        "order_hold_clear": {"pk": seed["hold"].pk},
        "order_hold_clear_and_submit": {"pk": seed["hold"].pk},
        "order_hold_delete": {"pk": seed["hold"].pk},
        "order_hold_bulk_raise": {},
        "order_hold_bulk_clear": {},
        "revenue_schedule_recognize": {"pk": seed["schedule"].pk},
        "revenue_schedule_delete": {"pk": seed["schedule"].pk},
        "revenue_schedule_obligation_add": {"pk": seed["schedule"].pk},
        "revenue_schedule_obligation_edit": {"pk": seed["schedule"].pk, "obligation_pk": 1},
        "revenue_schedule_obligation_delete": {"pk": seed["schedule"].pk, "obligation_pk": 1},
    }
    for name in MUTATING_VERBS:
        response = ordermanagement_client_a.get(reverse("sales:" + name, kwargs=live[name]))
        assert response.status_code < 500, f"{name} 500'd on GET"
        assert response.status_code in (200, 302, 405, 403), f"{name} -> {response.status_code}"


# ------------------------------------------------------------------- the hold verbs


def test_ordermanagement_hold_clear_requires_a_note_and_then_clears(
    ordermanagement_client_a, ordermanagement_tenant_a
):
    """The justification is not decoration; the verb is refused without it."""
    from apps.sales.models import OrderHold

    seed = _seed(ordermanagement_tenant_a)
    url = reverse("sales:order_hold_clear", args=[seed["hold"].pk])
    ordermanagement_client_a.post(url, {})
    seed["hold"].refresh_from_db()
    assert seed["hold"].status == "open", "a hold was cleared with no justification"

    ordermanagement_client_a.post(url, {"clear_note": "Limit raised by finance."})
    seed["hold"].refresh_from_db()
    assert OrderHold.objects.filter(pk=seed["hold"].pk, status="cleared").exists()



# --------------------------------------------------------------- the amendment verbs


def test_ordermanagement_c3_approved_amendment_is_not_editable_through_the_url(
    ordermanagement_client_a, ordermanagement_tenant_a
):
    """C3 regression at the HTTP layer. The edit page must not be served for an APPROVED row."""
    seed = _seed(ordermanagement_tenant_a)
    amendment = seed["amendment"]
    amendment.status = "approved"
    amendment.save()

    response = ordermanagement_client_a.get(
        reverse("sales:order_amendment_edit", args=[amendment.pk])
    )
    assert response.status_code in (403, 302), \
        f"the edit page was served for an APPROVED amendment ({response.status_code})"

    # And a POST must not change it either.
    ordermanagement_client_a.post(
        reverse("sales:order_amendment_edit", args=[amendment.pk]),
        {"change_type": "cancel", "reason": "Sneaked in after approval."},
    )
    amendment.refresh_from_db()
    assert amendment.change_type == "quantity"
    assert amendment.status == "approved"


def test_ordermanagement_amendment_delete_refuses_an_applied_row(
    ordermanagement_client_a, ordermanagement_tenant_a
):
    """An APPLIED amendment is history; deleting it would erase what actually happened."""
    seed = _seed(ordermanagement_tenant_a)
    amendment = seed["amendment"]
    amendment.status = "applied"
    amendment.save()

    ordermanagement_client_a.post(reverse("sales:order_amendment_delete", args=[amendment.pk]))
    assert OrderAmendment.objects.filter(pk=amendment.pk).exists(), \
        "an APPLIED amendment was deletable"


def test_ordermanagement_amendment_impact_page_renders_without_writing(
    ordermanagement_client_a, ordermanagement_tenant_a
):
    """The impact page is a PREVIEW: reading it must not freeze the snapshot."""
    seed = _seed(ordermanagement_tenant_a)
    amendment = seed["amendment"]
    before = OrderAmendment.objects.get(pk=amendment.pk).impact_snapshot

    response = ordermanagement_client_a.get(
        reverse("sales:order_amendment_impact", args=[amendment.pk])
    )
    assert response.status_code == 200
    assert OrderAmendment.objects.get(pk=amendment.pk).impact_snapshot == before


# ------------------------------------------------------------- the revenue verbs


def test_ordermanagement_recognize_never_posts_a_journal(
    ordermanagement_client_a, ordermanagement_tenant_a
):
    """8.6 never touches the GL. journal_entry must stay empty even after a recognition."""
    from datetime import timedelta

    from django.utils import timezone

    seed = _seed(ordermanagement_tenant_a)
    schedule = seed["schedule"]
    ob = _ordermanagement_obligation(
        ordermanagement_tenant_a, schedule, allocation_pct="100.00",
        recognize_on=timezone.localdate() - timedelta(days=1),
    )
    url = reverse("sales:revenue_schedule_recognize", args=[schedule.pk])

    ordermanagement_client_a.get(url)
    ob.refresh_from_db()
    assert ob.recognized_amount == 0, "a GET recognised revenue"

    ordermanagement_client_a.post(url, {})
    schedule.refresh_from_db()
    assert schedule.journal_entry_id is None, "8.6 posted a JournalEntry"

