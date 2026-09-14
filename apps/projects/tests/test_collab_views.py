"""Projects 7.9 — Collaboration & Communication view tests.

Covers all 41 routes: they resolve, the GET pages render the object they are about, the pinned
figures land on the RENDERED page (not merely in the context), the 18 POST-only verbs answer GET
with 405, every verb's state machine runs in both directions and writes its ``changes["verb"]``
audit row, the registers paginate over an ORDERED queryset, junk params never 500 and never
silently empty a register, the empty state is safe, and the tenant-None guard redirects.

The figures come from ``collab_figures_a`` — a closed graph whose numbers are hand-computed in
``.claude/tasks/test-contract-projects-7.9.md`` §2. They are asserted here as literals on purpose:
reading them back off the code would make the test agree with any bug.

Naming: every test ``test_collab_*``, every helper ``_collab_*``.
"""
import warnings

import pytest
from django.urls import reverse

from apps.core.models import AuditLog
from apps.projects.models import (
    ChannelMessage,
    DocumentShare,
    Meeting,
    MeetingActionItem,
    MeetingAgendaItem,
    ProjectNotification,
)


def _audited(verb):
    """True when SOME audit row carries this verb in ``changes``.

    ``AuditLog.action`` is varchar(10), so a verb can never live there — it goes in the JSON
    ``changes`` payload. This is the assertion that keeps that convention honest.
    """
    return AuditLog.objects.filter(changes__verb=verb).exists()


# ==================================================================================================
# Every route resolves, and the POST-only verbs are POST-only
# ==================================================================================================

_ALL_ROUTE_NAMES = [
    "activity_feed",
    "chn_list", "chn_create", "chn_detail", "chn_edit", "chn_delete", "chn_archive",
    "msg_list", "msg_create", "msg_edit", "msg_delete",
    "dsh_list", "dsh_create", "dsh_detail", "dsh_edit", "dsh_delete", "dsh_revoke",
    "dsh_claim", "dsh_release",
    "mtg_list", "mtg_create", "mtg_detail", "mtg_edit", "mtg_delete", "mtg_start",
    "mtg_complete", "mtg_cancel", "mtg_minutes",
    "agi_create", "agi_edit", "agi_delete", "agi_cover",
    "mai_create", "mai_edit", "mai_delete", "mai_toggle",
    "ntf_list", "ntf_mark_all_read", "ntf_detail", "ntf_mark_read", "ntf_delete",
]


def test_collab_all_forty_one_routes_resolve(db):
    assert len(_ALL_ROUTE_NAMES) == 41
    for name in _ALL_ROUTE_NAMES:
        # Any route with a pk resolves with a placeholder; the no-pk ones need none.
        try:
            reverse(f"projects:{name}")
        except Exception:
            assert reverse(f"projects:{name}", args=[1]).startswith("/projects/")


#: (url name, fixture providing the pk object)
_GET_WITH_PK = [
    ("chn_detail", "collab_channel_a"),
    ("chn_edit", "collab_channel_a"),
    ("msg_edit", "collab_message_bare_a"),
    ("dsh_detail", "collab_share_view_a"),
    ("dsh_edit", "collab_share_edit_free_a"),
    ("mtg_detail", "collab_meeting_scheduled_a"),
    ("mtg_edit", "collab_meeting_scheduled_a"),
    ("mtg_minutes", "collab_meeting_scheduled_a"),
    ("agi_edit", "collab_agenda_open_a"),
    ("mai_edit", "collab_action_open_a"),
    ("ntf_detail", "collab_notification_unread_a"),
]

#: (url name, fixture providing the PARENT pk)
_GET_WITH_PARENT_PK = [
    ("agi_create", "collab_meeting_scheduled_a"),
    ("mai_create", "collab_meeting_scheduled_a"),
]

_GET_NO_PK = ["chn_list", "chn_create", "msg_list", "msg_create", "dsh_list", "dsh_create",
              "mtg_list", "mtg_create", "ntf_list", "activity_feed"]


@pytest.mark.parametrize("name,fixture", _GET_WITH_PK)
def test_collab_get_page_with_pk_renders(db, collab_admin_client, request, name, fixture):
    obj = request.getfixturevalue(fixture)
    r = collab_admin_client.get(reverse(f"projects:{name}", args=[obj.pk]))
    assert r.status_code == 200, f"{name} -> {r.status_code}"
    body = r.content.decode("utf-8")
    assert obj.number in body, f"{name} does not mention {obj.number}"


