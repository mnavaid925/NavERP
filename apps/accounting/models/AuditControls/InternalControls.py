"""Accounting 2.14 Audit & Controls — InternalControls models (split from models.py/models_advanced.py)."""
from apps.accounting.models._base import *  # noqa: F401,F403


# ================================================================= 2.14 Audit & Controls
class InternalControl(TenantOwned):
    """A documented SOX-style internal control with its latest test result (audit trail reuses
    ``core.AuditLog``)."""

    CONTROL_TYPE_CHOICES = [("preventive", "Preventive"), ("detective", "Detective"), ("corrective", "Corrective")]
    FREQUENCY_CHOICES = [("transactional", "Per Transaction"), ("daily", "Daily"), ("monthly", "Monthly"),
                         ("quarterly", "Quarterly"), ("annual", "Annual")]
    RISK_CHOICES = [("low", "Low"), ("medium", "Medium"), ("high", "High")]
    RESULT_CHOICES = [("na", "Not Tested"), ("pass", "Pass"), ("fail", "Fail")]
    STATUS_CHOICES = [("active", "Active"), ("inactive", "Inactive")]

    code = models.CharField(max_length=40)
    name = models.CharField(max_length=255)
    control_type = models.CharField(max_length=12, choices=CONTROL_TYPE_CHOICES, default="preventive")
    frequency = models.CharField(max_length=14, choices=FREQUENCY_CHOICES, default="monthly")
    risk_level = models.CharField(max_length=8, choices=RISK_CHOICES, default="medium")
    owner = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="owned_controls")
    last_tested_date = models.DateField(null=True, blank=True)
    last_result = models.CharField(max_length=4, choices=RESULT_CHOICES, default="na")
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default="active")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]
        unique_together = ("tenant", "code")
        indexes = [models.Index(fields=["tenant", "status"], name="acc_ctrl_tenant_status_idx")]

    def __str__(self):
        return f"{self.code} · {self.name}"
