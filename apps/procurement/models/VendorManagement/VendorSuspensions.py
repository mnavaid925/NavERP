"""Procurement 6.4 Vendor Management — VendorSuspension (the blacklist/suspension register).

**Vendor Management** bullet: "Workflow to block non-compliant or underperforming suppliers
from receiving POs." ``scm.SupplierProfile`` carries only a one-click ``suspended``
onboarding STATUS flag — no register, no documented reason, no decision trail, no lift
record. THIS register adds the governance layer AROUND that flag: a request -> decide ->
lift lifecycle where every block is its own numbered row with who asked, why, which PO
triggered it, who decided it and when, and a mandatory reason on the way back out.

L36: we extend, never re-declare, the scm master — the vendor is a ``core.Party`` and the
evidence link is an ``scm.PurchaseOrder``; both stay owned where they were born.

**Enforcement today is at the portal gate only.** ``blocking_for`` refuses invoice
submissions for a blocked supplier; the PO-side hook ("block from receiving new POs")
would have to live inside scm's PurchaseOrder flow, which this app may not edit — that
integration stays deferred, and the register's banner copy says "flagged", promising
nothing the code does not do.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.procurement.models._base import *  # noqa: F401,F403


class VendorSuspension(TenantNumbered):
    """One suspension/blacklist case against a vendor — requested, decided, liftable."""

    NUMBER_PREFIX = "VSU"

    KIND_CHOICES = [("suspension", "Suspension"), ("blacklist", "Blacklist")]
    REASON_CHOICES = [
        ("quality", "Quality failure"),
        ("delivery", "Delivery failure"),
        ("compliance", "Compliance breach"),
        ("financial", "Financial risk"),
        ("other", "Other"),
    ]
    STATUS_CHOICES = [
        ("requested", "Requested"),
        ("active", "In force"),
        ("rejected", "Rejected"),
        ("lifted", "Lifted"),
    ]

    supplier = models.ForeignKey(
        "core.Party", on_delete=models.PROTECT, related_name="procurement_suspensions",
        help_text="The vendor being blocked")
    kind = models.CharField(max_length=16, choices=KIND_CHOICES, default="suspension",
                            help_text="Blacklists are normally open-ended; suspensions carry an end date")
    reason_category = models.CharField(max_length=16, choices=REASON_CHOICES, default="other")
    reason = models.TextField(help_text="The documented case for the block")
    po_reference = models.ForeignKey(
        "scm.PurchaseOrder", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_suspensions",
        help_text="Optional evidence link — the order that triggered it")
    starts_on = models.DateField(default=timezone.localdate)
    ends_on = models.DateField(
        null=True, blank=True,
        help_text="Suspensions expire automatically after; blank = until lifted "
                  "(blacklists normally open-ended)")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="requested")
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_suspensions_requested", editable=False)
    decision_note = models.TextField(blank=True, help_text="Approve/reject note")
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_suspensions_decided", editable=False)
    decided_at = models.DateTimeField(null=True, blank=True, editable=False)
    lifted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_suspensions_lifted", editable=False)
    lifted_at = models.DateTimeField(null=True, blank=True, editable=False)
    lift_note = models.TextField(blank=True, help_text="Why the block was lifted")

    class Meta:
        ordering = ["-created_at"]
        unique_together = (("tenant", "number"),)
        indexes = [
            models.Index(fields=["tenant", "status"], name="prc_vsu_tnt_status_idx"),
            models.Index(fields=["tenant", "supplier"], name="prc_vsu_tnt_supp_idx"),
        ]

    def __str__(self):
        return f"{self.number} {self.supplier} ({self.get_status_display()})"

    # -- derived ------------------------------------------------------------------------------------

    @property
    def is_blocking(self):
        return self.status == "active"

    @property
    def is_expired(self):
        return self.ends_on is not None and self.ends_on < timezone.localdate()

    @property
    def is_current(self):
        return self.is_blocking and not self.is_expired

    # -- resolution ----------------------------------------------------------------------------------

    @classmethod
    def blocking_for(cls, tenant, supplier_id, today=None):
        """The register row currently blocking this supplier, or None.

        Used by the portal to refuse invoice submissions while blocked. Only an ACTIVE,
        UNEXPIRED entry answers — a suspension whose ``ends_on`` has passed no longer
        blocks anything (the register keeps the row and its history; expiry is read here,
        not flipped by a background job). Among several active rows the most recently
        decided wins.
        """
        today = today or timezone.localdate()
        return (cls.objects
                .filter(tenant=tenant, supplier_id=supplier_id, status="active")
                .filter(Q(ends_on__isnull=True) | Q(ends_on__gte=today))
                .order_by("-decided_at", "-id").first())

    # -- hygiene --------------------------------------------------------------------------------------

    def clean(self):
        super().clean()
        errors = {}
        if self.starts_on and self.ends_on and self.ends_on < self.starts_on:
            errors["ends_on"] = "Ends before it starts."
        # _id guards, NOT bare getattr: with the FK unset, getattr(self, "supplier") raises
        # RelatedObjectDoesNotExist — which is exactly the state a ModelForm leaves when a
        # rejected FK field clears to None — and two-arg getattr does NOT swallow it (only
        # the three-arg form catches AttributeError). This crash WAS a live 500 on
        # /suspensions/add/ until the ids came in.
        if self.supplier_id and self.supplier.tenant_id != self.tenant_id:
            errors["supplier"] = "That record belongs to another workspace."
        if (self.po_reference_id
                and self.po_reference.tenant_id != self.tenant_id):
            errors["po_reference"] = "That record belongs to another workspace."
        if errors:
            raise ValidationError(errors)
