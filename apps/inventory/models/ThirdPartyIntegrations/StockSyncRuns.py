"""Inventory 5.19 Third-Party Integrations & API — ``StockSyncRun``, the append-only
push/pull batch log.

One row per stock-sync batch recorded against one
:class:`~apps.inventory.models.ThirdPartyIntegrations.IntegrationChannel` — Boomi document
tracking / Workato job reports posture, the inventory twin of scm's ``IntegrationMessage``
register. A run says what a sync DID as a batch: how many records it walked, how many landed,
how many failed, and where it stopped. It is never one row per record (the counts columns are
the whole point) and it NEVER mutates stock: quantities live in 4.3's ledger, and this table
only ever *describes* traffic around them.

==================================================================================================
1. APPEND-ONLY — list + detail + retry POST, no create/edit/delete anywhere
==================================================================================================
There is no ``StockSyncRunForm`` (the forms sub-package ``__init__`` carries the deliberate-absence
comment instead of an import), no create/edit/delete route, and no edit/delete affordance in any
template. Runs enter through :meth:`record` — the sync verb and the seeder both go through it and
nothing else writes rows — and the ONE UI write this table exposes is
``stocksyncrun_retry``, which moves only the row's own queue state (``status`` / ``attempt_no`` /
``next_retry_at``) and touches no recorded outcome (counts/error/payload untouched). The
correction for a wrong row is a later row, exactly as in scm's delivery/message registers.

==================================================================================================
2. WHY THIS TABLE IS NUMBERED (SYN-) — the human-discussed-batches line
=================================================================================================
The app draws the numbering line at "records humans discuss by name": runs ARE discussed that way
("last night's Shopify push", "chase SYN-00042"), which is why this class extends
``TenantNumbered`` with ``NUMBER_PREFIX = "SYN"``. Per-attempt telemetry sits on the other side of
that line — scm's ``WebhookDelivery`` carries its explicit no-number ruling for exactly the mirror
reason: nobody chases WHD-04417 about the fourth retry of one event. A run is the unit a human
argues about; an attempt inside it is bookkeeping. Hence: numbered here, unnumbered there.

==================================================================================================
3. NOTHING IN THIS PASS SENDS ANYTHING — and ``simulated`` is first-class
==================================================================================================
5.19 ships no transport: no ``requests``/``urllib``/``httpx``/``http.client`` anywhere, no
scheduler reading ``next_retry_at`` on a clock. So:

* ``status`` carries a mandatory-honesty ``simulated`` member — a run that never left the process
  is neither a success nor a failure, and recording "success" would fabricate evidence;
* ``next_retry_at`` is a STAMP, not a trigger — nothing wakes up and reads it;
* the retry verb performs no HTTP request; it advances the row onto the published backoff schedule
  (:data:`~apps.inventory.models.ThirdPartyIntegrations._choices.SYNC_BACKOFF_SECONDS`, Svix's
  tuple adopted verbatim, same posture as scm's DELIVERY_BACKOFF_SECONDS) and says so out loud.
"""
from apps.inventory.models._base import *  # noqa: F401,F403

# BY NAME, never `import *` — siblings already star-import several `_choices` modules through the
# package __init__, so a further star-import could silently shadow a shared token with the winner
# decided by import order. `ThirdPartyIntegrations/_choices.py` imports NOTHING (not even `_base`),
# so the dependency edge inside 5.19 runs one way only and no cycle is possible.
#
# THAT FILE IS OWNED AND CREATED BY THE `IntegrationChannels` ENTITY MODULE. This module only reads
# from it and must never create or edit it.
from apps.inventory.models.ThirdPartyIntegrations._choices import (
    RUN_DIRECTION_CHOICES,
    RUN_STATUS_CHOICES,
    RUN_TRIGGER_CHOICES,
    SYNC_BACKOFF_SECONDS,
)


