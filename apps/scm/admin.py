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
# 4.11 Supply Chain Analytics (registrations at the foot of this module, following the per-sub-module
# import blocks 4.3 onwards already use).
from apps.scm.models import (
    KpiSnapshot,
    KpiTarget,
    SupplyChainAlert,
)
# 4.17 Third-Party Logistics (3PL) Management
from apps.scm.models import (
    ClientBillingRun,
    ClientBillingRunLine,
    ClientRateCard,
    ClientRateCardLine,
    ClientSLA,
    LogisticsClient,
)
# 4.16 Customer Portal
from apps.scm.models import (
    PortalAccount,
    PortalActivity,
    PortalDocumentShare,
    PortalOrderInquiry,
)
# 4.18 Finance & Accounting Integration
from apps.scm.models import (
    DutyTariff,
    LandedCostAllocation,
    LandedCostCharge,
    LandedCostVoucher,
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
    # is_spare_part (4.13) is an ordinary editable marker, not a derived column — it says "this is an
    # MRO part", which is a decision somebody makes, so it is a filter and a column and stays out of
    # readonly_fields.
    list_display = ("sku", "name", "tenant", "item_type", "tracking", "costing_method",
                    "average_cost", "is_spare_part")
    list_filter = ("tenant", "item_type", "tracking", "costing_method", "is_spare_part", "is_active")
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


# ============================================================ 4.9 Quality Management System (QMS)
from apps.scm.models import (  # noqa: E402
    InspectionPlan, InspectionCharacteristic, QualityInspection, InspectionResult, QualityAudit,
    NonConformance, CapaAction, CapaTask,
)


class InspectionCharacteristicInline(admin.TabularInline):
    model = InspectionCharacteristic
    extra = 0


@admin.register(InspectionPlan)
class InspectionPlanAdmin(admin.ModelAdmin):
    list_display = ("code", "version", "name", "tenant", "plan_type", "item", "supplier",
                    "sampling_method", "is_active")
    list_filter = ("tenant", "plan_type", "sampling_method", "is_active")
    search_fields = ("code", "name", "version", "item__sku", "item__name", "supplier__name")
    inlines = [InspectionCharacteristicInline]


class InspectionResultInline(admin.TabularInline):
    model = InspectionResult
    extra = 0
    # The whole snapshot block is written once by generate_results() and must never be edited: a
    # certificate already issued would otherwise start printing limits nobody measured against.
    # `result` is derived by InspectionResult.save() for a measurement, so it is shown but the
    # admin cannot make it disagree with the limits.
    readonly_fields = ("characteristic", "characteristic_name", "characteristic_type", "uom",
                       "target_value", "lower_limit", "upper_limit", "test_method",
                       "include_on_coa", "is_critical", "is_mandatory")


@admin.register(QualityInspection)
class QualityInspectionAdmin(admin.ModelAdmin):
    list_display = ("number", "tenant", "inspection_type", "item", "lot_serial", "inspected_on",
                    "status", "usage_decision", "coa_number")
    list_filter = ("tenant", "status", "inspection_type", "usage_decision", "action_taken")
    search_fields = ("number", "coa_number", "item__sku", "item__name", "lot_serial__number",
                     "supplier_coa_reference")
    # Every field below is written by a lifecycle, decision or issue action. Leaving any of them
    # editable would make the admin a second writer — the exact bug 4.7 shipped and then fixed.
    readonly_fields = ("number", "status", "usage_decision", "action_taken", "coa_number",
                       "coa_issued_on", "coa_issued_to")
    inlines = [InspectionResultInline]


@admin.register(QualityAudit)
class QualityAuditAdmin(admin.ModelAdmin):
    list_display = ("number", "tenant", "audit_type", "title", "auditee_party",
                    "auditee_org_unit", "planned_date", "risk_level", "status")
    list_filter = ("tenant", "audit_type", "status", "risk_level")
    search_fields = ("number", "title", "standard", "scope", "lead_auditor__name")
    # findings_major / findings_minor are deliberately NOT columns — they are properties and list
    # annotations. Do not add them here or anywhere else.
    readonly_fields = ("number", "status", "actual_start", "actual_end")


@admin.register(NonConformance)
class NonConformanceAdmin(admin.ModelAdmin):
    list_display = ("number", "tenant", "source", "item", "severity", "defect_category",
                    "quantity_affected", "status", "disposition", "detected_on")
    list_filter = ("tenant", "status", "severity", "source", "defect_category", "disposition")
    search_fields = ("number", "title", "description", "item__sku", "lot_serial__number")
    # The MRB decision block plus the quarantine mirror — all written by their actions inside the
    # same transaction that posts (or deliberately does not post) the StockMove.
    readonly_fields = ("number", "status", "quarantine_applied", "disposition",
                       "disposition_quantity", "disposition_by", "disposition_on",
                       "disposition_notes", "closed_on")


class CapaTaskInline(admin.TabularInline):
    model = CapaTask
    extra = 0


@admin.register(CapaAction)
class CapaActionAdmin(admin.ModelAdmin):
    list_display = ("number", "tenant", "action_type", "title", "source", "owner", "priority",
                    "due_date", "status", "effectiveness_result")
    list_filter = ("tenant", "status", "action_type", "priority", "source", "effectiveness_result")
    search_fields = ("number", "title", "problem_statement", "root_cause", "owner__name")
    # effectiveness_due_date is NOT here: it is an ordinary editable field whose single writer is
    # the form (capaaction_implement refuses while it is blank rather than filling it).
    readonly_fields = ("number", "status", "implemented_on", "effectiveness_result", "verified_by",
                       "verified_on", "verification_notes", "closed_on")
    inlines = [CapaTaskInline]


# ============================================================ 4.10 Returns Management (Reverse Logistics)
from apps.scm.models import (  # noqa: E402
    ReturnReason, ReturnPolicy, ReturnAuthorization, ReturnLine, ReturnDisposition,
    WarrantyClaim, WarrantyClaimCost,
)


@admin.register(ReturnReason)
class ReturnReasonAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "tenant", "fault_party", "blocks_restock",
                    "suggested_disposition", "requires_photo", "raises_nonconformance",
                    "sort_order", "is_active")
    list_filter = ("tenant", "fault_party", "is_active", "blocks_restock", "requires_photo",
                   "raises_nonconformance")
    search_fields = ("code", "name", "follow_up_question")
    # Nothing here is computed — a reason is pure configuration, so there is no readonly block.


