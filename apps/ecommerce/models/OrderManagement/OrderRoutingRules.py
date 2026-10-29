from django.db import models

from apps.ecommerce.models._base import TenantNumbered


class OrderRoutingRule(TenantNumbered):
    """
    Intelligent order fulfillment sourcing and routing configuration.
    Determines optimal fulfillment center or vendor dispatch node based on
    geographic priority, proximity, stock levels, and split shipment permissions.
    """

    NUMBER_PREFIX = "EORT"

    ROUTING_STRATEGY_CHOICES = [
        ("closest_location", "Closest Fulfillment Center"),
        ("fewest_splits", "Fewest Split Shipments"),
        ("highest_inventory", "Highest Stock Level"),
        ("drop_ship_preferred", "Drop-Ship Preferred"),
        ("manual", "Manual Assignment"),
    ]

    name = models.CharField(
        max_length=150,
        help_text="Rule identification label (e.g. North America Domestic Standard, APAC Direct)",
    )
    strategy = models.CharField(
        max_length=30,
        choices=ROUTING_STRATEGY_CHOICES,
        default="closest_location",
        help_text="Fulfillment node selection heuristic",
    )
    priority = models.PositiveIntegerField(
        default=10,
        help_text="Evaluation sequence priority (lower numbers evaluate first, e.g. 1 = highest)",
    )
    destination_country = models.CharField(
        max_length=100,
        blank=True,
        help_text="ISO country name or code filter (leave empty for global wildcard)",
    )
    destination_region = models.CharField(
        max_length=100,
        blank=True,
        help_text="State, province, or shipping zone constraint",
    )
    preferred_fulfillment_center = models.ForeignKey(
        "ecommerce.FulfillmentCenter",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="routing_rules",
        help_text="Primary warehouse or 3PL center assigned by this rule",
    )
    allow_split_shipment = models.BooleanField(
        default=True,
        help_text="Permit line items in a single order to dispatch from distinct fulfillment centers",
    )
    enable_dropship = models.BooleanField(
        default=False,
        help_text="Authorize routing directly to vendor drop-ship partner when local stock is exhausted",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Enable or suppress rule evaluation during live order checkout",
    )
    description = models.TextField(
        blank=True,
        help_text="Internal policy explanation and fulfillment SLA notes",
    )

    class Meta:
        ordering = ["priority", "name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecom_ort_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "is_active", "priority"], name="ecom_ort_tnt_act_prio_idx"),
        ]

    def __str__(self):
        return f"{self.name} (Priority {self.priority})"
