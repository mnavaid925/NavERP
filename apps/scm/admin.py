"""SCM admin registrations.

Stays a flat module at the app root (per the Backend Package Structure rule); the models import
works because apps/scm/models/__init__.py re-exports everything.
"""
from django.contrib import admin

from apps.scm.models import (
    GoodsReceiptLine,
    GoodsReceiptNote,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequisition,
    PurchaseRequisitionLine,
    RFQ,
    RFQLine,
    RFQQuote,
    RFQQuoteLine,
    RFQVendor,
    SalesOrder,
    SalesOrderAllocation,
    SalesOrderLine,
    SupplierCatalog,
    SupplierCatalogItem,
    SupplierContract,
    SupplierProfile,
    SupplierRiskAssessment,
    SupplierScorecard,
)


class PurchaseRequisitionLineInline(admin.TabularInline):
    model = PurchaseRequisitionLine
    extra = 0


@admin.register(PurchaseRequisition)
class PurchaseRequisitionAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "tenant", "status", "estimated_total", "required_by")
    list_filter = ("tenant", "status")
    search_fields = ("number", "title")
    inlines = [PurchaseRequisitionLineInline]


class RFQLineInline(admin.TabularInline):
    model = RFQLine
    extra = 0


class RFQVendorInline(admin.TabularInline):
    model = RFQVendor
    extra = 0


@admin.register(RFQ)
class RFQAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "tenant", "status", "issue_date", "response_due")
    list_filter = ("tenant", "status")
    search_fields = ("number", "title")
    inlines = [RFQLineInline, RFQVendorInline]


class RFQQuoteLineInline(admin.TabularInline):
    model = RFQQuoteLine
    extra = 0


@admin.register(RFQQuote)
class RFQQuoteAdmin(admin.ModelAdmin):
    list_display = ("number", "rfq", "party", "tenant", "status", "total", "lead_time_days")
    list_filter = ("tenant", "status")
    search_fields = ("number", "vendor_reference", "party__name")
    inlines = [RFQQuoteLineInline]


class PurchaseOrderLineInline(admin.TabularInline):
    model = PurchaseOrderLine
    extra = 0


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ("number", "vendor", "tenant", "status", "total", "order_date", "version")
    list_filter = ("tenant", "status")
    search_fields = ("number", "vendor__name")
    inlines = [PurchaseOrderLineInline]


class GoodsReceiptLineInline(admin.TabularInline):
    model = GoodsReceiptLine
    extra = 0


@admin.register(GoodsReceiptNote)
class GoodsReceiptNoteAdmin(admin.ModelAdmin):
    list_display = ("number", "purchase_order", "tenant", "status", "match_status", "receipt_date")
    list_filter = ("tenant", "status", "match_status")
    search_fields = ("number", "delivery_note_ref", "purchase_order__number")
    inlines = [GoodsReceiptLineInline]


# ============================================================ 4.2 Supplier Relationship Management
@admin.register(SupplierProfile)
class SupplierProfileAdmin(admin.ModelAdmin):
    list_display = ("party", "tenant", "onboarding_status", "tier", "category")
    list_filter = ("tenant", "onboarding_status", "tier")
    search_fields = ("party__name", "legal_name", "category")


@admin.register(SupplierScorecard)
class SupplierScorecardAdmin(admin.ModelAdmin):
    list_display = ("number", "party", "tenant", "status", "overall_score", "grade", "period_end")
    list_filter = ("tenant", "status")
    search_fields = ("number", "party__name")


@admin.register(SupplierContract)
class SupplierContractAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "party", "tenant", "status", "end_date")
    list_filter = ("tenant", "status", "contract_type")
    search_fields = ("number", "title", "party__name")


class SupplierCatalogItemInline(admin.TabularInline):
    model = SupplierCatalogItem
    extra = 0


@admin.register(SupplierCatalog)
class SupplierCatalogAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "party", "tenant", "status", "valid_until")
    list_filter = ("tenant", "status")
    search_fields = ("number", "name", "party__name")
    inlines = [SupplierCatalogItemInline]


