"""Module 0.1 — Tenant & Subscription Management.

SaaS platform→tenant billing (Subscription, SubscriptionInvoice — distinct from any
future spine Invoice which is the tenant's own AR/AP), white-label branding, per-tenant
encryption keys (secret never stored — only prefix + hash), and health metrics.
"""
import hashlib
import secrets

from django.core.validators import RegexValidator
from django.db import IntegrityError, models, transaction
from django.utils import timezone

from apps.core.models import Tenant
from apps.core.utils import next_number

HEX_COLOR = RegexValidator(
    r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$",
    "Enter a valid hex color, e.g. #2563eb.",
)


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


class BrandingSetting(models.Model):
    tenant = models.OneToOneField("core.Tenant", on_delete=models.CASCADE, related_name="branding", db_index=True)
    logo = models.ImageField(upload_to="branding/", null=True, blank=True)
    primary_color = models.CharField(max_length=7, default="#2563eb", validators=[HEX_COLOR])
    accent_color = models.CharField(max_length=7, default="#1d4ed8", validators=[HEX_COLOR])
    email_from_name = models.CharField(max_length=120, blank=True)
    email_footer = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def save(self, *args, **kwargs):
        # Enforce the hex validator on every save (defense-in-depth vs CSS injection
        # into inline style= — covers programmatic writes that bypass the form).
        HEX_COLOR(self.primary_color)
        HEX_COLOR(self.accent_color)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Branding · {self.tenant}"


class EncryptionKey(models.Model):
    """Per-tenant key handle. The plaintext is shown exactly once on creation/rotation
    and NEVER stored — only its prefix (for identification) and a SHA-256 hash."""

    STATUS_CHOICES = [("active", "Active"), ("rotated", "Rotated"), ("revoked", "Revoked")]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="encryption_keys", db_index=True)
    name = models.CharField(max_length=120)
    prefix = models.CharField(max_length=16, editable=False)
    key_hash = models.CharField(max_length=128, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    last_rotated_at = models.DateTimeField(null=True, blank=True)  # system-set, out of forms (L22)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @staticmethod
    def generate_plaintext():
        return "nk_" + secrets.token_urlsafe(32)

    def set_secret(self, plaintext):
        self.prefix = plaintext[:10]
        self.key_hash = hashlib.sha256(plaintext.encode()).hexdigest()

    def __str__(self):
        return f"{self.name} ({self.prefix}…)"


class HealthMetric(models.Model):
    METRIC_CHOICES = [
        ("users", "Active Users"),
        ("storage_mb", "Storage (MB)"),
        ("api_calls", "API Calls"),
        ("db_rows", "DB Rows"),
        ("uptime_pct", "Uptime %"),
    ]
    STATUS_CHOICES = [("ok", "OK"), ("warning", "Warning"), ("critical", "Critical")]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="health_metrics", db_index=True)
    metric = models.CharField(max_length=20, choices=METRIC_CHOICES)
    value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ok")
    recorded_at = models.DateTimeField(null=True, blank=True)  # system-set, out of forms (L22)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "metric", "-created_at"], name="health_tenant_metric_idx"),
        ]

    def __str__(self):
        return f"{self.get_metric_display()}: {self.value}"
