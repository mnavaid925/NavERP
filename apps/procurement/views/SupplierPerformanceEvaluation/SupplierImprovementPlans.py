"""Procurement 6.16 Supplier Performance & Evaluation — SupplierImprovementPlan views.

The PIP register: open a plan off a bad period, work it, and close it with a recorded outcome.
Ten routes — list, create, detail, edit, five POST verbs and delete.

**The five verbs are why ``status`` and ``outcome`` are not on the form.** ``draft`` is the only
value a create can produce; ``active``, ``monitoring``, ``closed`` and ``cancelled`` are reachable
ONLY through ``improvementplan_activate`` / ``_monitor`` / ``_close`` / ``_cancel``, and all four
``OUTCOME_CHOICES`` are reachable only through ``_close``. Every choice is therefore reachable and
none is dead — a status nothing can set is a lie in a dropdown, and one anyone can type is a claim
with nothing behind it. Each verb guards its own legal source statuses in ONE shared helper,
stamps its columns with an explicit ``update_fields``, and writes its own audit row.

**``acknowledge`` moves no status, and that is the point.** It records that the supplier was told
— on a draft, an active or a monitoring plan — and it is idempotent by refusal: a second
acknowledgement is rejected rather than silently re-stamping, because the first one is the date
that matters. It is the only verb whose gate is a stamp (``acknowledged_at is None``) rather than
a status.

**``close`` is the only ``@tenant_admin_required`` route here.** Closing a plan writes the
outcome the supplier will be shown, signs it (``verified_by`` / ``verified_at``) and stops the
overdue clock; that is a sign-off, not an edit. The posted ``outcome`` is validated against the
model's own ``OUTCOME_CHOICES`` before anything is written — this verb does not go through a
form, so nothing else would — and a close with no outcome is REFUSED with a message rather than
saved as an ending nobody named.

Discipline a reviewer will otherwise go looking for:

* **Every queryset is ``filter(tenant=request.tenant)``** — never ``.all()``, so another
  workspace's pk is a 404 rather than a leak, on the verbs as much as on the pages.
* **``stats`` is ONE conditional ``aggregate()``**, counted over the WHOLE workspace rather than
  the filtered page: a stat card answers "where do we stand?", which must not change because
  somebody typed a search. ``overdue`` is computed IN THE ORM through the same
  ``COALESCE(extended_close_date, target_close_date)`` the model's ``effective_close_date``
  property resolves, so the stat and the row badge can never disagree about which plans are late.
* **``crud_edit``'s ``success_url`` is handed to ``redirect()`` with NO args**, so a route taking
  a pk must be passed as an already-reversed PATH — a bare url NAME would ``NoReverseMatch`` at
  save time, not at import time.
* **The detail page renders many FKs**, so every one a template or a ``__str__`` hops is
  ``select_related``.

**Import discipline.** Two kinds of not-yet-wired import live here, both deliberate:

1. This sub-module's own model and form come from their ENTITY modules at module top, never from
   ``apps.procurement.models`` / ``.forms`` — the package ``__init__`` re-export blocks land at
   Integrate, and a package-level import would be a star-import cycle at URLconf import time (the
   ``CostForecasts.py`` precedent).
2. ``core.Party`` is imported INSIDE the function that needs it, so this module imports cleanly
   on its own and cannot start a cycle.
"""
import os

from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.db.models.functions import Coalesce
from django.http import FileResponse
from django.urls import reverse

# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULES directly — see the
# module docstring.
from apps.procurement.forms.SupplierPerformanceEvaluation.SupplierImprovementPlans import (
    SupplierImprovementPlanForm)
from apps.procurement.models.SupplierPerformanceEvaluation.SupplierImprovementPlans import (
    OPEN_STATUSES, OUTCOME_CHOICES, SEVERITY_CHOICES, STATUS_CHOICES, SupplierImprovementPlan)
from apps.procurement.models.SupplierPerformanceEvaluation.SupplierKpis import SupplierKpi
from apps.procurement.views._common import *  # noqa: F401,F403

