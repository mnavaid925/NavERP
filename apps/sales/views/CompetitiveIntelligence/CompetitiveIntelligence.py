from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.crud import paginate
from apps.core.decorators import tenant_admin_required
from apps.core.models import Party
from apps.core.utils import write_audit_log
from apps.crm.models import Opportunity
from apps.sales.forms.CompetitiveIntelligence.CompetitiveIntelligence import (
    CompetitorProfileForm,
    OpportunityCompetitorForm,
)
from apps.sales.models.CompetitiveIntelligence.CompetitiveIntelligence import (
    CompetitorProfile,
    OpportunityCompetitor,
)
from apps.sales.opportunity_services import (
    sales_remove_opportunity_competitor,
    sales_save_opportunity_competitor,
)


COMPETITOR_ACTIVE_CHOICES = [("active", "Active"), ("inactive", "Inactive")]


def _competitor_validation_message(exc):
    return " ".join(exc.messages) if getattr(exc, "messages", None) else str(exc)


def _competitor_parties(tenant):
    if tenant is None:
        return Party.objects.none()
    return Party.objects.filter(tenant=tenant, kind="organization").order_by("name")


def _competitor_profiles(tenant, link=None):
    if tenant is None:
        return CompetitorProfile.objects.none()
    profile_filter = Q(tenant=tenant, is_active=True)
    if link is not None and link.pk and link.competitor_profile_id:
        profile_filter |= Q(pk=link.competitor_profile_id, tenant=tenant)
    return CompetitorProfile.objects.filter(profile_filter).select_related("party").order_by("party__name")


def _competitor_profile_context(form, is_edit, tenant, obj=None):
    context = {
        "form": form,
        "is_edit": is_edit,
        "parties": _competitor_parties(tenant),
    }
    if is_edit:
        context["obj"] = obj
    return context


def _competitor_link_context(opportunity, form, is_edit, obj=None):
    context = {
        "opportunity": opportunity,
        "form": form,
        "is_edit": is_edit,
        "competitor_profiles": _competitor_profiles(opportunity.tenant, obj if is_edit else None),
    }
    if is_edit:
        context["obj"] = obj
    return context


@login_required
def opportunity_competitor_profile_list(request):
    base_queryset = CompetitorProfile.objects.filter(tenant=request.tenant).select_related("party")
    q = request.GET.get("q", "").strip()[:200]
    active = request.GET.get("active", "").strip().lower()
    queryset = base_queryset
    if q:
        queryset = queryset.filter(
            Q(number__icontains=q)
            | Q(party__name__icontains=q)
            | Q(aliases__icontains=q)
            | Q(description__icontains=q)
            | Q(market_positioning__icontains=q)
        )
    if active == "active":
        queryset = queryset.filter(is_active=True)
    elif active == "inactive":
        queryset = queryset.filter(is_active=False)
    else:
        active = ""
    page_obj = paginate(request, queryset, 20)
    stats = base_queryset.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        inactive=Count("id", filter=Q(is_active=False)),
    )
    return render(
        request,
        "sales/opportunity/competitor/list.html",
        {
            "object_list": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "active": active,
            "active_choices": COMPETITOR_ACTIVE_CHOICES,
            "stats": stats,
        },
    )


@tenant_admin_required
def opportunity_competitor_profile_create(request):
    form = CompetitorProfileForm(
        request.POST if request.method == "POST" else None,
        tenant=request.tenant,
    )
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.tenant = request.tenant
        try:
            obj.full_clean()
            obj.save()
        except ValidationError as exc:
            form.add_error(None, exc)
        except IntegrityError:
            form.add_error(None, "That competitor profile already exists.")
        else:
            write_audit_log(
                request.user,
                obj,
                "create",
                {"operation": "create_competitor_profile"},
                tenant=request.tenant,
            )
            messages.success(request, "Competitor profile created.")
            return redirect("sales:opportunity_competitor_profile_list")
    return render(
        request,
        "sales/opportunity/competitor/form.html",
        _competitor_profile_context(form, False, request.tenant),
    )


@login_required
def opportunity_competitor_profile_detail(request, pk):
    obj = get_object_or_404(
        CompetitorProfile.objects.select_related("party"),
        pk=pk,
        tenant=request.tenant,
    )
    opportunity_links = list(
        OpportunityCompetitor.objects.filter(
            tenant=request.tenant,
            competitor_profile=obj,
        )
        .select_related("opportunity", "competitor_profile__party")
        .order_by("-is_primary", "relationship", "id")
    )
    return render(
        request,
        "sales/opportunity/competitor/detail.html",
        {"obj": obj, "opportunity_links": opportunity_links},
    )


