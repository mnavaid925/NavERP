from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from apps.bi.forms.Dashboards.BiDashboardForms import BiDashboardDuplicateForm, BiDashboardForm
from apps.bi.models.Dashboards.BiDashboards import BiDashboard
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def bi_dashboard_list(request):
    qs = bi_scope(BiDashboard.objects.all(), request, owner_field="created_by")
    counts = qs.aggregate(
        total=Count("id"),
        published=Count("id", filter=Q(is_published=True)),
        template=Count("id", filter=Q(is_template=True)),
    )
    total_dashboards = counts["total"]
    published_count = counts["published"]
    template_count = counts["template"]

    qs = qs.annotate(widget_count=Count("widgets", filter=Q(widgets__is_active=True)))

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(slug__icontains=q)
            | Q(number__icontains=q)
            | Q(description__icontains=q)
        )

    category = request.GET.get("category", "").strip()
    if category:
        qs = qs.filter(category=category)

    layout_type = request.GET.get("layout_type", "").strip()
    if layout_type:
        qs = qs.filter(layout_type=layout_type)

    theme = request.GET.get("theme", "").strip()
    if theme:
        qs = qs.filter(theme=theme)

    is_published = request.GET.get("is_published", "").strip()
    if is_published in ("1", "true", "True"):
        qs = qs.filter(is_published=True)
    elif is_published in ("0", "false", "False"):
        qs = qs.filter(is_published=False)

    paginator = Paginator(qs, 12)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "dashboards": page_obj,
        "category_choices": BiDashboard.CATEGORY_CHOICES,
        "layout_choices": BiDashboard.LAYOUT_TYPE_CHOICES,
        "theme_choices": BiDashboard.THEME_CHOICES,
        "total_dashboards": total_dashboards,
        "published_count": published_count,
        "template_count": template_count,
        "q": q,
        "category": category,
        "layout_type": layout_type,
        "theme": theme,
        "is_published": is_published,
    }
    return render(request, "bi/dashboards/dashboard/list.html", context)


@login_required
def bi_dashboard_detail(request, pk):
    dashboard = bi_object(
        request,
        BiDashboard,
        pk,
        select_related=("created_by", "org_unit"),
    )

    # Telemetry: update view count and last viewed
    BiDashboard.objects.filter(pk=dashboard.pk).update(
        view_count=dashboard.view_count + 1,
        last_viewed_at=timezone.now(),
    )

    widgets = (
        dashboard.widgets.filter(is_active=True)
        .select_related("calculated_measure", "semantic_model", "warehouse_table")
        .order_by("pos_y", "pos_x", "sort_order")
    )
    filters = dashboard.filters.filter(is_active=True).order_by("order")
    bookmarks = (
        dashboard.bookmarks.filter(is_active=True)
        .filter(Q(user=request.user) | Q(is_shared=True))
        .select_related("user")
        .order_by("-is_default", "name")
    )

    user_default_bookmark = dashboard.bookmarks.filter(
        user=request.user, is_default=True, is_active=True
    ).first()

    can_edit = request.user.is_superuser or getattr(request, "is_tenant_admin", False)

    context = {
        "dashboard": dashboard,
        "widgets": widgets,
        "filters": filters,
        "bookmarks": bookmarks,
        "total_widgets": widgets.count(),
        "user_default_bookmark": user_default_bookmark,
        "can_edit": can_edit,
    }
    return render(request, "bi/dashboards/dashboard/detail.html", context)


@login_required
@tenant_admin_required
def bi_dashboard_create(request):
    if request.method == "POST":
        form = BiDashboardForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                dashboard = form.save(commit=False)
                dashboard.tenant = request.tenant
                dashboard.created_by = request.user
                dashboard.save()
                write_audit_log(
                    request.user,
                    dashboard,
                    "create",
                    changes=form.cleaned_data,
                    tenant=request.tenant,
                )
            messages.success(request, f"Dashboard '{dashboard.title}' created successfully.")
            return redirect("bi:bi_dashboard_detail", pk=dashboard.pk)
    else:
        form = BiDashboardForm(tenant=request.tenant)

    context = {
        "form": form,
        "dashboard": None,
        "is_edit": False,
    }
    return render(request, "bi/dashboards/dashboard/form.html", context)


