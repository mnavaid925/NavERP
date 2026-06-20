"""Core app test fixtures."""
import pytest
from django.test import Client


@pytest.fixture
def party_a(db, tenant_a):
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_a, name="Acme Party", kind="organization")


@pytest.fixture
def party_b(db, tenant_b):
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_b, name="Globex Party", kind="organization")
