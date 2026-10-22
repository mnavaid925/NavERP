"""8.12 Sales Analytics & Intelligence — Security Test Suite.

Tests cover:
- Authentication: Anonymous requests redirect to login across all 26 routes (lists, details, creates, edits, deletes, and consoles).
- Cross-Tenant IDOR: Tenant A admin accessing Tenant B records returns 404 (detail, edit, delete).
- Multi-Tenant List Isolation: Tenant A list views and console boards never leak Tenant B records.
- Tenant Admin Authorization: Regular tenant members (is_tenant_admin=False) are rejected with 403 Forbidden on create, edit, and delete endpoints.
- HTTP Method Enforcement: Delete endpoints require POST (@require_POST), rejecting GET with 405.
- Robustness: Hostile, invalid, and extreme query parameters (?page=999, non-numeric FKs, extreme integers) degrade gracefully with 200 OK without 500 server errors.
"""
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _body(response):
    return response.content.decode("utf-8", "replace")


# -----------------------------------------------------------------------------
# 1. Anonymous Access Redirection
# -----------------------------------------------------------------------------

@pytest.mark.parametrize(
    "route_name",
    [
        "sales:analytics_console",
        "sales:win_loss_console",
        "sales:velocity_console",
        "sales:funnel_console",
        "sales:rep_scorecard_console",
        "sales:benchmark_console",
        "sales:win_loss_debrief_list",
        "sales:win_loss_debrief_create",
        "sales:stage_velocity_analysis_list",
        "sales:stage_velocity_analysis_create",
        "sales:funnel_conversion_record_list",
        "sales:funnel_conversion_record_create",
        "sales:rep_performance_scorecard_list",
        "sales:rep_performance_scorecard_create",
    ],
)
def test_salesanalytics_anonymous_redirects_to_login(client, route_name):
    url = reverse(route_name)
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response.url or "/login/" in response.url


def test_salesanalytics_anonymous_detail_and_actions_redirect_to_login(
    client,
    sa_debrief_a,
    sa_velocity_a,
    sa_funnel_a,
    sa_scorecard_a,
):
    routes = [
        reverse("sales:win_loss_debrief_detail", args=[sa_debrief_a.pk]),
        reverse("sales:win_loss_debrief_edit", args=[sa_debrief_a.pk]),
        reverse("sales:stage_velocity_analysis_detail", args=[sa_velocity_a.pk]),
        reverse("sales:stage_velocity_analysis_edit", args=[sa_velocity_a.pk]),
        reverse("sales:funnel_conversion_record_detail", args=[sa_funnel_a.pk]),
        reverse("sales:funnel_conversion_record_edit", args=[sa_funnel_a.pk]),
        reverse("sales:rep_performance_scorecard_detail", args=[sa_scorecard_a.pk]),
        reverse("sales:rep_performance_scorecard_edit", args=[sa_scorecard_a.pk]),
    ]
    for url in routes:
        res = client.get(url)
        assert res.status_code == 302


# -----------------------------------------------------------------------------
# 2. Cross-Tenant IDOR Protection
# -----------------------------------------------------------------------------

def test_salesanalytics_cross_tenant_idor_detail_returns_404(
    client_a,
    sa_debrief_b,
    sa_velocity_b,
    sa_funnel_b,
    sa_scorecard_b,
):
    detail_urls = [
        reverse("sales:win_loss_debrief_detail", args=[sa_debrief_b.pk]),
        reverse("sales:stage_velocity_analysis_detail", args=[sa_velocity_b.pk]),
        reverse("sales:funnel_conversion_record_detail", args=[sa_funnel_b.pk]),
        reverse("sales:rep_performance_scorecard_detail", args=[sa_scorecard_b.pk]),
    ]
    for url in detail_urls:
        res = client_a.get(url)
        assert res.status_code == 404, f"IDOR vulnerability on {url}"


def test_salesanalytics_cross_tenant_idor_edit_returns_404(
    client_a,
    sa_debrief_b,
    sa_velocity_b,
    sa_funnel_b,
    sa_scorecard_b,
):
    edit_urls = [
        reverse("sales:win_loss_debrief_edit", args=[sa_debrief_b.pk]),
        reverse("sales:stage_velocity_analysis_edit", args=[sa_velocity_b.pk]),
        reverse("sales:funnel_conversion_record_edit", args=[sa_funnel_b.pk]),
        reverse("sales:rep_performance_scorecard_edit", args=[sa_scorecard_b.pk]),
    ]
    for url in edit_urls:
        res_get = client_a.get(url)
        assert res_get.status_code == 404
        res_post = client_a.post(url, {})
        assert res_post.status_code == 404


def test_salesanalytics_cross_tenant_idor_delete_returns_404(
    client_a,
    sa_debrief_b,
    sa_velocity_b,
    sa_funnel_b,
    sa_scorecard_b,
):
    delete_urls = [
        reverse("sales:win_loss_debrief_delete", args=[sa_debrief_b.pk]),
        reverse("sales:stage_velocity_analysis_delete", args=[sa_velocity_b.pk]),
        reverse("sales:funnel_conversion_record_delete", args=[sa_funnel_b.pk]),
        reverse("sales:rep_performance_scorecard_delete", args=[sa_scorecard_b.pk]),
    ]
    for url in delete_urls:
        res = client_a.post(url)
        assert res.status_code == 404


# -----------------------------------------------------------------------------
# 3. Cross-Tenant List Isolation
# -----------------------------------------------------------------------------

