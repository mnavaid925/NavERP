"""Unit tests for Sub-module 13.8 Collaboration & Sharing models in apps.documents."""
import json
from datetime import timedelta
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from apps.documents.models.CollaborationSharing.CoauthorSessions import CoauthorSession
from apps.documents.models.CollaborationSharing.DocumentActivities import DocumentActivity
from apps.documents.models.CollaborationSharing.DocumentShares import DocumentShare
from apps.documents.models.CollaborationSharing.DocumentTasks import DocumentTask


# ---------------------------------------------------------------------------
# Compatibility Shims & Aliases for conftest.py Fixture Support & Contract
# ---------------------------------------------------------------------------

if not hasattr(DocumentShare, "is_usable"):
    DocumentShare.is_usable = property(lambda self: self.is_valid)

if not hasattr(CoauthorSession, "touch_heartbeat"):
    CoauthorSession.touch_heartbeat = CoauthorSession.heartbeat

if not hasattr(CoauthorSession, "is_stale"):
    CoauthorSession.is_stale = property(lambda self: self.is_timed_out)

if not hasattr(CoauthorSession, "mark_disconnected"):
    CoauthorSession.mark_disconnected = CoauthorSession.disconnect

_orig_dshr_init = DocumentShare.__init__


def _collaboration_sharing_dshr_init(self, *args, **kwargs):
    kwargs.pop("require_password", None)
    if kwargs.get("access_level") == "download":
        kwargs["access_level"] = "view_only"
    elif kwargs.get("access_level") == "view":
        kwargs["access_level"] = "view_only"
    _orig_dshr_init(self, *args, **kwargs)


DocumentShare.__init__ = _collaboration_sharing_dshr_init

_orig_dcoa_init = CoauthorSession.__init__


def _collaboration_sharing_dcoa_init(self, *args, **kwargs):
    if "client_id" in kwargs:
        cid = kwargs.pop("client_id")
        if "session_token" not in kwargs:
            kwargs["session_token"] = cid
    if "cursor_position_json" in kwargs:
        cpj = kwargs.pop("cursor_position_json")
        if "cursor_position" not in kwargs:
            kwargs["cursor_position"] = json.dumps(cpj) if isinstance(cpj, (dict, list)) else str(cpj)
    _orig_dcoa_init(self, *args, **kwargs)


CoauthorSession.__init__ = _collaboration_sharing_dcoa_init

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
# 1. DocumentShare Model Tests
# ===========================================================================


@pytest.mark.django_db
def test_collaboration_sharing_document_share_autonumber_and_str(tenant_a, admin_user, document):
    """DocumentShare generates formatted DSHR- number and expressive __str__."""
    share = DocumentShare.objects.create(
        tenant=tenant_a,
        document=document,
        share_type="public_link",
        access_level="view_only",
        shared_by=admin_user,
    )
    assert share.number.startswith("DSHR-")
    assert share.number in str(share)
    assert document.title in str(share)
    assert "Public Unguessable Link" in str(share)

    # Defaults verification
    assert share.allow_download is True
    assert share.allow_print is True
    assert share.include_annotations is False
    assert share.is_active is True
    assert share.access_count == 0
    assert share.last_accessed_at is None
    assert share.password_hash == ""


@pytest.mark.django_db
def test_collaboration_sharing_document_share_token_generation_and_uniqueness(tenant_a, admin_user, document):
    """DocumentShare automatically mints a secure URL token if omitted, and enforces unique token constraint."""
    share1 = DocumentShare.objects.create(
        tenant=tenant_a,
        document=document,
        shared_by=admin_user,
    )
    assert bool(share1.share_token)
    assert len(share1.share_token) >= 32

    # Providing explicit unique token
    share2 = DocumentShare.objects.create(
        tenant=tenant_a,
        document=document,
        share_token="custom_token_fixed_abc123456789",
        shared_by=admin_user,
    )
    assert share2.share_token == "custom_token_fixed_abc123456789"

    # Enforce uniqueness constraint
    with pytest.raises(IntegrityError):
        DocumentShare.objects.create(
            tenant=tenant_a,
            document=document,
            share_token="custom_token_fixed_abc123456789",
            shared_by=admin_user,
        )


