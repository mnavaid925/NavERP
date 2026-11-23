"""Unit tests for Sub-module 13.7 Security & Access Control forms."""
from datetime import timedelta
import pytest
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import OrgUnit
from apps.documents.forms._common import reject_foreign
from apps.documents.forms.SecurityAccessControl.DocumentAccessPermissions import DocumentAccessPermissionForm
from apps.documents.forms.SecurityAccessControl.WatermarkPolicies import WatermarkPolicyForm
from apps.documents.forms.SecurityAccessControl.DocumentDrmPolicies import DocumentDrmPolicyForm
from apps.documents.forms.SecurityAccessControl.DlpPolicies import DlpPolicyForm
from apps.documents.forms.SecurityAccessControl.DlpIncidents import DlpIncidentResolveForm

from apps.documents.models.SecurityAccessControl.DocumentAccessPermissions import DocumentAccessPermission
from apps.documents.models.SecurityAccessControl.WatermarkPolicies import WatermarkPolicy
from apps.documents.models.SecurityAccessControl.DocumentDrmPolicies import DocumentDrmPolicy
from apps.documents.models.SecurityAccessControl.DlpPolicies import DlpPolicy
from apps.documents.models.SecurityAccessControl.DlpIncidents import DlpIncident
from apps.documents.models.StorageRepository.DocumentFolders import DocumentFolder
from apps.documents.models.VersionControl.Documents import Document


# ============================================================================
# Helpers (Must be prefixed with _security_access_control_*)
# ============================================================================

def _security_access_control_create_org_unit(tenant, name="Legal & Compliance"):
    """Helper to create an OrgUnit for a specific tenant."""
    return OrgUnit.objects.create(
        tenant=tenant,
        name=name,
        kind="department",
    )


def _security_access_control_create_foreign_doc(tenant_b, admin_b, title="Globex Secret Contract"):
    """Helper to create a Document belonging to foreign tenant_b."""
    return Document.objects.create(
        tenant=tenant_b,
        title=title,
        owner=admin_b,
        document_type="contract",
        classification="confidential",
        status="published",
    )


def _security_access_control_create_foreign_folder(tenant_b, admin_b, name="Globex Secure Vault"):
    """Helper to create a DocumentFolder belonging to foreign tenant_b."""
    return DocumentFolder.objects.create(
        tenant=tenant_b,
        name=name,
        owner=admin_b,
    )


# ============================================================================
# 1. DocumentAccessPermissionForm Tests
# ============================================================================

@pytest.mark.django_db
def test_security_access_control_document_permission_form_exclusions():
    """Verify system-managed and sensitive fields are excluded from DocumentAccessPermissionForm."""
    form = DocumentAccessPermissionForm()
    excluded = [
        "tenant",
        "number",
        "created_by",
        "access_count",
        "last_accessed_at",
        "created_at",
        "updated_at",
    ]
    for field in excluded:
        assert field not in form.fields, f"Security violation: {field} exposed in DocumentAccessPermissionForm"

    expected_fields = {
        "document",
        "folder",
        "grantee_type",
        "user",
        "org_unit",
        "role_name",
        "permission_level",
        "can_read",
        "can_write",
        "can_delete",
        "can_download",
        "can_print",
        "can_share",
        "valid_from",
        "valid_until",
        "is_active",
        "notes",
    }
    assert set(form.fields.keys()) == expected_fields


@pytest.mark.django_db
def test_security_access_control_document_permission_form_fk_scoping(
    tenant_a, tenant_b, admin_user, member_user, admin_b, document, document_folder, org_unit_a
):
    """Test that Foreign Key querysets for document, folder, user, and org_unit are strictly tenant-scoped."""
    foreign_doc = _security_access_control_create_foreign_doc(tenant_b, admin_b)
    foreign_folder = _security_access_control_create_foreign_folder(tenant_b, admin_b)
    foreign_ou = _security_access_control_create_org_unit(tenant_b, name="Globex Dept")

    form = DocumentAccessPermissionForm(tenant=tenant_a)

    # Document scoping
    assert document in form.fields["document"].queryset
    assert foreign_doc not in form.fields["document"].queryset

    # Folder scoping
    assert document_folder in form.fields["folder"].queryset
    assert foreign_folder not in form.fields["folder"].queryset

    # User scoping
    assert admin_user in form.fields["user"].queryset
    assert member_user in form.fields["user"].queryset
    assert admin_b not in form.fields["user"].queryset

    # OrgUnit scoping
    assert org_unit_a in form.fields["org_unit"].queryset
    assert foreign_ou not in form.fields["org_unit"].queryset


@pytest.mark.django_db
def test_security_access_control_document_permission_form_valid_user_grantee(
    tenant_a, admin_user, member_user, document
):
    """Test valid permission submission targeting a Document and a specific User grantee."""
    data = {
        "document": document.pk,
        "grantee_type": "user",
        "user": member_user.pk,
        "permission_level": "editor",
        "can_read": True,
        "can_write": True,
        "can_delete": False,
        "can_download": True,
        "can_print": True,
        "can_share": False,
        "is_active": True,
        "notes": "Granted for Q4 financial review project",
    }
    form = DocumentAccessPermissionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    perm = form.save(commit=False)
    perm.created_by = admin_user
    perm.save()

    assert perm.pk is not None
    assert perm.tenant == tenant_a
    assert perm.document == document
    assert perm.folder is None
    assert perm.grantee_type == "user"
    assert perm.user == member_user
    assert perm.permission_level == "editor"
    assert perm.can_read is True
    assert perm.can_write is True
    assert perm.can_delete is False
    assert perm.notes == "Granted for Q4 financial review project"


