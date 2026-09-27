"""tenants — LicenseAssignment (0.19 "License & Subscription Administration", bullet 1).

ONE SEAT, HELD BY ONE PERSON, FOR ONE MODULE.

A row here is a commercial term somebody wrote down, not a control that ran. A seat is a register
entry: it records who holds what. Reclaiming a seat does NOT disable anybody's login — seat
auto-deprovisioning is decline #3 of the ten, because there is no identity sync in NavERP.

`status`, `reclaimed_on` and `reclaim_reason` are all OFF the form and written by exactly one piece
of code, the `licenseassignment_reclaim` verb. A form carrying `status` would let a member
`POST status=active` and silently re-activate a revoked or reclaimed seat, undoing the one-writer
discipline (L22) the verb exists to establish. "Expired" is a DISPLAYED state derived from
`expires_on` by `is_expired`; nothing ever writes `status="expired"`.

**SEAT, not LIC — [RULING] 1.** `LIC` is `scm.TradeLicense`'s internal number
(`apps/scm/models/ContractCompliance/TradeLicenses.py:55`), and two registers must not mint the same
customer-facing number in one tenant. `core.NumberingScheme` has `unique_together = ("tenant",
"prefix")`, so a tenant could not even configure both, and the 0.10 numbering board would read as one
prefix serving two unrelated document kinds.

`assignment_source` is VOCABULARY SOMEBODY RECORDS BY HAND. Nothing in NavERP chooses it
automatically — there is no directory sync, no group engine, no rule evaluator — so `"direct"` is the
only value a view or the seeder may ever write; `group` and `rule` exist so an operator can say where
a seat came from. This is the `IpAccessRule.source` 0.18 precedent: a source field nobody sets is
fine, a source field silently set by nothing is a lie about provenance.

**Ownership:** 0.19 owns the COMMERCIAL seat count only. The abuse bound is `core.IpAccessRule` (0.18)
and operational thresholds are `core.AlertRule` (0.17); neither is re-declared here.

**The same TEN declines as the rest of 0.19:** entitlement enforcement · quota enforcement/throttling ·
seat auto-deprovisioning (the one this file is most tempted by) · metered event ingestion · proration ·
prepaid credit grants · rate cards / tiered / multi-currency pricing · plan versioning &
grandfathering · automatic renewal execution · expiry email delivery.
"""
from django.core.exceptions import ValidationError

from apps.tenants.models._base import *  # noqa: F401,F403


class LicenseAssignment(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("reclaimed", "Reclaimed"),
        ("revoked", "Revoked"),
        ("expired", "Expired"),
    ]
    SOURCE_CHOICES = [
        ("direct", "Direct"),
        ("group", "Group"),
        ("rule", "Rule"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="license_assignments", db_index=True)
    #: SEAT-#####, NOT LIC-##### — see the module docstring ([RULING] 1]).
    number = models.CharField(max_length=20, editable=False)
    #: NOT nullable: a seat with no holder is not a seat. Note `accounts.User.tenant` is NULLABLE
    #: (the superuser `admin` has tenant=None by design), so the list filter, the board count and the
    #: seeder all narrow to `user__tenant=request.tenant` themselves.
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE,
                             related_name="license_assignments")
    #: A CHAR, not an FK: no module master exists in this repo. `max_length=40` matches the verified
    #: `core.ModuleAccessScope.module_slug` exactly so the two registries read consistently. Blank
    #: ("") means a tenant-wide seat — a VALUE here, never NULL, so two tenant-wide seats for one
    #: user collide correctly.
    module_slug = models.CharField(max_length=40, blank=True)
    #: Off the form ([RULING] 5). Sole writer: the `licenseassignment_reclaim` verb.
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="active")
    assignment_source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default="direct")
    assigned_from = models.DateField(null=True, blank=True)
    #: Drives the DISPLAYED expired state, never a stored status.
    expires_on = models.DateField(null=True, blank=True)
    #: Evidence stamps — `editable=False`, written only by the verb (L22).
    reclaimed_on = models.DateTimeField(null=True, blank=True, editable=False)
    reclaim_reason = models.CharField(max_length=200, blank=True, editable=False)
    #: The BILLING link, and deliberately NOT part of seat identity — `SET_NULL` so deleting a
    #: subscription does not delete a person's seat history.
    subscription = models.ForeignKey("tenants.Subscription", on_delete=models.SET_NULL, null=True,
                                     blank=True, related_name="license_assignments")
    #: Free text an operator writes about THIS seat. Distinct from `reclaim_reason`, which is the
    #: verb's evidence of a particular act. The other three 0.19 models all carry a `notes` column and
    #: the research + plan both list it here; contract §1.4 dropped it only to keep a "4 x 12 = 48"
    #: count tidy, which is not a schema reason. [RULING] 11.
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-assigned_from", "-id"]
        # Three members, not four: `subscription` is nullable, so including it would make the
        # constraint inert (NULLs are distinct) — and it is the billing link, not seat identity.
        # Seat identity is "this user holds this module's seat in this workspace, once".
        unique_together = (("tenant", "user", "module_slug"),)
        indexes = [
            models.Index(fields=["tenant", "status"], name="licassign_tenant_status_idx"),
            models.Index(fields=["tenant", "user"], name="licassign_user_idx"),
            models.Index(fields=["tenant", "subscription"], name="licassign_sub_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.number:
            return super().save(*args, **kwargs)
        # Assign SEAT-#####; retry on the rare concurrent-collision (unique_together).
        for _ in range(5):
            self.number = next_number(LicenseAssignment, self.tenant, "SEAT")
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                self.number = ""
        return super().save(*args, **kwargs)

    def clean(self):
        """One rule: the [RULING] 8 duplicate guard on the unique tuple.

        Reachable by an ordinary user, because both `user` and `module_slug` are on the form.
        """
        super().clean()
        if self.tenant_id and self.user_id:
            # `module_slug` is normalised to "" here so a form that posts None (or omits the key) is
            # compared as the same tenant-wide value the unique_together stores.
            slug = self.module_slug or ""
            clash = LicenseAssignment.objects.filter(
                tenant_id=self.tenant_id, user_id=self.user_id, module_slug=slug,
            ).exclude(pk=self.pk)
            if clash.exists():
                raise ValidationError({
                    "module_slug": "That person already holds a seat here. Edit the existing seat "
                                    "instead of creating a second one.",
                })

    # --------------------------------------------------------------- derived (never stored)
    @property
    def is_reclaimable(self):
        """A per-row fact, so a @property is correct and cheap ([RULING] 4).

        The seat COUNT is deliberately NOT a property: a count is a queryset aggregate, and a
        per-row `.count()` re-queries on every render. It is computed in the view, off one grouped
        query, and passed as a context key.
        """
        return self.status == "active"

    @property
    def is_expired(self):
        """A DISPLAYED state. Nothing ever writes `status="expired"` ([RULING] 5)."""
        return bool(self.expires_on and self.expires_on < timezone.localdate())

    def __str__(self):
        return f"{self.user} · {self.module_slug or 'all modules'} ({self.get_status_display()})"

