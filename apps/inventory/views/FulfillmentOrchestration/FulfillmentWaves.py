"""Inventory 5.9 Order Management & Fulfillment — wave views + the planning board.

Five thin CRUD wrappers over apps.core.crud, the three lifecycle verbs, the two
membership verbs and ONE genuinely custom page: ``wave_board`` is the PRIMARY UX (the
at-a-glance multi-wave picture with derived progress columns). It owns no extra table
and writes NOTHING into scm — release/close/cancel flip only the wave's own status, and
progress is read from scm.PickTask through the wave_ref==number text convention.

Like sibling 5.4/5.5, the WRITES are tenant-admin gated (releasing a batch to the floor
and changing its membership are planner decisions): reads stay open to every signed-in
member, create/edit/delete/verbs/membership carry ``core.decorators.tenant_admin_required``,
and every template receives the same ``is_admin`` flag so it can hide affordances to
match. Membership locks once a wave leaves ``planned``; the view refuses before binding
the form so the refusal is a flash on the detail page, not a form error nobody asked for.

Ordering of operations on the board is deliberate: search + filters apply to the
queryset BEFORE pagination; pagination happens at 25/page in the database via
core.crud.paginate; only then do THREE grouped queries run over the current page's waves
(members, fulfilled members, picks by wave_ref) and merge into row dicts in Python —
stats describe the FULL filtered set via cheap counts, and no page render pays a
per-row N+1.
"""
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.utils import timezone

from apps.core.crud import as_db_int, paginate
from apps.core.decorators import tenant_admin_required
from apps.inventory.forms.FulfillmentOrchestration.FulfillmentWaves import (
    FulfillmentWaveForm,
    FulfillmentWaveOrderForm,
)
# Through the leaf module, not the package root: the models sub-package __init__
# re-exports both names (house contract), so this line keeps working unchanged after
# the integrate phase adds the app-root wiring.
from apps.inventory.models.FulfillmentOrchestration.FulfillmentWaves import (
    FulfillmentWave,
    FulfillmentWaveOrder,
    pick_progress_pct_from,
)
from apps.inventory.views._common import *  # noqa: F401,F403
from apps.scm.models import Location, PickTask, SalesOrder


def _is_admin(user):
    """The one admin flag every 5.9 template receives — same test as the decorator."""
    return bool(user.is_superuser or getattr(user, "is_tenant_admin", False))


def _scoped(tenant):
    """Tenant-scoped wave queryset with the joins every list/detail page renders."""
    return (FulfillmentWave.objects.filter(tenant=tenant)
            .select_related("location", "carrier"))


@login_required
def wave_list(request):
    qs = _scoped(request.tenant)
    # The status chip maps to a CHOICE value BEFORE crud_list runs (house filter rule:
    # parse GET, shape the queryset, THEN let the helper paginate/render it). A junk or
    # unknown ?status= skips the filter instead of obeying it — junk ignored beats an
    # silently-empty page.
    status = request.GET.get("status", "").strip()
    if status in dict(FulfillmentWave.STATUS_CHOICES):
        qs = qs.filter(status=status)
    return crud_list(
        request, qs, "inventory/fulfillment/wave/list.html",
        search_fields=["number", "description"],
        filters=(),
        extra_context={
            "status_choices": FulfillmentWave.STATUS_CHOICES,
            "status": status,
            # Writes are tenant-admin gated server-side; hide the affordances to match.
            "is_admin": _is_admin(request.user),
        },
    )


@login_required
def wave_detail(request, pk):
    obj = get_object_or_404(_scoped(request.tenant), pk=pk)
    admin = _is_admin(request.user)
    add_form = None
    if admin and obj.is_editable:
        # Tenant stamped by the mixin's __init__; the WAVE is stamped here too so
        # is_valid() validates a fully-parented row (SEC-1 stamping).
        add_form = FulfillmentWaveOrderForm(tenant=request.tenant)
        add_form.instance.wave = obj
    return render(request, "inventory/fulfillment/wave/detail.html", {
        "obj": obj,
        "members": (obj.orders.select_related("sales_order", "added_by")
                    .order_by("created_at")),
        # Picks matched through the wave_ref==number text convention — newest first.
        "linked_picks": obj.linked_picks()[:20],
        "add_form": add_form,
        "is_admin": admin,
    })