@pytest.mark.django_db
def test_security_access_control_document_permission_form_valid_org_unit_grantee(
    tenant_a, admin_user, document_folder, org_unit_a
):
    """Test valid permission submission targeting a DocumentFolder and an OrgUnit grantee."""
    data = {
        "folder": document_folder.pk,
        "grantee_type": "org_unit",
        "org_unit": org_unit_a.pk,
        "permission_level": "viewer",
        "can_read": True,
        "can_write": False,
        "can_delete": False,
        "can_download": False,
        "can_print": False,
        "can_share": False,
        "is_active": True,
    }
    form = DocumentAccessPermissionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    perm = form.save(commit=False)
    perm.created_by = admin_user
    perm.save()

    assert perm.folder == document_folder
    assert perm.document is None
    assert perm.grantee_type == "org_unit"
    assert perm.org_unit == org_unit_a
    assert perm.permission_level == "viewer"


@pytest.mark.django_db
def test_security_access_control_document_permission_form_valid_role_grantee(
    tenant_a, admin_user, document
):
    """Test valid permission submission targeting a Document and a Role grantee."""
    data = {
        "document": document.pk,
        "grantee_type": "role",
        "role_name": "Compliance Auditor",
        "permission_level": "commenter",
        "can_read": True,
        "can_write": False,
        "can_delete": False,
        "can_download": True,
        "can_print": True,
        "can_share": False,
        "is_active": True,
        "notes": "External audit compliance engagement",
    }
    form = DocumentAccessPermissionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    perm = form.save(commit=False)
    perm.created_by = admin_user
    perm.save()

    assert perm.grantee_type == "role"
    assert perm.role_name == "Compliance Auditor"
    assert perm.user is None
    assert perm.org_unit is None


@pytest.mark.django_db
def test_security_access_control_document_permission_form_valid_tenant_wide_grantee(
    tenant_a, admin_user, document
):
    """Test valid permission submission targeting a Document with tenant_wide scope."""
    data = {
        "document": document.pk,
        "grantee_type": "tenant_wide",
        "permission_level": "viewer",
        "can_read": True,
        "can_download": True,
        "is_active": True,
    }
    form = DocumentAccessPermissionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    perm = form.save(commit=False)
    perm.created_by = admin_user
    perm.save()

    assert perm.grantee_type == "tenant_wide"
    assert perm.user is None
    assert perm.org_unit is None
    assert perm.role_name == ""


@pytest.mark.django_db
def test_security_access_control_document_permission_form_target_required(
    tenant_a, member_user
):
    """Validation test: submitting without specifying neither a document nor a folder raises non-field error."""
    data = {
        "grantee_type": "user",
        "user": member_user.pk,
        "permission_level": "viewer",
        "can_read": True,
    }
    form = DocumentAccessPermissionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "__all__" in form.errors
    assert "You must specify either a target Document or a target Folder." in form.errors["__all__"]


@pytest.mark.django_db
def test_security_access_control_document_permission_form_grantee_validation_errors(
    tenant_a, document
):
    """Validation test: each grantee_type requires its corresponding grantee field to be provided."""
    # 1. Specific User missing user
    data_user = {
        "document": document.pk,
        "grantee_type": "user",
        "permission_level": "viewer",
    }
    form_user = DocumentAccessPermissionForm(data=data_user, tenant=tenant_a)
    assert not form_user.is_valid()
    assert "user" in form_user.errors
    assert "User must be selected when Grantee Type is 'Specific User'." in form_user.errors["user"]

    # 2. Org Unit missing org_unit
    data_ou = {
        "document": document.pk,
        "grantee_type": "org_unit",
        "permission_level": "viewer",
    }
    form_ou = DocumentAccessPermissionForm(data=data_ou, tenant=tenant_a)
    assert not form_ou.is_valid()
    assert "org_unit" in form_ou.errors
    assert "Organizational Unit must be selected when Grantee Type is 'Org Unit'." in form_ou.errors["org_unit"]

    # 3. Role missing role_name
    data_role = {
        "document": document.pk,
        "grantee_type": "role",
        "permission_level": "viewer",
        "role_name": "",
    }
    form_role = DocumentAccessPermissionForm(data=data_role, tenant=tenant_a)
    assert not form_role.is_valid()
    assert "role_name" in form_role.errors
    assert "Role Name is required when Grantee Type is 'Role'." in form_role.errors["role_name"]


