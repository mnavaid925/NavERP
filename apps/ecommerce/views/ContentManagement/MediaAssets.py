from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.ContentManagement.MediaAssets import MediaAssetForm
from apps.ecommerce.models.ContentManagement.MediaAssets import MediaAsset
from apps.ecommerce.views._common import ecommerce_object


@login_required
def mediaasset_list(request):
    qs = MediaAsset.objects.filter(tenant=request.tenant).select_related("uploaded_by")

    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(title__icontains=search_query)
            | Q(alt_text__icontains=search_query)
            | Q(caption__icontains=search_query)
            | Q(number__icontains=search_query)
            | Q(mime_type__icontains=search_query)
        )

    selected_type = request.GET.get("media_type", "").strip()
    if selected_type:
        qs = qs.filter(media_type=selected_type)

    selected_folder = request.GET.get("folder_category", "").strip()
    if selected_folder:
        qs = qs.filter(folder_category=selected_folder)

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    assets = paginator.get_page(page_number)

    return render(
        request,
        "ecommerce/content_management/media/list.html",
        {
            "assets": assets,
            "media_type_choices": MediaAsset.MEDIA_TYPE_CHOICES,
            "folder_choices": MediaAsset.FOLDER_CHOICES,
            "selected_type": selected_type,
            "selected_folder": selected_folder,
            "search_query": search_query,
        },
    )


@login_required
def mediaasset_detail(request, pk):
    asset = ecommerce_object(request, MediaAsset, pk, select_related=("uploaded_by",))
    return render(
        request,
        "ecommerce/content_management/media/detail.html",
        {"asset": asset},
    )


@login_required
def mediaasset_create(request):
    if request.method == "POST":
        form = MediaAssetForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            asset = form.save(commit=False)
            if not asset.uploaded_by:
                asset.uploaded_by = request.user
            asset.save()
            write_audit_log(
                request.user,
                asset,
                "create",
                {"title": asset.title, "media_type": asset.media_type, "folder": asset.folder_category},
                tenant=request.tenant,
            )
            messages.success(request, f"Media Asset '{asset.title}' cataloged successfully.")
            return redirect("ecommerce:mediaasset_detail", pk=asset.pk)
    else:
        form = MediaAssetForm(tenant=request.tenant)

    return render(
        request,
        "ecommerce/content_management/media/form.html",
        {"form": form, "asset": None},
    )


@login_required
def mediaasset_edit(request, pk):
    asset = ecommerce_object(request, MediaAsset, pk)
    if request.method == "POST":
        form = MediaAssetForm(request.POST, instance=asset, tenant=request.tenant)
        if form.is_valid():
            asset = form.save()
            write_audit_log(
                request.user,
                asset,
                "update",
                {"title": asset.title, "media_type": asset.media_type},
                tenant=request.tenant,
            )
            messages.success(request, f"Media Asset '{asset.title}' updated successfully.")
            return redirect("ecommerce:mediaasset_detail", pk=asset.pk)
    else:
        form = MediaAssetForm(instance=asset, tenant=request.tenant)

    return render(
        request,
        "ecommerce/content_management/media/form.html",
        {"form": form, "asset": asset},
    )


@login_required
@tenant_admin_required
@require_POST
def mediaasset_delete(request, pk):
    asset = ecommerce_object(request, MediaAsset, pk)
    title = asset.title
    number = asset.number
    write_audit_log(
        request.user,
        asset,
        "delete",
        {"number": number, "title": title},
        tenant=request.tenant,
    )
    asset.delete()
    messages.success(request, f"Media Asset '{title}' deleted.")
    return redirect("ecommerce:mediaasset_list")
