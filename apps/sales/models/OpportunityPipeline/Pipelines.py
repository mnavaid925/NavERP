from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.sales.models._base import TenantNumbered, TenantOwned


PIPELINE_CRITERION_CHOICES = [
    ("account", "Account is linked"),
    ("primary_contact", "Primary contact is linked"),
    ("amount", "Amount is greater than zero"),
    ("close_date", "Close date is set"),
    ("next_step", "Next step is defined"),
    ("next_step_due_date", "Next-step due date is set"),
    ("owner", "Owner is assigned"),
    ("active_team_member", "Active team member is assigned"),
]


def _validate_pipeline_criteria(value):
    if not isinstance(value, list):
        raise ValidationError("Criteria must be a list.")
    if len(value) > 20:
        raise ValidationError("A stage may contain at most 20 criteria.")
    labels = dict(PIPELINE_CRITERION_CHOICES)
    normalized = []
    seen = set()
    for item in value:
        if not isinstance(item, dict) or set(item) != {"key", "label"}:
            raise ValidationError("Each criterion must contain only key and label.")
        key = item["key"]
        label = item["label"]
        if key not in labels:
            raise ValidationError("Choose a supported stage criterion.")
        if not isinstance(label, str) or not 1 <= len(label.strip()) <= 120:
            raise ValidationError("Criterion labels must be 1 to 120 characters.")
        if key in seen:
            raise ValidationError("Stage criteria must be unique.")
        seen.add(key)
        normalized.append({"key": key, "label": label.strip()})
    return normalized


class Pipeline(TenantNumbered):
    NUMBER_PREFIX = "PIPE"

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-is_default", "name", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="sales_pipe_tenant_number_uniq"),
            models.UniqueConstraint(
                fields=["tenant"],
                condition=Q(is_active=True, is_default=True),
                name="sales_pipe_active_default_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="sales_pipe_tenant_active_idx"),
            models.Index(fields=["tenant", "is_default"], name="sales_pipe_tenant_default_idx"),
        ]

    def clean(self):
        super().clean()
        if self.is_default and not self.is_active:
            raise ValidationError({"is_default": "The default pipeline must be active."})
        if self.pk and not self.is_active:
            has_open_placements = self.placements.filter(
                current_stage__stage_kind="open"
            ).exists()
            if has_open_placements:
                raise ValidationError(
                    {"is_active": "A pipeline with open placements cannot be deactivated."}
                )
        if self.pk and self.is_active and self.is_default:
            duplicate = Pipeline.objects.filter(
                tenant=self.tenant,
                is_active=True,
                is_default=True,
            ).exclude(pk=self.pk)
            if duplicate.exists():
                raise ValidationError({"is_default": "Only one active default pipeline is allowed."})

    def save(self, *args, **kwargs):
        if self.pk and not self.is_active and self.placements.filter(
            current_stage__stage_kind="open"
        ).exists():
            raise ValidationError(
                {"is_active": "A pipeline with open placements cannot be deactivated."}
            )
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.placements.exists():
            raise ValidationError("A pipeline with placements cannot be deleted.")
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.number} · {self.name}"


