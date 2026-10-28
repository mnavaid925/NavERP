"""SalesMethodology model for 8.19 Master Data & Configuration — Sales Methodology Configuration."""
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.sales.models._base import TenantNumbered


class SalesMethodology(TenantNumbered):
    """Framework templates and stage gating criteria for commercial sales methodologies."""

    NUMBER_PREFIX = "SMD"

    FRAMEWORK_CHOICES = [
        ("meddic", "MEDDIC (Metrics, Econ Buyer, Criteria, Process, Pain, Champ)"),
        ("meddpicc", "MEDDPICC (+ Paper Process & Competition)"),
        ("bant", "BANT (Budget, Authority, Need, Timeline)"),
        ("spin", "SPIN (Situation, Problem, Implication, Need-Payoff)"),
        ("challenger", "The Challenger Sale (Teach, Tailor, Take Control)"),
        ("command_message", "Command of the Message / Value Selling"),
        ("sandler", "Sandler Selling System (Pain, Budget, Decision)"),
        ("custom", "Custom Commercial Methodology"),
    ]

    name = models.CharField(
        max_length=150,
        help_text="Methodology label, e.g. 'Enterprise MEDDPICC Stage Gate'",
    )
    framework = models.CharField(
        max_length=30,
        choices=FRAMEWORK_CHOICES,
        default="meddic",
        help_text="Standard industry sales methodology framework",
    )
    pipeline = models.ForeignKey(
        "sales.Pipeline",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_methodologies",
        help_text="Optional pipeline bound to this methodology",
    )
    gating_stage = models.ForeignKey(
        "sales.PipelineStage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gated_methodologies",
        help_text="Pipeline stage requiring qualification score before advancing",
    )
    min_passing_score = models.PositiveIntegerField(
        default=70,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Minimum score percentage required to pass qualification gate",
    )
    is_mandatory_gate = models.BooleanField(
        default=False,
        help_text="When True, enforces qualification score verification before stage promotion",
    )
    qualification_criteria = models.JSONField(
        default=list,
        blank=True,
        help_text="Checklist criteria formatted as [{'key': 'metrics', 'label': 'Economic Impact Measured', 'weight': 20, 'is_required': True}]",
    )
    coaching_guidelines = models.TextField(
        blank=True,
        default="",
        help_text="Tactical guidance, questions to ask, and coaching tips for sales reps",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this methodology template is active",
    )

    class Meta:
        ordering = ["framework", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="sales_smd_tenant_num_uniq",
            ),
            models.UniqueConstraint(
                fields=["tenant", "name"],
                name="sales_smd_tnt_name_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "framework", "is_active"], name="sales_smd_frw_act_idx"),
            models.Index(fields=["tenant", "pipeline", "is_active"], name="sales_smd_pipe_act_idx"),
        ]

    def clean(self):
        super().clean()
        if self.tenant_id:
            if self.pipeline_id and self.pipeline.tenant_id != self.tenant_id:
                raise ValidationError({"pipeline": "Pipeline must belong to the active workspace."})
            if self.gating_stage_id and self.gating_stage.tenant_id != self.tenant_id:
                raise ValidationError({"gating_stage": "Gating stage must belong to the active workspace."})
        if self.gating_stage_id and self.pipeline_id and self.gating_stage.pipeline_id != self.pipeline_id:
            raise ValidationError({"gating_stage": "Gating stage must belong to the selected pipeline."})
        if not isinstance(self.qualification_criteria, list):
            raise ValidationError({"qualification_criteria": "Qualification criteria must be a JSON array."})

    def __str__(self):
        return f"{self.number} · {self.name} ({self.get_framework_display()})"
