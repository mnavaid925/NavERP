"""Inventory 5.7 Stock Movement & Transfers — TransferRoute.

**Transfer Routing bullet:** defining the best path or transit method for transfers.
The movement DOCUMENT is 4.3's ``scm.StockTransfer`` (L36 — extend the spine, never
re-declare it); this master is the routing catalog that document can now travel by.
A route says HOW stock goes from A to B — direct run, scheduled shuttle, consolidated
milk run or booked freight — and how long the hop should take, so a submitted transfer
carries an expected transit window instead of a shrug.

Endpoints are OPTIONAL: a route may be written for one lane (both endpoints set),
offered as a general service (neither), or pinned at just one end. The spine carries
the chosen route as a nullable FK added to ``scm.StockTransfer`` itself — same
additive-on-the-spine move Location made for bin capacity and cold storage — so a
route deletion SET_NULLs history rather than rewriting it.
"""
from apps.inventory.models._base import *  # noqa: F401,F403


class TransferRoute(TenantOwned):
    """One way stock routinely travels between locations."""

    MODE_CHOICES = [
        ("direct", "Direct Run"),
        ("shuttle", "Scheduled Shuttle"),
        ("milk_run", "Consolidated Milk Run"),
        ("freight", "Freight Carrier"),
    ]

    name = models.CharField(max_length=120)
    code = models.CharField(
        max_length=32, blank=True,
        help_text="Short reference used on documents, e.g. RT-WH1-WH2")
    mode = models.CharField(max_length=12, choices=MODE_CHOICES, default="direct")
    origin_location = models.ForeignKey(
        "scm.Location", on_delete=models.PROTECT, null=True, blank=True,
        related_name="transfer_routes_from",
        help_text="Lane start — blank means this route may start anywhere")
    destination_location = models.ForeignKey(
        "scm.Location", on_delete=models.PROTECT, null=True, blank=True,
        related_name="transfer_routes_to",
        help_text="Lane end — blank means this route may end anywhere")
    default_transit_days = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1)],
        help_text="Expected door-to-door days when this route is used")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "name")
        indexes = [models.Index(fields=["tenant", "is_active"], name="inv_trt_tnt_active_idx")]

    @property
    def mode_css(self):
        """:attr:`MODE_CHOICES` badge colour, decided in ONE place. theme.css ships
        colour-named modifiers only (green/red/amber/info/muted/slate) — L33."""
        return {
            "direct": "badge-green",
            "shuttle": "badge-info",
            "milk_run": "badge-amber",
            "freight": "badge-slate",
        }.get(self.mode, "badge-muted")

    def covers(self, source_location_id, destination_location_id):
        """True when this route may carry a leg between the two given locations.

        A set endpoint must match exactly; a blank endpoint matches anything — the
        both-blank route is the tenant's general service."""
        if self.origin_location_id and self.origin_location_id != source_location_id:
            return False
        if self.destination_location_id and self.destination_location_id != destination_location_id:
            return False
        return True

    def clean(self):
        super().clean()
        # The form's _reject_foreign covers crafted POSTs; these checks cover every OTHER
        # write path (admin, seeder, a future import).
        for field in ("origin_location", "destination_location"):
            loc = getattr(self, field)
            if loc is not None and loc.tenant_id != self.tenant_id:
                raise ValidationError({field: "That location belongs to another workspace."})
        if (self.origin_location_id and self.destination_location_id
                and self.origin_location_id == self.destination_location_id):
            raise ValidationError(
                {"destination_location":
                 "A route's start and end must be different locations."})

    def __str__(self):
        return self.name
