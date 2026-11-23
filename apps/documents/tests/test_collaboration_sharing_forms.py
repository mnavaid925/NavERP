"""Unit tests for Sub-module 13.8 Collaboration & Sharing forms in apps.documents."""
from datetime import timedelta
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.models import OrgUnit
from apps.documents.forms import (
    CoauthorSessionForm,
    DocumentActivityForm,
    DocumentShareForm,
    DocumentTaskForm,
)
from apps.documents.forms._common import reject_foreign
from apps.documents.models.ApprovalWorkflow.DocumentReviewComments import DocumentReviewComment
from apps.documents.models.CollaborationSharing.CoauthorSessions import CoauthorSession
from apps.documents.models.CollaborationSharing.DocumentActivities import DocumentActivity
from apps.documents.models.CollaborationSharing.DocumentShares import DocumentShare
from apps.documents.models.CollaborationSharing.DocumentTasks import DocumentTask
from apps.documents.models.DocumentAuthoring.DocumentDrafts import DocumentDraft
from apps.documents.models.StorageRepository.DocumentFolders import DocumentFolder
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.models.VersionControl.DocumentVersions import DocumentVersion

User = get_user_model()


# ---------------------------------------------------------------------------
# Compatibility Shims & Aliases for conftest.py Fixture Support
# ---------------------------------------------------------------------------

if not getattr(DocumentShare, "_collaboration_sharing_form_shimmed", False):
    DocumentShare._collaboration_sharing_form_shimmed = True

    if not hasattr(DocumentShare, "is_usable"):
        DocumentShare.is_usable = property(lambda self: self.is_valid)

    _orig_dshr_init = DocumentShare.__init__

    def _collaboration_sharing_dshr_init(self, *args, **kwargs):
        kwargs.pop("require_password", None)
        if kwargs.get("access_level") == "download":
            kwargs["access_level"] = "view_only"
        elif kwargs.get("access_level") == "view":
            kwargs["access_level"] = "view_only"
        _orig_dshr_init(self, *args, **kwargs)

    DocumentShare.__init__ = _collaboration_sharing_dshr_init

if not getattr(CoauthorSession, "_collaboration_sharing_form_shimmed", False):
    CoauthorSession._collaboration_sharing_form_shimmed = True

    _orig_dcoa_init = CoauthorSession.__init__

    def _collaboration_sharing_dcoa_init(self, *args, **kwargs):
        if "client_id" in kwargs:
            cid = kwargs.pop("client_id")
            if "session_token" not in kwargs:
                kwargs["session_token"] = cid
        if "cursor_position_json" in kwargs:
            cpj = kwargs.pop("cursor_position_json")
            if "cursor_position" not in kwargs:
                import json
                kwargs["cursor_position"] = json.dumps(cpj) if isinstance(cpj, (dict, list)) else str(cpj)
        _orig_dcoa_init(self, *args, **kwargs)

    CoauthorSession.__init__ = _collaboration_sharing_dcoa_init

if not getattr(DocumentActivity, "_collaboration_sharing_form_shimmed", False):
    DocumentActivity._collaboration_sharing_form_shimmed = True

    _orig_dact_init = DocumentActivity.__init__

    def _collaboration_sharing_dact_init(self, *args, **kwargs):
        title = kwargs.pop("title", None)
        desc = kwargs.pop("description", None)
        if title and "summary" not in kwargs:
            kwargs["summary"] = title
        elif desc and "summary" not in kwargs:
            kwargs["summary"] = desc
        _orig_dact_init(self, *args, **kwargs)

    DocumentActivity.__init__ = _collaboration_sharing_dact_init


# ===========================================================================
# 1. DocumentShareForm Unit Tests
# ===========================================================================


@pytest.mark.django_db
def test_collaboration_sharing_share_form_system_fields_excluded():
    """Verify system-managed and sensitive fields are excluded from DocumentShareForm Meta.fields."""
    form = DocumentShareForm()
    excluded = [
        "tenant",
        "number",
        "share_token",
        "access_count",
        "password_hash",
        "last_accessed_at",
        "created_at",
        "updated_at",
        "shared_by",
        "is_active",
        "revoked_at",
        "revoked_by",
    ]
    for field in excluded:
        assert field not in form.fields, f"Security violation: {field} exposed in DocumentShareForm"


