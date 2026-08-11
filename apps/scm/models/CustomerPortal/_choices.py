"""SCM 4.16 Customer Portal — the vocabularies and bounds shared across the sub-module.

**Why this file exists.** Same rule as ``AssetManagement/_choices.py`` and
``LaborManagement/_choices.py``: a vocabulary read by exactly one model stays on that model.
Everything below is read from **two or more directions at once** —

* ``STOCK_DISPLAY_CHOICES`` / ``CATALOG_SCOPE_CHOICES`` / ``PRICE_BASIS_CHOICES`` — declared on
  ``PortalAccount``, branched on by the customer catalog page **and** by the staff
  "catalog as seen by customer X" preview. One vocabulary, or the preview renders a projection the
  real portal would never show, which is the exact bug that page exists to prevent.
* ``INQUIRY_TYPE_CHOICES`` — declared on ``PortalOrderInquiry``, read by its ``clean()`` (the
  order-bound types below), by ``open_for()`` (which derives the ``crm.Case.type`` from it) and by
  both the staff and the customer forms.
* ``INQUIRY_OUTCOME_CHOICES`` — written only by the workflow verbs, filtered on the list page and
  banded on the detail page.
* ``SHARE_DOC_TYPE_CHOICES`` + ``SHARE_DOC_TYPE_FIELDS`` — the doc-type/pointer contract is read by
  ``PortalDocumentShare.clean()``, by the form (which scopes each pointer queryset) and by the
  download view. Three copies of that table would be three chances to disagree about which column a
  ``coa`` lives in.
* ``PORTAL_ACTION_CHOICES`` — written by ``PortalActivity.record()`` from half a dozen portal views
  and filtered on the staff activity list.
* The bounds — enforced in ``clean()`` so the form, the seeder and every future verb inherit them,
  and quoted back in the messages the views and templates print.

**Pure data — no imports at all: no queries, no model imports, not even ``_base``.** Nothing here
imports a sibling model, so the dependency edge inside the sub-module can only ever run one way
(``PortalAccounts`` / ``PortalOrderInquiries`` / ``PortalDocumentShares`` / ``PortalActivities`` ->
``_choices``) and no import cycle is possible.

**``__all__`` is explicit, and the parent re-exports these BY NAME rather than with ``import *``.**
``apps/scm/models/__init__.py`` already star-imports 4.12's and 4.13's ``_choices``; a second
star-imported ``_choices`` re-declaring a shared token would **silently shadow** one of them, with
the winner decided by import order. Spelling every name out makes such a collision a visible edit
instead of a runtime coin-flip. (Checked at write time: none of the names below is declared anywhere
else in ``apps/scm/models``.)

**Why the vocabularies are CLOSED.** ``inquiry_type`` in particular could have been a free-text box,
and then "which failure mode drives our WISMO volume?" would be a pile of strings nobody can total.
A closed set makes that question a ``GROUP BY`` — which is the entire reason we ask the customer to
pick a type at all. ``other`` is present wherever a customer chooses, so nobody is ever forced into a
wrong code; the honest escape hatch is what keeps the other values trustworthy.

**The CSS dicts.** Colour is decided in exactly one place per vocabulary (the ``KpiSnapshot.BAND_CSS``
precedent) so a badge cannot be styled one way on the list page and another on the detail page. Only
the six classes that actually exist in ``static/css/theme.css`` may appear —
``badge-green / badge-red / badge-amber / badge-info / badge-muted / badge-slate``. There is no
``badge-success`` / ``badge-warning`` / ``badge-danger``; those render completely unstyled (L33,
already shipped four times). Verified against ``theme.css`` before this file was written.
"""

