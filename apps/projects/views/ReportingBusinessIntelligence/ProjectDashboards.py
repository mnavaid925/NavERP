"""Projects 7.16 Reporting & Business Intelligence — ProjectDashboard [PDB-] views.

Six routes over the dashboard pair: the personalized home, the register, the live tile grid, the
definition form for create and edit, and the delete. **Nothing here computes a figure** — every
number on a tile arrives from :func:`apps.projects.analytics.compute_widget` while the page renders,
so a board can never drift from the ledger it reports on (L29), and the only writes this module
makes are the definition rows the two ``crud_*`` form helpers save.

Three rules every shape below exists to keep:

* **visibility** (R7) — every fetch starts from ``analytics.visible_dashboards(request)``, the two
  delegations to ``crud_edit`` / ``crud_delete`` included. Those helpers scope on ``tenant`` only
  (verified ``apps/core/crud.py:213`` and ``:241``), so without the guard line a hand-typed pk would
  open a colleague's **private** board. It is a **404, never a 403** — the row does not exist for
  that caller. A tenant-less superuser gets an empty register and a 404 on every pk route.
* **one grid, one code path** — :func:`_widget_grid` is the only place a tile is computed, a span is
  chosen or a canvas entry is built, and ``pdb_home`` and ``pdb_detail`` both go through it. B2.4
  pins ``projects/reporting/_widget_grid.html`` as the single markup source for those two pages; a
  second copy of the span map or its clamp is how "large" comes to mean two different widths.
* **the window is a request, never a column** — only ``pdb_detail`` accepts ``?range=``, and it
  reaches the tiles through ``compute_widget``'s keyword-only ``date_range=`` argument, which
  overrides without touching the row (B3.4). ``pdb_home`` always shows the board's authored
  ``default_range``, and no route in this module mutates a dashboard to get there.
"""
from functools import partial

from django.db.models import Count
from django.urls import reverse

from apps.core.crud import crud_create, crud_delete, crud_edit, crud_list
from apps.projects import analytics
from apps.projects.forms.ReportingBusinessIntelligence.ProjectDashboards import ProjectDashboardForm
from apps.projects.models import ProjectDashboard
from apps.projects.views._common import get_object_or_404, login_required, render, require_POST
from apps.projects.views._helpers import DASHBOARD_ORDER, chart_config
from apps.projects.views._helpers import owners as owner_choices
from apps.projects.views._helpers import projects as project_choices

#: The home grid's template. D21 overrides B2.4's heading literal
#: (``projects/reporting/dashboard_home.html``): CLAUDE.md's template-location rule 5
#: (``.claude/CLAUDE.md:372-375``, "secondary entity-action pages go inside the entity folder",
#: longest-entity-stem match) folds a ``dashboard_*`` page into the ``dashboard/`` folder that already
#: owns the CRUD triple — and the root ``home.html`` of this sub-module already belongs to
#: ``rbi_home``, so two ``*home*`` pages one folder apart is exactly what that rule exists to prevent.
#: B4.1's own table (contract line 1875) already pins the folded path.
TEMPLATE_HOME = "projects/reporting/dashboard/home.html"
TEMPLATE_LIST = "projects/reporting/dashboard/list.html"
TEMPLATE_DETAIL = "projects/reporting/dashboard/detail.html"
TEMPLATE_FORM = "projects/reporting/dashboard/form.html"

#: ``layout`` → grid column count, i.e. what ``repeat(n, 1fr)`` in the template's style takes.
#: Deliberately **not** ``obj.column_span``: A1.5 pins that property as the 12-column *CSS* span a
#: tile multiplies, and the two numbers look similar enough to be mistaken for each other — one is
#: 1/2/3, the other 4/6/12. The ``.get`` fallback is the model's own (``column_span`` defaults a
#: layout it does not recognise to two columns), so a row minted outside the form agrees with the
#: tile widths the model would claim for it.
LAYOUT_COLS = {"one": 1, "two": 2, "three": 3}

#: tile size → columns it occupies *in this board's grid* (B2.4's map, taken from the verified crm
#: twin ``apps/crm/views/AnalyticsReporting/Dashboards.py:55``). ``full`` is absent because its
#: width is the row itself, i.e. ``cols``; an unrecognised size gets the narrowest column, which is
#: what the clamp would leave it with anyway.
SIZE_SPANS = {"small": 1, "medium": 2, "large": 3}