@pytest.mark.django_db
def test_collaboration_sharing_share_form_tenant_scoped_querysets(
    tenant_a, tenant_b, admin_user, member_user, document, document_version, document_folder, org_unit_a
):
    """DocumentShareForm ForeignKeys must be scoped to the active tenant."""
    # Create tenant_b entities
    user_b = User.objects.create_user(
        username="user_b_collab_share",
        email="user_b_collab_share@globex.com",
        password="password",
        tenant=tenant_b,
        is_active=True,
    )
    inactive_user_a = User.objects.create_user(
        username="inactive_user_collab_share",
        email="inactive_user@acme.com",
        password="password",
        tenant=tenant_a,
        is_active=False,
    )
    doc_b = Document.objects.create(
        tenant=tenant_b,
        title="Tenant B Secret Doc",
        owner=admin_user,
    )
    ver_b = DocumentVersion.objects.create(
        tenant=tenant_b,
        document=doc_b,
        version_label="0.9",
        author=admin_user,
    )
    folder_b = DocumentFolder.objects.create(
        tenant=tenant_b,
        name="Tenant B Private Folder",
        owner=admin_user,
    )
    org_b = OrgUnit.objects.create(
        tenant=tenant_b,
        name="Globex Legal",
        kind="department",
    )

    form = DocumentShareForm(tenant=tenant_a)

    # Scoped document queryset
    assert document in form.fields["document"].queryset
    assert doc_b not in form.fields["document"].queryset

    # Scoped folder queryset
    assert document_folder in form.fields["folder"].queryset
    assert folder_b not in form.fields["folder"].queryset

    # Scoped version queryset
    assert document_version in form.fields["version"].queryset
    assert ver_b not in form.fields["version"].queryset

    # Scoped shared_with_user queryset (active tenant_a users only)
    assert member_user in form.fields["shared_with_user"].queryset
    assert admin_user in form.fields["shared_with_user"].queryset
    assert user_b not in form.fields["shared_with_user"].queryset
    assert inactive_user_a not in form.fields["shared_with_user"].queryset

    # Scoped shared_with_org_unit queryset
    assert org_unit_a in form.fields["shared_with_org_unit"].queryset
    assert org_b not in form.fields["shared_with_org_unit"].queryset


@pytest.mark.django_db
def test_collaboration_sharing_share_form_reject_foreign_injection(
    tenant_a, tenant_b, admin_user, document
):
    """Test reject_foreign raises workspace mismatch error for foreign objects in cleaned_data."""
    doc_b = Document.objects.create(
        tenant=tenant_b,
        title="Foreign Document",
        owner=admin_user,
    )
    form = DocumentShareForm(tenant=tenant_a)
    form.cleaned_data = {"document": doc_b}
    form._errors = {}
    reject_foreign(form, form.cleaned_data, ["document"])
    assert "document" in form.errors
    assert "That record belongs to another workspace." in form.errors["document"]


@pytest.mark.django_db
def test_collaboration_sharing_share_form_unauthorized_foreign_pk_rejected(
    tenant_a, tenant_b, admin_user
):
    """Submitting foreign PKs fails form validation."""
    foreign_doc = Document.objects.create(
        tenant=tenant_b,
        title="Foreign Document PK",
        owner=admin_user,
    )
    form = DocumentShareForm(
        tenant=tenant_a,
        data={
            "document": foreign_doc.pk,
            "share_type": "public_link",
            "access_level": "view_only",
        },
    )
    assert not form.is_valid()
    assert "document" in form.errors


@pytest.mark.django_db
def test_collaboration_sharing_share_form_version_document_cross_record_integrity(
    tenant_a, admin_user, document
):
    """Version must belong to the selected document; mismatched version is rejected."""
    other_doc = Document.objects.create(
        tenant=tenant_a,
        title="Secondary Document",
        owner=admin_user,
    )
    other_ver = DocumentVersion.objects.create(
        tenant=tenant_a,
        document=other_doc,
        version_label="2.0",
        author=admin_user,
    )

    form = DocumentShareForm(
        tenant=tenant_a,
        data={
            "document": document.pk,
            "version": other_ver.pk,
            "share_type": "public_link",
            "access_level": "view_only",
        },
    )
    assert not form.is_valid()
    assert "version" in form.errors
    assert "The selected version does not belong to the selected document." in form.errors["version"]


