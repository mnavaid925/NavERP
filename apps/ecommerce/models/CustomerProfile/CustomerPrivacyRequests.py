from datetime import timedelta

from django.db import models
from django.utils import timezone

from apps.ecommerce.models._base import TenantNumbered


class CustomerPrivacyRequest(TenantNumbered):
    NUMBER_PREFIX = "ECPR"

    REQUEST_TYPE_CHOICES = [
        ("access_export", "Right of Access / Data Portability (JSON Export)"),
        ("rectification", "Right to Rectification (Correct Data)"),
        ("erasure_anonymize", "Right to Erasure (GDPR Account Anonymization)"),
        ("restriction", "Right to Restriction of Processing"),
        ("opt_out_sale", "Do Not Sell / Share My Data (CCPA)"),
    ]
    STATUS_CHOICES = [
        ("received", "Received / Awaiting Identity Verification"),
        ("identity_verified", "Identity Verified"),
        ("processing", "Processing Data Query / Erasure"),
        ("completed", "Completed & Delivered"),
        ("rejected", "Rejected / Legally Exempt"),
    ]

    customer = models.ForeignKey(
        "core.Party",
        on_delete=models.PROTECT,
        related_name="ecommerce_privacy_requests",
    )
    request_type = models.CharField(
        max_length=25,
        choices=REQUEST_TYPE_CHOICES,
        default="access_export",
    )
    status = models.CharField(
        max_length=25,
        choices=STATUS_CHOICES,
        default="received",
    )
    statutory_deadline = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    requested_by_email = models.EmailField(blank=True)
    verification_method = models.CharField(max_length=50, blank=True, default="account_login")
    data_export_payload = models.JSONField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecommerce_ecpr_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "customer"], name="idx_ecpr_ten_cust"),
            models.Index(fields=["tenant", "status"], name="idx_ecpr_ten_stat"),
            models.Index(fields=["tenant", "request_type"], name="idx_ecpr_ten_type"),
        ]

    def __str__(self):
        return f"{self.number} - {self.get_request_type_display()} ({self.customer})"

    def save(self, *args, **kwargs):
        if not self.statutory_deadline:
            self.statutory_deadline = (timezone.now() + timedelta(days=30)).date()
        if self.status == "completed" and not self.completed_at:
            self.completed_at = timezone.now()
        super().save(*args, **kwargs)
