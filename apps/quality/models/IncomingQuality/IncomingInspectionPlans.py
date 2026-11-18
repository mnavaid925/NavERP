from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.quality.models._base import TenantNumbered


class IncomingInspectionPlan(TenantNumbered):
    NUMBER_PREFIX = "QIIP"

    SAMPLING_STANDARD_CHOICES = [
        ("ansi_asq_z14", "ANSI/ASQ Z1.4 (Attribute Sampling)"),
        ("iso_2859_1", "ISO 2859-1 (Lot-by-Lot Inspection)"),
        ("c_zero_squeglia", "Zero-Defect (c=0 Squeglia Plan)"),
        ("fixed_percentage", "Fixed Percentage Sampling"),
        ("one_hundred_pct", "100% Comprehensive Inspection"),
    ]

    INSPECTION_LEVEL_CHOICES = [
        ("level_1", "General Level I (Reduced)"),
        ("level_2", "General Level II (Normal / Default)"),
        ("level_3", "General Level III (Tightened)"),
        ("special_s1", "Special Level S-1"),
        ("special_s2", "Special Level S-2"),
        ("special_s3", "Special Level S-3"),
        ("special_s4", "Special Level S-4"),
    ]

    INSPECTION_SEVERITY_CHOICES = [
        ("normal", "Normal Inspection"),
        ("tightened", "Tightened Inspection"),
        ("reduced", "Reduced Inspection"),
    ]

    INSPECTION_FREQUENCY_CHOICES = [
        ("every_lot", "Every Received Lot"),
        ("skip_lot", "Skip-Lot (1 in N Lots)"),
        ("dock_to_stock", "Dock-to-Stock (Bypass Inspection)"),
        ("first_article", "First Article Inspection (FAI)"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("under_revision", "Under Revision"),
        ("obsolete", "Obsolete"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "active": "badge-green",
        "under_revision": "badge-amber",
        "obsolete": "badge-muted",
    }

    FREQUENCY_CSS = {
        "every_lot": "badge-info",
        "skip_lot": "badge-slate",
        "dock_to_stock": "badge-green",
        "first_article": "badge-amber",
    }

    title = models.CharField(max_length=150)
    item_code = models.CharField(max_length=50, db_index=True)
    item_name = models.CharField(max_length=150)
    revision = models.CharField(max_length=20, default="A")
    supplier = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incoming_inspection_plans",
    )
    sampling_standard = models.CharField(
        max_length=25,
        choices=SAMPLING_STANDARD_CHOICES,
        default="ansi_asq_z14",
        db_index=True,
    )
    inspection_level = models.CharField(
        max_length=15,
        choices=INSPECTION_LEVEL_CHOICES,
        default="level_2",
    )
    inspection_severity = models.CharField(
        max_length=15,
        choices=INSPECTION_SEVERITY_CHOICES,
        default="normal",
    )
    inspection_frequency = models.CharField(
        max_length=20,
        choices=INSPECTION_FREQUENCY_CHOICES,
        default="every_lot",
        db_index=True,
    )
    skip_lot_interval = models.PositiveIntegerField(
        default=5,
        help_text="Inspect 1 in every N lots if skip-lot enabled",
    )
    aql_critical = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=0.00,
        help_text="Critical Defect AQL (typically 0.00)",
    )
    aql_major = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=1.00,
        help_text="Major Defect AQL (typically 1.00 or 0.65)",
    )
    aql_minor = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=4.00,
        help_text="Minor Defect AQL (typically 4.00 or 2.50)",
    )
    requires_coa = models.BooleanField(
        default=True,
        help_text="CoA must be received and verified prior to lot release",
    )
    requires_coc = models.BooleanField(
        default=False,
        help_text="Certificate of Conformance required",
    )
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default="draft",
        db_index=True,
    )
    characteristics_matrix = models.JSONField(
        default=list,
        blank=True,
        help_text="List of CTQ specs: [{name, type, usl, lsl, target, unit, test_method}]",
    )
    sop_document = models.ForeignKey(
        "quality.ControlledDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="linked_inspection_plans",
    )
    assigned_team = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incoming_inspection_plans",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Incoming Inspection Plan"
        verbose_name_plural = "Incoming Inspection Plans"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="quality_qiip_ten_num_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qiip_ten_status"),
            models.Index(fields=["tenant", "item_code"], name="idx_qiip_ten_item"),
            models.Index(fields=["tenant", "supplier"], name="idx_qiip_ten_supp"),
            models.Index(fields=["tenant", "inspection_frequency"], name="idx_qiip_ten_freq"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title} ({self.item_code} Rev {self.revision})"

    def get_absolute_url(self):
        return reverse("quality:incoming_inspection_plan_detail", kwargs={"pk": self.pk})

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def frequency_css(self):
        return self.FREQUENCY_CSS.get(self.inspection_frequency, "badge-slate")
