"""Model unit tests for Sub-module 13.2 Version Control & Revision Management."""
import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.documents.models.VersionControl.Documents import Document
from apps.documents.models.VersionControl.DocumentVersions import DocumentVersion
from apps.documents.models.VersionControl.DocumentLocks import DocumentLock
from apps.documents.models.VersionControl.DocumentBranches import DocumentBranch


@pytest.mark.django_db
def test_version_control_document_creation_and_defaults(tenant_a, admin_user):
    """Assert document creation assigns prefix DOC and default status/version."""
    doc = Document.objects.create(
        tenant=tenant_a,
        title="Quality Calibration Standard",
        document_type="sop",
        classification="internal",
        owner=admin_user,
    )
    assert doc.number.startswith("DOC-")
    assert doc.status == "draft"
    assert doc.current_version_label == "1.0"
    assert doc.current_version_no == 1
    assert not doc.is_locked
    assert doc.status_badge_class == "badge-slate"
    assert doc.classification_badge_class == "badge-info"
    assert "DOC-" in str(doc)


@pytest.mark.django_db
def test_version_control_document_slug_auto_generation(tenant_a, admin_user):
    """Assert slug is automatically generated from title on save."""
    doc = Document.objects.create(
        tenant=tenant_a,
        title="Annual Risk Assessment 2026",
        owner=admin_user,
    )
    assert doc.slug == "annual-risk-assessment-2026"


@pytest.mark.django_db
def test_version_control_document_version_creation_and_prefix(tenant_a, admin_user, document):
    """Assert version inherits DVER prefix and computes badges."""
    ver = DocumentVersion.objects.create(
        tenant=tenant_a,
        document=document,
        version_label="1.1.0",
        major_number=1,
        minor_number=1,
        patch_number=0,
        version_type="minor",
        status="approved",
        is_official=True,
        change_summary="Added calibration telemetry",
        extracted_text="Telemetry readings are automated hourly.",
        author=admin_user,
    )
    assert ver.number.startswith("DVER-")
    assert ver.version_type_badge_class == "badge-info"
    assert ver.status_badge_class == "badge-green"
    assert "v1.1.0" in str(ver)


@pytest.mark.django_db
def test_version_control_version_label_uniqueness_per_document(tenant_a, admin_user, document, document_version):
    """Assert duplicate version label for the same document and tenant raises IntegrityError."""
    with pytest.raises(IntegrityError):
        DocumentVersion.objects.create(
            tenant=tenant_a,
            document=document,
            version_label=document_version.version_label,  # "1.0.0" duplicate
            major_number=1,
            minor_number=0,
            patch_number=0,
            author=admin_user,
        )


@pytest.mark.django_db
def test_version_control_lock_creation_and_expiry(tenant_a, admin_user, document, document_version):
    """Assert lock assigns DLOCK prefix and calculates stale status."""
    past_time = timezone.now() - timezone.timedelta(hours=2)
    stale_lock = DocumentLock.objects.create(
        tenant=tenant_a,
        document=document,
        base_version=document_version,
        locked_by=admin_user,
        lock_type="exclusive",
        status="active",
        expires_at=past_time,
    )
    assert stale_lock.number.startswith("DLOCK-")
    assert stale_lock.is_stale_lock is True
    assert stale_lock.lock_type_badge_class == "badge-red"
    assert stale_lock.status_badge_class == "badge-red"
    assert "DLOCK-" in str(stale_lock)


@pytest.mark.django_db
def test_version_control_branch_creation_and_merge_strategy(tenant_a, admin_user, document, document_version):
    """Assert branch assigns DBRN prefix and formats display."""
    branch = DocumentBranch.objects.create(
        tenant=tenant_a,
        document=document,
        name="Variant-EMEA",
        base_version=document_version,
        branch_type="variant",
        status="active",
        created_by=admin_user,
        merge_strategy="new_minor_version",
    )
    assert branch.number.startswith("DBRN-")
    assert branch.branch_type_badge_class == "badge-slate"
    assert branch.status_badge_class == "badge-amber"
    assert "Variant-EMEA" in str(branch)
