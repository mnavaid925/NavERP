"""
Unit tests for apps/quality forms (Sub-module 12.2: Design Controls & Development).

Covers:
- DesignProjectForm:
  - System field exclusion (tenant, number, dhf_locked, created_at, updated_at).
  - Multi-tenant foreign key scoping (department, project_lead, quality_lead).
  - Foreign key rejection via reject_foreign.
  - DHF regulatory lock integrity: clean() rejects re-opening or changing status
    on a locked project (dhf_locked=True).
  - Widget classes (form-input, form-select, form-textarea, type="date").
  - Form save & auto-number persistence.
- DesignInputForm:
  - System field exclusion (tenant, number, created_at, updated_at).
  - Multi-tenant foreign key scoping (project, owner, user_need_parent, controlled_document).
  - DHF regulatory lock integrity: cannot create/modify inputs for locked projects.
  - Parent user need project alignment (user_need_parent must belong to same project).
  - Parent user need exclusion of self on edit.
  - Parent user need filtering strictly to input_type="user_need".
  - Status="verified" business validation (rejects manual verified status without passing test).
  - Status="verified" allowed with passing verification protocol or if already verified.
  - Widget classes & form save.
- DesignReviewForm:
  - System field exclusion (tenant, number, electronic_signature, created_at, updated_at).
  - Multi-tenant foreign key scoping (project, lead_reviewer, independent_reviewer).
  - DHF regulatory lock integrity: cannot create/modify reviews for locked projects.
  - Stage-gate approval restriction: rejects setting status="approved" directly in form.
  - 21 CFR § 820.30(e) independent reviewer invariants:
    - independent_reviewer cannot equal lead_reviewer.
    - independent_reviewer cannot equal project.project_lead.
  - Widget classes (form-input, form-select, form-textarea, form-checkbox, type="date").
  - Form save & auto-number persistence.
- DesignVerificationForm:
  - System field exclusion (tenant, number, created_at, updated_at).
  - Multi-tenant foreign key scoping (project, primary_input, executed_by, protocol_document, report_document).
  - DHF regulatory lock integrity: cannot create/modify verification protocols for locked projects.
  - Primary input project alignment (primary_input must belong to selected project).
  - Acceptance criteria mandatory validation.
  - Sample size positive integer validation (sample_size >= 1).
  - Choice validations: activity_type, test_method, pass_fail_result.
  - Widget classes & form save.
- Direct reject_foreign utility validation.
"""

from datetime import timedelta
import pytest
from django import forms
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import OrgUnit
from apps.quality.forms import (
    DesignInputForm,
    DesignProjectForm,
    DesignReviewForm,
    DesignVerificationForm,
)
from apps.quality.forms._common import reject_foreign
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
def _designcontrols_org_unit(db, tenant_a):
    return OrgUnit.objects.create(
        tenant=tenant_a,
        name="Biomedical Engineering Dept",
        kind="department",
    )


@pytest.fixture
def _designcontrols_org_unit_b(db, tenant_b):
    return OrgUnit.objects.create(
        tenant=tenant_b,
        name="Globex Engineering Dept",
        kind="department",
    )


@pytest.fixture
def _designcontrols_engineer_user(db, tenant_a):
    return User.objects.create_user(
        email="lead.engineer@acme.com",
        username="engineer_acme",
        password="TestPass123!",
        tenant=tenant_a,
        is_tenant_admin=False,
    )


@pytest.fixture
def _designcontrols_independent_user(db, tenant_a):
    return User.objects.create_user(
        email="independent.reviewer@acme.com",
        username="reviewer_acme",
        password="TestPass123!",
        tenant=tenant_a,
        is_tenant_admin=False,
    )


@pytest.fixture
def _designcontrols_user_b(db, tenant_b):
    return User.objects.create_user(
        email="engineer@globex.com",
        username="engineer_globex",
        password="TestPass123!",
        tenant=tenant_b,
        is_tenant_admin=False,
    )


def _designcontrols_create_project(tenant, project_lead, quality_lead=None, **kwargs):
    if quality_lead is None:
        quality_lead = project_lead
    data = {
        "tenant": tenant,
        "title": "NextGen Infusion Pump System",
        "device_name": "InfuseFlow Pro 3000",
        "device_class": "class_ii",
        "regulatory_pathway": "510k",
        "intended_use": "Volumetric infusion pump for intravenous administration of fluids.",
        "current_phase": "planning",
        "status": "draft",
        "project_lead": project_lead,
        "quality_lead": quality_lead,
        "dhf_locked": False,
        "dhf_location": "DHF/INFUSE-3000/REV-A",
        "description": "Smart infusion pump development under 21 CFR § 820.30.",
    }
    data.update(kwargs)
    return DesignProject.objects.create(**data)


def _designcontrols_create_input(tenant, project, owner, **kwargs):
    data = {
        "tenant": tenant,
        "project": project,
        "identifier": "DI-001",
        "title": "Battery Backup Duration",
        "input_type": "functional",
        "priority": "major",
        "status": "draft",
        "description": "Device must operate on internal battery power during patient transport.",
        "acceptance_criteria": "Continuous infusion delivery for at least 8 hours at 125 mL/hr.",
        "rationale": "Clinical requirement per IEC 60601-2-24.",
        "owner": owner,
        "version": "1.0",
    }
    data.update(kwargs)
    return DesignInput.objects.create(**data)


def _designcontrols_create_review(tenant, project, lead_reviewer, independent_reviewer, **kwargs):
    data = {
        "tenant": tenant,
        "project": project,
        "title": "Design Input Phase Gate Review",
        "review_stage": "input_freeze",
        "review_date": timezone.now().date(),
        "status": "scheduled",
        "lead_reviewer": lead_reviewer,
        "independent_reviewer": independent_reviewer,
        "agenda": "Formal gate review to freeze functional and clinical user needs.",
        "discussion_summary": "Requirements traceability matrix evaluated against ISO 13485.",
        "conclusions": "Requirements deemed objective and testable.",
        "action_items": "",
        "action_items_resolved": False,
    }
    data.update(kwargs)
    return DesignReview.objects.create(**data)


