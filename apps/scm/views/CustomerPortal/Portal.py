"""SCM 4.16 Customer Portal — the GATED CUSTOMER SURFACE, and the one public token route.

Everything in this module is read by a **customer**, not by staff. That single sentence is what
makes it the security-critical file of the sub-module: every other 4.16 view answers "what did we
configure?", and these eight answer "what may this person see?". The whole file is therefore written
around one rule — **nothing is ever scoped by what a URL, a form or a template said; it is scoped by
who the signed-in user resolved to.**

--------------------------------------------------------------------------------------------------
IDENTITY — resolved ONCE, by a shared helper, and never re-derived
--------------------------------------------------------------------------------------------------
Every view here opens with :func:`apps.scm.views._helpers._portal_account`, which walks
``user -> crm.CustomerPortalAccess (active) -> customer_party -> scm.PortalAccount (active)`` and
**refuses at each step with a message + redirect** rather than falling through. It returns a
``(portal, refusal)`` pair and the caller's first three lines are always::

    portal, refusal = _portal_account(request)
    if refusal is not None:
        return refusal

The refusal is built inside the helper, not here, so a page cannot half-refuse — flash a message and
then carry on with an unscoped queryset. The reason that matters is written out in the helper's own
docstring and comes from ``apps/crm/views/CustomerService/CustomerPortal.py``: *a party of ``None``
turns "this customer's own orders" into a filter on NULL, which for an OR-composed or nullable-FK
lookup is not "nothing" — it is "everybody's".*

**A successful resolve answers WHO, never MAY-THEY-SEE-THIS.** The six entitlement booleans on
``PortalAccount`` are each page's own gate, applied through :func:`_gate` below, and the gate is
applied BEFORE any queryset is built — an entitlement checked after the data is fetched is a
template-level secret, not an access control.

--------------------------------------------------------------------------------------------------
WHAT IS DELIBERATELY NOT HERE (§4 of the plan — decisions, not omissions)
--------------------------------------------------------------------------------------------------
* **No second thread page.** The inquiry conversation is ``crm:portal_case_detail`` over
  ``crm.CaseComment(is_public=True)``; :func:`portal_inquiry_create` redirects there and there is
  deliberately no ``portal/inquiries/<int:pk>/`` route in scm.
* **No second RMA.** A return request routes to 4.10's existing ``scm:portal_return_create``.
* **No cart, no checkout, no order placement, no price engine.** NetSuite SuiteCommerce MyAccount
  ships a login-only portal with none of them; that is the precedent and the licence to park it.
* **No writes of any kind except the inquiry.** :func:`portal_profile` is READ-ONLY on purpose: a
  customer silently re-pointing their own delivery address is a live fraud vector (it is how a
  compromised login turns into a diverted pallet), so address maintenance stays a staff action with
  a human in it. That is also why ``update_profile`` never appears in this module's activity rows.
* **No AR.** Balances and terms are read from ``accounting.CustomerProfile`` /
  ``accounting.Invoice`` and recomputed nowhere (L29).
* **No ``StockMove`` write.** The catalog reads the ledger; it never posts to it.

--------------------------------------------------------------------------------------------------
THE ACTIVITY TRAIL — which page writes which action, and the two that write none
--------------------------------------------------------------------------------------------------
``PortalActivity.record()`` is the single writer and its vocabulary is CLOSED (it is a committed
column with a shipped migration), so each page is mapped onto a value that is actually TRUE rather
than given a new one::

    portal_home             -> "login"           (once per session — see SESSION_LOGIN_KEY)
    portal_order_list       -> "view_order"      (no pointer: the page is the index, not a document)
    portal_order_detail     -> "track_shipment" when the order has a shipment, else "view_order"
    portal_catalog          -> "view_catalog"
    portal_inquiry_create   -> "raise_inquiry"   (on a SUCCESSFUL submit only)
    portal_document_download-> "download_document"
    portal_documents        -> nothing
    portal_profile          -> nothing

The last two write nothing **deliberately**. ``portal_documents`` is an index; the recordable fact is
the retrieval, and the download view writes it. ``portal_profile`` is read-only, so ``update_profile``
would be a row asserting a change that did not happen. Inventing a ``view_documents`` value would
mean widening a closed vocabulary from a view, which is exactly the corruption
``PortalActivity``'s docstring refuses for ``core.AuditLog``.

``record()`` fails soft by contract — a logging error must never 500 the page the customer was
reading — so no call site here wraps it or checks its return.

--------------------------------------------------------------------------------------------------
EMPTY STATES ARE THE MODAL FIRST SESSION, NOT AN EDGE CASE
--------------------------------------------------------------------------------------------------
A brand-new portal account legitimately has **zero orders, zero shipments, zero documents, zero
inquiries and zero invoices** — that is what every account looks like the day it is switched on. So
no page here assumes a row exists: every aggregate is defaulted, every "latest" lookup is a
``.first()`` whose ``None`` is a real answer, and every derived figure that has no input is passed as
``None`` rather than ``0``. **``None`` and ``0`` are different statements** and the templates render
``None`` as an em-dash: *no ledger row exists for this item* is not *we have none left*, and *no
invoice exists* is not *you owe nothing*. :func:`apps.scm.models.stock_band` encodes the same
distinction and is the only thing allowed to decide a stock word or colour.

--------------------------------------------------------------------------------------------------
CONTEXT-VAR CONTRACT (pinned, L7 — the templates are written by a separate agent, so EVERY key is
listed here, and every list-of-dicts has its EXACT keys spelled out; a template built against a
guessed key renders a grid of em-dashes and still returns 200)
--------------------------------------------------------------------------------------------------
Shared by every page below: ``account`` (the ``PortalAccount``), ``customer`` (its ``core.Party``),
``access`` (the ``crm.CustomerPortalAccess`` row) and the six entitlement booleans
``can_track_shipments`` / ``can_view_invoices`` / ``can_view_documents`` / ``can_raise_inquiries`` /
``can_request_returns`` / ``show_credit_and_balance``.

* ``scm/portal/customer_home.html`` — ``stats`` (dict: ``open_orders`` / ``in_transit`` /
  ``live_documents`` / ``open_inquiries`` / ``outstanding_balance``; every value is an int, or
  ``None`` where the entitlement is off or there is nothing to count), ``recent_orders``
  (list of dicts — see :func:`_order_rows`), ``recent_documents`` (list of dicts — see
  :func:`_share_rows`), ``recent_inquiries`` (``PortalOrderInquiry`` queryset),
  ``welcome_message``, ``support_email``.
* ``scm/portal/customer_orders.html`` — ``object_list`` (list of dicts, :func:`_order_rows`),
  ``page_obj``, ``q``, ``status_choices`` (list of ``(value, label)``), ``status`` (the RESOLVED
  value, ``""`` when absent or junk — bind the select to THIS, not to ``request.GET.status``).
* ``scm/portal/customer_order.html`` — ``obj`` (the ``SalesOrder``), ``lines`` (list of dicts),
  ``shipments`` (list of dicts), ``inquiry_url`` (pre-filled; ``""`` when inquiries are off),
  ``order_inquiries`` (this customer's own ``PortalOrderInquiry`` rows about this order).
* ``scm/portal/customer_documents.html`` — ``object_list`` (list of dicts, :func:`_share_rows`),
  ``page_obj``, ``q``, ``doc_type_choices``, ``doc_type`` (resolved).
* ``scm/portal/customer_catalog.html`` — ``object_list`` (list of dicts), ``page_obj``, ``q``,
  ``item_categories`` (queryset for the pk dropdown — compare with ``|stringformat:"d"``, NEVER
  ``|slugify``), ``category`` (resolved pk as a string), plus the presentation switches
  ``stock_display`` / ``stock_display_label`` / ``show_by_location`` / ``price_basis`` /
  ``catalog_scope`` / ``catalog_scope_label`` / ``show_prices``.
* ``scm/portal/customer_profile.html`` — ``addresses``, ``contacts``, ``default_ship_to``,
  ``invoices`` (list of dicts, ``[]`` when ``can_view_invoices`` is off), ``finance``
  (dict or ``None``).
* ``scm/portal/customer_inquiry_form.html`` — ``form`` + ``is_edit`` (always ``False`` — there is no
  portal edit path), ``kb_articles`` (list of dicts), ``prefill_order``.

**Badges** come from the model properties and the ``_choices`` maps only —
``PortalOrderInquiry.customer_status_css`` / ``inquiry_type_css``, ``PortalDocumentShare``'s
``doc_type_css``, and ``band_css`` on a catalog row. theme.css is COLOUR-named:
``badge-green / badge-red / badge-amber / badge-info / badge-muted / badge-slate``.
``badge-success`` / ``badge-danger`` / ``badge-warning`` **do not exist** and render completely
unstyled (L33). **Everything on these pages is user-typed** — ``welcome_message``, a share ``title``,
an item ``description``, a ``CaseComment`` body — so every template renders escaped and **never**
with ``|safe``.

**Backend package ``CustomerPortal/`` vs template folder ``templates/scm/portal/``** is the house
rule, not a defect: PascalCase of the NavERP.md title for the Python package, the short slug for the
template folder, exactly as all fourteen shipped scm sub-modules do it.
"""
import os
import re

