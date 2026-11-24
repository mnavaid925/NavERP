from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.documents.forms.RecordsManagement.RecordDeclarations import RecordDeclarationForm
from apps.documents.models.RecordsManagement.DocumentLegalHolds import DocumentLegalHold
from apps.documents.models.RecordsManagement.RecordDeclarations import RecordDeclaration
from apps.documents.models.RecordsManagement.RetentionSchedules import RetentionSchedule
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.views._common import documents_object, documents_scope


@login_required
def record_declaration_list(request):
    qs = documents_scope(RecordDeclaration.objects.all(), request).select_related(
        "document", "version", "retention_schedule", "declared_by"
    )

    hold_subquery = DocumentLegalHold.objects.filter(
        tenant=request.tenant,
        document=OuterRef("document_id"),
        is_active=True,
    )
    qs = qs.annotate(has_active_hold=Exists(hold_subquery))

    current_status = request.GET.get("status", "").strip()
    if current_status:
        qs = qs.filter(record_status=current_status)

    current_schedule = request.GET.get("schedule", "").strip()
    if current_schedule.isdigit():
        qs = qs.filter(retention_schedule_id=int(current_schedule))

    current_vital = request.GET.get("vital", "").strip()
    if current_vital == "yes":
        qs = qs.filter(is_vital_record=True)
    elif current_vital == "no":
        qs = qs.filter(is_vital_record=False)

    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(number__icontains=query)
            | Q(document__title__icontains=query)
            | Q(document__number__icontains=query)
            | Q(retention_schedule__code__icontains=query)
            | Q(retention_schedule__name__icontains=query)
            | Q(notes__icontains=query)
        )

    qs = qs.order_by("-declaration_date")
    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    schedules = RetentionSchedule.objects.filter(tenant=request.tenant).order_by("code")

    context = {
        "declarations": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "status_choices": RecordDeclaration.RECORD_STATUS_CHOICES,
        "schedules": schedules,
        "current_status": current_status,
        "current_schedule": current_schedule,
        "current_vital": current_vital,
        "query": query,
    }
    return render(request, "documents/records_management/record_declaration/list.html", context)


@login_required
def record_declaration_detail(request, pk):
    declaration = documents_object(
        request,
        RecordDeclaration,
        pk,
        select_related=("document", "version", "retention_schedule", "declared_by"),
    )
    active_holds = declaration.document.legal_holds.filter(tenant=request.tenant, is_active=True).select_related(
        "placed_by", "custodian"
    )
    certificates = declaration.destruction_certificates.filter(tenant=request.tenant).select_related(
        "authorized_by", "executed_by"
    )

    context = {
        "declaration": declaration,
        "active_holds": active_holds,
        "certificates": certificates,
    }
    return render(request, "documents/records_management/record_declaration/detail.html", context)


@login_required
def record_declaration_create(request):
    initial = {}
    schedule_id = request.GET.get("schedule", "").strip()
    if schedule_id.isdigit():
        schedule = RetentionSchedule.objects.filter(tenant=request.tenant, pk=int(schedule_id)).first()
        if schedule:
            initial["retention_schedule"] = schedule

    document_id = request.GET.get("document", "").strip()
    if document_id.isdigit():
        doc = Document.objects.filter(tenant=request.tenant, pk=int(document_id)).first()
        if doc:
            initial["document"] = doc
            if hasattr(doc, "current_version") and doc.current_version:
                initial["version"] = doc.current_version

    if request.method == "POST":
        form = RecordDeclarationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            declaration = form.save(commit=False)
            declaration.tenant = request.tenant
            declaration.declared_by = request.user
            declaration.save()
            write_audit_log(request.user, declaration, "declare", tenant=request.tenant)
            messages.success(request, f"Document '{declaration.document.title}' declared as official record {declaration.number}.")
            return redirect("documents:record_declaration_detail", pk=declaration.pk)
    else:
        form = RecordDeclarationForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "declaration": None,
        "is_edit": False,
    }
    return render(request, "documents/records_management/record_declaration/form.html", context)


@login_required
def record_declaration_edit(request, pk):
    declaration = documents_object(request, RecordDeclaration, pk)
    if declaration.is_locked or declaration.retention_schedule.retention_mode == "regulatory_worm":
        messages.error(request, "Cannot edit an immutable record under WORM compliance lock.")
        return redirect("documents:record_declaration_detail", pk=declaration.pk)
    if declaration.is_under_legal_hold:
        messages.error(request, "Cannot edit a record currently frozen under an active legal hold.")
        return redirect("documents:record_declaration_detail", pk=declaration.pk)

    if request.method == "POST":
        form = RecordDeclarationForm(request.POST, instance=declaration, tenant=request.tenant)
        if form.is_valid():
            declaration = form.save()
            write_audit_log(request.user, declaration, "update", tenant=request.tenant)
            messages.success(request, f"Record declaration {declaration.number} updated.")
            return redirect("documents:record_declaration_detail", pk=declaration.pk)
    else:
        form = RecordDeclarationForm(instance=declaration, tenant=request.tenant)

    context = {
        "form": form,
        "declaration": declaration,
        "is_edit": True,
    }
    return render(request, "documents/records_management/record_declaration/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def record_declaration_delete(request, pk):
    declaration = documents_object(request, RecordDeclaration, pk)
    if declaration.is_locked and declaration.retention_schedule.retention_mode == "regulatory_worm":
        messages.error(
            request,
            "Cannot delete a declared Regulatory WORM record. It must be disposed via an authorized Destruction Certificate.",
        )
        return redirect("documents:record_declaration_detail", pk=declaration.pk)

    if declaration.is_under_legal_hold:
        messages.error(request, "Cannot delete record while an active legal hold is placed on the document.")
        return redirect("documents:record_declaration_detail", pk=declaration.pk)

    num = declaration.number
    write_audit_log(request.user, declaration, "delete", tenant=request.tenant)
    declaration.delete()
    messages.success(request, f"Record declaration {num} was deleted.")
    return redirect("documents:record_declaration_list")


@login_required
@require_POST
def record_declaration_trigger_cutoff(request, pk):
    declaration = documents_object(request, RecordDeclaration, pk)
    declaration.trigger_cutoff()
    write_audit_log(request.user, declaration, "cutoff", tenant=request.tenant)
    messages.success(request, f"Cutoff milestone triggered for record {declaration.number}. Retention clock started.")
    return redirect("documents:record_declaration_detail", pk=declaration.pk)
