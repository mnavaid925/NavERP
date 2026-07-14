"""CRM 1.3 Marketing Automation — Campaigns forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    Campaign,
    CampaignMember,
)


class CampaignForm(TenantModelForm):
    class Meta:
        model = Campaign
        fields = ["name", "type", "objective", "status", "parent_campaign", "start_date",
                  "end_date", "budget_planned", "budget_actual", "expected_revenue",
                  "actual_revenue", "target_size", "utm_source", "utm_medium",
                  "utm_campaign", "owner", "description"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A campaign can't be its own parent program.
        if self.instance and self.instance.pk:
            self.fields["parent_campaign"].queryset = self.fields["parent_campaign"].queryset.exclude(pk=self.instance.pk)


# ===== 1.3 Marketing Automation (recreated) =================================
class CampaignMemberForm(TenantModelForm):
    """Target-list membership. ``responded_at`` is system-set (stamped in save())."""

    class Meta:
        model = CampaignMember
        fields = ["campaign", "party", "lead", "member_name", "member_email", "status", "notes"]