from django.core.exceptions import SuspiciousFileOperation
from django.db.models import Max
from django.http import FileResponse, Http404, HttpResponse
from django.urls import reverse

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _portal_account

from apps.scm.forms import PortalInquiryCustomerForm
# The clamping quantizer every printer of a computed money figure goes through (the LaborStandards
# precedent). q2 CLAMPS as well as quantizes, so an absurd line total degrades to a capped figure on
# the page instead of a DataError-shaped 500 out of the arithmetic.
from apps.scm.models._base import q2
from apps.scm.models import (INQUIRY_TYPE_CHOICES, Item, ItemCategory, Location, PortalActivity,
                             PortalDocumentShare, PortalOrderInquiry, ReorderRule, SalesOrder,
                             SalesOrderLine, SHARE_DOC_TYPE_CHOICES, Shipment, StockMove,
                             STOCK_BAND_CSS, STOCK_BAND_LABELS, stock_band)

ZERO = Decimal("0")

#: Rows per page on the three paginated customer pages. Smaller than the staff default of 15 on
#: purpose: these pages carry a joined row (an order plus its shipment, an item plus its stock band)
#: rather than a flat record, and the per-page aggregates below are sized by this number.
PORTAL_PAGE_SIZE = 12

#: How many tracking events a single shipment may contribute to an order timeline. A GPS-fed
#: shipment can accumulate hundreds of pings (``TrackingEvent.source`` includes ``gps_ping``), and
#: an order with four such shipments would render a page nobody can read out of a query nobody
#: bounded. Newest first, so the cut falls on the oldest events, which are the ones already
#: summarised by the shipment's own status.
MAX_TIMELINE_EVENTS = 40

#: Statuses a customer may see their own order in. **``draft`` is excluded and that is an access
#: decision, not a tidy-up**: a draft order is internal work in progress — quantities and prices are
#: still being negotiated, and 4.5's ``EDITABLE_STATUSES = ("draft",)`` says so — and showing one
#: publishes a commitment nobody has made yet. Derived from the model's own vocabulary rather than
#: hand-listed, so a status added to 4.5 later becomes visible here by default instead of silently
#: dropping the customer's newest orders off their own page.
PORTAL_ORDER_STATUSES = tuple(value for value, _label in SalesOrder.STATUS_CHOICES
                              if value != "draft")

#: Orders that still have something to happen to them — what the home tile counts as "open".
OPEN_ORDER_STATUSES = ("submitted", "on_hold", "allocated", "partially_fulfilled", "fulfilled")

#: Shipment statuses that mean goods are actually moving. ``exception`` is included deliberately: a
#: consignment stuck in customs is very much still in transit from the customer's point of view, and
#: dropping it would make the count on the home page quietly disagree with the rows on the order
#: page it links to.
MOVING_SHIPMENT_STATUSES = ("booked", "in_transit", "exception")

#: Invoices a customer may see. ``draft`` is ours until we send it and ``void`` is a document we
#: withdrew; publishing either would show a customer money we are not asking them for.
CUSTOMER_VISIBLE_INVOICE_STATUSES = ("sent", "partial", "paid")

#: Session key marking that this portal session's ``login`` activity row has been written.
#:
#: **Why a session flag rather than a row per page view.** ``PortalActivity`` is a log and two reads
#: a second apart are genuinely two facts — but "Signed in" is not a read, it is a session boundary,
#: and a row per refresh would make ``PortalAccount.has_never_logged_in`` still correct while making
#: *"when did they last sign in?"* meaningless and costing a write on every page load. The value
#: stored is the account pk, so a user whose portal account changes underneath them is recorded
#: again rather than silently suppressed.
SESSION_LOGIN_KEY = "scm_portal_login_logged"

#: Anything outside this set is replaced in a download filename. ``\w`` (Unicode) is letters, digits
#: and underscore — which excludes every path separator, every control character, ``:``, ``"``, ``;``
#: and ``%``. See :func:`_safe_download_name`.
_UNSAFE_FILENAME = re.compile(r"[^\w.\- ]", flags=re.UNICODE)

#: A file extension we are willing to echo back. Bounded and alphanumeric so a stored name ending in
#: something exotic cannot smuggle anything into the header through the extension.
_SAFE_EXTENSION = re.compile(r"\.[A-Za-z0-9]{1,10}\Z")


# ==================================================================================================
# Shared plumbing
# ==================================================================================================
def _gate(request, account, flag, what):
    """Refuse a page whose entitlement is off. Returns a redirect, or ``None`` to continue.

    Applied BEFORE any queryset is built. An entitlement checked after the data is fetched is a
    template-level secret rather than an access control — the rows are already in memory and one
    forgotten ``{% if %}`` publishes them.

    Redirects to :func:`portal_home`, which carries no gate of its own, so this can never loop.
    The message names the surface but not the reason: whether an administrator turned it off, never
    turned it on, or the workspace does not use it is internal configuration, and the customer's
    remedy is the same sentence in all three cases.
    """
    if getattr(account, flag, False):
        return None
    messages.error(request, f"{what} isn't enabled for your account — contact support.")
    return redirect("scm:portal_home")


def _customer_orders(tenant, party):
    """This customer's own orders, drafts excluded. **The only order queryset in this module.**

    Written once so the ownership term (``customer=party``) and the visibility term
    (``status__in=PORTAL_ORDER_STATUSES``) cannot come apart between the list, the detail, the home
    tiles and the inquiry pre-fill. A second copy that forgot either one is the whole bug class this
    file exists to avoid.
    """
    return (SalesOrder.objects
            .filter(tenant=tenant, customer=party, status__in=PORTAL_ORDER_STATUSES)
            .select_related("currency"))


def _live_shares(tenant, account):
    """The document shares this account may still retrieve — **live evaluated in SQL, not Python**.

    ``PortalDocumentShare.is_live`` is the right thing for a row already in hand, but a page filters
    and then PAGINATES: evaluating liveness after the slice would show a short page (or an empty
    one) while claiming there are more, and evaluating it before the slice in Python would drag the
    whole table into memory. So the same rule is spelled in the query — never revoked, and either no
    expiry or an expiry still in the future.

    ``select_related`` covers all six pointers plus ``trade_document.document`` because the list
    resolves ``target`` and ``file_field`` per row; without it a page of twelve shares is a dozen
    extra round trips for information already joinable.
    """
    return (PortalDocumentShare.objects
            .filter(tenant=tenant, portal_account=account, revoked_at__isnull=True)
            .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
            .select_related("document", "invoice", "shipment", "trade_document",
                            "trade_document__document", "contract", "quality_inspection"))


def _outstanding_balance(tenant, party):
    """What this customer still owes across their open invoices — or ``None`` when there are none.

    **``None``, never ``0``.** A customer with no invoices at all has not been told they owe nothing;
    they have been told nothing, and the template renders that as an em-dash. Collapsing the two
    would print a reassuring "0.00" for an account whose billing was never set up.

    Two aggregates rather than one. A single query annotating ``Sum("total")`` alongside
    ``Sum("allocations__allocated_amount")`` joins the allocation table and multiplies the invoice
    rows, so an invoice paid in two instalments would have its total counted twice — the classic
    fan-out. Summing each side separately is exact.

    ``kind="invoice"`` excludes credit notes: 2.4 stores them in the same table and adding one to an
    outstanding balance would inflate the very figure it should reduce. L29 — SCM computes no AR of
    its own; this reads accounting's documents and totals them.
    """
    from apps.accounting.models import Invoice, PaymentAllocation

    open_invoices = Invoice.objects.filter(
        tenant=tenant, party=party, kind="invoice",
        status__in=Invoice.OPEN_STATUSES)
    # ONE aggregate answers both questions. `exists()` followed by `Sum()` asked the database twice
    # about the same rows; `Count` alongside the `Sum` distinguishes "no invoices at all" (return
    # None -> the page prints an em dash) from "invoices totalling zero" in the same round trip.
    #
    # That distinction is the reason this function returns None rather than ZERO: "you have no
    # invoices" and "you owe nothing" are different statements, and only one of them is a promise.
    # This runs on `portal_home`, the hottest page in the sub-module, and again on `portal_profile`.
    summary = open_invoices.aggregate(n=Count("id"), s=Sum("total"))
    if not summary["n"]:
        return None
    billed = summary["s"] or ZERO
    paid = (PaymentAllocation.objects
            .filter(invoice__in=open_invoices, payment__status="confirmed")
            .aggregate(s=Sum("allocated_amount"))["s"] or ZERO)
    return q2(billed - paid)


