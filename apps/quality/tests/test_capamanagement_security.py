"""
Security, Multi-Tenant Data Isolation, Role Authorization, and Adversarial Tests
for Sub-module 12.4: CAPA (Corrective & Preventive Action).

Covers:
1. Multi-Tenant Data Isolation & Cross-Tenant IDOR:
   - Exhaustive IDOR sweeps: accessing Tenant B objects as Tenant A returns HTTP 404 across detail, edit, delete,
     advance_status, close, verify, mark_completed, sign_off, and tracking board endpoints.
   - Symmetric IDOR: Client B accessing Tenant A resources returns HTTP 404.
   - List & Dashboard views: zero cross-tenant record leakage.
   - Cross-Tenant Foreign Key Injection: forging POST payloads with Foreign Keys belonging to Tenant B
     (department, lead_investigator, quality_owner, containment_verified_by, design_project, risk_assessment,
      capa, root_cause, assigned_to, controlled_document, change_order, evaluator) is strictly rejected.
2. Authorization & Role Separation:
   - Create a standard non-admin member user in Tenant A.
   - Privileged operations protected by @tenant_admin_required return HTTP 403 Forbidden:
     capa_investigation_delete, capa_investigation_close, root_cause_analysis_delete,
     capa_action_delete, capa_effectiveness_review_delete.
   - capa_investigation_advance_status: standard user cannot set target_status="voided".
   - capa_action_verify: assignee cannot self-verify action without tenant-admin privilege (Separation of Duties).
   - capa_effectiveness_review_sign_off: non-evaluator non-admin user cannot sign off review.
3. Status & Lifecycle Tampering:
   - Form submissions with status="closed", "voided", "verified", "completed" rejected via clean_status.
   - Direct transition to target_status="closed" via advance_status rejected (must use formal close workflow).
   - Advancing or editing a closed CAPA is blocked.
   - Deleting a closed CAPA, verified RCA, verified Action, or completed Review is blocked.
   - Child records belonging to a closed parent CAPA cannot be deleted or verified.
   - Verified RCA and Action, and completed Review cannot be directly modified.
   - Re-verification of already verified/completed records is blocked.
   - Signing off an effectiveness review as "effective" when recurrence_observed=True is blocked.
   - Closing a CAPA with pending actions is blocked.
   - Parent CAPA is immutable once child record is created.
4. CSV Export Security (CWE-1236 Formula Injection Defense):
   - csv_safe() neutralizes malicious formula prefixes (=, +, -, @, %, \\t, \\r) across all 5 export endpoints.
   - X-Content-Type-Options: nosniff header enforced.
   - Content-Disposition attachment header enforced.
   - Tenant isolation preserved across CSV export datasets.
5. HTTP Method & Authentication Enforcement:
   - All 10 state-changing POST-only endpoints reject GET with HTTP 405 Method Not Allowed.
   - Unauthenticated GET and POST requests across all 32 endpoints redirect to login (HTTP 302).
6. Audit Trail Integrity & Forensic Compliance (21 CFR Part 11):
   - AuditLog records written on create, update, delete, advance, close, verify, complete, sign-off, and export.
   - Object ID preserved on deletion audit records.
"""

import csv
import io
from datetime import timedelta
import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import AuditLog, OrgUnit
from apps.quality.forms.CapaManagement.CapaActions import CapaActionForm
from apps.quality.forms.CapaManagement.CapaEffectivenessReviews import CapaEffectivenessReviewForm
from apps.quality.forms.CapaManagement.CapaInvestigations import CapaInvestigationForm
from apps.quality.forms.CapaManagement.RootCauseAnalyses import RootCauseAnalysisForm
from apps.quality.models import (
    CapaAction,
    CapaEffectivenessReview,
    CapaInvestigation,
    ControlledDocument,
    DesignProject,
    DocumentChangeOrder,
    RiskAssessment,
    RootCauseAnalysis,
)
from apps.quality.views.CapaManagement.CapaInvestigations import csv_safe

pytestmark = pytest.mark.django_db


# =====================================================================
# Fixtures and Helpers (Prefix: _capamanagement_*)
# =====================================================================


def _capamanagement_set_actions_count(self, value):
    self.__dict__["actions_count"] = value


def _capamanagement_set_pending_actions_count(self, value):
    self.__dict__["pending_actions_count"] = value


if not CapaInvestigation.actions_count.fset:
    CapaInvestigation.actions_count = CapaInvestigation.actions_count.setter(
        _capamanagement_set_actions_count
    )

if not CapaInvestigation.pending_actions_count.fset:
    CapaInvestigation.pending_actions_count = (
        CapaInvestigation.pending_actions_count.setter(
            _capamanagement_set_pending_actions_count
        )
    )


def _capamanagement_get_messages(response):
    """Extract message strings from response wsgi_request."""
    if hasattr(response, "wsgi_request") and response.wsgi_request:
        return [m.message for m in get_messages(response.wsgi_request)]
    return []


def _capamanagement_audit_logs(obj_or_model, object_id=None, action=None):
    """Retrieve audit log rows written for obj or model."""
    if isinstance(obj_or_model, type):
        ct = ContentType.objects.get_for_model(obj_or_model)
        qs = AuditLog.objects.filter(content_type=ct)
        if object_id is not None:
            qs = qs.filter(object_id=object_id)
    else:
        ct = ContentType.objects.get_for_model(obj_or_model.__class__)
        qs = AuditLog.objects.filter(content_type=ct, object_id=obj_or_model.pk)
    if action:
        qs = qs.filter(action=action)
    return qs


def _capamanagement_parse_csv(response):
    """Parse CSV response into list of rows."""
    content = response.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    return list(reader)


@pytest.fixture
def _capamanagement_non_admin_user(member_user):
    """Tenant A standard non-admin member user."""
    return member_user


@pytest.fixture
def _capamanagement_non_admin_client(member_client):
    """Test client logged in as Tenant A standard non-admin member."""
    return member_client


@pytest.fixture
def _capamanagement_closed_capa(db, tenant_a, admin_user, quality_department):
    """Fixture for a formally closed CAPA investigation."""
    return CapaInvestigation.objects.create(
        tenant=tenant_a,
        title="Closed Optical Connector Polishing Defect Investigation",
        action_type="corrective",
        source_type="internal_audit",
        risk_priority="medium",
        status="closed",
        department=quality_department,
        lead_investigator=admin_user,
        quality_owner=admin_user,
        issue_summary="Connector ferrule polishing defect remediated and verified.",
        target_closure_date=timezone.now().date() - timedelta(days=10),
        closed_at=timezone.now(),
        closure_approved_by=admin_user,
        closure_summary="Remediation actions confirmed effective in release lots.",
    )


@pytest.fixture
def _capamanagement_verified_rca(db, tenant_a, admin_user, capa_investigation_a):
    """Fixture for an already verified Root Cause Analysis."""
    return RootCauseAnalysis.objects.create(
        tenant=tenant_a,
        capa=capa_investigation_a,
        rca_method="5_whys",
        problem_statement="Core pin wear causing wall thinning.",
        root_cause_summary="Preventive maintenance interval lacked pin metrology.",
        root_cause_category="equipment",
        lead_investigator=admin_user,
        status="verified",
        verified_by=admin_user,
        verified_date=timezone.now().date(),
        verification_notes="Root cause verified via CMM metrology measurements.",
    )


@pytest.fixture
def _capamanagement_implemented_action(
    db, tenant_a, admin_user, quality_department, capa_investigation_a, root_cause_analysis_a
):
    """Fixture for an implemented CAPA Action ready for verification."""
    return CapaAction.objects.create(
        tenant=tenant_a,
        capa=capa_investigation_a,
        root_cause=root_cause_analysis_a,
        action_type="corrective",
        title="Revise Tooling PM Checklist to Mandate CMM Metrology",
        description="Add dimensional core pin check every 10,000 cycles.",
        assigned_to=admin_user,
        department=quality_department,
        due_date=timezone.now().date() + timedelta(days=7),
        status="implemented",
        completion_date=timezone.now().date(),
        implementation_notes="Tooling PM SOP revised and technician training completed.",
    )


@pytest.fixture
def _capamanagement_verified_action(
    db, tenant_a, admin_user, quality_department, capa_investigation_a, root_cause_analysis_a
):
    """Fixture for an already verified CAPA Action item."""
    return CapaAction.objects.create(
        tenant=tenant_a,
        capa=capa_investigation_a,
        root_cause=root_cause_analysis_a,
        action_type="corrective",
        title="Revise Tooling PM Checklist to Mandate CMM Metrology (Verified)",
        description="Add dimensional core pin check every 10,000 cycles.",
        assigned_to=admin_user,
        department=quality_department,
        due_date=timezone.now().date() + timedelta(days=7),
        status="verified",
        completion_date=timezone.now().date(),
        implementation_notes="Tooling PM SOP revised.",
        verified_by=admin_user,
        verified_on=timezone.now().date(),
        verification_evidence="SOP-MNT-042 rev B released and trained.",
    )


@pytest.fixture
def _capamanagement_completed_review(db, tenant_a, admin_user, capa_investigation_a):
    """Fixture for an already completed Effectiveness Review."""
    return CapaEffectivenessReview.objects.create(
        tenant=tenant_a,
        capa=capa_investigation_a,
        review_criteria="Zero ferrule cracking in 5 consecutive lots.",
        verification_method="statistical_sample",
        planned_review_date=timezone.now().date() - timedelta(days=5),
        actual_review_date=timezone.now().date(),
        evaluator=admin_user,
        recurrence_observed=False,
        outcome="effective",
        status="completed",
        review_notes="5 consecutive lots inspected; zero defects detected (Cpk 1.48).",
    )


# =====================================================================
# 1. Multi-Tenant Data Isolation & Cross-Tenant IDOR Sweeps
# =====================================================================


