from django.core.exceptions import ValidationError
from django.db import models

from apps.ecommerce.models._base import TenantNumbered


class StoreCategory(TenantNumbered):
    """Hierarchical customer-facing storefront taxonomy for eCommerce catalog."""

    NUMBER_PREFIX = "ECAT"

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
        help_text="Parent category for hierarchical navigation",
    )
    description = models.TextField(blank=True)
    image_url = models.URLField(blank=True, help_text="Category banner or icon URL")
    display_order = models.PositiveIntegerField(default=0, help_text="Sort order on storefront menus")
    is_active = models.BooleanField(default=True)
    include_in_menu = models.BooleanField(default=True, help_text="Display in top navigation bar")
    meta_title = models.CharField(max_length=160, blank=True, help_text="SEO title tag")
    meta_description = models.CharField(max_length=255, blank=True, help_text="SEO meta description")

    class Meta:
        ordering = ["display_order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecommerce_cat_tenant_num_uniq"),
            models.UniqueConstraint(fields=["tenant", "slug"], name="ecommerce_cat_tenant_slug_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "is_active", "display_order"], name="ecom_cat_tnt_act_ord_idx"),
        ]

    def clean(self):
        super().clean()
        if self.parent_id:
            if self.parent.tenant_id != self.tenant_id:
                raise ValidationError({"parent": "Parent category must belong to the same workspace."})
            if self.pk and self.parent_id == self.pk:
                raise ValidationError({"parent": "A category cannot be its own parent."})
            # Check for ancestor cycles
            ancestor = self.parent
            seen = {self.pk} if self.pk else set()
            while ancestor:
                if ancestor.pk in seen:
                    raise ValidationError({"parent": "Circular category hierarchy detected."})
                seen.add(ancestor.pk)
                ancestor = ancestor.parent

    @property
    def full_path(self):
        crumbs = self.get_breadcrumbs()
        return " > ".join([c["name"] for c in crumbs])

    def get_breadcrumbs(self):
        crumbs = []
        curr = self
        seen = set()
        while curr:
            if curr.pk in seen:
                break
            if curr.pk:
                seen.add(curr.pk)
            crumbs.append({"pk": curr.pk, "name": curr.name, "slug": curr.slug})
            curr = curr.parent
        crumbs.reverse()
        return crumbs

    def __str__(self):
        return self.name
