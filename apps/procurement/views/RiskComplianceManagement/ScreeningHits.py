"""Procurement 6.17 Risk & Compliance Management — ScreeningHit views (the Resolution Manager).

Six routes: the cross-screening work queue, one hit's detail page, capture/amend/delete, and the
adjudication verb.

``ScreeningHit`` is **tenant-LESS by design** (the parent FK is the scope), so every object here
is resolved with ``screening__tenant=request.tenant`` and NEVER by pk alone. That single lookup
shape is the whole multi-tenant boundary for this entity — there is no second tenant column to
fall back on, so a route that forgets it is an IDOR.

Two guards that are easy to miss and cost the module its meaning if dropped:

* **A hit cannot be added to, amended on, or deleted from a screening that has already been
  decided.** Otherwise a new open hit appears under a cleared supplier and the clearance silently
  stops meaning anything — or, in the other direction, the match a block was reasoned against is
  deleted and the block stands with nothing behind it.
* **An adjudicated hit cannot be edited.** Its ``matched_name`` and score are what the
  disposition was reasoned against; changing them afterwards rewrites the record. Delete-and-
  recapture is the honest correction, and delete is audited.

Every write that can change how many hits are open calls ``screening.recount_hits()`` afterwards
— those counters are display values only, so a missed recount costs a wrong badge and can never
unlock the disposition gate (which re-asks the database).
"""
from django.db import transaction
from django.db.models import Count, Q

from apps.core.crud import _changed
from apps.procurement.forms.RiskComplianceManagement.Screenings import (
    ScreeningHitDispositionForm, ScreeningHitForm)
# NOT-YET-WIRED entities of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.RiskComplianceManagement.Screenings import (
    DISPOSITION_CHOICES, LIST_SOURCE_CHOICES, MATCH_TYPE_CHOICES, TERMINAL_DISPOSITIONS,
    ComplianceScreening, ScreeningHit)
from apps.procurement.views._common import *  # noqa: F401,F403

TEMPLATE_LIST = "procurement/riskcompliance/screeninghit/list.html"
TEMPLATE_DETAIL = "procurement/riskcompliance/screeninghit/detail.html"
TEMPLATE_FORM = "procurement/riskcompliance/screeninghit/form.html"

#: The dispositions a hit may be adjudicated TO. ``open`` is never offered — un-adjudicating a
#: hit is not something this module does.
_TERMINAL_DISPOSITION_CHOICES = [(value, label) for value, label in DISPOSITION_CHOICES
                                 if value in TERMINAL_DISPOSITIONS]

#: Every hop a queue row (or its parent's ``__str__``) walks.
_ROW_RELATIONS = ("screening", "screening__party")

#: Every hop the detail page walks.
_DETAIL_RELATIONS = _ROW_RELATIONS + ("disposed_by",)


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


def _hit_qs(request):
    """THE tenant boundary for this entity: the parent's tenant, never the hit's own."""
    return (ScreeningHit.objects.filter(screening__tenant=request.tenant)
            .select_related(*_ROW_RELATIONS))


def _get_hit(request, pk, relations=_ROW_RELATIONS):
    return get_object_or_404(ScreeningHit.objects.select_related(*relations),
                             pk=pk, screening__tenant=request.tenant)


def _get_screening(request, pk):
    return get_object_or_404(ComplianceScreening.objects.select_related("party"),
                             pk=pk, tenant=request.tenant)


def _stats(tenant):
    """The three queue stat cards, over the whole workspace rather than the filtered page."""
    return ScreeningHit.objects.filter(screening__tenant=tenant).aggregate(
        open=Count("id", filter=Q(disposition="open")),
        true_match=Count("id", filter=Q(disposition="true_match")),
        false_positive=Count("id", filter=Q(disposition="false_positive")),
    )


def _screening_options(tenant):
    """The parent-screening filter dropdown.

    ``select_related("party")`` because ``ComplianceScreening.__str__`` walks the party — without
    it every option in the list costs its own query.
    """
    if tenant is None:
        return ComplianceScreening.objects.none()
    return (ComplianceScreening.objects.filter(tenant=tenant).select_related("party")
            .order_by("-screened_on", "-id"))


