"""Projects 7.9 — Collaboration & Communication security tests.

Every assertion here is about what an ATTACKER gets, not about the happy path: anonymity, the
cross-tenant boundary (including crafted POST *bodies*, which a status-only IDOR probe never
reaches), the per-recipient notification boundary, mass assignment against the verb-written flags,
CSRF, and XSS through the user-authored text fields.

The two review findings this file pins as regressions:
* **I1** — a crafted ``msg_edit`` that repoints a thread ROOT must not be able to strand its replies.
* **I8** — a member must not be able to clear or delete a TEAMMATE's notification row.

Naming: every test ``test_collab_*``, every helper ``_collab_*``.
"""
import pytest
from django.urls import reverse

from apps.projects.models import (
    Channel,
    ChannelMessage,
    DocumentShare,
    Meeting,
    MeetingActionItem,
    MeetingAgendaItem,
    ProjectNotification,
)

#: Every one of the 41 routes, with the fixture supplying a pk (None = no pk in the path).
_ROUTE_FIXTURES = [
    ("activity_feed", None),
    ("chn_list", None), ("chn_create", None),
    ("chn_detail", "collab_channel_a"), ("chn_edit", "collab_channel_a"),
    ("chn_delete", "collab_channel_a"), ("chn_archive", "collab_channel_a"),
    ("msg_list", None), ("msg_create", None),
    ("msg_edit", "collab_message_bare_a"), ("msg_delete", "collab_message_bare_a"),
    ("dsh_list", None), ("dsh_create", None),
    ("dsh_detail", "collab_share_view_a"), ("dsh_edit", "collab_share_view_a"),
    ("dsh_delete", "collab_share_view_a"), ("dsh_revoke", "collab_share_view_a"),
    ("dsh_claim", "collab_share_edit_free_a"), ("dsh_release", "collab_share_edit_claimed_a"),
    ("mtg_list", None), ("mtg_create", None),
    ("mtg_detail", "collab_meeting_scheduled_a"), ("mtg_edit", "collab_meeting_scheduled_a"),
    ("mtg_delete", "collab_meeting_scheduled_a"), ("mtg_start", "collab_meeting_scheduled_a"),
    ("mtg_complete", "collab_meeting_in_progress_a"), ("mtg_cancel", "collab_meeting_scheduled_a"),
    ("mtg_minutes", "collab_meeting_scheduled_a"),
    ("agi_create", "collab_meeting_scheduled_a"), ("agi_edit", "collab_agenda_open_a"),
    ("agi_delete", "collab_agenda_open_a"), ("agi_cover", "collab_agenda_open_a"),
    ("mai_create", "collab_meeting_scheduled_a"), ("mai_edit", "collab_action_open_a"),
    ("mai_delete", "collab_action_open_a"), ("mai_toggle", "collab_action_open_a"),
    ("ntf_list", None), ("ntf_mark_all_read", None),
    ("ntf_detail", "collab_notification_unread_a"),
    ("ntf_mark_read", "collab_notification_unread_a"),
    ("ntf_delete", "collab_notification_unread_a"),
]

#: The 18 verbs — POST-only, so a crafted POST is the attack and a GET is merely a 405.
_VERB_NAMES = {
    "chn_delete", "chn_archive", "msg_delete",
    "dsh_delete", "dsh_revoke", "dsh_claim", "dsh_release",
    "mtg_delete", "mtg_start", "mtg_complete", "mtg_cancel",
    "agi_delete", "agi_cover", "mai_delete", "mai_toggle",
    "ntf_mark_all_read", "ntf_mark_read", "ntf_delete",
}

