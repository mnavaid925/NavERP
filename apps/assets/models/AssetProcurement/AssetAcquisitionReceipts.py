from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetAcquisitionReceipt(TenantNumbered):
    """Physical receiving, inspection, and intake registration of capital equipment [ARCV-]."""

    NUMBER_PREFIX = "ARCV"

    CONDITION_CHOICES = [
        ("excellent", "Excellent (New / Undamaged)"),
        ("good", "Good (Minor cosmetic blemishes)"),
        ("fair", "Fair (Operational with wear)"),
        ("damaged", "Damaged in Transit"),
        ("defective", "Defective / Rejected"),
    ]

    STATUS_CHOICES = [
        ("pending_inspection", "Pending Inspection"),
        ("accepted", "Inspected & Accepted"),
        ("quarantined", "Quarantined / On Hold"),
        ("rejected", "Rejected & RMA Issued"),
        ("capitalized", "Fully Capitalized"),
    ]

    # Theme CSS colour-named badges ONLY
    CONDITION_CSS = {
        "excellent": "badge-green",
        "good": "badge-info",
        "fair": "badge-amber",
        "damaged": "badge-red",
        "defective": "badge-red",
    }

    STATUS_CSS = {
        "pending_inspection": "badge-amber",
        "accepted": "badge-green",
        "quarantined": "badge-slate",
        "rejected": "badge-red",
        "capitalized": "badge-info",
    }

    # Core identity
    title = models.CharField(max_length=200, help_text="Summary description of received asset shipment")

    # Sourcing linkages
    requisition = models.ForeignKey(
        "assets.AssetRequisition",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acquisition_receipts",
        help_text="Original capital requisition authorizing this purchase",
    )
    purchase_order = models.ForeignKey(
        "scm.PurchaseOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_receipts",
        help_text="SCM Purchase Order against which assets are received",
    )
    vendor = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplied_asset_receipts",
        help_text="Delivering supplier or vendor",
    )

    # Physical machine identification
    manufacturer = models.CharField(max_length=120, blank=True)
    model_number = models.CharField(max_length=100, blank=True)
    serial_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Manufacturer serial number, chassis number, or VIN stamped on asset",
    )
    quantity_received = models.PositiveIntegerField(default=1)

    # Logistics & staging
    received_date = models.DateField(default=timezone.now)
    carrier_name = models.CharField(max_length=100, blank=True, help_text="Freight carrier or transport company")
    tracking_number = models.CharField(max_length=100, blank=True, help_text="Waybill or consignment tracking ID")
    bill_of_lading = models.CharField(max_length=100, blank=True, help_text="BOL / shipping document reference")
    receiving_location = models.ForeignKey(
        "scm.Location",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_receipts",
        help_text="Dock, warehouse staging bay, or facility room",
    )

    # Inspection & quality intake
    condition_on_arrival = models.CharField(max_length=20, choices=CONDITION_CHOICES, default="good")
    inspection_notes = models.TextField(blank=True, help_text="Physical inspection observations, defects, or tests")
    inspected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inspected_asset_receipts",
    )
    inspected_at = models.DateTimeField(null=True, blank=True)

    # Status
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="pending_inspection")

    class Meta:
        db_table = "assets_acquisition_receipt"
        ordering = ["-received_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="assets_arcv_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_arcv_ten_stat"),
            models.Index(fields=["tenant", "received_date"], name="idx_arcv_ten_rcvdate"),
            models.Index(fields=["tenant", "condition_on_arrival"], name="idx_arcv_ten_cond"),
            models.Index(fields=["tenant", "serial_number"], name="idx_arcv_ten_ser"),
            models.Index(fields=["tenant", "created_at"], name="idx_arcv_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title}"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-amber")

    @property
    def condition_css(self):
        return self.CONDITION_CSS.get(self.condition_on_arrival, "badge-info")

    def can_inspect_accept(self):
        return self.status in ("pending_inspection", "quarantined")

    def can_quarantine(self):
        return self.status in ("pending_inspection", "accepted")

    def can_reject(self):
        return self.status in ("pending_inspection", "quarantined")
