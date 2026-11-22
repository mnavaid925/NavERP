"""View integration tests for Sub-module 13.2 Version Control & Revision Management."""
import pytest
from django.urls import reverse

from apps.documents.models.VersionControl.Documents import Document
from apps.documents.models.VersionControl.DocumentVersions import DocumentVersion
from apps.documents.models.VersionControl.DocumentLocks import DocumentLock
from apps.documents.models.VersionControl.DocumentBranches import DocumentBranch


@pytest.mark.django_db
def test_version_control_document_list_and_detail(client, tenant_a, admin_user, document):
    """Assert document list and detail views render with expected context variables."""
    client.force_login(admin_user)
    resp = client.get(reverse("documents:document_list"))
    assert resp.status_code == 200
    assert document.title in resp.content.decode()

    detail_resp = client.get(reverse("documents:document_detail", args=[document.pk]))
    assert detail_resp.status_code == 200
    assert document.number in detail_resp.content.decode()


@pytest.mark.django_db
def test_version_control_document_checkout_and_checkin_lifecycle(client, tenant_a, admin_user, document, document_version):
    """Assert full checkout -> lock -> check-in -> new version lifecycle."""
    client.force_login(admin_user)

    # 1. Checkout document
    checkout_url = reverse("documents:document_checkout", args=[document.pk])
    resp = client.post(
        checkout_url,
        data={
            "lock_type": "exclusive",
            "expires_in_hours": 12,
            "checkout_note": "Executing minor updates for Q4",
        },
        follow=True,
    )
    assert resp.status_code == 200
    document.refresh_from_db()
    assert document.is_locked is True
    assert document.locked_by == admin_user

    lock = DocumentLock.objects.filter(document=document, status="active").first()
    assert lock is not None

    # 2. Checkin document
    checkin_url = reverse("documents:document_checkin", args=[document.pk])
    checkin_resp = client.post(
        checkin_url,
        data={
            "increment_intent": "minor",
            "change_summary": "Completed Q4 updates",
            "extracted_text": "Updated content with Q4 standards.",
            "is_official": True,
        },
        follow=True,
    )
    assert checkin_resp.status_code == 200
    document.refresh_from_db()
    lock.refresh_from_db()

    assert document.is_locked is False
    assert lock.status == "checked_in"
    assert document.current_version_label == "1.1"

    new_ver = DocumentVersion.objects.filter(document=document, version_label="1.1").first()
    assert new_ver is not None
    assert new_ver.is_official is True


@pytest.mark.django_db
def test_version_control_version_rollback(client, tenant_a, admin_user, document, document_version):
    """Assert rollback restores an earlier version as a new forward increment."""
    client.force_login(admin_user)
    # Create a secondary version 2.0.0
    v2 = DocumentVersion.objects.create(
        tenant=tenant_a,
        document=document,
        version_label="2.0.0",
        major_number=2,
        minor_number=0,
        patch_number=0,
        author=admin_user,
        extracted_text="Version 2 content with regression.",
    )
    document.current_version_label = "2.0.0"
    document.current_version_no = 2
    document.save()

    # Roll back to version 1.0.0
    rollback_url = reverse("documents:document_version_rollback", args=[document_version.pk])
    resp = client.post(rollback_url, follow=True)
    assert resp.status_code == 200

    document.refresh_from_db()
    assert document.current_version_label == "3.0"

    restored = DocumentVersion.objects.filter(document=document, version_label="3.0").first()
    assert restored is not None
    assert restored.version_type == "rollback"
    assert restored.restored_from_version == document_version


@pytest.mark.django_db
def test_version_control_branch_merge_lifecycle(client, tenant_a, admin_user, document, document_version, document_branch):
    """Assert branch merge merges branch revisions into mainline and marks branch merged."""
    client.force_login(admin_user)
    merge_url = reverse("documents:document_branch_merge", args=[document_branch.pk])
    resp = client.post(
        merge_url,
        data={
            "merge_strategy": "new_minor_version",
            "change_summary": "Merged safety spike updates into official mainline.",
            "merge_notes": "All automated safety tests passed.",
        },
        follow=True,
    )
    assert resp.status_code == 200

    document_branch.refresh_from_db()
    document.refresh_from_db()

    assert document_branch.status == "merged"
    assert document_branch.merged_by == admin_user
    assert document.current_version_label == "1.2"


@pytest.mark.django_db
def test_version_control_compare_view_rendering(client, tenant_a, admin_user, document, document_version):
    """Assert version comparison renders side-by-side diff table."""
    client.force_login(admin_user)
    v2 = DocumentVersion.objects.create(
        tenant=tenant_a,
        document=document,
        version_label="1.1.0",
        major_number=1,
        minor_number=1,
        patch_number=0,
        author=admin_user,
        extracted_text="Section 1: Operating protocols and safety checks updated.\nSection 2: Maintenance schedule.",
    )
    compare_url = reverse("documents:document_version_compare") + f"?document={document.pk}&version_a={document_version.pk}&version_b={v2.pk}"
    resp = client.get(compare_url)
    assert resp.status_code == 200
    assert "diff" in resp.content.decode().lower()
