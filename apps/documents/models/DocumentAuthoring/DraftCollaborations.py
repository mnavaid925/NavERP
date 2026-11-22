from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.documents.models._base import TenantNumbered

ENTRY_TYPE_CHOICES = [
    ("comment", "Inline Comment / Feedback"),
    ("suggestion", "Content Suggestion (Proposed Change)"),
    ("track_change", "Tracked Edit / Delta"),
]

STATUS_CHOICES = [
    ("open", "Open / Pending Review"),
    ("accepted", "Accepted & Applied"),
    ("rejected", "Rejected / Dismissed"),
    ("resolved", "Resolved"),
]


class DraftCollaboration(TenantNumbered):
    NUMBER_PREFIX = "DCMT"

    ENTRY_TYPE_CHOICES = ENTRY_TYPE_CHOICES
    STATUS_CHOICES = STATUS_CHOICES

    draft = models.ForeignKey(
        "documents.DocumentDraft",
        on_delete=models.CASCADE,
        related_name="collaborations",
    )
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPE_CHOICES, default="comment", db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open", db_index=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="draft_collaborations",
    )
    selected_text = models.TextField(blank=True, help_text="Original text being referenced or proposed for change")
    replacement_text = models.TextField(blank=True, help_text="Proposed replacement text in suggestion or track changes mode")
    comment_text = models.TextField(help_text="Review feedback, explanation, or discussion comment")
    section_anchor = models.CharField(max_length=100, blank=True, help_text="Heading or section anchor in the document")
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_collaborations",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="doc_cmt_tnt_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "draft", "status"], name="doc_cmt_tnt_dft_idx"),
        ]

    def __str__(self):
        return f"{self.number} - {self.get_entry_type_display()} on {self.draft.number}"

    def clean(self):
        super().clean()
        if self.draft_id and self.draft.tenant_id != self.tenant_id:
            raise ValidationError({"draft": "Referenced draft must belong to the same workspace."})
