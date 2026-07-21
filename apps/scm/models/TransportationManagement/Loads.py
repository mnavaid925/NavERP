"""SCM 4.6 Transportation Management System — Load + LoadStop models.

A **load** is the trip/route execution unit that consolidates one or more customer-facing
``Shipment``s onto one truck/route — the "freight order" every enterprise TMS keeps distinct from the
"shipment order". It carries the route (an ordered list of ``LoadStop``s), the equipment capacity,
and the **cube-utilization** headline.

Load Optimization here is the *aggregate* capacity-vs-planned calculation, not true 3D bin-packing:
``weight_utilization_pct`` / ``volume_utilization_pct`` are DERIVED properties over the assigned
shipments' weight/volume against the equipment capacity — never stored, so they can never go stale.
The detail view computes the planned totals in ONE aggregate; the list view annotates the same sums,
so no page re-queries per row.
"""
from apps.scm.models._base import *  # noqa: F401,F403
from apps.scm.models.TransportationManagement.Carriers import EQUIPMENT_CHOICES, MODE_CHOICES


class Load(TenantNumbered):
    """A planned/executed trip [LD-] carrying consolidated shipments over a sequence of stops."""

    NUMBER_PREFIX = "LD"

    STATUS_CHOICES = [
        ("planning", "Planning"),
        ("tendered", "Tendered"),
        ("booked", "Booked"),
        ("in_transit", "In Transit"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    ]
    EDITABLE_STATUSES = ("planning", "tendered")
    CLOSED_STATUSES = ("delivered", "cancelled")

    carrier = models.ForeignKey("scm.Carrier", on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="loads", help_text="Assigned once tendered/booked")
    mode = models.CharField(max_length=12, choices=MODE_CHOICES, default="truckload")
    equipment_type = models.CharField(max_length=12, choices=EQUIPMENT_CHOICES, default="dry_van")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="planning", editable=False)
    origin_text = models.CharField(max_length=255, blank=True,
                                   help_text="Origin (free text — not every dock has a Party address)")
    destination_text = models.CharField(max_length=255, blank=True, help_text="Final destination")
    planned_departure = models.DateTimeField(null=True, blank=True)
    planned_arrival = models.DateTimeField(null=True, blank=True)
    # Stamped by the dispatch/deliver actions, never typed — kept off the form.
    actual_departure = models.DateTimeField(null=True, blank=True, editable=False)
    actual_arrival = models.DateTimeField(null=True, blank=True, editable=False)
    distance_km = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                      validators=[MinValueValidator(ZERO)],
                                      help_text="Route distance (stored estimate — no live routing engine)")
    estimated_fuel_cost = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                              validators=[MinValueValidator(ZERO)])
    freight_cost_estimate = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                                validators=[MinValueValidator(ZERO)])
    # Equipment capacity feeds the cube-utilization calc. Plain fields (no equipment-spec master yet).
    equipment_capacity_weight_kg = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                                       validators=[MinValueValidator(ZERO)])
    equipment_capacity_volume_cbm = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True,
                                                        validators=[MinValueValidator(ZERO)])
    driver_name = models.CharField(max_length=255, blank=True,
                                   help_text="Free text — same stand-in as YardVisit until a fleet master exists")
    vehicle_ref = models.CharField(max_length=64, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-planned_departure", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_load_tnt_status_idx"),
        ]

    # --- derived cube utilization (never stored) ---------------------------------------------------
    def planned_weight_kg(self):
        """Total weight of the assigned shipments — ONE aggregate, not a per-shipment loop."""
        return self.shipments.aggregate(s=Sum("weight_kg"))["s"] or ZERO

    def planned_volume_cbm(self):
        return self.shipments.aggregate(s=Sum("volume_cbm"))["s"] or ZERO

    @staticmethod
    def _utilization(planned, capacity):
        if not capacity or capacity <= ZERO:
            return None
        return (Decimal(planned or ZERO) * 100 / capacity).quantize(Decimal("0.1"))

    def weight_utilization_pct(self, planned=None):
        """Cube-utilization headline. ``planned`` may be passed in (e.g. from a list annotation) to
        avoid re-querying; otherwise it is aggregated on demand."""
        planned = self.planned_weight_kg() if planned is None else planned
        return self._utilization(planned, self.equipment_capacity_weight_kg)

    def volume_utilization_pct(self, planned=None):
        planned = self.planned_volume_cbm() if planned is None else planned
        return self._utilization(planned, self.equipment_capacity_volume_cbm)

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    @property
    def is_closed(self):
        return self.status in self.CLOSED_STATUSES

    def __str__(self):
        return f"{self.number or 'LD'} · {self.origin_text or '?'} → {self.destination_text or '?'}"


class LoadStop(models.Model):
    """One ordered stop on a load's route. Tenant-less child, reached via ``load.tenant``."""

    STOP_TYPE_CHOICES = [
        ("pickup", "Pickup"),
        ("delivery", "Delivery"),
        ("cross_dock", "Cross-dock"),
        ("fuel", "Fuel / Rest"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("arrived", "Arrived"),
        ("completed", "Completed"),
        ("skipped", "Skipped"),
    ]

    load = models.ForeignKey("scm.Load", on_delete=models.CASCADE, related_name="stops")
    sequence = models.PositiveIntegerField(default=1, help_text="Stop order along the route")
    stop_type = models.CharField(max_length=12, choices=STOP_TYPE_CHOICES, default="delivery")
    address = models.ForeignKey("core.Address", on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="scm_load_stops")
    address_text = models.CharField(max_length=255, blank=True,
                                    help_text="Free-text address when it isn't a Party address")
    planned_arrival = models.DateTimeField(null=True, blank=True)
    actual_arrival = models.DateTimeField(null=True, blank=True, editable=False)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="pending")
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["sequence", "id"]

    def __str__(self):
        where = self.address_text or (str(self.address) if self.address_id else "?")
        return f"#{self.sequence} {self.get_stop_type_display()} · {where}"
