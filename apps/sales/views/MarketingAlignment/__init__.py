"""Sales 8.13 — MarketingAlignment views package re-exports."""
from apps.sales.views.MarketingAlignment.AttributionTouchpoints import (
    attribution_touchpoint_create,
    attribution_touchpoint_delete,
    attribution_touchpoint_detail,
    attribution_touchpoint_edit,
    attribution_touchpoint_list,
)

__all__ = [
    "attribution_touchpoint_list",
    "attribution_touchpoint_create",
    "attribution_touchpoint_detail",
    "attribution_touchpoint_edit",
    "attribution_touchpoint_delete",
]
