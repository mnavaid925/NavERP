"""Procurement 6.17 Risk & Compliance Management — FraudAlert views.

Six routes: the register, one detail page, hand-raise/amend/delete, and the disposition verb.
The scan and the board live next door in ``FraudScan.py``, because they are pages about the
RULES rather than pages about one alert.

Discipline a reviewer will otherwise go looking for:

* **Every queryset is ``filter(tenant=request.tenant)``** — never ``.all()``. This model has its
  own tenant column, so every object is fetched ``get_object_or_404(..., tenant=request.tenant)``.
* **Ordinary CRUD is ``@login_required``; DELETE and the disposition verb add
  ``@tenant_admin_required``** (with ``@require_POST``, in that order, L27). Unlike the risk
  signal review verb next door, disposing of a fraud alert IS admin-gated: this register holds
  accusations about named people, and closing one is not daily analyst work.
* **The disposition verb runs the row under ``select_for_update()`` inside
  ``transaction.atomic()``**, so two admins clicking at once cannot both audit a state change.
* **``allowed_actions`` mirrors the decorators and the model guards exactly** — a hidden button
  and a refused POST always agree.
* **Nothing here writes to the spine** (L29). Substantiating an alert can LINK a block somebody
  already raised in the 6.4 register; it never raises, lifts or edits one, and it never touches
  a party, requisition, order or invoice.
* **Query shape.** The register select_relateds every hop a row or its ``__str__`` walks —
  ``vendor``, ``related_party``, ``assigned_to`` — so a page of 15 rows is not 46 queries. The
  detail page pulls all nine relations in one go, including the chained ``supplier_invoice``
  and ``approval__requisition`` hops the source list walks.

Context contracts pinned by ``.claude/tasks/contract-procurement-6.17.md`` §1:

``fraudalert_list``   → crud_list's ``object_list`` / ``page_obj`` / ``q``, plus
                        ``rule_choices``, ``status_choices``, ``severity_choices``, ``vendors``,
                        ``users``, ``stats``, ``is_admin``.
``fraudalert_detail`` → ``obj``, ``sources``, ``allowed_actions``, ``disposition_form``,
                        ``blocking_suspensions``, ``is_admin``.
"""
from django.db import transaction
from django.db.models import Count, Q
from django.urls import reverse

from apps.core.crud import _changed
from apps.core.models import Party
from apps.procurement.forms.RiskComplianceManagement.FraudAlerts import (
    DISPOSITION_ACTIONS, FraudAlertForm, FraudDispositionForm)
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.RiskComplianceManagement.FraudAlerts import (
    RULE_CHOICES, SEVERITY_CHOICES, STATUS_CHOICES, FraudAlert)
from apps.procurement.views._common import *  # noqa: F401,F403

TEMPLATE_LIST = "procurement/riskcompliance/fraudalert/list.html"
TEMPLATE_DETAIL = "procurement/riskcompliance/fraudalert/detail.html"
TEMPLATE_FORM = "procurement/riskcompliance/fraudalert/form.html"

#: Every hop a register row (or its own ``__str__``) walks. ``resolved_by`` is here and not only
#: on the detail set because ``fraudalert/list.html`` names the person who closed every TERMINAL
#: row — one extra query per such row otherwise, up to +15 on a settled register.
_ROW_RELATIONS = ("vendor", "related_party", "assigned_to", "resolved_by")

#: Every hop the detail page walks on top of the row set, chained ones included —
#: ``approval__requisition`` is what the source list needs to name the requisition a signature
#: belongs to without a second query.
_DETAIL_RELATIONS = _ROW_RELATIONS + (
    "requisition", "purchase_order", "supplier_invoice", "approval", "approval__requisition",
    "screening", "screening__party", "suspension", "suspension__supplier")


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
    return (f"{obj.number} has already been closed as "
            f"{obj.get_status_display().lower()} and cannot be {verb}. A disposed alert is the "
            f"record a decision rests on — raise a NEW alert if there is new evidence.")


def _alert_qs(request):
    return (FraudAlert.objects.filter(tenant=request.tenant)
            .select_related(*_ROW_RELATIONS))


def _suppliers(tenant):
    """The parties the register's vendor filter offers: this workspace's suppliers."""
    if tenant is None:
        return Party.objects.none()
    return (Party.objects.filter(tenant=tenant, roles__role__in=("supplier", "vendor"))
            .distinct().order_by("name"))


