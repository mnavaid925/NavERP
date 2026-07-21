"""SCM 4.6 Transportation Management System — Carrier + CarrierRateCard models.

A **carrier** is the ships-first landing point 4.4 anticipated: ``YardVisit.carrier_name`` /
``PickTask`` packing fields are free-text *"until 4.6 TMS"* placeholders, and this is where a real
carrier master lives. It follows the 4.2 ``SupplierProfile`` precedent exactly — a carrier is NOT a
new standalone company table but a TMS **profile on a ``core.Party``** carrying the supplier/vendor
role. Identity (name, addresses, contacts, tax id) stays on the Party; this model adds only the
transport-specific attributes (SCAC/MC/DOT, mode, service level, rate cards, on-time scorecard).

``on_time_delivery_pct`` is DERIVED from real ``Shipment`` history by ``recompute_scorecard()`` —
the same "evidence, not opinion" posture as ``SupplierScorecard.recompute_from_signals()`` — never a
hand-typed figure.

The transport choice vocabularies (mode / equipment / service level) live here as module constants
and are imported by ``Loads``/``Shipments``/``FreightInvoices`` so the four entities speak one
language. The dependency is one-way (Carriers imports nothing from its siblings), so there is no
import cycle.
"""
from apps.scm.models._base import *  # noqa: F401,F403


# Shared transportation vocabularies — one definition, reused across the 4.6 entities.
MODE_CHOICES = [
    ("truckload", "Full Truckload (FTL)"),
    ("ltl", "Less-than-Truckload (LTL)"),
    ("parcel", "Parcel / Courier"),
    ("ocean", "Ocean"),
    ("air", "Air"),
    ("rail", "Rail"),
    ("intermodal", "Intermodal"),
]
EQUIPMENT_CHOICES = [
    ("dry_van", "Dry Van"),
    ("reefer", "Refrigerated (Reefer)"),
    ("flatbed", "Flatbed"),
    ("container", "Container"),
    ("tanker", "Tanker"),
    ("parcel", "Parcel"),
]
SERVICE_LEVEL_CHOICES = [
    ("economy", "Economy"),
    ("standard", "Standard"),
    ("expedited", "Expedited"),
]


