"""Security, authorization, and multi-tenant isolation unit tests for Sub-module 13.7: Document Security & Access Control."""
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.documents.models.SecurityAccessControl.DocumentAccessPermissions import DocumentAccessPermission
from apps.documents.models.SecurityAccessControl.WatermarkPolicies import WatermarkPolicy
from apps.documents.models.SecurityAccessControl.DocumentDrmPolicies import DocumentDrmPolicy
from apps.documents.models.SecurityAccessControl.DlpPolicies import DlpPolicy
from apps.documents.models.SecurityAccessControl.DlpIncidents import DlpIncident


@pytest.mark.django_db
def test_security_access_control_unauthenticated_access_redirects(
    client, document_permission, watermark_policy, drm_policy, dlp_policy, dlp_incident, document
):
    """Test that all Sub-module 13.7 endpoints redirect unauthenticated requests to login."""
    endpoints = [
        reverse("documents:permission_list"),
        reverse("documents:permission_create"),
        reverse("documents:permission_simulate"),
        reverse("documents:permission_detail", args=[document_permission.pk]),
        reverse("documents:permission_edit", args=[document_permission.pk]),
        reverse("documents:watermark_list"),
        reverse("documents:watermark_create"),
        reverse("documents:watermark_preview"),
        reverse("documents:watermark_detail", args=[watermark_policy.pk]),
        reverse("documents:watermark_edit", args=[watermark_policy.pk]),
        reverse("documents:drm_policy_list"),
        reverse("documents:drm_policy_create"),
        reverse("documents:drm_policy_detail", args=[drm_policy.pk]),
        reverse("documents:drm_policy_edit", args=[drm_policy.pk]),
        reverse("documents:dlp_policy_list"),
        reverse("documents:dlp_policy_create"),
        reverse("documents:dlp_policy_detail", args=[dlp_policy.pk]),
        reverse("documents:dlp_policy_edit", args=[dlp_policy.pk]),
        reverse("documents:dlp_incident_list"),
        reverse("documents:dlp_incident_detail", args=[dlp_incident.pk]),
        reverse("documents:secure_viewer"),
        reverse("documents:secure_viewer_doc", args=[document.pk]),
    ]
    for url in endpoints:
        res = client.get(url)
        assert res.status_code == 302, f"Expected 302 redirect for {url}, got {res.status_code}"
        assert "/login/" in res.headers["Location"]


@pytest.mark.django_db
def test_security_access_control_admin_authorization_enforced(
    member_client, document_permission, watermark_policy, drm_policy, dlp_policy, dlp_incident
):
    """Test that non-admin member is forbidden (403) from accessing admin-restricted security views."""
    admin_restricted_gets = [
        reverse("documents:permission_create"),
        reverse("documents:permission_edit", args=[document_permission.pk]),
        reverse("documents:watermark_create"),
        reverse("documents:watermark_edit", args=[watermark_policy.pk]),
        reverse("documents:drm_policy_create"),
        reverse("documents:drm_policy_edit", args=[drm_policy.pk]),
        reverse("documents:dlp_policy_create"),
        reverse("documents:dlp_policy_edit", args=[dlp_policy.pk]),
    ]
    for url in admin_restricted_gets:
        res = member_client.get(url)
        assert res.status_code == 403, f"Expected 403 for {url}, got {res.status_code}"

    admin_restricted_posts = [
        reverse("documents:permission_delete", args=[document_permission.pk]),
        reverse("documents:watermark_delete", args=[watermark_policy.pk]),
        reverse("documents:drm_policy_delete", args=[drm_policy.pk]),
        reverse("documents:drm_kill_switch", args=[drm_policy.pk]),
        reverse("documents:dlp_policy_delete", args=[dlp_policy.pk]),
        reverse("documents:dlp_incident_resolve", args=[dlp_incident.pk]),
    ]
    for url in admin_restricted_posts:
        res = member_client.post(url, {})
        assert res.status_code == 403, f"Expected 403 for POST {url}, got {res.status_code}"