#: (route, tenant-B fixture) — every pk-carrying route, as tenant A.
_IDOR = [
    ("chn_detail", "collab_channel_b"), ("chn_edit", "collab_channel_b"),
    ("chn_delete", "collab_channel_b"), ("chn_archive", "collab_channel_b"),
    ("msg_edit", "collab_message_b"), ("msg_delete", "collab_message_b"),
    ("dsh_detail", "collab_share_b"), ("dsh_edit", "collab_share_b"),
    ("dsh_delete", "collab_share_b"), ("dsh_revoke", "collab_share_b"),
    ("dsh_claim", "collab_share_b"), ("dsh_release", "collab_share_b"),
    ("mtg_detail", "collab_meeting_b"), ("mtg_edit", "collab_meeting_b"),
    ("mtg_delete", "collab_meeting_b"), ("mtg_start", "collab_meeting_b"),
    ("mtg_complete", "collab_meeting_b"), ("mtg_cancel", "collab_meeting_b"),
    ("mtg_minutes", "collab_meeting_b"),
    ("agi_create", "collab_meeting_b"), ("agi_edit", "collab_agenda_b"),
    ("agi_delete", "collab_agenda_b"), ("agi_cover", "collab_agenda_b"),
    ("mai_create", "collab_meeting_b"), ("mai_edit", "collab_action_b"),
    ("mai_delete", "collab_action_b"), ("mai_toggle", "collab_action_b"),
    ("ntf_detail", "collab_notification_b"), ("ntf_mark_read", "collab_notification_b"),
    ("ntf_delete", "collab_notification_b"),
]


def _url(name, fixture, request):
    args = [] if fixture is None else [request.getfixturevalue(fixture).pk]
    return reverse(f"projects:{name}", args=args)


# ==================================================================================================
# Anonymity
# ==================================================================================================

def test_collab_route_list_is_the_full_forty_one(db):
    assert len(_ROUTE_FIXTURES) == 41


@pytest.mark.parametrize("name,fixture", _ROUTE_FIXTURES)
def test_collab_anonymous_is_redirected_to_login(db, collab_anon_client, request, name, fixture):
    r = collab_anon_client.get(_url(name, fixture, request))
    assert r.status_code == 302, f"{name} -> {r.status_code}"
    assert "/login" in r["Location"] or "accounts" in r["Location"], r["Location"]


# ==================================================================================================
# Cross-tenant IDOR — every pk-carrying route
# ==================================================================================================

def test_collab_idor_route_list_covers_every_pk_route(db):
    assert len(_IDOR) == 30


@pytest.mark.parametrize("name,fixture", _IDOR)
def test_collab_foreign_pk_is_404(db, collab_admin_client, request, name, fixture):
    """Tenant A asking for tenant B's row — a 404, never a 200 or a 403 that confirms existence."""
    url = _url(name, fixture, request)
    r = (collab_admin_client.post(url) if name in _VERB_NAMES
         else collab_admin_client.get(url))
    assert r.status_code == 404, f"{name} -> {r.status_code}"


@pytest.mark.parametrize("name,fixture", _IDOR)
def test_collab_foreign_pk_is_404_for_a_member_too(db, collab_member_client, request, name,
                                                   fixture):
    """Member-level per contract L27 — the tenant boundary still applies to a plain member."""
    url = _url(name, fixture, request)
    r = (collab_member_client.post(url) if name in _VERB_NAMES
         else collab_member_client.get(url))
    assert r.status_code == 404, f"{name} -> {r.status_code}"


def test_collab_foreign_row_is_untouched_by_a_cross_tenant_verb(
        db, collab_admin_client, collab_channel_b):
    """The 404 must be a refusal, not a silent partial write."""
    collab_admin_client.post(reverse("projects:chn_archive", args=[collab_channel_b.pk]))
    collab_channel_b.refresh_from_db()
    assert collab_channel_b.is_archived is False


# ==================================================================================================
# Crafted cross-tenant POST bodies — the boundary a pk-only probe never reaches
# ==================================================================================================

