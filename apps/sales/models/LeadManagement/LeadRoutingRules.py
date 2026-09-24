import json
import math

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.accounts.models import User
from apps.sales.models._base import *


ROUTING_FIELDS = {
    "source", "status", "rating", "score", "est_value", "owner_id", "company", "title",
    "email_present", "phone_present", "qualification_status", "framework", "country_code",
    "region", "city", "industry", "employee_count", "seniority", "budget_status",
    "authority_level", "expected_purchase_on",
}
ROUTING_OPERATORS = {"eq", "ne", "in", "not_in", "contains", "icontains", "gt", "gte", "lt", "lte", "is_set", "is_empty"}
MAX_ROUTING_CONDITIONS = 20
MAX_ROUTING_JSON_BYTES = 16 * 1024


def _reject_json_constant(value):
    raise ValueError(f"Non-finite JSON value: {value}")


def _is_scalar(value):
    if value is None or isinstance(value, (str, bool, int)):
        return True
    return isinstance(value, float) and math.isfinite(value)


def _relation_belongs_to_tenant(instance, field_name):
    if not instance.tenant_id:
        return True
    field = instance._meta.get_field(field_name)
    related_id = getattr(instance, f"{field_name}_id", None)
    if not related_id:
        return True
    related_model = field.remote_field.model
    return related_model._default_manager.filter(pk=related_id, tenant_id=instance.tenant_id).exists()


def validate_routing_conditions(value, is_catch_all=False):
    if isinstance(value, str):
        try:
            value = json.loads(value, parse_constant=_reject_json_constant)
        except (TypeError, ValueError) as exc:
            raise ValidationError("Conditions must be valid JSON.") from exc
    if not isinstance(value, list):
        raise ValidationError("Conditions must be a list.")
    if len(value) > MAX_ROUTING_CONDITIONS:
        raise ValidationError("A routing rule may contain at most 20 conditions.")
    if not value and not is_catch_all:
        raise ValidationError("An empty rule must be explicitly marked as a catch-all.")
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError("Conditions contain an unsupported value.") from exc
    if len(encoded.encode("utf-8")) > MAX_ROUTING_JSON_BYTES:
        raise ValidationError("Conditions must be 16 KiB or smaller.")
    normalized = []
    for condition in value:
        if not isinstance(condition, dict) or set(condition) != {"field", "operator", "value"}:
            raise ValidationError("Each condition must contain only field, operator, and value.")
        field = condition["field"]
        operator = condition["operator"]
        scalar = condition["value"]
        if not isinstance(field, str) or field not in ROUTING_FIELDS:
            raise ValidationError(f"Unsupported routing field: {field}")
        if not isinstance(operator, str) or operator not in ROUTING_OPERATORS:
            raise ValidationError(f"Unsupported routing operator: {operator}")
        if len(field) > 255 or len(operator) > 255:
            raise ValidationError("Routing field and operator values are too long.")
        if operator in {"in", "not_in"}:
            if not isinstance(scalar, list) or not scalar or len(scalar) > 20:
                raise ValidationError("List operators require 1 to 20 scalar values.")
            if any(not _is_scalar(item) for item in scalar):
                raise ValidationError("List operator values must be finite scalar values.")
            if any(isinstance(item, str) and len(item) > 255 for item in scalar):
                raise ValidationError("Condition values must be 255 characters or fewer.")
        elif operator in {"is_set", "is_empty"}:
            if not (isinstance(scalar, bool) or scalar is None):
                raise ValidationError("Set operators accept only true, false, or null.")
        elif not _is_scalar(scalar):
            raise ValidationError("Condition values must be finite scalars or bounded lists.")
        if isinstance(scalar, str) and len(scalar) > 255:
            raise ValidationError("Condition values must be 255 characters or fewer.")
        normalized.append({"field": field, "operator": operator, "value": scalar})
    return normalized


class LeadRoutingRule(TenantOwned):
    MATCH_MODE_CHOICES = [("all", "All conditions"), ("any", "Any condition")]
    ASSIGNMENT_MODE_CHOICES = [
        ("fixed_owner", "Fixed Owner"),
        ("territory_manager", "Territory Manager"),
        ("round_robin", "Round Robin"),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(default=100, validators=[MinValueValidator(1)])
    match_mode = models.CharField(max_length=10, choices=MATCH_MODE_CHOICES, default="all")
    conditions = models.JSONField(default=list, blank=True)
    is_catch_all = models.BooleanField(default=False)
    assignment_mode = models.CharField(max_length=20, choices=ASSIGNMENT_MODE_CHOICES)
    default_owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="sales_default_routing_rules")
    territory = models.ForeignKey("crm.Territory", on_delete=models.SET_NULL, null=True, blank=True, related_name="sales_routing_rules")
    eligible_owners = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="sales_routing_rules")
    fallback_owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="sales_fallback_routing_rules")
    max_open_leads = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    cursor = models.PositiveIntegerField(default=0, editable=False)
    last_assigned_owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="sales_last_routing_rules")
    last_assigned_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["priority", "id"]
        constraints = [models.UniqueConstraint(fields=["tenant", "name"], name="sales_lrr_tenant_name_uniq")]
        indexes = [
            models.Index(fields=["tenant", "is_active", "priority"], name="sales_lrr_tnt_active_idx"),
            models.Index(fields=["tenant", "assignment_mode"], name="sales_lrr_tnt_mode_idx"),
        ]

    def clean(self):
        super().clean()
        self.conditions = validate_routing_conditions(self.conditions, self.is_catch_all)
        for field_name in ("default_owner", "fallback_owner"):
            if not _relation_belongs_to_tenant(self, field_name):
                raise ValidationError({field_name: "Choose an active user from this workspace."})
            value = getattr(self, field_name, None)
            if value is not None and not value.is_active:
                raise ValidationError({field_name: "Choose an active user from this workspace."})
        if not _relation_belongs_to_tenant(self, "territory"):
            raise ValidationError({"territory": "Choose a territory from this workspace."})
        if self.territory_id and self.territory.manager_id:
            manager = User._default_manager.filter(
                pk=self.territory.manager_id,
                tenant_id=self.tenant_id,
                is_active=True,
            ).first()
            if manager is None:
                raise ValidationError({"territory": "The selected territory manager is not active in this workspace."})
        if self.assignment_mode == "fixed_owner" and not self.default_owner_id:
            raise ValidationError({"default_owner": "A fixed-owner rule needs a default owner."})
        if self.assignment_mode == "territory_manager" and not self.territory_id:
            raise ValidationError({"territory": "A territory-manager rule needs a territory."})
        if self.assignment_mode == "territory_manager" and self.territory_id and not self.territory.manager_id:
            raise ValidationError({"territory": "The selected territory has no manager."})
        if self.pk:
            invalid_owners = [owner for owner in self.eligible_owners.all() if owner.tenant_id != self.tenant_id or not owner.is_active]
            if invalid_owners:
                raise ValidationError({"eligible_owners": "Choose active owners from this workspace."})
            if self.assignment_mode == "round_robin" and not self.eligible_owners.exists():
                raise ValidationError({"eligible_owners": "A round-robin rule needs eligible owners."})

    def __str__(self):
        return self.name
