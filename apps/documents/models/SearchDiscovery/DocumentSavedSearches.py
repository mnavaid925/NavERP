import json

from django.conf import settings
from django.db import models
from django.utils.text import slugify

from apps.documents.models._base import TenantNumbered


class DocumentSavedSearch(TenantNumbered):
    NUMBER_PREFIX = "DSVD"

    VISIBILITY_CHOICES = (
        ("private", "Private (Only Me)"),
        ("shared_department", "Department Shared"),
        ("public", "Public (All Users)"),
    )

    SORT_BY_CHOICES = (
        ("relevance", "Best Match / Relevance"),
        ("updated_at_desc", "Recently Updated"),
        ("created_at_desc", "Recently Created"),
        ("title_asc", "Title (A-Z)"),
        ("size_desc", "File Size (Largest)"),
    )

    SORT_ORDER_CHOICES = (
        ("asc", "Ascending"),
        ("desc", "Descending"),
    )

    VISIBILITY_CSS = {
        "private": "badge-slate",
        "shared_department": "badge-info",
        "public": "badge-green",
    }

    STATUS_CSS = {
        True: "badge-green",
        False: "badge-slate",
    }

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=160, blank=True)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_saved_searches",
    )
    department = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="department_saved_searches",
    )
    visibility = models.CharField(
        max_length=25,
        choices=VISIBILITY_CHOICES,
        default="private",
        db_index=True,
    )
    query_text = models.CharField(max_length=500, blank=True)
    filters_json = models.TextField(blank=True, default="{}")
    facet_filters_json = models.TextField(blank=True, default="{}")
    sort_by = models.CharField(
        max_length=30,
        choices=SORT_BY_CHOICES,
        default="relevance",
    )
    sort_order = models.CharField(
        max_length=10,
        choices=SORT_ORDER_CHOICES,
        default="desc",
    )
    is_pinned = models.BooleanField(default=False, db_index=True)
    is_favorite = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    run_count = models.PositiveIntegerField(default=0)
    total_results_last_run = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-is_pinned", "-updated_at"]
        verbose_name = "Saved Search"
        verbose_name_plural = "Saved Searches"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="doc_dsvd_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "owner", "is_pinned"],
                name="doc_dsvd_tnt_own_pin_idx",
            ),
            models.Index(
                fields=["tenant", "visibility", "is_active"],
                name="doc_dsvd_tnt_vis_act_idx",
            ),
        ]

    def __str__(self):
        return f"{self.number} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug and self.name:
            base_slug = slugify(self.name)[:150]
            self.slug = base_slug
        super().save(*args, **kwargs)

    @property
    def visibility_badge_class(self):
        return self.VISIBILITY_CSS.get(self.visibility, "badge-slate")

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.is_active, "badge-slate")

    def get_filters_dict(self):
        if not self.filters_json:
            return {}
        try:
            return json.loads(self.filters_json)
        except (ValueError, TypeError):
            return {}

    def get_facet_filters_dict(self):
        if not self.facet_filters_json:
            return {}
        try:
            return json.loads(self.facet_filters_json)
        except (ValueError, TypeError):
            return {}
