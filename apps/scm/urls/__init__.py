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
]
