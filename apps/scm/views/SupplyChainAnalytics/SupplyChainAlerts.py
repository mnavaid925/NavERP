"""SCM 4.11 Supply Chain Analytics — SupplyChainAlert views: the exception inbox.

This is the module's daily-driver page. Everything else in 4.11 is a computed report; this is the
one screen somebody works *through*, so it is built as an inbox rather than as a table: the default
view is what still needs attention, ranked by ``impact_value`` — **what acting on it is worth, not
how many there are.** A queue ranked by count is a queue people learn to ignore, which is the
alert-fatigue failure the whole sub-module exists to avoid.

--------------------------------------------------------------------------------------------------
TWO THINGS THIS MODULE DELIBERATELY DOES NOT CONTAIN
--------------------------------------------------------------------------------------------------
**1. The state machine.** ``acknowledge`` / ``assign`` / ``snooze`` / ``resolve`` / ``dismiss`` are
methods on :class:`~apps.scm.models.SupplyChainAlert`. The five action views below lock the row,
call the method, and write the ``{field: [before, after]}`` diff it returns through
``write_audit_log``. They re-implement none of it — a second copy of "may I acknowledge a resolved
alert?" living in a view is exactly how the button and the seeder start disagreeing.

**2. Detection.** :func:`supplychainalert_detect` calls ``analytics.detect_alerts`` and does nothing
else. That function is the ONLY writer of this table, and it is also the only place de-duplication
happens (see the model's module docstring for why a database constraint cannot express "re-fire the
open row rather than raise a second one", and why MariaDB's lack of partial indexes rules out the
conditional-unique shape that looks right). A rule re-implemented here would raise alerts the
detector cannot then match, and the queue would grow a duplicate per press.

**4.11 is read-only over 4.1-4.10.** Nothing in this module writes a ``StockMove`` or a
``JournalEntry``; an alert points at the rows that caused it and records what a person decided.

--------------------------------------------------------------------------------------------------
WHY THE DEFAULT VIEW IS "NEEDS ATTENTION" AND NOT SIMPLY "NOT CLOSED"
--------------------------------------------------------------------------------------------------
``OPEN_STATUSES`` is ``open | acknowledged | snoozed``, but a LIVE snooze is a deliberate
suppression: counting it in the inbox — and in the header chip every analytics page carries — would
make snoozing do nothing at all. So the default is
``open | acknowledged | (snoozed whose window has run out)``, which is exactly the three conditions
``SupplyChainAlert.is_snooze_expired`` tests, so the filtered set and the badged set agree. A snooze
that has expired comes back on its own — otherwise ``snoozed`` is a black hole (L39 §4) — and live
snoozes remain one click away under ``?status=snoozed``, with their own count on the page so the
bucket is never invisible.

:func:`open_alert_count` counts that same set, so the chip and the page it links to cannot disagree.
"""
import json
from decimal import InvalidOperation
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._common import _changed
from apps.scm.views._helpers import _need_tenant
from apps.scm.models._base import q2
from apps.scm import analytics
from apps.scm.models import (ALERT_STATUS_CHOICES, ALERT_TYPE_CHOICES, METRIC_GROUP_PAGES,
                             METRIC_LABELS, METRIC_META, SEVERITY_CHOICES, SupplyChainAlert,
                             format_metric_value)
from apps.scm.forms import (AlertAssignForm, AlertResolveForm, AlertSnoozeForm,
                            SupplyChainAlertForm)

User = get_user_model()

#: Every FK the inbox table renders, joined once. ``purchase_order__vendor`` is two joins deep on
#: purpose: ``PurchaseOrder.__str__`` is ``f"{number} · {vendor}"``, so ``subject_label`` walks a
#: second FK and a bare ``select_related("purchase_order")`` would still fire one query per row.
#: (``Item`` / ``Location`` / ``Carrier`` / ``Shipment`` / ``Party`` all render from their own
#: columns, so they need nothing deeper — checked, not assumed.)
_ALERT_SELECT = ("kpi_target", "item", "party", "carrier", "shipment", "purchase_order__vendor",
                 "location", "assigned_to")

