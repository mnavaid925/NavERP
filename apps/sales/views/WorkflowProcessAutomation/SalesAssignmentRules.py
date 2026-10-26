"""Sales 8.17 — SalesAssignmentRule views."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.crud import as_db_int, paginate
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.crm.models import Territory
from apps.sales.forms.WorkflowProcessAutomation.SalesAssignmentRules import (
    SalesAssignmentRuleForm,
)
from apps.sales.models.WorkflowProcessAutomation.SalesAssignmentRules import (
    SalesAssignmentRule,
)

# NOTE (contract §3.2): no owner-assignment resolution ships this pass — the register + CRUD
# only. For `lead` targets the future resolver MUST delegate to 8.1's LeadRoutingRule decision
# path (apps.sales.services.route_lead) and must NEVER create a second lead-owner decision.


@login_required
def sales_assignment_rule_list(request):
    tenant = request.tenant
    qs = SalesAssignmentRule.objects.filter(tenant=tenant).select_related(
        "default_owner", "territory", "last_assigned_owner"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(number__icontains=q))

    target_entity = request.GET.get("target_entity", "").strip()
    if target_entity in {value for value, _ in SalesAssignmentRule.TARGET_ENTITY_CHOICES}:
        qs = qs.filter(target_entity=target_entity)

    assignment_mode = request.GET.get("assignment_mode", "").strip()
    if assignment_mode in {value for value, _ in SalesAssignmentRule.ASSIGNMENT_MODE_CHOICES}:
        qs = qs.filter(assignment_mode=assignment_mode)

    is_active = request.GET.get("is_active", "").strip()
    if is_active == "active":
        qs = qs.filter(is_active=True)
    elif is_active == "inactive":
        qs = qs.filter(is_active=False)

    # L11: validate the GET param BEFORE the `_id=` filter — junk must skip, never 500.
    territory_id = as_db_int(request.GET.get("territory"))
    if territory_id is not None:
        qs = qs.filter(territory_id=territory_id)

    page_obj = paginate(request, qs, 15)
    context = {
        "assignment_rules": page_obj.object_list,
        "page_obj": page_obj,
        "target_entity_choices": SalesAssignmentRule.TARGET_ENTITY_CHOICES,
        "assignment_mode_choices": SalesAssignmentRule.ASSIGNMENT_MODE_CHOICES,
        "territories": Territory.objects.filter(tenant=tenant, is_active=True).order_by("name"),
    }
    return render(request, "sales/workflowprocessautomation/salesassignmentrule/list.html", context)


@login_required
def sales_assignment_rule_detail(request, pk):
    assignment_rule = get_object_or_404(
        SalesAssignmentRule.objects.filter(tenant=request.tenant).select_related(
            "default_owner", "fallback_owner", "territory", "last_assigned_owner", "escalate_to"
        ),
        pk=pk,
    )
    context = {
        "assignment_rule": assignment_rule,
        "eligible_owners": list(assignment_rule.eligible_owners.all().order_by("pk")),
    }
    return render(request, "sales/workflowprocessautomation/salesassignmentrule/detail.html", context)


@login_required
@tenant_admin_required
@transaction.atomic
def sales_assignment_rule_create(request):
    tenant = request.tenant
    if request.method == "POST":
        form = SalesAssignmentRuleForm(request.POST, tenant=tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = tenant
            obj.save()
            form.save_m2m()
            write_audit_log(request.user, obj, "create", tenant=tenant)
            messages.success(request, f"Assignment rule '{obj.name}' created.")
            return redirect("sales:sales_assignment_rule_detail", pk=obj.pk)
    else:
        form = SalesAssignmentRuleForm(tenant=tenant)

    context = {
        "form": form,
        "assignment_rule": None,
        "is_edit": False,
    }
    return render(request, "sales/workflowprocessautomation/salesassignmentrule/form.html", context)


@login_required
@tenant_admin_required
@transaction.atomic
def sales_assignment_rule_edit(request, pk):
    tenant = request.tenant
    obj = get_object_or_404(SalesAssignmentRule.objects.filter(tenant=tenant), pk=pk)
    if request.method == "POST":
        form = SalesAssignmentRuleForm(request.POST, instance=obj, tenant=tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.save()
            form.save_m2m()
            write_audit_log(request.user, obj, "update", tenant=tenant)
            messages.success(request, f"Assignment rule '{obj.name}' updated.")
            return redirect("sales:sales_assignment_rule_detail", pk=obj.pk)
    else:
        form = SalesAssignmentRuleForm(instance=obj, tenant=tenant)

    context = {
        "form": form,
        "assignment_rule": obj,
        "is_edit": True,
    }
    return render(request, "sales/workflowprocessautomation/salesassignmentrule/form.html", context)


@login_required
@require_POST
@tenant_admin_required
@transaction.atomic
def sales_assignment_rule_delete(request, pk):
    tenant = request.tenant
    obj = get_object_or_404(SalesAssignmentRule.objects.filter(tenant=tenant), pk=pk)
    name = obj.name
    write_audit_log(request.user, obj, "delete", tenant=tenant)
    obj.delete()
    messages.success(request, f"Assignment rule '{name}' deleted.")
    return redirect("sales:sales_assignment_rule_list")
