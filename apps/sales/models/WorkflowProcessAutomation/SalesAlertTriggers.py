"""Sales 8.17 — SalesAlertTrigger model."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.sales.models._base import TenantNumbered
from apps.sales.models.WorkflowProcessAutomation.SalesProcessDefinitions import (
    TARGET_ENTITY_CHOICES,
    _relation_belongs_to_tenant,
    validate_process_conditions,
)

# 8.16 MobileDealAlert.ALERT_TYPE_CHOICES is CLOSED (its module-level constant is already
# re-exported from apps/sales/models/__init__.py), so every SAT alert type maps onto an
# existing MDA value instead of extending the 8.16 constant (contract §10 deviation 9).
# Verified against apps/sales/models/MobileSales/MobileDealAlerts.py.
SAT_TO_MDA_ALERT_TYPE = {
    "deal_inactivity": "checkin_reminder",
    "stage_change": "deal_stage_changed",
    "milestone": "attainment_milestone",
    "approval_requested": "quote_approval_required",
    "sla_breach": "checkin_reminder",
    "contract_expiry": "contract_expiring",
    "quota_attainment": "attainment_milestone",
}


class SalesAlertTrigger(TenantNumbered):
    """Sales-scoped alert trigger.

    AUDIENCE_KIND_CHOICES is a sales-scoped variant of core.NotificationRule.AUDIENCE_CHOICES
    (Notification.py:95 = role / user / party / all): here ``owner`` (the record's owning rep)
    REPLACES core's ``party``, because a sales alert audience is the deal owner, not the
    customer party. This divergence is intentional, not drift.
    """

    NUMBER_PREFIX = "SAT"

    ALERT_TYPE_CHOICES = [
        ("deal_inactivity", "Deal Inactivity"),
        ("stage_change", "Stage Change"),
        ("milestone", "Milestone Reached"),
        ("approval_requested", "Approval Requested"),
        ("sla_breach", "SLA Breach"),
        ("contract_expiry", "Contract Expiry"),
        ("quota_attainment", "Quota Attainment"),
    ]
    SEVERITY_CHOICES = [
        ("low", "Low Priority"),
        ("normal", "Normal"),
        ("high", "High Priority"),
        ("urgent", "Urgent Action Required"),
    ]
    AUDIENCE_KIND_CHOICES = [
        ("role", "Everyone holding a role"),
        ("user", "Named users"),
        ("owner", "The record owner"),
        ("all", "Everyone in the workspace"),
    ]

    name = models.CharField(max_length=200)
    alert_type = models.CharField(max_length=24, choices=ALERT_TYPE_CHOICES, default="deal_inactivity")
    target_entity = models.CharField(max_length=16, choices=TARGET_ENTITY_CHOICES)
    conditions = models.JSONField(default=list, blank=True)
    inactivity_days = models.PositiveSmallIntegerField(null=True, blank=True)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default="normal")
    audience_kind = models.CharField(max_length=10, choices=AUDIENCE_KIND_CHOICES, default="all")
    audience_role = models.ForeignKey(
        "accounts.Role",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_wpa_audience_roles",
    )
    audience_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="sales_wpa_alert_audiences",
    )
    notification_rule = models.ForeignKey(
        "core.NotificationRule",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_wpa_alert_triggers",
    )
    cooldown_hours = models.PositiveSmallIntegerField(default=24)
    last_evaluated_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_fired_at = models.DateTimeField(null=True, blank=True, editable=False)
    fire_count = models.PositiveIntegerField(default=0, editable=False)
    priority = models.PositiveSmallIntegerField(default=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["priority", "name", "id"]
        indexes = [
            models.Index(fields=["tenant", "alert_type", "is_active"], name="sales_sat_tnt_type_idx"),
        ]

    def is_on_cooldown(self, now=None):
        if self.last_fired_at is None:
            return False
        now = now or timezone.now()
        return self.last_fired_at + timezone.timedelta(hours=self.cooldown_hours) > now

    def mark_evaluated(self, now=None):
        self.last_evaluated_at = now or timezone.now()
        self.save(update_fields=["last_evaluated_at", "updated_at"])

    def mark_fired(self, now=None):
        now = now or timezone.now()
        self.last_fired_at = now
        self.last_evaluated_at = now
        self.fire_count += 1
        self.save(update_fields=["last_fired_at", "last_evaluated_at", "fire_count", "updated_at"])

    def clean(self):
        super().clean()
        self.conditions = validate_process_conditions(self.conditions, is_catch_all=True)
        if not _relation_belongs_to_tenant(self, "audience_role"):
            raise ValidationError({"audience_role": "Choose a role from this workspace."})
        if not _relation_belongs_to_tenant(self, "notification_rule"):
            raise ValidationError({"notification_rule": "Choose a notification rule from this workspace."})
        if self.audience_kind == "role" and not self.audience_role_id:
            raise ValidationError({"audience_role": "A role-audience trigger needs a role."})
        if self.alert_type in {"deal_inactivity", "sla_breach"} and not self.inactivity_days:
            raise ValidationError({"inactivity_days": "An inactivity trigger needs a day window."})
        if self.pk and self.audience_kind == "user" and not self.audience_users.exists():
            raise ValidationError({"audience_users": "A user-audience trigger needs at least one recipient."})

    def __str__(self):
        return f"{self.number} — {self.name}"