#: The two extra joins only the detail page reads — a list row never renders who acknowledged or
#: closed an alert, so it does not pay for them.
_ALERT_DETAIL_SELECT = _ALERT_SELECT + ("acknowledged_by", "resolved_by")

#: The inbox's filter params. Whitelisted rather than echoed, so the query string a row's triage
#: form carries back can only ever contain these (the 4.7 ``_safety_report_url`` rule).
_LIST_FILTERS = ("q", "status", "severity", "alert_type", "assigned_to", "min_impact", "sort",
                 "page")

#: What the ``sort`` toggle offers. The default IS ``Meta.ordering`` — see the module docstring for
#: why impact and not recency ranks an exception queue.
_SORT_ORDERS = {
    "impact": ("-impact_value", "-raised_at", "-id"),
    "newest": ("-raised_at", "-id"),
    "oldest": ("raised_at", "id"),
}
_SORT_CHOICES = [("impact", "Biggest impact first"), ("newest", "Newest first"),
                 ("oldest", "Oldest first")]
_DEFAULT_SORT = "impact"

#: ``status=`` values that are not a status: the default view (absent), and the escape hatch.
_STATUS_ATTENTION = ""
_STATUS_ALL = "all"

#: The open statuses that are NOT a live suppression. Derived from the model's own OPEN set rather
#: than re-typed, so adding an open status in ``_choices.py`` cannot leave this filter behind.
_UNSUPPRESSED_OPEN = tuple(s for s in SupplyChainAlert.OPEN_STATUSES if s != "snoozed")

#: Cap on the evidence rows rendered out of ``detail``. Tested BEFORE each row is built, so the
#: guard is O(1) in the thing it guards instead of being the payload it is protecting against
#: (L40 §1 — ``len(build_the_whole_thing())`` is not a bound).
_MAX_EVIDENCE_ROWS = 60

#: Which of the model's six subject FKs links where. Keyed by the field name so
#: :func:`_subject_links` can walk ``SupplyChainAlert.SUBJECT_FIELDS`` — the model's own tuple — and
#: a seventh subject added there shows up immediately (unlinked) rather than silently vanishing.
_SUBJECT_META = {
    "item": ("Item", "scm:item_detail"),
    "party": ("Counterparty", "core:party_detail"),
    "carrier": ("Carrier", "scm:carrier_detail"),
    "shipment": ("Shipment", "scm:shipment_detail"),
    "purchase_order": ("Purchase order", "scm:purchaseorder_detail"),
    "location": ("Location", "scm:location_detail"),
}


# =================================================================================================
# Shared helpers
# =================================================================================================
def _needs_attention_q(today=None):
    """Q for "still demanding attention": open, acknowledged, or a snooze that has run out.

    Exactly the conditions ``SupplyChainAlert.is_snooze_expired`` tests — including its refusal to
    treat a snooze with no date as expired — so the rows this filter returns and the rows the model
    badges as needing attention are the same rows. The 4.10 overdue-filter rule: whenever a property
    and a queryset describe the same thing, they must be written from the same three conditions.
    """
    return (Q(status__in=_UNSUPPRESSED_OPEN)
            | Q(status="snoozed", snoozed_until__lt=today or timezone.localdate()))


def open_alert_count(tenant):
    """How many exceptions still need somebody — the header chip on all five analytics pages.

    **ONE ``.count()``, deliberately.** This runs on every report page load, so it must never grow
    into a per-row walk or a second query. It counts precisely what :func:`supplychainalert_list`
    shows by default, so the chip and the page it links to can never disagree — a count that
    disagrees with its own destination is worse than no count.

    Returns 0 for a tenant-less user (the superuser) rather than filtering on NULL.
    """
    if tenant is None:
        return 0
    return SupplyChainAlert.objects.filter(tenant=tenant).filter(_needs_attention_q()).count()


