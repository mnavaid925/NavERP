from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from apps.bi.models._base import TenantNumbered


class PredictiveModel(TenantNumbered):
    NUMBER_PREFIX = "BPML"

    PROBLEM_TYPE_CHOICES = [
        ("time_series_forecast", "Time-Series Forecasting"),
        ("binary_classification", "Binary Classification (Propensity/Churn)"),
        ("multiclass_classification", "Multiclass Classification"),
        ("regression", "Value Regression (Numeric Prediction)"),
        ("anomaly_detection", "Statistical Anomaly Detection"),
    ]

    ALGORITHM_CHOICES = [
        ("linear_regression", "Linear / Ridge Regression"),
        ("logistic_regression", "Logistic Regression"),
        ("random_forest", "Random Forest Ensemble"),
        ("gradient_boosting", "Gradient Boosted Trees (GBM)"),
        ("exponential_smoothing", "Holt-Winters / Exponential Smoothing"),
        ("arima", "Auto-ARIMA"),
        ("isolation_forest", "Isolation Forest"),
        ("z_score", "Moving Z-Score / Statistical Baseline"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft Configuration"),
        ("training", "Training / Fitting"),
        ("active", "Active / Deployed"),
        ("under_review", "Under Review"),
        ("retired", "Retired"),
    ]

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120)
    description = models.TextField(blank=True)
    problem_type = models.CharField(
        max_length=35,
        choices=PROBLEM_TYPE_CHOICES,
        default="time_series_forecast",
    )
    algorithm = models.CharField(
        max_length=40,
        choices=ALGORITHM_CHOICES,
        default="exponential_smoothing",
    )
    semantic_model = models.ForeignKey(
        "bi.SemanticModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="predictive_models",
    )
    warehouse_table = models.ForeignKey(
        "bi.WarehouseTable",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="predictive_models",
    )
    target_metric = models.CharField(
        max_length=120,
        help_text="Target column or KPI metric being predicted",
    )
    features_list = models.JSONField(
        default=list,
        help_text="List of feature column names used for training",
    )
    hyperparameters = models.JSONField(
        default=dict,
        help_text="Model tuning hyperparameters",
    )
    model_version = models.CharField(max_length=20, default="1.0.0")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
    )
    accuracy_metric_name = models.CharField(
        max_length=30,
        default="R2",
        help_text="Evaluation metric name (e.g., R2, RMSE, AUC, F1, MAPE)",
    )
    accuracy_metric_value = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Validated performance score",
    )
    feature_importance = models.JSONField(
        default=dict,
        help_text="Relative feature weightings / contributions",
    )
    drift_threshold = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=15.00,
        help_text="Percentage drift trigger for re-training",
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_predictive_models",
    )

    class Meta:
        db_table = "bi_predictive_model"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "slug"], name="bi_bpml_tenant_slug_uniq"),
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bpml_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "-created_at"], name="idx_bpml_ten_created"),
            models.Index(fields=["tenant", "problem_type"], name="idx_bpml_ten_prob"),
            models.Index(fields=["tenant", "status"], name="idx_bpml_ten_stat"),
            models.Index(fields=["tenant", "created_by"], name="idx_bpml_ten_user"),
        ]

    def __str__(self):
        return f"{self.name} v{self.model_version} ({self.number})"

    def get_absolute_url(self):
        return reverse("bi:predictive_model_detail", kwargs={"pk": self.pk})

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or "model"
            self.slug = base_slug[:120]
        super().save(*args, **kwargs)

    def trigger_training(self):
        """Simulates an AutoML model training run."""
        import random
        from decimal import Decimal
        self.status = "active"
        if self.problem_type in ("binary_classification", "multiclass_classification"):
            self.accuracy_metric_name = "AUC"
            self.accuracy_metric_value = Decimal(str(round(random.uniform(0.82, 0.96), 4)))
        elif self.problem_type == "time_series_forecast":
            self.accuracy_metric_name = "MAPE"
            self.accuracy_metric_value = Decimal(str(round(random.uniform(4.5, 9.2), 2)))
        elif self.problem_type == "anomaly_detection":
            self.accuracy_metric_name = "F1"
            self.accuracy_metric_value = Decimal(str(round(random.uniform(0.85, 0.94), 4)))
        else:
            self.accuracy_metric_name = "R2"
            self.accuracy_metric_value = Decimal(str(round(random.uniform(0.78, 0.95), 4)))
        
        self.feature_importance = {
            "historical_mean": 0.35,
            "seasonality_factor": 0.25,
            "period_trend": 0.20,
            "external_indicators": 0.20,
        }
        self.save(update_fields=["status", "accuracy_metric_name", "accuracy_metric_value", "feature_importance", "updated_at"])
