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
            models.Index(fields=["tenant", "hierarchy_type", "level"], name="idx_bmhr_ten_htype_lvl"),
            models.Index(fields=["tenant", "parent"], name="idx_bmhr_ten_parent"),
            models.Index(fields=["tenant", "path"], name="idx_bmhr_ten_path"),
            models.Index(fields=["tenant", "golden_record"], name="idx_bmhr_ten_grec"),
            models.Index(fields=["tenant", "is_active"], name="idx_bmhr_ten_active"),
        ]

    def __init__(self, *args, **kwargs):
        if "node_type" in kwargs and "relationship_kind" not in kwargs:
            kwargs["relationship_kind"] = kwargs.pop("node_type")
        super().__init__(*args, **kwargs)

    @property
    def node_type(self):
        return self.relationship_kind

    @node_type.setter
    def node_type(self, value):
        self.relationship_kind = value

    def __str__(self):
        return f"{self.number} - {self.name} ({self.get_hierarchy_type_display()})"

    def get_absolute_url(self):
        return reverse("bi:mdm_hierarchy_node_detail", kwargs={"pk": self.pk})

    def save(self, *args, **kwargs):
        if not self.code and self.name:
            from django.utils.text import slugify
            self.code = slugify(self.name)[:80]

        old_path = None
        if self.pk:
            existing = MdmHierarchyNode.objects.filter(pk=self.pk).values("path").first()
            if existing:
                old_path = existing["path"]

        if self.parent:
            if not self.parent.path:
                self.parent.save()
            self.level = self.parent.level + 1
        else:
            self.level = 0
        super().save(*args, **kwargs)

        # Re-compute materialized path with persisted pk
        parent_path = self.parent.path if (self.parent and self.parent.path) else ""
        if self.parent and not parent_path:
            parent_path = f"/{self.parent.pk}/"
        calculated_path = f"{parent_path}{self.pk}/" if parent_path else f"/{self.pk}/"

        path_changed = False
        if self.path != calculated_path:
            self.path = calculated_path
            super().save(update_fields=["path"])
            path_changed = True

        if old_path and (path_changed or old_path != self.path):
            self._cascade_descendants()

    def _cascade_descendants(self):
        for child in self.children.all():
            child.level = self.level + 1
            child.path = f"{self.path}{child.pk}/"
            MdmHierarchyNode.objects.filter(pk=child.pk).update(level=child.level, path=child.path)
            child._cascade_descendants()
