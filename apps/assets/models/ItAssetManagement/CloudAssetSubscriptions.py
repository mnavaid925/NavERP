"""Cloud Asset, SaaS Subscription & FinOps Tracking model (11.18)."""

from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered
from apps.assets.models.ItAssetManagement._validators import (
    add_field_error,
    validate_tenant_fks,
)


class CloudAssetSubscription(TenantNumbered):
    """Cloud resource, SaaS application, and FinOps commitment record [ITCL]."""

    NUMBER_PREFIX = "ITCL"

    ASSET_KIND_CHOICES = [
        ("saas_application", "SaaS Application"),
        ("iaas_compute", "IaaS Compute / VM / Cluster"),
        ("paas_database", "PaaS Database / Managed Service"),
        ("reserved_instance", "Reserved Instance (RI)"),
        ("savings_plan", "Cloud Savings Plan"),
        ("cloud_storage", "Object / Block Storage"),
        ("cloud_network_cdn", "Cloud Network / CDN / WAF"),
        ("ai_api_platform", "AI / API Platform"),
    ]

    PROVIDER_CHOICES = [
        ("aws", "Amazon Web Services (AWS)"),
        ("azure", "Microsoft Azure"),
        ("gcp", "Google Cloud (GCP)"),
        ("oracle_cloud", "Oracle Cloud (OCI)"),
        ("microsoft_365", "Microsoft 365"),
        ("google_workspace", "Google Workspace"),
        ("salesforce", "Salesforce"),
        ("atlassian", "Atlassian Cloud"),
        ("github", "GitHub Enterprise"),
        ("slack", "Slack"),
        ("datadog", "Datadog"),
        ("other_saas", "Other Cloud / SaaS"),
    ]

    ENVIRONMENT_CHOICES = [
        ("production", "Production"),
        ("staging", "Staging"),
        ("development", "Development"),
        ("corporate_saas", "Corporate SaaS"),
        ("sandbox", "Sandbox"),
    ]

    BILLING_CADENCE_CHOICES = [
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("annual", "Annual"),
        ("multi_year", "Multi-Year"),
        ("usage_payg", "Pay-As-You-Go"),
    ]

    COMMITMENT_TERM_CHOICES = [
        ("on_demand", "On-Demand"),
        ("1yr_reserved", "1-Year Reserved"),
        ("3yr_reserved", "3-Year Reserved"),
        ("annual_contract", "Annual Contract"),
        ("monthly_flex", "Monthly Flex"),
    ]

    SSO_STATUS_CHOICES = [
        ("sso_enforced", "SSO / SAML Enforced"),
        ("sso_optional", "SSO Optional"),
        ("local_auth_only", "Local Auth Only"),
        ("shadow_it_unapproved", "Shadow IT / Unmanaged"),
    ]

    APPROVAL_STATUS_CHOICES = [
        ("sanctioned", "IT Sanctioned"),
        ("under_review", "Under Security Review"),
        ("shadow_it_flagged", "Shadow IT Flagged"),
        ("consolidation_target", "Consolidation Target"),
        ("decommissioned", "Decommissioned"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("expiring_soon", "Expiring Soon"),
        ("underutilized", "Underutilized"),
        ("shadow_flagged", "Shadow IT Flagged"),
        ("suspended", "Suspended"),
        ("cancelled", "Cancelled"),
    ]

    STATUS_CSS = {
        "active": "badge-green",
        "expiring_soon": "badge-amber",
        "underutilized": "badge-info",
        "shadow_flagged": "badge-red",
        "suspended": "badge-amber",
        "cancelled": "badge-muted",
    }

    APPROVAL_CSS = {
        "sanctioned": "badge-green",
        "under_review": "badge-info",
        "shadow_it_flagged": "badge-red",
        "consolidation_target": "badge-amber",
        "decommissioned": "badge-muted",
    }

    SSO_CSS = {
        "sso_enforced": "badge-green",
        "sso_optional": "badge-info",
        "local_auth_only": "badge-amber",
        "shadow_it_unapproved": "badge-red",
    }

    LOCKED_STATUSES = {"cancelled"}

    _TENANT_FK_FIELDS = (
        "org_unit",
        "vendor_party",
        "gl_expense_account",
        "business_owner",
        "technical_owner",
    )

    name = models.CharField(max_length=200)
    asset_kind = models.CharField(
        max_length=24,
        choices=ASSET_KIND_CHOICES,
        default="saas_application",
    )
    provider = models.CharField(
        max_length=24,
        choices=PROVIDER_CHOICES,
        default="aws",
    )
    external_account_id = models.CharField(max_length=120, blank=True)
    cloud_resource_id = models.CharField(max_length=200, blank=True)
    cloud_region = models.CharField(max_length=64, blank=True)
    environment = models.CharField(
        max_length=24,
        choices=ENVIRONMENT_CHOICES,
        default="corporate_saas",
    )
    resource_tags = models.JSONField(default=dict, blank=True)

    billing_cadence = models.CharField(
        max_length=16,
        choices=BILLING_CADENCE_CHOICES,
        default="monthly",
    )
    commitment_term = models.CharField(
        max_length=24,
        choices=COMMITMENT_TERM_CHOICES,
        default="annual_contract",
    )
    monthly_recurring_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    annual_contract_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    # Global Currency table (shared across tenants)
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cloud_asset_subscriptions",
    )

    provisioned_seats = models.PositiveIntegerField(default=0)
    active_seats_30d = models.PositiveIntegerField(default=0)
    sso_status = models.CharField(
        max_length=28,
        choices=SSO_STATUS_CHOICES,
        default="sso_optional",
    )
    approval_status = models.CharField(
        max_length=28,
        choices=APPROVAL_STATUS_CHOICES,
        default="sanctioned",
    )
    renewal_date = models.DateField(null=True, blank=True)
    cancellation_notice_days = models.PositiveSmallIntegerField(default=30)
    auto_renew = models.BooleanField(default=True)
    vendor_eol_date = models.DateField(null=True, blank=True)

    status = models.CharField(
        max_length=24,
        choices=STATUS_CHOICES,
        default="active",
        editable=False,
    )
    last_finops_sync_at = models.DateTimeField(null=True, blank=True, editable=False)
    decommissioned_at = models.DateTimeField(null=True, blank=True, editable=False)

    org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cloud_asset_subscriptions",
    )
    vendor_party = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cloud_asset_subscriptions",
    )
    gl_expense_account = models.ForeignKey(
        "accounting.GLAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cloud_asset_subscriptions",
    )
    business_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="business_owned_cloud_assets",
    )
    technical_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="technical_owned_cloud_assets",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name", "-number"]
        verbose_name = "Cloud Asset & Subscription"
        verbose_name_plural = "Cloud Assets & Subscriptions"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_itcl_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_itcl_ten_stat"),
            models.Index(fields=["tenant", "provider"], name="idx_itcl_ten_prov"),
            models.Index(fields=["tenant", "approval_status"], name="idx_itcl_ten_aprv"),
            models.Index(fields=["tenant", "renewal_date"], name="idx_itcl_ten_ren"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name}"

    def clean(self):
        super().clean()
        errors = validate_tenant_fks(self, self._TENANT_FK_FIELDS)
        if self.resource_tags is not None and not isinstance(self.resource_tags, dict):
            add_field_error(
                errors,
                "resource_tags",
                "Resource tags must be a JSON object of key/value pairs.",
            )
        if self.monthly_recurring_cost is not None and self.monthly_recurring_cost < 0:
            add_field_error(
                errors,
                "monthly_recurring_cost",
                "Monthly recurring cost cannot be negative.",
            )
        if self.annual_contract_value is not None and self.annual_contract_value < 0:
            add_field_error(
                errors,
                "annual_contract_value",
                "Annual contract value cannot be negative.",
            )
        if self.provisioned_seats and self.active_seats_30d > self.provisioned_seats:
            add_field_error(
                errors,
                "active_seats_30d",
                "Active seats in last 30 days cannot exceed provisioned seats.",
            )
        if errors:
            raise ValidationError(errors)

    def compute_operational_status(self, today=None):
        """Derive operational status unless manually suspended or cancelled."""
        if self.status in ("suspended", "cancelled"):
            return self.status
        today = today or timezone.now().date()
        if (
            self.approval_status == "shadow_it_flagged"
            or self.sso_status == "shadow_it_unapproved"
        ):
            return "shadow_flagged"
        if self.renewal_date and self.renewal_date <= today + timedelta(days=30):
            return "expiring_soon"
        if (
            self.provisioned_seats
            and self.provisioned_seats > 0
            and (self.active_seats_30d * 100 / self.provisioned_seats) < 50
        ):
            return "underutilized"
        return "active"

    @property
    def seat_utilization_pct(self):
        if not self.provisioned_seats:
            return None
        return round((self.active_seats_30d * 100.0) / self.provisioned_seats, 1)

    @property
    def wasted_monthly_spend(self):
        if not self.provisioned_seats or self.active_seats_30d >= self.provisioned_seats:
            return Decimal("0.00")
        unused = Decimal(self.provisioned_seats - self.active_seats_30d)
        ratio = unused / Decimal(self.provisioned_seats)
        mrc = self.monthly_recurring_cost or Decimal("0.00")
        return (ratio * mrc).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def has_required_tags(self):
        tags = self.resource_tags if isinstance(self.resource_tags, dict) else {}
        return all(bool(str(tags.get(k, "")).strip()) for k in ("env", "cost_center", "owner"))

    @property
    def is_eol_expired(self):
        return bool(self.vendor_eol_date and self.vendor_eol_date < timezone.now().date())

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def approval_badge_class(self):
        return self.APPROVAL_CSS.get(self.approval_status, "badge-slate")

    @property
    def sso_badge_class(self):
        return self.SSO_CSS.get(self.sso_status, "badge-slate")

    @property
    def is_locked(self):
        return self.status in self.LOCKED_STATUSES
