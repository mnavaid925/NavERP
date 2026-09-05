"""Procurement 6.16 Supplier Performance & Evaluation — SupplierFeedback views.

The 360 register: request a response, read it, correct it, and move it through its lifecycle.
Eight routes — list, create, detail, edit, three POST verbs and delete.

**The three verbs are why ``status`` is not on the form.** ``requested`` is the only value a
create can produce; ``submitted``, ``declined`` and ``expired`` are reachable ONLY through
``supplierfeedback_submit`` / ``_decline`` / ``_expire``. Every choice is therefore reachable and
none is dead — a status nothing can set is a lie in a dropdown, and a status anyone can type is a
claim with nothing behind it. Each verb guards the one legal source status (``requested``),
stamps its own columns with an explicit ``update_fields``, and writes its own audit row.

**Submit takes the rating from the request when the row has none.** The ordinary flow is "request
now, rate later", so the row is usually unrated when submit arrives; the posted value is checked
against ``dict(RATING_CHOICES)`` keyed by ``int`` before it is written, and a submit with no
rating anywhere is refused with a message rather than saved as an answer nobody gave (the model's
own rule says the same thing — this view refuses first so the failure is a message, not a
``ValidationError`` page).

**Create is hand-rolled, not ``crud_create``.** ``requested_by`` is stamped from ``request.user``
between ``is_valid()`` and ``save()``, and the shared helper has no hook for that — the
``costforecast_create`` precedent. It therefore also refuses a tenant-less user itself and writes
its own audit row.

Discipline a reviewer will otherwise go looking for:

* **Every queryset is ``filter(tenant=request.tenant)``** — never ``.all()``, including the
  cross-app scorecard dropdown, so another workspace's pk is a 404 rather than a leak.
* **``stats`` is ONE conditional ``aggregate()``**, counted over the WHOLE workspace rather than
  the filtered page: a stat card answers "where do we stand?", which must not change because
  somebody typed a search.
* **``crud_edit``'s ``success_url`` is handed to ``redirect()`` with NO args**, so a route taking
  a pk must be passed as an already-reversed PATH — a bare url NAME would ``NoReverseMatch`` at
  save time, not at import time.
* **``rating`` is an INT-valued CHOICES field**, so it is not a ``crud_list`` filter at all
  (``crud_list``'s enum guard only handles string choices). It rides the register as a legend.

**Import discipline.** Two kinds of not-yet-wired import live here, both deliberate:

1. This sub-module's own model and form come from their ENTITY modules at module top, never from
   ``apps.procurement.models`` / ``.forms`` — the package ``__init__`` re-export blocks land at
   Integrate, and a package-level import would be a star-import cycle at URLconf import time (the
   ``CostForecasts.py`` precedent).
2. ``scm.SupplierScorecard`` and ``core.Party`` are imported INSIDE the function that needs them,
   so this module imports cleanly on its own and cannot start a cycle.
"""
from django.db.models import Count, Q
from django.urls import reverse

from apps.core.crud import as_db_int
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULES directly — see the
# module docstring.
from apps.procurement.forms.SupplierPerformanceEvaluation.SupplierFeedback import (
    SupplierFeedbackForm)
from apps.procurement.models.SupplierPerformanceEvaluation.SupplierFeedback import (
    FUNCTION_CHOICES, RATING_CHOICES, RESPONDENT_KIND_CHOICES, STATUS_CHOICES, SupplierFeedback)
from apps.procurement.models.SupplierPerformanceEvaluation.SupplierKpis import SupplierKpi
from apps.procurement.views._common import *  # noqa: F401,F403

TEMPLATE_LIST = "procurement/performance/feedback/list.html"
TEMPLATE_DETAIL = "procurement/performance/feedback/detail.html"
TEMPLATE_FORM = "procurement/performance/feedback/form.html"

#: The FKs a response row hops in a template or in ``__str__``. ONE tuple, so the register, the
#: detail page and the edit lookup cannot drift into different N+1 profiles.
_ROW_RELATIONS = ("supplier", "scorecard", "kpi", "respondent")

#: The one status a response may be moved OUT of. Every verb below checks it, so a crafted POST
#: cannot re-submit an already-declined request or expire a submitted answer.
_OPEN_STATUS = "requested"

