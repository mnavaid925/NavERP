from datetime import timedelta
from decimal import Decimal

from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetServiceContract(TenantNumbered):
    """
    Third-party vendor maintenance agreements (AMC), OEM warranty extensions,
    SLA response/resolution performance guarantees, and maintenance visit quotas [ASVC-].
    """

    NUMBER_PREFIX = "ASVC"

    CONTRACT_TYPE_CHOICES = [
        ("comprehensive_amc", "Comprehensive Annual Maintenance (Parts & Labor)"),
        ("labor_only", "Labor-Only Maintenance Agreement"),
        ("parts_and_labor", "Standard Parts & Labor Agreement"),
        ("on_call_support", "On-Call Emergency Support Agreement"),
        ("oem_warranty_extension", "OEM Extended Warranty Contract"),
    ]

    BILLING_FREQUENCY_CHOICES = [
        ("monthly", "Monthly Retainer"),
        ("quarterly", "Quarterly In Advance"),
        ("semi_annual", "Semi-Annual"),
        ("annual", "Annual Lump Sum"),
        ("per_visit", "Per-Visit Invoiced"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft Agreement"),
        ("active", "Active Contract"),
        ("expiring_soon", "Expiring Within 30 Days"),
        ("expired", "Contract Expired"),
        ("terminated", "Terminated Early"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "active": "badge-green",
        "expiring_soon": "badge-amber",
        "expired": "badge-red",
        "terminated": "badge-muted",
    }

    CONTRACT_TYPE_CSS = {
        "comprehensive_amc": "badge-green",
        "labor_only": "badge-info",
        "parts_and_labor": "badge-blue",
        "on_call_support": "badge-amber",
        "oem_warranty_extension": "badge-purple",
    }

    contract_number = models.CharField(
        max_length=100,
        help_text="External vendor contract or SLA agreement number",
    )
    title = models.CharField(
        max_length=255,
        help_text="Agreement title / scope description",
    )
    vendor = models.ForeignKey(
        "core.Party",
        on_delete=models.PROTECT,
        related_name="asset_service_contracts",
        help_text="Service provider / vendor Party record",
    )
    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_contracts",
        help_text="Financial Fixed Asset covered",
    )
    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_contracts",
        help_text="Operational machinery covered",
    )
    contract_type = models.CharField(
        max_length=32,
        choices=CONTRACT_TYPE_CHOICES,
        default="comprehensive_amc",
    )
    start_date = models.DateField(
        help_text="Effective start date of contract coverage",
    )
    end_date = models.DateField(
        help_text="Contract expiration date",
    )
    contract_value = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Total contractual value or annual retainer cost",
    )
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_service_contracts",
    )
    billing_frequency = models.CharField(
        max_length=20,
        choices=BILLING_FREQUENCY_CHOICES,
        default="annual",
    )
    sla_response_hours = models.PositiveIntegerField(
        default=4,
        help_text="Target first response / arrival SLA in hours",
    )
    sla_resolution_hours = models.PositiveIntegerField(
        default=24,
        help_text="Target full fault resolution SLA in hours",
    )
    pm_visits_included = models.PositiveIntegerField(
        default=4,
        help_text="Routine preventive maintenance visits included in agreement",
    )
    pm_visits_completed = models.PositiveIntegerField(
        default=0,
        help_text="Actual visits logged against quota",
    )
    coverage_terms = models.TextField(
        blank=True,
        help_text="Specific inclusion/exclusion clauses, parts warranty coverage, and emergency rates",
    )
    auto_renew = models.BooleanField(
        default=False,
        help_text="Contract automatically rolls over unless cancelled",
    )
    contact_person = models.CharField(
        max_length=150,
        blank=True,
        help_text="Vendor primary account manager / technical rep",
    )
    contact_phone = models.CharField(max_length=50, blank=True)
    contact_email = models.EmailField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["end_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_asvc_ten_num_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_asvc_ten_stat"),
            models.Index(fields=["tenant", "vendor"], name="idx_asvc_ten_vend"),
            models.Index(fields=["tenant", "end_date"], name="idx_asvc_ten_end"),
            models.Index(fields=["tenant", "contract_type"], name="idx_asvc_ten_type"),
        ]

    def __str__(self):
        return f"{self.number} ({self.contract_number}) - {self.title}"

    @property
    def status_css(self):
        today = timezone.now().date()
        if self.status == "active":
            if self.end_date < today:
                return "badge-red"
            elif self.end_date <= today + timedelta(days=30):
                return "badge-amber"
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def contract_type_css(self):
        return self.CONTRACT_TYPE_CSS.get(self.contract_type, "badge-slate")

    @property
    def remaining_visits(self):
        return max(0, self.pm_visits_included - self.pm_visits_completed)

    def activate(self):
        self.status = "active"
        self.save(update_fields=["status", "updated_at"])

    def record_visit(self):
        self.pm_visits_completed += 1
        self.save(update_fields=["pm_visits_completed", "updated_at"])

    def renew(self, new_end_date, new_contract_value=None):
        self.end_date = new_end_date
        if new_contract_value is not None:
            self.contract_value = new_contract_value
        self.status = "active"
        self.pm_visits_completed = 0
        self.save(update_fields=["end_date", "contract_value", "status", "pm_visits_completed", "updated_at"])

    def terminate(self):
        self.status = "terminated"
        self.save(update_fields=["status", "updated_at"])
