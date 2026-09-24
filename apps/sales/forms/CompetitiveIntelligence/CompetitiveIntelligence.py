from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q

from apps.core.models import Party
from apps.sales.forms._common import TenantModelForm, TenantUniqueMixin
from apps.sales.models.CompetitiveIntelligence.CompetitiveIntelligence import (
    CompetitorProfile,
    OpportunityCompetitor,
)


class CompetitorProfileForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CompetitorProfile
        fields = [
            "party",
            "aliases",
            "website_url",
            "description",
            "market_positioning",
            "strengths",
            "weaknesses",
            "differentiators",
            "objection_handling",
            "last_reviewed_on",
            "is_active",
        ]

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        tenant_id = getattr(tenant, "pk", tenant)
        if tenant_id is None:
            self.fields["party"].queryset = Party.objects.none()
        else:
            self.fields["party"].queryset = Party.objects.filter(
                tenant_id=tenant_id,
                kind="organization",
            ).order_by("name")
        if self.instance.tenant_id is None and tenant is not None:
            self.instance.tenant = tenant

    def clean(self):
        cleaned = super().clean()
        tenant_id = getattr(self.tenant, "pk", self.tenant)
        if tenant_id is None:
            self.add_error(None, "A tenant workspace is required.")
        party = cleaned.get("party")
        if party is not None and (party.tenant_id != tenant_id or party.kind != "organization"):
            self.add_error("party", "Choose a same-tenant organization.")
        return cleaned


class OpportunityCompetitorForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = OpportunityCompetitor
        fields = [
            "competitor_profile",
            "relationship",
            "is_primary",
            "pricing_notes",
            "deal_notes",
            "positioning_notes",
        ]

    def __init__(self, *args, opportunity=None, tenant=None, **kwargs):
        self.opportunity = opportunity
        super().__init__(*args, tenant=tenant, **kwargs)
        tenant_id = getattr(tenant, "pk", tenant)
        if tenant_id is None:
            self.fields["competitor_profile"].queryset = CompetitorProfile.objects.none()
        else:
            profile_filter = Q(tenant_id=tenant_id, is_active=True)
            if self.instance.pk and self.instance.competitor_profile_id:
                profile_filter |= Q(
                    pk=self.instance.competitor_profile_id,
                    tenant_id=tenant_id,
                )
            self.fields["competitor_profile"].queryset = CompetitorProfile.objects.filter(
                profile_filter
            ).select_related("party").order_by("party__name")
        if self.instance.tenant_id is None and tenant is not None:
            self.instance.tenant = tenant
        if self.instance.opportunity_id is None and opportunity is not None:
            self.instance.opportunity = opportunity

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
        elif opportunity.tenant_id != tenant_id:
            self.add_error(None, "The opportunity must belong to this workspace.")
        elif self.instance.pk and self.instance.opportunity_id != opportunity.pk:
            self.add_error(None, "A competitor link cannot move to another opportunity.")
        profile = cleaned.get("competitor_profile")
        if profile is not None:
            if profile.tenant_id != tenant_id:
                self.add_error("competitor_profile", "Choose a competitor profile from this workspace.")
            if not profile.is_active and (
                not self.instance.pk or profile.pk != self.instance.competitor_profile_id
            ):
                self.add_error("competitor_profile", "Choose an active competitor profile.")
        if tenant_id is not None and opportunity is not None and profile is not None:
            duplicates = OpportunityCompetitor.objects.filter(
                tenant_id=tenant_id,
                opportunity=opportunity,
                competitor_profile=profile,
            )
            if self.instance.pk:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                self.add_error("competitor_profile", "That competitor is already linked to this opportunity.")
        return cleaned
