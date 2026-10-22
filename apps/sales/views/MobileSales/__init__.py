from .FieldSalesRoutes import (
    field_sales_route_list,
    field_sales_route_detail,
    field_sales_route_create,
    field_sales_route_edit,
    field_sales_route_delete,
    field_sales_route_optimize,
)
from .FieldCheckIns import (
    field_check_in_list,
    field_check_in_detail,
    field_check_in_create,
    field_check_in_edit,
    field_check_in_delete,
    field_check_in_checkout,
)
from .MobileDeviceSessions import (
    mobile_device_session_list,
    mobile_device_session_detail,
    mobile_device_session_create,
    mobile_device_session_edit,
    mobile_device_session_delete,
    mobile_device_session_sync,
)
from .MobileDealAlerts import (
    mobile_deal_alert_list,
    mobile_deal_alert_detail,
    mobile_deal_alert_create,
    mobile_deal_alert_edit,
    mobile_deal_alert_delete,
    mobile_deal_alert_mark_read,
)
from .MobileSalesDashboards import (
    mobile_sales_dashboard,
)

__all__ = [
    "field_sales_route_list",
    "field_sales_route_detail",
    "field_sales_route_create",
    "field_sales_route_edit",
    "field_sales_route_delete",
    "field_sales_route_optimize",
    "field_check_in_list",
    "field_check_in_detail",
    "field_check_in_create",
    "field_check_in_edit",
    "field_check_in_delete",
    "field_check_in_checkout",
    "mobile_device_session_list",
    "mobile_device_session_detail",
    "mobile_device_session_create",
    "mobile_device_session_edit",
    "mobile_device_session_delete",
    "mobile_device_session_sync",
    "mobile_deal_alert_list",
    "mobile_deal_alert_detail",
    "mobile_deal_alert_create",
    "mobile_deal_alert_edit",
    "mobile_deal_alert_delete",
    "mobile_deal_alert_mark_read",
    "mobile_sales_dashboard",
]
