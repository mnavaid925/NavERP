from django.conf import settings
from django.db import models

from apps.ecommerce.models._base import TenantNumbered


class ShopperBehaviorEvent(TenantNumbered):
    NUMBER_PREFIX = "ESBE"

    EVENT_TYPE_CHOICES = [
        ("page_view", "Page View"),
        ("product_view", "Product Detail View"),
        ("category_view", "Category Browse"),
        ("search_query", "Search Query"),
        ("cart_add", "Add to Cart"),
        ("wishlist_add", "Add to Wishlist"),
        ("checkout_start", "Initiate Checkout"),
        ("order_purchase", "Order Completed"),
    ]

    session_key = models.CharField(
        max_length=64,
        db_index=True,
        help_text="Shopper session identifier for anonymous clickstream attribution",
    )
    customer_profile = models.ForeignKey(
        "ecommerce.CustomerAccountProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="behavior_events",
        help_text="Customer account profile if identified",
    )
    party = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shopper_behavior_events",
        help_text="Core Party identity if authenticated",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shopper_behavior_events",
        help_text="Django auth user if logged in",
    )
    event_type = models.CharField(
        max_length=30,
        choices=EVENT_TYPE_CHOICES,
        default="page_view",
        help_text="Interaction classification",
    )
    product = models.ForeignKey(
        "ecommerce.CatalogProduct",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="behavior_events",
        help_text="Interacted catalog product",
    )
    category = models.ForeignKey(
        "ecommerce.StoreCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="behavior_events",
        help_text="Interacted store category",
    )
    intent_score_delta = models.IntegerField(
        default=1,
        help_text="Affinity weight contribution of this event",
    )
    referrer_url = models.CharField(
        max_length=255,
        blank=True,
        help_text="HTTP Referer header",
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Client IP address",
    )
    user_agent = models.CharField(
        max_length=255,
        blank=True,
        help_text="Client User-Agent string",
    )
    payload_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="Arbitrary interaction metadata (price, search terms, variant)",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_esbe_tenant_num_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "session_key", "event_type"],
                name="idx_esbe_ten_sess_type",
            ),
            models.Index(
                fields=["tenant", "event_type", "-created_at"],
                name="idx_esbe_ten_type_created",
            ),
            models.Index(
                fields=["tenant", "-created_at"],
                name="idx_esbe_ten_created",
            ),
        ]

    def __str__(self):
        return f"{self.get_event_type_display()} [{self.session_key[:8]}] ({self.number})"
