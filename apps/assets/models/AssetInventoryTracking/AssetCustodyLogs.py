from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetCustodyLog(TenantNumbered):
    """Tool crib check-in/check-out lending, borrower liability, return due dates, and condition inspections [ACHK-]."""

    NUMBER_PREFIX = "ACHK"

    ACTION_TYPE_CHOICES = [
        ("checkout", "Equipment Checkout"),
        ("checkin", "Equipment Return (Checkin)"),
        ("custody_transfer", "Peer-to-Peer Transfer"),
        ("extension", "Loan Extension"),
    ]

    STATUS_CHOICES = [
        ("active_loan", "Active Loan"),
        ("returned", "Returned & Checked In"),
        ("overdue", "Overdue for Return"),
        ("damaged_returned", "Returned Damaged"),
        ("unreturned_lost", "Unreturned / Presumed Lost"),
    ]

    STATUS_CSS = {
        "active_loan": "badge-amber",
        "returned": "badge-green",
        "overdue": "badge-red",
        "damaged_returned": "badge-red",
        "unreturned_lost": "badge-muted",
    }

    CHECKOUT_CONDITION_CHOICES = [
        ("excellent", "Excellent (Like New)"),
        ("good", "Good (Standard Wear)"),
        ("fair", "Fair (Operational Wear)"),
    ]

    RETURN_CONDITION_CHOICES = [
        ("excellent", "Excellent"),
        ("good", "Good"),
        ("fair", "Fair"),
        ("damaged", "Damaged"),
        ("inoperable", "Inoperable / Broken"),
    ]

    asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.CASCADE,
        related_name="custody_logs",
        help_text="Operational physical asset or serialized tool lent",
    )
    action_type = models.CharField(max_length=30, choices=ACTION_TYPE_CHOICES, default="checkout")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="active_loan")

    # People & Accountability
    borrower = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_custody_loans",
        help_text="Employee or contractor receiving equipment",
    )
    borrower_name = models.CharField(max_length=120, blank=True, help_text="Individual name or badge number of borrower")
    crib_attendant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_asset_loans",
        help_text="Tool crib attendant or supervisor issuing the loan",
    )

    # Operational Context
    purpose = models.CharField(max_length=200, blank=True, help_text="Purpose of loan, shift, or work order scope")
    work_order_reference = models.CharField(max_length=64, blank=True, help_text="Optional Maintenance Work Order number or task reference")
    project_reference = models.CharField(max_length=100, blank=True, help_text="Capital project or cost center code")

    # Timeline & Tracking
    checkout_date = models.DateTimeField(default=timezone.now, help_text="Timestamp equipment was checked out")
    expected_return_date = models.DateField(null=True, blank=True, help_text="Date equipment must be returned to tool crib")
    actual_return_date = models.DateTimeField(null=True, blank=True, help_text="Timestamp equipment was checked back in")

    # Pre- and Post-Loan Condition Inspection
    checkout_condition = models.CharField(max_length=20, choices=CHECKOUT_CONDITION_CHOICES, default="good")
    return_condition = models.CharField(max_length=20, choices=RETURN_CONDITION_CHOICES, blank=True)
    condition_notes = models.TextField(blank=True, help_text="Inspection notes regarding tool wear, scratches, or missing accessories")

    # Liability & Electronic Acknowledgment
    borrower_signature_acknowledged = models.BooleanField(
        default=True,
        help_text="Borrower electronically acknowledged custody and financial liability for damage or loss",
    )
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "assets_custody_log"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="assets_achk_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_achk_ten_stat"),
            models.Index(fields=["tenant", "action_type"], name="idx_achk_ten_act"),
            models.Index(fields=["tenant", "asset"], name="idx_achk_ten_asset"),
            models.Index(fields=["tenant", "expected_return_date"], name="idx_achk_ten_expdate"),
            models.Index(fields=["tenant", "created_at"], name="idx_achk_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} — {self.asset.number if self.asset else 'Asset'} ({self.get_action_type_display()})"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")
