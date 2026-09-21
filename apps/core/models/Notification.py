"""core — 0.12 Notification & Communication Management.

**0.12 owns the PLATFORM layer of a subsystem every module has already partly built.** An inventory
found per-module email templates (`crm.EmailTemplate`, `hrm.OfferLetterTemplate`), per-module webhook
subscriptions and delivery rows (`crm`, `scm`, `projects`), a per-module notification
(`projects.ProjectNotification`) and per-module delivery records (`inventory.NotificationDelivery`).
Each of those is the right home for ITS module's messages.

What nobody owns, and what this is:

1. **The channel registry** — `NotificationChannel`. Which channels exist and whether the workspace
   has them enabled. No module owns this because every module needs it.
2. **The platform template registry** — `NotificationTemplate`, with locale. The per-module templates
   are document templates for one business purpose; there is no shared, localisable one.
3. **The platform routing rules and user preferences** — `NotificationRule` +
   `NotificationPreference`. This is the piece that genuinely did not exist: an event-to-channel-to-
   audience mapping, and a member's own opt-out. Without it, "user preferences" is unimplementable
   because there is nothing to prefer against.
4. **Provider configuration with failover order** — `ProviderConfig`. Django's `EMAIL_BACKEND` is a
   process setting; there is no per-tenant provider config anywhere in the repo.
5. **Delivery tracking** — a COMPUTED board over the REAL delivery tables of other apps
   (`apps/core/notify.py`).

**What is NOT here, and is stated on the pages:** nothing sends anything. There is no outbound
worker, no retry loop and no scheduler, so a `NotificationRule` routes and a `ProviderConfig` records
where a message *would* go. `render_template()` renders; nothing dispatches. The board reports what
other modules actually sent.
"""
from apps.core.models._base import *  # noqa: F401,F403


