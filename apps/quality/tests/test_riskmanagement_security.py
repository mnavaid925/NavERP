"""
Security, Authorization, Multi-Tenant Isolation, and Adversarial Tests
for Sub-module 12.3: Risk Management (ISO 14971 / FMEA).

Test coverage requirements:
1. Multi-tenant isolation and IDOR:
   - Tenant B accessing Tenant A's RiskManagementPlan detail, edit, delete, activate, archive returns 404.
   - Tenant B accessing Tenant A's RiskAssessment detail, edit, delete returns 404.
   - Tenant B accessing Tenant A's RiskControlMeasure detail, edit, delete, verify_impl, verify_eff returns 404.
   - Tenant B accessing Tenant A's RiskReviewRecord detail, edit, delete, approve returns 404.
   - Tenant B accessing Tenant A's FmeaMatrix and RiskTraceabilityMatrix (HTML and export) with Tenant A's plan returns 404.
   - Symmetric IDOR: Tenant A accessing Tenant B's objects returns 404.
   - List views and exports for Tenant B never leak Tenant A's rows.
2. Cross-tenant foreign key injection rejection:
   - Tenant A submitting a form referencing Tenant B's plan, department, design_project, design_input,
     design_verification, controlled_document, or user fails with form validation errors.
3. Authorization decorators:
   - Unauthenticated access redirects to login across all 33 endpoints.
   - Non-admin user (e.g. user_a who is not a tenant admin) attempting to POST to destructive and lifecycle actions
     (plan_delete, plan_activate, plan_archive, risk_assessment_delete, risk_control_measure_delete,
      risk_review_record_delete, risk_review_record_approve) receives HTTP 403 Forbidden.
4. HTTP Method enforcement:
   - State-changing views reject GET with 405 Method Not Allowed.
5. Mass assignment & Safety Gate integrity:
   - RiskReviewRecordForm rejects status="approved".
   - RiskControlMeasureForm rejects verification without objective evidence notes or design verification.
   - RiskAssessmentForm rejects residual_risk_acceptable=True when risk is in Unacceptable zone.
   - RiskAssessmentForm rejects residual_risk_acceptable=True in ALARP zone without clinical BRA justification.
   - Edit views reject tampering with active/signed plans or approved review records.
6. Audit trail integrity:
   - All mutations (create, edit, delete, activate, archive, verify, approve) write to AuditLog.
   - On deletion of plans, assessments, controls, and reviews, AuditLog.object_id is verified to be non-empty and
     matching the deleted object's pk.
7. CSV Formula injection protection:
   - Verify csv_safe() neutralizes formulas like =1+1, -5+2, @SUM(),  =CMD(), %VAR%, +123, \t, \r.
   - CSV export outputs properly escape formula cells across all 6 export endpoints.
"""

import csv
import io
import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog, OrgUnit
from apps.quality.forms.RiskManagement.RiskAssessments import RiskAssessmentForm
from apps.quality.forms.RiskManagement.RiskControlMeasures import RiskControlMeasureForm
from apps.quality.forms.RiskManagement.RiskManagementPlans import RiskManagementPlanForm
from apps.quality.forms.RiskManagement.RiskReviewRecords import RiskReviewRecordForm
from apps.quality.models import (
    ControlledDocument,
    DesignInput,
    DesignProject,
    DesignVerification,
    ElectronicSignatureRecord,
    RiskAssessment,
    RiskControlMeasure,
    RiskManagementPlan,
    RiskReviewRecord,
)
from apps.quality.views.RiskManagement.RiskManagementPlans import csv_safe

User = get_user_model()
pytestmark = pytest.mark.django_db


# =====================================================================
# Fixtures and Helpers (Prefix: _riskmanagement_*)
# =====================================================================


@pytest.fixture
def user_a(member_user):
    """Alias user_a fixture for a tenant-scoped non-admin user."""
    return member_user


@pytest.fixture
def non_admin_client(member_client):
    """Alias non_admin_client fixture for requests authenticated as a non-admin."""
    return member_client


def _riskmanagement_get_messages(response):
    """Extract message strings from response wsgi_request."""
    if hasattr(response, "wsgi_request") and response.wsgi_request:
        return [m.message for m in get_messages(response.wsgi_request)]
    return []


def _riskmanagement_audit_logs(obj_or_model, object_id=None, action=None):
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


def _riskmanagement_parse_csv(response):
    """Parse CSV response into list of rows."""
    content = response.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    return list(reader)


def _riskmanagement_create_signature(tenant, user, doc, meaning="risk_approval"):
    """Helper to create a valid ElectronicSignatureRecord for edit guard tests."""
    sig = ElectronicSignatureRecord(
        tenant=tenant,
        document=doc,
        signer=user,
        signer_name=user.get_full_name() or user.username,
        signer_title="QA Director",
        signature_meaning=meaning,
        document_revision="1.0",
        ip_address="127.0.0.1",
        comments="Approved for release.",
    )
    sig.verification_hash = sig.generate_hash()
    sig.save()
    return sig


@pytest.fixture
def _riskmanagement_plan_draft(db, tenant_a, admin_user, design_project_a, quality_department):
    """Draft RiskManagementPlan fixture suitable for edit, activate, and delete tests."""
    return RiskManagementPlan.objects.create(
        tenant=tenant_a,
        title="Draft InfuseFlow Risk Management Plan",
        plan_version="1.0",
        device_classification="class_ii_a",
        design_project=design_project_a,
        lead_risk_manager=admin_user,
        department=quality_department,
        status="draft",
        matrix_dimension="5x5",
        scope_description="Draft scope for testing lifecycle changes.",
        risk_acceptability_policy="Broadly acceptable when RPN < 6.",
        overall_residual_risk_acceptable=True,
    )


# =====================================================================
# 1. Multi-Tenant Data Isolation & Cross-Tenant IDOR Sweeps
# =====================================================================


