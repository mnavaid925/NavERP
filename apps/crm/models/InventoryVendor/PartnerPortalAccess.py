"""CRM 1.12 Inventory & Vendor Management — PartnerPortalAccess models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


class PartnerPortalAccess(TenantNumbered):
    """External partner/vendor portal login mapping (1.12)."""

    NUMBER_PREFIX = "PRT"

    ACCESS_CHOICES = [
        ("read_only", "Read Only"),
        ("lead_register", "Lead Registration"),
        ("full", "Full Access"),
    ]

    partner_party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_portal_accesses")
    portal_user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_portal_access")
    access_level = models.CharField(max_length=20, choices=ACCESS_CHOICES, default="read_only")
    can_view_stock = models.BooleanField(default=False)
    can_register_leads = models.BooleanField(default=False)
    accepted_at = models.DateTimeField(null=True, blank=True)  # system-set when partner activates
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="crm_prt_tnt_active_idx"),
            models.Index(fields=["tenant", "partner_party"], name="crm_prt_tnt_partner_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.partner_party or 'Partner'}"
