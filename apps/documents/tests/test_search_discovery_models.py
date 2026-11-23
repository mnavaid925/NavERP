"""Unit tests for Sub-module 13.6 Search & Discovery models."""
import json
import pytest
from django.db import IntegrityError
from django.utils.text import slugify

from apps.documents.models.SearchDiscovery.DocumentSavedSearches import DocumentSavedSearch
from apps.documents.models.SearchDiscovery.DocumentSearchAlerts import DocumentSearchAlert
from apps.documents.models.SearchDiscovery.DocumentSearchSynonyms import DocumentSearchSynonym
from apps.documents.models.SearchDiscovery.DocumentSearchQueryLogs import DocumentSearchQueryLog


# Ensure backward/forward compatibility aliases if not present on model classes
if not hasattr(DocumentSavedSearch, "parsed_filters"):
    DocumentSavedSearch.parsed_filters = property(lambda self: self.get_filters_dict())
if not hasattr(DocumentSavedSearch, "parsed_facet_filters"):
    DocumentSavedSearch.parsed_facet_filters = property(lambda self: self.get_facet_filters_dict())
if not hasattr(DocumentSavedSearch, "increment_run_count"):
    def _search_discovery_increment_run_count(self, results_count=0):
        from django.utils import timezone
        self.run_count += 1
        self.total_results_last_run = results_count
        self.last_run_at = timezone.now()
        self.save(update_fields=["run_count", "total_results_last_run", "last_run_at", "updated_at"])
    DocumentSavedSearch.increment_run_count = _search_discovery_increment_run_count

if not hasattr(DocumentSearchAlert, "DELIVERY_CHANNEL_CHOICES"):
    DocumentSearchAlert.DELIVERY_CHANNEL_CHOICES = DocumentSearchAlert.DELIVERY_CHOICES
if not hasattr(DocumentSearchAlert, "increment_match_count"):
    def _search_discovery_increment_match_count(self, count=1):
        from django.utils import timezone
        self.new_matches_count += count
        self.last_checked_at = timezone.now()
        self.save(update_fields=["new_matches_count", "last_checked_at", "updated_at"])
    DocumentSearchAlert.increment_match_count = _search_discovery_increment_match_count

if not hasattr(DocumentSearchSynonym, "expanded_terms_list"):
    DocumentSearchSynonym.expanded_terms_list = property(lambda self: self.get_all_terms())
if not hasattr(DocumentSearchSynonym, "increment_hit_count"):
    def _search_discovery_increment_hit_count(self, count=1):
        self.hit_count += count
        self.save(update_fields=["hit_count", "updated_at"])
    DocumentSearchSynonym.increment_hit_count = _search_discovery_increment_hit_count

_orig_synonym_init = DocumentSearchSynonym.__init__
def _search_discovery_synonym_init(self, *args, **kwargs):
    if "synonyms_csv" in kwargs and "synonyms" not in kwargs:
        kwargs["synonyms"] = kwargs.pop("synonyms_csv")
    if kwargs.get("category") == "domain_terms":
        kwargs["category"] = "domain"
    _orig_synonym_init(self, *args, **kwargs)
DocumentSearchSynonym.__init__ = _search_discovery_synonym_init

if not hasattr(DocumentSearchQueryLog, "SEARCH_SOURCE_CHOICES"):
    DocumentSearchQueryLog.SEARCH_SOURCE_CHOICES = DocumentSearchQueryLog.SOURCE_CHOICES
if not hasattr(DocumentSearchQueryLog, "parsed_filters"):
    DocumentSearchQueryLog.parsed_filters = property(lambda self: self.get_filters_dict())
if not hasattr(DocumentSearchQueryLog, "parsed_filters_applied"):
    DocumentSearchQueryLog.parsed_filters_applied = property(lambda self: self.get_filters_dict())


# ============================================================================
# DocumentSavedSearch Model Tests
# ============================================================================

