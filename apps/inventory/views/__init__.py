"""Inventory views package — one sub-package per NavERP sub-module, one module per entity.

Re-exports every view so the URLconf's ``views.<name>`` resolves.
"""
from .Catalog.ItemAttributes import (
    itemattribute_create,
    itemattribute_delete,
    itemattribute_detail,
    itemattribute_edit,
    itemattribute_list,
)
from .Catalog.ItemPrices import (
    itemprice_create,
    itemprice_delete,
    itemprice_detail,
    itemprice_edit,
    itemprice_list,
)
from .BarcodeRfidIntegration import (
    barcodelabel_list, barcodelabel_detail, barcodelabel_create,
    barcodelabel_edit, barcodelabel_delete, barcodelabel_print, barcodelabel_render,
    barcodelabel_void,
    scan_console, scansession_list, scansession_detail, scansession_create,
    scansession_edit, scansession_close, scansession_delete,
    rfidtag_list, rfidtag_detail, rfidtag_create, rfidtag_edit, rfidtag_delete,
    rfidtag_activate, rfidtag_retire, rfidtag_mark_lost, rfidtag_bulkread,
)
from .Catalog.Overview import overview
from .FulfillmentOrchestration.FulfillmentWaves import (
    wave_board,
    wave_cancel,
    wave_close,
    wave_create,
    wave_delete,
    wave_detail,
    wave_edit,
    wave_list,
    wave_release,
    waveorder_add,
    waveorder_remove,
)
from .Catalog.ProductFiles import (
    productfile_create,
    productfile_delete,
    productfile_detail,
    productfile_edit,
    productfile_list,
)
from .InventoryTrackingControl.InventoryReservations import (
    reservation_cancel,
    reservation_consume,
    reservation_create,
    reservation_delete,
    reservation_detail,
    reservation_edit,
    reservation_list,
    reservation_release,
)
from .InventoryTrackingControl.StockLevels import stocklevels
from .InventoryTrackingControl.StockStatuses import (
    stockstatus_create,
    stockstatus_delete,
    stockstatus_detail,
    stockstatus_edit,
    stockstatus_list,
)
from .StocktakingCycleCounting.CountPrograms import (
    countprogram_create,
    countprogram_delete,
    countprogram_detail,
    countprogram_edit,
    countprogram_list,
    countprogram_run,
)
from .StocktakingCycleCounting.PhysicalInventories import (
    physicalinventory_cancel,
    physicalinventory_create,
    physicalinventory_delete,
    physicalinventory_detail,
    physicalinventory_edit,
    physicalinventory_list,
    physicalinventory_reconcile,
    physicalinventory_start,
)
from .StocktakingCycleCounting.VarianceReport import variance_report
from .ForecastingPlanning.PlanningBoard import planning_apply_computed, planning_board
from .ForecastingPlanning.StockLevelPlans import (
    stocklevelplan_activate,
    stocklevelplan_archive,
    stocklevelplan_create,
    stocklevelplan_delete,
    stocklevelplan_detail,
    stocklevelplan_edit,
    stocklevelplan_list,
)
from .LotSerialTracking.FefoBoard import fefo_board
from .LotSerialTracking.LotNumberRules import (
    lot_generate,
    lotrule_create,
    lotrule_delete,
    lotrule_detail,
    lotrule_edit,
    lotrule_list,
)
from .LotSerialTracking.ShelfLifePolicies import (
    shelflifepolicy_create,
    shelflifepolicy_delete,
    shelflifepolicy_detail,
    shelflifepolicy_edit,
    shelflifepolicy_list,
)
from .LotSerialTracking.Traceability import traceability
from .MultiLocationManagement.GlobalStock import global_stock
from .MultiLocationManagement.LocationNetworks import (
    locationnetwork_create,
    locationnetwork_delete,
    locationnetwork_detail,
    locationnetwork_edit,
    locationnetwork_list,
)
from .PurchaseOrderManagement.ApprovalRules import (
    approvalrule_create,
    approvalrule_delete,
    approvalrule_detail,
    approvalrule_edit,
    approvalrule_list,
)
from .PurchaseOrderManagement.Approvals import (
    approval_queue,
    approval_tier_approve,
    approval_tier_reject,
)
from .PurchaseOrderManagement.Dispatches import (
    dispatch_create,
    dispatch_delete,
    dispatch_detail,
    dispatch_list,
)
from .PurchaseOrderManagement.ReorderDrafts import reorderdraft
from .ReceivingPutaway.PutawayRules import (
    putaway_suggestions,
    putawayrule_create,
    putawayrule_delete,
    putawayrule_detail,
    putawayrule_edit,
    putawayrule_list,
)
from .ReturnsManagement import (
    dispositionrule_create,
    dispositionrule_delete,
    dispositionrule_detail,
    dispositionrule_edit,
    dispositionrule_list,
    returninspection_create,
    returninspection_delete,
    returninspection_detail,
    returninspection_edit,
    returninspection_list,
    returns_workbench,
)
from .StockMovementTransfers.ApprovalRules import (
    transferapprovalrule_create,
    transferapprovalrule_delete,
    transferapprovalrule_detail,
    transferapprovalrule_edit,
    transferapprovalrule_list,
)
from .StockMovementTransfers.TransferRoutes import (
    transferroute_create,
    transferroute_delete,
    transferroute_detail,
    transferroute_edit,
    transferroute_list,
)
from .StockMovementTransfers.Transfers import (
    transfer_board,
    transfer_detail_panel,
    transfer_queue,
    transfer_submit,
    transfer_tier_approve,
    transfer_tier_reject,
)
from .VendorSupplierManagement.VendorCommunications import (
    vendorcommunication_create,
    vendorcommunication_delete,
    vendorcommunication_detail,
    vendorcommunication_edit,
    vendorcommunication_list,
)
from .WarehousingBinManagement.BinCapacities import (
    bincapacity_create,
    bincapacity_delete,
    bincapacity_detail,
    bincapacity_edit,
    bincapacity_list,
)
from .WarehousingBinManagement.CrossDockOrders import (
    crossdockorder_cancel,
    crossdockorder_create,
    crossdockorder_delete,
    crossdockorder_detail,
    crossdockorder_edit,
    crossdockorder_list,
    crossdockorder_receive,
    crossdockorder_ship,
)
from .WarehousingBinManagement.WarehouseMap import warehousemap

