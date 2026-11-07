from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class SmartDataPrepSuggestion(TenantNumbered):
    NUMBER_PREFIX = "BSDP"

    SUGGESTION_TYPE_CHOICES = [
        ("join_relationship", "Suggested Foreign Key Join"),
        ("type_cast", "Data Type Inference / Cast"),
        ("split_column", "Column Extraction / Delimiter Split"),
        ("impute_missing", "Missing Value Imputation"),
        ("deduplicate_fuzzy", "Fuzzy Match Deduplication"),
        ("filter_outliers", "Statistical Outlier Filter"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending Review"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("applied", "Applied"),
    ]

    target_table = models.ForeignKey(
        "bi.WarehouseTable",
        on_delete=models.CASCADE,
        related_name="target_prep_suggestions",
    )
    target_column = models.CharField(max_length=100, help_text="Column in target table being transformed or joined")
    suggestion_type = models.CharField(max_length=24, choices=SUGGESTION_TYPE_CHOICES, default="join_relationship")
    related_table = models.ForeignKey(
        "bi.WarehouseTable",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="related_prep_suggestions",
        help_text="Joining table for relationship suggestions",
    )
    related_column = models.CharField(max_length=100, blank=True, help_text="Key column in related table")
    confidence_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("85.00"))
    rationale = models.TextField(help_text="AI rationale explaining why this preparation step or relationship is recommended")
    suggested_config = models.JSONField(default=dict, blank=True, help_text="Rule parameters, join syntax, regex expressions, or imputation settings")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pending")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_prep_suggestions",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bsdp_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "suggestion_type"], name="idx_bsdp_ten_type"),
            models.Index(fields=["tenant", "status"], name="idx_bsdp_ten_stat"),
            models.Index(fields=["tenant", "target_table"], name="idx_bsdp_ten_tbl"),
        ]

    def __str__(self):
        return f"{self.number} — {self.get_suggestion_type_display()} on {self.target_table.name}.{self.target_column}"

    def get_absolute_url(self):
        return reverse("bi:smart_data_prep_suggestion_detail", kwargs={"pk": self.pk})

    @property
    def badge_color(self):
        if self.status == "applied":
            return "badge-green"
        if self.status == "accepted":
            return "badge-info"
        if self.status == "rejected":
            return "badge-red"
        return "badge-amber"