#: The windows a ``?range=`` may carry. ``custom`` is missing because
#: ``analytics.PRESET_RANGES`` is built without it (verified ``apps/projects/analytics.py:87``) —
#: a tile has no date pair to resolve, so A1.2 rule 4 / A1.3 rule 4 refuse the key at the model.
#: Membership here is therefore both the junk guard (L11) and the ``custom`` guard (A1.2) in one
#: test, which is why no separate ``!= "custom"`` clause follows it.
RANGE_KEYS = frozenset(key for key, _label in analytics.PRESET_RANGES)

#: key → the label the header badge shows. ``.get(key, key)`` is the house fallback
#: (``analytics.resolve_window`` labels an unknown window the same way,
#: verified ``apps/projects/analytics.py:175``): a row minted outside the form gets its raw key on
#: the badge instead of a 500 on a page whose whole job is reading other people's data.
RANGE_LABELS = dict(ProjectDashboard.RANGE_CHOICES)

#: ``crud_list``'s ``(get_param, orm_lookup, is_int)`` triples — B2.4's five register filters.
#: No lookup crosses a relation: ``_enum_values`` bails on a ``__`` (verified
#: ``apps/core/crud.py:100``), so a junk value on a hopped lookup would silently empty the register
#: instead of being ignored (L11). ``is_int`` is True for the two pk selects.
DASHBOARD_FILTERS = (
    ("audience", "audience", False),
    ("layout", "layout", False),
    ("owner", "owner_id", True),
    ("project", "project_id", True),
    ("shared", "is_shared", False),
)

#: ``(get_param, echo_key)`` for the same five filters (R2). All five echo under their own name
#: here — the list exists so the echo set and the filter set cannot drift apart, not to rename.
DASHBOARD_ECHOES = (
    ("audience", "audience_filter"),
    ("layout", "layout_filter"),
    ("owner", "owner_filter"),
    ("project", "project_filter"),
    ("shared", "shared_filter"),
)

#: Free text the register searches. All three are columns on this row, so the search drags in no
#: JOIN — ``rep_list``'s rule for the same reason.
DASHBOARD_SEARCH_FIELDS = ["number", "name", "description"]

# Both annotated reads below pass ``DASHBOARD_ORDER`` explicitly: a GROUP BY drops ``Meta.ordering``,
# and that constant lives in ``_helpers`` because ``rbi_home``'s board strip carries the same
# annotation and must order identically.


# ---------------------------------------------------------------------------------
# shared builders
# ---------------------------------------------------------------------------------
def _echoes(request):
    """The register's five filter echoes, as the stripped strings they arrived as (R2).

    Never the parsed int: ``?project=abc`` comes back as ``abc``, matches no option, and the
    dropdown renders unselected instead of claiming to have narrowed the table.
    """
    return {key: request.GET.get(param, "").strip() for param, key in DASHBOARD_ECHOES}


def _form_context():
    """The keys the definition form needs beside ``form`` / ``is_edit`` / ``obj``.

    One builder for both routes on purpose: create and edit share ``dashboard/form.html``, and two
    copies of this dict are how an edit page stops offering a window the create page still lists.
    ``range_choices`` is the preset six, not the model's seven — the form narrows its own
    ``default_range`` dropdown to the same list (verified
    ``apps/projects/forms/ReportingBusinessIntelligence/ProjectDashboards.py:27``), and this key is
    what any hand-rolled option row on the template reads. ``audience_choices`` /
    ``layout_choices`` are page furniture (the form fields already carry their options from A1.4),
    and ``is_default`` / ``owner`` appear nowhere because A2.3 keeps both off the form.
    """
    return {
        "audience_choices": ProjectDashboard.AUDIENCE_CHOICES,
        "layout_choices": ProjectDashboard.LAYOUT_CHOICES,
        "range_choices": analytics.PRESET_RANGES,
    }


