"""Comprehensive view and integration tests for Module 9.1 Product Catalog Management (`ecommerce`).

Covers:
- Overview: catalog_overview, dashboard alias, KPI aggregates, recent items.
- StoreCategory CRUD: list, search, status filter, pagination, detail, create, edit, delete, permissions, 405s.
- CatalogProduct CRUD + Actions: list, filters (status, visibility, category, brand), non-numeric resilience,
  detail (variants, cross-sells, up-sells, accessories, bundles, bought-together), create, edit, delete, publish toggle.
- ProductVariant CRUD: list, filters (product, is_active), non-numeric resilience, detail, create, edit, delete.
- ProductRelationship CRUD: list, type filter, detail, create, edit, self-relation rejection, delete.
- Bulk Operations: product_import_csv (GET, dry_run preview, actual commit, validation errors),
  product_export_csv (CSV headers, content formatting, empty variant fallback, tenant isolation).

Conventions enforced:
- Every test function: test_productcatalog_<name>
- Every module-level helper: _productcatalog_<name>
- Lesson L8: Assert content in 200 responses, never status code alone.
"""
import csv
from decimal import Decimal
import io
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog
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
from apps.scm.models import Item

pytestmark = pytest.mark.django_db


# ==============================================================================
# Module Helpers (_productcatalog_*)
# ==============================================================================

def _productcatalog_category_payload(**overrides):
    """Returns valid POST dictionary for StoreCategory creation/update."""
    defaults = {
        "name": "Audio & Sound",
        "slug": "audio-sound",
        "parent": "",
        "description": "Premium wireless headphones, earbuds, and home audio gear.",
        "image_url": "https://example.com/audio-banner.jpg",
        "display_order": 1,
        "is_active": True,
        "include_in_menu": True,
        "meta_title": "Buy Audio Gear Online",
        "meta_description": "Best prices on wireless audio gear and accessories.",
    }
    defaults.update(overrides)
    return defaults


def _productcatalog_product_payload(**overrides):
    """Returns valid POST dictionary for CatalogProduct creation/update."""
    defaults = {
        "name": "Wireless Noise-Cancelling Headphones",
        "slug": "wireless-nc-headphones",
        "item": "",
        "primary_category": "",
        "categories": [],
        "status": "active",
        "visibility": "storefront",
        "brand": "AcousticPro",
        "short_description": "Industry-leading noise cancellation with 40-hour battery life.",
        "description": "Full technical specifications and features for AcousticPro headphones.",
        "hero_image_url": "https://example.com/headphones-hero.jpg",
        "video_url": "https://youtube.com/watch?v=acousticpro",
        "is_featured": True,
        "is_digital": False,
        "meta_title": "AcousticPro Wireless Headphones",
        "meta_description": "Shop the latest AcousticPro ANC headphones.",
    }
    defaults.update(overrides)
    return defaults


def _productcatalog_variant_payload(product, **overrides):
    """Returns valid POST dictionary for ProductVariant creation/update."""
    prod_pk = product.pk if hasattr(product, "pk") else product
    defaults = {
        "product": prod_pk,
        "sku": "ANC-PRO-BLK",
        "name": "Midnight Black / Standard",
        "barcode": "8901234567890",
        "price": "299.9900",
        "compare_at_price": "349.9900",
        "cost_price": "150.0000",
        "item": "",
        "weight_kg": "0.280",
        "image_url": "https://example.com/headphones-black.jpg",
        "is_active": True,
        "sort_order": 1,
        "option_values_raw": '{"Color": "Midnight Black", "Edition": "Standard"}',
    }
    defaults.update(overrides)
    return defaults


def _productcatalog_relationship_payload(source_product, target_product, **overrides):
    """Returns valid POST dictionary for ProductRelationship creation/update."""
    src_pk = source_product.pk if hasattr(source_product, "pk") else source_product
    tgt_pk = target_product.pk if hasattr(target_product, "pk") else target_product
    defaults = {
        "source_product": src_pk,
        "target_product": tgt_pk,
        "relationship_type": "accessory",
        "discount_pct": "15.00",
        "is_active": True,
        "sort_order": 1,
        "notes": "Hardshell travel case bundle recommendation.",
    }
    defaults.update(overrides)
    return defaults


def _productcatalog_sample_csv(content=None, filename="catalog.csv"):
    """Creates a SimpleUploadedFile representing a CSV upload."""
    if content is None:
        content = (
            "Product_Name,Slug,Brand,Category,Status,Visibility,SKU,Variant_Name,Price,Compare_At_Price,Cost_Price,Barcode\n"
            "Mechanical Keyboard,mech-keyboard,KeyCraft,Peripherals,active,storefront,KB-RGB-01,RGB Linear,129.99,149.99,70.00,123456789012\n"
        )
    return SimpleUploadedFile(filename, content.encode("utf-8"), content_type="text/csv")


# ==============================================================================
# Overview Tests
# ==============================================================================

def test_productcatalog_overview_view_kpis(client_a, tenant_a, ecom_category_a, ecom_product_a, ecom_variant_a):
    """Test catalog_overview renders KPI aggregates, categories, and products."""
    # Create draft product and zero variant product
    p_draft = _productcatalog_product(
        tenant_a,
        name="Draft Tablet",
        slug="draft-tablet",
        status="draft",
        primary_category=ecom_category_a,
    )
    p_draft.pim_completeness = 40
    p_draft.save()

    ecom_product_a.pim_completeness = 80
    ecom_product_a.save()

    p_target = _productcatalog_product(tenant_a, name="Target Soundbar", slug="target-soundbar")
    rel = _productcatalog_relationship(tenant_a, ecom_product_a, p_target, relationship_type="cross_sell")

    url = reverse("ecommerce:catalog_overview")
    resp = client_a.get(url)
    assert resp.status_code == 200

    # Assert context variables
    assert resp.context["total_products"] == 3
    assert resp.context["active_products"] == 2
    assert resp.context["draft_products"] == 1
    assert resp.context["total_categories"] == 1
    assert resp.context["total_variants"] == 1
    assert resp.context["total_relationships"] == 1
    assert resp.context["zero_variant_products"] == 2  # p_draft and p_target have no variants
    assert resp.context["avg_pim_completeness"] == 80.0

    # Assert content
    html = resp.content.decode("utf-8")
    assert "Product Catalog &amp; PIM Overview" in html or "Product Catalog & PIM Overview" in html
    assert "Total Products" in html
    assert ecom_product_a.name in html
    assert ecom_category_a.name in html


def test_productcatalog_overview_view_recent_items(client_a, tenant_a, ecom_category_a, ecom_product_a):
    """Test recent_products and recent_categories lists are populated in overview context."""
    url = reverse("ecommerce:catalog_overview")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert ecom_product_a in resp.context["recent_products"]
    assert ecom_category_a in resp.context["recent_categories"]


def test_productcatalog_overview_dashboard_alias(client_a, tenant_a, ecom_product_a):
    """Test the 'ecommerce:dashboard' route aliases to catalog_overview."""
    url = reverse("ecommerce:dashboard")
    resp = client_a.get(url)
    assert resp.status_code == 200
    html = resp.content.decode("utf-8")
    assert "Product Catalog &amp; PIM Overview" in html or "Product Catalog & PIM Overview" in html
    assert ecom_product_a.name in html


def test_productcatalog_overview_tenant_isolation(client_a, tenant_a, client_b, tenant_b, ecom_product_a, ecom_product_b):
    """Test overview only shows products and counts for the authenticated tenant."""
    url = reverse("ecommerce:catalog_overview")

    resp_a = client_a.get(url)
    assert resp_a.status_code == 200
    assert resp_a.context["total_products"] == 1
    html_a = resp_a.content.decode("utf-8")
    assert ecom_product_a.name in html_a
    assert ecom_product_b.name not in html_a

    resp_b = client_b.get(url)
    assert resp_b.status_code == 200
    assert resp_b.context["total_products"] == 1
    html_b = resp_b.content.decode("utf-8")
    assert ecom_product_b.name in html_b
    assert ecom_product_a.name not in html_b


