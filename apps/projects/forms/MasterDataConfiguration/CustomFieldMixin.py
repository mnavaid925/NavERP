import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from django import forms
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.forms.models import ModelChoiceIterator

from apps.core.models import CustomFieldDefinition, CustomFieldValue
from apps.core.settings_engine import validate_custom_value
from apps.projects.models.MasterDataConfiguration.ProjectCustomFields import (
    CUSTOM_FIELD_ENTITY_LABELS,
    ProjectCustomField,
    sync_core_definition,
)

CUSTOM_FIELD_PREFIX = "custom_"
CUSTOM_FIELD_MAX_DEFINITIONS = 200
CUSTOM_FIELD_MAX_TEXT_LENGTH = 10000
CUSTOM_FIELD_MAX_JSON_BYTES = 16384


class _BoundedModelChoiceIterator(ModelChoiceIterator):
    def __iter__(self):
        limit = getattr(self.field, "choice_limit", None)
        if limit is not None:
            self.queryset = self.queryset[:limit]
        yield from super().__iter__()


def _bound_choices(field, limit):
    field.iterator = _BoundedModelChoiceIterator
    field.choice_limit = limit
    field.widget.choices = field.choices


def _input_name(definition):
    return f"{CUSTOM_FIELD_PREFIX}{definition.field_key}"


def _is_blank(value):
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, dict, set)):
        return not value
    return False


def _stored_value(value):
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, "pk"):
        return value.pk
    if isinstance(value, (list, tuple)):
        return [_stored_value(item) for item in value]
    return value


def _default_value(definition):
    raw = (definition.default_value or "").strip()
    if not raw:
        return None
    if definition.field_type == "boolean":
        return raw.lower() in {"1", "true", "yes", "on"}
    if definition.field_type == "multiselect":
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
            except (json.JSONDecodeError, RecursionError):
                parsed = []
            return parsed if isinstance(parsed, list) else []
        return [item.strip() for item in raw.split(",") if item.strip()]
    return raw


def _user_queryset(tenant):
    User = get_user_model()
    return User.objects.filter(
        Q(tenant=tenant) | Q(tenant__isnull=True),
        is_active=True,
    ).only(
        "id", "username", "first_name", "last_name", "email", "tenant_id", "is_active"
    ).order_by("username")


def _field_widget(definition):
    attrs = {"class": "form-input"}
    if definition.placeholder:
        attrs["placeholder"] = definition.placeholder
    if definition.field_type == "textarea":
        return forms.Textarea(attrs={**attrs, "class": "form-textarea", "rows": 4})
    if definition.field_type == "date":
        return forms.DateInput(attrs={**attrs, "type": "date"})
    if definition.field_type == "boolean":
        return forms.CheckboxInput(attrs={"class": "form-check"})
    if definition.field_type == "select":
        return forms.Select(attrs={"class": "form-select"})
    if definition.field_type == "multiselect":
        return forms.SelectMultiple(attrs={"class": "form-select"})
    if definition.field_type == "user_ref":
        return forms.Select(attrs={"class": "form-select"})
    if definition.field_type == "url":
        return forms.URLInput(attrs=attrs)
    if definition.field_type in {"integer", "decimal"}:
        return forms.NumberInput(attrs={**attrs, "step": "0.01" if definition.field_type == "decimal" else "1"})
    return forms.TextInput(attrs=attrs)


