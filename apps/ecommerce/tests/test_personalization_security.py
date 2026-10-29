"""Multi-tenancy, authentication, and cross-tenant IDOR isolation tests for eCommerce 9.8.

Covers:
- Anonymous user access prevention (302 redirect to login)
- Tenant Admin Gate enforcement (@tenant_admin_required)
- Cross-tenant IDOR defense (404 on all foreign tenant records for detail, edit, delete, toggle, recalculate)
- Queryset isolation across tenant boundaries
- Personalization Simulator multi-tenant scoping

Naming conventions enforced:
- Test functions: test_personalization_*
- Module-level helpers: _personalization_*
"""
import pytest
from django.urls import reverse

from apps.ecommerce.models import (
    AudienceSegment,
    RecommendationStrategy,
    PersonalizedExperience,
    ShopperBehaviorEvent,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Anonymous Access Prevention Tests
# ==============================================================================

@pytest.mark.parametrize(
    "url_name,args",
    [
        ("audiencesegment_list", []),
        ("audiencesegment_create", []),
        ("recommendationstrategy_list", []),
        ("recommendationstrategy_create", []),
        ("personalizedexperience_list", []),
        ("personalizedexperience_create", []),
        ("shopperbehaviorevent_list", []),
        ("personalization_console", []),
        ("recommendation_simulate", []),
    ],
)
def test_personalization_anonymous_redirects_to_login(client, url_name, args):
    url = reverse(f"ecommerce:{url_name}", args=args)
    resp = client.get(url)
    assert resp.status_code == 302
    assert "/login" in resp.url or "login" in resp.url


# ==============================================================================
# Cross-Tenant IDOR Defense Tests (404 on Foreign Tenant Records)
# ==============================================================================

def test_personalization_segment_idor_defense(client_a, ecom_segment_b):
    # Detail
    url_det = reverse("ecommerce:audiencesegment_detail", args=[ecom_segment_b.pk])
    assert client_a.get(url_det).status_code == 404

    # Edit GET & POST
    url_edit = reverse("ecommerce:audiencesegment_edit", args=[ecom_segment_b.pk])
    assert client_a.get(url_edit).status_code == 404
    assert client_a.post(url_edit, {"name": "Hacked Segment"}).status_code == 404

    # Toggle POST
    url_tog = reverse("ecommerce:audiencesegment_toggle", args=[ecom_segment_b.pk])
    assert client_a.post(url_tog).status_code == 404

    # Recalculate POST
    url_recalc = reverse("ecommerce:audiencesegment_recalculate", args=[ecom_segment_b.pk])
    assert client_a.post(url_recalc).status_code == 404

    # Delete POST
    url_del = reverse("ecommerce:audiencesegment_delete", args=[ecom_segment_b.pk])
    assert client_a.post(url_del).status_code == 404
    assert AudienceSegment.objects.filter(pk=ecom_segment_b.pk).exists()


def test_personalization_strategy_idor_defense(client_a, ecom_strategy_b):
    # Detail
    url_det = reverse("ecommerce:recommendationstrategy_detail", args=[ecom_strategy_b.pk])
    assert client_a.get(url_det).status_code == 404

    # Edit GET & POST
    url_edit = reverse("ecommerce:recommendationstrategy_edit", args=[ecom_strategy_b.pk])
    assert client_a.get(url_edit).status_code == 404
    assert client_a.post(url_edit, {"name": "Hacked Strategy"}).status_code == 404

    # Toggle POST
    url_tog = reverse("ecommerce:recommendationstrategy_toggle", args=[ecom_strategy_b.pk])
    assert client_a.post(url_tog).status_code == 404

    # Delete POST
    url_del = reverse("ecommerce:recommendationstrategy_delete", args=[ecom_strategy_b.pk])
    assert client_a.post(url_del).status_code == 404
    assert RecommendationStrategy.objects.filter(pk=ecom_strategy_b.pk).exists()


def test_personalization_experience_idor_defense(client_a, ecom_experience_b):
    # Detail
    url_det = reverse("ecommerce:personalizedexperience_detail", args=[ecom_experience_b.pk])
    assert client_a.get(url_det).status_code == 404

    # Edit GET & POST
    url_edit = reverse("ecommerce:personalizedexperience_edit", args=[ecom_experience_b.pk])
    assert client_a.get(url_edit).status_code == 404
    assert client_a.post(url_edit, {"name": "Hacked Experience"}).status_code == 404

    # Toggle POST
    url_tog = reverse("ecommerce:personalizedexperience_toggle", args=[ecom_experience_b.pk])
    assert client_a.post(url_tog).status_code == 404

    # Delete POST
    url_del = reverse("ecommerce:personalizedexperience_delete", args=[ecom_experience_b.pk])
    assert client_a.post(url_del).status_code == 404
    assert PersonalizedExperience.objects.filter(pk=ecom_experience_b.pk).exists()


def test_personalization_event_idor_defense(client_a, ecom_event_b):
    # Detail
    url_det = reverse("ecommerce:shopperbehaviorevent_detail", args=[ecom_event_b.pk])
    assert client_a.get(url_det).status_code == 404

    # Delete POST
    url_del = reverse("ecommerce:shopperbehaviorevent_delete", args=[ecom_event_b.pk])
    assert client_a.post(url_del).status_code == 404
    assert ShopperBehaviorEvent.objects.filter(pk=ecom_event_b.pk).exists()


# ==============================================================================
# Queryset Isolation Tests
# ==============================================================================

def test_personalization_queryset_isolation(
    client_a,
    ecom_segment_a,
    ecom_segment_b,
    ecom_strategy_a,
    ecom_strategy_b,
    ecom_experience_a,
    ecom_experience_b,
    ecom_event_a,
    ecom_event_b,
):
    # AudienceSegment list
    resp_seg = client_a.get(reverse("ecommerce:audiencesegment_list"))
    assert resp_seg.status_code == 200
    seg_ids = [s.id for s in resp_seg.context["segments"]]
    assert ecom_segment_a.id in seg_ids
    assert ecom_segment_b.id not in seg_ids

    # RecommendationStrategy list
    resp_strat = client_a.get(reverse("ecommerce:recommendationstrategy_list"))
    assert resp_strat.status_code == 200
    strat_ids = [s.id for s in resp_strat.context["strategies"]]
    assert ecom_strategy_a.id in strat_ids
    assert ecom_strategy_b.id not in strat_ids

    # PersonalizedExperience list
    resp_exp = client_a.get(reverse("ecommerce:personalizedexperience_list"))
    assert resp_exp.status_code == 200
    exp_ids = [e.id for e in resp_exp.context["experiences"]]
    assert ecom_experience_a.id in exp_ids
    assert ecom_experience_b.id not in exp_ids

    # ShopperBehaviorEvent list
    resp_evt = client_a.get(reverse("ecommerce:shopperbehaviorevent_list"))
    assert resp_evt.status_code == 200
    evt_ids = [e.id for e in resp_evt.context["events"]]
    assert ecom_event_a.id in evt_ids
    assert ecom_event_b.id not in evt_ids


# ==============================================================================
# Simulator Isolation Tests
# ==============================================================================

def test_personalization_simulator_tenant_isolation(
    client_a,
    tenant_a,
    tenant_b,
    ecom_strategy_b,
    ecom_product_b,
):
    preview_url = reverse("ecommerce:recommendation_simulate")
    # Requesting simulation with tenant B's objects in tenant A's session
    resp = client_a.post(preview_url, {
        "strategy_id": ecom_strategy_b.pk,
        "product_id": ecom_product_b.pk,
    })
    assert resp.status_code == 200
    # Both anchor_product and strategy should resolve to None for tenant A
    assert resp.context["anchor_product"] is None
    assert resp.context["strategy"] is None
    # None of the recommended products should belong to tenant B
    for p in resp.context["simulated_recommendations"]:
        assert p.tenant_id == tenant_a.id