__all__ = [
    "STOCK_DISPLAY_CHOICES", "THRESHOLD_STOCK_DISPLAYS",
    "STOCK_BAND_LABELS", "STOCK_BAND_CSS", "stock_band",
    "CATALOG_SCOPE_CHOICES",
    "PRICE_BASIS_CHOICES",
    "PREFERRED_CHANNEL_CHOICES",
    "INQUIRY_TYPE_CHOICES", "INQUIRY_TYPE_CSS", "ORDER_BOUND_INQUIRY_TYPES",
    "REQUESTED_RESOLUTION_CHOICES",
    "INQUIRY_OUTCOME_CHOICES", "INQUIRY_OUTCOME_CSS",
    "INQUIRY_SOURCE_CHOICES",
    "SHARE_DOC_TYPE_CHOICES", "SHARE_DOC_TYPE_CSS",
    "SHARE_DOC_TYPE_FIELDS", "SHARE_POINTER_FIELDS", "MAX_SHARE_EXPIRY_DAYS",
    "PORTAL_ACTION_CHOICES", "PORTAL_ACTION_CSS",
    "CUSTOMER_STATUS_MAP",
]


# --------------------------------------------------------------------------------------------
# PortalAccount — how this customer's catalog is presented to them
# --------------------------------------------------------------------------------------------

#: How much of the live stock figure this customer is allowed to see. **Sana's Stock Presentation**
#: is the model: exact amount, text, colour indicator, or hidden entirely, with different rules for
#: B2C, B2B and sales agents; Unleashed ships the same idea. It is a per-ACCOUNT setting because the
#: reason to hide a number is commercial (a competitor buying one pallet must not read our whole
#: position), and that reason varies by who is looking, not by which item they looked at.
#:
#: Whatever is chosen, the number behind it is **derived over the append-only ``StockMove`` ledger
#: and never a stored column** (L37) — this vocabulary decides the *rendering* of that figure, never
#: its source.
#:
#: ``max_length=20`` against a 17-char longest value (``availability_text``) — headroom, because a
#: longer value added later is a column widen, not "a one-line choices change".
STOCK_DISPLAY_CHOICES = [
    ("hidden", "Hidden — show nothing"),
    ("availability_text", "Availability text (in stock / low / out of stock)"),
    ("band", "Colour band only"),
    ("exact_quantity", "Exact quantity"),
]

#: The displays that actually *consume* ``PortalAccount.low_stock_threshold``. ``clean()`` rejects a
#: threshold set against ``hidden`` or ``exact_quantity`` rather than ignoring it, because a number a
#: user typed and the system silently dropped is worse than an error: they believe it took effect.
#: Owned here so the model's ``clean()``, the form's help text and the catalog renderer that compares
#: against the threshold cannot drift apart.
THRESHOLD_STOCK_DISPLAYS = ("availability_text", "band")

#: The three buckets a derived on-hand figure collapses into, and the ONE place their words and
#: colours are decided.
#:
#: **This is not a model vocabulary and never becomes a column.** No row anywhere stores a band: the
#: band is recomputed from the on-hand aggregate every time a catalog page renders, because on-hand
#: is itself derived over the append-only ``StockMove`` ledger (L37). A stored band would be a cached
#: copy of a derived figure — stale the moment a move posts, and stale in the direction that tells a
#: customer something is in stock when it is not.
#:
#: ``availability_text`` and ``band`` are the SAME three buckets rendered two ways, which is exactly
#: why :data:`THRESHOLD_STOCK_DISPLAYS` contains both: the text display prints
#: :data:`STOCK_BAND_LABELS`, the band display shows :data:`STOCK_BAND_CSS` as a colour chip. Two
#: vocabularies here would let the words and the colour disagree about the same quantity on the same
#: page — the customer reads "In stock" beside an amber dot and trusts neither.
#:
#: **The colour is never the only carrier of the meaning.** A colour-only chip is invisible to a
#: screen reader and to the ~8% of men with a red/green deficiency, so a template rendering the band
#: must still expose the label as ``title``/``aria-label`` even when it prints no visible text. The
#: pairing lives here so that rule has one home rather than being remembered per template.
STOCK_BAND_LABELS = {
    "out": "Out of stock",
    "low": "Low stock",
    "in": "In stock",
}

#: Colour-named theme.css classes only — ``badge-success``/``badge-warning``/``badge-danger`` do not
#: exist in this project and render completely unstyled (L33).
STOCK_BAND_CSS = {
    "out": "badge-red",
    "low": "badge-amber",
    "in": "badge-green",
}


