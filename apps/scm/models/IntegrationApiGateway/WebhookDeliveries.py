"""SCM 4.19 Integration & API Gateway — ``WebhookDelivery``, one attempt against one subscription.

One row per *attempt* to push one event to one :class:`~apps.scm.models.WebhookSubscription`. The
subscription is the standing rule ("when a shipment is delivered, POST it here"); this table is the
evidence of what that rule actually did, attempt by attempt.

==================================================================================================
1. APPEND-ONLY — list and detail only, no create, no edit, no delete
==================================================================================================
This model is reached through exactly three routes (``webhook-deliveries/``,
``webhook-deliveries/<pk>/`` and the ``retry`` POST) and there is **no ModelForm for it anywhere**:
``apps/scm/forms/IntegrationApiGateway/WebhookDeliveries.py`` deliberately does not exist, and the
forms package ``__init__`` carries a comment saying so rather than an import. It is the
``scm.StockMove`` / ``scm.MeterReading`` / ``scm.PortalActivity`` / ``crm.WebhookDelivery`` posture,
and CRM states it in the same words — *"Immutable append-only delivery record … Accessed list+detail
only — never edited"* (``apps/crm/models/AutomationWorkflow/Webhooks.py:68-70``).

The reason is not tidiness. A delivery log answers the question a partner asks in a dispute: *did you
ever send it, how many times, and what came back?* An answer somebody can retype after the argument
starts is not an answer. The correction for a wrong row is therefore **a later row**, exactly as a
wrong stock movement is corrected by a compensating move and a wrong journal entry by a reversal —
which is also why ``attempt_no`` counts up rather than a single row being rewritten in place.

The one write this table exposes to the UI is :func:`~apps.scm.views.webhookdelivery_retry`, and it
touches only the row's own queue state (``status`` / ``attempt_no`` / ``next_attempt_at``). It edits
no recorded outcome: ``response_code``, ``error_message``, ``payload_excerpt``, ``signature`` and
``triggered_at`` are never rewritten by it.

==================================================================================================
2. NOTHING IN THIS PASS SENDS ANYTHING — and ``retry`` least of all
==================================================================================================
4.19 ships **no transport**. There is no ``requests``, ``urllib``, ``httpx`` or ``http.client``
import anywhere under ``apps/scm`` for this sub-module, and no scheduler, daemon or task queue. So:

* rows are created by the seeder, not by a sender;
* ``next_attempt_at`` is a STAMP, not a trigger — nothing wakes up and reads it;
* ``webhookdelivery_retry`` **performs no HTTP request**. It advances the row to the next slot in
  :data:`~apps.scm.models.IntegrationApiGateway._choices.DELIVERY_BACKOFF_SECONDS` and says so in
  its own message. The button is called *Retry* and it would be entirely reasonable to assume it
  re-sends, which is precisely why the view, the URL module and this docstring all say it does not.

``DELIVERY_STATUS_CHOICES`` carries a ``simulated`` member for the same honesty reason: a row that
never left the process is neither a success nor a failure, and recording it as ``success`` would make
this log evidence of something that did not happen.

==================================================================================================
3. WHY ``signature`` IS BLANK ON EVERY ROW THIS PASS CREATES — this is not a bug
==================================================================================================
``signature`` is the HMAC hex a real transport would compute over the payload and send in the
request header, so the receiver can prove the call came from us. **Every row created in this pass
leaves it blank, and it cannot be otherwise**, for two independent reasons:

* there is no plaintext signing key to sign WITH. ``WebhookSubscription`` stores its secret as
  ``signing_secret_prefix`` + ``signing_secret_hash`` — a configuration marker, deliberately
  one-way (see that model's docstring §2 for why that is correct *here* and why the fix at
  transport time is encryption at rest, **not** reverting the column to plaintext); and
* there is no payload to sign OVER, because nothing is serialised and nothing is sent.

The column exists now so the transport pass writes into a home that is already there instead of
adding one late — the same posture as 4.17's ``last_synced_at``. It is surfaced on the detail page as
an explicit *"Not computed — outbound transport is deferred"*, never as an empty cell that reads as a
bug.

==================================================================================================
4. WHY THERE IS NO ``number`` — this class extends ``TenantOwned``, not ``TenantNumbered``
==================================================================================================
Its three siblings in 4.19 are numbered (``CNX-`` / ``MSG-`` / ``WHK-``); this one is not, and the
line the app draws is consistent: **human-discussed records get a number, per-attempt telemetry does
not**. ``StockMove``, ``TemperatureReading``, ``PortalActivity`` and ``KpiSnapshot`` all sit on the
same side of it, as does ``crm.WebhookDelivery``. Nobody says *"chase WHD-04417"* about the fourth
retry of one event; they say *"the shipment.delivered pushes to the WMS are failing"*, which is the
subscription's number plus a filter. A per-attempt sequence would also be the single hottest
``next_number`` contention point in the module for a value nothing reads.

Consequently there is **no** ``unique_together`` here — there is no number to constrain, and no
natural key either: the same subscription genuinely does retry the same event, which is the whole
point of ``attempt_no``.

==================================================================================================
5. LAYOUT NOTE — do not "fix" the asymmetry
==================================================================================================
The backend package is ``IntegrationApiGateway/`` (PascalCase of the NavERP.md sub-module title)
while the templates live under ``templates/scm/integration/`` (the short slug every shipped scm
template folder uses). That asymmetry is the house rule — the identical note sits at
``ThirdPartyLogistics/LogisticsClients.py:35-38``.
"""
from apps.scm.models._base import *  # noqa: F401,F403

