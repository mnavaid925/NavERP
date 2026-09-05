"""Procurement 6.16 Supplier Performance & Evaluation — SupplierKpi views.

The KPI *catalogue*: register, create, detail, edit, delete. A row here is a definition, not a
measurement — which is why this file is plain ``crud_*`` all the way through and stamps nothing.
Every measured figure lives on ``SupplierKpiScore`` and is written by
``supplierevaluation_generate``, never here.

Discipline a reviewer will otherwise go looking for:

* **Every queryset is ``filter(tenant=request.tenant)``** — never ``.all()``. ``crud_detail`` /
  ``crud_edit`` / ``crud_delete`` scope by tenant themselves, so a cross-tenant pk is a 404, not
  a leak.
* **The ``owners`` filter dropdown lists only users who actually own a KPI** (the
  ``_dispute_owners`` precedent, ``views/InvoiceVoucherManagement/InvoiceDisputes.py``). A
  dropdown of the whole directory is a page that never finishes loading on a big tenant, and an
  empty option list is more honest than one full of people who own nothing.
* **``stats`` is ONE conditional ``aggregate()``**, not five COUNTs — and it is counted over the
  WHOLE workspace, not the filtered page: a stat card answers "what is the catalogue?", which
  must not change because somebody typed a search.
* **Retire, never delete.** The delete route exists (a mis-typed definition that has never been
  measured should go), but ``SupplierKpiScore.kpi`` is ``PROTECT``, so a KPI with history
  refuses to delete at the database. The list and detail pages both say so, and
  ``is_active=False`` is the retirement mechanism the templates point at instead.

**Import discipline.** Two kinds of not-yet-wired import live here, both deliberate:

1. ``SupplierKpi`` / ``SupplierKpiForm`` come from their ENTITY modules at module top, never
   from ``apps.procurement.models`` / ``.forms`` — this sub-package is not added to the package
   ``__init__`` re-export blocks until the Integrate phase, and a package-level import would be
   a star-import cycle at URLconf import time (the ``CostForecasts.py`` precedent).
2. The three sibling models the detail page lists, and the two shared constants from
   ``apps.procurement.performance``, are imported INSIDE ``supplierkpi_detail``. They belong to
   the same 6.16 pass and land beside this file; keeping the import local means this module
   imports cleanly on its own and cannot start a cycle.
"""
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, ProtectedError, Q

# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULES directly — see the
# module docstring.
from apps.procurement.forms.SupplierPerformanceEvaluation.SupplierKpis import SupplierKpiForm
from apps.procurement.models.SupplierPerformanceEvaluation.SupplierKpis import (
    APPLIES_CHOICES, CATEGORY_CHOICES, DIRECTION_CHOICES, SOURCE_CHOICES, SupplierKpi)
from apps.procurement.views._common import *  # noqa: F401,F403

TEMPLATE_LIST = "procurement/performance/kpi/list.html"
TEMPLATE_DETAIL = "procurement/performance/kpi/detail.html"
TEMPLATE_FORM = "procurement/performance/kpi/form.html"

#: The register's active/inactive filter. ``is_active`` is a BooleanField, so ``crud_list``'s
#: non-int path maps the strings "True"/"False" onto real booleans before it filters.
ACTIVE_CHOICES = (("True", "Active"), ("False", "Inactive"))

#: Per-list cap on the two SECONDARY lists of the detail page (plans, feedback). The primary
#: measured-history list uses ``performance.DETAIL_ROW_CAP``. The template prints them under
#: SEPARATE keys — ``row_cap`` and ``related_cap`` — because one key for two different numbers
#: is how the page came to describe a 20-row list as "the most recent 50".
_RELATED_CAP = 20

_ROW_RELATIONS = ("owner",)


def _kpi_qs(request):
    """The register's base queryset — tenant-scoped, with the one FK the rows render."""
    return SupplierKpi.objects.filter(tenant=request.tenant).select_related(*_ROW_RELATIONS)


def _kpi_owners(request):
    """Whoever actually owns a KPI in this workspace — not every user in it.

    ``.none()`` for a tenant-less user (the superuser has ``tenant=None``), so the filter bar
    renders empty rather than offering the whole directory.
    """
    users = get_user_model().objects
    if request.tenant is None:
        return users.none()
    return (users.filter(tenant=request.tenant, procurement_supplier_kpis__isnull=False)
            .distinct().order_by("email"))


def _kpi_stats(tenant):
    """``{total, active, derived, survey, manual}`` in ONE query.

    Counted over the whole workspace on purpose — see the module docstring.
    """
    return SupplierKpi.objects.filter(tenant=tenant).aggregate(
        total=Count("pk"),
        active=Count("pk", filter=Q(is_active=True)),
        derived=Count("pk", filter=Q(source="derived")),
        survey=Count("pk", filter=Q(source="survey")),
        manual=Count("pk", filter=Q(source="manual")),
    )


@login_required
def supplierkpi_list(request):
    """The KPI catalogue, in ``display_order, code`` (model ordering).

    Six filters, each one a column a buyer actually sorts the catalogue by. ``owner`` is an FK
    and rides the ``is_int=True`` path so a hand-edited query string cannot 500 the page (L11);
    the other five are plain CHOICES/boolean strings, which ``crud_list`` validates against the
    field's own choices and skips when they do not match.
    """
    return crud_list(
        request, _kpi_qs(request), TEMPLATE_LIST,
        search_fields=("code", "name", "description", "notes"),
        filters=(("category", "category", False),
                 ("source", "source", False),
                 ("direction", "direction", False),
                 ("applies_to", "applies_to", False),
                 ("owner", "owner_id", True),
                 ("is_active", "is_active", False)),
        extra_context={
            "category_choices": CATEGORY_CHOICES,
            "source_choices": SOURCE_CHOICES,
            "direction_choices": DIRECTION_CHOICES,
            "applies_choices": APPLIES_CHOICES,
            "active_choices": ACTIVE_CHOICES,
            "owners": _kpi_owners(request),
            "stats": _kpi_stats(request.tenant),
        },
    )


