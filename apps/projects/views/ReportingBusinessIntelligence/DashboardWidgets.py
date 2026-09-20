"""Projects 7.16 Reporting & Business Intelligence — DashboardWidget views (the four tile verbs).

A tile is the unnumbered child of a board (A1.3), so this module owns exactly four routes: append one
to a board, edit its definition, remove it, and shuffle it a single slot up or down. **Nothing here
computes a figure** — a tile's value arrives from ``analytics.compute_widget`` when
``projects/reporting/_widget_grid.html`` renders it on ``pdb_detail``, which is also the only page that
links into any of these four routes. What this module writes is a definition and a ``position``.

All four are hand-written rather than ``crud_*`` (R9, B2.5), and both halves of that are load-bearing:
the success target is the PARENT board and needs the parent's pk, while ``crud_edit``/``crud_delete``
call bare ``redirect(success_url)`` (verified ``apps/core/crud.py:221``/``:247`` — a bare name would
raise ``NoReverseMatch`` on the one path that has to work); and their fetch is ``tenant=`` only
(verified ``apps/core/crud.py:213`` and ``:241``) — "any tile in my workspace", which for a CHILD row is
not the ACL at all, because a tile can sit under a board its finder may not see.

Four rules every shape below exists to keep:

* **visibility** (R7) — all four resolve the parent dashboard through
  ``analytics.visible_dashboards(request)`` and 404 from there. A tile the caller cannot reach through
  its board does not exist for them: **404, never a 403**. There is no 403 anywhere in this sub-module,
  and on the two POST-only routes ``@require_POST`` answers a wrong verb with a 405 while
  ``@login_required`` stays outermost (B1.7, D20).
* **``position`` is written here and nowhere else** — A2.4 keeps the column off the form's field list so
  a hand-typed number cannot interleave two tiles, ``wdg_create`` appends ``max + 1``, and ``wdg_move``
  is the only mover. ``wdg_edit`` therefore re-saves a row whose position it must not touch, which is
  also why the swap below is the module's only queryset write.
* **the write split (B2.3) with its one pinned exception** — every write here is ``obj.save()`` /
  ``obj.delete()`` so ``updated_at`` (``auto_now``, verified
  ``apps/projects/models/ReportingBusinessIntelligence/DashboardWidgets.py:72``) stays honest, EXCEPT
  ``wdg_move``'s two-position swap, which B2.5 pins as two ``.update()`` calls inside one
  ``transaction.atomic()``. That exception is the same rule as ``rep_favorite`` rather than a
  contradiction of it: ``updated_at`` on this table means "somebody changed what this tile SAYS", and
  clicking an arrow does not. ``analytics.renumber_tiles`` — the tie repair — is itself a ``bulk_update``
  (verified ``apps/projects/analytics.py:2150``), so both branches of the move agree on that.
* **BF-1 lands here too** (``.claude/tasks/review-projects-7.16.md`` §BF-1). The gate on all four verbs
  is *visibility*, inherited from the board, so **a plain member may add, re-word, reorder and delete
  tiles on a SHARED board they can neither edit nor delete** — ``pdb_detail``'s ``can_edit`` (verified
  ``apps/projects/views/ReportingBusinessIntelligence/ProjectDashboards.py:315``) only decides which
  buttons that page draws, and no view consults it. That is R7 and B2.5's pinned fetch reproduced
  faithfully rather than a deviation from it, and changing the authorization model is Phase 4/5's call,
  not this module's — so nothing below enforces a role, and the sentence is here so the next reader
  finds the rule in the code as well as in the file.
"""
from django.db import transaction
from django.db.models import Max
from django.urls import reverse

from apps.projects import analytics
from apps.projects.forms.ReportingBusinessIntelligence.DashboardWidgets import DashboardWidgetForm
from apps.projects.models import DashboardWidget
from apps.projects.views._common import (
    get_object_or_404, login_required, messages, redirect, render, require_POST, write_audit_log,
)
from apps.projects.views._helpers import redirect_back_or

#: One template for both verbs (B4.1) — the two-entity page that names its parent board and whose
#: Cancel returns there, which is what ``cancel_url`` in :func:`_widget_context` is for.
TEMPLATE_FORM = "projects/reporting/widget/form.html"

