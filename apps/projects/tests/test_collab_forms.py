"""Projects 7.9 — Collaboration & Communication form tests.

The form layer is where the two authorization boundaries actually live, so these tests are mostly
about what a CRAFTED POST can and cannot do:

* ``Meta.fields`` — the mass-assignment boundary. Every flag 7.9 writes from a verb
  (``is_archived``/``is_active``/``is_read``/``is_covered``/``is_done``/``status``/``minutes`` and
  every ``*_by``/``*_at`` stamp) must be unreachable from every form.
* ``_reject_foreign`` — the tenant boundary for single FKs. It re-checks tenant-scoped FKs and must
  be applied to NEITHER a ``settings.AUTH_USER_MODEL`` FK (users may be tenant-less) NOR a M2M (a
  cleaned M2M value is a list, so ``getattr(list, "tenant_id")`` would raise ``AttributeError``).
* ``ChannelMessageForm.mentions`` — the one place ``TenantModelForm`` does NOT help, because it
  scopes ``ModelChoiceField`` only and ``mentions`` is a ``ModelMultipleChoiceField``. The narrowed
  queryset IS the authorization boundary here.

Naming: every test ``test_collab_*``, every helper ``_collab_*``.
"""
import pytest

from apps.projects.forms import (
    ChannelForm,
    ChannelMessageForm,
    DocumentShareForm,
    MeetingActionItemForm,
    MeetingAgendaItemForm,
    MeetingForm,
    MeetingMinutesForm,
)

#: The contract's §4 field lists, in order. These are the mass-assignment boundary.
_PINNED_FIELDS = {
    ChannelForm: ["project", "name", "topic", "kind"],
    ChannelMessageForm: ["channel", "parent", "body", "mentions"],
    DocumentShareForm: ["project", "channel", "document", "access_level", "shared_with", "note"],
    MeetingForm: ["project", "title", "kind", "scheduled_start", "scheduled_end", "location",
                  "mode", "recurrence"],
    MeetingAgendaItemForm: ["title", "presenter", "duration_minutes", "sequence"],
    MeetingActionItemForm: ["description", "assignee", "due_date", "task"],
}

#: Every flag a 7.9 verb writes. None may appear on ANY form.
_VERB_WRITTEN = {
    "is_archived", "archived_by", "archived_at",
    "is_active", "revoked_by", "revoked_at",
    "claimed_by", "claimed_at",
    "is_read", "read_at",
    "is_covered", "covered_by", "covered_at",
    "is_done", "done_by", "done_at",
    "edited_by", "edited_at",
    "status", "minutes", "minutes_by", "minutes_at",
    "actual_start", "actual_end",
}


# ==================================================================================================
# Meta.fields — the mass-assignment boundary
# ==================================================================================================

@pytest.mark.parametrize("form_class,expected", list(_PINNED_FIELDS.items()))
def test_collab_form_fields_are_pinned_in_order(db, form_class, expected):
    assert list(form_class.Meta.fields) == expected


@pytest.mark.parametrize("form_class", list(_PINNED_FIELDS))
def test_collab_no_form_exposes_a_verb_written_flag(db, form_class):
    """A crafted POST must not be able to set a state the verb alone owns."""
    leaked = _VERB_WRITTEN.intersection(form_class.Meta.fields)
    assert not leaked, f"{form_class.__name__} exposes {sorted(leaked)}"


def test_collab_meeting_minutes_form_is_a_plain_form(db):
    """``MeetingMinutesForm`` is the verb BODY, not a ModelForm — it can only carry ``minutes``."""
    assert not issubclass(MeetingMinutesForm, type(MeetingForm))
    assert list(MeetingMinutesForm().fields) == ["minutes"]
    assert MeetingMinutesForm().fields["minutes"].required is True


def test_collab_meeting_minutes_form_rejects_a_blank_body(db):
    assert MeetingMinutesForm({"minutes": ""}).is_valid() is False
    assert MeetingMinutesForm({"minutes": "   "}).is_valid() is False
    assert MeetingMinutesForm({"minutes": "Decisions recorded."}).is_valid() is True


# ==================================================================================================
# ChannelMessageForm — the M2M authorization boundary
# ==================================================================================================

