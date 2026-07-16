"""HRM 3.8 Offer Management — Backgroundverification models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.OfferManagement.BGV_CHECK_TYPE_CHOICESs import BGV_CHECK_TYPE_CHOICES
from apps.hrm.models.OfferManagement.BGV_RESULT_CHOICESs import BGV_RESULT_CHOICES
from apps.hrm.models.OfferManagement.BGV_STATUS_CHOICESs import BGV_STATUS_CHOICES
from apps.hrm.models.OfferManagement.BGV_VENDOR_CHOICESs import BGV_VENDOR_CHOICES
from apps.hrm.models.OfferManagement.BGV_CHECK_TYPE_CHOICESs import BGV_CHECK_TYPE_CHOICES
from apps.hrm.models.OfferManagement.BGV_RESULT_CHOICESs import BGV_RESULT_CHOICES
from apps.hrm.models.OfferManagement.BGV_STATUS_CHOICESs import BGV_STATUS_CHOICES
from apps.hrm.models.OfferManagement.BGV_VENDOR_CHOICESs import BGV_VENDOR_CHOICES


class BackgroundVerification(TenantNumbered):
    """A background/reference check ordered on an ``Offer`` (3.8). ``status`` (the Checkr/Sterling
    standardized lifecycle) and ``result`` (Clear/Consider) are orthogonal workflow-owned fields a manual
    action (or a future vendor webhook) writes to — live vendor API ordering/webhooks are DEFERRED.
    Candidate identity data is read through ``offer.application.candidate`` — never re-stored here (no PII
    duplication). The formal adverse-action/dispute compliance sub-flow is out of scope this pass."""

    NUMBER_PREFIX = "BGV"

    offer = models.ForeignKey("hrm.Offer", on_delete=models.CASCADE, related_name="background_checks")
    vendor = models.CharField(max_length=30, choices=BGV_VENDOR_CHOICES, blank=True)
    check_type = models.CharField(max_length=30, choices=BGV_CHECK_TYPE_CHOICES, default="employment")
    status = models.CharField(max_length=20, choices=BGV_STATUS_CHOICES, default="not_started",
                              editable=False)
    result = models.CharField(max_length=20, choices=BGV_RESULT_CHOICES, blank=True)
    consent_given = models.BooleanField(default=False)
    consent_date = models.DateTimeField(null=True, blank=True, editable=False)
    report_file = models.FileField(upload_to="hrm/offers/bgv_reports/%Y/%m/", null=True, blank=True)
    initiated_at = models.DateTimeField(null=True, blank=True, editable=False)
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)
    initiated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                     blank=True, related_name="initiated_bgv_checks", editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_bgv_tenant_status_idx"),
            models.Index(fields=["tenant", "offer"], name="hrm_bgv_tenant_ofr_idx"),
            models.Index(fields=["tenant", "check_type"], name="hrm_bgv_tenant_type_idx"),
            # Backs the default -created_at ordering under the tenant filter (mirrors Offer's index).
            models.Index(fields=["tenant", "created_at"], name="hrm_bgv_tenant_created_idx"),
        ]

    @property
    def is_completed(self):
        return self.status == "completed"

    def __str__(self):
        return f"{self.number} · {self.get_check_type_display()}" if self.number else self.get_check_type_display()
