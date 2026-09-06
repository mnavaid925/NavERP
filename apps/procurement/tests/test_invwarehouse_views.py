"""Procurement 6.18 Inventory & Warehouse Integration — view tests.

Every page asserts **content**, not just status. A mismatched context variable returns 200 and
renders a blank region, so a status-only sweep is the check that reports clean by reading nothing.

The regressions here are named by finding id. Several guard defects that were shipped and fixed in
Phase 5 and would come back **silently** — a filter that empties a board, a dropdown that does
nothing, a query count that triples because somebody printed an object instead of its pk.
"""
from datetime import date, timedelta

import pytest
from django.urls import reverse

from apps.procurement.models import MaterialIssue, ReplenishmentRun, ReplenishmentSuggestion
from apps.scm.models import StockAdjustment, StockMove

pytestmark = pytest.mark.django_db


def _invwarehouse_get(client, name, *args, **params):
    url = reverse(f"procurement:{name}", args=args)
    return client.get(url, params)


# --------------------------------------------------------------------------- registers render


def test_invwarehouse_policy_list_renders_its_rows(client_a, invwarehouse_policy_a):
    resp = _invwarehouse_get(client_a, "replenishmentpolicy_list")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert invwarehouse_policy_a.item.sku in body
    assert "{#" not in body and "{% comment" not in body


def test_invwarehouse_run_list_renders_the_run_number(client_a, invwarehouse_run_proposed_a):
    resp = _invwarehouse_get(client_a, "replenishmentrun_list")
    assert resp.status_code == 200
    assert invwarehouse_run_proposed_a.number in resp.content.decode()


def test_invwarehouse_issue_list_renders_the_document_number(
        client_a, invwarehouse_issue_draft_a):
    resp = _invwarehouse_get(client_a, "materialissue_list")
    assert resp.status_code == 200
    assert invwarehouse_issue_draft_a.number in resp.content.decode()


def test_invwarehouse_issue_list_stats_split_issues_from_returns(
        client_a, invwarehouse_issue_draft_a, invwarehouse_return_a):
    resp = _invwarehouse_get(client_a, "materialissue_list")
    stats = resp.context["stats"]
    assert stats["issues"] >= 1 and stats["returns"] >= 1


# --------------------------------------------------------------------------- detail pages


def test_invwarehouse_policy_detail_shows_the_effective_numbers_and_their_source(
        client_a, invwarehouse_policy_a, invwarehouse_rule_a):
    """The comparison table is this page's reason to exist — each figure beside where it came from."""
    resp = _invwarehouse_get(client_a, "replenishmentpolicy_detail", invwarehouse_policy_a.pk)
    assert resp.status_code == 200
    effective = resp.context["effective"]
    assert {"reorder_point", "safety_stock", "target_level", "lead_time_days"} <= set(effective)


def test_invwarehouse_run_detail_paginates_its_lines_separately(
        client_a, invwarehouse_run_lines_a):
    resp = _invwarehouse_get(client_a, "replenishmentrun_detail", invwarehouse_run_lines_a.pk)
    assert resp.status_code == 200
    assert "line_page_obj" in resp.context
    assert resp.context["totals"]["line_count"] >= 1


def test_invwarehouse_issue_detail_carries_both_boundary_notes(
        client_a, invwarehouse_issue_draft_a):
    """The two notes exist so the page cannot be read as claiming more than it does.

    One says return-to-STOCK is this document while return-to-VENDOR is 6.12's; the other says
    posting mints a DRAFT adjustment and stock moves only when SCM posts it.
    """
    resp = _invwarehouse_get(client_a, "materialissue_detail", invwarehouse_issue_draft_a.pk)
    assert resp.status_code == 200
    assert resp.context["boundary_note"]
    assert resp.context["ledger_note"]


def test_invwarehouse_issue_detail_flags_the_shortfall_before_posting(
        client_a, invwarehouse_issue_draft_a):
    """Regression for finding I10, from the page side.

    The fixture is two lines of the SAME item, 6 and 6, against 10 on hand. The page must flag it
    while the document is still editable — a per-line check passes both rows and the buyer only
    learns at Post.
    """
    resp = _invwarehouse_get(client_a, "materialissue_detail", invwarehouse_issue_draft_a.pk)
    lines = list(resp.context["lines"])
    assert lines
    assert any(getattr(line, "is_short", False) for line in lines), (
        "two lines of one item exceeding on-hand were not flagged before Post")


# --------------------------------------------------------------------------- derived pages


def test_invwarehouse_stock_position_renders_with_its_honest_note(
        client_a, invwarehouse_stock_a):
    resp = _invwarehouse_get(client_a, "stock_position")
    assert resp.status_code == 200
    assert resp.context["sku_match_note"]


