"""tenants — LicenseAssignment form (0.19, the seat register)."""
from django.core.exceptions import ValidationError

from apps.tenants.forms._common import *  # noqa: F401,F403
from apps.tenants.models import (
    LicenseAssignment,
)


class LicenseAssignmentForm(TenantModelForm):
    """`TenantModelForm`, never a plain `ModelForm` ([RULING] 9) — see the 0.19 contract.

    Excluded, with the reason for each:
      * `status` — the SOLE writer is the `licenseassignment_reclaim` verb ([RULING] 5). A form
        carrying it would let a member `POST status=active` and silently re-activate a revoked or
        reclaimed seat. A seat is created `active` (the model default) and its status changes ONLY
        through the verb. "Expired" is a DISPLAYED state derived from `expires_on`, never a stored
        status a form can write.
      * `reclaimed_on` — evidence stamp, `editable=False`, written only by the verb. L22: no system
        stamp is user-editable.
      * `reclaim_reason` — the reason belongs to the ACT of reclamation, which is the verb. A
        free-text reason typed into a form is a claim, not a record.
      * `number` — `editable=False`, minted in `save()`.
      * `tenant` — set by the view.
    """

    class Meta:
        model = LicenseAssignment
        # `notes` IS on this form ([RULING] 11). Contract §1.4's field table omitted the column while
        # §2.4 and §3.5 both named it — a contract-internal contradiction, since a ModelForm naming an
        # undeclared field raises `FieldError: Unknown field(s)` at class-definition time. The research
        # and the plan both list `notes`, and the other three 0.19 models all carry one, so the MODEL
        # was the thing that was wrong and the column was added. This list is now contract §2.4 as
        # written.
        fields = ["user", "module_slug", "assignment_source", "assigned_from", "expires_on",
                  "subscription", "notes"]

    def clean(self):
        """The [RULING] 8 duplicate guard on `(tenant, user, module_slug)`.

        Fully non-nullable, so the database enforces it and a duplicate POST would otherwise be a
        500. It is reachable by an ordinary user because both `user` and `module_slug` are on this
        form. A blank `module_slug` is the tenant-wide seat and normalises to `""`, never NULL, so
        two tenant-wide seats for one user collide correctly.
        """
        super().clean()
        user = self.cleaned_data.get("user")
        tenant = getattr(self, "tenant", None)
        if user is None or tenant is None:
            return self.cleaned_data
        slug = self.cleaned_data.get("module_slug") or ""
        clash = LicenseAssignment.objects.filter(tenant=tenant, user=user, module_slug=slug)
        if self.instance and self.instance.pk:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise ValidationError({
                "module_slug": "That person already holds a seat here. Edit the existing seat "
                                "instead of creating a second one.",
            })
        return self.cleaned_data
