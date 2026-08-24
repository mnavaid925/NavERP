"""Inventory admin registrations.

Stays a flat module at the app root (per the Backend Package Structure rule); the models import
works because apps/inventory/models/__init__.py re-exports everything.
"""
from django.contrib import admin

from apps.inventory.models import (
    BarcodeLabel,
    BinCapacity,
    StockLevelPlan,
    CountProgram,
    CrossDockOrder,
    FulfillmentWave,
    FulfillmentWaveOrder,
    GLPostRule,
    InventoryReservation,
    ItemAttribute,
    ItemPrice,
    JournalSyncLog,
    LocationNetwork,
    LotNumberRule,
    ProductFile,
    PurchaseOrderApproval,
    PurchaseOrderApprovalRule,
    PurchaseOrderDispatch,
    PhysicalInventory,
    PutawayRule,
    ReturnInspection,
    ReturnInspectionChecklist,
    DispositionRoutingRule,
    ShelfLifePolicy,
    TaxRule,
    StockStatus,
    VendorCommunication,
    ScanEvent,
    ScanSession,
    RfidTag,
    TransferApproval,
    TransferApprovalRule,
    TransferRoute,
    AlertRule,
    InventoryAlert,
    NotificationDelivery,
    QcChecklist,
    QcChecklistItem,
    QcRoutingRule,
    QuarantineOrder,
    DefectReport,
    InventoryReportSnapshot,
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


@admin.register(FulfillmentWave)
class FulfillmentWaveAdmin(admin.ModelAdmin):
    list_display = ("number", "status", "location", "carrier", "ship_method",
                    "planned_ship_date", "priority")
    list_filter = ("tenant", "status")
    search_fields = ("number", "description", "criteria_text")


@admin.register(FulfillmentWaveOrder)
class FulfillmentWaveOrderAdmin(admin.ModelAdmin):
    list_display = ("wave", "sales_order", "added_by", "created_at")
    list_filter = ("tenant",)
    search_fields = ("wave__number", "sales_order__number")


@admin.register(LocationNetwork)
class LocationNetworkAdmin(admin.ModelAdmin):
    list_display = ("number", "code", "name", "node_type", "parent", "warehouse", "is_active")
    list_filter = ("tenant", "node_type", "is_active")
    search_fields = ("number", "code", "name")


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


@admin.register(TransferRoute)
class TransferRouteAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "mode", "origin_location", "destination_location",
                    "default_transit_days", "is_active")
    list_filter = ("tenant", "mode", "is_active")
    search_fields = ("name", "code")


@admin.register(TransferApprovalRule)
class TransferApprovalRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "applies_to", "min_units", "max_units", "tier_count", "is_active")
    list_filter = ("tenant", "applies_to", "is_active")
    search_fields = ("name",)


@admin.register(TransferApproval)
class TransferApprovalAdmin(admin.ModelAdmin):
    list_display = ("number", "transfer", "tier", "decision", "rule", "decided_by",
                    "decided_at")
    list_filter = ("tenant", "decision")
    search_fields = ("number", "transfer__number")


@admin.register(StockLevelPlan)
class StockLevelPlanAdmin(admin.ModelAdmin):
    list_display = ("number", "item", "location", "seasonal_profile",
                    "base_target_qty", "effective_from", "status")
    list_filter = ("tenant", "status")
    search_fields = ("number", "item__sku", "item__name")


@admin.register(CountProgram)
class CountProgramAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "location", "frequency", "abc_class",
                    "count_method", "is_active", "last_run_date")
    list_filter = ("tenant", "frequency", "is_active")
    search_fields = ("number", "name")


@admin.register(PhysicalInventory)
class PhysicalInventoryAdmin(admin.ModelAdmin):
    list_display = ("number", "warehouse", "scheduled_date", "status",
                    "is_frozen", "requested_by")
    list_filter = ("tenant", "status", "is_frozen")
    search_fields = ("number", "warehouse__code")


@admin.register(LotNumberRule)
class LotNumberRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "item", "kind", "prefix", "include_date",
                    "sequence_padding", "is_active")
    list_filter = ("tenant", "kind", "is_active")
    search_fields = ("name", "prefix", "item__sku", "item__name")


@admin.register(ShelfLifePolicy)
class ShelfLifePolicyAdmin(admin.ModelAdmin):
    list_display = ("item", "shelf_life_days", "min_remaining_days", "warning_days",
                    "fefo_enforced")
    list_filter = ("tenant", "fefo_enforced")
    search_fields = ("item__sku", "item__name")


class ReturnInspectionChecklistInline(admin.TabularInline):
    model = ReturnInspectionChecklist
    extra = 1


@admin.register(ReturnInspection)
class ReturnInspectionAdmin(admin.ModelAdmin):
    list_display = ("number", "return_authorization", "item", "quantity", "condition_grade",
                    "functional_status", "status", "inspected_at")
    list_filter = ("tenant", "status", "condition_grade", "functional_status")
    search_fields = ("number", "return_authorization__number", "item__sku", "item__name", "findings")
    inlines = [ReturnInspectionChecklistInline]


