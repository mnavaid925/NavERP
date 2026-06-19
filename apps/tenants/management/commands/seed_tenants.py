"""Seed Module 0.1 data: subscriptions, invoices, branding, encryption keys, health
metrics — per tenant. Idempotent (skips a tenant that already has a subscription).
Run after seed_core and seed_accounts.
"""
import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import Tenant
from apps.tenants.models import (
    BrandingSetting,
    EncryptionKey,
    HealthMetric,
    Subscription,
    SubscriptionInvoice,
)

PLAN_AMOUNT = {"free": Decimal("0"), "starter": Decimal("49"), "pro": Decimal("149"),
               "enterprise": Decimal("499")}
HEALTH = [
    ("users", Decimal("12"), "ok"),
    ("storage_mb", Decimal("2048"), "ok"),
    ("api_calls", Decimal("18450"), "warning"),
    ("uptime_pct", Decimal("99.95"), "ok"),
]


class Command(BaseCommand):
    help = "Seed subscriptions, invoices, branding, keys, health metrics (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        tenants = list(Tenant.objects.all())
        if not tenants:
            self.stdout.write(self.style.WARNING("No tenants found — run `seed_core` first."))
            return

        for tenant in tenants:
            if Subscription.objects.filter(tenant=tenant).exists():
                self.stdout.write(f"{tenant.name}: subscription exists — skipping")
                continue

            amount = PLAN_AMOUNT.get(tenant.plan, Decimal("49"))
            sub = Subscription.objects.create(
                tenant=tenant, plan=tenant.plan if tenant.plan != "free" else "pro",
                status="active", billing_cycle="monthly", amount=amount, seats=10,
                started_on=timezone.localdate() - datetime.timedelta(days=40),
                renews_on=timezone.localdate() + datetime.timedelta(days=20),
            )

            # One paid invoice + one open invoice
            SubscriptionInvoice.objects.create(
                tenant=tenant, subscription=sub, status="paid", amount=amount,
                issued_on=timezone.localdate() - datetime.timedelta(days=40),
                paid_at=timezone.now() - datetime.timedelta(days=39),
            )
            SubscriptionInvoice.objects.create(
                tenant=tenant, subscription=sub, status="open", amount=amount,
                issued_on=timezone.localdate() - datetime.timedelta(days=10),
                due_on=timezone.localdate() + datetime.timedelta(days=20),
            )

            BrandingSetting.objects.get_or_create(
                tenant=tenant,
                defaults={"primary_color": "#2563eb", "accent_color": "#1d4ed8",
                          "email_from_name": tenant.name},
            )

            for name in ("Primary API Key", "Data-at-rest Key"):
                if not EncryptionKey.objects.filter(tenant=tenant, name=name).exists():
                    key = EncryptionKey(tenant=tenant, name=name, status="active")
                    key.set_secret(EncryptionKey.generate_plaintext())  # plaintext discarded (seed)
                    key.save()

            for metric, value, status in HEALTH:
                HealthMetric.objects.create(
                    tenant=tenant, metric=metric, value=value, status=status,
                    recorded_at=timezone.now(),
                )

            self.stdout.write(self.style.SUCCESS(f"{tenant.name}: seeded subscription + 0.1 data"))

        self.stdout.write(self.style.SUCCESS("tenants seed complete."))
