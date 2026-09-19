"""core — 0.10 forms (system configuration)."""
from apps.core.forms._common import *  # noqa: F401,F403
from apps.core.models import (
    BusinessCalendar,
    CustomFieldDefinition,
    CustomFieldValue,
    FeatureFlag,
    Holiday,
    NumberingScheme,
    SettingDefinition,
    SettingValue,
)


class SettingDefinitionForm(TenantModelForm):
    """`choices` is redeclared as a CharField ON PURPOSE.

    The model field is a JSONField, and Django's `forms.JSONField` validates the input as JSON in
    `to_python` — BEFORE any `clean_<field>` runs. So an operator typing `a, b, c` failed validation
    and `clean_choices` never executed: the form was unusable for its main input. Declaring a
    CharField here lets the raw string through to `clean_choices`, which splits it.
    """

    choices = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"class": "form-input"}),
        help_text="For a choice setting, the options comma-separated. e.g. iso, uk, us",
    )

    class Meta:
        model = SettingDefinition
        fields = ["key", "label", "module_slug", "value_type", "default_value", "choices",
                  "help_text", "is_locked"]

    def clean_choices(self):
        raw = self.cleaned_data.get("choices")
        if isinstance(raw, str):
            return [c.strip() for c in raw.split(",") if c.strip()]
        return raw or []


class SettingValueForm(TenantModelForm):
    """One tenant's override. `definition` is excluded: the override is always created FROM a
    definition's page, so a free choice of definition here would let one be set twice."""

    class Meta:
        model = SettingValue
        fields = ["value"]

    def __init__(self, *args, definition=None, **kwargs):
        self.definition = definition
        super().__init__(*args, **kwargs)
        if definition is not None and definition.is_locked:
            # Locked settings render but cannot be changed — disabling is honest, hiding is not.
            self.fields["value"].disabled = True
            self.fields["value"].help_text = "This setting is locked and cannot be overridden."

    def clean_value(self):
        value = self.cleaned_data.get("value", "")
        definition = self.definition
        if definition is None:
            return value
        from apps.core.settings_engine import validate_custom_value
        ok, coerced, error = validate_custom_value(
            type("D", (), {"field_type": definition.value_type, "is_required": False,
                           "choices": definition.choices, "validation_regex": ""})(),
            value)
        if not ok:
            raise forms.ValidationError(error)
        return value


class FeatureFlagForm(TenantModelForm):
    class Meta:
        model = FeatureFlag
        fields = ["key", "label", "description", "is_enabled", "applies_to_plan", "exempt_roles",
                  "notes"]
        widgets = {"exempt_roles": forms.CheckboxSelectMultiple()}

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        # `exempt_roles` is a ModelMultipleChoiceField, which TenantModelForm does NOT scope (it only
        # narrows ModelChoiceField) — so without this the picker would list every other workspace's
        # roles. Same leak 0.6's mask form had to close explicitly.
        if tenant is not None:
            from apps.accounts.models import Role
            self.fields["exempt_roles"].queryset = Role.objects.filter(tenant=tenant).order_by("name")


class NumberingSchemeForm(TenantModelForm):
    class Meta:
        model = NumberingScheme
        fields = ["document_kind", "prefix", "padding_width", "reset_rule", "is_active", "notes"]

    def clean_prefix(self):
        prefix = (self.cleaned_data.get("prefix") or "").strip().upper()
        if not prefix:
            raise forms.ValidationError("A scheme needs a prefix.")
        return prefix

    def clean_padding_width(self):
        width = self.cleaned_data["padding_width"]
        if not (1 <= width <= 12):
            raise forms.ValidationError("Padding must be between 1 and 12 digits.")
        return width


class BusinessCalendarForm(TenantModelForm):
    """`working_days` is a JSON list of ISO weekdays; the form takes a comma-separated string."""

    working_days = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"class": "form-input"}),
        help_text="ISO weekday numbers, comma-separated. 1=Mon … 7=Sun. e.g. 1,2,3,4,5",
    )

    class Meta:
        model = BusinessCalendar
        fields = ["timezone_name", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["working_days"].initial = ",".join(
                str(d) for d in (self.instance.working_days or []))

    def clean_working_days(self):
        raw = (self.cleaned_data.get("working_days") or "").strip()
        if not raw:
            return []
        days = []
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            if not part.isdigit() or not (1 <= int(part) <= 7):
                raise forms.ValidationError("Use ISO weekday numbers 1-7, comma-separated.")
            days.append(int(part))
        return sorted(set(days))

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.working_days = self.cleaned_data["working_days"]
        if commit:
            obj.save()
        return obj


class HolidayForm(TenantModelForm):
    class Meta:
        model = Holiday
        fields = ["name", "date", "is_recurring", "region", "notes"]


class CustomFieldDefinitionForm(TenantModelForm):
    """`choices` is redeclared as a CharField for the same reason as SettingDefinitionForm: the model
    field is a JSONField, whose form field rejects `a, b` as invalid JSON before `clean_choices` runs."""

    choices = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"class": "form-input"}),
        help_text="For a choice field, the options comma-separated. e.g. search, referral, event",
    )

    class Meta:
        model = CustomFieldDefinition
        fields = ["module_slug", "entity_label", "field_key", "label", "field_type", "is_required",
                  "choices", "validation_regex", "help_text", "display_order", "is_active"]

    def clean_choices(self):
        raw = self.cleaned_data.get("choices")
        if isinstance(raw, str):
            return [c.strip() for c in raw.split(",") if c.strip()]
        return raw or []

    def clean_validation_regex(self):
        import re
        pattern = (self.cleaned_data.get("validation_regex") or "").strip()
        if not pattern:
            return ""
        try:
            re.compile(pattern)
        except re.error as exc:
            # Refused HERE rather than tolerated: the engine tolerates a broken regex at write time
            # so it cannot block a save, but a definition should never be saved with one.
            raise forms.ValidationError(f"That is not a valid regular expression: {exc}")
        return pattern

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("field_type") == "choice" and not cleaned.get("choices"):
            self.add_error("choices", "A choice field needs at least one option.")
        return cleaned


class CustomFieldValueForm(TenantModelForm):
    """Writes ONE value, validated against its definition.

    `value` is redeclared as a CharField for the THIRD instance of the same trap in this file: the
    model field is a JSONField, so Django's `forms.JSONField` rejects a plain `a` as invalid JSON
    before `clean()` ever runs. The raw string is exactly what `validate_custom_value()` wants — it
    coerces per the definition's `field_type` — so the form must not pre-judge it as JSON.
    """

    value = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"class": "form-input"}),
        help_text="Enter the value; it is validated against the field's type and rules.",
    )

    class Meta:
        model = CustomFieldValue
        fields = ["entity_label", "object_id", "value"]

    def __init__(self, *args, definition=None, **kwargs):
        self.definition = definition
        super().__init__(*args, **kwargs)
        if definition is not None:
            # The entity is fixed by the definition; letting it be re-chosen would let a value be
            # filed against an entity the field was never defined for.
            self.fields["entity_label"].initial = definition.entity_label
            self.fields["entity_label"].disabled = True

    def clean(self):
        cleaned = super().clean()
        if self.definition is None:
            return cleaned
        from apps.core.settings_engine import validate_custom_value
        ok, coerced, error = validate_custom_value(self.definition, cleaned.get("value"))
        if not ok:
            self.add_error("value", error)
        else:
            cleaned["value"] = coerced
        return cleaned
