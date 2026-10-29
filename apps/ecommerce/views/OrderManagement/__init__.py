from apps.ecommerce.views.OrderManagement.EcommerceOrders import (
    ecommerceorder_cancel,
    ecommerceorder_create,
    ecommerceorder_delete,
    ecommerceorder_detail,
    ecommerceorder_edit,
    ecommerceorder_list,
)
from apps.ecommerce.views.OrderManagement.OrderFulfillments import (
    orderfulfillment_create,
    orderfulfillment_delete,
    orderfulfillment_detail,
    orderfulfillment_edit,
    orderfulfillment_list,
    orderfulfillment_ship,
)
from apps.ecommerce.views.OrderManagement.OrderRoutingRules import (
    orderroutingrule_create,
    orderroutingrule_delete,
    orderroutingrule_detail,
    orderroutingrule_edit,
    orderroutingrule_list,
)
from apps.ecommerce.views.OrderManagement.ReturnMerchandiseAuthorizations import (
    returnmerchandiseauthorization_complete,
    returnmerchandiseauthorization_create,
    returnmerchandiseauthorization_delete,
    returnmerchandiseauthorization_detail,
    returnmerchandiseauthorization_edit,
    returnmerchandiseauthorization_list,
)

__all__ = [
    "ecommerceorder_list",
    "ecommerceorder_create",
    "ecommerceorder_detail",
    "ecommerceorder_edit",
    "ecommerceorder_delete",
    "ecommerceorder_cancel",
    "orderroutingrule_list",
    "orderroutingrule_create",
    "orderroutingrule_detail",
    "orderroutingrule_edit",
    "orderroutingrule_delete",
    "orderfulfillment_list",
    "orderfulfillment_create",
    "orderfulfillment_detail",
    "orderfulfillment_edit",
    "orderfulfillment_delete",
    "orderfulfillment_ship",
    "returnmerchandiseauthorization_list",
    "returnmerchandiseauthorization_create",
    "returnmerchandiseauthorization_detail",
    "returnmerchandiseauthorization_edit",
    "returnmerchandiseauthorization_delete",
    "returnmerchandiseauthorization_complete",
]
