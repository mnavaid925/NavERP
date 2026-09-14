"""Projects 7.9 — Collaboration & Communication model tests.

7.9 adds five entity files carrying SEVEN tables: ``Channel`` [CHN-], ``ChannelMessage`` [CHM-],
``DocumentShare`` [DSH-], ``Meeting`` [MTG-] + its two children ``MeetingAgendaItem`` [AGI-] and
``MeetingActionItem`` [MAIT-], and ``ProjectNotification`` [NTF-]. These tests pin the model
surface the views and forms present to the user: the numbering, the two ``clean()`` invariants, the
``unique_together`` constraints, the derived properties, and the declared ordering/indexes.

The prefix pair worth remembering: ``MSG`` is taken by ``scm.IntegrationMessage`` and ``MAI`` by
``hrm.MeetingActionItem`` (a 1-on-1 action item in another app) — which is why this module's
message and meeting-action prefixes are ``CHM`` and ``MAIT``. Both are pinned below so a future
"tidy-up" cannot quietly collide with them.

Naming: every test ``test_collab_*``, every helper ``_collab_*``.
"""
import datetime

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.projects.models import (
    Channel,
    ChannelMessage,
    DocumentShare,
    Meeting,
    MeetingActionItem,
    MeetingAgendaItem,
    ProjectNotification,
)
from apps.projects.tests.conftest import (
    _collab_action,
    _collab_agenda,
    _collab_channel,
    _collab_meeting,
    _collab_message,
    _collab_notification,
    _collab_share,
)

_MODELS = [
    (Channel, "CHN"),
    (ChannelMessage, "CHM"),
    (DocumentShare, "DSH"),
    (Meeting, "MTG"),
    (MeetingAgendaItem, "AGI"),
    (MeetingActionItem, "MAIT"),
    (ProjectNotification, "NTF"),
]


# ==================================================================================================
# Numbering — the prefix is the model's identity in the UI
# ==================================================================================================

@pytest.mark.parametrize("model,prefix", _MODELS)
def test_collab_number_prefix_is_pinned(db, model, prefix):
    """Each model declares exactly the prefix the contract reserved."""
    assert model.NUMBER_PREFIX == prefix


def test_collab_no_model_reuses_the_taken_msg_or_mai_prefix(db):
    """``MSG`` belongs to ``scm.IntegrationMessage`` and ``MAI`` to ``hrm.MeetingActionItem``.

    Reusing either would be a silent cross-app collision in every list page's numbering.
    """
    prefixes = {model.NUMBER_PREFIX for model, _ in _MODELS}
    assert "MSG" not in prefixes
    assert "MAI" not in prefixes


def test_collab_channel_mints_a_chn_number(db, collab_channel_a):
    assert collab_channel_a.number.startswith("CHN-")


def test_collab_message_mints_a_chm_number(db, collab_message_bare_a):
    assert collab_message_bare_a.number.startswith("CHM-")


def test_collab_share_mints_a_dsh_number(db, collab_share_view_a):
    assert collab_share_view_a.number.startswith("DSH-")


def test_collab_meeting_mints_a_mtg_number(db, collab_meeting_scheduled_a):
    assert collab_meeting_scheduled_a.number.startswith("MTG-")


def test_collab_agenda_item_mints_an_agi_number(db, collab_agenda_open_a):
    assert collab_agenda_open_a.number.startswith("AGI-")


def test_collab_action_item_mints_a_mait_number(db, collab_action_open_a):
    assert collab_action_open_a.number.startswith("MAIT-")


def test_collab_notification_mints_an_ntf_number(db, collab_notification_unread_a):
    assert collab_notification_unread_a.number.startswith("NTF-")


def test_collab_numbers_are_per_tenant_not_global(db, tenant_a, tenant_b,
                                                  planning_project_a, planning_project_b):
    """Each tenant's first channel is 00001 — the sequence is tenant-scoped, not global."""
    a = _collab_channel(tenant_a, planning_project_a, name="Per-tenant A")
    b = _collab_channel(tenant_b, planning_project_b, name="Per-tenant B")
    assert a.number == b.number


