from decimal import Decimal

from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class CalculatedMeasure(TenantNumbered):
    NUMBER_PREFIX = "BCMS"

    AGGREGATION_TYPE_CHOICES = [
        ("sum", "Sum"),
        ("avg", "Average"),
        ("count", "Count"),
        ("count_distinct", "Count Distinct"),
        ("min", "Minimum"),
        ("max", "Maximum"),
        ("formula", "Custom Calculated Expression / Ratio"),
    ]

    TIME_INTELLIGENCE_CHOICES = [
        ("none", "None (Standard Aggregation)"),
        ("yoy_growth", "Year-over-Year (YoY) Growth %"),
        ("qtd", "Quarter-to-Date (QTD)"),
        ("ytd", "Year-to-Date (YTD)"),
        ("rolling_30d", "Rolling 30-Day Moving Sum/Avg"),
        ("prior_period", "Prior Period Difference"),
    ]

    FORMAT_STRING_CHOICES = [
        ("currency", "Currency ($#,##0.00)"),
        ("percentage", "Percentage (0.00%)"),
        ("integer", "Whole Number (#,##0)"),
        ("decimal", "Decimal Number (#,##0.00)"),
        ("raw", "Raw Unformatted"),
    ]

    DISPLAY_UNITS_CHOICES = [
        ("auto", "Auto-Scale (K/M/B)"),
        ("none", "None (Raw Value)"),
        ("thousands", "Thousands (K)"),
        ("millions", "Millions (M)"),
        ("billions", "Billions (B)"),
    ]

    semantic_model = models.ForeignKey(
        "bi.SemanticModel",
        on_delete=models.CASCADE,
        related_name="measures",
        help_text="Parent semantic model to which this measure applies",
    )
    glossary_term = models.ForeignKey(
        "bi.BusinessGlossaryTerm",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="measures",
        help_text="Associated enterprise glossary term definition",
    )

    name = models.CharField(max_length=150, help_text="Human-friendly measure name")
    code = models.SlugField(max_length=50, help_text="Unique measure identifier slug")

    aggregation_type = models.CharField(
        max_length=25,
        choices=AGGREGATION_TYPE_CHOICES,
        default="sum",
    )
    source_column = models.CharField(
        max_length=100,
        blank=True,
        help_text="Physical/logical column name for standard aggregations",
    )
    formula_expression = models.CharField(
        max_length=500,
        blank=True,
        help_text="Calculation formula expression, e.g. [revenue] - [cost] or ([gp] / [rev]) * 100",
    )
    filter_expression = models.CharField(
        max_length=500,
        blank=True,
        help_text="SQL WHERE clause filter condition, e.g. status = 'posted'",
    )

    time_intelligence = models.CharField(
        max_length=25,
        choices=TIME_INTELLIGENCE_CHOICES,
        default="none",
    )
    format_string = models.CharField(
        max_length=25,
        choices=FORMAT_STRING_CHOICES,
        default="decimal",
    )
    display_units = models.CharField(
        max_length=20,
        choices=DISPLAY_UNITS_CHOICES,
        default="auto",
    )

    target_value = models.DecimalField(
        max_digits=16,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Benchmark target value",
    )
    warning_threshold = models.DecimalField(
        max_digits=16,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Warning alert threshold value",
    )
    critical_threshold = models.DecimalField(
        max_digits=16,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Critical alert threshold value",
    )

    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "bi_calculated_measure"
        ordering = ["semantic_model", "name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "semantic_model", "code"], name="bi_bcms_tenant_model_code_uniq"),
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bcms_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "aggregation_type"], name="idx_bcms_ten_agg"),
            models.Index(fields=["tenant", "time_intelligence"], name="idx_bcms_ten_ti"),
            models.Index(fields=["tenant", "is_active"], name="idx_bcms_ten_active"),
        ]

    def __str__(self):
        return f"{self.name} ({self.number})"

    def get_absolute_url(self):
        return reverse("bi:calculated_measure_detail", kwargs={"pk": self.pk})
