"""Comprehensive security, multi-tenant IDOR, auth, and negative-input tests for Module 9.1 Product Catalog Management (`ecommerce`).

Conventions enforced:
- Every test function: test_productcatalog_<name>
- Every module-level helper: _productcatalog_<name>
- Multi-tenant isolation: Cross-tenant detail/edit/delete/publish access returns 404
- Authorization: Non-admin member blocked on delete actions (403)
- Method restriction: State mutations require POST (405 on GET)
- Input hardening: Malicious/negative filter params do not 500
- XSS prevention: User-supplied HTML/scripts in models are escaped
- CSV security: Formula injection sanitization on export and format/size validation on import
"""
import csv
from decimal import Decimal
import io
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.ecommerce.models import (
    CatalogProduct,
    ProductRelationship,
    ProductVariant,
    StoreCategory,
)
from apps.ecommerce.tests.conftest import (
    _productcatalog_category,
    _productcatalog_product,
    _productcatalog_relationship,
    _productcatalog_variant,
)
from apps.scm.models.InventoryManagement.Items import Item

pytestmark = pytest.mark.django_db


# ==============================================================================
# Module Helpers (_productcatalog_*)
# ==============================================================================

def _productcatalog_create_file(filename, content, content_type="text/csv"):
    """Helper to generate a SimpleUploadedFile for upload testing."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return SimpleUploadedFile(filename, content, content_type=content_type)


def _productcatalog_assert_login_redirect(response):
    """Helper asserting redirect to login page for unauthenticated access."""
    assert response.status_code == 302
    assert "login" in response.headers.get("Location", "")


# ==============================================================================
# 1. Multi-Tenant Isolation & IDOR Tests
# ==============================================================================

def test_productcatalog_idor_storecategory_detail_cross_tenant_returns_404(
    client_a, client_b, ecom_category_a, ecom_category_b
):
    """Assert tenant A cannot view tenant B's store category detail and vice versa."""
    resp_a = client_a.get(reverse("ecommerce:storecategory_detail", kwargs={"pk": ecom_category_b.pk}))
    assert resp_a.status_code == 404

    resp_b = client_b.get(reverse("ecommerce:storecategory_detail", kwargs={"pk": ecom_category_a.pk}))
    assert resp_b.status_code == 404


def test_productcatalog_idor_storecategory_edit_cross_tenant_returns_404(
    client_a, client_b, ecom_category_a, ecom_category_b
):
    """Assert tenant A cannot GET or POST to edit tenant B's category."""
    # GET edit form
    resp_get = client_a.get(reverse("ecommerce:storecategory_edit", kwargs={"pk": ecom_category_b.pk}))
    assert resp_get.status_code == 404

    # POST update
    resp_post = client_a.post(
        reverse("ecommerce:storecategory_edit", kwargs={"pk": ecom_category_b.pk}),
        data={"name": "Hacked Category", "slug": "hacked-category", "display_order": 1},
    )
    assert resp_post.status_code == 404

    ecom_category_b.refresh_from_db()
    assert ecom_category_b.name != "Hacked Category"


def test_productcatalog_idor_storecategory_delete_cross_tenant_returns_404(
    client_a, client_b, ecom_category_a, ecom_category_b
):
    """Assert tenant A cannot delete tenant B's store category."""
    resp = client_a.post(reverse("ecommerce:storecategory_delete", kwargs={"pk": ecom_category_b.pk}))
    assert resp.status_code == 404

    # Verify category still exists
    assert StoreCategory.objects.filter(pk=ecom_category_b.pk).exists()


def test_productcatalog_idor_catalogproduct_detail_cross_tenant_returns_404(
    client_a, client_b, ecom_product_a, ecom_product_b
):
    """Assert tenant A cannot view tenant B's product detail and vice versa."""
    resp_a = client_a.get(reverse("ecommerce:catalogproduct_detail", kwargs={"pk": ecom_product_b.pk}))
    assert resp_a.status_code == 404

    resp_b = client_b.get(reverse("ecommerce:catalogproduct_detail", kwargs={"pk": ecom_product_a.pk}))
    assert resp_b.status_code == 404


def test_productcatalog_idor_catalogproduct_edit_cross_tenant_returns_404(
    client_a, client_b, ecom_product_a, ecom_product_b
):
    """Assert tenant A cannot GET or POST to edit tenant B's product."""
    resp_get = client_a.get(reverse("ecommerce:catalogproduct_edit", kwargs={"pk": ecom_product_b.pk}))
    assert resp_get.status_code == 404

    resp_post = client_a.post(
        reverse("ecommerce:catalogproduct_edit", kwargs={"pk": ecom_product_b.pk}),
        data={"name": "Tampered Product", "slug": "tampered-product", "status": "draft", "visibility": "storefront"},
    )
    assert resp_post.status_code == 404

    ecom_product_b.refresh_from_db()
    assert ecom_product_b.name != "Tampered Product"


def test_productcatalog_idor_catalogproduct_delete_cross_tenant_returns_404(
    client_a, client_b, ecom_product_a, ecom_product_b
):
    """Assert tenant A cannot delete tenant B's product."""
    resp = client_a.post(reverse("ecommerce:catalogproduct_delete", kwargs={"pk": ecom_product_b.pk}))
    assert resp.status_code == 404

    assert CatalogProduct.objects.filter(pk=ecom_product_b.pk).exists()


