"""SCM views package — one sub-package per NavERP sub-module (4.1-4.19), one module per entity.

This __init__ re-exports EVERY view so the apps/scm/urls/ package's ``views.<name>`` lookups
resolve. Adding a view without adding it here is a bug — the URLconf will AttributeError at import.
"""
from ._helpers import *  # noqa: F401,F403

# 4.1 Procurement Management
from .ProcurementManagement.Overview import (  # noqa: F401
    overview,
)
from .ProcurementManagement.PurchaseRequisitions import (  # noqa: F401
    requisition_list,
    requisition_create,
    requisition_detail,
    requisition_edit,
    requisition_delete,
    requisition_submit,
    requisition_approve,
    requisition_reject,
)
from .ProcurementManagement.Rfqs import (  # noqa: F401
    rfq_list,
    rfq_create,
    rfq_detail,
    rfq_edit,
    rfq_delete,
    rfq_send,
    rfq_close,
    rfq_compare,
    quote_create,
    quote_edit,
    quote_delete,
    quote_award,
)
from .ProcurementManagement.PurchaseOrders import (  # noqa: F401
    purchaseorder_list,
    purchaseorder_create,
    purchaseorder_detail,
    purchaseorder_edit,
    purchaseorder_delete,
    purchaseorder_amend,
    purchaseorder_submit,
    purchaseorder_approve,
    purchaseorder_send,
    purchaseorder_acknowledge,
    purchaseorder_cancel,
    purchaseorder_close,
)
from .ProcurementManagement.GoodsReceiptNotes import (  # noqa: F401
    goodsreceipt_list,
    goodsreceipt_create,
    goodsreceipt_detail,
    goodsreceipt_edit,
    goodsreceipt_delete,
    goodsreceipt_receive,
    goodsreceipt_cancel,
    goodsreceipt_rematch,
)

# 4.2 Supplier Relationship Management
from .SupplierRelationshipManagement.SupplierProfiles import (  # noqa: F401
    supplierprofile_list,
    supplierprofile_create,
    supplierprofile_detail,
    supplierprofile_edit,
    supplierprofile_delete,
    supplierprofile_submit,
    supplierprofile_approve,
    supplierprofile_reject,
    supplierprofile_reopen,
    supplierprofile_suspend,
)
from .SupplierRelationshipManagement.SupplierScorecards import (  # noqa: F401
    scorecard_list,
    scorecard_create,
    scorecard_detail,
    scorecard_edit,
    scorecard_delete,
    scorecard_recompute,
    scorecard_publish,
)
from .SupplierRelationshipManagement.SupplierContracts import (  # noqa: F401
    contract_list,
    contract_create,
    contract_detail,
    contract_edit,
    contract_delete,
    contract_activate,
    contract_renew,
    contract_terminate,
)
from .SupplierRelationshipManagement.SupplierCatalogs import (  # noqa: F401
    catalog_list,
    catalog_create,
    catalog_detail,
    catalog_edit,
    catalog_delete,
    catalog_activate,
)
from .SupplierRelationshipManagement.SupplierRiskAssessments import (  # noqa: F401
    riskassessment_list,
    riskassessment_create,
    riskassessment_detail,
    riskassessment_edit,
    riskassessment_delete,
    riskassessment_submit,
    riskassessment_review,
)

# 4.3 Inventory Management
from .InventoryManagement.Items import (  # noqa: F401
    item_list, item_create, item_detail, item_edit, item_delete,
    category_list, category_create, category_edit, category_delete,
    uom_list, uom_create, uom_edit, uom_delete,
)
from .InventoryManagement.Locations import (  # noqa: F401
    location_list, location_create, location_detail, location_edit, location_delete,
)
from .InventoryManagement.LotSerials import (  # noqa: F401
    lotserial_list, lotserial_create, lotserial_detail, lotserial_edit, lotserial_delete,
)
from .InventoryManagement.StockTransfers import (  # noqa: F401
    stocktransfer_list, stocktransfer_create, stocktransfer_detail, stocktransfer_edit,
    stocktransfer_delete, stocktransfer_complete, stocktransfer_cancel,
)
from .InventoryManagement.StockAdjustments import (  # noqa: F401
    stockadjustment_list, stockadjustment_create, stockadjustment_detail, stockadjustment_edit,
    stockadjustment_delete, stockadjustment_post, stockadjustment_cancel,
)
from .InventoryManagement.ReorderRules import (  # noqa: F401
    reorderrule_list, reorderrule_create, reorderrule_detail, reorderrule_edit, reorderrule_delete,
)
from .InventoryManagement.Reports import (  # noqa: F401
    valuation_report, reorder_alerts, stock_ledger, on_hand_by_location,
)

