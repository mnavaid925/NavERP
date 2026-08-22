"""Inventory admin registrations.

Stays a flat module at the app root (per the Backend Package Structure rule); the models import
works because apps/inventory/models/__init__.py re-exports everything.
"""
from django.contrib import admin

from apps.inventory.models import (
    BinCapacity,
    CrossDockOrder,
    InventoryReservation,
    ItemAttribute,
    ItemPrice,
    ProductFile,
    PurchaseOrderApproval,
    PurchaseOrderApprovalRule,
    PurchaseOrderDispatch,
    PutawayRule,
    StockStatus,
    VendorCommunication,
)


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


@admin.register(PurchaseOrderApprovalRule)
class PurchaseOrderApprovalRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "min_amount", "max_amount", "org_unit", "tier_count", "is_active")
    list_filter = ("tenant", "is_active")
    search_fields = ("name",)


@admin.register(PurchaseOrderApproval)
class PurchaseOrderApprovalAdmin(admin.ModelAdmin):
    list_display = ("number", "purchase_order", "tier", "decision", "decided_by",
                    "decided_at", "rule")
    list_filter = ("tenant", "decision")
    search_fields = ("number", "purchase_order__number", "note")


@admin.register(PurchaseOrderDispatch)
class PurchaseOrderDispatchAdmin(admin.ModelAdmin):
    list_display = ("number", "purchase_order", "channel", "recipient", "reference",
                    "dispatched_at")
    list_filter = ("tenant", "channel")
    search_fields = ("number", "purchase_order__number", "recipient", "reference")
    date_hierarchy = "dispatched_at"


@admin.register(BinCapacity)
class BinCapacityAdmin(admin.ModelAdmin):
    list_display = ("location", "max_weight_kg", "max_volume_m3", "max_quantity", "notes")
    list_filter = ("tenant",)
    search_fields = ("location__code", "location__name", "notes")


@admin.register(CrossDockOrder)
class CrossDockOrderAdmin(admin.ModelAdmin):
    list_display = ("number", "item", "dock_location", "quantity", "scheduled_date", "status")
    list_filter = ("tenant", "status")
    search_fields = ("number", "item__sku", "item__name", "inbound_reference",
                     "outbound_reference")


@admin.register(PutawayRule)
class PutawayRuleAdmin(admin.ModelAdmin):
    list_display = ("item", "category", "source_location", "destination", "priority",
                    "is_active")
    list_filter = ("tenant", "is_active")
    search_fields = ("item__sku", "item__name", "destination__code")


@admin.register(StockStatus)
class StockStatusAdmin(admin.ModelAdmin):
    list_display = ("item", "location", "lot_serial", "status", "quantity", "effective_at")
    list_filter = ("tenant", "status")
    search_fields = ("item__sku", "item__name", "reason")


@admin.register(InventoryReservation)
class InventoryReservationAdmin(admin.ModelAdmin):
    list_display = ("number", "item", "location", "purpose", "reference", "quantity",
                    "status", "reserved_by", "resolved_at")
    list_filter = ("tenant", "status", "purpose")
    search_fields = ("number", "reference", "item__sku", "item__name", "notes")
