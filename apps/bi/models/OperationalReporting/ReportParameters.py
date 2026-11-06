from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class ReportParameter(TenantNumbered):
    NUMBER_PREFIX = "BPAR"

    PARAMETER_TYPE_CHOICES = [
        ("string", "Text String"),
        ("integer", "Integer Number"),
        ("decimal", "Decimal Amount"),
        ("date", "Single Date Picker"),
        ("daterange", "Date Range (From / To)"),
        ("boolean", "Boolean Checkbox"),
        ("choice_single", "Single-Select Dropdown"),
        ("choice_multi", "Multi-Select Badges / List"),
    ]

    CHOICES_SOURCE_CHOICES = [
        ("static_list", "Static Pre-defined Choices"),
        ("semantic_dimension", "Distinct Values from Semantic Model"),
        ("warehouse_column", "Distinct Values from Warehouse Table"),
    ]

    report = models.ForeignKey(
        "bi.ReportDefinition",
        on_delete=models.CASCADE,
        related_name="parameters",
        help_text="Parent report definition this parameter prompt filters",
    )
    parameter_name = models.SlugField(
        max_length=60,
        help_text="Parameter token identifier used in queries, e.g. 'start_date', 'status'",
    )
    prompt_label = models.CharField(
        max_length=120,
        help_text="User-facing prompt label, e.g. 'Fiscal Period Start Date'",
    )
    parameter_type = models.CharField(
        max_length=30,
        choices=PARAMETER_TYPE_CHOICES,
        default="string",
    )
    default_value = models.CharField(
        max_length=255,
        blank=True,
        help_text="Default value or preset token, e.g. 'current_year', 'posted', 'today'",
    )
    choices_source = models.CharField(
        max_length=30,
        choices=CHOICES_SOURCE_CHOICES,
        default="static_list",
    )
    choices_config_json = models.JSONField(
        default=list,
        help_text="Choice options: [{'value': 'draft', 'label': 'Draft'}, ...]",
    )
    validation_regex = models.CharField(
        max_length=200,
        blank=True,
        help_text="Regex for validating user input values",
    )
    help_text = models.CharField(
        max_length=255,
        blank=True,
        help_text="Instructional help text displayed below the prompt input",
    )
    prompt_order = models.PositiveIntegerField(
        default=10,
        help_text="Display order in the prompt panel (lowest first)",
    )
    is_required = models.BooleanField(
        default=False,
        help_text="If True, user must supply a value before report executes",
    )
    is_hidden = models.BooleanField(
        default=False,
        help_text="If True, parameter is populated programmatically without rendering prompt input",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "bi_report_parameter"
        ordering = ["report", "prompt_order", "parameter_name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bpar_tenant_num_uniq"),
            models.UniqueConstraint(fields=["tenant", "report", "parameter_name"], name="bi_bpar_ten_rpt_pname_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "report"], name="idx_bpar_ten_rpt"),
            models.Index(fields=["tenant", "parameter_type"], name="idx_bpar_ten_ptype"),
            models.Index(fields=["tenant", "prompt_order"], name="idx_bpar_ten_ord"),
        ]

    def __str__(self):
        return f"{self.prompt_label} ({self.parameter_name}) — {self.report.name}"

    def get_absolute_url(self):
        return reverse("bi:report_parameter_detail", kwargs={"pk": self.pk})

    @property
    def badge_type(self):
        mapping = {
            "string": "badge-slate",
            "integer": "badge-info",
            "decimal": "badge-info",
            "date": "badge-green",
            "daterange": "badge-green",
            "boolean": "badge-amber",
            "choice_single": "badge-purple",
            "choice_multi": "badge-purple",
        }
        return mapping.get(self.parameter_type, "badge-slate")
