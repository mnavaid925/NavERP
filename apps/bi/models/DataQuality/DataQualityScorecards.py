from decimal import Decimal
from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class DataQualityScorecard(TenantNumbered):
    NUMBER_PREFIX = "BDQS"

    SCOPE_TYPE_CHOICES = [
        ("warehouse_table", "Warehouse Table"),
        ("semantic_model", "Semantic Model"),
        ("data_mart", "Data Mart Domain"),
        ("tenant_wide", "Tenant-Wide Aggregate"),
    ]

    GRADE_CHOICES = [
        ("A", "Grade A: Excellent (>95%)"),
        ("B", "Grade B: Good (85-95%)"),
        ("C", "Grade C: Acceptable (75-84%)"),
        ("D", "Grade D: Poor (60-74%)"),
        ("F", "Grade F: Failing (<60%)"),
    ]

    HEALTH_STATUS_CHOICES = [
        ("healthy", "Healthy (Meets SLAs)"),
        ("needs_attention", "Needs Attention (Minor Breaches)"),
        ("critical", "Critical (Major SLA Breaches)"),
        ("failing", "Failing (Data Untrusted)"),
    ]

    EVALUATION_PERIOD_CHOICES = [
        ("ad_hoc", "Ad-Hoc / Current"),
        ("daily", "Daily Snapshot"),
        ("weekly", "Weekly Rollup"),
        ("monthly", "Monthly Scorecard"),
    ]

    name = models.CharField(max_length=150, help_text="Executive scorecard title")
    code = models.SlugField(max_length=60, help_text="Unique scorecard identifier slug")

    scope_type = models.CharField(max_length=25, choices=SCOPE_TYPE_CHOICES, default="warehouse_table")

    warehouse_table = models.ForeignKey(
        "bi.WarehouseTable",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="scorecards",
        help_text="Target warehouse table if scope is warehouse table",
    )
    semantic_model = models.ForeignKey(
        "bi.SemanticModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="scorecards",
        help_text="Target semantic model if scope is semantic model",
    )
    data_mart = models.ForeignKey(
        "bi.DataMart",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="scorecards",
        help_text="Target analytical data mart if scope is data mart domain",
    )
    org_unit = models.ForeignKey(
        "core.OrgUnit",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quality_scorecards",
        help_text="Owning department or organizational unit",
    )

    overall_quality_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("100.00"),
        help_text="Aggregated Data Trust Index (0.00% - 100.00%)",
    )
    completeness_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("100.00"))
    accuracy_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("100.00"))
    consistency_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("100.00"))
    timeliness_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("100.00"))
    uniqueness_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("100.00"))
    validity_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("100.00"))

    grade = models.CharField(max_length=5, choices=GRADE_CHOICES, default="A")
    health_status = models.CharField(max_length=20, choices=HEALTH_STATUS_CHOICES, default="healthy")

    target_quality_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("95.00"),
        help_text="Corporate SLA threshold target",
    )
    meets_sla = models.BooleanField(default=True)

    total_rules_evaluated = models.PositiveIntegerField(default=0)
    rules_passed_count = models.PositiveIntegerField(default=0)
    rules_failed_count = models.PositiveIntegerField(default=0)
    open_exceptions_count = models.PositiveIntegerField(default=0)
    critical_exceptions_count = models.PositiveIntegerField(default=0)

    evaluation_period = models.CharField(max_length=20, choices=EVALUATION_PERIOD_CHOICES, default="ad_hoc")
    last_calculated_at = models.DateTimeField(null=True, blank=True)

    steward = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stewarded_scorecards",
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "bi_data_quality_scorecard"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="bi_bdqs_tenant_code_uniq"),
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bdqs_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "scope_type"], name="idx_bdqs_ten_stype"),
            models.Index(fields=["tenant", "grade"], name="idx_bdqs_ten_grade"),
            models.Index(fields=["tenant", "health_status"], name="idx_bdqs_ten_hstat"),
            models.Index(fields=["tenant", "is_active"], name="idx_bdqs_ten_active"),
            models.Index(fields=["tenant", "-created_at"], name="idx_bdqs_ten_created"),
        ]

    def __str__(self):
        return f"{self.name} ({self.number}) — Grade {self.grade} ({self.overall_quality_score}%)"

    def get_absolute_url(self):
        return reverse("bi:data_quality_scorecard_detail", kwargs={"pk": self.pk})
