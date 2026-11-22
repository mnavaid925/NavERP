from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.documents.models._base import TenantNumbered


class DocumentReviewComment(TenantNumbered):
    NUMBER_PREFIX = "DREV"

    ANNOTATION_TYPE_CHOICES = [
        ("inline_comment", "Inline Discussion Comment"),
        ("highlight", "Text Highlight Annotation"),
        ("redline", "Redline / Suggested Revision"),
        ("sticky_note", "Sticky Note Pin"),
        ("drawing_callout", "Geometry / Drawing Callout"),
    ]

    STATUS_CHOICES = [
        ("open", "Open / Action Required"),
        ("addressed", "Addressed / Implemented"),
        ("resolved", "Resolved & Closed"),
        ("dismissed", "Dismissed / Not Applicable"),
    ]

    STATUS_CSS = {
        "open": "badge-amber",
        "addressed": "badge-info",
        "resolved": "badge-green",
        "dismissed": "badge-muted",
    }

    ANNOTATION_TYPE_CSS = {
        "inline_comment": "badge-info",
        "highlight": "badge-amber",
        "redline": "badge-red",
        "sticky_note": "badge-slate",
        "drawing_callout": "badge-green",
    }

    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.CASCADE,
        related_name="review_comments",
        db_index=True,
    )
    version = models.ForeignKey(
        "documents.DocumentVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="review_comments",
    )
    workflow = models.ForeignKey(
        "documents.DocumentApprovalWorkflow",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="review_comments",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="document_review_comments",
    )
    annotation_type = models.CharField(
        max_length=30,
        choices=ANNOTATION_TYPE_CHOICES,
        default="inline_comment",
        db_index=True,
    )
    page_number = models.PositiveIntegerField(default=1)
    coordinate_ref = models.CharField(
        max_length=255,
        blank=True,
        help_text="Coordinates 'x,y,w,h' or DOM text anchor",
    )
    selected_text = models.TextField(
        blank=True,
        help_text="Highlighted or quoted snippet",
    )
    content = models.TextField()
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="open",
        db_index=True,
    )
    is_blocking = models.BooleanField(
        default=False,
        help_text="Blocks workflow approval until marked resolved",
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_document_comments",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["page_number", "-created_at"]
        verbose_name = "Document Review Comment"
        verbose_name_plural = "Document Review Comments"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="doc_drev_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "document", "status"], name="doc_drev_tnt_doc_stat_idx"),
            models.Index(fields=["tenant", "workflow", "is_blocking"], name="doc_drev_tnt_wf_block_idx"),
        ]

    def __str__(self):
        return f"{self.number} — p.{self.page_number} [{self.get_annotation_type_display()}] by {self.author.username}"

    def get_absolute_url(self):
        return reverse("documents:review_comment_detail", kwargs={"pk": self.pk})

    @property
    def status_css_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def annotation_type_css_class(self):
        return self.ANNOTATION_TYPE_CSS.get(self.annotation_type, "badge-slate")
