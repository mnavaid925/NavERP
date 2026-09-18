"""Projects 7.14 Client & External Collaboration — StatementOfWork views.
"""
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.crud import as_db_int, crud_create, crud_delete, crud_edit, crud_list
from apps.core.utils import write_audit_log
from apps.projects.forms.ClientExternalCollaboration.StatementOfWorks import (
    SOWAmendmentForm,
    StatementOfWorkForm,
)
from apps.projects.models.ClientExternalCollaboration.StatementOfWorks import (
    SOWAmendment,
    StatementOfWork,
)
from apps.projects.models.ProjectInitiation.Projects import Project
from apps.projects.views._common import login_required


@login_required
def sow_list(request):
    qs = (
        StatementOfWork.objects.filter(tenant=request.tenant)
        .select_related("project", "client", "currency")
        .prefetch_related("amendments")
    )
    project_id = as_db_int(request.GET.get("project"))
    if project_id:
        qs = qs.filter(project_id=project_id)

    projects = Project.objects.filter(tenant=request.tenant).order_by("name")

    return crud_list(
        request,
        qs,
        "projects/clientcollaboration/statementofwork/list.html",
        search_fields=["number", "title", "sow_code", "client__name", "scope_summary"],
        filters=[
            ("status", "status", False),
        ],
        extra_context={
            "sow_list": qs,
            "projects": projects,
            "project_filter": project_id,
            "status_choices": StatementOfWork.STATUS_CHOICES,
            "status_filter": request.GET.get("status", ""),
            "total_count": qs.count(),
        },
    )


@login_required
def sow_create(request):
    return crud_create(
        request,
        form_class=StatementOfWorkForm,
        template="projects/clientcollaboration/statementofwork/form.html",
        success_url="projects:sow_list",
        extra_context={"is_edit": False},
    )


@login_required
def sow_detail(request, pk):
    sow = get_object_or_404(
        StatementOfWork.objects.select_related("project", "client", "currency"),
        pk=pk,
        tenant=request.tenant,
    )
    amendments = sow.amendments.select_related("approved_by").order_by("amendment_number")
    return render(
        request,
        "projects/clientcollaboration/statementofwork/detail.html",
        {
            "obj": sow,
            "sow": sow,
            "amendments": amendments,
        },
    )


@login_required
def sow_edit(request, pk):
    sow = get_object_or_404(
        StatementOfWork,
        pk=pk,
        tenant=request.tenant,
    )
    return crud_edit(
        request,
        model=StatementOfWork,
        pk=pk,
        form_class=StatementOfWorkForm,
        template="projects/clientcollaboration/statementofwork/form.html",
        success_url="projects:sow_list",
        extra_context={"is_edit": True, "obj": sow, "sow": sow},
    )


@login_required
def sow_delete(request, pk):
    return crud_delete(
        request,
        model=StatementOfWork,
        pk=pk,
        success_url="projects:sow_list",
    )


@login_required
@require_POST
def sow_activate(request, pk):
    sow = get_object_or_404(
        StatementOfWork,
        pk=pk,
        tenant=request.tenant,
    )
    if sow.status == "active":
        messages.warning(request, f"SOW {sow.number} is already active.")
        return redirect("projects:sow_detail", pk=pk)

    with transaction.atomic():
        sow.status = "active"
        sow.activated_at = timezone.now()
        sow.activated_by = request.user
        sow.save()

        write_audit_log(
            request.user,
            sow,
            "activate",
            changes={"status": "active", "activated_at": str(sow.activated_at)},
        )
    messages.success(request, f"Statement of Work {sow.number} is now active.")
    return redirect("projects:sow_detail", pk=pk)


@login_required
def sow_amendment_create(request, pk):
    sow = get_object_or_404(
        StatementOfWork,
        pk=pk,
        tenant=request.tenant,
    )
    if request.method == "POST":
        form = SOWAmendmentForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                amendment = form.save(commit=False)
                amendment.tenant = request.tenant
                amendment.sow = sow
                if amendment.status == "approved":
                    amendment.approved_by = request.user
                    amendment.approved_at = timezone.now()
                amendment.save()

                if amendment.status == "approved" and sow.status == "active":
                    sow.status = "amended"
                    sow.save(update_fields=["status"])

                write_audit_log(
                    request.user,
                    amendment,
                    "create",
                    changes={"number": amendment.number, "sow": sow.number},
                )
            messages.success(request, f"Amendment #{amendment.amendment_number} created for SOW {sow.number}.")
            return redirect("projects:sow_detail", pk=sow.pk)
    else:
        next_num = sow.amendments.count() + 1
        form = SOWAmendmentForm(
            initial={"sow": sow, "amendment_number": next_num, "effective_date": timezone.localdate()},
            tenant=request.tenant,
        )

    return render(
        request,
        "projects/clientcollaboration/statementofwork/amendment_form.html",
        {"form": form, "sow": sow},
    )
