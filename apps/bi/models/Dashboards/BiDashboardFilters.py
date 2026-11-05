from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class BiDashboardFilter(TenantNumbered):
    NUMBER_PREFIX = "BDFL"

    FILTER_TYPE_CHOICES = [
        ("dropdown", "Single Select Dropdown"),
        ("multi_select", "Multi-Select Dropdown / Badges"),
        ("date_range", "Date Range Picker (From / To)"),
        ("date_preset", "Relative Date Preset (Today, MTD, QTD, YTD)"),
        ("number_range", "Numeric Range Slider / Min-Max"),
        ("search_text", "Search Text Input"),
    ]

    OPTIONS_SOURCE_CHOICES = [
        ("static_list", "Static Pre-defined Choices"),
        ("semantic_distinct", "Distinct Values from Semantic Model"),
        ("warehouse_column", "Distinct Values from Warehouse Table"),
    ]

    dashboard = models.ForeignKey(
        "bi.BiDashboard",
        on_delete=models.CASCADE,
        related_name="filters",
    )
    filter_label = models.CharField(max_length=100)
    filter_key = models.SlugField(
        max_length=60,
        help_text="Query parameter key passed in filter requests, e.g. 'fiscal_year', 'region'",
    )
    filter_type = models.CharField(
        max_length=30,
        choices=FILTER_TYPE_CHOICES,
        default="dropdown",
    )
    target_field = models.CharField(
        max_length=100,
        help_text="Target semantic dimension or column filtered in the dataset, e.g. 'customer_region', 'order_date'",
    )
    default_value = models.CharField(
        max_length=255,
        blank=True,
        help_text="Default selected value or preset token (e.g. 'current_year', 'all')",
    )
    options_source = models.CharField(
        max_length=30,
        choices=OPTIONS_SOURCE_CHOICES,
        default="static_list",
    )
    static_options_json = models.JSONField(
        default=list,
        help_text="Pre-defined choices: [{'value': 'north', 'label': 'North Region'}, ...]",
    )
    order = models.PositiveIntegerField(
        default=10,
        help_text="Display order in the top filter bar",
    )
    is_required = models.BooleanField(
        default=False,
        help_text="If True, user must select a value before queries execute",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "bi_dashboard_filter"
        ordering = ["order", "filter_label"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "dashboard", "filter_key"],
                name="bi_bdfl_ten_dsh_fkey_uniq",
            ),
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bdfl_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "dashboard"], name="idx_bdfl_ten_dsh"),
            models.Index(fields=["tenant", "filter_key"], name="idx_bdfl_ten_fkey"),
            models.Index(fields=["tenant", "order"], name="idx_bdfl_ten_ord"),
            models.Index(fields=["tenant", "is_active"], name="idx_bdfl_ten_act"),
        ]

    def __str__(self):
        return f"{self.filter_label} ({self.filter_key}) [{self.number}]"

    def get_absolute_url(self):
        return reverse("bi:bi_dashboard_filter_detail", kwargs={"pk": self.pk})

    @property
    def badge_filter_type(self):
        mapping = {
            "dropdown": "badge-info",
            "multi_select": "badge-info",
            "date_range": "badge-green",
            "date_preset": "badge-green",
            "number_range": "badge-amber",
            "search_text": "badge-slate",
        }
        return mapping.get(self.filter_type, "badge-slate")
