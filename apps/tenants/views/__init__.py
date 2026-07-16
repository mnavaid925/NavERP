"""tenants views package — split from apps/tenants/views.py.

tenants is a Module 0 foundation app with no NavERP sub-modules, so entity files are FLAT
at the package root. This __init__ re-exports every symbol, so
``from apps.tenants.views import X`` (and the 3+ modules that do it) is unchanged.
"""
from ._common import *  # noqa: F401,F403
from .Subscription import (
    subscription_list,
    subscription_create,
    subscription_detail,
    subscription_edit,
    subscription_delete,
    subscription_checkout,
    subscription_mark_paid,
    stripe_return,
    stripe_webhook,
)  # noqa: F401
from .SubscriptionInvoice import (
    subscriptioninvoice_list,
    subscriptioninvoice_create,
    subscriptioninvoice_detail,
    subscriptioninvoice_edit,
    subscriptioninvoice_delete,
)  # noqa: F401
from .BrandingSetting import (
    brandingsetting_list,
    brandingsetting_create,
    brandingsetting_detail,
    brandingsetting_edit,
    brandingsetting_delete,
)  # noqa: F401
from .EncryptionKey import (
    encryptionkey_list,
    encryptionkey_create,
    encryptionkey_detail,
    encryptionkey_edit,
    encryptionkey_rotate,
    encryptionkey_delete,
)  # noqa: F401
from .HealthMetric import (
    healthmetric_list,
    healthmetric_create,
    healthmetric_detail,
    healthmetric_edit,
    healthmetric_delete,
)  # noqa: F401
from .Onboarding import (
    onboarding,
)  # noqa: F401
