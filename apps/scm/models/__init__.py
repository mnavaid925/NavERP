"""SCM models package — one sub-package per NavERP sub-module (4.1-4.19), one module per entity.

This __init__ re-exports EVERY model so ``from apps.scm.models import PurchaseOrder`` works from the
admin, the seeder, the tests and any peer app. Adding a model without adding it here is a bug: it
will ImportError/AttributeError at runtime, not at import time.
"""
from ._base import *  # noqa: F401,F403

# 4.1 Procurement Management
from .ProcurementManagement.PurchaseRequisitions import (  # noqa: F401
    PurchaseRequisition,
    PurchaseRequisitionLine,
)
from .ProcurementManagement.Rfqs import (  # noqa: F401
    RFQ,
    RFQLine,
    RFQVendor,
    RFQQuote,
    RFQQuoteLine,
)
from .ProcurementManagement.PurchaseOrders import (  # noqa: F401
    PurchaseOrder,
    PurchaseOrderLine,
)
from .ProcurementManagement.GoodsReceiptNotes import (  # noqa: F401
    GoodsReceiptNote,
    GoodsReceiptLine,
)

# 4.2 Supplier Relationship Management
from .SupplierRelationshipManagement.SupplierProfiles import (  # noqa: F401
    SupplierProfile,
)
from .SupplierRelationshipManagement.SupplierScorecards import (  # noqa: F401
    SupplierScorecard,
)
from .SupplierRelationshipManagement.SupplierContracts import (  # noqa: F401
    SupplierContract,
)
from .SupplierRelationshipManagement.SupplierCatalogs import (  # noqa: F401
    SupplierCatalog,
    SupplierCatalogItem,
)
from .SupplierRelationshipManagement.SupplierRiskAssessments import (  # noqa: F401
    SupplierRiskAssessment,
)

# 4.3 Inventory Management — the spine (owned here ships-first, L29/L36) + domain tables
from .InventoryManagement.Items import (  # noqa: F401
    ItemCategory,
    UOM,
    Item,
)
from .InventoryManagement.Locations import (  # noqa: F401
    Location,
)
from .InventoryManagement.LotSerials import (  # noqa: F401
    LotSerial,
)
from .InventoryManagement.StockMoves import (  # noqa: F401
    StockMove,
)
from .InventoryManagement.StockTransfers import (  # noqa: F401
    StockTransfer,
    StockTransferLine,
)
from .InventoryManagement.StockAdjustments import (  # noqa: F401
    StockAdjustment,
    StockAdjustmentLine,
)
from .InventoryManagement.ReorderRules import (  # noqa: F401
    ReorderRule,
)

# 4.4 Warehouse Management
from .WarehouseManagement.PutawayTasks import (  # noqa: F401
    PutawayTask,
)
from .WarehouseManagement.PickTasks import (  # noqa: F401
    PickTask,
    PickTaskLine,
)
from .WarehouseManagement.CycleCountTasks import (  # noqa: F401
    CycleCountTask,
    CycleCountTaskLine,
)
from .WarehouseManagement.YardVisits import (  # noqa: F401
    YardVisit,
)

# 4.5 Order Management System (OMS)
from .OrderManagement.SalesOrders import (  # noqa: F401
    SalesOrder,
    SalesOrderLine,
)
from .OrderManagement.SalesOrderAllocations import (  # noqa: F401
    SalesOrderAllocation,
)