#: B3.1's grid cap, read rather than re-typed: ``_widget_grid`` slices the board to the same number, so
#: an un-capped create would mint tiles the page cannot show — tiles that are then invisible to the
#: delete arrow and quietly occupy the board. ``wdg_create`` refuses past it (B3.1's own row).
TILE_LIMIT = analytics.MAX_TILES_PER_DASHBOARD

#: ``direction`` → the neighbour lookup, as the two B2.5 pins per verb: the strict comparator the tile
#: moves toward, and the order that finds the CLOSEST row on the far side of it. ``up`` reads
#: ``-position`` because the neighbour wanted is the highest position still below this one; the bare
#: ``id`` tail is the tiebreak ``Meta.ordering`` uses (verified
#: ``apps/projects/models/ReportingBusinessIntelligence/DashboardWidgets.py:75``). The two keys ARE the
#: junk guard: anything else misses this dict (L11), so a typo cannot reach a write.
#:
#: The third and fourth entries of each row are the TIE pair — the same comparator on ``id`` and its
#: order — used only when the strict positional lookup finds nothing (see :func:`wdg_move`).
MOVE_DIRECTIONS = {
    "up": ("position__lt", ("-position", "id"), "id__lt", ("-id",)),
    "down": ("position__gt", ("position", "id"), "id__gt", ("id",)),
}

#: ``_NO_OBJ`` rather than ``obj=None``: B2.5 pins ``obj`` as a ``wdg_edit``-only key, and a ``None``
#: passed by ``wdg_create`` would still be a key — the exact blank-region-at-200 shape (L8) this
#: sentinel exists to make impossible.
_NO_OBJ = object()


# ---------------------------------------------------------------------------------
# shared builders
# ---------------------------------------------------------------------------------
def _widget_context(dashboard, *, form, is_edit, obj=_NO_OBJ):
    """The ONE context behind ``wdg_create`` and ``wdg_edit`` — the drift guard B2.5 exists for.

    Both verbs render ``widget/form.html``, so anything the page reads must come from one builder: two
    copies of the choice lists is how an edit page stops offering a window the add page still lists, or
    how the metric↔chart JS hint (D23: ``chart_rules`` lives on these two pages and nowhere else in the
    sub-module) goes missing from one of them.

    ``form`` is passed in rather than built here because only the caller knows whether it is bound
    (a POST that failed validation must re-render the user's own values and their errors, B2.5's
    error-rendering paragraph). ``range_choices`` is the preset six from ``analytics.PRESET_RANGES``,
    not the model's seven: ``custom`` is un-saveable on a tile (A1.3 rule 4) and the form narrows its
    own dropdown to the same list (verified
    ``apps/projects/forms/ReportingBusinessIntelligence/DashboardWidgets.py:24``). The other three
    choice keys are the model's own class attributes (verified
    ``apps/projects/models/ReportingBusinessIntelligence/DashboardWidgets.py:35-38``) — the same lists
    the fields carry, exposed so a hand-rolled option row on the template reads one source.

    ``obj`` is added ONLY when a widget was handed in, which is only ``wdg_edit``; ``is_edit`` and
    ``obj`` therefore cannot disagree, because both come from the one argument.
    """
    ctx = {
        "form": form,
        "is_edit": is_edit,
        "dashboard": dashboard,
        "metric_choices": DashboardWidget.WIDGET_METRIC_CHOICES,
        "chart_choices": DashboardWidget.CHART_CHOICES,
        "size_choices": DashboardWidget.SIZE_CHOICES,
        "range_choices": analytics.PRESET_RANGES,
        "chart_rules": analytics.chart_rules(),
        "cancel_url": reverse("projects:pdb_detail", args=[dashboard.pk]),
    }
    if obj is not _NO_OBJ:
        ctx["obj"] = obj
    return ctx