@tenant_admin_required
def wave_create(request):
    return crud_create(
        request, form_class=FulfillmentWaveForm,
        template="inventory/fulfillment/wave/form.html",
        success_url="inventory:wave_list",
    )


@tenant_admin_required
def wave_edit(request, pk):
    # Server-side status guard: the template hides Edit on non-planned waves, but a
    # crafted POST must not rewrite cutoff/carrier/criteria beneath a released batch
    # (CrossDockOrders precedent — crud_edit cannot know EDITABLE_STATUSES).
    obj = get_object_or_404(_scoped(request.tenant), pk=pk)
    if not obj.is_editable:
        messages.error(
            request,
            f"{obj.number} has been released to the floor and can no longer be edited.")
        return redirect("inventory:wave_detail", pk=obj.pk)
    return crud_edit(
        request, model=FulfillmentWave, pk=pk, form_class=FulfillmentWaveForm,
        template="inventory/fulfillment/wave/form.html",
        success_url="inventory:wave_list",
    )


@tenant_admin_required
@require_POST
def wave_delete(request, pk):
    # No ledger legs and no scm writes exist behind a wave, so deletion is safe at any
    # status; plain crud_delete suffices (it re-checks POST itself).
    return crud_delete(request, model=FulfillmentWave, pk=pk,
                       success_url="inventory:wave_list")


@tenant_admin_required
@require_POST
def wave_release(request, pk):
    return _run_action(request, pk, "release")


@tenant_admin_required
@require_POST
def wave_close(request, pk):
    return _run_action(request, pk, "close")


@tenant_admin_required
@require_POST
def wave_cancel(request, pk):
    return _run_action(request, pk, "cancel")


# -- membership --------------------------------------------------------------------------------