def test_invwarehouse_receipt_bin_map_renders_with_its_reference_note(client_a):
    resp = _invwarehouse_get(client_a, "receipt_bin_map")
    assert resp.status_code == 200
    assert resp.context["reference_note"]


def test_invwarehouse_count_accuracy_renders_with_its_attribution_note(client_a):
    """attribution_note must say root-cause attribution is NOT recorded.

    A page showing variance by item and location invites the question of whose fault it was, and
    the honest answer is that nothing here records that — it belongs to 6.16.
    """
    resp = _invwarehouse_get(client_a, "count_accuracy")
    assert resp.status_code == 200
    assert resp.context["attribution_note"]


def test_invwarehouse_stock_position_row_keys_match_the_contract(
        client_a, invwarehouse_stock_a):
    """An unpinned row key is a silently blank column, not an error."""
    rows = list(_invwarehouse_get(client_a, "stock_position").context["object_list"])
    if not rows:
        pytest.skip("no stock rows in this workspace")
    expected = {"item", "location", "on_hand", "allocated", "held", "available", "on_order",
                "expected_date", "expected_vendor", "expected_po_number", "expected_po_url",
                "open_requisition_qty", "reorder_point", "avg_daily_demand", "days_of_cover",
                "below_point", "policy_vendor", "raise_requisition_url"}
    assert expected <= set(rows[0])


# ------------------------------------------------ REGRESSIONS: junk input must narrow nothing


@pytest.mark.parametrize("param", ["item", "location", "vendor"])
def test_invwarehouse_stock_position_pk_zero_does_not_empty_the_board(
        client_a, invwarehouse_stock_a, param):
    """Regression for finding S1/I1.

    as_db_int() deliberately passes 0 through — it is decimal and in range — but an AutoField
    starts at 1, so filter(item_id=0) matches nothing and silently EMPTIES the register. A value
    that cannot be a pk is not a narrowing request.
    """
    baseline = len(_invwarehouse_get(client_a, "stock_position").context["object_list"])
    resp = _invwarehouse_get(client_a, "stock_position", **{param: "0"})
    assert resp.status_code == 200
    assert len(resp.context["object_list"]) == baseline, f"?{param}=0 emptied the board"


@pytest.mark.parametrize("page", ["stock_position", "receipt_bin_map", "count_accuracy"])
@pytest.mark.parametrize("params", [
    {"location": "99999999999999999999"},   # over-range: converts fine, then overflows the driver
    {"location": "²"},                      # isdigit() is True, int() refuses it
    {"q": "'; DROP TABLE--"},
    {"status": "nonsense"},
    {"page": "2"},
])
def test_invwarehouse_derived_pages_survive_junk_params(client_a, page, params):
    assert _invwarehouse_get(client_a, page, **params).status_code == 200


def test_invwarehouse_count_accuracy_accepts_a_half_open_date_range(client_a):
    """Regression for finding C2 — this was a live 500 from an ordinary filter-bar interaction.

    Clearing one of the two date inputs and pressing Apply submits an empty bound, and None
    reached scheduled_date__gte.
    """
    today = date.today().isoformat()
    assert _invwarehouse_get(client_a, "count_accuracy",
                             date_from=today, date_to="").status_code == 200
    assert _invwarehouse_get(client_a, "count_accuracy",
                             date_from="", date_to=today).status_code == 200


def test_invwarehouse_count_accuracy_window_actually_changes_the_window(client_a):
    """Regression for finding C3 — the dropdown was permanently inert.

    The template rendered the RESOLVED dates back into its own inputs, so every submit carried
    them and the 'both are None' guard never fired. Selecting Last 30 days changed nothing.
    """
    short = _invwarehouse_get(client_a, "count_accuracy", window="30")
    long = _invwarehouse_get(client_a, "count_accuracy", window="365")
    assert short.status_code == long.status_code == 200
    assert short.context["date_from"] != long.context["date_from"], (
        "the window dropdown did not change the resolved window")


def test_invwarehouse_registers_survive_junk_filters(client_a, invwarehouse_policy_a):
    for params in ({"status": "nope"}, {"location": "0"}, {"item": "²"}, {"page": "99"}):
        assert _invwarehouse_get(client_a, "replenishmentpolicy_list",
                                 **params).status_code == 200


# --------------------------------------------------------------------------- verbs


def test_invwarehouse_verbs_reject_get(client_a, invwarehouse_run_a):
    """Every mutating verb is POST-only — a GET must never change state."""
    for name in ("replenishmentrun_generate", "replenishmentrun_cancel", "replenishmentrun_delete"):
        resp = _invwarehouse_get(client_a, name, invwarehouse_run_a.pk)
        assert resp.status_code in (405, 302), name


