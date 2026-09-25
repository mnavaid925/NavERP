from django.db import transaction
from django.db.models import Count, F, Q
from django.urls import reverse
from django.utils.dateparse import parse_date

from apps.core.crud import as_db_int, apply_search, paginate
from apps.core.models import Party, PartyRelationship
from apps.core.utils import write_audit_log
from apps.crm.models import CommunicationLog, ContactProfile, Opportunity
from apps.sales.forms.ContactAccountManagement.AccountStakeholders import AccountStakeholderForm
from apps.sales.models.ContactAccountManagement.AccountStakeholders import AccountStakeholder
from apps.sales.views._common import *


def _stakeholder_queryset(request):
    return AccountStakeholder.objects.filter(tenant=request.tenant).select_related("account", "contact")


def _filter_stakeholder_queryset(request, queryset):
    filters = {
        "q": request.GET.get("q", "").strip(),
        "account": as_db_int(request.GET.get("account")),
        "contact": as_db_int(request.GET.get("contact")),
        "role": request.GET.get("role", ""),
        "influence": request.GET.get("influence", ""),
        "attitude": request.GET.get("attitude", ""),
        "relationship_strength": request.GET.get("relationship_strength", ""),
        "status": request.GET.get("status", ""),
        "valid_from": request.GET.get("valid_from", ""),
        "valid_to": request.GET.get("valid_to", ""),
    }
    queryset = apply_search(queryset, filters["q"], ["account__name", "contact__name", "notes"])
    if filters["account"]:
        queryset = queryset.filter(account_id=filters["account"])
    if filters["contact"]:
        queryset = queryset.filter(contact_id=filters["contact"])
    for key, field, choices in (
        ("role", "role", dict(AccountStakeholder.ROLE_CHOICES)),
        ("influence", "influence", dict(AccountStakeholder.INFLUENCE_CHOICES)),
        ("attitude", "attitude", dict(AccountStakeholder.ATTITUDE_CHOICES)),
        ("relationship_strength", "relationship_strength", dict(AccountStakeholder.RELATIONSHIP_STRENGTH_CHOICES)),
        ("status", "status", dict(AccountStakeholder.STATUS_CHOICES)),
    ):
        if filters[key] in choices:
            queryset = queryset.filter(**{field: filters[key]})
    from_date = safe_parse_date(filters["valid_from"]) if filters["valid_from"] else None
    to_date = safe_parse_date(filters["valid_to"]) if filters["valid_to"] else None
    if from_date:
        queryset = queryset.filter(Q(valid_to__gte=from_date) | Q(valid_to__isnull=True))
    if to_date:
        queryset = queryset.filter(Q(valid_from__lte=to_date) | Q(valid_from__isnull=True))
    return queryset, filters


def _stakeholder_form_context(request):
    return {
        "accounts": list(Party.objects.filter(tenant=request.tenant, kind="organization").order_by("name")[:500]),
        "contacts": list(Party.objects.filter(tenant=request.tenant, kind="person").order_by("name")[:500]),
    }


@login_required
def account_stakeholder_list(request):
    queryset = _stakeholder_queryset(request)
    queryset, filters = _filter_stakeholder_queryset(request, queryset)
    q = filters["q"]
    account_id = filters["account"]
    contact_id = filters["contact"]
    role = filters["role"]
    influence = filters["influence"]
    attitude = filters["attitude"]
    relationship_strength = filters["relationship_strength"]
    status = filters["status"]
    valid_from = filters["valid_from"]
    valid_to = filters["valid_to"]
    page_obj = paginate(request, queryset, 20)
    stats_base = _stakeholder_queryset(request)
    stats = stats_base.aggregate(
        total=Count("pk"),
        active=Count("pk", filter=Q(status="active")),
        former=Count("pk", filter=Q(status="former")),
    )
    export_url = reverse("sales:account_stakeholder_export")
    if request.GET:
        export_url = f"{export_url}?{request.GET.urlencode()}"
    return render(request, "sales/contactaccountmanagement/accountstakeholder/list.html", {
        "object_list": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "accounts": list(Party.objects.filter(tenant=request.tenant, kind="organization").order_by("name")[:500]),
        "contacts": list(Party.objects.filter(tenant=request.tenant, kind="person").order_by("name")[:500]),
        "role_choices": AccountStakeholder.ROLE_CHOICES,
        "influence_choices": AccountStakeholder.INFLUENCE_CHOICES,
        "attitude_choices": AccountStakeholder.ATTITUDE_CHOICES,
        "relationship_strength_choices": AccountStakeholder.RELATIONSHIP_STRENGTH_CHOICES,
        "status_choices": AccountStakeholder.STATUS_CHOICES,
        "account_id": account_id or "",
        "contact_id": contact_id or "",
        "role": role,
        "influence": influence,
        "attitude": attitude,
        "relationship_strength": relationship_strength,
        "status": status,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "stats": stats,
        "export_url": export_url,
    })


