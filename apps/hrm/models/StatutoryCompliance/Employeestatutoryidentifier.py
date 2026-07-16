"""HRM 3.15 Statutory Compliance — Employeestatutoryidentifier models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.StatutoryCompliance.INDIAN_STATE_CHOICESs import INDIAN_STATE_CHOICES
from apps.hrm.models.StatutoryCompliance.INDIAN_STATE_CHOICESs import INDIAN_STATE_CHOICES


class EmployeeStatutoryIdentifier(TenantOwned):
    """Per-employee government-issued statutory identifiers (3.15) — a 1:1 companion to
    ``EmployeeProfile`` for the UAN/PF/ESI numbers that don't fit the generic
    ``EmployeeProfile.national_id`` (PAN) field. Created lazily (get-or-create) — not every
    employee needs every identifier filled at once.

    WARNING: ``uan_number``/``pf_number``/``esi_number`` are sensitive government IDs — they are
    added to ``apps.core.crud._SENSITIVE_AUDIT_FIELDS`` so they are redacted from AuditLog.changes
    (mirroring national_id/passport_number). Encrypt at rest in production."""

    employee = models.OneToOneField(
        "hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="statutory_identifiers")
    uan_number = models.CharField(max_length=20, blank=True,
        help_text="PF Universal Account Number (lifelong, distinct from the establishment PF number).")
    pf_number = models.CharField(max_length=30, blank=True,
        help_text="Establishment-specific PF account/member ID.")
    esi_number = models.CharField(max_length=20, blank=True,
        help_text="ESI Insurance Number (blank if the employee is above the ESI ceiling / exempt).")
    pt_state = models.CharField(max_length=50, choices=INDIAN_STATE_CHOICES, blank=True,
        help_text="Resolves which PT/LWF StatutoryStateRule applies; falls back to the config default.")
    is_pf_applicable = models.BooleanField(default=True)
    is_esi_applicable = models.BooleanField(default=True)

    class Meta:
        ordering = ["employee__party__name"]
        indexes = [
            models.Index(fields=["tenant", "employee"], name="hrm_empstat_tenant_emp_idx"),
        ]

    @staticmethod
    def _mask_last4(value):
        """Last-4 masked view of a sensitive ID (mirrors EmployeeProfile._mask_last4)."""
        v = value or ""
        return f"••••{v[-4:]}" if len(v) >= 4 else ("••••" if v else "")

    def masked_uan_number(self):
        """Last-4 view of the UAN (lifelong government ID — never render the full value in the UI)."""
        return self._mask_last4(self.uan_number)

    def masked_pf_number(self):
        return self._mask_last4(self.pf_number)

    def masked_esi_number(self):
        return self._mask_last4(self.esi_number)

    def __str__(self):
        return f"Statutory IDs · {self.employee}"
