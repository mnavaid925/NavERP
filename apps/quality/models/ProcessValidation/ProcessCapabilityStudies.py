from decimal import Decimal
import math

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class ProcessCapabilityStudy(TenantNumbered):
    NUMBER_PREFIX = "QCPK"

    PARAMETER_CATEGORY_CHOICES = [
        ("dimensional_thickness", "Dimensional / Thickness / Diameter"),
        ("temperature", "Temperature / Thermal Cycle"),
        ("pressure", "Pressure / Vacuum Seal"),
        ("speed_feed", "Speed / Flow / Feed Rate"),
        ("torque", "Torque / Force Tension"),
        ("ph_chemical", "pH / Conductivity / Concentration"),
        ("humidity", "Relative Humidity / Moisture"),
        ("voltage_current", "Voltage / Current / Resistance"),
        ("cycle_time", "Cycle Time / Dwell Duration"),
        ("weight_mass", "Fill Weight / Mass / Density"),
        ("other", "Other Critical Parameter"),
    ]

    CAPABILITY_DETERMINATION_CHOICES = [
        ("highly_capable", "Highly Capable (Cpk >= 1.67)"),
        ("capable", "Capable (1.33 <= Cpk < 1.67)"),
        ("marginally_capable", "Marginally Capable (1.00 <= Cpk < 1.33)"),
        ("incapable", "Incapable / Action Required (Cpk < 1.00)"),
        ("undetermined", "Undetermined / Incomplete Data"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft Study"),
        ("data_collection", "Data Collection in Progress"),
        ("analyzed", "Statistical Analysis Completed"),
        ("approved", "Capability Study Approved"),
        ("action_required", "CAPA / Engineering Action Required"),
    ]

    DETERMINATION_CSS = {
        "highly_capable": "badge-green",
        "capable": "badge-info",
        "marginally_capable": "badge-amber",
        "incapable": "badge-red",
        "undetermined": "badge-slate",
    }

    STATUS_CSS = {
        "draft": "badge-muted",
        "data_collection": "badge-info",
        "analyzed": "badge-amber",
        "approved": "badge-green",
        "action_required": "badge-red",
    }

    title = models.CharField(max_length=255, help_text="Study title e.g. Tablet Press 02 Fill Weight Capability Study")
    parameter_name = models.CharField(max_length=150, help_text="Critical Quality Attribute (CQA) or Critical Process Parameter (CPP) measured")
    parameter_category = models.CharField(max_length=30, choices=PARAMETER_CATEGORY_CHOICES, default="dimensional_thickness", db_index=True)
    unit_of_measure = models.CharField(max_length=50, default="mm", help_text="Engineering unit (e.g. mm, °C, bar, g, mL, psi)")

    upper_spec_limit = models.DecimalField(max_digits=12, decimal_places=4, help_text="Upper Specification Limit (USL)")
    lower_spec_limit = models.DecimalField(max_digits=12, decimal_places=4, help_text="Lower Specification Limit (LSL)")
    target_nominal = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True, help_text="Process target or nominal aim point")

    subgroup_size = models.PositiveIntegerField(default=5, help_text="Rational subgroup sample size (n >= 1)")
    number_of_subgroups = models.PositiveIntegerField(default=25, help_text="Total number of subgroups sampled (k)")
    total_samples = models.PositiveIntegerField(default=125, help_text="Total individual sample observations (N = n * k)")

    mean_value = models.DecimalField(max_digits=12, decimal_places=4, help_text="Calculated process average (X-bar)")
    within_subgroup_stdev = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True, help_text="Short-term within-subgroup variation (sigma_within)")
    overall_stdev = models.DecimalField(max_digits=12, decimal_places=4, help_text="Total overall sample standard deviation (s_overall)")

    cp_index = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True, help_text="Potential capability index: Cp = (USL - LSL) / (6 * sigma_within)")
    cpk_index = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True, help_text="Centering-adjusted capability index: Cpk = min(Cpu, Cpl)")
    pp_index = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True, help_text="Overall performance index: Pp = (USL - LSL) / (6 * s_overall)")
    ppk_index = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True, help_text="Centering-adjusted performance index: Ppk = min(Ppu, Ppl)")
    expected_ppm = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Estimated non-conforming parts per million based on normal distribution")

    is_normally_distributed = models.BooleanField(default=True, help_text="Normality assumption verified via probability plot / goodness of fit")
    capability_determination = models.CharField(max_length=25, choices=CAPABILITY_DETERMINATION_CHOICES, default="undetermined", db_index=True)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="draft", db_index=True)

    process_name = models.CharField(max_length=150, blank=True, help_text="Manufacturing step or production operation stand-in")
    equipment_tag = models.CharField(max_length=100, blank=True, help_text="Machine or tool asset tag stand-in")
    item_code = models.CharField(max_length=100, blank=True, help_text="Manufactured item number stand-in")
    lot_number = models.CharField(max_length=100, blank=True, help_text="Batch or production run identifier stand-in")

    analysis_summary = models.TextField(blank=True, help_text="Statistical conclusions, assignable causes, and process capability assessment notes")
    study_date = models.DateField(null=True, blank=True, help_text="Date capability study data was acquired")

    validation_protocol = models.ForeignKey(
        "quality.ValidationProtocol",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="capability_studies",
        help_text="Associated qualification protocol (PQ/PPQ/CPV)",
    )
    investigator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="capability_studies",
        help_text="Quality engineer / statistician performing study",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_capability_studies",
        help_text="Quality manager approving capability determination",
    )
    linked_parameter_log = models.ForeignKey(
        "quality.ProcessParameterLog",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="capability_studies",
        help_text="Source shop-floor parameter log run",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Process Capability Study"
        verbose_name_plural = "Process Capability Studies"
        indexes = [
            models.Index(fields=["tenant", "-created_at"], name="idx_qcpk_ten_created"),
            models.Index(fields=["tenant", "status"], name="idx_qcpk_ten_status"),
            models.Index(fields=["tenant", "capability_determination"], name="idx_qcpk_ten_determ"),
            models.Index(fields=["tenant", "parameter_category"], name="idx_qcpk_ten_param_cat"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qcpk_ten_num_uniq"),
        ]

    def __str__(self):
        return f"{self.number} - {self.parameter_name} ({self.title})"

    @property
    def tolerance_width(self):
        return self.upper_spec_limit - self.lower_spec_limit

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def determination_css(self):
        return self.DETERMINATION_CSS.get(self.capability_determination, "badge-slate")

    def calculate_indices(self):
        """Calculates statistical capability and performance indices."""
        tol = self.upper_spec_limit - self.lower_spec_limit
        if tol <= Decimal("0"):
            return

        # Overall performance (Pp, Ppk)
        if self.overall_stdev and self.overall_stdev > Decimal("0"):
            six_sigma_overall = Decimal("6") * self.overall_stdev
            three_sigma_overall = Decimal("3") * self.overall_stdev
            self.pp_index = (tol / six_sigma_overall).quantize(Decimal("0.001"))

            ppu = (self.upper_spec_limit - self.mean_value) / three_sigma_overall
            ppl = (self.mean_value - self.lower_spec_limit) / three_sigma_overall
            self.ppk_index = min(ppu, ppl).quantize(Decimal("0.001"))

        # Within-subgroup capability (Cp, Cpk)
        sigma_w = self.within_subgroup_stdev or self.overall_stdev
        if sigma_w and sigma_w > Decimal("0"):
            six_sigma_w = Decimal("6") * sigma_w
            three_sigma_w = Decimal("3") * sigma_w
            self.cp_index = (tol / six_sigma_w).quantize(Decimal("0.001"))

            cpu = (self.upper_spec_limit - self.mean_value) / three_sigma_w
            cpl = (self.mean_value - self.lower_spec_limit) / three_sigma_w
            self.cpk_index = min(cpu, cpl).quantize(Decimal("0.001"))

        # Determine capability status
        target_index = self.cpk_index if self.cpk_index is not None else self.ppk_index
        if target_index is not None:
            if target_index >= Decimal("1.67"):
                self.capability_determination = "highly_capable"
            elif target_index >= Decimal("1.33"):
                self.capability_determination = "capable"
            elif target_index >= Decimal("1.00"):
                self.capability_determination = "marginally_capable"
            else:
                self.capability_determination = "incapable"

            # Approximate PPM calculation using normal cumulative distribution
            try:
                z_score = float(target_index * 3)
                # Area under tail of standard normal distribution
                p_one_tail = 0.5 * math.erfc(z_score / math.sqrt(2))
                self.expected_ppm = Decimal(str(round(p_one_tail * 2 * 1_000_000, 2)))
            except Exception:
                self.expected_ppm = Decimal("0.00")

    def save(self, *args, **kwargs):
        self.calculate_indices()
        super().save(*args, **kwargs)
