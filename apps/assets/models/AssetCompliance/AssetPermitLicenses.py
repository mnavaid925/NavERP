from decimal import Decimal

from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetPermitLicense(TenantNumbered):
    """
    Asset Operating Permit & Regulatory License [APL-].
    Tracks mandatory operating permits, municipal licenses, emissions registrations,
    safety certificates, and recurring renewal deadlines for plant equipment.
    """

    NUMBER_PREFIX = "APL"

    PERMIT_TYPE_CHOICES = [
        ("environmental_emissions", "Air Quality / Emissions Permit"),
        ("safety_operating", "Plant Equipment Operating Certificate"),
        ("hazardous_material", "Hazardous Materials Storage Permit"),
        ("water_discharge", "NPDES / Industrial Wastewater Discharge"),
        ("pressure_vessel", "Boiler & Pressure Vessel Certificate"),
        ("radiation_device", "Radiation / X-Ray Source License"),
        ("municipal_zoning", "Municipal Special Operations Permit"),
        ("transportation", "DOT Hazmat Transport Certificate"),
    ]

    STATUS_CHOICES = [
        ("active", "Active & Valid"),
        ("pending_renewal", "Renewal Pending Approval"),
        ("under_review", "Under Agency Review"),
        ("expired", "Expired (Non-Compliant)"),
        ("suspended", "Suspended by Regulator"),
        ("revoked", "Revoked / Injunction"),
    ]

    STATUS_CSS = {
        "active": "badge-green",
        "pending_renewal": "badge-amber",
        "under_review": "badge-info",
        "expired": "badge-red",
        "suspended": "badge-red",
        "revoked": "badge-muted",
    }

    PERMIT_TYPE_CSS = {
        "environmental_emissions": "badge-amber",
        "safety_operating": "badge-green",
        "hazardous_material": "badge-red",
        "water_discharge": "badge-info",
        "pressure_vessel": "badge-slate",
        "radiation_device": "badge-red",
        "municipal_zoning": "badge-slate",
        "transportation": "badge-info",
    }

    tenant = models.ForeignKey(
        "core.Tenant",
        on_delete=models.CASCADE,
        related_name="permits_licenses",
    )
    permit_name = models.CharField(
        max_length=255,
        help_text="Official statutory permit or license title",
    )
    permit_number = models.CharField(
        max_length=100,
        help_text="Regulatory permit or license number issued by agency",
    )
    permit_type = models.CharField(
        max_length=30,
        choices=PERMIT_TYPE_CHOICES,
        default="safety_operating",
    )
    asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.CASCADE,
        related_name="permits_licenses",
        help_text="Permitted plant machinery or physical asset",
    )
    issuing_authority = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="issued_asset_permits",
        help_text="Permitting authority or government agency",
    )
    issue_date = models.DateField(default=timezone.now)
    effective_date = models.DateField(default=timezone.now)
    expiration_date = models.DateField(
        help_text="Statutory license expiration date",
    )
    renewal_lead_days = models.PositiveIntegerField(
        default=60,
        help_text="Advance notice lead window for renewal alert in days",
    )
    renewal_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Statutory renewal filing fee",
    )
    operating_conditions = models.TextField(
        blank=True,
        help_text="Mandated operating conditions, capacity thresholds, and monitoring limits",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
    )

    class Meta:
        ordering = ["expiration_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_apl_ten_num_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_apl_ten_stat"),
            models.Index(fields=["tenant", "permit_type"], name="idx_apl_ten_type"),
            models.Index(fields=["tenant", "expiration_date"], name="idx_apl_ten_exp"),
            models.Index(fields=["tenant", "asset"], name="idx_apl_ten_ast"),
        ]

    def __str__(self):
        return f"{self.permit_name} ({self.permit_number})"

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def permit_type_badge_class(self):
        return self.PERMIT_TYPE_CSS.get(self.permit_type, "badge-slate")

    @property
    def days_to_expiration(self):
        if self.expiration_date:
            return (self.expiration_date - timezone.now().date()).days
        return None

    @property
    def is_expiring_soon(self):
        days = self.days_to_expiration
        if days is not None and self.status == "active":
            return 0 <= days <= self.renewal_lead_days
        return False

    @property
    def is_expired(self):
        if self.status == "expired":
            return True
        days = self.days_to_expiration
        return days is not None and days < 0

