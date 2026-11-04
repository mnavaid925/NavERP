from decimal import Decimal
from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class DataQualityProfile(TenantNumbered):
    NUMBER_PREFIX = "BDQP"

    TARGET_TYPE_CHOICES = [
        ("warehouse_table", "Warehouse Table"),
        ("semantic_model", "Semantic Model"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending / Scheduled"),
        ("profiling", "Profiling In Progress"),
        ("completed", "Completed Successfully"),
        ("failed", "Profiling Failed"),
    ]

    name = models.CharField(max_length=150, help_text="Profile run name or dataset identifier")
    target_type = models.CharField(max_length=25, choices=TARGET_TYPE_CHOICES, default="warehouse_table")

    warehouse_table = models.ForeignKey(
        "bi.WarehouseTable",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="quality_profiles",
        help_text="Target warehouse table to profile",
    )
    semantic_model = models.ForeignKey(
        "bi.SemanticModel",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="quality_profiles",
        help_text="Target semantic model to profile",
    )

    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="pending")
    total_row_count = models.BigIntegerField(default=0, help_text="Total rows analyzed during profiling run")
    total_column_count = models.PositiveIntegerField(default=0, help_text="Total columns analyzed")

    completeness_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("100.00"),
        help_text="Percentage of populated, non-null values",
    )
    uniqueness_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("100.00"),
        help_text="Percentage of unique distinct records across primary keys",
    )
    validity_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("100.00"),
        help_text="Percentage of values conforming to expected data types and masks",
    )

    column_profiles_json = models.JSONField(
        default=list,
        blank=True,
        help_text="Statistical metadata per column (nulls, distinct, min, max, patterns)",
    )

    profiled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    profiled_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Execution run duration in seconds",
    )

    error_message = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "bi_data_quality_profile"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bdqp_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "target_type"], name="idx_bdqp_ten_ttype"),
            models.Index(fields=["tenant", "status"], name="idx_bdqp_ten_status"),
            models.Index(fields=["tenant", "warehouse_table"], name="idx_bdqp_ten_whtbl"),
            models.Index(fields=["tenant", "semantic_model"], name="idx_bdqp_ten_smd"),
            models.Index(fields=["tenant", "is_active"], name="idx_bdqp_ten_active"),
            models.Index(fields=["tenant", "-created_at"], name="idx_bdqp_ten_created"),
        ]

    def __str__(self):
        return f"{self.name} ({self.number})"

    def get_absolute_url(self):
        return reverse("bi:data_quality_profile_detail", kwargs={"pk": self.pk})
