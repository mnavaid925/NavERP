"""CRM 1.2 Sales Force Automation — Opportunities models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


class Opportunity(TenantNumbered):
    """A sales deal (1.2) on the pipeline. Account/contact reuse ``core.Party``."""

    NUMBER_PREFIX = "OPP"

    STAGE_CHOICES = [
        ("prospecting", "Prospecting"),
        ("qualification", "Qualification"),
        ("proposal", "Proposal"),
        ("negotiation", "Negotiation"),
        ("closed_won", "Closed Won"),
        ("closed_lost", "Closed Lost"),
    ]
    OPEN_STAGES = ["prospecting", "qualification", "proposal", "negotiation"]
    # Forecast rollup buckets (Salesforce/Zoho/Clari) — drive the 1.2 forecast dashboard.
    FORECAST_CATEGORY_CHOICES = [
        ("omitted", "Omitted"),
        ("pipeline", "Pipeline"),
        ("best_case", "Best Case"),
        ("commit", "Commit"),
        ("closed", "Closed"),
    ]

    name = models.CharField(max_length=255)
    account = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_opportunities")
    primary_contact = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_contact_opportunities")
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default="prospecting")
    forecast_category = models.CharField(max_length=12, choices=FORECAST_CATEGORY_CHOICES, default="pipeline")
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    probability = models.PositiveSmallIntegerField(default=10, validators=[MaxValueValidator(100)])
    close_date = models.DateField(null=True, blank=True)
    competitor = models.CharField(max_length=255, blank=True)
    loss_reason = models.CharField(max_length=255, blank=True)  # filled when closed_lost
    lost_at = models.DateTimeField(null=True, blank=True)  # system-set when stage→closed_lost
    stage_changed_at = models.DateTimeField(null=True, blank=True)  # system-set on stage change (days-in-stage)
    territory = models.ForeignKey("crm.Territory", on_delete=models.SET_NULL, null=True, blank=True, related_name="opportunities")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_opportunities")
    source_lead = models.ForeignKey("crm.Lead", on_delete=models.SET_NULL, null=True, blank=True, related_name="opportunities")
    campaign = models.ForeignKey("crm.Campaign", on_delete=models.SET_NULL, null=True, blank=True, related_name="opportunities")
    next_step = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "stage"], name="crm_opp_tenant_stage_idx"),
            models.Index(fields=["tenant", "created_at"], name="crm_opp_tenant_created_idx"),
            models.Index(fields=["tenant", "forecast_category"], name="crm_opp_tnt_fcast_idx"),
        ]

    @classmethod
    def from_db(cls, db, field_names, values):
        # Remember the persisted stage so save() can detect a transition without a re-query.
        inst = super().from_db(db, field_names, values)
        inst._loaded_stage = inst.stage
        return inst

    def save(self, *args, **kwargs):
        # System-stamp stage_changed_at on any stage transition (incl. first create — a fresh
        # instance has no _loaded_stage, so the None sentinel never equals a real stage);
        # stamp lost_at when entering closed_lost, clear it if re-opened (mirrors Case.resolved_at).
        if self.stage != getattr(self, "_loaded_stage", None):
            self.stage_changed_at = timezone.now()
        if self.stage == "closed_lost":
            if self.lost_at is None:
                self.lost_at = timezone.now()
        else:
            self.lost_at = None
        super().save(*args, **kwargs)
        self._loaded_stage = self.stage

    @property
    def weighted_amount(self):
        """Pipeline-forecast value: amount × probability ÷ 100.

        Casts to Decimal so it is correct on a freshly-created instance (where the
        DecimalField value is still a string before the first DB round-trip)."""
        return Decimal(self.amount or 0) * self.probability / 100

    @property
    def is_open(self):
        return self.stage in self.OPEN_STAGES

    @property
    def is_won(self):
        return self.stage == "closed_won"

    def __str__(self):
        return f"{self.number} · {self.name}"


class OpportunitySplit(models.Model):
    """A sales-team credit/commission split on an Opportunity (1.2). Plain tenant-scoped row
    (no auto-number). Revenue-type splits across an opportunity must total ≤ 100% (validated in
    ``clean()`` + the add view); overlay credit is uncapped (it doesn't divide the booking)."""

    SPLIT_TYPE_CHOICES = [
        ("revenue", "Revenue"),
        ("overlay", "Overlay / Credit"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    opportunity = models.ForeignKey("Opportunity", on_delete=models.CASCADE, related_name="splits")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="crm_opportunity_splits")
    split_type = models.CharField(max_length=10, choices=SPLIT_TYPE_CHOICES, default="revenue")
    # WARNING: a negative percentage would slip under the ≤100% sum guard and corrupt
    # split_amount / forecast math — bound it to (0, 100].
    percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(100)])
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["split_type", "-percentage"]
        indexes = [
            models.Index(fields=["tenant", "opportunity"], name="crm_osplit_tnt_opp_idx"),
        ]

    @property
    def split_amount(self):
        """This split's share of the opportunity amount (Decimal-safe)."""
        return Decimal(self.opportunity.amount or 0) * Decimal(self.percentage or 0) / 100

    def clean(self):
        from django.core.exceptions import ValidationError
        # Defence in depth (the inline add calls clean() directly, not full_clean()): reject a
        # non-positive percentage so it can't slip under the ≤100% aggregate guard below.
        if self.percentage is not None and self.percentage <= 0:
            raise ValidationError("Percentage must be greater than zero.")
        # Revenue splits divide the booking — they must not exceed 100% across the opportunity.
        # (Guard on tenant_id too so a clean() before the view sets tenant can't query tenant=None.)
        if self.split_type == "revenue" and self.opportunity_id and self.tenant_id:
            from django.db.models import Sum
            others = OpportunitySplit.objects.filter(
                tenant=self.tenant, opportunity=self.opportunity, split_type="revenue")
            if self.pk:
                others = others.exclude(pk=self.pk)
            # DB-side SUM instead of fetching every split row to add in Python.
            existing = others.aggregate(t=Sum("percentage"))["t"] or Decimal(0)
            if existing + Decimal(self.percentage or 0) > 100:
                raise ValidationError("Revenue splits for an opportunity cannot exceed 100%.")

    def __str__(self):
        return f"{self.user} · {self.percentage}% ({self.get_split_type_display()})"
