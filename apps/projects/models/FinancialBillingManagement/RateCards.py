"""Projects 7.15 Financial & Billing Management — ProjectRateCard [RTC-].

Governs role and activity billing rate cards, project overrides, and pass-through
expense markup percentages. Fulfills 7.4 EVM pricing and billing basis rules.
"""
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from apps.projects.models._base import TenantNumbered, q2


class ProjectRateCard(TenantNumbered):
    NUMBER_PREFIX = "RTC"

    name = models.CharField(max_length=120)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rate_cards",
    )
    client = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_rate_cards",
    )
    role_name = models.CharField(max_length=100)
    activity_code = models.CharField(max_length=40, blank=True)
    hourly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    expense_markup_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.PROTECT,
        related_name="+",
    )
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = (("tenant", "number"),)
        indexes = [
            models.Index(fields=["tenant", "project", "is_active"], name="rtc_tnt_prj_act_idx"),
            models.Index(fields=["tenant", "client", "is_active"], name="rtc_tnt_cli_act_idx"),
        ]

    def __str__(self):
        scope = self.project.name if self.project else (self.client.name if self.client else "Global Standard")
        return f"{self.number} — {self.role_name} ({scope}): {self.hourly_rate} {self.currency.code}/hr"

    def clean(self):
        super().clean()
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            from django.core.exceptions import ValidationError
            raise ValidationError({"effective_to": "Effective to date cannot precede effective from date."})

    def save(self, *args, **kwargs):
        self.hourly_rate = q2(self.hourly_rate)
        self.expense_markup_pct = q2(self.expense_markup_pct)
        super().save(*args, **kwargs)
