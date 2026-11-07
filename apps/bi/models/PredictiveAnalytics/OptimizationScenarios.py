from decimal import Decimal
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from apps.bi.models._base import TenantNumbered


class OptimizationScenario(TenantNumbered):
    NUMBER_PREFIX = "BOPT"

    OBJECTIVE_CHOICES = [
        ("maximize", "Maximize Objective"),
        ("minimize", "Minimize Cost / Risk"),
        ("target_value", "Reach Specific Target Value"),
    ]

    ALGORITHM_CHOICES = [
        ("linear_programming", "Linear Programming (Simplex)"),
        ("goal_programming", "Goal Programming / Multi-Objective"),
        ("heuristic", "Greedy Heuristic / Hill Climbing"),
    ]

    SOLVER_STATUS_CHOICES = [
        ("draft", "Draft Setup"),
        ("optimal", "Optimal Solution Found"),
        ("feasible", "Feasible (Sub-Optimal)"),
        ("infeasible", "Infeasible (Constraints Conflict)"),
        ("unbounded", "Unbounded"),
    ]

    STATUS_CHOICES = [
        ("active", "Active Scenario"),
        ("draft", "Draft Exploration"),
        ("applied", "Applied / Implemented"),
        ("archived", "Archived"),
    ]

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120)
    description = models.TextField(blank=True)
    objective_type = models.CharField(
        max_length=20,
        choices=OBJECTIVE_CHOICES,
        default="maximize",
    )
    target_metric_name = models.CharField(
        max_length=120,
        help_text="Metric/KPI being optimized",
    )
    kpi_definition = models.ForeignKey(
        "bi.KpiDefinition",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="optimization_scenarios",
    )
    baseline_value = models.DecimalField(
        max_digits=16,
        decimal_places=4,
        default=0.00,
    )
    target_value = models.DecimalField(
        max_digits=16,
        decimal_places=4,
        null=True,
        blank=True,
    )
    optimal_value = models.DecimalField(
        max_digits=16,
        decimal_places=4,
        null=True,
        blank=True,
    )
    projected_lift_percentage = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0.00,
    )
    solver_algorithm = models.CharField(
        max_length=30,
        choices=ALGORITHM_CHOICES,
        default="linear_programming",
    )
    solver_status = models.CharField(
        max_length=20,
        choices=SOLVER_STATUS_CHOICES,
        default="draft",
    )
    decision_variables = models.JSONField(
        default=list,
        help_text="List of controllable levers, min/max bounds, step size",
    )
    constraint_rules = models.JSONField(
        default=list,
        help_text="Operational boundary equations",
    )
    recommended_actions = models.JSONField(
        default=list,
        help_text="Prescriptive next-best-actions with expected delta",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_optimization_scenarios",
    )

    class Meta:
        db_table = "bi_optimization_scenario"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "slug"], name="bi_bopt_tenant_slug_uniq"),
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bopt_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "solver_status"], name="idx_bopt_ten_solv"),
            models.Index(fields=["tenant", "status"], name="idx_bopt_ten_stat"),
            models.Index(fields=["tenant", "owner"], name="idx_bopt_ten_user"),
        ]

    def __str__(self):
        return f"{self.name} ({self.number})"

    def get_absolute_url(self):
        return reverse("bi:optimization_scenario_detail", kwargs={"pk": self.pk})

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or "scenario"
            self.slug = base_slug[:120]
        super().save(*args, **kwargs)

    def solve_scenario(self):
        """Simulates solver computation and generates prescriptive next-best-actions."""
        base = float(self.baseline_value) if self.baseline_value else 100000.0
        if self.objective_type == "maximize":
            opt = base * 1.15
            lift = 15.00
        elif self.objective_type == "minimize":
            opt = base * 0.88
            lift = -12.00
        else:
            opt = float(self.target_value) if self.target_value else base * 1.10
            lift = ((opt - base) / base * 100) if base != 0 else 0.0

        self.optimal_value = Decimal(str(round(opt, 4)))
        self.projected_lift_percentage = Decimal(str(round(lift, 2)))
        self.solver_status = "optimal"

        actions = [
            {
                "rank": 1,
                "action": "Reallocate discretionary marketing spend +12% toward high-converting digital channels",
                "expected_delta": "+$18,400",
                "confidence": "High",
            },
            {
                "rank": 2,
                "action": "Consolidate regional freight shipments to reduce LTL carrier surcharges by 8%",
                "expected_delta": "-$11,200 cost",
                "confidence": "High",
            },
            {
                "rank": 3,
                "action": "Adjust inventory reorder point for Tier-1 items from 14 to 10 days lead time",
                "expected_delta": "+$7,800 working capital freed",
                "confidence": "Medium",
            },
        ]
        self.recommended_actions = actions
        self.save(update_fields=["optimal_value", "projected_lift_percentage", "solver_status", "recommended_actions", "updated_at"])
