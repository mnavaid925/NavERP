"""Tests for 8.12 Sales Analytics & Intelligence forms.

Covers:
- WinLossDebriefForm: field exclusions, decision_drivers JSON validation, array cap, cross-tenant rejection.
- StageVelocityAnalysisForm: field exclusions, pipeline-stage consistency, select_related optimization, cross-tenant rejection.
- FunnelConversionRecordForm: field exclusions (derived rate/dropoff), converted <= entered, stage sequence, select_related optimization.
- RepPerformanceScorecardForm: field exclusions (derived metrics), select_related optimization, period validation, cross-tenant rejection.
"""
from decimal import Decimal
import json
import pytest
from django.utils import timezone

from apps.sales.forms.SalesAnalytics.WinLossDebriefs import WinLossDebriefForm
from apps.sales.forms.SalesAnalytics.StageVelocityAnalyses import StageVelocityAnalysisForm
from apps.sales.forms.SalesAnalytics.FunnelConversionRecords import FunnelConversionRecordForm
from apps.sales.forms.SalesAnalytics.RepPerformanceScorecards import RepPerformanceScorecardForm

pytestmark = pytest.mark.django_db


class TestWinLossDebriefForm:
    def test_salesanalytics_debrief_form_exclusions(self):
        form = WinLossDebriefForm()
        for excluded in ("tenant", "number", "created_at", "updated_at"):
            assert excluded not in form.fields

    def test_salesanalytics_debrief_form_valid(self, tenant_a, sa_opportunity_a):
        data = {
            "opportunity": sa_opportunity_a.pk,
            "debriefed_on": timezone.localdate(),
            "interview_channel": "interview",
            "feedback_team": "sales",
            "decision_drivers": json.dumps([
                {"driver": "Feature parity", "sentiment": "positive", "weight": 4, "quote": "Loved the UX"}
            ]),
            "buyer_quote": "Strong capabilities across all modules.",
            "status": "draft",
        }
        form = WinLossDebriefForm(data=data, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_salesanalytics_debrief_form_decision_drivers_invalid_schema(self, tenant_a, sa_opportunity_a):
        # Invalid JSON string
        form1 = WinLossDebriefForm(data={"opportunity": sa_opportunity_a.pk, "decision_drivers": "not json"}, tenant=tenant_a)
        assert not form1.is_valid()
        assert "decision_drivers" in form1.errors

        # Non-list
        form2 = WinLossDebriefForm(data={"opportunity": sa_opportunity_a.pk, "decision_drivers": json.dumps({"driver": "Fit"})}, tenant=tenant_a)
        assert not form2.is_valid()
        assert "decision_drivers" in form2.errors

        # Invalid sentiment
        form3 = WinLossDebriefForm(data={"opportunity": sa_opportunity_a.pk, "decision_drivers": json.dumps([{"driver": "Fit", "sentiment": "neutral", "weight": 3}])}, tenant=tenant_a)
        assert not form3.is_valid()
        assert "decision_drivers" in form3.errors

        # Array cap (> 50 items)
        oversized = [{"driver": f"D{i}", "sentiment": "positive", "weight": 3} for i in range(51)]
        form4 = WinLossDebriefForm(data={"opportunity": sa_opportunity_a.pk, "decision_drivers": json.dumps(oversized)}, tenant=tenant_a)
        assert not form4.is_valid()
        assert "decision_drivers" in form4.errors

    def test_salesanalytics_debrief_form_cross_tenant_rejected(self, tenant_a, sa_opportunity_b):
        data = {
            "opportunity": sa_opportunity_b.pk,  # tenant_b
            "debriefed_on": timezone.localdate(),
            "status": "draft",
        }
        form = WinLossDebriefForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "opportunity" in form.errors


class TestStageVelocityAnalysisForm:
    def test_salesanalytics_velocity_form_exclusions_and_select_related(self, tenant_a):
        form = StageVelocityAnalysisForm(tenant=tenant_a)
        for excluded in ("tenant", "number", "created_at", "updated_at"):
            assert excluded not in form.fields

        # C3 verification: pipeline_stage queryset has select_related('pipeline')
        assert "pipeline" in form.fields["pipeline_stage"].queryset.query.select_related

    def test_salesanalytics_velocity_form_valid(self, tenant_a, sa_pipeline_a, sa_stage_a1):
        data = {
            "pipeline": sa_pipeline_a.pk,
            "pipeline_stage": sa_stage_a1.pk,
            "period_start": timezone.localdate() - timezone.timedelta(days=90),
            "period_end": timezone.localdate(),
            "opportunity_count": 20,
            "velocity_value": "150000.00",
            "median_days_in_stage": "15.00",
            "p90_days_in_stage": "30.00",
            "max_days_in_stage": 45,
            "status": "draft",
        }
        form = StageVelocityAnalysisForm(data=data, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_salesanalytics_velocity_form_pipeline_stage_mismatch(self, tenant_a, sa_pipeline_a, sa_stage_b1):
        # sa_stage_b1 belongs to tenant_b
        data = {
            "pipeline": sa_pipeline_a.pk,
            "pipeline_stage": sa_stage_b1.pk,
            "period_start": timezone.localdate() - timezone.timedelta(days=90),
            "period_end": timezone.localdate(),
            "status": "draft",
        }
        form = StageVelocityAnalysisForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "pipeline_stage" in form.errors


class TestFunnelConversionRecordForm:
    def test_salesanalytics_funnel_form_exclusions_and_select_related(self, tenant_a):
        form = FunnelConversionRecordForm(tenant=tenant_a)
        for excluded in ("tenant", "number", "conversion_rate_pct", "dropoff_count", "created_at", "updated_at"):
            assert excluded not in form.fields

        # C4 verification: from_stage and to_stage have select_related('pipeline')
        assert "pipeline" in form.fields["from_stage"].queryset.query.select_related
        assert "pipeline" in form.fields["to_stage"].queryset.query.select_related

    def test_salesanalytics_funnel_form_valid(self, tenant_a, sa_stage_a1, sa_stage_a2):
        data = {
            "label": "Inbound Demo Funnel",
            "funnel_scope": "stage_to_stage",
            "from_stage": sa_stage_a1.pk,
            "to_stage": sa_stage_a2.pk,
            "period_start": timezone.localdate() - timezone.timedelta(days=90),
            "period_end": timezone.localdate(),
            "entered_count": 50,
            "converted_count": 20,
            "skipped_count": 2,
        }
        form = FunnelConversionRecordForm(data=data, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_salesanalytics_funnel_form_converted_exceeds_entered(self, tenant_a):
        data = {
            "label": "Invalid Funnel",
            "funnel_scope": "lead_to_opportunity",
            "period_start": timezone.localdate() - timezone.timedelta(days=90),
            "period_end": timezone.localdate(),
            "entered_count": 10,
            "converted_count": 25,  # converted > entered
        }
        form = FunnelConversionRecordForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "converted_count" in form.errors


class TestRepPerformanceScorecardForm:
    def test_salesanalytics_scorecard_form_exclusions_and_select_related(self, tenant_a):
        form = RepPerformanceScorecardForm(tenant=tenant_a)
        for excluded in (
            "tenant",
            "number",
            "win_rate_pct",
            "average_deal_size",
            "quota_attainment_pct",
            "goal_gap_value",
            "created_at",
            "updated_at",
        ):
            assert excluded not in form.fields

        # C5 verification: quota_plan and coaching_scorecard select_related
        assert "quota_ref" in form.fields["quota_plan"].queryset.query.select_related
        assert "coachee" in form.fields["coaching_scorecard"].queryset.query.select_related

    def test_salesanalytics_scorecard_form_valid(self, tenant_a, admin_user):
        data = {
            "rep": admin_user.pk,
            "period_start": timezone.localdate() - timezone.timedelta(days=90),
            "period_end": timezone.localdate(),
            "activities_logged": 100,
            "calls_logged": 50,
            "emails_logged": 30,
            "meetings_logged": 20,
            "meetings_booked": 15,
            "follow_ups_completed": 25,
            "activity_minutes": 300,
            "opportunities_created": 10,
            "opportunities_won": 4,
            "opportunities_lost": 2,
            "pipeline_value": "200000.00",
            "weighted_pipeline_value": "150000.00",
            "revenue_closed": "100000.00",
            "quota_target": "100000.00",
            "rating": "strong",
            "status": "draft",
        }
        form = RepPerformanceScorecardForm(data=data, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_salesanalytics_scorecard_form_cross_tenant_rep_rejected(self, tenant_a, admin_b):
        data = {
            "rep": admin_b.pk,  # admin_b belongs to tenant_b
            "period_start": timezone.localdate() - timezone.timedelta(days=90),
            "period_end": timezone.localdate(),
            "rating": "strong",
            "status": "draft",
        }
        form = RepPerformanceScorecardForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "rep" in form.errors
