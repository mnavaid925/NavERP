from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.sales.models._base import *


class LeadNurtureEnrollment(TenantNumbered):
    NUMBER_PREFIX = "LNE"
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("active", "Active"),
        ("paused", "Paused"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("replied", "Replied"),
        ("converted", "Converted"),
    ]
    TRIGGER_KIND_CHOICES = [
        ("manual", "Manual"),
        ("score_threshold", "Score Threshold"),
        ("form_source", "Form Source"),
        ("qualification", "Qualification"),
        ("recycled", "Recycled"),
    ]
    EXIT_REASON_CHOICES = [
        ("qualified", "Qualified"),
        ("disqualified", "Disqualified"),
        ("replied", "Replied"),
        ("converted", "Converted"),
        ("unsubscribed", "Unsubscribed"),
        ("bounced", "Bounced"),
        ("cancelled", "Cancelled"),
        ("completed", "Completed"),
        ("manual", "Manual"),
    ]
    EXIT_REASON_TARGETS = {
        "completed": {"completed"},
        "cancelled": {"cancelled", "qualified", "disqualified", "unsubscribed", "bounced", "manual"},
        "replied": {"replied"},
        "converted": {"converted"},
    }

    lead = models.ForeignKey("crm.Lead", on_delete=models.PROTECT, related_name="sales_nurture_enrollments")
    email_campaign = models.ForeignKey("crm.EmailCampaign", on_delete=models.PROTECT, related_name="sales_nurture_enrollments")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="pending")
    trigger_kind = models.CharField(max_length=20, choices=TRIGGER_KIND_CHOICES, default="manual")
    score_at_enrollment = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)], editable=False)
    consent_purpose = models.ForeignKey("core.ConsentPurpose", on_delete=models.PROTECT, null=True, blank=True, related_name="sales_nurture_enrollments")
    consent_evidence = models.CharField(max_length=255, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="sales_nurture_enrollments")
    started_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_touch_at = models.DateTimeField(null=True, blank=True, editable=False)
    next_touch_at = models.DateTimeField(null=True, blank=True)
    touch_count = models.PositiveIntegerField(default=0, editable=False)
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)
    exit_reason = models.CharField(max_length=20, choices=EXIT_REASON_CHOICES, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "lead", "email_campaign"], name="sales_lne_tenant_lead_campaign_uniq"),
            models.UniqueConstraint(fields=["tenant", "number"], name="sales_lne_tenant_number_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status", "next_touch_at"], name="sales_lne_tnt_status_idx"),
            models.Index(fields=["tenant", "email_campaign", "status"], name="sales_lne_tnt_campaign_idx"),
        ]

    def clean(self):
        super().clean()
        self.consent_evidence = self.consent_evidence or ""
        for field_name in ("lead", "email_campaign", "consent_purpose", "owner"):
            if not self._relation_belongs_to_tenant(field_name):
                raise ValidationError({field_name: "Choose a record from this workspace."})
        if self.email_campaign_id and self.email_campaign.send_type != "drip":
            raise ValidationError({"email_campaign": "Nurture enrollment requires a CRM drip campaign."})
        if self.status in self.EXIT_REASON_TARGETS:
            if self.exit_reason not in self.EXIT_REASON_TARGETS[self.status]:
                raise ValidationError({"exit_reason": "That exit reason is not valid for this status."})
        elif self.exit_reason:
            raise ValidationError({"exit_reason": "An open enrollment cannot have an exit reason."})

    def _relation_belongs_to_tenant(self, field_name):
        if not self.tenant_id:
            return True
        field = self._meta.get_field(field_name)
        related_id = getattr(self, f"{field_name}_id", None)
        if not related_id:
            return True
        related_model = field.remote_field.model
        return related_model._default_manager.filter(pk=related_id, tenant_id=self.tenant_id).exists()

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values(
                "status", "lead_id", "email_campaign_id", "consent_purpose_id", "owner_id", "consent_evidence"
            ).first()
            if previous and previous["status"] != "pending":
                identity = {
                    "lead_id": self.lead_id,
                    "email_campaign_id": self.email_campaign_id,
                    "consent_purpose_id": self.consent_purpose_id,
                    "owner_id": self.owner_id,
                    "consent_evidence": self.consent_evidence or "",
                }
                if any(identity[name] != previous[name] for name in identity):
                    raise ValidationError({"lead": "Enrollment identity is fixed after activation."})
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} · {self.lead.number} · {self.get_status_display()}"
