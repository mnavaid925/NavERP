"""Tests for Module 9.20 Multi-Store & Platform Operations models."""
from decimal import Decimal
import pytest
from django.db import IntegrityError
from apps.ecommerce.models import (
    StorefrontInstance,
    StorefrontCatalogAssignment,
    PlatformEnvironment,
    DeploymentPipeline,
)
from apps.ecommerce.tests.conftest import (
    MULTISTORE_MODEL_FIELDS,
    _multistore_storefront_instance,
    _multistore_catalog_assignment,
    _multistore_platform_environment,
    _multistore_deployment_pipeline,
)


@pytest.mark.django_db
def test_multistore_model_contract_fields():
    """Assert all 4 models contain the exact fields pinned in MULTISTORE_MODEL_FIELDS."""
    model_map = {
        "StorefrontInstance": StorefrontInstance,
        "StorefrontCatalogAssignment": StorefrontCatalogAssignment,
        "PlatformEnvironment": PlatformEnvironment,
        "DeploymentPipeline": DeploymentPipeline,
    }
    for model_name, expected_fields in MULTISTORE_MODEL_FIELDS.items():
        model_cls = model_map[model_name]
        actual_fields = {f.name for f in model_cls._meta.get_fields()}
        for field in expected_fields:
            assert field in actual_fields, f"Field '{field}' missing from {model_name}"


@pytest.mark.django_db
def test_multistore_storefront_instance_creation(tenant_a, ecom_storefront_a):
    """Test StorefrontInstance creation, number auto-generation with prefix ESTR-, and str representation."""
    assert ecom_storefront_a.pk is not None
    assert ecom_storefront_a.tenant == tenant_a
    assert ecom_storefront_a.number.startswith("ESTR-")
    assert ecom_storefront_a.name == "Acme Main Storefront"
    assert ecom_storefront_a.code == "acme-main"
    assert str(ecom_storefront_a) == f"Acme Main Storefront ({ecom_storefront_a.number})"


@pytest.mark.django_db
def test_multistore_storefront_instance_unique_constraints(tenant_a, ecom_storefront_a):
    """Test that duplicate numbers within the same tenant are rejected."""
    with pytest.raises(IntegrityError):
        StorefrontInstance.objects.create(
            tenant=tenant_a,
            number=ecom_storefront_a.number,
            name="Duplicate Store",
            code="dup-code",
            default_currency=ecom_storefront_a.default_currency,
        )


@pytest.mark.django_db
def test_multistore_catalog_assignment_creation(tenant_a, ecom_storefront_a, ecom_product_a):
    """Test StorefrontCatalogAssignment creation, prefix ESCA-, pricing overrides, and non-FK str."""
    assignment = _multistore_catalog_assignment(
        tenant_a,
        ecom_storefront_a,
        ecom_product_a,
        custom_title="Special Promotion Title",
        custom_price=Decimal("49.95"),
    )
    assert assignment.pk is not None
    assert assignment.number.startswith("ESCA-")
    assert assignment.custom_price == Decimal("49.95")
    assert assignment.publish_status == "published"
    # Ensure __str__ uses non-FK fields per Rule L18
    assert str(assignment) == f"Special Promotion Title ({assignment.number})"


@pytest.mark.django_db
def test_multistore_catalog_assignment_unique_storefront_product(tenant_a, ecom_storefront_a, ecom_product_a):
    """Test that a product can only be assigned once per storefront within the same tenant."""
    _multistore_catalog_assignment(tenant_a, ecom_storefront_a, ecom_product_a)
    with pytest.raises(IntegrityError):
        _multistore_catalog_assignment(tenant_a, ecom_storefront_a, ecom_product_a)


@pytest.mark.django_db
def test_multistore_platform_environment_creation(tenant_a, ecom_storefront_a):
    """Test PlatformEnvironment creation, prefix EENV-, slot assignment, and str."""
    env = _multistore_platform_environment(
        tenant_a,
        storefront=ecom_storefront_a,
        name="Acme Production East",
        current_active_slot="blue",
    )
    assert env.pk is not None
    assert env.number.startswith("EENV-")
    assert env.env_type == "production"
    assert env.current_active_slot == "blue"
    assert env.status == "healthy"
    assert str(env) == f"Acme Production East ({env.get_env_type_display()}) [{env.number}]"


@pytest.mark.django_db
def test_multistore_deployment_pipeline_creation(tenant_a, ecom_environment_a):
    """Test DeploymentPipeline creation, prefix EDPL-, blue/green strategy, and non-FK str."""
    pipeline = _multistore_deployment_pipeline(
        tenant_a,
        ecom_environment_a,
        release_version="v2.5.0-rc1",
        target_slot="green",
    )
    assert pipeline.pk is not None
    assert pipeline.number.startswith("EDPL-")
    assert pipeline.release_version == "v2.5.0-rc1"
    assert pipeline.deployment_strategy == "blue_green"
    assert pipeline.target_slot == "green"
    # Ensure __str__ uses non-FK fields per Rule L18
    assert str(pipeline) == f"v2.5.0-rc1 [building] ({pipeline.number})"
