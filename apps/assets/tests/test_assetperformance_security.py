"""Security, multi-tenancy, authorization, and IDOR protection test suite for Module 11.6 Asset Performance."""
from decimal import Decimal
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.assets.models import (
    AssetDowntimeLog,
    AssetOeeRecord,
    AssetEnergyReading,
    AssetPerformanceScorecard,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# 1. Cross-Tenant IDOR Protection (404 on Foreign Tenant Records)
# ==============================================================================

def test_assetperformance_security_idor_downtime_log(client, admin_user, downtime_log_b):
    client.force_login(admin_user)
    # Detail
    assert client.get(reverse("assets:asset_downtime_log_detail", args=[downtime_log_b.pk])).status_code == 404
    # Edit
    assert client.get(reverse("assets:asset_downtime_log_edit", args=[downtime_log_b.pk])).status_code == 404
    assert client.post(reverse("assets:asset_downtime_log_edit", args=[downtime_log_b.pk]), {}).status_code == 404
    # Delete
    assert client.post(reverse("assets:asset_downtime_log_delete", args=[downtime_log_b.pk])).status_code == 404
    # Custom action resolve
    assert client.get(reverse("assets:asset_downtime_log_resolve", args=[downtime_log_b.pk])).status_code == 404
    assert client.post(reverse("assets:asset_downtime_log_resolve", args=[downtime_log_b.pk]), {}).status_code == 404


def test_assetperformance_security_idor_oee_record(client, admin_user, oee_record_b):
    client.force_login(admin_user)
    # Detail
    assert client.get(reverse("assets:asset_oee_record_detail", args=[oee_record_b.pk])).status_code == 404
    # Edit
    assert client.get(reverse("assets:asset_oee_record_edit", args=[oee_record_b.pk])).status_code == 404
    assert client.post(reverse("assets:asset_oee_record_edit", args=[oee_record_b.pk]), {}).status_code == 404
    # Delete
    assert client.post(reverse("assets:asset_oee_record_delete", args=[oee_record_b.pk])).status_code == 404
    # Custom action finalize
    assert client.post(reverse("assets:asset_oee_record_finalize", args=[oee_record_b.pk])).status_code == 404


def test_assetperformance_security_idor_energy_reading(client, admin_user, energy_reading_b):
    client.force_login(admin_user)
    # Detail
    assert client.get(reverse("assets:asset_energy_reading_detail", args=[energy_reading_b.pk])).status_code == 404
    # Edit
    assert client.get(reverse("assets:asset_energy_reading_edit", args=[energy_reading_b.pk])).status_code == 404
    assert client.post(reverse("assets:asset_energy_reading_edit", args=[energy_reading_b.pk]), {}).status_code == 404
    # Delete
    assert client.post(reverse("assets:asset_energy_reading_delete", args=[energy_reading_b.pk])).status_code == 404
    # Custom action validate
    assert client.post(reverse("assets:asset_energy_reading_validate", args=[energy_reading_b.pk])).status_code == 404


def test_assetperformance_security_idor_scorecard(client, admin_user, performance_scorecard_b):
    client.force_login(admin_user)
    # Detail
    assert client.get(reverse("assets:asset_performance_scorecard_detail", args=[performance_scorecard_b.pk])).status_code == 404
    # Edit
    assert client.get(reverse("assets:asset_performance_scorecard_edit", args=[performance_scorecard_b.pk])).status_code == 404
    assert client.post(reverse("assets:asset_performance_scorecard_edit", args=[performance_scorecard_b.pk]), {}).status_code == 404
    # Delete
    assert client.post(reverse("assets:asset_performance_scorecard_delete", args=[performance_scorecard_b.pk])).status_code == 404
    # Custom action publish
    assert client.post(reverse("assets:asset_performance_scorecard_publish", args=[performance_scorecard_b.pk])).status_code == 404


def test_assetperformance_security_reverse_idor(client, admin_b, downtime_log_a, oee_record_a, energy_reading_a, performance_scorecard_a):
    client.force_login(admin_b)
    # Globex user accessing Acme records must receive 404
    assert client.get(reverse("assets:asset_downtime_log_detail", args=[downtime_log_a.pk])).status_code == 404
    assert client.get(reverse("assets:asset_oee_record_detail", args=[oee_record_a.pk])).status_code == 404
    assert client.get(reverse("assets:asset_energy_reading_detail", args=[energy_reading_a.pk])).status_code == 404
    assert client.get(reverse("assets:asset_performance_scorecard_detail", args=[performance_scorecard_a.pk])).status_code == 404


# ==============================================================================
# 2. List Isolation (Zero Cross-Tenant Leakage)
# ==============================================================================

def test_assetperformance_security_list_isolation(client, admin_user, downtime_log_a, downtime_log_b, oee_record_a, oee_record_b, energy_reading_a, energy_reading_b, performance_scorecard_a, performance_scorecard_b):
    client.force_login(admin_user)
    # Acme list must show Acme records and NOT show Globex records
    downtime_resp = client.get(reverse("assets:asset_downtime_log_list"))
    assert downtime_log_a in downtime_resp.context["page_obj"].object_list
    assert downtime_log_b not in downtime_resp.context["page_obj"].object_list
    assert downtime_log_b.failure_description not in downtime_resp.content.decode()

    oee_resp = client.get(reverse("assets:asset_oee_record_list"))
    assert oee_record_a in oee_resp.context["page_obj"].object_list
    assert oee_record_b not in oee_resp.context["page_obj"].object_list

    energy_resp = client.get(reverse("assets:asset_energy_reading_list"))
    assert energy_reading_a in energy_resp.context["page_obj"].object_list
    assert energy_reading_b not in energy_resp.context["page_obj"].object_list

    scorecard_resp = client.get(reverse("assets:asset_performance_scorecard_list"))
    assert performance_scorecard_a in scorecard_resp.context["page_obj"].object_list
    assert performance_scorecard_b not in scorecard_resp.context["page_obj"].object_list


# ==============================================================================
# 3. Unauthenticated Access Protection (302 Redirect to Login)
# ==============================================================================

def test_assetperformance_security_unauthenticated_redirect(client, downtime_log_a, oee_record_a, energy_reading_a, performance_scorecard_a):
    endpoints = [
        reverse("assets:asset_downtime_log_list"),
        reverse("assets:asset_downtime_log_create"),
        reverse("assets:asset_downtime_log_detail", args=[downtime_log_a.pk]),
        reverse("assets:asset_downtime_log_edit", args=[downtime_log_a.pk]),
        reverse("assets:asset_downtime_log_delete", args=[downtime_log_a.pk]),
        reverse("assets:asset_downtime_log_resolve", args=[downtime_log_a.pk]),
        reverse("assets:asset_oee_record_list"),
        reverse("assets:asset_oee_record_create"),
        reverse("assets:asset_oee_record_detail", args=[oee_record_a.pk]),
        reverse("assets:asset_oee_record_edit", args=[oee_record_a.pk]),
        reverse("assets:asset_oee_record_delete", args=[oee_record_a.pk]),
        reverse("assets:asset_oee_record_finalize", args=[oee_record_a.pk]),
        reverse("assets:asset_energy_reading_list"),
        reverse("assets:asset_energy_reading_create"),
        reverse("assets:asset_energy_reading_detail", args=[energy_reading_a.pk]),
        reverse("assets:asset_energy_reading_edit", args=[energy_reading_a.pk]),
        reverse("assets:asset_energy_reading_delete", args=[energy_reading_a.pk]),
        reverse("assets:asset_energy_reading_validate", args=[energy_reading_a.pk]),
        reverse("assets:asset_performance_scorecard_list"),
        reverse("assets:asset_performance_scorecard_create"),
        reverse("assets:asset_performance_scorecard_detail", args=[performance_scorecard_a.pk]),
        reverse("assets:asset_performance_scorecard_edit", args=[performance_scorecard_a.pk]),
        reverse("assets:asset_performance_scorecard_delete", args=[performance_scorecard_a.pk]),
        reverse("assets:asset_performance_scorecard_publish", args=[performance_scorecard_a.pk]),
    ]
    for url in endpoints:
        resp = client.get(url)
        assert resp.status_code == 302, f"Expected 302 redirect for {url}, got {resp.status_code}"


# ==============================================================================
# 4. Status Guard Enforcement on State Transitions
# ==============================================================================

def test_assetperformance_security_status_guards(client, admin_user, downtime_log_a, oee_record_a, energy_reading_a, performance_scorecard_a):
    client.force_login(admin_user)

    # 1. DowntimeLog resolve on non-active log
    downtime_log_a.status = "resolved"
    downtime_log_a.save()
    resp = client.post(reverse("assets:asset_downtime_log_resolve", args=[downtime_log_a.pk]), {"resolution_notes": "test"})
    assert resp.status_code == 302
    assert downtime_log_a.status == "resolved"

    # 2. OeeRecord finalize on non-draft record
    oee_record_a.status = "finalized"
    oee_record_a.save()
    resp_oee = client.post(reverse("assets:asset_oee_record_finalize", args=[oee_record_a.pk]))
    assert resp_oee.status_code == 302
    assert oee_record_a.status == "finalized"

    # 3. EnergyReading validate on non-pending/flagged record
    energy_reading_a.status = "cancelled"
    energy_reading_a.save()
    resp_energy = client.post(reverse("assets:asset_energy_reading_validate", args=[energy_reading_a.pk]))
    assert resp_energy.status_code == 302
    assert energy_reading_a.status == "cancelled"

    # 4. Scorecard publish on non-draft scorecard
    performance_scorecard_a.status = "archived"
    performance_scorecard_a.save()
    resp_sc = client.post(reverse("assets:asset_performance_scorecard_publish", args=[performance_scorecard_a.pk]))
    assert resp_sc.status_code == 302
    assert performance_scorecard_a.status == "archived"


# ==============================================================================
# 5. HTTP Method Guard (require_POST on Deletions)
# ==============================================================================

def test_assetperformance_security_delete_method_guard(client, admin_user, downtime_log_a, oee_record_a, energy_reading_a, performance_scorecard_a):
    client.force_login(admin_user)
    delete_urls = [
        reverse("assets:asset_downtime_log_delete", args=[downtime_log_a.pk]),
        reverse("assets:asset_oee_record_delete", args=[oee_record_a.pk]),
        reverse("assets:asset_energy_reading_delete", args=[energy_reading_a.pk]),
        reverse("assets:asset_performance_scorecard_delete", args=[performance_scorecard_a.pk]),
    ]
    for url in delete_urls:
        resp = client.get(url)
        assert resp.status_code == 405, f"Expected 405 Method Not Allowed for GET on {url}, got {resp.status_code}"
