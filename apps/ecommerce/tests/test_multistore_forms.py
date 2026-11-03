"""Tests for Module 9.20 Multi-Store & Platform Operations forms."""
from decimal import Decimal
import pytest
from apps.ecommerce.forms.MultiStore.StorefrontInstances import StorefrontInstanceForm
from apps.ecommerce.forms.MultiStore.StorefrontCatalogAssignments import StorefrontCatalogAssignmentForm
from apps.ecommerce.forms.MultiStore.PlatformEnvironments import PlatformEnvironmentForm
from apps.ecommerce.forms.MultiStore.DeploymentPipelines import DeploymentPipelineForm
from apps.ecommerce.models import StorefrontInstance


@pytest.mark.django_db
def test_multistore_storefront_instance_form_valid(tenant_a, ecom_currency_usd):
    """Test valid StorefrontInstanceForm submission with domain normalization."""
    data = {
        "name": "Flagship US Store",
        "code": "us-flagship",
        "store_type": "retail_b2c",
        "brand_name": "Apex Outdoors",
        "primary_domain": "https://shop.apexoutdoors.com/store/",
        "default_currency": ecom_currency_usd.pk,
        "supported_currencies": "USD,EUR",
        "default_locale": "en-US",
        "supported_locales": "en-US,es-ES",
        "theme_identifier": "default-slate",
        "status": "active",
        "checkout_mode": "standard_multistep",
        "ssl_certificate_status": "active_provisioned",
    }
    form = StorefrontInstanceForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["primary_domain"] == "shop.apexoutdoors.com"


@pytest.mark.django_db
def test_multistore_storefront_instance_form_fk_scoping(tenant_a, tenant_b, ecom_storefront_b):
    """Test that StoreCategory and FulfillmentCenter choices are scoped to tenant."""
    form_a = StorefrontInstanceForm(tenant=tenant_a)
    assert form_a.fields["default_currency"].queryset.count() >= 1
    # Check tenant isolation on root_category and default_fulfillment_center
    assert not form_a.fields["root_category"].queryset.filter(tenant=tenant_b).exists()
    assert not form_a.fields["default_fulfillment_center"].queryset.filter(tenant=tenant_b).exists()


@pytest.mark.django_db
def test_multistore_catalog_assignment_form_valid(tenant_a, ecom_storefront_a, ecom_product_a):
    """Test valid StorefrontCatalogAssignmentForm creation."""
    data = {
        "storefront": ecom_storefront_a.pk,
        "product": ecom_product_a.pk,
        "is_visible": True,
        "custom_title": "Store Specific Title",
        "custom_price": "59.99",
        "sort_order": 0,
        "publish_status": "published",
    }
    form = StorefrontCatalogAssignmentForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_multistore_catalog_assignment_form_cross_tenant_rejection(tenant_a, tenant_b, ecom_storefront_a, ecom_product_b):
    """Test that submitting a product from tenant_b to tenant_a's storefront fails form validation."""
    data = {
        "storefront": ecom_storefront_a.pk,
        "product": ecom_product_b.pk,
        "is_visible": True,
        "sort_order": 0,
        "publish_status": "published",
    }
    form = StorefrontCatalogAssignmentForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "product" in form.errors


@pytest.mark.django_db
def test_multistore_platform_environment_form_valid(tenant_a, ecom_storefront_a):
    """Test valid PlatformEnvironmentForm creation."""
    data = {
        "name": "Staging Cluster Alpha",
        "env_type": "staging",
        "storefront": ecom_storefront_a.pk,
        "cluster_region": "us-east-1",
        "base_url": "https://staging-alpha.example.com",
        "current_active_slot": "blue",
        "status": "healthy",
        "resource_tier": "standard",
    }
    form = PlatformEnvironmentForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_multistore_deployment_pipeline_form_valid(tenant_a, ecom_environment_a):
    """Test valid DeploymentPipelineForm creation in pending/building state."""
    data = {
        "environment": ecom_environment_a.pk,
        "release_version": "v1.2.0-beta",
        "git_branch": "release/1.2",
        "git_commit_sha": "b2c3d4e5f678901234567890abcdef1234567890",
        "deployment_strategy": "blue_green",
        "target_slot": "green",
        "status": "building",
        "traffic_percentage": 0,
        "build_duration_seconds": 150,
    }
    form = DeploymentPipelineForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_multistore_deployment_pipeline_form_gate_bypass_rejected(tenant_a, ecom_environment_a):
    """Test that creating a new deployment directly as promoted_active with traffic > 0 is rejected (Finding I4)."""
    data = {
        "environment": ecom_environment_a.pk,
        "release_version": "v1.2.0-cheat",
        "git_branch": "main",
        "git_commit_sha": "c3d4e5f678901234567890abcdef123456789012",
        "deployment_strategy": "blue_green",
        "target_slot": "green",
        "status": "promoted_active",
        "traffic_percentage": 100,
    }
    form = DeploymentPipelineForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "status" in form.errors or "traffic_percentage" in form.errors
    assert "promotion workflow" in form.errors.get("status", [""])[0]
