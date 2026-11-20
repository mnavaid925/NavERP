from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class RegulatoryReport(TenantNumbered):
    NUMBER_PREFIX = "QRPT"

    AGENCY_CHOICES = (
        ("fda_cdrh", "FDA CDRH (Medical Devices / eMDR)"),
        ("fda_cder", "FDA CDER (Pharmaceuticals / FAERS)"),
        ("eu_competent_auth", "EU Competent Authority (EUDAMED / MIR)"),
        ("health_canada", "Health Canada Medical Device Directorate"),
        ("pmda_japan", "PMDA Japan (Pharmaceuticals & Medical Devices)"),
        ("tga_australia", "TGA Australia Therapeutic Goods Admin"),
        ("mhra_uk", "MHRA UK Medicines & Healthcare Products"),
        ("other_authority", "Other National Regulatory Authority"),
    )

    REPORT_TYPE_CHOICES = (
        ("initial_report", "Initial Adverse Event Report"),
        ("follow_up_supplemental", "Follow-up / Supplemental Report"),
        ("final_closure_report", "Final Investigation / Closure Report"),
        ("non_reportable_justification", "Non-Reportable Decision Documentation"),
    )

    ADVERSE_EVENT_CLASS_CHOICES = (
        ("death", "Death Allegation"),
        ("serious_injury", "Serious Injury / Life-Threatening"),
        ("malfunction_recurrent", "Malfunction with Recurrence Potential"),
        ("public_health_threat", "Public Health Threat / Outbreak"),
        ("remedial_action_trigger", "Statutory Field Remedial Action"),
    )

    TIMELINE_CATEGORY_CHOICES = (
        ("2_day_public_health", "2-Day Public Health Threat Clock"),
        ("5_day_remedial", "5-Day Remedial Action / Urgent Clock"),
        ("10_day_death_deterioration", "10-Day Death / Unanticipated Deterioration"),
        ("15_day_serious_incident", "15-Day EU MIR Serious Incident Clock"),
        ("30_day_standard_mdr", "30-Day Standard FDA MDR / Annual Clock"),
    )

    SUBMISSION_STATUS_CHOICES = (
        ("draft", "Draft / In Preparation"),
        ("under_internal_review", "Under Regulatory Affairs Review"),
        ("ready_to_transmit", "Approved & Ready to Transmit"),
        ("submitted", "Submitted to Agency Gateway"),
        ("acknowledged", "Agency Acknowledged & Accepted"),
        ("rejected_supplement_needed", "Agency Deficient / Supplemental Required"),
        ("withdrawn", "Formally Withdrawn / Voided"),
    )

    SUBMISSION_FORMAT_CHOICES = (
        ("fda_medwatch_3500a", "FDA MedWatch Form 3500A (Paper/PDF)"),
        ("fda_emdr_xml", "FDA eMDR Gateway (XML AS2)"),
        ("eu_mir_xml", "EU MIR Manufacturer Incident Report XML"),
        ("eudamed_portal", "EUDAMED Web Portal Upload"),
        ("health_canada_portal", "Health Canada Regulatory Web Portal"),
        ("other_transmission", "Other Electronic / Secure Transmission"),
    )

    AGENCY_CSS = {
        "fda_cdrh": "badge-blue",
        "fda_cder": "badge-info",
        "eu_competent_auth": "badge-purple",
        "health_canada": "badge-red",
        "pmda_japan": "badge-amber",
        "tga_australia": "badge-green",
        "mhra_uk": "badge-slate",
        "other_authority": "badge-muted",
    }

    SUBMISSION_STATUS_CSS = {
        "draft": "badge-slate",
        "under_internal_review": "badge-amber",
        "ready_to_transmit": "badge-info",
        "submitted": "badge-purple",
        "acknowledged": "badge-green",
        "rejected_supplement_needed": "badge-red",
        "withdrawn": "badge-muted",
    }

    complaint = models.ForeignKey(
        "quality.CustomerComplaint",
        on_delete=models.CASCADE,
        related_name="regulatory_reports",
        help_text="Associated customer complaint",
    )
    agency = models.CharField(max_length=30, choices=AGENCY_CHOICES, default="fda_cdrh", db_index=True)
    report_type = models.CharField(max_length=32, choices=REPORT_TYPE_CHOICES, default="initial_report", db_index=True)
    adverse_event_class = models.CharField(
        max_length=32,
        choices=ADVERSE_EVENT_CLASS_CHOICES,
        default="malfunction_recurrent",
        db_index=True,
    )
    timeline_category = models.CharField(
        max_length=32,
        choices=TIMELINE_CATEGORY_CHOICES,
        default="30_day_standard_mdr",
        db_index=True,
    )
    statutory_due_date = models.DateField(db_index=True, help_text="Legally mandated agency transmission deadline")
    submission_status = models.CharField(max_length=30, choices=SUBMISSION_STATUS_CHOICES, default="draft", db_index=True)
    submission_format = models.CharField(max_length=30, choices=SUBMISSION_FORMAT_CHOICES, default="fda_emdr_xml")

    submission_date = models.DateField(null=True, blank=True, help_text="Date report was transmitted to agency")
    agency_report_identifier = models.CharField(
        max_length=100,
        blank=True,
        help_text="Agency reference / case file number (e.g. FDA MDR #, EU MIR ID)",
    )
    agency_acknowledgement_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Electronic submission gateway receipt / ACK number",
    )
    agency_acknowledgement_date = models.DateField(null=True, blank=True)

    event_summary = models.TextField(help_text="Official medical adverse event narrative for regulatory submission")
    device_operator = models.CharField(max_length=64, blank=True, help_text="e.g. 'Healthcare Professional', 'Patient', 'Lay User'")
    patient_remedial_action = models.TextField(blank=True, help_text="Medical interventions, surgeries, or therapies administered to patient")

    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="prepared_regulatory_reports",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_regulatory_reports",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["statutory_due_date", "-created_at"]
        verbose_name = "Regulatory Vigilance Report"
        verbose_name_plural = "Regulatory Vigilance Reports"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qrpt_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "submission_status"], name="idx_qrpt_ten_status"),
            models.Index(fields=["tenant", "agency"], name="idx_qrpt_ten_agency"),
            models.Index(fields=["tenant", "statutory_due_date"], name="idx_qrpt_ten_due"),
            models.Index(fields=["tenant", "complaint"], name="idx_qrpt_ten_cmp"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qrpt_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} - {self.get_agency_display()} ({self.get_report_type_display()})"

    @property
    def days_until_due(self):
        if self.statutory_due_date:
            return (self.statutory_due_date - timezone.now().date()).days
        return 0

    @property
    def is_overdue(self):
        if self.submission_status in ["acknowledged", "submitted", "withdrawn"]:
            return False
        return self.days_until_due < 0

    @property
    def urgency_badge_css(self):
        if self.is_overdue:
            return "badge-red"
        if self.days_until_due <= 3:
            return "badge-red"
        if self.days_until_due <= 7:
            return "badge-amber"
        return "badge-info"
