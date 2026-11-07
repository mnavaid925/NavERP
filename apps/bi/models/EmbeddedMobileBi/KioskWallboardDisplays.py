from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from apps.bi.models._base import TenantNumbered


class KioskWallboardDisplay(TenantNumbered):
    NUMBER_PREFIX = "WALL"

    TRANSITION_EFFECT_CHOICES = [
        ("fade", "Smooth Fade (1s)"),
        ("slide_horizontal", "Horizontal Slide"),
        ("zoom", "Subtle Zoom In"),
        ("none", "Instant Cut"),
    ]

    WALLBOARD_THEME_CHOICES = [
        ("dark_oled", "Deep Dark OLED (#000000)"),
        ("dark_navy", "Command Center Navy (#0f172a)"),
        ("light_high_contrast", "High-Contrast Light (#ffffff)"),
    ]

    DISPLAY_SCHEDULE_CHOICES = [
        ("continuous_24_7", "Continuous 24/7 Operations"),
        ("business_hours", "Business Hours (08:00 - 18:00)"),
        ("shift_work", "Multi-Shift Operations"),
    ]

    STATUS_CHOICES = [
        ("active", "Active & Broadcasting"),
        ("standby", "Standby / Paused"),
        ("offline", "Offline"),
    ]

    name = models.CharField(max_length=200)
    location_description = models.CharField(
        max_length=255,
        blank=True,
        help_text="Physical installation location (e.g. Ops Floor Monitor 4, Exec Boardroom TV)",
    )
    kiosk_slug = models.SlugField(max_length=220, blank=True)
    access_passcode = models.CharField(
        max_length=64,
        blank=True,
        help_text="Optional PIN or secret key for unattended display login",
    )
    is_public_kiosk = models.BooleanField(
        default=False,
        help_text="Allow access via public kiosk URL with passcode",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="active")

    playlist_items = models.JSONField(
        default=list,
        blank=True,
        help_text="Ordered playlist array of items: [{'type': 'dashboard', 'id': 1, 'title': 'Ops Overview', 'duration_seconds': 30}]",
    )
    default_slide_duration_seconds = models.PositiveIntegerField(
        default=30,
        help_text="Default dwell time per dashboard slide in seconds",
    )
    transition_effect = models.CharField(
        max_length=24,
        choices=TRANSITION_EFFECT_CHOICES,
        default="fade",
    )
    theme = models.CharField(max_length=24, choices=WALLBOARD_THEME_CHOICES, default="dark_navy")
    display_schedule = models.CharField(
        max_length=24,
        choices=DISPLAY_SCHEDULE_CHOICES,
        default="continuous_24_7",
    )
    operating_hours_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="Schedule config {'start': '08:00', 'end': '18:00', 'days': [1,2,3,4,5]}",
    )
    auto_refresh_data_interval_seconds = models.PositiveIntegerField(
        default=60,
        help_text="Background data reload interval in seconds",
    )

    last_heartbeat_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Most recent ping timestamp received from display device",
    )
    device_ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_user_agent = models.CharField(max_length=255, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bi_kiosk_displays",
    )

    class Meta:
        db_table = "bi_kiosk_wallboard_display"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_wall_tenant_num_uniq"),
            models.UniqueConstraint(fields=["tenant", "kiosk_slug"], name="bi_wall_tenant_slug_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_wall_ten_stat"),
            models.Index(fields=["tenant", "theme"], name="idx_wall_ten_theme"),
            models.Index(fields=["tenant", "display_schedule"], name="idx_wall_ten_schedule"),
            models.Index(fields=["tenant", "last_heartbeat_at"], name="idx_wall_ten_heartbeat"),
            models.Index(fields=["tenant", "created_at"], name="idx_wall_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} - {self.name} ({self.location_description or 'Unassigned'})"

    def save(self, *args, **kwargs):
        if not self.kiosk_slug:
            base_slug = slugify(self.name) or "kiosk-display"
            slug = base_slug
            counter = 1
            qs = KioskWallboardDisplay.objects.filter(tenant=self.tenant)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            while qs.filter(kiosk_slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.kiosk_slug = slug
        super().save(*args, **kwargs)

    def record_heartbeat(self, ip_address=None, user_agent=""):
        KioskWallboardDisplay.objects.filter(pk=self.pk).update(
            last_heartbeat_at=timezone.now(),
            device_ip_address=ip_address,
            device_user_agent=(user_agent[:250] if user_agent else ""),
        )
