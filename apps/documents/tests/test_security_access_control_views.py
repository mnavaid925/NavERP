"""View integration and access control tests for Sub-module 13.7: Security & Access Control.

Covers:
- DocumentAccessPermissions views: list, create, detail, edit, delete, simulate.
- WatermarkPolicies views: list, create, detail, edit, delete, preview.
- DocumentDrmPolicies views: list, create, detail, edit, delete, kill_switch.
- DlpPolicies views: list, create, detail, edit, delete.
- DlpIncidents views: list, detail, resolve.
- SecureViewer views: secure_viewer (no params, doc_id, junk params, revoked DRM), secure_viewer_doc.
- Tenant isolation, unauthenticated redirects, and non-admin permission gates.
"""
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog, OrgUnit
from apps.documents.models.SecurityAccessControl.DocumentAccessPermissions import DocumentAccessPermission
from apps.documents.models.SecurityAccessControl.WatermarkPolicies import WatermarkPolicy
from apps.documents.models.SecurityAccessControl.DocumentDrmPolicies import DocumentDrmPolicy
from apps.documents.models.SecurityAccessControl.DlpPolicies import DlpPolicy
from apps.documents.models.SecurityAccessControl.DlpIncidents import DlpIncident
from apps.documents.models.StorageRepository.DocumentFolders import DocumentFolder
from apps.documents.models.VersionControl.Documents import Document


# ============================================================================
# Helpers
# ============================================================================

def _security_access_control_create_doc(
    tenant,
    owner,
    title="Secured Test Spec",
    doc_type="sop",
    classification="confidential",
):
    """Helper to create an active Document in tenant."""
    return Document.objects.create(
        tenant=tenant,
        owner=owner,
        title=title,
        document_type=doc_type,
        classification=classification,
        status="published",
        description="Security view verification document.",
    )


# ============================================================================
# 1. DocumentAccessPermissions View Tests
# ============================================================================

@pytest.mark.django_db
def test_security_access_control_permission_list_standard(client, tenant_a, admin_user, document_permission):
    """Test permission_list renders 200 OK with expected context keys and items."""
    client.force_login(admin_user)
    url = reverse("documents:permission_list")
    res = client.get(url)
    assert res.status_code == 200
    assert "permissions" in res.context
    assert "page_obj" in res.context
    assert "grantee_choices" in res.context
    assert "level_choices" in res.context
    assert document_permission in res.context["permissions"]


@pytest.mark.django_db
def test_security_access_control_permission_list_filters(client, tenant_a, admin_user, member_user, document):
    """Test permission_list filtering by grantee_type, permission_level, is_active, and search query q."""
    client.force_login(admin_user)
    perm_active = DocumentAccessPermission.objects.create(
        tenant=tenant_a,
        document=document,
        grantee_type="user",
        user=member_user,
        permission_level="editor",
        role_name="LeadReviewer",
        notes="AuditSpecialist",
        is_active=True,
        created_by=admin_user,
    )
    perm_inactive = DocumentAccessPermission.objects.create(
        tenant=tenant_a,
        document=document,
        grantee_type="tenant_wide",
        permission_level="viewer",
        role_name="GeneralPublic",
        notes="ExpiredRule",
        is_active=False,
        created_by=admin_user,
    )

    url = reverse("documents:permission_list")

    # Filter by grantee_type
    res_grantee = client.get(url, {"grantee_type": "user"})
    assert res_grantee.status_code == 200
    assert perm_active in res_grantee.context["permissions"]
    assert perm_inactive not in res_grantee.context["permissions"]

    # Filter by permission_level
    res_level = client.get(url, {"permission_level": "viewer"})
    assert res_level.status_code == 200
    assert perm_inactive in res_level.context["permissions"]
    assert perm_active not in res_level.context["permissions"]

    # Filter by is_active=1
    res_active = client.get(url, {"is_active": "1"})
    assert res_active.status_code == 200
    assert perm_active in res_active.context["permissions"]
    assert perm_inactive not in res_active.context["permissions"]

    # Filter by is_active=0
    res_inactive = client.get(url, {"is_active": "0"})
    assert res_inactive.status_code == 200
    assert perm_inactive in res_inactive.context["permissions"]
    assert perm_active not in res_inactive.context["permissions"]

    # Search by q matching role_name
    res_search = client.get(url, {"q": "LeadReviewer"})
    assert res_search.status_code == 200
    assert perm_active in res_search.context["permissions"]
    assert perm_inactive not in res_search.context["permissions"]

    # Filter by document id
    res_doc = client.get(url, {"document": document.pk})
    assert res_doc.status_code == 200
    assert perm_active in res_doc.context["permissions"]


@pytest.mark.django_db
def test_security_access_control_permission_create_get(client, tenant_a, admin_user, document, document_folder):
    """Test permission_create GET renders form with is_edit=False and handles initial query params."""
    client.force_login(admin_user)
    url = reverse("documents:permission_create")
    res = client.get(url, {"document_id": document.pk, "folder_id": document_folder.pk})
    assert res.status_code == 200
    assert "form" in res.context
    assert res.context["is_edit"] is False
    assert res.context["form"].initial.get("document") == document.pk
    assert res.context["form"].initial.get("folder") == document_folder.pk


@pytest.mark.django_db
def test_security_access_control_permission_create_post_valid(client, tenant_a, admin_user, member_user, document):
    """Test permission_create POST valid form creates permission, logs audit event, and redirects to detail."""
    client.force_login(admin_user)
    url = reverse("documents:permission_create")
    data = {
        "document": document.pk,
        "grantee_type": "user",
        "user": member_user.pk,
        "permission_level": "editor",
        "can_read": "on",
        "can_write": "on",
        "can_download": "on",
        "can_print": "on",
        "is_active": "on",
        "notes": "Contractor team access permit",
    }
    res = client.post(url, data)
    assert res.status_code == 302

    created_perm = DocumentAccessPermission.objects.filter(
        tenant=tenant_a,
        document=document,
        user=member_user,
        permission_level="editor",
    ).first()
    assert created_perm is not None
    assert created_perm.created_by == admin_user
    assert created_perm.can_read is True
    assert created_perm.can_write is True
    assert res.url == reverse("documents:permission_detail", kwargs={"pk": created_perm.pk})

    # Assert audit log was recorded
    assert AuditLog.objects.filter(tenant=tenant_a, action="create").exists()


