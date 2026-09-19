"""tenants — UsageRecord forms (0.1 usage metering)."""
from apps.tenants.forms._common import *  # noqa: F401,F403
from apps.tenants.models import (
    UsageRecord,
)


class UsageRecordForm(TenantModelForm):
    """`is_billed` / `billed_at` are excluded: they are evidence written only by
    `usagerecord_mark_billed`, and a form that could set them would let a member mark their own
    usage as invoiced. `subscription_invoice` stays IN the form because the operator links the
    invoice before marking billed — a billed row refuses further edits."""

    class Meta:
        model = UsageRecord
        fields = ["subscription", "metric", "quantity", "period_start", "period_end",
                  "subscription_invoice", "notes"]
