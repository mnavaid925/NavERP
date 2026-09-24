"""Projects 7.19 — ProjectCustomField model [PCF-].

Configurable user-defined metadata fields for project management entities
with validation constraints and conditional visibility rules.
"""
import json
import re
from decimal import Decimal

from django.db.models.signals import post_delete

from apps.projects.models._base import *


CUSTOM_FIELD_JSON_MAX_BYTES = 16384
CUSTOM_FIELD_JSON_MAX_DEPTH = 4
CUSTOM_FIELD_ENTITY_LABELS = {
    "project": "projects.Project",
    "task": "projects.ProjectTask",
    "milestone": "projects.ProjectMilestone",
    "risk": "projects.ProjectRisk",
    "team": "projects.ProjectTeam",
}
CORE_FIELD_TYPES = {
    "text": "text",
    "textarea": "textarea",
    "integer": "integer",
    "decimal": "decimal",
    "date": "date",
    "boolean": "boolean",
    "select": "choice",
    "multiselect": "text",
    "url": "text",
    "user_ref": "text",
}


def _json_depth(value):
    if isinstance(value, dict):
        return 1 + max((_json_depth(item) for item in value.values()), default=0)
    if isinstance(value, list):
        return 1 + max((_json_depth(item) for item in value), default=0)
    return 0


def _validate_custom_field_json(value, label):
    try:
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except (RecursionError, TypeError, ValueError) as exc:
        raise ValidationError(f"{label} is not valid bounded JSON: {exc}")
    if len(encoded.encode("utf-8")) > CUSTOM_FIELD_JSON_MAX_BYTES:
        raise ValidationError(f"{label} exceeds the {CUSTOM_FIELD_JSON_MAX_BYTES}-byte limit.")
    if _json_depth(value) > CUSTOM_FIELD_JSON_MAX_DEPTH:
        raise ValidationError(f"{label} exceeds the maximum nesting depth of {CUSTOM_FIELD_JSON_MAX_DEPTH}.")


def sync_core_definition(definition):
    if definition.tenant_id is None or definition.field_key in (None, ""):
        return None
    from apps.core.models import CustomFieldDefinition

    entity_label = CUSTOM_FIELD_ENTITY_LABELS.get(definition.target_entity)
    if entity_label is None:
        return None
    core_definition, _created = CustomFieldDefinition.objects.update_or_create(
        tenant_id=definition.tenant_id,
        entity_label=entity_label,
        field_key=definition.field_key,
        defaults={
            "module_slug": "projects",
            "label": definition.label,
            "field_type": CORE_FIELD_TYPES.get(definition.field_type, "text"),
            "is_required": definition.is_required,
            "choices": definition.choices_list if definition.field_type == "select" else [],
            "validation_regex": definition.regex_pattern or "",
            "help_text": definition.description or "",
            "display_order": definition.display_order,
            "is_active": definition.is_active,
        },
    )
    return core_definition


def deactivate_core_definition(tenant_id, target_entity, field_key):
    from apps.core.models import CustomFieldDefinition

    entity_label = CUSTOM_FIELD_ENTITY_LABELS.get(target_entity)
    if tenant_id is None or entity_label is None or not field_key:
        return 0
    return CustomFieldDefinition.objects.filter(
        tenant_id=tenant_id,
        entity_label=entity_label,
        field_key=field_key,
    ).update(is_active=False)


