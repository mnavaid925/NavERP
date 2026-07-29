"""SCM 4.10 Returns Management — the computed queues and the three portal surfaces.

Four computed pages (no table of their own — the ``coa_report`` / ``mrp_report`` /
``safety_stock_report`` precedent):

* ``refund_queue``               — Refund Processing. What is credit-bearing and unsettled.
* ``returns_awaiting_disposition`` — what is physically on the bench and off-ledger.
* ``advance_refund_exposure``    — money already returned against goods that have not arrived.
* ``return_portal``              — the STAFF console (L32; see below).

And the three portal surfaces, which are deliberately three DIFFERENT things:

(a) ``portal_return_create`` — ``@login_required``, the CUSTOMER's own request, bound through
    ``crm.CustomerPortalAccess`` exactly as ``portal_case_create`` is. **This is what makes the
    "Return Portal — request returns" bullet honest.** Anonymous request is NOT buildable: nothing
    lets a stranger prove they own a ``SalesOrder``, and ``core.Address`` has kind/line1/city/
    country and NO postal-code field, so Loop's order-number + ZIP lookup would need a Module 0
    change. It is not attempted rather than half-built.

(b) ``returnauthorization_public`` / ``returnauthorization_label`` — **no decorator at all.** There
    is no ``LoginRequiredMiddleware`` in this project, so a bare view is genuinely public (the
    ``case_public`` mechanism). The unguessable ``public_token`` is the bearer credential.

(c) ``return_portal`` — the SIDEBAR bullet, and it points at a STAFF console, never at the token
    page. L32 bars a staff sidebar bullet from pointing at a customer-facing page, and this app
    already applied that ruling at 4.1's "Vendor Portal" (``navigation.py:774-777``).

**Public-surface security, stated rather than assumed:**

* Tenant is taken OFF THE OBJECT (``obj.tenant``), never ``request.tenant`` — ``TenantMiddleware``
  is not bypassed for public routes and sets ``request.tenant = None`` for an anonymous visitor.
* The state guard lives in the LOOKUP (``status__in=PUBLIC_STATUSES``), so a draft or cancelled
  return 404s rather than leaking — the ``kb_public`` pattern.
* ``obj.tenant.is_active`` is re-checked (the ``careers_list`` precedent): otherwise a churned or
  suspended tenant keeps serving customer data forever from a token that never expires.
* CSRF is enforced globally (``CsrfViewMiddleware``; the repo's only exemption is the Stripe
  webhook), so the public form carries ``{% csrf_token %}`` and nothing here exempts it.
* The customer write is a TOCTOU-safe conditional UPDATE, not read-then-save.
* **The LABEL grants MORE than the status page does** — it necessarily prints a warehouse address.
  The two are not equivalent and nobody should later assume they are.
* **Residual risk:** the token never expires, cannot be rotated and cannot be revoked. No token in
  this codebase can. A forwarded link is permanent read access to one RMA.
"""
import datetime

from django.http import Http404

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _date_window, _item_qs, _location_qs
from apps.scm.forms._common import _customer_parties
from apps.scm.models._base import q2
from apps.scm.models import (CREDIT_BEARING_DISPOSITIONS, ReturnAuthorization, ReturnDisposition,
                             ReturnLine, ReturnPolicy, ReturnReason, SalesOrder, select_policy)
from apps.scm.forms import PortalReturnRequestForm, PublicReturnUpdateForm

ZERO = Decimal("0")