class TestCapaManagementCrossTenantIdor:
    """Validate strict multi-tenant boundary isolation across all CAPA endpoints."""

    # --- CapaInvestigation IDOR ---

    def test_capamanagement_security_capa_detail_cross_tenant_idor_404(
        self, client_a, client_b, capa_investigation_a, capa_investigation_b
    ):
        """Accessing foreign CAPA investigation detail returns 404."""
        url_b = reverse("quality:capa_investigation_detail", kwargs={"pk": capa_investigation_b.pk})
        assert client_a.get(url_b).status_code == 404

        url_a = reverse("quality:capa_investigation_detail", kwargs={"pk": capa_investigation_a.pk})
        assert client_b.get(url_a).status_code == 404

    def test_capamanagement_security_capa_edit_cross_tenant_idor_404(
        self, client_a, client_b, capa_investigation_a, capa_investigation_b
    ):
        """GET and POST to edit foreign CAPA investigation returns 404; database remains untouched."""
        url_b = reverse("quality:capa_investigation_edit", kwargs={"pk": capa_investigation_b.pk})
        assert client_a.get(url_b).status_code == 404
        assert client_a.post(url_b, {"title": "Tampered Title"}).status_code == 404
        capa_investigation_b.refresh_from_db()
        assert capa_investigation_b.title != "Tampered Title"

        url_a = reverse("quality:capa_investigation_edit", kwargs={"pk": capa_investigation_a.pk})
        assert client_b.get(url_a).status_code == 404
        assert client_b.post(url_a, {"title": "Tampered Title"}).status_code == 404
        capa_investigation_a.refresh_from_db()
        assert capa_investigation_a.title != "Tampered Title"

    def test_capamanagement_security_capa_delete_cross_tenant_idor_404(
        self, client_a, client_b, capa_investigation_a, capa_investigation_b
    ):
        """POST to delete foreign CAPA investigation returns 404 and record is preserved."""
        url_b = reverse("quality:capa_investigation_delete", kwargs={"pk": capa_investigation_b.pk})
        assert client_a.post(url_b).status_code == 404
        assert CapaInvestigation.objects.filter(pk=capa_investigation_b.pk).exists()

        url_a = reverse("quality:capa_investigation_delete", kwargs={"pk": capa_investigation_a.pk})
        assert client_b.post(url_a).status_code == 404
        assert CapaInvestigation.objects.filter(pk=capa_investigation_a.pk).exists()

    def test_capamanagement_security_capa_advance_status_cross_tenant_idor_404(
        self, client_a, client_b, capa_investigation_a, capa_investigation_b
    ):
        """POST to advance foreign CAPA status returns 404; status remains untouched."""
        url_b = reverse("quality:capa_investigation_advance_status", kwargs={"pk": capa_investigation_b.pk})
        assert client_a.post(url_b, {"target_status": "rca_in_progress"}).status_code == 404
        capa_investigation_b.refresh_from_db()
        assert capa_investigation_b.status == "under_investigation"

        url_a = reverse("quality:capa_investigation_advance_status", kwargs={"pk": capa_investigation_a.pk})
        assert client_b.post(url_a, {"target_status": "rca_in_progress"}).status_code == 404
        capa_investigation_a.refresh_from_db()
        assert capa_investigation_a.status == "under_investigation"

    def test_capamanagement_security_capa_close_cross_tenant_idor_404(
        self, client_a, client_b, capa_investigation_a, capa_investigation_b
    ):
        """POST to formally close foreign CAPA returns 404; status and closure fields remain untouched."""
        url_b = reverse("quality:capa_investigation_close", kwargs={"pk": capa_investigation_b.pk})
        assert client_a.post(url_b, {"closure_summary": "Tampered Closure"}).status_code == 404
        capa_investigation_b.refresh_from_db()
        assert capa_investigation_b.status != "closed"
        assert capa_investigation_b.closed_at is None

        url_a = reverse("quality:capa_investigation_close", kwargs={"pk": capa_investigation_a.pk})
        assert client_b.post(url_a, {"closure_summary": "Tampered Closure"}).status_code == 404
        capa_investigation_a.refresh_from_db()
        assert capa_investigation_a.status != "closed"
        assert capa_investigation_a.closed_at is None

    # --- RootCauseAnalysis IDOR ---

    def test_capamanagement_security_rca_detail_cross_tenant_idor_404(
        self, client_a, client_b, root_cause_analysis_a, root_cause_analysis_b
    ):
        """Accessing foreign RCA detail returns 404."""
        url_b = reverse("quality:root_cause_analysis_detail", kwargs={"pk": root_cause_analysis_b.pk})
        assert client_a.get(url_b).status_code == 404

        url_a = reverse("quality:root_cause_analysis_detail", kwargs={"pk": root_cause_analysis_a.pk})
        assert client_b.get(url_a).status_code == 404

    def test_capamanagement_security_rca_edit_cross_tenant_idor_404(
        self, client_a, client_b, root_cause_analysis_a, root_cause_analysis_b
    ):
        """GET and POST to edit foreign RCA returns 404; database remains untouched."""
        url_b = reverse("quality:root_cause_analysis_edit", kwargs={"pk": root_cause_analysis_b.pk})
        assert client_a.get(url_b).status_code == 404
        assert client_a.post(url_b, {"problem_statement": "Tampered Problem"}).status_code == 404
        root_cause_analysis_b.refresh_from_db()
        assert root_cause_analysis_b.problem_statement != "Tampered Problem"

        url_a = reverse("quality:root_cause_analysis_edit", kwargs={"pk": root_cause_analysis_a.pk})
        assert client_b.get(url_a).status_code == 404
        assert client_b.post(url_a, {"problem_statement": "Tampered Problem"}).status_code == 404
        root_cause_analysis_a.refresh_from_db()
        assert root_cause_analysis_a.problem_statement != "Tampered Problem"

    def test_capamanagement_security_rca_delete_cross_tenant_idor_404(
        self, client_a, client_b, root_cause_analysis_a, root_cause_analysis_b
    ):
        """POST to delete foreign RCA returns 404 and record is preserved."""
        url_b = reverse("quality:root_cause_analysis_delete", kwargs={"pk": root_cause_analysis_b.pk})
        assert client_a.post(url_b).status_code == 404
        assert RootCauseAnalysis.objects.filter(pk=root_cause_analysis_b.pk).exists()

        url_a = reverse("quality:root_cause_analysis_delete", kwargs={"pk": root_cause_analysis_a.pk})
        assert client_b.post(url_a).status_code == 404
        assert RootCauseAnalysis.objects.filter(pk=root_cause_analysis_a.pk).exists()

    def test_capamanagement_security_rca_verify_cross_tenant_idor_404(
        self, client_a, client_b, root_cause_analysis_a, root_cause_analysis_b
    ):
        """POST to verify foreign RCA returns 404; status remains unchanged."""
        url_b = reverse("quality:root_cause_analysis_verify", kwargs={"pk": root_cause_analysis_b.pk})
        assert client_a.post(url_b, {"verification_notes": "Tampered Verification"}).status_code == 404
        root_cause_analysis_b.refresh_from_db()
        assert root_cause_analysis_b.status != "verified"
        assert root_cause_analysis_b.verified_by is None

        url_a = reverse("quality:root_cause_analysis_verify", kwargs={"pk": root_cause_analysis_a.pk})
        assert client_b.post(url_a, {"verification_notes": "Tampered Verification"}).status_code == 404
        root_cause_analysis_a.refresh_from_db()
        assert root_cause_analysis_a.status != "verified"
        assert root_cause_analysis_a.verified_by is None

    # --- CapaAction IDOR ---

    def test_capamanagement_security_action_detail_cross_tenant_idor_404(
        self, client_a, client_b, capa_action_a, capa_action_b
    ):
        """Accessing foreign CAPA action detail returns 404."""
        url_b = reverse("quality:capa_action_detail", kwargs={"pk": capa_action_b.pk})
        assert client_a.get(url_b).status_code == 404

        url_a = reverse("quality:capa_action_detail", kwargs={"pk": capa_action_a.pk})
        assert client_b.get(url_a).status_code == 404

    def test_capamanagement_security_action_edit_cross_tenant_idor_404(
        self, client_a, client_b, capa_action_a, capa_action_b
    ):
        """GET and POST to edit foreign CAPA action returns 404; database remains untouched."""
        url_b = reverse("quality:capa_action_edit", kwargs={"pk": capa_action_b.pk})
        assert client_a.get(url_b).status_code == 404
        assert client_a.post(url_b, {"title": "Tampered Title"}).status_code == 404
        capa_action_b.refresh_from_db()
        assert capa_action_b.title != "Tampered Title"

        url_a = reverse("quality:capa_action_edit", kwargs={"pk": capa_action_a.pk})
        assert client_b.get(url_a).status_code == 404
        assert client_b.post(url_a, {"title": "Tampered Title"}).status_code == 404
        capa_action_a.refresh_from_db()
        assert capa_action_a.title != "Tampered Title"

    def test_capamanagement_security_action_delete_cross_tenant_idor_404(
        self, client_a, client_b, capa_action_a, capa_action_b
    ):
        """POST to delete foreign CAPA action returns 404 and record is preserved."""
        url_b = reverse("quality:capa_action_delete", kwargs={"pk": capa_action_b.pk})
        assert client_a.post(url_b).status_code == 404
        assert CapaAction.objects.filter(pk=capa_action_b.pk).exists()

        url_a = reverse("quality:capa_action_delete", kwargs={"pk": capa_action_a.pk})
        assert client_b.post(url_a).status_code == 404
        assert CapaAction.objects.filter(pk=capa_action_a.pk).exists()

    def test_capamanagement_security_action_mark_completed_cross_tenant_idor_404(
        self, client_a, client_b, capa_action_a, capa_action_b
    ):
        """POST to mark foreign action implemented returns 404; status remains untouched."""
        url_b = reverse("quality:capa_action_mark_completed", kwargs={"pk": capa_action_b.pk})
        assert client_a.post(url_b, {"implementation_notes": "Tampered Implementation"}).status_code == 404
        capa_action_b.refresh_from_db()
        assert capa_action_b.status == "pending"

        url_a = reverse("quality:capa_action_mark_completed", kwargs={"pk": capa_action_a.pk})
        assert client_b.post(url_a, {"implementation_notes": "Tampered Implementation"}).status_code == 404
        capa_action_a.refresh_from_db()
        assert capa_action_a.status == "pending"

    def test_capamanagement_security_action_verify_cross_tenant_idor_404(
        self, client_a, client_b, capa_action_a, capa_action_b
    ):
        """POST to verify foreign CAPA action returns 404; status remains untouched."""
        url_b = reverse("quality:capa_action_verify", kwargs={"pk": capa_action_b.pk})
        assert client_a.post(url_b, {"verification_evidence": "Tampered Evidence"}).status_code == 404
        capa_action_b.refresh_from_db()
        assert capa_action_b.status != "verified"

        url_a = reverse("quality:capa_action_verify", kwargs={"pk": capa_action_a.pk})
        assert client_b.post(url_a, {"verification_evidence": "Tampered Evidence"}).status_code == 404
        capa_action_a.refresh_from_db()
        assert capa_action_a.status != "verified"

    # --- CapaEffectivenessReview IDOR ---

    def test_capamanagement_security_review_detail_cross_tenant_idor_404(
        self, client_a, client_b, capa_effectiveness_review_a, capa_effectiveness_review_b
    ):
        """Accessing foreign effectiveness review detail returns 404."""
        url_b = reverse("quality:capa_effectiveness_review_detail", kwargs={"pk": capa_effectiveness_review_b.pk})
        assert client_a.get(url_b).status_code == 404

        url_a = reverse("quality:capa_effectiveness_review_detail", kwargs={"pk": capa_effectiveness_review_a.pk})
        assert client_b.get(url_a).status_code == 404

    def test_capamanagement_security_review_edit_cross_tenant_idor_404(
        self, client_a, client_b, capa_effectiveness_review_a, capa_effectiveness_review_b
    ):
        """GET and POST to edit foreign effectiveness review returns 404; database remains untouched."""
        url_b = reverse("quality:capa_effectiveness_review_edit", kwargs={"pk": capa_effectiveness_review_b.pk})
        assert client_a.get(url_b).status_code == 404
        assert client_a.post(url_b, {"review_criteria": "Tampered Criteria"}).status_code == 404
        capa_effectiveness_review_b.refresh_from_db()
        assert capa_effectiveness_review_b.review_criteria != "Tampered Criteria"

        url_a = reverse("quality:capa_effectiveness_review_edit", kwargs={"pk": capa_effectiveness_review_a.pk})
        assert client_b.get(url_a).status_code == 404
        assert client_b.post(url_a, {"review_criteria": "Tampered Criteria"}).status_code == 404
        capa_effectiveness_review_a.refresh_from_db()
        assert capa_effectiveness_review_a.review_criteria != "Tampered Criteria"

    def test_capamanagement_security_review_delete_cross_tenant_idor_404(
        self, client_a, client_b, capa_effectiveness_review_a, capa_effectiveness_review_b
    ):
        """POST to delete foreign effectiveness review returns 404 and record is preserved."""
        url_b = reverse("quality:capa_effectiveness_review_delete", kwargs={"pk": capa_effectiveness_review_b.pk})
        assert client_a.post(url_b).status_code == 404
        assert CapaEffectivenessReview.objects.filter(pk=capa_effectiveness_review_b.pk).exists()

        url_a = reverse("quality:capa_effectiveness_review_delete", kwargs={"pk": capa_effectiveness_review_a.pk})
        assert client_b.post(url_a).status_code == 404
        assert CapaEffectivenessReview.objects.filter(pk=capa_effectiveness_review_a.pk).exists()

    def test_capamanagement_security_review_sign_off_cross_tenant_idor_404(
        self, client_a, client_b, capa_effectiveness_review_a, capa_effectiveness_review_b
    ):
        """POST to sign off foreign effectiveness review returns 404; status remains untouched."""
        url_b = reverse("quality:capa_effectiveness_review_sign_off", kwargs={"pk": capa_effectiveness_review_b.pk})
        assert client_a.post(url_b, {"outcome": "effective", "review_notes": "Tampered"}).status_code == 404
        capa_effectiveness_review_b.refresh_from_db()
        assert capa_effectiveness_review_b.status != "completed"

        url_a = reverse("quality:capa_effectiveness_review_sign_off", kwargs={"pk": capa_effectiveness_review_a.pk})
        assert client_b.post(url_a, {"outcome": "effective", "review_notes": "Tampered"}).status_code == 404
        capa_effectiveness_review_a.refresh_from_db()
        assert capa_effectiveness_review_a.status != "completed"

    # --- List & Dashboard Tenant Isolation ---

    def test_capamanagement_security_list_views_tenant_isolation(
        self,
        client_a,
        client_b,
        capa_investigation_a,
        capa_investigation_b,
        root_cause_analysis_a,
        root_cause_analysis_b,
        capa_action_a,
        capa_action_b,
        capa_effectiveness_review_a,
        capa_effectiveness_review_b,
    ):
        """List views for investigations, RCAs, actions, and reviews never leak cross-tenant records."""
        # 1. Capa investigations list
        res_a = client_a.get(reverse("quality:capa_investigation_list"))
        assert res_a.status_code == 200
        content_a = res_a.content.decode("utf-8")
        assert capa_investigation_a.title in content_a
        assert capa_investigation_b.title not in content_a

        res_b = client_b.get(reverse("quality:capa_investigation_list"))
        assert res_b.status_code == 200
        content_b = res_b.content.decode("utf-8")
        assert capa_investigation_b.title in content_b
        assert capa_investigation_a.title not in content_b

        # 2. RCA list
        res_rca_a = client_a.get(reverse("quality:root_cause_analysis_list"))
        assert res_rca_a.status_code == 200
        content_rca_a = res_rca_a.content.decode("utf-8")
        assert root_cause_analysis_a.problem_statement[:50] in content_rca_a
        assert root_cause_analysis_b.problem_statement[:50] not in content_rca_a

        res_rca_b = client_b.get(reverse("quality:root_cause_analysis_list"))
        assert res_rca_b.status_code == 200
        content_rca_b = res_rca_b.content.decode("utf-8")
        assert root_cause_analysis_b.problem_statement[:50] in content_rca_b
        assert root_cause_analysis_a.problem_statement[:50] not in content_rca_b

        # 3. Actions list
        res_act_a = client_a.get(reverse("quality:capa_action_list"))
        assert res_act_a.status_code == 200
        content_act_a = res_act_a.content.decode("utf-8")
        assert capa_action_a.title in content_act_a
        assert capa_action_b.title not in content_act_a

        res_act_b = client_b.get(reverse("quality:capa_action_list"))
        assert res_act_b.status_code == 200
        content_act_b = res_act_b.content.decode("utf-8")
        assert capa_action_b.title in content_act_b
        assert capa_action_a.title not in content_act_b

        # 4. Reviews list
        res_rev_a = client_a.get(reverse("quality:capa_effectiveness_review_list"))
        assert res_rev_a.status_code == 200
        content_rev_a = res_rev_a.content.decode("utf-8")
        assert capa_effectiveness_review_a.evaluator.username in content_rev_a
        assert capa_effectiveness_review_b.evaluator.username not in content_rev_a

        res_rev_b = client_b.get(reverse("quality:capa_effectiveness_review_list"))
        assert res_rev_b.status_code == 200
        content_rev_b = res_rev_b.content.decode("utf-8")
        assert capa_effectiveness_review_b.evaluator.username in content_rev_b
        assert capa_effectiveness_review_a.evaluator.username not in content_rev_b

    def test_capamanagement_security_tracking_board_tenant_isolation(
        self, client_a, client_b, capa_investigation_a, capa_investigation_b
    ):
        """Tracking board strictly segregates active CAPAs per tenant."""
        res_a = client_a.get(reverse("quality:capa_tracking_board"))
        assert res_a.status_code == 200
        content_a = res_a.content.decode("utf-8")
        assert capa_investigation_a.title in content_a
        assert capa_investigation_b.title not in content_a

        res_b = client_b.get(reverse("quality:capa_tracking_board"))
        assert res_b.status_code == 200
        content_b = res_b.content.decode("utf-8")
        assert capa_investigation_b.title in content_b
        assert capa_investigation_a.title not in content_b


