import urllib.parse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.core.models import OrgUnit
from apps.core.utils import write_audit_log
from apps.documents.forms.SearchDiscovery.DocumentSavedSearches import DocumentSavedSearchForm
from apps.documents.models.SearchDiscovery.DocumentSavedSearches import DocumentSavedSearch
from apps.documents.views._common import documents_object, documents_scope


def _can_access_saved_search(user, saved_search):
    if getattr(user, "is_tenant_admin", False) or getattr(user, "is_superuser", False):
        return True
    if saved_search.owner == user:
        return True
    if saved_search.visibility == "public":
        return True
    if saved_search.visibility == "shared_department":
        user_dept = getattr(user, "department", None)
        if user_dept and saved_search.department_id == user_dept.id:
            return True
    return False


@login_required
def document_saved_search_list(request):
    qs = documents_scope(DocumentSavedSearch.objects.all(), request).select_related("owner", "department")

    # Visibility scoping: user can see owned, public, or their department
    if not getattr(request.user, "is_tenant_admin", False):
        user_dept = getattr(request.user, "department", None)
        vis_filter = Q(owner=request.user) | Q(visibility="public")
        if user_dept:
            vis_filter |= Q(visibility="shared_department", department=user_dept)
        qs = qs.filter(vis_filter)

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(query_text__icontains=q) | Q(number__icontains=q))

    visibility = request.GET.get("visibility", "").strip()
    if visibility:
        qs = qs.filter(visibility=visibility)

    status = request.GET.get("status", "").strip()
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "inactive":
        qs = qs.filter(is_active=False)

    department_id = request.GET.get("department", "").strip()
    if department_id and department_id.isdigit():
        qs = qs.filter(department_id=int(department_id))

    is_pinned = request.GET.get("is_pinned", "").strip()
    if is_pinned == "1":
        qs = qs.filter(is_pinned=True)

    total_count = qs.count()
    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    departments = OrgUnit.objects.filter(tenant=request.tenant).order_by("name")

    status_choices = [("active", "Active"), ("inactive", "Inactive")]

    return render(
        request,
        "documents/search_discovery/document_saved_search/list.html",
        {
            "page_obj": page_obj,
            "saved_searches": page_obj.object_list,
            "total_count": total_count,
            "departments": departments,
            "visibility_choices": DocumentSavedSearch.VISIBILITY_CHOICES,
            "sort_by_choices": DocumentSavedSearch.SORT_BY_CHOICES,
            "status_choices": status_choices,
        },
    )


@login_required
def document_saved_search_detail(request, pk):
    saved_search = documents_object(
        request,
        DocumentSavedSearch,
        pk,
        select_related=("owner", "department"),
    )
    if not _can_access_saved_search(request.user, saved_search):
        return HttpResponseForbidden("You do not have permission to view this saved search.")
    alerts = saved_search.alerts.filter(tenant=request.tenant).select_related("subscriber")
    parsed_filters = saved_search.get_filters_dict()
    parsed_facet_filters = saved_search.get_facet_filters_dict()

    return render(
        request,
        "documents/search_discovery/document_saved_search/detail.html",
        {
            "saved_search": saved_search,
            "alerts": alerts,
            "parsed_filters": parsed_filters,
            "parsed_facet_filters": parsed_facet_filters,
        },
    )


@login_required
def document_saved_search_create(request):
    if request.method == "POST":
        form = DocumentSavedSearchForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            saved_search = form.save(commit=False)
            saved_search.tenant = request.tenant
            saved_search.owner = request.user
            saved_search.save()
            write_audit_log(request.user, saved_search, "create", tenant=request.tenant)
            messages.success(request, f"Saved search '{saved_search.name}' created successfully.")
            return redirect("documents:document_saved_search_detail", pk=saved_search.pk)
    else:
        form = DocumentSavedSearchForm(tenant=request.tenant)

    return render(
        request,
        "documents/search_discovery/document_saved_search/form.html",
        {
            "form": form,
            "saved_search": None,
            "is_edit": False,
        },
    )


@login_required
def document_saved_search_edit(request, pk):
    saved_search = documents_object(request, DocumentSavedSearch, pk)

    if saved_search.owner != request.user and not getattr(request.user, "is_tenant_admin", False):
        return HttpResponseForbidden("You do not have permission to edit this saved search.")

    if request.method == "POST":
        form = DocumentSavedSearchForm(request.POST, instance=saved_search, tenant=request.tenant)
        if form.is_valid():
            saved_search = form.save()
            write_audit_log(request.user, saved_search, "update", tenant=request.tenant)
            messages.success(request, f"Saved search '{saved_search.name}' updated successfully.")
            return redirect("documents:document_saved_search_detail", pk=saved_search.pk)
    else:
        form = DocumentSavedSearchForm(instance=saved_search, tenant=request.tenant)

    return render(
        request,
        "documents/search_discovery/document_saved_search/form.html",
        {
            "form": form,
            "saved_search": saved_search,
            "is_edit": True,
        },
    )


@login_required
@require_POST
def document_saved_search_delete(request, pk):
    saved_search = documents_object(request, DocumentSavedSearch, pk)

    if saved_search.owner != request.user and not getattr(request.user, "is_tenant_admin", False):
        return HttpResponseForbidden("You do not have permission to delete this saved search.")

    name = saved_search.name
    write_audit_log(request.user, saved_search, "delete", tenant=request.tenant)
    saved_search.delete()
    messages.success(request, f"Saved search '{name}' was deleted.")
    return redirect("documents:document_saved_search_list")


@login_required
def document_saved_search_run(request, pk):
    saved_search = documents_object(request, DocumentSavedSearch, pk)

    if not _can_access_saved_search(request.user, saved_search):
        return HttpResponseForbidden("You do not have permission to run this saved search.")

    saved_search.run_count += 1
    saved_search.last_run_at = timezone.now()
    saved_search.save(update_fields=["run_count", "last_run_at"])
    write_audit_log(request.user, saved_search, "execute", tenant=request.tenant)

    query_params = {}
    if saved_search.query_text:
        query_params["q"] = saved_search.query_text

    filters = saved_search.get_filters_dict()
    for k, v in filters.items():
        if v:
            query_params[k] = v

    query_params["saved_search_id"] = str(saved_search.pk)
    encoded = urllib.parse.urlencode(query_params)
    return redirect(f"/documents/search/?{encoded}")


@login_required
@require_POST
def document_saved_search_toggle_pin(request, pk):
    saved_search = documents_object(request, DocumentSavedSearch, pk)

    if saved_search.owner != request.user and not getattr(request.user, "is_tenant_admin", False):
        return HttpResponseForbidden("You do not have permission to modify this saved search.")

    saved_search.is_pinned = not saved_search.is_pinned
    saved_search.save(update_fields=["is_pinned"])
    write_audit_log(request.user, saved_search, "toggle", tenant=request.tenant)

    status_str = "pinned" if saved_search.is_pinned else "unpinned"
    messages.success(request, f"Saved search '{saved_search.name}' {status_str}.")
    referer = request.META.get("HTTP_REFERER")
    if referer and url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()}):
        return redirect(referer)
    return redirect("documents:document_saved_search_list")
