"""Sales 8.8 — the activity-type register views.

Straight CRUD over ``ActivityType`` with one deliberate detail: the filter bar declares its filters
through ``crud_list``'s ``filters`` spec, **not** merely by handing choice tuples to the template. A
control that renders and filters nothing is L54's third silent failure, and the template is where you
notice it because the template is what offers the affordance.

The ``active`` filter carries the stringified pair ``"active"``/``"inactive"`` rather than
``"True"``/``"False"``. ``crud_list`` maps those two to booleans for a ``BooleanField``, so the
stringified form would work — but it reads as a programming artefact in a URL a user can hand-edit,
and the paired wording is what the rest of the module uses.
"""
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

from apps.core.utils import write_audit_log
from apps.sales.forms.SalesActivityTaskManagement.ActivityTypes import ActivityTypeForm
from apps.sales.models.SalesActivityTaskManagement.ActivityLogs import ActivityLog
from apps.sales.models.SalesActivityTaskManagement.ActivityTypes import ActivityType
from apps.sales.models.SalesActivityTaskManagement.TaskTemplates import TaskTemplate
from apps.sales.views._common import *

LIST_TEMPLATE = "sales/salesactivitytaskmanagement/activitytype/list.html"
DETAIL_TEMPLATE = "sales/salesactivitytaskmanagement/activitytype/detail.html"
FORM_TEMPLATE = "sales/salesactivitytaskmanagement/activitytype/form.html"

#: Per-page value for the register, carried into the template as `page_size`.
PAGE_SIZE = 15

#: Most recent activities shown on a type's detail page.
MAX_RECENT_ACTIVITIES = 25

ACTIVE_CHOICES = [("active", "Active"), ("inactive", "Inactive")]


def _type_queryset(request):
    return ActivityType.objects.filter(tenant=request.tenant)


def _choice_context():
    """The three choice lists every type page renders. One source, three pages."""
    return {
        "kind_choices": ActivityType.KIND_CHOICES,
        "outcome_choices": ActivityType.OUTCOME_CHOICES,
        "priority_choices": ActivityType.PRIORITY_CHOICES,
        "active_choices": ACTIVE_CHOICES,
    }


@login_required
def activity_type_list(request):
    """The type catalogue: search, three GET filters, and usage counts per row."""
    stats = _type_queryset(request).aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        retired=Count("id", filter=Q(is_active=False)),
        unused=Count("id", filter=Q(activity_logs__isnull=True)),
    )
    return crud_list(
        request,
        _type_queryset(request).annotate(_usage=Count("activity_logs")),
        LIST_TEMPLATE,
        search_fields=["number", "name", "description"],
        # Declared HERE, not just handed to the template — L54's third rule.
        filters=[
            ("kind", "kind", False),
            ("default_priority", "default_priority", False),
            ("active", "is_active", True),
        ],
        extra_context={
            "page_size": PAGE_SIZE,
            **_choice_context(),
            "stats": stats,
        },
        per_page=PAGE_SIZE,
    )


@tenant_admin_required
def activity_type_create(request):
    return crud_create(
        request,
        form_class=ActivityTypeForm,
        template=FORM_TEMPLATE,
        success_url=reverse("sales:activity_type_list"),
        extra_context=_choice_context(),
    )


@login_required
def activity_type_detail(request, pk):
    obj = get_object_or_404(_type_queryset(request), pk=pk)
    recent_activities = ActivityLog.objects.filter(
        tenant=request.tenant, activity_type=obj
    ).select_related("owner", "opportunity", "communication_log")[:MAX_RECENT_ACTIVITIES]
    used_by_templates = TaskTemplate.objects.filter(
        tenant=request.tenant, activity_type=obj
    ).only("number", "name", "is_active")
    caveats = []
    if not obj.is_active:
        caveats.append(
            "This type is retired, so it stays off the picker — existing activities keep pointing "
            "at it, and a type referenced by history cannot be deleted."
        )
    if obj.default_outcome and obj.kind != "call":
        caveats.append(
            "This type carries a call outcome but is not a call, which the model refuses to save."
        )
    return render(request, DETAIL_TEMPLATE, {
        "obj": obj,
        **_choice_context(),
        "recent_activities": recent_activities,
        "used_by_templates": used_by_templates,
        "usage_count": ActivityLog.objects.filter(
            tenant=request.tenant, activity_type=obj
        ).count(),
        "template_count": TaskTemplate.objects.filter(
            tenant=request.tenant, activity_type=obj
        ).count(),
        "caveats": caveats,
    })


@tenant_admin_required
def activity_type_edit(request, pk):
    return crud_edit(
        request,
        model=ActivityType,
        pk=pk,
        form_class=ActivityTypeForm,
        template=FORM_TEMPLATE,
        success_url=reverse("sales:activity_type_detail", args=[pk]),
        extra_context=_choice_context(),
    )


@require_POST
@login_required
@tenant_admin_required
def activity_type_delete(request, pk):
    """Refuse the delete when history points at the type, and say why.

    ``ActivityLog.activity_type`` is ``PROTECT``, so an unguarded delete would raise
    ``ProtectedError`` inside the view and answer a POST with a 500. Checking first turns that into
    a redirect carrying a message the author can act on — retire the type instead.
    """
    obj = get_object_or_404(_type_queryset(request), pk=pk)
    usage = ActivityLog.objects.filter(tenant=request.tenant, activity_type=obj).count()
    template_usage = TaskTemplate.objects.filter(tenant=request.tenant, activity_type=obj).count()
    if usage or template_usage:
        reasons = []
        if usage:
            reasons.append(f"{usage} logged activity/activities")
        if template_usage:
            reasons.append(f"{template_usage} task template(s)")
        messages.warning(
            request,
            f"{obj.name} cannot be deleted because {', '.join(reasons)} still reference it. "
            "Retire it instead — it stays readable and disappears from the picker.",
        )
        return redirect("sales:activity_type_detail", pk=obj.pk)
    obj.delete()
    messages.success(request, f"Activity type {obj.name} deleted.")
    return redirect("sales:activity_type_list")