def _assignable_users(tenant):
    """The users the register's assignee filter offers."""
    from apps.accounts.models import User

    if tenant is None:
        return User.objects.none()
    return User.objects.filter(tenant=tenant).order_by("username")


def _stats(tenant):
    """The four register stat cards.

    Counted over the WHOLE workspace, not the filtered page: a stat card answers "how much fraud
    work is outstanding?", which must not change because somebody typed a search.

    ``confirmed`` is the CONTRACT's key name for the ``substantiated`` status count (contract §1
    pins ``stats.confirmed``). The status value stays ``substantiated`` — "confirmed" is what the
    card is labelled, and renaming the status to match would churn the model for a caption.
    """
    return FraudAlert.objects.filter(tenant=tenant).aggregate(
        open=Count("id", filter=Q(status="open")),
        investigating=Count("id", filter=Q(status="investigating")),
        confirmed=Count("id", filter=Q(status="substantiated")),
        high=Count("id", filter=Q(severity="high", status__in=FraudAlert.OPEN_STATUSES)),
    )


def _sources(obj):
    """Every document this alert points at, as the detail page renders them.

    ROW-DICT CONTRACT (L41 §1) — each entry carries EXACTLY::

        {"label": str,          # what this pointer is, e.g. "Supplier"
         "value": str,          # how to recognise the row, e.g. "SIV-00007"
         "url":   str | None}   # where to open it, or None when there is no page for it

    The template renders those three names and nothing else. A pointer that is NULL is simply
    absent from the list — the page says "no documents attached" rather than rendering a grid of
    em-dashes, which is what a mismatched row-dict key produces (200, and blank).
    """
    rows = []

    def add(label, value, url):
        if value:
            rows.append({"label": label, "value": str(value), "url": url})

    if obj.vendor_id:
        add("Supplier", obj.vendor.name,
            reverse("core:party_detail", args=[obj.vendor_id]))
    if obj.related_party_id:
        # Named for what it IS under each rule: the employee in an overlap, the second supplier
        # record in a duplicate pair. A generic "Related party" would hide the whole finding.
        label = ("Employee" if obj.rule == "vendor_employee_match"
                 else "Second supplier record" if obj.rule == "duplicate_vendor"
                 else "Related party")
        add(label, obj.related_party.name,
            reverse("core:party_detail", args=[obj.related_party_id]))
    if obj.requisition_id:
        add("Requisition", obj.requisition.number,
            reverse("scm:requisition_detail", args=[obj.requisition_id]))
    if obj.purchase_order_id:
        add("Purchase order", obj.purchase_order.number,
            reverse("scm:purchaseorder_detail", args=[obj.purchase_order_id]))
    if obj.supplier_invoice_id:
        add("Supplier invoice", obj.supplier_invoice.number,
            reverse("procurement:supplierinvoice_detail", args=[obj.supplier_invoice_id]))
    if obj.approval_id:
        # There is no per-signature detail page — a RequisitionApproval is a row on a
        # requisition's chain — so this lands on the signature register rather than 404ing a
        # made-up route.
        requisition = obj.approval.requisition
        add("Approval signature",
            f"{obj.approval.number} on {requisition.number}" if requisition
            else obj.approval.number,
            reverse("procurement:approval_history"))
    if obj.screening_id:
        add("Screening", obj.screening.number,
            reverse("procurement:screening_detail", args=[obj.screening_id]))
    if obj.suspension_id:
        add("Linked vendor block", obj.suspension.number,
            reverse("procurement:vsu_detail", args=[obj.suspension_id]))
    return rows


