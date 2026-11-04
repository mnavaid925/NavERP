from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class DrillHierarchy(TenantNumbered):
    NUMBER_PREFIX = "BDHI"

    HIERARCHY_TYPE_CHOICES = [
        ("time", "Calendar / Fiscal Time (Year -> Quarter -> Month -> Day)"),
        ("geography", "Geographical Territory (Region -> Country -> State -> City)"),
        ("organizational", "Organizational Unit (Company -> Division -> Department)"),
        ("product", "Product Catalog (Category -> Subcategory -> Item)"),
        ("custom", "Custom Business Dimension Path"),
    ]

    semantic_model = models.ForeignKey(
        "bi.SemanticModel",
        on_delete=models.CASCADE,
        related_name="drill_hierarchies",
        help_text="Target dimensional semantic model",
    )

    name = models.CharField(max_length=150, help_text="Human-friendly hierarchy name")
    code = models.SlugField(max_length=50, help_text="Unique hierarchy identifier slug")

    hierarchy_type = models.CharField(
        max_length=25,
        choices=HIERARCHY_TYPE_CHOICES,
        default="time",
    )

    levels_json = models.JSONField(
        default=list,
        help_text="Ordered list of hierarchy levels [{'level': 1, 'name': 'Year', 'column': 'fiscal_year'}, ...]",
    )

    primary_drill_path = models.BooleanField(
        default=True,
        help_text="Default primary drill path for self-service slicing and dicing",
    )

    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "bi_drill_hierarchy"
        ordering = ["semantic_model", "name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "semantic_model", "code"], name="bi_bdhi_tenant_model_code_uniq"),
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bdhi_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "hierarchy_type"], name="idx_bdhi_ten_htype"),
            models.Index(fields=["tenant", "is_active"], name="idx_bdhi_ten_active"),
        ]

    def __str__(self):
        return f"{self.name} ({self.number})"

    def get_absolute_url(self):
        return reverse("bi:drill_hierarchy_detail", kwargs={"pk": self.pk})
