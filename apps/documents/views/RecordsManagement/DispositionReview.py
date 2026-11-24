from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from apps.documents.models.RecordsManagement.DestructionCertificates import DestructionCertificate
from apps.documents.models.RecordsManagement.RecordDeclarations import RecordDeclaration
from apps.documents.views._common import documents_scope


@login_required
def disposition_review_board(request):
    """Interactive disposition clearance board for records managers and compliance officers."""
    all_declarations = documents_scope(RecordDeclaration.objects.all(), request).select_related(
        "document", "version", "retention_schedule", "declared_by"
    )

    # Records that are cutoff or pending disposition, or due
    today = timezone.now().date()
    due_records = (
        all_declarations.exclude(record_status="disposed")
        .exclude(document__legal_holds__is_active=True)
        .filter(disposition_due_date__isnull=False, disposition_due_date__lte=today)
        .order_by("disposition_due_date")
    )

    # Records currently blocked by active litigation legal holds
    held_records = (
        all_declarations.exclude(record_status="disposed")
        .filter(document__legal_holds__is_active=True)
        .distinct()
        .order_by("-declaration_date")
    )

    # Certificates currently in authorization or execution stages
    pending_certificates = documents_scope(
        DestructionCertificate.objects.filter(status__in=["pending_approval", "authorized"]),
        request,
    ).select_related("record_declaration", "authorized_by")

    due_count = due_records.count()
    held_count = held_records.count()
    pending_count = pending_certificates.count()

    context = {
        "due_records": due_records,
        "held_records": held_records,
        "pending_certificates": pending_certificates,
        "due_count": due_count,
        "held_count": held_count,
        "pending_count": pending_count,
    }
    return render(request, "documents/records_management/disposition_review/board.html", context)
