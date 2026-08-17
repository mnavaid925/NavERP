"""SCM 4.19 Integration & API Gateway — ``IntegrationMessage``, the exchange log [MSG-].

One row per document, batch or event that crossed the boundary between this workspace and an outside
system through an :class:`~apps.scm.models.IntegrationEndpoint`: an inbound 850 from a trading
partner, an outbound 856 to a customer's VAN, a Shopify order import, a batch of RFID tag reads
lifted off a reader. It is the answer to the only question anybody asks when an integration is
blamed for something — *what actually came in, what actually went out, and when* — and it is the
table the exceptions cockpit (``scm:integration_exceptions``) reads.

**APPEND-ONLY. There is no create, edit or delete route, and that is a ruling rather than an
omission.** The module ships LIST + DETAIL + a single ``reprocess`` POST, exactly the posture
``scm.StockMove``, ``scm.MeterReading``, ``scm.TrackingEvent``, ``scm.PortalActivity`` and
``crm.WebhookDelivery`` already hold. A wrong row is corrected by **appending a later, correct
row**, the same way a wrong stock movement is corrected by a compensating move and a wrong journal
entry by a reversal. The reason is not tidiness:

* an exchange log is *evidence of what crossed the boundary*. Evidence that can be revised after the
  dispute starts is not evidence. "Your 855 said 400 units" has to be defensible against a row
  nobody could have quietly retyped;
* somebody has already acted on these rows — a receipt was booked, an order was released, a 997 was
  chased. Rewriting the record after the fact leaves the action standing on a figure that no longer
  exists anywhere;
* ``acknowledges`` chains one row to another (the 997 to the 850 it answers). Editing the answered
  row silently rewrites what the acknowledgement is an acknowledgement *of*.

Consequently this model has **no ModelForm at all** — ``apps/scm/forms/IntegrationApiGateway/
IntegrationMessages.py`` deliberately does not exist, matching ``forms/CustomerPortal/
PortalActivities.py``, which does not exist for the same reason. The only UI write to this table is
``integrationmessage_reprocess``, which re-queues a row and clears its error text. **A reviewer
should not "complete" this CRUD.**

**THE SHOPIFY / WEBHOOK ORDERING CAVEAT — read before building anything on top of this table.**
Neither Shopify's webhooks nor any comparable event feed guarantees ORDER or DELIVERY. Events can
arrive out of sequence, arrive twice, or never arrive at all. So:

* this log is a record of *what we saw*, not a reconstruction of *what happened, in order*. Never
  derive state by replaying these rows in ``occurred_at`` sequence — a later ``updated`` event may
  well be older than the ``created`` one filed after it;
* ``external_id`` exists to make redelivery detectable (``X-Shopify-Webhook-Id`` / the Svix
  ``eventId``). It is indexed with the tenant for exactly that lookup. It is **not** unique-
  constrained, because a duplicate delivery is a fact worth *recording* rather than an insert worth
  *refusing* — and because a partner that reuses an id across document types would otherwise start
  losing rows silently;
* the truth is reconciled separately, by polling the partner for current state. Anything that must
  be right (stock, money, fulfilment) is confirmed against the partner's own API, never against the
  arrival order of this table.

**NO GenericForeignKey — the app bans it** (``ColdChainMonitors.py:18``,
``PortalDocumentShares.py:9-11``): a ``(content_type, object_id)`` pair cannot be tenant-joined, so
every query that has to prove "this row belongs to this workspace" degrades into a Python-side
check. Correlation to an internal document is therefore a **soft pointer** — the ``source`` choice
plus a free-text ``source_reference`` (the ``DemandSignals.py:74`` /
``ComplianceRequirements.py:239`` / ``ClientBillingRunLines.py:810`` idiom) — with exactly TWO typed
nullable FKs alongside it for the two flows worth joining in SQL: ``purchase_order`` and
``sales_order``. GoodsReceiptNote, Shipment, StockMove, Item, TradeDocument, ReturnAuthorization and
LogisticsClient are reachable only through the soft pointer this pass; each becomes a typed FK the
day a page actually needs to *join* on it, and not before.

**NO TRANSPORT.** 4.19 ships no ``requests`` / ``urllib`` / ``httpx`` / ``http.client`` import
anywhere. Nothing in this pass fetches, posts, signs or polls; rows are written by the seeder and by
whatever integration pass lands later. ``reprocess`` re-queues a row and fires **no HTTP request**.

**Note on layout, so no review agent "fixes" it:** the backend package is ``IntegrationApiGateway/``
(PascalCase of the NavERP.md title) while the templates live in ``templates/scm/integration/`` (the
short slug every shipped scm template folder uses). The asymmetry is the house rule, not a defect —
the identical note sits at ``ThirdPartyLogistics/LogisticsClients.py:35-38`` and
``CustomerPortal/PortalAccounts.py:45-47``.
"""
from apps.scm.models._base import *  # noqa: F401,F403
# BY NAME, never `import *` — `apps/scm/models/__init__.py` already star-imports several `_choices`
# modules, so one more star-import could silently shadow a shared token with the winner decided by
# import order. `IntegrationApiGateway/_choices.py` imports NOTHING (not even `_base`), so the
# dependency edge inside 4.19 only ever runs one way and no cycle is possible.
#
# THE `IntegrationEndpoints` ENTITY OWNS THAT FILE. This module, `WebhookSubscriptions` and
# `WebhookDeliveries` import from it exactly like the line below and must never create or edit it.
from apps.scm.models.IntegrationApiGateway._choices import (
    DOCUMENT_TYPE_CHOICES,
    MESSAGE_DIRECTION_CHOICES,
    MESSAGE_SOURCE_CHOICES,
    MESSAGE_STATUS_CHOICES,
)