def _is_tenant_admin(user):
    """Tenant administrator or superuser — the role allowed to change a shared board's audience.

    crm's ``_can_share_dashboards`` predicate (verified
    ``apps/crm/views/AnalyticsReporting/Dashboards.py:24–27``), which is the same test
    ``@tenant_admin_required`` applies (verified ``apps/core/decorators.py:18``). Read-only here, so
    the decorator is not the right tool: ``pdb_detail`` must still answer 200 for a member and simply
    hide the affordances.
    """
    return bool(user.is_superuser or getattr(user, "is_tenant_admin", False))


def _widget_grid(dashboard, tenant, *, date_range=None):
    """The ONE tile path behind ``pdb_home`` and ``pdb_detail`` (B2.4).

    Returns the six keys both pages publish — ``rendered_widgets``, ``chart_configs``, ``cols``,
    ``active_range``, ``active_range_label``, ``empty`` — so the two pages cannot disagree about
    what a tile means. ``dashboard`` may be ``None`` (home's empty state): that is the one case this
    builder handles by answering with no tiles, two columns and no window, which is what lets
    ``dashboard/home.html`` render its CTA from the same contract as the grid.

    ``date_range`` is the request's override; without one the board's authored ``default_range``
    wins, and the value is threaded into ``compute_widget`` rather than written anywhere. The tile
    rows are filtered on ``tenant`` a second time because their own FK is denormalised from the
    parent on purpose (A1.3) and this is the one read where a disagreement would be visible.

    ``empty`` is ``not rendered_widgets`` for both pages, which is also B2.4's home formula
    (``dashboard is None or not rendered_widgets``): a ``None`` board renders no tiles, so the two
    spellings cannot come apart.
    """
    cols = LAYOUT_COLS.get(dashboard.layout if dashboard else "", 2)
    active_range = (date_range or (dashboard.default_range if dashboard else "")) or ""

    rendered_widgets = []
    chart_configs = []
    if dashboard is not None:
        # Meta.ordering is ["position", "id"] (A1.3), so the register order is the authored order.
        # The slice is B2.4's stated bound on the grid ("bounded by MAX_TILES_PER_DASHBOARD"): every
        # tile below is a live compute, so an over-populated board must cost 24 of them, not one per
        # row somebody managed to insert.
        for widget in dashboard.widgets.filter(tenant=tenant)[:analytics.MAX_TILES_PER_DASHBOARD]:
            result = analytics.compute_widget(widget, date_range=active_range or None)
            raw_span = cols if widget.size == "full" else SIZE_SPANS.get(widget.size, 1)
            rendered_widgets.append({
                "widget": widget,
                "result": result,
                # Clamped, per B2.4: a "large" tile on a single-column board is that board's width,
                # and an unclamped 3 would overflow ``repeat(1, 1fr)`` into a broken grid.
                "span": min(raw_span, cols),
            })
            # R6's two conditions, with the chart kind read off the PAYLOAD: ``compute_widget``
            # rewrites ``chart_type`` when the stored kind cannot show the metric it got (a
            # non-RAG series asked to be heat bands becomes a bar chart, verified
            # ``apps/projects/analytics.py:1797–1813``). The canvas the grid draws follows that
            # decision, so an entry keyed to the stale stored kind would either draw a chart the
            # page has no element for or leave a real canvas with no config — the blank-canvas-
            # at-200 outcome R6 exists to prevent. ``chart_config`` is the single builder that
            # turns a series into an entry and it owns the CANVAS_CHARTS half of the rule (D52),
            # answering ``[]`` for an HTML kind and for a series with nothing to plot.
            if result.get("kind") == "series":
                chart_type = result.get("chart_type") or widget.chart_type
                chart_configs.extend(chart_config(
                    chart_type,
                    result.get("labels") or [],
                    result.get("data") or [],
                    # R6: the entry is keyed to the widget pk, and the grid's canvas element is
                    # ``{{ w.canvas_id }}`` = ``wchart<pk>`` (A1.5) — one id, two readers.
                    chart_id=widget.pk,
                ))

    return {
        "rendered_widgets": rendered_widgets,
        "chart_configs": chart_configs,
        "cols": cols,
        "active_range": active_range,
        "active_range_label": RANGE_LABELS.get(active_range, active_range),
        "empty": not rendered_widgets,
    }


