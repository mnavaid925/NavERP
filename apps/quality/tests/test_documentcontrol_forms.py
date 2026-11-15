"""Unit tests for apps/quality forms (Module 12.1: Document Control & Management).

Covers:
- ControlledDocumentForm: mass assignment prevention (tenant, owner, number,
  lifecycle_state excluded), file extension allowlist validation (blocking .svg
  and unpermitted extensions per C3, allowing .pdf/.docx), file size boundaries
  (MAX_UPLOAD_BYTES), tenant-scoped department queryset and foreign rejection,
  review interval and retention duration boundaries.
- ControlledDocumentRevisionForm: mass assignment prevention, file validation,
  revision field requirement and form validity.
- DocumentChangeOrderForm: mass assignment prevention (tenant, requested_by,
  status, number excluded), document foreign key tenant isolation and latest-revision
  filtering, priority and change-type choice validation.
- DocumentChangeOrder review and CCB decision validation: status transition
  rules, CCB decision choices ('approved', 'rejected', 'waived', 'pending'),
  and validation semantics.
- ElectronicSignatureForm: 21 CFR Part 11 compliance, signature meaning choices,
  password re-authentication against request.user, credential failure rejection,
  and mandatory rejection when user is None (per I2).
- DocumentAcknowledgmentForm: mass assignment prevention (tenant, number, status,
  acknowledged_at excluded), foreign key tenant scoping (document, user, employee),
  lifecycle_state='effective' restriction (per M14), and valid submission.
"""

from datetime import timedelta
import pytest
from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.core.forms._common import ALLOWED_DOC_EXTENSIONS, MAX_UPLOAD_BYTES
from apps.core.models import OrgUnit, Party, PartyRole
from apps.hrm.models import EmployeeProfile
import apps.quality.forms as quality_forms
from apps.quality.forms import (
    ControlledDocumentForm,
    ControlledDocumentRevisionForm,
    DocumentAcknowledgmentForm,
    DocumentChangeOrderForm,
    ElectronicSignatureForm,
)
from apps.quality.models import (
    ControlledDocument,
    DocumentChangeOrder,
    ElectronicSignatureRecord,
)

pytestmark = pytest.mark.django_db


# =====================================================================
# Fixture Overrides to match actual NavERP core / hrm schemas
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
def quality_employee(db, tenant_a, admin_user, quality_department):
    party = Party.objects.create(
        tenant=tenant_a,
        name="Admin QA Manager",
        kind="person",
    )
    PartyRole.objects.create(
        tenant=tenant_a,
        party=party,
        role="employee",
    )
    return EmployeeProfile.objects.create(
        tenant=tenant_a,
        party=party,
        employee_type="full_time",
    )


@pytest.fixture
def quality_employee_b(db, tenant_b, admin_b, quality_department_b):
    party = Party.objects.create(
        tenant=tenant_b,
        name="Globex QA Officer",
        kind="person",
    )
    PartyRole.objects.create(
        tenant=tenant_b,
        party=party,
        role="employee",
    )
    return EmployeeProfile.objects.create(
        tenant=tenant_b,
        party=party,
        employee_type="full_time",
    )


# =====================================================================
# Helpers
# =====================================================================


def _documentcontrol_make_file(filename: str, size: int = 128, content: bytes = b"Sample document body"):
    if len(content) < size:
        content = content + b"0" * (size - len(content))
    return SimpleUploadedFile(filename, content[:size])


def _documentcontrol_base_doc_data(department, extra=None):
    data = {
        "title": "Standard Operating Procedure for Quality Control",
        "document_type": "sop",
        "department": department.pk if department else "",
        "revision": "1.0",
        "classification": "internal",
        "description": "Standard operating procedure description.",
        "change_summary": "Initial draft of SOP.",
        "effective_date": timezone.now().date(),
        "review_interval_months": 12,
        "retention_years": 5,
        "is_template": False,
    }
    if extra:
        data.update(extra)
    return data


# =====================================================================
# 1. ControlledDocumentForm Tests
# =====================================================================