def _build_field(definition, tenant, initial=None):
    label = definition.label or definition.field_key
    help_text = definition.description or ""
    required = False
    if definition.field_type == "textarea":
        field = forms.CharField(
            label=label,
            required=required,
            max_length=CUSTOM_FIELD_MAX_TEXT_LENGTH,
            widget=_field_widget(definition),
            help_text=help_text,
            initial=initial,
        )
    elif definition.field_type == "integer":
        field = forms.IntegerField(
            label=label,
            required=required,
            min_value=definition.min_value,
            max_value=definition.max_value,
            widget=_field_widget(definition),
            help_text=help_text,
            initial=initial,
        )
    elif definition.field_type == "decimal":
        field = forms.DecimalField(
            label=label,
            required=required,
            min_value=definition.min_value,
            max_value=definition.max_value,
            widget=_field_widget(definition),
            help_text=help_text,
            initial=initial,
        )
    elif definition.field_type == "date":
        field = forms.DateField(
            label=label,
            required=required,
            widget=_field_widget(definition),
            help_text=help_text,
            initial=initial,
        )
    elif definition.field_type == "boolean":
        field = forms.BooleanField(
            label=label,
            required=required,
            widget=_field_widget(definition),
            help_text=help_text,
            initial=initial,
        )
    elif definition.field_type == "select":
        field = forms.ChoiceField(
            label=label,
            required=required,
            choices=[("", "—")] + [(str(value), str(value)) for value in definition.choices_list],
            widget=_field_widget(definition),
            help_text=help_text,
            initial=initial,
        )
    elif definition.field_type == "multiselect":
        field = forms.MultipleChoiceField(
            label=label,
            required=required,
            choices=[(str(value), str(value)) for value in definition.choices_list],
            widget=_field_widget(definition),
            help_text=help_text,
            initial=initial,
        )
    elif definition.field_type == "user_ref":
        field = forms.ModelChoiceField(
            label=label,
            required=required,
            queryset=_user_queryset(tenant),
            empty_label="—",
            widget=_field_widget(definition),
            help_text=help_text,
            initial=initial,
        )
        _bound_choices(field, 100)
    else:
        field = forms.CharField(
            label=label,
            required=required,
            max_length=CUSTOM_FIELD_MAX_TEXT_LENGTH,
            widget=_field_widget(definition),
            help_text=help_text,
            initial=initial,
        )
    field.custom_definition = definition
    field.custom_required = definition.is_required
    field.custom_visible = True
    return field


def _model_value(value):
    if hasattr(value, "pk"):
        return value.pk
    return value


def _compare_visibility(actual, expected, operator):
    operator = (operator or "equals").lower()
    actual = _model_value(actual)
    if operator in {"equals", "eq", "="}:
        if isinstance(actual, (list, tuple)):
            return str(expected) in {str(item) for item in actual}
        return str(actual) == str(expected)
    if operator in {"not_equals", "neq", "ne", "!="}:
        if isinstance(actual, (list, tuple)):
            return str(expected) not in {str(item) for item in actual}
        return str(actual) != str(expected)
    if operator in {"in", "one_of"}:
        values = expected if isinstance(expected, (list, tuple, set)) else [expected]
        return str(actual) in {str(item) for item in values}
    if operator in {"not_in", "none_of"}:
        values = expected if isinstance(expected, (list, tuple, set)) else [expected]
        return str(actual) not in {str(item) for item in values}
    if operator in {"contains", "includes"}:
        if isinstance(actual, (list, tuple, set)):
            return str(expected) in {str(item) for item in actual}
        return str(expected) in str(actual or "")
    if operator in {"not_contains", "not_includes"}:
        if isinstance(actual, (list, tuple, set)):
            return str(expected) not in {str(item) for item in actual}
        return str(expected) not in str(actual or "")
    if operator in {"truthy", "checked"}:
        return bool(actual)
    if operator in {"falsy", "unchecked"}:
        return not bool(actual)
    if operator in {"is_empty", "empty"}:
        return _is_blank(actual)
    if operator in {"not_empty", "present"}:
        return not _is_blank(actual)
    if operator in {"gt", ">"}:
        return Decimal(str(actual)) > Decimal(str(expected))
    if operator in {"gte", ">="}:
        return Decimal(str(actual)) >= Decimal(str(expected))
    if operator in {"lt", "<"}:
        return Decimal(str(actual)) < Decimal(str(expected))
    if operator in {"lte", "<="}:
        return Decimal(str(actual)) <= Decimal(str(expected))
    return str(actual) == str(expected)


def _rule_matches(rule, source):
    if not rule:
        return True
    if not isinstance(rule, dict):
        return True
    if "all" in rule and isinstance(rule["all"], list):
        return all(_rule_matches(item, source) for item in rule["all"])
    if "any" in rule and isinstance(rule["any"], list):
        return any(_rule_matches(item, source) for item in rule["any"])
    depends_on = rule.get("depends_on") or rule.get("field")
    if not depends_on:
        return True
    candidates = [str(depends_on)]
    if not str(depends_on).startswith(CUSTOM_FIELD_PREFIX):
        candidates.append(f"{CUSTOM_FIELD_PREFIX}{depends_on}")
    actual = None
    for candidate in candidates:
        if candidate in source:
            actual = source[candidate]
            break
    expected = rule.get("value", rule.get("equals"))
    try:
        return _compare_visibility(actual, expected, rule.get("operator"))
    except (InvalidOperation, TypeError, ValueError):
        return False


