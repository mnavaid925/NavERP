"""SCM 4.12 Contract & Compliance Management — the obligation register and its proof history.

This is 4.12's daily-driver screen: the queue of what this workspace still owes proof of. Everything
else in the sub-module describes a document or a licence; this describes a *duty*, and the whole
point of the page is that a duty coming due is visible before an auditor finds it.

--------------------------------------------------------------------------------------------------
WHAT THIS MODULE DELIBERATELY DOES NOT CONTAIN
--------------------------------------------------------------------------------------------------
**The state machine.** ``refresh_status`` (date-driven) and ``record_check`` (evidence-driven) are
methods on :class:`~apps.scm.models.ComplianceRequirement`. The views below lock the row, call the
method, and audit the diff. Not one of them re-implements "does a pass advance the due date?" — a
second copy of that living in a view is how the button, the seeder and the tests start disagreeing.

**A stored compliance rate.** ``compliance_rate`` is a property computed from the child rows on
read. It returns ``None`` — never ``0`` — when there is nothing to divide by, so a requirement that
has never been checked renders "—" rather than a confident red 0%. Templates must render the
``None`` case as an em dash and NOT as a zero.

--------------------------------------------------------------------------------------------------
WHY THE LIST ROLLS STATUSES ON A GET
--------------------------------------------------------------------------------------------------
``status`` is a stored column but ``overdue`` is a fact about a date, so somewhere the two have to
catch up. :func:`_roll_requirement_statuses` does it here, for the rows that actually crossed a
boundary, in ONE ``bulk_update`` — never a ``save()`` per row on an unpaginated scan (the
``_roll_contract_statuses`` precedent, and precisely the shape ``refresh_status(save=False)`` exists
to serve). It only ever moves rows inside ``AUTO_STATUSES``; ``compliant`` / ``non_compliant`` /
``not_applicable`` / ``retired`` are human decisions and a clock must not walk them back.

--------------------------------------------------------------------------------------------------
Context-var contract (pinned, L7 — the templates are written by a separate agent, so EVERY key each
template consumes is listed here, not merely the list variable):
--------------------------------------------------------------------------------------------------
* ``scm/compliance/compliancerequirement/list.html`` — ``object_list`` + ``page_obj`` + ``q`` (from
  ``crud_list``) plus ``status_choices``, ``framework_choices``, ``source_choices``,
  ``criticality_choices``, ``due_choices``, ``owners`` (a User queryset for the owner select),
  ``due`` (the RESOLVED due-filter value, so the select shows the view that actually rendered),
  ``overdue_count`` and ``due_soon_count`` (the two header chips).
* ``scm/compliance/compliancerequirement/detail.html`` — ``obj``, ``checks`` (the proof timeline,
  newest first), ``check_form`` (the inline "Record check" form).
* ``scm/compliance/compliancerequirement/form.html`` — ``form`` + ``is_edit`` (+ ``obj`` on edit).
* ``scm/compliance/compliancecheck/form.html`` — ``form``, ``is_edit`` (always ``True`` — a check is
  only ever created inline from the requirement's page), ``obj`` (the check) and ``requirement``
  (its parent, for the breadcrumb and the cancel link).

Badge colours come from the models' own ``status_css`` / ``criticality_css`` / ``result_css``
properties — ``badge-green / badge-red / badge-amber / badge-info / badge-muted / badge-slate`` are
the only classes ``theme.css`` ships (L33).
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import ProtectedError

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._common import _changed
from apps.scm.forms import ComplianceCheckForm, ComplianceRequirementForm
from apps.scm.models import ComplianceCheck, ComplianceRequirement

User = get_user_model()

#: Every FK the LIST renders. ``scope_label`` walks whichever pointer the row's scope names, so all
#: four scope FKs are joined or a page of 15 rows is up to 15 extra queries for a single column.
#: ``contract`` / ``license`` are joined for the "source" column, ``owner`` for the owner column.
#: None of the seven ``__str__`` methods walks a SECOND FK (checked: OrgUnit -> name, Party -> name,
#: Location -> "code · name", Item -> "sku · name", SupplierContract/TradeLicense -> "number ·
#: title", User -> its own columns), so nothing deeper is owed.
_REQUIREMENT_SELECT = ("owner", "party", "org_unit", "location", "item", "contract", "license")

#: The one extra join only the detail page reads — a list row never renders the standing document.
_REQUIREMENT_DETAIL_SELECT = _REQUIREMENT_SELECT + ("document",)

#: What the ``due`` filter offers. Not a model vocabulary: these are three *views* of the queue, so
#: they are declared here and handed to the template rather than hard-coded into the select.
DUE_CHOICES = [
    ("overdue", "Overdue"),
    ("due_soon", "Due soon"),
    ("open", "Open — still owed"),
]

#: How many distinct notice windows the due-soon condition will expand into (see
#: :func:`_due_soon_q`). ``notice_days`` is a per-row column, and no portable ORM expression adds an
#: integer column of days to a date, so the condition is an OR over the windows the tenant actually
#: uses — realistically two or three ("90/60/30" is the whole convention). The cap bounds the SQL
#: for a pathological workspace; past it the condition WIDENS to the largest window seen, which
#: over-counts visibly rather than hiding rows silently (fail open — the 4.11 impact-floor posture).
_MAX_NOTICE_WINDOWS = 64


# =================================================================================================
# Shared helpers — every one of these is written from the same conditions as the model property it
# mirrors. The 4.10 rule: when a property and a queryset describe the same thing, they must be one
# statement of the rule, or the badge and the count disagree on the same screen.
# =================================================================================================
def _overdue_q(today):
    """Q for ``is_overdue`` — a due date strictly in the past. ``None`` never matches."""
    return Q(next_due_date__lt=today)


def _due_soon_q(tenant, today):
    """Q for ``is_due_soon`` — inside the row's OWN notice window and not yet past it.

    ``is_due_soon`` is ``0 <= days_to_due <= notice_days``, and ``notice_days`` is a column. Django
    cannot add an integer column of days to a date portably (``F("notice_days") * timedelta`` is not
    a legal duration expression on MySQL), so this expands into one ``(notice_days=N, next_due_date
    <= today + N)`` clause per window the tenant actually uses — read in ONE small grouped query.

    Returns a never-matching Q when the tenant has no future-dated rows at all, rather than an empty
    ``Q()``, which would match EVERYTHING and turn an empty chip into the whole register.
    """
    if tenant is None:
        return Q(pk__in=())
    windows = sorted(set(
        ComplianceRequirement.objects
        .filter(tenant=tenant, next_due_date__gte=today)
        .order_by()
        .values_list("notice_days", flat=True)
        .distinct()[:_MAX_NOTICE_WINDOWS]
    ))
    if not windows:
        return Q(pk__in=())
    if len(windows) >= _MAX_NOTICE_WINDOWS:
        # Degraded, and deliberately in the OVER-counting direction: one window at the widest value
        # seen. A chip that says "more than it should" is a visible discrepancy somebody can chase;
        # one that quietly drops rows is the failure this whole register exists to prevent.
        return Q(next_due_date__gte=today,
                 next_due_date__lte=today + timedelta(days=max(windows)))
    condition = Q()
    for days in windows:
        condition |= Q(notice_days=days,
                       next_due_date__gte=today,
                       next_due_date__lte=today + timedelta(days=days))
    return condition


def _open_q():
    """Q for "still owes us something" — read from the model's own ``OPEN_STATUSES``.

    Declared once ON THE MODEL so the list filter, the header chips and the seeder guard cannot
    encode different subsets of it (the 4.10 finding where a bench filter encoded two of three
    shapes and the count on the page disagreed with the rows under it).
    """
    return Q(status__in=ComplianceRequirement.OPEN_STATUSES)


def _owner_qs(tenant):
    """The tenant's logins, for the owner FILTER — ``.none()`` when there is no tenant.

    Deliberately WIDER than the form's owner dropdown, which drops deactivated logins: you cannot
    make somebody who has left answerable for a new obligation, but "what was still owned by them
    when they left" is exactly the question this filter answers. Ordered by ``email`` to match the
    4.11 assignee filter, so the two selects list people in the same order.
    """
    if tenant is None:
        return User.objects.none()
    return User.objects.filter(tenant=tenant).order_by("email")


def _roll_requirement_statuses(request, today):
    """Catch the stored ``status`` up with the calendar — in ONE bulk write.

    Only rows already inside ``AUTO_STATUSES`` are even read, and only those that actually crossed a
    boundary are written, so the cost is bounded by the rows that changed rather than by the
    tenant's whole register. ``refresh_status(save=False)`` exists for precisely this call site.

    ``updated_at`` is assigned by hand: ``bulk_update`` builds a ``CASE`` out of the in-memory
    attribute values and never calls ``pre_save``, so an ``auto_now`` column would otherwise be
    written back with its stale value (Django 5.1, ``db/models/query.py:912-916``).

    A GET that mutates is unusual, and it is the pragmatic trigger the 4.2 contract list already
    uses: a date-derived status has to catch up somewhere, and a page load is where somebody is
    looking. Nothing outside this table is written.
    """
    if request.tenant is None:
        return
    changed = []
    stamp = timezone.now()
    for requirement in (ComplianceRequirement.objects
                        .filter(tenant=request.tenant,
                                status__in=ComplianceRequirement.AUTO_STATUSES)
                        .only("id", "status", "next_due_date", "updated_at")):
        before = requirement.status
        requirement.refresh_status(today=today, save=False)
        if requirement.status != before:
            requirement.updated_at = stamp
            changed.append(requirement)
    if changed:
        with transaction.atomic():
            ComplianceRequirement.objects.bulk_update(changed, ["status", "updated_at"])


def _form_errors(form):
    """Flatten a small inline form's errors into one message line (the 4.10 action-view shape)."""
    return "; ".join(" ".join(errors) for errors in form.errors.values())


