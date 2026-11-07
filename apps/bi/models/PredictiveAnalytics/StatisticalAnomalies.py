from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class StatisticalAnomaly(TenantNumbered):
    NUMBER_PREFIX = "BANM"

    ANOMALY_TYPE_CHOICES = [
        ("spike", "Positive Spike"),
        ("dip", "Negative Dip"),
        ("trend_break", "Structural Trend Break"),
        ("variance_outlier", "Variance Outlier"),
    ]

    METHOD_CHOICES = [
        ("z_score", "Z-Score (Sigma Deviation)"),
        ("iqr", "Interquartile Range (IQR)"),
        ("isolation_forest", "Isolation Forest"),
        ("moving_average", "Moving Average Envelope"),
    ]

    SEVERITY_CHOICES = [
        ("info", "Informational Notice"),
        ("warning", "Moderate Warning"),
        ("critical", "Critical Anomaly"),
    ]

    TRIAGE_CHOICES = [
        ("open", "Open / Unreviewed"),
        ("acknowledged", "Acknowledged"),
        ("investigating", "Under Investigation"),
        ("false_positive", "False Positive"),
        ("resolved", "Resolved"),
    ]

    title = models.CharField(max_length=200)
    model = models.ForeignKey(
        "bi.PredictiveModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="detected_anomalies",
    )
    semantic_model = models.ForeignKey(
        "bi.SemanticModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="statistical_anomalies",
    )
    kpi_definition = models.ForeignKey(
        "bi.KpiDefinition",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="statistical_anomalies",
    )
    metric_name = models.CharField(max_length=120)
    anomaly_type = models.CharField(
        max_length=20,
        choices=ANOMALY_TYPE_CHOICES,
        default="spike",
    )
    detection_method = models.CharField(
        max_length=30,
        choices=METHOD_CHOICES,
        default="z_score",
    )
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default="warning",
    )
    observed_value = models.DecimalField(max_digits=16, decimal_places=4)
    expected_value = models.DecimalField(max_digits=16, decimal_places=4)
    deviation_percentage = models.DecimalField(max_digits=8, decimal_places=2)
    anomaly_timestamp = models.DateTimeField()
    root_cause_factors = models.JSONField(
        default=list,
        help_text="Contributing drivers and dimension segments",
    )
    triage_status = models.CharField(
        max_length=20,
        choices=TRIAGE_CHOICES,
        default="open",
    )
    resolution_notes = models.TextField(blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_anomalies",
    )

    class Meta:
        db_table = "bi_statistical_anomaly"
        ordering = ["-anomaly_timestamp"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_banm_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "triage_status"], name="idx_banm_ten_triage"),
            models.Index(fields=["tenant", "severity"], name="idx_banm_ten_sev"),
            models.Index(fields=["tenant", "assigned_to"], name="idx_banm_ten_user"),
        ]

    def __str__(self):
        return f"{self.title} ({self.number})"

    def get_absolute_url(self):
        return reverse("bi:statistical_anomaly_detail", kwargs={"pk": self.pk})

    def mark_triage(self, status, notes="", user=None):
        self.triage_status = status
        if notes:
            self.resolution_notes = notes
        if user:
            self.assigned_to = user
        self.save(update_fields=["triage_status", "resolution_notes", "assigned_to", "updated_at"])