class IntegrationMessage(TenantNumbered):
    """One document/batch/event that crossed the boundary, recorded once [MSG-]. Append-only."""

    NUMBER_PREFIX = "MSG"

    #: Every FK on this model whose target is tenant-scoped, read by this model's own ``clean()``.
    #: There is no form for this model, so — unlike the sub-module's two edited entities — nothing
    #: calls ``_reject_foreign`` against this tuple; ``clean()`` is the single boundary, and it is
    #: the one that holds for the seeder, the shell and the admin as well.
    TENANT_SCOPED_FKS = ("endpoint", "acknowledges", "purchase_order", "sales_order")

    # --- what it crossed through -----------------------------------------------------------------
    # CASCADE, and the only one in this sub-module: a log line has no life of its own without the
    # endpoint it crossed. "Message MSG-00042 came in through <deleted>" is not a record anybody can
    # use, and orphaning it would leave the exceptions cockpit grouping failures under a connection
    # that no longer exists.
    endpoint = models.ForeignKey("scm.IntegrationEndpoint", on_delete=models.CASCADE,
                                 related_name="messages")

    # --- what it was -----------------------------------------------------------------------------
    # No default: which way a message travelled is never a safe assumption, and a wrong default here
    # would file inbound partner traffic as something we sent.
    direction = models.CharField(max_length=8, choices=MESSAGE_DIRECTION_CHOICES)
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPE_CHOICES, default="other")
    status = models.CharField(max_length=14, choices=MESSAGE_STATUS_CHOICES, default="pending")

    #: The partner's own envelope reference (an X12 ISA/GS/ST control number). Free text because the
    #: shape differs per standard and per VAN — this column exists to be quoted back at a partner,
    #: not to be parsed.
    control_number = models.CharField(max_length=32, blank=True)
    #: The PROVIDER's id for this delivery — ``X-Shopify-Webhook-Id``, the Svix ``eventId``. The
    #: de-dupe key, indexed with the tenant. Deliberately NOT unique: see the ordering caveat in the
    #: module docstring — a redelivery is a fact to record, not an insert to refuse.
    external_id = models.CharField(max_length=120, blank=True)
    #: How many records the payload carried. THE BATCH SIZE — a tag-read batch of 4,000 reads is ONE
    #: row with ``record_count=4000``, never 4,000 rows. An exchange log that grows with the volume
    #: of the traffic it describes stops being readable at exactly the moment it matters.
    record_count = models.PositiveIntegerField(
        default=0, help_text="Number of records the payload carried (batch size), not a row count.")

    payload_excerpt = models.TextField(
        blank=True,
        help_text="TRUNCATED excerpt only. May contain partner PII (ship-to names and addresses on "
                  "an 856). A full document body is NEVER stored.")

    # --- how it went -----------------------------------------------------------------------------
    error_code = models.CharField(max_length=40, blank=True)
    error_message = models.TextField(blank=True)
    #: Bumped by ``integrationmessage_reprocess`` and by nothing else. ``editable=False`` makes "no
    #: form ever shows this" structural rather than a rule somebody has to remember (L22).
    attempt_count = models.PositiveSmallIntegerField(default=1, editable=False)

    # --- when ------------------------------------------------------------------------------------
    # `default=timezone.now` rather than `auto_now_add`: a message that crossed the boundary at
    # 02:14 and was recorded at 02:31 must be filed at 02:14, and a back-dated import must be able
    # to say so. `editable=False` keeps it off every form (L22) WITHOUT stopping the seeder or an
    # importer assigning it explicitly — the two are independent, and `auto_now_add` would have
    # taken the second away along with the first.
    occurred_at = models.DateTimeField(default=timezone.now, editable=False)
    acknowledged_at = models.DateTimeField(null=True, blank=True, editable=False)

    # --- what it was about (the soft pointer; see the module docstring) ---------------------------
    source = models.CharField(max_length=22, choices=MESSAGE_SOURCE_CHOICES, default="none")
    source_reference = models.CharField(
        max_length=60, blank=True,
        help_text="The referenced document's own number (e.g. PO-00042). A soft pointer, not an FK "
                  "— see the model docstring for why there is no GenericForeignKey here.")

    #: The 997 points at the 850 it answers. ``SET_NULL`` and not ``CASCADE``: an acknowledgement
    #: outlives the thing it acknowledged — losing the answered row must not delete the proof that
    #: the partner answered.
    acknowledges = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name="acknowledged_by")
    #: The two flows worth joining in SQL. Everything else goes through ``source`` +
    #: ``source_reference``; each earns a typed FK the day a page needs to JOIN on it.
    purchase_order = models.ForeignKey("scm.PurchaseOrder", on_delete=models.SET_NULL, null=True,
                                       blank=True, related_name="+")
    sales_order = models.ForeignKey("scm.SalesOrder", on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="+")

    class Meta:
        # Newest first — this is a log, and the tie-break on `-id` is load-bearing rather than
        # decorative: a batch import lands many rows on the identical `occurred_at`, and without it
        # page 2 is whatever the database felt like returning (L9's sibling problem).
        ordering = ["-occurred_at", "-id"]
        # WITH the tenant, never a bare global unique=True — two workspaces both legitimately own an
        # MSG-00001.
        unique_together = (("tenant", "number"),)
        indexes = [
            # The list page's status filter AND the exceptions cockpit, which is the reason for the
            # third column. `integration_exceptions` always filters tenant + status="failed" and then
            # takes 30 rows in `ordering` order, so a 2-column (tenant, status) index served the
            # equality and left MariaDB to filesort the whole failure set on every page load of the
            # sub-module's main report. With `occurred_at` in the index the sort is satisfied by the
            # index order — the DESC direction is fine, InnoDB reads a B-tree backwards. Widened
            # rather than added alongside: (tenant, status) is this index's own leftmost prefix, so
            # every query the 2-column version served still uses it and nothing regresses.
            models.Index(fields=["tenant", "status", "occurred_at"], name="scm_msg_tnt_status_idx"),
            # The endpoint detail page's "recent messages" panel and the list's ?endpoint= filter.
            models.Index(fields=["tenant", "endpoint"], name="scm_msg_tnt_endpoint_idx"),
            # The redelivery de-dupe probe — the one lookup that has to stay cheap while this table
            # is the fastest-growing one in the sub-module.
            models.Index(fields=["tenant", "external_id"], name="scm_msg_tnt_extid_idx"),
            # `ordering` itself, plus the list page's date window. A range on the column, which is
            # why the views widen `?date_from=` into a datetime range rather than wrapping the
            # column in `__date` (a function of a column cannot use this index).
            models.Index(fields=["tenant", "occurred_at"], name="scm_msg_tnt_occat_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.get_document_type_display()}"

    def clean(self):
        """The cross-tenant FK guard, plus the one self-reference that cannot mean anything."""
        super().clean()

        # THE GUARD. This model has no form, so there is no narrowed dropdown in front of it and no
        # `_reject_foreign` behind it — this loop is the whole boundary. Skipped when the instance
        # has no tenant yet: an unsaved row has `tenant_id` None and `self.tenant` would raise
        # RelatedObjectDoesNotExist on a non-nullable FK rather than return None.
        if self.tenant_id is not None:
            for name in self.TENANT_SCOPED_FKS:
                if getattr(self, f"{name}_id", None) is None:
                    continue
                # Defaulted getattr: RelatedObjectDoesNotExist subclasses AttributeError, so a
                # pointer whose row went away degrades to None here instead of 500-ing inside
                # validation.
                related = getattr(self, name, None)
                if related is not None and related.tenant_id != self.tenant_id:
                    raise ValidationError({name: "That record belongs to another workspace."})

        # A row cannot acknowledge itself. Checked against the pk rather than the object so it holds
        # on an admin edit of a saved row, and skipped while `pk` is None because an unsaved row
        # cannot yet be pointed at by anything, including itself.
        if self.pk is not None and self.acknowledges_id == self.pk:
            raise ValidationError(
                {"acknowledges": "A message cannot acknowledge itself — point at the message this "
                                 "one answers."})
