"""SCM 4.6 Transportation Management System — Shipment + TrackingEvent models.

A **shipment** is the customer/GRN-facing movement of goods. It links the order it fulfils
(``scm.SalesOrder`` outbound, ``scm.PurchaseOrder`` inbound — both by nullable FK, verified existing),
optionally rides on a consolidated ``Load``, and is executed by a ``Carrier``.

``TrackingEvent`` is an **append-only** milestone/GPS log — no edit or delete views, the same posture
as the ``StockMove`` ledger. The summary fields on ``Shipment`` (``status``, ``current_status_text``,
``last_known_location``, ``eta``, POD, actual pickup/delivery) are DERIVED from events by
``apply_tracking_event()``: an event is the fact, the summary is a projection of the latest fact.
Cube inputs (``weight_kg``/``volume_cbm``/``package_count``) live here because ``scm.Item`` has no
physical-dimension fields yet — the same stand-in posture 4.1 used before the item catalog existed.
"""
from apps.scm.models._base import *  # noqa: F401,F403
from apps.scm.models.TransportationManagement.Carriers import MODE_CHOICES


class Shipment(TenantNumbered):
    """A tracked movement of goods [SHP-] executed by a carrier, optionally consolidated on a load."""

    NUMBER_PREFIX = "SHP"

    DIRECTION_CHOICES = [
        ("outbound", "Outbound (to customer)"),
        ("inbound", "Inbound (from supplier)"),
    ]
    STATUS_CHOICES = [
        ("planned", "Planned"),
        ("booked", "Booked"),
        ("in_transit", "In Transit"),
        ("exception", "Exception"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    ]
    EDITABLE_STATUSES = ("planned", "booked")
    CLOSED_STATUSES = ("delivered", "cancelled")

    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, default="outbound")
    carrier = models.ForeignKey("scm.Carrier", on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="shipments")
    load = models.ForeignKey("scm.Load", on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="shipments", help_text="Consolidation onto a trip")
    sales_order = models.ForeignKey("scm.SalesOrder", on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="shipments", help_text="Outbound order fulfilled")
    purchase_order = models.ForeignKey("scm.PurchaseOrder", on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name="shipments", help_text="Inbound order received")
    ship_from_address = models.ForeignKey("core.Address", on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name="scm_shipments_from")
    ship_to_address = models.ForeignKey("core.Address", on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name="scm_shipments_to")
    origin_text = models.CharField(max_length=255, blank=True)
    destination_text = models.CharField(max_length=255, blank=True)
    mode = models.CharField(max_length=12, choices=MODE_CHOICES, default="truckload")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="planned", editable=False)
    planned_pickup_date = models.DateField(null=True, blank=True)
    planned_delivery_date = models.DateField(null=True, blank=True)
    # Stamped from tracking events, never typed — kept off the form.
    actual_pickup_at = models.DateTimeField(null=True, blank=True, editable=False)
    actual_delivery_at = models.DateTimeField(null=True, blank=True, editable=False)
    weight_kg = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                    validators=[MinValueValidator(ZERO)])
    volume_cbm = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True,
                                     validators=[MinValueValidator(ZERO)])
    package_count = models.PositiveIntegerField(null=True, blank=True)
    carrier_tracking_number = models.CharField(max_length=64, blank=True,
                                               help_text="Carrier's own tracking reference")
    freight_cost_estimate = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                                validators=[MinValueValidator(ZERO)])
    # Projections of the latest TrackingEvent — all editable=False, driven by apply_tracking_event().
    current_status_text = models.CharField(max_length=120, blank=True, editable=False)
    last_known_location = models.CharField(max_length=255, blank=True, editable=False)
    eta = models.DateTimeField(null=True, blank=True, editable=False)
    pod_received = models.BooleanField(default=False, editable=False, verbose_name="POD received")
    pod_received_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_shp_tnt_status_idx"),
            models.Index(fields=["tenant", "direction"], name="scm_shp_tnt_dir_idx"),
        ]

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    @property
    def is_closed(self):
        return self.status in self.CLOSED_STATUSES

    @property
    def is_delayed(self):
        """Past its planned delivery date and still moving."""
        return bool(self.planned_delivery_date
                    and self.status in ("planned", "booked", "in_transit", "exception")
                    and self.planned_delivery_date < timezone.localdate())

    def apply_tracking_event(self, event, save=True):
        """Project a newly-appended ``TrackingEvent`` onto the shipment's summary fields.

        The event's ``event_type`` may advance the shipment's status (an ``in_transit`` event moves a
        booked shipment into transit; ``delivered`` closes it and stamps POD/actual-delivery; an
        ``exception``/``delayed`` event flips it to ``exception``). ``pickup`` stamps the actual
        pickup once. Terminal shipments (delivered/cancelled) are never dragged backwards.
        """
        fields = ["current_status_text", "last_known_location", "updated_at"]
        self.current_status_text = event.get_event_type_display()
        if event.location_text:
            self.last_known_location = event.location_text
            fields.append("last_known_location")

        if self.status in self.CLOSED_STATUSES:
            # A closed shipment still records the event, but its status is not walked back.
            if save:
                self.save(update_fields=list(dict.fromkeys(fields)))
            return

        etype = event.event_type
        if etype == "pickup" and self.actual_pickup_at is None:
            self.actual_pickup_at = event.event_at
            self.status = "in_transit"
            fields += ["actual_pickup_at", "status"]
        elif etype in ("in_transit", "departed_origin", "arrived_hub", "out_for_delivery"):
            if self.status in ("planned", "booked"):
                self.status = "in_transit"
                fields.append("status")
        elif etype in ("exception", "delayed", "customs_hold"):
            self.status = "exception"
            fields.append("status")
        elif etype in ("delivered", "pod_signed"):
            self.status = "delivered"
            self.actual_delivery_at = event.event_at
            fields += ["status", "actual_delivery_at"]
            if etype == "pod_signed" and not self.pod_received:
                self.pod_received = True
                self.pod_received_at = event.event_at
                fields += ["pod_received", "pod_received_at"]

        if save:
            self.save(update_fields=list(dict.fromkeys(fields)))

    def __str__(self):
        return f"{self.number or 'SHP'} · {self.get_direction_display()}"


class TrackingEvent(models.Model):
    """One append-only tracking milestone / GPS ping on a shipment. Tenant-less child (via
    ``shipment.tenant``); mirrors the StockMove ledger — created, never edited or deleted."""

    EVENT_TYPE_CHOICES = [
        ("booked", "Booked"),
        ("pickup", "Picked Up"),
        ("departed_origin", "Departed Origin"),
        ("in_transit", "In Transit"),
        ("arrived_hub", "Arrived at Hub"),
        ("customs_hold", "Customs Hold"),
        ("out_for_delivery", "Out for Delivery"),
        ("exception", "Exception"),
        ("delayed", "Delayed"),
        ("delivered", "Delivered"),
        ("pod_signed", "POD Signed"),
    ]
    SOURCE_CHOICES = [
        ("manual", "Manual"),
        ("carrier_api", "Carrier API"),
        ("edi", "EDI"),
        ("driver_app", "Driver App"),
        ("gps_ping", "GPS Ping"),
    ]

    shipment = models.ForeignKey("scm.Shipment", on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES, default="in_transit")
    event_at = models.DateTimeField(default=timezone.now)
    location_text = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    source = models.CharField(max_length=12, choices=SOURCE_CHOICES, default="manual")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="scm_tracking_events", editable=False)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-event_at", "-id"]

    def __str__(self):
        return f"{self.get_event_type_display()} @ {self.event_at:%Y-%m-%d %H:%M}"