@admin.register(ReturnPolicy)
class ReturnPolicyAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "item_category", "priority", "window_basis", "window_days",
                    "refund_basis", "restocking_fee_type", "auto_approve", "is_default",
                    "is_active")
    list_filter = ("tenant", "is_active", "is_default", "window_basis", "refund_basis",
                   "restocking_fee_type", "return_shipping_paid_by", "auto_approve")
    search_fields = ("name", "return_to_address", "portal_instructions")
    # Every field is user-owned; the grade ladder is a policy, not a derived figure.


class ReturnLineInline(admin.TabularInline):
    model = ReturnLine
    extra = 0


class ReturnDispositionInline(admin.TabularInline):
    model = ReturnDisposition
    extra = 0
    # received_on/received_by are stamped at intake, decided_on/decided_by at the decision, and
    # stock_posted/stock_move by the ONE action that writes the append-only ledger. An admin edit
    # of any of them would claim a movement the ledger never recorded — the exact bug 4.7 shipped.
    # restock_unit_cost is deliberately NOT here: it is user-owned (seeded once from the grade
    # write-down, then whoever refurbished the unit knows what it is worth).
    readonly_fields = ("received_on", "received_by", "refurbished_on", "stock_posted",
                       "stock_move", "decided_on", "decided_by")


@admin.register(ReturnAuthorization)
class ReturnAuthorizationAdmin(admin.ModelAdmin):
    list_display = ("number", "tenant", "customer", "return_type", "status", "resolution",
                    "requested_on", "approved_on", "credit_total", "credit_note")
    list_filter = ("tenant", "status", "return_type", "source", "resolution", "refund_method",
                   "return_method", "advance_refund")
    search_fields = ("number", "notes", "return_tracking_number", "counterparty_rma_number",
                     "customer__name", "sales_order__number")
    # Every field below has exactly ONE writer and it is never a form (plan section 7.7).
    # public_token in particular: it is the bearer credential for the public status page, so it is
    # minted once in save() and must never be typed, re-typed or copied between rows.
    readonly_fields = ("number", "status", "policy_snapshot", "approved_on", "approved_by",
                       "rejected_reason", "customer_shipped_on", "public_token", "portal_note",
                       "credit_note", "replacement_order", "refund_subtotal", "fee_total",
                       "tax_total", "credit_total")
    inlines = [ReturnLineInline]


@admin.register(ReturnDisposition)
class ReturnDispositionAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant", "return_line", "quantity", "condition_grade", "disposition",
                    "location", "restock_location", "restock_unit_cost", "stock_posted",
                    "received_on")
    list_filter = ("tenant", "disposition", "condition_grade", "stock_posted", "location")
    search_fields = ("notes", "return_line__item__sku",
                     "return_line__return_authorization__number", "lot_serial__number")
    # Same reasoning as the inline above — the stamped block is the ledger's own evidence.
    readonly_fields = ("received_on", "received_by", "refurbished_on", "stock_posted",
                       "stock_move", "decided_on", "decided_by")


class WarrantyClaimCostInline(admin.TabularInline):
    model = WarrantyClaimCost
    extra = 0
    # amount_claimed is computed in WarrantyClaimCost.save() from quantity x unit_amount. Shipping
    # all three as inputs is how a row ends up claiming a figure its own arithmetic contradicts.
    readonly_fields = ("amount_claimed",)


@admin.register(WarrantyClaim)
class WarrantyClaimAdmin(admin.ModelAdmin):
    list_display = ("number", "tenant", "supplier", "item", "quantity_claimed", "status",
                    "defect_classification", "submitted_on", "response_due_on", "amount_approved",
                    "amount_credited")
    list_filter = ("tenant", "status", "defect_classification", "submission_channel", "supplier")
    search_fields = ("number", "supplier_rma_number", "serial_reference", "description",
                     "supplier__name", "item__sku", "item__name", "lot_serial__number")
    # The whole negotiation block: the supplier's side of a two-party exchange, written only by
    # warrantyclaim_submit / _record_response / _record_credit. amount_claimed_total,
    # recovery_variance and recovery_rate_pct are PROPERTIES and are deliberately not columns here
    # or anywhere else (plan section 7.3).
    readonly_fields = ("number", "status", "submitted_on", "responded_on",
                       "supplier_response_notes", "amount_approved", "amount_credited",
                       "credit_reference", "credit_received_on")
    inlines = [WarrantyClaimCostInline]


# =================================================================================================
# 4.11 Supply Chain Analytics
#
# Every editable=False column is listed in readonly_fields. That is not decoration: the admin is the
# one surface that bypasses the forms, so a workflow column left editable here is a column any staff
# user can set by hand — which for these three models means hand-typing a "measured" figure, a
# frozen history point, or an acknowledgement nobody actually made.
# =================================================================================================