def test_collab_crafted_foreign_channel_body_is_rejected(db, collab_admin_client,
                                                         collab_channel_b):
    before = ChannelMessage.objects.count()
    r = collab_admin_client.post(reverse("projects:msg_create"), {
        "channel": collab_channel_b.pk, "body": "Foreign write attempt.", "mentions": []})
    assert r.status_code == 200  # re-rendered with the form error
    assert ChannelMessage.objects.count() == before
    assert not ChannelMessage.objects.filter(body="Foreign write attempt.").exists()


def test_collab_crafted_foreign_project_body_is_rejected(db, collab_admin_client,
                                                         planning_project_b):
    before = Channel.objects.count()
    r = collab_admin_client.post(reverse("projects:chn_create"), {
        "project": planning_project_b.pk, "name": "Foreign channel", "topic": "",
        "kind": "discussion"})
    assert r.status_code == 200
    assert Channel.objects.count() == before
    assert not Channel.objects.filter(name="Foreign channel").exists()


def test_collab_crafted_foreign_document_body_is_rejected(db, collab_admin_client,
                                                          planning_project_a, collab_document_b):
    before = DocumentShare.objects.count()
    r = collab_admin_client.post(reverse("projects:dsh_create"), {
        "project": planning_project_a.pk, "channel": "", "document": collab_document_b.pk,
        "access_level": "view", "shared_with": "", "note": ""})
    assert r.status_code == 200
    assert DocumentShare.objects.count() == before


def test_collab_crafted_foreign_task_body_is_rejected(db, collab_admin_client,
                                                      collab_meeting_scheduled_a,
                                                      planning_project_b):
    from apps.projects.tests.conftest import _planning_task
    foreign_task = _planning_task(planning_project_b.tenant, planning_project_b)
    before = MeetingActionItem.objects.count()
    r = collab_admin_client.post(reverse("projects:mai_create",
                                         args=[collab_meeting_scheduled_a.pk]), {
        "description": "Foreign task link", "assignee": "", "due_date": "",
        "task": foreign_task.pk})
    assert r.status_code == 200
    assert MeetingActionItem.objects.count() == before


def test_collab_crafted_foreign_mention_mints_no_notification(
        db, collab_admin_client, collab_channel_a, admin_b):
    """The M2M boundary: a foreign user must not be mentionable, and must get no inbox row."""
    before_messages = ChannelMessage.objects.count()
    before_notifications = ProjectNotification.objects.count()
    r = collab_admin_client.post(reverse("projects:msg_create"), {
        "channel": collab_channel_a.pk, "body": "Mention attempt.", "mentions": [admin_b.pk]})
    assert r.status_code == 200
    assert ChannelMessage.objects.count() == before_messages
    assert ProjectNotification.objects.count() == before_notifications


def test_collab_crafted_foreign_shared_with_is_rejected(db, collab_admin_client,
                                                        planning_project_a, collab_document_a,
                                                        admin_b):
    before = DocumentShare.objects.count()
    r = collab_admin_client.post(reverse("projects:dsh_create"), {
        "project": planning_project_a.pk, "channel": "", "document": collab_document_a.pk,
        "access_level": "view", "shared_with": admin_b.pk, "note": ""})
    assert r.status_code == 200
    assert DocumentShare.objects.count() == before


# ==================================================================================================
# I8 — the per-recipient notification boundary
# ==================================================================================================

def test_collab_marking_a_teammates_notification_read_is_404(db, collab_admin_client,
                                                             collab_notification_other_a):
    r = collab_admin_client.post(
        reverse("projects:ntf_mark_read", args=[collab_notification_other_a.pk]))
    assert r.status_code == 404, f"got {r.status_code}"
    collab_notification_other_a.refresh_from_db()
    assert collab_notification_other_a.is_read is False
    assert collab_notification_other_a.read_at is None


def test_collab_deleting_a_teammates_notification_is_404(db, collab_admin_client,
                                                         collab_notification_other_a):
    r = collab_admin_client.post(
        reverse("projects:ntf_delete", args=[collab_notification_other_a.pk]))
    assert r.status_code == 404, f"got {r.status_code}"
    assert ProjectNotification.objects.filter(pk=collab_notification_other_a.pk).exists()


