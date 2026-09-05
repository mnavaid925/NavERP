"""Procurement 6.17 Risk & Compliance Management — SupplierRiskSignal views.

Seven routes: the register, one detail page, capture/amend/delete, the review verb, and the
standalone **refresh due** board.

Discipline a reviewer will otherwise go looking for:

* **Every queryset is ``filter(tenant=request.tenant)``** — never ``.all()``. This model has its
  own tenant column, so every object is fetched ``get_object_or_404(..., tenant=request.tenant)``.
* **Ordinary CRUD and the review verb are ``@login_required``; only DELETE adds
  ``@tenant_admin_required``** (with ``@require_POST``, in that order, L27). Reviewing an
  observation is the daily work of a procurement analyst and is deliberately not admin-gated;
  destroying the evidence that a supplier's health was ever watched is.
* **The review verb runs the row under ``select_for_update()`` inside ``transaction.atomic()``**,
  so two analysts clicking on the same signal cannot both audit a state change.
* **Nothing here writes to the spine or to ``apps.accounting``** (L29). A deteriorating supplier
  raises a 6.1 inbox item and colours a badge; it holds no PO, blocks no payment and refuses no
  award. The only place a vendor is actually blocked is the 6.4 suspension register.
* **No second composite score.** The detail page CITES the party's latest
  ``scm.SupplierRiskAssessment`` (SCM 4.2 owns the internal four-factor composite) and links to
  the 4.2 register. 6.17 never computes a rival headline (L29/L36/L37).
* **Query shape.** The register select_relateds ``party`` — a row's own ``__str__`` walks it, so
  without it a page of 15 rows is 16 queries — and ``reviewed_by``, which the list template names
  on every reviewed row, for the same reason. The detail page takes the ``SERIES_LIMIT`` window
  and the latest assessment in one query each.
"""
from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Q

from apps.core.crud import _changed
from apps.core.models import Party
from apps.procurement.forms.RiskComplianceManagement.RiskSignals import SupplierRiskSignalForm
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.RiskComplianceManagement.RiskSignals import (
    BAND_CHOICES, METRIC_CHOICES, PROVIDER_CHOICES, REVIEW_STATUS_CHOICES, TREND_CHOICES,
    SupplierRiskSignal)
from apps.procurement.views._common import *  # noqa: F401,F403

TEMPLATE_LIST = "procurement/riskcompliance/risksignal/list.html"
TEMPLATE_DETAIL = "procurement/riskcompliance/risksignal/detail.html"
TEMPLATE_FORM = "procurement/riskcompliance/risksignal/form.html"
TEMPLATE_REFRESH = "procurement/riskcompliance/risk_refresh_due.html"

#: How far ahead the refresh board's "due soon" card looks.
REFRESH_DUE_SOON_DAYS = 30

#: What the review POST's ``action`` may say, mapped to the model verb it calls. Anything else is
#: reported and ignored rather than raised (L11 — this value arrives from a POST body).
_REVIEW_ACTIONS = {
    "reviewed": ("mark_reviewed", False),
    "actioned": ("mark_actioned", True),
    "dismissed": ("dismiss", True),
}

#: Every hop a register row (or its own ``__str__``) walks. ``reviewed_by`` is here and not only
#: on the detail set because ``risksignal/list.html`` names the reviewer on every reviewed row —
#: without the join that is one extra query per such row, so a mature page costs ~7 queries when
#: nothing has been reviewed and ~22 once everything has.
_ROW_RELATIONS = ("party", "reviewed_by")

#: Every hop the detail page walks, on top of the row set.
_DETAIL_RELATIONS = _ROW_RELATIONS + ("evidence", "captured_by", "alert")


# -- shared helpers ------------------------------------------------------------------------------

def _is_admin(request):
    """Mirrors ``@tenant_admin_required`` exactly, so a hidden button and a refused POST agree."""
    return bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False))


def _need_tenant(request, what):
    """The superuser has no workspace by design; say so instead of rendering an empty page."""
    if request.tenant is None:
        messages.error(request, f"Select a tenant workspace to {what}.")
        return redirect("dashboard:home")
    return None


