"""Seed identity & access: superuser, RBAC permission catalog, per-tenant roles,
tenant-admin + member users, and a sample invite. Idempotent. Run after seed_core.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Permission, Role, User, UserInvite
from apps.core.models import Tenant

PERMISSIONS = [
    ("core.party.view", "View parties", "0"),
    ("core.party.manage", "Manage parties", "0"),
    ("core.orgunit.manage", "Manage org units", "0"),
    ("accounts.user.view", "View users", "0"),
    ("accounts.user.manage", "Manage users", "0"),
    ("accounts.role.manage", "Manage roles", "0"),
    ("tenants.subscription.manage", "Manage subscriptions", "0"),
    ("tenants.branding.manage", "Manage branding", "0"),
    ("tenants.key.manage", "Manage encryption keys", "0"),
    ("tenants.health.view", "View tenant health", "0"),
    ("core.audit.view", "View audit log", "0"),
    ("dashboard.view", "View dashboard", "0"),
]

MEMBERS = [
    ("sales", "Sam", "Sales", "Member"),
    ("ops", "Olive", "Ops", "Member"),
]


class Command(BaseCommand):
    help = "Seed superuser, permissions, roles, tenant-admin & member users (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        # 1) Superuser (no tenant — by design)
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser(email="admin@naverp.local", username="admin", password="admin")
            self.stdout.write(self.style.SUCCESS("Superuser 'admin' created (password: admin)."))
        else:
            self.stdout.write("Superuser 'admin' exists.")

        # 2) Permission catalog (global)
        perms = []
        for codename, name, module in PERMISSIONS:
            perm, _ = Permission.objects.get_or_create(codename=codename, defaults={"name": name, "module": module})
            perms.append(perm)

        tenants = list(Tenant.objects.all())
        if not tenants:
            self.stdout.write(self.style.WARNING("No tenants found — run `seed_core` first."))
            return

        for tenant in tenants:
            admin_role, created = Role.objects.get_or_create(
                tenant=tenant, name="Administrator",
                defaults={"description": "Full workspace access", "is_system": True},
            )
            if created:
                admin_role.permissions.set(perms)
            member_role, created = Role.objects.get_or_create(
                tenant=tenant, name="Member",
                defaults={"description": "Standard access", "is_system": True},
            )
            if created:
                member_role.permissions.set([p for p in perms if p.codename.endswith(".view")])

            admin_username = f"admin_{tenant.slug}"
            if not User.objects.filter(username=admin_username).exists():
                User.objects.create_user(
                    email=f"admin@{tenant.slug}.example", username=admin_username, password="password",
                    first_name="Workspace", last_name="Admin", tenant=tenant,
                    is_tenant_admin=True, role=admin_role,
                )
                self.stdout.write(f"  {tenant.name}: tenant admin '{admin_username}' / password")

            for suffix, first, last, role_name in MEMBERS:
                username = f"{suffix}_{tenant.slug}"
                if not User.objects.filter(username=username).exists():
                    User.objects.create_user(
                        email=f"{suffix}@{tenant.slug}.example", username=username, password="password",
                        first_name=first, last_name=last, tenant=tenant, role=member_role,
                    )

            # A sample pending invite
            invite_email = f"invitee@{tenant.slug}.example"
            if not UserInvite.objects.filter(tenant=tenant, email=invite_email).exists():
                UserInvite.objects.create(
                    tenant=tenant, email=invite_email, role=member_role, status="pending",
                    expires_at=timezone.now() + timezone.timedelta(days=7),
                )

        self.stdout.write(self.style.SUCCESS("accounts seed complete."))
        self.stdout.write("Login as a TENANT ADMIN to see module data, e.g. admin_acme / password.")
        self.stdout.write(self.style.WARNING(
            "Note: superuser 'admin' has tenant=None — module pages show NO data when logged in as admin."
        ))