def test_productcatalog_overview_unauthenticated_redirect(client):
    """Test unauthenticated user is redirected to login from catalog overview."""
    url = reverse("ecommerce:catalog_overview")
    resp = client.get(url)
    assert resp.status_code == 302
    assert "/accounts/login/" in resp.url or "login" in resp.url


# ==============================================================================
# StoreCategory CRUD Tests
# ==============================================================================

def test_productcatalog_storecategory_list_renders_200(client_a, tenant_a, ecom_category_a):
    """Test storecategory_list renders 200, contains category and filters."""
    url = reverse("ecommerce:storecategory_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "categories" in resp.context
    assert ecom_category_a in resp.context["categories"]
    html = resp.content.decode("utf-8")
    assert "Store Categories" in html
    assert ecom_category_a.name in html
    assert ecom_category_a.slug in html


def test_productcatalog_storecategory_list_search(client_a, tenant_a):
    """Test storecategory_list search filter matches name, slug, description, or number."""
    cat1 = _productcatalog_category(tenant_a, name="Monitors Display", slug="monitors-display", description="OLED Panels")
    cat2 = _productcatalog_category(tenant_a, name="Keyboards", slug="keyboards", description="Mechanical switches")

    url = reverse("ecommerce:storecategory_list")
    resp = client_a.get(url, {"q": "Monitors"})
    assert resp.status_code == 200
    assert cat1 in resp.context["categories"]
    assert cat2 not in resp.context["categories"]
    html = resp.content.decode("utf-8")
    assert "Monitors Display" in html
    assert "Keyboards" not in html

    # Search by description
    resp_desc = client_a.get(url, {"q": "switches"})
    assert resp_desc.status_code == 200
    assert cat2 in resp_desc.context["categories"]
    assert cat1 not in resp_desc.context["categories"]


def test_productcatalog_storecategory_list_filter_status(client_a, tenant_a):
    """Test storecategory_list filters by active and inactive status."""
    cat_act = _productcatalog_category(tenant_a, name="Active Category", slug="active-cat", is_active=True)
    cat_inact = _productcatalog_category(tenant_a, name="Inactive Category", slug="inactive-cat", is_active=False)

    url = reverse("ecommerce:storecategory_list")
    # Filter active
    resp_act = client_a.get(url, {"status": "active"})
    assert resp_act.status_code == 200
    assert cat_act in resp_act.context["categories"]
    assert cat_inact not in resp_act.context["categories"]

    # Filter inactive
    resp_inact = client_a.get(url, {"status": "inactive"})
    assert resp_inact.status_code == 200
    assert cat_inact in resp_inact.context["categories"]
    assert cat_act not in resp_inact.context["categories"]


def test_productcatalog_storecategory_list_pagination(client_a, tenant_a):
    """Test storecategory_list pagination with >25 records."""
    categories = [
        _productcatalog_category(tenant_a, name=f"Category {i:02d}", slug=f"cat-{i:02d}")
        for i in range(28)
    ]
    url = reverse("ecommerce:storecategory_list")
    resp_p1 = client_a.get(url)
    assert resp_p1.status_code == 200
    assert resp_p1.context["is_paginated"] is True
    assert len(resp_p1.context["categories"]) == 25

    resp_p2 = client_a.get(url, {"page": 2})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["categories"]) == 3


def test_productcatalog_storecategory_list_tenant_isolation(client_a, ecom_category_a, client_b, ecom_category_b):
    """Test storecategory_list does not show categories from another tenant."""
    url = reverse("ecommerce:storecategory_list")
    resp_a = client_a.get(url)
    assert resp_a.status_code == 200
    assert ecom_category_a in resp_a.context["categories"]
    assert ecom_category_b not in resp_a.context["categories"]


