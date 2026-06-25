"""Core spine CRUD views (tenant-scoped). Reads/writes are open to any logged-in
member; the AuditLog is admin-only and read-only. All list/detail/edit lookups filter
by ``request.tenant`` so cross-tenant ids 404.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from .crud import crud_create, crud_delete, crud_detail, crud_edit, crud_list
from .decorators import tenant_admin_required
from .models import (
    Activity,
    Address,
    AuditLog,
    ContactMethod,
    Document,
    Employment,
    OrgUnit,
    Party,
    PartyRelationship,
    PartyRole,
)
from .forms import (
    ActivityForm,
    AddressForm,
    ContactMethodForm,
    DocumentForm,
    EmploymentForm,
    OrgUnitForm,
    PartyForm,
    PartyRelationshipForm,
    PartyRoleForm,
)

User = get_user_model()


def _parties(request):
    return Party.objects.filter(tenant=request.tenant)


# --------------------------------------------------------------------------- OrgUnit
@login_required
def orgunit_list(request):
    return crud_list(
        request, OrgUnit.objects.filter(tenant=request.tenant).select_related("parent"),
        "core/orgunit/list.html",
        search_fields=["name"],
        filters=[("kind", "kind", False), ("parent", "parent_id", True)],
        extra_context={"kind_choices": OrgUnit.KIND_CHOICES,
                       "parents": OrgUnit.objects.filter(tenant=request.tenant)},
    )


@login_required
def orgunit_create(request):
    return crud_create(request, form_class=OrgUnitForm, template="core/orgunit/form.html",
                       success_url="core:orgunit_list")


@login_required
def orgunit_detail(request, pk):
    return crud_detail(request, model=OrgUnit, pk=pk, template="core/orgunit/detail.html",
                       select_related=["parent"])


@login_required
def orgunit_edit(request, pk):
    return crud_edit(request, model=OrgUnit, pk=pk, form_class=OrgUnitForm,
                     template="core/orgunit/form.html", success_url="core:orgunit_list")


@login_required
@require_POST
def orgunit_delete(request, pk):
    return crud_delete(request, model=OrgUnit, pk=pk, success_url="core:orgunit_list")


# ----------------------------------------------------------------------------- Party
@login_required
def party_list(request):
    return crud_list(
        request, Party.objects.filter(tenant=request.tenant),
        "core/party/list.html",
        search_fields=["name", "tax_id"],
        filters=[("kind", "kind", False)],
        extra_context={"kind_choices": Party.KIND_CHOICES},
    )


@login_required
def party_create(request):
    return crud_create(request, form_class=PartyForm, template="core/party/form.html",
                       success_url="core:party_list")


@login_required
def party_detail(request, pk):
    return crud_detail(request, model=Party, pk=pk, template="core/party/detail.html",
                       extra_context=None)


@login_required
def party_edit(request, pk):
    return crud_edit(request, model=Party, pk=pk, form_class=PartyForm,
                     template="core/party/form.html", success_url="core:party_list")


@login_required
@require_POST
def party_delete(request, pk):
    return crud_delete(request, model=Party, pk=pk, success_url="core:party_list")


# ------------------------------------------------------------------------- PartyRole
@login_required
def partyrole_list(request):
    return crud_list(
        request, PartyRole.objects.filter(tenant=request.tenant).select_related("party"),
        "core/partyrole/list.html",
        search_fields=["party__name"],
        filters=[("role", "role", False), ("status", "status", False), ("party", "party_id", True)],
        extra_context={"role_choices": PartyRole.ROLE_CHOICES,
                       "status_choices": PartyRole.STATUS_CHOICES, "parties": _parties(request)},
    )


@login_required
def partyrole_create(request):
    return crud_create(request, form_class=PartyRoleForm, template="core/partyrole/form.html",
                       success_url="core:partyrole_list")


@login_required
def partyrole_detail(request, pk):
    return crud_detail(request, model=PartyRole, pk=pk, template="core/partyrole/detail.html",
                       select_related=["party"])


@login_required
def partyrole_edit(request, pk):
    return crud_edit(request, model=PartyRole, pk=pk, form_class=PartyRoleForm,
                     template="core/partyrole/form.html", success_url="core:partyrole_list")


@login_required
@require_POST
def partyrole_delete(request, pk):
    return crud_delete(request, model=PartyRole, pk=pk, success_url="core:partyrole_list")


# --------------------------------------------------------------------------- Address
@login_required
def address_list(request):
    return crud_list(
        request, Address.objects.filter(tenant=request.tenant).select_related("party"),
        "core/address/list.html",
        search_fields=["line1", "city", "country"],
        filters=[("kind", "kind", False), ("party", "party_id", True)],
        extra_context={"kind_choices": Address.KIND_CHOICES, "parties": _parties(request)},
    )


@login_required
def address_create(request):
    return crud_create(request, form_class=AddressForm, template="core/address/form.html",
                       success_url="core:address_list")


@login_required
def address_detail(request, pk):
    return crud_detail(request, model=Address, pk=pk, template="core/address/detail.html",
                       select_related=["party"])


@login_required
def address_edit(request, pk):
    return crud_edit(request, model=Address, pk=pk, form_class=AddressForm,
                     template="core/address/form.html", success_url="core:address_list")


@login_required
@require_POST
def address_delete(request, pk):
    return crud_delete(request, model=Address, pk=pk, success_url="core:address_list")


# --------------------------------------------------------------------- ContactMethod
@login_required
def contactmethod_list(request):
    return crud_list(
        request, ContactMethod.objects.filter(tenant=request.tenant).select_related("party"),
        "core/contactmethod/list.html",
        search_fields=["value"],
        filters=[("kind", "kind", False), ("party", "party_id", True)],
        extra_context={"kind_choices": ContactMethod.KIND_CHOICES, "parties": _parties(request)},
    )


@login_required
def contactmethod_create(request):
    return crud_create(request, form_class=ContactMethodForm, template="core/contactmethod/form.html",
                       success_url="core:contactmethod_list")


@login_required
def contactmethod_detail(request, pk):
    return crud_detail(request, model=ContactMethod, pk=pk, template="core/contactmethod/detail.html",
                       select_related=["party"])


@login_required
def contactmethod_edit(request, pk):
    return crud_edit(request, model=ContactMethod, pk=pk, form_class=ContactMethodForm,
                     template="core/contactmethod/form.html", success_url="core:contactmethod_list")


@login_required
@require_POST
def contactmethod_delete(request, pk):
    return crud_delete(request, model=ContactMethod, pk=pk, success_url="core:contactmethod_list")


# ----------------------------------------------------------------- PartyRelationship
@login_required
def partyrelationship_list(request):
    return crud_list(
        request,
        PartyRelationship.objects.filter(tenant=request.tenant).select_related("from_party", "to_party"),
        "core/partyrelationship/list.html",
        search_fields=["from_party__name", "to_party__name"],
        filters=[("kind", "kind", False)],
        extra_context={"kind_choices": PartyRelationship.KIND_CHOICES, "parties": _parties(request)},
    )


@login_required
def partyrelationship_create(request):
    return crud_create(request, form_class=PartyRelationshipForm,
                       template="core/partyrelationship/form.html",
                       success_url="core:partyrelationship_list")


@login_required
def partyrelationship_detail(request, pk):
    return crud_detail(request, model=PartyRelationship, pk=pk,
                       template="core/partyrelationship/detail.html",
                       select_related=["from_party", "to_party"])


@login_required
def partyrelationship_edit(request, pk):
    return crud_edit(request, model=PartyRelationship, pk=pk, form_class=PartyRelationshipForm,
                     template="core/partyrelationship/form.html",
                     success_url="core:partyrelationship_list")


@login_required
@require_POST
def partyrelationship_delete(request, pk):
    return crud_delete(request, model=PartyRelationship, pk=pk,
                       success_url="core:partyrelationship_list")


# ------------------------------------------------------------------------ Employment
@login_required
def employment_list(request):
    return crud_list(
        request,
        Employment.objects.filter(tenant=request.tenant).select_related("party", "org_unit", "manager"),
        "core/employment/list.html",
        search_fields=["party__name", "job_title"],
        filters=[("status", "status", False), ("org_unit", "org_unit_id", True)],
        extra_context={"status_choices": Employment.STATUS_CHOICES,
                       "org_units": OrgUnit.objects.filter(tenant=request.tenant),
                       "parties": _parties(request)},
    )


@login_required
def employment_create(request):
    return crud_create(request, form_class=EmploymentForm, template="core/employment/form.html",
                       success_url="core:employment_list")


@login_required
def employment_detail(request, pk):
    return crud_detail(request, model=Employment, pk=pk, template="core/employment/detail.html",
                       select_related=["party", "org_unit", "manager"])


@login_required
def employment_edit(request, pk):
    return crud_edit(request, model=Employment, pk=pk, form_class=EmploymentForm,
                     template="core/employment/form.html", success_url="core:employment_list")


@login_required
@require_POST
def employment_delete(request, pk):
    return crud_delete(request, model=Employment, pk=pk, success_url="core:employment_list")


# -------------------------------------------------------------------------- Activity
@login_required
def activity_list(request):
    return crud_list(
        request, Activity.objects.filter(tenant=request.tenant).select_related("owner", "party"),
        "core/activity/list.html",
        search_fields=["subject"],
        filters=[("kind", "kind", False), ("status", "status", False), ("owner", "owner_id", True)],
        extra_context={"kind_choices": Activity.KIND_CHOICES,
                       "status_choices": Activity.STATUS_CHOICES,
                       "parties": _parties(request),
                       "owners": User.objects.filter(tenant=request.tenant)
                       .only("id", "email", "first_name", "last_name")},
    )


@login_required
def activity_create(request):
    return crud_create(request, form_class=ActivityForm, template="core/activity/form.html",
                       success_url="core:activity_list")


@login_required
def activity_detail(request, pk):
    return crud_detail(request, model=Activity, pk=pk, template="core/activity/detail.html",
                       select_related=["owner", "party"])


@login_required
def activity_edit(request, pk):
    return crud_edit(request, model=Activity, pk=pk, form_class=ActivityForm,
                     template="core/activity/form.html", success_url="core:activity_list")


@login_required
@require_POST
def activity_delete(request, pk):
    return crud_delete(request, model=Activity, pk=pk, success_url="core:activity_list")


# -------------------------------------------------------------------------- Document
@login_required
def document_list(request):
    return crud_list(
        request, Document.objects.filter(tenant=request.tenant),
        "core/document/list.html",
        search_fields=["name"],
        filters=[("classification", "classification", False)],
        extra_context={"classification_choices": Document.CLASSIFICATION_CHOICES},
    )


@login_required
def document_create(request):
    return crud_create(request, form_class=DocumentForm, template="core/document/form.html",
                       success_url="core:document_list")


@login_required
def document_detail(request, pk):
    return crud_detail(request, model=Document, pk=pk, template="core/document/detail.html")


@login_required
def document_edit(request, pk):
    return crud_edit(request, model=Document, pk=pk, form_class=DocumentForm,
                     template="core/document/form.html", success_url="core:document_list")


@login_required
@require_POST
def document_delete(request, pk):
    return crud_delete(request, model=Document, pk=pk, success_url="core:document_list")


# -------------------------------------------------------------- AuditLog (read-only)
@tenant_admin_required
def auditlog_list(request):
    return crud_list(
        request, AuditLog.objects.filter(tenant=request.tenant).select_related("user"),
        "core/auditlog/list.html",
        search_fields=["target"],
        filters=[("action", "action", False)],
        extra_context={"action_choices": AuditLog.ACTION_CHOICES,
                       "users": User.objects.filter(tenant=request.tenant)
                       .only("id", "email", "first_name", "last_name")},
    )


@tenant_admin_required
def auditlog_detail(request, pk):
    obj = get_object_or_404(AuditLog.objects.select_related("user"), pk=pk, tenant=request.tenant)
    return render(request, "core/auditlog/detail.html", {"obj": obj})
