"""Projects 7.15 Financial & Billing Management — ProjectBillingRun views.
"""
from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounting.models import Invoice, InvoiceLine
from apps.core.crud import as_db_int, crud_create, crud_delete, crud_edit, crud_list
from apps.core.utils import write_audit_log
from apps.projects.forms.FinancialBillingManagement.BillingRuns import (
    BillingRunDispatchForm,
    ProjectBillingRunForm,
)
from apps.projects.models.FinancialBillingManagement.BillingRuns import ProjectBillingRun
from apps.projects.models.ProjectInitiation.Projects import Project
from apps.projects.views._common import login_required


@login_required
def pbr_list(request):
    qs = (
        ProjectBillingRun.objects.filter(tenant=request.tenant)
        .select_related("project", "client", "sow", "milestone", "currency", "accounting_invoice")
    )
    project_id = as_db_int(request.GET.get("project"))
    if project_id:
        qs = qs.filter(project_id=project_id)

    status_filter = request.GET.get("status", "")
    if status_filter:
        qs = qs.filter(status=status_filter)

    projects = Project.objects.filter(tenant=request.tenant).order_by("name")

    return crud_list(
        request,
        qs,
        "projects/financialbilling/billingrun/list.html",
        search_fields=["number", "project__name", "client__name", "recipient_email", "notes"],
        filters=[
            ("status", "status", False),
        ],
        extra_context={
            "projects": projects,
            "project_filter": project_id,
            "status_choices": ProjectBillingRun.STATUS_CHOICES,
            "status_filter": status_filter,
            "total_count": qs.count(),
        },
    )


@login_required
def pbr_create(request):
    return crud_create(
        request,
        form_class=ProjectBillingRunForm,
        template="projects/financialbilling/billingrun/form.html",
        success_url="projects:pbr_list",
        extra_context={"is_edit": False},
    )


@login_required
def pbr_detail(request, pk):
    billing_run = get_object_or_404(
        ProjectBillingRun.objects.select_related(
            "project", "client", "sow", "milestone", "tax_code", "currency", "accounting_invoice", "dispatched_by"
        ),
        pk=pk,
        tenant=request.tenant,
    )
    dispatch_form = BillingRunDispatchForm(initial={"recipient_email": billing_run.recipient_email})
    return render(
        request,
        "projects/financialbilling/billingrun/detail.html",
        {
            "obj": billing_run,
            "billing_run": billing_run,
            "dispatch_form": dispatch_form,
        },
    )


@login_required
def pbr_edit(request, pk):
    billing_run = get_object_or_404(
        ProjectBillingRun,
        pk=pk,
        tenant=request.tenant,
    )
    if billing_run.status in ("invoiced", "cancelled"):
        messages.warning(request, f"Billing run {billing_run.number} is {billing_run.get_status_display()} and cannot be edited.")
        return redirect("projects:pbr_detail", pk=billing_run.pk)

    return crud_edit(
        request,
        model=ProjectBillingRun,
        pk=pk,
        form_class=ProjectBillingRunForm,
        template="projects/financialbilling/billingrun/form.html",
        success_url="projects:pbr_list",
        extra_context={"is_edit": True, "obj": billing_run, "billing_run": billing_run},
    )


@login_required
@require_POST
def pbr_delete(request, pk):
    billing_run = get_object_or_404(ProjectBillingRun, pk=pk, tenant=request.tenant)
    if billing_run.status == "invoiced":
        messages.error(request, "Cannot delete an invoiced billing run.")
        return redirect("projects:pbr_detail", pk=billing_run.pk)

    return crud_delete(
        request,
        model=ProjectBillingRun,
        pk=pk,
        success_url="projects:pbr_list",
    )


@login_required
@require_POST
def pbr_approve(request, pk):
    billing_run = get_object_or_404(ProjectBillingRun, pk=pk, tenant=request.tenant)
    if billing_run.status != "draft":
        messages.error(request, f"Billing run {billing_run.number} cannot be approved because status is {billing_run.get_status_display()}.")
        return redirect("projects:pbr_detail", pk=billing_run.pk)

    billing_run.status = "approved"
    billing_run.save(update_fields=["status", "updated_at"])
    write_audit_log(
        tenant=request.tenant,
        user=request.user,
        action="approve",
        obj=billing_run,
        changes={"status": ["draft", "approved"]},
    )
    messages.success(request, f"Billing run {billing_run.number} approved successfully.")
    return redirect("projects:pbr_detail", pk=billing_run.pk)


