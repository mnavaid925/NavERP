from django.db import migrations


ENTITY_LABELS = {
    "project": "projects.Project",
    "task": "projects.ProjectTask",
    "milestone": "projects.ProjectMilestone",
    "risk": "projects.ProjectRisk",
    "team": "projects.ProjectTeam",
}
FIELD_TYPES = {
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


def synchronize_definitions(apps, schema_editor):
    project_custom_field = apps.get_model("projects", "ProjectCustomField")
    core_definition = apps.get_model("core", "CustomFieldDefinition")
    for definition in project_custom_field.objects.all().iterator():
        entity_label = ENTITY_LABELS.get(definition.target_entity)
        if entity_label is None:
            continue
        choices = definition.choices_list if isinstance(definition.choices_list, list) else []
        core_definition.objects.update_or_create(
            tenant_id=definition.tenant_id,
            entity_label=entity_label,
            field_key=definition.field_key,
            defaults={
                "module_slug": "projects",
                "label": definition.label,
                "field_type": FIELD_TYPES.get(definition.field_type, "text"),
                "is_required": definition.is_required,
                "choices": choices if definition.field_type == "select" else [],
                "validation_regex": definition.regex_pattern or "",
                "help_text": definition.description or "",
                "display_order": definition.display_order,
                "is_active": definition.is_active,
            },
        )
    duplicates = project_custom_field.objects.filter(
        target_entity="task",
        field_key="story_points",
    )
    for definition in list(duplicates):
        core_definition.objects.filter(
            tenant_id=definition.tenant_id,
            entity_label=ENTITY_LABELS["task"],
            field_key=definition.field_key,
        ).update(is_active=False)
        definition.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0014_dataarchive_darch_tenant_at_idx_and_more"),
        ("projects", "0029_alter_projecttemplate_estimated_duration_days_and_more"),
    ]

    operations = [
        migrations.RunPython(synchronize_definitions, migrations.RunPython.noop),
    ]