def _core_definition(definition, tenant_id):
    entity_label = CUSTOM_FIELD_ENTITY_LABELS[definition.target_entity]
    return CustomFieldDefinition.objects.filter(
        tenant_id=tenant_id,
        module_slug="projects",
        entity_label=entity_label,
        field_key=definition.field_key,
    ).first()


def _validate_value(definition, value, tenant, core_definition):
    if _is_blank(value):
        if definition.is_required:
            return False, None, "This field is required."
        return True, None, ""
    if definition.field_type == "multiselect":
        values = list(value or [])
        allowed = {str(item) for item in definition.choices_list}
        if any(str(item) not in allowed for item in values):
            return False, None, "Choose only configured options."
        try:
            encoded = json.dumps(_stored_value(values), ensure_ascii=False, separators=(",", ":"))
        except (RecursionError, TypeError, ValueError):
            return False, None, "Enter a valid list of options."
        if len(encoded.encode("utf-8")) > CUSTOM_FIELD_MAX_JSON_BYTES:
            return False, None, "The selected value is too large."
        return True, values, ""
    if definition.field_type == "user_ref":
        user = value
        if getattr(user, "tenant_id", None) not in (None, tenant.pk):
            return False, None, "That user belongs to another workspace."
        return True, user.pk, ""
    if definition.field_type == "url":
        raw = str(value).strip()
        parsed = urlparse(raw)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return False, None, "Enter a valid http or https URL."
    if core_definition is not None and definition.field_type in {
        "text", "textarea", "integer", "decimal", "date", "boolean", "select",
    }:
        ok, coerced, error = validate_custom_value(core_definition, value)
        if not ok:
            return False, None, error
        value = coerced
    elif definition.field_type == "integer":
        try:
            value = int(value)
        except (TypeError, ValueError):
            return False, None, "Enter a whole number."
    elif definition.field_type == "decimal":
        try:
            value = format(Decimal(str(value)), "f")
        except (InvalidOperation, TypeError, ValueError):
            return False, None, "Enter a number."
    elif definition.field_type == "date":
        try:
            value = value.isoformat() if hasattr(value, "isoformat") else str(value)
        except (AttributeError, ValueError):
            return False, None, "Enter a valid date."
    elif definition.field_type == "boolean":
        value = bool(value)
    else:
        value = str(value).strip()
    if definition.field_type == "select" and str(value) not in {
        str(item) for item in definition.choices_list
    }:
        return False, None, "Choose one of the configured options."
    if definition.regex_pattern and definition.field_type in {
        "text", "textarea", "url", "user_ref",
    }:
        try:
            if not re.fullmatch(definition.regex_pattern, str(value)):
                return False, None, "That value does not match the required format."
        except re.error:
            return False, None, "This field has an invalid validation expression."
    if definition.min_value is not None or definition.max_value is not None:
        try:
            numeric = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return False, None, "Enter a number within the configured range."
        if definition.min_value is not None and numeric < Decimal(str(definition.min_value)):
            return False, None, f"Enter a value of at least {definition.min_value}."
        if definition.max_value is not None and numeric > Decimal(str(definition.max_value)):
            return False, None, f"Enter a value no greater than {definition.max_value}."
    if definition.field_type in {"text", "textarea", "url"} and len(str(value)) > CUSTOM_FIELD_MAX_TEXT_LENGTH:
        return False, None, f"Enter no more than {CUSTOM_FIELD_MAX_TEXT_LENGTH} characters."
    if definition.field_type == "multiselect":
        try:
            encoded = json.dumps(_stored_value(value), ensure_ascii=False, separators=(",", ":"))
        except (RecursionError, TypeError, ValueError):
            return False, None, "Enter a valid list of options."
        if len(encoded.encode("utf-8")) > CUSTOM_FIELD_MAX_JSON_BYTES:
            return False, None, "The selected value is too large."
    return True, _stored_value(value), ""