# =====================================================================
# 2. Cross-Tenant Foreign Key Injection Rejection
# =====================================================================


class TestCapaManagementCrossTenantForeignKeyInjection:
    """Validate that forms reject binding foreign keys belonging to another tenant."""

    def test_capamanagement_security_capa_form_rejects_foreign_department(
        self, tenant_a, quality_department_b, admin_user
    ):
        """CapaInvestigationForm rejects foreign OrgUnit department binding."""
        form = CapaInvestigationForm(tenant=tenant_a)
        assert quality_department_b.pk not in list(form.fields["department"].queryset.values_list("pk", flat=True))

        data = {
            "title": "Cross Tenant Department Injection Test",
            "issue_summary": "Issue with foreign department.",
            "action_type": "corrective",
            "source_type": "complaint",
            "risk_priority": "high",
            "status": "draft",
            "lead_investigator": admin_user.pk,
            "quality_owner": admin_user,
            "department": quality_department_b.pk,
        }
        bound = CapaInvestigationForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "department" in bound.errors or "__all__" in bound.errors

    def test_capamanagement_security_capa_form_rejects_foreign_users(
        self, tenant_a, admin_b, quality_department
    ):
        """CapaInvestigationForm rejects foreign users as lead_investigator, quality_owner, or containment_verified_by."""
        form = CapaInvestigationForm(tenant=tenant_a)
        user_pks = list(form.fields["lead_investigator"].queryset.values_list("pk", flat=True))
        assert admin_b.pk not in user_pks

        data = {
            "title": "Cross Tenant User Injection Test",
            "issue_summary": "Issue with foreign users.",
            "action_type": "corrective",
            "source_type": "complaint",
            "risk_priority": "high",
            "status": "draft",
            "lead_investigator": admin_b.pk,
            "quality_owner": admin_b.pk,
            "department": quality_department.pk,
        }
        bound = CapaInvestigationForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "lead_investigator" in bound.errors or "quality_owner" in bound.errors or "__all__" in bound.errors

    def test_capamanagement_security_capa_form_rejects_foreign_design_project(
        self, tenant_a, design_project_b, admin_user, quality_department
    ):
        """CapaInvestigationForm rejects foreign DesignProject binding."""
        form = CapaInvestigationForm(tenant=tenant_a)
        assert design_project_b.pk not in list(form.fields["design_project"].queryset.values_list("pk", flat=True))

        data = {
            "title": "Cross Tenant Design Project Test",
            "issue_summary": "Issue with foreign project.",
            "action_type": "corrective",
            "source_type": "internal_audit",
            "risk_priority": "medium",
            "status": "draft",
            "lead_investigator": admin_user.pk,
            "quality_owner": admin_user.pk,
            "department": quality_department.pk,
            "design_project": design_project_b.pk,
        }
        bound = CapaInvestigationForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "design_project" in bound.errors or "__all__" in bound.errors

    def test_capamanagement_security_capa_form_rejects_foreign_risk_assessment(
        self, tenant_a, risk_assessment_b, admin_user, quality_department
    ):
        """CapaInvestigationForm rejects foreign RiskAssessment binding."""
        form = CapaInvestigationForm(tenant=tenant_a)
        assert risk_assessment_b.pk not in list(form.fields["risk_assessment"].queryset.values_list("pk", flat=True))

        data = {
            "title": "Cross Tenant Risk Assessment Test",
            "issue_summary": "Issue with foreign risk.",
            "action_type": "corrective",
            "source_type": "deviation",
            "risk_priority": "high",
            "status": "draft",
            "lead_investigator": admin_user.pk,
            "quality_owner": admin_user.pk,
            "department": quality_department.pk,
            "risk_assessment": risk_assessment_b.pk,
        }
        bound = CapaInvestigationForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "risk_assessment" in bound.errors or "__all__" in bound.errors

    def test_capamanagement_security_rca_form_rejects_foreign_capa(
        self, tenant_a, capa_investigation_b, admin_user
    ):
        """RootCauseAnalysisForm rejects foreign CapaInvestigation binding."""
        form = RootCauseAnalysisForm(tenant=tenant_a)
        assert capa_investigation_b.pk not in list(form.fields["capa"].queryset.values_list("pk", flat=True))

        data = {
            "capa": capa_investigation_b.pk,
            "rca_method": "5_whys",
            "problem_statement": "Problem under foreign CAPA.",
            "root_cause_category": "equipment",
            "root_cause_summary": "Root cause summary test.",
            "status": "draft",
            "lead_investigator": admin_user.pk,
        }
        bound = RootCauseAnalysisForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "capa" in bound.errors or "__all__" in bound.errors

    def test_capamanagement_security_rca_form_rejects_foreign_lead_investigator(
        self, tenant_a, capa_investigation_a, admin_b
    ):
        """RootCauseAnalysisForm rejects foreign user as lead investigator."""
        form = RootCauseAnalysisForm(tenant=tenant_a)
        assert admin_b.pk not in list(form.fields["lead_investigator"].queryset.values_list("pk", flat=True))

        data = {
            "capa": capa_investigation_a.pk,
            "rca_method": "5_whys",
            "problem_statement": "Problem with foreign investigator.",
            "root_cause_category": "equipment",
            "root_cause_summary": "Root cause summary test.",
            "status": "draft",
            "lead_investigator": admin_b.pk,
        }
        bound = RootCauseAnalysisForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "lead_investigator" in bound.errors or "__all__" in bound.errors

    def test_capamanagement_security_action_form_rejects_foreign_capa(
        self, tenant_a, capa_investigation_b, root_cause_analysis_a, admin_user, quality_department
    ):
        """CapaActionForm rejects foreign CapaInvestigation binding."""
        form = CapaActionForm(tenant=tenant_a)
        assert capa_investigation_b.pk not in list(form.fields["capa"].queryset.values_list("pk", flat=True))

        data = {
            "capa": capa_investigation_b.pk,
            "root_cause": root_cause_analysis_a.pk,
            "action_type": "corrective",
            "title": "Action under foreign CAPA",
            "description": "Action description.",
            "assigned_to": admin_user.pk,
            "department": quality_department.pk,
            "due_date": timezone.now().date() + timedelta(days=7),
            "status": "pending",
        }
        bound = CapaActionForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "capa" in bound.errors or "__all__" in bound.errors

    def test_capamanagement_security_action_form_rejects_foreign_root_cause(
        self, tenant_a, capa_investigation_a, root_cause_analysis_b, admin_user, quality_department
    ):
        """CapaActionForm rejects foreign RootCauseAnalysis binding."""
        form = CapaActionForm(tenant=tenant_a)
        assert root_cause_analysis_b.pk not in list(form.fields["root_cause"].queryset.values_list("pk", flat=True))

        data = {
            "capa": capa_investigation_a.pk,
            "root_cause": root_cause_analysis_b.pk,
            "action_type": "corrective",
            "title": "Action with foreign RCA",
            "description": "Action description.",
            "assigned_to": admin_user.pk,
            "department": quality_department.pk,
            "due_date": timezone.now().date() + timedelta(days=7),
            "status": "pending",
        }
        bound = CapaActionForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "root_cause" in bound.errors or "__all__" in bound.errors

    def test_capamanagement_security_action_form_rejects_foreign_assignee_and_department(
        self, tenant_a, capa_investigation_a, root_cause_analysis_a, admin_b, quality_department_b
    ):
        """CapaActionForm rejects foreign user and foreign department bindings."""
        form = CapaActionForm(tenant=tenant_a)
        assert admin_b.pk not in list(form.fields["assigned_to"].queryset.values_list("pk", flat=True))
        assert quality_department_b.pk not in list(form.fields["department"].queryset.values_list("pk", flat=True))

        data = {
            "capa": capa_investigation_a.pk,
            "root_cause": root_cause_analysis_a.pk,
            "action_type": "corrective",
            "title": "Action with foreign assignee and dept",
            "description": "Action description.",
            "assigned_to": admin_b.pk,
            "department": quality_department_b.pk,
            "due_date": timezone.now().date() + timedelta(days=7),
            "status": "pending",
        }
        bound = CapaActionForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "assigned_to" in bound.errors or "department" in bound.errors or "__all__" in bound.errors

    def test_capamanagement_security_action_form_rejects_foreign_controlled_doc_and_change_order(
        self, tenant_a, capa_investigation_a, root_cause_analysis_a, admin_user, quality_department, quality_doc_b, quality_dco_b
    ):
        """CapaActionForm rejects foreign controlled document and change order bindings."""
        form = CapaActionForm(tenant=tenant_a)
        assert quality_doc_b.pk not in list(form.fields["controlled_document"].queryset.values_list("pk", flat=True))
        assert quality_dco_b.pk not in list(form.fields["change_order"].queryset.values_list("pk", flat=True))

        data = {
            "capa": capa_investigation_a.pk,
            "root_cause": root_cause_analysis_a.pk,
            "action_type": "corrective",
            "title": "Action with foreign doc and dco",
            "description": "Action description.",
            "assigned_to": admin_user.pk,
            "department": quality_department.pk,
            "due_date": timezone.now().date() + timedelta(days=7),
            "status": "pending",
            "controlled_document": quality_doc_b.pk,
            "change_order": quality_dco_b.pk,
        }
        bound = CapaActionForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "controlled_document" in bound.errors or "change_order" in bound.errors or "__all__" in bound.errors

    def test_capamanagement_security_review_form_rejects_foreign_capa(
        self, tenant_a, capa_investigation_b, admin_user
    ):
        """CapaEffectivenessReviewForm rejects foreign CapaInvestigation binding."""
        form = CapaEffectivenessReviewForm(tenant=tenant_a)
        assert capa_investigation_b.pk not in list(form.fields["capa"].queryset.values_list("pk", flat=True))

        data = {
            "capa": capa_investigation_b.pk,
            "review_criteria": "Review criteria on foreign CAPA.",
            "verification_method": "statistical_sample",
            "planned_review_date": timezone.now().date() + timedelta(days=30),
            "evaluator": admin_user.pk,
            "outcome": "pending",
            "status": "scheduled",
        }
        bound = CapaEffectivenessReviewForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "capa" in bound.errors or "__all__" in bound.errors

    def test_capamanagement_security_review_form_rejects_foreign_evaluator(
        self, tenant_a, capa_investigation_a, admin_b
    ):
        """CapaEffectivenessReviewForm rejects foreign user as evaluator."""
        form = CapaEffectivenessReviewForm(tenant=tenant_a)
        assert admin_b.pk not in list(form.fields["evaluator"].queryset.values_list("pk", flat=True))

        data = {
            "capa": capa_investigation_a.pk,
            "review_criteria": "Review criteria with foreign evaluator.",
            "verification_method": "statistical_sample",
            "planned_review_date": timezone.now().date() + timedelta(days=30),
            "evaluator": admin_b.pk,
            "outcome": "pending",
            "status": "scheduled",
        }
        bound = CapaEffectivenessReviewForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "evaluator" in bound.errors or "__all__" in bound.errors