#: Legal rating values, keyed by int — the submit verb validates the posted value against this
#: rather than trusting the form, because submit does not go through a form at all.
_RATING_VALUES = dict(RATING_CHOICES)


def _need_tenant(request, what):
    """Refuse a tenant-less user (the superuser has ``tenant=None``) before any write.

    Mirrors ``crud_create``'s own guard so the hand-rolled create below cannot mint orphan rows
    that no workspace can ever see again.
    """
    if request.tenant is None:
        messages.error(request, f"Select a tenant workspace before you {what}.")
        return redirect("dashboard:home")
    return None


def _feedback_qs(request):
    """The register's base queryset — tenant-scoped, with every rendered FK joined."""
    return (SupplierFeedback.objects.filter(tenant=request.tenant)
            .select_related(*_ROW_RELATIONS))


def _supplier_parties(request):
    """The supplier/vendor cohort for the register's dropdown. ``.none()`` without a tenant.

    ``.distinct()`` is load-bearing: the PartyRole join would otherwise list a party carrying
    both the ``supplier`` and the ``vendor`` role twice.
    """
    from apps.core.models import Party
    if request.tenant is None:
        return Party.objects.none()
    return (Party.objects.filter(tenant=request.tenant,
                                 roles__role__in=("supplier", "vendor"))
            .distinct().order_by("name"))


def _survey_kpis(request):
    """Only SURVEY KPIs — the only kind a response can be attached to (the model refuses others)."""
    return (SupplierKpi.objects.filter(tenant=request.tenant, source="survey")
            .order_by("display_order", "code"))


def _scorecards(request):
    """The workspace's period documents, newest period first. Cross-app read, imported locally."""
    from apps.scm.models import SupplierScorecard
    return (SupplierScorecard.objects.filter(tenant=request.tenant)
            .select_related("party").order_by("-period_end", "-id"))


def _feedback_stats(tenant):
    """``{total, requested, submitted, declined, overdue}`` in ONE query.

    ``overdue`` is a still-``requested`` response whose due date has passed — the same rule
    ``SupplierFeedback.is_overdue`` states per row, expressed once here as a filtered ``Count``
    so the stat costs nothing extra. Counted over the whole workspace on purpose: a stat card
    answers "where do we stand?", which must not change because somebody typed a search.
    """
    return SupplierFeedback.objects.filter(tenant=tenant).aggregate(
        total=Count("pk"),
        requested=Count("pk", filter=Q(status="requested")),
        submitted=Count("pk", filter=Q(status="submitted")),
        declined=Count("pk", filter=Q(status="declined")),
        overdue=Count("pk", filter=Q(status="requested",
                                     due_date__lt=timezone.localdate())),
    )


@login_required
def supplierfeedback_list(request):
    """The 360 register, newest period first (model ordering).

    Six filters. ``supplier``, ``kpi`` and ``scorecard`` are FKs and ride the ``is_int=True`` path
    so a hand-edited query string cannot 500 the page (L11); ``status``, ``kind`` and ``function``
    are plain CHOICES strings, which ``crud_list`` validates against the field's own choices and
    SKIPS when they do not match, rather than silently emptying the register.

    ``rating`` is deliberately NOT a filter: its choices are integers, which ``crud_list``'s enum
    guard does not cover, so ``rating_choices`` rides the page as the scale's legend instead.
    """
    return crud_list(
        request, _feedback_qs(request), TEMPLATE_LIST,
        search_fields=("number", "supplier__name", "respondent_name", "comment"),
        filters=(("supplier", "supplier_id", True),
                 ("status", "status", False),
                 ("kind", "respondent_kind", False),
                 ("function", "respondent_function", False),
                 ("kpi", "kpi_id", True),
                 ("scorecard", "scorecard_id", True)),
        extra_context={
            "status_choices": STATUS_CHOICES,
            "kind_choices": RESPONDENT_KIND_CHOICES,
            "function_choices": FUNCTION_CHOICES,
            "rating_choices": RATING_CHOICES,
            "suppliers": _supplier_parties(request),
            "kpis": _survey_kpis(request),
            "scorecards": _scorecards(request),
            "stats": _feedback_stats(request.tenant),
        },
    )