def _display_value(definition, value, tenant_id):
    if value is None:
        return "Not captured"
    if definition.field_type == "boolean":
        return "Yes" if value else "No"
    if definition.field_type == "user_ref":
        User = get_user_model()
        user = User.objects.filter(
            pk=value,
        ).filter(Q(tenant_id=tenant_id) | Q(tenant_id__isnull=True)).first()
        if user is not None:
            return user.get_full_name() or user.username
        return str(value)
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value) or "Not captured"
    return str(value)


def custom_values_for_object(obj):
    if obj is None or not getattr(obj, "pk", None) or not getattr(obj, "tenant_id", None):
        return []
    target_by_model = {
        "project": "project",
        "projecttask": "task",
        "projectmilestone": "milestone",
        "projectrisk": "risk",
        "projectteam": "team",
    }
    target = target_by_model.get(obj._meta.model_name)
    if target is None:
        return []
    entity_label = CUSTOM_FIELD_ENTITY_LABELS[target]
    definitions = list(
        ProjectCustomField.objects.filter(
            tenant_id=obj.tenant_id,
            target_entity=target,
        ).order_by("form_section", "display_order", "id")[:CUSTOM_FIELD_MAX_DEFINITIONS]
    )
    if not definitions:
        return []
    core_definitions = {
        item.field_key: item
        for item in CustomFieldDefinition.objects.filter(
            tenant_id=obj.tenant_id,
            module_slug="projects",
            entity_label=entity_label,
        )
    }
    values = {
        item.definition.field_key: item.value
        for item in CustomFieldValue.objects.filter(
            tenant_id=obj.tenant_id,
            entity_label=entity_label,
            object_id=obj.pk,
            definition__module_slug="projects",
        ).select_related("definition")
    }
    result = []
    for definition in definitions:
        core_definition = core_definitions.get(definition.field_key)
        raw_value = values.get(definition.field_key) if core_definition else None
        result.append({
            "label": definition.label or definition.field_key,
            "value": _display_value(definition, raw_value, obj.tenant_id),
            "is_active": definition.is_active,
            "has_value": raw_value is not None,
        })
    return result


