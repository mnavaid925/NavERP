from django.db import models

from apps.quality.models._base import TenantNumbered


class RiskAssessment(TenantNumbered):
    NUMBER_PREFIX = "QRSK"

    ANALYSIS_TYPE_CHOICES = (
        ("hazard_analysis", "Preliminary Hazard Analysis (PHA)"),
        ("dfmea", "Design FMEA (DFMEA)"),
        ("pfmea", "Process FMEA (PFMEA)"),
        ("software_fmea", "Software FMEA / Cyber Risk"),
        ("use_error_urra", "Usability / Use Error Analysis (URRA)"),
    )

    HAZARD_CATEGORY_CHOICES = (
        ("energy_electrical", "Electrical Energy / Shock"),
        ("energy_thermal", "Thermal Energy / Burns"),
        ("energy_mechanical", "Mechanical / Kinetic / Pressure"),
        ("radiation", "Ionizing / Optical Radiation"),
        ("biological_chemical", "Biological / Chemical Toxicity"),
        ("operational_use_error", "Human Factors / Use Error"),
        ("software_cybersecurity", "Software Failure / Cybersecurity"),
        ("environmental", "Environmental / Storage / Transport"),
        ("other", "Other Recognized Hazard"),
    )

    SEVERITY_CHOICES = (
        (1, "1 - Negligible (Inconvenience / No Injury)"),
        (2, "2 - Minor (Reversible Injury / First Aid)"),
        (3, "3 - Serious (Medical Intervention Required)"),
        (4, "4 - Critical (Permanent Impairment / Life Threat)"),
        (5, "5 - Catastrophic (Patient or User Death)"),
    )

    PROBABILITY_CHOICES = (
        (1, "1 - Improbable (< 1 in 100,000)"),
        (2, "2 - Remote (1 in 10,000)"),
        (3, "3 - Occasional (1 in 1,000)"),
        (4, "4 - Probable (1 in 100)"),
        (5, "5 - Frequent (> 1 in 10)"),
    )

    DETECTABILITY_CHOICES = (
        (1, "1 - Almost Certain (Automated Interlock / Check)"),
        (2, "2 - High (Obvious Alarm / Clear Visual Warning)"),
        (3, "3 - Moderate (Detectability through routine check)"),
        (4, "4 - Low (Subtle warning / easily overlooked)"),
        (5, "5 - Undetectable (Silent failure until harm occurs)"),
    )

    RISK_LEVEL_CHOICES = (
        ("broadly_acceptable", "Broadly Acceptable (Green)"),
        ("alarp", "ALARP / Conditionally Acceptable (Amber)"),
        ("unacceptable", "Unacceptable (Red)"),
    )

    LIFECYCLE_STATUS_CHOICES = (
        ("open", "Open / Unmitigated"),
        ("mitigation_in_progress", "Mitigation In Progress"),
        ("mitigated", "Mitigated / Pending Residual Check"),
        ("accepted", "Accepted with Clinical BRA"),
        ("closed", "Closed / Verified Safe"),
    )

    RISK_LEVEL_CSS = {
        "broadly_acceptable": "badge-green",
        "alarp": "badge-amber",
        "unacceptable": "badge-red",
    }

    LIFECYCLE_STATUS_CSS = {
        "open": "badge-red",
        "mitigation_in_progress": "badge-amber",
        "mitigated": "badge-info",
        "accepted": "badge-info",
        "closed": "badge-green",
    }

    ANALYSIS_TYPE_CSS = {
        "hazard_analysis": "badge-info",
        "dfmea": "badge-slate",
        "pfmea": "badge-slate",
        "software_fmea": "badge-amber",
        "use_error_urra": "badge-info",
    }

    plan = models.ForeignKey(
        "quality.RiskManagementPlan",
        on_delete=models.CASCADE,
        related_name="assessments",
    )
    analysis_type = models.CharField(
        max_length=24,
        choices=ANALYSIS_TYPE_CHOICES,
        default="hazard_analysis",
        db_index=True,
    )
    hazard_category = models.CharField(
        max_length=32,
        choices=HAZARD_CATEGORY_CHOICES,
        default="other",
    )
    hazard_description = models.CharField(
        max_length=255,
        help_text="Potential source of harm per ISO 14971",
    )
    hazardous_situation = models.TextField(
        help_text="Circumstance in which people, property, or environment are exposed to hazard(s)",
    )
    foreseeable_sequence_of_events = models.TextField(
        blank=True,
        help_text="Causal sequence of events leading to the hazardous situation",
    )
    potential_harm = models.TextField(
        help_text="Physical injury, impairment, damage to health, or environmental harm",
    )

    # FMEA specific fields
    item_function = models.CharField(
        max_length=255,
        blank=True,
        help_text="System component, subsystem, or process step analyzed",
    )
    failure_mode = models.CharField(
        max_length=255,
        blank=True,
        help_text="Specific manner in which the item fails to perform intended function",
    )
    failure_cause = models.TextField(
        blank=True,
        help_text="Root physical or chemical mechanism causing the failure mode",
    )
    failure_effect = models.TextField(
        blank=True,
        help_text="Consequence of the failure on the system or end user",
    )

    # Pre-mitigation scoring
    initial_severity = models.PositiveSmallIntegerField(
        default=3,
        choices=SEVERITY_CHOICES,
        help_text="1=Negligible to 5=Catastrophic",
    )
    initial_probability = models.PositiveSmallIntegerField(
        default=3,
        choices=PROBABILITY_CHOICES,
        help_text="1=Improbable to 5=Frequent",
    )
    initial_detectability = models.PositiveSmallIntegerField(
        default=1,
        choices=DETECTABILITY_CHOICES,
        help_text="1=Almost Certain to 5=Undetectable",
    )
    initial_rpn = models.PositiveIntegerField(
        default=0,
        editable=False,
        help_text="Computed S x P x D",
    )
    initial_risk_level = models.CharField(
        max_length=24,
        choices=RISK_LEVEL_CHOICES,
        default="unacceptable",
        editable=False,
    )

    # Post-mitigation residual scoring
    residual_severity = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        choices=SEVERITY_CHOICES,
    )
    residual_probability = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        choices=PROBABILITY_CHOICES,
    )
    residual_detectability = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        choices=DETECTABILITY_CHOICES,
    )
    residual_rpn = models.PositiveIntegerField(
        null=True,
        blank=True,
        editable=False,
    )
    residual_risk_level = models.CharField(
        max_length=24,
        choices=RISK_LEVEL_CHOICES,
        blank=True,
        editable=False,
    )
    residual_risk_acceptable = models.BooleanField(
        default=False,
        help_text="Meets pre-defined risk acceptability threshold",
    )
    bra_required = models.BooleanField(
        default=False,
        help_text="Mandatory Benefit-Risk Analysis if residual risk is in ALARP zone",
    )
    benefit_risk_justification = models.TextField(
        blank=True,
        help_text="Documented clinical evidence justifying that clinical benefit outweighs residual risk",
    )
    disclosed_in_ifu = models.BooleanField(
        default=False,
        help_text="Residual risk disclosed in Instructions for Use / device labeling",
    )

    design_input = models.ForeignKey(
        "quality.DesignInput",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="risk_assessments",
        help_text="Originating or mitigating design requirement in Design Controls",
    )
    lifecycle_status = models.CharField(
        max_length=28,
        choices=LIFECYCLE_STATUS_CHOICES,
        default="open",
        db_index=True,
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Risk Assessment"
        verbose_name_plural = "Risk Assessments"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qrsk_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "plan", "analysis_type"], name="idx_qrsk_ten_pln_type"),
            models.Index(fields=["tenant", "hazard_category"], name="idx_qrsk_ten_hazard_cat"),
            models.Index(fields=["tenant", "initial_risk_level"], name="idx_qrsk_ten_init_lvl"),
            models.Index(fields=["tenant", "residual_risk_level"], name="idx_qrsk_ten_res_lvl"),
            models.Index(fields=["tenant", "lifecycle_status"], name="idx_qrsk_ten_status"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qrsk_ten_created"),
        ]

    def __str__(self):
        desc = self.hazard_description or self.failure_mode or "Risk Assessment"
        return f"{self.number} - {desc}"

    @property
    def initial_risk_level_badge(self):
        return self.RISK_LEVEL_CSS.get(self.initial_risk_level, "badge-slate")

    @property
    def residual_risk_level_badge(self):
        return self.RISK_LEVEL_CSS.get(self.residual_risk_level, "badge-slate")

    @property
    def lifecycle_status_badge(self):
        return self.LIFECYCLE_STATUS_CSS.get(self.lifecycle_status, "badge-slate")

    @property
    def analysis_type_badge(self):
        return self.ANALYSIS_TYPE_CSS.get(self.analysis_type, "badge-slate")

    @staticmethod
    def calculate_level(severity, probability):
        score = severity * probability
        if score >= 15:
            return "unacceptable"
        elif score >= 6:
            return "alarp"
        return "broadly_acceptable"

    def save(self, *args, **kwargs):
        # Calculate initial score
        s = self.initial_severity or 1
        p = self.initial_probability or 1
        d = self.initial_detectability or 1
        self.initial_rpn = s * p * d
        self.initial_risk_level = self.calculate_level(s, p)

        # Calculate residual score if post-mitigation values exist
        if self.residual_severity and self.residual_probability:
            res_s = self.residual_severity
            res_p = self.residual_probability
            res_d = self.residual_detectability or 1
            self.residual_rpn = res_s * res_p * res_d
            self.residual_risk_level = self.calculate_level(res_s, res_p)

            if self.residual_risk_level == "unacceptable":
                self.residual_risk_acceptable = False
            elif self.residual_risk_level == "alarp":
                self.bra_required = True
            elif self.residual_risk_level == "broadly_acceptable":
                self.residual_risk_acceptable = True
        else:
            self.residual_rpn = None
            self.residual_risk_level = ""
            self.residual_risk_acceptable = False

        super().save(*args, **kwargs)
