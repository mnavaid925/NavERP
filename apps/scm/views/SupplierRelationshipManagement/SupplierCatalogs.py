"""SCM 4.2 SRM — SupplierCatalog views (parent + item formset)."""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._common import _changed
from apps.scm.views._helpers import _need_tenant, _supplier_parties
from apps.scm.models import SupplierCatalog
from apps.scm.forms import SupplierCatalogForm, SupplierCatalogItemFormSet


@login_required
def catalog_list(request):
    qs = (SupplierCatalog.objects.filter(tenant=request.tenant)
          .select_related("party", "currency")
          .annotate(line_count=Count("items", distinct=True))
          # Count adds a GROUP BY that drops Meta ordering — re-assert it for stable pagination.
          .order_by("-valid_from", "-id"))
    return crud_list(
        request, qs, "scm/srm/catalog/list.html",
        search_fields=["number", "name", "party__name"],
        filters=[("status", "status", False), ("party", "party_id", True)],
        extra_context={
            "status_choices": SupplierCatalog.STATUS_CHOICES,
            "parties": _supplier_parties(request.tenant),
        },
    )


@login_required
def catalog_create(request):
    return _catalog_form(request, instance=None)


@login_required
def catalog_edit(request, pk):
    obj = get_object_or_404(SupplierCatalog, pk=pk, tenant=request.tenant)
    if obj.status == "archived":
        messages.error(request, "An archived catalog can't be edited.")
        return redirect("scm:catalog_detail", pk=pk)
    return _catalog_form(request, instance=obj)


def _catalog_form(request, instance):
    if instance is None and _need_tenant(request):
        return redirect("scm:catalog_list")
    is_edit = instance is not None
    if request.method == "POST":
        form = SupplierCatalogForm(request.POST, instance=instance, tenant=request.tenant)
        formset = SupplierCatalogItemFormSet(request.POST, instance=instance,
                                             form_kwargs={"tenant": request.tenant})
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                catalog = form.save(commit=False)
                catalog.tenant = request.tenant
                catalog.save()
                formset.instance = catalog
                formset.save()
            write_audit_log(request.user, catalog, "update" if is_edit else "create", _changed(form))
            messages.success(request, f"Catalog {catalog.number} saved.")
            return redirect("scm:catalog_detail", pk=catalog.pk)
    else:
        form = SupplierCatalogForm(instance=instance, tenant=request.tenant)
        formset = SupplierCatalogItemFormSet(instance=instance, form_kwargs={"tenant": request.tenant})
    return render(request, "scm/srm/catalog/form.html",
                  {"form": form, "formset": formset, "is_edit": is_edit, "obj": instance})


@login_required
def catalog_detail(request, pk):
    obj = get_object_or_404(SupplierCatalog.objects.select_related("party", "currency"),
                            pk=pk, tenant=request.tenant)
    return render(request, "scm/srm/catalog/detail.html", {
        "obj": obj,
        "items": obj.items.all(),
    })


@login_required
@require_POST
def catalog_delete(request, pk):
    obj = get_object_or_404(SupplierCatalog, pk=pk, tenant=request.tenant)
    if obj.status not in ("draft", "archived"):
        messages.error(request, "Only a draft or archived catalog can be deleted.")
        return redirect("scm:catalog_detail", pk=pk)
    return crud_delete(request, model=SupplierCatalog, pk=pk, success_url="scm:catalog_list")


@login_required
@require_POST
def catalog_activate(request, pk):
    obj = get_object_or_404(SupplierCatalog, pk=pk, tenant=request.tenant)
    if obj.status != "draft":
        messages.info(request, "This catalog is not a draft.")
        return redirect("scm:catalog_detail", pk=pk)
    if not obj.items.exists():
        messages.error(request, "Add at least one item before activating.")
        return redirect("scm:catalog_detail", pk=pk)
    obj.status = "active"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "activate"})
    messages.success(request, f"Catalog {obj.number} activated.")
    return redirect("scm:catalog_detail", pk=pk)