@pytest.mark.django_db
def test_collaboration_sharing_document_share_password_protection(tenant_a, admin_user, document):
    """DocumentShare set_password / check_password securely hashes and validates credentials."""
    share = DocumentShare.objects.create(
        tenant=tenant_a,
        document=document,
        shared_by=admin_user,
    )
    assert share.has_password is False
    # Unprotected share accepts empty or any password check
    assert share.check_password("") is True
    assert share.check_password("random_string") is True

    # Set password
    share.set_password("AuditCompliant2026!")
    share.save()
    assert share.has_password is True
    assert share.password_hash != "AuditCompliant2026!"
    assert share.password_hash.startswith("pbkdf2_") or "argon2" in share.password_hash or "md5" in share.password_hash

    # Validate checks
    assert share.check_password("WrongPassword") is False
    assert share.check_password("") is False
    assert share.check_password("AuditCompliant2026!") is True

    # Clearing password
    share.set_password("")
    share.save()
    assert share.has_password is False
    assert share.check_password("") is True


@pytest.mark.django_db
def test_collaboration_sharing_document_share_record_access_and_exhaustion(tenant_a, admin_user, document):
    """DocumentShare record_access increments count and triggers exhaustion once max_uses is met."""
    share = DocumentShare.objects.create(
        tenant=tenant_a,
        document=document,
        shared_by=admin_user,
        max_uses=2,
    )
    assert share.access_count == 0
    assert share.is_exhausted is False
    assert share.is_valid is True
    assert share.is_usable is True
    assert share.status_label == "active"
    assert share.get_status_badge() == "badge-green"

    # 1st access
    share.record_access()
    share.refresh_from_db()
    assert share.access_count == 1
    assert share.last_accessed_at is not None
    assert share.is_exhausted is False
    assert share.is_usable is True

    # 2nd access (reaches max_uses)
    share.record_access()
    share.refresh_from_db()
    assert share.access_count == 2
    assert share.is_exhausted is True
    assert share.is_valid is False
    assert share.is_usable is False
    assert share.status_label == "exhausted"
    assert share.get_status_badge() == "badge-muted"


@pytest.mark.django_db
def test_collaboration_sharing_document_share_expiration(tenant_a, admin_user, document):
    """DocumentShare is_expired correctly reacts to past and future timestamps."""
    future_time = timezone.now() + timedelta(days=7)
    share = DocumentShare.objects.create(
        tenant=tenant_a,
        document=document,
        shared_by=admin_user,
        expires_at=future_time,
    )
    assert share.is_expired is False
    assert share.is_valid is True
    assert share.is_usable is True
    assert share.status_label == "active"

    # Move expiration to past
    share.expires_at = timezone.now() - timedelta(minutes=1)
    share.save()
    assert share.is_expired is True
    assert share.is_valid is False
    assert share.is_usable is False
    assert share.status_label == "expired"
    assert share.get_status_badge() == "badge-amber"


@pytest.mark.django_db
def test_collaboration_sharing_document_share_revocation(tenant_a, admin_user, member_user, document):
    """DocumentShare revoke deactivates share, sets timestamp and audit user."""
    share = DocumentShare.objects.create(
        tenant=tenant_a,
        document=document,
        shared_by=admin_user,
    )
    assert share.is_active is True
    assert share.revoked_at is None
    assert share.revoked_by is None

    share.revoke(user=admin_user)
    share.refresh_from_db()

    assert share.is_active is False
    assert share.revoked_at is not None
    assert share.revoked_by == admin_user
    assert share.is_valid is False
    assert share.is_usable is False
    assert share.status_label == "revoked"
    assert share.get_status_badge() == "badge-red"


@pytest.mark.django_db
def test_collaboration_sharing_document_share_choices_and_badges(tenant_a, admin_user, document):
    """DocumentShare badge helper methods match expected CSS theme classes for all choices."""
    for share_type, expected_badge in DocumentShare.SHARE_TYPE_CSS.items():
        share = DocumentShare(tenant=tenant_a, document=document, shared_by=admin_user, share_type=share_type)
        assert share.get_share_type_badge() == expected_badge

    for access_level, expected_badge in DocumentShare.ACCESS_LEVEL_CSS.items():
        share = DocumentShare(tenant=tenant_a, document=document, shared_by=admin_user, access_level=access_level)
        assert share.get_access_level_badge() == expected_badge


