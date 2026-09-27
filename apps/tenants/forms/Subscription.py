"""tenants — Subscription forms (split from apps/tenants/forms.py)."""
from apps.tenants.forms._common import *  # noqa: F401,F403
from apps.tenants.models import (
    Subscription,
)


class SubscriptionForm(TenantModelForm):
    class Meta:
        model = Subscription
        # `auto_renew` + `grace_ends_on` appended by 0.19. They are commercial terms an operator
        # negotiates, not system stamps, so they are editable here (unlike `UsageQuota.breached_at`).
        fields = ["plan", "status", "billing_cycle", "amount", "seats", "started_on", "renews_on",
                  "auto_renew", "grace_ends_on"]