def _assignee_qs(tenant):
    """The tenant's logins, for the assignee FILTER — ``.none()`` when there is no tenant.

    Same posture as ``_item_qs``: an empty queryset for a tenant-less user, never the unscoped
    default manager, which would offer every workspace's users in a dropdown.

    Deliberately WIDER than ``forms._assignable_users``, which drops deactivated logins: you cannot
    hand new work to somebody who has left, but "what was still assigned to them when they left" is
    exactly the question their alerts need to answer. Ordered by ``email`` to match that helper, so
    the filter here and the assign select on the detail page list people in the same order.
    """
    if tenant is None:
        return User.objects.none()
    return User.objects.filter(tenant=tenant).order_by("email")


def _apply_status(queryset, raw):
    """Apply the one filter that is not plain equality. Returns ``(queryset, value for the select)``.

    ``crud_list``'s filter spec only does equality and this param has three non-status meanings
    (absent = the default view, ``all`` = no filter, junk = fall back), so it is applied here,
    before pagination, and the resolved value is handed to the template so the select shows what
    actually happened rather than what was typed.
    """
    value = (raw or "").strip()
    if value == _STATUS_ALL:
        return queryset, _STATUS_ALL
    if value in dict(ALERT_STATUS_CHOICES):
        return queryset.filter(status=value), value
    # Absent, or hand-edited junk: fall back to the default view rather than to an empty page. The
    # crud_list posture on a bad filter — skip it, never 500, and never silently show nothing.
    return queryset.filter(_needs_attention_q()), _STATUS_ATTENTION


def _min_impact(raw):
    """Parse ``?min_impact=`` into a Decimal the ``impact_value`` column can actually be compared to.

    Three separate hazards, and "is it a Decimal" answers none of them:

    * junk (``?min_impact=abc``) is SKIPPED rather than 500'd — the ``_date_window`` / int-FK-guard
      posture (L11): a hand-edited filter narrows nothing, it does not raise out of ``.filter()``;
    * ``NaN`` and infinity parse happily out of ``Decimal()`` and then poison the comparison, so
      they are rejected explicitly;
    * an in-range-looking but OVERSIZED figure (``?min_impact=1e400``) is clamped through ``q2()``
      to what a ``DecimalField(14, 2)`` holds. Django 5.1 does not adapt a lookup value, so this
      backend tolerates it today — but ``format_number`` raises ``InvalidOperation`` on anything
      past ``max_digits`` the moment the same number reaches a save/aggregate path, and the tests
      run on a different backend from production. Clamping is also the truthful answer: "at least
      10^400" matches nothing, which is what the ceiling gives, whereas dropping the filter would
      silently show everything.
    """
    value = (raw or "").strip()
    if not value:
        return None
    try:
        amount = Decimal(value)
    except (InvalidOperation, ValueError, TypeError):
        return None
    return q2(amount) if amount.is_finite() else None


def _return_query(data):
    """The whitelisted filter state, pre-encoded, for the ``action=`` of a row's triage form.

    One attribute per form rather than one hidden input per filter — and the string is built HERE
    from ``_LIST_FILTERS`` rather than echoed back out of the request, so a post-action redirect can
    never carry the CSRF token (or anything else a caller invented) into a URL. :func:`_return_url`
    re-whitelists what it reads, so both ends of the round trip are closed independently.
    """
    params = {key: (data.get(key) or "").strip() for key in _LIST_FILTERS}
    params = {key: value for key, value in params.items() if value}
    params["origin"] = "list"
    return urlencode(params)


