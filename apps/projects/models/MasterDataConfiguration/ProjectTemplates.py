"""Projects 7.19 — ProjectTemplate model [PTM-].

Reusable project blueprint and methodology framework (Waterfall, Agile, Hybrid) with
pre-built WBS hierarchy JSON, default roles, workflow stages, and budget/duration baselines.
"""
import json
import math
from decimal import Decimal

from apps.projects.models._base import *


WBS_MAX_PHASES = 100
WBS_MAX_ITEMS = 2000
WBS_MAX_DURATION_DAYS = 3650
WBS_MAX_JSON_BYTES = 262144
WBS_MAX_JSON_DEPTH = 5
WORKFLOW_MAX_JSON_BYTES = 65536
WORKFLOW_MAX_JSON_DEPTH = 6
WORKFLOW_MAX_RULES = 20
WORKFLOW_MAX_GATES = 20


def _json_depth(value):
    if isinstance(value, dict):
        return 1 + max((_json_depth(item) for item in value.values()), default=0)
    if isinstance(value, list):
        return 1 + max((_json_depth(item) for item in value), default=0)
    return 0


def _validate_stored_json_size(value, max_bytes, max_depth, label):
    try:
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except (RecursionError, TypeError, ValueError) as exc:
        raise ValidationError(f"{label} is not valid bounded JSON: {exc}")
    if len(encoded.encode("utf-8")) > max_bytes:
        raise ValidationError(f"{label} exceeds the {max_bytes}-byte limit.")
    if _json_depth(value) > max_depth:
        raise ValidationError(f"{label} exceeds the maximum nesting depth of {max_depth}.")


def _bounded_text(value, field, max_length):
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be a string.")
    value = value.strip()
    if not value or len(value) > max_length:
        raise ValidationError(f"{field} must contain 1 to {max_length} characters.")
    return value


def normalize_default_roles(value):
    if not isinstance(value, list) or len(value) > 20:
        raise ValidationError("Default roles must be a JSON array of at most 20 entries.")
    normalized = []
    for index, role in enumerate(value, start=1):
        role = _bounded_text(role, f"Default role {index}", 80)
        if role in normalized:
            raise ValidationError("Default roles must be unique.")
        normalized.append(role)
    return normalized