class StockSyncRun(TenantNumbered):
    """One stock-sync batch against one channel. Append-only register row."""

    NUMBER_PREFIX = "SYN"

    #: Re-checked in :meth:`clean` against this row's own tenant. No ModelForm exists in front of
    #: this table (docstring §1), so there is no narrowed ``<select>`` and no ``_reject_foreign``
    #: behind it — the guard below is the WHOLE boundary for shell/admin/seeder writers.
    TENANT_SCOPED_FKS = ("channel",)

    #: How many attempts the published backoff schedule describes (8 — Svix's, adopted verbatim).
    #: Read by the detail page (*"attempt N of M"*) and derived from the tuple rather than typed, so
    #: widening the schedule cannot leave a stale ceiling behind it.
    MAX_ATTEMPTS = len(SYNC_BACKOFF_SECONDS)

    #: CASCADE, and the only sensible rule: a run log with no rule is telemetry about nothing.
    #: ``related_name="runs"`` is what the channel detail page's recent-runs panel reads.
    channel = models.ForeignKey("inventory.IntegrationChannel", on_delete=models.CASCADE,
                                related_name="runs")

    #: Push (we sent availability out) vs pull (orders/stock came in). NO default, never assume:
    #: recording a direction by accident is worse than refusing to save without one.
    direction = models.CharField(max_length=14, choices=RUN_DIRECTION_CHOICES)

    #: What started the batch. INTENT vocabulary only — no scheduler exists in this pass.
    trigger_mode = models.CharField(max_length=15, choices=RUN_TRIGGER_CHOICES, default="manual")

    #: ``simulated`` is mandatory honesty (docstring §3): nothing leaves the process, so a demo or
    #: dry-run batch must never be recorded as plain "success".
    status = models.CharField(max_length=10, choices=RUN_STATUS_CHOICES, default="pending")

    # Batch counts — one row per BATCH, never one row per record.
    records_total = models.PositiveIntegerField(default=0)
    records_ok = models.PositiveIntegerField(default=0)
    records_failed = models.PositiveIntegerField(default=0)

    payload_excerpt = models.TextField(
        blank=True,
        help_text="TRUNCATED excerpt only. May contain buyer PII. A full body is NEVER stored.")

    error_code = models.CharField(max_length=40, blank=True)
    error_message = models.TextField(blank=True)

    #: 1-based ATTEMPT counter. Attempt N has consumed slot N-1 of SYNC_BACKOFF_SECONDS (attempt 1
    #: runs immediately at slot 0), so the wait BEFORE the next attempt lives at index
    #: ``attempt_no`` — which is exactly what :meth:`next_backoff_seconds` reads, the contract
    #: scheme scm's WebhookDelivery uses verbatim.
    attempt_no = models.PositiveSmallIntegerField(default=1)

    #: A STAMP, not a trigger (docstring §3). Nothing reads this on a clock — there is no scheduler
    #: in this pass. The retry verb writes it so a human can see what pressing Retry queued, and so
    #: the transport pass has a column already in place.
    next_retry_at = models.DateTimeField(null=True, blank=True)

    #: ``default=now``, NOT ``auto_now_add``: the seeder must be able to back-date demo runs across
    #: a plausible window, and auto_now_add would stamp every row with seed time. ``editable=False``
    #: makes "no form shows this" structural rather than remembered.
    started_at = models.DateTimeField(default=timezone.now, editable=False)

    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        # Newest first; the `-id` tie-break is load-bearing rather than decorative — a burst of
        # batches lands many rows on the identical `started_at`, and without a TOTAL order tied
        # rows can swap between page 1 and page 2 of the same paginated read.
        ordering = ["-started_at", "-id"]
        unique_together = (("tenant", "number"),)
        indexes = [
            # The channel detail page's recent-runs panel and the list's ?channel= deep-link —
            # the two most frequent reads on the table.
            models.Index(fields=["tenant", "channel"], name="inv_syn_tnt_channel_idx"),
            # The ?status= filter plus newest-first ordering (status, then started_at) so the
            # common "failed runs, latest first" lens is index-served.
            models.Index(fields=["tenant", "status", "started_at"], name="inv_syn_tnt_status_idx"),
            # The register's default landing order is -started_at over an unbounded append-only
            # table: a leading (tenant, started_at) index serves the bare newest-first page 1
            # without a file-sort.
            models.Index(fields=["tenant", "started_at"], name="inv_syn_tnt_started_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.get_direction_display()}"

    @classmethod
    def record(cls, tenant, channel, *, direction, trigger_mode="manual", **extra):
        """THE append-only creator. Builds, saves, returns — assigns nothing beyond the kwargs,
        the tenant and the channel.

        Views (the sync verb) and the seeder create runs ONLY through it; there is no edit/delete
        route anywhere, so this method is the single front door of the table. Extra outcome fields
        (``status``, counts, ``finished_at``, …) ride in via ``**extra`` exactly as named kwargs —
        no second implicit default is applied here.
        """
        run = cls(tenant=tenant, channel=channel, direction=direction,
                  trigger_mode=trigger_mode, **extra)
        run.save()
        return run

    @property
    def next_backoff_seconds(self):
        """Seconds the NEXT retry would wait, or ``None`` once the schedule is spent.

        The frozen contract scheme, identical to scm's ``WebhookDelivery``: attempt N occupies
        slot N-1 (attempt 1 ran immediately at slot 0), so the wait a retry from the CURRENT state
        would incur is read at index ``attempt_no``. Both bounds are checked BEFORE indexing —
        ``attempt_no`` is a PositiveSmallIntegerField a raw import could set to 0, and an unguarded
        read would either negative-index silently onto the LAST tuple slot (0) or run off the end.
        The schedule is spent when ``attempt_no >= len(SYNC_BACKOFF_SECONDS)``: there is no slot
        left to offer, and the retry verb marks the row ``exhausted`` instead of scheduling an
        attempt the published schedule does not describe. Returning ``None`` — rather than raising
        or clamping to the last slot — is the signal both callers agree on: the detail page renders
        *"schedule spent"* and ``stocksyncrun_retry`` flips the status.
        """
        if not 0 <= self.attempt_no < len(SYNC_BACKOFF_SECONDS):
            return None
        return SYNC_BACKOFF_SECONDS[self.attempt_no]

    def clean(self):
        """The cross-tenant FK guard. This model has no form, so this is the whole boundary.

        Skipped while the instance has no tenant yet: an unsaved row has ``tenant_id`` ``None``
        and ``self.tenant`` would raise ``RelatedObjectDoesNotExist`` on a non-nullable FK rather
        than return ``None``.
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
