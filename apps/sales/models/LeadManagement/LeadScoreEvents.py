from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.sales.models._base import *


def _relation_belongs_to_tenant(instance, field_name):
    if not instance.tenant_id:
        return True
    field = instance._meta.get_field(field_name)
    related_id = getattr(instance, f"{field_name}_id", None)
    if not related_id:
        return True
    related_model = field.remote_field.model
    return related_model._default_manager.filter(pk=related_id, tenant_id=instance.tenant_id).exists()


class LeadScoreEvent(TenantEventOwned):
    SIGNAL_CATEGORY_CHOICES = [
        ("behavioral", "Behavioral"),
        ("demographic", "Demographic"),
        ("qualification", "Qualification"),
        ("manual", "Manual"),
        ("decay", "Decay"),
        ("correction", "Correction"),
    ]
    EVENT_TYPE_CHOICES = [
        ("form_submitted", "Form Submitted"),
        ("email_open", "Email Open"),
        ("email_click", "Email Click"),
        ("web_visit", "Website Visit"),
        ("content_download", "Content Download"),
        ("event_attendance", "Event Attendance"),
        ("meeting_booked", "Meeting Booked"),
        ("demo_request", "Demo Request"),
        ("call_connected", "Call Connected"),
        ("reply_received", "Reply Received"),
        ("fit_match", "Fit Match"),
        ("fit_mismatch", "Fit Mismatch"),
        ("unsubscribe", "Unsubscribe"),
        ("manual_adjustment", "Manual Adjustment"),
        ("decay", "Score Decay"),
        ("correction", "Correction"),
    ]
    SOURCE_KIND_CHOICES = [
        ("form_submission", "Form Submission"),
        ("campaign_member", "Campaign Member"),
        ("communication_log", "Communication Log"),
        ("qualification", "Qualification"),
        ("web_tracking", "Web Tracking"),
        ("api", "API"),
        ("manual", "Manual"),
    ]

    lead = models.ForeignKey("crm.Lead", on_delete=models.PROTECT, related_name="sales_score_events")
    signal_category = models.CharField(max_length=20, choices=SIGNAL_CATEGORY_CHOICES)
    event_type = models.CharField(max_length=32, choices=EVENT_TYPE_CHOICES)
    score_delta = models.SmallIntegerField(validators=[MinValueValidator(-100), MaxValueValidator(100)])
    source_kind = models.CharField(max_length=20, choices=SOURCE_KIND_CHOICES)
    source_ref = models.CharField(max_length=255, blank=True)
    reason = models.TextField(blank=True)
    effective_until = models.DateTimeField(null=True, blank=True)
    idempotency_key = models.CharField(max_length=120, null=True, blank=True)
    corrects_event = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="corrections")
    occurred_at = models.DateTimeField(default=timezone.now, editable=False)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="sales_recorded_score_events")

    class Meta:
        ordering = ["-occurred_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "idempotency_key"], name="sales_lse_tenant_key_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "lead", "-occurred_at"], name="sales_lse_tnt_lead_idx"),
            models.Index(fields=["tenant", "event_type", "-occurred_at"], name="sales_lse_tnt_type_idx"),
            models.Index(fields=["tenant", "source_kind", "source_ref"], name="sales_lse_tnt_source_idx"),
        ]

    def clean(self):
        super().clean()
        self.idempotency_key = (self.idempotency_key or "").strip() or None
        if not _relation_belongs_to_tenant(self, "lead"):
            raise ValidationError({"lead": "The lead must belong to this workspace."})
        if not _relation_belongs_to_tenant(self, "recorded_by"):
            raise ValidationError({"recorded_by": "The recorder must belong to this workspace."})
        if self.event_type in {"manual_adjustment", "correction"} and not (self.reason or "").strip():
            raise ValidationError({"reason": "A reason is required for manual and correction events."})
        if self.event_type == "correction" and not self.corrects_event_id:
            raise ValidationError({"corrects_event": "A correction must identify the event it corrects."})
        if self.event_type != "correction" and self.corrects_event_id:
            raise ValidationError({"corrects_event": "Only correction events may correct another event."})
        if self.corrects_event_id:
            if self.pk and self.corrects_event_id == self.pk:
                raise ValidationError({"corrects_event": "An event cannot correct itself."})
            if not _relation_belongs_to_tenant(self, "corrects_event"):
                raise ValidationError({"corrects_event": "The corrected event must belong to this workspace."})
            if self.lead_id and self.corrects_event.lead_id != self.lead_id:
                raise ValidationError({"corrects_event": "The corrected event must belong to the same lead."})

    def save(self, *args, **kwargs):
        if self.corrects_event_id and type(self).objects.filter(corrects_event_id=self.corrects_event_id).exclude(pk=self.pk).exists():
            raise ValidationError({"corrects_event": "That score event has already been corrected."})
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.lead.number} · {self.get_event_type_display()} ({self.score_delta:+d})"
