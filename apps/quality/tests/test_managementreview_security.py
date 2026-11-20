"""Security, multi-tenant isolation (IDOR), segregation of duties, and authorization tests
for Quality Management Sub-module 12.14: Management Review & Quality Planning.

Covers:
1. Unauthenticated Access:
   - Anonymous requests to dashboard, lists, creates, details, actions, and exports redirect to login (302).
2. Cross-Tenant IDOR Protection (Strict 404):
   - Tenant A client accessing Tenant B QualityObjective (detail, edit, evaluate, delete) returns 404.
   - Tenant A client accessing Tenant B ManagementReview (detail, edit, start, draft-minutes, approve, cancel, delete, export-pdf) returns 404.
   - Tenant A client accessing Tenant B ManagementReviewInput (detail, edit, present, accept, delete) returns 404.
   - Tenant A client accessing Tenant B ManagementReviewAction (detail, edit, start, complete, verify, escalate-capa, delete) returns 404.
3. Multi-Tenant Query Isolation:
   - Client A list views, exports, and dashboard display only Tenant A records, never Tenant B records.
   - Client B list views, exports, and dashboard display only Tenant B records, never Tenant A records.
4. Authorization & Segregation of Duties (SoD):
   - Executive Approval: Standard non-executive member cannot approve management review.
   - Objective Evaluation: Non-owner member cannot evaluate performance on objective.
   - Action Verification: Assignee cannot self-verify their own action item (independent QA verification enforcement).
5. State Tampering & Lifecycle Integrity:
   - Cannot add, edit, present, accept, or delete ManagementReviewInput on approved review.
   - Cannot edit or delete ManagementReviewAction on approved review.
   - Cannot delete completed ManagementReviewAction.
   - Cannot edit, cancel, or delete an approved ManagementReview.
   - Cannot draft minutes for an unstarted / scheduled review.
   - Cannot approve review with pending QMS suitability conclusion.
6. Cross-Tenant Foreign Key Injection Rejection:
   - Form rejection when Tenant A user attempts to submit Tenant B org_unit, owner, presenter, or assignee.
7. HTTP Method Gating (405 Method Not Allowed):
   - Mutating state-changing actions reject GET requests with HTTP 405.
"""

from datetime import date, timedelta
from decimal import Decimal
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.models import OrgUnit
from apps.quality.models.ManagementReview.ManagementReviewActions import ManagementReviewAction
from apps.quality.models.ManagementReview.ManagementReviewInputs import ManagementReviewInput
from apps.quality.models.ManagementReview.ManagementReviews import ManagementReview
from apps.quality.models.ManagementReview.QualityObjectives import QualityObjective

pytestmark = pytest.mark.django_db


def _managementreview_relative_date(days: int) -> date:
    """Helper returning a date offset from today."""
    return timezone.now().date() + timedelta(days=days)


# ==============================================================================
# 1. UNAUTHENTICATED ACCESS (Anonymous Redirect to Login)
# ==============================================================================

def test_managementreview_unauthenticated_dashboard_redirects(client):
    """Verify anonymous access to Quality Planning Dashboard redirects to login (302)."""
    resp = client.get(reverse("quality:quality_planning_dashboard"))
    assert resp.status_code == 302
    assert "/login" in resp.headers.get("Location", "") or "/accounts/login" in resp.headers.get("Location", "")


def test_managementreview_unauthenticated_quality_objective_endpoints_redirect(
    client, quality_objective_a
):
    """Verify anonymous access to QualityObjective endpoints redirects to login (302)."""
    pk = quality_objective_a.pk
    urls = [
        reverse("quality:quality_objective_list"),
        reverse("quality:quality_objective_create"),
        reverse("quality:quality_objective_detail", kwargs={"pk": pk}),
        reverse("quality:quality_objective_edit", kwargs={"pk": pk}),
        reverse("quality:quality_objective_evaluate", kwargs={"pk": pk}),
        reverse("quality:quality_objective_delete", kwargs={"pk": pk}),
        reverse("quality:quality_objective_export_csv"),
    ]
    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 302
        assert "/login" in resp.headers.get("Location", "") or "/accounts/login" in resp.headers.get("Location", "")


