"""Projects 7.9 — DocumentShare [DSH-]: a stored document shared into a project conversation.

Realizes bullet **2's document sharing**. The split of ownership is the whole point of this row:

* The FILE and its VERSION belong to **``core.Document``** — the generic attachment store, reached
  here **by string** (``"core.Document"``). 7.10 Document & Knowledge Management owns the
  repository, the folders, the metadata tags and the version history; 7.9 ships **no second file
  store and no version column** (the 7.1 ``charter_document`` ruling).
* **This row is the SHARE** — who in this project may do what with an already-stored document,
  optionally pinned into a channel, optionally addressed to one person instead of the whole team.

**Co-editing, honestly.** Real-time collaborative editing needs a websocket/CRDT stack the repo
does not have, so the affordance 7.9 ships is the one a non-realtime tool can actually honour: an
access level plus a **single-editor claim**. ``claimed_by``/``claimed_at`` are written by the
POST-only ``dsh_claim`` / ``dsh_release`` verbs and answer "who is editing this right now".

**Verb-written state.** ``is_active``/``revoked_by``/``revoked_at`` are OFF the form and written by
``dsh_revoke`` alone — a toggle, so a restore goes through the SAME verb + audit. Revoking also
**releases any active claim**, because "I may edit this now" cannot outlive the share that granted
it.

**No money column.** Nothing on a share is priced; cost lives on 7.4's registers (L29).
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models, settings


class DocumentShare(TenantNumbered):
    NUMBER_PREFIX = "DSH"

    ACCESS_CHOICES = [
        ("view", "View only"),
        ("comment", "Comment"),
        ("edit", "Can edit"),
    ]

    #: The project this share lives in. CASCADE — a share has no life outside its project.
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="document_shares")
    #: Optional: pin the share into one conversation. SET_NULL — deleting the channel must not
    #: destroy the share, it just stops being pinned to a room.
    channel = models.ForeignKey(
        "projects.Channel", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="document_shares")
    #: The stored artifact. CASCADE — the share is meaningless without the file behind it. The
    #: FILE is 7.10's; this FK is by string precisely so 7.9 owns no attachment table (L29).
    document = models.ForeignKey(
        "core.Document", on_delete=models.CASCADE, related_name="project_shares")
    access_level = models.CharField(max_length=8, choices=ACCESS_CHOICES, default="view")
    #: NULL means "the whole project team" — a share is addressed to a person OR to everyone, and
    #: a null here is a state, not a missing value.
    shared_with = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="received_document_shares")
    note = models.TextField(blank=True)

    #: VERB-WRITTEN by ``dsh_revoke`` ONLY — stamped together on revoke, cleared on restore.
    is_active = models.BooleanField(default=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")
    revoked_at = models.DateTimeField(null=True, blank=True, editable=False)
    #: VERB-WRITTEN by ``dsh_claim``/``dsh_release`` ONLY — the single-editor marker.
    claimed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")
    claimed_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "project"], name="dsh_tnt_project_idx"),
            models.Index(fields=["tenant", "is_active"], name="dsh_tnt_active_idx"),
            models.Index(fields=["tenant", "document"], name="dsh_tnt_document_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.document.name}"

    @property
    def is_revoked(self):
        """Derived converse of ``is_active`` — a template lens, never a column."""
        return not self.is_active

    @property
    def is_claimed(self):
        """Derived: does anyone hold the edit claim right now."""
        return self.claimed_at is not None

    @property
    def is_co_editable(self):
        """Derived: may this share be claimed at all (live AND shared at ``edit``)."""
        return self.is_active and self.access_level == "edit"
