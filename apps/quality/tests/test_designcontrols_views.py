"""
Unit and integration tests for apps/quality views (Sub-module 12.2: Design Controls & Development).

Covers all views, routes, filters, context keys, status transitions, permissions, and CSV exports:
1. DesignProject views:
   - list (filters, search ?q=, pagination, junk params)
   - export (CSV output, headers, formula sanitization)
   - create (GET, POST valid, redirect)
   - detail (context keys: project, inputs, reviews, verifications, input_stats, review_stats, verification_stats)
   - edit (GET, POST valid, redirect, locked DHF rejection)
   - delete (POST valid, locked DHF rejection, GET rejection)
   - advance_phase (POST sequential phase transitions, locked DHF rejection, GET rejection)
   - lock_dhf (POST authorization check for leads/admins, locked project handling, GET rejection)
2. DesignInput views:
   - list (filters, search ?q=, pagination, junk params)
   - export (CSV output, headers, formula sanitization)
   - create (GET with ?project= prefill, POST valid, redirect)
   - detail (context keys: input_obj, verifications, derived_inputs)
   - edit (GET, POST valid, locked project rejection)
   - delete (POST valid, locked project rejection, GET rejection)
3. DesignReview views:
   - list (filters, search ?q=, pagination)
   - export (CSV output, headers)
   - create (GET with ?project= prefill, POST valid, redirect)
   - detail (context key: review)
   - edit (GET, POST valid, locked project rejection)
   - delete (POST valid, locked project rejection, GET rejection)
   - approve_gate (POST authorization check, locked project rejection, GET rejection)
4. DesignVerification views:
   - list (filters, search ?q=, pagination)
   - export (CSV output, headers)
   - create (GET with ?input= / ?project= prefill, POST valid)
   - detail (context key: verification)
   - edit (GET, POST valid, locked project rejection)
   - delete (POST valid, locked project rejection, GET rejection)
   - Auto-verification behavior: creating/editing passing verification updates primary_input.status to "verified"
     and writes audit log; editing to fail or deleting recalculates primary_input.status.
5. TraceabilityMatrix & DHF Dossier views:
   - traceability_matrix (project selector, matrix_rows, coverage_percentage, gap_count, warning on invalid project ID)
   - traceability_matrix_export (CSV export)
   - design_project_dhf (dhf dossier, sections: inputs, reviews, verifications, specifications, transfer_gate_cleared, is_dhf_complete)
   - design_project_dhf_export (DHF index CSV)
6. Assert rendered content (titles, badges, table rows) and verify no template comment leaks ({# or {% comment).
7. Cross-tenant isolation & authentication guards.
"""

import csv
import io
from datetime import timedelta
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
    DesignReview,
    DesignVerification,
)

pytestmark = pytest.mark.django_db


# =====================================================================
# Fixtures and Helpers (Prefix: _designcontrols_*)
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
def _designcontrols_secondary_user(db, tenant_a):
    return User.objects.create_user(
        email="lead2@acme.com",
        username="lead2_acme",
        password="TestPass123!",
        tenant=tenant_a,
        is_tenant_admin=False,
    )


def _designcontrols_get_messages(response):
    """Extract message strings from response wsgi_request."""
    if hasattr(response, "wsgi_request"):
        return [m.message for m in get_messages(response.wsgi_request)]
    return []


def _designcontrols_audit_logs(obj, action=None):
    """Retrieve audit log rows written for obj."""
    ct = ContentType.objects.get_for_model(obj.__class__)
    qs = AuditLog.objects.filter(content_type=ct, object_id=obj.pk)
    if action:
        qs = qs.filter(action=action)
    return qs


def _designcontrols_assert_no_comment_leaks(response):
    """Assert response HTML contains no template comment fragments."""
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "{#" not in content, "Found unrendered '{#' comment leak in HTML template"
    assert "{% comment" not in content, "Found unrendered '{% comment' leak in HTML template"


# =====================================================================
# 1. DesignProject Views
# =====================================================================


