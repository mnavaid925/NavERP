from django.conf import settings
from django.db import models

from apps.assets.models._base import TenantNumbered


class AssetMovementLog(TenantNumbered):
    """Inter-facility, room-to-room, or site asset relocations, tracking and custody hand-offs [AMOV-]."""

    NUMBER_PREFIX = "AMOV"

    MOVEMENT_TYPE_CHOICES = [
        ("relocation", "Internal Relocation"),
        ("inter_facility_transfer", "Inter-Facility Transfer"),
        ("room_reassignment", "Room / Bin Reassignment"),
        ("department_transfer", "Department Transfer"),
        ("repair_dispatch", "Offsite Repair Dispatch"),
        ("temporary_deployment", "Temporary Field Deployment"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft Request"),
        ("requested", "Transfer Requested"),
        ("dispatched", "Dispatched / In Transit"),
        ("in_transit", "In Transit"),
        ("received", "Received & Verified"),
        ("rejected", "Rejected at Destination"),
        ("cancelled", "Cancelled"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "requested": "badge-info",
        "dispatched": "badge-amber",
        "in_transit": "badge-amber",
        "received": "badge-green",
        "rejected": "badge-red",
        "cancelled": "badge-muted",
    }

    CONDITION_CHOICES = [
        ("good", "Good / Undamaged"),
        ("fair", "Fair / Minor Transit Wear"),
        ("damaged", "Damaged in Transit"),
    ]

    title = models.CharField(max_length=200, help_text="Transfer title, e.g. CNC Machine Relocation to Bay 4")
    asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.CASCADE,
        related_name="movement_logs",
        help_text="Operational physical asset being transferred",
    )
    movement_type = models.CharField(max_length=30, choices=MOVEMENT_TYPE_CHOICES, default="relocation")

    # Source hierarchy
    from_location = models.ForeignKey(
        "scm.Location",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="outgoing_asset_movements",
        help_text="Source facility, warehouse, or plant",
    )
    from_org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="outgoing_asset_movements",
        help_text="Relinquishing department or operating division",
    )
    from_room_bin = models.CharField(max_length=100, blank=True, help_text="Specific source building, floor, room, or bin")

    # Destination hierarchy
    to_location = models.ForeignKey(
        "scm.Location",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incoming_asset_movements",
        help_text="Destination facility, warehouse, or plant",
    )
    to_org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incoming_asset_movements",
        help_text="Accepting department or operating division",
    )
    to_room_bin = models.CharField(max_length=100, blank=True, help_text="Specific destination building, floor, room, or bin")

    # Custody hand-off
    from_custodian = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="relinquished_asset_movements",
        help_text="Relinquishing custodian or supervisor",
    )
    to_custodian = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accepted_asset_movements",
        help_text="Accepting custodian or supervisor",
    )

    # Point-in-time Geolocation (GPS)
    gps_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, help_text="GPS latitude coordinate")
    gps_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, help_text="GPS longitude coordinate")
    gps_address = models.CharField(max_length=255, blank=True, help_text="Resolved physical street address or geofenced facility tag")

    # Shipping & Logistics
    carrier_name = models.CharField(max_length=100, blank=True, help_text="Internal riggers or commercial carrier (e.g. FedEx Freight, R+L)")
    tracking_number = models.CharField(max_length=100, blank=True, help_text="Waybill, bill of lading, or internal transfer manifest")
    dispatch_date = models.DateTimeField(null=True, blank=True)
    received_date = models.DateTimeField(null=True, blank=True)
    dispatched_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dispatched_asset_movements",
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_asset_movements",
    )

    # Lifecycle & Condition
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="draft")
    condition_on_receipt = models.CharField(max_length=20, choices=CONDITION_CHOICES, default="good")
    reason = models.TextField(blank=True, help_text="Reason for transfer, work order reference, or project reassignment")
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "assets_movement_log"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="assets_amov_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_amov_ten_stat"),
            models.Index(fields=["tenant", "movement_type"], name="idx_amov_ten_type"),
            models.Index(fields=["tenant", "asset"], name="idx_amov_ten_asset"),
            models.Index(fields=["tenant", "created_at"], name="idx_amov_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title} ({self.asset.number if self.asset else 'Asset'})"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")
