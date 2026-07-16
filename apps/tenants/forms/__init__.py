"""tenants forms package — split from apps/tenants/forms.py.

tenants is a Module 0 foundation app with no NavERP sub-modules, so entity files are FLAT
at the package root. This __init__ re-exports every symbol, so
``from apps.tenants.forms import X`` (and the 3+ modules that do it) is unchanged.
"""
from ._common import *  # noqa: F401,F403
from .Subscription import (
    SubscriptionForm,
)  # noqa: F401
from .SubscriptionInvoice import (
    SubscriptionInvoiceForm,
)  # noqa: F401
from .BrandingSetting import (
    BrandingSettingForm,
)  # noqa: F401
from .EncryptionKey import (
    EncryptionKeyForm,
)  # noqa: F401
from .HealthMetric import (
    HealthMetricForm,
)  # noqa: F401
from .Onboarding import (
    OnboardingForm,
)  # noqa: F401