def stock_band(on_hand, threshold=None):
    """Bucket a derived on-hand quantity into ``"out"`` / ``"low"`` / ``"in"``, or ``None``.

    ``None`` in means ``None`` out, and it is a genuinely different answer from ``"out"``: *no
    ledger rows exist for this item at this scope* is not the same statement as *we have none left*.
    The first renders as an em-dash, the second as "Out of stock" — and a caller that collapses them
    tells a customer an item is unavailable when the truth is that nobody has ever counted it.

    ``threshold`` of ``None`` or zero means the account set none, so nothing is ever "low": a
    positive quantity is simply in stock. That is the right default, because
    ``PortalAccount.low_stock_threshold`` defaults to zero and a zero threshold treated as "low"
    would paint every item amber on every freshly created account.

    Pure and import-free on purpose — this module deliberately imports nothing at all (not even
    ``Decimal``), so the dependency edge inside 4.16 runs one way and no cycle is possible. The
    comparisons work unchanged on ``Decimal``, ``int`` and ``float``.
    """
    if on_hand is None:
        return None
    if on_hand <= 0:
        return "out"
    if threshold is not None and threshold > 0 and on_hand <= threshold:
        return "low"
    return "in"

#: Which items this customer's catalog contains. Customer-specific catalogs are table stakes in the
#: surveyed products (Shopify B2B, Oro organization-aware catalogs, Unleashed per-customer
#: catalogues). ``previously_ordered`` is the cheapest useful one for a distributor — it is derived
#: from the customer's own ``SalesOrderLine`` history and needs no curation at all.
#:
#: ``max_length=20`` against a 18-char longest value (``previously_ordered``).
CATALOG_SCOPE_CHOICES = [
    ("all_active", "All active items"),
    ("previously_ordered", "Items previously ordered"),
    ("categories", "Selected categories only"),
]

#: What price, if any, the portal prints. **This vocabulary is short because of a documented GAP, not
#: because pricing is simple:** there is no customer price list / price book on the SCM side, so the
#: only price this build can state truthfully is the one the customer themselves last paid.
#: ``last_ordered`` is that customer's own most recent ``SalesOrderLine.unit_price`` for the item,
#: **derived at render time and never stored** — a stored copy would quietly become a quote we never
#: agreed to. A real price engine (tiers, contracts, volume breaks, currency) is **9.3**, and when it
#: lands it adds a value here rather than replacing the column.
PRICE_BASIS_CHOICES = [
    ("hidden", "Hidden — no prices"),
    ("last_ordered", "This customer's last ordered price"),
]

#: Where this account would *prefer* to be told about shipment events (Narvar's channel choice,
#: NetSuite's email preferences).
#:
#: **4.16 DISPATCHES NOTHING.** These are stored preferences only — exactly the posture
#: ``SalesOrder.confirmation_sent_at`` / ``shipped_notification_at`` / ``delivered_notification_at``
#: have held unfired since 4.5. The preference is captured now so the day a mailer exists it reads a
#: column that already carries years of customer intent, instead of defaulting everyone to "email"
#: and spamming them. The form and the docstring both say so; **do not read this as a promise that a
#: message goes out.** ``none`` is a real answer, not an empty one.
PREFERRED_CHANNEL_CHOICES = [
    ("email", "Email"),
    ("sms", "SMS"),
    ("none", "No notifications"),
]


# --------------------------------------------------------------------------------------------
# PortalOrderInquiry — what the customer is asking about, and how it ended
# --------------------------------------------------------------------------------------------

#: Why the customer got in touch. WISMO ("where is my order") is ~25-40% of inbound support volume
#: in the surveyed literature, which is why it is the default and why it leads the list. The rest is
#: the classic distribution claim set (short / damaged / wrong item) plus Narvar Care's dispute
#: shapes.
#:
#: ``reorder_request`` is the **honest v1 of "reorder"**: it files a ticket a salesperson acts on.
#: Writing a ``SalesOrder`` straight from the portal is parked to 9.4/9.17, and a button that
#: silently created an order would be a commercial commitment made by a page, not by a person.
#:
#: ``max_length=20`` against a 18-char longest value (``delivery_exception``).
INQUIRY_TYPE_CHOICES = [
    ("wismo", "Where is my order?"),
    ("delivery_exception", "Delivery exception"),
    ("short_shipment", "Short shipment"),
    ("damaged", "Damaged goods"),
    ("wrong_item", "Wrong item received"),
    ("quality", "Quality issue"),
    ("invoice_dispute", "Invoice dispute"),
    ("return_request", "Return request"),
    ("reorder_request", "Reorder request"),
    ("product_question", "Product question"),
    ("other", "Other"),
]