def _grouped(qs):
    """Strip a model's default ``Meta.ordering`` before a ``DISTINCT`` or a roll-up.

    Every model this module aggregates over carries one — ``StockMove`` ``["-moved_at", "-id"]``,
    ``ReorderRule`` ``["item__sku"]``, ``PaymentAllocation`` ``["id"]``, ``Item`` ``["sku"]`` — and
    an ordering that survives into an aggregate query is the classic silently-wrong result: the page
    renders happily with the wrong numbers.

    **The two halves of that are NOT equally true on this Django, and the difference is written down
    here rather than assumed.** Verified against Django 5.1 on this tree:

    * ``DISTINCT`` — **still broken by ``Meta.ordering`` today, and this is why the helper exists.**
      ``Item.objects.filter(…).values_list("category_id", flat=True).distinct()`` compiles to
      ``SELECT DISTINCT category_id, sku … ORDER BY sku``: the ordering column is added to the SELECT
      list, so the DISTINCT is over the *pair* and returns one row per ITEM instead of one per
      category. With ``.order_by()`` it is a single column and correct.
    * ``values().annotate()`` — Django stopped folding ``Meta.ordering`` into the ``GROUP BY`` in
      3.1, so ``StockMove.objects.filter(…).values("item_id").annotate(Sum("quantity"))`` already
      groups by ``item_id`` alone here. **An ordering set EXPLICITLY on the queryset is still folded
      in** — ``.order_by("-moved_at").values("item_id").annotate(…)`` groups by
      ``(item_id, moved_at)`` and hands back one row per MOVEMENT — so the trap is one edit away
      from every roll-up below rather than absent from them.

    Applied at both kinds of site, and named rather than inlined, so the rule is visible at the call
    and a future ``.order_by(…)`` added for readability cannot quietly turn an on-hand figure into
    "the last movement" or an invoice balance into "the last part-payment". It also drops a sort the
    database would otherwise perform for a result nobody reads in order.
    """
    return qs.order_by()


def _shipments_by_order(tenant, orders):
    """``{sales_order_id: [Shipment, …]}`` for a whole page of orders in ONE query.

    The alternative — ``order.shipments.first()`` inside the row loop — is a query per row, which is
    the 4.13 ``asset_list`` finding restated on a customer-facing page. Ordered newest first within
    each order so ``[0]`` is the current consignment.
    """
    grouped = {}
    order_ids = [order.pk for order in orders]
    if not order_ids:
        return grouped
    shipments = (Shipment.objects
                 .filter(tenant=tenant, sales_order_id__in=order_ids)
                 .select_related("carrier")
                 .order_by("sales_order_id", "-id"))
    for shipment in shipments:
        grouped.setdefault(shipment.sales_order_id, []).append(shipment)
    return grouped


def _order_rows(tenant, orders):
    """Build the order rows both the list page and the home page render.

    Keys, exactly: ``obj`` (the ``SalesOrder``), ``shipment`` (the latest ``Shipment`` or ``None``),
    ``shipment_count`` (int), ``status_text`` (the carrier's own words from
    ``Shipment.current_status_text``, or ``""``), ``last_known_location`` (str or ``""``), ``eta``
    (datetime or ``None``), ``is_delayed`` (bool), ``pod_received`` (bool), ``pod_received_at``
    (datetime or ``None``), ``tracking_number`` (str or ``""``).

    Every shipment-derived value is ``None``/``""``/``False`` when the order has no shipment yet,
    which is the state EVERY order is in between submission and dispatch — the common case, not an
    edge one.
    """
    grouped = _shipments_by_order(tenant, orders)
    rows = []
    for order in orders:
        shipments = grouped.get(order.pk, [])
        latest = shipments[0] if shipments else None
        rows.append({
            "obj": order,
            "shipment": latest,
            "shipment_count": len(shipments),
            "status_text": (latest.current_status_text if latest else ""),
            "last_known_location": (latest.last_known_location if latest else ""),
            "eta": (latest.eta if latest else None),
            # `is_delayed` is 4.6's own property (past its planned delivery date and still moving) —
            # read, never recomputed, so this page and the shipment list cannot disagree.
            "is_delayed": bool(latest.is_delayed) if latest else False,
            "pod_received": bool(latest.pod_received) if latest else False,
            "pod_received_at": (latest.pod_received_at if latest else None),
            "tracking_number": (latest.carrier_tracking_number if latest else ""),
        })
    return rows


def _share_rows(shares):
    """Build the document rows the documents page and the home page render.

    Keys, exactly: ``obj`` (the ``PortalDocumentShare``), ``download_url`` (str — ``""`` when the row
    somehow has no token), ``has_file`` (bool — ``True`` when bytes will stream, ``False`` when the
    target is a rendered document), ``is_available`` (bool — ``False`` when the pointed-at record has
    since been deleted; every pointer is ``SET_NULL``, so that is a real state rather than a bug).

    **The raw ``public_token`` is deliberately NOT a key.** It is a bearer credential, and the only
    legitimate exposure is the URL it forms — so the URL is built here and the template is never
    handed the value it could print as text next to the link.
    """
    rows = []
    for share in shares:
        token = share.public_token or ""
        rows.append({
            "obj": share,
            "download_url": (reverse("scm:portal_document_download", args=[token])
                             if token else ""),
            "has_file": share.file_field is not None,
            "is_available": share.target is not None,
        })
    return rows


def _resolved_choice(raw, choices):
    """A GET value echoed back only if it is one the page actually offers, else ``""``.

    Bind a filter ``<select>`` to THIS rather than to ``request.GET.<param>``: a hand-edited value
    that narrowed nothing must not be rendered as the selected option, or the page shows a filter
    that did not happen (the 4.14 ``effective`` finding).
    """
    raw = (raw or "").strip()
    return raw if raw in dict(choices) else ""


def _safe_download_name(title, *, fallback, stored_name=""):
    """A ``Content-Disposition`` filename built from the CUSTOMER-FACING title, made safe.

    Three separate problems, all real:

    1. **Header injection.** ``title`` is free text a staff user typed. A CR or LF in it would split
       the response header. :data:`_UNSAFE_FILENAME` keeps only ``\\w``, ``.``, ``-`` and space, so
       no control character, quote or semicolon survives.
    2. **Path traversal.** ``/`` and ``\\`` are gone with the same substitution, and ``..`` is
       collapsed in a loop (a single pass turns ``....`` back into ``..``). Leading and trailing dots
       and spaces are stripped because Windows silently drops them, which would make
       ``report.pdf   `` and ``report.pdf`` the same name.
    3. **A usable file.** The title is what the customer sees and often carries no extension, so the
       STORED name's extension is appended — bounded and alphanumeric, and skipped when the title
       already ends with it. The extension is the only thing ever taken from the storage path; the
       internal filename itself is never rendered, never logged and never used as a fallback (it
       names our conventions, our systems and sometimes our other customers).

    ``fallback`` is the share's own number, so a title made entirely of stripped characters still
    produces a downloadable file rather than a blank name.
    """
    stem = _UNSAFE_FILENAME.sub("_", (title or "").strip())
    while ".." in stem:
        stem = stem.replace("..", "_")
    stem = stem.strip(" .")[:120] or fallback
    extension = os.path.splitext(stored_name or "")[1]
    if not _SAFE_EXTENSION.fullmatch(extension):
        extension = ""
    if extension and stem.lower().endswith(extension.lower()):
        extension = ""
    return f"{stem}{extension}"