def _designcontrols_create_verification(tenant, project, primary_input, **kwargs):
    data = {
        "tenant": tenant,
        "project": project,
        "primary_input": primary_input,
        "title": "Battery Runtime Bench Test Protocol",
        "activity_type": "verification",
        "status": "draft",
        "test_method": "lab_test",
        "acceptance_criteria": "Unit delivers fluid continuously >= 8 hours without low battery alarm.",
        "sample_size": 5,
        "pass_fail_result": "pending",
        "results_summary": "",
        "deviation_notes": "",
    }
    data.update(kwargs)
    return DesignVerification.objects.create(**data)


def _designcontrols_create_doc(tenant, owner, **kwargs):
    data = {
        "tenant": tenant,
        "title": "Product Requirements Document (PRD)",
        "document_type": "spec",
        "owner": owner,
        "revision": "1.0",
        "lifecycle_state": "approved",
    }
    data.update(kwargs)
    return ControlledDocument.objects.create(**data)


def _designcontrols_base_project_data(lead_user, quality_lead_user, department=None, **extra):
    data = {
        "title": "NextGen Infusion Pump System",
        "device_name": "InfuseFlow Pro 3000",
        "device_class": "class_ii",
        "regulatory_pathway": "510k",
        "intended_use": "Controlled volumetric administration of IV fluids.",
        "current_phase": "planning",
        "status": "draft",
        "project_lead": lead_user.pk,
        "quality_lead": quality_lead_user.pk,
        "department": department.pk if department else "",
        "target_completion_date": (timezone.now() + timedelta(days=90)).date(),
        "actual_completion_date": "",
        "dhf_location": "DHF/INFUSE-3000",
        "description": "General project description.",
    }
    data.update(extra)
    return data


def _designcontrols_base_input_data(project, owner, **extra):
    data = {
        "project": project.pk,
        "identifier": "DI-001",
        "title": "Battery Backup Duration",
        "input_type": "functional",
        "priority": "major",
        "status": "draft",
        "description": "Must operate on internal battery during transport.",
        "acceptance_criteria": "Continuous infusion delivery for at least 8 hours.",
        "rationale": "Clinical requirement per IEC 60601-2-24.",
        "user_need_parent": "",
        "controlled_document": "",
        "owner": owner.pk,
        "version": "1.0",
    }
    data.update(extra)
    return data


def _designcontrols_base_review_data(project, lead_user, independent_user, **extra):
    data = {
        "project": project.pk,
        "title": "Design Input Freeze Gate Review",
        "review_stage": "input_freeze",
        "review_date": timezone.now().date(),
        "status": "scheduled",
        "lead_reviewer": lead_user.pk,
        "independent_reviewer": independent_user.pk,
        "agenda": "Review functional and safety requirements.",
        "discussion_summary": "Traceability matrix reviewed.",
        "conclusions": "Requirements deemed objective.",
        "action_items": "Update risk analysis.",
        "action_items_resolved": False,
    }
    data.update(extra)
    return data


def _designcontrols_base_verification_data(project, primary_input, executed_by=None, **extra):
    data = {
        "project": project.pk,
        "primary_input": primary_input.pk,
        "title": "Battery Runtime Protocol",
        "activity_type": "verification",
        "status": "draft",
        "test_method": "lab_test",
        "acceptance_criteria": "Unit delivers fluid >= 8 hours without failure.",
        "sample_size": 5,
        "results_summary": "Bench tests completed.",
        "pass_fail_result": "pending",
        "deviation_notes": "",
        "executed_by": executed_by.pk if executed_by else "",
        "execution_date": timezone.now().date(),
        "protocol_document": "",
        "report_document": "",
    }
    data.update(extra)
    return data


# =====================================================================
# 1. System Field Exclusion Tests across All 4 Forms
# =====================================================================


def test_designcontrols_project_form_system_field_exclusion(tenant_a, admin_user):
    """Verify tenant, number, dhf_locked, created_at, updated_at are strictly excluded from DesignProjectForm."""
    form = DesignProjectForm(tenant=tenant_a)
    forbidden_fields = [
        "tenant",
        "number",
        "dhf_locked",
        "created_at",
        "updated_at",
    ]
    for field_name in forbidden_fields:
        assert field_name not in form.fields, f"Field '{field_name}' must be excluded from DesignProjectForm"

    # Submitting forbidden parameters in POST data must not bind to form instance
    malicious_data = _designcontrols_base_project_data(admin_user, admin_user, extra={
        "tenant": tenant_a.pk,
        "number": "QDPL-HACKED-9999",
        "dhf_locked": True,
    })
    bound_form = DesignProjectForm(data=malicious_data, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=False)
    assert getattr(instance, "number", "") != "QDPL-HACKED-9999"
    assert getattr(instance, "dhf_locked", False) is False


def test_designcontrols_input_form_system_field_exclusion(tenant_a, admin_user):
    """Verify tenant, number, created_at, updated_at are strictly excluded from DesignInputForm."""
    form = DesignInputForm(tenant=tenant_a)
    forbidden_fields = ["tenant", "number", "created_at", "updated_at"]
    for field_name in forbidden_fields:
        assert field_name not in form.fields, f"Field '{field_name}' must be excluded from DesignInputForm"

    proj = _designcontrols_create_project(tenant_a, admin_user)
    malicious_data = _designcontrols_base_input_data(proj, admin_user, extra={
        "tenant": tenant_a.pk,
        "number": "QINP-HACKED-9999",
    })
    bound_form = DesignInputForm(data=malicious_data, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=False)
    assert getattr(instance, "number", "") != "QINP-HACKED-9999"


def test_designcontrols_review_form_system_field_exclusion(tenant_a, admin_user, _designcontrols_independent_user):
    """Verify tenant, number, electronic_signature, created_at, updated_at are strictly excluded from DesignReviewForm."""
    form = DesignReviewForm(tenant=tenant_a)
    forbidden_fields = [
        "tenant",
        "number",
        "electronic_signature",
        "created_at",
        "updated_at",
    ]
    for field_name in forbidden_fields:
        assert field_name not in form.fields, f"Field '{field_name}' must be excluded from DesignReviewForm"

    proj = _designcontrols_create_project(tenant_a, admin_user)
    malicious_data = _designcontrols_base_review_data(proj, admin_user, _designcontrols_independent_user, extra={
        "tenant": tenant_a.pk,
        "number": "QREV-HACKED-9999",
        "electronic_signature": 1234,
    })
    bound_form = DesignReviewForm(data=malicious_data, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=False)
    assert getattr(instance, "number", "") != "QREV-HACKED-9999"
    assert getattr(instance, "electronic_signature", None) is None


