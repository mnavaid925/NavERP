from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render

from apps.documents.models.StorageRepository.DocumentBatchImports import DocumentBatchImport
from apps.documents.models.StorageRepository.DocumentFolders import DocumentFolder
from apps.documents.models.StorageRepository.DocumentRelationships import DocumentRelationship
from apps.documents.models.StorageRepository.StorageVolumes import StorageVolume


@login_required
def repository_dashboard(request):
    total_folders = DocumentFolder.objects.filter(tenant=request.tenant).count()
    total_volumes = StorageVolume.objects.filter(tenant=request.tenant).count()
    total_relationships = DocumentRelationship.objects.filter(tenant=request.tenant).count()
    total_imports = DocumentBatchImport.objects.filter(tenant=request.tenant).count()

    # Aggregate storage metrics across all volumes
    vol_totals = StorageVolume.objects.filter(tenant=request.tenant).aggregate(
        cap=Sum("max_capacity_bytes"),
        util=Sum("utilized_bytes"),
    )
    total_capacity_bytes = vol_totals["cap"] or 0
    total_utilized_bytes = vol_totals["util"] or 0

    if total_capacity_bytes > 0:
        capacity_utilization_pct = round((total_utilized_bytes / total_capacity_bytes) * 100.0, 2)
    else:
        capacity_utilization_pct = 0.0

    recent_imports = DocumentBatchImport.objects.filter(
        tenant=request.tenant,
    ).select_related("target_folder", "storage_volume", "created_by").order_by("-created_at")[:5]

    volumes = StorageVolume.objects.filter(tenant=request.tenant).order_by("name")
    top_folders = DocumentFolder.objects.filter(
        tenant=request.tenant,
        parent__isnull=True,
    ).select_related("department", "owner").order_by("name")[:6]

    context = {
        "total_folders": total_folders,
        "total_volumes": total_volumes,
        "total_relationships": total_relationships,
        "total_imports": total_imports,
        "total_capacity_bytes": total_capacity_bytes,
        "total_utilized_bytes": total_utilized_bytes,
        "total_capacity_gb": round(total_capacity_bytes / (1024**3), 2),
        "total_utilized_gb": round(total_utilized_bytes / (1024**3), 2),
        "capacity_utilization_pct": capacity_utilization_pct,
        "recent_imports": recent_imports,
        "volumes": volumes,
        "top_folders": top_folders,
    }
    return render(request, "documents/storage_repository/repository_dashboard.html", context)
