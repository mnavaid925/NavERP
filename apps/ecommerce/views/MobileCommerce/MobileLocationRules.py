from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.MobileCommerce.MobileLocationRules import MobileLocationRuleForm
from apps.ecommerce.models.MobileCommerce.MobileLocationRules import MobileLocationRule
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def mobilelocationrule_list(request):
    qs = ecommerce_scope(
        MobileLocationRule.objects.all().select_related("fulfillment_center", "linked_promotion"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains(q))
            | Q(store_name__icontains(q))
            | Q(number__icontains(q))
            | Q(fulfillment_center__name__icontains(q))
        )

    selected_type = request.GET.get("rule_type", "").strip()
    if selected_type:
        qs = qs.filter(rule_type=selected_type)

    selected_action = request.GET.get("trigger_action", "").strip()
    if selected_action:
        qs = qs.filter(trigger_action=selected_action)

    selected_status = request.GET.get("is_active", "").strip()
    if selected_status in ("1", "true", "True"):
        qs = qs.filter(is_active=True)
    elif selected_status in ("0", "false", "False"):
        qs = qs.filter(is_active=False)

    base_all = ecommerce_scope(MobileLocationRule.objects.all(), request)
    total_count = base_all.count()
    active_count = base_all.filter(is_active=True).count()

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "location_rules": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "type_choices": MobileLocationRule.RULE_TYPE_CHOICES,
        "action_choices": MobileLocationRule.TRIGGER_ACTION_CHOICES,
        "selected_type": selected_type,
        "selected_action": selected_action,
        "selected_status": selected_status,
        "total_count": total_count,
        "active_count": active_count,
        "q": q,
    }
    return render(request, "ecommerce/mobile/mobile_location_rule/list.html", context)


@login_required
def mobilelocationrule_detail(request, pk):
    rule = ecommerce_object(
        request,
        MobileLocationRule,
        pk,
        select_related=("fulfillment_center", "linked_promotion"),
    )
    context = {
        "location_rule": rule,
        "object": rule,
    }
    return render(request, "ecommerce/mobile/mobile_location_rule/detail.html", context)


@login_required
@tenant_admin_required
def mobilelocationrule_create(request):
    if request.method == "POST":
        form = MobileLocationRuleForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.tenant = request.tenant
            rule.save()
            write_audit_log(
                request=request,
                action="CREATE",
                instance=rule,
                message=f"Created MobileLocationRule {rule.number} ({rule.name})",
            )
            messages.success(request, f"Location Rule '{rule.name}' created successfully.")
            return redirect("ecommerce:mobilelocationrule_detail", pk=rule.pk)
    else:
        form = MobileLocationRuleForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "ecommerce/mobile/mobile_location_rule/form.html", context)


@login_required
@tenant_admin_required
def mobilelocationrule_edit(request, pk):
    rule = ecommerce_object(request, MobileLocationRule, pk)
    if request.method == "POST":
        form = MobileLocationRuleForm(request.POST, instance=rule, tenant=request.tenant)
        if form.is_valid():
            rule = form.save()
            write_audit_log(
                request=request,
                action="UPDATE",
                instance=rule,
                message=f"Updated MobileLocationRule {rule.number}",
            )
            messages.success(request, f"Location Rule '{rule.name}' updated successfully.")
            return redirect("ecommerce:mobilelocationrule_detail", pk=rule.pk)
    else:
        form = MobileLocationRuleForm(instance=rule, tenant=request.tenant)

    context = {
        "form": form,
        "location_rule": rule,
        "object": rule,
        "is_edit": True,
    }
    return render(request, "ecommerce/mobile/mobile_location_rule/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def mobilelocationrule_delete(request, pk):
    rule = ecommerce_object(request, MobileLocationRule, pk)
    number = rule.number
    name = rule.name
    write_audit_log(
        request=request,
        action="DELETE",
        instance=rule,
        message=f"Deleted MobileLocationRule {number} ({name})",
    )
    rule.delete()
    messages.success(request, f"Location Rule '{name}' ({number}) deleted.")
    return redirect("ecommerce:mobilelocationrule_list")


@login_required
@tenant_admin_required
@require_POST
def mobilelocationrule_simulate(request, pk):
    """Simulate checking whether GPS coordinates trigger this geofence rule."""
    rule = ecommerce_object(request, MobileLocationRule, pk)
    lat_str = request.POST.get("test_lat", "").strip()
    lng_str = request.POST.get("test_lng", "").strip()

    try:
        lat = float(lat_str) if lat_str else float(rule.latitude)
        lng = float(lng_str) if lng_str else float(rule.longitude)
    except ValueError:
        messages.error(request, "Invalid coordinates provided for simulation.")
        return redirect("ecommerce:mobilelocationrule_detail", pk=rule.pk)

    dist_m = rule.distance_to(lat, lng)
    inside = dist_m <= rule.radius_meters

    if inside:
        messages.success(
            request,
            f"Simulation Success: Device at ({lat}, {lng}) is {dist_m}m away, INSIDE the {rule.radius_meters}m geofence! Trigger action '{rule.get_trigger_action_display()}' activated.",
        )
    else:
        messages.warning(
            request,
            f"Simulation Result: Device at ({lat}, {lng}) is {dist_m}m away, OUTSIDE the {rule.radius_meters}m geofence.",
        )

    return redirect("ecommerce:mobilelocationrule_detail", pk=rule.pk)
