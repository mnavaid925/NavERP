"""SalesCustomEntityDefinition model for 8.19 Master Data & Configuration — Custom Fields & Objects."""
from django.core.exceptions import ValidationError
from django.db import models

from apps.sales.models._base import TenantNumbered


class SalesCustomEntityDefinition(TenantNumbered):
    """Metadata registry defining extensible custom entities, fields, relationships, and formulas."""

    NUMBER_PREFIX = "SCO"

    TARGET_MODEL_CHOICES = [
        ("opportunity", "Opportunity (crm.Opportunity)"),
        ("cpq_quote", "CPQ Quote (sales.CPQQuote)"),
        ("sales_order", "Sales Order (scm.SalesOrder)"),
        ("customer_contract", "Customer Contract (sales.CustomerContract)"),
        ("account", "Account / Customer (core.Party)"),
        ("standalone_custom", "Standalone Custom Sales Object"),
    ]

    FIELD_TYPE_CHOICES = [
        ("text", "Single-line Text"),
        ("textarea", "Multi-line Text / Markdown"),
        ("number", "Numeric (Integer / Decimal)"),
        ("currency", "Monetary Currency Amount"),
        ("percent", "Percentage (0–100%)"),
        ("date", "Calendar Date"),
        ("boolean", "Checkbox / Yes-No"),
        ("picklist", "Single Picklist Option"),
        ("multi_picklist", "Multi-Select Picklist"),
        ("formula", "Calculated Formula Expression"),
        ("lookup", "Lookup Relationship (1:N)"),
        ("master_detail", "Master-Detail Relationship"),
    ]

    name = models.CharField(
        max_length=150,
        help_text="Human-readable display label, e.g. 'Deal Profit Margin' or 'Channel Partner Code'",
    )
    entity_code = models.SlugField(
        max_length=60,
        help_text="Machine API key, e.g. 'profit_margin_pct_c' or 'custom_deal_type'",
    )
    target_model = models.CharField(
        max_length=30,
        choices=TARGET_MODEL_CHOICES,
        default="opportunity",
        help_text="Sales domain model or standalone object extended by this definition",
    )
    field_type = models.CharField(
        max_length=20,
        choices=FIELD_TYPE_CHOICES,
        default="text",
        help_text="Underlying storage and presentation data type",
    )
    is_required = models.BooleanField(
        default=False,
        help_text="Whether this field is mandatory when records are created or edited",
    )
    formula_expression = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Declarative formula expression, e.g. '(amount - total_cost) / amount * 100'",
    )
    lookup_target_model = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Target entity class or table for lookup or master-detail relationships",
    )
    picklist_options = models.JSONField(
        default=list,
        blank=True,
        help_text="Allowed choice options formatted as ['Option A', 'Option B', 'Option C']",
    )
    validation_rule = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Validation rule regex or expression",
    )
    display_order = models.PositiveIntegerField(
        default=10,
        help_text="Sorting priority within object detail cards and forms",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this custom object/field definition is active",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Documentation describing business rationale, formula calculations, and dependencies",
    )

    class Meta:
        ordering = ["target_model", "display_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="sales_sco_tenant_num_uniq",
            ),
            models.UniqueConstraint(
                fields=["tenant", "target_model", "entity_code"],
                name="sales_sco_tnt_tgt_code_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "target_model", "is_active"], name="sales_sco_tgt_act_idx"),
            models.Index(fields=["tenant", "field_type"], name="sales_sco_ftype_idx"),
            models.Index(fields=["tenant", "entity_code"], name="sales_sco_code_idx"),
        ]

    def clean(self):
        super().clean()
        self.entity_code = self.entity_code.lower().strip()
        if self.field_type == "formula" and not self.formula_expression.strip():
            raise ValidationError({"formula_expression": "Formula expression is required when field type is 'Formula'."})
        if self.field_type in ["lookup", "master_detail"] and not self.lookup_target_model.strip():
            raise ValidationError({"lookup_target_model": "Lookup target model is required for relationship fields."})
        if self.field_type in ["picklist", "multi_picklist"] and not isinstance(self.picklist_options, list):
            raise ValidationError({"picklist_options": "Picklist options must be a JSON array of strings."})

    def __str__(self):
        return f"{self.number} · {self.get_target_model_display()} - {self.name} ({self.entity_code})"