@pytest.mark.django_db
def test_security_access_control_permission_create_post_invalid(client, tenant_a, admin_user):
    """Test permission_create POST invalid form re-renders form with 200 and validation errors."""
    client.force_login(admin_user)
    url = reverse("documents:permission_create")
    # Submitting empty form missing both document and folder
    res = client.post(url, {})
    assert res.status_code == 200
    assert "form" in res.context
    assert res.context["form"].errors


@pytest.mark.django_db
def test_security_access_control_permission_detail(client, tenant_a, admin_user, document_permission):
    """Test permission_detail GET asserts expected context keys (permission, document, folder, grantee)."""
    client.force_login(admin_user)
    url = reverse("documents:permission_detail", kwargs={"pk": document_permission.pk})
    res = client.get(url)
    assert res.status_code == 200
    assert "permission" in res.context
    assert res.context["permission"] == document_permission
    assert "document" in res.context
    assert "folder" in res.context
    assert "grantee" in res.context
    assert res.context["grantee"] == document_permission.grantee_display


@pytest.mark.django_db
def test_security_access_control_permission_edit_get_and_post(client, tenant_a, admin_user, member_user, document_permission):
    """Test permission_edit GET and POST updates fields, writes audit log, and redirects to detail."""
    client.force_login(admin_user)
    url = reverse("documents:permission_edit", kwargs={"pk": document_permission.pk})

    # GET
    res_get = client.get(url)
    assert res_get.status_code == 200
    assert res_get.context["is_edit"] is True
    assert res_get.context["permission"] == document_permission

    # POST update
    data = {
        "document": document_permission.document.pk,
        "grantee_type": "user",
        "user": member_user.pk,
        "permission_level": "manager",
        "can_read": "on",
        "can_write": "on",
        "can_delete": "on",
        "can_download": "on",
        "can_print": "on",
        "can_share": "on",
        "is_active": "on",
        "notes": "Upgraded to full manager capabilities",
    }
    res_post = client.post(url, data)
    assert res_post.status_code == 302
    assert res_post.url == reverse("documents:permission_detail", kwargs={"pk": document_permission.pk})

    document_permission.refresh_from_db()
    assert document_permission.permission_level == "manager"
    assert document_permission.can_delete is True
    assert document_permission.notes == "Upgraded to full manager capabilities"

    # Audit log check
    assert AuditLog.objects.filter(tenant=tenant_a, action="update").exists()


@pytest.mark.django_db
def test_security_access_control_permission_delete_get_405_and_post(client, tenant_a, admin_user, document_permission):
    """Test permission_delete GET returns 405 (require_POST) and POST deletes permission."""
    client.force_login(admin_user)
    url = reverse("documents:permission_delete", kwargs={"pk": document_permission.pk})

    # GET must be rejected
    res_get = client.get(url)
    assert res_get.status_code == 405

    # POST deletes
    perm_id = document_permission.pk
    res_post = client.post(url)
    assert res_post.status_code == 302
    assert res_post.url == reverse("documents:permission_list")
    assert not DocumentAccessPermission.objects.filter(pk=perm_id).exists()
    assert AuditLog.objects.filter(tenant=tenant_a, action="delete").exists()


@pytest.mark.django_db
def test_security_access_control_permission_simulate_initial(client, tenant_a, admin_user, document):
    """Test permission_simulate GET with no query parameters renders initial view with simulated=False."""
    client.force_login(admin_user)
    url = reverse("documents:permission_simulate")
    res = client.get(url)
    assert res.status_code == 200
    assert res.context["simulated"] is False
    assert "documents" in res.context
    assert "users" in res.context
    assert "effective_capabilities" in res.context


@pytest.mark.django_db
def test_security_access_control_permission_simulate_user_with_grant(
    client, tenant_a, admin_user, member_user, document, document_permission
):
    """Test permission_simulate evaluating member_user access with active rule and verifying effective_capabilities."""
    client.force_login(admin_user)
    url = reverse("documents:permission_simulate")

    res = client.get(url, {"document": document.pk, "user": member_user.pk})
    assert res.status_code == 200
    assert res.context["simulated"] is True
    assert res.context["target_document"] == document
    assert res.context["target_user"] == member_user

    eff = res.context["effective_capabilities"]
    assert eff["can_read"] is True
    assert eff["can_write"] is True
    assert eff["can_download"] is True
    assert eff["can_print"] is True
    assert eff["can_delete"] is False

    # Contributing rules validation
    assert len(eff["matched_rules"]) >= 1
    assert any(document_permission.number in r for r in eff["matched_rules"])
    assert any("Editor" in r for r in eff["matched_rules"])
    assert "Aggregated from" in eff["reason"]

    # Audit log check
    assert AuditLog.objects.filter(tenant=tenant_a, action="simulate").exists()


@pytest.mark.django_db
def test_security_access_control_permission_simulate_tenant_admin_bypass(client, tenant_a, admin_user, document):
    """Test permission_simulate evaluates unrestricted bypass for tenant administrator."""
    client.force_login(admin_user)
    url = reverse("documents:permission_simulate")

    res = client.get(url, {"document": document.pk, "user": admin_user.pk})
    assert res.status_code == 200
    eff = res.context["effective_capabilities"]
    assert eff["can_read"] is True
    assert eff["can_write"] is True
    assert eff["can_delete"] is True
    assert "Tenant Admin Bypass" in eff["matched_rules"]


