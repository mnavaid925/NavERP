from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.ContentManagement.ContentBlocks import ContentBlockForm
from apps.ecommerce.models.ContentManagement.ContentBlocks import ContentBlock
from apps.ecommerce.views._common import ecommerce_object


@login_required
def contentblock_list(request):
    qs = (
        ContentBlock.objects.filter(tenant=request.tenant)
        .select_related("media_asset", "target_category", "target_product")
        .order_by("sort_order", "-created_at")
    )

    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(name__icontains=search_query)
            | Q(headline__icontains=search_query)
            | Q(subheadline__icontains=search_query)
            | Q(body_text__icontains=search_query)
            | Q(number__icontains=search_query)
        )

    selected_type = request.GET.get("block_type", "").strip()
    if selected_type:
        qs = qs.filter(block_type=selected_type)

    selected_active = request.GET.get("is_active", "").strip()
    if selected_active == "1":
        qs = qs.filter(is_active=True)
    elif selected_active == "0":
        qs = qs.filter(is_active=False)

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    blocks = paginator.get_page(page_number)

    return render(
        request,
        "ecommerce/content_management/block/list.html",
        {
            "blocks": blocks,
            "block_type_choices": ContentBlock.BLOCK_TYPE_CHOICES,
            "selected_type": selected_type,
            "selected_active": selected_active,
            "search_query": search_query,
        },
    )


@login_required
def contentblock_detail(request, pk):
    block = ecommerce_object(request, ContentBlock, pk)
    return render(
        request,
        "ecommerce/content_management/block/detail.html",
        {"block": block, "content_block": block},
    )


@login_required
def contentblock_create(request):
    if request.method == "POST":
        form = ContentBlockForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            block = form.save()
            write_audit_log(
                request.user,
                block,
                "create",
                {"name": block.name, "block_type": block.block_type, "is_active": block.is_active},
                tenant=request.tenant,
            )
            messages.success(request, f"Content Block '{block.name}' created successfully.")
            return redirect("ecommerce:contentblock_detail", pk=block.pk)
    else:
        form = ContentBlockForm(tenant=request.tenant)

    return render(
        request,
        "ecommerce/content_management/block/form.html",
        {"form": form, "block": None, "content_block": None},
    )


@login_required
def contentblock_edit(request, pk):
    block = ecommerce_object(request, ContentBlock, pk)
    if request.method == "POST":
        form = ContentBlockForm(request.POST, instance=block, tenant=request.tenant)
        if form.is_valid():
            block = form.save()
            write_audit_log(
                request.user,
                block,
                "update",
                {"name": block.name, "block_type": block.block_type},
                tenant=request.tenant,
            )
            messages.success(request, f"Content Block '{block.name}' updated successfully.")
            return redirect("ecommerce:contentblock_detail", pk=block.pk)
    else:
        form = ContentBlockForm(instance=block, tenant=request.tenant)

    return render(
        request,
        "ecommerce/content_management/block/form.html",
        {"form": form, "block": block, "content_block": block},
    )


@login_required
@tenant_admin_required
@require_POST
def contentblock_delete(request, pk):
    block = ecommerce_object(request, ContentBlock, pk)
    name = block.name
    number = block.number
    write_audit_log(
        request.user,
        block,
        "delete",
        {"number": number, "name": name},
        tenant=request.tenant,
    )
    block.delete()
    messages.success(request, f"Content Block '{name}' deleted.")
    return redirect("ecommerce:contentblock_list")
