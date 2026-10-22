"""Tests for 8.12 Sales Analytics & Intelligence models.

Covers:
- WinLossDebrief invariants, auto-numbering, choices, clean validation.
- StageVelocityAnalysis invariants, auto-numbering, bottleneck_display, choices, clean validation.
- FunnelConversionRecord invariants, derived rate/dropoff computation, clamping, clean validation.
- RepPerformanceScorecard invariants, derived attainment/win-rate/deal-size/goal-gap, clamping.
"""
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.sales.models.SalesAnalytics.WinLossDebriefs import (
    DEBRIEF_STATUS_CHOICES,
    FEEDBACK_TEAM_CHOICES,
    INTERVIEW_CHANNEL_CHOICES,
    WinLossDebrief,
)
from apps.sales.models.SalesAnalytics.StageVelocityAnalyses import (
    VELOCITY_STATUS_CHOICES,
    StageVelocityAnalysis,
)
from apps.sales.models.SalesAnalytics.FunnelConversionRecords import (
    FUNNEL_SCOPE_CHOICES,
    FunnelConversionRecord,
)
from apps.sales.models.SalesAnalytics.RepPerformanceScorecards import (
    SCORECARD_RATING_CHOICES,
    SCORECARD_STATUS_CHOICES,
    RepPerformanceScorecard,
)

pytestmark = pytest.mark.django_db