@pytest.mark.django_db
def test_security_access_control_permission_simulate_document_owner(client, tenant_a, admin_user, member_user):
    """Test permission_simulate recognizes primary document owner privileges."""
    client.force_login(admin_user)
    owned_doc = _security_access_control_create_doc(
        tenant=tenant_a,
        owner=member_user,
        title="Member Authored Research",
    )
    url = reverse("documents:permission_simulate")

    res = client.get(url, {"document": owned_doc.pk, "user": member_user.pk})
    assert res.status_code == 200
    eff = res.context["effective_capabilities"]
    assert eff["can_read"] is True
    assert eff["can_write"] is True
    assert eff["can_delete"] is True
    assert any("Document Owner" in r for r in eff["matched_rules"])


# ============================================================================
# 2. WatermarkPolicies View Tests
# ============================================================================

@pytest.mark.django_db
def test_security_access_control_watermark_list_standard(client, tenant_a, admin_user, watermark_policy):
    """Test watermark_list renders 200 OK with expected context keys."""
    client.force_login(admin_user)
    url = reverse("documents:watermark_list")
    res = client.get(url)
    assert res.status_code == 200
    assert "policies" in res.context
    assert "classification_choices" in res.context
    assert watermark_policy in res.context["policies"]


@pytest.mark.django_db
def test_security_access_control_watermark_list_filters(client, tenant_a, admin_user):
    """Test watermark_list filters by classification, is_active, and search q."""
    client.force_login(admin_user)
    wp_conf = WatermarkPolicy.objects.create(
        tenant=tenant_a,
        name="Confidential Watermark Policy",
        slug="conf-wm-policy",
        classification="confidential",
        watermark_text="CONFIDENTIAL",
        is_active=True,
        created_by=admin_user,
    )
    wp_pub = WatermarkPolicy.objects.create(
        tenant=tenant_a,
        name="Public Notice Watermark",
        slug="pub-wm-policy",
        classification="public",
        watermark_text="PUBLIC DISTRIBUTION",
        is_active=False,
        created_by=admin_user,
    )

    url = reverse("documents:watermark_list")

    # Classification filter
    res_cls = client.get(url, {"classification": "confidential"})
    assert res_cls.status_code == 200
    assert wp_conf in res_cls.context["policies"]
    assert wp_pub not in res_cls.context["policies"]

    # Active filter
    res_act = client.get(url, {"is_active": "1"})
    assert res_act.status_code == 200
    assert wp_conf in res_act.context["policies"]
    assert wp_pub not in res_act.context["policies"]

    # Search filter
    res_search = client.get(url, {"q": "Notice"})
    assert res_search.status_code == 200
    assert wp_pub in res_search.context["policies"]
    assert wp_conf not in res_search.context["policies"]


@pytest.mark.django_db
def test_security_access_control_watermark_create_get_and_post(client, tenant_a, admin_user):
    """Test watermark_create GET and POST creates policy and records audit log."""
    client.force_login(admin_user)
    url = reverse("documents:watermark_create")

    # GET
    res_get = client.get(url)
    assert res_get.status_code == 200
    assert res_get.context["is_edit"] is False
    assert "form" in res_get.context

    # POST valid form
    data = {
        "name": "Restricted Board Watermark",
        "slug": "restricted-board-wm",
        "classification": "restricted",
        "document_type": "all",
        "watermark_text": "{{classification}} | {{user_name}}",
        "secondary_text": "DO NOT DISTRIBUTE",
        "position": "diagonal_center",
        "opacity_percent": 30,
        "font_size": 36,
        "font_color": "#DC2626",
        "rotation_angle": -45,
        "banner_position": "both",
        "show_classification_banner": "on",
        "enforce_on_view": "on",
        "enforce_on_download": "on",
        "enforce_on_print": "on",
        "priority": 5,
        "is_active": "on",
    }
    res_post = client.post(url, data)
    assert res_post.status_code == 302

    created_policy = WatermarkPolicy.objects.filter(tenant=tenant_a, slug="restricted-board-wm").first()
    assert created_policy is not None
    assert created_policy.created_by == admin_user
    assert created_policy.opacity_percent == 30
    assert res_post.url == reverse("documents:watermark_detail", kwargs={"pk": created_policy.pk})
    assert AuditLog.objects.filter(tenant=tenant_a, action="create").exists()


@pytest.mark.django_db
def test_security_access_control_watermark_detail(client, tenant_a, admin_user, watermark_policy):
    """Test watermark_detail asserts policy and sample_watermark_text in context."""
    client.force_login(admin_user)
    url = reverse("documents:watermark_detail", kwargs={"pk": watermark_policy.pk})
    res = client.get(url)
    assert res.status_code == 200
    assert "policy" in res.context
    assert res.context["policy"] == watermark_policy
    assert "sample_watermark_text" in res.context
    assert len(res.context["sample_watermark_text"]) > 0


@pytest.mark.django_db
def test_security_access_control_watermark_edit_get_and_post(client, tenant_a, admin_user, watermark_policy):
    """Test watermark_edit GET renders form and POST updates policy."""
    client.force_login(admin_user)
    url = reverse("documents:watermark_edit", kwargs={"pk": watermark_policy.pk})

    # GET
    res_get = client.get(url)
    assert res_get.status_code == 200
    assert res_get.context["is_edit"] is True
    assert res_get.context["policy"] == watermark_policy

    # POST
    data = {
        "name": "Updated Confidential Overlay",
        "slug": watermark_policy.slug,
        "classification": watermark_policy.classification,
        "document_type": watermark_policy.document_type,
        "watermark_text": "{{classification}} | {{ip_address}}",
        "position": "tiled_grid",
        "opacity_percent": 45,
        "font_size": 28,
        "font_color": "#94A3B8",
        "rotation_angle": -30,
        "banner_position": "top",
        "priority": 12,
        "is_active": "on",
    }
    res_post = client.post(url, data)
    assert res_post.status_code == 302
    assert res_post.url == reverse("documents:watermark_detail", kwargs={"pk": watermark_policy.pk})

    watermark_policy.refresh_from_db()
    assert watermark_policy.name == "Updated Confidential Overlay"
    assert watermark_policy.opacity_percent == 45
    assert watermark_policy.position == "tiled_grid"
    assert AuditLog.objects.filter(tenant=tenant_a, action="update").exists()


