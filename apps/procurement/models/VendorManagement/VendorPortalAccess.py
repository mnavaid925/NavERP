"""Procurement 6.4 Vendor Management — VendorPortalAccess (VPA-).

**Vendor Management** bullet: "A self-service portal for suppliers to view POs,
acknowledge orders, submit invoices, and track payments." Every gated page behind
that promise starts from the same question: WHICH supplier is this login? That
answer is not a property of a user nor of an order — it is a binding between one
login user and one supplier Party, and procurement owns the vendor relationship,
so the binding lives HERE as a staff-managed console row.

The shape mirrors ``apps/crm/models/CustomerService/CustomerPortalAccess.py``:
``portal_user`` is a OneToOne so one login can hold only ONE vendor binding — two
supplier identities behind a single login would make "whose data am I looking at"
unanswerable — while several logins MAY bind to the same supplier company on purpose
(AP clerk + buyer at the same vendor both need the portal). ``supplier`` is SET_NULL so
deleting a Party archives the binding instead of cascading it away. scm's PurchaseOrder
comment (L65-67) explicitly deferred a vendor login ("there is no vendor login in
this pass") — this model is that deferred login's access row.
"""
from django.conf import settings

from apps.procurement.models._base import *  # noqa: F401,F403


class VendorPortalAccess(TenantNumbered):
    """One supplier-portal login binding: user ↔ supplier Party."""

    NUMBER_PREFIX = "VPA"

    supplier = models.ForeignKey(
        "core.Party", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_portal_accesses",
        help_text="The company whose POs/invoices this login may see")
    portal_user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_vendor_portal_access",
        help_text="The ONE login bound to this supplier identity")
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_vendor_invitations", editable=False,
        help_text="Which staff member issued this access")
    is_active = models.BooleanField(default=True,
                                    help_text="Switch off instead of delete")
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = (("tenant", "number"),)
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="prc_vpa_tnt_active_idx"),
            models.Index(fields=["tenant", "supplier"], name="prc_vpa_tnt_supp_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.supplier or 'Unlinked'}"

    # -- resolution --------------------------------------------------------------------------------

    @classmethod
    def for_user(cls, tenant, user):
        """The active access row binding ``user`` to its supplier in ``tenant``, or None.

        The single lookup every gated portal page makes first: no row, no view.
        """
        return (cls.objects
                .filter(tenant=tenant, portal_user=user, is_active=True)
                .select_related("supplier")
                .first())
