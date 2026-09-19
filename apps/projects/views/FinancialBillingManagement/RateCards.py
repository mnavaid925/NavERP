"""Projects 7.15 Financial & Billing Management — ProjectRateCard views.
"""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.crud import as_db_int, crud_create, crud_delete, crud_edit, crud_list
from apps.projects.forms.FinancialBillingManagement.RateCards import ProjectRateCardForm
from apps.projects.models.FinancialBillingManagement.RateCards import ProjectRateCard
from apps.projects.models.ProjectInitiation.Projects import Project
from apps.projects.views._common import login_required


@login_required
def rtc_list(request):
    qs = (
        ProjectRateCard.objects.filter(tenant=request.tenant)
        .select_related("project", "client", "currency")
    )
    project_id = as_db_int(request.GET.get("project"))
    if project_id:
        qs = qs.filter(project_id=project_id)

    is_active_val = request.GET.get("is_active", "")
    if is_active_val == "true":
        qs = qs.filter(is_active=True)
    elif is_active_val == "false":
        qs = qs.filter(is_active=False)

    projects = Project.objects.filter(tenant=request.tenant).order_by("name")

    return crud_list(
        request,
        qs,
        "projects/financialbilling/ratecard/list.html",
        search_fields=["number", "name", "role_name", "activity_code", "project__name"],
        filters=[],
        extra_context={
            "projects": projects,
            "project_filter": project_id,
            "is_active_filter": is_active_val,
        },
    )


@login_required
def rtc_create(request):
    return crud_create(
        request,
        form_class=ProjectRateCardForm,
        template="projects/financialbilling/ratecard/form.html",
        success_url="projects:rtc_list",
        extra_context={"is_edit": False},
    )


@login_required
def rtc_detail(request, pk):
    rate_card = get_object_or_404(
        ProjectRateCard.objects.select_related("project", "client", "currency"),
        pk=pk,
        tenant=request.tenant,
    )
    return render(
        request,
        "projects/financialbilling/ratecard/detail.html",
        {
            "obj": rate_card,
            "rate_card": rate_card,
        },
    )


@login_required
def rtc_edit(request, pk):
    rate_card = get_object_or_404(
        ProjectRateCard,
        pk=pk,
        tenant=request.tenant,
    )
    return crud_edit(
        request,
        model=ProjectRateCard,
        pk=pk,
        form_class=ProjectRateCardForm,
        template="projects/financialbilling/ratecard/form.html",
        success_url="projects:rtc_list",
        extra_context={"is_edit": True, "obj": rate_card, "rate_card": rate_card},
    )


@login_required
@require_POST
def rtc_delete(request, pk):
    return crud_delete(
        request,
        model=ProjectRateCard,
        pk=pk,
        success_url="projects:rtc_list",
    )
