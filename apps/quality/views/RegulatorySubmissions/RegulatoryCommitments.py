import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.models import Party
from apps.core.utils import write_audit_log
from apps.quality.forms.RegulatorySubmissions.RegulatoryCommitments import RegulatoryCommitmentForm
from apps.quality.models.AuditManagement.RegulatoryInspectionHosts import RegulatoryInspectionHost
from apps.quality.models.RegulatorySubmissions.ProductRegistrations import ProductRegistration
from apps.quality.models.RegulatorySubmissions.RegulatoryCommitments import RegulatoryCommitment
from apps.quality.models.RegulatorySubmissions.RegulatorySubmissions import RegulatorySubmission
from apps.quality.views._common import _csv_safe, quality_object, quality_scope

PAGE_SIZE = 15


@login_required
def regulatory_commitment_list(request):
    base_qs = quality_scope(
        RegulatoryCommitment.objects.all(),
        request,
    )

    today = timezone.now().date()
    stats = base_qs.aggregate(
        total=Count("id"),
        open_items=Count("id", filter=Q(status__in=["open", "in_progress"])),
        overdue=Count(
            "id",
            filter=Q(status="overdue") | (Q(status__in=["open", "in_progress"]) & Q(due_date__lt=today)),
        ),
    )
    total_commitments = stats["total"]
    open_count = stats["open_items"]
    overdue_count = stats["overdue"]

    qs = base_qs.select_related(
        "regulatory_agency", "linked_submission", "linked_registration", "linked_inspection", "responsible_owner"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(number__icontains=q)
            | Q(agency_reference_number__icontains=q)
            | Q(commitment_description__icontains=q)
        )

    commitment_type = request.GET.get("commitment_type", "").strip()
    if commitment_type:
        qs = qs.filter(commitment_type=commitment_type)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    regulatory_agency_id = request.GET.get("regulatory_agency", "").strip()
    if regulatory_agency_id.isdigit():
        qs = qs.filter(regulatory_agency_id=int(regulatory_agency_id))

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    agencies = Party.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "page_obj": page_obj,
        "regulatory_commitments": page_obj.object_list,
        "commitment_type_choices": RegulatoryCommitment.COMMITMENT_TYPE_CHOICES,
        "status_choices": RegulatoryCommitment.STATUS_CHOICES,
        "agencies": agencies,
        "total_commitments": total_commitments,
        "open_count": open_count,
        "overdue_count": overdue_count,
        "search_query": q,
    }
    return render(
        request,
        "quality/regulatory_submissions/regulatory_commitment/list.html",
        context,
    )


@login_required
def regulatory_commitment_detail(request, pk):
    commitment = quality_object(
        request,
        RegulatoryCommitment,
        pk,
        select_related=(
            "regulatory_agency",
            "linked_submission",
            "linked_registration",
            "linked_inspection",
            "responsible_owner",
        ),
    )

    context = {
        "regulatory_commitment": commitment,
    }
    return render(
        request,
        "quality/regulatory_submissions/regulatory_commitment/detail.html",
        context,
    )


@login_required
def regulatory_commitment_create(request):
    initial_data = {}
    sub_id = request.GET.get("submission")
    if sub_id and sub_id.isdigit():
        sub = RegulatorySubmission.objects.filter(tenant=request.tenant, pk=int(sub_id)).first()
        if sub:
            initial_data["linked_submission"] = sub
            initial_data["regulatory_agency"] = sub.target_authority

    reg_id = request.GET.get("registration")
    if reg_id and reg_id.isdigit():
        reg = ProductRegistration.objects.filter(tenant=request.tenant, pk=int(reg_id)).first()
        if reg:
            initial_data["linked_registration"] = reg
            initial_data["regulatory_agency"] = reg.regulatory_authority

    insp_id = request.GET.get("inspection")
    if insp_id and insp_id.isdigit():
        insp = RegulatoryInspectionHost.objects.filter(tenant=request.tenant, pk=int(insp_id)).first()
        if insp:
            initial_data["linked_inspection"] = insp
            agency_party = Party.objects.filter(tenant=request.tenant, name__icontains=insp.agency_name).first()
            if agency_party:
                initial_data["regulatory_agency"] = agency_party

    if request.method == "POST":
        form = RegulatoryCommitmentForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            form.save_m2m()
            write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"Regulatory Commitment {obj.number} created successfully.")
            return redirect("quality:regulatory_commitment_detail", pk=obj.pk)
    else:
        form = RegulatoryCommitmentForm(initial=initial_data, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(
        request,
        "quality/regulatory_submissions/regulatory_commitment/form.html",
        context,
    )


@login_required
def regulatory_commitment_edit(request, pk):
    commitment = quality_object(request, RegulatoryCommitment, pk)
    if request.method == "POST":
        form = RegulatoryCommitmentForm(request.POST, instance=commitment, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Regulatory Commitment {obj.number} updated successfully.")
            return redirect("quality:regulatory_commitment_detail", pk=obj.pk)
    else:
        form = RegulatoryCommitmentForm(instance=commitment, tenant=request.tenant)

    context = {
        "form": form,
        "regulatory_commitment": commitment,
        "is_edit": True,
    }
    return render(
        request,
        "quality/regulatory_submissions/regulatory_commitment/form.html",
        context,
    )


@login_required
@require_POST
@tenant_admin_required
def regulatory_commitment_delete(request, pk):
    commitment = quality_object(request, RegulatoryCommitment, pk)
    num = commitment.number
    write_audit_log(request.user, commitment, "delete", tenant=request.tenant)
    commitment.delete()
    messages.success(request, f"Regulatory Commitment {num} was deleted.")
    return redirect("quality:regulatory_commitment_list")


@login_required
def regulatory_commitment_export(request):
    write_audit_log(request.user, RegulatoryCommitment(), "export", tenant=request.tenant)
    qs = (
        quality_scope(RegulatoryCommitment.objects.all(), request)
        .select_related("regulatory_agency", "responsible_owner")
        .defer("commitment_description", "verification_method", "agency_feedback", "notes")
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="regulatory_commitments.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Commitment Number",
        "Title",
        "Commitment Type",
        "Regulatory Agency",
        "Agency Reference Number",
        "Correspondence Date",
        "Responsible Owner",
        "Due Date",
        "Completion Date",
        "Status",
        "Days Remaining",
    ])

    for item in qs.iterator(chunk_size=1000):
        writer.writerow([
            _csv_safe(item.number),
            _csv_safe(item.title),
            _csv_safe(item.get_commitment_type_display()),
            _csv_safe(item.regulatory_agency.name if item.regulatory_agency else ""),
            _csv_safe(item.agency_reference_number),
            _csv_safe(item.correspondence_date),
            _csv_safe(item.responsible_owner.get_full_name() if item.responsible_owner else ""),
            _csv_safe(item.due_date),
            _csv_safe(item.completion_date),
            _csv_safe(item.get_status_display()),
            _csv_safe(item.days_remaining),
        ])

    return response
