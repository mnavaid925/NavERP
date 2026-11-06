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

    def __init__(self, *args, **kwargs):
        if "coordinate_keys_json" in kwargs and "cell_coordinates" not in kwargs:
            kwargs["cell_coordinates"] = kwargs.pop("coordinate_keys_json")
        if "baseline_amount" in kwargs and "baseline_value" not in kwargs:
            kwargs["baseline_value"] = kwargs.pop("baseline_amount")
        if "simulated_amount" in kwargs and "adjusted_value" not in kwargs:
            kwargs["adjusted_value"] = kwargs.pop("simulated_amount")
        if "adjustment_delta" in kwargs:
            delta = kwargs.pop("adjustment_delta")
            if "adjusted_value" not in kwargs and "baseline_value" in kwargs:
                kwargs["adjusted_value"] = kwargs["baseline_value"] + delta
        if "adjustment_method" in kwargs and "spread_method" not in kwargs:
            method = kwargs.pop("adjustment_method")
            if method == "absolute":
                method = "direct_leaf"
            kwargs["spread_method"] = method
        super().__init__(*args, **kwargs)

    def __str__(self):
        return f"{self.number}"

    def get_absolute_url(self):
        return reverse("bi:writeback_cell_detail", kwargs={"pk": self.pk})

    @property
    def coordinate_keys_json(self):
        return self.cell_coordinates

    @coordinate_keys_json.setter
    def coordinate_keys_json(self, value):
        self.cell_coordinates = value

    @property
    def baseline_amount(self):
        return self.baseline_value

    @baseline_amount.setter
    def baseline_amount(self, value):
        self.baseline_value = value

    @property
    def simulated_amount(self):
        return self.adjusted_value

    @simulated_amount.setter
    def simulated_amount(self, value):
        self.adjusted_value = value

    @property
    def adjustment_delta(self):
        return self.variance_amount

    @adjustment_delta.setter
    def adjustment_delta(self, value):
        self.variance_amount = value

    @property
    def adjustment_method(self):
        return self.spread_method

    @adjustment_method.setter
    def adjustment_method(self, value):
        self.spread_method = value

    def save(self, *args, **kwargs):
        self.variance_amount = self.adjusted_value - self.baseline_value
        super().save(*args, **kwargs)