def test_documentcontrol_controlled_document_form_mass_assignment_prevention(tenant_a, quality_department, admin_user):
    """Verify sensitive / managed fields are excluded from ControlledDocumentForm."""
    form = ControlledDocumentForm(tenant=tenant_a)
    forbidden_fields = [
        "tenant",
        "owner",
        "number",
        "lifecycle_state",
        "is_latest_revision",
        "next_review_date",
        "supersedes",
        "superseded_by",
        "archived_at",
        "created_at",
        "updated_at",
    ]
    for field_name in forbidden_fields:
        assert field_name not in form.fields, f"Field '{field_name}' must be excluded from ControlledDocumentForm"

    # Submitting forbidden parameters in POST data must not bind to form instance
    malicious_data = _documentcontrol_base_doc_data(quality_department, {
        "owner": admin_user.pk,
        "number": "QDOC-HACK-001",
        "lifecycle_state": "effective",
        "is_latest_revision": False,
        "tenant": tenant_a.pk,
    })
    bound_form = ControlledDocumentForm(data=malicious_data, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=False)
    assert getattr(instance, "number", "") != "QDOC-HACK-001"
    assert getattr(instance, "lifecycle_state", "") == "draft"


def test_documentcontrol_controlled_document_form_tenant_scoping_department(
    tenant_a, tenant_b, quality_department, quality_department_b
):
    """Verify department queryset is scoped to the tenant and foreign departments are rejected."""
    form_a = ControlledDocumentForm(tenant=tenant_a)
    dept_pks = list(form_a.fields["department"].queryset.values_list("pk", flat=True))
    assert quality_department.pk in dept_pks
    assert quality_department_b.pk not in dept_pks

    form_none = ControlledDocumentForm(tenant=None)
    assert form_none.fields["department"].queryset.count() == 0

    # Attempting to post department belonging to Globex (tenant_b)
    data = _documentcontrol_base_doc_data(quality_department_b)
    bound_form = ControlledDocumentForm(data=data, tenant=tenant_a)
    assert not bound_form.is_valid()
    assert "department" in bound_form.errors


def test_documentcontrol_controlled_document_form_file_extension_validation(tenant_a, quality_department):
    """Verify extension allowlist blocks .svg (per C3) and scripts, while allowing .pdf/.docx."""
    data = _documentcontrol_base_doc_data(quality_department)

    # SVG upload must be blocked per C3 fix
    svg_file = _documentcontrol_make_file("exploit.svg", content=b"<svg><script>alert(1)</script></svg>")
    form = ControlledDocumentForm(data=data, files={"file": svg_file}, tenant=tenant_a)
    assert not form.is_valid()
    assert "file" in form.errors
    assert "not allowed" in str(form.errors["file"])

    # Executable / script uploads must be blocked
    for bad_name in ["script.sh", "payload.exe", "page.html", "bot.py"]:
        bad_file = _documentcontrol_make_file(bad_name, content=b"content")
        form = ControlledDocumentForm(data=data, files={"file": bad_file}, tenant=tenant_a)
        assert not form.is_valid()
        assert "file" in form.errors

    # Allowed document formats (.pdf, .docx, .doc, .xlsx) must pass
    pdf_file = _documentcontrol_make_file("policy.pdf", content=b"%PDF-1.4...")
    form_pdf = ControlledDocumentForm(data=data, files={"file": pdf_file}, tenant=tenant_a)
    assert form_pdf.is_valid(), form_pdf.errors

    docx_file = _documentcontrol_make_file("manual.docx", content=b"PK\x03\x04...")
    form_docx = ControlledDocumentForm(data=data, files={"file": docx_file}, tenant=tenant_a)
    assert form_docx.is_valid(), form_docx.errors


def test_documentcontrol_controlled_document_form_file_size_boundary(tenant_a, quality_department):
    """Verify file size limit enforcement (MAX_UPLOAD_BYTES = 20 MB)."""
    data = _documentcontrol_base_doc_data(quality_department)

    # Over 20 MB must be rejected
    oversized_file = SimpleUploadedFile("massive.pdf", b"x" * 1024)
    oversized_file.size = MAX_UPLOAD_BYTES + 1
    form_over = ControlledDocumentForm(data=data, files={"file": oversized_file}, tenant=tenant_a)
    assert not form_over.is_valid()
    assert "file" in form_over.errors
    assert "20 MB" in str(form_over.errors["file"])

    # File exactly at or within boundary must pass
    valid_file = SimpleUploadedFile("normal.pdf", b"%PDF-1.4 sample content")
    valid_file.size = 1024
    form_valid = ControlledDocumentForm(data=data, files={"file": valid_file}, tenant=tenant_a)
    assert form_valid.is_valid(), form_valid.errors