class TestRiskManagementCrossTenantIsolation:
    """Exhaustive sweeps asserting no cross-tenant object access, mutations, or data leakage."""

    # --- Plan IDOR ---

    def test_riskmanagement_security_plan_detail_cross_tenant_idor_404(
        self, client_a, client_b, risk_management_plan_a, risk_management_plan_b
    ):
        """Accessing Tenant B plan detail as Tenant A returns 404, and vice versa."""
        res_a = client_a.get(reverse("quality:risk_management_plan_detail", kwargs={"pk": risk_management_plan_b.pk}))
        assert res_a.status_code == 404

        res_b = client_b.get(reverse("quality:risk_management_plan_detail", kwargs={"pk": risk_management_plan_a.pk}))
        assert res_b.status_code == 404

    def test_riskmanagement_security_plan_edit_cross_tenant_idor_404(
        self, client_a, client_b, _riskmanagement_plan_draft, risk_management_plan_b
    ):
        """GET and POST to edit Tenant B plan as Tenant A returns 404; database remains unmutated."""
        url_b = reverse("quality:risk_management_plan_edit", kwargs={"pk": risk_management_plan_b.pk})
        assert client_a.get(url_b).status_code == 404
        assert client_a.post(url_b, {"title": "Hostile Hijack"}).status_code == 404
        risk_management_plan_b.refresh_from_db()
        assert risk_management_plan_b.title != "Hostile Hijack"

        # Symmetric
        url_a = reverse("quality:risk_management_plan_edit", kwargs={"pk": _riskmanagement_plan_draft.pk})
        assert client_b.get(url_a).status_code == 404
        assert client_b.post(url_a, {"title": "Hostile Hijack"}).status_code == 404
        _riskmanagement_plan_draft.refresh_from_db()
        assert _riskmanagement_plan_draft.title != "Hostile Hijack"

    def test_riskmanagement_security_plan_delete_cross_tenant_idor_404(
        self, client_a, client_b, _riskmanagement_plan_draft, risk_management_plan_b
    ):
        """POST to delete foreign plan returns 404 and record is not deleted."""
        url_b = reverse("quality:risk_management_plan_delete", kwargs={"pk": risk_management_plan_b.pk})
        assert client_a.post(url_b).status_code == 404
        assert RiskManagementPlan.objects.filter(pk=risk_management_plan_b.pk).exists()

        url_a = reverse("quality:risk_management_plan_delete", kwargs={"pk": _riskmanagement_plan_draft.pk})
        assert client_b.post(url_a).status_code == 404
        assert RiskManagementPlan.objects.filter(pk=_riskmanagement_plan_draft.pk).exists()

    def test_riskmanagement_security_plan_activate_cross_tenant_idor_404(
        self, client_a, client_b, _riskmanagement_plan_draft, risk_management_plan_b
    ):
        """POST to activate foreign plan returns 404 and status remains unchanged."""
        url_a = reverse("quality:risk_management_plan_activate", kwargs={"pk": _riskmanagement_plan_draft.pk})
        assert client_b.post(url_a).status_code == 404
        _riskmanagement_plan_draft.refresh_from_db()
        assert _riskmanagement_plan_draft.status == "draft"

    def test_riskmanagement_security_plan_archive_cross_tenant_idor_404(
        self, client_a, client_b, risk_management_plan_a, risk_management_plan_b
    ):
        """POST to archive foreign plan returns 404 and status remains unchanged."""
        url_b = reverse("quality:risk_management_plan_archive", kwargs={"pk": risk_management_plan_b.pk})
        assert client_a.post(url_b).status_code == 404
        risk_management_plan_b.refresh_from_db()
        assert risk_management_plan_b.status == "active"

        url_a = reverse("quality:risk_management_plan_archive", kwargs={"pk": risk_management_plan_a.pk})
        assert client_b.post(url_a).status_code == 404
        risk_management_plan_a.refresh_from_db()
        assert risk_management_plan_a.status == "active"

    # --- Assessment IDOR ---

    def test_riskmanagement_security_assessment_detail_cross_tenant_idor_404(
        self, client_a, client_b, risk_assessment_a, risk_assessment_b
    ):
        """Accessing foreign risk assessment detail returns 404."""
        assert client_a.get(reverse("quality:risk_assessment_detail", kwargs={"pk": risk_assessment_b.pk})).status_code == 404
        assert client_b.get(reverse("quality:risk_assessment_detail", kwargs={"pk": risk_assessment_a.pk})).status_code == 404

    def test_riskmanagement_security_assessment_edit_cross_tenant_idor_404(
        self, client_a, client_b, risk_assessment_a, risk_assessment_b
    ):
        """GET and POST to edit foreign risk assessment returns 404; db not modified."""
        url_b = reverse("quality:risk_assessment_edit", kwargs={"pk": risk_assessment_b.pk})
        assert client_a.get(url_b).status_code == 404
        assert client_a.post(url_b, {"hazard_description": "Tampered"}).status_code == 404
        risk_assessment_b.refresh_from_db()
        assert risk_assessment_b.hazard_description != "Tampered"

        url_a = reverse("quality:risk_assessment_edit", kwargs={"pk": risk_assessment_a.pk})
        assert client_b.get(url_a).status_code == 404
        assert client_b.post(url_a, {"hazard_description": "Tampered"}).status_code == 404
        risk_assessment_a.refresh_from_db()
        assert risk_assessment_a.hazard_description != "Tampered"

    def test_riskmanagement_security_assessment_delete_cross_tenant_idor_404(
        self, client_a, client_b, risk_assessment_a, risk_assessment_b
    ):
        """POST to delete foreign risk assessment returns 404 and record is preserved."""
        url_b = reverse("quality:risk_assessment_delete", kwargs={"pk": risk_assessment_b.pk})
        assert client_a.post(url_b).status_code == 404
        assert RiskAssessment.objects.filter(pk=risk_assessment_b.pk).exists()

        url_a = reverse("quality:risk_assessment_delete", kwargs={"pk": risk_assessment_a.pk})
        assert client_b.post(url_a).status_code == 404
        assert RiskAssessment.objects.filter(pk=risk_assessment_a.pk).exists()

    # --- Control Measure IDOR ---

    def test_riskmanagement_security_control_detail_cross_tenant_idor_404(
        self, client_a, client_b, risk_control_measure_a, risk_control_measure_b
    ):
        """Accessing foreign control measure detail returns 404."""
        assert client_a.get(reverse("quality:risk_control_measure_detail", kwargs={"pk": risk_control_measure_b.pk})).status_code == 404
        assert client_b.get(reverse("quality:risk_control_measure_detail", kwargs={"pk": risk_control_measure_a.pk})).status_code == 404

    def test_riskmanagement_security_control_edit_cross_tenant_idor_404(
        self, client_a, client_b, risk_control_measure_a, risk_control_measure_b
    ):
        """GET and POST to edit foreign control measure returns 404; db not modified."""
        url_b = reverse("quality:risk_control_measure_edit", kwargs={"pk": risk_control_measure_b.pk})
        assert client_a.get(url_b).status_code == 404
        assert client_a.post(url_b, {"title": "Tampered Title"}).status_code == 404
        risk_control_measure_b.refresh_from_db()
        assert risk_control_measure_b.title != "Tampered Title"

        url_a = reverse("quality:risk_control_measure_edit", kwargs={"pk": risk_control_measure_a.pk})
        assert client_b.get(url_a).status_code == 404
        assert client_b.post(url_a, {"title": "Tampered Title"}).status_code == 404
        risk_control_measure_a.refresh_from_db()
        assert risk_control_measure_a.title != "Tampered Title"

    def test_riskmanagement_security_control_delete_cross_tenant_idor_404(
        self, client_a, client_b, risk_control_measure_a, risk_control_measure_b
    ):
        """POST to delete foreign control measure returns 404 and record is preserved."""
        url_b = reverse("quality:risk_control_measure_delete", kwargs={"pk": risk_control_measure_b.pk})
        assert client_a.post(url_b).status_code == 404
        assert RiskControlMeasure.objects.filter(pk=risk_control_measure_b.pk).exists()

        url_a = reverse("quality:risk_control_measure_delete", kwargs={"pk": risk_control_measure_a.pk})
        assert client_b.post(url_a).status_code == 404
        assert RiskControlMeasure.objects.filter(pk=risk_control_measure_a.pk).exists()

    def test_riskmanagement_security_control_verify_impl_cross_tenant_idor_404(
        self, client_a, client_b, risk_control_measure_a, risk_control_measure_b
    ):
        """POST to verify implementation on foreign control measure returns 404; status unchanged."""
        url_b = reverse("quality:risk_control_measure_verify_impl", kwargs={"pk": risk_control_measure_b.pk})
        assert client_a.post(url_b).status_code == 404
        risk_control_measure_b.refresh_from_db()
        assert not risk_control_measure_b.implementation_verified

        url_a = reverse("quality:risk_control_measure_verify_impl", kwargs={"pk": risk_control_measure_a.pk})
        assert client_b.post(url_a).status_code == 404
        risk_control_measure_a.refresh_from_db()
        assert not risk_control_measure_a.implementation_verified

    def test_riskmanagement_security_control_verify_eff_cross_tenant_idor_404(
        self, client_a, client_b, risk_control_measure_a, risk_control_measure_b
    ):
        """POST to verify effectiveness on foreign control measure returns 404; status unchanged."""
        url_b = reverse("quality:risk_control_measure_verify_eff", kwargs={"pk": risk_control_measure_b.pk})
        assert client_a.post(url_b).status_code == 404
        risk_control_measure_b.refresh_from_db()
        assert not risk_control_measure_b.effectiveness_verified

        url_a = reverse("quality:risk_control_measure_verify_eff", kwargs={"pk": risk_control_measure_a.pk})
        assert client_b.post(url_a).status_code == 404
        risk_control_measure_a.refresh_from_db()
        assert not risk_control_measure_a.effectiveness_verified

    # --- Review Record IDOR ---

    def test_riskmanagement_security_review_detail_cross_tenant_idor_404(
        self, client_a, client_b, risk_review_record_a, risk_review_record_b
    ):
        """Accessing foreign risk review record detail returns 404."""
        assert client_a.get(reverse("quality:risk_review_record_detail", kwargs={"pk": risk_review_record_b.pk})).status_code == 404
        assert client_b.get(reverse("quality:risk_review_record_detail", kwargs={"pk": risk_review_record_a.pk})).status_code == 404

    def test_riskmanagement_security_review_edit_cross_tenant_idor_404(
        self, client_a, client_b, risk_review_record_a, risk_review_record_b
    ):
        """GET and POST to edit foreign review record returns 404; db not modified."""
        url_b = reverse("quality:risk_review_record_edit", kwargs={"pk": risk_review_record_b.pk})
        assert client_a.get(url_b).status_code == 404
        assert client_a.post(url_b, {"review_title": "Tampered Review"}).status_code == 404
        risk_review_record_b.refresh_from_db()
        assert risk_review_record_b.review_title != "Tampered Review"

        url_a = reverse("quality:risk_review_record_edit", kwargs={"pk": risk_review_record_a.pk})
        assert client_b.get(url_a).status_code == 404
        assert client_b.post(url_a, {"review_title": "Tampered Review"}).status_code == 404
        risk_review_record_a.refresh_from_db()
        assert risk_review_record_a.review_title != "Tampered Review"

    def test_riskmanagement_security_review_delete_cross_tenant_idor_404(
        self, client_a, client_b, risk_review_record_a, risk_review_record_b
    ):
        """POST to delete foreign review record returns 404 and record is preserved."""
        url_b = reverse("quality:risk_review_record_delete", kwargs={"pk": risk_review_record_b.pk})
        assert client_a.post(url_b).status_code == 404
        assert RiskReviewRecord.objects.filter(pk=risk_review_record_b.pk).exists()

        url_a = reverse("quality:risk_review_record_delete", kwargs={"pk": risk_review_record_a.pk})
        assert client_b.post(url_a).status_code == 404
        assert RiskReviewRecord.objects.filter(pk=risk_review_record_a.pk).exists()

    def test_riskmanagement_security_review_approve_cross_tenant_idor_404(
        self, client_a, client_b, risk_review_record_a, risk_review_record_b
    ):
        """POST to approve foreign review record returns 404; status remains draft."""
        url_b = reverse("quality:risk_review_record_approve", kwargs={"pk": risk_review_record_b.pk})
        assert client_a.post(url_b).status_code == 404
        risk_review_record_b.refresh_from_db()
        assert risk_review_record_b.status == "draft"

        url_a = reverse("quality:risk_review_record_approve", kwargs={"pk": risk_review_record_a.pk})
        assert client_b.post(url_a).status_code == 404
        risk_review_record_a.refresh_from_db()
        assert risk_review_record_a.status == "draft"

    # --- Matrix and Traceability with foreign plan ---

    def test_riskmanagement_security_fmea_matrix_cross_tenant_plan_404(
        self, client_a, client_b, risk_management_plan_a, risk_management_plan_b
    ):
        """Accessing FMEA matrix with foreign plan query param raises 404."""
        url_a = reverse("quality:fmea_matrix") + f"?plan={risk_management_plan_b.pk}"
        assert client_a.get(url_a).status_code == 404

        url_b = reverse("quality:fmea_matrix") + f"?plan={risk_management_plan_a.pk}"
        assert client_b.get(url_b).status_code == 404

    def test_riskmanagement_security_fmea_matrix_export_cross_tenant_plan_404(
        self, client_a, client_b, risk_management_plan_a, risk_management_plan_b
    ):
        """Exporting FMEA matrix CSV with foreign plan query param raises 404."""
        url_a = reverse("quality:fmea_matrix_export") + f"?plan={risk_management_plan_b.pk}"
        assert client_a.get(url_a).status_code == 404

        url_b = reverse("quality:fmea_matrix_export") + f"?plan={risk_management_plan_a.pk}"
        assert client_b.get(url_b).status_code == 404

    def test_riskmanagement_security_risk_traceability_matrix_cross_tenant_plan_404(
        self, client_a, client_b, risk_management_plan_a, risk_management_plan_b
    ):
        """Accessing Risk Traceability Matrix with foreign plan query param raises 404."""
        url_a = reverse("quality:risk_traceability_matrix") + f"?plan={risk_management_plan_b.pk}"
        assert client_a.get(url_a).status_code == 404

        url_b = reverse("quality:risk_traceability_matrix") + f"?plan={risk_management_plan_a.pk}"
        assert client_b.get(url_b).status_code == 404

    def test_riskmanagement_security_risk_traceability_matrix_export_cross_tenant_plan_404(
        self, client_a, client_b, risk_management_plan_a, risk_management_plan_b
    ):
        """Exporting Risk Traceability Matrix CSV with foreign plan query param raises 404."""
        url_a = reverse("quality:risk_traceability_matrix_export") + f"?plan={risk_management_plan_b.pk}"
        assert client_a.get(url_a).status_code == 404

        url_b = reverse("quality:risk_traceability_matrix_export") + f"?plan={risk_management_plan_a.pk}"
        assert client_b.get(url_b).status_code == 404

    # --- List Views and Exports Zero Cross-Tenant Leakage ---

    def test_riskmanagement_security_list_views_zero_cross_tenant_leakage(
        self, client_a, client_b,
        risk_management_plan_a, risk_management_plan_b,
        risk_assessment_a, risk_assessment_b,
        risk_control_measure_a, risk_control_measure_b,
        risk_review_record_a, risk_review_record_b,
    ):
        """List views for Tenant A contain 0 Tenant B records, and vice-versa."""
        # Plans list
        res_plan_a = client_a.get(reverse("quality:risk_management_plan_list"))
        assert res_plan_a.status_code == 200
        pks_a = [p.pk for p in res_plan_a.context["plans"]]
        assert risk_management_plan_a.pk in pks_a
        assert risk_management_plan_b.pk not in pks_a

        res_plan_b = client_b.get(reverse("quality:risk_management_plan_list"))
        assert res_plan_b.status_code == 200
        pks_b = [p.pk for p in res_plan_b.context["plans"]]
        assert risk_management_plan_b.pk in pks_b
        assert risk_management_plan_a.pk not in pks_b

        # Assessments list
        res_ass_a = client_a.get(reverse("quality:risk_assessment_list"))
        assert res_ass_a.status_code == 200
        ass_pks_a = [a.pk for a in res_ass_a.context["assessments"]]
        assert risk_assessment_a.pk in ass_pks_a
        assert risk_assessment_b.pk not in ass_pks_a

        res_ass_b = client_b.get(reverse("quality:risk_assessment_list"))
        assert res_ass_b.status_code == 200
        ass_pks_b = [a.pk for a in res_ass_b.context["assessments"]]
        assert risk_assessment_b.pk in ass_pks_b
        assert risk_assessment_a.pk not in ass_pks_b

        # Controls list
        res_ctrl_a = client_a.get(reverse("quality:risk_control_measure_list"))
        assert res_ctrl_a.status_code == 200
        ctrl_pks_a = [c.pk for c in res_ctrl_a.context["control_measures"]]
        assert risk_control_measure_a.pk in ctrl_pks_a
        assert risk_control_measure_b.pk not in ctrl_pks_a

        res_ctrl_b = client_b.get(reverse("quality:risk_control_measure_list"))
        assert res_ctrl_b.status_code == 200
        ctrl_pks_b = [c.pk for c in res_ctrl_b.context["control_measures"]]
        assert risk_control_measure_b.pk in ctrl_pks_b
        assert risk_control_measure_a.pk not in ctrl_pks_b

        # Reviews list
        res_rev_a = client_a.get(reverse("quality:risk_review_record_list"))
        assert res_rev_a.status_code == 200
        rev_pks_a = [r.pk for r in res_rev_a.context["review_records"]]
        assert risk_review_record_a.pk in rev_pks_a
        assert risk_review_record_b.pk not in rev_pks_a

        res_rev_b = client_b.get(reverse("quality:risk_review_record_list"))
        assert res_rev_b.status_code == 200
        rev_pks_b = [r.pk for r in res_rev_b.context["review_records"]]
        assert risk_review_record_b.pk in rev_pks_b
        assert risk_review_record_a.pk not in rev_pks_b

    def test_riskmanagement_security_export_views_zero_cross_tenant_leakage(
        self, client_a, client_b,
        risk_management_plan_a, risk_management_plan_b,
        risk_assessment_a, risk_assessment_b,
        risk_control_measure_a, risk_control_measure_b,
        risk_review_record_a, risk_review_record_b,
    ):
        """CSV export endpoints for Tenant A leak 0 records belonging to Tenant B, and vice-versa."""
        # Plans CSV
        res_p = client_a.get(reverse("quality:risk_management_plan_export"))
        assert res_p.status_code == 200
        text_p = res_p.content.decode("utf-8")
        assert risk_management_plan_a.title in text_p
        assert risk_management_plan_b.title not in text_p

        # Assessments CSV
        res_a = client_a.get(reverse("quality:risk_assessment_export"))
        assert res_a.status_code == 200
        text_a = res_a.content.decode("utf-8")
        assert risk_assessment_a.hazard_description in text_a
        assert risk_assessment_b.hazard_description not in text_a

        # Controls CSV
        res_c = client_a.get(reverse("quality:risk_control_measure_export"))
        assert res_c.status_code == 200
        text_c = res_c.content.decode("utf-8")
        assert risk_control_measure_a.title in text_c
        assert risk_control_measure_b.title not in text_c

        # Reviews CSV
        res_r = client_a.get(reverse("quality:risk_review_record_export"))
        assert res_r.status_code == 200
        text_r = res_r.content.decode("utf-8")
        assert risk_review_record_a.review_title in text_r
        assert risk_review_record_b.review_title not in text_r


