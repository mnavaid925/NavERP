from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class AnalyticsRecommendation(TenantNumbered):
    NUMBER_PREFIX = "BARC"

    RECOMMENDATION_TYPE_CHOICES = [
        ("dashboard", "Interactive Dashboard"),
        ("report", "Operational Report"),
        ("kpi", "KPI Metric Definition"),
        ("dataset", "Semantic Dataset"),
        ("drill_path", "Guided Drill Path"),
    ]

    REASON_CHOICES = [
        ("peer_usage", "Popular Among Your Peers"),
        ("trending_metric", "High Metric Volatility / Trend"),
        ("anomaly_in_domain", "Recent Anomaly Detected in Domain"),
        ("recent_search", "Matches Recent Data Inquiries"),
        ("role_relevance", "Standard for Your Organizational Role"),
    ]

    STATUS_CHOICES = [
        ("active", "Active Recommendation"),
        ("clicked", "Viewed / Clicked"),
        ("dismissed", "Dismissed by User"),
        ("saved", "Saved / Bookmarked"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="analytics_recommendations",
    )
    recommendation_type = models.CharField(max_length=24, choices=RECOMMENDATION_TYPE_CHOICES, default="dashboard")
    target_title = models.CharField(max_length=200, help_text="Title of the recommended asset")
    target_url = models.CharField(max_length=255, help_text="Direct internal URL link to view the recommended asset")
    reason = models.CharField(max_length=24, choices=REASON_CHOICES, default="role_relevance")
    rationale_text = models.TextField(blank=True, help_text="Friendly explanation of why this asset is suggested")
    affinity_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("80.00"), help_text="Match affinity score (0.00 to 100.00%)")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="active")

    dashboard = models.ForeignKey(
        "bi.BiDashboard",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recommendations",
    )
    report = models.ForeignKey(
        "bi.ReportDefinition",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recommendations",
    )
    kpi = models.ForeignKey(
        "bi.KpiDefinition",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recommendations",
    )
    semantic_model = models.ForeignKey(
        "bi.SemanticModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recommendations",
    )
    last_interacted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-affinity_score", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_barc_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "user", "status"], name="idx_barc_ten_user_stat"),
            models.Index(fields=["tenant", "recommendation_type"], name="idx_barc_ten_type"),
            models.Index(fields=["tenant", "affinity_score"], name="idx_barc_ten_score"),
        ]

    def __str__(self):
        return f"{self.number} — Suggest {self.target_title} to {self.user.username}"

    def get_absolute_url(self):
        return reverse("bi:analytics_recommendation_detail", kwargs={"pk": self.pk})

    @property
    def badge_color(self):
        if self.status == "saved":
            return "badge-green"
        if self.status == "clicked":
            return "badge-info"
        if self.status == "dismissed":
            return "badge-slate"
        return "badge-amber"
