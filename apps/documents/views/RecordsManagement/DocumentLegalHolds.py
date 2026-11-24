from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.documents.forms.RecordsManagement.DocumentLegalHolds import DocumentLegalHoldForm, LegalHoldReleaseForm
from apps.documents.models.RecordsManagement.DocumentLegalHolds import DocumentLegalHold
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.views._common import documents_object, documents_scope


@login_required
def legal_hold_list(request):
    qs = documents_scope(DocumentLegalHold.objects.all(), request).select_related(
        "document", "placed_by", "custodian", "core_legal_hold"
    )

    current_reason = request.GET.get("hold_reason", "").strip()
    if current_reason:
        qs = qs.filter(hold_reason=current_reason)

    current_status = request.GET.get("status", "").strip()
    if current_status == "active":
        qs = qs.filter(is_active=True)
    elif current_status == "released":
        qs = qs.filter(is_active=False)

    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(matter_name__icontains=query)
            | Q(matter_number__icontains=query)
            | Q(description__icontains=query)
            | Q(document__title__icontains=query)
            | Q(document__number__icontains=query)
        )

    qs = qs.order_by("-placed_at")
    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "holds": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "reason_choices": DocumentLegalHold.HOLD_REASON_CHOICES,
        "current_reason": current_reason,
        "current_status": current_status,
        "query": query,
    }
    return render(request, "documents/records_management/legal_hold/list.html", context)


@login_required
def legal_hold_detail(request, pk):
    hold = documents_object(
        request,
        DocumentLegalHold,
        pk,
        select_related=("document", "placed_by", "custodian", "released_by", "core_legal_hold"),
    )
    release_form = LegalHoldReleaseForm()

    context = {
        "hold": hold,
        "release_form": release_form,
    }
    return render(request, "documents/records_management/legal_hold/detail.html", context)


@login_required
def legal_hold_create(request):
    initial = {}
    doc_id = request.GET.get("document", "").strip()
    if doc_id.isdigit():
        doc = Document.objects.filter(tenant=request.tenant, pk=int(doc_id)).first()
        if doc:
            initial["document"] = doc

    if request.method == "POST":
        form = DocumentLegalHoldForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            hold = form.save(commit=False)
            hold.tenant = request.tenant
            hold.placed_by = request.user
            hold.save()
            write_audit_log(request.user, hold, "hold", tenant=request.tenant)
            messages.success(request, f"Legal hold placed on document '{hold.document.title}' for matter {hold.matter_number}.")
            return redirect("documents:legal_hold_detail", pk=hold.pk)
    else:
        form = DocumentLegalHoldForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
    }
    return render(request, "documents/records_management/legal_hold/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def legal_hold_release(request, pk):
    hold = documents_object(request, DocumentLegalHold, pk)
    if not hold.is_active:
        messages.info(request, "This legal hold has already been released.")
        return redirect("documents:legal_hold_detail", pk=hold.pk)

    form = LegalHoldReleaseForm(request.POST)
    if form.is_valid():
        justification = form.cleaned_data["release_justification"]
        hold.release_hold(request.user, justification)
        write_audit_log(request.user, hold, "release", tenant=request.tenant)
        messages.success(request, f"Legal hold for matter {hold.matter_number} successfully released.")
    else:
        messages.error(request, "Release justification is mandatory to lift a legal hold.")

    return redirect("documents:legal_hold_detail", pk=hold.pk)


@login_required
@require_POST
def legal_hold_acknowledge(request, pk):
    hold = documents_object(request, DocumentLegalHold, pk)
    hold.acknowledge_hold(request.user)
    write_audit_log(request.user, hold, "update", tenant=request.tenant)
    messages.success(request, f"Custodian acknowledgment recorded for legal hold {hold.number}.")
    return redirect("documents:legal_hold_detail", pk=hold.pk)
