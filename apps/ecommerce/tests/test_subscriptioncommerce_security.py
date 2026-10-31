import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestSubscriptionCommerceSecurity:
    def test_idor_subscription_plan(self, client_b, ecom_subscription_plan_a):
        # Tenant B admin accessing Tenant A plan detail/edit/delete
        detail_url = reverse("ecommerce:subscriptionplan_detail", args=[ecom_subscription_plan_a.pk])
        edit_url = reverse("ecommerce:subscriptionplan_edit", args=[ecom_subscription_plan_a.pk])
        del_url = reverse("ecommerce:subscriptionplan_delete", args=[ecom_subscription_plan_a.pk])

        assert client_b.get(detail_url).status_code == 404
        assert client_b.get(edit_url).status_code == 404
        assert client_b.post(del_url).status_code == 404

    def test_idor_customer_subscription(self, client_b, ecom_customer_subscription_a):
        detail_url = reverse("ecommerce:customersubscription_detail", args=[ecom_customer_subscription_a.pk])
        edit_url = reverse("ecommerce:customersubscription_edit", args=[ecom_customer_subscription_a.pk])
        del_url = reverse("ecommerce:customersubscription_delete", args=[ecom_customer_subscription_a.pk])

        assert client_b.get(detail_url).status_code == 404
        assert client_b.get(edit_url).status_code == 404
        assert client_b.post(del_url).status_code == 404

    def test_idor_subscription_box_curation(self, client_b, ecom_box_curation_a):
        detail_url = reverse("ecommerce:subscriptionboxcuration_detail", args=[ecom_box_curation_a.pk])
        edit_url = reverse("ecommerce:subscriptionboxcuration_edit", args=[ecom_box_curation_a.pk])
        del_url = reverse("ecommerce:subscriptionboxcuration_delete", args=[ecom_box_curation_a.pk])

        assert client_b.get(detail_url).status_code == 404
        assert client_b.get(edit_url).status_code == 404
        assert client_b.post(del_url).status_code == 404

    def test_idor_subscription_retention_action(self, client_b, ecom_retention_action_a):
        detail_url = reverse("ecommerce:subscriptionretentionaction_detail", args=[ecom_retention_action_a.pk])
        edit_url = reverse("ecommerce:subscriptionretentionaction_edit", args=[ecom_retention_action_a.pk])
        del_url = reverse("ecommerce:subscriptionretentionaction_delete", args=[ecom_retention_action_a.pk])

        assert client_b.get(detail_url).status_code == 404
        assert client_b.get(edit_url).status_code == 404
        assert client_b.post(del_url).status_code == 404

    def test_idor_portal_actions(self, client_b, ecom_customer_subscription_a):
        # Tenant B admin executing mutating actions on Tenant A subscription
        skip_url = reverse("ecommerce:subscription_portal_skip", args=[ecom_customer_subscription_a.pk])
        pause_url = reverse("ecommerce:subscription_portal_pause", args=[ecom_customer_subscription_a.pk])
        resume_url = reverse("ecommerce:subscription_portal_resume", args=[ecom_customer_subscription_a.pk])
        deflect_url = reverse("ecommerce:subscription_portal_deflect", args=[ecom_customer_subscription_a.pk])

        assert client_b.post(skip_url).status_code == 404
        assert client_b.post(pause_url).status_code == 404
        assert client_b.post(resume_url).status_code == 404
        assert client_b.post(deflect_url).status_code == 404

    def test_unauthenticated_redirect(self, client):
        urls = [
            reverse("ecommerce:subscriptionplan_list"),
            reverse("ecommerce:customersubscription_list"),
            reverse("ecommerce:subscriptionboxcuration_list"),
            reverse("ecommerce:subscriptionretentionaction_list"),
            reverse("ecommerce:subscription_portal"),
        ]
        for url in urls:
            resp = client.get(url)
            assert resp.status_code == 302
            assert "login" in resp.url

    def test_actions_require_post(self, client_a, ecom_customer_subscription_a):
        urls = [
            reverse("ecommerce:subscriptionplan_delete", args=[1]),
            reverse("ecommerce:customersubscription_delete", args=[1]),
            reverse("ecommerce:subscriptionboxcuration_delete", args=[1]),
            reverse("ecommerce:subscriptionretentionaction_delete", args=[1]),
            reverse("ecommerce:subscription_portal_skip", args=[ecom_customer_subscription_a.pk]),
            reverse("ecommerce:subscription_portal_pause", args=[ecom_customer_subscription_a.pk]),
            reverse("ecommerce:subscription_portal_resume", args=[ecom_customer_subscription_a.pk]),
            reverse("ecommerce:subscription_portal_deflect", args=[ecom_customer_subscription_a.pk]),
        ]
        for url in urls:
            resp = client_a.get(url)
            assert resp.status_code == 405
