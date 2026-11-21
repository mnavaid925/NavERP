from django.conf import settings
from django.db import models

from apps.quality.models._base import TenantNumbered


class ElectronicRecordPolicy(TenantNumbered):
    NUMBER_PREFIX = "QREC"

    RECORD_CATEGORY_CHOICES = [
        ("production_batch", "Batch Production & Lot Records"),
        ("lab_analytical", "Laboratory & Analytical Test Data"),
        ("equipment_calibration", "Equipment Calibration & Maintenance"),
        ("change_control", "Change Control & System Validation"),
        ("deviation_ncr", "Deviation, OOS & Non-Conformance"),
        ("capa", "Corrective & Preventive Action (CAPA)"),
        ("audit_inspection", "Audits & Regulatory Inspections"),
        ("training_competency", "Training & Competency Records"),
        ("complaint_pharmacovigilance", "Complaints & Pharmacovigilance"),
        ("electronic_signature", "Electronic Signature Logs"),
    ]

    SIGNATURE_REQUIREMENT_CHOICES = [
        ("none", "No Electronic Signature Required"),
        ("single_author", "Single Signature: Author / Originator"),
        ("dual_peer_review", "Dual Signature: Author + Technical Verifier"),
        ("triple_qa_approval", "Triple Signature: Author + Reviewer + QA Approval"),
        ("ccb_approval", "Change Control Board (CCB) Multi-Signoff"),
    ]

    STORAGE_FORMAT_CHOICES = [
        ("database_relational", "Relational Database with Encrypted Storage"),
        ("pdf_a_immutable", "PDF/A-1a Archival Blob with Digital Signature"),
        ("xml_json_raw", "Structured XML/JSON Raw Stream"),
        ("hybrid_blob", "Hybrid: Structured Table + WORM Object Store"),
    ]

    BACKUP_FREQUENCY_CHOICES = [
        ("continuous_wal", "Continuous Write-Ahead Log (WAL) Streaming"),
        ("hourly_incremental", "Hourly Incremental Snapshot"),
        ("daily_snapshot", "Daily Automated Snapshot"),
        ("weekly_full", "Weekly Full Cold Storage Backup"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft Policy"),
        ("active", "Active & Enforced"),
        ("under_revision", "Under Periodic Revision"),
        ("archived", "Archived / Retired"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "active": "badge-green",
        "under_revision": "badge-amber",
        "archived": "badge-muted",
    }

    title = models.CharField(max_length=255)
    record_type_name = models.CharField(max_length=150, db_index=True)
    record_category = models.CharField(
        max_length=40, choices=RECORD_CATEGORY_CHOICES, default="production_batch", db_index=True
    )
    target_model_name = models.CharField(
        max_length=100, blank=True, help_text="Django model or dataset name (e.g. BatchRecord)"
    )
    system = models.ForeignKey(
        "quality.ComputerSystemValidation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="electronic_record_policies",
    )
    governing_sop = models.ForeignKey(
        "quality.ControlledDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="record_policies",
    )
    is_part_11_regulated = models.BooleanField(
        default=True, db_index=True, help_text="Subject to FDA 21 CFR Part 11 requirements"
    )
    is_annex_11_regulated = models.BooleanField(
        default=True, help_text="Subject to EU GMP Annex 11 requirements"
    )
    signature_requirement = models.CharField(
        max_length=30, choices=SIGNATURE_REQUIREMENT_CHOICES, default="dual_peer_review"
    )
    reauthentication_required = models.BooleanField(
        default=True, help_text="Password/MFA re-entry required at moment of signature execution"
    )
    dual_signature_required = models.BooleanField(default=False)
    audit_trail_mandatory = models.BooleanField(default=True)
    retention_period_years = models.PositiveIntegerField(
        default=10, help_text="Mandatory retention period in years"
    )
    storage_format = models.CharField(
        max_length=30, choices=STORAGE_FORMAT_CHOICES, default="database_relational"
    )
    backup_frequency = models.CharField(
        max_length=30, choices=BACKUP_FREQUENCY_CHOICES, default="daily_snapshot"
    )
    legal_hold = models.BooleanField(
        default=False, db_index=True, help_text="Litigation / regulatory investigation freeze"
    )
    status = models.CharField(
        max_length=25, choices=STATUS_CHOICES, default="draft", db_index=True
    )
    system_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_record_policies",
    )
    qa_approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_record_policies",
    )
    approval_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "record_type_name"]
        verbose_name = "Electronic Record Policy"
        verbose_name_plural = "Electronic Record Policies"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qrec_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "record_category", "status"], name="idx_qrec_ten_cat_stat"),
            models.Index(fields=["tenant", "is_part_11_regulated"], name="idx_qrec_ten_part11"),
        ]

    def __str__(self):
        return f"{self.number} — {self.record_type_name}"

    @property
    def is_active(self):
        return self.status == "active"

    @property
    def requires_signature(self):
        return self.signature_requirement != "none"
