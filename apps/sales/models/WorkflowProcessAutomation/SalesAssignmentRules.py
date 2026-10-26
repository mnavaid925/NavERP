"""Sales 8.17 — SalesAssignmentRule model."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.accounts.models import User
from apps.sales.models._base import TenantNumbered
from apps.sales.models.WorkflowProcessAutomation.SalesProcessDefinitions import (
    _relation_belongs_to_tenant,
    validate_process_conditions,
)


class SalesAssignmentRule(TenantNumbered):
    """Auto-assignment rule register (NavERP.md 8.17 bullet 2).

    DOMAIN RULING (8.1 research, binding): ``target_entity`` includes ``lead``, but CRM owns
    ``crm.Lead`` and sub-module 8.1 already ships the race-safe lead-owner resolver
    ``apps.sales.services.route_lead`` (``select_for_update`` on the lead AND on the
    ``sales.LeadRoutingRule`` row, cursor advanced inside that lock). Any future assignment
    resolution for ``lead`` targets MUST delegate to that 8.1 ``LeadRoutingRule`` decision path
    and MUST NEVER create a second lead-owner decision here. This pass ships the rule register
    + CRUD only — no owner-assignment resolution (contract §3.2).
    """

    NUMBER_PREFIX = "SAR"

    TARGET_ENTITY_CHOICES = [("lead", "Lead"), ("opportunity", "Opportunity"), ("case", "Case")]
    MATCH_MODE_CHOICES = [("all", "All conditions"), ("any", "Any condition")]
    ASSIGNMENT_MODE_CHOICES = [
        ("fixed_owner", "Fixed Owner"),
        ("round_robin", "Round Robin"),
        ("load_balanced", "Load Balanced"),
        ("territory_manager", "Territory Manager"),
        ("escalate_manager", "Escalate to Manager"),
    ]

    name = models.CharField(max_length=200)
    target_entity = models.CharField(max_length=16, choices=TARGET_ENTITY_CHOICES)
    match_mode = models.CharField(max_length=8, choices=MATCH_MODE_CHOICES, default="all")
    conditions = models.JSONField(default=list, blank=True)
    is_catch_all = models.BooleanField(default=False)
    assignment_mode = models.CharField(max_length=20, choices=ASSIGNMENT_MODE_CHOICES)
    default_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_wpa_default_assignments",
    )
    eligible_owners = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="sales_wpa_eligible_assignments",
    )
    fallback_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_wpa_fallback_assignments",
    )
    territory = models.ForeignKey(
        "crm.Territory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_wpa_assignment_rules",
    )
    max_open_records = models.PositiveSmallIntegerField(null=True, blank=True)
    cursor = models.PositiveIntegerField(default=0, editable=False)
    last_assigned_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="sales_wpa_last_assignments",
    )
    last_assigned_at = models.DateTimeField(null=True, blank=True, editable=False)
    escalate_after_hours = models.PositiveSmallIntegerField(null=True, blank=True)
    escalate_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_wpa_escalation_assignments",
    )
    priority = models.PositiveSmallIntegerField(default=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["priority", "name", "id"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "name"], name="sales_sar_tnt_name_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "target_entity", "is_active"], name="sales_sar_tnt_entity_idx"),
        ]

    def clean(self):
        super().clean()
        self.conditions = validate_process_conditions(self.conditions, self.is_catch_all)
        for field_name in ("default_owner", "fallback_owner", "escalate_to"):
            if not _relation_belongs_to_tenant(self, field_name):
                raise ValidationError({field_name: "Choose an active user from this workspace."})
            value = getattr(self, field_name, None)
            if value is not None and not value.is_active:
                raise ValidationError({field_name: "Choose an active user from this workspace."})
        if not _relation_belongs_to_tenant(self, "territory"):
            raise ValidationError({"territory": "Choose a territory from this workspace."})
        if self.assignment_mode == "fixed_owner" and not self.default_owner_id:
            raise ValidationError({"default_owner": "A fixed-owner rule needs a default owner."})
        if self.assignment_mode == "territory_manager" and not self.territory_id:
            raise ValidationError({"territory": "A territory-manager rule needs a territory."})
        if self.assignment_mode == "territory_manager" and self.territory_id and not self.territory.manager_id:
            raise ValidationError({"territory": "The selected territory has no manager."})
        if self.assignment_mode == "escalate_manager" and not self.escalate_to_id:
            raise ValidationError({"escalate_to": "An escalation rule needs an escalation target."})
        if self.assignment_mode == "escalate_manager" and not self.escalate_after_hours:
            raise ValidationError({"escalate_after_hours": "An escalation rule needs an escalation window."})
        if self.pk:
            invalid_owners = [owner for owner in self.eligible_owners.all() if owner.tenant_id != self.tenant_id or not owner.is_active]
            if invalid_owners:
                raise ValidationError({"eligible_owners": "Choose active owners from this workspace."})
            if self.assignment_mode == "round_robin" and not self.eligible_owners.exists():
                raise ValidationError({"eligible_owners": "A round-robin rule needs eligible owners."})
            if self.assignment_mode == "load_balanced" and not self.eligible_owners.exists():
                raise ValidationError({"eligible_owners": "A load-balanced rule needs eligible owners."})

    def __str__(self):
        return self.name
