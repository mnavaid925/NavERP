"""Sales 8.13 Marketing Alignment & Attribution — View tests.

Verifies all 6 entity controllers, CRUD flows, status transitions, filtering,
search, pagination, and attribution console analytics calculations.
"""
from decimal import Decimal
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.sales.models.MarketingAlignment.AttributionTouchpoints import (
    AttributionTouchpoint,
)
from apps.sales.models.MarketingAlignment.CampaignAttributions import (
    CampaignAttribution,
)
from apps.sales.models.MarketingAlignment.ContentEngagements import (
    ContentEngagement,
)
from apps.sales.models.MarketingAlignment.MarketingEvents import (
    EventRegistration,
    MarketingEvent,
)
from apps.sales.models.MarketingAlignment.MqlHandoffs import MqlHandoff


# ==============================================================================
# Attribution Console View Tests
# ==============================================================================

@pytest.mark.django_db
def test_marketingalignment_console_view_get_default(
    client_a, ma_touchpoint_a, ma_attribution_a
):
    url = reverse("sales:marketing_attribution_console")
    response = client_a.get(url)
    assert response.status_code == 200
    assert "active_model" in response.context
    assert response.context["active_model"] == "first_touch"
    assert "stats" in response.context
    assert "total_touchpoints" in response.context["stats"]
    assert "total_attributed_revenue" in response.context["stats"]


@pytest.mark.django_db
def test_marketingalignment_console_view_filter_model(
    client_a, ma_touchpoint_a, ma_attribution_a
):
    url = reverse("sales:marketing_attribution_console")
    response = client_a.get(url, {"model": "linear"})
    assert response.status_code == 200
    assert response.context["active_model"] == "linear"
    assert response.context["active_model_label"] == "Linear (Multi-Touch)"


# ==============================================================================
# Attribution Touchpoints View Tests
# ==============================================================================

@pytest.mark.django_db
def test_marketingalignment_touchpoint_list_view(client_a, ma_touchpoint_a):
    url = reverse("sales:attribution_touchpoint_list")
    response = client_a.get(url)
    assert response.status_code == 200
    assert "touchpoints" in response.context
    assert "channel_choices" in response.context
    assert "position_choices" in response.context

    # Filter by channel
    resp_filtered = client_a.get(url, {"channel": "paid_search"})
    assert resp_filtered.status_code == 200
    assert len(resp_filtered.context["touchpoints"]) >= 1

    # Search by keyword
    resp_search = client_a.get(url, {"q": "ATB-"})
    assert resp_search.status_code == 200
    assert len(resp_search.context["touchpoints"]) >= 1


@pytest.mark.django_db
def test_marketingalignment_touchpoint_detail_view(client_a, ma_touchpoint_a):
    url = reverse("sales:attribution_touchpoint_detail", kwargs={"pk": ma_touchpoint_a.pk})
    response = client_a.get(url)
    assert response.status_code == 200
    assert response.context["obj"].pk == ma_touchpoint_a.pk


@pytest.mark.django_db
def test_marketingalignment_touchpoint_create_view_get_and_post(
    client_a, ma_campaign_a, ma_lead_a, ma_currency
):
    url = reverse("sales:attribution_touchpoint_create")
    # GET renders form
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200

    # POST creates
    post_data = {
        "campaign": ma_campaign_a.pk,
        "lead": ma_lead_a.pk,
        "channel": "email",
        "touch_type": "email_click",
        "touch_date": timezone.now().date(),
        "touch_position": "first",
        "cost": "12.00",
        "engagement_value": "80.00",
        "currency": ma_currency.pk,
        "source_reference": "newsletter-2026-q3",
    }
    resp_post = client_a.post(url, post_data)
    assert resp_post.status_code == 302
    created = AttributionTouchpoint.objects.latest("created_at")
    assert created.channel == "email"
    assert created.source_reference == "newsletter-2026-q3"