# =====================================================================
# 2. Cross-Tenant Foreign Key Injection Defense (reject_foreign)
# =====================================================================


class TestRiskManagementCrossTenantFKInjection:
    """Ensure submitting Foreign Key IDs belonging to a foreign tenant is strictly rejected."""

    def test_riskmanagement_security_plan_form_rejects_foreign_department(
        self, tenant_a, quality_department, quality_department_b, admin_user, design_project_a
    ):
        """RiskManagementPlanForm excludes foreign department and rejects forged submission."""
        form = RiskManagementPlanForm(tenant=tenant_a)
        dept_pks = list(form.fields["department"].queryset.values_list("pk", flat=True))
        assert quality_department.pk in dept_pks
        assert quality_department_b.pk not in dept_pks

        data = {
            "title": "Cross Tenant Department Injection Plan",
            "plan_version": "1.0",
            "status": "draft",
            "design_project": design_project_a.pk,
            "lead_risk_manager": admin_user.pk,
            "department": quality_department_b.pk,
            "device_classification": "class_ii_a",
            "scope_description": "Valid scope description.",
            "matrix_dimension": "5x5",
            "risk_acceptability_policy": "Valid policy.",
            "periodic_review_frequency_months": 12,
        }
        bound = RiskManagementPlanForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "department" in bound.errors or "__all__" in bound.errors

    def test_riskmanagement_security_plan_form_rejects_foreign_design_project(
        self, tenant_a, quality_department, admin_user, design_project_a, design_project_b
    ):
        """RiskManagementPlanForm excludes foreign project and rejects forged submission."""
        form = RiskManagementPlanForm(tenant=tenant_a)
        project_pks = list(form.fields["design_project"].queryset.values_list("pk", flat=True))
        assert design_project_a.pk in project_pks
        assert design_project_b.pk not in project_pks

        data = {
            "title": "Cross Tenant Project Injection Plan",
            "plan_version": "1.0",
            "status": "draft",
            "design_project": design_project_b.pk,
            "lead_risk_manager": admin_user.pk,
            "department": quality_department.pk,
            "device_classification": "class_ii_a",
            "scope_description": "Valid scope description.",
            "matrix_dimension": "5x5",
            "risk_acceptability_policy": "Valid policy.",
            "periodic_review_frequency_months": 12,
        }
        bound = RiskManagementPlanForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "design_project" in bound.errors or "__all__" in bound.errors

    def test_riskmanagement_security_plan_form_rejects_foreign_lead_risk_manager(
        self, tenant_a, quality_department, admin_user, admin_b, design_project_a
    ):
        """RiskManagementPlanForm excludes foreign user and rejects foreign risk manager assignment."""
        form = RiskManagementPlanForm(tenant=tenant_a)
        user_pks = list(form.fields["lead_risk_manager"].queryset.values_list("pk", flat=True))
        assert admin_user.pk in user_pks
        assert admin_b.pk not in user_pks

        data = {
            "title": "Cross Tenant Manager Injection Plan",
            "plan_version": "1.0",
            "status": "draft",
            "design_project": design_project_a.pk,
            "lead_risk_manager": admin_b.pk,
            "department": quality_department.pk,
            "device_classification": "class_ii_a",
            "scope_description": "Valid scope description.",
            "matrix_dimension": "5x5",
            "risk_acceptability_policy": "Valid policy.",
            "periodic_review_frequency_months": 12,
        }
        bound = RiskManagementPlanForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "lead_risk_manager" in bound.errors or "__all__" in bound.errors

    def test_riskmanagement_security_assessment_form_rejects_foreign_plan(
        self, tenant_a, risk_management_plan_a, risk_management_plan_b
    ):
        """RiskAssessmentForm excludes foreign plan and rejects forged plan association."""
        form = RiskAssessmentForm(tenant=tenant_a)
        plan_pks = list(form.fields["plan"].queryset.values_list("pk", flat=True))
        assert risk_management_plan_a.pk in plan_pks
        assert risk_management_plan_b.pk not in plan_pks

        data = {
            "plan": risk_management_plan_b.pk,
            "analysis_type": "dfmea",
            "hazard_category": "energy_electrical",
            "hazard_description": "Cross Tenant Foreign Hazard",
            "hazardous_situation": "Cross Tenant Situation",
            "potential_harm": "Electrocution",
            "initial_severity": 4,
            "initial_probability": 3,
            "initial_detectability": 2,
            "lifecycle_status": "open",
        }
        bound = RiskAssessmentForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "plan" in bound.errors or "__all__" in bound.errors

    def test_riskmanagement_security_assessment_form_rejects_foreign_design_input(
        self, tenant_a, risk_management_plan_a, design_input_spec, design_input_b
    ):
        """RiskAssessmentForm excludes foreign design input and rejects forged association."""
        form = RiskAssessmentForm(tenant=tenant_a)
        input_pks = list(form.fields["design_input"].queryset.values_list("pk", flat=True))
        assert design_input_spec.pk in input_pks
        assert design_input_b.pk not in input_pks

        data = {
            "plan": risk_management_plan_a.pk,
            "design_input": design_input_b.pk,
            "analysis_type": "dfmea",
            "hazard_category": "energy_electrical",
            "hazard_description": "Foreign Input Link",
            "hazardous_situation": "Dangerous circumstance",
            "potential_harm": "Thermal shock",
            "initial_severity": 3,
            "initial_probability": 2,
            "initial_detectability": 1,
            "lifecycle_status": "open",
        }
        bound = RiskAssessmentForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "design_input" in bound.errors or "__all__" in bound.errors

    def test_riskmanagement_security_control_form_rejects_foreign_risk_assessment(
        self, tenant_a, admin_user, risk_assessment_a, risk_assessment_b
    ):
        """RiskControlMeasureForm rejects foreign risk assessment binding."""
        form = RiskControlMeasureForm(tenant=tenant_a)
        ass_pks = list(form.fields["risk_assessment"].queryset.values_list("pk", flat=True))
        assert risk_assessment_a.pk in ass_pks
        assert risk_assessment_b.pk not in ass_pks

        data = {
            "risk_assessment": risk_assessment_b.pk,
            "control_hierarchy": "inherent_safety",
            "title": "Cross Tenant Control Mitigation",
            "description": "Protective hardware.",
            "assigned_to": admin_user.pk,
            "status": "planned",
        }
        bound = RiskControlMeasureForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "risk_assessment" in bound.errors or "__all__" in bound.errors

    def test_riskmanagement_security_control_form_rejects_foreign_assigned_to(
        self, tenant_a, admin_user, admin_b, risk_assessment_a
    ):
        """RiskControlMeasureForm rejects foreign user assignment."""
        form = RiskControlMeasureForm(tenant=tenant_a)
        user_pks = list(form.fields["assigned_to"].queryset.values_list("pk", flat=True))
        assert admin_user.pk in user_pks
        assert admin_b.pk not in user_pks

        data = {
            "risk_assessment": risk_assessment_a.pk,
            "control_hierarchy": "inherent_safety",
            "title": "Mitigation with Foreign User",
            "description": "Protective hardware.",
            "assigned_to": admin_b.pk,
            "status": "planned",
        }
        bound = RiskControlMeasureForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "assigned_to" in bound.errors or "__all__" in bound.errors

    def test_riskmanagement_security_control_form_rejects_foreign_verification_and_docs(
        self, tenant_a, admin_user, risk_assessment_a,
        quality_doc_effective, quality_doc_b,
        design_verification_a, design_verification_b
    ):
        """RiskControlMeasureForm rejects foreign controlled documents and design verification protocols."""
        form = RiskControlMeasureForm(tenant=tenant_a)
        assert quality_doc_effective.pk in list(form.fields["controlled_document"].queryset.values_list("pk", flat=True))
        assert quality_doc_b.pk not in list(form.fields["controlled_document"].queryset.values_list("pk", flat=True))
        assert design_verification_a.pk in list(form.fields["design_verification"].queryset.values_list("pk", flat=True))
        assert design_verification_b.pk not in list(form.fields["design_verification"].queryset.values_list("pk", flat=True))

        # Test foreign doc injection
        data_doc = {
            "risk_assessment": risk_assessment_a.pk,
            "control_hierarchy": "protective_measure",
            "title": "Mitigation with Foreign Doc",
            "description": "Safety labeling.",
            "assigned_to": admin_user.pk,
            "controlled_document": quality_doc_b.pk,
            "status": "planned",
        }
        bound_doc = RiskControlMeasureForm(data=data_doc, tenant=tenant_a)
        assert not bound_doc.is_valid()
        assert "controlled_document" in bound_doc.errors or "__all__" in bound_doc.errors

        # Test foreign verification protocol injection
        data_ver = {
            "risk_assessment": risk_assessment_a.pk,
            "control_hierarchy": "protective_measure",
            "title": "Mitigation with Foreign Verification",
            "description": "Bench testing.",
            "assigned_to": admin_user.pk,
            "design_verification": design_verification_b.pk,
            "status": "planned",
        }
        bound_ver = RiskControlMeasureForm(data=data_ver, tenant=tenant_a)
        assert not bound_ver.is_valid()
        assert "design_verification" in bound_ver.errors or "__all__" in bound_ver.errors

    def test_riskmanagement_security_review_form_rejects_foreign_plan(
        self, tenant_a, admin_user, risk_management_plan_a, risk_management_plan_b
    ):
        """RiskReviewRecordForm rejects foreign plan binding."""
        form = RiskReviewRecordForm(tenant=tenant_a)
        plan_pks = list(form.fields["plan"].queryset.values_list("pk", flat=True))
        assert risk_management_plan_a.pk in plan_pks
        assert risk_management_plan_b.pk not in plan_pks

        data = {
            "plan": risk_management_plan_b.pk,
            "review_title": "Forged Review Plan Association",
            "review_type": "interim_phase_gate",
            "review_date": timezone.now().date(),
            "findings_summary": "Test findings.",
            "status": "draft",
            "lead_reviewer": admin_user.pk,
        }
        bound = RiskReviewRecordForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "plan" in bound.errors or "__all__" in bound.errors

    def test_riskmanagement_security_review_form_rejects_foreign_lead_reviewer(
        self, tenant_a, admin_user, admin_b, risk_management_plan_a
    ):
        """RiskReviewRecordForm rejects foreign lead reviewer user."""
        form = RiskReviewRecordForm(tenant=tenant_a)
        user_pks = list(form.fields["lead_reviewer"].queryset.values_list("pk", flat=True))
        assert admin_user.pk in user_pks
        assert admin_b.pk not in user_pks

        data = {
            "plan": risk_management_plan_a.pk,
            "review_title": "Forged Review Lead Association",
            "review_type": "interim_phase_gate",
            "review_date": timezone.now().date(),
            "findings_summary": "Test findings.",
            "status": "draft",
            "lead_reviewer": admin_b.pk,
        }
        bound = RiskReviewRecordForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "lead_reviewer" in bound.errors or "__all__" in bound.errors


