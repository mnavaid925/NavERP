"""Sales 8.17 — SalesProcessDefinition model."""
import json
import math

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.sales.models._base import TenantNumbered

TARGET_ENTITY_CHOICES = [
    ("lead", "Lead"),
    ("opportunity", "Opportunity"),
    ("quote", "Quote"),
    ("order", "Order"),
    ("case", "Case"),
    ("contract", "Contract"),
    ("subscription", "Subscription"),
]

PROCESS_NODE_TYPES = {"approval", "assign", "notify", "update_field", "create_task", "wait", "branch"}

PROCESS_OPERATORS = {"eq", "ne", "in", "not_in", "contains", "icontains", "gt", "gte", "lt", "lte", "is_set", "is_empty"}
MAX_PROCESS_CONDITIONS = 20
MAX_PROCESS_JSON_BYTES = 16 * 1024
MAX_PROCESS_NODES = 20
MAX_NODE_PARAMS = 20
MAX_REQUIRED_FIELDS = 20


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


def validate_process_conditions(value, is_catch_all=False):
    """Bounded-JSON validator for the trigger condition list.

    Clone of 8.1's ``validate_routing_conditions`` with IDENTICAL bounds and messages,
    except the ROUTING_FIELDS whitelist is dropped (8.17 conditions span 7 entities):
    ``field`` may be any non-empty str <= 255. Returns the normalized list of
    ``{"field": ..., "operator": ..., "value": ...}`` dicts.
    """
    if isinstance(value, str):
        try:
            value = json.loads(value, parse_constant=_reject_json_constant)
        except (TypeError, ValueError) as exc:
            raise ValidationError("Conditions must be valid JSON.") from exc
    if not isinstance(value, list):
        raise ValidationError("Conditions must be a list.")
    if len(value) > MAX_PROCESS_CONDITIONS:
        raise ValidationError("A process rule may contain at most 20 conditions.")
    if not value and not is_catch_all:
        raise ValidationError("An empty rule must be explicitly marked as a catch-all.")
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError("Conditions contain an unsupported value.") from exc
    if len(encoded.encode("utf-8")) > MAX_PROCESS_JSON_BYTES:
        raise ValidationError("Conditions must be 16 KiB or smaller.")
    normalized = []
    for condition in value:
        if not isinstance(condition, dict) or set(condition) != {"field", "operator", "value"}:
            raise ValidationError("Each condition must contain only field, operator, and value.")
        field = condition["field"]
        operator = condition["operator"]
        scalar = condition["value"]
        if not isinstance(field, str) or not field or len(field) > 255:
            raise ValidationError("Condition fields must be 1 to 255 characters.")
        if not isinstance(operator, str) or operator not in PROCESS_OPERATORS:
            raise ValidationError(f"Unsupported condition operator: {operator}")
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


def validate_process_nodes(value):
    """Bounded-JSON validator for the ordered node list.

    Returns the normalized ``[{"seq": int, "type": str, "params": dict}]`` list.
    """
    if isinstance(value, str):
        try:
            value = json.loads(value, parse_constant=_reject_json_constant)
        except (TypeError, ValueError) as exc:
            raise ValidationError("Nodes must be valid JSON.") from exc
    if not isinstance(value, list):
        raise ValidationError("Nodes must be a list.")
    if len(value) > MAX_PROCESS_NODES:
        raise ValidationError("A process may contain at most 20 nodes.")
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError("Nodes contain an unsupported value.") from exc
    if len(encoded.encode("utf-8")) > MAX_PROCESS_JSON_BYTES:
        raise ValidationError("Nodes must be 16 KiB or smaller.")
    normalized = []
    seen_seq = set()
    for node in value:
        if not isinstance(node, dict) or set(node) != {"seq", "type", "params"}:
            raise ValidationError("Each node must contain only seq, type, and params.")
        seq = node["seq"]
        kind = node["type"]
        params = node["params"]
        if isinstance(seq, bool) or not isinstance(seq, int) or seq < 1 or seq > 999:
            raise ValidationError("Node seq must be an integer from 1 to 999.")
        if not isinstance(kind, str) or kind not in PROCESS_NODE_TYPES:
            raise ValidationError(f"Unsupported node type: {kind}")
        if not isinstance(params, dict) or len(params) > MAX_NODE_PARAMS:
            raise ValidationError("Node params must be a dict of at most 20 keys.")
        normalized_params = {}
        for key, param_value in params.items():
            if not isinstance(key, str) or not key or len(key) > 100:
                raise ValidationError("Node param keys must be 1 to 100 characters.")
            if key == "required_fields":
                if (
                    not isinstance(param_value, list)
                    or len(param_value) > MAX_REQUIRED_FIELDS
                    or any(not isinstance(item, str) or len(item) > 255 for item in param_value)
                ):
                    raise ValidationError("required_fields must be at most 20 strings of 255 characters or fewer.")
            elif not _is_scalar(param_value):
                raise ValidationError("Node param values must be finite scalars.")
            if key != "required_fields" and isinstance(param_value, str) and len(param_value) > 255:
                raise ValidationError("Node param values must be 255 characters or fewer.")
            normalized_params[key] = param_value
        if seq in seen_seq:
            raise ValidationError("Node seq values must be unique.")
        seen_seq.add(seq)
        normalized.append({"seq": seq, "type": kind, "params": normalized_params})
    return normalized


class SalesProcessDefinition(TenantNumbered):
    NUMBER_PREFIX = "SPD"

    STATUS_CHOICES = [("draft", "Draft"), ("active", "Active"), ("paused", "Paused"), ("archived", "Archived")]
    TRIGGER_EVENT_CHOICES = [
        ("created", "Record Created"),
        ("updated", "Record Updated"),
        ("stage_changed", "Stage Changed"),
        ("field_value", "Field Matches Value"),
        ("date_reached", "Date Reached"),
        ("inactivity", "Inactivity Window"),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    target_entity = models.CharField(max_length=16, choices=TARGET_ENTITY_CHOICES)
    trigger_event = models.CharField(max_length=16, choices=TRIGGER_EVENT_CHOICES, default="created")
    trigger_field = models.CharField(max_length=100, blank=True)
    trigger_value = models.CharField(max_length=200, blank=True)
    conditions = models.JSONField(default=list, blank=True)
    nodes = models.JSONField(default=list, blank=True)
    max_enrollments = models.PositiveSmallIntegerField(default=1)
    priority = models.PositiveSmallIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_wpa_owned_processes",
    )
    job_definition = models.ForeignKey(
        "core.JobDefinition",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_wpa_process_jobs",
    )

    class Meta:
        ordering = ["priority", "name", "id"]
        indexes = [
            models.Index(fields=["tenant", "status"], name="sales_spd_tnt_status_idx"),
        ]

    def clean(self):
        super().clean()
        self.conditions = validate_process_conditions(self.conditions, is_catch_all=True)
        self.nodes = validate_process_nodes(self.nodes)
        if self.trigger_event == "field_value":
            if not self.trigger_field:
                raise ValidationError({"trigger_field": "A field-value trigger needs a trigger field."})
            if not self.trigger_value:
                raise ValidationError({"trigger_value": "A field-value trigger needs a comparison value."})
        if not _relation_belongs_to_tenant(self, "owner"):
            raise ValidationError({"owner": "Choose an active user from this workspace."})
        if not _relation_belongs_to_tenant(self, "job_definition"):
            raise ValidationError({"job_definition": "Choose a job definition from this workspace."})

    def __str__(self):
        return f"{self.number} — {self.name}"
