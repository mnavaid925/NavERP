from django import forms
from django.core.exceptions import ValidationError

from apps.accounts.models import User
from apps.sales.forms._common import TenantActionForm, TenantModelForm, TenantUniqueMixin, _reject_foreign, tenant_leads, tenant_territories, tenant_users
from apps.sales.models import LeadRoutingRule, validate_routing_conditions


class LeadRoutingRuleForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = LeadRoutingRule
        fields = [
            "name", "description", "is_active", "priority", "match_mode", "conditions",
            "is_catch_all", "assignment_mode", "default_owner", "territory", "eligible_owners",
            "fallback_owner", "max_open_leads",
        ]
        widgets = {"conditions": forms.Textarea(attrs={"rows": 8})}

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        self.fields["default_owner"].queryset = tenant_users(tenant)
        self.fields["fallback_owner"].queryset = tenant_users(tenant)
        self.fields["eligible_owners"].queryset = tenant_users(tenant)
        self.fields["territory"].queryset = tenant_territories(tenant)

    def clean(self):
        cleaned = super().clean()
        try:
            cleaned["conditions"] = validate_routing_conditions(cleaned.get("conditions"), cleaned.get("is_catch_all", False))
        except ValidationError as exc:
            self.add_error("conditions", exc)
        _reject_foreign(self, cleaned, ["default_owner", "territory", "fallback_owner", "eligible_owners"])
        owners = cleaned.get("eligible_owners")
        if cleaned.get("assignment_mode") == "round_robin" and owners is not None and not owners.exists():
            self.add_error("eligible_owners", "A round-robin rule needs eligible owners.")
        if cleaned.get("assignment_mode") == "territory_manager":
            territory = cleaned.get("territory")
            tenant_id = getattr(self.tenant, "pk", self.tenant)
            if territory:
                manager = User._default_manager.filter(pk=territory.manager_id, tenant_id=tenant_id, is_active=True).first() if territory.manager_id else None
                if manager is None:
                    self.add_error("territory", "Choose a territory with an active manager from this workspace.")
        return cleaned


class LeadRoutingPreviewForm(TenantActionForm):
    lead = forms.ModelChoiceField(queryset=None)

    def __init__(self, *args, tenant=None, leads=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        self.fields["lead"].queryset = leads if leads is not None else tenant_leads(tenant)


class LeadRoutingRunForm(LeadRoutingPreviewForm):
    pass