# ============================================================= Refund Processing (the bullet)
@login_required
def refund_queue(request):
    """Every return with money owed on it and no credit note yet.

    **The filter SQL and the per-row verdict must agree (§7.5)**, and here they are two expressions
    of one rule. ``ReturnAuthorization.is_settleable`` says: not draft/requested/rejected/cancelled,
    and either a ``credit_only`` return with an approved quantity, or at least one credit-bearing
    disposition row. The two ``Exists`` below encode exactly that — ``quantity_approved`` and
    ``quantity`` both carry ``MinValueValidator``, so "any row > 0" and "the sum > 0" are the same
    question asked two ways.

    **§7.11 — the credit-only trap.** A ``credit_only`` RMA never gets a disposition row, so a
    queue keyed on "has received goods" would drop it silently: perfectly valid work that looks
    abandoned. The first branch of that ``Q`` is the whole reason this page is correct, and there is
    a test asserting a credit-only RMA reaches it.
    """
    has_approved_lines = Exists(
        ReturnLine.objects.filter(return_authorization_id=OuterRef("pk"), quantity_approved__gt=0))
    has_credit_rows = Exists(
        ReturnDisposition.objects.filter(
            return_line__return_authorization_id=OuterRef("pk"),
            disposition__in=CREDIT_BEARING_DISPOSITIONS, quantity__gt=0))

    qs = (ReturnAuthorization.objects
          .filter(tenant=request.tenant, credit_note__isnull=True)
          .exclude(status__in=("draft", "requested", "rejected", "cancelled"))
          .select_related("customer", "sales_order", "policy", "currency")
          .prefetch_related(
              Prefetch("lines", queryset=ReturnLine.objects.select_related("item", "reason")),
              Prefetch("lines__dispositions",
                       queryset=ReturnDisposition.objects.only(
                           "id", "return_line_id", "quantity", "disposition")))
          # §7.3 — `_agg` on both, so neither can shadow a model property on the row.
          .annotate(has_approved_lines_agg=has_approved_lines,
                    has_credit_rows_agg=has_credit_rows)
          .filter(Q(return_type="credit_only", has_approved_lines_agg=True)
                  | Q(has_credit_rows_agg=True))
          .order_by("-requested_on", "-id"))

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(customer__name__icontains=q)
                       | Q(sales_order__number__icontains=q)
                       | Q(counterparty_rma_number__icontains=q))
    # L11: never hand a non-numeric value to an int FK filter — the guard crud_list applies.
    for param, lookup in (("customer", "customer_id"), ("policy", "policy_id")):
        value = (request.GET.get(param) or "").strip()
        if value.isdigit():
            qs = qs.filter(**{lookup: int(value)})
    resolution = (request.GET.get("resolution") or "").strip()
    if resolution:
        qs = qs.filter(resolution=resolution)
    kind = (request.GET.get("return_type") or "").strip()
    if kind:
        qs = qs.filter(return_type=kind)
    qs = _date_window(qs, request.GET, "requested_on")

    page_obj = paginate(request, qs)
    rows, total_owed = [], ZERO
    for rma in page_obj.object_list:
        subtotal, fee, tax, credit = rma.settlement_figures
        total_owed += credit
        rows.append({
            "obj": rma,
            "subtotal": subtotal,
            "fee": fee,
            "tax": tax,
            "credit": credit,
            # A credit note that would total <= 0 can NEVER be posted or paid: invoice_post guards
            # `total > ZERO` and recompute_payment_status only reaches `paid` above zero. The row
            # says so here rather than the action refusing after the click.
            "unpostable": credit <= ZERO,
            "credit_only": rma.return_type == "credit_only",
            "advance_refund": rma.advance_refund,
        })
    return render(request, "scm/returns/refund_queue.html", {
        "rows": rows,
        "page_obj": page_obj,
        "q": q,
        "total_owed": q2(total_owed),
        "resolution_choices": ReturnAuthorization.RESOLUTION_CHOICES,
        "type_choices": ReturnAuthorization.RETURN_TYPE_CHOICES,
        "customers": _customer_parties(request.tenant),
        "policies": ReturnPolicy.objects.filter(tenant=request.tenant).order_by("priority", "name"),
        # Rendered as a standing note on this page. It is Module 2's defect and 4.10 deliberately
        # does not work around it by touching the ledger.
        "accounting_caveat": (
            "accounting.invoice_post does not branch on Invoice.kind, so an ISSUED credit note "
            "currently posts Dr AR / Cr Income rather than the reverse, and while it is 'sent' it "
            "ADDS to the open-exposure figure SCM's own credit hold reads. Drafting here is safe; "
            "issuing is Accounts Receivable's decision."),
    })


