"""SCM 4.18 Finance & Accounting Integration — ``DutyTariff``: the customs duty master's CRUD.

Five function-based views — list / create / detail / edit / delete — over the tenant-scoped
HS-code × country-of-origin × effective-date duty schedule. **Nothing here computes a landed cost.**
This module maintains the master that ``LandedCostCharge`` reads ONCE, through
``DutyTariff.rate_for()``, to DEFAULT a duty line's ``duty_rate_pct``; the charge then SNAPSHOTS the
number, so nothing on these pages can restate what a receipt was already costed at.

FOLDER-NAME NOTE (do not "fix" it): the backend package is ``FinanceIntegration/`` while the
templates live under ``templates/scm/finance/``. That asymmetry is the house rule — every shipped
scm template folder uses a short slug while the Python package uses the NavERP.md sub-module
title in PascalCase. ``ThirdPartyLogistics/ClientSlas.py`` carries the same note.

--------------------------------------------------------------------------------------------------
THE ONE THING THIS MODULE DOES THAT ``crud_list`` CANNOT DO FOR IT
--------------------------------------------------------------------------------------------------
``crud_list``'s ``(param, lookup, is_int)`` filter spec applies a GET value **directly** as an ORM
lookup value. ``?status=active`` is not a value ``is_active`` can take — the mapping
``active → True`` / ``inactive → False`` is a translation, not a lookup — so it is applied to the
queryset in :func:`dutytariff_list` **before** ``crud_list`` is called (and therefore, like every
other filter, before pagination). Anything that is neither string is IGNORED: a hand-edited
``?status=banana`` must narrow nothing and return 200, never 500 (L11).

``?country`` needs no such translation and goes through ``crud_list``'s own spec. It is a
**CharField**, so the template compares it as a plain string — ``{% if request.GET.country == c %}``
— and **never** with ``|stringformat:"d"`` (which is for pk params) or ``|slugify``.

--------------------------------------------------------------------------------------------------
WHY DELETE HAS NO STATUS GATE
--------------------------------------------------------------------------------------------------
A tariff is a MASTER row, not a document with a lifecycle, and — deliberately — nothing FKs it:
``LandedCostCharge`` snapshots the rate rather than pointing at the tariff, so there is no
``PROTECT`` to trip and no ``ProtectedError`` to catch. Deleting one therefore removes a future
DEFAULT and touches no history. ``is_active`` is the softer alternative and the delete message says
so.
"""
from django.urls import reverse

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _need_tenant

from apps.scm.forms import DutyTariffForm
from apps.scm.models import DutyTariff


#: The ``?status=`` vocabulary for this page. A LITERAL, not a model constant, because ``DutyTariff``
#: has no ``status`` column at all — it has ``is_active``, and these two strings are the URL spelling
#: of that boolean. Passed to the template as ``status_choices`` so the widget and the view read the
#: same two values.
STATUS_CHOICES = [("active", "Active"), ("inactive", "Inactive")]

#: How ``?status`` maps onto the column. Anything not in here is ignored — see the module docstring.
_STATUS_TO_ACTIVE = {"active": True, "inactive": False}


def _current_window_q(today):
    """``Q`` matching the rows that are IN FORCE on ``today``.

    Both halves, exactly as :attr:`DutyTariff.is_current` reads them — ``is_active`` AND the window —
    so the list's ``current`` statistic and the per-row badge can never disagree about what "current"
    means. ``effective_to IS NULL`` is +infinity and carries its own ``isnull`` leg, because a
    comparison against NULL in SQL is neither true nor false and would silently drop every open-ended
    row out of the count.
    """
    return (Q(is_active=True, effective_from__lte=today)
            & (Q(effective_to__isnull=True) | Q(effective_to__gte=today)))


def _countries(tenant):
    """The distinct, non-blank origins in this workspace — a LIST OF STRINGS for the ``?country=``
    dropdown.

    Strings, not objects and not pks: ``country_of_origin`` is free text on the tariff itself, so the
    filter compares string to string. A blank origin is the "applies to any origin" catch-all and is
    excluded — offering it as a dropdown entry would read as a country called "".

    ``.order_by("country_of_origin")`` is REQUIRED, not cosmetic. ``Meta.ordering`` is
    ``["hs_code", "-effective_from"]``, and Django adds every ordering column to the SELECT — which
    would make ``.distinct()`` operate on ``(country, hs_code, effective_from)`` triples and return
    the same country many times over. The explicit single-column ordering replaces it.

    ``.none()``-equivalent for a tenant-less caller falls out of the ``tenant=None`` filter on a
    non-nullable FK (no row can match), so the superuser gets an empty dropdown rather than every
    workspace's origins.
    """
    return list(DutyTariff.objects
                .filter(tenant=tenant)
                .exclude(country_of_origin="")
                .order_by("country_of_origin")
                .values_list("country_of_origin", flat=True)
                .distinct())


