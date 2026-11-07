from apps.bi.views.EmbeddedMobileBi.EmbeddedAnalyticsConfigs import (
    embedded_analytics_config_create,
    embedded_analytics_config_delete,
    embedded_analytics_config_detail,
    embedded_analytics_config_edit,
    embedded_analytics_config_list,
    embedded_analytics_config_preview,
)
from apps.bi.views.EmbeddedMobileBi.EmbedApiTokens import (
    embed_api_token_create,
    embed_api_token_delete,
    embed_api_token_detail,
    embed_api_token_edit,
    embed_api_token_list,
    embed_api_token_revoke,
)
from apps.bi.views.EmbeddedMobileBi.KioskWallboardDisplays import (
    kiosk_wallboard_display_create,
    kiosk_wallboard_display_delete,
    kiosk_wallboard_display_detail,
    kiosk_wallboard_display_edit,
    kiosk_wallboard_display_heartbeat,
    kiosk_wallboard_display_list,
    kiosk_wallboard_display_player,
)
from apps.bi.views.EmbeddedMobileBi.MobileBiConfigurations import (
    mobile_bi_config_create,
    mobile_bi_config_delete,
    mobile_bi_config_detail,
    mobile_bi_config_edit,
    mobile_bi_config_list,
)

__all__ = [
    "embedded_analytics_config_list",
    "embedded_analytics_config_create",
    "embedded_analytics_config_detail",
    "embedded_analytics_config_edit",
    "embedded_analytics_config_delete",
    "embedded_analytics_config_preview",
    "kiosk_wallboard_display_list",
    "kiosk_wallboard_display_create",
    "kiosk_wallboard_display_detail",
    "kiosk_wallboard_display_edit",
    "kiosk_wallboard_display_delete",
    "kiosk_wallboard_display_player",
    "kiosk_wallboard_display_heartbeat",
    "mobile_bi_config_list",
    "mobile_bi_config_create",
    "mobile_bi_config_detail",
    "mobile_bi_config_edit",
    "mobile_bi_config_delete",
    "embed_api_token_list",
    "embed_api_token_create",
    "embed_api_token_detail",
    "embed_api_token_edit",
    "embed_api_token_delete",
    "embed_api_token_revoke",
]