def test_productcatalog_storecategory_detail_view(client_a, tenant_a):
    """Test storecategory_detail renders 200 with category, child categories, and associated products."""
    parent = _productcatalog_category(tenant_a, name="Parent Tech", slug="parent-tech")
    child = _productcatalog_category(tenant_a, name="Child Laptops", slug="child-laptops", parent=parent)
    prod = _productcatalog_product(tenant_a, name="Gaming Laptop", slug="gaming-laptop", primary_category=parent)

    url = reverse("ecommerce:storecategory_detail", kwargs={"pk": parent.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["category"] == parent
    assert child in resp.context["children"]
    assert prod in resp.context["products"]

    html = resp.content.decode("utf-8")
    assert "Parent Tech" in html
    assert "Child Laptops" in html
    assert "Gaming Laptop" in html


def test_productcatalog_storecategory_detail_cross_tenant_404(client_b, ecom_category_a):
    """Test storecategory_detail returns 404 when tenant B accesses tenant A's category."""
    url = reverse("ecommerce:storecategory_detail", kwargs={"pk": ecom_category_a.pk})
    resp = client_b.get(url)
    assert resp.status_code == 404


def test_productcatalog_storecategory_create_get(client_a, tenant_a, ecom_category_a):
    """Test storecategory_create GET displays empty form and available parent categories."""
    url = reverse("ecommerce:storecategory_create")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["is_edit"] is False
    assert resp.context["category"] is None
    assert ecom_category_a in resp.context["parent_categories"]
    html = resp.content.decode("utf-8")
    assert "New Store Category" in html or "Create Category" in html or "New Category" in html


def test_productcatalog_storecategory_create_post_success(client_a, tenant_a):
    """Test storecategory_create POST saves category, creates audit log, and redirects to detail."""
    url = reverse("ecommerce:storecategory_create")
    payload = _productcatalog_category_payload(name="Smart Home Gadgets", slug="smart-home")
    resp = client_a.post(url, data=payload)

    new_cat = StoreCategory.objects.filter(tenant=tenant_a, slug="smart-home").first()
    assert new_cat is not None
    assert new_cat.name == "Smart Home Gadgets"
    assert resp.status_code == 302
    assert resp.url == reverse("ecommerce:storecategory_detail", kwargs={"pk": new_cat.pk})

    # Assert audit log
    log = AuditLog.objects.filter(tenant=tenant_a, action="create", object_id=str(new_cat.pk)).first()
    assert log is not None


def test_productcatalog_storecategory_create_post_invalid(client_a, tenant_a):
    """Test storecategory_create POST with invalid data re-renders form with errors."""
    url = reverse("ecommerce:storecategory_create")
    payload = _productcatalog_category_payload(name="")  # Name is required
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert resp.context["form"].errors
    assert "name" in resp.context["form"].errors


def test_productcatalog_storecategory_edit_get(client_a, ecom_category_a):
    """Test storecategory_edit GET displays form pre-populated with instance data."""
    url = reverse("ecommerce:storecategory_edit", kwargs={"pk": ecom_category_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["is_edit"] is True
    assert resp.context["category"] == ecom_category_a
    html = resp.content.decode("utf-8")
    assert ecom_category_a.name in html


def test_productcatalog_storecategory_edit_post_success(client_a, tenant_a, ecom_category_a):
    """Test storecategory_edit POST updates category, writes audit log, and redirects to detail."""
    url = reverse("ecommerce:storecategory_edit", kwargs={"pk": ecom_category_a.pk})
    payload = _productcatalog_category_payload(
        name="Hardware Updated",
        slug=ecom_category_a.slug,
        description="Updated category description.",
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse("ecommerce:storecategory_detail", kwargs={"pk": ecom_category_a.pk})

    ecom_category_a.refresh_from_db()
    assert ecom_category_a.name == "Hardware Updated"
    assert ecom_category_a.description == "Updated category description."

    # Assert audit log
    log = AuditLog.objects.filter(tenant=tenant_a, action="update", object_id=str(ecom_category_a.pk)).first()
    assert log is not None


def test_productcatalog_storecategory_edit_post_invalid(client_a, tenant_a, ecom_category_a):
    """Test storecategory_edit POST with missing required name re-renders form with errors."""
    url = reverse("ecommerce:storecategory_edit", kwargs={"pk": ecom_category_a.pk})
    payload = _productcatalog_category_payload(name="", slug=ecom_category_a.slug)
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "name" in resp.context["form"].errors


def test_productcatalog_storecategory_edit_cross_tenant_404(client_b, ecom_category_a):
    """Test storecategory_edit returns 404 when tenant B attempts to edit tenant A category."""
    url = reverse("ecommerce:storecategory_edit", kwargs={"pk": ecom_category_a.pk})
    resp = client_b.get(url)
    assert resp.status_code == 404


def test_productcatalog_storecategory_delete_post_success(client_a, tenant_a):
    """Test storecategory_delete POST deletes category, records audit log, and redirects to list."""
    cat = _productcatalog_category(tenant_a, name="Temporary Cat", slug="temp-cat")
    cat_pk = cat.pk
    url = reverse("ecommerce:storecategory_delete", kwargs={"pk": cat_pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("ecommerce:storecategory_list")
    assert not StoreCategory.objects.filter(pk=cat_pk).exists()

    # Assert audit log
    log = AuditLog.objects.filter(tenant=tenant_a, action="delete", object_id=str(cat_pk)).first()
    assert log is not None


def test_productcatalog_storecategory_delete_get_method_not_allowed(client_a, ecom_category_a):
    """Test storecategory_delete GET returns 405 Method Not Allowed."""
    url = reverse("ecommerce:storecategory_delete", kwargs={"pk": ecom_category_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


def test_productcatalog_storecategory_delete_non_admin_forbidden(member_client, ecom_category_a):
    """Test storecategory_delete raises 403 PermissionDenied for non-admin user."""
    url = reverse("ecommerce:storecategory_delete", kwargs={"pk": ecom_category_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403


def test_productcatalog_storecategory_delete_cross_tenant_404(client_b, ecom_category_a):
    """Test storecategory_delete returns 404 when tenant B attempts to delete tenant A category."""
    url = reverse("ecommerce:storecategory_delete", kwargs={"pk": ecom_category_a.pk})
    resp = client_b.post(url)
    assert resp.status_code == 404


# ==============================================================================
# CatalogProduct CRUD + Actions Tests
# ==============================================================================

def test_productcatalog_catalogproduct_list_renders_200(client_a, tenant_a, ecom_product_a):
    """Test catalogproduct_list renders 200 with product listings and filter choices."""
    url = reverse("ecommerce:catalogproduct_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "products" in resp.context
    assert ecom_product_a in resp.context["products"]
    assert "status_choices" in resp.context
    assert "visibility_choices" in resp.context
    assert "categories_list" in resp.context
    assert "brands_list" in resp.context

    html = resp.content.decode("utf-8")
    assert "Catalog Products" in html
    assert ecom_product_a.name in html
    assert ecom_product_a.brand in html


def test_productcatalog_catalogproduct_list_search(client_a, tenant_a):
    """Test catalogproduct_list search matches name, brand, number, or variant SKU."""
    p1 = _productcatalog_product(tenant_a, name="Gaming Console X", slug="console-x", brand="PlayStudio")
    p2 = _productcatalog_product(tenant_a, name="Office Chair Ergonomic", slug="office-chair", brand="ErgoMax")
    _productcatalog_variant(tenant_a, p1, sku="CONSOLE-SKU-99")

    url = reverse("ecommerce:catalogproduct_list")

    # Match name
    resp_name = client_a.get(url, {"q": "Gaming"})
    assert resp_name.status_code == 200
    assert p1 in resp_name.context["products"]
    assert p2 not in resp_name.context["products"]

    # Match brand
    resp_brand = client_a.get(url, {"q": "ErgoMax"})
    assert resp_brand.status_code == 200
    assert p2 in resp_brand.context["products"]
    assert p1 not in resp_brand.context["products"]

    # Match variant SKU
    resp_sku = client_a.get(url, {"q": "CONSOLE-SKU"})
    assert resp_sku.status_code == 200
    assert p1 in resp_sku.context["products"]
    assert p2 not in resp_sku.context["products"]


def test_productcatalog_catalogproduct_list_filter_status(client_a, tenant_a):
    """Test catalogproduct_list filters by status."""
    p_act = _productcatalog_product(tenant_a, name="Live Product", slug="live-prod", status="active")
    p_dft = _productcatalog_product(tenant_a, name="Draft Product", slug="draft-prod", status="draft")

    url = reverse("ecommerce:catalogproduct_list")
    resp_act = client_a.get(url, {"status": "active"})
    assert resp_act.status_code == 200
    assert p_act in resp_act.context["products"]
    assert p_dft not in resp_act.context["products"]

    resp_dft = client_a.get(url, {"status": "draft"})
    assert resp_dft.status_code == 200
    assert p_dft in resp_dft.context["products"]
    assert p_act not in resp_dft.context["products"]


def test_productcatalog_catalogproduct_list_filter_visibility(client_a, tenant_a):
    """Test catalogproduct_list filters by visibility."""
    p_front = _productcatalog_product(tenant_a, name="Storefront Prod", slug="storefront-prod", visibility="storefront")
    p_hid = _productcatalog_product(tenant_a, name="Hidden Prod", slug="hidden-prod", visibility="hidden")

    url = reverse("ecommerce:catalogproduct_list")
    resp_front = client_a.get(url, {"visibility": "storefront"})
    assert resp_front.status_code == 200
    assert p_front in resp_front.context["products"]
    assert p_hid not in resp_front.context["products"]

    resp_hid = client_a.get(url, {"visibility": "hidden"})
    assert resp_hid.status_code == 200
    assert p_hid in resp_hid.context["products"]
    assert p_front not in resp_hid.context["products"]


def test_productcatalog_catalogproduct_list_filter_category(client_a, tenant_a):
    """Test catalogproduct_list filters products by primary or secondary category."""
    cat1 = _productcatalog_category(tenant_a, name="Laptops", slug="laptops")
    cat2 = _productcatalog_category(tenant_a, name="Desktops", slug="desktops")

    p1 = _productcatalog_product(tenant_a, name="Ultrabook 14", slug="ultra-14", primary_category=cat1)
    p2 = _productcatalog_product(tenant_a, name="Tower Workstation", slug="tower-workstation", primary_category=cat2)
    p3 = _productcatalog_product(tenant_a, name="Hybrid PC", slug="hybrid-pc", primary_category=cat2)
    p3.categories.add(cat1)

    url = reverse("ecommerce:catalogproduct_list")
    resp = client_a.get(url, {"category": str(cat1.pk)})
    assert resp.status_code == 200
    assert p1 in resp.context["products"]
    assert p3 in resp.context["products"]
    assert p2 not in resp.context["products"]


def test_productcatalog_catalogproduct_list_filter_category_non_numeric_resilience(client_a, tenant_a, ecom_product_a):
    """Test catalogproduct_list handles non-numeric category param gracefully without 500 error."""
    url = reverse("ecommerce:catalogproduct_list")
    resp = client_a.get(url, {"category": "invalid_abc"})
    assert resp.status_code == 200
    assert ecom_product_a in resp.context["products"]


def test_productcatalog_catalogproduct_list_filter_brand(client_a, tenant_a):
    """Test catalogproduct_list filters products by brand."""
    p1 = _productcatalog_product(tenant_a, name="Alpha Phone", slug="alpha-phone", brand="AlphaCorp")
    p2 = _productcatalog_product(tenant_a, name="Beta Phone", slug="beta-phone", brand="BetaCorp")

    url = reverse("ecommerce:catalogproduct_list")
    resp = client_a.get(url, {"brand": "AlphaCorp"})
    assert resp.status_code == 200
    assert p1 in resp.context["products"]
    assert p2 not in resp.context["products"]


def test_productcatalog_catalogproduct_list_pagination(client_a, tenant_a):
    """Test catalogproduct_list pagination with >20 records."""
    products = [
        _productcatalog_product(tenant_a, name=f"Product {i:02d}", slug=f"prod-{i:02d}")
        for i in range(24)
    ]
    url = reverse("ecommerce:catalogproduct_list")
    resp_p1 = client_a.get(url)
    assert resp_p1.status_code == 200
    assert resp_p1.context["is_paginated"] is True
    assert len(resp_p1.context["products"]) == 20

    resp_p2 = client_a.get(url, {"page": 2})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["products"]) == 4


def test_productcatalog_catalogproduct_list_tenant_isolation(client_a, ecom_product_a, client_b, ecom_product_b):
    """Test catalogproduct_list isolates products across tenants."""
    url = reverse("ecommerce:catalogproduct_list")
    resp_a = client_a.get(url)
    assert resp_a.status_code == 200
    assert ecom_product_a in resp_a.context["products"]
    assert ecom_product_b not in resp_a.context["products"]


def test_productcatalog_catalogproduct_detail_view(client_a, tenant_a, ecom_category_a):
    """Test catalogproduct_detail renders product, variants, and relationship categories."""
    prod = _productcatalog_product(tenant_a, name="Master Phone", slug="master-phone", primary_category=ecom_category_a)
    var1 = _productcatalog_variant(tenant_a, prod, sku="MP-64GB", name="64GB Slate")
    var2 = _productcatalog_variant(tenant_a, prod, sku="MP-128GB", name="128GB Slate")

    target1 = _productcatalog_product(tenant_a, name="Fast Charger", slug="fast-charger")
    target2 = _productcatalog_product(tenant_a, name="Master Phone Pro", slug="master-phone-pro")
    target3 = _productcatalog_product(tenant_a, name="Silicone Case", slug="silicone-case")
    target4 = _productcatalog_product(tenant_a, name="Screen Protector", slug="screen-protector")
    target5 = _productcatalog_product(tenant_a, name="Wireless Earbuds", slug="wireless-earbuds")

    rel_cross = _productcatalog_relationship(tenant_a, prod, target1, relationship_type="cross_sell")
    rel_up = _productcatalog_relationship(tenant_a, prod, target2, relationship_type="up_sell")
    rel_acc = _productcatalog_relationship(tenant_a, prod, target3, relationship_type="accessory")
    rel_kit = _productcatalog_relationship(tenant_a, prod, target4, relationship_type="bundle_kit")
    rel_fbt = _productcatalog_relationship(tenant_a, prod, target5, relationship_type="bought_together")

    url = reverse("ecommerce:catalogproduct_detail", kwargs={"pk": prod.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["product"] == prod
    assert var1 in resp.context["variants"]
    assert var2 in resp.context["variants"]
    assert rel_cross in resp.context["cross_sells"]
    assert rel_up in resp.context["up_sells"]
    assert rel_acc in resp.context["accessories"]
    assert rel_kit in resp.context["bundles"]
    assert rel_fbt in resp.context["bought_together"]

    html = resp.content.decode("utf-8")
    assert "Master Phone" in html
    assert "MP-64GB" in html
    assert "Silicone Case" in html


def test_productcatalog_catalogproduct_detail_cross_tenant_404(client_b, ecom_product_a):
    """Test catalogproduct_detail returns 404 for cross-tenant access."""
    url = reverse("ecommerce:catalogproduct_detail", kwargs={"pk": ecom_product_a.pk})
    resp = client_b.get(url)
    assert resp.status_code == 404


def test_productcatalog_catalogproduct_create_get(client_a, tenant_a, ecom_category_a):
    """Test catalogproduct_create GET renders form, categories, and inventory items."""
    item = Item.objects.create(tenant=tenant_a, sku="SCM-TEST-01", name="SCM Item Test")
    url = reverse("ecommerce:catalogproduct_create")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["is_edit"] is False
    assert resp.context["product"] is None
    assert ecom_category_a in resp.context["primary_categories"]
    assert item in resp.context["items_list"]

    html = resp.content.decode("utf-8")
    assert "New Catalog Product" in html or "Create Product" in html or "New Product" in html


def test_productcatalog_catalogproduct_create_post_success(client_a, tenant_a, ecom_category_a):
    """Test catalogproduct_create POST creates product with m2m categories, writes audit log, redirects."""
    cat2 = _productcatalog_category(tenant_a, name="Audio Accessories", slug="audio-acc")
    url = reverse("ecommerce:catalogproduct_create")
    payload = _productcatalog_product_payload(
        name="Noise Cancelling Earbuds",
        slug="nc-earbuds",
        primary_category=ecom_category_a.pk,
        categories=[cat2.pk],
    )
    resp = client_a.post(url, data=payload)

    new_prod = CatalogProduct.objects.filter(tenant=tenant_a, slug="nc-earbuds").first()
    assert new_prod is not None
    assert new_prod.name == "Noise Cancelling Earbuds"
    assert new_prod.primary_category == ecom_category_a
    assert cat2 in new_prod.categories.all()

    assert resp.status_code == 302
    assert resp.url == reverse("ecommerce:catalogproduct_detail", kwargs={"pk": new_prod.pk})

    # Assert audit log
    log = AuditLog.objects.filter(tenant=tenant_a, action="create", object_id=str(new_prod.pk)).first()
    assert log is not None


def test_productcatalog_catalogproduct_create_post_invalid(client_a, tenant_a):
    """Test catalogproduct_create POST with missing required name returns form errors."""
    url = reverse("ecommerce:catalogproduct_create")
    payload = _productcatalog_product_payload(name="")
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "name" in resp.context["form"].errors


def test_productcatalog_catalogproduct_edit_get(client_a, ecom_product_a):
    """Test catalogproduct_edit GET renders edit form populated with product."""
    url = reverse("ecommerce:catalogproduct_edit", kwargs={"pk": ecom_product_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["is_edit"] is True
    assert resp.context["product"] == ecom_product_a
    html = resp.content.decode("utf-8")
    assert ecom_product_a.name in html


def test_productcatalog_catalogproduct_edit_post_success(client_a, tenant_a, ecom_product_a):
    """Test catalogproduct_edit POST updates product fields, records audit log, redirects."""
    url = reverse("ecommerce:catalogproduct_edit", kwargs={"pk": ecom_product_a.pk})
    payload = _productcatalog_product_payload(
        name="Server A Updated Name",
        slug=ecom_product_a.slug,
        brand="SuperServerBrand",
        description="Updated high memory enterprise server.",
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse("ecommerce:catalogproduct_detail", kwargs={"pk": ecom_product_a.pk})

    ecom_product_a.refresh_from_db()
    assert ecom_product_a.name == "Server A Updated Name"
    assert ecom_product_a.brand == "SuperServerBrand"

    # Assert audit log
    log = AuditLog.objects.filter(tenant=tenant_a, action="update", object_id=str(ecom_product_a.pk)).first()
    assert log is not None


def test_productcatalog_catalogproduct_edit_post_invalid(client_a, tenant_a, ecom_product_a):
    """Test catalogproduct_edit POST with missing required name re-renders form with errors."""
    url = reverse("ecommerce:catalogproduct_edit", kwargs={"pk": ecom_product_a.pk})
    payload = _productcatalog_product_payload(name="", slug=ecom_product_a.slug)
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "name" in resp.context["form"].errors


def test_productcatalog_catalogproduct_edit_cross_tenant_404(client_b, ecom_product_a):
    """Test catalogproduct_edit returns 404 for tenant B."""
    url = reverse("ecommerce:catalogproduct_edit", kwargs={"pk": ecom_product_a.pk})
    resp = client_b.get(url)
    assert resp.status_code == 404


def test_productcatalog_catalogproduct_delete_post_success(client_a, tenant_a):
    """Test catalogproduct_delete POST removes product, creates audit log, redirects to list."""
    prod = _productcatalog_product(tenant_a, name="Temporary Product", slug="temp-prod")
    prod_pk = prod.pk
    url = reverse("ecommerce:catalogproduct_delete", kwargs={"pk": prod_pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("ecommerce:catalogproduct_list")
    assert not CatalogProduct.objects.filter(pk=prod_pk).exists()

    # Assert audit log
    log = AuditLog.objects.filter(tenant=tenant_a, action="delete", object_id=str(prod_pk)).first()
    assert log is not None


def test_productcatalog_catalogproduct_delete_get_method_not_allowed(client_a, ecom_product_a):
    """Test catalogproduct_delete GET returns 405 Method Not Allowed."""
    url = reverse("ecommerce:catalogproduct_delete", kwargs={"pk": ecom_product_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


def test_productcatalog_catalogproduct_delete_non_admin_forbidden(member_client, ecom_product_a):
    """Test catalogproduct_delete returns 403 Forbidden for non-admin members."""
    url = reverse("ecommerce:catalogproduct_delete", kwargs={"pk": ecom_product_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403


def test_productcatalog_catalogproduct_delete_cross_tenant_404(client_b, ecom_product_a):
    """Test catalogproduct_delete returns 404 for cross-tenant request."""
    url = reverse("ecommerce:catalogproduct_delete", kwargs={"pk": ecom_product_a.pk})
    resp = client_b.post(url)
    assert resp.status_code == 404


def test_productcatalog_catalogproduct_publish_draft_to_active(client_a, tenant_a):
    """Test catalogproduct_publish POST transitions draft to active and sets published_at."""
    prod = _productcatalog_product(tenant_a, name="Unpublished Gadget", slug="unpub-gadget", status="draft")
    assert prod.published_at is None

    url = reverse("ecommerce:catalogproduct_publish", kwargs={"pk": prod.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("ecommerce:catalogproduct_detail", kwargs={"pk": prod.pk})

    prod.refresh_from_db()
    assert prod.status == "active"
    assert prod.published_at is not None

    # Assert audit log
    log = AuditLog.objects.filter(tenant=tenant_a, action="update", object_id=str(prod.pk)).first()
    assert log is not None


def test_productcatalog_catalogproduct_publish_active_to_draft(client_a, tenant_a, ecom_product_a):
    """Test catalogproduct_publish POST transitions active product back to draft."""
    assert ecom_product_a.status == "active"
    url = reverse("ecommerce:catalogproduct_publish", kwargs={"pk": ecom_product_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("ecommerce:catalogproduct_detail", kwargs={"pk": ecom_product_a.pk})

    ecom_product_a.refresh_from_db()
    assert ecom_product_a.status == "draft"


def test_productcatalog_catalogproduct_publish_get_method_not_allowed(client_a, ecom_product_a):
    """Test catalogproduct_publish GET returns 405 Method Not Allowed."""
    url = reverse("ecommerce:catalogproduct_publish", kwargs={"pk": ecom_product_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


def test_productcatalog_catalogproduct_publish_cross_tenant_404(client_b, ecom_product_a):
    """Test catalogproduct_publish returns 404 for cross-tenant access."""
    url = reverse("ecommerce:catalogproduct_publish", kwargs={"pk": ecom_product_a.pk})
    resp = client_b.post(url)
    assert resp.status_code == 404


# ==============================================================================
# ProductVariant CRUD Tests
# ==============================================================================

def test_productcatalog_productvariant_list_renders_200(client_a, tenant_a, ecom_variant_a):
    """Test productvariant_list renders 200 with variants and filter dropdowns."""
    url = reverse("ecommerce:productvariant_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "variants" in resp.context
    assert ecom_variant_a in resp.context["variants"]
    assert "products_list" in resp.context

    html = resp.content.decode("utf-8")
    assert "Product Variants" in html
    assert ecom_variant_a.sku in html
    assert ecom_variant_a.name in html


def test_productcatalog_productvariant_list_filter_product(client_a, tenant_a, ecom_product_a):
    """Test productvariant_list filters variants by parent product."""
    p2 = _productcatalog_product(tenant_a, name="Desk Lamp", slug="desk-lamp")
    v1 = _productcatalog_variant(tenant_a, ecom_product_a, sku="VAR-PROD-A")
    v2 = _productcatalog_variant(tenant_a, p2, sku="VAR-PROD-B")

    url = reverse("ecommerce:productvariant_list")
    resp = client_a.get(url, {"product": str(ecom_product_a.pk)})
    assert resp.status_code == 200
    assert v1 in resp.context["variants"]
    assert v2 not in resp.context["variants"]


def test_productcatalog_productvariant_list_filter_product_non_numeric_resilience(client_a, tenant_a, ecom_variant_a):
    """Test productvariant_list handles non-numeric product filter without crashing."""
    url = reverse("ecommerce:productvariant_list")
    resp = client_a.get(url, {"product": "not_an_int"})
    assert resp.status_code == 200
    assert ecom_variant_a in resp.context["variants"]


def test_productcatalog_productvariant_list_filter_is_active(client_a, tenant_a, ecom_product_a):
    """Test productvariant_list filters by is_active boolean."""
    v_act = _productcatalog_variant(tenant_a, ecom_product_a, sku="V-ACT", is_active=True)
    v_inact = _productcatalog_variant(tenant_a, ecom_product_a, sku="V-INACT", is_active=False)

    url = reverse("ecommerce:productvariant_list")
    resp_act = client_a.get(url, {"is_active": "true"})
    assert resp_act.status_code == 200
    assert v_act in resp_act.context["variants"]
    assert v_inact not in resp_act.context["variants"]

    resp_inact = client_a.get(url, {"is_active": "false"})
    assert resp_inact.status_code == 200
    assert v_inact in resp_inact.context["variants"]
    assert v_act not in resp_inact.context["variants"]


def test_productcatalog_productvariant_list_search(client_a, tenant_a, ecom_product_a):
    """Test productvariant_list search by SKU, name, or barcode."""
    v1 = _productcatalog_variant(tenant_a, ecom_product_a, sku="SEARCH-SKU-99", barcode="1122334455")
    v2 = _productcatalog_variant(tenant_a, ecom_product_a, sku="OTHER-SKU-00", barcode="9988776655")

    url = reverse("ecommerce:productvariant_list")
    resp = client_a.get(url, {"q": "SEARCH-SKU"})
    assert resp.status_code == 200
    assert v1 in resp.context["variants"]
    assert v2 not in resp.context["variants"]

    resp_bar = client_a.get(url, {"q": "9988776655"})
    assert resp_bar.status_code == 200
    assert v2 in resp_bar.context["variants"]
    assert v1 not in resp_bar.context["variants"]


def test_productcatalog_productvariant_list_pagination(client_a, tenant_a, ecom_product_a):
    """Test productvariant_list pagination with >25 variants."""
    variants = [
        _productcatalog_variant(tenant_a, ecom_product_a, sku=f"PAG-SKU-{i:02d}")
        for i in range(28)
    ]
    url = reverse("ecommerce:productvariant_list")
    resp_p1 = client_a.get(url)
    assert resp_p1.status_code == 200
    assert resp_p1.context["is_paginated"] is True
    assert len(resp_p1.context["variants"]) == 25

    resp_p2 = client_a.get(url, {"page": 2})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["variants"]) == 3


def test_productcatalog_productvariant_list_tenant_isolation(client_a, ecom_variant_a, client_b, ecom_variant_b):
    """Test productvariant_list isolates variants across tenants."""
    url = reverse("ecommerce:productvariant_list")
    resp_a = client_a.get(url)
    assert resp_a.status_code == 200
    assert ecom_variant_a in resp_a.context["variants"]
    assert ecom_variant_b not in resp_a.context["variants"]


def test_productcatalog_productvariant_detail_view(client_a, tenant_a, ecom_variant_a):
    """Test productvariant_detail renders variant data, parent product, and item link."""
    url = reverse("ecommerce:productvariant_detail", kwargs={"pk": ecom_variant_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["variant"] == ecom_variant_a
    assert resp.context["product"] == ecom_variant_a.product
    assert resp.context["item"] == ecom_variant_a.item

    html = resp.content.decode("utf-8")
    assert ecom_variant_a.sku in html
    assert ecom_variant_a.name in html


def test_productcatalog_productvariant_detail_cross_tenant_404(client_b, ecom_variant_a):
    """Test productvariant_detail returns 404 for tenant B."""
    url = reverse("ecommerce:productvariant_detail", kwargs={"pk": ecom_variant_a.pk})
    resp = client_b.get(url)
    assert resp.status_code == 404


def test_productcatalog_productvariant_create_get(client_a, tenant_a, ecom_product_a):
    """Test productvariant_create GET renders form and pre-fills product from GET param."""
    url = reverse("ecommerce:productvariant_create")
    resp = client_a.get(url, {"product": str(ecom_product_a.pk)})
    assert resp.status_code == 200
    assert resp.context["is_edit"] is False
    assert resp.context["variant"] is None
    assert ecom_product_a in resp.context["products_list"]

    html = resp.content.decode("utf-8")
    assert "New Product Variant" in html or "Create Variant" in html or "New Variant" in html


def test_productcatalog_productvariant_create_post_success(client_a, tenant_a, ecom_product_a):
    """Test productvariant_create POST creates variant, writes audit log, and redirects to product detail."""
    url = reverse("ecommerce:productvariant_create")
    payload = _productcatalog_variant_payload(
        ecom_product_a,
        sku="CUSTOM-VAR-01",
        name="Silver / 32GB",
        price="1299.0000",
    )
    resp = client_a.post(url, data=payload)

    new_var = ProductVariant.objects.filter(tenant=tenant_a, sku="CUSTOM-VAR-01").first()
    assert new_var is not None
    assert new_var.price == Decimal("1299.0000")
    assert new_var.option_values == {"Color": "Midnight Black", "Edition": "Standard"}

    assert resp.status_code == 302
    assert resp.url == reverse("ecommerce:catalogproduct_detail", kwargs={"pk": ecom_product_a.pk})

    # Assert audit log
    log = AuditLog.objects.filter(tenant=tenant_a, action="create", object_id=str(new_var.pk)).first()
    assert log is not None


def test_productcatalog_productvariant_create_post_invalid(client_a, tenant_a, ecom_product_a):
    """Test productvariant_create POST with missing SKU returns form errors."""
    url = reverse("ecommerce:productvariant_create")
    payload = _productcatalog_variant_payload(ecom_product_a, sku="")
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "sku" in resp.context["form"].errors


def test_productcatalog_productvariant_edit_get(client_a, ecom_variant_a):
    """Test productvariant_edit GET renders edit form populated with variant."""
    url = reverse("ecommerce:productvariant_edit", kwargs={"pk": ecom_variant_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["is_edit"] is True
    assert resp.context["variant"] == ecom_variant_a
    html = resp.content.decode("utf-8")
    assert ecom_variant_a.sku in html


def test_productcatalog_productvariant_edit_post_success(client_a, tenant_a, ecom_variant_a):
    """Test productvariant_edit POST updates variant and redirects to variant detail."""
    url = reverse("ecommerce:productvariant_edit", kwargs={"pk": ecom_variant_a.pk})
    payload = _productcatalog_variant_payload(
        ecom_variant_a.product,
        sku=ecom_variant_a.sku,
        name="Updated Variant Name",
        price="1099.5000",
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse("ecommerce:productvariant_detail", kwargs={"pk": ecom_variant_a.pk})

    ecom_variant_a.refresh_from_db()
    assert ecom_variant_a.name == "Updated Variant Name"
    assert ecom_variant_a.price == Decimal("1099.5000")

    # Assert audit log
    log = AuditLog.objects.filter(tenant=tenant_a, action="update", object_id=str(ecom_variant_a.pk)).first()
    assert log is not None


def test_productcatalog_productvariant_edit_post_invalid(client_a, tenant_a, ecom_product_a, ecom_variant_a):
    """Test productvariant_edit POST with missing required SKU re-renders form with errors."""
    url = reverse("ecommerce:productvariant_edit", kwargs={"pk": ecom_variant_a.pk})
    payload = _productcatalog_variant_payload(ecom_product_a, sku="")
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "sku" in resp.context["form"].errors


def test_productcatalog_productvariant_edit_cross_tenant_404(client_b, ecom_variant_a):
    """Test productvariant_edit returns 404 for cross-tenant access."""
    url = reverse("ecommerce:productvariant_edit", kwargs={"pk": ecom_variant_a.pk})
    resp = client_b.get(url)
    assert resp.status_code == 404


def test_productcatalog_productvariant_delete_post_success(client_a, tenant_a, ecom_product_a):
    """Test productvariant_delete POST deletes variant, writes audit log, redirects to parent product."""
    var = _productcatalog_variant(tenant_a, ecom_product_a, sku="DELETE-ME-VAR")
    var_pk = var.pk
    url = reverse("ecommerce:productvariant_delete", kwargs={"pk": var_pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("ecommerce:catalogproduct_detail", kwargs={"pk": ecom_product_a.pk})
    assert not ProductVariant.objects.filter(pk=var_pk).exists()

    # Assert audit log
    log = AuditLog.objects.filter(tenant=tenant_a, action="delete", object_id=str(var_pk)).first()
    assert log is not None


def test_productcatalog_productvariant_delete_get_method_not_allowed(client_a, ecom_variant_a):
    """Test productvariant_delete GET returns 405 Method Not Allowed."""
    url = reverse("ecommerce:productvariant_delete", kwargs={"pk": ecom_variant_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


def test_productcatalog_productvariant_delete_non_admin_forbidden(member_client, ecom_variant_a):
    """Test productvariant_delete returns 403 Forbidden for non-admin user."""
    url = reverse("ecommerce:productvariant_delete", kwargs={"pk": ecom_variant_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403


def test_productcatalog_productvariant_delete_cross_tenant_404(client_b, ecom_variant_a):
    """Test productvariant_delete returns 404 for cross-tenant access."""
    url = reverse("ecommerce:productvariant_delete", kwargs={"pk": ecom_variant_a.pk})
    resp = client_b.post(url)
    assert resp.status_code == 404


# ==============================================================================
# ProductRelationship CRUD Tests
# ==============================================================================

def test_productcatalog_productrelationship_list_renders_200(client_a, tenant_a, ecom_relationship_a):
    """Test productrelationship_list renders 200 with relationship rows and type choices."""
    url = reverse("ecommerce:productrelationship_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "relationships" in resp.context
    assert ecom_relationship_a in resp.context["relationships"]
    assert "relationship_type_choices" in resp.context

    html = resp.content.decode("utf-8")
    assert "Product Relationships" in html
    assert ecom_relationship_a.source_product.name in html
    assert ecom_relationship_a.target_product.name in html


def test_productcatalog_productrelationship_list_filter_type(client_a, tenant_a, ecom_product_a):
    """Test productrelationship_list filters by relationship_type."""
    p2 = _productcatalog_product(tenant_a, name="Target 2", slug="target-2")
    p3 = _productcatalog_product(tenant_a, name="Target 3", slug="target-3")
    r_cross = _productcatalog_relationship(tenant_a, ecom_product_a, p2, relationship_type="cross_sell")
    r_up = _productcatalog_relationship(tenant_a, ecom_product_a, p3, relationship_type="up_sell")

    url = reverse("ecommerce:productrelationship_list")
    resp_cross = client_a.get(url, {"type": "cross_sell"})
    assert resp_cross.status_code == 200
    assert r_cross in resp_cross.context["relationships"]
    assert r_up not in resp_cross.context["relationships"]

    resp_up = client_a.get(url, {"type": "up_sell"})
    assert resp_up.status_code == 200
    assert r_up in resp_up.context["relationships"]
    assert r_cross not in resp_up.context["relationships"]


def test_productcatalog_productrelationship_list_search(client_a, tenant_a, ecom_product_a):
    """Test productrelationship_list searches by source or target product name or notes."""
    p_special = _productcatalog_product(tenant_a, name="Exclusive Headset", slug="exclusive-headset")
    p_normal = _productcatalog_product(tenant_a, name="Generic Cable", slug="generic-cable")
    r1 = _productcatalog_relationship(tenant_a, ecom_product_a, p_special, notes="Seasonal Headset Promo")
    r2 = _productcatalog_relationship(tenant_a, ecom_product_a, p_normal, notes="Standard spare cable")

    url = reverse("ecommerce:productrelationship_list")
    resp_search = client_a.get(url, {"q": "Exclusive"})
    assert resp_search.status_code == 200
    assert r1 in resp_search.context["relationships"]
    assert r2 not in resp_search.context["relationships"]

    resp_notes = client_a.get(url, {"q": "spare"})
    assert resp_notes.status_code == 200
    assert r2 in resp_notes.context["relationships"]
    assert r1 not in resp_notes.context["relationships"]


def test_productcatalog_productrelationship_list_pagination(client_a, tenant_a, ecom_product_a):
    """Test productrelationship_list pagination with >25 relationships."""
    targets = [
        _productcatalog_product(tenant_a, name=f"Target {i:02d}", slug=f"tgt-{i:02d}")
        for i in range(27)
    ]
    rels = [
        _productcatalog_relationship(tenant_a, ecom_product_a, tgt)
        for tgt in targets
    ]
    url = reverse("ecommerce:productrelationship_list")
    resp_p1 = client_a.get(url)
    assert resp_p1.status_code == 200
    assert resp_p1.context["is_paginated"] is True
    assert len(resp_p1.context["relationships"]) == 25

    resp_p2 = client_a.get(url, {"page": 2})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["relationships"]) == 2


def test_productcatalog_productrelationship_list_tenant_isolation(client_a, ecom_relationship_a, client_b, ecom_relationship_b):
    """Test productrelationship_list isolates relationships across tenants."""
    url = reverse("ecommerce:productrelationship_list")
    resp_a = client_a.get(url)
    assert resp_a.status_code == 200
    assert ecom_relationship_a in resp_a.context["relationships"]
    assert ecom_relationship_b not in resp_a.context["relationships"]


def test_productcatalog_productrelationship_detail_view(client_a, ecom_relationship_a):
    """Test productrelationship_detail renders relationship, source, and target products."""
    url = reverse("ecommerce:productrelationship_detail", kwargs={"pk": ecom_relationship_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["relationship"] == ecom_relationship_a
    assert resp.context["source_product"] == ecom_relationship_a.source_product
    assert resp.context["target_product"] == ecom_relationship_a.target_product

    html = resp.content.decode("utf-8")
    assert ecom_relationship_a.source_product.name in html
    assert ecom_relationship_a.target_product.name in html


def test_productcatalog_productrelationship_detail_cross_tenant_404(client_b, ecom_relationship_a):
    """Test productrelationship_detail returns 404 for cross-tenant access."""
    url = reverse("ecommerce:productrelationship_detail", kwargs={"pk": ecom_relationship_a.pk})
    resp = client_b.get(url)
    assert resp.status_code == 404


def test_productcatalog_productrelationship_create_get(client_a, tenant_a, ecom_product_a):
    """Test productrelationship_create GET renders form and pre-fills source_product."""
    url = reverse("ecommerce:productrelationship_create")
    resp = client_a.get(url, {"source": str(ecom_product_a.pk)})
    assert resp.status_code == 200
    assert resp.context["is_edit"] is False
    assert resp.context["relationship"] is None
    assert ecom_product_a in resp.context["products_list"]

    html = resp.content.decode("utf-8")
    assert "New Product Relationship" in html or "Create Relationship" in html or "New Relationship" in html


def test_productcatalog_productrelationship_create_post_success(client_a, tenant_a, ecom_product_a):
    """Test productrelationship_create POST creates mapping, writes audit log, redirects to source product."""
    target_prod = _productcatalog_product(tenant_a, name="Carry Pouch", slug="carry-pouch")
    url = reverse("ecommerce:productrelationship_create")
    payload = _productcatalog_relationship_payload(
        ecom_product_a,
        target_prod,
        relationship_type="accessory",
        discount_pct="20.00",
    )
    resp = client_a.post(url, data=payload)

    rel = ProductRelationship.objects.filter(
        tenant=tenant_a,
        source_product=ecom_product_a,
        target_product=target_prod,
    ).first()
    assert rel is not None
    assert rel.relationship_type == "accessory"
    assert rel.discount_pct == Decimal("20.00")

    assert resp.status_code == 302
    assert resp.url == reverse("ecommerce:catalogproduct_detail", kwargs={"pk": ecom_product_a.pk})

    # Assert audit log
    log = AuditLog.objects.filter(tenant=tenant_a, action="create", object_id=str(rel.pk)).first()
    assert log is not None


def test_productcatalog_productrelationship_create_post_invalid_self_relation(client_a, tenant_a, ecom_product_a):
    """Test productrelationship_create POST rejects linking a product to itself."""
    url = reverse("ecommerce:productrelationship_create")
    payload = _productcatalog_relationship_payload(ecom_product_a, ecom_product_a)
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "target_product" in resp.context["form"].errors


def test_productcatalog_productrelationship_edit_get(client_a, ecom_relationship_a):
    """Test productrelationship_edit GET renders edit form populated with relationship."""
    url = reverse("ecommerce:productrelationship_edit", kwargs={"pk": ecom_relationship_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["is_edit"] is True
    assert resp.context["relationship"] == ecom_relationship_a

    html = resp.content.decode("utf-8")
    assert ecom_relationship_a.source_product.name in html
    assert ecom_relationship_a.target_product.name in html


def test_productcatalog_productrelationship_edit_post_success(client_a, tenant_a, ecom_relationship_a):
    """Test productrelationship_edit POST updates relationship and redirects to relationship detail."""
    url = reverse("ecommerce:productrelationship_edit", kwargs={"pk": ecom_relationship_a.pk})
    payload = _productcatalog_relationship_payload(
        ecom_relationship_a.source_product,
        ecom_relationship_a.target_product,
        relationship_type="up_sell",
        discount_pct="25.00",
        notes="Updated upsell bundle notes.",
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse("ecommerce:productrelationship_detail", kwargs={"pk": ecom_relationship_a.pk})

    ecom_relationship_a.refresh_from_db()
    assert ecom_relationship_a.relationship_type == "up_sell"
    assert ecom_relationship_a.discount_pct == Decimal("25.00")
    assert ecom_relationship_a.notes == "Updated upsell bundle notes."

    # Assert audit log
    log = AuditLog.objects.filter(tenant=tenant_a, action="update", object_id=str(ecom_relationship_a.pk)).first()
    assert log is not None


def test_productcatalog_productrelationship_edit_post_invalid(client_a, tenant_a, ecom_relationship_a):
    """Test productrelationship_edit POST with self-target fails validation."""
    url = reverse("ecommerce:productrelationship_edit", kwargs={"pk": ecom_relationship_a.pk})
    payload = _productcatalog_relationship_payload(
        ecom_relationship_a.source_product,
        ecom_relationship_a.source_product,  # Self target
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "target_product" in resp.context["form"].errors


def test_productcatalog_productrelationship_edit_cross_tenant_404(client_b, ecom_relationship_a):
    """Test productrelationship_edit returns 404 for cross-tenant access."""
    url = reverse("ecommerce:productrelationship_edit", kwargs={"pk": ecom_relationship_a.pk})
    resp = client_b.get(url)
    assert resp.status_code == 404


def test_productcatalog_productrelationship_delete_post_success(client_a, tenant_a, ecom_relationship_a):
    """Test productrelationship_delete POST removes mapping, writes audit log, redirects to source product."""
    rel_pk = ecom_relationship_a.pk
    source_pk = ecom_relationship_a.source_product_id
    url = reverse("ecommerce:productrelationship_delete", kwargs={"pk": rel_pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("ecommerce:catalogproduct_detail", kwargs={"pk": source_pk})
    assert not ProductRelationship.objects.filter(pk=rel_pk).exists()

    # Assert audit log
    log = AuditLog.objects.filter(tenant=tenant_a, action="delete", object_id=str(rel_pk)).first()
    assert log is not None


def test_productcatalog_productrelationship_delete_get_method_not_allowed(client_a, ecom_relationship_a):
    """Test productrelationship_delete GET returns 405 Method Not Allowed."""
    url = reverse("ecommerce:productrelationship_delete", kwargs={"pk": ecom_relationship_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


def test_productcatalog_productrelationship_delete_non_admin_forbidden(member_client, ecom_relationship_a):
    """Test productrelationship_delete returns 403 Forbidden for non-admin user."""
    url = reverse("ecommerce:productrelationship_delete", kwargs={"pk": ecom_relationship_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403


def test_productcatalog_productrelationship_delete_cross_tenant_404(client_b, ecom_relationship_a):
    """Test productrelationship_delete returns 404 for cross-tenant access."""
    url = reverse("ecommerce:productrelationship_delete", kwargs={"pk": ecom_relationship_a.pk})
    resp = client_b.post(url)
    assert resp.status_code == 404


# ==============================================================================
# Bulk Operations Tests
# ==============================================================================

def test_productcatalog_product_import_csv_get(client_a):
    """Test product_import_csv GET renders upload form."""
    url = reverse("ecommerce:product_import_csv")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    html = resp.content.decode("utf-8")
    assert "Bulk Product &amp; Variant Import" in html or "Bulk Product & Variant Import" in html
    assert "Upload CSV Catalog File" in html


def test_productcatalog_product_import_csv_post_dry_run(client_a, tenant_a):
    """Test product_import_csv POST with dry_run=True previews records without writing to DB."""
    csv_file = _productcatalog_sample_csv(
        content=(
            "Product_Name,Slug,Brand,Category,Status,Visibility,SKU,Variant_Name,Price,Compare_At_Price,Cost_Price,Barcode\n"
            "Dry Run Monitor,dry-run-mon,DisplayCorp,Screens,active,storefront,DRY-MON-01,27 inch 4K,499.00,599.00,300.00,111222333444\n"
        )
    )
    url = reverse("ecommerce:product_import_csv")
    resp = client_a.post(
        url,
        data={
            "csv_file": csv_file,
            "dry_run": True,
            "auto_create_categories": True,
        },
    )
    assert resp.status_code == 200
    results = resp.context["import_results"]
    assert results is not None
    assert results["dry_run"] is True
    assert results["created_products"] == 1
    assert results["created_variants"] == 1
    assert results["errors_count"] == 0

    # Ensure no DB records were created
    assert not CatalogProduct.objects.filter(tenant=tenant_a, slug="dry-run-mon").exists()
    assert not ProductVariant.objects.filter(tenant=tenant_a, sku="DRY-MON-01").exists()
    assert not StoreCategory.objects.filter(tenant=tenant_a, slug="screens").exists()


def test_productcatalog_product_import_csv_post_actual_import(client_a, tenant_a):
    """Test product_import_csv POST with dry_run=False commits products, variants, categories, and audit log."""
    csv_file = _productcatalog_sample_csv(
        content=(
            "Product_Name,Slug,Brand,Category,Status,Visibility,SKU,Variant_Name,Price,Compare_At_Price,Cost_Price,Barcode\n"
            "Mechanical Keyboard,mech-kb,KeyCorp,Keyboards,active,storefront,KB-RGB-01,RGB Linear,129.99,149.99,70.00,123456789012\n"
        )
    )
    url = reverse("ecommerce:product_import_csv")
    resp = client_a.post(
        url,
        data={
            "csv_file": csv_file,
            "dry_run": False,
            "auto_create_categories": True,
        },
    )
    assert resp.status_code == 200
    results = resp.context["import_results"]
    assert results is not None
    assert results["dry_run"] is False
    assert results["created_products"] == 1
    assert results["created_variants"] == 1
    assert results["errors_count"] == 0

    # Verify DB records created
    cat = StoreCategory.objects.filter(tenant=tenant_a, slug="keyboards").first()
    assert cat is not None
    assert cat.name == "Keyboards"

    prod = CatalogProduct.objects.filter(tenant=tenant_a, slug="mech-kb").first()
    assert prod is not None
    assert prod.name == "Mechanical Keyboard"
    assert prod.primary_category == cat

    variant = ProductVariant.objects.filter(tenant=tenant_a, sku="KB-RGB-01").first()
    assert variant is not None
    assert variant.product == prod
    assert variant.price == Decimal("129.99")
    assert variant.compare_at_price == Decimal("149.99")

    # Assert audit log
    log = AuditLog.objects.filter(tenant=tenant_a, action="create").first()
    assert log is not None


def test_productcatalog_product_import_csv_post_with_errors(client_a, tenant_a):
    """Test product_import_csv handles rows with missing product name and invalid price format."""
    csv_file = _productcatalog_sample_csv(
        content=(
            "Product_Name,Slug,Brand,Category,Status,Visibility,SKU,Variant_Name,Price,Compare_At_Price,Cost_Price,Barcode\n"
            ",bad-slug,BrandX,CatX,active,storefront,SKU-BAD-1,Var1,10.00,,,\n"
            "Good Product,good-prod,BrandY,CatY,active,storefront,SKU-BAD-2,Var2,INVALID_PRICE,,,\n"
        )
    )
    url = reverse("ecommerce:product_import_csv")
    resp = client_a.post(
        url,
        data={
            "csv_file": csv_file,
            "dry_run": False,
            "auto_create_categories": True,
        },
    )
    assert resp.status_code == 200
    assert len(resp.context["errors"]) == 2
    html = resp.content.decode("utf-8")
    assert "Missing required" in html
    assert "Product_Name" in html
    assert "Invalid Price" in html
    assert "INVALID_PRICE" in html


def test_productcatalog_product_import_csv_post_invalid_file_extension(client_a):
    """Test product_import_csv rejects non-CSV files."""
    text_file = SimpleUploadedFile("products.txt", b"some text content", content_type="text/plain")
    url = reverse("ecommerce:product_import_csv")
    resp = client_a.post(
        url,
        data={"csv_file": text_file},
    )
    assert resp.status_code == 200
    assert "csv_file" in resp.context["form"].errors
    html = resp.content.decode("utf-8")
    assert "Only .csv files are supported" in html


def test_productcatalog_product_export_csv_get_headers_and_content(client_a, tenant_a, ecom_category_a, ecom_product_a, ecom_variant_a):
    """Test product_export_csv GET returns valid CSV attachment with headers and row data."""
    url = reverse("ecommerce:product_export_csv")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"
    assert f'filename="catalog_export_{tenant_a.pk}.csv"' in resp["Content-Disposition"]

    content = resp.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)

    # Assert header row
    assert rows[0] == [
        "Product_Number",
        "Product_Name",
        "Slug",
        "Brand",
        "Category",
        "Status",
        "Visibility",
        "SKU",
        "Variant_Name",
        "Price",
        "Compare_At_Price",
        "Cost_Price",
        "Barcode",
        "Weight_KG",
    ]

    # Assert data row
    data_row = rows[1]
    assert data_row[0] == ecom_product_a.number
    assert data_row[1] == ecom_product_a.name
    assert data_row[2] == ecom_product_a.slug
    assert data_row[3] == ecom_product_a.brand
    assert data_row[4] == ecom_category_a.name
    assert data_row[7] == ecom_variant_a.sku
    assert data_row[8] == ecom_variant_a.name
    assert Decimal(data_row[9]) == ecom_variant_a.price


def test_productcatalog_product_export_csv_product_without_variants(client_a, tenant_a, ecom_category_a):
    """Test product_export_csv exports products without variants with blank variant fields."""
    prod_no_var = _productcatalog_product(
        tenant_a,
        name="Digital E-Book",
        slug="digital-ebook",
        primary_category=ecom_category_a,
    )
    url = reverse("ecommerce:product_export_csv")
    resp = client_a.get(url)
    assert resp.status_code == 200

    content = resp.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)

    matched_rows = [r for r in rows if r[1] == "Digital E-Book"]
    assert len(matched_rows) == 1
    row = matched_rows[0]
    assert row[2] == "digital-ebook"
    assert row[7] == ""  # SKU is blank
    assert row[8] == ""  # Variant name is blank
    assert row[9] == ""  # Price is blank


def test_productcatalog_product_export_csv_tenant_isolation(client_a, tenant_a, client_b, tenant_b, ecom_product_a, ecom_product_b):
    """Test product_export_csv isolates exported products across tenants."""
    url = reverse("ecommerce:product_export_csv")

    resp_a = client_a.get(url)
    content_a = resp_a.content.decode("utf-8")
    assert ecom_product_a.name in content_a
    assert ecom_product_b.name not in content_a

    resp_b = client_b.get(url)
    content_b = resp_b.content.decode("utf-8")
    assert ecom_product_b.name in content_b
    assert ecom_product_a.name not in content_b
