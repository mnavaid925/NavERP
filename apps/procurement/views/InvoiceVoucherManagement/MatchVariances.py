"""Procurement 6.13 Invoice & Voucher Management — InvoiceMatchVariance views + Match Board.

Four routes, and deliberately only four: the register, one detail page, one human verb
(``accept``) and the invoice-level **Match Board**.

Discipline worth recording, because a reviewer will otherwise go looking for it:

* **No create / edit / delete route exists, by design.** A variance is EVIDENCE produced by
  ``run_match()``: the next run deletes every row and rebuilds the register, so a hand-made row
  would be wiped and a hand-edited one would be a forged audit trail. The one ``form.html`` in
  this lane is therefore NOT a create/edit form — it is the GET confirmation page for the single
  human verb, ``accept``, whose only field is the optional note.
* **This model HAS its own ``tenant`` column** (unlike ``SupplierInvoiceLine``), so every
  queryset is ``filter(tenant=request.tenant)`` and every object is fetched
  ``get_object_or_404(..., tenant=request.tenant)`` — never through the header alone.
* **Accept is a row-locked write.** ``select_for_update()`` inside ``transaction.atomic()``, so
  two clerks clicking "accept" on the same exception cannot both audit a state change.
* **The Match Board is a PROJECTION, not a register.** It re-groups the same variance rows by
  invoice and writes nothing.
"""
from django.db import transaction
from django.db.models import Count, Min, Q
from django.urls import reverse

from apps.core.crud import paginate
from apps.procurement.forms.InvoiceVoucherManagement.MatchVariances import (
    InvoiceVarianceAcceptForm)
# NOT-YET-WIRED entities of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it and a package-level re-export is a star-import cycle at URLconf import.
from apps.procurement.models.InvoiceVoucherManagement.MatchVariances import (
    BASIS_CHOICES, OUTCOME_CHOICES, RESOLUTION_CHOICES, VARIANCE_TYPE_CHOICES,
    InvoiceMatchVariance)
from apps.procurement.models.InvoiceVoucherManagement.SupplierInvoices import SupplierInvoice
from apps.procurement.views._common import *  # noqa: F401,F403

TEMPLATE_LIST = "procurement/invoicevouchermanagement/matchvariance/list.html"
TEMPLATE_DETAIL = "procurement/invoicevouchermanagement/matchvariance/detail.html"
TEMPLATE_FORM = "procurement/invoicevouchermanagement/matchvariance/form.html"
TEMPLATE_BOARD = "procurement/invoicevouchermanagement/match_board.html"

#: How many invoices the register's filter dropdown offers. A dropdown that renders the whole
#: workspace is a page that never finishes loading.
INVOICE_CHOICE_LIMIT = 200

#: How many invoices the Match Board shows per page — the board's unit IS the invoice, so this
#: is also the number of groups rendered.
BOARD_PAGE_SIZE = 15

#: Every hop a register row walks. ``invoice_line`` and ``dispute`` are rendered as their own
#: columns; the invoice's vendor is what makes a row recognisable at a glance.
_ROW_RELATIONS = ("invoice", "invoice__vendor", "invoice__currency", "invoice_line", "dispute")

#: Every hop the detail page walks — the whole exception plus the document it was raised on.
_DETAIL_RELATIONS = _ROW_RELATIONS + ("invoice__purchase_order", "invoice__goods_receipt")


# -- shared helpers --------------------------------------------------------------------------

def _is_admin(request):
    """Mirrors ``@tenant_admin_required`` exactly, so a hidden button and a refused POST agree."""
    return bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False))


def _need_tenant(request, what):
    """The superuser has no workspace by design; say so instead of rendering an empty page."""
    if request.tenant is None:
        messages.error(request, f"Select a tenant workspace to {what}.")
        return redirect("dashboard:home")
    return None


def _stats(rows):
    """The four register stat cards, counted over the WHOLE workspace.

    A stat card answers "how much exception work is outstanding?", which must not change because
    somebody typed a search — hence one aggregate over the unfiltered queryset.
    """
    return rows.aggregate(
        open=Count("id", filter=Q(resolution="open")),
        blocking=Count("id", filter=Q(outcome="block")),
        warn=Count("id", filter=Q(outcome="warn")),
        auto_accept=Count("id", filter=Q(outcome="auto_accept")),
    )


# -- the exceptions register --------------------------------------------------------------------