@pytest.mark.django_db
def test_marketingalignment_touchpoint_edit_view_get_and_post(client_a, ma_touchpoint_a):
    url = reverse("sales:attribution_touchpoint_edit", kwargs={"pk": ma_touchpoint_a.pk})
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200

    post_data = {
        "channel": ma_touchpoint_a.channel,
        "touch_type": ma_touchpoint_a.touch_type,
        "touch_date": ma_touchpoint_a.touch_date,
        "touch_position": "last",
        "cost": "45.00",
        "engagement_value": "300.00",
        "notes": "Updated to last touch position",
    }
    resp_post = client_a.post(url, post_data)
    assert resp_post.status_code == 302
    ma_touchpoint_a.refresh_from_db()
    assert ma_touchpoint_a.touch_position == "last"
    assert ma_touchpoint_a.cost == Decimal("45.00")


@pytest.mark.django_db
def test_marketingalignment_touchpoint_delete_view(client_a, ma_touchpoint_a):
    url = reverse("sales:attribution_touchpoint_delete", kwargs={"pk": ma_touchpoint_a.pk})
    # GET rejected by require_POST (405)
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405
    assert AttributionTouchpoint.objects.filter(pk=ma_touchpoint_a.pk).exists()

    # POST deletes
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert not AttributionTouchpoint.objects.filter(pk=ma_touchpoint_a.pk).exists()


# ==============================================================================
# Campaign Attributions View Tests
# ==============================================================================

@pytest.mark.django_db
def test_marketingalignment_campaign_attribution_list_view(client_a, ma_attribution_a):
    url = reverse("sales:campaign_attribution_list")
    response = client_a.get(url)
    assert response.status_code == 200
    assert "attributions" in response.context
    assert "model_choices" in response.context
    assert "status_choices" in response.context

    resp_filter = client_a.get(url, {"attribution_model": "first_touch"})
    assert resp_filter.status_code == 200
    assert len(resp_filter.context["attributions"]) >= 1


@pytest.mark.django_db
def test_marketingalignment_campaign_attribution_detail_view(client_a, ma_attribution_a):
    url = reverse("sales:campaign_attribution_detail", kwargs={"pk": ma_attribution_a.pk})
    response = client_a.get(url)
    assert response.status_code == 200
    assert response.context["obj"].pk == ma_attribution_a.pk


@pytest.mark.django_db
def test_marketingalignment_campaign_attribution_create_and_edit_view(
    client_a, ma_touchpoint_a, admin_user
):
    create_url = reverse("sales:campaign_attribution_create")
    post_data = {
        "touchpoint": ma_touchpoint_a.pk,
        "attribution_model": "linear",
        "credit_pct": "50.00",
        "attributed_revenue": "15000.00",
        "attributed_cost": "20.00",
        "status": "computed",
        "computed_on": timezone.now().date(),
        "computed_by": admin_user.pk,
    }
    resp_create = client_a.post(create_url, post_data)
    assert resp_create.status_code == 302
    attr = CampaignAttribution.objects.filter(touchpoint=ma_touchpoint_a, attribution_model="linear").first()
    assert attr is not None

    edit_url = reverse("sales:campaign_attribution_edit", kwargs={"pk": attr.pk})
    post_edit = {
        "touchpoint": ma_touchpoint_a.pk,
        "attribution_model": "linear",
        "credit_pct": "60.00",
        "attributed_revenue": "18000.00",
        "attributed_cost": "20.00",
        "status": "approved",
        "computed_on": timezone.now().date(),
        "computed_by": admin_user.pk,
    }
    resp_edit = client_a.post(edit_url, post_edit)
    assert resp_edit.status_code == 302
    attr.refresh_from_db()
    assert attr.credit_pct == Decimal("60.00")
    assert attr.status == "approved"


