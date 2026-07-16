"""HRM 3.1 Employee Management — Document models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# 3.1 Employee Management (completion) — EmployeeDocument (personnel-file vault) +
# EmployeeLifecycleEvent (dated job-history timeline). Both FK ``EmployeeProfile``
# (the anchor) — distinct from ``OnboardingDocument`` (program e-sign) and the generic
# ``core.Document``. Children of the employee, not co-equal sub-module entities.
# ---------------------------------------------------------------------------
class EmployeeDocument(TenantNumbered):
    """A personnel-file document for one employee (3.1 Document Management) — ID proof, passport,
    visa, certificate, contract, NDA, etc. ``verification_status`` is workflow-owned (HR verifies/
    rejects); ``is_expired``/``is_expiring_soon`` are derived from ``expires_on``."""

    NUMBER_PREFIX = "EDOC"

    DOCUMENT_TYPE_CHOICES = [
        ("national_id", "National ID / Aadhaar / NRIC"),
        ("passport", "Passport"),
        ("driving_license", "Driving License"),
        ("address_proof", "Address Proof"),
        ("visa", "Visa"),
        ("work_permit", "Work Permit"),
        ("degree_certificate", "Degree / Diploma Certificate"),
        ("professional_cert", "Professional Certification"),
        ("appointment_letter", "Appointment Letter"),
        ("employment_contract", "Employment Contract"),
        ("nda", "Non-Disclosure Agreement"),
        ("non_compete", "Non-Compete Agreement"),
        ("tax_form", "Tax Form (W-4 / Form 16 / TDS)"),
        ("bank_proof", "Bank Account Proof"),
        ("pf_nomination", "PF / Pension Nomination"),
        ("medical_cert", "Medical / Fitness Certificate"),
        ("background_check", "Background Check Report"),
        ("experience_certificate", "Previous Employment / Experience Letter"),
        ("other", "Other"),
    ]
    VERIFICATION_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("verified", "Verified"),
        ("rejected", "Rejected"),
    ]

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPE_CHOICES, default="other")
    title = models.CharField(max_length=255)
    document_number = models.CharField(max_length=100, blank=True, help_text="The alphanumeric ID on the document itself (passport no., PAN, licence no.).")
    issuing_authority = models.CharField(max_length=255, blank=True)
    issuing_country = models.CharField(max_length=100, blank=True)
    issued_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True, help_text="Leave blank for documents that do not expire.")
    is_confidential = models.BooleanField(default=False, help_text="HR-only visibility flag.")
    file = models.FileField(upload_to="hrm/employee_docs/%Y/%m/", null=True, blank=True)
    # Workflow-owned — set only by the mark-verified / reject POST actions, never on the form.
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_STATUS_CHOICES, default="pending", editable=False)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="hrm_verified_documents", editable=False)
    verified_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "employee"], name="hrm_edoc_tenant_emp_idx"),
            models.Index(fields=["tenant", "document_type"], name="hrm_edoc_tenant_type_idx"),
            models.Index(fields=["tenant", "verification_status"], name="hrm_edoc_tenant_vstat_idx"),
            models.Index(fields=["tenant", "expires_on"], name="hrm_edoc_tenant_expiry_idx"),
        ]

    @property
    def is_expired(self):
        """True when the document has an expiry that is already in the past."""
        return self.expires_on is not None and self.expires_on < date.today()

    @property
    def is_expiring_soon(self):
        """True when the document expires within the next 30 days (and is not already expired)."""
        if self.expires_on is None:
            return False
        days = (self.expires_on - date.today()).days
        return 0 <= days <= 30

    def __str__(self):
        return f"{self.number} · {self.title}"