def test_collab_a_member_may_still_mark_their_own_notification_read(
        db, collab_member_client, collab_notification_other_a):
    """The boundary is per-RECIPIENT, not per-role: the owner can still clear their own row."""
    r = collab_member_client.post(
        reverse("projects:ntf_mark_read", args=[collab_notification_other_a.pk]))
    assert r.status_code == 302
    collab_notification_other_a.refresh_from_db()
    assert collab_notification_other_a.is_read is True


def test_collab_mark_all_read_never_touches_a_teammates_rows(
        db, collab_admin_client, collab_notification_unread_a, collab_notification_other_a):
    collab_admin_client.post(reverse("projects:ntf_mark_all_read"))
    collab_notification_unread_a.refresh_from_db()
    collab_notification_other_a.refresh_from_db()
    assert collab_notification_unread_a.is_read is True
    assert collab_notification_other_a.is_read is False


def test_collab_ntf_list_without_the_mine_lens_is_a_workspace_view(
        db, collab_admin_client, collab_notification_other_a):
    """The register itself is a workspace view (that is the design) — but the ACTIONS are not."""
    r = collab_admin_client.get(reverse("projects:ntf_list"))
    assert r.status_code == 200
    assert r.context["mine"] is False


# ==================================================================================================
# I1 — a crafted repoint must not strand a thread
# ==================================================================================================

def test_collab_crafted_root_repoint_is_refused(db, collab_admin_client, collab_thread_root_a,
                                                collab_channel_archived_a):
    """POST a channel change on a root that has replies — refused, replies stay visible."""
    original_channel = collab_thread_root_a.channel_id
    replies = list(collab_thread_root_a.replies.all())
    r = collab_admin_client.post(reverse("projects:msg_edit", args=[collab_thread_root_a.pk]), {
        "channel": collab_channel_archived_a.pk, "body": collab_thread_root_a.body,
        "mentions": []})
    assert r.status_code == 200  # form error, re-rendered
    collab_thread_root_a.refresh_from_db()
    assert collab_thread_root_a.channel_id == original_channel
    for reply in replies:
        reply.refresh_from_db()
        assert reply.channel_id == original_channel
    body = collab_admin_client.get(
        reverse("projects:chn_detail", args=[original_channel])).content.decode("utf-8")
    for reply in replies:
        assert reply.number in body, f"{reply.number} vanished from its channel"


# ==================================================================================================
# Mass assignment — the verb-written flags
# ==================================================================================================

def test_collab_crafted_channel_edit_cannot_archive(db, collab_admin_client, collab_channel_a):
    collab_admin_client.post(reverse("projects:chn_edit", args=[collab_channel_a.pk]), {
        "project": collab_channel_a.project_id, "name": collab_channel_a.name, "topic": "",
        "kind": "discussion", "is_archived": "on", "archived_by": "",
        "archived_at": "2020-01-01T00:00"})
    collab_channel_a.refresh_from_db()
    assert collab_channel_a.is_archived is False
    assert collab_channel_a.archived_at is None


def test_collab_crafted_share_edit_cannot_revoke_or_claim(
        db, collab_admin_client, collab_share_edit_free_a):
    collab_admin_client.post(reverse("projects:dsh_edit", args=[collab_share_edit_free_a.pk]), {
        "project": collab_share_edit_free_a.project_id, "channel": "",
        "document": collab_share_edit_free_a.document_id, "access_level": "edit",
        "shared_with": "", "note": "", "is_active": "", "claimed_by": "",
        "claimed_at": "2020-01-01T00:00", "revoked_at": "2020-01-01T00:00"})
    collab_share_edit_free_a.refresh_from_db()
    assert collab_share_edit_free_a.is_active is True
    assert collab_share_edit_free_a.claimed_by_id is None
    assert collab_share_edit_free_a.revoked_at is None


