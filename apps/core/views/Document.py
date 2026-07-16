"""core — Document views (split from apps/core/views.py)."""
from apps.core.views._common import *  # noqa: F401,F403
from apps.core.models import (
    Document,
)
from apps.core.forms import (
    DocumentForm,
)


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
