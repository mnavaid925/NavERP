"""Seed Module 0.1 data: subscriptions, invoices, branding, encryption keys, health
metrics - per tenant. Idempotent (skips a tenant that already has a subscription).
Also seeds 0.19 licensing data (feature catalog, plan grants, quotas, seats) through FOUR
INDEPENDENT per-entity blocks, each of which heals a partial state rather than skipping the
whole tenant. Run after seed_core and seed_accounts.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import Tenant
from apps.tenants.models import (
    BrandingSetting,
    EncryptionKey,
    EntitlementFeature,
    HealthMetric,
    LicenseAssignment,
    PlanEntitlement,
    Subscription,
    SubscriptionInvoice,
    UsageQuota,
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

            # 0.19 licensing. Same reasoning: its OWN per-entity guards, never a tenant-wide one.
            self._seed_licensing(tenant)

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

    def _seed_licensing(self, tenant):
        """0.19 licensing. FOUR INDEPENDENT per-entity blocks, never one tenant-wide guard.

        It creates NO `Subscription`: 0.1 owns those. The two 0.19 columns on that existing row
        (`auto_renew`, `grace_ends_on`) are backfilled only when still unset, so a re-run never
        overwrites a term somebody edited by hand in the UI.

        **Each block guards ITSELF and reports what it actually created.** I4: the shipped code
        had a single `if EntitlementFeature.objects.filter(tenant=tenant).exists(): return` in
        front of all four entities, so a tenant with features but no quotas or seats could never
        self-heal: delete a `UsageQuota`, re-run, and the seeder printed "seeded" and created
        nothing. That is the confident-prose failure L52 exists to stop, reached through a guard
        rather than through `get_or_create`.

        So the shape is: each entity is its own block, each block runs its own `get_or_create`
        calls, and each block COUNTS what it created and says so. Nothing is skipped wholesale,
        and the output is a statement about THIS run rather than a guess about the state of the
        database. The old `exists()` guard is not merely split four ways - it is REPLACED, because
        a per-entity `exists()` would still refuse to heal a HALF-seeded entity (one of three
        quotas deleted is not "no quotas"), whereas counting creations heals every partial state.

        `get_or_create` on a unique tuple is load-bearing rather than tidy throughout: the
        auto-numbered `number` column means a bare `create()` would mint a duplicate, and a
        duplicate `EntitlementFeature` code is a duplicate commercial feature.
        """
        sub = Subscription.objects.filter(tenant=tenant).order_by("-created_at").first()

        # The 0.19 columns on 0.1's row. Independent of every licensing entity, and deliberately
        # NOT behind any of their guards: it was unreachable for a tenant that already had
        # features, which is how a subscription kept a NULL grace window forever.
        if sub is not None and sub.grace_ends_on is None and sub.renews_on is not None:
            sub.grace_ends_on = sub.renews_on
            sub.save(update_fields=["grace_ends_on"])
            self.stdout.write(
                f"{tenant.name}: backfilled grace_ends_on on the existing subscription")

        created = 0
        created += self._seed_features(tenant)
        created += self._seed_grants(tenant, sub)
        created += self._seed_quotas(tenant, sub)
        created += self._seed_seats(tenant, sub)

        if created:
            self.stdout.write(self.style.SUCCESS(
                f"{tenant.name}: seeded 0.19 licensing - {created} new row(s) "
                f"(features, plan grants, quotas, seats)"))
        else:
            self.stdout.write(
                f"{tenant.name}: 0.19 licensing already complete - nothing created")

    def _seed_features(self, tenant):
        """Bullet 2, the feature catalog. Returns how many rows THIS run created.

        One of the four independent per-entity blocks (I4). Nothing here consults the state of any
        other 0.19 entity, so a tenant whose features were deleted re-acquires them even if its
        grants, quotas and seats are all intact - and vice versa.
        """
        feature_specs = [
            ("sso", "Single Sign-On", "boolean", "active", False,
             "Federated sign-in for every member of the workspace."),
            ("api_access", "Public API Access", "boolean", "active", False,
             "Token-authenticated access to the REST endpoints."),
            ("seats", "Named User Seats", "integer", "active", False,
             "How many named users this plan licenses."),
            ("sso_provider", "SSO Provider", "select", "active", True,
             "Which identity provider federated sign-in may use."),
            ("advanced_reporting", "Advanced Reporting", "boolean", "draft", True,
             "The scheduled report packs. Still a draft add-on, so NO plan grants it."),
            ("audit_export", "Audit Evidence Export", "boolean", "active", True,
             "Exportable control evidence. An add-on, granted per subscription below."),
        ]
        created = 0
        for code, name, priv, status, is_add_on, description in feature_specs:
            _feature, was_created = EntitlementFeature.objects.get_or_create(
                tenant=tenant, code=code,
                defaults={
                    "name": name, "description": description, "privilege_type": priv,
                    "status": status, "is_add_on": is_add_on, "is_active": status == "active",
                    "select_options": "entra_id,okta,onelogin" if priv == "select" else "",
                },
            )
            created += int(was_created)
        return created
    def _seed_grants(self, tenant, sub):
        """Bullet 2, the plan grants and the subscription overrides. Returns rows created.

        `subscription=None` is the PLAN row; the overrides pin the same grant at one subscription
        (Chargebee: subscription-level entitlements take precedence over catalog-level ones).

        The features are re-read here by `code` rather than handed over from `_seed_features`, so
        this block heals a missing grant even when the catalog is already complete - the coupling
        that made the old single guard unable to do either.
        """
        features = {f.code: f for f in EntitlementFeature.objects.filter(tenant=tenant)}
        if not features:
            # Nothing to grant against. NOT a silent skip: the catalog block has already run and
            # will have created it, so this can only mean the catalog was emptied between the two
            # calls. Say so rather than reporting success.
            self.stdout.write(self.style.WARNING(
                f"{tenant.name}: no EntitlementFeature rows - skipping plan grants"))
            return 0

        grant_specs = [
            ("free", "sso", "false", False),
            ("free", "api_access", "false", False),
            ("free", "seats", "3", False),
            ("starter", "sso", "false", False),
            ("starter", "api_access", "true", False),
            ("starter", "seats", "10", False),
            ("pro", "sso", "true", False),
            ("pro", "api_access", "true", False),
            ("pro", "seats", "50", False),
            # An add-on granted at the PLAN level, so the register shows an add-on row that is
            # NOT a subscription override - the two are different facts and the list shows both.
            ("pro", "sso_provider", "okta", True),
            ("enterprise", "sso", "true", False),
            ("enterprise", "api_access", "true", False),
            ("enterprise", "seats", "500", False),
            ("enterprise", "sso_provider", "entra_id", True),
        ]
        created = 0
        for plan, code, value, is_add_on in grant_specs:
            _grant, was_created = PlanEntitlement.objects.get_or_create(
                tenant=tenant, plan=plan, feature=features[code], subscription=None,
                defaults={"privilege_value": value, "is_add_on": is_add_on, "is_enabled": True},
            )
            created += int(was_created)

        if sub is not None:
            # A negotiated override ABOVE the plan allowance. `is_override` is a @property
            # derived from `subscription_id`, so nothing extra is set: the row existing at a
            # subscription IS the override, and it outranks the plan row.
            _ovr, was_created = PlanEntitlement.objects.get_or_create(
                tenant=tenant, plan=sub.plan, feature=features["seats"], subscription=sub,
                defaults={
                    "privilege_value": "75", "is_add_on": False, "is_enabled": True,
                    "notes": "Negotiated 75 seats on this subscription, above the plan allowance.",
                },
            )
            created += int(was_created)
            _ovr, was_created = PlanEntitlement.objects.get_or_create(
                tenant=tenant, plan=sub.plan, feature=features["audit_export"], subscription=sub,
                defaults={
                    "privilege_value": "true", "is_add_on": True, "is_enabled": True,
                    "notes": "Audit evidence export purchased as an add-on for this subscription.",
                },
            )
            created += int(was_created)
        return created
    def _seed_quotas(self, tenant, sub):
        """Bullet 3, the commercial ceilings. Returns rows created.

        `quota_limit` 0 means UNMETERED (mirroring `UsageRecord.included_allowance` returning
        None), which is why transactions is seeded at 0 rather than at some large number: the
        board must show all three states.

        A quota is CASCADE-linked to its subscription, so deleting one is exactly the partial
        state the old single guard could not heal. This block is independent of the other three.
        """
        if sub is None:
            # 0.1 owns subscriptions. With none, there is nothing for a ceiling to bound - and
            # saying so is the point: a silent return here would report "seeded" having seeded
            # nothing, which is the L52 failure.
            self.stdout.write(self.style.WARNING(
                f"{tenant.name}: no Subscription - skipping usage quotas (nothing to bound)"))
            return 0

        quota_specs = [
            ("api_calls", Decimal("750000.00"), 80, "alert", False),
            ("storage_mb", Decimal("102400.00"), 90, "charge", True),
            ("transactions", Decimal("0.00"), 80, "alert", False),
        ]
        created = 0
        for metric, limit, warn_pct, action, fair_use in quota_specs:
            _quota, was_created = UsageQuota.objects.get_or_create(
                tenant=tenant, subscription=sub, metric=metric, period="monthly",
                defaults={
                    "quota_limit": limit, "warn_at_pct": warn_pct,
                    "action_on_breach": action, "is_fair_use": fair_use,
                    "notes": "Seeded demo ceiling. `action_on_breach` is a RECORDED policy - "
                             "nothing in NavERP enforces it.",
                },
            )
            created += int(was_created)
        return created
    def _seed_seats(self, tenant, sub):
        """Bullet 1, the seat register. Returns rows created.

        Only users WHOSE TENANT IS THIS TENANT may be seated: `accounts.User.tenant` is nullable
        (the superuser has tenant=None), and seating one would make the board's count disagree
        with the register by exactly one (contract 1.4).

        The per-seat `exists()` check is what makes this block self-heal a HALF-seeded register:
        deleting one seat does not make the block conclude the register is complete.
        """
        if sub is None:
            self.stdout.write(self.style.WARNING(
                f"{tenant.name}: no Subscription - skipping the seat register"))
            return 0

        users = list(get_user_model().objects.filter(tenant=tenant).order_by("email")[:6])
        # (user index, module_slug, status, expires_on, notes)
        seat_specs = [
            (0, "", "active", None, "Workspace-wide seat."),
            (1, "", "active", None, "Workspace-wide seat."),
            (2, "accounting", "active", None, "Licensed for the accounting module only."),
            (3, "accounting", "active", None, "Licensed for the accounting module only."),
            (4, "crm", "active", timezone.localdate() - datetime.timedelta(days=3),
             "Expired: the display state is DERIVED from expires_on, not a stored status."),
            (5, "", "reclaimed", None, "Reclaimed by the demo; reclaim_reason is the verb's."),
        ]
        created = 0
        for idx, slug, status, expires_on, notes in seat_specs:
            if idx >= len(users):
                break
            # One seat per (user, module_slug) - the unique tuple `clean()` also guards, so a
            # second run skips rather than tripping it.
            if LicenseAssignment.objects.filter(
                tenant=tenant, user=users[idx], module_slug=slug
            ).exists():
                continue
            assignment = LicenseAssignment(
                tenant=tenant, user=users[idx], module_slug=slug, status=status,
                assignment_source="direct", subscription=sub,
                assigned_from=timezone.localdate() - datetime.timedelta(days=30),
                expires_on=expires_on, notes=notes,
            )
            if status == "reclaimed":
                # A seeder may set the one-writer stamp directly - the 0.1 usage seeder does the
                # same for is_billed/billed_at, and nothing else in the app may.
                assignment.reclaimed_on = timezone.now() - datetime.timedelta(days=5)
                assignment.reclaim_reason = "Seeded demo: seat returned to the pool."
            assignment.save()
            created += 1
        return created
