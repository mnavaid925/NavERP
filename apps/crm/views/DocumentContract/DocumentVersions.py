"""CRM 1.9 Document & Contract Management — DocumentVersions views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    ContractDocument,
    DocumentVersion,
    Opportunity,
)


@login_required
def documentversion_detail(request, pk):
    """Read-only view of one immutable contract revision (snapshot + file download)."""
    obj = get_object_or_404(
        DocumentVersion.objects.select_related("contract", "created_by"), pk=pk, tenant=request.tenant)
    return render(request, "crm/documents/documentversion/detail.html", {"obj": obj})


@login_required
def document_repository(request):
    """1.9 File Repository — contracts organized by account/deal, with version counts."""
    qs = (ContractDocument.objects.filter(tenant=request.tenant)
          .select_related("account", "opportunity", "owner")
          .annotate(version_count=Count("versions"))
          .defer("body_snapshot")
          .order_by("-created_at"))  # annotate()+GROUP BY drops the Meta default ordering
    return crud_list(
        request, qs, "crm/documents/repository.html",
        search_fields=["number", "name", "account__name", "opportunity__name"],
        filters=[("status", "status", False), ("account", "account_id", True),
                 ("opportunity", "opportunity_id", True)],
        extra_context={
            "status_choices": ContractDocument.STATUS_CHOICES,
            "accounts": Party.objects.filter(tenant=request.tenant, kind="organization").only("id", "name").order_by("name"),
            "opportunities": Opportunity.objects.filter(tenant=request.tenant).only("id", "number", "name").order_by("-created_at")[:200],
        },
    )
