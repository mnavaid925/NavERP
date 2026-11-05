from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class BiDashboard(TenantNumbered):
    NUMBER_PREFIX = "BDSH"

    CATEGORY_CHOICES = [
        ("executive", "Executive & C-Suite"),
        ("finance", "Finance & Accounting"),
        ("sales_crm", "Sales & CRM"),
        ("supply_chain", "Supply Chain & Inventory"),
        ("operations", "Plant & Operations"),
        ("hr", "Human Resources & Talent"),
        ("custom", "Custom Dashboard"),
    ]

    LAYOUT_TYPE_CHOICES = [
        ("grid_12", "12-Column Responsive Grid"),
        ("executive_summary", "Executive Summary Blueprint"),
        ("operational_monitoring", "Operational Monitoring Board"),
        ("freeform", "Flexible Fluid Layout"),
    ]

    THEME_CHOICES = [
        ("slate_corporate", "Corporate Slate (Default)"),
        ("indigo_modern", "Modern Indigo"),
        ("emerald_growth", "Emerald Financial"),
        ("amber_industrial", "Amber Industrial / Logistics"),
        ("dark_observability", "High-Contrast Dark Mode"),
    ]

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=100)
    category = models.CharField(max_length=40, choices=CATEGORY_CHOICES, default="executive")
    layout_type = models.CharField(max_length=40, choices=LAYOUT_TYPE_CHOICES, default="grid_12")
    refresh_interval_seconds = models.PositiveIntegerField(
        default=0,
        help_text="Auto-refresh timer in seconds (0 = manual refresh only, 10, 30, 60, 300, 900, 3600)",
    )
    theme = models.CharField(max_length=40, choices=THEME_CHOICES, default="slate_corporate")
    role_required = models.CharField(
        max_length=60,
        blank=True,
        default="all",
        help_text="Restricted role required to access dashboard: 'all', 'executive', etc.",
    )
    org_unit = models.ForeignKey(
        "core.OrgUnit",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bi_dashboards",
        help_text="Optional link to internal OrgUnit / Department",
    )
    is_published = models.BooleanField(
        default=False,
        help_text="True if published and visible to authorized users; False if draft",
    )
    is_template = models.BooleanField(
        default=False,
        help_text="True if available as a starter template for new dashboards",
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Tenant default landing dashboard",
    )
    is_kiosk_enabled = models.BooleanField(
        default=False,
        help_text="Permits full-screen headerless display mode for office monitors",
    )
    color_palette_json = models.JSONField(
        default=list,
        help_text="Custom hex color sequence for charts: ['#1e40af', '#0d9488', ...]",
    )
    config_json = models.JSONField(
        default=dict,
        help_text="Advanced dashboard settings: margins, default date range, animation flags",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_bi_dashboards",
    )
    view_count = models.PositiveIntegerField(default=0)
    last_viewed_at = models.DateTimeField(null=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "bi_dashboard"
        ordering = ["-is_default", "title"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "slug"], name="bi_bdsh_tenant_slug_uniq"),
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bdsh_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "category"], name="idx_bdsh_ten_cat"),
            models.Index(fields=["tenant", "is_published"], name="idx_bdsh_ten_pub"),
            models.Index(fields=["tenant", "is_default"], name="idx_bdsh_ten_def"),
            models.Index(fields=["tenant", "org_unit"], name="idx_bdsh_ten_org"),
            models.Index(fields=["tenant", "is_active"], name="idx_bdsh_ten_act"),
        ]

    def __str__(self):
        return f"{self.title} ({self.number})"

    def get_absolute_url(self):
        return reverse("bi:bi_dashboard_detail", kwargs={"pk": self.pk})

    @property
    def badge_theme(self):
        mapping = {
            "slate_corporate": "badge-slate",
            "indigo_modern": "badge-info",
            "emerald_growth": "badge-green",
            "amber_industrial": "badge-amber",
            "dark_observability": "badge-muted",
        }
        return mapping.get(self.theme, "badge-slate")

    @property
    def badge_category(self):
        mapping = {
            "executive": "badge-info",
            "finance": "badge-green",
            "sales_crm": "badge-amber",
            "supply_chain": "badge-info",
            "operations": "badge-slate",
            "hr": "badge-muted",
            "custom": "badge-slate",
        }
        return mapping.get(self.category, "badge-slate")
