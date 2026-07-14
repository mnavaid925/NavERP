"""CRM 1.3 Marketing Automation — EmailCampaigns forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    EmailCampaign,
)


class EmailCampaignForm(TenantModelForm):
    class Meta:
        model = EmailCampaign
        # WARNING: sent_at + every *_count metric are system-managed (set only by the
        # emailcampaign_send action / seeder). Excluded so a user can't fabricate engagement
        # numbers or back-date a send via POST. `status` is ALSO excluded: draft→sent happens
        # only through the admin-gated emailcampaign_send action — accepting status from POST
        # would let a member mark a blast "sent" (sent_at NULL, counts 0), corrupt metrics, and
        # permanently lock out the send workflow.
        fields = ["name", "campaign", "template", "variant_template", "is_ab_test",
                  "send_type", "scheduled_at", "owner"]