TEMPLATE_LIST = "procurement/performance/improvementplan/list.html"
TEMPLATE_DETAIL = "procurement/performance/improvementplan/detail.html"
TEMPLATE_FORM = "procurement/performance/improvementplan/form.html"

#: The FKs a plan row hops in a template or in ``__str__``. ONE tuple, so the register, the
#: detail page and the verbs cannot drift into different N+1 profiles.
#:
#: ``scorecard__party`` is the CHAINED hop, and it was missing: ``improvementplan/detail.html``
#: renders ``{{ obj.scorecard.party.name }}``, so a plan carrying a scorecard cost 10 queries
#: against 9 for one without — the extra being a bare ``SELECT FROM core_party``. One query on a
#: detail page, but this tuple is also what the paginated register joins on, so the day a list
#: column prints the supplier off the scorecard it becomes 1+N for a 15-row page (L18). The
#: sibling ``_SCORE_RELATIONS`` carries the chained hop for exactly this reason.
_ROW_RELATIONS = ("supplier", "kpi", "owner", "scorecard", "scorecard__party",
                  "escalated_suspension")

#: Legal outcome values, keyed by the posted string — the close verb validates against this
#: rather than trusting the request, because close does not go through a form at all.
_OUTCOME_VALUES = dict(OUTCOME_CHOICES)


def _is_admin(request):
    """Mirrors ``@tenant_admin_required`` exactly, so a hidden button and a refused POST agree.

    The local-copy convention twelve sibling view modules follow (6.3, 6.12 and 6.13 each carry
    the same three lines). Without it ``can_close`` offered the close form to every member —
    while the page's own help text said closing was admin-only — and the POST then 403'd.
    """
    return bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False))


#: Printed where the close form would have been, so a non-admin reads why rather than finding a
#: control missing. The verb's own copy says closing is admin-only; this is the same sentence
#: reaching the person it applies to.
_CLOSE_NOT_ADMIN = ("Closing signs the ending the supplier will be shown, so it is a "
                    "workspace-admin action — ask an admin of this workspace to close it.")