def test_productcatalog_idor_catalogproduct_publish_cross_tenant_returns_404(
    client_a, client_b, ecom_product_a, ecom_product_b
):
    """Assert tenant A cannot publish/unpublish tenant B's product."""
    original_status = ecom_product_b.status
    resp = client_a.post(reverse("ecommerce:catalogproduct_publish", kwargs={"pk": ecom_product_b.pk}))
    assert resp.status_code == 404

    ecom_product_b.refresh_from_db()
    assert ecom_product_b.status == original_status


def test_productcatalog_idor_productvariant_detail_cross_tenant_returns_404(
    client_a, client_b, ecom_variant_a, ecom_variant_b
):
    """Assert tenant A cannot view tenant B's variant detail and vice versa."""
    resp_a = client_a.get(reverse("ecommerce:productvariant_detail", kwargs={"pk": ecom_variant_b.pk}))
    assert resp_a.status_code == 404

    resp_b = client_b.get(reverse("ecommerce:productvariant_detail", kwargs={"pk": ecom_variant_a.pk}))
    assert resp_b.status_code == 404


def test_productcatalog_idor_productvariant_edit_cross_tenant_returns_404(
    client_a, client_b, ecom_variant_a, ecom_variant_b
):
    """Assert tenant A cannot GET or POST to edit tenant B's variant."""
    resp_get = client_a.get(reverse("ecommerce:productvariant_edit", kwargs={"pk": ecom_variant_b.pk}))
    assert resp_get.status_code == 404

    resp_post = client_a.post(
        reverse("ecommerce:productvariant_edit", kwargs={"pk": ecom_variant_b.pk}),
        data={
            "product": ecom_variant_b.product_id,
            "name": "Tampered Variant",
            "sku": "HACKED-SKU",
            "price": "1.00",
            "cost_price": "0.50",
            "weight_kg": "0.100",
            "sort_order": 0,
        },
    )
    assert resp_post.status_code == 404

    ecom_variant_b.refresh_from_db()
    assert ecom_variant_b.sku != "HACKED-SKU"


def test_productcatalog_idor_productvariant_delete_cross_tenant_returns_404(
    client_a, client_b, ecom_variant_a, ecom_variant_b
):
    """Assert tenant A cannot delete tenant B's product variant."""
    resp = client_a.post(reverse("ecommerce:productvariant_delete", kwargs={"pk": ecom_variant_b.pk}))
    assert resp.status_code == 404

    assert ProductVariant.objects.filter(pk=ecom_variant_b.pk).exists()


def test_productcatalog_idor_productrelationship_detail_cross_tenant_returns_404(
    client_a, client_b, ecom_relationship_a, ecom_relationship_b
):
    """Assert tenant A cannot view tenant B's relationship detail and vice versa."""
    resp_a = client_a.get(reverse("ecommerce:productrelationship_detail", kwargs={"pk": ecom_relationship_b.pk}))
    assert resp_a.status_code == 404

    resp_b = client_b.get(reverse("ecommerce:productrelationship_detail", kwargs={"pk": ecom_relationship_a.pk}))
    assert resp_b.status_code == 404


def test_productcatalog_idor_productrelationship_edit_cross_tenant_returns_404(
    client_a, client_b, ecom_relationship_a, ecom_relationship_b
):
    """Assert tenant A cannot GET or POST to edit tenant B's relationship."""
    resp_get = client_a.get(reverse("ecommerce:productrelationship_edit", kwargs={"pk": ecom_relationship_b.pk}))
    assert resp_get.status_code == 404

    resp_post = client_a.post(
        reverse("ecommerce:productrelationship_edit", kwargs={"pk": ecom_relationship_b.pk}),
        data={
            "source_product": ecom_relationship_b.source_product_id,
            "target_product": ecom_relationship_b.target_product_id,
            "relationship_type": "cross_sell",
            "discount_pct": "10.00",
            "sort_order": 0,
            "notes": "Hacked Notes",
        },
    )
    assert resp_post.status_code == 404

    ecom_relationship_b.refresh_from_db()
    assert ecom_relationship_b.notes != "Hacked Notes"


def test_productcatalog_idor_productrelationship_delete_cross_tenant_returns_404(
    client_a, client_b, ecom_relationship_a, ecom_relationship_b
):
    """Assert tenant A cannot delete tenant B's product relationship."""
    resp = client_a.post(reverse("ecommerce:productrelationship_delete", kwargs={"pk": ecom_relationship_b.pk}))
    assert resp.status_code == 404

    assert ProductRelationship.objects.filter(pk=ecom_relationship_b.pk).exists()


# ==============================================================================
# 2. Multi-Tenant List Isolation & Data Leakage Protection
# ==============================================================================

def test_productcatalog_tenant_isolation_storecategory_list(client_a, client_b, ecom_category_a, ecom_category_b):
    """Assert category list never leaks items across tenant boundaries."""
    resp_a = client_a.get(reverse("ecommerce:storecategory_list"))
    assert resp_a.status_code == 200
    content_a = resp_a.content.decode()
    assert ecom_category_a.name in content_a
    assert ecom_category_b.name not in content_a

    resp_b = client_b.get(reverse("ecommerce:storecategory_list"))
    assert resp_b.status_code == 200
    content_b = resp_b.content.decode()
    assert ecom_category_b.name in content_b
    assert ecom_category_a.name not in content_b


