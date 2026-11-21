import datetime
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class CleaningValidation(TenantNumbered):
    NUMBER_PREFIX = "QCLN"

    WORST_CASE_RATIONALE_CHOICES = [
        ("lowest_solubility", "Lowest Solubility in Cleaning Solvent"),
        ("highest_toxicity_pde", "Highest Toxicity / Lowest PDE Limit"),
        ("highest_potency", "Highest Therapeutic Potency"),
        ("hardest_to_clean", "Physical Hardness / Residue Tenacity"),
    ]

    CALCULATION_BASIS_CHOICES = [
        ("therapeutic_dose", "1/1000th Minimum Therapeutic Dose"),
        ("ten_ppm_limit", "10 ppm General Default Limit"),
        ("toxicological_pde", "Health-Based Toxicological PDE/ADE"),
        ("most_stringent", "Most Stringent (Safety Envelope)"),
    ]

    ANALYTICAL_METHOD_CHOICES = [
        ("hplc", "HPLC / UPLC UV Specific Assay"),
        ("toc", "Total Organic Carbon (TOC)"),
        ("uv_vis", "UV-Vis Spectrophotometry"),
        ("conductivity", "Conductivity Verification"),
        ("visual_clean", "Visual Cleanliness Inspection"),
    ]

    CLEANING_STATUS_CHOICES = [
        ("draft", "Draft Study Protocol"),
        ("protocol_approved", "Protocol Approved for Execution"),
        ("sampling_in_progress", "Swab / Rinse Sampling Active"),
        ("analytical_testing", "Analytical Lab Testing in Progress"),
        ("validated_pass", "Cleaning Validated (Passed)"),
        ("failed_recleaning", "Failed (Recleaning Required)"),
        ("expired", "Revalidation Cycle Expired"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "protocol_approved": "badge-info",
        "sampling_in_progress": "badge-amber",
        "analytical_testing": "badge-amber",
        "validated_pass": "badge-green",
        "failed_recleaning": "badge-red",
        "expired": "badge-muted",
    }

    title = models.CharField(max_length=255, help_text="Title e.g. Solid Dose Granulation Train Cleaning Validation")
    equipment_train_tag = models.CharField(max_length=150, help_text="Equipment train or shared asset identifier (e.g. Mixer + Granulator + Coater)")
    target_residue = models.CharField(max_length=150, help_text="Target active ingredient (API), marker substance, or detergent of interest")
    cleaning_agent_used = models.CharField(max_length=150, help_text="Cleaning detergent or solvent used (e.g. CIP-100, WFI, 0.1M NaOH)")
    worst_case_rationale = models.CharField(max_length=28, choices=WORST_CASE_RATIONALE_CHOICES, default="highest_potency")
    calculation_basis = models.CharField(max_length=25, choices=CALCULATION_BASIS_CHOICES, default="most_stringent")

    min_daily_dose_active_mg = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True,
        help_text="Minimum therapeutic daily dose of preceding active (Product A) in mg"
    )
    max_daily_dose_subsequent_mg = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True,
        help_text="Maximum daily dose of next product (Product B) in mg"
    )
    smallest_batch_size_kg = models.DecimalField(
        max_digits=12, decimal_places=3,
        help_text="Smallest commercial batch size of subsequent product (Product B) in kg"
    )
    safety_factor = models.DecimalField(
        max_digits=8, decimal_places=1, default=Decimal("1000.0"),
        help_text="Safety factor denominator (typically 1000 for oral doses)"
    )
    toxicological_pde_mg_day = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True,
        help_text="Permitted Daily Exposure (PDE) limit in mg/day"
    )

    calculated_maco_mg = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True,
        help_text="Computed Maximum Allowable Carryover (MACO) in shared train (mg)"
    )
    total_surface_area_sqcm = models.DecimalField(
        max_digits=14, decimal_places=2,
        help_text="Total product-contact surface area of equipment train in cm²"
    )
    swab_sampling_area_sqcm = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("25.0"),
        help_text="Area sampled per swab coupon in cm² (typically 25.0 cm²)"
    )
    calculated_swab_limit_ug = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True,
        help_text="Calculated maximum residue limit per swab in µg"
    )
    rinse_volume_liters = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Total final rinse solvent volume in Liters"
    )
    calculated_rinse_limit_ppm = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True,
        help_text="Calculated allowable rinse concentration in ppm (mg/L)"
    )

    analytical_method = models.CharField(max_length=20, choices=ANALYTICAL_METHOD_CHOICES, default="hplc")
    method_recovery_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("80.00"),
        help_text="Analytical method swab recovery percentage (e.g. 80.0%)"
    )

    dirty_hold_time_hours = models.DecimalField(max_digits=8, decimal_places=1, help_text="Validated Dirty Hold Time (DHT) in hours")
    clean_hold_time_hours = models.DecimalField(max_digits=8, decimal_places=1, help_text="Validated Clean Hold Time (CHT) in hours")
    consecutive_successful_runs = models.PositiveIntegerField(default=0, help_text="Count of consecutive successful validation runs completed (target >= 3)")
    is_visually_clean = models.BooleanField(default=True, help_text="Verification that all product-contact surfaces are visually clean and odor-free")

    worst_swab_result_ug = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True, help_text="Highest residue measured across all swab locations in µg")
    worst_rinse_result_ppm = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True, help_text="Highest concentration measured in rinse samples in ppm")

    cleaning_status = models.CharField(max_length=28, choices=CLEANING_STATUS_CHOICES, default="draft", db_index=True)
    next_revalidation_date = models.DateField(null=True, blank=True, db_index=True, help_text="Date for routine periodic revalidation")
    notes = models.TextField(blank=True)

    validation_protocol = models.ForeignKey(
        "quality.ValidationProtocol",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cleaning_studies",
        help_text="Parent qualification protocol",
    )
    cleaning_sop = models.ForeignKey(
        "quality.ControlledDocument",
        on_delete=models.PROTECT,
        related_name="cleaning_validation_studies",
        help_text="Standard Operating Procedure governing the cleaning procedure",
    )
    analytical_lead = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cleaning_studies",
        help_text="Chemist / analytical scientist performing test",
    )
    qa_approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_cleaning_studies",
        help_text="Quality Assurance release authority",
    )
    linked_deviation = models.ForeignKey(
        "quality.ProcessDeviation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cleaning_studies",
        help_text="Out of specification cleaning deviation",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Cleaning Validation"
        verbose_name_plural = "Cleaning Validations"
        indexes = [
            models.Index(fields=["tenant", "cleaning_status"], name="idx_qcln_ten_status"),
            models.Index(fields=["tenant", "next_revalidation_date"], name="idx_qcln_ten_reval_due"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qcln_ten_num_uniq"),
        ]

    def __str__(self):
        return f"{self.number} - {self.target_residue} ({self.equipment_train_tag})"

    @property
    def is_revalidation_overdue(self):
        if self.next_revalidation_date and self.cleaning_status not in ("expired",):
            return self.next_revalidation_date < datetime.date.today()
        return False

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.cleaning_status, "badge-slate")

    def calculate_limits(self):
        """Calculates MACO, Swab limit, and Rinse limit using GMP regulatory formulas."""
        limits = []

        # 1. 10 ppm general limit: MACO = 10 mg/kg * Batch Size (kg)
        if self.smallest_batch_size_kg and self.smallest_batch_size_kg > Decimal("0"):
            maco_10ppm = Decimal("10.0") * self.smallest_batch_size_kg
            if self.calculation_basis == "ten_ppm_limit":
                limits = [maco_10ppm]
            else:
                limits.append(maco_10ppm)

        # 2. Therapeutic dose limit: MACO = (Min Dose / Safety Factor) * (Smallest Batch / Max Daily Dose)
        if (
            self.min_daily_dose_active_mg
            and self.max_daily_dose_subsequent_mg
            and self.smallest_batch_size_kg
            and self.safety_factor
            and self.max_daily_dose_subsequent_mg > Decimal("0")
            and self.safety_factor > Decimal("0")
        ):
            # Batch size in mg: smallest_batch_size_kg * 1,000,000 mg/kg
            batch_mg = self.smallest_batch_size_kg * Decimal("1000000.0")
            number_of_doses = batch_mg / self.max_daily_dose_subsequent_mg
            maco_dose = (self.min_daily_dose_active_mg / self.safety_factor) * number_of_doses
            if self.calculation_basis == "therapeutic_dose":
                limits = [maco_dose]
            else:
                limits.append(maco_dose)

        # 3. Toxicological PDE limit: MACO = PDE * (Smallest Batch / Max Daily Dose)
        if (
            self.toxicological_pde_mg_day
            and self.max_daily_dose_subsequent_mg
            and self.smallest_batch_size_kg
            and self.max_daily_dose_subsequent_mg > Decimal("0")
        ):
            batch_mg = self.smallest_batch_size_kg * Decimal("1000000.0")
            number_of_doses = batch_mg / self.max_daily_dose_subsequent_mg
            maco_pde = self.toxicological_pde_mg_day * number_of_doses
            if self.calculation_basis == "toxicological_pde":
                limits = [maco_pde]
            else:
                limits.append(maco_pde)

        if limits:
            self.calculated_maco_mg = min(limits).quantize(Decimal("0.0001"))

            # Swab limit: (MACO in ug / Surface Area) * Swab Area * Recovery %
            # MACO in ug = MACO in mg * 1000
            if self.total_surface_area_sqcm and self.total_surface_area_sqcm > Decimal("0"):
                maco_ug = self.calculated_maco_mg * Decimal("1000.0")
                surface_limit_ug_cm2 = maco_ug / self.total_surface_area_sqcm
                swab_area = self.swab_sampling_area_sqcm or Decimal("25.0")
                recovery_factor = (self.method_recovery_percentage or Decimal("100.0")) / Decimal("100.0")
                self.calculated_swab_limit_ug = (surface_limit_ug_cm2 * swab_area * recovery_factor).quantize(Decimal("0.001"))

            # Rinse limit: MACO in mg / Rinse Volume in Liters = mg/L (ppm)
            if self.rinse_volume_liters and self.rinse_volume_liters > Decimal("0"):
                self.calculated_rinse_limit_ppm = (self.calculated_maco_mg / self.rinse_volume_liters).quantize(Decimal("0.001"))

    def save(self, *args, **kwargs):
        self.calculate_limits()
        super().save(*args, **kwargs)