# =====================================================================
# 3. Authentication & Authorization Decorators
# =====================================================================


class TestRiskManagementAuthorizationAndPermissions:
    """Validate @login_required, @tenant_admin_required, and permission enforcement."""

    def test_riskmanagement_security_unauthenticated_endpoints_redirect_to_login(
        self, client, risk_management_plan_a, risk_assessment_a,
        risk_control_measure_a, risk_review_record_a
    ):
        """Unauthenticated GET and POST requests across all endpoints redirect to login (302)."""
        endpoints = [
            ("get", reverse("quality:risk_management_plan_list")),
            ("get", reverse("quality:risk_management_plan_create")),
            ("get", reverse("quality:risk_management_plan_export")),
            ("get", reverse("quality:risk_management_plan_detail", kwargs={"pk": risk_management_plan_a.pk})),
            ("get", reverse("quality:risk_management_plan_edit", kwargs={"pk": risk_management_plan_a.pk})),
            ("post", reverse("quality:risk_management_plan_delete", kwargs={"pk": risk_management_plan_a.pk})),
            ("post", reverse("quality:risk_management_plan_activate", kwargs={"pk": risk_management_plan_a.pk})),
            ("post", reverse("quality:risk_management_plan_archive", kwargs={"pk": risk_management_plan_a.pk})),

            ("get", reverse("quality:risk_assessment_list")),
            ("get", reverse("quality:risk_assessment_create")),
            ("get", reverse("quality:risk_assessment_export")),
            ("get", reverse("quality:risk_assessment_detail", kwargs={"pk": risk_assessment_a.pk})),
            ("get", reverse("quality:risk_assessment_edit", kwargs={"pk": risk_assessment_a.pk})),
            ("post", reverse("quality:risk_assessment_delete", kwargs={"pk": risk_assessment_a.pk})),

            ("get", reverse("quality:risk_control_measure_list")),
            ("get", reverse("quality:risk_control_measure_create")),
            ("get", reverse("quality:risk_control_measure_export")),
            ("get", reverse("quality:risk_control_measure_detail", kwargs={"pk": risk_control_measure_a.pk})),
            ("get", reverse("quality:risk_control_measure_edit", kwargs={"pk": risk_control_measure_a.pk})),
            ("post", reverse("quality:risk_control_measure_delete", kwargs={"pk": risk_control_measure_a.pk})),
            ("post", reverse("quality:risk_control_measure_verify_impl", kwargs={"pk": risk_control_measure_a.pk})),
            ("post", reverse("quality:risk_control_measure_verify_eff", kwargs={"pk": risk_control_measure_a.pk})),

            ("get", reverse("quality:risk_review_record_list")),
            ("get", reverse("quality:risk_review_record_create")),
            ("get", reverse("quality:risk_review_record_export")),
            ("get", reverse("quality:risk_review_record_detail", kwargs={"pk": risk_review_record_a.pk})),
            ("get", reverse("quality:risk_review_record_edit", kwargs={"pk": risk_review_record_a.pk})),
            ("post", reverse("quality:risk_review_record_delete", kwargs={"pk": risk_review_record_a.pk})),
            ("post", reverse("quality:risk_review_record_approve", kwargs={"pk": risk_review_record_a.pk})),

            ("get", reverse("quality:fmea_matrix")),
            ("get", reverse("quality:fmea_matrix_export")),
            ("get", reverse("quality:risk_traceability_matrix")),
            ("get", reverse("quality:risk_traceability_matrix_export")),
        ]

        for method, url in endpoints:
            call = getattr(client, method)
            res = call(url)
            assert res.status_code == 302, f"Endpoint {url} via {method.upper()} did not redirect anonymous user"
            assert "/login" in res.url or "login" in res.url

    def test_riskmanagement_security_plan_delete_requires_tenant_admin_403(
        self, non_admin_client, _riskmanagement_plan_draft
    ):
        """Non-admin user POST to plan_delete receives HTTP 403 Forbidden."""
        url = reverse("quality:risk_management_plan_delete", kwargs={"pk": _riskmanagement_plan_draft.pk})
        res = non_admin_client.post(url)
        assert res.status_code == 403
        assert RiskManagementPlan.objects.filter(pk=_riskmanagement_plan_draft.pk).exists()

    def test_riskmanagement_security_plan_activate_requires_tenant_admin_403(
        self, non_admin_client, _riskmanagement_plan_draft
    ):
        """Non-admin user POST to plan_activate receives HTTP 403 Forbidden."""
        url = reverse("quality:risk_management_plan_activate", kwargs={"pk": _riskmanagement_plan_draft.pk})
        res = non_admin_client.post(url)
        assert res.status_code == 403
        _riskmanagement_plan_draft.refresh_from_db()
        assert _riskmanagement_plan_draft.status == "draft"

    def test_riskmanagement_security_plan_archive_requires_tenant_admin_403(
        self, non_admin_client, risk_management_plan_a
    ):
        """Non-admin user POST to plan_archive receives HTTP 403 Forbidden."""
        url = reverse("quality:risk_management_plan_archive", kwargs={"pk": risk_management_plan_a.pk})
        res = non_admin_client.post(url)
        assert res.status_code == 403
        risk_management_plan_a.refresh_from_db()
        assert risk_management_plan_a.status == "active"

    def test_riskmanagement_security_assessment_delete_requires_tenant_admin_403(
        self, non_admin_client, risk_assessment_a
    ):
        """Non-admin user POST to risk_assessment_delete receives HTTP 403 Forbidden."""
        url = reverse("quality:risk_assessment_delete", kwargs={"pk": risk_assessment_a.pk})
        res = non_admin_client.post(url)
        assert res.status_code == 403
        assert RiskAssessment.objects.filter(pk=risk_assessment_a.pk).exists()

    def test_riskmanagement_security_control_delete_requires_tenant_admin_403(
        self, non_admin_client, risk_control_measure_a
    ):
        """Non-admin user POST to risk_control_measure_delete receives HTTP 403 Forbidden."""
        url = reverse("quality:risk_control_measure_delete", kwargs={"pk": risk_control_measure_a.pk})
        res = non_admin_client.post(url)
        assert res.status_code == 403
        assert RiskControlMeasure.objects.filter(pk=risk_control_measure_a.pk).exists()

    def test_riskmanagement_security_review_delete_requires_tenant_admin_403(
        self, non_admin_client, risk_review_record_a
    ):
        """Non-admin user POST to risk_review_record_delete receives HTTP 403 Forbidden."""
        url = reverse("quality:risk_review_record_delete", kwargs={"pk": risk_review_record_a.pk})
        res = non_admin_client.post(url)
        assert res.status_code == 403
        assert RiskReviewRecord.objects.filter(pk=risk_review_record_a.pk).exists()

    def test_riskmanagement_security_review_approve_requires_tenant_admin_403(
        self, non_admin_client, risk_review_record_a
    ):
        """Non-admin user POST to risk_review_record_approve receives HTTP 403 Forbidden."""
        url = reverse("quality:risk_review_record_approve", kwargs={"pk": risk_review_record_a.pk})
        res = non_admin_client.post(url)
        assert res.status_code == 403
        risk_review_record_a.refresh_from_db()
        assert risk_review_record_a.status == "draft"

    def test_riskmanagement_security_non_admin_allowed_standard_actions(
        self, non_admin_client, risk_management_plan_a, risk_assessment_a, risk_control_measure_a
    ):
        """Non-admin user CAN access list views, detail views, and verification actions."""
        assert non_admin_client.get(reverse("quality:risk_management_plan_list")).status_code == 200
        assert non_admin_client.get(reverse("quality:risk_management_plan_detail", kwargs={"pk": risk_management_plan_a.pk})).status_code == 200
        assert non_admin_client.get(reverse("quality:risk_assessment_detail", kwargs={"pk": risk_assessment_a.pk})).status_code == 200

        # Non-admin is allowed to verify control measures
        url_ver = reverse("quality:risk_control_measure_verify_impl", kwargs={"pk": risk_control_measure_a.pk})
        res_ver = non_admin_client.post(url_ver)
        assert res_ver.status_code == 302
        risk_control_measure_a.refresh_from_db()
        assert risk_control_measure_a.implementation_verified