class Carrier(TenantNumbered):
    """A transport provider [CAR-] — a TMS profile on a supplier/vendor ``core.Party``.

    ``party`` is REQUIRED (PROTECT): a carrier is a party you procure transport from, so — like the
    4.2 supplier profile — it reuses the spine rather than duplicating a name/address table. That
    also keeps the freight hand-off clean: ``FreightInvoice`` drafts an ``accounting.Bill`` whose
    (PROTECT, required) ``party`` is exactly this carrier's party.
    """

    NUMBER_PREFIX = "CAR"

    CARRIER_TYPE_CHOICES = [
        ("asset_based", "Asset-Based"),
        ("broker", "Broker"),
        ("3pl", "Third-Party Logistics (3PL)"),
        ("courier", "Courier / Parcel"),
    ]
    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("suspended", "Suspended"),
    ]
    ACTIVE_STATUSES = ("active",)

    party = models.ForeignKey("core.Party", on_delete=models.PROTECT, related_name="scm_carriers")
    carrier_type = models.CharField(max_length=16, choices=CARRIER_TYPE_CHOICES, default="asset_based")
    primary_mode = models.CharField(max_length=12, choices=MODE_CHOICES, default="truckload")
    service_level = models.CharField(max_length=12, choices=SERVICE_LEVEL_CHOICES, default="standard")
    # Compliance identifiers — free text, blank until captured (a domestic parcel carrier has no SCAC).
    scac_code = models.CharField("SCAC code", max_length=8, blank=True,
                                 help_text="Standard Carrier Alpha Code")
    mc_number = models.CharField("MC number", max_length=20, blank=True,
                                 help_text="Motor Carrier authority number")
    dot_number = models.CharField("DOT number", max_length=20, blank=True)
    insurance_certificate_expiry = models.DateField(null=True, blank=True,
                                                    help_text="Certificate of Insurance expiry")
    primary_contact_name = models.CharField(max_length=255, blank=True)
    primary_contact_email = models.EmailField(blank=True)
    primary_contact_phone = models.CharField(max_length=40, blank=True)
    is_preferred = models.BooleanField(default=False, help_text="Prefer this carrier when tendering")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="active")
    # Derived from delivered Shipment history — editable=False keeps it off the form (evidence, not
    # opinion). None until there is at least one datable delivered shipment to score from.
    on_time_delivery_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                               editable=False)
    performance_summary = models.CharField(max_length=255, blank=True, editable=False,
                                           help_text="How the on-time score was derived")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["party__name", "id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_car_tnt_status_idx"),
            models.Index(fields=["tenant", "primary_mode"], name="scm_car_tnt_mode_idx"),
        ]

    @property
    def name(self):
        """Display name comes from the Party — the carrier never stores its own copy."""
        return self.party.name if self.party_id else ""

    @property
    def is_active(self):
        return self.status in self.ACTIVE_STATUSES

    @property
    def insurance_expired(self):
        return bool(self.insurance_certificate_expiry
                    and self.insurance_certificate_expiry < timezone.localdate())

    def recompute_scorecard(self, save=True):
        """Derive ``on_time_delivery_pct`` from this carrier's delivered shipments.

        On-time = delivered on/before the planned delivery date. Only shipments that HAVE a planned
        date and an actual delivery count toward the denominator, so an undated shipment never drags
        the score. Leaves the score untouched (rather than zeroing it) when there is no signal yet —
        mirrors ``SupplierScorecard.recompute_from_signals`` refusing to wipe a figure with a
        phantom zero. Imported here (not at module top) to avoid a models-package import cycle.
        """
        from apps.scm.models import Shipment

        delivered = list(
            Shipment.objects
            .filter(tenant=self.tenant, carrier=self, status="delivered",
                    planned_delivery_date__isnull=False, actual_delivery_at__isnull=False)
            .only("planned_delivery_date", "actual_delivery_at")
        )
        before = (self.on_time_delivery_pct, self.performance_summary)
        if delivered:
            on_time = sum(1 for s in delivered
                          if s.actual_delivery_at.date() <= s.planned_delivery_date)
            self.on_time_delivery_pct = (Decimal(on_time) * 100 / len(delivered)).quantize(Decimal("0.01"))
            self.performance_summary = f"On-time on {on_time}/{len(delivered)} delivered shipment(s)."
        else:
            self.performance_summary = "No delivered shipments with a planned date yet."
        if save and (self.on_time_delivery_pct, self.performance_summary) != before:
            self.save(update_fields=["on_time_delivery_pct", "performance_summary", "updated_at"])
        return self.on_time_delivery_pct

    def __str__(self):
        return f"{self.number or 'CAR'} · {self.name}"


class CarrierRateCard(models.Model):
    """A negotiated lane/mode/equipment rate for a carrier — the baseline a freight invoice is
    audited against. No tenant FK of its own: reached through ``carrier.tenant`` like every other scm
    child (PurchaseOrderLine, SalesOrderLine).
    """

    RATE_BASIS_CHOICES = [
        ("flat", "Flat per shipment"),
        ("per_mile", "Per mile"),
        ("per_km", "Per km"),
        ("per_kg", "Per kg"),
        ("per_cbm", "Per m³"),
        ("per_pallet", "Per pallet"),
    ]

    carrier = models.ForeignKey("scm.Carrier", on_delete=models.CASCADE, related_name="rate_cards")
    lane_name = models.CharField(max_length=120, blank=True,
                                 help_text="e.g. Chicago → Dallas (free text — no geo-zone master yet)")
    origin_region = models.CharField(max_length=120, blank=True)
    destination_region = models.CharField(max_length=120, blank=True)
    mode = models.CharField(max_length=12, choices=MODE_CHOICES, default="truckload")
    equipment_type = models.CharField(max_length=12, choices=EQUIPMENT_CHOICES, default="dry_van")
    rate_basis = models.CharField(max_length=12, choices=RATE_BASIS_CHOICES, default="flat")
    base_rate = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                    validators=[MinValueValidator(ZERO)])
    fuel_surcharge_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                             validators=[MinValueValidator(0), MaxValueValidator(100)])
    min_charge = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                     validators=[MinValueValidator(ZERO)])
    transit_days = models.PositiveIntegerField(null=True, blank=True,
                                               help_text="Typical door-to-door transit time")
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="scm_rate_cards")
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["carrier__party__name", "mode", "id"]

    @property
    def rate_with_fuel(self):
        """Base rate grossed up by the fuel surcharge — the all-in expected figure for the audit."""
        return (self.base_rate or ZERO) * (Decimal("1") + (self.fuel_surcharge_pct or ZERO) / Decimal("100"))

    def __str__(self):
        lane = self.lane_name or f"{self.origin_region or '?'} → {self.destination_region or '?'}"
        return f"{lane} ({self.get_mode_display()})"
