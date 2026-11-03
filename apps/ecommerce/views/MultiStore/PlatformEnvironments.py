from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.ecommerce.forms.MultiStore.PlatformEnvironments import PlatformEnvironmentForm
from apps.ecommerce.models.MultiStore.PlatformEnvironments import PlatformEnvironment
from apps.ecommerce.models.MultiStore.StorefrontInstances import StorefrontInstance
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def platform_environment_list(request):
    queryset = ecommerce_scope(
        PlatformEnvironment.objects.select_related("storefront"),
        request,
    )

    search_query = request.GET.get("q", "").strip()
    if search_query:
        queryset = queryset.filter(
            Q(name__icontains=search_query)
            | Q(base_url__icontains=search_query)
            | Q(cluster_region__icontains=search_query)
            | Q(number__icontains=search_query)
        )

    env_type_filter = request.GET.get("env_type", "").strip()
    if env_type_filter:
        queryset = queryset.filter(env_type=env_type_filter)

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    paginator = Paginator(queryset, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    storefronts = ecommerce_scope(StorefrontInstance.objects.all(), request)

    context = {
        "platform_environments": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "search_query": search_query,
        "env_type_filter": env_type_filter,
        "status_filter": status_filter,
        "env_type_choices": PlatformEnvironment.ENV_TYPE_CHOICES,
        "status_choices": PlatformEnvironment.STATUS_CHOICES,
        "storefronts": storefronts,
    }
    return render(request, "ecommerce/multi_store/platform_environment/list.html", context)


@login_required
def platform_environment_detail(request, pk):
    environment = ecommerce_object(
        request,
        PlatformEnvironment,
        pk=pk,
        select_related=("storefront",),
    )
    pipelines = environment.deployment_pipelines.select_related("promoted_by").order_by("-created_at")[:10]

    context = {
        "environment": environment,
        "pipelines": pipelines,
    }
    return render(request, "ecommerce/multi_store/platform_environment/detail.html", context)


@login_required
def platform_environment_create(request):
    initial = {}
    storefront_id = request.GET.get("storefront")
    if storefront_id:
        initial["storefront"] = storefront_id

    if request.method == "POST":
        form = PlatformEnvironmentForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            environment = form.save(commit=False)
            environment.tenant = request.tenant
            environment.save()
            write_audit_log(
                request.user,
                "CREATE",
                environment,
                f"Created platform environment '{environment.name}' ({environment.number}) for {environment.get_env_type_display()}"
            )
            messages.success(request, f"Environment '{environment.name}' created successfully.")
            return redirect("ecommerce:platform_environment_detail", pk=environment.pk)
    else:
        form = PlatformEnvironmentForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "environment": None,
        "is_edit": False,
    }
    return render(request, "ecommerce/multi_store/platform_environment/form.html", context)


@login_required
def platform_environment_edit(request, pk):
    environment = ecommerce_object(request, PlatformEnvironment, pk=pk)
    if request.method == "POST":
        form = PlatformEnvironmentForm(request.POST, instance=environment, tenant=request.tenant)
        if form.is_valid():
            environment = form.save()
            write_audit_log(
                request.user,
                "UPDATE",
                environment,
                f"Updated platform environment '{environment.name}' ({environment.number})"
            )
            messages.success(request, f"Environment '{environment.name}' updated successfully.")
            return redirect("ecommerce:platform_environment_detail", pk=environment.pk)
    else:
        form = PlatformEnvironmentForm(instance=environment, tenant=request.tenant)

    context = {
        "form": form,
        "environment": environment,
        "is_edit": True,
    }
    return render(request, "ecommerce/multi_store/platform_environment/form.html", context)


@login_required
@require_POST
def platform_environment_delete(request, pk):
    environment = ecommerce_object(request, PlatformEnvironment, pk=pk)
    name = environment.name
    num = environment.number
    environment.delete()
    write_audit_log(
        request.user,
        "DELETE",
        None,
        f"Deleted platform environment '{name}' ({num})"
    )
    messages.success(request, f"Environment '{name}' was deleted.")
    return redirect("ecommerce:platform_environment_list")