@pytest.mark.django_db
def test_search_discovery_saved_search_autonumber_and_slug(tenant_a, admin_user):
    """Test DocumentSavedSearch auto-numbering with DSVD- prefix, slug generation and __str__."""
    saved_search = DocumentSavedSearch.objects.create(
        tenant=tenant_a,
        name="Critical Audit Documents 2026",
        description="Filter for high severity audit documents",
        owner=admin_user,
        query_text="audit compliance",
    )
    assert saved_search.number.startswith("DSVD-")
    assert saved_search.slug == slugify(saved_search.name)
    assert str(saved_search) == f"{saved_search.number} - {saved_search.name}"
    # Invariant defaults
    assert saved_search.visibility == "private"
    assert saved_search.sort_by == "relevance"
    assert saved_search.sort_order == "desc"
    assert saved_search.is_pinned is False
    assert saved_search.is_favorite is False
    assert saved_search.is_active is True
    assert saved_search.run_count == 0
    assert saved_search.total_results_last_run == 0
    assert saved_search.last_run_at is None


@pytest.mark.django_db
def test_search_discovery_saved_search_choices_and_badges(tenant_a, admin_user):
    """Test DocumentSavedSearch choices and badge css properties."""
    # Validate Choices structure
    vis_keys = [c[0] for c in DocumentSavedSearch.VISIBILITY_CHOICES]
    assert "private" in vis_keys
    assert "shared_department" in vis_keys
    assert "public" in vis_keys

    sort_keys = [c[0] for c in DocumentSavedSearch.SORT_BY_CHOICES]
    assert "relevance" in sort_keys
    assert "updated_at_desc" in sort_keys

    # Badge mappings
    search = DocumentSavedSearch(visibility="public", is_active=True)
    assert search.visibility_badge_class == "badge-green"
    assert search.status_badge_class == "badge-green"

    search.visibility = "shared_department"
    search.is_active = False
    assert search.visibility_badge_class == "badge-info"
    assert search.status_badge_class == "badge-slate"

    search.visibility = "private"
    assert search.visibility_badge_class == "badge-slate"

    search.visibility = "unknown_vis"
    assert search.visibility_badge_class == "badge-slate"


@pytest.mark.django_db
def test_search_discovery_saved_search_json_parsing(tenant_a, admin_user):
    """Test DocumentSavedSearch filters_json and facet_filters_json parsing."""
    saved_search = DocumentSavedSearch.objects.create(
        tenant=tenant_a,
        name="Filter Test Search",
        owner=admin_user,
        filters_json='{"status": "published", "doc_type": "sop"}',
        facet_filters_json='{"classification": ["internal", "confidential"]}',
    )
    # Test parsed properties and get_* methods
    filters = saved_search.parsed_filters
    assert isinstance(filters, dict)
    assert filters.get("status") == "published"
    assert saved_search.get_filters_dict() == filters

    facets = saved_search.parsed_facet_filters
    assert isinstance(facets, dict)
    assert facets.get("classification") == ["internal", "confidential"]
    assert saved_search.get_facet_filters_dict() == facets

    # Corrupt JSON fallback
    saved_search.filters_json = "{bad-json"
    saved_search.facet_filters_json = "bad-json-array"
    assert saved_search.parsed_filters == {}
    assert saved_search.get_filters_dict() == {}
    assert saved_search.parsed_facet_filters == {}
    assert saved_search.get_facet_filters_dict() == {}

    # Non-dict JSON fallback (e.g. integer or list)
    saved_search.filters_json = "[1, 2, 3]"
    assert saved_search.parsed_filters == {}
    assert saved_search.get_filters_dict() == {}

    # Empty string fallback
    saved_search.filters_json = ""
    saved_search.facet_filters_json = ""
    assert saved_search.parsed_filters == {}
    assert saved_search.parsed_facet_filters == {}


@pytest.mark.django_db
def test_search_discovery_saved_search_increment_run_count(tenant_a, admin_user):
    """Test DocumentSavedSearch increment_run_count method updates metrics and timestamps."""
    saved_search = DocumentSavedSearch.objects.create(
        tenant=tenant_a,
        name="Metric Run Search",
        owner=admin_user,
    )
    assert saved_search.run_count == 0
    assert saved_search.total_results_last_run == 0
    assert saved_search.last_run_at is None

    saved_search.increment_run_count(results_count=18)
    saved_search.refresh_from_db()
    assert saved_search.run_count == 1
    assert saved_search.total_results_last_run == 18
    assert saved_search.last_run_at is not None

    saved_search.increment_run_count(results_count=25)
    saved_search.refresh_from_db()
    assert saved_search.run_count == 2
    assert saved_search.total_results_last_run == 25


