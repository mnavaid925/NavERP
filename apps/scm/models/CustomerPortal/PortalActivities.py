"""SCM 4.16 Customer Portal — PortalActivity, the append-only evidence trail.

**What this table is for.** It makes *"we published that POD on the 3rd and you downloaded it on the
4th"* a sentence somebody can defend with a row rather than a memory, and it is the only honest input
to any deflection metric this sub-module claims (a self-service number computed from anything other
than recorded self-service is a press release). It is also the answer to the flat question a staff
enablement console has to ask: *has this account ever actually logged in?*

**Why NOT ``core.AuditLog``.** Its ``ACTION_CHOICES`` are ``create`` / ``update`` / ``delete`` only
(read off ``apps/core/models/AuditLog.py`` at write time — that is the whole vocabulary). AuditLog
records *staff changing a record*; this table records *a customer reading one*. Those are different
facts, and a read is not a mutation dressed differently: it has no ``changes`` diff, no before/after,
and its interesting dimension is which document left the building rather than which column moved.
Widening AuditLog's vocabulary to fit would corrupt an existing audit surface — every AuditLog reader
today may assume an entry means something changed, and half of them would start counting page views
as edits. So 4.16 keeps its own log, and **staff CRUD on all four 4.16 models still goes through
``write_audit_log`` exactly as before.** The two tables answer two questions and neither replaces the
other.

**Append-only — the ``StockMove`` / ``TrackingEvent`` / ``MeterReading`` posture.** A row is written
once and never edited or deleted. That is not tidiness, it is the entire value of the table: evidence
that can be revised after the dispute starts is not evidence. Consequently **every field is
``editable=False``, there is no form module for this model, and the front end ships LIST + DETAIL
only** — no create, no edit, no delete route and no Actions column. That is a deliberate, precedented
exception to the CRUD-completeness rule, matching ``StockMoveAdmin`` and ``MeterReadingAdmin`` in
``apps/scm/admin.py``, which already refuse add/change/delete for the same reason. **A reviewer
should not "complete" this CRUD.**

``TenantOwned``, not ``TenantNumbered``, and no ``NUMBER_PREFIX`` — the ``StockMove`` /
``MeterReading`` rule: a document number is for something a person quotes back across a conversation,
and nobody has ever said "see activity PAC-00417". The row is identified by its account and its
timestamp.

**There is no ``at`` column.** ``TenantOwned.created_at`` already is that timestamp, and it is
``auto_now_add`` so it cannot be back-dated by a caller. Two columns both meaning "when" is two
things to keep in sync and, the first time they disagree, a log nobody trusts.
"""
from apps.scm.models._base import *  # noqa: F401,F403
from apps.scm.models.CustomerPortal._choices import PORTAL_ACTION_CHOICES, PORTAL_ACTION_CSS