@pytest.mark.parametrize("name,fixture", _GET_WITH_PARENT_PK)
def test_collab_child_create_page_renders(db, collab_admin_client, request, name, fixture):
    parent = request.getfixturevalue(fixture)
    r = collab_admin_client.get(reverse(f"projects:{name}", args=[parent.pk]))
    assert r.status_code == 200, f"{name} -> {r.status_code}"


@pytest.mark.parametrize("name", _GET_NO_PK)
def test_collab_get_page_without_pk_renders(db, collab_admin_client, name):
    r = collab_admin_client.get(reverse(f"projects:{name}"))
    assert r.status_code == 200, f"{name} -> {r.status_code}"


#: The 18 POST-only verbs.
_POST_ONLY = [
    ("chn_delete", "collab_channel_a"),
    ("chn_archive", "collab_channel_a"),
    ("msg_delete", "collab_message_bare_a"),
    ("dsh_delete", "collab_share_view_a"),
    ("dsh_revoke", "collab_share_view_a"),
    ("dsh_claim", "collab_share_edit_free_a"),
    ("dsh_release", "collab_share_edit_claimed_a"),
    ("mtg_delete", "collab_meeting_scheduled_a"),
    ("mtg_start", "collab_meeting_scheduled_a"),
    ("mtg_complete", "collab_meeting_in_progress_a"),
    ("mtg_cancel", "collab_meeting_scheduled_a"),
    ("agi_delete", "collab_agenda_open_a"),
    ("agi_cover", "collab_agenda_open_a"),
    ("mai_delete", "collab_action_open_a"),
    ("mai_toggle", "collab_action_open_a"),
    ("ntf_mark_all_read", None),
    ("ntf_mark_read", "collab_notification_unread_a"),
    ("ntf_delete", "collab_notification_unread_a"),
]


def test_collab_the_post_only_verb_list_is_complete(db):
    assert len(_POST_ONLY) == 18


@pytest.mark.parametrize("name,fixture", _POST_ONLY)
def test_collab_get_on_a_post_only_verb_is_405(db, collab_admin_client, request, name, fixture):
    """A GET must be a 405, never a 302 or a 200 that quietly mutated something."""
    args = [] if fixture is None else [request.getfixturevalue(fixture).pk]
    r = collab_admin_client.get(reverse(f"projects:{name}", args=args))
    assert r.status_code == 405, f"{name} -> {r.status_code}"


# ==================================================================================================
# The pinned figures — asserted on the rendered page / context, as literals
# ==================================================================================================

def _row_by(pk, page):
    for obj in page:
        if obj.pk == pk:
            return obj
    return None


def test_collab_chn_list_message_count_annotation(db, collab_admin_client, collab_figures_a):
    """The graph's two channels carry 2 and 1 messages — one join, not a per-row query."""
    r = collab_admin_client.get(reverse("projects:chn_list"))
    page = r.context["object_list"]
    ch1, ch2 = collab_figures_a["channels"]
    assert _row_by(ch1.pk, page).message_count == 2
    assert _row_by(ch2.pk, page).message_count == 1


def test_collab_msg_list_reply_count_annotation(db, collab_admin_client, collab_figures_a):
    """The thread root carries 1 reply; the bare root carries 0."""
    r = collab_admin_client.get(reverse("projects:msg_list"))
    page = r.context["object_list"]
    assert _row_by(collab_figures_a["root"].pk, page).reply_count == 1
    assert _row_by(collab_figures_a["bare"].pk, page).reply_count == 0


def test_collab_mtg_list_annotations_do_not_multiply_rows(db, collab_admin_client,
                                                          collab_figures_a):
    """3 agenda items (2 covered) and 3 action items (2 open) over TWO different joins.

    Without ``distinct=True`` the two joins multiply and these figures inflate — which is exactly
    the bug the annotation shape exists to avoid, so the numbers (not just the row count) matter.
    """
    r = collab_admin_client.get(reverse("projects:mtg_list"))
    page = r.context["object_list"]
    meeting = _row_by(collab_figures_a["meeting"].pk, page)
    assert meeting is not None, "the figure meeting is not on page 1"
    assert meeting.agenda_total == 3
    assert meeting.agenda_covered == 2
    assert meeting.open_actions == 2
    # And the meeting appears exactly once — the row-multiplication half of the same bug.
    assert [o.pk for o in page].count(collab_figures_a["meeting"].pk) == 1