def _return_url(pk, data):
    """Where a POST action lands: back to the inbox it was fired from, else the alert's own page.

    Built by REVERSING our own url names and re-reading only ``_LIST_FILTERS``; no caller-supplied
    URL is ever followed, so there is no open-redirect surface. A detail-page form carries no query
    string at all, so ``origin`` is simply absent there and the user stays on the alert.
    """
    if (data.get("origin") or "").strip() != "list" and pk is not None:
        return reverse("scm:supplychainalert_detail", args=[pk])
    params = {key: (data.get(key) or "").strip() for key in _LIST_FILTERS}
    query = urlencode({key: value for key, value in params.items() if value})
    url = reverse("scm:supplychainalert_list")
    return f"{url}?{query}" if query else url


def _evidence_rows(detail):
    """``(label, text)`` pairs for the evidence panel, out of the alert's ``detail`` JSON.

    Every score 4.11 raises renders its own arithmetic rather than asking the reader to trust it
    (the ``SupplierScorecard.signal_summary`` precedent), and this is where that arithmetic is
    shown. Nested structures are compacted to JSON rather than dropped — an unreadable value is
    still evidence; a missing one is a number nobody can check.

    Bounded at ``_MAX_EVIDENCE_ROWS`` with the test BEFORE the row is built, so the cap costs
    nothing on an oversized payload instead of materialising it first (L40 §1).
    """
    if not isinstance(detail, dict):
        return [] if detail in (None, "", [], {}) else [("detail", str(detail)[:500])]
    rows = []
    for key, value in detail.items():
        if len(rows) >= _MAX_EVIDENCE_ROWS:
            break
        if isinstance(value, (dict, list, tuple)):
            text = json.dumps(value, default=str)[:500]
        elif value is None:
            text = "—"
        else:
            text = str(value)[:500]
        rows.append((str(key).replace("_", " "), text))
    return rows


def _subject_links(alert):
    """``{label, text, url}`` for every subject FK this alert actually names — the drill-down rows.

    Driven by the model's own ``SUBJECT_FIELDS`` tuple, and reversed here rather than in the
    template so the six-branch ``{% if %}`` chain a template would otherwise need does not exist.
    An unmapped field renders unlinked instead of raising — a detail page must not 500 because a
    seventh subject FK was added to the model.
    """
    rows = []
    for name in alert.SUBJECT_FIELDS:
        subject = getattr(alert, name, None)
        if subject is None:
            continue
        label, url_name = _SUBJECT_META.get(name, (name.replace("_", " ").capitalize(), ""))
        rows.append({
            "label": label,
            "text": str(subject),
            "url": reverse(url_name, args=[subject.pk]) if url_name else "",
        })
    return rows


# =================================================================================================
# CRUD
# =================================================================================================
@login_required
def supplychainalert_list(request):
    """The exception inbox — what still needs attention, ranked by what acting on it is worth."""
    queryset = SupplyChainAlert.objects.filter(tenant=request.tenant).select_related(*_ALERT_SELECT)
    queryset, status_value = _apply_status(queryset, request.GET.get("status"))

    # "Unassigned" is a real triage question and cannot be expressed as an equality filter. A
    # NUMERIC assigned_to falls through to crud_list's int-FK filter below, which carries the
    # .isdigit() guard (L11) — so this branch and that one cannot both fire on the same value.
    if (request.GET.get("assigned_to") or "").strip() == "unassigned":
        queryset = queryset.filter(assigned_to__isnull=True)

    floor = _min_impact(request.GET.get("min_impact"))
    if floor is not None:
        queryset = queryset.filter(impact_value__gte=floor)

    sort = (request.GET.get("sort") or "").strip()
    if sort not in _SORT_ORDERS:
        sort = _DEFAULT_SORT
    # Every filter above is applied BEFORE the ordering and before crud_list paginates.
    queryset = queryset.order_by(*_SORT_ORDERS[sort])

    today = timezone.localdate()
    attention = _needs_attention_q(today)
    # ONE aggregate for the whole header strip — five conditional counts in a single query rather
    # than five .count() round trips. Deliberately computed over the UNFILTERED tenant set: these
    # tiles say what the workspace looks like, not what the current filter narrowed it to.
    stats = SupplyChainAlert.objects.filter(tenant=request.tenant).aggregate(
        attention=Count("id", filter=attention),
        critical=Count("id", filter=attention & Q(severity="critical")),
        unassigned=Count("id", filter=attention & Q(assigned_to__isnull=True)),
        snoozed=Count("id", filter=Q(status="snoozed", snoozed_until__gte=today)),
        at_risk=Sum("impact_value", filter=attention),
    )

    return crud_list(
        request, queryset, "scm/analytics/supplychainalert/list.html",
        search_fields=["number", "title", "dimension_label"],
        filters=[("severity", "severity", False),
                 ("alert_type", "alert_type", False),
                 ("assigned_to", "assigned_to_id", True)],
        extra_context={
            "status_choices": ALERT_STATUS_CHOICES,
            "severity_choices": SEVERITY_CHOICES,
            "alert_type_choices": ALERT_TYPE_CHOICES,
            "sort_choices": _SORT_CHOICES,
            "assignees": _assignee_qs(request.tenant),
            # The RESOLVED status, not the raw GET value — so a junk ?status= shows the select on
            # the view the page actually rendered rather than on nothing.
            "status_value": status_value,
            "sort": sort,
            "stats": stats,
            "return_query": _return_query(request.GET),
        },
    )