# ============================================================= the bench queue
@login_required
def returns_awaiting_disposition(request):
    """What is physically on the returns bench, off-ledger, waiting for a decision.

    This page IS the mitigation for the one honest cost of keeping intake off-ledger: goods on the
    bench are absent from inventory value until they are dispositioned. That trade is deliberate —
    ``Location.LOCATION_TYPES`` has no blocked type and ``Item.on_hand()`` sums every location, so
    an intake receipt would inflate on-hand, ``total_value()``, the valuation report and 4.7's
    reorder inputs tenant-wide. **The answer is this report, not a ledger row.**

    §7.11 again: credit-only returns can never appear here, so they are counted and listed
    separately rather than silently missing.
    """
    qs = (ReturnDisposition.objects
          .filter(tenant=request.tenant, disposition="received_pending")
          .select_related("return_line__return_authorization__customer", "return_line__item__uom",
                          "return_line__reason", "location", "lot_serial__item", "received_by")
          .order_by("received_on", "id"))
    for param, lookup in (("location", "location_id"), ("item", "return_line__item_id")):
        value = (request.GET.get(param) or "").strip()
        if value.isdigit():
            qs = qs.filter(**{lookup: int(value)})
    grade = (request.GET.get("condition_grade") or "").strip()
    if grade:
        qs = qs.filter(condition_grade=grade)
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(return_line__item__sku__icontains=q)
                       | Q(return_line__item__name__icontains=q)
                       | Q(return_line__return_authorization__number__icontains=q)
                       | Q(lot_serial__number__icontains=q))
    qs = _date_window(qs, request.GET, "received_on")

    today = timezone.localdate()
    page_obj = paginate(request, qs)
    rows, bench_value = [], ZERO
    for row in page_obj.object_list:
        line = row.return_line
        # The value that is OFF the books while this row sits here — at the graded write-down, not
        # at what the customer paid.
        value = q2((row.quantity or ZERO) * (row.restock_unit_cost or ZERO))
        bench_value += value
        rows.append({
            "obj": row,
            "line": line,
            "rma": line.return_authorization,
            "age_days": max((today - row.received_on).days, 0) if row.received_on else 0,
            "off_ledger_value": value,
            "suggested": (line.reason.suggested_disposition
                          if line.reason_id and line.reason.suggested_disposition else ""),
            "blocks_restock": bool(line.reason_id and line.reason.blocks_restock),
        })
    aged = ReturnDisposition.objects.filter(
        tenant=request.tenant, disposition="received_pending",
        received_on__lt=today - datetime.timedelta(days=14)).count()
    return render(request, "scm/returns/awaiting_disposition.html", {
        "rows": rows,
        "page_obj": page_obj,
        "q": q,
        "bench_value": q2(bench_value),
        "aged_over_14_days": aged,
        "grade_choices": ReturnDisposition.GRADE_CHOICES,
        "locations": _location_qs(request.tenant),
        "items": _item_qs(request.tenant),
        # §7.11 made visible: real work that structurally cannot appear on a bench queue.
        "credit_only_waiting": (
            ReturnAuthorization.objects
            .filter(tenant=request.tenant, return_type="credit_only", credit_note__isnull=True)
            .exclude(status__in=("draft", "requested", "rejected", "cancelled"))
            .select_related("customer")[:10]),
        "off_ledger_note": (
            "Goods on the returns bench are deliberately OFF the stock ledger until they are "
            "dispositioned: there is no blocked-stock location type, and on-hand sums every "
            "location, so posting them at intake would inflate on-hand, inventory value and the "
            "reorder calculations tenant-wide. This page is how that stock stays visible."),
    })