@pytest.mark.django_db
def test_security_access_control_watermark_delete_get_405_and_post(client, tenant_a, admin_user, watermark_policy):
    """Test watermark_delete GET returns 405 and POST deletes policy."""
    client.force_login(admin_user)
    url = reverse("documents:watermark_delete", kwargs={"pk": watermark_policy.pk})

    # GET returns 405
    res_get = client.get(url)
    assert res_get.status_code == 405

    # POST deletes
    policy_id = watermark_policy.pk
    res_post = client.post(url)
    assert res_post.status_code == 302
    assert res_post.url == reverse("documents:watermark_list")
    assert not WatermarkPolicy.objects.filter(pk=policy_id).exists()
    assert AuditLog.objects.filter(tenant=tenant_a, action="delete").exists()


@pytest.mark.django_db
def test_security_access_control_watermark_preview(client, tenant_a, admin_user, watermark_policy):
    """Test watermark_preview with no query param and with ?policy_id=<pk> verifying canvas context vars."""
    client.force_login(admin_user)
    url = reverse("documents:watermark_preview")

    # Standard default preview
    res_default = client.get(url)
    assert res_default.status_code == 200
    assert "preview_text" in res_default.context
    assert res_default.context["opacity"] == 25
    assert res_default.context["angle"] == -45

    # Preview with specific policy_id
    res_policy = client.get(url, {"policy_id": watermark_policy.pk})
    assert res_policy.status_code == 200
    assert res_policy.context["policy"] == watermark_policy
    assert res_policy.context["opacity"] == watermark_policy.opacity_percent
    assert res_policy.context["angle"] == watermark_policy.rotation_angle
    assert res_policy.context["position"] == watermark_policy.position
    assert watermark_policy.render_watermark(user=admin_user, ip_address="127.0.0.1") in res_policy.context["preview_text"]


# ============================================================================
# 3. DocumentDrmPolicies View Tests
# ============================================================================

@pytest.mark.django_db
def test_security_access_control_drm_policy_list_standard(client, tenant_a, admin_user, drm_policy):
    """Test drm_policy_list renders 200 OK with expected context keys."""
    client.force_login(admin_user)
    url = reverse("documents:drm_policy_list")
    res = client.get(url)
    assert res.status_code == 200
    assert "policies" in res.context
    assert "classification_choices" in res.context
    assert drm_policy in res.context["policies"]


@pytest.mark.django_db
def test_security_access_control_drm_policy_list_filters(client, tenant_a, admin_user, document):
    """Test drm_policy_list filtering by classification, is_revoked, and search q."""
    client.force_login(admin_user)
    drm_active = DocumentDrmPolicy.objects.create(
        tenant=tenant_a,
        name="Board Papers DRM Shield",
        slug="board-drm",
        classification="restricted",
        target_document=document,
        is_revoked=False,
        created_by=admin_user,
    )
    drm_revoked = DocumentDrmPolicy.objects.create(
        tenant=tenant_a,
        name="Public Distribution Shield",
        slug="public-drm",
        classification="public",
        is_revoked=True,
        revocation_reason="Decommissioned test policy",
        created_by=admin_user,
    )

    url = reverse("documents:drm_policy_list")

    # Filter classification
    res_cls = client.get(url, {"classification": "restricted"})
    assert res_cls.status_code == 200
    assert drm_active in res_cls.context["policies"]
    assert drm_revoked not in res_cls.context["policies"]

    # Filter is_revoked=1
    res_revoked = client.get(url, {"is_revoked": "1"})
    assert res_revoked.status_code == 200
    assert drm_revoked in res_revoked.context["policies"]
    assert drm_active not in res_revoked.context["policies"]

    # Filter is_revoked=0
    res_unrevoked = client.get(url, {"is_revoked": "0"})
    assert res_unrevoked.status_code == 200
    assert drm_active in res_unrevoked.context["policies"]
    assert drm_revoked not in res_unrevoked.context["policies"]

    # Search by q
    res_search = client.get(url, {"q": "Board Papers"})
    assert res_search.status_code == 200
    assert drm_active in res_search.context["policies"]
    assert drm_revoked not in res_search.context["policies"]


@pytest.mark.django_db
def test_security_access_control_drm_policy_create_get_and_post(client, tenant_a, admin_user, document):
    """Test drm_policy_create GET and POST creates policy, redirects to detail, and logs audit."""
    client.force_login(admin_user)
    url = reverse("documents:drm_policy_create")

    # GET
    res_get = client.get(url)
    assert res_get.status_code == 200
    assert res_get.context["is_edit"] is False
    assert "form" in res_get.context

    # POST
    data = {
        "name": "Strict Patent Protection DRM",
        "slug": "strict-patent-drm",
        "classification": "restricted",
        "document_type": "all",
        "target_document": document.pk,
        "allow_download": False,
        "allow_print": False,
        "allow_copy_paste": False,
        "screen_shield_enabled": "on",
        "secure_viewer_required": "on",
        "require_watermark": "on",
        "max_offline_hours": 0,
        "expiry_days": 15,
        "encryption_standard": "AES_256_GCM",
        "is_active": "on",
    }
    res_post = client.post(url, data)
    assert res_post.status_code == 302

    created_drm = DocumentDrmPolicy.objects.filter(tenant=tenant_a, slug="strict-patent-drm").first()
    assert created_drm is not None
    assert created_drm.screen_shield_enabled is True
    assert res_post.url == reverse("documents:drm_policy_detail", kwargs={"pk": created_drm.pk})
    assert AuditLog.objects.filter(tenant=tenant_a, action="create").exists()


@pytest.mark.django_db
def test_security_access_control_drm_policy_detail(client, tenant_a, admin_user, drm_policy):
    """Test drm_policy_detail asserts policy in context."""
    client.force_login(admin_user)
    url = reverse("documents:drm_policy_detail", kwargs={"pk": drm_policy.pk})
    res = client.get(url)
    assert res.status_code == 200
    assert "policy" in res.context
    assert res.context["policy"] == drm_policy


