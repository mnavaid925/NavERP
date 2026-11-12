"""Software License Entitlement & SAM Compliance model (11.18)."""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered
from apps.assets.models.ItAssetManagement._validators import (
    add_field_error,
    validate_masked_key_ref,
    validate_tenant_fks,
)


class SoftwareLicense(TenantNumbered):
    """Software license entitlement, usage metering, ELP compliance & harvesting [ITSW]."""

    NUMBER_PREFIX = "ITSW"

    SOFTWARE_CATEGORY_CHOICES = [
        ("os_platform", "OS & Platform"),
        ("productivity_suite", "Productivity & Collaboration"),
        ("erp_finance", "ERP & Finance"),
        ("devops_ide", "DevOps & Developer Tools"),
        ("database_engine", "Database Engine"),
        ("security_edr", "Security & EDR"),
        ("design_cad", "Engineering / CAD / Creative"),
        ("virtualization", "Virtualization & Hypervisor"),
        ("middleware", "Middleware & Integration"),
        ("other", "Other Software"),
    ]

    LICENSE_TYPE_CHOICES = [
        ("subscription_term", "Term Subscription"),
        ("perpetual", "Perpetual"),
        ("enterprise_ela", "Enterprise Agreement (ELA)"),
        ("oem_bundled", "OEM / Hardware Bundled"),
        ("open_source_commercial", "Commercial Open Source"),
    ]

    LICENSE_METRIC_CHOICES = [
        ("per_user", "Per Named User"),
        ("per_device", "Per Device / Endpoint"),
        ("per_core", "Per Processor Core"),
        ("per_cpu_socket", "Per CPU Socket"),
        ("concurrent_floating", "Concurrent / Floating"),
        ("site_unlimited", "Site / Enterprise Unlimited"),
        ("cal_client_access", "Client Access License (CAL)"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active_compliant", "Active / Compliant"),
        ("surplus_reclaimable", "Surplus / Reclaimable"),
        ("true_up_required", "True-Up Required"),
        ("audit_hold", "Audit Hold"),
        ("expired", "Expired"),
        ("retired", "Retired"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "active_compliant": "badge-green",
        "surplus_reclaimable": "badge-info",
        "true_up_required": "badge-red",
        "audit_hold": "badge-amber",
        "expired": "badge-red",
        "retired": "badge-muted",
    }

    LOCKED_STATUSES = {"retired"}

    _TENANT_FK_FIELDS = (
        "publisher_party",
        "reseller_party",
        "org_unit",
        "gl_expense_account",
        "purchase_order",
        "service_contract",
        "license_owner",
    )

    software_name = models.CharField(max_length=200)
    publisher_name = models.CharField(max_length=150)
    product_sku = models.CharField(max_length=80, blank=True)
    version_edition = models.CharField(max_length=80, blank=True)
    software_category = models.CharField(
        max_length=24, choices=SOFTWARE_CATEGORY_CHOICES, default="productivity_suite"
    )
    license_type = models.CharField(
        max_length=32, choices=LICENSE_TYPE_CHOICES, default="subscription_term"
    )
    license_metric = models.CharField(
        max_length=24, choices=LICENSE_METRIC_CHOICES, default="per_user"
    )
    agreement_number = models.CharField(max_length=80, blank=True)
    license_key_ref = models.CharField(
        max_length=120,
        blank=True,
        help_text="Masked reference only (e.g. MS365-****-9X2K) — never store raw keys.",
    )

    entitled_quantity = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1)]
    )
    allocated_quantity = models.PositiveIntegerField(default=0)
    active_used_quantity = models.PositiveIntegerField(default=0)
    reclaimable_inactive_count = models.PositiveIntegerField(default=0)
    unit_license_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    total_annual_spend = models.DecimalField(
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
        related_name="software_licenses",
    )

    effective_date = models.DateField(null=True, blank=True)
    renewal_date = models.DateField(null=True, blank=True)
    vendor_eol_date = models.DateField(null=True, blank=True)
    auto_renew = models.BooleanField(default=False)

    status = models.CharField(
        max_length=24, choices=STATUS_CHOICES, default="draft", editable=False
    )
    last_reconciled_at = models.DateTimeField(null=True, blank=True, editable=False)
    retired_at = models.DateTimeField(null=True, blank=True, editable=False)

    publisher_party = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="publisher_software_licenses",
    )
    reseller_party = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reseller_software_licenses",
    )
    org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="software_licenses",
    )
    gl_expense_account = models.ForeignKey(
        "accounting.GLAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="software_licenses",
    )
    purchase_order = models.ForeignKey(
        "scm.PurchaseOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="software_licenses",
    )
    service_contract = models.ForeignKey(
        "assets.AssetServiceContract",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="software_licenses",
    )
    license_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_software_licenses",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["software_name", "-number"]
        verbose_name = "Software License"
        verbose_name_plural = "Software Licenses"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"], name="assets_itsw_ten_num_uniq"
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "software_name"], name="idx_itsw_ten_name"),
            models.Index(fields=["tenant", "status"], name="idx_itsw_ten_stat"),
            models.Index(fields=["tenant", "software_category"], name="idx_itsw_ten_cat"),
            models.Index(fields=["tenant", "license_type"], name="idx_itsw_ten_ltype"),
            models.Index(fields=["tenant", "renewal_date"], name="idx_itsw_ten_ren"),
            models.Index(fields=["tenant", "vendor_eol_date"], name="idx_itsw_ten_eol"),
        ]

    def __str__(self):
        return f"{self.number} — {self.software_name}"

    @property
    def is_locked(self):
        return self.status in self.LOCKED_STATUSES

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def compliance_delta(self):
        return int(self.entitled_quantity or 0) - int(self.allocated_quantity or 0)

    @property
    def is_under_licensed(self):
        return self.compliance_delta < 0

    @property
    def utilization_pct(self):
        entitled = int(self.entitled_quantity or 0)
        if entitled <= 0:
            return 0.0
        return round((int(self.active_used_quantity or 0) * 100.0) / entitled, 1)

    @property
    def estimated_true_up_cost(self):
        delta = self.compliance_delta
        if delta >= 0:
            return Decimal("0.00")
        return (Decimal(abs(delta)) * (self.unit_license_cost or Decimal("0.00"))).quantize(
            Decimal("0.01")
        )

    @property
    def reclaim_savings_potential(self):
        reclaimable = int(self.reclaimable_inactive_count or 0)
        if reclaimable <= 0:
            return Decimal("0.00")
        return (Decimal(reclaimable) * (self.unit_license_cost or Decimal("0.00"))).quantize(
            Decimal("0.01")
        )

    @property
    def is_eol_expired(self):
        if not self.vendor_eol_date:
            return False
        return self.vendor_eol_date < timezone.now().date()

    def compute_compliance_status(self, today=None):
        """Derive Effective License Position (ELP) status from entitlements and usage."""
        if self.status in ("audit_hold", "retired"):
            return self.status
        today = today or timezone.now().date()
        if self.renewal_date and self.renewal_date < today:
            return "expired"
        if self.allocated_quantity > self.entitled_quantity:
            return "true_up_required"
        surplus = self.entitled_quantity - self.allocated_quantity
        surplus_threshold = max(1, int(self.entitled_quantity * 0.15))
        if self.reclaimable_inactive_count > 0 or surplus >= surplus_threshold:
            return "surplus_reclaimable"
        return "active_compliant"

    def clean(self):
        super().clean()
        errors = validate_tenant_fks(self, self._TENANT_FK_FIELDS)
        if self.entitled_quantity is not None and self.entitled_quantity < 1:
            add_field_error(errors, "entitled_quantity", "Entitled quantity must be at least 1.")
        if self.unit_license_cost is not None and self.unit_license_cost < 0:
            add_field_error(errors, "unit_license_cost", "Unit license cost cannot be negative.")
        if self.total_annual_spend is not None and self.total_annual_spend < 0:
            add_field_error(errors, "total_annual_spend", "Total annual spend cannot be negative.")
        if (
            self.reclaimable_inactive_count is not None
            and self.allocated_quantity is not None
            and self.reclaimable_inactive_count > self.allocated_quantity
        ):
            add_field_error(
                errors,
                "reclaimable_inactive_count",
                "Reclaimable inactive count cannot exceed allocated quantity.",
            )
        if self.effective_date and self.renewal_date and self.renewal_date < self.effective_date:
            add_field_error(errors, "renewal_date", "Renewal date cannot precede effective date.")
        if self.license_key_ref:
            try:
                self.license_key_ref = validate_masked_key_ref(self.license_key_ref)
            except ValidationError as exc:
                for msg in exc.messages:
                    add_field_error(errors, "license_key_ref", msg)
        if errors:
            raise ValidationError(errors)