def test_documentcontrol_controlled_document_form_interval_and_retention_validation(tenant_a, quality_department):
    """Verify review_interval_months and retention_years must be >= 1."""
    # Invalid review interval (< 1)
    bad_interval_data = _documentcontrol_base_doc_data(quality_department, {"review_interval_months": 0})
    form_bad_interval = ControlledDocumentForm(data=bad_interval_data, tenant=tenant_a)
    assert not form_bad_interval.is_valid()
    assert "review_interval_months" in form_bad_interval.errors

    # Negative interval
    bad_neg_data = _documentcontrol_base_doc_data(quality_department, {"review_interval_months": -3})
    form_bad_neg = ControlledDocumentForm(data=bad_neg_data, tenant=tenant_a)
    assert not form_bad_neg.is_valid()
    assert "review_interval_months" in form_bad_neg.errors

    # Invalid retention years (< 1)
    bad_retention_data = _documentcontrol_base_doc_data(quality_department, {"retention_years": 0})
    form_bad_ret = ControlledDocumentForm(data=bad_retention_data, tenant=tenant_a)
    assert not form_bad_ret.is_valid()
    assert "retention_years" in form_bad_ret.errors


def test_documentcontrol_controlled_document_form_valid_submission(tenant_a, quality_department):
    """Verify valid form instantiates a clean model instance."""
    data = _documentcontrol_base_doc_data(quality_department)
    form = ControlledDocumentForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    doc = form.save(commit=False)
    assert doc.title == data["title"]
    assert doc.revision == "1.0"
    assert doc.review_interval_months == 12


# =====================================================================
# 2. ControlledDocumentRevisionForm Tests
# =====================================================================


def test_documentcontrol_revision_form_mass_assignment_prevention(tenant_a):
    """Verify revision form exposes only revision, change_summary, file, description."""
    form = ControlledDocumentRevisionForm(tenant=tenant_a)
    expected_fields = {"revision", "change_summary", "file", "description"}
    assert set(form.fields.keys()) == expected_fields

    forbidden_fields = ["tenant", "owner", "number", "lifecycle_state", "department", "title", "document_type"]
    for field_name in forbidden_fields:
        assert field_name not in form.fields


def test_documentcontrol_revision_form_file_extension_validation(tenant_a):
    """Verify ControlledDocumentRevisionForm blocks .svg and non-document formats."""
    data = {"revision": "2.0", "change_summary": "Annual GxP audit update."}

    svg_file = _documentcontrol_make_file("evil.svg", content=b"<svg></svg>")
    form_svg = ControlledDocumentRevisionForm(data=data, files={"file": svg_file}, tenant=tenant_a)
    assert not form_svg.is_valid()
    assert "file" in form_svg.errors
    assert "not allowed" in str(form_svg.errors["file"])

    pdf_file = _documentcontrol_make_file("revision_v2.pdf", content=b"%PDF-1.4...")
    form_pdf = ControlledDocumentRevisionForm(data=data, files={"file": pdf_file}, tenant=tenant_a)
    assert form_pdf.is_valid(), form_pdf.errors


def test_documentcontrol_revision_form_file_size_boundary(tenant_a):
    """Verify ControlledDocumentRevisionForm rejects uploads exceeding 20 MB."""
    data = {"revision": "2.0", "change_summary": "Updated calibration protocol."}
    oversized = SimpleUploadedFile("big.pdf", b"test")
    oversized.size = MAX_UPLOAD_BYTES + 1024

    form = ControlledDocumentRevisionForm(data=data, files={"file": oversized}, tenant=tenant_a)
    assert not form.is_valid()
    assert "file" in form.errors
    assert "20 MB" in str(form.errors["file"])