def test_collab_message_form_scopes_mentions_to_the_tenant(db, tenant_a, admin_user):
    """The mention picker must offer only this workspace's users."""
    form = ChannelMessageForm(tenant=tenant_a)
    offered = set(form.fields["mentions"].queryset.values_list("pk", flat=True))
    assert offered, "the mention picker is empty for a tenant that has users"
    assert admin_user.pk in offered


def test_collab_message_form_rejects_a_cross_tenant_mention(
        db, tenant_a, tenant_b, planning_project_a, collab_channel_a, admin_b):
    """A crafted POST naming another workspace's user must be INVALID.

    This is the leak the narrowed queryset exists to close: accepting it would put a foreign user's
    name and email into this tenant's message AND mint a notification row in the wrong inbox.
    """
    form = ChannelMessageForm(
        data={"channel": collab_channel_a.pk, "parent": "", "body": "Hello.",
              "mentions": [admin_b.pk]},
        tenant=tenant_a)
    assert form.is_valid() is False
    assert "mentions" in form.errors


def test_collab_message_form_accepts_a_same_tenant_mention(
        db, tenant_a, planning_project_a, collab_channel_a, admin_user):
    form = ChannelMessageForm(
        data={"channel": collab_channel_a.pk, "parent": "", "body": "Hello.",
              "mentions": [admin_user.pk]},
        tenant=tenant_a)
    assert form.is_valid() is True, form.errors


def test_collab_message_form_mentions_are_empty_for_a_tenantless_form(db):
    """A tenant-less user gets an EMPTY picker, not an unscoped one (the ``owners()`` ruling)."""
    form = ChannelMessageForm(tenant=None)
    assert list(form.fields["mentions"].queryset) == []


def test_collab_message_form_rejects_a_cross_tenant_channel(
        db, tenant_a, collab_channel_b):
    """``channel`` is a single tenant-scoped FK, so ``_reject_foreign`` catches it."""
    form = ChannelMessageForm(
        data={"channel": collab_channel_b.pk, "parent": "", "body": "Hello.", "mentions": []},
        tenant=tenant_a)
    assert form.is_valid() is False
    assert "channel" in form.errors


def test_collab_message_form_rejects_a_cross_tenant_parent(
        db, tenant_a, collab_channel_a, collab_message_b):
    """A reply may not hang off another workspace's message."""
    form = ChannelMessageForm(
        data={"channel": collab_channel_a.pk, "parent": collab_message_b.pk, "body": "Reply.",
              "mentions": []},
        tenant=tenant_a)
    assert form.is_valid() is False
    assert "parent" in form.errors


# ==================================================================================================
# _reject_foreign — applied to tenant-scoped FKs, never to a User FK or a M2M
# ==================================================================================================

def test_collab_channel_form_rejects_a_cross_tenant_project(db, tenant_a, planning_project_b):
    form = ChannelForm(data={"project": planning_project_b.pk, "name": "Foreign channel",
                             "topic": "", "kind": "discussion"}, tenant=tenant_a)
    assert form.is_valid() is False
    assert "project" in form.errors


def test_collab_share_form_rejects_a_cross_tenant_document(db, tenant_a, planning_project_a,
                                                           collab_document_b):
    form = DocumentShareForm(
        data={"project": planning_project_a.pk, "channel": "", "document": collab_document_b.pk,
              "access_level": "view", "shared_with": "", "note": ""},
        tenant=tenant_a)
    assert form.is_valid() is False
    assert "document" in form.errors


def test_collab_meeting_form_rejects_a_cross_tenant_project(db, tenant_a, planning_project_b):
    form = MeetingForm(
        data={"project": planning_project_b.pk, "title": "Foreign meeting", "kind": "standup",
              "scheduled_start": "2026-10-01T09:00", "scheduled_end": "2026-10-01T10:00",
              "location": "", "mode": "virtual", "recurrence": "none"},
        tenant=tenant_a)
    assert form.is_valid() is False
    assert "project" in form.errors