# ==================================================================================================
# 1. The landing page
# ==================================================================================================
@login_required
def portal_home(request):
    """The MyAccount landing: purchases · billing · documents · support · catalog.

    **Ungated by design** — this is the page every refusal redirects TO, so a gate here would be a
    loop. Each TILE is gated instead, and the tile's data is not merely hidden but never fetched:
    ``stats["outstanding_balance"]`` stays ``None`` when ``show_credit_and_balance`` is off, so a
    template that forgot its ``{% if %}`` prints an em-dash rather than a figure.

    The ``login`` activity row is written ONCE per session (see :data:`SESSION_LOGIN_KEY`). Writing
    one per page view would keep ``has_never_logged_in`` correct while making "when did they last
    sign in?" unanswerable, and would cost a write on every hit of the most-visited page here.

    Every count is defaulted and every list may be empty: a brand-new account has no orders, no
    shipments, no documents and no inquiries, and that is the modal first session rather than an
    error state.
    """
    portal, refusal = _portal_account(request)
    if refusal is not None:
        return refusal
    account, party = portal.account, portal.party

    if request.session.get(SESSION_LOGIN_KEY) != account.pk:
        PortalActivity.record(account, "login", request=request,
                              object_label=str(party)[:PortalActivity.MAX_LABEL_LENGTH])
        request.session[SESSION_LOGIN_KEY] = account.pk

    orders = _customer_orders(request.tenant, party)

    recent_orders, open_orders, in_transit = [], None, None
    if account.can_track_shipments:
        open_orders = orders.filter(status__in=OPEN_ORDER_STATUSES).count()
        in_transit = Shipment.objects.filter(
            tenant=request.tenant, sales_order__customer=party,
            status__in=MOVING_SHIPMENT_STATUSES).count()
        recent_orders = _order_rows(request.tenant, list(orders.order_by("-order_date", "-id")[:5]))

    recent_documents, live_documents = [], None
    if account.can_view_documents:
        shares = _live_shares(request.tenant, account)
        live_documents = shares.count()
        recent_documents = _share_rows(list(shares.order_by("-created_at", "-id")[:5]))

    # Inquiries are shown whether or not the customer may raise NEW ones: `can_raise_inquiries`
    # governs filing, and hiding the history of tickets they already have would be a different
    # (and worse) rule than the one the entitlement states.
    inquiries = (PortalOrderInquiry.objects
                 .filter(tenant=request.tenant, portal_account=account)
                 .select_related("case", "sales_order"))

    return render(request, "scm/portal/customer_home.html", {
        "account": account,
        "customer": party,
        "access": portal.access,
        "can_track_shipments": account.can_track_shipments,
        "can_view_invoices": account.can_view_invoices,
        "can_view_documents": account.can_view_documents,
        "can_raise_inquiries": account.can_raise_inquiries,
        "can_request_returns": account.can_request_returns,
        "show_credit_and_balance": account.show_credit_and_balance,
        "stats": {
            "open_orders": open_orders,
            "in_transit": in_transit,
            "live_documents": live_documents,
            "open_inquiries": inquiries.filter(outcome="open").count(),
            "outstanding_balance": (_outstanding_balance(request.tenant, party)
                                    if account.show_credit_and_balance else None),
        },
        "recent_orders": recent_orders,
        "recent_documents": recent_documents,
        "recent_inquiries": inquiries.order_by("-created_at", "-id")[:5],
        # Both are staff-authored free text and are rendered ESCAPED — never with `|safe`.
        "welcome_message": account.welcome_message,
        "support_email": account.support_email,
    })


# ==================================================================================================
# 2. Orders and tracking
# ==================================================================================================
@login_required
def portal_order_list(request):
    """This customer's own orders, each row carrying where its goods actually are.

    Gated on ``can_track_shipments``. The ownership term comes from :func:`_customer_orders` and is
    never widened by a GET parameter — there is deliberately no ``?customer=`` on this page, because
    the only customer it can ever show is the one the session resolved to.

    **``notes`` is neither searched nor rendered.** ``SalesOrder.notes`` is a plain staff-editable
    field that routinely carries internal commentary ("chase credit control", "difficult delivery"),
    and a customer-facing search that matched on it would leak by relevance ranking alone.

    L11 is satisfied without an int filter of its own: ``status`` is resolved against the offered
    vocabulary by :func:`_resolved_choice`, so ``?status=abc`` narrows nothing instead of rendering
    an empty page that claims a filter was applied.
    """
    portal, refusal = _portal_account(request)
    if refusal is not None:
        return refusal
    account, party = portal.account, portal.party
    denied = _gate(request, account, "can_track_shipments", "Order tracking")
    if denied is not None:
        return denied

    qs = _customer_orders(request.tenant, party)

    q = (request.GET.get("q") or "").strip()
    if q:
        # distinct(): the line joins fan out one order into one row per matching line.
        qs = qs.filter(Q(number__icontains=q)
                       | Q(lines__item__sku__icontains=q)
                       | Q(lines__item__name__icontains=q)
                       | Q(lines__description__icontains=q)).distinct()

    status_choices = [(value, label) for value, label in SalesOrder.STATUS_CHOICES
                      if value in PORTAL_ORDER_STATUSES]
    status = _resolved_choice(request.GET.get("status"), status_choices)
    if status:
        qs = qs.filter(status=status)

    # Filters applied BEFORE pagination, always — paginating first and filtering the page would
    # give a page count for a set nobody is looking at.
    page_obj = paginate(request, qs.order_by("-order_date", "-id"), PORTAL_PAGE_SIZE)
    rows = _order_rows(request.tenant, list(page_obj.object_list))

    # No pointer and no label: this page is the INDEX, not a document. `object_label` is blank=True
    # for exactly this shape of row (the same as `login` and `view_catalog`).
    PortalActivity.record(account, "view_order", request=request)

    return render(request, "scm/portal/customer_orders.html", {
        "object_list": rows,
        "page_obj": page_obj,
        "q": q,
        "status_choices": status_choices,
        "status": status,
        "account": account,
        "customer": party,
        "access": portal.access,
        "can_track_shipments": account.can_track_shipments,
        "can_view_invoices": account.can_view_invoices,
        "can_view_documents": account.can_view_documents,
        "can_raise_inquiries": account.can_raise_inquiries,
        "can_request_returns": account.can_request_returns,
        "show_credit_and_balance": account.show_credit_and_balance,
    })


@login_required
def portal_order_detail(request, pk):
    """One order's timeline: lines with allocation and backorder, then every shipment's events.

    **The ownership check is in the LOOKUP.** ``customer=party`` and the status filter sit inside
    ``get_object_or_404``, so another customer's order — and this customer's own draft — answer 404
    rather than 403. A 403 would confirm the row exists, which is a different disclosure from
    "no such order" and one this page has no reason to make.

    Allocated and backordered quantities come from 4.5's ``SalesOrderLine.quantity_allocated()`` /
    ``quantity_backordered()``, which aggregate over ``SalesOrderAllocation`` — **derived, never
    stored**, so the figure cannot go stale against the allocations it describes. That is a query per
    line; the alternative is re-implementing 4.5's definition here, and two definitions of "how much
    of this line is spoken for" is precisely the drift this codebase refuses. Lines per order are
    tens, not thousands.

    The activity row is ``track_shipment`` when the order has a consignment and ``view_order`` when
    it does not, so ONE row per page view says which surface was actually consumed.
    """
    portal, refusal = _portal_account(request)
    if refusal is not None:
        return refusal
    account, party = portal.account, portal.party
    denied = _gate(request, account, "can_track_shipments", "Order tracking")
    if denied is not None:
        return denied

    order = get_object_or_404(
        _customer_orders(request.tenant, party).select_related("ship_to_address"), pk=pk)

    lines = []
    # ONE grouped aggregate for every line, not two per line.
    #
    # `line.quantity_allocated()` is an aggregate, and `line.quantity_backordered()`
    # (`SalesOrders.py`) calls `quantity_allocated()` AGAIN internally — re-deriving from the
    # database the exact figure this loop already holds. A 40-line order cost 80 queries, and the
    # second forty of them asked a question we had just answered.
    #
    # The annotation excludes cancelled allocations, matching `quantity_allocated()` exactly (a
    # cancelled claim releases its hold and stops counting; a released one still counts, because
    # released means "sent to the floor", not "gone"). `SalesOrder.recompute_allocation_status()`
    # and this sub-module's own `Reports.py::_line_figures` both already do it this way and both
    # say why in their docstrings.
    line_qs = (order.lines
               .select_related("item", "item__uom")
               .annotate(_allocated=Sum("allocations__quantity",
                                        filter=~Q(allocations__status="cancelled")))
               .order_by("id"))
    for line in line_qs:
        allocated = line._allocated or ZERO
        remaining = (line.quantity_ordered or ZERO) - allocated
        lines.append({
            "obj": line,
            "sku": (line.item.sku if line.item_id else ""),
            "description": (line.description or (line.item.name if line.item_id else "")),
            "quantity_ordered": line.quantity_ordered,
            "quantity_allocated": allocated,
            "quantity_backordered": remaining if remaining > ZERO else ZERO,
            "unit_price": line.unit_price,
            "line_total": q2(line.line_total),
        })

    shipments = []
    for shipment in (order.shipments.select_related("carrier").order_by("-id")):
        shipments.append({
            "obj": shipment,
            # Sliced: a GPS-fed consignment can carry hundreds of pings (see MAX_TIMELINE_EVENTS).
            "events": list(shipment.events.all()[:MAX_TIMELINE_EVENTS]),
            "status_text": shipment.current_status_text,
            "last_known_location": shipment.last_known_location,
            "eta": shipment.eta,
            "is_delayed": bool(shipment.is_delayed),
            "pod_received": bool(shipment.pod_received),
            "pod_received_at": shipment.pod_received_at,
            "tracking_number": shipment.carrier_tracking_number,
        })

    latest_shipment = shipments[0]["obj"] if shipments else None
    PortalActivity.record(
        account, "track_shipment" if latest_shipment is not None else "view_order",
        request=request, sales_order=order, shipment=latest_shipment,
        object_label=order.number or "")

    # Pre-fills the inquiry form's context instead of making the customer retype what the page
    # already knows. Only offered when they may actually file one — a button the view would refuse
    # is the 4.11 finding.
    inquiry_url = ""
    if account.can_raise_inquiries:
        inquiry_url = f"{reverse('scm:portal_inquiry_create')}?sales_order={order.pk}"

    return render(request, "scm/portal/customer_order.html", {
        "obj": order,
        "lines": lines,
        "shipments": shipments,
        "inquiry_url": inquiry_url,
        # Their own tickets about this order, so the page can say "you already asked about this"
        # rather than inviting a duplicate. The thread itself lives in CRM (§4).
        "order_inquiries": (PortalOrderInquiry.objects
                            .filter(tenant=request.tenant, portal_account=account,
                                    sales_order=order)
                            .select_related("case")
                            .order_by("-created_at", "-id")),
        "account": account,
        "customer": party,
        "access": portal.access,
        "can_track_shipments": account.can_track_shipments,
        "can_view_invoices": account.can_view_invoices,
        "can_view_documents": account.can_view_documents,
        "can_raise_inquiries": account.can_raise_inquiries,
        "can_request_returns": account.can_request_returns,
        "show_credit_and_balance": account.show_credit_and_balance,
    })