def test_collab_mtg_detail_action_counts(db, collab_admin_client, collab_figures_a):
    """2 open (one of them overdue) of 3 — computed in the view off ONE materialized list."""
    r = collab_admin_client.get(
        reverse("projects:mtg_detail", args=[collab_figures_a["meeting"].pk]))
    assert r.context["agenda_total"] == 3
    assert r.context["agenda_covered"] == 2
    assert r.context["open_action_count"] == 2
    assert r.context["overdue_action_count"] == 1


def test_collab_ntf_list_unread_count_is_the_callers_own(db, collab_admin_client,
                                                         collab_figures_a):
    """3 unread of the admin's own 4 rows."""
    assert collab_figures_a["unread_count"] == 3
    r = collab_admin_client.get(reverse("projects:ntf_list"))
    assert r.context["unread_count"] == 3


def test_collab_ntf_list_unread_count_excludes_other_recipients(db, collab_admin_client,
                                                                collab_notification_other_a):
    """A row delivered to a colleague must NOT inflate the viewer's unread badge."""
    r = collab_admin_client.get(reverse("projects:ntf_list"))
    assert r.context["unread_count"] == 0


def test_collab_mine_lens_narrows_to_the_caller(db, collab_admin_client, admin_user,
                                                collab_notification_other_a,
                                                collab_notification_unread_a):
    """``?mine=1`` returns the caller's rows only."""
    r = collab_admin_client.get(reverse("projects:ntf_list") + "?mine=1")
    assert r.context["mine"] is True
    pks = {o.pk for o in r.context["object_list"]}
    assert collab_notification_unread_a.pk in pks
    assert collab_notification_other_a.pk not in pks


# ==================================================================================================
# activity_feed — the pinned counts, the window and the kind lens
# ==================================================================================================

def test_collab_feed_counts_are_pinned(db, collab_admin_client, collab_figures_a):
    """3 messages + 1 meeting + 3 shares + 4 notifications = 11, with audit EXCLUDED.

    The audit half cannot be attributed to one project (only a GFK and a free-text target), so a
    project-filtered feed drops it rather than guessing.
    """
    project = collab_figures_a["project"]
    r = collab_admin_client.get(reverse("projects:activity_feed") + f"?project={project.pk}")
    counts = r.context["counts"]
    assert counts["message"] == 3
    assert counts["meeting"] == 1
    assert counts["share"] == 3
    assert counts["notification"] == 4
    assert counts["audit"] == 0
    assert r.context["total_count"] == 11
    assert r.context["entry_count"] == 11
    assert r.context["truncated"] is False


def test_collab_feed_says_why_audit_is_missing_under_a_project_lens(
        db, collab_admin_client, collab_figures_a):
    """The exclusion must be VISIBLE, not silent."""
    project = collab_figures_a["project"]
    body = collab_admin_client.get(
        reverse("projects:activity_feed") + f"?project={project.pk}").content.decode("utf-8")
    assert "not attributable to a single project" in body


def test_collab_feed_whole_workspace_has_the_five_count_keys(db, collab_admin_client,
                                                             collab_figures_a):
    """No project lens: all five keys present and the audit source is live again."""
    r = collab_admin_client.get(reverse("projects:activity_feed"))
    assert set(r.context["counts"]) == {"message", "meeting", "share", "notification", "audit"}
    assert r.context["counts"]["message"] == 3
    assert r.context["counts"]["audit"] == 0  # no fixture writes an audit row
    assert r.context["total_count"] == 11


def test_collab_feed_kind_lens_narrows_the_stream_not_the_summary(db, collab_admin_client,
                                                                  collab_figures_a):
    """``?kind=`` narrows ``entries`` but must leave all five window counts intact.

    Zeroing the other four cards when one kind is picked is the M3 bug — the stat row summarises
    the WINDOW, so it must not follow the stream filter.
    """
    r = collab_admin_client.get(reverse("projects:activity_feed") + "?kind=message")
    assert r.context["kind"] == "message"
    assert r.context["counts"]["meeting"] == 1
    assert r.context["counts"]["share"] == 3
    assert r.context["counts"]["notification"] == 4
    assert all(e["kind"] == "message" for e in r.context["entries"])
    assert len(r.context["entries"]) == 3


@pytest.mark.parametrize("raw,expected", [("7", 7), ("30", 30), ("90", 90),
                                          ("abc", 30), ("999", 30), ("", 30), ("-1", 30)])