@pytest.mark.django_db
def test_security_access_control_cross_tenant_idor_get_protection(
    client_b, document_permission, watermark_policy, drm_policy, dlp_policy, dlp_incident, document
):
    """Test that tenant B cannot read tenant A security objects or documents (must return 404)."""
    # 1. DocumentAccessPermission
    assert client_b.get(reverse("documents:permission_detail", args=[document_permission.pk])).status_code == 404
    assert client_b.get(reverse("documents:permission_edit", args=[document_permission.pk])).status_code == 404

    # 2. WatermarkPolicy
    assert client_b.get(reverse("documents:watermark_detail", args=[watermark_policy.pk])).status_code == 404
    assert client_b.get(reverse("documents:watermark_edit", args=[watermark_policy.pk])).status_code == 404

    # 3. DocumentDrmPolicy
    assert client_b.get(reverse("documents:drm_policy_detail", args=[drm_policy.pk])).status_code == 404
    assert client_b.get(reverse("documents:drm_policy_edit", args=[drm_policy.pk])).status_code == 404

    # 4. DlpPolicy
    assert client_b.get(reverse("documents:dlp_policy_detail", args=[dlp_policy.pk])).status_code == 404
    assert client_b.get(reverse("documents:dlp_policy_edit", args=[dlp_policy.pk])).status_code == 404

    # 5. DlpIncident
    assert client_b.get(reverse("documents:dlp_incident_detail", args=[dlp_incident.pk])).status_code == 404

    # 6. Secure Viewer & Simulator targeting Tenant A's document
    assert client_b.get(reverse("documents:secure_viewer_doc", args=[document.pk])).status_code == 404
    assert client_b.get(f"{reverse('documents:secure_viewer')}?doc_id={document.pk}").status_code == 404
    sim_res = client_b.get(f"{reverse('documents:permission_simulate')}?document={document.pk}")
    assert sim_res.status_code == 200
    assert sim_res.context["target_document"] is None
    assert sim_res.context["simulated"] is False


@pytest.mark.django_db
def test_security_access_control_cross_tenant_idor_post_mutations_protection(
    client_b, document_permission, watermark_policy, drm_policy, dlp_policy, dlp_incident
):
    """Test that tenant B cannot execute POST mutations against tenant A objects (must return 404)."""
    # 1. Permission mutations
    assert client_b.post(
        reverse("documents:permission_edit", args=[document_permission.pk]),
        {"notes": "Tampered Note"},
    ).status_code == 404
    assert client_b.post(reverse("documents:permission_delete", args=[document_permission.pk])).status_code == 404

    # 2. Watermark mutations
    assert client_b.post(
        reverse("documents:watermark_edit", args=[watermark_policy.pk]),
        {"name": "Tampered Policy"},
    ).status_code == 404
    assert client_b.post(reverse("documents:watermark_delete", args=[watermark_policy.pk])).status_code == 404

    # 3. DRM mutations & kill switch
    assert client_b.post(
        reverse("documents:drm_policy_edit", args=[drm_policy.pk]),
        {"name": "Tampered DRM"},
    ).status_code == 404
    assert client_b.post(reverse("documents:drm_policy_delete", args=[drm_policy.pk])).status_code == 404
    assert client_b.post(
        reverse("documents:drm_kill_switch", args=[drm_policy.pk]),
        {"reason": "Malicious Kill"},
    ).status_code == 404

    # 4. DLP mutations
    assert client_b.post(
        reverse("documents:dlp_policy_edit", args=[dlp_policy.pk]),
        {"name": "Tampered DLP"},
    ).status_code == 404
    assert client_b.post(reverse("documents:dlp_policy_delete", args=[dlp_policy.pk])).status_code == 404

    # 5. Incident resolve
    assert client_b.post(
        reverse("documents:dlp_incident_resolve", args=[dlp_incident.pk]),
        {"resolution_status": "dismissed", "resolution_notes": "Cross-tenant bypass attempt."},
    ).status_code == 404