# ==================================================================================================
# 3. Documents — the library, and the token route that actually serves the bytes
# ==================================================================================================
@login_required
def portal_documents(request):
    """Only the LIVE shares published to this account, each with its download link.

    Gated on ``can_view_documents``. The queryset is ``portal_account=account`` — a share belongs to
    exactly one audience by construction, so there is no ownership question left for this page to
    get wrong. Expired and revoked rows are dropped in SQL (:func:`_live_shares`) rather than hidden
    by a template flag, so pagination counts what it shows.

    **No activity row.** Listing what was published is not a retrieval; the recordable fact is the
    download, and :func:`portal_document_download` writes it. Adding a ``view_documents`` action
    would mean widening a closed, migrated vocabulary from a view.
    """
    portal, refusal = _portal_account(request)
    if refusal is not None:
        return refusal
    account, party = portal.account, portal.party
    denied = _gate(request, account, "can_view_documents", "Document access")
    if denied is not None:
        return denied

    qs = _live_shares(request.tenant, account)

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(number__icontains=q))
    doc_type = _resolved_choice(request.GET.get("doc_type"), SHARE_DOC_TYPE_CHOICES)
    if doc_type:
        qs = qs.filter(doc_type=doc_type)

    page_obj = paginate(request, qs.order_by("-created_at", "-id"), PORTAL_PAGE_SIZE)

    return render(request, "scm/portal/customer_documents.html", {
        "object_list": _share_rows(list(page_obj.object_list)),
        "page_obj": page_obj,
        "q": q,
        "doc_type_choices": SHARE_DOC_TYPE_CHOICES,
        "doc_type": doc_type,
        "account": account,
        "customer": party,
        "access": portal.access,
        "can_track_shipments": account.can_track_shipments,
        "can_view_invoices": account.can_view_invoices,
        "can_view_documents": account.can_view_documents,
        "can_raise_inquiries": account.can_raise_inquiries,
        "can_request_returns": account.can_request_returns,
        "show_credit_and_balance": account.show_credit_and_balance,
    })


def _target_still_owned(share):
    """Re-answer the authorisation question at DOWNLOAD time: is this still the customer's own doc?

    ``PortalDocumentShare.clean()`` already asks it, but ``full_clean()`` runs from
    ``ModelForm.is_valid()`` and from nothing else — a row created by a shell, a data migration, a
    future API or a bug reaches the token URL having never passed through it. And even a row that
    did pass can go stale: every pointer is ``SET_NULL`` and the chain each check walks
    (``Shipment -> sales_order -> customer``) can be re-pointed after the share was published.
    **Validation that only ran on a form is not an access control.**

    The rule is re-run rather than re-invented: :data:`PortalDocumentShare.OWNER_PATHS` and the
    model's own ``_resolve`` are the same table and the same walker ``clean()`` uses, so the two
    checks cannot come to disagree about where a ``coa``'s owner lives.

    **The ``core.Document`` weakening is reproduced EXACTLY, and not tightened.** A generic
    attachment has no party column, so when its related record names no owner either, tenant is all
    there is. Being stricter here than ``clean()`` would 404 every legitimately-created ``statement``
    and ``other`` share — a page that refuses what the form accepted. Anything stronger needs a party
    FK on ``core.Document``, which is a Module 0 schema change.
    """
    pointer = share.pointer_field
    target = share.target
    if not pointer or target is None:
        return False
    if getattr(target, "tenant_id", None) != share.tenant_id:
        return False
    # A CONFIDENTIAL attachment is refused outright, whatever its ownership says. `classification`
    # is `core.Document`'s own "not for outsiders" flag, and this route is the only place in the
    # codebase that hands a file to someone with no login at all. Checked here as well as in the
    # form (which does not offer one) and `clean()` (which refuses a crafted pk), because this is
    # the boundary that actually serves the bytes — and a share created before this rule existed
    # must stop working now rather than keep resolving.
    if getattr(target, "classification", "") == "confidential":
        return False

    customer_id = share.portal_account.customer_id
    owners = [share._resolve(target, path)
              for path in PortalDocumentShare.OWNER_PATHS.get(pointer, ())]
    owners = [owner for owner in owners if owner is not None]
    if customer_id is not None and customer_id in owners:
        return True
    return pointer == "document" and not owners


