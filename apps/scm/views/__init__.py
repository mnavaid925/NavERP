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
    reorderrule_list, reorderrule_create, reorderrule_edit, reorderrule_delete,
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