def _visible_tile(request):
    """R7's ONE tile fetch, shared by the three routes whose ``pk`` is a widget's.

    Two clauses, and they are not redundant even though both can 404 the same row:
    ``dashboard__in=analytics.visible_dashboards(request)`` is the ACL — it refuses a tile parked under
    a colleague's private board, and it is the clause ``crud_edit``/``crud_delete`` do not have.
    ``tenant=request.tenant`` is defence in depth over the denormalised column (A1.3 pins
    ``widget.tenant`` as a copy of ``dashboard.tenant`` that ``clean()`` keeps agreeing): it refuses a
    row whose own tenant disagrees with its board's, which the board clause alone would let through.
    ``visible_dashboards`` is itself tenant-scoped and answers ``none()`` for a tenant-less caller
    (verified ``apps/projects/analytics.py:217-219``), so the superuser ``admin`` 404s here rather than
    seeing every workspace's tiles — but say plainly what this shape does NOT prove: it never turns a
    visible-but-not-owned row away. Visibility is the whole gate (see the BF-1 note in the docstring).
    """
    return DashboardWidget.objects.filter(
        tenant=request.tenant,
        dashboard__in=analytics.visible_dashboards(request),
    )


def _board_full(dashboard, tenant):
    """B3.1's cap, as a count on the board's own tiles — the same tenant-narrowed read the grid uses.

    Counted rather than summed from the aggregate the append needs: the cap is about how many rows the
    page can DISPLAY, and ``_widget_grid`` slices at ``MAX_TILES_PER_DASHBOARD`` (verified
    ``apps/projects/views/ReportingBusinessIntelligence/ProjectDashboards.py:180``).
    """
    return dashboard.widgets.filter(tenant=tenant).count() >= TILE_LIMIT


# ---------------------------------------------------------------------------------
# the tile form (GET + POST)
# ---------------------------------------------------------------------------------
@login_required
def wdg_create(request, pk):
    """Append a tile to the board the URL names. **This ``pk`` is the dashboard's** (B1.5).

    The parent fetch is the ACL and it is also the whole tenant story: a tenant-less superuser gets
    ``none()`` from ``visible_dashboards`` and 404s here, so unlike ``pdb_create`` this view needs no
    ``request.tenant is None`` branch of its own (the one ``crud_create`` carries is at
    ``apps/core/crud.py:189``). No ``@require_POST`` (B1.7) — this is a form view and ``crud_*``-style
    branching on ``request.method`` is the app's shape for one.

    Three columns the form has no field for are stamped here (A2.4): ``tenant`` copied from the PARENT
    (not from ``request.tenant`` — the two are equal only because the fetch above made them so, and the
    parent is the value the row's own ``clean()`` compares against), ``dashboard`` fixed by the URL, and
    ``position`` = max + 1, 1-based because ``analytics.renumber_tiles`` renumbers 1-based too (verified
    ``apps/projects/analytics.py:2145``). ``aggregate`` answers ``{"m": None}`` on an empty board, hence
    the ``or 0``; a hand-inserted row with ``position=0`` still lands ahead of the first appended tile
    and the next move repairs it.
    """
    dashboard = get_object_or_404(analytics.visible_dashboards(request), pk=pk)
    if request.method == "POST" and _board_full(dashboard, request.tenant):
        # Refused BEFORE the form is built, so nothing is written and the board cannot gain a 25th row
        # the grid will not draw. Rides ``messages`` because B2.5 pins no context key for a "board is
        # full" banner on this page.
        messages.error(request, f"A board shows at most {TILE_LIMIT} tiles. Remove one before adding another.")
        return redirect("projects:pdb_detail", pk=dashboard.pk)

    if request.method == "POST":
        form = DashboardWidgetForm(request.POST, request.FILES, tenant=request.tenant)
        if form.is_valid():
            widget = form.save(commit=False)
            widget.tenant = dashboard.tenant
            widget.dashboard = dashboard
            widget.position = (
                dashboard.widgets.aggregate(m=Max("position"))["m"] or 0) + 1
            # .save(), and not a .update(): a brand-new tile's created_at/updated_at must be its own
            # birth, and auto_now_add/auto_now only fire on the instance path.
            widget.save()
            write_audit_log(request.user, widget, "create",
                            changes={"dashboard": str(dashboard.pk)})
            messages.success(request, "Tile added.")
            return redirect("projects:pdb_detail", pk=dashboard.pk)
        # Invalid POST falls through to the SAME render as the GET, with the bound form: the
        # metric↔chart refusal (A2.4) and the window refusal (A1.3 rule 4) both surface here, and a
        # redirect instead would look like a dead button (B2.5's error-rendering paragraph).
    else:
        form = DashboardWidgetForm(tenant=request.tenant)
    return render(request, TEMPLATE_FORM,
                  _widget_context(dashboard, form=form, is_edit=False))