def _refuse_terminal(obj, verb):
    return (f"{obj.number} has already been {obj.get_review_status_display().lower()} and cannot "
            f"be {verb}. A closed-out signal is the record a decision rests on — capture a NEW "
            f"observation instead.")


def _signal_qs(request):
    return (SupplierRiskSignal.objects.filter(tenant=request.tenant)
            .select_related(*_ROW_RELATIONS))


def _monitorable_parties(tenant):
    """The parties whose financial health is monitored: this workspace's suppliers and vendors."""
    if tenant is None:
        return Party.objects.none()
    return (Party.objects.filter(tenant=tenant, roles__role__in=("supplier", "vendor"))
            .distinct().order_by("name"))


def _stats(tenant, today):
    """The four register stat cards.

    Counted over the WHOLE workspace, not the filtered page: a stat card answers "how much risk
    work is outstanding?", which must not change because somebody typed a search.
    """
    return SupplierRiskSignal.objects.filter(tenant=tenant).aggregate(
        critical=Count("id", filter=Q(band="critical")),
        deteriorating=Count("id", filter=Q(trend="deteriorated")),
        unreviewed=Count("id", filter=Q(review_status="new")),
        refresh_due=Count("id", filter=Q(next_refresh_on__lte=today)),
    )


def _scale_context(obj):
    """How this row's metric is scaled, as the detail page needs to SAY it.

    Read off the model's :attr:`SupplierRiskSignal.scale` property (which reads ``METRIC_SCALES``)
    so the page and the derivation can never disagree about which way is up. ``registered`` is
    False for ``metric="other"``, which has no scale at all — the page states that rather than
    rendering a bar with no meaning behind it.
    """
    scale_min, scale_max, higher_is_better = obj.scale
    return {
        "registered": scale_min is not None and scale_max is not None,
        "min": scale_min,
        "max": scale_max,
        "higher_is_better": higher_is_better,
        "direction": ("higher is healthier" if higher_is_better else "higher is riskier"),
        "safest": (scale_max if higher_is_better else scale_min),
        "riskiest": (scale_min if higher_is_better else scale_max),
    }


def _latest_assessment(obj):
    """The party's most recent ``scm.SupplierRiskAssessment``, or ``None``.

    CITED, never duplicated. SCM 4.2 owns the internal four-factor composite; this page shows it
    beside the bureau observation so the two views of the same supplier sit together, and links
    out to the 4.2 register. 6.17 ships no second composite score (research 2.10).
    """
    if not (obj.tenant_id and obj.party_id):
        return None
    from apps.scm.models import SupplierRiskAssessment

    return (SupplierRiskAssessment.objects
            .filter(tenant_id=obj.tenant_id, party_id=obj.party_id)
            .select_related("party")
            .order_by("-assessment_date", "-id")
            .first())


# -- the register --------------------------------------------------------------------------------

@login_required
def risksignal_list(request):
    """The monitoring register — every observation in the workspace, newest first."""
    guard = _need_tenant(request, "review supplier risk signals")
    if guard is not None:
        return guard
    return crud_list(
        request,
        _signal_qs(request),
        TEMPLATE_LIST,
        search_fields=["number", "party__name", "source_ref", "notes"],
        # (get_param, orm_lookup, is_int). The int one goes through crud_list's as_db_int guard,
        # so ?party=abc / ?party=999999999999999999999 skip the filter instead of 500ing; the
        # five enum ones are validated against the model's own CHOICES before they narrow, so a
        # stale bookmark cannot silently empty the register (L11).
        filters=[("party", "party_id", True),
                 ("provider", "provider", False),
                 ("metric", "metric", False),
                 ("band", "band", False),
                 ("trend", "trend", False),
                 ("review_status", "review_status", False)],
        extra_context={
            "provider_choices": PROVIDER_CHOICES,
            "metric_choices": METRIC_CHOICES,
            "band_choices": BAND_CHOICES,
            "trend_choices": TREND_CHOICES,
            "review_status_choices": REVIEW_STATUS_CHOICES,
            "parties": _monitorable_parties(request.tenant),
            "stats": _stats(request.tenant, timezone.localdate()),
            "is_admin": _is_admin(request),
        },
    )


