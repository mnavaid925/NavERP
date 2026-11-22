"""Security and authorization tests for Sub-module 13.2 Version Control & Revision Management."""
import pytest
from django.urls import reverse

from apps.documents.models.VersionControl.Documents import Document
from apps.documents.models.VersionControl.DocumentLocks import DocumentLock
from apps.documents.models.VersionControl.DocumentBranches import DocumentBranch


@pytest.mark.django_db
def test_version_control_cross_tenant_idor_document_returns_404(client, tenant_a, tenant_b, admin_user, member_user, document):
    """Assert tenant_b user cannot access tenant_a document (IDOR protection)."""
    # Create user in tenant_b
    member_user.tenant = tenant_b
    member_user.save()
    client.force_login(member_user)

    resp = client.get(reverse("documents:document_detail", args=[document.pk]))
    assert resp.status_code == 404

    edit_resp = client.get(reverse("documents:document_edit", args=[document.pk]))
    assert edit_resp.status_code == 404

    checkout_resp = client.get(reverse("documents:document_checkout", args=[document.pk]))
    assert checkout_resp.status_code == 404


@pytest.mark.django_db
def test_version_control_cross_tenant_idor_version_and_lock_returns_404(client, tenant_b, member_user, document_version, document_lock):
    """Assert tenant_b user cannot access tenant_a versions or locks."""
    member_user.tenant = tenant_b
    member_user.save()
    client.force_login(member_user)

    ver_resp = client.get(reverse("documents:document_version_detail", args=[document_version.pk]))
    assert ver_resp.status_code == 404

    lock_resp = client.get(reverse("documents:document_lock_detail", args=[document_lock.pk]))
    assert lock_resp.status_code == 404


@pytest.mark.django_db
def test_version_control_unauthenticated_access_redirects_login(client, document):
    """Assert unauthenticated requests redirect to login."""
    urls = [
        reverse("documents:document_list"),
        reverse("documents:document_detail", args=[document.pk]),
        reverse("documents:document_version_list"),
        reverse("documents:document_lock_list"),
        reverse("documents:document_branch_list"),
    ]
    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 302
        assert "/login/" in resp.url or "login" in resp.url


@pytest.mark.django_db
def test_version_control_force_unlock_requires_tenant_admin(client, tenant_a, member_user, document_lock):
    """Assert non-admin member cannot force unlock an active lock held by another author (C1)."""
    client.force_login(member_user)
    url = reverse("documents:document_force_unlock", args=[document_lock.pk])
    resp = client.post(url, data={"override_reason": "Unauthorized break attempt"}, follow=True)
    # Redirected with error message or forbidden
    document_lock.refresh_from_db()
    assert document_lock.status == "active"


@pytest.mark.django_db
def test_version_control_delete_requires_admin(client, tenant_a, member_user, document):
    """Assert non-admin user cannot delete documents."""
    client.force_login(member_user)
    delete_url = reverse("documents:document_delete", args=[document.pk])
    resp = client.post(delete_url)
    assert resp.status_code == 403
    assert Document.objects.filter(pk=document.pk).exists()


@pytest.mark.django_db
def test_version_control_branch_abandon_authorization(client, tenant_a, admin_user, member_user, document_branch):
    """Assert non-creator and non-admin member cannot abandon another user's branch (I3)."""
    client.force_login(member_user)
    abandon_url = reverse("documents:document_branch_abandon", args=[document_branch.pk])
    resp = client.post(abandon_url, follow=True)
    document_branch.refresh_from_db()
    assert document_branch.status == "active"
