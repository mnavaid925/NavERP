"""Projects 7.19 — ProjectLocaleSetting model [PLS-].

Project regional profile, language pack selection (core.Language), IANA timezone (core.TimeZone),
and work-week calendar patterns.
"""
from decimal import Decimal

from apps.projects.models._base import *


class ProjectLocaleSetting(TenantNumbered):
    """Regional and localization configuration settings profile for project delivery."""

    NUMBER_PREFIX = "PLS"

    DATE_FORMAT_CHOICES = [
        ("YYYY-MM-DD", "YYYY-MM-DD (ISO Standard)"),
        ("DD/MM/YYYY", "DD/MM/YYYY (UK / EU / Commonwealth)"),
        ("MM/DD/YYYY", "MM/DD/YYYY (US Standard)"),
        ("YYYY/MM/DD", "YYYY/MM/DD (East Asia)"),
    ]

    TIME_FORMAT_CHOICES = [
        ("12h", "12-Hour (1:30 PM)"),
        ("24h", "24-Hour (13:30)"),
    ]

    FIRST_DAY_CHOICES = [
        (1, "Monday (ISO Standard)"),
        (6, "Saturday (Middle East Standard)"),
        (7, "Sunday (US / Global Standard)"),
    ]

    NUMBER_FORMAT_CHOICES = [
        ("#,##0.00", "1,234.56 (Standard comma thousands, dot decimal)"),
        ("#.##0,00", "1.234,56 (European dot thousands, comma decimal)"),
        ("# ##0,00", "1 234,56 (French / SI space thousands)"),
    ]

    name = models.CharField(max_length=255, help_text="Profile title (e.g. UK Standard, Gulf Regional).")
    code = models.CharField(max_length=50, blank=True, help_text="Short profile identifier.")
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="locale_settings",
        help_text="Specific project override (leave blank for workspace default).",
    )
    language = models.ForeignKey(
        "core.Language",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Standard platform language pack.",
    )
    time_zone = models.ForeignKey(
        "core.TimeZone",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Standard IANA timezone for schedule calculations and milestone dates.",
    )
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Presentation currency for project financials.",
    )
    date_format = models.CharField(
        max_length=40,
        choices=DATE_FORMAT_CHOICES,
        default="YYYY-MM-DD",
        help_text="Display format for project schedule dates.",
    )
    time_format = models.CharField(
        max_length=10,
        choices=TIME_FORMAT_CHOICES,
        default="24h",
        help_text="Time display format.",
    )
    first_day_of_week = models.PositiveSmallIntegerField(
        choices=FIRST_DAY_CHOICES,
        default=1,
        help_text="First day of the week for scheduling and Gantt views.",
    )
    number_format = models.CharField(
        max_length=40,
        choices=NUMBER_FORMAT_CHOICES,
        default="#,##0.00",
        help_text="Formatting notation for numbers and currencies.",
    )
    working_hours_per_day = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal("8.00"),
        validators=[MinValueValidator(Decimal("1.00")), MaxValueValidator(Decimal("24.00"))],
        help_text="Standard business working hours per day.",
    )
    working_days_pattern = models.JSONField(
        default=list,
        blank=True,
        help_text="List of active working ISO weekday integers: 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat, 7=Sun.",
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Workspace default profile for projects without custom override.",
    )
    is_active = models.BooleanField(default=True, help_text="Active profile.")

    class Meta:
        ordering = ["-is_default", "name"]
        indexes = [
            models.Index(fields=["tenant", "project"], name="pls_tnt_prj_idx"),
            models.Index(fields=["tenant", "is_default"], name="pls_tnt_def_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name}"

    def clean(self):
        super().clean()
        if self.tenant_id and self.project_id and self.project.tenant_id != self.tenant_id:
            raise ValidationError({"project": "The project belongs to another tenant."})
        if self.is_default and self.project_id:
            raise ValidationError({"is_default": "Only a workspace-wide profile can be the default."})
        if self.project_id and self.is_active:
            overrides = ProjectLocaleSetting.objects.filter(
                tenant=self.tenant,
                project_id=self.project_id,
                is_active=True,
            )
            if self.pk:
                overrides = overrides.exclude(pk=self.pk)
            if overrides.exists():
                raise ValidationError({
                    "project": "Only one active locale override can apply to a project."
                })
        if not isinstance(self.working_days_pattern, list) or not self.working_days_pattern:
            raise ValidationError({"working_days_pattern": "Select at least one working day."})
        if any(
            isinstance(day, bool) or not isinstance(day, int) or day not in range(1, 8)
            for day in self.working_days_pattern
        ):
            raise ValidationError({"working_days_pattern": "Working days must be integers from 1 to 7."})
        if len(set(self.working_days_pattern)) != len(self.working_days_pattern):
            raise ValidationError({"working_days_pattern": "Working days must be unique."})
        if self.is_default and self.tenant_id and not self.project_id:
            qs = ProjectLocaleSetting.objects.filter(
                tenant=self.tenant,
                project__isnull=True,
                is_default=True,
            )
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({"is_default": "A default workspace locale profile already exists."})

    @property
    def active_badge_class(self):
        return "badge-green" if self.is_active else "badge-muted"

    @property
    def scope_badge_class(self):
        return "badge-info" if self.project_id else "badge-slate"

    @property
    def working_days_display(self):
        days_map = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun"}
        if not self.working_days_pattern:
            return "Not configured"
        return ", ".join(days_map.get(d, str(d)) for d in self.working_days_pattern)


def resolve_project_locale(project):
    tenant = project.tenant
    from apps.core.models.Calendar import BusinessCalendar
    from apps.core.models.Localization import LocaleProfile

    override = (
        ProjectLocaleSetting.objects.filter(
            tenant=tenant,
            project=project,
            is_active=True,
        )
        .select_related("language", "time_zone", "currency")
        .order_by("-updated_at", "-id")
        .first()
    )
    locale_profile = (
        LocaleProfile.objects.filter(tenant=tenant)
        .select_related("language", "time_zone", "base_currency")
        .first()
    )
    calendar = BusinessCalendar.objects.filter(tenant=tenant).first()
    working_days = override.working_days_pattern if override else None
    if not working_days and calendar is not None:
        working_days = calendar.working_days
    return {
        "tenant": tenant,
        "override": override,
        "locale_profile": locale_profile,
        "calendar": calendar,
        "language": override.language if override and override.language_id else (
            locale_profile.language if locale_profile else None
        ),
        "time_zone": override.time_zone if override and override.time_zone_id else (
            locale_profile.time_zone if locale_profile else None
        ),
        "currency": override.currency if override and override.currency_id else (
            locale_profile.base_currency if locale_profile else None
        ),
        "date_format": override.date_format if override else (
            locale_profile.date_format if locale_profile else None
        ),
        "time_format": override.time_format if override else (
            locale_profile.time_format if locale_profile else None
        ),
        "number_format": override.number_format if override else (
            locale_profile.number_format if locale_profile else None
        ),
        "first_day_of_week": override.first_day_of_week if override else (
            locale_profile.first_day_of_week if locale_profile else None
        ),
        "working_days": list(working_days or []),
        "working_hours_per_day": (
            override.working_hours_per_day if override else None
        ),
    }
