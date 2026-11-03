"""Tests for Module 9.20 Multi-Store & Platform Operations views."""
from decimal import Decimal
import pytest
from django.urls import reverse
from apps.ecommerce.models import (
    StorefrontInstance,
    StorefrontCatalogAssignment,
    PlatformEnvironment,
    DeploymentPipeline,
)


@pytest.mark.django_db
def test_multistore_hub_view(auth_client_a, ecom_storefront_a, ecom_environment_a):
    """Test MultiStore Hub view 200 OK and expected context keys."""
    url = reverse("ecommerce:multi_store_hub")
    response = auth_client_a.get(url)
    assert response.status_code == 200
    assert "total_storefronts" in response.context
    assert "active_storefronts" in response.context
    assert "total_environments" in response.context
    assert "production_environments" in response.context
    assert response.context["total_storefronts"] >= 1
    assert response.context["total_environments"] >= 1


@pytest.mark.django_db
def test_multistore_storefront_instance_views(auth_client_a, tenant_a, ecom_storefront_a, ecom_currency_usd):
    """Test StorefrontInstance list, create, detail, edit, delete, and toggle-status views."""
    # 1. List
    list_url = reverse("ecommerce:storefront_instance_list")
    resp = auth_client_a.get(list_url)
    assert resp.status_code == 200
    assert "storefront_instances" in resp.context

    # List with search and filter
    resp = auth_client_a.get(list_url + f"?q={ecom_storefront_a.name}&status=active")
    assert resp.status_code == 200
    assert len(resp.context["storefront_instances"]) >= 1

    # 2. Create GET & POST
    create_url = reverse("ecommerce:storefront_instance_create")
    assert auth_client_a.get(create_url).status_code == 200

    create_data = {
        "name": "B2B Wholesale Portal",
        "code": "b2b-portal",
        "store_type": "wholesale_b2b",
        "brand_name": "Apex Pro",
        "primary_domain": "b2b.apexoutdoors.com",
        "default_currency": ecom_currency_usd.pk,
        "supported_currencies": "USD,EUR",
        "default_locale": "en-US",
        "supported_locales": "en-US",
        "theme_identifier": "default-slate",
        "status": "active",
        "checkout_mode": "standard_multistep",
        "ssl_certificate_status": "active_provisioned",
    }
    resp = auth_client_a.post(create_url, data=create_data)
    assert resp.status_code == 302
    created = StorefrontInstance.objects.get(tenant=tenant_a, code="b2b-portal")
    assert created.name == "B2B Wholesale Portal"

    # 3. Detail
    detail_url = reverse("ecommerce:storefront_instance_detail", args=[created.pk])
    resp = auth_client_a.get(detail_url)
    assert resp.status_code == 200
    assert resp.context["storefront"] == created

    # 4. Edit GET & POST
    edit_url = reverse("ecommerce:storefront_instance_edit", args=[created.pk])
    assert auth_client_a.get(edit_url).status_code == 200
    create_data["name"] = "B2B Global Portal Updated"
    resp = auth_client_a.post(edit_url, data=create_data)
    assert resp.status_code == 302
    created.refresh_from_db()
    assert created.name == "B2B Global Portal Updated"

    # 5. Toggle Status
    toggle_url = reverse("ecommerce:storefront_toggle_status", args=[created.pk])
    assert auth_client_a.get(toggle_url).status_code == 405
    resp = auth_client_a.post(toggle_url)
    assert resp.status_code == 302
    created.refresh_from_db()
    assert created.status == "maintenance"

    # 6. Delete POST
    delete_url = reverse("ecommerce:storefront_instance_delete", args=[created.pk])
    assert auth_client_a.get(delete_url).status_code == 405
    resp = auth_client_a.post(delete_url)
    assert resp.status_code == 302
    assert not StorefrontInstance.objects.filter(pk=created.pk).exists()


@pytest.mark.django_db
def test_multistore_catalog_assignment_views(auth_client_a, tenant_a, ecom_storefront_a, ecom_product_a):
    """Test StorefrontCatalogAssignment list, junk-filter handling, create, detail, edit, delete."""
    list_url = reverse("ecommerce:storefront_catalog_assignment_list")
    # Non-digit filter handling (Finding I1 / CRIT-1)
    resp = auth_client_a.get(list_url + "?storefront=invalid_junk")
    assert resp.status_code == 200

    create_url = reverse("ecommerce:storefront_catalog_assignment_create")
    assert auth_client_a.get(create_url).status_code == 200

    create_data = {
        "storefront": ecom_storefront_a.pk,
        "product": ecom_product_a.pk,
        "is_visible": True,
        "is_featured": True,
        "custom_title": "Store Front Exclusive Title",
        "custom_price": "79.50",
        "sort_order": 5,
        "publish_status": "published",
    }
    resp = auth_client_a.post(create_url, data=create_data)
    assert resp.status_code == 302
    ca = StorefrontCatalogAssignment.objects.get(tenant=tenant_a, storefront=ecom_storefront_a, product=ecom_product_a)
    assert ca.custom_price == Decimal("79.50")

    # Detail
    detail_url = reverse("ecommerce:storefront_catalog_assignment_detail", args=[ca.pk])
    resp = auth_client_a.get(detail_url)
    assert resp.status_code == 200

    # Edit
    edit_url = reverse("ecommerce:storefront_catalog_assignment_edit", args=[ca.pk])
    create_data["custom_price"] = "89.00"
    resp = auth_client_a.post(edit_url, data=create_data)
    assert resp.status_code == 302
    ca.refresh_from_db()
    assert ca.custom_price == Decimal("89.00")

    # Delete
    delete_url = reverse("ecommerce:storefront_catalog_assignment_delete", args=[ca.pk])
    resp = auth_client_a.post(delete_url)
    assert resp.status_code == 302
    assert not StorefrontCatalogAssignment.objects.filter(pk=ca.pk).exists()