# 4.4 Warehouse Management
from .WarehouseManagement.PutawayTasks import (  # noqa: F401
    putawaytask_list, putawaytask_create, putawaytask_detail, putawaytask_edit,
    putawaytask_delete, putawaytask_start, putawaytask_complete, putawaytask_cancel,
)
from .WarehouseManagement.PickTasks import (  # noqa: F401
    picktask_list, picktask_create, picktask_detail, picktask_edit, picktask_delete,
    picktask_release, picktask_start, picktask_confirm, picktask_pack, picktask_cancel,
)
from .WarehouseManagement.CycleCountTasks import (  # noqa: F401
    cyclecounttask_list, cyclecounttask_create, cyclecounttask_detail, cyclecounttask_edit,
    cyclecounttask_delete, cyclecounttask_start, cyclecounttask_complete,
    cyclecounttask_reconcile, cyclecounttask_cancel,
)
from .WarehouseManagement.YardVisits import (  # noqa: F401
    yardvisit_list, yardvisit_create, yardvisit_detail, yardvisit_edit, yardvisit_delete,
    yardvisit_arrive, yardvisit_dock, yardvisit_depart, yardvisit_cancel,
)

# 4.5 Order Management System (OMS)
from .OrderManagement.SalesOrders import (  # noqa: F401
    salesorder_list, salesorder_create, salesorder_detail, salesorder_edit, salesorder_delete,
    salesorder_submit, salesorder_release_hold, salesorder_fulfill, salesorder_mark_delivered,
    salesorder_mark_invoiced, salesorder_cancel, salesorder_close, salesorder_create_from_quote,
)
from .OrderManagement.SalesOrderAllocations import (  # noqa: F401
    salesorderallocation_list, salesorderallocation_detail, salesorderallocation_create,
    salesorderallocation_edit, salesorderallocation_delete, salesorderallocation_release,
    salesorderallocation_cancel,
)

# 4.6 Transportation Management System (TMS)
from .TransportationManagement.Carriers import (  # noqa: F401
    carrier_list, carrier_create, carrier_detail, carrier_edit, carrier_delete,
    carrier_recompute_scorecard,
)
from .TransportationManagement.Loads import (  # noqa: F401
    load_list, load_create, load_detail, load_edit, load_delete,
    load_tender, load_book, load_dispatch, load_deliver, load_cancel,
)
from .TransportationManagement.Shipments import (  # noqa: F401
    shipment_list, shipment_create, shipment_detail, shipment_edit, shipment_delete,
    shipment_book, shipment_add_event, shipment_cancel,
)
from .TransportationManagement.FreightInvoices import (  # noqa: F401
    freightinvoice_list, freightinvoice_create, freightinvoice_detail, freightinvoice_edit,
    freightinvoice_delete, freightinvoice_run_audit, freightinvoice_dispute,
    freightinvoice_approve, freightinvoice_reject, freightinvoice_handoff,
)

# 4.7 Demand Planning & Forecasting
from .DemandPlanning.SeasonalityProfiles import (  # noqa: F401
    seasonalityprofile_list, seasonalityprofile_create, seasonalityprofile_detail,
    seasonalityprofile_edit, seasonalityprofile_delete, seasonalityprofile_derive,
)
from .DemandPlanning.DemandForecasts import (  # noqa: F401
    demandforecast_list, demandforecast_create, demandforecast_detail, demandforecast_edit,
    demandforecast_delete, demandforecast_generate, demandforecast_submit_review,
    demandforecast_approve, demandforecast_archive, demandforecast_revise,
)
from .DemandPlanning.DemandSignals import (  # noqa: F401
    demandsignal_list, demandsignal_create, demandsignal_detail, demandsignal_edit,
    demandsignal_delete, demandsignal_detect, demandsignal_review, demandsignal_apply,
    demandsignal_dismiss,
)
from .DemandPlanning.ForecastAdjustments import (  # noqa: F401
    forecastadjustment_list, forecastadjustment_create, forecastadjustment_detail,
    forecastadjustment_edit, forecastadjustment_delete, forecastadjustment_accept,
    forecastadjustment_reject,
)
from .DemandPlanning.Reports import (  # noqa: F401
    safety_stock_report, safety_stock_recalculate, safety_stock_apply, forecast_accuracy_report,
)

# 4.8 Manufacturing / Production
from .Manufacturing.WorkCenters import (  # noqa: F401
    workcenter_list, workcenter_create, workcenter_detail, workcenter_edit, workcenter_delete,
)
from .Manufacturing.BillsOfMaterials import (  # noqa: F401
    billofmaterials_list, billofmaterials_create, billofmaterials_detail, billofmaterials_edit,
    billofmaterials_delete,
)
from .Manufacturing.WorkOrders import (  # noqa: F401
    workorder_list, workorder_create, workorder_detail, workorder_edit, workorder_delete,
    workorder_plan, workorder_release, workorder_close, workorder_cancel, workorder_schedule,
    workorder_issue_components, workorder_report_production,
)
from .Manufacturing.ProductionTimeLogs import (  # noqa: F401
    productiontimelog_list, productiontimelog_create, productiontimelog_detail,
    productiontimelog_edit, productiontimelog_delete,
)
from .Manufacturing.Reports import (  # noqa: F401
    mrp_report, production_schedule,
)

