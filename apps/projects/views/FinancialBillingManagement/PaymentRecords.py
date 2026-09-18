"""Projects 7.15 Financial & Billing Management — ProjectPaymentRecord views.
"""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.crud import as_db_int, crud_create, crud_delete, crud_edit, crud_list
from apps.core.utils import write_audit_log
from apps.projects.forms.FinancialBillingManagement.PaymentRecords import (
    ContactLogForm,
    PaymentPromiseForm,
    ProjectPaymentRecordForm,
)
from apps.projects.models.FinancialBillingManagement.PaymentRecords import ProjectPaymentRecord
from apps.projects.models.ProjectInitiation.Projects import Project
from apps.projects.views._common import login_required


@login_required
def ppr_list(request):
    qs = (
        ProjectPaymentRecord.objects.filter(tenant=request.tenant)
        .select_related("project", "client", "billing_run", "accounting_invoice", "assigned_collector")
    )
    project_id = as_db_int(request.GET.get("project"))
    if project_id:
        qs = qs.filter(project_id=project_id)

    stage_filter = request.GET.get("stage", "")
    if stage_filter:
        qs = qs.filter(stage=stage_filter)

    dunning_filter = request.GET.get("dunning_level", "")
    if dunning_filter:
        qs = qs.filter(dunning_level=dunning_filter)

    projects = Project.objects.filter(tenant=request.tenant).order_by("name")

    return crud_list(
        request,
        qs,
        "projects/financialbilling/paymentrecord/list.html",
        search_fields=["number", "project__name", "client__name", "accounting_invoice__number", "notes"],
        filters=[
            ("stage", "stage", False),
            ("dunning_level", "dunning_level", False),
        ],
        extra_context={
            "payment_records": qs,
            "projects": projects,
            "project_filter": project_id,
            "stage_choices": ProjectPaymentRecord.STAGE_CHOICES,
            "stage_filter": stage_filter,
            "dunning_choices": ProjectPaymentRecord.DUNNING_LEVEL_CHOICES,
            "dunning_filter": dunning_filter,
            "total_count": qs.count(),
        },
    )


@login_required
def ppr_create(request):
    return crud_create(
        request,
        form_class=ProjectPaymentRecordForm,
        template="projects/financialbilling/paymentrecord/form.html",
        success_url="projects:ppr_list",
        extra_context={"is_edit": False},
    )


@login_required
def ppr_detail(request, pk):
    payment_record = get_object_or_404(
        ProjectPaymentRecord.objects.select_related(
            "project", "client", "billing_run", "accounting_invoice", "assigned_collector"
        ),
        pk=pk,
        tenant=request.tenant,
    )
    promise_form = PaymentPromiseForm(initial={
        "promised_payment_date": payment_record.promised_payment_date,
        "promised_amount": payment_record.promised_amount,
    })
    contact_form = ContactLogForm(initial={"contact_date": timezone.localdate()})

    return render(
        request,
        "projects/financialbilling/paymentrecord/detail.html",
        {
            "obj": payment_record,
            "payment_record": payment_record,
            "promise_form": promise_form,
            "contact_form": contact_form,
        },
    )


@login_required
def ppr_edit(request, pk):
    payment_record = get_object_or_404(
        ProjectPaymentRecord,
        pk=pk,
        tenant=request.tenant,
    )
    return crud_edit(
        request,
        model=ProjectPaymentRecord,
        pk=pk,
        form_class=ProjectPaymentRecordForm,
        template="projects/financialbilling/paymentrecord/form.html",
        success_url="projects:ppr_list",
        extra_context={"is_edit": True, "obj": payment_record, "payment_record": payment_record},
    )


@login_required
@require_POST
def ppr_delete(request, pk):
    return crud_delete(
        request,
        model=ProjectPaymentRecord,
        pk=pk,
        success_url="projects:ppr_list",
    )


