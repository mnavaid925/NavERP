from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class MdmHierarchyNode(TenantNumbered):
    NUMBER_PREFIX = "BMHR"

    HIERARCHY_TYPE_CHOICES = [
        ("corporate_legal", "Corporate & Legal Subsidiary Tree"),
        ("account_group", "Sales & Account Grouping Hierarchy"),
        ("product_taxonomy", "Product Category & SKU Taxonomy"),
        ("org_reporting", "Organizational & Departmental Hierarchy"),
        ("cost_center_rollup", "Financial Cost Center Rollup"),
        ("asset_location", "Physical Facility & Asset Location Tree"),
    ]

    name = models.CharField(max_length=200)
    code = models.SlugField(max_length=80)
    hierarchy_type = models.CharField(
        max_length=30,
        choices=HIERARCHY_TYPE_CHOICES,
        default="corporate_legal",
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
    )
    level = models.PositiveIntegerField(default=1)
    path = models.CharField(max_length=500, blank=True, db_index=True)

    golden_record = models.ForeignKey(
        "bi.MdmGoldenRecord",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="hierarchy_nodes",
    )
    party = models.ForeignKey(
        "core.Party",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mdm_hierarchy_nodes",
    )
    org_unit = models.ForeignKey(
        "core.OrgUnit",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mdm_hierarchy_nodes",
    )
    item_category = models.ForeignKey(
        "scm.ItemCategory",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mdm_hierarchy_nodes",
    )

    relationship_kind = models.CharField(max_length=60, default="parent_child")
    sort_order = models.PositiveIntegerField(default=10)
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "bi_mdm_hierarchy_node"
        ordering = ["hierarchy_type", "level", "sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "hierarchy_type", "code"],
                name="bi_bmhr_tenant_type_code_uniq",
            ),
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="bi_bmhr_tenant_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "hierarchy_type"], name="idx_bmhr_ten_htype"),
            models.Index(fields=["tenant", "parent"], name="idx_bmhr_ten_parent"),
            models.Index(fields=["tenant", "path"], name="idx_bmhr_ten_path"),
            models.Index(fields=["tenant", "golden_record"], name="idx_bmhr_ten_grec"),
            models.Index(fields=["tenant", "is_active"], name="idx_bmhr_ten_active"),
        ]

    def __str__(self):
        return f"{self.number} - {self.name} ({self.get_hierarchy_type_display()})"

    def get_absolute_url(self):
        return reverse("bi:mdm_hierarchy_node_detail", kwargs={"pk": self.pk})

    def save(self, *args, **kwargs):
        if self.parent:
            self.level = self.parent.level + 1
        else:
            self.level = 1
        super().save(*args, **kwargs)
        # Re-compute materialized path with persisted pk
        calculated_path = f"{self.parent.path}{self.pk}/" if self.parent and self.parent.path else f"/{self.pk}/"
        if self.path != calculated_path:
            self.path = calculated_path
            super().save(update_fields=["path"])
