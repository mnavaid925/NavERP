"""Projects 7.19 — ProjectTemplate model [PTM-].

Reusable project blueprint and methodology framework (Waterfall, Agile, Hybrid) with
pre-built WBS hierarchy JSON, default roles, workflow stages, and budget/duration baselines.
"""
from decimal import Decimal

from apps.projects.models._base import *


class ProjectTemplate(TenantNumbered):
    """Reusable project template and methodology framework."""

    NUMBER_PREFIX = "PTM"

    METHODOLOGY_CHOICES = [
        ("waterfall", "Waterfall (Predictive)"),
        ("agile", "Agile (Scrum / Iterative)"),
        ("hybrid", "Hybrid (Stage-Gate + Agile)"),
    ]

    CATEGORY_CHOICES = [
        ("software", "Software & IT"),
        ("infrastructure", "Infrastructure & Cloud"),
        ("consulting", "Professional Services / Consulting"),
        ("r_and_d", "R&D / Innovation"),
        ("marketing", "Marketing / Creative"),
        ("operational", "Operational / Internal"),
        ("internal", "Internal Governance"),
    ]

    COMPLEXITY_CHOICES = [
        ("small", "Small / Quick-Turn"),
        ("medium", "Medium Standard"),
        ("large", "Large Multi-Phase"),
        ("enterprise", "Enterprise Strategic"),
    ]

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, blank=True)
    methodology = models.CharField(
        max_length=20,
        choices=METHODOLOGY_CHOICES,
        default="hybrid",
        help_text="Project execution and governance methodology.",
    )
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default="software",
        help_text="Industry or operational domain category.",
    )
    complexity = models.CharField(
        max_length=20,
        choices=COMPLEXITY_CHOICES,
        default="medium",
        help_text="Project scale and governance rigor tier.",
    )
    description = models.TextField(blank=True, help_text="Scope and PM guidelines for this blueprint.")
    estimated_duration_days = models.PositiveIntegerField(
        default=30,
        help_text="Estimated baseline delivery duration in business days.",
    )
    target_budget = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Indicative baseline budget estimate.",
    )
    default_roles = models.JSONField(
        default=list,
        blank=True,
        help_text="List of recommended standard team roles for this template.",
    )
    wbs_structure = models.JSONField(
        default=list,
        blank=True,
        help_text="Pre-built WBS phases, tasks, and milestone deliverables structure.",
    )
    workflow_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Pre-configured lifecycle stage gates and transition approvals.",
    )
    is_active = models.BooleanField(default=True, help_text="Available for project instantiation.")
    is_default = models.BooleanField(
        default=False,
        help_text="Tenant default template for this methodology.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["tenant", "methodology"], name="ptm_tnt_meth_idx"),
            models.Index(fields=["tenant", "is_active"], name="ptm_tnt_active_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name}"

    def clean(self):
        super().clean()
        if self.is_default and self.tenant_id:
            # Enforce single default per methodology per tenant
            qs = ProjectTemplate.objects.filter(
                tenant=self.tenant,
                methodology=self.methodology,
                is_default=True,
            )
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError(
                    {"is_default": f"A default template for {self.get_methodology_display()} already exists."}
                )

    def save(self, *args, **kwargs):
        self.target_budget = q2(self.target_budget)
        super().save(*args, **kwargs)

    @property
    def methodology_badge_class(self):
        mapping = {
            "waterfall": "badge-info",
            "agile": "badge-green",
            "hybrid": "badge-purple" if False else "badge-info",  # theme.css safe: badge-info, badge-green, badge-amber
        }
        return mapping.get(self.methodology, "badge-slate")

    @property
    def complexity_badge_class(self):
        mapping = {
            "small": "badge-green",
            "medium": "badge-info",
            "large": "badge-amber",
            "enterprise": "badge-red",
        }
        return mapping.get(self.complexity, "badge-slate")
