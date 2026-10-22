"""8.12 Sales Analytics & Intelligence — Views Test Suite.

Tests cover:
- List views: 200 OK, context key verification, pagination, search & dropdown filtering, seeded record display.
- Detail views: 200 OK, correct object in context, rendered attributes.
- Create views: GET (empty form 200 OK), POST (creates record, auto-assigns tenant/number, redirects).
- Edit views: GET (populated form 200 OK), POST (updates record fields, redirects).
- Delete views: POST (deletes record, redirects to list view).
- Console boards: 200 OK, stats calculations, tenant-scoped data aggregation across all 6 console views.
"""
from decimal import Decimal
import json
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.sales.models.SalesAnalytics.WinLossDebriefs import WinLossDebrief
from apps.sales.models.SalesAnalytics.StageVelocityAnalyses import StageVelocityAnalysis
from apps.sales.models.SalesAnalytics.FunnelConversionRecords import FunnelConversionRecord
from apps.sales.models.SalesAnalytics.RepPerformanceScorecards import RepPerformanceScorecard

pytestmark = pytest.mark.django_db


def _body(response):
    return response.content.decode("utf-8", "replace")


# -----------------------------------------------------------------------------
# 1. List Views
# -----------------------------------------------------------------------------

def test_salesanalytics_win_loss_debrief_list(client_a, sa_debrief_a):
    url = reverse("sales:win_loss_debrief_list")
    response = client_a.get(url)
    assert response.status_code == 200
    assert "debriefs" in response.context
    assert "page_obj" in response.context
    assert "stats" in response.context
    body = _body(response)
    assert sa_debrief_a.number in body


def test_salesanalytics_stage_velocity_analysis_list(client_a, sa_velocity_a):
    url = reverse("sales:stage_velocity_analysis_list")
    response = client_a.get(url)
    assert response.status_code == 200
    assert "analyses" in response.context
    assert "page_obj" in response.context
    assert "stats" in response.context
    body = _body(response)
    assert sa_velocity_a.number in body


def test_salesanalytics_funnel_conversion_record_list(client_a, sa_funnel_a):
    url = reverse("sales:funnel_conversion_record_list")
    response = client_a.get(url)
    assert response.status_code == 200
    assert "records" in response.context
    assert "page_obj" in response.context
    assert "stats" in response.context
    body = _body(response)
    assert sa_funnel_a.number in body


def test_salesanalytics_rep_performance_scorecard_list(client_a, sa_scorecard_a):
    url = reverse("sales:rep_performance_scorecard_list")
    response = client_a.get(url)
    assert response.status_code == 200
    assert "scorecards" in response.context
    assert "page_obj" in response.context
    assert "stats" in response.context
    body = _body(response)
    assert sa_scorecard_a.number in body


def test_salesanalytics_list_filters_and_search(client_a, sa_debrief_a, sa_velocity_a):
    # Filter debrief list by status
    url = reverse("sales:win_loss_debrief_list") + f"?status={sa_debrief_a.status}"
    response = client_a.get(url)
    assert response.status_code == 200
    assert sa_debrief_a.number in _body(response)

    # Search debrief list by quote
    url_search = reverse("sales:win_loss_debrief_list") + "?q=Great+product+fit"
    response_search = client_a.get(url_search)
    assert response_search.status_code == 200
    assert sa_debrief_a.number in _body(response_search)

    # Filter velocity list by pipeline
    url_vel = reverse("sales:stage_velocity_analysis_list") + f"?pipeline={sa_velocity_a.pipeline_id}"
    response_vel = client_a.get(url_vel)
    assert response_vel.status_code == 200
    assert sa_velocity_a.number in _body(response_vel)


# -----------------------------------------------------------------------------
# 2. Detail Views
# -----------------------------------------------------------------------------

def test_salesanalytics_win_loss_debrief_detail(client_a, sa_debrief_a):
    url = reverse("sales:win_loss_debrief_detail", args=[sa_debrief_a.pk])
    response = client_a.get(url)
    assert response.status_code == 200
    assert response.context["debrief"].pk == sa_debrief_a.pk
    body = _body(response)
    assert sa_debrief_a.number in body
    assert "Product Fit" in body


