from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import IntegrityError, ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.core.models import OrgUnit
from apps.core.utils import write_audit_log
from apps.crm.models import Opportunity
from apps.sales.forms.OpportunityTeams.OpportunityTeams import OpportunityTeamMemberForm
from apps.sales.models.OpportunityTeams.OpportunityTeams import OpportunityTeamMember


def _opportunity_team_member_users(tenant, member=None):
    if tenant is None:
        return User.objects.none()
    user_filter = Q(tenant=tenant, is_active=True)
    if member is not None and member.pk and member.user_id:
        user_filter |= Q(pk=member.user_id, tenant=tenant)
    return User.objects.filter(user_filter).order_by("email")


def _opportunity_team_member_org_units(tenant):
    if tenant is None:
        return OrgUnit.objects.none()
    return OrgUnit.objects.filter(tenant=tenant).order_by("name")


def _opportunity_team_member_context(opportunity, form, is_edit, member=None):
    context = {
        "opportunity": opportunity,
        "form": form,
        "is_edit": is_edit,
        "users": _opportunity_team_member_users(opportunity.tenant, member),
        "org_units": _opportunity_team_member_org_units(opportunity.tenant),
    }
    if is_edit:
        context["obj"] = member
    return context


@login_required
def opportunity_team_member_add(request, opportunity_pk):
    if request.method == "POST":
        with transaction.atomic():
            opportunity = get_object_or_404(
                Opportunity.objects.select_for_update(),
                pk=opportunity_pk,
                tenant=request.tenant,
            )
            form = OpportunityTeamMemberForm(
                request.POST,
                tenant=request.tenant,
                opportunity=opportunity,
            )
            if form.is_valid():
                member = form.save(commit=False)
                member.tenant = request.tenant
                member.opportunity = opportunity
                try:
                    with transaction.atomic():
                        member.full_clean()
                        member.save()
                except ValidationError as exc:
                    form.add_error(None, exc)
                except IntegrityError:
                    form.add_error(None, "That team membership already exists.")
                else:
                    write_audit_log(
                        request.user,
                        member,
                        "create",
                        {
                            "operation": "add_team_member",
                            "opportunity_id": opportunity.pk,
                            "user_id": member.user_id,
                            "role": member.role,
                        },
                        tenant=request.tenant,
                    )
                    messages.success(request, "Opportunity team member added.")
                    return redirect(
                        "sales:opportunity_workspace_detail",
                        opportunity_pk=opportunity.pk,
                    )
    else:
        with transaction.atomic():
            opportunity = get_object_or_404(
                Opportunity.objects.select_for_update(),
                pk=opportunity_pk,
                tenant=request.tenant,
            )
            form = OpportunityTeamMemberForm(
                tenant=request.tenant,
                opportunity=opportunity,
            )
    return render(
        request,
        "sales/opportunity/team_member/form.html",
        _opportunity_team_member_context(opportunity, form, False),
    )


@login_required
def opportunity_team_member_edit(request, opportunity_pk, member_pk):
    if request.method == "POST":
        with transaction.atomic():
            opportunity = get_object_or_404(
                Opportunity.objects.select_for_update(),
                pk=opportunity_pk,
                tenant=request.tenant,
            )
            member = get_object_or_404(
                OpportunityTeamMember.objects.select_for_update(),
                pk=member_pk,
                opportunity=opportunity,
                tenant=request.tenant,
            )
            form = OpportunityTeamMemberForm(
                request.POST,
                instance=member,
                tenant=request.tenant,
                opportunity=opportunity,
            )
            if form.is_valid():
                member = form.save(commit=False)
                member.tenant = request.tenant
                member.opportunity = opportunity
                try:
                    with transaction.atomic():
                        member.full_clean()
                        member.save()
                except ValidationError as exc:
                    form.add_error(None, exc)
                except IntegrityError:
                    form.add_error(None, "That team membership already exists.")
                else:
                    write_audit_log(
                        request.user,
                        member,
                        "update",
                        {
                            "operation": "update_team_member",
                            "member_id": member.pk,
                            "opportunity_id": opportunity.pk,
                            "user_id": member.user_id,
                            "role": member.role,
                        },
                        tenant=request.tenant,
                    )
                    messages.success(request, "Opportunity team member updated.")
                    return redirect(
                        "sales:opportunity_workspace_detail",
                        opportunity_pk=opportunity.pk,
                    )
    else:
        with transaction.atomic():
            opportunity = get_object_or_404(
                Opportunity.objects.select_for_update(),
                pk=opportunity_pk,
                tenant=request.tenant,
            )
            member = get_object_or_404(
                OpportunityTeamMember.objects.select_for_update(),
                pk=member_pk,
                opportunity=opportunity,
                tenant=request.tenant,
            )
            form = OpportunityTeamMemberForm(
                instance=member,
                tenant=request.tenant,
                opportunity=opportunity,
            )
    return render(
        request,
        "sales/opportunity/team_member/form.html",
        _opportunity_team_member_context(opportunity, form, True, member),
    )


@login_required
@require_POST
def opportunity_team_member_remove(request, opportunity_pk, member_pk):
    with transaction.atomic():
        opportunity = get_object_or_404(
            Opportunity.objects.select_for_update(),
            pk=opportunity_pk,
            tenant=request.tenant,
        )
        member = get_object_or_404(
            OpportunityTeamMember.objects.select_for_update(),
            pk=member_pk,
            opportunity=opportunity,
            tenant=request.tenant,
        )
        write_audit_log(
            request.user,
            member,
            "delete",
            {
                "operation": "remove_team_member",
                "member_id": member.pk,
                "opportunity_id": opportunity.pk,
                "user_id": member.user_id,
                "role": member.role,
            },
            tenant=request.tenant,
        )
        member.delete()
    messages.success(request, "Opportunity team member removed.")
    return redirect(
        "sales:opportunity_workspace_detail",
        opportunity_pk=opportunity.pk,
    )
