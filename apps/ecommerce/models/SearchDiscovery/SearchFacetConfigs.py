from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify

from apps.ecommerce.models._base import TenantNumbered


class SearchFacetConfig(TenantNumbered):
    NUMBER_PREFIX = "ESFC"

    SOURCE_TYPE_CHOICES = [
        ("category", "Category Hierarchy"),
        ("brand", "Product Brand"),
        ("price", "Price Range"),
        ("variant_option", "Variant Option / Attribute"),
        ("availability", "Stock Availability"),
        ("rating", "Customer Rating"),
        ("tag", "Product Tag"),
    ]
    WIDGET_TYPE_CHOICES = [
        ("checkbox", "Checkboxes (Multi-Select)"),
        ("color_swatch", "Color Swatches"),
        ("price_slider", "Price Range Slider"),
        ("rating_stars", "Rating Star Filter"),
        ("toggle", "Boolean Toggle"),
        ("dropdown", "Single-Select Dropdown"),
    ]
    FILTER_LOGIC_CHOICES = [
        ("disjunctive", "Disjunctive (OR)"),
        ("conjunctive", "Conjunctive (AND)"),
    ]

    name = models.CharField(
        max_length=100,
        help_text="Storefront display heading, e.g. 'Brand', 'Color', 'Price'",
    )
    code = models.CharField(
        max_length=50,
        help_text="Machine identifier, e.g. 'brand', 'price', 'category', 'color', 'size', 'in_stock'",
    )
    source_type = models.CharField(
        max_length=30,
        choices=SOURCE_TYPE_CHOICES,
        default="brand",
    )
    option_key = models.CharField(
        max_length=50,
        blank=True,
        help_text="Key in ProductVariant.option_values (e.g. 'Size', 'Color') when source_type='variant_option'",
    )
    widget_type = models.CharField(
        max_length=20,
        choices=WIDGET_TYPE_CHOICES,
        default="checkbox",
    )
    filter_logic = models.CharField(
        max_length=15,
        choices=FILTER_LOGIC_CHOICES,
        default="disjunctive",
        help_text="Disjunctive (OR) allows multi-select within facet; Conjunctive (AND) requires all selected values",
    )
    display_order = models.PositiveIntegerField(
        default=0,
        help_text="Sidebar vertical presentation order",
    )
    is_collapsed_by_default = models.BooleanField(default=False)
    max_values_shown = models.PositiveIntegerField(
        default=10,
        help_text="Max filter items displayed before 'Show More' toggle",
    )
    is_searchable = models.BooleanField(
        default=False,
        help_text="Show in-facet search box for facets with many values like Brands",
    )
    category_scope = models.ForeignKey(
        "ecommerce.StoreCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scoped_facets",
        help_text="Optional: Restrict this filter to a specific category hierarchy",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_esfc_tenant_num_uniq",
            ),
            models.UniqueConstraint(
                fields=["tenant", "code", "category_scope"],
                name="ecommerce_esfc_code_cat_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "is_active", "display_order"],
                name="idx_esfc_ten_act_disp",
            ),
        ]

    def __str__(self):
        return f"{self.number} - {self.name} ({self.code})"

    def clean(self):
        super().clean()
        if self.code:
            self.code = slugify(self.code).replace("-", "_")
        if self.source_type == "variant_option" and not self.option_key:
            raise ValidationError(
                {"option_key": "Option key (e.g. 'Size', 'Color') is required when source type is Variant Option."}
            )