# ============================================================= advance-refund exposure
@login_required
def advance_refund_exposure(request):
    """Money already given back against goods that have not arrived.

    There is no payment gateway and no card hold in this repo, so instant/advance refunds ship as
    a FLAG, a DEADLINE and this report. The claw-back is a manual credit-note reversal in
    Accounting — stated, not silently missing.
    """
    today = timezone.localdate()
    qs = (ReturnAuthorization.objects
          .filter(tenant=request.tenant, advance_refund=True)
          .exclude(status__in=("rejected", "cancelled", "closed"))
          .select_related("customer", "sales_order", "policy", "currency", "credit_note")
          .prefetch_related(
              Prefetch("lines", queryset=ReturnLine.objects.select_related("item")),
              Prefetch("lines__dispositions",
                       queryset=ReturnDisposition.objects.only(
                           "id", "return_line_id", "quantity", "disposition")))
          .order_by("advance_refund_deadline", "-id"))
    state = (request.GET.get("state") or "").strip()
    if state == "overdue":
        # SQL half of the row's `overdue` verdict — deadline passed and nothing received.
        qs = qs.filter(advance_refund_deadline__lt=today, customer_shipped_on__isnull=True)
    elif state == "received":
        qs = qs.filter(status__in=("received", "settled"))
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(customer__name__icontains=q))

    page_obj = paginate(request, qs)
    rows, exposure = [], ZERO
    for rma in page_obj.object_list:
        # What we handed over: the drafted credit where one exists, otherwise what the lines are
        # worth. Both are honest figures for "how much is at risk"; which one applies is shown.
        credited = rma.credit_total if rma.credit_note_id else sum(
            (q2((line.quantity_approved or line.quantity_requested or ZERO)
                * (line.unit_price or ZERO)) for line in rma.lines.all()), ZERO)
        outstanding = rma.quantity_approved_total - rma.quantity_received_total
        at_risk = credited if outstanding > ZERO else ZERO
        exposure += at_risk
        rows.append({
            "obj": rma,
            "credited": q2(credited),
            "quantity_outstanding": outstanding if outstanding > ZERO else ZERO,
            "at_risk": q2(at_risk),
            "overdue": bool(rma.advance_refund_deadline
                            and rma.advance_refund_deadline < today
                            and rma.customer_shipped_on is None),
            "days_left": ((rma.advance_refund_deadline - today).days
                          if rma.advance_refund_deadline else None),
            "estimated": rma.credit_note_id is None,
        })
    return render(request, "scm/returns/advance_refund_exposure.html", {
        "rows": rows,
        "page_obj": page_obj,
        "q": q,
        "total_exposure": q2(exposure),
        "state_choices": [("overdue", "Deadline passed, nothing shipped"),
                          ("received", "Goods now received")],
        "clawback_note": (
            "There is no card hold and no automatic claw-back: reversing an advance refund is a "
            "manual credit-note reversal in Accounts Receivable. This page is the list of what "
            "would need reversing."),
    })


# ============================================================= (d) the STAFF console (L32)
@login_required
def return_portal(request):
    """The sidebar bullet's target: the STAFF side of the return portal. **Zero writes.**

    L32 bars a staff sidebar bullet from pointing at a login-gated (or customer-facing) page, and
    this app already applied that at 4.1's "Vendor Portal" → ``purchaseorder_list?status=sent``. So
    the bullet lands here: the portal INBOX awaiting approval, the copyable public link per open
    return, and the two masters that define what the customer is promised and offered.
    """
    inbox = (ReturnAuthorization.objects
             .filter(tenant=request.tenant, source="portal", status="requested")
             .select_related("customer", "sales_order", "policy")
             .prefetch_related(Prefetch("lines",
                                        queryset=ReturnLine.objects.select_related("item",
                                                                                   "reason")))
             .order_by("requested_on", "id"))
    # Capped and materialised ONCE. The sibling `open_returns` below already carries [:25]; this
    # queryset was unbounded and then had .count() called on it as well, so a tenant with a genuine
    # backlog of unapproved portal requests — exactly the state this page exists to surface —
    # rendered every one of them plus every one of their lines, and paid for a separate COUNT of the
    # same rows. `inbox_count` is now len() of what is actually shown.
    inbox = list(inbox[:50])
    # The public URL is built IN THE TEMPLATE from request.scheme/get_host + the token (the
    # landing-page detail pattern), so nothing here has to know the deployment's host.
    open_returns = (ReturnAuthorization.objects
                    .filter(tenant=request.tenant,
                            status__in=ReturnAuthorization.PUBLIC_STATUSES)
                    .exclude(public_token__isnull=True).exclude(public_token="")
                    .select_related("customer")
                    .order_by("-requested_on", "-id")[:25])
    return render(request, "scm/returns/return_portal.html", {
        "inbox": inbox,
        "inbox_count": len(inbox),
        "open_returns": open_returns,
        "policies": (ReturnPolicy.objects.filter(tenant=request.tenant, is_active=True)
                     .select_related("item_category").order_by("priority", "name")),
        "reasons": (ReturnReason.objects.filter(tenant=request.tenant, is_active=True)
                    .order_by("sort_order", "code")),
        "default_policy": select_policy(request.tenant),
        "portal_note": (
            "This is the staff console. The customer-facing pages are the token status page (one "
            "link per return, below) and the logged-in request form, which needs a CRM customer "
            "portal account. Anonymous order lookup is not built: nothing lets a stranger prove "
            "they own an order, and core.Address has no postal-code field to check against."),
    })


