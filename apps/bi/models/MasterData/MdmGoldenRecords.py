from decimal import Decimal
from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class MdmGoldenRecord(TenantNumbered):
    NUMBER_PREFIX = "BMGR"

    DOMAIN_CHOICES = [
        ("customer", "Customer Master"),
        ("vendor", "Vendor / Supplier Master"),
        ("product", "Product / Material Master"),
        ("asset", "Asset / Facility Master"),
        ("employee", "Employee / Personnel Master"),
        ("account", "General Ledger Account Master"),
        ("custom", "Custom Domain Master"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft / Staging"),
        ("pending_review", "Pending Steward Review"),
        ("approved", "Approved / Certified Active"),
        ("in_dispute", "In Dispute / Exception Flagged"),
        ("merged", "Merged / Consolidated"),
        ("superseded", "Superseded"),
        ("archived", "Archived"),
    ]

    TRUST_TIER_CHOICES = [
        ("gold", "Gold Tier (Certified, Complete)"),
        ("silver", "Silver Tier (Standard Confidence)"),
        ("bronze", "Bronze Tier (Partial / Unverified)"),
    ]

    name = models.CharField(max_length=255)
    code = models.SlugField(max_length=80)
    domain = models.CharField(max_length=30, choices=DOMAIN_CHOICES, default="customer")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="approved")
    trust_tier = models.CharField(max_length=20, choices=TRUST_TIER_CHOICES, default="silver")
    confidence_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("100.00"))

    tax_id = models.CharField(max_length=64, blank=True)
    primary_email = models.EmailField(blank=True)
    primary_phone = models.CharField(max_length=40, blank=True)
    primary_address = models.TextField(blank=True)

    party = models.ForeignKey(
        "core.Party",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mdm_golden_records",
    )
    party_role = models.ForeignKey(
        "core.PartyRole",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mdm_golden_records",
    )
    item = models.ForeignKey(
        "scm.Item",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mdm_golden_records",
    )
    asset = models.ForeignKey(
        "scm.Asset",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mdm_golden_records",
    )
    warehouse_table = models.ForeignKey(
        "bi.WarehouseTable",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mdm_golden_records",
    )

    source_record_count = models.PositiveIntegerField(default=1)
    golden_attributes_json = models.JSONField(default=dict)
    source_crosswalks_json = models.JSONField(default=list)

    merged_into_record = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="absorbed_records",
    )
    merged_at = models.DateTimeField(null=True, blank=True)

    assigned_steward = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_golden_records",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    stewardship_notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "bi_mdm_golden_record"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "domain", "code"],
                name="bi_bmgr_tenant_dom_code_uniq",
            ),
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="bi_bmgr_tenant_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "domain"], name="idx_bmgr_ten_dom"),
            models.Index(fields=["tenant", "status"], name="idx_bmgr_ten_status"),
            models.Index(fields=["tenant", "trust_tier"], name="idx_bmgr_ten_tier"),
            models.Index(fields=["tenant", "party"], name="idx_bmgr_ten_party"),
            models.Index(fields=["tenant", "item"], name="idx_bmgr_ten_item"),
            models.Index(fields=["tenant", "tax_id"], name="idx_bmgr_ten_taxid"),
            models.Index(fields=["tenant", "is_active"], name="idx_bmgr_ten_active"),
        ]

    def __str__(self):
        return f"{self.number} - {self.name} ({self.get_domain_display()})"

    def get_absolute_url(self):
        return reverse("bi:mdm_golden_record_detail", kwargs={"pk": self.pk})
