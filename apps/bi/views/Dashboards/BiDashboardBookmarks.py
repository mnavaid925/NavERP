import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.bi.forms.Dashboards.BiDashboardBookmarkForms import BiDashboardBookmarkForm
from apps.bi.models.Dashboards.BiDashboards import BiDashboard
from apps.bi.models.Dashboards.BiDashboardBookmarks import BiDashboardBookmark
from apps.bi.views._common import bi_object, bi_scope
from apps.core.utils import write_audit_log


@login_required
def bi_dashboard_bookmark_list(request):
    qs = (
        bi_scope(BiDashboardBookmark.objects.all(), request)
        .select_related("dashboard", "user")
        .defer("filter_state_json", "crossfilter_state_json")
    )
    # Users can view their own bookmarks, or bookmarks marked shared
    qs = qs.filter(Q(user=request.user) | Q(is_shared=True))
    total_bookmarks = qs.count()

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(number__icontains=q)
            | Q(dashboard__title__icontains=q)
            | Q(description__icontains=q)
        )

    dashboard_id = request.GET.get("dashboard", "").strip()
    if dashboard_id and dashboard_id.isdigit():
        qs = qs.filter(dashboard_id=dashboard_id)

    is_shared = request.GET.get("is_shared", "").strip()
    if is_shared in ("1", "true", "True"):
        qs = qs.filter(is_shared=True)
    elif is_shared in ("0", "false", "False"):
        qs = qs.filter(is_shared=False)

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    dashboards = BiDashboard.objects.filter(tenant=request.tenant, is_active=True).only("id", "title").order_by("title")

    context = {
        "page_obj": page_obj,
        "bookmarks": page_obj,
        "dashboards": dashboards,
        "total_bookmarks": total_bookmarks,
        "q": q,
        "dashboard_id": dashboard_id,
        "is_shared": is_shared,
    }
    return render(request, "bi/dashboards/bookmark/list.html", context)


@login_required
def bi_dashboard_bookmark_detail(request, pk):
    bookmark = bi_object(
        request,
        BiDashboardBookmark,
        pk,
        select_related=("dashboard", "user"),
    )

    filter_state_pretty = json.dumps(bookmark.filter_state_json, indent=2)
    crossfilter_state_pretty = json.dumps(bookmark.crossfilter_state_json, indent=2)

    context = {
        "bookmark": bookmark,
        "dashboard": bookmark.dashboard,
        "filter_state_pretty": filter_state_pretty,
        "crossfilter_state_pretty": crossfilter_state_pretty,
    }
    return render(request, "bi/dashboards/bookmark/detail.html", context)


@login_required
def bi_dashboard_bookmark_create(request):
    initial_data = {}
    dashboard_id = request.GET.get("dashboard")
    if dashboard_id:
        initial_data["dashboard"] = dashboard_id

    if request.method == "POST":
        form = BiDashboardBookmarkForm(request.POST, tenant=request.tenant, user=request.user)
        if form.is_valid():
            with transaction.atomic():
                bookmark = form.save(commit=False)
                bookmark.tenant = request.tenant
                bookmark.user = request.user

                # Capture active GET filter params if passed
                active_filters = {}
                for k, v in request.GET.items():
                    if k not in ("dashboard", "page"):
                        active_filters[k] = v
                if active_filters:
                    bookmark.filter_state_json = active_filters

                # If set to default, unset other defaults for this user on this dashboard
                if bookmark.is_default:
                    BiDashboardBookmark.objects.filter(
                        tenant=request.tenant,
                        dashboard=bookmark.dashboard,
                        user=request.user,
                        is_default=True,
                    ).update(is_default=False)

                bookmark.save()
                write_audit_log(
                    request.user,
                    bookmark,
                    "create",
                    changes=form.cleaned_data,
                    tenant=request.tenant,
                )
            messages.success(request, f"Bookmark '{bookmark.name}' saved successfully.")
            return redirect("bi:bi_dashboard_detail", pk=bookmark.dashboard_id)
    else:
        form = BiDashboardBookmarkForm(initial=initial_data, tenant=request.tenant, user=request.user)

    context = {
        "form": form,
        "bookmark": None,
        "is_edit": False,
    }
    return render(request, "bi/dashboards/bookmark/form.html", context)


@login_required
def bi_dashboard_bookmark_edit(request, pk):
    bookmark = bi_object(request, BiDashboardBookmark, pk)
    # Only owner or admin can edit
    if bookmark.user != request.user and not getattr(request, "is_tenant_admin", False):
        messages.error(request, "You can only modify your own bookmarks.")
        return redirect("bi:bi_dashboard_bookmark_detail", pk=bookmark.pk)

    if request.method == "POST":
        form = BiDashboardBookmarkForm(request.POST, instance=bookmark, tenant=request.tenant, user=request.user)
        if form.is_valid():
            with transaction.atomic():
                if form.cleaned_data.get("is_default"):
                    BiDashboardBookmark.objects.filter(
                        tenant=request.tenant,
                        dashboard=bookmark.dashboard,
                        user=request.user,
                        is_default=True,
                    ).exclude(pk=bookmark.pk).update(is_default=False)

                bookmark = form.save()
                write_audit_log(
                    request.user,
                    bookmark,
                    "update",
                    changes=form.cleaned_data,
                    tenant=request.tenant,
                )
            messages.success(request, f"Bookmark '{bookmark.name}' updated successfully.")
            return redirect("bi:bi_dashboard_bookmark_detail", pk=bookmark.pk)
    else:
        form = BiDashboardBookmarkForm(instance=bookmark, tenant=request.tenant, user=request.user)

    context = {
        "form": form,
        "bookmark": bookmark,
        "is_edit": True,
    }
    return render(request, "bi/dashboards/bookmark/form.html", context)


@login_required
@require_POST
def bi_dashboard_bookmark_delete(request, pk):
    bookmark = bi_object(request, BiDashboardBookmark, pk)
    if bookmark.user != request.user and not getattr(request, "is_tenant_admin", False):
        messages.error(request, "You can only delete your own bookmarks.")
        return redirect("bi:bi_dashboard_bookmark_detail", pk=bookmark.pk)

    dashboard_id = bookmark.dashboard_id
    name = bookmark.name
    with transaction.atomic():
        write_audit_log(
            request.user,
            bookmark,
            "delete",
            changes={"name": name, "number": bookmark.number},
            tenant=request.tenant,
        )
        bookmark.delete()
    messages.success(request, f"Bookmark '{name}' deleted.")
    return redirect("bi:bi_dashboard_detail", pk=dashboard_id)


@login_required
def bi_dashboard_bookmark_apply(request, pk):
    bookmark = bi_object(request, BiDashboardBookmark, pk)
    if bookmark.user != request.user and not bookmark.is_shared and not getattr(request, "is_tenant_admin", False):
        return HttpResponseForbidden("You do not have permission to access this private bookmark.")
    BiDashboardBookmark.objects.filter(pk=bookmark.pk).update(
        view_count=bookmark.view_count + 1,
        last_viewed_at=timezone.now(),
    )
    url = reverse("bi:bi_dashboard_canvas_view", kwargs={"pk": bookmark.dashboard_id}) + f"?bookmark={bookmark.pk}"
    return redirect(url)
