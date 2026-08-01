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
    readonly_fields = ("number", "status", "created_at", "updated_at")


@admin.register(TradeLicense)
class TradeLicenseAdmin(admin.ModelAdmin):
    list_display = ("number", "tenant", "license_number", "title", "license_type", "status",
                    "issue_date", "expiry_date")
    list_filter = ("tenant", "status", "license_type", "expiry_date")
    search_fields = ("number", "license_number", "title", "issuing_authority")
    date_hierarchy = "expiry_date"
    readonly_fields = ("number", "status", "created_at", "updated_at")


@admin.register(SustainabilityAssessment)
class SustainabilityAssessmentAdmin(admin.ModelAdmin):
    list_display = ("number", "tenant", "party", "assessment_date", "source", "status",
                    "overall_score")
    list_filter = ("tenant", "status", "source", "assessment_date")
    search_fields = ("number", "party__name")
    date_hierarchy = "assessment_date"
    # overall_score is DERIVED from the theme scores — it is editable=False on the model precisely so
    # the headline number can never disagree with the components it is computed from.
    readonly_fields = ("number", "overall_score", "created_at", "updated_at")
