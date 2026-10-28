from django.contrib import admin

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
