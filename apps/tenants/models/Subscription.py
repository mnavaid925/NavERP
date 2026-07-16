"""tenants — Subscription models (split from apps/tenants/models.py)."""
from apps.tenants.models._base import *  # noqa: F401,F403


class Subscription(models.Model):
    PLAN_CHOICES = Tenant.PLAN_CHOICES
    STATUS_CHOICES = [
        ("trialing", "Trialing"),
        ("active", "Active"),
        ("past_due", "Past Due"),
        ("canceled", "Canceled"),
        ("incomplete", "Incomplete"),
    ]
    BILLING_CHOICES = [("monthly", "Monthly"), ("yearly", "Yearly")]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="subscriptions", db_index=True)
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default="starter")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="trialing")
    billing_cycle = models.CharField(max_length=10, choices=BILLING_CHOICES, default="monthly")
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    seats = models.PositiveIntegerField(default=5)
    started_on = models.DateField(null=True, blank=True)
    renews_on = models.DateField(null=True, blank=True)
    # Stripe linkage — set by the webhook, excluded from forms.
    stripe_customer_id = models.CharField(max_length=120, blank=True)
    stripe_subscription_id = models.CharField(max_length=120, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.tenant} · {self.get_plan_display()}"

    def days_left(self):
        if not self.renews_on:
            return None
        return (self.renews_on - timezone.localdate()).days
