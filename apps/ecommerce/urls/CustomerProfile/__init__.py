from apps.ecommerce.urls.CustomerProfile.CustomerAccountProfiles import (
    urlpatterns as account_profile_patterns,
)
from apps.ecommerce.urls.CustomerProfile.CustomerAddressPreferences import (
    urlpatterns as address_preference_patterns,
)
from apps.ecommerce.urls.CustomerProfile.CustomerPrivacyRequests import (
    urlpatterns as privacy_request_patterns,
)
from apps.ecommerce.urls.CustomerProfile.CustomerWishlists import (
    urlpatterns as wishlist_patterns,
)

urlpatterns = (
    account_profile_patterns
    + address_preference_patterns
    + wishlist_patterns
    + privacy_request_patterns
)

__all__ = ["urlpatterns"]
