"""Shared test contract constants and fixtures for apps/ecommerce."""
from decimal import Decimal
import pytest
from django.utils import timezone
from apps.ecommerce.models import (
    StoreCategory,
    CatalogProduct,
    ProductVariant,
    ProductRelationship,
    FulfillmentCenter,
    InventoryAllocation,
    BackorderPolicy,
    ChannelInventorySync,
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


INVENTORYSTOCK_PAGE_SIZE = 20

INVENTORYSTOCK_MODEL_FIELDS = {
    "FulfillmentCenter": (
        "id", "tenant", "number", "name", "code", "center_type", "location",
        "priority", "is_active", "supports_pick_pack_ship", "supports_customer_pickup",
        "daily_cutoff_time", "address_line1", "city", "state", "postal_code",
        "country", "contact_email", "contact_phone", "notes", "created_at", "updated_at",
    ),
    "InventoryAllocation": (
        "id", "tenant", "number", "product", "variant", "fulfillment_center",
        "zone_bin", "quantity_on_hand", "quantity_allocated", "safety_stock_buffer",
        "low_stock_threshold", "restock_lead_time_days", "last_counted_at",
        "notes", "created_at", "updated_at",
    ),
    "BackorderPolicy": (
        "id", "tenant", "number", "variant", "policy_type", "storefront_message",
        "expected_availability_date", "max_backorder_quantity", "current_backorder_count",
        "auto_notify_waitlist", "is_active", "notes", "created_at", "updated_at",
    ),
    "ChannelInventorySync": (
        "id", "tenant", "number", "variant", "channel_type", "channel_name",
        "fulfillment_center", "sync_mode", "allocation_buffer_pct", "last_synced_quantity",
        "sync_status", "last_synced_at", "error_message", "created_at", "updated_at",
    ),
}

INVENTORYSTOCK_CHOICES = {
    "FulfillmentCenter": {
        "center_type": (
            ("internal_warehouse", "Internal Distribution Center"),
            ("third_party_3pl", "Third-Party Logistics (3PL) Partner"),
            ("retail_store", "Retail Store Node"),
            ("drop_shipper", "Direct Vendor Drop-Shipper"),
        ),
    },
    "BackorderPolicy": {
        "policy_type": (
            ("deny_when_empty", "Deny When Out of Stock (Standard)"),
            ("allow_backorder_with_notice", "Allow Backorders with Warning Notice"),
            ("pre_order_only", "Pre-Order Mode (Advance Campaign)"),
        ),
    },
    "ChannelInventorySync": {
        "channel_type": (
            ("web_storefront", "Direct Web Storefront"),
            ("amazon_marketplace", "Amazon Marketplace"),
            ("walmart_marketplace", "Walmart Marketplace"),
            ("pos_retail", "Retail POS Register"),
            ("wholesale_b2b", "B2B Wholesale Portal"),
        ),
        "sync_mode": (
            ("real_time", "Real-Time Event Sync"),
            ("scheduled_batch", "Scheduled Batch"),
            ("manual", "Manual Push Only"),
        ),
        "sync_status": (
            ("synced", "In Sync"),
            ("pending", "Sync Pending"),
            ("sync_error", "Sync Error"),
            ("disabled", "Disabled"),
        ),
    },
}

INVENTORYSTOCK_FORM_FIELDS = {
    "FulfillmentCenterForm": (
        "name", "code", "center_type", "location", "priority", "is_active",
        "supports_pick_pack_ship", "supports_customer_pickup", "daily_cutoff_time",
        "address_line1", "city", "state", "postal_code", "country", "contact_email",
        "contact_phone", "notes",
    ),
    "InventoryAllocationForm": (
        "product", "variant", "fulfillment_center", "zone_bin", "quantity_on_hand",
        "quantity_allocated", "safety_stock_buffer", "low_stock_threshold",
        "restock_lead_time_days", "last_counted_at", "notes",
    ),
    "StockAdjustmentActionForm": (
        "adjustment_type", "adjustment_quantity", "reason_notes",
    ),
    "BackorderPolicyForm": (
        "variant", "policy_type", "storefront_message", "expected_availability_date",
        "max_backorder_quantity", "auto_notify_waitlist", "is_active", "notes",
    ),
    "ChannelInventorySyncForm": (
        "variant", "channel_type", "channel_name", "fulfillment_center",
        "sync_mode", "allocation_buffer_pct", "sync_status", "error_message",
    ),
}

INVENTORYSTOCK_URLS = {
    "inventory_operations": "inventory/",
    "fulfillmentcenter_list": "inventory/centers/",
    "fulfillmentcenter_create": "inventory/centers/create/",
    "fulfillmentcenter_detail": "inventory/centers/<int:pk>/",
    "fulfillmentcenter_edit": "inventory/centers/<int:pk>/edit/",
    "fulfillmentcenter_delete": "inventory/centers/<int:pk>/delete/",
    "inventoryallocation_list": "inventory/allocations/",
    "inventoryallocation_create": "inventory/allocations/create/",
    "inventoryallocation_detail": "inventory/allocations/<int:pk>/",
    "inventoryallocation_edit": "inventory/allocations/<int:pk>/edit/",
    "inventoryallocation_delete": "inventory/allocations/<int:pk>/delete/",
    "inventoryallocation_adjust": "inventory/allocations/<int:pk>/adjust/",
    "backorderpolicy_list": "inventory/backorders/",
    "backorderpolicy_create": "inventory/backorders/create/",
    "backorderpolicy_detail": "inventory/backorders/<int:pk>/",
    "backorderpolicy_edit": "inventory/backorders/<int:pk>/edit/",
    "backorderpolicy_delete": "inventory/backorders/<int:pk>/delete/",
    "channelinventorysync_list": "inventory/sync/",
    "channelinventorysync_create": "inventory/sync/create/",
    "channelinventorysync_detail": "inventory/sync/<int:pk>/",
    "channelinventorysync_edit": "inventory/sync/<int:pk>/edit/",
    "channelinventorysync_delete": "inventory/sync/<int:pk>/delete/",
    "channelinventorysync_trigger": "inventory/sync/<int:pk>/trigger/",
}


def _inventorystock_center(tenant, name="West DC", code=None, **overrides):
    if not code:
        code = f"DC-{tenant.slug.upper()[:4]}-{name[:3].upper()}"
    defaults = {
        "tenant": tenant,
        "name": name,
        "code": code,
        "center_type": "internal_warehouse",
        "priority": 1,
        "is_active": True,
        "supports_pick_pack_ship": True,
        "supports_customer_pickup": False,
        "city": "Seattle",
        "country": "USA",
    }
    defaults.update(overrides)
    return FulfillmentCenter.objects.create(**defaults)


def _inventorystock_allocation(tenant, variant, center, quantity_on_hand=100, **overrides):
    defaults = {
        "tenant": tenant,
        "product": variant.product,
        "variant": variant,
        "fulfillment_center": center,
        "zone_bin": "A1-B2",
        "quantity_on_hand": quantity_on_hand,
        "quantity_allocated": 10,
        "safety_stock_buffer": 5,
        "low_stock_threshold": 15,
        "restock_lead_time_days": 7,
    }
    defaults.update(overrides)
    return InventoryAllocation.objects.create(**defaults)


def _inventorystock_backorder(tenant, variant, policy_type="allow_backorder_with_notice", **overrides):
    defaults = {
        "tenant": tenant,
        "variant": variant,
        "policy_type": policy_type,
        "storefront_message": "Available on backorder. Ships in 2 weeks.",
        "max_backorder_quantity": 50,
        "current_backorder_count": 0,
        "auto_notify_waitlist": True,
        "is_active": True,
    }
    defaults.update(overrides)
    return BackorderPolicy.objects.create(**defaults)


def _inventorystock_sync(tenant, variant, center=None, channel_type="amazon_marketplace", **overrides):
    defaults = {
        "tenant": tenant,
        "variant": variant,
        "channel_type": channel_type,
        "channel_name": f"{channel_type.replace('_', ' ').title()} Feed",
        "fulfillment_center": center,
        "sync_mode": "real_time",
        "allocation_buffer_pct": Decimal("10.00"),
        "last_synced_quantity": 75,
        "sync_status": "synced",
    }
    defaults.update(overrides)
    return ChannelInventorySync.objects.create(**defaults)


@pytest.fixture
def ecom_center_a(tenant_a):
    return _inventorystock_center(tenant_a, name="Seattle Hub A", code="SEA-A")


@pytest.fixture
def ecom_center_b(tenant_b):
    return _inventorystock_center(tenant_b, name="Denver Hub B", code="DEN-B")


@pytest.fixture
def ecom_allocation_a(tenant_a, ecom_variant_a, ecom_center_a):
    return _inventorystock_allocation(tenant_a, ecom_variant_a, ecom_center_a, quantity_on_hand=150)


@pytest.fixture
def ecom_allocation_b(tenant_b, ecom_variant_b, ecom_center_b):
    return _inventorystock_allocation(tenant_b, ecom_variant_b, ecom_center_b, quantity_on_hand=80)


@pytest.fixture
def ecom_backorder_a(tenant_a, ecom_variant_a):
    return _inventorystock_backorder(tenant_a, ecom_variant_a)


@pytest.fixture
def ecom_backorder_b(tenant_b, ecom_variant_b):
    return _inventorystock_backorder(tenant_b, ecom_variant_b)


@pytest.fixture
def ecom_sync_a(tenant_a, ecom_variant_a, ecom_center_a):
    return _inventorystock_sync(tenant_a, ecom_variant_a, ecom_center_a, channel_type="amazon_marketplace")


@pytest.fixture
def ecom_sync_b(tenant_b, ecom_variant_b, ecom_center_b):
    return _inventorystock_sync(tenant_b, ecom_variant_b, ecom_center_b, channel_type="web_storefront")