def _allowed_actions(obj, is_admin):
    """The disposition buttons this alert may actually be offered.

    ROW-DICT CONTRACT (L41 §1) — each entry carries EXACTLY::

        {"key": str,     # the POST's ``action`` value
         "label": str,   # the button caption
         "css": str,     # a btn-* class
         "icon": str,    # a lucide icon name
         "note_required": bool}

    All four post to the ONE ``fraudalert_disposition`` route, which re-validates the action
    against the same whitelist — so the page never offers a button that would 403 or be refused,
    and a direct POST is exactly as safe as a click.
    """
    if not (is_admin and obj.is_open):
        return []
    actions = []
    if obj.status == "open":
        actions.append({"key": "investigate", "label": "Take it on", "css": "btn-outline",
                        "icon": "search", "note_required": False})
    actions.append({"key": "substantiate", "label": "Substantiate", "css": "btn-danger",
                    "icon": "alert-octagon", "note_required": True})
    actions.append({"key": "unsubstantiate", "label": "False positive", "css": "btn-outline",
                    "icon": "x-circle", "note_required": True})
    actions.append({"key": "refer", "label": "Refer on", "css": "btn-outline",
                    "icon": "send", "note_required": True})
    return actions


def _blocking_suspensions(obj):
    """The 6.4 register row currently blocking this alert's supplier, as a list.

    Delegated whole to ``VendorSuspension.blocking_for`` so this page and the enforcement point
    can never disagree. A list because that is what the page renders, and because an alert with
    no supplier has nothing to look up.
    """
    if not (obj.tenant_id and obj.vendor_id):
        return []
    from apps.procurement.models.VendorManagement.VendorSuspensions import VendorSuspension

    blocking = VendorSuspension.blocking_for(obj.tenant, obj.vendor_id)
    return [blocking] if blocking is not None else []


# -- the register --------------------------------------------------------------------------------

@login_required
def fraudalert_list(request):
    """The fraud register — every alert in the workspace, newest fact first."""
    guard = _need_tenant(request, "review fraud alerts")
    if guard is not None:
        return guard
    return crud_list(
        request,
        _alert_qs(request),
        TEMPLATE_LIST,
        search_fields=["number", "detail", "matched_on", "vendor__name"],
        # (get_param, orm_lookup, is_int). The two int ones go through crud_list's as_db_int
        # guard, so ?vendor=abc / ?vendor=999999999999999999999 skip the filter instead of
        # 500ing; the three enum ones are validated against the model's own CHOICES before they
        # narrow, so a stale bookmark cannot silently empty the register (L11).
        filters=[("rule", "rule", False),
                 ("status", "status", False),
                 ("severity", "severity", False),
                 ("vendor", "vendor_id", True),
                 ("assigned_to", "assigned_to_id", True)],
        extra_context={
            "rule_choices": RULE_CHOICES,
            "status_choices": STATUS_CHOICES,
            "severity_choices": SEVERITY_CHOICES,
            "vendors": _suppliers(request.tenant),
            "users": _assignable_users(request.tenant),
            "stats": _stats(request.tenant),
            "is_admin": _is_admin(request),
        },
    )


@login_required
def fraudalert_detail(request, pk):
    """One alert: what the rule matched on, every document behind it, and what may be decided."""
    obj = get_object_or_404(FraudAlert.objects.select_related(*_DETAIL_RELATIONS),
                            pk=pk, tenant=request.tenant)
    is_admin = _is_admin(request)
    return render(request, TEMPLATE_DETAIL, {
        "obj": obj,
        "sources": _sources(obj),
        "allowed_actions": _allowed_actions(obj, is_admin),
        "disposition_form": FraudDispositionForm(tenant=request.tenant, alert=obj),
        "blocking_suspensions": _blocking_suspensions(obj),
        "is_admin": is_admin,
    })


# -- hand-raise / amend ----------------------------------------------------------------------------

def _alert_form(request, instance=None):
    """Raise or amend one alert by hand.

    Hand-rolled rather than ``crud_create`` / ``crud_edit`` because the model's ``save()`` has to
    run its ``dedupe_key`` derivation before the unique constraint sees it, and because the
    success redirect goes to the DETAIL page — an alert nobody reads is an alert nobody acts on.

    The context is exactly the ``crud_*`` contract — ``form`` + ``is_edit``, plus ``obj`` on the
    edit path only — so the one template behaves identically on both routes (L7).
    """
    is_edit = instance is not None

    if request.method == "POST":
        form = FraudAlertForm(request.POST, request.FILES, instance=instance,
                              tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "update" if is_edit else "create", _changed(form))
            messages.success(request, f"Fraud alert {obj.number} saved.")
            return redirect("procurement:fraudalert_detail", pk=obj.pk)
    else:
        form = FraudAlertForm(instance=instance, tenant=request.tenant)

    ctx = {"form": form, "is_edit": is_edit}
    if is_edit:
        ctx["obj"] = instance
    return render(request, TEMPLATE_FORM, ctx)