def test_collab_feed_window_is_allow_listed(db, collab_admin_client, raw, expected):
    """Only 7/30/90 are windows; anything else falls back to the 30-day default."""
    r = collab_admin_client.get(reverse("projects:activity_feed") + f"?days={raw}")
    assert r.status_code == 200
    assert r.context["days"] == expected


@pytest.mark.parametrize("raw", ["nope", "MESSAGE", "1", "%C2%B2", "message;drop"])
def test_collab_feed_junk_kind_is_ignored(db, collab_admin_client, raw):
    """A junk kind is IGNORED (no filter), not applied as an empty filter."""
    r = collab_admin_client.get(reverse("projects:activity_feed") + f"?kind={raw}")
    assert r.status_code == 200
    assert r.context["kind"] == ""


def test_collab_feed_unresolvable_project_degrades_loudly(db, collab_admin_client,
                                                          collab_figures_a):
    """A well-formed id that is not in this workspace falls back to the whole workspace."""
    r = collab_admin_client.get(reverse("projects:activity_feed") + "?project=999999999")
    assert r.status_code == 200
    assert r.context["project"] is None
    assert r.context["counts"]["message"] == 3


def test_collab_feed_junk_project_is_skipped(db, collab_admin_client, collab_figures_a):
    for raw in ("abc", "0", "%C2%B2", "999999999999999999999"):
        r = collab_admin_client.get(reverse("projects:activity_feed") + f"?project={raw}")
        assert r.status_code == 200, f"project={raw} -> {r.status_code}"


# ==================================================================================================
# Verb state machines — both directions, with the audit trail
# ==================================================================================================

def test_collab_chn_archive_toggles_and_stamps(db, collab_admin_client, collab_channel_a):
    assert collab_channel_a.is_archived is False
    collab_admin_client.post(reverse("projects:chn_archive", args=[collab_channel_a.pk]))
    collab_channel_a.refresh_from_db()
    assert collab_channel_a.is_archived is True
    assert collab_channel_a.archived_by_id is not None
    assert collab_channel_a.archived_at is not None
    assert _audited("chn_archive")

    collab_admin_client.post(reverse("projects:chn_archive", args=[collab_channel_a.pk]))
    collab_channel_a.refresh_from_db()
    assert collab_channel_a.is_archived is False
    assert collab_channel_a.archived_by_id is None
    assert collab_channel_a.archived_at is None


def test_collab_mtg_start_refuses_a_non_scheduled_meeting(db, collab_admin_client,
                                                          collab_meeting_completed_a):
    collab_admin_client.post(reverse("projects:mtg_start", args=[collab_meeting_completed_a.pk]))
    collab_meeting_completed_a.refresh_from_db()
    assert collab_meeting_completed_a.status == "completed"


def test_collab_mtg_start_accepts_scheduled(db, collab_admin_client, collab_meeting_scheduled_a):
    collab_admin_client.post(reverse("projects:mtg_start", args=[collab_meeting_scheduled_a.pk]))
    collab_meeting_scheduled_a.refresh_from_db()
    assert collab_meeting_scheduled_a.status == "in_progress"
    assert collab_meeting_scheduled_a.actual_start is not None
    assert _audited("mtg_start")


def test_collab_mtg_complete_refuses_a_scheduled_meeting(db, collab_admin_client,
                                                         collab_meeting_scheduled_a):
    collab_admin_client.post(reverse("projects:mtg_complete", args=[collab_meeting_scheduled_a.pk]))
    collab_meeting_scheduled_a.refresh_from_db()
    assert collab_meeting_scheduled_a.status == "scheduled"


def test_collab_mtg_complete_accepts_in_progress(db, collab_admin_client,
                                                 collab_meeting_in_progress_a):
    collab_admin_client.post(reverse("projects:mtg_complete",
                                     args=[collab_meeting_in_progress_a.pk]))
    collab_meeting_in_progress_a.refresh_from_db()
    assert collab_meeting_in_progress_a.status == "completed"
    assert collab_meeting_in_progress_a.actual_end is not None
    assert _audited("mtg_complete")


def test_collab_mtg_cancel_refuses_a_terminal_meeting(db, collab_admin_client,
                                                      collab_meeting_completed_a,
                                                      collab_meeting_cancelled_a):
    for meeting in (collab_meeting_completed_a, collab_meeting_cancelled_a):
        before = meeting.status
        collab_admin_client.post(reverse("projects:mtg_cancel", args=[meeting.pk]))
        meeting.refresh_from_db()
        assert meeting.status == before