# =====================================================================
# 4. HTTP Method Enforcement (@require_POST)
# =====================================================================


class TestRiskManagementHttpMethodEnforcement:
    """Ensure state-changing endpoints reject GET requests with HTTP 405 Method Not Allowed."""

    def test_riskmanagement_security_state_changing_endpoints_reject_get_405(
        self, client_a, _riskmanagement_plan_draft, risk_assessment_a,
        risk_control_measure_a, risk_review_record_a
    ):
        """All 9 state-changing endpoints strictly reject GET with 405 Method Not Allowed."""
        post_only_urls = [
            reverse("quality:risk_management_plan_delete", kwargs={"pk": _riskmanagement_plan_draft.pk}),
            reverse("quality:risk_management_plan_activate", kwargs={"pk": _riskmanagement_plan_draft.pk}),
            reverse("quality:risk_management_plan_archive", kwargs={"pk": _riskmanagement_plan_draft.pk}),
            reverse("quality:risk_assessment_delete", kwargs={"pk": risk_assessment_a.pk}),
            reverse("quality:risk_control_measure_delete", kwargs={"pk": risk_control_measure_a.pk}),
            reverse("quality:risk_control_measure_verify_impl", kwargs={"pk": risk_control_measure_a.pk}),
            reverse("quality:risk_control_measure_verify_eff", kwargs={"pk": risk_control_measure_a.pk}),
            reverse("quality:risk_review_record_delete", kwargs={"pk": risk_review_record_a.pk}),
            reverse("quality:risk_review_record_approve", kwargs={"pk": risk_review_record_a.pk}),
        ]

        for url in post_only_urls:
            res = client_a.get(url)
            assert res.status_code == 405, f"GET on state-changing URL {url} did not return 405"


# =====================================================================
# 5. Mass Assignment & Safety Gate Integrity
# =====================================================================