def test_productcatalog_tenant_isolation_catalogproduct_list(client_a, client_b, ecom_product_a, ecom_product_b):
    """Assert product list never leaks products across tenant boundaries."""
    resp_a = client_a.get(reverse("ecommerce:catalogproduct_list"))
    assert resp_a.status_code == 200
    content_a = resp_a.content.decode()
    assert ecom_product_a.name in content_a
    assert ecom_product_b.name not in content_a

    resp_b = client_b.get(reverse("ecommerce:catalogproduct_list"))
    assert resp_b.status_code == 200
    content_b = resp_b.content.decode()
    assert ecom_product_b.name in content_b
    assert ecom_product_a.name not in content_b


def test_productcatalog_tenant_isolation_productvariant_list(client_a, client_b, ecom_variant_a, ecom_variant_b):
    """Assert variant list never leaks variants across tenant boundaries."""
    resp_a = client_a.get(reverse("ecommerce:productvariant_list"))
    assert resp_a.status_code == 200
    content_a = resp_a.content.decode()
    assert ecom_variant_a.sku in content_a
    assert ecom_variant_b.sku not in content_a

    resp_b = client_b.get(reverse("ecommerce:productvariant_list"))
    assert resp_b.status_code == 200
    content_b = resp_b.content.decode()
    assert ecom_variant_b.sku in content_b
    assert ecom_variant_a.sku not in content_b


def test_productcatalog_tenant_isolation_productrelationship_list(
    client_a, client_b, ecom_relationship_a, ecom_relationship_b
):
    """Assert relationship list never leaks relationships across tenant boundaries."""
    resp_a = client_a.get(reverse("ecommerce:productrelationship_list"))
    assert resp_a.status_code == 200
    content_a = resp_a.content.decode()
    assert ecom_relationship_a.source_product.name in content_a
    assert ecom_relationship_a.target_product.name in content_a
    assert ecom_relationship_b.source_product.name not in content_a
    assert ecom_relationship_b.target_product.name not in content_a

    resp_b = client_b.get(reverse("ecommerce:productrelationship_list"))
    assert resp_b.status_code == 200
    content_b = resp_b.content.decode()
    assert ecom_relationship_b.source_product.name in content_b
    assert ecom_relationship_b.target_product.name in content_b
    assert ecom_relationship_a.source_product.name not in content_b
    assert ecom_relationship_a.target_product.name not in content_b


def test_productcatalog_tenant_isolation_catalog_overview(
    client_a, client_b, ecom_category_a, ecom_category_b, ecom_product_a, ecom_product_b
):
    """Assert overview dashboard only shows current tenant's counts and recent items."""
    resp_a = client_a.get(reverse("ecommerce:catalog_overview"))
    assert resp_a.status_code == 200
    content_a = resp_a.content.decode()
    assert ecom_product_a.name in content_a
    assert ecom_product_b.name not in content_a

    resp_b = client_b.get(reverse("ecommerce:catalog_overview"))
    assert resp_b.status_code == 200
    content_b = resp_b.content.decode()
    assert ecom_product_b.name in content_b
    assert ecom_product_a.name not in content_b


def test_productcatalog_tenant_isolation_csv_export(
    client_a, client_b, ecom_product_a, ecom_variant_a, ecom_product_b, ecom_variant_b
):
    """Assert CSV export only outputs records belonging to the requesting tenant."""
    resp_a = client_a.get(reverse("ecommerce:product_export_csv"))
    assert resp_a.status_code == 200
    content_a = resp_a.content.decode("utf-8")
    assert ecom_product_a.name in content_a
    assert ecom_variant_a.sku in content_a
    assert ecom_product_b.name not in content_a
    assert ecom_variant_b.sku not in content_a

    resp_b = client_b.get(reverse("ecommerce:product_export_csv"))
    assert resp_b.status_code == 200
    content_b = resp_b.content.decode("utf-8")
    assert ecom_product_b.name in content_b
    assert ecom_variant_b.sku in content_b
    assert ecom_product_a.name not in content_b
    assert ecom_variant_a.sku not in content_b


# ==============================================================================
# 3. Cross-Tenant Foreign Key Assignment Prevention
# ==============================================================================

def test_productcatalog_cross_tenant_fk_category_assignment_rejected(client_a, tenant_a, ecom_category_b):
    """Assert tenant A cannot assign tenant B's StoreCategory as primary category."""
    payload = {
        "name": "Cross Tenant Product",
        "slug": "cross-tenant-product",
        "primary_category": ecom_category_b.pk,
        "status": "draft",
        "visibility": "storefront",
    }
    resp = client_a.post(reverse("ecommerce:catalogproduct_create"), data=payload)
    # Form should fail validation (returns 200 with form error), not redirect
    assert resp.status_code == 200
    assert not CatalogProduct.objects.filter(slug="cross-tenant-product").exists()


def test_productcatalog_cross_tenant_fk_category_m2m_assignment_rejected(client_a, tenant_a, ecom_category_b):
    """Assert tenant A cannot assign tenant B's StoreCategory in categories M2M."""
    payload = {
        "name": "Cross Tenant M2M Product",
        "slug": "cross-tenant-m2m-product",
        "categories": [ecom_category_b.pk],
        "status": "draft",
        "visibility": "storefront",
    }
    resp = client_a.post(reverse("ecommerce:catalogproduct_create"), data=payload)
    assert resp.status_code == 200
    assert not CatalogProduct.objects.filter(slug="cross-tenant-m2m-product").exists()


