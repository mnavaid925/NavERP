"""core — 0.13 Integration & API Management.

**What already exists, and what 0.13 therefore does NOT re-declare.** An inventory found per-module
integration machinery across five apps: `scm.IntegrationEndpoint` / `IntegrationMessage` /
`WebhookSubscription` / `WebhookDelivery` (a whole IntegrationApiGateway sub-module, 4.16),
`crm.Webhook` / `WebhookDelivery`, `projects.ProjectIntegrationConnector` /
`ProjectWebhookEndpoint` / `ProjectWebhookDelivery` / `ConnectorFieldMapping`,
`inventory.IntegrationChannel` and `accounting.IntegrationConfig`. Each owns its own endpoints,
subscriptions and delivery rows.

**What genuinely did not exist anywhere**, and is what this is:

1. **`ApiCredential`** — bullet 1's "API-key/OAuth issuance". There was no API key model in the repo
   at all. Stores a PREFIX and a SHA-256 HASH, never the plaintext, following the same one-way pattern
   `tenants.EncryptionKey` established: a credential only ever answers "is this the same key?", never
   "what was the key?", so a one-way hash is strictly safer than reversible encryption.
2. **`RateLimitPolicy`** — bullet 1's "rate limiting". Nothing recorded a limit anywhere.
3. **`ConnectorDefinition`** — bullet 3's marketplace. Only `projects.ProjectIntegrationConnector`
   existed, and that is one project's configured connector, not a catalogue.
4. **`MappingTemplate`** + **`SyncSchedule`** — bullet 4. `projects.ConnectorFieldMapping` is
   project-scoped; there was no platform mapping registry and no scheduled-sync registry.
5. **Integration monitoring** — bullet 5, a COMPUTED board over the real tables (`apps/core/integration.py`).

**Nothing here makes a request.** There is no gateway process, no outbound worker and no scheduler, so
a credential authenticates when asked, a policy records a limit, and a schedule records an intention.
`@api_credential_required` is a real, tested decorator — but it is applied by a view, and no API views
ship in this module.
"""
import hashlib
import secrets

from apps.core.models._base import *  # noqa: F401,F403


class ApiCredential(models.Model):
    """An issued API credential. The plaintext is shown ONCE and never stored."""

    KIND_CHOICES = [
        ("api_key", "API key"),
        ("oauth_client", "OAuth client"),
        ("service_account", "Service account token"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="api_credentials", db_index=True)
    label = models.CharField(max_length=150)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="api_key")
    #: Shown to the operator so a key can be identified in a log without revealing it. Never secret.
    prefix = models.CharField(max_length=16, editable=False)
    #: SHA-256 of the plaintext. A credential only ever answers "is this the same key?", so a one-way
    #: hash is strictly safer than reversible encryption — the same reasoning as EncryptionKey.
    key_hash = models.CharField(max_length=64, editable=False)
    #: Space-separated scope names, e.g. "projects.read crm.write". Free-form on purpose: the scopes a
    #: module exposes are the module's business, and a closed list here would have to be edited every
    #: time one adds a scope.
    scopes = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   blank=True, editable=False, related_name="issued_api_credentials")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="apicred_tenant_active_idx"),
            models.Index(fields=["key_hash"], name="apicred_hash_idx"),
        ]

    @staticmethod
    def generate_plaintext():
        """A fresh credential. `nvr_` makes it greppable in a log; the body is 32 bytes of entropy."""
        return "nvr_" + secrets.token_urlsafe(32)

    @staticmethod
    def hash_plaintext(plaintext):
        return hashlib.sha256((plaintext or "").encode()).hexdigest()

    @classmethod
    def issue(cls, tenant, label, **kwargs):
        """Create a credential and return `(instance, plaintext)`. The plaintext is NOT persisted."""
        plaintext = cls.generate_plaintext()
        credential = cls(
            tenant=tenant, label=label,
            prefix=plaintext[:12], key_hash=cls.hash_plaintext(plaintext), **kwargs
        )
        credential.save()
        return credential, plaintext

    def set_plaintext(self, plaintext):
        """Used by the seeder only. The plaintext is discarded immediately after this."""
        self.prefix = (plaintext or "")[:12]
        self.key_hash = self.hash_plaintext(plaintext)

    @property
    def is_expired(self):
        return self.expires_at is not None and self.expires_at <= timezone.now()

    @property
    def is_usable(self):
        return self.is_active and not self.is_expired

    def scope_list(self):
        return [s for s in (self.scopes or "").replace(",", " ").split() if s]

    def has_scope(self, scope):
        return scope in self.scope_list()

    def __str__(self):
        return "%s (%s…)" % (self.label, self.prefix)


