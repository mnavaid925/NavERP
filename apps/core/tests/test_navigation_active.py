"""Sidebar active-state ("most-specific match wins") tests for ``apps.core.navigation``.

Regression cover for the bug where several sub-module bullets sharing one route (3.5 Job
Requisition: Job Posting / Budget Management / Requisition Tracking, + Approval Workflow via a
query string) ALL highlighted at once. ``_mark_active`` now scores each bullet against the request's
query string so a ``?query`` bullet highlights only on its own filtered page; route-only and
``#fragment`` bullets (which the server can't distinguish) still tie/co-highlight by design.
"""
from types import SimpleNamespace

from apps.core.navigation import _EXACT_ROUTE, _match_score, resolve_nav


def _req(view_name, **get):
    """A minimal stand-in for the request ``resolve_nav`` reads (resolver view name + GET)."""
    return SimpleNamespace(resolver_match=SimpleNamespace(view_name=view_name), GET=dict(get))


def _features(request, sub_num):
    """{feature label: is_active} for the given ``N.M`` sub-module in the rendered nav."""
    for section in resolve_nav(request):
        for sub in section.get("submodules", []):
            if sub["label"].startswith(sub_num + " "):
                return {f["label"]: f["is_active"] for f in sub["features"]}
    return {}


def _active(request, sub_num):
    return {label for label, on in _features(request, sub_num).items() if on}


# --------------------------------------------------------------- _match_score unit behavior
def test_match_score_exact_route_is_exact_constant():
    assert _match_score("hrm:jobrequisition_list", "hrm:jobrequisition_list", {}) == _EXACT_ROUTE


def test_match_score_fragment_scores_as_exact_route():
    # fragments never reach the server → treated as an exact route-only match (no query)
    assert _match_score("accounting:accounting_dashboard#cash-flow",
                        "accounting:accounting_dashboard", {}) == _EXACT_ROUTE


def test_match_score_query_match_beats_bare_exact():
    bare = _match_score("hrm:jobrequisition_list", "hrm:jobrequisition_list", {"status": "posted"})
    filtered = _match_score("hrm:jobrequisition_list?status=posted",
                            "hrm:jobrequisition_list", {"status": "posted"})
    assert filtered == _EXACT_ROUTE + 1 and filtered > bare == _EXACT_ROUTE


def test_match_score_query_conflict_disqualifies():
    assert _match_score("hrm:jobrequisition_list?status=posted",
                        "hrm:jobrequisition_list", {"status": "draft"}) == -1
    # query bullet on a bare request (param absent) is also disqualified
    assert _match_score("hrm:jobrequisition_list?status=posted",
                        "hrm:jobrequisition_list", {}) == -1


def test_match_score_wrong_route_is_minus_one():
    assert _match_score("hrm:jobrequisition_list", "hrm:employee_list", {}) == -1


def test_match_score_subroute_scores_below_exact():
    # a CRUD sub-route match is a positive prefix score (len of base) but strictly below an exact match
    sub = _match_score("hrm:jobrequisition_list", "hrm:jobrequisition_detail", {})
    assert 0 < sub < _EXACT_ROUTE


def test_match_score_longest_prefix_wins():
    # the longer (more specific) base outscores the shorter one on a compound-entity sub-route
    longer = _match_score("accounting:payment_term_list", "accounting:payment_term_detail", {})
    shorter = _match_score("accounting:payment_list", "accounting:payment_term_detail", {})
    assert 0 < shorter < longer < _EXACT_ROUTE


# --------------------------------------------------------------- 3.5 the reported bug
def test_3_5_job_posting_click_highlights_only_job_posting():
    # the exact scenario the user hit: clicking "Job Posting" lands on ?status=posted
    active = _active(_req("hrm:jobrequisition_list", status="posted"), "3.5")
    assert active == {"Job Posting"}, active


