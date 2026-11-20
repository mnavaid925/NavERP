"""Unit and functional view tests for Quality Management Sub-module 12.14: Management Review & Quality Planning.

Covers all 5 functional areas / entities:
1. QualityPlanningDashboard:
   - quality_planning_dashboard: returns 200, validates all KPI context keys and collections.
2. QualityObjective Views:
   - quality_objective_list: normal render, search, filters (category, status, rag_status, owner, year), junk params.
   - quality_objective_create: GET form, POST 302 creation and redirect to detail.
   - quality_objective_detail: GET 200, contract context keys (objective, variance, is_achieved, evaluate_form, can_evaluate).
   - quality_objective_edit: GET form, POST 302 update.
   - quality_objective_evaluate: POST 302 performance re-evaluation, GET 405 rejection, draft status evaluation blocking.
   - quality_objective_delete: POST 302 deletion, GET 405 rejection.
   - quality_objective_export_csv: GET 200 text/csv export.
3. ManagementReview Views:
   - management_review_list: normal render, filters (cadence, status, suitability, sponsor, q), junk params.
   - management_review_create: GET form, POST 302 creation and redirect to detail.
   - management_review_detail: GET 200, contract context keys (review, inputs, actions, approve_form, can_start, can_draft_minutes, can_approve).
   - management_review_edit: GET form, POST 302 update, approved review editing blocking.
   - management_review_start: POST 302 transition to meeting_active, GET 405 rejection.
   - management_review_draft_minutes: GET form, POST 302 minutes recording & pending_approval status update, unstarted meeting blocking.
   - management_review_approve: POST 302 electronic signature record creation & approval, pending suitability blocking, GET 405 rejection.
   - management_review_cancel: POST 302 cancellation, approved review cancellation blocking.
   - management_review_delete: POST 302 deletion, approved review deletion blocking.
   - management_review_export_pdf (dossier): GET 200 dossier template rendering.
   - management_review_export_csv: GET 200 text/csv export.
4. ManagementReviewInput Views:
   - management_review_input_list: normal render, search, filters, junk params.
   - management_review_input_create: GET without ?review_id=, GET with ?review_id=, POST 302 creation, approved review input blocking.
   - management_review_input_detail: GET 200, context keys (review_input, can_present, can_accept).
   - management_review_input_edit: GET form, POST 302 update.
   - management_review_input_present: POST 302 transition to presented, GET 405 rejection.
   - management_review_input_accept: POST 302 transition to accepted, GET 405 rejection.
   - management_review_input_delete: POST 302 deletion.
   - management_review_input_export_csv: GET 200 text/csv export.
5. ManagementReviewAction Views:
   - management_review_action_list: normal render, filters (action_type, priority, status, review, assignee, q), junk params.
   - management_review_action_create: GET without ?review_id=, GET with ?review_id=, POST 302 creation, approved review action blocking.
   - management_review_action_detail: GET 200, context keys (action_item, is_overdue, days_open, can_start, can_complete, can_verify, can_escalate_capa, complete_form, verify_form).
   - management_review_action_edit: GET form, POST 302 update.
   - management_review_action_start: POST 302 transition to in_progress, GET 405 rejection.
   - management_review_action_complete: POST 302 transition to pending_verification, GET 405 rejection.
   - management_review_action_verify: POST 302 transition to completed with verified_by sign-off, GET 405 rejection.
   - management_review_action_escalate_capa: POST 302 formal CapaInvestigation creation & linking, GET 405 rejection.
   - management_review_action_delete: POST 302 deletion, completed action deletion blocking.
   - management_review_action_export_csv: GET 200 text/csv export.
"""

from datetime import date, timedelta
from decimal import Decimal
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.quality.models.CapaManagement.CapaInvestigations import CapaInvestigation
from apps.quality.models.DocumentControl.ElectronicSignatures import ElectronicSignatureRecord
from apps.quality.models.ManagementReview.ManagementReviewActions import ManagementReviewAction
from apps.quality.models.ManagementReview.ManagementReviewInputs import ManagementReviewInput
from apps.quality.models.ManagementReview.ManagementReviews import ManagementReview
from apps.quality.models.ManagementReview.QualityObjectives import QualityObjective

pytestmark = pytest.mark.django_db


def _managementreview_relative_date(days: int) -> date:
    """Helper returning a date offset from today."""
    return timezone.now().date() + timedelta(days=days)


# ==============================================================================
# 1. QUALITY PLANNING DASHBOARD
# ==============================================================================

def test_managementreview_dashboard_view(
    client_a,
    quality_objective_a,
    management_review_a,
    management_review_action_a,
):
    """Verify QualityPlanningDashboard view returns 200 and passes all contracted context keys."""
    url = reverse("quality:quality_planning_dashboard")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "quality/managementreview/quality_planning_dashboard.html" in [t.name for t in resp.templates]

    ctx = resp.context
    # Quality Objectives KPI contract keys
    assert "total_objectives" in ctx
    assert "objectives_on_track" in ctx
    assert "objectives_at_risk" in ctx
    assert "objectives_behind" in ctx
    assert "objectives_achieved" in ctx
    assert "objective_achievement_rate" in ctx
    assert "objectives_by_category" in ctx
    assert "rag_distribution" in ctx

    assert ctx["total_objectives"] >= 1
    assert isinstance(ctx["rag_distribution"], dict)
    assert "green" in ctx["rag_distribution"]
    assert "amber" in ctx["rag_distribution"]
    assert "red" in ctx["rag_distribution"]

    # Management Reviews KPI contract keys
    assert "total_reviews" in ctx
    assert "scheduled_reviews" in ctx
    assert "reviews_approved_this_year" in ctx
    assert "upcoming_reviews" in ctx
    assert ctx["total_reviews"] >= 1
    assert ctx["scheduled_reviews"] >= 1

    # Review Actions KPI contract keys
    assert "total_actions" in ctx
    assert "open_actions" in ctx
    assert "overdue_actions" in ctx
    assert "completed_actions" in ctx
    assert "action_closure_rate" in ctx
    assert "urgent_actions" in ctx
    assert ctx["total_actions"] >= 1
    assert ctx["open_actions"] >= 1

    # Assert rendered content displays review title
    assert b"Executive QMS Suitability" in resp.content