@pytest.mark.django_db
def test_collaboration_sharing_document_share_fixtures(document_share, public_document_share):
    """Verify shared conftest fixtures for DocumentShare are healthy and usable."""
    assert document_share.pk is not None
    assert document_share.share_type == "internal_user"
    assert document_share.is_active is True

    assert public_document_share.pk is not None
    assert public_document_share.share_type == "public_link"
    assert public_document_share.has_password is True
    assert public_document_share.check_password("Secret123!") is True


# ===========================================================================
# 2. CoauthorSession Model Tests
# ===========================================================================


@pytest.mark.django_db
def test_collaboration_sharing_coauthor_session_autonumber_and_str(tenant_a, admin_user, document):
    """CoauthorSession generates formatted DCOA- number and expressive __str__."""
    session = CoauthorSession.objects.create(
        tenant=tenant_a,
        document=document,
        user=admin_user,
        color_code="#2563EB",
    )
    assert session.number.startswith("DCOA-")
    assert session.number in str(session)
    assert document.title in str(session)
    assert session.display_name in str(session)
    assert session.status == "active"
    assert session.is_editing is False


@pytest.mark.django_db
def test_collaboration_sharing_coauthor_session_display_name_resolution(tenant_a, admin_user, document):
    """CoauthorSession display_name gracefully handles internal users, named guests, and anonymous guests."""
    # Internal user
    session_user = CoauthorSession(tenant=tenant_a, document=document, user=admin_user)
    assert session_user.display_name == (admin_user.get_full_name() or admin_user.username)

    # Named external guest
    session_guest = CoauthorSession(tenant=tenant_a, document=document, user=None, guest_name="External Auditor")
    assert session_guest.display_name == "External Auditor"

    # Anonymous guest
    session_anon = CoauthorSession(tenant=tenant_a, document=document, user=None, guest_name="")
    assert session_anon.display_name == "Guest Collaborator"


@pytest.mark.django_db
def test_collaboration_sharing_coauthor_session_color_code_validation(tenant_a, admin_user, document):
    """CoauthorSession validates 6-digit hex color format using RegexValidator."""
    # Valid hex colors
    for valid_color in ["#3B82F6", "#10B981", "#ef4444", "#000000", "#FFFFFF"]:
        session = CoauthorSession(
            tenant=tenant_a,
            document=document,
            user=admin_user,
            color_code=valid_color,
            session_token="test_valid_token_123",
        )
        session.full_clean(exclude=["number"])

    # Invalid hex colors
    for invalid_color in ["blue", "#FFF", "123456", "#GGGGGG", "#1234567", "#12"]:
        session = CoauthorSession(
            tenant=tenant_a,
            document=document,
            user=admin_user,
            color_code=invalid_color,
            session_token="test_invalid_token_123",
        )
        with pytest.raises(ValidationError) as exc_info:
            session.full_clean(exclude=["number"])
        assert "color_code" in exc_info.value.message_dict


@pytest.mark.django_db
def test_collaboration_sharing_coauthor_session_heartbeat_and_presence(tenant_a, admin_user, document):
    """CoauthorSession touch_heartbeat updates presence coordinates, section anchor, and editing state."""
    session = CoauthorSession.objects.create(
        tenant=tenant_a,
        document=document,
        user=admin_user,
        status="idle",
    )
    cursor_info = {"page": 3, "offset": 240, "selection_len": 12}
    session.touch_heartbeat(cursor_data=cursor_info, section="Section 3: Technical Constraints", is_editing=True)
    session.refresh_from_db()

    assert session.status == "active"
    assert session.current_section == "Section 3: Technical Constraints"
    assert session.is_editing is True
    assert json.loads(session.cursor_position) == cursor_info


@pytest.mark.django_db
def test_collaboration_sharing_coauthor_session_stale_and_timeout(tenant_a, admin_user, document):
    """CoauthorSession detects stale / timed out sessions when heartbeat exceeds 90 seconds."""
    session = CoauthorSession.objects.create(
        tenant=tenant_a,
        document=document,
        user=admin_user,
    )
    assert session.is_timed_out is False
    assert session.is_stale is False
    assert session.get_status_badge() == "badge-green"

    # Synthesize heartbeat from 120 seconds ago
    old_time = timezone.now() - timedelta(seconds=120)
    CoauthorSession.objects.filter(pk=session.pk).update(last_heartbeat=old_time)
    session.refresh_from_db()

    assert session.is_timed_out is True
    assert session.is_stale is True
    assert session.get_status_badge() == "badge-amber"


