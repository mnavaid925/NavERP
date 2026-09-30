"""Sales 8.7 — the account-to-territory assignment ledger views.

The ledger exists so a coverage decision is a RECORD rather than a value on the account: a
rebalance opens a new row instead of overwriting the old one, so "what did Territory West contain
in March?" stays answerable (research §5.8).

`assigned_by` is `editable=False` frozen evidence, which is why create and edit are hand-written
here rather than delegated to `crud_create` / `crud_edit`: those stamp `tenant` and the audit row
but know nothing about who made the assignment, and a form cannot carry a fact about itself (§12).
Every other field is ordinary form input.
"""
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.core.crud import as_db_int
from apps.core.models import Party
from apps.core.utils import write_audit_log
from apps.sales.forms.TerritoryQuotaManagement.AccountTerritoryAssignments import (
    AccountTerritoryAssignmentForm,
)
from apps.sales.models.TerritoryQuotaManagement.AccountTerritoryAssignments import (
    AccountTerritoryAssignment,
)
from apps.sales.models.TerritoryQuotaManagement.TerritoryRules import TerritoryRule
from apps.sales.views._common import *
from apps.sales.views.TerritoryQuotaManagement.TerritoryBoards import tenant_territories

LIST_TEMPLATE = "sales/territoryquotamanagement/accountterritoryassignment/list.html"
DETAIL_TEMPLATE = "sales/territoryquotamanagement/accountterritoryassignment/detail.html"
FORM_TEMPLATE = "sales/territoryquotamanagement/accountterritoryassignment/form.html"

PAGE_SIZE = 15

#: The `coverage` filter reads the WINDOW, not a stored boolean: "current" is `effective_to IS NULL`.
COVERAGE_CHOICES = [("current", "Current"), ("expired", "Expired"), ("all", "All")]


def _assignment_queryset(request):
    return (
        AccountTerritoryAssignment.objects.filter(tenant=request.tenant)
        .select_related("account", "territory", "rule", "owner", "assigned_by")
    )


def _choice_context():
    return {
        "alignment_type_choices": TerritoryRule.ALIGNMENT_TYPE_CHOICES,
        "assignment_source_choices": AccountTerritoryAssignment.ASSIGNMENT_SOURCE_CHOICES,
    }


def _form_context(request):
    return {
        **_choice_context(),
        "territories": tenant_territories(request.tenant),
        "users": User.objects.filter(tenant=request.tenant, is_active=True).order_by("username"),
        "rules": TerritoryRule.objects.filter(tenant=request.tenant, is_active=True).order_by(
            "priority", "id"
        ),
    }


@login_required
def account_territory_assignment_list(request):
    queryset = _assignment_queryset(request)
    alignment_type = request.GET.get("alignment_type", "")
    if alignment_type in dict(TerritoryRule.ALIGNMENT_TYPE_CHOICES):
        queryset = queryset.filter(alignment_type=alignment_type)
    assignment_source = request.GET.get("assignment_source", "")
    if assignment_source in dict(AccountTerritoryAssignment.ASSIGNMENT_SOURCE_CHOICES):
        queryset = queryset.filter(assignment_source=assignment_source)
    coverage = request.GET.get("coverage", "")
    if coverage in {"current", "expired"}:
        if coverage == "current":
            queryset = queryset.filter(effective_to__isnull=True)
        else:
            queryset = queryset.filter(effective_to__isnull=False)
    elif coverage:
        coverage = ""
    territory_id = as_db_int(request.GET.get("territory"))
    if territory_id:
        queryset = queryset.filter(territory_id=territory_id)
    owner_id = as_db_int(request.GET.get("owner"))
    if owner_id:
        queryset = queryset.filter(owner_id=owner_id)

    base = _assignment_queryset(request)
    stats = {
        "total": base.count(),
        "current": base.filter(effective_to__isnull=True).count(),
        # An assignment with no territory is the SET_NULL orphan; it is counted here so the
        # register can never show a healthy "assigned" count while rows point at nothing.
        "unassigned": base.filter(territory__isnull=True, effective_to__isnull=True).count(),
        "overlay": base.filter(alignment_type="overlay", effective_to__isnull=True).count(),
    }
    return crud_list(
        request,
        queryset,
        LIST_TEMPLATE,
        search_fields=[
            "number", "account__name", "territory__name", "territory__number", "notes",
        ],
        extra_context={
            "page_size": PAGE_SIZE,
            **_choice_context(),
            "coverage_choices": COVERAGE_CHOICES,
            "territories": tenant_territories(request.tenant),
            "users": User.objects.filter(tenant=request.tenant, is_active=True).order_by("username"),
            "stats": stats,
            "alignment_type": alignment_type,
            "assignment_source": assignment_source,
            "coverage": coverage,
            "territory_id": territory_id or "",
            "owner_id": owner_id or "",
        },
        per_page=PAGE_SIZE,
    )


