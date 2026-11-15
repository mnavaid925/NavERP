"""Vehicle Driver Assignment, Qualification & Safety model (11.19)."""

from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class VehicleDriverAssignment(TenantNumbered):
    """Driver assignment records, licensing qualifications, safety scores, and duty logs [VDRV]."""

    NUMBER_PREFIX = "VDRV"

    ASSIGNMENT_ROLE_CHOICES = [
        ("primary_assigned", "Primary Assigned Driver"),
        ("secondary_relief", "Secondary / Relief Driver"),
        ("temporary_loaner", "Temporary Loaner Driver"),
        ("pool_driver", "Motor Pool Dispatch Driver"),
    ]

    STATUS_CHOICES = [
        ("active", "Active Assignment"),
        ("completed", "Completed / Returned"),
        ("revoked_safety", "Revoked for Safety"),
        ("transferred", "Transferred"),
    ]

    LICENSE_CLASS_CHOICES = [
        ("class_a_cdl", "Class A Commercial (CDL-A)"),
        ("class_b_cdl", "Class B Commercial (CDL-B)"),
        ("class_c_cdl", "Class C Commercial (CDL-C)"),
        ("standard_non_cdl", "Standard Driver License (Class D/Non-CDL)"),
    ]

    QUALIFICATION_STATUS_CHOICES = [
        ("qualified", "Qualified & Cleared"),
        ("expiring_soon", "License / Medical Expiring Soon"),
        ("expired_disqualified", "Disqualified / Expired Credentials"),
        ("suspended", "Suspended Safety Standing"),
    ]

    DUTY_STATUS_CHOICES = [
        ("off_duty", "Off Duty"),
        ("sleeper_berth", "Sleeper Berth"),
        ("driving", "Driving"),
        ("on_duty_not_driving", "On Duty (Not Driving)"),
    ]

    SAFETY_TIER_CHOICES = [
        ("exemplary", "Exemplary (90-100)"),
        ("good", "Good (80-89)"),
        ("needs_coaching", "Needs Coaching (65-79)"),
        ("high_risk", "High Risk (<65)"),
    ]

    STATUS_CSS = {
        "active": "badge-green",
        "completed": "badge-slate",
        "revoked_safety": "badge-red",
        "transferred": "badge-info",
    }

    QUALIFICATION_CSS = {
        "qualified": "badge-green",
        "expiring_soon": "badge-amber",
        "expired_disqualified": "badge-red",
        "suspended": "badge-red",
    }

    SAFETY_TIER_CSS = {
        "exemplary": "badge-green",
        "good": "badge-info",
        "needs_coaching": "badge-amber",
        "high_risk": "badge-red",
    }

    DUTY_STATUS_CSS = {
        "off_duty": "badge-slate",
        "sleeper_berth": "badge-info",
        "driving": "badge-green",
        "on_duty_not_driving": "badge-amber",
    }

    vehicle = models.ForeignKey(
        "assets.FleetVehicle",
        on_delete=models.CASCADE,
        related_name="driver_assignments",
        help_text="Assigned fleet vehicle",
    )
    driver = models.ForeignKey(
        "hrm.EmployeeProfile",
        on_delete=models.CASCADE,
        related_name="vehicle_driver_assignments",
        help_text="Assigned employee driver profile",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_vehicle_records",
        help_text="Optional login user account associated with driver",
    )
    assignment_role = models.CharField(max_length=24, choices=ASSIGNMENT_ROLE_CHOICES, default="primary_assigned")
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="active")
    start_datetime = models.DateTimeField(default=timezone.now)
    end_datetime = models.DateTimeField(null=True, blank=True)
    start_odometer = models.PositiveIntegerField(default=0, help_text="Odometer reading when vehicle was checked out")
    end_odometer = models.PositiveIntegerField(null=True, blank=True, help_text="Odometer reading when vehicle was returned")

    # Qualification & License credentials
    driver_license_number = models.CharField(max_length=48, blank=True)
    driver_license_state = models.CharField(max_length=32, blank=True)
    license_class = models.CharField(max_length=24, choices=LICENSE_CLASS_CHOICES, default="standard_non_cdl")
    license_expiration_date = models.DateField(null=True, blank=True)
    medical_card_expiration_date = models.DateField(null=True, blank=True, help_text="DOT Medical Examiner Certificate expiration")
    hazmat_endorsed = models.BooleanField(default=False)
    qualification_status = models.CharField(max_length=28, choices=QUALIFICATION_STATUS_CHOICES, default="qualified")

    # Safety metrics and HOS
    safety_score = models.PositiveSmallIntegerField(
        default=100,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Telematics calculated driver safety index (0–100)",
    )
    speeding_event_count = models.PositiveIntegerField(default=0)
    harsh_braking_count = models.PositiveIntegerField(default=0)
    harsh_acceleration_count = models.PositiveIntegerField(default=0)
    incident_count = models.PositiveIntegerField(default=0)
    duty_status = models.CharField(max_length=24, choices=DUTY_STATUS_CHOICES, default="off_duty")
    safety_tier = models.CharField(max_length=20, choices=SAFETY_TIER_CHOICES, default="exemplary")
    supervisor_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-start_datetime", "-number"]
        verbose_name = "Vehicle Driver Assignment"
        verbose_name_plural = "Vehicle Driver Assignments"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="assets_vdrv_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_vdrv_ten_stat"),
            models.Index(fields=["tenant", "vehicle", "status"], name="idx_vdrv_ten_veh_stat"),
            models.Index(fields=["tenant", "driver", "status"], name="idx_vdrv_ten_drv_stat"),
            models.Index(fields=["tenant", "safety_tier"], name="idx_vdrv_ten_stier"),
        ]

    def __str__(self):
        return f"{self.number} — {self.driver} -> {self.vehicle.name}"

    def clean(self):
        super().clean()
        if self.end_datetime and self.start_datetime and self.end_datetime < self.start_datetime:
            raise ValidationError({"end_datetime": "Assignment end datetime cannot precede start datetime."})
        if self.end_odometer is not None and self.start_odometer is not None and self.end_odometer < self.start_odometer:
            raise ValidationError({"end_odometer": "Ending odometer cannot be less than starting odometer."})

    def refresh_qualification_status(self, today=None):
        if today is None:
            today = timezone.now().date()
        if self.qualification_status == "suspended":
            return
        if (self.license_expiration_date and self.license_expiration_date < today) or (
            self.medical_card_expiration_date and self.medical_card_expiration_date < today
        ):
            self.qualification_status = "expired_disqualified"
        elif (self.license_expiration_date and self.license_expiration_date <= today + timedelta(days=30)) or (
            self.medical_card_expiration_date and self.medical_card_expiration_date <= today + timedelta(days=30)
        ):
            self.qualification_status = "expiring_soon"
        else:
            self.qualification_status = "qualified"

    def refresh_safety_tier(self):
        if self.safety_score >= 90:
            self.safety_tier = "exemplary"
        elif self.safety_score >= 80:
            self.safety_tier = "good"
        elif self.safety_score >= 65:
            self.safety_tier = "needs_coaching"
        else:
            self.safety_tier = "high_risk"

    def save(self, *args, **kwargs):
        self.refresh_qualification_status()
        self.refresh_safety_tier()
        super().save(*args, **kwargs)

    @property
    def is_license_expired(self):
        if not self.license_expiration_date:
            return False
        return self.license_expiration_date < timezone.now().date()

    @property
    def is_license_expiring_soon(self):
        if not self.license_expiration_date:
            return False
        today = timezone.now().date()
        return today <= self.license_expiration_date <= today + timedelta(days=30)

    @property
    def is_medical_expired(self):
        if not self.medical_card_expiration_date:
            return False
        return self.medical_card_expiration_date < timezone.now().date()

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def qualification_badge_class(self):
        return self.QUALIFICATION_CSS.get(self.qualification_status, "badge-slate")

    @property
    def safety_tier_badge_class(self):
        return self.SAFETY_TIER_CSS.get(self.safety_tier, "badge-slate")

    @property
    def duty_status_badge_class(self):
        return self.DUTY_STATUS_CSS.get(self.duty_status, "badge-slate")