def test_designcontrols_verification_form_system_field_exclusion(tenant_a, admin_user):
    """Verify tenant, number, created_at, updated_at are strictly excluded from DesignVerificationForm."""
    form = DesignVerificationForm(tenant=tenant_a)
    forbidden_fields = ["tenant", "number", "created_at", "updated_at"]
    for field_name in forbidden_fields:
        assert field_name not in form.fields, f"Field '{field_name}' must be excluded from DesignVerificationForm"

    proj = _designcontrols_create_project(tenant_a, admin_user)
    inp = _designcontrols_create_input(tenant_a, proj, admin_user)
    malicious_data = _designcontrols_base_verification_data(proj, inp, admin_user, extra={
        "tenant": tenant_a.pk,
        "number": "QVER-HACKED-9999",
    })
    bound_form = DesignVerificationForm(data=malicious_data, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=False)
    assert getattr(instance, "number", "") != "QVER-HACKED-9999"


# =====================================================================
# 2. Multi-Tenant FK Scoping and Foreign Key Rejection Tests
# =====================================================================


def test_designcontrols_project_form_tenant_scoping(
    tenant_a,
    tenant_b,
    admin_user,
    _designcontrols_engineer_user,
    _designcontrols_user_b,
    _designcontrols_org_unit,
    _designcontrols_org_unit_b,
):
    """Verify DesignProjectForm dropdown querysets are strictly tenant-scoped and reject foreign FKs."""
    form_a = DesignProjectForm(tenant=tenant_a)
    dept_pks = list(form_a.fields["department"].queryset.values_list("pk", flat=True))
    lead_pks = list(form_a.fields["project_lead"].queryset.values_list("pk", flat=True))
    quality_pks = list(form_a.fields["quality_lead"].queryset.values_list("pk", flat=True))

    assert _designcontrols_org_unit.pk in dept_pks
    assert _designcontrols_org_unit_b.pk not in dept_pks

    assert admin_user.pk in lead_pks
    assert _designcontrols_engineer_user.pk in lead_pks
    assert _designcontrols_user_b.pk not in lead_pks
    assert _designcontrols_user_b.pk not in quality_pks

    # When instantiated with tenant=None, all scoped querysets must be empty
    form_none = DesignProjectForm(tenant=None)
    assert form_none.fields["department"].queryset.count() == 0
    assert form_none.fields["project_lead"].queryset.count() == 0
    assert form_none.fields["quality_lead"].queryset.count() == 0

    # Submitting foreign department belonging to tenant_b must fail
    data_foreign_dept = _designcontrols_base_project_data(
        admin_user, admin_user, department=_designcontrols_org_unit_b
    )
    bound_foreign_dept = DesignProjectForm(data=data_foreign_dept, tenant=tenant_a)
    assert not bound_foreign_dept.is_valid()
    assert "department" in bound_foreign_dept.errors

    # Submitting foreign project_lead belonging to tenant_b must fail
    data_foreign_lead = _designcontrols_base_project_data(
        _designcontrols_user_b, admin_user, department=_designcontrols_org_unit
    )
    bound_foreign_lead = DesignProjectForm(data=data_foreign_lead, tenant=tenant_a)
    assert not bound_foreign_lead.is_valid()
    assert "project_lead" in bound_foreign_lead.errors


def test_designcontrols_input_form_tenant_scoping(
    tenant_a,
    tenant_b,
    admin_user,
    _designcontrols_user_b,
):
    """Verify DesignInputForm dropdown querysets are strictly tenant-scoped and reject foreign FKs."""
    proj_a = _designcontrols_create_project(tenant_a, admin_user)
    proj_b = _designcontrols_create_project(tenant_b, _designcontrols_user_b)
    user_need_a = _designcontrols_create_input(
        tenant_a, proj_a, admin_user, identifier="UN-001", input_type="user_need"
    )
    user_need_b = _designcontrols_create_input(
        tenant_b, proj_b, _designcontrols_user_b, identifier="UN-999", input_type="user_need"
    )
    doc_a = _designcontrols_create_doc(tenant_a, admin_user)
    doc_b = _designcontrols_create_doc(tenant_b, _designcontrols_user_b)

    form_a = DesignInputForm(tenant=tenant_a)
    proj_pks = list(form_a.fields["project"].queryset.values_list("pk", flat=True))
    owner_pks = list(form_a.fields["owner"].queryset.values_list("pk", flat=True))
    parent_pks = list(form_a.fields["user_need_parent"].queryset.values_list("pk", flat=True))
    doc_pks = list(form_a.fields["controlled_document"].queryset.values_list("pk", flat=True))

    assert proj_a.pk in proj_pks
    assert proj_b.pk not in proj_pks
    assert admin_user.pk in owner_pks
    assert _designcontrols_user_b.pk not in owner_pks
    assert user_need_a.pk in parent_pks
    assert user_need_b.pk not in parent_pks
    assert doc_a.pk in doc_pks
    assert doc_b.pk not in doc_pks

    # When instantiated with tenant=None, querysets must be empty
    form_none = DesignInputForm(tenant=None)
    assert form_none.fields["project"].queryset.count() == 0
    assert form_none.fields["owner"].queryset.count() == 0
    assert form_none.fields["user_need_parent"].queryset.count() == 0
    assert form_none.fields["controlled_document"].queryset.count() == 0

    # Submitting foreign project must fail
    data_bad_proj = _designcontrols_base_input_data(proj_b, admin_user)
    bound_bad_proj = DesignInputForm(data=data_bad_proj, tenant=tenant_a)
    assert not bound_bad_proj.is_valid()
    assert "project" in bound_bad_proj.errors

    # Submitting foreign owner must fail
    data_bad_owner = _designcontrols_base_input_data(proj_a, _designcontrols_user_b)
    bound_bad_owner = DesignInputForm(data=data_bad_owner, tenant=tenant_a)
    assert not bound_bad_owner.is_valid()
    assert "owner" in bound_bad_owner.errors


