from django.db import models

from apps.quality.models._base import TenantNumbered


class SerializedItem(TenantNumbered):
    NUMBER_PREFIX = "QSER"

    PACKAGING_LEVEL_CHOICES = [
        ("unit", "Item / Primary Unit"),
        ("bundle", "Bundle / Intermediate"),
        ("carton", "Carton / Shipper Case"),
        ("case", "Master Case"),
        ("pallet", "Pallet / Logistical Unit (SSCC)"),
    ]

    COMMISSIONING_STATUS_CHOICES = [
        ("allocated", "Serial Allocated"),
        ("commissioned", "Commissioned / Active"),
        ("aggregated", "Aggregated in Pack"),
        ("shipped", "Shipped Outbound"),
        ("decommissioned", "Decommissioned"),
        ("destroyed", "Destroyed / Sampled"),
        ("recalled", "Recalled / Quarantined"),
    ]

    EPCIS_STATE_CHOICES = [
        ("active", "Active In Inventory"),
        ("in_transit", "In Transit"),
        ("delivered", "Delivered / Dispensed"),
        ("quarantined", "Quarantine Hold"),
        ("suspect", "Suspect Counterfeit / Diverted"),
    ]

    COMMISSIONING_STATUS_CSS = {
        "allocated": "badge-slate",
        "commissioned": "badge-info",
        "aggregated": "badge-slate",
        "shipped": "badge-green",
        "decommissioned": "badge-slate",
        "destroyed": "badge-muted",
        "recalled": "badge-red",
    }

    EPCIS_STATE_CSS = {
        "active": "badge-green",
        "in_transit": "badge-info",
        "delivered": "badge-slate",
        "quarantined": "badge-amber",
        "suspect": "badge-red",
    }

    serial_number = models.CharField(max_length=100, db_index=True)
    gtin_or_di = models.CharField(max_length=64, db_index=True)
    item_code = models.CharField(max_length=100, db_index=True)
    item_name = models.CharField(max_length=255)
    lot_number = models.CharField(max_length=100, db_index=True)
    batch_record = models.ForeignKey(
        "quality.BatchRecord",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="serialized_items",
    )
    device_identifier = models.ForeignKey(
        "quality.DeviceIdentifier",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="serialized_items",
    )
    packaging_level = models.CharField(max_length=25, choices=PACKAGING_LEVEL_CHOICES, default="unit", db_index=True)
    parent_container = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="child_units",
    )
    sscc_code = models.CharField(max_length=64, blank=True, db_index=True, help_text="Serial Shipping Container Code (SSCC)")
    commissioning_status = models.CharField(
        max_length=25,
        choices=COMMISSIONING_STATUS_CHOICES,
        default="allocated",
        db_index=True,
    )
    epcis_state = models.CharField(max_length=25, choices=EPCIS_STATE_CHOICES, default="active", db_index=True)
    verification_code = models.CharField(max_length=64, blank=True, help_text="Cryptographic verification hash")
    is_cold_chain = models.BooleanField(default=False)
    temperature_limit_min = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    temperature_limit_max = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    custodian = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="custody_serialized_items",
    )
    location_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="serialized_items",
    )
    shipment = models.ForeignKey(
        "scm.Shipment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="serialized_items",
    )
    manufacturing_date = models.DateField(null=True, blank=True)
    expiration_date = models.DateField(null=True, blank=True)
    commissioned_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "serial_number"]
        verbose_name = "Serialized Item"
        verbose_name_plural = "Serialized Items"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qser_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "serial_number"], name="idx_qser_ten_serial"),
            models.Index(fields=["tenant", "commissioning_status"], name="idx_qser_ten_comm"),
            models.Index(fields=["tenant", "packaging_level"], name="idx_qser_ten_pkg"),
            models.Index(fields=["tenant", "epcis_state"], name="idx_qser_ten_epcis"),
        ]

    def __str__(self):
        return f"{self.serial_number} ({self.get_packaging_level_display()})"