def test_collab_crafted_meeting_edit_cannot_complete_or_write_minutes(
        db, collab_admin_client, collab_meeting_scheduled_a):
    collab_admin_client.post(reverse("projects:mtg_edit", args=[collab_meeting_scheduled_a.pk]), {
        "project": collab_meeting_scheduled_a.project_id, "title": "Tampered",
        "kind": "standup", "scheduled_start": "2026-10-01T09:00",
        "scheduled_end": "2026-10-01T10:00", "location": "", "mode": "virtual",
        "recurrence": "none", "status": "completed", "minutes": "Fabricated.",
        "actual_start": "2020-01-01T00:00", "actual_end": "2020-01-01T01:00"})
    collab_meeting_scheduled_a.refresh_from_db()
    assert collab_meeting_scheduled_a.status == "scheduled"
    assert collab_meeting_scheduled_a.minutes == ""
    assert collab_meeting_scheduled_a.actual_start is None


def test_collab_crafted_message_edit_cannot_forge_the_edit_stamp(
        db, collab_admin_client, collab_message_bare_a):
    collab_admin_client.post(reverse("projects:msg_edit", args=[collab_message_bare_a.pk]), {
        "channel": collab_message_bare_a.channel_id, "body": "Tampered.",
        "mentions": [], "edited_at": "2020-01-01T00:00", "edited_by": ""})
    collab_message_bare_a.refresh_from_db()
    # The stamp IS written — but by the verb, to NOW, never to the posted value.
    assert collab_message_bare_a.edited_at is not None
    assert collab_message_bare_a.edited_at.year != 2020


def test_collab_crafted_agenda_edit_cannot_cover_itself(db, collab_admin_client,
                                                        collab_agenda_open_a):
    collab_admin_client.post(reverse("projects:agi_edit", args=[collab_agenda_open_a.pk]), {
        "title": collab_agenda_open_a.title, "presenter": "", "duration_minutes": 10,
        "sequence": 1, "is_covered": "on", "covered_at": "2020-01-01T00:00"})
    collab_agenda_open_a.refresh_from_db()
    assert collab_agenda_open_a.is_covered is False
    assert collab_agenda_open_a.covered_at is None


def test_collab_crafted_action_edit_cannot_close_itself(db, collab_admin_client,
                                                        collab_action_open_a):
    collab_admin_client.post(reverse("projects:mai_edit", args=[collab_action_open_a.pk]), {
        "description": collab_action_open_a.description, "assignee": "", "due_date": "",
        "task": "", "is_done": "on", "done_at": "2020-01-01T00:00"})
    collab_action_open_a.refresh_from_db()
    assert collab_action_open_a.is_done is False
    assert collab_action_open_a.done_at is None


# ==================================================================================================
# CSRF
# ==================================================================================================

@pytest.mark.parametrize("name,fixture", [
    ("chn_create", None), ("msg_create", None), ("dsh_create", None), ("mtg_create", None),
    ("chn_edit", "collab_channel_a"), ("dsh_edit", "collab_share_view_a"),
    ("mtg_edit", "collab_meeting_scheduled_a"), ("mtg_minutes", "collab_meeting_scheduled_a"),
    ("agi_edit", "collab_agenda_open_a"), ("mai_edit", "collab_action_open_a"),
])
def test_collab_form_pages_render_a_csrf_token(db, collab_admin_client, request, name, fixture):
    body = collab_admin_client.get(_url(name, fixture, request)).content.decode("utf-8")
    assert "csrfmiddlewaretoken" in body, f"{name} renders no CSRF token"


def test_collab_post_without_a_csrf_token_is_rejected(db, collab_csrf_client, admin_user,
                                                      collab_channel_a):
    collab_csrf_client.force_login(admin_user)
    r = collab_csrf_client.post(reverse("projects:chn_archive", args=[collab_channel_a.pk]))
    assert r.status_code == 403
    collab_channel_a.refresh_from_db()
    assert collab_channel_a.is_archived is False


