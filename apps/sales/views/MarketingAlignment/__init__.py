"""Sales 8.13 — MarketingAlignment views package re-exports."""
from apps.sales.views.MarketingAlignment.AttributionTouchpoints import (
    attribution_touchpoint_create,
    attribution_touchpoint_delete,
    attribution_touchpoint_detail,
    attribution_touchpoint_edit,
    attribution_touchpoint_list,
)
from apps.sales.views.MarketingAlignment.CampaignAttributions import (
    campaign_attribution_create,
    campaign_attribution_delete,
    campaign_attribution_detail,
    campaign_attribution_edit,
    campaign_attribution_list,
)

__all__ = [
    "attribution_touchpoint_list",
    "attribution_touchpoint_create",
    "attribution_touchpoint_detail",
    "attribution_touchpoint_edit",
    "attribution_touchpoint_delete",
    "campaign_attribution_list",
    "campaign_attribution_create",
    "campaign_attribution_detail",
    "campaign_attribution_edit",
    "campaign_attribution_delete",
]
