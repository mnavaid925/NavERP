"""SCM 4.19 Integration & API Gateway — ``WebhookSubscription``, the outbound event rule [WHK-].

One row per *"when X happens in the supply chain, POST it to this URL"* standing instruction. It is
the target of the sub-module's **Webhooks** sidebar bullet and the parent of
:class:`~apps.scm.models.WebhookDelivery`, which records one row per attempt against it (CASCADE —
deleting the rule takes its attempt log with it, because an attempt log with no rule is telemetry
about nothing).

==================================================================================================
1. WHY THIS IS NOT ``crm.Webhook`` — a documented decision, not drift
==================================================================================================
CRM 1.10 already ships an outbound webhook pair (``apps/crm/models/AutomationWorkflow/Webhooks.py``).
It is not reusable here, and the reason is its **vocabulary**, not its plumbing:
``crm.Webhook.trigger_entity`` takes its choices from ``crm.WorkflowRule.ENTITY_CHOICES``, which is
exactly ``lead / opportunity / case / expense / contract / health_score``. There is no member of that
list that can express ``shipment.delivered``, ``goods_receipt.posted`` or
``quality_inspection.status_changed``, and widening a CRM automation vocabulary with ten supply-chain
nouns would make every CRM workflow rule offer triggers its own engine cannot fire.

So 4.19 keeps its own subscription table whose ``trigger_entity`` members are all **verified existing
scm classes**, and CRM keeps its own. Two tables, two vocabularies, neither pretending to be the
other. (This is the same call 4.16 made for ``PortalActivity`` vs ``core.AuditLog``.)

==================================================================================================
2. THE SIGNING SECRET IS A PREFIX + HASH — and the obvious rationale for that is WRONG
==================================================================================================
``signing_secret_prefix`` (12) + ``signing_secret_hash`` (64), both ``editable=False`` so their
absence from every ModelForm is STRUCTURAL rather than a field list somebody has to remember (L20 /
L22). :meth:`set_signing_secret` is the only writer, and it is reached from exactly one place —
``webhooksubscription_rotate_secret``.

**Hashing is NOT the general way to store an HMAC signing key.** Signing needs the plaintext key
bytes back and SHA-256 is one-way, so a hashed key makes signing mathematically impossible. For a key
you must USE, the correct storage is **reversible encryption at rest** with the key material held
outside the row — which this project already has, at ``apps/core/crypto.py`` (Fernet, keyed from
``SECRET_KEY``/``FIELD_ENCRYPTION_KEY``).

Prefix + hash is correct **here and only here** because *4.19 ships no transport*: nothing signs,
nothing calls a provider, and no code path anywhere in this sub-module reads a credential back. The
stored value is therefore a **configuration marker** — "a signing secret is registered for this
subscription" — which keeps the whole identification affordance (last-4 display via :attr:`masked`,
is-one-set, rotation detection) with none of a credential store's liability. It is the identical call
``accounting.IntegrationConfig`` made for its API key.

**MIGRATION HAZARD, stated here so the pass that hits it does not "fix" it the wrong way.** The first
pass that implements real outbound transport WILL hit a wall: it cannot compute an HMAC from a hash.
The correct move at that point is to migrate this column to reversible encrypted-at-rest storage
(``apps/core/crypto.py``'s ``encrypt``/``decrypt``, or a KMS envelope) — it is **NOT** to revert the
column to plaintext.

And do **not** "harmonize" ``crm.Webhook.secret`` against this model. CRM 1.10 genuinely intends to
sign, so its correct fix was encryption at rest, and CRM has **already made it**: that column now
holds Fernet ciphertext (``CharField(512)``, marked ``fernet.v1:``) and is read through
``Webhook.get_secret()``. It is the worked example of the migration named above, not a weakness to
copy or to hash. Either way it is CRM's column and 4.19 does not touch it.

==================================================================================================
3. NOTHING AUTO-DISABLES, BECAUSE NOTHING DELIVERS
==================================================================================================
``auto_disable_threshold`` and ``consecutive_failures`` record INTENT and STATE. There is no
scheduler, no daemon and no HTTP client in this pass, so nothing increments the counter, nothing
compares it against the threshold, and no subscription is ever switched off automatically. Same
posture as 4.17's ``last_synced_at``: the column exists so the transport pass writes into a home that
is already there instead of adding one late. ``filter_expression`` and ``include_fields`` are the
same — recorded, never evaluated.

``consecutive_failures`` is ``editable=False`` for the L29 reason as well as the L22 one: it is a
DERIVED counter, and a counter a human can type is a number that stops meaning anything.

==================================================================================================
4. LAYOUT NOTE — do not "fix" the asymmetry
==================================================================================================
The backend package is ``IntegrationApiGateway/`` (PascalCase of the NavERP.md sub-module title)
while the templates live under ``templates/scm/integration/`` (the short slug every shipped scm
template folder uses). That asymmetry is the house rule — the identical note sits at
``ThirdPartyLogistics/LogisticsClients.py:35-38`` and ``CustomerPortal/PortalAccounts.py:45-47``.
"""
from apps.scm.models._base import *  # noqa: F401,F403