def test_managementreview_unauthenticated_review_endpoints_redirect(
    client, management_review_a
):
    """Verify anonymous access to ManagementReview endpoints redirects to login (302)."""
    pk = management_review_a.pk
    urls = [
        reverse("quality:management_review_list"),
        reverse("quality:management_review_create"),
        reverse("quality:management_review_detail", kwargs={"pk": pk}),
        reverse("quality:management_review_edit", kwargs={"pk": pk}),
        reverse("quality:management_review_start", kwargs={"pk": pk}),
        reverse("quality:management_review_draft_minutes", kwargs={"pk": pk}),
        reverse("quality:management_review_approve", kwargs={"pk": pk}),
        reverse("quality:management_review_cancel", kwargs={"pk": pk}),
        reverse("quality:management_review_delete", kwargs={"pk": pk}),
        reverse("quality:management_review_export_pdf", kwargs={"pk": pk}),
        reverse("quality:management_review_export_csv"),
    ]
    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 302
        assert "/login" in resp.headers.get("Location", "") or "/accounts/login" in resp.headers.get("Location", "")


def test_managementreview_unauthenticated_input_endpoints_redirect(
    client, management_review_input_a
):
    """Verify anonymous access to ManagementReviewInput endpoints redirects to login (302)."""
    pk = management_review_input_a.pk
    urls = [
        reverse("quality:management_review_input_list"),
        reverse("quality:management_review_input_create"),
        reverse("quality:management_review_input_detail", kwargs={"pk": pk}),
        reverse("quality:management_review_input_edit", kwargs={"pk": pk}),
        reverse("quality:management_review_input_present", kwargs={"pk": pk}),
        reverse("quality:management_review_input_accept", kwargs={"pk": pk}),
        reverse("quality:management_review_input_delete", kwargs={"pk": pk}),
        reverse("quality:management_review_input_export_csv"),
    ]
    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 302
        assert "/login" in resp.headers.get("Location", "") or "/accounts/login" in resp.headers.get("Location", "")


def test_managementreview_unauthenticated_action_endpoints_redirect(
    client, management_review_action_a
):
    """Verify anonymous access to ManagementReviewAction endpoints redirects to login (302)."""
    pk = management_review_action_a.pk
    urls = [
        reverse("quality:management_review_action_list"),
        reverse("quality:management_review_action_create"),
        reverse("quality:management_review_action_detail", kwargs={"pk": pk}),
        reverse("quality:management_review_action_edit", kwargs={"pk": pk}),
        reverse("quality:management_review_action_start", kwargs={"pk": pk}),
        reverse("quality:management_review_action_complete", kwargs={"pk": pk}),
        reverse("quality:management_review_action_verify", kwargs={"pk": pk}),
        reverse("quality:management_review_action_escalate_capa", kwargs={"pk": pk}),
        reverse("quality:management_review_action_delete", kwargs={"pk": pk}),
        reverse("quality:management_review_action_export_csv"),
    ]
    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 302
        assert "/login" in resp.headers.get("Location", "") or "/accounts/login" in resp.headers.get("Location", "")


# ==============================================================================
# 2. CROSS-TENANT IDOR (Strict 404 Isolation)
# ==============================================================================

def test_managementreview_idor_quality_objective(client_a, quality_objective_b):
    """Verify Tenant A user accessing Tenant B QualityObjective returns strict 404."""
    pk = quality_objective_b.pk
    assert client_a.get(reverse("quality:quality_objective_detail", kwargs={"pk": pk})).status_code == 404
    assert client_a.get(reverse("quality:quality_objective_edit", kwargs={"pk": pk})).status_code == 404
    assert client_a.post(
        reverse("quality:quality_objective_edit", kwargs={"pk": pk}),
        {"title": "IDOR Objective Edit"},
    ).status_code == 404
    assert client_a.post(
        reverse("quality:quality_objective_evaluate", kwargs={"pk": pk}),
        {"current_value": "99.000"},
    ).status_code == 404
    assert client_a.post(reverse("quality:quality_objective_delete", kwargs={"pk": pk})).status_code == 404


def test_managementreview_idor_management_review(client_a, management_review_b):
    """Verify Tenant A user accessing Tenant B ManagementReview returns strict 404."""
    pk = management_review_b.pk
    assert client_a.get(reverse("quality:management_review_detail", kwargs={"pk": pk})).status_code == 404
    assert client_a.get(reverse("quality:management_review_edit", kwargs={"pk": pk})).status_code == 404
    assert client_a.post(
        reverse("quality:management_review_edit", kwargs={"pk": pk}),
        {"title": "IDOR Review Edit"},
    ).status_code == 404
    assert client_a.post(reverse("quality:management_review_start", kwargs={"pk": pk})).status_code == 404
    assert client_a.get(reverse("quality:management_review_draft_minutes", kwargs={"pk": pk})).status_code == 404
    assert client_a.post(
        reverse("quality:management_review_draft_minutes", kwargs={"pk": pk}),
        {"minutes_discussion": "IDOR Minutes"},
    ).status_code == 404
    assert client_a.post(
        reverse("quality:management_review_approve", kwargs={"pk": pk}),
        {"confirm_suitability": True},
    ).status_code == 404
    assert client_a.post(reverse("quality:management_review_cancel", kwargs={"pk": pk})).status_code == 404
    assert client_a.post(reverse("quality:management_review_delete", kwargs={"pk": pk})).status_code == 404
    assert client_a.get(reverse("quality:management_review_export_pdf", kwargs={"pk": pk})).status_code == 404


