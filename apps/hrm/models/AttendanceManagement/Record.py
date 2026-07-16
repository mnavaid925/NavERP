"""HRM 3.9 Attendance Management — Record models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class AttendanceRecord(TenantNumbered):
    """A daily attendance entry per employee (3.9). ``hours_worked`` is recomputed in ``save()``
    from check-in/out (handling an overnight shift), never hand-edited on the form."""

    NUMBER_PREFIX = "ATT"

    STATUS_CHOICES = [
        ("present", "Present"),
        ("absent", "Absent"),
        ("half_day", "Half Day"),
        ("on_leave", "On Leave"),
        ("holiday", "Holiday"),
        ("regularized", "Regularized"),
    ]
    SOURCE_CHOICES = [
        ("web", "Web"),
        ("mobile", "Mobile App"),
        ("biometric", "Biometric"),
        ("manual", "Manual Entry"),
    ]

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="attendance_records")
    date = models.DateField()
    check_in = models.TimeField(null=True, blank=True)
    check_out = models.TimeField(null=True, blank=True)
    hours_worked = models.DecimalField(max_digits=5, decimal_places=2, default=0, editable=False)
    shift = models.ForeignKey("hrm.Shift", on_delete=models.SET_NULL, null=True, blank=True, related_name="attendance_records")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="present")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="web")
    # Geofencing (3.9): GPS coordinates captured at the punch + the zone it is checked against.
    # ``is_within_geofence`` (verified/outside/unknown) is DERIVED via ``geo_status()`` — not stored.
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True,
                                   validators=[MinValueValidator(Decimal("-90")), MaxValueValidator(Decimal("90"))])
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True,
                                    validators=[MinValueValidator(Decimal("-180")), MaxValueValidator(Decimal("180"))])
    geofence = models.ForeignKey("hrm.GeoFence", on_delete=models.SET_NULL, null=True, blank=True, related_name="attendance_records")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date"]
        unique_together = [("tenant", "number"), ("tenant", "employee", "date")]
        indexes = [
            models.Index(fields=["tenant", "employee", "date"], name="hrm_att_tenant_emp_date_idx"),
            models.Index(fields=["tenant", "date", "status"], name="hrm_att_tenant_date_stat_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_att_tenant_status_idx"),
            # Geofence-scoped lookups: geofence_detail's recent-punches list + geofence_delete's guard.
            models.Index(fields=["tenant", "geofence"], name="hrm_att_tenant_geofence_idx"),
        ]

    def _recompute_hours(self):
        if self.check_in and self.check_out:
            ci = datetime.combine(date.min, self.check_in)
            co = datetime.combine(date.min, self.check_out)
            seconds = (co - ci).total_seconds()
            if seconds < 0:  # overnight shift — check-out is the next calendar day
                seconds += 24 * 3600
            self.hours_worked = (Decimal(seconds) / Decimal(3600)).quantize(Decimal("0.01"))
        else:
            self.hours_worked = ZERO

    def is_late(self):
        """True when check-in is past the shift start + grace window (display-only helper).
        Compared in minutes-of-day to stay platform-safe (no epoch conversion)."""
        if not (self.check_in and self.shift_id and self.shift and self.shift.start_time):
            return False
        start_min = self.shift.start_time.hour * 60 + self.shift.start_time.minute
        check_in_min = self.check_in.hour * 60 + self.check_in.minute
        return check_in_min > start_min + self.shift.grace_minutes

    def has_geo(self):
        """True when a GPS coordinate pair was captured for this punch."""
        return self.latitude is not None and self.longitude is not None

    def geo_status(self):
        """DERIVED geofence verification for display/reporting (never stored):
        ``"verified"`` inside the linked zone, ``"outside"`` beyond its radius, ``""`` when
        there is no coordinate pair or no zone to check against. Evaluated against the zone's
        live radius regardless of ``is_active`` — a punch reflects where it happened."""
        if not (self.has_geo() and self.geofence_id and self.geofence):
            return ""
        return "verified" if self.geofence.contains(self.latitude, self.longitude) else "outside"

    def clean(self):
        super().clean()
        # GPS coordinates are a pair (both or neither); a geofence needs coordinates to check against.
        if (self.latitude is None) != (self.longitude is None):
            raise ValidationError({"longitude": "Provide both latitude and longitude, or neither."})
        if self.geofence_id and self.latitude is None:
            raise ValidationError({"geofence": "Set the punch coordinates to check against this geofence."})

    def save(self, *args, **kwargs):
        self._recompute_hours()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} · {self.employee} · {self.date} · {self.get_status_display()}"
