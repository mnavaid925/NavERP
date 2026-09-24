from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models

from apps.sales.models._base import TenantNumbered, TenantOwned


class CompetitorProfile(TenantNumbered):
    NUMBER_PREFIX = "CMP"

    party = models.OneToOneField(
        "core.Party",
        on_delete=models.CASCADE,
        related_name="sales_competitor_profile",
    )
    aliases = models.TextField(blank=True)
    website_url = models.URLField(max_length=500, blank=True)
    description = models.TextField(blank=True)
    market_positioning = models.TextField(blank=True)
    strengths = models.TextField(blank=True)
    weaknesses = models.TextField(blank=True)
    differentiators = models.TextField(blank=True)
    objection_handling = models.TextField(blank=True)
    last_reviewed_on = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["party__name", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="sales_cmp_tenant_number_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "is_active"],
                name="sales_cmp_tenant_active_idx",
            ),
        ]

    def _party_is_same_tenant_organization(self):
        if not self.party_id:
            return True
        party_model = self._meta.get_field("party").remote_field.model
        return party_model._default_manager.filter(
            pk=self.party_id,
            tenant_id=self.tenant_id,
            kind="organization",
        ).exists()

    def clean(self):
        super().clean()
        if self.tenant_id and not self._party_is_same_tenant_organization():
            raise ValidationError({"party": "Choose a same-tenant organization."})

    def delete(self, *args, **kwargs):
        if OpportunityCompetitor.objects.filter(competitor_profile=self).exists():
            raise ValidationError("A referenced competitor profile cannot be deleted.")
        return super().delete(*args, **kwargs)

    def __str__(self):
        try:
            party = self.party if self.party_id else None
        except ObjectDoesNotExist:
            party = None
        return f"{self.number or '—'} · {party or '—'}"


class OpportunityCompetitor(TenantOwned):
    RELATIONSHIP_CHOICES = [
        ("identified", "Identified"),
        ("evaluating", "Evaluating"),
        ("shortlisted", "Shortlisted"),
        ("preferred", "Preferred"),
        ("incumbent", "Incumbent"),
        ("eliminated", "Eliminated"),
        ("lost_to", "Lost To"),
        ("beaten", "Beaten"),
        ("withdrew", "Withdrew"),
    ]

    opportunity = models.ForeignKey(
        "crm.Opportunity",
        on_delete=models.CASCADE,
        related_name="sales_competitors",
    )
    competitor_profile = models.ForeignKey(
        "sales.CompetitorProfile",
        on_delete=models.PROTECT,
    )
    relationship = models.CharField(max_length=20, choices=RELATIONSHIP_CHOICES)
    is_primary = models.BooleanField(default=False)
    pricing_notes = models.TextField(blank=True)
    deal_notes = models.TextField(blank=True)
    positioning_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-is_primary", "relationship", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "opportunity", "competitor_profile"],
                name="sales_oc_tno_profile_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "opportunity", "relationship"],
                name="sales_oc_tno_relationship_idx",
            ),
            models.Index(
                fields=["tenant", "opportunity", "is_primary"],
                name="sales_oc_tno_primary_idx",
            ),
        ]

    def _relation_belongs_to_tenant(self, field_name):
        relation_id = getattr(self, f"{field_name}_id", None)
        if not relation_id:
            return True
        field = self._meta.get_field(field_name)
        related_model = field.remote_field.model
        return related_model._default_manager.filter(
            pk=relation_id,
            tenant_id=self.tenant_id,
        ).exists()

    def clean(self):
        super().clean()
        if not self.tenant_id:
            return
        for field_name, message in (
            ("opportunity", "The opportunity must belong to this workspace."),
            ("competitor_profile", "Choose a competitor profile from this workspace."),
        ):
            if not self._relation_belongs_to_tenant(field_name):
                raise ValidationError({field_name: message})

    def __str__(self):
        try:
            opportunity = self.opportunity if self.opportunity_id else None
        except ObjectDoesNotExist:
            opportunity = None
        try:
            profile = self.competitor_profile if self.competitor_profile_id else None
        except ObjectDoesNotExist:
            profile = None
        relationship = self.get_relationship_display() or "—"
        return " · ".join(
            [str(opportunity) if opportunity is not None else "—", str(profile) if profile is not None else "—", relationship]
        )