def test_collab_number_is_never_blank_and_never_duplicated(db, collab_figures_a):
    """The figure graph spans five numbered tables; none may ship a blank or a duplicate.

    ``bulk_create`` bypasses ``TenantNumbered.save()`` — the only thing that mints ``number`` — so
    this is the assertion that would catch a fan-out that skipped it.
    """
    for model, _prefix in _MODELS:
        numbers = list(model.objects.values_list("number", flat=True))
        assert "" not in numbers, f"{model.__name__} shipped a blank number"
        assert len(numbers) == len(set(numbers)), f"{model.__name__} shipped a duplicate"


# ==================================================================================================
# Channel — the unique_together constraint
# ==================================================================================================

def test_collab_channel_name_is_unique_per_project(db, planning_project_a, collab_channel_a):
    """A project cannot carry two channels of the same name.

    ``_collab_channel`` calls ``full_clean()``, so the duplicate is caught by Django's own
    ``validate_unique()`` and surfaces as a ``ValidationError`` — the user-facing path. Note it
    lands on ``__all__`` rather than on ``name``: Django reports a ``unique_together`` violation
    against the whole constraint, unlike a single-field ``unique=True``. The DB constraint itself
    is pinned separately below.
    """
    from django.core.exceptions import ValidationError
    with pytest.raises(ValidationError) as exc:
        _collab_channel(planning_project_a.tenant, planning_project_a,
                        name=collab_channel_a.name)
    assert "__all__" in getattr(exc.value, "message_dict", {})


def test_collab_channel_duplicate_is_also_blocked_by_the_database(
        db, planning_project_a, collab_channel_a):
    """Bypassing ``full_clean()`` must still fail — the constraint is real, not just Python.

    ``Channel.objects.create()`` skips validation entirely, so this reaches the DB and proves the
    ``unique_together`` exists in migration 0012 rather than only in ``Meta``.
    """
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Channel.objects.create(
                tenant=planning_project_a.tenant, project=planning_project_a,
                name=collab_channel_a.name, topic="", kind="discussion", is_archived=False)


def test_collab_channel_same_name_in_a_different_project_is_fine(
        db, planning_project_a, collab_channel_a):
    """The constraint is scoped to the project, not to the tenant."""
    from apps.projects.models import Project
    other = Project.objects.filter(tenant=planning_project_a.tenant).exclude(
        pk=planning_project_a.pk).first()
    if other is None:
        pytest.skip("only one project in tenant A — nothing to compare against")
    twin = _collab_channel(planning_project_a.tenant, other, name=collab_channel_a.name)
    assert twin.pk != collab_channel_a.pk


def test_collab_channel_same_name_in_a_different_tenant_is_fine(
        db, planning_project_b, collab_channel_a):
    twin = _collab_channel(planning_project_b.tenant, planning_project_b,
                           name=collab_channel_a.name)
    assert twin.pk != collab_channel_a.pk


# ==================================================================================================
# ChannelMessage.clean() — the three invariants
# ==================================================================================================

def test_collab_reply_may_not_jump_channels(db, collab_channel_a, collab_thread_root_a):
    """A reply must stay in the channel its parent belongs to."""
    other = _collab_channel(collab_thread_root_a.tenant, collab_channel_a.project,
                            name="A different channel")
    reply = collab_thread_root_a.replies.order_by("id").first()
    reply.channel = other
    with pytest.raises(Exception) as exc:
        reply.full_clean()
    assert "parent" in getattr(exc.value, "message_dict", {})


def test_collab_reply_may_not_nest_two_levels_deep(db, collab_thread_root_a):
    """A thread is one level deep — replying to a reply is refused."""
    reply = collab_thread_root_a.replies.order_by("id").first()
    nested = ChannelMessage(tenant=reply.tenant, channel=reply.channel, parent=reply,
                            body="A reply to a reply.")
    with pytest.raises(Exception) as exc:
        nested.full_clean()
    assert "parent" in getattr(exc.value, "message_dict", {})


def test_collab_root_with_replies_may_not_change_channel(db, collab_thread_root_a):
    """I1 regression — repointing a root would strand its replies on neither channel.

    The replies stay behind in the old channel while the root moves, and the channel page keys
    replies by parent inside that channel's own list — so the replies would render nowhere at all.
    """
    other = _collab_channel(collab_thread_root_a.tenant, collab_thread_root_a.channel.project,
                            name="Somewhere else")
    collab_thread_root_a.channel = other
    with pytest.raises(Exception) as exc:
        collab_thread_root_a.full_clean()
    assert "channel" in getattr(exc.value, "message_dict", {})


