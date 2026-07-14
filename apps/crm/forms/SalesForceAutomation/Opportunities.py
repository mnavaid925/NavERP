"""CRM 1.2 Sales Force Automation — Opportunities forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    Opportunity,
    OpportunitySplit,
)


class OpportunityForm(TenantModelForm):
    class Meta:
        model = Opportunity
        # lost_at + stage_changed_at are system-stamped in Opportunity.save() — excluded.
        fields = ["name", "account", "primary_contact", "stage", "forecast_category", "amount",
                  "probability", "close_date", "competitor", "loss_reason", "territory", "owner",
                  "source_lead", "campaign", "next_step", "description"]


class OpportunitySplitForm(TenantModelForm):
    """Inline on the opportunity detail page; tenant/opportunity set in the view."""

    class Meta:
        model = OpportunitySplit
        fields = ["user", "split_type", "percentage", "notes"]
