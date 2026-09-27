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
from .UsageRecord import (
    usagerecord_list,
    usagerecord_create,
    usagerecord_detail,
    usagerecord_edit,
    usagerecord_delete,
    usagerecord_mark_billed,
)  # noqa: F401
from .Onboarding import (
    onboarding,
)  # noqa: F401
from .Isolation import (
    isolation_overview,
)  # noqa: F401
# 0.19 "License & Subscription Administration" — 24 views: 22 CRUD across four entities, the two
# POST-only verbs, and the two computed boards. Every one re-exported here, because a view wired
# into urls.py but missing from this block is an AttributeError at import (L7).
from .EntitlementFeature import (
    entitlementfeature_list,
    entitlementfeature_create,
    entitlementfeature_detail,
    entitlementfeature_edit,
    entitlementfeature_delete,
)  # noqa: F401
from .PlanEntitlement import (
    planentitlement_list,
    planentitlement_create,
    planentitlement_detail,
    planentitlement_edit,
    planentitlement_delete,
)  # noqa: F401
from .UsageQuota import (
    usagequota_list,
    usagequota_create,
    usagequota_detail,
    usagequota_edit,
    usagequota_delete,
    usagequota_mark_breached,
)  # noqa: F401
from .LicenseAssignment import (
    licenseassignment_list,
    licenseassignment_create,
    licenseassignment_detail,
    licenseassignment_edit,
    licenseassignment_delete,
    licenseassignment_reclaim,
)  # noqa: F401
from .Boards import (
    quota_board,
    renewal_board,
)  # noqa: F401