# BY NAME, never `import *` — `apps/scm/models/__init__.py` already star-imports several `_choices`
# modules, so a further star-import could silently shadow a shared token with the winner decided by
# import order. `IntegrationApiGateway/_choices.py` imports NOTHING (not even `_base`), so the
# dependency edge inside 4.19 runs one way only and no cycle is possible.
#
# THAT FILE IS OWNED AND CREATED BY THE `IntegrationEndpoints` ENTITY MODULE. This module only reads
# from it and must never create or edit it.
from apps.scm.models.IntegrationApiGateway._choices import (
    DELIVERY_BACKOFF_SECONDS,
    DELIVERY_STATUS_CHOICES,
)


class WebhookDelivery(TenantOwned):
    """One attempt to push one event to one :class:`WebhookSubscription`. Append-only."""

    #: Re-checked in :meth:`clean` against this row's own tenant. There is no ModelForm in front of
    #: this table (see docstring §1), so there is no narrowed ``<select>`` and no ``_reject_foreign``
    #: behind it — the guard below is the whole boundary, and the seeder and any future writer go
    #: straight through it.
    TENANT_SCOPED_FKS = ("subscription",)

    #: How many attempts the published backoff schedule describes (8 — Svix's, adopted verbatim).
    #: Read by the detail page so it can render *"attempt 3 of 8"*, and by :meth:`next_backoff_seconds`
    #: to decide when the schedule is spent. Derived from the tuple rather than typed, so widening
    #: the schedule cannot leave a stale ceiling behind it.
    MAX_ATTEMPTS = len(DELIVERY_BACKOFF_SECONDS)

    #: CASCADE, and it is the only sensible rule: an attempt log with no rule is telemetry about
    #: nothing. `related_name="deliveries"` is what the subscription detail page's panel reads.
    subscription = models.ForeignKey("scm.WebhookSubscription", on_delete=models.CASCADE,
                                     related_name="deliveries")

    #: The event name as the transport pass would publish it, e.g. ``shipment.delivered``.
    #: DENORMALISED on purpose rather than derived from the subscription's
    #: ``trigger_entity``/``trigger_event`` pair: editing the rule afterwards must not silently
    #: rewrite what an already-recorded attempt was an attempt AT.
    event = models.CharField(max_length=60, help_text='e.g. "shipment.delivered"')

    payload_excerpt = models.TextField(
        blank=True,
        help_text="TRUNCATED excerpt only. May contain partner PII. A full payload body is NEVER "
                  "stored.")

    signature = models.CharField(
        max_length=128, blank=True,
        help_text="The HMAC hex a real transport would compute. BLANK on every row this pass "
                  "creates: there is no plaintext signing key (only a prefix + hash marker) and no "
                  "transport, so nothing can compute one. The column is the home for the future "
                  "transport pass — this is not a bug.")

    status = models.CharField(max_length=10, choices=DELIVERY_STATUS_CHOICES, default="pending")

    #: 1-based, and it counts ATTEMPTS rather than indexing the schedule: attempt 1 is schedule slot
    #: 0 (immediate), which is why :meth:`next_backoff_seconds` indexes with ``attempt_no`` itself.
    attempt_no = models.PositiveSmallIntegerField(default=1)

    #: A STAMP, not a trigger. Nothing reads this on a clock — there is no scheduler in this pass
    #: (docstring §2). ``webhookdelivery_retry`` writes it so a human can see what pressing Retry
    #: would have queued, and so the transport pass has a column already in place.
    next_attempt_at = models.DateTimeField(null=True, blank=True)

    #: Nullable, not 0-defaulted: "the partner answered 000" and "we never got an answer" are
    #: different facts, and a log that cannot tell them apart is not much of a log.
    response_code = models.PositiveSmallIntegerField(null=True, blank=True)

    error_message = models.TextField(blank=True)

    #: ``editable=False`` makes "no form ever shows this" STRUCTURAL rather than a field list
    #: somebody has to remember (L22) — and it does NOT stop the seeder assigning it explicitly,
    #: which is how the demo data spreads attempts across a plausible window.
    triggered_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        # Newest first, and the `-id` tie-break is load-bearing rather than decorative: a burst of
        # attempts lands many rows on the identical `triggered_at`, and without a TOTAL order the
        # rows that tie are free to swap between page 1 and page 2 of the same paginated read — so a
        # row can be shown twice, or not at all (L9's sibling problem).
        ordering = ["-triggered_at", "-id"]

        # NO unique_together — see docstring §4. There is no `number` to constrain and no natural
        # key: the same subscription genuinely does retry the same event, which is what attempt_no
        # is for.

        indexes = [
            # The subscription detail page's "recent attempts" panel and the list's ?subscription=
            # filter — the two most frequent reads on the table.
            models.Index(fields=["tenant", "subscription"], name="scm_whd_tnt_sub_idx"),
            # The ?status= filter and the header chips on both the list and the subscription panel.
            models.Index(fields=["tenant", "status"], name="scm_whd_tnt_status_idx"),
            # `ordering` itself, plus the list page's date window. A RANGE on the column, which is
            # exactly why the view widens `?date_from=` into a datetime range rather than wrapping
            # the column in `__date` — a function of a column cannot use this index.
            models.Index(fields=["tenant", "triggered_at"], name="scm_whd_tnt_trigat_idx"),
        ]
        # INDEX NAMES ARE GLOBAL to the database, not scoped to the app or the table. The `scm_whd_`
        # prefix is what keeps these three distinct from crm's already-shipped `crm_whd_tnt_*` names
        # on its own WebhookDelivery (apps/crm/models/AutomationWorkflow/Webhooks.py:92-93).

    def __str__(self):
        return f"{self.event} #{self.attempt_no}"

    @property
    def next_backoff_seconds(self):
        """Seconds until the attempt a Retry would schedule, or ``None`` when the schedule is spent.

        Attempt N is schedule slot N-1, so the NEXT slot is index ``attempt_no`` — attempt 1 has
        already consumed slot 0 (immediate) and a retry from it is scheduled at slot 1 (5s).

        Lives on the model rather than in the view because two callers need the identical answer and
        a second copy is a second place for them to disagree: the detail page renders it (*"next
        attempt in N seconds"*, so the human knows what the button will do) and
        ``webhookdelivery_retry`` stamps ``next_attempt_at`` from it. Returning ``None`` — rather
        than raising or clamping to the last slot — is what tells the retry view to mark the row
        ``exhausted`` instead of scheduling an attempt the published schedule does not describe.

        The lower bound is checked as well as the upper one: ``attempt_no`` is a
        ``PositiveSmallIntegerField`` that a raw import could set to 0, and a negative index would
        silently read the LAST slot of the tuple (10 hours) rather than fail.
        """
        index = self.attempt_no
        if 0 <= index < len(DELIVERY_BACKOFF_SECONDS):
            return DELIVERY_BACKOFF_SECONDS[index]
        return None

    def clean(self):
        """The cross-tenant FK guard. This model has no form, so this is the whole boundary.

        Skipped while the instance has no tenant yet: an unsaved row has ``tenant_id`` ``None`` and
        ``self.tenant`` would raise ``RelatedObjectDoesNotExist`` on a non-nullable FK rather than
        return ``None``.
        """
        super().clean()
        if self.tenant_id is None:
            return
        for name in self.TENANT_SCOPED_FKS:
            if getattr(self, f"{name}_id", None) is None:
                continue
            # Defaulted getattr: RelatedObjectDoesNotExist subclasses AttributeError, so a pointer
            # whose row went away degrades to None here instead of 500-ing inside validation.
            related = getattr(self, name, None)
            if related is not None and related.tenant_id != self.tenant_id:
                raise ValidationError({name: "That record belongs to another workspace."})