# ============================================================= (a) the logged-in customer request
def _customer_portal_access(request):
    """The active ``crm.CustomerPortalAccess`` for the logged-in portal user, or None.

    Re-used verbatim from ``crm.views.CustomerService.CustomerPortal`` rather than reimplemented —
    a second copy of an authorisation rule is a second place for it to be wrong. Local import: SCM
    does not import CRM at module scope.
    """
    if not request.user.is_authenticated:
        return None
    from apps.crm.models import CustomerPortalAccess
    return (CustomerPortalAccess.objects
            .filter(portal_user=request.user, tenant=request.tenant, is_active=True)
            .select_related("customer_party").first())


@login_required
def portal_return_create(request):
    """A CUSTOMER raising their own return. ``customer`` and ``source`` are forced server-side.

    The ``portal_case_create`` shape applied to returns — no new auth mechanism is invented. A
    portal account with no linked customer is REFUSED rather than silently scoped to nothing: the
    CRM view's own WARNING comment explains why (an unlinked party would match every unscoped row).
    """
    access = _customer_portal_access(request)
    if access is None:
        messages.error(request, "You don't have customer portal access.")
        return redirect("dashboard:home")
    party = access.customer_party
    if party is None:
        messages.error(request, "Your portal account has no linked customer — contact support.")
        return redirect("dashboard:home")

    def _portal_currency_id(tenant, customer, order, so_line):
        """The currency a portal-filed return should settle in.

        `accounting.Currency` is a GLOBAL master (code/name/symbol/is_active) with no tenant FK and
        no `is_base` flag — verified — so there is no "the tenant's default currency" to fall back
        to. The order the return came from is the honest answer; failing that, whatever this
        customer was last invoiced in.

        Returning None is a legitimate outcome for a customer with no order history, and it is NOT
        silent: `returnauthorization_draft_credit_note` refuses with "This return has no currency"
        and the staff RMA form exposes the field so a CSR can set it. Guessing a currency on a
        money document would be worse than stopping.
        """
        if order is not None and order.currency_id:
            return order.currency_id
        if so_line is not None and so_line.sales_order.currency_id:
            return so_line.sales_order.currency_id
        last = (SalesOrder.objects
                .filter(tenant=tenant, customer=customer, currency__isnull=False)
                .order_by("-order_date", "-id")
                .values_list("currency_id", flat=True)
                .first())
        return last

    if request.method == "POST":
        form = PortalReturnRequestForm(request.POST, tenant=request.tenant, customer=party)
        if form.is_valid():
            order = form.cleaned_data.get("sales_order")
            so_line = form.cleaned_data.get("sales_order_line")
            item = form.cleaned_data["item"]
            reason = form.cleaned_data["reason"]
            with transaction.atomic():
                policy = select_policy(request.tenant, item)
                rma = ReturnAuthorization(
                    tenant=request.tenant,
                    # FORCED server-side. Whatever the POST says, a portal user files for
                    # themselves only.
                    customer=party, source="portal", return_type="physical",
                    sales_order=order or (so_line.sales_order if so_line else None),
                    policy=policy, requested_on=timezone.localdate(),
                    resolution="refund", refund_method="original_tender",
                    return_method="mail_prepaid",
                    currency_id=_portal_currency_id(request.tenant, party, order, so_line),
                    notes=(form.cleaned_data.get("notes") or "")[:2000])
                rma.status = "requested"
                rma.save()
                ReturnLine.objects.create(
                    return_authorization=rma, sales_order_line=so_line, item=item,
                    description=(so_line.description if so_line else "") or "",
                    quantity_requested=form.cleaned_data["quantity_requested"],
                    reason=reason,
                    unit_price=(so_line.unit_price if so_line else ZERO),
                    tax_pct=(so_line.tax_pct if so_line else ZERO),
                    unit_cost=(item.average_cost or ZERO),
                    condition_reported=(form.cleaned_data.get("condition_reported") or "")[:120])
            write_audit_log(request.user, rma, "create",
                            {"via": "customer_portal", "customer": party.name})
            messages.success(request, f"Return request {rma.number} submitted — we'll email you "
                                      "once it has been reviewed.")
            return redirect("scm:returnauthorization_public", token=rma.public_token)
    else:
        form = PortalReturnRequestForm(tenant=request.tenant, customer=party)
    return render(request, "scm/returns/portal_return_form.html", {
        "form": form,
        "access": access,
        "party": party,
        "policy": select_policy(request.tenant),
        # Narrowed to PUBLIC_STATUSES: the template's "Track" link goes to the token page, whose
        # lookup resolves only those states, so a draft, rejected or cancelled row was rendered with
        # a link that 404s on a page the customer was just shown. Filtering here rather than hiding
        # the link keeps one definition of "trackable" instead of two.
        "my_returns": (ReturnAuthorization.objects
                       .filter(tenant=request.tenant, customer=party,
                               status__in=ReturnAuthorization.PUBLIC_STATUSES)
                       .order_by("-requested_on", "-id")[:10]),
    })