def test_productcatalog_cross_tenant_fk_product_item_assignment_rejected(client_a, tenant_a, tenant_b):
    """Assert tenant A cannot assign tenant B's inventory Item to a CatalogProduct."""
    foreign_item = Item.objects.create(tenant=tenant_b, sku="FOREIGN-ITEM-01", name="Foreign Stock Item")
    payload = {
        "name": "Cross Item Product",
        "slug": "cross-item-product",
        "item": foreign_item.pk,
        "status": "draft",
        "visibility": "storefront",
    }
    resp = client_a.post(reverse("ecommerce:catalogproduct_create"), data=payload)
    assert resp.status_code == 200
    assert not CatalogProduct.objects.filter(slug="cross-item-product").exists()


def test_productcatalog_cross_tenant_fk_parent_category_assignment_rejected(client_a, tenant_a, ecom_category_b):
    """Assert tenant A cannot set parent category to tenant B's category."""
    payload = {
        "name": "Subcategory Attempt",
        "slug": "subcat-attempt",
        "parent": ecom_category_b.pk,
        "display_order": 0,
        "is_active": True,
    }
    resp = client_a.post(reverse("ecommerce:storecategory_create"), data=payload)
    assert resp.status_code == 200
    assert not StoreCategory.objects.filter(slug="subcat-attempt").exists()


def test_productcatalog_cross_tenant_fk_variant_product_assignment_rejected(client_a, tenant_a, ecom_product_b):
    """Assert tenant A cannot create a ProductVariant attached to tenant B's product."""
    payload = {
        "product": ecom_product_b.pk,
        "sku": "INTRUDER-VAR-01",
        "name": "Intruder Variant",
        "price": "99.00",
        "cost_price": "50.00",
        "weight_kg": "0.500",
        "sort_order": 0,
    }
    resp = client_a.post(reverse("ecommerce:productvariant_create"), data=payload)
    assert resp.status_code == 200
    assert not ProductVariant.objects.filter(sku="INTRUDER-VAR-01").exists()


def test_productcatalog_cross_tenant_fk_variant_item_assignment_rejected(
    client_a, tenant_a, tenant_b, ecom_product_a
):
    """Assert tenant A cannot assign tenant B's warehouse item to a ProductVariant."""
    foreign_item = Item.objects.create(tenant=tenant_b, sku="FOREIGN-VAR-ITEM", name="Foreign Var Item")
    payload = {
        "product": ecom_product_a.pk,
        "sku": "VAR-FOREIGN-ITEM",
        "name": "Variant with foreign item",
        "item": foreign_item.pk,
        "price": "50.00",
        "cost_price": "20.00",
        "weight_kg": "0.200",
        "sort_order": 0,
    }
    resp = client_a.post(reverse("ecommerce:productvariant_create"), data=payload)
    assert resp.status_code == 200
    assert not ProductVariant.objects.filter(sku="VAR-FOREIGN-ITEM").exists()


def test_productcatalog_cross_tenant_fk_relationship_products_rejected(
    client_a, tenant_a, ecom_product_a, ecom_product_b
):
    """Assert tenant A cannot link source product in tenant A to target product in tenant B."""
    payload = {
        "source_product": ecom_product_a.pk,
        "target_product": ecom_product_b.pk,
        "relationship_type": "cross_sell",
        "discount_pct": "5.00",
        "sort_order": 0,
    }
    resp = client_a.post(reverse("ecommerce:productrelationship_create"), data=payload)
    assert resp.status_code == 200
    assert not ProductRelationship.objects.filter(
        source_product=ecom_product_a, target_product=ecom_product_b
    ).exists()


# ==============================================================================
# 4. Authentication & Authorization Gates
# ==============================================================================

@pytest.mark.parametrize(
    "route_name,kwargs",
    [
        ("ecommerce:catalog_overview", {}),
        ("ecommerce:dashboard", {}),
        ("ecommerce:product_import_csv", {}),
        ("ecommerce:product_export_csv", {}),
        ("ecommerce:storecategory_list", {}),
        ("ecommerce:storecategory_create", {}),
        ("ecommerce:storecategory_detail", {"pk": 1}),
        ("ecommerce:storecategory_edit", {"pk": 1}),
        ("ecommerce:storecategory_delete", {"pk": 1}),
        ("ecommerce:catalogproduct_list", {}),
        ("ecommerce:catalogproduct_create", {}),
        ("ecommerce:catalogproduct_detail", {"pk": 1}),
        ("ecommerce:catalogproduct_edit", {"pk": 1}),
        ("ecommerce:catalogproduct_delete", {"pk": 1}),
        ("ecommerce:catalogproduct_publish", {"pk": 1}),
        ("ecommerce:productvariant_list", {}),
        ("ecommerce:productvariant_create", {}),
        ("ecommerce:productvariant_detail", {"pk": 1}),
        ("ecommerce:productvariant_edit", {"pk": 1}),
        ("ecommerce:productvariant_delete", {"pk": 1}),
        ("ecommerce:productrelationship_list", {}),
        ("ecommerce:productrelationship_create", {}),
        ("ecommerce:productrelationship_detail", {"pk": 1}),
        ("ecommerce:productrelationship_edit", {"pk": 1}),
        ("ecommerce:productrelationship_delete", {"pk": 1}),
    ],
)
def test_productcatalog_unauthenticated_request_redirects_to_login(route_name, kwargs):
    """Assert all ecommerce endpoints redirect unauthenticated requests to login."""
    anon_client = Client()
    url = reverse(route_name, kwargs=kwargs) if kwargs else reverse(route_name)
    resp = anon_client.get(url)
    _productcatalog_assert_login_redirect(resp)


