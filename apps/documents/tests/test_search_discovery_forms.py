"""Unit tests for Sub-module 13.6 Search & Discovery forms."""
import json
import pytest
from django import forms
from django.core.exceptions import ValidationError

from apps.core.models import OrgUnit
from apps.documents.forms._common import reject_foreign
from apps.documents.forms.SearchDiscovery.DocumentSavedSearches import DocumentSavedSearchForm
from apps.documents.forms.SearchDiscovery.DocumentSearchAlerts import DocumentSearchAlertForm
from apps.documents.forms.SearchDiscovery.DocumentSearchSynonyms import DocumentSearchSynonymForm
from apps.documents.forms.SearchDiscovery.DocumentSearchQueryLogs import (
    DocumentSearchQueryLogForm,
)

# Exported / conventional alias for log filter form representation
DocumentSearchQueryLogFilterForm = DocumentSearchQueryLogForm

from apps.documents.models.SearchDiscovery.DocumentSavedSearches import DocumentSavedSearch
from apps.documents.models.SearchDiscovery.DocumentSearchAlerts import DocumentSearchAlert
from apps.documents.models.SearchDiscovery.DocumentSearchSynonyms import DocumentSearchSynonym
from apps.documents.models.SearchDiscovery.DocumentSearchQueryLogs import DocumentSearchQueryLog


# ============================================================================
# Helpers
# ============================================================================

def _search_discovery_create_dept(tenant, name="Engineering"):
    """Helper to create an OrgUnit department for tenant."""
    return OrgUnit.objects.create(
        tenant=tenant,
        name=name,
        kind="department",
    )


def _search_discovery_create_saved_search(
    tenant,
    owner,
    name="Test Saved Search",
    visibility="private",
    department=None,
    is_active=True,
    query_text="test query",
):
    """Helper to create a DocumentSavedSearch instance."""
    return DocumentSavedSearch.objects.create(
        tenant=tenant,
        owner=owner,
        name=name,
        visibility=visibility,
        department=department,
        is_active=is_active,
        query_text=query_text,
    )


# ============================================================================
# 1. DocumentSavedSearchForm Tests
# ============================================================================

@pytest.mark.django_db
def test_search_discovery_saved_search_form_excluded_fields():
    """Verify system-managed and sensitive fields are excluded from DocumentSavedSearchForm."""
    form = DocumentSavedSearchForm()
    excluded = [
        "tenant",
        "number",
        "owner",
        "slug",
        "run_count",
        "total_results_last_run",
        "last_run_at",
        "created_at",
        "updated_at",
    ]
    for field in excluded:
        assert field not in form.fields, f"Security violation: {field} exposed in DocumentSavedSearchForm"

    expected_fields = {
        "name",
        "description",
        "department",
        "visibility",
        "query_text",
        "filters_json",
        "facet_filters_json",
        "sort_by",
        "sort_order",
        "is_pinned",
        "is_favorite",
        "is_active",
    }
    assert set(form.fields.keys()) == expected_fields


