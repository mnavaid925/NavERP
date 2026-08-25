"""Procurement 6.3 Approval Workflow Engine — Delegation of Authority.

**Delegation of Authority (DOA)** bullet: "Ability for approvers to temporarily
reassign approval rights to a delegate." A delegation is a dated GRANT: while it is
active, decisions the delegate makes on the delegator's behalf are stamped
``via_delegation`` on the resulting RequisitionApproval row — so the history shows
both who signed AND whose authority they signed under, which is the whole point of
a DOA register.

Grants are tenant-admin managed config (consistent with every other rule table in
this app), scoped optionally to one department, and soft-deactivatable so a recalled
grant keeps its place in history instead of vanishing under an audited signature.
"""
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.procurement.models._base import *  # noqa: F401,F403

#: How long a fresh grant defaults to run — a quarter, the common review cadence.
DEFAULT_WINDOW_DAYS = 90


class ApprovalDelegation(TenantOwned):
    """One temporary reassignment of approval authority."""

    delegator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_doa_given",
        help_text="The approver stepping aside")
    delegate = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_doa_received",
        help_text="The approver covering for them")
    scope_org_unit = models.ForeignKey(
        "core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_delegations",
        help_text="Restrict the grant to one department; blank covers them all")
    valid_from = models.DateField(default=timezone.localdate)
    valid_until = models.DateField(
        help_text="Last day the grant holds — authority reverts automatically after")
    reason = models.CharField(max_length=255, blank=True,
                              help_text="e.g. annual leave cover")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-valid_from", "-id"]
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="prc_del_tnt_active_idx"),
        ]

    def __str__(self):
        return (f"{self.delegator or '?'} → {self.delegate or '?'} "
                f"({self.valid_from:%Y-%m-%d} → {self.valid_until:%Y-%m-%d})")

    @property
    def is_current(self):
        today = timezone.localdate()
        return self.is_active and self.valid_from <= today <= self.valid_until

    # -- resolution --------------------------------------------------------------------------------

    @classmethod
    def active_for(cls, tenant, user, org_unit_id=None, today=None):
        """The grant currently giving ``user`` delegated authority, or None.

        Authority flows delegator -> delegate: this answers "is ``user`` covering
        for someone right now", which is the question the deciding view asks before
        stamping ``via_delegation``. A department-scoped grant beats an unscoped
        one; among equals the newest window wins. An inactive/expired/early grant
        never answers, and a department-scoped grant does NOT cover requests
        outside its department.
        """
        today = today or timezone.localdate()
        base = (cls.objects.filter(tenant=tenant, is_active=True, delegate=user,
                                   valid_from__lte=today, valid_until__gte=today)
                .order_by("-valid_from", "-id"))
        if org_unit_id:
            exact = base.filter(scope_org_unit_id=org_unit_id).first()
            if exact is not None:
                return exact
            return base.filter(scope_org_unit__isnull=True).first()
        return base.filter(scope_org_unit__isnull=True).first()

    # -- hygiene -----------------------------------------------------------------------------------

    def clean(self):
        super().clean()
        errors = {}
        if (self.valid_from and self.valid_until
                and self.valid_until < self.valid_from):
            errors["valid_until"] = "Ends before it starts."
        if self.delegator_id and self.delegate_id and self.delegator_id == self.delegate_id:
            errors["delegate"] = "An approver cannot delegate to themselves."
        for name in ("delegator", "delegate"):
            user = getattr(self, name)
            if user is not None and user.tenant_id != self.tenant_id:
                errors[name] = "That record belongs to another workspace."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.pk and not self.valid_until:
            self.valid_until = timezone.localdate() + timedelta(days=DEFAULT_WINDOW_DAYS)
        super().save(*args, **kwargs)
