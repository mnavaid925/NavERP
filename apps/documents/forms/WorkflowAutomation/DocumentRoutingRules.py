import json

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.accounts.models import Role
from apps.core.models import BusinessRule, OrgUnit
from apps.documents.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.documents.models.StorageRepository.DocumentFolders import DocumentFolder
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.models.WorkflowAutomation.DocumentProcessDefinitions import (
    DocumentProcessDefinition,
)
from apps.documents.models.WorkflowAutomation.DocumentRoutingRules import DocumentRoutingRule
from apps.documents.services.workflow_automation import (
    validate_routing_rule_config,
    validate_rule_conditions,
    validate_validation_rules,
)


def _parse_json_value(val, expected_type, label):
    if val is None or val == "":
        return expected_type()
    if isinstance(val, expected_type):
        return val
    if isinstance(val, str):
        stripped = val.strip()
        if not stripped:
            return expected_type()
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Invalid JSON for {label}: {exc}") from exc
        if not isinstance(parsed, expected_type):
            type_label = "array" if expected_type is list else "object"
            raise ValidationError(f"{label} must be a JSON {type_label}.")
        return parsed
    raise ValidationError(f"Invalid structure for {label}.")


class DocumentRoutingRuleForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DocumentRoutingRule
        fields = [
            "name",
            "description",
            "process_definition",
            "core_rule_ref",
            "rule_type",
            "trigger_event",
            "priority",
            "source_folder",
            "target_document_type",
            "target_classification",
            "condition_logic_mode",
            "conditions_json",
            "else_branch_enabled",
            "else_action_json",
            "validation_rules_json",
            "auto_populate_json",
            "route_action",
            "destination_folder",
            "route_to_org_unit",
            "route_to_role",
            "route_to_user",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Confidential Contract Legal Triage"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
            "process_definition": forms.Select(attrs={"class": "form-select"}),
            "core_rule_ref": forms.Select(attrs={"class": "form-select"}),
            "rule_type": forms.Select(attrs={"class": "form-select"}),
            "trigger_event": forms.Select(attrs={"class": "form-select"}),
            "priority": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "source_folder": forms.Select(attrs={"class": "form-select"}),
            "target_document_type": forms.Select(attrs={"class": "form-select"}),
            "target_classification": forms.Select(attrs={"class": "form-select"}),
            "condition_logic_mode": forms.Select(attrs={"class": "form-select"}),
            "conditions_json": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 4}),
            "else_branch_enabled": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "else_action_json": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 3}),
            "validation_rules_json": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 3}),
            "auto_populate_json": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 3}),
            "route_action": forms.Select(attrs={"class": "form-select"}),
            "destination_folder": forms.Select(attrs={"class": "form-select"}),
            "route_to_org_unit": forms.Select(attrs={"class": "form-select"}),
            "route_to_role": forms.Select(attrs={"class": "form-select"}),
            "route_to_user": forms.Select(attrs={"class": "form-select"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        User = get_user_model()
        if self.tenant:
            self.fields["process_definition"].queryset = DocumentProcessDefinition.objects.filter(
                tenant=self.tenant
            ).order_by("code", "-version_number")
            self.fields["core_rule_ref"].queryset = BusinessRule.objects.filter(
                tenant=self.tenant
            ).order_by("priority", "name")
            self.fields["source_folder"].queryset = DocumentFolder.objects.filter(
                tenant=self.tenant
            ).order_by("path", "name")
            self.fields["destination_folder"].queryset = DocumentFolder.objects.filter(
                tenant=self.tenant
            ).order_by("path", "name")
            self.fields["route_to_org_unit"].queryset = OrgUnit.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["route_to_role"].queryset = Role.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["route_to_user"].queryset = User.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("username")
        else:
            self.fields["process_definition"].queryset = DocumentProcessDefinition.objects.none()
            self.fields["core_rule_ref"].queryset = BusinessRule.objects.none()
            self.fields["source_folder"].queryset = DocumentFolder.objects.none()
            self.fields["destination_folder"].queryset = DocumentFolder.objects.none()
            self.fields["route_to_org_unit"].queryset = OrgUnit.objects.none()
            self.fields["route_to_role"].queryset = Role.objects.none()
            self.fields["route_to_user"].queryset = User.objects.none()

        for opt in (
            "description",
            "process_definition",
            "core_rule_ref",
            "source_folder",
            "target_document_type",
            "target_classification",
            "conditions_json",
            "else_action_json",
            "validation_rules_json",
            "auto_populate_json",
            "destination_folder",
            "route_to_org_unit",
            "route_to_role",
            "route_to_user",
        ):
            self.fields[opt].required = False

    def clean_conditions_json(self):
        clauses = _parse_json_value(self.cleaned_data.get("conditions_json"), list, "conditions")
        return validate_rule_conditions(clauses)

    def clean_else_action_json(self):
        return _parse_json_value(self.cleaned_data.get("else_action_json"), dict, "else action")

    def clean_validation_rules_json(self):
        rules = _parse_json_value(self.cleaned_data.get("validation_rules_json"), list, "validation rules")
        return validate_validation_rules(rules)

    def clean_auto_populate_json(self):
        return _parse_json_value(self.cleaned_data.get("auto_populate_json"), dict, "auto-populate config")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(
            self,
            cleaned,
            [
                "process_definition",
                "core_rule_ref",
                "source_folder",
                "destination_folder",
                "route_to_org_unit",
                "route_to_role",
                "route_to_user",
            ],
        )
        try:
            validate_routing_rule_config(
                cleaned.get("conditions_json"),
                cleaned.get("validation_rules_json"),
                route_action=cleaned.get("route_action"),
                else_branch_enabled=bool(cleaned.get("else_branch_enabled")),
                else_action=cleaned.get("else_action_json"),
            )
        except ValidationError as exc:
            for field, msgs in exc.message_dict.items():
                if field in self.fields:
                    for msg in msgs:
                        self.add_error(field, msg)
                else:
                    raise
        return cleaned


class RoutingRuleSimulatorForm(forms.Form):
    document = forms.ModelChoiceField(
        queryset=Document.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    rule = forms.ModelChoiceField(
        queryset=DocumentRoutingRule.objects.none(),
        required=False,
        empty_label="All Active Rules (Priority Chain)",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    trigger_event = forms.ChoiceField(
        required=False,
        choices=[("", "Any Trigger Event")] + list(DocumentRoutingRule.TRIGGER_EVENT_CHOICES),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    apply_mutations = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={"class": "form-checkbox"}),
    )

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant is not None:
            self.fields["document"].queryset = (
                Document.objects.filter(tenant=tenant)
                .only("id", "number", "title", "current_version_label", "created_at", "tenant_id")
                .order_by("-created_at", "title")
            )
            self.fields["rule"].queryset = (
                DocumentRoutingRule.objects.filter(tenant=tenant)
                .only("id", "number", "name", "priority", "tenant_id")
                .order_by("priority", "name")
            )
        else:
            self.fields["document"].queryset = Document.objects.none()
            self.fields["rule"].queryset = DocumentRoutingRule.objects.none()