def normalize_wbs_structure(value):
    if not isinstance(value, list) or len(value) > WBS_MAX_PHASES:
        raise ValidationError(f"WBS structure must contain at most {WBS_MAX_PHASES} phases.")
    _validate_stored_json_size(value, WBS_MAX_JSON_BYTES, WBS_MAX_JSON_DEPTH, "WBS structure")
    phase_keys = {"phase", "name", "description", "tasks"}
    task_keys = {
        "name", "description", "duration_days", "is_milestone", "is_phase_gate",
        "estimation_method", "confidence",
    }
    normalized_phases = []
    item_count = 0
    duration_total = 0
    for phase_index, phase in enumerate(value, start=1):
        if not isinstance(phase, dict):
            raise ValidationError(f"Phase {phase_index} must be a JSON object.")
        unknown = set(phase) - phase_keys
        if unknown:
            raise ValidationError(
                f"Phase {phase_index} has unsupported keys: {', '.join(sorted(unknown))}."
            )
        phase_name = phase.get("phase") or phase.get("name")
        phase_name = _bounded_text(phase_name, f"Phase {phase_index} name", 255)
        description = phase.get("description", "")
        if not isinstance(description, str) or len(description) > 4000:
            raise ValidationError(f"Phase {phase_index} description must be at most 4,000 characters.")
        tasks = phase.get("tasks")
        if not isinstance(tasks, list) or not tasks:
            raise ValidationError(f"Phase {phase_index} tasks must be a non-empty JSON array.")
        normalized_tasks = []
        for task_index, task in enumerate(tasks, start=1):
            item_count += 1
            if item_count > WBS_MAX_ITEMS:
                raise ValidationError(f"A template may contain at most {WBS_MAX_ITEMS:,} WBS items.")
            if not isinstance(task, dict):
                raise ValidationError(
                    f"Phase {phase_index}, item {task_index} must be a JSON object."
                )
            unknown = set(task) - task_keys
            if unknown:
                raise ValidationError(
                    f"Phase {phase_index}, item {task_index} has unsupported keys: "
                    f"{', '.join(sorted(unknown))}."
                )
            name = _bounded_text(
                task.get("name"), f"Phase {phase_index}, item {task_index} name", 255
            )
            description = task.get("description", "")
            if not isinstance(description, str) or len(description) > 4000:
                raise ValidationError(
                    f"Phase {phase_index}, item {task_index} description must be at most "
                    "4,000 characters."
                )
            duration = task.get("duration_days", 1)
            if type(duration) is not int or not 1 <= duration <= WBS_MAX_DURATION_DAYS:
                raise ValidationError(
                    f"Phase {phase_index}, item {task_index} duration must be an integer "
                    f"from 1 to {WBS_MAX_DURATION_DAYS:,}."
                )
            is_milestone = task.get("is_milestone", False)
            is_phase_gate = task.get("is_phase_gate", False)
            if type(is_milestone) is not bool or type(is_phase_gate) is not bool:
                raise ValidationError(
                    f"Phase {phase_index}, item {task_index} milestone flags must be real booleans."
                )
            if is_phase_gate and not is_milestone:
                raise ValidationError(
                    f"Phase {phase_index}, item {task_index} phase-gate flags require a milestone."
                )
            estimation_method = task.get("estimation_method", "bottom_up")
            confidence = task.get("confidence", "medium")
            if estimation_method not in {"bottom_up", "top_down", "analogous", "parametric"}:
                raise ValidationError(
                    f"Phase {phase_index}, item {task_index} has an invalid estimation method."
                )
            if confidence not in {"high", "medium", "low"}:
                raise ValidationError(
                    f"Phase {phase_index}, item {task_index} has an invalid confidence value."
                )
            normalized_tasks.append({
                "name": name,
                "description": description.strip(),
                "duration_days": duration,
                "is_milestone": is_milestone,
                "is_phase_gate": is_phase_gate,
                "estimation_method": estimation_method,
                "confidence": confidence,
            })
            duration_total += duration
        if duration_total > WBS_MAX_DURATION_DAYS:
            raise ValidationError(
                f"The WBS schedule may not exceed {WBS_MAX_DURATION_DAYS:,} working days."
            )
        normalized_phases.append({
            "phase": phase_name,
            "description": description.strip(),
            "tasks": normalized_tasks,
        })
    return normalized_phases


def _bounded_json_objects(value, label, max_items=50):
    if not isinstance(value, list) or len(value) > max_items:
        raise ValidationError(f"{label} must be a JSON array of at most {max_items} objects.")
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise ValidationError(f"{label} item {index} must be a JSON object.")
    return value


def _bounded_number(value, label):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{label} must be a finite number or null.")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValidationError(f"{label} must be a finite number or null.")
    if abs(Decimal(str(value))) > MAX_Q2:
        raise ValidationError(f"{label} exceeds the supported monetary range.")
    return value


