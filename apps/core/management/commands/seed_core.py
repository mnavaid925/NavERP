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
    ApprovalLimit,
    BusinessRule,
    SlaRule,
    WorkflowDefinition,
    WorkflowStep,
    BusinessCalendar,
    CustomFieldDefinition,
    FeatureFlag,
    Holiday,
    NumberingScheme,
    SettingDefinition,
    ConsentPurpose,
    ConsentRecord,
    DataSubjectRequest,
    PiiClassification,
    RegulatoryFramework,
    RetentionPolicy,
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
            self._seed_privacy(tenant)
            self._seed_configuration(tenant)
            self._seed_workflow(tenant)

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

    def _seed_privacy(self, tenant):
        """0.8: consent purposes, a couple of events, DSARs, retention policies and frameworks.

        Deliberately does NOT seed any PiiClassification row and does NOT run the scan: the map is
        meant to be populated by the operator pressing Run scan on their own schema, and a seeder
        that pre-filled 177 suggestions would make the "human confirms" step look already done.

        Frameworks are created DISABLED. A workspace claiming HIPAA because a seeder said so would be
        a compliance lie, and enabling one is what starts the DSAR clock — so the seeded DSARs carry
        NO due date until an operator enables a regime, which is the honest state to demonstrate.
        """
        purposes = [
            ("Marketing email", "marketing-email", "consent", True),
            ("Product analytics", "product-analytics", "legitimate_interest", False),
            ("Service communications", "service-comms", "contract", False),
        ]
        created_purposes = []
        for name, code, basis, optional in purposes:
            obj, _ = ConsentPurpose.objects.get_or_create(
                tenant=tenant, code=code,
                defaults={"name": name, "lawful_basis": basis, "is_optional": optional,
                          "description": f"Seeded demo purpose: {name}."},
            )
            created_purposes.append(obj)

        if not ConsentRecord.objects.filter(tenant=tenant).exists():
            parties = list(Party.objects.filter(tenant=tenant).order_by("id")[:3])
            for idx, party in enumerate(parties):
                for jdx, purpose in enumerate(created_purposes):
                    # A mix on purpose: granted, withdrawn and never-asked all render differently
                    # on the matrix, and a seeder that only granted would hide two of the three.
                    if (idx + jdx) % 3 == 1:
                        continue
                    action = "withdrawn" if (idx + jdx) % 3 == 2 else "granted"
                    ConsentRecord.objects.create(
                        tenant=tenant, party=party, purpose=purpose, action=action,
                        source="web_form", evidence=f"seed-form-{party.pk}-{purpose.pk}",
                    )

        if not DataSubjectRequest.objects.filter(tenant=tenant).exists():
            parties = list(Party.objects.filter(tenant=tenant).order_by("id")[:3])
            kinds = ["access", "erasure", "rectification"]
            for idx, party in enumerate(parties):
                DataSubjectRequest.objects.create(
                    tenant=tenant, subject=party, kind=kinds[idx % len(kinds)],
                    detail="Seeded demo request: the subject asked for their data.",
                    identity_verified=(idx == 0),
                    verification_note="Seeded: verified by callback." if idx == 0 else "",
                )

        if not RetentionPolicy.objects.filter(tenant=tenant).exists():
            RetentionPolicy.objects.create(
                tenant=tenant, name="Audit trail", data_category="Audit and activity records",
                model_label="core.AuditLog", retention_months=84, action="archive", basis="legal",
                notes="Seeded: statutory retention for financial audit evidence.",
            )
            RetentionPolicy.objects.create(
                tenant=tenant, name="Marketing consent", data_category="Consent evidence",
                model_label="core.ConsentRecord", retention_months=36, action="review",
                basis="consent",
                notes="Seeded: consent evidence is kept while the relationship lasts plus a margin.",
            )
            RetentionPolicy.objects.create(
                tenant=tenant, name="Customer contacts", data_category="Contact details",
                model_label="", retention_months=24, action="review", basis="operational",
                notes="Seeded: a category that spans tables, so it is deliberately NOT computable.",
            )

        for code, label in RegulatoryFramework.CODE_CHOICES:
            RegulatoryFramework.objects.get_or_create(
                tenant=tenant, code=code, defaults={"label": label, "is_enabled": False},
            )

    def _seed_configuration(self, tenant):
        """0.10: setting definitions, feature flags, numbering schemes and a working calendar.

        `SettingDefinition` rows are PLATFORM-level (no tenant FK) and are seeded once for everyone,
        while the tenant-scoped pieces are guarded per tenant.

        Numbering: seeds only a handful of the 300+ prefixes the repo actually mints. That is
        deliberate — the reconciliation board exists to show the gap, and pre-filling every prefix
        would hide the very thing the board is for.
        """
        definitions = [
            ("accounting.default_payment_terms", "Default payment terms (days)",
             "accounting", "integer", "30", [], "Applied to new bills and invoices.", False),
            ("accounting.fiscal_year_start_month", "Fiscal year start month",
             "accounting", "integer", "1", [], "1 = January.", False),
            ("core.date_display_format", "Date display format", "core", "choice", "iso",
             [["iso", "YYYY-MM-DD"], ["uk", "DD/MM/YYYY"], ["us", "MM/DD/YYYY"]],
             "How dates render in lists and detail pages.", False),
            ("core.session_idle_timeout_minutes", "Session idle timeout (minutes)",
             "core", "integer", "30", [], "Enforced by SessionTimeoutMiddleware.", True),
            ("crm.lead_duplicate_check", "Warn on duplicate leads",
             "crm", "boolean", "true", [], "Shows the duplicate warning on lead create.", False),
            ("projects.require_timesheet_approval", "Require timesheet approval",
             "projects", "boolean", "true", [], "Approved hours only count toward billing.", False),
        ]
        for key, label, module_slug, value_type, default_value, choices, help_text, locked in definitions:
            SettingDefinition.objects.get_or_create(
                key=key,
                defaults={"label": label, "module_slug": module_slug, "value_type": value_type,
                          "default_value": default_value, "choices": choices,
                          "help_text": help_text, "is_locked": locked},
            )

        flags = [
            ("projects.gantt", "Interactive Gantt timeline", False, ""),
            ("crm.kanban_board", "Kanban pipeline board", True, ""),
            ("core.custom_fields", "Custom fields on forms", False, ""),
            ("projects.ai_forecast", "AI schedule forecast", False, "enterprise"),
        ]
        for key, label, enabled, plan in flags:
            FeatureFlag.objects.get_or_create(
                tenant=tenant, key=key,
                defaults={"label": label, "is_enabled": enabled, "applies_to_plan": plan,
                          "description": f"Seeded demo flag: {label}."},
            )

        # A handful of the prefixes the repo really mints, plus one that NO model mints so the
        # reconciliation board demonstrates its "configured but nothing uses it" branch.
        schemes = [
            ("Purchase Order", "PO", "never"),
            ("Purchase Requisition", "PRQ", "never"),
            ("Sales Invoice", "SINV", "yearly"),
            ("Journal Entry", "JE", "yearly"),
            ("Retired Document Kind", "ZZZ", "never"),
        ]
        for kind, prefix, reset in schemes:
            NumberingScheme.objects.get_or_create(
                tenant=tenant, prefix=prefix,
                defaults={"document_kind": kind, "reset_rule": reset},
            )

        BusinessCalendar.objects.get_or_create(
            tenant=tenant,
            defaults={"working_days": [1, 2, 3, 4, 5], "timezone_name": "Europe/London",
                      "notes": "Seeded demo calendar: Mon-Fri working week."},
        )

        if not Holiday.objects.filter(tenant=tenant).exists():
            year = timezone.localdate().year
            for name, month, day, recurring in [
                ("New Year's Day", 1, 1, True),
                ("Christmas Day", 12, 25, True),
                ("Boxing Day", 12, 26, True),
            ]:
                Holiday.objects.create(tenant=tenant, name=name,
                                       date=datetime.date(year, month, day),
                                       is_recurring=recurring, region="UK")
            # A one-off in the FUTURE so the "upcoming" list on the board is never empty.
            Holiday.objects.create(
                tenant=tenant, name="Company Foundation Day",
                date=timezone.localdate() + datetime.timedelta(days=45),
                is_recurring=False, region="UK",
                notes="Seeded one-off so the upcoming-holidays list has content.",
            )

        if not CustomFieldDefinition.objects.filter(tenant=tenant).exists():
            CustomFieldDefinition.objects.create(
                tenant=tenant, module_slug="crm", entity_label="crm.Lead",
                field_key="referral_source", label="Referral source", field_type="choice",
                choices=["search", "referral", "event", "outbound"],
                help_text="Seeded demo custom field.", display_order=1,
            )
            CustomFieldDefinition.objects.create(
                tenant=tenant, module_slug="projects", entity_label="projects.Project",
                field_key="cost_code", label="Internal cost code", field_type="text",
                validation_regex="[A-Z]{2}-[0-9]{4}",
                help_text="Seeded demo custom field with a format rule, e.g. AB-1234.",
                display_order=2,
            )

    def _seed_workflow(self, tenant):
        """0.11: the workflow registry, limits, SLA rules and business rules.

        Every seeded definition points at a REAL engine label that `apps/core/workflow.py` monitors,
        except one, deliberately left pointing at a model that is NOT a monitored queue so the
        process-monitoring board's unmonitored-process flag is demonstrated rather than theoretical.

        No approval DECISION rows are seeded. Those belong to the modules that own the engines
        (procurement, inventory, projects, crm, hrm) and their own seeders create them; this command
        registers and describes, and does not invent decisions in another module's table.

        `accounts.Role` is imported INSIDE the method: core is imported by accounts, so a module-level
        import would be circular.
        """
        from apps.accounts.models import Role

        definitions = [
            ("Purchase requisition approval", "procurement", "procurement.RequisitionApproval",
             "Two-tier requisition approval with a value threshold.", 48),
            ("Purchase order approval", "inventory", "inventory.PurchaseOrderApproval",
             "Warehouse purchase-order sign-off.", 24),
            ("Stock transfer approval", "inventory", "inventory.TransferApproval",
             "Inter-location transfer sign-off.", 24),
            ("Offer approval", "hrm", "hrm.OfferApproval",
             "Offer letter approval before issue.", 72),
            ("Client approval request", "projects", "projects.ClientApprovalRequest",
             "Client sign-off on a deliverable.", 120),
            ("Project approval gate", "projects", "projects.ProjectApprovalGate",
             "Stage-gate approval on a project.", 48),
            ("CRM approval request", "crm", "crm.ApprovalRequest",
             "Discount and terms approval.", 24),
            # NOT a monitored queue on purpose: ApprovalRoutingRule is a rule table, not a queue.
            ("Vendor onboarding review", "procurement", "procurement.ApprovalRoutingRule",
             "Seeded example of a process whose engine is a rule table, not a queue.", 96),
        ]
        for name, module_slug, engine, description, target in definitions:
            definition, created = WorkflowDefinition.objects.get_or_create(
                tenant=tenant, name=name,
                defaults={"module_slug": module_slug, "engine_label": engine,
                          "description": description, "target_hours": target},
            )
            if created and engine in ("procurement.RequisitionApproval",
                                      "projects.ProjectApprovalGate"):
                for seq, step_name, parallel, threshold in [
                    (1, "Line manager review", False, None),
                    (2, "Finance review", False, "10000.00"),
                    (3, "Director sign-off", True, "50000.00"),
                ]:
                    WorkflowStep.objects.create(
                        tenant=tenant, definition=definition, sequence=seq, name=step_name,
                        is_parallel=parallel, threshold_amount=threshold,
                    )

        admin_role = Role.objects.filter(tenant=tenant, name="Administrator").first()
        member_role = Role.objects.filter(tenant=tenant, name="Member").first()
        if member_role:
            for module_slug, amount in [("procurement", "5000.00"), ("inventory", "10000.00"),
                                        ("projects", "2500.00")]:
                ApprovalLimit.objects.get_or_create(
                    tenant=tenant, module_slug=module_slug, role=member_role,
                    defaults={"max_amount": amount,
                              "notes": "Seeded demo limit: above this the approval escalates."},
                )
        if admin_role:
            ApprovalLimit.objects.get_or_create(
                tenant=tenant, module_slug="procurement", role=admin_role,
                defaults={"max_amount": "250000.00", "notes": "Seeded demo limit."},
            )

        sla_rules = [
            ("Requisition ageing", "procurement", 48, "escalate"),
            ("Offer ageing", "hrm", 72, "remind"),
            ("Transfer ageing", "inventory", 24, "remind"),
            ("Client approval ageing", "projects", 120, "escalate"),
        ]
        for name, module_slug, hours, action in sla_rules:
            SlaRule.objects.get_or_create(
                tenant=tenant, name=name,
                defaults={"module_slug": module_slug, "hours": hours, "action": action,
                          "escalate_to_role": admin_role if action == "escalate" else None,
                          "notes": "Seeded demo SLA rule. Nothing acts on it, by design."},
            )

        business_rules = [
            ("Large requisition needs finance", "procurement", "on_create",
             {"all": [{"field": "amount", "op": "gt", "value": 10000}]}, "require_approval",
             {"role": "Administrator"}, 10),
            ("High-value PO needs director", "inventory", "on_create",
             {"all": [{"field": "total", "op": "gte", "value": 50000}]}, "require_approval",
             {"role": "Administrator"}, 20),
            ("Expiring contract flagged", "procurement", "on_evaluation",
             {"all": [{"field": "days_to_expiry", "op": "lte", "value": 30}]}, "flag", {}, 30),
            ("Rush order notify ops", "projects", "on_status_change",
             {"any": [{"field": "priority", "op": "eq", "value": "urgent"},
                      {"field": "tags", "op": "contains", "value": "rush"}]}, "notify_role",
             {"role": "Member"}, 40),
        ]
        for name, module_slug, trigger, condition, action, payload, priority in business_rules:
            BusinessRule.objects.get_or_create(
                tenant=tenant, name=name,
                defaults={"module_slug": module_slug, "trigger": trigger, "condition": condition,
                          "action": action, "action_payload": payload, "priority": priority,
                          "notes": "Seeded demo rule. Evaluated on request; nothing executes it."},
            )