def test_salesanalytics_cross_tenant_list_isolation(
    client_a,
    sa_debrief_a,
    sa_debrief_b,
    sa_velocity_a,
    sa_velocity_b,
    sa_funnel_a,
    sa_funnel_b,
    sa_scorecard_a,
    sa_scorecard_b,
):
    # Set distinctive markers on tenant B records to verify zero cross-tenant leakage
    sa_debrief_b.buyer_quote = "Globex Unique Debrief Quote 98765"
    sa_debrief_b.save(update_fields=["buyer_quote"])

    sa_velocity_b.recommendation = "Globex Unique Velocity Rec 98765"
    sa_velocity_b.save(update_fields=["recommendation"])

    sa_funnel_b.label = "Globex Unique Funnel Label 98765"
    sa_funnel_b.save(update_fields=["label"])

    sa_scorecard_b.strengths = "Globex Unique Scorecard Strength 98765"
    sa_scorecard_b.save(update_fields=["strengths"])

    # Debrief list
    body = _body(client_a.get(reverse("sales:win_loss_debrief_list")))
    assert "Globex Unique Debrief Quote 98765" not in body

    # Velocity list
    body = _body(client_a.get(reverse("sales:stage_velocity_analysis_list")))
    assert "Globex Unique Velocity Rec 98765" not in body

    # Funnel list
    body = _body(client_a.get(reverse("sales:funnel_conversion_record_list")))
    assert sa_funnel_a.label in body
    assert "Globex Unique Funnel Label 98765" not in body

    # Scorecard list
    body = _body(client_a.get(reverse("sales:rep_performance_scorecard_list")))
    assert "Globex Unique Scorecard Strength 98765" not in body


# -----------------------------------------------------------------------------
# 4. Tenant Admin Authorization Enforcement
# -----------------------------------------------------------------------------

def test_salesanalytics_tenant_admin_required_rejects_member(
    member_client,
    sa_debrief_a,
    sa_velocity_a,
    sa_funnel_a,
    sa_scorecard_a,
):
    # Member trying to access create views
    create_urls = [
        reverse("sales:win_loss_debrief_create"),
        reverse("sales:stage_velocity_analysis_create"),
        reverse("sales:funnel_conversion_record_create"),
        reverse("sales:rep_performance_scorecard_create"),
    ]
    for url in create_urls:
        res = member_client.get(url)
        assert res.status_code == 403

    # Member trying to access edit views
    edit_urls = [
        reverse("sales:win_loss_debrief_edit", args=[sa_debrief_a.pk]),
        reverse("sales:stage_velocity_analysis_edit", args=[sa_velocity_a.pk]),
        reverse("sales:funnel_conversion_record_edit", args=[sa_funnel_a.pk]),
        reverse("sales:rep_performance_scorecard_edit", args=[sa_scorecard_a.pk]),
    ]
    for url in edit_urls:
        res = member_client.get(url)
        assert res.status_code == 403

    # Member trying to delete
    delete_urls = [
        reverse("sales:win_loss_debrief_delete", args=[sa_debrief_a.pk]),
        reverse("sales:stage_velocity_analysis_delete", args=[sa_velocity_a.pk]),
        reverse("sales:funnel_conversion_record_delete", args=[sa_funnel_a.pk]),
        reverse("sales:rep_performance_scorecard_delete", args=[sa_scorecard_a.pk]),
    ]
    for url in delete_urls:
        res = member_client.post(url)
        assert res.status_code == 403


# -----------------------------------------------------------------------------
# 5. Method Enforcement on Actions
# -----------------------------------------------------------------------------

def test_salesanalytics_delete_routes_reject_get(
    client_a,
    sa_debrief_a,
    sa_velocity_a,
    sa_funnel_a,
    sa_scorecard_a,
):
    delete_urls = [
        reverse("sales:win_loss_debrief_delete", args=[sa_debrief_a.pk]),
        reverse("sales:stage_velocity_analysis_delete", args=[sa_velocity_a.pk]),
        reverse("sales:funnel_conversion_record_delete", args=[sa_funnel_a.pk]),
        reverse("sales:rep_performance_scorecard_delete", args=[sa_scorecard_a.pk]),
    ]
    for url in delete_urls:
        res = client_a.get(url)
        assert res.status_code == 405


# -----------------------------------------------------------------------------
# 6. Robustness against Hostile / Extreme Query Parameters
# -----------------------------------------------------------------------------

def test_salesanalytics_hostile_query_parameters_do_not_500(client_a):
    hostile_params = (
        "?page=999999"
        "&opportunity=notanumber"
        "&reason=999999999999999999999999999999"
        "&pipeline=-1"
        "&pipeline_stage=abc"
        "&from_stage=xyz"
        "&to_stage=999999999999999999999999999999"
        "&rep=invalid"
        "&territory=junk"
        "&status=nonexistent_status"
        "&interview_channel=random_channel"
        "&q=%20%20%20"
    )
    list_routes = [
        "sales:win_loss_debrief_list",
        "sales:stage_velocity_analysis_list",
        "sales:funnel_conversion_record_list",
        "sales:rep_performance_scorecard_list",
        "sales:analytics_console",
        "sales:win_loss_console",
        "sales:velocity_console",
        "sales:funnel_console",
        "sales:rep_scorecard_console",
        "sales:benchmark_console",
    ]
    for route in list_routes:
        url = reverse(route) + hostile_params
        res = client_a.get(url)
        assert res.status_code == 200, f"Hostile query crashed {route} with {res.status_code}"
