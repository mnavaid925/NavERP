"""Projects 7.14 Client & External Collaboration — ProjectClientInvoice views.
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
from apps.projects.forms.ClientExternalCollaboration.ClientInvoices import ProjectClientInvoiceForm
from apps.projects.models.ClientExternalCollaboration.ClientInvoices import ProjectClientInvoice
from apps.projects.models.ProjectInitiation.Projects import Project
from apps.projects.views._common import login_required


@login_required
def pci_list(request):
    qs = (
        ProjectClientInvoice.objects.filter(tenant=request.tenant)
        .select_related("project", "sow", "milestone", "currency", "accounting_invoice")
    )
    project_id = as_db_int(request.GET.get("project"))
    if project_id:
        qs = qs.filter(project_id=project_id)

    projects = Project.objects.filter(tenant=request.tenant).order_by("name")

    return crud_list(
        request,
        qs,
        "projects/clientcollaboration/clientinvoice/list.html",
        search_fields=["number", "project__name", "notes"],
        filters=[
            ("status", "status", False),
        ],
        extra_context={
            "invoice_list": qs,
            "projects": projects,
            "project_filter": project_id,
            "status_choices": ProjectClientInvoice.STATUS_CHOICES,
            "status_filter": request.GET.get("status", ""),
            "total_count": qs.count(),
        },
    )


@login_required
def pci_create(request):
    return crud_create(
        request,
        form_class=ProjectClientInvoiceForm,
        template="projects/clientcollaboration/clientinvoice/form.html",
        success_url="projects:pci_list",
        extra_context={"is_edit": False},
    )


@login_required
def pci_detail(request, pk):
    invoice_record = get_object_or_404(
        ProjectClientInvoice.objects.select_related(
            "project", "sow", "milestone", "currency", "accounting_invoice"
        ),
        pk=pk,
        tenant=request.tenant,
    )
    return render(
        request,
        "projects/clientcollaboration/clientinvoice/detail.html",
        {
            "obj": invoice_record,
            "invoice_record": invoice_record,
        },
    )


@login_required
def pci_edit(request, pk):
    invoice_record = get_object_or_404(
        ProjectClientInvoice,
        pk=pk,
        tenant=request.tenant,
    )
    return crud_edit(
        request,
        model=ProjectClientInvoice,
        pk=pk,
        form_class=ProjectClientInvoiceForm,
        template="projects/clientcollaboration/clientinvoice/form.html",
        success_url="projects:pci_list",
        extra_context={"is_edit": True, "obj": invoice_record, "invoice_record": invoice_record},
    )


@login_required
def pci_delete(request, pk):
    return crud_delete(
        request,
        model=ProjectClientInvoice,
        pk=pk,
        success_url="projects:pci_list",
    )


@login_required
@require_POST
def pci_generate_invoice(request, pk):
    pci = get_object_or_404(
        ProjectClientInvoice.objects.select_related("project__client", "currency"),
        pk=pk,
        tenant=request.tenant,
    )
    if pci.status == "invoiced" and pci.accounting_invoice_id:
        messages.warning(request, f"Billing record {pci.number} is already invoiced as {pci.accounting_invoice.number}.")
        return redirect("projects:pci_detail", pk=pk)

    client_party = pci.project.client
    if not client_party:
        messages.error(request, "Cannot generate invoice: project has no associated client party.")
        return redirect("projects:pci_detail", pk=pk)

    with transaction.atomic():
        tax_pct = Decimal("0.00")
        if pci.amount and pci.amount > Decimal("0.00") and pci.tax_amount:
            tax_pct = ((pci.tax_amount / pci.amount) * Decimal("100.00")).quantize(Decimal("0.01"))

        acc_invoice = Invoice.objects.create(
            tenant=request.tenant,
            kind="invoice",
            party=client_party,
            issue_date=pci.billing_date,
            due_date=pci.due_date,
            status="draft",
            currency=pci.currency,
            notes=f"Generated from Project {pci.project.name} (Billing Ref: {pci.number})",
        )
        desc = f"Project Billing: {pci.project.name} ({pci.get_billing_type_display()})"
        if pci.milestone:
            desc += f" - Milestone: {pci.milestone.name}"
        elif pci.sow:
            desc += f" - SOW: {pci.sow.title}"

        InvoiceLine.objects.create(
            invoice=acc_invoice,
            description=desc,
            quantity=Decimal("1.0000"),
            unit_price=pci.amount,
            tax_rate_pct=tax_pct,
        )
        acc_invoice.recalc_totals(save=True)

        pci.accounting_invoice = acc_invoice
        pci.status = "invoiced"
        pci.invoiced_at = timezone.now()
        pci.save()

        write_audit_log(
            request.user,
            pci,
            "bill",
            changes={"status": "invoiced", "accounting_invoice": acc_invoice.number},
        )

    messages.success(request, f"Generated draft customer invoice {acc_invoice.number} successfully.")
    return redirect("projects:pci_detail", pk=pk)