# =================================================================================================
# ComplianceRequirement — CRUD
# =================================================================================================
@login_required
def compliancerequirement_list(request):
    """The due queue: search, six filters, two header chips.

    EVERY filter is applied BEFORE ``crud_list`` paginates. A filter applied afterwards would page
    over the unfiltered set and quietly show the wrong rows on page 2.
    """
    today = timezone.localdate()
    # Catch the stored status up with the calendar first, so the badge a row renders and the bucket
    # this page just put it in cannot disagree by one page load.
    _roll_requirement_statuses(request, today)

    queryset = (ComplianceRequirement.objects.filter(tenant=request.tenant)
                .select_related(*_REQUIREMENT_SELECT))

    # --- the one filter crud_list's equality spec cannot express -----------------------------------
    # All three buckets are ANDed with "still open": a retired or not-applicable row with a stale
    # date owes nothing, and counting it as overdue is the noise that makes a queue unopenable. The
    # two chips below are built from the SAME Qs, so the chip and the page it links to agree.
    overdue_condition = _overdue_q(today) & _open_q()
    due_soon_condition = _due_soon_q(request.tenant, today) & _open_q()
    due = (request.GET.get("due") or "").strip()
    if due == "overdue":
        queryset = queryset.filter(overdue_condition)
    elif due == "due_soon":
        queryset = queryset.filter(due_soon_condition)
    elif due == "open":
        queryset = queryset.filter(_open_q())
    else:
        # Absent, or hand-edited junk: no narrowing, and the select is told so. The crud_list posture
        # on a bad filter — skip it, never 500, and never silently show nothing.
        due = ""

    # ONE aggregate for the whole header strip — two conditional counts in a single query rather
    # than two round trips. Computed over the UNFILTERED tenant set on purpose: these chips say what
    # the workspace owes, not what the current filter narrowed it to.
    chips = (ComplianceRequirement.objects.filter(tenant=request.tenant)
             .aggregate(overdue=Count("id", filter=overdue_condition),
                        due_soon=Count("id", filter=due_soon_condition)))

    return crud_list(
        request, queryset, "scm/compliance/compliancerequirement/list.html",
        search_fields=["number", "title", "source_reference"],
        filters=[("status", "status", False),
                 ("framework", "framework", False),
                 ("source", "source", False),
                 ("criticality", "criticality", False),
                 # is_int=True: `crud_list` applies the L11 guard (non-decimal, Unicode superscript
                 # or over-range values SKIP the filter instead of raising out of .filter()).
                 ("owner", "owner_id", True)],
        extra_context={
            "status_choices": ComplianceRequirement.STATUS_CHOICES,
            "framework_choices": ComplianceRequirement.FRAMEWORK_CHOICES,
            "source_choices": ComplianceRequirement.SOURCE_CHOICES,
            "criticality_choices": ComplianceRequirement.CRITICALITY_CHOICES,
            "due_choices": DUE_CHOICES,
            "owners": _owner_qs(request.tenant),
            "due": due,
            "overdue_count": chips["overdue"] or 0,
            "due_soon_count": chips["due_soon"] or 0,
        },
    )