@login_required
def matchvariance_list(request):
    """The exceptions board — every variance in the workspace, newest first."""
    guard = _need_tenant(request, "review match variances")
    if guard is not None:
        return guard
    rows = InvoiceMatchVariance.objects.filter(tenant=request.tenant)
    return crud_list(
        request,
        rows.select_related(*_ROW_RELATIONS),
        TEMPLATE_LIST,
        search_fields=["message", "invoice__number", "invoice__invoice_number"],
        # (get_param, orm_lookup, is_int) — the int one goes through crud_list's as_db_int guard,
        # so ?invoice=abc / ?invoice=999999999999999999999 skip the filter instead of 500ing (L11).
        filters=[("variance_type", "variance_type", False), ("outcome", "outcome", False),
                 ("resolution", "resolution", False), ("basis", "basis", False),
                 ("invoice", "invoice_id", True)],
        extra_context={
            "variance_type_choices": VARIANCE_TYPE_CHOICES,
            "outcome_choices": OUTCOME_CHOICES,
            "resolution_choices": RESOLUTION_CHOICES,
            "basis_choices": BASIS_CHOICES,
            "invoices": (SupplierInvoice.objects.filter(tenant=request.tenant)
                         .order_by("-invoice_date", "-id")[:INVOICE_CHOICE_LIMIT]),
            "stats": _stats(rows),
        },
    )


@login_required
def matchvariance_detail(request, pk):
    """One exception: what the engine expected, what the supplier claimed, and what can be done."""
    obj = get_object_or_404(InvoiceMatchVariance.objects.select_related(*_DETAIL_RELATIONS),
                            pk=pk, tenant=request.tenant)
    is_admin = _is_admin(request)
    # Accepting a variance on money that has already been paid or reversed is a no-op, and the
    # route refuses it — the button must not be offered either. The rule lives on the model so the
    # register and the Match Board gate on exactly the same expression.
    can_accept = obj.can_accept
    # A GET link, not a POST form: accepting carries an optional note and settles a decision
    # about money, so the button lands on the confirmation page (matchvariance/form.html) and the
    # write only happens when that page is submitted.
    actions = [{
        "url": reverse("procurement:matchvariance_accept", args=[obj.pk]),
        "label": "Accept variance…",
        "verb": "get",
        "css": "btn-primary",
    }] if can_accept else []
    return render(request, TEMPLATE_DETAIL, {
        "obj": obj,
        "invoice": obj.invoice,
        "invoice_line": obj.invoice_line,
        "dispute": obj.dispute,
        "explanation": obj.explain(),
        # The band actually in force when the row was written — the "against what" of the
        # verdict, which is unanswerable later if the workspace retunes its tolerances.
        "tolerance": {"abs": obj.tolerance_abs_applied, "pct": obj.tolerance_pct_applied},
        "actions": actions,
        "can_accept": can_accept,
        "is_admin": is_admin,
    })


@login_required
def matchvariance_accept(request, pk):
    """AP has looked at the exception and accepts it.

    GET renders the confirmation page — the Accept button has to land somewhere a person can
    read what they are accepting and type the optional note. POST applies the accept.

    Row-locked under ``select_for_update()``: two clerks clicking on the same exception must not
    both audit a state change. The note is bound by a plain ``Form`` — it writes nothing, it is
    carried into the audit trail.
    """
    guard = _need_tenant(request, "accept match variances")
    if guard is not None:
        return guard

    if request.method != "POST":
        # Unbound form: the note has nothing to re-display until a POST has failed validation.
        obj = get_object_or_404(InvoiceMatchVariance.objects.select_related(*_DETAIL_RELATIONS),
                                pk=pk, tenant=request.tenant)
        return render(request, TEMPLATE_FORM, {
            "obj": obj,
            "form": InvoiceVarianceAcceptForm(),
            # The template's title reads "Review variance" vs "Accept variance" off this.
            "is_edit": False,
        })

    form = InvoiceVarianceAcceptForm(request.POST)
    if not form.is_valid():
        # The only way this form fails is a note over 500 characters.
        messages.error(request, "The note is too long — 500 characters at most.")
        return redirect("procurement:matchvariance_detail", pk=pk)
    note = (form.cleaned_data.get("note") or "").strip()

    with transaction.atomic():
        obj = get_object_or_404(
            InvoiceMatchVariance.objects.select_related("invoice").select_for_update(),
            pk=pk, tenant=request.tenant)
        if not obj.accept(request.user):
            messages.error(
                request,
                f"This variance is already {obj.get_resolution_display().lower()}, so it cannot "
                f"be accepted.")
            return redirect("procurement:matchvariance_detail", pk=pk)

    changes = {"action": "accept"}
    if note:
        changes["note"] = note
    write_audit_log(request.user, obj, "update", changes)
    messages.success(request, f"{obj.get_variance_type_display()} accepted.")
    return redirect("procurement:matchvariance_detail", pk=pk)


# -- Match Board ---------------------------------------------------------------------------------

