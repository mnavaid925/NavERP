"""Seed the core spine: demo tenants + parties, org units, employments, activities.

Idempotent — safe to re-run. Tenants are get_or_create'd by slug; per-tenant spine data
is skipped if any Party already exists for that tenant. Run order: seed_core →
seed_accounts → seed_tenants.
"""
import datetime

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.navigation import parse_catalog
from apps.core.models import (
    ModuleAccessScope,
    Activity,
    Address,
    ContactMethod,
    Document,
    Employment,
    OrgUnit,
    Party,
    PartyRelationship,
    PartyRole,
    Tenant,
)

TENANTS = [
    {"name": "Acme Inc", "slug": "acme", "plan": "pro"},
    {"name": "Globex Corporation", "slug": "globex", "plan": "enterprise"},
]

DEPARTMENTS = ["Sales", "Finance", "Operations", "Engineering", "Human Resources"]

ORGS = [
    ("Initech LLC", "vendor"),
    ("Umbrella Supplies", "supplier"),
    ("Wayne Enterprises", "customer"),
    ("Stark Industries", "customer"),
    ("Hooli Partners", "partner"),
]
PEOPLE = [
    ("Olivia Martin", "employee", "Sales Manager"),
    ("Liam Johnson", "employee", "Accountant"),
    ("Emma Williams", "employee", "Operations Lead"),
    ("Noah Brown", "lead", ""),
    ("Ava Davis", "contact", ""),
    ("Sophia Miller", "employee", "HR Specialist"),
]


class Command(BaseCommand):
    help = "Seed core tenants and spine demo data (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        for spec in TENANTS:
            tenant, created = Tenant.objects.get_or_create(
                slug=spec["slug"],
                defaults={"name": spec["name"], "plan": spec["plan"], "is_active": True},
            )
            label = "created" if created else "exists"
            self.stdout.write(f"Tenant {tenant.name} [{label}]")

            if Party.objects.filter(tenant=tenant).exists():
                self.stdout.write("  core spine data already present — skipping")
            else:
                self._seed_tenant(tenant)

            # 0.6 module scopes have their OWN guard, deliberately NOT riding on the spine guard
            # above. A tenant-wide guard means anything added to this command later never reaches
            # the workspaces that already exist — which is exactly what happened here on the first
            # run: `continue` skipped the whole tenant, so no scope rows were created at all.
            self._seed_module_scopes(tenant)

        self.stdout.write(self.style.SUCCESS("core seed complete."))
        self.stdout.write("Next: run `seed_accounts` then `seed_tenants`.")

    def _seed_module_scopes(self, tenant):
        """0.6: one access-scope row per module in the catalog.

        Creates them in the DEFAULT posture (`data_scope="all"`, nothing enforcing) on purpose — a
        seeder must not silently restrict a workspace. Two rows are deliberately narrowed so the
        enforcing state is visible rather than theoretical, and both are read-only-ish choices a
        demo can safely show: HRM masked (the personnel-data bullet) and Accounting period-locked.

        Idempotent by slug, so re-running after the catalog changes only fills the gaps.
        """
        existing = set(ModuleAccessScope.objects.filter(tenant=tenant)
                       .values_list("module_slug", flat=True))
        narrowed = {
            "humanresourcemanagementhrm": {"data_scope": "team", "mask_sensitive": True},
            "accountingfinance": {"data_scope": "all", "requires_approval": True,
                                  "period_lock_until": timezone.localdate() - datetime.timedelta(days=1)},
        }
        created = 0
        for mod in parse_catalog():
            slug = "".join(ch if ch.isalnum() else "" for ch in (mod.get("title") or "").lower())[:40]
            if not slug or slug in existing:
                continue
            ModuleAccessScope.objects.create(
                tenant=tenant, module_number=mod["num"], module_slug=slug,
                module_title=mod["title"], **narrowed.get(slug, {}),
            )
            created += 1
        if created:
            self.stdout.write(f"  {tenant.name}: seeded {created} module access scope(s)")

    def _seed_tenant(self, tenant):
        company = OrgUnit.objects.create(tenant=tenant, kind="company", name=tenant.name)
        units = {"company": company}
        for dept in DEPARTMENTS:
            units[dept] = OrgUnit.objects.create(
                tenant=tenant, kind="department", name=dept, parent=company
            )

        # Organizations + their roles
        for name, role in ORGS:
            party = Party.objects.create(tenant=tenant, kind="organization", name=name,
                                         tax_id=f"TAX-{abs(hash(name)) % 1000000:06d}")
            PartyRole.objects.create(tenant=tenant, party=party, role=role, status="active",
                                     start_date=timezone.localdate())
            Address.objects.create(tenant=tenant, party=party, kind="billing",
                                   line1=f"{(abs(hash(name)) % 900) + 100} Market St",
                                   city="Springfield", country="USA")
            ContactMethod.objects.create(tenant=tenant, party=party, kind="email",
                                         value=f"contact@{name.split()[0].lower()}.example")

        # People + employments
        managers = []
        for idx, (name, role, title) in enumerate(PEOPLE):
            party = Party.objects.create(tenant=tenant, kind="person", name=name)
            PartyRole.objects.create(tenant=tenant, party=party, role=role, status="active",
                                     start_date=timezone.localdate())
            ContactMethod.objects.create(tenant=tenant, party=party, kind="email",
                                         value=f"{name.split()[0].lower()}@{tenant.slug}.example")
            if role == "employee":
                dept = DEPARTMENTS[idx % len(DEPARTMENTS)]
                Employment.objects.create(
                    tenant=tenant, party=party, org_unit=units[dept],
                    manager=managers[0] if managers else None, job_title=title,
                    hired_on=timezone.localdate() - datetime.timedelta(days=300 + idx * 40),
                    status="active",
                )
                managers.append(party)

        # A relationship + a couple of activities
        people = list(Party.objects.filter(tenant=tenant, kind="person"))
        if len(people) >= 2:
            PartyRelationship.objects.create(tenant=tenant, from_party=people[1],
                                             to_party=people[0], kind="reports_to")
        for i, subj in enumerate(["Kick-off call with customer", "Send onboarding pack",
                                   "Quarterly review meeting"]):
            Activity.objects.create(
                tenant=tenant, party=people[i % len(people)] if people else None,
                kind=["call", "task", "meeting"][i % 3], subject=subj,
                status=["done", "open", "open"][i % 3],
                due_at=timezone.now() + datetime.timedelta(days=i + 1),
            )

        doc = Document(tenant=tenant, name="Company Handbook", classification="internal", version="1.0")
        doc.file.save("handbook.txt", ContentFile(b"NavERP demo document."), save=False)
        doc.save()
        self.stdout.write("  seeded org units, parties, employments, activities, document")