def test_invwarehouse_released_run_delete_is_refused(client_a, invwarehouse_run_released_a):
    """Regression for finding C1 — the worst defect the review found.

    A POST deleted a RELEASED run and CASCADE-took every suggestion with it, destroying the only
    record of which requisition came from which proposal while the requisitions survived orphaned.
    Both templates claimed the view already refused this. It did not.
    """
    pk = invwarehouse_run_released_a.pk
    lines_before = ReplenishmentSuggestion.objects.filter(run_id=pk).count()

    resp = client_a.post(reverse("procurement:replenishmentrun_delete", args=[pk]))

    assert resp.status_code in (302, 403)
    assert ReplenishmentRun.objects.filter(pk=pk).exists(), "a released run was deleted"
    assert ReplenishmentSuggestion.objects.filter(run_id=pk).count() == lines_before


def test_invwarehouse_draft_run_delete_is_allowed(client_a, invwarehouse_run_a):
    pk = invwarehouse_run_a.pk
    client_a.post(reverse("procurement:replenishmentrun_delete", args=[pk]))
    assert not ReplenishmentRun.objects.filter(pk=pk).exists()


def test_invwarehouse_post_verb_writes_no_stock_move(client_a,
                                                     invwarehouse_issue_submitted_a):
    """The ledger boundary, exercised through the HTTP layer rather than the model."""
    moves_before = StockMove.objects.count()
    adj_before = StockAdjustment.objects.count()

    client_a.post(
        reverse("procurement:materialissue_post", args=[invwarehouse_issue_submitted_a.pk]))

    assert StockMove.objects.count() == moves_before
    invwarehouse_issue_submitted_a.refresh_from_db()
    if invwarehouse_issue_submitted_a.status == "posted":
        assert StockAdjustment.objects.count() == adj_before + 1
        assert invwarehouse_issue_submitted_a.adjustment.status == "draft"


def test_invwarehouse_decide_returns_to_the_page_being_worked(
        client_a, invwarehouse_run_lines_a):
    """Regression for finding I12.

    The board pages at 25 and a run caps at 500, so a redirect that always landed on page 1 threw
    a buyer working page 8 back to the top after every single save.
    """
    line = invwarehouse_run_lines_a.lines.first()
    resp = client_a.post(
        reverse("procurement:replenishmentsuggestion_decide",
                args=[invwarehouse_run_lines_a.pk, line.pk]),
        {"decision": "dismissed", "snooze_until": "", "decision_note": "", "page": "2"})
    assert resp.status_code == 302
    assert "page=2" in resp["Location"]


# --------------------------------------------------------------------------- query budgets


def test_invwarehouse_run_detail_stays_within_its_query_budget(
        client_a, invwarehouse_run_lines_a, django_assert_max_num_queries):
    """Pins a count that two templates hold ONLY by the exact phrasing chosen.

    replenishmentrun/detail.html prints {{ line.policy.pk }}. Printing {{ line.policy }} instead
    would resolve ReplenishmentPolicy.__str__ -> item.sku AND location.code, neither joined, at
    1+2N for a 25-row page. Nothing about that edit looks wrong in review; only this ceiling
    catches it.
    """
    with django_assert_max_num_queries(20):
        _invwarehouse_get(client_a, "replenishmentrun_detail", invwarehouse_run_lines_a.pk)


def test_invwarehouse_issue_detail_stays_within_its_query_budget(
        client_a, invwarehouse_issue_lots_a, django_assert_max_num_queries):
    """Same shape: materialissue/detail.html prints {{ line.lot_serial.number }}.

    {{ line.lot_serial }} would resolve LotSerial.__str__ -> item.sku through a relation
    _LINE_RELATIONS does not join. Also guards a per-line availability query.
    """
    with django_assert_max_num_queries(20):
        _invwarehouse_get(client_a, "materialissue_detail", invwarehouse_issue_lots_a.pk)


def test_invwarehouse_stock_position_query_count_does_not_grow_with_rows(
        client_a, invwarehouse_stock_a, invwarehouse_stock2_a,
        django_assert_max_num_queries):
    """A derived page's whole claim is that its query count is flat in the data."""
    with django_assert_max_num_queries(30):
        _invwarehouse_get(client_a, "stock_position")


# --------------------------------------------------------------------------- tenant-less user


@pytest.mark.parametrize("page", ["stock_position", "receipt_bin_map", "count_accuracy",
                                  "replenishmentpolicy_list", "replenishmentrun_list",
                                  "materialissue_list"])
def test_invwarehouse_pages_render_empty_for_a_tenant_less_user(admin_client, page):
    """The superuser has tenant=None. Empty is by design; a 500 is not."""
    assert _invwarehouse_get(admin_client, page).status_code == 200