def test_productcatalog_storecategory_delete_requires_tenant_admin(member_client, ecom_category_a):
    """Assert non-admin tenant member receives 403 Forbidden on store category deletion."""
    resp = member_client.post(reverse("ecommerce:storecategory_delete", kwargs={"pk": ecom_category_a.pk}))
    assert resp.status_code == 403
    assert StoreCategory.objects.filter(pk=ecom_category_a.pk).exists()


def test_productcatalog_catalogproduct_delete_requires_tenant_admin(member_client, ecom_product_a):
    """Assert non-admin tenant member receives 403 Forbidden on catalog product deletion."""
    resp = member_client.post(reverse("ecommerce:catalogproduct_delete", kwargs={"pk": ecom_product_a.pk}))
    assert resp.status_code == 403
    assert CatalogProduct.objects.filter(pk=ecom_product_a.pk).exists()


def test_productcatalog_productvariant_delete_requires_tenant_admin(member_client, ecom_variant_a):
    """Assert non-admin tenant member receives 403 Forbidden on product variant deletion."""
    resp = member_client.post(reverse("ecommerce:productvariant_delete", kwargs={"pk": ecom_variant_a.pk}))
    assert resp.status_code == 403
    assert ProductVariant.objects.filter(pk=ecom_variant_a.pk).exists()


def test_productcatalog_productrelationship_delete_requires_tenant_admin(member_client, ecom_relationship_a):
    """Assert non-admin tenant member receives 403 Forbidden on product relationship deletion."""
    resp = member_client.post(reverse("ecommerce:productrelationship_delete", kwargs={"pk": ecom_relationship_a.pk}))
    assert resp.status_code == 403
    assert ProductRelationship.objects.filter(pk=ecom_relationship_a.pk).exists()


def test_productcatalog_storecategory_delete_requires_post(client_a, ecom_category_a):
    """Assert GET request on store category delete receives 405 MethodNotAllowed."""
    resp = client_a.get(reverse("ecommerce:storecategory_delete", kwargs={"pk": ecom_category_a.pk}))
    assert resp.status_code == 405
    assert StoreCategory.objects.filter(pk=ecom_category_a.pk).exists()


def test_productcatalog_catalogproduct_delete_requires_post(client_a, ecom_product_a):
    """Assert GET request on catalog product delete receives 405 MethodNotAllowed."""
    resp = client_a.get(reverse("ecommerce:catalogproduct_delete", kwargs={"pk": ecom_product_a.pk}))
    assert resp.status_code == 405
    assert CatalogProduct.objects.filter(pk=ecom_product_a.pk).exists()


def test_productcatalog_catalogproduct_publish_requires_post(client_a, ecom_product_a):
    """Assert GET request on catalog product publish receives 405 MethodNotAllowed."""
    original_status = ecom_product_a.status
    resp = client_a.get(reverse("ecommerce:catalogproduct_publish", kwargs={"pk": ecom_product_a.pk}))
    assert resp.status_code == 405
    ecom_product_a.refresh_from_db()
    assert ecom_product_a.status == original_status


def test_productcatalog_productvariant_delete_requires_post(client_a, ecom_variant_a):
    """Assert GET request on product variant delete receives 405 MethodNotAllowed."""
    resp = client_a.get(reverse("ecommerce:productvariant_delete", kwargs={"pk": ecom_variant_a.pk}))
    assert resp.status_code == 405
    assert ProductVariant.objects.filter(pk=ecom_variant_a.pk).exists()


def test_productcatalog_productrelationship_delete_requires_post(client_a, ecom_relationship_a):
    """Assert GET request on product relationship delete receives 405 MethodNotAllowed."""
    resp = client_a.get(reverse("ecommerce:productrelationship_delete", kwargs={"pk": ecom_relationship_a.pk}))
    assert resp.status_code == 405
    assert ProductRelationship.objects.filter(pk=ecom_relationship_a.pk).exists()


# ==============================================================================
# 5. Mass Assignment Protection
# ==============================================================================

def test_productcatalog_mass_assignment_catalogproduct_create(client_a, tenant_a, tenant_b):
    """Assert posting tenant, number, pim_completeness, or published_at does not overwrite instance attributes."""
    payload = {
        "name": "Mass Assignment Product",
        "slug": "mass-assignment-prod",
        "status": "draft",
        "visibility": "storefront",
        # Attack payload attempting mass-assignment
        "tenant": tenant_b.pk,
        "tenant_id": tenant_b.pk,
        "number": "PRD-FORGED-0001",
        "pim_completeness": "99.99",
        "published_at": "2020-01-01 00:00:00",
    }
    resp = client_a.post(reverse("ecommerce:catalogproduct_create"), data=payload)
    assert resp.status_code == 302

    product = CatalogProduct.objects.get(slug="mass-assignment-prod")
    assert product.tenant == tenant_a
    assert product.number != "PRD-FORGED-0001"
    assert product.number.startswith("EPRD-")
    assert product.published_at is None
    assert product.pim_completeness != Decimal("99.99")


def test_productcatalog_mass_assignment_catalogproduct_edit(client_a, ecom_product_a, tenant_b):
    """Assert editing a product ignores tenant and number override attempts."""
    original_number = ecom_product_a.number
    original_tenant = ecom_product_a.tenant
    payload = {
        "name": "Edited Name Legit",
        "slug": ecom_product_a.slug,
        "status": "draft",
        "visibility": "storefront",
        "tenant": tenant_b.pk,
        "tenant_id": tenant_b.pk,
        "number": "PRD-HACKED-9999",
        "published_at": "2021-01-01 00:00:00",
    }
    resp = client_a.post(reverse("ecommerce:catalogproduct_edit", kwargs={"pk": ecom_product_a.pk}), data=payload)
    assert resp.status_code == 302

    ecom_product_a.refresh_from_db()
    assert ecom_product_a.name == "Edited Name Legit"
    assert ecom_product_a.tenant == original_tenant
    assert ecom_product_a.number == original_number