# ============================================================= (b) the PUBLIC token pages
def _public_rma(token, *, statuses):
    """Resolve a token to an RMA, or 404. The state guard lives in the LOOKUP (``kb_public``).

    ``select_related("tenant")`` because the tenant is taken OFF THE OBJECT — ``request.tenant`` is
    None for an anonymous visitor — and because ``tenant.is_active`` is checked here (the
    ``careers_list`` precedent): a churned or suspended workspace must stop serving customer data,
    and this token never expires on its own.
    """
    obj = get_object_or_404(
        ReturnAuthorization.objects.select_related("tenant", "customer", "policy"),
        public_token=token, status__in=statuses)
    if not obj.tenant.is_active:
        raise Http404("This workspace is no longer active.")
    return obj


def returnauthorization_public(request, token):
    """Public return-status page — NO decorator; the unguessable token is the bearer credential.

    **What a visitor may see:** status, line descriptions, next steps and the policy's
    ``portal_instructions``. **No prices, no costs, no supplier data** — the template renders
    everything escaped and never with ``|safe``.

    **What a visitor may do:** two POSTs discriminated by a hidden ``action`` field — "I've shipped
    it" (stamps ``customer_shipped_on`` and stores a pasted tracking number) and "add a note". Both
    writes are TOCTOU-safe conditional UPDATEs — ``filter(pk=…, customer_shipped_on__isnull=True)
    .update(...)`` — which is the shape ``case_public`` uses for its CSAT rating, NOT read-then-save.
    A concurrent second submit updates 0 rows and cannot overwrite the first.

    # WARNING: unauthenticated POST — add per-IP rate-limiting (django-ratelimit) or a WAF throttle
    # in production to stop floods. There is no rate limiting anywhere in this repo and none is
    # being invented here.
    """
    obj = _public_rma(token, statuses=ReturnAuthorization.PUBLIC_STATUSES)
    form = PublicReturnUpdateForm()
    if request.method == "POST":
        form = PublicReturnUpdateForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data["action"]
            now = timezone.now()
            if action == "shipped":
                tracking = (form.cleaned_data.get("return_tracking_number") or "").strip()[:64]
                # The STATE GUARD belongs in the UPDATE filter, not only in the template flag that
                # decides whether to draw the button. This is an UNAUTHENTICATED endpoint: a direct
                # POST against a still-unapproved or already-settled return would otherwise stamp
                # `customer_shipped_on` — permanently suppressing the overdue-shipment chase badge —
                # and overwrite a staff-entered tracking number with attacker-supplied text.
                updated = ReturnAuthorization.objects.filter(
                    pk=obj.pk, status__in=ReturnAuthorization.SHIPPABLE_STATUSES,
                    customer_shipped_on__isnull=True).update(
                        customer_shipped_on=timezone.localdate(),
                        return_tracking_number=tracking or obj.return_tracking_number,
                        updated_at=now)
                if updated:
                    # The anonymous actor is recorded as None — the careers_apply precedent. The
                    # AuditLog row is still the trace that something changed and how.
                    write_audit_log(None, obj, "update",
                                    {"via": "return_portal", "action": "shipped"})
            else:
                note = (form.cleaned_data.get("portal_note") or "").strip()[:500]
                # Same state guard: a settled or closed return is not a conversation any more.
                ReturnAuthorization.objects.filter(
                    pk=obj.pk, status__in=ReturnAuthorization.NOTEABLE_STATUSES).update(
                        portal_note=note, updated_at=now)
                write_audit_log(None, obj, "update", {"via": "return_portal", "action": "note"})
            return redirect("scm:returnauthorization_public", token=token)
    lines = list(obj.lines.select_related("item", "reason"))
    return render(request, "scm/returns/returnauthorization/public.html", {
        "obj": obj,
        # Explicitly NOT the line objects' money: the template is handed only what a customer may
        # see, so a future edit cannot accidentally render a cost by reaching through `obj`.
        "lines": [{"description": (line.description or (line.item.name if line.item_id else "")),
                   "quantity": line.quantity_requested,
                   "reason": line.reason.name if line.reason_id else "",
                   "follow_up_question": (line.reason.follow_up_question
                                          if line.reason_id else "")}
                  for line in lines],
        "policy": obj.policy,
        "form": form,
        "can_confirm_shipment": (obj.customer_shipped_on is None
                                 and obj.status in ("approved", "awaiting_receipt",
                                                    "partially_received")),
        "can_print_label": obj.status in ReturnAuthorization.LABEL_STATUSES,
    })


