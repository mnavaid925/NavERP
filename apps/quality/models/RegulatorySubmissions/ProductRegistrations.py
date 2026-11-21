from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Index, UniqueConstraint
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class ProductRegistration(TenantNumbered):
    NUMBER_PREFIX = "QREG"

    REGISTRATION_TYPE_CHOICES = [
        ("product_license", "Product License / Clearance"),
        ("establishment_reg", "Establishment Registration"),
        ("national_listing", "National Device Listing"),
        ("ce_certificate", "CE Certificate (Notified Body)"),
        ("import_permit", "Import / Export Permit"),
    ]

    STATUS_CHOICES = [
        ("active", "Active / Authorized"),
        ("pending_renewal", "Pending Renewal"),
        ("in_application", "In Application"),
        ("suspended", "Suspended"),
        ("expired", "Expired"),
        ("withdrawn", "Withdrawn"),
    ]

    STATUS_CSS = {
        "active": "badge-green",
        "pending_renewal": "badge-amber",
        "in_application": "badge-info",
        "suspended": "badge-red",
        "expired": "badge-red",
        "withdrawn": "badge-slate",
    }

    registration_title = models.CharField(max_length=255)
    registration_type = models.CharField(
        max_length=30, choices=REGISTRATION_TYPE_CHOICES, default="product_license"
    )
    jurisdiction_country = models.CharField(
        max_length=100, help_text="Target Country / Economic Region e.g. USA, European Union, Canada, Japan"
    )
    regulatory_authority = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="authorized_registrations",
    )
    authorized_representative = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="represented_registrations",
        help_text="EU AR, UKRP, or local in-country sponsor",
    )
    product_name = models.CharField(max_length=255)
    product_code = models.CharField(max_length=100, blank=True, db_index=True)
    intended_purpose = models.TextField(blank=True)
    license_certificate_number = models.CharField(max_length=100, blank=True, db_index=True)
    establishment_id = models.CharField(
        max_length=100, blank=True, help_text="FEI, SRN, or National Establishment Identifier"
    )
    status = models.CharField(
        max_length=25, choices=STATUS_CHOICES, default="in_application"
    )
    initial_approval_date = models.DateField(null=True, blank=True)
    effective_date = models.DateField(null=True, blank=True)
    expiration_date = models.DateField(null=True, blank=True)
    renewal_due_date = models.DateField(null=True, blank=True, db_index=True)
    renewal_lead_days = models.PositiveIntegerField(default=90)
    regulatory_lead = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_registrations",
    )
    linked_submission = models.ForeignKey(
        "quality.RegulatorySubmission",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="product_registrations",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["product_name", "jurisdiction_country", "number"]
        verbose_name = "Product Registration"
        verbose_name_plural = "Product Registrations"
        constraints = [
            UniqueConstraint(fields=["tenant", "number"], name="quality_qreg_ten_num_uniq"),
        ]
        indexes = [
            Index(fields=["tenant", "status"], name="idx_qreg_ten_status"),
            Index(fields=["tenant", "status", "expiration_date"], name="idx_qreg_ten_stat_exp"),
            Index(fields=["tenant", "registration_type"], name="idx_qreg_ten_type"),
            Index(fields=["tenant", "jurisdiction_country"], name="idx_qreg_ten_juris"),
            Index(fields=["tenant", "expiration_date"], name="idx_qreg_ten_exp"),
        ]

    def __str__(self):
        return f"{self.number} — {self.product_name} ({self.jurisdiction_country})"

    @property
    def is_active(self):
        return self.status == "active"

    @property
    def days_to_expiration(self):
        if not self.expiration_date:
            return None
        return (self.expiration_date - timezone.now().date()).days

    @property
    def is_overdue_renewal(self):
        if not self.renewal_due_date:
            return False
        return self.status in ["active", "pending_renewal"] and self.renewal_due_date < timezone.now().date()

    @property
    def urgency_status(self):
        days = self.days_to_expiration
        if days is None:
            return "normal"
        if days < 0:
            return "expired"
        if days <= 30:
            return "urgent"
        if days <= 90:
            return "warning"
        return "normal"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")