@login_required
def compliancerequirement_create(request):
    """``crud_create`` stamps the tenant, audits, and refuses a tenant-less user outright.

    The FORM stamps the tenant onto the unsaved instance as well — that is not redundancy for its
    own sake, it is what makes ``ComplianceRequirement.clean()``'s cross-tenant FK guard run on the
    create path (``crud_create`` assigns the tenant only after ``is_valid()``).
    """
    return crud_create(request, form_class=ComplianceRequirementForm,
                       template="scm/compliance/compliancerequirement/form.html",
                       success_url="scm:compliancerequirement_list")


@login_required
def compliancerequirement_edit(request, pk):
    """Editable at any time, including once retired.

    An obligation is a description of a duty, and duties are re-scoped, re-owned and re-cited. No
    status gate: the row worth editing most is often the one somebody got wrong. The proof history
    is untouched by an edit — ``ComplianceCheck.due_date`` snapshots the cycle each check answered,
    so re-scheduling the requirement never rewrites what a PAST cycle was due.
    """
    return crud_edit(request, model=ComplianceRequirement, pk=pk,
                     form_class=ComplianceRequirementForm,
                     template="scm/compliance/compliancerequirement/form.html",
                     success_url="scm:compliancerequirement_list")


@login_required
def compliancerequirement_detail(request, pk):
    """One obligation, where it stands, and every cycle ever performed against it."""
    obj = get_object_or_404(
        ComplianceRequirement.objects.select_related(*_REQUIREMENT_DETAIL_SELECT),
        pk=pk, tenant=request.tenant)
    # One row, and only when it actually crossed a boundary — the single-row twin of the list roll,
    # so opening a requirement directly from a bookmark shows the same standing the queue does.
    obj.refresh_status()

    # The proof timeline. Meta ordering is newest-first, which is what a history panel reads.
    # `evidence` and `performed_by` are joined because every row renders both.
    checks = list(obj.checks.select_related("performed_by", "evidence"))

    return render(request, "scm/compliance/compliancerequirement/detail.html", {
        "obj": obj,
        "checks": checks,
        # `requirement=obj` is what lets ComplianceCheck.clean() validate the evidence document
        # against THIS obligation's tenant while the form is still being validated.
        "check_form": ComplianceCheckForm(tenant=request.tenant, requirement=obj),
    })


