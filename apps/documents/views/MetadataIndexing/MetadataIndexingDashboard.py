from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.documents.models.MetadataIndexing.DocumentMetadataValues import DocumentMetadataValue
from apps.documents.models.MetadataIndexing.DocumentOcrJobs import DocumentOcrJob
from apps.documents.models.MetadataIndexing.MetadataSchemas import MetadataSchema
from apps.documents.models.MetadataIndexing.TaxonomyTerms import TaxonomyTerm


@login_required
def metadata_indexing_dashboard(request):
    """
    Sub-module 13.5: Central management dashboard for Document Metadata & Indexing.
    Aggregates schema statistics, taxonomy depth, OCR queue processing, and validation health.
    """
    tenant = request.tenant

    total_schemas = MetadataSchema.objects.filter(tenant=tenant).count()
    total_values = DocumentMetadataValue.objects.filter(tenant=tenant).count()
    total_terms = TaxonomyTerm.objects.filter(tenant=tenant).count()
    total_ocr_jobs = DocumentOcrJob.objects.filter(tenant=tenant).count()
    pending_ocr_count = DocumentOcrJob.objects.filter(tenant=tenant, status__in=["queued", "processing"]).count()

    recent_schemas = MetadataSchema.objects.filter(tenant=tenant).order_by("-created_at")[:5]
    recent_jobs = DocumentOcrJob.objects.filter(tenant=tenant).select_related("document").order_by("-created_at")[:5]
    recent_terms = TaxonomyTerm.objects.filter(tenant=tenant).order_by("-created_at")[:6]

    context = {
        "total_schemas": total_schemas,
        "total_values": total_values,
        "total_terms": total_terms,
        "total_ocr_jobs": total_ocr_jobs,
        "pending_ocr_count": pending_ocr_count,
        "recent_schemas": recent_schemas,
        "recent_jobs": recent_jobs,
        "recent_terms": recent_terms,
    }
    return render(request, "documents/metadata_indexing/metadata_indexing_dashboard.html", context)