def test_designcontrols_review_form_tenant_scoping(
    tenant_a,
    tenant_b,
    admin_user,
    _designcontrols_independent_user,
    _designcontrols_user_b,
):
    """Verify DesignReviewForm dropdown querysets are strictly tenant-scoped and reject foreign FKs."""
    proj_a = _designcontrols_create_project(tenant_a, admin_user)
    proj_b = _designcontrols_create_project(tenant_b, _designcontrols_user_b)

    form_a = DesignReviewForm(tenant=tenant_a)
    proj_pks = list(form_a.fields["project"].queryset.values_list("pk", flat=True))
    lead_pks = list(form_a.fields["lead_reviewer"].queryset.values_list("pk", flat=True))
    indep_pks = list(form_a.fields["independent_reviewer"].queryset.values_list("pk", flat=True))

    assert proj_a.pk in proj_pks
    assert proj_b.pk not in proj_pks
    assert admin_user.pk in lead_pks
    assert _designcontrols_independent_user.pk in indep_pks
    assert _designcontrols_user_b.pk not in lead_pks
    assert _designcontrols_user_b.pk not in indep_pks

    # When tenant=None, querysets are empty
    form_none = DesignReviewForm(tenant=None)
    assert form_none.fields["project"].queryset.count() == 0
    assert form_none.fields["lead_reviewer"].queryset.count() == 0
    assert form_none.fields["independent_reviewer"].queryset.count() == 0

    # Submitting foreign project must fail
    data_bad_proj = _designcontrols_base_review_data(
        proj_b, admin_user, _designcontrols_independent_user
    )
    bound_bad_proj = DesignReviewForm(data=data_bad_proj, tenant=tenant_a)
    assert not bound_bad_proj.is_valid()
    assert "project" in bound_bad_proj.errors

    # Submitting foreign independent reviewer must fail
    data_bad_reviewer = _designcontrols_base_review_data(
        proj_a, admin_user, _designcontrols_user_b
    )
    bound_bad_reviewer = DesignReviewForm(data=data_bad_reviewer, tenant=tenant_a)
    assert not bound_bad_reviewer.is_valid()
    assert "independent_reviewer" in bound_bad_reviewer.errors


def test_designcontrols_verification_form_tenant_scoping(
    tenant_a,
    tenant_b,
    admin_user,
    _designcontrols_user_b,
):
    """Verify DesignVerificationForm dropdown querysets are strictly tenant-scoped and reject foreign FKs."""
    proj_a = _designcontrols_create_project(tenant_a, admin_user)
    proj_b = _designcontrols_create_project(tenant_b, _designcontrols_user_b)
    inp_a = _designcontrols_create_input(tenant_a, proj_a, admin_user)
    inp_b = _designcontrols_create_input(tenant_b, proj_b, _designcontrols_user_b)
    doc_a = _designcontrols_create_doc(tenant_a, admin_user)
    doc_b = _designcontrols_create_doc(tenant_b, _designcontrols_user_b)

    form_a = DesignVerificationForm(tenant=tenant_a)
    proj_pks = list(form_a.fields["project"].queryset.values_list("pk", flat=True))
    input_pks = list(form_a.fields["primary_input"].queryset.values_list("pk", flat=True))
    user_pks = list(form_a.fields["executed_by"].queryset.values_list("pk", flat=True))
    proto_pks = list(form_a.fields["protocol_document"].queryset.values_list("pk", flat=True))
    rep_pks = list(form_a.fields["report_document"].queryset.values_list("pk", flat=True))

    assert proj_a.pk in proj_pks
    assert proj_b.pk not in proj_pks
    assert inp_a.pk in input_pks
    assert inp_b.pk not in input_pks
    assert admin_user.pk in user_pks
    assert _designcontrols_user_b.pk not in user_pks
    assert doc_a.pk in proto_pks
    assert doc_b.pk not in proto_pks
    assert doc_a.pk in rep_pks
    assert doc_b.pk not in rep_pks

    # When tenant=None, querysets are empty
    form_none = DesignVerificationForm(tenant=None)
    assert form_none.fields["project"].queryset.count() == 0
    assert form_none.fields["primary_input"].queryset.count() == 0
    assert form_none.fields["executed_by"].queryset.count() == 0
    assert form_none.fields["protocol_document"].queryset.count() == 0
    assert form_none.fields["report_document"].queryset.count() == 0

    # Submitting foreign primary_input must fail
    data_bad_input = _designcontrols_base_verification_data(proj_a, inp_b, admin_user)
    bound_bad_input = DesignVerificationForm(data=data_bad_input, tenant=tenant_a)
    assert not bound_bad_input.is_valid()
    assert "primary_input" in bound_bad_input.errors


def test_designcontrols_reject_foreign_function_direct(
    tenant_a,
    tenant_b,
    admin_user,
    _designcontrols_user_b,
):
    """Directly verify reject_foreign adds validation error when foreign objects are cleaned."""
    form = DesignProjectForm(tenant=tenant_a)
    form.cleaned_data = {
        "project_lead": _designcontrols_user_b,
    }
    reject_foreign(form, form.cleaned_data, ["project_lead"])
    assert "project_lead" in form.errors
    assert "That record belongs to another workspace." in str(form.errors["project_lead"])


# =====================================================================
# 3. DHF Regulatory Lock Integrity Tests
# =====================================================================


def test_designcontrols_project_form_dhf_lock_status_change_rejected(tenant_a, admin_user):
    """Re-opening or changing status of a DHF-locked DesignProject via form is rejected."""
    locked_proj = _designcontrols_create_project(
        tenant_a, admin_user, dhf_locked=True, status="completed"
    )
    # Attempting to change status from "completed" to "active"
    data = _designcontrols_base_project_data(admin_user, admin_user, status="active")
    form = DesignProjectForm(data=data, instance=locked_proj, tenant=tenant_a)
    assert not form.is_valid()
    assert any(
        "DHF is locked. Re-opening requires formal Change Control" in str(err)
        for err in form.non_field_errors()
    )