@admin.register(KpiTarget)
class KpiTargetAdmin(admin.ModelAdmin):
    list_display = ("number", "tenant", "name", "metric", "scope", "direction", "target_value",
                    "warning_threshold", "critical_threshold", "is_alerting", "severity",
                    "is_active", "last_evaluated_at")
    list_filter = ("tenant", "metric", "scope", "direction", "severity", "is_alerting",
                   "is_active", "period_grain", "date_range")
    search_fields = ("number", "name", "notes", "scope_category__name", "scope_location__code",
                     "scope_vendor__name")
    # number is assigned once in save(); last_evaluated_at is stamped by capture_snapshots /
    # detect_alerts and means "when this target was last measured" — typing it would be a lie about
    # data freshness, which is the one thing a target's staleness badge relies on.
    readonly_fields = ("number", "last_evaluated_at", "created_at", "updated_at")


@admin.register(KpiSnapshot)
class KpiSnapshotAdmin(admin.ModelAdmin):
    list_display = ("kpi_target", "tenant", "metric", "period_start", "period_end",
                    "dimension_label", "value", "target_value_at_time", "status_band",
                    "computed_at", "computed_by")
    list_filter = ("tenant", "metric", "status_band", "period_end")
    search_fields = ("dimension_label", "dimension_key", "kpi_target__number",
                     "kpi_target__name")
    date_hierarchy = "period_end"
    # A snapshot is a MEASUREMENT: the whole reason it is stored is that re-deriving it later would
    # give a different answer (average cost is recomputed on every receipt, back-dated moves are
    # legal). Everything that says what was measured, when, and by whom is therefore read-only —
    # an editable value column would make the frozen history editable, which defeats freezing it.
    readonly_fields = ("kpi_target", "metric", "period_start", "period_end", "dimension_key",
                       "dimension_label", "value", "target_value_at_time", "status_band",
                       "breakdown", "computed_at", "computed_by", "created_at", "updated_at")


@admin.register(SupplyChainAlert)
class SupplyChainAlertAdmin(admin.ModelAdmin):
    list_display = ("number", "tenant", "severity", "alert_type", "title", "dimension_label",
                    "observed_value", "threshold_value", "impact_value", "status", "assigned_to",
                    "raised_at", "last_seen_at")
    list_filter = ("tenant", "status", "severity", "alert_type", "assigned_to")
    search_fields = ("number", "title", "dimension_label", "dedupe_key", "notes",
                     "resolution_note", "party__name", "item__sku", "item__name")
    date_hierarchy = "raised_at"
    # The lifecycle block. status moves only through the five action views; dedupe_key is the
    # detector's own bookkeeping and editing it would either orphan an open alert (so the next sweep
    # raises a duplicate) or collide it with an unrelated one (so a real breach silently updates the
    # wrong row). raised_at/last_seen_at are what "still breaching" is read from.
    readonly_fields = ("number", "status", "dedupe_key", "acknowledged_by", "acknowledged_at",
                       "snoozed_until", "resolved_by", "resolved_at", "raised_at", "last_seen_at",
                       "created_at", "updated_at")


# --- 4.12 Contract & Compliance Management ------------------------------------------------------
from apps.scm.models import (  # noqa: E402
    ComplianceRequirement, ComplianceCheck, TradeDocument, TradeDocumentLine, TradeLicense,
    SustainabilityAssessment,
)


class ComplianceCheckInline(admin.TabularInline):
    model = ComplianceCheck
    extra = 0
    # performed_by is stamped from request.user by the view, never typed — see the model. Showing it
    # read-only here keeps the admin from becoming the one path that can forge "who proved this".
    readonly_fields = ("performed_by", "created_at")


@admin.register(ComplianceRequirement)
class ComplianceRequirementAdmin(admin.ModelAdmin):
    list_display = ("number", "tenant", "title", "source", "framework", "scope", "criticality",
                    "status", "frequency", "next_due_date", "owner")
    list_filter = ("tenant", "status", "source", "framework", "criticality", "frequency")
    search_fields = ("number", "title", "description", "jurisdiction", "source_reference",
                     "party__name")
    date_hierarchy = "next_due_date"
    inlines = [ComplianceCheckInline]
    # number is assigned once in save(); last_checked_on is written only by record_check() as the
    # parent's proof stamp, so it is a derived fact rather than an input.
    readonly_fields = ("number", "last_checked_on", "created_at", "updated_at")


@admin.register(ComplianceCheck)
class ComplianceCheckAdmin(admin.ModelAdmin):
    list_display = ("requirement", "result", "due_date", "performed_on", "performed_by")
    list_filter = ("result", "performed_on")
    search_fields = ("requirement__number", "requirement__title", "finding",
                     "corrective_reference", "notes")
    date_hierarchy = "performed_on"
    readonly_fields = ("performed_by", "created_at")


class TradeDocumentLineInline(admin.TabularInline):
    model = TradeDocumentLine
    extra = 0


@admin.register(TradeDocument)
class TradeDocumentAdmin(admin.ModelAdmin):
    list_display = ("number", "tenant", "doc_type", "status", "issue_date", "shipment",
                    "license")
    list_filter = ("tenant", "status", "doc_type", "issue_date")
    search_fields = ("number", "shipment__number", "license__license_number")
    date_hierarchy = "issue_date"
    inlines = [TradeDocumentLineInline]
    # status is editable=False on the model and moves only through issue/submit/accept/void, each of
    # which is what charges or refunds the licence balance. An editable status column here would let
    # a document be marked issued without ever touching the licence it was issued under.
    readonly_fields = ("number", "status", "issued_at", "issued_by", "void_reason",
                       "created_at", "updated_at")