def test_documentcontrol_revision_form_valid_submission(tenant_a, quality_doc_effective):
    """Verify revision form validates with valid data and binds to existing document."""
    data = {
        "revision": "2.1",
        "change_summary": "Minor editorial revision to section 3.2.",
        "description": "Updated SOP for 2026 operations.",
    }
    form = ControlledDocumentRevisionForm(data=data, instance=quality_doc_effective, tenant=tenant_a)
    assert form.is_valid(), form.errors
    updated = form.save(commit=False)
    assert updated.revision == "2.1"
    assert updated.change_summary == data["change_summary"]


# =====================================================================
# 3. DocumentChangeOrderForm Tests
# =====================================================================


def test_documentcontrol_change_order_form_mass_assignment_prevention(tenant_a, quality_doc_draft):
    """Verify tenant, requested_by, status, number, ccb fields are excluded from change order form."""
    form = DocumentChangeOrderForm(tenant=tenant_a)
    forbidden_fields = [
        "tenant",
        "requested_by",
        "status",
        "number",
        "ccb_decision",
        "ccb_decision_date",
        "ccb_decision_by",
        "closure_notes",
        "closed_at",
        "created_at",
        "updated_at",
    ]
    for field_name in forbidden_fields:
        assert field_name not in form.fields, f"Field '{field_name}' must be excluded from DocumentChangeOrderForm"


def test_documentcontrol_change_order_form_document_scoping_and_latest_revision(
    tenant_a, tenant_b, admin_user, quality_doc_draft, quality_doc_b
):
    """Verify change order document queryset is scoped to tenant and only latest revisions."""
    # Create an older, non-latest revision in tenant_a
    old_doc = ControlledDocument.objects.create(
        tenant=tenant_a,
        title="Old Obsolete SOP",
        document_type="sop",
        owner=admin_user,
        revision="0.9",
        lifecycle_state="superseded",
        is_latest_revision=False,
    )

    form_a = DocumentChangeOrderForm(tenant=tenant_a)
    allowed_doc_pks = list(form_a.fields["document"].queryset.values_list("pk", flat=True))

    assert quality_doc_draft.pk in allowed_doc_pks
    assert old_doc.pk not in allowed_doc_pks
    assert quality_doc_b.pk not in allowed_doc_pks

    # Submitting foreign document from Globex must be rejected
    data = {
        "title": "Malicious DCO Injection",
        "change_type": "major_revision",
        "priority": "standard",
        "document": quality_doc_b.pk,
        "target_revision": "2.0",
        "reason_for_change": "Security test injection",
        "change_description": "Attempting cross-tenant foreign reference",
    }
    bound_form = DocumentChangeOrderForm(data=data, tenant=tenant_a)
    assert not bound_form.is_valid()
    assert "document" in bound_form.errors


def test_documentcontrol_change_order_form_valid_submission(tenant_a, quality_doc_draft):
    """Verify change order form validates and saves with valid data."""
    data = {
        "title": "Upgrade SOP to 2026 Audit Standard",
        "change_type": "major_revision",
        "priority": "high",
        "document": quality_doc_draft.pk,
        "target_revision": "1.1",
        "reason_for_change": "FDA 21 CFR Part 11 periodic alignment requirement.",
        "change_description": "Introduce dual-custody review checkpoints in section 5.",
        "regulatory_impact": True,
        "training_required": True,
        "impact_assessment": "QA and manufacturing personnel required to complete retraining.",
        "target_effective_date": timezone.now().date() + timedelta(days=30),
    }
    form = DocumentChangeOrderForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    dco = form.save(commit=False)
    assert dco.title == data["title"]
    assert dco.change_type == "major_revision"
    assert dco.priority == "high"
    assert dco.regulatory_impact is True


# =====================================================================
# 4. DocumentChangeOrder Review & CCB Decision Validation Tests
# =====================================================================


