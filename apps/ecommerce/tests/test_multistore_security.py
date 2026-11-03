"""Security and multi-tenant isolation tests for Module 9.20 Multi-Store & Platform Operations."""
import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_multistore_security_anonymous_redirect(client, ecom_storefront_a, ecom_environment_a):
    """Test that all endpoints redirect unauthenticated users to the login screen."""
    urls = [
        reverse("ecommerce:multi_store_hub"),
        reverse("ecommerce:storefront_instance_list"),
        reverse("ecommerce:storefront_instance_create"),
        reverse("ecommerce:storefront_instance_detail", args=[ecom_storefront_a.pk]),
        reverse("ecommerce:storefront_instance_edit", args=[ecom_storefront_a.pk]),
        reverse("ecommerce:platform_environment_list"),
        reverse("ecommerce:platform_environment_detail", args=[ecom_environment_a.pk]),
        reverse("ecommerce:deployment_pipeline_list"),
    ]
    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 302
        assert "/accounts/login/" in resp.url or "login" in resp.url


@pytest.mark.django_db
def test_multistore_security_idor_storefront(auth_client_a, ecom_storefront_b):
    """Test that Tenant A cannot view, edit, delete, or toggle Tenant B's storefront (returns 404)."""
    pk = ecom_storefront_b.pk
    assert auth_client_a.get(reverse("ecommerce:storefront_instance_detail", args=[pk])).status_code == 404
    assert auth_client_a.get(reverse("ecommerce:storefront_instance_edit", args=[pk])).status_code == 404
    assert auth_client_a.post(reverse("ecommerce:storefront_instance_delete", args=[pk])).status_code == 404
    assert auth_client_a.post(reverse("ecommerce:storefront_toggle_status", args=[pk])).status_code == 404


@pytest.mark.django_db
def test_multistore_security_idor_catalog_assignment(auth_client_a, ecom_catalog_assignment_b):
    """Test that Tenant A cannot view, edit, or delete Tenant B's catalog assignment (returns 404)."""
    pk = ecom_catalog_assignment_b.pk
    assert auth_client_a.get(reverse("ecommerce:storefront_catalog_assignment_detail", args=[pk])).status_code == 404
    assert auth_client_a.get(reverse("ecommerce:storefront_catalog_assignment_edit", args=[pk])).status_code == 404
    assert auth_client_a.post(reverse("ecommerce:storefront_catalog_assignment_delete", args=[pk])).status_code == 404


@pytest.mark.django_db
def test_multistore_security_idor_platform_environment(auth_client_a, ecom_environment_b):
    """Test that Tenant A cannot view, edit, or delete Tenant B's platform environment (returns 404)."""
    pk = ecom_environment_b.pk
    assert auth_client_a.get(reverse("ecommerce:platform_environment_detail", args=[pk])).status_code == 404
    assert auth_client_a.get(reverse("ecommerce:platform_environment_edit", args=[pk])).status_code == 404
    assert auth_client_a.post(reverse("ecommerce:platform_environment_delete", args=[pk])).status_code == 404


@pytest.mark.django_db
def test_multistore_security_idor_deployment_pipeline(auth_client_a, ecom_pipeline_b):
    """Test that Tenant A cannot view, edit, delete, promote, or roll back Tenant B's pipeline (returns 404)."""
    pk = ecom_pipeline_b.pk
    assert auth_client_a.get(reverse("ecommerce:deployment_pipeline_detail", args=[pk])).status_code == 404
    assert auth_client_a.get(reverse("ecommerce:deployment_pipeline_edit", args=[pk])).status_code == 404
    assert auth_client_a.post(reverse("ecommerce:deployment_pipeline_delete", args=[pk])).status_code == 404
    assert auth_client_a.post(reverse("ecommerce:deployment_promote", args=[pk])).status_code == 404
    assert auth_client_a.post(reverse("ecommerce:deployment_rollback", args=[pk])).status_code == 404


@pytest.mark.django_db
def test_multistore_security_post_only_destructive_actions(auth_client_a, ecom_storefront_a, ecom_pipeline_a):
    """Test that mutating and destructive endpoints reject GET requests with 405 Method Not Allowed."""
    endpoints = [
        reverse("ecommerce:storefront_instance_delete", args=[ecom_storefront_a.pk]),
        reverse("ecommerce:storefront_toggle_status", args=[ecom_storefront_a.pk]),
        reverse("ecommerce:deployment_promote", args=[ecom_pipeline_a.pk]),
        reverse("ecommerce:deployment_rollback", args=[ecom_pipeline_a.pk]),
    ]
    for url in endpoints:
        resp = auth_client_a.get(url)
        assert resp.status_code == 405, f"Expected 405 Method Not Allowed on GET {url}"


@pytest.mark.django_db
def test_multistore_security_list_data_isolation(auth_client_a, ecom_storefront_a, ecom_storefront_b):
    """Test that list queries strictly isolate records between tenants."""
    resp = auth_client_a.get(reverse("ecommerce:storefront_instance_list"))
    assert resp.status_code == 200
    storefront_ids = [s.pk for s in resp.context["storefront_instances"]]
    assert ecom_storefront_a.pk in storefront_ids
    assert ecom_storefront_b.pk not in storefront_ids