def _plan_qs(request):
    """The register's base queryset — tenant-scoped, with every rendered FK joined."""
    return (SupplierImprovementPlan.objects.filter(tenant=request.tenant)
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


def _plan_owners(request):
    """Whoever actually owns a plan in this workspace — not every user in it.

    ``.none()`` for a tenant-less user (the superuser has ``tenant=None``), so the filter bar
    renders empty rather than offering the whole directory (the ``_kpi_owners`` precedent).
    """
    users = get_user_model().objects
    if request.tenant is None:
        return users.none()
    return (users.filter(tenant=request.tenant, procurement_improvement_plans__isnull=False)
            .distinct().order_by("email"))


def _plan_stats(tenant):
    """``{total, active, monitoring, overdue, closed}`` in ONE query.

    ``overdue`` is the model's own rule expressed in SQL: a plan in an OPEN status whose
    ``COALESCE(extended_close_date, target_close_date)`` has passed. It goes through the same
    coalesce ``SupplierImprovementPlan.effective_close_date`` resolves in Python, so a granted
    extension is honoured identically by the stat card and by the row badge next to it —
    re-deriving "late" from ``target_close_date`` alone here would quietly report every extended
    plan as overdue.

    Counted over the whole workspace on purpose: a stat card answers "where do we stand?", which
    must not change because somebody typed a search.
    """
    return (SupplierImprovementPlan.objects.filter(tenant=tenant)
            .annotate(effective_close=Coalesce("extended_close_date", "target_close_date"))
            .aggregate(
                total=Count("pk"),
                active=Count("pk", filter=Q(status="active")),
                monitoring=Count("pk", filter=Q(status="monitoring")),
                overdue=Count("pk", filter=Q(status__in=OPEN_STATUSES,
                                             effective_close__lt=timezone.localdate())),
                closed=Count("pk", filter=Q(status="closed")),
            ))


@login_required
def improvementplan_list(request):
    """The PIP register, newest start date first (model ordering).

    Six filters. ``supplier``, ``owner`` and ``kpi`` are FKs and ride the ``is_int=True`` path so
    a hand-edited query string cannot 500 the page (L11); ``status``, ``severity`` and ``outcome``
    are plain CHOICES strings, which ``crud_list`` validates against the field's own choices and
    SKIPS when they do not match, rather than silently emptying the register.
    """
    return crud_list(
        request, _plan_qs(request), TEMPLATE_LIST,
        search_fields=("number", "title", "finding", "supplier__name"),
        filters=(("supplier", "supplier_id", True),
                 ("status", "status", False),
                 ("severity", "severity", False),
                 ("outcome", "outcome", False),
                 ("owner", "owner_id", True),
                 ("kpi", "kpi_id", True)),
        extra_context={
            "status_choices": STATUS_CHOICES,
            "severity_choices": SEVERITY_CHOICES,
            "outcome_choices": OUTCOME_CHOICES,
            "suppliers": _supplier_parties(request),
            "kpis": SupplierKpi.objects.filter(tenant=request.tenant)
                                       .order_by("display_order", "code"),
            "owners": _plan_owners(request),
            "stats": _plan_stats(request.tenant),
        },
    )


@login_required
def improvementplan_detail(request, pk):
    """One plan: what was found, what was agreed, where it stands, and what can still happen.

    The five ``can_*`` flags are passed SEPARATELY rather than as one "is open" flag, because
    they gate five different verbs with three different rules — ``can_activate`` is draft-only,
    ``can_monitor`` is active-only, ``can_acknowledge`` keys on a STAMP rather than a status, and
    ``can_close`` excludes draft (there is nothing to verify on a plan that never started) AND
    tests ``_is_admin``, because closing is the one ``@tenant_admin_required`` verb here. They
    are the UX half of the rule: every verb re-checks its own gate, so a crafted POST against a
    closed plan is refused there too.

    ``is_overdue`` is surfaced as a context key so the template reads the property once rather
    than calling it in both the header badge and the dates panel.
    """
    obj = get_object_or_404(SupplierImprovementPlan.objects.only(
        "pk", "tenant_id", "status", "acknowledged_at", "target_close_date",
        "extended_close_date"), pk=pk, tenant=request.tenant)
    return crud_detail(
        request, model=SupplierImprovementPlan, pk=pk, template=TEMPLATE_DETAIL,
        select_related=(*_ROW_RELATIONS, "acknowledged_by", "verified_by"),
        extra_context={
            "outcome_choices": OUTCOME_CHOICES,
            "can_activate": obj.status == "draft",
            "can_monitor": obj.status == "active",
            "can_acknowledge": obj.status in OPEN_STATUSES and obj.acknowledged_at is None,
            # ``improvementplan_close`` is @tenant_admin_required, so the admin test belongs on
            # the flag as well: a form that renders for everybody and then 403s is worse than no
            # form. ``close_refusal`` is what the page prints in its place.
            "can_close": obj.status in ("active", "monitoring") and _is_admin(request),
            # Non-empty ONLY when the admin rule is what hid the form. A draft, cancelled or
            # already-closed plan has no close form for anybody, and printing "ask an admin"
            # there would offer a route that does not exist.
            "close_refusal": ("" if _is_admin(request)
                              or obj.status not in ("active", "monitoring")
                              else _CLOSE_NOT_ADMIN),
            "can_cancel": obj.status in OPEN_STATUSES,
            "is_overdue": obj.is_overdue,
        },
    )


@login_required
def improvementplan_create(request):
    """Open a plan. ``crud_create`` stamps the tenant and refuses a tenant-less user.

    ``status`` is left at its ``draft`` default — this view never sets it, and neither does the
    form. The lifecycle belongs to the five verbs below, so a plan starts as a draft that has not
    yet been put to the supplier.

    ``crud_create`` passes ``request.FILES`` through, which is what makes the ``evidence`` upload
    work; the form's ``clean_evidence`` applies the extension allowlist and the size cap.
    """
    return crud_create(request, form_class=SupplierImprovementPlanForm, template=TEMPLATE_FORM,
                       success_url="procurement:improvementplan_list")


@login_required
def improvementplan_edit(request, pk):
    """Correct a plan — the finding, the actions, the dates, the owners, the evidence.

    ``status`` and ``outcome`` are not on the form, so editing can never move a plan through its
    lifecycle or write an ending: that is what the five verbs are for. The acknowledgement and
    verification stamps are equally untouchable — a stamp that could be edited would stop being
    evidence of anything.

    Granting an extension IS an edit, not a verb: ``extended_close_date`` is on the form, and the
    model refuses one that does not fall strictly after the original target.

    **OPEN plans only.** "Editing cannot move the lifecycle" was true and beside the point: the
    payload is not the status. A closed plan carries ``verified_by``/``verified_at`` against the
    finding, the root cause, the corrective actions and the dates — so leaving it editable let
    any member rewrite the content a signature sits beside. The same ``OPEN_STATUSES`` gate
    ``ContractsManagement/Milestones.py`` puts on its own edit and delete.

    ``crud_edit`` hands ``success_url`` straight to ``redirect()`` with no arguments, so a route
    taking a pk must be an already-reversed PATH: passing the url NAME here would raise
    ``NoReverseMatch`` at save time, not at import time.
    """
    obj = get_object_or_404(SupplierImprovementPlan.objects.only("pk", "tenant_id", "status"),
                            pk=pk, tenant=request.tenant)
    if obj.status not in OPEN_STATUSES:
        messages.error(request, f"This plan is {obj.get_status_display().lower()} and its "
                                "record is frozen — a closed plan is signed, and a cancelled one "
                                "is history. Neither can be edited.")
        return redirect("procurement:improvementplan_detail", pk=pk)

    return crud_edit(
        request, model=SupplierImprovementPlan, pk=pk, form_class=SupplierImprovementPlanForm,
        template=TEMPLATE_FORM,
        success_url=reverse("procurement:improvementplan_detail", args=[pk]))


@login_required
def improvementplan_evidence(request, pk):
    """Hand back this plan's uploaded evidence — authenticated, tenant-scoped, as an attachment.

    WARNING, and the reason this view exists: ``evidence.url`` is a raw ``MEDIA_URL`` path served
    by the web server, so linking it hands the file to anybody who can guess a filename under the
    month's folder — no login, no session, no tenant. An NCR pack or an audit report attached to
    a supplier's plan is exactly what must not be readable that way. The upload validation is
    already correct (``clean_evidence`` applies the extension allow-list and the size cap); the
    gap was purely in SERVING. Mirrors ``DocumentKnowledgeManagement/Revisions.py``'s
    ``pdocrevision_download``, which is the app's precedent for this.

    Two headers do the rest:

    * ``Content-Disposition: attachment`` — the bytes are handed to the browser to save, never
      rendered on this origin. An uploaded ``.html`` served inline would be stored XSS against
      every logged-in member of the workspace.
    * ``X-Content-Type-Options: nosniff`` — ``SECURE_CONTENT_TYPE_NOSNIFF`` only applies outside
      DEBUG, so it is set here rather than assumed.
    """
    obj = get_object_or_404(
        SupplierImprovementPlan.objects.only("pk", "tenant_id", "number", "evidence"),
        pk=pk, tenant=request.tenant)
    if not obj.evidence:
        messages.error(request, f"{obj.number} has no uploaded evidence file — its proof may be "
                                "the linked one instead.")
        return redirect("procurement:improvementplan_detail", pk=pk)

    try:
        handle = obj.evidence.open("rb")
    except (OSError, ValueError):
        # The row can outlive its bytes: a file removed from MEDIA_ROOT behind Django's back has
        # to be a message on the page it was linked from, never a 500 on a download click.
        messages.error(request, f"The evidence stored against {obj.number} could not be read "
                                "back from storage.")
        return redirect("procurement:improvementplan_detail", pk=pk)

    # The stored basename, with any CR/LF removed: it is user-supplied and it is about to be
    # written into a response header. Django refuses a header carrying a newline outright
    # (BadHeaderError); stripping is what keeps that correct refusal from becoming a 500.
    filename = os.path.basename(obj.evidence.name) or f"{obj.number}-evidence"
    filename = filename.replace("\r", " ").replace("\n", " ")

    response = FileResponse(handle, as_attachment=True, filename=filename)
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _plan_in(request, pk, statuses, verb):
    """``(obj, None)`` when the plan is in one of ``statuses``, ``(None, response)`` when it is not.

    The ONE status gate every verb shares, so they cannot drift into disagreeing about which
    plans are still movable. A plan in the wrong state gets a message naming what it already is —
    silently redirecting would look like the verb had worked.
    """
    obj = get_object_or_404(SupplierImprovementPlan.objects.select_related("supplier"), pk=pk,
                            tenant=request.tenant)
    if obj.status not in statuses:
        messages.error(
            request,
            f"{obj.number} is {obj.get_status_display().lower()} — only a plan that is "
            f"{' or '.join(statuses)} can be {verb}.")
        return None, redirect("procurement:improvementplan_detail", pk=pk)
    return obj, None


@login_required
@require_POST
def improvementplan_activate(request, pk):
    """Put a drafted plan into force — it has been agreed and the clock is running.

    Draft-only: re-activating a plan already being worked would reset nothing and mean nothing,
    and activating a closed one would re-open an ending somebody signed off.
    """
    obj, refusal = _plan_in(request, pk, ("draft",), "activated")
    if refusal is not None:
        return refusal

    obj.status = "active"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "activate",
                    changes={"action": "activate", "status": obj.status}, tenant=request.tenant)
    messages.success(request, f"Plan {obj.number} is now active — due "
                              f"{obj.effective_close_date:%b %d, %Y}.")
    return redirect("procurement:improvementplan_detail", pk=pk)


