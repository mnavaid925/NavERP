from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from apps.bi.models._base import TenantNumbered


class KpiDefinition(TenantNumbered):
    NUMBER_PREFIX = "BKPI"

    PERSPECTIVE_CHOICES = [
        ("financial", "Financial"),
        ("customer", "Customer"),
        ("internal_process", "Internal Business Process"),
        ("learning_growth", "Learning & Growth"),
    ]

    DIRECTION_CHOICES = [
        ("maximize", "Maximize (Higher is Better)"),
        ("minimize", "Minimize (Lower is Better)"),
        ("in_range", "In Range (Target Band)"),
    ]

    UOM_CHOICES = [
        ("percentage", "Percentage (%)"),
        ("currency", "Currency Amount ($)"),
        ("count", "Integer Count (#)"),
        ("days", "Days / Duration"),
        ("hours", "Hours / Time"),
        ("ratio", "Ratio / Decimal"),
        ("score", "Index / Score (0-100)"),
    ]

    FREQUENCY_CHOICES = [
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("annual", "Annual"),
    ]

    CALC_TYPE_CHOICES = [
        ("manual", "Manual Entry / Qualitative"),
        ("semantic_measure", "Governed Semantic Measure (10.4)"),
        ("formula_expression", "Calculated Formula Expression"),
        ("aggregation", "Database Aggregate"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft Setup"),
        ("active", "Active / In Production"),
        ("under_review", "Under Review"),
        ("deprecated", "Deprecated"),
        ("archived", "Archived"),
    ]

    code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=60, default="operations")
    perspective = models.CharField(max_length=30, choices=PERSPECTIVE_CHOICES, default="internal_process")
    target_direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES, default="maximize")
    unit_of_measure = models.CharField(max_length=20, choices=UOM_CHOICES, default="percentage")
    tracking_frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default="monthly")
    calculation_type = models.CharField(max_length=30, choices=CALC_TYPE_CHOICES, default="manual")
    semantic_measure = models.ForeignKey(
        "bi.CalculatedMeasure",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="kpi_definitions",
    )
    formula_expression = models.CharField(max_length=500, blank=True)
    target_value = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0.0000"))
    warning_threshold = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    critical_threshold = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    current_value = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0.0000"))
    previous_value = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    industry_benchmark_value = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    benchmark_source = models.CharField(max_length=150, blank=True)
    benchmark_percentile = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    is_active = models.BooleanField(default=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_kpis",
    )
    department = models.ForeignKey(
        "core.OrgUnit",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="kpi_definitions",
    )
    last_calculated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["perspective", "name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "slug"], name="bi_bkpi_tenant_slug_uniq"),
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bkpi_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "code"], name="idx_bkpi_ten_code"),
            models.Index(fields=["tenant", "perspective"], name="idx_bkpi_ten_persp"),
            models.Index(fields=["tenant", "status"], name="idx_bkpi_ten_stat"),
            models.Index(fields=["tenant", "owner"], name="idx_bkpi_ten_owner"),
        ]

    def __str__(self):
        return f"{self.number} - {self.name} ({self.code})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:120]
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("bi:kpi_definition_detail", kwargs={"pk": self.pk})

    @property
    def variance(self):
        if self.target_value is not None and self.current_value is not None:
            return self.current_value - self.target_value
        return Decimal("0.0000")

    @property
    def variance_percentage(self):
        if self.target_value and self.target_value != Decimal("0.0000"):
            return ((self.current_value - self.target_value) / abs(self.target_value)) * Decimal("100.00")
        return Decimal("0.00")

    @property
    def benchmark_gap(self):
        if self.industry_benchmark_value is not None and self.current_value is not None:
            return self.current_value - self.industry_benchmark_value
        return None

    def calculate_rag_status(self):
        """Evaluate RAG traffic-light health status."""
        if not self.is_active or self.status in ["deprecated", "archived"]:
            return "gray"
        if self.current_value is None or self.target_value is None:
            return "gray"

        cur = self.current_value
        tgt = self.target_value
        warn = self.warning_threshold
        crit = self.critical_threshold

        if self.target_direction == "maximize":
            if cur >= tgt:
                return "green"
            if warn is not None and cur >= warn:
                return "amber"
            if crit is not None and cur < crit:
                return "red"
            return "amber" if warn is not None else "red"
        elif self.target_direction == "minimize":
            if cur <= tgt:
                return "green"
            if warn is not None and cur <= warn:
                return "amber"
            if crit is not None and cur > crit:
                return "red"
            return "amber" if warn is not None else "red"
        else:  # in_range
            lower = warn if warn is not None else tgt * Decimal("0.9")
            upper = crit if crit is not None else tgt * Decimal("1.1")
            if lower <= cur <= upper:
                return "green"
            return "amber"

    def record_measurement(self, new_value, save=True):
        """Update current value, shifting current to previous value."""
        self.previous_value = self.current_value
        self.current_value = Decimal(str(new_value))
        self.last_calculated_at = timezone.now()
        if save:
            self.save(update_fields=["previous_value", "current_value", "last_calculated_at", "updated_at"])
        return self

