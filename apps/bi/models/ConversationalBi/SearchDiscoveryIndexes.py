from decimal import Decimal

from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class SearchDiscoveryIndex(TenantNumbered):
    NUMBER_PREFIX = "BSDI"

    ASSET_TYPE_CHOICES = [
        ("dashboard", "Dashboard View"),
        ("report", "Operational Report"),
        ("kpi", "KPI / Metric Definition"),
        ("semantic_model", "Semantic Dataset"),
        ("warehouse_table", "Data Warehouse Table"),
        ("glossary_term", "Business Glossary Term"),
        ("ad_hoc_query", "Saved Ad-Hoc Analysis"),
    ]

    asset_name = models.CharField(max_length=200)
    asset_type = models.CharField(
        max_length=24,
        choices=ASSET_TYPE_CHOICES,
        default="dashboard",
    )
    target_url = models.CharField(
        max_length=255,
        help_text="Route or link pointing to indexed asset",
    )
    description = models.TextField(
        blank=True,
        help_text="Brief summary of asset purpose",
    )
    category = models.CharField(
        max_length=64,
        blank=True,
        help_text="Functional domain e.g. Finance, Sales, Operations, HR",
    )
    synonyms = models.JSONField(
        default=list,
        blank=True,
        help_text="List of colloquial aliases, e.g. ['sales', 'revenue', 'turnover']",
    )
    search_keywords = models.TextField(
        blank=True,
        help_text="Space or comma-delimited tokens indexed for search discovery",
    )

    semantic_model = models.ForeignKey(
        "bi.SemanticModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="discovery_indexes",
    )
    dashboard = models.ForeignKey(
        "bi.BiDashboard",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="discovery_indexes",
    )
    report = models.ForeignKey(
        "bi.ReportDefinition",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="discovery_indexes",
    )
    kpi = models.ForeignKey(
        "bi.KpiDefinition",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="discovery_indexes",
    )
    warehouse_table = models.ForeignKey(
        "bi.WarehouseTable",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="discovery_indexes",
    )
    glossary_term = models.ForeignKey(
        "bi.BusinessGlossaryTerm",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="discovery_indexes",
    )

    relevance_weight = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal("1.00"),
        help_text="Multiplier boost for ranking relevance",
    )
    search_hit_count = models.PositiveIntegerField(
        default=0,
        help_text="Telemetry count of discovery queries matching this asset",
    )
    view_count = models.PositiveIntegerField(
        default=0,
        help_text="Telemetry count of click-throughs from search",
    )
    is_featured = models.BooleanField(
        default=False,
        help_text="Pin to curated recommended discovery cards",
    )
    is_verified = models.BooleanField(
        default=True,
        help_text="Verified enterprise asset badge",
    )

    class Meta:
        ordering = ["-is_featured", "-relevance_weight", "-view_count", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bsdi_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "asset_type"], name="idx_bsdi_ten_type"),
            models.Index(fields=["tenant", "category"], name="idx_bsdi_ten_cat"),
            models.Index(fields=["tenant", "is_featured"], name="idx_bsdi_ten_feat"),
            models.Index(fields=["tenant", "is_verified"], name="idx_bsdi_ten_ver"),
            models.Index(fields=["tenant", "is_featured", "-relevance_weight"], name="idx_bsdi_ten_feat_rw"),
        ]

    def __str__(self):
        return f"{self.number} — {self.asset_name}"

    def get_absolute_url(self):
        return reverse("bi:search_discovery_index_detail", kwargs={"pk": self.pk})

    @property
    def asset_type_badge_color(self):
        if self.asset_type == "dashboard":
            return "badge-info"
        if self.asset_type == "report":
            return "badge-slate"
        if self.asset_type == "kpi":
            return "badge-green"
        if self.asset_type in ["semantic_model", "warehouse_table"]:
            return "badge-amber"
        return "badge-muted"

    @property
    def type_badge_color(self):
        return self.asset_type_badge_color

    @property
    def verification_badge_color(self):
        return "badge-green" if self.is_verified else "badge-slate"
