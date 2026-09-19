"""Seed identity & access: superuser, RBAC permission catalog, per-tenant roles,
tenant-admin + member users, and a sample invite. Idempotent. Run after seed_core.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import ModuleAccessScope, SensitiveFieldMask

from apps.accounts.models import (
    AccessRequest,
    AccessReview,
    AccessReviewItem,
    ElevationGrant,
    LoginAttempt,
    PasswordPolicy,
    Permission,
    Role,
    User,
    UserImportBatch,
    UserInvite,
)
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

            # 0.2 access governance. Own guards per entity, NOT a tenant-wide one — a guard that
            # skips the whole tenant would mean anything added here later never reaches the
            # workspaces that already exist (exactly what happened to usage metering in
            # seed_tenants).
            self._seed_access_governance(tenant, admin_role, member_role)
            self._seed_auth_security(tenant)
            self._seed_field_masks(tenant, admin_role)

        self.stdout.write(self.style.SUCCESS("accounts seed complete."))
        self.stdout.write("Login as a TENANT ADMIN to see module data, e.g. admin_acme / password.")
        self.stdout.write(self.style.WARNING(
            "Note: superuser 'admin' has tenant=None — module pages show NO data when logged in as admin."
        ))

    def _seed_access_governance(self, tenant, admin_role, member_role):
        """Access requests, elevations, a certification campaign and an import batch.

        Seeds all four states a reviewer needs to see: an ACTIVE time-bound grant, a PENDING
        request, an EXPIRED grant whose role is still assigned (the orphan the certification board
        exists to catch), a LIVE elevation, and a certification campaign with one attested, one
        revoked and one undecided line.
        """
        admin = User.objects.filter(tenant=tenant, username=f"admin_{tenant.slug}").first()
        if admin is None:
            return
        members = list(User.objects.filter(tenant=tenant, role=member_role)
                       .exclude(pk=admin.pk).order_by("username"))
        if not members:
            return
        requester = members[0]
        other = members[1] if len(members) > 1 else members[0]

        # ---- bullet 3: one active grant, one pending, one expired-but-still-assigned
        if not AccessRequest.objects.filter(tenant=tenant).exists():
            AccessRequest.objects.create(
                tenant=tenant, requester=requester, requested_role=member_role,
                justification="Needs member access for the current project rotation.",
                requested_days=30, status="approved", decided_by=admin,
                decided_at=timezone.now() - timezone.timedelta(days=5),
                decision_note="Approved for the rotation.",
                granted_until=timezone.now() + timezone.timedelta(days=25),
            )
            AccessRequest.objects.create(
                tenant=tenant, requester=other, requested_role=admin_role,
                justification="Covering for the workspace admin while they are on leave.",
                requested_days=10, status="pending",
            )
            # Expired window, role deliberately left assigned — the orphan-account cross-check.
            expired = AccessRequest.objects.create(
                tenant=tenant, requester=requester, requested_role=admin_role,
                justification="Temporary admin cover for the migration weekend.",
                requested_days=7, status="approved", decided_by=admin,
                decided_at=timezone.now() - timezone.timedelta(days=30),
                decision_note="Approved for the migration window only.",
                granted_until=timezone.now() - timezone.timedelta(days=23),
            )
            if expired.requested_role_id:
                requester.role = expired.requested_role
                requester.save(update_fields=["role"])

        # ---- bullet 5: one live elevation and one already revoked
        if not ElevationGrant.objects.filter(tenant=tenant).exists():
            ElevationGrant.objects.create(
                tenant=tenant, user=other, scope="tenant_admin",
                reason="Investigating a data inconsistency reported by the client.",
                starts_at=timezone.now() - timezone.timedelta(hours=1),
                expires_at=timezone.now() + timezone.timedelta(hours=3),
                status="active", requested_by=admin, approved_by=admin,
                approved_at=timezone.now() - timezone.timedelta(hours=1),
            )
            ElevationGrant.objects.create(
                tenant=tenant, user=requester, scope="staff",
                reason="Bulk-correcting migrated reference data.",
                starts_at=timezone.now() - timezone.timedelta(days=4),
                expires_at=timezone.now() - timezone.timedelta(days=3),
                status="revoked", requested_by=admin, approved_by=admin,
                approved_at=timezone.now() - timezone.timedelta(days=4),
                revoked_by=admin, revoked_at=timezone.now() - timezone.timedelta(days=3),
            )

        # ---- bullet 4: a closed-out campaign with attested / revoked / undecided lines
        if not AccessReview.objects.filter(tenant=tenant).exists():
            review = AccessReview.objects.create(
                tenant=tenant, name="Q3 entitlement certification",
                status="open", due_on=timezone.localdate() + timezone.timedelta(days=14),
                created_by=admin,
            )
            decisions = ["attest", "revoke", "pending"]
            for idx, user_obj in enumerate(members[:3]):
                AccessReviewItem.objects.create(
                    tenant=tenant, review=review, user=user_obj, role=member_role,
                    decision=decisions[idx % len(decisions)],
                    decided_by=admin if decisions[idx % len(decisions)] != "pending" else None,
                    decided_at=(timezone.now() - timezone.timedelta(days=1)
                                if decisions[idx % len(decisions)] != "pending" else None),
                    note="Confirmed with the line manager." if idx == 0 else "",
                )

        # ---- bullet 2: a validated batch, staged but NOT committed
        if not UserImportBatch.objects.filter(tenant=tenant).exists():
            UserImportBatch.objects.create(
                tenant=tenant, file_name="q4-intake.csv", uploaded_by=admin,
                status="validated", row_count=4, error_count=1,
                errors=[{"line": 4, "error": "email already exists: invitee@%s.example" % tenant.slug}],
                staged_rows=[
                    {"email": f"nina.patel@{tenant.slug}.example", "username": f"nina_{tenant.slug}",
                     "first_name": "Nina", "last_name": "Patel", "role_id": member_role.pk},
                    {"email": f"omar.haddad@{tenant.slug}.example", "username": f"omar_{tenant.slug}",
                     "first_name": "Omar", "last_name": "Haddad", "role_id": member_role.pk},
                    {"email": f"pia.lindqvist@{tenant.slug}.example", "username": f"pia_{tenant.slug}",
                     "first_name": "Pia", "last_name": "Lindqvist", "role_id": None},
                ],
            )

    def _seed_auth_security(self, tenant):
        """0.4: a credential policy and a realistic spread of login attempts.

        Deliberately does NOT seed an MfaDevice. A confirmed device on a demo account would mean
        that account can no longer sign in through the UI without a code the seeder cannot tell the
        user — a footgun dressed as a demo. The MFA flow is exercised by temp/smoke_02.../smoke_04
        instead, and the enrolment path is fully reachable from the UI.
        """
        admin = User.objects.filter(tenant=tenant, username=f"admin_{tenant.slug}").first()
        PasswordPolicy.objects.get_or_create(
            tenant=tenant,
            defaults={"is_enforced": False, "min_length": 12, "require_symbol": False,
                      "max_age_days": 0, "prevent_reuse_count": 0},
        )

        if LoginAttempt.objects.filter(tenant=tenant).exists():
            return
        rows = [
            (admin, admin.email, "203.0.113.10", "Mozilla/5.0 (Macintosh) Smoke", True, 0, []),
            (admin, admin.email, "203.0.113.10", "Mozilla/5.0 (Macintosh) Smoke", True, 0, []),
            (None, "nobody@nowhere.example", "198.51.100.77", "curl/8.0", False, 30, ["new_ip"]),
            (None, "nobody@nowhere.example", "198.51.100.77", "curl/8.0", False, 70,
             ["new_ip", "recent_failures"]),
            (admin, admin.email, "198.51.100.99", "Mozilla/5.0 (Windows) Unknown", False, 100,
             ["new_ip", "new_device", "recent_failures"]),
        ]
        for user_obj, identifier, ip, ua, ok, score, reasons in rows:
            LoginAttempt.objects.create(
                tenant=tenant, user=user_obj, identifier=identifier, ip=ip, user_agent=ua,
                success=ok, risk_score=score, risk_reasons=reasons,
            )

    def _seed_field_masks(self, tenant, admin_role):
        """0.6: two mask rules demonstrating the mechanism, one of them role-exempt.

        Seeded here rather than in `seed_core` because `exempt_roles` points at `accounts.Role`, and
        roles do not exist until this command has run (the documented order is
        seed_core -> seed_accounts -> seed_tenants).
        """
        hrm = ModuleAccessScope.objects.filter(tenant=tenant, module_slug="humanresourcemanagementhrm").first()
        if hrm is None:
            return
        rules = [
            ("bank_account", "last4", [admin_role]),
            ("national_id", "partial", []),
        ]
        for field_name, style, exempt in rules:
            mask, created = SensitiveFieldMask.objects.get_or_create(
                tenant=tenant, scope=hrm, field_name=field_name,
                defaults={"mask_style": style,
                          "notes": "Seeded demo mask for the HRM personnel-data bullet."},
            )
            if created and exempt:
                mask.exempt_roles.set(exempt)