@pytest.mark.django_db
def test_security_access_control_drm_policy_edit_get_and_post(client, tenant_a, admin_user, drm_policy):
    """Test drm_policy_edit GET and POST updates policy fields and logs audit."""
    client.force_login(admin_user)
    url = reverse("documents:drm_policy_edit", kwargs={"pk": drm_policy.pk})

    # GET
    res_get = client.get(url)
    assert res_get.status_code == 200
    assert res_get.context["is_edit"] is True
    assert res_get.context["policy"] == drm_policy

    # POST
    data = {
        "name": "Updated NDA DRM Shield",
        "slug": drm_policy.slug,
        "classification": drm_policy.classification,
        "document_type": drm_policy.document_type,
        "allow_download": "on",
        "allow_print": "on",
        "screen_shield_enabled": "on",
        "secure_viewer_required": "on",
        "require_watermark": "on",
        "max_offline_hours": 4,
        "expiry_days": 45,
        "encryption_standard": "AES_256_GCM",
        "is_active": "on",
    }
    res_post = client.post(url, data)
    assert res_post.status_code == 302
    assert res_post.url == reverse("documents:drm_policy_detail", kwargs={"pk": drm_policy.pk})

    drm_policy.refresh_from_db()
    assert drm_policy.name == "Updated NDA DRM Shield"
    assert drm_policy.allow_download is True
    assert drm_policy.max_offline_hours == 4
    assert AuditLog.objects.filter(tenant=tenant_a, action="update").exists()


@pytest.mark.django_db
def test_security_access_control_drm_policy_delete_get_405_and_post(client, tenant_a, admin_user, drm_policy):
    """Test drm_policy_delete GET returns 405 and POST deletes DRM policy."""
    client.force_login(admin_user)
    url = reverse("documents:drm_policy_delete", kwargs={"pk": drm_policy.pk})

    # GET
    res_get = client.get(url)
    assert res_get.status_code == 405

    # POST
    pol_id = drm_policy.pk
    res_post = client.post(url)
    assert res_post.status_code == 302
    assert res_post.url == reverse("documents:drm_policy_list")
    assert not DocumentDrmPolicy.objects.filter(pk=pol_id).exists()
    assert AuditLog.objects.filter(tenant=tenant_a, action="delete").exists()


@pytest.mark.django_db
def test_security_access_control_drm_kill_switch_get_405_and_post_emergency(client, tenant_a, admin_user, drm_policy):
    """Test drm_kill_switch GET returns 405 and POST triggers emergency revocation."""
    client.force_login(admin_user)
    url = reverse("documents:drm_kill_switch", kwargs={"pk": drm_policy.pk})

    # GET
    res_get = client.get(url)
    assert res_get.status_code == 405

    # Emergency Kill Switch POST
    res_post = client.post(url, {"reason": "Suspected credential compromise"})
    assert res_post.status_code == 302
    assert res_post.url == reverse("documents:drm_policy_detail", kwargs={"pk": drm_policy.pk})

    drm_policy.refresh_from_db()
    assert drm_policy.is_revoked is True
    assert drm_policy.is_active is False
    assert drm_policy.revoked_at is not None
    assert drm_policy.revocation_reason == "Suspected credential compromise"
    assert AuditLog.objects.filter(tenant=tenant_a, action="revoke").exists()


@pytest.mark.django_db
def test_security_access_control_drm_kill_switch_repeated_post_status_guard(client, tenant_a, admin_user, drm_policy):
    """Test drm_kill_switch repeated POST is blocked cleanly by status guard."""
    client.force_login(admin_user)
    drm_policy.is_revoked = True
    drm_policy.revocation_reason = "Already revoked"
    drm_policy.save()

    url = reverse("documents:drm_kill_switch", kwargs={"pk": drm_policy.pk})
    res_post = client.post(url, {"reason": "Duplicate attempt"})
    assert res_post.status_code == 302
    assert res_post.url == reverse("documents:drm_policy_detail", kwargs={"pk": drm_policy.pk})

    # Assert revocation reason remained untouched
    drm_policy.refresh_from_db()
    assert drm_policy.revocation_reason == "Already revoked"


# ============================================================================
# 4. DlpPolicies View Tests
# ============================================================================

@pytest.mark.django_db
def test_security_access_control_dlp_policy_list_standard(client, tenant_a, admin_user, dlp_policy):
    """Test dlp_policy_list renders 200 OK with expected context keys."""
    client.force_login(admin_user)
    url = reverse("documents:dlp_policy_list")
    res = client.get(url)
    assert res.status_code == 200
    assert "policies" in res.context
    assert "rule_choices" in res.context
    assert "severity_choices" in res.context
    assert dlp_policy in res.context["policies"]


@pytest.mark.django_db
def test_security_access_control_dlp_policy_list_filters(client, tenant_a, admin_user):
    """Test dlp_policy_list filtering by rule_type, severity, is_active, and search q."""
    client.force_login(admin_user)
    dlp_crit = DlpPolicy.objects.create(
        tenant=tenant_a,
        name="PCI Card Exfiltration Guard",
        slug="pci-guard",
        rule_type="built_in_pattern",
        built_in_pattern="credit_card_pci",
        severity="critical",
        action="block_save",
        is_active=True,
        created_by=admin_user,
    )
    dlp_low = DlpPolicy.objects.create(
        tenant=tenant_a,
        name="General Keyword Alert",
        slug="kw-alert",
        rule_type="sensitive_keywords",
        sensitive_keywords=["Confidential", "Draft"],
        severity="low",
        action="audit_log",
        is_active=False,
        created_by=admin_user,
    )

    url = reverse("documents:dlp_policy_list")

    # Filter rule_type
    res_rule = client.get(url, {"rule_type": "built_in_pattern"})
    assert res_rule.status_code == 200
    assert dlp_crit in res_rule.context["policies"]
    assert dlp_low not in res_rule.context["policies"]

    # Filter severity
    res_sev = client.get(url, {"severity": "critical"})
    assert res_sev.status_code == 200
    assert dlp_crit in res_sev.context["policies"]
    assert dlp_low not in res_sev.context["policies"]

    # Filter is_active
    res_act = client.get(url, {"is_active": "1"})
    assert res_act.status_code == 200
    assert dlp_crit in res_act.context["policies"]
    assert dlp_low not in res_act.context["policies"]

    # Search q
    res_search = client.get(url, {"q": "Card Exfiltration"})
    assert res_search.status_code == 200
    assert dlp_crit in res_search.context["policies"]
    assert dlp_low not in res_search.context["policies"]