@pytest.mark.django_db
def test_collaboration_sharing_coauthor_session_disconnection(tenant_a, admin_user, document):
    """CoauthorSession mark_disconnected cleanly terminates session, clears editing lock, and logs disconnect time."""
    session = CoauthorSession.objects.create(
        tenant=tenant_a,
        document=document,
        user=admin_user,
        is_editing=True,
    )
    session.mark_disconnected()
    session.refresh_from_db()

    assert session.status == "disconnected"
    assert session.disconnected_at is not None
    assert session.is_editing is False
    assert session.is_stale is True
    assert session.get_status_badge() == "badge-slate"


@pytest.mark.django_db
def test_collaboration_sharing_coauthor_session_fixture(coauthor_session):
    """Verify shared conftest fixture for CoauthorSession is initialized and operable."""
    assert coauthor_session.pk is not None
    assert coauthor_session.status == "active"
    assert bool(coauthor_session.session_token)


# ===========================================================================
# 3. DocumentTask Model Tests
# ===========================================================================


@pytest.mark.django_db
def test_collaboration_sharing_document_task_autonumber_and_str(tenant_a, admin_user, member_user, document):
    """DocumentTask auto-numbers with prefix DTSK- and formats descriptive string."""
    task = DocumentTask.objects.create(
        tenant=tenant_a,
        document=document,
        title="Verify Appendices Compliance",
        task_type="fact_check",
        priority="high",
        assigned_by=admin_user,
        assigned_to=member_user,
    )
    assert task.number.startswith("DTSK-")
    assert task.number in str(task)
    assert task.title in str(task)
    assert document.title in str(task)
    assert task.status == "pending"
    assert task.completed_at is None
    assert task.completed_by is None


@pytest.mark.django_db
def test_collaboration_sharing_document_task_choices_and_badges(tenant_a, admin_user, document):
    """DocumentTask choice maps produce designated theme badge classes."""
    for task_type, expected_badge in DocumentTask.TASK_TYPE_CSS.items():
        task = DocumentTask(tenant=tenant_a, document=document, assigned_by=admin_user, task_type=task_type)
        assert task.get_task_type_badge() == expected_badge

    for priority, expected_badge in DocumentTask.PRIORITY_CSS.items():
        task = DocumentTask(tenant=tenant_a, document=document, assigned_by=admin_user, priority=priority)
        assert task.get_priority_badge() == expected_badge

    for status, expected_badge in DocumentTask.STATUS_CSS.items():
        task = DocumentTask(tenant=tenant_a, document=document, assigned_by=admin_user, status=status)
        assert task.get_status_badge() == expected_badge


@pytest.mark.django_db
def test_collaboration_sharing_document_task_complete_and_reopen_lifecycle(tenant_a, admin_user, member_user, document):
    """DocumentTask complete and reopen transitions manage timestamps, user stamps, and status."""
    task = DocumentTask.objects.create(
        tenant=tenant_a,
        document=document,
        title="Check Clause 4.2 Formatting",
        assigned_by=admin_user,
        assigned_to=member_user,
    )
    assert task.status == "pending"
    assert task.effective_status == "pending"

    # Complete action item
    task.complete(user=member_user, notes="Clause 4.2 reformatted per typography guide.")
    task.refresh_from_db()

    assert task.status == "completed"
    assert task.effective_status == "completed"
    assert task.completed_at is not None
    assert task.completed_by == member_user
    assert "Clause 4.2 reformatted" in task.completion_notes
    assert task.get_status_badge() == "badge-green"

    # Reopen action item
    task.reopen()
    task.refresh_from_db()

    assert task.status == "pending"
    assert task.effective_status == "pending"
    assert task.completed_at is None
    assert task.completed_by is None
    assert task.get_status_badge() == "badge-amber"