# @require_GET, not because anything here writes on POST — the view has no POST branch — but because
# an unauthenticated endpoint should accept exactly the method it is for. A POST reaching a bare
# view is a CSRF-shaped request arriving at a route with no CSRF protection (there is none to have:
# the token IS the credential and there is no session). Refusing the method outright is one fewer
# thing to reason about, and it costs nothing.
@require_GET
def portal_document_download(request, token):
    """Serve a shared document to whoever holds the link. **NO DECORATOR — read this first.**

    There is no ``LoginRequiredMiddleware`` in this project, so a bare view is genuinely public: the
    unguessable ``public_token`` (``secrets.token_urlsafe(32)``, minted once in ``save()``) is the
    bearer credential, exactly as ``returnauthorization_public`` and ``case_public`` work. A
    ``@login_required`` here would break the one thing the token exists for — a link that can be
    mailed to an accounts-payable clerk who has no portal login at all.

    Being public means every scoping assumption a logged-in view may make is unavailable, so each of
    the following is done explicitly:

    1. **The tenant comes OFF THE OBJECT** (``share.tenant``), never ``request.tenant``.
       ``TenantMiddleware`` sets ``request.tenant = None`` for an anonymous visitor, so scoping the
       lookup by it would match nothing — or, worse, be "fixed" later by dropping the term.
    2. **``share.tenant.is_active`` is re-checked** (the ``careers_list`` / ``_public_rma``
       precedent). A churned or suspended workspace must stop serving customer data, and this token
       has no way of knowing the workspace went away.
    3. **The state guard lives IN THE LOOKUP** — ``revoked_at__isnull=True`` inside ``filter()``,
       then an explicit ``expires_at`` test raising ``Http404``. A revoked or expired share is
       therefore **indistinguishable from a wrong token**: it leaks not even its own existence, which
       is the point of revocation. Checking either one after a successful fetch would answer "this
       used to work", which is information.
    4. **``portal_account.is_active`` is re-checked**, so deactivating an account kills its live
       links in one save rather than relying on somebody remembering to revoke each share.
    5. **The target is re-proved to belong to that account's customer** — :func:`_target_still_owned`.
    6. **The bytes are STREAMED through this view.** ``config/urls.py`` serves ``MEDIA_URL``
       directly under ``DEBUG``, so redirecting to ``obj.file.url`` — or rendering ``.url`` into any
       template — would make the token decorative: the underlying ``/media/...`` path answers without
       it. Nothing here exposes ``MEDIA_URL``, and the filename is sanitised
       (:func:`_safe_download_name`) because the title is free text and a header is a line-oriented
       format.

    **The no-file branch is explicit, not an accident.** ``file_field`` returns ``None`` when the
    target is a RENDERED document — an invoice, a contract, a certificate of analysis are printed by
    their own staff pages and ``Shipment`` records POD as ``pod_received`` / ``pod_received_at``,
    which is a fact rather than a scan. 4.16 does not publish a new anonymous renderer for a
    financial document (§4), so the holder is told plainly instead of being handed a 404 that says
    "your link is wrong" when it is not. That branch records **neither** ``record_download()`` **nor**
    an activity row: both are read in a dispute as *"the customer received this document"*, and no
    bytes left the building.

    # WARNING (security): this is an UNAUTHENTICATED GET. Add per-IP rate limiting
    # (django-ratelimit) or a WAF throttle before it faces the internet. **Token enumeration is the
    # attack**, and 32 urlsafe bytes from the CSPRNG is the mitigation for guessing a SPECIFIC
    # token — it is not a substitute for a throttle, because an unthrottled endpoint also lets an
    # attacker measure, flood and mine timing. 4.10 flagged exactly this on its public POST
    # (``apps/scm/views/ReturnsManagement/Reports.py``); there is no rate limiting anywhere in this
    # repo and none is being invented here.
    """
    if not token:
        raise Http404("No such document.")

    share = get_object_or_404(
        PortalDocumentShare.objects.select_related(
            "tenant", "portal_account", "portal_account__customer", "document", "invoice",
            "shipment", "trade_document", "trade_document__document", "contract",
            "quality_inspection"),
        public_token=token, revoked_at__isnull=True)

    # Every refusal below raises the SAME bare 404 on purpose — a message that distinguished
    # "expired" from "revoked" from "wrong workspace" would hand an enumerator a classifier.
    if share.expires_at is not None and share.expires_at <= timezone.now():
        raise Http404("No such document.")
    if not share.tenant.is_active:
        raise Http404("No such document.")
    if not share.portal_account.is_active:
        raise Http404("No such document.")
    # `can_view_documents`, re-checked here for exactly the reason `is_active` is re-checked one
    # line above: turning the switch off has to kill the live links, not merely hide the page that
    # lists them. An admin who unticks it reasonably believes the outstanding links died — and every
    # link already sitting in a customer's inbox stayed live. The entitlement's own help text calls
    # it "the document library", which is the page; the library and its links are one control.
    if not share.portal_account.can_view_documents:
        raise Http404("No such document.")
    if not _target_still_owned(share):
        raise Http404("No such document.")

    file_field = share.file_field
    if file_field is None:
        # Deliberately text/plain: no template, no markup, nothing to escape, and no chance of a
        # future edit reflecting user-typed text into HTML on an unauthenticated endpoint.
        return HttpResponse(
            f"{share.title}\n\n"
            "This document is issued as a printed page rather than a stored file, so there is "
            "nothing to download from this link.\n"
            f"Please contact us and quote {share.number}.\n",
            content_type="text/plain; charset=utf-8")

    try:
        handle = file_field.open("rb")
    except (OSError, ValueError, SuspiciousFileOperation):
        # The row is valid; the bytes are not. 404 rather than a 500 — and rather than a message
        # naming a storage path, which is the one thing this module never renders.
        #
        # OSError covers the file being gone or unreadable (FileNotFoundError is a subclass);
        # ValueError is an empty FileField that slipped past `file_field`'s own `or None`;
        # SuspiciousFileOperation is what the storage backend raises when a stored `name` resolves
        # outside MEDIA_ROOT — a hand-edited row, and an uncaught 500 on an ANONYMOUS endpoint if it
        # is not named here.
        raise Http404("No such document.")

    filename = _safe_download_name(share.title, fallback=share.number or "document",
                                   stored_name=getattr(file_field, "name", ""))

    # Recorded only now, once the file is genuinely open and about to stream. Both are quoted in a
    # dispute, so neither may fire for a retrieval that failed.
    #
    # AND ONLY FOR A REAL NAVIGATION. This endpoint is unauthenticated and writes into the one table
    # whose whole value is being believable, so anyone who has ever held a token could otherwise
    # forge a record: `<img src="https://erp.example/scm/portal-documents/<token>/">` on any page
    # the customer visits makes their browser fetch it, and `record()` falls back to `request.user`,
    # so the row would name that customer and their IP. A download they never made, in the log we
    # would quote at them.
    #
    # `Sec-Fetch-Dest` is set by the browser and cannot be overridden by page script: a genuine
    # navigation or link click sends `document`, an `<img>`/`<script>`/`<iframe>` sends
    # `image`/`script`/`iframe`. Absent (older browsers, curl) defaults to `document` — this decides
    # whether to WRITE EVIDENCE, not whether to serve, so the failure we choose on an unknown client
    # is to record it. The bytes are served either way; suppressing the row is not access control
    # and must not be mistaken for it.
    if request.headers.get("Sec-Fetch-Dest", "document") == "document":
        share.record_download()
        # `user=None` for the anonymous case; `record()` still picks up `request.user` when the
        # holder happens to be signed in, which is the honest attribution either way. The IP comes
        # from REMOTE_ADDR inside `record()` and from no forwarding header — see the field's comment.
        PortalActivity.record(share.portal_account, "download_document", request=request, user=None,
                              document_share=share, shipment=share.shipment,
                              object_label=share.number or "")

    return FileResponse(handle, as_attachment=True, filename=filename)


# ==================================================================================================
# 4. Raising an inquiry
# ==================================================================================================
def _kb_articles(tenant):
    """Published, externally-visible knowledge-base articles with their PUBLIC urls, newest first.

    The deflection block Zendesk and Salesforce both put above a "contact us" form: a customer who
    finds the answer costs nobody a ticket. ``KnowledgeArticle.is_public`` is
    ``status == "published" and visibility == "external"`` — spelled out in the filter because a
    Python property cannot narrow a queryset, and getting either half wrong publishes internal
    articles to customers.

    Keys, exactly: ``title`` (str) and ``url`` (str). The article's own ``public_token`` is turned
    into a URL here for the same reason a share's is — a template is never handed a credential it
    could print.

    Local CRM import: scm does not import crm at module scope (the ``ReturnsManagement/Reports.py``
    precedent). Returns ``[]`` for a workspace with no KB, which is most of them at first.
    """
    from apps.crm.models import KnowledgeArticle
    articles = (KnowledgeArticle.objects
                .filter(tenant=tenant, status="published", visibility="external")
                .exclude(public_token__isnull=True)
                .order_by("-updated_at", "-id")[:5])
    return [{"title": article.title,
             "url": reverse("crm:kb_public", args=[article.public_token])}
            for article in articles]


@login_required
def portal_inquiry_create(request):
    """The customer files an order-context inquiry. ``PortalInquiryCustomerForm`` + ``open_for()``.

    Gated on ``can_raise_inquiries``.

    **Three things are forced server-side and cannot be named by the POST**: the ``portal_account``
    (resolved from the session — the customer form has no such field at all), ``source="portal"``
    and the actor. ``open_for()`` is the SINGLE writer of the ``crm.Case``: it derives the case type
    from the inquiry type, forces ``origin="portal"``, sets ``account`` to the resolved party and
    resolves the tenant's default SLA policy, all inside one ``transaction.atomic()`` so a rejected
    submission cannot leave an orphaned ticket in the CRM queue.

    ``**context`` is built from ``PortalOrderInquiry.CONTEXT_FIELDS`` intersected with what the form
    actually cleaned, never from ``request.POST``. That is what makes the model's whitelist
    load-bearing rather than decorative: ``outcome``, ``return_authorization`` and ``case`` are
    unreachable from here by construction, not by inspection.

    ``open_for()`` runs ``full_clean()``, so the model's own rules (a WISMO needs an order, a line
    must belong to that order, a claimed quantity may not exceed what was sold) surface as field
    errors on the form. A rule keyed on a field the CUSTOMER form does not carry — ``invoice``, which
    only staff may attach — is re-homed to the form's non-field errors, because
    ``add_error("invoice", …)`` on a form without that field raises ``ValueError`` and turns a
    validation message into a 500.

    The audit row is written by hand: ``crud_create`` is not on this path (the case and the inquiry
    must commit together), and a create with no trail is the gap that line exists to close.
    """
    portal, refusal = _portal_account(request)
    if refusal is not None:
        return refusal
    account, party = portal.account, portal.party
    denied = _gate(request, account, "can_raise_inquiries", "Raising an inquiry")
    if denied is not None:
        return denied

    # Pre-fill from the order page's "Raise an inquiry about this order" button. Each value is
    # re-resolved against THIS customer's own rows: an initial is only a default, and the form's
    # querysets would reject a foreign pk anyway, but showing a blank picker after the customer
    # clicked a specific order is a bug they cannot diagnose.
    initial, prefill_order = {}, None
    order_pk = as_db_int(request.GET.get("sales_order"))
    if order_pk is not None:
        prefill_order = _customer_orders(request.tenant, party).filter(pk=order_pk).first()
        if prefill_order is not None:
            initial["sales_order"] = prefill_order.pk
    shipment_pk = as_db_int(request.GET.get("shipment"))
    if shipment_pk is not None:
        shipment = Shipment.objects.filter(tenant=request.tenant, pk=shipment_pk,
                                           sales_order__customer=party).first()
        if shipment is not None:
            initial["shipment"] = shipment.pk
    inquiry_type = _resolved_choice(request.GET.get("inquiry_type"), INQUIRY_TYPE_CHOICES)
    if inquiry_type:
        initial["inquiry_type"] = inquiry_type

    form = PortalInquiryCustomerForm(tenant=request.tenant, customer=party, initial=initial)
    if request.method == "POST":
        form = PortalInquiryCustomerForm(request.POST, tenant=request.tenant, customer=party)
        if form.is_valid():
            context = {name: form.cleaned_data[name]
                       for name in PortalOrderInquiry.CONTEXT_FIELDS
                       if name in form.cleaned_data}
            try:
                inquiry = PortalOrderInquiry.open_for(
                    tenant=request.tenant,
                    portal_account=account,
                    subject=form.cleaned_data["subject"],
                    description=form.cleaned_data["description"],
                    user=request.user,
                    source="portal",
                    **context)
            except ValidationError as exc:
                errors = (exc.message_dict if hasattr(exc, "error_dict")
                          else {"__all__": exc.messages})
                for field, messages_for_field in errors.items():
                    form.add_error(field if field in form.fields else None, messages_for_field)
            else:
                write_audit_log(request.user, inquiry, "create",
                                {"via": "customer_portal", "source": "portal",
                                 "case": getattr(inquiry.case, "number", "") or "",
                                 "inquiry_type": inquiry.inquiry_type})
                PortalActivity.record(account, "raise_inquiry", request=request,
                                      sales_order=inquiry.sales_order, shipment=inquiry.shipment,
                                      object_label=inquiry.number or "")
                messages.success(
                    request, f"Inquiry {inquiry.number} raised — we'll reply on this ticket.")
                # §4: there is no second thread page. The conversation continues on CRM's existing
                # portal case detail, which scopes itself to this same party.
                return redirect("crm:portal_case_detail", pk=inquiry.case_id)

    return render(request, "scm/portal/customer_inquiry_form.html", {
        "form": form,
        # Always False: the portal files inquiries and never edits them. Triage lives with staff,
        # and the customer's own words continue in the case thread.
        "is_edit": False,
        "kb_articles": _kb_articles(request.tenant),
        "prefill_order": prefill_order,
        "account": account,
        "customer": party,
        "access": portal.access,
        "can_track_shipments": account.can_track_shipments,
        "can_view_invoices": account.can_view_invoices,
        "can_view_documents": account.can_view_documents,
        "can_raise_inquiries": account.can_raise_inquiries,
        "can_request_returns": account.can_request_returns,
        "show_credit_and_balance": account.show_credit_and_balance,
    })