def normalize_workflow_config(value):
    if not isinstance(value, dict):
        raise ValidationError("Workflow config must be a JSON object.")
    unknown = set(value) - {"rules", "approval_gates"}
    if unknown:
        raise ValidationError(
            f"Workflow config has unsupported keys: {', '.join(sorted(unknown))}."
        )
    _validate_stored_json_size(
        value, WORKFLOW_MAX_JSON_BYTES, WORKFLOW_MAX_JSON_DEPTH, "Workflow config"
    )
    from apps.projects.models.WorkflowAutomation.ApprovalGates import ProjectApprovalGate
    from apps.projects.models.WorkflowAutomation.WorkflowRules import ProjectWorkflowRule

    rules = value.get("rules", [])
    normalized_rules = []
    rule_keys = {
        "name", "description", "trigger_entity", "trigger_event", "trigger_field",
        "trigger_value", "conditions", "actions",
    }
    trigger_entities = {choice[0] for choice in ProjectWorkflowRule.TRIGGER_ENTITY_CHOICES}
    trigger_events = {choice[0] for choice in ProjectWorkflowRule.TRIGGER_EVENT_CHOICES}
    for index, rule in enumerate(_bounded_json_objects(
        rules, "Workflow rules", WORKFLOW_MAX_RULES
    ), start=1):
        unknown = set(rule) - rule_keys
        if unknown:
            raise ValidationError(
                f"Workflow rule {index} has unsupported keys: {', '.join(sorted(unknown))}."
            )
        name = _bounded_text(rule.get("name"), f"Workflow rule {index} name", 255)
        description = rule.get("description", "")
        trigger_field = rule.get("trigger_field", "")
        trigger_value = rule.get("trigger_value", "")
        if not isinstance(description, str) or len(description) > 4000:
            raise ValidationError(f"Workflow rule {index} description is too long.")
        if not isinstance(trigger_field, str) or len(trigger_field) > 100:
            raise ValidationError(f"Workflow rule {index} trigger field is invalid.")
        if not isinstance(trigger_value, str) or len(trigger_value) > 255:
            raise ValidationError(f"Workflow rule {index} trigger value is invalid.")
        trigger_entity = rule.get("trigger_entity", "project")
        trigger_event = rule.get("trigger_event", "status_changed")
        if trigger_entity not in trigger_entities or trigger_event not in trigger_events:
            raise ValidationError(f"Workflow rule {index} has an invalid trigger.")
        normalized_rules.append({
            "name": name,
            "description": description.strip(),
            "trigger_entity": trigger_entity,
            "trigger_event": trigger_event,
            "trigger_field": trigger_field.strip(),
            "trigger_value": trigger_value.strip(),
            "conditions": _bounded_json_objects(
                rule.get("conditions", []), f"Workflow rule {index} conditions"
            ),
            "actions": _bounded_json_objects(
                rule.get("actions", []), f"Workflow rule {index} actions"
            ),
        })

    gates = value.get("approval_gates", [])
    normalized_gates = []
    gate_keys = {
        "gate_type", "title", "description", "target_kind", "target_index",
        "timeout_hours", "threshold_amount", "auto_approve_threshold",
    }
    gate_types = {choice[0] for choice in ProjectApprovalGate.GATE_TYPE_CHOICES}
    for index, gate in enumerate(_bounded_json_objects(
        gates, "Workflow approval gates", WORKFLOW_MAX_GATES
    ), start=1):
        unknown = set(gate) - gate_keys
        if unknown:
            raise ValidationError(
                f"Workflow approval gate {index} has unsupported keys: "
                f"{', '.join(sorted(unknown))}."
            )
        gate_type = gate.get("gate_type")
        if gate_type not in gate_types:
            raise ValidationError(f"Workflow approval gate {index} has an invalid gate type.")
        title = _bounded_text(gate.get("title"), f"Workflow approval gate {index} title", 255)
        description = gate.get("description", "")
        if not isinstance(description, str) or len(description) > 4000:
            raise ValidationError(f"Workflow approval gate {index} description is too long.")
        target_kind = gate.get("target_kind")
        if target_kind not in {"project", "milestone"}:
            raise ValidationError(
                f"Workflow approval gate {index} target must be project or milestone."
            )
        target_index = gate.get("target_index", 1)
        if target_kind == "milestone" and (
            type(target_index) is not int or not 1 <= target_index <= WBS_MAX_ITEMS
        ):
            raise ValidationError(
                f"Workflow approval gate {index} milestone index must be from 1 to {WBS_MAX_ITEMS:,}."
            )
        timeout_hours = gate.get("timeout_hours", 48)
        if type(timeout_hours) is not int or not 1 <= timeout_hours <= 8760:
            raise ValidationError(
                f"Workflow approval gate {index} timeout must be from 1 to 8,760 hours."
            )
        normalized_gates.append({
            "gate_type": gate_type,
            "title": title,
            "description": description.strip(),
            "target_kind": target_kind,
            "target_index": target_index if target_kind == "milestone" else None,
            "timeout_hours": timeout_hours,
            "threshold_amount": _bounded_number(
                gate.get("threshold_amount"), f"Workflow approval gate {index} threshold"
            ),
            "auto_approve_threshold": _bounded_number(
                gate.get("auto_approve_threshold"),
                f"Workflow approval gate {index} auto-approve threshold",
            ),
        })
    return {"rules": normalized_rules, "approval_gates": normalized_gates}