@admin.register(TradeLicense)
class TradeLicenseAdmin(admin.ModelAdmin):
    list_display = ("number", "tenant", "license_number", "title", "license_type", "status",
                    "issue_date", "expiry_date")
    list_filter = ("tenant", "status", "license_type", "expiry_date")
    search_fields = ("number", "license_number", "title", "issuing_authority")
    date_hierarchy = "expiry_date"
    # used_value/used_quantity are DERIVED from the documents issued under this licence -
    # recompute_usage() is their only writer. approved_*/revoked_*/revocation_reason are the
    # lifecycle stamps. All are editable=False on the model, so listing them here is what makes
    # them VISIBLE in the admin at all rather than silently absent from the form.
    readonly_fields = ("number", "status", "used_value", "used_quantity", "approved_at",
                       "approved_by", "revoked_at", "revocation_reason", "created_at",
                       "updated_at")
    actions = ["recompute_usage"]

    @admin.action(description="Re-derive consumed balance from issued documents")
    def recompute_usage(self, request, queryset):
        """The admin-side remedy for a stale balance.

        Deleting a TradeDocument, or editing its lines through TradeDocumentLineInline, bypasses the
        issue/void views that maintain used_value — so the admin needs its own way back to a correct
        figure, or an admin edit silently leaves the licence over- or under-drawn with no route to
        fix it but the tenant-admin button on the front end.
        """
        for licence in queryset:
            licence.recompute_usage(save=True)
        self.message_user(request, f"Re-derived {queryset.count()} licence(s) from their documents.")


@admin.register(SustainabilityAssessment)
class SustainabilityAssessmentAdmin(admin.ModelAdmin):
    list_display = ("number", "tenant", "party", "assessment_date", "source", "status",
                    "overall_score")
    list_filter = ("tenant", "status", "source", "assessment_date")
    search_fields = ("number", "party__name")
    date_hierarchy = "assessment_date"
    # overall_score is DERIVED from the theme scores — it is editable=False on the model precisely so
    # the headline number can never disagree with the components it is computed from.
    readonly_fields = ("number", "overall_score", "rating", "assessed_by", "created_at",
                       "updated_at")


# --- 4.13 Asset Management ----------------------------------------------------------------------
from apps.scm.models import (  # noqa: E402
    Asset, AssetSparePart, MaintenancePlan, MaintenancePlanTask, MaintenanceWorkOrder,
    MaintenanceWorkOrderPart, MaintenanceWorkOrderTask, MeterReading,
)


class AssetSparePartInline(admin.TabularInline):
    model = AssetSparePart
    extra = 0
    # Nothing here is derived — the row is the ASSOCIATION (which item, how many per service,
    # whether running out stops the job), so every column is a genuine input.


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "tenant", "asset_type", "status", "criticality", "location",
                    "work_center", "custodian", "warranty_expires_on", "is_active")
    list_filter = ("tenant", "status", "criticality", "asset_type", "is_active")
    search_fields = ("code", "name", "number", "serial_number", "tag_code", "model_number",
                     "manufacturer", "category")
    date_hierarchy = "warranty_expires_on"
    inlines = [AssetSparePartInline]
    # number is minted once in save(). MTBF, MTTR, availability, downtime and maintenance cost to
    # date are METHODS on the model and are deliberately not columns here or anywhere else — the
    # whole design is that a reliability figure recomputes on read and may honestly answer None.
    readonly_fields = ("number", "created_at", "updated_at")


class MaintenancePlanTaskInline(admin.TabularInline):
    model = MaintenancePlanTask
    extra = 0
    # The job plan's steps. Editing them here changes what FUTURE generated jobs will ask for and
    # nothing else — a job already raised snapshotted its own copy (MaintenanceWorkOrderTask has no
    # FK back), which is exactly why that snapshot exists.


@admin.register(MaintenancePlan)
class MaintenancePlanAdmin(admin.ModelAdmin):
    list_display = ("number", "tenant", "name", "asset", "trigger_type", "schedule_basis",
                    "interval_days", "meter_interval", "next_due_on", "next_due_reading",
                    "priority", "work_type", "is_active")
    list_filter = ("tenant", "trigger_type", "schedule_basis", "priority", "work_type", "is_active")
    search_fields = ("number", "name", "instructions", "asset__code", "asset__name")
    date_hierarchy = "next_due_on"
    inlines = [MaintenancePlanTaskInline]
    # number is minted once in save(); last_completed_on is stamped by the work-order complete verb
    # and last_generated_on by the generate action (both editable=False on the model, so listing
    # them here is what makes them VISIBLE rather than silently absent from the form). Typing either
    # by hand would claim a service that was never performed, and the PM-compliance report believes
    # it. next_due_on / next_due_reading are deliberately NOT here: they are the schedule, and a
    # planner shifting one is a legitimate edit.
    readonly_fields = ("number", "last_completed_on", "last_generated_on", "created_at",
                       "updated_at")


class MaintenanceWorkOrderPartInline(admin.TabularInline):
    model = MaintenanceWorkOrderPart
    extra = 0
    # unit_cost is stamped from the item's average cost AT ISSUE TIME by the issue verb, in the same
    # transaction that posts the negative `maintenance` StockMove; is_issued / issued_at are that
    # verb's own evidence. Editing any of them here would claim a draw the ledger never recorded —
    # the ReturnDisposition.stock_posted reasoning, one table over.
    readonly_fields = ("unit_cost", "is_issued", "issued_at")


class MaintenanceWorkOrderTaskInline(admin.TabularInline):
    model = MaintenanceWorkOrderTask
    extra = 0
    # completed_at is stamped by the tick route (L22) — the tick IS the event, so its time is not
    # something anyone should be able to disagree with afterwards. The five snapshot columns stay
    # editable: an ad-hoc breakdown job has steps typed straight onto it, so they are inputs here in
    # a way the plan-copied ones are not, and a single readonly rule cannot tell the two apart.
    readonly_fields = ("completed_at",)