def test_3_5_approval_workflow_highlights_alone():
    active = _active(_req("hrm:jobrequisition_list", status="pending_approval"), "3.5")
    assert active == {"Approval Workflow"}, active


def test_3_5_bare_list_only_full_list_bullets():
    # the unfiltered list serves Budget Management + Requisition Tracking (both the full list);
    # the two ?status= bullets must NOT light up here
    active = _active(_req("hrm:jobrequisition_list"), "3.5")
    assert active == {"Budget Management", "Requisition Tracking"}, active


def test_3_5_job_templates_separate_page():
    active = _active(_req("hrm:jobdescriptiontemplate_list"), "3.5")
    assert active == {"Job Templates"}, active


def test_3_5_detail_subroute_lights_full_list_bullets():
    active = _active(_req("hrm:jobrequisition_detail"), "3.5")
    assert active == {"Budget Management", "Requisition Tracking"}, active


# --------------------------------------------------------------- 2.15 integration categories now precise
def test_2_15_category_filter_highlights_one():
    active = _active(_req("accounting:integration_list", category="banking"), "2.15")
    assert active == {"Banking APIs"}, active


def test_2_15_bare_list_highlights_custom_api_only():
    active = _active(_req("accounting:integration_list"), "2.15")
    assert active == {"Custom API"}, active


# --------------------------------------------------------------- 2.1 #fragment widgets still co-highlight
def test_2_1_dashboard_widgets_all_highlight():
    # fragments are invisible server-side, so all four widgets tie on the dashboard route (by design)
    active = _active(_req("accounting:accounting_dashboard"), "2.1")
    for label in ("Executive Summary", "Cash Flow Widget", "Alert Center", "Quick Actions"):
        assert label in active, (label, active)


# --------------------------------------------------------------- a plain single-bullet sub-module
def test_single_bullet_module_highlights():
    active = _active(_req("hrm:publicholiday_list"), "3.12")
    assert "Holiday Calendar" in active


# --------------- sibling-route prefix collisions (exact route beats a prefix sub-route match) -------
def test_2_3_payment_schedule_does_not_light_payment_processing():
    # payment_list base "accounting:payment" is a prefix of payment_schedule — must NOT co-highlight
    active = _active(_req("accounting:payment_schedule"), "2.3")
    assert "Payment Scheduling" in active
    assert "Payment Processing" not in active, active


def test_2_3_payment_term_list_does_not_light_payment_processing():
    active = _active(_req("accounting:payment_term_list"), "2.3")
    assert "Early Payment Discounts" in active
    assert "Payment Processing" not in active, active


def test_2_13_budget_variance_does_not_light_budget_list_bullets():
    active = _active(_req("accounting:budget_variance"), "2.13")
    assert "Variance Analysis" in active
    assert "Budget Creation" not in active and "Version Control" not in active, active


def test_3_1_employee_document_list_does_not_light_employee_list_bullets():
    active = _active(_req("hrm:employee_document_list"), "3.1")
    assert "Document Management" in active
    for label in ("Employee Directory", "Employee Profile", "Employment Details"):
        assert label not in active, (label, active)


def test_3_1_employee_lifecycle_list_isolated():
    active = _active(_req("hrm:employee_lifecycle_list"), "3.1")
    assert "Employee Lifecycle" in active
    assert "Employee Directory" not in active, active


def test_compound_entity_detail_longest_prefix_wins():
    # on payment_term_detail the longer base (payment_term) beats the shorter (payment) prefix —
    # this is the case the action-allowlist approach could not reach generically
    active = _active(_req("accounting:payment_term_detail"), "2.3")
    assert "Early Payment Discounts" in active
    assert "Payment Processing" not in active, active


def test_crud_detail_with_no_own_bullet_falls_back_to_list():
    # a plain detail sub-route with no bullet of its own still lights its parent list bullet
    active = _active(_req("hrm:leaverequest_detail"), "3.10")
    assert "Leave Application" in active or "Leave Calendar" in active, active