@admin.register(SupplierRiskAssessment)
class SupplierRiskAssessmentAdmin(admin.ModelAdmin):
    list_display = ("number", "party", "tenant", "status", "risk_level", "assessment_date")
    list_filter = ("tenant", "status", "risk_level")
    search_fields = ("number", "party__name")


# ============================================================ 4.3 Inventory Management
from apps.scm.models import (  # noqa: E402
    Item, ItemCategory, UOM, Location, LotSerial, StockMove,
    StockTransfer, StockTransferLine, StockAdjustment, StockAdjustmentLine, ReorderRule,
)


@admin.register(ItemCategory)
class ItemCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "parent", "is_active")
    list_filter = ("tenant", "is_active")
    search_fields = ("name",)


@admin.register(UOM)
class UOMAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "tenant", "factor", "is_active")
    list_filter = ("tenant", "is_active")
    search_fields = ("code", "name")


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "tenant", "item_type", "tracking", "costing_method", "average_cost")
    list_filter = ("tenant", "item_type", "tracking", "costing_method", "is_active")
    search_fields = ("sku", "name")
    readonly_fields = ("average_cost",)


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "tenant", "location_type", "parent", "is_active")
    list_filter = ("tenant", "location_type", "is_active")
    search_fields = ("code", "name")


@admin.register(LotSerial)
class LotSerialAdmin(admin.ModelAdmin):
    list_display = ("number", "item", "tenant", "kind", "status", "expiry_date")
    list_filter = ("tenant", "kind", "status")
    search_fields = ("number", "item__sku")


@admin.register(StockMove)
class StockMoveAdmin(admin.ModelAdmin):
    # Append-only ledger — read-only in the admin, no add/change/delete.
    list_display = ("item", "location", "tenant", "quantity", "unit_cost", "move_type", "reference", "moved_at")
    list_filter = ("tenant", "move_type")
    search_fields = ("reference", "item__sku", "location__code")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class StockTransferLineInline(admin.TabularInline):
    model = StockTransferLine
    extra = 0


@admin.register(StockTransfer)
class StockTransferAdmin(admin.ModelAdmin):
    list_display = ("number", "tenant", "from_location", "to_location", "status", "transfer_date")
    list_filter = ("tenant", "status")
    search_fields = ("number",)
    inlines = [StockTransferLineInline]


class StockAdjustmentLineInline(admin.TabularInline):
    model = StockAdjustmentLine
    extra = 0


@admin.register(StockAdjustment)
class StockAdjustmentAdmin(admin.ModelAdmin):
    list_display = ("number", "tenant", "location", "reason", "status", "adjustment_date")
    list_filter = ("tenant", "status", "reason")
    search_fields = ("number",)
    inlines = [StockAdjustmentLineInline]


@admin.register(ReorderRule)
class ReorderRuleAdmin(admin.ModelAdmin):
    list_display = ("item", "location", "tenant", "reorder_point", "safety_stock", "is_active")
    list_filter = ("tenant", "is_active")
    search_fields = ("item__sku", "location__code")


# ============================================================ 4.4 Warehouse Management
from apps.scm.models import (  # noqa: E402
    PutawayTask, PickTask, PickTaskLine, CycleCountTask, CycleCountTaskLine, YardVisit,
)


@admin.register(PutawayTask)
class PutawayTaskAdmin(admin.ModelAdmin):
    list_display = ("number", "item", "tenant", "from_location", "to_location", "quantity", "status")
    list_filter = ("tenant", "status", "strategy")
    search_fields = ("number", "item__sku", "to_location__code")


class PickTaskLineInline(admin.TabularInline):
    model = PickTaskLine
    extra = 0


@admin.register(PickTask)
class PickTaskAdmin(admin.ModelAdmin):
    list_display = ("number", "tenant", "strategy", "status", "zone", "wave_ref")
    list_filter = ("tenant", "status", "strategy")
    search_fields = ("number", "wave_ref", "ship_to")
    inlines = [PickTaskLineInline]


