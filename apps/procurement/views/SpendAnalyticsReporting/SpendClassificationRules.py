"""Procurement 6.14 Spend Analytics & Reporting — SpendClassificationRule CRUD + preview.

Six routes: the rule register, one detail page (which RUNS the rule against real spend rather
than describing it in prose), create / edit / delete, and the **preview** verb.

**This master has no sidebar key, by design.** It is reached from ``category_spend`` and from the
classification workbench — the ``ReceiptTolerancePolicy`` / ``KpiTarget`` precedent. A rule table
is configuration behind an analysis page, not a destination of its own.

Discipline a reviewer will otherwise go looking for:

* **Every queryset is ``filter(tenant=request.tenant)``** — never ``.all()`` — and every object is
  fetched ``get_object_or_404(..., tenant=request.tenant)``.
* **``spendrule_preview`` is the ONLY write outside the CRUD helpers.** It is ``@require_POST``,
  it takes the row under ``select_for_update()`` inside ``transaction.atomic()`` so two clerks
  previewing the same rule cannot interleave their stamps, and it calls ``write_audit_log``
  itself — ``crud_*`` does not cover a hand-rolled save path.
* **It stamps ``match_count`` / ``last_matched_at`` and NOTHING else.** 6.14 writes nothing to
  ``accounting.*`` and nothing to the ``scm`` document spine (L29/L36); this is a read-only
  analytics pass over spend that already exists.
* **The engine is explicit and auditable.** Every classification traces to a row a person wrote.
  It is not machine learning and is never labelled "AI" or "ML" on any page this module renders.

The detail page's preview is the honest test of a rule: it aggregates the real spend lines the
rule matches in the default window instead of asserting a scope, and it links each recent match
out to 6.13's invoice page rather than re-rendering it here.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.urls import reverse

from apps.core.crud import as_db_int
from apps.procurement.forms.SpendAnalyticsReporting.SpendClassificationRules import (
    SpendClassificationRuleForm,
)
# NOT-YET-WIRED entities of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrate
# phase lands it, and a package-level re-export is a star-import cycle at URLconf import (the
# 6.13 InvoiceDisputes precedent).
from apps.procurement.models.SpendAnalyticsReporting.SpendClassificationRules import (
    APPLIES_TO_CHOICES,
    MATCH_TYPE_CHOICES,
    RECENT_MATCH_LIMIT,
    SpendClassificationRule,
    default_preview_window,
    invoiced_line_window,
    money,
)
from apps.procurement.views._common import *  # noqa: F401,F403

ZERO = Decimal("0")

TEMPLATE_LIST = "procurement/spendanalytics/spendrule/list.html"
TEMPLATE_DETAIL = "procurement/spendanalytics/spendrule/detail.html"
TEMPLATE_FORM = "procurement/spendanalytics/spendrule/form.html"

#: The GET params the workbench may pre-fill a new rule with. Read as data, never trusted: the
#: three pk ones go through ``as_db_int`` AND an existence check inside this workspace, and the
#: two vocabulary ones are checked against their own choice keys.
_PREFILL_PK_FIELDS = ("vendor", "gl_account", "org_unit")


def _scoped(tenant):
    """This workspace's rules, with every FK a row (or a row's ``__str__``) touches pre-fetched.

    ``__str__`` walks ``self.category``, and the register renders the subject column off
    ``vendor`` / ``gl_account`` / ``org_unit`` — four hops that are four queries PER ROW without
    this.
    """
    return (SpendClassificationRule.objects.filter(tenant=tenant)
            .select_related("category", "vendor", "gl_account", "org_unit"))


def _supplier_parties(tenant):
    """Supplier/vendor-role parties for the filter widget — the local-copy convention."""
    from apps.core.models import Party

    if tenant is None:
        return Party.objects.none()
    return (Party.objects.filter(tenant=tenant, roles__role__in=("supplier", "vendor"))
            .distinct().order_by("name"))


def _matched_value(tenant, rules, start, end):
    """Recognised invoiced spend that the ACTIVE rules classify, in ONE query.

    Each rule contributes its own ``line_filter`` predicate and they are OR-ed together, so the
    whole register's stat strip costs a single aggregate rather than one preview per rule. A rule
    that can match nothing on the invoiced basis (inactive, committed-only, or an unset subject)
    returns ``None`` from ``line_filter`` and is skipped — never folded in as "no filter", which
    would report the entire workspace's spend as classified.
    """
    if tenant is None:
        return ZERO
    predicate = None
    for rule in rules:
        clause = rule.line_filter("invoiced")
        if clause is None:
            continue
        predicate = clause if predicate is None else (predicate | clause)
    if predicate is None:
        return ZERO
    total = (invoiced_line_window(tenant, start, end)
             .filter(predicate)
             .aggregate(v=Sum("line_total"))["v"])
    return money(total)


@login_required
def spendrule_list(request):
    """The rule register: what this workspace has told the cube about its own spend."""
    base = _scoped(request.tenant)
    start, end = default_preview_window()

    # ONE aggregate over the UNFILTERED tenant queryset — the cards describe the workspace, not
    # the current filter, so they can never contradict the list they link to.
    counts = base.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        inactive=Count("id", filter=Q(is_active=False)),
    )
    # Deliberately its own narrow query rather than a Python filter over ``base``: iterating the
    # select_related() register queryset here would load (and cache) every rule and its four FK
    # rows just to build one number, and ``line_filter`` reads nothing but ``*_id`` columns.
    active_rules = list(
        SpendClassificationRule.objects.filter(tenant=request.tenant, is_active=True)
        .order_by("priority", "id")
    ) if request.tenant is not None else []
    stats = {
        "total": counts["total"],
        "active": counts["active"],
        "inactive": counts["inactive"],
        "matched_value": _matched_value(request.tenant, active_rules, start, end),
    }

    from apps.accounting.models import GLAccount
    from apps.core.models import OrgUnit
    from apps.scm.models import ItemCategory

    # L11 for enums. ``?category=abc`` is refused by crud_list's int guard and ``?is_active=abc``
    # raises ValidationError inside .filter() there and is skipped — but an unrecognised CHOICES
    # value is a plain string, so ``.filter(match_type="not-a-type")`` neither raises nor narrows:
    # it silently empties the register. A hand-edited enum is junk, not a narrowing request, so it
    # must be IGNORED. crud_list reads request.GET itself, so the guard is expressed by WITHHOLDING
    # the filter spec — the same ``in dict(MATCH_TYPE_CHOICES)`` test the prefill below uses.
    list_filters = [("category", "category_id", True), ("is_active", "is_active", False)]
    if request.GET.get("match_type", "").strip() in dict(MATCH_TYPE_CHOICES):
        list_filters.append(("match_type", "match_type", False))

    return crud_list(
        request, base, TEMPLATE_LIST,
        search_fields=("name", "keyword", "notes", "category__name"),
        filters=tuple(list_filters),
        extra_context={
            "match_type_choices": MATCH_TYPE_CHOICES,
            "applies_to_choices": APPLIES_TO_CHOICES,
            "categories": (ItemCategory.objects.filter(tenant=request.tenant, is_active=True)
                           .order_by("name") if request.tenant is not None
                           else ItemCategory.objects.none()),
            "vendors": _supplier_parties(request.tenant),
            "gl_accounts": (GLAccount.objects.filter(tenant=request.tenant, is_active=True)
                            .order_by("code") if request.tenant is not None
                            else GLAccount.objects.none()),
            "org_units": (OrgUnit.objects.filter(tenant=request.tenant).order_by("name")
                          if request.tenant is not None else OrgUnit.objects.none()),
            "stats": stats,
        },
    )


def _recent_matches(rule, start, end):
    """Up to :data:`RECENT_MATCH_LIMIT` real lines this rule matched, newest first.

    Prefers the INVOICED basis (that is what a buyer recognises as spend) and falls back to the
    committed basis for a committed-only rule, so a PO-only rule still shows its evidence instead
    of an empty panel. Each row links OUT to the document's own page — 6.13 owns the invoice view
    and SCM 4.1 owns the order view; neither is re-rendered here.
    """
    lines = rule.matching_lines(start, end, "invoiced")
    if lines is not None:
        rows = list(
            lines.select_related("invoice", "invoice__vendor")
            .order_by("-invoice__invoice_date", "-id")[:RECENT_MATCH_LIMIT]
        )
        return [{
            "label": line.description or line.sku_hint or "Line",
            "document": line.invoice.number or line.invoice.invoice_number,
            "document_url": reverse("procurement:supplierinvoice_detail", args=[line.invoice_id]),
            "date": line.invoice.invoice_date,
            "amount": line.line_total,
        } for line in rows]

    lines = rule.matching_lines(start, end, "committed")
    if lines is None:
        return []
    rows = list(
        lines.select_related("purchase_order", "purchase_order__vendor")
        .order_by("-doc_date", "-id")[:RECENT_MATCH_LIMIT]
    )
    return [{
        "label": line.item_description or line.sku_hint or "Line",
        "document": line.purchase_order.number,
        "document_url": reverse("scm:purchaseorder_detail", args=[line.purchase_order_id]),
        "date": line.doc_date,
        "amount": line.line_total,
    } for line in rows]


@login_required
def spendrule_detail(request, pk):
    """One rule, run against real spend rather than described in prose."""
    obj = get_object_or_404(_scoped(request.tenant), pk=pk)
    start, end = default_preview_window()
    result = obj.preview(start, end)
    preview = {"count": result["count"], "value": result["value"], "start": start, "end": end}

    return render(request, TEMPLATE_DETAIL, {
        "obj": obj,
        # Same object under the name the detail template reads — pinned by the contract.
        "rule": obj,
        "preview": preview,
        "recent_matches": _recent_matches(obj, start, end),
        "category": obj.category if obj.category_id else None,
        # Nothing in the schema points AT a rule (``category`` is an outbound PROTECT), so
        # deleting one can never orphan a row — it only stops classifying future cube passes.
        # The key exists so the template's button and this view agree if that ever changes.
        "can_delete": True,
        "stats": {
            "match_count": obj.match_count,
            "last_matched_at": obj.last_matched_at,
            "preview_count": result["count"],
            "preview_value": result["value"],
        },
    })


def _prefill(request):
    """``initial`` for a rule created from the workbench, built from GET params treated as DATA.

    Every pk goes through ``as_db_int`` (L11 — a hand-edited ``?vendor=abc`` must skip the
    prefill, not 500) AND is confirmed to exist inside THIS workspace, so a crafted link can never
    pre-select another tenant's supplier. The vocabulary params are checked against their own
    choice keys for the same reason.
    """
    initial = {}
    if request.tenant is None:
        return initial

    from apps.accounting.models import GLAccount
    from apps.core.models import OrgUnit

    querysets = {
        "vendor": _supplier_parties(request.tenant),
        "gl_account": GLAccount.objects.filter(tenant=request.tenant),
        "org_unit": OrgUnit.objects.filter(tenant=request.tenant),
    }
    for field in _PREFILL_PK_FIELDS:
        pk = as_db_int(request.GET.get(field, ""))
        if pk is not None and querysets[field].filter(pk=pk).exists():
            initial[field] = pk

    match_type = request.GET.get("match_type", "").strip()
    if match_type in dict(MATCH_TYPE_CHOICES):
        initial["match_type"] = match_type

    invoice_type = request.GET.get("invoice_type", "").strip()
    if invoice_type:
        from apps.procurement.models.InvoiceVoucherManagement.SupplierInvoices import (
            SupplierInvoice,
        )
        if invoice_type in dict(SupplierInvoice.INVOICE_TYPE_CHOICES):
            initial["invoice_type"] = invoice_type

    keyword = request.GET.get("keyword", "").strip()
    if keyword:
        # Truncated to the column width: an over-long prefill would render a value the form is
        # guaranteed to reject, which reads as a broken link rather than as a validation message.
        initial["keyword"] = keyword[:120]

    return initial


@login_required
def spendrule_create(request):
    """New rule, optionally pre-filled from the classification workbench.

    ``crud_create`` builds the form itself and takes no ``initial``, so the prefill is bound to
    the form class with ``functools.partial`` — the helper keeps owning tenant stamping, the audit
    row and the POST-redirect-GET, and the prefill is applied where Django expects it. On a POST
    the bound form ignores ``initial`` for display, so this is GET-only behaviour by construction.
    """
    from functools import partial

    initial = _prefill(request)
    form_class = partial(SpendClassificationRuleForm, initial=initial) if initial \
        else SpendClassificationRuleForm
    return crud_create(
        request, form_class=form_class, template=TEMPLATE_FORM,
        success_url="procurement:spendrule_list",
        extra_context={
            "title": "New classification rule",
            "submit_label": "Create rule",
            "cancel_url": reverse("procurement:spendrule_list"),
        },
    )


@login_required
def spendrule_edit(request, pk):
    return crud_edit(
        request, model=SpendClassificationRule, pk=pk,
        form_class=SpendClassificationRuleForm, template=TEMPLATE_FORM,
        success_url=reverse("procurement:spendrule_detail", args=[pk]),
        extra_context={
            "title": "Edit rule",
            "submit_label": "Save changes",
            "cancel_url": reverse("procurement:spendrule_detail", args=[pk]),
        },
    )


@login_required
@require_POST
def spendrule_delete(request, pk):
    """POST-only. ``crud_delete`` writes the audit row before the row goes."""
    return crud_delete(request, model=SpendClassificationRule, pk=pk,
                       success_url="procurement:spendrule_list")


@login_required
@require_POST
def spendrule_preview(request, pk):
    """Run the rule against real spend and stamp what it found.

    The ONLY hand-rolled write in this module. ``select_for_update()`` inside
    ``transaction.atomic()`` so two people previewing the same rule cannot interleave their
    stamps, ``update_fields`` so nothing else on the row can be touched by accident, and an
    explicit ``write_audit_log`` because ``crud_*`` does not cover this path.

    It writes ``match_count`` and ``last_matched_at`` and nothing else — no ledger row, no spine
    row, no cached money column (L29).
    """
    start, end = default_preview_window()
    with transaction.atomic():
        obj = get_object_or_404(
            SpendClassificationRule.objects.select_for_update(), pk=pk, tenant=request.tenant)
        result = obj.preview(start, end)
        obj.match_count = result["count"]
        obj.last_matched_at = timezone.now()
        obj.save(update_fields=["match_count", "last_matched_at", "updated_at"])
        write_audit_log(request.user, obj, "preview", changes={
            "matched_lines": result["count"],
            "matched_value": str(result["value"]),
            "window": f"{start} to {end}",
        })
    messages.success(
        request,
        f"Preview run: {result['count']} line(s) worth {result['value']} matched since {start}.")
    return redirect("procurement:spendrule_detail", pk=pk)