@pytest.mark.django_db
def test_security_access_control_document_permission_form_stale_grantee_fields_cleared(
    tenant_a, member_user, org_unit_a, document
):
    """Test that clean() clears non-applicable grantee fields when grantee_type is switched."""
    # User grantee clears org_unit and role_name
    data_user = {
        "document": document.pk,
        "grantee_type": "user",
        "user": member_user.pk,
        "org_unit": org_unit_a.pk,
        "role_name": "Stale Role",
        "permission_level": "viewer",
    }
    form_user = DocumentAccessPermissionForm(data=data_user, tenant=tenant_a)
    assert form_user.is_valid(), form_user.errors
    assert form_user.cleaned_data["user"] == member_user
    assert form_user.cleaned_data["org_unit"] is None
    assert form_user.cleaned_data["role_name"] == ""

    # OrgUnit grantee clears user and role_name
    data_ou = {
        "document": document.pk,
        "grantee_type": "org_unit",
        "org_unit": org_unit_a.pk,
        "user": member_user.pk,
        "role_name": "Stale Role",
        "permission_level": "viewer",
    }
    form_ou = DocumentAccessPermissionForm(data=data_ou, tenant=tenant_a)
    assert form_ou.is_valid(), form_ou.errors
    assert form_ou.cleaned_data["org_unit"] == org_unit_a
    assert form_ou.cleaned_data["user"] is None
    assert form_ou.cleaned_data["role_name"] == ""

    # Role grantee clears user and org_unit
    data_role = {
        "document": document.pk,
        "grantee_type": "role",
        "role_name": "Senior Partner",
        "user": member_user.pk,
        "org_unit": org_unit_a.pk,
        "permission_level": "editor",
    }
    form_role = DocumentAccessPermissionForm(data=data_role, tenant=tenant_a)
    assert form_role.is_valid(), form_role.errors
    assert form_role.cleaned_data["role_name"] == "Senior Partner"
    assert form_role.cleaned_data["user"] is None
    assert form_role.cleaned_data["org_unit"] is None

    # Tenant-wide grantee clears user, org_unit, and role_name
    data_tw = {
        "document": document.pk,
        "grantee_type": "tenant_wide",
        "user": member_user.pk,
        "org_unit": org_unit_a.pk,
        "role_name": "Stale Role",
        "permission_level": "viewer",
    }
    form_tw = DocumentAccessPermissionForm(data=data_tw, tenant=tenant_a)
    assert form_tw.is_valid(), form_tw.errors
    assert form_tw.cleaned_data["user"] is None
    assert form_tw.cleaned_data["org_unit"] is None
    assert form_tw.cleaned_data["role_name"] == ""


@pytest.mark.django_db
def test_security_access_control_document_permission_form_valid_date_range(
    tenant_a, member_user, document
):
    """Test valid_from and valid_until temporal validity range constraints."""
    now = timezone.now()
    tomorrow = now + timedelta(days=1)
    yesterday = now - timedelta(days=1)

    # Valid: valid_from <= valid_until
    data_valid = {
        "document": document.pk,
        "grantee_type": "user",
        "user": member_user.pk,
        "permission_level": "viewer",
        "valid_from": now.strftime("%Y-%m-%dT%H:%M"),
        "valid_until": tomorrow.strftime("%Y-%m-%dT%H:%M"),
    }
    form_valid = DocumentAccessPermissionForm(data=data_valid, tenant=tenant_a)
    assert form_valid.is_valid(), form_valid.errors

    # Invalid: valid_from > valid_until
    data_invalid = {
        "document": document.pk,
        "grantee_type": "user",
        "user": member_user.pk,
        "permission_level": "viewer",
        "valid_from": tomorrow.strftime("%Y-%m-%dT%H:%M"),
        "valid_until": yesterday.strftime("%Y-%m-%dT%H:%M"),
    }
    form_invalid = DocumentAccessPermissionForm(data=data_invalid, tenant=tenant_a)
    assert not form_invalid.is_valid()
    assert "valid_until" in form_invalid.errors
    assert "Valid Until date must be after Valid From date." in form_invalid.errors["valid_until"]


@pytest.mark.django_db
def test_security_access_control_document_permission_form_reject_foreign(
    tenant_a, tenant_b, admin_b, document
):
    """Security test: reject_foreign prevents binding foreign tenant's document, folder, user, or org_unit."""
    foreign_doc = _security_access_control_create_foreign_doc(tenant_b, admin_b)
    foreign_folder = _security_access_control_create_foreign_folder(tenant_b, admin_b)
    foreign_ou = _security_access_control_create_org_unit(tenant_b, name="Foreign OU")

    # 1. Foreign document rejected in form submission
    form_doc = DocumentAccessPermissionForm(
        tenant=tenant_a,
        data={
            "document": foreign_doc.pk,
            "grantee_type": "tenant_wide",
            "permission_level": "viewer",
        },
    )
    assert not form_doc.is_valid()
    assert "document" in form_doc.errors

    # Direct reject_foreign check on document
    cleaned = {"document": foreign_doc}
    reject_foreign(form_doc, cleaned, ["document"])
    assert "document" in form_doc.errors
    assert "That record belongs to another workspace." in form_doc.errors["document"]

    # 2. Foreign folder rejected
    form_folder = DocumentAccessPermissionForm(
        tenant=tenant_a,
        data={
            "folder": foreign_folder.pk,
            "grantee_type": "tenant_wide",
            "permission_level": "viewer",
        },
    )
    assert not form_folder.is_valid()
    assert "folder" in form_folder.errors

    cleaned = {"folder": foreign_folder}
    reject_foreign(form_folder, cleaned, ["folder"])
    assert "folder" in form_folder.errors
    assert "That record belongs to another workspace." in form_folder.errors["folder"]

    # 3. Foreign user rejected
    form_user = DocumentAccessPermissionForm(
        tenant=tenant_a,
        data={
            "document": document.pk,
            "grantee_type": "user",
            "user": admin_b.pk,
            "permission_level": "viewer",
        },
    )
    assert not form_user.is_valid()
    assert "user" in form_user.errors

    cleaned = {"user": admin_b}
    reject_foreign(form_user, cleaned, ["user"])
    assert "user" in form_user.errors
    assert "That record belongs to another workspace." in form_user.errors["user"]

    # 4. Foreign org_unit rejected
    form_ou = DocumentAccessPermissionForm(
        tenant=tenant_a,
        data={
            "document": document.pk,
            "grantee_type": "org_unit",
            "org_unit": foreign_ou.pk,
            "permission_level": "viewer",
        },
    )
    assert not form_ou.is_valid()
    assert "org_unit" in form_ou.errors

    cleaned = {"org_unit": foreign_ou}
    reject_foreign(form_ou, cleaned, ["org_unit"])
    assert "org_unit" in form_ou.errors
    assert "That record belongs to another workspace." in form_ou.errors["org_unit"]


