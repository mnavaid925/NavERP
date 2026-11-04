from decimal import Decimal
from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class DataQualityRule(TenantNumbered):
    NUMBER_PREFIX = "BDQR"

    RULE_CATEGORY_CHOICES = [
        ("validation", "Validation & Accuracy Check"),
        ("consistency", "Consistency & Referential Integrity"),
        ("uniqueness", "Uniqueness & Deduplication"),
        ("standardization", "Standardization & Cleansing"),
        ("custom_sql", "Custom SQL Assertion"),
    ]

    DIMENSION_CHOICES = [
        ("completeness", "Completeness"),
        ("accuracy", "Accuracy"),
        ("consistency", "Consistency"),
        ("timeliness", "Timeliness"),
        ("uniqueness", "Uniqueness"),
        ("validity", "Validity"),
    ]

    TARGET_TYPE_CHOICES = [
        ("warehouse_table", "Warehouse Table"),
        ("semantic_model", "Semantic Model"),
    ]

    RULE_TYPE_CHOICES = [
        ("not_null", "Not Null / Mandatory Check"),
        ("unique", "Uniqueness Constraint"),
        ("range_between", "Value Range Boundary (Min/Max)"),
        ("regex_pattern", "Regex Pattern Matching"),
        ("set_membership", "Allowed Set Membership / Enum"),
        ("referential_integrity", "Referential Integrity / Foreign Key"),
        ("date_freshness", "Data Freshness / Timeliness SLA"),
        ("string_standardization", "Standardization (Trim, Case, Regex Normalize)"),
        ("duplicate_cluster", "Fuzzy Duplicate Cluster Check"),
        ("custom_sql", "Custom SQL Boolean Condition"),
    ]

    SEVERITY_CHOICES = [
        ("info", "Information (Advisory)"),
        ("warning", "Warning (Low Impact)"),
        ("critical", "Critical (Business SLA Impact)"),
        ("fatal", "Fatal (Pipeline Blocking)"),
    ]

    STATUS_CHOICES = [
        ("passed", "Passed"),
        ("warning", "Warning (Within Tolerance)"),
        ("failed", "Failed"),
        ("error", "Execution Error"),
        ("skipped", "Skipped"),
    ]

    name = models.CharField(max_length=150, help_text="Human-readable rule assertion title")
    code = models.SlugField(max_length=60, help_text="Unique rule identifier slug")

    rule_category = models.CharField(max_length=25, choices=RULE_CATEGORY_CHOICES, default="validation")
    dimension = models.CharField(max_length=20, choices=DIMENSION_CHOICES, default="validity")
    target_type = models.CharField(max_length=25, choices=TARGET_TYPE_CHOICES, default="warehouse_table")

    warehouse_table = models.ForeignKey(
        "bi.WarehouseTable",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="quality_rules",
        help_text="Target warehouse table to evaluate",
    )
    semantic_model = models.ForeignKey(
        "bi.SemanticModel",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="quality_rules",
        help_text="Target semantic model to evaluate",
    )

    target_column = models.CharField(max_length=100, blank=True, help_text="Target column or leave blank for table-level rules")
    rule_type = models.CharField(max_length=30, choices=RULE_TYPE_CHOICES, default="not_null")
    parameters_json = models.JSONField(default=dict, blank=True, help_text="Rule parameters (min, max, regex, enums, SQL)")

    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default="warning")
    failure_tolerance_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Maximum failure rate percentage allowed before rule fails",
    )

    last_run_at = models.DateTimeField(null=True, blank=True)
    last_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="passed")
    passed_records_count = models.BigIntegerField(default=0)
    failed_records_count = models.BigIntegerField(default=0)
    pass_rate_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("100.00"))

    steward = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stewarded_quality_rules",
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "bi_data_quality_rule"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="bi_bdqr_tenant_code_uniq"),
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bdqr_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "rule_category"], name="idx_bdqr_ten_rcat"),
            models.Index(fields=["tenant", "dimension"], name="idx_bdqr_ten_dim"),
            models.Index(fields=["tenant", "last_status"], name="idx_bdqr_ten_lstat"),
            models.Index(fields=["tenant", "severity"], name="idx_bdqr_ten_sev"),
            models.Index(fields=["tenant", "warehouse_table"], name="idx_bdqr_ten_wtbl"),
            models.Index(fields=["tenant", "semantic_model"], name="idx_bdqr_ten_smdl"),
            models.Index(fields=["tenant", "-last_run_at"], name="idx_bdqr_ten_lrun"),
            models.Index(fields=["tenant", "is_active"], name="idx_bdqr_ten_active"),
            models.Index(fields=["tenant", "-created_at"], name="idx_bdqr_ten_created"),
        ]

    def __str__(self):
        return f"{self.name} ({self.number})"

    def get_absolute_url(self):
        return reverse("bi:data_quality_rule_detail", kwargs={"pk": self.pk})
