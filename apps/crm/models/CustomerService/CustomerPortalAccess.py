"""CRM 1.4 Customer Service & Support — CustomerPortalAccess models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


class CustomerPortalAccess(TenantNumbered):
    """Customer self-service portal login mapping (1.4). Mirrors ``PartnerPortalAccess`` (1.12):
    a ``portal_user`` is bound to a ``customer_party`` and only ever sees that party's cases."""

    NUMBER_PREFIX = "CSP"

    customer_party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_customer_portal_accesses")
    portal_user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_customer_portal_access")
    can_submit_cases = models.BooleanField(default=True)
    accepted_at = models.DateTimeField(null=True, blank=True)  # system-set when the customer activates
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="crm_csp_tnt_active_idx"),
            models.Index(fields=["tenant", "customer_party"], name="crm_csp_tnt_party_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.customer_party or 'Customer'}"
