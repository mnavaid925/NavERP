"""Multi-tenancy, authentication, and cross-tenant IDOR isolation tests for eCommerce 9.10 Marketing.

Covers:
- Anonymous user access prevention (302 redirect to login)
- Cross-tenant IDOR defense (404 on all foreign tenant records for detail, edit, delete, action endpoints)
- Queryset isolation across tenant boundaries on list views
- Multi-user tenant boundary verification
- Adversarial workflow and cross-tenant injection defenses

Naming conventions enforced:
- Test functions: test_marketingcampaign_*
- Module-level helpers: _marketingcampaign_*
"""
from decimal import Decimal
import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.core.models import Party
from apps.ecommerce.models import (
    MarketingCampaign,
    AffiliatePartner,
    AffiliateReferralConversion,
    SeoMetadataRule,
    StoreCategory,
    CatalogProduct,
    AudienceSegment,
)
from apps.ecommerce.tests.conftest import (
    _marketing_campaign,
    _affiliate_partner,
    _affiliate_conversion,
    _seo_rule,
    _ordermanagement_order,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Anonymous Access Prevention Tests
# ==============================================================================

@pytest.mark.parametrize(
    "url_name",
    [
        "marketing_dashboard",
        "social_commerce_feed",
        "marketingcampaign_list",
        "marketingcampaign_create",
        "affiliatepartner_list",
        "affiliatepartner_create",
        "affiliatereferralconversion_list",
        "affiliatereferralconversion_create",
        "seometadatarule_list",
        "seometadatarule_create",
    ],
)
def test_marketingcampaign_anonymous_redirects_to_login(client, url_name):
    url = reverse(f"ecommerce:{url_name}")
    resp = client.get(url)
    assert resp.status_code == 302
    assert "/accounts/login/" in resp.url or "login" in resp.url


# ==============================================================================
# Cross-Tenant IDOR Defense Tests
# ==============================================================================

def test_marketingcampaign_cross_tenant_idor(client_b, ecom_campaign_a):
    detail_url = reverse("ecommerce:marketingcampaign_detail", kwargs={"pk": ecom_campaign_a.pk})
    edit_url = reverse("ecommerce:marketingcampaign_edit", kwargs={"pk": ecom_campaign_a.pk})
    send_url = reverse("ecommerce:marketingcampaign_send", kwargs={"pk": ecom_campaign_a.pk})
    delete_url = reverse("ecommerce:marketingcampaign_delete", kwargs={"pk": ecom_campaign_a.pk})

    assert client_b.get(detail_url).status_code == 404
    assert client_b.get(edit_url).status_code == 404
    assert client_b.post(edit_url, {"name": "Hacked Name"}).status_code == 404
    assert client_b.post(send_url).status_code == 404
    assert client_b.post(delete_url).status_code == 404


def test_marketingcampaign_affiliate_cross_tenant_idor(client_b, ecom_affiliate_a):
    detail_url = reverse("ecommerce:affiliatepartner_detail", kwargs={"pk": ecom_affiliate_a.pk})
    edit_url = reverse("ecommerce:affiliatepartner_edit", kwargs={"pk": ecom_affiliate_a.pk})
    approve_url = reverse("ecommerce:affiliatepartner_approve", kwargs={"pk": ecom_affiliate_a.pk})
    delete_url = reverse("ecommerce:affiliatepartner_delete", kwargs={"pk": ecom_affiliate_a.pk})

    assert client_b.get(detail_url).status_code == 404
    assert client_b.get(edit_url).status_code == 404
    assert client_b.post(edit_url, {"name": "Hacked Affiliate"}).status_code == 404
    assert client_b.post(approve_url).status_code == 404
    assert client_b.post(delete_url).status_code == 404


def test_marketingcampaign_conversion_cross_tenant_idor(client_b, ecom_conversion_a):
    detail_url = reverse("ecommerce:affiliatereferralconversion_detail", kwargs={"pk": ecom_conversion_a.pk})
    edit_url = reverse("ecommerce:affiliatereferralconversion_edit", kwargs={"pk": ecom_conversion_a.pk})
    approve_url = reverse("ecommerce:affiliatereferralconversion_approve", kwargs={"pk": ecom_conversion_a.pk})
    void_url = reverse("ecommerce:affiliatereferralconversion_void", kwargs={"pk": ecom_conversion_a.pk})
    delete_url = reverse("ecommerce:affiliatereferralconversion_delete", kwargs={"pk": ecom_conversion_a.pk})

    assert client_b.get(detail_url).status_code == 404
    assert client_b.get(edit_url).status_code == 404
    assert client_b.post(approve_url).status_code == 404
    assert client_b.post(void_url).status_code == 404
    assert client_b.post(delete_url).status_code == 404


def test_marketingcampaign_seo_rule_cross_tenant_idor(client_b, ecom_seo_rule_a):
    detail_url = reverse("ecommerce:seometadatarule_detail", kwargs={"pk": ecom_seo_rule_a.pk})
    edit_url = reverse("ecommerce:seometadatarule_edit", kwargs={"pk": ecom_seo_rule_a.pk})
    toggle_url = reverse("ecommerce:seometadatarule_toggle", kwargs={"pk": ecom_seo_rule_a.pk})
    delete_url = reverse("ecommerce:seometadatarule_delete", kwargs={"pk": ecom_seo_rule_a.pk})

    assert client_b.get(detail_url).status_code == 404
    assert client_b.get(edit_url).status_code == 404
    assert client_b.post(toggle_url).status_code == 404
    assert client_b.post(delete_url).status_code == 404


# ==============================================================================
# Queryset Isolation Tests
# ==============================================================================

def test_marketingcampaign_queryset_isolation(client_a, client_b, ecom_campaign_a, ecom_campaign_b):
    list_url = reverse("ecommerce:marketingcampaign_list")

    resp_a = client_a.get(list_url)
    assert resp_a.status_code == 200
    campaign_ids_a = [c.pk for c in resp_a.context["campaigns"]]
    assert ecom_campaign_a.pk in campaign_ids_a
    assert ecom_campaign_b.pk not in campaign_ids_a

    resp_b = client_b.get(list_url)
    assert resp_b.status_code == 200
    campaign_ids_b = [c.pk for c in resp_b.context["campaigns"]]
    assert ecom_campaign_b.pk in campaign_ids_b
    assert ecom_campaign_a.pk not in campaign_ids_b


def test_marketingcampaign_affiliate_queryset_isolation(client_a, client_b, ecom_affiliate_a, ecom_affiliate_b):
    list_url = reverse("ecommerce:affiliatepartner_list")

    resp_a = client_a.get(list_url)
    assert resp_a.status_code == 200
    ids_a = [p.pk for p in resp_a.context["partners"]]
    assert ecom_affiliate_a.pk in ids_a
    assert ecom_affiliate_b.pk not in ids_a

    resp_b = client_b.get(list_url)
    assert resp_b.status_code == 200
    ids_b = [p.pk for p in resp_b.context["partners"]]
    assert ecom_affiliate_b.pk in ids_b
    assert ecom_affiliate_a.pk not in ids_b


# ==============================================================================
# Adversarial & Concurrency Defense Tests
# ==============================================================================

def test_marketingcampaign_adversarial_cross_tenant_injection(client_a, tenant_a, tenant_b):
    # Attacker logged into tenant_a attempts to bind a campaign to tenant_b's segment
    segment_b = AudienceSegment.objects.create(tenant=tenant_b, name="Globex High Spenders")
    create_url = reverse("ecommerce:marketingcampaign_create")
    post_data = {
        "name": "Spy Campaign",
        "code": "SPY-01",
        "campaign_type": "newsletter_broadcast",
        "channel": "email",
        "target_segment": segment_b.pk,
        "subject": "Infiltrating",
        "content_body": "Test",
        "sender_name": "Spy",
        "sender_address": "spy@test.com",
        "send_throttle_window_hours": 12,
    }
    resp = client_a.post(create_url, post_data)
    # Must fail form validation and reject foreign tenant FK
    assert resp.status_code == 200
    assert not MarketingCampaign.objects.filter(tenant=tenant_a, code="SPY-01").exists()


def test_marketingcampaign_adversarial_cannot_dispatch_cancelled_campaign(client_a, tenant_a, ecom_campaign_a):
    ecom_campaign_a.status = "cancelled"
    ecom_campaign_a.save()

    send_url = reverse("ecommerce:marketingcampaign_send", args=[ecom_campaign_a.pk])
    resp = client_a.post(send_url)
    assert resp.status_code == 302
    ecom_campaign_a.refresh_from_db()
    # Must remain cancelled and not dispatched
    assert ecom_campaign_a.status == "cancelled"
    assert ecom_campaign_a.sent_at is None
