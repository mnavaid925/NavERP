"""Projects 7.9 — ChannelMessage [CHM-]: one message in a project channel.

Realizes bullet **1's threaded discussions** and delivers its **@mention notifications**. A thread
reply is simply a row with ``parent`` set (a self-FK) — the schema allows one nesting level and
``clean()`` enforces it, because a thread that nests arbitrarily is a tree nobody reads.

**The mention list is the audience; the notification is the delivery.** ``mentions`` records WHO
was named, and ``msg_create`` / ``msg_edit`` mint one ``ProjectNotification`` row per newly-added
mention (``related_name="project_notifications"`` on the message). That split is deliberate: the
message is the collaboration artifact, the notification is per-recipient delivery state, and only
the latter carries ``is_read``/``read_at``.

**The edit stamps are verb-written.** ``edited_by`` / ``edited_at`` are OFF the model form and
stamped by ``msg_edit`` alone, so "was this edited, and by whom" survives every later save.

**Prefix is ``CHM``, not ``MSG``** — ``MSG`` is taken by ``scm.IntegrationMessage`` (the integration
gateway's outbound log). Numbers are unique per ``(tenant, number)`` *within a model*, so a shared
prefix would not be a key collision, but two different things reading ``MSG-00001`` is exactly the
confusion the three-``PRJ-``-models note in 7.1 warns about.

**No money column.** Nothing on a message is priced; cost lives on 7.4's registers (L29).
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models, settings


class ChannelMessage(TenantNumbered):
    NUMBER_PREFIX = "CHM"

    #: The conversation this message belongs to. CASCADE — a message has no life outside its
    #: channel (the same idiom every child row of a parent register uses).
    channel = models.ForeignKey(
        "projects.Channel", on_delete=models.CASCADE, related_name="messages")
    #: The thread root this row replies to. NULL means this row IS a root. CASCADE, because a
    #: deleted root takes its thread with it — an orphaned reply has nothing to read against.
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies")
    body = models.TextField()
    #: WHO was named. The delivery half is the notification row — see the module docstring.
    mentions = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="channel_mentions")
    #: VERB-WRITTEN by ``msg_edit`` ONLY — never on a form.
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")
    edited_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")

    class Meta:
        ordering = ["channel_id", "created_at", "id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "channel"], name="chm_tnt_channel_idx"),
            models.Index(fields=["tenant", "parent"], name="chm_tnt_parent_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.body[:60]}"

    def clean(self):
        """A reply must stay in its own channel, one level deep.

        The same cross-row guard idiom ``TaskDependency.clean()`` uses for its same-project rule.
        Both checks read ``self.parent`` once: the FK is already loaded by the form's own
        validation path, so this does not add a query per save.
        """
        super().clean()
        if self.parent_id is None:
            return
        parent = self.parent
        if parent.channel_id != self.channel_id:
            raise ValidationError(
                {"parent": "A reply must stay in the channel its parent message belongs to."})
        if parent.parent_id is not None:
            raise ValidationError(
                {"parent": "A thread is one level deep — reply to the message, not to a reply."})

    @property
    def is_reply(self):
        """Derived: is this row inside a thread rather than starting one."""
        return self.parent_id is not None

    @property
    def is_edited(self):
        """Derived: has the body been changed since it was posted."""
        return self.edited_at is not None
