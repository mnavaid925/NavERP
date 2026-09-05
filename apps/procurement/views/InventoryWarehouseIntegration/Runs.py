"""Procurement 6.18 Inventory & Warehouse Integration — ReplenishmentRun views.

**Reorder Point Automation** bullet, the working half: the register of batch proposals, the
review board where a buyer accepts / snoozes / dismisses each suggested line, and the three verbs
that move a run through ``draft → proposed → released``.

Discipline a reviewer will otherwise go looking for:

* **Every queryset is ``filter(tenant=request.tenant)``** — never ``.all()``. Suggestion lines
  carry no tenant column of their own, so theirs is reached THROUGH the run (``run__tenant``),
  and :func:`replenishmentsuggestion_decide` loads its line as
  ``pk=line_id, run__pk=pk, run__tenant=request.tenant`` — **that compound lookup IS the IDOR
  boundary**, not a convenience. A tenant-less user gets an EMPTY page, never a 500.
* **The stats strip is ONE conditional aggregate**, and so is the detail page's totals strip —
  six ``COUNT`` round-trips for six numbers off the same table is exactly the shape the
  performance rule exists to stop.
* **The register annotates rather than reading the model's count properties.** ``line_count`` and
  ``accepted_count`` are ``@property`` — a data descriptor, so a same-named annotation would be
  written to the instance ``__dict__`` and then SILENTLY IGNORED on read, leaving a page that
  quietly costs two queries per row. The annotations therefore carry distinct names
  (``annotated_*``) and the template reads those.
* **The decide row does NOT instantiate a form per line.** ``vendors`` and ``decision_choices``
  are passed once and the row renders its own ``<select>``s; 25 bound forms would each evaluate
  the vendor queryset, which is 25 queries for one page of a review board. The FORM is still what
  validates the POST — :func:`replenishmentsuggestion_decide` builds exactly one.
* **``release`` is ``@tenant_admin_required``** on top of ``@require_POST``: it raises
  requisitions, and a requisition is the start of spending money.
* **Every URL on a dict row is ``reverse()``d in Python.** ``requisitions`` is a list of plain
  dicts for precisely that reason — a ``{% url %}`` tag cannot express "only when this line was
  released", and a null pk in one is a ``NoReverseMatch`` 500 rather than a blank cell.
"""
from django.core.exceptions import ValidationError
from django.db.models import Count, F, Q, Sum
from django.urls import reverse

from apps.core.crud import paginate     # NOT in views/_common — imported explicitly (contract §1)
from apps.core.models import Party
from apps.scm.models import Location, PurchaseRequisition

from apps.procurement.forms.InventoryWarehouseIntegration.Runs import (
    ReplenishmentRunForm, ReplenishmentSuggestionDecisionForm)
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.InventoryWarehouseIntegration.Runs import (ReplenishmentRun,
                                                                        ReplenishmentSuggestion)
from apps.procurement.views._common import *  # noqa: F401,F403

TEMPLATE_LIST = "procurement/inventorywarehouse/replenishmentrun/list.html"
TEMPLATE_DETAIL = "procurement/inventorywarehouse/replenishmentrun/detail.html"
TEMPLATE_FORM = "procurement/inventorywarehouse/replenishmentrun/form.html"

#: The review board renders the item, its UOM, the location, the vendor, the policy that shaped
#: the line and the requisition it was released into — so it joins all six.
_LINE_RELATIONS = ("item", "item__uom", "location", "vendor", "policy", "requisition")

#: One page of the review board. 25 rather than the crud default of 15: a buyer works down a run
#: in one sitting and every extra page is another round of context-switching.
_LINES_PER_PAGE = 25

#: Said on the detail page, in the view, once. Open purchase orders and open requisitions match
#: an item by its free-text ``sku_hint`` (L28 — 4.1's lines predate the item spine) and carry no
#: location, so a network figure is netted off every location's shortfall. A run scoped to one
#: location is exact; a whole-network run under-proposes for a SKU stocked in several places.
SKU_MATCH_NOTE = (
    "On-order and open-requisition quantities are matched to an item by its SKU, exactly, and "
    "purchase-order and requisition lines carry no location. A run scoped to a single location is "
    "therefore exact; a whole-network run nets the same incoming quantity off every location that "
    "stocks the SKU, so it proposes conservatively. On-hand, allocations and reservations are all "
    "per location and always exact.")