# ==============================================================================
# 2. QUALITY OBJECTIVE VIEWS
# ==============================================================================

def test_managementreview_objective_list_view(client_a, quality_objective_a):
    """Verify QualityObjective list returns 200 and populates expected context keys and KPIs."""
    url = reverse("quality:quality_objective_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    ctx = resp.context
    assert "objectives" in ctx
    assert "page_obj" in ctx
    assert "total_count" in ctx
    assert "on_track_count" in ctx
    assert "at_risk_count" in ctx
    assert "behind_count" in ctx
    assert "category_choices" in ctx
    assert "status_choices" in ctx
    assert "rag_choices" in ctx
    assert "org_units" in ctx
    assert "owners" in ctx

    assert ctx["total_count"] >= 1
    assert quality_objective_a.number.encode() in resp.content
    assert b"Reduce Customer RMA Incident Rate" in resp.content


def test_managementreview_objective_list_filters_and_search(
    client_a,
    quality_objective_a,
    admin_user,
    quality_department,
):
    """Verify QualityObjective list search, filters, and junk query parameters."""
    url = reverse("quality:quality_objective_list")

    # Search by text matching title
    resp_search = client_a.get(url, {"q": "RMA Incident"})
    assert resp_search.status_code == 200
    assert quality_objective_a.number.encode() in resp_search.content

    # Search with no match
    resp_nomatch = client_a.get(url, {"q": "NonExistentObjectivePhraseXYZ"})
    assert resp_nomatch.status_code == 200
    assert quality_objective_a.number.encode() not in resp_nomatch.content

    # Filter by category
    resp_cat_match = client_a.get(url, {"category": "product_quality"})
    assert resp_cat_match.status_code == 200
    assert quality_objective_a.number.encode() in resp_cat_match.content

    resp_cat_mismatch = client_a.get(url, {"category": "esg_sustainability"})
    assert resp_cat_mismatch.status_code == 200
    assert quality_objective_a.number.encode() not in resp_cat_mismatch.content

    # Filter by status and rag_status
    resp_status = client_a.get(url, {"status": "achieved", "rag_status": "green"})
    assert resp_status.status_code == 200
    assert quality_objective_a.number.encode() in resp_status.content

    # Filter by owner and year
    resp_owner_year = client_a.get(
        url,
        {
            "owner": str(admin_user.pk),
            "year": str(quality_objective_a.period_year),
            "org_unit": str(quality_department.pk),
        },
    )
    assert resp_owner_year.status_code == 200
    assert quality_objective_a.number.encode() in resp_owner_year.content

    # Junk parameter handling
    resp_junk = client_a.get(url, {"category": "totally_invalid_junk_123", "owner": "not_an_id"})
    assert resp_junk.status_code == 200


def test_managementreview_objective_create_get(client_a):
    """Verify QualityObjective create GET returns 200 and initial form."""
    url = reverse("quality:quality_objective_create")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["objective"] is None


def test_managementreview_objective_create_post(client_a, admin_user, quality_department):
    """Verify QualityObjective create POST successfully creates an objective and redirects to detail."""
    url = reverse("quality:quality_objective_create")
    data = {
        "title": "First Pass Inspection Yield >= 99.0%",
        "description": "Increase automated surface-mount inspection yields.",
        "category": "process_performance",
        "period_year": 2026,
        "cadence": "quarterly",
        "metric_unit": "%",
        "baseline_value": "95.000",
        "target_value": "99.000",
        "current_value": "98.500",
        "target_direction": "higher_better",
        "status": "on_track",
        "owner": admin_user.pk,
        "org_unit": quality_department.pk,
        "target_date": "2026-12-31",
        "action_plan_summary": "Implement high-speed 3D AOI machines.",
        "notes": "Initiated per 2026 strategic quality plan.",
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 302

    created_obj = QualityObjective.objects.filter(title="First Pass Inspection Yield >= 99.0%").first()
    assert created_obj is not None
    assert created_obj.number.startswith("QOBJ-")
    assert resp.url == reverse("quality:quality_objective_detail", kwargs={"pk": created_obj.pk})


def test_managementreview_objective_detail_view(client_a, quality_objective_a):
    """Verify QualityObjective detail view returns 200 and exposes all contracted context variables."""
    url = reverse("quality:quality_objective_detail", kwargs={"pk": quality_objective_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    ctx = resp.context
    assert "objective" in ctx
    assert ctx["objective"].pk == quality_objective_a.pk
    assert "variance" in ctx
    assert "is_achieved" in ctx
    assert "evaluate_form" in ctx
    assert "can_evaluate" in ctx
    assert ctx["is_achieved"] is True
    assert b"Reduce Customer RMA Incident Rate" in resp.content


def test_managementreview_objective_edit_get(client_a, quality_objective_a):
    """Verify QualityObjective edit GET returns 200 with populated form."""
    url = reverse("quality:quality_objective_edit", kwargs={"pk": quality_objective_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is True
    assert resp.context["objective"].pk == quality_objective_a.pk


def test_managementreview_objective_edit_post(client_a, quality_objective_a, admin_user, quality_department):
    """Verify QualityObjective edit POST updates record and redirects to detail."""
    url = reverse("quality:quality_objective_edit", kwargs={"pk": quality_objective_a.pk})
    data = {
        "title": "Reduce Customer RMA Incident Rate < 0.40% (Updated)",
        "description": quality_objective_a.description,
        "category": quality_objective_a.category,
        "period_year": quality_objective_a.period_year,
        "cadence": quality_objective_a.cadence,
        "metric_unit": quality_objective_a.metric_unit,
        "baseline_value": str(quality_objective_a.baseline_value),
        "target_value": "0.400",
        "current_value": str(quality_objective_a.current_value),
        "target_direction": quality_objective_a.target_direction,
        "status": "on_track",
        "owner": admin_user.pk,
        "org_unit": quality_department.pk,
        "target_date": str(quality_objective_a.target_date),
        "action_plan_summary": "Enhanced burn-in screening.",
        "notes": "Target revised downwards.",
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:quality_objective_detail", kwargs={"pk": quality_objective_a.pk})

    quality_objective_a.refresh_from_db()
    assert quality_objective_a.title == "Reduce Customer RMA Incident Rate < 0.40% (Updated)"
    assert quality_objective_a.target_value == Decimal("0.400")


def test_managementreview_objective_evaluate_post(client_a, quality_objective_a):
    """Verify QualityObjective evaluate POST updates current_value and recalculates RAG."""
    url = reverse("quality:quality_objective_evaluate", kwargs={"pk": quality_objective_a.pk})
    # Target direction is lower_better, target is 0.500. A value of 0.350 is achieved (green).
    data = {
        "current_value": "0.350",
        "notes": "Q3 performance evaluation audit confirms 0.350% RMA rate.",
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:quality_objective_detail", kwargs={"pk": quality_objective_a.pk})

    quality_objective_a.refresh_from_db()
    assert quality_objective_a.current_value == Decimal("0.350")
    assert quality_objective_a.rag_status == "green"
    assert "Q3 performance evaluation audit" in quality_objective_a.notes


def test_managementreview_objective_evaluate_rejects_get(client_a, quality_objective_a):
    """Verify QualityObjective evaluate view rejects GET requests with 405 Method Not Allowed."""
    url = reverse("quality:quality_objective_evaluate", kwargs={"pk": quality_objective_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


def test_managementreview_objective_evaluate_draft_blocked(client_a, tenant_a, admin_user, quality_department):
    """Verify QualityObjective evaluate view rejects evaluation of draft objectives."""
    draft_obj = QualityObjective.objects.create(
        tenant=tenant_a,
        title="Draft Objective Under Development",
        category="compliance",
        period_year=2026,
        cadence="annual",
        metric_unit="count",
        baseline_value=Decimal("5.000"),
        target_value=Decimal("0.000"),
        target_direction="lower_better",
        status="draft",
        owner=admin_user,
        org_unit=quality_department,
    )
    url = reverse("quality:quality_objective_evaluate", kwargs={"pk": draft_obj.pk})
    resp = client_a.post(url, {"current_value": "2.000"})
    assert resp.status_code == 302
    assert resp.url == reverse("quality:quality_objective_detail", kwargs={"pk": draft_obj.pk})

    draft_obj.refresh_from_db()
    assert draft_obj.current_value is None


def test_managementreview_objective_delete_post(client_a, tenant_a, admin_user, quality_department):
    """Verify QualityObjective delete POST deletes the record and redirects to list."""
    temp_obj = QualityObjective.objects.create(
        tenant=tenant_a,
        title="Temporary Objective to Delete",
        category="customer_satisfaction",
        period_year=2026,
        cadence="monthly",
        metric_unit="NPS",
        baseline_value=Decimal("60.000"),
        target_value=Decimal("80.000"),
        target_direction="higher_better",
        status="draft",
        owner=admin_user,
        org_unit=quality_department,
    )
    pk = temp_obj.pk
    url = reverse("quality:quality_objective_delete", kwargs={"pk": pk})

    # GET is rejected with 405
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # POST deletes record
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("quality:quality_objective_list")
    assert not QualityObjective.objects.filter(pk=pk).exists()


def test_managementreview_objective_export_csv(client_a, quality_objective_a):
    """Verify QualityObjective export CSV returns 200 text/csv with correct headers."""
    url = reverse("quality:quality_objective_export_csv")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/csv")
    assert 'attachment; filename="quality_objectives.csv"' in resp["Content-Disposition"]
    content = resp.content.decode("utf-8")
    assert "Objective Number" in content
    assert "Target Direction" in content
    assert quality_objective_a.number in content


# ==============================================================================
# 3. MANAGEMENT REVIEW VIEWS
# ==============================================================================

def test_managementreview_list_view(client_a, management_review_a):
    """Verify ManagementReview list returns 200 and provides KPI aggregates and choices."""
    url = reverse("quality:management_review_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    ctx = resp.context
    assert "reviews" in ctx
    assert "scheduled_count" in ctx
    assert "active_count" in ctx
    assert "approved_count" in ctx
    assert "cadence_choices" in ctx
    assert "status_choices" in ctx
    assert "suitability_choices" in ctx
    assert "org_units" in ctx
    assert "sponsors" in ctx

    assert ctx["scheduled_count"] >= 1
    assert management_review_a.number.encode() in resp.content
    assert b"Executive QMS Suitability" in resp.content


def test_managementreview_list_filters_and_search(client_a, management_review_a, admin_user):
    """Verify ManagementReview list search, filters, and junk query params."""
    url = reverse("quality:management_review_list")

    # Search filter
    resp_search = client_a.get(url, {"q": "Executive QMS"})
    assert resp_search.status_code == 200
    assert management_review_a.number.encode() in resp_search.content

    resp_nomatch = client_a.get(url, {"q": "NonExistentReviewTitle999"})
    assert resp_nomatch.status_code == 200
    assert management_review_a.number.encode() not in resp_nomatch.content

    # Cadence filter
    resp_cadence = client_a.get(url, {"cadence": "quarterly"})
    assert resp_cadence.status_code == 200
    assert management_review_a.number.encode() in resp_cadence.content

    resp_cadence_mismatch = client_a.get(url, {"cadence": "annual"})
    assert resp_cadence_mismatch.status_code == 200
    assert management_review_a.number.encode() not in resp_cadence_mismatch.content

    # Status & Suitability & Sponsor filter
    resp_filters = client_a.get(
        url,
        {
            "status": "scheduled",
            "suitability": "pending",
            "sponsor": str(admin_user.pk),
        },
    )
    assert resp_filters.status_code == 200
    assert management_review_a.number.encode() in resp_filters.content

    # Junk parameter handling
    resp_junk = client_a.get(url, {"cadence": "unrecognized_cadence_xyz", "sponsor": "invalid_pk"})
    assert resp_junk.status_code == 200


def test_managementreview_create_get(client_a):
    """Verify ManagementReview create GET returns 200 and initial form."""
    url = reverse("quality:management_review_create")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["review"] is None


def test_managementreview_create_post(client_a, admin_user, staff_user, quality_department):
    """Verify ManagementReview create POST creates review and redirects to detail."""
    url = reverse("quality:management_review_create")
    start = _managementreview_relative_date(-90)
    end = _managementreview_relative_date(0)
    scheduled = _managementreview_relative_date(14)

    data = {
        "title": "Q4 Executive QMS Suitability & Adequacy Review",
        "cadence": "quarterly",
        "period_start": str(start),
        "period_end": str(end),
        "scheduled_date": str(scheduled),
        "location": "Boardroom A & MS Teams",
        "executive_sponsor": admin_user.pk,
        "lead_facilitator": staff_user.pk,
        "org_unit": quality_department.pk,
        "notes": "Review all FDA readiness findings.",
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 302

    created = ManagementReview.objects.filter(title="Q4 Executive QMS Suitability & Adequacy Review").first()
    assert created is not None
    assert created.number.startswith("QMRV-")
    assert created.status == "scheduled"
    assert resp.url == reverse("quality:management_review_detail", kwargs={"pk": created.pk})


def test_managementreview_detail_view(client_a, management_review_a, management_review_input_a, management_review_action_a):
    """Verify ManagementReview detail returns 200 and populates all contract context variables."""
    url = reverse("quality:management_review_detail", kwargs={"pk": management_review_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    ctx = resp.context
    assert "review" in ctx
    assert ctx["review"].pk == management_review_a.pk
    assert "inputs" in ctx
    assert "actions" in ctx
    assert "open_actions" in ctx
    assert "total_inputs_count" in ctx
    assert "total_actions_count" in ctx
    assert "open_actions_count" in ctx
    assert "approve_form" in ctx
    assert "can_start" in ctx
    assert "can_draft_minutes" in ctx
    assert "can_approve" in ctx
    assert "can_cancel" in ctx

    # For scheduled review, can_start is True
    assert ctx["can_start"] is True
    assert b"Executive QMS Suitability" in resp.content


def test_managementreview_edit_get(client_a, management_review_a):
    """Verify ManagementReview edit GET returns 200 with populated form."""
    url = reverse("quality:management_review_edit", kwargs={"pk": management_review_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is True
    assert resp.context["review"].pk == management_review_a.pk


def test_managementreview_edit_post(client_a, management_review_a, admin_user, staff_user, quality_department):
    """Verify ManagementReview edit POST updates record and redirects to detail."""
    url = reverse("quality:management_review_edit", kwargs={"pk": management_review_a.pk})
    data = {
        "title": "Q3 Executive QMS Suitability Review (Rescheduled)",
        "cadence": management_review_a.cadence,
        "period_start": str(management_review_a.period_start),
        "period_end": str(management_review_a.period_end),
        "scheduled_date": str(_managementreview_relative_date(21)),
        "location": "Main Conference Facility",
        "executive_sponsor": admin_user.pk,
        "lead_facilitator": staff_user.pk,
        "org_unit": quality_department.pk,
        "notes": "Rescheduled for VP availability.",
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:management_review_detail", kwargs={"pk": management_review_a.pk})

    management_review_a.refresh_from_db()
    assert management_review_a.title == "Q3 Executive QMS Suitability Review (Rescheduled)"
    assert management_review_a.location == "Main Conference Facility"


def test_managementreview_edit_approved_blocked(client_a, management_review_a):
    """Verify editing an approved ManagementReview is blocked."""
    management_review_a.status = "approved"
    management_review_a.save()

    url = reverse("quality:management_review_edit", kwargs={"pk": management_review_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:management_review_detail", kwargs={"pk": management_review_a.pk})


def test_managementreview_start_post(client_a, management_review_a):
    """Verify ManagementReview start POST transitions review to meeting_active."""
    url = reverse("quality:management_review_start", kwargs={"pk": management_review_a.pk})

    # GET is rejected with 405
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # POST transitions to meeting_active
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("quality:management_review_detail", kwargs={"pk": management_review_a.pk})

    management_review_a.refresh_from_db()
    assert management_review_a.status == "meeting_active"
    assert management_review_a.actual_meeting_date == timezone.now().date()


def test_managementreview_draft_minutes_flow(client_a, management_review_a):
    """Verify ManagementReview draft minutes GET/POST saves minutes, roster, and suitability."""
    # Minutes require meeting to be started
    management_review_a.status = "meeting_active"
    management_review_a.save()

    url = reverse("quality:management_review_draft_minutes", kwargs={"pk": management_review_a.pk})

    # GET renders minutes form
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert "form" in resp_get.context
    assert resp_get.context["review"].pk == management_review_a.pk

    # POST saves minutes and moves status to pending_approval (since suitability != pending)
    data = {
        "actual_meeting_date": str(timezone.now().date()),
        "attendees_roster": "CEO, VP Quality, Operations Director, Regulatory Affairs Lead",
        "quorum_met": True,
        "qms_suitability_conclusion": "suitable_effective",
        "executive_summary": "The QMS continues to operate in compliance with ISO 13485:2016 and FDA 21 CFR Part 820.",
        "minutes_discussion": "Thoroughly analyzed 14 input topics, internal audits, and customer feedback.",
        "resource_decisions": "Authorized $120,000 for cleanroom automation and 2 additional QA engineers.",
        "notes": "Unanimous executive endorsement.",
    }
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("quality:management_review_detail", kwargs={"pk": management_review_a.pk})

    management_review_a.refresh_from_db()
    assert management_review_a.status == "pending_approval"
    assert management_review_a.qms_suitability_conclusion == "suitable_effective"
    assert management_review_a.quorum_met is True
    assert "Authorized $120,000" in management_review_a.resource_decisions


def test_managementreview_draft_minutes_unstarted_blocked(client_a, management_review_a):
    """Verify drafting minutes before meeting start is blocked."""
    management_review_a.status = "scheduled"
    management_review_a.save()

    url = reverse("quality:management_review_draft_minutes", kwargs={"pk": management_review_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:management_review_detail", kwargs={"pk": management_review_a.pk})


def test_managementreview_approve_post(client_a, management_review_a, admin_user):
    """Verify ManagementReview approve POST creates ElectronicSignatureRecord, binds it, and marks approved."""
    management_review_a.status = "pending_approval"
    management_review_a.qms_suitability_conclusion = "suitable_effective"
    management_review_a.save()

    url = reverse("quality:management_review_approve", kwargs={"pk": management_review_a.pk})

    # GET rejected with 405
    assert client_a.get(url).status_code == 405

    # POST with confirmation
    data = {
        "confirm_suitability": True,
        "comment": "Formally endorsed and certified as executive sponsor.",
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:management_review_detail", kwargs={"pk": management_review_a.pk})

    management_review_a.refresh_from_db()
    assert management_review_a.status == "approved"
    assert management_review_a.approved_by == admin_user
    assert management_review_a.approved_at is not None
    assert management_review_a.electronic_signature is not None
    assert management_review_a.electronic_signature.signature_meaning == "management_approval"


def test_managementreview_approve_pending_suitability_blocked(client_a, management_review_a):
    """Verify ManagementReview approve is blocked if suitability conclusion is still pending."""
    management_review_a.status = "meeting_active"
    management_review_a.qms_suitability_conclusion = "pending"
    management_review_a.save()

    url = reverse("quality:management_review_approve", kwargs={"pk": management_review_a.pk})
    resp = client_a.post(url, {"confirm_suitability": True, "comment": "premature approval"})
    assert resp.status_code == 302
    assert resp.url == reverse("quality:management_review_detail", kwargs={"pk": management_review_a.pk})

    management_review_a.refresh_from_db()
    assert management_review_a.status != "approved"


def test_managementreview_cancel_post(client_a, management_review_a):
    """Verify ManagementReview cancel POST marks review as cancelled."""
    url = reverse("quality:management_review_cancel", kwargs={"pk": management_review_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:management_review_detail", kwargs={"pk": management_review_a.pk})

    management_review_a.refresh_from_db()
    assert management_review_a.status == "cancelled"


def test_managementreview_cancel_approved_blocked(client_a, management_review_a):
    """Verify approved ManagementReview cannot be cancelled."""
    management_review_a.status = "approved"
    management_review_a.save()

    url = reverse("quality:management_review_cancel", kwargs={"pk": management_review_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302

    management_review_a.refresh_from_db()
    assert management_review_a.status == "approved"


def test_managementreview_delete_post(client_a, tenant_a, admin_user, staff_user, quality_department):
    """Verify ManagementReview delete POST deletes scheduled review."""
    temp_rev = ManagementReview.objects.create(
        tenant=tenant_a,
        title="Temporary Review to Delete",
        cadence="monthly",
        period_start=_managementreview_relative_date(-30),
        period_end=_managementreview_relative_date(0),
        scheduled_date=_managementreview_relative_date(7),
        executive_sponsor=admin_user,
        lead_facilitator=staff_user,
        org_unit=quality_department,
        status="scheduled",
    )
    pk = temp_rev.pk
    url = reverse("quality:management_review_delete", kwargs={"pk": pk})

    # GET rejected with 405
    assert client_a.get(url).status_code == 405

    # POST deletes review
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:management_review_list")
    assert not ManagementReview.objects.filter(pk=pk).exists()


def test_managementreview_delete_approved_blocked(client_a, management_review_a):
    """Verify approved ManagementReview cannot be deleted due to regulatory audit compliance."""
    management_review_a.status = "approved"
    management_review_a.save()

    url = reverse("quality:management_review_delete", kwargs={"pk": management_review_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:management_review_detail", kwargs={"pk": management_review_a.pk})
    assert ManagementReview.objects.filter(pk=management_review_a.pk).exists()


def test_managementreview_export_pdf_view(
    client_a,
    management_review_a,
    management_review_input_a,
    management_review_action_a,
):
    """Verify ManagementReview export PDF / dossier renders dossier template with inputs and actions."""
    url = reverse("quality:management_review_export_pdf", kwargs={"pk": management_review_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "quality/managementreview/management_review/dossier.html" in [t.name for t in resp.templates]
    assert "review" in resp.context
    assert "inputs" in resp.context
    assert "actions" in resp.context
    assert "export_date" in resp.context
    assert management_review_a.number.encode() in resp.content


def test_managementreview_export_csv(client_a, management_review_a):
    """Verify ManagementReview export CSV returns 200 text/csv."""
    url = reverse("quality:management_review_export_csv")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/csv")
    assert 'attachment; filename="management_reviews.csv"' in resp["Content-Disposition"]
    content = resp.content.decode("utf-8")
    assert "Review Number" in content
    assert "QMS Suitability Conclusion" in content
    assert management_review_a.number in content


# ==============================================================================
# 4. MANAGEMENT REVIEW INPUT VIEWS
# ==============================================================================

def test_managementreview_input_list_view(client_a, management_review_input_a, management_review_a):
    """Verify ManagementReviewInput list returns 200 with metrics, filters, and choices."""
    url = reverse("quality:management_review_input_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    ctx = resp.context
    assert "inputs" in ctx
    assert "compiled_count" in ctx
    assert "presented_count" in ctx
    assert "accepted_count" in ctx
    assert "category_choices" in ctx
    assert "status_choices" in ctx
    assert "reviews" in ctx
    assert "presenters" in ctx

    assert ctx["compiled_count"] >= 1
    assert management_review_input_a.number.encode() in resp.content

    # Search filter
    resp_search = client_a.get(url, {"q": "Supplier Quality Audit"})
    assert resp_search.status_code == 200
    assert management_review_input_a.number.encode() in resp_search.content

    # Specific category and review filters
    resp_filter = client_a.get(
        url,
        {
            "category": "audit_results",
            "status": "compiled",
            "review": str(management_review_a.pk),
        },
    )
    assert resp_filter.status_code == 200
    assert management_review_input_a.number.encode() in resp_filter.content

    # Junk parameter handling
    resp_junk = client_a.get(url, {"category": "non_existent_cat", "review": "junk_id"})
    assert resp_junk.status_code == 200


def test_managementreview_input_create_get_without_review_id(client_a):
    """Verify ManagementReviewInput create GET without review_id returns 200 and form."""
    url = reverse("quality:management_review_input_create")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["parent_review"] is None
    assert resp.context["is_edit"] is False


def test_managementreview_input_create_get_with_review_id(client_a, management_review_a):
    """Verify ManagementReviewInput create GET with review_id binds parent review in context."""
    url = f"{reverse('quality:management_review_input_create')}?review_id={management_review_a.pk}"
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["parent_review"].pk == management_review_a.pk


def test_managementreview_input_create_post(client_a, management_review_a, admin_user):
    """Verify ManagementReviewInput create POST creates input and redirects to review detail."""
    url = reverse("quality:management_review_input_create")
    data = {
        "management_review": management_review_a.pk,
        "agenda_order": 2,
        "title": "CAPA Open Volume & Overdue Aging Metrics",
        "category": "capa_status",
        "presenter": admin_user.pk,
        "summary_findings": "Total 4 open CAPAs; zero overdue investigations exceeding statutory timelines.",
        "metrics_data": "Mean time to closure: 38 days.",
        "attachments_summary": "CAPA Q3 Dashboard Export PDF",
        "notes": "Reviewed by QA manager.",
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:management_review_detail", kwargs={"pk": management_review_a.pk})

    created = ManagementReviewInput.objects.filter(title="CAPA Open Volume & Overdue Aging Metrics").first()
    assert created is not None
    assert created.number.startswith("QMRI-")
    assert created.status == "compiled"


def test_managementreview_input_create_approved_review_blocked(client_a, management_review_a):
    """Verify creating an input under an approved review is blocked."""
    management_review_a.status = "approved"
    management_review_a.save()

    url = f"{reverse('quality:management_review_input_create')}?review_id={management_review_a.pk}"
    resp = client_a.get(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:management_review_detail", kwargs={"pk": management_review_a.pk})


def test_managementreview_input_detail_view(client_a, management_review_input_a):
    """Verify ManagementReviewInput detail returns 200 with contracted context variables."""
    url = reverse("quality:management_review_input_detail", kwargs={"pk": management_review_input_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    ctx = resp.context
    assert "review_input" in ctx
    assert ctx["review_input"].pk == management_review_input_a.pk
    assert "can_present" in ctx
    assert "can_accept" in ctx
    assert b"Supplier Quality Audit Performance" in resp.content


def test_managementreview_input_edit_get_and_post(client_a, management_review_input_a, admin_user):
    """Verify ManagementReviewInput edit GET/POST updates input item."""
    url = reverse("quality:management_review_input_edit", kwargs={"pk": management_review_input_a.pk})

    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True

    data = {
        "management_review": management_review_input_a.management_review_id,
        "agenda_order": 1,
        "title": "Updated Audit Performance Summary Title",
        "category": management_review_input_a.category,
        "presenter": admin_user.pk,
        "summary_findings": "Updated findings narrative.",
        "metrics_data": "100% resolution rate.",
        "attachments_summary": "Deck v2.0",
        "notes": "Updated during meeting prep.",
    }
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("quality:management_review_input_detail", kwargs={"pk": management_review_input_a.pk})

    management_review_input_a.refresh_from_db()
    assert management_review_input_a.title == "Updated Audit Performance Summary Title"


def test_managementreview_input_present_post(client_a, management_review_input_a):
    """Verify ManagementReviewInput present POST transitions status to presented."""
    url = reverse("quality:management_review_input_present", kwargs={"pk": management_review_input_a.pk})

    # GET rejected with 405
    assert client_a.get(url).status_code == 405

    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:management_review_input_detail", kwargs={"pk": management_review_input_a.pk})

    management_review_input_a.refresh_from_db()
    assert management_review_input_a.status == "presented"


def test_managementreview_input_accept_post(client_a, management_review_input_a):
    """Verify ManagementReviewInput accept POST transitions status to accepted."""
    url = reverse("quality:management_review_input_accept", kwargs={"pk": management_review_input_a.pk})

    # GET rejected with 405
    assert client_a.get(url).status_code == 405

    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:management_review_input_detail", kwargs={"pk": management_review_input_a.pk})

    management_review_input_a.refresh_from_db()
    assert management_review_input_a.status == "accepted"


def test_managementreview_input_delete_post(client_a, tenant_a, management_review_a, admin_user):
    """Verify ManagementReviewInput delete POST deletes input and redirects to review detail."""
    temp_inp = ManagementReviewInput.objects.create(
        tenant=tenant_a,
        management_review=management_review_a,
        category="other_business",
        title="Temporary Input to Delete",
        agenda_order=9,
        presenter=admin_user,
        status="compiled",
    )
    pk = temp_inp.pk
    url = reverse("quality:management_review_input_delete", kwargs={"pk": pk})

    # GET rejected with 405
    assert client_a.get(url).status_code == 405

    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:management_review_detail", kwargs={"pk": management_review_a.pk})
    assert not ManagementReviewInput.objects.filter(pk=pk).exists()


def test_managementreview_input_export_csv(client_a, management_review_input_a):
    """Verify ManagementReviewInput export CSV returns 200 text/csv."""
    url = reverse("quality:management_review_input_export_csv")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/csv")
    assert 'attachment; filename="management_review_inputs.csv"' in resp["Content-Disposition"]
    content = resp.content.decode("utf-8")
    assert "Input Number" in content
    assert "Topic Title" in content
    assert management_review_input_a.number in content


# ==============================================================================
# 5. MANAGEMENT REVIEW ACTION VIEWS
# ==============================================================================

def test_managementreview_action_list_view(client_a, management_review_action_a, management_review_a, staff_user):
    """Verify ManagementReviewAction list returns 200 with KPI stats, filters, and choices."""
    url = reverse("quality:management_review_action_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    ctx = resp.context
    assert "actions" in ctx
    assert "open_count" in ctx
    assert "overdue_count" in ctx
    assert "completed_count" in ctx
    assert "action_type_choices" in ctx
    assert "priority_choices" in ctx
    assert "status_choices" in ctx
    assert "reviews" in ctx
    assert "assignees" in ctx

    assert ctx["open_count"] >= 1
    assert management_review_action_a.number.encode() in resp.content

    # Search filter
    resp_search = client_a.get(url, {"q": "Optical Inspection"})
    assert resp_search.status_code == 200
    assert management_review_action_a.number.encode() in resp_search.content

    # Specific attribute filters
    resp_filter = client_a.get(
        url,
        {
            "action_type": "resource_allocation",
            "priority": "high",
            "status": "open",
            "review": str(management_review_a.pk),
            "assignee": str(staff_user.pk),
        },
    )
    assert resp_filter.status_code == 200
    assert management_review_action_a.number.encode() in resp_filter.content

    # Junk parameter handling
    resp_junk = client_a.get(url, {"action_type": "invalid_type", "priority": "extreme_junk"})
    assert resp_junk.status_code == 200


def test_managementreview_action_create_get_without_review_id(client_a):
    """Verify ManagementReviewAction create GET without review_id returns 200 and form."""
    url = reverse("quality:management_review_action_create")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["parent_review"] is None
    assert resp.context["is_edit"] is False


def test_managementreview_action_create_get_with_review_id(client_a, management_review_a):
    """Verify ManagementReviewAction create GET with review_id binds parent review."""
    url = f"{reverse('quality:management_review_action_create')}?review_id={management_review_a.pk}"
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["parent_review"].pk == management_review_a.pk


def test_managementreview_action_create_post(client_a, management_review_a, staff_user):
    """Verify ManagementReviewAction create POST creates action item and redirects to review detail."""
    url = reverse("quality:management_review_action_create")
    due = _managementreview_relative_date(45)
    data = {
        "management_review": management_review_a.pk,
        "title": "Commission Secondary Cleanroom Humidity Sensor Array",
        "action_type": "resource_allocation",
        "priority": "medium",
        "assignee": staff_user.pk,
        "due_date": str(due),
        "budget_allocated": "18500.00",
        "description": "Install redundant calibrated NIST sensors to prevent excursion events.",
        "notes": "Fast-tracked per QMS review.",
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:management_review_detail", kwargs={"pk": management_review_a.pk})

    created = ManagementReviewAction.objects.filter(title="Commission Secondary Cleanroom Humidity Sensor Array").first()
    assert created is not None
    assert created.number.startswith("QMRA-")
    assert created.status == "open"


def test_managementreview_action_create_approved_review_blocked(client_a, management_review_a):
    """Verify creating an action item under an approved review is blocked."""
    management_review_a.status = "approved"
    management_review_a.save()

    url = f"{reverse('quality:management_review_action_create')}?review_id={management_review_a.pk}"
    resp = client_a.get(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:management_review_detail", kwargs={"pk": management_review_a.pk})


def test_managementreview_action_detail_view(client_a, management_review_action_a):
    """Verify ManagementReviewAction detail returns 200 and exposes all contract context keys."""
    url = reverse("quality:management_review_action_detail", kwargs={"pk": management_review_action_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    ctx = resp.context
    assert "action_item" in ctx
    assert ctx["action_item"].pk == management_review_action_a.pk
    assert "is_overdue" in ctx
    assert "days_open" in ctx
    assert "can_start" in ctx
    assert "can_complete" in ctx
    assert "can_verify" in ctx
    assert "can_escalate_capa" in ctx
    assert "complete_form" in ctx
    assert "verify_form" in ctx
    assert management_review_action_a.title.encode() in resp.content


def test_managementreview_action_edit_get_and_post(client_a, management_review_action_a, staff_user):
    """Verify ManagementReviewAction edit GET/POST updates action item."""
    url = reverse("quality:management_review_action_edit", kwargs={"pk": management_review_action_a.pk})

    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True

    data = {
        "management_review": management_review_action_a.management_review_id,
        "title": "Procure AOI Station (Revised Scope)",
        "action_type": management_review_action_a.action_type,
        "priority": "critical",
        "assignee": staff_user.pk,
        "due_date": str(management_review_action_a.due_date),
        "budget_allocated": "55000.00",
        "description": "Expanded to cover high-speed dual vision head camera.",
        "notes": "Budget revised by CFO.",
    }
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("quality:management_review_action_detail", kwargs={"pk": management_review_action_a.pk})

    management_review_action_a.refresh_from_db()
    assert management_review_action_a.title == "Procure AOI Station (Revised Scope)"
    assert management_review_action_a.priority == "critical"
    assert management_review_action_a.budget_allocated == Decimal("55000.00")


def test_managementreview_action_start_post(client_a, management_review_action_a):
    """Verify ManagementReviewAction start POST moves status to in_progress."""
    url = reverse("quality:management_review_action_start", kwargs={"pk": management_review_action_a.pk})

    # GET rejected with 405
    assert client_a.get(url).status_code == 405

    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:management_review_action_detail", kwargs={"pk": management_review_action_a.pk})

    management_review_action_a.refresh_from_db()
    assert management_review_action_a.status == "in_progress"


def test_managementreview_action_complete_post(client_a, management_review_action_a):
    """Verify ManagementReviewAction complete POST sets resolution and moves to pending_verification."""
    management_review_action_a.status = "in_progress"
    management_review_action_a.save()

    url = reverse("quality:management_review_action_complete", kwargs={"pk": management_review_action_a.pk})

    # GET rejected with 405
    assert client_a.get(url).status_code == 405

    data = {
        "resolution_summary": "AOI inspection system delivered, installed, and validated via IQ/OQ/PQ protocols.",
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:management_review_action_detail", kwargs={"pk": management_review_action_a.pk})

    management_review_action_a.refresh_from_db()
    assert management_review_action_a.status == "pending_verification"
    assert management_review_action_a.completion_date == timezone.now().date()
    assert "validated via IQ/OQ/PQ" in management_review_action_a.resolution_summary


def test_managementreview_action_verify_post(client_a, management_review_action_a, admin_user):
    """Verify ManagementReviewAction verify POST marks action completed and binds verified_by."""
    management_review_action_a.status = "pending_verification"
    management_review_action_a.resolution_summary = "Equipment fully installed."
    management_review_action_a.save()

    url = reverse("quality:management_review_action_verify", kwargs={"pk": management_review_action_a.pk})

    # GET rejected with 405
    assert client_a.get(url).status_code == 405

    data = {
        "verification_notes": "QA Director audited IQ/OQ validation package and verified zero defects on test batch.",
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:management_review_action_detail", kwargs={"pk": management_review_action_a.pk})

    management_review_action_a.refresh_from_db()
    assert management_review_action_a.status == "completed"
    assert management_review_action_a.verified_by == admin_user
    assert "QA Director audited IQ/OQ" in management_review_action_a.verification_notes


def test_managementreview_action_escalate_capa_post(client_a, management_review_action_a):
    """Verify ManagementReviewAction escalate CAPA creates CapaInvestigation and links spawned_capa."""
    url = reverse("quality:management_review_action_escalate_capa", kwargs={"pk": management_review_action_a.pk})

    # GET rejected with 405
    assert client_a.get(url).status_code == 405

    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:management_review_action_detail", kwargs={"pk": management_review_action_a.pk})

    management_review_action_a.refresh_from_db()
    assert management_review_action_a.spawned_capa is not None
    capa = management_review_action_a.spawned_capa
    assert isinstance(capa, CapaInvestigation)
    assert capa.source_type == "management_review"
    assert capa.source_reference == management_review_action_a.number
    assert management_review_action_a.status == "in_progress"


def test_managementreview_action_delete_post(client_a, tenant_a, management_review_a, staff_user):
    """Verify ManagementReviewAction delete POST removes open action item."""
    temp_act = ManagementReviewAction.objects.create(
        tenant=tenant_a,
        management_review=management_review_a,
        title="Temporary Action Item to Delete",
        action_type="qms_improvement",
        priority="low",
        assignee=staff_user,
        due_date=_managementreview_relative_date(30),
        status="open",
    )
    pk = temp_act.pk
    url = reverse("quality:management_review_action_delete", kwargs={"pk": pk})

    # GET rejected with 405
    assert client_a.get(url).status_code == 405

    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:management_review_detail", kwargs={"pk": management_review_a.pk})
    assert not ManagementReviewAction.objects.filter(pk=pk).exists()


def test_managementreview_action_delete_completed_blocked(client_a, management_review_action_a):
    """Verify completed action items cannot be deleted."""
    management_review_action_a.status = "completed"
    management_review_action_a.save()

    url = reverse("quality:management_review_action_delete", kwargs={"pk": management_review_action_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:management_review_action_detail", kwargs={"pk": management_review_action_a.pk})
    assert ManagementReviewAction.objects.filter(pk=management_review_action_a.pk).exists()


def test_managementreview_action_export_csv(client_a, management_review_action_a):
    """Verify ManagementReviewAction export CSV returns 200 text/csv."""
    url = reverse("quality:management_review_action_export_csv")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/csv")
    assert 'attachment; filename="management_review_actions.csv"' in resp["Content-Disposition"]
    content = resp.content.decode("utf-8")
    assert "Action Number" in content
    assert "Action Title" in content
    assert management_review_action_a.number in content
