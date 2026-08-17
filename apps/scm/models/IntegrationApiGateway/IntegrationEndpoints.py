"""SCM 4.19 Integration & API Gateway — ``IntegrationEndpoint``, the connection register [CNX-].

One row per registered connection to one outside system: which system, which way the data flows, how
the bytes would move, which environment it points at, how far its onboarding has got, and — as a
marker only — whether a credential has been registered for it. It is the ROOT of the sub-module:
``IntegrationMessage.endpoint`` CASCADEs off it, and the four category-scoped sidebar bullets ("ERP
Integration", "E-commerce Integration", "IoT Gateway", "EDI Management") are four routes onto this
one table discriminated by :attr:`category` — the same compression ``accounting.IntegrationConfig``
made.

--------------------------------------------------------------------------------------------------
CONSTRAINT A — THE 4.17 OWNERSHIP BOUNDARY, AND IT IS NON-NEGOTIABLE
--------------------------------------------------------------------------------------------------
4.17's ``LogisticsClient`` already ships ``integration_mode`` / ``client_system`` /
``edi_partner_id`` / ``edi_qualifier`` / ``last_synced_at``
(``ThirdPartyLogistics/LogisticsClients.py:172-186``). **4.19 adds no column to that model, takes no
route beneath ``logistics-clients/``, and re-declares none of those five names.** Where an endpoint
names a 3PL client, its interchange identifiers are READ THROUGH the FK
(:attr:`effective_interchange_id` / :attr:`effective_interchange_qualifier`) and this row's own
``interchange_id`` / ``interchange_qualifier`` must stay blank — enforced in :meth:`clean`, keyed on
fields the form has, with a message naming the client record as the place to edit them. Two columns
holding the same ISA sender id is two places for it to be wrong, and the copy that goes stale is the
one nobody looks at.

``LogisticsClient.last_synced_at`` is the column 4.17 created FOR this sub-module to write. **Nothing
in this pass writes it** — there is no transport, so there is no sync to timestamp. It is named here
so a later transport pass knows the home already exists rather than adding a second one.

--------------------------------------------------------------------------------------------------
THE CREDENTIAL STORE IS A MARKER, AND THE OBVIOUS RATIONALE FOR IT IS WRONG
--------------------------------------------------------------------------------------------------
:attr:`credential_prefix` + :attr:`credential_hash` store a 12-char prefix and a SHA-256 digest, both
``editable=False`` so they are structurally off every ModelForm (L20/L22) and :func:`set_credential`
is the only writer.

**Hashing is NOT the general way to store an integration credential.** Signing an outbound payload
needs the plaintext key, and authenticating to SAP or Shopify needs the real credential; SHA-256 is
one-way, so hashing makes both mathematically impossible. The general fix for a key you must USE is
ENCRYPTION AT REST — a KMS/Fernet envelope with the key material outside the row.

Prefix+hash is correct **here and only here** because 4.19 ships **no transport**: nothing signs and
nothing calls a provider, so the stored value is a CONFIGURATION MARKER ("a credential is
registered") that keeps the whole identification affordance — last-4 display, is-one-set, rotation
detection — with none of a credential store's liability. Identical call to
``accounting.IntegrationConfig`` (``apps/accounting/models/Integration/IntegrationConfigs.py:36-53``)
and ``tenants.EncryptionKey`` (``apps/tenants/models/EncryptionKey.py:22-31``).

**MIGRATION HAZARD, stated now so the next pass does not rediscover it as a wall.** The first pass
that implements real transport WILL be unable to sign or authenticate from a hash. The correct move
at that point is to migrate these columns to encrypted-at-rest reversible storage. **It is NOT to
revert the column to plaintext.** And do not "harmonize" ``crm.Webhook.secret``
(a plaintext ``CharField(128)`` at ``apps/crm/models/AutomationWorkflow/Webhooks.py:21``) by hashing
it: CRM 1.10 genuinely intends to sign, so ITS correct fix is encryption at rest — and it is 1.10's
to make, not 4.19's.

--------------------------------------------------------------------------------------------------
SSRF POSTURE — NO OUTBOUND HTTP EXISTS IN THIS SUB-MODULE
--------------------------------------------------------------------------------------------------
:attr:`endpoint_url` is a tenant-editable URL the server WOULD fetch. There is no ``requests`` /
``urllib`` / ``httpx`` / ``http.client`` import anywhere under ``apps/scm/**`` for 4.19 and there must
not be one added casually: any future transport pass must FIRST add an allow-list AND a private-IP
block (RFC1918, loopback, link-local 169.254.0.0/16, IPv6 ULA) and re-resolve against DNS rebinding.
Until then the column is configuration a human reads, not an address anything dials.

--------------------------------------------------------------------------------------------------
Note on layout, so no review agent "fixes" it
--------------------------------------------------------------------------------------------------
The backend package is ``IntegrationApiGateway/`` (PascalCase of the NavERP.md title) while the
templates live in ``templates/scm/integration/`` (the short slug every shipped scm template folder
uses). The asymmetry is the house rule, not a defect — the identical note sits at
``ThirdPartyLogistics/LogisticsClients.py:35-38`` and ``CustomerPortal/PortalAccounts.py:45-47``.
"""
import hashlib

