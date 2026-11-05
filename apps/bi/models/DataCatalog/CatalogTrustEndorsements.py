from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class CatalogTrustEndorsement(TenantNumbered):
    NUMBER_PREFIX = "BTRU"

    ENDORSEMENT_TYPE_CHOICES = [
        ("formal_certification", "Formal Data Steward Certification"),
        ("peer_endorsement", "Peer Data Practitioner Endorsement"),
        ("user_rating", "Community User Review & Rating"),
        ("deprecation_notice", "Deprecation Notice & Decommission Warning"),
        ("steward_attestation", "Periodic Stewardship Attestation"),
        ("audit_clearance", "Internal Audit Compliance Clearance"),
    ]

    VERDICT_CHOICES = [
        ("approved_certified", "Approved & Certified Production-Ready"),
        ("conditionally_approved", "Conditionally Approved (Minor Caveats)"),
        ("recommended", "Recommended Best-Practice Asset"),
        ("deprecated_scheduled_retirement", "Deprecated - Scheduled for Retirement"),
        ("rejected_unfit_for_use", "Rejected - Unfit for Enterprise Decision-Making"),
    ]

    asset = models.ForeignKey(
        "bi.CatalogAsset",
        on_delete=models.CASCADE,
        related_name="endorsements",
        help_text="Catalog asset being evaluated or endorsed",
    )
    endorsement_type = models.CharField(
        max_length=30,
        choices=ENDORSEMENT_TYPE_CHOICES,
        default="formal_certification",
    )
    verdict = models.CharField(
        max_length=35,
        choices=VERDICT_CHOICES,
        default="approved_certified",
    )
    rating_value = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Optional numerical rating: 1 to 5 stars",
    )
    attested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="catalog_endorsements",
        help_text="User, steward, or auditor submitting the attestation",
    )
    attested_at = models.DateTimeField(auto_now_add=True)
    valid_until = models.DateField(
        null=True,
        blank=True,
        help_text="Certification validity expiration date (triggering re-attestation)",
    )
    criteria_checklist_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="Checklist: {schema_documented: bool, quality_sla_passed: bool, ownership_verified: bool, lineage_complete: bool}",
    )
    review_comments = models.TextField(
        blank=True,
        help_text="Detailed feedback, validation notes, or deprecation explanation",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "bi_catalog_trust_endorsement"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_btru_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "asset"], name="idx_btru_ten_asset"),
            models.Index(fields=["tenant", "endorsement_type"], name="idx_btru_ten_etype"),
            models.Index(fields=["tenant", "verdict"], name="idx_btru_ten_verdict"),
            models.Index(fields=["tenant", "is_active"], name="idx_btru_ten_active"),
            models.Index(fields=["tenant", "-created_at"], name="idx_btru_ten_created"),
            models.Index(fields=["tenant", "-attested_at"], name="idx_btru_ten_attested"),
        ]

    def __str__(self):
        asset_label = self.asset.name if "asset" in self._state.fields_cache else f"Asset #{self.asset_id}"
        return f"{self.number} ({asset_label} - {self.get_verdict_display()})"

    def get_absolute_url(self):
        return reverse("bi:catalog_trust_endorsement_detail", kwargs={"pk": self.pk})