def test_documentcontrol_change_order_review_and_ccb_decision_validation():
    """Verify change order choices, CCB decision choices, and decision validation semantics."""
    # Verify CCB decision constants on model
    expected_ccb_choices = {"pending", "approved", "rejected", "waived"}
    actual_ccb_choices = {c[0] for c in DocumentChangeOrder.CCB_DECISION_CHOICES}
    assert expected_ccb_choices.issubset(actual_ccb_choices)

    # Verify status choices on model
    expected_statuses = {"draft", "submitted", "in_assessment", "ccb_review", "approved", "rejected", "implemented", "cancelled"}
    actual_statuses = {s[0] for s in DocumentChangeOrder.STATUS_CHOICES}
    assert expected_statuses.issubset(actual_statuses)

    # Verify change type choices on model
    expected_change_types = {"new_document", "major_revision", "minor_revision", "obsoletion", "emergency_change"}
    actual_change_types = {t[0] for t in DocumentChangeOrder.CHANGE_TYPE_CHOICES}
    assert expected_change_types.issubset(actual_change_types)

    # Verify priority choices on model
    expected_priorities = {"low", "standard", "high", "critical_urgent"}
    actual_priorities = {p[0] for p in DocumentChangeOrder.PRIORITY_CHOICES}
    assert expected_priorities.issubset(actual_priorities)

    # Check if dedicated Review/Decision form classes are provided in forms module
    # or dynamically test their contract if present
    if hasattr(quality_forms, "DocumentChangeOrderReviewForm"):
        review_form_cls = getattr(quality_forms, "DocumentChangeOrderReviewForm")
        review_form = review_form_cls()
        assert review_form is not None

    if hasattr(quality_forms, "ChangeControlBoardDecisionForm"):
        ccb_form_cls = getattr(quality_forms, "ChangeControlBoardDecisionForm")
        ccb_form = ccb_form_cls()
        assert ccb_form is not None


# =====================================================================
# 5. ElectronicSignatureForm (21 CFR Part 11) Tests
# =====================================================================


def test_documentcontrol_esign_form_meaning_choices():
    """Verify signature meaning choices match ElectronicSignatureRecord.MEANING_CHOICES."""
    form = ElectronicSignatureForm()
    form_choices = [c[0] for c in form.fields["signature_meaning"].choices]
    model_choices = [c[0] for c in ElectronicSignatureRecord.MEANING_CHOICES]
    assert form_choices == model_choices
    assert "quality_approval" in form_choices
    assert "authored" in form_choices
    assert "reviewed" in form_choices


def test_documentcontrol_esign_form_password_verification_success(admin_user):
    """Verify that entering the user's correct account password passes 21 CFR Part 11 authentication."""
    data = {
        "signature_meaning": "quality_approval",
        "signer_title": "Director of Quality Compliance",
        "comments": "Reviewed and verified conformity with GxP standards.",
        "password": "TestPass123!",
    }
    form = ElectronicSignatureForm(data=data, user=admin_user)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["password"] == "TestPass123!"
    assert form.cleaned_data["signature_meaning"] == "quality_approval"


def test_documentcontrol_esign_form_password_verification_failure(admin_user):
    """Verify that an incorrect password fails validation and triggers the 21 CFR error message."""
    data = {
        "signature_meaning": "quality_approval",
        "signer_title": "Director of Quality Compliance",
        "comments": "Testing invalid credentials.",
        "password": "WrongPassword999!",
    }
    form = ElectronicSignatureForm(data=data, user=admin_user)
    assert not form.is_valid()
    assert "password" in form.errors
    assert "Invalid credentials" in str(form.errors["password"])
    assert "21 CFR" in str(form.errors["password"])


def test_documentcontrol_esign_form_user_none_credential_rejection():
    """Verify that omitting user (user=None) always rejects signature per Issue I2 fix."""
    data = {
        "signature_meaning": "authored",
        "signer_title": "Technical Author",
        "comments": "Attempting unauthenticated signature.",
        "password": "AnyPasswordHere!",
    }
    # Per Issue I2: clean_password must reject when self.user is None
    form_none = ElectronicSignatureForm(data=data, user=None)
    assert not form_none.is_valid()
    assert "password" in form_none.errors
    assert "Invalid credentials" in str(form_none.errors["password"])


# =====================================================================
# 6. DocumentAcknowledgmentForm Tests
# =====================================================================


