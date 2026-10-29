from apps.ecommerce.views.CustomerProfile.CustomerAccountProfiles import (
    customeraccountprofile_create,
    customeraccountprofile_delete,
    customeraccountprofile_detail,
    customeraccountprofile_edit,
    customeraccountprofile_list,
)
from apps.ecommerce.views.CustomerProfile.CustomerAddressPreferences import (
    customeraddresspreference_create,
    customeraddresspreference_delete,
    customeraddresspreference_detail,
    customeraddresspreference_edit,
    customeraddresspreference_list,
)
from apps.ecommerce.views.CustomerProfile.CustomerPrivacyRequests import (
    customerprivacyrequest_anonymize,
    customerprivacyrequest_create,
    customerprivacyrequest_delete,
    customerprivacyrequest_detail,
    customerprivacyrequest_edit,
    customerprivacyrequest_generate_export,
    customerprivacyrequest_list,
)
from apps.ecommerce.views.CustomerProfile.CustomerWishlists import (
    customerwishlist_create,
    customerwishlist_delete,
    customerwishlist_detail,
    customerwishlist_edit,
    customerwishlist_item_add,
    customerwishlist_item_delete,
    customerwishlist_list,
)

__all__ = [
    "customeraccountprofile_list",
    "customeraccountprofile_detail",
    "customeraccountprofile_create",
    "customeraccountprofile_edit",
    "customeraccountprofile_delete",
    "customeraddresspreference_list",
    "customeraddresspreference_detail",
    "customeraddresspreference_create",
    "customeraddresspreference_edit",
    "customeraddresspreference_delete",
    "customerwishlist_list",
    "customerwishlist_detail",
    "customerwishlist_create",
    "customerwishlist_edit",
    "customerwishlist_delete",
    "customerwishlist_item_add",
    "customerwishlist_item_delete",
    "customerprivacyrequest_list",
    "customerprivacyrequest_detail",
    "customerprivacyrequest_create",
    "customerprivacyrequest_edit",
    "customerprivacyrequest_delete",
    "customerprivacyrequest_generate_export",
    "customerprivacyrequest_anonymize",
]