def test_managementreview_idor_management_review_input(client_a, management_review_input_b):
    """Verify Tenant A user accessing Tenant B ManagementReviewInput returns strict 404."""
    pk = management_review_input_b.pk
    assert client_a.get(reverse("quality:management_review_input_detail", kwargs={"pk": pk})).status_code == 404
    assert client_a.get(reverse("quality:management_review_input_edit", kwargs={"pk": pk})).status_code == 404
    assert client_a.post(
        reverse("quality:management_review_input_edit", kwargs={"pk": pk}),
        {"title": "IDOR Input Edit"},
    ).status_code == 404
    assert client_a.post(reverse("quality:management_review_input_present", kwargs={"pk": pk})).status_code == 404
    assert client_a.post(reverse("quality:management_review_input_accept", kwargs={"pk": pk})).status_code == 404
    assert client_a.post(reverse("quality:management_review_input_delete", kwargs={"pk": pk})).status_code == 404


def test_managementreview_idor_management_review_action(client_a, management_review_action_b):
    """Verify Tenant A user accessing Tenant B ManagementReviewAction returns strict 404."""
    pk = management_review_action_b.pk
    assert client_a.get(reverse("quality:management_review_action_detail", kwargs={"pk": pk})).status_code == 404
    assert client_a.get(reverse("quality:management_review_action_edit", kwargs={"pk": pk})).status_code == 404
    assert client_a.post(
        reverse("quality:management_review_action_edit", kwargs={"pk": pk}),
        {"title": "IDOR Action Edit"},
    ).status_code == 404
    assert client_a.post(reverse("quality:management_review_action_start", kwargs={"pk": pk})).status_code == 404
    assert client_a.post(
        reverse("quality:management_review_action_complete", kwargs={"pk": pk}),
        {"resolution_summary": "IDOR Resolution"},
    ).status_code == 404
    assert client_a.post(
        reverse("quality:management_review_action_verify", kwargs={"pk": pk}),
        {"verification_notes": "IDOR Verification"},
    ).status_code == 404
    assert client_a.post(reverse("quality:management_review_action_escalate_capa", kwargs={"pk": pk})).status_code == 404
    assert client_a.post(reverse("quality:management_review_action_delete", kwargs={"pk": pk})).status_code == 404


# ==============================================================================
# 3. TENANT QUERY ISOLATION (List Views & Dashboard)
# ==============================================================================

def test_managementreview_query_isolation_dashboard(
    client_a,
    client_b,
    quality_objective_a,
    quality_objective_b,
    management_review_a,
    management_review_b,
    management_review_action_a,
    management_review_action_b,
):
    """Verify dashboard isolates records by tenant."""
    resp_a = client_a.get(reverse("quality:quality_planning_dashboard"))
    assert resp_a.status_code == 200
    assert resp_a.context["total_objectives"] >= 1
    reviews_a = [r.pk for r in resp_a.context["upcoming_reviews"]]
    actions_a = [a.pk for a in resp_a.context["urgent_actions"]]
    assert management_review_a.pk in reviews_a
    assert management_review_b.pk not in reviews_a
    assert management_review_action_a.pk in actions_a
    assert management_review_action_b.pk not in actions_a

    resp_b = client_b.get(reverse("quality:quality_planning_dashboard"))
    assert resp_b.status_code == 200
    assert resp_b.context["total_objectives"] >= 1
    reviews_b = [r.pk for r in resp_b.context["upcoming_reviews"]]
    actions_b = [a.pk for a in resp_b.context["urgent_actions"]]
    assert management_review_b.pk in reviews_b
    assert management_review_a.pk not in reviews_b
    assert management_review_action_b.pk in actions_b
    assert management_review_action_a.pk not in actions_b