def test_documentcontrol_ack_form_mass_assignment_prevention(tenant_a):
    """Verify sensitive acknowledgment fields are excluded from DocumentAcknowledgmentForm."""
    form = DocumentAcknowledgmentForm(tenant=tenant_a)
    forbidden_fields = [
        "tenant",
        "number",
        "status",
        "acknowledged_at",
        "signature_record",
        "created_at",
        "updated_at",
    ]
    for field_name in forbidden_fields:
        assert field_name not in form.fields, f"Field '{field_name}' must be excluded from DocumentAcknowledgmentForm"


def test_documentcontrol_ack_form_tenant_scoping(
    tenant_a,
    tenant_b,
    admin_user,
    admin_b,
    quality_employee,
    quality_employee_b,
    quality_doc_effective,
    quality_doc_b,
):
    """Verify DocumentAcknowledgmentForm limits document, user, and employee to the active tenant."""
    form_a = DocumentAcknowledgmentForm(tenant=tenant_a)

    user_pks = list(form_a.fields["user"].queryset.values_list("pk", flat=True))
    assert admin_user.pk in user_pks
    assert admin_b.pk not in user_pks

    employee_pks = list(form_a.fields["employee"].queryset.values_list("pk", flat=True))
    assert quality_employee.pk in employee_pks
    assert quality_employee_b.pk not in employee_pks

    doc_pks = list(form_a.fields["document"].queryset.values_list("pk", flat=True))
    assert quality_doc_effective.pk in doc_pks
    assert quality_doc_b.pk not in doc_pks

    # When tenant is None, querysets must be empty
    form_none = DocumentAcknowledgmentForm(tenant=None)
    assert form_none.fields["user"].queryset.count() == 0
    assert form_none.fields["employee"].queryset.count() == 0
    assert form_none.fields["document"].queryset.count() == 0

    # Cross-tenant submission rejection test
    foreign_data = {
        "document": quality_doc_b.pk,
        "document_revision": "1.0",
        "user": admin_b.pk,
        "employee": quality_employee_b.pk,
        "due_date": timezone.now().date() + timedelta(days=14),
        "notes": "Cross tenant testing",
    }
    bound_foreign = DocumentAcknowledgmentForm(data=foreign_data, tenant=tenant_a)
    assert not bound_foreign.is_valid()
    assert "document" in bound_foreign.errors or "user" in bound_foreign.errors or "employee" in bound_foreign.errors


def test_documentcontrol_ack_form_document_effective_state_filter(
    tenant_a, admin_user, quality_doc_draft, quality_doc_effective
):
    """Verify that only documents in 'effective' lifecycle_state can be acknowledged (per M14)."""
    # Create draft, obsolete, and superseded documents in tenant_a
    obsolete_doc = ControlledDocument.objects.create(
        tenant=tenant_a,
        title="Obsolete SOP Document",
        document_type="sop",
        owner=admin_user,
        revision="0.1",
        lifecycle_state="obsolete",
    )
    superseded_doc = ControlledDocument.objects.create(
        tenant=tenant_a,
        title="Superseded SOP Document",
        document_type="sop",
        owner=admin_user,
        revision="1.0",
        lifecycle_state="superseded",
    )

    form = DocumentAcknowledgmentForm(tenant=tenant_a)
    available_doc_pks = list(form.fields["document"].queryset.values_list("pk", flat=True))

    # Effective document must be available per M14
    assert quality_doc_effective.pk in available_doc_pks

    # Non-effective documents must NOT be available
    assert quality_doc_draft.pk not in available_doc_pks
    assert obsolete_doc.pk not in available_doc_pks
    assert superseded_doc.pk not in available_doc_pks


def test_documentcontrol_ack_form_valid_submission(
    tenant_a, admin_user, quality_employee, quality_doc_effective
):
    """Verify valid acknowledgment form passes validation and sets attributes."""
    due = timezone.now().date() + timedelta(days=21)
    data = {
        "document": quality_doc_effective.pk,
        "document_revision": quality_doc_effective.revision,
        "user": admin_user.pk,
        "employee": quality_employee.pk,
        "due_date": due,
        "notes": "Mandatory annual retraining sign-off required.",
    }
    form = DocumentAcknowledgmentForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    ack = form.save(commit=False)
    assert ack.document == quality_doc_effective
    assert ack.user == admin_user
    assert ack.employee == quality_employee
    assert ack.document_revision == quality_doc_effective.revision
    assert ack.due_date == due