# -- the work queue --------------------------------------------------------------------------------

@login_required
def screeninghit_list(request):
    """Every potential match in the workspace, across every screening — highest score first."""
    guard = _need_tenant(request, "review screening hits")
    if guard is not None:
        return guard
    return crud_list(
        request,
        _hit_qs(request),
        TEMPLATE_LIST,
        search_fields=["matched_name", "program", "country", "entry_reference", "remarks",
                       "screening__number", "screening__party__name"],
        # (get_param, orm_lookup, is_int). ``screening`` and ``min_score`` go through crud_list's
        # as_db_int guard; the three enum filters are checked against the model's own CHOICES
        # before they narrow, so a stale bookmark cannot silently empty the queue (L11).
        # ``match_score__gte`` is not a pk lookup, so a legitimate ?min_score=0 still filters.
        filters=[("disposition", "disposition", False),
                 ("matched_list", "matched_list", False),
                 ("match_type", "match_type", False),
                 ("screening", "screening_id", True),
                 ("min_score", "match_score__gte", True)],
        extra_context={
            # The FULL vocabulary here, ``open`` included — this is a filter, and "show me what
            # is still open" is the queue's whole reason to exist. (The adjudication PICKER, by
            # contrast, offers only the terminal values.)
            "disposition_choices": DISPOSITION_CHOICES,
            "list_source_choices": LIST_SOURCE_CHOICES,
            "match_type_choices": MATCH_TYPE_CHOICES,
            "screenings": _screening_options(request.tenant),
            "stats": _stats(request.tenant),
            "is_admin": _is_admin(request),
        },
    )


@login_required
def screeninghit_detail(request, pk):
    """One potential match: what was matched, and how it was adjudicated."""
    obj = _get_hit(request, pk, relations=_DETAIL_RELATIONS)
    return render(request, TEMPLATE_DETAIL, {
        "obj": obj,
        "screening": obj.screening,
        # Empty once adjudicated, so the page cannot offer a verb the model would refuse.
        "allowed_dispositions": _TERMINAL_DISPOSITION_CHOICES if obj.is_open else [],
        "disposition_form": ScreeningHitDispositionForm(tenant=request.tenant),
        "is_admin": _is_admin(request),
    })


# -- capture / amend ---------------------------------------------------------------------------------