@pytest.mark.django_db
def test_security_access_control_dlp_policy_create_get_and_post(client, tenant_a, admin_user):
    """Test dlp_policy_create GET and POST creates DLP policy and logs audit event."""
    client.force_login(admin_user)
    url = reverse("documents:dlp_policy_create")

    # GET
    res_get = client.get(url)
    assert res_get.status_code == 200
    assert res_get.context["is_edit"] is False
    assert "form" in res_get.context

    # POST valid form
    data = {
        "name": "US SSN Data Exfiltration Guard",
        "slug": "us-ssn-guard",
        "rule_type": "built_in_pattern",
        "built_in_pattern": "us_ssn",
        "match_threshold": 1,
        "action": "quarantine",
        "severity": "high",
        "notify_security_officer": "on",
        "notification_email": "security@acme.com",
        "apply_to_all_types": "on",
        "is_active": "on",
    }
    res_post = client.post(url, data)
    assert res_post.status_code == 302

    created_dlp = DlpPolicy.objects.filter(tenant=tenant_a, slug="us-ssn-guard").first()
    assert created_dlp is not None
    assert created_dlp.severity == "high"
    assert created_dlp.action == "quarantine"
    assert res_post.url == reverse("documents:dlp_policy_detail", kwargs={"pk": created_dlp.pk})
    assert AuditLog.objects.filter(tenant=tenant_a, action="create").exists()


@pytest.mark.django_db
def test_security_access_control_dlp_policy_detail(client, tenant_a, admin_user, dlp_policy, dlp_incident):
    """Test dlp_policy_detail asserts policy and related incidents in context."""
    client.force_login(admin_user)
    url = reverse("documents:dlp_policy_detail", kwargs={"pk": dlp_policy.pk})
    res = client.get(url)
    assert res.status_code == 200
    assert "policy" in res.context
    assert res.context["policy"] == dlp_policy
    assert "incidents" in res.context
    assert dlp_incident in res.context["incidents"]


@pytest.mark.django_db
def test_security_access_control_dlp_policy_edit_get_and_post(client, tenant_a, admin_user, dlp_policy):
    """Test dlp_policy_edit GET and POST updates policy attributes and logs audit."""
    client.force_login(admin_user)
    url = reverse("documents:dlp_policy_edit", kwargs={"pk": dlp_policy.pk})

    # GET
    res_get = client.get(url)
    assert res_get.status_code == 200
    assert res_get.context["is_edit"] is True
    assert res_get.context["policy"] == dlp_policy

    # POST
    data = {
        "name": "Updated Card Exfiltration Guard",
        "slug": dlp_policy.slug,
        "rule_type": dlp_policy.rule_type,
        "built_in_pattern": dlp_policy.built_in_pattern,
        "match_threshold": 2,
        "action": "quarantine",
        "severity": "critical",
        "notify_security_officer": "on",
        "notification_email": "alerts@acme.com",
        "apply_to_all_types": "on",
        "is_active": "on",
    }
    res_post = client.post(url, data)
    assert res_post.status_code == 302
    assert res_post.url == reverse("documents:dlp_policy_detail", kwargs={"pk": dlp_policy.pk})

    dlp_policy.refresh_from_db()
    assert dlp_policy.name == "Updated Card Exfiltration Guard"
    assert dlp_policy.match_threshold == 2
    assert dlp_policy.action == "quarantine"
    assert AuditLog.objects.filter(tenant=tenant_a, action="update").exists()


@pytest.mark.django_db
def test_security_access_control_dlp_policy_delete_get_405_and_post(client, tenant_a, admin_user, dlp_policy):
    """Test dlp_policy_delete GET returns 405 and POST deletes policy."""
    client.force_login(admin_user)
    url = reverse("documents:dlp_policy_delete", kwargs={"pk": dlp_policy.pk})

    # GET
    res_get = client.get(url)
    assert res_get.status_code == 405

    # POST
    pol_id = dlp_policy.pk
    res_post = client.post(url)
    assert res_post.status_code == 302
    assert res_post.url == reverse("documents:dlp_policy_list")
    assert not DlpPolicy.objects.filter(pk=pol_id).exists()
    assert AuditLog.objects.filter(tenant=tenant_a, action="delete").exists()


# ============================================================================
# 5. DlpIncidents View Tests
# ============================================================================

@pytest.mark.django_db
def test_security_access_control_dlp_incident_list_standard(client, tenant_a, admin_user, dlp_incident):
    """Test dlp_incident_list renders 200 OK with expected context keys."""
    client.force_login(admin_user)
    url = reverse("documents:dlp_incident_list")
    res = client.get(url)
    assert res.status_code == 200
    assert "incidents" in res.context
    assert "severity_choices" in res.context
    assert "resolution_choices" in res.context
    assert dlp_incident in res.context["incidents"]


