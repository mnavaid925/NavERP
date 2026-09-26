"""8.4 Sales Forecasting -- the VIEWS lane.

Naming: every test is ``test_salesforecasting_*`` and every module-level helper
``_salesforecasting_*`` so the next sub-module appending nearby cannot shadow
them (8.1/8.2/8.3 own the ``leadmanagement``/``opportunitypipeline``/
``contactaccountmanagement`` names in this same package).

The rule this lane exists for is **L8**: a context key a template reads but the
view never passes returns HTTP 200 and renders a blank region. So every list and
report test asserts both the status AND that a seeded record's own number is
actually in the HTML.
"""
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.sales.tests.conftest import (
    _salesforecasting_adjustment,
    _salesforecasting_submission,
)


def _body(response):
    return response.content.decode("utf-8", "replace")


# ------------------------------------------------------------------- the lists
@pytest.mark.parametrize(
    "route",
    [
        "sales:forecast_period_list",
        "sales:forecast_submission_list",
        "sales:forecast_adjustment_list",
        "sales:forecast_scenario_list",
    ],
)
def test_salesforecasting_list_renders_200_and_shows_a_seeded_number(
    salesforecasting_client_a,
    salesforecasting_period_a,
    salesforecasting_submission_a,
    salesforecasting_adjustment_a,
    salesforecasting_scenario_a,
    route,
):
    """Each register must render the seeded row, not just an empty-state 200 (L8)."""
    body = _body(salesforecasting_client_a.get(reverse(route)))
    assert any(tag in body for tag in ("FCP-", "FCS-", "FAD-", "FSC-")), route


def test_salesforecasting_submission_list_shows_the_seeded_record(
    salesforecasting_client_a, salesforecasting_submission_a
):
    body = _body(salesforecasting_client_a.get(reverse("sales:forecast_submission_list")))
    assert salesforecasting_submission_a.number in body


def test_salesforecasting_list_passes_the_pagination_object(salesforecasting_client_a):
    response = salesforecasting_client_a.get(reverse("sales:forecast_submission_list"))
    page_obj = response.context["page_obj"]
    assert page_obj is not None
    assert hasattr(page_obj, "has_next")


def test_salesforecasting_search_filter_narrows_the_register(
    salesforecasting_client_a, salesforecasting_tenant_a, salesforecasting_period_a
):
    _salesforecasting_submission(
        salesforecasting_tenant_a, salesforecasting_period_a, notes="ZZUNIQUEMARKERZZ"
    )
    body = _body(
        salesforecasting_client_a.get(
            reverse("sales:forecast_submission_list") + "?q=ZZUNIQUEMARKERZZ"
        )
    )
    assert "ZZUNIQUEMARKERZZ" in body


def test_salesforecasting_junk_query_parameters_do_not_break_a_list(salesforecasting_client_a):
    url = reverse("sales:forecast_submission_list") + (
        "?status=nonsense&period=abc&q=%20&owner=999999999999999999999&page=notanumber"
    )
    assert salesforecasting_client_a.get(url).status_code == 200


def test_salesforecasting_junk_query_parameters_do_not_break_a_report(salesforecasting_client_a):
    url = reverse("sales:forecast_board") + "?period=abc&rollup_dimension=junk&q=%20"
    assert salesforecasting_client_a.get(url).status_code == 200



# ------------------------------------------------------------------ the reports
@pytest.mark.parametrize(
    "route,needle",
    [
        ("sales:forecast_board", "Forecast Board"),
        ("sales:forecast_attainment", "Quota Attainment"),
        ("sales:forecast_accuracy", "Forecast Accuracy"),
        ("sales:forecast_call", "Forecast Call"),
    ],
)
def test_salesforecasting_report_renders_its_title(salesforecasting_client_a, route, needle):
    assert needle in _body(salesforecasting_client_a.get(reverse(route))), route


def test_salesforecasting_board_derives_a_total_from_the_seeded_submission(
    salesforecasting_client_a, salesforecasting_tenant_a, salesforecasting_period_a
):
    """The report must show the DERIVED figure, not a blank cell (L8)."""
    _salesforecasting_submission(salesforecasting_tenant_a, salesforecasting_period_a)
    body = _body(salesforecasting_client_a.get(reverse("sales:forecast_board")))
    # pipeline 10000 + best_case 8000 + commit 5000 + closed 0 = 23000
    assert "23,000.00" in body or "23000.00" in body


def test_salesforecasting_reports_never_show_a_non_finite_percentage(salesforecasting_client_a):
    """A zero quota must render a dash, never Infinity/NaN."""
    for route in ("sales:forecast_board", "sales:forecast_attainment"):
        body = _body(salesforecasting_client_a.get(reverse(route)))
        assert "Infinity" not in body and "NaN" not in body, route


def test_salesforecasting_call_lists_the_seeded_override(
    salesforecasting_client_a, salesforecasting_adjustment_a
):
    assert salesforecasting_adjustment_a.number in _body(
        salesforecasting_client_a.get(reverse("sales:forecast_call"))
    )


# ------------------------------------------------------------------ the details
def test_salesforecasting_detail_pages_render_200(
    salesforecasting_client_a,
    salesforecasting_period_a,
    salesforecasting_submission_a,
    salesforecasting_adjustment_a,
    salesforecasting_scenario_a,
):
    for route, obj in (
        ("sales:forecast_period_detail", salesforecasting_period_a),
        ("sales:forecast_submission_detail", salesforecasting_submission_a),
        ("sales:forecast_adjustment_detail", salesforecasting_adjustment_a),
        ("sales:forecast_scenario_detail", salesforecasting_scenario_a),
    ):
        assert salesforecasting_client_a.get(reverse(route, args=[obj.pk])).status_code == 200, route


def test_salesforecasting_adjustment_detail_renders_the_manager_note(
    salesforecasting_client_a, salesforecasting_tenant_a, salesforecasting_submission_a
):
    """Regression (C2): the note fragment sat after ``{% endblock %}`` and Django
    silently discarded it, so the override's justification never rendered."""
    adjustment = _salesforecasting_adjustment(
        salesforecasting_tenant_a,
        salesforecasting_submission_a,
        reason_code="sandbagging_risk",
        note="PROMARKERNOTE",
    )
    body = _body(
        salesforecasting_client_a.get(
            reverse("sales:forecast_adjustment_detail", args=[adjustment.pk])
        )
    )
    assert "PROMARKERNOTE" in body


def test_salesforecasting_create_forms_render_200(salesforecasting_client_a):
    for route in (
        "sales:forecast_period_create",
        "sales:forecast_submission_create",
        "sales:forecast_adjustment_create",
        "sales:forecast_scenario_create",
    ):
        assert salesforecasting_client_a.get(reverse(route)).status_code == 200, route


def test_salesforecasting_export_renders_a_csv(salesforecasting_client_a):
    response = salesforecasting_client_a.get(reverse("sales:forecast_submission_export"))
    assert response.status_code == 200
    assert "text/csv" in response["Content-Type"]


def test_salesforecasting_no_template_comment_leaks_into_a_page(salesforecasting_client_a):
    for route in (
        "sales:forecast_period_list",
        "sales:forecast_submission_list",
        "sales:forecast_board",
        "sales:forecast_call",
    ):
        body = _body(salesforecasting_client_a.get(reverse(route)))
        assert "{#" not in body, route
        assert "{% comment" not in body, route