@login_required
def risksignal_detail(request, pk):
    """One observation: the number, what it means on its own scale, and how it has moved."""
    obj = get_object_or_404(SupplierRiskSignal.objects.select_related(*_DETAIL_RELATIONS),
                            pk=pk, tenant=request.tenant)

    # The series this observation belongs to: same party + provider + metric, newest first,
    # capped at SERIES_LIMIT. ONE query, backed by prc_srs_series_idx. This row is included —
    # the page shows where the current reading sits in its own history, not next to it.
    series = list(SupplierRiskSignal.objects
                  .filter(tenant=request.tenant, party_id=obj.party_id, provider=obj.provider,
                          metric=obj.metric)
                  .select_related("captured_by")
                  .order_by("-observed_on", "-id")[:SupplierRiskSignal.SERIES_LIMIT])

    return render(request, TEMPLATE_DETAIL, {
        "obj": obj,
        "series": series,
        "scale": _scale_context(obj),
        # Both are model properties; passed explicitly because the context contract pins them,
        # and because the page's whole argument depends on them being present by name.
        "breaches_minimum": obj.breaches_minimum,
        "minimum_acceptable": obj.minimum_acceptable,
        "assessment": _latest_assessment(obj),
        "alert": obj.alert,
        "is_admin": _is_admin(request),
    })


# -- capture / amend -------------------------------------------------------------------------------

