import json

from django.core.exceptions import ValidationError

from apps.accounts.models import User
from apps.core.crud import crud_create, crud_delete, crud_edit, crud_list
from apps.crm.models import Lead, Territory
from apps.sales.forms import LeadRoutingPreviewForm, LeadRoutingRuleForm, LeadRoutingRunForm
from apps.sales.models import LeadRoutingRule
from apps.sales.services import preview_routing, route_lead
from apps.sales.views._common import *


@login_required
def lead_routing_rule_list(request):
    queryset = LeadRoutingRule.objects.filter(tenant=request.tenant).prefetch_related("eligible_owners").select_related("default_owner", "territory", "fallback_owner")
    return crud_list(
        request,
        queryset,
        "sales/leadmanagement/leadroutingrule/list.html",
        search_fields=["name", "description"],
        filters=[("active", "is_active", False), ("assignment_mode", "assignment_mode", False), ("match_mode", "match_mode", False), ("territory", "territory_id", True), ("priority", "priority", True)],
        extra_context={
            "assignment_mode_choices": LeadRoutingRule.ASSIGNMENT_MODE_CHOICES,
            "match_mode_choices": LeadRoutingRule.MATCH_MODE_CHOICES,
            "active_choices": [("True", "Active"), ("False", "Inactive")],
            "territories": Territory.objects.filter(tenant=request.tenant, is_active=True),
            "users": User.objects.filter(tenant=request.tenant, is_active=True),
        },
    )


@tenant_admin_required
def lead_routing_rule_create(request):
    return crud_create(
        request,
        form_class=LeadRoutingRuleForm,
        template="sales/leadmanagement/leadroutingrule/form.html",
        success_url="sales:lead_routing_rule_list",
        extra_context={"territories": Territory.objects.filter(tenant=request.tenant, is_active=True), "users": User.objects.filter(tenant=request.tenant, is_active=True)},
    )


@login_required
def lead_routing_rule_detail(request, pk):
    obj = get_object_or_404(LeadRoutingRule.objects.select_related("default_owner", "territory", "fallback_owner", "last_assigned_owner").prefetch_related("eligible_owners"), pk=pk, tenant=request.tenant)
    form = LeadRoutingPreviewForm(tenant=request.tenant, leads=sales_leads(request))
    result = None
    if request.GET.get("lead"):
        if form.is_valid():
            result = preview_routing(form.cleaned_data["lead"], request.tenant, rule=obj)
    return render(request, "sales/leadmanagement/leadroutingrule/detail.html", {
        "obj": obj,
        "eligible_owners": obj.eligible_owners.all(),
        "leads": sales_leads(request),
        "preview_form": form,
        "preview_result": result,
        "conditions_json": json.dumps(obj.conditions, ensure_ascii=False, indent=2, default=str),
    })


@tenant_admin_required
def lead_routing_rule_edit(request, pk):
    obj = get_object_or_404(LeadRoutingRule, pk=pk, tenant=request.tenant)
    return crud_edit(
        request,
        model=LeadRoutingRule,
        pk=pk,
        form_class=LeadRoutingRuleForm,
        template="sales/leadmanagement/leadroutingrule/form.html",
        success_url="sales:lead_routing_rule_list",
        extra_context={"obj": obj, "territories": Territory.objects.filter(tenant=request.tenant, is_active=True), "users": User.objects.filter(tenant=request.tenant, is_active=True)},
    )


@require_POST
@tenant_admin_required
def lead_routing_rule_delete(request, pk):
    return crud_delete(request, model=LeadRoutingRule, pk=pk, success_url="sales:lead_routing_rule_list")


@require_POST
@tenant_admin_required
def lead_routing_rule_toggle(request, pk):
    obj = get_object_or_404(LeadRoutingRule, pk=pk, tenant=request.tenant)
    obj.is_active = not obj.is_active
    obj.save(update_fields=["is_active", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "toggle_routing"}, tenant=request.tenant)
    messages.success(request, "Routing rule updated.")
    return redirect("sales:lead_routing_rule_detail", pk=obj.pk)


@login_required
def lead_routing_rule_preview(request, pk):
    obj = get_object_or_404(LeadRoutingRule, pk=pk, tenant=request.tenant)
    form = LeadRoutingPreviewForm(request.GET or None, tenant=request.tenant, leads=sales_leads(request))
    result = None
    if request.GET and form.is_valid():
        result = preview_routing(form.cleaned_data["lead"], request.tenant, rule=obj)
    return render(request, "sales/leadmanagement/leadroutingrule/detail.html", {
        "obj": obj,
        "eligible_owners": obj.eligible_owners.all(),
        "leads": sales_leads(request),
        "preview_form": form,
        "preview_result": result,
        "conditions_json": json.dumps(obj.conditions, ensure_ascii=False, indent=2, default=str),
    })


@require_POST
@tenant_admin_required
def lead_routing_rule_run(request, pk):
    rule = get_object_or_404(LeadRoutingRule, pk=pk, tenant=request.tenant)
    form = LeadRoutingRunForm(request.POST, tenant=request.tenant, leads=sales_leads(request))
    if not form.is_valid():
        messages.error(request, "Choose a valid lead for routing.")
        return redirect("sales:lead_routing_rule_detail", pk=rule.pk)
    try:
        result = route_lead(form.cleaned_data["lead"], request.tenant, request.user, rule=rule)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("sales:lead_routing_rule_detail", pk=rule.pk)
    if result.get("changed"):
        messages.success(request, "Lead owner updated.")
    else:
        messages.info(request, result.get("reason", "Lead was not changed."))
    return redirect("sales:lead_routing_rule_detail", pk=rule.pk)