#: Colour is by **what the row costs us**, not by mood: red is goods we got wrong and will pay to put
#: right, amber is a claim under investigation, green is revenue, and the two pure questions are
#: neutral. A list where everything is red tells the reader nothing.
INQUIRY_TYPE_CSS = {
    "wismo": "badge-info",
    "delivery_exception": "badge-amber",
    "short_shipment": "badge-amber",
    "damaged": "badge-red",
    "wrong_item": "badge-red",
    "quality": "badge-red",
    "invoice_dispute": "badge-amber",
    "return_request": "badge-slate",
    "reorder_request": "badge-green",
    "product_question": "badge-info",
    "other": "badge-muted",
}

#: The types that are **meaningless without an order** — ``clean()`` requires ``sales_order`` for
#: every one of them. A WISMO ticket with no order attached is a question nobody can answer and a row
#: that can never join to a shipment, which defeats the whole point of wrapping the case in supply
#: chain context. ``invoice_dispute`` has its own rule (it requires ``invoice``) and is deliberately
#: NOT in this tuple; ``quality`` / ``return_request`` / ``product_question`` / ``other`` can legally
#: be about a product rather than a purchase.
#:
#: A tuple, not a re-derived filter, so the model's ``clean()``, the customer form's field-required
#: hinting and any future triage rule all branch on the same set (the ``OPEN_ALERT_STATUSES``
#: precedent).
ORDER_BOUND_INQUIRY_TYPES = (
    "wismo",
    "delivery_exception",
    "short_shipment",
    "damaged",
    "wrong_item",
    "reorder_request",
)

#: What the customer is *asking for*, recorded separately from what they reported. The two genuinely
#: differ — "my box arrived damaged" (type) and "just credit me" (resolution) is a different job from
#: the same damage with "send another one", and an agent who has to infer it guesses wrong. Narvar
#: Shield and the NetSuite claim flows both capture the ask up front for exactly this reason.
#:
#: ``max_length=16`` against a 11-char longest value (``information``).
REQUESTED_RESOLUTION_CHOICES = [
    ("information", "Information only"),
    ("redeliver", "Redeliver"),
    ("replace", "Replacement"),
    ("credit", "Credit note"),
    ("return", "Return / collection"),
    ("callback", "Call me back"),
]

#: How it actually ended. **``editable=False`` and written ONLY by the workflow verbs**
#: (``resolve`` / ``reopen`` / ``link_return``) — an outcome a user can pick out of a dropdown is a
#: label, not an outcome, and the verbs are what also stamp ``resolved_at`` and write the audit row.
#:
#: ``duplicate`` is deliberately present: without it, closing the third copy of the same WISMO looks
#: identical to actually answering one, and the deflection numbers become fiction.
#:
#: ``max_length=24`` against two 20-char values (``information_provided``, ``replacement_arranged``).
INQUIRY_OUTCOME_CHOICES = [
    ("open", "Open"),
    ("information_provided", "Information provided"),
    ("credit_drafted", "Credit drafted"),
    ("rma_raised", "RMA raised"),
    ("replacement_arranged", "Replacement arranged"),
    ("rejected", "Rejected"),
    ("duplicate", "Duplicate"),
]

#: ``open`` is AMBER, not red — unlike ``TemperatureExcursion``, an open inquiry is the *normal*
#: state of a row a minute after it was filed, and a list that is red by default trains the reader to
#: ignore red. Urgency here is carried by the separate SLA badge, which is computed from
#: ``case.first_response_due`` / ``case.resolution_due`` — **4.16 recomputes no SLA of its own.**
INQUIRY_OUTCOME_CSS = {
    "open": "badge-amber",
    "information_provided": "badge-green",
    "credit_drafted": "badge-info",
    "rma_raised": "badge-info",
    "replacement_arranged": "badge-info",
    "rejected": "badge-red",
    "duplicate": "badge-muted",
}

