from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class HazardousMaterial(TenantNumbered):
    NUMBER_PREFIX = "QHAZ"

    PHYSICAL_STATE_CHOICES = [
        ("liquid", "Liquid"),
        ("solid", "Solid"),
        ("gas", "Compressed Gas"),
        ("aerosol", "Aerosol"),
        ("sludge", "Sludge / Paste"),
    ]

    GHS_SIGNAL_WORD_CHOICES = [
        ("danger", "Danger"),
        ("warning", "Warning"),
        ("none", "None / Non-Hazardous"),
    ]

    NFPA_SPECIAL_HAZARD_CHOICES = [
        ("none", "None"),
        ("ox", "OX — Oxidizer"),
        ("w_slash", "W (bar) — Reacts violently with water"),
        ("sa", "SA — Simple Asphyxiant"),
        ("cor", "COR — Corrosive"),
        ("bio", "BIO — Biological Hazard"),
    ]

    STATUS_CHOICES = [
        ("active", "Active In Use"),
        ("restricted", "Restricted Access"),
        ("under_review", "Under EHS Review"),
        ("discontinued", "Discontinued / Phased Out"),
    ]

    STATUS_CSS = {
        "active": "badge-green",
        "restricted": "badge-amber",
        "under_review": "badge-info",
        "discontinued": "badge-slate",
    }

    SIGNAL_WORD_CSS = {
        "danger": "badge-red",
        "warning": "badge-amber",
        "none": "badge-slate",
    }

    material_name = models.CharField(max_length=255, help_text="Common or technical chemical name")
    trade_name = models.CharField(max_length=255, blank=True, help_text="Commercial trade name or brand identifier")
    cas_number = models.CharField(max_length=50, blank=True, db_index=True, help_text="CAS Registry Number (e.g. 67-64-1)")
    un_number = models.CharField(max_length=20, blank=True, help_text="UN transport identification number (e.g. UN1090)")
    chemical_formula = models.CharField(max_length=100, blank=True, help_text="Empirical or structural chemical formula")
    physical_state = models.CharField(max_length=20, choices=PHYSICAL_STATE_CHOICES, default="liquid", db_index=True)
    ghs_signal_word = models.CharField(max_length=20, choices=GHS_SIGNAL_WORD_CHOICES, default="warning", db_index=True)
    ghs_pictograms = models.CharField(max_length=255, blank=True, help_text="Comma-separated GHS pictogram codes")
    hazard_statements = models.TextField(blank=True, help_text="GHS Hazard statements (H-codes and descriptions)")
    precautionary_statements = models.TextField(blank=True, help_text="GHS Precautionary statements (P-codes and instructions)")

    nfpa_health = models.PositiveSmallIntegerField(default=0, help_text="NFPA 704 Health rating 0-4")
    nfpa_flammability = models.PositiveSmallIntegerField(default=0, help_text="NFPA 704 Flammability rating 0-4")
    nfpa_instability = models.PositiveSmallIntegerField(default=0, help_text="NFPA 704 Instability/Reactivity rating 0-4")
    nfpa_special_hazard = models.CharField(max_length=20, choices=NFPA_SPECIAL_HAZARD_CHOICES, default="none")

    sds_revision = models.CharField(max_length=50, blank=True, default="Rev 1.0", help_text="SDS document revision identifier")
    sds_issue_date = models.DateField(null=True, blank=True, help_text="Date SDS was issued by manufacturer")
    sds_expiry_date = models.DateField(null=True, blank=True, db_index=True, help_text="3-year SDS renewal or expiration target date")
    sds_document = models.ForeignKey(
        "quality.ControlledDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hazardous_materials",
        help_text="Linked controlled document in QMS Document Control",
    )

    osha_pel = models.CharField(max_length=100, blank=True, help_text="OSHA Permissible Exposure Limit (e.g. 1000 ppm TWA)")
    acgih_tlv = models.CharField(max_length=100, blank=True, help_text="ACGIH Threshold Limit Value (e.g. 500 ppm TWA, 750 ppm STEL)")
    exposure_uom = models.CharField(max_length=50, blank=True, default="ppm", help_text="Exposure limit unit of measure")
    ppe_requirements = models.TextField(blank=True, help_text="Mandatory PPE specifications (respirator, gloves, eye protection)")
    incompatible_materials = models.TextField(blank=True, help_text="Incompatible substances to segregate from")
    spill_cleanup_procedure = models.TextField(blank=True, help_text="Emergency spill containment and cleanup instructions")

    org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hazardous_materials",
        help_text="Facility or departmental storage owner",
    )
    storage_location_code = models.CharField(max_length=100, blank=True, help_text="Storage location code e.g. Flammable-Cabinet-A1")
    maximum_storage_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), help_text="Maximum authorized storage capacity")
    quantity_uom = models.CharField(max_length=50, default="L", help_text="Unit of measure for storage quantity")
    supplier = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hazardous_materials",
        help_text="Chemical manufacturer or commercial vendor",
    )
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="active", db_index=True)
    managed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="managed_hazardous_materials",
        help_text="Designated Chemical Hygiene / Safety Officer",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["material_name", "number"]
        verbose_name = "Hazardous Material"
        verbose_name_plural = "Hazardous Materials"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qhaz_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qhaz_ten_status"),
            models.Index(fields=["tenant", "physical_state"], name="idx_qhaz_ten_state"),
            models.Index(fields=["tenant", "cas_number"], name="idx_qhaz_ten_cas"),
            models.Index(fields=["tenant", "sds_expiry_date"], name="idx_qhaz_ten_exp_dt"),
            models.Index(fields=["tenant", "org_unit"], name="idx_qhaz_ten_org"),
            models.Index(fields=["tenant", "supplier"], name="idx_qhaz_ten_sup"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qhaz_ten_created"),
            models.Index(fields=["tenant", "material_name"], name="idx_qhaz_ten_name"),
        ]

    def __str__(self):
        return f"{self.number} — {self.material_name}"

    @property
    def is_sds_expired(self):
        if not self.sds_expiry_date:
            return False
        return self.sds_expiry_date < timezone.now().date()

    @property
    def sds_status_css(self):
        if not self.sds_expiry_date:
            return "badge-slate"
        today = timezone.now().date()
        if self.sds_expiry_date < today:
            return "badge-red"
        days_remaining = (self.sds_expiry_date - today).days
        if days_remaining <= 90:
            return "badge-amber"
        return "badge-green"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def signal_word_css(self):
        return self.SIGNAL_WORD_CSS.get(self.ghs_signal_word, "badge-slate")

    @property
    def pictograms_list(self):
        if not self.ghs_pictograms:
            return []
        return [p.strip() for p in self.ghs_pictograms.split(",") if p.strip()]