@login_required
def supplychainalert_create(request):
    """Raise an exception by hand. A planner spotting something the detectors cannot is real work."""
    return _alert_form(request, instance=None)


@login_required
def supplychainalert_edit(request, pk):
    """Correct the description of an exception. No triage column is reachable from here (L22)."""
    obj = get_object_or_404(SupplyChainAlert, pk=pk, tenant=request.tenant)
    return _alert_form(request, instance=obj)


def _alert_form(request, instance):
    """Create/edit through one hand-rolled path, so the tenant is stamped BEFORE validation.

    ``crud_create`` assigns the tenant only after ``is_valid()`` (``apps/core/crud.py:82-84``), and
    ``SupplyChainAlert.clean()``'s cross-tenant subject guard is a no-op when ``tenant_id`` is None
    — which is the create path, i.e. the one place a crafted POST would exercise it.
    ``SupplyChainAlertForm`` already stamps it through ``TenantUniqueMixin``, so the line below is
    deliberately redundant: this view is the other half of that contract and should not depend on a
    mixin staying on a form it does not own. It is a no-op when the form has done its job.

    Hand-rolled also means this path owes its own ``write_audit_log`` (``crud_*`` calls it for you),
    and it is what lets a successful save land on the DETAIL page — where all five triage actions
    live — rather than back on the list.
    """
    is_edit = instance is not None
    if not is_edit and _need_tenant(request):
        return redirect("scm:supplychainalert_list")
    if request.method == "POST":
        form = SupplyChainAlertForm(request.POST, instance=instance, tenant=request.tenant)
        if form.instance.tenant_id is None and request.tenant is not None:
            form.instance.tenant = request.tenant
        if form.is_valid():
            alert = form.save()
            write_audit_log(request.user, alert, "update" if is_edit else "create", _changed(form))
            messages.success(request, f"{alert.number} saved.")
            return redirect("scm:supplychainalert_detail", pk=alert.pk)
    else:
        form = SupplyChainAlertForm(instance=instance, tenant=request.tenant)
    return render(request, "scm/analytics/supplychainalert/form.html",
                  {"form": form, "is_edit": is_edit, "obj": instance})


