"""Inventory 5.13 Inventory Forecasting & Planning — StockLevelPlan.

**Seasonality Planning** bullet: "Adjusting inventory targets based on seasonal peaks and
troughs." SCM 4.7 owns the DEMAND side — ``scm.DemandForecast`` predicts sales and
``scm.SeasonalityProfile`` carries the index curve (L36: never re-declare either).
What the spine does NOT hold is the inventory-side DECISION those numbers feed: the
stock level we choose to hold per SKU through the year. A StockLevelPlan is that
decision — a base target quantity over an effective window with an optional
seasonality profile applied ON TOP, so a 1.25 December index lifts December's target
25 % without anyone retyping twelve numbers.

The recommended level is DERIVED, never stored: it reads the profile's own
``apply_to()`` each time, so re-deriving an index next season cannot silently rewrite
what this plan says today. Applying the recommendation into live reorder parameters
stays the spine's job (4.7's gated apply on ReorderRule); this plan advises.
"""
from django.utils import timezone

from apps.core.utils import write_audit_log

from apps.inventory.models._base import *  # noqa: F401,F403


class StockLevelPlan(TenantNumbered):
    """A seasonality-aware stock target for one SKU [SLP-] [of 5.13]."""

    NUMBER_PREFIX = "SLP"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("archived", "Archived"),
    ]
    STATUS_CSS = {
        "draft": "badge-muted",
        "active": "badge-green",
        "archived": "badge-slate",
    }
    #: Statuses edit()/delete() may touch.
    EDITABLE_STATUSES = ("draft",)

    item = models.ForeignKey(
        "scm.Item", on_delete=models.PROTECT, related_name="stock_level_plans",
        help_text="The SKU being planned")
    location = models.ForeignKey(
        "scm.Location", on_delete=models.PROTECT, null=True, blank=True,
        related_name="stock_level_plans",
        help_text="Empty = network-wide plan row for this SKU")
    seasonal_profile = models.ForeignKey(
        "scm.SeasonalityProfile", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="stock_level_plans",
        help_text="Optional SCM index curve applied on top of the base target")
    base_target_qty = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Unadjusted stock target for index-neutral periods")
    min_qty = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(ZERO)],
        help_text="Floor below which the plan flags the item understocked")
    max_qty = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(ZERO)],
        help_text="Ceiling above which the plan flags excess stock")
    effective_from = models.DateField(default=timezone.localdate)
    effective_until = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft",
                              editable=False)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["item__sku", "-effective_from", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="inv_slp_tnt_status_idx"),
            models.Index(fields=["tenant", "item"], name="inv_slp_tnt_item_idx"),
        ]

    # -- derived planning figures ----------------------------------------------------------------

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    def is_in_effect(self, today=None):
        today = today or timezone.localdate()
        if self.status != "active":
            return False
        if self.effective_from and today < self.effective_from:
            return False
        if self.effective_until and today > self.effective_until:
            return False
        return True

    def recommended_qty(self, today=None):
        """Base target adjusted by the seasonality profile's factor for ``today``.

        Reads the profile's own ``apply_to()`` so the two modules can never disagree
        about what an index means; without a profile the base IS the recommendation.
        """
        baseline = self.base_target_qty or ZERO
        if self.seasonal_profile_id is None:
            return baseline
        factor, _uplift = self.seasonal_profile.apply_to(baseline, today or timezone.localdate())
        return (baseline * (factor or Decimal("1"))).quantize(Decimal("0.01"))

    @property
    def plan_flags(self):
        """(code, css) verdict against floor/ceiling when the plan is in effect."""
        from apps.scm.models import StockMove

        if not self.is_in_effect():
            return ("inactive", "badge-muted")
        scope = StockMove.objects.filter(tenant_id=self.tenant_id, item=self.item)
        if self.location_id:
            scope = scope.filter(location=self.location)
        qty = scope.aggregate(q=Sum("quantity"))["q"] or ZERO
        if self.min_qty is not None and qty < self.min_qty:
            return ("under", "badge-red")
        if self.max_qty is not None and qty > self.max_qty:
            return ("over", "badge-amber")
        return ("on_plan", "badge-green")

    # -- lifecycle --------------------------------------------------------------------------------

    def activate(self, user):
        """Promote a draft to active — at most one active plan per (item, location).

        Activating supersedes the previous active row by archiving it: history is
        kept, never overwritten, mirroring how price/plan rows age elsewhere.
        """
        with transaction.atomic():
            obj = type(self).objects.select_for_update().get(pk=self.pk)
            if obj.status != "draft":
                raise ValidationError(
                    f"{obj.number} is {obj.get_status_display().lower()} — only a draft "
                    "can be activated.")
            siblings = type(self).objects.filter(
                tenant_id=obj.tenant_id, item=obj.item, status="active").exclude(pk=obj.pk)
            if obj.location_id:
                siblings = siblings.filter(location=obj.location)
            else:
                siblings = siblings.filter(location__isnull=True)
            superseded = list(siblings)
            for sib in siblings:
                sib.status = "archived"
                sib.save(update_fields=["status", "updated_at"])
            obj.status = "active"
            obj.save(update_fields=["status", "updated_at"])
            write_audit_log(user, obj, "activate",
                            {"superseded": [s.number for s in superseded]})
            return obj

    def archive(self, user):
        with transaction.atomic():
            obj = type(self).objects.select_for_update().get(pk=self.pk)
            if obj.status == "archived":
                raise ValidationError(f"{obj.number} is already archived.")
            obj.status = "archived"
            obj.save(update_fields=["status", "updated_at"])
            write_audit_log(user, obj, "archive")
            return obj

    def clean(self):
        super().clean()
        if self.item_id and self.item.tenant_id != self.tenant_id:
            raise ValidationError({"item": "That item belongs to another workspace."})
        if self.location_id and self.location.tenant_id != self.tenant_id:
            raise ValidationError({"location": "That location belongs to another workspace."})
        if (self.seasonal_profile_id
                and self.seasonal_profile.tenant_id != self.tenant_id):
            raise ValidationError(
                {"seasonal_profile": "That profile belongs to another workspace."})
        if (self.effective_until and self.effective_from
                and self.effective_until < self.effective_from):
            raise ValidationError({"effective_until": "Ends before it starts."})
        if (self.min_qty is not None and self.max_qty is not None
                and self.max_qty < self.min_qty):
            raise ValidationError({"max_qty": "Ceiling below the floor."})

    def __str__(self):
        sku = self.item.sku if self.item_id else "?"
        return f"{self.number or 'SLP'} · {sku} ×{self.base_target_qty}"