def _run_qs(request):
    """The register's base queryset: tenant-scoped, joined and counted in ONE query.

    The two ``Count``s and the ``Sum`` all ride the SAME ``lines`` join, so there is no fan-out to
    worry about — that only happens across two DIFFERENT multi-valued relations. See the module
    docstring for why they cannot be named ``line_count`` / ``accepted_count``.

    **The explicit ``order_by`` is not redundant — it is load-bearing.** Since Django 3.1
    ``Meta.ordering`` is deliberately NOT applied to a GROUP BY query, and ``annotate()`` over a
    multi-valued relation makes this one. Without it the register's SQL carries no ``ORDER BY``
    at all, ``qs.ordered`` is ``False``, ``Paginator`` warns about an unordered object list, and
    the database is free to return rows in a different order per page — so a run can appear on
    page 1 and again on page 2 while another is never shown. It repeats ``Meta.ordering``
    verbatim; keep the two in step.
    """
    return (ReplenishmentRun.objects.filter(tenant=request.tenant)
            .select_related("location")
            .annotate(
                annotated_line_count=Count("lines"),
                annotated_accepted_count=Count("lines", filter=Q(lines__decision="accepted")),
                annotated_total_value=Sum(F("lines__suggested_qty") * F("lines__unit_cost")))
            .order_by("-run_date", "-id"))


def _vendor_options(request):
    """Parties this workspace can actually buy from — empty for a tenant-less user.

    The same supplier-or-vendor rule the policy and decision forms use: ``core.PartyRole``
    distinguishes ``supplier`` from ``vendor`` and workspaces use both interchangeably, so a line
    can only be re-pointed at a party it could have been pointed at in the first place.
    """
    if request.tenant is None:
        return Party.objects.none()
    return (Party.objects.filter(tenant=request.tenant, roles__role__in=("supplier", "vendor"))
            .distinct().order_by("name"))


def _released_requisitions(run):
    """The distinct draft requisitions this run raised, each with its URL reversed IN PYTHON.

    ONE query, reached backwards through the suggestion lines, so a run that was released into
    four vendor requisitions shows four rows rather than one per accepted line.
    """
    rows = (PurchaseRequisition.objects
            .filter(procurement_replenishment_suggestions__run=run)
            .distinct().order_by("number"))
    return [{"requisition": r,
             "url": reverse("scm:requisition_detail", args=[r.pk])} for r in rows]


@login_required
def replenishmentrun_list(request):
    """The register of replenishment proposals — what was planned, when, and how far it got."""
    base = ReplenishmentRun.objects.filter(tenant=request.tenant)
    # ONE conditional aggregate over the UNANNOTATED base: aggregating over _run_qs() would
    # count through its ``lines`` join and report the number of suggestion rows, not of runs.
    stats = base.aggregate(
        total=Count("pk"),
        draft=Count("pk", filter=Q(status="draft")),
        proposed=Count("pk", filter=Q(status="proposed")),
        released=Count("pk", filter=Q(status="released")),
    )
    return crud_list(
        request, _run_qs(request), TEMPLATE_LIST,
        search_fields=("number", "notes", "location__code", "location__name"),
        # crud_list already hardens these: is_int=True gets the over-range / pk=0 / non-decimal
        # guard, and the three enum filters get its CHOICES-membership check. None of that is
        # re-implemented here.
        filters=(("status", "status", False),
                 ("trigger", "trigger", False),
                 ("location", "location_id", True),
                 ("abc", "abc_class_filter", False)),
        extra_context={
            "stats": stats,
            "locations": (Location.objects.filter(tenant=request.tenant).order_by("code")
                          if request.tenant is not None else Location.objects.none()),
            "status_choices": ReplenishmentRun.STATUS_CHOICES,
            "trigger_choices": ReplenishmentRun.TRIGGER_CHOICES,
            "abc_choices": ReplenishmentRun.ABC_CHOICES,
        },
    )