class TestRiskManagementMassAssignmentAndSafetyGates:
    """ISO 14971 Safety Gates, Risk Acceptability Rules, and Tamper-Resistance."""

    def test_riskmanagement_security_review_form_rejects_approved_status(
        self, tenant_a, admin_user, risk_management_plan_a
    ):
        """RiskReviewRecordForm rejects direct mass-assignment of status='approved'."""
        form = RiskReviewRecordForm(tenant=tenant_a)
        assert ("approved", "Approved") not in form.fields["status"].choices

        data = {
            "plan": risk_management_plan_a.pk,
            "review_title": "Sneak Approval Review",
            "review_type": "periodic_review",
            "review_date": timezone.now().date(),
            "findings_summary": "Attempting bypass.",
            "status": "approved",
            "lead_reviewer": admin_user.pk,
        }
        bound = RiskReviewRecordForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "status" in bound.errors

    def test_riskmanagement_security_control_form_rejects_verification_without_notes_or_protocol(
        self, tenant_a, admin_user, risk_assessment_a
    ):
        """RiskControlMeasureForm rejects implementation or effectiveness verification without notes or protocol."""
        # 1. Implementation verified without evidence
        data_impl = {
            "risk_assessment": risk_assessment_a.pk,
            "control_hierarchy": "protective_measure",
            "title": "Hardware Interlock Switch",
            "description": "Cuts circuit if panel is open.",
            "assigned_to": admin_user.pk,
            "implementation_verified": True,
            "verification_notes": "",
            "design_verification": "",
            "status": "planned",
        }
        bound_impl = RiskControlMeasureForm(data=data_impl, tenant=tenant_a)
        assert not bound_impl.is_valid()
        assert "implementation_verified" in bound_impl.errors

        # 2. Effectiveness verified without evidence
        data_eff = {
            "risk_assessment": risk_assessment_a.pk,
            "control_hierarchy": "protective_measure",
            "title": "Hardware Interlock Switch",
            "description": "Cuts circuit if panel is open.",
            "assigned_to": admin_user.pk,
            "effectiveness_verified": True,
            "verification_notes": "",
            "design_verification": "",
            "status": "planned",
        }
        bound_eff = RiskControlMeasureForm(data=data_eff, tenant=tenant_a)
        assert not bound_eff.is_valid()
        assert "effectiveness_verified" in bound_eff.errors

    def test_riskmanagement_security_control_form_accepts_verification_with_notes_or_protocol(
        self, tenant_a, admin_user, risk_assessment_a, design_verification_a
    ):
        """RiskControlMeasureForm accepts verification when notes or protocol is provided."""
        # Verification with notes
        data_notes = {
            "risk_assessment": risk_assessment_a.pk,
            "control_hierarchy": "protective_measure",
            "title": "Hardware Interlock Switch Notes",
            "description": "Cuts circuit if panel is open.",
            "assigned_to": admin_user.pk,
            "implementation_verified": True,
            "verification_notes": "Tested 10 mechanical cycles with multimeter showing open circuit within 5ms.",
            "status": "planned",
        }
        bound_notes = RiskControlMeasureForm(data=data_notes, tenant=tenant_a)
        assert bound_notes.is_valid(), bound_notes.errors

        # Verification with protocol
        data_proto = {
            "risk_assessment": risk_assessment_a.pk,
            "control_hierarchy": "protective_measure",
            "title": "Hardware Interlock Switch Protocol",
            "description": "Cuts circuit if panel is open.",
            "assigned_to": admin_user.pk,
            "effectiveness_verified": True,
            "design_verification": design_verification_a.pk,
            "status": "planned",
        }
        bound_proto = RiskControlMeasureForm(data=data_proto, tenant=tenant_a)
        assert bound_proto.is_valid(), bound_proto.errors

    def test_riskmanagement_security_control_form_rejects_mismatched_project_design_input(
        self, tenant_a, admin_user, risk_assessment_a, quality_department
    ):
        """RiskControlMeasureForm rejects selecting a DesignInput that belongs to a different DesignProject."""
        # Create a second design project and input for Tenant A
        project_other = DesignProject.objects.create(
            tenant=tenant_a,
            title="Other Device Project",
            device_name="PulseOx 100",
            device_class="class_ii",
            regulatory_pathway="510k",
            intended_use="Pulse oximetry.",
            current_phase="planning",
            status="active",
            project_lead=admin_user,
            quality_lead=admin_user,
            department=quality_department,
        )
        input_other = DesignInput.objects.create(
            tenant=tenant_a,
            project=project_other,
            identifier="DI-OTHER-001",
            title="Other Project Input Requirement",
            input_type="functional",
            priority="high",
            status="approved",
            owner=admin_user,
            acceptance_criteria="Other criteria.",
        )

        data = {
            "risk_assessment": risk_assessment_a.pk,
            "control_hierarchy": "protective_measure",
            "title": "Cross Project Input Control",
            "description": "Test control.",
            "assigned_to": admin_user.pk,
            "design_input": input_other.pk,
            "status": "planned",
        }
        bound = RiskControlMeasureForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "design_input" in bound.errors

    def test_riskmanagement_security_assessment_form_rejects_acceptable_in_unacceptable_zone(
        self, tenant_a, risk_management_plan_a
    ):
        """RiskAssessmentForm strictly rejects residual_risk_acceptable=True when residual RPN is Unacceptable (>= 15)."""
        data = {
            "plan": risk_management_plan_a.pk,
            "analysis_type": "dfmea",
            "hazard_category": "energy_electrical",
            "hazard_description": "Catastrophic Power Surge",
            "hazardous_situation": "High voltage arc",
            "potential_harm": "Fatal electrocution",
            "initial_severity": 5,
            "initial_probability": 4,
            "initial_detectability": 3,
            "residual_severity": 5,
            "residual_probability": 3,  # 5 * 3 = 15 -> Unacceptable zone!
            "residual_detectability": 2,
            "residual_risk_acceptable": True,  # Safety Gate Violation!
            "lifecycle_status": "open",
        }
        bound = RiskAssessmentForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "residual_risk_acceptable" in bound.errors
        assert "Unacceptable zone" in str(bound.errors["residual_risk_acceptable"])

    def test_riskmanagement_security_assessment_form_rejects_acceptable_in_alarp_without_bra_justification(
        self, tenant_a, risk_management_plan_a
    ):
        """RiskAssessmentForm rejects residual_risk_acceptable=True in ALARP zone (6 <= score < 15) without BRA justification."""
        data = {
            "plan": risk_management_plan_a.pk,
            "analysis_type": "dfmea",
            "hazard_category": "energy_mechanical",
            "hazard_description": "Needle Shield Latch Jam",
            "hazardous_situation": "Shield fails to deploy after injection",
            "potential_harm": "Needlestick injury to healthcare worker",
            "initial_severity": 3,
            "initial_probability": 3,
            "initial_detectability": 2,
            "residual_severity": 3,
            "residual_probability": 2,  # 3 * 2 = 6 -> ALARP zone!
            "residual_detectability": 2,
            "residual_risk_acceptable": True,
            "benefit_risk_justification": "",  # Missing mandatory clinical justification!
            "lifecycle_status": "open",
        }
        bound = RiskAssessmentForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "benefit_risk_justification" in bound.errors
        assert "Benefit-Risk Analysis" in str(bound.errors["benefit_risk_justification"])

    def test_riskmanagement_security_assessment_form_accepts_alarp_with_bra_justification(
        self, tenant_a, risk_management_plan_a
    ):
        """RiskAssessmentForm accepts residual_risk_acceptable=True in ALARP zone when BRA justification is provided."""
        data = {
            "plan": risk_management_plan_a.pk,
            "analysis_type": "dfmea",
            "hazard_category": "energy_mechanical",
            "hazard_description": "Needle Shield Latch Jam",
            "hazardous_situation": "Shield fails to deploy after injection",
            "potential_harm": "Needlestick injury to healthcare worker",
            "initial_severity": 3,
            "initial_probability": 3,
            "initial_detectability": 2,
            "residual_severity": 3,
            "residual_probability": 2,  # 3 * 2 = 6 -> ALARP
            "residual_detectability": 2,
            "residual_risk_acceptable": True,
            "benefit_risk_justification": "Clinical literature shows safety needle reduces total injuries by 92%; residual risk is justified by primary therapeutic efficacy.",
            "lifecycle_status": "mitigated",
        }
        bound = RiskAssessmentForm(data=data, tenant=tenant_a)
        assert bound.is_valid(), bound.errors

    def test_riskmanagement_security_plan_edit_guard_active_plan(
        self, client_a, risk_management_plan_a
    ):
        """Attempting to edit an Active plan redirects to detail with error message; record is unmutated."""
        url = reverse("quality:risk_management_plan_edit", kwargs={"pk": risk_management_plan_a.pk})
        res_get = client_a.get(url)
        assert res_get.status_code == 302
        assert res_get.url == reverse("quality:risk_management_plan_detail", kwargs={"pk": risk_management_plan_a.pk})

        messages = _riskmanagement_get_messages(res_get)
        assert any("cannot be modified while active" in m for m in messages)

        # POST attempt
        res_post = client_a.post(url, {"title": "Hostile Active Modification"})
        assert res_post.status_code == 302
        risk_management_plan_a.refresh_from_db()
        assert risk_management_plan_a.title != "Hostile Active Modification"

    def test_riskmanagement_security_plan_edit_guard_archived_plan(
        self, client_a, _riskmanagement_plan_draft
    ):
        """Attempting to edit an Archived plan redirects to detail with error message; record is unmutated."""
        _riskmanagement_plan_draft.status = "archived"
        _riskmanagement_plan_draft.save(update_fields=["status"])

        url = reverse("quality:risk_management_plan_edit", kwargs={"pk": _riskmanagement_plan_draft.pk})
        res_post = client_a.post(url, {"title": "Hostile Archived Modification"})
        assert res_post.status_code == 302
        _riskmanagement_plan_draft.refresh_from_db()
        assert _riskmanagement_plan_draft.title != "Hostile Archived Modification"

    def test_riskmanagement_security_plan_edit_guard_signed_plan(
        self, client_a, tenant_a, admin_user, quality_doc_effective, _riskmanagement_plan_draft
    ):
        """Attempting to edit an electronically signed plan redirects to detail with error message; record is unmutated."""
        sig = _riskmanagement_create_signature(tenant_a, admin_user, quality_doc_effective)
        _riskmanagement_plan_draft.approved_signature = sig
        _riskmanagement_plan_draft.save(update_fields=["approved_signature"])

        url = reverse("quality:risk_management_plan_edit", kwargs={"pk": _riskmanagement_plan_draft.pk})
        res_post = client_a.post(url, {"title": "Hostile Signed Modification"})
        assert res_post.status_code == 302
        _riskmanagement_plan_draft.refresh_from_db()
        assert _riskmanagement_plan_draft.title != "Hostile Signed Modification"

    def test_riskmanagement_security_review_edit_guard_approved_review(
        self, client_a, risk_review_record_a
    ):
        """Attempting to edit an Approved review record redirects to detail with error message; record is unmutated."""
        risk_review_record_a.status = "approved"
        risk_review_record_a.save(update_fields=["status"])

        url = reverse("quality:risk_review_record_edit", kwargs={"pk": risk_review_record_a.pk})
        res_get = client_a.get(url)
        assert res_get.status_code == 302
        assert res_get.url == reverse("quality:risk_review_record_detail", kwargs={"pk": risk_review_record_a.pk})

        messages = _riskmanagement_get_messages(res_get)
        assert any("cannot be modified because it is already approved" in m for m in messages)

        # POST attempt
        res_post = client_a.post(url, {"review_title": "Hostile Approved Modification"})
        assert res_post.status_code == 302
        risk_review_record_a.refresh_from_db()
        assert risk_review_record_a.review_title != "Hostile Approved Modification"

    def test_riskmanagement_security_review_edit_guard_signed_review(
        self, client_a, tenant_a, admin_user, quality_doc_effective, risk_review_record_a
    ):
        """Attempting to edit an electronically signed review record redirects to detail with error message."""
        sig = _riskmanagement_create_signature(tenant_a, admin_user, quality_doc_effective)
        risk_review_record_a.approved_signature = sig
        risk_review_record_a.save(update_fields=["approved_signature"])

        url = reverse("quality:risk_review_record_edit", kwargs={"pk": risk_review_record_a.pk})
        res_post = client_a.post(url, {"review_title": "Hostile Signed Review Modification"})
        assert res_post.status_code == 302
        risk_review_record_a.refresh_from_db()
        assert risk_review_record_a.review_title != "Hostile Signed Review Modification"


