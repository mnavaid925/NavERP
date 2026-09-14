"""Projects 7.9 — ProjectNotification [NTF-]: one delivered notification for one recipient.

Realizes bullet **4's notification rows** ("Customizable triggers for assignments, due dates,
mentions, and system events") and delivers bullet **1's @mention notifications**. The trigger
**RULES** — the engine that decides when to mint one, the reminders, the escalation on timeout —
belong to 7.17 Workflow & Automation ("Notification & Reminder Rules"). This table is the
delivery half: a row per recipient, with read state.

**Evidence-row ruling (do not add a create or edit path).** Rows are **minted by triggers only** —
``msg_create``/``msg_edit`` (a ``mention``), the seeder, and later 7.17's rule engine — and are
closed by ``ntf_mark_read`` and dismissed by ``ntf_delete``. There is **no ModelForm** and no
``ntf_create``/``ntf_edit`` route at all: a hand-written notification has no trigger behind it, so
it would be a lie in the inbox.

**Unlike 7.8's ``TaskBlock``, a notification IS deletable.** A block is shared evidence that the
whole project reads; a notification is one person's delivery row, and an inbox you cannot clear is
a worse inbox. The distinction is the reason both rulings coexist.

**``is_read``/``read_at`` are verb-written** by ``ntf_mark_read`` alone — a toggle, so marking
something unread again goes through the SAME verb + audit.

**The four optional source FKs** (``channel``/``message``/``task``/``meeting``) are what the inbox
and the activity feed deep-link from. Each is SET_NULL: deleting the thing that triggered a
notification must not delete the record that someone was told about it.

**No money column.** Nothing on a notification is priced; cost lives on 7.4's registers (L29).
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models, settings


class ProjectNotification(TenantNumbered):
    NUMBER_PREFIX = "NTF"

    KIND_CHOICES = [
        ("mention", "Mention"),
        ("assignment", "Assignment"),
        ("due_date", "Due Date"),
        ("status_change", "Status Change"),
        ("system", "System"),
    ]

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="project_notifications")
    #: The person this row is delivered to. CASCADE — a notification has no meaning without a
    #: recipient (the one FK here that is not SET_NULL, on purpose).
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="project_notifications")
    kind = models.CharField(max_length=16, choices=KIND_CHOICES, default="system")
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)

    # -- the optional sources the inbox deep-links from -----------------------------------------
    channel = models.ForeignKey(
        "projects.Channel", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="project_notifications")
    message = models.ForeignKey(
        "projects.ChannelMessage", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="project_notifications")
    task = models.ForeignKey(
        "projects.ProjectTask", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="project_notifications")
    meeting = models.ForeignKey(
        "projects.Meeting", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="project_notifications")

    #: Who caused it. NULL for a system event.
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="triggered_notifications")
    #: VERB-WRITTEN by ``ntf_mark_read`` ONLY — a toggle, one writer per direction.
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            # The inbox's own query: one recipient's unread rows.
            models.Index(fields=["tenant", "recipient", "is_read"],
                         name="ntf_tnt_recipient_idx"),
            models.Index(fields=["tenant", "kind"], name="ntf_tnt_kind_idx"),
            models.Index(fields=["tenant", "project"], name="ntf_tnt_project_idx"),
            # Serves `Meta.ordering` itself (`ntf_list` sorts every render) and the activity
            # feed's notification source. The in-pattern add — ["tenant", "created_at"] already
            # ships on 20+ models app-wide.
            models.Index(fields=["tenant", "-created_at"], name="ntf_tnt_created_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"

    @property
    def is_unread(self):
        """Derived converse of ``is_read`` — a template lens, never a column."""
        return not self.is_read
