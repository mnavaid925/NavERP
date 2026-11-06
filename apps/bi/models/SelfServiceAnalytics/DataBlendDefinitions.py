from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from apps.bi.models._base import TenantNumbered


class DataBlendDefinition(TenantNumbered):
    NUMBER_PREFIX = "BBLD"

    SOURCE_TYPE_CHOICES = [
        ("semantic_model", "Governed Semantic Model"),
        ("warehouse_table", "Warehouse Fact/Dimension Table"),
    ]

    JOIN_TYPE_CHOICES = [
        ("inner", "Inner Join (Matching Records Only)"),
        ("left_outer", "Left Outer Join (All Primary Records)"),
        ("right_outer", "Right Outer Join (All Secondary Records)"),
        ("full_outer", "Full Outer Join (All Records from Both)"),
    ]

    CARDINALITY_CHOICES = [
        ("one_to_one", "One-to-One (1:1)"),
        ("one_to_many", "One-to-Many (1:N)"),
        ("many_to_one", "Many-to-One (N:1)"),
    ]

    STATUS_CHOICES = [
        ("active", "Active / In Use"),
        ("draft", "Draft Setup"),
        ("deprecated", "Deprecated"),
    ]

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120)
    description = models.TextField(blank=True)

    primary_source_type = models.CharField(max_length=30, choices=SOURCE_TYPE_CHOICES, default="semantic_model")
    primary_semantic_model = models.ForeignKey(
        "bi.SemanticModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="primary_blends",
    )
    primary_warehouse_table = models.ForeignKey(
        "bi.WarehouseTable",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="primary_blends",
    )

    secondary_source_type = models.CharField(max_length=30, choices=SOURCE_TYPE_CHOICES, default="semantic_model")
    secondary_semantic_model = models.ForeignKey(
        "bi.SemanticModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="secondary_blends",
    )
    secondary_warehouse_table = models.ForeignKey(
        "bi.WarehouseTable",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="secondary_blends",
    )

    join_type = models.CharField(max_length=20, choices=JOIN_TYPE_CHOICES, default="left_outer")
    join_keys_mapping_json = models.JSONField(
        default=list,
        help_text="Pairs of primary and secondary field keys to join on",
    )
    cardinality = models.CharField(max_length=20, choices=CARDINALITY_CHOICES, default="many_to_one")
    collision_resolution = models.CharField(max_length=50, default="prefix_secondary")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_data_blends",
    )

    class Meta:
        db_table = "bi_data_blend_definition"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "slug"], name="bi_bbld_tenant_slug_uniq"),
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bbld_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_bbld_ten_stat"),
            models.Index(fields=["tenant", "join_type"], name="idx_bbld_ten_jtype"),
            models.Index(fields=["tenant", "created_at"], name="idx_bbld_ten_created"),
        ]

    def __str__(self):
        return f"{self.name} ({self.number})"

    def save(self, *args, **kwargs):
        if not self.slug and self.name:
            base = slugify(self.name)[:100] or "blend"
            self.slug = base
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("bi:data_blend_definition_detail", kwargs={"pk": self.pk})

    @property
    def badge_status(self):
        mapping = {
            "active": "badge-green",
            "draft": "badge-amber",
            "deprecated": "badge-muted",
        }
        return mapping.get(self.status, "badge-slate")

    @property
    def badge_join(self):
        mapping = {
            "inner": "badge-info",
            "left_outer": "badge-green",
            "right_outer": "badge-amber",
            "full_outer": "badge-purple",
        }
        return mapping.get(self.join_type, "badge-slate")