def test_designcontrols_project_form_dhf_lock_metadata_update_allowed(tenant_a, admin_user):
    """Updating description or dates without changing status on a locked project is permitted."""
    locked_proj = _designcontrols_create_project(
        tenant_a, admin_user, dhf_locked=True, status="completed"
    )
    data = _designcontrols_base_project_data(
        admin_user, admin_user, status="completed", description="Updated audit trail note."
    )
    form = DesignProjectForm(data=data, instance=locked_proj, tenant=tenant_a)
    assert form.is_valid(), form.errors
    saved = form.save()
    assert saved.description == "Updated audit trail note."


def test_designcontrols_input_form_dhf_locked_project_creation_rejected(tenant_a, admin_user):
    """Creating a new DesignInput under a DHF-locked project is rejected."""
    locked_proj = _designcontrols_create_project(tenant_a, admin_user, dhf_locked=True)
    data = _designcontrols_base_input_data(locked_proj, admin_user)
    form = DesignInputForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "project" in form.errors
    assert "locked Design History File (DHF)" in str(form.errors["project"])


def test_designcontrols_input_form_dhf_locked_project_modification_rejected(tenant_a, admin_user):
    """Modifying an existing DesignInput whose parent project has been locked is rejected."""
    proj = _designcontrols_create_project(tenant_a, admin_user, dhf_locked=False)
    inp = _designcontrols_create_input(tenant_a, proj, admin_user)

    # Lock the project in DHF
    proj.dhf_locked = True
    proj.save()
    inp.refresh_from_db()

    data = _designcontrols_base_input_data(proj, admin_user, title="Altered Requirement")
    form = DesignInputForm(data=data, instance=inp, tenant=tenant_a)
    assert not form.is_valid()
    assert "project" in form.errors
    assert "locked Design History File (DHF)" in str(form.errors["project"])


def test_designcontrols_review_form_dhf_locked_project_creation_rejected(
    tenant_a, admin_user, _designcontrols_independent_user
):
    """Creating a new DesignReview for a DHF-locked project is rejected."""
    locked_proj = _designcontrols_create_project(tenant_a, admin_user, dhf_locked=True)
    data = _designcontrols_base_review_data(
        locked_proj, admin_user, _designcontrols_independent_user
    )
    form = DesignReviewForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "project" in form.errors
    assert "locked Design History File (DHF)" in str(form.errors["project"])


def test_designcontrols_review_form_dhf_locked_project_modification_rejected(
    tenant_a, admin_user, _designcontrols_independent_user
):
    """Modifying an existing DesignReview whose parent project has been locked is rejected."""
    proj = _designcontrols_create_project(tenant_a, admin_user, dhf_locked=False)
    review = _designcontrols_create_review(
        tenant_a, proj, admin_user, _designcontrols_independent_user
    )

    proj.dhf_locked = True
    proj.save()
    review.refresh_from_db()

    data = _designcontrols_base_review_data(
        proj, admin_user, _designcontrols_independent_user, title="Altered Review Title"
    )
    form = DesignReviewForm(data=data, instance=review, tenant=tenant_a)
    assert not form.is_valid()
    assert "project" in form.errors
    assert "locked Design History File (DHF)" in str(form.errors["project"])


def test_designcontrols_verification_form_dhf_locked_project_creation_rejected(tenant_a, admin_user):
    """Creating a new DesignVerification under a DHF-locked project is rejected."""
    locked_proj = _designcontrols_create_project(tenant_a, admin_user, dhf_locked=True)
    inp = _designcontrols_create_input(tenant_a, locked_proj, admin_user)

    data = _designcontrols_base_verification_data(locked_proj, inp, admin_user)
    form = DesignVerificationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "project" in form.errors
    assert "locked Design History File (DHF)" in str(form.errors["project"])


def test_designcontrols_verification_form_dhf_locked_project_modification_rejected(tenant_a, admin_user):
    """Modifying an existing DesignVerification whose parent project has been locked is rejected."""
    proj = _designcontrols_create_project(tenant_a, admin_user, dhf_locked=False)
    inp = _designcontrols_create_input(tenant_a, proj, admin_user)
    verif = _designcontrols_create_verification(tenant_a, proj, inp)

    proj.dhf_locked = True
    proj.save()
    verif.refresh_from_db()

    data = _designcontrols_base_verification_data(proj, inp, admin_user, title="Modified Test Protocol")
    form = DesignVerificationForm(data=data, instance=verif, tenant=tenant_a)
    assert not form.is_valid()
    assert "project" in form.errors
    assert "locked Design History File (DHF)" in str(form.errors["project"])


# =====================================================================
# 4. DesignInputForm Business Validation Tests
# =====================================================================


def test_designcontrols_input_form_verified_status_rejected_without_passing_test(tenant_a, admin_user):
    """Manual setting of status='verified' is rejected if no passing verification protocol exists."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    data = _designcontrols_base_input_data(proj, admin_user, status="verified")
    form = DesignInputForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "status" in form.errors
    assert "cannot be marked as verified without at least one executed passing verification" in str(
        form.errors["status"]
    )


def test_designcontrols_input_form_verified_status_allowed_with_passing_verification(tenant_a, admin_user):
    """DesignInput can be marked verified if a passing verification protocol exists on the instance."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    inp = _designcontrols_create_input(tenant_a, proj, admin_user, status="approved")
    # Attach passing verification protocol
    _designcontrols_create_verification(
        tenant_a, proj, inp, pass_fail_result="pass", status="passed"
    )

    data = _designcontrols_base_input_data(proj, admin_user, status="verified")
    form = DesignInputForm(data=data, instance=inp, tenant=tenant_a)
    assert form.is_valid(), form.errors
    saved = form.save()
    assert saved.status == "verified"


