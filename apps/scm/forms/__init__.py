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
