"""IT Hardware Asset Lifecycle & NIST SP 800-88 Sanitization model (11.18)."""

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered
from apps.assets.models.ItAssetManagement._validators import (
    add_field_error,
    add_months,
    validate_tenant_fks,
)


class ItHardwareAsset(TenantNumbered):
    """IT Hardware Asset endpoint/server/network register with EOL & sanitization tracking [ITHW]."""

    NUMBER_PREFIX = "ITHW"

    DEVICE_CLASS_CHOICES = [
        ("laptop", "Laptop / Notebook"),
        ("desktop", "Desktop PC"),
        ("workstation", "Engineering Workstation"),
        ("physical_server", "Physical Server"),
        ("virtual_host", "Virtualization Host"),
        ("network_switch", "Network Switch"),
        ("router_firewall", "Router / Firewall"),
        ("wireless_ap", "Wireless Access Point"),
        ("storage_array", "SAN / NAS Storage Array"),
        ("mobile_tablet", "Mobile / Tablet"),
        ("printer_mfp", "Printer / MFP"),
        ("peripheral", "Dock / Monitor / Peripheral"),
    ]

    ENVIRONMENT_CHOICES = [
        ("corporate_enduser", "Corporate End-User"),
        ("production", "Production"),
        ("staging", "Staging"),
        ("development", "Development"),
        ("dr_standby", "DR / Standby"),
    ]

    CRITICALITY_CHOICES = [
        ("critical", "Critical"),
        ("high", "High"),
        ("medium", "Medium"),
        ("low", "Low"),
    ]

    DISK_ENCRYPTION_CHOICES = [
        ("bitlocker_filevault", "BitLocker / FileVault"),
        ("luks_encrypted", "LUKS / dm-crypt"),
        ("unencrypted", "Unencrypted"),
        ("exempt", "Exempt / N/A"),
    ]

    STATUS_CHOICES = [
        ("procured", "Procured"),
        ("staged_in_stock", "Staged in Stock"),
        ("deployed", "Deployed / In Use"),
        ("in_repair", "In Repair / RMA"),
        ("loaner_pool", "Loaner Pool"),
        ("pending_refresh", "Pending Refresh"),
        ("sanitized_retired", "Sanitized & Retired"),
        ("disposed", "Disposed"),
    ]

    SANITIZATION_METHOD_CHOICES = [
        ("none", "None"),
        ("nist_clear", "NIST SP 800-88 Clear"),
        ("nist_purge", "NIST SP 800-88 Purge"),
        ("crypto_erase", "Cryptographic Erase"),
        ("physical_shredding", "Physical Shredding / Degauss"),
    ]

    SANITIZATION_STATUS_CHOICES = [
        ("not_required", "Not Required"),
        ("pending_wipe", "Pending Sanitization"),
        ("wiped_verified", "Wiped & Verified"),
        ("certificate_on_file", "Certificate on File"),
    ]

    STATUS_CSS = {
        "procured": "badge-slate",
        "staged_in_stock": "badge-info",
        "deployed": "badge-green",
        "in_repair": "badge-amber",
        "loaner_pool": "badge-info",
        "pending_refresh": "badge-amber",
        "sanitized_retired": "badge-slate",
        "disposed": "badge-muted",
    }

    CRITICALITY_CSS = {
        "critical": "badge-red",
        "high": "badge-amber",
        "medium": "badge-info",
        "low": "badge-slate",
    }

    SANITIZATION_CSS = {
        "not_required": "badge-slate",
        "pending_wipe": "badge-amber",
        "wiped_verified": "badge-green",
        "certificate_on_file": "badge-green",
    }

    REFRESH_PRIORITY_CSS = {
        "overdue_critical": "badge-red",
        "due_within_90d": "badge-amber",
        "planned_fy": "badge-info",
        "healthy": "badge-green",
    }

    LOCKED_STATUSES = {"sanitized_retired", "disposed"}

    _TENANT_FK_FIELDS = (
        "sanitization_verified_by",
        "operational_asset",
        "fixed_asset",
        "asset_model",
        "asset_category",
        "warranty",
        "requisition",
        "replacement_plan",
        "disposal_request",
        "scrap_salvage",
        "org_unit",
        "location",
        "custodian_party",
        "vendor_party",
        "employee_profile",
        "owner",
    )

    hostname = models.CharField(max_length=120)
    fqdn = models.CharField(max_length=200, blank=True)
    device_class = models.CharField(
        max_length=24, choices=DEVICE_CLASS_CHOICES, default="laptop"
    )
    serial_number = models.CharField(max_length=80, blank=True)
    asset_tag_code = models.CharField(max_length=64, blank=True)
    manufacturer = models.CharField(max_length=120, blank=True)
    model_name = models.CharField(max_length=120, blank=True)
    mac_address = models.CharField(max_length=48, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    operating_system = models.CharField(max_length=100, blank=True)
    os_version = models.CharField(max_length=64, blank=True)
    cpu_spec = models.CharField(max_length=120, blank=True)
    ram_gb = models.PositiveIntegerField(null=True, blank=True)
    storage_gb = models.PositiveIntegerField(null=True, blank=True)
    bios_firmware_version = models.CharField(max_length=64, blank=True)
    rack_unit_ref = models.CharField(max_length=64, blank=True)
    environment = models.CharField(
        max_length=24, choices=ENVIRONMENT_CHOICES, default="corporate_enduser"
    )
    criticality = models.CharField(
        max_length=16, choices=CRITICALITY_CHOICES, default="medium"
    )
    mdm_enrolled = models.BooleanField(default=False)
    mdm_platform = models.CharField(max_length=60, blank=True)
    mdm_device_id = models.CharField(max_length=80, blank=True)
    disk_encryption_status = models.CharField(
        max_length=24, choices=DISK_ENCRYPTION_CHOICES, default="unencrypted"
    )
    last_seen_checkin = models.DateTimeField(null=True, blank=True, editable=False)
    status = models.CharField(
        max_length=24, choices=STATUS_CHOICES, default="procured", editable=False
    )

    commissioned_date = models.DateField(null=True, blank=True)
    assigned_date = models.DateField(null=True, blank=True)
    vendor_eos_date = models.DateField(null=True, blank=True)
    vendor_eol_date = models.DateField(null=True, blank=True)
    refresh_cycle_months = models.PositiveSmallIntegerField(
        default=48, validators=[MinValueValidator(1)]
    )
    refresh_due_date = models.DateField(null=True, blank=True)
    estimated_refresh_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="it_hardware_assets",
    )

    sanitization_required = models.BooleanField(default=True)
    sanitization_method = models.CharField(
        max_length=24, choices=SANITIZATION_METHOD_CHOICES, default="none"
    )
    sanitization_status = models.CharField(
        max_length=24, choices=SANITIZATION_STATUS_CHOICES, default="pending_wipe"
    )
    sanitization_date = models.DateField(null=True, blank=True)
    sanitization_certificate_ref = models.CharField(max_length=100, blank=True)
    sanitization_verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="verified_it_sanitizations",
    )
    sanitized_at = models.DateTimeField(null=True, blank=True, editable=False)
    retired_at = models.DateTimeField(null=True, blank=True, editable=False)

    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="it_hardware_assets",
    )
    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="it_hardware_assets",
    )
    asset_model = models.ForeignKey(
        "assets.AssetModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="it_hardware_assets",
    )
    asset_category = models.ForeignKey(
        "assets.AssetCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="it_hardware_assets",
    )
    warranty = models.ForeignKey(
        "assets.AssetWarranty",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="it_hardware_assets",
    )
    requisition = models.ForeignKey(
        "assets.AssetRequisition",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="it_hardware_assets",
    )
    replacement_plan = models.ForeignKey(
        "assets.AssetReplacementPlan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="it_hardware_assets",
    )
    disposal_request = models.ForeignKey(
        "assets.AssetDisposalRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="it_hardware_assets",
    )
    scrap_salvage = models.ForeignKey(
        "assets.AssetScrapSalvage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="it_hardware_assets",
    )
    org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="it_hardware_assets",
    )
    location = models.ForeignKey(
        "scm.Location",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="it_hardware_assets",
    )
    custodian_party = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="custodian_it_hardware_assets",
    )
    vendor_party = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vendor_it_hardware_assets",
    )
    employee_profile = models.ForeignKey(
        "hrm.EmployeeProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="it_hardware_assets",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_it_hardware_assets",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["hostname", "-number"]
        verbose_name = "IT Hardware Asset"
        verbose_name_plural = "IT Hardware Assets"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"], name="assets_ithw_ten_num_uniq"
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "hostname"], name="idx_ithw_ten_host"),
            models.Index(fields=["tenant", "status"], name="idx_ithw_ten_stat"),
            models.Index(fields=["tenant", "device_class"], name="idx_ithw_ten_dcls"),
            models.Index(fields=["tenant", "environment"], name="idx_ithw_ten_env"),
            models.Index(fields=["tenant", "sanitization_status"], name="idx_ithw_ten_sanst"),
            models.Index(fields=["tenant", "vendor_eol_date"], name="idx_ithw_ten_eol"),
            models.Index(fields=["tenant", "refresh_due_date"], name="idx_ithw_ten_rfsh"),
        ]

    def __str__(self):
        return f"{self.number} — {self.hostname}"

    @property
    def is_locked(self):
        return self.status in self.LOCKED_STATUSES

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def criticality_badge_class(self):
        return self.CRITICALITY_CSS.get(self.criticality, "badge-slate")

    @property
    def sanitization_badge_class(self):
        return self.SANITIZATION_CSS.get(self.sanitization_status, "badge-slate")

    @property
    def is_eol_expired(self):
        if not self.vendor_eol_date:
            return False
        return self.vendor_eol_date < timezone.now().date()

    @property
    def is_eos_approaching(self):
        if not self.vendor_eos_date:
            return False
        today = timezone.now().date()
        return today <= self.vendor_eos_date <= today + timedelta(days=90)

    @property
    def refresh_priority(self):
        if self.status in self.LOCKED_STATUSES:
            return "healthy"
        today = timezone.now().date()
        target_date = self.refresh_due_date or self.vendor_eol_date
        if self.vendor_eol_date and self.vendor_eol_date < today:
            return "overdue_critical"
        if target_date is None:
            return "healthy"
        if target_date < today:
            return "overdue_critical"
        if target_date <= today + timedelta(days=90):
            return "due_within_90d"
        if target_date <= today + timedelta(days=365):
            return "planned_fy"
        return "healthy"

    @property
    def refresh_priority_display(self):
        labels = {
            "overdue_critical": "Overdue / EOL Expired",
            "due_within_90d": "Due <= 90 Days",
            "planned_fy": "Planned (12 Mo)",
            "healthy": "Healthy",
        }
        return labels.get(self.refresh_priority, "Healthy")

    @property
    def refresh_priority_badge_class(self):
        return self.REFRESH_PRIORITY_CSS.get(self.refresh_priority, "badge-slate")

    def clean(self):
        super().clean()
        errors = validate_tenant_fks(self, self._TENANT_FK_FIELDS)
        if self.refresh_cycle_months is not None and self.refresh_cycle_months < 1:
            add_field_error(errors, "refresh_cycle_months", "Refresh cycle must be at least 1 month.")
        if self.estimated_refresh_cost is not None and self.estimated_refresh_cost < 0:
            add_field_error(errors, "estimated_refresh_cost", "Estimated refresh cost cannot be negative.")
        if self.vendor_eos_date and self.vendor_eol_date and self.vendor_eol_date < self.vendor_eos_date:
            add_field_error(errors, "vendor_eol_date", "Vendor EOL date cannot precede End-of-Sale (EOS) date.")
        if (
            self.sanitization_required
            and self.sanitization_status in ("wiped_verified", "certificate_on_file")
            and self.sanitization_method == "none"
        ):
            add_field_error(
                errors,
                "sanitization_method",
                "Select a NIST SP 800-88 sanitization method when status is Wiped or Certified.",
            )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.refresh_due_date is None:
            if self.commissioned_date and self.refresh_cycle_months:
                self.refresh_due_date = add_months(self.commissioned_date, self.refresh_cycle_months)
            elif self.vendor_eol_date:
                self.refresh_due_date = self.vendor_eol_date
        super().save(*args, **kwargs)