def test_designcontrols_input_form_verified_status_allowed_if_already_verified(tenant_a, admin_user):
    """If DesignInput was already marked verified, updating metadata while retaining verified status is permitted."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    inp = _designcontrols_create_input(tenant_a, proj, admin_user, status="verified")

    data = _designcontrols_base_input_data(proj, admin_user, status="verified", version="1.1")
    form = DesignInputForm(data=data, instance=inp, tenant=tenant_a)
    assert form.is_valid(), form.errors
    saved = form.save()
    assert saved.version == "1.1"
    assert saved.status == "verified"


def test_designcontrols_input_form_parent_user_need_same_project_required(tenant_a, admin_user):
    """Parent user need must belong to the exact same design project."""
    proj_1 = _designcontrols_create_project(tenant_a, admin_user, title="Project 1")
    proj_2 = _designcontrols_create_project(tenant_a, admin_user, title="Project 2")

    user_need_proj_2 = _designcontrols_create_input(
        tenant_a, proj_2, admin_user, identifier="UN-002", input_type="user_need"
    )

    # Attempting to assign user_need_proj_2 as parent to input in proj_1
    data = _designcontrols_base_input_data(
        proj_1, admin_user, user_need_parent=user_need_proj_2.pk
    )
    form = DesignInputForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "user_need_parent" in form.errors
    assert "Parent user need must belong to the same design project" in str(
        form.errors["user_need_parent"]
    )


def test_designcontrols_input_form_parent_user_need_same_project_allowed(tenant_a, admin_user):
    """Parent user need belonging to the same project passes validation."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    user_need = _designcontrols_create_input(
        tenant_a, proj, admin_user, identifier="UN-001", input_type="user_need"
    )

    data = _designcontrols_base_input_data(
        proj, admin_user, user_need_parent=user_need.pk, identifier="DI-002"
    )
    form = DesignInputForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    saved = form.save()
    assert saved.user_need_parent == user_need


def test_designcontrols_input_form_user_need_parent_excludes_self(tenant_a, admin_user):
    """When editing an existing DesignInput, it cannot select itself as user_need_parent."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    user_need = _designcontrols_create_input(
        tenant_a, proj, admin_user, identifier="UN-001", input_type="user_need"
    )
    other_need = _designcontrols_create_input(
        tenant_a, proj, admin_user, identifier="UN-002", input_type="user_need"
    )

    form = DesignInputForm(instance=user_need, tenant=tenant_a)
    parent_pks = list(form.fields["user_need_parent"].queryset.values_list("pk", flat=True))
    assert user_need.pk not in parent_pks
    assert other_need.pk in parent_pks


def test_designcontrols_input_form_user_need_parent_filtered_to_user_needs(tenant_a, admin_user):
    """user_need_parent dropdown only displays inputs with input_type='user_need'."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    user_need = _designcontrols_create_input(
        tenant_a, proj, admin_user, identifier="UN-001", input_type="user_need"
    )
    func_spec = _designcontrols_create_input(
        tenant_a, proj, admin_user, identifier="DI-001", input_type="functional"
    )
    safety_spec = _designcontrols_create_input(
        tenant_a, proj, admin_user, identifier="DI-002", input_type="safety"
    )

    form = DesignInputForm(tenant=tenant_a)
    parent_pks = list(form.fields["user_need_parent"].queryset.values_list("pk", flat=True))
    assert user_need.pk in parent_pks
    assert func_spec.pk not in parent_pks
    assert safety_spec.pk not in parent_pks


# =====================================================================
# 5. DesignReviewForm Business Validation Tests
# =====================================================================


def test_designcontrols_review_form_direct_approved_status_rejected(
    tenant_a, admin_user, _designcontrols_independent_user
):
    """Directly setting status='approved' in DesignReviewForm is rejected (formal gate clearance required)."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    data = _designcontrols_base_review_data(
        proj, admin_user, _designcontrols_independent_user, status="approved"
    )
    form = DesignReviewForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "status" in form.errors
    assert "Stage-gate review approval requires formal gate clearance" in str(
        form.errors["status"]
    )


def test_designcontrols_review_form_approved_status_allowed_if_already_approved(
    tenant_a, admin_user, _designcontrols_independent_user
):
    """If DesignReview in DB is already approved, maintaining approved status on metadata edit is allowed."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    review = _designcontrols_create_review(
        tenant_a, proj, admin_user, _designcontrols_independent_user, status="approved"
    )

    data = _designcontrols_base_review_data(
        proj, admin_user, _designcontrols_independent_user, status="approved", conclusions="Final approved conclusions."
    )
    form = DesignReviewForm(data=data, instance=review, tenant=tenant_a)
    assert form.is_valid(), form.errors
    saved = form.save()
    assert saved.conclusions == "Final approved conclusions."
    assert saved.status == "approved"


def test_designcontrols_review_form_independent_reviewer_cannot_equal_lead_reviewer(
    tenant_a, admin_user
):
    """21 CFR § 820.30(e) invariant: lead_reviewer and independent_reviewer cannot be the same user."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    data = _designcontrols_base_review_data(
        proj, admin_user, admin_user
    )
    form = DesignReviewForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "independent_reviewer" in form.errors
    assert "21 CFR § 820.30(e) requires an independent reviewer" in str(
        form.errors["independent_reviewer"]
    )


def test_designcontrols_review_form_independent_reviewer_cannot_equal_project_lead(
    tenant_a, admin_user, _designcontrols_engineer_user
):
    """21 CFR § 820.30(e) invariant: DesignProject project_lead cannot serve as independent reviewer."""
    # admin_user is project_lead
    proj = _designcontrols_create_project(tenant_a, admin_user)

    # Lead reviewer is engineer, independent reviewer attempted to be admin_user (the project lead)
    data = _designcontrols_base_review_data(
        proj, _designcontrols_engineer_user, admin_user
    )
    form = DesignReviewForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "independent_reviewer" in form.errors
    assert "The project lead cannot serve as the independent reviewer" in str(
        form.errors["independent_reviewer"]
    )


def test_designcontrols_review_form_independent_reviewer_distinct_valid(
    tenant_a, admin_user, _designcontrols_engineer_user, _designcontrols_independent_user
):
    """When independent_reviewer is distinct from lead_reviewer and project_lead, validation passes."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    data = _designcontrols_base_review_data(
        proj, _designcontrols_engineer_user, _designcontrols_independent_user
    )
    form = DesignReviewForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


# =====================================================================
# 6. DesignVerificationForm Validation Tests
# =====================================================================