@login_required
def account_territory_assignment_create(request):
    if request.method == "POST":
        form = AccountTerritoryAssignmentForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                obj = form.save(commit=False)
                obj.tenant = request.tenant
                # Frozen evidence, stamped here and nowhere else (§12). Never a form field.
                obj.assigned_by = request.user
                obj.save()
                form.save_m2m()
                write_audit_log(
                    request.user,
                    obj,
                    "create",
                    {
                        "action": "account_territory_assignment",
                        "account_id": obj.account_id,
                        "territory_id": obj.territory_id,
                        "alignment_type": obj.alignment_type,
                        "assignment_source": obj.assignment_source,
                    },
                    tenant=request.tenant,
                )
            messages.success(request, "Assignment saved.")
            return redirect("sales:account_territory_assignment_detail", pk=obj.pk)
    else:
        form = AccountTerritoryAssignmentForm(tenant=request.tenant)
    return render(request, FORM_TEMPLATE, {
        "form": form,
        "obj": None,
        "is_edit": False,
        **_form_context(request),
    })


@login_required
def account_territory_assignment_detail(request, pk):
    obj = get_object_or_404(_assignment_queryset(request), pk=pk)
    siblings = (
        AccountTerritoryAssignment.objects.filter(tenant=request.tenant, account=obj.account)
        .exclude(pk=obj.pk)
        .filter(effective_to__isnull=True)
        .select_related("territory")[:50]
    )
    caveats = []
    if obj.territory_id is None:
        caveats.append(
            "This assignment points at no territory. That is the SET_NULL orphan a deleted CRM "
            "territory leaves behind; the row is kept because it is the record of a decision."
        )
    if obj.alignment_type == "primary" and obj.effective_to is None:
        primary_count = AccountTerritoryAssignment.objects.filter(
            tenant=request.tenant, account=obj.account, alignment_type="primary", effective_to__isnull=True
        ).count()
        if primary_count > 1:
            caveats.append(
                f"This account carries {primary_count} live primary rows. The model refuses a new one; "
                "close the others here."
            )
    if obj.rule_id and obj.assignment_source != "rule":
        caveats.append("This row names a rule but does not say it came from one.")
    return render(request, DETAIL_TEMPLATE, {
        "obj": obj,
        **_choice_context(),
        "rule": obj.rule,
        "siblings": siblings,
        "caveats": caveats,
    })


@login_required
def account_territory_assignment_edit(request, pk):
    obj = get_object_or_404(_assignment_queryset(request), pk=pk)
    if request.method == "POST":
        form = AccountTerritoryAssignmentForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                locked = AccountTerritoryAssignment.objects.select_for_update().get(
                    pk=obj.pk, tenant=request.tenant
                )
                form.instance = locked
                for field_name in form._meta.fields:
                    model_field = form.instance._meta.get_field(field_name)
                    if (
                        model_field.concrete
                        and not model_field.many_to_many
                        and field_name in form.cleaned_data
                    ):
                        setattr(form.instance, field_name, form.cleaned_data[field_name])
                locked.assigned_by = request.user
                locked.save()
                form.save_m2m()
                write_audit_log(
                    request.user,
                    locked,
                    "update",
                    {
                        "action": "account_territory_assignment",
                        "account_id": locked.account_id,
                        "territory_id": locked.territory_id,
                        "alignment_type": locked.alignment_type,
                        "assignment_source": locked.assignment_source,
                    },
                    tenant=request.tenant,
                )
            messages.success(request, "Assignment updated.")
            return redirect("sales:account_territory_assignment_detail", pk=obj.pk)
    else:
        form = AccountTerritoryAssignmentForm(instance=obj, tenant=request.tenant)
    return render(request, FORM_TEMPLATE, {
        "form": form,
        "obj": obj,
        "is_edit": True,
        **_form_context(request),
    })


@require_POST
@login_required
@tenant_admin_required
def account_territory_assignment_delete(request, pk):
    obj = get_object_or_404(_assignment_queryset(request), pk=pk)
    with transaction.atomic():
        locked = AccountTerritoryAssignment.objects.select_for_update().get(
            pk=obj.pk, tenant=request.tenant
        )
        write_audit_log(
            request.user,
            locked,
            "delete",
            {
                "action": "account_territory_assignment",
                "account_id": locked.account_id,
                "territory_id": locked.territory_id,
            },
            tenant=request.tenant,
        )
        locked.delete()
    messages.success(request, "Assignment deleted.")
    return redirect("sales:account_territory_assignment_list")
