"""Projects 7.18 — ProjectIntegrationConnector model [IXC-].

The Integration & API Hub's connection register: one row per registered connection to one
outside system (ERP/finance, CRM, HR/talent, DevOps, file storage), discriminated by ``domain``.

--------------------------------------------------------------------------------------------------
L36/L31 OWNERSHIP RULING — FOUR INTEGRATION REGISTERS COEXIST DELIBERATELY, DO NOT "CONSOLIDATE"
--------------------------------------------------------------------------------------------------
* scm 4.19 ``IntegrationEndpoint`` [CNX-] — the supply-chain, TRANSPORT-LESS register (EDI/IoT/3PL).
* inventory 5.19 ``IntegrationChannel`` [INT-] — the commerce-stock register.
* accounting 2.15 ``IntegrationConfig`` — the finance-side register.
* **this** ``ProjectIntegrationConnector`` [IXC-] — the PROJECT connector register.
Four registers, four questions, deliberately not merged (research-projects-7.18.md §4.4, option b).
7.18 FKs none of them and re-declares none of their class names or columns. **7.18 performs no
outbound HTTP and writes no accounting row.**

Push vs sync: 7.17 Workflow & Automation owns event PUSH (``ProjectWebhookEndpoint`` [PWH-],
HMAC-SHA256, delivery log). 7.18 owns scheduled/triggered data SYNC (connector registry, field
mappings, sync jobs, run log). Where they touch, a connector references a 7.17 endpoint by FK
(``notify_webhook``) for "notify on sync failure" — it never re-declares one.
"""
from apps.core.crypto import decrypt, encrypt, is_encrypted
from apps.projects.models._base import *


