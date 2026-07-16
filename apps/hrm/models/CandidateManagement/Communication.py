"""HRM 3.6 Candidate Management — Communication models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.CandidateManagement.DELIVERY_STATUS_CHOICESs import DELIVERY_STATUS_CHOICES
from apps.hrm.models.CandidateManagement.DELIVERY_STATUS_CHOICESs import DELIVERY_STATUS_CHOICES


COMMUNICATION_CHANNEL_CHOICES = [
    ("email", "Email"),
    ("sms", "SMS"),
    ("whatsapp", "WhatsApp"),
]


COMMUNICATION_DIRECTION_CHOICES = [
    ("outbound", "Outbound"),
    ("inbound", "Inbound"),
]


class CandidateCommunication(TenantNumbered):
    """Append-only typed communication log (3.6). Created only by the send-email POST action /
    ``_send_candidate_email`` helper (no create form; admin blocks add/change). ``sent_by=None`` marks a
    system auto-send. Distinct from the broader ``core.Activity`` ledger — this is the ATS email trail."""

    NUMBER_PREFIX = "CC"

    candidate = models.ForeignKey("hrm.CandidateProfile", on_delete=models.CASCADE, related_name="communications")
    application = models.ForeignKey("hrm.JobApplication", on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="communications")
    template = models.ForeignKey("hrm.CandidateEmailTemplate", on_delete=models.SET_NULL, null=True,
                                 blank=True, related_name="communications")
    channel = models.CharField(max_length=10, choices=COMMUNICATION_CHANNEL_CHOICES, default="email")
    direction = models.CharField(max_length=10, choices=COMMUNICATION_DIRECTION_CHOICES, default="outbound")
    subject = models.CharField(max_length=500, blank=True)
    body = models.TextField()
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="candidate_communications")
    sent_at = models.DateTimeField(auto_now_add=True)
    delivery_status = models.CharField(max_length=10, choices=DELIVERY_STATUS_CHOICES, default="sent")

    class Meta:
        ordering = ["-sent_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "candidate"], name="hrm_cc_tenant_cand_idx"),
            models.Index(fields=["tenant", "application"], name="hrm_cc_tenant_app_idx"),
            models.Index(fields=["tenant", "delivery_status"], name="hrm_cc_tenant_dstatus_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.get_channel_display()} → {self.candidate.name}"
