"""Procurement 6.9 Catalog Management — CatalogUploadBatch views.

The upload register, the upload/edit form, the batch detail (counters + error log) and the
guarded lifecycle: validate (parse + stage), publish, reject — each a POST-only verb with an
audit entry, mirroring the RfxEvent lifecycle pattern.
"""
from django.db.models import Count, Q

from apps.core.models import Party
from apps.procurement.forms.CatalogManagement.UploadBatches import CatalogUploadBatchForm
from apps.procurement.models.CatalogManagement.UploadBatches import CatalogUploadBatch
from apps.procurement.views._common import *  # noqa: F401,F403


# -- register + form ------------------------------------------------------------------------------


@login_required
def catalog_upload_list(request):
    qs = (CatalogUploadBatch.objects.filter(tenant=request.tenant)
          .select_related("party", "validated_by"))
    stats = CatalogUploadBatch.objects.filter(tenant=request.tenant).aggregate(
        received=Count("pk", filter=Q(status="received")),
        validated=Count("pk", filter=Q(status="validated")),
        published=Count("pk", filter=Q(status="published")),
    )
    return crud_list(
        request, qs, "procurement/catalogmanagement/uploadbatch/list.html",
        search_fields=["number", "original_filename", "notes"],
        filters=[("status", "status", False), ("party", "party_id", True)],
        extra_context={
            "status_choices": CatalogUploadBatch.STATUS_CHOICES,
            "party_choices": Party.objects.filter(tenant=request.tenant).order_by("name"),
            "stats": stats,
        },
    )


@login_required
def catalog_upload_detail(request, pk):
    obj = get_object_or_404(
        CatalogUploadBatch.objects.select_related("party", "validated_by"),
        pk=pk, tenant=request.tenant,
    )
    return render(request, "procurement/catalogmanagement/uploadbatch/detail.html", {"obj": obj})


@login_required
def catalog_upload_create(request):
    return _batch_form(request, instance=None)


@login_required
def catalog_upload_edit(request, pk):
    obj = get_object_or_404(CatalogUploadBatch, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, f"Batch {obj.number} is {obj.get_status_display().lower()} "
                                f"— only received batches can be edited.")
        return redirect("procurement:catalog_upload_detail", pk=obj.pk)
    return _batch_form(request, instance=obj)


def _batch_form(request, instance):
    if instance is None and request.tenant is None:
        messages.error(request, "Select a tenant workspace before uploading catalogs.")
        return redirect("dashboard:home")
    is_edit = instance is not None
    if request.method == "POST":
        # request.FILES flows through the form — the file field is the point of this screen.
        form = CatalogUploadBatchForm(request.POST, request.FILES, instance=instance,
                                      tenant=request.tenant)
        if form.is_valid():
            batch = form.save(commit=False)
            batch.tenant = request.tenant
            batch.save()
            write_audit_log(request.user, batch, "update" if is_edit else "create")
            messages.success(request, f"Catalog upload {batch.number} saved.")
            return redirect("procurement:catalog_upload_detail", pk=batch.pk)
    else:
        form = CatalogUploadBatchForm(instance=instance, tenant=request.tenant)
    return render(request, "procurement/catalogmanagement/uploadbatch/form.html",
                  {"form": form, "is_edit": is_edit, "obj": instance})


@login_required
@require_POST
def catalog_upload_delete(request, pk):
    # No pre-fetch: crud_delete re-fetches the row itself (a prior get_object_or_404 here
    # was a dead query).
    return crud_delete(request, model=CatalogUploadBatch, pk=pk,
                       success_url="procurement:catalog_upload_list")


# -- lifecycle ------------------------------------------------------------------------------------


@tenant_admin_required
@require_POST
def catalog_upload_validate(request, pk):
    obj = get_object_or_404(CatalogUploadBatch, pk=pk, tenant=request.tenant)
    ok, result = obj.validate_and_stage(request.user)
    if ok:
        write_audit_log(request.user, obj, "validate")
        messages.success(request, f"{obj.number} validated — {result} catalog item(s) staged "
                                  f"for approval, {obj.rows_rejected} row(s) rejected.")
    else:
        messages.error(request, f"Validation failed: {result}")
    return redirect("procurement:catalog_upload_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def catalog_upload_publish(request, pk):
    obj = get_object_or_404(CatalogUploadBatch, pk=pk, tenant=request.tenant)
    if obj.publish():
        write_audit_log(request.user, obj, "publish")
        messages.success(request, f"{obj.number} published — staged items are confirmed live "
                                  f"catalog entries.")
    else:
        messages.error(request, "Only validated batches can be published.")
    return redirect("procurement:catalog_upload_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def catalog_upload_reject(request, pk):
    obj = get_object_or_404(CatalogUploadBatch, pk=pk, tenant=request.tenant)
    if obj.reject():
        write_audit_log(request.user, obj, "reject")
        messages.success(request, f"{obj.number} rejected.")
    else:
        messages.error(request, "Only received or validated batches can be rejected.")
    return redirect("procurement:catalog_upload_detail", pk=obj.pk)