@admin.register(MaintenanceWorkOrder)
class MaintenanceWorkOrderAdmin(admin.ModelAdmin):
    list_display = ("number", "tenant", "title", "asset", "work_type", "priority", "status",
                    "source", "assigned_to", "reported_at", "scheduled_start", "completed_at",
                    "downtime_minutes")
    list_filter = ("tenant", "status", "work_type", "priority", "source", "is_unplanned_downtime",
                   "problem_code", "cause_code", "remedy_code")
    search_fields = ("number", "title", "description", "resolution_notes", "asset__code",
                     "asset__name", "plan__number", "assigned_to__name", "service_vendor__name")
    date_hierarchy = "reported_at"
    inlines = [MaintenanceWorkOrderPartInline, MaintenanceWorkOrderTaskInline]
    # status moves only through the lifecycle verbs (editable=False on the model, and absent from
    # the form's Meta.fields so a crafted POST has no path to it either) — an editable status here
    # would be the one surface that can mark a job complete without stamping completed_at, advancing
    # its plan or filing the meter reading the complete verb captures. started_at / completed_at are
    # the verbs' stamps. downtime_minutes is DERIVED in save() from the start/end pair and clamped:
    # showing it read-only is what stops the admin making the total disagree with the window it is
    # computed from. parts_cost / labour_cost / total_cost / duration_hours / is_on_time are
    # PROPERTIES and are deliberately not columns anywhere.
    readonly_fields = ("number", "status", "started_at", "completed_at", "downtime_minutes",
                       "created_at", "updated_at")


@admin.register(MeterReading)
class MeterReadingAdmin(admin.ModelAdmin):
    # APPEND-ONLY log — read-only in the admin, no add/change/delete. Exactly the StockMoveAdmin
    # posture, and for the same reason: a wrong reading is corrected by posting a later, correct one,
    # never by editing the row a scheduler has already acted on. An editable meter reading is a
    # number that silently moves every meter-based due date derived from it, with no trace that it
    # ever said anything else. The front end ships no edit and no delete route for the same reason.
    list_display = ("asset", "tenant", "meter_name", "reading", "unit", "read_at", "source",
                    "reference", "recorded_by")
    list_filter = ("tenant", "source", "meter_name")
    search_fields = ("meter_name", "reference", "notes", "asset__code", "asset__name")
    date_hierarchy = "read_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# --- 4.14 Labor Management --------------------------------------------------------------------
from apps.scm.models import (  # noqa: E402
    LaborActivity, LaborPlan, LaborPlanLine, LaborSession, LaborStandard,
)


@admin.register(LaborStandard)
class LaborStandardAdmin(admin.ModelAdmin):
    list_display = ("number", "tenant", "name", "activity", "basis", "source", "status",
                    "minutes_per_unit", "setup_minutes", "travel_minutes", "allowance_pct",
                    "labour_rate", "location", "item_category", "effective_from", "effective_to")
    list_filter = ("tenant", "status", "activity", "basis", "source")
    search_fields = ("number", "name", "notes", "location__name", "item_category__name")
    date_hierarchy = "effective_from"
    # `status` moves only through the activate/archive verbs. It is not a cosmetic flag: activating a
    # standard changes what every FUTURE LaborActivity snapshots, and archiving one removes it from
    # `select_standard()`'s candidate set, which changes what tomorrow's work is measured against.
    # An editable dropdown here is a surface that can do both without an audit row.
    readonly_fields = ("number", "status", "created_at", "updated_at")


class LaborActivityInline(admin.TabularInline):
    model = LaborActivity
    extra = 0
    # The four snapshot columns plus the derived duration are read-only for the reason the whole
    # sub-module turns on: they record what the standard said AT FILE TIME. A snapshot an admin can
    # retype is not a record of anything — it is last month's performance figure, editable.
    readonly_fields = ("number", "duration_minutes", "standard", "standard_fixed_snapshot",
                       "standard_rate_snapshot", "standard_allowance_snapshot",
                       "standard_minutes_snapshot", "created_at", "updated_at")


@admin.register(LaborSession)
class LaborSessionAdmin(admin.ModelAdmin):
    list_display = ("number", "tenant", "worker", "location", "work_date", "shift_label",
                    "clock_in", "clock_out", "status", "source", "recorded_by", "login",
                    "approved_by", "approved_at")
    list_filter = ("tenant", "status", "source", "location")
    search_fields = ("number", "shift_label", "notes", "worker__name", "location__name")
    date_hierarchy = "work_date"
    inlines = [LaborActivityInline]
    # The whole provenance block is read-only, which is the 4.13 MeterReading fix carried through to
    # the admin. `source` / `recorded_by` / `login` say WHERE a shift record came from, and the
    # payroll export is built on the claim that they are true. `status` is the export lock — an
    # editable one could approve a shift without stamping who approved it or when. Every derived
    # figure (attended/direct/indirect/unaccounted minutes, performance, utilisation, units per hour)
    # is a METHOD and is deliberately not a column anywhere.
    readonly_fields = ("number", "status", "source", "recorded_by", "login", "closed_at",
                       "approved_at", "approved_by", "created_at", "updated_at")


@admin.register(LaborActivity)
class LaborActivityAdmin(admin.ModelAdmin):
    list_display = ("number", "tenant", "session", "activity_type", "indirect_reason",
                    "started_at", "ended_at", "duration_minutes", "quantity", "error_quantity",
                    "standard", "standard_minutes_snapshot")
    list_filter = ("tenant", "activity_type", "indirect_reason")
    search_fields = ("number", "reference", "notes", "session__number", "session__worker__name")
    date_hierarchy = "started_at"
    readonly_fields = ("number", "duration_minutes", "standard", "standard_fixed_snapshot",
                       "standard_rate_snapshot", "standard_allowance_snapshot",
                       "standard_minutes_snapshot", "created_at", "updated_at")