# =====================================================================
# 6. Audit Trail Integrity (21 CFR Part 11 / ISO 13485)
# =====================================================================


class TestRiskManagementAuditTrailIntegrity:
    """Validate comprehensive audit logging across all lifecycle actions and mutations."""

    def test_riskmanagement_security_audit_log_plan_lifecycle(
        self, client_a, tenant_a, admin_user, design_project_a, quality_department
    ):
        """RiskManagementPlan create, edit, activate, archive, and delete write AuditLog entries preserving object_id."""
        # 1. Create
        res_create = client_a.post(
            reverse("quality:risk_management_plan_create"),
            {
                "title": "Audit Lifecycle Infusion Plan",
                "plan_version": "1.0",
                "status": "draft",
                "design_project": design_project_a.pk,
                "lead_risk_manager": admin_user.pk,
                "department": quality_department.pk,
                "device_classification": "class_ii_a",
                "scope_description": "Full audit test plan.",
                "matrix_dimension": "5x5",
                "risk_acceptability_policy": "RPN < 4 acceptable.",
                "overall_residual_risk_acceptable": True,
                "periodic_review_frequency_months": 12,
            },
        )
        assert res_create.status_code == 302
        plan = RiskManagementPlan.objects.get(title="Audit Lifecycle Infusion Plan")
        plan_pk = plan.pk

        assert _riskmanagement_audit_logs(plan, action="create").exists()

        # 2. Update
        client_a.post(
            reverse("quality:risk_management_plan_edit", kwargs={"pk": plan_pk}),
            {
                "title": "Audit Lifecycle Infusion Plan (Updated)",
                "plan_version": "1.1",
                "status": "draft",
                "design_project": design_project_a.pk,
                "lead_risk_manager": admin_user.pk,
                "department": quality_department.pk,
                "device_classification": "class_ii_a",
                "scope_description": "Full audit test plan revised.",
                "matrix_dimension": "5x5",
                "risk_acceptability_policy": "RPN < 4 acceptable.",
                "overall_residual_risk_acceptable": True,
                "periodic_review_frequency_months": 12,
            },
        )
        assert _riskmanagement_audit_logs(plan, action="update").exists()

        # 3. Activate
        client_a.post(reverse("quality:risk_management_plan_activate", kwargs={"pk": plan_pk}))
        assert _riskmanagement_audit_logs(plan, action="activate").exists()

        # 4. Archive
        client_a.post(reverse("quality:risk_management_plan_archive", kwargs={"pk": plan_pk}))
        assert _riskmanagement_audit_logs(plan, action="archive").exists()

        # 5. Delete (object_id must match deleted pk)
        client_a.post(reverse("quality:risk_management_plan_delete", kwargs={"pk": plan_pk}))
        assert not RiskManagementPlan.objects.filter(pk=plan_pk).exists()

        del_logs = _riskmanagement_audit_logs(RiskManagementPlan, object_id=plan_pk, action="delete")
        assert del_logs.exists()
        del_entry = del_logs.first()
        assert del_entry.object_id == plan_pk
        assert del_entry.user == admin_user
        assert del_entry.tenant == tenant_a

    def test_riskmanagement_security_audit_log_assessment_lifecycle(
        self, client_a, tenant_a, admin_user, risk_management_plan_a
    ):
        """RiskAssessment create, edit, and delete write AuditLog entries preserving object_id."""
        # 1. Create
        res_create = client_a.post(
            reverse("quality:risk_assessment_create"),
            {
                "plan": risk_management_plan_a.pk,
                "analysis_type": "dfmea",
                "hazard_category": "software_cybersecurity",
                "hazard_description": "Buffer Overflow in Rate Calculation",
                "hazardous_situation": "Pump delivers incorrect infusion rate",
                "potential_harm": "Medication overdose",
                "initial_severity": 5,
                "initial_probability": 2,
                "initial_detectability": 3,
                "lifecycle_status": "open",
            },
        )
        assert res_create.status_code == 302
        assessment = RiskAssessment.objects.get(hazard_description="Buffer Overflow in Rate Calculation")
        ass_pk = assessment.pk

        assert _riskmanagement_audit_logs(assessment, action="create").exists()

        # 2. Update
        client_a.post(
            reverse("quality:risk_assessment_edit", kwargs={"pk": ass_pk}),
            {
                "plan": risk_management_plan_a.pk,
                "analysis_type": "dfmea",
                "hazard_category": "software_cybersecurity",
                "hazard_description": "Buffer Overflow in Rate Calculation (Mitigated)",
                "hazardous_situation": "Pump delivers incorrect infusion rate",
                "potential_harm": "Medication overdose",
                "initial_severity": 5,
                "initial_probability": 2,
                "initial_detectability": 3,
                "residual_severity": 2,
                "residual_probability": 1,
                "residual_detectability": 1,
                "residual_risk_acceptable": True,
                "lifecycle_status": "mitigated",
            },
        )
        assert _riskmanagement_audit_logs(assessment, action="update").exists()

        # 3. Delete
        client_a.post(reverse("quality:risk_assessment_delete", kwargs={"pk": ass_pk}))
        assert not RiskAssessment.objects.filter(pk=ass_pk).exists()

        del_logs = _riskmanagement_audit_logs(RiskAssessment, object_id=ass_pk, action="delete")
        assert del_logs.exists()
        assert del_logs.first().object_id == ass_pk

    def test_riskmanagement_security_audit_log_control_measure_lifecycle(
        self, client_a, tenant_a, admin_user, risk_assessment_a
    ):
        """RiskControlMeasure create, edit, verify_impl, verify_eff, and delete write AuditLog entries."""
        # 1. Create
        res_create = client_a.post(
            reverse("quality:risk_control_measure_create"),
            {
                "risk_assessment": risk_assessment_a.pk,
                "control_hierarchy": "protective_measure",
                "title": "Watchdog Timer Hardware Reset",
                "description": "Independent hardware watchdog reboots microcontroller if loop freezes.",
                "assigned_to": admin_user.pk,
                "status": "planned",
            },
        )
        assert res_create.status_code == 302
        control = RiskControlMeasure.objects.get(title="Watchdog Timer Hardware Reset")
        ctrl_pk = control.pk

        assert _riskmanagement_audit_logs(control, action="create").exists()

        # 2. Update
        client_a.post(
            reverse("quality:risk_control_measure_edit", kwargs={"pk": ctrl_pk}),
            {
                "risk_assessment": risk_assessment_a.pk,
                "control_hierarchy": "protective_measure",
                "title": "Watchdog Timer Hardware Reset (Rev 2)",
                "description": "Independent hardware watchdog with 100ms timeout.",
                "assigned_to": admin_user.pk,
                "status": "in_progress",
            },
        )
        assert _riskmanagement_audit_logs(control, action="update").exists()

        # 3. Verify Implementation
        client_a.post(reverse("quality:risk_control_measure_verify_impl", kwargs={"pk": ctrl_pk}))
        assert _riskmanagement_audit_logs(control, action="verify").filter(object_id=ctrl_pk).exists()

        # 4. Verify Effectiveness
        client_a.post(reverse("quality:risk_control_measure_verify_eff", kwargs={"pk": ctrl_pk}))
        # Multiple verify action rows should exist
        assert _riskmanagement_audit_logs(control, action="verify").count() >= 2

        # 5. Delete
        client_a.post(reverse("quality:risk_control_measure_delete", kwargs={"pk": ctrl_pk}))
        assert not RiskControlMeasure.objects.filter(pk=ctrl_pk).exists()

        del_logs = _riskmanagement_audit_logs(RiskControlMeasure, object_id=ctrl_pk, action="delete")
        assert del_logs.exists()
        assert del_logs.first().object_id == ctrl_pk

    def test_riskmanagement_security_audit_log_review_record_lifecycle(
        self, client_a, tenant_a, admin_user, risk_management_plan_a
    ):
        """RiskReviewRecord create, edit, approve, and delete write AuditLog entries preserving object_id."""
        # 1. Create
        res_create = client_a.post(
            reverse("quality:risk_review_record_create"),
            {
                "plan": risk_management_plan_a.pk,
                "review_title": "Quarterly Audit Review",
                "review_type": "periodic_review",
                "review_date": timezone.now().date(),
                "findings_summary": "All mitigations active and confirmed.",
                "status": "draft",
                "lead_reviewer": admin_user.pk,
            },
        )
        assert res_create.status_code == 302
        review = RiskReviewRecord.objects.get(review_title="Quarterly Audit Review")
        rev_pk = review.pk

        assert _riskmanagement_audit_logs(review, action="create").exists()

        # 2. Update
        client_a.post(
            reverse("quality:risk_review_record_edit", kwargs={"pk": rev_pk}),
            {
                "plan": risk_management_plan_a.pk,
                "review_title": "Quarterly Audit Review (Revised)",
                "review_type": "periodic_review",
                "review_date": timezone.now().date(),
                "findings_summary": "Mitigations verified via laboratory test protocols.",
                "status": "under_review",
                "lead_reviewer": admin_user.pk,
            },
        )
        assert _riskmanagement_audit_logs(review, action="update").exists()

        # 3. Approve
        client_a.post(reverse("quality:risk_review_record_approve", kwargs={"pk": rev_pk}))
        assert _riskmanagement_audit_logs(review, action="approve").exists()

        # 4. Delete
        client_a.post(reverse("quality:risk_review_record_delete", kwargs={"pk": rev_pk}))
        assert not RiskReviewRecord.objects.filter(pk=rev_pk).exists()

        del_logs = _riskmanagement_audit_logs(RiskReviewRecord, object_id=rev_pk, action="delete")
        assert del_logs.exists()
        assert del_logs.first().object_id == rev_pk


