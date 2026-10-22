"""Sales 8.13 Marketing Alignment & Attribution — Security & IDOR tests.

Verifies tenant isolation, cross-tenant IDOR defense (404 on all read, edit,
and delete operations across tenant boundaries), non-admin permission gates
(@tenant_admin_required -> 403), and unauthenticated access redirects.
"""
import pytest
from django.urls import reverse

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
# Cross-Tenant IDOR Read Tests (404)
# ==============================================================================

@pytest.mark.django_db
def test_marketingalignment_touchpoint_detail_cross_tenant_404(client_a, ma_touchpoint_b):
    url = reverse("sales:attribution_touchpoint_detail", kwargs={"pk": ma_touchpoint_b.pk})
    response = client_a.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_marketingalignment_campaign_attribution_detail_cross_tenant_404(client_a, ma_attribution_b):
    url = reverse("sales:campaign_attribution_detail", kwargs={"pk": ma_attribution_b.pk})
    response = client_a.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_marketingalignment_mql_handoff_detail_cross_tenant_404(client_a, ma_handoff_b):
    url = reverse("sales:mql_handoff_detail", kwargs={"pk": ma_handoff_b.pk})
    response = client_a.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_marketingalignment_content_engagement_detail_cross_tenant_404(client_a, ma_engagement_b):
    url = reverse("sales:content_engagement_detail", kwargs={"pk": ma_engagement_b.pk})
    response = client_a.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_marketingalignment_marketing_event_detail_cross_tenant_404(client_a, ma_event_b):
    url = reverse("sales:marketing_event_detail", kwargs={"pk": ma_event_b.pk})
    response = client_a.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_marketingalignment_marketing_event_registrations_cross_tenant_404(client_a, ma_event_b):
    url = reverse("sales:marketing_event_registrations", kwargs={"pk": ma_event_b.pk})
    response = client_a.get(url)
    assert response.status_code == 404


# ==============================================================================
# Cross-Tenant IDOR Edit Tests (404)
# ==============================================================================

@pytest.mark.django_db
def test_marketingalignment_touchpoint_edit_cross_tenant_404(client_a, ma_touchpoint_b):
    url = reverse("sales:attribution_touchpoint_edit", kwargs={"pk": ma_touchpoint_b.pk})
    assert client_a.get(url).status_code == 404
    assert client_a.post(url, {"touch_position": "last"}).status_code == 404


@pytest.mark.django_db
def test_marketingalignment_campaign_attribution_edit_cross_tenant_404(client_a, ma_attribution_b):
    url = reverse("sales:campaign_attribution_edit", kwargs={"pk": ma_attribution_b.pk})
    assert client_a.get(url).status_code == 404
    assert client_a.post(url, {"credit_pct": "50.00"}).status_code == 404


@pytest.mark.django_db
def test_marketingalignment_mql_handoff_edit_cross_tenant_404(client_a, ma_handoff_b):
    url = reverse("sales:mql_handoff_edit", kwargs={"pk": ma_handoff_b.pk})
    assert client_a.get(url).status_code == 404
    assert client_a.post(url, {"lead_score": 99}).status_code == 404


@pytest.mark.django_db
def test_marketingalignment_content_engagement_edit_cross_tenant_404(client_a, ma_engagement_b):
    url = reverse("sales:content_engagement_edit", kwargs={"pk": ma_engagement_b.pk})
    assert client_a.get(url).status_code == 404
    assert client_a.post(url, {"engagement_score": 99}).status_code == 404


@pytest.mark.django_db
def test_marketingalignment_marketing_event_edit_cross_tenant_404(client_a, ma_event_b):
    url = reverse("sales:marketing_event_edit", kwargs={"pk": ma_event_b.pk})
    assert client_a.get(url).status_code == 404
    assert client_a.post(url, {"capacity": 999}).status_code == 404


@pytest.mark.django_db
def test_marketingalignment_marketing_event_registration_edit_cross_tenant_404(
    client_a, ma_event_b, ma_registration_b
):
    url = reverse(
        "sales:marketing_event_registration_edit",
        kwargs={"pk": ma_event_b.pk, "registration_pk": ma_registration_b.pk},
    )
    assert client_a.get(url).status_code == 404
    assert client_a.post(url, {"registration_status": "attended"}).status_code == 404


# ==============================================================================
# Cross-Tenant IDOR Delete Tests (404 & no deletion)
# ==============================================================================

@pytest.mark.django_db
def test_marketingalignment_touchpoint_delete_cross_tenant_404(client_a, ma_touchpoint_b):
    url = reverse("sales:attribution_touchpoint_delete", kwargs={"pk": ma_touchpoint_b.pk})
    response = client_a.post(url)
    assert response.status_code == 404
    assert AttributionTouchpoint.objects.filter(pk=ma_touchpoint_b.pk).exists()


@pytest.mark.django_db
def test_marketingalignment_campaign_attribution_delete_cross_tenant_404(client_a, ma_attribution_b):
    url = reverse("sales:campaign_attribution_delete", kwargs={"pk": ma_attribution_b.pk})
    response = client_a.post(url)
    assert response.status_code == 404
    assert CampaignAttribution.objects.filter(pk=ma_attribution_b.pk).exists()


