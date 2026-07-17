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