def test_collab_replyless_root_may_still_change_channel(db, collab_message_bare_a):
    """The guard must not over-reach: a root with no replies is free to move."""
    original = collab_message_bare_a.channel
    other = _collab_channel(collab_message_bare_a.tenant, original.project,
                            name="A new home")
    collab_message_bare_a.channel = other
    collab_message_bare_a.full_clean(exclude=["number"])
    collab_message_bare_a.save()
    collab_message_bare_a.refresh_from_db()
    assert collab_message_bare_a.channel_id == other.pk


def test_collab_root_with_replies_may_still_be_body_edited(db, collab_thread_root_a):
    """The guard is about the CHANNEL, not the row — editing the body must still work."""
    collab_thread_root_a.body = "Revised body."
    collab_thread_root_a.full_clean(exclude=["number"])
    collab_thread_root_a.save()
    collab_thread_root_a.refresh_from_db()
    assert collab_thread_root_a.body == "Revised body."


def test_collab_reply_body_is_editable_in_place(db, collab_thread_root_a):
    """A reply's own body edit is legitimate and must not be caught by the channel guard."""
    reply = collab_thread_root_a.replies.order_by("id").first()
    reply.body = "Revised reply body."
    reply.full_clean(exclude=["number"])
    reply.save()
    reply.refresh_from_db()
    assert reply.body == "Revised reply body."


# ==================================================================================================
# Derived properties — each pinned to an exact value
# ==================================================================================================

def test_collab_channel_is_open_mirrors_is_archived(db, collab_channel_a, collab_channel_archived_a):
    assert collab_channel_a.is_open is True
    assert collab_channel_archived_a.is_open is False


def test_collab_message_is_reply(db, collab_thread_root_a, collab_reply_a):
    assert collab_thread_root_a.is_reply is False
    assert collab_reply_a.is_reply is True


def test_collab_message_is_edited_is_false_until_stamped(db, collab_message_bare_a):
    """``is_edited`` reads the stamp, not the presence of an editor."""
    assert collab_message_bare_a.is_edited is False
    collab_message_bare_a.edited_at = timezone.now()
    assert collab_message_bare_a.is_edited is True


def test_collab_share_is_revoked_and_is_claimed(db, collab_share_view_a, collab_share_revoked_a,
                                                collab_share_edit_claimed_a):
    assert collab_share_view_a.is_revoked is False
    assert collab_share_view_a.is_claimed is False
    assert collab_share_revoked_a.is_revoked is True
    assert collab_share_edit_claimed_a.is_claimed is True


def test_collab_share_is_co_editable_needs_both_edit_and_active(
        db, collab_share_edit_free_a, collab_share_view_a, collab_share_revoked_a):
    """``edit`` alone is not enough — a REVOKED edit share is not co-editable."""
    assert collab_share_edit_free_a.is_co_editable is True
    assert collab_share_view_a.is_co_editable is False
    assert collab_share_revoked_a.is_co_editable is False


def test_collab_meeting_is_upcoming_and_is_past(db, collab_meeting_scheduled_a,
                                                collab_meeting_completed_a):
    """``is_upcoming`` needs BOTH the scheduled status and a future start."""
    assert collab_meeting_scheduled_a.is_upcoming is True
    assert collab_meeting_completed_a.is_upcoming is False
    assert collab_meeting_scheduled_a.is_past is False


def test_collab_meeting_is_past_for_a_backdated_meeting(db, planning_project_a):
    past = _collab_meeting(planning_project_a.tenant, planning_project_a,
                           scheduled_start=timezone.now() - datetime.timedelta(days=3))
    assert past.is_past is True
    assert past.is_upcoming is False


def test_collab_action_is_overdue_only_for_an_open_past_due_item(
        db, collab_action_open_a, collab_action_overdue_a, collab_action_done_a):
    """Three cases: no due date → False; open + past due → True; done + past due → False."""
    assert collab_action_open_a.is_overdue is False
    assert collab_action_overdue_a.is_overdue is True

    done_overdue = _collab_action(
        collab_action_done_a.tenant, collab_action_done_a.meeting,
        description="Done but was late", is_done=True,
        due_date=timezone.localdate() - datetime.timedelta(days=5))
    assert done_overdue.is_overdue is False