class TestDesignProjectViews:
    def test_designcontrols_project_list_get_success(self, client_a, design_project_a):
        url = reverse("quality:design_project_list")
        res = client_a.get(url)
        assert res.status_code == 200
        _designcontrols_assert_no_comment_leaks(res)

        # Context keys
        assert "projects" in res.context
        assert "device_class_choices" in res.context
        assert "phase_choices" in res.context
        assert "status_choices" in res.context
        assert res.context["total_count"] >= 1
        assert "active_count" in res.context
        assert "locked_count" in res.context

        # Rendered content
        content = res.content.decode("utf-8")
        assert design_project_a.number in content
        assert design_project_a.title in content
        assert design_project_a.device_name in content

    def test_designcontrols_project_list_filters_and_search(self, client_a, design_project_a, design_project_locked):
        url = reverse("quality:design_project_list")

        # Search query by number
        res_q = client_a.get(f"{url}?q={design_project_a.number}")
        assert res_q.status_code == 200
        projects_q = list(res_q.context["projects"])
        assert design_project_a in projects_q
        assert design_project_locked not in projects_q

        # Search query by device_name
        res_dev = client_a.get(f"{url}?q={design_project_a.device_name[:8]}")
        assert res_dev.status_code == 200
        assert design_project_a in list(res_dev.context["projects"])

        # Filter by device_class
        res_class = client_a.get(f"{url}?device_class=class_ii")
        assert res_class.status_code == 200
        assert design_project_a in list(res_class.context["projects"])

        # Filter by phase
        res_phase = client_a.get(f"{url}?phase=planning")
        assert res_phase.status_code == 200
        assert design_project_a in list(res_phase.context["projects"])
        assert design_project_locked not in list(res_phase.context["projects"])

        # Filter by status
        res_status = client_a.get(f"{url}?status=completed")
        assert res_status.status_code == 200
        assert design_project_locked in list(res_status.context["projects"])
        assert design_project_a not in list(res_status.context["projects"])

    def test_designcontrols_project_list_pagination_and_junk(self, client_a, design_project_a):
        url = reverse("quality:design_project_list")

        # Valid page 1
        res1 = client_a.get(f"{url}?page=1")
        assert res1.status_code == 200

        # Out-of-range page returns last page
        res_far = client_a.get(f"{url}?page=9999")
        assert res_far.status_code == 200

        # Junk non-numeric page returns page 1
        res_junk = client_a.get(f"{url}?page=invalid_string&device_class=nonexistent")
        assert res_junk.status_code == 200

    def test_designcontrols_project_export_csv(self, client_a, tenant_a, admin_user, quality_department):
        # Create a project with formula-injection string
        p_formula = DesignProject.objects.create(
            tenant=tenant_a,
            title="=SUM(A1:A10)",
            device_name="+MaliciousDevice",
            device_class="class_ii",
            regulatory_pathway="510k",
            intended_use="Clinical testing",
            current_phase="planning",
            status="active",
            project_lead=admin_user,
            quality_lead=admin_user,
            department=quality_department,
        )

        url = reverse("quality:design_project_export")
        res = client_a.get(url)
        assert res.status_code == 200
        assert res["Content-Type"] == "text/csv"
        assert 'attachment; filename="design_projects.csv"' in res["Content-Disposition"]
        assert res["X-Content-Type-Options"] == "nosniff"

        csv_text = res.content.decode("utf-8")
        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)
        headers = rows[0]

        expected_headers = [
            "Number", "Title", "Device Name", "Device Class", "Regulatory Pathway",
            "Phase", "Status", "Project Lead", "Quality Lead", "Department", "DHF Locked"
        ]
        assert headers == expected_headers

        # Verify formula sanitization (leading quote added)
        found_sanitized = False
        for row in rows[1:]:
            if row[0] == p_formula.number:
                assert row[1] == "'=SUM(A1:A10)"
                assert row[2] == "'+MaliciousDevice"
                found_sanitized = True
        assert found_sanitized

    def test_designcontrols_project_create_get(self, client_a):
        url = reverse("quality:design_project_create")
        res = client_a.get(url)
        assert res.status_code == 200
        _designcontrols_assert_no_comment_leaks(res)
        assert "form" in res.context
        assert res.context["action"] == "Create"

    def test_designcontrols_project_create_post_valid(self, client_a, tenant_a, admin_user, quality_department):
        url = reverse("quality:design_project_create")
        payload = {
            "title": "Smart Infusion Monitor X",
            "device_name": "InfuseSense 100",
            "device_class": "class_ii",
            "regulatory_pathway": "510k",
            "intended_use": "Infusion rate continuous monitoring.",
            "current_phase": "planning",
            "status": "active",
            "project_lead": admin_user.pk,
            "quality_lead": admin_user.pk,
            "department": quality_department.pk,
            "target_completion_date": "2027-06-30",
            "dhf_location": "Vault-QA-01",
            "description": "Smart sensor integration.",
        }
        res = client_a.post(url, data=payload)
        new_project = DesignProject.objects.filter(tenant=tenant_a, title="Smart Infusion Monitor X").first()
        assert new_project is not None
        assert res.status_code == 302
        assert res.url == reverse("quality:design_project_detail", kwargs={"pk": new_project.pk})

        # Verify audit log
        audit = _designcontrols_audit_logs(new_project, action="create")
        assert audit.exists()

    def test_designcontrols_project_create_post_invalid(self, client_a):
        url = reverse("quality:design_project_create")
        # Missing required title, device_name, intended_use, etc.
        res = client_a.post(url, data={})
        assert res.status_code == 200
        assert res.context["form"].errors
        _designcontrols_assert_no_comment_leaks(res)

    def test_designcontrols_project_detail(self, client_a, design_project_a, design_input_need, design_review_a, design_verification_a):
        url = reverse("quality:design_project_detail", kwargs={"pk": design_project_a.pk})
        res = client_a.get(url)
        assert res.status_code == 200
        _designcontrols_assert_no_comment_leaks(res)

        # Context keys
        assert res.context["project"] == design_project_a
        assert design_input_need in list(res.context["inputs"])
        assert design_review_a in list(res.context["reviews"])
        assert design_verification_a in list(res.context["verifications"])
        assert res.context["input_stats"]["total"] >= 1
        assert res.context["review_stats"]["total"] >= 1
        assert res.context["verification_stats"]["total"] >= 1

        # Rendered badges and text
        content = res.content.decode("utf-8")
        assert design_project_a.number in content
        assert design_project_a.device_name in content
        assert "Advance Phase" in content
        assert "Lock DHF" in content

    def test_designcontrols_project_edit_get(self, client_a, design_project_a):
        url = reverse("quality:design_project_edit", kwargs={"pk": design_project_a.pk})
        res = client_a.get(url)
        assert res.status_code == 200
        _designcontrols_assert_no_comment_leaks(res)
        assert "form" in res.context
        assert res.context["project"] == design_project_a

    def test_designcontrols_project_edit_post_valid(self, client_a, design_project_a, admin_user, quality_department):
        url = reverse("quality:design_project_edit", kwargs={"pk": design_project_a.pk})
        payload = {
            "title": "Smart Infusion System Updated Title",
            "device_name": design_project_a.device_name,
            "device_class": design_project_a.device_class,
            "regulatory_pathway": design_project_a.regulatory_pathway,
            "intended_use": design_project_a.intended_use,
            "current_phase": design_project_a.current_phase,
            "status": design_project_a.status,
            "project_lead": admin_user.pk,
            "quality_lead": admin_user.pk,
            "department": quality_department.pk,
            "dhf_location": "Updated-Vault-Path",
        }
        res = client_a.post(url, data=payload)
        assert res.status_code == 302
        assert res.url == reverse("quality:design_project_detail", kwargs={"pk": design_project_a.pk})

        design_project_a.refresh_from_db()
        assert design_project_a.title == "Smart Infusion System Updated Title"
        assert design_project_a.dhf_location == "Updated-Vault-Path"

        audit = _designcontrols_audit_logs(design_project_a, action="update")
        assert audit.exists()

    def test_designcontrols_project_edit_locked_dhf_rejected(self, client_a, design_project_locked):
        url = reverse("quality:design_project_edit", kwargs={"pk": design_project_locked.pk})
        # GET should redirect
        res_get = client_a.get(url)
        assert res_get.status_code == 302
        assert res_get.url == reverse("quality:design_project_detail", kwargs={"pk": design_project_locked.pk})

        messages = _designcontrols_get_messages(res_get)
        assert any("DHF is locked" in m for m in messages)

        # POST should also redirect
        res_post = client_a.post(url, data={"title": "Hacked Title"})
        assert res_post.status_code == 302
        design_project_locked.refresh_from_db()
        assert design_project_locked.title != "Hacked Title"

    def test_designcontrols_project_delete_post_valid(self, client_a, tenant_a, admin_user):
        project = DesignProject.objects.create(
            tenant=tenant_a,
            title="Temporary Prototype Project",
            device_name="Proto 1",
            device_class="class_i",
            regulatory_pathway="exempt",
            intended_use="Internal testing only",
            current_phase="planning",
            status="draft",
            project_lead=admin_user,
            quality_lead=admin_user,
            dhf_locked=False,
        )
        url = reverse("quality:design_project_delete", kwargs={"pk": project.pk})
        res = client_a.post(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:design_project_list")
        assert not DesignProject.objects.filter(pk=project.pk).exists()

    def test_designcontrols_project_delete_get_rejected(self, client_a, design_project_a):
        url = reverse("quality:design_project_delete", kwargs={"pk": design_project_a.pk})
        res = client_a.get(url)
        assert res.status_code == 405  # require_POST rejects GET

    def test_designcontrols_project_delete_locked_dhf_rejected(self, client_a, design_project_locked):
        url = reverse("quality:design_project_delete", kwargs={"pk": design_project_locked.pk})
        res = client_a.post(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:design_project_detail", kwargs={"pk": design_project_locked.pk})
        assert DesignProject.objects.filter(pk=design_project_locked.pk).exists()
        messages = _designcontrols_get_messages(res)
        assert any("Cannot delete a project with a locked Design History File" in m for m in messages)

    def test_designcontrols_project_advance_phase_sequential(self, client_a, design_project_a):
        url = reverse("quality:design_project_advance_phase", kwargs={"pk": design_project_a.pk})

        # GET should be rejected with 405
        assert client_a.get(url).status_code == 405

        # 1. planning -> input
        res1 = client_a.post(url)
        assert res1.status_code == 302
        design_project_a.refresh_from_db()
        assert design_project_a.current_phase == "input"

        # 2. input -> output_verification
        client_a.post(url)
        design_project_a.refresh_from_db()
        assert design_project_a.current_phase == "output_verification"

        # 3. output_verification -> validation
        client_a.post(url)
        design_project_a.refresh_from_db()
        assert design_project_a.current_phase == "validation"

        # 4. validation -> commercial_closure (also sets status="completed")
        client_a.post(url)
        design_project_a.refresh_from_db()
        assert design_project_a.current_phase == "commercial_closure"
        assert design_project_a.status == "completed"

        # 5. commercial_closure -> closed
        client_a.post(url)
        design_project_a.refresh_from_db()
        assert design_project_a.current_phase == "closed"

        # 6. Already closed -> stays closed
        res_end = client_a.post(url)
        assert res_end.status_code == 302
        design_project_a.refresh_from_db()
        assert design_project_a.current_phase == "closed"
        messages = _designcontrols_get_messages(res_end)
        assert any("already in final closed phase" in m for m in messages)

    def test_designcontrols_project_advance_phase_locked_rejected(self, client_a, design_project_locked):
        url = reverse("quality:design_project_advance_phase", kwargs={"pk": design_project_locked.pk})
        res = client_a.post(url)
        assert res.status_code == 302
        messages = _designcontrols_get_messages(res)
        assert any("Cannot advance phase on a project with a locked Design History File" in m for m in messages)

    def test_designcontrols_project_lock_dhf_authorized(self, client_a, design_project_a):
        url = reverse("quality:design_project_lock_dhf", kwargs={"pk": design_project_a.pk})

        # GET should be rejected with 405
        assert client_a.get(url).status_code == 405

        # POST locks the project
        res = client_a.post(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:design_project_detail", kwargs={"pk": design_project_a.pk})

        design_project_a.refresh_from_db()
        assert design_project_a.dhf_locked is True
        assert design_project_a.status == "completed"
        assert design_project_a.actual_completion_date is not None

        audit = _designcontrols_audit_logs(design_project_a, action="lock_dhf")
        assert audit.exists()

        # Second lock attempt notifies it's already locked
        res2 = client_a.post(url)
        assert res2.status_code == 302
        messages = _designcontrols_get_messages(res2)
        assert any("already locked" in m for m in messages)

    def test_designcontrols_project_lock_dhf_permission_denied(self, member_client, design_project_a):
        # member_user is not project lead, not quality lead, and not tenant admin
        url = reverse("quality:design_project_lock_dhf", kwargs={"pk": design_project_a.pk})
        res = member_client.post(url)
        assert res.status_code == 302
        design_project_a.refresh_from_db()
        assert design_project_a.dhf_locked is False

        messages = _designcontrols_get_messages(res)
        assert any("Permission denied" in m for m in messages)


# =====================================================================
# 2. DesignInput Views
# =====================================================================


class TestDesignInputViews:
    def test_designcontrols_input_list_get_success(self, client_a, design_input_need, design_input_spec):
        url = reverse("quality:design_input_list")
        res = client_a.get(url)
        assert res.status_code == 200
        _designcontrols_assert_no_comment_leaks(res)

        # Context keys
        assert "inputs" in res.context
        assert "projects" in res.context
        assert "input_type_choices" in res.context
        assert "priority_choices" in res.context
        assert "status_choices" in res.context
        assert res.context["total_count"] >= 2
        assert "verified_count" in res.context
        assert "unverified_count" in res.context

        content = res.content.decode("utf-8")
        assert design_input_need.identifier in content
        assert design_input_spec.identifier in content

    def test_designcontrols_input_list_filters_and_search(self, client_a, design_input_need, design_input_spec):
        url = reverse("quality:design_input_list")

        # Search by identifier
        res_q = client_a.get(f"{url}?q={design_input_need.identifier}")
        assert res_q.status_code == 200
        items_q = list(res_q.context["inputs"])
        assert design_input_need in items_q
        assert design_input_spec not in items_q

        # Filter by project
        res_proj = client_a.get(f"{url}?project={design_input_need.project.pk}")
        assert res_proj.status_code == 200
        assert design_input_need in list(res_proj.context["inputs"])

        # Filter by input_type
        res_type = client_a.get(f"{url}?input_type=user_need")
        assert res_type.status_code == 200
        assert design_input_need in list(res_type.context["inputs"])
        assert design_input_spec not in list(res_type.context["inputs"])

        # Filter by priority
        res_prio = client_a.get(f"{url}?priority=high")
        assert res_prio.status_code == 200
        assert design_input_need in list(res_prio.context["inputs"])

        # Filter by status
        res_stat = client_a.get(f"{url}?status=approved")
        assert res_stat.status_code == 200
        assert design_input_need in list(res_stat.context["inputs"])

        # Out of bounds pagination and junk params
        res_junk = client_a.get(f"{url}?page=invalid&project=xyz")
        assert res_junk.status_code == 200

    def test_designcontrols_input_export_csv(self, client_a, tenant_a, design_project_a, admin_user):
        # Create input with formula sanitization test string
        inp_formula = DesignInput.objects.create(
            tenant=tenant_a,
            project=design_project_a,
            identifier="=FORMULA-01",
            title="+Formula Title",
            input_type="functional",
            priority="major",
            status="draft",
            description="Testing formula sanitization",
            acceptance_criteria="-NegativeCriteria",
            owner=admin_user,
        )

        url = reverse("quality:design_input_export")
        res = client_a.get(url)
        assert res.status_code == 200
        assert res["Content-Type"] == "text/csv"
        assert 'attachment; filename="design_inputs.csv"' in res["Content-Disposition"]

        reader = csv.reader(io.StringIO(res.content.decode("utf-8")))
        rows = list(reader)
        headers = rows[0]

        expected_headers = [
            "Number", "Identifier", "Title", "Project", "Type", "Priority", "Status",
            "Owner", "Parent Need", "Acceptance Criteria", "Verified"
        ]
        assert headers == expected_headers

        found = False
        for row in rows[1:]:
            if row[0] == inp_formula.number:
                assert row[1] == "'=FORMULA-01"
                assert row[2] == "'+Formula Title"
                assert row[9] == "'-NegativeCriteria"
                found = True
        assert found

    def test_designcontrols_input_create_get_prefill(self, client_a, design_project_a):
        url = reverse("quality:design_input_create")
        res = client_a.get(f"{url}?project={design_project_a.pk}")
        assert res.status_code == 200
        _designcontrols_assert_no_comment_leaks(res)
        assert res.context["form"].initial.get("project") == design_project_a

    def test_designcontrols_input_create_post_valid(self, client_a, tenant_a, design_project_a, admin_user, design_input_need):
        url = reverse("quality:design_input_create")
        payload = {
            "project": design_project_a.pk,
            "identifier": "DI-PRF-001",
            "title": "Infusion Flow Rate Accuracy",
            "input_type": "performance",
            "priority": "critical",
            "status": "draft",
            "description": "Flow rate must remain within +/- 2% under varying backpressures.",
            "acceptance_criteria": "Flow deviation < 2% across 0 to 300 mmHg.",
            "rationale": "Direct patient dose safety.",
            "user_need_parent": design_input_need.pk,
            "owner": admin_user.pk,
            "version": "1.0",
        }
        res = client_a.post(url, data=payload)
        new_inp = DesignInput.objects.filter(tenant=tenant_a, identifier="DI-PRF-001").first()
        assert new_inp is not None
        assert res.status_code == 302
        assert res.url == reverse("quality:design_input_detail", kwargs={"pk": new_inp.pk})

        audit = _designcontrols_audit_logs(new_inp, action="create")
        assert audit.exists()

    def test_designcontrols_input_create_post_invalid(self, client_a):
        url = reverse("quality:design_input_create")
        res = client_a.post(url, data={})
        assert res.status_code == 200
        assert res.context["form"].errors
        _designcontrols_assert_no_comment_leaks(res)

    def test_designcontrols_input_detail(self, client_a, design_input_need, design_input_spec, design_verification_a):
        url = reverse("quality:design_input_detail", kwargs={"pk": design_input_spec.pk})
        res = client_a.get(url)
        assert res.status_code == 200
        _designcontrols_assert_no_comment_leaks(res)

        # Context keys
        assert res.context["input_obj"] == design_input_spec
        assert design_verification_a in list(res.context["verifications"])

        content = res.content.decode("utf-8")
        assert design_input_spec.identifier in content
        assert design_input_spec.title in content
        assert design_input_need.identifier in content

    def test_designcontrols_input_edit(self, client_a, design_input_spec, admin_user):
        url = reverse("quality:design_input_edit", kwargs={"pk": design_input_spec.pk})

        res_get = client_a.get(url)
        assert res_get.status_code == 200
        _designcontrols_assert_no_comment_leaks(res_get)

        payload = {
            "project": design_input_spec.project.pk,
            "identifier": design_input_spec.identifier,
            "title": "Battery Capacity Revised Spec",
            "input_type": design_input_spec.input_type,
            "priority": "major",
            "status": "approved",
            "description": "High-density lithium ion battery pack specification.",
            "acceptance_criteria": "Revised criteria: >= 5000mAh",
            "user_need_parent": design_input_spec.user_need_parent_id,
            "owner": admin_user.pk,
            "version": "1.1",
        }
        res_post = client_a.post(url, data=payload)
        assert res_post.status_code == 302
        assert res_post.url == reverse("quality:design_input_detail", kwargs={"pk": design_input_spec.pk})

        design_input_spec.refresh_from_db()
        assert design_input_spec.title == "Battery Capacity Revised Spec"
        assert design_input_spec.version == "1.1"

        audit = _designcontrols_audit_logs(design_input_spec, action="update")
        assert audit.exists()

    def test_designcontrols_input_edit_locked_project_rejected(self, client_a, tenant_a, design_project_locked, admin_user):
        locked_input = DesignInput.objects.create(
            tenant=tenant_a,
            project=design_project_locked,
            identifier="LOCKED-INP-01",
            title="Locked Input",
            input_type="functional",
            priority="minor",
            status="approved",
            description="Locked spec",
            acceptance_criteria="Pass",
            owner=admin_user,
        )
        url = reverse("quality:design_input_edit", kwargs={"pk": locked_input.pk})
        res_get = client_a.get(url)
        assert res_get.status_code == 302
        assert res_get.url == reverse("quality:design_input_detail", kwargs={"pk": locked_input.pk})

        messages = _designcontrols_get_messages(res_get)
        assert any("Parent project DHF is locked" in m for m in messages)

        res_post = client_a.post(url, data={"title": "Hacked Locked Input"})
        assert res_post.status_code == 302
        locked_input.refresh_from_db()
        assert locked_input.title != "Hacked Locked Input"

    def test_designcontrols_input_delete_post_valid(self, client_a, tenant_a, design_project_a, admin_user):
        inp = DesignInput.objects.create(
            tenant=tenant_a,
            project=design_project_a,
            identifier="DEL-INP-01",
            title="Temporary Input",
            input_type="functional",
            priority="minor",
            status="draft",
            description="To be removed",
            acceptance_criteria="Pass",
            owner=admin_user,
        )
        url = reverse("quality:design_input_delete", kwargs={"pk": inp.pk})
        res = client_a.post(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:design_input_list")
        assert not DesignInput.objects.filter(pk=inp.pk).exists()

    def test_designcontrols_input_delete_get_rejected(self, client_a, design_input_spec):
        url = reverse("quality:design_input_delete", kwargs={"pk": design_input_spec.pk})
        res = client_a.get(url)
        assert res.status_code == 405

    def test_designcontrols_input_delete_locked_project_rejected(self, client_a, tenant_a, design_project_locked, admin_user):
        locked_inp = DesignInput.objects.create(
            tenant=tenant_a,
            project=design_project_locked,
            identifier="LOCK-DEL-01",
            title="Locked Del Input",
            input_type="functional",
            priority="minor",
            status="approved",
            description="Locked",
            acceptance_criteria="Pass",
            owner=admin_user,
        )
        url = reverse("quality:design_input_delete", kwargs={"pk": locked_inp.pk})
        res = client_a.post(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:design_input_detail", kwargs={"pk": locked_inp.pk})
        assert DesignInput.objects.filter(pk=locked_inp.pk).exists()

        messages = _designcontrols_get_messages(res)
        assert any("Cannot delete design input from a locked Design History File" in m for m in messages)


# =====================================================================
# 3. DesignReview Views
# =====================================================================


class TestDesignReviewViews:
    def test_designcontrols_review_list_get_success(self, client_a, design_review_a):
        url = reverse("quality:design_review_list")
        res = client_a.get(url)
        assert res.status_code == 200
        _designcontrols_assert_no_comment_leaks(res)

        # Context keys
        assert "reviews" in res.context
        assert "projects" in res.context
        assert "stage_choices" in res.context
        assert "status_choices" in res.context
        assert res.context["total_count"] >= 1
        assert "approved_count" in res.context
        assert "pending_count" in res.context

        content = res.content.decode("utf-8")
        assert design_review_a.number in content
        assert design_review_a.title in content

    def test_designcontrols_review_list_filters_and_search(self, client_a, design_review_a):
        url = reverse("quality:design_review_list")

        # Search by number
        res_q = client_a.get(f"{url}?q={design_review_a.number}")
        assert res_q.status_code == 200
        assert design_review_a in list(res_q.context["reviews"])

        # Filter by project
        res_proj = client_a.get(f"{url}?project={design_review_a.project.pk}")
        assert res_proj.status_code == 200
        assert design_review_a in list(res_proj.context["reviews"])

        # Filter by stage
        res_stage = client_a.get(f"{url}?stage=planning")
        assert res_stage.status_code == 200
        assert design_review_a in list(res_stage.context["reviews"])

        # Filter by status
        res_stat = client_a.get(f"{url}?status=scheduled")
        assert res_stat.status_code == 200
        assert design_review_a in list(res_stat.context["reviews"])

    def test_designcontrols_review_export_csv(self, client_a, design_review_a):
        url = reverse("quality:design_review_export")
        res = client_a.get(url)
        assert res.status_code == 200
        assert res["Content-Type"] == "text/csv"
        assert 'attachment; filename="design_reviews.csv"' in res["Content-Disposition"]

        reader = csv.reader(io.StringIO(res.content.decode("utf-8")))
        rows = list(reader)
        headers = rows[0]
        expected_headers = [
            "Number", "Title", "Project", "Stage", "Review Date", "Status",
            "Lead Reviewer", "Independent Reviewer", "Action Items Resolved"
        ]
        assert headers == expected_headers

    def test_designcontrols_review_create_get_prefill(self, client_a, design_project_a):
        url = reverse("quality:design_review_create")
        res = client_a.get(f"{url}?project={design_project_a.pk}")
        assert res.status_code == 200
        _designcontrols_assert_no_comment_leaks(res)
        assert res.context["form"].initial.get("project") == design_project_a

    def test_designcontrols_review_create_post_valid(self, client_a, tenant_a, design_project_a, admin_user, member_user):
        url = reverse("quality:design_review_create")
        payload = {
            "project": design_project_a.pk,
            "title": "Phase 2 Input Freeze Formal Gate Review",
            "review_stage": "input_freeze",
            "review_date": "2026-11-25",
            "status": "scheduled",
            "lead_reviewer": admin_user.pk,
            "independent_reviewer": member_user.pk,
            "agenda": "Review user needs to engineering input traceability.",
            "discussion_summary": "All 15 inputs reviewed.",
            "conclusions": "Recommended for freeze.",
            "action_items": "Close open question on packaging.",
            "action_items_resolved": False,
        }
        res = client_a.post(url, data=payload)
        new_rev = DesignReview.objects.filter(tenant=tenant_a, title="Phase 2 Input Freeze Formal Gate Review").first()
        assert new_rev is not None
        assert res.status_code == 302
        assert res.url == reverse("quality:design_review_detail", kwargs={"pk": new_rev.pk})

        audit = _designcontrols_audit_logs(new_rev, action="create")
        assert audit.exists()

    def test_designcontrols_review_create_post_invalid(self, client_a):
        url = reverse("quality:design_review_create")
        res = client_a.post(url, data={})
        assert res.status_code == 200
        assert res.context["form"].errors
        _designcontrols_assert_no_comment_leaks(res)

    def test_designcontrols_review_detail(self, client_a, design_review_a):
        url = reverse("quality:design_review_detail", kwargs={"pk": design_review_a.pk})
        res = client_a.get(url)
        assert res.status_code == 200
        _designcontrols_assert_no_comment_leaks(res)
        assert res.context["review"] == design_review_a

        content = res.content.decode("utf-8")
        assert design_review_a.number in content
        assert design_review_a.title in content
        assert "Clear & Approve Gate" in content or "Approve Gate" in content or "Stage-Gate" in content

    def test_designcontrols_review_edit(self, client_a, design_review_a, admin_user, member_user):
        url = reverse("quality:design_review_edit", kwargs={"pk": design_review_a.pk})

        res_get = client_a.get(url)
        assert res_get.status_code == 200
        _designcontrols_assert_no_comment_leaks(res_get)

        payload = {
            "project": design_review_a.project.pk,
            "title": "Planning Gate Review (Updated)",
            "review_stage": "planning",
            "review_date": "2026-11-26",
            "status": "in_progress",
            "lead_reviewer": admin_user.pk,
            "independent_reviewer": member_user.pk,
            "agenda": "Updated agenda with QA audit notes.",
            "discussion_summary": "In progress discussion.",
            "conclusions": "Pending one sign-off.",
            "action_items": "None",
            "action_items_resolved": True,
        }
        res_post = client_a.post(url, data=payload)
        assert res_post.status_code == 302
        assert res_post.url == reverse("quality:design_review_detail", kwargs={"pk": design_review_a.pk})

        design_review_a.refresh_from_db()
        assert design_review_a.title == "Planning Gate Review (Updated)"
        assert design_review_a.status == "in_progress"

        audit = _designcontrols_audit_logs(design_review_a, action="update")
        assert audit.exists()

    def test_designcontrols_review_edit_locked_project_rejected(self, client_a, tenant_a, design_project_locked, admin_user, member_user):
        rev = DesignReview.objects.create(
            tenant=tenant_a,
            project=design_project_locked,
            title="Post Transfer Review",
            review_stage="transfer_gate",
            review_date=timezone.now().date(),
            status="approved",
            lead_reviewer=admin_user,
            independent_reviewer=member_user,
        )
        url = reverse("quality:design_review_edit", kwargs={"pk": rev.pk})
        res_get = client_a.get(url)
        assert res_get.status_code == 302
        assert res_get.url == reverse("quality:design_review_detail", kwargs={"pk": rev.pk})
        messages = _designcontrols_get_messages(res_get)
        assert any("Parent project DHF is locked" in m for m in messages)

        res_post = client_a.post(url, data={"title": "Hacked Review Title"})
        assert res_post.status_code == 302
        rev.refresh_from_db()
        assert rev.title != "Hacked Review Title"

    def test_designcontrols_review_delete_post_valid(self, client_a, tenant_a, design_project_a, admin_user, member_user):
        rev = DesignReview.objects.create(
            tenant=tenant_a,
            project=design_project_a,
            title="Cancelled Preliminary Meeting",
            review_stage="concept",
            review_date=timezone.now().date(),
            status="cancelled",
            lead_reviewer=admin_user,
            independent_reviewer=member_user,
        )
        url = reverse("quality:design_review_delete", kwargs={"pk": rev.pk})
        res = client_a.post(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:design_review_list")
        assert not DesignReview.objects.filter(pk=rev.pk).exists()

    def test_designcontrols_review_delete_get_rejected(self, client_a, design_review_a):
        url = reverse("quality:design_review_delete", kwargs={"pk": design_review_a.pk})
        assert client_a.get(url).status_code == 405

    def test_designcontrols_review_delete_locked_project_rejected(self, client_a, tenant_a, design_project_locked, admin_user, member_user):
        rev = DesignReview.objects.create(
            tenant=tenant_a,
            project=design_project_locked,
            title="Locked DHF Review",
            review_stage="transfer_gate",
            review_date=timezone.now().date(),
            status="approved",
            lead_reviewer=admin_user,
            independent_reviewer=member_user,
        )
        url = reverse("quality:design_review_delete", kwargs={"pk": rev.pk})
        res = client_a.post(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:design_review_detail", kwargs={"pk": rev.pk})
        assert DesignReview.objects.filter(pk=rev.pk).exists()

    def test_designcontrols_review_approve_gate_authorized(self, client_a, design_review_a):
        url = reverse("quality:design_review_approve_gate", kwargs={"pk": design_review_a.pk})

        # GET should be rejected with 405
        assert client_a.get(url).status_code == 405

        # POST as admin clears gate
        res = client_a.post(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:design_review_detail", kwargs={"pk": design_review_a.pk})

        design_review_a.refresh_from_db()
        assert design_review_a.status == "approved"
        assert design_review_a.action_items_resolved is True

        audit = _designcontrols_audit_logs(design_review_a, action="approve")
        assert audit.exists()

    def test_designcontrols_review_approve_gate_unauthorized(self, member_client, design_review_a):
        url = reverse("quality:design_review_approve_gate", kwargs={"pk": design_review_a.pk})
        # member_user is not lead reviewer, not quality lead, and not tenant admin
        res = member_client.post(url)
        assert res.status_code == 302
        design_review_a.refresh_from_db()
        assert design_review_a.status != "approved"

        messages = _designcontrols_get_messages(res)
        assert any("Permission denied" in m for m in messages)

    def test_designcontrols_review_approve_gate_locked_project_rejected(self, client_a, tenant_a, design_project_locked, admin_user, member_user):
        rev = DesignReview.objects.create(
            tenant=tenant_a,
            project=design_project_locked,
            title="Locked Gate Review",
            review_stage="transfer_gate",
            review_date=timezone.now().date(),
            status="scheduled",
            lead_reviewer=admin_user,
            independent_reviewer=member_user,
        )
        url = reverse("quality:design_review_approve_gate", kwargs={"pk": rev.pk})
        res = client_a.post(url)
        assert res.status_code == 302
        rev.refresh_from_db()
        assert rev.status != "approved"
        messages = _designcontrols_get_messages(res)
        assert any("Cannot approve gate review for a project with a locked Design History File" in m for m in messages)


# =====================================================================
# 4. DesignVerification Views
# =====================================================================


class TestDesignVerificationViews:
    def test_designcontrols_verification_list_get_success(self, client_a, design_verification_a):
        url = reverse("quality:design_verification_list")
        res = client_a.get(url)
        assert res.status_code == 200
        _designcontrols_assert_no_comment_leaks(res)

        # Context keys
        assert "verifications" in res.context
        assert "projects" in res.context
        assert "activity_choices" in res.context
        assert "status_choices" in res.context
        assert "result_choices" in res.context
        assert res.context["total_count"] >= 1
        assert "passed_count" in res.context
        assert "failed_count" in res.context

        content = res.content.decode("utf-8")
        assert design_verification_a.number in content
        assert design_verification_a.title in content

    def test_designcontrols_verification_list_filters_and_search(self, client_a, design_verification_a):
        url = reverse("quality:design_verification_list")

        # Search by number
        res_q = client_a.get(f"{url}?q={design_verification_a.number}")
        assert res_q.status_code == 200
        assert design_verification_a in list(res_q.context["verifications"])

        # Filter by project
        res_proj = client_a.get(f"{url}?project={design_verification_a.project.pk}")
        assert res_proj.status_code == 200
        assert design_verification_a in list(res_proj.context["verifications"])

        # Filter by activity_type
        res_act = client_a.get(f"{url}?activity_type={design_verification_a.activity_type}")
        assert res_act.status_code == 200

        # Filter by status
        res_stat = client_a.get(f"{url}?status=draft")
        assert res_stat.status_code == 200
        assert design_verification_a in list(res_stat.context["verifications"])

        # Filter by result
        res_res = client_a.get(f"{url}?result=pending")
        assert res_res.status_code == 200
        assert design_verification_a in list(res_res.context["verifications"])

    def test_designcontrols_verification_export_csv(self, client_a, design_verification_a):
        url = reverse("quality:design_verification_export")
        res = client_a.get(url)
        assert res.status_code == 200
        assert res["Content-Type"] == "text/csv"
        assert 'attachment; filename="design_verifications.csv"' in res["Content-Disposition"]

        reader = csv.reader(io.StringIO(res.content.decode("utf-8")))
        rows = list(reader)
        headers = rows[0]
        expected_headers = [
            "Number", "Title", "Project", "Design Input", "Activity Type", "Status",
            "Test Method", "Sample Size", "Pass/Fail Result", "Executed By", "Execution Date"
        ]
        assert headers == expected_headers

    def test_designcontrols_verification_create_get_prefill(self, client_a, design_input_spec, design_project_a):
        url = reverse("quality:design_verification_create")

        # Prefill via ?input=
        res_inp = client_a.get(f"{url}?input={design_input_spec.pk}")
        assert res_inp.status_code == 200
        _designcontrols_assert_no_comment_leaks(res_inp)
        assert res_inp.context["form"].initial.get("primary_input") == design_input_spec
        assert res_inp.context["form"].initial.get("project") == design_project_a

        # Prefill via ?project=
        res_proj = client_a.get(f"{url}?project={design_project_a.pk}")
        assert res_proj.status_code == 200
        assert res_proj.context["form"].initial.get("project") == design_project_a

    def test_designcontrols_verification_create_post_draft(self, client_a, tenant_a, design_project_a, design_input_need, admin_user):
        url = reverse("quality:design_verification_create")
        payload = {
            "project": design_project_a.pk,
            "primary_input": design_input_need.pk,
            "title": "Drop Impact Test Protocol",
            "activity_type": "verification",
            "status": "draft",
            "test_method": "lab_test",
            "acceptance_criteria": "No cracking after 1m drop.",
            "sample_size": 3,
            "results_summary": "Draft protocol.",
            "pass_fail_result": "pending",
            "executed_by": admin_user.pk,
        }
        res = client_a.post(url, data=payload)
        new_ver = DesignVerification.objects.filter(tenant=tenant_a, title="Drop Impact Test Protocol").first()
        assert new_ver is not None
        assert res.status_code == 302
        assert res.url == reverse("quality:design_verification_detail", kwargs={"pk": new_ver.pk})

        # Primary input status should remain unchanged
        design_input_need.refresh_from_db()
        assert design_input_need.status == "approved"

    def test_designcontrols_verification_create_post_auto_verifies_input(self, client_a, tenant_a, design_project_a, design_input_need, admin_user):
        url = reverse("quality:design_verification_create")
        payload = {
            "project": design_project_a.pk,
            "primary_input": design_input_need.pk,
            "title": "Battery Operational Endurance Test",
            "activity_type": "verification",
            "status": "passed",
            "test_method": "lab_test",
            "acceptance_criteria": "Exceeds 8 hours runtime.",
            "sample_size": 5,
            "results_summary": "All 5 units averaged 9.2 hours.",
            "pass_fail_result": "pass",
            "executed_by": admin_user.pk,
            "execution_date": "2026-11-17",
        }
        res = client_a.post(url, data=payload)
        new_ver = DesignVerification.objects.filter(tenant=tenant_a, title="Battery Operational Endurance Test").first()
        assert new_ver is not None
        assert res.status_code == 302

        # Assert primary_input status was automatically updated to 'verified'
        design_input_need.refresh_from_db()
        assert design_input_need.status == "verified"

        # Verify audit log was written for primary_input
        audit = _designcontrols_audit_logs(design_input_need, action="verify")
        assert audit.exists()

    def test_designcontrols_verification_detail(self, client_a, design_verification_a):
        url = reverse("quality:design_verification_detail", kwargs={"pk": design_verification_a.pk})
        res = client_a.get(url)
        assert res.status_code == 200
        _designcontrols_assert_no_comment_leaks(res)
        assert res.context["verification"] == design_verification_a

        content = res.content.decode("utf-8")
        assert design_verification_a.number in content
        assert design_verification_a.title in content
        assert design_verification_a.primary_input.identifier in content

    def test_designcontrols_verification_edit_and_status_recalculation(self, client_a, tenant_a, design_project_a, admin_user):
        # 1. Create a fresh input
        inp = DesignInput.objects.create(
            tenant=tenant_a,
            project=design_project_a,
            identifier="RECALC-001",
            title="Recalculation Target Spec",
            input_type="functional",
            priority="major",
            status="approved",
            description="Target for status recalculation",
            acceptance_criteria="Pass threshold >= 100",
            owner=admin_user,
        )

        # 2. Create passing verification protocol
        ver = DesignVerification.objects.create(
            tenant=tenant_a,
            project=design_project_a,
            primary_input=inp,
            title="Tensile Strength Run #1",
            activity_type="verification",
            status="passed",
            test_method="lab_test",
            acceptance_criteria="Pass threshold >= 100",
            sample_size=3,
            pass_fail_result="pass",
            results_summary="Mean = 112",
            executed_by=admin_user,
        )
        inp.status = "verified"
        inp.save(update_fields=["status"])

        # 3. Edit verification to FAIL
        url = reverse("quality:design_verification_edit", kwargs={"pk": ver.pk})
        payload = {
            "project": design_project_a.pk,
            "primary_input": inp.pk,
            "title": "Tensile Strength Run #1 (Retest Failed)",
            "activity_type": ver.activity_type,
            "status": "failed",
            "test_method": ver.test_method,
            "acceptance_criteria": ver.acceptance_criteria,
            "sample_size": ver.sample_size,
            "pass_fail_result": "fail",
            "results_summary": "Sample failed at 85N",
            "deviation_notes": "Material degradation detected",
            "executed_by": admin_user.pk,
        }
        res_post = client_a.post(url, data=payload)
        assert res_post.status_code == 302
        assert res_post.url == reverse("quality:design_verification_detail", kwargs={"pk": ver.pk})

        # 4. Primary input should revert to 'approved' (unverified)
        inp.refresh_from_db()
        assert inp.status == "approved"

        # Verify audit log recorded 'unverify'
        audit_unver = _designcontrols_audit_logs(inp, action="unverify")
        assert audit_unver.exists()

        # 5. Edit back to PASS -> updates to 'verified'
        payload["status"] = "passed"
        payload["pass_fail_result"] = "pass"
        client_a.post(url, data=payload)
        inp.refresh_from_db()
        assert inp.status == "verified"

    def test_designcontrols_verification_delete_recalculates_primary_input_status(self, client_a, tenant_a, design_project_a, admin_user):
        inp = DesignInput.objects.create(
            tenant=tenant_a,
            project=design_project_a,
            identifier="DEL-RECALC-001",
            title="Delete Recalc Target",
            input_type="functional",
            priority="major",
            status="verified",
            description="Spec for deletion verification test",
            acceptance_criteria="Pass threshold",
            owner=admin_user,
        )
        ver = DesignVerification.objects.create(
            tenant=tenant_a,
            project=design_project_a,
            primary_input=inp,
            title="Single Passing Verification",
            activity_type="verification",
            status="passed",
            test_method="lab_test",
            acceptance_criteria="Pass",
            sample_size=1,
            pass_fail_result="pass",
            results_summary="Passed",
            executed_by=admin_user,
        )

        url = reverse("quality:design_verification_delete", kwargs={"pk": ver.pk})

        # GET should be rejected with 405
        assert client_a.get(url).status_code == 405

        # POST deletes and recalculates status to approved
        res_del = client_a.post(url)
        assert res_del.status_code == 302
        assert res_del.url == reverse("quality:design_verification_list")

        inp.refresh_from_db()
        assert inp.status == "approved"
        assert not DesignVerification.objects.filter(pk=ver.pk).exists()

    def test_designcontrols_verification_locked_project_rejected(self, client_a, tenant_a, design_project_locked, admin_user):
        locked_inp = DesignInput.objects.create(
            tenant=tenant_a,
            project=design_project_locked,
            identifier="LOCK-VER-INP",
            title="Locked Input for Ver",
            input_type="functional",
            priority="minor",
            status="approved",
            description="Locked",
            acceptance_criteria="Pass",
            owner=admin_user,
        )
        ver = DesignVerification.objects.create(
            tenant=tenant_a,
            project=design_project_locked,
            primary_input=locked_inp,
            title="Locked Verification Record",
            activity_type="verification",
            status="passed",
            test_method="lab_test",
            acceptance_criteria="Pass",
            sample_size=1,
            pass_fail_result="pass",
            results_summary="Locked test",
            executed_by=admin_user,
        )

        # Edit attempt rejected
        url_edit = reverse("quality:design_verification_edit", kwargs={"pk": ver.pk})
        res_edit = client_a.get(url_edit)
        assert res_edit.status_code == 302
        messages = _designcontrols_get_messages(res_edit)
        assert any("Parent project DHF is locked" in m for m in messages)

        # Delete attempt rejected
        url_del = reverse("quality:design_verification_delete", kwargs={"pk": ver.pk})
        res_del = client_a.post(url_del)
        assert res_del.status_code == 302
        assert DesignVerification.objects.filter(pk=ver.pk).exists()
        messages_del = _designcontrols_get_messages(res_del)
        assert any("Cannot delete verification protocol from a locked Design History File" in m for m in messages_del)


# =====================================================================
# 5. Traceability Matrix & DHF Dossier Views
# =====================================================================


class TestTraceabilityMatrixAndDHFViews:
    def test_designcontrols_matrix_get_default_project(self, client_a, design_project_a, design_input_spec):
        url = reverse("quality:traceability_matrix")
        res = client_a.get(url)
        assert res.status_code == 200
        _designcontrols_assert_no_comment_leaks(res)

        # Context keys
        assert "projects" in res.context
        assert res.context["selected_project"] is not None
        assert "matrix_rows" in res.context
        assert "total_inputs" in res.context
        assert "verified_inputs" in res.context
        assert "coverage_percentage" in res.context
        assert "gap_count" in res.context

        # Verify row structure
        rows = res.context["matrix_rows"]
        assert len(rows) >= 1
        first_row = rows[0]
        assert "input" in first_row
        assert "user_need" in first_row
        assert "verifications" in first_row
        assert "is_verified" in first_row
        assert "has_failures" in first_row

        content = res.content.decode("utf-8")
        assert "Traceability Matrix" in content
        assert design_input_spec.identifier in content

    def test_designcontrols_matrix_get_selected_project(self, client_a, design_project_a, design_project_locked):
        url = reverse("quality:traceability_matrix")
        res = client_a.get(f"{url}?project={design_project_locked.pk}")
        assert res.status_code == 200
        _designcontrols_assert_no_comment_leaks(res)
        assert res.context["selected_project"] == design_project_locked

    def test_designcontrols_matrix_invalid_project_warning(self, client_a, design_project_a):
        url = reverse("quality:traceability_matrix")
        res = client_a.get(f"{url}?project=999999")
        assert res.status_code == 200
        # Falls back to first available project
        assert res.context["selected_project"] == design_project_a
        messages = _designcontrols_get_messages(res)
        assert any("Selected design project was not found" in m for m in messages)

    def test_designcontrols_matrix_export_csv_success(self, client_a, design_project_a, design_input_need, design_input_spec, design_verification_a):
        url = reverse("quality:traceability_matrix_export")
        res = client_a.get(f"{url}?project={design_project_a.pk}")
        assert res.status_code == 200
        assert res["Content-Type"] == "text/csv"
        assert f'attachment; filename="RTM_{design_project_a.number}.csv"' in res["Content-Disposition"]

        reader = csv.reader(io.StringIO(res.content.decode("utf-8")))
        rows = list(reader)
        headers = rows[0]
        expected_headers = [
            "Project #", "User Need", "Design Input Identifier", "Design Input Title", "Type",
            "Acceptance Criteria", "Verification Protocol #", "Test Method", "Pass/Fail Result", "Status"
        ]
        assert headers == expected_headers
        assert len(rows) >= 2

    def test_designcontrols_matrix_export_csv_missing_project(self, client_a):
        url = reverse("quality:traceability_matrix_export")
        res = client_a.get(url)
        assert res.status_code == 302
        assert res.url == reverse("quality:traceability_matrix")
        messages = _designcontrols_get_messages(res)
        assert any("Select a valid design project" in m for m in messages)

    def test_designcontrols_dhf_dossier_detail_and_completeness(self, client_a, tenant_a, admin_user, member_user, quality_department):
        # Create a project with complete DHF prerequisites
        p_complete = DesignProject.objects.create(
            tenant=tenant_a,
            title="Complete Diagnostic Instrument",
            device_name="DiagPro 10",
            device_class="class_ii",
            regulatory_pathway="510k",
            intended_use="Clinical diagnostic use",
            current_phase="validation",
            status="active",
            project_lead=admin_user,
            quality_lead=admin_user,
            department=quality_department,
        )
        inp = DesignInput.objects.create(
            tenant=tenant_a,
            project=p_complete,
            identifier="DI-COMPLETE-01",
            title="Sensory Range Spec",
            input_type="functional",
            priority="critical",
            status="verified",
            description="Sensory accuracy check",
            acceptance_criteria="Accuracy within 0.1%",
            owner=admin_user,
        )
        DesignVerification.objects.create(
            tenant=tenant_a,
            project=p_complete,
            primary_input=inp,
            title="Verification Test",
            activity_type="verification",
            status="passed",
            test_method="lab_test",
            acceptance_criteria="Accuracy within 0.1%",
            sample_size=3,
            pass_fail_result="pass",
            results_summary="Pass",
            executed_by=admin_user,
        )
        # Add approved transfer_gate review
        DesignReview.objects.create(
            tenant=tenant_a,
            project=p_complete,
            title="Design Transfer Gate Review",
            review_stage="transfer_gate",
            review_date=timezone.now().date(),
            status="approved",
            lead_reviewer=admin_user,
            independent_reviewer=member_user,
            action_items_resolved=True,
        )

        url = reverse("quality:design_project_dhf", kwargs={"pk": p_complete.pk})
        res = client_a.get(url)
        assert res.status_code == 200
        _designcontrols_assert_no_comment_leaks(res)

        # Context keys
        assert res.context["project"] == p_complete
        assert inp in list(res.context["inputs"])
        assert res.context["total_inputs"] == 1
        assert res.context["verified_inputs"] == 1
        assert res.context["transfer_gate_cleared"] is True
        assert res.context["is_dhf_complete"] is True

        content = res.content.decode("utf-8")
        assert "Design History File (DHF) Dossier" in content
        assert p_complete.number in content
        assert "Transfer Gate Cleared" in content or "Transfer Gate" in content

    def test_designcontrols_dhf_dossier_export_csv(self, client_a, design_project_a, design_input_need, design_review_a, design_verification_a):
        url = reverse("quality:design_project_dhf_export", kwargs={"pk": design_project_a.pk})
        res = client_a.get(url)
        assert res.status_code == 200
        assert res["Content-Type"] == "text/csv"
        assert f'attachment; filename="DHF_Index_{design_project_a.number}.csv"' in res["Content-Disposition"]

        reader = csv.reader(io.StringIO(res.content.decode("utf-8")))
        rows = list(reader)
        headers = rows[0]
        expected_headers = ["Section", "Record Number", "Title / Item", "Classification / Stage", "Status", "Date / Outcome"]
        assert headers == expected_headers

        sections = [r[0] for r in rows[1:]]
        assert "DHF Plan" in sections
        assert "Design Input" in sections
        assert "Design Review" in sections
        assert "Verification" in sections


# =====================================================================
# 6. Security, Authentication & Multi-Tenant Isolation
# =====================================================================


class TestSecurityAndCrossTenantIsolation:
    def test_designcontrols_views_require_login(self, design_project_a):
        anon = Client()
        urls = [
            reverse("quality:design_project_list"),
            reverse("quality:design_project_create"),
            reverse("quality:design_project_detail", kwargs={"pk": design_project_a.pk}),
            reverse("quality:design_input_list"),
            reverse("quality:design_review_list"),
            reverse("quality:design_verification_list"),
            reverse("quality:traceability_matrix"),
            reverse("quality:design_project_dhf", kwargs={"pk": design_project_a.pk}),
        ]
        for url in urls:
            res = anon.get(url)
            assert res.status_code == 302
            assert "/login/" in res.url

    def test_designcontrols_cross_tenant_isolation_404(self, client_b, design_project_a, design_input_spec, design_review_a, design_verification_a):
        # Client B (Tenant B) must receive 404 for all Tenant A resources
        endpoints_404 = [
            reverse("quality:design_project_detail", kwargs={"pk": design_project_a.pk}),
            reverse("quality:design_project_edit", kwargs={"pk": design_project_a.pk}),
            reverse("quality:design_project_dhf", kwargs={"pk": design_project_a.pk}),
            reverse("quality:design_project_dhf_export", kwargs={"pk": design_project_a.pk}),
            reverse("quality:design_input_detail", kwargs={"pk": design_input_spec.pk}),
            reverse("quality:design_input_edit", kwargs={"pk": design_input_spec.pk}),
            reverse("quality:design_review_detail", kwargs={"pk": design_review_a.pk}),
            reverse("quality:design_review_edit", kwargs={"pk": design_review_a.pk}),
            reverse("quality:design_verification_detail", kwargs={"pk": design_verification_a.pk}),
            reverse("quality:design_verification_edit", kwargs={"pk": design_verification_a.pk}),
        ]
        for url in endpoints_404:
            res = client_b.get(url)
            assert res.status_code == 404

        # POST actions must also return 404
        post_endpoints_404 = [
            reverse("quality:design_project_delete", kwargs={"pk": design_project_a.pk}),
            reverse("quality:design_project_advance_phase", kwargs={"pk": design_project_a.pk}),
            reverse("quality:design_project_lock_dhf", kwargs={"pk": design_project_a.pk}),
            reverse("quality:design_input_delete", kwargs={"pk": design_input_spec.pk}),
            reverse("quality:design_review_delete", kwargs={"pk": design_review_a.pk}),
            reverse("quality:design_review_approve_gate", kwargs={"pk": design_review_a.pk}),
            reverse("quality:design_verification_delete", kwargs={"pk": design_verification_a.pk}),
        ]
        for url in post_endpoints_404:
            res = client_b.post(url)
            assert res.status_code == 404
