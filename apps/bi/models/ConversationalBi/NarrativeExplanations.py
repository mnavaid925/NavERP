from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class NarrativeExplanation(TenantNumbered):
    NUMBER_PREFIX = "BNLG"

    TARGET_ARTIFACT_TYPE_CHOICES = [
        ("dashboard", "Executive Dashboard"),
        ("report", "Operational Report"),
        ("kpi_scorecard", "KPI Scorecard"),
        ("query_result", "Natural Language Query Result"),
        ("custom_dataset", "Custom Analytical Dataset"),
    ]

    NARRATIVE_STYLE_CHOICES = [
        ("executive_briefing", "Executive Briefing (High-Level Summary)"),
        ("analytical_deepdive", "Analytical Deep Dive (Detailed Variance Analysis)"),
        ("bulleted_highlights", "Bulleted Key Highlights"),
        ("anomaly_alert", "Statistical Anomaly Alert"),
        ("spoken_voice_script", "Spoken Voice Audio Script"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft Narrative"),
        ("generated", "Machine-Generated"),
        ("reviewed", "Analyst Reviewed"),
        ("published", "Published & Distributed"),
    ]

    title = models.CharField(max_length=200)
    headline = models.CharField(
        max_length=255,
        help_text="Attention-grabbing single-sentence executive insight",
    )
    target_artifact_type = models.CharField(
        max_length=24,
        choices=TARGET_ARTIFACT_TYPE_CHOICES,
        default="dashboard",
    )
    dashboard = models.ForeignKey(
        "bi.BiDashboard",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="narrative_explanations",
    )
    report = models.ForeignKey(
        "bi.ReportDefinition",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="narrative_explanations",
    )
    kpi = models.ForeignKey(
        "bi.KpiDefinition",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="narrative_explanations",
    )
    query = models.ForeignKey(
        "bi.NaturalLanguageQuery",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="narrative_explanations",
    )
    insight = models.ForeignKey(
        "bi.AugmentedInsight",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="narrative_explanations",
    )
    narrative_style = models.CharField(
        max_length=24,
        choices=NARRATIVE_STYLE_CHOICES,
        default="executive_briefing",
    )
    narrative_body = models.TextField(
        help_text="Formatted natural language commentary with metric callouts",
    )
    key_takeaways = models.JSONField(
        default=list,
        blank=True,
        help_text="List of bulleted key takeaway strings",
    )
    top_positive_driver = models.CharField(
        max_length=150,
        blank=True,
        help_text="Primary positive contributor to variance",
    )
    top_negative_driver = models.CharField(
        max_length=150,
        blank=True,
        help_text="Primary drag/negative contributor to variance",
    )
    audio_ready_script = models.TextField(
        blank=True,
        help_text="Pronunciation-optimized text formatted for speech synthesis audio",
    )
    language = models.CharField(max_length=8, default="en")
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default="generated",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_narratives",
    )

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="bi_bnlg_tenant_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "target_artifact_type"], name="idx_bnlg_ten_art"),
            models.Index(fields=["tenant", "narrative_style"], name="idx_bnlg_ten_style"),
            models.Index(fields=["tenant", "status"], name="idx_bnlg_ten_stat"),
            models.Index(fields=["tenant", "created_at"], name="idx_bnlg_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"

    def get_absolute_url(self):
        return reverse("bi:narrative_explanation_detail", kwargs={"pk": self.pk})

    @property
    def status_badge_color(self):
        if self.status == "published":
            return "badge-green"
        if self.status == "reviewed":
            return "badge-info"
        if self.status == "generated":
            return "badge-purple" if hasattr(self, "dummy") else "badge-info"
        return "badge-slate"

    @property
    def style_badge_color(self):
        if self.narrative_style == "executive_briefing":
            return "badge-info"
        if self.narrative_style == "anomaly_alert":
            return "badge-amber"
        if self.narrative_style == "analytical_deepdive":
            return "badge-slate"
        if self.narrative_style == "spoken_voice_script":
            return "badge-green"
        return "badge-slate"