# 4.9 Quality Management System (QMS)
from .QualityManagement.InspectionPlans import (  # noqa: F401
    inspectionplan_list, inspectionplan_create, inspectionplan_detail, inspectionplan_edit,
    inspectionplan_delete,
)
from .QualityManagement.QualityInspections import (  # noqa: F401
    qualityinspection_list, qualityinspection_create, qualityinspection_detail,
    qualityinspection_edit, qualityinspection_delete, qualityinspection_generate_results,
    qualityinspection_start, qualityinspection_complete, qualityinspection_hold,
    qualityinspection_resume, qualityinspection_cancel, qualityinspection_decide,
    qualityinspection_quarantine, qualityinspection_release_lot, qualityinspection_raise_ncr,
)
from .QualityManagement.QualityAudits import (  # noqa: F401
    qualityaudit_list, qualityaudit_create, qualityaudit_detail, qualityaudit_edit,
    qualityaudit_delete, qualityaudit_start, qualityaudit_complete, qualityaudit_close,
    qualityaudit_cancel, qualityaudit_add_finding, qualityaudit_print,
)
from .QualityManagement.NonConformances import (  # noqa: F401
    nonconformance_list, nonconformance_create, nonconformance_detail, nonconformance_edit,
    nonconformance_delete, nonconformance_investigate, nonconformance_quarantine,
    nonconformance_release_lot, nonconformance_disposition, nonconformance_close,
    nonconformance_cancel, nonconformance_raise_capa,
)
from .QualityManagement.CapaActions import (  # noqa: F401
    capaaction_list, capaaction_create, capaaction_detail, capaaction_edit, capaaction_delete,
    capaaction_start, capaaction_progress, capaaction_implement, capaaction_verify,
    capaaction_cancel,
)
from .QualityManagement.Reports import (  # noqa: F401
    coa_report, coa_issue, coa_print,
)

# 4.10 Returns Management (Reverse Logistics)
from .ReturnsManagement.ReturnReasons import (  # noqa: F401
    returnreason_list, returnreason_create, returnreason_detail, returnreason_edit,
    returnreason_delete,
)
from .ReturnsManagement.ReturnPolicies import (  # noqa: F401
    returnpolicy_list, returnpolicy_create, returnpolicy_detail, returnpolicy_edit,
    returnpolicy_delete,
)
from .ReturnsManagement.ReturnAuthorizations import (  # noqa: F401
    returnauthorization_list, returnauthorization_create, returnauthorization_detail,
    returnauthorization_edit, returnauthorization_delete, returnauthorization_approve,
    returnauthorization_reject, returnauthorization_cancel, returnauthorization_receive_all,
    returnauthorization_draft_credit_note, returnauthorization_draft_replacement,
    returnauthorization_raise_warranty_claim,
)
from .ReturnsManagement.ReturnDispositions import (  # noqa: F401
    returndisposition_list, returndisposition_create, returndisposition_detail,
    returndisposition_edit, returndisposition_delete, returndisposition_decide,
    returndisposition_post, returndisposition_split, returndisposition_mark_refurbished,
)
from .ReturnsManagement.WarrantyClaims import (  # noqa: F401
    warrantyclaim_list, warrantyclaim_create, warrantyclaim_detail, warrantyclaim_edit,
    warrantyclaim_delete, warrantyclaim_submit, warrantyclaim_record_response,
    warrantyclaim_record_credit,
)
from .ReturnsManagement.Reports import (  # noqa: F401
    refund_queue, returns_awaiting_disposition, advance_refund_exposure, return_portal,
    portal_return_create, returnauthorization_public, returnauthorization_label,
)

# 4.11 Supply Chain Analytics
# 33 callables (6 target + 5 snapshot + 12 alert + 10 report). A view missing here is an
# AttributeError the MOMENT the URLconf loads —
# not at first request — because apps/scm/urls/ resolves every route through ``views.<name>``.
# ``open_alert_count`` is exported too: the five report pages import it for their header chip.
from .SupplyChainAnalytics.KpiTargets import (  # noqa: F401
    kpitarget_list, kpitarget_create, kpitarget_detail, kpitarget_edit, kpitarget_delete,
    kpitarget_snapshot,
)
from .SupplyChainAnalytics.KpiSnapshots import (  # noqa: F401
    kpisnapshot_list, kpisnapshot_detail, kpisnapshot_delete, kpisnapshot_capture,
    kpisnapshot_export,
)
from .SupplyChainAnalytics.SupplyChainAlerts import (  # noqa: F401
    supplychainalert_list, supplychainalert_create, supplychainalert_detail,
    supplychainalert_edit, supplychainalert_delete, supplychainalert_acknowledge,
    supplychainalert_assign, supplychainalert_snooze, supplychainalert_resolve,
    supplychainalert_dismiss, supplychainalert_detect, open_alert_count,
)
from .SupplyChainAnalytics.Reports import (  # noqa: F401
    inventory_analytics, inventory_analytics_export,
    spend_analytics, spend_analytics_export,
    logistics_kpis, logistics_kpis_export,
    margin_analytics, margin_analytics_export,
    disruption_risk, disruption_risk_export,
)