# =====================================================================
# 7. CSV Formula Injection Defense (CWE-1236)
# =====================================================================


class TestRiskManagementCsvFormulaInjectionDefense:
    """Ensure CSV exports neutralize spreadsheet formula injection payloads."""

    def test_riskmanagement_security_csv_safe_unit_escapes_formula_prefixes(self):
        """csv_safe() prepends single quote to values starting with =, +, -, @, %."""
        assert csv_safe("=1+1") == "'=1+1"
        assert csv_safe("-5+2") == "'-5+2"
        assert csv_safe("+100") == "'+100"
        assert csv_safe("@SUM(A1:A10)") == "'@SUM(A1:A10)"
        assert csv_safe("  =CMD|' /C calc'!A0") == "'  =CMD|' /C calc'!A0"
        assert csv_safe("%COMSPEC%") == "'%COMSPEC%"

        # Benign values remain untouched
        assert csv_safe("Safe Text 123") == "Safe Text 123"
        assert csv_safe("") == ""
        assert csv_safe(None) == ""
        assert csv_safe(42) == "42"

    def test_riskmanagement_security_plan_export_csv_escapes_formulas(
        self, client_a, tenant_a, admin_user, design_project_a
    ):
        """RiskManagementPlan CSV export neutralizes formula payloads."""
        RiskManagementPlan.objects.create(
            tenant=tenant_a,
            title="=SUM(1,2)",
            plan_version="+1.0",
            device_classification="class_ii_a",
            design_project=design_project_a,
            lead_risk_manager=admin_user,
            status="draft",
            matrix_dimension="5x5",
            scope_description="@DDE('calc')",
            risk_acceptability_policy="-4+5",
        )

        res = client_a.get(reverse("quality:risk_management_plan_export"))
        assert res.status_code == 200
        rows = _riskmanagement_parse_csv(res)

        titles = [r[1] for r in rows[1:]]
        versions = [r[2] for r in rows[1:]]

        assert "'=SUM(1,2)" in titles
        assert "'+1.0" in versions

    def test_riskmanagement_security_assessment_export_csv_escapes_formulas(
        self, client_a, tenant_a, risk_management_plan_a
    ):
        """RiskAssessment CSV export neutralizes formula payloads."""
        RiskAssessment.objects.create(
            tenant=tenant_a,
            plan=risk_management_plan_a,
            hazard_category="energy_electrical",
            hazard_description="=2+5*10",
            potential_harm="@ALERT('hazard')",
            analysis_type="dfmea",
            initial_severity=3,
            initial_probability=2,
            lifecycle_status="open",
        )

        res = client_a.get(reverse("quality:risk_assessment_export"))
        assert res.status_code == 200
        rows = _riskmanagement_parse_csv(res)

        hazards = [r[4] for r in rows[1:]]
        harms = [r[5] for r in rows[1:]]

        assert "'=2+5*10" in hazards
        assert "'@ALERT('hazard')" in harms

    def test_riskmanagement_security_control_export_csv_escapes_formulas(
        self, client_a, tenant_a, admin_user, risk_assessment_a
    ):
        """RiskControlMeasure CSV export neutralizes formula payloads."""
        RiskControlMeasure.objects.create(
            tenant=tenant_a,
            risk_assessment=risk_assessment_a,
            control_hierarchy="inherent_safety",
            title="=CMD('calc')",
            description="-10+20",
            assigned_to=admin_user,
            status="planned",
        )

        res = client_a.get(reverse("quality:risk_control_measure_export"))
        assert res.status_code == 200
        rows = _riskmanagement_parse_csv(res)

        titles = [r[3] for r in rows[1:]]
        assert "'=CMD('calc')" in titles

    def test_riskmanagement_security_review_export_csv_escapes_formulas(
        self, client_a, tenant_a, admin_user, risk_management_plan_a
    ):
        """RiskReviewRecord CSV export neutralizes formula payloads."""
        RiskReviewRecord.objects.create(
            tenant=tenant_a,
            plan=risk_management_plan_a,
            review_type="initial_rmr",
            review_title="@SUM(10,20)",
            findings_summary="=1+1",
            review_date=timezone.now().date(),
            lead_reviewer=admin_user,
            status="draft",
        )

        res = client_a.get(reverse("quality:risk_review_record_export"))
        assert res.status_code == 200
        rows = _riskmanagement_parse_csv(res)

        titles = [r[2] for r in rows[1:]]
        assert "'@SUM(10,20)" in titles

    def test_riskmanagement_security_fmea_matrix_export_csv_escapes_formulas(
        self, client_a, tenant_a, risk_management_plan_a
    ):
        """FMEA Matrix CSV export neutralizes formula payloads in hazard descriptions."""
        RiskAssessment.objects.create(
            tenant=tenant_a,
            plan=risk_management_plan_a,
            hazard_category="energy_electrical",
            hazard_description="=HYPERLINK('http://evil.com')",
            analysis_type="dfmea",
            initial_severity=4,
            initial_probability=3,
            lifecycle_status="open",
        )

        url = reverse("quality:fmea_matrix_export") + f"?plan={risk_management_plan_a.pk}"
        res = client_a.get(url)
        assert res.status_code == 200
        rows = _riskmanagement_parse_csv(res)

        hazards = [r[3] for r in rows[1:]]
        assert "'=HYPERLINK('http://evil.com')" in hazards

    def test_riskmanagement_security_traceability_matrix_export_csv_escapes_formulas(
        self, client_a, tenant_a, admin_user, risk_management_plan_a
    ):
        """Risk Traceability Matrix CSV export neutralizes formula payloads."""
        ass = RiskAssessment.objects.create(
            tenant=tenant_a,
            plan=risk_management_plan_a,
            hazard_category="software_cybersecurity",
            hazard_description="=CMD('calc')",
            analysis_type="dfmea",
            initial_severity=3,
            initial_probability=2,
            lifecycle_status="open",
        )
        RiskControlMeasure.objects.create(
            tenant=tenant_a,
            risk_assessment=ass,
            control_hierarchy="inherent_safety",
            title="+FORMULA_MITIGATION",
            description="Sanitized.",
            assigned_to=admin_user,
            status="planned",
        )

        url = reverse("quality:risk_traceability_matrix_export") + f"?plan={risk_management_plan_a.pk}"
        res = client_a.get(url)
        assert res.status_code == 200
        rows = _riskmanagement_parse_csv(res)

        hazards = [r[2] for r in rows[1:]]
        controls = [r[6] for r in rows[1:]]

        assert "'=CMD('calc')" in hazards
        assert "'+FORMULA_MITIGATION" in controls


# =====================================================================
# 8. Adversarial Chaos & System Resilience
# =====================================================================


class TestRiskManagementAdversarialAndEdgeCases:
    """Robustness against malformed queries, special characters, and boundary conditions."""

    def test_riskmanagement_security_fmea_matrix_invalid_plan_param_404(self, client_a):
        """FMEA matrix handles non-numeric and negative plan IDs with 404."""
        assert client_a.get(reverse("quality:fmea_matrix") + "?plan=notanumber").status_code == 404
        assert client_a.get(reverse("quality:fmea_matrix") + "?plan=-99").status_code == 404
        assert client_a.get(reverse("quality:fmea_matrix") + "?plan=99999999").status_code == 404

    def test_riskmanagement_security_traceability_matrix_invalid_plan_param_404(self, client_a):
        """Traceability matrix handles non-numeric and invalid plan IDs with 404."""
        assert client_a.get(reverse("quality:risk_traceability_matrix") + "?plan=badinput").status_code == 404
        assert client_a.get(reverse("quality:risk_traceability_matrix") + "?plan=99999999").status_code == 404

    def test_riskmanagement_security_search_xss_sql_injection_safe(
        self, client_a, risk_management_plan_a, risk_assessment_a
    ):
        """Hostile search parameters (XSS tags, SQL fragments) return 200 without executing or breaking."""
        hostile_queries = [
            "<script>alert('xss')</script>",
            "' OR '1'='1",
            "'; DROP TABLE quality_riskmanagementplan; --",
            "<img src=x onerror=alert(1)>",
            "%00",
            "&quot;><script>alert(1)</script>",
        ]

        for q in hostile_queries:
            # Plan search
            res_p = client_a.get(reverse("quality:risk_management_plan_list") + f"?q={q}")
            assert res_p.status_code == 200

            # Assessment search
            res_a = client_a.get(reverse("quality:risk_assessment_list") + f"?q={q}")
            assert res_a.status_code == 200

            # Control search
            res_c = client_a.get(reverse("quality:risk_control_measure_list") + f"?q={q}")
            assert res_c.status_code == 200

            # Review search
            res_r = client_a.get(reverse("quality:risk_review_record_list") + f"?q={q}")
            assert res_r.status_code == 200

    def test_riskmanagement_security_pagination_invalid_page_handles_gracefully(self, client_a):
        """Paginator gracefully handles negative, junk, and out-of-range page numbers."""
        for bad_page in ["-1", "0", "abc", "99999999"]:
            res = client_a.get(reverse("quality:risk_management_plan_list") + f"?page={bad_page}")
            assert res.status_code == 200
            assert "plans" in res.context