@pytest.mark.django_db
def test_marketingalignment_campaign_attribution_delete_view(client_a, ma_attribution_a):
    url = reverse("sales:campaign_attribution_delete", kwargs={"pk": ma_attribution_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not CampaignAttribution.objects.filter(pk=ma_attribution_a.pk).exists()


# ==============================================================================
# MQL Handoffs View Tests
# ==============================================================================

@pytest.mark.django_db
def test_marketingalignment_mql_handoff_list_view(client_a, ma_handoff_a):
    url = reverse("sales:mql_handoff_list")
    response = client_a.get(url)
    assert response.status_code == 200
    assert "handoffs" in response.context
    assert "status_choices" in response.context
    assert "source_choices" in response.context

    resp_filter = client_a.get(url, {"status": "pending"})
    assert resp_filter.status_code == 200
    assert len(resp_filter.context["handoffs"]) >= 1


@pytest.mark.django_db
def test_marketingalignment_mql_handoff_detail_view(client_a, ma_handoff_a):
    url = reverse("sales:mql_handoff_detail", kwargs={"pk": ma_handoff_a.pk})
    response = client_a.get(url)
    assert response.status_code == 200
    assert response.context["obj"].pk == ma_handoff_a.pk


@pytest.mark.django_db
def test_marketingalignment_mql_handoff_create_and_edit_view(
    client_a, ma_lead_a, ma_customer_a, admin_user, ma_currency
):
    now = timezone.now()
    create_url = reverse("sales:mql_handoff_create")
    post_data = {
        "lead": ma_lead_a.pk,
        "account": ma_customer_a.pk,
        "owner": admin_user.pk,
        "assigned_to": admin_user.pk,
        "source_kind": "inbound",
        "handoff_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "sla_due_at": (now + timezone.timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S"),
        "lead_score": 92,
        "estimated_value": "50000.00",
        "currency": ma_currency.pk,
    }
    resp_create = client_a.post(create_url, post_data)
    assert resp_create.status_code == 302
    created = MqlHandoff.objects.latest("created_at")
    assert created.source_kind == "inbound"
    assert created.status == "pending"

    edit_url = reverse("sales:mql_handoff_edit", kwargs={"pk": created.pk})
    post_edit = {
        "lead": ma_lead_a.pk,
        "account": ma_customer_a.pk,
        "owner": admin_user.pk,
        "assigned_to": admin_user.pk,
        "status": "pending",
        "source_kind": "inbound",
        "handoff_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "sla_due_at": (now + timezone.timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S"),
        "lead_score": 95,
        "estimated_value": "55000.00",
        "currency": ma_currency.pk,
        "notes": "Extended SLA window",
    }
    resp_edit = client_a.post(edit_url, post_edit)
    assert resp_edit.status_code == 302
    created.refresh_from_db()
    assert created.lead_score == 95


@pytest.mark.django_db
def test_marketingalignment_mql_handoff_delete_view(client_a, ma_handoff_a):
    url = reverse("sales:mql_handoff_delete", kwargs={"pk": ma_handoff_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not MqlHandoff.objects.filter(pk=ma_handoff_a.pk).exists()


@pytest.mark.django_db
def test_marketingalignment_mql_handoff_accept_and_reject_transitions(
    client_a, ma_handoff_a, ma_lead_a, ma_customer_a, admin_user, ma_currency
):
    now = timezone.now()
    edit_url = reverse("sales:mql_handoff_edit", kwargs={"pk": ma_handoff_a.pk})

    # Transition to accepted
    post_accept = {
        "lead": ma_lead_a.pk,
        "account": ma_customer_a.pk,
        "owner": admin_user.pk,
        "assigned_to": admin_user.pk,
        "status": "accepted",
        "source_kind": "inbound",
        "handoff_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "sla_due_at": (now + timezone.timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S"),
        "lead_score": ma_handoff_a.lead_score,
        "estimated_value": str(ma_handoff_a.estimated_value),
        "currency": ma_currency.pk,
        "acceptance_reason": "High quality enterprise lead",
    }
    resp_acc = client_a.post(edit_url, post_accept)
    assert resp_acc.status_code == 302
    ma_handoff_a.refresh_from_db()
    assert ma_handoff_a.status == "accepted"
    assert ma_handoff_a.acceptance_reason == "High quality enterprise lead"
    assert ma_handoff_a.responded_at is not None

    # Transition to rejected with reason
    post_reject = {
        "lead": ma_lead_a.pk,
        "account": ma_customer_a.pk,
        "owner": admin_user.pk,
        "assigned_to": admin_user.pk,
        "status": "rejected",
        "source_kind": "inbound",
        "handoff_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "sla_due_at": (now + timezone.timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S"),
        "lead_score": ma_handoff_a.lead_score,
        "estimated_value": str(ma_handoff_a.estimated_value),
        "currency": ma_currency.pk,
        "rejection_reason": "Budget already fully committed",
    }
    resp_rej = client_a.post(edit_url, post_reject)
    assert resp_rej.status_code == 302
    ma_handoff_a.refresh_from_db()
    assert ma_handoff_a.status == "rejected"
    assert ma_handoff_a.rejection_reason == "Budget already fully committed"