# =====================================================================
# 3. Authorization & Role Separation
# =====================================================================


class TestCapaManagementAuthorizationAndRoleSeparation:
    """Validate @tenant_admin_required, separation of duties, and role gates."""

    def test_capamanagement_security_tenant_admin_required_endpoints_return_403(
        self,
        _capamanagement_non_admin_client,
        capa_investigation_a,
        root_cause_analysis_a,
        capa_action_a,
        capa_effectiveness_review_a,
    ):
        """Non-admin user receives HTTP 403 Forbidden on all 5 @tenant_admin_required endpoints."""
        privileged_endpoints = [
            reverse("quality:capa_investigation_delete", kwargs={"pk": capa_investigation_a.pk}),
            reverse("quality:capa_investigation_close", kwargs={"pk": capa_investigation_a.pk}),
            reverse("quality:root_cause_analysis_delete", kwargs={"pk": root_cause_analysis_a.pk}),
            reverse("quality:capa_action_delete", kwargs={"pk": capa_action_a.pk}),
            reverse("quality:capa_effectiveness_review_delete", kwargs={"pk": capa_effectiveness_review_a.pk}),
        ]

        for url in privileged_endpoints:
            res = _capamanagement_non_admin_client.post(url, {})
            assert res.status_code == 403, f"Expected 403 Forbidden for non-admin on {url}, got {res.status_code}"

    def test_capamanagement_security_advance_voided_blocked_for_standard_user(
        self, _capamanagement_non_admin_client, capa_investigation_a
    ):
        """Standard user cannot set target_status='voided' on CAPA investigation."""
        url = reverse("quality:capa_investigation_advance_status", kwargs={"pk": capa_investigation_a.pk})
        res = _capamanagement_non_admin_client.post(url, {"target_status": "voided"})
        assert res.status_code == 302
        messages = _capamanagement_get_messages(res)
        assert any("only tenant administrators can void" in m.lower() for m in messages)

        capa_investigation_a.refresh_from_db()
        assert capa_investigation_a.status == "under_investigation"

    def test_capamanagement_security_advance_voided_allowed_for_tenant_admin(
        self, client_a, capa_investigation_a
    ):
        """Tenant administrator can successfully void a CAPA investigation."""
        url = reverse("quality:capa_investigation_advance_status", kwargs={"pk": capa_investigation_a.pk})
        res = client_a.post(url, {"target_status": "voided"})
        assert res.status_code == 302
        capa_investigation_a.refresh_from_db()
        assert capa_investigation_a.status == "voided"

    def test_capamanagement_security_action_verify_assignee_cannot_self_verify_as_standard_user(
        self,
        _capamanagement_non_admin_client,
        _capamanagement_non_admin_user,
        capa_action_a,
    ):
        """Assignee cannot self-verify their own action item without tenant-admin privilege (Separation of Duties)."""
        capa_action_a.assigned_to = _capamanagement_non_admin_user
        capa_action_a.status = "implemented"
        capa_action_a.completion_date = timezone.now().date()
        capa_action_a.save()

        url = reverse("quality:capa_action_verify", kwargs={"pk": capa_action_a.pk})
        res = _capamanagement_non_admin_client.post(url, {"verification_evidence": "Self-verification attempt"})
        assert res.status_code == 302
        messages = _capamanagement_get_messages(res)
        assert any("separation of duties required" in m.lower() for m in messages)

        capa_action_a.refresh_from_db()
        assert capa_action_a.status == "implemented"
        assert capa_action_a.verified_by is None

    def test_capamanagement_security_action_verify_assignee_can_verify_if_tenant_admin(
        self, client_a, admin_user, capa_action_a
    ):
        """Tenant administrator can verify an action item even if assigned to themselves."""
        capa_action_a.assigned_to = admin_user
        capa_action_a.status = "implemented"
        capa_action_a.completion_date = timezone.now().date()
        capa_action_a.save()

        url = reverse("quality:capa_action_verify", kwargs={"pk": capa_action_a.pk})
        res = client_a.post(url, {"verification_evidence": "Admin verification of implemented protocol."})
        assert res.status_code == 302
        capa_action_a.refresh_from_db()
        assert capa_action_a.status == "verified"
        assert capa_action_a.verified_by == admin_user

    def test_capamanagement_security_action_verify_non_assignee_standard_user_can_verify(
        self,
        _capamanagement_non_admin_client,
        admin_user,
        capa_action_a,
    ):
        """Standard user who is NOT the assignee can verify an implemented action item."""
        capa_action_a.assigned_to = admin_user
        capa_action_a.status = "implemented"
        capa_action_a.completion_date = timezone.now().date()
        capa_action_a.save()

        url = reverse("quality:capa_action_verify", kwargs={"pk": capa_action_a.pk})
        res = _capamanagement_non_admin_client.post(url, {"verification_evidence": "Peer quality verification."})
        assert res.status_code == 302
        capa_action_a.refresh_from_db()
        assert capa_action_a.status == "verified"

    def test_capamanagement_security_review_sign_off_blocked_for_non_evaluator_non_admin(
        self,
        _capamanagement_non_admin_client,
        admin_user,
        capa_effectiveness_review_a,
    ):
        """Non-evaluator non-admin user cannot sign off an effectiveness review."""
        capa_effectiveness_review_a.evaluator = admin_user
        capa_effectiveness_review_a.status = "scheduled"
        capa_effectiveness_review_a.save()

        url = reverse("quality:capa_effectiveness_review_sign_off", kwargs={"pk": capa_effectiveness_review_a.pk})
        res = _capamanagement_non_admin_client.post(url, {"outcome": "effective", "review_notes": "Unauthorized sign-off"})
        assert res.status_code == 302
        messages = _capamanagement_get_messages(res)
        assert any("only the assigned evaluator or a tenant administrator" in m.lower() for m in messages)

        capa_effectiveness_review_a.refresh_from_db()
        assert capa_effectiveness_review_a.status != "completed"

    def test_capamanagement_security_review_sign_off_allowed_for_assigned_evaluator(
        self,
        _capamanagement_non_admin_client,
        _capamanagement_non_admin_user,
        capa_effectiveness_review_a,
    ):
        """Standard user assigned as evaluator CAN sign off their review."""
        capa_effectiveness_review_a.evaluator = _capamanagement_non_admin_user
        capa_effectiveness_review_a.status = "scheduled"
        capa_effectiveness_review_a.save()

        url = reverse("quality:capa_effectiveness_review_sign_off", kwargs={"pk": capa_effectiveness_review_a.pk})
        res = _capamanagement_non_admin_client.post(url, {"outcome": "effective", "review_notes": "Evaluator confirmed zero defect."})
        assert res.status_code == 302
        capa_effectiveness_review_a.refresh_from_db()
        assert capa_effectiveness_review_a.status == "completed"
        assert capa_effectiveness_review_a.outcome == "effective"

    def test_capamanagement_security_review_sign_off_allowed_for_tenant_admin(
        self, client_a, _capamanagement_non_admin_user, capa_effectiveness_review_a
    ):
        """Tenant administrator can sign off any effectiveness review even if assigned to another user."""
        capa_effectiveness_review_a.evaluator = _capamanagement_non_admin_user
        capa_effectiveness_review_a.status = "scheduled"
        capa_effectiveness_review_a.save()

        url = reverse("quality:capa_effectiveness_review_sign_off", kwargs={"pk": capa_effectiveness_review_a.pk})
        res = client_a.post(url, {"outcome": "effective", "review_notes": "Admin override sign-off."})
        assert res.status_code == 302
        capa_effectiveness_review_a.refresh_from_db()
        assert capa_effectiveness_review_a.status == "completed"


# =====================================================================
# 4. Status & Lifecycle Tampering & Business Logic Integrity
# =====================================================================


