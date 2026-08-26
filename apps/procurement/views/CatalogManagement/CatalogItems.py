"""Procurement 6.9 Catalog Management — CatalogItem views.

The catalogue register (search + status/source/supplier/preferred filters + one-aggregate
stats), the detail page with its price-tier table and guarded approval lifecycle
(submit / approve / reject / block), and the hand-rolled create/edit form following the
RfxManagement ``_event_form`` precedent. Decisions (approve/reject/block) are tenant-admin
verbs; any member may propose (submit) and view.
"""
from django.db.models import Count, Q

from apps.core.crud import crud_delete, crud_list
from apps.core.models import Party

from apps.procurement.forms.CatalogManagement.CatalogItems import CatalogItemForm
from apps.procurement.models.CatalogManagement.CatalogItems import CatalogItem
from apps.procurement.views._common import *  # noqa: F401,F403


# -- register -------------------------------------------------------------------------------------


@login_required
def catalog_item_list(request):
    qs = (CatalogItem.objects.filter(tenant=request.tenant)
          .select_related("item", "supplier", "uom", "currency")
          .order_by("-created_at", "-id"))
    stats = CatalogItem.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        pending=Count("id", filter=Q(status="pending_approval")),
        approved=Count("id", filter=Q(status="approved")),
        blocked=Count("id", filter=Q(status="blocked")),
    )
    return crud_list(
        request, qs, "procurement/catalogmanagement/catalogitem/list.html",
        search_fields=["number", "name", "supplier_part_no", "category_text"],
        filters=[("status", "status", False),
                 ("source_type", "source_type", False),
                 ("supplier", "supplier_id", True),
                 ("is_preferred", "is_preferred", False)],
        extra_context={
            "status_choices": CatalogItem.STATUS_CHOICES,
            "source_choices": CatalogItem.SOURCE_TYPES,
            "supplier_choices": Party.objects.filter(tenant=request.tenant).order_by("name"),
            "stats": stats,
        },
    )


@login_required
def catalog_item_detail(request, pk):
    obj = get_object_or_404(
        CatalogItem.objects.select_related(
            "item", "supplier", "contract", "uom", "currency",
            "created_by", "submitted_by", "approved_by"),
        pk=pk, tenant=request.tenant,
    )
    tiers = obj.price_tiers.select_related("contract").order_by("min_quantity")
    return render(request, "procurement/catalogmanagement/catalogitem/detail.html",
                  {"obj": obj, "tiers": tiers})


# -- create / edit (hand-rolled, RfxEvents._event_form precedent) ----------------------------------


@login_required
def catalog_item_create(request):
    return _item_form(request, instance=None)


@login_required
def catalog_item_edit(request, pk):
    obj = get_object_or_404(CatalogItem, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(
            request,
            f"{obj.number} is {obj.get_status_display()} — only draft or rejected entries "
            f"can be edited.")
        return redirect("procurement:catalog_item_detail", pk=obj.pk)
    return _item_form(request, instance=obj)


def _item_form(request, instance):
    if instance is None and request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating catalog items.")
        return redirect("dashboard:home")
    is_edit = instance is not None
    if request.method == "POST":
        form = CatalogItemForm(request.POST, request.FILES, instance=instance,
                               tenant=request.tenant)
        if form.is_valid():
            item = form.save(commit=False)
            item.tenant = request.tenant
            if not is_edit:
                item.created_by = request.user
            item.save()
            write_audit_log(request.user, item, "update" if is_edit else "create")
            messages.success(request, f"Catalog entry {item.number} saved.")
            return redirect("procurement:catalog_item_detail", pk=item.pk)
    else:
        form = CatalogItemForm(instance=instance, tenant=request.tenant)
    return render(request, "procurement/catalogmanagement/catalogitem/form.html",
                  {"form": form, "is_edit": is_edit, "obj": instance})


@login_required
@require_POST
def catalog_item_delete(request, pk):
    return crud_delete(request, model=CatalogItem, pk=pk,
                       success_url="procurement:catalog_item_list")


# -- lifecycle ------------------------------------------------------------------------------------


@login_required
@require_POST
def catalog_item_submit(request, pk):
    # Proposing stays open to every member — maker-checker needs makers.
    obj = get_object_or_404(CatalogItem, pk=pk, tenant=request.tenant)
    if obj.submit(request.user):
        write_audit_log(request.user, obj, "submit")
        messages.success(request, f"{obj.number} submitted for approval.")
    else:
        messages.error(request, "Only draft or rejected entries can be submitted.")
    return redirect("procurement:catalog_item_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def catalog_item_approve(request, pk):
    obj = get_object_or_404(CatalogItem, pk=pk, tenant=request.tenant)
    if obj.approve(request.user):
        write_audit_log(request.user, obj, "approve")
        messages.success(request, f"{obj.number} approved — it can now be picked onto "
                                  f"requisitions while active.")
    else:
        messages.error(request, "Only entries pending approval can be approved.")
    return redirect("procurement:catalog_item_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def catalog_item_reject(request, pk):
    obj = get_object_or_404(CatalogItem, pk=pk, tenant=request.tenant)
    if obj.reject(request.user, request.POST.get("reason", "")):
        write_audit_log(request.user, obj, "reject")
        messages.success(request, f"{obj.number} rejected — it returns to the maintainer "
                                  f"as editable.")
    else:
        messages.error(request, "Only entries pending approval can be rejected.")
    return redirect("procurement:catalog_item_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def catalog_item_block(request, pk):
    obj = get_object_or_404(CatalogItem, pk=pk, tenant=request.tenant)
    if obj.block():
        write_audit_log(request.user, obj, "block")
        messages.success(request, f"{obj.number} blocked — it can no longer be picked onto "
                                  f"purchase documents.")
    else:
        messages.error(request, "Only approved entries can be blocked.")
    return redirect("procurement:catalog_item_detail", pk=obj.pk)
