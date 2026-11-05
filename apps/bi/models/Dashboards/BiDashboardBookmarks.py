from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class BiDashboardBookmark(TenantNumbered):
    NUMBER_PREFIX = "BDBM"

    dashboard = models.ForeignKey(
        "bi.BiDashboard",
        on_delete=models.CASCADE,
        related_name="bookmarks",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bi_dashboard_bookmarks",
    )
    name = models.CharField(max_length=150)
    filter_state_json = models.JSONField(
        default=dict,
        help_text="Serialized filter selections: {filter_key: selected_value, ...}",
    )
    crossfilter_state_json = models.JSONField(
        default=dict,
        help_text="Active cross-filtering selections: {widget_id: selected_dimension_value}",
    )
    is_default = models.BooleanField(
        default=False,
        help_text="If True, this bookmark automatically loads when this user accesses the dashboard",
    )
    is_shared = models.BooleanField(
        default=False,
        help_text="If True, other authorized tenant users can view and apply this bookmark",
    )
    view_count = models.PositiveIntegerField(default=0)
    last_viewed_at = models.DateTimeField(null=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "bi_dashboard_bookmark"
        ordering = ["-is_default", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "dashboard", "user", "name"],
                name="bi_bdbm_ten_dsh_usr_name_uniq",
            ),
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bdbm_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "dashboard"], name="idx_bdbm_ten_dsh"),
            models.Index(fields=["tenant", "user"], name="idx_bdbm_ten_usr"),
            models.Index(fields=["tenant", "is_default"], name="idx_bdbm_ten_def"),
            models.Index(fields=["tenant", "is_shared"], name="idx_bdbm_ten_shr"),
            models.Index(fields=["tenant", "is_active"], name="idx_bdbm_ten_act"),
        ]

    def __str__(self):
        return f"{self.name} ({self.number}) [{self.dashboard.title}]"

    def get_absolute_url(self):
        return reverse("bi:bi_dashboard_bookmark_detail", kwargs={"pk": self.pk})