@login_required
def wdg_edit(request, pk):
    """Re-word a tile. Its board and its slot are both out of reach here (B2.5).

    ``crud_edit`` is not used for the two reasons in this module's docstring: its ``get_object_or_404``
    is tenant-only (``apps/core/crud.py:213``) and its redirect cannot name the parent. The POST/GET
    shape below is its shape, deliberately, minus the ``success_url`` problem — the target is resolved
    with the board's pk, which the fetched row already carries (``select_related`` keeps that read off
    a second query).

    No cross-dashboard move is offered: ``dashboard`` is not on the form (A2.4) and this view never
    assigns it, so moving a tile between boards has no route in 7.16 at all. Same for ``position``:
    editing a title cannot reshuffle a board, and ``updated_at`` moves because the definition changed.
    """
    obj = get_object_or_404(_visible_tile(request).select_related("dashboard"), pk=pk)
    if request.method == "POST":
        form = DashboardWidgetForm(
            request.POST, request.FILES, instance=obj, tenant=request.tenant)
        if form.is_valid():
            # form.save() → instance.save(); auto_now is the point of this path (B2.3's split).
            widget = form.save()
            write_audit_log(request.user, widget, "update",
                            changes={"dashboard": str(widget.dashboard_id)})
            messages.success(request, "Tile updated.")
            return redirect("projects:pdb_detail", pk=widget.dashboard_id)
    else:
        form = DashboardWidgetForm(instance=obj, tenant=request.tenant)
    return render(request, TEMPLATE_FORM,
                  _widget_context(obj.dashboard, form=form, is_edit=True, obj=obj))


# ---------------------------------------------------------------------------------
# verbs (POST only)
# ---------------------------------------------------------------------------------
@login_required
@require_POST
def wdg_delete(request, pk):
    """Remove the tile. Its board's other tiles keep their positions (no renumber on a delete).

    Hand-written rather than ``crud_delete`` for the fetch reason (``apps/core/crud.py:241`` is
    tenant-only) — and the audit row is written BEFORE ``obj.delete()`` so it outlives the object and
    still names the tile (``run_delete``'s ordering, and ``write_audit_log`` reads ``obj.pk``/``str()``
    at call time, verified ``apps/core/utils.py:17-21``).

    A gap is left on purpose: deleting the middle of ``1..n`` leaves ``1,3,4``, and nothing here
    renumbers. ``Meta.ordering`` hides it from the reader, the next ``wdg_move`` swap still walks the
    nearest positional neighbour, and ``wdg_create`` appends past the top — so the only cost is a
    non-contiguous tail, which the tie branch repairs if it ever bites. Re-counting on every delete
    would also move ``updated_at`` on rows nobody touched, which is the lie B2.3's split exists to stop.
    """
    obj = get_object_or_404(_visible_tile(request).select_related("dashboard"), pk=pk)
    board_pk = obj.dashboard_id
    title = obj.title
    write_audit_log(request.user, obj, "delete", changes={"dashboard": str(board_pk)})
    obj.delete()
    messages.success(request, f"Tile {title} removed.")
    # R10 lists this route among the ``redirect_back_or`` users: the arrow/delete forms are posted from
    # the board page, so the user lands back exactly where they were, and the fallback is that same
    # page when no (or a hostile) ``next`` came with the POST.
    return redirect_back_or(request, "projects:pdb_detail", pk=board_pk)