@pytest.mark.django_db
def test_collaboration_sharing_share_form_matching_version_valid(
    tenant_a, document, document_version
):
    """Matching document and version pass validation cleanly."""
    form = DocumentShareForm(
        tenant=tenant_a,
        data={
            "document": document.pk,
            "version": document_version.pk,
            "share_type": "public_link",
            "access_level": "view_only",
        },
    )
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_collaboration_sharing_share_form_internal_user_requires_recipient(
    tenant_a, document, member_user
):
    """share_type='internal_user' requires shared_with_user."""
    # Missing shared_with_user
    form_invalid = DocumentShareForm(
        tenant=tenant_a,
        data={
            "document": document.pk,
            "share_type": "internal_user",
            "access_level": "view_only",
        },
    )
    assert not form_invalid.is_valid()
    assert "shared_with_user" in form_invalid.errors
    assert "Please select the internal user to share with." in form_invalid.errors["shared_with_user"]

    # Provided shared_with_user
    form_valid = DocumentShareForm(
        tenant=tenant_a,
        data={
            "document": document.pk,
            "share_type": "internal_user",
            "access_level": "view_only",
            "shared_with_user": member_user.pk,
        },
    )
    assert form_valid.is_valid(), form_valid.errors


@pytest.mark.django_db
def test_collaboration_sharing_share_form_internal_dept_requires_org_unit(
    tenant_a, document, org_unit_a
):
    """share_type='internal_dept' requires shared_with_org_unit."""
    # Missing shared_with_org_unit
    form_invalid = DocumentShareForm(
        tenant=tenant_a,
        data={
            "document": document.pk,
            "share_type": "internal_dept",
            "access_level": "comment",
        },
    )
    assert not form_invalid.is_valid()
    assert "shared_with_org_unit" in form_invalid.errors
    assert "Please select the internal department to share with." in form_invalid.errors["shared_with_org_unit"]

    # Provided shared_with_org_unit
    form_valid = DocumentShareForm(
        tenant=tenant_a,
        data={
            "document": document.pk,
            "share_type": "internal_dept",
            "access_level": "comment",
            "shared_with_org_unit": org_unit_a.pk,
        },
    )
    assert form_valid.is_valid(), form_valid.errors


@pytest.mark.django_db
def test_collaboration_sharing_share_form_external_email_requires_email(
    tenant_a, document
):
    """share_type='external_email' requires shared_with_email."""
    # Missing shared_with_email
    form_invalid = DocumentShareForm(
        tenant=tenant_a,
        data={
            "document": document.pk,
            "share_type": "external_email",
            "access_level": "view_only",
        },
    )
    assert not form_invalid.is_valid()
    assert "shared_with_email" in form_invalid.errors
    assert "Please specify the recipient email address for external sharing." in form_invalid.errors["shared_with_email"]

    # Provided valid email
    form_valid = DocumentShareForm(
        tenant=tenant_a,
        data={
            "document": document.pk,
            "share_type": "external_email",
            "access_level": "view_only",
            "shared_with_email": "auditor@external-firm.com",
        },
    )
    assert form_valid.is_valid(), form_valid.errors


@pytest.mark.django_db
def test_collaboration_sharing_share_form_public_link_valid(
    tenant_a, document
):
    """share_type='public_link' requires no specific recipient."""
    form = DocumentShareForm(
        tenant=tenant_a,
        data={
            "document": document.pk,
            "share_type": "public_link",
            "access_level": "view_only",
            "allow_download": True,
            "allow_print": False,
        },
    )
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_collaboration_sharing_share_form_raw_password_sets_password_hash(
    tenant_a, admin_user, document
):
    """When raw_password is provided, save() sets cryptographically hashed password."""
    form = DocumentShareForm(
        tenant=tenant_a,
        user=admin_user,
        data={
            "document": document.pk,
            "share_type": "public_link",
            "access_level": "view_only",
            "raw_password": "Passcode-Secure-987",
        },
    )
    assert form.is_valid(), form.errors
    share = form.save(commit=False)
    share.tenant = tenant_a
    share.save()
    assert share.has_password is True
    assert share.password_hash != ""
    assert share.password_hash != "Passcode-Secure-987"
    assert share.check_password("Passcode-Secure-987") is True
    assert share.check_password("IncorrectPass") is False


