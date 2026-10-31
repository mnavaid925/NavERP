from apps.ecommerce.views.Marketplace.MarketplaceConsoleViews import (
    marketplace_console,
)
from apps.ecommerce.views.Marketplace.MarketplaceVendorViews import (
    marketplacevendor_create,
    marketplacevendor_delete,
    marketplacevendor_detail,
    marketplacevendor_edit,
    marketplacevendor_list,
    marketplacevendor_suspend,
    marketplacevendor_verify_kyc,
)
from apps.ecommerce.views.Marketplace.VendorPayoutViews import (
    vendorpayout_approve,
    vendorpayout_create,
    vendorpayout_delete,
    vendorpayout_detail,
    vendorpayout_edit,
    vendorpayout_execute,
    vendorpayout_list,
)
from apps.ecommerce.views.Marketplace.VendorProductListingViews import (
    vendorproductlisting_create,
    vendorproductlisting_delete,
    vendorproductlisting_detail,
    vendorproductlisting_edit,
    vendorproductlisting_list,
    vendorproductlisting_moderate,
)
from apps.ecommerce.views.Marketplace.VendorSubOrderViews import (
    vendorsuborder_create,
    vendorsuborder_delete,
    vendorsuborder_detail,
    vendorsuborder_dispute,
    vendorsuborder_edit,
    vendorsuborder_fulfill,
    vendorsuborder_list,
)

__all__ = [
    "marketplace_console",
    "marketplacevendor_list",
    "marketplacevendor_detail",
    "marketplacevendor_create",
    "marketplacevendor_edit",
    "marketplacevendor_delete",
    "marketplacevendor_verify_kyc",
    "marketplacevendor_suspend",
    "vendorproductlisting_list",
    "vendorproductlisting_detail",
    "vendorproductlisting_create",
    "vendorproductlisting_edit",
    "vendorproductlisting_delete",
    "vendorproductlisting_moderate",
    "vendorsuborder_list",
    "vendorsuborder_detail",
    "vendorsuborder_create",
    "vendorsuborder_edit",
    "vendorsuborder_delete",
    "vendorsuborder_fulfill",
    "vendorsuborder_dispute",
    "vendorpayout_list",
    "vendorpayout_detail",
    "vendorpayout_create",
    "vendorpayout_edit",
    "vendorpayout_delete",
    "vendorpayout_approve",
    "vendorpayout_execute",
]
