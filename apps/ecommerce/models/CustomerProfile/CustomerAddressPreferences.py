from django.db import models

from apps.ecommerce.models._base import TenantNumbered


class CustomerAddressPreference(TenantNumbered):
    NUMBER_PREFIX = "ECAD"

    WINDOW_CHOICES = [
        ("anytime", "Anytime (Standard)"),
        ("morning", "Morning (8 AM - 12 PM)"),
        ("afternoon", "Afternoon (12 PM - 5 PM)"),
        ("evening", "Evening (5 PM - 9 PM)"),
        ("weekend", "Weekend Only"),
    ]

    customer = models.ForeignKey(
        "core.Party",
        on_delete=models.PROTECT,
        related_name="ecommerce_address_preferences",
    )
    address = models.ForeignKey(
        "core.Address",
        on_delete=models.CASCADE,
        related_name="ecommerce_preferences",
    )
    label = models.CharField(max_length=50, default="Home")

    is_default_shipping = models.BooleanField(default=False)
    is_default_billing = models.BooleanField(default=False)

    recipient_name = models.CharField(max_length=150, blank=True)
    contact_phone = models.CharField(max_length=32, blank=True)
    delivery_instructions = models.TextField(blank=True)
    preferred_delivery_window = models.CharField(
        max_length=20,
        choices=WINDOW_CHOICES,
        default="anytime",
    )
    requires_signature = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "customer"], name="idx_ecad_ten_cust"),
            models.Index(fields=["tenant", "is_default_shipping"], name="idx_ecad_ten_def_shp"),
            models.Index(fields=["tenant", "is_default_billing"], name="idx_ecad_ten_def_bil"),
        ]

    def __str__(self):
        return f"{self.number} - {self.label} ({self.customer})"

    def save(self, *args, **kwargs):
        if self.is_default_shipping and self.tenant_id and self.customer_id:
            CustomerAddressPreference.objects.filter(
                tenant=self.tenant,
                customer=self.customer,
                is_default_shipping=True,
            ).exclude(pk=self.pk).update(is_default_shipping=False)

        if self.is_default_billing and self.tenant_id and self.customer_id:
            CustomerAddressPreference.objects.filter(
                tenant=self.tenant,
                customer=self.customer,
                is_default_billing=True,
            ).exclude(pk=self.pk).update(is_default_billing=False)

        super().save(*args, **kwargs)