class RateLimitPolicy(models.Model):
    """A recorded request limit. **Nothing enforces it** — there is no gateway process."""

    WINDOW_CHOICES = [
        ("minute", "Per minute"),
        ("hour", "Per hour"),
        ("day", "Per day"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="rate_limit_policies", db_index=True)
    name = models.CharField(max_length=150)
    #: Optional: scope the policy to one credential. Blank applies to the whole workspace.
    credential = models.ForeignKey("core.ApiCredential", on_delete=models.CASCADE, null=True,
                                   blank=True, related_name="rate_limits")
    max_requests = models.PositiveIntegerField(default=1000)
    window = models.CharField(max_length=10, choices=WINDOW_CHOICES, default="hour")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["tenant", "is_active"], name="ratelimit_tenant_active_idx")]

    def __str__(self):
        return "%s (%s/%s)" % (self.name, self.max_requests, self.window)


class ConnectorDefinition(models.Model):
    """Bullet 3's marketplace: what connectors exist, and whether this workspace has installed one."""

    CATEGORY_CHOICES = [
        ("erp", "ERP"),
        ("crm", "CRM"),
        ("accounting", "Accounting"),
        ("logistics", "Logistics"),
        ("payments", "Payments"),
        ("messaging", "Messaging"),
        ("storage", "Storage"),
        ("other", "Other"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="connector_definitions", db_index=True)
    name = models.CharField(max_length=150)
    vendor = models.CharField(max_length=150, blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="other")
    description = models.TextField(blank=True)
    #: The per-module model that actually holds this connector's configuration, as
    #: `app_label.Model`. A STRING, not a FK, so the catalogue can describe a connector whose model is
    #: registered later.
    engine_label = models.CharField(
        max_length=120, blank=True,
        help_text="The model holding this connector's config, e.g. projects.ProjectIntegrationConnector.")
    is_installed = models.BooleanField(
        default=False,
        help_text="Off until the connector is actually configured — a catalogue entry is not an install.")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["category", "name"]
        unique_together = ("tenant", "name")
        indexes = [models.Index(fields=["tenant", "category"], name="connector_tenant_cat_idx")]

    def __str__(self):
        return self.name


class MappingTemplate(models.Model):
    """A reusable field-mapping definition for an inbound or outbound exchange."""

    DIRECTION_CHOICES = [("inbound", "Inbound"), ("outbound", "Outbound")]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="mapping_templates", db_index=True)
    name = models.CharField(max_length=150)
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, default="inbound")
    source_format = models.CharField(max_length=40, blank=True,
                                     help_text="e.g. 'X12 850', 'CSV', 'JSON'.")
    target_label = models.CharField(max_length=120, blank=True,
                                    help_text="The entity this maps onto, e.g. 'scm.PurchaseOrder'.")
    #: A JSON list of {"from": ..., "to": ..., "transform": ...} rows. JSON rather than a child table:
    #: a mapping is one document an operator edits as a whole, and a table would make the editor a
    #: multi-page CRUD for no benefit.
    mappings = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["direction", "name"]
        unique_together = ("tenant", "name")
        indexes = [models.Index(fields=["tenant", "direction"], name="mapping_tenant_dir_idx")]

    @property
    def mapping_count(self):
        return len(self.mappings or [])

    def __str__(self):
        return self.name


class SyncSchedule(models.Model):
    """A recorded sync intention. **Nothing runs it** — the repo has no scheduler."""

    DIRECTION_CHOICES = [("inbound", "Inbound"), ("outbound", "Outbound")]
    FREQUENCY_CHOICES = [
        ("manual", "Manual only"),
        ("hourly", "Hourly"),
        ("daily", "Daily"),
        ("weekly", "Weekly"),
    ]
    TRANSPORT_CHOICES = [
        ("api", "REST API"),
        ("sftp", "SFTP"),
        ("file", "File drop"),
        ("edi", "EDI"),
        ("webhook", "Webhook"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="sync_schedules", db_index=True)
    name = models.CharField(max_length=150)
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, default="inbound")
    transport = models.CharField(max_length=10, choices=TRANSPORT_CHOICES, default="api")
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default="manual")
    entity_label = models.CharField(max_length=120, blank=True,
                                    help_text="What is exchanged, e.g. 'inventory.Item'.")
    mapping_template = models.ForeignKey("core.MappingTemplate", on_delete=models.SET_NULL, null=True,
                                         blank=True, related_name="schedules")
    connector = models.ForeignKey("core.ConnectorDefinition", on_delete=models.SET_NULL, null=True,
                                  blank=True, related_name="schedules")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "name")
        indexes = [models.Index(fields=["tenant", "frequency"], name="syncsched_tenant_freq_idx")]

    def __str__(self):
        return "%s (%s, %s)" % (self.name, self.get_transport_display(), self.get_frequency_display())
