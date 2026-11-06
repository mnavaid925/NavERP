from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from apps.bi.models._base import TenantNumbered


class PivotAnalysisView(TenantNumbered):
    NUMBER_PREFIX = "BPIV"

    TOTAL_POSITION_CHOICES = [
        ("bottom_right", "Bottom & Right"),
        ("top_left", "Top & Left"),
        ("none", "No Totals"),
    ]

    STATUS_CHOICES = [
        ("active", "Active View"),
        ("draft", "Draft Exploration"),
        ("archived", "Archived"),
    ]

    cube = models.ForeignKey(
        "bi.OlapCube",
        on_delete=models.CASCADE,
        related_name="pivot_views",
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120)
    description = models.TextField(blank=True)
    row_dimensions = models.JSONField(
        default=list,
        help_text="Ordered list of dimensions plotted along rows",
    )
    column_dimensions = models.JSONField(
        default=list,
        help_text="Ordered list of dimensions plotted along columns",
    )
    selected_measures = models.JSONField(
        default=list,
        help_text="Selected measures and aggregations",
    )
    filters_json = models.JSONField(
        default=list,
        help_text="Dimensional slicers and value filters",
    )
    show_row_subtotals = models.BooleanField(default=True)
    show_col_subtotals = models.BooleanField(default=True)
    show_grand_totals = models.BooleanField(default=True)
    total_position = models.CharField(
        max_length=20,
        choices=TOTAL_POSITION_CHOICES,
        default="bottom_right",
    )
    conditional_formatting = models.JSONField(
        default=dict,
        help_text="Heatmap, threshold, and alert styling rules",
    )
    drill_through_enabled = models.BooleanField(default=True)
    drill_through_target = models.CharField(
        max_length=150,
        default="accounting:journal_entry_list",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
    )
    is_favorite = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_pivot_views",
    )

    class Meta:
        db_table = "bi_pivot_analysis_view"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "slug"], name="bi_bpiv_tenant_slug_uniq"),
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bpiv_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "cube"], name="idx_bpiv_ten_cube"),
            models.Index(fields=["tenant", "status"], name="idx_bpiv_ten_stat"),
            models.Index(fields=["tenant", "created_by"], name="idx_bpiv_ten_user"),
        ]

    def __str__(self):
        return f"{self.name} ({self.number})"

    def get_absolute_url(self):
        return reverse("bi:pivot_view_detail", kwargs={"pk": self.pk})

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or "pivot"
            self.slug = base_slug[:120]
        super().save(*args, **kwargs)
