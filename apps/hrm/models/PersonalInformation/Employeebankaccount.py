"""HRM 3.25 Personal Information — Employeebankaccount models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class EmployeeBankAccount(TenantOwned):
    """3.25 Bank Details — multiple salary/direct-deposit accounts per employee (Gusto/greytHR/ADP
    parity), replacing the single flat ``EmployeeProfile.bank_*`` trio. The highest fraud-risk field
    group: an employee never self-saves here — the model's own create/edit/delete views are
    ``@tenant_admin_required`` and the only employee-initiated path is an ``EmployeeInfoChangeRequest``
    (``request_type="bank"``). ``account_number`` is plaintext for the demo (WARNING below) and is
    NEVER rendered raw — only via ``masked_account_number()``."""

    ACCOUNT_TYPE_CHOICES = [
        ("checking", "Checking / Current"),
        ("savings", "Savings"),
        ("other", "Other"),
    ]
    VERIFICATION_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("verified", "Verified"),
        ("rejected", "Rejected"),
    ]
    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
    ]

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="bank_accounts")
    bank_name = models.CharField(max_length=255)
    account_holder_name = models.CharField(max_length=255)
    # WARNING: account_number is stored in plaintext for demo purposes (mirrors the
    # EmployeeProfile.bank_account note). In production, encrypt at rest (e.g. the tenants
    # EncryptionKey pattern) or store only a tokenized/masked value. NEVER render the raw value —
    # use masked_account_number(). Also redacted from AuditLog.changes via
    # core.crud._SENSITIVE_AUDIT_FIELDS ("account_number").
    account_number = models.CharField(max_length=64)
    routing_number = models.CharField(max_length=20, blank=True, help_text="IFSC / ABA / sort code.")
    account_type = models.CharField(max_length=10, choices=ACCOUNT_TYPE_CHOICES, default="checking")
    is_salary_account = models.BooleanField(default=False, help_text="The account salary is paid into (one per employee).")
    split_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Split-deposit intent (Gusto-style); stored only, not wired to payroll disbursement yet.")
    verification_status = models.CharField(max_length=10, choices=VERIFICATION_STATUS_CHOICES, default="pending",
                                           editable=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["employee", "-is_salary_account", "bank_name"]
        indexes = [models.Index(fields=["tenant", "employee"], name="hrm_eba_tenant_emp_idx")]

    @staticmethod
    def _mask_last4(value):
        """Last-4 view of a sensitive number (duplicated verbatim from EmployeeProfile._mask_last4 —
        per-model duplication convention, not a shared util)."""
        v = value or ""
        return f"••••{v[-4:]}" if len(v) >= 4 else ("••••" if v else "")

    def masked_account_number(self):
        return self._mask_last4(self.account_number)

    def masked_routing_number(self):
        return self._mask_last4(self.routing_number)

    def save(self, *args, **kwargs):
        # Auto-demote so at most one salary account per employee (same pattern as
        # EmergencyContact.is_primary above).
        if self.is_salary_account and self.tenant_id and self.employee_id:
            with transaction.atomic():
                EmployeeBankAccount.objects.filter(
                    tenant_id=self.tenant_id, employee_id=self.employee_id, is_salary_account=True
                ).exclude(pk=self.pk).update(is_salary_account=False)
                return super().save(*args, **kwargs)
        return super().save(*args, **kwargs)

    def __str__(self):
        # Never expose the raw account number, not even in str()/admin/audit-log str(obj).
        return f"{self.bank_name} {self.masked_account_number()} - {self.employee}"
