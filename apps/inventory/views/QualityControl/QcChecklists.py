"""Inventory 5.15 Quality Control (QC) & Inspection — QcChecklist views.

CRUD for checklists and their inline checkpoints (the 5.10 ReturnInspection formset
pattern: the parent form and its child rows save in ONE atomic block, children tenant-
stamped by the view because ``crud_create``/``crud_edit`` only know one form). Rule-style
config masters get admin-gated writes; list/detail stay member-readable with ``is_admin``
hiding affordances.
"""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count

from apps.core.decorators import tenant_admin_required
from apps.inventory.forms import QcChecklistForm, QcChecklistItemFormSet
from apps.inventory.models import QcChecklist
from apps.inventory.views._common import *  # noqa: F401,F403


def _scoped(tenant):
    """Tenant-scoped queryset with the joins every list page renders, plus the
    checkpoint count the list column shows (annotated: no COUNT per row)."""
    return (QcChecklist.objects.filter(tenant=tenant)
            .select_related("item", "vendor")
            .annotate(n_items=Count("checklist_items"))
            .order_by("name", "id"))


@login_required
def qcchecklist_list(request):
    qs = _scoped(request.tenant)

    is_active = request.GET.get("is_active", "").strip()
    if is_active == "active":
        qs = qs.filter(is_active=True)
    elif is_active == "inactive":
        qs = qs.filter(is_active=False)

    scope = request.GET.get("scope", "").strip()
    if scope == "item":
        qs = qs.filter(item__isnull=False)
    elif scope == "vendor":
        qs = qs.filter(vendor__isnull=False)
    elif scope == "workspace":
        qs = qs.filter(item__isnull=True, vendor__isnull=True)

    return crud_list(
        request,
        qs,
        "inventory/qc/qcchecklist/list.html",
        search_fields=["name", "description", "item__sku", "item__name", "vendor__name"],
        filters=(),
        extra_context={
            "is_active_choices": [["active", "Active"], ["inactive", "Inactive"]],
            "is_active": is_active,
            "scope_choices": [["item", "Product-pinned"], ["vendor", "Vendor-pinned"],
                              ["workspace", "Workspace-wide"]],
            "scope": scope,
            "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
        },
    )


@login_required
def qcchecklist_detail(request, pk):
    obj = get_object_or_404(_scoped(request.tenant), pk=pk)
    return render(request, "inventory/qc/qcchecklist/detail.html", {
        "obj": obj,
        "items": obj.checklist_items.all().order_by("sequence", "id"),
        "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
    })


@tenant_admin_required
def qcchecklist_create(request):
    """Create a checklist and its checkpoints in one atomic block."""
    if request.method == "POST":
        form = QcChecklistForm(request.POST, tenant=request.tenant)
        formset = QcChecklistItemFormSet(request.POST, instance=QcChecklist(tenant=request.tenant))
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    checklist = form.save(commit=False)
                    checklist.tenant = request.tenant
                    checklist.save()

                    for item_form in formset:
                        if not item_form.cleaned_data or item_form.cleaned_data.get("DELETE"):
                            continue
                        row = item_form.save(commit=False)
                        row.tenant = request.tenant
                        row.checklist = checklist
                        row.save()

                    write_audit_log(
                        request.user, checklist, "create",
                        {"name": checklist.name, "applies_to": checklist.applies_to},
                    )
                messages.success(request, f"QC Checklist '{checklist.name}' created.")
                return redirect("inventory:qcchecklist_detail", pk=checklist.pk)
            except ValidationError as exc:
                form.add_error(None, "; ".join(exc.messages))
    else:
        form = QcChecklistForm(tenant=request.tenant)
        formset = QcChecklistItemFormSet(instance=QcChecklist(tenant=request.tenant))

    return render(request, "inventory/qc/qcchecklist/form.html", {
        "form": form,
        "formset": formset,
        "is_edit": False,
    })


@tenant_admin_required
def qcchecklist_edit(request, pk):
    """Edit a checklist and its checkpoints. Checklists are config masters — always
    editable (no lifecycle), unlike the stock-touching documents of this sub-module."""
    checklist = get_object_or_404(_scoped(request.tenant), pk=pk)

    if request.method == "POST":
        form = QcChecklistForm(request.POST, instance=checklist, tenant=request.tenant)
        formset = QcChecklistItemFormSet(request.POST, instance=checklist)
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    checklist = form.save()

                    for item_form in formset:
                        if not item_form.cleaned_data:
                            continue
                        if item_form.cleaned_data.get("DELETE"):
                            if item_form.instance.pk:
                                item_form.instance.delete()
                            continue
                        row = item_form.save(commit=False)
                        row.tenant = request.tenant
                        row.checklist = checklist
                        row.save()

                    write_audit_log(
                        request.user, checklist, "update",
                        {"name": checklist.name, "is_active": checklist.is_active},
                    )
                messages.success(request, f"QC Checklist '{checklist.name}' updated.")
                return redirect("inventory:qcchecklist_detail", pk=checklist.pk)
            except ValidationError as exc:
                form.add_error(None, "; ".join(exc.messages))
    else:
        form = QcChecklistForm(instance=checklist, tenant=request.tenant)
        formset = QcChecklistItemFormSet(instance=checklist)

    return render(request, "inventory/qc/qcchecklist/form.html", {
        "form": form,
        "formset": formset,
        "obj": checklist,
        "is_edit": True,
    })


@tenant_admin_required
@require_POST
def qcchecklist_delete(request, pk):
    """Delete a checklist and (CASCADE) its checkpoints."""
    return crud_delete(
        request,
        model=QcChecklist,
        pk=pk,
        success_url="inventory:qcchecklist_list",
    )
