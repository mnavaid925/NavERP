from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q

from apps.accounts.models import User
from apps.core.models import OrgUnit
from apps.crm.models import Opportunity
from apps.sales.forms._common import TenantModelForm
from apps.sales.models.OpportunityTeams.OpportunityTeams import OpportunityTeamMember


class OpportunityTeamMemberForm(TenantModelForm):
    class Meta:
        model = OpportunityTeamMember
        fields = ["user", "org_unit", "role", "responsibility", "is_active"]

    def __init__(self, *args, opportunity=None, tenant=None, **kwargs):
        self.opportunity = opportunity
        super().__init__(*args, tenant=tenant, **kwargs)
        if self.instance.tenant_id is None and tenant is not None:
            self.instance.tenant = tenant
        if self.instance.opportunity_id is None and opportunity is not None:
            self.instance.opportunity = opportunity
        if tenant is None:
            self.fields["user"].queryset = User.objects.none()
            self.fields["org_unit"].queryset = OrgUnit.objects.none()
        else:
            user_filter = Q(tenant=tenant, is_active=True)
            if self.instance.pk and self.instance.user_id:
                user_filter |= Q(pk=self.instance.user_id, tenant=tenant)
            self.fields["user"].queryset = User.objects.filter(user_filter).order_by("email")
            self.fields["org_unit"].queryset = OrgUnit.objects.filter(tenant=tenant).order_by("name")

    def clean(self):
        cleaned = super().clean()
        tenant_id = getattr(self.tenant, "pk", self.tenant)
        opportunity = self.opportunity
        if opportunity is None and self.instance.opportunity_id:
            try:
                opportunity = self.instance.opportunity
            except ObjectDoesNotExist:
                opportunity = None
        if tenant_id is None:
            self.add_error(None, "A tenant workspace is required.")
        if opportunity is None:
            self.add_error(None, "Choose an opportunity from this workspace.")
        else:
            if opportunity.tenant_id != tenant_id:
                self.add_error(None, "The opportunity must belong to this workspace.")
            if self.instance.pk and self.instance.opportunity_id != opportunity.pk:
                self.add_error(None, "A team member cannot move to another opportunity.")
        user = cleaned.get("user")
        if user is not None:
            if user.tenant_id != tenant_id:
                self.add_error("user", "The user must belong to this workspace.")
            if not user.is_active and (self.instance.pk is None or user.pk != self.instance.user_id):
                self.add_error("user", "Choose an active user for this membership.")
        org_unit = cleaned.get("org_unit")
        if org_unit is not None and org_unit.tenant_id != tenant_id:
            self.add_error("org_unit", "The organizational unit must belong to this workspace.")
        role = cleaned.get("role")
        if tenant_id is not None and opportunity is not None and user is not None and role:
            duplicates = OpportunityTeamMember.objects.filter(
                tenant_id=tenant_id,
                opportunity=opportunity,
                user=user,
                role=role,
            )
            if self.instance.pk:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                self.add_error("role", "This user already has that role on the opportunity.")
        return cleaned
