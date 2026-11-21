from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class WasteDisposalManifest(TenantNumbered):
    NUMBER_PREFIX = "QWST"

    MANIFEST_TYPE_CHOICES = [
        ("hazardous_chemical", "RCRA Hazardous Chemical Waste"),
        ("universal_waste", "Universal Waste (Batteries / Lamps / Mercury)"),
        ("biohazard_infectious", "Biohazardous / Medical Infectious Waste"),
        ("radioactive", "Radioactive / Low-Level Waste"),
        ("non_hazardous_industrial", "Non-Hazardous Regulated Industrial Waste"),
        ("electronic_weee", "Electronic Waste (WEEE / RoHS Regulated)"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft In Preparation"),
        ("scheduled", "Scheduled for Transport Pickup"),
        ("in_transit", "In Transit to TSDF"),
        ("received_by_tsdf", "Received at TSDF Facility"),
        ("certified_disposed", "Final Destruction Certified"),
        ("discrepancy_flagged", "TSDF Discrepancy Flagged"),
    ]

    PHYSICAL_STATE_CHOICES = [
        ("liquid", "Liquid"),
        ("solid", "Solid"),
        ("sludge", "Sludge / Semi-Solid"),
        ("gas_cylinder", "Compressed Gas Cylinder"),
    ]

    CONTAINER_TYPE_CHOICES = [
        ("drum_55gal", "55-Gallon Steel / Poly Drum (DM)"),
        ("tote_ibc", "275/330-Gallon IBC Tote (TT)"),
        ("cylinder", "Cylinder / Pressure Vessel (CY)"),
        ("box_fiberboard", "Fiberboard Box / Gaylord (BA)"),
        ("tank_bulk", "Bulk Tanker / Tank Truck (TK)"),
        ("roll_off", "Roll-Off Box / Dumpster (RO)"),
    ]

    QUANTITY_UOM_CHOICES = [
        ("pounds", "Pounds (P)"),
        ("kilograms", "Kilograms (K)"),
        ("gallons", "Gallons (G)"),
        ("liters", "Liters (L)"),
        ("tons", "Tons (T)"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "scheduled": "badge-info",
        "in_transit": "badge-amber",
        "received_by_tsdf": "badge-info",
        "certified_disposed": "badge-green",
        "discrepancy_flagged": "badge-red",
    }

    MANIFEST_TYPE_CSS = {
        "hazardous_chemical": "badge-red",
        "universal_waste": "badge-amber",
        "biohazard_infectious": "badge-red",
        "radioactive": "badge-red",
        "non_hazardous_industrial": "badge-slate",
        "electronic_weee": "badge-info",
    }

    manifest_title = models.CharField(max_length=255, help_text="Waste shipment title e.g. Q4 Spent Solvent and Debris")
    regulatory_manifest_id = models.CharField(max_length=100, db_index=True, help_text="Official tracking # e.g. EPA Form 8700-22 Manifest #")
    manifest_type = models.CharField(max_length=35, choices=MANIFEST_TYPE_CHOICES, default="hazardous_chemical", db_index=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="draft", db_index=True)

    generator_org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="waste_manifests",
        help_text="Generator site / facility",
    )
    generator_epa_id = models.CharField(max_length=50, blank=True, help_text="EPA Identification number of generator site")
    accumulation_start_date = models.DateField(db_index=True, default=timezone.now, help_text="Date hazardous waste accumulation commenced")

    waste_description = models.TextField(help_text="Proper DOT Shipping Name, Hazard Class, and Waste Description")
    epa_waste_codes = models.CharField(max_length=255, blank=True, help_text="Applicable EPA waste codes e.g. D001, F003, U002")
    associated_hazardous_material = models.ForeignKey(
        "quality.HazardousMaterial",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="waste_manifests",
        help_text="Linked originating chemical from inventory",
    )

    physical_state = models.CharField(max_length=25, choices=PHYSICAL_STATE_CHOICES, default="liquid", db_index=True)
    is_ignitable = models.BooleanField(default=False, help_text="RCRA Characteristic D001 Ignitable")
    is_corrosive = models.BooleanField(default=False, help_text="RCRA Characteristic D002 Corrosive")
    is_reactive = models.BooleanField(default=False, help_text="RCRA Characteristic D003 Reactive")
    is_toxic = models.BooleanField(default=False, help_text="RCRA Characteristic D004-D043 Toxicity")

    container_type = models.CharField(max_length=25, choices=CONTAINER_TYPE_CHOICES, default="drum_55gal", db_index=True)
    container_count = models.PositiveIntegerField(default=1, help_text="Number of individual containers/drums")
    quantity_value = models.DecimalField(max_digits=12, decimal_places=2, help_text="Net weight or volume of waste")
    quantity_uom = models.CharField(max_length=20, choices=QUANTITY_UOM_CHOICES, default="pounds", db_index=True)

    transporter = models.ForeignKey(
        "core.Party",
        on_delete=models.PROTECT,
        related_name="transported_waste_manifests",
        help_text="EPA licensed hazardous waste transporter (core.Party)",
    )
    transporter_epa_id = models.CharField(max_length=50, blank=True, help_text="Transporter EPA ID number")

    tsdf_facility = models.ForeignKey(
        "core.Party",
        on_delete=models.PROTECT,
        related_name="received_waste_manifests",
        help_text="Designated Treatment, Storage, & Disposal Facility (core.Party)",
    )
    tsdf_epa_id = models.CharField(max_length=50, blank=True, help_text="Designated TSDF EPA ID number")

    shipment_date = models.DateField(null=True, blank=True, db_index=True, help_text="Date waste left generator facility")
    tsdf_receipt_date = models.DateField(null=True, blank=True, help_text="Date received and confirmed by TSDF facility")
    management_method_code = models.CharField(max_length=50, blank=True, help_text="Disposal method code e.g. H040 Incineration, H020 Solvent Recovery")
    certificate_of_disposal_number = models.CharField(max_length=100, blank=True, help_text="TSDF Certificate of Destruction / Disposal reference number")
    certificate_received_date = models.DateField(null=True, blank=True, help_text="Date final destruction certificate was received")
    discrepancy_details = models.TextField(blank=True, help_text="Documented TSDF receipt discrepancies in weight, container count, or type")

    certifying_officer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="certified_waste_manifests",
        help_text="Authorized Generator Representative signing manifest",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-shipment_date", "-accumulation_start_date", "-created_at"]
        verbose_name = "Waste Disposal Manifest"
        verbose_name_plural = "Waste Disposal Manifests"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qwst_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qwst_ten_status"),
            models.Index(fields=["tenant", "manifest_type"], name="idx_qwst_ten_type"),
            models.Index(fields=["tenant", "shipment_date"], name="idx_qwst_ten_ship_dt"),
            models.Index(fields=["tenant", "accumulation_start_date"], name="idx_qwst_ten_acc_dt"),
            models.Index(fields=["tenant", "generator_org_unit"], name="idx_qwst_ten_gen_org"),
            models.Index(fields=["tenant", "transporter"], name="idx_qwst_ten_transp"),
            models.Index(fields=["tenant", "tsdf_facility"], name="idx_qwst_ten_tsdf"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qwst_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} — {self.regulatory_manifest_id} ({self.manifest_title})"

    @property
    def accumulation_days(self):
        if not self.accumulation_start_date:
            return 0
        end_dt = self.shipment_date or timezone.now().date()
        return max(0, (end_dt - self.accumulation_start_date).days)

    @property
    def is_accumulation_overdue(self):
        return self.accumulation_days > 90 and self.status in ("draft", "scheduled")

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def manifest_type_css(self):
        return self.MANIFEST_TYPE_CSS.get(self.manifest_type, "badge-slate")

    @property
    def has_certificate(self):
        return bool(self.certificate_of_disposal_number or self.certificate_received_date)