#: Who filed it. **``editable=False`` and forced server-side by whichever view wrote the row** — the
#: reason ``MeterReading.source`` stopped being a form field (``AssetManagement/_choices.py``): a
#: provenance a user can type is not a provenance, and this figure is the denominator of every
#: self-service / deflection claim the module makes.
INQUIRY_SOURCE_CHOICES = [
    ("portal", "Customer portal"),
    ("staff", "Raised by staff"),
]


# --------------------------------------------------------------------------------------------
# PortalDocumentShare — what this account may retrieve
# --------------------------------------------------------------------------------------------

#: What kind of document is being shared. Each value has exactly one legal target column — see
#: :data:`SHARE_DOC_TYPE_FIELDS` immediately below.
#:
#: ``max_length=20`` against a 14-char longest value (``trade_document``).
SHARE_DOC_TYPE_CHOICES = [
    ("invoice", "Invoice"),
    ("pod", "Proof of delivery"),
    ("packing_list", "Packing list"),
    ("trade_document", "Trade document"),
    ("contract", "Contract"),
    ("coa", "Certificate of analysis"),
    ("statement", "Statement"),
    ("other", "Other document"),
]

#: Colour groups by **what question the document answers** — money (amber), proof that we delivered
#: or that the goods conformed (green), shipping paperwork (info), legal (slate) — and NOT by
#: severity, because a document type has no severity. Grouping is the only thing colour can honestly
#: carry here, so that is what it carries.
SHARE_DOC_TYPE_CSS = {
    "invoice": "badge-amber",
    "pod": "badge-green",
    "packing_list": "badge-info",
    "trade_document": "badge-info",
    "contract": "badge-slate",
    "coa": "badge-green",
    "statement": "badge-amber",
    "other": "badge-muted",
}

#: ``doc_type`` -> the single ``PortalDocumentShare`` pointer column that must be set for it.
#: ``clean()`` walks this so "exactly one pointer, and it is the one this type means" is
#: **table-driven** rather than an eight-branch if-chain that drifts the day a ninth type is added —
#: the ``SCOPE_FIELDS`` precedent (``SupplyChainAnalytics/_choices.py``).
#:
#: Two types share a target on purpose: a packing list IS a ``scm.TradeDocument`` in this codebase
#: (4.12 already types BoL / commercial invoice / packing list), and ``statement`` / ``other`` are
#: both an uploaded ``core.Document``. ``coa`` points at ``scm.QualityInspection`` because 4.9
#: explicitly deferred the customer-facing CoA to 4.16 and its report page already exists;
#: ``contract`` points at **``crm.ContractDocument`` — the CUSTOMER-side contract, never
#: ``scm.SupplierContract``, which is supplier-side commercial data and must never reach a customer.**
SHARE_DOC_TYPE_FIELDS = {
    "invoice": "invoice",
    "pod": "shipment",
    "packing_list": "trade_document",
    "trade_document": "trade_document",
    "contract": "contract",
    "coa": "quality_inspection",
    "statement": "document",
    "other": "document",
}

#: The six pointer columns, deduplicated in declaration order. **Derived from the map above rather
#: than restated**, so the "exactly one of these is set" check and the "and it is the right one for
#: this type" check can never come to disagree about how many pointers there are.
SHARE_POINTER_FIELDS = tuple(dict.fromkeys(SHARE_DOC_TYPE_FIELDS.values()))

#: Ceiling on how far out ``PortalDocumentShare.expires_at`` may be set, in days.
#:
#: ``expires_at`` exists to fix 4.10's documented residual risk — *"the token never expires, cannot be
#: rotated and cannot be revoked… a forwarded link is permanent read access"*
#: (``ReturnsManagement/Reports.py``). A share dated 2099 is that same defect wearing a date, and a
#: mistyped year produces one by accident rather than by intent. One year is long enough for every
#: real case (an annual statement, a contract the customer re-reads) and short enough that a
#: forwarded link eventually dies on its own. Enforced in ``clean()`` alongside the
#: "must be in the future on create" rule, so the form, the seeder and any future verb inherit it.
MAX_SHARE_EXPIRY_DAYS = 365


