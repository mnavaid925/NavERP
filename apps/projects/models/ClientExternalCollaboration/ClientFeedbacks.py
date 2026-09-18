"""Projects 7.14 Client & External Collaboration — ClientApprovalRequest [CFB-].

Client review cycles, deliverable/milestone feedback capture, annotations,
and formal client sign-off / rejection workflows.
"""
from django.conf import settings
from django.db import models

from apps.projects.models._base import TenantNumbered


class ClientApprovalRequest(TenantNumbered):
    NUMBER_PREFIX = "CFB"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending_review", "Pending Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("revision_requested", "Revision Requested"),
    ]

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="client_approval_requests",
    )
    deliverable_name = models.CharField(max_length=255)
    document = models.ForeignKey(
        "core.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="client_approval_requests",
    )
    milestone = models.ForeignKey(
        "projects.ProjectMilestone",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="client_approval_requests",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_client_approvals",
    )
    assigned_contact = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_client_approvals",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    due_date = models.DateField(null=True, blank=True)
    review_notes = models.TextField(blank=True, help_text="Context and instructions for the client")
    client_feedback = models.TextField(blank=True, help_text="Client annotations and comments")
    signed_by_name = models.CharField(max_length=255, blank=True)
    signed_at = models.DateTimeField(null=True, blank=True, editable=False)
    rejection_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = (("tenant", "number"),)
        indexes = [
            models.Index(fields=["tenant", "project"], name="cfb_tnt_project_idx"),
            models.Index(fields=["tenant", "status"], name="cfb_tnt_status_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.deliverable_name} ({self.get_status_display()})"