class ProjectTemplate(TenantNumbered):
    """Reusable project template and methodology framework."""

    NUMBER_PREFIX = "PTM"

    METHODOLOGY_CHOICES = [
        ("waterfall", "Waterfall (Predictive)"),
        ("agile", "Agile (Scrum / Iterative)"),
        ("hybrid", "Hybrid (Stage-Gate + Agile)"),
    ]

    CATEGORY_CHOICES = [
        ("software", "Software & IT"),
        ("infrastructure", "Infrastructure & Cloud"),
        ("consulting", "Professional Services / Consulting"),
        ("r_and_d", "R&D / Innovation"),
        ("marketing", "Marketing / Creative"),
        ("operational", "Operational / Internal"),
        ("internal", "Internal Governance"),
    ]

    COMPLEXITY_CHOICES = [
        ("small", "Small / Quick-Turn"),
        ("medium", "Medium Standard"),
        ("large", "Large Multi-Phase"),
        ("enterprise", "Enterprise Strategic"),
    ]

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, blank=True)
    methodology = models.CharField(
        max_length=20,
        choices=METHODOLOGY_CHOICES,
        default="hybrid",
        help_text="Project execution and governance methodology.",
    )
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default="software",
        help_text="Industry or operational domain category.",
    )
    complexity = models.CharField(
        max_length=20,
        choices=COMPLEXITY_CHOICES,
        default="medium",
        help_text="Project scale and governance rigor tier.",
    )
    description = models.TextField(blank=True, help_text="Scope and PM guidelines for this blueprint.")
    estimated_duration_days = models.PositiveIntegerField(
        default=30,
        help_text="Estimated baseline duration in business days when an operational calendar is configured; otherwise calendar days.",
    )
    target_budget = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Indicative baseline budget estimate.",
    )
    default_roles = models.JSONField(
        default=list,
        blank=True,
        help_text="List of recommended standard team roles for this template.",
    )
    wbs_structure = models.JSONField(
        default=list,
        blank=True,
        help_text="Pre-built WBS phases, tasks, and milestone deliverables structure.",
    )
    workflow_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Pre-configured lifecycle stage gates and transition approvals.",
    )
    is_active = models.BooleanField(default=True, help_text="Available for project instantiation.")
    is_default = models.BooleanField(
        default=False,
        help_text="Tenant default template for this methodology.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["tenant", "methodology"], name="ptm_tnt_meth_idx"),
            models.Index(fields=["tenant", "is_active"], name="ptm_tnt_active_idx"),
            models.Index(fields=["tenant", "-created_at"], name="ptm_tnt_created_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name}"

    def clean(self):
        super().clean()
        self.default_roles = normalize_default_roles(self.default_roles or [])
        self.wbs_structure = normalize_wbs_structure(self.wbs_structure or [])
        self.workflow_config = normalize_workflow_config(self.workflow_config or {})
        if self.is_default and self.tenant_id:
            # Enforce single default per methodology per tenant
            qs = ProjectTemplate.objects.filter(
                tenant=self.tenant,
                methodology=self.methodology,
                is_default=True,
            )
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError(
                    {"is_default": f"A default template for {self.get_methodology_display()} already exists."}
                )

    def save(self, *args, **kwargs):
        self.default_roles = normalize_default_roles(self.default_roles or [])
        self.wbs_structure = normalize_wbs_structure(self.wbs_structure or [])
        self.workflow_config = normalize_workflow_config(self.workflow_config or {})
        self.target_budget = q2(self.target_budget)
        if self.is_default and self.tenant_id:
            from apps.core.models import Tenant

            with transaction.atomic():
                Tenant.objects.select_for_update().get(pk=self.tenant_id)
                defaults = ProjectTemplate.objects.select_for_update().filter(
                    tenant_id=self.tenant_id,
                    methodology=self.methodology,
                    is_default=True,
                )
                if self.pk:
                    defaults = defaults.exclude(pk=self.pk)
                if defaults.exists():
                    raise ValidationError({
                        "is_default": (
                            f"A default template for {self.get_methodology_display()} "
                            "already exists."
                        )
                    })
                return super().save(*args, **kwargs)
        return super().save(*args, **kwargs)

    @property
    def methodology_badge_class(self):
        mapping = {
            "waterfall": "badge-info",
            "agile": "badge-green",
            "hybrid": "badge-info",
        }
        return mapping.get(self.methodology, "badge-slate")

    @property
    def complexity_badge_class(self):
        mapping = {
            "small": "badge-green",
            "medium": "badge-info",
            "large": "badge-amber",
            "enterprise": "badge-red",
        }
        return mapping.get(self.complexity, "badge-slate")

    def get_methodology_badge(self):
        return self.methodology_badge_class

    @property
    def active_badge_class(self):
        return "badge-green" if self.is_active else "badge-muted"

    def get_complexity_badge(self):
        return self.complexity_badge_class