def test_managementreview_query_isolation_quality_objective_list(
    client_a, client_b, quality_objective_a, quality_objective_b
):
    """Verify QualityObjective list view enforces tenant query isolation."""
    resp_a = client_a.get(reverse("quality:quality_objective_list"))
    assert resp_a.status_code == 200
    pks_a = [o.pk for o in resp_a.context["objectives"]]
    assert quality_objective_a.pk in pks_a
    assert quality_objective_b.pk not in pks_a

    resp_b = client_b.get(reverse("quality:quality_objective_list"))
    assert resp_b.status_code == 200
    pks_b = [o.pk for o in resp_b.context["objectives"]]
    assert quality_objective_b.pk in pks_b
    assert quality_objective_a.pk not in pks_b


def test_managementreview_query_isolation_management_review_list(
    client_a, client_b, management_review_a, management_review_b
):
    """Verify ManagementReview list view enforces tenant query isolation."""
    resp_a = client_a.get(reverse("quality:management_review_list"))
    assert resp_a.status_code == 200
    pks_a = [r.pk for r in resp_a.context["reviews"]]
    assert management_review_a.pk in pks_a
    assert management_review_b.pk not in pks_a

    resp_b = client_b.get(reverse("quality:management_review_list"))
    assert resp_b.status_code == 200
    pks_b = [r.pk for r in resp_b.context["reviews"]]
    assert management_review_b.pk in pks_b
    assert management_review_a.pk not in pks_b


def test_managementreview_query_isolation_input_list(
    client_a, client_b, management_review_input_a, management_review_input_b
):
    """Verify ManagementReviewInput list view enforces tenant query isolation."""
    resp_a = client_a.get(reverse("quality:management_review_input_list"))
    assert resp_a.status_code == 200
    pks_a = [i.pk for i in resp_a.context["inputs"]]
    assert management_review_input_a.pk in pks_a
    assert management_review_input_b.pk not in pks_a

    resp_b = client_b.get(reverse("quality:management_review_input_list"))
    assert resp_b.status_code == 200
    pks_b = [i.pk for i in resp_b.context["inputs"]]
    assert management_review_input_b.pk in pks_b
    assert management_review_input_a.pk not in pks_b


def test_managementreview_query_isolation_action_list(
    client_a, client_b, management_review_action_a, management_review_action_b
):
    """Verify ManagementReviewAction list view enforces tenant query isolation."""
    resp_a = client_a.get(reverse("quality:management_review_action_list"))
    assert resp_a.status_code == 200
    pks_a = [a.pk for a in resp_a.context["actions"]]
    assert management_review_action_a.pk in pks_a
    assert management_review_action_b.pk not in pks_a

    resp_b = client_b.get(reverse("quality:management_review_action_list"))
    assert resp_b.status_code == 200
    pks_b = [a.pk for a in resp_b.context["actions"]]
    assert management_review_action_b.pk in pks_b
    assert management_review_action_a.pk not in pks_b


def test_managementreview_query_isolation_csv_exports(
    client_a,
    client_b,
    quality_objective_a,
    quality_objective_b,
    management_review_a,
    management_review_b,
    management_review_input_a,
    management_review_input_b,
    management_review_action_a,
    management_review_action_b,
):
    """Verify all CSV exports enforce strict tenant data isolation."""
    # Objectives CSV
    csv_obj_a = client_a.get(reverse("quality:quality_objective_export_csv")).content.decode("utf-8")
    assert quality_objective_a.title in csv_obj_a
    assert quality_objective_b.title not in csv_obj_a

    # Reviews CSV
    csv_rev_a = client_a.get(reverse("quality:management_review_export_csv")).content.decode("utf-8")
    assert management_review_a.title in csv_rev_a
    assert management_review_b.title not in csv_rev_a

    # Inputs CSV
    csv_inp_a = client_a.get(reverse("quality:management_review_input_export_csv")).content.decode("utf-8")
    assert management_review_input_a.title in csv_inp_a
    assert management_review_input_b.title not in csv_inp_a

    # Actions CSV
    csv_act_a = client_a.get(reverse("quality:management_review_action_export_csv")).content.decode("utf-8")
    assert management_review_action_a.title in csv_act_a
    assert management_review_action_b.title not in csv_act_a


# ==============================================================================
# 4. AUTHORIZATION & SEGREGATION OF DUTIES (SoD)
# ==============================================================================