@login_required
def supplychainalert_detail(request, pk):
    """One exception: what fired, what it is about, the evidence, and who has done what about it."""
    obj = get_object_or_404(
        SupplyChainAlert.objects.filter(tenant=request.tenant)
        .select_related(*_ALERT_DETAIL_SELECT), pk=pk)
    meta = METRIC_META.get(obj.metric) or {}
    unit = meta.get("unit", "")
    # The report page that owns this metric, so "where does this number come from" is one click.
    # A rule-based exception has no metric at all, and then there is deliberately no link.
    page_url, page_title = METRIC_GROUP_PAGES.get(meta.get("group")) or ("", "")
    return render(request, "scm/analytics/supplychainalert/detail.html", {
        "obj": obj,
        "metric_label": METRIC_LABELS.get(obj.metric, ""),
        "metric_page_url": page_url,
        "metric_page_title": page_title,
        # Formatted through the SAME function a KpiSnapshot and a live tile use, so an alert can
        # never render its own number in a different shape from the page it points at.
        "observed_display": format_metric_value(obj.observed_value, unit),
        "threshold_display": format_metric_value(obj.threshold_value, unit),
        "evidence_rows": _evidence_rows(obj.detail),
        "subjects": _subject_links(obj),
        # `current=` re-admits the present holder even if their login has since been deactivated —
        # without it the select would silently drop the person the alert is actually assigned to.
        "assign_form": AlertAssignForm(tenant=request.tenant, current=obj.assigned_to_id),
        "snooze_form": AlertSnoozeForm(),
        "resolve_form": AlertResolveForm(),
    })


@login_required
@require_POST
def supplychainalert_delete(request, pk):
    """Delete the row outright.

    **No status gate, deliberately.** An alert is a triage record, not a financial document, and the
    row anybody actually needs to delete is a hand-raised one typed by mistake. A DETECTOR-raised
    row is a different thing and the message says so: ``dedupe_key`` matches only OPEN rows, so
    deleting one clears it exactly until the next detection pass, because the exception underneath
    is still true. Resolving is what records that somebody dealt with it; deleting only hides it.
    """
    obj = get_object_or_404(SupplyChainAlert.objects.only("pk", "dedupe_key"),
                            pk=pk, tenant=request.tenant)
    detector_raised = bool(obj.dedupe_key)
    response = crud_delete(request, model=SupplyChainAlert, pk=pk,
                           success_url="scm:supplychainalert_list")
    if detector_raised:
        messages.info(request, "That exception was raised by detection rather than by hand — if it "
                               "is still true it will be raised again on the next run. Resolving "
                               "it is what records that somebody dealt with it.")
    return response


# =================================================================================================
# The five lifecycle actions.
#
# Each one locks the row, calls the MODEL method, and audits the diff that method returns. The state
# rules — which statuses accept which move, what a re-run must not overwrite, when a live snooze is
# dropped — all live on SupplyChainAlert and are not repeated here. See the module docstring.
# =================================================================================================
def _run(request, pk, name, apply_changes, *, ok, noop):
    """Lock, apply, audit, message, redirect. The shared body of all five actions.

    ``select_for_update`` matters even though every model method is no-op safe: they are no-op safe
    against **what they read**, so two people acknowledging at once would otherwise both see
    ``open`` and the second would overwrite the first acknowledger — the first acknowledger is the
    true one. Re-reading inside the lock makes the loser a plain no-op (the 4.10 pattern).

    An EMPTY diff is the model saying *nothing changed* — already in that state, or already closed.
    That is information rather than an error, so it is messaged at info level and nothing is
    written to the audit trail: an audit row recording that nothing happened is noise that makes
    the rows recording something harder to find.
    """
    with transaction.atomic():
        alert = get_object_or_404(SupplyChainAlert.objects.select_for_update(),
                                  pk=pk, tenant=request.tenant)
        changes = apply_changes(alert)
    if changes:
        write_audit_log(request.user, alert, "update", {"action": name, **changes})
        messages.success(request, ok(alert))
    else:
        messages.info(request, noop(alert))
    return redirect(_return_url(alert.pk, request.GET))


def _form_errors(form):
    """Flatten a small action form's errors into one message line (the 4.10 action-view shape)."""
    return "; ".join(" ".join(errors) for errors in form.errors.values())


