"""Procurement 6.18 Inventory & Warehouse Integration — MaterialIssue views.

The **Goods Issue / Return to Stock** surface: a register of consumption documents, a detail page
that doubles as the line editor, and the four verbs that move a document through
``draft → submitted → posted`` (or ``cancelled``).

Discipline a reviewer will otherwise go looking for:

* **Every queryset is ``filter(tenant=request.tenant)``** — never ``.all()``. Lines carry no tenant
  column of their own, so theirs is reached THROUGH the header (``issue__tenant``), and
  :func:`materialissueline_delete` loads its line as
  ``pk=line_id, issue__pk=pk, issue__tenant=request.tenant`` — **that compound lookup IS the IDOR
  boundary**, not a convenience. A tenant-less user gets an EMPTY page, never a 500.
* **The stats strip is ONE conditional aggregate.** Six ``COUNT`` round-trips for six numbers off
  the same table is exactly the shape the performance rule exists to stop.
* **``_post`` is ``@tenant_admin_required``** on top of ``@require_POST``: posting mints a stock
  adjustment, and that document is one SCM click away from moving real stock. Decorator order in
  this app is ``@login_required`` → ``@tenant_admin_required`` → ``@require_POST``.
* **``availability`` is ONE grouped query for the whole document** (``obj.on_hand_at_location``),
  so every line shows its shortfall flag *before* anybody presses Post — rather than one aggregate
  per row, which is the same page at N times the cost.
* **Every URL that depends on a nullable row is ``reverse()``d in Python.** ``adjustment_url`` is
  ``None`` until the document is posted; a ``{% url %}`` tag on a null pk is a ``NoReverseMatch``
  500 rather than a blank cell.
* **The two boundary notes are context, not template prose.** ``boundary_note`` (return to STOCK is
  this document, return to VENDOR is 6.12) and ``ledger_note`` (the minted adjustment is DRAFT) are
  the two things a user can get expensively wrong here, so they are written once, in Python, with
  their links reversed there too.
"""
from django.core.exceptions import ValidationError
from django.db.models import Count, F, Q, Sum
from django.urls import reverse

from apps.core.models import OrgUnit
from apps.scm.models import Location

from apps.procurement.forms.InventoryWarehouseIntegration.MaterialIssues import (
    MaterialIssueForm, MaterialIssueLineForm)
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.InventoryWarehouseIntegration.MaterialIssues import (MaterialIssue,
                                                                                  MaterialIssueLine)
from apps.procurement.views._common import *  # noqa: F401,F403

TEMPLATE_LIST = "procurement/inventorywarehouse/materialissue/list.html"
TEMPLATE_DETAIL = "procurement/inventorywarehouse/materialissue/detail.html"
TEMPLATE_FORM = "procurement/inventorywarehouse/materialissue/form.html"

#: The detail page renders each line's item, its unit of measure, the lot and the expense account.
_LINE_RELATIONS = ("item", "item__uom", "lot_serial", "gl_account")

#: The single most expensive mistake available on this page, so it is said in words rather than
#: left to the reader to infer from a movement-type dropdown. Its link is reversed in the view.
BOUNDARY_NOTE_TEXT = (
    "Return to STOCK is this document: material that was drawn for a job and came back unused, "
    "going onto the same shelf it came off. Returning goods to a SUPPLIER is a different document "
    "entirely — 6.12's Return to Vendor [RMA-], which ships the goods off site and expects a "
    "credit note against the purchase. Filing one as the other leaves either stock on hand that "
    "nobody can find, or a vendor credit nobody ever claims.")

#: The other one: what posting does and, more importantly, what it does NOT do.
LEDGER_NOTE_TEXT = (
    "Posting this document does not move stock. It mints a DRAFT stock adjustment in SCM, signed "
    "for the direction of this document, and stamps it here as the provenance of the movement. "
    "Stock actually changes when somebody posts THAT adjustment — which is deliberate: one code "
    "path writes the stock ledger and it lives in the app that owns it.")


def _is_admin(request):
    """Mirrors @tenant_admin_required exactly, so a hidden button and a refused POST agree.

    The local-copy convention: every peer sub-module in this app carries its own one-line copy
    rather than importing another entity module's private name.
    """
    return bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False))