def test_collab_action_is_overdue_is_false_on_the_due_date_itself(db, collab_meeting_completed_a):
    """Due TODAY is not overdue — the comparison is strictly less-than (L16 clock)."""
    due_today = _collab_action(collab_meeting_completed_a.tenant, collab_meeting_completed_a,
                               description="Due today", due_date=timezone.localdate())
    assert due_today.is_overdue is False


def test_collab_notification_is_unread_mirrors_is_read(db, collab_notification_unread_a,
                                                       collab_notification_read_a):
    assert collab_notification_unread_a.is_unread is True
    assert collab_notification_read_a.is_unread is False


# ==================================================================================================
# Meta — ordering and the declared indexes
# ==================================================================================================

@pytest.mark.parametrize("model,ordering", [
    (Channel, ["project_id", "name", "id"]),
    (ChannelMessage, ["channel_id", "created_at", "id"]),
    (DocumentShare, ["-created_at", "-id"]),
    (Meeting, ["-scheduled_start", "-id"]),
    (MeetingAgendaItem, ["meeting_id", "sequence", "id"]),
    (MeetingActionItem, ["meeting_id", "id"]),
    (ProjectNotification, ["-created_at", "-id"]),
])
def test_collab_meta_ordering_is_pinned(db, model, ordering):
    assert model._meta.ordering == ordering


@pytest.mark.parametrize("model,index_name", [
    (Channel, "chn_tnt_project_idx"),
    (Channel, "chn_tnt_archived_idx"),
    (ChannelMessage, "chm_tnt_channel_idx"),
    (ChannelMessage, "chm_tnt_parent_idx"),
    (ChannelMessage, "chm_tnt_created_idx"),
    (DocumentShare, "dsh_tnt_project_idx"),
    (DocumentShare, "dsh_tnt_active_idx"),
    (DocumentShare, "dsh_tnt_document_idx"),
    (DocumentShare, "dsh_tnt_created_idx"),
    (Meeting, "mtg_tnt_project_idx"),
    (Meeting, "mtg_tnt_status_idx"),
    (Meeting, "mtg_tnt_start_idx"),
    (Meeting, "mtg_tnt_created_idx"),
    (MeetingAgendaItem, "agi_tnt_meeting_idx"),
    (MeetingAgendaItem, "agi_tnt_covered_idx"),
    (MeetingActionItem, "mait_tnt_meeting_idx"),
    (MeetingActionItem, "mait_tnt_done_idx"),
    (MeetingActionItem, "mait_tnt_assignee_idx"),
    (ProjectNotification, "ntf_tnt_recipient_idx"),
    (ProjectNotification, "ntf_tnt_kind_idx"),
    (ProjectNotification, "ntf_tnt_project_idx"),
    (ProjectNotification, "ntf_tnt_created_idx"),
])
def test_collab_declared_index_exists(db, model, index_name):
    """Every index the contract declared is actually on the model (and therefore in migration 0013).

    The four ``*_tnt_created_idx`` indexes are the I2 fix: the feed filters every source on
    ``(tenant, created_at)`` and nothing indexed it.
    """
    names = {idx.name for idx in model._meta.indexes}
    assert index_name in names, f"{model.__name__} is missing {index_name}"


def test_collab_every_declared_index_is_tenant_leading(db):
    """``tenant`` is the always-applied filter, so it must be the first column of every index."""
    for model, _prefix in _MODELS:
        for idx in model._meta.indexes:
            assert idx.fields[0] == "tenant", f"{model.__name__}.{idx.name} does not lead with tenant"


def test_collab_unique_together_is_tenant_number_everywhere(db):
    """All seven tables constrain ``(tenant, number)`` — the numbering contract."""
    for model, _prefix in _MODELS:
        assert ("tenant", "number") in model._meta.unique_together, model.__name__


def test_collab_channel_adds_the_project_name_constraint(db):
    assert ("tenant", "project", "name") in Channel._meta.unique_together


# ==================================================================================================
# __str__ — the label every list page and admin renders
# ==================================================================================================

def test_collab_str_renders_the_number_and_a_label(db, collab_channel_a, collab_share_view_a,
                                                   collab_meeting_scheduled_a):
    assert collab_channel_a.number in str(collab_channel_a)
    assert collab_channel_a.name in str(collab_channel_a)
    assert collab_share_view_a.number in str(collab_share_view_a)
    assert collab_meeting_scheduled_a.title in str(collab_meeting_scheduled_a)