class PipelineStage(TenantOwned):
    STAGE_KIND_CHOICES = [("open", "Open"), ("won", "Won"), ("lost", "Lost")]
    CRM_STAGE_KEY_CHOICES = [
        ("prospecting", "Prospecting"),
        ("qualification", "Qualification"),
        ("proposal", "Proposal"),
        ("negotiation", "Negotiation"),
        ("closed_won", "Closed Won"),
        ("closed_lost", "Closed Lost"),
    ]
    FORECAST_CATEGORY_CHOICES = [
        ("omitted", "Omitted"),
        ("pipeline", "Pipeline"),
        ("best_case", "Best Case"),
        ("commit", "Commit"),
        ("closed", "Closed"),
    ]

    pipeline = models.ForeignKey(
        "sales.Pipeline",
        on_delete=models.CASCADE,
        related_name="stages",
    )
    name = models.CharField(max_length=120)
    code = models.SlugField(max_length=40)
    sequence = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    stage_kind = models.CharField(max_length=10, choices=STAGE_KIND_CHOICES, default="open")
    crm_stage_key = models.CharField(max_length=20, choices=CRM_STAGE_KEY_CHOICES)
    probability = models.PositiveSmallIntegerField(
        default=10,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    forecast_category = models.CharField(
        max_length=12,
        choices=FORECAST_CATEGORY_CHOICES,
        default="pipeline",
    )
    entry_guidance = models.TextField(blank=True)
    exit_guidance = models.TextField(blank=True)
    entry_criteria = models.JSONField(default=list, blank=True)
    exit_criteria = models.JSONField(default=list, blank=True)
    target_days = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(3650)],
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["pipeline", "sequence", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "pipeline", "code"],
                name="sales_pstage_tp_code_uniq",
            ),
            models.UniqueConstraint(
                fields=["tenant", "pipeline", "sequence"],
                name="sales_pstage_tp_sequence_uniq",
            ),
            models.CheckConstraint(
                condition=Q(sequence__gte=1),
                name="sales_pstage_sequence_valid",
            ),
            models.CheckConstraint(
                condition=Q(probability__gte=0, probability__lte=100),
                name="sales_pstage_probability_valid",
            ),
            models.CheckConstraint(
                condition=Q(target_days__isnull=True) | Q(target_days__gte=1, target_days__lte=3650),
                name="sales_pstage_target_days_valid",
            ),
            models.CheckConstraint(
                condition=Q(stage_kind__in=("open", "won", "lost")),
                name="sales_pstage_kind_valid",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(stage_kind="open")
                    | Q(
                        stage_kind="open",
                        crm_stage_key__in=("prospecting", "qualification", "proposal", "negotiation"),
                        probability__gte=1,
                        probability__lte=99,
                    )
                ),
                name="sales_pstage_open_integrity",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(stage_kind="won")
                    | Q(
                        stage_kind="won",
                        crm_stage_key="closed_won",
                        probability=100,
                        forecast_category="closed",
                    )
                ),
                name="sales_pstage_won_integrity",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(stage_kind="lost")
                    | Q(
                        stage_kind="lost",
                        crm_stage_key="closed_lost",
                        probability=0,
                        forecast_category="closed",
                    )
                ),
                name="sales_pstage_lost_integrity",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "pipeline", "sequence"], name="sales_pstage_tp_sequence_idx"),
            models.Index(fields=["tenant", "stage_kind", "is_active"], name="sales_pstage_tenant_kind_idx"),
        ]

    def _referenced_locked_field(self):
        if not self.pk or not self.current_placements.exists():
            return None
        previous = (
            PipelineStage.objects.filter(pk=self.pk)
            .values("stage_kind", "crm_stage_key", "probability", "forecast_category", "is_active")
            .first()
        )
        if previous is None:
            return None
        locked_fields = ("stage_kind", "crm_stage_key", "probability", "forecast_category", "is_active")
        for field_name in locked_fields:
            if getattr(self, field_name) != previous[field_name]:
                return field_name
        return None

    def clean(self):
        super().clean()
        if self.pipeline_id and self.pipeline.tenant_id != self.tenant_id:
            raise ValidationError({"pipeline": "Choose a pipeline from this workspace."})
        self.entry_criteria = _validate_pipeline_criteria(self.entry_criteria)
        self.exit_criteria = _validate_pipeline_criteria(self.exit_criteria)
        if self.stage_kind == "open":
            valid = (
                self.crm_stage_key in {"prospecting", "qualification", "proposal", "negotiation"}
                and self.probability is not None
                and 1 <= self.probability <= 99
            )
            if not valid:
                raise ValidationError("Open stages require an open CRM stage and probability from 1 to 99.")
        elif self.stage_kind == "won":
            if (self.crm_stage_key, self.probability, self.forecast_category) != (
                "closed_won",
                100,
                "closed",
            ):
                raise ValidationError("Won stages require Closed Won, 100%, and Closed category.")
        elif self.stage_kind == "lost":
            if (self.crm_stage_key, self.probability, self.forecast_category) != (
                "closed_lost",
                0,
                "closed",
            ):
                raise ValidationError("Lost stages require Closed Lost, 0%, and Closed category.")
        locked_field = self._referenced_locked_field()
        if locked_field:
            raise ValidationError(
                {locked_field: "A stage used by a placement has locked configuration fields."}
            )

    def save(self, *args, **kwargs):
        locked_field = self._referenced_locked_field()
        if locked_field:
            raise ValidationError(
                {locked_field: "A stage used by a placement has locked configuration fields."}
            )
        self.code = self.code.lower()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.current_placements.exists():
            raise ValidationError("A stage used by a placement cannot be deleted.")
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.pipeline} · {self.name}"


class OpportunityPipelinePlacement(TenantOwned):
    opportunity = models.OneToOneField(
        "crm.Opportunity",
        on_delete=models.CASCADE,
        related_name="sales_pipeline_placement",
    )
    pipeline = models.ForeignKey(
        "sales.Pipeline",
        on_delete=models.PROTECT,
        related_name="placements",
    )
    current_stage = models.ForeignKey(
        "sales.PipelineStage",
        on_delete=models.PROTECT,
        related_name="current_placements",
    )
    probability_override = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    stage_entered_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["-updated_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(probability_override__isnull=True)
                    | Q(probability_override__gte=0, probability_override__lte=100)
                ),
                name="sales_opp_place_override_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "opportunity"], name="sales_opp_place_tenant_opp_idx"),
            models.Index(fields=["tenant", "pipeline"], name="sales_opp_place_tenant_pipe_idx"),
        ]

    def clean(self):
        super().clean()
        if self.opportunity_id and self.opportunity.tenant_id != self.tenant_id:
            raise ValidationError({"opportunity": "Choose an opportunity from this workspace."})
        if self.pipeline_id and self.pipeline.tenant_id != self.tenant_id:
            raise ValidationError({"pipeline": "Choose a pipeline from this workspace."})
        if self.current_stage_id:
            stage = self.current_stage
            if stage.tenant_id != self.tenant_id:
                raise ValidationError({"current_stage": "Choose a stage from this workspace."})
            if stage.pipeline_id != self.pipeline_id:
                raise ValidationError({"current_stage": "Choose a stage from the selected pipeline."})
            if not stage.is_active:
                raise ValidationError({"current_stage": "Choose an active stage."})
        if self.probability_override is not None:
            if not 0 <= self.probability_override <= 100:
                raise ValidationError({"probability_override": "Probability must be between 0 and 100."})
            if self.current_stage.stage_kind == "won" and self.probability_override != 100:
                raise ValidationError({"probability_override": "Won placements require 100%."})
            if self.current_stage.stage_kind == "lost" and self.probability_override != 0:
                raise ValidationError({"probability_override": "Lost placements require 0%."})

    @property
    def effective_probability(self):
        if self.probability_override is not None:
            return self.probability_override
        return self.current_stage.probability

    def __str__(self):
        return f"{self.opportunity} · {self.current_stage}"