@login_required
@require_POST
def wdg_move(request, pk):
    """Swap this tile with its neighbour in one slot. Position is the ONLY column this route writes.

    Three branches, and the one thing they all share is that a refused move writes nothing (L11): a
    junk direction must not read as success, and no branch may empty the board.

    1. **junk direction** — ``direction`` arrives from a form the client controls, so it is matched
       against :data:`MOVE_DIRECTIONS` and anything else (including the absent key, ``"  "`` and
       ``"UP"``) is an error message plus the redirect back, with no row touched.
    2. **no neighbour at all** — the first tile asked to go up, or the last asked to go down. Nothing
       is written and nothing is audited; the message says why (``info``, not ``error``: the user did
       nothing wrong, and the alternative readings — wrap to the other end, or 400 — would either move
       a tile further than one slot or invent a verb 7.16 has no shape for). This is the branch that
       must not 500, and the probe asserts it returns 302 with the order unmoved.
    3. **the tie** — B2.5 pins ``analytics.renumber_tiles(dashboard)`` "when the neighbour's position
       equals the moved tile's". With the pinned strict ``<``/``>`` lookup that equality is
       unreachable, so the tie is looked for where it can actually exist: when no strictly lower/higher
       row is found, the board may still have a row at the SAME position, ordered either side of this
       one by ``id`` — which is exactly the row the grid shows above/below it, because
       ``Meta.ordering`` is ``["position", "id"]``. That partner's position equals this tile's, so
       swapping would write the value it already has: a no-op that reports success. Instead the board
       is repaired (``renumber_tiles`` is the documented single position-repair path, verified
       ``apps/projects/analytics.py:2136-2150``) and the message tells the user to move again now that
       every slot is distinct. Repairing rather than refusing is the safer write: the corrupt board is
       left contiguous ``1..n``, and no row gets a position nobody asked for.
    4. **the swap** — two ``.update()`` calls inside ONE ``transaction.atomic()`` (B2.5). Both are
       narrowed by ``pk__in=[this, neighbour]`` plus the tile's own tenant and board, so the write can
       only ever touch the two rows in hand even if a later edit widens the fetch; and one transaction
       is what stops a half-swap leaving two tiles on the same slot when the second statement fails.
       ``.update()`` is the pinned exception to this module's save-only rule, for the reason stated in
       the docstring: an arrow click is not a change to what a tile says.

    Audit is ``action="toggle"`` — 6 characters, because ``AuditLog.action`` is ``varchar(10)`` (R8) and
    "move" is not an allowed action string; the verb rides in ``changes`` with the direction, and only a
    branch that wrote something is audited.
    """
    obj = get_object_or_404(_visible_tile(request).select_related("dashboard"), pk=pk)
    direction = request.POST.get("direction", "").strip()
    if direction not in MOVE_DIRECTIONS:
        messages.error(request, "Unknown direction — the tile was not moved.")
        return redirect_back_or(request, "projects:pdb_detail", pk=obj.dashboard_id)
    comparator, order, tie_comparator, tie_order = MOVE_DIRECTIONS[direction]

    # B2.5's sibling read verbatim: the board's own tiles, tenant-narrowed, minus this one. No
    # ``dashboard__in`` subquery here — the parent is already resolved and ACL-checked by the fetch
    # above, so re-running it per arrow click would be a second subquery proving nothing new.
    siblings = DashboardWidget.objects.filter(
        tenant=request.tenant, dashboard=obj.dashboard).exclude(pk=obj.pk)
    neighbour = siblings.filter(**{comparator: obj.position}).order_by(*order).first()
    if neighbour is None:
        # The tie hunt of branch 3, and only ever reachable when the positional lookup came back empty.
        neighbour = siblings.filter(
            position=obj.position, **{tie_comparator: obj.id}).order_by(*tie_order).first()

    if neighbour is None:
        messages.info(request, f"This tile is already the {'first' if direction == 'up' else 'last'} one on the board.")
        return redirect_back_or(request, "projects:pdb_detail", pk=obj.dashboard_id)

    board_pk = obj.dashboard_id
    if neighbour.position == obj.position:
        analytics.renumber_tiles(obj.dashboard)
        messages.success(request, "Two tiles shared a slot, so the board was renumbered — move the tile again.")
        write_audit_log(request.user, obj, "toggle",
                        changes={"verb": "move", "direction": direction})
        return redirect_back_or(request, "projects:pdb_detail", pk=board_pk)

    pair = DashboardWidget.objects.filter(
        pk__in=[obj.pk, neighbour.pk], tenant=request.tenant, dashboard=obj.dashboard)
    with transaction.atomic():
        pair.filter(pk=neighbour.pk).update(position=obj.position)
        pair.filter(pk=obj.pk).update(position=neighbour.position)
    write_audit_log(request.user, obj, "toggle",
                    changes={"verb": "move", "direction": direction})
    messages.success(request, f"Tile moved {direction}.")
    return redirect_back_or(request, "projects:pdb_detail", pk=board_pk)
