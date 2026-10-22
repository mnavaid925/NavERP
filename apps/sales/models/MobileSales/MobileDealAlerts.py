"""Sales 8.16 — MobileDealAlert model."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.sales.models._base import TenantNumbered

ALERT_TYPE_CHOICES = [
    ("deal_stage_changed", "Deal Stage Advanced"),
    ("quote_approval_required", "Quote Discount Approval Required"),
    ("route_dispatched", "Daily Route Assigned"),
    ("checkin_reminder", "Check-In Reminder"),
    ("attainment_milestone", "Quota Attainment Milestone"),
    ("contract_expiring", "Contract Expiring Soon"),
]

URGENCY_CHOICES = [
    ("low", "Low Priority"),
    ("normal", "Normal"),
    ("high", "High Priority"),
    ("urgent", "Urgent Action Required"),
]

PUSH_STATUS_CHOICES = [
    ("pending", "Pending Dispatch"),
    ("sent", "Dispatched"),
    ("delivered", "Delivered"),
    ("failed", "Delivery Failed"),
]


class MobileDealAlert(TenantNumbered):
    NUMBER_PREFIX = "MDA"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mobile_deal_alerts",
    )
    device = models.ForeignKey(
        "sales.MobileDeviceSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_alerts",
    )
    alert_type = models.CharField(
        max_length=30,
        choices=ALERT_TYPE_CHOICES,
        default="deal_stage_changed",
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    urgency = models.CharField(
        max_length=20,
        choices=URGENCY_CHOICES,
        default="normal",
    )
    related_opportunity = models.ForeignKey(
        "crm.Opportunity",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mobile_alerts",
    )
    related_quote = models.ForeignKey(
        "sales.CPQQuote",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mobile_alerts",
    )
    related_route = models.ForeignKey(
        "sales.FieldSalesRoute",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mobile_alerts",
    )
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    push_status = models.CharField(
        max_length=20,
        choices=PUSH_STATUS_CHOICES,
        default="pending",
    )
    push_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="sales_mda_ten_num_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "recipient"], name="sales_mda_ten_rec_idx"),
            models.Index(fields=["tenant", "alert_type"], name="sales_mda_ten_type_idx"),
            models.Index(fields=["tenant", "is_read"], name="sales_mda_ten_read_idx"),
            models.Index(fields=["tenant", "urgency"], name="sales_mda_ten_urg_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title} ({self.get_urgency_display()})"

    def clean(self):
        super().clean()
        if self.tenant_id:
            for fk_field, rel_name in [
                ("recipient", "Recipient User"),
                ("device", "Mobile Device"),
                ("related_opportunity", "Opportunity"),
                ("related_quote", "CPQ Quote"),
                ("related_route", "Sales Route"),
            ]:
                obj = getattr(self, fk_field, None)
                if obj and getattr(obj, "tenant_id", None) and obj.tenant_id != self.tenant_id:
                    raise ValidationError({fk_field: f"{rel_name} belongs to another workspace."})

    def mark_as_read(self):
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=["is_read", "read_at", "updated_at"])

    def dispatch_alert(self):
        self.push_status = "sent"
        self.push_sent_at = timezone.now()
        self.save(update_fields=["push_status", "push_sent_at", "updated_at"])