# ==================================================================================================
# XSS — user-authored text must be escaped
# ==================================================================================================

_XSS = "<script>alert('xss')</script>"


def test_collab_message_body_is_escaped_on_the_channel_page(db, collab_admin_client,
                                                            collab_channel_a):
    from apps.projects.tests.conftest import _collab_message
    _collab_message(collab_channel_a.tenant, collab_channel_a, body=_XSS)
    body = collab_admin_client.get(
        reverse("projects:chn_detail", args=[collab_channel_a.pk])).content.decode("utf-8")
    assert _XSS not in body
    assert "&lt;script&gt;" in body


def test_collab_channel_topic_is_escaped_on_the_register(db, collab_admin_client,
                                                         planning_project_a):
    from apps.projects.tests.conftest import _collab_channel
    _collab_channel(planning_project_a.tenant, planning_project_a, name="XSS channel",
                    topic=_XSS)
    body = collab_admin_client.get(reverse("projects:chn_list")).content.decode("utf-8")
    assert _XSS not in body


def test_collab_meeting_title_is_escaped_on_the_register(db, collab_admin_client,
                                                         planning_project_a):
    from apps.projects.tests.conftest import _collab_meeting
    _collab_meeting(planning_project_a.tenant, planning_project_a, title=_XSS)
    body = collab_admin_client.get(reverse("projects:mtg_list")).content.decode("utf-8")
    assert _XSS not in body


def test_collab_notification_title_is_escaped_on_the_inbox(db, collab_admin_client,
                                                           planning_project_a, admin_user):
    from apps.projects.tests.conftest import _collab_notification
    _collab_notification(planning_project_a.tenant, planning_project_a, admin_user, title=_XSS)
    body = collab_admin_client.get(reverse("projects:ntf_list")).content.decode("utf-8")
    assert _XSS not in body


def test_collab_share_note_is_escaped_on_the_register(db, collab_admin_client,
                                                      planning_project_a, collab_document_a):
    from apps.projects.tests.conftest import _collab_share
    _collab_share(planning_project_a.tenant, planning_project_a, collab_document_a, note=_XSS)
    body = collab_admin_client.get(reverse("projects:dsh_list")).content.decode("utf-8")
    assert _XSS not in body


def test_collab_feed_escapes_user_authored_text(db, collab_admin_client, planning_project_a,
                                                admin_user):
    """The feed builds its labels in the VIEW — they must still be escaped by the template."""
    from apps.projects.tests.conftest import _collab_channel, _collab_message
    channel = _collab_channel(planning_project_a.tenant, planning_project_a, name="Feed XSS")
    _collab_message(planning_project_a.tenant, channel, body=_XSS)
    body = collab_admin_client.get(reverse("projects:activity_feed")).content.decode("utf-8")
    assert _XSS not in body


# ==================================================================================================
# Audit integrity — the varchar(10) column
# ==================================================================================================

def test_collab_no_audit_row_puts_a_verb_in_the_action_column(db, collab_admin_client,
                                                              collab_channel_a):
    """``AuditLog.action`` is varchar(10); a verb written there would truncate or error."""
    collab_admin_client.post(reverse("projects:chn_archive", args=[collab_channel_a.pk]))
    from apps.core.models import AuditLog
    verbs = {"chn_archive", "mtg_start", "mtg_complete", "mtg_cancel", "mtg_minutes",
             "agi_cover", "mai_toggle", "dsh_claim", "dsh_release", "dsh_revoke",
             "ntf_mark_read", "ntf_mark_all_read", "msg_edit"}
    assert not AuditLog.objects.filter(action__in=verbs).exists()
    assert AuditLog.objects.filter(action="update", changes__verb="chn_archive").exists()