def _issue_qs(request):
    """The register's base queryset: tenant-scoped, joined and counted in ONE query.

    The ``Count`` and the ``Sum`` ride the SAME ``lines`` join, so there is no fan-out to worry
    about — that only happens across two DIFFERENT multi-valued relations. The annotations carry
    ``annotated_*`` names because ``total_value`` is a ``@property``, a data descriptor: a
    same-named annotation would be written to the instance ``__dict__`` and then SILENTLY IGNORED
    on read, leaving a register that quietly costs an extra query per row.

    **The explicit ``order_by`` is not redundant — it is load-bearing.** Since Django 3.1
    ``Meta.ordering`` is deliberately NOT applied to a GROUP BY query, and ``annotate()`` with an
    aggregate makes this one. Without the call below the register's SQL carries **no ORDER BY at
    all**, and paginating an unordered queryset means a row can show up on page 1 and again on
    page 2, or never appear. Measured, not assumed: ``str(qs.query)`` contains no ``ORDER BY``
    without it, and ``qs.ordered`` is ``False``. The tuple repeats ``Meta.ordering`` exactly.
    """
    return (MaterialIssue.objects.filter(tenant=request.tenant)
            .select_related("location", "org_unit")
            .annotate(
                annotated_line_count=Count("lines"),
                annotated_total_value=Sum(F("lines__quantity") * F("lines__unit_cost")))
            .order_by("-issue_date", "-id"))


@login_required
def materialissue_list(request):
    """The register of consumption documents — what left the shelf, for what, and how far it got."""
    base = MaterialIssue.objects.filter(tenant=request.tenant)
    # ONE conditional aggregate over the UNANNOTATED base: aggregating over _issue_qs() would count
    # through its ``lines`` join and report the number of LINE rows, not of documents.
    stats = base.aggregate(
        total=Count("pk"),
        draft=Count("pk", filter=Q(status="draft")),
        submitted=Count("pk", filter=Q(status="submitted")),
        posted=Count("pk", filter=Q(status="posted")),
        issues=Count("pk", filter=Q(movement_type="issue")),
        returns=Count("pk", filter=Q(movement_type="return")),
    )
    return crud_list(
        request, _issue_qs(request), TEMPLATE_LIST,
        search_fields=("number", "reference", "notes",
                       "location__code", "location__name", "org_unit__name"),
        # crud_list already hardens these: is_int=True gets the over-range / pk=0 / non-decimal
        # guard, and the three enum filters get its CHOICES-membership check. None of that is
        # re-implemented here.
        filters=(("status", "status", False),
                 ("movement_type", "movement_type", False),
                 ("purpose", "purpose", False),
                 ("location", "location_id", True),
                 ("org_unit", "org_unit_id", True)),
        extra_context={
            "stats": stats,
            "locations": (Location.objects.filter(tenant=request.tenant).order_by("code")
                          if request.tenant is not None else Location.objects.none()),
            "org_units": (OrgUnit.objects.filter(tenant=request.tenant).order_by("name")
                          if request.tenant is not None else OrgUnit.objects.none()),
            "status_choices": MaterialIssue.STATUS_CHOICES,
            "movement_choices": MaterialIssue.MOVEMENT_TYPE_CHOICES,
            "purpose_choices": MaterialIssue.PURPOSE_CHOICES,
        },
    )