@tenant_admin_required
@require_POST
def waveorder_add(request, pk):
    """Add one sales order to a still-planned wave (inline detail-page form).

    The lock check runs BEFORE binding: a released/closed wave refuses with a flash,
    never a half-rendered form error. instance.wave + tenant are stamped BEFORE
    is_valid() so unique_together and the model clean() see the real parentage."""
    obj = get_object_or_404(_scoped(request.tenant), pk=pk)
    if not obj.is_editable:
        messages.error(
            request,
            f"{obj.number} is {obj.get_status_display().lower()} — its membership can "
            f"no longer be changed.")
        return redirect("inventory:wave_detail", pk=obj.pk)
    form = FulfillmentWaveOrderForm(request.POST, tenant=request.tenant)
    form.instance.wave = obj
    if form.is_valid():
        member = form.save(commit=False)
        member.added_by = request.user
        member.save()
        write_audit_log(request.user, member, "create")
        messages.success(request, f"{member.sales_order.number} added to {obj.number}.")
    else:
        errors = "; ".join(e for bucket in form.errors.values() for e in bucket)
        messages.error(request, errors or "That order could not be added.")
    return redirect("inventory:wave_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def waveorder_remove(request, pk, order_pk):
    """Remove one membership row from a still-planned wave."""
    obj = get_object_or_404(_scoped(request.tenant), pk=pk)
    if not obj.is_editable:
        messages.error(
            request,
            f"{obj.number} is {obj.get_status_display().lower()} — its membership can "
            f"no longer be changed.")
        return redirect("inventory:wave_detail", pk=obj.pk)
    member = FulfillmentWaveOrder.objects.filter(wave=obj, pk=order_pk).first()
    if member is None:
        messages.error(request, "That sales order is not part of this wave.")
        return redirect("inventory:wave_detail", pk=obj.pk)
    number = member.sales_order.number
    write_audit_log(request.user, member, "delete")
    member.delete()
    messages.success(request, f"{number} removed from {obj.number}.")
    return redirect("inventory:wave_detail", pk=obj.pk)


# -- computed pages ------------------------------------------------------------------------------

@login_required
def wave_board(request):
    """The Wave Planning board: every wave with its derived progress columns.

    Read-only by construction. Rows for the PAGE carry precomputed counts merged from
    three grouped queries; the stats strip counts over the FULL filtered queryset, so
    the strip always describes the whole queue rather than the visible page."""
    qs = _scoped(request.tenant)

    # --- filters BEFORE pagination -------------------------------------------------------
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(description__icontains=q))

    # ?status= obeys only real STATUS_CHOICES values; ?location= goes through the
    # as_db_int guard (?location=abc / ² / <2^63> are all "not a pk" and skip the
    # filter instead of raising inside the driver, L11) plus an exists() check, because
    # an unknown-but-valid pk is treated exactly the same way.
    status = request.GET.get("status", "").strip()
    if status in dict(FulfillmentWave.STATUS_CHOICES):
        qs = qs.filter(status=status)

    location_raw = request.GET.get("location", "").strip()
    location_pk = as_db_int(location_raw)
    if location_pk is not None and Location.objects.filter(
            tenant=request.tenant, pk=location_pk).exists():
        qs = qs.filter(location_id=location_pk)

    # --- paginate FIRST, then precompute ---------------------------------------------------
    page_obj = paginate(request, qs, 25)
    waves = list(page_obj.object_list)
    wave_ids = [w.pk for w in waves]

    member_counts, fulfilled_counts, pick_stats = {}, {}, {}
    if wave_ids:
        member_counts = dict(FulfillmentWaveOrder.objects.filter(wave_id__in=wave_ids)
                             .values("wave").annotate(n=Count("id"))
                             .values_list("wave", "n"))
        fulfilled_counts = dict(
            FulfillmentWaveOrder.objects.filter(
                wave_id__in=wave_ids,
                sales_order__status__in=FulfillmentWave.FULFILLED_STATUSES)
            .values("wave").annotate(n=Count("id")).values_list("wave", "n"))
        numbers = [w.number for w in waves if w.number]
        if numbers:
            for ref, total, done, active in (
                    PickTask.objects.filter(tenant=request.tenant, wave_ref__in=numbers)
                    .values("wave_ref")
                    .annotate(total=Count("id"),
                              done=Count("id", filter=Q(status__in=FulfillmentWave.PICK_DONE_STATUSES)),
                              active=Count("id", filter=~Q(status="cancelled")))
                    .values_list("wave_ref", "total", "done", "active")):
                pick_stats[ref] = (total, done, active)

    rows = []
    for wave in waves:
        total, done, active = pick_stats.get(wave.number, (0, 0, 0))
        rows.append({
            "wave": wave,
            "members": member_counts.get(wave.pk, 0),
            "fulfilled": fulfilled_counts.get(wave.pk, 0),
            # None when no picks match yet — rendered as "—", never a fake 0%.
            "pick_pct": pick_progress_pct_from(done, active) if total else None,
        })

    stats = {
        "open_waves": qs.filter(status="planned").count(),
        "released_today": qs.filter(status="released",
                                    released_at__date=timezone.localdate()).count(),
        # Open-sellable orders (4.5's own allocatable vocabulary) not yet waved anywhere
        # — one query: NOT IN over the tenant's membership rows.
        "unassigned_orders": (
            SalesOrder.objects
            .filter(tenant=request.tenant, status__in=SalesOrder.ALLOCATABLE_STATUSES)
            .exclude(pk__in=FulfillmentWaveOrder.objects
                     .filter(tenant=request.tenant).values("sales_order_id"))
            .count()),
    }

    locations = Location.objects.none()
    if request.tenant is not None:
        locations = (Location.objects.filter(tenant=request.tenant,
                                             location_type="warehouse")
                     .order_by("code"))

    return render(request, "inventory/fulfillment/wave_board.html", {
        "object_list": rows,
        "page_obj": page_obj,
        "stats": stats,
        "status_choices": FulfillmentWave.STATUS_CHOICES,
        "status": status,
        "locations": locations,
        "location": location_raw,
        "q": q,
        "is_admin": _is_admin(request.user),
    })


# -- module-private helpers ------------------------------------------------------------------------

_ACTION_MESSAGES = {
    "release": "released to the floor.",
    "close": "closed.",
    "cancel": "cancelled.",
}


def _run_action(request, pk, action):
    """Run one lifecycle verb and turn its refusal into a flash message.

    The success/error split is deliberate: a refusal is EXPECTED traffic (double-click,
    stale tab, someone else got there first), so it lands as a message on the detail
    page rather than an exception page. The audit row is written by the model INSIDE
    its transaction."""
    obj = get_object_or_404(FulfillmentWave, pk=pk, tenant=request.tenant)
    try:
        getattr(obj, action)(request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, f"{obj.number} {_ACTION_MESSAGES[action]}")
    return redirect("inventory:wave_detail", pk=obj.pk)