from apps.scm.models._base import *  # noqa: F401,F403
# BY NAME, never `import *` — `apps/scm/models/__init__.py` already star-imports several `_choices`
# modules, so a further star-import could silently shadow a shared token with the winner decided by
# import order. `IntegrationApiGateway/_choices.py` imports NOTHING (not even `_base`), so the
# dependency edge inside 4.19 only ever runs one way and no cycle is possible.
#
# THIS ENTITY OWNS THAT FILE. IntegrationMessages / WebhookSubscriptions / WebhookDeliveries import
# from it by name exactly like the line below and must never create or edit it.
#
# `hashlib` is imported here rather than added to `_base`: `_base` star-exports `secrets` but NOT
# `hashlib`, and editing a shared file from an entity agent is exactly what L43 forbids while another
# session may be building in the same checkout.
from apps.scm.models.IntegrationApiGateway._choices import (
    AUTH_METHOD_CHOICES,
    ENDPOINT_CATEGORY_CHOICES,
    ENDPOINT_DIRECTION_CHOICES,
    ENDPOINT_STATUS_CHOICES,
    ENDPOINT_SYSTEM_CHOICES,
    ENVIRONMENT_CHOICES,
    LIFECYCLE_STAGE_CHOICES,
    TRANSPORT_CHOICES,
    TRIGGER_MODE_CHOICES,
)


