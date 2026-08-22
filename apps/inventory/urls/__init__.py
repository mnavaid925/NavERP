"""Inventory URLconf package — one sub-package per NavERP sub-module, one module per entity.

Each entity module exposes its own ``urlpatterns``; this __init__ sets ``app_name = "inventory"``
once and concatenates them.

Django is first-match-wins: within each module the literal routes (`add/`) precede the
``<int:pk>`` ones. The app introduces NO greedy ``<str:…>`` converter, so there is no cross-module
shadowing surface to reason about; the first segments (`""`, `attributes/`, `prices/`,
`files/`, `putaway-rules/`, `putaway-suggestions/`, `vendor-communications/`,
`bin-capacity/`, `cross-dock/`, `warehouse-map/`,
`tracking/stock-levels/`, `tracking/stock-status/`, `tracking/reservations/`) are
distinct whole components and none can swallow another.
"""
from .Catalog.ItemAttributes import urlpatterns as _cat_itemattributes
from .Catalog.ItemPrices import urlpatterns as _cat_itemprices
from .Catalog.ProductFiles import urlpatterns as _cat_productfiles
from .Catalog.Overview import urlpatterns as _cat_overview
from .InventoryTrackingControl.InventoryReservations import urlpatterns as _tc_reservations
from .InventoryTrackingControl.StockLevels import urlpatterns as _tc_stocklevels
from .InventoryTrackingControl.StockStatuses import urlpatterns as _tc_stockstatuses
from .PurchaseOrderManagement.ApprovalRules import urlpatterns as _po_approvalrules
from .PurchaseOrderManagement.Approvals import urlpatterns as _po_approvals
from .PurchaseOrderManagement.Dispatches import urlpatterns as _po_dispatches
from .PurchaseOrderManagement.ReorderDrafts import urlpatterns as _po_reorderdrafts
from .ReceivingPutaway.PutawayRules import urlpatterns as _rp_putawayrules
from .VendorSupplierManagement.VendorCommunications import urlpatterns as _vsm_vendorcommunications
from .WarehousingBinManagement.BinCapacities import urlpatterns as _wh_bincapacities
from .WarehousingBinManagement.CrossDockOrders import urlpatterns as _wh_crossdockorders
from .WarehousingBinManagement.WarehouseMap import urlpatterns as _wh_warehousemap


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
    *_vsm_vendorcommunications,  # VendorSupplierManagement/VendorCommunications
    *_wh_bincapacities,    # WarehousingBinManagement/BinCapacities
    *_wh_crossdockorders,  # WarehousingBinManagement/CrossDockOrders (CRUD + lifecycle verbs)
    *_wh_warehousemap,     # WarehousingBinManagement/WarehouseMap (computed page)
    *_tc_stocklevels,      # InventoryTrackingControl/StockLevels (computed page)
    *_tc_stockstatuses,    # InventoryTrackingControl/StockStatuses (CRUD)
    *_tc_reservations,     # InventoryTrackingControl/InventoryReservations (CRUD + lifecycle verbs)
]
