"""Inventory URLconf package — one sub-package per NavERP sub-module, one module per entity.

Each entity module exposes its own ``urlpatterns``; this __init__ sets ``app_name = "inventory"``
once and concatenates them.

Django is first-match-wins: within each module the literal routes (`add/`) precede the
``<int:pk>`` ones. The app introduces NO greedy ``<str:…>`` converter, so there is no cross-module
shadowing surface to reason about; the first segments (`""`, `attributes/`, `prices/`,
`files/`, `putaway-rules/`, `putaway-suggestions/`, `waves/`, `waves-board/`,
`networks/`, `global-stock/`,
`vendor-communications/`,
`bin-capacity/`, `cross-dock/`, `warehouse-map/`, `transfers/`, `lot-rules/`,
`lot-generate/`, `shelf-life-policies/`, `fefo-board/`, `traceability/`,
`count-programs/`, `physical-inventory/`, `variance-report/`,
`stock-level-plans/`, `planning-board/`, `labels/`, `sessions/`, `console/`, `tags/`,
`alerts/`, `alerts/rules/`, `alerts/deliveries/`,
`reports/valuation/`, `reports/turnover/`, `reports/aging/`, `reports/abc/`,
`snapshots/`,
`tracking/stock-levels/`, `tracking/stock-status/`, `tracking/reservations/`,
`channels/`, `listings/`, `runs/`, `api-clients/`) are
distinct whole components and none can swallow another.
"""
from .Catalog.ItemAttributes import urlpatterns as _cat_itemattributes
from .Catalog.ItemPrices import urlpatterns as _cat_itemprices
from .Catalog.ProductFiles import urlpatterns as _cat_productfiles
from .BarcodeRfidIntegration import urlpatterns as _br_barcode
from .AlertsNotifications import urlpatterns as _an_alerts
from .AccountingFinancialIntegration import urlpatterns as _fin_finint
from .Catalog.Overview import urlpatterns as _cat_overview
from .FulfillmentOrchestration.FulfillmentWaves import urlpatterns as _fo_waves
from .InventoryTrackingControl.InventoryReservations import urlpatterns as _tc_reservations
from .InventoryTrackingControl.StockLevels import urlpatterns as _tc_stocklevels
from .InventoryTrackingControl.StockStatuses import urlpatterns as _tc_stockstatuses
from .ForecastingPlanning import urlpatterns as _fp_forecasting
from .LotSerialTracking import urlpatterns as _lst_lotserial
from .MultiLocationManagement.LocationNetworks import urlpatterns as _mlm_locationnetworks
from .StocktakingCycleCounting import urlpatterns as _stk_stocktake
from .PurchaseOrderManagement.ApprovalRules import urlpatterns as _po_approvalrules
from .PurchaseOrderManagement.Approvals import urlpatterns as _po_approvals
from .PurchaseOrderManagement.Dispatches import urlpatterns as _po_dispatches
from .PurchaseOrderManagement.ReorderDrafts import urlpatterns as _po_reorderdrafts
from .ReceivingPutaway.PutawayRules import urlpatterns as _rp_putawayrules
from .ReturnsManagement import urlpatterns as _rm_returns
from .StockMovementTransfers import urlpatterns as _smt_transfers
from .VendorSupplierManagement.VendorCommunications import urlpatterns as _vsm_vendorcommunications
from .WarehousingBinManagement.BinCapacities import urlpatterns as _wh_bincapacities
from .WarehousingBinManagement.CrossDockOrders import urlpatterns as _wh_crossdockorders
from .WarehousingBinManagement.WarehouseMap import urlpatterns as _wh_warehousemap
from .QualityControl import urlpatterns as _qc_qualitycontrol
from .ReportingAnalytics import urlpatterns as _ra_reportinganalytics
from .ThirdPartyIntegrations import urlpatterns as _tpi_integrations
from .UnitsOfMeasure import urlpatterns as _uom_units


app_name = "inventory"

urlpatterns = [
    *_cat_overview,        # Catalog/Overview — "" (module landing)
    *_cat_itemattributes,  # Catalog/ItemAttributes
    *_cat_itemprices,      # Catalog/ItemPrices
    *_cat_productfiles,    # Catalog/ProductFiles
    *_po_approvalrules,    # PurchaseOrderManagement/ApprovalRules
    *_po_approvals,        # PurchaseOrderManagement/Approvals (queue + tier verbs)
    *_po_dispatches,       # PurchaseOrderManagement/Dispatches
    *_po_reorderdrafts,    # PurchaseOrderManagement/ReorderDrafts
    *_rp_putawayrules,     # ReceivingPutaway/PutawayRules (+ computed suggestions page)
    *_fo_waves,            # FulfillmentOrchestration/FulfillmentWaves (CRUD + verbs + board)
    *_mlm_locationnetworks,  # MultiLocationManagement/LocationNetworks (CRUD + global stock page)
    *_rm_returns,          # ReturnsManagement (inspections, disposition rules, workbench)
    *_br_barcode,          # BarcodeRfidIntegration (labels, scan console/sessions, RFID tags)
    *_an_alerts,           # AlertsNotifications (inbox, rule catalog, dispatch log)
    *_smt_transfers,       # StockMovementTransfers (board/queue/panel + verbs, routes, rules)
    *_vsm_vendorcommunications,  # VendorSupplierManagement/VendorCommunications
    *_wh_bincapacities,    # WarehousingBinManagement/BinCapacities
    *_wh_crossdockorders,  # WarehousingBinManagement/CrossDockOrders (CRUD + lifecycle verbs)
    *_wh_warehousemap,     # WarehousingBinManagement/WarehouseMap (computed page)
    *_tc_stocklevels,      # InventoryTrackingControl/StockLevels (computed page)
    *_tc_stockstatuses,    # InventoryTrackingControl/StockStatuses (CRUD)
    *_tc_reservations,     # InventoryTrackingControl/InventoryReservations (CRUD + lifecycle verbs)
    *_lst_lotserial,       # LotSerialTracking (rules/generate/policies CRUD + FEFO board + trace)
    *_stk_stocktake,       # StocktakingCycleCounting (programs + physical inventory + variance report)
    *_fp_forecasting,      # ForecastingPlanning (seasonal plans CRUD + ROP/safety-stock board)
    *_qc_qualitycontrol,   # QualityControl (checklists, routing rules, quarantine, defects)
    *_ra_reportinganalytics,  # ReportingAnalytics (4 computed reports + IRS- snapshots)
    *_fin_finint,          # AccountingFinancialIntegration (AP/AR sync, JE automation, tax & GL rules)
    *_tpi_integrations,    # ThirdPartyIntegrations (channels, listing maps, sync runs, API clients)
    *_uom_units,           # UnitsOfMeasure (conversion matrix CRUD + calculator)
]