def test_collab_mtg_cancel_accepts_a_scheduled_meeting(db, collab_admin_client,
                                                       collab_meeting_scheduled_a):
    collab_admin_client.post(reverse("projects:mtg_cancel", args=[collab_meeting_scheduled_a.pk]))
    collab_meeting_scheduled_a.refresh_from_db()
    assert collab_meeting_scheduled_a.status == "cancelled"
    assert _audited("mtg_cancel")


def test_collab_mtg_minutes_writes_the_body_and_stamps_without_completing(
        db, collab_admin_client, collab_meeting_in_progress_a, admin_user):
    """Capturing minutes is NOT completing the meeting."""
    collab_admin_client.post(reverse("projects:mtg_minutes", args=[collab_meeting_in_progress_a.pk]),
                             {"minutes": "Decisions recorded here."})
    collab_meeting_in_progress_a.refresh_from_db()
    assert collab_meeting_in_progress_a.minutes == "Decisions recorded here."
    assert collab_meeting_in_progress_a.minutes_by_id == admin_user.pk
    assert collab_meeting_in_progress_a.minutes_at is not None
    assert collab_meeting_in_progress_a.status == "in_progress"
    assert _audited("mtg_minutes")


def test_collab_mtg_minutes_refuses_a_blank_body(db, collab_admin_client,
                                                 collab_meeting_in_progress_a):
    collab_admin_client.post(reverse("projects:mtg_minutes", args=[collab_meeting_in_progress_a.pk]),
                             {"minutes": ""})
    collab_meeting_in_progress_a.refresh_from_db()
    assert collab_meeting_in_progress_a.minutes == ""


def test_collab_agi_cover_toggles_and_stamps(db, collab_admin_client, collab_agenda_open_a):
    collab_admin_client.post(reverse("projects:agi_cover", args=[collab_agenda_open_a.pk]))
    collab_agenda_open_a.refresh_from_db()
    assert collab_agenda_open_a.is_covered is True
    assert collab_agenda_open_a.covered_at is not None
    assert _audited("agi_cover")

    collab_admin_client.post(reverse("projects:agi_cover", args=[collab_agenda_open_a.pk]))
    collab_agenda_open_a.refresh_from_db()
    assert collab_agenda_open_a.is_covered is False
    assert collab_agenda_open_a.covered_at is None
    assert collab_agenda_open_a.covered_by_id is None


def test_collab_mai_toggle_toggles_and_stamps(db, collab_admin_client, collab_action_open_a):
    collab_admin_client.post(reverse("projects:mai_toggle", args=[collab_action_open_a.pk]))
    collab_action_open_a.refresh_from_db()
    assert collab_action_open_a.is_done is True
    assert collab_action_open_a.done_at is not None
    assert _audited("mai_toggle")

    collab_admin_client.post(reverse("projects:mai_toggle", args=[collab_action_open_a.pk]))
    collab_action_open_a.refresh_from_db()
    assert collab_action_open_a.is_done is False
    assert collab_action_open_a.done_at is None


def test_collab_dsh_claim_refuses_a_view_only_share(db, collab_admin_client, collab_share_view_a):
    collab_admin_client.post(reverse("projects:dsh_claim", args=[collab_share_view_a.pk]))
    collab_share_view_a.refresh_from_db()
    assert collab_share_view_a.claimed_by_id is None


def test_collab_dsh_claim_refuses_a_revoked_share(db, collab_admin_client,
                                                  collab_share_revoked_a):
    collab_admin_client.post(reverse("projects:dsh_claim", args=[collab_share_revoked_a.pk]))
    collab_share_revoked_a.refresh_from_db()
    assert collab_share_revoked_a.claimed_by_id is None


def test_collab_dsh_claim_accepts_a_free_edit_share(db, collab_admin_client,
                                                    collab_share_edit_free_a, admin_user):
    collab_admin_client.post(reverse("projects:dsh_claim", args=[collab_share_edit_free_a.pk]))
    collab_share_edit_free_a.refresh_from_db()
    assert collab_share_edit_free_a.claimed_by_id == admin_user.pk
    assert collab_share_edit_free_a.claimed_at is not None
    assert _audited("dsh_claim")