class NotificationChannel(models.Model):
    """One delivery channel, and whether this workspace has it enabled."""

    KIND_CHOICES = [
        ("email", "Email"),
        ("sms", "SMS"),
        ("push", "Push"),
        ("in_app", "In-app"),
        ("chat", "Chat (Slack / Teams)"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="notification_channels", db_index=True)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    label = models.CharField(max_length=150, blank=True)
    is_enabled = models.BooleanField(
        default=False,
        help_text="Off by default: enabling a channel without a provider behind it sends nothing.")
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["kind"]
        unique_together = ("tenant", "kind")
        indexes = [models.Index(fields=["tenant", "is_enabled"], name="nchan_tenant_enabled_idx")]

    def __str__(self):
        return self.label or self.get_kind_display()


class NotificationTemplate(models.Model):
    """A reusable, localisable message template."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="notification_templates", db_index=True)
    code = models.SlugField(max_length=60, help_text="Stable identifier, e.g. 'invoice_overdue'.")
    name = models.CharField(max_length=200)
    channel_kind = models.CharField(max_length=10, choices=NotificationChannel.KIND_CHOICES,
                                    default="email")
    #: Only meaningful for email; SMS and push have no subject.
    subject = models.CharField(max_length=255, blank=True)
    #: Rendered with Django's template engine against a PLAIN DICT of primitives. See
    #: `apps/core/notify.py` for the restriction and why it is stated rather than assumed.
    body = models.TextField()
    locale = models.CharField(max_length=10, blank=True, default="en",
                              help_text="e.g. 'en', 'fr-CA'. Blank means the workspace default.")
    module_slug = models.CharField(max_length=40, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["module_slug", "code", "locale"]
        #: Locale is part of the key: one code may have an English and a French row.
        unique_together = ("tenant", "code", "locale")
        indexes = [models.Index(fields=["tenant", "code"], name="ntmpl_tenant_code_idx")]

    def __str__(self):
        return "%s (%s)" % (self.name, self.locale or "default")


class NotificationRule(models.Model):
    """Event -> channel -> audience. The routing table that did not exist anywhere."""

    AUDIENCE_CHOICES = [
        ("role", "Everyone holding a role"),
        ("user", "One named user"),
        ("party", "The related party (customer / vendor)"),
        ("all", "Everyone in the workspace"),
    ]
    DIGEST_CHOICES = [
        ("immediate", "Send immediately"),
        ("daily", "Daily digest"),
        ("weekly", "Weekly digest"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="notification_rules", db_index=True)
    name = models.CharField(max_length=200)
    event = models.CharField(max_length=120,
                             help_text="The event key, e.g. 'invoice.overdue'.")
    module_slug = models.CharField(max_length=40, blank=True)
    channel = models.ForeignKey("core.NotificationChannel", on_delete=models.CASCADE,
                                related_name="rules")
    template = models.ForeignKey("core.NotificationTemplate", on_delete=models.SET_NULL, null=True,
                                 blank=True, related_name="rules")
    audience_kind = models.CharField(max_length=10, choices=AUDIENCE_CHOICES, default="role")
    audience_role = models.ForeignKey("accounts.Role", on_delete=models.SET_NULL, null=True,
                                      blank=True, related_name="notification_rules")
    audience_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                      blank=True, related_name="notification_rules")
    digest = models.CharField(max_length=10, choices=DIGEST_CHOICES, default="immediate")
    #: Lower fires first when two rules target the same event and channel.
    priority = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["priority", "name"]
        unique_together = ("tenant", "name")
        indexes = [
            models.Index(fields=["tenant", "event", "is_active"], name="nrule_tenant_event_idx"),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()
        # A role-audience rule with no role targets nobody, and a user-audience rule with no user
        # likewise. Refused rather than saved as a rule that silently reaches no one.
        if self.audience_kind == "role" and self.audience_role_id is None:
            raise ValidationError({"audience_role": "Choose the role this rule notifies."})
        if self.audience_kind == "user" and self.audience_user_id is None:
            raise ValidationError({"audience_user": "Choose the user this rule notifies."})

    def __str__(self):
        return "%s -> %s" % (self.event, self.channel)


class NotificationPreference(models.Model):
    """One member's opt-out for one event on one channel. Absence means "take the default"."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="notification_preferences", db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="notification_preferences")
    event = models.CharField(max_length=120)
    channel_kind = models.CharField(max_length=10, choices=NotificationChannel.KIND_CHOICES)
    is_enabled = models.BooleanField(
        default=True, help_text="Uncheck to opt out of this event on this channel.")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__email", "event", "channel_kind"]
        unique_together = ("user", "event", "channel_kind")
        indexes = [models.Index(fields=["tenant", "user"], name="npref_tenant_user_idx")]

    def __str__(self):
        return "%s · %s · %s" % (self.user, self.event, self.channel_kind)


class ProviderConfig(models.Model):
    """Where a channel's messages WOULD go, and in what failover order."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="provider_configs", db_index=True)
    channel_kind = models.CharField(max_length=10, choices=NotificationChannel.KIND_CHOICES)
    label = models.CharField(max_length=150)
    #: Lower is tried first. A second row on the same channel is a failover target.
    priority = models.PositiveIntegerField(default=10)
    host = models.CharField(max_length=255, blank=True)
    port = models.PositiveIntegerField(null=True, blank=True)
    from_address = models.CharField(max_length=255, blank=True)
    api_endpoint = models.CharField(max_length=255, blank=True)
    #: The NAME of the environment variable holding the credential, never the credential. Storing a
    #: live secret here would put it in every backup and admin page; 0.7 owns secret storage.
    credential_env_var = models.CharField(
        max_length=120, blank=True,
        help_text="Name of the environment variable holding the secret. Never the secret itself.")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["channel_kind", "priority"]
        unique_together = ("tenant", "channel_kind", "label")
        indexes = [models.Index(fields=["tenant", "channel_kind"], name="nprov_tenant_kind_idx")]

    def __str__(self):
        return "%s · %s (p%s)" % (self.get_channel_kind_display(), self.label, self.priority)