def test_productcatalog_mass_assignment_storecategory_create(client_a, tenant_a, tenant_b):
    """Assert creating a store category ignores tenant and number overrides."""
    payload = {
        "name": "Mass Assign Category",
        "slug": "mass-assign-cat",
        "display_order": 1,
        "is_active": True,
        "tenant": tenant_b.pk,
        "tenant_id": tenant_b.pk,
        "number": "CAT-FORGED-9999",
    }
    resp = client_a.post(reverse("ecommerce:storecategory_create"), data=payload)
    assert resp.status_code == 302

    cat = StoreCategory.objects.get(slug="mass-assign-cat")
    assert cat.tenant == tenant_a
    assert cat.number != "CAT-FORGED-9999"
    assert cat.number.startswith("ECAT-")


def test_productcatalog_mass_assignment_storecategory_edit(client_a, ecom_category_a, tenant_b):
    """Assert editing a category cannot overwrite tenant or number."""
    original_number = ecom_category_a.number
    original_tenant = ecom_category_a.tenant
    payload = {
        "name": "Renamed Category",
        "slug": ecom_category_a.slug,
        "display_order": 2,
        "is_active": True,
        "tenant": tenant_b.pk,
        "number": "CAT-OVERRIDE",
    }
    resp = client_a.post(reverse("ecommerce:storecategory_edit", kwargs={"pk": ecom_category_a.pk}), data=payload)
    assert resp.status_code == 302

    ecom_category_a.refresh_from_db()
    assert ecom_category_a.tenant == original_tenant
    assert ecom_category_a.number == original_number


def test_productcatalog_mass_assignment_productvariant_create(client_a, ecom_product_a, tenant_a, tenant_b):
    """Assert creating a variant ignores tenant and number overrides."""
    payload = {
        "product": ecom_product_a.pk,
        "sku": "VAR-MASS-ASSIGN",
        "name": "Standard Variant",
        "price": "49.99",
        "cost_price": "20.00",
        "weight_kg": "0.500",
        "sort_order": 0,
        "is_active": True,
        "tenant": tenant_b.pk,
        "number": "VAR-FORGED-777",
    }
    resp = client_a.post(reverse("ecommerce:productvariant_create"), data=payload)
    assert resp.status_code == 302

    var = ProductVariant.objects.get(sku="VAR-MASS-ASSIGN")
    assert var.tenant == tenant_a
    assert var.number != "VAR-FORGED-777"
    assert var.number.startswith("PVR-")


def test_productcatalog_mass_assignment_productvariant_edit(client_a, ecom_variant_a, tenant_b):
    """Assert editing a variant cannot overwrite tenant or number."""
    original_number = ecom_variant_a.number
    original_tenant = ecom_variant_a.tenant
    payload = {
        "product": ecom_variant_a.product_id,
        "sku": ecom_variant_a.sku,
        "name": "Renamed Variant",
        "price": "59.99",
        "cost_price": "25.00",
        "weight_kg": "0.600",
        "sort_order": 1,
        "is_active": True,
        "tenant": tenant_b.pk,
        "number": "VAR-OVERRIDE",
    }
    resp = client_a.post(reverse("ecommerce:productvariant_edit", kwargs={"pk": ecom_variant_a.pk}), data=payload)
    assert resp.status_code == 302

    ecom_variant_a.refresh_from_db()
    assert ecom_variant_a.tenant == original_tenant
    assert ecom_variant_a.number == original_number


def test_productcatalog_mass_assignment_productrelationship_create(client_a, ecom_product_a, tenant_a, tenant_b):
    """Assert creating a relationship ignores tenant and number overrides."""
    target_prod = _productcatalog_product(tenant_a, name="Target Product Rel", slug="target-prod-rel")
    payload = {
        "source_product": ecom_product_a.pk,
        "target_product": target_prod.pk,
        "relationship_type": "cross_sell",
        "discount_pct": "10.00",
        "sort_order": 0,
        "is_active": True,
        "tenant": tenant_b.pk,
        "number": "REL-FORGED-555",
    }
    resp = client_a.post(reverse("ecommerce:productrelationship_create"), data=payload)
    assert resp.status_code == 302

    rel = ProductRelationship.objects.get(source_product=ecom_product_a, target_product=target_prod)
    assert rel.tenant == tenant_a
    assert rel.number != "REL-FORGED-555"
    assert rel.number.startswith("PRL-")


def test_productcatalog_mass_assignment_productrelationship_edit(client_a, ecom_relationship_a, tenant_b):
    """Assert editing a relationship cannot overwrite tenant or number."""
    original_number = ecom_relationship_a.number
    original_tenant = ecom_relationship_a.tenant
    payload = {
        "source_product": ecom_relationship_a.source_product_id,
        "target_product": ecom_relationship_a.target_product_id,
        "relationship_type": "up_sell",
        "discount_pct": "15.00",
        "sort_order": 1,
        "is_active": True,
        "tenant": tenant_b.pk,
        "number": "REL-OVERRIDE",
    }
    resp = client_a.post(
        reverse("ecommerce:productrelationship_edit", kwargs={"pk": ecom_relationship_a.pk}), data=payload
    )
    assert resp.status_code == 302

    ecom_relationship_a.refresh_from_db()
    assert ecom_relationship_a.tenant == original_tenant
    assert ecom_relationship_a.number == original_number


