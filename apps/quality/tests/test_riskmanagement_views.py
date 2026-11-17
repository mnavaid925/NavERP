"""
Unit and integration tests for apps/quality views (Sub-module 12.3: Risk Management - ISO 14971 / FMEA).

Covers all 5 view sets, routes, query filters, context keys, status transitions, permissions, and CSV exports:
1. RiskManagementPlans views:
   - list (filters, search ?q=, pagination, status & device_class counts, context keys)
   - detail (context keys: plan, assessments, reviews, stats; aggregate stats assertion)
   - create (GET, POST valid -> redirect to detail with audit log, POST invalid -> 200 with form errors)
   - edit (GET on draft, POST valid update, guard against modifying active or electronically signed plans)
   - activate (POST 302 -> status="active" + audit log, require_POST 405 rejection on GET, tenant_admin_required 403)
   - archive (POST 302 -> status="archived" + audit log, require_POST 405 rejection, tenant_admin_required 403)
   - delete (POST 302 -> plan deleted + audit log preserving object_id, require_POST 405, tenant_admin_required 403)
   - export (CSV output, text/csv, nosniff, column headers, csv_safe formula sanitization)
2. RiskAssessments views:
   - list (filters by hazard_category, analysis_type, risk_level, lifecycle_status, plan; search, pagination, context keys)
   - detail (context keys: assessment, control_measures)
   - create (GET with ?plan= prefill, POST valid -> pre/post mitigation score calculation + audit log, POST invalid)
   - edit (GET, POST valid update + recalculation of scores + audit log)
   - delete (POST 302 -> assessment deleted + audit log preserving object_id, redirect to plan detail, require_POST 405, 403)
   - export (CSV output, text/csv, nosniff, column headers)
3. RiskControlMeasures views:
   - list (filters by control_hierarchy, status, plan; search, pagination, context keys)
   - detail (context key: control_measure)
   - create (GET with ?assessment= prefill, POST valid -> redirect to detail + audit log, POST invalid)
   - edit (GET, POST valid update + audit log)
   - verify_impl (POST 302 -> sets implementation_verified=True, status="implemented" or "verified" + audit log, GET 405)
   - verify_eff (POST 302 -> sets effectiveness_verified=True, status="verified" if implementation_verified + audit log, GET 405)
   - delete (POST 302 -> measure deleted + audit log, redirect to assessment detail, require_POST 405, 403)
   - export (CSV output, text/csv, nosniff, column headers)
4. RiskReviewRecords views:
   - list (filters by review_type, status, plan; search, pagination, context keys)
   - detail (context key: review_record)
   - create (GET with ?plan= prefill, POST valid -> redirect to detail + audit log, POST invalid)
   - edit (GET on draft, POST valid update + audit log, guard against editing approved or signed reviews)
   - approve (POST 302 -> sets status="approved" + audit log, require_POST 405, tenant_admin_required 403)
   - delete (POST 302 -> review deleted + audit log, redirect to plan detail, require_POST 405, 403)
   - export (CSV output, text/csv, nosniff, column headers)
5. FmeaMatrix & RiskTraceabilityMatrix views:
   - fmea_matrix (GET 200, 5x5 matrix cells, severity/probability ranges, high_risk_items, rpn_pareto_items, stats, plan selector)
   - fmea_matrix invalid or cross-tenant plan validation (404)
   - fmea_matrix_export (CSV export, defaults to first plan, validates plan against tenant)
   - risk_traceability_matrix (GET 200, traceability rows from hazard to control to verification, stats: coverage pct)
   - risk_traceability_matrix invalid or cross-tenant plan validation (404)
   - risk_traceability_matrix_export (CSV export, handles hazards with and without controls, validates plan against tenant)
6. Cross-Tenant Isolation & Authentication Guards:
   - detail, edit, delete, export 404 on cross-tenant access.
   - unauthenticated redirects to login.
"""

import csv
import io
import pytest
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import AuditLog, OrgUnit
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

pytestmark = pytest.mark.django_db


# =====================================================================
# Fixtures and Helpers (Prefix: _riskmanagement_*)
# =====================================================================


def _riskmanagement_get_messages(response):
    """Extract message strings from response wsgi_request."""
    if hasattr(response, "wsgi_request"):
        return [m.message for m in get_messages(response.wsgi_request)]
    return []


def _riskmanagement_assert_no_comment_leaks(response):
    """Assert response HTML contains no template comment fragments."""
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "{#" not in content, "Found unrendered '{#' comment leak in HTML template"
    assert "{% comment" not in content, "Found unrendered '{% comment' leak in HTML template"


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


@pytest.fixture
def _riskmanagement_plan_draft(db, tenant_a, admin_user, design_project_a, quality_department):
    """Draft RiskManagementPlan fixture suitable for edit and activate tests."""
    return RiskManagementPlan.objects.create(
        tenant=tenant_a,
        title="Draft Risk Management Plan for Infusion Pump",
        plan_version="1.0",
        device_classification="class_ii_a",
        design_project=design_project_a,
        lead_risk_manager=admin_user,
        department=quality_department,
        status="draft",
        matrix_dimension="5x5",
        scope_description="Initial draft plan awaiting approval.",
        risk_acceptability_policy="Broadly acceptable when RPN < 6.",
        overall_residual_risk_acceptable=False,
    )


@pytest.fixture
def _riskmanagement_review_approved(db, tenant_a, admin_user, risk_management_plan_a):
    """Approved RiskReviewRecord fixture for testing edit guard."""
    return RiskReviewRecord.objects.create(
        tenant=tenant_a,
        plan=risk_management_plan_a,
        review_type="initial_rmr",
        review_title="Approved Initial Risk Management Review",
        findings_summary="All initial hazards evaluated and deemed acceptable.",
        review_date=timezone.now().date(),
        lead_reviewer=admin_user,
        status="approved",
    )


@pytest.fixture
def _riskmanagement_signed_plan(db, tenant_a, admin_user, quality_doc_effective, design_project_a):
    """Signed RiskManagementPlan fixture for testing edit guard."""
    sig = ElectronicSignatureRecord(
        tenant=tenant_a,
        document=quality_doc_effective,
        signer=admin_user,
        signer_name="Admin Acme",
        signer_title="QA Director",
        signature_meaning="quality_approval",
        document_revision="1.0",
        ip_address="127.0.0.1",
        comments="Approved for release.",
    )
    sig.verification_hash = sig.generate_hash()
    sig.save()

    return RiskManagementPlan.objects.create(
        tenant=tenant_a,
        title="Signed Risk Management Plan",
        plan_version="2.0",
        device_classification="class_ii_a",
        design_project=design_project_a,
        lead_risk_manager=admin_user,
        status="draft",
        matrix_dimension="5x5",
        scope_description="Electronically signed plan.",
        risk_acceptability_policy="Broadly acceptable when RPN < 6.",
        approved_signature=sig,
    )


# =====================================================================
# 1. RiskManagementPlans Views
# =====================================================================


