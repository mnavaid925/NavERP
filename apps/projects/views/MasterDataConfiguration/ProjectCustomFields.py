"""Projects 7.19 — ProjectCustomField views [PCF-]."""
from django.core.paginator import Paginator
from django.db.models import Count, Q

from apps.projects.forms.MasterDataConfiguration.ProjectCustomFields import ProjectCustomFieldForm
from apps.projects.models.MasterDataConfiguration.ProjectCustomFields import ProjectCustomField
from apps.projects.views._common import *


@login_required
def pcf_list(request):
    """List custom field definitions with filters, search, and section counts."""
    qs = ProjectCustomField.objects.filter(tenant=request.tenant).defer(
        "description", "regex_pattern", "choices_list", "visibility_rule"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(label__icontains=q) | Q(field_key__icontains=q) | Q(number__icontains=q))

    target_entity = request.GET.get("target_entity", "").strip()
    if target_entity:
        qs = qs.filter(target_entity=target_entity)

    field_type = request.GET.get("field_type", "").strip()
    if field_type:
        qs = qs.filter(field_type=field_type)

    form_section = request.GET.get("form_section", "").strip()
    if form_section:
        qs = qs.filter(form_section=form_section)

    is_active = request.GET.get("is_active", "").strip()
    if is_active in ("active", "true", "1"):
        is_active = "active"
        qs = qs.filter(is_active=True)
    elif is_active in ("inactive", "false", "0"):
        is_active = "inactive"
        qs = qs.filter(is_active=False)

    stats = ProjectCustomField.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        project=Count("id", filter=Q(target_entity="project")),
        task=Count("id", filter=Q(target_entity="task")),
        milestone=Count("id", filter=Q(target_entity="milestone")),
        risk=Count("id", filter=Q(target_entity="risk")),
    )

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "projects/masterdataconfiguration/customfield/list.html",
        {
            "custom_fields": page_obj.object_list,
            "page_obj": page_obj,
            "target_choices": ProjectCustomField.TARGET_ENTITY_CHOICES,
            "field_type_choices": ProjectCustomField.FIELD_TYPE_CHOICES,
            "section_choices": ProjectCustomField.SECTION_CHOICES,
            "q": q,
            "target_entity": target_entity,
            "field_type": field_type,
            "form_section": form_section,
            "is_active": is_active,
            "stats": stats,
            "has_filters": bool(q or target_entity or field_type or form_section or is_active),
        },
    )


@login_required
def pcf_detail(request, pk):
    """View details of a custom field definition."""
    custom_field = get_object_or_404(ProjectCustomField, pk=pk, tenant=request.tenant)
    return render(
        request,
        "projects/masterdataconfiguration/customfield/detail.html",
        {
            "custom_field": custom_field,
        },
    )


@login_required
@tenant_admin_required
def pcf_create(request):
    """Create a new custom field definition."""
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = ProjectCustomFieldForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            cf = form.save(commit=False)
            cf.tenant = request.tenant
            cf.save()
            write_audit_log(
                user=request.user,
                obj=cf,
                action="create",
                changes={"target_entity": cf.target_entity, "field_key": cf.field_key},
                tenant=request.tenant,
            )
            messages.success(request, f"Custom field '{cf.label}' created successfully.")
            return redirect("projects:pcf_detail", pk=cf.pk)
    else:
        form = ProjectCustomFieldForm(tenant=request.tenant)

    return render(
        request,
        "projects/masterdataconfiguration/customfield/form.html",
        {
            "form": form,
            "is_edit": False,
        },
    )


@login_required
@tenant_admin_required
def pcf_edit(request, pk):
    """Edit an existing custom field definition."""
    custom_field = get_object_or_404(ProjectCustomField, pk=pk, tenant=request.tenant)

    if request.method == "POST":
        form = ProjectCustomFieldForm(request.POST, instance=custom_field, tenant=request.tenant)
        if form.is_valid():
            cf = form.save()
            write_audit_log(
                user=request.user,
                obj=cf,
                action="update",
                changes={"target_entity": cf.target_entity, "field_key": cf.field_key},
                tenant=request.tenant,
            )
            messages.success(request, f"Custom field '{cf.label}' updated successfully.")
            return redirect("projects:pcf_detail", pk=cf.pk)
    else:
        form = ProjectCustomFieldForm(instance=custom_field, tenant=request.tenant)

    return render(
        request,
        "projects/masterdataconfiguration/customfield/form.html",
        {
            "form": form,
            "custom_field": custom_field,
            "is_edit": True,
        },
    )


@login_required
@require_POST
@tenant_admin_required
def pcf_delete(request, pk):
    """Delete a custom field definition."""
    custom_field = get_object_or_404(ProjectCustomField, pk=pk, tenant=request.tenant)
    label = custom_field.label
    write_audit_log(
        user=request.user,
        obj=custom_field,
        action="delete",
        changes={"label": label},
        tenant=request.tenant,
    )
    custom_field.delete()
    messages.success(request, f"Custom field '{label}' deleted successfully.")
    return redirect("projects:pcf_list")


@login_required
@require_POST
@tenant_admin_required
def pcf_toggle_active(request, pk):
    """Toggle active status of a custom field definition."""
    custom_field = get_object_or_404(ProjectCustomField, pk=pk, tenant=request.tenant)
    custom_field.is_active = not custom_field.is_active
    custom_field.save(update_fields=["is_active"])
    write_audit_log(
        user=request.user,
        obj=custom_field,
        action="toggle",
        changes={"is_active": custom_field.is_active},
        tenant=request.tenant,
    )
    status_str = "activated" if custom_field.is_active else "deactivated"
    messages.success(request, f"Custom field '{custom_field.label}' {status_str}.")
    return redirect("projects:pcf_detail", pk=custom_field.pk)