# ==============================================================================
# 6. XSS & Template Escaping Tests
# ==============================================================================

def test_productcatalog_xss_storecategory_escaping(client_a, tenant_a):
    """Assert malicious script tags in StoreCategory name/description are HTML-escaped."""
    cat = StoreCategory.objects.create(
        tenant=tenant_a,
        name='<script>alert("xss-cat-name")</script>',
        slug="xss-cat-slug",
        description='<script>alert("xss-cat-desc")</script>',
        is_active=True,
    )
    # List view
    resp_list = client_a.get(reverse("ecommerce:storecategory_list"))
    assert resp_list.status_code == 200
    assert b'<script>alert("xss-cat-name")</script>' not in resp_list.content
    assert b"&lt;script&gt;alert(" in resp_list.content

    # Detail view
    resp_detail = client_a.get(reverse("ecommerce:storecategory_detail", kwargs={"pk": cat.pk}))
    assert resp_detail.status_code == 200
    assert b'<script>alert("xss-cat-name")</script>' not in resp_detail.content
    assert b'<script>alert("xss-cat-desc")</script>' not in resp_detail.content
    assert b"&lt;script&gt;alert(" in resp_detail.content


def test_productcatalog_xss_catalogproduct_escaping(client_a, tenant_a):
    """Assert malicious script tags in CatalogProduct name/descriptions are HTML-escaped."""
    prod = CatalogProduct.objects.create(
        tenant=tenant_a,
        name='<script>alert("xss-prod-name")</script>',
        slug="xss-prod-slug",
        short_description='<img src=x onerror=alert("xss-short")>',
        description='<script>alert("xss-prod-desc")</script>',
        status="active",
        visibility="storefront",
    )
    # List view
    resp_list = client_a.get(reverse("ecommerce:catalogproduct_list"))
    assert resp_list.status_code == 200
    assert b'<script>alert("xss-prod-name")</script>' not in resp_list.content
    assert b"&lt;script&gt;alert(" in resp_list.content

    # Detail view
    resp_detail = client_a.get(reverse("ecommerce:catalogproduct_detail", kwargs={"pk": prod.pk}))
    assert resp_detail.status_code == 200
    assert b'<script>alert("xss-prod-name")</script>' not in resp_detail.content
    assert b'<script>alert("xss-prod-desc")</script>' not in resp_detail.content
    assert b'<img src=x onerror=alert("xss-short")>' not in resp_detail.content
    assert b"&lt;script&gt;alert(" in resp_detail.content


def test_productcatalog_xss_productvariant_escaping(client_a, tenant_a, ecom_product_a):
    """Assert malicious script tags in ProductVariant name/sku are HTML-escaped."""
    var = ProductVariant.objects.create(
        tenant=tenant_a,
        product=ecom_product_a,
        sku="SKU-<script>",
        name='<script>alert("xss-var-name")</script>',
        price=Decimal("19.99"),
        is_active=True,
    )
    # List view
    resp_list = client_a.get(reverse("ecommerce:productvariant_list"))
    assert resp_list.status_code == 200
    assert b'<script>alert("xss-var-name")</script>' not in resp_list.content
    assert b"&lt;script&gt;alert(" in resp_list.content

    # Detail view
    resp_detail = client_a.get(reverse("ecommerce:productvariant_detail", kwargs={"pk": var.pk}))
    assert resp_detail.status_code == 200
    assert b'<script>alert("xss-var-name")</script>' not in resp_detail.content
    assert b"&lt;script&gt;alert(" in resp_detail.content


def test_productcatalog_xss_productrelationship_escaping(client_a, tenant_a, ecom_product_a):
    """Assert malicious script tags in ProductRelationship notes are HTML-escaped on detail view."""
    target_prod = _productcatalog_product(tenant_a, name="Target XSS Prod", slug="target-xss-prod")
    rel = ProductRelationship.objects.create(
        tenant=tenant_a,
        source_product=ecom_product_a,
        target_product=target_prod,
        relationship_type="cross_sell",
        notes='<script>alert("xss-rel-notes")</script>',
        is_active=True,
    )
    # Detail view displays notes
    resp_detail = client_a.get(reverse("ecommerce:productrelationship_detail", kwargs={"pk": rel.pk}))
    assert resp_detail.status_code == 200
    assert b'<script>alert("xss-rel-notes")</script>' not in resp_detail.content
    assert b"&lt;script&gt;alert(" in resp_detail.content


def test_productcatalog_csv_export_formula_injection_sanitization(client_a, tenant_a):
    """Assert CSV export sanitizes spreadsheet formula triggers (=, +, -, @) with single-quote prefix."""
    cat = StoreCategory.objects.create(tenant=tenant_a, name="Safe Category", slug="safe-cat")
    prod = CatalogProduct.objects.create(
        tenant=tenant_a,
        name="=cmd|' /C calc'!A0",
        slug="formula-product-test",
        brand="+EvilBrand",
        primary_category=cat,
        status="active",
        visibility="storefront",
    )
    ProductVariant.objects.create(
        tenant=tenant_a,
        product=prod,
        sku="-FORMULA-SKU",
        name="@SUM(1,2)",
        price=Decimal("10.00"),
    )

    resp = client_a.get(reverse("ecommerce:product_export_csv"))
    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"

    csv_reader = csv.reader(io.StringIO(resp.content.decode("utf-8")))
    headers = next(csv_reader)
    rows = list(csv_reader)

    # Find the row corresponding to our formula product
    matched_row = None
    for r in rows:
        # Index 1 is Product_Name, Index 3 is Brand, Index 7 is SKU, Index 8 is Variant_Name
        if "=cmd" in r[1] or "'=cmd" in r[1]:
            matched_row = r
            break

    assert matched_row is not None, "Export row with formula product was not found."
    # Assert formulas are neutralized with a leading single quote
    assert matched_row[1].startswith("'="), f"Product name was not sanitized: {matched_row[1]}"
    assert matched_row[3].startswith("'+"), f"Brand was not sanitized: {matched_row[3]}"
    assert matched_row[7].startswith("'-"), f"SKU was not sanitized: {matched_row[7]}"
    assert matched_row[8].startswith("'@"), f"Variant name was not sanitized: {matched_row[8]}"