@login_required
@require_POST
def improvementplan_monitor(request, pk):
    """Move an active plan into monitoring: the actions are done, the results are being watched.

    Kept distinct from ``closed`` on purpose. A supplier that fixes a process in week two has not
    proved anything until the next period's numbers come in, and closing at the moment the work
    stops would record a success nobody has evidence for yet.
    """
    obj, refusal = _plan_in(request, pk, ("active",), "moved to monitoring")
    if refusal is not None:
        return refusal

    obj.status = "monitoring"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "monitor",
                    changes={"action": "monitor", "status": obj.status}, tenant=request.tenant)
    messages.success(request, f"Plan {obj.number} is now being monitored — the corrective work "
                              "is done and the results are being watched.")
    return redirect("procurement:improvementplan_detail", pk=pk)


@login_required
@require_POST
def improvementplan_acknowledge(request, pk):
    """Record that the supplier has been told — the ONE verb that moves no status.

    Acknowledgement is evidence that the plan was put to the supplier, which is the fact a
    disputed escalation turns on later. It is legal on a draft (the plan was sent for agreement),
    an active plan and a monitored one, and it is refused once already stamped: re-stamping would
    overwrite the date that matters with a later one.
    """
    obj, refusal = _plan_in(request, pk, OPEN_STATUSES, "acknowledged")
    if refusal is not None:
        return refusal
    if obj.acknowledged_at is not None:
        messages.error(request, f"{obj.number} was already acknowledged on "
                                f"{obj.acknowledged_at:%b %d, %Y} — the first acknowledgement is "
                                "the date that counts, so it is not re-stamped.")
        return redirect("procurement:improvementplan_detail", pk=pk)

    obj.acknowledged_by = request.user if request.user.is_authenticated else None
    obj.acknowledged_at = timezone.now()
    obj.save(update_fields=["acknowledged_by", "acknowledged_at", "updated_at"])
    write_audit_log(request.user, obj, "acknowledge",
                    changes={"action": "acknowledge", "status": obj.status}, tenant=request.tenant)
    messages.success(request, f"Plan {obj.number} acknowledged — the supplier has been recorded "
                              "as having received it. Its status is unchanged.")
    return redirect("procurement:improvementplan_detail", pk=pk)