@tenant_admin_required
@require_POST
def compliancerequirement_delete(request, pk):
    """Delete the obligation — and say what goes with it.

    ``ComplianceCheck.requirement`` is ``CASCADE``, so the proof history goes too. That is the right
    cascade (a check's meaning is its requirement's) but it is a larger consequence than "Deleted
    successfully." admits: those rows ARE the defensible documentation, and they cannot be
    re-derived from anything. **Tenant-admin gated for that reason** — and because a non-applicable
    obligation is meant to be kept WITH ITS REASON rather than deleted, which is why the model has a
    ``not_applicable`` status and a mandatory reason at all.

    The ``ProtectedError`` catch is the generic §7.4 guard, not an enumeration: nothing PROTECTs
    this table today, but 4.12's own later passes and Modules 5/9 are declared FK extenders of it,
    and an enumeration would go stale silently — as a 500 on a mainline delete. ``atomic()`` so the
    audit row ``crud_delete`` writes before deleting rolls back with the failed delete.
    """
    obj = get_object_or_404(ComplianceRequirement.objects.only("pk", "number"),
                            pk=pk, tenant=request.tenant)
    proof_rows = ComplianceCheck.objects.filter(requirement=obj).count()
    try:
        with transaction.atomic():
            response = crud_delete(request, model=ComplianceRequirement, pk=pk,
                                   success_url="scm:compliancerequirement_list")
    except ProtectedError as exc:
        blockers = sorted({protected._meta.verbose_name for protected in exc.protected_objects})
        messages.error(
            request,
            f"{obj.number} is still referenced by {', '.join(blockers)} and cannot be deleted — "
            "retire it instead, or mark it not applicable with a reason, so the record of the "
            "decision survives.")
        return redirect("scm:compliancerequirement_detail", pk=pk)
    if proof_rows:
        messages.info(request, f"{proof_rows} recorded check(s) were removed with {obj.number} — "
                               "that proof history cannot be reconstructed.")
    return response