class ProjectCustomFieldFormMixin:
    custom_field_target = None

    def __init__(self, *args, **kwargs):
        self.updated_by = kwargs.pop("updated_by", None)
        self._custom_definitions = []
        self.custom_field_names = []
        super().__init__(*args, **kwargs)
        self._install_custom_fields()

    def _visibility_source(self, cleaned=None):
        source = {}
        if cleaned:
            source.update(cleaned)
        if self.is_bound:
            for key in self.data:
                if not key.startswith(CUSTOM_FIELD_PREFIX):
                    source[key] = self.data.get(key)
        for key, value in (self.initial or {}).items():
            source.setdefault(key, value)
        if self.instance is not None and self.instance.pk:
            for field in self.instance._meta.fields:
                source.setdefault(field.name, getattr(self.instance, field.name, None))
        for name in self.custom_field_names:
            if name in self.fields and name not in source:
                source[name] = self.fields[name].initial
        return source

    def _install_custom_fields(self):
        tenant = self.tenant
        target = self.custom_field_target
        if tenant is None or not target:
            return
        entity_label = CUSTOM_FIELD_ENTITY_LABELS.get(target)
        if entity_label is None:
            return
        definitions = list(
            ProjectCustomField.objects.filter(
                tenant_id=tenant.pk,
                target_entity=target,
                is_active=True,
            ).order_by("form_section", "display_order", "id")[:CUSTOM_FIELD_MAX_DEFINITIONS]
        )
        stored = {}
        if self.instance is not None and self.instance.pk:
            stored = {
                item.definition.field_key: item.value
                for item in CustomFieldValue.objects.filter(
                    tenant_id=tenant.pk,
                    entity_label=entity_label,
                    object_id=self.instance.pk,
                    definition__module_slug="projects",
                ).select_related("definition")
            }
        source = self._visibility_source()
        for definition in definitions:
            name = _input_name(definition)
            if name in self.fields:
                continue
            initial = stored[definition.field_key] if definition.field_key in stored else _default_value(definition)
            field = _build_field(definition, tenant, initial=initial)
            self.fields[name] = field
            self._custom_definitions.append(definition)
            self.custom_field_names.append(name)
            field.custom_visible = _rule_matches(definition.visibility_rule, source)
            field.required = field.custom_visible and definition.is_required
        source = self._visibility_source()
        for definition in self._custom_definitions:
            name = _input_name(definition)
            field = self.fields[name]
            field.custom_visible = _rule_matches(definition.visibility_rule, source)
            field.required = field.custom_visible and definition.is_required

    @property
    def custom_fields(self):
        return [
            self[name]
            for name in self.custom_field_names
            if getattr(self.fields[name], "custom_visible", True)
        ]

    def clean(self):
        cleaned = super().clean()
        for definition in self._custom_definitions:
            name = _input_name(definition)
            field = self.fields[name]
            visible = _rule_matches(definition.visibility_rule, cleaned)
            field.custom_visible = visible
            field.required = visible and definition.is_required
            if not visible:
                self._errors.pop(name, None)
                cleaned.pop(name, None)
                continue
            value = cleaned.get(name)
            if definition.field_type == "boolean" and self.is_bound and name in self.data:
                submitted = self.data.getlist(name) if hasattr(self.data, "getlist") else [self.data.get(name)]
                normalized = str(submitted[-1]).strip().lower() if len(submitted) == 1 else None
                if normalized in {"true", "1", "yes", "on"}:
                    value = True
                elif normalized in {"false", "0", "no", "off", ""}:
                    value = False
                else:
                    self.add_error(name, "Choose a valid boolean value.")
                    cleaned.pop(name, None)
                    continue
                cleaned[name] = value
            elif (
                definition.field_type == "boolean"
                and not definition.is_required
                and self.is_bound
                and name not in self.data
            ):
                cleaned[name] = None
                value = None
            missing = definition.is_required and (
                (
                    definition.field_type == "boolean"
                    and self.is_bound
                    and name not in self.data
                )
                or (
                    definition.field_type != "boolean"
                    and _is_blank(value)
                )
            )
            if missing:
                if not self._errors.get(name):
                    self.add_error(name, "This field is required.")
                continue
            core_definition = _core_definition(definition, self.tenant.pk)
            ok, coerced, error = _validate_value(definition, value, self.tenant, core_definition)
            if not ok:
                self.add_error(name, error)
            else:
                cleaned[name] = coerced
        return cleaned

    def save_custom_values(self, instance, updated_by=None):
        if self._errors or not getattr(instance, "pk", None) or not getattr(instance, "tenant_id", None):
            return
        tenant = self.tenant
        if tenant is None or instance.tenant_id != tenant.pk:
            return
        entity_label = CUSTOM_FIELD_ENTITY_LABELS[self.custom_field_target]
        if instance._meta.model_name != entity_label.rsplit(".", 1)[-1].lower():
            return
        for definition in self._custom_definitions:
            name = _input_name(definition)
            if not getattr(self.fields[name], "custom_visible", True) or name not in self.cleaned_data:
                continue
            if not ProjectCustomField.objects.filter(
                pk=definition.pk,
                tenant_id=tenant.pk,
                is_active=True,
            ).exists():
                continue
            core_definition = _core_definition(definition, tenant.pk)
            if core_definition is None:
                core_definition = sync_core_definition(definition)
            if core_definition is None:
                continue
            value = self.cleaned_data[name]
            if _is_blank(value) and not definition.is_required:
                updated = CustomFieldValue.objects.filter(
                    definition=core_definition,
                    entity_label=entity_label,
                    object_id=instance.pk,
                ).first()
                if updated is not None:
                    updated.value = None
                    updated.updated_by = updated_by
                    updated.save(update_fields=["value", "updated_by", "updated_at"])
                continue
            CustomFieldValue.objects.update_or_create(
                definition=core_definition,
                entity_label=entity_label,
                object_id=instance.pk,
                defaults={
                    "tenant_id": tenant.pk,
                    "value": _stored_value(value),
                    "updated_by": updated_by,
                },
            )

    def save(self, commit=True):
        if not commit:
            return super().save(commit=False)
        with transaction.atomic():
            instance = super().save(commit=True)
            self.save_custom_values(instance, updated_by=self.updated_by)
        return instance