class LaborPlanLineInline(admin.TabularInline):
    model = LaborPlanLine
    extra = 0
    # `planned_headcount` and `notes` are the only editable columns — everything else is what
    # `laborplan_generate` computed, and the variance chip beside them only means something while
    # the required figure is the arithmetic's and the planned figure is the planner's.
    readonly_fields = ("period_start", "activity", "forecast_volume", "standard",
                       "standard_minutes_snapshot", "required_minutes", "required_headcount")


@admin.register(LaborPlan)
class LaborPlanAdmin(admin.ModelAdmin):
    list_display = ("number", "tenant", "name", "location", "period_start", "period_end",
                    "bucket", "volume_source", "method", "history_days", "hours_per_shift",
                    "productivity_pct", "status", "generated_at", "approved_by", "approved_at")
    list_filter = ("tenant", "status", "bucket", "volume_source", "method")
    search_fields = ("number", "name", "notes", "location__name")
    date_hierarchy = "period_start"
    inlines = [LaborPlanLineInline]
    readonly_fields = ("number", "status", "generated_at", "approved_by", "approved_at",
                       "created_at", "updated_at")


# --- 4.15 Cold Chain Management ----------------------------------------------------------------
from apps.scm.models import (  # noqa: E402
    ColdChainMonitor, TemperatureExcursion, TemperatureReading,
)


@admin.register(ColdChainMonitor)
class ColdChainMonitorAdmin(admin.ModelAdmin):
    list_display = ("number", "tenant", "name", "device_type", "device_serial", "location", "asset",
                    "shipment", "storage_condition", "min_temperature", "max_temperature",
                    "excursion_grace_minutes", "logging_interval_minutes", "calibration_due_on",
                    "status")
    list_filter = ("tenant", "status", "device_type", "storage_condition")
    search_fields = ("number", "name", "device_serial", "calibration_reference", "notes",
                     "location__code", "location__name", "asset__code", "asset__name",
                     "shipment__number")
    date_hierarchy = "calibration_due_on"
    # `status` is deliberately NOT read-only here — unlike TemperatureExcursion.status it is
    # user-owned lifecycle and the user is its only writer (the Asset.status ruling). Every derived
    # answer on this model (in range, in the warning band, still reporting, calibration due, the open
    # episode) is a METHOD and is deliberately not a column anywhere, so there is nothing else to
    # protect from an admin edit beyond the generated number.
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(TemperatureReading)
class TemperatureReadingAdmin(admin.ModelAdmin):
    # APPEND-ONLY ledger — read-only in the admin, no add/change/delete. Exactly the StockMoveAdmin
    # (:198-212) and MeterReadingAdmin (:964-984) posture, and for the same reason one sub-module on:
    # a wrong reading is corrected by posting a later, correct one, never by editing the row a
    # compliance report has already been built from. It is also the only posture that survives an
    # ALCOA+ review, where a silently editable measurement IS the finding. The front end ships no
    # edit and no delete route for the same reason.
    list_display = ("monitor", "tenant", "reading_at", "temperature", "min_temperature",
                    "max_temperature", "humidity_pct", "sample_count", "interval_minutes", "source",
                    "recorded_by")
    list_filter = ("tenant", "source")
    search_fields = ("notes", "monitor__number", "monitor__name", "monitor__device_serial")
    date_hierarchy = "reading_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TemperatureExcursion)
class TemperatureExcursionAdmin(admin.ModelAdmin):
    list_display = ("number", "tenant", "monitor", "started_at", "ended_at", "duration_minutes",
                    "breach_direction", "extreme_temperature", "limit_min", "limit_max", "mkt",
                    "severity", "status", "assessment", "cause")
    list_filter = ("tenant", "status", "severity", "assessment", "breach_direction", "cause")
    search_fields = ("number", "corrective_action", "notes", "monitor__number", "monitor__name")
    date_hierarchy = "started_at"
    # EVERY detector-written column is read-only, plus the workflow-controlled `status` and the two
    # attribution stamps. These are MEASUREMENTS and SNAPSHOTS: `limit_min`/`limit_max` record the
    # band that was in force when the episode fired, and an admin who can retype them can rewrite
    # last year's audit finding into a pass. `status` is read-only because the four triage verbs are
    # what stamp who acknowledged and who assessed; an editable dropdown could close an excursion
    # with nobody's name on it. `severity`, `assessment`, `cause`, `corrective_action` and `notes`
    # stay editable — that is the human half of the record.
    readonly_fields = ("number", "started_at", "ended_at", "duration_minutes", "breach_direction",
                       "extreme_temperature", "limit_min", "limit_max", "reading_count", "mkt",
                       "last_detected_at", "status", "acknowledged_by", "acknowledged_at",
                       "assessed_by", "assessed_on", "created_at", "updated_at")


# --- 4.16 Customer Portal -----------------------------------------------------------------------
# The admin is a second write path into every one of these tables, and it does NOT go through the
# forms, the gated verbs or `full_clean()`. So every column the application treats as
# system-written has to be re-declared read-only HERE as well — otherwise the admin is exactly the
# bypass the `editable=False` flags exist to prevent, one URL over.


@admin.register(PortalAccount)
class PortalAccountAdmin(admin.ModelAdmin):
    list_display = ("number", "tenant", "customer", "is_active", "activated_on", "stock_display",
                    "catalog_scope", "price_basis", "show_credit_and_balance")
    list_filter = ("tenant", "is_active", "stock_display", "catalog_scope", "price_basis",
                   "show_credit_and_balance", "preferred_channel")
    search_fields = ("number", "customer__name", "support_email", "notes")
    filter_horizontal = ("catalog_categories",)
    # `activated_on` is evidence of when enablement first happened, stamped once in save() and never
    # restamped. An admin who can retype it can rewrite the adoption history the enablement console
    # exists to report.
    readonly_fields = ("number", "activated_on", "created_at", "updated_at")


