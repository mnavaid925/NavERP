from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Avg, Sum

from apps.assets.models._base import TenantNumbered
from apps.assets.models.AssetAnalytics._validators import (
    ZERO,
    add_field_error,
    cap_decimal,
    q2,
    validate_tenant_fks,
)


class AssetPortfolioScenario(TenantNumbered):
    """
    Portfolio What-If Scenario Model [AWIF-].
    Simulates multi-year CapEx, OpEx maintenance, deferred backlog, FCI, health score, risk exposure,
    NPV, payback period, and benefit-cost ratio across expansion, consolidation, accelerated replacement,
    and budget constraint strategies.
    """

    NUMBER_PREFIX = "AWIF"

    SCENARIO_TYPE_CHOICES = [
        ("baseline_bau", "Baseline (Business-As-Usual)"),
        ("fleet_expansion", "Fleet / Capacity Expansion"),
        ("site_consolidation", "Site / Fleet Consolidation"),
        ("accelerated_replacement", "Accelerated Replacement Program"),
        ("budget_constrained", "CapEx Budget Cap Constraint"),
        ("deferred_maintenance_impact", "Deferred Maintenance Impact"),
        ("sustainability_retrofit", "Efficiency & Electrification Retrofit"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("simulated", "Simulated"),
        ("under_review", "Under Review"),
        ("recommended", "Recommended"),
        ("adopted", "Adopted"),
        ("archived", "Archived"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "simulated": "badge-info",
        "under_review": "badge-amber",
        "recommended": "badge-green",
        "adopted": "badge-green",
        "archived": "badge-muted",
    }

    LOCKED_STATUSES = {"adopted", "archived"}

    ALLOWED_TRANSITIONS = {
        "draft": {"simulated", "under_review", "archived"},
        "simulated": {"under_review", "recommended", "archived"},
        "under_review": {"recommended", "archived"},
        "recommended": {"adopted", "archived"},
        "adopted": {"archived"},
        "archived": set(),
    }

    SCENARIO_TYPE_CSS = {
        "baseline_bau": "badge-slate",
        "fleet_expansion": "badge-info",
        "site_consolidation": "badge-amber",
        "accelerated_replacement": "badge-green",
        "budget_constrained": "badge-red",
        "deferred_maintenance_impact": "badge-red",
        "sustainability_retrofit": "badge-green",
    }

    name = models.CharField(
        max_length=255,
        help_text="Scenario title for portfolio strategic planning comparison",
    )
    scenario_type = models.CharField(
        max_length=35,
        choices=SCENARIO_TYPE_CHOICES,
        default="baseline_bau",
    )
    is_baseline = models.BooleanField(default=False)
    base_fiscal_year = models.PositiveIntegerField(default=2026)
    horizon_years = models.PositiveSmallIntegerField(default=5)

    scope_org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_portfolio_scenarios",
    )
    scope_category = models.ForeignKey(
        "assets.AssetCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_portfolio_scenarios",
    )
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_portfolio_scenarios",
    )
    baseline_scenario = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="derived_scenarios",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_asset_scenarios",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
    )

    # Simulation Input Levers
    annual_capex_budget_limit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    discount_rate_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("8.00"),
    )
    inflation_rate_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("4.00"),
    )
    acceleration_months = models.IntegerField(default=0)
    fleet_growth_pct = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    consolidation_reduction_pct = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    maintenance_efficiency_gain_pct = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    # Server-Computed Outputs
    baseline_capex_total = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    simulated_capex_total = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    capex_variance_amount = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    baseline_opex_maintenance = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    simulated_opex_maintenance = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    opex_savings_amount = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    baseline_deferred_backlog = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    simulated_deferred_backlog = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    baseline_avg_health_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    simulated_avg_health_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    baseline_fci_pct = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0.00"))
    simulated_fci_pct = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0.00"))
    baseline_risk_exposure = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    simulated_risk_exposure = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    net_present_value = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    payback_period_years = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    benefit_cost_ratio = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))

    assumptions_summary = models.TextField(blank=True)

    class Meta:
        ordering = ["-base_fiscal_year", "-id"]
        verbose_name = "Asset Portfolio Scenario"
        verbose_name_plural = "Asset Portfolio Scenarios"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_awif_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_awif_ten_stat"),
            models.Index(fields=["tenant", "scenario_type"], name="idx_awif_ten_type"),
            models.Index(fields=["tenant", "base_fiscal_year"], name="idx_awif_ten_yr"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name}"

    @property
    def is_locked(self):
        return self.status in self.LOCKED_STATUSES

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def scenario_type_badge_class(self):
        return self.SCENARIO_TYPE_CSS.get(self.scenario_type, "badge-slate")

    def run_simulation(self, save=True):
        """
        Deterministically project CapEx, maintenance OpEx, deferred backlog, FCI %, health score,
        risk exposure, NPV, payback period, and BCR against scoped tenant portfolio baselines.
        """
        if self.is_locked:
            raise ValidationError(
                "Adopted or archived portfolio scenarios are locked and cannot be re-simulated."
            )
        from apps.assets.models.AssetAnalytics.AssetLifecycleCostAnalyses import (
            AssetLifecycleCostAnalysis,
        )
        from apps.assets.models.AssetAnalytics.AssetReplacementPlans import (
            AssetReplacementPlan,
        )
        from apps.assets.models.AssetReliability.AssetConditionAssessments import (
            AssetConditionAssessment,
        )
        from apps.assets.models.AssetRisk.AssetRiskRegisters import AssetRiskRegister

        horizon = min(30, max(1, int(self.horizon_years or 5)))
        tenant_id = self.tenant_id

        plan_qs = AssetReplacementPlan.objects.filter(tenant_id=tenant_id).exclude(
            status__in=["executed", "cancelled"]
        )
        alcc_qs = AssetLifecycleCostAnalysis.objects.filter(tenant_id=tenant_id).exclude(
            status="archived"
        )
        cond_qs = AssetConditionAssessment.objects.filter(tenant_id=tenant_id).exclude(
            status="archived"
        )
        risk_qs = AssetRiskRegister.objects.filter(tenant_id=tenant_id).exclude(
            status="closed"
        )

        if self.scope_org_unit_id:
            plan_qs = plan_qs.filter(org_unit_id=self.scope_org_unit_id)
            alcc_qs = alcc_qs.filter(org_unit_id=self.scope_org_unit_id)
            cond_qs = cond_qs.filter(operational_asset__org_unit_id=self.scope_org_unit_id)
            risk_qs = risk_qs.filter(asset__org_unit_id=self.scope_org_unit_id)

        if self.scope_category_id:
            plan_qs = plan_qs.filter(asset_category_id=self.scope_category_id)
            alcc_qs = alcc_qs.filter(asset_category_id=self.scope_category_id)
            cond_qs = cond_qs.filter(asset_category_id=self.scope_category_id)
            risk_qs = risk_qs.filter(category_id=self.scope_category_id)

        plan_agg = plan_qs.aggregate(
            capex=Sum("inflation_adjusted_cost"),
            base_cost=Sum("estimated_replacement_cost"),
            crv=Sum("current_replacement_value"),
            deferred=Sum("deferred_maintenance_cost"),
        )
        alcc_agg = alcc_qs.aggregate(
            pm=Sum("preventive_maintenance_cost"),
            cm=Sum("corrective_maintenance_cost"),
            svc=Sum("service_contract_cost"),
            crv=Sum("current_replacement_value"),
        )
        avg_health = cond_qs.aggregate(avg_h=Avg("health_score"))["avg_h"]
        risk_exposure = risk_qs.aggregate(total=Sum("financial_exposure_amount"))["total"] or ZERO

        base_capex = plan_agg["capex"] or plan_agg["base_cost"] or ZERO
        if base_capex <= ZERO and self.baseline_scenario_id and self.baseline_scenario:
            base_capex = self.baseline_scenario.baseline_capex_total or ZERO
        if base_capex <= ZERO and (self.annual_capex_budget_limit or ZERO) > ZERO:
            base_capex = self.annual_capex_budget_limit * Decimal(horizon)

        base_opex = (alcc_agg["pm"] or ZERO) + (alcc_agg["cm"] or ZERO) + (alcc_agg["svc"] or ZERO)
        if base_opex <= ZERO and self.baseline_scenario_id and self.baseline_scenario:
            base_opex = self.baseline_scenario.baseline_opex_maintenance or ZERO
        elif base_opex <= ZERO and base_capex > ZERO:
            base_opex = base_capex * Decimal("0.20")

        base_backlog = plan_agg["deferred"] or ZERO
        total_crv = plan_agg["crv"] or alcc_agg["crv"] or base_capex or ZERO
        base_health = Decimal(str(avg_health)) if avg_health is not None else Decimal("72.00")
        base_fci = cap_decimal((base_backlog / total_crv) * Decimal("100.00")) if total_crv > ZERO else ZERO
        base_risk = risk_exposure

        growth_pct = max(Decimal("-95.00"), min(Decimal("500.00"), self.fleet_growth_pct or ZERO))
        growth_factor = max(ZERO, Decimal("1.00") + (growth_pct / Decimal("100.00")))
        consol_pct = max(ZERO, min(Decimal("90.00"), self.consolidation_reduction_pct or ZERO))
        consol_factor = Decimal("1.00") - (consol_pct / Decimal("100.00"))
        eff_gain = max(ZERO, min(Decimal("80.00"), self.maintenance_efficiency_gain_pct or ZERO))
        eff_factor = Decimal("1.00") - (eff_gain / Decimal("100.00"))
        accel_months = max(-60, min(120, int(self.acceleration_months or 0)))
        accel_yrs = Decimal(accel_months) / Decimal("12.00")

        capex_mult = growth_factor * consol_factor
        opex_mult = growth_factor * consol_factor * eff_factor
        backlog_mult = Decimal("1.00")
        health_delta = ZERO
        risk_mult = Decimal("1.00")

        stype = self.scenario_type
        if stype == "fleet_expansion":
            exp_uplift = max(Decimal("1.10"), growth_factor)
            capex_mult = exp_uplift * consol_factor
            opex_mult = (Decimal("1.00") + (exp_uplift - Decimal("1.00")) * Decimal("0.75")) * eff_factor
            backlog_mult = Decimal("0.92")
            health_delta = Decimal("3.50")
            risk_mult = Decimal("0.95")
        elif stype == "site_consolidation":
            red_factor = min(Decimal("0.88"), consol_factor)
            capex_mult = red_factor
            opex_mult = red_factor * eff_factor
            backlog_mult = Decimal("0.80")
            health_delta = Decimal("4.00")
            risk_mult = Decimal("0.85")
        elif stype == "accelerated_replacement":
            front_load = Decimal("1.00") + max(Decimal("0.05"), accel_yrs * Decimal("0.08"))
            capex_mult = front_load * growth_factor * consol_factor
            opex_mult = Decimal("0.82") * eff_factor
            backlog_mult = Decimal("0.60")
            health_delta = Decimal("9.50")
            risk_mult = Decimal("0.70")
        elif stype == "budget_constrained":
            opex_mult = Decimal("1.08") * eff_factor
            backlog_mult = Decimal("1.25")
            health_delta = Decimal("-4.50")
            risk_mult = Decimal("1.15")
        elif stype == "deferred_maintenance_impact":
            capex_mult = Decimal("0.60")
            opex_mult = Decimal("1.18")
            backlog_mult = Decimal("1.45")
            health_delta = Decimal("-8.00")
            risk_mult = Decimal("1.25")
        elif stype == "sustainability_retrofit":
            retrofit_eff = min(Decimal("0.85"), eff_factor)
            capex_mult = Decimal("1.12") * growth_factor * consol_factor
            opex_mult = retrofit_eff * Decimal("0.90")
            backlog_mult = Decimal("0.78")
            health_delta = Decimal("6.00")
            risk_mult = Decimal("0.80")

        sim_capex = base_capex * capex_mult
        budget_ceiling = (self.annual_capex_budget_limit or ZERO) * Decimal(horizon)
        if stype == "budget_constrained" and budget_ceiling > ZERO and sim_capex > budget_ceiling:
            unmet = sim_capex - budget_ceiling
            sim_capex = budget_ceiling
            sim_backlog = (base_backlog + unmet) * backlog_mult
        elif stype == "budget_constrained" and budget_ceiling <= ZERO:
            unmet = base_capex * Decimal("0.25")
            sim_capex = base_capex * Decimal("0.75")
            sim_backlog = base_backlog * backlog_mult + unmet
        else:
            sim_backlog = base_backlog * backlog_mult

        sim_opex = base_opex * opex_mult
        sim_health = min(Decimal("100.00"), max(ZERO, base_health + health_delta))
        sim_crv = total_crv * max(Decimal("0.50"), growth_factor * consol_factor)
        sim_fci = cap_decimal((sim_backlog / sim_crv) * Decimal("100.00")) if sim_crv > ZERO else ZERO
        sim_risk = base_risk * risk_mult

        max_money = Decimal("99999999999999.99")
        self.baseline_capex_total = cap_decimal(base_capex, max_abs=max_money)
        self.simulated_capex_total = cap_decimal(sim_capex, max_abs=max_money)
        self.capex_variance_amount = cap_decimal(sim_capex - base_capex, max_abs=max_money)
        self.baseline_opex_maintenance = cap_decimal(base_opex, max_abs=max_money)
        self.simulated_opex_maintenance = cap_decimal(sim_opex, max_abs=max_money)
        self.opex_savings_amount = cap_decimal(base_opex - sim_opex, max_abs=max_money)
        self.baseline_deferred_backlog = cap_decimal(base_backlog, max_abs=max_money)
        self.simulated_deferred_backlog = cap_decimal(sim_backlog, max_abs=max_money)
        self.baseline_avg_health_score = cap_decimal(base_health, max_abs=Decimal("100.00"))
        self.simulated_avg_health_score = cap_decimal(sim_health, max_abs=Decimal("100.00"))
        self.baseline_fci_pct = base_fci
        self.simulated_fci_pct = sim_fci
        self.baseline_risk_exposure = cap_decimal(base_risk, max_abs=max_money)
        self.simulated_risk_exposure = cap_decimal(sim_risk, max_abs=max_money)

        # Economic NPV, Payback & BCR over horizon
        annual_opex_saving = (base_opex - sim_opex) / Decimal(horizon)
        annual_risk_saving = (base_risk - sim_risk) / Decimal(horizon)
        annual_benefit = annual_opex_saving + annual_risk_saving
        incremental_capex = sim_capex - base_capex

        disc_pct = max(
            ZERO,
            min(Decimal("100.00"), self.discount_rate_pct if self.discount_rate_pct is not None else Decimal("8.00")),
        )
        disc_rate = disc_pct / Decimal("100.00")
        pv_benefits = ZERO
        for yr in range(1, horizon + 1):
            denom = (Decimal("1.00") + disc_rate) ** yr
            pv_benefits += annual_benefit / denom

        self.net_present_value = cap_decimal(pv_benefits - incremental_capex, max_abs=max_money)

        investment = sim_capex if incremental_capex <= ZERO else incremental_capex
        if annual_benefit > ZERO and investment > ZERO:
            self.payback_period_years = cap_decimal(investment / annual_benefit, max_abs=Decimal("999.99"))
        else:
            self.payback_period_years = ZERO

        gross_benefits = (base_opex - sim_opex) + (base_risk - sim_risk)
        cost_basis = sim_capex if sim_capex > ZERO else base_capex
        if cost_basis > ZERO and gross_benefits > ZERO:
            self.benefit_cost_ratio = cap_decimal(gross_benefits / cost_basis, max_abs=Decimal("999.99"))
        else:
            self.benefit_cost_ratio = ZERO

        if self.status == "draft":
            self.status = "simulated"
        if save:
            self.save()

    def clean(self):
        errors = {}
        validate_tenant_fks(
            self,
            errors,
            ["scope_org_unit", "scope_category", "baseline_scenario", "owner"],
        )
        if self.pk and self.baseline_scenario_id == self.pk:
            add_field_error(errors, "baseline_scenario", "A scenario cannot reference itself as its baseline.")
        if self.horizon_years is None or not (1 <= int(self.horizon_years) <= 30):
            add_field_error(errors, "horizon_years", "Simulation horizon must be between 1 and 30 years.")
        if self.acceleration_months is not None and not (-60 <= int(self.acceleration_months) <= 120):
            add_field_error(errors, "acceleration_months", "Acceleration months must be between -60 and 120.")
        if self.fleet_growth_pct is not None and (
            self.fleet_growth_pct < Decimal("-95.00") or self.fleet_growth_pct > Decimal("500.00")
        ):
            add_field_error(errors, "fleet_growth_pct", "Fleet growth % must be between -95.00% and 500.00%.")
        if self.base_fiscal_year is not None and not (2000 <= int(self.base_fiscal_year) <= 2100):
            add_field_error(errors, "base_fiscal_year", "Base fiscal year must be between 2000 and 2100.")
        if (self.annual_capex_budget_limit or ZERO) < ZERO:
            add_field_error(errors, "annual_capex_budget_limit", "Budget limit cannot be negative.")
        if self.discount_rate_pct is not None and (self.discount_rate_pct < ZERO or self.discount_rate_pct > Decimal("100.00")):
            add_field_error(errors, "discount_rate_pct", "Discount rate must be between 0% and 100%.")
        if self.inflation_rate_pct is not None and (self.inflation_rate_pct < ZERO or self.inflation_rate_pct > Decimal("50.00")):
            add_field_error(errors, "inflation_rate_pct", "Inflation rate must be between 0% and 50%.")
        if self.consolidation_reduction_pct is not None and (
            self.consolidation_reduction_pct < ZERO or self.consolidation_reduction_pct > Decimal("100.00")
        ):
            add_field_error(errors, "consolidation_reduction_pct", "Consolidation reduction must be between 0% and 100%.")
        if self.maintenance_efficiency_gain_pct is not None and (
            self.maintenance_efficiency_gain_pct < ZERO or self.maintenance_efficiency_gain_pct > Decimal("100.00")
        ):
            add_field_error(errors, "maintenance_efficiency_gain_pct", "Efficiency gain must be between 0% and 100%.")
        if errors:
            raise ValidationError(errors)
