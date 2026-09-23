"""Projects 7.19 — ProjectCustomField model [PCF-].

Configurable user-defined metadata fields for project management entities
with validation constraints and conditional visibility rules.
"""
from decimal import Decimal

from apps.projects.models._base import *


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
            "integer": "badge-blue",
            "decimal": "badge-blue",
            "date": "badge-amber",
            "boolean": "badge-green",
            "select": "badge-info",
            "multiselect": "badge-info",
            "url": "badge-purple" if False else "badge-slate",
            "user_ref": "badge-green",
        }
        return mapping.get(self.field_type, "badge-slate")
