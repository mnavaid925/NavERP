from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class MeasurementSystemAnalysis(TenantNumbered):
    NUMBER_PREFIX = "QMSA"

    STUDY_TYPE_CHOICES = (
        ("gage_rr_crossed", "Gage R&R (Crossed / Standard)"),
        ("gage_rr_nested", "Gage R&R (Nested / Destructive)"),
        ("linearity_and_bias", "Gage Linearity & Bias Study"),
        ("stability_study", "Measurement Stability (Control Chart)"),
        ("attribute_agreement", "Attribute Agreement Analysis"),
        ("type_1_gage_study", "Type 1 Gage Study (Bias & Cgk)"),
    )

    ANALYSIS_METHOD_CHOICES = (
        ("anova", "ANOVA (Analysis of Variance) Method"),
        ("average_and_range_xbar_r", "Average & Range (X-bar & R) Method"),
    )

    STATUS_CHOICES = (
        ("draft", "Draft / Setup"),
        ("data_collection", "Data Collection"),
        ("analyzed", "Analyzed"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )

    RESULT_CHOICES = (
        ("acceptable", "Acceptable (%GRR < 10% / NDC >= 5)"),
        ("marginal_conditional", "Marginal / Conditional (%GRR 10-30%)"),
        ("unacceptable", "Unacceptable (%GRR > 30% / NDC < 5)"),
    )

    RESULT_CSS = {
        "acceptable": "badge-green",
        "marginal_conditional": "badge-amber",
        "unacceptable": "badge-red",
    }

    STATUS_CSS = {
        "draft": "badge-slate",
        "data_collection": "badge-amber",
        "analyzed": "badge-info",
        "approved": "badge-green",
        "rejected": "badge-red",
    }

    STUDY_TYPE_CSS = {
        "gage_rr_crossed": "badge-info",
        "gage_rr_nested": "badge-slate",
        "linearity_and_bias": "badge-amber",
        "stability_study": "badge-slate",
        "attribute_agreement": "badge-info",
        "type_1_gage_study": "badge-info",
    }

    study_title = models.CharField(
        max_length=150, help_text="e.g. Micrometer 0-25mm Gage R&R for Pin OD"
    )
    gage = models.ForeignKey(
        "quality.CalibrationGage", on_delete=models.CASCADE, related_name="msa_studies"
    )
    study_type = models.CharField(
        max_length=32, choices=STUDY_TYPE_CHOICES, default="gage_rr_crossed", db_index=True
    )
    analysis_method = models.CharField(
        max_length=32, choices=ANALYSIS_METHOD_CHOICES, default="anova", db_index=True
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)

    characteristic_name = models.CharField(
        max_length=150, help_text="Dimension or feature being measured e.g. Outer Diameter"
    )
    study_date = models.DateField(default=timezone.now, db_index=True)

    number_of_operators = models.PositiveIntegerField(default=3)
    number_of_parts = models.PositiveIntegerField(default=10)
    number_of_trials = models.PositiveIntegerField(default=3)

    specification_tolerance = models.DecimalField(
        max_digits=10, decimal_places=4, default=Decimal("0.1000"),
        help_text="Total process or product tolerance (USL - LSL)"
    )
    reference_master_value = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True,
        help_text="Certified master value for bias/linearity"
    )

    repeatability_ev = models.DecimalField(
        max_digits=10, decimal_places=4, default=Decimal("0.0000"),
        help_text="EV - Equipment Variation"
    )
    reproducibility_av = models.DecimalField(
        max_digits=10, decimal_places=4, default=Decimal("0.0000"),
        help_text="AV - Appraiser Variation"
    )
    gage_rr_grr = models.DecimalField(
        max_digits=10, decimal_places=4, default=Decimal("0.0000"),
        help_text="GRR - Combined Gage R&R"
    )
    part_variation_pv = models.DecimalField(
        max_digits=10, decimal_places=4, default=Decimal("0.0000"),
        help_text="PV - Part-to-part variation"
    )
    total_variation_tv = models.DecimalField(
        max_digits=10, decimal_places=4, default=Decimal("0.0000"),
        help_text="TV - Total study variation"
    )

    percent_gage_rr_study_variation = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal("0.00"),
        help_text="%GRR of Study Variation (<10% Acceptable, 10-30% Marginal, >30% Unacceptable)"
    )
    percent_tolerance_pt_ratio = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal("0.00"),
        help_text="P/T ratio (% of Tolerance)"
    )
    number_of_distinct_categories_ndc = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal("0.00"),
        help_text="NDC category count (>= 5 acceptable)"
    )

    bias_value = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    bias_percentage = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    linearity_slope = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    linearity_r_squared = models.DecimalField(max_digits=6, decimal_places=4, null=True, blank=True)

    study_result = models.CharField(
        max_length=24, choices=RESULT_CHOICES, default="acceptable", db_index=True
    )
    raw_study_data = models.JSONField(
        default=dict, blank=True,
        help_text="Raw measurement data array (operator, part, trial, value)"
    )

    study_protocol_doc = models.ForeignKey(
        "quality.ControlledDocument", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="msa_studies"
    )
    study_lead = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="led_msa_studies"
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="approved_msa_studies"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    conclusion = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-study_date", "-created_at"]
        verbose_name = "Measurement System Analysis (MSA)"
        verbose_name_plural = "Measurement System Analyses (MSA)"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qmsa_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "study_type"], name="idx_qmsa_ten_type"),
            models.Index(fields=["tenant", "study_result"], name="idx_qmsa_ten_res"),
            models.Index(fields=["tenant", "status"], name="idx_qmsa_ten_status"),
            models.Index(fields=["tenant", "gage"], name="idx_qmsa_ten_gage"),
            models.Index(fields=["tenant", "study_date"], name="idx_qmsa_ten_date"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qmsa_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} — {self.study_title} ({self.get_study_result_display()})"

    @property
    def result_css(self):
        return self.RESULT_CSS.get(self.study_result, "badge-slate")

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def study_type_css(self):
        return self.STUDY_TYPE_CSS.get(self.study_type, "badge-slate")
