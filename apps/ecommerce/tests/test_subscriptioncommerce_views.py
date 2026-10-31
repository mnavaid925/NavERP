from decimal import Decimal
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.ecommerce.models import (
    CustomerSubscription,
    SubscriptionBoxCuration,
    SubscriptionPlan,
    SubscriptionRetentionAction,
)


@pytest.mark.django_db
class TestSubscriptionCommerceViews:
    def test_subscription_plan_list_and_filters(self, client_admin_a, ecom_subscription_plan_a):
        url = reverse("ecommerce:subscriptionplan_list")
        resp = client_admin_a.get(url)
        assert resp.status_code == 200
        assert ecom_subscription_plan_a.name in resp.content.decode()

        # Filter by plan_type and status
        resp_filtered = client_admin_a.get(url, {"plan_type": "curated_box", "status": "active"})
        assert resp_filtered.status_code == 200

    def test_customersubscription_list_and_junk_param(self, client_admin_a, ecom_customer_subscription_a):
        url = reverse("ecommerce:customersubscription_list")
        resp = client_admin_a.get(url)
        assert resp.status_code == 200
        assert ecom_customer_subscription_a.number in resp.content.decode()

        # Non-numeric plan parameter should not crash
        resp_junk = client_admin_a.get(url, {"plan": "invalid_abc", "status": "active"})
        assert resp_junk.status_code == 200

    def test_subscriptionboxcuration_list_and_junk_param(self, client_admin_a, ecom_box_curation_a):
        url = reverse("ecommerce:subscriptionboxcuration_list")
        resp = client_admin_a.get(url)
        assert resp.status_code == 200
        assert ecom_box_curation_a.cycle_identifier in resp.content.decode()

        # Non-numeric plan parameter should not crash
        resp_junk = client_admin_a.get(url, {"plan": "invalid_abc"})
        assert resp_junk.status_code == 200

    def test_subscriptionretentionaction_list(self, client_admin_a, ecom_retention_action_a):
        url = reverse("ecommerce:subscriptionretentionaction_list")
        resp = client_admin_a.get(url)
        assert resp.status_code == 200
        assert ecom_retention_action_a.number in resp.content.decode()

    def test_subscription_plan_delete_protected(self, client_admin_a, ecom_subscription_plan_a, ecom_customer_subscription_a):
        # Plan has an active subscription -> ProtectedError should be caught cleanly
        url = reverse("ecommerce:subscriptionplan_delete", args=[ecom_subscription_plan_a.pk])
        resp = client_admin_a.post(url, follow=True)
        assert resp.status_code == 200
        assert SubscriptionPlan.objects.filter(pk=ecom_subscription_plan_a.pk).exists()

    def test_subscription_portal_dashboard(self, client_admin_a, ecom_customer_subscription_a):
        url = reverse("ecommerce:subscription_portal")
        resp = client_admin_a.get(url)
        assert resp.status_code == 200
        content = resp.content.decode()
        assert "Subscription & Retention Portal" in content
        assert ecom_customer_subscription_a.number in content

    def test_subscription_portal_skip_action(self, client_admin_a, ecom_customer_subscription_a):
        old_billing_date = ecom_customer_subscription_a.next_billing_date
        url = reverse("ecommerce:subscription_portal_skip", args=[ecom_customer_subscription_a.pk])
        resp = client_admin_a.post(url, follow=True)
        assert resp.status_code == 200
        ecom_customer_subscription_a.refresh_from_db()
        assert ecom_customer_subscription_a.next_billing_date == old_billing_date + timezone.timedelta(days=30)
        assert SubscriptionRetentionAction.objects.filter(subscription=ecom_customer_subscription_a, trigger_type="pause_request").exists()

    def test_subscription_portal_pause_and_resume_action(self, client_admin_a, ecom_customer_subscription_a):
        # Pause
        url_pause = reverse("ecommerce:subscription_portal_pause", args=[ecom_customer_subscription_a.pk])
        resp_pause = client_admin_a.post(url_pause, follow=True)
        assert resp_pause.status_code == 200
        ecom_customer_subscription_a.refresh_from_db()
        assert ecom_customer_subscription_a.status == "paused"
        assert ecom_customer_subscription_a.paused_until is not None

        # Resume
        url_resume = reverse("ecommerce:subscription_portal_resume", args=[ecom_customer_subscription_a.pk])
        resp_resume = client_admin_a.post(url_resume, follow=True)
        assert resp_resume.status_code == 200
        ecom_customer_subscription_a.refresh_from_db()
        assert ecom_customer_subscription_a.status == "active"
        assert ecom_customer_subscription_a.paused_until is None

    def test_subscription_portal_deflect_discount(self, client_admin_a, ecom_customer_subscription_a):
        orig_discount = ecom_customer_subscription_a.recurring_discount_pct
        url_deflect = reverse("ecommerce:subscription_portal_deflect", args=[ecom_customer_subscription_a.pk])
        resp = client_admin_a.post(
            url_deflect,
            {"reason": "too_expensive", "action_choice": "discount_cycle"},
            follow=True,
        )
        assert resp.status_code == 200
        ecom_customer_subscription_a.refresh_from_db()
        assert ecom_customer_subscription_a.recurring_discount_pct == orig_discount + Decimal("15.00")
        assert SubscriptionRetentionAction.objects.filter(
            subscription=ecom_customer_subscription_a,
            outcome="deflected",
            cancellation_reason="too_expensive",
        ).exists()
