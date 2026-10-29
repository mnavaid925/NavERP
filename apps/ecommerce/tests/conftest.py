"""Shared test contract constants and fixtures for apps/ecommerce."""
from decimal import Decimal
import pytest
from django.utils import timezone
from apps.accounting.models.GeneralLedger.Currencies import Currency
from apps.core.models import Party
from apps.ecommerce.models import (
    StoreCategory,
    CatalogProduct,
    ProductVariant,
    ProductRelationship,
    FulfillmentCenter,
    InventoryAllocation,
    BackorderPolicy,
    ChannelInventorySync,
    DynamicPriceRule,
    CouponPromotion,
    FlashSale,
    CompetitorPriceMonitor,
    EcommerceOrder,
    EcommerceOrderLine,
    OrderRoutingRule,
    OrderFulfillment,
    ReturnMerchandiseAuthorization,
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


PRICINGPROMOTION_PAGE_SIZE = 20

PRICINGPROMOTION_MODEL_FIELDS = {
    "DynamicPriceRule": (
        "id", "tenant", "number", "name", "rule_type", "adjustment_value",
        "scope", "category", "product", "variant", "customer_segment",
        "loyalty_tier", "min_quantity", "country_code", "currency_code",
        "valid_from", "valid_to", "priority", "is_active", "description",
        "created_at", "updated_at",
    ),
    "CouponPromotion": (
        "id", "tenant", "number", "code", "name", "discount_type",
        "discount_value", "min_spend", "max_discount_amount",
        "usage_limit_total", "usage_limit_per_customer", "used_count",
        "is_stackable", "loyalty_tier_required", "customer", "valid_from",
        "valid_to", "is_active", "created_at", "updated_at",
    ),
    "FlashSale": (
        "id", "tenant", "number", "title", "status", "product", "variant",
        "category", "discount_percentage", "flash_price", "inventory_cap",
        "units_sold", "max_units_per_order", "start_time", "end_time",
        "badge_label", "banner_bg_color", "terms_and_conditions",
        "created_at", "updated_at",
    ),
    "CompetitorPriceMonitor": (
        "id", "tenant", "number", "competitor_name", "product", "variant",
        "competitor_url", "competitor_price", "competitor_currency",
        "is_in_stock", "last_scraped_at", "match_strategy", "beat_by_value",
        "min_margin_pct", "floor_price", "status", "notes",
        "created_at", "updated_at",
    ),
}

PRICINGPROMOTION_CHOICES = {
    "DynamicPriceRule": {
        "rule_type": (
            ("percentage_discount", "Percentage Discount"),
            ("fixed_discount", "Fixed Discount Amount"),
            ("fixed_price_override", "Fixed Price Override"),
        ),
        "scope": (
            ("storewide", "Storewide"),
            ("category", "Category"),
            ("product", "Specific Product"),
            ("variant", "Specific SKU Variant"),
        ),
        "customer_segment": (
            ("all", "All Customers"),
            ("retail", "Retail / Standard"),
            ("wholesale", "Wholesale / B2B"),
            ("vip", "VIP / Key Accounts"),
        ),
        "loyalty_tier": (
            ("none", "No Loyalty Requirement"),
            ("bronze", "Bronze Tier"),
            ("silver", "Silver Tier"),
            ("gold", "Gold Tier"),
            ("platinum", "Platinum Tier"),
        ),
    },
    "CouponPromotion": {
        "discount_type": (
            ("percentage", "Percentage Off Cart"),
            ("fixed_cart", "Fixed Amount Off Cart"),
            ("fixed_item", "Fixed Amount Off Item"),
            ("free_shipping", "Free Shipping"),
        ),
        "loyalty_tier_required": (
            ("none", "No Loyalty Requirement"),
            ("bronze", "Bronze Tier"),
            ("silver", "Silver Tier"),
            ("gold", "Gold Tier"),
            ("platinum", "Platinum Tier"),
        ),
    },
    "FlashSale": {
        "status": (
            ("draft", "Draft"),
            ("scheduled", "Scheduled"),
            ("active", "Active"),
            ("paused", "Paused"),
            ("ended", "Ended"),
        ),
    },
    "CompetitorPriceMonitor": {
        "match_strategy": (
            ("manual", "Manual Review Only"),
            ("match_exact", "Match Competitor Exact Price"),
            ("beat_by_fixed", "Beat Competitor by Fixed Amount"),
            ("beat_by_percent", "Beat Competitor by Percentage"),
        ),
        "status": (
            ("active", "Active Tracking"),
            ("paused", "Paused"),
            ("margin_suppressed", "Suppressed (Margin Risk)"),
            ("out_of_stock", "Competitor Out of Stock"),
        ),
    },
}

PRICINGPROMOTION_FORM_FIELDS = {
    "DynamicPriceRuleForm": (
        "name", "rule_type", "adjustment_value", "scope", "category",
        "product", "variant", "customer_segment", "loyalty_tier",
        "min_quantity", "country_code", "currency_code", "valid_from",
        "valid_to", "priority", "is_active", "description",
    ),
    "CouponPromotionForm": (
        "code", "name", "discount_type", "discount_value", "min_spend",
        "max_discount_amount", "usage_limit_total", "usage_limit_per_customer",
        "is_stackable", "loyalty_tier_required", "customer", "valid_from",
        "valid_to", "is_active",
    ),
    "FlashSaleForm": (
        "title", "status", "product", "variant", "category",
        "discount_percentage", "flash_price", "inventory_cap",
        "max_units_per_order", "start_time", "end_time", "badge_label",
        "banner_bg_color", "terms_and_conditions",
    ),
    "CompetitorPriceMonitorForm": (
        "competitor_name", "product", "variant", "competitor_url",
        "competitor_price", "competitor_currency", "is_in_stock",
        "match_strategy", "beat_by_value", "min_margin_pct",
        "floor_price", "status", "notes",
    ),
}

PRICINGPROMOTION_URLS = {
    "dynamicpricerule_list": "pricing/rules/",
    "dynamicpricerule_create": "pricing/rules/create/",
    "dynamicpricerule_detail": "pricing/rules/<int:pk>/",
    "dynamicpricerule_edit": "pricing/rules/<int:pk>/edit/",
    "dynamicpricerule_delete": "pricing/rules/<int:pk>/delete/",
    "couponpromotion_list": "pricing/coupons/",
    "couponpromotion_create": "pricing/coupons/create/",
    "couponpromotion_detail": "pricing/coupons/<int:pk>/",
    "couponpromotion_edit": "pricing/coupons/<int:pk>/edit/",
    "couponpromotion_delete": "pricing/coupons/<int:pk>/delete/",
    "flashsale_list": "pricing/flash-sales/",
    "flashsale_create": "pricing/flash-sales/create/",
    "flashsale_detail": "pricing/flash-sales/<int:pk>/",
    "flashsale_edit": "pricing/flash-sales/<int:pk>/edit/",
    "flashsale_delete": "pricing/flash-sales/<int:pk>/delete/",
    "competitorpricemonitor_list": "pricing/competitors/",
    "competitorpricemonitor_create": "pricing/competitors/create/",
    "competitorpricemonitor_detail": "pricing/competitors/<int:pk>/",
    "competitorpricemonitor_edit": "pricing/competitors/<int:pk>/edit/",
    "competitorpricemonitor_delete": "pricing/competitors/<int:pk>/delete/",
    "competitorpricemonitor_sync": "pricing/competitors/<int:pk>/sync/",
}


def _pricingpromotion_rule(tenant, name="Standard 10% Off", **overrides):
    defaults = {
        "tenant": tenant,
        "name": name,
        "rule_type": "percentage_discount",
        "adjustment_value": Decimal("10.0000"),
        "scope": "storewide",
        "customer_segment": "all",
        "loyalty_tier": "none",
        "min_quantity": 1,
        "currency_code": "USD",
        "priority": 10,
        "is_active": True,
        "valid_from": timezone.now(),
    }
    defaults.update(overrides)
    return DynamicPriceRule.objects.create(**defaults)


def _pricingpromotion_coupon(tenant, code="SAVE20", name="Save 20 Dollars", **overrides):
    defaults = {
        "tenant": tenant,
        "code": code.upper(),
        "name": name,
        "discount_type": "fixed_cart",
        "discount_value": Decimal("20.0000"),
        "min_spend": Decimal("50.0000"),
        "usage_limit_total": 500,
        "usage_limit_per_customer": 1,
        "is_active": True,
        "valid_from": timezone.now(),
    }
    defaults.update(overrides)
    return CouponPromotion.objects.create(**defaults)


def _pricingpromotion_flash_sale(tenant, title="Flash Midnight Deal", **overrides):
    now = timezone.now()
    defaults = {
        "tenant": tenant,
        "title": title,
        "status": "active",
        "discount_percentage": Decimal("25.00"),
        "inventory_cap": 100,
        "units_sold": 5,
        "max_units_per_order": 2,
        "start_time": now - timezone.timedelta(hours=1),
        "end_time": now + timezone.timedelta(hours=23),
        "badge_label": "FLASH DEAL",
    }
    defaults.update(overrides)
    return FlashSale.objects.create(**defaults)


def _pricingpromotion_monitor(tenant, variant, competitor_name="Competitor Retail", **overrides):
    defaults = {
        "tenant": tenant,
        "competitor_name": competitor_name,
        "product": variant.product,
        "variant": variant,
        "competitor_url": "https://example-competitor.com/product/123",
        "competitor_price": Decimal("899.0000"),
        "competitor_currency": "USD",
        "is_in_stock": True,
        "match_strategy": "beat_by_fixed",
        "beat_by_value": Decimal("10.0000"),
        "min_margin_pct": Decimal("15.00"),
        "status": "active",
    }
    defaults.update(overrides)
    return CompetitorPriceMonitor.objects.create(**defaults)


@pytest.fixture
def ecom_rule_a(tenant_a):
    return _pricingpromotion_rule(tenant_a, name="Acme Storewide 10%")


@pytest.fixture
def ecom_rule_b(tenant_b):
    return _pricingpromotion_rule(tenant_b, name="Beta Storewide 15%", adjustment_value=Decimal("15.0000"))


@pytest.fixture
def ecom_coupon_a(tenant_a):
    return _pricingpromotion_coupon(tenant_a, code="ACMEPROMO")


@pytest.fixture
def ecom_coupon_b(tenant_b):
    return _pricingpromotion_coupon(tenant_b, code="BETAPROMO")


@pytest.fixture
def ecom_flash_sale_a(tenant_a, ecom_variant_a):
    return _pricingpromotion_flash_sale(tenant_a, title="Acme 24h Flash", variant=ecom_variant_a, product=ecom_variant_a.product)


@pytest.fixture
def ecom_flash_sale_b(tenant_b, ecom_variant_b):
    return _pricingpromotion_flash_sale(tenant_b, title="Beta 24h Flash", variant=ecom_variant_b, product=ecom_variant_b.product)


@pytest.fixture
def ecom_monitor_a(tenant_a, ecom_variant_a):
    return _pricingpromotion_monitor(tenant_a, ecom_variant_a, competitor_name="MegaStore A")


@pytest.fixture
def ecom_monitor_b(tenant_b, ecom_variant_b):
    return _pricingpromotion_monitor(tenant_b, ecom_variant_b, competitor_name="MegaStore B")


ORDERMANAGEMENT_PAGE_SIZE = 20

ORDERMANAGEMENT_MODEL_FIELDS = {
    "EcommerceOrder": (
        "id", "tenant", "number", "customer", "guest_email", "currency",
        "status", "payment_status", "fulfillment_status", "fraud_risk_level",
        "fraud_score", "address_verification_status", "inventory_reservation_status",
        "subtotal_amount", "discount_amount", "shipping_amount", "tax_amount",
        "total_amount", "applied_coupon", "shipping_address", "shipping_name",
        "shipping_address_line1", "shipping_city", "shipping_state",
        "shipping_postal_code", "shipping_country", "billing_address",
        "billing_name", "billing_address_line1", "billing_city", "billing_state",
        "billing_postal_code", "billing_country", "cancellation_reason",
        "cancelled_at", "customer_notes", "internal_notes", "created_at", "updated_at",
    ),
    "EcommerceOrderLine": (
        "id", "tenant", "order", "product", "variant", "sku", "product_name",
        "quantity", "fulfilled_quantity", "returned_quantity", "unit_price",
        "unit_discount", "line_total", "status", "created_at", "updated_at",
    ),
    "OrderRoutingRule": (
        "id", "tenant", "number", "name", "strategy", "priority",
        "destination_country", "destination_region", "preferred_fulfillment_center",
        "allow_split_shipment", "enable_dropship", "is_active", "description",
        "created_at", "updated_at",
    ),
    "OrderFulfillment": (
        "id", "tenant", "number", "order", "fulfillment_center", "carrier_name",
        "tracking_number", "tracking_url", "status", "shipping_cost",
        "shipped_at", "estimated_delivery_date", "actual_delivery_date",
        "shipping_label_url", "notification_sent", "notes", "created_at", "updated_at",
    ),
    "ReturnMerchandiseAuthorization": (
        "id", "tenant", "number", "order", "customer", "return_type", "status",
        "reason", "return_shipping_label_url", "return_tracking_number",
        "restocking_fee", "refund_amount", "refund_status", "restocking_status",
        "restocking_center", "customer_notes", "inspection_notes",
        "authorized_at", "completed_at", "created_at", "updated_at",
    ),
}

ORDERMANAGEMENT_CHOICES = {
    "EcommerceOrder": {
        "status": (
            ("draft", "Draft"),
            ("pending_validation", "Pending Validation"),
            ("validated", "Validated & Approved"),
            ("processing", "Processing / In Fulfillment"),
            ("partially_fulfilled", "Partially Fulfilled"),
            ("fulfilled", "Fulfilled"),
            ("cancelled", "Cancelled"),
            ("closed", "Closed"),
        ),
        "payment_status": (
            ("pending", "Pending Payment"),
            ("authorized", "Payment Authorized"),
            ("captured", "Payment Captured"),
            ("partially_refunded", "Partially Refunded"),
            ("refunded", "Fully Refunded"),
            ("failed", "Payment Failed"),
        ),
        "fulfillment_status": (
            ("unfulfilled", "Unfulfilled"),
            ("partially_fulfilled", "Partially Fulfilled"),
            ("fulfilled", "Fulfilled"),
            ("returned", "Returned"),
        ),
        "fraud_risk_level": (
            ("low", "Low Risk"),
            ("medium", "Medium Risk"),
            ("high", "High Risk"),
            ("flagged", "Fraud Flagged"),
        ),
        "address_verification_status": (
            ("unverified", "Unverified"),
            ("passed", "Address Verified (Passed)"),
            ("failed", "Verification Failed"),
            ("corrected", "Address Corrected"),
        ),
        "inventory_reservation_status": (
            ("none", "No Reservation"),
            ("reserved", "Stock Reserved"),
            ("allocated", "Stock Allocated to Node"),
            ("released", "Reservation Released"),
        ),
    },
    "EcommerceOrderLine": {
        "status": (
            ("pending", "Pending"),
            ("reserved", "Stock Reserved"),
            ("routing", "Routing to Fulfillment"),
            ("fulfilled", "Fulfilled"),
            ("cancelled", "Cancelled"),
            ("returned", "Returned"),
        ),
    },
    "OrderRoutingRule": {
        "strategy": (
            ("closest_location", "Closest Fulfillment Center"),
            ("fewest_splits", "Fewest Split Shipments"),
            ("highest_inventory", "Highest Stock Level"),
            ("drop_ship_preferred", "Drop-Ship Preferred"),
            ("manual", "Manual Assignment"),
        ),
    },
    "OrderFulfillment": {
        "status": (
            ("draft", "Draft / Sourced"),
            ("allocated", "Stock Allocated"),
            ("picking", "Picking Items"),
            ("packing", "Packing Package"),
            ("shipped", "Shipped with Carrier"),
            ("in_transit", "In Transit"),
            ("out_for_delivery", "Out for Delivery"),
            ("delivered", "Delivered to Customer"),
            ("failed_delivery", "Delivery Attempt Failed"),
        ),
    },
    "ReturnMerchandiseAuthorization": {
        "return_type": (
            ("refund", "Refund to Original Payment"),
            ("exchange", "Exchange for Alternate Variant"),
            ("store_credit", "Store Credit / Voucher"),
        ),
        "status": (
            ("requested", "Return Requested"),
            ("authorized", "Authorized & Label Issued"),
            ("label_generated", "Return Label Generated"),
            ("in_transit", "In Transit back to Center"),
            ("received", "Received at Center"),
            ("inspected", "Inspected & Evaluated"),
            ("approved", "Approved for Settlement"),
            ("rejected", "Rejected / Denied"),
            ("completed", "Completed & Settled"),
        ),
        "reason": (
            ("damaged_defective", "Damaged or Defective"),
            ("wrong_item_sent", "Wrong Item Sent"),
            ("size_fit_issue", "Size or Fit Issue"),
            ("not_as_described", "Item Not as Described"),
            ("changed_mind", "Customer Changed Mind"),
            ("late_delivery", "Late Delivery Arrival"),
            ("other", "Other Reason"),
        ),
        "refund_status": (
            ("pending", "Pending Approval"),
            ("processed", "Refund Processed"),
            ("failed", "Refund Failed"),
            ("waived", "Fee Waived / No Refund"),
        ),
        "restocking_status": (
            ("pending", "Pending Restock Inspection"),
            ("restocked", "Restocked to Active Inventory"),
            ("scrapped", "Damaged / Scrapped"),
            ("quarantined", "Quarantined for Review"),
        ),
    },
}

ORDERMANAGEMENT_FORM_FIELDS = {
    "EcommerceOrderForm": (
        "customer", "guest_email", "currency", "status", "payment_status",
        "fulfillment_status", "fraud_risk_level", "fraud_score",
        "address_verification_status", "inventory_reservation_status",
        "discount_amount", "shipping_amount", "tax_amount", "applied_coupon",
        "shipping_name", "shipping_address_line1", "shipping_city",
        "shipping_state", "shipping_postal_code", "shipping_country",
        "billing_name", "billing_address_line1", "billing_city",
        "billing_state", "billing_postal_code", "billing_country",
        "customer_notes", "internal_notes",
    ),
    "EcommerceOrderLineForm": (
        "product", "variant", "sku", "product_name", "quantity",
        "unit_price", "unit_discount", "status",
    ),
    "OrderRoutingRuleForm": (
        "name", "strategy", "priority", "destination_country",
        "destination_region", "preferred_fulfillment_center",
        "allow_split_shipment", "enable_dropship", "is_active", "description",
    ),
    "OrderFulfillmentForm": (
        "order", "fulfillment_center", "carrier_name", "tracking_number",
        "tracking_url", "status", "shipping_cost", "estimated_delivery_date",
        "shipping_label_url", "notification_sent", "notes",
    ),
    "ReturnMerchandiseAuthorizationForm": (
        "order", "customer", "return_type", "status", "reason",
        "return_shipping_label_url", "return_tracking_number",
        "restocking_fee", "refund_amount", "refund_status",
        "restocking_status", "restocking_center", "customer_notes",
        "inspection_notes",
    ),
}

ORDERMANAGEMENT_URLS = {
    "ecommerceorder_list": "orders/",
    "ecommerceorder_create": "orders/create/",
    "ecommerceorder_detail": "orders/<int:pk>/",
    "ecommerceorder_edit": "orders/<int:pk>/edit/",
    "ecommerceorder_delete": "orders/<int:pk>/delete/",
    "ecommerceorder_cancel": "orders/<int:pk>/cancel/",
    "orderroutingrule_list": "routing-rules/",
    "orderroutingrule_create": "routing-rules/create/",
    "orderroutingrule_detail": "routing-rules/<int:pk>/",
    "orderroutingrule_edit": "routing-rules/<int:pk>/edit/",
    "orderroutingrule_delete": "routing-rules/<int:pk>/delete/",
    "orderfulfillment_list": "fulfillments/",
    "orderfulfillment_create": "fulfillments/create/",
    "orderfulfillment_detail": "fulfillments/<int:pk>/",
    "orderfulfillment_edit": "fulfillments/<int:pk>/edit/",
    "orderfulfillment_delete": "fulfillments/<int:pk>/delete/",
    "orderfulfillment_ship": "fulfillments/<int:pk>/ship/",
    "returnmerchandiseauthorization_list": "returns/",
    "returnmerchandiseauthorization_create": "returns/create/",
    "returnmerchandiseauthorization_detail": "returns/<int:pk>/",
    "returnmerchandiseauthorization_edit": "returns/<int:pk>/edit/",
    "returnmerchandiseauthorization_delete": "returns/<int:pk>/delete/",
    "returnmerchandiseauthorization_complete": "returns/<int:pk>/complete/",
}


def _ordermanagement_customer(tenant, name="Customer One"):
    return Party.objects.create(tenant=tenant, name=name, kind="person")


def _ordermanagement_currency():
    curr, _ = Currency.objects.get_or_create(
        code="USD",
        defaults={"name": "US Dollar", "symbol": "$", "is_active": True},
    )
    return curr


def _ordermanagement_order(tenant, customer=None, currency=None, **overrides):
    if customer is None:
        customer = _ordermanagement_customer(tenant)
    if currency is None:
        currency = _ordermanagement_currency()
    defaults = {
        "tenant": tenant,
        "customer": customer,
        "currency": currency,
        "status": "pending_validation",
        "payment_status": "pending",
        "fulfillment_status": "unfulfilled",
        "shipping_name": "John Doe",
        "shipping_address_line1": "123 Main St",
        "shipping_city": "Austin",
        "shipping_state": "TX",
        "shipping_postal_code": "78701",
        "shipping_country": "USA",
        "subtotal_amount": Decimal("100.00"),
        "total_amount": Decimal("100.00"),
    }
    defaults.update(overrides)
    return EcommerceOrder.objects.create(**defaults)


def _ordermanagement_line(tenant, order, product, variant=None, **overrides):
    defaults = {
        "tenant": tenant,
        "order": order,
        "product": product,
        "variant": variant,
        "sku": variant.sku if variant else "SKU-DEFAULT",
        "product_name": product.name,
        "quantity": 1,
        "unit_price": Decimal("100.00"),
        "line_total": Decimal("100.00"),
        "status": "pending",
    }
    defaults.update(overrides)
    return EcommerceOrderLine.objects.create(**defaults)


def _ordermanagement_routing_rule(tenant, name="Rule Standard", **overrides):
    defaults = {
        "tenant": tenant,
        "name": name,
        "strategy": "closest_location",
        "priority": 10,
        "allow_split_shipment": True,
        "is_active": True,
    }
    defaults.update(overrides)
    return OrderRoutingRule.objects.create(**defaults)


def _ordermanagement_fulfillment(tenant, order, fulfillment_center=None, **overrides):
    defaults = {
        "tenant": tenant,
        "order": order,
        "fulfillment_center": fulfillment_center,
        "carrier_name": "FedEx Ground",
        "tracking_number": "1234567890",
        "status": "allocated",
        "shipping_cost": Decimal("15.00"),
    }
    defaults.update(overrides)
    return OrderFulfillment.objects.create(**defaults)


def _ordermanagement_rma(tenant, order, customer=None, **overrides):
    if customer is None:
        customer = order.customer
    defaults = {
        "tenant": tenant,
        "order": order,
        "customer": customer,
        "return_type": "refund",
        "status": "requested",
        "reason": "changed_mind",
        "refund_amount": Decimal("50.00"),
        "restocking_fee": Decimal("5.00"),
        "refund_status": "pending",
        "restocking_status": "pending",
    }
    defaults.update(overrides)
    return ReturnMerchandiseAuthorization.objects.create(**defaults)


@pytest.fixture
def ecom_customer_a(tenant_a):
    return _ordermanagement_customer(tenant_a, name="Acme Customer A")


@pytest.fixture
def ecom_customer_b(tenant_b):
    return _ordermanagement_customer(tenant_b, name="Beta Customer B")


@pytest.fixture
def ecom_currency_usd():
    return _ordermanagement_currency()


@pytest.fixture
def ecom_order_a(tenant_a, ecom_customer_a, ecom_currency_usd):
    return _ordermanagement_order(tenant_a, customer=ecom_customer_a, currency=ecom_currency_usd)


@pytest.fixture
def ecom_order_b(tenant_b, ecom_customer_b, ecom_currency_usd):
    return _ordermanagement_order(tenant_b, customer=ecom_customer_b, currency=ecom_currency_usd)


@pytest.fixture
def ecom_order_line_a(tenant_a, ecom_order_a, ecom_product_a, ecom_variant_a):
    return _ordermanagement_line(tenant_a, ecom_order_a, ecom_product_a, ecom_variant_a)


@pytest.fixture
def ecom_order_line_b(tenant_b, ecom_order_b, ecom_product_b, ecom_variant_b):
    return _ordermanagement_line(tenant_b, ecom_order_b, ecom_product_b, ecom_variant_b)


@pytest.fixture
def ecom_routing_rule_a(tenant_a, ecom_center_a):
    return _ordermanagement_routing_rule(tenant_a, name="Acme Fast Route", preferred_fulfillment_center=ecom_center_a)


@pytest.fixture
def ecom_routing_rule_b(tenant_b, ecom_center_b):
    return _ordermanagement_routing_rule(tenant_b, name="Beta Fast Route", preferred_fulfillment_center=ecom_center_b)


@pytest.fixture
def ecom_fulfillment_a(tenant_a, ecom_order_a, ecom_center_a):
    return _ordermanagement_fulfillment(tenant_a, ecom_order_a, fulfillment_center=ecom_center_a)


@pytest.fixture
def ecom_fulfillment_b(tenant_b, ecom_order_b, ecom_center_b):
    return _ordermanagement_fulfillment(tenant_b, ecom_order_b, fulfillment_center=ecom_center_b)


@pytest.fixture
def ecom_rma_a(tenant_a, ecom_order_a, ecom_customer_a, ecom_center_a):
    return _ordermanagement_rma(tenant_a, ecom_order_a, customer=ecom_customer_a, restocking_center=ecom_center_a)


@pytest.fixture
def ecom_rma_b(tenant_b, ecom_order_b, ecom_customer_b, ecom_center_b):
    return _ordermanagement_rma(tenant_b, ecom_order_b, customer=ecom_customer_b, restocking_center=ecom_center_b)


