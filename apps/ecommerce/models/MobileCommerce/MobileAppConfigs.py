import json
from django.core.validators import RegexValidator
from django.db import models
from apps.ecommerce.models._base import TenantNumbered

HEX_COLOR_VALIDATOR = RegexValidator(
    regex=r"^#[0-9A-Fa-f]{6}$",
    message="Color must be a valid 6-character hex code starting with # (e.g. #2563EB).",
)


class MobileAppConfig(TenantNumbered):
    NUMBER_PREFIX = "EMAC"

    DISPLAY_MODE_CHOICES = [
        ("standalone", "Standalone (No Browser UI)"),
        ("fullscreen", "Fullscreen (Immersive)"),
        ("minimal-ui", "Minimal UI (Limited Controls)"),
        ("browser", "Standard Browser Tab"),
    ]

    ORIENTATION_CHOICES = [
        ("portrait", "Portrait Preferred"),
        ("landscape", "Landscape Preferred"),
        ("any", "Auto / Any Orientation"),
    ]

    CACHE_STRATEGY_CHOICES = [
        ("stale_while_revalidate", "Stale While Revalidate (Fast + Background Sync)"),
        ("cache_first", "Cache First (Offline Resilient)"),
        ("network_first", "Network First with Cache Fallback"),
        ("network_only", "Network Only (No Offline Storage)"),
    ]

    app_name = models.CharField(
        max_length=120,
        default="NavERP Mobile Store",
        help_text="Full application name displayed on splash screens",
    )
    short_name = models.CharField(
        max_length=50,
        default="NavERP Store",
        help_text="Short name used on mobile home-screen icon launcher",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Description for web app manifest and app stores",
    )
    theme_color = models.CharField(
        max_length=7,
        default="#2563EB",
        validators=[HEX_COLOR_VALIDATOR],
        help_text="Brand hex color for browser status bar",
    )
    background_color = models.CharField(
        max_length=7,
        default="#FFFFFF",
        validators=[HEX_COLOR_VALIDATOR],
        help_text="Splash screen background hex color",
    )
    display_mode = models.CharField(
        max_length=20,
        choices=DISPLAY_MODE_CHOICES,
        default="standalone",
    )
    orientation = models.CharField(
        max_length=20,
        choices=ORIENTATION_CHOICES,
        default="portrait",
    )
    start_url = models.CharField(
        max_length=255,
        default="/",
        help_text="Entry route when launched from home screen",
    )
    scope = models.CharField(
        max_length=255,
        default="/",
        help_text="Navigation boundary for progressive web app",
    )
    icon_192_url = models.CharField(
        max_length=255,
        blank=True,
        default="/static/img/icons/icon-192.png",
        help_text="192x192 PNG launcher icon URL",
    )
    icon_512_url = models.CharField(
        max_length=255,
        blank=True,
        default="/static/img/icons/icon-512.png",
        help_text="512x512 PNG splash icon URL",
    )
    offline_cache_strategy = models.CharField(
        max_length=30,
        choices=CACHE_STRATEGY_CHOICES,
        default="stale_while_revalidate",
    )
    offline_fallback_html = models.TextField(
        blank=True,
        default="<div class='offline-card text-center p-8'><h2 class='text-xl font-bold mb-2'>You are offline</h2><p class='text-slate-500'>Saved items and cached catalog products remain available.</p></div>",
        help_text="Offline fallback HTML payload when network is unavailable",
    )
    enable_pwa = models.BooleanField(
        default=True,
        help_text="Enable progressive web app manifest and service worker",
    )
    enable_biometric_login = models.BooleanField(
        default=True,
        help_text="Allow FaceID/TouchID/Fingerprint authentication in native shell",
    )
    min_ios_version = models.CharField(
        max_length=16,
        default="15.0",
        help_text="Minimum supported iOS version",
    )
    min_android_version = models.CharField(
        max_length=16,
        default="10.0",
        help_text="Minimum supported Android API level",
    )
    apple_pay_merchant_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Apple Pay merchant identifier",
    )
    google_pay_gateway_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Google Pay merchant gateway profile identifier",
    )
    enable_apple_pay = models.BooleanField(
        default=False,
        help_text="Enable Apple Pay native express checkout",
    )
    enable_google_pay = models.BooleanField(
        default=False,
        help_text="Enable Google Pay native express checkout",
    )
    enable_in_app_wallet = models.BooleanField(
        default=True,
        help_text="Allow customers to store prepaid account balances",
    )
    enable_express_checkout = models.BooleanField(
        default=True,
        help_text="Enable 1-tap mobile buy-now checkout bypassing cart review",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Active primary configuration for tenant",
    )

    class Meta:
        db_table = "ecommerce_mobile_app_config"
        ordering = ["-is_active", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_emac_tenant_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="idx_emac_ten_act"),
            models.Index(fields=["tenant", "enable_pwa"], name="idx_emac_ten_pwa"),
        ]

    def __str__(self):
        return f"{self.short_name} ({self.number})"

    def generate_manifest_dict(self):
        icons = []
        if self.icon_192_url:
            icons.append({
                "src": self.icon_192_url,
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable",
            })
        if self.icon_512_url:
            icons.append({
                "src": self.icon_512_url,
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable",
            })
        return {
            "name": self.app_name,
            "short_name": self.short_name,
            "description": self.description,
            "start_url": self.start_url,
            "scope": self.scope,
            "display": self.display_mode,
            "orientation": self.orientation,
            "theme_color": self.theme_color,
            "background_color": self.background_color,
            "icons": icons,
        }

    def generate_manifest_json(self):
        return json.dumps(self.generate_manifest_dict(), indent=2)
