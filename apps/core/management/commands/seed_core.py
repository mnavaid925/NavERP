"""Seed the core spine: demo tenants + parties, org units, employments, activities.

Idempotent — safe to re-run. Tenants are get_or_create'd by slug; per-tenant spine data
is skipped if any Party already exists for that tenant. Run order: seed_core →
seed_accounts → seed_tenants.
"""
import datetime
from decimal import Decimal

from django.apps import apps as django_apps
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
    NotificationChannel,
    NotificationRule,
    NotificationTemplate,
    ProviderConfig,
    ApiCredential,
    ConnectorDefinition,
    MappingTemplate,
    RateLimitPolicy,
    SyncSchedule,
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
    Language,
    LocaleProfile,
    StatutoryRule,
    TimeZone,
    BackupJob,
    DataArchive,
    EnvironmentInstance,
    LegalHold,
    RecoveryDrill,
    RecoveryPosture,
    RestoreRecord,
    ServiceComponent,
    AlertRule,
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
        # 0.15's Language and TimeZone are GLOBAL registries (no tenant FK), so they are seeded ONCE
        # here — outside the tenant loop — rather than per workspace. Seeding them per tenant would
        # imply they belong to one, which is exactly the mistake their missing FK prevents.
        self._seed_localization_globals()

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
            self._seed_notifications(tenant)
            self._seed_integrations(tenant)
            self._seed_localization(tenant)
            self._seed_backup(tenant)
            self._seed_monitoring(tenant)

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

    def _seed_notifications(self, tenant):
        """0.12: channels, templates, routing rules and provider configs.

        Three deliberate omissions, each the honest state to show:

        * **Only email and in-app are ENABLED.** A channel is enabled only when a provider sits
          behind it; enabling SMS with no gateway would be a switch that does nothing.
        * **No `NotificationPreference` rows are seeded.** A preference is a member's own choice, and
          a seeder inventing opt-outs would be fabricating consent. Absence means "take the rule's
          default", which is the correct starting state.
        * **No delivery rows are seeded anywhere.** Delivery records belong to the modules that own
          the webhooks and notifications; this command does not invent rows in another app's tables.

        `accounts.Role` is imported here for the same reason as in `_seed_workflow`: core is imported
        by accounts, so a module-level import would be circular.
        """
        from apps.accounts.models import Role

        channels = [
            ("email", "Email", True, "Enabled: an SMTP provider is configured below."),
            ("in_app", "In-app", True, "Enabled: delivered by the module's own in-app register."),
            ("sms", "SMS", False, "Disabled until an SMS gateway is configured."),
            ("push", "Push", False, "Disabled: no push provider is configured."),
            ("chat", "Chat (Slack / Teams)", False, "Disabled: no chat webhook is configured."),
        ]
        for kind, label, enabled, notes in channels:
            NotificationChannel.objects.get_or_create(
                tenant=tenant, kind=kind,
                defaults={"label": label, "is_enabled": enabled, "notes": notes},
            )
        email_channel = NotificationChannel.objects.filter(tenant=tenant, kind="email").first()
        inapp_channel = NotificationChannel.objects.filter(tenant=tenant, kind="in_app").first()

        templates = [
            ("invoice_overdue", "Invoice overdue", "email",
             "Invoice {{ reference }} is overdue",
             "Hello {{ recipient_name }},\n\nInvoice {{ reference }} for {{ amount }} is now overdue."
             "\n\nRegards,\n{{ tenant_name }}", "en", "accounting"),
            ("invoice_overdue_fr", "Facture en retard", "email",
             "La facture {{ reference }} est en retard",
             "Bonjour {{ recipient_name }},\n\nLa facture {{ reference }} de {{ amount }} est en "
             "retard.\n\nCordialement,\n{{ tenant_name }}", "fr", "accounting"),
            ("approval_waiting", "Approval waiting", "in_app", "",
             "An approval is waiting for you: {{ reference }}.", "en", ""),
        ]
        for code, name, kind, subject, body, locale, module_slug in templates:
            NotificationTemplate.objects.get_or_create(
                tenant=tenant, code=code, locale=locale,
                defaults={"name": name, "channel_kind": kind, "subject": subject, "body": body,
                          "module_slug": module_slug},
            )
        overdue_tmpl = NotificationTemplate.objects.filter(
            tenant=tenant, code="invoice_overdue", locale="en").first()
        waiting_tmpl = NotificationTemplate.objects.filter(
            tenant=tenant, code="approval_waiting", locale="en").first()

        rules = [
            ("Overdue invoice email", "invoice.overdue", "accounting", email_channel,
             overdue_tmpl, "party", "immediate", 10),
            ("Approval waiting in-app", "approval.waiting", "", inapp_channel,
             waiting_tmpl, "role", "immediate", 20),
            ("Approval digest", "approval.waiting", "", email_channel,
             None, "role", "daily", 30),
        ]
        admin_role = Role.objects.filter(tenant=tenant, name="Administrator").first()
        for name, event, module_slug, channel, template, audience, digest, priority in rules:
            if channel is None:
                continue
            NotificationRule.objects.get_or_create(
                tenant=tenant, name=name,
                defaults={"event": event, "module_slug": module_slug, "channel": channel,
                          "template": template, "audience_kind": audience,
                          "audience_role": admin_role if audience == "role" else None,
                          "digest": digest, "priority": priority,
                          "notes": "Seeded demo rule. It routes; nothing dispatches."},
            )

        providers = [
            ("email", "Primary SMTP", 10, "smtp.example.com", 587, "no-reply@example.com", "",
             "SMTP_PASSWORD"),
            ("email", "Failover SMTP", 20, "smtp-backup.example.com", 587,
             "no-reply@example.com", "", "SMTP_FAILOVER_PASSWORD"),
            ("sms", "SMS gateway", 10, "", None, "", "https://sms.example.com/send", "SMS_API_KEY"),
        ]
        for kind, label, priority, host, port, from_address, api, env_var in providers:
            ProviderConfig.objects.get_or_create(
                tenant=tenant, channel_kind=kind, label=label,
                    defaults={"priority": priority, "host": host, "port": port,
                              "from_address": from_address, "api_endpoint": api,
                              "credential_env_var": env_var,
                              "notes": "Seeded demo provider. No credential is stored, only its "
                                       "environment variable name."},
            )

    def _seed_integrations(self, tenant):
        """0.13: API credentials, rate limits, the connector catalogue, mappings and sync schedules.

        Three deliberate omissions, each the honest state to show:

        * **The API credential's plaintext is discarded here.** `ApiCredential.issue()` returns it and
          the seeder drops it on the floor — that is the whole point of the one-way design, and a
          seeder that printed a working key would defeat it. The seeded key is therefore unusable,
          which is the correct state for a demo credential.
        * **Connector `engine_label`s point at the REAL per-module models** (`scm.IntegrationEndpoint`,
          `accounting.IntegrationConfig`, `inventory.IntegrationChannel`,
          `projects.ProjectIntegrationConnector`) so the catalogue is followable rather than
          decorative. `is_installed` mirrors whether that model actually has rows.
        * **No integration TRAFFIC rows are seeded** — those belong to the modules that own the
          webhooks, and their own seeders create them.
        """
        from apps.core.integration import integration_health

        # A credential whose plaintext is thrown away on purpose.
        if not ApiCredential.objects.filter(tenant=tenant, label="Primary API key").exists():
            ApiCredential.issue(
                tenant, "Primary API key", kind="api_key",
                scopes="projects.read crm.read inventory.read",
            )
        primary = ApiCredential.objects.filter(tenant=tenant, label="Primary API key").first()

        if primary and not RateLimitPolicy.objects.filter(tenant=tenant,
                                                          name="Default API limit").exists():
            RateLimitPolicy.objects.create(
                tenant=tenant, credential=primary, name="Default API limit",
                max_requests=1000, window="hour",
                notes="Seeded demo limit. Nothing enforces it — there is no gateway process.",
            )
        if not RateLimitPolicy.objects.filter(tenant=tenant, name="Workspace-wide limit").exists():
            RateLimitPolicy.objects.create(
                tenant=tenant, name="Workspace-wide limit", max_requests=10000, window="day",
                notes="Seeded demo limit applying to every credential.",
            )

        # The catalogue indexes the REAL per-module connector models.
        health = integration_health(tenant)
        installed_labels = {c["label"] for c in health["connections"] if c["total"] > 0}
        connectors = [
            ("SCM integration endpoint", "NavERP", "logistics", "scm.IntegrationEndpoint",
             "Trading-partner EDI endpoints (850/856/810)."),
            ("Accounting integration", "NavERP", "accounting", "accounting.IntegrationConfig",
             "Ledger and payment-gateway connections."),
            ("Inventory channel", "Boomi", "logistics", "inventory.IntegrationChannel",
             "Warehouse and 3PL stock-sync channels."),
            ("Project integration connector", "NavERP", "other",
             "projects.ProjectIntegrationConnector",
             "Per-project third-party connectors with field mappings."),
        ]
        for name, vendor, category, engine, description in connectors:
            ConnectorDefinition.objects.get_or_create(
                tenant=tenant, name=name,
                defaults={"vendor": vendor, "category": category, "engine_label": engine,
                          "description": description,
                          "is_installed": engine in installed_labels,
                          "notes": "Seeded catalogue entry. Installed mirrors whether the engine "
                                   "model actually has rows."},
            )

        mappings = [
            ("X12 850 to purchase order", "inbound", "X12 850", "scm.PurchaseOrder",
             [{"from": "PO1.01", "to": "number"},
              {"from": "PO1.02", "to": "quantity", "transform": "int"},
              {"from": "N1.02", "to": "supplier_name"}]),
            ("Stock level to Boomi", "outbound", "JSON", "inventory.Item",
             [{"from": "sku", "to": "item_code"},
              {"from": "on_hand", "to": "quantity_available", "transform": "int"}]),
        ]
        for name, direction, source_format, target, rows in mappings:
            MappingTemplate.objects.get_or_create(
                tenant=tenant, name=name,
                defaults={"direction": direction, "source_format": source_format,
                          "target_label": target, "mappings": rows,
                          "notes": "Seeded demo mapping. Nothing applies it — a module reads it."},
            )

        schedules = [
            ("Nightly stock sync", "inbound", "api", "daily", "inventory.Item",
             "Stock level to Boomi", "Inventory channel"),
            ("Hourly order export", "outbound", "sftp", "hourly", "scm.PurchaseOrder",
             None, "SCM integration endpoint"),
            ("Manual EDI import", "inbound", "edi", "manual", "scm.PurchaseOrder",
             "X12 850 to purchase order", "SCM integration endpoint"),
        ]
        for name, direction, transport, frequency, entity, tmpl_name, conn_name in schedules:
            template = MappingTemplate.objects.filter(tenant=tenant, name=tmpl_name).first() if tmpl_name else None
            connector = ConnectorDefinition.objects.filter(tenant=tenant, name=conn_name).first() if conn_name else None
            SyncSchedule.objects.get_or_create(
                tenant=tenant, name=name,
                defaults={"direction": direction, "transport": transport, "frequency": frequency,
                          "entity_label": entity, "mapping_template": template,
                          "connector": connector,
                          "notes": "Seeded demo schedule. Nothing runs it — the repo has no "
                                   "scheduler."},
            )

    # ---------------------------------------------------------------- 0.15 Localization
    def _seed_localization_globals(self):
        """0.15: the two GLOBAL registries — languages and IANA time zones.

        Called ONCE, outside the tenant loop, because neither model has a `tenant` FK. Guarded by
        `get_or_create` on the natural key so a re-run adds only what is missing.

        Two of the eight languages are RTL, and the ten zones span both DST postures — not for
        variety's sake, but because `is_rtl` and `observes_dst` are the two flags the whole sub-module
        exists to expose, and a registry that contained only one posture of either would leave the
        board and the list filters untestable against real data.
        """
        languages = [
            ("en", "English", "English", False, True),
            ("fr", "French", "Français", False, False),
            ("de", "German", "Deutsch", False, False),
            ("es", "Spanish", "Español", False, False),
            ("pt", "Portuguese", "Português", False, False),
            ("zh-hans", "Chinese (Simplified)", "简体中文", False, False),
            ("ar", "Arabic", "العربية", True, False),
            ("he", "Hebrew", "עברית", True, False),
        ]
        created = 0
        for code, name, native, rtl, is_default in languages:
            _, made = Language.objects.get_or_create(
                code=code,
                defaults={"name": name, "native_name": native, "is_rtl": rtl,
                          "is_default": is_default, "is_active": True},
            )
            created += int(made)
        if created:
            self.stdout.write(f"  localization: seeded {created} language(s)")

        zones = [
            ("UTC", "UTC", 0, False),
            ("Europe/London", "London (GMT/BST)", 0, True),
            ("Europe/Berlin", "Berlin (CET/CEST)", 60, True),
            ("Europe/Lisbon", "Lisbon (WET/WEST)", 0, True),
            ("America/New_York", "New York (EST/EDT)", -300, True),
            ("America/Chicago", "Chicago (CST/CDT)", -360, True),
            ("America/Los_Angeles", "Los Angeles (PST/PDT)", -480, True),
            ("Asia/Dubai", "Dubai (GST)", 240, False),
            ("Asia/Kolkata", "Kolkata (IST)", 330, False),
            ("Asia/Tokyo", "Tokyo (JST)", 540, False),
        ]
        created = 0
        for name, label, offset, dst in zones:
            _, made = TimeZone.objects.get_or_create(
                name=name,
                defaults={"label": label, "utc_offset_minutes": offset, "observes_dst": dst,
                          "is_active": True},
            )
            created += int(made)
        if created:
            self.stdout.write(f"  localization: seeded {created} time zone(s)")

    def _seed_localization(self, tenant):
        """0.15: the per-tenant half — the locale profile and the statutory register.

        PER-ENTITY guards, never a tenant-wide one. A tenant-wide guard is the documented defect that
        left every entity added to this command after the fact unreachable in the workspaces that
        already existed — so each entity below checks for itself.

        `Currency` and `TaxCode` are read through `django_apps.get_model` rather than imported: they
        belong to `accounting`, and this command seeds `core` only. Reading a peer's rows to build a
        coherent FK is fine; seeding them here would be the cross-app defect the audit's check 6 hunts.

        **The guard alone is not enough for those two FKs.** On a fresh install this command runs
        BEFORE `seed_accounting` — which is their only creator and itself refuses to run without
        tenants — so the create below freezes `base_currency`/`tax_code` at NULL, and a bare
        `if not exists()` would skip the existing rows forever. Hence the `else` branches backfill a
        NULL link on re-run, once accounting data exists.
        """
        profile = LocaleProfile.objects.filter(tenant=tenant).first()
        if profile is None:
            Currency = django_apps.get_model("accounting", "Currency")
            LocaleProfile.objects.create(
                tenant=tenant,
                language=Language.objects.filter(code="en").first(),
                base_currency=Currency.objects.filter(code="USD").first(),
                time_zone=TimeZone.objects.filter(name="UTC").first(),
                date_format="dd/MM/yyyy",
                time_format="HH:mm",
                number_format="#,##0.00",
                address_format="{line1}\n{line2}\n{city}, {region} {postal}\n{country}",
                first_day_of_week=1,
                notes="Seeded default profile. Formats are patterns, not an enum — edit them here.",
            )
            self.stdout.write(f"  {tenant.name}: seeded the locale profile")
        elif profile.base_currency_id is None:
            # Re-run after `seed_accounting`: repair the NULL the fresh-install ordering froze.
            Currency = django_apps.get_model("accounting", "Currency")
            base_currency = Currency.objects.filter(code="USD").first()
            if base_currency is not None:
                profile.base_currency = base_currency
                profile.save(update_fields=["base_currency", "updated_at"])
                self.stdout.write(f"  {tenant.name}: linked the locale profile's base currency")

        if not StatutoryRule.objects.filter(tenant=tenant).exists():
            TaxCode = django_apps.get_model("accounting", "TaxCode")
            # Matched by TYPE, not by `.first()`. Picking an arbitrary code attached the EU
            # e-invoicing rule to a California sales-tax code — a rule pointing at a rate that has
            # nothing to do with it. The FK is only meaningful if it names the right rate.
            vat_code = TaxCode.objects.filter(tenant=tenant, tax_type="vat").first()
            sales_code = TaxCode.objects.filter(tenant=tenant, tax_type="sales").first()
            today = timezone.localdate()
            rules = [
                ("EU VAT e-invoicing", "European Union", vat_code, True, "peppol", "EC Sales List"),
                ("US sales tax filing", "United States", sales_code, False, "none",
                 "Sales Tax Return"),
                ("India GST e-invoice", "India", None, True, "gst_irn", "GSTR-1"),
            ]
            for name, jurisdiction, tax_code, e_inv, scheme, report in rules:
                StatutoryRule.objects.create(
                    tenant=tenant, name=name, jurisdiction=jurisdiction, tax_code=tax_code,
                    e_invoicing_required=e_inv, e_invoicing_scheme=scheme,
                    statutory_report=report, effective_from=today, is_active=True,
                    notes="Seeded statutory rule. Nothing transmits an invoice — this records the "
                          "obligation.",
                )
            self.stdout.write(f"  {tenant.name}: seeded {len(rules)} statutory rule(s)")
        elif StatutoryRule.objects.filter(
                tenant=tenant, name__in=["EU VAT e-invoicing", "US sales tax filing"],
                tax_code__isnull=True).exists():
            # Re-run after `seed_accounting`: repair the NULL tax codes the same ordering froze.
            TaxCode = django_apps.get_model("accounting", "TaxCode")
            codes = {
                "EU VAT e-invoicing": TaxCode.objects.filter(tenant=tenant, tax_type="vat").first(),
                "US sales tax filing": TaxCode.objects.filter(tenant=tenant, tax_type="sales").first(),
            }
            linked = 0
            for name, code in codes.items():
                if code is not None:
                    linked += StatutoryRule.objects.filter(
                        tenant=tenant, name=name, tax_code__isnull=True).update(tax_code=code)
            if linked:
                self.stdout.write(f"  {tenant.name}: linked {linked} statutory rule tax code(s)")

    def _seed_backup(self, tenant):
        """0.16: the backup, recovery and data-lifecycle registers.

        PER-ENTITY guards, never a tenant-wide one — the documented defect that left every entity added
        to this command after the fact unreachable in workspaces that already existed.

        **The rows are chosen to exercise the states a naive seed would omit.** One `BackupJob` is
        seeded as `warning` (partial) with `partial_scope_skipped`, and one successful backup is left
        with a NULL `integrity_verified_at`. A seed where every backup is green would hide the two
        conditions the board exists to surface: a partial backup people would trust, and a backup
        nobody has ever checked. A fourth job is seeded `queued` with a NULL `started_at` (M11), so the
        in-flight state is present too. `EncryptionKey` belongs to `tenants`, so it is read from there and
        never created here — and because `seed_core` runs *before* `seed_tenants` it is absent on a fresh
        seed, which is why `encryption_key` is backfilled at the end of this method rather than only set
        at insert time (M2).
        """
        EncryptionKey = django_apps.get_model("tenants", "EncryptionKey")
        key = EncryptionKey.objects.filter(tenant=tenant).first()
        now = timezone.now()

        # ---- BackupJob: three rows covering success+verified, partial, and failed ----
        if not BackupJob.objects.filter(tenant=tenant).exists():
            jobs = [
                dict(name="Nightly full backup", scope_label="nav_erp schema", backup_type="full",
                     frequency="daily", retention_days=30, target_location="s3://acme-backups/nav_erp",
                     storage_tier="standard", encryption_scheme="aes256", size_bytes=1_845_000_000,
                     checksum="sha256:9f2c…", integrity_method="restore_test",
                     integrity_verified_at=now, status="success", failure_reason="n_a",
                     started_at=now - datetime.timedelta(hours=8),
                     finished_at=now - datetime.timedelta(hours=8) + datetime.timedelta(minutes=24),
                     evidence="OPS-1041"),
                dict(name="Hourly transaction log", scope_label="nav_erp binlog", backup_type="log",
                     frequency="hourly", retention_days=7, target_location="s3://acme-backups/binlog",
                     storage_tier="infrequent", encryption_scheme="aes256", size_bytes=48_000_000,
                     checksum="", integrity_method="checksum", integrity_verified_at=None,
                     status="warning", failure_reason="partial_scope_skipped",
                     started_at=now - datetime.timedelta(hours=1),
                     finished_at=now - datetime.timedelta(hours=1) + datetime.timedelta(minutes=2),
                     evidence="OPS-1042",
                     notes="Two tables were locked and skipped. Partial — do not treat as a full "
                           "recovery point."),
                dict(name="Weekly offsite copy", scope_label="nav_erp + documents", backup_type="full",
                     frequency="weekly", retention_days=90, target_location="glacier://acme-offsite",
                     storage_tier="deep_archive", encryption_scheme="managed", size_bytes=None,
                     checksum="", integrity_method="none", integrity_verified_at=None,
                     status="failed", failure_reason="insufficient_space",
                     started_at=now - datetime.timedelta(days=2),
                     finished_at=now - datetime.timedelta(days=2) + datetime.timedelta(minutes=6),
                     evidence="OPS-1039",
                     notes="Target quota reached. Nothing was written."),
            ]
            for row in jobs:
                BackupJob.objects.create(tenant=tenant, encryption_key=key, is_immutable=False,
                                         performed_by=None, **row)
            self.stdout.write(f"  {tenant.name}: seeded {len(jobs)} backup job(s)")

        # ---- BackupJob: a queued row, with its OWN guard (M11) ----
        # `Meta.ordering` is `["-started_at", "-id"]` and MariaDB sorts a NULL `started_at` LAST under
        # `DESC`, so a just-queued backup sank below every finished one and was sliced off the board's
        # ten-row window -- that is C5. All three rows above carry a `started_at`, which is exactly why a
        # green sweep never caught it. This row has `started_at=None`, so the in-flight state is actually
        # present in the demo data; and it gets its OWN guard rather than riding on the tenant-wide one,
        # so it also reaches workspaces that were seeded before this fix.
        if not BackupJob.objects.filter(tenant=tenant, name="Queued nightly full backup").exists():
            BackupJob.objects.create(
                tenant=tenant, encryption_key=key, is_immutable=False, performed_by=None,
                name="Queued nightly full backup", scope_label="nav_erp schema", backup_type="full",
                frequency="daily", retention_days=30, target_location="s3://acme-backups/nav_erp",
                storage_tier="standard", encryption_scheme="aes256", size_bytes=None,
                checksum="", integrity_method="none", integrity_verified_at=None,
                status="queued", failure_reason="n_a", started_at=None, finished_at=None,
                evidence="",
                notes="Seeded as queued with no start time: this row records an intention to back up, "
                      "not a backup. Nothing has been written yet.",
            )
            self.stdout.write(f"  {tenant.name}: seeded 1 queued backup job")

        # ---- RecoveryPosture: the singleton (get_or_create, one row per tenant) ----
        _, posture_created = RecoveryPosture.objects.get_or_create(
            tenant=tenant,
            defaults=dict(rpo_target_minutes=60, rto_target_minutes=240,
                          replication_mode="async", primary_region="eu-west-1",
                          dr_region="eu-central-1", backup_retention_days=30,
                          dr_plan_reference="Confluence / OPS / DR-Plan-2026",
                          last_reviewed_at=timezone.localdate()),
        )
        if posture_created:
            self.stdout.write(f"  {tenant.name}: seeded the recovery posture")

        # ---- RecoveryDrill: one run with measured actuals, one not yet run ----
        if not RecoveryDrill.objects.filter(tenant=tenant).exists():
            drills = [
                dict(name="Q3 isolated failover test", kind="test_failover",
                     scheduled_for=timezone.localdate() - datetime.timedelta(days=20),
                     performed_at=now - datetime.timedelta(days=20), outcome="passed",
                     measured_rpo_minutes=45, measured_rto_minutes=195,
                     participants="Ops, DBA, Finance",
                     findings="Failover completed inside the RTO. The application booted without "
                              "manual intervention.",
                     follow_up_actions="Automate the DNS cutover; it was done by hand.",
                     evidence="OPS-1050"),
                dict(name="Q4 unplanned failover drill", kind="unplanned_failover",
                     scheduled_for=timezone.localdate() + datetime.timedelta(days=40),
                     performed_at=None, outcome="not_run",
                     measured_rpo_minutes=None, measured_rto_minutes=None,
                     participants="Ops, DBA", findings="", follow_up_actions="", evidence="OPS-1061"),
            ]
            for row in drills:
                RecoveryDrill.objects.create(tenant=tenant, **row)
            self.stdout.write(f"  {tenant.name}: seeded {len(drills)} recovery drill(s)")

        # ---- DataArchive: linked back to 0.8's retention policy where one exists ----
        if not DataArchive.objects.filter(tenant=tenant).exists():
            policy = RetentionPolicy.objects.filter(tenant=tenant, is_active=True).first()
            archived_at = now - datetime.timedelta(days=400)
            DataArchive.objects.create(
                tenant=tenant, name="2024 activity archive", policy=policy, disposal=None,
                model_label="core.Activity",
                content_description="Activities closed before 2025, exported to Parquet.",
                location="glacier://acme-archive/2024/activity.parquet", storage_tier="glacier",
                format="parquet", record_count=182_450, size_bytes=640_000_000,
                encryption_key=key, checksum="sha256:41ab…", immutable=True,
                archived_at=archived_at, restored_at=None,
                expires_at=archived_at + datetime.timedelta(days=365 * 7), status="active",
                notes="Seeded catalogue entry. `location` is what makes this restorable.",
            )
            DataArchive.objects.create(
                tenant=tenant, name="Legacy CRM export (media lost)", policy=None, disposal=None,
                model_label="", content_description="Offline tape from the old CRM.",
                location="", storage_tier="tape", format="native", record_count=None,
                size_bytes=None, encryption_key=None, checksum="", immutable=False,
                archived_at=archived_at - datetime.timedelta(days=200), restored_at=None,
                expires_at=None, status="lost",
                notes="Seeded deliberately WITHOUT a location: unrestorable, so the board's "
                      "unrestorable count has something to say.",
            )
            self.stdout.write(f"  {tenant.name}: seeded 2 data archive entry(ies)")

        # ---- LegalHold: one active hold, so a suspended scope is visible ----
        if not LegalHold.objects.filter(tenant=tenant).exists():
            policy = RetentionPolicy.objects.filter(tenant=tenant, is_active=True).first()
            LegalHold.objects.create(
                tenant=tenant, name="Hold — Acme v. Initech", custodian="Finance team",
                subject_party=None, matter_reference="CASE-2026-0042",
                issuing_authority="Superior Court", retention_policy=policy,
                model_label=policy.model_label if policy else "",
                scope="All financial records, correspondence and activity logs for this workspace "
                      "during 2024–2026.",
                issued_at=now - datetime.timedelta(days=30), status="active", released_at=None,
                release_reason="", authority_reference="PRESERVATION ORDER 2026/114",
                notes="Seeded active hold. It SUSPENDS any retention window covering the same scope — "
                      "the schedule does not run while this is in force.",
            )
            self.stdout.write(f"  {tenant.name}: seeded 1 legal hold")

        # ---- EnvironmentInstance: production + a sandbox refreshed from it ----
        if not EnvironmentInstance.objects.filter(tenant=tenant).exists():
            production = EnvironmentInstance.objects.create(
                tenant=tenant, name="Production", kind="production", tier="",
                source_environment=None, copy_scope="full", subset_rule="",
                copy_includes_pii=True, masking_required=False, status="active",
                refreshed_at=None, refresh_source=None, refresh_interval_days=None,
                expires_at=None, storage_limit_mb=None, is_active=True,
                notes="Seeded source environment. Nothing here provisions it.",
            )
            EnvironmentInstance.objects.create(
                tenant=tenant, name="Sandbox — UAT", kind="sandbox", tier="partial copy",
                source_environment=production, copy_scope="summary",
                subset_rule="Last 12 months of orders and parties; users excluded.",
                copy_includes_pii=True, masking_required=True, status="active",
                refreshed_at=now - datetime.timedelta(days=14), refresh_source=production,
                refresh_interval_days=29,
                expires_at=now + datetime.timedelta(days=15), storage_limit_mb=5120, is_active=True,
                notes="Seeded sandbox. `masking_required` records the obligation; NavERP does not "
                      "mask anything.",
            )
            self.stdout.write(f"  {tenant.name}: seeded 2 environment(s)")

        # ---- RestoreRecord: a completed per-tenant restore with a reason ----
        if not RestoreRecord.objects.filter(tenant=tenant).exists():
            source = BackupJob.objects.filter(tenant=tenant, status="success").first()
            target = EnvironmentInstance.objects.filter(tenant=tenant, kind="sandbox").first()
            RestoreRecord.objects.create(
                tenant=tenant, backup=source, archive=None, scope="per_tenant",
                target_time=(source.started_at if source and source.started_at else None),
                target_environment=target, status="succeeded", requested_by=None,
                reason="Recover rows a user deleted by mistake during a bulk import.",
                started_at=now - datetime.timedelta(days=6),
                finished_at=now - datetime.timedelta(days=6) + datetime.timedelta(minutes=52),
                outcome="Rows restored into production, verified against the source count.",
                is_verified=True, evidence="OPS-1055",
            )
            self.stdout.write(f"  {tenant.name}: seeded 1 restore record")

        # ---- M2: backfill `encryption_key` once `seed_tenants` has created one ----
        # `seed_core` runs BEFORE `seed_tenants` (`seed_core -> seed_accounts -> seed_tenants`), so on a
        # fresh seed no `EncryptionKey` exists yet and `key` above is None: every seeded backup, plus the
        # located archive, is written with `encryption_key=NULL`. The per-entity guards above then never
        # re-run, so the NULL would stick forever even after the key appears. Backfill here, on a later
        # run, matched by the names this seeder itself creates — a user-added row is never touched, and
        # the deliberately keyless "Legacy CRM export (media lost)" is not in either list.
        if key is not None:
            stale_jobs = BackupJob.objects.filter(
                tenant=tenant, encryption_key__isnull=True,
                name__in=["Nightly full backup", "Hourly transaction log", "Weekly offsite copy",
                          "Queued nightly full backup"]).update(encryption_key=key)
            stale_archives = DataArchive.objects.filter(
                tenant=tenant, encryption_key__isnull=True,
                name="2024 activity archive").update(encryption_key=key)
            if stale_jobs or stale_archives:
                self.stdout.write(
                    f"  {tenant.name}: backfilled encryption_key on {stale_jobs} backup job(s) "
                    f"and {stale_archives} archive(s)")

    def _seed_monitoring(self, tenant):
        """0.17: the service catalogue and the declared alert thresholds.

        **SEEDED:** `ServiceComponent` and `AlertRule`, and only those two. A catalogue is a
        declaration ("this workspace has a web front end, a database and a payments gateway") and a
        threshold is a recorded intention - both are true statements about what somebody chose to watch,
        and seeding either fabricates no event. This is the same basis 0.13 seeds `SyncSchedule` and 0.16
        seeds `BackupJob.frequency` on.

        **NOT SEEDED - the L52 ruling, and the load-bearing one:** `AlertEvent` and `Incident`. A firing
        is EVIDENCE that a threshold was crossed; seeding one fabricates an alert that never happened and
        its `fired_at` / `observed_value` / `evidence` would be a lie told in the register's own voice. An
        incident records a communication somebody published; seeding one invents an outage NavERP was
        never told about. Both are exempt in `temp/audit_integrity.py`'s `KNOWN_OK` with that reason
        printed, because an unexplained exemption is indistinguishable from an oversight.

        **The consequence is intended and must NOT be "fixed":** a fresh seed leaves this workspace with
        zero events and zero incidents, so the firing board renders its "no firings have been recorded"
        state and a naive smoke run reads as contract drift. It is not drift. It is the board telling the
        truth about a system that watches nothing. The smoke script creates the rows it needs via the ORM
        and deletes them in a `finally`.

        **`ServiceComponent.current_status` IS seeded, and that is the one tension here.** It resolves
        cleanly: seeding the CLAIM is fine because every seeded row says in its own `notes` that it is a
        starting position and not a measurement. A claim honestly labelled is honest; what would be
        dishonest is seeding a FIRING, which asserts that something actually happened.

        PER-ENTITY guards, never a tenant-wide one - the documented defect that left everything added to
        this command after the fact unreachable in workspaces that already existed.
        """
        now = timezone.now()
        # Defensive `.first()` lookup: `_seed_notifications` has already run, but a future reordering
        # must not crash the seeder over a nullable FK.
        notify_rule = NotificationRule.objects.filter(tenant=tenant).first()

        # ---- ServiceComponent: operational, degraded+critical, and never-reported ----
        if not ServiceComponent.objects.filter(tenant=tenant).exists():
            components = [
                dict(name="Web front end", code="web", kind="web_service", display_order=1,
                     current_status="operational", is_public=True, is_critical=True,
                     last_status_at=now - datetime.timedelta(hours=6),
                     description="The customer-facing browser application.",
                     notes="Seeded starting position. This status is a hand-set claim, not a "
                           "measurement - nothing in NavERP probes this component."),
                dict(name="Primary database", code="db", kind="database", display_order=2,
                     current_status="degraded", is_public=False, is_critical=True,
                     last_status_at=now - datetime.timedelta(days=2),
                     description="The transactional store backing every module.",
                     notes="Seeded starting position, deliberately DEGRADED and critical so the "
                           "health board's roll-up has something to roll up from. Hand-set claim, not "
                           "a measurement - nothing in NavERP probes this component."),
                dict(name="Payments gateway", code="payments", kind="external_dependency",
                     display_order=3, current_status="unknown", is_public=False, is_critical=False,
                     last_status_at=None,
                     description="An external provider NavERP calls but does not control.",
                     notes="Seeded with NO status ever set, so the board's unreported case is present "
                           "in real data. Unknown is a true answer; Operational would be a claim "
                           "somebody else would have to vouch for."),
            ]
            for row in components:
                ServiceComponent.objects.create(tenant=tenant, owner_role=None, **row)
            self.stdout.write(f"  {tenant.name}: seeded 3 service component(s)")


        # ---- AlertRule: two-tier performance, one-tier availability, inactive capacity ----
        if not AlertRule.objects.filter(tenant=tenant).exists():
            web = ServiceComponent.objects.filter(tenant=tenant, code="web").first()
            db = ServiceComponent.objects.filter(tenant=tenant, code="db").first()
            gateway = ServiceComponent.objects.filter(tenant=tenant, code="payments").first()
            rules = [
                dict(name="Payments API latency budget", service=db, module_slug="core",
                     metric_key="latency_p95_ms", comparator="gte",
                     warning_threshold=Decimal("800.0000"), critical_threshold=Decimal("1500.0000"),
                     must_persist_seconds=300, frequency="hourly", severity="warning",
                     category="performance", no_data_action="ignore", notification_rule=notify_rule,
                     notes="Seeded two-tier threshold. Nothing in NavERP evaluates this rule and no "
                           "reading of latency_p95_ms is stored anywhere in this repository."),
                dict(name="Gateway availability floor", service=gateway, module_slug="core",
                     metric_key="uptime_pct", comparator="lt",
                     warning_threshold=None, critical_threshold=Decimal("99.5000"),
                     must_persist_seconds=0, frequency="daily", severity="critical",
                     category="availability", no_data_action="fire", notification_rule=notify_rule,
                     notes="Seeded ONE-TIER rule (critical only) - a single bound is a normal shape, "
                           "not a half-finished one. 'no data' fires rather than passing silently."),
                dict(name="Database storage headroom", service=web, module_slug="tenants",
                     metric_key="storage_mb", comparator="gte",
                     warning_threshold=Decimal("51200.0000"), critical_threshold=None,
                     must_persist_seconds=0, frequency="weekly", severity="warning",
                     category="capacity", no_data_action="ignore", notification_rule=None,
                     is_active=False,
                     notes="Seeded INACTIVE so the ?active= filter and the capacity board's inactive "
                           "row are both provable. A threshold an operator parked is still a "
                           "declaration, not a firing."),
            ]
            for row in rules:
                AlertRule.objects.create(tenant=tenant, **row)
            self.stdout.write(f"  {tenant.name}: seeded 3 alert rule(s)")
        # No line is printed for AlertEvent or Incident. The ABSENCE of them is deliberate, and a count
        # of zero here would read as an all-clear on exactly the board that must never show one.

