from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class DocumentAcknowledgment(TenantNumbered):
    NUMBER_PREFIX = "QACK"

    STATUS_CHOICES = [
        ("pending", "Pending Sign-Off"),
        ("acknowledged", "Acknowledged"),
        ("overdue", "Overdue"),
        ("waived", "Waived"),
    ]

    STATUS_CSS = {
        "pending": "badge-amber",
        "acknowledged": "badge-green",
        "overdue": "badge-red",
        "waived": "badge-slate",
    }

    document = models.ForeignKey(
        "quality.ControlledDocument", on_delete=models.CASCADE, related_name="acknowledgments"
    )
    document_revision = models.CharField(max_length=20)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="document_acknowledgments"
    )
    employee = models.ForeignKey(
        "hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="quality_acknowledgments"
    )
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True, editable=False)
    signature_record = models.ForeignKey(
        "quality.ElectronicSignatureRecord", on_delete=models.SET_NULL, null=True, blank=True, related_name="linked_acknowledgment"
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-due_date", "-created_at"]
        verbose_name = "Document Acknowledgment"
        verbose_name_plural = "Document Acknowledgments"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qack_ten_num_uniq"),
            models.UniqueConstraint(
                fields=["tenant", "document", "document_revision", "user"],
                name="idx_qack_ten_doc_rev_usr",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qack_ten_status"),
            models.Index(fields=["tenant", "user", "status"], name="idx_qack_ten_user_stat"),
            models.Index(fields=["tenant", "due_date"], name="idx_qack_ten_duedate"),
        ]

    def __str__(self):
        return f"{self.number} - {self.user.username} ({self.document.number} Rev {self.document_revision})"

    @property
    def is_overdue(self):
        if self.status == "pending" and self.due_date:
            return self.due_date < timezone.now().date()
        return False
