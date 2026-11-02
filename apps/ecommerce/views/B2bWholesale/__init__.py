from apps.ecommerce.views.B2bWholesale.B2bCompanyAccounts import (
    b2bcompanyaccount_create,
    b2bcompanyaccount_delete,
    b2bcompanyaccount_detail,
    b2bcompanyaccount_edit,
    b2bcompanyaccount_list,
    b2bcompanyaccount_punchout_test,
)
from apps.ecommerce.views.B2bWholesale.B2bCompanyUsers import (
    b2bcompanyuser_create,
    b2bcompanyuser_delete,
    b2bcompanyuser_detail,
    b2bcompanyuser_edit,
    b2bcompanyuser_list,
)
from apps.ecommerce.views.B2bWholesale.B2bQuoteRequests import (
    b2bquoterequest_accept,
    b2bquoterequest_convert_order,
    b2bquoterequest_create,
    b2bquoterequest_delete,
    b2bquoterequest_detail,
    b2bquoterequest_edit,
    b2bquoterequest_list,
    b2bquoterequest_quote,
    b2bquoterequest_reject,
    b2bquoterequest_submit,
)
from apps.ecommerce.views.B2bWholesale.B2bQuickOrderTemplates import (
    b2b_quick_order_matrix,
    b2bquickordertemplate_create,
    b2bquickordertemplate_delete,
    b2bquickordertemplate_detail,
    b2bquickordertemplate_edit,
    b2bquickordertemplate_list,
)
from apps.ecommerce.views.B2bWholesale.B2bWholesaleHub import b2b_wholesale_hub

__all__ = [
    # Hub
    "b2b_wholesale_hub",
    # Company Accounts
    "b2bcompanyaccount_list",
    "b2bcompanyaccount_detail",
    "b2bcompanyaccount_create",
    "b2bcompanyaccount_edit",
    "b2bcompanyaccount_delete",
    "b2bcompanyaccount_punchout_test",
    # Company Users
    "b2bcompanyuser_list",
    "b2bcompanyuser_detail",
    "b2bcompanyuser_create",
    "b2bcompanyuser_edit",
    "b2bcompanyuser_delete",
    # Quote Requests
    "b2bquoterequest_list",
    "b2bquoterequest_detail",
    "b2bquoterequest_create",
    "b2bquoterequest_edit",
    "b2bquoterequest_delete",
    "b2bquoterequest_submit",
    "b2bquoterequest_quote",
    "b2bquoterequest_accept",
    "b2bquoterequest_reject",
    "b2bquoterequest_convert_order",
    # Quick Order Templates
    "b2bquickordertemplate_list",
    "b2bquickordertemplate_detail",
    "b2bquickordertemplate_create",
    "b2bquickordertemplate_edit",
    "b2bquickordertemplate_delete",
    "b2b_quick_order_matrix",
]
