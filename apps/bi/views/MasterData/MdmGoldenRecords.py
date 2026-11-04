from decimal import Decimal
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.bi.forms.MasterData.MdmGoldenRecordForms import (
    MdmGoldenRecordForm,
    MdmGoldenRecordMergeForm,
)
from apps.bi.models.MasterData.MdmGoldenRecords import MdmGoldenRecord
from apps.bi.views._common import bi_object, bi_scope
from apps.core.utils import write_audit_log


@login_required
def mdm_golden_record_list(request):
    queryset = (
        bi_scope(MdmGoldenRecord.objects.all(), request)
        .select_related("party", "party_role", "item", "asset", "warehouse_table", "assigned_steward")
    )

    q = request.GET.get("q", "").strip()[:100]
    if q:
        queryset = queryset.filter(
            Q(name__icontains=q)
            | Q(code__icontains=q)
            | Q(number__icontains=q)
            | Q(tax_id__icontains=q)
            | Q(primary_email__icontains=q)
        )

    domain_filter = request.GET.get("domain", "").strip()
    if domain_filter:
        queryset = queryset.filter(domain=domain_filter)

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    trust_tier_filter = request.GET.get("trust_tier", "").strip()
    if trust_tier_filter:
        queryset = queryset.filter(trust_tier=trust_tier_filter)

    all_tenant_records = bi_scope(MdmGoldenRecord.objects.all(), request)
    total_count = all_tenant_records.count()
    gold_count = all_tenant_records.filter(trust_tier="gold").count()
    pending_count = all_tenant_records.filter(status="pending_review").count()
    merged_count = all_tenant_records.filter(status="merged").count()

    paginator = Paginator(queryset.order_by("-created_at"), 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "golden_records": page_obj,
        "domain_choices": MdmGoldenRecord.DOMAIN_CHOICES,
        "status_choices": MdmGoldenRecord.STATUS_CHOICES,
        "trust_tier_choices": MdmGoldenRecord.TRUST_TIER_CHOICES,
        "total_count": total_count,
        "gold_count": gold_count,
        "pending_count": pending_count,
        "merged_count": merged_count,
    }
    return render(request, "bi/master_data/golden_record/list.html", context)


@login_required
def mdm_golden_record_detail(request, pk):
    golden_record = bi_object(
        request,
        MdmGoldenRecord,
        pk,
        select_related=("party", "party_role", "item", "asset", "warehouse_table", "assigned_steward", "merged_into_record"),
    )

    crosswalks = golden_record.source_crosswalks_json
    if isinstance(crosswalks, str):
        try:
            crosswalks = json.loads(crosswalks)
        except Exception:
            crosswalks = []

    attributes_dict = golden_record.golden_attributes_json
    if isinstance(attributes_dict, str):
        try:
            attributes_dict = json.loads(attributes_dict)
        except Exception:
            attributes_dict = {}

    absorbed_records = golden_record.absorbed_records.all().order_by("-created_at")
    hierarchy_nodes = golden_record.hierarchy_nodes.all().order_by("level", "sort_order")
    merge_form = MdmGoldenRecordMergeForm(tenant=request.tenant, primary_record=golden_record)

    context = {
        "golden_record": golden_record,
        "crosswalks": crosswalks,
        "attributes_dict": attributes_dict,
        "absorbed_records": absorbed_records,
        "hierarchy_nodes": hierarchy_nodes,
        "merge_form": merge_form,
    }
    return render(request, "bi/master_data/golden_record/detail.html", context)


@login_required
def mdm_golden_record_create(request):
    if request.method == "POST":
        form = MdmGoldenRecordForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            record = form.save(commit=False)
            record.tenant = request.tenant
            record.save()
            write_audit_log(
                request.user,
                record,
                "create",
                changes=f"Created golden master record {record.number} ({record.name})",
                tenant=request.tenant,
            )
            messages.success(request, f"Golden record '{record.name}' created successfully.")
            return redirect("bi:mdm_golden_record_detail", pk=record.pk)
    else:
        form = MdmGoldenRecordForm(tenant=request.tenant)

    context = {
        "form": form,
        "golden_record": None,
        "is_edit": False,
    }
    return render(request, "bi/master_data/golden_record/form.html", context)


@login_required
def mdm_golden_record_edit(request, pk):
    golden_record = bi_object(request, MdmGoldenRecord, pk)

    if request.method == "POST":
        form = MdmGoldenRecordForm(request.POST, instance=golden_record, tenant=request.tenant)
        if form.is_valid():
            record = form.save()
            write_audit_log(
                request.user,
                record,
                "update",
                changes=f"Updated golden master record {record.number}",
                tenant=request.tenant,
            )
            messages.success(request, f"Golden record '{record.name}' updated successfully.")
            return redirect("bi:mdm_golden_record_detail", pk=record.pk)
    else:
        form = MdmGoldenRecordForm(instance=golden_record, tenant=request.tenant)

    context = {
        "form": form,
        "golden_record": golden_record,
        "is_edit": True,
    }
    return render(request, "bi/master_data/golden_record/form.html", context)


