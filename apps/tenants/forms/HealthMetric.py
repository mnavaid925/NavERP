"""tenants — HealthMetric forms (split from apps/tenants/forms.py)."""
from apps.tenants.forms._common import *  # noqa: F401,F403
from apps.tenants.models import (
    HealthMetric,
)


class HealthMetricForm(TenantModelForm):
    class Meta:
        model = HealthMetric
        fields = ["metric", "value", "status"]
