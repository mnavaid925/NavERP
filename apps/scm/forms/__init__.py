"""SCM forms package — one sub-package per NavERP sub-module (4.1-4.19), one module per entity.

This __init__ re-exports EVERY form + formset so ``from apps.scm.forms import PurchaseOrderForm``
works from the views and the tests. Adding a form without adding it here is a bug.
"""
from ._common import *  # noqa: F401,F403

# 4.1 Procurement Management
from .ProcurementManagement.PurchaseRequisitions import (  # noqa: F401
    PurchaseRequisitionForm,
    PurchaseRequisitionLineForm,
    PurchaseRequisitionLineFormSet,
)
from .ProcurementManagement.Rfqs import (  # noqa: F401
    RFQForm,
    RFQLineForm,
    RFQLineFormSet,
    RFQVendorForm,
    RFQVendorFormSet,
    RFQQuoteForm,
    RFQQuoteLineForm,
    RFQQuoteLineFormSet,
)
from .ProcurementManagement.PurchaseOrders import (  # noqa: F401
    PurchaseOrderForm,
    PurchaseOrderLineForm,
    PurchaseOrderLineFormSet,
    PurchaseOrderAmendForm,
    PurchaseOrderCancelForm,
    PurchaseOrderAcknowledgeForm,
)
from .ProcurementManagement.GoodsReceiptNotes import (  # noqa: F401
    GoodsReceiptNoteForm,
    GoodsReceiptLineForm,
    GoodsReceiptLineFormSet,
)

# 4.2 Supplier Relationship Management
from .SupplierRelationshipManagement.SupplierProfiles import (  # noqa: F401
    SupplierProfileForm,
)
from .SupplierRelationshipManagement.SupplierScorecards import (  # noqa: F401
    SupplierScorecardForm,
)
from .SupplierRelationshipManagement.SupplierContracts import (  # noqa: F401
    SupplierContractForm,
)
from .SupplierRelationshipManagement.SupplierCatalogs import (  # noqa: F401
    SupplierCatalogForm,
    SupplierCatalogItemForm,
    SupplierCatalogItemFormSet,
)
from .SupplierRelationshipManagement.SupplierRiskAssessments import (  # noqa: F401
    SupplierRiskAssessmentForm,
)

# 4.3 Inventory Management
from .InventoryManagement.Items import (  # noqa: F401
    ItemCategoryForm,
    UOMForm,
    ItemForm,
)
from .InventoryManagement.Locations import (  # noqa: F401
    LocationForm,
)
from .InventoryManagement.LotSerials import (  # noqa: F401
    LotSerialForm,
)
from .InventoryManagement.StockTransfers import (  # noqa: F401
    StockTransferForm,
    StockTransferLineForm,
    StockTransferLineFormSet,
)
from .InventoryManagement.StockAdjustments import (  # noqa: F401
    StockAdjustmentForm,
    StockAdjustmentLineForm,
    StockAdjustmentLineFormSet,
)
from .InventoryManagement.ReorderRules import (  # noqa: F401
    ReorderRuleForm,
)

# 4.4 Warehouse Management
from .WarehouseManagement.PutawayTasks import (  # noqa: F401
    PutawayTaskForm,
)
from .WarehouseManagement.PickTasks import (  # noqa: F401
    PickTaskForm,
    PickTaskPackForm,
    PickTaskLineForm,
    PickTaskLineFormSet,
)
from .WarehouseManagement.CycleCountTasks import (  # noqa: F401
    CycleCountTaskForm,
    CycleCountTaskLineForm,
    CycleCountTaskLineFormSet,
)
from .WarehouseManagement.YardVisits import (  # noqa: F401
    YardVisitForm,
)

# 4.5 Order Management System (OMS)
from .OrderManagement.SalesOrders import (  # noqa: F401
    SalesOrderForm,
    SalesOrderLineForm,
    BaseSalesOrderLineFormSet,
    SalesOrderLineFormSet,
)
from .OrderManagement.SalesOrderAllocations import (  # noqa: F401
    SalesOrderAllocationForm,
)
