from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class NaturalLanguageQuery(TenantNumbered):
    NUMBER_PREFIX = "BNLQ"

    INPUT_MODALITY_CHOICES = [
        ("text", "Typed Text Query"),
        ("voice", "Spoken Voice Query"),
        ("api", "External API / Webhook"),
    ]

    INTENT_TYPE_CHOICES = [
        ("metric_lookup", "Metric Value Lookup"),
        ("trend_analysis", "Trend & Time-Series Analysis"),
        ("ranking_top_bottom", "Top / Bottom Ranking"),
        ("comparative_analysis", "Dimensional Comparison"),
        ("distribution", "Data Distribution & Histogram"),
        ("correlation", "Measure Correlation"),
        ("drill_down", "Hierarchical Drill-Down"),
    ]

    CHART_TYPE_CHOICES = [
        ("metric_card", "Single KPI Metric Card"),
        ("bar_chart", "Vertical Bar Chart"),
        ("horizontal_bar", "Horizontal Bar Chart"),
        ("line_chart", "Time-Series Line Chart"),
        ("donut_chart", "Proportional Donut Chart"),
        ("scatter_plot", "Correlation Scatter Plot"),
        ("pivot_table", "Multi-Level Pivot Matrix"),
        ("data_table", "Tabular Record Grid"),
    ]

    EXECUTION_STATUS_CHOICES = [
        ("pending", "Pending Execution"),
        ("completed", "Completed Successfully"),
        ("failed", "Execution Failed"),
        ("ambiguous", "Ambiguous Query / Clarification Needed"),
    ]

    USER_RATING_CHOICES = [
        ("unrated", "Unrated"),
        ("helpful", "Helpful / Accurate"),
        ("unhelpful", "Unhelpful / Inaccurate"),
    ]

    query_text = models.CharField(
        max_length=500,
        help_text="Plain-language analytical question asked by user",
    )
    input_modality = models.CharField(
        max_length=16,
        choices=INPUT_MODALITY_CHOICES,
        default="text",
    )
    intent_type = models.CharField(
        max_length=24,
        choices=INTENT_TYPE_CHOICES,
        default="metric_lookup",
    )
    semantic_model = models.ForeignKey(
        "bi.SemanticModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="nlq_queries",
    )
    warehouse_table = models.ForeignKey(
        "bi.WarehouseTable",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="nlq_queries",
    )
    kpi_definition = models.ForeignKey(
        "bi.KpiDefinition",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="nlq_queries",
    )
    conversation_session = models.ForeignKey(
        "bi.BiConversationSession",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="queries",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="nlq_queries",
    )
    parsed_measures = models.JSONField(
        default=list,
        blank=True,
        help_text="List of extracted metrics / aggregations",
    )
    parsed_dimensions = models.JSONField(
        default=list,
        blank=True,
        help_text="List of extracted grouping dimensions",
    )
    parsed_filters = models.JSONField(
        default=dict,
        blank=True,
        help_text="Dictionary of extracted filter conditions",
    )
    generated_sql = models.TextField(
        blank=True,
        help_text="Executable SQL or ORM expression generated from intent",
    )
    chart_type = models.CharField(
        max_length=20,
        choices=CHART_TYPE_CHOICES,
        default="bar_chart",
    )
    chart_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Chart.js visualization payload",
    )
    result_summary = models.JSONField(
        default=dict,
        blank=True,
        help_text="Tabular data payload or summarized metric cards",
    )
    confidence_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("85.00"),
        help_text="Intent mapping confidence percentage",
    )
    execution_status = models.CharField(
        max_length=16,
        choices=EXECUTION_STATUS_CHOICES,
        default="completed",
    )
    execution_duration_ms = models.IntegerField(
        default=0,
        help_text="Query parsing and data retrieval latency in milliseconds",
    )
    audio_duration_seconds = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Voice audio input duration in seconds",
    )
    user_rating = models.CharField(
        max_length=16,
        choices=USER_RATING_CHOICES,
        default="unrated",
    )
    user_feedback_notes = models.TextField(
        blank=True,
        help_text="User explanation if rating is unhelpful",
    )

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="bi_bnlq_tenant_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "input_modality"], name="idx_bnlq_ten_mod"),
            models.Index(fields=["tenant", "intent_type"], name="idx_bnlq_ten_intent"),
            models.Index(fields=["tenant", "execution_status"], name="idx_bnlq_ten_status"),
            models.Index(fields=["tenant", "created_at"], name="idx_bnlq_ten_created"),
        ]

    def __str__(self):
        truncated = (self.query_text[:47] + "...") if len(self.query_text) > 50 else self.query_text
        return f"{self.number} — {truncated}"

    def get_absolute_url(self):
        return reverse("bi:natural_language_query_detail", kwargs={"pk": self.pk})

    @property
    def status_badge_color(self):
        if self.execution_status == "completed":
            return "badge-green"
        if self.execution_status == "pending":
            return "badge-amber"
        if self.execution_status == "ambiguous":
            return "badge-info"
        if self.execution_status == "failed":
            return "badge-red"
        return "badge-slate"

    @property
    def modality_badge_color(self):
        if self.input_modality == "voice":
            return "badge-info"
        if self.input_modality == "api":
            return "badge-purple" if hasattr(self, "dummy") else "badge-info"
        return "badge-slate"

    @property
    def rating_badge_color(self):
        if self.user_rating == "helpful":
            return "badge-green"
        if self.user_rating == "unhelpful":
            return "badge-red"
        return "badge-slate"