# ---------------------------------------------------------------------------------
# home, register, grid
# ---------------------------------------------------------------------------------
@login_required
def pdb_home(request):
    """The board the caller lands on, or the CTA that asks them to make one.

    Hand-written because it computes (R9). No ``?range=`` is read here, and no ``range_choices`` is
    passed (B2.4): "my home" shows the window its author saved, and the switcher belongs to the page
    that can go back from it. ``analytics.home_dashboard`` is the whole resolution — the caller's
    ``is_default``, else a shared tenant template, else the newest visible board, else ``None`` — and
    it writes nothing on the user's behalf (B3.4).
    """
    dashboard = analytics.home_dashboard(request)
    ctx = _widget_grid(dashboard, request.tenant)
    ctx["dashboard"] = dashboard

    others = analytics.visible_dashboards(request)
    if dashboard is not None:
        # Guarded rather than written as ``exclude(pk=dashboard.pk)`` with a possibly-``None`` pk:
        # the answer ``exclude`` gives for a NULL comparison is database-flavoured, and the strip is
        # supposed to be "the other boards", which is exactly what the branch says.
        others = others.exclude(pk=dashboard.pk)
    ctx.update({
        # Annotated under the pinned name so the strip reads ``d.annotation_count`` and never the
        # ``widget_count`` property — the property is one COUNT per row of a page that is already a
        # per-row compute (A1.5 pins both names for this reason). Same explicit order as the
        # register, because the annotation's GROUP BY drops the model's: a slice of an unordered
        # query is not "the first four", it is four the database felt like (L9).
        "other_dashboards": others.annotate(annotation_count=Count("widgets")).order_by(
            *DASHBOARD_ORDER)[:4],
        "create_url": reverse("projects:pdb_create"),
        "detail_url": reverse("projects:pdb_detail", args=[dashboard.pk]) if dashboard else "",
    })
    return render(request, TEMPLATE_HOME, ctx)


@login_required
def pdb_list(request):
    """Every board this caller may see, narrowed by search and the five register filters.

    The one non-obvious line is the ``order_by``: B2.4 pins a ``Count("widgets")`` annotation here,
    and a grouped SELECT loses the model's default ordering (see ``DASHBOARD_ORDER``).
    """
    qs = analytics.visible_dashboards(request).select_related("owner").annotate(
        annotation_count=Count("widgets")).order_by(*DASHBOARD_ORDER)
    return crud_list(
        request, qs, TEMPLATE_LIST,
        search_fields=DASHBOARD_SEARCH_FIELDS,
        filters=DASHBOARD_FILTERS,
        extra_context={
            "audience_choices": ProjectDashboard.AUDIENCE_CHOICES,
            "layout_choices": ProjectDashboard.LAYOUT_CHOICES,
            # The two dropdowns that are not model choice lists, from the same shared builders every
            # register in the app uses — and both ``.none()`` for a tenant-less user, so the filter
            # card cannot offer a person or a project whose rows this caller cannot open anyway (R7).
            "owners": owner_choices(request.tenant),
            "projects": project_choices(request.tenant),
            **_echoes(request),
        },
    )


@login_required
def pdb_detail(request, pk):
    """The board and its LIVE tiles, with the window switcher that home deliberately lacks.

    Hand-written because it computes (R9), and it **must not** pass ``page_obj`` (B2.4): the grid is
    bounded by ``MAX_TILES_PER_DASHBOARD``, not by a page size, so ``dashboard/detail.html`` includes
    no pagination partial. The fetch below is the ACL — a private board in the same workspace is a
    404 here, and ``select_related`` is what keeps the header's owner/project/portfolio names off
    three more queries.
    """
    obj = get_object_or_404(
        analytics.visible_dashboards(request).select_related("owner", "project", "portfolio"),
        pk=pk)
    # L11 plus A1.2 rule 4 in one line: a junk ``?range=`` silently falls back to the authored
    # window instead of emptying every tile, and ``custom`` is refused because RANGE_KEYS does not
    # contain it. Nothing is written either way — the override lives in the compute call, and
    # ``active_range`` itself is the grid builder's answer (override, else authored).
    window = request.GET.get("range", "").strip()
    override = window if window in RANGE_KEYS else ""

    ctx = _widget_grid(obj, request.tenant, date_range=override)
    is_owner = obj.owner_id == request.user.id
    ctx.update({
        "obj": obj,
        "range_choices": analytics.PRESET_RANGES,
        # The "Add tile" target. Reversed rather than spelled because the route exists: a renamed
        # tile route is a crash on this page, not a dead button on it.
        "widget_add_url": reverse("projects:wdg_create", args=[obj.pk]),
        "home_url": reverse("projects:pdb_home"),
        "is_owner": is_owner,
        # crm's shape: your own board, or a shared one and the role that may change what everyone
        # else sees. A private board never reaches here — the fetch above 404s it.
        "can_edit": is_owner or (obj.is_shared and _is_tenant_admin(request.user)),
    })
    return render(request, TEMPLATE_DETAIL, ctx)


