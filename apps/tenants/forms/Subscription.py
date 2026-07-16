"""tenants — Subscription forms (split from apps/tenants/forms.py)."""
from apps.tenants.forms._common import *  # noqa: F401,F403
from apps.tenants.models import (
    Subscription,
)


class SubscriptionForm(TenantModelForm):
    class Meta:
        model = Subscription
        fields = ["plan", "status", "billing_cycle", "amount", "seats", "started_on", "renews_on"]
