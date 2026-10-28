"""Shared test contract constants and fixtures for apps/ecommerce."""
from decimal import Decimal
import pytest
from django.utils import timezone
from apps.ecommerce.models import (
    StoreCategory,
    CatalogProduct,
    ProductVariant,
    ProductRelationship,
)

PRODUCTCATALOG_PAGE_SIZE = 20

PRODUCTCATALOG_MODEL_FIELDS = {
    "StoreCategory": (
        "id", "tenant", "number", "name", "slug", "parent", "description",
        "image_url", "display_order", "is_active", "include_in_menu",
        "meta_title", "meta_description", "created_at", "updated_at",
    ),
    "CatalogProduct": (
        "id", "tenant", "number", "name", "slug", "item", "primary_category",
        "categories", "status", "visibility", "brand", "short_description",
        "description", "hero_image_url", "video_url", "is_featured",
        "is_digital", "pim_completeness", "meta_title", "meta_description",
        "published_at", "created_at", "updated_at",
    ),
    "ProductVariant": (
        "id", "tenant", "number", "product", "sku", "name", "option_values",
        "barcode", "price", "compare_at_price", "cost_price", "item",
        "weight_kg", "image_url", "is_active", "sort_order", "created_at", "updated_at",
    ),
    "ProductRelationship": (
        "id", "tenant", "number", "source_product", "target_product",
        "relationship_type", "discount_pct", "is_active", "sort_order",
        "notes", "created_at", "updated_at",
    ),
}

PRODUCTCATALOG_CHOICES = {
    "CatalogProduct": {
        "status": (("draft", "Draft"), ("active", "Active"), ("archived", "Archived")),
        "visibility": (
            ("storefront", "Storefront & Search"),
            ("hidden", "Hidden"),
            ("search_only", "Search Only"),
        ),
    },
    "ProductRelationship": {
        "relationship_type": (
            ("cross_sell", "Cross-Sell"),
            ("up_sell", "Up-Sell"),
            ("accessory", "Accessory"),
            ("bundle_kit", "Bundle / Kit Component"),
            ("bought_together", "Frequently Bought Together"),
        ),
    },
}

PRODUCTCATALOG_FORM_FIELDS = {
    "StoreCategoryForm": (
        "name", "slug", "parent", "description", "image_url",
        "display_order", "is_active", "include_in_menu", "meta_title", "meta_description",
    ),
    "CatalogProductForm": (
        "name", "slug", "item", "primary_category", "categories", "status",
        "visibility", "brand", "short_description", "description", "hero_image_url",
        "video_url", "is_featured", "is_digital", "meta_title", "meta_description",
    ),
    "ProductVariantForm": (
        "product", "sku", "name", "option_values", "barcode", "price",
        "compare_at_price", "cost_price", "item", "weight_kg", "image_url",
        "is_active", "sort_order",
    ),
    "ProductRelationshipForm": (
        "source_product", "target_product", "relationship_type",
        "discount_pct", "is_active", "sort_order", "notes",
    ),
    "ProductImportForm": ("csv_file", "dry_run", "auto_create_categories"),
}

PRODUCTCATALOG_URLS = {
    "storecategory_list": "categories/",
    "storecategory_create": "categories/create/",
    "storecategory_detail": "categories/<int:pk>/",
    "storecategory_edit": "categories/<int:pk>/edit/",
    "storecategory_delete": "categories/<int:pk>/delete/",
    "catalogproduct_list": "products/",
    "catalogproduct_create": "products/create/",
    "catalogproduct_detail": "products/<int:pk>/",
    "catalogproduct_edit": "products/<int:pk>/edit/",
    "catalogproduct_delete": "products/<int:pk>/delete/",
    "catalogproduct_publish": "products/<int:pk>/publish/",
    "productvariant_list": "variants/",
    "productvariant_create": "variants/create/",
    "productvariant_detail": "variants/<int:pk>/",
    "productvariant_edit": "variants/<int:pk>/edit/",
    "productvariant_delete": "variants/<int:pk>/delete/",
    "productrelationship_list": "relationships/",
    "productrelationship_create": "relationships/create/",
    "productrelationship_detail": "relationships/<int:pk>/",
    "productrelationship_edit": "relationships/<int:pk>/edit/",
    "productrelationship_delete": "relationships/<int:pk>/delete/",
    "product_import_csv": "products/import/",
    "product_export_csv": "products/export/",
    "catalog_overview": "overview/",
    "dashboard": "",
}