@login_required
def replenishmentrun_detail(request, pk):
    """One run, as a review board: every proposed line and what was decided about it.

    Fetched with ``get_object_or_404`` + ``render`` rather than through ``crud_detail``, and the
    contract's ``obj`` key is set BY HAND to exactly what that helper would have set. Every extra
    on this page is computed FROM the run, so ``crud_detail`` would have had to fetch the same row
    a second time to hand it to the template — the ``contract_detail`` precedent
    (``apps/procurement/views/ContractsManagement/Contracts.py:78``) resolves it the same way. The
    tenant filter is identical to the helper's, so the IDOR boundary is unchanged: another
    workspace's pk is a 404, not a 403 and not a render.
    """
    obj = get_object_or_404(
        ReplenishmentRun.objects.filter(tenant=request.tenant)
        .select_related("location", "generated_by"), pk=pk)

    lines_qs = obj.lines.select_related(*_LINE_RELATIONS)
    line_page_obj = paginate(request, lines_qs, per_page=_LINES_PER_PAGE)

    # ONE conditional aggregate for the whole totals strip — five counts and a value off the same
    # table, not six round-trips. ``accepted_value`` is what the release will actually commit, so
    # it is filtered to accepted lines rather than totalling the proposal.
    totals = obj.lines.aggregate(
        line_count=Count("pk"),
        accepted=Count("pk", filter=Q(decision="accepted")),
        snoozed=Count("pk", filter=Q(decision="snoozed")),
        dismissed=Count("pk", filter=Q(decision="dismissed")),
        pending=Count("pk", filter=Q(decision="pending")),
        accepted_value=Sum(F("suggested_qty") * F("unit_cost"), filter=Q(decision="accepted")),
    )
    totals["accepted_value"] = totals["accepted_value"] or 0

    return render(request, TEMPLATE_DETAIL, {
        "obj": obj,
        "lines": line_page_obj.object_list,
        "line_page_obj": line_page_obj,
        "decision_choices": ReplenishmentSuggestion.DECISION_CHOICES,
        "vendors": _vendor_options(request),
        "totals": totals,
        # Read from the model so the button and the verb can never disagree about what is allowed.
        "can_generate": obj.can_generate,
        "can_release": obj.can_release,
        "can_cancel": obj.can_cancel,
        "requisitions": _released_requisitions(obj),
        "truncated": obj.is_truncated,
        "sku_match_note": SKU_MATCH_NOTE,
    })


@login_required
def replenishmentrun_create(request):
    return crud_create(request, form_class=ReplenishmentRunForm, template=TEMPLATE_FORM,
                       success_url="procurement:replenishmentrun_list")


@login_required
def replenishmentrun_edit(request, pk):
    """Amend a run's header — refused once it has been released or cancelled.

    Gated on ``can_generate`` (draft OR proposed) rather than on ``is_editable`` (draft only) on
    purpose: changing the scope of a run that has already proposed is harmless, because Generate
    deletes and rebuilds every line from the new scope. What is NOT harmless is re-dating or
    re-scoping a run that already raised requisitions — that turns a record of what was decided
    into a claim about something else, so it is refused here.
    """
    obj = get_object_or_404(ReplenishmentRun.objects.filter(tenant=request.tenant), pk=pk)
    if not obj.can_generate:
        messages.error(request, f"{obj.number} is {obj.get_status_display().lower()} and its "
                                f"header can no longer be changed.")
        return redirect("procurement:replenishmentrun_detail", pk=pk)
    return crud_edit(request, model=ReplenishmentRun, pk=pk, form_class=ReplenishmentRunForm,
                     template=TEMPLATE_FORM,
                     success_url="procurement:replenishmentrun_list")


@login_required
@require_POST
def replenishmentrun_delete(request, pk):
    """Delete a run and its suggestions — draft or proposed only.

    Gated on ``can_generate`` for the same reason :func:`replenishmentrun_edit` is, only harder:
    ``ReplenishmentSuggestion.run`` is ``CASCADE``, so deleting a RELEASED run destroys every line
    that says which requisition came from which proposal while the requisition rows themselves
    survive, orphaned. Both templates already hide the button behind ``can_generate`` and say the
    view refuses it anyway — this is what makes that true, and it mirrors
    :func:`materialissue_delete`, which guards its own posted documents the same way.
    """
    obj = get_object_or_404(ReplenishmentRun.objects.filter(tenant=request.tenant), pk=pk)
    if not obj.can_generate:
        messages.error(request, f"{obj.number} is {obj.get_status_display().lower()} and cannot be "
                                f"deleted. Its suggestions are the only record of which "
                                f"requisitions came from which proposal.")
        return redirect("procurement:replenishmentrun_detail", pk=pk)
    return crud_delete(request, model=ReplenishmentRun, pk=pk,
                       success_url="procurement:replenishmentrun_list")