# ============================================================================
# 2. WatermarkPolicyForm Tests
# ============================================================================

@pytest.mark.django_db
def test_security_access_control_watermark_policy_form_exclusions():
    """Verify system-managed and sensitive fields are excluded from WatermarkPolicyForm."""
    form = WatermarkPolicyForm()
    excluded = [
        "tenant",
        "number",
        "created_by",
        "created_at",
        "updated_at",
    ]
    for field in excluded:
        assert field not in form.fields, f"Security violation: {field} exposed in WatermarkPolicyForm"

    expected_fields = {
        "name",
        "slug",
        "description",
        "classification",
        "document_type",
        "department",
        "apply_to_all",
        "watermark_text",
        "secondary_text",
        "position",
        "opacity_percent",
        "font_size",
        "font_color",
        "rotation_angle",
        "show_classification_banner",
        "banner_position",
        "enforce_on_view",
        "enforce_on_download",
        "enforce_on_print",
        "priority",
        "is_active",
    }
    assert set(form.fields.keys()) == expected_fields


@pytest.mark.django_db
def test_security_access_control_watermark_policy_form_scoping(tenant_a, tenant_b, org_unit_a):
    """Test department field queryset is properly scoped to the current tenant."""
    foreign_dept = _security_access_control_create_org_unit(tenant_b, name="Globex Legal")
    form = WatermarkPolicyForm(tenant=tenant_a)

    assert org_unit_a in form.fields["department"].queryset
    assert foreign_dept not in form.fields["department"].queryset


@pytest.mark.django_db
def test_security_access_control_watermark_policy_form_valid_creation(tenant_a, admin_user, org_unit_a):
    """Test valid creation of a WatermarkPolicy via WatermarkPolicyForm."""
    data = {
        "name": "Strict Financial Watermark",
        "slug": "strict-financial-watermark",
        "description": "Applies to quarterly results and sensitive financial models",
        "classification": "confidential",
        "document_type": "all",
        "department": org_unit_a.pk,
        "apply_to_all": False,
        "watermark_text": "{{classification}} | {{user_name}} | {{timestamp}}",
        "secondary_text": "CONFIDENTIAL & PROPRIETARY",
        "position": "diagonal_center",
        "opacity_percent": 30,
        "font_size": 36,
        "font_color": "#DC2626",
        "rotation_angle": -45,
        "show_classification_banner": True,
        "banner_position": "top",
        "enforce_on_view": True,
        "enforce_on_download": True,
        "enforce_on_print": True,
        "priority": 10,
        "is_active": True,
    }
    form = WatermarkPolicyForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    policy = form.save(commit=False)
    policy.created_by = admin_user
    policy.save()

    assert policy.pk is not None
    assert policy.tenant == tenant_a
    assert policy.name == "Strict Financial Watermark"
    assert policy.classification == "confidential"
    assert policy.opacity_percent == 30
    assert policy.font_size == 36
    assert policy.rotation_angle == -45
    assert policy.department == org_unit_a


@pytest.mark.django_db
def test_security_access_control_watermark_policy_form_valid_editing(tenant_a, watermark_policy):
    """Test editing an existing WatermarkPolicy instance."""
    data = {
        "name": "Updated Confidential Policy",
        "slug": watermark_policy.slug,
        "classification": "restricted",
        "document_type": "sop",
        "watermark_text": "RESTRICTED - DO NOT COPY",
        "secondary_text": "STRICT CONTROL",
        "position": "center",
        "opacity_percent": 45,
        "font_size": 42,
        "font_color": "#EF4444",
        "rotation_angle": 0,
        "show_classification_banner": False,
        "banner_position": "both",
        "enforce_on_view": True,
        "enforce_on_download": True,
        "enforce_on_print": False,
        "priority": 5,
        "is_active": True,
    }
    form = WatermarkPolicyForm(data=data, instance=watermark_policy, tenant=tenant_a)
    assert form.is_valid(), form.errors

    updated = form.save()
    assert updated.pk == watermark_policy.pk
    assert updated.name == "Updated Confidential Policy"
    assert updated.classification == "restricted"
    assert updated.opacity_percent == 45
    assert updated.font_size == 42
    assert updated.rotation_angle == 0
    assert updated.enforce_on_print is False


