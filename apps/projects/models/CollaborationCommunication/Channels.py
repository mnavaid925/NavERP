"""Projects 7.9 Collaboration & Communication — Channel [CHN-]: a project's conversation container.

Realizes bullet **1's channels** ("Project-specific chat, threaded discussions, and @mention
notifications"). A channel owns nothing but its own metadata: the conversation lives in
``ChannelMessage`` (``related_name="messages"``) and the documents pinned into it are
``DocumentShare`` rows (``related_name="document_shares"``). There is no message column here and
no document column here.

**The archive state is verb-written.** ``is_archived`` / ``archived_by`` / ``archived_at`` are OFF
the model form and OFF every generic writer: the POST-only ``chn_archive`` verb is their ONLY
writer, and it is a TOGGLE — archiving stamps all three together, unarchiving clears all three,
with ``previous`` captured BEFORE the mutation (the 7.4/7.6/7.8 verb-written-stamp idiom). An
archived channel stays fully readable; it just stops inviting new posts.

**No message counter column.** ``Channel.messages`` is the source of truth; the register's count
is a ``Count("messages")`` ANNOTATION on the view's queryset, never a stored column and never a
``.count()`` property — a property re-queries once per rendered row and defeats
``prefetch_related`` (the 7.8 ``checklist_progress`` lesson).

**No money column.** Nothing on a channel is priced; cost lives on 7.4's registers (L29).
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models, settings


class Channel(TenantNumbered):
    NUMBER_PREFIX = "CHN"

    KIND_CHOICES = [
        ("discussion", "Discussion"),
        ("announcement", "Announcement"),
    ]

    #: The project this conversation belongs to. CASCADE — a channel has no life outside its
    #: project (the same idiom every child row of a parent register uses).
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="channels")
    name = models.CharField(max_length=100)
    topic = models.CharField(max_length=255, blank=True)
    kind = models.CharField(max_length=12, choices=KIND_CHOICES, default="discussion")

    #: VERB-WRITTEN by ``chn_archive`` ONLY — stamped together on archive, cleared together on
    #: unarchive. Never on a form.
    is_archived = models.BooleanField(default=False)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")
    archived_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")

    class Meta:
        ordering = ["project_id", "name", "id"]
        # The second constraint is the working one: one project cannot carry two channels of the
        # same name. ``("tenant", "number")`` is the TenantNumbered house constraint.
        unique_together = (("tenant", "number"), ("tenant", "project", "name"))
        indexes = [
            models.Index(fields=["tenant", "project"], name="chn_tnt_project_idx"),
            models.Index(fields=["tenant", "is_archived"], name="chn_tnt_archived_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name}"

    @property
    def is_open(self):
        """The derived converse of ``is_archived`` — a template lens, never a column."""
        return not self.is_archived
