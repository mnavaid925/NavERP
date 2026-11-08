import re

from django.core.exceptions import ValidationError
from django.db import models

from apps.assets.models._base import TenantNumbered


class AssetSpecificationTemplate(TenantNumbered):
    """Dynamic technical specification parameter and custom attribute schema definition [ASPC-]."""

    NUMBER_PREFIX = "ASPC"

    DATA_TYPE_CHOICES = [
        ("text", "Text / Alphanumeric"),
        ("number", "Numeric (Decimal / Integer)"),
        ("boolean", "Yes / No (Boolean)"),
        ("date", "Date"),
        ("select", "Dropdown Selection"),
    ]

    DATA_TYPE_CSS = {
        "text": "badge-info",
        "number": "badge-green",
        "boolean": "badge-amber",
        "date": "badge-slate",
        "select": "badge-purple",
    }

    attribute_key = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Machine-readable attribute slug, e.g. rated_voltage, cooling_capacity_tons",
    )
    display_name = models.CharField(
        max_length=120,
        help_text="Human-readable label, e.g. Rated Operating Voltage",
    )
    category = models.ForeignKey(
        "assets.AssetCategory",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="spec_templates",
        help_text="Apply this attribute to all assets in this category (inherited by children)",
    )
    model = models.ForeignKey(
        "assets.AssetModel",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="spec_templates",
        help_text="Apply this attribute to all assets referencing this equipment model",
    )
    data_type = models.CharField(
        max_length=16,
        choices=DATA_TYPE_CHOICES,
        default="text",
    )
    unit_of_measure = models.CharField(
        max_length=24,
        blank=True,
        help_text="Standard engineering unit, e.g. V, kW, PSI, bar, GPM, RPM, ton, degC",
    )
    default_value = models.CharField(
        max_length=255,
        blank=True,
        help_text="Default value prefilled for new assets",
    )
    dropdown_options = models.TextField(
        blank=True,
        help_text="Comma-separated option choices for 'select' data type, e.g. R-134a, R-410A, R-1234ze",
    )
    min_numeric_value = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Optional minimum acceptable numerical bound",
    )
    max_numeric_value = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Optional maximum acceptable numerical bound",
    )
    validation_regex = models.CharField(
        max_length=120,
        blank=True,
        help_text="Optional regex pattern for string validation, e.g. ^[0-9]{3}-[A-Z]{2}$",
    )
    is_required = models.BooleanField(
        default=False,
        help_text="Must be populated during asset registration and maintenance inspection",
    )
    is_filterable = models.BooleanField(
        default=True,
        help_text="Surfaced as a search and filtering parameter on asset registers",
    )
    display_order = models.PositiveIntegerField(
        default=10,
        help_text="Sequence on specification sheets and inspection cards",
    )
    help_text = models.CharField(
        max_length=255,
        blank=True,
        help_text="Contextual guidance shown to technicians and data entry operators",
    )

    class Meta:
        db_table = "assets_specification_template"
        ordering = ["display_order", "attribute_key"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="assets_aspc_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "category"], name="idx_aspc_ten_cat"),
            models.Index(fields=["tenant", "model"], name="idx_aspc_ten_model"),
            models.Index(fields=["tenant", "attribute_key"], name="idx_aspc_ten_attrkey"),
            models.Index(fields=["tenant", "data_type"], name="idx_aspc_ten_dtype"),
        ]

    def __str__(self):
        return f"{self.attribute_key} ({self.display_name})"

    def clean(self):
        super().clean()
        if not self.category_id and not self.model_id:
            raise ValidationError("A specification template must be assigned to either an Asset Category or an Asset Model.")

        if self.attribute_key:
            slug = self.attribute_key.strip().lower()
            if not re.match(r"^[a-z0-9_]+$", slug):
                raise ValidationError({"attribute_key": "Attribute key must contain only lowercase letters, digits, and underscores."})
            self.attribute_key = slug

        if self.min_numeric_value is not None and self.max_numeric_value is not None:
            if self.min_numeric_value > self.max_numeric_value:
                raise ValidationError({"min_numeric_value": "Minimum bound cannot exceed maximum bound."})

    @property
    def data_type_css(self):
        return self.DATA_TYPE_CSS.get(self.data_type, "badge-slate")

    @property
    def target_scope(self):
        if self.model:
            return f"Model: {self.model.model_number}"
        if self.category:
            return f"Category: {self.category.code}"
        return "Global"