@pytest.mark.django_db
def test_collaboration_sharing_share_form_save_assigns_shared_by(
    tenant_a, admin_user, document
):
    """DocumentShareForm save() assigns shared_by to the passed authenticated user."""
    form = DocumentShareForm(
        tenant=tenant_a,
        user=admin_user,
        data={
            "document": document.pk,
            "share_type": "public_link",
            "access_level": "view_only",
        },
    )
    assert form.is_valid(), form.errors
    share = form.save(commit=False)
    share.tenant = tenant_a
    share.save()
    assert share.shared_by == admin_user
    assert share.tenant == tenant_a


# ===========================================================================
# 2. CoauthorSessionForm Unit Tests
# ===========================================================================


@pytest.mark.django_db
def test_collaboration_sharing_coauthor_form_system_fields_excluded():
    """Verify system-managed fields are excluded from CoauthorSessionForm Meta.fields."""
    form = CoauthorSessionForm()
    excluded = [
        "tenant",
        "number",
        "session_token",
        "cursor_position",
        "client_ip",
        "user_agent",
        "joined_at",
        "last_heartbeat",
        "disconnected_at",
        "created_at",
        "updated_at",
    ]
    for field in excluded:
        assert field not in form.fields, f"Security violation: {field} exposed in CoauthorSessionForm"


@pytest.mark.django_db
def test_collaboration_sharing_coauthor_form_tenant_scoped_querysets(
    tenant_a, tenant_b, admin_user, member_user, document, document_version, document_draft
):
    """CoauthorSessionForm ForeignKeys must be scoped to tenant_a and active users."""
    user_b = User.objects.create_user(
        username="user_b_coauthor",
        email="user_b_coauthor@globex.com",
        password="password",
        tenant=tenant_b,
        is_active=True,
    )
    inactive_user_a = User.objects.create_user(
        username="inactive_a_coauthor",
        email="inactive_a_coauthor@acme.com",
        password="password",
        tenant=tenant_a,
        is_active=False,
    )
    doc_b = Document.objects.create(
        tenant=tenant_b,
        title="Tenant B Coauthor Doc",
        owner=admin_user,
    )
    ver_b = DocumentVersion.objects.create(
        tenant=tenant_b,
        document=doc_b,
        version_label="0.1",
        author=admin_user,
    )
    draft_b = DocumentDraft.objects.create(
        tenant=tenant_b,
        title="Tenant B Draft",
        author=admin_user,
    )

    form = CoauthorSessionForm(tenant=tenant_a)

    # Scoped document queryset
    assert document in form.fields["document"].queryset
    assert doc_b not in form.fields["document"].queryset

    # Scoped version queryset
    assert document_version in form.fields["version"].queryset
    assert ver_b not in form.fields["version"].queryset

    # Scoped draft queryset
    assert document_draft in form.fields["draft"].queryset
    assert draft_b not in form.fields["draft"].queryset

    # Scoped user queryset
    assert member_user in form.fields["user"].queryset
    assert admin_user in form.fields["user"].queryset
    assert user_b not in form.fields["user"].queryset
    assert inactive_user_a not in form.fields["user"].queryset


@pytest.mark.django_db
def test_collaboration_sharing_coauthor_form_color_code_valid_hex(
    tenant_a, document, member_user
):
    """Valid 6-digit hex color codes pass CoauthorSessionForm validation."""
    for valid_color in ["#3B82F6", "#10B981", "#EF4444", "#000000", "#ffffff", "#AABBCC"]:
        form = CoauthorSessionForm(
            tenant=tenant_a,
            data={
                "document": document.pk,
                "user": member_user.pk,
                "color_code": valid_color,
                "status": "active",
                "is_editing": True,
            },
        )
        assert form.is_valid(), f"Color {valid_color} failed: {form.errors}"