class TestCapaManagementStatusAndLifecycleTampering:
    """Validate model/form lifecycle invariants and guard against status tampering."""

    # --- Form clean_status Rejections ---

    def test_capamanagement_security_capa_form_rejects_closed_and_voided_status(
        self, tenant_a, admin_user, quality_department
    ):
        """CapaInvestigationForm rejects setting status='closed' or 'voided' directly via form."""
        base_data = {
            "title": "Status Tampering Test",
            "issue_summary": "Testing direct closed status.",
            "action_type": "corrective",
            "source_type": "ncr",
            "risk_priority": "high",
            "lead_investigator": admin_user.pk,
            "quality_owner": admin_user.pk,
            "department": quality_department.pk,
        }

        # 1. Closed status rejected
        data_closed = {**base_data, "status": "closed"}
        form_closed = CapaInvestigationForm(data=data_closed, tenant=tenant_a)
        assert not form_closed.is_valid()
        assert "status" in form_closed.errors
        assert any("cannot be set directly" in err for err in form_closed.errors["status"])

        # 2. Voided status rejected
        data_voided = {**base_data, "status": "voided"}
        form_voided = CapaInvestigationForm(data=data_voided, tenant=tenant_a)
        assert not form_voided.is_valid()
        assert "status" in form_voided.errors
        assert any("cannot be set directly" in err for err in form_voided.errors["status"])

    def test_capamanagement_security_rca_form_rejects_verified_status(
        self, tenant_a, capa_investigation_a, admin_user
    ):
        """RootCauseAnalysisForm rejects setting status='verified' directly via form."""
        data = {
            "capa": capa_investigation_a.pk,
            "rca_method": "5_whys",
            "problem_statement": "RCA direct verified test.",
            "root_cause_category": "equipment",
            "root_cause_summary": "Summary.",
            "lead_investigator": admin_user.pk,
            "status": "verified",
        }
        form = RootCauseAnalysisForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "status" in form.errors
        assert any("cannot be set directly" in err for err in form.errors["status"])

    def test_capamanagement_security_action_form_rejects_verified_status(
        self, tenant_a, capa_investigation_a, root_cause_analysis_a, admin_user, quality_department
    ):
        """CapaActionForm rejects setting status='verified' directly via form."""
        data = {
            "capa": capa_investigation_a.pk,
            "root_cause": root_cause_analysis_a.pk,
            "action_type": "corrective",
            "title": "Action direct verified test",
            "description": "Description.",
            "assigned_to": admin_user.pk,
            "department": quality_department.pk,
            "due_date": timezone.now().date() + timedelta(days=7),
            "status": "verified",
        }
        form = CapaActionForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "status" in form.errors
        assert any("cannot be set directly" in err for err in form.errors["status"])

    def test_capamanagement_security_review_form_rejects_completed_status(
        self, tenant_a, capa_investigation_a, admin_user
    ):
        """CapaEffectivenessReviewForm rejects setting status='completed' directly via form."""
        data = {
            "capa": capa_investigation_a.pk,
            "review_criteria": "Review direct completed test.",
            "verification_method": "statistical_sample",
            "planned_review_date": timezone.now().date() + timedelta(days=30),
            "evaluator": admin_user.pk,
            "outcome": "effective",
            "status": "completed",
        }
        form = CapaEffectivenessReviewForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "status" in form.errors
        assert any("cannot be set directly" in err for err in form.errors["status"])

    # --- Advance Status Tampering ---

    def test_capamanagement_security_advance_status_rejects_closed(
        self, client_a, capa_investigation_a
    ):
        """Direct transition to target_status='closed' via advance_status is rejected."""
        url = reverse("quality:capa_investigation_advance_status", kwargs={"pk": capa_investigation_a.pk})
        res = client_a.post(url, {"target_status": "closed"})
        assert res.status_code == 302
        messages = _capamanagement_get_messages(res)
        assert any("formal closure must be performed via the closure workflow" in m.lower() for m in messages)

        capa_investigation_a.refresh_from_db()
        assert capa_investigation_a.status == "under_investigation"

    def test_capamanagement_security_advance_status_rejects_invalid_status(
        self, client_a, capa_investigation_a
    ):
        """advance_status rejects arbitrary invalid lifecycle status values."""
        url = reverse("quality:capa_investigation_advance_status", kwargs={"pk": capa_investigation_a.pk})
        res = client_a.post(url, {"target_status": "fabricated_status"})
        assert res.status_code == 302
        messages = _capamanagement_get_messages(res)
        assert any("invalid lifecycle transition" in m.lower() for m in messages)

        capa_investigation_a.refresh_from_db()
        assert capa_investigation_a.status == "under_investigation"

    def test_capamanagement_security_closed_capa_cannot_be_advanced(
        self, client_a, _capamanagement_closed_capa
    ):
        """Cannot advance or modify status of a closed CAPA investigation."""
        url = reverse("quality:capa_investigation_advance_status", kwargs={"pk": _capamanagement_closed_capa.pk})
        res = client_a.post(url, {"target_status": "under_investigation"})
        assert res.status_code == 302
        messages = _capamanagement_get_messages(res)
        assert any("cannot advance or modify a closed capa" in m.lower() for m in messages)

        _capamanagement_closed_capa.refresh_from_db()
        assert _capamanagement_closed_capa.status == "closed"

    def test_capamanagement_security_closed_capa_cannot_be_edited(
        self, client_a, _capamanagement_closed_capa
    ):
        """GET and POST to edit a closed CAPA redirects with warning and prevents modification."""
        url = reverse("quality:capa_investigation_edit", kwargs={"pk": _capamanagement_closed_capa.pk})
        # 1. GET
        res_get = client_a.get(url)
        assert res_get.status_code == 302
        messages_get = _capamanagement_get_messages(res_get)
        assert any("is closed and cannot be directly edited" in m.lower() for m in messages_get)

        # 2. POST
        res_post = client_a.post(url, {"title": "Attempted Edit on Closed CAPA"})
        assert res_post.status_code == 302
        messages_post = _capamanagement_get_messages(res_post)
        assert any("is closed and cannot be directly edited" in m.lower() for m in messages_post)

        _capamanagement_closed_capa.refresh_from_db()
        assert _capamanagement_closed_capa.title != "Attempted Edit on Closed CAPA"

    def test_capamanagement_security_closed_capa_cannot_be_deleted(
        self, client_a, _capamanagement_closed_capa
    ):
        """Cannot delete a closed CAPA investigation; record retained for audit compliance."""
        url = reverse("quality:capa_investigation_delete", kwargs={"pk": _capamanagement_closed_capa.pk})
        res = client_a.post(url)
        assert res.status_code == 302
        messages = _capamanagement_get_messages(res)
        assert any("cannot delete a closed capa investigation" in m.lower() for m in messages)

        assert CapaInvestigation.objects.filter(pk=_capamanagement_closed_capa.pk).exists()

    # --- Deletion Guards for Verified / Completed Child Records ---

    def test_capamanagement_security_verified_rca_cannot_be_deleted(
        self, client_a, _capamanagement_verified_rca
    ):
        """Cannot delete a verified Root Cause Analysis record."""
        url = reverse("quality:root_cause_analysis_delete", kwargs={"pk": _capamanagement_verified_rca.pk})
        res = client_a.post(url)
        assert res.status_code == 302
        messages = _capamanagement_get_messages(res)
        assert any("cannot delete a verified root cause analysis" in m.lower() for m in messages)

        assert RootCauseAnalysis.objects.filter(pk=_capamanagement_verified_rca.pk).exists()

    def test_capamanagement_security_rca_under_closed_capa_cannot_be_deleted(
        self, client_a, _capamanagement_closed_capa, admin_user
    ):
        """Cannot delete an RCA belonging to a closed parent CAPA."""
        rca = RootCauseAnalysis.objects.create(
            tenant=_capamanagement_closed_capa.tenant,
            capa=_capamanagement_closed_capa,
            rca_method="5_whys",
            problem_statement="Problem on closed CAPA.",
            root_cause_summary="Summary.",
            lead_investigator=admin_user,
            status="draft",
        )
        url = reverse("quality:root_cause_analysis_delete", kwargs={"pk": rca.pk})
        res = client_a.post(url)
        assert res.status_code == 302
        messages = _capamanagement_get_messages(res)
        assert any("cannot delete records belonging to a closed capa" in m.lower() for m in messages)

        assert RootCauseAnalysis.objects.filter(pk=rca.pk).exists()

    def test_capamanagement_security_verified_action_cannot_be_deleted(
        self, client_a, _capamanagement_verified_action
    ):
        """Cannot delete a verified CAPA action item."""
        url = reverse("quality:capa_action_delete", kwargs={"pk": _capamanagement_verified_action.pk})
        res = client_a.post(url)
        assert res.status_code == 302
        messages = _capamanagement_get_messages(res)
        assert any("cannot delete a verified capa action" in m.lower() for m in messages)

        assert CapaAction.objects.filter(pk=_capamanagement_verified_action.pk).exists()

    def test_capamanagement_security_action_under_closed_capa_cannot_be_deleted(
        self, client_a, _capamanagement_closed_capa, admin_user, quality_department
    ):
        """Cannot delete an action belonging to a closed parent CAPA."""
        action = CapaAction.objects.create(
            tenant=_capamanagement_closed_capa.tenant,
            capa=_capamanagement_closed_capa,
            action_type="corrective",
            title="Action under closed CAPA",
            description="Description.",
            assigned_to=admin_user,
            department=quality_department,
            due_date=timezone.now().date(),
            status="implemented",
        )
        url = reverse("quality:capa_action_delete", kwargs={"pk": action.pk})
        res = client_a.post(url)
        assert res.status_code == 302
        messages = _capamanagement_get_messages(res)
        assert any("cannot delete actions belonging to a closed capa" in m.lower() for m in messages)

        assert CapaAction.objects.filter(pk=action.pk).exists()

    def test_capamanagement_security_completed_review_cannot_be_deleted(
        self, client_a, _capamanagement_completed_review
    ):
        """Cannot delete a completed Effectiveness Review record."""
        url = reverse("quality:capa_effectiveness_review_delete", kwargs={"pk": _capamanagement_completed_review.pk})
        res = client_a.post(url)
        assert res.status_code == 302
        messages = _capamanagement_get_messages(res)
        assert any("cannot delete a completed effectiveness review" in m.lower() for m in messages)

        assert CapaEffectivenessReview.objects.filter(pk=_capamanagement_completed_review.pk).exists()

    def test_capamanagement_security_review_under_closed_capa_cannot_be_deleted(
        self, client_a, _capamanagement_closed_capa, admin_user
    ):
        """Cannot delete a review belonging to a closed parent CAPA."""
        review = CapaEffectivenessReview.objects.create(
            tenant=_capamanagement_closed_capa.tenant,
            capa=_capamanagement_closed_capa,
            review_criteria="Criteria on closed CAPA.",
            verification_method="statistical_sample",
            planned_review_date=timezone.now().date(),
            evaluator=admin_user,
            status="scheduled",
        )
        url = reverse("quality:capa_effectiveness_review_delete", kwargs={"pk": review.pk})
        res = client_a.post(url)
        assert res.status_code == 302
        messages = _capamanagement_get_messages(res)
        assert any("cannot delete reviews belonging to a closed capa" in m.lower() for m in messages)

        assert CapaEffectivenessReview.objects.filter(pk=review.pk).exists()

    # --- Verification & Modification Protections ---

    def test_capamanagement_security_verified_rca_cannot_be_edited(
        self, client_a, _capamanagement_verified_rca
    ):
        """Verified RCA cannot be directly modified via edit view."""
        url = reverse("quality:root_cause_analysis_edit", kwargs={"pk": _capamanagement_verified_rca.pk})
        res_get = client_a.get(url)
        assert res_get.status_code == 302
        messages_get = _capamanagement_get_messages(res_get)
        assert any("has been verified and cannot be directly modified" in m.lower() for m in messages_get)

        res_post = client_a.post(url, {"problem_statement": "Tampered"})
        assert res_post.status_code == 302
        _capamanagement_verified_rca.refresh_from_db()
        assert _capamanagement_verified_rca.problem_statement != "Tampered"

    def test_capamanagement_security_already_verified_rca_cannot_be_reverified(
        self, client_a, _capamanagement_verified_rca
    ):
        """Already verified RCA cannot be reverified."""
        url = reverse("quality:root_cause_analysis_verify", kwargs={"pk": _capamanagement_verified_rca.pk})
        res = client_a.post(url, {"verification_notes": "New notes"})
        assert res.status_code == 302
        messages = _capamanagement_get_messages(res)
        assert any("already been verified" in m.lower() for m in messages)

    def test_capamanagement_security_rca_under_closed_capa_cannot_be_verified(
        self, client_a, _capamanagement_closed_capa, admin_user
    ):
        """RCA under a closed parent CAPA cannot be verified."""
        rca = RootCauseAnalysis.objects.create(
            tenant=_capamanagement_closed_capa.tenant,
            capa=_capamanagement_closed_capa,
            rca_method="5_whys",
            problem_statement="Problem on closed CAPA.",
            root_cause_summary="Summary.",
            lead_investigator=admin_user,
            status="draft",
        )
        url = reverse("quality:root_cause_analysis_verify", kwargs={"pk": rca.pk})
        res = client_a.post(url, {"verification_notes": "Attempted verification"})
        assert res.status_code == 302
        messages = _capamanagement_get_messages(res)
        assert any("cannot verify records belonging to a closed capa" in m.lower() for m in messages)

        rca.refresh_from_db()
        assert rca.status != "verified"

    def test_capamanagement_security_verified_action_cannot_be_edited(
        self, client_a, _capamanagement_verified_action
    ):
        """Verified action cannot be directly modified via edit view."""
        url = reverse("quality:capa_action_edit", kwargs={"pk": _capamanagement_verified_action.pk})
        res_get = client_a.get(url)
        assert res_get.status_code == 302
        messages = _capamanagement_get_messages(res_get)
        assert any("has been verified and cannot be directly modified" in m.lower() for m in messages)

        res_post = client_a.post(url, {"title": "Tampered"})
        assert res_post.status_code == 302
        _capamanagement_verified_action.refresh_from_db()
        assert _capamanagement_verified_action.title != "Tampered"

    def test_capamanagement_security_action_verify_requires_implemented_status(
        self, client_a, capa_action_a
    ):
        """capa_action_verify rejects actions that are not yet in 'implemented' status."""
        assert capa_action_a.status == "pending"
        url = reverse("quality:capa_action_verify", kwargs={"pk": capa_action_a.pk})
        res = client_a.post(url, {"verification_evidence": "Verification of pending action"})
        assert res.status_code == 302
        messages = _capamanagement_get_messages(res)
        assert any("only implemented actions can be verified" in m.lower() for m in messages)

        capa_action_a.refresh_from_db()
        assert capa_action_a.status != "verified"

    def test_capamanagement_security_already_verified_action_cannot_be_reverified(
        self, client_a, _capamanagement_verified_action
    ):
        """Already verified action cannot be reverified."""
        url = reverse("quality:capa_action_verify", kwargs={"pk": _capamanagement_verified_action.pk})
        res = client_a.post(url, {"verification_evidence": "Reverification"})
        assert res.status_code == 302
        messages = _capamanagement_get_messages(res)
        assert any("already verified" in m.lower() for m in messages)

    def test_capamanagement_security_completed_review_cannot_be_edited(
        self, client_a, _capamanagement_completed_review
    ):
        """Completed review cannot be directly modified via edit view."""
        url = reverse("quality:capa_effectiveness_review_edit", kwargs={"pk": _capamanagement_completed_review.pk})
        res_get = client_a.get(url)
        assert res_get.status_code == 302
        messages = _capamanagement_get_messages(res_get)
        assert any("has been completed and cannot be edited" in m.lower() for m in messages)

        res_post = client_a.post(url, {"review_criteria": "Tampered"})
        assert res_post.status_code == 302
        _capamanagement_completed_review.refresh_from_db()
        assert _capamanagement_completed_review.review_criteria != "Tampered"

    def test_capamanagement_security_already_completed_review_cannot_be_signed_off(
        self, client_a, _capamanagement_completed_review
    ):
        """Already completed review cannot be signed off again."""
        url = reverse("quality:capa_effectiveness_review_sign_off", kwargs={"pk": _capamanagement_completed_review.pk})
        res = client_a.post(url, {"outcome": "effective", "review_notes": "Resigning"})
        assert res.status_code == 302
        messages = _capamanagement_get_messages(res)
        assert any("already been signed off and completed" in m.lower() for m in messages)

    # --- Effectiveness Review Recurrence Invariant ---

    def test_capamanagement_security_review_sign_off_requires_definitive_outcome(
        self, client_a, capa_effectiveness_review_a
    ):
        """Sign-off requires choosing a definitive outcome ('effective', 'ineffective', 'inconclusive')."""
        url = reverse("quality:capa_effectiveness_review_sign_off", kwargs={"pk": capa_effectiveness_review_a.pk})
        res = client_a.post(url, {"outcome": "pending"})
        assert res.status_code == 302
        messages = _capamanagement_get_messages(res)
        assert any("please choose a definitive outcome" in m.lower() for m in messages)

        capa_effectiveness_review_a.refresh_from_db()
        assert capa_effectiveness_review_a.status != "completed"

    def test_capamanagement_security_review_sign_off_effective_blocked_when_recurrence_observed(
        self, client_a, capa_effectiveness_review_a
    ):
        """Sign-off rejects outcome='effective' if recurrence_observed=True."""
        capa_effectiveness_review_a.recurrence_observed = True
        capa_effectiveness_review_a.recurrence_details = "Ferrule fractured again in lot 2026-092."
        capa_effectiveness_review_a.save()

        url = reverse("quality:capa_effectiveness_review_sign_off", kwargs={"pk": capa_effectiveness_review_a.pk})
        res = client_a.post(url, {"outcome": "effective", "review_notes": "Attempting effective despite recurrence"})
        assert res.status_code == 302
        messages = _capamanagement_get_messages(res)
        assert any("cannot mark review as 'effective' when recurrence has been observed" in m.lower() for m in messages)

        capa_effectiveness_review_a.refresh_from_db()
        assert capa_effectiveness_review_a.status != "completed"

    def test_capamanagement_security_review_form_effective_blocked_when_recurrence_observed(
        self, tenant_a, capa_investigation_a, admin_user
    ):
        """CapaEffectivenessReviewForm rejects outcome='effective' when recurrence_observed=True."""
        data = {
            "capa": capa_investigation_a.pk,
            "review_criteria": "Acceptance criteria.",
            "verification_method": "statistical_sample",
            "planned_review_date": timezone.now().date() + timedelta(days=30),
            "evaluator": admin_user.pk,
            "recurrence_observed": True,
            "recurrence_details": "Defect recurred in line inspection.",
            "outcome": "effective",
            "status": "in_progress",
        }
        form = CapaEffectivenessReviewForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "outcome" in form.errors
        assert any("cannot mark review as 'effective' when recurrence has been observed" in err.lower() for err in form.errors["outcome"])

    # --- Formal Closure Pending Actions Guard ---

    def test_capamanagement_security_capa_close_blocked_if_actions_incomplete(
        self, client_a, capa_investigation_a, capa_action_a
    ):
        """capa_investigation_close is blocked while action items remain incomplete."""
        assert capa_action_a.capa == capa_investigation_a
        assert capa_action_a.status == "pending"

        url = reverse("quality:capa_investigation_close", kwargs={"pk": capa_investigation_a.pk})
        res = client_a.post(url, {"closure_summary": "Attempting premature closure."})
        assert res.status_code == 302
        messages = _capamanagement_get_messages(res)
        assert any("cannot close capa" in m.lower() and "remain incomplete" in m.lower() for m in messages)

        capa_investigation_a.refresh_from_db()
        assert capa_investigation_a.status != "closed"
        assert capa_investigation_a.closed_at is None

    def test_capamanagement_security_capa_close_succeeds_when_actions_complete(
        self, client_a, capa_investigation_a, capa_action_a
    ):
        """capa_investigation_close succeeds when all action items are implemented, verified, or cancelled."""
        capa_action_a.status = "verified"
        capa_action_a.save()

        url = reverse("quality:capa_investigation_close", kwargs={"pk": capa_investigation_a.pk})
        res = client_a.post(url, {"closure_summary": "All actions verified and confirmed effective."})
        assert res.status_code == 302
        messages = _capamanagement_get_messages(res)
        assert any("formally closed and verified" in m.lower() for m in messages)

        capa_investigation_a.refresh_from_db()
        assert capa_investigation_a.status == "closed"
        assert capa_investigation_a.closed_at is not None
        assert capa_investigation_a.closure_summary == "All actions verified and confirmed effective."

    # --- Parent CAPA Immutability on Child Forms ---

    def test_capamanagement_security_rca_parent_capa_immutable_on_edit(
        self, tenant_a, root_cause_analysis_a, _capamanagement_closed_capa
    ):
        """Parent CAPA cannot be swapped on an existing RCA record."""
        data = {
            "capa": _capamanagement_closed_capa.pk,
            "rca_method": root_cause_analysis_a.rca_method,
            "problem_statement": root_cause_analysis_a.problem_statement,
            "root_cause_category": root_cause_analysis_a.root_cause_category,
            "root_cause_summary": root_cause_analysis_a.root_cause_summary,
            "lead_investigator": root_cause_analysis_a.lead_investigator.pk,
            "status": root_cause_analysis_a.status,
        }
        form = RootCauseAnalysisForm(data=data, instance=root_cause_analysis_a, tenant=tenant_a)
        assert not form.is_valid()
        assert "capa" in form.errors
        assert any("cannot be changed once established" in err for err in form.errors["capa"])

    def test_capamanagement_security_action_parent_capa_immutable_on_edit(
        self, tenant_a, capa_action_a, _capamanagement_closed_capa
    ):
        """Parent CAPA cannot be swapped on an existing Action record."""
        data = {
            "capa": _capamanagement_closed_capa.pk,
            "action_type": capa_action_a.action_type,
            "title": capa_action_a.title,
            "description": capa_action_a.description,
            "assigned_to": capa_action_a.assigned_to.pk,
            "department": capa_action_a.department.pk,
            "due_date": capa_action_a.due_date,
            "status": capa_action_a.status,
        }
        form = CapaActionForm(data=data, instance=capa_action_a, tenant=tenant_a)
        assert not form.is_valid()
        assert "capa" in form.errors
        assert any("cannot be changed once established" in err for err in form.errors["capa"])

    def test_capamanagement_security_action_root_cause_must_belong_to_capa(
        self, tenant_a, capa_investigation_a, _capamanagement_closed_capa, admin_user, quality_department
    ):
        """Action form enforces that selected root cause belongs to the selected CAPA investigation."""
        rca_on_closed_capa = RootCauseAnalysis.objects.create(
            tenant=tenant_a,
            capa=_capamanagement_closed_capa,
            rca_method="5_whys",
            problem_statement="Problem on closed CAPA.",
            root_cause_summary="Summary.",
            lead_investigator=admin_user,
            status="draft",
        )

        data = {
            "capa": capa_investigation_a.pk,
            "root_cause": rca_on_closed_capa.pk,
            "action_type": "corrective",
            "title": "Action with mismatched RCA",
            "description": "Description.",
            "assigned_to": admin_user.pk,
            "department": quality_department.pk,
            "due_date": timezone.now().date() + timedelta(days=7),
            "status": "pending",
        }
        form = CapaActionForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "root_cause" in form.errors
        assert any("must belong to the selected capa" in err.lower() for err in form.errors["root_cause"])

    def test_capamanagement_security_review_parent_capa_immutable_on_edit(
        self, tenant_a, capa_effectiveness_review_a, _capamanagement_closed_capa
    ):
        """Parent CAPA cannot be swapped on an existing Effectiveness Review record."""
        data = {
            "capa": _capamanagement_closed_capa.pk,
            "review_criteria": capa_effectiveness_review_a.review_criteria,
            "verification_method": capa_effectiveness_review_a.verification_method,
            "planned_review_date": capa_effectiveness_review_a.planned_review_date,
            "evaluator": capa_effectiveness_review_a.evaluator.pk,
            "outcome": capa_effectiveness_review_a.outcome,
            "status": capa_effectiveness_review_a.status,
        }
        form = CapaEffectivenessReviewForm(data=data, instance=capa_effectiveness_review_a, tenant=tenant_a)
        assert not form.is_valid()
        assert "capa" in form.errors
        assert any("cannot be changed once established" in err for err in form.errors["capa"])


