"""SCM 4.8 Manufacturing — BillOfMaterials views (the recipe + its component lines)."""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._common import _changed
from apps.scm.views._helpers import _item_qs, _need_tenant
from apps.scm.models import BillOfMaterials, WorkCenter
from apps.scm.forms import BillOfMaterialsForm, BOMLineFormSet

ZERO = Decimal("0")


@login_required
def billofmaterials_list(request):
    qs = (BillOfMaterials.objects.filter(tenant=request.tenant)
          .select_related("item", "uom", "default_work_center")
          .annotate(line_count=Count("lines", distinct=True)))
    return crud_list(
        request, qs, "scm/manufacturing/billofmaterials/list.html",
        search_fields=["number", "name", "version", "notes", "item__sku", "item__name"],
        filters=[("status", "status", False), ("bom_type", "bom_type", False),
                 ("is_default", "is_default", False), ("item", "item_id", True),
                 ("default_work_center", "default_work_center_id", True)],
        extra_context={
            "status_choices": BillOfMaterials.STATUS_CHOICES,
            "type_choices": BillOfMaterials.BOM_TYPE_CHOICES,
            "items": _item_qs(request.tenant),
            "work_centers": WorkCenter.objects.filter(tenant=request.tenant, is_active=True),
        },
    )


@login_required
def billofmaterials_create(request):
    return _billofmaterials_form(request, instance=None)


@login_required
def billofmaterials_edit(request, pk):
    obj = get_object_or_404(BillOfMaterials, pk=pk, tenant=request.tenant)
    return _billofmaterials_form(request, instance=obj)


def _billofmaterials_form(request, instance):
    """Header + component formset saved in ONE transaction (the _load_form pattern).

    The formset must commit with its parent — a recipe that saved its header but lost its lines
    would silently become a BOM that explodes to nothing.
    """
    if instance is None and _need_tenant(request):
        return redirect("scm:billofmaterials_list")
    is_edit = instance is not None
    if request.method == "POST":
        form = BillOfMaterialsForm(request.POST, instance=instance, tenant=request.tenant)
        formset = BOMLineFormSet(request.POST, instance=instance,
                                 form_kwargs={"tenant": request.tenant})
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                bom = form.save(commit=False)
                bom.tenant = request.tenant
                bom.save()
                formset.instance = bom
                formset.save()
            write_audit_log(request.user, bom, "update" if is_edit else "create", _changed(form))
            messages.success(request, f"Bill of materials {bom.number} saved.")
            return redirect("scm:billofmaterials_detail", pk=bom.pk)
    else:
        form = BillOfMaterialsForm(instance=instance, tenant=request.tenant)
        formset = BOMLineFormSet(instance=instance, form_kwargs={"tenant": request.tenant})
    return render(request, "scm/manufacturing/billofmaterials/form.html",
                  {"form": form, "formset": formset, "is_edit": is_edit, "obj": instance})


@login_required
def billofmaterials_detail(request, pk):
    obj = get_object_or_404(
        BillOfMaterials.objects.select_related("item", "uom", "default_work_center"),
        pk=pk, tenant=request.tenant)
    lines = obj.lines.select_related("component", "component__uom", "uom").all()
    # The flattened multi-level view alongside the single-level lines: the recipe as entered vs the
    # raw materials it actually bottoms out in.
    exploded = obj.explode(obj.output_quantity)
    return render(request, "scm/manufacturing/billofmaterials/detail.html", {
        "obj": obj,
        "lines": lines,
        "exploded": exploded,
        "is_multi_level": any(row["level"] > 1 for row in exploded),
        "estimated_unit_cost": obj.estimated_unit_cost(),
        "is_effective_now": obj.is_effective(),
        "work_order_count": obj.work_orders.count(),
    })


@login_required
@require_POST
def billofmaterials_delete(request, pk):
    obj = get_object_or_404(BillOfMaterials, pk=pk, tenant=request.tenant)
    # WorkOrder.bom is SET_NULL, so deleting would silently orphan the link on historical runs
    # rather than error. Refuse it — the run's provenance is worth more than the tidy-up.
    if obj.work_orders.exists():
        messages.error(request, "This BOM has been used by work orders and cannot be deleted — "
                                "mark it obsolete instead.")
        return redirect("scm:billofmaterials_detail", pk=pk)
    return crud_delete(request, model=BillOfMaterials, pk=pk,
                       success_url="scm:billofmaterials_list")
