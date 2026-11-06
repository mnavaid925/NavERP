from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class ReportDrillPath(TenantNumbered):
    NUMBER_PREFIX = "BDRP"

    TARGET_TYPE_CHOICES = [
        ("subreport", "Subreport Definition"),
        ("operational_report", "Sibling Operational Report"),
        ("erp_record_url", "Direct ERP Entity Detail URL"),
    ]

    source_report = models.ForeignKey(
        "bi.ReportDefinition",
        on_delete=models.CASCADE,
        related_name="source_drill_paths",
        help_text="Parent report containing the drillable cell/column",
    )
    source_field = models.CharField(
        max_length=100,
        help_text="Column name or field triggering the drill action (e.g. 'customer_code', 'account_id')",
    )
    drill_label = models.CharField(
        max_length=150,
        help_text="User-facing action label, e.g. 'View Customer Invoices', 'Drill to GL Line Items'",
    )
    target_type = models.CharField(
        max_length=30,
        choices=TARGET_TYPE_CHOICES,
        default="operational_report",
    )
    target_report = models.ForeignKey(
        "bi.ReportDefinition",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="target_drill_paths",
        help_text="Target report executed upon drill-through navigation",
    )
    target_url_pattern = models.CharField(
        max_length=255,
        blank=True,
        help_text="URL pattern for ERP entity detail drill (e.g. '/crm/accounts/{customer_id}/')",
    )
    parameter_mapping_json = models.JSONField(
        default=dict,
        help_text="Mapping from source row fields to target parameters: {'customer_code': 'target_customer_id'}",
    )
    sort_order = models.PositiveIntegerField(
        default=10,
        help_text="Display priority order for drill-through actions",
    )
    is_enabled = models.BooleanField(
        default=True,
        help_text="True if drill-through navigation is active",
    )

    class Meta:
        db_table = "bi_report_drill_path"
        ordering = ["source_report", "sort_order", "drill_label"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bdrp_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "source_report"], name="idx_bdrp_ten_srpt"),
            models.Index(fields=["tenant", "target_report"], name="idx_bdrp_ten_trpt"),
            models.Index(fields=["tenant", "target_type"], name="idx_bdrp_ten_ttype"),
        ]

    def __str__(self):
        return f"{self.drill_label} ({self.source_field} → {self.get_target_type_display()})"

    def get_absolute_url(self):
        return reverse("bi:report_drill_path_detail", kwargs={"pk": self.pk})

    @property
    def badge_target_type(self):
        mapping = {
            "subreport": "badge-info",
            "operational_report": "badge-slate",
            "erp_record_url": "badge-green",
        }
        return mapping.get(self.target_type, "badge-slate")
