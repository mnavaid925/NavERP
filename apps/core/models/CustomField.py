"""core — 0.10 bullet 5: Custom Fields & Form Builder.

The DEFINITION registry and the VALUE store, plus per-type validation in `apps/core/settings_engine.py`.

**Honest scope, stated on the page.** A module renders these only if it asks for them — the same
opt-in shape 0.6's data scoping uses. Nothing here retrofits extra inputs onto the ~150 existing
create/edit forms, because a generic form mutator would have to guess where each field belongs on
every one of them.

`CustomFieldValue` stores its target as (entity_label, object_id) with NO foreign key. That is a real
trade and it is stated rather than hidden: a generic value table cannot hold an FK to a table that is
not known at migration time, so a deleted parent leaves an orphan value behind. `object_id` is
indexed and the page says the link is by convention, not enforced.
"""
from apps.core.models._base import *  # noqa: F401,F403


class CustomFieldDefinition(models.Model):
    """One extra field an operator defined for one module entity."""

    FIELD_TYPE_CHOICES = [
        ("text", "Text"),
        ("textarea", "Long text"),
        ("integer", "Integer"),
        ("decimal", "Decimal"),
        ("boolean", "Yes / No"),
        ("date", "Date"),
        ("choice", "Choice"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="custom_field_definitions", db_index=True)
    module_slug = models.CharField(max_length=40)
    entity_label = models.CharField(max_length=120,
                                    help_text="e.g. 'crm.Lead' — the entity the field extends.")
    field_key = models.SlugField(max_length=60)
    label = models.CharField(max_length=200)
    field_type = models.CharField(max_length=10, choices=FIELD_TYPE_CHOICES, default="text")
    is_required = models.BooleanField(default=False)
    #: For `choice`, a JSON list of allowed values. Validated on every value write.
    choices = models.JSONField(default=list, blank=True)
    #: An optional regex applied to text values. Validated on write, never applied silently.
    validation_regex = models.CharField(max_length=255, blank=True)
    help_text = models.TextField(blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["module_slug", "entity_label", "display_order", "field_key"]
        unique_together = ("tenant", "entity_label", "field_key")
        indexes = [
            models.Index(fields=["tenant", "entity_label"], name="cfdef_tenant_entity_idx"),
            models.Index(fields=["tenant", "module_slug"], name="cfdef_tenant_module_idx"),
        ]

    def __str__(self):
        return f"{self.entity_label}.{self.field_key}"


class CustomFieldValue(models.Model):
    """One value, keyed by (entity_label, object_id). **No foreign key — stated, not hidden.**"""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="custom_field_values", db_index=True)
    definition = models.ForeignKey("core.CustomFieldDefinition", on_delete=models.CASCADE,
                                   related_name="values")
    entity_label = models.CharField(max_length=120)
    object_id = models.BigIntegerField()
    #: JSON so one column holds every type. The type is on the definition, and validation happens on
    #: write, so a reader never has to guess how to interpret it.
    value = models.JSONField(null=True, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   blank=True, editable=False, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["entity_label", "object_id", "definition__display_order"]
        unique_together = ("definition", "entity_label", "object_id")
        indexes = [
            models.Index(fields=["tenant", "entity_label", "object_id"], name="cfval_tenant_entity_idx"),
        ]

    def __str__(self):
        return f"{self.entity_label}#{self.object_id} · {self.definition.field_key}"