class TestSalesAnalyticsModels:
    def test_salesanalytics_win_loss_debrief_creation_and_numbering(self, tenant_a, sa_opportunity_a):
        debrief = WinLossDebrief.objects.create(
            tenant=tenant_a,
            opportunity=sa_opportunity_a,
            debriefed_on=timezone.localdate(),
            interview_channel="interview",
            buyer_quote="Pricing was slightly high but product fit was top-notch.",
            status="submitted",
        )
        assert debrief.number.startswith("WLA-")
        assert str(debrief) == f"{debrief.number} · {sa_opportunity_a}"
        assert debrief.tenant == tenant_a
        assert debrief.status in dict(DEBRIEF_STATUS_CHOICES)
        assert debrief.interview_channel in dict(INTERVIEW_CHANNEL_CHOICES)

    def test_salesanalytics_win_loss_debrief_cross_tenant_clean_rejected(
        self, tenant_a, tenant_b, sa_opportunity_a, sa_opportunity_b
    ):
        debrief = WinLossDebrief(
            tenant=tenant_a,
            opportunity=sa_opportunity_b,  # belongs to tenant_b!
            debriefed_on=timezone.localdate(),
        )
        with pytest.raises(ValidationError):
            debrief.clean()

    def test_salesanalytics_stage_velocity_analysis_creation_and_properties(
        self, tenant_a, sa_pipeline_a, sa_stage_a1
    ):
        vca = StageVelocityAnalysis.objects.create(
            tenant=tenant_a,
            pipeline=sa_pipeline_a,
            pipeline_stage=sa_stage_a1,
            period_start=timezone.localdate() - timezone.timedelta(days=90),
            period_end=timezone.localdate(),
            opportunity_count=15,
            median_days_in_stage=Decimal("12.50"),
            p90_days_in_stage=Decimal("24.00"),
            is_bottleneck=True,
            bottleneck_rank=1,
            status="reviewed",
        )
        assert vca.number.startswith("VCA-")
        assert "Discovery" in str(vca)
        assert vca.bottleneck_display == "Bottleneck"
        assert vca.status in dict(VELOCITY_STATUS_CHOICES)

        vca.is_bottleneck = False
        assert vca.bottleneck_display == "Normal"

    def test_salesanalytics_stage_velocity_cross_tenant_clean_rejected(
        self, tenant_a, sa_pipeline_a, sa_stage_b1
    ):
        vca = StageVelocityAnalysis(
            tenant=tenant_a,
            pipeline=sa_pipeline_a,
            pipeline_stage=sa_stage_b1,  # stage belongs to tenant_b
            period_start=timezone.localdate() - timezone.timedelta(days=90),
            period_end=timezone.localdate(),
        )
        with pytest.raises(ValidationError):
            vca.clean()

    def test_salesanalytics_funnel_conversion_derived_calculations_and_clamping(self, tenant_a):
        fnl = FunnelConversionRecord.objects.create(
            tenant=tenant_a,
            label="Enterprise Inbound Funnel",
            funnel_scope="lead_to_opportunity",
            period_start=timezone.localdate() - timezone.timedelta(days=90),
            period_end=timezone.localdate(),
            entered_count=200,
            converted_count=50,
            skipped_count=10,
        )
        assert fnl.number.startswith("FNL-")
        # 50 / 200 * 100 = 25.00%
        assert fnl.conversion_rate_pct == Decimal("25.00")
        # 200 - 50 = 150 dropoff
        assert fnl.dropoff_count == 150
        assert fnl.funnel_scope in dict(FUNNEL_SCOPE_CHOICES)

        # Clamping guard test
        fnl.entered_count = 1
        fnl.converted_count = 100
        fnl.save()
        # Clamped to 999.99 instead of overflowing DECIMAL(5,2)
        assert fnl.conversion_rate_pct == Decimal("999.99")

    def test_salesanalytics_funnel_conversion_stage_sequence_validation(
        self, tenant_a, sa_pipeline_a, sa_stage_a1, sa_stage_a2
    ):
        # sa_stage_a1 is sequence 10, sa_stage_a2 is sequence 20
        # Valid stage_to_stage
        fnl_valid = FunnelConversionRecord(
            tenant=tenant_a,
            label="Valid Stage Funnel",
            funnel_scope="stage_to_stage",
            from_stage=sa_stage_a1,
            to_stage=sa_stage_a2,
            period_start=timezone.localdate() - timezone.timedelta(days=90),
            period_end=timezone.localdate(),
            entered_count=10,
            converted_count=5,
        )
        fnl_valid.clean()  # should not raise

        # Invalid stage_to_stage: reversed sequence
        fnl_invalid = FunnelConversionRecord(
            tenant=tenant_a,
            label="Invalid Stage Funnel",
            funnel_scope="stage_to_stage",
            from_stage=sa_stage_a2,  # sequence 20
            to_stage=sa_stage_a1,    # sequence 10
            period_start=timezone.localdate() - timezone.timedelta(days=90),
            period_end=timezone.localdate(),
            entered_count=10,
            converted_count=5,
        )
        with pytest.raises(ValidationError):
            fnl_invalid.clean()

    def test_salesanalytics_rep_performance_scorecard_derived_metrics_and_clamping(
        self, tenant_a, admin_user
    ):
        rps = RepPerformanceScorecard.objects.create(
            tenant=tenant_a,
            rep=admin_user,
            period_start=timezone.localdate() - timezone.timedelta(days=90),
            period_end=timezone.localdate(),
            opportunities_won=5,
            opportunities_lost=5,
            revenue_closed=Decimal("250000.00"),
            quota_target=Decimal("200000.00"),
            rating="outstanding",
            status="approved",
        )
        assert rps.number.startswith("RPS-")
        # Win rate: 5 / (5 + 5) * 100 = 50.00%
        assert rps.win_rate_pct == Decimal("50.00")
        # Avg deal size: 250000 / 5 = 50000.00
        assert rps.average_deal_size == Decimal("50000.00")
        # Attainment: 250000 / 200000 * 100 = 125.00%
        assert rps.quota_attainment_pct == Decimal("125.00")
        # Goal gap: target - actual = 200000 - 250000 = -50000.00 (exceeded)
        assert rps.goal_gap_value == Decimal("-50000.00")
        assert rps.rating in dict(SCORECARD_RATING_CHOICES)
        assert rps.status in dict(SCORECARD_STATUS_CHOICES)

        # Clamping test with tiny quota_target
        rps.quota_target = Decimal("0.01")
        rps.save()
        assert rps.quota_attainment_pct == Decimal("9999.99")