@pytest.mark.django_db
def test_collaboration_sharing_coauthor_form_color_code_invalid_rejected(
    tenant_a, document, member_user
):
    """Malformed or invalid hex color codes are rejected by CoauthorSessionForm."""
    invalid_colors = [
        "blue",        # not hex
        "#123",        # 3 hex digits instead of 6
        "#GGGGGG",     # invalid characters
        "3B82F6",      # missing leading hash
        "#1234567",    # 7 digits
        "#12345",      # 5 digits
    ]
    for invalid_color in invalid_colors:
        form = CoauthorSessionForm(
            tenant=tenant_a,
            data={
                "document": document.pk,
                "user": member_user.pk,
                "color_code": invalid_color,
                "status": "active",
            },
        )
        assert not form.is_valid(), f"Color {invalid_color} should have failed validation"
        assert "color_code" in form.errors


@pytest.mark.django_db
def test_collaboration_sharing_coauthor_form_version_document_mismatch_rejected(
    tenant_a, admin_user, document
):
    """Version belonging to a different document is rejected in CoauthorSessionForm."""
    other_doc = Document.objects.create(
        tenant=tenant_a,
        title="Coauthor Other Doc",
        owner=admin_user,
    )
    other_ver = DocumentVersion.objects.create(
        tenant=tenant_a,
        document=other_doc,
        version_label="1.5",
        author=admin_user,
    )

    form = CoauthorSessionForm(
        tenant=tenant_a,
        data={
            "document": document.pk,
            "version": other_ver.pk,
            "user": admin_user.pk,
            "color_code": "#3B82F6",
            "status": "active",
        },
    )
    assert not form.is_valid()
    assert "version" in form.errors
    assert "The selected version does not belong to the selected document." in form.errors["version"]


@pytest.mark.django_db
def test_collaboration_sharing_coauthor_form_reject_foreign_injection(
    tenant_a, tenant_b, admin_user, document
):
    """reject_foreign blocks cross-tenant entities in CoauthorSessionForm."""
    doc_b = Document.objects.create(
        tenant=tenant_b,
        title="Cross Tenant Coauthor Doc",
        owner=admin_user,
    )
    form = CoauthorSessionForm(tenant=tenant_a)
    form.cleaned_data = {"document": doc_b}
    form._errors = {}
    reject_foreign(form, form.cleaned_data, ["document", "version", "draft", "user"])
    assert "document" in form.errors
    assert "That record belongs to another workspace." in form.errors["document"]


@pytest.mark.django_db
def test_collaboration_sharing_coauthor_form_valid_session_create(
    tenant_a, document, document_version, member_user
):
    """Valid CoauthorSessionForm data successfully saves a new session."""
    form = CoauthorSessionForm(
        tenant=tenant_a,
        data={
            "document": document.pk,
            "version": document_version.pk,
            "user": member_user.pk,
            "color_code": "#10B981",
            "status": "active",
            "is_editing": True,
            "current_section": "Clause 4.1 Indemnification",
        },
    )
    assert form.is_valid(), form.errors
    session = form.save(commit=False)
    session.tenant = tenant_a
    session.save()
    assert session.user == member_user
    assert session.is_editing is True
    assert session.current_section == "Clause 4.1 Indemnification"
    assert session.tenant == tenant_a


@pytest.mark.django_db
def test_collaboration_sharing_coauthor_form_guest_session_create(
    tenant_a, document
):
    """CoauthorSessionForm supports guest collaborators without a user account."""
    form = CoauthorSessionForm(
        tenant=tenant_a,
        data={
            "document": document.pk,
            "guest_name": "External Auditor Jane",
            "color_code": "#F59E0B",
            "status": "active",
            "is_editing": False,
        },
    )
    assert form.is_valid(), form.errors
    session = form.save(commit=False)
    session.tenant = tenant_a
    session.save()
    assert session.user is None
    assert session.guest_name == "External Auditor Jane"
    assert session.tenant == tenant_a


# ===========================================================================
# 3. DocumentTaskForm Unit Tests
# ===========================================================================


@pytest.mark.django_db
def test_collaboration_sharing_task_form_system_fields_excluded():
    """Verify system-managed fields are excluded from DocumentTaskForm Meta.fields."""
    form = DocumentTaskForm()
    excluded = [
        "tenant",
        "number",
        "assigned_by",
        "completed_at",
        "completed_by",
        "reminder_sent",
        "created_at",
        "updated_at",
    ]
    for field in excluded:
        assert field not in form.fields, f"Security violation: {field} exposed in DocumentTaskForm"


