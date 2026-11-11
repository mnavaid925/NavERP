from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Max, Q, Sum
from django.utils import timezone

from apps.assets.models._base import TenantNumbered
from apps.assets.models.AssetAnalytics._validators import (
    ZERO,
    add_field_error,
    cap_decimal,
    q2,
    validate_tenant_fks,
)


class AssetLifecycleCostAnalysis(TenantNumbered):
    """
    Asset Lifecycle Cost Analysis (LCC) [ALCC-].
    Captures cradle-to-grave Total Cost of Ownership (CapEx, preventive/corrective maintenance,
    service contracts, energy, downtime, insurance/compliance minus salvage & warranty recoveries),
    Equivalent Annual Cost (EAC), Maintenance-to-RAV %, and Repair-vs-Replace recommendations.
    """

    NUMBER_PREFIX = "ALCC"

    LIFECYCLE_STAGE_CHOICES = [
        ("acquisition", "Acquisition & Commissioning"),
        ("in_service", "Active In-Service"),
        ("mid_life", "Mid-Life Operations"),
        ("late_life", "Late-Life / High Maintenance"),
        ("end_of_life", "End-of-Life Candidate"),
        ("disposed", "Disposed / Retired"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("calculated", "Calculated"),
        ("reviewed", "Reviewed"),
        ("approved", "Approved"),
        ("archived", "Archived"),
    ]

    RECOMMENDATION_CHOICES = [
        ("retain_operate", "Retain & Operate"),
        ("overhaul_refurbish", "Overhaul / Refurbish"),
        ("schedule_replacement", "Schedule Replacement"),
        ("dispose_retire", "Dispose / Retire"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "calculated": "badge-info",
        "reviewed": "badge-amber",
        "approved": "badge-green",
        "archived": "badge-muted",
    }

    LOCKED_STATUSES = {"approved", "archived"}

    ALLOWED_TRANSITIONS = {
        "draft": {"calculated", "reviewed", "archived"},
        "calculated": {"reviewed", "approved", "archived"},
        "reviewed": {"approved", "archived"},
        "approved": {"archived"},
        "archived": set(),
    }

    LIFECYCLE_STAGE_CSS = {
        "acquisition": "badge-info",
        "in_service": "badge-green",
        "mid_life": "badge-slate",
        "late_life": "badge-amber",
        "end_of_life": "badge-red",
        "disposed": "badge-muted",
    }

    RECOMMENDATION_CSS = {
        "retain_operate": "badge-green",
        "overhaul_refurbish": "badge-info",
        "schedule_replacement": "badge-amber",
        "dispose_retire": "badge-red",
    }

    title = models.CharField(
        max_length=255,
        help_text="Lifecycle cost analysis study title or asset fleet scope",
    )
    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lifecycle_cost_analyses",
        help_text="Linked financial fixed asset register record",
    )
    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lifecycle_cost_analyses",
        help_text="Linked operational equipment or facility asset",
    )
    asset_category = models.ForeignKey(
        "assets.AssetCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lifecycle_cost_analyses",
        help_text="Classification category for benchmark grouping",
    )
    asset_model = models.ForeignKey(
        "assets.AssetModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lifecycle_cost_analyses",
        help_text="Standard catalog make/model reference",
    )
    org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_lifecycle_analyses",
        help_text="Responsible department or operating business unit",
    )
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_lifecycle_analyses",
        help_text="Reporting currency for monetary lifecycle amounts",
    )
    analyzed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_lifecycle_analyses",
        help_text="Reliability or financial analyst owning the LCC model",
    )

    analysis_date = models.DateField(
        default=timezone.localdate,
        help_text="As-of valuation date for lifecycle spend aggregation",
    )
    analysis_horizon_years = models.PositiveSmallIntegerField(
        default=5,
        help_text="Evaluation horizon in years used to annualize TCO into EAC",
    )
    discount_rate_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("8.00"),
        help_text="Annual WACC / hurdle discount rate percentage for EAC calculation",
    )
    lifecycle_stage = models.CharField(
        max_length=20,
        choices=LIFECYCLE_STAGE_CHOICES,
        default="in_service",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
    )

    # Spend & Recovery Buckets
    acquisition_capital_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Original purchase / capitalized acquisition basis",
    )
    installation_commissioning_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Freight, rigging, civil works, and commissioning spend",
    )
    preventive_maintenance_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Scheduled PM, inspection, and calibration maintenance spend",
    )
    corrective_maintenance_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Unplanned repairs, breakdowns, and major overhaul spend",
    )
    service_contract_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Third-party OEM SLA and maintenance contract expenditure",
    )
    energy_utility_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Cumulative electricity, fuel, and utility operating cost",
    )
    downtime_opportunity_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Production loss value attributed to asset downtime events",
    )
    insurance_compliance_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Policy premiums, permits, and statutory regulatory costs",
    )
    accumulated_depreciation_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Posted cumulative accounting depreciation reference",
    )
    expected_salvage_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Estimated end-of-life residual resale or scrap recovery",
    )
    warranty_insurance_recoveries = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Approved warranty reimbursements, insurance payouts, and disposal credits",
    )
    current_replacement_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Modern equivalent replacement asset value (RAV) denominator",
    )

    # Computed Outputs
    total_lifecycle_cost = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    equivalent_annual_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    maintenance_to_rav_pct = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    opex_to_capex_ratio = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    economic_eol_year = models.PositiveIntegerField(
        null=True,
        blank=True,
    )
    recommendation = models.CharField(
        max_length=30,
        choices=RECOMMENDATION_CHOICES,
        default="retain_operate",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-analysis_date", "-id"]
        verbose_name = "Asset Lifecycle Cost Analysis"
        verbose_name_plural = "Asset Lifecycle Cost Analyses"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_alcc_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_alcc_ten_stat"),
            models.Index(fields=["tenant", "lifecycle_stage"], name="idx_alcc_ten_stg"),
            models.Index(fields=["tenant", "recommendation"], name="idx_alcc_ten_rec"),
            models.Index(fields=["tenant", "analysis_date"], name="idx_alcc_ten_date"),
            models.Index(fields=["tenant", "asset_category"], name="idx_alcc_ten_cat"),
            models.Index(fields=["tenant", "org_unit"], name="idx_alcc_ten_org"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"

    @property
    def is_locked(self):
        return self.status in self.LOCKED_STATUSES

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def lifecycle_stage_badge_class(self):
        return self.LIFECYCLE_STAGE_CSS.get(self.lifecycle_stage, "badge-slate")

    @property
    def recommendation_badge_class(self):
        return self.RECOMMENDATION_CSS.get(self.recommendation, "badge-slate")

    @property
    def total_capex_amount(self):
        return q2((self.acquisition_capital_cost or ZERO) + (self.installation_commissioning_cost or ZERO))

    @property
    def total_maintenance_amount(self):
        return q2(
            (self.preventive_maintenance_cost or ZERO)
            + (self.corrective_maintenance_cost or ZERO)
            + (self.service_contract_cost or ZERO)
        )

    @property
    def total_opex_amount(self):
        return q2(
            self.total_maintenance_amount
            + (self.energy_utility_cost or ZERO)
            + (self.downtime_opportunity_cost or ZERO)
            + (self.insurance_compliance_cost or ZERO)
        )

    @property
    def total_recoveries_amount(self):
        return q2((self.expected_salvage_value or ZERO) + (self.warranty_insurance_recoveries or ZERO))

    def recalculate_metrics(self):
        """Derive net TCO, annuity Equivalent Annual Cost (EAC), Maintenance/RAV %, OpEx/CapEx, and EOL recommendation."""
        capex = self.total_capex_amount
        maint = self.total_maintenance_amount
        opex = self.total_opex_amount
        recoveries = self.total_recoveries_amount

        net_tco = max(ZERO, capex + opex - recoveries)
        self.total_lifecycle_cost = cap_decimal(net_tco, max_abs=Decimal("99999999999999.99"))

        horizon = min(50, max(1, int(self.analysis_horizon_years or 1)))
        rate_pct = max(ZERO, min(Decimal("100.00"), self.discount_rate_pct or ZERO))
        if rate_pct > ZERO and net_tco > ZERO:
            rate = rate_pct / Decimal("100.00")
            compound = (Decimal("1.00") + rate) ** horizon
            denom = compound - Decimal("1.00")
            if denom > ZERO:
                crf = (rate * compound) / denom
                self.equivalent_annual_cost = cap_decimal(
                    net_tco * crf, max_abs=Decimal("999999999999.99")
                )
            else:
                self.equivalent_annual_cost = cap_decimal(
                    net_tco / Decimal(horizon), max_abs=Decimal("999999999999.99")
                )
        else:
            self.equivalent_annual_cost = cap_decimal(
                net_tco / Decimal(horizon), max_abs=Decimal("999999999999.99")
            )

        rav = self.current_replacement_value or ZERO
        if rav > ZERO:
            self.maintenance_to_rav_pct = cap_decimal((maint / rav) * Decimal("100.00"))
        else:
            self.maintenance_to_rav_pct = ZERO

        if capex > ZERO:
            self.opex_to_capex_ratio = cap_decimal(opex / capex)
        else:
            self.opex_to_capex_ratio = ZERO

        mcr = self.maintenance_to_rav_pct
        ratio = self.opex_to_capex_ratio
        if self.lifecycle_stage in ("end_of_life", "disposed") and mcr >= Decimal("60.00"):
            self.recommendation = "dispose_retire"
        elif mcr >= Decimal("50.00") or ratio >= Decimal("1.50") or self.lifecycle_stage == "end_of_life":
            self.recommendation = "schedule_replacement"
        elif mcr >= Decimal("25.00") or self.lifecycle_stage == "late_life":
            self.recommendation = "overhaul_refurbish"
        else:
            self.recommendation = "retain_operate"

        base_year = self.analysis_date.year if self.analysis_date else timezone.localdate().year
        if self.recommendation == "dispose_retire":
            self.economic_eol_year = base_year
        elif self.recommendation == "schedule_replacement":
            self.economic_eol_year = base_year + 1
        else:
            self.economic_eol_year = base_year + horizon

    def _dual_asset_filter(self, fixed_field="fixed_asset_id", op_field="operational_asset_id"):
        """Build Q filter matching either the linked fixed_asset or operational_asset."""
        q_obj = Q()
        if fixed_field and self.fixed_asset_id:
            q_obj |= Q(**{fixed_field: self.fixed_asset_id})
        if op_field and self.operational_asset_id:
            q_obj |= Q(**{op_field: self.operational_asset_id})
        return q_obj

    def populate_from_asset_records(self, save=True):
        """
        Aggregate historical CapEx, depreciation, preventive/corrective maintenance, SLA contracts,
        energy, downtime, insurance, and disposal/warranty recoveries from linked asset records.
        """
        if self.is_locked:
            raise ValidationError(
                "Approved or archived lifecycle cost analyses are locked and cannot be recalculated."
            )
        if not self.tenant_id:
            return
        if not self.fixed_asset_id and not self.operational_asset_id:
            if self.status == "draft":
                self.status = "calculated"
            self.recalculate_metrics()
            if save:
                self.save()
            return

        from apps.assets.models.AssetCompliance.AssetComplianceIncidents import AssetComplianceIncident
        from apps.assets.models.AssetDepreciation.AssetDepreciationSchedules import AssetDepreciationSchedule
        from apps.assets.models.AssetDisposal.AssetDisposalRequests import AssetDisposalRequest
        from apps.assets.models.AssetDisposal.AssetResaleListings import AssetResaleListing
        from apps.assets.models.AssetDisposal.AssetScrapSalvages import AssetScrapSalvage
        from apps.assets.models.AssetMaintenance.AssetMaintenanceLogs import AssetMaintenanceLog
        from apps.assets.models.AssetMaintenance.AssetServiceContracts import AssetServiceContract
        from apps.assets.models.AssetPerformance.AssetDowntimeLogs import AssetDowntimeLog
        from apps.assets.models.AssetPerformance.AssetEnergyReadings import AssetEnergyReading
        from apps.assets.models.AssetProcurement.AssetCapitalizations import AssetCapitalization
        from apps.assets.models.AssetWarrantyInsurance.AssetInsuranceClaims import AssetInsuranceClaim
        from apps.assets.models.AssetWarrantyInsurance.AssetInsurancePolicies import AssetInsurancePolicy
        from apps.assets.models.AssetWarrantyInsurance.AssetWarrantyClaims import AssetWarrantyClaim

        dual_q = self._dual_asset_filter()

        cap_agg = AssetCapitalization.objects.filter(
            tenant_id=self.tenant_id, status="capitalized"
        ).filter(dual_q).aggregate(
            total_basis=Sum("total_cost_basis"),
            total_install=Sum("installation_cost"),
        )
        cap_basis = cap_agg["total_basis"] or ZERO
        install_sum = cap_agg["total_install"] or ZERO
        if cap_basis > ZERO:
            self.acquisition_capital_cost = q2(cap_basis - install_sum) if cap_basis >= install_sum else q2(cap_basis)
            self.installation_commissioning_cost = q2(install_sum)
        elif (
            self.fixed_asset_id
            and self.fixed_asset
            and self.fixed_asset.tenant_id == self.tenant_id
            and (self.fixed_asset.acquisition_cost or ZERO) > ZERO
        ):
            self.acquisition_capital_cost = q2(self.fixed_asset.acquisition_cost)
        elif (
            self.operational_asset_id
            and self.operational_asset
            and self.operational_asset.tenant_id == self.tenant_id
            and (self.operational_asset.purchase_cost or ZERO) > ZERO
        ):
            self.acquisition_capital_cost = q2(self.operational_asset.purchase_cost)

        pm_sum = AssetMaintenanceLog.objects.filter(
            tenant_id=self.tenant_id,
            maintenance_type__in=["preventive_service", "calibration", "inspection"],
        ).exclude(status="draft").filter(dual_q).aggregate(total=Sum("total_cost"))["total"] or ZERO
        cm_sum = AssetMaintenanceLog.objects.filter(
            tenant_id=self.tenant_id,
            maintenance_type__in=["corrective_repair", "emergency_breakdown", "overhaul"],
        ).exclude(status="draft").filter(dual_q).aggregate(total=Sum("total_cost"))["total"] or ZERO
        if pm_sum > ZERO:
            self.preventive_maintenance_cost = q2(pm_sum)
        if cm_sum > ZERO:
            self.corrective_maintenance_cost = q2(cm_sum)

        contract_sum = AssetServiceContract.objects.filter(
            tenant_id=self.tenant_id,
            status__in=["active", "expiring_soon", "expired"],
        ).filter(dual_q).aggregate(total=Sum("contract_value"))["total"] or ZERO
        if contract_sum > ZERO:
            self.service_contract_cost = q2(contract_sum)

        energy_sum = AssetEnergyReading.objects.filter(
            tenant_id=self.tenant_id, status="validated"
        ).filter(dual_q).aggregate(total=Sum("total_energy_cost"))["total"] or ZERO
        if energy_sum > ZERO:
            self.energy_utility_cost = q2(energy_sum)

        downtime_sum = AssetDowntimeLog.objects.filter(
            tenant_id=self.tenant_id
        ).exclude(status="cancelled").filter(dual_q).aggregate(total=Sum("total_downtime_cost"))["total"] or ZERO
        if downtime_sum > ZERO:
            self.downtime_opportunity_cost = q2(downtime_sum)

        premium_sum = AssetInsurancePolicy.objects.filter(
            tenant_id=self.tenant_id
        ).exclude(status="cancelled").filter(dual_q).aggregate(total=Sum("annual_premium"))["total"] or ZERO
        fines_sum = ZERO
        if self.operational_asset_id:
            fines_sum = AssetComplianceIncident.objects.filter(
                tenant_id=self.tenant_id, asset_id=self.operational_asset_id
            ).aggregate(total=Sum("fine_assessed"))["total"] or ZERO
        ins_comp_total = premium_sum + fines_sum
        if ins_comp_total > ZERO:
            self.insurance_compliance_cost = q2(ins_comp_total)

        depr_posted = AssetDepreciationSchedule.objects.filter(
            tenant_id=self.tenant_id, status="posted"
        ).filter(dual_q).aggregate(
            max_accum=Max("accumulated_depreciation_after"),
            sum_depr=Sum("depreciation_amount"),
        )
        accum_val = depr_posted["max_accum"] or depr_posted["sum_depr"] or ZERO
        if accum_val > ZERO:
            self.accumulated_depreciation_cost = q2(accum_val)
        elif (
            self.fixed_asset_id
            and self.fixed_asset
            and self.fixed_asset.tenant_id == self.tenant_id
            and (self.fixed_asset.accumulated_depreciation or ZERO) > ZERO
        ):
            self.accumulated_depreciation_cost = q2(self.fixed_asset.accumulated_depreciation)

        salvage_est = AssetDisposalRequest.objects.filter(
            tenant_id=self.tenant_id
        ).exclude(status__in=["rejected", "cancelled"]).filter(dual_q).aggregate(
            total=Max("estimated_residual_value")
        )["total"] or ZERO
        if salvage_est > ZERO:
            self.expected_salvage_value = q2(salvage_est)
        elif (
            self.fixed_asset_id
            and self.fixed_asset
            and self.fixed_asset.tenant_id == self.tenant_id
            and (self.fixed_asset.salvage_value or ZERO) > ZERO
        ):
            self.expected_salvage_value = q2(self.fixed_asset.salvage_value)

        warranty_rec = AssetWarrantyClaim.objects.filter(
            tenant_id=self.tenant_id,
            claim_status__in=["approved", "partially_approved", "settled_closed"],
        ).filter(dual_q).aggregate(total=Sum("approved_amount"))["total"] or ZERO
        ins_rec = AssetInsuranceClaim.objects.filter(
            tenant_id=self.tenant_id,
            claim_status__in=["approved_pending_payout", "settled_paid", "closed"],
        ).filter(dual_q).aggregate(total=Sum("settlement_payout_amount"))["total"] or ZERO

        resale_rec = ZERO
        if self.fixed_asset_id:
            resale_rec = AssetResaleListing.objects.filter(
                tenant_id=self.tenant_id,
                fixed_asset_id=self.fixed_asset_id,
                status__in=["sold", "payment_received", "delivered"],
            ).aggregate(total=Sum("net_sale_proceeds"))["total"] or ZERO
        scrap_rec = AssetScrapSalvage.objects.filter(
            tenant_id=self.tenant_id,
            status__in=["certified_destroyed", "settled"],
        ).filter(dual_q).aggregate(total=Sum("net_salvage_recovery"))["total"] or ZERO

        total_rec = warranty_rec + ins_rec + resale_rec + scrap_rec
        if total_rec > ZERO:
            self.warranty_insurance_recoveries = q2(total_rec)

        if (self.current_replacement_value or ZERO) <= ZERO:
            if (
                self.asset_model_id
                and self.asset_model
                and self.asset_model.tenant_id == self.tenant_id
                and (self.asset_model.estimated_replacement_cost or ZERO) > ZERO
            ):
                self.current_replacement_value = q2(self.asset_model.estimated_replacement_cost)
            elif (self.acquisition_capital_cost or ZERO) > ZERO:
                self.current_replacement_value = q2(self.acquisition_capital_cost)

        if self.status == "draft":
            self.status = "calculated"
        self.recalculate_metrics()
        if save:
            self.save()

    def clean(self):
        errors = {}
        validate_tenant_fks(
            self,
            errors,
            [
                "fixed_asset",
                "operational_asset",
                "asset_category",
                "asset_model",
                "org_unit",
                "analyzed_by",
            ],
        )
        if self.analysis_horizon_years is None or not (1 <= int(self.analysis_horizon_years) <= 50):
            add_field_error(errors, "analysis_horizon_years", "Analysis horizon must be between 1 and 50 years.")
        if self.discount_rate_pct is not None and (
            self.discount_rate_pct < ZERO or self.discount_rate_pct > Decimal("100.00")
        ):
            add_field_error(errors, "discount_rate_pct", "Discount rate must be between 0% and 100%.")
        for fname in (
            "acquisition_capital_cost",
            "installation_commissioning_cost",
            "preventive_maintenance_cost",
            "corrective_maintenance_cost",
            "service_contract_cost",
            "energy_utility_cost",
            "downtime_opportunity_cost",
            "insurance_compliance_cost",
            "accumulated_depreciation_cost",
            "expected_salvage_value",
            "warranty_insurance_recoveries",
            "current_replacement_value",
        ):
            val = getattr(self, fname, None)
            if val is not None and val < ZERO:
                add_field_error(errors, fname, "Monetary amount cannot be negative.")
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if kwargs.get("update_fields") is None:
            self.recalculate_metrics()
        return super().save(*args, **kwargs)
