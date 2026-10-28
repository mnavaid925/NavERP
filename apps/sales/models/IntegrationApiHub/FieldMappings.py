"""Sales 8.18 — SalesFieldMapping model."""
from django.db import models

from apps.sales.models._base import TenantOwned

TARGET_ENTITY_CHOICES = [
    ("lead", "Sales Lead"),
    ("account", "Account (core.Party)"),
    ("opportunity", "Opportunity"),
    ("quote", "CPQ Quote"),
    ("order", "Sales Order"),
    ("contract", "Customer Contract"),
    ("analytics", "Analytics & Snapshot"),
]

DIRECTION_CHOICES = [
    ("bidirectional", "Two-Way Bidirectional (⇄)"),
    ("outbound", "Outbound NavERP → Remote (→)"),
    ("inbound", "Inbound Remote → NavERP (←)"),
]

TRANSFORM_CHOICES = [
    ("none", "Direct / None"),
    ("uppercase", "Upper Case"),
    ("lowercase", "Lower Case"),
    ("boolean_to_int", "Boolean to Integer (0/1)"),
    ("json_extract", "JSON Key Extract"),
    ("currency_round", "Round Currency (2 decimals)"),
    ("value_map", "Value Map Picklist Translation"),
]


class SalesFieldMapping(TenantOwned):
    connector = models.ForeignKey(
        "sales.SalesIntegrationConnector",
        on_delete=models.CASCADE,
        related_name="field_mappings",
    )
    target_entity = models.CharField(max_length=30, choices=TARGET_ENTITY_CHOICES, default="order")
    local_field = models.CharField(max_length=100)
    remote_field = models.CharField(max_length=100)
    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES, default="bidirectional")
    transform_rule = models.CharField(max_length=30, choices=TRANSFORM_CHOICES, default="none")
    value_map = models.JSONField(default=dict, blank=True, help_text="Dictionary of local-to-remote picklist mappings")
    default_value = models.CharField(max_length=255, blank=True, default="")
    is_key = models.BooleanField(default=False, help_text="True if field is used as external deduplication/matching key")
    is_required = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["connector", "target_entity", "local_field"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "connector", "target_entity", "local_field", "remote_field"],
                name="sales_sfm_target_fields_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "connector", "target_entity"], name="sales_sfm_conn_ent_idx"),
        ]

    def __str__(self):
        conn_name = getattr(self.connector, "name", f"Connector #{self.connector_id}") if self.connector_id else "None"
        return f"{conn_name} | {self.get_target_entity_display()}: {self.local_field} → {self.remote_field}"
