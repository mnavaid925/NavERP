from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.documents.models._base import TenantNumbered

DRAFT_STATUS_CHOICES = [
    ("draft", "Draft / In Authoring"),
    ("in_review", "Peer Review / Collaboration"),
    ("ready_for_promotion", "Ready for Official Release"),
    ("promoted", "Promoted to Official Document"),
    ("discarded", "Discarded / Canceled"),
]

DOCUMENT_TYPE_CHOICES = [
    ("sop", "Standard Operating Procedure"),
    ("contract", "Contract Agreement"),
    ("policy", "Company Policy"),
    ("report", "Report"),
    ("memo", "Internal Memo"),
    ("letter", "Official Letter"),
    ("other", "Other Document"),
]

CONTENT_FORMAT_CHOICES = [
    ("html", "Rich Text / HTML"),
    ("markdown", "Markdown / Plain Text"),
    ("plain", "Plain Text"),
]

SYNC_STATUS_CHOICES = [
    ("synced", "Fully Synchronized"),
    ("conflict_pending", "Sync Conflict Detected"),
    ("resolved", "Conflict Resolved"),
]


class DocumentDraft(TenantNumbered):
    NUMBER_PREFIX = "DDFT"

    DRAFT_STATUS_CHOICES = DRAFT_STATUS_CHOICES
    DOCUMENT_TYPE_CHOICES = DOCUMENT_TYPE_CHOICES
    CONTENT_FORMAT_CHOICES = CONTENT_FORMAT_CHOICES
    SYNC_STATUS_CHOICES = SYNC_STATUS_CHOICES

    title = models.CharField(max_length=255, db_index=True)
    document_type = models.CharField(max_length=40, choices=DOCUMENT_TYPE_CHOICES, default="sop")
    template = models.ForeignKey(
        "documents.DocumentTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="derived_drafts",
    )
    status = models.CharField(max_length=30, choices=DRAFT_STATUS_CHOICES, default="draft", db_index=True)
    draft_version = models.CharField(max_length=20, default="0.1", help_text="Pre-release Version Zero notation (e.g. 0.1, 0.2)")
    content = models.TextField(blank=True, help_text="Active working draft text and embedded media")
    content_format = models.CharField(max_length=20, choices=CONTENT_FORMAT_CHOICES, default="html")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="authored_drafts",
    )
    department = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="draft_documents",
    )
    related_party = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="draft_documents",
    )
    auto_save_timestamp = models.DateTimeField(null=True, blank=True)
    is_collaboration_locked = models.BooleanField(default=False, help_text="Lock to prevent simultaneous conflicting edits")
    offline_client_id = models.CharField(max_length=64, blank=True, help_text="Session client ID for offline authoring cache")
    offline_cached_at = models.DateTimeField(null=True, blank=True)
    sync_status = models.CharField(max_length=30, choices=SYNC_STATUS_CHOICES, default="synced")
    word_count = models.PositiveIntegerField(default=0)
    promoted_at = models.DateTimeField(null=True, blank=True)
    promoted_version = models.CharField(max_length=20, blank=True, help_text="Official version assigned upon promotion e.g. 1.0")
    promoted_document = models.ForeignKey(
        "core.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_drafts",
        help_text="Official released file master",
    )

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="doc_dft_tnt_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status", "document_type"], name="doc_dft_tnt_stat_idx"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title} (v{self.draft_version})"

    def clean(self):
        super().clean()
        if self.template_id and self.template.tenant_id != self.tenant_id:
            raise ValidationError({"template": "Template must belong to the same workspace."})
        if self.department_id and self.department.tenant_id != self.tenant_id:
            raise ValidationError({"department": "Department must belong to the same workspace."})
        if self.related_party_id and self.related_party.tenant_id != self.tenant_id:
            raise ValidationError({"related_party": "Party must belong to the same workspace."})
        if self.promoted_document_id and self.promoted_document.tenant_id != self.tenant_id:
            raise ValidationError({"promoted_document": "Document record must belong to the same workspace."})
