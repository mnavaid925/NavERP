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
    list_display = ("item", "location", "tenant", "reorder_point", "safety_stock",
                    "safety_stock_method", "computed_safety_stock", "is_active")
    list_filter = ("tenant", "is_active", "safety_stock_method", "abc_class", "xyz_class")
    search_fields = ("item__sku", "location__code")
    # The 4.7 calculated set — produced by calculate(), promoted only by the explicit apply action.
    readonly_fields = ("avg_daily_demand", "demand_std_dev", "abc_class", "xyz_class",
                       "computed_safety_stock", "computed_reorder_point", "last_calculated_at")


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


# ============================================================ 4.7 Demand Planning & Forecasting
from apps.scm.models import (  # noqa: E402
    SeasonalityProfile, SeasonalityIndex, DemandForecast, DemandForecastPeriod,
    DemandSignal, ForecastAdjustment,
)


class SeasonalityIndexInline(admin.TabularInline):
    model = SeasonalityIndex
    extra = 0
    readonly_fields = ("sample_size",)


@admin.register(SeasonalityProfile)
class SeasonalityProfileAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "tenant", "profile_type", "scope", "bucket", "is_active")
    list_filter = ("tenant", "profile_type", "scope", "bucket", "is_active")
    search_fields = ("number", "name", "item__sku")
    readonly_fields = ("last_derived_at",)
    inlines = [SeasonalityIndexInline]


class DemandForecastPeriodInline(admin.TabularInline):
    model = DemandForecastPeriod
    extra = 0
    # The waterfall columns the app owns: a history snapshot, the signal engine's output and the
    # consensus roll-up. Typing them here would make the decomposition lie.
    # Every computed step of the waterfall. All are editable=False on the model now, so the admin
    # cannot offer them either — typing any of them here would make the decomposition lie.
    readonly_fields = ("historical_quantity", "seasonal_index_applied", "event_uplift_quantity",
                       "signal_adjustment_quantity", "consensus_quantity", "final_quantity")


@admin.register(DemandForecast)
class DemandForecastAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "tenant", "item", "bucket", "method", "status",
                    "horizon_start", "horizon_end")
    list_filter = ("tenant", "status", "method", "bucket", "scenario")
    search_fields = ("number", "name", "item__sku", "item__name")
    readonly_fields = ("selected_method", "revision", "supersedes", "generated_at",
                       "approved_by", "approved_at")
    inlines = [DemandForecastPeriodInline]


@admin.register(DemandSignal)
class DemandSignalAdmin(admin.ModelAdmin):
    list_display = ("number", "tenant", "signal_type", "source", "item", "impact_direction",
                    "impact_pct", "status", "observed_at")
    list_filter = ("tenant", "status", "signal_type", "source", "impact_direction", "confidence")
    search_fields = ("number", "source_reference", "item__sku")
    readonly_fields = ("applied_to_forecast", "reviewed_by", "reviewed_at")


@admin.register(ForecastAdjustment)
class ForecastAdjustmentAdmin(admin.ModelAdmin):
    list_display = ("number", "tenant", "forecast", "contributor_function", "adjustment_type",
                    "resolved_quantity", "reason_code", "status")
    list_filter = ("tenant", "status", "contributor_function", "reason_code", "adjustment_type")
    search_fields = ("number", "rationale", "forecast__number")
    readonly_fields = ("submitted_by", "resolved_quantity", "reviewed_by", "reviewed_at",
                       "review_note")


# ============================================================ 4.8 Manufacturing / Production
from apps.scm.models import (  # noqa: E402
    WorkCenter, BillOfMaterials, BOMLine, WorkOrder, WorkOrderComponent, ProductionTimeLog,
)


@admin.register(WorkCenter)
class WorkCenterAdmin(admin.ModelAdmin):
    list_display = ("number", "code", "name", "tenant", "center_type", "location",
                    "capacity_hours_per_day", "efficiency_pct", "is_active")
    list_filter = ("tenant", "center_type", "is_active")
    search_fields = ("number", "code", "name", "supervisor__name")


class BOMLineInline(admin.TabularInline):
    model = BOMLine
    extra = 0


@admin.register(BillOfMaterials)
class BillOfMaterialsAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "tenant", "item", "version", "bom_type", "status",
                    "output_quantity", "is_default")
    list_filter = ("tenant", "status", "bom_type", "is_default")
    search_fields = ("number", "name", "version", "item__sku", "item__name")
    inlines = [BOMLineInline]


class WorkOrderComponentInline(admin.TabularInline):
    model = WorkOrderComponent
    extra = 0
    # quantity_issued is written only by the issue action — an admin edit would claim a consumption
    # the StockMove ledger never recorded.
    readonly_fields = ("quantity_issued",)


@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    list_display = ("number", "tenant", "item", "quantity_planned", "quantity_produced",
                    "status", "priority", "work_center", "planned_start", "due_date")
    list_filter = ("tenant", "status", "priority", "order_policy", "work_center")
    search_fields = ("number", "item__sku", "item__name", "bom__number", "sales_order__number")
    # Every field below is written by a posting or lifecycle action. Leaving any of them editable
    # would make the admin a second writer of a figure the stock ledger is the authority for.
    readonly_fields = ("status", "actual_start", "actual_end", "quantity_produced",
                       "quantity_scrapped", "produced_unit_cost", "released_by")
    inlines = [WorkOrderComponentInline]


@admin.register(ProductionTimeLog)
class ProductionTimeLogAdmin(admin.ModelAdmin):
    list_display = ("number", "tenant", "work_order", "work_center", "entry_type", "operator",
                    "started_at", "duration_minutes", "quantity_completed")
    list_filter = ("tenant", "entry_type", "downtime_reason", "work_center")
    search_fields = ("number", "operation", "work_order__number", "operator__name")
    readonly_fields = ("duration_minutes",)