@pytest.mark.django_db
def test_security_access_control_watermark_policy_form_opacity_boundaries(tenant_a):
    """Test opacity_percent boundary validation: strictly between 1% and 100%."""
    base_data = {
        "name": "Boundary Test Watermark",
        "classification": "internal",
        "document_type": "all",
        "watermark_text": "Boundary Check",
        "position": "diagonal_center",
        "banner_position": "top",
        "font_size": 24,
        "font_color": "#94a3b8",
        "rotation_angle": -45,
        "priority": 50,
        "is_active": True,
    }

    # Opacity = 0 (Invalid: below 1)
    data_zero = {**base_data, "opacity_percent": 0}
    form_zero = WatermarkPolicyForm(data=data_zero, tenant=tenant_a)
    assert not form_zero.is_valid()
    assert "opacity_percent" in form_zero.errors
    assert "Opacity must be between 1% and 100%." in form_zero.errors["opacity_percent"]

    # Opacity = 101 (Invalid: above 100)
    data_over = {**base_data, "opacity_percent": 101}
    form_over = WatermarkPolicyForm(data=data_over, tenant=tenant_a)
    assert not form_over.is_valid()
    assert "opacity_percent" in form_over.errors
    assert "Opacity must be between 1% and 100%." in form_over.errors["opacity_percent"]

    # Opacity = 1 (Valid lower boundary)
    data_one = {**base_data, "opacity_percent": 1}
    form_one = WatermarkPolicyForm(data=data_one, tenant=tenant_a)
    assert form_one.is_valid(), form_one.errors

    # Opacity = 100 (Valid upper boundary)
    data_hundred = {**base_data, "opacity_percent": 100}
    form_hundred = WatermarkPolicyForm(data=data_hundred, tenant=tenant_a)
    assert form_hundred.is_valid(), form_hundred.errors


@pytest.mark.django_db
def test_security_access_control_watermark_policy_form_font_size_and_rotation(tenant_a):
    """Test font_size and rotation_angle acceptance across positive and negative values."""
    data = {
        "name": "Angle & Size Policy",
        "classification": "confidential",
        "document_type": "all",
        "watermark_text": "Angle Check",
        "position": "tiled_grid",
        "banner_position": "top",
        "opacity_percent": 50,
        "font_size": 72,
        "font_color": "#475569",
        "rotation_angle": 90,
        "priority": 20,
        "is_active": True,
    }
    form = WatermarkPolicyForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["font_size"] == 72
    assert form.cleaned_data["rotation_angle"] == 90


@pytest.mark.django_db
def test_security_access_control_watermark_policy_form_reject_foreign_department(
    tenant_a, tenant_b
):
    """Security test: reject_foreign rejects department belonging to a foreign tenant."""
    foreign_dept = _security_access_control_create_org_unit(tenant_b, name="Foreign Department")

    form = WatermarkPolicyForm(
        tenant=tenant_a,
        data={
            "name": "Cross Tenant Watermark Attack",
            "department": foreign_dept.pk,
            "classification": "internal",
            "document_type": "all",
            "watermark_text": "Hacked",
            "banner_position": "top",
            "opacity_percent": 20,
            "font_size": 24,
            "rotation_angle": 0,
            "priority": 1,
        },
    )
    assert not form.is_valid()
    assert "department" in form.errors

    # Direct reject_foreign invocation
    cleaned = {"department": foreign_dept}
    reject_foreign(form, cleaned, ["department"])
    assert "department" in form.errors
    assert "That record belongs to another workspace." in form.errors["department"]


# ============================================================================
# 3. DocumentDrmPolicyForm Tests
# ============================================================================

@pytest.mark.django_db
def test_security_access_control_drm_policy_form_exclusions():
    """Verify system-managed and sensitive revocation fields are excluded from DocumentDrmPolicyForm."""
    form = DocumentDrmPolicyForm()
    excluded = [
        "tenant",
        "number",
        "created_by",
        "is_revoked",
        "revoked_at",
        "revocation_reason",
        "created_at",
        "updated_at",
    ]
    for field in excluded:
        assert field not in form.fields, f"Security violation: {field} exposed in DocumentDrmPolicyForm"

    expected_fields = {
        "name",
        "slug",
        "description",
        "classification",
        "document_type",
        "target_document",
        "target_folder",
        "allow_download",
        "allow_print",
        "allow_copy_paste",
        "screen_shield_enabled",
        "secure_viewer_required",
        "require_watermark",
        "max_offline_hours",
        "expiry_days",
        "ip_allowlist",
        "geo_fencing_countries",
        "encryption_standard",
        "is_active",
    }
    assert set(form.fields.keys()) == expected_fields


@pytest.mark.django_db
def test_security_access_control_drm_policy_form_scoping(
    tenant_a, tenant_b, admin_b, document, document_folder
):
    """Test target_document and target_folder querysets are scoped to current tenant."""
    foreign_doc = _security_access_control_create_foreign_doc(tenant_b, admin_b)
    foreign_folder = _security_access_control_create_foreign_folder(tenant_b, admin_b)

    form = DocumentDrmPolicyForm(tenant=tenant_a)

    assert document in form.fields["target_document"].queryset
    assert foreign_doc not in form.fields["target_document"].queryset

    assert document_folder in form.fields["target_folder"].queryset
    assert foreign_folder not in form.fields["target_folder"].queryset


@pytest.mark.django_db
def test_security_access_control_drm_policy_form_valid_creation(
    tenant_a, admin_user, document
):
    """Test valid creation of a DocumentDrmPolicy with document target and DRM parameters."""
    data = {
        "name": "Restricted Board Documents DRM",
        "slug": "restricted-board-documents-drm",
        "description": "Strict viewing and anti-copy policies for board packs",
        "classification": "restricted",
        "document_type": "all",
        "target_document": document.pk,
        "allow_download": False,
        "allow_print": False,
        "allow_copy_paste": False,
        "screen_shield_enabled": True,
        "secure_viewer_required": True,
        "require_watermark": True,
        "max_offline_hours": 0,
        "expiry_days": 14,
        "ip_allowlist": "10.0.0.0/16\n192.168.1.100",
        "geo_fencing_countries": "US, CA, GB",
        "encryption_standard": "AES_256_GCM",
        "is_active": True,
    }
    form = DocumentDrmPolicyForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    policy = form.save(commit=False)
    policy.created_by = admin_user
    policy.save()

    assert policy.pk is not None
    assert policy.tenant == tenant_a
    assert policy.target_document == document
    assert policy.target_folder is None
    assert policy.allow_download is False
    assert policy.screen_shield_enabled is True
    assert policy.max_offline_hours == 0
    assert policy.expiry_days == 14
    assert policy.encryption_standard == "AES_256_GCM"


