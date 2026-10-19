"""Sales 8.13 — MarketingAlignment views package re-exports."""
from apps.sales.views.MarketingAlignment.AttributionConsole import (
    marketing_attribution_console,
)
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
from apps.sales.views.MarketingAlignment.ContentEngagements import (
    content_engagement_create,
    content_engagement_delete,
    content_engagement_detail,
    content_engagement_edit,
    content_engagement_list,
)
from apps.sales.views.MarketingAlignment.MqlHandoffs import (
    mql_handoff_create,
    mql_handoff_delete,
    mql_handoff_detail,
    mql_handoff_edit,
    mql_handoff_list,
)
from apps.sales.views.MarketingAlignment.MarketingEvents import (
    marketing_event_create,
    marketing_event_delete,
    marketing_event_detail,
    marketing_event_edit,
    marketing_event_list,
    marketing_event_registration_create,
    marketing_event_registrations,
)

__all__ = [
    "marketing_attribution_console",
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
    "mql_handoff_list",
    "mql_handoff_create",
    "mql_handoff_detail",
    "mql_handoff_edit",
    "mql_handoff_delete",
    "content_engagement_list",
    "content_engagement_create",
    "content_engagement_detail",
    "content_engagement_edit",
    "content_engagement_delete",
    "marketing_event_list",
    "marketing_event_create",
    "marketing_event_detail",
    "marketing_event_edit",
    "marketing_event_delete",
    "marketing_event_registrations",
    "marketing_event_registration_create",
]
