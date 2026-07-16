"""HRM 3.26 Request Management — Documentrequest models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class DocumentRequest(TenantNumbered):
    """3.26 official-letter request — an employee asks HR to issue an experience letter, salary
    certificate, employment-verification / address-proof letter, NOC, etc. HR approves, then
    fulfils by (optionally) attaching the signed letter. Lifecycle draft -> pending ->
    approved/rejected/cancelled, then approved -> fulfilled. `output_file` is set ONLY by the
    fulfill action (never a create/edit form field)."""

    NUMBER_PREFIX = "DOCREQ"

    DOCUMENT_TYPE_CHOICES = [
        ("experience_letter", "Experience Letter"),
        ("salary_certificate", "Salary Certificate"),
        ("address_proof", "Address Proof"),
        ("employment_verification", "Employment Verification"),
        ("noc", "No-Objection Certificate"),
        ("relieving_letter_copy", "Relieving Letter Copy"),
        ("other", "Other"),
    ]
    DELIVERY_METHOD_CHOICES = [
        ("soft_copy", "Soft Copy"),
        ("hard_copy", "Hard Copy"),
        ("both", "Both"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
        ("fulfilled", "Fulfilled"),
    ]
    OPEN_STATUSES = ("draft", "pending")

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="document_requests")
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPE_CHOICES, default="experience_letter")
    purpose = models.TextField(help_text="Why the document is needed (e.g. visa, bank loan, higher education).")
    addressed_to = models.CharField(max_length=255, blank=True,
                                    help_text='e.g. "To Whom It May Concern" or a named recipient.')
    copies = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    delivery_method = models.CharField(max_length=15, choices=DELIVERY_METHOD_CHOICES, default="soft_copy")
    needed_by = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="hrm_documentrequest_approvals")
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    fulfilled_at = models.DateTimeField(null=True, blank=True, editable=False)
    output_file = models.FileField(upload_to="hrm/requests/documents/%Y/%m/", blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "employee", "status"], name="hrm_docreq_emp_status_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_docreq_tenant_status_idx"),
        ]

    def __str__(self):
        return (f"{self.number} · {self.employee} · {self.get_document_type_display()}"
                if self.number else self.get_document_type_display())