@login_required
@require_POST
def supplychainalert_acknowledge(request, pk):
    """Somebody has seen it — the step that stops an exception being unattended.

    Not admin-gated: acknowledging is the cheapest, most reversible act in the queue, and requiring
    a workspace administrator for it is how a queue stops being triaged at all.
    """
    return _run(
        request, pk, "acknowledge",
        lambda alert: alert.acknowledge(request.user),
        ok=lambda alert: f"{alert.number} acknowledged — it is now yours to close or hand on.",
        noop=lambda alert: (f"{alert.number} is already {alert.get_status_display().lower()}."
                            if alert.status != "acknowledged" else
                            f"{alert.number} was already acknowledged by "
                            f"{alert.acknowledged_by or 'somebody'}."))


@login_required
@require_POST
def supplychainalert_assign(request, pk):
    """Put a name on it. An empty choice un-assigns; only an OPEN alert can be handed to anybody."""
    # Tenant first: whether this 404s must not depend on the form being valid.
    alert = get_object_or_404(SupplyChainAlert.objects.only("pk", "assigned_to"),
                              pk=pk, tenant=request.tenant)
    # Same `current=` the detail page rendered with. Without it a form submitted UNCHANGED while the
    # present holder is deactivated would fail with "Select a valid choice" on a field nobody
    # touched — the queryset that draws the select and the one that validates it must agree.
    form = AlertAssignForm(request.POST, tenant=request.tenant, current=alert.assigned_to_id)
    if not form.is_valid():
        messages.error(request, _form_errors(form))
        return redirect(_return_url(pk, request.GET))
    assignee = form.cleaned_data.get("assigned_to")
    # The form's queryset is UX; THIS is the guard (L39 §2). A person and the exception they are
    # handed must agree on at least the workspace (L40 §3), and a crafted POST is precisely the
    # case a narrowed dropdown never held against. A superuser has tenant=None and is correctly
    # refused here — they are not a member of anybody's workspace.
    if assignee is not None and getattr(assignee, "tenant_id", None) != getattr(request.tenant,
                                                                               "pk", None):
        messages.error(request, "That user is not a member of this workspace.")
        return redirect(_return_url(pk, request.GET))
    return _run(
        request, pk, "assign",
        lambda alert: alert.assign(assignee),
        ok=lambda alert: (f"{alert.number} assigned to {alert.assigned_to}."
                          if alert.assigned_to_id else f"{alert.number} un-assigned."),
        noop=lambda alert: (f"{alert.number} is {alert.get_status_display().lower()} — a closed "
                            "exception is not handed to anybody."
                            if not alert.is_open else
                            f"{alert.number} is already assigned to "
                            f"{alert.assigned_to or 'nobody'}."))


@login_required
@require_POST
def supplychainalert_snooze(request, pk):
    """Suppress it for a number of days. Suppression, not closure — it comes back on its own."""
    get_object_or_404(SupplyChainAlert.objects.only("pk"), pk=pk, tenant=request.tenant)
    form = AlertSnoozeForm(request.POST)
    if not form.is_valid():
        messages.error(request, _form_errors(form))
        return redirect(_return_url(pk, request.GET))
    days = form.cleaned_data["snooze_days"]
    try:
        return _run(
            request, pk, "snooze",
            lambda alert: alert.snooze(days),
            ok=lambda alert: (f"{alert.number} snoozed until {alert.snoozed_until:%b %d, %Y}. It "
                              "returns to the queue on its own when the window runs out."),
            noop=lambda alert: (f"{alert.number} is {alert.get_status_display().lower()} — a "
                                "closed exception cannot be snoozed."
                                if not alert.is_open else
                                f"{alert.number} is already snoozed until "
                                f"{alert.snoozed_until:%b %d, %Y}."))
    except ValidationError as exc:
        # The model validates the 1-90 bound as well as the form, and the model is the real rule —
        # a management command or a test calling snooze() directly gets the same refusal. A wrong
        # VALUE is refused loudly; a wrong STATE stays a silent no-op above, because only the first
        # is the caller's mistake.
        messages.error(request, "; ".join(exc.messages))
        return redirect(_return_url(pk, request.GET))