@pytest.mark.django_db
def test_multistore_platform_environment_views(auth_client_a, tenant_a, ecom_storefront_a):
    """Test PlatformEnvironment list with storefront filter, create, detail, edit, delete."""
    list_url = reverse("ecommerce:platform_environment_list")
    resp = auth_client_a.get(list_url + f"?storefront={ecom_storefront_a.pk}")
    assert resp.status_code == 200
    assert "storefronts" in resp.context

    create_url = reverse("ecommerce:platform_environment_create")
    assert auth_client_a.get(create_url).status_code == 200

    create_data = {
        "name": "Staging Cluster Beta",
        "env_type": "staging",
        "storefront": ecom_storefront_a.pk,
        "cluster_region": "us-east-1",
        "base_url": "https://staging-beta.example.com",
        "current_active_slot": "blue",
        "status": "healthy",
        "resource_tier": "standard",
    }
    resp = auth_client_a.post(create_url, data=create_data)
    assert resp.status_code == 302
    env = PlatformEnvironment.objects.get(tenant=tenant_a, name="Staging Cluster Beta")

    # Detail
    detail_url = reverse("ecommerce:platform_environment_detail", args=[env.pk])
    resp = auth_client_a.get(detail_url)
    assert resp.status_code == 200

    # Edit
    edit_url = reverse("ecommerce:platform_environment_edit", args=[env.pk])
    create_data["resource_tier"] = "high_performance"
    resp = auth_client_a.post(edit_url, data=create_data)
    assert resp.status_code == 302
    env.refresh_from_db()
    assert env.resource_tier == "high_performance"

    # Delete
    delete_url = reverse("ecommerce:platform_environment_delete", args=[env.pk])
    resp = auth_client_a.post(delete_url)
    assert resp.status_code == 302
    assert not PlatformEnvironment.objects.filter(pk=env.pk).exists()


@pytest.mark.django_db
def test_multistore_deployment_pipeline_views_and_lifecycle(auth_client_a, tenant_a, ecom_environment_a):
    """Test DeploymentPipeline list (with junk param), create, detail, promote cutover, and rollback."""
    list_url = reverse("ecommerce:deployment_pipeline_list")
    resp = auth_client_a.get(list_url + "?environment=invalid_junk")
    assert resp.status_code == 200

    create_url = reverse("ecommerce:deployment_pipeline_create")
    assert auth_client_a.get(create_url).status_code == 200

    create_data = {
        "environment": ecom_environment_a.pk,
        "release_version": "v3.0.0-prod",
        "git_branch": "release/v3.0",
        "git_commit_sha": "d4e5f678901234567890abcdef12345678901234",
        "deployment_strategy": "blue_green",
        "target_slot": "green",
        "status": "staging_preview",
        "traffic_percentage": 0,
        "build_duration_seconds": 180,
    }
    resp = auth_client_a.post(create_url, data=create_data)
    assert resp.status_code == 302
    pipeline = DeploymentPipeline.objects.get(tenant=tenant_a, release_version="v3.0.0-prod")
    assert pipeline.status == "staging_preview"

    # Detail view
    detail_url = reverse("ecommerce:deployment_pipeline_detail", args=[pipeline.pk])
    resp = auth_client_a.get(detail_url)
    assert resp.status_code == 200

    # Promote to active live traffic (Finding I3)
    promote_url = reverse("ecommerce:deployment_promote", args=[pipeline.pk])
    resp = auth_client_a.post(promote_url)
    assert resp.status_code == 302
    pipeline.refresh_from_db()
    ecom_environment_a.refresh_from_db()
    assert pipeline.status == "promoted_active"
    assert pipeline.traffic_percentage == 100
    assert ecom_environment_a.current_active_slot == "green"

    # Rollback from active live traffic
    rollback_url = reverse("ecommerce:deployment_rollback", args=[pipeline.pk])
    resp = auth_client_a.post(rollback_url)
    assert resp.status_code == 302
    pipeline.refresh_from_db()
    assert pipeline.status == "rolled_back"
    assert pipeline.traffic_percentage == 0