@login_required
def fraudalert_create(request):
    """Raise an alert by hand — for what no rule can see."""
    guard = _need_tenant(request, "raise fraud alerts")
    if guard is not None:
        return guard
    return _alert_form(request)


@login_required
def fraudalert_edit(request, pk):
    """Amend an alert — refused once it has been disposed of.

    Editing the evidence behind a recorded disposition would rewrite the basis that disposition
    rests on. If there is new evidence, the honest move is a new alert.
    """
    obj = get_object_or_404(FraudAlert, pk=pk, tenant=request.tenant)
    if obj.is_terminal:
        messages.error(request, _refuse_terminal(obj, "edited"))
        return redirect("procurement:fraudalert_detail", pk=pk)
    return _alert_form(request, instance=obj)


@login_required
@tenant_admin_required
@require_POST
def fraudalert_delete(request, pk):
    """Admin-gated: deleting an alert erases an accusation and the reasoning behind it.

    A DISPOSED alert cannot be deleted at all, by anybody. That is the point of a disposition:
    the record that somebody looked and decided has to outlive the person who would rather it
    did not. A re-scan would in any case re-raise a deleted OPEN alert on the next pass — the
    dedupe key is deterministic — which is why deletion is for mistakes, not for disagreement.
    """
    obj = get_object_or_404(FraudAlert, pk=pk, tenant=request.tenant)
    if obj.is_terminal:
        messages.error(request, _refuse_terminal(obj, "deleted"))
        return redirect("procurement:fraudalert_detail", pk=pk)
    return crud_delete(request, model=FraudAlert, pk=pk,
                       success_url="procurement:fraudalert_list")


# -- the disposition verb -------------------------------------------------------------------------

@login_required
@tenant_admin_required
@require_POST
def fraudalert_disposition(request, pk):
    """Investigate, substantiate, unsubstantiate or refer one alert.

    Admin-gated, unlike the risk-signal review verb next door: this register holds accusations
    about named people, and closing one is a decision with consequences rather than daily
    analyst triage. The row is locked for the call so two admins cannot both stamp a decision on
    it, and each model verb re-checks its own guard, which is what makes a direct POST exactly as
    safe as a click.

    Substantiating can LINK a block somebody already raised in the 6.4 register. It never raises
    one — parking a question and stopping a supplier trading are different decisions, made by
    different people, and this view only records that the second one happened.
    """
    guard = _need_tenant(request, "dispose of fraud alerts")
    if guard is not None:
        return guard

    alert = get_object_or_404(FraudAlert, pk=pk, tenant=request.tenant)
    form = FraudDispositionForm(request.POST, tenant=request.tenant, alert=alert)
    if not form.is_valid():
        # L11: the action and the note arrive from a POST body. Every failure here is reported
        # and ignored, never raised — an unknown action, a missing note, a block against another
        # supplier. The first error is the one shown, because a redirect carries no form state.
        for field_errors in form.errors.values():
            messages.error(request, field_errors[0])
            break
        return redirect("procurement:fraudalert_detail", pk=pk)

    action = form.cleaned_data["action"]
    note = form.cleaned_data.get("resolution_note") or ""
    suspension = form.cleaned_data.get("suspension")
    verb_name, _note_required = DISPOSITION_ACTIONS[action]

    with transaction.atomic():
        obj = get_object_or_404(FraudAlert.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        verb = getattr(obj, verb_name)
        moved = (verb(request.user, note, suspension=suspension) if action == "substantiate"
                 else verb(request.user, note))
        if not moved:
            messages.error(
                request,
                f"{obj.number} cannot be {action}d from {obj.get_status_display().lower()}.")
            return redirect("procurement:fraudalert_detail", pk=pk)

    # The note is TRUNCATED into the audit log rather than copied whole: an audit entry is an
    # index of what happened, and the full reasoning lives on the alert itself.
    write_audit_log(request.user, obj, "update",
                    {"action": action, "resolution_note": note[:200]})
    messages.success(request, f"{obj.number} marked {obj.get_status_display().lower()}.")
    return redirect("procurement:fraudalert_detail", pk=pk)