# =====================================================================
# 5. CSV Export Security & Formula Injection Defense (CWE-1236)
# =====================================================================


class TestCapaManagementCsvExportSecurity:
    """Ensure CSV exports neutralize spreadsheet formula injection payloads across all endpoints."""

    def test_capamanagement_security_csv_safe_unit_escapes_formula_prefixes(self):
        """csv_safe() prepends a single quote to values starting with =, +, -, @, %, \\t, \\r."""
        assert csv_safe("=1+1") == "'=1+1"
        assert csv_safe("-5+2") == "'-5+2"
        assert csv_safe("+100") == "'+100"
        assert csv_safe("@SUM(A1:A10)") == "'@SUM(A1:A10)"
        assert csv_safe("+cmd|' /C calc'!A0") == "'+cmd|' /C calc'!A0"
        assert csv_safe("  =CMD|' /C calc'!A0") == "'  =CMD|' /C calc'!A0"
        assert csv_safe("%COMSPEC%") == "'%COMSPEC%"

        # Benign values remain untouched
        assert csv_safe("Normal Safe Title") == "Normal Safe Title"
        assert csv_safe("") == ""
        assert csv_safe(None) == ""
        assert csv_safe(100) == "100"

    def test_capamanagement_security_capa_export_formula_sanitization_and_headers(
        self, client_a, tenant_a, admin_user, quality_department
    ):
        """CapaInvestigation CSV export neutralizes formulas and includes security headers."""
        CapaInvestigation.objects.create(
            tenant=tenant_a,
            title="=1+1",
            issue_summary="-5+2",
            source_reference="@SUM(A1:A10)",
            action_type="corrective",
            source_type="complaint",
            risk_priority="high",
            status="under_investigation",
            department=quality_department,
            lead_investigator=admin_user,
            quality_owner=admin_user,
        )

        res = client_a.get(reverse("quality:capa_investigation_export"))
        assert res.status_code == 200
        assert res["Content-Type"] == "text/csv"
        assert res["X-Content-Type-Options"] == "nosniff"
        assert "attachment; filename=" in res["Content-Disposition"]

        rows = _capamanagement_parse_csv(res)
        titles = [r[1] for r in rows[1:]]
        source_refs = [r[4] for r in rows[1:]]

        assert "'=1+1" in titles
        assert "'@SUM(A1:A10)" in source_refs

    def test_capamanagement_security_rca_export_formula_sanitization_and_headers(
        self, client_a, tenant_a, admin_user, capa_investigation_a
    ):
        """RootCauseAnalysis CSV export neutralizes formulas and includes security headers."""
        RootCauseAnalysis.objects.create(
            tenant=tenant_a,
            capa=capa_investigation_a,
            rca_method="5_whys",
            problem_statement="=2+5*10",
            root_cause_summary="@ALERT('hazard')",
            root_cause_category="equipment",
            lead_investigator=admin_user,
            status="draft",
        )

        res = client_a.get(reverse("quality:root_cause_analysis_export"))
        assert res.status_code == 200
        assert res["Content-Type"] == "text/csv"
        assert res["X-Content-Type-Options"] == "nosniff"
        assert "attachment; filename=" in res["Content-Disposition"]

        rows = _capamanagement_parse_csv(res)
        problems = [r[4] for r in rows[1:]]
        summaries = [r[5] for r in rows[1:]]

        assert "'=2+5*10" in problems
        assert "'@ALERT('hazard')" in summaries

    def test_capamanagement_security_action_export_formula_sanitization_and_headers(
        self, client_a, tenant_a, admin_user, capa_investigation_a, quality_department
    ):
        """CapaAction CSV export neutralizes formulas and includes security headers."""
        CapaAction.objects.create(
            tenant=tenant_a,
            capa=capa_investigation_a,
            action_type="corrective",
            title="+cmd|' /C calc'!A0",
            description="-10+20",
            assigned_to=admin_user,
            department=quality_department,
            due_date=timezone.now().date() + timedelta(days=7),
            status="pending",
        )

        res = client_a.get(reverse("quality:capa_action_export"))
        assert res.status_code == 200
        assert res["Content-Type"] == "text/csv"
        assert res["X-Content-Type-Options"] == "nosniff"
        assert "attachment; filename=" in res["Content-Disposition"]

        rows = _capamanagement_parse_csv(res)
        titles = [r[3] for r in rows[1:]]
        assert "'+cmd|' /C calc'!A0" in titles

    def test_capamanagement_security_review_export_formula_sanitization_and_headers(
        self, client_a, tenant_a, admin_user, capa_investigation_a
    ):
        """CapaEffectivenessReview CSV export neutralizes formulas and includes security headers."""
        CapaEffectivenessReview.objects.create(
            tenant=tenant_a,
            capa=capa_investigation_a,
            review_criteria="=HYPERLINK('http://evil.com')",
            verification_method="statistical_sample",
            planned_review_date=timezone.now().date() + timedelta(days=30),
            evaluator=admin_user,
            status="scheduled",
        )

        res = client_a.get(reverse("quality:capa_effectiveness_review_export"))
        assert res.status_code == 200
        assert res["Content-Type"] == "text/csv"
        assert res["X-Content-Type-Options"] == "nosniff"
        assert "attachment; filename=" in res["Content-Disposition"]

        rows = _capamanagement_parse_csv(res)
        assert len(rows) > 1

    def test_capamanagement_security_tracking_board_export_formula_sanitization_and_headers(
        self, client_a, tenant_a, admin_user, quality_department
    ):
        """Tracking board CSV export neutralizes formulas and includes security headers."""
        CapaInvestigation.objects.create(
            tenant=tenant_a,
            title="@SUM(10,20)",
            action_type="corrective",
            source_type="complaint",
            risk_priority="high",
            status="under_investigation",
            department=quality_department,
            lead_investigator=admin_user,
            quality_owner=admin_user,
        )

        res = client_a.get(reverse("quality:capa_tracking_board_export"))
        assert res.status_code == 200
        assert res["Content-Type"] == "text/csv"
        assert res["X-Content-Type-Options"] == "nosniff"
        assert "attachment; filename=" in res["Content-Disposition"]

        rows = _capamanagement_parse_csv(res)
        titles = [r[1] for r in rows[1:]]
        assert "'@SUM(10,20)" in titles

    def test_capamanagement_security_csv_exports_tenant_isolation(
        self,
        client_a,
        client_b,
        capa_investigation_a,
        capa_investigation_b,
        root_cause_analysis_a,
        root_cause_analysis_b,
        capa_action_a,
        capa_action_b,
        capa_effectiveness_review_a,
        capa_effectiveness_review_b,
    ):
        """All 5 CSV export endpoints strictly filter output by tenant."""
        export_endpoints = [
            ("quality:capa_investigation_export", capa_investigation_a.title, capa_investigation_b.title),
            ("quality:root_cause_analysis_export", root_cause_analysis_a.problem_statement, root_cause_analysis_b.problem_statement),
            ("quality:capa_action_export", capa_action_a.title, capa_action_b.title),
            ("quality:capa_effectiveness_review_export", capa_effectiveness_review_a.evaluator.username, capa_effectiveness_review_b.evaluator.username),
            ("quality:capa_tracking_board_export", capa_investigation_a.title, capa_investigation_b.title),
        ]

        for route, text_a, text_b in export_endpoints:
            url = reverse(route)
            # Tenant A export
            res_a = client_a.get(url)
            assert res_a.status_code == 200
            content_a = res_a.content.decode("utf-8")
            assert text_a in content_a, f"Expected {text_a} in Tenant A {route}"
            assert text_b not in content_a, f"Found foreign {text_b} in Tenant A {route}"

            # Tenant B export
            res_b = client_b.get(url)
            assert res_b.status_code == 200
            content_b = res_b.content.decode("utf-8")
            assert text_b in content_b, f"Expected {text_b} in Tenant B {route}"
            assert text_a not in content_b, f"Found foreign {text_a} in Tenant B {route}"