# =================================================================================================
# The register
# =================================================================================================
@login_required
def dutytariff_list(request):
    """Every duty rate in the workspace, with what is actually in force today.

    **Filter GET params** (every one applied BEFORE pagination):

    * ``q`` — free text over ``hs_code`` / ``description`` / ``country_of_origin`` / ``number``.
    * ``status`` — ``active`` | ``inactive``, translated onto ``is_active`` HERE (``crud_list``
      cannot express a mapping). Any other value narrows nothing and returns 200 (L11).
    * ``country`` — an exact ``country_of_origin``, through ``crud_list``'s own spec. A **string**
      compare in the template; ``|stringformat:"d"`` would be wrong on a CharField.

    **Context**, exhaustively — these names are the published interface the template is written
    against:

    * ``object_list`` / ``page_obj`` / ``q`` — from ``crud_list``. Guard prev/next with
      ``has_previous`` / ``has_next`` (L9).
    * ``status_choices`` — :data:`STATUS_CHOICES`, the literal active/inactive pair.
    * ``countries`` — a list of STRINGS behind the ``?country=`` dropdown.
    * ``stats`` — a dict with EXACTLY ``total`` / ``active`` / ``inactive`` / ``current`` (ints).
      Computed over the WHOLE workspace, never the filtered page: "9 rates in force" is a fact
      somebody acts on, and a figure that moved as you browsed would be useless.
    * ``today`` (date) — so a row outside its window can be labelled *Not in effect* rather than
      looking identical to a live one.

    **Per row**, safe to read without a query: ``obj.number``, ``obj.hs_code``,
    ``obj.country_of_origin`` (blank means **Any**, and must render as such — never as an empty
    cell), ``obj.description``, ``obj.duty_rate_pct``, ``obj.effective_from``, ``obj.effective_to``
    (``None`` = open-ended), ``obj.is_active``, ``obj.is_current`` and ``obj.tax_code``.

    ``select_related("tax_code")`` because ``TaxCode.__str__`` is ``"{name} ({rate_pct}%)"`` and any
    row printing it would otherwise cost one query each.

    Badges are COLOUR-NAMED theme.css classes only — ``badge-green`` (Active), ``badge-slate``
    (Inactive), ``badge-muted`` (in date terms, not in effect). A semantic ``badge-success`` /
    ``badge-danger`` does not exist in theme.css and renders UNSTYLED (L33).
    """
    tenant = request.tenant
    qs = DutyTariff.objects.filter(tenant=tenant).select_related("tax_code")

    # The translation `crud_list` cannot do. Applied to the queryset, so it is honoured before
    # pagination exactly like every declared filter; an unrecognised value falls through untouched.
    wanted = _STATUS_TO_ACTIVE.get(request.GET.get("status", "").strip())
    if wanted is not None:
        qs = qs.filter(is_active=wanted)

    today = timezone.localdate()
    # Workspace-wide, and computed from the UNFILTERED manager on purpose (see the context note).
    # No alias here collides with a model field name, so all four counts share one aggregate() call
    # safely — the FieldError trap only bites when an alias shadows a column named in the same call.
    stats = DutyTariff.objects.filter(tenant=tenant).aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        inactive=Count("id", filter=Q(is_active=False)),
        current=Count("id", filter=_current_window_q(today)))

    return crud_list(
        request, qs, "scm/finance/dutytariff/list.html",
        search_fields=("hs_code", "description", "country_of_origin", "number"),
        filters=(
            ("country", "country_of_origin", False),
        ),
        extra_context={
            "status_choices": STATUS_CHOICES,
            "countries": _countries(tenant),
            "stats": {key: value or 0 for key, value in stats.items()},
            "today": today,
        })