def _productcatalog_category(tenant, name="Electronics", slug=None, parent=None, **overrides):
    if not slug:
        slug = f"{name.lower().replace(' ', '-')}-{tenant.slug}"
    defaults = {
        "tenant": tenant,
        "name": name,
        "slug": slug,
        "parent": parent,
        "description": f"{name} category description",
        "display_order": 0,
        "is_active": True,
        "include_in_menu": True,
    }
    defaults.update(overrides)
    return StoreCategory.objects.create(**defaults)


def _productcatalog_product(tenant, name="Pro Laptop", slug=None, primary_category=None, **overrides):
    if not slug:
        slug = f"{name.lower().replace(' ', '-')}-{tenant.slug}"
    defaults = {
        "tenant": tenant,
        "name": name,
        "slug": slug,
        "primary_category": primary_category,
        "status": "active",
        "visibility": "storefront",
        "brand": "AcmeBrand",
        "short_description": "A high-performance laptop.",
        "description": "Full detailed description of the laptop.",
        "is_featured": True,
        "is_digital": False,
    }
    defaults.update(overrides)
    return CatalogProduct.objects.create(**defaults)


def _productcatalog_variant(tenant, product, sku=None, name="Base Model", price=Decimal("999.0000"), **overrides):
    if not sku:
        sku = f"SKU-{product.slug[:8]}-{tenant.slug}"
    defaults = {
        "tenant": tenant,
        "product": product,
        "sku": sku,
        "name": name,
        "option_values": {"Color": "Silver", "RAM": "16GB"},
        "price": price,
        "cost_price": Decimal("600.0000"),
        "compare_at_price": Decimal("1199.0000"),
        "weight_kg": Decimal("1.500"),
        "is_active": True,
        "sort_order": 0,
    }
    defaults.update(overrides)
    return ProductVariant.objects.create(**defaults)


def _productcatalog_relationship(tenant, source_product, target_product, relationship_type="cross_sell", **overrides):
    defaults = {
        "tenant": tenant,
        "source_product": source_product,
        "target_product": target_product,
        "relationship_type": relationship_type,
        "discount_pct": Decimal("10.00"),
        "is_active": True,
        "sort_order": 0,
        "notes": "Recommended together.",
    }
    defaults.update(overrides)
    return ProductRelationship.objects.create(**defaults)


@pytest.fixture
def ecom_category_a(tenant_a):
    return _productcatalog_category(tenant_a, name="Hardware A")


@pytest.fixture
def ecom_category_b(tenant_b):
    return _productcatalog_category(tenant_b, name="Hardware B")


@pytest.fixture
def ecom_product_a(tenant_a, ecom_category_a):
    return _productcatalog_product(tenant_a, name="Server A", primary_category=ecom_category_a)


@pytest.fixture
def ecom_product_b(tenant_b, ecom_category_b):
    return _productcatalog_product(tenant_b, name="Server B", primary_category=ecom_category_b)


@pytest.fixture
def ecom_variant_a(tenant_a, ecom_product_a):
    return _productcatalog_variant(tenant_a, ecom_product_a, sku="SRV-A-01")


@pytest.fixture
def ecom_variant_b(tenant_b, ecom_product_b):
    return _productcatalog_variant(tenant_b, ecom_product_b, sku="SRV-B-01")


@pytest.fixture
def ecom_relationship_a(tenant_a, ecom_product_a):
    product2 = _productcatalog_product(tenant_a, name="Accessory A", slug="accessory-a")
    return _productcatalog_relationship(tenant_a, ecom_product_a, product2)


@pytest.fixture
def ecom_relationship_b(tenant_b, ecom_product_b):
    product2 = _productcatalog_product(tenant_b, name="Accessory B", slug="accessory-b")
    return _productcatalog_relationship(tenant_b, ecom_product_b, product2)