@pytest.mark.django_db
def test_search_discovery_saved_search_form_valid_minimal(tenant_a):
    """Test DocumentSavedSearchForm with only required fields."""
    form = DocumentSavedSearchForm(
        tenant=tenant_a,
        data={
            "name": "Quick Invoices",
            "visibility": "private",
            "sort_by": "relevance",
            "sort_order": "desc",
            "is_active": True,
        },
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["name"] == "Quick Invoices"
    assert form.cleaned_data["filters_json"] == "{}"
    assert form.cleaned_data["facet_filters_json"] == "{}"
    assert form.cleaned_data["visibility"] == "private"


@pytest.mark.django_db
def test_search_discovery_saved_search_form_valid_full(tenant_a, admin_user):
    """Test DocumentSavedSearchForm with full valid payload including department and json filters."""
    dept = _search_discovery_create_dept(tenant_a, name="Legal & Compliance")
    filters_payload = json.dumps({"document_type": "contract", "status": "approved"})
    facet_payload = json.dumps({"classification": ["confidential", "restricted"]})

    form = DocumentSavedSearchForm(
        tenant=tenant_a,
        data={
            "name": "Approved Confidential Contracts",
            "description": "High value contracts filtered for compliance audit",
            "department": dept.pk,
            "visibility": "shared_department",
            "query_text": "indemnity AND liability",
            "filters_json": filters_payload,
            "facet_filters_json": facet_payload,
            "sort_by": "updated_at_desc",
            "sort_order": "asc",
            "is_pinned": True,
            "is_favorite": True,
            "is_active": True,
        },
    )
    assert form.is_valid(), form.errors
    instance = form.save(commit=False)
    instance.owner = admin_user
    instance.save()

    assert instance.pk is not None
    assert instance.tenant == tenant_a
    assert instance.department == dept
    assert instance.number.startswith("DSVD-")
    assert instance.visibility == "shared_department"
    assert json.loads(instance.filters_json) == {"document_type": "contract", "status": "approved"}
    assert json.loads(instance.facet_filters_json) == {"classification": ["confidential", "restricted"]}
    assert instance.is_pinned is True


@pytest.mark.django_db
def test_search_discovery_saved_search_form_department_dropdown_scoping(tenant_a, tenant_b):
    """Test department field queryset is strictly scoped to the tenant."""
    dept_a = _search_discovery_create_dept(tenant_a, name="Acme R&D")
    dept_b = _search_discovery_create_dept(tenant_b, name="Globex Security")

    form = DocumentSavedSearchForm(tenant=tenant_a)
    dept_qs = form.fields["department"].queryset

    assert dept_a in dept_qs
    assert dept_b not in dept_qs


@pytest.mark.django_db
def test_search_discovery_saved_search_form_cross_tenant_department_rejected(tenant_a, tenant_b):
    """Test cross-tenant department FK selection is rejected by reject_foreign validation."""
    foreign_dept = _search_discovery_create_dept(tenant_b, name="Foreign Org Unit")

    form = DocumentSavedSearchForm(
        tenant=tenant_a,
        data={
            "name": "Hacked Tenant Search",
            "department": foreign_dept.pk,
            "visibility": "shared_department",
            "sort_by": "relevance",
            "sort_order": "desc",
        },
    )
    assert not form.is_valid()
    assert "department" in form.errors

    # Direct check of reject_foreign behavior
    cleaned = {"department": foreign_dept}
    reject_foreign(form, cleaned, ["department"])
    assert "department" in form.errors
    assert "That record belongs to another workspace." in form.errors["department"]


@pytest.mark.django_db
def test_search_discovery_saved_search_form_filters_json_valid_dictionary(tenant_a):
    """Test filters_json normalizes valid JSON dictionaries."""
    form = DocumentSavedSearchForm(
        tenant=tenant_a,
        data={
            "name": "JSON Filter Test",
            "filters_json": '{\n  "status": "published",\n  "author_id": 42\n}',
            "visibility": "private",
            "sort_by": "relevance",
            "sort_order": "desc",
        },
    )
    assert form.is_valid(), form.errors
    parsed = json.loads(form.cleaned_data["filters_json"])
    assert parsed == {"status": "published", "author_id": 42}


@pytest.mark.django_db
def test_search_discovery_saved_search_form_filters_json_empty_or_whitespace(tenant_a):
    """Test filters_json blank or whitespace string normalizes to '{}'."""
    for empty_val in ["", "   ", "\t\n"]:
        form = DocumentSavedSearchForm(
            tenant=tenant_a,
            data={
                "name": "Empty Filters",
                "filters_json": empty_val,
                "facet_filters_json": empty_val,
                "visibility": "private",
                "sort_by": "relevance",
                "sort_order": "desc",
            },
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data["filters_json"] == "{}"
        assert form.cleaned_data["facet_filters_json"] == "{}"


@pytest.mark.django_db
def test_search_discovery_saved_search_form_filters_json_invalid_syntax(tenant_a):
    """Test filters_json with syntax errors raises ValidationError."""
    form = DocumentSavedSearchForm(
        tenant=tenant_a,
        data={
            "name": "Bad Syntax",
            "filters_json": "{not valid json: 'missing quotes'}",
            "visibility": "private",
            "sort_by": "relevance",
            "sort_order": "desc",
        },
    )
    assert not form.is_valid()
    assert "filters_json" in form.errors
    assert "Invalid JSON" in str(form.errors["filters_json"])


@pytest.mark.django_db
def test_search_discovery_saved_search_form_filters_json_non_dict_rejected(tenant_a):
    """Test filters_json containing valid JSON that is not a dictionary raises ValidationError."""
    for invalid_payload in ['["item1", "item2"]', '"just a string"', '12345', 'true']:
        form = DocumentSavedSearchForm(
            tenant=tenant_a,
            data={
                "name": "Non-Dict JSON",
                "filters_json": invalid_payload,
                "visibility": "private",
                "sort_by": "relevance",
                "sort_order": "desc",
            },
        )
        assert not form.is_valid()
        assert "filters_json" in form.errors
        assert "Must be a valid JSON dictionary" in str(form.errors["filters_json"])


@pytest.mark.django_db
def test_search_discovery_saved_search_form_facet_filters_json_validation(tenant_a):
    """Test facet_filters_json validates syntax and requires JSON dictionary."""
    # Syntax error
    form_syntax = DocumentSavedSearchForm(
        tenant=tenant_a,
        data={
            "name": "Bad Facet Syntax",
            "facet_filters_json": "{unclosed facet json",
            "visibility": "private",
            "sort_by": "relevance",
            "sort_order": "desc",
        },
    )
    assert not form_syntax.is_valid()
    assert "facet_filters_json" in form_syntax.errors
    assert "Invalid JSON" in str(form_syntax.errors["facet_filters_json"])

    # Non-dictionary list
    form_list = DocumentSavedSearchForm(
        tenant=tenant_a,
        data={
            "name": "List Facet",
            "facet_filters_json": '["status", "approved"]',
            "visibility": "private",
            "sort_by": "relevance",
            "sort_order": "desc",
        },
    )
    assert not form_list.is_valid()
    assert "facet_filters_json" in form_list.errors
    assert "Must be a valid JSON dictionary" in str(form_list.errors["facet_filters_json"])


@pytest.mark.django_db
def test_search_discovery_saved_search_form_missing_required_name(tenant_a):
    """Test missing or whitespace name fails validation."""
    for bad_name in ["", "   ", None]:
        data = {
            "visibility": "private",
            "sort_by": "relevance",
            "sort_order": "desc",
        }
        if bad_name is not None:
            data["name"] = bad_name
        form = DocumentSavedSearchForm(tenant=tenant_a, data=data)
        assert not form.is_valid()
        assert "name" in form.errors


@pytest.mark.django_db
def test_search_discovery_saved_search_form_invalid_choices(tenant_a):
    """Test invalid choice values for visibility, sort_by, and sort_order fail validation."""
    form = DocumentSavedSearchForm(
        tenant=tenant_a,
        data={
            "name": "Invalid Choices Test",
            "visibility": "secret_vault",
            "sort_by": "random_shuffle",
            "sort_order": "diagonal",
        },
    )
    assert not form.is_valid()
    assert "visibility" in form.errors
    assert "sort_by" in form.errors
    assert "sort_order" in form.errors


# ============================================================================
# 2. DocumentSearchAlertForm Tests
# ============================================================================

@pytest.mark.django_db
def test_search_discovery_search_alert_form_excluded_fields():
    """Verify system-managed and execution counters are excluded from DocumentSearchAlertForm."""
    form = DocumentSearchAlertForm()
    excluded = [
        "tenant",
        "number",
        "subscriber",
        "last_notified_at",
        "last_checked_at",
        "new_matches_count",
        "last_result_ids",
        "created_at",
        "updated_at",
    ]
    for field in excluded:
        assert field not in form.fields, f"Security violation: {field} exposed in DocumentSearchAlertForm"

    expected_fields = {
        "saved_search",
        "frequency",
        "delivery_channel",
        "status",
        "notes",
        "is_active",
    }
    assert set(form.fields.keys()) == expected_fields


@pytest.mark.django_db
def test_search_discovery_search_alert_form_valid(tenant_a, admin_user, document_saved_search):
    """Test DocumentSearchAlertForm with valid data."""
    form = DocumentSearchAlertForm(
        tenant=tenant_a,
        user=admin_user,
        data={
            "saved_search": document_saved_search.pk,
            "frequency": "weekly",
            "delivery_channel": "email",
            "status": "active",
            "notes": "Notify executive team weekly",
            "is_active": True,
        },
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["frequency"] == "weekly"
    assert form.cleaned_data["delivery_channel"] == "email"


@pytest.mark.django_db
def test_search_discovery_search_alert_form_dropdown_scoping_normal_user(
    tenant_a, member_user, admin_user
):
    """Test saved_search queryset for a non-admin user includes own searches and public ones, but excludes other users' private ones."""
    # 1. Own private search -> SHOULD be visible
    own_search = _search_discovery_create_saved_search(
        tenant_a, owner=member_user, name="Member Own Search", visibility="private", is_active=True
    )
    # 2. Public search by another user -> SHOULD be visible
    public_search = _search_discovery_create_saved_search(
        tenant_a, owner=admin_user, name="Admin Public Search", visibility="public", is_active=True
    )
    # 3. Private search by another user -> MUST be excluded
    other_private = _search_discovery_create_saved_search(
        tenant_a, owner=admin_user, name="Admin Confidential Search", visibility="private", is_active=True
    )
    # 4. Inactive search -> MUST be excluded
    inactive_search = _search_discovery_create_saved_search(
        tenant_a, owner=member_user, name="Old Inactive Search", visibility="public", is_active=False
    )

    form = DocumentSearchAlertForm(tenant=tenant_a, user=member_user)
    saved_search_qs = form.fields["saved_search"].queryset

    assert own_search in saved_search_qs
    assert public_search in saved_search_qs
    assert other_private not in saved_search_qs
    assert inactive_search not in saved_search_qs


@pytest.mark.django_db
def test_search_discovery_search_alert_form_dropdown_scoping_department(
    tenant_a, member_user, admin_user
):
    """Test saved_search queryset includes department-shared searches matching user's department."""
    dept_eng = _search_discovery_create_dept(tenant_a, name="Engineering")
    dept_hr = _search_discovery_create_dept(tenant_a, name="Human Resources")

    # Set user department attribute
    member_user.department = dept_eng

    dept_search = _search_discovery_create_saved_search(
        tenant_a,
        owner=admin_user,
        name="Engineering Docs",
        visibility="shared_department",
        department=dept_eng,
        is_active=True,
    )
    other_dept_search = _search_discovery_create_saved_search(
        tenant_a,
        owner=admin_user,
        name="HR Payroll Docs",
        visibility="shared_department",
        department=dept_hr,
        is_active=True,
    )

    form = DocumentSearchAlertForm(tenant=tenant_a, user=member_user)
    saved_search_qs = form.fields["saved_search"].queryset

    assert dept_search in saved_search_qs
    assert other_dept_search not in saved_search_qs


@pytest.mark.django_db
def test_search_discovery_search_alert_form_dropdown_scoping_tenant_admin(
    tenant_a, admin_user, member_user
):
    """Test tenant admin user can see all active saved searches in tenant regardless of private visibility."""
    private_member_search = _search_discovery_create_saved_search(
        tenant_a,
        owner=member_user,
        name="Member Secret Search",
        visibility="private",
        is_active=True,
    )
    form = DocumentSearchAlertForm(tenant=tenant_a, user=admin_user)
    saved_search_qs = form.fields["saved_search"].queryset

    assert admin_user.is_tenant_admin is True
    assert private_member_search in saved_search_qs


@pytest.mark.django_db
def test_search_discovery_search_alert_form_cross_tenant_saved_search_rejected(
    tenant_a, tenant_b, admin_user, admin_b
):
    """Test cross-tenant saved_search FK is rejected by reject_foreign."""
    foreign_search = _search_discovery_create_saved_search(
        tenant_b, owner=admin_b, name="Tenant B Secret Search", visibility="public", is_active=True
    )

    form = DocumentSearchAlertForm(
        tenant=tenant_a,
        user=admin_user,
        data={
            "saved_search": foreign_search.pk,
            "frequency": "daily",
            "delivery_channel": "in_app",
            "status": "active",
        },
    )
    assert not form.is_valid()
    assert "saved_search" in form.errors

    # Direct check of reject_foreign behavior
    cleaned = {"saved_search": foreign_search}
    reject_foreign(form, cleaned, ["saved_search"])
    assert "saved_search" in form.errors
    assert "That record belongs to another workspace." in form.errors["saved_search"]


@pytest.mark.django_db
def test_search_discovery_search_alert_form_duplicate_subscription_rejected(
    tenant_a, admin_user, document_saved_search, document_search_alert
):
    """Test duplicate alert subscription for (tenant, saved_search, subscriber) raises clean error."""
    # document_search_alert fixture already has (tenant_a, document_saved_search, admin_user)
    form = DocumentSearchAlertForm(
        tenant=tenant_a,
        user=admin_user,
        data={
            "saved_search": document_saved_search.pk,
            "frequency": "weekly",
            "delivery_channel": "both",
            "status": "active",
        },
    )
    assert not form.is_valid()
    assert "saved_search" in form.errors
    assert "You already have an active alert subscription for this saved search." in str(
        form.errors["saved_search"]
    )


@pytest.mark.django_db
def test_search_discovery_search_alert_form_edit_existing_instance_allowed(
    tenant_a, admin_user, document_saved_search, document_search_alert
):
    """Test updating existing alert instance does not trigger self-duplicate error."""
    form = DocumentSearchAlertForm(
        tenant=tenant_a,
        user=admin_user,
        instance=document_search_alert,
        data={
            "saved_search": document_saved_search.pk,
            "frequency": "monthly",
            "delivery_channel": "email",
            "status": "paused",
            "notes": "Paused for end of quarter",
            "is_active": True,
        },
    )
    assert form.is_valid(), form.errors
    updated = form.save()
    assert updated.frequency == "monthly"
    assert updated.delivery_channel == "email"
    assert updated.status == "paused"


@pytest.mark.django_db
def test_search_discovery_search_alert_form_invalid_choices(tenant_a, admin_user, document_saved_search):
    """Test invalid frequency, delivery channel, or status values fail validation."""
    form = DocumentSearchAlertForm(
        tenant=tenant_a,
        user=admin_user,
        data={
            "saved_search": document_saved_search.pk,
            "frequency": "every_minute",
            "delivery_channel": "sms_pager",
            "status": "cancelled",
        },
    )
    assert not form.is_valid()
    assert "frequency" in form.errors
    assert "delivery_channel" in form.errors
    assert "status" in form.errors


# ============================================================================
# 3. DocumentSearchSynonymForm Tests
# ============================================================================

@pytest.mark.django_db
def test_search_discovery_synonym_form_excluded_fields():
    """Verify system-managed and usage counters are excluded from DocumentSearchSynonymForm."""
    form = DocumentSearchSynonymForm()
    excluded = [
        "tenant",
        "number",
        "created_by",
        "hit_count",
        "created_at",
        "updated_at",
    ]
    for field in excluded:
        assert field not in form.fields, f"Security violation: {field} exposed in DocumentSearchSynonymForm"

    expected_fields = {
        "term",
        "synonyms",
        "category",
        "is_bidirectional",
        "language",
        "is_active",
    }
    assert set(form.fields.keys()) == expected_fields


@pytest.mark.django_db
def test_search_discovery_synonym_form_valid(tenant_a, admin_user):
    """Test DocumentSearchSynonymForm with valid data."""
    form = DocumentSearchSynonymForm(
        tenant=tenant_a,
        data={
            "term": "NDA",
            "synonyms": "non disclosure agreement, confidentiality agreement, mnda",
            "category": "acronym",
            "is_bidirectional": True,
            "language": "en",
            "is_active": True,
        },
    )
    assert form.is_valid(), form.errors
    instance = form.save(commit=False)
    instance.created_by = admin_user
    instance.save()

    assert instance.pk is not None
    assert instance.number.startswith("DSYN-")
    assert instance.term == "NDA"
    assert instance.synonyms == "non disclosure agreement, confidentiality agreement, mnda"
    assert instance.category == "acronym"
    assert instance.is_bidirectional is True


@pytest.mark.django_db
def test_search_discovery_synonym_form_term_contains_comma_rejected(tenant_a):
    """Test base term containing commas is rejected with actionable error."""
    form = DocumentSearchSynonymForm(
        tenant=tenant_a,
        data={
            "term": "SOP, Standard Operating Procedure",
            "synonyms": "work instruction, procedure",
            "category": "acronym",
            "is_bidirectional": True,
            "language": "en",
        },
    )
    assert not form.is_valid()
    assert "term" in form.errors
    assert "Base term should not contain commas" in str(form.errors["term"])


@pytest.mark.django_db
def test_search_discovery_synonym_form_term_blank_rejected(tenant_a):
    """Test blank or whitespace-only term fails validation."""
    for bad_term in ["", "   ", "\t"]:
        form = DocumentSearchSynonymForm(
            tenant=tenant_a,
            data={
                "term": bad_term,
                "synonyms": "contract, agreement",
                "category": "general",
            },
        )
        assert not form.is_valid()
        assert "term" in form.errors


@pytest.mark.django_db
def test_search_discovery_synonym_form_synonyms_blank_or_whitespace_rejected(tenant_a):
    """Test blank, whitespace-only, or comma-only synonyms string fails validation."""
    for bad_synonyms in ["", "   ", ",", ",  , ,"]:
        form = DocumentSearchSynonymForm(
            tenant=tenant_a,
            data={
                "term": "Invoice",
                "synonyms": bad_synonyms,
                "category": "domain",
            },
        )
        assert not form.is_valid()
        assert "synonyms" in form.errors


@pytest.mark.django_db
def test_search_discovery_synonym_form_synonyms_only_self_rejected(tenant_a):
    """Test synonyms list containing only identical representations of base term is rejected."""
    form = DocumentSearchSynonymForm(
        tenant=tenant_a,
        data={
            "term": "Agreement",
            "synonyms": "agreement, Agreement, AGREEMENT",
            "category": "general",
        },
    )
    assert not form.is_valid()
    assert "synonyms" in form.errors
    assert "Synonyms cannot be identical only to the base term itself" in str(form.errors["synonyms"])


@pytest.mark.django_db
def test_search_discovery_synonym_form_synonyms_deduplication_and_stripping(tenant_a):
    """Test synonyms are cleanly normalized, deduplicated case-insensitively, and base term is stripped."""
    form = DocumentSearchSynonymForm(
        tenant=tenant_a,
        data={
            "term": "SOP",
            "synonyms": "Standard Operating Procedure, sop, Work Instruction, standard operating procedure, WORK INSTRUCTION, procedure",
            "category": "acronym",
            "is_bidirectional": True,
            "language": "en",
        },
    )
    assert form.is_valid(), form.errors
    # 'sop' (matching term) should be stripped
    # 'standard operating procedure' duplicate should be removed, preserving original case of first item
    # 'WORK INSTRUCTION' duplicate should be removed, preserving original case of first item
    expected = "Standard Operating Procedure, Work Instruction, procedure"
    assert form.cleaned_data["synonyms"] == expected


@pytest.mark.django_db
def test_search_discovery_synonym_form_invalid_category_rejected(tenant_a):
    """Test invalid category value fails validation."""
    form = DocumentSearchSynonymForm(
        tenant=tenant_a,
        data={
            "term": "Specs",
            "synonyms": "specifications",
            "category": "random_category",
        },
    )
    assert not form.is_valid()
    assert "category" in form.errors


# ============================================================================
# 4. DocumentSearchQueryLogForm / Filter Form Tests
# ============================================================================

@pytest.mark.django_db
def test_search_discovery_query_log_form_excluded_fields():
    """Verify system-managed and tracking fields are excluded from DocumentSearchQueryLogForm."""
    form = DocumentSearchQueryLogForm()
    excluded = [
        "tenant",
        "number",
        "user",
        "filters_applied_json",
        "clicked_document",
        "click_rank",
        "ip_address",
        "session_key",
        "created_at",
        "updated_at",
    ]
    for field in excluded:
        assert field not in form.fields, f"Security violation: {field} exposed in DocumentSearchQueryLogForm"

    expected_fields = {
        "query_text",
        "search_source",
        "results_count",
        "is_zero_result",
        "execution_time_ms",
    }
    assert set(form.fields.keys()) == expected_fields


@pytest.mark.django_db
def test_search_discovery_query_log_form_valid(tenant_a):
    """Test DocumentSearchQueryLogForm with valid search log attributes."""
    form = DocumentSearchQueryLogForm(
        tenant=tenant_a,
        data={
            "query_text": "q4 financial report",
            "search_source": "search_hub",
            "results_count": 8,
            "is_zero_result": False,
            "execution_time_ms": 42,
        },
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["query_text"] == "q4 financial report"
    assert form.cleaned_data["results_count"] == 8
    assert form.cleaned_data["is_zero_result"] is False
    assert form.cleaned_data["execution_time_ms"] == 42


@pytest.mark.django_db
def test_search_discovery_query_log_form_readonly_widgets():
    """Test inspect-only fields have readonly widget attributes set."""
    form = DocumentSearchQueryLogForm()
    assert form.fields["query_text"].widget.attrs.get("readonly") == "readonly"
    assert form.fields["results_count"].widget.attrs.get("readonly") == "readonly"
    assert form.fields["execution_time_ms"].widget.attrs.get("readonly") == "readonly"


@pytest.mark.django_db
def test_search_discovery_query_log_form_invalid_search_source(tenant_a):
    """Test invalid search_source value fails validation."""
    form = DocumentSearchQueryLogForm(
        tenant=tenant_a,
        data={
            "query_text": "audit checklist",
            "search_source": "unsupported_crawler",
            "results_count": 0,
            "is_zero_result": True,
            "execution_time_ms": 10,
        },
    )
    assert not form.is_valid()
    assert "search_source" in form.errors


@pytest.mark.django_db
def test_search_discovery_query_log_filter_form_alias(tenant_a):
    """Test DocumentSearchQueryLogFilterForm alias matches DocumentSearchQueryLogForm functionality."""
    assert DocumentSearchQueryLogFilterForm is DocumentSearchQueryLogForm
    form = DocumentSearchQueryLogFilterForm(
        tenant=tenant_a,
        data={
            "query_text": "filtered query",
            "search_source": "quick_search",
            "results_count": 3,
            "is_zero_result": False,
            "execution_time_ms": 15,
        },
    )
    assert form.is_valid(), form.errors
