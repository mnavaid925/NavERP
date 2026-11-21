from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class LabSpecification(TenantNumbered):
    NUMBER_PREFIX = "QSPC"

    SPEC_TYPE_CHOICES = [
        ("raw_material", "Raw Material Release"),
        ("in_process", "In-Process Control (IPC)"),
        ("finished_product", "Finished Product Release"),
        ("stability", "Stability Specification"),
        ("cleaning_verification", "Cleaning Verification / Swab"),
        ("environmental", "Environmental Monitoring Limit"),
    ]

    TEST_CATEGORY_CHOICES = [
        ("chemical", "Chemical / Wet Chemistry"),
        ("physical", "Physical Testing / Appearance"),
        ("microbiological", "Microbiological Bioburden / Sterility"),
        ("chromatographic", "Chromatography (HPLC / GC / UPLC)"),
        ("spectroscopic", "Spectroscopy (UV-Vis / FT-IR / NIR)"),
        ("biological_assay", "Biological / Immuno-Assay"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("under_review", "Under Review"),
        ("approved", "Approved / Active"),
        ("superseded", "Superseded"),
        ("retired", "Retired"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "under_review": "badge-amber",
        "approved": "badge-green",
        "superseded": "badge-muted",
        "retired": "badge-muted",
    }

    TEST_CATEGORY_CSS = {
        "chemical": "badge-info",
        "physical": "badge-slate",
        "microbiological": "badge-red",
        "chromatographic": "badge-purple",
        "spectroscopic": "badge-info",
        "biological_assay": "badge-amber",
    }

    title = models.CharField(max_length=255)
    specification_type = models.CharField(
        max_length=30,
        choices=SPEC_TYPE_CHOICES,
        default="finished_product",
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
        db_index=True,
    )
    version = models.CharField(max_length=20, default="1.0")
    product_code = models.CharField(max_length=100, db_index=True)
    product_name = models.CharField(max_length=255)
    analytical_method_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="e.g. AM-QC-304 / USP <621>",
    )
    test_category = models.CharField(
        max_length=30,
        choices=TEST_CATEGORY_CHOICES,
        default="chemical",
    )
    sop_document = models.ForeignKey(
        "quality.ControlledDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lab_specifications",
    )
    target_parameter_name = models.CharField(
        max_length=150,
        help_text="Primary parameter tested, e.g. Assay Purity, Dissolution, pH, Endotoxin",
    )
    parameter_unit = models.CharField(
        max_length=25,
        blank=True,
        help_text="e.g., %, pH, EU/mL, ppm, mg/mL",
    )
    lower_limit = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
    )
    upper_limit = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
    )
    target_value = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
    )
    text_acceptance_criteria = models.TextField(
        blank=True,
        help_text="Qualitative visual or spectroscopic criteria",
    )
    method_validation_reference = models.CharField(max_length=150, blank=True)
    method_validation_date = models.DateField(null=True, blank=True)
    effective_date = models.DateField(null=True, blank=True)
    review_due_date = models.DateField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_lab_specifications",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["product_code", "-version", "title"]
        verbose_name = "Lab Specification"
        verbose_name_plural = "Lab Specifications"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qspc_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "product_code"], name="idx_qspc_ten_prod"),
            models.Index(fields=["tenant", "specification_type"], name="idx_qspc_ten_type"),
            models.Index(fields=["tenant", "status"], name="idx_qspc_ten_status"),
            models.Index(fields=["tenant", "test_category"], name="idx_qspc_ten_cat"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title} v{self.version} ({self.product_code})"

    @property
    def is_active(self):
        return self.status == "approved"

    @property
    def is_overdue_review(self):
        return self.review_due_date is not None and self.review_due_date < timezone.now().date()

    def get_status_badge(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    def get_test_category_badge(self):
        return self.TEST_CATEGORY_CSS.get(self.test_category, "badge-info")
