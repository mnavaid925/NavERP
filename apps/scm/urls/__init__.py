"""SCM URLconf package — one sub-package per NavERP sub-module (4.1-4.19), one module per entity.

Each entity module exposes its own ``urlpatterns``; this __init__ sets ``app_name = "scm"`` once and
concatenates them, so every ``scm:<name>`` reverse and ``include("apps.scm.urls")`` resolves.

Django is first-match-wins, so ORDER IS BEHAVIOUR. Keep literal routes before ``<int:pk>`` ones
within a module, and when you ADD a route with a greedy converter check it against this whole
concatenated list, not just its own module.
"""
from .ProcurementManagement.Overview import urlpatterns as _procurement_overview
from .ProcurementManagement.PurchaseRequisitions import urlpatterns as _procurement_purchaserequisitions
from .ProcurementManagement.Rfqs import urlpatterns as _procurement_rfqs
from .ProcurementManagement.PurchaseOrders import urlpatterns as _procurement_purchaseorders
from .ProcurementManagement.GoodsReceiptNotes import urlpatterns as _procurement_goodsreceiptnotes
from .SupplierRelationshipManagement.SupplierProfiles import urlpatterns as _srm_supplierprofiles
from .SupplierRelationshipManagement.SupplierScorecards import urlpatterns as _srm_scorecards
from .SupplierRelationshipManagement.SupplierContracts import urlpatterns as _srm_contracts
from .SupplierRelationshipManagement.SupplierCatalogs import urlpatterns as _srm_catalogs
from .SupplierRelationshipManagement.SupplierRiskAssessments import urlpatterns as _srm_riskassessments
from .InventoryManagement.Items import urlpatterns as _inv_items
from .InventoryManagement.Locations import urlpatterns as _inv_locations
from .InventoryManagement.LotSerials import urlpatterns as _inv_lotserials
from .InventoryManagement.StockTransfers import urlpatterns as _inv_transfers
from .InventoryManagement.StockAdjustments import urlpatterns as _inv_adjustments
from .InventoryManagement.ReorderRules import urlpatterns as _inv_reorderrules
from .InventoryManagement.Reports import urlpatterns as _inv_reports
from .WarehouseManagement.PutawayTasks import urlpatterns as _wms_putaway
from .WarehouseManagement.PickTasks import urlpatterns as _wms_picks
from .WarehouseManagement.CycleCountTasks import urlpatterns as _wms_cyclecounts
from .WarehouseManagement.YardVisits import urlpatterns as _wms_yard
from .OrderManagement.SalesOrders import urlpatterns as _oms_salesorders
from .OrderManagement.SalesOrderAllocations import urlpatterns as _oms_allocations
from .TransportationManagement.Carriers import urlpatterns as _tms_carriers
from .TransportationManagement.Loads import urlpatterns as _tms_loads
from .TransportationManagement.Shipments import urlpatterns as _tms_shipments
from .TransportationManagement.FreightInvoices import urlpatterns as _tms_freightinvoices
from .DemandPlanning.SeasonalityProfiles import urlpatterns as _dp_seasonality
from .DemandPlanning.DemandForecasts import urlpatterns as _dp_forecasts
from .DemandPlanning.DemandSignals import urlpatterns as _dp_signals
from .DemandPlanning.ForecastAdjustments import urlpatterns as _dp_adjustments
from .DemandPlanning.Reports import urlpatterns as _dp_reports
from .Manufacturing.WorkCenters import urlpatterns as _mf_workcenters
from .Manufacturing.BillsOfMaterials import urlpatterns as _mf_boms
from .Manufacturing.WorkOrders import urlpatterns as _mf_workorders
from .Manufacturing.ProductionTimeLogs import urlpatterns as _mf_timelogs
from .Manufacturing.Reports import urlpatterns as _mf_reports
from .QualityManagement.InspectionPlans import urlpatterns as _qm_inspectionplans
from .QualityManagement.QualityInspections import urlpatterns as _qm_inspections
from .QualityManagement.QualityAudits import urlpatterns as _qm_audits
from .QualityManagement.NonConformances import urlpatterns as _qm_ncrs
from .QualityManagement.CapaActions import urlpatterns as _qm_capa
from .QualityManagement.Reports import urlpatterns as _qm_reports
from .ReturnsManagement.ReturnReasons import urlpatterns as _rma_reasons
from .ReturnsManagement.ReturnPolicies import urlpatterns as _rma_policies
from .ReturnsManagement.ReturnAuthorizations import urlpatterns as _rma_authorizations
from .ReturnsManagement.ReturnDispositions import urlpatterns as _rma_dispositions
from .ReturnsManagement.WarrantyClaims import urlpatterns as _rma_warranty
from .ReturnsManagement.Reports import urlpatterns as _rma_reports
from .SupplyChainAnalytics.KpiTargets import urlpatterns as _sca_kpitargets
from .SupplyChainAnalytics.KpiSnapshots import urlpatterns as _sca_kpisnapshots
from .SupplyChainAnalytics.SupplyChainAlerts import urlpatterns as _sca_alerts
from .SupplyChainAnalytics.Reports import urlpatterns as _sca_reports