# =================================================================================================
# CRUD
# =================================================================================================
@login_required
def dutytariff_create(request):
    """Add a duty rate. ``crud_create`` stamps the tenant, audits and refuses a tenant-less user.

    ``_need_tenant`` refuses FIRST so the message steers back to this list rather than to the
    dashboard — the superuser has ``tenant=None`` BY DESIGN and every scm view filters by tenant, so
    creating here would otherwise mint an orphan row.

    ``DutyTariffForm`` ALSO stamps the tenant (through ``TenantUniqueMixin``) and that is not
    redundancy: ``crud_create`` assigns ``obj.tenant`` only AFTER ``is_valid()``, so without the
    form-side stamp both the ``unique_together`` check and the cross-tenant leg of
    ``DutyTariff.clean()`` would validate an instance whose ``tenant_id`` is ``None`` — which is the
    exact case each of them skips. They would be dead code on the create path, and the create path is
    the one a crafted POST takes.

    Context: ``form``, ``is_edit`` (``False``). **``obj`` does not exist on this path** — every
    ``{{ obj.* }}`` in the shared form template must sit inside ``{% if is_edit %}``.
    """
    if _need_tenant(request):
        return redirect("scm:dutytariff_list")
    return crud_create(request, form_class=DutyTariffForm,
                       template="scm/finance/dutytariff/form.html",
                       success_url="scm:dutytariff_list")


@login_required
def dutytariff_detail(request, pk):
    """One duty rate: what it covers, what it charges, and whether it is in force today.

    Context keys, exhaustively (the template is written by a separate agent):

    * ``obj`` — the :class:`~apps.scm.models.DutyTariff`, with ``tax_code`` joined. **The page asks
      it for ``obj.is_current`` directly** — ``is_current`` is a pure property over three columns
      the row already carries, so it queries nothing.
    * ``today`` (date) — print it beside the window so "not in effect" is checkable rather than
      asserted.

    A blank ``country_of_origin`` means **applies to any origin** and must render as *Any*, never as
    an empty field; ``effective_to = None`` means **open-ended**, never "expired".

    ONE query. There was a second one — a ``.only()`` pre-read of the same row, purely so the view
    could hand the template an ``is_current`` flag before ``crud_detail`` fetched the object — and it
    bought nothing: ``extra_context`` is evaluated by the caller, but the OBJECT is in the template's
    hand by then and answers the same question for free.
    """
    return crud_detail(request, model=DutyTariff, pk=pk,
                       template="scm/finance/dutytariff/detail.html",
                       select_related=("tax_code",),
                       extra_context={"today": timezone.localdate()})


@login_required
def dutytariff_edit(request, pk):
    """Correct a duty rate. **This never restates a costed receipt.**

    Editable at any time and with no status ladder, deliberately: a schedule genuinely gets corrected,
    a description gets clarified and a window gets closed, and none of those is a derived figure.
    ``LandedCostCharge`` SNAPSHOTS ``duty_rate_pct`` when the charge is entered, so an edit here
    changes what the next ``rate_for()`` lookup DEFAULTS to and nothing that has already been costed.

    ``success_url`` is a REVERSED URL, not a route name: ``redirect()`` would resolve a bare
    ``"scm:dutytariff_detail"`` without the ``pk`` this route requires and raise ``NoReverseMatch`` on
    save — the failure would land on the success path, after the row was already written.

    Context: ``form``, ``obj``, ``is_edit`` (``True``).
    """
    return crud_edit(request, model=DutyTariff, pk=pk, form_class=DutyTariffForm,
                     template="scm/finance/dutytariff/form.html",
                     success_url=reverse("scm:dutytariff_detail", args=[pk]))


@login_required
@require_POST
def dutytariff_delete(request, pk):
    """Delete a duty rate. POST-only — a GET is a 405, never a silent state change.

    No status gate, and no ``ProtectedError`` to catch: nothing in the application FKs a tariff
    (``LandedCostCharge`` snapshots the rate instead of pointing at it), so this removes a future
    lookup default and touches no costed history.

    What it DOES remove is the schedule itself. The follow-up message steers to ``is_active`` —
    clearing that box retires a rate from ``rate_for()`` while keeping the row readable, which is
    what somebody almost always meant.

    ``crud_delete`` writes the audit row BEFORE deleting; wrapping it in ``transaction.atomic()``
    rolls that row back with a delete that then fails, so the trail cannot record something that
    did not happen.
    """
    with transaction.atomic():
        response = crud_delete(request, model=DutyTariff, pk=pk,
                               success_url="scm:dutytariff_list")
    messages.info(request, "To retire a rate without losing it, clear its Active box instead — an "
                           "inactive tariff is skipped by the duty lookup and stays readable beside "
                           "everything it costed.")
    return response