# ---------------------------------------------------------------------------------
# definition form (GET + POST)
# ---------------------------------------------------------------------------------
@login_required
def pdb_create(request):
    """Author a board. ``owner`` is the creating user and ``is_default`` is not a checkbox (A2.3).

    ``user=`` is what makes the first half of that sentence true: ``crud_create`` builds and saves a
    form class it cannot hand a user to, so without the partial the board saved as ``owner=None`` —
    this table reads a null owner as a tenant template, so creating "my board" would have published
    a template instead. D54's shape, narrowed to create-only because an unset owner means something
    here (see ``ProjectDashboardForm.save``).

    No ``@require_POST`` (B1.7): this is a form view, so the verb is the form's own submit and
    ``crud_create`` branches on it. A tenant-less caller never reaches the form at all — the helper
    sends them back to the dashboard home with a message (verified ``apps/core/crud.py:189–191``),
    which is how the superuser's empty registers stay empty instead of becoming orphan rows.
    """
    return crud_create(
        request,
        form_class=partial(ProjectDashboardForm, user=request.user),
        template=TEMPLATE_FORM,
        success_url="projects:pdb_list",
        extra_context=_form_context(),
    )


@login_required
def pdb_edit(request, pk):
    """Edit the definition. Ownership and the home flag are not reachable here.

    Guard-fetch then delegate, exactly as ``rep_edit`` does (D26): ``crud_edit``'s own fetch is
    ``tenant=`` scoped only, so this line is what 404s a colleague's private board before the helper
    resolves the pk. The helper's second fetch is on the same tenant and is harmless — the check, not
    the object, is what the line is for.

    ``success_url`` is pre-resolved because the route takes a pk and ``crud_edit`` calls bare
    ``redirect(success_url)`` (verified ``apps/core/crud.py:221``): a bare name would raise
    ``NoReverseMatch`` on the one path that has to work, a valid save. B2.4 pins the target
    (``projects:pdb_detail``), and ``tsk_execute`` is the in-app precedent for resolving it here
    (verified ``apps/projects/views/TaskWorkManagement/ProjectTasks.py:80–86``).
    """
    get_object_or_404(analytics.visible_dashboards(request), pk=pk)
    return crud_edit(
        request,
        model=ProjectDashboard,
        pk=pk,
        form_class=ProjectDashboardForm,
        template=TEMPLATE_FORM,
        success_url=reverse("projects:pdb_detail", args=[pk]),
        extra_context=_form_context(),
    )


# ---------------------------------------------------------------------------------
# verb (POST only)
# ---------------------------------------------------------------------------------
@login_required
@require_POST
def pdb_delete(request, pk):
    """Drop the board. Its tiles go with it (CASCADE, A1.6).

    No context: the helper only redirects (R1). The guard-fetch is here for the same reason as
    ``pdb_edit``'s — ``crud_delete``'s fetch is tenant-scoped, not ACL-scoped (D26). ``@require_POST``
    sits below ``@login_required`` and above nothing else (B1.7): an anonymous visitor is redirected
    to login rather than handed a 405, and a member with the wrong verb gets 405, never a 403 that
    leaks which role the route wants. The confirm dialog's "and its N tiles" count is read off the
    row's own data attribute, never a context key (B2.2's rule for the same pattern).
    """
    get_object_or_404(analytics.visible_dashboards(request), pk=pk)
    return crud_delete(request, model=ProjectDashboard, pk=pk, success_url="projects:pdb_list")