@login_required
def account_stakeholder_create(request):
    if request.method == "POST":
        form = AccountStakeholderForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                obj = form.save(commit=False)
                obj.tenant = request.tenant
                obj.save()
                write_audit_log(
                    request.user,
                    obj,
                    "create",
                    {"action": "account_stakeholder", "account_id": obj.account_id, "role": obj.role, "status": obj.status},
                    tenant=request.tenant,
                )
            messages.success(request, "Account stakeholder created.")
            return redirect("sales:account_stakeholder_list")
    else:
        form = AccountStakeholderForm(tenant=request.tenant)
    context = {"form": form, "is_edit": False}
    context.update(_stakeholder_form_context(request))
    return render(request, "sales/contactaccountmanagement/accountstakeholder/form.html", context)


@login_required
def account_stakeholder_detail(request, pk):
    obj = get_object_or_404(_stakeholder_queryset(request), pk=pk)
    primary = ContactProfile.objects.filter(
        tenant=request.tenant,
        party=obj.contact,
        party__tenant=request.tenant,
        party__kind="person",
        account=obj.account,
        account__tenant=request.tenant,
        account__kind="organization",
    ).exists()
    reports_to = list(
        PartyRelationship.objects.filter(
            tenant=request.tenant,
            from_party=obj.contact,
            from_party__tenant=request.tenant,
            from_party__kind="person",
            to_party__tenant=request.tenant,
            to_party__kind="person",
            kind="reports_to",
        )
        .exclude(from_party_id=F("to_party_id"))
        .select_related("to_party")[:100]
    )
    opportunities = list(
        Opportunity.objects.filter(
            tenant=request.tenant,
            account=obj.account,
            account__tenant=request.tenant,
            account__kind="organization",
        )
        .only("id", "number", "name", "stage", "amount", "close_date", "account_id", "created_at")
        .order_by("-created_at")[:20]
    )
    latest_log = CommunicationLog.objects.filter(
        tenant=request.tenant,
        party=obj.contact,
        party__tenant=request.tenant,
        party__kind="person",
    ).order_by("-occurred_at").first()
    coverage_roles = list(
        AccountStakeholder.objects.filter(
            tenant=request.tenant,
            account=obj.account,
            account__tenant=request.tenant,
            account__kind="organization",
            contact=obj.contact,
            contact__tenant=request.tenant,
            contact__kind="person",
            status="active",
        )
        .values_list("role", flat=True)
        .distinct()[:100]
    )
    return render(request, "sales/contactaccountmanagement/accountstakeholder/detail.html", {
        "obj": obj,
        "account": obj.account,
        "contact": obj.contact,
        "is_primary_affiliation": primary,
        "reports_to": reports_to,
        "related_opportunities": opportunities,
        "interaction_recency": latest_log,
        "coverage_roles": coverage_roles,
        "can_edit": True,
    })


@login_required
def account_stakeholder_edit(request, pk):
    obj = get_object_or_404(_stakeholder_queryset(request), pk=pk)
    if request.method == "POST":
        form = AccountStakeholderForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                locked = AccountStakeholder.objects.select_for_update().get(pk=obj.pk, tenant=request.tenant)
                form.instance = locked
                for field_name in form._meta.fields:
                    model_field = form.instance._meta.get_field(field_name)
                    if model_field.concrete and not model_field.many_to_many and field_name in form.cleaned_data:
                        setattr(form.instance, field_name, form.cleaned_data[field_name])
                locked = form.save()
                write_audit_log(
                    request.user,
                    locked,
                    "update",
                    {"action": "account_stakeholder", "account_id": locked.account_id, "role": locked.role, "status": locked.status},
                    tenant=request.tenant,
                )
            messages.success(request, "Account stakeholder updated.")
            return redirect("sales:account_stakeholder_list")
    else:
        form = AccountStakeholderForm(instance=obj, tenant=request.tenant)
    context = {"form": form, "obj": obj, "is_edit": True}
    context.update(_stakeholder_form_context(request))
    return render(request, "sales/contactaccountmanagement/accountstakeholder/form.html", context)


@require_POST
@login_required
def account_stakeholder_delete(request, pk):
    obj = get_object_or_404(_stakeholder_queryset(request), pk=pk)
    with transaction.atomic():
        locked = AccountStakeholder.objects.select_for_update().get(pk=obj.pk, tenant=request.tenant)
        write_audit_log(
            request.user,
            locked,
            "delete",
            {"action": "account_stakeholder", "account_id": locked.account_id, "role": locked.role, "status": locked.status},
            tenant=request.tenant,
        )
        locked.delete()
    messages.success(request, "Account stakeholder deleted.")
    return redirect("sales:account_stakeholder_list")


@login_required
def account_stakeholder_export(request):
    queryset, filters = _filter_stakeholder_queryset(request, _stakeholder_queryset(request))
    rows = (
        (
            obj.account.name,
            obj.contact.name,
            obj.get_role_display(),
            obj.get_influence_display(),
            obj.get_attitude_display(),
            obj.get_relationship_strength_display(),
            obj.get_status_display(),
            obj.valid_from or "",
            obj.valid_to or "",
        )
        for obj in queryset.order_by("account__name", "contact__name", "role")[:5000]
    )
    return csv_export_response(
        request,
        filename="sales-account-stakeholders.csv",
        dataset="account_stakeholders",
        headers=["Account", "Contact", "Role", "Influence", "Attitude", "Strength", "Status", "Valid from", "Valid to"],
        rows=rows,
        filters={key: value for key, value in filters.items() if key != "q"},
    )