# ==============================================================================
# 7. Negative & Malicious Input Hardening
# ==============================================================================

def test_productcatalog_negative_sql_injection_and_non_numeric_filters(
    client_a, ecom_product_a, ecom_category_a, ecom_variant_a, ecom_relationship_a
):
    """Assert malicious SQL injection or non-numeric query parameters return 200 without unhandled 500s."""
    malicious_queries = [
        # Product list filters
        (reverse("ecommerce:catalogproduct_list"), {"category": "999' OR 1=1--"}),
        (reverse("ecommerce:catalogproduct_list"), {"category": "notanumber"}),
        (reverse("ecommerce:catalogproduct_list"), {"category": "-1"}),
        (reverse("ecommerce:catalogproduct_list"), {"status": "active' OR '1'='1"}),
        (reverse("ecommerce:catalogproduct_list"), {"visibility": "storefront'; DROP TABLE--"}),
        (reverse("ecommerce:catalogproduct_list"), {"brand": "' OR 1=1--"}),
        (reverse("ecommerce:catalogproduct_list"), {"q": "' UNION SELECT 1,2,3--"}),
        (reverse("ecommerce:catalogproduct_list"), {"page": "999999"}),
        (reverse("ecommerce:catalogproduct_list"), {"page": "-5"}),
        (reverse("ecommerce:catalogproduct_list"), {"page": "invalid_page_num"}),

        # Variant list filters
        (reverse("ecommerce:productvariant_list"), {"product": "foo' UNION SELECT--"}),
        (reverse("ecommerce:productvariant_list"), {"product": "not_an_id"}),
        (reverse("ecommerce:productvariant_list"), {"is_active": "malicious' OR '1'='1"}),
        (reverse("ecommerce:productvariant_list"), {"q": "<script>alert('sku')</script>"}),
        (reverse("ecommerce:productvariant_list"), {"page": "abc"}),

        # Relationship list filters
        (reverse("ecommerce:productrelationship_list"), {"type": "nonexistent'; DROP TABLE--"}),
        (reverse("ecommerce:productrelationship_list"), {"q": "' OR 1=1--"}),
        (reverse("ecommerce:productrelationship_list"), {"page": "-1"}),

        # Category list filters
        (reverse("ecommerce:storecategory_list"), {"status": "invalid' OR '1'='1"}),
        (reverse("ecommerce:storecategory_list"), {"q": "<script>alert(1)</script>"}),
        (reverse("ecommerce:storecategory_list"), {"page": "NaN"}),
    ]

    for url, params in malicious_queries:
        resp = client_a.get(url, params)
        assert resp.status_code == 200, f"Failed on URL {url} with params {params}: HTTP {resp.status_code}"


def test_productcatalog_csv_import_non_csv_extension_rejected(client_a):
    """Assert files with non-.csv extensions (.exe, .php, .py) are rejected by validation."""
    invalid_files = [
        ("malicious.exe", b"MZ\x90\x00\x03\x00\x00\x00", "application/x-dosexec"),
        ("exploit.php", b"<?php phpinfo(); ?>", "text/x-php"),
        ("backdoor.py", b"import os; os.system('calc')", "text/x-python"),
    ]

    for filename, content, mime in invalid_files:
        upload = _productcatalog_create_file(filename, content, mime)
        resp = client_a.post(reverse("ecommerce:product_import_csv"), {"csv_file": upload})
        assert resp.status_code == 200
        content_decoded = resp.content.decode("utf-8")
        assert "Only .csv files are supported." in content_decoded


def test_productcatalog_csv_import_file_size_exceeded_rejected(client_a):
    """Assert CSV files exceeding 5MB are rejected by validation."""
    # 5MB + 1KB
    oversized_bytes = b"Product_Name,SKU\n" + b"A,B\n" * 1500000
    upload = _productcatalog_create_file("oversized.csv", oversized_bytes)
    resp = client_a.post(reverse("ecommerce:product_import_csv"), {"csv_file": upload})
    assert resp.status_code == 200
    content_decoded = resp.content.decode("utf-8")
    assert "CSV file size must not exceed 5MB." in content_decoded


def test_productcatalog_csv_import_invalid_utf8_handled_safely(client_a):
    """Assert CSV files with invalid UTF-8 byte sequences are handled gracefully without 500 error."""
    corrupt_bytes = b"Product_Name,SKU,Price\nValidProduct\xff\xfe\xfa\x80,CORRUPT-SKU-01,25.00\n"
    upload = _productcatalog_create_file("corrupt.csv", corrupt_bytes)
    resp = client_a.post(reverse("ecommerce:product_import_csv"), {"csv_file": upload})
    assert resp.status_code in (200, 302)
    # Ensure no unhandled 500 error occurs