@login_required
def supplierkpi_detail(request, pk):
    """The definition, plus everything measured or opened under it.

    Three bounded, tenant-scoped lists hang off the definition — the measured history, the
    improvement plans that cite it and the 360 responses against it. Each is capped and each
    reports its own truncation, so a KPI with ten years of history is still one page.

    The sibling models and the two shared constants are imported HERE rather than at module top:
    they are the same 6.16 pass's other entities and its compute module, and a module-level
    import of them would tie this file's importability to their build order (the
    ``CostForecasts.py`` precedent).
    """
    from apps.procurement.models.SupplierPerformanceEvaluation.ScorecardKpiScores import (
        SupplierKpiScore)
    from apps.procurement.models.SupplierPerformanceEvaluation.SupplierFeedback import (
        SupplierFeedback)
    from apps.procurement.models.SupplierPerformanceEvaluation.SupplierImprovementPlans import (
        SupplierImprovementPlan)
    from apps.procurement.performance import BENCHMARK_NOTE, DETAIL_ROW_CAP

    # Fetch cap + 1 so "was it cut?" is answered by the same query, not by a second COUNT.
    score_rows = list(
        SupplierKpiScore.objects.filter(tenant=request.tenant, kpi_id=pk)
        .select_related("scorecard", "scorecard__party")
        .order_by("-scorecard__period_end", "-id")[:DETAIL_ROW_CAP + 1])
    plans = list(
        SupplierImprovementPlan.objects.filter(tenant=request.tenant, kpi_id=pk)
        .select_related("supplier")
        .order_by("-start_date", "-id")[:_RELATED_CAP + 1])
    feedback_rows = list(
        SupplierFeedback.objects.filter(tenant=request.tenant, kpi_id=pk)
        .select_related("supplier", "respondent")
        .order_by("-period_end", "-id")[:_RELATED_CAP + 1])

    # TWO flags and TWO caps, because there are two caps in play. One ``truncated`` next to one
    # ``row_cap`` of 50 described three lists, two of which are actually cut at ``_RELATED_CAP``
    # (20) — so the page could tell the reader "the most recent 50 are shown" about a list that
    # stopped at 20. Same shape as ``supplierevaluation_detail``.
    truncated = len(score_rows) > DETAIL_ROW_CAP
    related_truncated = (len(plans) > _RELATED_CAP or len(feedback_rows) > _RELATED_CAP)

    return crud_detail(
        request, model=SupplierKpi, pk=pk, template=TEMPLATE_DETAIL,
        select_related=_ROW_RELATIONS,
        extra_context={
            "score_rows": score_rows[:DETAIL_ROW_CAP],
            "plans": plans[:_RELATED_CAP],
            "feedback_rows": feedback_rows[:_RELATED_CAP],
            "row_cap": DETAIL_ROW_CAP,
            "truncated": truncated,
            "related_cap": _RELATED_CAP,
            "related_truncated": related_truncated,
            "benchmark_note": BENCHMARK_NOTE,
        },
    )


@login_required
def supplierkpi_create(request):
    """Add a KPI definition. ``crud_create`` stamps the tenant and refuses a tenant-less user."""
    return crud_create(request, form_class=SupplierKpiForm, template=TEMPLATE_FORM,
                       success_url="procurement:supplierkpi_list")


@login_required
def supplierkpi_edit(request, pk):
    """Re-tune a definition.

    Editing a KPI does NOT rewrite history: ``SupplierKpiScore`` freezes the weight, target,
    direction, source and unit that were in force when the line was generated, so a retune
    changes the next period and leaves closed ones alone.
    """
    return crud_edit(request, model=SupplierKpi, pk=pk, form_class=SupplierKpiForm,
                     template=TEMPLATE_FORM, success_url="procurement:supplierkpi_list")


@login_required
@require_POST
def supplierkpi_delete(request, pk):
    """Delete a definition that has never been measured.

    ``SupplierKpiScore.kpi`` is ``PROTECT``, so a KPI that any scorecard line references refuses
    to delete at the database — deliberately. The way to take a measured KPI out of service is
    ``is_active=False``, which stops generate picking it up and keeps every figure ever taken
    under it readable.

    That refusal has to arrive as a MESSAGE, not a 500, which is what the ``ProtectedError``
    guard is for — the same generic guard ``party_delete`` / ``item_delete`` /
    ``currency_delete`` already carry. Deliberately generic rather than an ``.exists()``
    enumeration: later passes add references (the 6.16 improvement plans and feedback rows are
    ``SET_NULL`` today, but nothing promises the next one will be), and an enumeration goes
    stale the moment one does. ``atomic()`` so the audit row ``crud_delete`` writes before
    deleting rolls back with the failed delete.
    """
    get_object_or_404(SupplierKpi.objects.only("pk"), pk=pk, tenant=request.tenant)
    try:
        with transaction.atomic():
            return crud_delete(request, model=SupplierKpi, pk=pk,
                               success_url="procurement:supplierkpi_list")
    except ProtectedError as exc:
        blockers = sorted({protected._meta.verbose_name for protected in exc.protected_objects})
        messages.error(
            request,
            f"This KPI is still referenced by {', '.join(blockers)} and cannot be deleted — "
            "the measured history under it would lose its definition. Deactivate it instead.")
        return redirect("procurement:supplierkpi_detail", pk=pk)