def _board_stats(rows, agg, today, tenant):
    """The board's four stat cards, counted over the FILTERED set (before pagination) — in SQL.

    Unlike the register, "how many invoices are held up" is a question the filters are allowed
    to answer — the board is a triage view (the ``payment_schedule`` precedent). Two queries over
    the GROUPED set, not a Python walk of every variance in the workspace: the cards cost what
    the cards are worth, and the page no longer has to materialise the table to count them.
    """
    # The output aliases MUST differ from the annotation aliases: reusing ``blocking``/``warn``
    # here makes Django resolve the filter against the aggregate it is defining and raise
    # "Cannot compute Count('blocking'): 'blocking' is an aggregate".
    summary = agg.aggregate(
        invoice_count=Count("invoice_id"),
        blocking_invoices=Count("invoice_id", filter=Q(blocking__gt=0)),
        # "Warn" means warnings and nothing blocking — a card carrying both counts as blocking.
        warn_invoices=Count("invoice_id", filter=Q(warn__gt=0, blocking=0)),
    )
    # An invoice is overdue when its due date has passed and it is not yet settled.
    overdue = (SupplierInvoice.objects
               .filter(tenant=tenant, pk__in=rows.values("invoice_id"), due_date__lt=today)
               .exclude(status__in=SupplierInvoice.TERMINAL_STATUSES).count())
    return {"invoices": summary["invoice_count"] or 0,
            "blocking": summary["blocking_invoices"] or 0,
            "warn": summary["warn_invoices"] or 0, "overdue": overdue}


def _group(invoice, variances):
    """One invoice card: its exceptions, how bad they are, and how long the oldest has waited."""
    return {
        "invoice": invoice,
        "variances": variances,
        "blocking_count": sum(1 for variance in variances if variance.outcome == "block"),
        "warn_count": sum(1 for variance in variances if variance.outcome == "warn"),
        # The STALEST exception, not the newest: a triage board is worked oldest-first.
        "oldest_at": min((variance.detected_at for variance in variances), default=None),
    }


@login_required
def invoice_match_board(request):
    """**Match Board** — the same exception register, grouped by invoice.

    The register answers "which checks failed?"; this board answers "which invoices are held up,
    and which have been waiting longest". It writes nothing.

    Every filter (``q``, ``outcome``, ``variance_type``) is applied to the VARIANCE queryset
    BEFORE grouping, so a card's counts always describe the rows it actually shows — filtering
    to ``?outcome=block`` yields only invoices with a blocking exception, and each card holds
    only its blocking rows.

    ``page_obj`` paginates the GROUP list: the invoice is the unit of work here, so the page
    count is a count of invoices, not of variances.
    """
    guard = _need_tenant(request, "review the match board")
    if guard is not None:
        return guard

    today = timezone.localdate()
    q = request.GET.get("q", "").strip()

    rows = InvoiceMatchVariance.objects.filter(tenant=request.tenant)
    outcome = request.GET.get("outcome", "").strip()
    if outcome:
        rows = rows.filter(outcome=outcome)
    variance_type = request.GET.get("variance_type", "").strip()
    if variance_type:
        rows = rows.filter(variance_type=variance_type)
    if q:
        rows = rows.filter(Q(message__icontains=q) | Q(invoice__number__icontains=q)
                           | Q(invoice__invoice_number__icontains=q)
                           | Q(invoice__vendor__name__icontains=q))

    # The board's unit is the INVOICE, so the grouping AND the paging both happen in SQL: one
    # aggregate row per invoice (no joins, no model instances), ordered oldest-exception-first,
    # and only the page's variance rows are then fetched with their relations. Materialising the
    # whole filtered variance queryset to render fifteen cards made this page cost what the table
    # costs rather than what the page shows.
    agg = (rows.values("invoice_id")
           .annotate(oldest=Min("detected_at"),
                     blocking=Count("id", filter=Q(outcome="block")),
                     warn=Count("id", filter=Q(outcome="warn")))
           .order_by("oldest", "-invoice_id"))

    page_obj = paginate(request, agg, BOARD_PAGE_SIZE)
    page_ids = [entry["invoice_id"] for entry in page_obj.object_list]

    # Newest first WITHIN a card (the freshest run's verdict is on top); the cards themselves stay
    # in ``page_ids`` order, which is the aggregate's oldest-first ordering.
    grouped = {}
    for variance in (rows.filter(invoice_id__in=page_ids).select_related(*_ROW_RELATIONS)
                     .order_by("-detected_at", "-id")):
        grouped.setdefault(variance.invoice_id, {"invoice": variance.invoice, "rows": []})
        grouped[variance.invoice_id]["rows"].append(variance)

    groups = [_group(grouped[invoice_id]["invoice"], grouped[invoice_id]["rows"])
              for invoice_id in page_ids if invoice_id in grouped]

    return render(request, TEMPLATE_BOARD, {
        # ``groups`` is the page's slice: the invoice is the unit of work, so paging the cards is
        # what keeps a 400-invoice workspace from rendering in one go.
        "groups": groups,
        "page_obj": page_obj,
        "stats": _board_stats(rows, agg, today, request.tenant),
        "outcome_choices": OUTCOME_CHOICES,
        "variance_type_choices": VARIANCE_TYPE_CHOICES,
        "today": today,
        "q": q,
    })