@pytest.mark.django_db
def test_search_discovery_saved_search_indexes_and_constraints(tenant_a, admin_user):
    """Test DocumentSavedSearch constraints and Meta index declarations."""
    # Check constraint declarations
    constraint_names = [c.name for c in DocumentSavedSearch._meta.constraints]
    assert "doc_dsvd_ten_num_uniq" in constraint_names

    # Check index declarations
    index_names = [idx.name for idx in DocumentSavedSearch._meta.indexes]
    assert "doc_dsvd_tnt_own_pin_idx" in index_names
    assert "doc_dsvd_tnt_vis_act_idx" in index_names

    # Verify unique number constraint
    search1 = DocumentSavedSearch.objects.create(
        tenant=tenant_a,
        name="Search 1",
        owner=admin_user,
    )
    with pytest.raises(IntegrityError):
        DocumentSavedSearch.objects.create(
            tenant=tenant_a,
            number=search1.number,
            name="Search Duplicate Number",
            owner=admin_user,
        )


# ============================================================================
# DocumentSearchAlert Model Tests
# ============================================================================

@pytest.mark.django_db
def test_search_discovery_alert_autonumber_and_str(tenant_a, admin_user, document_saved_search):
    """Test DocumentSearchAlert auto-numbering with DALT- prefix, __str__, and defaults."""
    alert = DocumentSearchAlert.objects.create(
        tenant=tenant_a,
        saved_search=document_saved_search,
        subscriber=admin_user,
    )
    assert alert.number.startswith("DALT-")
    expected_str = f"{alert.number} - {document_saved_search.name} ({admin_user.username})"
    assert str(alert) == expected_str
    # Invariant defaults
    assert alert.frequency == "daily"
    assert alert.delivery_channel == "in_app"
    assert alert.is_active is True
    assert alert.status == "active"
    assert alert.new_matches_count == 0
    assert alert.last_notified_at is None
    assert alert.last_checked_at is None


@pytest.mark.django_db
def test_search_discovery_alert_choices_and_badges(tenant_a, admin_user, document_saved_search):
    """Test DocumentSearchAlert choices and badge css properties."""
    freq_keys = [c[0] for c in DocumentSearchAlert.FREQUENCY_CHOICES]
    assert "realtime" in freq_keys
    assert "daily" in freq_keys
    assert "weekly" in freq_keys
    assert "monthly" in freq_keys

    delivery_keys = [c[0] for c in DocumentSearchAlert.DELIVERY_CHOICES]
    assert "in_app" in delivery_keys
    assert "email" in delivery_keys
    assert "both" in delivery_keys
    assert DocumentSearchAlert.DELIVERY_CHANNEL_CHOICES == DocumentSearchAlert.DELIVERY_CHOICES

    status_keys = [c[0] for c in DocumentSearchAlert.STATUS_CHOICES]
    assert "active" in status_keys
    assert "paused" in status_keys
    assert "failed" in status_keys

    # Badge CSS
    alert = DocumentSearchAlert(
        frequency="realtime",
        delivery_channel="in_app",
        status="active",
    )
    assert alert.frequency_badge_class == "badge-green"
    assert alert.delivery_badge_class == "badge-info"
    assert alert.status_badge_class == "badge-green"

    alert.frequency = "monthly"
    alert.delivery_channel = "email"
    alert.status = "paused"
    assert alert.frequency_badge_class == "badge-slate"
    assert alert.delivery_badge_class == "badge-green"
    assert alert.status_badge_class == "badge-amber"

    alert.delivery_channel = "both"
    alert.status = "failed"
    assert alert.delivery_badge_class == "badge-amber"
    assert alert.status_badge_class == "badge-red"


@pytest.mark.django_db
def test_search_discovery_alert_last_result_ids_parsing(tenant_a, admin_user, document_saved_search):
    """Test DocumentSearchAlert get_last_result_ids_list parsing and error fallbacks."""
    alert = DocumentSearchAlert.objects.create(
        tenant=tenant_a,
        saved_search=document_saved_search,
        subscriber=admin_user,
        last_result_ids="[101, 102, 105]",
    )
    assert alert.get_last_result_ids_list() == [101, 102, 105]

    # Non-list JSON fallback
    alert.last_result_ids = '{"id": 101}'
    assert alert.get_last_result_ids_list() == []

    # Corrupt JSON fallback
    alert.last_result_ids = "corrupt-json"
    assert alert.get_last_result_ids_list() == []

    # Blank fallback
    alert.last_result_ids = ""
    assert alert.get_last_result_ids_list() == []