class TestRiskManagementPlanViews:
    def test_riskmanagement_plan_list_get_success(self, client_a, risk_management_plan_a):
        url = reverse("quality:risk_management_plan_list")
        res = client_a.get(url)
        assert res.status_code == 200
        _riskmanagement_assert_no_comment_leaks(res)

        # Context keys
        assert "plans" in res.context
        assert "page_obj" in res.context
        assert "total_count" in res.context
        assert "active_count" in res.context
        assert "overdue_count" in res.context
        assert "archived_count" in res.context
        assert "status_choices" in res.context
        assert "device_class_choices" in res.context
        assert "selected_status" in res.context
        assert "selected_class" in res.context
        assert "q" in res.context

        assert res.context["total_count"] >= 1
        assert res.context["active_count"] >= 1

        # Rendered content
        content = res.content.decode("utf-8")
        assert risk_management_plan_a.number in content
        assert risk_management_plan_a.title in content

    def test_riskmanagement_plan_list_filter_status_and_device_class(
        self, client_a, risk_management_plan_a, _riskmanagement_plan_draft
    ):
        url = reverse("quality:risk_management_plan_list")

        # Filter by status: active
        res_active = client_a.get(f"{url}?status=active")
        assert res_active.status_code == 200
        plans_active = list(res_active.context["plans"])
        assert risk_management_plan_a in plans_active
        assert _riskmanagement_plan_draft not in plans_active

        # Filter by status: draft
        res_draft = client_a.get(f"{url}?status=draft")
        assert res_draft.status_code == 200
        plans_draft = list(res_draft.context["plans"])
        assert _riskmanagement_plan_draft in plans_draft
        assert risk_management_plan_a not in plans_draft

        # Filter by device_class: class_ii_a
        res_class = client_a.get(f"{url}?device_class=class_ii_a")
        assert res_class.status_code == 200
        assert risk_management_plan_a in list(res_class.context["plans"])

        # Filter by non-matching device_class
        res_none = client_a.get(f"{url}?device_class=class_i")
        assert res_none.status_code == 200
        assert len(res_none.context["plans"]) == 0

    def test_riskmanagement_plan_list_search_and_pagination(
        self, client_a, risk_management_plan_a, _riskmanagement_plan_draft
    ):
        url = reverse("quality:risk_management_plan_list")

        # Search by number
        res_q = client_a.get(f"{url}?q={risk_management_plan_a.number}")
        assert res_q.status_code == 200
        assert risk_management_plan_a in list(res_q.context["plans"])
        assert _riskmanagement_plan_draft not in list(res_q.context["plans"])

        # Search by title
        res_title = client_a.get(f"{url}?q=Infusion+Pump")
        assert res_title.status_code == 200
        assert _riskmanagement_plan_draft in list(res_title.context["plans"])

        # Pagination: valid page
        res_p1 = client_a.get(f"{url}?page=1")
        assert res_p1.status_code == 200

        # Pagination: out of range page returns last page
        res_far = client_a.get(f"{url}?page=9999")
        assert res_far.status_code == 200

        # Pagination: junk non-numeric page returns page 1
        res_junk = client_a.get(f"{url}?page=abc&status=invalid_status")
        assert res_junk.status_code == 200

    def test_riskmanagement_plan_detail_get_success(
        self, client_a, risk_management_plan_a, risk_assessment_a, risk_control_measure_a, risk_review_record_a
    ):
        url = reverse("quality:risk_management_plan_detail", kwargs={"pk": risk_management_plan_a.pk})
        res = client_a.get(url)
        assert res.status_code == 200
        _riskmanagement_assert_no_comment_leaks(res)

        # Context keys
        assert res.context["plan"] == risk_management_plan_a
        assert "assessments" in res.context
        assert "reviews" in res.context
        assert "stats" in res.context

        # Verify stats dictionary
        stats = res.context["stats"]
        assert stats["total_assessments"] >= 1
        assert "unacceptable_count" in stats
        assert "alarp_count" in stats
        assert "acceptable_count" in stats
        assert stats["controls_count"] >= 1
        assert "verified_controls_count" in stats

        # Rendered content
        content = res.content.decode("utf-8")
        assert risk_management_plan_a.number in content
        assert risk_assessment_a.number in content
        assert risk_review_record_a.number in content

    def test_riskmanagement_plan_create_get(self, client_a):
        url = reverse("quality:risk_management_plan_create")
        res = client_a.get(url)
        assert res.status_code == 200
        _riskmanagement_assert_no_comment_leaks(res)

        assert "form" in res.context
        assert res.context["plan"] is None
        assert res.context["is_edit"] is False

    def test_riskmanagement_plan_create_post_valid(
        self, client_a, tenant_a, admin_user, design_project_a, quality_department
    ):
        url = reverse("quality:risk_management_plan_create")
        payload = {
            "title": "Hemodialysis System Risk Management Plan",
            "plan_version": "1.0",
            "device_classification": "class_ii_b",
            "design_project": design_project_a.pk,
            "lead_risk_manager": admin_user.pk,
            "department": quality_department.pk,
            "matrix_dimension": "5x5",
            "status": "draft",
            "scope_description": "Comprehensive risk analysis covering extracorporeal blood circuit safety.",
            "risk_acceptability_policy": "ISO 14971 ALARP criteria applied; all critical risks require mitigation.",
            "periodic_review_frequency_months": 12,
            "next_review_due_date": "2027-12-31",
        }
        res = client_a.post(url, payload)
        assert res.status_code == 302

        new_plan = RiskManagementPlan.objects.filter(title="Hemodialysis System Risk Management Plan").first()
        assert new_plan is not None
        assert new_plan.tenant == tenant_a
        assert new_plan.number.startswith("QRMP-")
        assert new_plan.device_classification == "class_ii_b"
        assert res.url == reverse("quality:risk_management_plan_detail", kwargs={"pk": new_plan.pk})

        # Verify audit log
        audit = _riskmanagement_audit_logs(new_plan, action="create")
        assert audit.exists()

        # Success message
        messages = _riskmanagement_get_messages(res)
        assert any("created successfully" in m for m in messages)

    def test_riskmanagement_plan_create_post_invalid(self, client_a):
        url = reverse("quality:risk_management_plan_create")
        # Missing required title, lead_risk_manager, scope_description, etc.
        res = client_a.post(url, {})
        assert res.status_code == 200
        assert "form" in res.context
        assert res.context["form"].errors
        assert "title" in res.context["form"].errors

    def test_riskmanagement_plan_edit_get_draft(self, client_a, _riskmanagement_plan_draft):
        url = reverse("quality:risk_management_plan_edit", kwargs={"pk": _riskmanagement_plan_draft.pk})
        res = client_a.get(url)
        assert res.status_code == 200
        _riskmanagement_assert_no_comment_leaks(res)

        assert "form" in res.context
        assert res.context["plan"] == _riskmanagement_plan_draft
        assert res.context["is_edit"] is True

    def test_riskmanagement_plan_edit_post_valid(self, client_a, _riskmanagement_plan_draft, admin_user):
        url = reverse("quality:risk_management_plan_edit", kwargs={"pk": _riskmanagement_plan_draft.pk})
        payload = {
            "title": "Updated Draft Plan Title for Infusion Pump",
            "plan_version": "1.1",
            "device_classification": "class_ii_a",
            "lead_risk_manager": admin_user.pk,
            "matrix_dimension": "5x5",
            "status": "draft",
            "scope_description": "Updated scope including wireless connectivity modules.",
            "risk_acceptability_policy": "Broadly acceptable when RPN < 4.",
            "periodic_review_frequency_months": 12,
        }
        res = client_a.post(url, payload)
        assert res.status_code == 302
        assert res.url == reverse("quality:risk_management_plan_detail", kwargs={"pk": _riskmanagement_plan_draft.pk})

        _riskmanagement_plan_draft.refresh_from_db()
        assert _riskmanagement_plan_draft.title == "Updated Draft Plan Title for Infusion Pump"
        assert _riskmanagement_plan_draft.plan_version == "1.1"

        # Verify audit log
        audit = _riskmanagement_audit_logs(_riskmanagement_plan_draft, action="update")
        assert audit.exists()

    def test_riskmanagement_plan_edit_guard_active_or_signed(
        self, client_a, risk_management_plan_a, _riskmanagement_signed_plan
    ):
        # 1. Guard against editing active plan
        url_active = reverse("quality:risk_management_plan_edit", kwargs={"pk": risk_management_plan_a.pk})
        res_get_act = client_a.get(url_active)
        assert res_get_act.status_code == 302
        assert res_get_act.url == reverse("quality:risk_management_plan_detail", kwargs={"pk": risk_management_plan_a.pk})
        messages_act = _riskmanagement_get_messages(res_get_act)
        assert any("cannot be modified while active" in m for m in messages_act)

        # POST should also be rejected
        res_post_act = client_a.post(url_active, {"title": "Malicious Mutate"})
        assert res_post_act.status_code == 302
        risk_management_plan_a.refresh_from_db()
        assert risk_management_plan_a.title != "Malicious Mutate"

        # 2. Guard against editing signed plan
        url_signed = reverse("quality:risk_management_plan_edit", kwargs={"pk": _riskmanagement_signed_plan.pk})
        res_get_sig = client_a.get(url_signed)
        assert res_get_sig.status_code == 302
        messages_sig = _riskmanagement_get_messages(res_get_sig)
        assert any("electronically signed" in m for m in messages_sig)

    def test_riskmanagement_plan_activate_post(self, client_a, _riskmanagement_plan_draft):
        url = reverse("quality:risk_management_plan_activate", kwargs={"pk": _riskmanagement_plan_draft.pk})
        res = client_a.post(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:risk_management_plan_detail", kwargs={"pk": _riskmanagement_plan_draft.pk})

        _riskmanagement_plan_draft.refresh_from_db()
        assert _riskmanagement_plan_draft.status == "active"

        # Verify audit log
        audit = _riskmanagement_audit_logs(_riskmanagement_plan_draft, action="activate")
        assert audit.exists()

        messages = _riskmanagement_get_messages(res)
        assert any("now Active" in m for m in messages)

    def test_riskmanagement_plan_activate_methods_and_permissions(
        self, client_a, member_client, _riskmanagement_plan_draft
    ):
        url = reverse("quality:risk_management_plan_activate", kwargs={"pk": _riskmanagement_plan_draft.pk})
        # GET should be rejected with 405 (require_POST)
        assert client_a.get(url).status_code == 405

        # Non-admin user should receive PermissionDenied 403
        res_perm = member_client.post(url)
        assert res_perm.status_code == 403

    def test_riskmanagement_plan_archive_post(self, client_a, risk_management_plan_a):
        url = reverse("quality:risk_management_plan_archive", kwargs={"pk": risk_management_plan_a.pk})
        res = client_a.post(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:risk_management_plan_detail", kwargs={"pk": risk_management_plan_a.pk})

        risk_management_plan_a.refresh_from_db()
        assert risk_management_plan_a.status == "archived"

        # Verify audit log
        audit = _riskmanagement_audit_logs(risk_management_plan_a, action="archive")
        assert audit.exists()

        messages = _riskmanagement_get_messages(res)
        assert any("has been archived" in m for m in messages)

    def test_riskmanagement_plan_archive_methods_and_permissions(
        self, client_a, member_client, risk_management_plan_a
    ):
        url = reverse("quality:risk_management_plan_archive", kwargs={"pk": risk_management_plan_a.pk})
        assert client_a.get(url).status_code == 405
        assert member_client.post(url).status_code == 403

    def test_riskmanagement_plan_delete_post(self, client_a, _riskmanagement_plan_draft):
        plan_pk = _riskmanagement_plan_draft.pk
        url = reverse("quality:risk_management_plan_delete", kwargs={"pk": plan_pk})
        res = client_a.post(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:risk_management_plan_list")

        assert not RiskManagementPlan.objects.filter(pk=plan_pk).exists()

        # Verify audit log was recorded with object_id before deletion
        audit = _riskmanagement_audit_logs(RiskManagementPlan, object_id=plan_pk, action="delete")
        assert audit.exists()

        messages = _riskmanagement_get_messages(res)
        assert any("deleted successfully" in m for m in messages)

    def test_riskmanagement_plan_delete_methods_and_permissions(
        self, client_a, member_client, _riskmanagement_plan_draft
    ):
        url = reverse("quality:risk_management_plan_delete", kwargs={"pk": _riskmanagement_plan_draft.pk})
        assert client_a.get(url).status_code == 405
        assert member_client.post(url).status_code == 403

    def test_riskmanagement_plan_export_csv(self, client_a, tenant_a, admin_user):
        # Create plan with potential formula injection
        p_formula = RiskManagementPlan.objects.create(
            tenant=tenant_a,
            title="=SUM(A1:B10)",
            plan_version="1.0",
            device_classification="class_ii_a",
            lead_risk_manager=admin_user,
            status="active",
            matrix_dimension="5x5",
            scope_description="+ScopeInjection",
            risk_acceptability_policy="Standard policy.",
        )

        url = reverse("quality:risk_management_plan_export")
        res = client_a.get(url)
        assert res.status_code == 200
        assert res["Content-Type"] == "text/csv"
        assert 'attachment; filename="risk_management_plans.csv"' in res["Content-Disposition"]
        assert res["X-Content-Type-Options"] == "nosniff"

        csv_text = res.content.decode("utf-8")
        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)
        headers = rows[0]

        expected_headers = [
            "Number",
            "Title",
            "Version",
            "Status",
            "Device Classification",
            "Design Project",
            "Lead Risk Manager",
            "Department",
            "Matrix Dimension",
            "Overall Residual Risk Acceptable",
            "Next Review Due",
            "Created At",
        ]
        assert headers == expected_headers

        # Verify formula sanitization (leading quote added)
        found_sanitized = False
        for row in rows[1:]:
            if row[0] == p_formula.number:
                assert row[1] == "'=SUM(A1:B10)"
                found_sanitized = True
        assert found_sanitized


# =====================================================================
# 2. RiskAssessments Views
# =====================================================================


class TestRiskAssessmentViews:
    def test_riskmanagement_assessment_list_get_success(self, client_a, risk_assessment_a):
        url = reverse("quality:risk_assessment_list")
        res = client_a.get(url)
        assert res.status_code == 200
        _riskmanagement_assert_no_comment_leaks(res)

        # Context keys
        assert "assessments" in res.context
        assert "page_obj" in res.context
        assert "total_count" in res.context
        assert "high_risk_count" in res.context
        assert "unmitigated_count" in res.context
        assert "closed_count" in res.context
        assert "analysis_type_choices" in res.context
        assert "hazard_category_choices" in res.context
        assert "risk_level_choices" in res.context
        assert "lifecycle_status_choices" in res.context
        assert "plans" in res.context
        assert "selected_type" in res.context
        assert "selected_cat" in res.context
        assert "selected_level" in res.context
        assert "selected_status" in res.context
        assert "selected_plan" in res.context
        assert "q" in res.context

        assert res.context["total_count"] >= 1

        content = res.content.decode("utf-8")
        assert risk_assessment_a.number in content
        assert risk_assessment_a.hazard_description in content

    def test_riskmanagement_assessment_list_filtering_and_search(
        self, client_a, risk_assessment_a, risk_management_plan_a, tenant_a
    ):
        # Create second assessment with different attributes
        assessment_pfmea = RiskAssessment.objects.create(
            tenant=tenant_a,
            plan=risk_management_plan_a,
            hazard_category="biological_chemical",
            hazard_description="Cleaning solvent residue on fluid path",
            foreseeable_sequence_of_events="Rinse cycle duration too short.",
            hazardous_situation="Toxics infused into patient blood stream.",
            potential_harm="Acute toxic organ failure.",
            analysis_type="pfmea",
            initial_severity=5,
            initial_probability=1,
            lifecycle_status="closed",
            residual_risk_acceptable=True,
        )

        url = reverse("quality:risk_assessment_list")

        # Filter by hazard_category
        res_cat = client_a.get(f"{url}?hazard_category=energy_electrical")
        assert res_cat.status_code == 200
        assessments_cat = list(res_cat.context["assessments"])
        assert risk_assessment_a in assessments_cat
        assert assessment_pfmea not in assessments_cat

        # Filter by analysis_type
        res_type = client_a.get(f"{url}?analysis_type=pfmea")
        assert res_type.status_code == 200
        assessments_type = list(res_type.context["assessments"])
        assert assessment_pfmea in assessments_type
        assert risk_assessment_a not in assessments_type

        # Filter by lifecycle_status
        res_status = client_a.get(f"{url}?lifecycle_status=closed")
        assert res_status.status_code == 200
        assert assessment_pfmea in list(res_status.context["assessments"])
        assert risk_assessment_a not in list(res_status.context["assessments"])

        # Filter by plan
        res_plan = client_a.get(f"{url}?plan={risk_management_plan_a.pk}")
        assert res_plan.status_code == 200
        assert risk_assessment_a in list(res_plan.context["assessments"])

        # Search by number
        res_q = client_a.get(f"{url}?q={risk_assessment_a.number}")
        assert res_q.status_code == 200
        assert risk_assessment_a in list(res_q.context["assessments"])
        assert assessment_pfmea not in list(res_q.context["assessments"])

        # Pagination: valid page and out of range
        assert client_a.get(f"{url}?page=1").status_code == 200
        assert client_a.get(f"{url}?page=9999").status_code == 200
        assert client_a.get(f"{url}?page=invalid_param").status_code == 200

    def test_riskmanagement_assessment_detail_get_success(
        self, client_a, risk_assessment_a, risk_control_measure_a
    ):
        url = reverse("quality:risk_assessment_detail", kwargs={"pk": risk_assessment_a.pk})
        res = client_a.get(url)
        assert res.status_code == 200
        _riskmanagement_assert_no_comment_leaks(res)

        assert res.context["assessment"] == risk_assessment_a
        assert "control_measures" in res.context
        assert risk_control_measure_a in list(res.context["control_measures"])

        content = res.content.decode("utf-8")
        assert risk_assessment_a.number in content
        assert risk_control_measure_a.title in content

    def test_riskmanagement_assessment_create_get(self, client_a, risk_management_plan_a):
        url = reverse("quality:risk_assessment_create")
        res = client_a.get(url)
        assert res.status_code == 200
        _riskmanagement_assert_no_comment_leaks(res)
        assert "form" in res.context
        assert res.context["assessment"] is None
        assert res.context["is_edit"] is False

        # Prefilled with plan query parameter
        res_plan = client_a.get(f"{url}?plan={risk_management_plan_a.pk}")
        assert res_plan.status_code == 200
        assert res_plan.context["form"].initial.get("plan") == risk_management_plan_a.pk

    def test_riskmanagement_assessment_create_post_valid(self, client_a, tenant_a, risk_management_plan_a):
        url = reverse("quality:risk_assessment_create")
        payload = {
            "plan": risk_management_plan_a.pk,
            "analysis_type": "dfmea",
            "hazard_category": "energy_thermal",
            "hazard_description": "Battery pack overheating during high-rate charging",
            "foreseeable_sequence_of_events": "Thermistor failure causes charger to overvolt cells beyond 4.35V.",
            "hazardous_situation": "Thermal runaway inside battery compartment adjacent to patient.",
            "potential_harm": "Severe third-degree burns and smoke inhalation.",
            "initial_severity": 5,
            "initial_probability": 3,
            "initial_detectability": 2,
            "residual_severity": 2,
            "residual_probability": 2,
            "residual_detectability": 1,
            "residual_risk_acceptable": True,
            "lifecycle_status": "mitigated",
        }
        res = client_a.post(url, payload)
        assert res.status_code == 302

        new_assessment = RiskAssessment.objects.filter(
            hazard_description="Battery pack overheating during high-rate charging"
        ).first()
        assert new_assessment is not None
        assert new_assessment.tenant == tenant_a
        assert new_assessment.number.startswith("QRSK-")
        assert res.url == reverse("quality:risk_assessment_detail", kwargs={"pk": new_assessment.pk})

        # Verify automated score calculations
        # Initial: S=5, P=3, D=2 => RPN = 30; Initial risk score = 5*3 = 15 => unacceptable
        assert new_assessment.initial_rpn == 30
        assert new_assessment.initial_risk_level == "unacceptable"

        # Residual: S=2, P=2, D=1 => RPN = 4; Residual score = 2*2 = 4 => broadly_acceptable
        assert new_assessment.residual_rpn == 4
        assert new_assessment.residual_risk_level == "broadly_acceptable"

        # Verify audit log
        audit = _riskmanagement_audit_logs(new_assessment, action="create")
        assert audit.exists()

        messages = _riskmanagement_get_messages(res)
        assert any("logged successfully" in m for m in messages)

    def test_riskmanagement_assessment_create_post_invalid(self, client_a, risk_management_plan_a):
        url = reverse("quality:risk_assessment_create")
        # Safety gate violation: residual risk cannot be acceptable when residual score is in unacceptable zone (S=5, P=4 => 20)
        payload = {
            "plan": risk_management_plan_a.pk,
            "analysis_type": "dfmea",
            "hazard_category": "energy_electrical",
            "hazard_description": "Inadequate insulation",
            "hazardous_situation": "Exposed high voltage",
            "potential_harm": "Fatal electrocution",
            "initial_severity": 5,
            "initial_probability": 5,
            "residual_severity": 5,
            "residual_probability": 4,
            "residual_risk_acceptable": True,  # ISO 14971 violation!
        }
        res = client_a.post(url, payload)
        assert res.status_code == 200
        assert "form" in res.context
        assert res.context["form"].errors
        assert "residual_risk_acceptable" in res.context["form"].errors

    def test_riskmanagement_assessment_edit_get(self, client_a, risk_assessment_a):
        url = reverse("quality:risk_assessment_edit", kwargs={"pk": risk_assessment_a.pk})
        res = client_a.get(url)
        assert res.status_code == 200
        _riskmanagement_assert_no_comment_leaks(res)

        assert "form" in res.context
        assert res.context["assessment"] == risk_assessment_a
        assert res.context["is_edit"] is True

    def test_riskmanagement_assessment_edit_post_valid(self, client_a, risk_assessment_a):
        url = reverse("quality:risk_assessment_edit", kwargs={"pk": risk_assessment_a.pk})
        payload = {
            "plan": risk_assessment_a.plan.pk,
            "analysis_type": risk_assessment_a.analysis_type,
            "hazard_category": risk_assessment_a.hazard_category,
            "hazard_description": "Updated chassis electrical breakdown under damp conditions",
            "foreseeable_sequence_of_events": risk_assessment_a.foreseeable_sequence_of_events,
            "hazardous_situation": risk_assessment_a.hazardous_situation,
            "potential_harm": risk_assessment_a.potential_harm,
            "initial_severity": 5,
            "initial_probability": 2,
            "initial_detectability": 2,
            "lifecycle_status": "open",
        }
        res = client_a.post(url, payload)
        assert res.status_code == 302
        assert res.url == reverse("quality:risk_assessment_detail", kwargs={"pk": risk_assessment_a.pk})

        risk_assessment_a.refresh_from_db()
        assert risk_assessment_a.hazard_description == "Updated chassis electrical breakdown under damp conditions"
        assert risk_assessment_a.initial_rpn == 20  # 5 * 2 * 2

        # Verify audit log
        audit = _riskmanagement_audit_logs(risk_assessment_a, action="update")
        assert audit.exists()

    def test_riskmanagement_assessment_delete_post(self, client_a, risk_assessment_a):
        assessment_pk = risk_assessment_a.pk
        plan_pk = risk_assessment_a.plan_id
        url = reverse("quality:risk_assessment_delete", kwargs={"pk": assessment_pk})
        res = client_a.post(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:risk_management_plan_detail", kwargs={"pk": plan_pk})

        assert not RiskAssessment.objects.filter(pk=assessment_pk).exists()

        # Audit log preserved with object_id
        audit = _riskmanagement_audit_logs(RiskAssessment, object_id=assessment_pk, action="delete")
        assert audit.exists()

        messages = _riskmanagement_get_messages(res)
        assert any("deleted successfully" in m for m in messages)

    def test_riskmanagement_assessment_delete_methods_and_permissions(
        self, client_a, member_client, risk_assessment_a
    ):
        url = reverse("quality:risk_assessment_delete", kwargs={"pk": risk_assessment_a.pk})
        assert client_a.get(url).status_code == 405
        assert member_client.post(url).status_code == 403

    def test_riskmanagement_assessment_export_csv(self, client_a, risk_assessment_a):
        url = reverse("quality:risk_assessment_export")
        res = client_a.get(url)
        assert res.status_code == 200
        assert res["Content-Type"] == "text/csv"
        assert 'attachment; filename="risk_assessments.csv"' in res["Content-Disposition"]
        assert res["X-Content-Type-Options"] == "nosniff"

        csv_text = res.content.decode("utf-8")
        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)
        headers = rows[0]

        expected_headers = [
            "Number",
            "Plan",
            "Analysis Type",
            "Hazard Category",
            "Hazard / Failure Mode",
            "Harm / Failure Effect",
            "Initial S",
            "Initial P",
            "Initial D",
            "Initial RPN",
            "Initial Risk Level",
            "Residual S",
            "Residual P",
            "Residual D",
            "Residual RPN",
            "Residual Risk Level",
            "Residual Risk Acceptable",
            "BRA Required",
            "Lifecycle Status",
            "Created At",
        ]
        assert headers == expected_headers
        assert any(row[0] == risk_assessment_a.number for row in rows[1:])


# =====================================================================
# 3. RiskControlMeasures Views
# =====================================================================


class TestRiskControlMeasureViews:
    def test_riskmanagement_control_measure_list_get_success(self, client_a, risk_control_measure_a):
        url = reverse("quality:risk_control_measure_list")
        res = client_a.get(url)
        assert res.status_code == 200
        _riskmanagement_assert_no_comment_leaks(res)

        # Context keys
        assert "control_measures" in res.context
        assert "page_obj" in res.context
        assert "total_count" in res.context
        assert "verified_count" in res.context
        assert "inherent_safety_count" in res.context
        assert "in_progress_count" in res.context
        assert "hierarchy_choices" in res.context
        assert "status_choices" in res.context
        assert "plans" in res.context
        assert "selected_hierarchy" in res.context
        assert "selected_status" in res.context
        assert "selected_plan" in res.context
        assert "q" in res.context

        assert res.context["total_count"] >= 1

        content = res.content.decode("utf-8")
        assert risk_control_measure_a.number in content
        assert risk_control_measure_a.title in content

    def test_riskmanagement_control_measure_list_filtering_and_search(
        self, client_a, risk_control_measure_a, risk_assessment_a, tenant_a, admin_user
    ):
        measure_warning = RiskControlMeasure.objects.create(
            tenant=tenant_a,
            risk_assessment=risk_assessment_a,
            control_hierarchy="information_for_safety",
            title="Warning Label on Enclosure Door",
            description="High voltage warning symbol per ISO 7010.",
            status="implemented",
            assigned_to=admin_user,
        )

        url = reverse("quality:risk_control_measure_list")

        # Filter by control_hierarchy
        res_hier = client_a.get(f"{url}?control_hierarchy=inherent_safety")
        assert res_hier.status_code == 200
        controls_hier = list(res_hier.context["control_measures"])
        assert risk_control_measure_a in controls_hier
        assert measure_warning not in controls_hier

        # Filter by status
        res_stat = client_a.get(f"{url}?status=implemented")
        assert res_stat.status_code == 200
        controls_stat = list(res_stat.context["control_measures"])
        assert measure_warning in controls_stat
        assert risk_control_measure_a not in controls_stat

        # Filter by plan
        res_plan = client_a.get(f"{url}?plan={risk_assessment_a.plan_id}")
        assert res_plan.status_code == 200
        assert risk_control_measure_a in list(res_plan.context["control_measures"])

        # Search by title
        res_q = client_a.get(f"{url}?q=Warning+Label")
        assert res_q.status_code == 200
        assert measure_warning in list(res_q.context["control_measures"])
        assert risk_control_measure_a not in list(res_q.context["control_measures"])

        # Pagination
        assert client_a.get(f"{url}?page=1").status_code == 200
        assert client_a.get(f"{url}?page=9999").status_code == 200
        assert client_a.get(f"{url}?page=invalid").status_code == 200

    def test_riskmanagement_control_measure_detail_get_success(self, client_a, risk_control_measure_a):
        url = reverse("quality:risk_control_measure_detail", kwargs={"pk": risk_control_measure_a.pk})
        res = client_a.get(url)
        assert res.status_code == 200
        _riskmanagement_assert_no_comment_leaks(res)

        assert res.context["control_measure"] == risk_control_measure_a

        content = res.content.decode("utf-8")
        assert risk_control_measure_a.number in content
        assert risk_control_measure_a.title in content

    def test_riskmanagement_control_measure_create_get(self, client_a, risk_assessment_a):
        url = reverse("quality:risk_control_measure_create")
        res = client_a.get(url)
        assert res.status_code == 200
        _riskmanagement_assert_no_comment_leaks(res)
        assert "form" in res.context
        assert res.context["control_measure"] is None
        assert res.context["is_edit"] is False

        # Prefill with ?assessment= query param
        res_param = client_a.get(f"{url}?assessment={risk_assessment_a.pk}")
        assert res_param.status_code == 200
        assert res_param.context["form"].initial.get("risk_assessment") == risk_assessment_a.pk

    def test_riskmanagement_control_measure_create_post_valid(
        self, client_a, tenant_a, risk_assessment_a, admin_user
    ):
        url = reverse("quality:risk_control_measure_create")
        payload = {
            "risk_assessment": risk_assessment_a.pk,
            "title": "Hardware Thermal Cutoff Switch",
            "control_hierarchy": "protective_measure",
            "description": "Bimetallic thermal cutoff switch in series with primary motor power.",
            "assigned_to": admin_user.pk,
            "status": "planned",
        }
        res = client_a.post(url, payload)
        assert res.status_code == 302

        new_control = RiskControlMeasure.objects.filter(title="Hardware Thermal Cutoff Switch").first()
        assert new_control is not None
        assert new_control.tenant == tenant_a
        assert new_control.number.startswith("QRCM-")
        assert res.url == reverse("quality:risk_control_measure_detail", kwargs={"pk": new_control.pk})

        # Verify audit log
        audit = _riskmanagement_audit_logs(new_control, action="create")
        assert audit.exists()

        messages = _riskmanagement_get_messages(res)
        assert any("created successfully" in m for m in messages)

    def test_riskmanagement_control_measure_create_post_invalid(self, client_a):
        url = reverse("quality:risk_control_measure_create")
        res = client_a.post(url, {})
        assert res.status_code == 200
        assert "form" in res.context
        assert res.context["form"].errors
        assert "title" in res.context["form"].errors

    def test_riskmanagement_control_measure_edit_get(self, client_a, risk_control_measure_a):
        url = reverse("quality:risk_control_measure_edit", kwargs={"pk": risk_control_measure_a.pk})
        res = client_a.get(url)
        assert res.status_code == 200
        _riskmanagement_assert_no_comment_leaks(res)

        assert "form" in res.context
        assert res.context["control_measure"] == risk_control_measure_a
        assert res.context["is_edit"] is True

    def test_riskmanagement_control_measure_edit_post_valid(self, client_a, risk_control_measure_a):
        url = reverse("quality:risk_control_measure_edit", kwargs={"pk": risk_control_measure_a.pk})
        payload = {
            "risk_assessment": risk_control_measure_a.risk_assessment.pk,
            "title": "Galvanic 5kV Reinforced Isolation Transformer",
            "control_hierarchy": "inherent_safety",
            "description": "Upgraded dielectric barrier to 5kV surge rating per IEC 60601-1.",
            "status": "planned",
        }
        res = client_a.post(url, payload)
        assert res.status_code == 302
        assert res.url == reverse("quality:risk_control_measure_detail", kwargs={"pk": risk_control_measure_a.pk})

        risk_control_measure_a.refresh_from_db()
        assert risk_control_measure_a.title == "Galvanic 5kV Reinforced Isolation Transformer"

        # Verify audit log
        audit = _riskmanagement_audit_logs(risk_control_measure_a, action="update")
        assert audit.exists()

    def test_riskmanagement_control_measure_verify_impl(self, client_a, risk_control_measure_a):
        assert not risk_control_measure_a.implementation_verified
        assert risk_control_measure_a.status == "planned"

        url = reverse("quality:risk_control_measure_verify_impl", kwargs={"pk": risk_control_measure_a.pk})
        res = client_a.post(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:risk_control_measure_detail", kwargs={"pk": risk_control_measure_a.pk})

        risk_control_measure_a.refresh_from_db()
        assert risk_control_measure_a.implementation_verified is True
        # Since status was planned and effectiveness not yet verified, transition to "implemented"
        assert risk_control_measure_a.status == "implemented"

        # Verify audit log
        audit = _riskmanagement_audit_logs(risk_control_measure_a, action="verify")
        assert audit.exists()

        messages = _riskmanagement_get_messages(res)
        assert any("Implementation verified" in m for m in messages)

    def test_riskmanagement_control_measure_verify_eff(self, client_a, risk_control_measure_a):
        # Set implementation verified first
        risk_control_measure_a.implementation_verified = True
        risk_control_measure_a.status = "implemented"
        risk_control_measure_a.save()

        url = reverse("quality:risk_control_measure_verify_eff", kwargs={"pk": risk_control_measure_a.pk})
        res = client_a.post(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:risk_control_measure_detail", kwargs={"pk": risk_control_measure_a.pk})

        risk_control_measure_a.refresh_from_db()
        assert risk_control_measure_a.effectiveness_verified is True
        # Both verified => status transitions to "verified"
        assert risk_control_measure_a.status == "verified"

        # Verify audit log
        audit = _riskmanagement_audit_logs(risk_control_measure_a, action="verify")
        assert audit.exists()

        messages = _riskmanagement_get_messages(res)
        assert any("Effectiveness verified" in m for m in messages)

    def test_riskmanagement_control_measure_verify_methods(self, client_a, risk_control_measure_a):
        url_impl = reverse("quality:risk_control_measure_verify_impl", kwargs={"pk": risk_control_measure_a.pk})
        assert client_a.get(url_impl).status_code == 405

        url_eff = reverse("quality:risk_control_measure_verify_eff", kwargs={"pk": risk_control_measure_a.pk})
        assert client_a.get(url_eff).status_code == 405

    def test_riskmanagement_control_measure_delete_post(self, client_a, risk_control_measure_a):
        control_pk = risk_control_measure_a.pk
        assessment_pk = risk_control_measure_a.risk_assessment_id
        url = reverse("quality:risk_control_measure_delete", kwargs={"pk": control_pk})
        res = client_a.post(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:risk_assessment_detail", kwargs={"pk": assessment_pk})

        assert not RiskControlMeasure.objects.filter(pk=control_pk).exists()

        # Audit log preserved with object_id
        audit = _riskmanagement_audit_logs(RiskControlMeasure, object_id=control_pk, action="delete")
        assert audit.exists()

        messages = _riskmanagement_get_messages(res)
        assert any("deleted successfully" in m for m in messages)

    def test_riskmanagement_control_measure_delete_methods_and_permissions(
        self, client_a, member_client, risk_control_measure_a
    ):
        url = reverse("quality:risk_control_measure_delete", kwargs={"pk": risk_control_measure_a.pk})
        assert client_a.get(url).status_code == 405
        assert member_client.post(url).status_code == 403

    def test_riskmanagement_control_measure_export_csv(self, client_a, risk_control_measure_a):
        url = reverse("quality:risk_control_measure_export")
        res = client_a.get(url)
        assert res.status_code == 200
        assert res["Content-Type"] == "text/csv"
        assert 'attachment; filename="risk_control_measures.csv"' in res["Content-Disposition"]
        assert res["X-Content-Type-Options"] == "nosniff"

        csv_text = res.content.decode("utf-8")
        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)
        headers = rows[0]

        expected_headers = [
            "Number",
            "Risk Item",
            "Hierarchy Tier",
            "Title",
            "Assigned To",
            "Status",
            "Design Input",
            "Controlled Document",
            "Design Verification",
            "Implementation Verified",
            "Effectiveness Verified",
            "Introduces New Hazard",
            "Created At",
        ]
        assert headers == expected_headers
        assert any(row[0] == risk_control_measure_a.number for row in rows[1:])


# =====================================================================
# 4. RiskReviewRecords Views
# =====================================================================


class TestRiskReviewRecordViews:
    def test_riskmanagement_review_record_list_get_success(self, client_a, risk_review_record_a):
        url = reverse("quality:risk_review_record_list")
        res = client_a.get(url)
        assert res.status_code == 200
        _riskmanagement_assert_no_comment_leaks(res)

        # Context keys
        assert "review_records" in res.context
        assert "page_obj" in res.context
        assert "total_count" in res.context
        assert "approved_count" in res.context
        assert "pms_count" in res.context
        assert "draft_count" in res.context
        assert "review_type_choices" in res.context
        assert "status_choices" in res.context
        assert "plans" in res.context
        assert "selected_type" in res.context
        assert "selected_status" in res.context
        assert "selected_plan" in res.context
        assert "q" in res.context

        assert res.context["total_count"] >= 1

        content = res.content.decode("utf-8")
        assert risk_review_record_a.number in content
        assert risk_review_record_a.review_title in content

    def test_riskmanagement_review_record_list_filtering_and_search(
        self, client_a, risk_review_record_a, risk_management_plan_a, tenant_a, admin_user
    ):
        pms_review = RiskReviewRecord.objects.create(
            tenant=tenant_a,
            plan=risk_management_plan_a,
            review_type="post_market_surveillance",
            review_title="Annual Post Market Clinical Surveillance",
            findings_summary="Complaints analyzed per ISO 14971: no new unanticipated harms reported.",
            review_date=timezone.now().date(),
            lead_reviewer=admin_user,
            status="approved",
        )

        url = reverse("quality:risk_review_record_list")

        # Filter by review_type
        res_type = client_a.get(f"{url}?review_type=post_market_surveillance")
        assert res_type.status_code == 200
        records_type = list(res_type.context["review_records"])
        assert pms_review in records_type
        assert risk_review_record_a not in records_type

        # Filter by status
        res_stat = client_a.get(f"{url}?status=approved")
        assert res_stat.status_code == 200
        records_stat = list(res_stat.context["review_records"])
        assert pms_review in records_stat
        assert risk_review_record_a not in records_stat

        # Filter by plan
        res_plan = client_a.get(f"{url}?plan={risk_management_plan_a.pk}")
        assert res_plan.status_code == 200
        assert risk_review_record_a in list(res_plan.context["review_records"])

        # Search by query
        res_q = client_a.get(f"{url}?q=Clinical+Surveillance")
        assert res_q.status_code == 200
        assert pms_review in list(res_q.context["review_records"])
        assert risk_review_record_a not in list(res_q.context["review_records"])

        # Pagination
        assert client_a.get(f"{url}?page=1").status_code == 200
        assert client_a.get(f"{url}?page=9999").status_code == 200
        assert client_a.get(f"{url}?page=junk").status_code == 200

    def test_riskmanagement_review_record_detail_get_success(self, client_a, risk_review_record_a):
        url = reverse("quality:risk_review_record_detail", kwargs={"pk": risk_review_record_a.pk})
        res = client_a.get(url)
        assert res.status_code == 200
        _riskmanagement_assert_no_comment_leaks(res)

        assert res.context["review_record"] == risk_review_record_a

        content = res.content.decode("utf-8")
        assert risk_review_record_a.number in content
        assert risk_review_record_a.review_title in content

    def test_riskmanagement_review_record_create_get(self, client_a, risk_management_plan_a):
        url = reverse("quality:risk_review_record_create")
        res = client_a.get(url)
        assert res.status_code == 200
        _riskmanagement_assert_no_comment_leaks(res)
        assert "form" in res.context
        assert res.context["review_record"] is None
        assert res.context["is_edit"] is False

        # Prefilled plan param
        res_plan = client_a.get(f"{url}?plan={risk_management_plan_a.pk}")
        assert res_plan.status_code == 200
        assert res_plan.context["form"].initial.get("plan") == risk_management_plan_a.pk

    def test_riskmanagement_review_record_create_post_valid(
        self, client_a, tenant_a, risk_management_plan_a, admin_user
    ):
        url = reverse("quality:risk_review_record_create")
        payload = {
            "plan": risk_management_plan_a.pk,
            "review_title": "Design Freeze Comprehensive Risk Review",
            "review_type": "initial_rmr",
            "review_date": "2026-11-20",
            "lead_reviewer": admin_user.pk,
            "findings_summary": "All mitigations documented and verified prior to design freeze release.",
            "status": "draft",
            "overall_residual_risk_reconfirmed": True,
        }
        res = client_a.post(url, payload)
        assert res.status_code == 302

        new_review = RiskReviewRecord.objects.filter(
            review_title="Design Freeze Comprehensive Risk Review"
        ).first()
        assert new_review is not None
        assert new_review.tenant == tenant_a
        assert new_review.number.startswith("QRMR-")
        assert res.url == reverse("quality:risk_review_record_detail", kwargs={"pk": new_review.pk})

        # Verify audit log
        audit = _riskmanagement_audit_logs(new_review, action="create")
        assert audit.exists()

        messages = _riskmanagement_get_messages(res)
        assert any("logged successfully" in m for m in messages)

    def test_riskmanagement_review_record_create_post_invalid(self, client_a, risk_management_plan_a):
        url = reverse("quality:risk_review_record_create")
        # Attempting status="approved" directly in form is rejected by form clean()
        payload = {
            "plan": risk_management_plan_a.pk,
            "review_title": "Bypass Approval Form",
            "review_type": "initial_rmr",
            "review_date": "2026-11-20",
            "status": "approved",
        }
        res = client_a.post(url, payload)
        assert res.status_code == 200
        assert "form" in res.context
        assert res.context["form"].errors

    def test_riskmanagement_review_record_edit_get_draft(self, client_a, risk_review_record_a):
        url = reverse("quality:risk_review_record_edit", kwargs={"pk": risk_review_record_a.pk})
        res = client_a.get(url)
        assert res.status_code == 200
        _riskmanagement_assert_no_comment_leaks(res)

        assert "form" in res.context
        assert res.context["review_record"] == risk_review_record_a
        assert res.context["is_edit"] is True

    def test_riskmanagement_review_record_edit_post_valid(self, client_a, risk_review_record_a, admin_user):
        url = reverse("quality:risk_review_record_edit", kwargs={"pk": risk_review_record_a.pk})
        payload = {
            "plan": risk_review_record_a.plan.pk,
            "review_title": "Revised Risk Review Title",
            "review_type": risk_review_record_a.review_type,
            "review_date": str(risk_review_record_a.review_date),
            "lead_reviewer": admin_user.pk,
            "findings_summary": "Updated findings including electrical isolation verification results.",
            "status": "draft",
        }
        res = client_a.post(url, payload)
        assert res.status_code == 302
        assert res.url == reverse("quality:risk_review_record_detail", kwargs={"pk": risk_review_record_a.pk})

        risk_review_record_a.refresh_from_db()
        assert risk_review_record_a.review_title == "Revised Risk Review Title"

        # Verify audit log
        audit = _riskmanagement_audit_logs(risk_review_record_a, action="update")
        assert audit.exists()

    def test_riskmanagement_review_record_edit_guard_approved(
        self, client_a, _riskmanagement_review_approved
    ):
        url = reverse("quality:risk_review_record_edit", kwargs={"pk": _riskmanagement_review_approved.pk})
        res = client_a.get(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:risk_review_record_detail", kwargs={"pk": _riskmanagement_review_approved.pk})

        messages = _riskmanagement_get_messages(res)
        assert any("cannot be modified because it is already approved" in m for m in messages)

        # POST should also be blocked
        res_post = client_a.post(url, {"review_title": "Hacked Review"})
        assert res_post.status_code == 302
        _riskmanagement_review_approved.refresh_from_db()
        assert _riskmanagement_review_approved.review_title != "Hacked Review"

    def test_riskmanagement_review_record_approve_post(self, client_a, risk_review_record_a):
        assert risk_review_record_a.status == "draft"

        url = reverse("quality:risk_review_record_approve", kwargs={"pk": risk_review_record_a.pk})
        res = client_a.post(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:risk_review_record_detail", kwargs={"pk": risk_review_record_a.pk})

        risk_review_record_a.refresh_from_db()
        assert risk_review_record_a.status == "approved"

        # Verify audit log
        audit = _riskmanagement_audit_logs(risk_review_record_a, action="approve")
        assert audit.exists()

        messages = _riskmanagement_get_messages(res)
        assert any("has been approved" in m for m in messages)

    def test_riskmanagement_review_record_approve_methods_and_permissions(
        self, client_a, member_client, risk_review_record_a
    ):
        url = reverse("quality:risk_review_record_approve", kwargs={"pk": risk_review_record_a.pk})
        assert client_a.get(url).status_code == 405
        assert member_client.post(url).status_code == 403

    def test_riskmanagement_review_record_delete_post(self, client_a, risk_review_record_a):
        review_pk = risk_review_record_a.pk
        plan_pk = risk_review_record_a.plan_id
        url = reverse("quality:risk_review_record_delete", kwargs={"pk": review_pk})
        res = client_a.post(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:risk_management_plan_detail", kwargs={"pk": plan_pk})

        assert not RiskReviewRecord.objects.filter(pk=review_pk).exists()

        # Audit log preserved with object_id
        audit = _riskmanagement_audit_logs(RiskReviewRecord, object_id=review_pk, action="delete")
        assert audit.exists()

        messages = _riskmanagement_get_messages(res)
        assert any("deleted successfully" in m for m in messages)

    def test_riskmanagement_review_record_delete_methods_and_permissions(
        self, client_a, member_client, risk_review_record_a
    ):
        url = reverse("quality:risk_review_record_delete", kwargs={"pk": risk_review_record_a.pk})
        assert client_a.get(url).status_code == 405
        assert member_client.post(url).status_code == 403

    def test_riskmanagement_review_record_export_csv(self, client_a, risk_review_record_a):
        url = reverse("quality:risk_review_record_export")
        res = client_a.get(url)
        assert res.status_code == 200
        assert res["Content-Type"] == "text/csv"
        assert 'attachment; filename="risk_review_records.csv"' in res["Content-Disposition"]
        assert res["X-Content-Type-Options"] == "nosniff"

        csv_text = res.content.decode("utf-8")
        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)
        headers = rows[0]

        expected_headers = [
            "Number",
            "Plan",
            "Review Title",
            "Review Type",
            "Review Date",
            "Lead Reviewer",
            "New Hazards Identified",
            "Risk Profile Changed",
            "Overall Residual Risk Reconfirmed",
            "Status",
            "Created At",
        ]
        assert headers == expected_headers
        assert any(row[0] == risk_review_record_a.number for row in rows[1:])


# =====================================================================
# 5. FmeaMatrix & RiskTraceabilityMatrix Views
# =====================================================================


class TestFmeaMatrixViews:
    def test_riskmanagement_fmea_matrix_get_default(
        self, client_a, risk_management_plan_a, risk_assessment_a
    ):
        url = reverse("quality:fmea_matrix")
        res = client_a.get(url)
        assert res.status_code == 200
        _riskmanagement_assert_no_comment_leaks(res)

        # Context keys
        assert "plans" in res.context
        assert "selected_plan" in res.context
        assert res.context["selected_plan"] == risk_management_plan_a
        assert "grid_rows" in res.context
        assert "matrix_cells" in res.context
        assert "matrix_dimension" in res.context
        assert "severity_range" in res.context
        assert "probability_range" in res.context
        assert "high_risk_items" in res.context
        assert "rpn_pareto_items" in res.context
        assert "stats" in res.context

        # Grid rows structure: 5 rows for 5x5 matrix
        grid_rows = res.context["grid_rows"]
        assert len(grid_rows) == 5
        # Each row has severity_val, severity_label, and 5 cells
        for row in grid_rows:
            assert len(row["cells"]) == 5

        # Stats validation
        stats = res.context["stats"]
        assert stats["total"] >= 1
        assert "unacceptable" in stats
        assert "alarp" in stats
        assert "broadly_acceptable" in stats
        assert "residual_acceptable" in stats

        # Matrix cells mapping contains risk_assessment_a (S=4, P=3)
        cell_4_3 = res.context["matrix_cells"][(4, 3)]
        assert risk_assessment_a in cell_4_3["initial_items"]

    def test_riskmanagement_fmea_matrix_get_specific_plan(
        self, client_a, risk_management_plan_a, _riskmanagement_plan_draft
    ):
        url = reverse("quality:fmea_matrix")
        res = client_a.get(f"{url}?plan={_riskmanagement_plan_draft.pk}")
        assert res.status_code == 200
        assert res.context["selected_plan"] == _riskmanagement_plan_draft

    def test_riskmanagement_fmea_matrix_invalid_or_cross_tenant_plan(
        self, client_a, risk_management_plan_b
    ):
        url = reverse("quality:fmea_matrix")

        # Non-numeric plan ID raises 404
        res_non_num = client_a.get(f"{url}?plan=invalid_id")
        assert res_non_num.status_code == 404

        # Cross-tenant plan ID raises 404
        res_cross = client_a.get(f"{url}?plan={risk_management_plan_b.pk}")
        assert res_cross.status_code == 404

    def test_riskmanagement_fmea_matrix_export_csv(
        self, client_a, risk_management_plan_a, risk_assessment_a
    ):
        url = reverse("quality:fmea_matrix_export")
        # Default (no ?plan= specified) exports first plan
        res = client_a.get(url)
        assert res.status_code == 200
        assert res["Content-Type"] == "text/csv"
        assert 'attachment; filename="fmea_risk_matrix.csv"' in res["Content-Disposition"]
        assert res["X-Content-Type-Options"] == "nosniff"

        csv_text = res.content.decode("utf-8")
        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)
        headers = rows[0]

        expected_headers = [
            "Plan",
            "Number",
            "Type",
            "Hazard / Failure Mode",
            "Initial S",
            "Initial P",
            "Initial D",
            "Initial RPN",
            "Initial Level",
            "Residual S",
            "Residual P",
            "Residual D",
            "Residual RPN",
            "Residual Level",
            "Residual Acceptable",
            "Lifecycle Status",
        ]
        assert headers == expected_headers
        assert any(row[1] == risk_assessment_a.number for row in rows[1:])

    def test_riskmanagement_fmea_matrix_export_cross_tenant_404(
        self, client_a, risk_management_plan_b
    ):
        url = reverse("quality:fmea_matrix_export")
        assert client_a.get(f"{url}?plan={risk_management_plan_b.pk}").status_code == 404
        assert client_a.get(f"{url}?plan=abc").status_code == 404

    def test_riskmanagement_risk_traceability_matrix_get(
        self, client_a, risk_management_plan_a, risk_assessment_a, risk_control_measure_a
    ):
        url = reverse("quality:risk_traceability_matrix")
        res = client_a.get(url)
        assert res.status_code == 200
        _riskmanagement_assert_no_comment_leaks(res)

        # Context keys
        assert "plans" in res.context
        assert "selected_plan" in res.context
        assert res.context["selected_plan"] == risk_management_plan_a
        assert "traceability_rows" in res.context
        assert "stats" in res.context

        # Traceability rows structure
        traceability_rows = res.context["traceability_rows"]
        assert len(traceability_rows) >= 1
        first_row = traceability_rows[0]
        assert "assessment" in first_row
        assert "controls" in first_row
        assert "controls_count" in first_row
        assert "is_covered" in first_row

        # Stats dictionary
        stats = res.context["stats"]
        assert "total_hazards" in stats
        assert "total_mitigations" in stats
        assert "covered_hazards" in stats
        assert "uncovered_hazards" in stats
        assert "verification_coverage_pct" in stats

    def test_riskmanagement_risk_traceability_matrix_invalid_or_cross_tenant_plan(
        self, client_a, risk_management_plan_b
    ):
        url = reverse("quality:risk_traceability_matrix")
        assert client_a.get(f"{url}?plan=xyz").status_code == 404
        assert client_a.get(f"{url}?plan={risk_management_plan_b.pk}").status_code == 404

    def test_riskmanagement_risk_traceability_matrix_export_csv(
        self, client_a, risk_assessment_a, risk_control_measure_a, tenant_a, risk_management_plan_a
    ):
        # Create an uncovered hazard to verify 'NO CONTROLS' branch
        uncovered_hazard = RiskAssessment.objects.create(
            tenant=tenant_a,
            plan=risk_management_plan_a,
            hazard_category="energy_radiation",
            hazard_description="Electromagnetic interference from nearby MRI unit",
            foreseeable_sequence_of_events="High stray magnetic field distorts motor drive PWM signals.",
            hazardous_situation="Infusion pump ceases delivery without audible alert.",
            potential_harm="Temporary hypoglycemia due to under-infusion.",
            analysis_type="dfmea",
            initial_severity=3,
            initial_probability=2,
            lifecycle_status="open",
        )

        url = reverse("quality:risk_traceability_matrix_export")
        res = client_a.get(url)
        assert res.status_code == 200
        assert res["Content-Type"] == "text/csv"
        assert 'attachment; filename="risk_traceability_matrix.csv"' in res["Content-Disposition"]
        assert res["X-Content-Type-Options"] == "nosniff"

        csv_text = res.content.decode("utf-8")
        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)
        headers = rows[0]

        expected_headers = [
            "Plan",
            "Hazard Number",
            "Hazard Description",
            "Initial Risk Level",
            "Control Number",
            "Control Tier",
            "Control Title",
            "Design Input (Spec)",
            "Controlled Document (SOP/IFU)",
            "Design Verification (Protocol)",
            "Implementation Verified",
            "Effectiveness Verified",
            "Residual Risk Level",
        ]
        assert headers == expected_headers

        # Verify covered hazard row contains control info
        found_covered = any(
            row[1] == risk_assessment_a.number and row[4] == risk_control_measure_a.number
            for row in rows[1:]
        )
        assert found_covered

        # Verify uncovered hazard row contains 'NO CONTROLS'
        found_uncovered = any(
            row[1] == uncovered_hazard.number and row[4] == "NO CONTROLS"
            for row in rows[1:]
        )
        assert found_uncovered

    def test_riskmanagement_risk_traceability_matrix_export_cross_tenant_404(
        self, client_a, risk_management_plan_b
    ):
        url = reverse("quality:risk_traceability_matrix_export")
        assert client_a.get(f"{url}?plan={risk_management_plan_b.pk}").status_code == 404
        assert client_a.get(f"{url}?plan=bad_id").status_code == 404


# =====================================================================
# 6. Cross-Tenant Isolation & Authentication Guards
# =====================================================================


class TestRiskManagementSecurityAndAuth:
    def test_riskmanagement_cross_tenant_detail_views_404(
        self,
        client_a,
        risk_management_plan_b,
        risk_assessment_b,
        risk_control_measure_b,
        risk_review_record_b,
    ):
        # Client A cannot access Tenant B's objects in detail views
        assert client_a.get(
            reverse("quality:risk_management_plan_detail", kwargs={"pk": risk_management_plan_b.pk})
        ).status_code == 404

        assert client_a.get(
            reverse("quality:risk_assessment_detail", kwargs={"pk": risk_assessment_b.pk})
        ).status_code == 404

        assert client_a.get(
            reverse("quality:risk_control_measure_detail", kwargs={"pk": risk_control_measure_b.pk})
        ).status_code == 404

        assert client_a.get(
            reverse("quality:risk_review_record_detail", kwargs={"pk": risk_review_record_b.pk})
        ).status_code == 404

    def test_riskmanagement_cross_tenant_edit_views_404(
        self,
        client_a,
        risk_management_plan_b,
        risk_assessment_b,
        risk_control_measure_b,
        risk_review_record_b,
    ):
        # Client A cannot access Tenant B's objects in edit views
        assert client_a.get(
            reverse("quality:risk_management_plan_edit", kwargs={"pk": risk_management_plan_b.pk})
        ).status_code == 404

        assert client_a.get(
            reverse("quality:risk_assessment_edit", kwargs={"pk": risk_assessment_b.pk})
        ).status_code == 404

        assert client_a.get(
            reverse("quality:risk_control_measure_edit", kwargs={"pk": risk_control_measure_b.pk})
        ).status_code == 404

        assert client_a.get(
            reverse("quality:risk_review_record_edit", kwargs={"pk": risk_review_record_b.pk})
        ).status_code == 404

    def test_riskmanagement_cross_tenant_delete_views_404(
        self,
        client_a,
        risk_management_plan_b,
        risk_assessment_b,
        risk_control_measure_b,
        risk_review_record_b,
    ):
        # Client A cannot delete Tenant B's objects
        assert client_a.post(
            reverse("quality:risk_management_plan_delete", kwargs={"pk": risk_management_plan_b.pk})
        ).status_code == 404

        assert client_a.post(
            reverse("quality:risk_assessment_delete", kwargs={"pk": risk_assessment_b.pk})
        ).status_code == 404

        assert client_a.post(
            reverse("quality:risk_control_measure_delete", kwargs={"pk": risk_control_measure_b.pk})
        ).status_code == 404

        assert client_a.post(
            reverse("quality:risk_review_record_delete", kwargs={"pk": risk_review_record_b.pk})
        ).status_code == 404

    def test_riskmanagement_unauthenticated_access_redirects(
        self,
        client,
        risk_management_plan_a,
        risk_assessment_a,
        risk_control_measure_a,
        risk_review_record_a,
    ):
        # Anonymous client is redirected to login for all views
        urls = [
            reverse("quality:risk_management_plan_list"),
            reverse("quality:risk_management_plan_create"),
            reverse("quality:risk_management_plan_export"),
            reverse("quality:risk_management_plan_detail", kwargs={"pk": risk_management_plan_a.pk}),
            reverse("quality:risk_management_plan_edit", kwargs={"pk": risk_management_plan_a.pk}),
            reverse("quality:risk_assessment_list"),
            reverse("quality:risk_assessment_create"),
            reverse("quality:risk_assessment_export"),
            reverse("quality:risk_assessment_detail", kwargs={"pk": risk_assessment_a.pk}),
            reverse("quality:risk_assessment_edit", kwargs={"pk": risk_assessment_a.pk}),
            reverse("quality:risk_control_measure_list"),
            reverse("quality:risk_control_measure_create"),
            reverse("quality:risk_control_measure_export"),
            reverse("quality:risk_control_measure_detail", kwargs={"pk": risk_control_measure_a.pk}),
            reverse("quality:risk_control_measure_edit", kwargs={"pk": risk_control_measure_a.pk}),
            reverse("quality:risk_review_record_list"),
            reverse("quality:risk_review_record_create"),
            reverse("quality:risk_review_record_export"),
            reverse("quality:risk_review_record_detail", kwargs={"pk": risk_review_record_a.pk}),
            reverse("quality:risk_review_record_edit", kwargs={"pk": risk_review_record_a.pk}),
            reverse("quality:fmea_matrix"),
            reverse("quality:fmea_matrix_export"),
            reverse("quality:risk_traceability_matrix"),
            reverse("quality:risk_traceability_matrix_export"),
        ]
        for url in urls:
            res = client.get(url)
            assert res.status_code == 302
            assert "/accounts/login/" in res.url or "login" in res.url
