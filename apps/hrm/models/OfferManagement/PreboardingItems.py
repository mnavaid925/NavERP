"""HRM 3.8 Offer Management — PreboardingItems models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.OfferManagement.PREBOARDING_DOC_TYPE_CHOICESs import PREBOARDING_DOC_TYPE_CHOICES
from apps.hrm.models.OfferManagement.PREBOARDING_STATUS_CHOICESs import PREBOARDING_STATUS_CHOICES
from apps.hrm.models.OfferManagement.PREBOARDING_DOC_TYPE_CHOICESs import PREBOARDING_DOC_TYPE_CHOICES
from apps.hrm.models.OfferManagement.PREBOARDING_STATUS_CHOICESs import PREBOARDING_STATUS_CHOICES


class PreboardingItem(TenantOwned):
    """A pre-start document-collection line tied to an accepted ``Offer`` (3.8). Deliberately distinct from
    the post-start 3.3 ``OnboardingDocument`` (that owns collection from day one onward; this is pre-join,
    offer-tied, and largely candidate-self-service). Managed inline on the offer detail hub (add/remove/
    submit/verify/reject + send-invite POST actions) — no standalone pages. ``status`` is workflow-owned;
    ``reminder_sent_at`` is stamped by the manual send-invite action (Celery auto-dispatch deferred)."""

    offer = models.ForeignKey("hrm.Offer", on_delete=models.CASCADE, related_name="preboarding_items")
    document_type = models.CharField(max_length=30, choices=PREBOARDING_DOC_TYPE_CHOICES, default="other")
    is_required = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=PREBOARDING_STATUS_CHOICES, default="pending",
                              editable=False)
    uploaded_file = models.FileField(upload_to="hrm/offers/preboarding/%Y/%m/", null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True, editable=False)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="verified_preboarding_items", editable=False)
    verified_at = models.DateTimeField(null=True, blank=True, editable=False)
    reminder_sent_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["document_type", "pk"]
        indexes = [
            models.Index(fields=["tenant", "offer"], name="hrm_pbi_tenant_ofr_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_pbi_tenant_status_idx"),
        ]

    def __str__(self):
        return f"{self.get_document_type_display()} ({self.get_status_display()})"