@login_required
def supplierfeedback_detail(request, pk):
    """One response: who was asked, what they said, and what can still happen to it.

    The three ``can_*`` flags are all ``status == "requested"`` today and are passed SEPARATELY
    rather than as one flag, because they gate three different verbs whose rules may diverge
    later — and because a template that reads ``can_submit`` next to a Submit button says what it
    means. They are the UX half of the rule: each verb re-checks the status itself, so a crafted
    POST against a submitted response is refused there too.

    The status is read through a deliberately narrow ``.only()`` probe rather than by fetching
    the whole row twice — ``crud_detail`` does its own tenant-scoped fetch with every rendered
    FK joined, and duplicating that just to read one column would double the page's join cost.
    """
    open_now = get_object_or_404(
        SupplierFeedback.objects.only("pk", "tenant_id", "status"),
        pk=pk, tenant=request.tenant).status == _OPEN_STATUS
    return crud_detail(
        request, model=SupplierFeedback, pk=pk, template=TEMPLATE_DETAIL,
        select_related=(*_ROW_RELATIONS, "requested_by"),
        extra_context={
            "can_submit": open_now,
            "can_decline": open_now,
            "can_expire": open_now,
        },
    )


@login_required
def supplierfeedback_create(request):
    """Raise one feedback request. Hand-rolled so ``requested_by`` is stamped from the user.

    ``crud_create`` has no hook between ``is_valid()`` and ``save()``, and an authorship stamp
    taken from the form would be a claim the requester could edit (the ``costforecast_create``
    precedent). The tenant guard mirrors ``crud_create``'s own, so a tenant-less user cannot mint
    an orphan request here either.

    ``status`` is left at its ``requested`` default — this view never sets it, and neither does
    the form. The lifecycle belongs to the three verbs below.
    """
    guard = _need_tenant(request, "request supplier feedback")
    if guard is not None:
        return guard

    if request.method == "POST":
        form = SupplierFeedbackForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.requested_by = request.user if request.user.is_authenticated else None
            obj.save()
            write_audit_log(request.user, obj, "create", changes={
                "supplier": obj.supplier.name,
                "period": f"{obj.period_start} .. {obj.period_end}",
                "respondent_kind": obj.respondent_kind,
                "kpi": obj.kpi.code if obj.kpi_id else "",
                "status": obj.status,
            })
            messages.success(request, f"Feedback request {obj.number} raised.")
            return redirect("procurement:supplierfeedback_detail", pk=obj.pk)
    else:
        form = SupplierFeedbackForm(tenant=request.tenant)

    return render(request, TEMPLATE_FORM, {
        "form": form,
        "is_edit": False,
        "title": "Request supplier feedback",
        "submit_label": "Send request",
        "cancel_url": reverse("procurement:supplierfeedback_list"),
    })


@login_required
def supplierfeedback_edit(request, pk):
    """Correct a response — the window, the respondent, the rating, the weight, the comment.

    ``status`` is not on the form, so editing can never move a response through its lifecycle:
    that is what the three verbs are for. ``requested_by`` and ``requested_at`` are equally
    untouchable — a raise stamp that could be edited would stop being evidence of anything.

    ``crud_edit`` hands ``success_url`` straight to ``redirect()`` with no arguments, so a route
    taking a pk must be an already-reversed PATH: passing the url NAME here would raise
    ``NoReverseMatch`` at save time, not at import time.
    """
    return crud_edit(
        request, model=SupplierFeedback, pk=pk, form_class=SupplierFeedbackForm,
        template=TEMPLATE_FORM,
        success_url=reverse("procurement:supplierfeedback_detail", args=[pk]))


def _open_response(request, pk, verb):
    """``(obj, None)`` when the response is still open, ``(None, response)`` when it is not.

    The ONE status gate the three verbs share, so they cannot drift into disagreeing about which
    responses are still answerable. A closed response gets a message naming what it already is —
    silently redirecting would look like the verb had worked.
    """
    obj = get_object_or_404(SupplierFeedback.objects.select_related("supplier"), pk=pk,
                            tenant=request.tenant)
    if obj.status != _OPEN_STATUS:
        messages.error(
            request,
            f"{obj.number} is already {obj.get_status_display().lower()} — only an outstanding "
            f"request can be {verb}.")
        return None, redirect("procurement:supplierfeedback_detail", pk=pk)
    return obj, None