@require_POST
@tenant_admin_required
def improvementplan_close(request, pk):
    """Close a plan with a recorded outcome, and sign the closure. **Admin-only.**

    Closing writes the ending the supplier will be shown, stamps ``verified_by`` /
    ``verified_at`` against it and stops the overdue clock. That is a sign-off rather than an
    edit, which is why this is the one ``@tenant_admin_required`` route in the register.

    The posted ``outcome`` is checked against the model's own ``OUTCOME_CHOICES`` before anything
    is written — this verb does not go through a form, so nothing else would — and a close with a
    missing or unrecognised outcome is REFUSED with a message. The model says the same thing (a
    closed plan must carry an outcome), but reaching it would raise a ``ValidationError`` page
    instead of telling the operator what to do about it.

    Draft is excluded on purpose: there is nothing to verify on a plan that never started. Cancel
    it instead.
    """
    obj, refusal = _plan_in(request, pk, ("active", "monitoring"), "closed")
    if refusal is not None:
        return refusal

    outcome = (request.POST.get("outcome") or "").strip()
    if outcome not in _OUTCOME_VALUES:
        messages.error(request, "Pick how this plan ended before closing it — successful, "
                                "extended, failed or escalated to suspension. A closed plan with "
                                "no outcome records nothing.")
        return redirect("procurement:improvementplan_detail", pk=pk)

    obj.status = "closed"
    obj.outcome = outcome
    obj.closure_note = (request.POST.get("closure_note") or "").strip()
    obj.actual_close_date = timezone.localdate()
    obj.verified_by = request.user if request.user.is_authenticated else None
    obj.verified_at = timezone.now()
    obj.save(update_fields=["status", "outcome", "closure_note", "actual_close_date",
                            "verified_by", "verified_at", "updated_at"])
    write_audit_log(request.user, obj, "close",
                    changes={"action": "close", "status": obj.status, "outcome": obj.outcome,
                             "actual_close_date": str(obj.actual_close_date)},
                    tenant=request.tenant)
    messages.success(request, f"Plan {obj.number} closed as "
                              f"{_OUTCOME_VALUES[outcome].lower()}, verified by you.")
    return redirect("procurement:improvementplan_detail", pk=pk)