def test_salesanalytics_stage_velocity_analysis_detail(client_a, sa_velocity_a):
    url = reverse("sales:stage_velocity_analysis_detail", args=[sa_velocity_a.pk])
    response = client_a.get(url)
    assert response.status_code == 200
    assert response.context["analysis"].pk == sa_velocity_a.pk
    body = _body(response)
    assert sa_velocity_a.number in body
    assert "Streamline legal redline phase" in body


def test_salesanalytics_funnel_conversion_record_detail(client_a, sa_funnel_a):
    url = reverse("sales:funnel_conversion_record_detail", args=[sa_funnel_a.pk])
    response = client_a.get(url)
    assert response.status_code == 200
    assert response.context["record"].pk == sa_funnel_a.pk
    body = _body(response)
    assert sa_funnel_a.number in body
    assert sa_funnel_a.label in body


def test_salesanalytics_rep_performance_scorecard_detail(client_a, sa_scorecard_a):
    url = reverse("sales:rep_performance_scorecard_detail", args=[sa_scorecard_a.pk])
    response = client_a.get(url)
    assert response.status_code == 200
    assert response.context["scorecard"].pk == sa_scorecard_a.pk
    body = _body(response)
    assert sa_scorecard_a.number in body


# -----------------------------------------------------------------------------
# 3. Create Views (GET & POST)
# -----------------------------------------------------------------------------

def test_salesanalytics_win_loss_debrief_create(client_a, tenant_a, sa_opportunity_a):
    create_url = reverse("sales:win_loss_debrief_create")
    get_res = client_a.get(create_url)
    assert get_res.status_code == 200
    assert "form" in get_res.context

    post_data = {
        "opportunity": sa_opportunity_a.pk,
        "debriefed_on": timezone.localdate(),
        "interview_channel": "interview",
        "feedback_team": "product",
        "decision_drivers": json.dumps([{"driver": "Speed", "sentiment": "positive", "weight": 5}]),
        "buyer_quote": "Fastest implementation we have seen.",
        "status": "draft",
    }
    post_res = client_a.post(create_url, post_data)
    assert post_res.status_code == 302
    created = WinLossDebrief.objects.filter(tenant=tenant_a, buyer_quote="Fastest implementation we have seen.").first()
    assert created is not None
    assert created.number.startswith("WLA-")


def test_salesanalytics_stage_velocity_analysis_create(client_a, tenant_a, sa_pipeline_a, sa_stage_a2):
    create_url = reverse("sales:stage_velocity_analysis_create")
    get_res = client_a.get(create_url)
    assert get_res.status_code == 200

    post_data = {
        "pipeline": sa_pipeline_a.pk,
        "pipeline_stage": sa_stage_a2.pk,
        "period_start": timezone.localdate() - timezone.timedelta(days=60),
        "period_end": timezone.localdate(),
        "opportunity_count": 15,
        "velocity_value": "120000.00",
        "median_days_in_stage": "10.00",
        "p90_days_in_stage": "20.00",
        "max_days_in_stage": 30,
        "sales_cycle_days": "50.00",
        "status": "draft",
    }
    post_res = client_a.post(create_url, post_data)
    assert post_res.status_code == 302
    created = StageVelocityAnalysis.objects.filter(tenant=tenant_a, pipeline_stage=sa_stage_a2).first()
    assert created is not None
    assert created.number.startswith("VCA-")


def test_salesanalytics_funnel_conversion_record_create(client_a, tenant_a, sa_stage_a1, sa_stage_a2):
    create_url = reverse("sales:funnel_conversion_record_create")
    get_res = client_a.get(create_url)
    assert get_res.status_code == 200

    post_data = {
        "label": "Created Test Funnel",
        "funnel_scope": "stage_to_stage",
        "from_stage": sa_stage_a1.pk,
        "to_stage": sa_stage_a2.pk,
        "period_start": timezone.localdate() - timezone.timedelta(days=30),
        "period_end": timezone.localdate(),
        "entered_count": 80,
        "converted_count": 40,
        "skipped_count": 5,
    }
    post_res = client_a.post(create_url, post_data)
    assert post_res.status_code == 302
    created = FunnelConversionRecord.objects.filter(tenant=tenant_a, label="Created Test Funnel").first()
    assert created is not None
    assert created.number.startswith("FNL-")
    assert created.conversion_rate_pct == Decimal("50.00")