def returnauthorization_label(request, token):
    """The return slip — token-gated, and linked from the staff detail page too.

    **STAND-IN, stated plainly: this is a RETURN SLIP, not a carrier label.** There is no barcode,
    QR or PDF library in this repo and no carrier API, so the RMA number prints as TEXT.
    ``return_label_url``, ``label_cost`` and ``return_tracking_number`` are pasted by a human after
    buying the real label elsewhere — the 4.6 ``Shipment.carrier_tracking_number`` posture.

    Follows the ``coa_print`` convention: a standalone document page with its own toolbar and print
    styles, and a STATE REFUSAL before rendering — a slip for an unapproved return is a document
    that looks real and is not, exactly as ``coa_print`` refuses an unissued certificate.

    **This page grants MORE than the status page does.** It necessarily carries the warehouse
    return-to address (``policy.return_to_address`` — ``scm.Location`` has no address field, so
    there is nowhere else for it to come from). The two token surfaces are NOT equivalent and
    should not later be assumed to be.
    """
    obj = _public_rma(token, statuses=ReturnAuthorization.LABEL_STATUSES)
    lines = list(obj.lines.select_related("item", "reason"))
    return render(request, "scm/returns/returnauthorization/label.html", {
        "obj": obj,
        "policy": obj.policy,
        "return_to_address": (obj.policy.return_to_address if obj.policy_id else ""),
        "lines": [{"sku": line.item.sku if line.item_id else "",
                   "description": (line.description or (line.item.name if line.item_id else "")),
                   "quantity": line.quantity_approved or line.quantity_requested,
                   "reason_code": line.reason.code if line.reason_id else ""}
                  for line in lines],
        "printed_at": timezone.now(),
    })
