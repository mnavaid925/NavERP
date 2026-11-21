from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class SafetyIncident(TenantNumbered):
    NUMBER_PREFIX = "QSIR"

    INCIDENT_TYPE_CHOICES = [
        ("injury_illness", "Occupational Injury / Illness"),
        ("near_miss", "Near-Miss Event"),
        ("hazardous_condition", "Hazardous Condition / Safety Hazard"),
        ("chemical_spill", "Chemical Spill / Hazmat Release"),
        ("fire_explosion", "Fire / Explosion"),
        ("property_damage", "Equipment / Property Damage"),
        ("cleanroom_breach", "Cleanroom Biocontainment / Protocol Breach"),
    ]

    SEVERITY_CHOICES = [
        ("minor", "Minor (First Aid / No Lost Time)"),
        ("moderate", "Moderate (Medical Treatment / Restricted)"),
        ("severe", "Severe (Lost Time / Inpatient)"),
        ("critical", "Critical (Amputation / Life Threatening)"),
        ("fatal", "Fatal (Fatality)"),
    ]

    STATUS_CHOICES = [
        ("reported", "Reported"),
        ("investigating", "Under Investigation"),
        ("under_review", "Under Review"),
        ("capa_pending", "CAPA Pending"),
        ("closed", "Closed"),
        ("cancelled", "Cancelled / Void"),
    ]

    AFFECTED_PARTY_TYPE_CHOICES = [
        ("employee", "Direct Company Employee"),
        ("contractor", "On-Site Contractor"),
        ("visitor", "Visitor / Guest"),
        ("temporary_worker", "Temporary / Agency Worker"),
    ]

    NATURE_OF_INJURY_CHOICES = [
        ("none", "None / Near-Miss"),
        ("strain_sprain", "Strain / Sprain"),
        ("laceration_cut", "Laceration / Cut / Puncture"),
        ("burn_heat_chemical", "Burn (Thermal / Chemical)"),
        ("fracture", "Fracture / Dislocation"),
        ("contusion_bruise", "Contusion / Bruise / Crush"),
        ("eye_injury", "Eye Injury / Foreign Body"),
        ("inhalation_respiratory", "Chemical Inhalation / Respiratory"),
        ("skin_irritation", "Dermatitis / Skin Irritation"),
        ("hearing_impact", "Acoustic Trauma / Hearing Impact"),
        ("other", "Other Specified Injury"),
    ]

    BODY_PART_CHOICES = [
        ("none", "None / Not Applicable"),
        ("head_face", "Head / Face"),
        ("eyes", "Eyes"),
        ("hands_fingers", "Hands / Fingers / Wrists"),
        ("arms_shoulders", "Arms / Shoulders"),
        ("back_spine", "Back / Spine"),
        ("legs_knees", "Legs / Knees"),
        ("feet_toes", "Feet / Toes"),
        ("respiratory_system", "Respiratory System / Lungs"),
        ("multiple", "Multiple Body Systems"),
    ]

    MEDICAL_TREATMENT_LEVEL_CHOICES = [
        ("none", "None Required"),
        ("first_aid_only", "First Aid On-Site Only"),
        ("clinic_visit", "Occupational Clinic / Urgent Care"),
        ("emergency_room", "Hospital Emergency Department"),
        ("hospitalization", "Inpatient Hospitalization"),
    ]

    OSHA_CLASSIFICATION_CHOICES = [
        ("non_recordable", "Non-Recordable Event"),
        ("first_aid", "First Aid Only (Non-Recordable)"),
        ("days_away_from_work", "Death or Days Away From Work"),
        ("job_transfer_restriction", "Job Transfer or Work Restriction"),
        ("other_recordable_case", "Other Recordable Case"),
    ]

    PPE_COMPLIANCE_CHOICES = [
        ("compliant", "Fully Compliant with Required PPE"),
        ("non_compliant", "Required PPE Not Worn"),
        ("inadequate_ppe", "PPE Worn Was Inadequate for Hazard"),
        ("not_applicable", "No Specific PPE Mandated"),
    ]

    ROOT_CAUSE_CATEGORY_CHOICES = [
        ("human_factors", "Human Factors / Unsafe Behavior"),
        ("equipment_failure", "Equipment / Tooling Failure"),
        ("procedure_gap", "SOP / Procedure Deficient or Missing"),
        ("training_deficiency", "Training / Competency Gap"),
        ("ergonomic_strain", "Ergonomic Stress / Repetitive Motion"),
        ("environmental_hazard", "Slip/Trip Hazard / Lighting / Noise"),
        ("inadequate_ppe", "Defective or Inappropriate PPE"),
        ("under_investigation", "Under Root Cause Investigation"),
    ]

    STATUS_CSS = {
        "reported": "badge-info",
        "investigating": "badge-amber",
        "under_review": "badge-amber",
        "capa_pending": "badge-red",
        "closed": "badge-green",
        "cancelled": "badge-muted",
    }

    SEVERITY_CSS = {
        "minor": "badge-slate",
        "moderate": "badge-info",
        "severe": "badge-amber",
        "critical": "badge-red",
        "fatal": "badge-red",
    }

    title = models.CharField(max_length=255, help_text="Concise incident title e.g. Chemical splash during acid etching")
    incident_date = models.DateTimeField(db_index=True, help_text="Exact timestamp of incident occurrence")
    report_date = models.DateField(db_index=True, default=timezone.now, help_text="Date initial report was submitted")
    incident_type = models.CharField(max_length=30, choices=INCIDENT_TYPE_CHOICES, default="injury_illness", db_index=True)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default="minor", db_index=True)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="reported", db_index=True)

    org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="safety_incidents",
        help_text="Facility, manufacturing line, or department where incident occurred",
    )
    location_details = models.CharField(max_length=255, blank=True, help_text="Specific physical location (e.g. Cleanroom B Airlock 3)")

    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reported_safety_incidents",
        help_text="Person submitting first report of incident",
    )
    affected_person = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="involved_safety_incidents",
        help_text="Affected employee (if company employee)",
    )
    affected_party_name = models.CharField(max_length=255, blank=True, help_text="Name of affected person if contractor, visitor, or non-user")
    affected_party_type = models.CharField(max_length=30, choices=AFFECTED_PARTY_TYPE_CHOICES, default="employee", db_index=True)

    nature_of_injury = models.CharField(max_length=35, choices=NATURE_OF_INJURY_CHOICES, default="none", db_index=True)
    body_part_affected = models.CharField(max_length=30, choices=BODY_PART_CHOICES, default="none")
    medical_treatment_level = models.CharField(max_length=30, choices=MEDICAL_TREATMENT_LEVEL_CHOICES, default="none", db_index=True)

    is_osha_recordable = models.BooleanField(default=False, db_index=True, help_text="Meets OSHA 29 CFR 1904 recordability criteria")
    osha_classification = models.CharField(max_length=35, choices=OSHA_CLASSIFICATION_CHOICES, default="non_recordable", db_index=True)
    lost_workdays_count = models.PositiveIntegerField(default=0, help_text="Number of full days away from work")
    restricted_workdays_count = models.PositiveIntegerField(default=0, help_text="Number of days restricted duty or job transfer")
    date_returned_to_work = models.DateField(null=True, blank=True, help_text="Date worker returned to full duty without restriction")

    ppe_compliance_status = models.CharField(max_length=25, choices=PPE_COMPLIANCE_CHOICES, default="compliant", db_index=True)
    ppe_notes = models.TextField(blank=True, help_text="Observations on PPE condition, fitting, or compliance")
    immediate_actions_taken = models.TextField(blank=True, help_text="Immediate emergency medical aid, evacuation, equipment lock-out, or containment")

    lead_investigator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="investigated_safety_incidents",
        help_text="Safety officer or supervisor leading root cause investigation",
    )
    root_cause_category = models.CharField(max_length=35, choices=ROOT_CAUSE_CATEGORY_CHOICES, default="under_investigation", db_index=True)
    investigation_findings = models.TextField(blank=True, help_text="Detailed root cause analysis narrative and sequence of events")

    capa_investigation = models.ForeignKey(
        "quality.CapaInvestigation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="safety_incidents",
        help_text="Linked formal CAPA investigation spawned from incident",
    )
    non_conformance_report = models.ForeignKey(
        "quality.NonConformanceReport",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="safety_incidents",
        help_text="Linked Non-Conformance Report for material/facility containment",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-incident_date", "-created_at"]
        verbose_name = "Safety Incident"
        verbose_name_plural = "Safety Incidents"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qsir_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qsir_ten_status"),
            models.Index(fields=["tenant", "incident_type"], name="idx_qsir_ten_type"),
            models.Index(fields=["tenant", "severity"], name="idx_qsir_ten_sev"),
            models.Index(fields=["tenant", "is_osha_recordable"], name="idx_qsir_ten_osha"),
            models.Index(fields=["tenant", "incident_date"], name="idx_qsir_ten_date"),
            models.Index(fields=["tenant", "org_unit"], name="idx_qsir_ten_org"),
            models.Index(fields=["tenant", "reported_by"], name="idx_qsir_ten_rep"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qsir_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"

    @property
    def is_dart_incident(self):
        return (self.lost_workdays_count > 0) or (self.restricted_workdays_count > 0)

    @property
    def total_lost_and_restricted_days(self):
        return self.lost_workdays_count + self.restricted_workdays_count

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def severity_css(self):
        return self.SEVERITY_CSS.get(self.severity, "badge-slate")

    @property
    def osha_css(self):
        return "badge-red" if self.is_osha_recordable else "badge-slate"

    @property
    def affected_person_display(self):
        if self.affected_person:
            return self.affected_person.get_full_name() or self.affected_person.username
        if self.affected_party_name:
            return f"{self.affected_party_name} ({self.get_affected_party_type_display()})"
        return "Not specified"