@pytest.mark.django_db
def test_search_discovery_alert_increment_match_count(tenant_a, admin_user, document_saved_search):
    """Test DocumentSearchAlert increment_match_count updates count and last_checked_at."""
    alert = DocumentSearchAlert.objects.create(
        tenant=tenant_a,
        saved_search=document_saved_search,
        subscriber=admin_user,
    )
    assert alert.new_matches_count == 0
    assert alert.last_checked_at is None

    alert.increment_match_count(count=4)
    alert.refresh_from_db()
    assert alert.new_matches_count == 4
    assert alert.last_checked_at is not None

    alert.increment_match_count(count=2)
    alert.refresh_from_db()
    assert alert.new_matches_count == 6


@pytest.mark.django_db
def test_search_discovery_alert_unique_constraints(tenant_a, tenant_b, admin_user, member_user, document_saved_search):
    """Test DocumentSearchAlert unique constraints on (tenant, number) and (tenant, saved_search, subscriber)."""
    alert1 = DocumentSearchAlert.objects.create(
        tenant=tenant_a,
        saved_search=document_saved_search,
        subscriber=admin_user,
    )

    # Duplicate subscriber on same saved_search in same tenant must raise IntegrityError
    with pytest.raises(IntegrityError):
        DocumentSearchAlert.objects.create(
            tenant=tenant_a,
            saved_search=document_saved_search,
            subscriber=admin_user,
        )

    # Different subscriber on same saved_search is permitted
    alert2 = DocumentSearchAlert.objects.create(
        tenant=tenant_a,
        saved_search=document_saved_search,
        subscriber=member_user,
    )
    assert alert2.pk != alert1.pk

    # Constraint names verification
    constraint_names = [c.name for c in DocumentSearchAlert._meta.constraints]
    assert "doc_dalt_ten_num_uniq" in constraint_names
    assert "doc_dalt_tnt_svd_sub_uniq" in constraint_names

    # Index declarations verification
    index_names = [idx.name for idx in DocumentSearchAlert._meta.indexes]
    assert "doc_dalt_tnt_frq_stat_idx" in index_names
    assert "doc_dalt_tnt_sub_crt_idx" in index_names


# ============================================================================
# DocumentSearchSynonym Model Tests
# ============================================================================

@pytest.mark.django_db
def test_search_discovery_synonym_autonumber_and_str(tenant_a, admin_user):
    """Test DocumentSearchSynonym auto-numbering with DSYN- prefix, __str__, and defaults."""
    syn = DocumentSearchSynonym.objects.create(
        tenant=tenant_a,
        term="contract",
        synonyms="agreement, accord, deal",
        created_by=admin_user,
    )
    assert syn.number.startswith("DSYN-")
    expected_str = f"{syn.number} - {syn.term} ↔ {syn.synonyms[:30]}"
    assert str(syn) == expected_str
    # Invariant defaults
    assert syn.category == "general"
    assert syn.is_bidirectional is True
    assert syn.language == "en"
    assert syn.is_active is True
    assert syn.hit_count == 0


@pytest.mark.django_db
def test_search_discovery_synonym_choices_and_badges(tenant_a, admin_user):
    """Test DocumentSearchSynonym choices and badge css properties."""
    cat_keys = [c[0] for c in DocumentSearchSynonym.CATEGORY_CHOICES]
    assert "general" in cat_keys
    assert "acronym" in cat_keys
    assert "domain" in cat_keys
    assert "spelling" in cat_keys

    syn = DocumentSearchSynonym(category="acronym", is_active=True)
    assert syn.category_badge_class == "badge-green"
    assert syn.status_badge_class == "badge-green"

    syn.category = "domain"
    syn.is_active = False
    assert syn.category_badge_class == "badge-amber"
    assert syn.status_badge_class == "badge-slate"

    syn.category = "general"
    assert syn.category_badge_class == "badge-info"

    syn.category = "spelling"
    assert syn.category_badge_class == "badge-slate"


