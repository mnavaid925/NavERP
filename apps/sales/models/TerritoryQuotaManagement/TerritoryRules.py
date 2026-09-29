"""Sales 8.7 Territory & Quota Management — the typed territory-assignment rule set.

**OWNERSHIP (L29/L36/L37) — read this before changing anything in this package.**
`crm.Territory` (`TER-`) and `crm.SalesQuota` (`QTA-`) are **OWNED by CRM 1.2** and live in
`apps/crm/models/SalesForceAutomation/`. Every model in this package reaches a territory through a
`ForeignKey("crm.Territory", ...)` and **none of them declares a second territory or quota master**.
A `class Territory` or `class SalesQuota` under `apps/sales/` would be a bug, not a variant — the
parallel-schema failure L29/L37 exist to prevent. CRM shipped first, so CRM owns the entity; 8.7 is
the commercial LAYER over it: the rules that assign accounts to territories, the effective-dated
assignment ledger, the coverage roster, and the quota-plan envelope.

The ruling is recorded in three durable places: this docstring, the `LIVE_LINKS["8.7"]` comment in
`apps/core/navigation.py`, and `.claude/tasks/lessons.md`.

**This module is a SIBLING of `LeadRoutingRules`, not a second rule engine.** It imports
`ROUTING_OPERATORS`, the two caps, the constant rejector and the scalar predicate from
`apps/sales/models/LeadManagement/LeadRoutingRules.py` and re-uses the *body shape* of
`validate_routing_conditions`. The only thing that differs is the allow-list a condition's `field`
is checked against: `TERRITORY_FIELDS` instead of `ROUTING_FIELDS`. Writing a fresh validator with
its own caps and its own scalar rules would be the fork 8.1's engine exists to prevent.

`segment_type` **IS the territory-model-type declaration** (research §5.1 rules *infer*): a
territory is "geographic" because the active rules pointing at it are geographic. That is what lets
8.7 satisfy bullet 1's four territory-model types with **zero** change to `crm.Territory`.
"""
import json
from datetime import date

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.sales.models._base import TenantNumbered
from apps.sales.models.LeadManagement.LeadRoutingRules import (
    MAX_ROUTING_CONDITIONS,
    MAX_ROUTING_JSON_BYTES,
    ROUTING_OPERATORS,
    LeadRoutingRule,
    _is_scalar,
    _reject_json_constant,
)


#: The allow-list a condition's ``field`` is checked against. Closed, exactly as ``ROUTING_FIELDS``
#: is closed — an unknown field is a form error, never a silently-ignored key. Sources:
#: ``crm.AccountProfile.industry / .annual_revenue / .employee_count / .address_country /
#: .address_city / .address_state / .address_postal`` (note: the as-built column is
#: ``address_postal``, NOT ``address_postal_code``), ``sales.AccountClassification.tier /
#: .lifecycle_stage``, an open-``crm.Opportunity`` probe, and ``core.Party.name``.
TERRITORY_FIELDS = {
    "industry", "annual_revenue", "employee_count", "tier", "lifecycle_stage",
    "country", "city", "state", "postal_code", "is_named_account",
    "has_open_opportunity", "account_name",
}




def validate_territory_conditions(value, is_catch_all=False):
    """A sibling of ``validate_routing_conditions`` that checks ``TERRITORY_FIELDS``.

    Same caps, same operator vocabulary, same "each condition is exactly ``{field, operator, value}``
    and nothing else" rule, and the same "an empty rule must be explicitly a catch-all" rule. It is a
    sibling rather than a second engine precisely because it imports every shared constant above: a
    second copy of the scalar predicate or the size caps is how the two drift apart and one of them
    quietly stops rejecting what the other rejects.
    """
    if isinstance(value, str):
        try:
            value = json.loads(value, parse_constant=_reject_json_constant)
        except (TypeError, ValueError) as exc:
            raise ValidationError("Conditions must be valid JSON.") from exc
    if not isinstance(value, list):
        raise ValidationError("Conditions must be a list.")
    if len(value) > MAX_ROUTING_CONDITIONS:
        raise ValidationError(f"A territory rule may contain at most {MAX_ROUTING_CONDITIONS} conditions.")
    if not value and not is_catch_all:
        raise ValidationError("An empty rule must be explicitly marked as a catch-all.")
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError("Conditions contain an unsupported value.") from exc
    if len(encoded.encode("utf-8")) > MAX_ROUTING_JSON_BYTES:
        raise ValidationError(f"Conditions must be {MAX_ROUTING_JSON_BYTES // 1024} KiB or smaller.")
    normalized = []
    for condition in value:
        if not isinstance(condition, dict) or set(condition) != {"field", "operator", "value"}:
            raise ValidationError("Each condition must contain only field, operator, and value.")
        field = condition["field"]
        operator = condition["operator"]
        scalar = condition["value"]
        if not isinstance(field, str) or field not in TERRITORY_FIELDS:
            raise ValidationError(f"Unsupported territory field: {field}")
        if not isinstance(operator, str) or operator not in ROUTING_OPERATORS:
            raise ValidationError(f"Unsupported territory operator: {operator}")
        if len(field) > 255 or len(operator) > 255:
            raise ValidationError("Territory field and operator values are too long.")
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


