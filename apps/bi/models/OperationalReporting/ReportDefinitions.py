from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class ReportDefinition(TenantNumbered):
    NUMBER_PREFIX = "BRPT"

    CATEGORY_CHOICES = [
        ("finance", "Finance & Accounting"),
        ("sales", "Sales & CRM"),
        ("inventory", "Inventory & Warehouse"),
        ("hr", "Human Resources & Talent"),
        ("procurement", "Procurement & Purchasing"),
        ("production", "Manufacturing & Production"),
        ("compliance", "Regulatory & Compliance"),
        ("custom", "Custom Operational Report"),
    ]

    REPORT_TYPE_CHOICES = [
        ("standard_tabular", "Standard Tabular Report"),
        ("pixel_perfect_document", "Pixel-Perfect Banded Document"),
        ("regulatory_filing", "Regulatory & Compliance Filing"),
        ("matrix_summary", "Cross-Tab Matrix Summary"),
        ("subreport", "Modular Subreport Component"),
    ]

    PAPER_SIZE_CHOICES = [
        ("a4", "ISO A4 (210 x 297 mm)"),
        ("letter", "US Letter (8.5 x 11 in)"),
        ("legal", "US Legal (8.5 x 14 in)"),
        ("tabloid", "US Tabloid (11 x 17 in)"),
        ("custom", "Custom Dimensions"),
    ]

    ORIENTATION_CHOICES = [
        ("portrait", "Portrait"),
        ("landscape", "Landscape"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft (Design in Progress)"),
        ("published", "Published (Live for Users)"),
        ("archived", "Archived (Deprecated)"),
    ]

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=40, choices=CATEGORY_CHOICES, default="finance")
    report_type = models.CharField(max_length=40, choices=REPORT_TYPE_CHOICES, default="standard_tabular")
    paper_size = models.CharField(max_length=20, choices=PAPER_SIZE_CHOICES, default="a4")
    orientation = models.CharField(max_length=20, choices=ORIENTATION_CHOICES, default="portrait")
    margins_json = models.JSONField(
        default=dict,
        help_text="Page margins in mm: {'top': 15, 'bottom': 15, 'left': 15, 'right': 15}",
    )
    bands_config_json = models.JSONField(
        default=dict,
        help_text="Banded layout configuration: title_band, page_header, group_header, detail_band, group_footer, page_footer, summary_band",
    )
    columns_config_json = models.JSONField(
        default=list,
        help_text="Tabular column definitions: field, title, width, align, format",
    )
    styling_css = models.TextField(
        blank=True,
        help_text="Custom CSS styling rules applied to rendered report output",
    )
    watermark_text = models.CharField(
        max_length=100,
        blank=True,
        help_text="Optional background watermark text",
    )
    semantic_model = models.ForeignKey(
        "bi.SemanticModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="operational_reports",
        help_text="Governed analytical dataset source (10.4)",
    )
    warehouse_table = models.ForeignKey(
        "bi.WarehouseTable",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="operational_reports",
        help_text="Direct physical analytical warehouse table (10.3)",
    )
    raw_query = models.TextField(
        blank=True,
        help_text="Optional direct analytical SQL/ORM query specification",
    )
    org_unit = models.ForeignKey(
        "core.OrgUnit",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bi_operational_reports",
        help_text="Departmental/branch scoping",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_bi_reports",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    is_prebuilt_template = models.BooleanField(
        default=False,
        help_text="True if out-of-the-box system report template",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "bi_report_definition"
        ordering = ["category", "name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "slug"], name="bi_brpt_tenant_slug_uniq"),
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_brpt_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "-created_at"], name="idx_brpt_ten_created"),
            models.Index(fields=["tenant", "category"], name="idx_brpt_ten_cat"),
            models.Index(fields=["tenant", "report_type"], name="idx_brpt_ten_type"),
            models.Index(fields=["tenant", "status"], name="idx_brpt_ten_stat"),
            models.Index(fields=["tenant", "semantic_model"], name="idx_brpt_ten_smdl"),
            models.Index(fields=["tenant", "is_active"], name="idx_brpt_ten_act"),
        ]

    def __str__(self):
        return f"{self.name} ({self.number})"

    def get_absolute_url(self):
        return reverse("bi:report_definition_detail", kwargs={"pk": self.pk})

    @property
    def badge_status(self):
        mapping = {
            "draft": "badge-amber",
            "published": "badge-green",
            "archived": "badge-muted",
        }
        return mapping.get(self.status, "badge-slate")

    @property
    def badge_category(self):
        mapping = {
            "finance": "badge-green",
            "sales": "badge-info",
            "inventory": "badge-amber",
            "hr": "badge-muted",
            "procurement": "badge-info",
            "production": "badge-slate",
            "compliance": "badge-green",
            "custom": "badge-slate",
        }
        return mapping.get(self.category, "badge-slate")

    @property
    def badge_type(self):
        mapping = {
            "standard_tabular": "badge-info",
            "pixel_perfect_document": "badge-green",
            "regulatory_filing": "badge-amber",
            "matrix_summary": "badge-slate",
            "subreport": "badge-muted",
        }
        return mapping.get(self.report_type, "badge-slate")
