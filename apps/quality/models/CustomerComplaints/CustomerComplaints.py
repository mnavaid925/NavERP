from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class CustomerComplaint(TenantNumbered):
    NUMBER_PREFIX = "QCMP"

    INTAKE_CHANNEL_CHOICES = (
        ("phone", "Telephone Call"),
        ("email", "Direct Email"),
        ("web_portal", "Web Customer Portal"),
        ("sales_rep", "Sales Representative"),
        ("service_tech", "Field Service Technician"),
        ("distributor", "Distributor / Wholesaler"),
        ("regulatory_agency", "Regulatory Agency Authority"),
        ("other", "Other Inbound Channel"),
    )

    SEVERITY_CHOICES = (
        ("critical_safety", "Critical Safety / Health Hazard"),
        ("major_malfunction", "Major Functional Malfunction"),
        ("minor_cosmetic", "Minor Cosmetic / Packaging"),
        ("service_inconvenience", "Service / Documentation Issue"),
        ("unspecified", "Unspecified / Pending Triage"),
    )

    COMPLAINT_STATUS_CHOICES = (
        ("intake_received", "Intake Received / Open"),
        ("under_triage", "Under Triage Review"),
        ("under_investigation", "Under Active Investigation"),
        ("pending_regulatory", "Pending Regulatory Action"),
        ("capa_pending", "Pending CAPA / NCR Actions"),
        ("resolved", "Resolved / Pending QA Closure"),
        ("closed", "Closed"),
        ("cancelled", "Cancelled / Invalid"),
    )

    VALIDITY_CHOICES = (
        ("pending_triage", "Pending Triage Determination"),
        ("valid_complaint", "Confirmed Valid Quality Complaint"),
        ("invalid_allegation", "Invalid / Unsubstantiated Allegation"),
        ("commercial_inquiry", "Commercial / Pricing Inquiry (Not Quality)"),
    )

    REPORTABILITY_CHOICES = (
        ("undetermined", "Undetermined (Screening Open)"),
        ("reportable_event", "Mandatory Reportable Adverse Event"),
        ("non_reportable", "Non-Reportable (QA Justified)"),
        ("exempt", "Exempt from Regulatory Reporting"),
    )

    SAMPLE_RETURN_STATUS_CHOICES = (
        ("not_requested", "Sample Not Requested"),
        ("requested_pending", "Sample Requested (Pending Return)"),
        ("sample_received", "Sample Received in Lab"),
        ("sample_destroyed", "Sample Destroyed / Retained"),
        ("customer_declined", "Customer Declined / Unable to Return"),
    )

    SEVERITY_CSS = {
        "critical_safety": "badge-red",
        "major_malfunction": "badge-amber",
        "minor_cosmetic": "badge-info",
        "service_inconvenience": "badge-slate",
        "unspecified": "badge-muted",
    }

    STATUS_CSS = {
        "intake_received": "badge-info",
        "under_triage": "badge-amber",
        "under_investigation": "badge-amber",
        "pending_regulatory": "badge-red",
        "capa_pending": "badge-amber",
        "resolved": "badge-green",
        "closed": "badge-muted",
        "cancelled": "badge-slate",
    }

    VALIDITY_CSS = {
        "pending_triage": "badge-amber",
        "valid_complaint": "badge-green",
        "invalid_allegation": "badge-slate",
        "commercial_inquiry": "badge-info",
    }

    REPORTABILITY_CSS = {
        "undetermined": "badge-amber",
        "reportable_event": "badge-red",
        "non_reportable": "badge-green",
        "exempt": "badge-muted",
    }

    title = models.CharField(max_length=255, help_text="Headline summary of customer allegation")
    intake_channel = models.CharField(max_length=30, choices=INTAKE_CHANNEL_CHOICES, default="email", db_index=True)
    customer = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_complaints",
        help_text="Complainant customer or hospital facility (core.Party)",
    )
    complainant_name = models.CharField(max_length=128, help_text="Contact person, reporter, or patient representative")
    complainant_email = models.CharField(max_length=128, blank=True, help_text="Complainant contact email")
    complainant_phone = models.CharField(max_length=64, blank=True, help_text="Complainant phone number")
    complainant_organization = models.CharField(max_length=128, blank=True, help_text="Facility, hospital, clinic, or institution name")

    sales_order = models.ForeignKey(
        "scm.SalesOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaints",
        help_text="Associated sales order",
    )
    item_code = models.CharField(max_length=100, db_index=True, help_text="Product catalog number / SKU")
    item_name = models.CharField(max_length=255, help_text="Commercial product name")
    lot_number = models.CharField(max_length=100, db_index=True, blank=True, help_text="Batch / lot number")
    serial_number = models.CharField(max_length=100, db_index=True, blank=True, help_text="Unit serial number")
    udi_di_number = models.CharField(max_length=100, blank=True, help_text="Unique Device Identification (UDI-DI / GTIN)")

    date_received = models.DateField(db_index=True, help_text="Date complaint was received by company")
    date_of_occurrence = models.DateField(null=True, blank=True, help_text="Date event occurred at user facility")
    problem_description = models.TextField(help_text="Detailed narrative of customer allegation or product malfunction")

    patient_involved = models.BooleanField(default=False, help_text="Was a patient or end-user directly involved in the event?")
    adverse_event_alleged = models.BooleanField(default=False, help_text="Did the event involve death, injury, or severe medical intervention?")
    severity = models.CharField(max_length=30, choices=SEVERITY_CHOICES, default="unspecified", db_index=True)
    status = models.CharField(max_length=30, choices=COMPLAINT_STATUS_CHOICES, default="intake_received", db_index=True)
    validity = models.CharField(max_length=30, choices=VALIDITY_CHOICES, default="pending_triage", db_index=True)
    reportability = models.CharField(max_length=30, choices=REPORTABILITY_CHOICES, default="undetermined", db_index=True)
    non_reportable_justification = models.TextField(
        blank=True,
        help_text="Mandatory regulatory rationale if determined non-reportable (21 CFR 820.198(a)(3))",
    )
    complaint_category = models.CharField(max_length=100, blank=True, db_index=True, help_text="Failure code e.g. 'Leakage', 'Broken Seal', 'Display Error'")

    sample_return_status = models.CharField(max_length=30, choices=SAMPLE_RETURN_STATUS_CHOICES, default="not_requested", db_index=True)
    return_authorization = models.ForeignKey(
        "scm.ReturnAuthorization",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaints",
        help_text="Linked RMA record",
    )
    sample_tracking_number = models.CharField(max_length=100, blank=True, help_text="Carrier tracking number for returned specimen")
    sample_received_date = models.DateField(null=True, blank=True, help_text="Date physical sample reached analysis laboratory")

    triage_notes = models.TextField(blank=True, help_text="Initial QA triage findings and next step assignments")
    triaged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triaged_complaints",
    )
    triaged_at = models.DateTimeField(null=True, blank=True)

    investigation_required = models.BooleanField(default=True, help_text="Is formal failure analysis / DHR investigation required?")
    no_investigation_rationale = models.TextField(blank=True, help_text="Regulatory justification if formal investigation was bypassed")

    resolution_summary = models.TextField(blank=True, help_text="Customer-facing resolution and corrective summary")
    customer_letter_sent = models.BooleanField(default=False)
    customer_letter_date = models.DateField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="closed_complaints",
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_complaints",
    )

    class Meta:
        ordering = ["-date_received", "-created_at"]
        verbose_name = "Customer Complaint"
        verbose_name_plural = "Customer Complaints"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qcmp_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qcmp_ten_status"),
            models.Index(fields=["tenant", "customer"], name="idx_qcmp_ten_cust"),
            models.Index(fields=["tenant", "intake_channel"], name="idx_qcmp_ten_chan"),
            models.Index(fields=["tenant", "severity"], name="idx_qcmp_ten_sev"),
            models.Index(fields=["tenant", "reportability"], name="idx_qcmp_ten_rep"),
            models.Index(fields=["tenant", "validity"], name="idx_qcmp_ten_val"),
            models.Index(fields=["tenant", "item_code"], name="idx_qcmp_ten_item"),
            models.Index(fields=["tenant", "lot_number"], name="idx_qcmp_ten_lot"),
            models.Index(fields=["tenant", "date_received"], name="idx_qcmp_ten_drcv"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qcmp_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title}"

    @property
    def days_open(self):
        end = self.closed_at.date() if self.closed_at else timezone.now().date()
        if self.date_received:
            return (end - self.date_received).days
        return 0

    @property
    def has_active_regulatory_report(self):
        return self.regulatory_reports.exclude(submission_status__in=["acknowledged", "withdrawn"]).exists()

    @property
    def is_overdue(self):
        if self.status in ["closed", "cancelled", "resolved"]:
            return False
        return self.days_open > 30