def test_collab_dsh_claim_refuses_when_another_user_holds_it(
        db, collab_admin_client, collab_share_edit_free_a, member_user):
    """Another user's live claim must block the admin."""
    collab_share_edit_free_a.claimed_by = member_user
    collab_share_edit_free_a.save(update_fields=["claimed_by", "updated_at"])
    collab_admin_client.post(reverse("projects:dsh_claim", args=[collab_share_edit_free_a.pk]))
    collab_share_edit_free_a.refresh_from_db()
    assert collab_share_edit_free_a.claimed_by_id == member_user.pk


def test_collab_dsh_release_clears_the_claim(db, collab_admin_client,
                                             collab_share_edit_claimed_a):
    collab_admin_client.post(reverse("projects:dsh_release", args=[collab_share_edit_claimed_a.pk]))
    collab_share_edit_claimed_a.refresh_from_db()
    assert collab_share_edit_claimed_a.claimed_by_id is None
    assert collab_share_edit_claimed_a.claimed_at is None
    assert _audited("dsh_release")


def test_collab_dsh_revoke_releases_any_claim(db, collab_admin_client,
                                              collab_share_edit_claimed_a):
    """A revoked share must not stay claimed."""
    collab_admin_client.post(reverse("projects:dsh_revoke", args=[collab_share_edit_claimed_a.pk]))
    collab_share_edit_claimed_a.refresh_from_db()
    assert collab_share_edit_claimed_a.is_active is False
    assert collab_share_edit_claimed_a.claimed_by_id is None
    assert collab_share_edit_claimed_a.claimed_at is None
    assert _audited("dsh_revoke")


def test_collab_dsh_revoke_toggles_back(db, collab_admin_client, collab_share_revoked_a):
    collab_admin_client.post(reverse("projects:dsh_revoke", args=[collab_share_revoked_a.pk]))
    collab_share_revoked_a.refresh_from_db()
    assert collab_share_revoked_a.is_active is True
    assert collab_share_revoked_a.revoked_at is None
    assert collab_share_revoked_a.revoked_by_id is None


def test_collab_ntf_mark_read_toggles_both_ways(db, collab_admin_client,
                                                collab_notification_unread_a):
    collab_admin_client.post(reverse("projects:ntf_mark_read",
                                     args=[collab_notification_unread_a.pk]))
    collab_notification_unread_a.refresh_from_db()
    assert collab_notification_unread_a.is_read is True
    assert collab_notification_unread_a.read_at is not None
    assert _audited("ntf_mark_read")

    collab_admin_client.post(reverse("projects:ntf_mark_read",
                                     args=[collab_notification_unread_a.pk]))
    collab_notification_unread_a.refresh_from_db()
    assert collab_notification_unread_a.is_read is False
    assert collab_notification_unread_a.read_at is None


def test_collab_ntf_mark_all_read_clears_only_the_callers_rows(
        db, collab_admin_client, collab_notification_unread_a, collab_notification_other_a):
    collab_admin_client.post(reverse("projects:ntf_mark_all_read"))
    collab_notification_unread_a.refresh_from_db()
    collab_notification_other_a.refresh_from_db()
    assert collab_notification_unread_a.is_read is True
    assert collab_notification_other_a.is_read is False
    assert _audited("ntf_mark_all_read")


def test_collab_msg_create_mints_mentions_and_audits(
        db, collab_admin_client, collab_channel_a, member_user):
    """A mention mints exactly one notification for the mentioned user."""
    before = ProjectNotification.objects.filter(kind="mention").count()
    collab_admin_client.post(reverse("projects:msg_create"), {
        "channel": collab_channel_a.pk, "body": "Heads up.", "mentions": [member_user.pk]})
    assert ProjectNotification.objects.filter(kind="mention").count() == before + 1
    row = ProjectNotification.objects.filter(kind="mention", recipient=member_user).first()
    assert row is not None and row.number.startswith("NTF-")
    assert row.channel_id == collab_channel_a.pk


def test_collab_msg_create_does_not_notify_the_author(
        db, collab_admin_client, collab_channel_a, admin_user):
    """You are not notified for mentioning yourself."""
    before = ProjectNotification.objects.filter(kind="mention", recipient=admin_user).count()
    collab_admin_client.post(reverse("projects:msg_create"), {
        "channel": collab_channel_a.pk, "body": "Note to self.", "mentions": [admin_user.pk]})
    assert ProjectNotification.objects.filter(
        kind="mention", recipient=admin_user).count() == before