@pytest.mark.django_db
def test_security_access_control_drm_policy_form_perimeter_parameters(
    tenant_a, admin_user, document_folder
):
    """Test perimeter parameters: expiry_days, max_offline_hours, ip_allowlist, and geo-fencing."""
    data = {
        "name": "Vendor Audit DRM Policy",
        "classification": "confidential",
        "document_type": "contract",
        "target_folder": document_folder.pk,
        "allow_download": True,
        "allow_print": False,
        "allow_copy_paste": False,
        "screen_shield_enabled": True,
        "secure_viewer_required": False,
        "require_watermark": True,
        "max_offline_hours": 72,
        "expiry_days": 180,
        "ip_allowlist": "172.16.0.0/12, 192.168.10.5",
        "geo_fencing_countries": "DE, FR, NL",
        "encryption_standard": "CHACHA20_POLY1305",
        "is_active": True,
    }
    form = DocumentDrmPolicyForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    policy = form.save(commit=False)
    policy.created_by = admin_user
    policy.save()

    assert policy.target_folder == document_folder
    assert policy.max_offline_hours == 72
    assert policy.expiry_days == 180
    assert "172.16.0.0/12" in policy.ip_allowlist
    assert policy.geo_fencing_countries == "DE, FR, NL"


@pytest.mark.django_db
def test_security_access_control_drm_policy_form_editing(tenant_a, drm_policy):
    """Test editing an existing DocumentDrmPolicy instance."""
    data = {
        "name": "Updated Executive Shield",
        "slug": drm_policy.slug,
        "classification": "restricted",
        "document_type": "all",
        "allow_download": True,
        "allow_print": True,
        "allow_copy_paste": False,
        "screen_shield_enabled": False,
        "secure_viewer_required": True,
        "require_watermark": False,
        "max_offline_hours": 12,
        "expiry_days": 45,
        "encryption_standard": "AES_256_CBC",
        "is_active": True,
    }
    form = DocumentDrmPolicyForm(data=data, instance=drm_policy, tenant=tenant_a)
    assert form.is_valid(), form.errors

    updated = form.save()
    assert updated.pk == drm_policy.pk
    assert updated.name == "Updated Executive Shield"
    assert updated.allow_download is True
    assert updated.allow_print is True
    assert updated.max_offline_hours == 12
    assert updated.expiry_days == 45
    assert updated.encryption_standard == "AES_256_CBC"


@pytest.mark.django_db
def test_security_access_control_drm_policy_form_reject_foreign(
    tenant_a, tenant_b, admin_b
):
    """Security test: reject_foreign prevents binding foreign target_document and target_folder."""
    foreign_doc = _security_access_control_create_foreign_doc(tenant_b, admin_b)
    foreign_folder = _security_access_control_create_foreign_folder(tenant_b, admin_b)

    # 1. Foreign target_document
    form_doc = DocumentDrmPolicyForm(
        tenant=tenant_a,
        data={
            "name": "Attack Target Doc",
            "classification": "confidential",
            "document_type": "all",
            "target_document": foreign_doc.pk,
            "expiry_days": 30,
            "max_offline_hours": 0,
            "encryption_standard": "AES_256_GCM",
        },
    )
    assert not form_doc.is_valid()
    assert "target_document" in form_doc.errors

    cleaned = {"target_document": foreign_doc}
    reject_foreign(form_doc, cleaned, ["target_document"])
    assert "target_document" in form_doc.errors
    assert "That record belongs to another workspace." in form_doc.errors["target_document"]

    # 2. Foreign target_folder
    form_folder = DocumentDrmPolicyForm(
        tenant=tenant_a,
        data={
            "name": "Attack Target Folder",
            "classification": "confidential",
            "document_type": "all",
            "target_folder": foreign_folder.pk,
            "expiry_days": 30,
            "max_offline_hours": 0,
            "encryption_standard": "AES_256_GCM",
        },
    )
    assert not form_folder.is_valid()
    assert "target_folder" in form_folder.errors

    cleaned = {"target_folder": foreign_folder}
    reject_foreign(form_folder, cleaned, ["target_folder"])
    assert "target_folder" in form_folder.errors
    assert "That record belongs to another workspace." in form_folder.errors["target_folder"]


# ============================================================================
# 4. DlpPolicyForm Tests
# ============================================================================

@pytest.mark.django_db
def test_security_access_control_dlp_policy_form_exclusions():
    """Verify system-managed and telemetry fields are excluded from DlpPolicyForm."""
    form = DlpPolicyForm()
    excluded = [
        "tenant",
        "number",
        "created_by",
        "incident_count",
        "last_triggered_at",
        "created_at",
        "updated_at",
    ]
    for field in excluded:
        assert field not in form.fields, f"Security violation: {field} exposed in DlpPolicyForm"

    expected_fields = {
        "name",
        "slug",
        "description",
        "rule_type",
        "built_in_pattern",
        "custom_regex",
        "keywords_raw",
        "match_threshold",
        "action",
        "severity",
        "notify_security_officer",
        "notification_email",
        "apply_to_all_types",
        "is_active",
    }
    assert set(form.fields.keys()) == expected_fields