# =================================================================================================
# The proof history.
#
# Lock, apply, audit — the 4.11 action shape. The state rules (what a pass/fail/partial does to the
# standing, how far a pass advances the due date, why `not_applicable` changes nothing) all live in
# ``ComplianceRequirement.record_check`` and are not repeated here.
# =================================================================================================

#: The three columns ``record_check`` may write. Captured before and compared after, so the audit
#: trail records the PROJECTION as a ``{field: [before, after]}`` diff rather than just "a check was
#: added" — "why did this go compliant and jump a quarter?" has to be answerable from the log.
_PROJECTED_FIELDS = ("status", "last_checked_on", "next_due_date")


@login_required
@require_POST
def compliancerequirement_record_check(request, pk):
    """Append one performed proof cycle and fold it into the obligation's standing.

    Not admin-gated, deliberately: recording that you did the thing you were supposed to do is the
    daily work of whoever owns the obligation, and putting it behind a workspace administrator is
    how a register stops being kept at all. Editing and deleting a recorded check are the gated
    acts — see below.

    ``select_for_update`` matters even though ``record_check`` is idempotent against what it reads:
    it is idempotent against **what it reads**, so two people recording a pass at once would both
    see the same ``next_due_date`` and the second would advance from a stale anchor. Re-reading
    inside the lock makes the loser advance from the winner's result (the 4.10 pattern).

    ``due_date`` defaults to the parent's ``next_due_date`` — the cycle this check answers, frozen
    as it stood — but only when the form left it blank, so a back-filled proof can still say which
    cycle it belongs to.

    **The audit row is written unconditionally**, unlike a pure verb action: a child row was
    created, and creating the defensible record of a proof cycle is never a no-op. An EMPTY
    projection diff is information rather than an error — a ``not_applicable`` result is evidence of
    neither compliance nor breach, so it deliberately changes nothing — and it is messaged at info
    level with the diff simply absent from the log entry.
    """
    parent = get_object_or_404(ComplianceRequirement, pk=pk, tenant=request.tenant)
    form = ComplianceCheckForm(request.POST, tenant=request.tenant, requirement=parent)
    if not form.is_valid():
        messages.error(request, _form_errors(form)
                       or "Couldn't record the check — check the fields and try again.")
        return redirect("scm:compliancerequirement_detail", pk=pk)

    with transaction.atomic():
        obj = get_object_or_404(ComplianceRequirement.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        before = {field: getattr(obj, field) for field in _PROJECTED_FIELDS}

        check = form.save(commit=False)
        # Re-point at the LOCKED row, not the one read above: they are the same record, but the
        # child must hang off the instance whose columns record_check is about to write.
        check.requirement = obj
        # Stamped, never typed — "who did it" is an audit fact, not an input (L22).
        check.performed_by = request.user
        if check.due_date is None:
            check.due_date = obj.next_due_date
        check.save()
        obj.record_check(check)

    changes = {field: [str(before[field]), str(getattr(obj, field))]
               for field in _PROJECTED_FIELDS if before[field] != getattr(obj, field)}
    write_audit_log(request.user, obj, "update", {
        "action": "record_check",
        "check_id": check.pk,
        "result": check.result,
        "due_date": str(check.due_date) if check.due_date else "",
        **changes,
    })

    if changes:
        messages.success(
            request,
            f"Recorded “{check.get_result_display()}” on {obj.number} — it is now "
            f"{obj.get_status_display().lower()}"
            + (f" and next due {obj.next_due_date:%b %d, %Y}." if obj.next_due_date
               else ", with no further cycle scheduled."))
    else:
        messages.info(request, f"Recorded “{check.get_result_display()}” on {obj.number}. A "
                               "not-applicable cycle is evidence of neither compliance nor breach, "
                               "so the obligation's standing and due date are unchanged and it is "
                               "left out of the compliance rate.")
    return redirect("scm:compliancerequirement_detail", pk=pk)


@tenant_admin_required
def compliancecheck_edit(request, pk):
    """Correct a recorded check.

    **Resolved through ``requirement__tenant`` and nothing else.** ``ComplianceCheck`` carries no
    ``tenant`` column of its own (it is a pure child, the ``TrackingEvent`` / ``InspectionResult``
    precedent), so a bare ``pk`` lookup here would be a cross-tenant read. ``request.tenant`` of
    ``None`` resolves to ``requirement__tenant IS NULL``, and that column is NOT NULL, so a
    tenant-less user gets a 404 rather than somebody else's proof record.

    Hand-rolled rather than ``crud_edit``, which filters ``tenant=request.tenant`` on the model
    itself and would raise ``FieldError`` on a model that has no such column. Hand-rolled means this
    path owes its own ``write_audit_log`` — ``crud_*`` writes one for you.

    **Tenant-admin gated.** Recording a check is open to anyone; rewriting one after the fact is
    not. This row IS the evidence, and a proof history anybody can quietly restate is not defensible
    documentation.

    **The parent is deliberately NOT re-projected.** Re-running ``record_check`` on an edit would
    advance ``next_due_date`` a SECOND time for a cycle that already advanced it, silently pushing
    the obligation a full period into the future. ``compliance_rate`` is derived on read and updates
    itself; the standing is corrected on the requirement's own edit screen, and the message says so.
    """
    obj = get_object_or_404(
        ComplianceCheck.objects.select_related("requirement", "performed_by", "evidence"),
        pk=pk, requirement__tenant=request.tenant)

    if request.method == "POST":
        form = ComplianceCheckForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            check = form.save()
            write_audit_log(request.user, check, "update", _changed(form))
            messages.success(request, "Check updated.")
            if "result" in form.changed_data:
                messages.info(request, "The obligation's status and next due date were NOT "
                                       "re-derived — re-running the projection would advance the "
                                       "due date a second time for a cycle that already advanced "
                                       "it. Adjust them on the requirement if they need to change.")
            return redirect("scm:compliancerequirement_detail", pk=obj.requirement_id)
    else:
        form = ComplianceCheckForm(instance=obj, tenant=request.tenant)

    return render(request, "scm/compliance/compliancecheck/form.html", {
        "form": form,
        # Always True: a check is only ever CREATED inline from its requirement's page, so this
        # template exists solely to correct one that is already there.
        "is_edit": True,
        "obj": obj,
        "requirement": obj.requirement,
    })


@tenant_admin_required
@require_POST
def compliancecheck_delete(request, pk):
    """Remove a recorded check.

    Same ``requirement__tenant`` resolution as the edit, and the same reason it is admin-gated:
    deleting a proof cycle deletes evidence. It also silently improves ``compliance_rate``, which is
    derived from these rows — a failure removed is a failure that never happened, as far as the page
    is concerned.

    Hand-rolled for the same reason as the edit: ``crud_delete`` filters ``tenant=`` on the model,
    which this child has not got. The audit row is therefore written here, BEFORE the delete, while
    the row still exists to be described.

    A passed check that advanced ``next_due_date`` is NOT walked back — the schedule is corrected on
    the requirement itself. Rewinding it here would guess at which of several passes was the one
    that moved it.
    """
    obj = get_object_or_404(ComplianceCheck.objects.select_related("requirement"),
                            pk=pk, requirement__tenant=request.tenant)
    requirement_pk = obj.requirement_id
    advanced = obj.result == "pass"
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Check deleted.")
    if advanced:
        messages.info(request, "That was a passed cycle, so it is what advanced the obligation's "
                               "due date. The due date was left where it is — correct it on the "
                               "requirement if the cycle should be owed again.")
    return redirect("scm:compliancerequirement_detail", pk=requirement_pk)