@pytest.mark.django_db
def test_security_access_control_require_post_enforced(
    admin_client, document_permission, watermark_policy, drm_policy, dlp_policy, dlp_incident
):
    """Test that mutating actions reject GET requests with 405 Method Not Allowed."""
    endpoints = [
        reverse("documents:permission_delete", args=[document_permission.pk]),
        reverse("documents:watermark_delete", args=[watermark_policy.pk]),
        reverse("documents:drm_policy_delete", args=[drm_policy.pk]),
        reverse("documents:drm_kill_switch", args=[drm_policy.pk]),
        reverse("documents:dlp_policy_delete", args=[dlp_policy.pk]),
        reverse("documents:dlp_incident_resolve", args=[dlp_incident.pk]),
    ]
    for url in endpoints:
        res = admin_client.get(url)
        assert res.status_code == 405, f"Expected 405 for GET {url}, got {res.status_code}"


@pytest.mark.django_db
def test_security_access_control_drm_kill_switch_repeated_post_status_guard(
    admin_client, drm_policy
):
    """Test that executing drm_kill_switch repeatedly is blocked cleanly by view status guard."""
    url = reverse("documents:drm_kill_switch", args=[drm_policy.pk])
    
    # Run 1: Revoke
    res1 = admin_client.post(url, {"reason": "Suspected data leak via leaked token."})
    assert res1.status_code == 302
    drm_policy.refresh_from_db()
    assert drm_policy.is_revoked is True
    assert drm_policy.is_active is False
    assert drm_policy.revoked_at is not None
    original_revoked_at = drm_policy.revoked_at
    original_reason = drm_policy.revocation_reason

    # Run 2: Repeated POST must be blocked without altering audit timestamp or reason
    res2 = admin_client.post(url, {"reason": "Second tampering attempt."})
    assert res2.status_code == 302
    drm_policy.refresh_from_db()
    assert drm_policy.revoked_at == original_revoked_at
    assert drm_policy.revocation_reason == original_reason


@pytest.mark.django_db
def test_security_access_control_secure_viewer_revoked_drm_block(
    admin_client, document, drm_policy
):
    """Test that secure_viewer displays an emergency revocation notice when DRM policy is revoked."""
    # Revoke DRM policy
    drm_policy.revoke(user=None, reason="Executive kill switch engaged.")

    viewer_url = reverse("documents:secure_viewer_doc", args=[document.pk])
    res = admin_client.get(viewer_url)
    assert res.status_code == 200
    assert res.context["is_drm_revoked"] is True
    assert "Access Terminated by Emergency Kill-Switch" in res.content.decode("utf-8")


@pytest.mark.django_db
def test_security_access_control_mass_assignment_protection(
    admin_client, tenant_a, tenant_b, admin_user, document
):
    """Test that POST payloads attempting to inject system or foreign fields are ignored/excluded."""
    post_data = {
        "tenant": tenant_b.pk,
        "number": "DPRM-99999",
        "created_by": 9999,
        "access_count": 999,
        "document": document.pk,
        "grantee_type": "user",
        "user": admin_user.pk,
        "permission_level": "viewer",
        "can_read": "on",
    }
    res = admin_client.post(reverse("documents:permission_create"), post_data)
    assert res.status_code == 302

    created_perm = DocumentAccessPermission.objects.filter(tenant=tenant_a, document=document).first()
    assert created_perm is not None
    # Tenant must be tenant_a, created_by must be admin_user, number must not be overridden
    assert created_perm.tenant == tenant_a
    assert created_perm.created_by == admin_user
    assert created_perm.number != "DPRM-99999"
    assert created_perm.number.startswith("DPRM-")
    assert created_perm.access_count == 0