# ==============================================================================
# Content Engagements View Tests
# ==============================================================================

@pytest.mark.django_db
def test_marketingalignment_content_engagement_list_view(client_a, ma_engagement_a):
    url = reverse("sales:content_engagement_list")
    response = client_a.get(url)
    assert response.status_code == 200
    assert "engagements" in response.context
    assert "engagement_type_choices" in response.context
    assert "channel_choices" in response.context


@pytest.mark.django_db
def test_marketingalignment_content_engagement_detail_view(client_a, ma_engagement_a):
    url = reverse("sales:content_engagement_detail", kwargs={"pk": ma_engagement_a.pk})
    response = client_a.get(url)
    assert response.status_code == 200
    assert response.context["obj"].pk == ma_engagement_a.pk


@pytest.mark.django_db
def test_marketingalignment_content_engagement_create_edit_delete(
    client_a, ma_content_a, ma_customer_a, ma_lead_a, ma_currency
):
    now = timezone.now()
    create_url = reverse("sales:content_engagement_create")
    post_data = {
        "content": ma_content_a.pk,
        "account": ma_customer_a.pk,
        "lead": ma_lead_a.pk,
        "engagement_type": "download",
        "engagement_channel": "web",
        "engagement_score": 85,
        "revenue_attributed": "7500.00",
        "currency": ma_currency.pk,
        "engaged_at": now.strftime("%Y-%m-%d %H:%M:%S"),
    }
    resp_create = client_a.post(create_url, post_data)
    assert resp_create.status_code == 302
    created = ContentEngagement.objects.latest("created_at")

    edit_url = reverse("sales:content_engagement_edit", kwargs={"pk": created.pk})
    post_edit = {
        "content": ma_content_a.pk,
        "account": ma_customer_a.pk,
        "lead": ma_lead_a.pk,
        "engagement_type": "download",
        "engagement_channel": "web",
        "engagement_score": 95,
        "revenue_attributed": "9000.00",
        "currency": ma_currency.pk,
        "engaged_at": now.strftime("%Y-%m-%d %H:%M:%S"),
    }
    resp_edit = client_a.post(edit_url, post_edit)
    assert resp_edit.status_code == 302
    created.refresh_from_db()
    assert created.engagement_score == 95

    delete_url = reverse("sales:content_engagement_delete", kwargs={"pk": created.pk})
    resp_del = client_a.post(delete_url)
    assert resp_del.status_code == 302
    assert not ContentEngagement.objects.filter(pk=created.pk).exists()


# ==============================================================================
# Marketing Events & Registrations View Tests
# ==============================================================================

@pytest.mark.django_db
def test_marketingalignment_marketing_event_list_view(client_a, ma_event_a):
    url = reverse("sales:marketing_event_list")
    response = client_a.get(url)
    assert response.status_code == 200
    assert "events" in response.context
    assert "status_choices" in response.context
    assert "event_type_choices" in response.context


@pytest.mark.django_db
def test_marketingalignment_marketing_event_detail_view(client_a, ma_event_a):
    url = reverse("sales:marketing_event_detail", kwargs={"pk": ma_event_a.pk})
    response = client_a.get(url)
    assert response.status_code == 200
    assert response.context["obj"].pk == ma_event_a.pk
    assert "registrations" in response.context


