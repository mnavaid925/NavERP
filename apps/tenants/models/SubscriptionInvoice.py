"""tenants — SubscriptionInvoice models (split from apps/tenants/models.py)."""
from apps.tenants.models._base import *  # noqa: F401,F403


class SubscriptionInvoice(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("open", "Open"),
        ("paid", "Paid"),
        ("void", "Void"),
        ("uncollectible", "Uncollectible"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="subscription_invoices", db_index=True)
    subscription = models.ForeignKey("tenants.Subscription", on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")
    number = models.CharField(max_length=20, editable=False)  # SINV-##### — assigned in save()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    issued_on = models.DateField(default=timezone.localdate)
    due_on = models.DateField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)  # system-set, out of forms (L22)
    stripe_invoice_id = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issued_on", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="subinv_tenant_status_idx"),
            models.Index(fields=["stripe_invoice_id"], name="subinv_stripe_inv_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.number:
            return super().save(*args, **kwargs)
        # Assign SINV-#####; retry on the rare concurrent-collision (unique_together).
        for _ in range(5):
            self.number = next_number(SubscriptionInvoice, self.tenant, "SINV")
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                self.number = ""
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.number