@login_required
@require_POST
def ppr_log_contact(request, pk):
    record = get_object_or_404(ProjectPaymentRecord, pk=pk, tenant=request.tenant)
    form = ContactLogForm(request.POST)
    if form.is_valid():
        c_date = form.cleaned_data["contact_date"]
        notes = form.cleaned_data["notes"]
        f_date = form.cleaned_data.get("next_follow_up_date")

        record.last_contact_date = c_date
        if f_date:
            record.next_follow_up_date = f_date
        record.notes = (record.notes + f"\n[{c_date} Contact Log]: {notes}").strip()
        record.save(update_fields=["last_contact_date", "next_follow_up_date", "notes", "updated_at"])

        write_audit_log(
            tenant=request.tenant,
            user=request.user,
            action="contact",
            obj=record,
            changes={"last_contact_date": str(c_date)},
        )
        messages.success(request, f"Contact log added to {record.number}.")
    else:
        messages.error(request, "Failed to log contact. Please check the form.")

    return redirect("projects:ppr_detail", pk=record.pk)


@login_required
@require_POST
def ppr_record_promise(request, pk):
    record = get_object_or_404(ProjectPaymentRecord, pk=pk, tenant=request.tenant)
    form = PaymentPromiseForm(request.POST)
    if form.is_valid():
        p_date = form.cleaned_data["promised_payment_date"]
        p_amt = form.cleaned_data["promised_amount"]
        notes = form.cleaned_data.get("notes", "")

        record.promised_payment_date = p_date
        record.promised_amount = p_amt
        record.stage = "promise_to_pay"
        if notes:
            record.notes = (record.notes + f"\n[Promise to Pay]: {p_amt} on {p_date}. {notes}").strip()
        record.save(update_fields=["promised_payment_date", "promised_amount", "stage", "notes", "updated_at"])

        write_audit_log(
            tenant=request.tenant,
            user=request.user,
            action="promise",
            obj=record,
            changes={"promised_payment_date": str(p_date), "promised_amount": str(p_amt)},
        )
        messages.success(request, f"Promise to pay recorded for {record.number}.")
    else:
        messages.error(request, "Invalid promise to pay values.")

    return redirect("projects:ppr_detail", pk=record.pk)


@login_required
@require_POST
def ppr_escalate(request, pk):
    record = get_object_or_404(ProjectPaymentRecord, pk=pk, tenant=request.tenant)
    dunning_ladder = ["friendly_reminder", "first_notice", "second_notice", "final_demand", "legal"]
    curr_idx = dunning_ladder.index(record.dunning_level) if record.dunning_level in dunning_ladder else 0

    if curr_idx < len(dunning_ladder) - 1:
        new_dunning = dunning_ladder[curr_idx + 1]
    else:
        new_dunning = "legal"

    record.dunning_level = new_dunning
    record.status = "escalated"
    record.stage = "overdue"
    record.save(update_fields=["dunning_level", "status", "stage", "updated_at"])

    write_audit_log(
        tenant=request.tenant,
        user=request.user,
        action="escalate",
        obj=record,
        changes={"dunning_level": new_dunning, "status": "escalated"},
    )
    messages.warning(request, f"Collection {record.number} escalated to {record.get_dunning_level_display()}.")
    return redirect("projects:ppr_detail", pk=record.pk)


@login_required
@require_POST
def ppr_resolve(request, pk):
    record = get_object_or_404(ProjectPaymentRecord, pk=pk, tenant=request.tenant)
    record.stage = "settled"
    record.status = "resolved"
    record.save(update_fields=["stage", "status", "updated_at"])

    write_audit_log(
        tenant=request.tenant,
        user=request.user,
        action="resolve",
        obj=record,
        changes={"stage": "settled", "status": "resolved"},
    )
    messages.success(request, f"Collection record {record.number} marked as settled and resolved.")
    return redirect("projects:ppr_detail", pk=record.pk)
