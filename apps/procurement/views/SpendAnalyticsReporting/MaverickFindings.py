"""Procurement 6.14 Spend Analytics & Reporting — MaverickSpendFinding views.

Six routes: the register, one detail page, raise/edit/delete, and the **disposition** verb that
moves a finding to acknowledged / justified / remediated / dismissed.

Discipline worth recording, because a reviewer will otherwise go looking for it:

* **Every queryset is ``filter(tenant=request.tenant)``** — never ``.all()``. This model HAS its
  own tenant column, so every object is fetched ``get_object_or_404(..., tenant=request.tenant)``
  rather than through the invoice it points at.
* **Ordinary CRUD is ``@login_required``; the disposition adds ``@tenant_admin_required`` and
  ``@require_POST``** (L27, in that order): accepting a piece of maverick spend as "justified" is
  a governance decision, and dismissing one deletes a control finding in all but name.
* **The disposition runs the row under ``select_for_update()``** inside ``transaction.atomic()``,
  so two reviewers clicking at once cannot both audit a state change.
* **The status guard lives in the MODEL verb, not in the template.** ``allowed_actions`` mirrors
  the decorator and the guard on the route it points at — a hidden button and a refused POST
  always agree — but hiding a button never stops a direct POST, so each verb re-checks itself.

**Not in this module.** ``maverick_dashboard`` and ``maverick_scan`` are contracted to
``apps/procurement/views/SpendAnalyticsReporting/MaverickDashboard.py``, a separate module of this
same lane. The engine they drive — ``MaverickSpendFinding.scan()`` — lives on the model, so the
dashboard needs nothing from this file. Nothing here reverses ``procurement:maverick_dashboard``
or ``procurement:maverick_scan``, so this module imports and renders cleanly on its own.

**Import discipline.** This sub-package is NOT YET WIRED (the Integrator adds the re-export
blocks), so every sibling entity is imported as a MODULE — never
``from apps.procurement.models import X``, which would be a star-import cycle at URLconf import.
Same rule the 6.13 ``InvoiceDisputes`` views follow.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.urls import reverse

from apps.core.models import OrgUnit, Party
from apps.procurement.forms.SpendAnalyticsReporting.MaverickFindings import (
    MaverickSpendFindingForm)
from apps.procurement.models.CatalogManagement.CatalogItems import CatalogItem
from apps.procurement.models.SpendAnalyticsReporting.MaverickFindings import (
    REASON_CHOICES, SEVERITY_CHOICES, STATUS_CHOICES, MaverickSpendFinding)
from apps.procurement.views._common import *  # noqa: F401,F403
from apps.scm.models import ItemCategory

ZERO = Decimal("0")

TEMPLATE_LIST = "procurement/spendanalytics/maverickfinding/list.html"
TEMPLATE_DETAIL = "procurement/spendanalytics/maverickfinding/detail.html"
TEMPLATE_FORM = "procurement/spendanalytics/maverickfinding/form.html"

#: Money shape of every aggregate on this page — mirrors the model's DecimalField(18, 2), so a
#: Coalesce over two Decimal expressions has an unambiguous output field.
_MONEY = DecimalField(max_digits=18, decimal_places=2)

#: Every hop a register row (or its ``__str__``) walks. ``__str__`` itself touches only ``number``
#: and ``reason``, but the list renders the supplier, the category, the department and the source
#: document on every row — without these that is five queries per row.
_ROW_RELATIONS = ("vendor", "category", "org_unit", "supplier_invoice", "purchase_order")

#: Every hop the detail page walks, including the CHAINED ones: the invoice line's own header and
#: item, and the source documents' suppliers.
_DETAIL_RELATIONS = _ROW_RELATIONS + (
    "contract", "catalog_item", "catalog_item__supplier", "invoice_line", "invoice_line__invoice",
    "invoice_line__item", "supplier_invoice__vendor", "supplier_invoice__currency",
    "purchase_order__vendor", "resolved_by")

#: The four disposition verbs, and NOTHING else moves ``status``. ``needs_note`` is enforced by
#: the view, not just asked for by the template: a finding filed as "justified" with no reason is
#: an audit trail that says nothing.
DISPOSITION_ACTIONS = {
    "acknowledge": {"label": "Acknowledge", "css": "btn-outline", "needs_note": False,
                    "done": "acknowledged"},
    "justify": {"label": "Justify - accept", "css": "btn-outline", "needs_note": True,
                "done": "justified"},
    "remediate": {"label": "Mark remediated", "css": "btn-primary", "needs_note": True,
                  "done": "remediated"},
    "dismiss": {"label": "Dismiss - false positive", "css": "btn-danger", "needs_note": True,
                "done": "dismissed"},
}


# -- shared helpers ----------------------------------------------------------------------------

def _is_admin(request):
    """Mirrors ``@tenant_admin_required`` EXACTLY, so a hidden button and a refused POST agree."""
    return bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False))


def _need_tenant(request, what):
    """The superuser has no workspace by design; say so instead of rendering an empty page."""
    if request.tenant is None:
        messages.error(request, f"Select a tenant workspace to {what}.")
        return redirect("dashboard:home")
    return None


def _suppliers(tenant):
    """The supplier-role parties this workspace buys from — the filter dropdown's options.

    Narrowed to suppliers rather than every party: a directory of customers and employees in a
    "supplier" filter is noise that also happens to be slow.
    """
    if tenant is None:
        return Party.objects.none()
    return (Party.objects.filter(tenant=tenant, roles__role__in=("supplier", "vendor"))
            .distinct().order_by("name"))


def _stats(tenant):
    """The four register stat cards in ONE aggregate over the WHOLE workspace.

    Deliberately not over the filtered page: a stat card answers "how much unmanaged spend is
    outstanding?", which must not change because somebody typed a search. ``high`` counts
    high-severity findings that are still OPEN — a resolved one is not work.
    """
    live = Q(status__in=MaverickSpendFinding.OPEN_STATUSES)
    return MaverickSpendFinding.objects.filter(tenant=tenant).aggregate(
        open=Count("id", filter=live),
        high=Count("id", filter=live & Q(severity="high")),
        value_at_risk=Coalesce(Sum("amount", filter=live), Value(ZERO), output_field=_MONEY),
        leakage=Coalesce(Sum("leakage_amount", filter=live), Value(ZERO), output_field=_MONEY),
    )


def _alternatives(tenant, obj):
    """Preferred catalogue entries for the same thing at a DIFFERENT supplier.

    This is the "what should we have done instead" panel, and it is the reason
    ``non_preferred_vendor`` is actionable rather than merely true. Returns a QuerySet — possibly
    empty — so the template can loop it unconditionally.
    """
    entry = obj.catalog_item if obj.catalog_item_id else None
    line = obj.invoice_line if obj.invoice_line_id else None

    item_id = entry.item_id if entry is not None else None
    part = (entry.supplier_part_no or "").strip() if entry is not None else ""
    if line is not None:
        item_id = item_id or line.item_id
        part = part or (line.sku_hint or "").strip()

    condition = Q()
    matched = False
    if item_id:
        condition |= Q(item_id=item_id)
        matched = True
    if part:
        condition |= Q(supplier_part_no__iexact=part)
        matched = True
    if not matched:
        return CatalogItem.objects.none()

    rows = (CatalogItem.objects
            .filter(tenant=tenant, status="approved", is_active=True, is_preferred=True)
            .filter(condition)
            .select_related("supplier", "item", "currency")
            .order_by("name"))
    if obj.vendor_id:
        # The supplier we actually bought from is not an "alternative" to itself.
        rows = rows.exclude(supplier_id=obj.vendor_id)
    return rows[:10]


def _allowed_actions(obj, is_admin):
    """What this finding may still be moved to, for the operator looking at it.

    Empty for a non-admin, because the disposition route is ``@tenant_admin_required``: offering
    a button that would 403 is worse than offering none.
    """
    if not is_admin or obj.is_resolved:
        return []
    actions = []
    for action, spec in DISPOSITION_ACTIONS.items():
        if action == "acknowledge" and obj.status != "open":
            # ``acknowledge`` only moves an untouched finding; re-acknowledging is a no-op.
            continue
        actions.append({
            "action": action,
            "label": spec["label"],
            "css": spec["css"],
            "needs_note": spec["needs_note"],
        })
    return actions


# -- the register --------------------------------------------------------------------------------

@login_required
def maverickfinding_list(request):
    """The maverick-spend register — every finding in the workspace, newest spend first."""
    guard = _need_tenant(request, "review maverick spend")
    if guard is not None:
        return guard
    return crud_list(
        request,
        MaverickSpendFinding.objects.filter(tenant=request.tenant)
        .select_related(*_ROW_RELATIONS),
        TEMPLATE_LIST,
        search_fields=["number", "detail", "vendor__name", "supplier_invoice__invoice_number",
                       "purchase_order__number"],
        # (get_param, orm_lookup, is_int) — the int ones go through crud_list's as_db_int guard,
        # so ?vendor=abc and ?vendor=999999999999999999999 skip the filter instead of 500ing
        # (L11). ``addressable`` is a BooleanField, which crud_list maps from "True"/"False".
        filters=[("reason", "reason", False), ("status", "status", False),
                 ("severity", "severity", False), ("vendor", "vendor_id", True),
                 ("category", "category_id", True), ("org_unit", "org_unit_id", True),
                 ("addressable", "is_addressable", False)],
        extra_context={
            "reason_choices": REASON_CHOICES,
            "status_choices": STATUS_CHOICES,
            "severity_choices": SEVERITY_CHOICES,
            "vendors": _suppliers(request.tenant),
            "categories": ItemCategory.objects.filter(tenant=request.tenant, is_active=True)
                                              .order_by("name"),
            "org_units": OrgUnit.objects.filter(tenant=request.tenant).order_by("name"),
            "stats": _stats(request.tenant),
            "is_admin": _is_admin(request),
        },
    )


@login_required
def maverickfinding_detail(request, pk):
    """One finding: what happened, what it should have cost, and what can still be done."""
    obj = get_object_or_404(
        MaverickSpendFinding.objects.select_related(*_DETAIL_RELATIONS),
        pk=pk, tenant=request.tenant)
    is_admin = _is_admin(request)
    return render(request, TEMPLATE_DETAIL, {
        "obj": obj,
        # Aliased for readability in a template that talks about a "finding" throughout — the
        # SAME object, never a second query.
        "finding": obj,
        "supplier_invoice": obj.supplier_invoice,
        "invoice_line": obj.invoice_line,
        "purchase_order": obj.purchase_order,
        "contract": obj.contract,
        "catalog_item": obj.catalog_item,
        "alternatives": _alternatives(request.tenant, obj),
        "benchmark": {
            "expected": obj.benchmark_amount,
            "actual": obj.amount,
            "variance_pct": obj.variance_pct,
        },
        "allowed_actions": _allowed_actions(obj, is_admin),
        "is_resolved": obj.is_resolved,
        "severity_css": obj.severity_css,
        "status_css": obj.status_css,
        "is_admin": is_admin,
        "disposition_url": reverse("procurement:maverickfinding_disposition", args=[obj.pk]),
    })


# -- raise / amend ---------------------------------------------------------------------------------

@login_required
def maverickfinding_create(request):
    """Raise a finding by hand — for maverick spend no detector can see.

    ``crud_create`` refuses a tenant-less user on its own (the superuser has ``tenant=None`` by
    design), stamps the tenant, and writes the AuditLog row.
    """
    return crud_create(
        request,
        form_class=MaverickSpendFindingForm,
        template=TEMPLATE_FORM,
        success_url="procurement:maverickfinding_list",
        extra_context={
            "title": "Raise a maverick-spend finding",
            "submit_label": "Raise finding",
            "cancel_url": reverse("procurement:maverickfinding_list"),
        },
    )


@login_required
def maverickfinding_edit(request, pk):
    """Amend an OPEN finding.

    A disposed finding is a closed book: its amount and reason are what a governance decision was
    recorded against, and re-writing them after the fact would rewrite the trail of that decision.
    The guard lives HERE, not only in the template — hiding an Edit button does not stop a direct
    POST to this URL.
    """
    obj = get_object_or_404(MaverickSpendFinding, pk=pk, tenant=request.tenant)
    if obj.is_resolved:
        messages.error(
            request,
            f"{obj.number} is {obj.get_status_display().lower()} — only an open finding can be "
            f"edited.")
        return redirect("procurement:maverickfinding_detail", pk=pk)
    return crud_edit(
        request,
        model=MaverickSpendFinding,
        pk=pk,
        form_class=MaverickSpendFindingForm,
        template=TEMPLATE_FORM,
        success_url=reverse("procurement:maverickfinding_detail", args=[pk]),
        extra_context={
            "title": "Edit finding",
            "submit_label": "Save changes",
            "cancel_url": reverse("procurement:maverickfinding_detail", args=[pk]),
        },
    )


@login_required
@require_POST
def maverickfinding_delete(request, pk):
    """POST-only. ``crud_delete`` is self-defending as well: it only mutates on POST."""
    return crud_delete(request, model=MaverickSpendFinding, pk=pk,
                       success_url="procurement:maverickfinding_list")


# -- disposition -------------------------------------------------------------------------------------

@login_required
@tenant_admin_required
@require_POST
def maverickfinding_disposition(request, pk):
    """Move a finding to acknowledged / justified / remediated / dismissed.

    The POSTed ``action`` is validated against ``DISPOSITION_ACTIONS`` and NOTHING else moves
    ``status``: an unknown verb is refused rather than guessed at, and the three terminal verbs
    require a note, because "justified" with no reason is an audit trail that says nothing.

    The row is locked with ``select_for_update()`` inside ``transaction.atomic()``, so two
    reviewers clicking at once cannot both audit a state change — and the model verb re-checks its
    own guard inside itself, so a stale page's POST is refused rather than applied.
    """
    guard = _need_tenant(request, "dispose of maverick-spend findings")
    if guard is not None:
        return guard

    action = (request.POST.get("action") or "").strip()
    spec = DISPOSITION_ACTIONS.get(action)
    if spec is None:
        messages.error(request, "Choose what to do with this finding.")
        return redirect("procurement:maverickfinding_detail", pk=pk)

    note = (request.POST.get("note") or "").strip()
    if spec["needs_note"] and not note:
        messages.error(request, f"A note is required to {spec['label'].split(' -')[0].lower()} "
                                f"a finding.")
        return redirect("procurement:maverickfinding_detail", pk=pk)

    with transaction.atomic():
        obj = get_object_or_404(MaverickSpendFinding.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        verb = getattr(obj, action)
        moved = verb(request.user) if not spec["needs_note"] else verb(request.user, note)
        if not moved:
            messages.error(
                request,
                f"{obj.number} is {obj.get_status_display().lower()} and cannot be "
                f"{spec['done']}.")
            return redirect("procurement:maverickfinding_detail", pk=pk)

    changes = {"action": action, "status": obj.status}
    if note:
        changes["note"] = note[:200]
    write_audit_log(request.user, obj, "update", changes)
    messages.success(request, f"{obj.number} marked {obj.get_status_display().lower()}.")
    return redirect("procurement:maverickfinding_detail", pk=pk)
