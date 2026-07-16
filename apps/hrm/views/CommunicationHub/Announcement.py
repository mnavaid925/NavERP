"""HRM 3.27 Communication Hub — Announcement views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.CommunicationHub._helpers import _announcement_targets
from apps.hrm.models import (
    Announcement,
)
from apps.hrm.forms import (
    AnnouncementForm,
)
from apps.hrm.views.CommunicationHub._helpers import _announcement_targets
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile
from apps.hrm.views.PerformanceReview._helpers import _is_admin


@login_required
def announcement_list(request):
    # The list template renders no FK objects (only local fields + a status/pin badge); the audience
    # filter uses target_*_id in WHERE, not the related objects — so no select_related is needed here
    # (announcement_detail does its own select_related for the fields it shows).
    qs = Announcement.objects.filter(tenant=request.tenant)
    is_admin = _is_admin(request.user)
    if is_admin:
        extra = {"is_admin": True,
                 "status_choices": Announcement.STATUS_CHOICES,
                 "category_choices": Announcement.CATEGORY_CHOICES,
                 "audience_type_choices": Announcement.AUDIENCE_TYPE_CHOICES}
        filters = [("status", "status", False), ("category", "category", False),
                   ("audience_type", "audience_type", False)]
        return crud_list(request, qs, "hrm/communication/announcement/list.html",
                         search_fields=("number", "title", "body"), filters=filters, extra_context=extra)
    # Employee feed: only published, un-expired announcements targeted at the viewer.
    today = timezone.localdate()
    qs = qs.filter(status="published").filter(Q(expires_at__isnull=True) | Q(expires_at__gte=today))
    profile = _current_employee_profile(request)
    dept_id = profile.employment.org_unit_id if (profile and profile.employment_id) else None
    desig_id = profile.designation_id if profile else None
    # Only add the department/designation clause when the viewer actually HAS one — otherwise a None id
    # degrades to `target_* IS NULL`, which would match an orphaned-target announcement (its FK was
    # SET_NULL'd by deleting the OrgUnit/Designation) that _announcement_targets then 403s on click.
    audience_q = Q(audience_type="all")
    if dept_id is not None:
        audience_q |= Q(audience_type="department", target_department_id=dept_id)
    if desig_id is not None:
        audience_q |= Q(audience_type="designation", target_designation_id=desig_id)
    qs = qs.filter(audience_q)
    return crud_list(request, qs, "hrm/communication/announcement/list.html",
                     search_fields=("number", "title", "body"), extra_context={"is_admin": False})


@login_required
def announcement_detail(request, pk):
    obj = get_object_or_404(
        Announcement.objects.select_related("target_department", "target_designation", "author"),
        pk=pk, tenant=request.tenant)
    if not _is_admin(request.user):
        today = timezone.localdate()
        published_ok = obj.status == "published" and (obj.expires_at is None or obj.expires_at >= today)
        if not published_ok or not _announcement_targets(request, obj):
            raise PermissionDenied("This announcement isn't available to you.")
    return render(request, "hrm/communication/announcement/detail.html",
                  {"obj": obj, "is_admin": _is_admin(request.user)})


@tenant_admin_required
def announcement_create(request):
    if request.tenant is None:  # the superuser has tenant=None — don't create an orphan row (IntegrityError)
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = AnnouncementForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.author = request.user  # stamped server-side, never a form field
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Announcement {obj.number} created.")
            return redirect("hrm:announcement_detail", pk=obj.pk)
    else:
        form = AnnouncementForm(tenant=request.tenant)
    return render(request, "hrm/communication/announcement/form.html", {"form": form, "is_edit": False})


@tenant_admin_required
def announcement_edit(request, pk):
    return crud_edit(request, model=Announcement, pk=pk, form_class=AnnouncementForm,
                     template="hrm/communication/announcement/form.html", success_url="hrm:announcement_list")


@tenant_admin_required
@require_POST
def announcement_delete(request, pk):
    return crud_delete(request, model=Announcement, pk=pk, success_url="hrm:announcement_list")


@tenant_admin_required
@require_POST
def announcement_publish(request, pk):
    obj = get_object_or_404(Announcement, pk=pk, tenant=request.tenant)
    if obj.status == "draft":
        obj.status = "published"
        obj.published_at = timezone.now()
        obj.save(update_fields=["status", "published_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "publish"})
        messages.success(request, f"Announcement {obj.number} published.")
    else:
        messages.error(request, "Only a draft announcement can be published.")
    return redirect("hrm:announcement_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def announcement_archive(request, pk):
    obj = get_object_or_404(Announcement, pk=pk, tenant=request.tenant)
    if obj.status == "published":
        obj.status = "archived"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "archive"})
        messages.success(request, f"Announcement {obj.number} archived.")
    else:
        messages.error(request, "Only a published announcement can be archived.")
    return redirect("hrm:announcement_detail", pk=obj.pk)
