from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetScrapSalvage(TenantNumbered):
    """
    Asset Scrap & Salvage Record [ASCR-].
    Governs industrial machinery dismantling, metal and e-waste recycling weight recovery,
    hazardous waste abatement manifests, data sanitization, and Certificates of Destruction (CoD).
    """

    NUMBER_PREFIX = "ASCR"

    SCRAP_METHOD_CHOICES = [
        ("physical_destruction", "Physical Crushing / Destruction On-Site"),
        ("dismantling_parts_recovery", "Controlled Teardown & Spare Parts Harvesting"),
        ("shredding_recycling", "Industrial Scrap Metal Shredding"),
        ("e_waste_itad", "Certified ITAD / Electronic Scrap Refining"),
        ("hazardous_waste_abatement", "Hazardous Materials Remediation & Destruction"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft Work Order"),
        ("dismantling", "Dismantling & Sorting In Progress"),
        ("abatement_in_progress", "Hazardous Waste Abatement"),
        ("scrap_transferred", "Transferred to Recycler Yard"),
        ("certified_destroyed", "Destruction Certified (CoD on File)"),
        ("settled", "Scrap Settlement Closed"),
        ("cancelled", "Cancelled"),
    ]

    SANITIZATION_METHOD_CHOICES = [
        ("none", "Not Applicable / Non-Electronic Asset"),
        ("nist_clear", "NIST SP 800-88 Clear (Logical Overwrite)"),
        ("nist_purge", "NIST SP 800-88 Purge (Cryptographic / Degauss)"),
        ("dod_5220_wipe", "DoD 5220.22-M Multi-Pass Wipe"),
        ("physical_shredding", "Mechanical Drive Puncture / Shredding"),
        ("crypto_erase", "SED Cryptographic Erase"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "dismantling": "badge-amber",
        "abatement_in_progress": "badge-amber",
        "scrap_transferred": "badge-info",
        "certified_destroyed": "badge-green",
        "settled": "badge-green",
        "cancelled": "badge-red",
    }

    SCRAP_METHOD_CSS = {
        "physical_destruction": "badge-red",
        "dismantling_parts_recovery": "badge-info",
        "shredding_recycling": "badge-slate",
        "e_waste_itad": "badge-info",
        "hazardous_waste_abatement": "badge-amber",
    }

    SANITIZATION_METHOD_CSS = {
        "none": "badge-slate",
        "nist_clear": "badge-info",
        "nist_purge": "badge-green",
        "dod_5220_wipe": "badge-green",
        "physical_shredding": "badge-red",
        "crypto_erase": "badge-info",
    }

    disposal_request = models.ForeignKey(
        "assets.AssetDisposalRequest",
        on_delete=models.CASCADE,
        related_name="scrap_salvages",
        help_text="Parent disposal authorization request",
    )
    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.CASCADE,
        related_name="scrap_salvages",
        help_text="Fixed asset being scrapped",
    )
    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scrap_salvages",
        help_text="Operational plant machinery decommissioned",
    )
    recycler_partner = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_scrap_recyclers",
        help_text="Licensed scrap processor, metal foundry, or certified ITAD partner",
    )
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supervised_asset_scraps",
        help_text="Plant decommissioning supervisor or safety officer",
    )
    certificate_of_destruction = models.ForeignKey(
        "core.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scrap_destruction_certificates",
        help_text="Attached certified Certificate of Destruction (CoD)",
    )
    hazardous_manifest_doc = models.ForeignKey(
        "core.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scrap_hazardous_manifests",
        help_text="EPA Uniform Hazardous Waste Manifest or e-Waste consignment document",
    )

    scrap_method = models.CharField(
        max_length=32,
        choices=SCRAP_METHOD_CHOICES,
        default="dismantling_parts_recovery",
    )
    decommissioning_date = models.DateField(
        default=timezone.now,
        help_text="Date equipment decommissioning commenced",
    )
    completion_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date scrapping and metal recycling concluded",
    )

    total_scrap_weight_kg = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Gross weight of scrapped machinery in kilograms",
    )
    ferrous_weight_kg = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Recovered carbon steel / cast iron scrap weight (kg)",
    )
    non_ferrous_weight_kg = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Recovered copper, aluminum, brass, or stainless scrap weight (kg)",
    )
    e_waste_weight_kg = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Printed circuit boards, drives, and electronic scrap weight (kg)",
    )

    salvage_proceeds = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Gross settlement revenue received from scrap metal dealer",
    )
    dismantling_cost = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Contractor teardown, crane hire, rigging, or hazardous abatement fees",
    )
    net_salvage_recovery = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Net financial recovery from salvage (proceeds - dismantling cost)",
    )

    has_hazardous_materials = models.BooleanField(
        default=False,
        help_text="Flags equipment containing PCB oils, mercury switches, asbestos, lead, refrigerants, or heavy metals",
    )
    hazardous_waste_class = models.CharField(
        max_length=50,
        blank=True,
        help_text="EPA/RCRA hazardous waste classification code",
    )
    epa_manifest_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="State/federal tracking number on uniform hazardous waste manifest",
    )
    abatement_certified = models.BooleanField(
        default=False,
        help_text="Verified that environmental contaminants have been professionally mitigated",
    )
    abatement_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date environmental remediation clearance was issued",
    )

    data_sanitized = models.BooleanField(
        default=False,
        help_text="Verified that persistent media has undergone certified data wiping or physical degauss/shredding",
    )
    sanitization_method = models.CharField(
        max_length=30,
        choices=SANITIZATION_METHOD_CHOICES,
        default="none",
    )
    sanitization_verified_by = models.CharField(
        max_length=150,
        blank=True,
        help_text="Name and credentials of IT security / ITAD auditor",
    )

    cod_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Serial number printed on official Certificate of Destruction",
    )
    cod_issue_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date Certificate of Destruction was executed",
    )
    cod_issuing_agency = models.CharField(
        max_length=150,
        blank=True,
        help_text="Authorized commercial recycling partner issuing destruction certificate",
    )

    carrier_name = models.CharField(
        max_length=150,
        blank=True,
        help_text="Hauling contractor transporting scrap",
    )
    bill_of_lading_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Bill of Lading / weigh scale ticket reference",
    )
    notes = models.TextField(
        blank=True,
        help_text="Dismantling notes, recovered spare parts serials, or recycling log details",
    )

    status = models.CharField(
        max_length=24,
        choices=STATUS_CHOICES,
        default="draft",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="assets_ascr_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_ascr_ten_stat"),
            models.Index(fields=["tenant", "scrap_method"], name="idx_ascr_ten_meth"),
            models.Index(fields=["tenant", "decommissioning_date"], name="idx_ascr_ten_dcdate"),
            models.Index(fields=["tenant", "has_hazardous_materials"], name="idx_ascr_ten_haz"),
        ]

    def __str__(self):
        return f"{self.number} — {self.fixed_asset.name} ({self.get_scrap_method_display()})"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def scrap_method_css(self):
        return self.SCRAP_METHOD_CSS.get(self.scrap_method, "badge-slate")

    @property
    def sanitization_method_css(self):
        return self.SANITIZATION_METHOD_CSS.get(self.sanitization_method, "badge-slate")

    def calculate_net_recovery(self):
        """Calculates net salvage recovery."""
        self.net_salvage_recovery = (self.salvage_proceeds or Decimal("0.00")) - (
            self.dismantling_cost or Decimal("0.00")
        )
        return self.net_salvage_recovery
