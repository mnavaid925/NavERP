from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class AdHocCalculatedField(TenantNumbered):
    NUMBER_PREFIX = "BACF"

    RETURN_TYPE_CHOICES = [
        ("decimal", "Decimal Amount"),
        ("integer", "Integer Number"),
        ("percentage", "Percentage (%)"),
        ("currency", "Currency ($)"),
        ("string", "Text String"),
        ("boolean", "Boolean (True/False)"),
    ]

    AGGREGATION_MODE_CHOICES = [
        ("formula", "Direct Formula Calculation"),
        ("pre_agg", "Row-Level Before Aggregation"),
        ("post_agg", "Summary-Level After Aggregation"),
    ]

    query = models.ForeignKey(
        "bi.AdHocQuery",
        on_delete=models.CASCADE,
        related_name="calculated_fields",
    )
    field_name = models.SlugField(max_length=60)
    display_label = models.CharField(max_length=120)
    formula_expression = models.CharField(
        max_length=500,
        help_text="e.g. [revenue] - [cost] or ([margin] / [revenue]) * 100",
    )
    return_type = models.CharField(max_length=30, choices=RETURN_TYPE_CHOICES, default="decimal")
    aggregation_mode = models.CharField(max_length=30, choices=AGGREGATION_MODE_CHOICES, default="formula")
    is_valid = models.BooleanField(default=True)
    error_message = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_ad_hoc_calc_fields",
    )

    class Meta:
        db_table = "bi_ad_hoc_calculated_field"
        ordering = ["query", "field_name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bacf_tenant_num_uniq"),
            models.UniqueConstraint(fields=["tenant", "query", "field_name"], name="bi_bacf_ten_qry_fname_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "query"], name="idx_bacf_ten_qry"),
            models.Index(fields=["tenant", "return_type"], name="idx_bacf_ten_rtype"),
            models.Index(fields=["tenant", "created_at"], name="idx_bacf_ten_created"),
        ]

    def __str__(self):
        return f"{self.display_label} ({self.number})"

    def get_absolute_url(self):
        return reverse("bi:ad_hoc_calculated_field_detail", kwargs={"pk": self.pk})

    @property
    def badge_return_type(self):
        mapping = {
            "decimal": "badge-info",
            "integer": "badge-slate",
            "percentage": "badge-purple",
            "currency": "badge-green",
            "string": "badge-slate",
            "boolean": "badge-amber",
        }
        return mapping.get(self.return_type, "badge-slate")

    @property
    def badge_mode(self):
        mapping = {
            "formula": "badge-info",
            "pre_agg": "badge-amber",
            "post_agg": "badge-green",
        }
        return mapping.get(self.aggregation_mode, "badge-slate")
