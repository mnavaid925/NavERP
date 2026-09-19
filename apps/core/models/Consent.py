"""core — 0.8 bullet 1: Consent & Preference Management.

`ConsentPurpose` is tenant-defined rather than a closed CHOICES list, because a lawful purpose is a
fact about the business, not about the software — a fixed list would force every workspace into one
company's legal analysis.

`ConsentRecord` is an append-only-ish log keyed on `core.Party` (the unified subject spine, L28):
one row per grant, and a withdrawal ADDS a row rather than editing the grant. Consent history is the
evidence — overwriting it would destroy the only proof of what was agreed and when.
"""
import datetime

from django.utils import timezone

from apps.core.models._base import *  # noqa: F401,F403


class ConsentPurpose(models.Model):
    """A tenant-defined lawful purpose for processing (e.g. 'Marketing email', 'Product analytics')."""

    LAWFUL_BASIS_CHOICES = [
        ("consent", "Consent"),
        ("contract", "Contract"),
        ("legal_obligation", "Legal obligation"),
        ("vital_interest", "Vital interest"),
        ("public_task", "Public task"),
        ("legitimate_interest", "Legitimate interest"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="consent_purposes", db_index=True)
    name = models.CharField(max_length=150)
    code = models.SlugField(max_length=60)
    lawful_basis = models.CharField(max_length=24, choices=LAWFUL_BASIS_CHOICES, default="consent")
    #: Only a `consent`-basis purpose is opt-outable. The others are not optional in law, so offering
    #: a toggle for them would be a lie the UI tells.
    is_optional = models.BooleanField(
        default=True, help_text="Only meaningful when the lawful basis is Consent.")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "code")
        indexes = [models.Index(fields=["tenant", "is_active"], name="cpurp_tenant_active_idx")]

    def __str__(self):
        return self.name


class ConsentRecord(models.Model):
    """One consent EVENT: a grant or a withdrawal. Never edited, never overwritten."""

    ACTION_CHOICES = [("granted", "Granted"), ("withdrawn", "Withdrawn")]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="consent_records", db_index=True)
    party = models.ForeignKey("core.Party", on_delete=models.CASCADE,
                              related_name="consent_records", db_index=True)
    purpose = models.ForeignKey("core.ConsentPurpose", on_delete=models.PROTECT,
                                related_name="records")
    action = models.CharField(max_length=12, choices=ACTION_CHOICES, default="granted")
    #: How the consent was captured. Free text plus a closed `source` kind: the channel matters for
    #: proving consent was freely given, and a closed list keeps it reportable.
    SOURCE_CHOICES = [
        ("web_form", "Web form"),
        ("email", "Email"),
        ("phone", "Phone"),
        ("in_person", "In person"),
        ("imported", "Imported"),
        ("api", "API"),
    ]
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="web_form")
    #: Where the proof lives (a form submission id, a ticket, a signed PDF). Consent that cannot be
    #: evidenced is not consent, so the field exists even when it is left blank.
    evidence = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="+")
    occurred_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at", "-id"]
        indexes = [
            models.Index(fields=["tenant", "party", "-occurred_at"], name="crec_tenant_party_idx"),
            models.Index(fields=["tenant", "purpose", "action"], name="crec_tenant_purpose_idx"),
        ]

    def __str__(self):
        return f"{self.party} · {self.purpose} · {self.get_action_display()}"


def current_consent(tenant, party, purpose):
    """The EFFECTIVE consent state: the latest event wins.

    Derived rather than stored. A `has_consent` boolean on Party would be a second source of truth
    that a withdrawal could fail to update; reading the last event cannot drift.
    Returns "granted" | "withdrawn" | None (never asked).
    """
    latest = (ConsentRecord.objects
              .filter(tenant=tenant, party=party, purpose=purpose)
              .order_by("-occurred_at", "-id")
              .first())
    if latest is None:
        return None
    if latest.expires_at is not None and latest.expires_at <= timezone.now():
        return None  # an expired grant is not a grant
    return latest.action