class ProjectIntegrationConnector(TenantNumbered):
    """One registered connection to one outside system, scoped to a project (or the workspace)."""

    NUMBER_PREFIX = "IXC"

    DOMAIN_CHOICES = [
        ("erp", "ERP & Finance"),
        ("crm", "CRM"),
        ("hris", "HR & Talent"),
        ("devops", "DevOps"),
        ("storage", "File Storage"),
        ("custom", "Custom / Other"),
    ]
    PROVIDER_CHOICES = [
        ("sap", "SAP"),
        ("oracle", "Oracle"),
        ("netsuite", "NetSuite"),
        ("dynamics", "Microsoft Dynamics"),
        ("workday", "Workday"),
        ("salesforce", "Salesforce"),
        ("hubspot", "HubSpot"),
        ("dynamics_sales", "Dynamics Sales"),
        ("bamboohr", "BambooHR"),
        ("adp", "ADP"),
        ("jira", "Jira"),
        ("github", "GitHub"),
        ("gitlab", "GitLab"),
        ("azure_devops", "Azure DevOps"),
        ("ci_cd", "CI/CD Pipeline"),
        ("sharepoint", "SharePoint"),
        ("google_drive", "Google Drive"),
        ("dropbox", "Dropbox"),
        ("box", "Box"),
        ("custom", "Custom / Other"),
    ]
    DIRECTION_CHOICES = [
        ("inbound", "Inbound"),
        ("outbound", "Outbound"),
        ("bidirectional", "Bidirectional"),
    ]
    AUTH_METHOD_CHOICES = [
        ("none", "None"),
        ("api_key", "API Key"),
        ("basic", "Basic Auth"),
        ("oauth2", "OAuth 2.0"),
        ("pat", "Personal Access Token"),
    ]
    TRIGGER_MODE_CHOICES = [
        ("manual", "Manual"),
        ("scheduled", "Scheduled"),
        ("event", "Event-driven"),
    ]
    ENVIRONMENT_CHOICES = [
        ("production", "Production"),
        ("sandbox", "Sandbox"),
    ]
    STATUS_CHOICES = [
        ("unverified", "Unverified"),
        ("connected", "Connected"),
        ("error", "Error"),
        ("disabled", "Disabled"),
        ("disconnected", "Disconnected"),
    ]

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="integration_connectors",
        help_text="Null implies a workspace-wide connector",
    )
    name = models.CharField(max_length=120)
    domain = models.CharField(max_length=12, choices=DOMAIN_CHOICES, default="custom")
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, blank=True, default="custom")
    direction = models.CharField(max_length=14, choices=DIRECTION_CHOICES, default="bidirectional")
    auth_method = models.CharField(max_length=10, choices=AUTH_METHOD_CHOICES, default="api_key")
    # WARNING: SSRF — this is a configuration reference ONLY and is NEVER fetched by this app.
    # CharField, not URLField: git/ssh/on-prem hosts are not necessarily http(s).
    base_url = models.CharField(max_length=500, blank=True)
    remote_scope_ref = models.CharField(max_length=200, blank=True)
    trigger_mode = models.CharField(max_length=10, choices=TRIGGER_MODE_CHOICES, default="manual")
    schedule_note = models.CharField(max_length=200, blank=True)
    environment = models.CharField(max_length=10, choices=ENVIRONMENT_CHOICES, default="sandbox")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="unverified")
    is_active = models.BooleanField(default=True)
    credential = models.CharField(
        max_length=512,
        blank=True,
        editable=False,
        help_text="Fernet ciphertext via apps.core.crypto; write-only via the form, never rendered.",
    )
    last_sync_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_success_at = models.DateTimeField(null=True, blank=True, editable=False)
    consecutive_failures = models.PositiveIntegerField(default=0, editable=False)
    notify_webhook = models.ForeignKey(
        "projects.ProjectWebhookEndpoint",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notify_connectors",
        help_text="7.17 endpoint pinged on sync failure (7.17 owns delivery).",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_project_connectors",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = [("tenant", "number"), ("tenant", "project", "name")]
        indexes = [
            models.Index(fields=["tenant", "domain"], name="ixc_tnt_domain_idx"),
            models.Index(fields=["tenant", "status"], name="ixc_tnt_status_idx"),
            models.Index(fields=["tenant", "project"], name="ixc_tnt_prj_idx"),
            models.Index(fields=["tenant", "is_active"], name="ixc_tnt_active_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name} ({self.get_provider_display()})"

    def clean(self):
        super().clean()
        if self.project_id and self.project.tenant_id != self.tenant_id:
            raise ValidationError({"project": "Project belongs to another workspace."})
        if self.notify_webhook_id and self.notify_webhook.tenant_id != self.tenant_id:
            raise ValidationError({"notify_webhook": "Webhook belongs to another workspace."})
        # unique_together cannot bind NULL projects, so workspace-wide names need a manual guard.
        if self.project_id is None and self.name:
            siblings = ProjectIntegrationConnector.objects.filter(
                tenant_id=self.tenant_id, project__isnull=True, name=self.name
            )
            if self.pk:
                siblings = siblings.exclude(pk=self.pk)
            if siblings.exists():
                raise ValidationError({"name": "A workspace-wide connector with this name already exists."})

    # -- credential (Fernet, reversible — it must be presentable to the provider) ----------------

    def set_credential(self, raw_secret):
        """Encrypt and store the provider credential (blank clears)."""
        self.credential = encrypt(raw_secret) if raw_secret else ""

    def get_credential(self):
        """Return the plaintext credential, or '' if unset. Raises if the key rotated."""
        return decrypt(self.credential) if self.credential else ""

    @property
    def credential_set(self):
        return bool(self.credential)

    @property
    def credential_masked(self):
        """A display-safe hint; degrades, never raises."""
        if not self.credential:
            return "(none)"
        if not is_encrypted(self.credential):
            return "(set — legacy plaintext)"
        try:
            plain = self.get_credential()
        except Exception:
            return "(set — undecryptable with the current key)"
        return f"••••{plain[-4:]}" if len(plain) >= 4 else "••••"

    def save(self, *args, **kwargs):
        # Single choke point: idempotent on an already-marked value (encrypt() no-ops on it).
        if self.credential:
            self.credential = encrypt(self.credential)
        return super().save(*args, **kwargs)

    # -- display ---------------------------------------------------------------------------------

    @property
    def status_badge(self):
        return {
            "connected": "badge-green",
            "error": "badge-red",
            "unverified": "badge-slate",
            "disabled": "badge-muted",
            "disconnected": "badge-amber",
        }.get(self.status, "badge-slate")

    @property
    def domain_badge(self):
        return "badge-slate" if self.domain == "custom" else "badge-info"

    @property
    def health_badge(self):
        if not self.last_sync_at:
            return "badge-slate"
        if self.consecutive_failures:
            return "badge-red" if self.consecutive_failures >= 3 else "badge-amber"
        return "badge-green"