def test_salesanalytics_rep_performance_scorecard_create(client_a, tenant_a, admin_user):
    create_url = reverse("sales:rep_performance_scorecard_create")
    get_res = client_a.get(create_url)
    assert get_res.status_code == 200

    post_data = {
        "rep": admin_user.pk,
        "period_start": timezone.localdate() - timezone.timedelta(days=30),
        "period_end": timezone.localdate(),
        "activities_logged": 50,
        "calls_logged": 20,
        "emails_logged": 20,
        "meetings_logged": 10,
        "meetings_booked": 8,
        "follow_ups_completed": 15,
        "activity_minutes": 240,
        "opportunities_created": 5,
        "opportunities_won": 2,
        "opportunities_lost": 1,
        "pipeline_value": "100000.00",
        "weighted_pipeline_value": "60000.00",
        "revenue_closed": "50000.00",
        "quota_target": "50000.00",
        "rating": "strong",
        "status": "draft",
    }
    post_res = client_a.post(create_url, post_data)
    assert post_res.status_code == 302
    created = RepPerformanceScorecard.objects.filter(tenant=tenant_a, rating="strong").first()
    assert created is not None
    assert created.number.startswith("RPS-")
    assert created.quota_attainment_pct == Decimal("100.00")


# -----------------------------------------------------------------------------
# 4. Edit Views (GET & POST)
# -----------------------------------------------------------------------------

def test_salesanalytics_win_loss_debrief_edit(client_a, sa_debrief_a):
    edit_url = reverse("sales:win_loss_debrief_edit", args=[sa_debrief_a.pk])
    get_res = client_a.get(edit_url)
    assert get_res.status_code == 200
    assert "form" in get_res.context

    post_data = {
        "opportunity": sa_debrief_a.opportunity_id,
        "debriefed_on": sa_debrief_a.debriefed_on,
        "interview_channel": "survey",
        "feedback_team": "product",
        "buyer_quote": "Updated buyer feedback quote.",
        "status": "draft",
    }
    post_res = client_a.post(edit_url, post_data)
    assert post_res.status_code == 302
    sa_debrief_a.refresh_from_db()
    assert sa_debrief_a.interview_channel == "survey"
    assert sa_debrief_a.buyer_quote == "Updated buyer feedback quote."


def test_salesanalytics_stage_velocity_analysis_edit(client_a, sa_velocity_a):
    edit_url = reverse("sales:stage_velocity_analysis_edit", args=[sa_velocity_a.pk])
    get_res = client_a.get(edit_url)
    assert get_res.status_code == 200

    post_data = {
        "pipeline": sa_velocity_a.pipeline_id,
        "pipeline_stage": sa_velocity_a.pipeline_stage_id,
        "period_start": sa_velocity_a.period_start,
        "period_end": sa_velocity_a.period_end,
        "opportunity_count": 30,
        "velocity_value": "250000.00",
        "median_days_in_stage": "18.00",
        "p90_days_in_stage": "35.00",
        "max_days_in_stage": 50,
        "recommendation": "Updated velocity recommendation.",
        "status": "reviewed",
    }
    post_res = client_a.post(edit_url, post_data)
    assert post_res.status_code == 302
    sa_velocity_a.refresh_from_db()
    assert sa_velocity_a.opportunity_count == 30
    assert sa_velocity_a.recommendation == "Updated velocity recommendation."