def _hit_form(request, screening, instance=None):
    """Capture or amend one hit.

    Hand-rolled because ``screening`` is NOT a form field: it comes from the URL and is resolved
    against ``screening__tenant`` / ``tenant`` before we get here. Accepting it from the POST
    would let a crafted request file a hit against another workspace's screening.

    The context is the ``crud_*`` contract (``form`` + ``is_edit``, plus ``obj`` when editing)
    with ``screening`` added — the page cannot render its heading, its cancel link or its context
    without the parent.
    """
    is_edit = instance is not None

    if request.method == "POST":
        form = ScreeningHitForm(request.POST, request.FILES, instance=instance,
                                tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            # The parent is stamped from the URL-resolved object, never from the payload.
            obj.screening = screening
            obj.save()
            write_audit_log(request.user, obj, "update" if is_edit else "create", _changed(form))
            # A new hit is born ``open``, so the parent's counters move on create as well as on
            # dispose. Display values only — the gate re-asks the database.
            screening.recount_hits()
            messages.success(request, f"Hit “{obj.matched_name}” saved.")
            return redirect("procurement:screeninghit_detail", pk=obj.pk)
    else:
        form = ScreeningHitForm(instance=instance, tenant=request.tenant)

    ctx = {"form": form, "is_edit": is_edit, "screening": screening}
    if is_edit:
        ctx["obj"] = instance
    return render(request, TEMPLATE_FORM, ctx)


@login_required
def screeninghit_create(request, pk):
    """Record a potential match against one screening. ``pk`` is the SCREENING's."""
    guard = _need_tenant(request, "record screening hits")
    if guard is not None:
        return guard
    screening = _get_screening(request, pk)
    if screening.is_terminal:
        # Adding an open hit under a decided screening would silently invalidate the decision
        # that has already been recorded against it.
        messages.error(
            request,
            f"{screening.number} is already {screening.get_status_display().lower()} — a hit "
            f"cannot be added to a decided screening. Record a NEW screening instead.")
        return redirect("procurement:screening_detail", pk=screening.pk)
    return _hit_form(request, screening)


def _refuse_if_parent_decided(request, screening, verb):
    """A decided screening's hits are the evidence its decision was reasoned against.

    ``screeninghit_create`` already refuses this parent state; amend and delete must refuse it
    too, or the record can be rewritten (or emptied) *after* the clearance/block was recorded.
    Returns a redirect to refuse, or ``None`` to allow.
    """
    if screening.is_terminal:
        messages.error(
            request,
            f"{screening.number} is already {screening.get_status_display().lower()} — a hit "
            f"on a decided screening cannot be {verb}. It is the evidence that decision was "
            f"reasoned against. Record a NEW screening instead.")
        return redirect("procurement:screening_detail", pk=screening.pk)
    return None


@login_required
def screeninghit_edit(request, pk):
    """Amend a hit — refused once it has been adjudicated, or its screening decided."""
    obj = _get_hit(request, pk)
    refusal = _refuse_if_parent_decided(request, obj.screening, "amended")
    if refusal is not None:
        return refusal
    if not obj.is_open:
        # The matched name and score are what the disposition was reasoned against; editing them
        # afterwards rewrites the record. Delete and re-capture is the honest correction.
        messages.error(
            request,
            f"This hit was already adjudicated as {obj.get_disposition_display().lower()} and "
            f"can no longer be edited.")
        return redirect("procurement:screeninghit_detail", pk=pk)
    return _hit_form(request, obj.screening, instance=obj)


@login_required
@require_POST
def screeninghit_delete(request, pk):
    """Remove a hit that should never have been captured, and re-count the parent.

    Refused once the parent screening is decided: ``block()`` only requires an OPEN status, not
    disposed hits, so a blocked screening routinely still carries open hits — and deleting one
    would leave the block standing with no match behind it.
    """
    obj = _get_hit(request, pk)
    screening = obj.screening
    refusal = _refuse_if_parent_decided(request, screening, "deleted")
    if refusal is not None:
        return refusal
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    screening.recount_hits()
    messages.success(request, "Hit deleted.")
    return redirect("procurement:screening_detail", pk=screening.pk)


# -- adjudication ---------------------------------------------------------------------------------

@login_required
@tenant_admin_required
@require_POST
def screeninghit_dispose(request, pk):
    """Adjudicate one hit. Terminal dispositions only, and the reasoning is required.

    The row is locked for the duration: two officers adjudicating the same hit must not both
    stamp it, and the parent's counters are recomputed from the committed state afterwards.
    """
    guard = _need_tenant(request, "adjudicate screening hits")
    if guard is not None:
        return guard

    form = ScreeningHitDispositionForm(request.POST, tenant=request.tenant)
    if not form.is_valid():
        # Surfaced as messages rather than a re-rendered form: the picker lives inline on two
        # different pages, and a redirect back to the hit keeps both of them working.
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
        return redirect("procurement:screeninghit_detail", pk=pk)

    disposition = form.cleaned_data["disposition"]
    note = form.cleaned_data["disposition_note"]

    with transaction.atomic():
        obj = get_object_or_404(ScreeningHit.objects.select_for_update().select_related("screening"),
                                pk=pk, screening__tenant=request.tenant)
        if not obj.dispose(request.user, disposition, note):
            messages.error(
                request,
                f"This hit was already adjudicated as {obj.get_disposition_display().lower()} "
                f"and cannot be re-opened.")
            return redirect("procurement:screeninghit_detail", pk=pk)
        screening = obj.screening

    write_audit_log(request.user, obj, "update",
                    {"action": "dispose", "disposition": disposition, "note": note[:200]})
    # Recounted after the commit, so the counters reflect state that actually landed.
    screening.recount_hits()
    messages.success(
        request,
        f"Hit adjudicated as {obj.get_disposition_display().lower()}."
        + ("" if screening.has_open_hits else
           f" Every hit on {screening.number} is now dispositioned — it can be cleared."))
    return redirect("procurement:screeninghit_detail", pk=pk)