# ==================================================================================================
# 5. The catalog
# ==================================================================================================
def _scoped_catalog(tenant, account):
    """The items this account's catalog contains, per ``PortalAccount.catalog_scope``.

    * ``all_active`` — every active item.
    * ``previously_ordered`` — derived from the customer's own order history, drafts excluded so an
      item that only ever appeared on an unsent draft is not presented as something they bought.
    * ``categories`` — the account's selected categories. **An account scoped to categories with
      none selected sees NOTHING, and that is deliberate**: the form requires at least one on
      create and edit, so an empty set can only be a legacy or hand-made row, and failing closed on
      a catalog-scoping rule is the only safe direction.
    """
    items = Item.objects.filter(tenant=tenant, is_active=True).select_related("category", "uom")
    if account.catalog_scope == "previously_ordered":
        return items.filter(
            sales_order_lines__sales_order__customer=account.customer,
            sales_order_lines__sales_order__status__in=PORTAL_ORDER_STATUSES).distinct()
    if account.catalog_scope == "categories":
        return items.filter(category__in=account.catalog_categories.all()).distinct()
    return items


def _stock_for_page(tenant, item_ids, *, by_location):
    """On-hand for a whole page of items in ONE grouped query over the append-only ledger.

    ``Item.on_hand()`` is the correct answer for a single item and the wrong tool for a list: it is
    an aggregate per call, so a page of twelve items would be twelve round trips, plus twelve more
    if the account also wants a per-warehouse split (the 4.13 ``asset_list`` finding).

    Returns ``(totals, per_location)``: ``totals`` maps ``item_id -> Decimal``; ``per_location`` maps
    ``item_id -> [(location_id, Decimal), …]`` and is empty unless ``by_location``.

    **An item with no ledger rows is ABSENT from the mapping, not zero.** ``stock_band(None)``
    returns ``None`` and the page renders an em-dash: *nobody has ever counted this* is a different
    statement from *we have none left*, and collapsing them tells a customer an item is unavailable
    when the truth is that it was never stocked here.
    """
    totals, per_location = {}, {}
    if not item_ids:
        return totals, per_location
    # _grouped(): drops StockMove's ["-moved_at", "-id"] before the roll-up. Django 5.1 no longer
    # folds Meta.ordering into the GROUP BY, so this is defensive here — but an explicit .order_by()
    # added to this line later WOULD be folded in, and the result would be one row per MOVEMENT
    # rendered as an on-hand quantity. It also saves a sort of a result nobody reads in order.
    moves = _grouped(StockMove.objects.filter(tenant=tenant, item_id__in=item_ids))
    if by_location:
        for row in moves.values("item_id", "location_id").annotate(qty=Sum("quantity")):
            per_location.setdefault(row["item_id"], []).append((row["location_id"], row["qty"]))
            totals[row["item_id"]] = (totals.get(row["item_id"]) or ZERO) + (row["qty"] or ZERO)
    else:
        for row in moves.values("item_id").annotate(qty=Sum("quantity")):
            totals[row["item_id"]] = row["qty"]
    return totals, per_location


def _last_ordered_prices(tenant, party, item_ids):
    """``{item_id: unit_price}`` — this customer's own most recent price for each item.

    The documented GAP made honest: there is no customer price list on the SCM side (a real price
    engine is 9.3), so the only price we can state truthfully is the one this customer themselves
    last paid. **Derived at render time and never stored** — a stored copy would quietly become a
    quote we never agreed to.

    One query, walked newest-first per item and kept on first sight, because a grouped ``Max`` would
    give the highest price rather than the latest one — a subtle and expensive difference on a page
    a customer reads as an offer. Drafts are excluded for the same reason as everywhere else here.
    """
    prices = {}
    if not item_ids:
        return prices
    rows = (SalesOrderLine.objects
            .filter(sales_order__tenant=tenant, sales_order__customer=party,
                    sales_order__status__in=PORTAL_ORDER_STATUSES, item_id__in=item_ids)
            .order_by("item_id", "-sales_order__order_date", "-sales_order_id", "-id")
            .values("item_id", "unit_price"))
    for row in rows:
        prices.setdefault(row["item_id"], row["unit_price"])
    return prices