@admin.register(DispositionRoutingRule)
class DispositionRoutingRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "item", "category", "condition_grade", "suggested_disposition",
                    "destination_location", "priority", "is_active")
    list_filter = ("tenant", "is_active", "condition_grade", "suggested_disposition")
    search_fields = ("name", "item__sku", "item__name", "notes")


class ScanEventInline(admin.TabularInline):
    model = ScanEvent
    extra = 0
    can_delete = False


@admin.register(BarcodeLabel)
class BarcodeLabelAdmin(admin.ModelAdmin):
    list_display = ('number', 'label_kind', 'target_type', 'payload', 'symbology',
                    'copies', 'status', 'printed_at')
    list_filter = ('tenant', 'status', 'symbology', 'label_kind')
    search_fields = ('number', 'payload', 'target_ref', 'pallet_ref', 'item__sku')


@admin.register(ScanSession)
class ScanSessionAdmin(admin.ModelAdmin):
    list_display = ('number', 'device_label', 'mode', 'status', 'started_at', 'ended_at')
    list_filter = ('tenant', 'status', 'mode')
    search_fields = ('number', 'device_label', 'notes')
    inlines = [ScanEventInline]


@admin.register(RfidTag)
class RfidTagAdmin(admin.ModelAdmin):
    list_display = ('epc', 'kind', 'status', 'item', 'location', 'lot_serial',
                    'last_seen_at', 'last_seen_location')
    list_filter = ('tenant', 'status', 'kind')
    search_fields = ('epc', 'target_ref', 'pallet_ref', 'item__sku')


@admin.register(AlertRule)
class AlertRuleAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "alert_type", "severity", "item", "location",
                    "cooldown_days", "is_active")
    list_filter = ("tenant", "alert_type", "severity", "is_active")
    search_fields = ("number", "name", "email_recipients", "item__sku", "location__code")


@admin.register(InventoryAlert)
class InventoryAlertAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "alert_type", "severity", "status",
                    "metric_value", "raised_at")
    list_filter = ("tenant", "status", "severity", "alert_type")
    search_fields = ("number", "title", "message", "dedup_key")


@admin.register(NotificationDelivery)
class NotificationDeliveryAdmin(admin.ModelAdmin):
    list_display = ("alert", "channel", "recipient", "status", "created_at")
    list_filter = ("tenant", "channel", "status")
    search_fields = ("recipient", "detail", "alert__number")


@admin.register(QcChecklist)
class QcChecklistAdmin(admin.ModelAdmin):
    list_display = ("name", "item", "vendor", "is_active", "created_at")
    list_filter = ("tenant", "is_active")
    search_fields = ("name", "item__sku", "vendor__name")


@admin.register(QcChecklistItem)
class QcChecklistItemAdmin(admin.ModelAdmin):
    list_display = ("checklist", "label", "kind", "is_mandatory", "sequence")
    list_filter = ("tenant", "kind", "is_mandatory")
    search_fields = ("label", "checklist__name")


@admin.register(QcRoutingRule)
class QcRoutingRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "item", "category", "vendor", "verdict",
                    "qc_location", "priority", "is_active")
    list_filter = ("tenant", "verdict", "is_active")
    search_fields = ("name", "notes", "item__sku")


@admin.register(QuarantineOrder)
class QuarantineOrderAdmin(admin.ModelAdmin):
    list_display = ("number", "item", "quantity", "source_location",
                    "quarantine_location", "reason", "status")
    list_filter = ("tenant", "status", "reason")
    search_fields = ("number", "reference", "item__sku")
    readonly_fields = ("number", "quarantined_at", "resolved_at")


@admin.register(DefectReport)
class DefectReportAdmin(admin.ModelAdmin):
    list_display = ("number", "item", "quantity", "defect_type", "severity",
                    "discovered_during", "reported_on", "status")
    list_filter = ("tenant", "status", "severity", "defect_type")
    search_fields = ("number", "description", "item__sku")
    readonly_fields = ("number", "resolved_at")


@admin.register(InventoryReportSnapshot)
class InventoryReportSnapshotAdmin(admin.ModelAdmin):
    list_display = ("number", "report_type", "title", "location",
                    "window_days", "generated_by", "created_at")
    list_filter = ("tenant", "report_type", "created_at")
    search_fields = ("number", "title", "notes")
    readonly_fields = ("number", "summary")


@admin.register(TaxRule)
class TaxRuleAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "item", "category", "country",
                    "tax_code", "priority", "is_active")
    list_filter = ("tenant", "is_active", "tax_code")
    search_fields = ("name", "country", "notes", "item__sku", "category__name")


@admin.register(GLPostRule)
class GLPostRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "event_type", "inventory_account", "offset_account", "is_active")
    list_filter = ("tenant", "event_type", "is_active")
    search_fields = ("name", "notes")


@admin.register(JournalSyncLog)
class JournalSyncLogAdmin(admin.ModelAdmin):
    list_display = ("number", "source_kind", "stock_adjustment", "date_from", "date_to",
                    "moves_count", "total_value", "journal_entry", "posted_at")
    list_filter = ("tenant", "source_kind", "posted_at")
    readonly_fields = ("number", "journal_entry", "posted_by", "posted_at")