@tenant_admin_required
def opportunity_competitor_profile_edit(request, pk):
    obj = get_object_or_404(
        CompetitorProfile.objects.select_related("party"),
        pk=pk,
        tenant=request.tenant,
    )
    form = CompetitorProfileForm(
        request.POST if request.method == "POST" else None,
        instance=obj,
        tenant=request.tenant,
    )
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.tenant = request.tenant
        try:
            obj.full_clean()
            obj.save()
        except ValidationError as exc:
            form.add_error(None, exc)
        except IntegrityError:
            form.add_error(None, "That competitor profile already exists.")
        else:
            write_audit_log(
                request.user,
                obj,
                "update",
                {"operation": "update_competitor_profile"},
                tenant=request.tenant,
            )
            messages.success(request, "Competitor profile updated.")
            return redirect("sales:opportunity_competitor_profile_list")
    return render(
        request,
        "sales/opportunity/competitor/form.html",
        _competitor_profile_context(form, True, request.tenant, obj),
    )


@require_POST
@tenant_admin_required
def opportunity_competitor_profile_delete(request, pk):
    with transaction.atomic():
        obj = get_object_or_404(
            CompetitorProfile.objects.select_for_update().select_related("party"),
            pk=pk,
            tenant=request.tenant,
        )
        try:
            with transaction.atomic():
                if obj.opportunitycompetitor_set.exists():
                    raise ValidationError("A referenced competitor profile cannot be deleted.")
                write_audit_log(
                    request.user,
                    obj,
                    "delete",
                    {"operation": "delete_competitor_profile"},
                    tenant=request.tenant,
                )
                obj.delete()
        except (ValidationError, ProtectedError) as exc:
            messages.error(request, _competitor_validation_message(exc))
        else:
            messages.success(request, "Competitor profile deleted.")
    return redirect("sales:opportunity_competitor_profile_list")


@login_required
def opportunity_competitor_link_add(request, opportunity_pk):
    opportunity = get_object_or_404(
        Opportunity,
        pk=opportunity_pk,
        tenant=request.tenant,
    )
    link = OpportunityCompetitor()
    form = OpportunityCompetitorForm(
        request.POST if request.method == "POST" else None,
        instance=link,
        opportunity=opportunity,
        tenant=request.tenant,
    )
    if request.method == "POST" and form.is_valid():
        try:
            sales_save_opportunity_competitor(
                opportunity,
                form.instance,
                request.tenant,
                request.user,
                form.cleaned_data,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        except IntegrityError:
            form.add_error(None, "That competitor is already linked to this opportunity.")
        else:
            messages.success(request, "Opportunity competitor added.")
            return redirect("sales:opportunity_workspace_detail", opportunity_pk=opportunity.pk)
    return render(
        request,
        "sales/opportunity/competitor/link_form.html",
        _competitor_link_context(opportunity, form, False),
    )


@login_required
def opportunity_competitor_link_edit(request, opportunity_pk, competitor_pk):
    opportunity = get_object_or_404(
        Opportunity,
        pk=opportunity_pk,
        tenant=request.tenant,
    )
    link = get_object_or_404(
        OpportunityCompetitor.objects.select_related("opportunity", "competitor_profile__party"),
        pk=competitor_pk,
        opportunity=opportunity,
        tenant=request.tenant,
    )
    form = OpportunityCompetitorForm(
        request.POST if request.method == "POST" else None,
        instance=link,
        opportunity=opportunity,
        tenant=request.tenant,
    )
    if request.method == "POST" and form.is_valid():
        try:
            sales_save_opportunity_competitor(
                opportunity,
                form.instance,
                request.tenant,
                request.user,
                form.cleaned_data,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        except IntegrityError:
            form.add_error(None, "That competitor is already linked to this opportunity.")
        else:
            messages.success(request, "Opportunity competitor updated.")
            return redirect("sales:opportunity_workspace_detail", opportunity_pk=opportunity.pk)
    return render(
        request,
        "sales/opportunity/competitor/link_form.html",
        _competitor_link_context(opportunity, form, True, link),
    )


@require_POST
@login_required
def opportunity_competitor_link_remove(request, opportunity_pk, competitor_pk):
    opportunity = get_object_or_404(
        Opportunity,
        pk=opportunity_pk,
        tenant=request.tenant,
    )
    link = get_object_or_404(
        OpportunityCompetitor.objects.select_related("opportunity", "competitor_profile__party"),
        pk=competitor_pk,
        opportunity=opportunity,
        tenant=request.tenant,
    )
    try:
        sales_remove_opportunity_competitor(
            opportunity,
            link,
            request.tenant,
            request.user,
        )
    except ValidationError as exc:
        messages.error(request, _competitor_validation_message(exc))
    else:
        messages.success(request, "Opportunity competitor removed.")
    return redirect("sales:opportunity_workspace_detail", opportunity_pk=opportunity.pk)