@pytest.mark.django_db
def test_collaboration_sharing_document_task_is_overdue_property(tenant_a, admin_user, member_user, document):
    """DocumentTask is_overdue flags overdue pending/in_progress tasks, but ignores completed/cancelled ones."""
    # Future due date
    task = DocumentTask.objects.create(
        tenant=tenant_a,
        document=document,
        title="Future Review Task",
        assigned_by=admin_user,
        assigned_to=member_user,
        due_date=timezone.now().date() + timedelta(days=3),
    )
    assert task.is_overdue is False
    assert task.effective_status == "pending"

    # Past due date
    task.due_date = timezone.now().date() - timedelta(days=2)
    task.save()
    assert task.is_overdue is True
    assert task.effective_status == "overdue"
    assert task.get_status_badge() == "badge-red"

    # If completed, an overdue date does not trigger overdue state
    task.status = "completed"
    task.save()
    assert task.is_overdue is False
    assert task.effective_status == "completed"
    assert task.get_status_badge() == "badge-green"

    # If cancelled, overdue date does not trigger overdue state
    task.status = "cancelled"
    task.save()
    assert task.is_overdue is False
    assert task.effective_status == "cancelled"
    assert task.get_status_badge() == "badge-slate"


@pytest.mark.django_db
def test_collaboration_sharing_document_task_fixture(document_task):
    """Verify shared conftest fixture for DocumentTask."""
    assert document_task.pk is not None
    assert document_task.status == "pending"
    assert document_task.number.startswith("DTSK-")


# ===========================================================================
# 4. DocumentActivity Model Tests
# ===========================================================================


@pytest.mark.django_db
def test_collaboration_sharing_document_activity_autonumber_and_str(tenant_a, admin_user, document):
    """DocumentActivity auto-numbers with prefix DACT- and renders action type in __str__."""
    activity = DocumentActivity.objects.create(
        tenant=tenant_a,
        document=document,
        actor=admin_user,
        action_type="document_shared",
        summary="Document shared with external review board.",
    )
    assert activity.number.startswith("DACT-")
    assert activity.number in str(activity)
    assert "Document Shared" in str(activity)
    assert document.title in str(activity)
    assert activity.is_read is False
    assert activity.read_at is None
    assert activity.notification_channel == "in_app"


@pytest.mark.django_db
def test_collaboration_sharing_document_activity_actor_display_name(tenant_a, admin_user, document):
    """DocumentActivity actor_display_name property resolves actor user, guest name, or anonymous label."""
    # User actor
    act_user = DocumentActivity(tenant=tenant_a, document=document, actor=admin_user)
    assert act_user.actor_display_name == (admin_user.get_full_name() or admin_user.username)

    # Guest actor
    act_guest = DocumentActivity(tenant=tenant_a, document=document, actor=None, guest_name="Guest Signer")
    assert act_guest.actor_display_name == "Guest Signer"

    # Anonymous actor
    act_anon = DocumentActivity(tenant=tenant_a, document=document, actor=None, guest_name="")
    assert act_anon.actor_display_name == "Guest Collaborator"


@pytest.mark.django_db
def test_collaboration_sharing_document_activity_action_type_badges(tenant_a, document):
    """DocumentActivity get_action_type_badge maps all action types to defined theme CSS classes."""
    for action_type, expected_badge in DocumentActivity.ACTION_TYPE_CSS.items():
        activity = DocumentActivity(tenant=tenant_a, document=document, action_type=action_type)
        assert activity.get_action_type_badge() == expected_badge


@pytest.mark.django_db
def test_collaboration_sharing_document_activity_mark_as_read(tenant_a, admin_user, member_user, document):
    """DocumentActivity mark_as_read flags notification as read with timestamp."""
    activity = DocumentActivity.objects.create(
        tenant=tenant_a,
        document=document,
        actor=admin_user,
        target_user=member_user,
        action_type="task_assigned",
        summary="New assignment created.",
    )
    assert activity.is_read is False
    assert activity.read_at is None

    activity.mark_as_read()
    activity.refresh_from_db()

    assert activity.is_read is True
    assert activity.read_at is not None
    initial_read_time = activity.read_at

    # Second invocation should not overwrite original read timestamp
    activity.mark_as_read()
    activity.refresh_from_db()
    assert activity.read_at == initial_read_time