@pytest.mark.django_db
def test_marketingalignment_marketing_event_create_edit_delete(
    client_a, admin_user, ma_currency
):
    now = timezone.now()
    create_url = reverse("sales:marketing_event_create")
    post_data = {
        "name": "Q1 Customer Executive Roundtable",
        "event_type": "roundtable",
        "status": "planned",
        "start_at": (now + timezone.timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S"),
        "end_at": (now + timezone.timedelta(days=20, hours=3)).strftime("%Y-%m-%d %H:%M:%S"),
        "timezone_name": "UTC",
        "venue": "Private Dining Suite",
        "capacity": 25,
        "budget": "5000.00",
        "currency": ma_currency.pk,
        "owner": admin_user.pk,
    }
    resp_create = client_a.post(create_url, post_data)
    assert resp_create.status_code == 302
    created = MarketingEvent.objects.latest("created_at")

    edit_url = reverse("sales:marketing_event_edit", kwargs={"pk": created.pk})
    post_edit = {
        "name": "Q1 Customer Executive Roundtable (VIP)",
        "event_type": "roundtable",
        "status": "published",
        "start_at": (now + timezone.timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S"),
        "end_at": (now + timezone.timedelta(days=20, hours=3)).strftime("%Y-%m-%d %H:%M:%S"),
        "timezone_name": "UTC",
        "venue": "Private Dining Suite",
        "capacity": 30,
        "budget": "6000.00",
        "currency": ma_currency.pk,
        "owner": admin_user.pk,
    }
    resp_edit = client_a.post(edit_url, post_edit)
    assert resp_edit.status_code == 302
    created.refresh_from_db()
    assert created.status == "published"
    assert created.capacity == 30

    delete_url = reverse("sales:marketing_event_delete", kwargs={"pk": created.pk})
    resp_del = client_a.post(delete_url)
    assert resp_del.status_code == 302
    assert not MarketingEvent.objects.filter(pk=created.pk).exists()


@pytest.mark.django_db
def test_marketingalignment_marketing_event_registrations_and_attendee_crud(
    client_a, ma_event_a, ma_lead_a, ma_registration_a
):
    list_url = reverse("sales:marketing_event_registrations", kwargs={"pk": ma_event_a.pk})
    resp_list = client_a.get(list_url)
    assert resp_list.status_code == 200
    assert "registrations" in resp_list.context

    # Register attendee
    now = timezone.now()
    create_url = reverse("sales:marketing_event_registration_create", kwargs={"pk": ma_event_a.pk})
    post_reg = {
        "lead": ma_lead_a.pk,
        "registrant_name": "Helena Ravenclaw",
        "registrant_email": "helena@ravenclaw.example",
        "registration_status": "registered",
        "source_channel": "campaign",
        "registered_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "followup_status": "pending",
        "engagement_score": 75,
        "revenue_attributed": "0.00",
    }
    resp_reg = client_a.post(create_url, post_reg)
    assert resp_reg.status_code == 302
    reg = EventRegistration.objects.get(registrant_name="Helena Ravenclaw")

    # Edit attendee (mark attended)
    edit_url = reverse(
        "sales:marketing_event_registration_edit",
        kwargs={"pk": ma_event_a.pk, "registration_pk": reg.pk},
    )
    post_reg_edit = {
        "lead": ma_lead_a.pk,
        "registrant_name": "Helena Ravenclaw",
        "registrant_email": "helena@ravenclaw.example",
        "registration_status": "attended",
        "source_channel": "campaign",
        "registered_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "followup_status": "meeting_booked",
        "engagement_score": 90,
        "revenue_attributed": "12000.00",
    }
    resp_reg_edit = client_a.post(edit_url, post_reg_edit)
    assert resp_reg_edit.status_code == 302
    reg.refresh_from_db()
    assert reg.registration_status == "attended"
    assert reg.attended_at is not None

    # Delete attendee
    del_url = reverse(
        "sales:marketing_event_registration_delete",
        kwargs={"pk": ma_event_a.pk, "registration_pk": reg.pk},
    )
    resp_reg_del = client_a.post(del_url)
    assert resp_reg_del.status_code == 302
    assert not EventRegistration.objects.filter(pk=reg.pk).exists()