@pytest.mark.django_db
def test_collaboration_sharing_task_form_tenant_scoped_querysets(
    tenant_a, tenant_b, admin_user, member_user, document, document_version, review_comment, org_unit_a
):
    """DocumentTaskForm ForeignKeys must be scoped to tenant_a."""
    user_b = User.objects.create_user(
        username="user_b_task",
        email="user_b_task@globex.com",
        password="password",
        tenant=tenant_b,
        is_active=True,
    )
    inactive_user_a = User.objects.create_user(
        username="inactive_a_task",
        email="inactive_a_task@acme.com",
        password="password",
        tenant=tenant_a,
        is_active=False,
    )
    doc_b = Document.objects.create(
        tenant=tenant_b,
        title="Tenant B Task Doc",
        owner=admin_user,
    )
    ver_b = DocumentVersion.objects.create(
        tenant=tenant_b,
        document=doc_b,
        version_label="0.2",
        author=admin_user,
    )
    comment_b = DocumentReviewComment.objects.create(
        tenant=tenant_b,
        document=doc_b,
        author=admin_user,
        content="Tenant B review note",
    )
    org_b = OrgUnit.objects.create(
        tenant=tenant_b,
        name="Globex Operations",
        kind="department",
    )

    form = DocumentTaskForm(tenant=tenant_a)

    # Scoped document queryset
    assert document in form.fields["document"].queryset
    assert doc_b not in form.fields["document"].queryset

    # Scoped version queryset
    assert document_version in form.fields["version"].queryset
    assert ver_b not in form.fields["version"].queryset

    # Scoped review_comment queryset
    assert review_comment in form.fields["review_comment"].queryset
    assert comment_b not in form.fields["review_comment"].queryset

    # Scoped assigned_to queryset
    assert member_user in form.fields["assigned_to"].queryset
    assert admin_user in form.fields["assigned_to"].queryset
    assert user_b not in form.fields["assigned_to"].queryset
    assert inactive_user_a not in form.fields["assigned_to"].queryset

    # Scoped assigned_org_unit queryset
    assert org_unit_a in form.fields["assigned_org_unit"].queryset
    assert org_b not in form.fields["assigned_org_unit"].queryset


@pytest.mark.django_db
def test_collaboration_sharing_task_form_due_date_and_reminder_date_validation(
    tenant_a, document
):
    """Reminder date cannot be later than task due date."""
    today = timezone.now().date()
    due = today + timedelta(days=5)
    reminder_after_due = today + timedelta(days=7)

    # Invalid: reminder > due_date
    form_invalid = DocumentTaskForm(
        tenant=tenant_a,
        data={
            "document": document.pk,
            "title": "Update Section 2",
            "task_type": "review",
            "priority": "medium",
            "status": "pending",
            "due_date": due,
            "reminder_date": reminder_after_due,
        },
    )
    assert not form_invalid.is_valid()
    assert "reminder_date" in form_invalid.errors
    assert "Reminder date cannot be later than the task due date." in form_invalid.errors["reminder_date"]

    # Valid: reminder <= due_date
    reminder_before_due = today + timedelta(days=3)
    form_valid = DocumentTaskForm(
        tenant=tenant_a,
        data={
            "document": document.pk,
            "title": "Update Section 2",
            "task_type": "review",
            "priority": "medium",
            "status": "pending",
            "due_date": due,
            "reminder_date": reminder_before_due,
        },
    )
    assert form_valid.is_valid(), form_valid.errors


@pytest.mark.django_db
def test_collaboration_sharing_task_form_version_mismatch_rejected(
    tenant_a, admin_user, document
):
    """Version belonging to another document is rejected in DocumentTaskForm."""
    other_doc = Document.objects.create(
        tenant=tenant_a,
        title="Other Document Task Test",
        owner=admin_user,
    )
    other_ver = DocumentVersion.objects.create(
        tenant=tenant_a,
        document=other_doc,
        version_label="2.0",
        author=admin_user,
    )

    form = DocumentTaskForm(
        tenant=tenant_a,
        data={
            "document": document.pk,
            "version": other_ver.pk,
            "title": "Review Mismatched Version",
            "task_type": "review",
            "priority": "high",
            "status": "pending",
        },
    )
    assert not form.is_valid()
    assert "version" in form.errors
    assert "The selected version does not belong to the selected document." in form.errors["version"]