# `_base` star-exports `secrets` (4.10's public_token needs it) but NOT `hashlib`, so the two hashing
# entity modules in this sub-module each import it themselves. Widening `_base.py` for two callers
# would be an edit to a shared single-writer file another session may be building against (L43).
import hashlib

# BY NAME, never `import *` — `apps/scm/models/__init__.py` already star-imports several `_choices`
# modules, so a further star-import could silently shadow a shared token with the winner decided by
# import order. `IntegrationApiGateway/_choices.py` imports NOTHING (not even `_base`), so the
# dependency edge inside 4.19 runs one way only and no cycle is possible.
#
# THAT FILE IS OWNED BY THE `IntegrationEndpoints` ENTITY MODULE. This module imports from it exactly
# as below and must never create or edit it.
from apps.scm.models.IntegrationApiGateway._choices import (
    PAYLOAD_FORMAT_CHOICES,
    WEBHOOK_ENTITY_CHOICES,
    WEBHOOK_EVENT_CHOICES,
)


class WebhookSubscription(TenantNumbered):
    """A standing "push this event to this URL" rule [WHK-]. Delivery itself is deferred."""

    NUMBER_PREFIX = "WHK"

    #: EMPTY ON PURPOSE, and its emptiness is a decision rather than an omission. Every other 4.19
    #: model lists the FKs both boundaries re-check (the form's ``_reject_foreign`` and the model's
    #: own ``clean()``); this one has **no foreign key at all beyond the inherited ``tenant``**,
    #: because a subscription is a rule about INTERNAL events and points at no partner, no party and
    #: no document. There is consequently no cross-tenant FK to reject, no ``clean()`` on this class,
    #: and no ``_reject_foreign`` call in its form. The constant stays declared so the absence reads
    #: as "checked, nothing to check" rather than "forgotten".
    TENANT_SCOPED_FKS = ()

    # --- what the rule is called -----------------------------------------------------------------
    name = models.CharField(
        max_length=120,
        help_text="What this subscription is for, e.g. 'Notify WMS when a shipment is delivered'")

    # --- when it fires ---------------------------------------------------------------------------
    # Every member of WEBHOOK_ENTITY_CHOICES is a VERIFIED existing scm class (grepped at build time),
    # which is the whole reason this table exists rather than reusing crm.Webhook — see docstring §1.
    trigger_entity = models.CharField(
        max_length=22, choices=WEBHOOK_ENTITY_CHOICES,
        help_text="Which supply-chain record type the event happens to")
    trigger_event = models.CharField(
        max_length=16, choices=WEBHOOK_EVENT_CHOICES, default="created",
        help_text="What happened to it")

    # --- where it goes ---------------------------------------------------------------------------
    # WARNING (SSRF): this is a TENANT-EDITABLE URL THE SERVER WOULD FETCH. Outbound HTTP is
    # DEFERRED in this pass — there is no `requests` / `urllib` / `httpx` / `http.client` import
    # anywhere under apps/scm for 4.19 — so today the column is inert configuration. Any future
    # transport pass MUST, before its first request:
    #   * enforce an allow-list of permitted hosts/schemes;
    #   * block private and special-use destinations — RFC1918 (10/8, 172.16/12, 192.168/16),
    #     loopback (127/8, ::1), link-local 169.254.0.0/16 (the cloud metadata endpoint) and IPv6
    #     unique-local (fc00::/7);
    #   * RE-RESOLVE the host at connect time and re-check the resolved address, because a DNS
    #     rebinding answer that passed validation can point at 169.254.169.254 by the time the
    #     socket opens; and
    #   * refuse redirects to anything the above would have refused.
    # URLField IS correct here, unlike `IntegrationEndpoint.endpoint_url`: a webhook target really is
    # HTTP(S), so URLValidator's http/https/ftp/ftps restriction excludes nothing legitimate.
    target_url = models.URLField(
        max_length=500, help_text="HTTPS endpoint the event payload would be POSTed to")

    payload_format = models.CharField(max_length=6, choices=PAYLOAD_FORMAT_CHOICES, default="json")

    # --- what it sends (recorded, never evaluated — see docstring §3) -----------------------------
    filter_expression = models.CharField(
        max_length=200, blank=True,
        help_text="RECORDED, NEVER EVALUATED in this pass — nothing delivers, so nothing filters.")
    include_fields = models.CharField(
        max_length=255, blank=True,
        help_text="Comma-separated field names. RECORDED, NEVER EVALUATED in this pass.")

    # Validated at the form boundary (`WebhookSubscriptionForm.clean_headers`) as a FLAT dict of
    # str -> str with no CR/LF in either half — the crm.WebhookForm precedent. A JSONField that
    # accepts arbitrary nested structure is a footgun handed to the future transport pass, and a
    # newline in a header value is request-splitting.
    headers = models.JSONField(
        default=dict, blank=True,
        help_text='Custom request headers as a JSON object, e.g. {"X-Source": "NavERP"}')

    is_active = models.BooleanField(default=True)

    # EDITABLE config, unlike the counter below it. 8 is Svix's published schedule (8 attempts spread
    # over roughly 32 hours), which is also what DELIVERY_BACKOFF_SECONDS models. Bounded 1..20 so a
    # typo cannot describe a retry policy nobody would run.
    auto_disable_threshold = models.PositiveSmallIntegerField(
        default=8, validators=[MinValueValidator(1), MaxValueValidator(20)],
        help_text="Consecutive failures after which this subscription SHOULD be switched off. "
                  "Recorded only — nothing enforces it in this pass, because nothing delivers")

    # DERIVED state, never typed (L29) and never on a form (L22 — editable=False makes that
    # structural). Nothing in this pass increments it; see docstring §3.
    consecutive_failures = models.PositiveIntegerField(default=0, editable=False)
    last_delivery_at = models.DateTimeField(null=True, blank=True, editable=False)

    # --- the signing secret: prefix + hash only. See docstring §2 before changing either column. ---
    signing_secret_prefix = models.CharField(max_length=12, blank=True, editable=False)
    signing_secret_hash = models.CharField(max_length=64, blank=True, editable=False)

    description = models.TextField(blank=True)

    class Meta:
        # A TOTAL order. `["name"]` alone is not one — two subscriptions may share nothing but a name
        # ordering can distinguish, and rows that tie are free to swap between page 1 and page 2 of
        # the same paginated read, so a row can be shown twice or not at all. `id` is the tiebreak.
        ordering = ["name", "id"]

        # Two pairs, NEVER a bare global `unique=True` (which would let one workspace's name block
        # another's). ("tenant", "number") is the guarantee TenantNumbered.save()'s retry loop relies
        # on; ("tenant", "name") is the business rule — two rules with the same name in one workspace
        # is an operator looking at a list and being unable to tell which one they are editing.
        unique_together = (("tenant", "number"), ("tenant", "name"))

        indexes = [
            # The list page's default view and its `?status=active` translation both filter this
            # pair, and so does the "how many rules are live?" header statistic.
            models.Index(fields=["tenant", "is_active"], name="scm_whk_tnt_active_idx"),
            # The `?trigger_entity=` filter, and the lookup the future transport pass makes on every
            # single event it considers publishing ("which rules care about a shipment?").
            models.Index(fields=["tenant", "trigger_entity"], name="scm_whk_tnt_entity_idx"),
        ]

    # ---------------------------------------------------------------------------------------------
    # Secret handling — the accounting.IntegrationConfig / tenants.EncryptionKey pattern, verbatim.
    # ---------------------------------------------------------------------------------------------
    @staticmethod
    def hash_secret(secret):
        """SHA-256 hex of ``secret``. One-way BY DESIGN — see the class docstring §2."""
        return hashlib.sha256(secret.encode()).hexdigest()

    def set_signing_secret(self, plaintext):
        """Store the prefix + hash of ``plaintext``. **The plaintext itself is never persisted.**

        The caller (``webhooksubscription_rotate_secret``) holds the plaintext only long enough to
        show it once, and then it is gone — there is no reveal view and no way to read it back.
        """
        self.signing_secret_prefix = plaintext[:8]
        self.signing_secret_hash = self.hash_secret(plaintext)

    @staticmethod
    def generate_secret():
        """A fresh signing secret from the CSPRNG.

        ``secrets.token_urlsafe``, never ``random`` (seeded, predictable, and documented as unfit for
        security) and never ``uuid4().hex`` (which advertises its own version/variant bits and is a
        128-bit identifier rather than a key).
        """
        return secrets.token_urlsafe(24)

    @property
    def masked(self):
        """``"abc12def••••••••"`` when a secret is registered, ``""`` when none is.

        The prefix is what makes a rotation checkable ("the value changed") and lets an operator tell
        two registered secrets apart. The hash is NEVER rendered — a digest is still the credential's
        fingerprint, and publishing it hands an offline attacker their verification oracle.
        """
        if not self.signing_secret_hash:
            return ""
        return f"{self.signing_secret_prefix}{'•' * 8}"

    def __str__(self):
        return f"{self.number} — {self.name}"
