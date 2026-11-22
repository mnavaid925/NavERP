"""Form unit tests for Sub-module 13.2 Version Control & Revision Management."""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.documents.forms.VersionControl.Documents import DocumentForm
from apps.documents.forms.VersionControl.DocumentVersions import DocumentVersionForm, VersionCompareForm
from apps.documents.forms.VersionControl.DocumentLocks import CheckoutForm, CheckinForm, ForceUnlockForm
from apps.documents.forms.VersionControl.DocumentBranches import DocumentBranchForm, BranchMergeForm
from apps.documents.models.VersionControl.Documents import Document


@pytest.mark.django_db
def test_version_control_document_form_valid(tenant_a, admin_user):
    """Assert DocumentForm accepts valid data and excludes view-owned fields."""
    form = DocumentForm(
        data={
            "title": "Corporate Governance Policy",
            "document_type": "policy",
            "classification": "confidential",
            "status": "draft",
            "versioning_scheme": "semantic",
            "owner": admin_user.pk,
            "max_versions_retained": 0,
            "description": "Standard compliance policy for corporate board.",
        },
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    doc = form.save(commit=False)
    doc.tenant = tenant_a
    doc.save()
    assert doc.title == "Corporate Governance Policy"


@pytest.mark.django_db
def test_version_control_checkout_form_validation():
    """Assert CheckoutForm validates expires_in_hours and lock_type."""
    form = CheckoutForm(data={"expires_in_hours": 4, "lock_type": "exclusive", "checkout_note": "Editing clause 4"})
    assert form.is_valid()
    assert form.cleaned_data["expires_in_hours"] == 4

    invalid_form = CheckoutForm(data={"expires_in_hours": -1, "lock_type": "invalid"})
    assert not invalid_form.is_valid()
    assert "expires_in_hours" in invalid_form.errors
    assert "lock_type" in invalid_form.errors


@pytest.mark.django_db
def test_version_control_force_unlock_form_mandatory_reason():
    """Assert ForceUnlockForm requires non-empty override reason."""
    empty_form = ForceUnlockForm(data={"override_reason": ""})
    assert not empty_form.is_valid()
    assert "override_reason" in empty_form.errors

    valid_form = ForceUnlockForm(data={"override_reason": "Author out of office on emergency medical leave."})
    assert valid_form.is_valid()


@pytest.mark.django_db
def test_version_control_branch_form_cross_document_rejection(tenant_a, admin_user, document, document_version):
    """Assert DocumentBranchForm rejects a base_version belonging to another document (I5)."""
    other_doc = Document.objects.create(
        tenant=tenant_a,
        title="Unrelated Engineering Specification",
        owner=admin_user,
    )
    form = DocumentBranchForm(
        data={
            "document": other_doc.pk,
            "name": "Invalid-Branch-Cross",
            "base_version": document_version.pk,  # Belongs to `document`, not `other_doc`
            "branch_type": "what_if",
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "base_version" in form.errors


@pytest.mark.django_db
def test_version_control_version_compare_form_choices(tenant_a, document, document_version):
    """Assert VersionCompareForm populates choices and validates version selection."""
    form = VersionCompareForm(document=document, tenant=tenant_a)
    assert form.fields["version_a"].queryset.filter(pk=document_version.pk).exists()
    assert form.fields["version_b"].queryset.filter(pk=document_version.pk).exists()


@pytest.mark.django_db
def test_version_control_file_upload_validation(tenant_a, admin_user, document):
    """Assert DocumentVersionForm rejects unsafe file extensions (I6)."""
    fake_exe = SimpleUploadedFile("malware.exe", b"binary content", content_type="application/octet-stream")
    form = DocumentVersionForm(
        data={
            "document": document.pk,
            "version_label": "2.0.0",
            "version_type": "major",
            "status": "approved",
            "author": admin_user.pk,
        },
        files={"file": fake_exe},
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "file" in form.errors