@login_required
def materialissue_detail(request, pk):
    """One document, its lines, and — before anything is posted — what the shelf actually holds.

    Fetched with ``get_object_or_404`` + ``render`` rather than through ``crud_detail``, and the
    contract's ``obj`` key is set BY HAND to exactly what that helper would have set. Every extra on
    this page is computed FROM the document (the availability map, the totals, the line form's
    tenant), so ``crud_detail`` would have had to fetch the same row a second time to hand it to the
    template — the ``contract_detail`` precedent
    (``apps/procurement/views/ContractsManagement/Contracts.py:78``) and this sub-module's own
    ``replenishmentrun_detail`` both resolve it the same way. The tenant filter is identical to the
    helper's, so the IDOR boundary is unchanged: another workspace's pk is a 404, not a render.

    ``availability`` is ONE grouped query covering every item on the document, so a shortfall is
    visible on the page rather than only as a refusal after pressing Post.
    """
    obj = get_object_or_404(
        MaterialIssue.objects.filter(tenant=request.tenant)
        .select_related("location", "org_unit", "gl_account", "requested_by", "issued_by",
                        "adjustment", "reservation", "reservation__item", "reservation__location"),
        pk=pk)

    lines = list(obj.lines.select_related(*_LINE_RELATIONS))
    availability = obj.on_hand_at_location([line.item_id for line in lines])

    # The shortfall flag is computed PER ITEM ACROSS THE DOCUMENT, not per line — the same
    # aggregation ``post()`` does before it refuses (``MaterialIssues.py:322-325``). There is no
    # unique_together on (issue, item) and the model says duplicate lines are expected, so two
    # lines of 6 against 10 on hand each look fine on their own while the document as a whole
    # wants 12. Flagging per line left both rows unmarked and then had Post refuse with "only 10
    # available … cannot issue 12", which is exactly the surprise the On-hand column exists to
    # prevent.
    demand = {}
    for line in lines:
        demand[line.item_id] = demand.get(line.item_id, 0) + (line.quantity or 0)

    # The figures are ALSO attached to each line, because a Django template cannot index a dict by
    # a variable key — ``{{ availability[line.item_id] }}`` has no template equivalent. The dict
    # stays in the context (it is the contract's key, and it is what a test asserts against); the
    # per-line attributes are how the table actually renders. A return has no shortfall by
    # definition: it ADDS stock, so ``is_short`` is only ever meaningful on an issue.
    for line in lines:
        line.on_hand = availability.get(line.item_id, 0)
        line.document_demand = demand.get(line.item_id, 0)
        line.is_short = obj.is_issue and line.document_demand > line.on_hand

    return render(request, TEMPLATE_DETAIL, {
        "obj": obj,
        "lines": lines,
        # Unbound, tenant-narrowed, built once — the add-a-line row at the foot of the table.
        "line_form": MaterialIssueLineForm(tenant=request.tenant),
        "total_value": obj.total_value,
        "adjustment": obj.adjustment,
        # Reversed in Python because it is None until the document is posted, and {% url %} on a
        # null pk is a NoReverseMatch 500 rather than a blank cell.
        "adjustment_url": (reverse("scm:stockadjustment_detail", args=[obj.adjustment_id])
                           if obj.adjustment_id else None),
        "availability": availability,
        # Read from the model so a button and its verb can never disagree about what is allowed.
        "can_submit": obj.can_submit,
        # Post is the one verb here that is @tenant_admin_required, so the flag carries that term
        # too: on the status flag alone a plain member saw the button, confirmed the dialog and
        # got a PermissionDenied. The decorator stays the enforcement — this only stops the page
        # OFFERING an action that is guaranteed to be refused.
        "can_post": obj.can_post and _is_admin(request),
        "can_cancel": obj.can_cancel,
        "can_edit": obj.can_edit,
        "boundary_note": {"text": BOUNDARY_NOTE_TEXT,
                          "url": reverse("procurement:rtv_list"),
                          "link_label": "Returns to vendor (6.12)"},
        "ledger_note": {"text": LEDGER_NOTE_TEXT,
                        "url": reverse("scm:stockadjustment_list"),
                        "link_label": "Stock adjustments (SCM)"},
    })


@login_required
def materialissue_create(request):
    return crud_create(request, form_class=MaterialIssueForm, template=TEMPLATE_FORM,
                       success_url="procurement:materialissue_list")


@login_required
def materialissue_edit(request, pk):
    """Amend a document's header — draft only.

    Once submitted, the header is what somebody is about to post; once posted, it is the evidence
    for a stock movement. Re-pointing either at a different location or purpose after the fact
    would turn a record of what happened into a claim about something else.
    """
    obj = get_object_or_404(MaterialIssue.objects.filter(tenant=request.tenant), pk=pk)
    if not obj.can_edit:
        messages.error(request, f"{obj.number} is {obj.get_status_display().lower()} and can no "
                                f"longer be changed.")
        return redirect("procurement:materialissue_detail", pk=pk)
    return crud_edit(request, model=MaterialIssue, pk=pk, form_class=MaterialIssueForm,
                     template=TEMPLATE_FORM,
                     success_url="procurement:materialissue_list")


@login_required
@require_POST
def materialissue_delete(request, pk):
    """Delete a document — draft only. A posted one is corrected by a mirror return, never removed."""
    obj = get_object_or_404(MaterialIssue.objects.filter(tenant=request.tenant), pk=pk)
    if not obj.can_edit:
        messages.error(request, f"{obj.number} is {obj.get_status_display().lower()} and cannot be "
                                f"deleted. A posted issue has minted a stock adjustment — correct "
                                f"it with a return against the same location.")
        return redirect("procurement:materialissue_detail", pk=pk)
    return crud_delete(request, model=MaterialIssue, pk=pk,
                       success_url="procurement:materialissue_list")


@login_required
@require_POST
def materialissue_submit(request, pk):
    """Draft → submitted: the document is finished and waiting for someone to post it."""
    obj = get_object_or_404(MaterialIssue.objects.filter(tenant=request.tenant), pk=pk)
    try:
        obj.submit(request.user)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("procurement:materialissue_detail", pk=pk)
    messages.success(request, f"{obj.number} submitted. Posting it will mint a draft stock "
                              f"adjustment — stock still does not move until SCM posts that.")
    return redirect("procurement:materialissue_detail", pk=pk)


