"""CRM 1.1 Core Data Management — Contacts models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403
from apps.crm.models.CoreData.Leads import Lead


class ContactProfile(models.Model):
    """CRM contact-detail extension for a person ``core.Party`` (job, phone, address, employer)."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    party = models.OneToOneField("core.Party", on_delete=models.CASCADE, related_name="crm_contact_profile")
    job_title = models.CharField(max_length=120, blank=True)
    department = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    mobile = models.CharField(max_length=40, blank=True)
    account = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_account_contacts")
    address_line = models.CharField(max_length=255, blank=True)
    address_city = models.CharField(max_length=120, blank=True)
    address_state = models.CharField(max_length=120, blank=True)
    address_postal = models.CharField(max_length=20, blank=True)
    address_country = models.CharField(max_length=120, blank=True)
    linkedin = models.URLField(blank=True)
    source = models.CharField(max_length=20, choices=Lead.SOURCE_CHOICES, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_contact_profiles")
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["party__name"]
        indexes = [
            models.Index(fields=["tenant", "source"], name="crm_conp_tnt_source_idx"),
            models.Index(fields=["tenant", "account"], name="crm_conp_tnt_account_idx"),
        ]

    def __str__(self):
        return f"Contact · {self.party.name}"