@login_required
@require_POST
def pbr_generate_invoice(request, pk):
    with transaction.atomic():
        billing_run = get_object_or_404(
            ProjectBillingRun.objects.select_for_update().select_related("project", "client", "currency", "tax_code"),
            pk=pk,
            tenant=request.tenant,
        )
        if billing_run.status not in ("draft", "approved"):
            messages.error(request, f"Billing run {billing_run.number} cannot generate an invoice because status is {billing_run.get_status_display()}.")
            return redirect("projects:pbr_detail", pk=billing_run.pk)
        invoice = Invoice.objects.create(
            tenant=request.tenant,
            party=billing_run.client,
            issue_date=billing_run.run_date,
            due_date=billing_run.run_date,
            currency=billing_run.currency,
            status="draft",
            notes=f"Generated from Project {billing_run.project.number} — Billing Run {billing_run.number}\n{billing_run.notes}",
        )

        if billing_run.labor_amount > Decimal("0.00"):
            InvoiceLine.objects.create(
                invoice=invoice,
                description=f"Professional Services (Labor): {billing_run.total_time_hours} hrs up to {billing_run.cutoff_date}",
                quantity=Decimal("1.00"),
                unit_price=billing_run.labor_amount,
                tax_rate_pct=billing_run.tax_rate_pct,
            )

        if billing_run.expense_amount > Decimal("0.00"):
            InvoiceLine.objects.create(
                invoice=invoice,
                description=f"Direct Reimbursable Project Expenses up to {billing_run.cutoff_date}",
                quantity=Decimal("1.00"),
                unit_price=billing_run.expense_amount,
                tax_rate_pct=billing_run.tax_rate_pct,
            )

        if billing_run.fee_amount > Decimal("0.00"):
            InvoiceLine.objects.create(
                invoice=invoice,
                description=f"Fixed Milestone / Contract Fees ({billing_run.get_billing_type_display()})",
                quantity=Decimal("1.00"),
                unit_price=billing_run.fee_amount,
                tax_rate_pct=billing_run.tax_rate_pct,
            )

        if billing_run.labor_amount == 0 and billing_run.expense_amount == 0 and billing_run.fee_amount == 0:
            InvoiceLine.objects.create(
                invoice=invoice,
                description=f"Project Billing: {billing_run.project.name} ({billing_run.get_billing_type_display()})",
                quantity=Decimal("1.00"),
                unit_price=billing_run.subtotal,
                tax_rate_pct=billing_run.tax_rate_pct,
            )

        initial_status = billing_run.status
        invoice.recalc_totals()

        billing_run.accounting_invoice = invoice
        billing_run.status = "invoiced"
        billing_run.save(update_fields=["accounting_invoice", "status", "updated_at"])

        write_audit_log(
            tenant=request.tenant,
            user=request.user,
            action="generate",
            obj=billing_run,
            changes={"accounting_invoice": str(invoice.pk), "status": [initial_status, "invoiced"]},
        )

    messages.success(request, f"Canonical accounting Invoice {invoice.number} successfully created for Billing Run {billing_run.number}.")
    return redirect("projects:pbr_detail", pk=billing_run.pk)


@login_required
@require_POST
def pbr_dispatch(request, pk):
    billing_run = get_object_or_404(ProjectBillingRun, pk=pk, tenant=request.tenant)
    if billing_run.status != "invoiced":
        messages.error(request, "Only invoiced billing runs can be dispatched.")
        return redirect("projects:pbr_detail", pk=billing_run.pk)
    form = BillingRunDispatchForm(request.POST)
    if form.is_valid():
        email = form.cleaned_data["recipient_email"]
        notes = form.cleaned_data.get("notes", "")

        billing_run.recipient_email = email
        billing_run.dispatched_at = timezone.now()
        billing_run.dispatched_by = request.user
        if notes:
            billing_run.notes = (billing_run.notes + f"\n[Dispatch note]: {notes}").strip()
        billing_run.save(update_fields=["recipient_email", "dispatched_at", "dispatched_by", "notes", "updated_at"])

        write_audit_log(
            tenant=request.tenant,
            user=request.user,
            action="dispatch",
            obj=billing_run,
            changes={"dispatched_to": email, "dispatched_at": billing_run.dispatched_at.isoformat()},
        )
        messages.success(request, f"Billing run {billing_run.number} dispatched to {email}.")
    else:
        messages.error(request, "Please enter a valid recipient email address.")

    return redirect("projects:pbr_detail", pk=billing_run.pk)


@login_required
def pbr_preview_pdf(request, pk):
    billing_run = get_object_or_404(
        ProjectBillingRun.objects.select_related("project", "client", "currency", "tax_code", "accounting_invoice"),
        pk=pk,
        tenant=request.tenant,
    )
    return render(
        request,
        "projects/financialbilling/billingrun/preview_pdf.html",
        {
            "billing_run": billing_run,
            "obj": billing_run,
        },
    )
