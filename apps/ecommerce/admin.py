from django.contrib import admin

from apps.ecommerce.models.InventoryStock.BackorderPolicies import BackorderPolicy
from apps.ecommerce.models.InventoryStock.ChannelInventorySyncs import ChannelInventorySync
from apps.ecommerce.models.InventoryStock.FulfillmentCenters import FulfillmentCenter
from apps.ecommerce.models.InventoryStock.InventoryAllocations import InventoryAllocation
from apps.ecommerce.models.PricingPromotion.CompetitorPriceMonitors import CompetitorPriceMonitor
from apps.ecommerce.models.PricingPromotion.CouponPromotions import CouponPromotion
from apps.ecommerce.models.PricingPromotion.DynamicPriceRules import DynamicPriceRule
from apps.ecommerce.models.PricingPromotion.FlashSales import FlashSale
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ProductCatalog.ProductRelationships import ProductRelationship
from apps.ecommerce.models.ProductCatalog.ProductVariants import ProductVariant
from apps.ecommerce.models.ProductCatalog.StoreCategories import StoreCategory


@admin.register(StoreCategory)
class StoreCategoryAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "slug", "parent", "display_order", "is_active", "include_in_menu"]
    list_filter = ["is_active", "include_in_menu", "tenant"]
    search_fields = ["name", "slug", "number", "description"]
    ordering = ["tenant", "display_order", "name"]


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = ["sku", "name", "price", "compare_at_price", "is_active", "sort_order"]


@admin.register(CatalogProduct)
class CatalogProductAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "brand", "primary_category", "status", "visibility", "pim_completeness", "is_featured", "created_at"]
    list_filter = ["status", "visibility", "is_featured", "is_digital", "tenant"]
    search_fields = ["name", "slug", "number", "brand", "short_description"]
    ordering = ["-created_at"]
    inlines = [ProductVariantInline]


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ["number", "sku", "product", "name", "price", "compare_at_price", "is_active", "sort_order"]
    list_filter = ["is_active", "tenant"]
    search_fields = ["sku", "name", "number", "barcode", "product__name"]
    ordering = ["product", "sort_order", "sku"]


@admin.register(ProductRelationship)
class ProductRelationshipAdmin(admin.ModelAdmin):
    list_display = ["number", "source_product", "relationship_type", "target_product", "discount_pct", "is_active", "sort_order"]
    list_filter = ["relationship_type", "is_active", "tenant"]
    search_fields = ["number", "source_product__name", "target_product__name", "notes"]
    ordering = ["source_product", "sort_order"]


@admin.register(FulfillmentCenter)
class FulfillmentCenterAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "code", "center_type", "priority", "city", "state", "is_active"]
    list_filter = ["center_type", "is_active", "tenant"]
    search_fields = ["name", "code", "city", "state", "number"]
    ordering = ["priority", "name"]


@admin.register(InventoryAllocation)
class InventoryAllocationAdmin(admin.ModelAdmin):
    list_display = ["number", "variant", "fulfillment_center", "zone_bin", "quantity_on_hand", "quantity_allocated", "safety_stock_buffer", "available_to_promise", "is_low_stock_alert"]
    list_filter = ["is_low_stock_alert", "fulfillment_center", "tenant"]
    search_fields = ["number", "variant__sku", "variant__name", "fulfillment_center__name", "zone_bin"]
    ordering = ["variant__sku", "fulfillment_center"]


@admin.register(BackorderPolicy)
class BackorderPolicyAdmin(admin.ModelAdmin):
    list_display = ["number", "variant", "policy_type", "expected_availability_date", "current_backorder_count", "max_backorder_quantity", "is_active"]
    list_filter = ["policy_type", "is_active", "tenant"]
    search_fields = ["number", "variant__sku", "variant__name", "storefront_message"]
    ordering = ["variant__sku"]


@admin.register(ChannelInventorySync)
class ChannelInventorySyncAdmin(admin.ModelAdmin):
    list_display = ["number", "channel_name", "channel_type", "variant", "fulfillment_center", "last_synced_quantity", "sync_status", "last_synced_at"]
    list_filter = ["channel_type", "sync_status", "sync_mode", "tenant"]
    search_fields = ["number", "channel_name", "variant__sku", "variant__name"]
    ordering = ["variant__sku", "channel_type"]


@admin.register(DynamicPriceRule)
class DynamicPriceRuleAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "rule_type", "adjustment_value", "scope", "customer_segment", "priority", "is_active", "valid_from", "valid_to"]
    list_filter = ["rule_type", "scope", "customer_segment", "loyalty_tier", "is_active", "tenant"]
    search_fields = ["name", "number", "description"]
    ordering = ["-priority", "-created_at"]


@admin.register(CouponPromotion)
class CouponPromotionAdmin(admin.ModelAdmin):
    list_display = ["number", "code", "name", "discount_type", "discount_value", "min_spend", "used_count", "usage_limit_total", "is_active"]
    list_filter = ["discount_type", "is_stackable", "loyalty_tier_required", "is_active", "tenant"]
    search_fields = ["code", "name", "number"]
    ordering = ["-created_at"]


@admin.register(FlashSale)
class FlashSaleAdmin(admin.ModelAdmin):
    list_display = ["number", "title", "status", "discount_percentage", "flash_price", "inventory_cap", "units_sold", "start_time", "end_time"]
    list_filter = ["status", "tenant"]
    search_fields = ["title", "number", "badge_label"]
    ordering = ["-start_time"]


@admin.register(CompetitorPriceMonitor)
class CompetitorPriceMonitorAdmin(admin.ModelAdmin):
    list_display = ["number", "competitor_name", "variant", "competitor_price", "match_strategy", "min_margin_pct", "is_in_stock", "status", "last_scraped_at"]
    list_filter = ["match_strategy", "status", "is_in_stock", "tenant"]
    search_fields = ["competitor_name", "number", "variant__sku"]
    ordering = ["-last_scraped_at", "-created_at"]

