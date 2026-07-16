"""HRM 3.17 Payout & Reports — Payslipdistribution models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class PayslipDistribution(TenantOwned):
    """Delivery tracking for a ``Payslip`` (3.17) — 1:1. Tracks the send→viewed→downloaded signal chain
    (the actual PDF render + SMTP dispatch are deferred). Created lazily via ``for_payslip()``."""

    DELIVERY_CHANNEL_CHOICES = [
        ("email", "Email"),
        ("portal", "Portal"),
        ("print", "Print"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("viewed", "Viewed"),
        ("downloaded", "Downloaded"),
        ("failed", "Failed"),
    ]

    payslip = models.OneToOneField("hrm.Payslip", on_delete=models.CASCADE, related_name="distribution")
    delivery_channel = models.CharField(max_length=10, choices=DELIVERY_CHANNEL_CHOICES, default="portal")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="pending")
    sent_to_email = models.EmailField(blank=True, editable=False,
        help_text="Snapshot of the employee's email at send time.")
    sent_at = models.DateTimeField(null=True, blank=True, editable=False)
    viewed_at = models.DateTimeField(null=True, blank=True, editable=False)
    downloaded_at = models.DateTimeField(null=True, blank=True, editable=False)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="hrm_payslip_distribution_sends", editable=False)

    class Meta:
        ordering = ["-payslip__cycle__pay_date"]
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_psd_tenant_status_idx"),
        ]

    @classmethod
    def for_payslip(cls, payslip):
        """Get-or-create the one distribution row for ``payslip`` (defaults portal/pending)."""
        obj, _ = cls.objects.get_or_create(
            tenant_id=payslip.tenant_id, payslip=payslip,
            defaults={"delivery_channel": "portal", "status": "pending"})
        return obj

    def __str__(self):
        return f"{self.payslip} · {self.get_status_display()}"
