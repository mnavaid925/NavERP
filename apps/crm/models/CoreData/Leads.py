"""CRM 1.1 Core Data Management — Leads models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


class Lead(TenantNumbered):
    """A potential customer (1.1). Convertible to a Party/Contact + Opportunity."""

    NUMBER_PREFIX = "LEAD"

    SOURCE_CHOICES = [
        ("web", "Web Form"),
        ("referral", "Referral"),
        ("event", "Event"),
        ("cold_call", "Cold Call"),
        ("email_campaign", "Email Campaign"),
        ("social", "Social Media"),
        ("other", "Other"),
    ]
    RATING_CHOICES = [("hot", "Hot"), ("warm", "Warm"), ("cold", "Cold")]
    STATUS_CHOICES = [
        ("new", "New"),
        ("contacted", "Contacted"),
        ("qualified", "Qualified"),
        ("unqualified", "Unqualified"),
        ("converted", "Converted"),
        ("recycled", "Recycled"),
    ]

    name = models.CharField(max_length=255)
    company = models.CharField(max_length=255, blank=True)
    title = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="web")
    rating = models.CharField(max_length=10, choices=RATING_CHOICES, default="warm")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    score = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(100)])  # 0–100 grade
    est_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_leads")
    description = models.TextField(blank=True)
    converted_party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_converted_leads")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_lead_tenant_status_idx"),
            models.Index(fields=["tenant", "created_at"], name="crm_lead_tenant_created_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.name}"
