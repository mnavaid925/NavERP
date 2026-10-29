from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.Personalization.PersonalizedExperiences import PersonalizedExperienceForm
from apps.ecommerce.models.Personalization.PersonalizedExperiences import PersonalizedExperience
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def personalizedexperience_list(request):
    qs = ecommerce_scope(PersonalizedExperience.objects.all(), request).select_related(
        "target_segment", "target_category", "target_product"
    )

    search_query = request.GET.get("q", "").strip()
    experience_type = request.GET.get("experience_type", "").strip()
    is_active = request.GET.get("is_active", "").strip()

    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(name__icontains=search_query)
            | Q(headline__icontains=search_query)
            | Q(subheadline__icontains=search_query)
            | Q(cta_label__icontains=search_query)
        )

    if experience_type:
        qs = qs.filter(experience_type=experience_type)

    if is_active in ("1", "true", "True"):
        qs = qs.filter(is_active=True)
    elif is_active in ("0", "false", "False"):
        qs = qs.filter(is_active=False)

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "experiences": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "q": search_query,
        "search_query": search_query,
        "selected_type": experience_type,
        "selected_active": is_active,
        "experience_type_choices": PersonalizedExperience.EXPERIENCE_TYPE_CHOICES,
    }
    return render(request, "ecommerce/personalization/personalizedexperience/list.html", context)


@login_required
def personalizedexperience_detail(request, pk):
    experience = ecommerce_object(request, PersonalizedExperience, pk)
    context = {
        "experience": experience,
    }
    return render(request, "ecommerce/personalization/personalizedexperience/detail.html", context)


@login_required
@tenant_admin_required
def personalizedexperience_create(request):
    target_segment_id = request.GET.get("target_segment")
    initial_data = {}
    if target_segment_id:
        initial_data["target_segment"] = target_segment_id

    if request.method == "POST":
        form = PersonalizedExperienceForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            experience = form.save(commit=False)
            experience.tenant = request.tenant
            experience.save()
            write_audit_log(
                request.tenant,
                request.user,
                "create",
                "PersonalizedExperience",
                experience.pk,
                f"Created personalized experience {experience.name} ({experience.number})",
            )
            messages.success(request, f"Personalized experience '{experience.name}' created.")
            return redirect("ecommerce:personalizedexperience_detail", pk=experience.pk)
    else:
        form = PersonalizedExperienceForm(initial=initial_data, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "ecommerce/personalization/personalizedexperience/form.html", context)


@login_required
@tenant_admin_required
def personalizedexperience_edit(request, pk):
    experience = ecommerce_object(request, PersonalizedExperience, pk)
    if request.method == "POST":
        form = PersonalizedExperienceForm(request.POST, instance=experience, tenant=request.tenant)
        if form.is_valid():
            experience = form.save()
            write_audit_log(
                request.tenant,
                request.user,
                "update",
                "PersonalizedExperience",
                experience.pk,
                f"Updated personalized experience {experience.name} ({experience.number})",
            )
            messages.success(request, f"Personalized experience '{experience.name}' updated.")
            return redirect("ecommerce:personalizedexperience_detail", pk=experience.pk)
    else:
        form = PersonalizedExperienceForm(instance=experience, tenant=request.tenant)

    context = {
        "form": form,
        "experience": experience,
        "is_edit": True,
    }
    return render(request, "ecommerce/personalization/personalizedexperience/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def personalizedexperience_delete(request, pk):
    experience = ecommerce_object(request, PersonalizedExperience, pk)
    name = experience.name
    number = experience.number
    experience.delete()
    write_audit_log(
        request.tenant,
        request.user,
        "delete",
        "PersonalizedExperience",
        pk,
        f"Deleted personalized experience {name} ({number})",
    )
    messages.success(request, f"Personalized experience '{name}' deleted.")
    return redirect("ecommerce:personalizedexperience_list")


@login_required
@tenant_admin_required
@require_POST
def personalizedexperience_toggle(request, pk):
    experience = ecommerce_object(request, PersonalizedExperience, pk)
    experience.is_active = not experience.is_active
    experience.save(update_fields=["is_active", "updated_at"])
    state = "activated" if experience.is_active else "deactivated"
    write_audit_log(
        request.tenant,
        request.user,
        "toggle",
        "PersonalizedExperience",
        experience.pk,
        f"{state.capitalize()} personalized experience {experience.name} ({experience.number})",
    )
    messages.success(request, f"Personalized experience '{experience.name}' {state}.")
    return redirect("ecommerce:personalizedexperience_detail", pk=experience.pk)