def test_managementreview_executive_approval_member_blocked(
    member_client, client_a, management_review_a
):
    """Verify standard non-executive member cannot approve management review."""
    management_review_a.status = "meeting_active"
    management_review_a.qms_suitability_conclusion = "suitable_effective"
    management_review_a.save()

    url = reverse("quality:management_review_approve", kwargs={"pk": management_review_a.pk})

    # Non-executive member attempt
    resp_member = member_client.post(url, {"confirm_suitability": True})
    assert resp_member.status_code == 302
    assert resp_member.url == reverse("quality:management_review_detail", kwargs={"pk": management_review_a.pk})

    management_review_a.refresh_from_db()
    assert management_review_a.status == "meeting_active"
    assert management_review_a.approved_by is None

    # Executive sponsor / admin approval succeeds
    resp_admin = client_a.post(url, {"confirm_suitability": True, "comment": "Executive Sign-Off"})
    assert resp_admin.status_code == 302
    management_review_a.refresh_from_db()
    assert management_review_a.status == "approved"
    assert management_review_a.approved_by is not None


def test_managementreview_objective_evaluate_non_owner_blocked(
    member_client, client_a, quality_objective_a
):
    """Verify non-owner non-admin member cannot evaluate quality objective performance."""
    original_value = quality_objective_a.current_value
    url = reverse("quality:quality_objective_evaluate", kwargs={"pk": quality_objective_a.pk})

    # Member user is NOT owner (owner is admin_user) and NOT admin
    resp = member_client.post(url, {"current_value": "0.123", "notes": "Unauthorized eval"})
    assert resp.status_code == 302
    assert resp.url == reverse("quality:quality_objective_detail", kwargs={"pk": quality_objective_a.pk})

    quality_objective_a.refresh_from_db()
    assert quality_objective_a.current_value == original_value

    # Designated owner / admin evaluation succeeds
    resp_owner = client_a.post(url, {"current_value": "0.350", "notes": "Authorized evaluation"})
    assert resp_owner.status_code == 302
    quality_objective_a.refresh_from_db()
    assert quality_objective_a.current_value == Decimal("0.350")


def test_managementreview_action_verification_assignee_sod_enforced(
    member_client, client_a, admin_user, member_user, management_review_action_a
):
    """Verify assignee cannot verify their own action item (independent QA verification SoD)."""
    # Set assignee to member_user (who is a non-admin member)
    management_review_action_a.assignee = member_user
    management_review_action_a.status = "pending_verification"
    management_review_action_a.save()

    url = reverse("quality:management_review_action_verify", kwargs={"pk": management_review_action_a.pk})

    # Member user (the assignee) attempts self-verification -> blocked by SoD guard
    resp_self = member_client.post(
        url,
        {"verification_notes": "Attempting self-verification by assignee"},
    )
    assert resp_self.status_code == 302
    assert resp_self.url == reverse("quality:management_review_action_detail", kwargs={"pk": management_review_action_a.pk})

    management_review_action_a.refresh_from_db()
    assert management_review_action_a.status == "pending_verification"
    assert management_review_action_a.verified_by is None

    # Independent QA admin verifies -> succeeds
    resp_admin = client_a.post(
        url,
        {"verification_notes": "Independent verification by QA Director confirming effectiveness"},
    )
    assert resp_admin.status_code == 302
    management_review_action_a.refresh_from_db()
    assert management_review_action_a.status == "completed"
    assert management_review_action_a.verified_by == admin_user


# ==============================================================================
# 5. STATE TAMPERING & LIFECYCLE PROTECTION
# ==============================================================================

