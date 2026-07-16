"""HRM 3.1 Employee Management — EmployeeProfiles models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# 3.1 Employee Management — EmployeeProfile (anchor; 1:1 over core.Party/Employment)
# ---------------------------------------------------------------------------
class EmployeeProfile(TenantNumbered):
    """The HRM employee record (3.1) — a 1:1 extension of ``core.Party`` + ``core.Employment``.
    All other HRM models FK to this, never to ``core.Party`` directly."""

    NUMBER_PREFIX = "EMP"

    EMPLOYEE_TYPE_CHOICES = [
        ("full_time", "Full Time"),
        ("part_time", "Part Time"),
        ("contract", "Contract"),
        ("intern", "Intern"),
        ("consultant", "Consultant"),
    ]
    GENDER_CHOICES = [
        ("male", "Male"),
        ("female", "Female"),
        ("other", "Other"),
        ("prefer_not_to_say", "Prefer Not to Say"),
    ]
    BLOOD_GROUP_CHOICES = [
        ("A+", "A+"), ("A-", "A-"), ("B+", "B+"), ("B-", "B-"),
        ("AB+", "AB+"), ("AB-", "AB-"), ("O+", "O+"), ("O-", "O-"),
    ]
    MARITAL_STATUS_CHOICES = [
        ("single", "Single"),
        ("married", "Married"),
        ("divorced", "Divorced"),
        ("widowed", "Widowed"),
        ("other", "Other"),
    ]

    party = models.OneToOneField("core.Party", on_delete=models.CASCADE, related_name="employee_profile")
    employment = models.OneToOneField("core.Employment", on_delete=models.SET_NULL, null=True, blank=True, related_name="employee_profile")
    designation = models.ForeignKey("hrm.Designation", on_delete=models.SET_NULL, null=True, blank=True, related_name="employees")
    employee_type = models.CharField(max_length=20, choices=EMPLOYEE_TYPE_CHOICES, default="full_time")
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    blood_group = models.CharField(max_length=5, choices=BLOOD_GROUP_CHOICES, blank=True)
    nationality = models.CharField(max_length=100, blank=True)
    personal_email = models.EmailField(blank=True)
    mobile = models.CharField(max_length=30, blank=True)
    # WARNING: bank_account / bank_routing are stored in plaintext for demo purposes. In
    # production, encrypt at rest (e.g. via the tenants EncryptionKey pattern) or store only a
    # tokenized/masked value. Never render the raw account number — use masked_bank_account().
    # Both are also redacted from AuditLog.changes (see core.crud._SENSITIVE_AUDIT_FIELDS).
    bank_name = models.CharField(max_length=255, blank=True)
    bank_account = models.CharField(max_length=64, blank=True)
    bank_routing = models.CharField(max_length=20, blank=True)
    probation_end_date = models.DateField(null=True, blank=True)
    confirmed_on = models.DateField(null=True, blank=True)
    notice_period_days = models.PositiveSmallIntegerField(null=True, blank=True,
        help_text="Profile-default notice period; a SeparationCase can override it per departure.")
    emergency_contact_name = models.CharField(max_length=255, blank=True)
    emergency_contact_phone = models.CharField(max_length=30, blank=True)
    emergency_contact_relation = models.CharField(max_length=100, blank=True)
    # Second emergency contact (most HRIS products support ≥2).
    emergency_contact_2_name = models.CharField(max_length=255, blank=True)
    emergency_contact_2_phone = models.CharField(max_length=30, blank=True)
    emergency_contact_2_relation = models.CharField(max_length=100, blank=True)
    # Personnel-file fields (3.1 completion — competitive HRIS parity).
    marital_status = models.CharField(max_length=20, choices=MARITAL_STATUS_CHOICES, blank=True)
    work_email = models.EmailField(blank=True, help_text="Company email, distinct from personal_email.")
    work_location = models.CharField(max_length=255, blank=True, help_text="Office / site / remote assignment.")
    father_name = models.CharField(max_length=255, blank=True)
    spouse_name = models.CharField(max_length=255, blank=True)
    # WARNING: national_id / passport_number are sensitive PII stored in plaintext for the demo —
    # encrypt at rest in production (mirror the bank_account note above). The full ID documents live
    # in EmployeeDocument; these are the quick-reference values on the profile.
    national_id = models.CharField(max_length=100, blank=True)
    national_id_type = models.CharField(max_length=50, blank=True, help_text="e.g. Aadhaar, SSN, NRIC, PAN.")
    passport_number = models.CharField(max_length=50, blank=True)
    passport_expiry = models.DateField(null=True, blank=True)
    current_address = models.TextField(blank=True)
    permanent_address = models.TextField(blank=True)
    photo = models.ImageField(upload_to="hrm/photos/%Y/%m/", null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["party__name"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "employee_type"], name="hrm_emp_tenant_type_idx"),
            models.Index(fields=["tenant", "designation"], name="hrm_emp_tenant_desig_idx"),
        ]

    @property
    def department(self):
        """Convenience accessor — the department lives on the linked core.Employment."""
        return self.employment.org_unit if self.employment_id else None

    @property
    def manager(self):
        return self.employment.manager if self.employment_id else None

    @property
    def name(self):
        return self.party.name if self.party_id else ""

    @staticmethod
    def _mask_last4(value):
        v = value or ""
        return f"••••{v[-4:]}" if len(v) >= 4 else ("••••" if v else "")

    def masked_bank_account(self):
        """Last-4 view of the account number (never render the full value)."""
        return self._mask_last4(self.bank_account)

    def masked_bank_routing(self):
        """Last-4 view of the routing number (never render the full value)."""
        return self._mask_last4(self.bank_routing)

    def masked_national_id(self):
        """Last-4 view of the national ID (sensitive PII — never render the full value)."""
        return self._mask_last4(self.national_id)

    def masked_passport_number(self):
        """Last-4 view of the passport number (sensitive PII — never render the full value)."""
        return self._mask_last4(self.passport_number)

    def __str__(self):
        return f"{self.number} · {self.party.name}" if self.party_id else self.number