__all__ = [
    "overview",
    "itemattribute_list", "itemattribute_detail", "itemattribute_create",
    "itemattribute_edit", "itemattribute_delete",
    "itemprice_list", "itemprice_detail", "itemprice_create",
    "itemprice_edit", "itemprice_delete",
    "productfile_list", "productfile_detail", "productfile_create",
    "productfile_edit", "productfile_delete",
    "vendorcommunication_list", "vendorcommunication_detail", "vendorcommunication_create",
    "vendorcommunication_edit", "vendorcommunication_delete",
    "approvalrule_list", "approvalrule_detail", "approvalrule_create",
    "approvalrule_edit", "approvalrule_delete",
    "approval_queue", "approval_tier_approve", "approval_tier_reject",
    "dispatch_list", "dispatch_detail", "dispatch_create", "dispatch_delete",
    "reorderdraft",
    "putawayrule_list", "putawayrule_detail", "putawayrule_create",
    "putawayrule_edit", "putawayrule_delete",
    "putaway_suggestions",
    "bincapacity_list", "bincapacity_detail", "bincapacity_create",
    "bincapacity_edit", "bincapacity_delete",
    "crossdockorder_list", "crossdockorder_detail", "crossdockorder_create",
    "crossdockorder_edit", "crossdockorder_delete",
    "crossdockorder_receive", "crossdockorder_ship", "crossdockorder_cancel",
    "warehousemap",
    "stocklevels",
    "stockstatus_list", "stockstatus_detail", "stockstatus_create",
    "stockstatus_edit", "stockstatus_delete",
    "reservation_list", "reservation_detail", "reservation_create",
    "reservation_edit", "reservation_delete",
    "reservation_release", "reservation_consume", "reservation_cancel",
    "lotrule_list", "lotrule_detail", "lotrule_create",
    "lotrule_edit", "lotrule_delete", "lot_generate",
    "shelflifepolicy_list", "shelflifepolicy_detail", "shelflifepolicy_create",
    "shelflifepolicy_edit", "shelflifepolicy_delete",
    "fefo_board", "traceability",
    "locationnetwork_list", "locationnetwork_detail", "locationnetwork_create",
    "locationnetwork_edit", "locationnetwork_delete",
    "global_stock",
    "countprogram_list", "countprogram_detail", "countprogram_create",
    "countprogram_edit", "countprogram_delete", "countprogram_run",
    "physicalinventory_list", "physicalinventory_detail", "physicalinventory_create",
    "physicalinventory_edit", "physicalinventory_delete",
    "physicalinventory_start", "physicalinventory_reconcile", "physicalinventory_cancel",
    "variance_report",
    "stocklevelplan_list", "stocklevelplan_detail", "stocklevelplan_create",
    "stocklevelplan_edit", "stocklevelplan_delete",
    "stocklevelplan_activate", "stocklevelplan_archive",
    "planning_board", "planning_apply_computed",
    "wave_list", "wave_detail", "wave_create", "wave_edit", "wave_delete",
    "wave_release", "wave_close", "wave_cancel",
    "waveorder_add", "waveorder_remove",
    "wave_board",
    "returninspection_list", "returninspection_detail", "returninspection_create",
    "returninspection_edit", "returninspection_delete",
    "dispositionrule_list", "dispositionrule_detail", "dispositionrule_create",
    "dispositionrule_edit", "dispositionrule_delete",
    "returns_workbench",
    "barcodelabel_list", "barcodelabel_detail", "barcodelabel_create",
    "barcodelabel_edit", "barcodelabel_delete", "barcodelabel_print", "barcodelabel_render",
    "barcodelabel_void",
    "scan_console", "scansession_list", "scansession_detail", "scansession_create",
    "scansession_edit", "scansession_close", "scansession_delete",
    "rfidtag_list", "rfidtag_detail", "rfidtag_create", "rfidtag_edit", "rfidtag_delete",
    "rfidtag_activate", "rfidtag_retire", "rfidtag_mark_lost", "rfidtag_bulkread",
]

