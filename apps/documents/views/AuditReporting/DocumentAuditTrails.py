import csv
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.documents.forms.AuditReporting.DocumentAuditTrails import DocumentAuditTrailFilterForm
from apps.documents.models.AuditReporting.DocumentAuditTrails import DocumentAuditTrail
from apps.documents.views._common import _csv_safe, safe_parse_date

PAGE_SIZE = 15


@login_required
def audit_trail_list(request):
    """List and search immutable document audit trails with multi-criteria filters."""
    qs = DocumentAuditTrail.objects.filter(tenant=request.tenant).select_related("document", "actor", "version")

    filter_form = DocumentAuditTrailFilterForm(request.GET)
    search_query = request.GET.get("q", "").strip()
    action_type = request.GET.get("action_type", "").strip()
    is_success = request.GET.get("is_success", "").strip()
    date_from = safe_parse_date(request.GET.get("date_from"))
    date_to = safe_parse_date(request.GET.get("date_to"))
    doc_id = request.GET.get("doc_id", "").strip()

    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(document_number_snapshot__icontains=search_query)
            | Q(document_title_snapshot__icontains=search_query)
            | Q(actor_email_snapshot__icontains=search_query)
            | Q(action_type__icontains=search_query)
            | Q(ip_address__icontains=search_query)
            | Q(user_agent__icontains=search_query)
        )

    if action_type:
        qs = qs.filter(action_type=action_type)

    if is_success in ("0", "1"):
        qs = qs.filter(is_success=(is_success == "1"))

    if date_from:
        qs = qs.filter(event_timestamp__date__gte=date_from)

    if date_to:
        qs = qs.filter(event_timestamp__date__lte=date_to)

    if doc_id and doc_id.isdigit():
        qs = qs.filter(document_id=int(doc_id))

    total_count = qs.count()

    # Simple sample chain verification on latest records
    chain_status = "intact"
    latest_entries = list(qs[:10])
    for entry in latest_entries:
        if not entry.verify_hash():
            chain_status = "compromised"
            break

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "audit_trails": page_obj.object_list,
        "page_obj": page_obj,
        "filter_form": filter_form,
        "total_count": total_count,
        "chain_status": chain_status,
        "action_type_choices": DocumentAuditTrail.ACTION_TYPE_CHOICES,
        "result_choices": [("1", "Success"), ("0", "Failed / Blocked")],
        "search_query": search_query,
    }
    return render(request, "documents/audit_reporting/audit_trail/list.html", context)


@login_required
def audit_trail_detail(request, pk):
    """Detailed forensic inspection of a single immutable audit trail entry."""
    audit_entry = get_object_or_404(
        DocumentAuditTrail.objects.select_related("document", "actor", "version"),
        pk=pk,
        tenant=request.tenant,
    )

    chain_valid = audit_entry.verify_hash()

    prev_entry = (
        DocumentAuditTrail.objects.filter(tenant=request.tenant, id__lt=audit_entry.id)
        .order_by("-id")
        .first()
    )
    next_entry = (
        DocumentAuditTrail.objects.filter(tenant=request.tenant, id__gt=audit_entry.id)
        .order_by("id")
        .first()
    )

    context = {
        "audit_entry": audit_entry,
        "chain_valid": chain_valid,
        "prev_entry": prev_entry,
        "next_entry": next_entry,
    }
    return render(request, "documents/audit_reporting/audit_trail/detail.html", context)


@require_POST
@tenant_admin_required
def audit_trail_verify_chain(request):
    """Walk through tenant audit entries sequentially to verify cryptographic chain integrity."""
    entries = (
        DocumentAuditTrail.objects.filter(tenant=request.tenant)
        .select_related("actor", "document")
        .order_by("id")
        .iterator(chunk_size=2000)
    )
    verified_count = 0
    tampered_id = None
    is_valid = True
    expected_prev = "GENESIS_BLOCK_000000000000000000000000000000000000000000000000000000"
    latest_hash = ""

    for entry in entries:
        latest_hash = entry.chain_hash
        # Check prev_hash continuity
        if verified_count > 0 and entry.prev_hash != expected_prev:
            is_valid = False
            tampered_id = entry.id
            break
        # Check own hash calculation
        if not entry.verify_hash():
            is_valid = False
            tampered_id = entry.id
            break
        expected_prev = entry.chain_hash
        verified_count += 1

    write_audit_log(request.user, None, "verify", tenant=request.tenant)

    if request.headers.get("x-requested-with") == "XMLHttpRequest" or request.GET.get("format") == "json":
        return JsonResponse({
            "is_valid": is_valid,
            "verified_count": verified_count,
            "tampered_id": tampered_id,
            "latest_hash": latest_hash,
        })

    if is_valid:
        messages.success(request, f"Cryptographic audit chain fully verified! {verified_count} records intact.")
    else:
        messages.error(request, f"Cryptographic integrity alert! Chain broken at audit record ID #{tampered_id}.")

    return redirect("documents:audit_trail_list")


@login_required
def audit_trail_export_csv(request):
    """Export filtered audit trail records to a CSV file with formula-injection mitigation."""
    qs = DocumentAuditTrail.objects.filter(tenant=request.tenant).select_related("document", "actor")

    search_query = request.GET.get("q", "").strip()
    action_type = request.GET.get("action_type", "").strip()
    is_success = request.GET.get("is_success", "").strip()
    date_from = safe_parse_date(request.GET.get("date_from"))
    date_to = safe_parse_date(request.GET.get("date_to"))

    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(document_number_snapshot__icontains=search_query)
            | Q(document_title_snapshot__icontains=search_query)
            | Q(actor_email_snapshot__icontains=search_query)
            | Q(action_type__icontains=search_query)
        )
    if action_type:
        qs = qs.filter(action_type=action_type)
    if is_success in ("0", "1"):
        qs = qs.filter(is_success=(is_success == "1"))
    if date_from:
        qs = qs.filter(event_timestamp__date__gte=date_from)
    if date_to:
        qs = qs.filter(event_timestamp__date__lte=date_to)

    write_audit_log(request.user, None, "export", tenant=request.tenant)

    response = HttpResponse(content_type="text/csv")
    filename = f"audit_trail_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow([
        "Entry #",
        "Timestamp (UTC)",
        "Action Type",
        "Result",
        "Document #",
        "Document Title",
        "Actor",
        "IP Address",
        "Failure Reason",
        "Chain Hash",
    ])

    for entry in qs.iterator(chunk_size=1000):
        writer.writerow([
            _csv_safe(entry.number),
            _csv_safe(entry.event_timestamp.isoformat() if entry.event_timestamp else ""),
            _csv_safe(entry.get_action_type_display()),
            _csv_safe("Success" if entry.is_success else "Failed/Blocked"),
            _csv_safe(entry.document_number_snapshot or (entry.document.number if entry.document else "")),
            _csv_safe(entry.document_title_snapshot or (entry.document.title if entry.document else "")),
            _csv_safe(entry.actor_email_snapshot or (entry.actor.email if entry.actor else "")),
            _csv_safe(entry.ip_address or ""),
            _csv_safe(entry.failure_reason or ""),
            _csv_safe(entry.chain_hash),
        ])

    return response