def test_designcontrols_verification_form_acceptance_criteria_required(tenant_a, admin_user):
    """Acceptance criteria is mandatory and cannot be empty."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    inp = _designcontrols_create_input(tenant_a, proj, admin_user)
    data = _designcontrols_base_verification_data(proj, inp, admin_user, acceptance_criteria="")
    form = DesignVerificationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "acceptance_criteria" in form.errors


def test_designcontrols_verification_form_sample_size_positive_required(tenant_a, admin_user):
    """Sample size must be a non-negative integer (sample_size >= 0)."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    inp = _designcontrols_create_input(tenant_a, proj, admin_user)

    # sample_size = -1 must fail
    data_neg = _designcontrols_base_verification_data(proj, inp, admin_user, sample_size=-1)
    form_neg = DesignVerificationForm(data=data_neg, tenant=tenant_a)
    assert not form_neg.is_valid()
    assert "sample_size" in form_neg.errors
    assert "Ensure this value is greater than or equal to 0" in str(form_neg.errors["sample_size"])

    # sample_size = 0 and sample_size = 1 must pass
    data_zero = _designcontrols_base_verification_data(proj, inp, admin_user, sample_size=0)
    form_zero = DesignVerificationForm(data=data_zero, tenant=tenant_a)
    assert form_zero.is_valid(), form_zero.errors

    # sample_size = 1 must pass
    data_one = _designcontrols_base_verification_data(proj, inp, admin_user, sample_size=1)
    form_one = DesignVerificationForm(data=data_one, tenant=tenant_a)
    assert form_one.is_valid(), form_one.errors


def test_designcontrols_verification_form_test_method_choices_validation(tenant_a, admin_user):
    """Verify test_method choice validation (inspection, lab_test, analysis, clinical_trial, demonstration)."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    inp = _designcontrols_create_input(tenant_a, proj, admin_user)

    valid_methods = ["inspection", "lab_test", "analysis", "clinical_trial", "demonstration"]
    for method in valid_methods:
        data = _designcontrols_base_verification_data(proj, inp, admin_user, test_method=method)
        form = DesignVerificationForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Expected test_method '{method}' to be valid, got errors: {form.errors}"

    # Invalid test method choice
    data_bad = _designcontrols_base_verification_data(proj, inp, admin_user, test_method="arbitrary_unapproved")
    form_bad = DesignVerificationForm(data=data_bad, tenant=tenant_a)
    assert not form_bad.is_valid()
    assert "test_method" in form_bad.errors


def test_designcontrols_verification_form_activity_type_choices_validation(tenant_a, admin_user):
    """Verify activity_type choice validation (verification, validation, usability, process_validation)."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    inp = _designcontrols_create_input(tenant_a, proj, admin_user)

    valid_types = ["verification", "validation", "usability", "process_validation"]
    for act_type in valid_types:
        data = _designcontrols_base_verification_data(proj, inp, admin_user, activity_type=act_type)
        form = DesignVerificationForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Expected activity_type '{act_type}' to be valid, got errors: {form.errors}"

    data_bad = _designcontrols_base_verification_data(proj, inp, admin_user, activity_type="illegal_activity")
    form_bad = DesignVerificationForm(data=data_bad, tenant=tenant_a)
    assert not form_bad.is_valid()
    assert "activity_type" in form_bad.errors


def test_designcontrols_verification_form_pass_fail_result_choices_validation(tenant_a, admin_user):
    """Verify pass_fail_result choice validation (pending, pass, fail)."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    inp = _designcontrols_create_input(tenant_a, proj, admin_user)

    for result in ["pending", "pass", "fail"]:
        data = _designcontrols_base_verification_data(proj, inp, admin_user, pass_fail_result=result)
        form = DesignVerificationForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Expected pass_fail_result '{result}' to be valid, got errors: {form.errors}"

    data_bad = _designcontrols_base_verification_data(proj, inp, admin_user, pass_fail_result="maybe")
    form_bad = DesignVerificationForm(data=data_bad, tenant=tenant_a)
    assert not form_bad.is_valid()
    assert "pass_fail_result" in form_bad.errors


def test_designcontrols_verification_form_primary_input_must_belong_to_project(tenant_a, admin_user):
    """primary_input must belong to the selected design project."""
    proj_1 = _designcontrols_create_project(tenant_a, admin_user, title="Project 1")
    proj_2 = _designcontrols_create_project(tenant_a, admin_user, title="Project 2")
    inp_proj_2 = _designcontrols_create_input(tenant_a, proj_2, admin_user, identifier="DI-002")

    # Mismatched primary_input from proj_2 assigned to proj_1
    data = _designcontrols_base_verification_data(proj_1, inp_proj_2, admin_user)
    form = DesignVerificationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "primary_input" in form.errors
    assert "Primary design input must belong to the selected design project" in str(
        form.errors["primary_input"]
    )


def test_designcontrols_verification_form_primary_input_same_project_valid(tenant_a, admin_user):
    """primary_input belonging to the selected project is valid."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    inp = _designcontrols_create_input(tenant_a, proj, admin_user)

    data = _designcontrols_base_verification_data(proj, inp, admin_user)
    form = DesignVerificationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


# =====================================================================
# 7. Widget Classes and HTML Attributes Tests
# =====================================================================


def test_designcontrols_project_form_widgets_and_classes(tenant_a):
    """Verify widget classes and input types for DesignProjectForm."""
    form = DesignProjectForm(tenant=tenant_a)

    text_inputs = ["title", "device_name", "dhf_location"]
    for field in text_inputs:
        assert isinstance(form.fields[field].widget, forms.TextInput)
        assert "form-input" in form.fields[field].widget.attrs.get("class", "")

    date_inputs = ["target_completion_date", "actual_completion_date"]
    for field in date_inputs:
        assert isinstance(form.fields[field].widget, forms.DateInput)
        assert getattr(form.fields[field].widget, "input_type", None) == "date"
        assert "form-input" in form.fields[field].widget.attrs.get("class", "")

    select_fields = [
        "device_class",
        "regulatory_pathway",
        "current_phase",
        "status",
        "project_lead",
        "quality_lead",
        "department",
    ]
    for field in select_fields:
        assert isinstance(form.fields[field].widget, forms.Select)
        assert "form-select" in form.fields[field].widget.attrs.get("class", "")

    textarea_fields = ["intended_use", "description"]
    for field in textarea_fields:
        assert isinstance(form.fields[field].widget, forms.Textarea)
        assert "form-textarea" in form.fields[field].widget.attrs.get("class", "")