@admin.register(PortalOrderInquiry)
class PortalOrderInquiryAdmin(admin.ModelAdmin):
    list_display = ("number", "tenant", "portal_account", "inquiry_type", "requested_resolution",
                    "sales_order", "outcome", "source", "resolved_at", "created_at")
    list_filter = ("tenant", "inquiry_type", "requested_resolution", "outcome", "source")
    search_fields = ("number", "case__subject", "sales_order__number", "portal_account__number")
    date_hierarchy = "created_at"
    # `case` is the wrapped crm.Case and is written ONLY by open_for(), inside a transaction that
    # also forces origin and the SLA policy — re-pointing it here would orphan a case and silently
    # hand this inquiry somebody else's conversation. `outcome`, `resolved_at` and
    # `return_authorization` are written ONLY by the resolve / reopen / link_return verbs, each of
    # which writes an audit row; an editable dropdown here would move an inquiry to `credit_drafted`
    # with nobody's name on it. `source` and `raised_by` are attribution, forced server-side by
    # whichever view filed it — an editable `source` lets a staff-filed inquiry claim to be the
    # customer's own words.
    readonly_fields = ("number", "case", "outcome", "resolved_at", "return_authorization",
                       "source", "raised_by", "created_at", "updated_at")


@admin.register(PortalDocumentShare)
class PortalDocumentShareAdmin(admin.ModelAdmin):
    # `public_token` appears in NO list_display, NO search_fields and NO filter. It is a bearer
    # credential: anything that renders it into a changelist puts a working link to a customer's
    # document into a page, a browser history and every screenshot of that page (L20).
    list_display = ("number", "tenant", "portal_account", "doc_type", "title", "expires_at",
                    "revoked_at", "download_count", "last_downloaded_at")
    list_filter = ("tenant", "doc_type")
    search_fields = ("number", "title", "portal_account__number", "portal_account__customer__name")
    date_hierarchy = "created_at"
    # `revoked_at` is written only by the admin-gated revoke verb, and the download audit trio is
    # the evidence that the share was fetched; all are read-only because an editable revoke stamp is
    # an un-revoke, and an editable download count is a forged receipt.
    #
    # **`public_token` is deliberately NOT in this tuple, and that is the opposite of an oversight.**
    # `readonly_fields` does not mean "hidden" — Django adds those names to `get_fields()` and
    # RENDERS their values on the change page. Listing the token there would print the plaintext
    # bearer credential onto a page, into a browser history and into every screenshot of it, which
    # is precisely the invariant the rest of this sub-module is built around (both staff querysets
    # `.defer()` it so it is not even loaded). The column is already `editable=False`, so it cannot
    # reach a form regardless — the entry bought nothing and cost the whole rule.
    readonly_fields = ("number", "revoked_at", "download_count", "first_viewed_at",
                       "last_downloaded_at", "shared_by", "created_at", "updated_at")
    # Belt and braces: even a future `readonly_fields` edit cannot surface it, because the change
    # form is built from this explicit list.
    fields = ("number", "tenant", "portal_account", "doc_type", "title",
              "document", "invoice", "shipment", "trade_document", "contract", "quality_inspection",
              "expires_at", "revoked_at", "download_count", "first_viewed_at", "last_downloaded_at",
              "shared_by", "created_at", "updated_at")


@admin.register(PortalActivity)
class PortalActivityAdmin(admin.ModelAdmin):
    """FULLY read-only — the StockMoveAdmin / MeterReadingAdmin posture.

    This is an append-only evidence log of what a customer read, written solely by
    ``PortalActivity.record()``. A row that can be added, edited or deleted from the admin is not
    evidence of anything: the whole value of the table in a dispute is that nobody could have
    adjusted it afterwards. Every field is ``editable=False`` on the model; these three methods are
    what stop the admin being the one place that ignores it.
    """

    list_display = ("created_at", "tenant", "portal_account", "action", "object_label", "user",
                    "ip_address")
    list_filter = ("tenant", "action")
    search_fields = ("object_label", "portal_account__number", "portal_account__customer__name")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# =================================================================================================
# 4.17 Third-Party Logistics (3PL) Management
# =================================================================================================
class ClientRateCardLineInline(admin.TabularInline):
    model = ClientRateCardLine
    extra = 0


@admin.register(LogisticsClient)
class LogisticsClientAdmin(admin.ModelAdmin):
    """The depositor master — who the client is and how we agreed to bill them.

    ``onboarded_on`` and ``last_synced_at`` are ``editable=False`` on the model (the first is stamped
    the moment status reaches ``active``, the second by an integration), so they are listed read-only
    here rather than being quietly droppable from the change form.
    """

    list_display = ("code", "party", "tenant", "status", "billing_cycle", "storage_billing_method",
                    "space_model", "contract_end", "is_active_client")
    list_filter = ("tenant", "status", "billing_cycle", "storage_billing_method", "space_model",
                   "integration_mode")
    search_fields = ("code", "number", "party__name", "client_system", "edi_partner_id")
    readonly_fields = ("number", "onboarded_on", "last_synced_at", "created_at", "updated_at")

    @admin.display(boolean=True, description="Active")
    def is_active_client(self, obj):
        return obj.status == "active"


@admin.register(ClientRateCard)
class ClientRateCardAdmin(admin.ModelAdmin):
    """Versioned pricing. ``status`` is read-only ON PURPOSE, mirroring the form.

    A card moves ``draft`` -> ``active`` -> ``superseded`` through the ``activate`` / ``supersede``
    views, which also stamp the effective window and close the previous active card for the client.
    An editable status dropdown here would be a second, unaudited way to re-price a period a billing
    run has already been calculated and approved against — the exact drift the version ladder exists
    to prevent.
    """

    list_display = ("number", "client", "name", "version", "status", "effective_from",
                    "effective_to", "tenant")
    list_filter = ("tenant", "status")
    search_fields = ("number", "name", "client__code", "client__party__name")
    inlines = [ClientRateCardLineInline]
    readonly_fields = ("number", "status", "created_at", "updated_at")