class IntegrationEndpoint(TenantNumbered):
    """One registered connection to one outside system [CNX-]. See the module docstring first."""

    NUMBER_PREFIX = "CNX"

    #: Every FK on this model whose target is tenant-scoped, read by BOTH boundaries: the form's
    #: ``_reject_foreign`` (which renders a field error) and this model's own :meth:`clean` (which
    #: holds for the seeder and the shell). One table, two readers — two copies of an authorisation
    #: rule is two places for it to be wrong.
    TENANT_SCOPED_FKS = ("partner_party", "logistics_client", "location", "spec_document")

    # --- identity -------------------------------------------------------------------------------
    name = models.CharField(max_length=120)

    #: The DISCRIMINATOR behind the four category-scoped sidebar bullets. See `_choices.py`.
    category = models.CharField(
        max_length=12, choices=ENDPOINT_CATEGORY_CHOICES, default="custom")

    system = models.CharField(
        max_length=20, choices=ENDPOINT_SYSTEM_CHOICES, blank=True, default="",
        help_text="The platform on the other end. Leave blank while it is undecided")

    direction = models.CharField(
        max_length=14, choices=ENDPOINT_DIRECTION_CHOICES, default="bidirectional")

    transport = models.CharField(max_length=12, choices=TRANSPORT_CHOICES, default="api_rest")

    auth_method = models.CharField(max_length=10, choices=AUTH_METHOD_CHOICES, default="none")

    # WARNING: SSRF — this is a TENANT-EDITABLE URL THE SERVER WOULD FETCH. Outbound HTTP is
    # DEFERRED in this pass (there is no requests/urllib/httpx/http.client import under apps/scm for
    # 4.19), so nothing dials it today. Any future transport pass must FIRST add an allow-list AND a
    # private-IP block (RFC1918, loopback, link-local 169.254.0.0/16, IPv6 ULA) and re-resolve to
    # defeat DNS rebinding.
    #
    # DELIBERATELY A CharField, NOT A URLField — do not "fix" this. Django's URLValidator accepts
    # only http/https/ftp/ftps, so it would REJECT the legitimate sftp:// as2:// mqtt:// llrp://
    # endpoints this table exists to hold — and it would reject them only at ModelForm validation,
    # which means the seeder passes and the UI fails, the worst possible place to find out.
    # (`WebhookSubscription.target_url` IS a URLField, because a webhook target really is HTTP(S).)
    endpoint_url = models.CharField(
        max_length=500, blank=True,
        help_text="Host, path or queue this connection uses. Non-HTTP schemes (sftp://, as2://, "
                  "mqtt://, llrp://) are accepted — nothing in this build connects to it")

    external_account_ref = models.CharField(
        max_length=120, blank=True,
        help_text="Their identifier for our account — shop domain, seller id, marketplace region")

    # --- EDI interchange identity (see constraint A in the module docstring) ---------------------
    # MUST stay blank when `logistics_client` is set: 4.17 already owns that client's
    # edi_partner_id / edi_qualifier, and two columns holding one ISA sender id is two places for it
    # to be wrong. Enforced in clean(), read through effective_interchange_id/_qualifier.
    interchange_id = models.CharField(
        max_length=32, blank=True,
        help_text="ISA sender/receiver id. Leave blank when a 3PL client is named above — theirs is "
                  "held on the client record and is read through it")
    interchange_qualifier = models.CharField(
        max_length=8, blank=True, help_text="Qualifier for the id above, e.g. ZZ or 01")

    device_identifier = models.CharField(
        max_length=64, blank=True,
        help_text="Reader / gateway / scanner registry identity, for an IoT endpoint")

    # --- scheduling INTENT (nothing runs — see the module docstring) -----------------------------
    trigger_mode = models.CharField(
        max_length=10, choices=TRIGGER_MODE_CHOICES, default="manual",
        help_text="Records intent only. There is NO scheduler in this build — nothing polls and "
                  "nothing fires on a clock")
    schedule_note = models.CharField(
        max_length=200, blank=True,
        help_text="Free text, e.g. 'every 15 minutes, business hours'. Documentation, not a cron")

    # --- lifecycle ---------------------------------------------------------------------------------
    environment = models.CharField(max_length=10, choices=ENVIRONMENT_CHOICES, default="sandbox")
    lifecycle_stage = models.CharField(
        max_length=10, choices=LIFECYCLE_STAGE_CHOICES, default="setup",
        help_text="How far onboarding has got — a different question from whether it is up now")

    # ON the form deliberately: with no transport there is nothing that could observe a connection
    # succeed or fail, so this is a human-maintained marker rather than workflow-owned state. There
    # is no state machine to own it. `consecutive_failures` below is the opposite case.
    status = models.CharField(
        max_length=14, choices=ENDPOINT_STATUS_CHOICES, default="disconnected")

    is_active = models.BooleanField(default=True)

    # --- system-maintained state (all editable=False -> structurally off every form, L22) ---------
    # Recorded, never enforced: nothing decrements it and nothing auto-disables on it, because
    # nothing delivers. Same posture as 4.17's `next_billing_date`.
    consecutive_failures = models.PositiveIntegerField(default=0, editable=False)
    last_run_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_success_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_seen_at = models.DateTimeField(null=True, blank=True, editable=False)

    # THE CREDENTIAL MARKER. Read the module docstring before touching either column: this is a
    # prefix + SHA-256 digest, `set_credential` is the only writer, and the plaintext is shown to a
    # human exactly once on rotate and then discarded. There is no reveal view and there must not be
    # one. `editable=False` is what makes "no form ever carries this" structural rather than a
    # promise each form's field list has to keep (L20/L22).
    credential_prefix = models.CharField(max_length=12, blank=True, editable=False)
    credential_hash = models.CharField(max_length=64, blank=True, editable=False)

    notes = models.TextField(blank=True)

    # --- pointers — ALL four SET_NULL/nullable, target BY STRING ----------------------------------
    # SET_NULL rather than CASCADE or PROTECT throughout: a connection registration outliving the
    # party, client, bin or spec document it referenced is a stale pointer, not a reason to destroy
    # the exchange history hanging off it (IntegrationMessage.endpoint is the module's only CASCADE).
    partner_party = models.ForeignKey(
        "core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        help_text="The counterparty. Identity lives on the party record — customer/vendor/supplier "
                  "are PartyRoles there, and 4.19 adds no partner table of its own")
    logistics_client = models.ForeignKey(
        "scm.LogisticsClient", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        help_text="When this connection is a 3PL client's. Their EDI identifiers stay on THAT "
                  "record and are read through this link — do not retype them below")
    location = models.ForeignKey(
        "scm.Location", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        help_text="The zone or bin an IoT reader watches")
    spec_document = models.ForeignKey(
        "core.Document", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        help_text="The partner's API spec or EDI implementation guide, uploaded to the library")

    class Meta:
        # `name` is what the list is scanned by; `id` is the tie-break that makes it a TOTAL order,
        # so page 2 is deterministic rather than depending on row order.
        ordering = ["name", "id"]
        # NEVER a bare global unique=True — every constraint here starts with `tenant`, or one
        # workspace's connection name would block another's. ("tenant", "number") is the house
        # auto-number guarantee TenantNumbered's retry loop relies on; ("tenant", "name") is the rule
        # a user breaks by hand, and it also gives Meta.ordering's leading column an index for free,
        # which is why there is no separate (tenant, name) entry below.
        unique_together = (("tenant", "number"), ("tenant", "name"))
        indexes = [
            # The four category-scoped routes filter this pair on every page load.
            models.Index(fields=["tenant", "category"], name="scm_cnx_tnt_cat_idx"),
            # The list page's status filter and the header chips.
            models.Index(fields=["tenant", "status"], name="scm_cnx_tnt_status_idx"),
            # The `active` header chip and any future "only live connections" query.
            models.Index(fields=["tenant", "is_active"], name="scm_cnx_tnt_active_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name}"

    # ---------------------------------------------------------------------------------------------
    # The credential marker — read the module docstring before changing any of these four
    # ---------------------------------------------------------------------------------------------
    @staticmethod
    def hash_secret(secret):
        """SHA-256 hex digest of ``secret``. One-way by design — see the module docstring."""
        return hashlib.sha256(secret.encode()).hexdigest()

    def set_credential(self, plaintext):
        """Record that a credential exists, WITHOUT storing it.

        Keeps the first 8 characters so a human can recognise which credential is registered, plus
        the digest so a rotation is detectable. The plaintext is never written anywhere — not to this
        row, not to the audit log, not to a message body.
        """
        self.credential_prefix = plaintext[:8]
        self.credential_hash = self.hash_secret(plaintext)

    @staticmethod
    def generate_credential():
        """A fresh credential from the CSPRNG.

        ``secrets.token_urlsafe`` — never ``random`` (seeded, predictable) and never
        ``uuid4().hex`` (a uuid is an identifier, not a secret, and its entropy layout is public).
        ``secrets`` reaches this module through the ``_base`` star import.
        """
        return secrets.token_urlsafe(24)

    @property
    def masked(self):
        """``"prefix••••••••"``, or ``""`` when no credential has been registered.

        The templates render this (or the literal "Not set") and must never render
        ``credential_prefix`` or ``credential_hash`` directly — a digest on a page is a digest in a
        screenshot, and it is offline-attackable against a weak secret.
        """
        if not self.credential_hash:
            return ""
        return f"{self.credential_prefix}{'•' * 8}"

    # ---------------------------------------------------------------------------------------------
    # Derived — constraint A's read-through. Neither is a column (L29).
    # ---------------------------------------------------------------------------------------------
    @property
    def effective_interchange_id(self):
        """The ISA id in force: the 3PL client's when one is named, else this row's own.

        The whole point of constraint A: there is ONE place a given partner's interchange id lives,
        and every reader goes through here rather than picking a column and hoping.
        """
        if self.logistics_client_id:
            return getattr(self.logistics_client, "edi_partner_id", "") or ""
        return self.interchange_id

    @property
    def effective_interchange_qualifier(self):
        """The qualifier in force — the sibling of :attr:`effective_interchange_id`."""
        if self.logistics_client_id:
            return getattr(self.logistics_client, "edi_qualifier", "") or ""
        return self.interchange_qualifier

    # ---------------------------------------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------------------------------------
    def clean(self):
        """Two guards. Every error is keyed on a field the FORM has.

        A model error keyed on a column the form lacks raises ``ValueError`` out of ``add_error`` —
        a 500 instead of a field error (L39 §2). Both keys below (``interchange_id`` /
        ``interchange_qualifier``, and the four FK names) are on ``IntegrationEndpointForm``.

        Each FK read is defended twice: an ``_id is not None`` test (so an unsaved instance with an
        unset pointer does not raise) AND a defaulted ``getattr`` (``RelatedObjectDoesNotExist``
        subclasses ``AttributeError``, so a pointer whose row went away degrades to ``None`` here
        instead of 500-ing inside validation).
        """
        super().clean()
        errors = {}

        # (a) CONSTRAINT A. 4.17's LogisticsClient already owns this partner's interchange identity;
        #     a second copy here would be a second thing to keep true, and the stale one is always
        #     the one an envelope gets built from. Refused rather than silently ignored: a value the
        #     user typed and the system quietly drops is worse than an error, because they leave
        #     believing it applied.
        if self.logistics_client_id is not None:
            client_label = getattr(getattr(self, "logistics_client", None), "code", "")
            named = f" ({client_label})" if client_label else ""
            message = (
                f"This connection is linked to a 3PL client{named}, and that client record already "
                "holds its EDI interchange id and qualifier. Clear this field and edit them on the "
                "client instead — the connection reads them through the link, so they stay correct "
                "in one place.")
            if (self.interchange_id or "").strip():
                errors["interchange_id"] = message
            if (self.interchange_qualifier or "").strip():
                errors["interchange_qualifier"] = message

        # (b) Every tenant-scoped pointer, in ONE loop keyed off TENANT_SCOPED_FKS — so a fifth FK
        #     added later inherits the check by being added to that tuple rather than by somebody
        #     remembering to write another branch. This is the copy of the rule that holds for the
        #     seeder and the shell; the form repeats it at the form boundary.
        if self.tenant_id is not None:
            for name in self.TENANT_SCOPED_FKS:
                if getattr(self, f"{name}_id", None) is None:
                    continue
                related = getattr(self, name, None)
                if related is not None and getattr(related, "tenant_id", None) != self.tenant_id:
                    errors[name] = "That record belongs to another workspace."

        if errors:
            raise ValidationError(errors)