@pytest.mark.django_db
def test_security_access_control_dlp_incident_list_filters(client, tenant_a, admin_user, member_user, document, dlp_policy):
    """Test dlp_incident_list filtering by severity, resolution_status, policy, and search q."""
    client.force_login(admin_user)
    inc_open = DlpIncident.objects.create(
        tenant=tenant_a,
        policy=dlp_policy,
        document=document,
        triggered_by=member_user,
        action_taken="blocked",
        severity="critical",
        matches_detected_count=1,
        snippet_redacted="4111-****-****-9999",
        resolution_status="open",
    )
    inc_resolved = DlpIncident.objects.create(
        tenant=tenant_a,
        policy=dlp_policy,
        document=document,
        triggered_by=member_user,
        action_taken="logged",
        severity="low",
        matches_detected_count=1,
        snippet_redacted="Confidential keyword",
        resolution_status="mitigated",
        resolution_notes="Remediated with developer team",
        resolved_by=admin_user,
    )

    url = reverse("documents:dlp_incident_list")

    # Severity filter
    res_sev = client.get(url, {"severity": "critical"})
    assert res_sev.status_code == 200
    assert inc_open in res_sev.context["incidents"]
    assert inc_resolved not in res_sev.context["incidents"]

    # Resolution status filter
    res_res = client.get(url, {"resolution_status": "mitigated"})
    assert res_res.status_code == 200
    assert inc_resolved in res_res.context["incidents"]
    assert inc_open not in res_res.context["incidents"]

    # Policy filter
    res_pol = client.get(url, {"policy": dlp_policy.pk})
    assert res_pol.status_code == 200
    assert inc_open in res_pol.context["incidents"]

    # Search q
    res_search = client.get(url, {"q": "9999"})
    assert res_search.status_code == 200
    assert inc_open in res_search.context["incidents"]
    assert inc_resolved not in res_search.context["incidents"]


@pytest.mark.django_db
def test_security_access_control_dlp_incident_detail(client, tenant_a, admin_user, dlp_incident):
    """Test dlp_incident_detail asserts incident and resolve_form in context."""
    client.force_login(admin_user)
    url = reverse("documents:dlp_incident_detail", kwargs={"pk": dlp_incident.pk})
    res = client.get(url)
    assert res.status_code == 200
    assert "incident" in res.context
    assert res.context["incident"] == dlp_incident
    assert "resolve_form" in res.context


@pytest.mark.django_db
def test_security_access_control_dlp_incident_resolve_get_405_and_post_valid(client, tenant_a, admin_user, dlp_incident):
    """Test dlp_incident_resolve GET returns 405 and POST resolves incident with triage notes."""
    client.force_login(admin_user)
    url = reverse("documents:dlp_incident_resolve", kwargs={"pk": dlp_incident.pk})

    # GET
    res_get = client.get(url)
    assert res_get.status_code == 405

    # POST valid resolution
    data = {
        "resolution_status": "false_positive",
        "resolution_notes": "Identified as synthetic mock test numbers used in unit tests.",
    }
    res_post = client.post(url, data)
    assert res_post.status_code == 302
    assert res_post.url == reverse("documents:dlp_incident_detail", kwargs={"pk": dlp_incident.pk})

    dlp_incident.refresh_from_db()
    assert dlp_incident.resolution_status == "false_positive"
    assert dlp_incident.resolved_by == admin_user
    assert "synthetic mock test numbers" in dlp_incident.resolution_notes
    assert AuditLog.objects.filter(tenant=tenant_a, action="resolve").exists()


@pytest.mark.django_db
def test_security_access_control_dlp_incident_resolve_post_invalid(client, tenant_a, admin_user, dlp_incident):
    """Test dlp_incident_resolve POST with missing resolution notes reports error and does not resolve."""
    client.force_login(admin_user)
    url = reverse("documents:dlp_incident_resolve", kwargs={"pk": dlp_incident.pk})

    # Missing required resolution_notes
    data = {
        "resolution_status": "mitigated",
        "resolution_notes": "",
    }
    res_post = client.post(url, data)
    assert res_post.status_code == 302

    dlp_incident.refresh_from_db()
    assert dlp_incident.resolution_status == "open"


# ============================================================================
# 6. SecureViewer View Tests
# ============================================================================

@pytest.mark.django_db
def test_security_access_control_secure_viewer_no_params(client, tenant_a, admin_user, document):
    """Test secure_viewer GET with no params selects default document and sets up security context."""
    client.force_login(admin_user)
    url = reverse("documents:secure_viewer")
    res = client.get(url)
    assert res.status_code == 200
    assert "document" in res.context
    assert res.context["document"] == document
    assert "has_read_permission" in res.context
    assert res.context["has_read_permission"] is True
    assert "is_drm_revoked" in res.context
    assert res.context["is_drm_revoked"] is False
    assert "watermark_text" in res.context
    assert "screen_shield" in res.context
    assert "available_documents" in res.context


@pytest.mark.django_db
def test_security_access_control_secure_viewer_with_doc_id(client, tenant_a, admin_user):
    """Test secure_viewer GET with ?doc_id=<pk> loads targeted document."""
    client.force_login(admin_user)
    doc_target = _security_access_control_create_doc(
        tenant=tenant_a,
        owner=admin_user,
        title="Target Calibration Manual",
    )
    url = reverse("documents:secure_viewer")
    res = client.get(url, {"doc_id": doc_target.pk})
    assert res.status_code == 200
    assert res.context["document"] == doc_target


@pytest.mark.django_db
def test_security_access_control_secure_viewer_with_invalid_junk_param(client, tenant_a, admin_user, document):
    """Test secure_viewer GET with junk non-numeric ?doc_id=invalid does not 500."""
    client.force_login(admin_user)
    url = reverse("documents:secure_viewer")
    res = client.get(url, {"doc_id": "invalid_string_not_numeric!"})
    assert res.status_code == 200
    # Must gracefully fall back to first document
    assert res.context["document"] == document


@pytest.mark.django_db
def test_security_access_control_secure_viewer_revoked_drm_policy(client, tenant_a, admin_user, document, drm_policy):
    """Test secure_viewer displays emergency revocation notice when document DRM policy is revoked."""
    client.force_login(admin_user)
    drm_policy.is_revoked = True
    drm_policy.revocation_reason = "Mandatory emergency containment"
    drm_policy.save()

    url = reverse("documents:secure_viewer")
    res = client.get(url, {"doc_id": document.pk})
    assert res.status_code == 200
    assert res.context["is_drm_revoked"] is True
    assert AuditLog.objects.filter(tenant=tenant_a).exists()


