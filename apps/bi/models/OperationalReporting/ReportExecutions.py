from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class ReportExecution(TenantNumbered):
    NUMBER_PREFIX = "BRUN"

    EXECUTION_MODE_CHOICES = [
        ("interactive_view", "Interactive Web Viewer"),
        ("export_pdf", "PDF Export Download"),
        ("export_excel", "Excel (XLSX) Export"),
        ("export_csv", "CSV Delimited Export"),
        ("export_docx", "Word (DOCX) Export"),
        ("drill_through", "Transactional Drill-Through Action"),
    ]

    EXECUTION_STATUS_CHOICES = [
        ("pending", "Pending Execution"),
        ("running", "Running Query"),
        ("completed", "Completed Successfully"),
        ("failed", "Execution Failed"),
    ]

    OUTPUT_FORMAT_CHOICES = [
        ("html", "Interactive HTML"),
        ("pdf", "Adobe PDF Document"),
        ("xlsx", "Microsoft Excel Workbook"),
        ("csv", "Comma-Separated Values (CSV)"),
        ("docx", "Microsoft Word Document"),
        ("json", "Raw JSON Data Payload"),
    ]

    report = models.ForeignKey(
        "bi.ReportDefinition",
        on_delete=models.CASCADE,
        related_name="executions",
        help_text="Parent report definition executed in this run",
    )
    executed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bi_report_executions",
    )
    execution_mode = models.CharField(
        max_length=30,
        choices=EXECUTION_MODE_CHOICES,
        default="interactive_view",
    )
    execution_status = models.CharField(
        max_length=20,
        choices=EXECUTION_STATUS_CHOICES,
        default="completed",
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(
        default=0,
        help_text="Total execution duration in milliseconds",
    )
    parameter_values_json = models.JSONField(
        default=dict,
        help_text="Frozen snapshot of exact parameter values applied in this run",
    )
    row_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of records returned in this execution",
    )
    output_format = models.CharField(
        max_length=20,
        choices=OUTPUT_FORMAT_CHOICES,
        default="html",
    )
    output_file_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Generated export file name",
    )
    file_size_bytes = models.PositiveIntegerField(
        default=0,
        help_text="Size of generated export artifact in bytes",
    )
    error_message = models.TextField(
        blank=True,
        help_text="Error message and diagnostic trace if execution failed",
    )
    is_cached = models.BooleanField(
        default=False,
        help_text="True if result was served from execution cache",
    )

    class Meta:
        db_table = "bi_report_execution"
        ordering = ["-started_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_brun_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "report"], name="idx_brun_ten_rpt"),
            models.Index(fields=["tenant", "execution_status"], name="idx_brun_ten_stat"),
            models.Index(fields=["tenant", "executed_by"], name="idx_brun_ten_exec"),
            models.Index(fields=["tenant", "started_at"], name="idx_brun_ten_start"),
        ]

    def __str__(self):
        return f"{self.number} — {self.report.name} ({self.get_execution_status_display()})"

    def get_absolute_url(self):
        return reverse("bi:report_execution_detail", kwargs={"pk": self.pk})

    @property
    def badge_status(self):
        mapping = {
            "pending": "badge-slate",
            "running": "badge-amber",
            "completed": "badge-green",
            "failed": "badge-red",
        }
        return mapping.get(self.execution_status, "badge-slate")

    @property
    def badge_mode(self):
        mapping = {
            "interactive_view": "badge-info",
            "export_pdf": "badge-red",
            "export_excel": "badge-green",
            "export_csv": "badge-slate",
            "export_docx": "badge-info",
            "drill_through": "badge-purple",
        }
        return mapping.get(self.execution_mode, "badge-slate")
