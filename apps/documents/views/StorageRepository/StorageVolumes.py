from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.documents.forms.StorageRepository.StorageVolumes import StorageVolumeForm
from apps.documents.models.StorageRepository.StorageVolumes import StorageVolume
from apps.documents.views._common import documents_object, documents_scope


@login_required
def storage_volume_list(request):
    qs = documents_scope(
        StorageVolume.objects.select_related("rollover_volume"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(code__icontains=q)
            | Q(base_path__icontains=q)
            | Q(description__icontains=q)
        )

    backend_type = request.GET.get("backend_type", "").strip()
    if backend_type:
        qs = qs.filter(backend_type=backend_type)

    tier = request.GET.get("tier", "").strip()
    if tier:
        qs = qs.filter(tier=tier)

    total_count = qs.count()

    # Aggregate total capacities
    totals = qs.aggregate(
        total_cap=Sum("max_capacity_bytes"),
        total_util=Sum("utilized_bytes"),
    )
    total_cap_bytes = totals["total_cap"] or 0
    total_util_bytes = totals["total_util"] or 0
    total_capacity_gb = round(total_cap_bytes / (1024**3), 2)
    total_utilized_gb = round(total_util_bytes / (1024**3), 2)

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "volumes": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "backend_type": backend_type,
        "tier": tier,
        "backend_choices": StorageVolume.BACKEND_TYPE_CHOICES,
        "tier_choices": StorageVolume.TIER_CHOICES,
        "total_count": total_count,
        "total_capacity_gb": total_capacity_gb,
        "total_utilized_gb": total_utilized_gb,
    }
    return render(request, "documents/storage_repository/storage_volume/list.html", context)


@login_required
def storage_volume_create(request):
    if request.method == "POST":
        form = StorageVolumeForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            volume = form.save(commit=False)
            volume.tenant = request.tenant
            volume.save()
            write_audit_log(request.user, volume, "create", tenant=request.tenant)
            messages.success(request, f"Storage volume '{volume.name}' created successfully.")
            return redirect("documents:storage_volume_detail", pk=volume.pk)
    else:
        form = StorageVolumeForm(tenant=request.tenant)

    context = {
        "form": form,
        "title": "Create Storage Volume",
    }
    return render(request, "documents/storage_repository/storage_volume/form.html", context)


@login_required
def storage_volume_detail(request, pk):
    volume = documents_object(
        request,
        StorageVolume,
        pk,
        select_related=("rollover_volume",),
    )
    batch_imports = volume.batch_imports.filter(tenant=request.tenant).order_by("-created_at")[:10]
    rollover_sources = volume.overflow_sources.filter(tenant=request.tenant)

    context = {
        "volume": volume,
        "batch_imports": batch_imports,
        "rollover_sources": rollover_sources,
    }
    return render(request, "documents/storage_repository/storage_volume/detail.html", context)


@login_required
def storage_volume_edit(request, pk):
    volume = documents_object(request, StorageVolume, pk)
    if request.method == "POST":
        form = StorageVolumeForm(request.POST, instance=volume, tenant=request.tenant)
        if form.is_valid():
            volume = form.save()
            write_audit_log(request.user, volume, "update", tenant=request.tenant)
            messages.success(request, f"Storage volume '{volume.name}' updated successfully.")
            return redirect("documents:storage_volume_detail", pk=volume.pk)
    else:
        form = StorageVolumeForm(instance=volume, tenant=request.tenant)

    context = {
        "form": form,
        "volume": volume,
        "is_edit": True,
        "title": f"Edit Storage Volume — {volume.name}",
    }
    return render(request, "documents/storage_repository/storage_volume/form.html", context)


@require_POST
@login_required
def storage_volume_delete(request, pk):
    volume = documents_object(request, StorageVolume, pk)
    if volume.is_default:
        messages.error(request, "Default storage volume cannot be deleted. Assign another volume as default first.")
        return redirect("documents:storage_volume_detail", pk=volume.pk)

    name = volume.name
    write_audit_log(request.user, volume, "delete", tenant=request.tenant)
    volume.delete()
    messages.success(request, f"Storage volume '{name}' deleted successfully.")
    return redirect("documents:storage_volume_list")