@pytest.mark.django_db
def test_security_access_control_dlp_policy_form_valid_built_in_pattern(tenant_a, admin_user):
    """Test valid creation of DlpPolicy using built-in pattern (e.g. PCI credit cards)."""
    data = {
        "name": "Global Payment Card Guard",
        "slug": "global-payment-card-guard",
        "description": "Detects unmasked Mastercard and Visa credit card PANs",
        "rule_type": "built_in_pattern",
        "built_in_pattern": "credit_card_pci",
        "match_threshold": 1,
        "action": "block_save",
        "severity": "critical",
        "notify_security_officer": True,
        "notification_email": "soc-leads@acme.com",
        "apply_to_all_types": True,
        "is_active": True,
    }
    form = DlpPolicyForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    policy = form.save(commit=False)
    policy.created_by = admin_user
    policy.save()

    assert policy.pk is not None
    assert policy.tenant == tenant_a
    assert policy.rule_type == "built_in_pattern"
    assert policy.built_in_pattern == "credit_card_pci"
    assert policy.action == "block_save"
    assert policy.severity == "critical"
    assert policy.notification_email == "soc-leads@acme.com"


@pytest.mark.django_db
def test_security_access_control_dlp_policy_form_valid_custom_regex(tenant_a, admin_user):
    """Test valid creation of DlpPolicy using a safe custom regular expression."""
    data = {
        "name": "Corporate Project Code Regex",
        "rule_type": "custom_regex",
        "built_in_pattern": "none",
        "custom_regex": r"\bPRJ-[0-9]{4}-[A-Z]{3}\b",
        "match_threshold": 2,
        "action": "warn_author",
        "severity": "high",
        "notify_security_officer": False,
        "apply_to_all_types": True,
        "is_active": True,
    }
    form = DlpPolicyForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    policy = form.save(commit=False)
    policy.created_by = admin_user
    policy.save()

    assert policy.rule_type == "custom_regex"
    assert policy.custom_regex == r"\bPRJ-[0-9]{4}-[A-Z]{3}\b"


@pytest.mark.django_db
def test_security_access_control_dlp_policy_form_valid_keywords_parsing(tenant_a, admin_user):
    """Test sensitive keywords parsing from keywords_raw into JSON list on form.save()."""
    data = {
        "name": "M&A Keywords Guard",
        "rule_type": "sensitive_keywords",
        "built_in_pattern": "none",
        "keywords_raw": "Project Apollo, Hostile Takeover, Board Resolution, Q3 Margin Leak",
        "match_threshold": 1,
        "action": "quarantine",
        "severity": "critical",
        "apply_to_all_types": True,
        "is_active": True,
    }
    form = DlpPolicyForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    policy = form.save(commit=False)
    policy.created_by = admin_user
    policy.save()

    assert policy.rule_type == "sensitive_keywords"
    assert policy.sensitive_keywords == [
        "Project Apollo",
        "Hostile Takeover",
        "Board Resolution",
        "Q3 Margin Leak",
    ]


@pytest.mark.django_db
def test_security_access_control_dlp_policy_form_redos_defense_nested_quantifiers(tenant_a):
    """Security test: clean_custom_regex catches and rejects ReDoS nested quantifiers and overlapping repetitions."""
    base_data = {
        "name": "ReDoS Vulnerability Test",
        "rule_type": "custom_regex",
        "built_in_pattern": "none",
        "match_threshold": 1,
        "action": "warn_author",
        "severity": "medium",
        "is_active": True,
    }

    # Malicious patterns known to trigger exponential catastrophic backtracking
    malicious_patterns = [
        r"(a+)+",
        r"(x+)*",
        r"(x*)*",
        r"(x+{2,})",
        r"(a|b+)+",
        r"[a-z]++",
    ]

    for pattern in malicious_patterns:
        test_data = {**base_data, "custom_regex": pattern}
        form = DlpPolicyForm(data=test_data, tenant=tenant_a)
        assert not form.is_valid(), f"ReDoS pattern '{pattern}' was not rejected!"
        assert "custom_regex" in form.errors
        assert (
            "Potential ReDoS (regular expression denial of service) pattern detected"
            in form.errors["custom_regex"][0]
        )


@pytest.mark.django_db
def test_security_access_control_dlp_policy_form_regex_length_guard(tenant_a):
    """Security test: custom_regex patterns exceeding 250 characters are rejected."""
    long_pattern = r"^" + ("a" * 250) + r"$"
    assert len(long_pattern) > 250

    data = {
        "name": "Excessive Regex Length Policy",
        "rule_type": "custom_regex",
        "built_in_pattern": "none",
        "custom_regex": long_pattern,
        "match_threshold": 1,
        "action": "warn_author",
        "severity": "low",
        "is_active": True,
    }
    form = DlpPolicyForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "custom_regex" in form.errors
    assert "Custom regular expression pattern is too long" in form.errors["custom_regex"][0]


@pytest.mark.django_db
def test_security_access_control_dlp_policy_form_invalid_regex_syntax(tenant_a):
    """Test that malformed Python regular expression syntax raises a ValidationError."""
    data = {
        "name": "Malformed Syntax Regex",
        "rule_type": "custom_regex",
        "built_in_pattern": "none",
        "custom_regex": r"[unclosed-bracket-\d+",
        "match_threshold": 1,
        "action": "warn_author",
        "severity": "low",
        "is_active": True,
    }
    form = DlpPolicyForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "custom_regex" in form.errors
    assert "Invalid Python regular expression" in form.errors["custom_regex"][0]


