"""Procurement 6.1 User Dashboard & Portal — the personalized overview (module landing page).

**Personalized Overview** bullet: widgets over pending tasks, pending approvals and spend
summaries. Every figure is an aggregate at render time over the documents the module already owns
or points at (``scm.PurchaseRequisition`` / ``scm.PurchaseOrder`` per L36, this app's alerts) —
nothing here stores a number.

"Customizable" is real: which widget sections render is stored per user in
``WidgetPreference`` (absence of a row = visible), toggled from this very page via POST.
"""
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import F, Sum
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.procurement.forms import WidgetToggleForm
from apps.procurement.models import ProcurementAlert, WidgetPreference
from apps.procurement.views._helpers import procurement_activity_qs
from apps.scm.models import PurchaseOrder, PurchaseRequisition

#: How far ahead "approaching" reaches for requisition need-by dates on the deadlines widget.
DEADLINE_WINDOW_DAYS = 14


@login_required
def dashboard(request):
    tenant = request.tenant

    # Computed once for both consumers below (the form's initial state and the widgets mapping) —
    # safe before the POST guard: hidden_keys() answers an empty set for a tenant-less superuser.
    hidden = WidgetPreference.hidden_keys(tenant, request.user)

    if request.method == "POST":
        # Widget customization posts back to THIS page — no separate settings route to get lost.
        if tenant is None:
            messages.error(request, "Select a tenant workspace before personalizing widgets.")
            return redirect("dashboard:home")
        form = WidgetToggleForm(request.POST)
        if form.is_valid():
            WidgetPreference.save_choices(tenant, request.user,
                                          set(form.cleaned_data["widgets"]))
            messages.success(request, "Your overview layout has been saved.")
            return redirect("procurement:dashboard")
        # An invalid toggle POST falls through to the GET render below with the form's errors;
        # unreachable in practice because the choices are server-generated checkboxes.
    else:
        form = WidgetToggleForm(
            initial_visible=[k for k in WidgetPreference.WIDGETS if k not in hidden])

    widgets = [{"key": key, "label": label, "visible": key not in hidden}
               for key, label in WidgetPreference.WIDGETS.items()]

    me = request.user
    today = timezone.localdate()
    month_start = today.replace(day=1)
    prev_month_start = (month_start - timedelta(days=1)).replace(day=1)
    window_end = today + timedelta(days=DEADLINE_WINDOW_DAYS)

    # -- alerts (this module's own table) ------------------------------------------------------
    alerts = ProcurementAlert.objects.filter(tenant=tenant)
    open_alerts = alerts.filter(status__in=ProcurementAlert.OPEN_STATUSES)

    # -- approvals & my work (scm spine) --------------------------------------------------------
    reqs = PurchaseRequisition.objects.filter(tenant=tenant)
    orders = PurchaseOrder.objects.filter(tenant=tenant)

    committed_statuses = PurchaseRequisition.COMMITTED_STATUSES
    closed_orders = PurchaseOrder.CLOSED_STATUSES
    live_reqs = reqs.exclude(status__in=["cancelled", "rejected", "converted"])

    stats = {
        "my_open_alerts": open_alerts.filter(assigned_to=me).count(),
        "open_alerts": open_alerts.count(),
        "overdue_alerts": open_alerts.filter(due_at__lt=timezone.now()).count(),
        "pending_approvals": reqs.filter(status="pending_approval").count(),
        "po_pending_approvals": orders.filter(status="pending_approval").count(),
        "my_drafts": reqs.filter(requester=me, status="draft").count(),
        # "Committed spend" = requisitions RAISED this calendar month AND currently
        # approved/converted (created_at buckets the raise; status is read as of NOW) — not
        # "approved in-month", which created_at alone cannot tell you.
        "committed_this_month": _sum(reqs.filter(status__in=committed_statuses,
                                                 created_at__gte=month_start)),
        "committed_last_month": _sum(reqs.filter(
            status__in=committed_statuses,
            created_at__gte=prev_month_start, created_at__lt=month_start)),
        "my_requested_this_month": _sum(reqs.filter(requester=me,
                                                    created_at__gte=month_start)),
        "open_po_value": (orders.exclude(status__in=closed_orders)
                          .aggregate(s=Sum("total"))["s"] or 0),
        "open_pos": orders.exclude(status__in=closed_orders).count(),
    }

    upcoming_alerts = (open_alerts.filter(due_at__isnull=False)
                       .order_by("due_at")[:6])
    due_requisitions = (live_reqs.filter(required_by__gte=today, required_by__lte=window_end)
                        .order_by("required_by")[:6])
    recent_activity = list(procurement_activity_qs(tenant)[:8])

    return render(request, "procurement/overview.html", {
        "stats": stats,
        "widgets": widgets,
        "widget_form": form,
        "pending_requisitions": (reqs.filter(status="pending_approval")
                                 .select_related("requester").order_by("created_at")[:6]),
        "my_open_alerts_list": (open_alerts.filter(assigned_to=me)
                                # due_at is nullable — plain ASC puts the undated (NULL) first on
                                # MariaDB, burying the actually-urgent rows; nulls_last fixes it
                                # (Django 5.1 emulates this on MariaDB).
                                .order_by(F("due_at").asc(nulls_last=True))[:5]),
        "upcoming_alerts": upcoming_alerts,
        "due_requisitions": due_requisitions,
        "recent_activity": recent_activity,
        "deadline_window_days": DEADLINE_WINDOW_DAYS,
    })


def _sum(qs):
    """``estimated_total`` over a requisition queryset as a plain number (0 when empty)."""
    return qs.aggregate(s=Sum("estimated_total"))["s"] or 0
