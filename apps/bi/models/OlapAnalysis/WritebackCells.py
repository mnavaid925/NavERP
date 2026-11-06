from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class ScenarioWritebackCell(TenantNumbered):
    NUMBER_PREFIX = "BWBC"

    SPREAD_METHOD_CHOICES = [
        ("direct_leaf", "Direct Leaf Adjustment"),
        ("pro_rata", "Pro-Rata Top-Down Splash"),
        ("equal", "Equal Split"),
        ("delta", "Incremental Delta"),
    ]

    scenario = models.ForeignKey(
        "bi.WhatIfScenario",
        on_delete=models.CASCADE,
        related_name="writeback_cells",
    )
    gl_account = models.ForeignKey(
        "accounting.GLAccount",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="scenario_writeback_cells",
    )
    org_unit = models.ForeignKey(
        "core.OrgUnit",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="scenario_writeback_cells",
    )
    cell_coordinates = models.JSONField(
        default=dict,
        help_text="Dimensional tuple coordinates: e.g. {'period': '2026-Q1', 'region': 'East'}",
    )
    baseline_value = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    adjusted_value = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    variance_amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    spread_method = models.CharField(
        max_length=20,
        choices=SPREAD_METHOD_CHOICES,
        default="direct_leaf",
    )
    is_committed = models.BooleanField(default=False)
    committed_budget_line = models.ForeignKey(
        "accounting.BudgetLine",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bi_writeback_cells",
    )
    commentary = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_writeback_cells",
    )

    class Meta:
        db_table = "bi_scenario_writeback_cell"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bwbc_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "scenario"], name="idx_bwbc_ten_scen"),
            models.Index(fields=["tenant", "gl_account"], name="idx_bwbc_ten_gl"),
            models.Index(fields=["tenant", "org_unit"], name="idx_bwbc_ten_org"),
            models.Index(fields=["tenant", "is_committed"], name="idx_bwbc_ten_sync"),
        ]

    def __str__(self):
        return f"{self.number}"

    def get_absolute_url(self):
        return reverse("bi:writeback_cell_detail", kwargs={"pk": self.pk})

    def save(self, *args, **kwargs):
        self.variance_amount = self.adjusted_value - self.baseline_value
        super().save(*args, **kwargs)