@login_required
@require_POST
def supplierfeedback_submit(request, pk):
    """File the answer: stamp the rating, the status and the moment it arrived.

    The rating may come from the row (a response filed complete on the create form) or from this
    POST (the ordinary "request now, rate later" flow). A posted value is checked against the
    model's own ``RATING_CHOICES`` keyed by ``int`` before it is written — this verb does not go
    through a form, so nothing else would.

    A submit with no rating anywhere is REFUSED with a message. The model says the same thing,
    but reaching it would raise a ``ValidationError`` page instead of telling the operator what
    to do about it.
    """
    obj, refusal = _open_response(request, pk, "submitted")
    if refusal is not None:
        return refusal

    rating = obj.rating
    posted = (request.POST.get("rating") or "").strip()
    if posted:
        # ``as_db_int``, never a bare ``int()``: ``isdecimal()`` is True for 5,000 digits and
        # ``int()`` then raises ``ValueError: Exceeds the limit (4300) for integer string
        # conversion`` — an uncaught 500 any member with an open response's pk could fire at
        # will. The helper length-checks BEFORE it parses, which is the same L11 guard
        # ``crud_list`` applies to every GET filter; this verb takes its value from a POST body
        # and goes through no form, so nothing else was applying it.
        number = as_db_int(posted)
        if number is None or number not in _RATING_VALUES:
            messages.error(request, "That is not one of the ratings on the 1-5 scale.")
            return redirect("procurement:supplierfeedback_detail", pk=pk)
        rating = number
    if rating is None:
        messages.error(request, "Pick a rating on the 1-5 scale before submitting this response "
                                "— a submitted response with no rating measures nothing.")
        return redirect("procurement:supplierfeedback_detail", pk=pk)

    obj.rating = rating
    obj.status = "submitted"
    obj.submitted_at = timezone.now()
    obj.save(update_fields=["rating", "status", "submitted_at", "updated_at"])
    write_audit_log(request.user, obj, "submit",
                    changes={"action": "submit", "rating": rating, "status": obj.status},
                    tenant=request.tenant)
    messages.success(request, f"Response {obj.number} submitted at {rating} out of 5.")
    return redirect("procurement:supplierfeedback_detail", pk=pk)


@login_required
@require_POST
def supplierfeedback_decline(request, pk):
    """Record that the respondent declined to answer.

    A declined request is not a bad rating and is never scored — ``survey_aggregate`` reads only
    submitted rows. Recording the refusal is still worth doing: it takes the request off the
    overdue list honestly, instead of leaving it open forever or deleting the evidence that it
    was ever asked.
    """
    obj, refusal = _open_response(request, pk, "declined")
    if refusal is not None:
        return refusal

    obj.status = "declined"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "decline",
                    changes={"action": "decline", "status": obj.status}, tenant=request.tenant)
    messages.success(request, f"Response {obj.number} recorded as declined.")
    return redirect("procurement:supplierfeedback_detail", pk=pk)


@login_required
@require_POST
def supplierfeedback_expire(request, pk):
    """Close an outstanding request nobody answered in time.

    Distinct from ``declined`` on purpose: declined means somebody said no, expired means the
    window closed. Collapsing the two would make the response rate unreadable — and this verb is
    also what keeps the ``expired`` choice reachable at all.
    """
    obj, refusal = _open_response(request, pk, "expired")
    if refusal is not None:
        return refusal

    obj.status = "expired"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "expire",
                    changes={"action": "expire", "status": obj.status}, tenant=request.tenant)
    messages.success(request, f"Response {obj.number} closed as expired.")
    return redirect("procurement:supplierfeedback_detail", pk=pk)


@login_required
@require_POST
def supplierfeedback_delete(request, pk):
    """Remove a request raised by mistake — the wrong supplier, the wrong period, a duplicate.

    Deleting a SUBMITTED response removes evidence a survey KPI was computed from, and it does
    NOT re-derive any scorecard line already generated: those were written by the generate run
    that read this row, and silently re-blending them from a hand-trimmed set would move a
    figure the supplier has already been shown. Re-press Generate on a draft period to rebuild
    it from what is actually there. The templates say so at the point of deletion.
    """
    return crud_delete(request, model=SupplierFeedback, pk=pk,
                       success_url="procurement:supplierfeedback_list")
