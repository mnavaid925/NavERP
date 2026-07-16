"""tenants models package — split from apps/tenants/models.py.

tenants is a Module 0 foundation app with no NavERP sub-modules, so entity files are FLAT
at the package root. This __init__ re-exports every symbol, so
``from apps.tenants.models import X`` (and the 3+ modules that do it) is unchanged.
"""
from ._base import *  # noqa: F401,F403
from .Subscription import (
    Subscription,
)  # noqa: F401
from .SubscriptionInvoice import (
    SubscriptionInvoice,
)  # noqa: F401
from .BrandingSetting import (
    BrandingSetting,
)  # noqa: F401
from .EncryptionKey import (
    EncryptionKey,
)  # noqa: F401
from .HealthMetric import (
    HealthMetric,
)  # noqa: F401
