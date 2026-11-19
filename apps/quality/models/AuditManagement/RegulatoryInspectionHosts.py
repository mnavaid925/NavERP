from django.conf import settings
from django.db import models

from apps.quality.models._base import TenantNumbered


class RegulatoryInspectionHost(TenantNumbered):
    NUMBER_PREFIX = "QHST"

    AGENCY_CHOICES = (
        ("fda_cdrh", "US FDA - CDRH (Medical Devices)"),
        ("fda_cder", "US FDA - CDER (Pharmaceuticals)"),
        ("iso_notified_body", "EU Notified Body (MDR/IVDR)"),
        ("ema_eu", "European Medicines Agency (EMA)"),
        ("health_canada", "Health Canada"),
        ("pmda_japan", "PMDA Japan"),
        ("customer_corporate", "Customer Corporate Quality Audit"),
        ("iso_registrar", "ISO Accredited Registrar"),
        ("other_authority", "Other Regulatory / Health Authority"),
    )

    PURPOSE_CHOICES = (
        ("routine_surveillance", "Routine cGMP / QMS Surveillance"),
        ("pre_approval_pma_nda", "Pre-Approval Inspection (PAI / PMA)"),
        ("for_cause_directed", "For-Cause / Directed Investigation"),
        ("unannounced_inspection", "Unannounced Facility Inspection"),
        ("mdsap_audit", "MDSAP Comprehensive Audit"),
        ("recertification_audit", "Triennial Recertification Audit"),
    )

    ANNOUNCEMENT_CHOICES = (
        ("announced", "Announced"),
        ("unannounced", "Unannounced"),
        ("short_notice", "Short Notice (< 48 Hours)"),
    )

    STATUS_CHOICES = (
        ("preparation", "Pre-Inspection Preparation"),
        ("active_inspection", "Active Inspection In Session"),
        ("daily_wrapup", "Daily Debrief / Wrap-up"),
        ("inspection_closed", "Inspection Closed / Exit Complete"),
        ("post_inspection_followup", "Post-Inspection Response Tracking"),
    )

    OUTCOME_CHOICES = (
        ("pending", "Pending Final Agency Classification"),
        ("nai_no_action_indicated", "NAI - No Action Indicated"),
        ("vai_voluntary_action_indicated", "VAI - Voluntary Action Indicated"),
        ("oai_official_action_indicated", "OAI - Official Action Indicated"),
        ("certified_unconditional", "Unconditional Certification / Clearance"),
        ("conditional_clearance", "Conditional Clearance / Action Plan Required"),
        ("refusal_warning_letter", "Warning Letter / Certification Refused"),
    )

    AGENCY_CSS = {
        "fda_cdrh": "badge-red",
        "fda_cder": "badge-red",
        "iso_notified_body": "badge-amber",
        "ema_eu": "badge-info",
        "health_canada": "badge-info",
        "pmda_japan": "badge-info",
        "customer_corporate": "badge-slate",
        "iso_registrar": "badge-amber",
        "other_authority": "badge-muted",
    }

    STATUS_CSS = {
        "preparation": "badge-slate",
        "active_inspection": "badge-amber",
        "daily_wrapup": "badge-info",
        "inspection_closed": "badge-green",
        "post_inspection_followup": "badge-muted",
    }

    OUTCOME_CSS = {
        "pending": "badge-muted",
        "nai_no_action_indicated": "badge-green",
        "vai_voluntary_action_indicated": "badge-amber",
        "oai_official_action_indicated": "badge-red",
        "certified_unconditional": "badge-green",
        "conditional_clearance": "badge-amber",
        "refusal_warning_letter": "badge-red",
    }

    audit = models.ForeignKey(
        "quality.QualityAudit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="regulatory_hosts",
        help_text="Linked QualityAudit record",
    )
    inspection_title = models.CharField(max_length=255, help_text="e.g. FDA cGMP / QSIT Inspection - Medical Device Facility")
    agency_or_body = models.CharField(max_length=32, choices=AGENCY_CHOICES, default="fda_cdrh", db_index=True)
    agency_name = models.CharField(max_length=128, help_text="Official body name e.g. US FDA - District Office, TÜV SÜD Product Service")
    lead_inspector_name = models.CharField(max_length=128, help_text="Lead inspector / investigator name")
    inspector_credentials = models.CharField(max_length=128, blank=True, help_text="Badge number, division, or contact identifier")

    inspection_purpose = models.CharField(max_length=32, choices=PURPOSE_CHOICES, default="routine_surveillance", db_index=True)
    announcement_status = models.CharField(max_length=24, choices=ANNOUNCEMENT_CHOICES, default="announced", db_index=True)

    scheduled_start_date = models.DateField(db_index=True)
    scheduled_end_date = models.DateField()
    actual_start_date = models.DateField(null=True, blank=True)
    actual_end_date = models.DateField(null=True, blank=True)

    front_room_lead = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="hosted_front_rooms",
        help_text="Primary company spokesperson / Front Room facilitator",
    )
    back_room_lead = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="managed_back_rooms",
        help_text="Back Room document staging & SME coordinator",
    )
    scribe_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scribed_inspections",
        help_text="Official inspection scribe and request logger",
    )

    war_room_location = models.CharField(max_length=255, help_text="Staging conference room or secure virtual bridge URL")
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="preparation", db_index=True)

    requests_logged_count = models.PositiveIntegerField(default=0, help_text="Count of records/documents requested by inspectors")
    requests_fulfilled_count = models.PositiveIntegerField(default=0, help_text="Count of requests successfully fulfilled")

    form_483_issued = models.BooleanField(default=False, help_text="Whether FDA Form 483 / Inspectional Observations was issued")
    observations_count = models.PositiveIntegerField(default=0, help_text="Number of formal inspection observations / Form 483 citations")

    formal_outcome = models.CharField(max_length=36, choices=OUTCOME_CHOICES, default="pending", db_index=True)

    daily_summary_notes = models.TextField(blank=True, help_text="Daily debrief log, inspector questions, and SME interview notes")
    closeout_memo = models.TextField(blank=True, help_text="Exit conference debrief, commitments, and executive response plan")

    class Meta:
        ordering = ["-scheduled_start_date", "-created_at"]
        verbose_name = "Regulatory Inspection Host Record"
        verbose_name_plural = "Regulatory Inspection Host Records"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qhst_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qhst_ten_status"),
            models.Index(fields=["tenant", "agency_or_body"], name="idx_qhst_ten_agency"),
            models.Index(fields=["tenant", "formal_outcome"], name="idx_qhst_ten_out"),
            models.Index(fields=["tenant", "audit"], name="idx_qhst_ten_audit"),
            models.Index(fields=["tenant", "scheduled_start_date"], name="idx_qhst_ten_sched"),
            models.Index(fields=["tenant", "front_room_lead"], name="idx_qhst_ten_flead"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qhst_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} - {self.agency_name} ({self.inspection_title})"

    @property
    def fulfillment_rate(self):
        if self.requests_logged_count == 0:
            return 100
        return int((self.requests_fulfilled_count / self.requests_logged_count) * 100)

    @property
    def is_active(self):
        return self.status in ("active_inspection", "daily_wrapup")

    @property
    def pending_requests_count(self):
        return max(0, self.requests_logged_count - self.requests_fulfilled_count)