@login_required
@require_POST
def replenishmentrun_generate(request, pk):
    """(Re)compute the proposal. Idempotent — pressing it twice replaces, never duplicates."""
    obj = get_object_or_404(ReplenishmentRun.objects.filter(tenant=request.tenant), pk=pk)
    try:
        written = obj.generate(request.user)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("procurement:replenishmentrun_detail", pk=pk)
    if written:
        messages.success(request, f"{obj.number} proposed {written} line"
                                  f"{'' if written == 1 else 's'}. Accept the ones worth buying, "
                                  f"then release.")
    else:
        messages.success(request, f"{obj.number} found nothing below its reorder point in scope. "
                                  f"That is a clean result, not a failure.")
    return redirect("procurement:replenishmentrun_detail", pk=pk)


@login_required
@tenant_admin_required
@require_POST
def replenishmentrun_release(request, pk):
    """Raise one DRAFT requisition per vendor from the accepted lines.

    ``@tenant_admin_required`` on top of ``@require_POST`` because this is the step that starts
    spending money. The requisitions are draft, so 6.3's approval routing, 6.15's budget check and
    6.10's PO conversion all still run — this view commits the workspace to *asking*, not to
    buying.
    """
    obj = get_object_or_404(ReplenishmentRun.objects.filter(tenant=request.tenant), pk=pk)
    try:
        created = obj.release(request.user)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("procurement:replenishmentrun_detail", pk=pk)
    numbers = ", ".join(r.number for r in created)
    messages.success(request, f"{obj.number} released into {len(created)} draft requisition"
                              f"{'' if len(created) == 1 else 's'}: {numbers}. Each still needs "
                              f"submitting for approval.")
    return redirect("procurement:replenishmentrun_detail", pk=pk)


@login_required
@require_POST
def replenishmentrun_cancel(request, pk):
    """Abandon a proposal. Refused once released — those requisitions are real."""
    obj = get_object_or_404(ReplenishmentRun.objects.filter(tenant=request.tenant), pk=pk)
    try:
        obj.cancel(request.user)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("procurement:replenishmentrun_detail", pk=pk)
    messages.success(request, f"{obj.number} cancelled. Its lines are kept as the record of what "
                              f"was proposed and rejected.")
    return redirect("procurement:replenishmentrun_detail", pk=pk)


@login_required
@require_POST
def replenishmentsuggestion_decide(request, pk, line_id):
    """Record the buyer's verdict on ONE proposed line.

    **The lookup below is the IDOR boundary.** ``ReplenishmentSuggestion`` has no tenant column,
    so the line is loaded by ``pk=line_id`` AND ``run__pk=pk`` AND ``run__tenant=request.tenant``:
    a line id from another workspace, or a valid line id under somebody else's run id, is a 404.
    Dropping any one of the three would make the other two decorative.

    A released line is frozen. Its requisition already carries the quantity, and letting somebody
    dismiss it afterwards would leave a requisition line nothing on this page explains.
    """
    line = get_object_or_404(
        ReplenishmentSuggestion.objects.select_related("run", "item"),
        pk=line_id, run__pk=pk, run__tenant=request.tenant)

    if line.is_released:
        messages.error(request, f"{line.item.sku} was already released into "
                                f"{line.requisition.number} — change the quantity on that "
                                f"requisition instead.")
        return redirect("procurement:replenishmentrun_detail", pk=pk)
    if not line.run.can_generate:   # draft or proposed; released/cancelled are records
        messages.error(request, f"{line.run.number} is {line.run.get_status_display().lower()} — "
                                f"its lines are a record now and cannot be re-decided.")
        return redirect("procurement:replenishmentrun_detail", pk=pk)

    form = ReplenishmentSuggestionDecisionForm(request.POST, instance=line, tenant=request.tenant)
    if not form.is_valid():
        # A verb view has nowhere to render field errors, so they are flattened onto the redirect
        # — losing the field association but never the reason, which is the part a buyer needs.
        messages.error(request, " ".join(
            f"{field}: {' '.join(errors)}" for field, errors in form.errors.items()))
        return redirect("procurement:replenishmentrun_detail", pk=pk)

    obj = form.save()
    write_audit_log(request.user, obj, "decide",
                    {"run": line.run.number, "decision": obj.decision})
    messages.success(request, f"{obj.item.sku} marked {obj.get_decision_display().lower()}.")
    return redirect("procurement:replenishmentrun_detail", pk=pk)