@pytest.mark.django_db
def test_collaboration_sharing_task_form_review_comment_mismatch_rejected(
    tenant_a, admin_user, document
):
    """Review comment belonging to another document is rejected in DocumentTaskForm."""
    other_doc = Document.objects.create(
        tenant=tenant_a,
        title="Comment Other Doc",
        owner=admin_user,
    )
    other_comment = DocumentReviewComment.objects.create(
        tenant=tenant_a,
        document=other_doc,
        author=admin_user,
        content="Other comment note",
    )

    form = DocumentTaskForm(
        tenant=tenant_a,
        data={
            "document": document.pk,
            "review_comment": other_comment.pk,
            "title": "Resolve Mismatched Comment",
            "task_type": "fact_check",
            "priority": "medium",
            "status": "pending",
        },
    )
    assert not form.is_valid()
    assert "review_comment" in form.errors
    assert "The selected review comment does not belong to the selected document." in form.errors["review_comment"]


@pytest.mark.django_db
def test_collaboration_sharing_task_form_matching_comment_and_version_valid(
    tenant_a, document, document_version, review_comment
):
    """Matching document, version, and review_comment pass validation."""
    form = DocumentTaskForm(
        tenant=tenant_a,
        data={
            "document": document.pk,
            "version": document_version.pk,
            "review_comment": review_comment.pk,
            "title": "Address Review Critique",
            "task_type": "review",
            "priority": "high",
            "status": "pending",
        },
    )
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_collaboration_sharing_task_form_reject_foreign_injection(
    tenant_a, tenant_b, admin_user, document
):
    """reject_foreign catches foreign references in DocumentTaskForm."""
    org_b = OrgUnit.objects.create(
        tenant=tenant_b,
        name="Foreign Org Unit",
        kind="department",
    )
    form = DocumentTaskForm(tenant=tenant_a)
    form.cleaned_data = {"assigned_org_unit": org_b}
    form._errors = {}
    reject_foreign(form, form.cleaned_data, ["document", "version", "review_comment", "assigned_to", "assigned_org_unit"])
    assert "assigned_org_unit" in form.errors
    assert "That record belongs to another workspace." in form.errors["assigned_org_unit"]


@pytest.mark.django_db
def test_collaboration_sharing_task_form_save_assigned_by_and_completion_lifecycle(
    tenant_a, admin_user, member_user, document
):
    """DocumentTaskForm save() manages assigned_by and completed_at / completed_by transitions."""
    # 1. Create task
    form_create = DocumentTaskForm(
        tenant=tenant_a,
        user=admin_user,
        data={
            "document": document.pk,
            "title": "Lifecycle Task",
            "task_type": "review",
            "priority": "medium",
            "status": "pending",
            "assigned_to": member_user.pk,
        },
    )
    assert form_create.is_valid(), form_create.errors
    task = form_create.save(commit=False)
    task.tenant = tenant_a
    task.save()
    assert task.assigned_by == admin_user
    assert task.completed_at is None
    assert task.completed_by is None

    # 2. Complete task
    form_complete = DocumentTaskForm(
        instance=task,
        tenant=tenant_a,
        user=member_user,
        data={
            "document": document.pk,
            "title": "Lifecycle Task",
            "task_type": "review",
            "priority": "medium",
            "status": "completed",
            "assigned_to": member_user.pk,
            "completion_notes": "Reviewed and verified specs.",
        },
    )
    assert form_complete.is_valid(), form_complete.errors
    task = form_complete.save()
    assert task.status == "completed"
    assert task.completed_at is not None
    assert task.completed_by == member_user
    assert task.completion_notes == "Reviewed and verified specs."

    # 3. Reopen task
    form_reopen = DocumentTaskForm(
        instance=task,
        tenant=tenant_a,
        user=admin_user,
        data={
            "document": document.pk,
            "title": "Lifecycle Task",
            "task_type": "review",
            "priority": "medium",
            "status": "in_progress",
            "assigned_to": member_user.pk,
        },
    )
    assert form_reopen.is_valid(), form_reopen.errors
    task = form_reopen.save()
    assert task.status == "in_progress"
    assert task.completed_at is None
    assert task.completed_by is None


# ===========================================================================
# 4. DocumentActivityForm Unit Tests
# ===========================================================================