@login_required
@tenant_admin_required
@require_POST
def materialissue_post(request, pk):
    """Mint the DRAFT ``scm.StockAdjustment`` this document becomes.

    ``@tenant_admin_required`` on top of ``@require_POST`` because this is the step that puts a
    stock movement one click away. It writes no ``StockMove`` itself — SCM's post action on the
    minted adjustment does that — but a document that reaches SCM as ready-to-post is exactly as
    consequential as one that moved the stock itself, minus the second pair of eyes.

    A shortfall arrives as a ``ValidationError`` carrying ONE MESSAGE PER SHORT ITEM, so the store
    person sees every problem at once instead of discovering them one refused post at a time.
    """
    obj = get_object_or_404(MaterialIssue.objects.filter(tenant=request.tenant), pk=pk)
    try:
        adjustment = obj.post(request.user)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("procurement:materialissue_detail", pk=pk)
    messages.success(request, f"{obj.number} posted and minted stock adjustment "
                              f"{adjustment.number} as a DRAFT. Stock changes when that adjustment "
                              f"is posted in SCM, not now.")
    return redirect("procurement:materialissue_detail", pk=pk)


@login_required
@require_POST
def materialissue_cancel(request, pk):
    """Abandon an unposted document. Refused once posted — that one is corrected by a return."""
    obj = get_object_or_404(MaterialIssue.objects.filter(tenant=request.tenant), pk=pk)
    try:
        obj.cancel(request.user)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("procurement:materialissue_detail", pk=pk)
    messages.success(request, f"{obj.number} cancelled. Its lines are kept as the record of what "
                              f"was going to be {'issued' if obj.is_issue else 'returned'}.")
    return redirect("procurement:materialissue_detail", pk=pk)


@login_required
@require_POST
def materialissueline_add(request, pk):
    """Add one item to a draft document.

    ``form.instance.issue`` is set BEFORE ``is_valid()`` on purpose: ``MaterialIssueLine.clean()``
    reaches its tenant through the issue and checks the lot belongs to the chosen item, and neither
    check can run against an unattached line. Setting it here — from the URL, never from a POSTed
    field — is also what stops a line being filed onto somebody else's document.
    """
    obj = get_object_or_404(MaterialIssue.objects.filter(tenant=request.tenant), pk=pk)
    if not obj.can_edit:
        messages.error(request, f"{obj.number} is {obj.get_status_display().lower()} — its lines "
                                f"can no longer be changed.")
        return redirect("procurement:materialissue_detail", pk=pk)

    form = MaterialIssueLineForm(request.POST, tenant=request.tenant)
    form.instance.issue = obj
    if not form.is_valid():
        # A verb view has nowhere to render field errors, so they are flattened onto the redirect —
        # losing the field association but never the reason, which is the part a user needs.
        messages.error(request, " ".join(
            f"{field}: {' '.join(errors)}" for field, errors in form.errors.items()))
        return redirect("procurement:materialissue_detail", pk=pk)

    line = form.save()
    write_audit_log(request.user, obj, "line_add",
                    {"item": line.item.sku, "quantity": str(line.quantity)})
    messages.success(request, f"{line.item.sku} × {line.quantity} added, valued at "
                              f"{line.unit_cost} each.")
    return redirect("procurement:materialissue_detail", pk=pk)


@login_required
@require_POST
def materialissueline_delete(request, pk, line_id):
    """Remove one line from a draft document.

    **The lookup below is the IDOR boundary.** ``MaterialIssueLine`` has no tenant column, so the
    line is loaded by ``pk=line_id`` AND ``issue__pk=pk`` AND ``issue__tenant=request.tenant``: a
    line id from another workspace, or a valid line id under somebody else's document id, is a 404.
    Dropping any one of the three would make the other two decorative.
    """
    obj = get_object_or_404(MaterialIssue.objects.filter(tenant=request.tenant), pk=pk)
    line = get_object_or_404(MaterialIssueLine.objects.select_related("item"),
                             pk=line_id, issue__pk=pk, issue__tenant=request.tenant)
    if not obj.can_edit:
        messages.error(request, f"{obj.number} is {obj.get_status_display().lower()} — its lines "
                                f"can no longer be changed.")
        return redirect("procurement:materialissue_detail", pk=pk)
    sku = line.item.sku
    line.delete()
    write_audit_log(request.user, obj, "line_delete", {"item": sku})
    messages.success(request, f"{sku} removed from {obj.number}.")
    return redirect("procurement:materialissue_detail", pk=pk)
