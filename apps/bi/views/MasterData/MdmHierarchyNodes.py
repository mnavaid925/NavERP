from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.MasterData.MdmHierarchyNodeForms import MdmHierarchyNodeForm
from apps.bi.models.MasterData.MdmHierarchyNodes import MdmHierarchyNode
from apps.bi.views._common import bi_object, bi_scope
from apps.core.utils import write_audit_log


@login_required
def mdm_hierarchy_node_list(request):
    queryset = (
        bi_scope(MdmHierarchyNode.objects.all(), request)
        .select_related("parent", "golden_record", "party", "org_unit", "item_category")
    )

    q = request.GET.get("q", "").strip()[:100]
    if q:
        queryset = queryset.filter(
            Q(name__icontains=q)
            | Q(code__icontains=q)
            | Q(number__icontains=q)
            | Q(relationship_kind__icontains=q)
            | Q(description__icontains=q)
        )

    hierarchy_type_filter = request.GET.get("hierarchy_type", "").strip()
    if hierarchy_type_filter:
        queryset = queryset.filter(hierarchy_type=hierarchy_type_filter)

    level_filter = request.GET.get("level", "").strip()
    if level_filter and level_filter.isdigit():
        queryset = queryset.filter(level=int(level_filter))

    all_tenant_nodes = bi_scope(MdmHierarchyNode.objects.all(), request)
    total_count = all_tenant_nodes.count()
    root_nodes_count = all_tenant_nodes.filter(parent__isnull=True).count()

    paginator = Paginator(queryset.order_by("hierarchy_type", "level", "sort_order", "name"), 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "hierarchy_nodes": page_obj,
        "hierarchy_type_choices": MdmHierarchyNode.HIERARCHY_TYPE_CHOICES,
        "total_count": total_count,
        "root_nodes_count": root_nodes_count,
    }
    return render(request, "bi/master_data/hierarchy_node/list.html", context)


@login_required
def mdm_hierarchy_node_detail(request, pk):
    node = bi_object(
        request,
        MdmHierarchyNode,
        pk,
        select_related=("parent", "golden_record", "party", "org_unit", "item_category"),
    )
    children = node.children.all().order_by("sort_order", "name")

    # Ancestors extraction from path
    ancestor_ids = [int(p) for p in node.path.strip("/").split("/") if p.isdigit() and int(p) != node.pk]
    ancestors = (
        MdmHierarchyNode.objects.filter(tenant=request.tenant, pk__in=ancestor_ids)
        .order_by("level")
    )

    context = {
        "node": node,
        "children": children,
        "ancestors": ancestors,
    }
    return render(request, "bi/master_data/hierarchy_node/detail.html", context)


@login_required
def mdm_hierarchy_node_create(request):
    if request.method == "POST":
        form = MdmHierarchyNodeForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            node = form.save(commit=False)
            node.tenant = request.tenant
            node.save()
            write_audit_log(
                request=request,
                action="create",
                instance=node,
                changes=f"Created hierarchy node {node.number} ({node.name})",
            )
            messages.success(request, f"Hierarchy node '{node.name}' created successfully.")
            return redirect("bi:mdm_hierarchy_node_detail", pk=node.pk)
    else:
        form = MdmHierarchyNodeForm(tenant=request.tenant)

    context = {
        "form": form,
        "node": None,
        "is_edit": False,
    }
    return render(request, "bi/master_data/hierarchy_node/form.html", context)


@login_required
def mdm_hierarchy_node_edit(request, pk):
    node = bi_object(request, MdmHierarchyNode, pk)

    if request.method == "POST":
        form = MdmHierarchyNodeForm(request.POST, instance=node, tenant=request.tenant)
        if form.is_valid():
            saved_node = form.save()
            write_audit_log(
                request=request,
                action="update",
                instance=saved_node,
                changes=f"Updated hierarchy node {saved_node.number}",
            )
            messages.success(request, f"Hierarchy node '{saved_node.name}' updated successfully.")
            return redirect("bi:mdm_hierarchy_node_detail", pk=saved_node.pk)
    else:
        form = MdmHierarchyNodeForm(instance=node, tenant=request.tenant)

    context = {
        "form": form,
        "node": node,
        "is_edit": True,
    }
    return render(request, "bi/master_data/hierarchy_node/form.html", context)


@login_required
@require_POST
def mdm_hierarchy_node_delete(request, pk):
    node = bi_object(request, MdmHierarchyNode, pk)
    node_number = node.number
    node_name = node.name

    write_audit_log(
        request=request,
        action="delete",
        instance=node,
        changes=f"Deleted hierarchy node {node_number} ({node_name})",
    )
    node.delete()
    messages.success(request, f"Hierarchy node {node_number} deleted successfully.")
    return redirect("bi:mdm_hierarchy_node_list")