def _signal_form(request, instance=None):
    """Capture or amend one observation.

    Hand-rolled rather than ``crud_create`` / ``crud_edit`` because it does two things those
    helpers cannot: it stamps ``captured_by`` from the session (a form field for "who captured
    this" is an attribution anybody could forge, and amending must not silently transfer it),
    and it calls :meth:`SupplierRiskSignal.raise_deterioration_alert` AFTER the save — the model
    deliberately does not raise from ``save()``, because a table write hidden there fires in
    every seeder run and every test fixture.

    The context is exactly the ``crud_*`` contract — ``form`` + ``is_edit``, plus ``obj`` on the
    edit path only — so the one template behaves identically on both routes (L7).
    """
    is_edit = instance is not None

    if request.method == "POST":
        form = SupplierRiskSignalForm(request.POST, request.FILES, instance=instance,
                                      tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            if not is_edit:
                obj.captured_by = request.user if request.user.is_authenticated else None
            # save() runs derive(): the scale, the risk position, the band and the trend are all
            # stamped here, from METRIC_SCALES and from this row's own predecessor.
            obj.save()
            write_audit_log(request.user, obj, "update" if is_edit else "create", _changed(form))

            alert = obj.raise_deterioration_alert(request.user)
            messages.success(request, f"Risk signal {obj.number} saved.")
            if alert is not None:
                messages.warning(
                    request,
                    f"{obj.party} has deteriorated to {obj.get_band_display().lower()} on "
                    f"{obj.get_metric_display()}. Alert raised in the Task & Alert Center.")
            return redirect("procurement:risksignal_detail", pk=obj.pk)
    else:
        form = SupplierRiskSignalForm(instance=instance, tenant=request.tenant)

    ctx = {"form": form, "is_edit": is_edit}
    if is_edit:
        ctx["obj"] = instance
    return render(request, TEMPLATE_FORM, ctx)


@login_required
def risksignal_create(request):
    """Capture an observation of a supplier's financial health."""
    guard = _need_tenant(request, "capture supplier risk signals")
    if guard is not None:
        return guard
    return _signal_form(request)


@login_required
def risksignal_edit(request, pk):
    """Amend an observation — refused once it has been actioned or dismissed.

    Amending the number behind a recorded decision would rewrite the basis that decision rests
    on. Note that a correction restamps THIS row's own trend against its own predecessor; rows
    captured after it keep the ``previous_value`` they were stamped with at the time. That is
    deliberate — a series is a record of what was known when, and the honest way to correct a
    reading is to capture the corrected one as a NEW observation.
    """
    obj = get_object_or_404(SupplierRiskSignal, pk=pk, tenant=request.tenant)
    if obj.is_terminal:
        messages.error(request, _refuse_terminal(obj, "edited"))
        return redirect("procurement:risksignal_detail", pk=pk)
    return _signal_form(request, instance=obj)


@login_required
@tenant_admin_required
@require_POST
def risksignal_delete(request, pk):
    """Admin-gated: deleting an observation erases part of a supplier's monitoring history."""
    obj = get_object_or_404(SupplierRiskSignal, pk=pk, tenant=request.tenant)
    if obj.is_terminal:
        messages.error(request, _refuse_terminal(obj, "deleted"))
        return redirect("procurement:risksignal_detail", pk=pk)
    return crud_delete(request, model=SupplierRiskSignal, pk=pk,
                       success_url="procurement:risksignal_list")


# -- the review verb -----------------------------------------------------------------------------

@login_required
@require_POST
def risksignal_review(request, pk):
    """Review one signal: acknowledge it, action it, or dismiss it.

    Deliberately NOT admin-gated — reviewing observations is the daily work of a procurement
    analyst, and a queue only an admin can clear is a queue nobody clears. The row is locked for
    the call so two analysts cannot both stamp a decision on it, and each model verb re-checks
    its own guard, which is what makes a direct POST exactly as safe as a click.
    """
    guard = _need_tenant(request, "review supplier risk signals")
    if guard is not None:
        return guard

    action = (request.POST.get("action") or "").strip()
    note = (request.POST.get("review_note") or "").strip()

    # L11: the action arrives from a POST body. An unrecognised one is reported and ignored,
    # never raised — and it must be checked BEFORE the note, so a junk action with no note gets
    # the accurate message rather than a misleading one about the note.
    if action not in _REVIEW_ACTIONS:
        messages.error(request, "Choose whether to mark this signal reviewed, actioned or "
                                "dismissed.")
        return redirect("procurement:risksignal_detail", pk=pk)

    verb_name, note_required = _REVIEW_ACTIONS[action]
    if note_required and not note:
        messages.error(
            request,
            "Record what was done about this signal. A closure with no stated reasoning is "
            "indistinguishable from a signal nobody looked at.")
        return redirect("procurement:risksignal_detail", pk=pk)

    with transaction.atomic():
        obj = get_object_or_404(SupplierRiskSignal.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if not getattr(obj, verb_name)(request.user, note):
            messages.error(
                request,
                f"{obj.number} cannot be marked {action} from "
                f"{obj.get_review_status_display().lower()}.")
            return redirect("procurement:risksignal_detail", pk=pk)

    write_audit_log(request.user, obj, "update", {"action": action, "review_note": note[:200]})
    messages.success(request, f"{obj.number} marked {obj.get_review_status_display().lower()}.")
    return redirect("procurement:risksignal_detail", pk=pk)


# -- the refresh board ---------------------------------------------------------------------------

@login_required
def risksignal_refresh_board(request):
    """Which supplier metrics are due — or overdue — a fresh observation, and which have none.

    Two queries and no stored "due" flag: the supplier list, then every signal belonging to one of
    those suppliers, ordered so the first row of each ``(party, provider, metric)`` series is its
    latest — narrowed to 8 columns and streamed, because that second read follows the append-only
    ledger and not the vendor master, and ~88% of its rows lose to ``setdefault``. Rows are
    built only for series that need attention, so the page's length tracks the size of the
    PROBLEM rather than the size of the vendor master — which is also why it needs no pagination.

    A party with no observation at all counts as **stale** rather than overdue: nobody promised a
    refresh date for it, so it cannot be late for one. What is true is that there is no data, and
    that is staleness taken to its limit. It sorts to the top of the board regardless.
    """
    guard = _need_tenant(request, "review the risk refresh board")
    if guard is not None:
        return guard

    today = timezone.localdate()
    soon = today + timedelta(days=REFRESH_DUE_SOON_DAYS)
    stale_before = today - timedelta(days=SupplierRiskSignal.STALE_AFTER_DAYS)
    parties = list(_monitorable_parties(request.tenant))
    parties_by_id = {party.pk: party for party in parties}

    # The latest signal per (party, provider, metric). Ordered so the first row setdefault() sees
    # within each series is the one that counts.
    #
    # Three deliberate narrowings, because this is the one read here whose size follows the
    # append-only LEDGER rather than the vendor master:
    #  * ``party_id__in`` pushes the "has it still got a supplier role?" test into SQL instead of
    #    fetching every signal and dropping it in Python one line later;
    #  * ``.only(...)`` fetches the 8 columns the board and its template actually read - not the
    #    22-column row with two TextFields (``notes``/``review_note``) that neither touches;
    #  * ``.iterator()`` keeps the discarded rows out of ``_result_cache``. With ~200 suppliers x
    #    ~3 metrics, the vast majority of rows lose to ``setdefault()`` immediately, and holding
    #    all of them resident for the length of the request is the actual cost here.
    # ``select_related("party")`` is deliberately dropped: the row-dict takes its Party from
    # ``parties_by_id``, which is already in memory, so the join was fetching each supplier again
    # once per signal.
    latest, monitored_parties = {}, set()
    for signal in (SupplierRiskSignal.objects
                   .filter(tenant=request.tenant, party_id__in=parties_by_id)
                   .only("party_id", "provider", "metric", "observed_on", "next_refresh_on",
                         "band", "number", "tenant_id")
                   .order_by("party_id", "provider", "metric", "-observed_on", "-id")
                   .iterator(chunk_size=2000)):
        latest.setdefault((signal.party_id, signal.provider, signal.metric), signal)
        monitored_parties.add(signal.party_id)

    rows, overdue, due_soon, stale = [], 0, 0, 0

    # A series against a party that has since lost its supplier role is not this board's business
    # — the register still shows it, but nobody is being asked to refresh it. That test is now the
    # ``party_id__in`` above, so every signal reaching this loop has a Party in ``parties_by_id``.
    for signal in latest.values():
        due = signal.next_refresh_on

        if due is not None and due <= today:
            state, label, css = "overdue", "Refresh overdue", "badge-red"
            overdue += 1
        elif signal.observed_on and signal.observed_on < stale_before:
            state, label, css = "stale", "Observation stale", "badge-amber"
            stale += 1
        elif due is not None and due <= soon:
            state, label, css = "due_soon", "Due soon", "badge-amber"
            due_soon += 1
        else:
            continue  # comfortably fresh — not this board's business

        rows.append({
            # From the in-memory supplier list, never signal.party — reading the FK off a
            # .only()-narrowed instance would fire one lazy query per row.
            "party": parties_by_id[signal.party_id],
            "signal": signal,
            "provider_label": signal.get_provider_display(),
            "metric_label": signal.get_metric_display(),
            "observed_on": signal.observed_on,
            "due_on": due,
            "days": (today - due).days if due is not None else None,
            "age_days": (today - signal.observed_on).days if signal.observed_on else None,
            "state": state,
            "state_label": label,
            "state_css": css,
            # Never-monitored parties sort first (see below), then the longest-neglected series.
            "sort_on": (1, -(((today - signal.observed_on).days) if signal.observed_on else 0)),
        })

    for party in parties:
        if party.pk in monitored_parties:
            continue
        stale += 1
        rows.append({
            "party": party,
            "signal": None,
            "provider_label": None,
            "metric_label": None,
            "observed_on": None,
            "due_on": None,
            "days": None,
            "age_days": None,
            "state": "never",
            "state_label": "Never monitored",
            "state_css": "badge-red",
            "sort_on": (0, 0),
        })

    # Worst first: never monitored, then the longest-neglected observation.
    rows.sort(key=lambda row: row["sort_on"])

    return render(request, TEMPLATE_REFRESH, {
        "rows": rows,
        "stats": {"overdue": overdue, "due_soon": due_soon, "stale": stale},
        "today": today,
        "is_admin": _is_admin(request),
    })