@login_required
def portal_catalog(request):
    """What this customer may browse, priced and stocked exactly as their account is configured.

    **Ungated by an entitlement** — there is no ``can_view_catalog`` flag; a portal account IS a
    catalog account, and what varies is the projection, not the permission. The three settings that
    shape it are ``catalog_scope`` (which items), ``stock_display`` (how much of the live figure) and
    ``price_basis`` (a price, or none).

    **``stock_display`` is enforced by what the view PASSES, not by a template ``{% if %}``.** When
    it is ``hidden`` the row carries no quantity, no band and no per-location split at all; when it
    is ``availability_text`` or ``band`` it carries the bucket but NOT the number. A template cannot
    leak a figure it was never given, and the reason to hide the figure is commercial — a competitor
    buying one pallet must not be able to read our whole position.

    The words and colours come from ``STOCK_BAND_LABELS`` / ``STOCK_BAND_CSS`` and the bucket from
    ``stock_band(on_hand, threshold)``. Nothing here invents a label or a class. ``band_label`` is
    passed even for the colour-band display because a colour-only chip is invisible to a screen
    reader and to the ~8% of men with a red/green deficiency — the template renders it as
    ``title``/``aria-label``.

    Row keys, exactly: ``obj`` (the ``Item``), ``on_hand`` (Decimal or ``None`` — populated ONLY for
    the exact-quantity display), ``band`` (``"out"``/``"low"``/``"in"`` or ``None``), ``band_label``
    (str or ``""``), ``band_css`` (str or ``""``), ``by_location`` (list of dicts with keys
    ``location`` / ``quantity`` / ``band`` / ``band_label`` / ``band_css``; ``[]`` unless
    ``show_by_location`` and the display is not hidden), ``last_price`` (Decimal or ``None``),
    ``replenishment_days`` (int or ``None`` — see below).

    ``replenishment_days`` is offered only for an item that is genuinely out of stock, and it is the
    LONGEST active ``ReorderRule.lead_time_days`` rather than the shortest: it is an estimate the
    template must label a **replenishment estimate, not a promise**, and the conservative end is the
    one that can be kept. ``None`` where no rule exists, which renders as an em-dash rather than as
    a reassuring zero.
    """
    portal, refusal = _portal_account(request)
    if refusal is not None:
        return refusal
    account, party = portal.account, portal.party

    # Built ONCE and derived from twice: the page's rows narrow it further, the dropdown reads it
    # whole. Calling the scoping helper a second time would be a second place for the scope rule to
    # be applied differently.
    scoped = _scoped_catalog(request.tenant, account)

    qs = scoped
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(sku__icontains=q) | Q(name__icontains=q) | Q(description__icontains=q))

    # The dropdown offers only categories that are IN SCOPE for this account — offering one whose
    # items this customer can never see is a filter that always returns nothing. Read off `scoped`
    # rather than `qs` on purpose: narrowing the options by the current search would make the
    # category list flicker as the customer types.
    # _grouped() is LOAD-BEARING here, not defensive: Item.Meta.ordering is ["sku"], and Django adds
    # an ordering column to the SELECT list of a DISTINCT — `SELECT DISTINCT category_id, sku` is
    # distinct over the PAIR, i.e. one row per item. Verified on this tree (Django 5.1).
    category_ids = (_grouped(scoped)
                    .exclude(category__isnull=True)
                    .values_list("category_id", flat=True).distinct())
    item_categories = (ItemCategory.objects
                       .filter(tenant=request.tenant, pk__in=list(category_ids))
                       .order_by("name"))
    # L11: `?category=abc`, `?category=²` and `?category=99999999999999999999` all skip the filter
    # rather than raising out of .filter().
    category_pk = as_db_int(request.GET.get("category"))
    category = ""
    if category_pk is not None:
        qs = qs.filter(category_id=category_pk)
        category = str(category_pk)

    page_obj = paginate(request, qs.order_by("sku", "id"), PORTAL_PAGE_SIZE)
    items = list(page_obj.object_list)
    item_ids = [item.pk for item in items]

    display = account.stock_display
    threshold = account.low_stock_threshold or ZERO
    wants_stock = display != "hidden"
    wants_split = wants_stock and account.show_by_location

    totals, per_location = ({}, {})
    if wants_stock:
        totals, per_location = _stock_for_page(request.tenant, item_ids, by_location=wants_split)

    locations = {}
    if wants_split:
        location_ids = {loc_id for rows in per_location.values() for loc_id, _qty in rows}
        locations = {loc.pk: loc for loc in Location.objects.filter(
            tenant=request.tenant, pk__in=list(location_ids))}

    prices = {}
    show_prices = account.price_basis == "last_ordered"
    if show_prices:
        prices = _last_ordered_prices(request.tenant, party, item_ids)

    lead_times = {}
    if wants_stock:
        # _grouped(): drops ReorderRule's ["item__sku"], which is a JOINED ordering column — the one
        # shape most likely to be re-added by hand for a "nicer" query and the one that would then
        # land in the GROUP BY and give a row per rule instead of the per-item maximum.
        lead_times = dict(_grouped(ReorderRule.objects.filter(
            tenant=request.tenant, item_id__in=item_ids, is_active=True))
            .values_list("item_id")
            .annotate(days=Max("lead_time_days"))
            .values_list("item_id", "days"))

    rows = []
    for item in items:
        on_hand = totals.get(item.pk) if wants_stock else None
        band = stock_band(on_hand, threshold) if wants_stock else None
        split = []
        if wants_split:
            for location_id, quantity in per_location.get(item.pk, []):
                location = locations.get(location_id)
                if location is None:
                    continue
                location_band = stock_band(quantity, threshold)
                split.append({
                    "location": location,
                    # The per-warehouse NUMBER is only shown where the account is allowed the exact
                    # figure; otherwise the split is a list of sites with their own bands.
                    "quantity": quantity if display == "exact_quantity" else None,
                    "band": location_band,
                    "band_label": STOCK_BAND_LABELS.get(location_band, ""),
                    "band_css": STOCK_BAND_CSS.get(location_band, ""),
                })
        rows.append({
            "obj": item,
            # The figure itself leaves the view ONLY for the exact-quantity display.
            "on_hand": on_hand if display == "exact_quantity" else None,
            "band": band,
            "band_label": STOCK_BAND_LABELS.get(band, ""),
            "band_css": STOCK_BAND_CSS.get(band, ""),
            "by_location": split,
            "last_price": prices.get(item.pk) if show_prices else None,
            "replenishment_days": lead_times.get(item.pk) if band == "out" else None,
        })

    PortalActivity.record(account, "view_catalog", request=request)

    return render(request, "scm/portal/customer_catalog.html", {
        "object_list": rows,
        "page_obj": page_obj,
        "q": q,
        "item_categories": item_categories,
        "category": category,
        "stock_display": display,
        "stock_display_label": account.get_stock_display_display(),
        "show_by_location": wants_split,
        "price_basis": account.price_basis,
        "show_prices": show_prices,
        "catalog_scope": account.catalog_scope,
        "catalog_scope_label": account.get_catalog_scope_display(),
        "account": account,
        "customer": party,
        "access": portal.access,
        "can_track_shipments": account.can_track_shipments,
        "can_view_invoices": account.can_view_invoices,
        "can_view_documents": account.can_view_documents,
        "can_raise_inquiries": account.can_raise_inquiries,
        "can_request_returns": account.can_request_returns,
        "show_credit_and_balance": account.show_credit_and_balance,
    })


# ==================================================================================================
# 6. The profile — READ-ONLY
# ==================================================================================================
@login_required
def portal_profile(request):
    """Addresses, contacts and — only where entitled — invoices, terms, credit and balance.

    **The page itself is ungated; its two money blocks are.** ``can_view_invoices`` governs the
    invoice history and ``show_credit_and_balance`` (default ``False`` — financial data is opt-in)
    governs terms, credit limit and outstanding balance. Each block's data is not merely hidden but
    never fetched, so an ungated block in a template cannot render a figure.

    **Read-only, and that is a security decision rather than a scope cut.** Letting a customer
    re-point their own delivery address from a portal session is how a compromised login becomes a
    diverted pallet; address maintenance stays a staff action with a person in it. That is also why
    no ``update_profile`` activity is ever written here.

    ``core.Address`` carries ``kind`` / ``line1`` / ``city`` / ``country`` and **NO postal-code
    field** — already documented at 4.10. No label or template on this page may imply one exists.

    ``invoices`` keys, exactly: ``obj`` (the ``accounting.Invoice``), ``balance_due`` (Decimal),
    ``is_open`` (bool). The balance comes from ONE grouped query over ``PaymentAllocation`` rather
    than ``Invoice.balance_due()`` per row, which is an aggregate per call.

    ``finance`` is a dict or ``None`` (``None`` when the entitlement is off). Its keys, exactly:
    ``has_profile`` (bool — a customer with no ``accounting.CustomerProfile`` is normal, not an
    error), ``credit_limit`` (Decimal or ``None``), ``credit_on_hold`` (bool), ``payment_terms``
    (the ``PaymentTerm`` or ``None``), ``currency`` (the ``Currency`` or ``None``),
    ``outstanding_balance`` (Decimal or ``None`` — ``None`` means *there are no invoices*, never
    *you owe nothing*).
    """
    from apps.accounting.models import CustomerProfile, Invoice, PaymentAllocation

    portal, refusal = _portal_account(request)
    if refusal is not None:
        return refusal
    account, party = portal.account, portal.party

    invoices = []
    if account.can_view_invoices:
        recent = list(Invoice.objects
                      .filter(tenant=request.tenant, party=party,
                              status__in=CUSTOMER_VISIBLE_INVOICE_STATUSES)
                      .select_related("currency", "payment_terms")
                      .order_by("-issue_date", "-id")[:10])
        # _grouped(): drops PaymentAllocation's ["id"] — a UNIQUE column, so if it ever reached the
        # GROUP BY the roll-up would return one row per allocation and an invoice settled in two
        # instalments would show only one of them against its balance.
        paid_by_invoice = dict(
            _grouped(PaymentAllocation.objects.filter(
                invoice_id__in=[inv.pk for inv in recent], payment__status="confirmed"))
            .values_list("invoice_id")
            .annotate(paid=Sum("allocated_amount"))
            .values_list("invoice_id", "paid"))
        invoices = [{
            "obj": invoice,
            "balance_due": q2((invoice.total or ZERO)
                              - (paid_by_invoice.get(invoice.pk) or ZERO)),
            "is_open": invoice.status in Invoice.OPEN_STATUSES,
        } for invoice in recent]

    finance = None
    if account.show_credit_and_balance:
        profile = (CustomerProfile.objects
                   .filter(tenant=request.tenant, party=party)
                   .select_related("payment_terms", "currency").first())
        finance = {
            "has_profile": profile is not None,
            "credit_limit": (profile.credit_limit if profile is not None else None),
            "credit_on_hold": bool(profile.credit_on_hold) if profile is not None else False,
            "payment_terms": (profile.payment_terms if profile is not None else None),
            "currency": (profile.currency if profile is not None else None),
            "outstanding_balance": _outstanding_balance(request.tenant, party),
        }

    return render(request, "scm/portal/customer_profile.html", {
        # Scoped to the resolved party on BOTH terms: core.Address and core.ContactMethod each carry
        # their own tenant FK, so filtering on the party alone would be one re-pointed row away from
        # showing another workspace's contact details.
        "addresses": (party.addresses.filter(tenant=request.tenant).order_by("kind", "id")
                      if party is not None else []),
        "contacts": (party.contact_methods.filter(tenant=request.tenant).order_by("kind", "id")
                     if party is not None else []),
        "default_ship_to": account.default_ship_to,
        "invoices": invoices,
        "finance": finance,
        "account": account,
        "customer": party,
        "access": portal.access,
        "can_track_shipments": account.can_track_shipments,
        "can_view_invoices": account.can_view_invoices,
        "can_view_documents": account.can_view_documents,
        "can_raise_inquiries": account.can_raise_inquiries,
        "can_request_returns": account.can_request_returns,
        "show_credit_and_balance": account.show_credit_and_balance,
    })
