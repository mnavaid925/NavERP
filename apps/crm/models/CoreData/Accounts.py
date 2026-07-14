"""CRM 1.1 Core Data Management — Accounts models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403
from apps.crm.models.CoreData.Leads import Lead


INDUSTRY_CHOICES = [
    ("technology", "Technology"),
    ("finance", "Finance & Banking"),
    ("healthcare", "Healthcare"),
    ("manufacturing", "Manufacturing"),
    ("retail", "Retail & E-commerce"),
    ("education", "Education"),
    ("real_estate", "Real Estate"),
    ("energy", "Energy & Utilities"),
    ("media", "Media & Entertainment"),
    ("professional_services", "Professional Services"),
    ("construction", "Construction"),
    ("transportation", "Transportation & Logistics"),
    ("hospitality", "Hospitality"),
    ("nonprofit", "Non-Profit"),
    ("government", "Government"),
    ("other", "Other"),
]


class AccountProfile(models.Model):
    """CRM firmographic + contact-detail extension for an organization ``core.Party``."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    party = models.OneToOneField("core.Party", on_delete=models.CASCADE, related_name="crm_account_profile")
    industry = models.CharField(max_length=40, choices=INDUSTRY_CHOICES, blank=True)
    website = models.URLField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    annual_revenue = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    employee_count = models.PositiveIntegerField(default=0)
    parent_account = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_child_account_profiles")
    address_line = models.CharField(max_length=255, blank=True)
    address_city = models.CharField(max_length=120, blank=True)
    address_state = models.CharField(max_length=120, blank=True)
    address_postal = models.CharField(max_length=20, blank=True)
    address_country = models.CharField(max_length=120, blank=True)
    source = models.CharField(max_length=20, choices=Lead.SOURCE_CHOICES, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_account_profiles")
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["party__name"]
        indexes = [
            models.Index(fields=["tenant", "industry"], name="crm_accp_tnt_industry_idx"),
            models.Index(fields=["tenant", "source"], name="crm_accp_tnt_source_idx"),
            models.Index(fields=["tenant", "parent_account"], name="crm_accp_tnt_parent_idx"),
        ]

    def __str__(self):
        return f"Account · {self.party.name}"
