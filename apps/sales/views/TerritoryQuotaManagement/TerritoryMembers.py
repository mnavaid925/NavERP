"""Sales 8.7 — the territory roster views: who works which territory, in what role, on what split.

A member is one person's role in one `crm.Territory` — never a territory, never a team hierarchy,
never a second manager field (§16). An overlay specialist is a member with no subtree of their own;
the overlay behaviour comes from the DATA SHAPE (an overlay member plus the account's overlay
assignments), not from a second tree to keep in step (research §5.7).

`coverage_split_pct` is summed in Python over the fetched siblings by the model itself, never by
`Sum()` in SQL — the SQLite integer-division trap drops fractional cents silently rather than
raising, so a database-side total is a WRONG ANSWER, not a slow one. These views do not touch that
total; they surface the roster and its gaps.
"""
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.core.crud import as_db_int
from apps.core.utils import write_audit_log
from apps.sales.forms.TerritoryQuotaManagement.TerritoryMembers import TerritoryMemberForm
from apps.sales.models.TerritoryQuotaManagement.TerritoryMembers import TerritoryMember
from apps.sales.views._common import *
from apps.sales.views.TerritoryQuotaManagement.TerritoryBoards import tenant_territories

LIST_TEMPLATE = "sales/territoryquotamanagement/territorymember/list.html"
DETAIL_TEMPLATE = "sales/territoryquotamanagement/territorymember/detail.html"
FORM_TEMPLATE = "sales/territoryquotamanagement/territorymember/form.html"

PAGE_SIZE = 15

#: The roster's "is this live?" question is the WINDOW (`effective_to IS NULL`), never a stored flag.
ACTIVE_CHOICES = [("active", "Active"), ("inactive", "Inactive")]


def _member_queryset(request):
    return (
        TerritoryMember.objects.filter(tenant=request.tenant)
        .select_related("territory", "user", "paired_user")
    )


def _choice_context():
    return {
        "member_role_choices": TerritoryMember.MEMBER_ROLE_CHOICES,
        "assignment_type_choices": TerritoryMember.ASSIGNMENT_TYPE_CHOICES,
    }


def _form_context(request):
    return {
        **_choice_context(),
        "territories": tenant_territories(request.tenant),
        "users": User.objects.filter(tenant=request.tenant, is_active=True).order_by("username"),
    }


@login_required
def territory_member_list(request):
    queryset = _member_queryset(request)
    member_role = request.GET.get("member_role", "")
    if member_role in dict(TerritoryMember.MEMBER_ROLE_CHOICES):
        queryset = queryset.filter(member_role=member_role)
    assignment_type = request.GET.get("assignment_type", "")
    if assignment_type in dict(TerritoryMember.ASSIGNMENT_TYPE_CHOICES):
        queryset = queryset.filter(assignment_type=assignment_type)
    territory_id = as_db_int(request.GET.get("territory"))
    if territory_id:
        queryset = queryset.filter(territory_id=territory_id)
    user_id = as_db_int(request.GET.get("user"))
    if user_id:
        queryset = queryset.filter(user_id=user_id)
    active = request.GET.get("active", "")
    if active == "active":
        queryset = queryset.filter(effective_to__isnull=True)
    elif active == "inactive":
        queryset = queryset.filter(effective_to__isnull=False)

    base = _member_queryset(request)
    live = base.filter(effective_to__isnull=True)
    stats = {
        "total": base.count(),
        "direct": live.filter(assignment_type="direct").count(),
        "shared": live.filter(assignment_type="shared").count(),
        "overlay": live.filter(assignment_type="overlay").count(),
        # A pairing is an SDR→AE relationship (contract §5.2), so ONLY an SDR with no live paired AE
        # is an orphan. Counting every member with a NULL `paired_user` would report every hunter,
        # farmer and AE on the roster as an orphan — technically true of the column, useless as a stat.
        "orphaned_pairs": live.filter(member_role="sdr").filter(
            Q(paired_user__isnull=True) | Q(paired_user__is_active=False)
        ).count(),
    }
    return crud_list(
        request,
        queryset,
        LIST_TEMPLATE,
        search_fields=["number", "user__username", "user__first_name", "user__last_name", "notes"],
        extra_context={
            "page_size": PAGE_SIZE,
            **_choice_context(),
            "active_choices": ACTIVE_CHOICES,
            "territories": tenant_territories(request.tenant),
            "users": User.objects.filter(tenant=request.tenant, is_active=True).order_by("username"),
            "stats": stats,
            "member_role": member_role,
            "assignment_type": assignment_type,
            "territory_id": territory_id or "",
            "user_id": user_id or "",
            "active": active,
        },
        per_page=PAGE_SIZE,
    )


@login_required
def territory_member_create(request):
    return crud_create(
        request,
        form_class=TerritoryMemberForm,
        template=FORM_TEMPLATE,
        success_url=reverse("sales:territory_member_list"),
        extra_context=_form_context(request),
    )


@login_required
def territory_member_detail(request, pk):
    obj = get_object_or_404(_member_queryset(request), pk=pk)
    territory_peers = (
        _member_queryset(request).filter(territory_id=obj.territory_id)
        .exclude(pk=obj.pk)
        .order_by("-is_primary", "member_role")[:100]
    )
    is_frozen = bool(obj.effective_to and obj.effective_to < timezone.localdate())
    caveats = []
    if obj.effective_to and obj.effective_to >= timezone.localdate():
        caveats.append(f"This membership ends on {obj.effective_to:%d %b %Y}, so it is still live today.")
    if obj.paired_user_id is None:
        if obj.assignment_type == "direct" and obj.member_role == "sdr":
            caveats.append("An SDR with no paired account executive has nobody to hand qualified work to.")
    elif not getattr(obj.paired_user, "is_active", False):
        caveats.append("The paired user is no longer active, so this pairing is an orphan (research §5.9).")
    if obj.member_role == "overlay_specialist":
        caveats.append(
            "An overlay specialist holds no subtree: the overlay behaviour comes from overlay "
            "assignments on the account, not from a second territory tree."
        )
    return render(request, DETAIL_TEMPLATE, {
        "obj": obj,
        **_choice_context(),
        "territory_peers": territory_peers,
        "paired_user": obj.paired_user,
        "is_frozen": is_frozen,
        "caveats": caveats,
    })


@login_required
def territory_member_edit(request, pk):
    obj = get_object_or_404(_member_queryset(request), pk=pk)
    if obj.effective_to and obj.effective_to < timezone.localdate():
        messages.error(
            request,
            "This territory membership has ended and can no longer be edited.",
        )
        return redirect("sales:territory_member_detail", pk=obj.pk)
    return crud_edit(
        request,
        model=TerritoryMember,
        pk=pk,
        form_class=TerritoryMemberForm,
        template=FORM_TEMPLATE,
        success_url=reverse("sales:territory_member_detail", args=[pk]),
        extra_context=_form_context(request),
    )


@require_POST
@login_required
@tenant_admin_required
def territory_member_delete(request, pk):
    obj = get_object_or_404(_member_queryset(request), pk=pk)
    with transaction.atomic():
        locked = TerritoryMember.objects.select_for_update().get(pk=obj.pk, tenant=request.tenant)
        write_audit_log(
            request.user,
            locked,
            "delete",
            {
                "action": "territory_member",
                "territory_id": locked.territory_id,
                "user_id": locked.user_id,
                "member_role": locked.member_role,
            },
            tenant=request.tenant,
        )
        locked.delete()
    messages.success(request, "Territory member removed.")
    return redirect("sales:territory_member_list")
