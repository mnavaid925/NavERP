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
    UsageRecord,
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
            else:
                self._seed_subscription(tenant)

            # Usage metering has its OWN guard rather than riding on the subscription one. A
            # tenant-wide guard would mean that adding a new entity to this command never seeds
            # it for workspaces that already exist — which is exactly what happened when usage
            # metering was first added here: Acme and Globex were skipped and got no usage rows.
            self._seed_usage(tenant)

        self.stdout.write(self.style.SUCCESS("tenants seed complete."))

    def _seed_subscription(self, tenant):
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

    def _seed_usage(self, tenant):
        """0.1 usage metering. Own guard — see the comment in `handle()`.

        Sized against the PRO allowance table on purpose so the demo exercises BOTH states:
        api_calls sits inside its 500k allowance, while storage_mb (61440 > 51200) and
        transactions (120000 > 100000) are genuine overages. On the enterprise tenant the
        allowance table is empty, so every metric renders as Unmetered — the third state, and
        the reason `included_allowance` returns None rather than 0.
        """
        if UsageRecord.objects.filter(tenant=tenant).exists():
            return
        sub = Subscription.objects.filter(tenant=tenant).order_by("-created_at").first()
        if sub is None:
            return
        paid_invoice = (SubscriptionInvoice.objects
                        .filter(tenant=tenant, status="paid")
                        .order_by("-issued_on").first())

        period_start = timezone.localdate() - datetime.timedelta(days=30)
        period_end = timezone.localdate()
        usage_rows = [
            ("api_calls", Decimal("320000.00"), False, None),
            ("storage_mb", Decimal("61440.00"), False, None),
            ("transactions", Decimal("120000.00"), False, None),
            # Already invoiced: linked to the paid invoice and frozen. `usagerecord_mark_billed`
            # is the only writer of is_billed/billed_at in the app; a seeder sets them directly.
            ("api_calls", Decimal("280000.00"), True, paid_invoice),
        ]
        for metric, qty, billed, invoice in usage_rows:
            UsageRecord.objects.create(
                tenant=tenant, subscription=sub, metric=metric, quantity=qty,
                period_start=period_start, period_end=period_end,
                subscription_invoice=invoice, is_billed=billed,
                billed_at=timezone.now() - datetime.timedelta(days=9) if billed else None,
                notes="Seeded demo usage.",
            )
        self.stdout.write(self.style.SUCCESS(f"{tenant.name}: seeded usage metering"))
