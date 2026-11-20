from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class ComplaintInvestigation(TenantNumbered):
    NUMBER_PREFIX = "QCIN"

    INVESTIGATION_STATUS_CHOICES = (
        ("assigned", "Assigned / Pending Analysis"),
        ("in_progress", "Lab & DHR Analysis In Progress"),
        ("pending_sample", "Awaiting Return Sample Delivery"),
        ("hhe_review", "Clinical Health Hazard Review"),
        ("pending_qa_review", "Pending QA Manager Sign-Off"),
        ("approved", "Investigation Approved & Closed"),
        ("rejected_rework", "Rejected (Requires Rework)"),
    )

    ANALYTICAL_METHOD_CHOICES = (
        ("visual_microscopy", "Visual & Optical Microscopy"),
        ("dimensional_metrology", "Dimensional Metrology & CMM"),
        ("mechanical_stress", "Mechanical Stress / Tensile Testing"),
        ("electrical_functional", "Electrical Functional Diagnostic"),
        ("chemical_spectroscopy", "Chemical Spectroscopy / FTIR"),
        ("software_code_audit", "Software Trace & Log Audit"),
        ("historical_data_review", "Historical DHR & Batch Audit Only"),
        ("other", "Other Specialized Laboratory Method"),
    )

    ROOT_CAUSE_CATEGORY_CHOICES = (
        ("component_defect", "Raw Material / Component Defect"),
        ("assembly_workmanship", "Manufacturing / Assembly Workmanship"),
        ("process_deviation", "Equipment / Process Parameter Drift"),
        ("design_flaw", "Design Flaw / Specification Inadequacy"),
        ("software_bug", "Firmware / Software Bug"),
        ("packaging_barrier", "Sterile Packaging / Barrier Breach"),
        ("transit_damage", "Storage / Transportation / Transit Damage"),
        ("user_error_misuse", "User Operational Error / Clinical Misuse"),
        ("unconfirmed_no_defect", "Unconfirmed / No Defect Found (NDF)"),
        ("other", "Other Root Cause"),
    )

    STATUS_CSS = {
        "assigned": "badge-info",
        "in_progress": "badge-amber",
        "pending_sample": "badge-slate",
        "hhe_review": "badge-purple",
        "pending_qa_review": "badge-amber",
        "approved": "badge-green",
        "rejected_rework": "badge-red",
    }

    complaint = models.ForeignKey(
        "quality.CustomerComplaint",
        on_delete=models.CASCADE,
        related_name="investigations",
        help_text="Parent customer complaint",
    )
    lead_investigator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="lead_complaint_investigations",
    )
    target_completion_date = models.DateField(null=True, blank=True)
    actual_completion_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=30, choices=INVESTIGATION_STATUS_CHOICES, default="assigned", db_index=True)

    dhr_reviewed = models.BooleanField(default=False, help_text="Was the Device History Record / Batch Record reviewed?")
    dhr_lot_number = models.CharField(max_length=100, blank=True, help_text="Batch/DHR examined")
    dhr_quantity_produced = models.PositiveIntegerField(default=0, help_text="Total units produced in examined batch")
    dhr_anomalies_identified = models.BooleanField(default=False, help_text="Were non-conformances or deviations recorded in batch history?")
    dhr_review_summary = models.TextField(blank=True, help_text="Detailed notes from manufacturing and testing records")

    physical_sample_examined = models.BooleanField(default=False)
    analytical_method = models.CharField(max_length=32, choices=ANALYTICAL_METHOD_CHOICES, default="visual_microscopy", db_index=True)
    sample_testing_findings = models.TextField(blank=True, help_text="Laboratory diagnostics and observed failure mode")
    failure_reproduced = models.BooleanField(default=False, help_text="Was customer reported failure replicated under test conditions?")

    hhe_required = models.BooleanField(default=False, help_text="Is a Health Hazard Evaluation (HHE) clinically mandated?")
    health_hazard_evaluation = models.TextField(blank=True, help_text="Clinical medical assessment of patient/user injury likelihood and severity")
    risk_assessment = models.ForeignKey(
        "quality.RiskAssessment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_investigations",
        help_text="Linked ISO 14971 FMEA Risk Assessment",
    )
    risk_exceeds_threshold = models.BooleanField(default=False, help_text="Does observed event frequency or severity exceed FMEA anticipated limits?")

    root_cause_category = models.CharField(max_length=32, choices=ROOT_CAUSE_CATEGORY_CHOICES, default="unconfirmed_no_defect", db_index=True)
    root_cause_narrative = models.TextField(blank=True, help_text="5 Whys or failure tree root cause analysis summary")

    capa_required = models.BooleanField(default=False, help_text="Does root cause warrant formal CAPA initiation?")
    capa = models.ForeignKey(
        "quality.CapaInvestigation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_investigations",
        help_text="Linked CAPA record",
    )
    ncr = models.ForeignKey(
        "quality.NonConformanceReport",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_investigations",
        help_text="Linked Non-Conformance Report",
    )
    investigation_conclusion = models.TextField(blank=True, help_text="Formal engineering conclusion and risk disposition")
    qa_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_complaint_investigations",
    )
    qa_approved_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Complaint Investigation"
        verbose_name_plural = "Complaint Investigations"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qcin_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qcin_ten_status"),
            models.Index(fields=["tenant", "complaint"], name="idx_qcin_ten_cmp"),
            models.Index(fields=["tenant", "root_cause_category"], name="idx_qcin_ten_rcat"),
            models.Index(fields=["tenant", "lead_investigator"], name="idx_qcin_ten_inv"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qcin_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} - {self.complaint.number} Investigation"

    @property
    def is_overdue(self):
        if self.status in ["approved", "rejected_rework"]:
            return False
        if self.target_completion_date:
            return timezone.now().date() > self.target_completion_date
        return False

    @property
    def is_complete(self):
        return self.status == "approved"