def test_managementreview_input_on_approved_review_tamper_blocked(
    client_a, management_review_a, management_review_input_a, admin_user
):
    """Verify cannot add, edit, present, accept, or delete ManagementReviewInput on an approved review."""
    management_review_a.status = "approved"
    management_review_a.save()

    # 1. Cannot add input via GET
    get_create_url = reverse("quality:management_review_input_create") + f"?review_id={management_review_a.pk}"
    resp_get = client_a.get(get_create_url)
    assert resp_get.status_code == 302
    assert resp_get.url == reverse("quality:management_review_detail", kwargs={"pk": management_review_a.pk})

    # 2. Cannot add input via POST
    post_create_data = {
        "management_review": management_review_a.pk,
        "title": "Tamper Input on Approved Review",
        "category": "risk_management",
        "agenda_order": 99,
        "presenter": admin_user.pk,
        "summary_findings": "Summary findings on closed review",
    }
    resp_post = client_a.post(reverse("quality:management_review_input_create"), post_create_data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("quality:management_review_detail", kwargs={"pk": management_review_a.pk})
    assert not ManagementReviewInput.objects.filter(title="Tamper Input on Approved Review").exists()

    # 3. Cannot edit input on approved review
    resp_edit = client_a.post(
        reverse("quality:management_review_input_edit", kwargs={"pk": management_review_input_a.pk}),
        {"title": "Modified Title Tamper"},
    )
    assert resp_edit.status_code == 302
    assert resp_edit.url == reverse("quality:management_review_input_detail", kwargs={"pk": management_review_input_a.pk})

    # 4. Cannot present or accept input on approved review
    resp_present = client_a.post(reverse("quality:management_review_input_present", kwargs={"pk": management_review_input_a.pk}))
    assert resp_present.status_code == 302
    resp_accept = client_a.post(reverse("quality:management_review_input_accept", kwargs={"pk": management_review_input_a.pk}))
    assert resp_accept.status_code == 302

    # 5. Cannot delete input on approved review
    resp_delete = client_a.post(reverse("quality:management_review_input_delete", kwargs={"pk": management_review_input_a.pk}))
    assert resp_delete.status_code == 302
    assert resp_delete.url == reverse("quality:management_review_detail", kwargs={"pk": management_review_a.pk})
    assert ManagementReviewInput.objects.filter(pk=management_review_input_a.pk).exists()


def test_managementreview_action_on_approved_review_tamper_blocked(
    client_a, management_review_a, management_review_action_a, staff_user
):
    """Verify cannot create, edit, or delete ManagementReviewAction on an approved review."""
    management_review_a.status = "approved"
    management_review_a.save()

    # 1. Cannot create action via GET
    get_create_url = reverse("quality:management_review_action_create") + f"?review_id={management_review_a.pk}"
    resp_get = client_a.get(get_create_url)
    assert resp_get.status_code == 302
    assert resp_get.url == reverse("quality:management_review_detail", kwargs={"pk": management_review_a.pk})

    # 2. Cannot create action via POST
    post_create_data = {
        "management_review": management_review_a.pk,
        "title": "Tamper Action on Approved Review",
        "action_type": "procedure_revision",
        "priority": "high",
        "assignee": staff_user.pk,
        "due_date": _managementreview_relative_date(30),
        "description": "Late action attempt",
    }
    resp_post = client_a.post(reverse("quality:management_review_action_create"), post_create_data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("quality:management_review_detail", kwargs={"pk": management_review_a.pk})
    assert not ManagementReviewAction.objects.filter(title="Tamper Action on Approved Review").exists()

    # 3. Cannot delete action under approved review
    resp_delete = client_a.post(reverse("quality:management_review_action_delete", kwargs={"pk": management_review_action_a.pk}))
    assert resp_delete.status_code == 302
    assert resp_delete.url == reverse("quality:management_review_action_detail", kwargs={"pk": management_review_action_a.pk})
    assert ManagementReviewAction.objects.filter(pk=management_review_action_a.pk).exists()


def test_managementreview_action_delete_completed_blocked(client_a, management_review_action_a):
    """Verify verified and completed action items cannot be deleted."""
    management_review_action_a.status = "completed"
    management_review_action_a.save()

    url = reverse("quality:management_review_action_delete", kwargs={"pk": management_review_action_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:management_review_action_detail", kwargs={"pk": management_review_action_a.pk})
    assert ManagementReviewAction.objects.filter(pk=management_review_action_a.pk).exists()


def test_managementreview_approved_review_immutable(client_a, management_review_a):
    """Verify approved ManagementReview cannot be edited, cancelled, or deleted."""
    management_review_a.status = "approved"
    management_review_a.save()

    pk = management_review_a.pk

    # Cannot edit
    resp_edit_get = client_a.get(reverse("quality:management_review_edit", kwargs={"pk": pk}))
    assert resp_edit_get.status_code == 302
    assert resp_edit_get.url == reverse("quality:management_review_detail", kwargs={"pk": pk})

    # Cannot cancel
    resp_cancel = client_a.post(reverse("quality:management_review_cancel", kwargs={"pk": pk}))
    assert resp_cancel.status_code == 302
    assert resp_cancel.url == reverse("quality:management_review_detail", kwargs={"pk": pk})

    # Cannot delete
    resp_delete = client_a.post(reverse("quality:management_review_delete", kwargs={"pk": pk}))
    assert resp_delete.status_code == 302
    assert resp_delete.url == reverse("quality:management_review_detail", kwargs={"pk": pk})
    assert ManagementReview.objects.filter(pk=pk).exists()


def test_managementreview_draft_minutes_unstarted_blocked(client_a, management_review_a):
    """Verify cannot draft minutes for unstarted/scheduled review."""
    management_review_a.status = "scheduled"
    management_review_a.save()

    url = reverse("quality:management_review_draft_minutes", kwargs={"pk": management_review_a.pk})

    # GET is blocked
    resp_get = client_a.get(url)
    assert resp_get.status_code == 302
    assert resp_get.url == reverse("quality:management_review_detail", kwargs={"pk": management_review_a.pk})

    # POST is blocked
    resp_post = client_a.post(url, {"minutes_discussion": "Premature minutes recording"})
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("quality:management_review_detail", kwargs={"pk": management_review_a.pk})


def test_managementreview_approve_pending_suitability_blocked(client_a, management_review_a):
    """Verify cannot approve review before executive QMS suitability conclusion is recorded."""
    management_review_a.status = "meeting_active"
    management_review_a.qms_suitability_conclusion = "pending"
    management_review_a.save()

    url = reverse("quality:management_review_approve", kwargs={"pk": management_review_a.pk})
    resp = client_a.post(url, {"confirm_suitability": True, "comment": "Premature signoff"})
    assert resp.status_code == 302
    assert resp.url == reverse("quality:management_review_detail", kwargs={"pk": management_review_a.pk})

    management_review_a.refresh_from_db()
    assert management_review_a.status == "meeting_active"
    assert management_review_a.approved_by is None


# ==============================================================================
# 6. CROSS-TENANT FOREIGN KEY INJECTION
# ==============================================================================

def test_managementreview_fk_injection_quality_objective(
    client_a, quality_department_b, admin_b
):
    """Verify cross-tenant foreign key injection on QualityObjective is rejected."""
    today = timezone.now().date()

    # Attempt to inject Tenant B org_unit
    data_bad_dept = {
        "title": "Injected Department Objective",
        "category": "product_quality",
        "period_year": today.year,
        "cadence": "quarterly",
        "metric_unit": "%",
        "baseline_value": "1.000",
        "target_value": "0.500",
        "target_direction": "lower_better",
        "status": "on_track",
        "org_unit": quality_department_b.pk,
        "target_date": today + timedelta(days=90),
    }
    resp = client_a.post(reverse("quality:quality_objective_create"), data_bad_dept)
    assert resp.status_code == 200
    assert "org_unit" in resp.context["form"].errors

    # Attempt to inject Tenant B owner
    data_bad_owner = {
        "title": "Injected Owner Objective",
        "category": "product_quality",
        "period_year": today.year,
        "cadence": "quarterly",
        "metric_unit": "%",
        "baseline_value": "1.000",
        "target_value": "0.500",
        "target_direction": "lower_better",
        "status": "on_track",
        "owner": admin_b.pk,
        "target_date": today + timedelta(days=90),
    }
    resp_owner = client_a.post(reverse("quality:quality_objective_create"), data_bad_owner)
    assert resp_owner.status_code == 200
    assert "owner" in resp_owner.context["form"].errors


def test_managementreview_fk_injection_management_review(
    client_a, quality_department_b, admin_b, admin_user
):
    """Verify cross-tenant foreign key injection on ManagementReview is rejected."""
    today = timezone.now().date()

    # Injected OrgUnit
    data_org = {
        "title": "Injected OrgUnit Review",
        "cadence": "quarterly",
        "period_start": today - timedelta(days=90),
        "period_end": today,
        "scheduled_date": today + timedelta(days=14),
        "executive_sponsor": admin_user.pk,
        "lead_facilitator": admin_user.pk,
        "org_unit": quality_department_b.pk,
    }
    resp_org = client_a.post(reverse("quality:management_review_create"), data_org)
    assert resp_org.status_code == 200
    assert "org_unit" in resp_org.context["form"].errors

    # Injected Executive Sponsor
    data_sponsor = {
        "title": "Injected Sponsor Review",
        "cadence": "quarterly",
        "period_start": today - timedelta(days=90),
        "period_end": today,
        "scheduled_date": today + timedelta(days=14),
        "executive_sponsor": admin_b.pk,
        "lead_facilitator": admin_user.pk,
    }
    resp_sponsor = client_a.post(reverse("quality:management_review_create"), data_sponsor)
    assert resp_sponsor.status_code == 200
    assert "executive_sponsor" in resp_sponsor.context["form"].errors


def test_managementreview_fk_injection_review_input(
    client_a, management_review_a, management_review_b, admin_user, admin_b
):
    """Verify cross-tenant foreign key injection on ManagementReviewInput is rejected."""
    # Injected parent ManagementReview (from Tenant B)
    data_bad_rev = {
        "management_review": management_review_b.pk,
        "title": "Input linked to Tenant B Review",
        "category": "audit_results",
        "agenda_order": 1,
        "presenter": admin_user.pk,
        "summary_findings": "Summary test",
    }
    resp_rev = client_a.post(reverse("quality:management_review_input_create"), data_bad_rev)
    assert resp_rev.status_code == 200
    assert "management_review" in resp_rev.context["form"].errors

    # Injected presenter (from Tenant B)
    data_bad_pres = {
        "management_review": management_review_a.pk,
        "title": "Input with Tenant B Presenter",
        "category": "audit_results",
        "agenda_order": 1,
        "presenter": admin_b.pk,
        "summary_findings": "Summary test",
    }
    resp_pres = client_a.post(reverse("quality:management_review_input_create"), data_bad_pres)
    assert resp_pres.status_code == 200
    assert "presenter" in resp_pres.context["form"].errors


def test_managementreview_fk_injection_review_action(
    client_a, management_review_a, management_review_b, staff_user, admin_b
):
    """Verify cross-tenant foreign key injection on ManagementReviewAction is rejected."""
    today = timezone.now().date()

    # Injected parent ManagementReview (from Tenant B)
    data_bad_rev = {
        "management_review": management_review_b.pk,
        "title": "Action linked to Tenant B Review",
        "action_type": "qms_improvement",
        "priority": "high",
        "assignee": staff_user.pk,
        "due_date": today + timedelta(days=30),
        "description": "Cross-tenant review action injection",
    }
    resp_rev = client_a.post(reverse("quality:management_review_action_create"), data_bad_rev)
    assert resp_rev.status_code == 200
    assert "management_review" in resp_rev.context["form"].errors

    # Injected assignee (from Tenant B)
    data_bad_assignee = {
        "management_review": management_review_a.pk,
        "title": "Action assigned to Tenant B User",
        "action_type": "qms_improvement",
        "priority": "high",
        "assignee": admin_b.pk,
        "due_date": today + timedelta(days=30),
        "description": "Cross-tenant assignee injection",
    }
    resp_assignee = client_a.post(reverse("quality:management_review_action_create"), data_bad_assignee)
    assert resp_assignee.status_code == 200
    assert "assignee" in resp_assignee.context["form"].errors


# ==============================================================================
# 7. HTTP METHOD ENFORCEMENT (Reject GET with 405 Method Not Allowed)
# ==============================================================================

def test_managementreview_mutating_actions_reject_get_with_405(
    client_a,
    quality_objective_a,
    management_review_a,
    management_review_input_a,
    management_review_action_a,
):
    """Verify all state-mutating POST-only endpoints reject GET requests with HTTP 405."""
    mutating_urls = [
        # Quality Objective actions
        reverse("quality:quality_objective_evaluate", kwargs={"pk": quality_objective_a.pk}),
        reverse("quality:quality_objective_delete", kwargs={"pk": quality_objective_a.pk}),
        # Management Review actions
        reverse("quality:management_review_start", kwargs={"pk": management_review_a.pk}),
        reverse("quality:management_review_approve", kwargs={"pk": management_review_a.pk}),
        reverse("quality:management_review_cancel", kwargs={"pk": management_review_a.pk}),
        reverse("quality:management_review_delete", kwargs={"pk": management_review_a.pk}),
        # Review Input actions
        reverse("quality:management_review_input_present", kwargs={"pk": management_review_input_a.pk}),
        reverse("quality:management_review_input_accept", kwargs={"pk": management_review_input_a.pk}),
        reverse("quality:management_review_input_delete", kwargs={"pk": management_review_input_a.pk}),
        # Review Action actions
        reverse("quality:management_review_action_start", kwargs={"pk": management_review_action_a.pk}),
        reverse("quality:management_review_action_complete", kwargs={"pk": management_review_action_a.pk}),
        reverse("quality:management_review_action_verify", kwargs={"pk": management_review_action_a.pk}),
        reverse("quality:management_review_action_escalate_capa", kwargs={"pk": management_review_action_a.pk}),
        reverse("quality:management_review_action_delete", kwargs={"pk": management_review_action_a.pk}),
    ]

    for url in mutating_urls:
        resp = client_a.get(url)
        assert resp.status_code == 405, f"Expected 405 Method Not Allowed for GET {url}, got {resp.status_code}"