class ClientBillingRunLineInline(admin.TabularInline):
    """Read-only. These lines are the invoice's EVIDENCE, not an input.

    ``calculate()`` derives every one of them from the ``StockMove`` ledger and the active rate card,
    snapshotting the category, basis, description and rate onto the row. ``amount`` is
    ``editable=False`` (quantity x rate) and ``needs_manual_quantity`` is the calculator's own flag
    for a basis this build cannot measure. A hand-edited line would be a typed number sitting beside
    derived ones with nothing on the page to tell them apart.
    """

    model = ClientBillingRunLine
    extra = 0
    can_delete = False
    fields = ("charge_category", "charge_basis", "description", "quantity", "rate", "amount",
              "source_reference", "is_manual", "needs_manual_quantity")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ClientBillingRun)
class ClientBillingRunAdmin(admin.ModelAdmin):
    """The period's billing. Every money figure is read-only — it is DERIVED, never typed.

    ``subtotal`` / ``minimum_adjustment`` / ``total`` are written by ``calculate()`` off the ledger,
    ``status`` by the four verbs, and ``invoice`` by the hand-off that DRAFTS an
    ``accounting.Invoice`` (the run never posts a journal entry itself, L29). All are
    ``editable=False`` on the model; the tuple below is what stops the admin being the one place
    that ignores it.
    """

    list_display = ("number", "client", "period_start", "period_end", "status", "total", "invoice",
                    "tenant")
    list_filter = ("tenant", "status")
    search_fields = ("number", "client__code", "client__party__name")
    date_hierarchy = "period_end"
    inlines = [ClientBillingRunLineInline]
    readonly_fields = ("number", "status", "subtotal", "minimum_adjustment", "total",
                       "calculated_at", "approved_at", "approved_by", "invoice",
                       "created_at", "updated_at")


@admin.register(ClientSLA)
class ClientSLAAdmin(admin.ModelAdmin):
    """The commitment is editable; the MEASUREMENT is not.

    Target, threshold, window, scope and credit percentages are what the contract says, so they stay
    on the form. Everything from ``last_measured_value`` down is written only by ``recompute()``,
    which derives it from 4.5 orders / 4.6 shipments / 4.10 returns — a hand-typed achievement
    figure is precisely the number a customer would dispute, and ``status`` follows from it.
    """

    list_display = ("number", "client", "metric", "target_value", "unit", "direction",
                    "last_measured_value", "status", "is_active", "tenant")
    list_filter = ("tenant", "metric", "status", "measurement_window", "is_active")
    search_fields = ("number", "name", "client__code", "client__party__name")
    readonly_fields = ("number", "last_measured_value", "last_measured_at",
                       "measurement_window_start", "measurement_window_end", "measurement_summary",
                       "sample_size", "breach_count", "status", "created_at", "updated_at")


# =================================================================================================
# 4.18 Finance & Accounting Integration
# =================================================================================================
class LandedCostChargeInline(admin.TabularInline):
    model = LandedCostCharge
    extra = 0


@admin.register(LandedCostVoucher)
class LandedCostVoucherAdmin(admin.ModelAdmin):
    """The landed-cost envelope. The charges are editable inline; the RESULT is not.

    Every total is written by ``recalc_totals()`` off the charge lines, ``status`` by the
    allocate → accrue → draft-bill ladder, and ``bill`` by ``draft_bill()``. All of them are already
    ``editable=False`` on the model and therefore unreachable here anyway; they are named in
    ``readonly_fields`` so that a later hand dropping ``editable=False`` for an admin convenience
    does not silently open a hand-typed total — a second source of truth for money.
    """

    list_display = ("number", "goods_receipt", "party", "tenant", "cost_date", "status",
                    "allocation_basis", "actual_total", "variance_amount")
    list_filter = ("tenant", "status", "allocation_basis")
    search_fields = ("number", "party__name", "goods_receipt__number")
    readonly_fields = ("number", "status", "estimated_total", "actual_total", "variance_amount",
                       "variance_pct", "allocated_total", "accrued_at", "bill",
                       "created_at", "updated_at")
    inlines = [LandedCostChargeInline]


@admin.register(DutyTariff)
class DutyTariffAdmin(admin.ModelAdmin):
    """The HS x origin duty-rate master — the ONE table 4.18 could not reuse from ``accounting``.

    Fully editable, and safely so: the charge line SNAPSHOTS the rate ``rate_for()`` returned, so
    re-rating a tariff next quarter never restates a shipment that has already cleared customs.
    """

    list_display = ("hs_code", "country_of_origin", "tenant", "duty_rate_pct", "effective_from",
                    "effective_to", "is_active")
    list_filter = ("tenant", "is_active", "country_of_origin")
    search_fields = ("number", "hs_code", "description", "country_of_origin")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(LandedCostAllocation)
class LandedCostAllocationAdmin(admin.ModelAdmin):
    """DERIVED ledger — read-only in the admin, no add/change/delete, mirroring ``StockMoveAdmin``.

    Every row is written by ``LandedCostVoucher.allocate()`` and re-written wholesale on every
    re-allocation, so a row edited here would be silently discarded the next time the voucher was
    allocated — and, worse, would disagree with the weighted average until then. Change the charge
    and re-allocate; that is the only supported path.
    """

    list_display = ("voucher", "charge", "item", "stock_move", "tenant", "quantity", "basis_used",
                    "basis_value", "allocated_amount", "unit_cost_uplift")
    list_filter = ("tenant", "basis_used")
    search_fields = ("voucher__number", "item__sku", "item__name")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