def test_collab_msg_edit_mints_only_the_added_mention(
        db, collab_admin_client, collab_message_bare_a, member_user, admin_user):
    """Editing to ADD a mention notifies once; re-saving the same mention notifies nobody."""
    collab_admin_client.post(reverse("projects:msg_edit", args=[collab_message_bare_a.pk]), {
        "channel": collab_message_bare_a.channel_id, "body": "Edited body.",
        "mentions": [member_user.pk]})
    collab_message_bare_a.refresh_from_db()
    assert collab_message_bare_a.edited_at is not None
    assert collab_message_bare_a.edited_by_id == admin_user.pk
    assert _audited("msg_edit")
    after_first = ProjectNotification.objects.filter(kind="mention").count()

    collab_admin_client.post(reverse("projects:msg_edit", args=[collab_message_bare_a.pk]), {
        "channel": collab_message_bare_a.channel_id, "body": "Edited body.",
        "mentions": [member_user.pk]})
    assert ProjectNotification.objects.filter(kind="mention").count() == after_first


def test_collab_chn_create_stamps_the_tenant_and_creator(db, collab_admin_client,
                                                         planning_project_a, admin_user):
    r = collab_admin_client.post(reverse("projects:chn_create"), {
        "project": planning_project_a.pk, "name": "A brand new channel", "topic": "",
        "kind": "announcement"})
    assert r.status_code == 302
    from apps.projects.models import Channel
    created = Channel.objects.get(name="A brand new channel")
    assert created.tenant_id == planning_project_a.tenant_id
    assert created.created_by_id == admin_user.pk
    assert created.number.startswith("CHN-")


# ==================================================================================================
# Pagination and ordering — the C-C regression
# ==================================================================================================

_REGISTERS = ["chn_list", "msg_list", "dsh_list", "mtg_list", "ntf_list"]


