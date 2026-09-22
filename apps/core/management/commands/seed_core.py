"""Seed the core spine: demo tenants + parties, org units, employments, activities.

Idempotent — safe to re-run. Tenants are get_or_create'd by slug; per-tenant spine data
is skipped if any Party already exists for that tenant. Run order: seed_core →
seed_accounts → seed_tenants.
"""
import datetime

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