@login_required
@require_POST
def improvementplan_cancel(request, pk):
    """Withdraw a plan that should not have been opened, or that events overtook.

    Distinct from a ``failed`` closure, and the distinction is the whole reason both exist:
    cancelled means the plan stopped being the right thing to do (the supplier was replaced, the
    finding turned out to be ours), while failed means it ran and did not work. Collapsing them
    would make the success rate unreadable — and a cancelled plan carries no outcome at all,
    because it has no ending to record.
    """
    obj, refusal = _plan_in(request, pk, OPEN_STATUSES, "cancelled")
    if refusal is not None:
        return refusal

    obj.status = "cancelled"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "cancel",
                    changes={"action": "cancel", "status": obj.status}, tenant=request.tenant)
    messages.success(request, f"Plan {obj.number} cancelled — withdrawn rather than failed, so "
                              "it carries no outcome.")
    return redirect("procurement:improvementplan_detail", pk=pk)


@login_required
@require_POST
def improvementplan_delete(request, pk):
    """Remove a plan raised by mistake — the wrong supplier, a duplicate, a test row.

    Deleting a CLOSED plan removes the record that a supplier was ever put on one, which is
    exactly the history an escalation stands on: a suspension raised "after two failed plans"
    means nothing once the plans are gone. Cancel an open plan instead of deleting it, and leave
    a closed one where it is. The templates say so at the point of deletion.

    **OPEN plans only**, which is what makes the paragraph above enforceable rather than advice:
    a closed plan is the record that a supplier was put on one, signed by whoever verified it,
    and the page told the reader to cancel an open plan instead — while still offering the bin
    on the closed one to every member.

    The ``escalated_suspension`` pointer is only a pointer: deleting the plan leaves 6.4's block
    register untouched, so a vendor that is blocked stays blocked.
    """
    obj = get_object_or_404(SupplierImprovementPlan.objects.only("pk", "tenant_id", "status"),
                            pk=pk, tenant=request.tenant)
    if obj.status not in OPEN_STATUSES:
        messages.error(request, f"This plan is {obj.get_status_display().lower()} and is part of "
                                "the supplier's history — exactly what an escalation stands on. "
                                "It cannot be deleted.")
        return redirect("procurement:improvementplan_detail", pk=pk)

    return crud_delete(request, model=SupplierImprovementPlan, pk=pk,
                       success_url="procurement:improvementplan_list")