class PortalActivity(TenantOwned):
    """One thing a customer did in the portal, recorded once and never touched again."""

    #: The optional pointers :meth:`record` accepts. Table-driven so adding a fourth target means
    #: adding it here rather than remembering to widen a hand-written kwargs dict — and so an
    #: unrecognised keyword at a call site is dropped instead of exploding inside the writer.
    TARGET_FIELDS = ("sales_order", "shipment", "document_share")

    #: Ceiling on :attr:`object_label`, mirrored from the column so :meth:`record` can truncate
    #: rather than let an over-long label raise inside a fail-soft block and lose the whole row.
    MAX_LABEL_LENGTH = 160

    # ``tenant`` / ``created_at`` / ``updated_at`` come from TenantOwned and are NOT re-declared:
    # Django forbids overriding a field inherited from an abstract base, and the two timestamps are
    # already non-editable by virtue of auto_now_add / auto_now. ``tenant`` staying nominally
    # editable costs nothing here because this model has no form at all — the "every field is
    # editable=False" rule is enforced on every field this class actually declares.

    portal_account = models.ForeignKey(
        "scm.PortalAccount", on_delete=models.CASCADE, related_name="activities", editable=False)

    # SET_NULL and nullable on purpose: a visitor arriving on a PortalDocumentShare token link is
    # not signed in, so there is no user to name — and that is a real, recordable event rather than
    # a row to skip. SET_NULL also means deactivating and deleting a portal login cannot erase the
    # trail of what that login did; object_label keeps the human string either way.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+", editable=False)

    # max_length 20 against a 17-char longest value ('download_document') — the headroom the 4.10
    # lesson asks for, because a longer value added later is a column widen, not a one-line edit.
    action = models.CharField(max_length=20, choices=PORTAL_ACTION_CHOICES, editable=False)

    # The short human string the row is read by — "SO-00012", "PDS-00004", an item SKU. It is
    # DENORMALISED on purpose: the three pointers below are all SET_NULL, so once a target is gone
    # the label is the only thing left that says what was looked at, and a log whose oldest rows
    # read "viewed an order" with no order is not evidence of anything.
    object_label = models.CharField(max_length=160, blank=True, editable=False)

    # The typed pointers, all SET_NULL: an activity row must outlive the thing it is about. None of
    # them is required — 'login' and 'view_catalog' point at nothing, which is why there is no
    # "exactly one pointer" rule here (unlike PortalDocumentShare, where the pointer IS the record).
    sales_order = models.ForeignKey(
        "scm.SalesOrder", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+", editable=False)
    shipment = models.ForeignKey(
        "scm.Shipment", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+", editable=False)
    document_share = models.ForeignKey(
        "scm.PortalDocumentShare", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+", editable=False)

    # SECURITY — read this before "improving" it. This is populated from request.META["REMOTE_ADDR"]
    # and from NOTHING ELSE. X-Forwarded-For (and X-Real-IP, and every other forwarding header) is
    # supplied by the caller: any client can send `X-Forwarded-For: 8.8.8.8` and, absent a list of
    # proxies we trust to have rewritten it, there is no way to tell a genuine hop from a lie. This
    # repo has no such trusted-proxy list and no USE_X_FORWARDED_HOST-style setting for it. Trusting
    # the header therefore writes an ATTACKER-CHOSEN string into an evidence table — the one table
    # whose entire job is to be believable in a dispute. REMOTE_ADDR is set by the WSGI server from
    # the socket, so behind a reverse proxy it records the proxy rather than the visitor; a
    # deliberately less precise value that is true beats a precise one that is forgeable. If a
    # trusted-proxy chain is ever configured, THAT is the change to make — not a header read here.
    ip_address = models.GenericIPAddressField(null=True, blank=True, editable=False)

    class Meta:
        # Newest first — every reader of this table (the account detail panel, the staff activity
        # list, "when did they last log in") wants the most recent rows and walks backwards.
        ordering = ["-created_at"]
        # NO unique_together, deliberately. This is a log, not a register: a customer who opens the
        # same order twice in one second performed two actions, and both are facts. A uniqueness
        # rule here would silently discard the second one and, with it, the frequency signal that
        # makes the log worth keeping.
        indexes = [
            # The workhorse: the per-account timeline filters (tenant, portal_account) and orders by
            # created_at, so the sort is served by the index instead of a filesort per account.
            # tenant_id is the LEADING column, so a query that reaches this table through the
            # related manager alone (``account.activities...``) states no tenant, cannot open this
            # index and falls back to the FK index plus a filesort — the MeterReading lesson. Every
            # caller states a "redundant" tenant= that narrows nothing and buys the whole index.
            models.Index(fields=["tenant", "portal_account", "created_at"],
                         name="scm_pact_tnt_acct_at_idx"),
            # Whole-workspace views (the staff activity list filtered to logins, any deflection
            # count) cannot use the index above — portal_account is not a prefix of the filter.
            models.Index(fields=["tenant", "action"], name="scm_pact_tnt_action_idx"),
        ]

    def __str__(self):
        return f"{self.get_action_display()} · {self.object_label or self.portal_account}"

    @property
    def action_css(self):
        """theme.css badge class for :attr:`action` — one lookup, so no template invents a colour.

        Colour is decided once in ``_choices.PORTAL_ACTION_CSS`` (the ``LaborStandard.status_css``
        precedent) so the list badge and the detail badge cannot drift apart.
        """
        return PORTAL_ACTION_CSS.get(self.action, "badge-muted")

    @classmethod
    def record(cls, account, action, *, request=None, user=None, **targets):
        """**The single writer.** Append one activity row; return it, or ``None`` if it could not be
        written.

        Called ONLY from the gated customer portal views and the token download view. **Never from a
        staff view** — a staff member opening a customer's order is ``core.AuditLog``'s business, and
        letting staff traffic into this table would corrupt the one number it exists to support: how
        much the customer actually served themselves.

        ``**targets`` accepts :attr:`TARGET_FIELDS` (model instances, not pks) plus ``object_label``;
        anything else is dropped. Dropping rather than forwarding is the deliberate choice — an
        unrecognised keyword forwarded to ``create()`` raises ``TypeError``, which the fail-soft
        block below would swallow, costing the entire row instead of one mistyped pointer.

        **It fails soft, on purpose.** Everything is inside one ``except``: a logging error must
        never 500 the page the customer was reading. The customer came to find out where their order
        is; a database hiccup in the audit trail is our problem, not a reason to show them an error
        page. The accepted cost is a gap in the log rather than a broken page, and that is the right
        way round — an evidence trail that can take down the thing it is evidencing would get turned
        off within a week, which is a permanent gap instead of an occasional one.

        The actor is taken from ``user`` when given, else from ``request.user`` **only when it is
        authenticated** — an ``AnonymousUser`` assigned to a FK raises, and a token visitor legally
        has no user at all (see the field comment).
        """
        try:
            fields = {name: targets.get(name) for name in cls.TARGET_FIELDS}

            actor = user
            if actor is None and request is not None:
                candidate = getattr(request, "user", None)
                # AnonymousUser is truthy and has no pk — is_authenticated is the only safe test.
                if candidate is not None and getattr(candidate, "is_authenticated", False):
                    actor = candidate

            # REMOTE_ADDR ONLY — see the ip_address field comment for why no forwarding header is
            # consulted. Empty string degrades to NULL so "we did not capture it" and "it was blank"
            # are the same, single, honest value.
            ip = None
            if request is not None:
                ip = (request.META.get("REMOTE_ADDR") or "").strip() or None

            return cls.objects.create(
                tenant_id=account.tenant_id,
                portal_account=account,
                action=action,
                object_label=(targets.get("object_label") or "")[:cls.MAX_LABEL_LENGTH],
                ip_address=ip,
                user=actor,
                **fields,
            )
        except Exception:  # noqa: BLE001 — a gap in the log never breaks the page being logged
            return None