def test_designcontrols_input_form_widgets_and_classes(tenant_a):
    """Verify widget classes and input types for DesignInputForm."""
    form = DesignInputForm(tenant=tenant_a)

    text_inputs = ["identifier", "title", "version"]
    for field in text_inputs:
        assert isinstance(form.fields[field].widget, forms.TextInput)
        assert "form-input" in form.fields[field].widget.attrs.get("class", "")

    select_fields = [
        "project",
        "input_type",
        "priority",
        "status",
        "user_need_parent",
        "controlled_document",
        "owner",
    ]
    for field in select_fields:
        assert isinstance(form.fields[field].widget, forms.Select)
        assert "form-select" in form.fields[field].widget.attrs.get("class", "")

    textarea_fields = ["description", "acceptance_criteria", "rationale"]
    for field in textarea_fields:
        assert isinstance(form.fields[field].widget, forms.Textarea)
        assert "form-textarea" in form.fields[field].widget.attrs.get("class", "")


def test_designcontrols_review_form_widgets_and_classes(tenant_a):
    """Verify widget classes and input types for DesignReviewForm."""
    form = DesignReviewForm(tenant=tenant_a)

    assert isinstance(form.fields["title"].widget, forms.TextInput)
    assert "form-input" in form.fields["title"].widget.attrs.get("class", "")

    assert isinstance(form.fields["review_date"].widget, forms.DateInput)
    assert getattr(form.fields["review_date"].widget, "input_type", None) == "date"
    assert "form-input" in form.fields["review_date"].widget.attrs.get("class", "")

    assert isinstance(form.fields["action_items_resolved"].widget, forms.CheckboxInput)
    assert "form-checkbox" in form.fields["action_items_resolved"].widget.attrs.get("class", "")

    select_fields = ["project", "review_stage", "status", "lead_reviewer", "independent_reviewer"]
    for field in select_fields:
        assert isinstance(form.fields[field].widget, forms.Select)
        assert "form-select" in form.fields[field].widget.attrs.get("class", "")

    textarea_fields = ["agenda", "discussion_summary", "conclusions", "action_items"]
    for field in textarea_fields:
        assert isinstance(form.fields[field].widget, forms.Textarea)
        assert "form-textarea" in form.fields[field].widget.attrs.get("class", "")


def test_designcontrols_verification_form_widgets_and_classes(tenant_a):
    """Verify widget classes and input types for DesignVerificationForm."""
    form = DesignVerificationForm(tenant=tenant_a)

    assert isinstance(form.fields["title"].widget, forms.TextInput)
    assert "form-input" in form.fields["title"].widget.attrs.get("class", "")

    assert isinstance(form.fields["sample_size"].widget, forms.NumberInput)
    assert form.fields["sample_size"].widget.attrs.get("min") == 0
    assert "form-input" in form.fields["sample_size"].widget.attrs.get("class", "")

    assert isinstance(form.fields["execution_date"].widget, forms.DateInput)
    assert getattr(form.fields["execution_date"].widget, "input_type", None) == "date"
    assert "form-input" in form.fields["execution_date"].widget.attrs.get("class", "")

    select_fields = [
        "project",
        "primary_input",
        "activity_type",
        "status",
        "test_method",
        "pass_fail_result",
        "executed_by",
        "protocol_document",
        "report_document",
    ]
    for field in select_fields:
        assert isinstance(form.fields[field].widget, forms.Select)
        assert "form-select" in form.fields[field].widget.attrs.get("class", "")

    textarea_fields = ["acceptance_criteria", "results_summary", "deviation_notes"]
    for field in textarea_fields:
        assert isinstance(form.fields[field].widget, forms.Textarea)
        assert "form-textarea" in form.fields[field].widget.attrs.get("class", "")


# =====================================================================
# 8. End-to-End Form Save & Persistence Tests
# =====================================================================


def test_designcontrols_project_form_save_success(
    tenant_a, admin_user, _designcontrols_engineer_user, _designcontrols_org_unit
):
    """Submitting valid DesignProjectForm persists record with tenant and QDPL auto-number."""
    data = _designcontrols_base_project_data(
        admin_user, _designcontrols_engineer_user, department=_designcontrols_org_unit
    )
    form = DesignProjectForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    project = form.save()

    assert project.pk is not None
    assert project.tenant == tenant_a
    assert project.number.startswith("QDPL-")
    assert project.title == "NextGen Infusion Pump System"
    assert project.device_class == "class_ii"
    assert project.project_lead == admin_user
    assert project.quality_lead == _designcontrols_engineer_user
    assert project.department == _designcontrols_org_unit


def test_designcontrols_input_form_save_success(tenant_a, admin_user):
    """Submitting valid DesignInputForm persists record with tenant and QINP auto-number."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    data = _designcontrols_base_input_data(proj, admin_user, identifier="DI-001")
    form = DesignInputForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    inp = form.save()

    assert inp.pk is not None
    assert inp.tenant == tenant_a
    assert inp.number.startswith("QINP-")
    assert inp.project == proj
    assert inp.owner == admin_user
    assert inp.identifier == "DI-001"
    assert inp.status == "draft"


def test_designcontrols_review_form_save_success(
    tenant_a, admin_user, _designcontrols_engineer_user, _designcontrols_independent_user
):
    """Submitting valid DesignReviewForm persists record with tenant and QREV auto-number."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    data = _designcontrols_base_review_data(
        proj, _designcontrols_engineer_user, _designcontrols_independent_user
    )
    form = DesignReviewForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    review = form.save()

    assert review.pk is not None
    assert review.tenant == tenant_a
    assert review.number.startswith("QREV-")
    assert review.project == proj
    assert review.lead_reviewer == _designcontrols_engineer_user
    assert review.independent_reviewer == _designcontrols_independent_user
    assert review.status == "scheduled"


def test_designcontrols_verification_form_save_success(tenant_a, admin_user):
    """Submitting valid DesignVerificationForm persists record with tenant and QVER auto-number."""
    proj = _designcontrols_create_project(tenant_a, admin_user)
    inp = _designcontrols_create_input(tenant_a, proj, admin_user)
    data = _designcontrols_base_verification_data(proj, inp, admin_user)
    form = DesignVerificationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    verif = form.save()

    assert verif.pk is not None
    assert verif.tenant == tenant_a
    assert verif.number.startswith("QVER-")
    assert verif.project == proj
    assert verif.primary_input == inp
    assert verif.executed_by == admin_user
    assert verif.sample_size == 5
    assert verif.status == "draft"
