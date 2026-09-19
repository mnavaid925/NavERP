"""core — 0.8 bullet 2: Data Subject Rights (DSAR).

A statutory clock is the whole point of this model. A request that is logged without a deadline is a
reminder, not a compliance control, so `due_at` is stamped at creation from the workspace's enabled
frameworks (the STRICTEST window wins) and `is_overdue` is derived from it.

`identity_verified` is a first-class field rather than a note: releasing or erasing personal data on
an unverified request is the failure mode this whole sub-module exists to prevent, so the workflow
refuses to progress past verification without it.
"""
from django.utils import timezone

from apps.core.models._base import *  # noqa: F401,F403


class DataSubjectRequest(models.Model):
    KIND_CHOICES = [
        ("access", "Access (copy of data)"),
        ("rectification", "Rectification"),
        ("erasure", "Erasure / right to be forgotten"),
        ("portability", "Portability (machine-readable export)"),
        ("restriction", "Restriction of processing"),
        ("objection", "Objection to processing"),
    ]
    STATUS_CHOICES = [
        ("received", "Received"),
        ("verifying", "Verifying identity"),
        ("in_progress", "In progress"),
        ("completed", "Completed"),
        ("refused", "Refused"),
        ("withdrawn", "Withdrawn by the subject"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="data_subject_requests", db_index=True)
    subject = models.ForeignKey("core.Party", on_delete=models.CASCADE,
                                related_name="data_subject_requests", db_index=True)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="received")
    detail = models.TextField(help_text="What the subject asked for, in their own words.")
    received_at = models.DateTimeField(default=timezone.now)
    #: Stamped at creation from the strictest enabled framework. Nullable so a workspace with NO
    #: framework enabled records an untimed request rather than inventing a deadline it cannot cite.
    due_at = models.DateTimeField(null=True, blank=True)
    #: Verification is a gate, not a checkbox: the status machine refuses to leave `verifying`
    #: without it. An unverified erasure request is how data gets destroyed for the wrong person.
    identity_verified = models.BooleanField(default=False)
    verification_note = models.CharField(max_length=255, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)
    refusal_reason = models.TextField(blank=True)
    response_notes = models.TextField(blank=True)
    handled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   blank=True, editable=False, related_name="handled_dsars")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at", "-id"]
        indexes = [
            models.Index(fields=["tenant", "status"], name="dsar_tenant_status_idx"),
            models.Index(fields=["tenant", "due_at"], name="dsar_tenant_due_idx"),
        ]

    @property
    def is_open(self):
        return self.status not in ("completed", "refused", "withdrawn")

    @property
    def is_overdue(self):
        """Only an OPEN request can be overdue — a completed one is not late even if it finished
        after the deadline, because the deadline is about the answer, not about the queue."""
        return (self.is_open and self.due_at is not None and timezone.now() > self.due_at)

    @property
    def days_remaining(self):
        if self.due_at is None:
            return None
        return (self.due_at - timezone.now()).days

    def __str__(self):
        return f"{self.get_kind_display()} · {self.subject}"