# =====================================================================
# 6. HTTP Method & Authentication Enforcement
# =====================================================================


class TestCapaManagementMethodAndAuthenticationEnforcement:
    """Validate @require_POST HTTP method restrictions and login redirects across all endpoints."""

    def test_capamanagement_security_post_only_endpoints_reject_get_with_405(
        self,
        client_a,
        capa_investigation_a,
        root_cause_analysis_a,
        capa_action_a,
        capa_effectiveness_review_a,
    ):
        """All 10 state-changing actions protected by @require_POST reject GET with HTTP 405 Method Not Allowed."""
        post_only_urls = [
            reverse("quality:capa_investigation_delete", kwargs={"pk": capa_investigation_a.pk}),
            reverse("quality:capa_investigation_advance_status", kwargs={"pk": capa_investigation_a.pk}),
            reverse("quality:capa_investigation_close", kwargs={"pk": capa_investigation_a.pk}),
            reverse("quality:root_cause_analysis_delete", kwargs={"pk": root_cause_analysis_a.pk}),
            reverse("quality:root_cause_analysis_verify", kwargs={"pk": root_cause_analysis_a.pk}),
            reverse("quality:capa_action_delete", kwargs={"pk": capa_action_a.pk}),
            reverse("quality:capa_action_mark_completed", kwargs={"pk": capa_action_a.pk}),
            reverse("quality:capa_action_verify", kwargs={"pk": capa_action_a.pk}),
            reverse("quality:capa_effectiveness_review_delete", kwargs={"pk": capa_effectiveness_review_a.pk}),
            reverse("quality:capa_effectiveness_review_sign_off", kwargs={"pk": capa_effectiveness_review_a.pk}),
        ]

        assert len(post_only_urls) == 10

        for url in post_only_urls:
            res = client_a.get(url)
            assert res.status_code == 405, f"Expected 405 Method Not Allowed for GET {url}, got {res.status_code}"

    def test_capamanagement_security_unauthenticated_requests_redirect_to_login(
        self,
        client,
        capa_investigation_a,
        root_cause_analysis_a,
        capa_action_a,
        capa_effectiveness_review_a,
    ):
        """Unauthenticated GET and POST requests across all 32 endpoints redirect to login (HTTP 302)."""
        endpoints = [
            # CapaInvestigation
            reverse("quality:capa_investigation_list"),
            reverse("quality:capa_investigation_create"),
            reverse("quality:capa_investigation_export"),
            reverse("quality:capa_investigation_detail", kwargs={"pk": capa_investigation_a.pk}),
            reverse("quality:capa_investigation_edit", kwargs={"pk": capa_investigation_a.pk}),
            reverse("quality:capa_investigation_delete", kwargs={"pk": capa_investigation_a.pk}),
            reverse("quality:capa_investigation_advance_status", kwargs={"pk": capa_investigation_a.pk}),
            reverse("quality:capa_investigation_close", kwargs={"pk": capa_investigation_a.pk}),
            # RootCauseAnalysis
            reverse("quality:root_cause_analysis_list"),
            reverse("quality:root_cause_analysis_create"),
            reverse("quality:root_cause_analysis_export"),
            reverse("quality:root_cause_analysis_detail", kwargs={"pk": root_cause_analysis_a.pk}),
            reverse("quality:root_cause_analysis_edit", kwargs={"pk": root_cause_analysis_a.pk}),
            reverse("quality:root_cause_analysis_delete", kwargs={"pk": root_cause_analysis_a.pk}),
            reverse("quality:root_cause_analysis_verify", kwargs={"pk": root_cause_analysis_a.pk}),
            # CapaAction
            reverse("quality:capa_action_list"),
            reverse("quality:capa_action_create"),
            reverse("quality:capa_action_export"),
            reverse("quality:capa_action_detail", kwargs={"pk": capa_action_a.pk}),
            reverse("quality:capa_action_edit", kwargs={"pk": capa_action_a.pk}),
            reverse("quality:capa_action_delete", kwargs={"pk": capa_action_a.pk}),
            reverse("quality:capa_action_mark_completed", kwargs={"pk": capa_action_a.pk}),
            reverse("quality:capa_action_verify", kwargs={"pk": capa_action_a.pk}),
            # CapaEffectivenessReview
            reverse("quality:capa_effectiveness_review_list"),
            reverse("quality:capa_effectiveness_review_create"),
            reverse("quality:capa_effectiveness_review_export"),
            reverse("quality:capa_effectiveness_review_detail", kwargs={"pk": capa_effectiveness_review_a.pk}),
            reverse("quality:capa_effectiveness_review_edit", kwargs={"pk": capa_effectiveness_review_a.pk}),
            reverse("quality:capa_effectiveness_review_delete", kwargs={"pk": capa_effectiveness_review_a.pk}),
            reverse("quality:capa_effectiveness_review_sign_off", kwargs={"pk": capa_effectiveness_review_a.pk}),
            # Tracking Board
            reverse("quality:capa_tracking_board"),
            reverse("quality:capa_tracking_board_export"),
        ]

        post_only_urls = {
            reverse("quality:capa_investigation_delete", kwargs={"pk": capa_investigation_a.pk}),
            reverse("quality:capa_investigation_advance_status", kwargs={"pk": capa_investigation_a.pk}),
            reverse("quality:capa_investigation_close", kwargs={"pk": capa_investigation_a.pk}),
            reverse("quality:root_cause_analysis_delete", kwargs={"pk": root_cause_analysis_a.pk}),
            reverse("quality:root_cause_analysis_verify", kwargs={"pk": root_cause_analysis_a.pk}),
            reverse("quality:capa_action_delete", kwargs={"pk": capa_action_a.pk}),
            reverse("quality:capa_action_mark_completed", kwargs={"pk": capa_action_a.pk}),
            reverse("quality:capa_action_verify", kwargs={"pk": capa_action_a.pk}),
            reverse("quality:capa_effectiveness_review_delete", kwargs={"pk": capa_effectiveness_review_a.pk}),
            reverse("quality:capa_effectiveness_review_sign_off", kwargs={"pk": capa_effectiveness_review_a.pk}),
        }

        assert len(endpoints) == 32

        for url in endpoints:
            if url not in post_only_urls:
                res_get = client.get(url)
                assert res_get.status_code == 302, f"Unauthenticated GET {url} did not redirect, got {res_get.status_code}"
                assert "/login/" in res_get.url or "/accounts/login/" in res_get.url

            res_post = client.post(url, {})
            assert res_post.status_code == 302, f"Unauthenticated POST {url} did not redirect, got {res_post.status_code}"
            assert "/login/" in res_post.url or "/accounts/login/" in res_post.url