@login_required
@tenant_admin_required
def bi_dashboard_edit(request, pk):
    dashboard = bi_object(request, BiDashboard, pk)
    if request.method == "POST":
        form = BiDashboardForm(request.POST, instance=dashboard, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                dashboard = form.save()
                write_audit_log(
                    request.user,
                    dashboard,
                    "update",
                    changes=form.cleaned_data,
                    tenant=request.tenant,
                )
            messages.success(request, f"Dashboard '{dashboard.title}' updated successfully.")
            return redirect("bi:bi_dashboard_detail", pk=dashboard.pk)
    else:
        form = BiDashboardForm(instance=dashboard, tenant=request.tenant)

    context = {
        "form": form,
        "dashboard": dashboard,
        "is_edit": True,
    }
    return render(request, "bi/dashboards/dashboard/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def bi_dashboard_delete(request, pk):
    dashboard = bi_object(request, BiDashboard, pk)
    title = dashboard.title
    with transaction.atomic():
        write_audit_log(
            request.user,
            dashboard,
            "delete",
            changes={"title": title, "number": dashboard.number},
            tenant=request.tenant,
        )
        dashboard.delete()
    messages.success(request, f"Dashboard '{title}' deleted successfully.")
    return redirect("bi:bi_dashboard_list")


@login_required
@tenant_admin_required
@require_POST
def bi_dashboard_publish(request, pk):
    dashboard = bi_object(request, BiDashboard, pk)
    dashboard.is_published = not dashboard.is_published
    dashboard.save(update_fields=["is_published", "updated_at"])
    state_str = "published" if dashboard.is_published else "unpublished (draft)"
    write_audit_log(
        request.user,
        dashboard,
        "update",
        changes={"is_published": dashboard.is_published},
        tenant=request.tenant,
    )
    messages.success(request, f"Dashboard '{dashboard.title}' is now {state_str}.")
    return redirect("bi:bi_dashboard_detail", pk=dashboard.pk)


@login_required
@tenant_admin_required
def bi_dashboard_duplicate(request, pk):
    source_dashboard = bi_object(request, BiDashboard, pk, prefetch_related=("widgets", "filters"))
    if request.method == "POST":
        form = BiDashboardDuplicateForm(request.POST)
        if form.is_valid():
            new_title = form.cleaned_data["new_title"]
            new_slug = form.cleaned_data["new_slug"] or slugify(new_title)[:100]
            copy_widgets = form.cleaned_data["copy_widgets"]
            copy_filters = form.cleaned_data["copy_filters"]

            # Ensure slug uniqueness for tenant
            base_slug = new_slug
            counter = 1
            while BiDashboard.objects.filter(tenant=request.tenant, slug=new_slug).exists():
                new_slug = f"{base_slug[:90]}-{counter}"
                counter += 1

            with transaction.atomic():
                new_dashboard = BiDashboard.objects.create(
                    tenant=request.tenant,
                    title=new_title,
                    slug=new_slug,
                    category=source_dashboard.category,
                    layout_type=source_dashboard.layout_type,
                    refresh_interval_seconds=source_dashboard.refresh_interval_seconds,
                    theme=source_dashboard.theme,
                    role_required=source_dashboard.role_required,
                    org_unit=source_dashboard.org_unit,
                    is_published=False,  # Duplicate starts as draft
                    is_template=False,
                    is_default=False,
                    is_kiosk_enabled=source_dashboard.is_kiosk_enabled,
                    color_palette_json=source_dashboard.color_palette_json,
                    config_json=source_dashboard.config_json,
                    created_by=request.user,
                    description=f"Cloned from {source_dashboard.title}. {source_dashboard.description}".strip(),
                )

                if copy_widgets:
                    for w in source_dashboard.widgets.filter(is_active=True):
                        w_copy = w
                        w_copy.pk = None
                        w_copy.id = None
                        w_copy.number = ""
                        w_copy.dashboard = new_dashboard
                        w_copy.save()

                if copy_filters:
                    for f in source_dashboard.filters.filter(is_active=True):
                        f_copy = f
                        f_copy.pk = None
                        f_copy.id = None
                        f_copy.number = ""
                        f_copy.dashboard = new_dashboard
                        f_copy.save()

                write_audit_log(
                    request.user,
                    new_dashboard,
                    "duplicate",
                    changes={"source_dashboard_id": source_dashboard.pk, "new_title": new_title},
                    tenant=request.tenant,
                )

            messages.success(request, f"Dashboard cloned successfully as '{new_dashboard.title}'.")
            return redirect("bi:bi_dashboard_detail", pk=new_dashboard.pk)
    else:
        form = BiDashboardDuplicateForm(initial={
            "new_title": f"{source_dashboard.title} (Copy)",
            "new_slug": f"{source_dashboard.slug}-copy"[:100],
            "copy_widgets": True,
            "copy_filters": True,
        })

    context = {
        "form": form,
        "source_dashboard": source_dashboard,
        "dashboard": source_dashboard,
    }
    return render(request, "bi/dashboards/dashboard/duplicate.html", context)
