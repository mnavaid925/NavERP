from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models

from apps.sales.models._base import TenantNumbered


class OpportunityTeamMember(TenantNumbered):
    NUMBER_PREFIX = "OTM"

    ROLE_CHOICES = [
        ("co_owner", "Co-Owner"),
        ("collaborator", "Collaborator"),
        ("sales_support", "Sales Support"),
        ("solution_consultant", "Solution Consultant"),
        ("executive_sponsor", "Executive Sponsor"),
        ("approver", "Approver"),
        ("observer", "Observer"),
    ]

    opportunity = models.ForeignKey(
        "crm.Opportunity",
        on_delete=models.CASCADE,
        related_name="sales_team_members",
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    responsibility = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["is_active", "role", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "opportunity", "user", "role"],
                name="sales_otm_tno_ur_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "opportunity", "is_active"],
                name="sales_otm_tno_active_idx",
            ),
            models.Index(
                fields=["tenant", "user"],
                name="sales_otm_tenant_user_idx",
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
            ("user", "The user must belong to this workspace."),
            ("org_unit", "The organizational unit must belong to this workspace."),
        ):
            if not self._relation_belongs_to_tenant(field_name):
                raise ValidationError({field_name: message})
        if self.user_id and self.pk is None and not self.user.is_active:
            raise ValidationError({"user": "A new team membership requires an active user."})

    def __str__(self):
        try:
            opportunity = self.opportunity if self.opportunity_id else None
        except ObjectDoesNotExist:
            opportunity = None
        try:
            user = self.user if self.user_id else None
        except ObjectDoesNotExist:
            user = None
        role = self.get_role_display() or "—"
        return " · ".join(
            [
                self.number or "—",
                str(opportunity) if opportunity is not None else "—",
                f"{user} ({role})" if user is not None else "—",
            ]
        )