class CycleCountTaskLineInline(admin.TabularInline):
    model = CycleCountTaskLine
    extra = 0
    # expected_quantity is a server-side snapshot — never hand-editable, even here.
    readonly_fields = ("expected_quantity",)


@admin.register(CycleCountTask)
class CycleCountTaskAdmin(admin.ModelAdmin):
    list_display = ("number", "location", "tenant", "scheduled_date", "status", "adjustment")
    list_filter = ("tenant", "status", "count_method")
    search_fields = ("number", "location__code")
    inlines = [CycleCountTaskLineInline]


@admin.register(YardVisit)
class YardVisitAdmin(admin.ModelAdmin):
    list_display = ("number", "carrier_name", "tenant", "direction", "status", "dock_door")
    list_filter = ("tenant", "status", "direction")
    search_fields = ("number", "carrier_name", "vehicle_ref", "trailer_ref")


# ============================================================ 4.5 Order Management System (OMS)
class SalesOrderLineInline(admin.TabularInline):
    model = SalesOrderLine
    extra = 0


@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = ("number", "customer", "tenant", "status", "total", "order_date")
    list_filter = ("tenant", "status", "source_channel")
    search_fields = ("number", "customer__name")
    inlines = [SalesOrderLineInline]


@admin.register(SalesOrderAllocation)
class SalesOrderAllocationAdmin(admin.ModelAdmin):
    list_display = ("sales_order_line", "location", "tenant", "quantity", "status", "allocated_at")
    list_filter = ("tenant", "status")
    search_fields = ("sales_order_line__sales_order__number", "sales_order_line__item__sku")


# ============================================================ 4.6 Transportation Management System (TMS)
from apps.scm.models import (  # noqa: E402
    Carrier, CarrierRateCard, Load, LoadStop, Shipment, TrackingEvent,
    FreightInvoice, FreightInvoiceLine,
)


class CarrierRateCardInline(admin.TabularInline):
    model = CarrierRateCard
    extra = 0


@admin.register(Carrier)
class CarrierAdmin(admin.ModelAdmin):
    list_display = ("number", "party", "tenant", "carrier_type", "primary_mode", "status",
                    "on_time_delivery_pct")
    list_filter = ("tenant", "status", "carrier_type", "primary_mode")
    search_fields = ("number", "party__name", "scac_code", "mc_number")
    readonly_fields = ("on_time_delivery_pct", "performance_summary")
    inlines = [CarrierRateCardInline]


class LoadStopInline(admin.TabularInline):
    model = LoadStop
    extra = 0


@admin.register(Load)
class LoadAdmin(admin.ModelAdmin):
    list_display = ("number", "carrier", "tenant", "mode", "equipment_type", "status", "planned_departure")
    list_filter = ("tenant", "status", "mode", "equipment_type")
    search_fields = ("number", "origin_text", "destination_text", "driver_name", "vehicle_ref")
    inlines = [LoadStopInline]


class TrackingEventInline(admin.TabularInline):
    model = TrackingEvent
    extra = 0
    readonly_fields = ("recorded_by",)


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ("number", "carrier", "tenant", "direction", "status", "planned_delivery_date",
                    "pod_received")
    list_filter = ("tenant", "status", "direction", "mode")
    search_fields = ("number", "carrier_tracking_number", "carrier__party__name")
    readonly_fields = ("current_status_text", "last_known_location", "eta", "actual_pickup_at",
                       "actual_delivery_at", "pod_received", "pod_received_at")
    inlines = [TrackingEventInline]


class FreightInvoiceLineInline(admin.TabularInline):
    model = FreightInvoiceLine
    extra = 0


@admin.register(FreightInvoice)
class FreightInvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "carrier", "tenant", "billed_amount", "variance_amount",
                    "match_status", "approval_status")
    list_filter = ("tenant", "match_status", "approval_status")
    search_fields = ("number", "carrier_invoice_number", "carrier__party__name")
    readonly_fields = ("billed_amount", "contract_amount", "variance_amount", "variance_pct",
                       "match_status", "approval_status", "approved_by", "approved_at", "bill")
    inlines = [FreightInvoiceLineInline]
