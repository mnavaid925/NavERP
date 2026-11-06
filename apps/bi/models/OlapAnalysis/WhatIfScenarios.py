from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from apps.bi.models._base import TenantNumbered


class WhatIfScenario(TenantNumbered):
    NUMBER_PREFIX = "BWIF"

    STATUS_CHOICES = [
        ("draft", "Draft Simulation"),
        ("simulated", "Simulated"),
        ("approved", "Approved by Management"),
        ("committed", "Committed to Ledger / Budget"),
        ("archived", "Archived"),
    ]

    DEFAULT_DISAGGREGATION_CHOICES = [
        ("pro_rata", "Pro-Rata / Proportional Splash"),
        ("equal", "Equal Split Across Leaf Cells"),
        ("delta", "Direct Delta Offset"),
    ]

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120)
    description = models.TextField(blank=True)
    cube = models.ForeignKey(
        "bi.OlapCube",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="scenarios",
    )
    baseline_budget = models.ForeignKey(
        "accounting.Budget",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bi_what_if_scenarios",
    )
    fiscal_period = models.ForeignKey(
        "accounting.FiscalPeriod",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bi_what_if_scenarios",
    )
    driver_parameters = models.JSONField(
        default=dict,
        help_text="Global simulation drivers: e.g. revenue_growth_pct, cost_inflation_pct",
    )
    default_disaggregation = models.CharField(
        max_length=20,
        choices=DEFAULT_DISAGGREGATION_CHOICES,
        default="pro_rata",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
    )
    total_baseline_amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    total_adjusted_amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    total_variance_amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    committed_at = models.DateTimeField(null=True, blank=True)
    committed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="committed_scenarios",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_what_if_scenarios",
    )

    class Meta:
        db_table = "bi_what_if_scenario"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "slug"], name="bi_bwif_tenant_slug_uniq"),
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bwif_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_bwif_ten_stat"),
            models.Index(fields=["tenant", "fiscal_period"], name="idx_bwif_ten_period"),
            models.Index(fields=["tenant", "created_by"], name="idx_bwif_ten_user"),
        ]

    def __str__(self):
        return f"{self.name} ({self.number})"

    def get_absolute_url(self):
        return reverse("bi:what_if_scenario_detail", kwargs={"pk": self.pk})

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or "scenario"
            self.slug = base_slug[:120]
        self.total_variance_amount = self.total_adjusted_amount - self.total_baseline_amount
        super().save(*args, **kwargs)