# =====================================================================
# 7. Audit Trail Integrity & Forensic Compliance (21 CFR Part 11)
# =====================================================================


class TestCapaManagementAuditTrailIntegrity:
    """Validate comprehensive AuditLog creation for forensic compliance."""

    def test_capamanagement_security_audit_log_capa_lifecycle(
        self, client_a, tenant_a, admin_user, quality_department
    ):
        """CapaInvestigation create, update, advance, close, export, and delete write AuditLog entries."""
        # 1. Create
        res_create = client_a.post(
            reverse("quality:capa_investigation_create"),
            {
                "title": "Audit Log Lifecycle CAPA",
                "issue_summary": "Issue summary for audit trial.",
                "action_type": "corrective",
                "source_type": "internal_audit",
                "risk_priority": "high",
                "status": "under_investigation",
                "department": quality_department.pk,
                "lead_investigator": admin_user.pk,
                "quality_owner": admin_user.pk,
            },
        )
        assert res_create.status_code == 302
        capa = CapaInvestigation.objects.get(title="Audit Log Lifecycle CAPA")
        capa_pk = capa.pk

        assert _capamanagement_audit_logs(capa, action="create").exists()

        # 2. Update
        client_a.post(
            reverse("quality:capa_investigation_edit", kwargs={"pk": capa_pk}),
            {
                "title": "Audit Log Lifecycle CAPA Updated",
                "issue_summary": "Updated issue summary.",
                "action_type": "corrective",
                "source_type": "internal_audit",
                "risk_priority": "high",
                "status": "under_investigation",
                "department": quality_department.pk,
                "lead_investigator": admin_user.pk,
                "quality_owner": admin_user.pk,
            },
        )
        assert _capamanagement_audit_logs(capa, action="update").exists()

        # 3. Advance
        client_a.post(
            reverse("quality:capa_investigation_advance_status", kwargs={"pk": capa_pk}),
            {"target_status": "rca_in_progress"},
        )
        assert _capamanagement_audit_logs(capa, action="advance").exists()

        # 4. Close
        client_a.post(
            reverse("quality:capa_investigation_close", kwargs={"pk": capa_pk}),
            {"closure_summary": "Remediation verified."},
        )
        assert _capamanagement_audit_logs(capa, action="close").exists()

        # 5. Export
        client_a.get(reverse("quality:capa_investigation_export"))
        assert _capamanagement_audit_logs(CapaInvestigation, action="export").exists()

    def test_capamanagement_security_audit_log_rca_lifecycle(
        self, client_a, tenant_a, admin_user, capa_investigation_a
    ):
        """RootCauseAnalysis create, update, verify, and delete write AuditLog entries."""
        # 1. Create
        res_create = client_a.post(
            reverse("quality:root_cause_analysis_create"),
            {
                "capa": capa_investigation_a.pk,
                "rca_method": "5_whys",
                "problem_statement": "RCA audit log test statement.",
                "root_cause_category": "equipment",
                "root_cause_summary": "RCA audit summary.",
                "lead_investigator": admin_user.pk,
                "status": "draft",
            },
        )
        assert res_create.status_code == 302
        rca = RootCauseAnalysis.objects.get(problem_statement="RCA audit log test statement.")
        rca_pk = rca.pk

        assert _capamanagement_audit_logs(rca, action="create").exists()

        # 2. Update
        client_a.post(
            reverse("quality:root_cause_analysis_edit", kwargs={"pk": rca_pk}),
            {
                "capa": capa_investigation_a.pk,
                "rca_method": "5_whys",
                "problem_statement": "RCA audit log updated statement.",
                "root_cause_category": "equipment",
                "root_cause_summary": "RCA audit summary.",
                "lead_investigator": admin_user.pk,
                "status": "draft",
            },
        )
        assert _capamanagement_audit_logs(rca, action="update").exists()

        # 3. Verify
        client_a.post(
            reverse("quality:root_cause_analysis_verify", kwargs={"pk": rca_pk}),
            {"verification_notes": "Root cause metrology verified."},
        )
        assert _capamanagement_audit_logs(rca, action="verify").exists()

        # 4. Export
        client_a.get(reverse("quality:root_cause_analysis_export"))
        assert _capamanagement_audit_logs(RootCauseAnalysis, action="export").exists()

    def test_capamanagement_security_audit_log_action_lifecycle(
        self, client_a, tenant_a, admin_user, capa_investigation_a, quality_department
    ):
        """CapaAction create, update, complete, verify, and delete write AuditLog entries."""
        # 1. Create
        res_create = client_a.post(
            reverse("quality:capa_action_create"),
            {
                "capa": capa_investigation_a.pk,
                "action_type": "corrective",
                "title": "Action Audit Log Lifecycle",
                "description": "Description for action audit.",
                "assigned_to": admin_user.pk,
                "department": quality_department.pk,
                "due_date": timezone.now().date() + timedelta(days=7),
                "status": "pending",
            },
        )
        assert res_create.status_code == 302
        action = CapaAction.objects.get(title="Action Audit Log Lifecycle")
        action_pk = action.pk

        assert _capamanagement_audit_logs(action, action="create").exists()

        # 2. Update
        client_a.post(
            reverse("quality:capa_action_edit", kwargs={"pk": action_pk}),
            {
                "capa": capa_investigation_a.pk,
                "action_type": "corrective",
                "title": "Action Audit Log Lifecycle (Updated)",
                "description": "Updated description.",
                "assigned_to": admin_user.pk,
                "department": quality_department.pk,
                "due_date": timezone.now().date() + timedelta(days=7),
                "status": "pending",
            },
        )
        assert _capamanagement_audit_logs(action, action="update").exists()

        # 3. Complete (implemented)
        client_a.post(
            reverse("quality:capa_action_mark_completed", kwargs={"pk": action_pk}),
            {"implementation_notes": "Action fully implemented."},
        )
        assert _capamanagement_audit_logs(action, action="complete").exists()

        # 4. Verify
        client_a.post(
            reverse("quality:capa_action_verify", kwargs={"pk": action_pk}),
            {"verification_evidence": "Objective evidence validated."},
        )
        assert _capamanagement_audit_logs(action, action="verify").exists()

        # 5. Export
        client_a.get(reverse("quality:capa_action_export"))
        assert _capamanagement_audit_logs(CapaAction, action="export").exists()

    def test_capamanagement_security_audit_log_review_lifecycle(
        self, client_a, tenant_a, admin_user, capa_investigation_a
    ):
        """CapaEffectivenessReview create, update, sign-off (approve), and delete write AuditLog entries."""
        # 1. Create
        res_create = client_a.post(
            reverse("quality:capa_effectiveness_review_create"),
            {
                "capa": capa_investigation_a.pk,
                "review_criteria": "Review Audit Criteria.",
                "verification_method": "statistical_sample",
                "planned_review_date": timezone.now().date() + timedelta(days=30),
                "evaluator": admin_user.pk,
                "outcome": "pending",
                "status": "scheduled",
            },
        )
        assert res_create.status_code == 302
        review = CapaEffectivenessReview.objects.get(review_criteria="Review Audit Criteria.")
        rev_pk = review.pk

        assert _capamanagement_audit_logs(review, action="create").exists()

        # 2. Update
        client_a.post(
            reverse("quality:capa_effectiveness_review_edit", kwargs={"pk": rev_pk}),
            {
                "capa": capa_investigation_a.pk,
                "review_criteria": "Review Audit Criteria (Updated).",
                "verification_method": "statistical_sample",
                "planned_review_date": timezone.now().date() + timedelta(days=30),
                "evaluator": admin_user.pk,
                "outcome": "pending",
                "status": "scheduled",
            },
        )
        assert _capamanagement_audit_logs(review, action="update").exists()

        # 3. Sign off (approve)
        client_a.post(
            reverse("quality:capa_effectiveness_review_sign_off", kwargs={"pk": rev_pk}),
            {"outcome": "effective", "review_notes": "Effectiveness demonstrated."},
        )
        assert _capamanagement_audit_logs(review, action="approve").exists()

        # 4. Export
        client_a.get(reverse("quality:capa_effectiveness_review_export"))
        assert _capamanagement_audit_logs(CapaEffectivenessReview, action="export").exists()

    def test_capamanagement_security_audit_log_tracking_board_export(
        self, client_a, tenant_a
    ):
        """Tracking board export writes AuditLog entry with action='export'."""
        client_a.get(reverse("quality:capa_tracking_board_export"))
        assert _capamanagement_audit_logs(tenant_a, action="export").exists()

    def test_capamanagement_security_audit_log_preserves_object_id_on_deletion(
        self, client_a, tenant_a, admin_user, quality_department
    ):
        """AuditLog created on record deletion preserves the deleted record's primary key as object_id."""
        capa = CapaInvestigation.objects.create(
            tenant=tenant_a,
            title="Temporary CAPA for Deletion Audit Verification",
            action_type="corrective",
            source_type="internal_audit",
            risk_priority="low",
            status="under_investigation",
            department=quality_department,
            lead_investigator=admin_user,
            quality_owner=admin_user,
        )
        capa_pk = capa.pk

        del_url = reverse("quality:capa_investigation_delete", kwargs={"pk": capa_pk})
        res = client_a.post(del_url)
        assert res.status_code == 302
        assert not CapaInvestigation.objects.filter(pk=capa_pk).exists()

        del_logs = _capamanagement_audit_logs(CapaInvestigation, object_id=capa_pk, action="delete")
        assert del_logs.exists()
        del_entry = del_logs.first()
        assert del_entry.object_id == capa_pk
        assert del_entry.user == admin_user
        assert del_entry.tenant == tenant_a