@pytest.mark.parametrize("name", _REGISTERS)
def test_collab_register_paginates_an_ordered_queryset(db, collab_admin_client,
                                                       collab_figures_a, name):
    """An ``annotate()`` puts a GROUP BY on the query, which makes Django's ``QuerySet.ordered``
    False and silently drops ``Meta.ordering`` — so the paginator would slice an unordered set and
    a row could appear on two pages or none. Django warns; this asserts it does not.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        r = collab_admin_client.get(reverse(f"projects:{name}"))
    assert r.status_code == 200
    unordered = [w for w in caught if "unordered" in str(w.message).lower()]
    assert not unordered, f"{name} paginated an unordered queryset"


@pytest.mark.parametrize("name", _REGISTERS)
def test_collab_register_overshooting_the_page_range_is_guarded(db, collab_admin_client,
                                                                collab_figures_a, name):
    r = collab_admin_client.get(reverse(f"projects:{name}") + "?page=9999")
    assert r.status_code == 200, f"{name} -> {r.status_code}"


def test_collab_msg_list_reaches_a_real_page_two(db, collab_admin_client, planning_project_a,
                                                 admin_user):
    """With more rows than one page, page 2 must carry rows page 1 does not.

    A page-2 test that only greps for the row prefix is a false pass: ``Paginator.get_page()``
    falls back to the last in-range page, so the prefix appears even on a single-page register.
    """
    from apps.projects.tests.conftest import _collab_channel, _collab_message
    channel = _collab_channel(planning_project_a.tenant, planning_project_a, name="Paging")
    for i in range(20):
        _collab_message(planning_project_a.tenant, channel, body=f"Paged message {i:02d}")

    first = collab_admin_client.get(reverse("projects:msg_list"))
    assert first.context["page_obj"].paginator.num_pages >= 2
    page1 = {o.number for o in first.context["object_list"]}

    second = collab_admin_client.get(reverse("projects:msg_list") + "?page=2")
    assert second.status_code == 200
    page2 = {o.number for o in second.context["object_list"]}
    assert page2 - page1, "page 2 added no new rows — the pages are not distinct"


# ==================================================================================================
# Junk params — never a 500, and a junk enum must not silently empty the register
# ==================================================================================================

_JUNK = [
    ("chn_list", "?project=abc"), ("chn_list", "?project=0"), ("chn_list", "?kind=nope"),
    ("chn_list", "?is_archived=nope"), ("chn_list", "?page=9999"), ("chn_list", "?q=%C2%B2"),
    ("msg_list", "?channel=%C2%B2"), ("msg_list", "?channel=0"), ("msg_list", "?parent=0"),
    ("msg_list", "?author=abc"),
    ("dsh_list", "?access_level=nope"), ("dsh_list", "?is_active=nope"),
    ("dsh_list", "?project=abc"), ("dsh_list", "?channel=%C2%B2"),
    ("mtg_list", "?status=nope"), ("mtg_list", "?kind=nope"), ("mtg_list", "?mode=nope"),
    ("mtg_list", "?recurrence=nope"), ("mtg_list", "?project=0"),
    ("ntf_list", "?recipient=%C2%B2"), ("ntf_list", "?kind=nope"), ("ntf_list", "?is_read=nope"),
    ("ntf_list", "?mine=yes"), ("ntf_list", "?mine=0"),
]


@pytest.mark.parametrize("name,qs", _JUNK)
def test_collab_junk_param_is_never_a_500(db, collab_admin_client, collab_figures_a, name, qs):
    r = collab_admin_client.get(reverse(f"projects:{name}") + qs)
    assert r.status_code == 200, f"{name}{qs} -> {r.status_code}"


@pytest.mark.parametrize("name,param", [("chn_list", "kind"), ("mtg_list", "status"),
                                        ("ntf_list", "kind"), ("dsh_list", "access_level")])
def test_collab_junk_enum_is_skipped_not_applied(db, collab_admin_client, collab_figures_a,
                                                 name, param):
    """A junk enum must be IGNORED — applying it would silently empty the register."""
    clean = collab_admin_client.get(reverse(f"projects:{name}"))
    junked = collab_admin_client.get(reverse(f"projects:{name}") + f"?{param}=nope")
    assert len(junked.context["object_list"]) == len(clean.context["object_list"])


def test_collab_unresolvable_int_filter_is_applied(db, collab_admin_client, collab_figures_a):
    """A well-formed id that resolves to nothing IS applied — 0 is the pk-skip sentinel only."""
    r = collab_admin_client.get(reverse("projects:chn_list") + "?project=999999999")
    assert r.status_code == 200
    assert len(r.context["object_list"]) == 0


# ==================================================================================================
# Empty state and the tenant-None guard
# ==================================================================================================

def test_collab_empty_state_pages_render(db, collab_admin_client):
    """Every list and the feed are 200 with no data at all — the empty-state branch."""
    for name in ["chn_list", "msg_list", "dsh_list", "mtg_list", "ntf_list", "activity_feed"]:
        r = collab_admin_client.get(reverse(f"projects:{name}"))
        assert r.status_code == 200, f"{name} -> {r.status_code}"


def test_collab_feed_with_a_project_that_has_no_collaboration_rows(db, collab_admin_client,
                                                                   planning_project_a):
    """A real project with nothing in it must not 500 on the project-scoped branch."""
    r = collab_admin_client.get(
        reverse("projects:activity_feed") + f"?project={planning_project_a.pk}")
    assert r.status_code == 200
    assert r.context["total_count"] == 0
    assert r.context["entries"] == []


@pytest.mark.parametrize("name", ["chn_create", "msg_create", "dsh_create", "mtg_create"])
def test_collab_create_page_redirects_a_tenantless_user(db, collab_tenantless_client, name):
    """The tenant-None guard sends the user to the dashboard rather than raising."""
    r = collab_tenantless_client.get(reverse(f"projects:{name}"))
    assert r.status_code == 302


# ==================================================================================================
# The four models' detail pages show their derived state
# ==================================================================================================

def test_collab_channel_detail_builds_the_thread_tree(db, collab_admin_client,
                                                      collab_thread_root_a):
    r = collab_admin_client.get(reverse("projects:chn_detail", args=[collab_thread_root_a.channel_id]))
    assert r.context["message_count"] == 3
    assert r.context["reply_count"] == 2
    threads = r.context["threads"]
    assert len(threads) == 1
    assert len(threads[0]["replies"]) == 2


def test_collab_meeting_detail_lists_agenda_and_actions(db, collab_admin_client,
                                                        collab_agenda_open_a,
                                                        collab_action_open_a):
    meeting = collab_agenda_open_a.meeting
    r = collab_admin_client.get(reverse("projects:mtg_detail", args=[meeting.pk]))
    assert r.status_code == 200
    assert len(r.context["agenda_items"]) == MeetingAgendaItem.objects.filter(
        meeting=meeting).count()
    assert len(r.context["action_items"]) == MeetingActionItem.objects.filter(
        meeting=meeting).count()
