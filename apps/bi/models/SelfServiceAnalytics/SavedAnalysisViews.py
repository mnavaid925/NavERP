import secrets
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from apps.bi.models._base import TenantNumbered


class SavedAnalysisView(TenantNumbered):
    NUMBER_PREFIX = "BSAV"

    SHARING_SCOPE_CHOICES = [
        ("personal", "Personal Workspace (Private)"),
        ("team", "Team / Department (Org Unit)"),
        ("tenant_public", "Tenant Public (All Users)"),
    ]

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120)
    description = models.TextField(blank=True)
    query = models.ForeignKey(
        "bi.AdHocQuery",
        on_delete=models.CASCADE,
        related_name="saved_views",
    )
    sharing_scope = models.CharField(max_length=20, choices=SHARING_SCOPE_CHOICES, default="personal")
    org_unit = models.ForeignKey(
        "core.OrgUnit",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bi_saved_analysis_views",
    )
    is_template = models.BooleanField(default=False)
    is_favorite = models.BooleanField(default=False)
    parent_view = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="forked_views",
    )
    share_token = models.CharField(max_length=64, blank=True)
    view_count = models.PositiveIntegerField(default=0)
    last_viewed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_saved_analysis_views",
    )

    class Meta:
        db_table = "bi_saved_analysis_view"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "slug"], name="bi_bsav_tenant_slug_uniq"),
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bsav_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "sharing_scope"], name="idx_bsav_ten_scope"),
            models.Index(fields=["tenant", "org_unit"], name="idx_bsav_ten_org"),
            models.Index(fields=["tenant", "created_by"], name="idx_bsav_ten_user"),
            models.Index(fields=["tenant", "is_template"], name="idx_bsav_ten_tmpl"),
            models.Index(fields=["tenant", "query"], name="idx_bsav_ten_qry"),
            models.Index(fields=["tenant", "created_at"], name="idx_bsav_ten_created"),
        ]

    def __str__(self):
        return f"{self.name} ({self.number})"

    def save(self, *args, **kwargs):
        if not self.slug and self.name:
            base = slugify(self.name)[:100] or "view"
            self.slug = base
        if not self.share_token:
            self.share_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("bi:saved_analysis_view_detail", kwargs={"pk": self.pk})

    @property
    def badge_scope(self):
        mapping = {
            "personal": "badge-slate",
            "team": "badge-info",
            "tenant_public": "badge-green",
        }
        return mapping.get(self.sharing_scope, "badge-slate")