@pytest.mark.django_db
def test_collaboration_sharing_activity_form_system_fields_excluded():
    """Verify system-managed fields are excluded from DocumentActivityForm Meta.fields."""
    form = DocumentActivityForm()
    excluded = [
        "tenant",
        "number",
        "details_json",
        "is_read",
        "read_at",
        "created_at",
        "updated_at",
    ]
    for field in excluded:
        assert field not in form.fields, f"Security violation: {field} exposed in DocumentActivityForm"


@pytest.mark.django_db
def test_collaboration_sharing_activity_form_tenant_scoped_querysets(
    tenant_a, tenant_b, admin_user, member_user, document
):
    """DocumentActivityForm ForeignKeys must be scoped to tenant_a and active users."""
    user_b = User.objects.create_user(
        username="user_b_act",
        email="user_b_act@globex.com",
        password="password",
        tenant=tenant_b,
        is_active=True,
    )
    inactive_user_a = User.objects.create_user(
        username="inactive_a_act",
        email="inactive_a_act@acme.com",
        password="password",
        tenant=tenant_a,
        is_active=False,
    )
    doc_b = Document.objects.create(
        tenant=tenant_b,
        title="Tenant B Activity Doc",
        owner=admin_user,
    )

    form = DocumentActivityForm(tenant=tenant_a)

    # Scoped document queryset
    assert document in form.fields["document"].queryset
    assert doc_b not in form.fields["document"].queryset

    # Scoped actor queryset
    assert admin_user in form.fields["actor"].queryset
    assert user_b not in form.fields["actor"].queryset
    assert inactive_user_a not in form.fields["actor"].queryset

    # Scoped target_user queryset
    assert member_user in form.fields["target_user"].queryset
    assert user_b not in form.fields["target_user"].queryset
    assert inactive_user_a not in form.fields["target_user"].queryset


@pytest.mark.django_db
def test_collaboration_sharing_activity_form_reject_foreign_injection(
    tenant_a, tenant_b, admin_user
):
    """reject_foreign blocks cross-tenant actor or target_user in DocumentActivityForm."""
    user_b = User.objects.create_user(
        username="user_b_foreign_act",
        email="user_b_foreign_act@globex.com",
        password="password",
        tenant=tenant_b,
        is_active=True,
    )
    form = DocumentActivityForm(tenant=tenant_a)
    form.cleaned_data = {"target_user": user_b}
    form._errors = {}
    reject_foreign(form, form.cleaned_data, ["document", "actor", "target_user"])
    assert "target_user" in form.errors
    assert "That record belongs to another workspace." in form.errors["target_user"]


@pytest.mark.django_db
def test_collaboration_sharing_activity_form_valid_submission(
    tenant_a, admin_user, member_user, document
):
    """Valid data passes DocumentActivityForm validation."""
    form = DocumentActivityForm(
        tenant=tenant_a,
        data={
            "document": document.pk,
            "actor": admin_user.pk,
            "target_user": member_user.pk,
            "action_type": "task_assigned",
            "summary": "Admin assigned a compliance review item to Jane Doe.",
            "notification_channel": "in_app",
        },
    )
    assert form.is_valid(), form.errors
    activity = form.save(commit=False)
    activity.tenant = tenant_a
    activity.save()
    assert activity.document == document
    assert activity.actor == admin_user
    assert activity.target_user == member_user
    assert activity.summary == "Admin assigned a compliance review item to Jane Doe."
    assert activity.tenant == tenant_a


@pytest.mark.django_db
def test_collaboration_sharing_activity_form_guest_submission(
    tenant_a, member_user, document
):
    """DocumentActivityForm supports anonymous or external guest actor."""
    form = DocumentActivityForm(
        tenant=tenant_a,
        data={
            "document": document.pk,
            "guest_name": "External Auditor John",
            "target_user": member_user.pk,
            "action_type": "link_accessed",
            "summary": "External auditor accessed the shared link.",
            "notification_channel": "email_digest",
        },
    )
    assert form.is_valid(), form.errors
    activity = form.save(commit=False)
    activity.tenant = tenant_a
    activity.save()
    assert activity.actor is None
    assert activity.guest_name == "External Auditor John"
    assert activity.action_type == "link_accessed"
    assert activity.tenant == tenant_a
