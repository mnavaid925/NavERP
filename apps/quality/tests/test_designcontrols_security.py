"""
Security, Multi-Tenant Isolation, and Adversarial Tests for Sub-module 12.2: Design Controls & Development.

Covers:
1. Multi-Tenant Data Isolation & Cross-Tenant IDOR:
   - Exhaustive IDOR sweeps: accessing Tenant B objects as Tenant A returns HTTP 404 across detail, edit, delete,
     advance-phase, lock-dhf, approve-gate, dhf dossier, and export endpoints.
   - Symmetric IDOR: Client B accessing Tenant A resources returns HTTP 404.
   - List views: assert 0 cross-tenant record leakage.
   - Export views: assert 0 cross-tenant record leakage in CSV outputs.
   - Cross-Tenant Foreign Key Injection: forging POST requests with Foreign Keys belonging to Tenant B
     (department, project, user_need_parent, lead_reviewer, independent_reviewer, primary_input, executed_by)
     is strictly rejected with validation errors via reject_foreign.
2. Authentication & Authorization:
   - Unauthenticated GET and POST requests to all 31 endpoints redirect to login (HTTP 302).
   - State-changing endpoints require POST (@require_POST); GET returns 405 Method Not Allowed.
   - Role authorization: design_project_lock_dhf and design_review_approve_gate require authorized role
     (project lead, quality lead, or tenant admin); standard member users get permission denied (302 redirect with error message).
3. 21 CFR § 820.30(j) Regulatory DHF Lock Integrity (Tamper-Resistance):
   - When project.dhf_locked=True, direct POST requests cannot:
     * advance phase
     * edit project or delete project
     * create design input, review, or verification under the locked project
     * edit or delete existing design inputs, reviews, or verifications
     * approve design reviews
4. Mass Assignment & Workflow State Bypasses:
   - DesignReviewForm rejects setting status="approved" directly via form.
   - DesignInputForm rejects setting status="verified" directly without a passing verification.
   - Mass assignment: attempts to inject tenant, number, created_at, updated_at, dhf_locked do not mutate instance.
5. 21 CFR § 820.30(e) Independent Reviewer Separation:
   - Rejects independent_reviewer == lead_reviewer.
   - Rejects independent_reviewer == project.project_lead.
   - Accepts valid independent reviewer with no direct responsibility.
6. CSV Formula Injection Defense:
   - Formula cells starting with =, +, -, @, \\t, \\r are escaped with leading single quote across all CSV export views.
7. Audit Trail Integrity:
   - AuditLog records written on create, update, delete, advance, lock_dhf, approve, verify, unverify.
8. Adversarial Chaos & System-Breaking:
   - Extreme inputs (10k chars, Unicode, special chars), invalid/malformed parameters (?page=-1, ?page=99999, ?project=junk).
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

from apps.core.models import AuditLog, OrgUnit
from apps.quality.forms.DesignControls.DesignInputs import DesignInputForm
from apps.quality.forms.DesignControls.DesignProjects import DesignProjectForm
from apps.quality.forms.DesignControls.DesignReviews import DesignReviewForm
from apps.quality.forms.DesignControls.DesignVerifications import DesignVerificationForm
from apps.quality.models.DesignControls.DesignInputs import DesignInput
from apps.quality.models.DesignControls.DesignProjects import DesignProject
from apps.quality.models.DesignControls.DesignReviews import DesignReview
from apps.quality.models.DesignControls.DesignVerifications import DesignVerification
from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument

User = get_user_model()
pytestmark = pytest.mark.django_db


# =====================================================================
# Fixtures & Helpers (Prefix: _designcontrols_*)
# =====================================================================


@pytest.fixture
def quality_department(db, tenant_a):
    return OrgUnit.objects.create(
        tenant=tenant_a,
        name="Quality Assurance",
        kind="department",
    )


@pytest.fixture
def quality_department_b(db, tenant_b):
    return OrgUnit.objects.create(
        tenant=tenant_b,
        name="Quality Assurance Globex",
        kind="department",
    )


@pytest.fixture
def design_review_a(db, tenant_a, admin_user, member_user, design_project_a):
    return DesignReview.objects.create(
        tenant=tenant_a,
        project=design_project_a,
        title="Phase 1 Design Planning Gate Review",
        review_stage="planning",
        review_date=timezone.now().date(),
        status="scheduled",
        lead_reviewer=admin_user,
        independent_reviewer=member_user,
    )


@pytest.fixture
def design_review_b(db, tenant_b, admin_b, design_project_b):
    user_indep = User.objects.create_user(
        email="indep_b@globex.com",
        username="indep_globex",
        password="TestPass123!",
        tenant=tenant_b,
    )
    return DesignReview.objects.create(
        tenant=tenant_b,
        project=design_project_b,
        title="Globex Phase 1 Review",
        review_stage="planning",
        review_date=timezone.now().date(),
        status="scheduled",
        lead_reviewer=admin_b,
        independent_reviewer=user_indep,
    )


@pytest.fixture
def _designcontrols_independent_user(db, tenant_a):
    return User.objects.create_user(
        email="auditor_dc@acme.com",
        username="auditor_dc_acme",
        password="TestPass123!",
        tenant=tenant_a,
        is_tenant_admin=False,
    )


def _designcontrols_get_messages(response):
    """Retrieve flashed messages from response."""
    if hasattr(response, "wsgi_request") and response.wsgi_request:
        return [m.message for m in get_messages(response.wsgi_request)]
    return []


def _designcontrols_audit_logs(obj, action=None):
    """Retrieve AuditLog rows written for obj."""
    ct = ContentType.objects.get_for_model(obj.__class__)
    qs = AuditLog.objects.filter(content_type=ct, object_id=obj.pk)
    if action:
        qs = qs.filter(action=action)
    return qs


def _designcontrols_parse_csv(response):
    """Parse CSV response into rows."""
    content = response.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    return list(reader)


# =====================================================================
# 1. Multi-Tenant Data Isolation & Cross-Tenant IDOR Sweeps
# =====================================================================


class TestDesignControlsCrossTenantIsolation:
    """Exhaustive sweeps asserting no cross-tenant object access or data leakage."""

    def test_designcontrols_project_detail_cross_tenant_idor_404(self, client_a, client_b, design_project_a, design_project_b):
        """Accessing Tenant B project detail as Tenant A returns 404, and vice versa."""
        res_a = client_a.get(reverse("quality:design_project_detail", kwargs={"pk": design_project_b.pk}))
        assert res_a.status_code == 404

        res_b = client_b.get(reverse("quality:design_project_detail", kwargs={"pk": design_project_a.pk}))
        assert res_b.status_code == 404

    def test_designcontrols_project_edit_cross_tenant_idor_404(self, client_a, client_b, design_project_a, design_project_b):
        """GET and POST to edit Tenant B project as Tenant A returns 404; database remains unmutated."""
        url_b = reverse("quality:design_project_edit", kwargs={"pk": design_project_b.pk})
        assert client_a.get(url_b).status_code == 404

        res_post = client_a.post(url_b, {"title": "Hostile Hijack Title"})
        assert res_post.status_code == 404

        design_project_b.refresh_from_db()
        assert design_project_b.title != "Hostile Hijack Title"

        # Symmetric check
        url_a = reverse("quality:design_project_edit", kwargs={"pk": design_project_a.pk})
        assert client_b.get(url_a).status_code == 404
        assert client_b.post(url_a, {"title": "Hostile Hijack Title"}).status_code == 404
        design_project_a.refresh_from_db()
        assert design_project_a.title != "Hostile Hijack Title"

    def test_designcontrols_project_delete_cross_tenant_idor_404(self, client_a, client_b, design_project_a, design_project_b):
        """POST to delete foreign project returns 404 and project is not deleted."""
        url_b = reverse("quality:design_project_delete", kwargs={"pk": design_project_b.pk})
        assert client_a.post(url_b).status_code == 404
        assert DesignProject.objects.filter(pk=design_project_b.pk).exists()

        url_a = reverse("quality:design_project_delete", kwargs={"pk": design_project_a.pk})
        assert client_b.post(url_a).status_code == 404
        assert DesignProject.objects.filter(pk=design_project_a.pk).exists()

    def test_designcontrols_project_advance_phase_cross_tenant_idor_404(self, client_a, client_b, design_project_a, design_project_b):
        """Advancing phase on foreign project returns 404 and phase is untouched."""
        url_b = reverse("quality:design_project_advance_phase", kwargs={"pk": design_project_b.pk})
        assert client_a.post(url_b).status_code == 404
        design_project_b.refresh_from_db()
        assert design_project_b.current_phase == "planning"

        url_a = reverse("quality:design_project_advance_phase", kwargs={"pk": design_project_a.pk})
        assert client_b.post(url_a).status_code == 404
        design_project_a.refresh_from_db()
        assert design_project_a.current_phase == "planning"

    def test_designcontrols_project_lock_dhf_cross_tenant_idor_404(self, client_a, client_b, design_project_a, design_project_b):
        """Locking DHF on foreign project returns 404 and dhf_locked remains False."""
        url_b = reverse("quality:design_project_lock_dhf", kwargs={"pk": design_project_b.pk})
        assert client_a.post(url_b).status_code == 404
        design_project_b.refresh_from_db()
        assert not design_project_b.dhf_locked

        url_a = reverse("quality:design_project_lock_dhf", kwargs={"pk": design_project_a.pk})
        assert client_b.post(url_a).status_code == 404
        design_project_a.refresh_from_db()
        assert not design_project_a.dhf_locked

    def test_designcontrols_project_dhf_dossier_cross_tenant_idor_404(self, client_a, client_b, design_project_a, design_project_b):
        """Accessing foreign project DHF dossier returns 404."""
        url_b = reverse("quality:design_project_dhf", kwargs={"pk": design_project_b.pk})
        assert client_a.get(url_b).status_code == 404

        url_a = reverse("quality:design_project_dhf", kwargs={"pk": design_project_a.pk})
        assert client_b.get(url_a).status_code == 404

    def test_designcontrols_project_dhf_export_cross_tenant_idor_404(self, client_a, client_b, design_project_a, design_project_b):
        """Exporting foreign project DHF index returns 404."""
        url_b = reverse("quality:design_project_dhf_export", kwargs={"pk": design_project_b.pk})
        assert client_a.get(url_b).status_code == 404

        url_a = reverse("quality:design_project_dhf_export", kwargs={"pk": design_project_a.pk})
        assert client_b.get(url_a).status_code == 404

    def test_designcontrols_input_detail_cross_tenant_idor_404(self, client_a, client_b, design_input_need, design_input_b):
        """Accessing foreign design input detail returns 404."""
        assert client_a.get(reverse("quality:design_input_detail", kwargs={"pk": design_input_b.pk})).status_code == 404
        assert client_b.get(reverse("quality:design_input_detail", kwargs={"pk": design_input_need.pk})).status_code == 404

    def test_designcontrols_input_edit_cross_tenant_idor_404(self, client_a, client_b, design_input_need, design_input_b):
        """Editing foreign design input returns 404 and does not modify the record."""
        url_b = reverse("quality:design_input_edit", kwargs={"pk": design_input_b.pk})
        assert client_a.get(url_b).status_code == 404
        assert client_a.post(url_b, {"title": "Hostile Hijack"}).status_code == 404
        design_input_b.refresh_from_db()
        assert design_input_b.title != "Hostile Hijack"

        url_a = reverse("quality:design_input_edit", kwargs={"pk": design_input_need.pk})
        assert client_b.get(url_a).status_code == 404
        assert client_b.post(url_a, {"title": "Hostile Hijack"}).status_code == 404
        design_input_need.refresh_from_db()
        assert design_input_need.title != "Hostile Hijack"

    def test_designcontrols_input_delete_cross_tenant_idor_404(self, client_a, client_b, design_input_need, design_input_b):
        """Deleting foreign design input returns 404 and record is retained."""
        assert client_a.post(reverse("quality:design_input_delete", kwargs={"pk": design_input_b.pk})).status_code == 404
        assert DesignInput.objects.filter(pk=design_input_b.pk).exists()

        assert client_b.post(reverse("quality:design_input_delete", kwargs={"pk": design_input_need.pk})).status_code == 404
        assert DesignInput.objects.filter(pk=design_input_need.pk).exists()

    def test_designcontrols_review_detail_cross_tenant_idor_404(self, client_a, client_b, design_review_a, design_review_b):
        """Accessing foreign design review detail returns 404."""
        assert client_a.get(reverse("quality:design_review_detail", kwargs={"pk": design_review_b.pk})).status_code == 404
        assert client_b.get(reverse("quality:design_review_detail", kwargs={"pk": design_review_a.pk})).status_code == 404

    def test_designcontrols_review_edit_cross_tenant_idor_404(self, client_a, client_b, design_review_a, design_review_b):
        """Editing foreign design review returns 404."""
        url_b = reverse("quality:design_review_edit", kwargs={"pk": design_review_b.pk})
        assert client_a.get(url_b).status_code == 404
        assert client_a.post(url_b, {"title": "Hostile Hijack Review"}).status_code == 404
        design_review_b.refresh_from_db()
        assert design_review_b.title != "Hostile Hijack Review"

        url_a = reverse("quality:design_review_edit", kwargs={"pk": design_review_a.pk})
        assert client_b.get(url_a).status_code == 404
        assert client_b.post(url_a, {"title": "Hostile Hijack Review"}).status_code == 404
        design_review_a.refresh_from_db()
        assert design_review_a.title != "Hostile Hijack Review"

    def test_designcontrols_review_delete_cross_tenant_idor_404(self, client_a, client_b, design_review_a, design_review_b):
        """Deleting foreign design review returns 404."""
        assert client_a.post(reverse("quality:design_review_delete", kwargs={"pk": design_review_b.pk})).status_code == 404
        assert DesignReview.objects.filter(pk=design_review_b.pk).exists()

        assert client_b.post(reverse("quality:design_review_delete", kwargs={"pk": design_review_a.pk})).status_code == 404
        assert DesignReview.objects.filter(pk=design_review_a.pk).exists()

    def test_designcontrols_review_approve_gate_cross_tenant_idor_404(self, client_a, client_b, design_review_a, design_review_b):
        """Approving stage gate on foreign design review returns 404."""
        url_b = reverse("quality:design_review_approve_gate", kwargs={"pk": design_review_b.pk})
        assert client_a.post(url_b).status_code == 404
        design_review_b.refresh_from_db()
        assert design_review_b.status == "scheduled"

        url_a = reverse("quality:design_review_approve_gate", kwargs={"pk": design_review_a.pk})
        assert client_b.post(url_a).status_code == 404
        design_review_a.refresh_from_db()
        assert design_review_a.status == "scheduled"

    def test_designcontrols_verification_detail_cross_tenant_idor_404(self, client_a, client_b, design_verification_a, design_verification_b):
        """Accessing foreign design verification protocol detail returns 404."""
        assert client_a.get(reverse("quality:design_verification_detail", kwargs={"pk": design_verification_b.pk})).status_code == 404
        assert client_b.get(reverse("quality:design_verification_detail", kwargs={"pk": design_verification_a.pk})).status_code == 404

    def test_designcontrols_verification_edit_cross_tenant_idor_404(self, client_a, client_b, design_verification_a, design_verification_b):
        """Editing foreign design verification returns 404."""
        url_b = reverse("quality:design_verification_edit", kwargs={"pk": design_verification_b.pk})
        assert client_a.get(url_b).status_code == 404
        assert client_a.post(url_b, {"title": "Hostile Hijack Protocol"}).status_code == 404
        design_verification_b.refresh_from_db()
        assert design_verification_b.title != "Hostile Hijack Protocol"

        url_a = reverse("quality:design_verification_edit", kwargs={"pk": design_verification_a.pk})
        assert client_b.get(url_a).status_code == 404
        assert client_b.post(url_a, {"title": "Hostile Hijack Protocol"}).status_code == 404
        design_verification_a.refresh_from_db()
        assert design_verification_a.title != "Hostile Hijack Protocol"

    def test_designcontrols_verification_delete_cross_tenant_idor_404(self, client_a, client_b, design_verification_a, design_verification_b):
        """Deleting foreign design verification returns 404."""
        assert client_a.post(reverse("quality:design_verification_delete", kwargs={"pk": design_verification_b.pk})).status_code == 404
        assert DesignVerification.objects.filter(pk=design_verification_b.pk).exists()

        assert client_b.post(reverse("quality:design_verification_delete", kwargs={"pk": design_verification_a.pk})).status_code == 404
        assert DesignVerification.objects.filter(pk=design_verification_a.pk).exists()

    def test_designcontrols_traceability_matrix_export_cross_tenant_idor_404(self, client_a, client_b, design_project_a, design_project_b):
        """Exporting matrix with foreign project ID returns 404."""
        url_a_foreign = reverse("quality:traceability_matrix_export") + f"?project={design_project_b.pk}"
        assert client_a.get(url_a_foreign).status_code == 404

        url_b_foreign = reverse("quality:traceability_matrix_export") + f"?project={design_project_a.pk}"
        assert client_b.get(url_b_foreign).status_code == 404

    def test_designcontrols_list_views_zero_cross_tenant_leakage(
        self, client_a, client_b, design_project_a, design_project_b,
        design_input_need, design_input_b,
        design_review_a, design_review_b,
        design_verification_a, design_verification_b
    ):
        """All list views for Tenant A render 0 records belonging to Tenant B, and vice-versa."""
        # 1. Projects
        res_proj_a = client_a.get(reverse("quality:design_project_list"))
        assert res_proj_a.status_code == 200
        pks_a = [p.pk for p in res_proj_a.context["projects"]]
        assert design_project_a.pk in pks_a
        assert design_project_b.pk not in pks_a

        res_proj_b = client_b.get(reverse("quality:design_project_list"))
        assert res_proj_b.status_code == 200
        pks_b = [p.pk for p in res_proj_b.context["projects"]]
        assert design_project_b.pk in pks_b
        assert design_project_a.pk not in pks_b

        # 2. Inputs
        res_inp_a = client_a.get(reverse("quality:design_input_list"))
        assert res_inp_a.status_code == 200
        inp_pks_a = [i.pk for i in res_inp_a.context["inputs"]]
        assert design_input_need.pk in inp_pks_a
        assert design_input_b.pk not in inp_pks_a

        res_inp_b = client_b.get(reverse("quality:design_input_list"))
        assert res_inp_b.status_code == 200
        inp_pks_b = [i.pk for i in res_inp_b.context["inputs"]]
        assert design_input_b.pk in inp_pks_b
        assert design_input_need.pk not in inp_pks_b

        # 3. Reviews
        res_rev_a = client_a.get(reverse("quality:design_review_list"))
        assert res_rev_a.status_code == 200
        rev_pks_a = [r.pk for r in res_rev_a.context["reviews"]]
        assert design_review_a.pk in rev_pks_a
        assert design_review_b.pk not in rev_pks_a

        res_rev_b = client_b.get(reverse("quality:design_review_list"))
        assert res_rev_b.status_code == 200
        rev_pks_b = [r.pk for r in res_rev_b.context["reviews"]]
        assert design_review_b.pk in rev_pks_b
        assert design_review_a.pk not in rev_pks_b

        # 4. Verifications
        res_ver_a = client_a.get(reverse("quality:design_verification_list"))
        assert res_ver_a.status_code == 200
        ver_pks_a = [v.pk for v in res_ver_a.context["verifications"]]
        assert design_verification_a.pk in ver_pks_a
        assert design_verification_b.pk not in ver_pks_a

        res_ver_b = client_b.get(reverse("quality:design_verification_list"))
        assert res_ver_b.status_code == 200
        ver_pks_b = [v.pk for v in res_ver_b.context["verifications"]]
        assert design_verification_b.pk in ver_pks_b
        assert design_verification_a.pk not in ver_pks_b

    def test_designcontrols_export_views_zero_cross_tenant_leakage(
        self, client_a, client_b, design_project_a, design_project_b,
        design_input_need, design_input_b,
        design_review_a, design_review_b,
        design_verification_a, design_verification_b
    ):
        """CSV exports for Tenant A contain 0 records belonging to Tenant B, and vice-versa."""
        # 1. Projects CSV
        res_proj_csv = client_a.get(reverse("quality:design_project_export"))
        assert res_proj_csv.status_code == 200
        csv_text_a = res_proj_csv.content.decode("utf-8")
        assert design_project_a.title in csv_text_a
        assert design_project_b.title not in csv_text_a

        # 2. Inputs CSV
        res_inp_csv = client_a.get(reverse("quality:design_input_export"))
        assert res_inp_csv.status_code == 200
        csv_text_inp_a = res_inp_csv.content.decode("utf-8")
        assert design_input_need.identifier in csv_text_inp_a
        assert design_input_b.identifier not in csv_text_inp_a

        # 3. Reviews CSV
        res_rev_csv = client_a.get(reverse("quality:design_review_export"))
        assert res_rev_csv.status_code == 200
        csv_text_rev_a = res_rev_csv.content.decode("utf-8")
        assert design_review_a.title in csv_text_rev_a
        assert design_review_b.title not in csv_text_rev_a

        # 4. Verifications CSV
        res_ver_csv = client_a.get(reverse("quality:design_verification_export"))
        assert res_ver_csv.status_code == 200
        csv_text_ver_a = res_ver_csv.content.decode("utf-8")
        assert design_verification_a.title in csv_text_ver_a
        assert design_verification_b.title not in csv_text_ver_a


# =====================================================================
# 2. Cross-Tenant Foreign Key Injection Defense (reject_foreign)
# =====================================================================


class TestDesignControlsCrossTenantFKInjection:
    """Ensure forging Foreign Key IDs belonging to a foreign tenant is strictly rejected."""

    def test_designcontrols_project_form_rejects_foreign_department(
        self, tenant_a, quality_department, quality_department_b, admin_user
    ):
        """DesignProjectForm excludes foreign department from queryset and rejects forged submission."""
        form = DesignProjectForm(tenant=tenant_a)
        dept_pks = list(form.fields["department"].queryset.values_list("pk", flat=True))
        assert quality_department.pk in dept_pks
        assert quality_department_b.pk not in dept_pks

        data = {
            "title": "Malicious Department Injection Project",
            "device_name": "TestDevice 100",
            "device_class": "class_ii",
            "regulatory_pathway": "510k",
            "intended_use": "Diagnostic testing.",
            "current_phase": "planning",
            "status": "draft",
            "project_lead": admin_user.pk,
            "quality_lead": admin_user.pk,
            "department": quality_department_b.pk,
        }
        bound = DesignProjectForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "department" in bound.errors or "__all__" in bound.errors

    def test_designcontrols_project_form_rejects_foreign_leads(
        self, tenant_a, quality_department, admin_user, admin_b
    ):
        """DesignProjectForm excludes foreign users from lead querysets and rejects foreign assignments."""
        form = DesignProjectForm(tenant=tenant_a)
        user_pks = list(form.fields["project_lead"].queryset.values_list("pk", flat=True))
        assert admin_user.pk in user_pks
        assert admin_b.pk not in user_pks

        # Inject foreign project lead
        data = {
            "title": "Malicious Lead Injection Project",
            "device_name": "TestDevice 200",
            "device_class": "class_ii",
            "regulatory_pathway": "510k",
            "intended_use": "Diagnostic testing.",
            "current_phase": "planning",
            "status": "draft",
            "project_lead": admin_b.pk,
            "quality_lead": admin_user.pk,
            "department": quality_department.pk,
        }
        bound = DesignProjectForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "project_lead" in bound.errors or "__all__" in bound.errors

    def test_designcontrols_input_form_rejects_foreign_project(
        self, tenant_a, design_project_a, design_project_b, admin_user
    ):
        """DesignInputForm rejects foreign design project binding."""
        form = DesignInputForm(tenant=tenant_a)
        assert design_project_a.pk in list(form.fields["project"].queryset.values_list("pk", flat=True))
        assert design_project_b.pk not in list(form.fields["project"].queryset.values_list("pk", flat=True))

        data = {
            "project": design_project_b.pk,
            "identifier": "INP-FOR-01",
            "title": "Cross Tenant Input Spec",
            "input_type": "functional",
            "priority": "major",
            "status": "draft",
            "owner": admin_user.pk,
            "acceptance_criteria": "Pass criteria.",
        }
        bound = DesignInputForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "project" in bound.errors or "__all__" in bound.errors

    def test_designcontrols_input_form_rejects_foreign_owner(
        self, tenant_a, design_project_a, admin_b
    ):
        """DesignInputForm rejects foreign user as owner."""
        data = {
            "project": design_project_a.pk,
            "identifier": "INP-FOR-02",
            "title": "Cross Tenant Owner Spec",
            "input_type": "functional",
            "priority": "major",
            "status": "draft",
            "owner": admin_b.pk,
            "acceptance_criteria": "Pass criteria.",
        }
        bound = DesignInputForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "owner" in bound.errors or "__all__" in bound.errors

    def test_designcontrols_input_form_rejects_foreign_parent_need(
        self, tenant_a, design_project_a, design_input_need, design_input_b, admin_user
    ):
        """DesignInputForm rejects linking to parent user need belonging to another tenant."""
        form = DesignInputForm(tenant=tenant_a)
        parent_pks = list(form.fields["user_need_parent"].queryset.values_list("pk", flat=True))
        assert design_input_need.pk in parent_pks
        assert design_input_b.pk not in parent_pks

        data = {
            "project": design_project_a.pk,
            "identifier": "DI-CHILD-01",
            "title": "Child Spec Under Foreign Parent",
            "input_type": "functional",
            "priority": "major",
            "status": "draft",
            "owner": admin_user.pk,
            "user_need_parent": design_input_b.pk,
            "acceptance_criteria": "Must align with parent need.",
        }
        bound = DesignInputForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "user_need_parent" in bound.errors or "__all__" in bound.errors

    def test_designcontrols_input_form_rejects_foreign_controlled_doc(
        self, tenant_a, design_project_a, quality_doc_b, admin_user
    ):
        """DesignInputForm rejects linking to controlled document belonging to another tenant."""
        form = DesignInputForm(tenant=tenant_a)
        doc_pks = list(form.fields["controlled_document"].queryset.values_list("pk", flat=True))
        assert quality_doc_b.pk not in doc_pks

        data = {
            "project": design_project_a.pk,
            "identifier": "DI-DOC-01",
            "title": "Spec Linked to Foreign Document",
            "input_type": "functional",
            "priority": "medium",
            "status": "draft",
            "owner": admin_user.pk,
            "controlled_document": quality_doc_b.pk,
            "acceptance_criteria": "Spec verified per doc.",
        }
        bound = DesignInputForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "controlled_document" in bound.errors or "__all__" in bound.errors

    def test_designcontrols_review_form_rejects_foreign_reviewers(
        self, tenant_a, design_project_a, admin_user, admin_b
    ):
        """DesignReviewForm rejects assigning foreign users as lead or independent reviewer."""
        form = DesignReviewForm(tenant=tenant_a)
        user_pks = list(form.fields["lead_reviewer"].queryset.values_list("pk", flat=True))
        assert admin_user.pk in user_pks
        assert admin_b.pk not in user_pks

        data = {
            "project": design_project_a.pk,
            "title": "Review with Foreign Reviewer",
            "review_stage": "planning",
            "review_date": timezone.now().date(),
            "status": "scheduled",
            "lead_reviewer": admin_b.pk,
            "independent_reviewer": admin_user.pk,
        }
        bound = DesignReviewForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "lead_reviewer" in bound.errors or "__all__" in bound.errors

    def test_designcontrols_verification_form_rejects_foreign_primary_input(
        self, tenant_a, design_project_a, design_input_spec, design_input_b, admin_user
    ):
        """DesignVerificationForm rejects foreign primary design input."""
        form = DesignVerificationForm(tenant=tenant_a)
        input_pks = list(form.fields["primary_input"].queryset.values_list("pk", flat=True))
        assert design_input_spec.pk in input_pks
        assert design_input_b.pk not in input_pks

        data = {
            "project": design_project_a.pk,
            "primary_input": design_input_b.pk,
            "title": "Test Protocol on Foreign Input",
            "activity_type": "verification",
            "status": "draft",
            "test_method": "lab_test",
            "sample_size": 5,
            "pass_fail_result": "pending",
            "acceptance_criteria": "Criteria.",
            "executed_by": admin_user.pk,
        }
        bound = DesignVerificationForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "primary_input" in bound.errors or "__all__" in bound.errors

    def test_designcontrols_verification_form_rejects_foreign_executed_by(
        self, tenant_a, design_project_a, design_input_spec, admin_b
    ):
        """DesignVerificationForm rejects foreign user as protocol executor."""
        data = {
            "project": design_project_a.pk,
            "primary_input": design_input_spec.pk,
            "title": "Test Protocol by Foreign User",
            "activity_type": "verification",
            "status": "draft",
            "test_method": "lab_test",
            "sample_size": 5,
            "pass_fail_result": "pending",
            "acceptance_criteria": "Criteria.",
            "executed_by": admin_b.pk,
        }
        bound = DesignVerificationForm(data=data, tenant=tenant_a)
        assert not bound.is_valid()
        assert "executed_by" in bound.errors or "__all__" in bound.errors


# =====================================================================
# 3. Authentication & Authorization Guards
# =====================================================================


class TestDesignControlsAuthenticationAndMethodGuards:
    """Validate login enforcement, @require_POST HTTP method restrictions, and role authorizations."""

    def test_designcontrols_unauthenticated_requests_redirect_to_login(
        self, client, design_project_a, design_input_need, design_review_a, design_verification_a
    ):
        """Unauthenticated GET and POST requests across all 31 endpoints redirect to login."""
        endpoints = [
            # Projects
            reverse("quality:design_project_list"),
            reverse("quality:design_project_export"),
            reverse("quality:design_project_create"),
            reverse("quality:design_project_detail", kwargs={"pk": design_project_a.pk}),
            reverse("quality:design_project_edit", kwargs={"pk": design_project_a.pk}),
            reverse("quality:design_project_delete", kwargs={"pk": design_project_a.pk}),
            reverse("quality:design_project_advance_phase", kwargs={"pk": design_project_a.pk}),
            reverse("quality:design_project_lock_dhf", kwargs={"pk": design_project_a.pk}),
            # Inputs
            reverse("quality:design_input_list"),
            reverse("quality:design_input_export"),
            reverse("quality:design_input_create"),
            reverse("quality:design_input_detail", kwargs={"pk": design_input_need.pk}),
            reverse("quality:design_input_edit", kwargs={"pk": design_input_need.pk}),
            reverse("quality:design_input_delete", kwargs={"pk": design_input_need.pk}),
            # Reviews
            reverse("quality:design_review_list"),
            reverse("quality:design_review_export"),
            reverse("quality:design_review_create"),
            reverse("quality:design_review_detail", kwargs={"pk": design_review_a.pk}),
            reverse("quality:design_review_edit", kwargs={"pk": design_review_a.pk}),
            reverse("quality:design_review_delete", kwargs={"pk": design_review_a.pk}),
            reverse("quality:design_review_approve_gate", kwargs={"pk": design_review_a.pk}),
            # Verifications
            reverse("quality:design_verification_list"),
            reverse("quality:design_verification_export"),
            reverse("quality:design_verification_create"),
            reverse("quality:design_verification_detail", kwargs={"pk": design_verification_a.pk}),
            reverse("quality:design_verification_edit", kwargs={"pk": design_verification_a.pk}),
            reverse("quality:design_verification_delete", kwargs={"pk": design_verification_a.pk}),
            # Traceability Matrix & DHF
            reverse("quality:traceability_matrix"),
            reverse("quality:traceability_matrix_export"),
            reverse("quality:design_project_dhf", kwargs={"pk": design_project_a.pk}),
            reverse("quality:design_project_dhf_export", kwargs={"pk": design_project_a.pk}),
        ]

        assert len(endpoints) == 31

        for url in endpoints:
            res_get = client.get(url)
            assert res_get.status_code == 302, f"Unauthenticated GET {url} did not redirect, got {res_get.status_code}"
            assert res_get.url.startswith("/login/") or reverse(settings.LOGIN_URL) in res_get.url or "/accounts/login/" in res_get.url

            res_post = client.post(url, {})
            assert res_post.status_code == 302, f"Unauthenticated POST {url} did not redirect, got {res_post.status_code}"

    def test_designcontrols_require_post_method_not_allowed_on_get(
        self, client_a, design_project_a, design_input_need, design_review_a, design_verification_a
    ):
        """State-changing actions protected by @require_POST return 405 Method Not Allowed on GET."""
        post_only_urls = [
            reverse("quality:design_project_delete", kwargs={"pk": design_project_a.pk}),
            reverse("quality:design_project_advance_phase", kwargs={"pk": design_project_a.pk}),
            reverse("quality:design_project_lock_dhf", kwargs={"pk": design_project_a.pk}),
            reverse("quality:design_input_delete", kwargs={"pk": design_input_need.pk}),
            reverse("quality:design_review_delete", kwargs={"pk": design_review_a.pk}),
            reverse("quality:design_review_approve_gate", kwargs={"pk": design_review_a.pk}),
            reverse("quality:design_verification_delete", kwargs={"pk": design_verification_a.pk}),
        ]

        for url in post_only_urls:
            res = client_a.get(url)
            assert res.status_code == 405, f"Expected 405 for GET {url}, got {res.status_code}"

    def test_designcontrols_lock_dhf_role_authorization_enforced(
        self, member_client, client_a, design_project_a
    ):
        """Only project lead, quality lead, or tenant admin can freeze/lock the DHF."""
        lock_url = reverse("quality:design_project_lock_dhf", kwargs={"pk": design_project_a.pk})

        # Standard non-admin, non-lead member user gets permission denied
        res_member = member_client.post(lock_url)
        assert res_member.status_code == 302
        msgs = _designcontrols_get_messages(res_member)
        assert any("permission denied" in m.lower() for m in msgs)
        design_project_a.refresh_from_db()
        assert not design_project_a.dhf_locked

        # Authorized admin/lead succeeds
        res_admin = client_a.post(lock_url)
        assert res_admin.status_code == 302
        design_project_a.refresh_from_db()
        assert design_project_a.dhf_locked
        msgs_admin = _designcontrols_get_messages(res_admin)
        assert any("frozen and locked" in m.lower() for m in msgs_admin)

    def test_designcontrols_lock_dhf_allowed_for_non_admin_project_lead(
        self, db, tenant_a, quality_department
    ):
        """A non-admin user designated as project_lead has authorization to lock DHF."""
        lead_user = User.objects.create_user(
            email="lead_only@acme.com",
            username="lead_only_user",
            password="TestPass123!",
            tenant=tenant_a,
            is_tenant_admin=False,
        )
        proj = DesignProject.objects.create(
            tenant=tenant_a,
            title="Lead Authorized Project",
            device_name="LeadDevice",
            device_class="class_ii",
            regulatory_pathway="510k",
            current_phase="commercial_closure",
            status="active",
            project_lead=lead_user,
            quality_lead=lead_user,
            department=quality_department,
            dhf_locked=False,
        )

        c = Client()
        c.login(username="lead_only_user", password="TestPass123!")
        lock_url = reverse("quality:design_project_lock_dhf", kwargs={"pk": proj.pk})
        res = c.post(lock_url)
        assert res.status_code == 302
        proj.refresh_from_db()
        assert proj.dhf_locked

    def test_designcontrols_approve_gate_role_authorization_enforced(
        self, member_client, client_a, design_review_a
    ):
        """Only lead reviewer, quality lead, or tenant admin can approve stage-gate reviews."""
        approve_url = reverse("quality:design_review_approve_gate", kwargs={"pk": design_review_a.pk})

        # Member user without review leadership gets permission denied
        res_member = member_client.post(approve_url)
        assert res_member.status_code == 302
        msgs = _designcontrols_get_messages(res_member)
        assert any("permission denied" in m.lower() for m in msgs)
        design_review_a.refresh_from_db()
        assert design_review_a.status == "scheduled"

        # Authorized admin/reviewer succeeds
        res_admin = client_a.post(approve_url)
        assert res_admin.status_code == 302
        design_review_a.refresh_from_db()
        assert design_review_a.status == "approved"
        assert design_review_a.action_items_resolved


# =====================================================================
# 4. 21 CFR § 820.30(j) Regulatory DHF Lock Integrity (Tamper-Resistance)
# =====================================================================


class TestDesignControlsRegulatoryDHFLockIntegrity:
    """
    Assert that when a Design History File (DHF) is locked, direct HTTP requests
    cannot modify or delete the project or any child design elements.
    """

    def test_designcontrols_locked_dhf_blocks_advance_phase(self, client_a, design_project_locked):
        """Advancing phase on a locked project is blocked."""
        curr_phase = design_project_locked.current_phase
        url = reverse("quality:design_project_advance_phase", kwargs={"pk": design_project_locked.pk})
        res = client_a.post(url)
        assert res.status_code == 302
        msgs = _designcontrols_get_messages(res)
        assert any("locked" in m.lower() for m in msgs)
        design_project_locked.refresh_from_db()
        assert design_project_locked.current_phase == curr_phase

    def test_designcontrols_locked_dhf_blocks_project_edit(self, client_a, design_project_locked):
        """Editing a project with a locked DHF is blocked."""
        orig_title = design_project_locked.title
        url = reverse("quality:design_project_edit", kwargs={"pk": design_project_locked.pk})
        res = client_a.post(url, {"title": "Attempted Tamper Title"})
        assert res.status_code == 302
        msgs = _designcontrols_get_messages(res)
        assert any("locked" in m.lower() for m in msgs)
        design_project_locked.refresh_from_db()
        assert design_project_locked.title == orig_title

    def test_designcontrols_locked_dhf_blocks_project_delete(self, client_a, design_project_locked):
        """Deleting a project with a locked DHF is blocked."""
        url = reverse("quality:design_project_delete", kwargs={"pk": design_project_locked.pk})
        res = client_a.post(url)
        assert res.status_code == 302
        msgs = _designcontrols_get_messages(res)
        assert any("locked" in m.lower() for m in msgs)
        assert DesignProject.objects.filter(pk=design_project_locked.pk).exists()

    def test_designcontrols_locked_dhf_blocks_input_creation(
        self, tenant_a, design_project_locked, admin_user
    ):
        """Creating design inputs under a locked project fails form validation."""
        data = {
            "project": design_project_locked.pk,
            "identifier": "DI-LOCKED-01",
            "title": "Post-Lock Input Addition",
            "input_type": "functional",
            "priority": "medium",
            "status": "draft",
            "owner": admin_user.pk,
            "acceptance_criteria": "Cannot add to locked DHF.",
        }
        form = DesignInputForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "project" in form.errors
        assert any("locked" in e.lower() for e in form.errors["project"])

    def test_designcontrols_locked_dhf_blocks_input_edit(
        self, client_a, tenant_a, design_project_locked, admin_user
    ):
        """Editing an existing design input under a locked project is blocked."""
        inp = DesignInput.objects.create(
            tenant=tenant_a,
            project=design_project_locked,
            identifier="DI-PRELOCK-01",
            title="Pre-Lock Input",
            input_type="functional",
            status="approved",
            owner=admin_user,
            acceptance_criteria="Pre-lock criteria.",
        )
        url = reverse("quality:design_input_edit", kwargs={"pk": inp.pk})
        res = client_a.post(url, {"title": "Tampered Pre-Lock Input"})
        assert res.status_code == 302
        msgs = _designcontrols_get_messages(res)
        assert any("locked" in m.lower() for m in msgs)
        inp.refresh_from_db()
        assert inp.title == "Pre-Lock Input"

    def test_designcontrols_locked_dhf_blocks_input_delete(
        self, client_a, tenant_a, design_project_locked, admin_user
    ):
        """Deleting a design input from a locked project is blocked."""
        inp = DesignInput.objects.create(
            tenant=tenant_a,
            project=design_project_locked,
            identifier="DI-PRELOCK-DEL",
            title="Pre-Lock Input For Deletion",
            input_type="functional",
            status="approved",
            owner=admin_user,
            acceptance_criteria="Pre-lock criteria.",
        )
        url = reverse("quality:design_input_delete", kwargs={"pk": inp.pk})
        res = client_a.post(url)
        assert res.status_code == 302
        msgs = _designcontrols_get_messages(res)
        assert any("locked" in m.lower() for m in msgs)
        assert DesignInput.objects.filter(pk=inp.pk).exists()

    def test_designcontrols_locked_dhf_blocks_review_creation(
        self, tenant_a, design_project_locked, admin_user, member_user
    ):
        """Creating design reviews under a locked project fails form validation."""
        data = {
            "project": design_project_locked.pk,
            "title": "Post-Lock Review Addition",
            "review_stage": "post_launch",
            "review_date": timezone.now().date(),
            "status": "scheduled",
            "lead_reviewer": admin_user.pk,
            "independent_reviewer": member_user.pk,
        }
        form = DesignReviewForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "project" in form.errors
        assert any("locked" in e.lower() for e in form.errors["project"])

    def test_designcontrols_locked_dhf_blocks_review_edit(
        self, client_a, tenant_a, design_project_locked, admin_user, member_user
    ):
        """Editing an existing design review under a locked project is blocked."""
        rev = DesignReview.objects.create(
            tenant=tenant_a,
            project=design_project_locked,
            title="Pre-Lock Review",
            review_stage="post_launch",
            review_date=timezone.now().date(),
            status="scheduled",
            lead_reviewer=admin_user,
            independent_reviewer=member_user,
        )
        url = reverse("quality:design_review_edit", kwargs={"pk": rev.pk})
        res = client_a.post(url, {"title": "Tampered Review Title"})
        assert res.status_code == 302
        msgs = _designcontrols_get_messages(res)
        assert any("locked" in m.lower() for m in msgs)
        rev.refresh_from_db()
        assert rev.title == "Pre-Lock Review"

    def test_designcontrols_locked_dhf_blocks_review_delete(
        self, client_a, tenant_a, design_project_locked, admin_user, member_user
    ):
        """Deleting a design review from a locked project is blocked."""
        rev = DesignReview.objects.create(
            tenant=tenant_a,
            project=design_project_locked,
            title="Pre-Lock Review Deletion",
            review_stage="post_launch",
            review_date=timezone.now().date(),
            status="scheduled",
            lead_reviewer=admin_user,
            independent_reviewer=member_user,
        )
        url = reverse("quality:design_review_delete", kwargs={"pk": rev.pk})
        res = client_a.post(url)
        assert res.status_code == 302
        msgs = _designcontrols_get_messages(res)
        assert any("locked" in m.lower() for m in msgs)
        assert DesignReview.objects.filter(pk=rev.pk).exists()

    def test_designcontrols_locked_dhf_blocks_review_approve_gate(
        self, client_a, tenant_a, design_project_locked, admin_user, member_user
    ):
        """Approving stage gate under a locked project is blocked."""
        rev = DesignReview.objects.create(
            tenant=tenant_a,
            project=design_project_locked,
            title="Pre-Lock Review Gate",
            review_stage="post_launch",
            review_date=timezone.now().date(),
            status="scheduled",
            lead_reviewer=admin_user,
            independent_reviewer=member_user,
        )
        url = reverse("quality:design_review_approve_gate", kwargs={"pk": rev.pk})
        res = client_a.post(url)
        assert res.status_code == 302
        msgs = _designcontrols_get_messages(res)
        assert any("locked" in m.lower() for m in msgs)
        rev.refresh_from_db()
        assert rev.status == "scheduled"

    def test_designcontrols_locked_dhf_blocks_verification_creation(
        self, tenant_a, design_project_locked, admin_user
    ):
        """Creating verification protocols under a locked project fails form validation."""
        inp = DesignInput.objects.create(
            tenant=tenant_a,
            project=design_project_locked,
            identifier="DI-VER-PRE",
            title="Input for Verification",
            input_type="functional",
            status="approved",
            owner=admin_user,
            acceptance_criteria="Pass.",
        )
        data = {
            "project": design_project_locked.pk,
            "primary_input": inp.pk,
            "title": "Post-Lock Verification Protocol",
            "activity_type": "verification",
            "status": "draft",
            "test_method": "lab_test",
            "sample_size": 3,
            "pass_fail_result": "pending",
            "acceptance_criteria": "Must conform to spec.",
            "executed_by": admin_user.pk,
        }
        form = DesignVerificationForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "project" in form.errors
        assert any("locked" in e.lower() for e in form.errors["project"])

    def test_designcontrols_locked_dhf_blocks_verification_edit(
        self, client_a, tenant_a, design_project_locked, admin_user
    ):
        """Editing an existing verification protocol under a locked project is blocked."""
        inp = DesignInput.objects.create(
            tenant=tenant_a,
            project=design_project_locked,
            identifier="DI-VER-EDIT",
            title="Input for Verification Edit",
            input_type="functional",
            status="approved",
            owner=admin_user,
            acceptance_criteria="Pass.",
        )
        ver = DesignVerification.objects.create(
            tenant=tenant_a,
            project=design_project_locked,
            primary_input=inp,
            title="Pre-Lock Verification",
            activity_type="verification",
            status="draft",
            test_method="lab_test",
            sample_size=3,
            pass_fail_result="pending",
            acceptance_criteria="Pass criteria.",
        )
        url = reverse("quality:design_verification_edit", kwargs={"pk": ver.pk})
        res = client_a.post(url, {"title": "Tampered Verification Protocol"})
        assert res.status_code == 302
        msgs = _designcontrols_get_messages(res)
        assert any("locked" in m.lower() for m in msgs)
        ver.refresh_from_db()
        assert ver.title == "Pre-Lock Verification"

    def test_designcontrols_locked_dhf_blocks_verification_delete(
        self, client_a, tenant_a, design_project_locked, admin_user
    ):
        """Deleting a verification protocol from a locked project is blocked."""
        inp = DesignInput.objects.create(
            tenant=tenant_a,
            project=design_project_locked,
            identifier="DI-VER-DEL",
            title="Input for Verification Delete",
            input_type="functional",
            status="approved",
            owner=admin_user,
            acceptance_criteria="Pass.",
        )
        ver = DesignVerification.objects.create(
            tenant=tenant_a,
            project=design_project_locked,
            primary_input=inp,
            title="Pre-Lock Verification For Delete",
            activity_type="verification",
            status="draft",
            test_method="lab_test",
            sample_size=3,
            pass_fail_result="pending",
            acceptance_criteria="Pass criteria.",
        )
        url = reverse("quality:design_verification_delete", kwargs={"pk": ver.pk})
        res = client_a.post(url)
        assert res.status_code == 302
        msgs = _designcontrols_get_messages(res)
        assert any("locked" in m.lower() for m in msgs)
        assert DesignVerification.objects.filter(pk=ver.pk).exists()


# =====================================================================
# 5. Mass Assignment & Workflow State Bypasses
# =====================================================================


class TestDesignControlsMassAssignmentAndWorkflowState:
    """Enforce strict workflow rules and mass-assignment defense."""

    def test_designcontrols_review_form_rejects_direct_status_approved(
        self, tenant_a, design_project_a, admin_user, member_user
    ):
        """Directly submitting status='approved' on review form is rejected without formal gate clearance."""
        data = {
            "project": design_project_a.pk,
            "title": "Attempted Direct Approval Review",
            "review_stage": "detailed_design",
            "review_date": timezone.now().date(),
            "status": "approved",
            "lead_reviewer": admin_user.pk,
            "independent_reviewer": member_user.pk,
        }
        form = DesignReviewForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "status" in form.errors
        assert any("requires formal gate clearance" in e.lower() for e in form.errors["status"])

    def test_designcontrols_input_form_rejects_direct_status_verified_without_passing_test(
        self, tenant_a, design_project_a, admin_user
    ):
        """Directly setting status='verified' on input form is rejected without a passing test."""
        data = {
            "project": design_project_a.pk,
            "identifier": "DI-UNVERIFIED-01",
            "title": "Prematurely Verified Input",
            "input_type": "functional",
            "priority": "major",
            "status": "verified",
            "owner": admin_user.pk,
            "acceptance_criteria": "Criteria.",
        }
        form = DesignInputForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "status" in form.errors
        assert any("cannot be marked as verified without" in e.lower() for e in form.errors["status"])

    def test_designcontrols_project_mass_assignment_defense(
        self, client_a, tenant_a, tenant_b, admin_user, quality_department
    ):
        """POSTing forged tenant, number, or dhf_locked does not mutate database model."""
        payload = {
            "title": "Mass Assignment Probe Project",
            "device_name": "ProbeDevice",
            "device_class": "class_ii",
            "regulatory_pathway": "510k",
            "intended_use": "Clinical evaluation.",
            "current_phase": "planning",
            "status": "active",
            "project_lead": admin_user.pk,
            "quality_lead": admin_user.pk,
            "department": quality_department.pk,
            # Forged system fields:
            "tenant": tenant_b.pk,
            "number": "DP-HIJACKED-999",
            "dhf_locked": True,
            "created_at": "2020-01-01T00:00:00Z",
        }
        res = client_a.post(reverse("quality:design_project_create"), payload)
        assert res.status_code == 302
        proj = DesignProject.objects.get(title="Mass Assignment Probe Project")
        assert proj.tenant == tenant_a
        assert proj.number.startswith("QDPL-")
        assert proj.number != "DP-HIJACKED-999"
        assert not proj.dhf_locked

    def test_designcontrols_input_mass_assignment_defense(
        self, client_a, tenant_a, tenant_b, design_project_a, admin_user
    ):
        """POSTing forged tenant or number in design input creation is neutralized."""
        payload = {
            "project": design_project_a.pk,
            "identifier": "DI-SAFE-01",
            "title": "Mass Assignment Probe Input",
            "input_type": "functional",
            "priority": "major",
            "status": "draft",
            "owner": admin_user.pk,
            "description": "Mass assignment safe description.",
            "acceptance_criteria": "Acceptance criteria.",
            "version": "1.0",
            # Forged system fields:
            "tenant": tenant_b.pk,
            "number": "INP-FORGED-888",
        }
        res = client_a.post(reverse("quality:design_input_create"), payload)
        assert res.status_code == 302
        inp = DesignInput.objects.get(identifier="DI-SAFE-01")
        assert inp.tenant == tenant_a
        assert inp.number.startswith("QINP-")
        assert inp.number != "INP-FORGED-888"


# =====================================================================
# 6. 21 CFR § 820.30(e) Independent Reviewer Separation
# =====================================================================


class TestDesignControlsIndependentReviewerSeparation:
    """Validate 21 CFR § 820.30(e) regulatory segregation of review responsibilities."""

    def test_designcontrols_review_form_rejects_lead_as_independent_reviewer(
        self, tenant_a, design_project_a, admin_user
    ):
        """Independent reviewer cannot be the same individual as the lead reviewer."""
        data = {
            "project": design_project_a.pk,
            "title": "Self-Review Conflict",
            "review_stage": "detailed_design",
            "review_date": timezone.now().date(),
            "status": "scheduled",
            "lead_reviewer": admin_user.pk,
            "independent_reviewer": admin_user.pk,
        }
        form = DesignReviewForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "independent_reviewer" in form.errors
        assert any("21 cfr § 820.30(e)" in e.lower() for e in form.errors["independent_reviewer"])

    def test_designcontrols_review_form_rejects_project_lead_as_independent_reviewer(
        self, tenant_a, design_project_a, admin_user, member_user
    ):
        """Project lead cannot serve as independent reviewer on the project (direct stage responsibility)."""
        # design_project_a has project_lead = admin_user
        assert design_project_a.project_lead == admin_user

        data = {
            "project": design_project_a.pk,
            "title": "Project Lead as Independent Reviewer Conflict",
            "review_stage": "detailed_design",
            "review_date": timezone.now().date(),
            "status": "scheduled",
            "lead_reviewer": member_user.pk,
            "independent_reviewer": admin_user.pk,
        }
        form = DesignReviewForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "independent_reviewer" in form.errors
        assert any("project lead cannot serve as the independent reviewer" in e.lower() for e in form.errors["independent_reviewer"])

    def test_designcontrols_review_form_accepts_valid_independent_reviewer(
        self, tenant_a, design_project_a, admin_user, member_user
    ):
        """Valid independent reviewer with separate responsibility is accepted."""
        data = {
            "project": design_project_a.pk,
            "title": "Compliant Independent Review",
            "review_stage": "detailed_design",
            "review_date": timezone.now().date(),
            "status": "scheduled",
            "lead_reviewer": admin_user.pk,
            "independent_reviewer": member_user.pk,
        }
        form = DesignReviewForm(data=data, tenant=tenant_a)
        assert form.is_valid(), form.errors


# =====================================================================
# 7. CSV Formula Injection Defense
# =====================================================================


class TestDesignControlsCSVFormulaInjectionDefense:
    """Ensure spreadsheet formulas starting with =, +, -, @, \\t, \\r are escaped with leading quote."""

    def test_designcontrols_project_export_csv_formula_sanitization(
        self, client_a, tenant_a, admin_user, quality_department
    ):
        """Formula cells in DesignProject export are neutralized with a leading single quote."""
        p = DesignProject.objects.create(
            tenant=tenant_a,
            title="=SUM(1+1)*cmd|' /C calc'!A0",
            device_name="@MacroInjected",
            device_class="class_ii",
            regulatory_pathway="510k",
            intended_use="+123456789",
            current_phase="planning",
            status="active",
            project_lead=admin_user,
            quality_lead=admin_user,
            department=quality_department,
        )

        res = client_a.get(reverse("quality:design_project_export"))
        assert res.status_code == 200
        rows = _designcontrols_parse_csv(res)
        found = False
        for row in rows:
            if p.number in row:
                found = True
                # Row indices: 1=Title, 2=Device Name
                assert row[1].startswith("'="), f"Title formula not escaped: {row[1]}"
                assert row[2].startswith("'@"), f"Device name formula not escaped: {row[2]}"
        assert found, "Created malicious project not found in CSV export"

    def test_designcontrols_input_export_csv_formula_sanitization(
        self, client_a, tenant_a, design_project_a, admin_user
    ):
        """Formula cells in DesignInput export are neutralized."""
        inp = DesignInput.objects.create(
            tenant=tenant_a,
            project=design_project_a,
            identifier="-INP-EVIL-01",
            title="=10+20",
            input_type="functional",
            priority="high",
            status="draft",
            owner=admin_user,
            acceptance_criteria="@HYPERLINK('http://attacker.com')",
        )

        res = client_a.get(reverse("quality:design_input_export"))
        assert res.status_code == 200
        rows = _designcontrols_parse_csv(res)
        found = False
        for row in rows:
            if inp.number in row:
                found = True
                # Row indices: 1=Identifier, 2=Title, 9=Acceptance Criteria
                assert row[1].startswith("'-"), f"Identifier formula not escaped: {row[1]}"
                assert row[2].startswith("'="), f"Title formula not escaped: {row[2]}"
                assert row[9].startswith("'@"), f"Acceptance criteria formula not escaped: {row[9]}"
        assert found

    def test_designcontrols_review_export_csv_formula_sanitization(
        self, client_a, tenant_a, design_project_a, admin_user, member_user
    ):
        """Formula cells in DesignReview export are neutralized."""
        rev = DesignReview.objects.create(
            tenant=tenant_a,
            project=design_project_a,
            title="+ReviewFormulaPayload",
            review_stage="planning",
            review_date=timezone.now().date(),
            status="scheduled",
            lead_reviewer=admin_user,
            independent_reviewer=member_user,
        )

        res = client_a.get(reverse("quality:design_review_export"))
        assert res.status_code == 200
        rows = _designcontrols_parse_csv(res)
        found = False
        for row in rows:
            if rev.number in row:
                found = True
                assert row[1].startswith("'+"), f"Review title formula not escaped: {row[1]}"
        assert found

    def test_designcontrols_verification_export_csv_formula_sanitization(
        self, client_a, tenant_a, design_project_a, design_input_spec, admin_user
    ):
        """Formula cells in DesignVerification export are neutralized."""
        ver = DesignVerification.objects.create(
            tenant=tenant_a,
            project=design_project_a,
            primary_input=design_input_spec,
            title="=cmd|' /C calc'!A0",
            activity_type="verification",
            status="draft",
            test_method="lab_test",
            sample_size=3,
            pass_fail_result="pending",
            acceptance_criteria="Pass.",
        )

        res = client_a.get(reverse("quality:design_verification_export"))
        assert res.status_code == 200
        rows = _designcontrols_parse_csv(res)
        found = False
        for row in rows:
            if ver.number in row:
                found = True
                assert row[1].startswith("'="), f"Verification title formula not escaped: {row[1]}"
        assert found

    def test_designcontrols_traceability_matrix_export_csv_formula_sanitization(
        self, client_a, tenant_a, design_project_a, admin_user
    ):
        """Formula cells in Traceability Matrix export are neutralized."""
        inp = DesignInput.objects.create(
            tenant=tenant_a,
            project=design_project_a,
            identifier="=FORMULA_INPUT",
            title="+FormulaTitle",
            input_type="functional",
            priority="high",
            status="draft",
            owner=admin_user,
            acceptance_criteria="@HYPERLINK",
        )

        url = reverse("quality:traceability_matrix_export") + f"?project={design_project_a.pk}"
        res = client_a.get(url)
        assert res.status_code == 200
        rows = _designcontrols_parse_csv(res)
        found = False
        for row in rows:
            if any("=FORMULA_INPUT" in cell for cell in row):
                found = True
                assert any(cell.startswith("'=") for cell in row)
        assert found

    def test_designcontrols_dhf_export_csv_formula_sanitization(
        self, client_a, tenant_a, design_project_a, admin_user
    ):
        """Formula cells in DHF Index export are neutralized."""
        DesignInput.objects.create(
            tenant=tenant_a,
            project=design_project_a,
            identifier="-MALICIOUS_DHF",
            title="=CMD|' /C notepad'!A0",
            input_type="functional",
            status="draft",
            owner=admin_user,
            acceptance_criteria="Criteria.",
        )

        url = reverse("quality:design_project_dhf_export", kwargs={"pk": design_project_a.pk})
        res = client_a.get(url)
        assert res.status_code == 200
        rows = _designcontrols_parse_csv(res)
        assert any(row[1].startswith("'-") or row[2].startswith("'=") for row in rows)


# =====================================================================
# 8. Audit Trail Integrity
# =====================================================================


class TestDesignControlsAuditTrailIntegrity:
    """Verify that every lifecycle event creates an immutable, verifiable AuditLog record."""

    def test_designcontrols_audit_log_written_on_project_lifecycle(
        self, client_a, tenant_a, admin_user, quality_department
    ):
        """AuditLog records are created on project create, update, advance, lock_dhf, and delete."""
        # 1. Create
        create_payload = {
            "title": "Audit Trail Trace Project",
            "device_name": "AuditDevice",
            "device_class": "class_ii",
            "regulatory_pathway": "510k",
            "intended_use": "Traceability test.",
            "current_phase": "planning",
            "status": "draft",
            "project_lead": admin_user.pk,
            "quality_lead": admin_user.pk,
            "department": quality_department.pk,
        }
        res_create = client_a.post(reverse("quality:design_project_create"), create_payload)
        assert res_create.status_code == 302
        proj = DesignProject.objects.get(title="Audit Trail Trace Project")
        assert _designcontrols_audit_logs(proj, "create").exists()

        # 2. Update
        edit_payload = create_payload.copy()
        edit_payload["title"] = "Audit Trail Updated Project"
        res_edit = client_a.post(reverse("quality:design_project_edit", kwargs={"pk": proj.pk}), edit_payload)
        assert res_edit.status_code == 302
        assert _designcontrols_audit_logs(proj, "update").exists()

        # 3. Advance
        res_advance = client_a.post(reverse("quality:design_project_advance_phase", kwargs={"pk": proj.pk}))
        assert res_advance.status_code == 302
        assert _designcontrols_audit_logs(proj, "advance").exists()

        # 4. Lock DHF
        res_lock = client_a.post(reverse("quality:design_project_lock_dhf", kwargs={"pk": proj.pk}))
        assert res_lock.status_code == 302
        assert _designcontrols_audit_logs(proj, "lock_dhf").exists()

        # 5. Delete (unlock first in memory for test)
        proj.dhf_locked = False
        proj.save(update_fields=["dhf_locked"])
        proj_pk = proj.pk
        res_del = client_a.post(reverse("quality:design_project_delete", kwargs={"pk": proj_pk}))
        assert res_del.status_code == 302
        del_logs = AuditLog.objects.filter(
            content_type=ContentType.objects.get_for_model(DesignProject),
            object_id=proj_pk,
            action="delete",
        )
        assert del_logs.exists()

    def test_designcontrols_audit_log_written_on_input_lifecycle(
        self, client_a, tenant_a, design_project_a, admin_user
    ):
        """AuditLog records are created on design input create, update, and delete."""
        create_payload = {
            "project": design_project_a.pk,
            "identifier": "DI-AUDIT-01",
            "title": "Audit Input Record",
            "input_type": "functional",
            "priority": "major",
            "status": "draft",
            "owner": admin_user.pk,
            "description": "Audit input description.",
            "acceptance_criteria": "Audit criteria.",
            "version": "1.0",
        }
        res_create = client_a.post(reverse("quality:design_input_create"), create_payload)
        assert res_create.status_code == 302
        inp = DesignInput.objects.get(identifier="DI-AUDIT-01")
        assert _designcontrols_audit_logs(inp, "create").exists()

        # Update
        edit_payload = create_payload.copy()
        edit_payload["title"] = "Audit Input Modified"
        res_edit = client_a.post(reverse("quality:design_input_edit", kwargs={"pk": inp.pk}), edit_payload)
        assert res_edit.status_code == 302
        assert _designcontrols_audit_logs(inp, "update").exists()

        # Delete
        inp_pk = inp.pk
        res_del = client_a.post(reverse("quality:design_input_delete", kwargs={"pk": inp_pk}))
        assert res_del.status_code == 302
        del_logs = AuditLog.objects.filter(
            content_type=ContentType.objects.get_for_model(DesignInput),
            object_id=inp_pk,
            action="delete",
        )
        assert del_logs.exists()

    def test_designcontrols_audit_log_written_on_review_lifecycle(
        self, client_a, tenant_a, design_project_a, admin_user, member_user
    ):
        """AuditLog records are created on review create, update, approve, and delete."""
        create_payload = {
            "project": design_project_a.pk,
            "title": "Audit Review Record",
            "review_stage": "concept",
            "review_date": timezone.now().date(),
            "status": "scheduled",
            "lead_reviewer": admin_user.pk,
            "independent_reviewer": member_user.pk,
        }
        res_create = client_a.post(reverse("quality:design_review_create"), create_payload)
        assert res_create.status_code == 302
        rev = DesignReview.objects.get(title="Audit Review Record")
        assert _designcontrols_audit_logs(rev, "create").exists()

        # Update
        edit_payload = create_payload.copy()
        edit_payload["title"] = "Audit Review Modified"
        res_edit = client_a.post(reverse("quality:design_review_edit", kwargs={"pk": rev.pk}), edit_payload)
        assert res_edit.status_code == 302
        assert _designcontrols_audit_logs(rev, "update").exists()

        # Approve
        res_appr = client_a.post(reverse("quality:design_review_approve_gate", kwargs={"pk": rev.pk}))
        assert res_appr.status_code == 302
        assert _designcontrols_audit_logs(rev, "approve").exists()

        # Delete
        rev_pk = rev.pk
        res_del = client_a.post(reverse("quality:design_review_delete", kwargs={"pk": rev_pk}))
        assert res_del.status_code == 302
        del_logs = AuditLog.objects.filter(
            content_type=ContentType.objects.get_for_model(DesignReview),
            object_id=rev_pk,
            action="delete",
        )
        assert del_logs.exists()

    def test_designcontrols_audit_log_written_on_verification_and_auto_verify(
        self, client_a, tenant_a, design_project_a, design_input_spec, admin_user
    ):
        """AuditLog records are created on verification lifecycle and primary input auto-verify/unverify."""
        create_payload = {
            "project": design_project_a.pk,
            "primary_input": design_input_spec.pk,
            "title": "Audit Verification Protocol",
            "activity_type": "verification",
            "status": "passed",
            "test_method": "lab_test",
            "sample_size": 5,
            "pass_fail_result": "pass",
            "acceptance_criteria": "All units pass.",
            "executed_by": admin_user.pk,
        }
        res_create = client_a.post(reverse("quality:design_verification_create"), create_payload)
        assert res_create.status_code == 302
        ver = DesignVerification.objects.get(title="Audit Verification Protocol")
        assert _designcontrols_audit_logs(ver, "create").exists()

        # Primary input must have been auto-verified and logged
        design_input_spec.refresh_from_db()
        assert design_input_spec.status == "verified"
        assert _designcontrols_audit_logs(design_input_spec, "verify").exists()

        # Update verification to failed
        edit_payload = create_payload.copy()
        edit_payload["pass_fail_result"] = "fail"
        edit_payload["status"] = "failed"
        res_edit = client_a.post(reverse("quality:design_verification_edit", kwargs={"pk": ver.pk}), edit_payload)
        assert res_edit.status_code == 302
        assert _designcontrols_audit_logs(ver, "update").exists()

        # Primary input must be unverified and logged
        design_input_spec.refresh_from_db()
        assert design_input_spec.status == "approved"
        assert _designcontrols_audit_logs(design_input_spec, "unverify").exists()

        # Delete
        ver_pk = ver.pk
        res_del = client_a.post(reverse("quality:design_verification_delete", kwargs={"pk": ver_pk}))
        assert res_del.status_code == 302
        del_logs = AuditLog.objects.filter(
            content_type=ContentType.objects.get_for_model(DesignVerification),
            object_id=ver_pk,
            action="delete",
        )
        assert del_logs.exists()


# =====================================================================
# 9. Adversarial Chaos & System-Breaking Testing
# =====================================================================


class TestDesignControlsAdversarialChaos:
    """Stress tests and boundary condition attacks against Design Controls."""

    def test_designcontrols_adversarial_extreme_payload_lengths(
        self, client_a, tenant_a, design_project_a, admin_user, quality_department
    ):
        """10,000 character strings in text fields do not cause unhandled 500 server crashes."""
        huge_text = "A" * 10000

        # Create input with massive acceptance criteria and description
        inp_data = {
            "project": design_project_a.pk,
            "identifier": "DI-HUGE-01",
            "title": "Massive Text Input",
            "input_type": "functional",
            "priority": "major",
            "status": "draft",
            "owner": admin_user.pk,
            "description": huge_text,
            "acceptance_criteria": huge_text,
            "rationale": huge_text,
            "version": "1.0",
        }
        res_inp = client_a.post(reverse("quality:design_input_create"), inp_data)
        assert res_inp.status_code == 302
        saved_inp = DesignInput.objects.get(identifier="DI-HUGE-01")
        assert len(saved_inp.acceptance_criteria) == 10000

        # Massive CharField title is cleanly rejected by form validation without 500
        proj_data = {
            "title": huge_text,
            "device_name": "Device 99",
            "device_class": "class_ii",
            "regulatory_pathway": "510k",
            "intended_use": "Short.",
            "current_phase": "planning",
            "status": "draft",
            "project_lead": admin_user.pk,
            "quality_lead": admin_user.pk,
            "department": quality_department.pk,
        }
        res_proj = client_a.post(reverse("quality:design_project_create"), proj_data)
        assert res_proj.status_code == 200  # Returns form errors page, not 500

    def test_designcontrols_adversarial_unicode_and_script_injection(
        self, client_a, tenant_a, design_project_a, admin_user
    ):
        """Emoji, Arabic text, XSS payloads, and SQL syntax render safely without crashing."""
        chaos_strings = [
            "<script>alert('XSS')</script>",
            "' OR '1'='1' --",
            "SELECT * FROM accounts_user; DROP TABLE apps_quality_designproject;",
            "🚀🔥💯 Non-Latin: \u0627\u0644\u062c\u0648\u062f\u0629 \u4e2d\u6587 \u0420\u0443\u0441\u0441\u043a\u0438\u0439",
            "ZeroWidth:\u200b\u200c\u200d\ufeff",
        ]

        for idx, text in enumerate(chaos_strings):
            inp = DesignInput.objects.create(
                tenant=tenant_a,
                project=design_project_a,
                identifier=f"CHAOS-{idx}",
                title=f"Chaos Title {text[:20]}",
                input_type="functional",
                priority="high",
                status="draft",
                owner=admin_user,
                description=text,
                acceptance_criteria=text,
            )
            # Detail view renders cleanly
            res_detail = client_a.get(reverse("quality:design_input_detail", kwargs={"pk": inp.pk}))
            assert res_detail.status_code == 200

            # List view renders cleanly
            res_list = client_a.get(reverse("quality:design_input_list"))
            assert res_list.status_code == 200

            # Traceability Matrix renders cleanly
            res_matrix = client_a.get(reverse("quality:traceability_matrix") + f"?project={design_project_a.pk}")
            assert res_matrix.status_code == 200

    def test_designcontrols_adversarial_invalid_pagination(self, client_a):
        """Malformed, negative, float, and astronomical page parameters return 200 without 500 error."""
        malformed_pages = ["-1", "0", "9999999", "abc", "NaN", "1.5", "' OR 1=1"]
        list_urls = [
            reverse("quality:design_project_list"),
            reverse("quality:design_input_list"),
            reverse("quality:design_review_list"),
            reverse("quality:design_verification_list"),
        ]

        for url in list_urls:
            for page in malformed_pages:
                res = client_a.get(f"{url}?page={page}")
                assert res.status_code == 200, f"Malformed page '{page}' at {url} returned {res.status_code}"

    def test_designcontrols_adversarial_invalid_filter_parameters(self, client_a):
        """Junk and SQL injection filter parameters on list and matrix views return 200 safely."""
        chaos_filters = [
            ("project", "junk_string"),
            ("project", "-999"),
            ("project", "99999999"),
            ("device_class", "nonexistent_class"),
            ("phase", "invalid_phase"),
            ("status", "' OR 1=1 --"),
            ("q", "<script>alert(1)</script>"),
            ("q", "%" * 50),
        ]

        list_urls = [
            reverse("quality:design_project_list"),
            reverse("quality:design_input_list"),
            reverse("quality:design_review_list"),
            reverse("quality:design_verification_list"),
            reverse("quality:traceability_matrix"),
        ]

        for url in list_urls:
            for key, val in chaos_filters:
                res = client_a.get(f"{url}?{key}={val}")
                assert res.status_code == 200, f"Chaos filter ?{key}={val} at {url} returned {res.status_code}"

    def test_designcontrols_adversarial_traceability_matrix_inaccessible_project(
        self, client_a, design_project_b
    ):
        """Requesting matrix with foreign or nonexistent project ID sets warning and gracefully defaults."""
        url = reverse("quality:traceability_matrix") + f"?project={design_project_b.pk}"
        res = client_a.get(url)
        assert res.status_code == 200
        msgs = _designcontrols_get_messages(res)
        assert any("inaccessible" in m.lower() or "not found" in m.lower() for m in msgs)
