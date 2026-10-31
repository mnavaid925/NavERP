from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.ecommerce.forms.ReviewUgc.VisualUgcMedia import VisualUgcMediaForm
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ReviewUgc.VisualUgcMedia import VisualUgcMedia
from apps.ecommerce.views._common import ecommerce_object


@login_required
def visualugcmedia_list(request):
    qs = VisualUgcMedia.objects.filter(tenant=request.tenant).select_related(
        "tagged_product", "tagged_variant"
    )

    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(caption__icontains=query)
            | Q(uploader_name__icontains=query)
            | Q(uploader_handle__icontains=query)
            | Q(number__icontains=query)
            | Q(tagged_product__name__icontains=query)
        )

    selected_media_type = request.GET.get("media_type", "").strip()
    if selected_media_type:
        qs = qs.filter(media_type=selected_media_type)

    selected_rights = request.GET.get("rights_status", "").strip()
    if selected_rights:
        qs = qs.filter(rights_status=selected_rights)

    selected_product = request.GET.get("product", "").strip()
    if selected_product and selected_product.isdigit():
        qs = qs.filter(tagged_product_id=int(selected_product))

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    products = CatalogProduct.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "media_items": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "media_type_choices": VisualUgcMedia.MEDIA_TYPE_CHOICES,
        "rights_status_choices": VisualUgcMedia.RIGHTS_STATUS_CHOICES,
        "products": products,
        "selected_media_type": selected_media_type,
        "selected_rights": selected_rights,
        "selected_product": selected_product,
        "query": query,
    }
    return render(request, "ecommerce/review_ugc/visual_ugc/list.html", context)


@login_required
def visualugcmedia_detail(request, pk):
    media_item = ecommerce_object(
        request,
        VisualUgcMedia,
        pk,
        select_related=("tagged_product", "tagged_variant"),
    )
    return render(
        request,
        "ecommerce/review_ugc/visual_ugc/detail.html",
        {"media_item": media_item},
    )


@login_required
def visualugcmedia_create(request):
    if request.method == "POST":
        form = VisualUgcMediaForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            media_item = form.save(commit=False)
            media_item.tenant = request.tenant
            media_item.save()
            write_audit_log(
                tenant=request.tenant,
                user=request.user,
                action="create",
                model_name="VisualUgcMedia",
                object_id=media_item.pk,
                changes={"number": media_item.number, "media_type": media_item.media_type},
            )
            messages.success(request, f"Visual UGC asset {media_item.number} created.")
            return redirect("ecommerce:visualugcmedia_detail", pk=media_item.pk)
    else:
        form = VisualUgcMediaForm(tenant=request.tenant)

    return render(
        request,
        "ecommerce/review_ugc/visual_ugc/form.html",
        {"form": form, "media_item": None},
    )


@login_required
def visualugcmedia_edit(request, pk):
    media_item = ecommerce_object(request, VisualUgcMedia, pk)
    if request.method == "POST":
        form = VisualUgcMediaForm(request.POST, instance=media_item, tenant=request.tenant)
        if form.is_valid():
            media_item = form.save()
            write_audit_log(
                tenant=request.tenant,
                user=request.user,
                action="update",
                model_name="VisualUgcMedia",
                object_id=media_item.pk,
                changes={"rights_status": media_item.rights_status, "is_published": media_item.is_published},
            )
            messages.success(request, f"Visual UGC asset {media_item.number} updated.")
            return redirect("ecommerce:visualugcmedia_detail", pk=media_item.pk)
    else:
        form = VisualUgcMediaForm(instance=media_item, tenant=request.tenant)

    return render(
        request,
        "ecommerce/review_ugc/visual_ugc/form.html",
        {"form": form, "media_item": media_item},
    )


@login_required
@require_POST
def visualugcmedia_delete(request, pk):
    media_item = ecommerce_object(request, VisualUgcMedia, pk)
    number = media_item.number
    pk_val = media_item.pk
    media_item.delete()
    write_audit_log(
        tenant=request.tenant,
        user=request.user,
        action="delete",
        model_name="VisualUgcMedia",
        object_id=pk_val,
        changes={"number": number},
    )
    messages.success(request, f"Visual UGC asset {number} deleted.")
    return redirect("ecommerce:visualugcmedia_list")