@login_required
@require_POST
def supplychainalert_resolve(request, pk):
    """Close it as dealt with, with a note saying what was done."""
    get_object_or_404(SupplyChainAlert.objects.only("pk"), pk=pk, tenant=request.tenant)
    form = AlertResolveForm(request.POST)
    if not form.is_valid():
        messages.error(request, _form_errors(form))
        return redirect(_return_url(pk, request.GET))
    note = (form.cleaned_data.get("resolution_note") or "").strip()
    return _run(
        request, pk, "resolve",
        lambda alert: alert.resolve(request.user, note),
        ok=lambda alert: f"{alert.number} resolved.",
        noop=lambda alert: (f"{alert.number} was already closed by "
                            f"{alert.resolved_by or 'somebody'} "
                            f"({alert.get_status_display().lower()}) — re-closing it would only "
                            "overwrite who did."))


@login_required
@require_POST
def supplychainalert_dismiss(request, pk):
    """Close it as not worth acting on. Attributed through the same pair ``resolve`` uses."""
    return _run(
        request, pk, "dismiss",
        lambda alert: alert.dismiss(request.user),
        ok=lambda alert: (f"{alert.number} dismissed as not worth acting on. If a detector raised "
                          "it and it is still true, it will be raised again."),
        noop=lambda alert: (f"{alert.number} was already closed by "
                            f"{alert.resolved_by or 'somebody'} "
                            f"({alert.get_status_display().lower()})."))


# =================================================================================================
# Detection
# =================================================================================================
@tenant_admin_required
@require_POST
def supplychainalert_detect(request):
    """Run every detector now. **Calls ``analytics.detect_alerts`` and reimplements nothing.**

    ``@tenant_admin_required`` because this is the one action in 4.11 that CREATES rows: every other
    view here reads, or edits triage state on a row that already exists. It is also a BATCH — every
    alerting target computed plus ten rule-based passes, on the order of a hundred queries on a
    seeded tenant — which is why it is a POST button and never a page load.

    The summary is reported in full rather than as a single number. ``below_impact`` in particular
    is a SUPPRESSION the operator configured (``KpiTarget.min_impact_value``), and a suppression
    nobody can see is how an impact floor quietly becomes a blindfold; ``skipped`` means a target
    could not be computed at all, which is a configuration problem and not a quiet day.
    """
    if _need_tenant(request):
        return redirect("scm:supplychainalert_list")
    summary = analytics.detect_alerts(request.tenant, user=request.user)
    created, updated = summary.get("created", 0), summary.get("updated", 0)
    write_audit_log(request.user, None, "create", {
        "action": "detect_alerts",
        "created": created,
        "updated": updated,
        "targets": summary.get("targets", 0),
        "breaches": summary.get("breaches", 0),
        "exceptions": summary.get("exceptions", 0),
        "below_impact": summary.get("below_impact", 0),
        "skipped": summary.get("skipped", 0),
    }, tenant=request.tenant)

    if created or updated:
        messages.success(request, f"Detection complete — {created} new exception(s) raised and "
                                  f"{updated} existing one(s) re-fired. A repeat breach moves the "
                                  "'last seen' stamp on the alert that is already open; it never "
                                  "adds a second row.")
    else:
        messages.info(request, f"Detection complete — nothing is breaching. "
                               f"{summary.get('targets', 0)} alerting target(s) were evaluated.")
    if summary.get("below_impact"):
        messages.info(request, f"{summary['below_impact']} breach(es) were below their target's "
                               "minimum impact value and raised nothing. That floor is what keeps "
                               "the queue worth opening — raise or clear it on the target if you "
                               "want them through.")
    if summary.get("skipped"):
        messages.warning(request, f"{summary['skipped']} target(s) could not be computed and were "
                                  "skipped — usually a scope subject that has since been deleted. "
                                  "Open the target to see which.")
    return redirect(_return_url(None, request.GET))
