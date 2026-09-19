"""core — 0.8 bullets 4 and 5: PII classification and regulatory coverage.

`PiiClassification` is a DATA MAP, not a scanner. The `pii_scan` view populates it from a heuristic
pass over the app's model fields (see `apps/core/privacy.py`), and every row records whether a human
has confirmed it. That distinction is the point: a heuristic that labels `notes` as PII is a
suggestion, and a compliance report that presents suggestions as findings is worse than none.

`RegulatoryFramework` is per-tenant enablement. Its `dsar_window_days` is what makes the DSAR clock
real: when several frameworks are enabled the STRICTEST window wins, because a workspace cannot be
compliant with one regime by missing another's deadline.
"""
from django.utils import timezone

from apps.core.models._base import *  # noqa: F401,F403


class PiiClassification(models.Model):
    """One model field, classified. Rows are created by the scan and confirmed by a human."""

    CATEGORY_CHOICES = [
        ("identifier", "Identifier (name, email, phone)"),
        ("financial", "Financial"),
        ("health", "Health"),
        ("biometric", "Biometric"),
        ("location", "Location"),
        ("online", "Online identifier"),
        ("special", "Special category"),
        ("unknown", "Unclassified"),
    ]
    SENSITIVITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
    ]
    CONFIRMATION_CHOICES = [
        ("suggested", "Suggested by scan"),
        ("confirmed", "Confirmed by a human"),
        ("dismissed", "Dismissed — not PII"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="pii_classifications", db_index=True)
    #: `app_label.Model` and the field name. Kept as strings, not a ContentType FK, because this map
    #: must be able to describe fields whose model has no rows at all — a data map is about schema.
    model_label = models.CharField(max_length=120)
    field_name = models.CharField(max_length=64)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="unknown")
    sensitivity = models.CharField(max_length=10, choices=SENSITIVITY_CHOICES, default="medium")
    confirmation = models.CharField(max_length=12, choices=CONFIRMATION_CHOICES, default="suggested")
    notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                    blank=True, editable=False, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["model_label", "field_name"]
        unique_together = ("tenant", "model_label", "field_name")
        indexes = [
            models.Index(fields=["tenant", "confirmation"], name="pii_tenant_conf_idx"),
            models.Index(fields=["tenant", "sensitivity"], name="pii_tenant_sens_idx"),
        ]

    @property
    def is_confirmed(self):
        return self.confirmation == "confirmed"

    def __str__(self):
        return f"{self.model_label}.{self.field_name}"


class RegulatoryFramework(models.Model):
    """A regime this workspace claims to operate under, and the obligations it implies."""

    CODE_CHOICES = [
        ("gdpr", "GDPR (EU)"),
        ("ccpa", "CCPA / CPRA (California)"),
        ("hipaa", "HIPAA (US health)"),
        ("lgpd", "LGPD (Brazil)"),
        ("pipeda", "PIPEDA (Canada)"),
        ("other", "Other / local"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="regulatory_frameworks", db_index=True)
    code = models.CharField(max_length=20, choices=CODE_CHOICES)
    label = models.CharField(max_length=150, blank=True)
    is_enabled = models.BooleanField(default=False)
    #: The statutory response window in DAYS. GDPR Art.12(3) is one month (~30); CCPA is 45.
    dsar_window_days = models.PositiveIntegerField(
        default=30, help_text="Statutory window to answer a data-subject request, in days.")
    #: Where the data is required to stay. Recorded, NOT enforced — see the page's caveat.
    data_residency_region = models.CharField(max_length=80, blank=True)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]
        unique_together = ("tenant", "code")
        indexes = [models.Index(fields=["tenant", "is_enabled"], name="regfw_tenant_enabled_idx")]

    def __str__(self):
        return self.label or self.get_code_display()
