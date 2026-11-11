from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Avg, Count, Q, Sum

from apps.assets.models._base import TenantNumbered
from apps.assets.models.AssetAnalytics._validators import (
    ZERO,
    add_field_error,
    cap_decimal,
    q2,
    validate_tenant_fks,
)


class AssetExecutiveScorecard(TenantNumbered):
    """
    Executive Reporting & KPI Scorecard [AKPI-].
    Captures board-level portfolio KPIs (Asset ROI, Maintenance Cost to RAV %, Planned Ratio,
    FCI %, CapEx Utilization, OEE/Availability, Compliance Audit Pass Rate, Risk Exposure, and Unfunded Backlog)
    with automated RAG grading and immutable snapshot lock once published or board-approved.
    """

    NUMBER_PREFIX = "AKPI"

    PERIOD_TYPE_CHOICES = [
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("annual", "Annual"),
        ("ytd", "Year-to-Date"),
        ("adhoc", "Ad-Hoc Executive Brief"),
    ]

    RAG_STATUS_CHOICES = [
        ("green", "On Target (Green)"),
        ("amber", "Watch / Variance (Amber)"),
        ("red", "Action Required (Red)"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
        ("board_approved", "Board Approved"),
        ("archived", "Archived"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "published": "badge-info",
        "board_approved": "badge-green",
        "archived": "badge-muted",
    }

    RAG_STATUS_CSS = {
        "green": "badge-green",
        "amber": "badge-amber",
        "red": "badge-red",
    }

    title = models.CharField(max_length=255)
    period_type = models.CharField(
        max_length=15,
        choices=PERIOD_TYPE_CHOICES,
        default="quarterly",
    )
    period_start = models.DateField()
    period_end = models.DateField()

    org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_executive_scorecards",
    )
    asset_category = models.ForeignKey(
        "assets.AssetCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_executive_scorecards",
    )
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_executive_scorecards",
    )
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prepared_asset_scorecards",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_asset_scorecards",
    )

    rag_status = models.CharField(
        max_length=10,
        choices=RAG_STATUS_CHOICES,
        default="green",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
    )

    # Valuation & ROI KPIs
    total_asset_count = models.PositiveIntegerField(default=0)
    gross_replacement_value = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    total_net_book_value = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    total_maintenance_spend = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    annual_asset_return_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    asset_roi_pct = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0.00"))
    target_asset_roi_pct = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("12.00"))

    # Cost & Reliability KPIs
    maintenance_cost_to_rav_pct = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0.00"))
    target_mcr_pct = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("3.50"))
    planned_maintenance_ratio_pct = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    portfolio_fci_pct = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0.00"))
    capex_budget_utilization_pct = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    fleet_availability_pct = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    portfolio_oee_pct = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))

    # Compliance & Risk KPIs
    compliance_audit_pass_rate_pct = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    target_compliance_rate_pct = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("95.00"))
    open_compliance_incidents = models.PositiveIntegerField(default=0)
    total_risk_exposure_amount = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    unfunded_replacement_backlog = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))

    executive_summary = models.TextField(blank=True)

    class Meta:
        ordering = ["-period_end", "-id"]
        verbose_name = "Asset Executive Scorecard"
        verbose_name_plural = "Asset Executive Scorecards"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_akpi_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_akpi_ten_stat"),
            models.Index(fields=["tenant", "period_type"], name="idx_akpi_ten_per"),
            models.Index(fields=["tenant", "rag_status"], name="idx_akpi_ten_rag"),
            models.Index(fields=["tenant", "period_end"], name="idx_akpi_ten_end"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"

    @property
    def is_locked(self):
        return self.status in ("published", "board_approved", "archived")

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def rag_status_badge_class(self):
        return self.RAG_STATUS_CSS.get(self.rag_status, "badge-slate")

    def compute_from_live_portfolio(self, save=True):
        """
        Compute executive KPIs from live tenant operational, financial, maintenance,
        replacement planning, risk, and compliance records while enforcing draft lock.
        """
        if self.is_locked:
            raise ValidationError(
                "Published, board-approved, or archived scorecards are locked and cannot be recalculated."
            )

        from apps.accounting.models.FixedAssets.FixedAssetsRegister import FixedAsset
        from apps.assets.models.AssetAnalytics.AssetLifecycleCostAnalyses import (
            AssetLifecycleCostAnalysis,
        )
        from apps.assets.models.AssetAnalytics.AssetReplacementPlans import (
            AssetReplacementPlan,
        )
        from apps.assets.models.AssetCompliance.AssetComplianceAudits import (
            AssetComplianceAudit,
        )
        from apps.assets.models.AssetCompliance.AssetComplianceIncidents import (
            AssetComplianceIncident,
        )
        from apps.assets.models.AssetDisposal.AssetResaleListings import AssetResaleListing
        from apps.assets.models.AssetDisposal.AssetScrapSalvages import AssetScrapSalvage
        from apps.assets.models.AssetMaintenance.AssetMaintenanceLogs import (
            AssetMaintenanceLog,
        )
        from apps.assets.models.AssetPerformance.AssetOeeRecords import AssetOeeRecord
        from apps.assets.models.AssetProcurement.AssetCapitalizations import (
            AssetCapitalization,
        )
        from apps.assets.models.AssetRisk.AssetRiskRegisters import AssetRiskRegister
        from apps.assets.models.AssetWarrantyInsurance.AssetInsuranceClaims import (
            AssetInsuranceClaim,
        )
        from apps.assets.models.AssetWarrantyInsurance.AssetWarrantyClaims import (
            AssetWarrantyClaim,
        )
        from apps.scm.models.AssetManagement.Assets import Asset

        tid = self.tenant_id

        scm_qs = Asset.objects.filter(tenant_id=tid).exclude(status__in=["retired", "disposed"])
        if self.org_unit_id:
            scm_qs = scm_qs.filter(org_unit_id=self.org_unit_id)

        fa_qs = FixedAsset.objects.filter(tenant_id=tid).exclude(status="disposed")
        if self.org_unit_id:
            linked_fa_ids = list(
                scm_qs.exclude(fixed_asset_id__isnull=True).values_list("fixed_asset_id", flat=True)
            )
            fa_qs = fa_qs.filter(pk__in=linked_fa_ids)

        scm_count = scm_qs.count()
        fa_agg = fa_qs.aggregate(
            cnt=Count("id"),
            acq=Sum("acquisition_cost"),
            dep=Sum("accumulated_depreciation"),
        )
        self.total_asset_count = scm_count if scm_count > 0 else (fa_agg["cnt"] or 0)
        fa_acq = fa_agg["acq"] or ZERO
        fa_dep = fa_agg["dep"] or ZERO
        self.total_net_book_value = q2(max(ZERO, fa_acq - fa_dep))

        plan_qs = AssetReplacementPlan.objects.filter(tenant_id=tid).exclude(
            status__in=["executed", "cancelled"]
        )
        alcc_qs = AssetLifecycleCostAnalysis.objects.filter(tenant_id=tid).exclude(status="archived")
        if self.org_unit_id:
            plan_qs = plan_qs.filter(org_unit_id=self.org_unit_id)
            alcc_qs = alcc_qs.filter(org_unit_id=self.org_unit_id)
        if self.asset_category_id:
            plan_qs = plan_qs.filter(asset_category_id=self.asset_category_id)
            alcc_qs = alcc_qs.filter(asset_category_id=self.asset_category_id)

        plan_agg = plan_qs.aggregate(
            crv=Sum("current_replacement_value"),
            deferred=Sum("deferred_maintenance_cost"),
            planned_capex=Sum("inflation_adjusted_cost"),
            unfunded=Sum("inflation_adjusted_cost", filter=Q(funding_status="unfunded")),
        )
        alcc_crv = alcc_qs.aggregate(crv=Sum("current_replacement_value"))["crv"] or ZERO

        grv = plan_agg["crv"] or alcc_crv or fa_acq or ZERO
        self.gross_replacement_value = q2(grv)
        self.unfunded_replacement_backlog = q2(plan_agg["unfunded"] or ZERO)
        deferred_total = plan_agg["deferred"] or ZERO
        self.portfolio_fci_pct = (
            cap_decimal((deferred_total / grv) * Decimal("100.00")) if grv > ZERO else ZERO
        )

        maint_qs = AssetMaintenanceLog.objects.filter(tenant_id=tid).exclude(status="draft")
        if self.period_start and self.period_end:
            maint_qs = maint_qs.filter(service_date__range=(self.period_start, self.period_end))
        if self.org_unit_id:
            maint_qs = maint_qs.filter(operational_asset__org_unit_id=self.org_unit_id)

        maint_agg = maint_qs.aggregate(
            total_cost=Sum("total_cost"),
            total_cnt=Count("id"),
            pm_cnt=Count("id", filter=Q(maintenance_type__in=["preventive_service", "calibration", "inspection"])),
        )
        maint_spend = maint_agg["total_cost"] or ZERO
        self.total_maintenance_spend = q2(maint_spend)
        self.maintenance_cost_to_rav_pct = (
            cap_decimal((maint_spend / grv) * Decimal("100.00")) if grv > ZERO else ZERO
        )
        m_cnt = maint_agg["total_cnt"] or 0
        self.planned_maintenance_ratio_pct = (
            cap_decimal((Decimal(maint_agg["pm_cnt"] or 0) / Decimal(m_cnt)) * Decimal("100.00"), max_abs=Decimal("100.00"))
            if m_cnt > 0
            else ZERO
        )

        # Recoveries & return basis (preserve explicit budget/return override if > 0)
        if (self.annual_asset_return_amount or ZERO) <= ZERO:
            resale_net = AssetResaleListing.objects.filter(
                tenant_id=tid, status__in=["sold", "payment_received", "delivered"]
            ).aggregate(total=Sum("net_sale_proceeds"))["total"] or ZERO
            scrap_net = AssetScrapSalvage.objects.filter(
                tenant_id=tid, status__in=["certified_destroyed", "settled"]
            ).aggregate(total=Sum("net_salvage_recovery"))["total"] or ZERO
            warr_net = AssetWarrantyClaim.objects.filter(
                tenant_id=tid, claim_status__in=["approved", "partially_approved", "settled_closed"]
            ).aggregate(total=Sum("approved_amount"))["total"] or ZERO
            ins_net = AssetInsuranceClaim.objects.filter(
                tenant_id=tid, claim_status__in=["approved_pending_payout", "settled_paid", "closed"]
            ).aggregate(total=Sum("settlement_payout_amount"))["total"] or ZERO
            self.annual_asset_return_amount = q2(resale_net + scrap_net + warr_net + ins_net)

        if self.total_net_book_value > ZERO:
            self.asset_roi_pct = cap_decimal(
                (self.annual_asset_return_amount / self.total_net_book_value) * Decimal("100.00")
            )
        else:
            self.asset_roi_pct = ZERO

        cap_qs = AssetCapitalization.objects.filter(tenant_id=tid, status="capitalized")
        if self.period_start and self.period_end:
            cap_qs = cap_qs.filter(in_service_date__range=(self.period_start, self.period_end))
        cap_actual = cap_qs.aggregate(total=Sum("total_cost_basis"))["total"] or ZERO
        planned_capex = plan_agg["planned_capex"] or ZERO
        if planned_capex > ZERO:
            self.capex_budget_utilization_pct = cap_decimal(
                (cap_actual / planned_capex) * Decimal("100.00"),
                max_abs=Decimal("999.99"),
            )
        else:
            self.capex_budget_utilization_pct = ZERO

        oee_qs = AssetOeeRecord.objects.filter(tenant_id=tid)
        if self.period_start and self.period_end:
            oee_qs = oee_qs.filter(record_date__range=(self.period_start, self.period_end))
        if self.org_unit_id:
            oee_qs = oee_qs.filter(operational_asset__org_unit_id=self.org_unit_id)
        oee_agg = oee_qs.aggregate(
            avail=Avg("availability_percentage"),
            oee=Avg("oee_percentage"),
        )
        self.fleet_availability_pct = cap_decimal(oee_agg["avail"] or ZERO, max_abs=Decimal("100.00"))
        self.portfolio_oee_pct = cap_decimal(oee_agg["oee"] or ZERO, max_abs=Decimal("100.00"))

        audit_qs = AssetComplianceAudit.objects.filter(tenant_id=tid).exclude(status="cancelled")
        if self.period_start and self.period_end:
            audit_qs = audit_qs.filter(audit_date__range=(self.period_start, self.period_end))
        if self.org_unit_id:
            audit_qs = audit_qs.filter(asset__org_unit_id=self.org_unit_id)
        audit_agg = audit_qs.aggregate(
            total_cp=Sum("total_checkpoints"),
            passed_cp=Sum("passed_checkpoints"),
        )
        tot_cp = audit_agg["total_cp"] or 0
        if tot_cp > 0:
            self.compliance_audit_pass_rate_pct = cap_decimal(
                (Decimal(audit_agg["passed_cp"] or 0) / Decimal(tot_cp)) * Decimal("100.00"),
                max_abs=Decimal("100.00"),
            )
        else:
            self.compliance_audit_pass_rate_pct = ZERO

        inc_qs = AssetComplianceIncident.objects.filter(tenant_id=tid).exclude(
            status__in=["resolved", "closed"]
        )
        if self.org_unit_id:
            inc_qs = inc_qs.filter(asset__org_unit_id=self.org_unit_id)
        self.open_compliance_incidents = inc_qs.count()

        risk_qs = AssetRiskRegister.objects.filter(tenant_id=tid).exclude(status="closed")
        if self.org_unit_id:
            risk_qs = risk_qs.filter(asset__org_unit_id=self.org_unit_id)
        if self.asset_category_id:
            risk_qs = risk_qs.filter(category_id=self.asset_category_id)
        self.total_risk_exposure_amount = q2(
            risk_qs.aggregate(total=Sum("financial_exposure_amount"))["total"] or ZERO
        )

        # Automated RAG grading against target thresholds
        misses = 0
        if self.asset_roi_pct < (self.target_asset_roi_pct or ZERO):
            misses += 1
        if self.maintenance_cost_to_rav_pct > (self.target_mcr_pct or Decimal("100.00")):
            misses += 1
        if tot_cp > 0 and self.compliance_audit_pass_rate_pct < (self.target_compliance_rate_pct or ZERO):
            misses += 1
        if misses >= 2 or self.open_compliance_incidents > 2:
            self.rag_status = "red"
        elif misses == 1 or self.open_compliance_incidents > 0:
            self.rag_status = "amber"
        else:
            self.rag_status = "green"

        if save:
            self.save()

    def clean(self):
        errors = {}
        validate_tenant_fks(
            self,
            errors,
            ["org_unit", "asset_category", "prepared_by", "approved_by"],
        )
        if self.period_start and self.period_end and self.period_end < self.period_start:
            add_field_error(errors, "period_end", "Period end date cannot precede period start date.")
        if self.target_mcr_pct is not None and (
            self.target_mcr_pct < ZERO or self.target_mcr_pct > Decimal("100.00")
        ):
            add_field_error(errors, "target_mcr_pct", "Target MCR % must be between 0% and 100%.")
        if self.target_compliance_rate_pct is not None and (
            self.target_compliance_rate_pct < ZERO or self.target_compliance_rate_pct > Decimal("100.00")
        ):
            add_field_error(
                errors, "target_compliance_rate_pct", "Target compliance pass rate must be between 0% and 100%."
            )
        if errors:
            raise ValidationError(errors)
