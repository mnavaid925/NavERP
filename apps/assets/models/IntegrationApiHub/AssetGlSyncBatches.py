import json
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetGlSyncBatch(TenantNumbered):
    """
    Financial and General Ledger synchronization batch linking asset depreciation,
    capitalization, maintenance work-order cost rollups, and PO asset clearings
    to accounting JournalEntry / GLAccount reconciliation.
    """

    NUMBER_PREFIX = "AGLS"

    SYNC_DOMAIN_CHOICES = [
        ("depreciation_posting", "Depreciation Posting"),
        ("capitalization_sync", "Capitalization Sync"),
        ("work_order_cost_rollup", "Work Order Cost Rollup"),
        ("asset_subledger_sync", "Asset Subledger Sync"),
        ("po_asset_clearing", "PO Asset Clearing"),
    ]

    SYNC_DIRECTION_CHOICES = [
        ("inbound", "Inbound"),
        ("outbound", "Outbound"),
        ("bidirectional", "Bidirectional"),
    ]

    RECONCILIATION_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("reconciled", "Reconciled"),
        ("variance_flagged", "Variance Flagged"),
        ("resolved", "Resolved"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("ready", "Ready"),
        ("posted", "Posted"),
        ("simulated", "Simulated"),
        ("failed", "Failed"),
        ("reconciled", "Reconciled"),
    ]

    STATUS_BADGE_MAP = {
        "draft": "badge-slate",
        "ready": "badge-info",
        "posted": "badge-green",
        "simulated": "badge-amber",
        "failed": "badge-red",
        "reconciled": "badge-green",
    }

    RECON_BADGE_MAP = {
        "pending": "badge-slate",
        "reconciled": "badge-green",
        "variance_flagged": "badge-red",
        "resolved": "badge-info",
    }

    GL_POSTING_DOMAINS = frozenset(
        {
            "depreciation_posting",
            "capitalization_sync",
            "work_order_cost_rollup",
        }
    )

    connector = models.ForeignKey(
        "assets.AssetIntegrationConnector",
        on_delete=models.PROTECT,
        related_name="gl_sync_batches",
    )
    sync_domain = models.CharField(
        max_length=32, choices=SYNC_DOMAIN_CHOICES, default="depreciation_posting"
    )
    sync_direction = models.CharField(
        max_length=20, choices=SYNC_DIRECTION_CHOICES, default="outbound"
    )
    external_batch_ref = models.CharField(max_length=100, blank=True)

    fiscal_period = models.ForeignKey(
        "accounting.FiscalPeriod",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="asset_gl_sync_batches",
    )
    gl_account = models.ForeignKey(
        "accounting.GLAccount",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="asset_gl_sync_debit_batches",
    )
    offset_gl_account = models.ForeignKey(
        "accounting.GLAccount",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="asset_gl_sync_credit_batches",
    )
    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gl_sync_batches",
    )
    purchase_order = models.ForeignKey(
        "scm.PurchaseOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_gl_sync_batches",
    )
    capitalization = models.ForeignKey(
        "assets.AssetCapitalization",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gl_sync_batches",
    )
    depreciation_schedule = models.ForeignKey(
        "assets.AssetDepreciationSchedule",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gl_sync_batches",
    )
    maintenance_request = models.ForeignKey(
        "assets.AssetMaintenanceRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gl_sync_batches",
    )
    cost_center = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_gl_sync_batches",
    )
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="asset_gl_sync_batches",
    )

    batch_date = models.DateField(default=timezone.localdate)
    source_amount = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal("0.00")
    )
    target_gl_amount = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal("0.00")
    )
    variance_amount = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal("0.00"), editable=False
    )
    reconciliation_status = models.CharField(
        max_length=24,
        choices=RECONCILIATION_STATUS_CHOICES,
        default="pending",
        editable=False,
    )
    status = models.CharField(
        max_length=24,
        choices=STATUS_CHOICES,
        default="draft",
        editable=False,
    )

    records_processed = models.PositiveIntegerField(default=0, editable=False)
    records_succeeded = models.PositiveIntegerField(default=0, editable=False)
    records_failed = models.PositiveIntegerField(default=0, editable=False)
    synced_at = models.DateTimeField(null=True, blank=True, editable=False)
    journal_entry = models.ForeignKey(
        "accounting.JournalEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="asset_gl_sync_batches",
    )
    executed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="executed_asset_gl_batches",
    )

    field_mapping_json = models.TextField(blank=True, default="{}")
    payload_summary = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-batch_date", "-number"]
        verbose_name = "Asset GL Sync Batch"
        verbose_name_plural = "Asset GL Sync Batches"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_agls_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "sync_domain"],
                name="idx_agls_ten_dom",
            ),
            models.Index(
                fields=["tenant", "status"],
                name="idx_agls_ten_stat",
            ),
            models.Index(
                fields=["tenant", "reconciliation_status"],
                name="idx_agls_ten_rec",
            ),
        ]

    def __str__(self):
        return f"{self.number} · {self.get_sync_domain_display()} ({self.batch_date})"

    @property
    def status_badge_class(self):
        return self.STATUS_BADGE_MAP.get(self.status, "badge-slate")

    @property
    def reconciliation_badge_class(self):
        return self.RECON_BADGE_MAP.get(self.reconciliation_status, "badge-slate")

    def clean(self):
        super().clean()
        errors = {}
        if self.source_amount is not None and self.source_amount < Decimal("0.00"):
            errors["source_amount"] = "Source amount cannot be negative."
        if (
            self.target_gl_amount is not None
            and self.target_gl_amount < Decimal("0.00")
        ):
            errors["target_gl_amount"] = "Target GL amount cannot be negative."
        if (
            self.gl_account_id is not None
            and self.offset_gl_account_id is not None
            and self.gl_account_id == self.offset_gl_account_id
        ):
            errors["offset_gl_account"] = (
                "Offset GL account must differ from primary GL account."
            )
        raw_json = (self.field_mapping_json or "").strip()
        if raw_json:
            try:
                parsed = json.loads(raw_json)
            except ValueError as exc:
                errors["field_mapping_json"] = (
                    "Field mapping must be valid JSON syntax."
                )
            else:
                if not isinstance(parsed, dict):
                    errors["field_mapping_json"] = (
                        "Field mapping must be a JSON object ({...})."
                    )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        src = self.source_amount if self.source_amount is not None else Decimal("0.00")
        tgt = (
            self.target_gl_amount
            if self.target_gl_amount is not None
            else Decimal("0.00")
        )
        self.variance_amount = src - tgt
        if "update_fields" in kwargs and kwargs["update_fields"] is not None:
            uf = set(kwargs["update_fields"])
            if {"source_amount", "target_gl_amount"} & uf:
                uf.add("variance_amount")
                kwargs["update_fields"] = list(uf)
        super().save(*args, **kwargs)
