"""Procurement 6.1 User Dashboard & Portal — ProcurementAlert views.

Full CRUD (the inbox is hand-raisable until 6.3's engine starts raising alerts itself) plus the
two lifecycle actions — Acknowledge and Resolve — which are the only writers of ``status``. The
status column is deliberately OFF the form: a row cannot be edited into "resolved", it must be
resolved through the action that stamps who/when (the scm requisition rule).
"""
from django.db.models import Case, IntegerField, Value, When

from apps.procurement.forms import ProcurementAlertForm
from apps.procurement.models import ProcurementAlert
from apps.procurement.views._common import *  # noqa: F401,F403
from apps.procurement.views._common import login_required, render  # explicit names for flake8


@login_required
def alert_list(request):
    """The Task & Alert Center.

    Open rows float to the top regardless of age (an old open alert outranks a fresh resolved
    one), then most recently raised wins inside a band. Filters: q over title/message,
    status / kind / severity from the model's own choices, assignee as an int-guarded pk
    dropdown (L11 via crud_list's ``as_db_int``).
    """
    # Rank bands: open=0, acknowledged=1, resolved=2. A Case expression rather than Meta.ordering
    # so the default "-raised_at" ordering stays untouched for every other consumer.
    open_first = Case(
        When(status="open", then=Value(0)),
        When(status="acknowledged", then=Value(1)),
        default=Value(2),
        output_field=IntegerField(),
    )
    qs = (ProcurementAlert.objects.filter(tenant=request.tenant)
          .select_related("assigned_to")
          .annotate(_open_rank=open_first)
          .order_by("_open_rank", "-raised_at"))
    return crud_list(
        request, qs, "procurement/dashboardportal/alerts/list.html",
        search_fields=["title", "message"],
        filters=[("status", "status", False), ("kind", "kind", False),
                 ("severity", "severity", False), ("assigned_to", "assigned_to_id", True)],
        extra_context={
            "status_choices": ProcurementAlert.STATUS_CHOICES,
            "kind_choices": ProcurementAlert.KIND_CHOICES,
            "severity_choices": ProcurementAlert.SEVERITY_CHOICES,
            # A dropdown of PEOPLE is a page of rows too — print full names, not bare usernames.
            "assignees": _assignees(request.tenant),
            "open_count": ProcurementAlert.objects.filter(
                tenant=request.tenant, status__in=ProcurementAlert.OPEN_STATUSES).count(),
        },
    )


def _assignees(tenant):
    """The workspace members an alert may be assigned to, ordered for human scanning."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    if tenant is None:
        return User.objects.none()
    return (User.objects.filter(tenant=tenant, is_active=True)
            .order_by("first_name", "last_name", "username"))


@login_required
def alert_detail(request, pk):
    obj = get_object_or_404(
        ProcurementAlert.objects.select_related("assigned_to", "created_by",
                                                "acknowledged_by", "resolved_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "procurement/dashboardportal/alerts/detail.html", {"obj": obj})


@login_required
def alert_create(request):
    """Hand-raise an alert. Thin wrapper around crud_create so ``created_by`` gets stamped —
    the generic helper saves without knowing about this module's authorship audit."""
    if request.method == "POST":
        form = ProcurementAlertForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            # Same guard as crud_create: a tenant-less user (superuser) must not create orphans.
            if request.tenant is None:
                messages.error(request, "Select a tenant workspace before raising alerts.")
                return redirect("dashboard:home")
            obj.tenant = request.tenant
            obj.created_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Alert raised.")
            return redirect("procurement:alert_detail", pk=obj.pk)
    else:
        form = ProcurementAlertForm(tenant=request.tenant)
    return render(request, "procurement/dashboardportal/alerts/form.html",
                  {"form": form, "is_edit": False})


@login_required
def alert_edit(request, pk):
    return crud_edit(
        request, model=ProcurementAlert, pk=pk, form_class=ProcurementAlertForm,
        template="procurement/dashboardportal/alerts/form.html",
        success_url="procurement:alert_list",
    )


@login_required
@require_POST
def alert_delete(request, pk):
    return crud_delete(request, model=ProcurementAlert, pk=pk,
                       success_url="procurement:alert_list")


# -- lifecycle actions ------------------------------------------------------------------------

@login_required
@require_POST
def alert_acknowledge(request, pk):
    """Mark seen. Idempotent by construction: acknowledge() is a no-op off ``open``."""
    obj = get_object_or_404(ProcurementAlert, pk=pk, tenant=request.tenant)
    if obj.acknowledge(request.user):
        write_audit_log(request.user, obj, "update", changes={"status": "acknowledged"})
        messages.success(request, f"Acknowledged “{obj.title}”.")
    else:
        messages.info(request, "That alert was already acknowledged or resolved.")
    return redirect("procurement:alert_detail", pk=obj.pk)


@login_required
@require_POST
def alert_resolve(request, pk):
    """Close out with an optional note. Allowed straight from ``open`` — resolving without first
    acknowledging is a normal fast path, not a policy violation."""
    obj = get_object_or_404(ProcurementAlert, pk=pk, tenant=request.tenant)
    note = (request.POST.get("resolution_note") or "").strip()
    # Only a transition writes history — re-resolving must not re-stamp who/when (CR-2).
    if obj.resolve(request.user, note=note):
        changes = {"status": "resolved"}
        if note:
            changes["resolution_note"] = note[:200]
        write_audit_log(request.user, obj, "update", changes=changes)
        messages.success(request, f"Resolved “{obj.title}”.")
    else:
        messages.info(request, "That alert was already resolved.")
    return redirect("procurement:alert_detail", pk=obj.pk)