class ProjectCustomField(TenantNumbered):
    """User-defined custom field specification for projects, tasks, and related entities."""

    NUMBER_PREFIX = "PCF"

    TARGET_ENTITY_CHOICES = [
        ("project", "Project"),
        ("task", "Project Task"),
        ("milestone", "Project Milestone"),
        ("risk", "Project Risk"),
        ("team", "Project Team"),
    ]

    FIELD_TYPE_CHOICES = [
        ("text", "Text (Single Line)"),
        ("textarea", "Text Area (Long)"),
        ("integer", "Integer Number"),
        ("decimal", "Decimal / Currency"),
        ("date", "Date"),
        ("boolean", "Yes / No (Boolean)"),
        ("select", "Single Select Dropdown"),
        ("multiselect", "Multi-Select Choices"),
        ("url", "URL Web Link"),
        ("user_ref", "Team Member Reference"),
    ]

    SECTION_CHOICES = [
        ("general", "General Information"),
        ("governance", "Governance & Compliance"),
        ("technical", "Technical & Architecture"),
        ("financial", "Financial & Commercial"),
        ("risk", "Risk & Safety"),
        ("custom", "Additional Attributes"),
    ]

    name = models.CharField(max_length=255, help_text="Administrative label for PMO governance.")
    field_key = models.SlugField(max_length=60, help_text="Unique programmatic key (slug) for data storage.")
    label = models.CharField(max_length=200, help_text="Human-facing label displayed on input forms.")
    target_entity = models.CharField(
        max_length=20,
        choices=TARGET_ENTITY_CHOICES,
        default="project",
        help_text="Project Management entity this custom field extends.",
    )
    field_type = models.CharField(
        max_length=20,
        choices=FIELD_TYPE_CHOICES,
        default="text",
        help_text="Underlying data type and widget format.",
    )
    form_section = models.CharField(
        max_length=30,
        choices=SECTION_CHOICES,
        default="general",
        help_text="Form section layout grouping.",
    )
    description = models.TextField(blank=True, help_text="Guidance or operational definition for users.")
    placeholder = models.CharField(max_length=255, blank=True, help_text="UI placeholder text.")
    default_value = models.CharField(max_length=255, blank=True, help_text="Default initial value.")
    is_required = models.BooleanField(default=False, help_text="Mandatory field on form submission.")
    min_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Minimum allowed value for numeric types.",
    )
    max_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Maximum allowed value for numeric types.",
    )
    regex_pattern = models.CharField(max_length=255, blank=True, help_text="Regex validation pattern.")
    choices_list = models.JSONField(
        default=list,
        blank=True,
        help_text="Array of allowed string options for select and multiselect types.",
    )
    visibility_rule = models.JSONField(
        default=dict,
        blank=True,
        help_text="Conditional display rule dict (e.g. {'depends_on': 'methodology', 'equals': 'agile'}).",
    )
    display_order = models.PositiveIntegerField(default=0, help_text="Visual sort order in form section.")
    is_active = models.BooleanField(default=True, help_text="Active for data capture.")

    class Meta:
        ordering = ["target_entity", "form_section", "display_order", "id"]
        unique_together = ("tenant", "target_entity", "field_key")
        indexes = [
            models.Index(fields=["tenant", "target_entity", "is_active"], name="pcf_tnt_ent_act_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.target_entity}.{self.field_key} ({self.label})"

    def _validate_definition(self):
        if self.min_value is not None and self.max_value is not None and self.min_value > self.max_value:
            raise ValidationError({"max_value": "Maximum value cannot be lower than the minimum value."})
        if self.regex_pattern:
            try:
                re.compile(self.regex_pattern)
            except re.error as exc:
                raise ValidationError({"regex_pattern": f"Invalid regular expression: {exc}"})
        if not isinstance(self.choices_list, list):
            raise ValidationError({"choices_list": "Choices must be a JSON array."})
        if any(not isinstance(value, str) or not value.strip() for value in self.choices_list):
            raise ValidationError({"choices_list": "Every choice must be a non-empty string."})
        if len({value.strip() for value in self.choices_list}) != len(self.choices_list):
            raise ValidationError({"choices_list": "Choices must be unique."})
        if self.field_type in ("select", "multiselect") and not self.choices_list:
            raise ValidationError({"choices_list": "Select fields require at least one choice."})
        if not isinstance(self.visibility_rule, dict):
            raise ValidationError({"visibility_rule": "Visibility rule must be a JSON object."})
        _validate_custom_field_json(self.choices_list, "Choices")
        _validate_custom_field_json(self.visibility_rule, "Visibility rule")

    def clean(self):
        super().clean()
        self._validate_definition()

    def save(self, *args, **kwargs):
        self._validate_definition()
        previous = None
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values(
                "tenant_id", "target_entity", "field_key"
            ).first()
        with transaction.atomic():
            result = super().save(*args, **kwargs)
            sync_core_definition(self)
            if previous and (
                previous["tenant_id"] != self.tenant_id
                or previous["target_entity"] != self.target_entity
                or previous["field_key"] != self.field_key
            ):
                deactivate_core_definition(
                    previous["tenant_id"], previous["target_entity"], previous["field_key"]
                )
        return result

    def delete(self, *args, **kwargs):
        tenant_id = self.tenant_id
        target_entity = self.target_entity
        field_key = self.field_key
        with transaction.atomic():
            result = super().delete(*args, **kwargs)
            deactivate_core_definition(tenant_id, target_entity, field_key)
        return result

    @property
    def has_numeric_bounds(self):
        return self.min_value is not None or self.max_value is not None

    @property
    def target_badge_class(self):
        mapping = {
            "project": "badge-info",
            "task": "badge-green",
            "milestone": "badge-amber",
            "risk": "badge-red",
            "team": "badge-slate",
        }
        return mapping.get(self.target_entity, "badge-slate")

    @property
    def field_type_badge_class(self):
        mapping = {
            "text": "badge-slate",
            "textarea": "badge-slate",
            "integer": "badge-info",
            "decimal": "badge-info",
            "date": "badge-amber",
            "boolean": "badge-green",
            "select": "badge-info",
            "multiselect": "badge-info",
            "url": "badge-slate",
            "user_ref": "badge-green",
        }
        return mapping.get(self.field_type, "badge-slate")

    @property
    def active_badge_class(self):
        return "badge-green" if self.is_active else "badge-muted"

    def get_target_entity_badge(self):
        return self.target_badge_class

    def get_field_type_badge(self):
        return self.field_type_badge_class


def _deactivate_deleted_core_definition(sender, instance, **kwargs):
    deactivate_core_definition(instance.tenant_id, instance.target_entity, instance.field_key)


post_delete.connect(
    _deactivate_deleted_core_definition,
    sender=ProjectCustomField,
)