class TerritoryRule(TenantNumbered):
    """One tenant-configured rule assigning accounts to a ``crm.Territory``."""

    NUMBER_PREFIX = "TRG"

    SEGMENT_TYPE_CHOICES = [
        ("geographic", "Geographic"),
        ("industry", "Industry"),
        ("account_size", "Account Size"),
        ("product_line", "Product Line"),
        ("named_account", "Named Account"),
        ("mixed", "Mixed"),
    ]
    #: The single source of truth for alignment vocabulary in 8.7.
    #: ``AccountTerritoryAssignment`` reuses THIS list rather than re-spelling it.
    ALIGNMENT_TYPE_CHOICES = [
        ("primary", "Primary"),
        ("secondary", "Secondary"),
        ("overlay", "Overlay"),
    ]
    ASSIGNMENT_SCOPE_CHOICES = [
        ("exact", "This Territory Only"),
        ("subtree", "This Territory And Children"),
    ]
    #: IMPORTED from 8.1, never re-spelled — [("all", "All conditions"), ("any", "Any condition")].
    MATCH_MODE_CHOICES = LeadRoutingRule.MATCH_MODE_CHOICES

    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    segment_type = models.CharField(max_length=20, choices=SEGMENT_TYPE_CHOICES, default="geographic")
    match_mode = models.CharField(max_length=8, choices=MATCH_MODE_CHOICES, default="all")
    conditions = models.JSONField(default=list, blank=True)
    is_catch_all = models.BooleanField(default=False)
    alignment_type = models.CharField(max_length=8, choices=ALIGNMENT_TYPE_CHOICES, default="primary")
    assignment_scope = models.CharField(max_length=10, choices=ASSIGNMENT_SCOPE_CHOICES, default="exact")
    target_territory = models.ForeignKey(
        "crm.Territory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_territory_rules",
    )
    is_active = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(default=100, validators=[MinValueValidator(1)])
    effective_from = models.DateField(default=timezone.localdate)
    effective_to = models.DateField(null=True, blank=True)
    # --- FROZEN EVIDENCE. editable=False, so auto-excluded from every ModelForm (L22). Written
    # ONLY by the `territory_rule_run` POST view, inside the transaction that writes the
    # assignment rows — a run's own receipt can never be hand-edited afterwards.
    last_run_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_run_matched_count = models.PositiveIntegerField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["priority", "id"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "name"], name="sales_trule_tenant_name_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "is_active", "priority"], name="sales_trule_tnt_active_idx"),
            models.Index(fields=["tenant", "segment_type"], name="sales_trule_tnt_seg_idx"),
        ]

    # ------------------------------------------------------------------ helpers

    def _relation_belongs_to_tenant(self, field_name):
        """True when the named FK is unset or points at a row in THIS workspace.

        An FK to a tenant-scoped model *looks* safe but is not: a hand-built
        ``Territory(pk=<other tenant>)`` handed to ``save()`` by a seeder, a service or the shell
        bypasses every form. This is the explicit check L4 warns about, copied in the same shape as
        ``LeadRoutingRules._relation_belongs_to_tenant`` and ``OrderValidationRule``.
        """
        if not self.tenant_id:
            return True
        relation_id = getattr(self, f"{field_name}_id", None)
        if not relation_id:
            return True
        field = self._meta.get_field(field_name)
        related_model = field.remote_field.model
        return related_model._default_manager.filter(
            pk=relation_id,
            tenant_id=self.tenant_id,
        ).exists()

    def is_effective_on(self, day):
        """Is this rule in force on ``day``? An ``effective_to`` of ``None`` means open-ended."""
        if self.effective_from and day < self.effective_from:
            return False
        if self.effective_to and day > self.effective_to:
            return False
        return True

    # ------------------------------------------------------------------ validation

    def clean(self):
        super().clean()
        # Every condition key is checked against the CLOSED allow-list here as well as inside the
        # validator: validate_territory_conditions raises a non-field error, and a model-level
        # caller (seeder, service, shell) must get the same refusal a form would give it.
        self.conditions = validate_territory_conditions(self.conditions, self.is_catch_all)
        if not self.tenant_id:
            return
        errors = {}
        # A rule assigns TO a territory. "No territory" is a coverage GAP, which the coverage-gap
        # board reports — it is not a rule outcome, so a rule without a target is refused rather
        # than silently matching accounts and dropping them.
        if not self.target_territory_id:
            errors["target_territory"] = "Choose the territory this rule assigns to."
        elif not self._relation_belongs_to_tenant("target_territory"):
            errors["target_territory"] = "The target territory must belong to this workspace."
        if self.effective_to and self.effective_from and self.effective_to < self.effective_from:
            errors["effective_to"] = "The end date cannot precede the start date."
        if isinstance(self.effective_to, date) and not isinstance(self.effective_from, date):
            errors["effective_from"] = "Enter a valid start date."
        # Named accounts are hand-picked; that is what makes them named. A "named_account" rule
        # carrying match conditions would be a contradiction, not a stricter rule.
        if self.segment_type == "named_account" and self.conditions:
            errors["conditions"] = "A named-account rule picks accounts by hand and carries no conditions."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # A direct .save() (seeder, service, shell) skips full_clean() by design, so the invariant
        # that keeps the row loadable by the evaluator — conditions is a LIST — is re-applied here
        # rather than trusted (L62: refuse rather than fall through to a default the reader breaks on).
        if not isinstance(self.conditions, list):
            self.conditions = []
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number or '—'} · {self.name}"