# --------------------------------------------------------------------------------------------
# PortalActivity — the append-only evidence trail
# --------------------------------------------------------------------------------------------

#: What the customer did. This vocabulary exists because ``core.AuditLog.ACTION_CHOICES`` is
#: ``create``/``update``/``delete`` **only** — it records *changes to records by staff*, and cannot
#: express *a read by a customer*. Bending it would corrupt an existing audit surface, so 4.16 keeps
#: its own log and staff CRUD keeps going through ``write_audit_log`` unchanged.
#:
#: The set is closed and small on purpose: it is the input to "did they ever log in?", to any
#: deflection metric, and to "we published that POD on the 3rd and they downloaded it on the 4th",
#: which is the sentence the whole table exists to make defensible.
#:
#: ``max_length=20`` against a 17-char longest value (``download_document``).
PORTAL_ACTION_CHOICES = [
    ("login", "Signed in"),
    ("view_order", "Viewed an order"),
    ("track_shipment", "Tracked a shipment"),
    ("view_catalog", "Browsed the catalog"),
    ("download_document", "Downloaded a document"),
    ("raise_inquiry", "Raised an inquiry"),
    ("request_return", "Requested a return"),
    ("update_profile", "Updated their profile"),
]

#: Reads are neutral, writes are green (something changed because the customer acted), and
#: ``download_document`` is amber on its own — it is the one action where **data leaves the
#: building**, and it is the row a dispute turns on. That is a scanning aid on a long log, not a
#: warning.
PORTAL_ACTION_CSS = {
    "login": "badge-slate",
    "view_order": "badge-info",
    "track_shipment": "badge-info",
    "view_catalog": "badge-muted",
    "download_document": "badge-amber",
    "raise_inquiry": "badge-green",
    "request_return": "badge-green",
    "update_profile": "badge-green",
}


# --------------------------------------------------------------------------------------------
# The customer-facing status vocabulary
# --------------------------------------------------------------------------------------------

#: ``crm.Case.status`` -> ``(customer-facing label, badge class)``.
#:
#: **This is a PRESENTATION MAP, not a model vocabulary and not a column.** No field anywhere uses it
#: as ``choices``; ``PortalOrderInquiry.customer_status`` reads it and returns the pair. Zendesk
#: documents outright that its portal ticket statuses are not its agent statuses, and Narvar does the
#: same for parcels — the internal queue's words are an internal matter.
#:
#: The three agent triage states ``new`` / ``open`` / ``in_progress`` deliberately collapse to ONE
#: customer word. Which of them a ticket sits in is a fact about *our* queue, and a customer reading
#: "New" on a four-day-old ticket reads it as "nobody has looked at this yet" — which may even be
#: true, and is still not something a status badge should be volunteering. ``waiting`` is the only
#: state where the CUSTOMER must act, so it is the only amber one: the badge is a call to action.
#:
#: **Keyed on the real values of ``crm.Case.STATUS_CHOICES``**, read off
#: ``apps/crm/models/CustomerService/Cases.py`` at write time — all six are present, so a plain
#: subscript is total today. A key that does not exist in CRM would be a silent hole (the branch
#: simply never fires and nobody sees an error), so a caller that wants to survive CRM adding a
#: seventh status should use ``CUSTOMER_STATUS_MAP.get(case.status, CUSTOMER_STATUS_MAP["open"])``
#: and never invent a label inline.
CUSTOMER_STATUS_MAP = {
    "new": ("In progress", "badge-info"),
    "open": ("In progress", "badge-info"),
    "in_progress": ("In progress", "badge-info"),
    "waiting": ("Awaiting your reply", "badge-amber"),
    "resolved": ("Solved", "badge-green"),
    "closed": ("Closed", "badge-muted"),
}