@pytest.mark.django_db
def test_security_access_control_dlp_policy_form_rule_type_validation_clean(tenant_a):
    """Validation test: clean() ensures required parameters for each rule_type are provided."""
    # 1. built_in_pattern without selected pattern
    data_builtin = {
        "name": "Empty Builtin Pattern",
        "rule_type": "built_in_pattern",
        "built_in_pattern": "none",
        "match_threshold": 1,
        "action": "warn_author",
        "severity": "low",
        "is_active": True,
    }
    form_builtin = DlpPolicyForm(data=data_builtin, tenant=tenant_a)
    assert not form_builtin.is_valid()
    assert "built_in_pattern" in form_builtin.errors
    assert "Please select a built-in pattern type." in form_builtin.errors["built_in_pattern"]

    # 2. custom_regex without custom_regex
    data_regex = {
        "name": "Empty Custom Regex",
        "rule_type": "custom_regex",
        "built_in_pattern": "none",
        "custom_regex": "",
        "match_threshold": 1,
        "action": "warn_author",
        "severity": "low",
        "is_active": True,
    }
    form_regex = DlpPolicyForm(data=data_regex, tenant=tenant_a)
    assert not form_regex.is_valid()
    assert "custom_regex" in form_regex.errors
    assert "Regular expression pattern is required for custom regex rules." in form_regex.errors["custom_regex"]

    # 3. sensitive_keywords without keywords
    data_keywords = {
        "name": "Empty Keywords",
        "rule_type": "sensitive_keywords",
        "built_in_pattern": "none",
        "keywords_raw": "   ",
        "match_threshold": 1,
        "action": "warn_author",
        "severity": "low",
        "is_active": True,
    }
    form_keywords = DlpPolicyForm(data=data_keywords, tenant=tenant_a)
    assert not form_keywords.is_valid()
    assert "keywords_raw" in form_keywords.errors
    assert "Please provide at least one sensitive keyword." in form_keywords.errors["keywords_raw"]


@pytest.mark.django_db
def test_security_access_control_dlp_policy_form_keywords_raw_initial_population(
    tenant_a, admin_user
):
    """Test that editing a DlpPolicy instance with existing sensitive_keywords populates keywords_raw initial."""
    policy = DlpPolicy.objects.create(
        tenant=tenant_a,
        name="Existing Keywords Policy",
        rule_type="sensitive_keywords",
        sensitive_keywords=["Top Secret", "Merger Proposal", "Executive Bonus"],
        action="quarantine",
        severity="high",
        created_by=admin_user,
    )

    form = DlpPolicyForm(instance=policy, tenant=tenant_a)
    assert form.fields["keywords_raw"].initial == "Top Secret, Merger Proposal, Executive Bonus"


# ============================================================================
# 5. DlpIncidentResolveForm Tests
# ============================================================================

@pytest.mark.django_db
def test_security_access_control_dlp_incident_resolve_form_exclusions():
    """Verify incident telemetry fields are excluded from DlpIncidentResolveForm."""
    form = DlpIncidentResolveForm()
    excluded = [
        "tenant",
        "number",
        "policy",
        "document",
        "triggered_by",
        "action_taken",
        "severity",
        "matches_detected_count",
        "snippet_redacted",
        "ip_address",
        "created_at",
        "updated_at",
    ]
    for field in excluded:
        assert field not in form.fields, f"Security violation: {field} exposed in DlpIncidentResolveForm"

    expected_fields = {"resolution_status", "resolution_notes"}
    assert set(form.fields.keys()) == expected_fields


@pytest.mark.django_db
def test_security_access_control_dlp_incident_resolve_form_valid_resolutions(
    tenant_a, dlp_incident
):
    """Test valid resolution status updates: resolved_justified, false_positive, dismissed."""
    resolution_scenarios = [
        (
            "resolved_justified",
            "Customer credit card number provided on authorized paper transaction slip.",
        ),
        (
            "false_positive",
            "Test number pattern in developer documentation sandbox, not real card data.",
        ),
        (
            "dismissed",
            "Duplicate incident triggered during concurrent document autosave sequence.",
        ),
    ]

    for status_choice, notes in resolution_scenarios:
        data = {
            "resolution_status": status_choice,
            "resolution_notes": notes,
        }
        form = DlpIncidentResolveForm(data=data, instance=dlp_incident, tenant=tenant_a)
        assert form.is_valid(), form.errors

        updated_incident = form.save()
        assert updated_incident.resolution_status == status_choice
        assert updated_incident.resolution_notes == notes


@pytest.mark.django_db
def test_security_access_control_dlp_incident_resolve_form_notes_required(
    tenant_a, dlp_incident
):
    """Validation test: resolution_notes is strictly required upon incident triage."""
    # Empty string
    data_empty = {
        "resolution_status": "false_positive",
        "resolution_notes": "",
    }
    form_empty = DlpIncidentResolveForm(data=data_empty, instance=dlp_incident, tenant=tenant_a)
    assert not form_empty.is_valid()
    assert "resolution_notes" in form_empty.errors

    # Whitespace only
    data_ws = {
        "resolution_status": "dismissed",
        "resolution_notes": "    ",
    }
    form_ws = DlpIncidentResolveForm(data=data_ws, instance=dlp_incident, tenant=tenant_a)
    assert not form_ws.is_valid()
    assert "resolution_notes" in form_ws.errors