@pytest.mark.django_db
def test_marketingalignment_mql_handoff_delete_cross_tenant_404(client_a, ma_handoff_b):
    url = reverse("sales:mql_handoff_delete", kwargs={"pk": ma_handoff_b.pk})
    response = client_a.post(url)
    assert response.status_code == 404
    assert MqlHandoff.objects.filter(pk=ma_handoff_b.pk).exists()


@pytest.mark.django_db
def test_marketingalignment_content_engagement_delete_cross_tenant_404(client_a, ma_engagement_b):
    url = reverse("sales:content_engagement_delete", kwargs={"pk": ma_engagement_b.pk})
    response = client_a.post(url)
    assert response.status_code == 404
    assert ContentEngagement.objects.filter(pk=ma_engagement_b.pk).exists()


@pytest.mark.django_db
def test_marketingalignment_marketing_event_delete_cross_tenant_404(client_a, ma_event_b):
    url = reverse("sales:marketing_event_delete", kwargs={"pk": ma_event_b.pk})
    response = client_a.post(url)
    assert response.status_code == 404
    assert MarketingEvent.objects.filter(pk=ma_event_b.pk).exists()


@pytest.mark.django_db
def test_marketingalignment_marketing_event_registration_delete_cross_tenant_404(
    client_a, ma_event_b, ma_registration_b
):
    url = reverse(
        "sales:marketing_event_registration_delete",
        kwargs={"pk": ma_event_b.pk, "registration_pk": ma_registration_b.pk},
    )
    response = client_a.post(url)
    assert response.status_code == 404
    assert EventRegistration.objects.filter(pk=ma_registration_b.pk).exists()


# ==============================================================================
# Non-Admin Authorization Gate Tests (403 Forbidden)
# ==============================================================================

@pytest.mark.django_db
def test_marketingalignment_touchpoint_delete_non_admin_403(member_client, ma_touchpoint_a):
    url = reverse("sales:attribution_touchpoint_delete", kwargs={"pk": ma_touchpoint_a.pk})
    response = member_client.post(url)
    assert response.status_code == 403
    assert AttributionTouchpoint.objects.filter(pk=ma_touchpoint_a.pk).exists()


@pytest.mark.django_db
def test_marketingalignment_campaign_attribution_delete_non_admin_403(member_client, ma_attribution_a):
    url = reverse("sales:campaign_attribution_delete", kwargs={"pk": ma_attribution_a.pk})
    response = member_client.post(url)
    assert response.status_code == 403
    assert CampaignAttribution.objects.filter(pk=ma_attribution_a.pk).exists()


@pytest.mark.django_db
def test_marketingalignment_mql_handoff_delete_non_admin_403(member_client, ma_handoff_a):
    url = reverse("sales:mql_handoff_delete", kwargs={"pk": ma_handoff_a.pk})
    response = member_client.post(url)
    assert response.status_code == 403
    assert MqlHandoff.objects.filter(pk=ma_handoff_a.pk).exists()


@pytest.mark.django_db
def test_marketingalignment_content_engagement_delete_non_admin_403(member_client, ma_engagement_a):
    url = reverse("sales:content_engagement_delete", kwargs={"pk": ma_engagement_a.pk})
    response = member_client.post(url)
    assert response.status_code == 403
    assert ContentEngagement.objects.filter(pk=ma_engagement_a.pk).exists()


@pytest.mark.django_db
def test_marketingalignment_marketing_event_delete_non_admin_403(member_client, ma_event_a):
    url = reverse("sales:marketing_event_delete", kwargs={"pk": ma_event_a.pk})
    response = member_client.post(url)
    assert response.status_code == 403
    assert MarketingEvent.objects.filter(pk=ma_event_a.pk).exists()


@pytest.mark.django_db
def test_marketingalignment_marketing_event_registration_delete_non_admin_403(
    member_client, ma_event_a, ma_registration_a
):
    url = reverse(
        "sales:marketing_event_registration_delete",
        kwargs={"pk": ma_event_a.pk, "registration_pk": ma_registration_a.pk},
    )
    response = member_client.post(url)
    assert response.status_code == 403
    assert EventRegistration.objects.filter(pk=ma_registration_a.pk).exists()


# ==============================================================================
# Unauthenticated Access Tests (302 Redirect to Login)
# ==============================================================================

@pytest.mark.django_db
def test_marketingalignment_unauthenticated_redirects_to_login(client):
    endpoints = [
        reverse("sales:marketing_attribution_console"),
        reverse("sales:attribution_touchpoint_list"),
        reverse("sales:campaign_attribution_list"),
        reverse("sales:mql_handoff_list"),
        reverse("sales:content_engagement_list"),
        reverse("sales:marketing_event_list"),
    ]
    for url in endpoints:
        response = client.get(url)
        assert response.status_code == 302
        assert "/accounts/login/" in response.url