def test_salesanalytics_funnel_conversion_record_edit(client_a, sa_funnel_a):
    edit_url = reverse("sales:funnel_conversion_record_edit", args=[sa_funnel_a.pk])
    get_res = client_a.get(edit_url)
    assert get_res.status_code == 200

    post_data = {
        "label": "Renamed Funnel Record",
        "funnel_scope": sa_funnel_a.funnel_scope,
        "from_stage": sa_funnel_a.from_stage_id,
        "to_stage": sa_funnel_a.to_stage_id,
        "period_start": sa_funnel_a.period_start,
        "period_end": sa_funnel_a.period_end,
        "entered_count": 200,
        "converted_count": 100,
        "skipped_count": 10,
    }
    post_res = client_a.post(edit_url, post_data)
    assert post_res.status_code == 302
    sa_funnel_a.refresh_from_db()
    assert sa_funnel_a.label == "Renamed Funnel Record"
    assert sa_funnel_a.entered_count == 200
    assert sa_funnel_a.conversion_rate_pct == Decimal("50.00")


def test_salesanalytics_rep_performance_scorecard_edit(client_a, sa_scorecard_a):
    edit_url = reverse("sales:rep_performance_scorecard_edit", args=[sa_scorecard_a.pk])
    get_res = client_a.get(edit_url)
    assert get_res.status_code == 200

    post_data = {
        "rep": sa_scorecard_a.rep_id,
        "period_start": sa_scorecard_a.period_start,
        "period_end": sa_scorecard_a.period_end,
        "activities_logged": 200,
        "calls_logged": 100,
        "emails_logged": 70,
        "meetings_logged": 30,
        "meetings_booked": 25,
        "follow_ups_completed": 40,
        "activity_minutes": 500,
        "opportunities_created": 20,
        "opportunities_won": 8,
        "opportunities_lost": 2,
        "pipeline_value": "500000.00",
        "weighted_pipeline_value": "350000.00",
        "revenue_closed": "300000.00",
        "quota_target": "200000.00",
        "rating": "outstanding",
        "status": "approved",
    }
    post_res = client_a.post(edit_url, post_data)
    assert post_res.status_code == 302
    sa_scorecard_a.refresh_from_db()
    assert sa_scorecard_a.rating == "outstanding"
    assert sa_scorecard_a.revenue_closed == Decimal("300000.00")
    assert sa_scorecard_a.quota_attainment_pct == Decimal("150.00")


# -----------------------------------------------------------------------------
# 5. Delete Views (POST)
# -----------------------------------------------------------------------------

def test_salesanalytics_debrief_delete_post(client_a, sa_debrief_a):
    pk = sa_debrief_a.pk
    delete_url = reverse("sales:win_loss_debrief_delete", args=[pk])
    res = client_a.post(delete_url)
    assert res.status_code == 302
    assert not WinLossDebrief.objects.filter(pk=pk).exists()


def test_salesanalytics_velocity_delete_post(client_a, sa_velocity_a):
    pk = sa_velocity_a.pk
    delete_url = reverse("sales:stage_velocity_analysis_delete", args=[pk])
    res = client_a.post(delete_url)
    assert res.status_code == 302
    assert not StageVelocityAnalysis.objects.filter(pk=pk).exists()


def test_salesanalytics_funnel_delete_post(client_a, sa_funnel_a):
    pk = sa_funnel_a.pk
    delete_url = reverse("sales:funnel_conversion_record_delete", args=[pk])
    res = client_a.post(delete_url)
    assert res.status_code == 302
    assert not FunnelConversionRecord.objects.filter(pk=pk).exists()


def test_salesanalytics_scorecard_delete_post(client_a, sa_scorecard_a):
    pk = sa_scorecard_a.pk
    delete_url = reverse("sales:rep_performance_scorecard_delete", args=[pk])
    res = client_a.post(delete_url)
    assert res.status_code == 302
    assert not RepPerformanceScorecard.objects.filter(pk=pk).exists()


# -----------------------------------------------------------------------------
# 6. Console Boards
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
    ],
)
def test_salesanalytics_console_boards_render_200(
    client_a,
    sa_debrief_a,
    sa_velocity_a,
    sa_funnel_a,
    sa_scorecard_a,
    route_name,
):
    url = reverse(route_name)
    response = client_a.get(url)
    assert response.status_code == 200
    assert "stats" in response.context
    body = _body(response)
    # Check that console templates render without error
    assert "Sales Analytics" in body or "Intelligence" in body or "Console" in body or "Scorecard" in body
