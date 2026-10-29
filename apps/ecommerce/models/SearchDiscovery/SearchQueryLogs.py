from django.db import models

from apps.ecommerce.models._base import TenantNumbered


class SearchQueryLog(TenantNumbered):
    NUMBER_PREFIX = "ESQL"

    query_text = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Raw search query string entered by shopper",
    )
    normalized_query = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Cleaned, lowercase, stripped search term for grouping",
    )
    results_count = models.PositiveIntegerField(
        default=0,
        help_text="Count of matching products returned",
    )
    is_zero_result = models.BooleanField(
        default=False,
        db_index=True,
        help_text="True if search returned 0 items (null-result)",
    )
    execution_time_ms = models.PositiveIntegerField(
        default=0,
        help_text="Search latency in milliseconds",
    )
    applied_filters = models.JSONField(
        default=dict,
        blank=True,
        help_text="Dictionary of facet filters applied during query",
    )
    sort_order = models.CharField(
        max_length=30,
        default="relevance",
        help_text="Active sort order selected (e.g. relevance, price_asc, newest)",
    )
    redirected_to = models.CharField(
        max_length=255,
        blank=True,
        help_text="Destination URL if intercepted by redirect rule",
    )
    clicked_product = models.ForeignKey(
        "ecommerce.CatalogProduct",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="search_clicks",
        help_text="First product clicked by shopper from search results",
    )
    click_position = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="1-indexed rank position of clicked product",
    )
    session_key = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        help_text="Shopper session key for anonymous attribution",
    )
    customer = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ecommerce_search_logs",
        help_text="Shopper party record if authenticated",
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_esql_tenant_num_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "is_zero_result", "-created_at"],
                name="idx_esql_ten_zr_created",
            ),
            models.Index(
                fields=["tenant", "normalized_query"],
                name="idx_esql_ten_norm_q",
            ),
            models.Index(
                fields=["tenant", "-created_at"],
                name="idx_esql_ten_created",
            ),
        ]

    def __str__(self):
        return f"{self.number} - '{self.query_text}' ({self.results_count} results)"

    def clean(self):
        super().clean()
        if self.query_text:
            self.normalized_query = self.query_text.strip().lower()
        if self.results_count == 0:
            self.is_zero_result = True
