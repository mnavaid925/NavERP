"""Unit tests for Sub-module 13.9: Records Management & Compliance forms in apps.documents.

Tests the five forms:
1. RetentionScheduleForm:
   - Valid submission with required fields
   - Tenant scoping of department dropdown (reject foreign tenant departments)
   - Retention period validation: negative period rejection, years/months validation
   - Code uniqueness within tenant (case-insensitive, exclude self on edit)
   - Regulatory WORM schedules validation: must have retention period > 0 or be permanent
   - Field exclusions and widget classes
2. RecordDeclarationForm:
   - Valid submission with document, version, retention schedule
   - Tenant scoping of document, version, and retention schedule dropdowns
   - Clean method: duplicate active record declaration rejection on same document (finding I1)
   - Immutability check on edit: cannot alter document, version, or retention schedule once saved (finding C4)
   - Version dropdown .select_related('document') and document filtering on instance
   - Mismatched document and version rejection
   - Optional version support
3. DocumentLegalHoldForm:
   - Valid submission with document, matter_name, hold_reason, custodian, core_legal_hold
   - Tenant scoping of document, custodian, and core_legal_hold dropdowns
   - Custodian and core_legal_hold optional
   - Widget classes verification
4. LegalHoldReleaseForm:
   - Requires non-empty release_justification
   - Valid form validation and cleaned_data
   - Textarea widget attributes
5. DestructionCertificateForm:
   - Valid submission with record_declaration, disposition_type, destruction_method
   - Tenant scoping of record_declaration dropdown
   - Exclusion of already disposed records from queryset
   - Rejection if record declaration is under active legal hold
   - Acceptance when legal hold is released
   - Method choices and widget validation
"""
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.models import LegalHold as CoreLegalHold, OrgUnit
from apps.documents.forms import (
    DestructionCertificateForm,
    DocumentLegalHoldForm,
    LegalHoldReleaseForm,
    RecordDeclarationForm,
    RetentionScheduleForm,
)
from apps.documents.models import (
    DestructionCertificate,
    Document,
    DocumentLegalHold,
    DocumentVersion,
    RecordDeclaration,
    RetentionSchedule,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Module-level test helpers (prefix _records_management_*)
# ---------------------------------------------------------------------------

def _records_management_create_org_unit(tenant, name="Legal & Compliance", kind="department"):
    """Helper to create an OrgUnit for department dropdown testing."""
    return OrgUnit.objects.create(
        tenant=tenant,
        name=name,
        kind=kind,
    )


def _records_management_create_user(tenant, username="custodian_user", email=None):
    """Helper to create a user for custodian/placed_by testing."""
    email = email or f"{username}@example.com"
    user = User.objects.create_user(
        username=username,
        email=email,
        password="secretpassword123",
        tenant=tenant,
    )
    return user


def _records_management_create_core_legal_hold(tenant, name="Litigation Hold Alpha"):
    """Helper to create a core.LegalHold instance."""
    return CoreLegalHold.objects.create(
        tenant=tenant,
        name=name,
    )


def _records_management_create_document(tenant, owner, title="Corporate Records Policy"):
    """Helper to create a Document for testing."""
    return Document.objects.create(
        tenant=tenant,
        title=title,
        document_type="policy",
        owner=owner,
    )


def _records_management_create_version(tenant, document, author=None, created_by=None, label="1.0.0", file_hash="", **kwargs):
    """Helper to create a DocumentVersion."""
    author = author or created_by
    return DocumentVersion.objects.create(
        tenant=tenant,
        document=document,
        version_label=label,
        author=author,
        file_hash=file_hash,
    )


def _records_management_create_schedule(
    tenant,
    code="RET-TEST-001",
    name="Standard Corporate Records",
    retention_period_years=7,
    retention_period_months=0,
    is_permanent=False,
    trigger_type="creation_date",
    cutoff_rule="calendar_year_end",
    disposition_action="destroy",
    compliance_framework="iso_15489",
    retention_mode="modifiable",
    is_active=True,
    department=None,
    legal_citation="ISO 15489-1:2016",
):
    """Helper to create a valid RetentionSchedule."""
    return RetentionSchedule.objects.create(
        tenant=tenant,
        code=code,
        name=name,
        retention_period_years=retention_period_years,
        retention_period_months=retention_period_months,
        is_permanent=is_permanent,
        trigger_type=trigger_type,
        cutoff_rule=cutoff_rule,
        disposition_action=disposition_action,
        compliance_framework=compliance_framework,
        retention_mode=retention_mode,
        is_active=is_active,
        department=department,
        legal_citation=legal_citation,
    )


def _records_management_create_declaration(
    tenant,
    document,
    schedule,
    user,
    version=None,
    declaration_mode="manual",
    record_status="active",
    is_vital_record=False,
    is_locked=True,
    notes="",
):
    """Helper to create a valid RecordDeclaration."""
    return RecordDeclaration.objects.create(
        tenant=tenant,
        document=document,
        version=version,
        retention_schedule=schedule,
        declared_by=user,
        declaration_mode=declaration_mode,
        record_status=record_status,
        is_vital_record=is_vital_record,
        is_locked=is_locked,
        notes=notes,
    )


def _records_management_create_legal_hold(
    tenant,
    document,
    user,
    matter_name="In re Acme Litigation",
    matter_number="MAT-2026-001",
    hold_reason="litigation",
    custodian=None,
    core_legal_hold=None,
    is_active=True,
    description="Preserve all financial and compliance records",
):
    """Helper to create a valid DocumentLegalHold."""
    return DocumentLegalHold.objects.create(
        tenant=tenant,
        document=document,
        matter_name=matter_name,
        matter_number=matter_number,
        hold_reason=hold_reason,
        placed_by=user,
        custodian=custodian,
        core_legal_hold=core_legal_hold,
        is_active=is_active,
        description=description,
    )


# ---------------------------------------------------------------------------
# 1. RetentionScheduleForm Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_records_management_retention_schedule_form_valid(tenant_a, admin_user):
    """Test valid RetentionScheduleForm submission with all standard fields."""
    dept = _records_management_create_org_unit(tenant=tenant_a, name="Accounting Dept")
    data = {
        "name": "Accounting Tax Filings",
        "code": "FIN-TAX-01",
        "description": "Annual IRS and state tax filing workpapers",
        "retention_period_years": 7,
        "retention_period_months": 0,
        "is_permanent": False,
        "trigger_type": "creation_date",
        "cutoff_rule": "calendar_year_end",
        "disposition_action": "destroy",
        "compliance_framework": "irs_tax",
        "retention_mode": "modifiable",
        "legal_citation": "26 U.S. Code § 6501",
        "department": dept.pk,
        "is_active": True,
        "notes": "Reviewed annually by CFO",
    }
    form = RetentionScheduleForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    schedule = form.save(commit=False)
    schedule.tenant = tenant_a
    schedule.save()

    assert schedule.pk is not None
    assert schedule.name == "Accounting Tax Filings"
    assert schedule.code == "FIN-TAX-01"
    assert schedule.department == dept
    assert schedule.retention_period_years == 7
    assert schedule.compliance_framework == "irs_tax"


@pytest.mark.django_db
def test_records_management_retention_schedule_form_tenant_scoping_department(tenant_a, tenant_b):
    """Test department field queryset scoping and rejection of foreign tenant departments."""
    dept_a = _records_management_create_org_unit(tenant=tenant_a, name="Acme Legal")
    dept_b = _records_management_create_org_unit(tenant=tenant_b, name="Beta Legal")

    form_a = RetentionScheduleForm(tenant=tenant_a)
    dept_qs = form_a.fields["department"].queryset
    assert dept_a in dept_qs
    assert dept_b not in dept_qs

    # Submitting with foreign department (from tenant_b) must fail validation
    data = {
        "name": "Cross-tenant test",
        "code": "XTN-01",
        "retention_period_years": 3,
        "retention_period_months": 0,
        "trigger_type": "creation_date",
        "cutoff_rule": "calendar_year_end",
        "disposition_action": "destroy",
        "compliance_framework": "iso_15489",
        "retention_mode": "modifiable",
        "department": dept_b.pk,
        "is_active": True,
    }
    form_foreign = RetentionScheduleForm(data=data, tenant=tenant_a)
    assert not form_foreign.is_valid()
    assert "department" in form_foreign.errors


@pytest.mark.django_db
def test_records_management_retention_schedule_form_no_tenant():
    """Test RetentionScheduleForm when instantiated with tenant=None."""
    form = RetentionScheduleForm(tenant=None)
    assert form.fields["department"].queryset.count() == 0


@pytest.mark.django_db
def test_records_management_retention_schedule_form_negative_period_rejection(tenant_a):
    """Test that negative retention periods are rejected by the form."""
    data = {
        "name": "Negative Period Schedule",
        "code": "NEG-01",
        "retention_period_years": -2,
        "retention_period_months": -1,
        "trigger_type": "creation_date",
        "cutoff_rule": "calendar_year_end",
        "disposition_action": "destroy",
        "compliance_framework": "iso_15489",
        "retention_mode": "modifiable",
        "is_active": True,
    }
    form = RetentionScheduleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "retention_period_years" in form.errors or "retention_period_months" in form.errors


@pytest.mark.django_db
def test_records_management_retention_schedule_form_code_uniqueness_within_tenant(tenant_a, tenant_b):
    """Test case-insensitive code uniqueness per tenant and self-exclusion on edit."""
    existing = _records_management_create_schedule(tenant=tenant_a, code="FIN-TAX-01", name="Existing Schedule")

    # Duplicate code on tenant_a (case-insensitive) should fail
    data_dup = {
        "name": "Duplicate Code Schedule",
        "code": "fin-tax-01",
        "retention_period_years": 5,
        "retention_period_months": 0,
        "trigger_type": "creation_date",
        "cutoff_rule": "calendar_year_end",
        "disposition_action": "destroy",
        "compliance_framework": "iso_15489",
        "retention_mode": "modifiable",
        "is_active": True,
    }
    form_dup = RetentionScheduleForm(data=data_dup, tenant=tenant_a)
    assert not form_dup.is_valid()
    assert "code" in form_dup.errors
    assert "already exists in your workspace" in str(form_dup.errors["code"])

    # Same code on tenant_b should succeed (tenant isolation)
    form_b = RetentionScheduleForm(data=data_dup, tenant=tenant_b)
    assert form_b.is_valid(), form_b.errors

    # Editing existing schedule with its own code should succeed
    data_edit = {
        "name": "Updated Schedule Name",
        "code": "FIN-TAX-01",
        "retention_period_years": 8,
        "retention_period_months": 0,
        "trigger_type": "creation_date",
        "cutoff_rule": "calendar_year_end",
        "disposition_action": "destroy",
        "compliance_framework": "iso_15489",
        "retention_mode": "modifiable",
        "is_active": True,
    }
    form_edit = RetentionScheduleForm(data=data_edit, instance=existing, tenant=tenant_a)
    assert form_edit.is_valid(), form_edit.errors


@pytest.mark.django_db
def test_records_management_retention_schedule_form_regulatory_worm_validation(tenant_a):
    """Test that regulatory WORM schedules must have retention duration > 0 or be marked permanent."""
    # 1. WORM mode with 0 years and 0 months and not permanent -> invalid
    data_invalid = {
        "name": "Invalid Zero Duration WORM",
        "code": "WORM-01",
        "retention_period_years": 0,
        "retention_period_months": 0,
        "is_permanent": False,
        "trigger_type": "creation_date",
        "cutoff_rule": "calendar_year_end",
        "disposition_action": "destroy",
        "compliance_framework": "sec_17a_4",
        "retention_mode": "regulatory_worm",
        "is_active": True,
    }
    form_invalid = RetentionScheduleForm(data=data_invalid, tenant=tenant_a)
    assert not form_invalid.is_valid()
    assert "retention_mode" in form_invalid.errors
    assert "Regulatory WORM schedules must have a retention duration greater than 0" in str(form_invalid.errors["retention_mode"])

    # 2. WORM mode with is_permanent=True -> valid
    data_perm = dict(data_invalid, is_permanent=True)
    form_perm = RetentionScheduleForm(data=data_perm, tenant=tenant_a)
    assert form_perm.is_valid(), form_perm.errors

    # 3. WORM mode with retention_period_years > 0 -> valid
    data_with_years = dict(data_invalid, retention_period_years=5)
    form_with_years = RetentionScheduleForm(data=data_with_years, tenant=tenant_a)
    assert form_with_years.is_valid(), form_with_years.errors

    # 4. Modifiable mode with 0 years and 0 months -> valid (not restricted)
    data_modifiable = dict(data_invalid, retention_mode="modifiable")
    form_modifiable = RetentionScheduleForm(data=data_modifiable, tenant=tenant_a)
    assert form_modifiable.is_valid(), form_modifiable.errors


@pytest.mark.django_db
def test_records_management_retention_schedule_form_fields_and_widgets():
    """Verify field exclusions and widget classes on RetentionScheduleForm."""
    form = RetentionScheduleForm()
    # Check field exclusions
    for field in ["tenant", "number", "created_at", "updated_at"]:
        assert field not in form.fields

    # Check widgets
    assert "form-input" in form.fields["name"].widget.attrs.get("class", "")
    assert "form-input" in form.fields["code"].widget.attrs.get("class", "")
    assert "form-textarea" in form.fields["description"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["trigger_type"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["cutoff_rule"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["disposition_action"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["compliance_framework"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["retention_mode"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["department"].widget.attrs.get("class", "")
    assert "form-checkbox" in form.fields["is_permanent"].widget.attrs.get("class", "")
    assert "form-checkbox" in form.fields["is_active"].widget.attrs.get("class", "")


# ---------------------------------------------------------------------------
# 2. RecordDeclarationForm Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_records_management_record_declaration_form_valid(tenant_a, admin_user, document, document_version):
    """Test valid RecordDeclarationForm submission with required and optional fields."""
    schedule = _records_management_create_schedule(tenant=tenant_a, code="RET-SOP-01")
    data = {
        "document": document.pk,
        "version": document_version.pk,
        "retention_schedule": schedule.pk,
        "declaration_mode": "manual",
        "is_vital_record": True,
        "vital_review_frequency_months": 6,
        "notes": "Formal regulatory submission version",
    }
    form = RecordDeclarationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    declaration = form.save(commit=False)
    declaration.tenant = tenant_a
    declaration.declared_by = admin_user
    declaration.save()

    assert declaration.pk is not None
    assert declaration.document == document
    assert declaration.version == document_version
    assert declaration.retention_schedule == schedule
    assert declaration.is_vital_record is True
    assert declaration.vital_review_frequency_months == 6


@pytest.mark.django_db
def test_records_management_record_declaration_form_version_optional(tenant_a, admin_user, document):
    """Test that version is optional when creating a RecordDeclaration."""
    schedule = _records_management_create_schedule(tenant=tenant_a, code="RET-DOC-ONLY")
    data = {
        "document": document.pk,
        "version": "",
        "retention_schedule": schedule.pk,
        "declaration_mode": "manual",
        "is_vital_record": False,
        "vital_review_frequency_months": 12,
        "notes": "Whole document level declaration",
    }
    form = RecordDeclarationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["version"] is None


@pytest.mark.django_db
def test_records_management_record_declaration_form_tenant_scoping(tenant_a, tenant_b, admin_user, document, document_version):
    """Test dropdown queryset tenant scoping and foreign object rejection."""
    schedule_a = _records_management_create_schedule(tenant=tenant_a, code="RET-A-01")
    inactive_sched_a = _records_management_create_schedule(tenant=tenant_a, code="RET-A-INACT", is_active=False)

    doc_b = _records_management_create_document(tenant=tenant_b, owner=admin_user, title="Tenant B Document")
    ver_b = _records_management_create_version(tenant=tenant_b, document=doc_b, created_by=admin_user)
    schedule_b = _records_management_create_schedule(tenant=tenant_b, code="RET-B-01")

    form = RecordDeclarationForm(tenant=tenant_a)

    # Document scoping
    doc_qs = form.fields["document"].queryset
    assert document in doc_qs
    assert doc_b not in doc_qs

    # Retention schedule scoping (tenant isolated and only active)
    sched_qs = form.fields["retention_schedule"].queryset
    assert schedule_a in sched_qs
    assert inactive_sched_a not in sched_qs
    assert schedule_b not in sched_qs

    # Version scoping
    ver_qs = form.fields["version"].queryset
    assert document_version in ver_qs
    assert ver_b not in ver_qs

    # Submitting with foreign tenant objects must be rejected
    data_foreign_doc = {
        "document": doc_b.pk,
        "retention_schedule": schedule_a.pk,
        "declaration_mode": "manual",
    }
    form_foreign_doc = RecordDeclarationForm(data=data_foreign_doc, tenant=tenant_a)
    assert not form_foreign_doc.is_valid()
    assert "document" in form_foreign_doc.errors

    data_foreign_sched = {
        "document": document.pk,
        "retention_schedule": schedule_b.pk,
        "declaration_mode": "manual",
    }
    form_foreign_sched = RecordDeclarationForm(data=data_foreign_sched, tenant=tenant_a)
    assert not form_foreign_sched.is_valid()
    assert "retention_schedule" in form_foreign_sched.errors


@pytest.mark.django_db
def test_records_management_record_declaration_form_no_tenant():
    """Test RecordDeclarationForm when instantiated with tenant=None."""
    form = RecordDeclarationForm(tenant=None)
    assert form.fields["document"].queryset.count() == 0
    assert form.fields["version"].queryset.count() == 0
    assert form.fields["retention_schedule"].queryset.count() == 0


@pytest.mark.django_db
def test_records_management_record_declaration_form_duplicate_active_rejected(tenant_a, admin_user, document):
    """Test clean method rejects duplicate active record declaration on same document (Finding I1)."""
    schedule = _records_management_create_schedule(tenant=tenant_a, code="RET-DUP-01")

    # Create an active record declaration for document
    _records_management_create_declaration(
        tenant=tenant_a,
        document=document,
        schedule=schedule,
        user=admin_user,
        record_status="active",
    )

    # Attempt to submit another declaration for the same document
    data = {
        "document": document.pk,
        "retention_schedule": schedule.pk,
        "declaration_mode": "manual",
    }
    form = RecordDeclarationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "document" in form.errors
    assert "An active record declaration already exists for this document" in str(form.errors["document"])


@pytest.mark.django_db
def test_records_management_record_declaration_form_disposed_allows_new_declaration(tenant_a, admin_user, document):
    """Test that a previously disposed record declaration does not block a new declaration on the document."""
    schedule = _records_management_create_schedule(tenant=tenant_a, code="RET-DISP-01")

    # Existing declaration has been disposed / destroyed
    _records_management_create_declaration(
        tenant=tenant_a,
        document=document,
        schedule=schedule,
        user=admin_user,
        record_status="disposed",
    )

    # Creating a new declaration on the same document should succeed
    data = {
        "document": document.pk,
        "retention_schedule": schedule.pk,
        "declaration_mode": "manual",
        "is_vital_record": False,
        "vital_review_frequency_months": 12,
    }
    form = RecordDeclarationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_records_management_record_declaration_form_immutability_on_edit(tenant_a, admin_user, document, document_version):
    """Test immutability check on edit: cannot alter document, version, or retention schedule once saved (Finding C4)."""
    schedule_1 = _records_management_create_schedule(tenant=tenant_a, code="RET-IMMUT-01")
    schedule_2 = _records_management_create_schedule(tenant=tenant_a, code="RET-IMMUT-02")
    doc_other = _records_management_create_document(tenant=tenant_a, owner=admin_user, title="Other Document")
    ver_2 = _records_management_create_version(tenant=tenant_a, document=document, label="1.1.0")

    existing_decl = _records_management_create_declaration(
        tenant=tenant_a,
        document=document,
        version=document_version,
        schedule=schedule_1,
        user=admin_user,
        record_status="active",
    )

    # 1. Attempting to change document
    form_change_doc = RecordDeclarationForm(
        data={
            "document": doc_other.pk,
            "version": document_version.pk,
            "retention_schedule": schedule_1.pk,
            "declaration_mode": "manual",
        },
        instance=existing_decl,
        tenant=tenant_a,
    )
    assert not form_change_doc.is_valid()
    assert "document" in form_change_doc.errors
    assert "Cannot change document on an existing record declaration" in str(form_change_doc.errors["document"])

    # 2. Attempting to change version (using another version belonging to document)
    form_change_ver = RecordDeclarationForm(
        data={
            "document": document.pk,
            "version": ver_2.pk,
            "retention_schedule": schedule_1.pk,
            "declaration_mode": "manual",
        },
        instance=existing_decl,
        tenant=tenant_a,
    )
    assert not form_change_ver.is_valid()
    assert "version" in form_change_ver.errors
    assert "Cannot change version on an existing record declaration" in str(form_change_ver.errors["version"])

    # 3. Attempting to change retention schedule
    form_change_sched = RecordDeclarationForm(
        data={
            "document": document.pk,
            "version": document_version.pk,
            "retention_schedule": schedule_2.pk,
            "declaration_mode": "manual",
        },
        instance=existing_decl,
        tenant=tenant_a,
    )
    assert not form_change_sched.is_valid()
    assert "retention_schedule" in form_change_sched.errors
    assert "Cannot change retention schedule on an existing record declaration" in str(form_change_sched.errors["retention_schedule"])

    # 4. Modifying allowed fields (notes, vital record settings) without altering document/version/schedule succeeds
    form_valid_edit = RecordDeclarationForm(
        data={
            "document": document.pk,
            "version": document_version.pk,
            "retention_schedule": schedule_1.pk,
            "declaration_mode": "workflow_trigger",
            "is_vital_record": True,
            "vital_review_frequency_months": 24,
            "notes": "Updated notes during compliance audit",
        },
        instance=existing_decl,
        tenant=tenant_a,
    )
    assert form_valid_edit.is_valid(), form_valid_edit.errors


@pytest.mark.django_db
def test_records_management_record_declaration_form_version_document_mismatch(tenant_a, admin_user, document):
    """Test validation fails if the chosen version does not belong to the selected document."""
    doc_2 = _records_management_create_document(tenant=tenant_a, owner=admin_user, title="Second Document")
    ver_2 = _records_management_create_version(tenant=tenant_a, document=doc_2, created_by=admin_user, label="2.0.0")
    schedule = _records_management_create_schedule(tenant=tenant_a, code="RET-MISMATCH")

    data = {
        "document": document.pk,
        "version": ver_2.pk,  # Belongs to doc_2, not document
        "retention_schedule": schedule.pk,
        "declaration_mode": "manual",
    }
    form = RecordDeclarationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "version" in form.errors
    assert "does not belong to the chosen document" in str(form.errors["version"])


@pytest.mark.django_db
def test_records_management_record_declaration_form_version_dropdown_scoping_on_instance(tenant_a, admin_user, document, document_version):
    """Test that on an existing instance, the version queryset is scoped to that instance's document."""
    doc_other = _records_management_create_document(tenant=tenant_a, owner=admin_user, title="Unrelated Document")
    ver_other = _records_management_create_version(tenant=tenant_a, document=doc_other, created_by=admin_user)
    schedule = _records_management_create_schedule(tenant=tenant_a, code="RET-INST-VER")

    decl = _records_management_create_declaration(
        tenant=tenant_a,
        document=document,
        version=document_version,
        schedule=schedule,
        user=admin_user,
    )

    form = RecordDeclarationForm(instance=decl, tenant=tenant_a)
    ver_qs = form.fields["version"].queryset
    assert document_version in ver_qs
    assert ver_other not in ver_qs


@pytest.mark.django_db
def test_records_management_record_declaration_form_widgets():
    """Verify widget classes on RecordDeclarationForm."""
    form = RecordDeclarationForm()
    assert "form-select" in form.fields["document"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["version"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["retention_schedule"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["declaration_mode"].widget.attrs.get("class", "")
    assert "form-checkbox" in form.fields["is_vital_record"].widget.attrs.get("class", "")
    assert "form-input" in form.fields["vital_review_frequency_months"].widget.attrs.get("class", "")
    assert "form-textarea" in form.fields["notes"].widget.attrs.get("class", "")


# ---------------------------------------------------------------------------
# 3. DocumentLegalHoldForm Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_records_management_legal_hold_form_valid(tenant_a, admin_user, member_user, document):
    """Test valid DocumentLegalHoldForm submission with custodian and core legal hold."""
    core_hold = _records_management_create_core_legal_hold(tenant=tenant_a, name="SEC Acme Inquiry 2026")
    data = {
        "matter_name": "In re Acme Securities Litigation",
        "matter_number": "SEC-2026-9042",
        "hold_reason": "regulatory_audit",
        "description": "Preserve all audit workpapers and board minutes",
        "document": document.pk,
        "custodian": member_user.pk,
        "core_legal_hold": core_hold.pk,
    }
    form = DocumentLegalHoldForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    hold = form.save(commit=False)
    hold.tenant = tenant_a
    hold.placed_by = admin_user
    hold.save()

    assert hold.pk is not None
    assert hold.matter_name == "In re Acme Securities Litigation"
    assert hold.matter_number == "SEC-2026-9042"
    assert hold.hold_reason == "regulatory_audit"
    assert hold.document == document
    assert hold.custodian == member_user
    assert hold.core_legal_hold == core_hold
    assert hold.is_active is True


@pytest.mark.django_db
def test_records_management_legal_hold_form_optional_custodian_and_core_hold(tenant_a, admin_user, document):
    """Test DocumentLegalHoldForm valid without optional custodian and core_legal_hold."""
    data = {
        "matter_name": "Antitrust Compliance Inquiry",
        "matter_number": "DOJ-2026-102",
        "hold_reason": "litigation",
        "description": "Do not delete",
        "document": document.pk,
        "custodian": "",
        "core_legal_hold": "",
    }
    form = DocumentLegalHoldForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["custodian"] is None
    assert form.cleaned_data["core_legal_hold"] is None


@pytest.mark.django_db
def test_records_management_legal_hold_form_tenant_scoping(tenant_a, tenant_b, admin_user, member_user, document):
    """Test dropdown tenant scoping and rejection of foreign tenant documents, custodians, and holds."""
    doc_b = _records_management_create_document(tenant=tenant_b, owner=admin_user, title="Tenant B Document")
    user_b = _records_management_create_user(tenant=tenant_b, username="tenant_b_custodian")
    core_hold_b = _records_management_create_core_legal_hold(tenant=tenant_b, name="Tenant B Hold")

    form = DocumentLegalHoldForm(tenant=tenant_a)

    # Scoping assertions
    assert document in form.fields["document"].queryset
    assert doc_b not in form.fields["document"].queryset

    assert member_user in form.fields["custodian"].queryset
    assert user_b not in form.fields["custodian"].queryset

    assert core_hold_b not in form.fields["core_legal_hold"].queryset

    # Rejection of foreign document
    form_foreign_doc = DocumentLegalHoldForm(
        data={
            "matter_name": "Test Matter",
            "matter_number": "MAT-01",
            "hold_reason": "litigation",
            "document": doc_b.pk,
        },
        tenant=tenant_a,
    )
    assert not form_foreign_doc.is_valid()
    assert "document" in form_foreign_doc.errors

    # Rejection of foreign custodian
    form_foreign_cust = DocumentLegalHoldForm(
        data={
            "matter_name": "Test Matter",
            "matter_number": "MAT-02",
            "hold_reason": "litigation",
            "document": document.pk,
            "custodian": user_b.pk,
        },
        tenant=tenant_a,
    )
    assert not form_foreign_cust.is_valid()
    assert "custodian" in form_foreign_cust.errors


@pytest.mark.django_db
def test_records_management_legal_hold_form_no_tenant():
    """Test DocumentLegalHoldForm when instantiated with tenant=None."""
    form = DocumentLegalHoldForm(tenant=None)
    assert form.fields["document"].queryset.count() == 0
    assert form.fields["custodian"].queryset.count() == 0
    assert form.fields["core_legal_hold"].queryset.count() == 0


@pytest.mark.django_db
def test_records_management_legal_hold_form_widgets():
    """Verify widget classes on DocumentLegalHoldForm."""
    form = DocumentLegalHoldForm()
    assert "form-input" in form.fields["matter_name"].widget.attrs.get("class", "")
    assert "form-input" in form.fields["matter_number"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["hold_reason"].widget.attrs.get("class", "")
    assert "form-textarea" in form.fields["description"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["document"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["custodian"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["core_legal_hold"].widget.attrs.get("class", "")


# ---------------------------------------------------------------------------
# 4. LegalHoldReleaseForm Tests
# ---------------------------------------------------------------------------

def test_records_management_legal_hold_release_form_valid():
    """Test LegalHoldReleaseForm with valid justification text."""
    justification = "Matter dismissed with prejudice by court order dated 2026-11-20. Outside counsel authorized hold release."
    form = LegalHoldReleaseForm(data={"release_justification": justification})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["release_justification"] == justification


def test_records_management_legal_hold_release_form_required_justification():
    """Test LegalHoldReleaseForm rejects empty or whitespace-only justification."""
    # Empty string
    form_empty = LegalHoldReleaseForm(data={"release_justification": ""})
    assert not form_empty.is_valid()
    assert "release_justification" in form_empty.errors

    # Whitespace only
    form_spaces = LegalHoldReleaseForm(data={"release_justification": "   \n   "})
    assert not form_spaces.is_valid()
    assert "release_justification" in form_spaces.errors

    # Missing field
    form_missing = LegalHoldReleaseForm(data={})
    assert not form_missing.is_valid()
    assert "release_justification" in form_missing.errors


def test_records_management_legal_hold_release_form_widget():
    """Verify LegalHoldReleaseForm widget attributes."""
    form = LegalHoldReleaseForm()
    widget = form.fields["release_justification"].widget
    assert "form-textarea" in widget.attrs.get("class", "")
    assert widget.attrs.get("rows") == 4
    assert "authorization for releasing this hold" in widget.attrs.get("placeholder", "")


# ---------------------------------------------------------------------------
# 5. DestructionCertificateForm Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_records_management_destruction_certificate_form_valid(tenant_a, admin_user, document):
    """Test valid DestructionCertificateForm submission."""
    schedule = _records_management_create_schedule(tenant=tenant_a, code="RET-DISP-01")
    declaration = _records_management_create_declaration(
        tenant=tenant_a,
        document=document,
        schedule=schedule,
        user=admin_user,
        record_status="active",
    )

    data = {
        "record_declaration": declaration.pk,
        "disposition_type": "destruction",
        "destruction_method": "database_purge",
        "certificate_notes": "Destruction approved following completion of 7-year retention period",
    }
    form = DestructionCertificateForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    certificate = form.save(commit=False)
    certificate.tenant = tenant_a
    certificate.save()

    assert certificate.pk is not None
    assert certificate.record_declaration == declaration
    assert certificate.disposition_type == "destruction"
    assert certificate.destruction_method == "database_purge"
    assert certificate.document_title_snapshot == document.title


@pytest.mark.django_db
def test_records_management_destruction_certificate_form_tenant_scoping(tenant_a, tenant_b, admin_user, document):
    """Test record_declaration dropdown tenant scoping and rejection of foreign declaration."""
    sched_a = _records_management_create_schedule(tenant=tenant_a, code="RET-A-CERT")
    decl_a = _records_management_create_declaration(tenant=tenant_a, document=document, schedule=sched_a, user=admin_user)

    doc_b = _records_management_create_document(tenant=tenant_b, owner=admin_user, title="Tenant B Document")
    sched_b = _records_management_create_schedule(tenant=tenant_b, code="RET-B-CERT")
    decl_b = _records_management_create_declaration(tenant=tenant_b, document=doc_b, schedule=sched_b, user=admin_user)

    form = DestructionCertificateForm(tenant=tenant_a)
    decl_qs = form.fields["record_declaration"].queryset
    assert decl_a in decl_qs
    assert decl_b not in decl_qs

    # Submitting with tenant_b declaration should fail
    data_foreign = {
        "record_declaration": decl_b.pk,
        "disposition_type": "destruction",
        "destruction_method": "database_purge",
    }
    form_foreign = DestructionCertificateForm(data=data_foreign, tenant=tenant_a)
    assert not form_foreign.is_valid()
    assert "record_declaration" in form_foreign.errors


@pytest.mark.django_db
def test_records_management_destruction_certificate_form_disposed_excluded(tenant_a, admin_user, document):
    """Test that declarations with record_status='disposed' are excluded from dropdown."""
    sched = _records_management_create_schedule(tenant=tenant_a, code="RET-DISP-EXCL")
    decl_disposed = _records_management_create_declaration(
        tenant=tenant_a,
        document=document,
        schedule=sched,
        user=admin_user,
        record_status="disposed",
    )

    form = DestructionCertificateForm(tenant=tenant_a)
    assert decl_disposed not in form.fields["record_declaration"].queryset


@pytest.mark.django_db
def test_records_management_destruction_certificate_form_active_legal_hold_rejected(tenant_a, admin_user, document):
    """Test rejection if record declaration is under active legal hold."""
    sched = _records_management_create_schedule(tenant=tenant_a, code="RET-HOLD-GATE")
    declaration = _records_management_create_declaration(
        tenant=tenant_a,
        document=document,
        schedule=sched,
        user=admin_user,
        record_status="active",
    )

    # Place an active legal hold on the document
    _records_management_create_legal_hold(
        tenant=tenant_a,
        document=document,
        user=admin_user,
        matter_name="SEC Investigation",
        is_active=True,
    )

    data = {
        "record_declaration": declaration.pk,
        "disposition_type": "destruction",
        "destruction_method": "database_purge",
    }
    form = DestructionCertificateForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "record_declaration" in form.errors
    assert "Cannot create a destruction certificate for this record: An active legal hold is currently placed" in str(form.errors["record_declaration"])


@pytest.mark.django_db
def test_records_management_destruction_certificate_form_released_legal_hold_allowed(tenant_a, admin_user, document):
    """Test that a released legal hold does NOT block destruction certificate creation."""
    sched = _records_management_create_schedule(tenant=tenant_a, code="RET-REL-GATE")
    declaration = _records_management_create_declaration(
        tenant=tenant_a,
        document=document,
        schedule=sched,
        user=admin_user,
        record_status="active",
    )

    # Place a hold and immediately release it
    hold = _records_management_create_legal_hold(
        tenant=tenant_a,
        document=document,
        user=admin_user,
        matter_name="Past Inquiry",
        is_active=True,
    )
    hold.release_hold(admin_user, justification="Audit closed")

    data = {
        "record_declaration": declaration.pk,
        "disposition_type": "destruction",
        "destruction_method": "cryptographic_erase",
        "certificate_notes": "Hold released, disposition authorized",
    }
    form = DestructionCertificateForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_records_management_destruction_certificate_form_no_tenant():
    """Test DestructionCertificateForm when instantiated with tenant=None."""
    form = DestructionCertificateForm(tenant=None)
    assert form.fields["record_declaration"].queryset.count() == 0


@pytest.mark.django_db
def test_records_management_destruction_certificate_form_widgets():
    """Verify widget classes on DestructionCertificateForm."""
    form = DestructionCertificateForm()
    assert "form-select" in form.fields["record_declaration"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["disposition_type"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["destruction_method"].widget.attrs.get("class", "")
    assert "form-textarea" in form.fields["certificate_notes"].widget.attrs.get("class", "")