@login_required
@require_POST
def mdm_golden_record_delete(request, pk):
    golden_record = bi_object(request, MdmGoldenRecord, pk)
    if golden_record.absorbed_records.exists():
        messages.error(
            request,
            f"Cannot delete {golden_record.number} because it has absorbed duplicate records. Unmerge them first.",
        )
        return redirect("bi:mdm_golden_record_detail", pk=golden_record.pk)

    record_number = golden_record.number
    record_name = golden_record.name

    write_audit_log(
        request.user,
        golden_record,
        "delete",
        changes=f"Deleted golden master record {record_number} ({record_name})",
        tenant=request.tenant,
    )
    golden_record.delete()
    messages.success(request, f"Golden record {record_number} deleted successfully.")
    return redirect("bi:mdm_golden_record_list")


@login_required
@require_POST
def mdm_golden_record_merge(request, pk):
    primary_record = bi_object(request, MdmGoldenRecord, pk)
    if primary_record.status == "merged":
        messages.error(request, "Cannot merge candidate records into an already absorbed master record.")
        return redirect("bi:mdm_golden_record_detail", pk=primary_record.pk)

    form = MdmGoldenRecordMergeForm(request.tenant, primary_record, request.POST)

    if form.is_valid():
        secondary_record = form.cleaned_data["secondary_record"]
        if secondary_record.status == "merged":
            messages.error(request, "Selected candidate record has already been absorbed.")
            return redirect("bi:mdm_golden_record_detail", pk=primary_record.pk)
        notes = form.cleaned_data.get("stewardship_notes", "")

        with transaction.atomic():
            secondary_record.status = "merged"
            secondary_record.merged_into_record = primary_record
            secondary_record.merged_at = timezone.now()
            if notes:
                secondary_record.stewardship_notes = (
                    f"{secondary_record.stewardship_notes}\n[Merged into {primary_record.number}]: {notes}".strip()
                )
            secondary_record.save()

            # Increment source record count and update primary notes
            primary_record.source_record_count += secondary_record.source_record_count
            if notes:
                primary_record.stewardship_notes = (
                    f"{primary_record.stewardship_notes}\n[Absorbed {secondary_record.number}]: {notes}".strip()
                )
            primary_record.save()

            write_audit_log(
                request.user,
                primary_record,
                "merge",
                changes=f"Merged {secondary_record.number} into {primary_record.number}",
                tenant=request.tenant,
            )

        messages.success(
            request,
            f"Record {secondary_record.number} ({secondary_record.name}) successfully merged into {primary_record.number}.",
        )
    else:
        messages.error(request, "Invalid merge request parameters.")

    return redirect("bi:mdm_golden_record_detail", pk=primary_record.pk)


@login_required
@require_POST
def mdm_golden_record_unmerge(request, pk):
    absorbed_record = bi_object(request, MdmGoldenRecord, pk)
    surviving_record = absorbed_record.merged_into_record

    if not surviving_record:
        messages.warning(request, "Record is not merged into any master record.")
        return redirect("bi:mdm_golden_record_detail", pk=absorbed_record.pk)

    with transaction.atomic():
        absorbed_record.status = "approved"
        absorbed_record.merged_into_record = None
        absorbed_record.merged_at = None
        absorbed_record.stewardship_notes = (
            f"{absorbed_record.stewardship_notes}\n[Unmerged from {surviving_record.number} on {timezone.now().strftime('%Y-%m-%d')} by {request.user.username}]".strip()
        )
        absorbed_record.save()

        if surviving_record.source_record_count > 1:
            surviving_record.source_record_count = max(1, surviving_record.source_record_count - 1)
            surviving_record.save()

        write_audit_log(
            request.user,
            absorbed_record,
            "unmerge",
            changes=f"Unmerged {absorbed_record.number} from {surviving_record.number}",
            tenant=request.tenant,
        )

    messages.success(request, f"Record {absorbed_record.number} successfully unmerged.")
    return redirect("bi:mdm_golden_record_detail", pk=absorbed_record.pk)


@login_required
@require_POST
def mdm_golden_record_approve(request, pk):
    golden_record = bi_object(request, MdmGoldenRecord, pk)
    if golden_record.status == "merged":
        messages.error(request, "Merged records cannot be certified directly. Unmerge the record before approval.")
        return redirect("bi:mdm_golden_record_detail", pk=golden_record.pk)

    golden_record.status = "approved"
    golden_record.reviewed_by = request.user
    golden_record.reviewed_at = timezone.now()
    golden_record.save()

    write_audit_log(
        request.user,
        golden_record,
        "approve",
        changes=f"Approved golden master record {golden_record.number} by {request.user.username}",
        tenant=request.tenant,
    )
    messages.success(request, f"Golden record {golden_record.number} approved as certified master.")
    return redirect("bi:mdm_golden_record_detail", pk=golden_record.pk)