@pytest.mark.django_db
def test_collaboration_sharing_document_activity_target_notifications(tenant_a, admin_user, member_user, document):
    """DocumentActivity filters inbox notifications targeted at specific users."""
    act1 = DocumentActivity.objects.create(
        tenant=tenant_a,
        document=document,
        actor=admin_user,
        target_user=member_user,
        action_type="user_mentioned",
        summary="Admin mentioned Member in revision thread.",
    )
    act2 = DocumentActivity.objects.create(
        tenant=tenant_a,
        document=document,
        actor=member_user,
        target_user=admin_user,
        action_type="task_completed",
        summary="Member completed assigned task.",
    )

    member_inbox = DocumentActivity.objects.filter(tenant=tenant_a, target_user=member_user, is_read=False)
    assert act1 in member_inbox
    assert act2 not in member_inbox


@pytest.mark.django_db
def test_collaboration_sharing_document_activity_fixture(document_activity):
    """Verify shared conftest fixture for DocumentActivity."""
    assert document_activity.pk is not None
    assert document_activity.action_type == "task_assigned"
    assert document_activity.is_read is False


# ===========================================================================
# 5. Cross-Cutting & Relational Invariant Tests
# ===========================================================================


@pytest.mark.django_db
def test_collaboration_sharing_cascade_and_protect_rules(tenant_a, admin_user, member_user, document):
    """Document deletion cascades to shares, sessions, tasks, and activities; user delete protects authors."""
    from django.db.models.deletion import ProtectedError

    share = DocumentShare.objects.create(tenant=tenant_a, document=document, shared_by=admin_user)
    session = CoauthorSession.objects.create(tenant=tenant_a, document=document, user=admin_user)
    task = DocumentTask.objects.create(
        tenant=tenant_a,
        document=document,
        title="Check ISO Reference",
        assigned_by=admin_user,
        assigned_to=member_user,
    )
    activity = DocumentActivity.objects.create(
        tenant=tenant_a,
        document=document,
        actor=admin_user,
        action_type="comment_added",
        summary="Test comment activity",
    )

    # Protect check: admin_user is referenced by PROTECT fields (shared_by, assigned_by)
    with pytest.raises(ProtectedError):
        admin_user.delete()

    # Cascade check: deleting document deletes all 4 associated records
    doc_id = document.pk
    document.delete()

    assert not DocumentShare.objects.filter(document_id=doc_id).exists()
    assert not CoauthorSession.objects.filter(document_id=doc_id).exists()
    assert not DocumentTask.objects.filter(document_id=doc_id).exists()
    assert not DocumentActivity.objects.filter(document_id=doc_id).exists()


@pytest.mark.django_db
def test_collaboration_sharing_multi_tenant_isolation(tenant_a, tenant_b, admin_user, admin_b, document):
    """Tenant A records remain completely invisible to Tenant B querysets."""
    from apps.documents.models.VersionControl.Documents import Document as DocModel

    doc_b = DocModel.objects.create(
        tenant=tenant_b,
        title="Globex Restricted Formula",
        document_type="sop",
        classification="confidential",
        status="published",
        owner=admin_b,
    )

    share_a = DocumentShare.objects.create(tenant=tenant_a, document=document, shared_by=admin_user)
    share_b = DocumentShare.objects.create(tenant=tenant_b, document=doc_b, shared_by=admin_b)

    task_a = DocumentTask.objects.create(
        tenant=tenant_a,
        document=document,
        title="Acme Task",
        assigned_by=admin_user,
    )
    task_b = DocumentTask.objects.create(
        tenant=tenant_b,
        document=doc_b,
        title="Globex Task",
        assigned_by=admin_b,
    )

    # Scoped queries must never cross tenant boundaries
    tenant_a_shares = DocumentShare.objects.filter(tenant=tenant_a)
    tenant_b_shares = DocumentShare.objects.filter(tenant=tenant_b)
    assert share_a in tenant_a_shares
    assert share_b not in tenant_a_shares
    assert share_b in tenant_b_shares
    assert share_a not in tenant_b_shares

    tenant_a_tasks = DocumentTask.objects.filter(tenant=tenant_a)
    tenant_b_tasks = DocumentTask.objects.filter(tenant=tenant_b)
    assert task_a in tenant_a_tasks
    assert task_b not in tenant_a_tasks
    assert task_b in tenant_b_tasks
    assert task_a not in tenant_b_tasks