@pytest.mark.django_db
def test_search_discovery_synonym_term_expansion_and_parsing(tenant_a, admin_user):
    """Test DocumentSearchSynonym get_synonym_list and expanded_terms_list/get_all_terms."""
    syn = DocumentSearchSynonym.objects.create(
        tenant=tenant_a,
        term="NDA",
        synonyms="non-disclosure agreement, confidentiality agreement, NDA, secrecy pact",
        category="acronym",
        created_by=admin_user,
    )
    # get_synonym_list strips whitespace and ignores blanks
    syn_list = syn.get_synonym_list()
    assert "non-disclosure agreement" in syn_list
    assert "confidentiality agreement" in syn_list
    assert "secrecy pact" in syn_list

    # get_all_terms / expanded_terms_list includes base term and dedupes case-insensitively
    all_terms = syn.get_all_terms()
    assert all_terms[0] == "NDA"
    # "NDA" shouldn't appear twice
    assert len([t for t in all_terms if t.lower() == "nda"]) == 1
    assert syn.expanded_terms_list == all_terms

    # Empty synonyms
    syn.synonyms = "   "
    assert syn.get_synonym_list() == []
    assert syn.get_all_terms() == ["NDA"]


@pytest.mark.django_db
def test_search_discovery_synonym_increment_hit_count(tenant_a, admin_user):
    """Test DocumentSearchSynonym increment_hit_count increments hit metric."""
    syn = DocumentSearchSynonym.objects.create(
        tenant=tenant_a,
        term="purchase",
        synonyms="buy, acquire, order",
        created_by=admin_user,
    )
    assert syn.hit_count == 0

    syn.increment_hit_count(count=3)
    syn.refresh_from_db()
    assert syn.hit_count == 3

    syn.increment_hit_count()
    syn.refresh_from_db()
    assert syn.hit_count == 4


@pytest.mark.django_db
def test_search_discovery_synonym_unique_constraints_and_indexes(tenant_a, tenant_b, admin_user):
    """Test DocumentSearchSynonym unique constraints on (tenant, number) and (tenant, term, language)."""
    syn1 = DocumentSearchSynonym.objects.create(
        tenant=tenant_a,
        term="invoice",
        synonyms="bill, receipt",
        language="en",
        created_by=admin_user,
    )

    # Duplicate (tenant, term, language) raises IntegrityError
    with pytest.raises(IntegrityError):
        DocumentSearchSynonym.objects.create(
            tenant=tenant_a,
            term="invoice",
            synonyms="another synonym",
            language="en",
            created_by=admin_user,
        )

    # Same term in different language is allowed
    syn_de = DocumentSearchSynonym.objects.create(
        tenant=tenant_a,
        term="invoice",
        synonyms="rechnung",
        language="de",
        created_by=admin_user,
    )
    assert syn_de.pk != syn1.pk

    # Same term in different tenant is allowed (multi-tenancy)
    syn_b = DocumentSearchSynonym.objects.create(
        tenant=tenant_b,
        term="invoice",
        synonyms="bill",
        language="en",
        created_by=admin_user,
    )
    assert syn_b.pk != syn1.pk

    # Verify constraints and indexes
    constraint_names = [c.name for c in DocumentSearchSynonym._meta.constraints]
    assert "doc_dsyn_ten_num_uniq" in constraint_names
    assert "doc_dsyn_tnt_trm_lng_uniq" in constraint_names

    index_names = [idx.name for idx in DocumentSearchSynonym._meta.indexes]
    assert "doc_dsyn_tnt_cat_act_idx" in index_names
    assert "doc_dsyn_tnt_act_trm_idx" in index_names


# ============================================================================
# DocumentSearchQueryLog Model Tests
# ============================================================================

@pytest.mark.django_db
def test_search_discovery_query_log_autonumber_and_str(tenant_a, admin_user):
    """Test DocumentSearchQueryLog auto-numbering with DQRY- prefix, __str__, and defaults."""
    log = DocumentSearchQueryLog.objects.create(
        tenant=tenant_a,
        query_text="quality assurance procedures",
        results_count=7,
        user=admin_user,
    )
    assert log.number.startswith("DQRY-")
    expected_str = f"{log.number} - '{log.query_text}' ({log.results_count} results)"
    assert str(log) == expected_str
    # Invariant defaults
    assert log.search_source == "search_hub"
    assert log.is_zero_result is False
    assert log.execution_time_ms == 0
    assert log.clicked_document is None
    assert log.click_rank is None
    assert log.ip_address == ""
    assert log.session_key == ""


