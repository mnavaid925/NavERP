from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.sales.models._base import TenantNumbered
from apps.sales.models.CompetitiveIntelligence.CompetitiveIntelligence import OpportunityCompetitor


class WinLossReason(TenantNumbered):
    NUMBER_PREFIX = "WLR"
    RESULT_CHOICES = [
        ("won", "Won"),
        ("lost", "Lost"),
        ("both", "Both"),
    ]
    CATEGORY_CHOICES = [
        ("price", "Price"),
        ("product_fit", "Product Fit"),
        ("timing", "Timing"),
        ("competition", "Competition"),
        ("relationship", "Relationship"),
        ("authority", "Authority"),
        ("budget", "Budget"),
        ("no_decision", "No Decision"),
        ("other", "Other"),
    ]

    code = models.SlugField(max_length=40)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    sequence = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    result = models.CharField(max_length=10, choices=RESULT_CHOICES)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sequence", "name", "id"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="sales_wlr_tenant_number_uniq"),
            models.UniqueConstraint(fields=["tenant", "code"], name="sales_wlr_tenant_code_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "result", "is_active"], name="sales_wlr_result_active_idx"),
            models.Index(fields=["tenant", "category", "is_active"], name="sales_wlr_category_active_idx"),
        ]

    def clean(self):
        self.code = (self.code or "").strip().lower()
        super().clean()

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().lower()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.pk and OpportunityOutcome.objects.filter(reason_id=self.pk, tenant_id=self.tenant_id).exists():
            raise ValidationError("A referenced win/loss reason cannot be deleted.")
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.number or '—'} · {self.name}"


class OpportunityOutcome(TenantNumbered):
    NUMBER_PREFIX = "OUT"
    RESULT_CHOICES = [
        ("won", "Won"),
        ("lost", "Lost"),
    ]

    opportunity = models.ForeignKey(
        "crm.Opportunity",
        on_delete=models.CASCADE,
        related_name="sales_outcomes",
    )
    result = models.CharField(max_length=10, choices=RESULT_CHOICES)
    reason = models.ForeignKey("sales.WinLossReason", on_delete=models.PROTECT)
    competitor_link = models.ForeignKey(
        "sales.OpportunityCompetitor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    notes = models.TextField(blank=True)
    closed_at = models.DateTimeField(default=timezone.now, editable=False)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
    )

    class Meta:
        ordering = ["-closed_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="sales_out_tenant_number_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "result", "closed_at"], name="sales_out_result_closed_idx"),
            models.Index(fields=["tenant", "opportunity", "closed_at"], name="sales_out_opp_closed_idx"),
            models.Index(fields=["tenant", "reason"], name="sales_out_reason_idx"),
        ]

    def _relation_belongs_to_tenant(self, field_name):
        relation_id = getattr(self, f"{field_name}_id", None)
        if not self.tenant_id or not relation_id:
            return True
        field = self._meta.get_field(field_name)
        related_model = field.remote_field.model
        return related_model._default_manager.filter(
            pk=relation_id,
            tenant_id=self.tenant_id,
        ).exists()

    def clean(self):
        super().clean()
        if not self.tenant_id:
            return
        for field_name, message in (
            ("opportunity", "The opportunity must belong to this workspace."),
            ("reason", "Choose a reason from this workspace."),
            ("competitor_link", "Choose a competitor link from this workspace."),
            ("recorded_by", "The recorder must belong to this workspace."),
        ):
            if not self._relation_belongs_to_tenant(field_name):
                raise ValidationError({field_name: message})
        reason = self.reason if self.reason_id else None
        if reason is not None and self.result in dict(self.RESULT_CHOICES):
            if reason.result not in {"both", self.result}:
                raise ValidationError({"reason": "The reason is not compatible with this outcome."})
        competitor_link = self.competitor_link if self.competitor_link_id else None
        if competitor_link is not None:
            if self.opportunity_id and competitor_link.opportunity_id != self.opportunity_id:
                raise ValidationError({"competitor_link": "The competitor link must belong to the opportunity."})
            if competitor_link.relationship in {"lost_to", "beaten"} and self.result != "lost":
                raise ValidationError({"competitor_link": "This competitor relationship requires a lost outcome."})

    def __str__(self):
        try:
            opportunity = self.opportunity if self.opportunity_id else None
        except ObjectDoesNotExist:
            opportunity = None
        return f"{self.number or '—'} · {opportunity or '—'} · {self.get_result_display()}"
