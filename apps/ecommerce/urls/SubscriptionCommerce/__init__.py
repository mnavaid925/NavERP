from apps.ecommerce.urls.SubscriptionCommerce.CustomerSubscriptions import (
    urlpatterns as customersubscriptions_patterns,
)
from apps.ecommerce.urls.SubscriptionCommerce.SubscriptionBoxCurations import (
    urlpatterns as subscriptionboxcurations_patterns,
)
from apps.ecommerce.urls.SubscriptionCommerce.SubscriptionPlans import (
    urlpatterns as subscriptionplans_patterns,
)
from apps.ecommerce.urls.SubscriptionCommerce.SubscriptionPortals import (
    urlpatterns as subscriptionportals_patterns,
)
from apps.ecommerce.urls.SubscriptionCommerce.SubscriptionRetentionActions import (
    urlpatterns as subscriptionretentionactions_patterns,
)

urlpatterns = (
    subscriptionplans_patterns
    + customersubscriptions_patterns
    + subscriptionboxcurations_patterns
    + subscriptionretentionactions_patterns
    + subscriptionportals_patterns
)
