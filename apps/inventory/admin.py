"""Inventory admin registrations.

Stays a flat module at the app root (per the Backend Package Structure rule); the models import
works because apps/inventory/models/__init__.py re-exports everything.
"""
from django.contrib import admin

from apps.inventory.models import ItemAttribute, ItemPrice, ProductFile, VendorCommunication


@admin.register(ItemAttribute)
class ItemAttributeAdmin(admin.ModelAdmin):
    list_display = ("item", "name", "value", "unit", "sequence")
    search_fields = ("item__sku", "item__name", "name", "value")
    list_filter = ("tenant",)


@admin.register(ItemPrice)
class ItemPriceAdmin(admin.ModelAdmin):
    list_display = ("item", "price_type", "unit_price", "currency", "min_quantity",
                    "valid_from", "valid_until", "is_active")
    list_filter = ("tenant", "price_type", "is_active")
    search_fields = ("item__sku", "item__name")


@admin.register(ProductFile)
class ProductFileAdmin(admin.ModelAdmin):
    list_display = ("item", "title", "kind", "is_primary", "created_at")
    list_filter = ("tenant", "kind", "is_primary")
    search_fields = ("item__sku", "item__name", "title")


@admin.register(VendorCommunication)
class VendorCommunicationAdmin(admin.ModelAdmin):
    list_display = ("number", "party", "channel", "direction", "subject", "occurred_at",
                    "follow_up_on")
    list_filter = ("tenant", "channel", "direction")
    search_fields = ("number", "subject", "body", "party__name")
    date_hierarchy = "occurred_at"
