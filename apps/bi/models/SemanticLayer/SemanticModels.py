from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class SemanticModel(TenantNumbered):
    NUMBER_PREFIX = "BSMD"

    MODEL_TYPE_CHOICES = [
        ("fact", "Fact Model"),
        ("dimension", "Dimension Model"),
        ("bridge", "Bridge / Disambiguation Model"),
        ("virtual_view", "Virtual Analytical View"),
        ("reusable_dataset", "Certified Reusable Dataset"),
    ]

    SCD_TYPE_CHOICES = [
        ("type_0", "Type 0: Fixed / Non-Changing"),
        ("type_1", "Type 1: Overwrite In-Place"),
        ("type_2", "Type 2: Historical Versioning (Start/End Date)"),
        ("type_3", "Type 3: Previous Value Tracking"),
    ]

    ACCESS_TIER_CHOICES = [
        ("public", "Public (Tenant-Wide)"),
        ("department", "Departmental Only"),
        ("restricted", "Restricted / Confidential"),
    ]

    CERTIFICATION_STATUS_CHOICES = [
        ("draft", "Draft / In Development"),
        ("in_review", "Under Review & Validation"),
        ("certified", "Certified Single Source of Truth"),
        ("deprecated", "Deprecated / Sunset Pending"),
    ]

    name = models.CharField(max_length=150, help_text="Human-friendly business model name")
    code = models.SlugField(max_length=50, help_text="Unique model identifier slug")
    model_type = models.CharField(max_length=25, choices=MODEL_TYPE_CHOICES, default="fact")

    warehouse_table = models.ForeignKey(
        "bi.WarehouseTable",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="semantic_models",
        help_text="Underlying warehouse table",
    )
    data_mart = models.ForeignKey(
        "bi.DataMart",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="semantic_models",
        help_text="Associated analytical data mart",
    )

    primary_key_column = models.CharField(
        max_length=100,
        default="id",
        help_text="Surrogate or physical primary key column",
    )
    natural_key_columns = models.CharField(
        max_length=255,
        blank=True,
        help_text="Business natural keys (comma-separated)",
    )
    grain_description = models.CharField(
        max_length=255,
        blank=True,
        help_text="Analytical granularity, e.g. One row per completed sales order item",
    )
    is_conformed_dimension = models.BooleanField(
        default=False,
        help_text="Shared dimension across multiple business processes / marts",
    )
    scd_type = models.CharField(
        max_length=20,
        choices=SCD_TYPE_CHOICES,
        default="type_1",
        help_text="Slowly changing dimension policy",
    )

    is_virtual_view = models.BooleanField(
        default=False,
        help_text="Computed on-the-fly via custom SQL expression",
    )
    sql_definition = models.TextField(
        blank=True,
        help_text="Custom SQL query for virtual analytical views",
    )
    access_tier = models.CharField(
        max_length=25,
        choices=ACCESS_TIER_CHOICES,
        default="department",
    )

    certification_status = models.CharField(
        max_length=25,
        choices=CERTIFICATION_STATUS_CHOICES,
        default="draft",
    )
    certified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    certified_at = models.DateTimeField(null=True, blank=True)
    certification_notes = models.TextField(blank=True)

    source_fingerprint = models.CharField(
        max_length=64,
        blank=True,
        help_text="Schema hash from warehouse table inspection",
    )
    last_introspected_at = models.DateTimeField(null=True, blank=True)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bi_semantic_models_owned",
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "bi_semantic_model"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="bi_bsmd_tenant_code_uniq"),
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bsmd_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "model_type"], name="idx_bsmd_ten_mtype"),
            models.Index(fields=["tenant", "certification_status"], name="idx_bsmd_ten_cert"),
            models.Index(fields=["tenant", "warehouse_table"], name="idx_bsmd_ten_whtbl"),
            models.Index(fields=["tenant", "is_active"], name="idx_bsmd_ten_active"),
        ]

    def __str__(self):
        return f"{self.name} ({self.number})"

    def get_absolute_url(self):
        return reverse("bi:semantic_model_detail", kwargs={"pk": self.pk})
