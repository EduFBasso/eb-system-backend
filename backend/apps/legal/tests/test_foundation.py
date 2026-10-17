import pytest
from rest_framework.test import APIClient

from apps.authentication.models import SystemUser, Tenant, TenantMembership
from apps.legal.models import LegalCase, LegalClient, LegalLawyerProfile


@pytest.fixture
def legal_context(db):
    user = SystemUser.objects.create_user(
        email="advogado@example.com",
        password="senha-segura-123",
        first_name="Advogado",
        last_name="Legal",
    )
    tenant = Tenant.objects.create(
        name="Escritorio Legal",
        slug="escritorio-legal-foundation",
        ecosystem=Tenant.Ecosystem.LEGAL,
        capabilities={"legal": True},
    )
    membership = TenantMembership.objects.create(
        tenant=tenant,
        professional=user,
        role=TenantMembership.Role.OWNER,
    )
    profile = LegalLawyerProfile.objects.create(
        tenant=tenant,
        system_user=user,
        oab_number="123456",
        oab_state="SP",
        official_name="Advogado Legal",
    )
    return user, tenant, membership, profile


@pytest.mark.django_db
def test_legal_profile_and_case_allow_process_without_client(legal_context):
    user, tenant, _, profile = legal_context

    case = LegalCase.objects.create(
        tenant=tenant,
        created_by=user,
        title="Processo sem cliente cadastrado",
    )

    assert profile.oab_number == "123456"
    assert case.client is None
    assert case.tenant_id == tenant.id


@pytest.mark.django_db
def test_legal_client_belongs_to_tenant(legal_context):
    user, tenant, _, _ = legal_context

    client = LegalClient.objects.create(
        tenant=tenant,
        created_by=user,
        name="Cliente Legal",
    )

    assert client.tenant_id == tenant.id


@pytest.mark.django_db
def test_legal_login_uses_shared_token_endpoint(legal_context):
    user, tenant, _, _ = legal_context

    response = APIClient().post(
        "/token/",
        {
            "login": user.email,
            "password": "senha-segura-123",
            "tenant_slug": tenant.slug,
            "ecosystem": "legal",
        },
        format="json",
    )

    assert response.status_code == 200, response.content
    assert response.data["ecosystem"] == "legal"
    assert response.data["tenant_id"] == tenant.id
    assert response.data["role"] == TenantMembership.Role.OWNER
