from apps.ecommerce.views.SubscriptionCommerce.CustomerSubscriptions import (
    customersubscription_create,
    customersubscription_delete,
    customersubscription_detail,
    customersubscription_edit,
    customersubscription_list,
)
from apps.ecommerce.views.SubscriptionCommerce.SubscriptionBoxCurations import (
    subscriptionboxcuration_create,
    subscriptionboxcuration_delete,
    subscriptionboxcuration_detail,
    subscriptionboxcuration_edit,
    subscriptionboxcuration_list,
)
from apps.ecommerce.views.SubscriptionCommerce.SubscriptionPlans import (
    subscriptionplan_create,
    subscriptionplan_delete,
    subscriptionplan_detail,
    subscriptionplan_edit,
    subscriptionplan_list,
)
from apps.ecommerce.views.SubscriptionCommerce.SubscriptionPortals import (
    subscription_portal,
    subscription_portal_deflect,
    subscription_portal_pause,
    subscription_portal_resume,
    subscription_portal_skip,
)
from apps.ecommerce.views.SubscriptionCommerce.SubscriptionRetentionActions import (
    subscriptionretentionaction_create,
    subscriptionretentionaction_delete,
    subscriptionretentionaction_detail,
    subscriptionretentionaction_edit,
    subscriptionretentionaction_list,
)

__all__ = [
    # Plans
    "subscriptionplan_list",
    "subscriptionplan_create",
    "subscriptionplan_detail",
    "subscriptionplan_edit",
    "subscriptionplan_delete",
    # Subscriptions
    "customersubscription_list",
    "customersubscription_create",
    "customersubscription_detail",
    "customersubscription_edit",
    "customersubscription_delete",
    # Curations
    "subscriptionboxcuration_list",
    "subscriptionboxcuration_create",
    "subscriptionboxcuration_detail",
    "subscriptionboxcuration_edit",
    "subscriptionboxcuration_delete",
    # Retention
    "subscriptionretentionaction_list",
    "subscriptionretentionaction_create",
    "subscriptionretentionaction_detail",
    "subscriptionretentionaction_edit",
    "subscriptionretentionaction_delete",
    # Portal & Actions
    "subscription_portal",
    "subscription_portal_skip",
    "subscription_portal_pause",
    "subscription_portal_resume",
    "subscription_portal_deflect",
]
