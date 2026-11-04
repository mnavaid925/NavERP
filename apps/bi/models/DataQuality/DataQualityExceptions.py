from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class DataQualityException(TenantNumbered):
    NUMBER_PREFIX = "BDQE"

    EXCEPTION_TYPE_CHOICES = [
        ("rule_violation", "Rule Assertion Violation"),
        ("duplicate_candidate", "Potential Duplicate Record Pair"),
        ("null_anomaly", "Null / Missing Mandatory Value"),
        ("range_outlier", "Range / Statistical Outlier"),
        ("format_invalid", "Invalid Pattern or Format"),
        ("referential_orphan", "Referential Integrity Orphan"),
    ]

    SEVERITY_CHOICES = [
        ("info", "Information"),
        ("warning", "Warning"),
        ("critical", "Critical"),
        ("fatal", "Fatal"),
    ]

    STATUS_CHOICES = [
        ("open", "Open / Unassigned"),
        ("investigating", "Under Investigation"),
        ("remediated", "Remediated & Verified"),
        ("suppressed_false_positive", "Suppressed (False Positive)"),
        ("accepted_risk", "Accepted Business Risk"),
        ("rejected", "Rejected / Invalid Exception"),
    ]

    REMEDIATION_ACTION_CHOICES = [
        ("none", "No Action Taken"),
        ("manual_edit", "Manual Record Correction"),
        ("automated_standardize", "Automated Standardization Applied"),
        ("merge_duplicate", "Duplicate Merged / Reconciled"),
        ("impute_value", "Value Imputed / Defaulted"),
        ("quarantine_row", "Record Quarantined"),
    ]

    rule = models.ForeignKey(
        "bi.DataQualityRule",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="exceptions",
        help_text="Associated data quality rule assertion",
    )
    profile = models.ForeignKey(
        "bi.DataQualityProfile",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="exceptions",
        help_text="Associated data quality profile run",
    )
    warehouse_table = models.ForeignKey(
        "bi.WarehouseTable",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quality_exceptions",
    )
    semantic_model = models.ForeignKey(
        "bi.SemanticModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quality_exceptions",
    )

    record_identifier = models.CharField(max_length=150, help_text="Primary key value or natural identifier of the offending record")
    target_column = models.CharField(max_length=100, blank=True, help_text="Target column where violation occurred")

    invalid_value = models.TextField(blank=True, help_text="Offending or anomalous value captured")
    expected_condition = models.CharField(max_length=255, blank=True, help_text="Description of what value was expected")

    exception_type = models.CharField(max_length=30, choices=EXCEPTION_TYPE_CHOICES, default="rule_violation")
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default="warning")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="open")

    remediation_action = models.CharField(max_length=30, choices=REMEDIATION_ACTION_CHOICES, default="none")
    proposed_value = models.TextField(blank=True, help_text="Suggested cleansed or standardized value")
    remediated_value = models.TextField(blank=True, help_text="Final corrected value applied")

    assigned_steward = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_quality_exceptions",
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "bi_data_quality_exception"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bdqe_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_bdqe_ten_status"),
            models.Index(fields=["tenant", "severity"], name="idx_bdqe_ten_sev"),
            models.Index(fields=["tenant", "exception_type"], name="idx_bdqe_ten_etype"),
            models.Index(fields=["tenant", "rule"], name="idx_bdqe_ten_rule"),
            models.Index(fields=["tenant", "is_active"], name="idx_bdqe_ten_active"),
            models.Index(fields=["tenant", "-created_at"], name="idx_bdqe_ten_created"),
        ]

    def __str__(self):
        return f"{self.number}: {self.record_identifier} ({self.get_exception_type_display()})"

    def get_absolute_url(self):
        return reverse("bi:data_quality_exception_detail", kwargs={"pk": self.pk})
