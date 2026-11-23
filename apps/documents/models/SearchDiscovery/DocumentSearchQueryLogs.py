import json

from django.conf import settings
from django.db import models

from apps.documents.models._base import TenantNumbered


class DocumentSearchQueryLog(TenantNumbered):
    NUMBER_PREFIX = "DQRY"

    SOURCE_CHOICES = (
        ("search_hub", "Search & Discovery Hub"),
        ("quick_search", "Header Quick Search"),
        ("saved_search", "Saved Search Run"),
        ("alert_cron", "Automated Alert Job"),
    )

    SOURCE_CSS = {
        "search_hub": "badge-info",
        "quick_search": "badge-green",
        "saved_search": "badge-amber",
        "alert_cron": "badge-slate",
    }

    ZERO_RESULT_CSS = {
        True: "badge-red",
        False: "badge-green",
    }

    query_text = models.CharField(max_length=500, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="document_search_queries",
    )
    filters_applied_json = models.TextField(blank=True, default="{}")
    results_count = models.PositiveIntegerField(default=0, db_index=True)
    is_zero_result = models.BooleanField(default=False, db_index=True)
    execution_time_ms = models.PositiveIntegerField(default=0)
    search_source = models.CharField(
        max_length=25,
        choices=SOURCE_CHOICES,
        default="search_hub",
        db_index=True,
    )
    clicked_document = models.ForeignKey(
        "documents.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="search_query_clicks",
    )
    click_rank = models.PositiveSmallIntegerField(null=True, blank=True)
    ip_address = models.CharField(max_length=45, blank=True)
    session_key = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Search Query Log"
        verbose_name_plural = "Search Query Logs"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="doc_dqry_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "is_zero_result", "-created_at"],
                name="doc_dqry_tnt_zero_crt_idx",
            ),
            models.Index(
                fields=["tenant", "user", "-created_at"],
                name="doc_dqry_tnt_usr_crt_idx",
            ),
            models.Index(
                fields=["tenant", "query_text"],
                name="doc_dqry_tnt_qry_idx",
            ),
        ]

    def __str__(self):
        return f"{self.number} - '{self.query_text}' ({self.results_count} results)"

    @property
    def source_badge_class(self):
        return self.SOURCE_CSS.get(self.search_source, "badge-slate")

    @property
    def zero_result_badge_class(self):
        return self.ZERO_RESULT_CSS.get(self.is_zero_result, "badge-green")

    def get_filters_dict(self):
        if not self.filters_applied_json:
            return {}
        try:
            data = json.loads(self.filters_applied_json)
            return data if isinstance(data, dict) else {}
        except (ValueError, TypeError):
            return {}