def test_collab_action_form_rejects_a_cross_tenant_task(db, tenant_a, collab_meeting_scheduled_a):
    """``task`` is a tenant-scoped FK — a foreign work package must be refused."""
    from apps.projects.models import Project
    from apps.projects.tests.conftest import _planning_task
    foreign_project = Project.objects.exclude(tenant=tenant_a).first()
    if foreign_project is None:
        pytest.skip("no other-tenant project available")
    foreign_task = _planning_task(foreign_project.tenant, foreign_project)
    form = MeetingActionItemForm(
        data={"description": "Do the thing", "assignee": "", "due_date": "",
              "task": foreign_task.pk},
        tenant=tenant_a)
    assert form.is_valid() is False
    assert "task" in form.errors


def test_collab_share_form_does_not_crash_on_a_cross_tenant_user_fk(
        db, tenant_a, planning_project_a, collab_document_a, admin_b):
    """``shared_with`` is a USER FK and must never be handed to ``_reject_foreign``.

    A tenant B user is rejected by the tenant-scoped queryset; the point is that the form returns
    a clean error rather than raising ``AttributeError`` or silently accepting it.
    """
    form = DocumentShareForm(
        data={"project": planning_project_a.pk, "channel": "", "document": collab_document_a.pk,
              "access_level": "view", "shared_with": admin_b.pk, "note": ""},
        tenant=tenant_a)
    assert form.is_valid() is False
    assert "shared_with" in form.errors


def test_collab_action_form_does_not_crash_on_a_cross_tenant_assignee_fk(
        db, tenant_a, collab_meeting_scheduled_a, admin_b):
    """``assignee`` is a USER FK — the ``shared_with`` ruling again."""
    form = MeetingActionItemForm(
        data={"description": "Do the thing", "assignee": admin_b.pk, "due_date": "", "task": ""},
        tenant=tenant_a)
    assert form.is_valid() is False
    assert "assignee" in form.errors


def test_collab_agenda_form_does_not_crash_on_a_cross_tenant_presenter_fk(
        db, tenant_a, admin_b):
    """``presenter`` is a USER FK, and the agenda form applies no ``_reject_foreign`` at all."""
    form = MeetingAgendaItemForm(
        data={"title": "Foreign presenter", "presenter": admin_b.pk, "duration_minutes": 10,
              "sequence": 1},
        tenant=tenant_a)
    assert form.is_valid() is False
    assert "presenter" in form.errors


def test_collab_agenda_form_has_no_meeting_field(db):
    """``meeting`` comes from the URL pk — it must not be a form field at all."""
    assert "meeting" not in MeetingAgendaItemForm.Meta.fields
    assert "meeting" not in MeetingActionItemForm.Meta.fields


# ==================================================================================================
# TenantUniqueMixin — stamps tenant BEFORE full_clean()
# ==================================================================================================

def test_collab_channel_form_stamps_the_tenant_on_create(db, tenant_a, planning_project_a):
    """``TenantUniqueMixin`` sets ``instance.tenant`` before validation, so a model ``clean()``
    that reads ``self.tenant`` works on the create path."""
    form = ChannelForm(
        data={"project": planning_project_a.pk, "name": "Stamped channel", "topic": "",
              "kind": "discussion"},
        tenant=tenant_a)
    assert form.is_valid() is True, form.errors
    obj = form.save(commit=False)
    assert obj.tenant_id == tenant_a.pk


# ==================================================================================================
# Enum choice sets — the form must offer exactly the model's vocabulary
# ==================================================================================================

def test_collab_meeting_form_offers_the_model_choice_sets(db, tenant_a):
    form = MeetingForm(tenant=tenant_a)
    from apps.projects.models import Meeting
    for field, choices in [("kind", Meeting.KIND_CHOICES), ("mode", Meeting.MODE_CHOICES),
                           ("recurrence", Meeting.RECURRENCE_CHOICES)]:
        assert list(form.fields[field].choices) == list(choices)


def test_collab_share_form_offers_the_access_levels(db, tenant_a):
    from apps.projects.models import DocumentShare
    form = DocumentShareForm(tenant=tenant_a)
    assert list(form.fields["access_level"].choices) == list(DocumentShare.ACCESS_CHOICES)


def test_collab_channel_form_offers_the_kinds(db, tenant_a):
    from apps.projects.models import Channel
    form = ChannelForm(tenant=tenant_a)
    assert list(form.fields["kind"].choices) == list(Channel.KIND_CHOICES)