@pytest.mark.django_db
def test_security_access_control_secure_viewer_doc_endpoint(client, tenant_a, admin_user, document):
    """Test secure_viewer_doc parameterized URL `/documents/secure-viewer/<pk>/`."""
    client.force_login(admin_user)
    url = reverse("documents:secure_viewer_doc", kwargs={"pk": document.pk})
    res = client.get(url)
    assert res.status_code == 200
    assert res.context["document"] == document


@pytest.mark.django_db
def test_security_access_control_secure_viewer_doc_not_found_404(client, tenant_a, admin_user):
    """Test secure_viewer_doc returns 404 for non-existent document ID."""
    client.force_login(admin_user)
    url = reverse("documents:secure_viewer_doc", kwargs={"pk": 999999})
    res = client.get(url)
    assert res.status_code == 404


@pytest.mark.django_db
def test_security_access_control_secure_viewer_empty_repository(client, tenant_a, admin_user):
    """Test secure_viewer renders cleanly when tenant has no documents."""
    client.force_login(admin_user)
    Document.objects.filter(tenant=tenant_a).delete()
    url = reverse("documents:secure_viewer")
    res = client.get(url)
    assert res.status_code == 200
    assert res.context["document"] is None


# ============================================================================
# 7. Security, Tenant Isolation & Access Gates
# ============================================================================

@pytest.mark.django_db
def test_security_access_control_unauthenticated_redirects(client, tenant_a, document_permission):
    """Test unauthenticated requests to protected endpoints redirect to login."""
    urls = [
        reverse("documents:permission_list"),
        reverse("documents:permission_create"),
        reverse("documents:permission_detail", kwargs={"pk": document_permission.pk}),
        reverse("documents:permission_simulate"),
        reverse("documents:watermark_list"),
        reverse("documents:watermark_create"),
        reverse("documents:watermark_preview"),
        reverse("documents:drm_policy_list"),
        reverse("documents:drm_policy_create"),
        reverse("documents:dlp_policy_list"),
        reverse("documents:dlp_policy_create"),
        reverse("documents:dlp_incident_list"),
        reverse("documents:secure_viewer"),
    ]
    for url in urls:
        res = client.get(url)
        assert res.status_code == 302
        assert "/accounts/login/" in res.url or "/login/" in res.url


@pytest.mark.django_db
def test_security_access_control_non_admin_forbidden_actions(
    client, tenant_a, member_user, document_permission, watermark_policy, drm_policy, dlp_policy, dlp_incident
):
    """Test regular non-admin member is forbidden (403) from accessing tenant-admin-required actions."""
    client.force_login(member_user)

    # Permission write views
    res_perm_create = client.get(reverse("documents:permission_create"))
    assert res_perm_create.status_code == 403

    res_perm_edit = client.get(reverse("documents:permission_edit", kwargs={"pk": document_permission.pk}))
    assert res_perm_edit.status_code == 403

    res_perm_del = client.post(reverse("documents:permission_delete", kwargs={"pk": document_permission.pk}))
    assert res_perm_del.status_code == 403

    # Watermark write views
    res_wm_create = client.get(reverse("documents:watermark_create"))
    assert res_wm_create.status_code == 403

    res_wm_edit = client.get(reverse("documents:watermark_edit", kwargs={"pk": watermark_policy.pk}))
    assert res_wm_edit.status_code == 403

    res_wm_del = client.post(reverse("documents:watermark_delete", kwargs={"pk": watermark_policy.pk}))
    assert res_wm_del.status_code == 403

    # DRM write views
    res_drm_create = client.get(reverse("documents:drm_policy_create"))
    assert res_drm_create.status_code == 403

    res_drm_edit = client.get(reverse("documents:drm_policy_edit", kwargs={"pk": drm_policy.pk}))
    assert res_drm_edit.status_code == 403

    res_drm_del = client.post(reverse("documents:drm_policy_delete", kwargs={"pk": drm_policy.pk}))
    assert res_drm_del.status_code == 403

    res_drm_kill = client.post(reverse("documents:drm_kill_switch", kwargs={"pk": drm_policy.pk}))
    assert res_drm_kill.status_code == 403

    # DLP write views
    res_dlp_create = client.get(reverse("documents:dlp_policy_create"))
    assert res_dlp_create.status_code == 403

    res_dlp_edit = client.get(reverse("documents:dlp_policy_edit", kwargs={"pk": dlp_policy.pk}))
    assert res_dlp_edit.status_code == 403

    res_dlp_del = client.post(reverse("documents:dlp_policy_delete", kwargs={"pk": dlp_policy.pk}))
    assert res_dlp_del.status_code == 403

    # DLP Incident resolve view
    res_inc_resolve = client.post(reverse("documents:dlp_incident_resolve", kwargs={"pk": dlp_incident.pk}))
    assert res_inc_resolve.status_code == 403


@pytest.mark.django_db
def test_security_access_control_cross_tenant_isolation_404(
    client, tenant_a, tenant_b, admin_b, document_permission, watermark_policy, drm_policy, dlp_policy, dlp_incident
):
    """Test tenant B administrator receives 404 when attempting to access tenant A security entities."""
    client.force_login(admin_b)

    # Permission detail of tenant A
    res_perm = client.get(reverse("documents:permission_detail", kwargs={"pk": document_permission.pk}))
    assert res_perm.status_code == 404

    # Watermark detail of tenant A
    res_wm = client.get(reverse("documents:watermark_detail", kwargs={"pk": watermark_policy.pk}))
    assert res_wm.status_code == 404

    # DRM policy detail of tenant A
    res_drm = client.get(reverse("documents:drm_policy_detail", kwargs={"pk": drm_policy.pk}))
    assert res_drm.status_code == 404

    # DLP policy detail of tenant A
    res_dlp = client.get(reverse("documents:dlp_policy_detail", kwargs={"pk": dlp_policy.pk}))
    assert res_dlp.status_code == 404

    # DLP incident detail of tenant A
    res_inc = client.get(reverse("documents:dlp_incident_detail", kwargs={"pk": dlp_incident.pk}))
    assert res_inc.status_code == 404