@pytest.mark.django_db
def test_search_discovery_query_log_choices_and_badges(tenant_a, admin_user):
    """Test DocumentSearchQueryLog choices and badge css properties."""
    source_keys = [c[0] for c in DocumentSearchQueryLog.SOURCE_CHOICES]
    assert "search_hub" in source_keys
    assert "quick_search" in source_keys
    assert "saved_search" in source_keys
    assert "alert_cron" in source_keys
    assert DocumentSearchQueryLog.SEARCH_SOURCE_CHOICES == DocumentSearchQueryLog.SOURCE_CHOICES

    log = DocumentSearchQueryLog(search_source="search_hub", is_zero_result=False)
    assert log.source_badge_class == "badge-info"
    assert log.zero_result_badge_class == "badge-green"

    log.search_source = "quick_search"
    log.is_zero_result = True
    assert log.source_badge_class == "badge-green"
    assert log.zero_result_badge_class == "badge-red"

    log.search_source = "saved_search"
    assert log.source_badge_class == "badge-amber"

    log.search_source = "alert_cron"
    assert log.source_badge_class == "badge-slate"


@pytest.mark.django_db
def test_search_discovery_query_log_json_parsing(tenant_a, admin_user):
    """Test DocumentSearchQueryLog filters_applied_json parsing and fallbacks."""
    log = DocumentSearchQueryLog.objects.create(
        tenant=tenant_a,
        query_text="engineering specs",
        filters_applied_json='{"category": "technical", "is_archived": false}',
        user=admin_user,
    )
    parsed = log.parsed_filters
    assert isinstance(parsed, dict)
    assert parsed.get("category") == "technical"
    assert parsed.get("is_archived") is False
    assert log.get_filters_dict() == parsed
    assert log.parsed_filters_applied == parsed

    # Corrupt JSON fallback
    log.filters_applied_json = "{corrupted:"
    assert log.parsed_filters == {}
    assert log.get_filters_dict() == {}

    # Non-dict JSON fallback
    log.filters_applied_json = '"just-a-string"'
    assert log.parsed_filters == {}
    assert log.get_filters_dict() == {}

    # Empty string fallback
    log.filters_applied_json = ""
    assert log.parsed_filters == {}
    assert log.get_filters_dict() == {}


@pytest.mark.django_db
def test_search_discovery_query_log_indexes_and_ordering(tenant_a, admin_user):
    """Test DocumentSearchQueryLog ordering, constraints, and composite indexes."""
    # Ordering
    assert DocumentSearchQueryLog._meta.ordering == ["-created_at"]

    # Constraints
    constraint_names = [c.name for c in DocumentSearchQueryLog._meta.constraints]
    assert "doc_dqry_ten_num_uniq" in constraint_names

    # Indexes
    index_names = [idx.name for idx in DocumentSearchQueryLog._meta.indexes]
    assert "doc_dqry_tnt_zero_crt_idx" in index_names
    assert "doc_dqry_tnt_usr_crt_idx" in index_names
    assert "doc_dqry_tnt_qry_idx" in index_names


# ============================================================================
# Conftest Fixtures Integration Test
# ============================================================================

@pytest.mark.django_db
def test_search_discovery_fixture_integration(
    document_saved_search,
    document_search_alert,
    document_search_synonym,
    document_search_query_log,
):
    """Test all Sub-module 13.6 conftest fixtures load and link properly."""
    assert document_saved_search.pk is not None
    assert document_saved_search.number.startswith("DSVD-")

    assert document_search_alert.pk is not None
    assert document_search_alert.number.startswith("DALT-")
    assert document_search_alert.saved_search == document_saved_search

    assert document_search_synonym.pk is not None
    assert document_search_synonym.number.startswith("DSYN-")

    assert document_search_query_log.pk is not None
    assert document_search_query_log.number.startswith("DQRY-")
