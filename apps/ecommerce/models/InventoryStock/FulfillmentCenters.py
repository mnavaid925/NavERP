from django.db import models

from apps.ecommerce.models._base import TenantNumbered


class FulfillmentCenter(TenantNumbered):
    NUMBER_PREFIX = "EFC"

    CENTER_TYPE_CHOICES = [
        ("internal_warehouse", "Internal Warehouse / DC"),
        ("third_party_3pl", "3PL Partner (ShipBob/FBA)"),
        ("retail_store", "Retail Store (Local Pickup/SFS)"),
        ("dropshipper", "Drop-Ship Vendor Facility"),
    ]

    name = models.CharField(max_length=120)
    code = models.CharField(max_length=30)
    center_type = models.CharField(max_length=30, choices=CENTER_TYPE_CHOICES, default="internal_warehouse")
    location = models.ForeignKey(
        "scm.Location",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ecommerce_fulfillment_centers",
    )
    priority = models.PositiveSmallIntegerField(default=1, help_text="Order routing priority (1 = highest priority)")
    is_active = models.BooleanField(default=True)
    supports_pick_pack_ship = models.BooleanField(default=True)
    supports_customer_pickup = models.BooleanField(default=False)
    daily_cutoff_time = models.TimeField(null=True, blank=True, help_text="Daily order cutoff for same-day dispatch")

    # Physical / Routing Address
    address_line1 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default="United States")

    # Contacts & Operational Notes
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["priority", "name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecom_fc_tenant_num_uniq"),
            models.UniqueConstraint(fields=["tenant", "code"], name="ecom_fc_tenant_code_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "is_active", "priority"], name="ecom_fc_tnt_act_prio_idx"),
            models.Index(fields=["tenant", "center_type"], name="ecom_fc_tnt_type_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def full_address(self):
        parts = [self.address_line1, self.city, self.state, self.postal_code, self.country]
        return ", ".join(p for p in parts if p)