app_name = "scm"

urlpatterns = [
    *_procurement_overview,              # ProcurementManagement/Overview — "" (module landing)
    *_procurement_purchaserequisitions,  # ProcurementManagement/PurchaseRequisitions
    *_procurement_rfqs,                  # ProcurementManagement/Rfqs (incl. quotes)
    *_procurement_purchaseorders,        # ProcurementManagement/PurchaseOrders
    *_procurement_goodsreceiptnotes,     # ProcurementManagement/GoodsReceiptNotes
    *_srm_supplierprofiles,              # SupplierRelationshipManagement/SupplierProfiles
    *_srm_scorecards,                    # SupplierRelationshipManagement/SupplierScorecards
    *_srm_contracts,                     # SupplierRelationshipManagement/SupplierContracts
    *_srm_catalogs,                      # SupplierRelationshipManagement/SupplierCatalogs
    *_srm_riskassessments,               # SupplierRelationshipManagement/SupplierRiskAssessments
    *_inv_items,                         # InventoryManagement/Items (item + category + uom)
    *_inv_locations,                     # InventoryManagement/Locations
    *_inv_lotserials,                    # InventoryManagement/LotSerials
    *_inv_transfers,                     # InventoryManagement/StockTransfers
    *_inv_adjustments,                   # InventoryManagement/StockAdjustments
    *_inv_reorderrules,                  # InventoryManagement/ReorderRules
    *_inv_reports,                       # InventoryManagement/Reports (valuation/reorder/ledger/on-hand)
    *_wms_putaway,                       # WarehouseManagement/PutawayTasks
    *_wms_picks,                         # WarehouseManagement/PickTasks
    *_wms_cyclecounts,                   # WarehouseManagement/CycleCountTasks
    *_wms_yard,                          # WarehouseManagement/YardVisits
    # 4.5 uses `sales-orders/`, NOT `orders/` — that prefix is already PurchaseOrder's above and
    # Django is first-match-wins, so reusing it would permanently shadow the sales order list.
    *_oms_salesorders,                   # OrderManagement/SalesOrders
    *_oms_allocations,                   # OrderManagement/SalesOrderAllocations
    # 4.6 TMS prefixes (carriers/ loads/ shipments/ freight-invoices/) are all unique — no
    # collision with orders/ (PurchaseOrder) or sales-orders/ (SalesOrder) above.
    *_tms_carriers,                      # TransportationManagement/Carriers
    *_tms_loads,                         # TransportationManagement/Loads
    *_tms_shipments,                     # TransportationManagement/Shipments
    *_tms_freightinvoices,               # TransportationManagement/FreightInvoices
    # 4.7 prefixes (seasonality/ forecasts/ demand-signals/ forecast-adjustments/ safety-stock/
    # forecast-accuracy/) are all first-segment-unique against everything above — in particular
    # `forecasts/` does not collide with 4.1's `orders/`, 4.5's `sales-orders/` or 4.3's
    # `reorder-rules/`/`reorder-alerts/`, and `forecast-adjustments/`/`forecast-accuracy/` are
    # separate segments from `forecasts/`, so no pk route can swallow them.
    *_dp_seasonality,                    # DemandPlanning/SeasonalityProfiles
    *_dp_forecasts,                      # DemandPlanning/DemandForecasts
    *_dp_signals,                        # DemandPlanning/DemandSignals
    *_dp_adjustments,                    # DemandPlanning/ForecastAdjustments
    *_dp_reports,                        # DemandPlanning/Reports (safety stock + accuracy)
    # 4.8 prefixes (work-centers/ boms/ work-orders/ time-logs/ mrp/ production-schedule/) are all
    # first-segment-unique against everything above — `work-orders/` is a separate segment from
    # 4.1's `orders/` and 4.5's `sales-orders/`, so no pk route can swallow it, and every 4.8 verb
    # route sits under its own `<int:pk>/`.
    *_mf_workcenters,                    # Manufacturing/WorkCenters
    *_mf_boms,                           # Manufacturing/BillsOfMaterials
    *_mf_workorders,                     # Manufacturing/WorkOrders
    *_mf_timelogs,                       # Manufacturing/ProductionTimeLogs
    *_mf_reports,                        # Manufacturing/Reports (MRP + production schedule)
    # 4.9 prefixes (inspection-plans/ inspections/ quality-audits/ nonconformances/ capa/ coa/)
    # are all first-segment-unique against everything above — checked against the full list, not
    # just this block. In particular `inspections/` is a separate segment from 4.1's `receipts/`
    # and from 4.9's own `inspection-plans/`, `capa/` from 4.2's `catalogs/` and 4.1's
    # `categories/`, and `quality-audits/` avoids the bare `audits/` a Module-0 audit-log page
    # would want. Every 4.9 verb route sits under its own `<int:pk>/`, so none can be swallowed.
    *_qm_inspectionplans,                # QualityManagement/InspectionPlans (criteria master)
    *_qm_inspections,                    # QualityManagement/QualityInspections
    *_qm_audits,                         # QualityManagement/QualityAudits
    *_qm_ncrs,                           # QualityManagement/NonConformances
    *_qm_capa,                           # QualityManagement/CapaActions
    *_qm_reports,                        # QualityManagement/Reports (Certificate of Analysis)
    # ---------------------------------------------------------------------------------------
    # 4.10 COLLISION CHECK — nine new first segments, each checked against the WHOLE list above
    # and not merely against this block:
    #
    #   returns/              vs 4.1 `orders/`, 4.5 `sales-orders/`, 4.8 `work-orders/`,
    #                            4.3 `reorder-rules/`/`reorder-alerts/`, 4.1 `receipts/`
    #                            — all separate first segments; `returns/` is free.
    #   return-reasons/       ) four distinct segments, none a prefix of another as far as Django
    #   return-policies/      ) is concerned (it matches whole path components, so
    #   return-dispositions/  ) `return-tracking/` cannot be captured by `returns/<int:pk>/`).
    #   return-tracking/      )
    #   returns-bench/        — distinct from `returns/`: `returns-bench` is ONE component and is
    #                           never split at the hyphen.
    #   refund-queue/ · return-portal/ · warranty-claims/ — no prior segment starts with
    #                           refund, portal or warranty anywhere in the app.
    #
    # `return-tracking/<str:token>/` is the module's only greedy converter and it sits ALONE on
    # its own first segment, so it can neither shadow nor be shadowed by any pk route. Within each
    # block below, literal routes (`add/`) precede the `<int:pk>/` ones.
    *_rma_reasons,                       # ReturnsManagement/ReturnReasons (master, no bullet)
    *_rma_policies,                      # ReturnsManagement/ReturnPolicies (master, no bullet)
    *_rma_authorizations,                # ReturnsManagement/ReturnAuthorizations (the RMA)
    *_rma_dispositions,                  # ReturnsManagement/ReturnDispositions (the bench)
    *_rma_warranty,                      # ReturnsManagement/WarrantyClaims
    *_rma_reports,                       # ReturnsManagement/Reports (queues + portal + public)
    # ---------------------------------------------------------------------------------------
    # 4.11 COLLISION CHECK — eight new first segments, each checked against the WHOLE list above
    # and not merely against this block:
    #
    #   kpi-targets/ · kpi-snapshots/  — nothing anywhere in the app starts with `kpi`. Both are
    #                           distinct whole components, so neither can swallow the other.
    #   alerts/               — 4.3 owns `reorder-alerts/`. Django matches WHOLE path components
    #                           and never splits at a hyphen, so `alerts` and `reorder-alerts` are
    #                           unrelated segments and neither shadows the other. Do NOT "tidy"
    #                           either one to match the other.
    #   disruption-risk/      — 4.2 owns `risk-assessments/`. Again a distinct first component;
    #                           `disruption-risk` is one component, not `disruption` + `risk`.
    #   inventory-analytics/ · spend-analytics/ · logistics-kpis/ · margin-analytics/
    #                         — nothing existing starts with inventory, spend, logistics or margin.
    #
    # The CSV exports are literal `export/` sub-routes under segments already claimed above, so
    # they add ZERO new first segments and zero new collision surface.
    #
    # 4.11 introduces NO greedy `<str:…>` converter — 4.10's `return-tracking/<str:token>/` remains
    # the module's only one, and it sits alone on its own first segment. Within each module below,
    # literal routes (`add/`, `export/`, `capture/`, `detect/`) precede every `<int:pk>/` one.
    *_sca_kpitargets,                    # SupplyChainAnalytics/KpiTargets (the target master)
    *_sca_kpisnapshots,                  # SupplyChainAnalytics/KpiSnapshots (frozen history)
    *_sca_alerts,                        # SupplyChainAnalytics/SupplyChainAlerts (the inbox)
    *_sca_reports,                       # SupplyChainAnalytics/Reports (the five bullet pages)
]
